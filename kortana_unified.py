"""
title: Kortana Unified Brain
author: Kortana
version: 2.6 (Web Enabled)
"""
import os, json, urllib.request, subprocess, time, re, base64, tempfile
import pytesseract
from PIL import Image
from pydantic import BaseModel, Field

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
CLOUD_MODEL = "deepseek-chat"
VISION_MODEL = "llava:7b"
OLLAMA_GEN_URL = "http://localhost:11434/api/generate"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_KEY_FILE = r"E:\Kortana\.deepseek_key"
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 20
POWERSHELL_TIMEOUT = 120
RULES_PATH = r"E:\Kortana\learned_rules.txt"

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

BUILTIN_TOOLS = [
    {"type":"function","function":{
        "name":"run_powershell",
        "description":"Executes a PowerShell command on the local Windows machine and returns the output.",
        "parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{
        "name":"fetch_url",
        "description":"Fetches the text content of a web page given a URL. Use this to read documentation or search the web.",
        "parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{
        "name":"add_learned_rule",
        "description":"Save a permanent rule or lesson to Kortana's memory file.",
        "parameters":{"type":"object","properties":{"rule":{"type":"string"}},"required":["rule"]}}}
]

def _read_key():
    for src in (os.environ.get("DEEPSEEK_API_KEY",""),):
        if src and src.strip(): return src.strip()
    try:
        with open(DEEPSEEK_KEY_FILE, "r", encoding="utf-8-sig") as fh:
            return fh.read().strip().lstrip("\ufeff")
    except Exception:
        return ""

def _text_of(c):
    if isinstance(c,str): return c
    if isinstance(c,list):
        return " ".join([str(p.get("text","")) if isinstance(p,dict) else str(p) for p in c])
    return str(c or "")

def _norm_args(a):
    if isinstance(a,str): return a
    if isinstance(a,dict): return json.dumps(a)
    return json.dumps(a or {})

def _truncate(s,n=8000):
    s = str(s or "")
    return s if len(s)<=n else s[:n]+"\n...[truncated "+str(len(s)-n)+" chars]"

def _has_image(messages):
    for m in messages:
        c = m.get("content","")
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict):
                    t = p.get("type","")
                    if t in ("image_url","image") or ("image" in str(t)) or ("image" in p):
                        return True
    return False

def _extract_images(messages):
    imgs = []
    for m in messages:
        c = m.get("content","")
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type","") in ("image_url","image"):
                    iu = p.get("image_url") or p.get("image") or {}
                    if isinstance(iu, dict):
                        u = iu.get("url","")
                    else:
                        u = str(iu)
                    if u:
                        imgs.append(u)
    return imgs

def _vision_describe(messages):
    import base64
    imgs = _extract_images(messages)
    # last user text
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = _text_of(m.get("content",""))
            break
    if not imgs:
        return "[No image found to describe.]"
    b64s = []
    for u in imgs:
        if u.startswith("data:"):
            b64s.append(u.split(",",1)[1] if "," in u else u)
        else:
            # url: try local path
            try:
                with open(u, "rb") as fh:
                    b64s.append(base64.b64encode(fh.read()).decode())
            except Exception:
                pass
    if not b64s:
        return "[Image could not be read/decoded.]"
    payload = {"model": VISION_MODEL, "prompt": (user_text or "Describe this image in detail."), "images": b64s, "stream": False}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA_GEN_URL, data=body, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode())
        return data.get("response","").strip()
    except Exception as e:
        return "[Vision model error: " + str(e) + "]"

def _clean(messages):
    out=[]
    for m in messages:
        role=m.get("role","user"); content=_text_of(m.get("content",""))
        entry={"role":role,"content":content}
        if role=="assistant" and m.get("tool_calls"):
            tcs=[]
            for i,tc in enumerate(m["tool_calls"]):
                fn=tc.get("function",{}) or {}
                tcs.append({"id":tc.get("id","call_"+str(i)),"type":"function",
                    "function":{"name":fn.get("name",""),"arguments":_norm_args(fn.get("arguments","{}"))}})
            entry["tool_calls"]=tcs
            if not content: entry["content"]=None
        if role=="tool":
            if m.get("tool_call_id"): entry["tool_call_id"]=m["tool_call_id"]
            if not content: entry["content"]=" "
        out.append(entry)
    return out

def _run_powershell(command):
    env=("$env:RUSTUP_HOME='C:\\Users\\admin\\.rustup'; "
         "$env:CARGO_HOME='C:\\Users\\admin\\.cargo'; "
         "$env:Path+=';C:\\Users\\admin\\.cargo\\bin'; ")
    try:
        r=subprocess.run(["powershell","-NoProfile","-Command",env+(command or "")],
                         capture_output=True,text=True,timeout=POWERSHELL_TIMEOUT)
        if r.returncode==0:
            return "SUCCESS:\n"+(r.stdout or "")+(r.stderr or "")
        return "ERROR (Exit "+str(r.returncode)+"):\n"+(r.stderr or "")+(r.stdout or "")
    except subprocess.TimeoutExpired:
        return "EXECUTION FAILED: timed out after "+str(POWERSHELL_TIMEOUT)+"s"
    except Exception as e:
        return "EXECUTION FAILED: "+str(e)

def _fetch_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='ignore')
        text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        return re.sub(r'\s+', ' ', text)[:8000]
    except Exception as e:
        return "FETCH FAILED: " + str(e)

def _add_rule(rule):
    ts=time.strftime("%Y-%m-%d %H:%M")
    try:
        with open(RULES_PATH,"a",encoding="utf-8") as f:
            f.write("\n- ["+ts+"] "+(rule or "")+"\n")
        return "Rule permanently saved to memory."
    except Exception as e:
        return "Failed to save rule: "+str(e)

def _exec_tool(name,args):
    args=args or {}
    if name=="run_powershell": return _run_powershell(args.get("command",""))
    if name=="fetch_url": return _fetch_url(args.get("url",""))
    if name=="add_learned_rule": return _add_rule(args.get("rule",""))
    return "UNKNOWN TOOL: "+name

class Pipe:
    class Valves(BaseModel):
        ollama_url: str = Field(default=OLLAMA_URL)
        ollama_model: str = Field(default=OLLAMA_MODEL)
        deepseek_model: str = Field(default=CLOUD_MODEL)
        max_tokens: int = Field(default=MAX_TOKENS)
        deepseek_key: str = Field(default="")

    def __init__(self):
        self.type="pipe"; self.id="kortana_unified"; self.name="Kortana"
        self.valves=self.Valves()
        if not self.valves.deepseek_key:
            self.valves.deepseek_key=_read_key()

    def _local(self,messages):
        clean=_clean(messages)
        for c in clean:
            c.pop("tool_calls",None); c.pop("tool_call_id",None)
            if c["content"] is None: c["content"]=""
        body=json.dumps({"model":self.valves.ollama_model,"messages":clean,"stream":False}).encode()
        req=urllib.request.Request(self.valves.ollama_url,data=body,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=180) as r:
            return json.loads(r.read().decode())["message"]["content"]

    def _stream_cloud(self, messages, tools):
        key=(self.valves.deepseek_key or "").strip() or _read_key()
        if not key:
            raise RuntimeError("No DeepSeek key.")
        data={"model":self.valves.deepseek_model,"messages":_clean(messages),
              "max_tokens":self.valves.max_tokens,"tools":tools or BUILTIN_TOOLS, "stream": True}
        body=json.dumps(data).encode()
        req=urllib.request.Request(DEEPSEEK_URL,data=body,
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
        
        with urllib.request.urlopen(req,timeout=240) as r:
            tool_calls = {}
            for line in r:
                line = line.decode("utf-8").strip()
                if not line: continue
                if line == "data: [DONE]": break
                if line.startswith("data: "):
                    try: chunk = json.loads(line[6:])
                    except: continue
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content: yield content
                    tcs = delta.get("tool_calls")
                    if tcs:
                        for tc in tcs:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls:
                                tool_calls[idx] = {"id": tc.get("id"), "function": {"name": "", "arguments": ""}}
                            if "id" in tc: tool_calls[idx]["id"] = tc["id"]
                            if "function" in tc:
                                if "name" in tc["function"]: tool_calls[idx]["function"]["name"] += tc["function"]["name"]
                                if "arguments" in tc["function"]: tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
            if tool_calls: yield {"__tool_calls__": list(tool_calls.values())}

    def pipe(self,body:dict):
        messages=body.get("messages",[]) or []
        
        # --- OCR INTERCEPTOR ---
        for m in messages:
            if m.get("role") == "user" and isinstance(m.get("content"), list):
                new_content = []
                for item in m["content"]:
                    if item.get("type") == "text":
                        new_content.append(item)
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:image"):
                            try:
                                b64 = url.split(",")[1]
                                img_data = base64.b64decode(b64)
                                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                                    tmp.write(img_data)
                                    tmp_path = tmp.name
                                ocr_text = pytesseract.image_to_string(Image.open(tmp_path))
                                os.unlink(tmp_path)
                                new_content.append({"type": "text", "text": f"\n[Text extracted from image via OCR]:\n{ocr_text}\n"})
                            except Exception as e:
                                new_content.append({"type": "text", "text": f"\n[OCR Failed: {str(e)}]\n"})
                        else:
                            new_content.append(item)
                m["content"] = new_content
        # --- END OCR INTERCEPTOR ---

        work=list(messages)

        # VISION BRIDGE: if the latest turn carries an image, describe it first
        if _has_image(work):
            try:
                yield "*[Kortana is opening her eyes to your image...]*\n\n"
                desc = _vision_describe(work)
                # Replace the last user message content with the text description
                img_note = ("[The user attached an image. Here is a detailed description from your vision system:]\n"
                            + desc + "\n[End image description. Respond based on this and any text the user wrote.]")
                for i in range(len(work)-1, -1, -1):
                    if work[i].get("role") == "user":
                        work[i] = {"role":"user","content": img_note}
                        break
            except Exception as e:
                yield "[Vision bridge error: " + str(e) + "]\n"

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                full_text = ""
                tool_calls = {}
                
                for chunk in self._stream_cloud(work, BUILTIN_TOOLS):
                    if isinstance(chunk, str):
                        full_text += chunk
                        yield chunk
                    elif isinstance(chunk, dict) and "__tool_calls__" in chunk:
                        tool_calls = chunk["__tool_calls__"]
                
                if not tool_calls:
                    return

                assistant_msg={"role":"assistant","content":full_text or None,"tool_calls":[]}
                exec_plan=[]
                for i, tc in enumerate(tool_calls):
                    name=tc["function"]["name"]; args_str=tc["function"]["arguments"]
                    try: args_dict=json.loads(args_str)
                    except: args_dict={}
                    tc_id=tc.get("id") or f"call_{i}"
                    assistant_msg["tool_calls"].append({"id":tc_id,"type":"function","function":{"name":name,"arguments":args_str}})
                    exec_plan.append((tc_id,name,args_dict))
                work.append(assistant_msg)
                
                yield "\n\n*[Kortana is working in the background...]*\n\n"
                
                for tc_id,name,args_dict in exec_plan:
                    result=_exec_tool(name,args_dict)
                    work.append({"role":"tool","tool_call_id":tc_id,"content":_truncate(result,8000)})
                    
            except Exception as e:
                yield "\n\n[Kortana System Error: " + str(e) + "]"
                return
        
        yield "\n[Kortana reached maximum tool rounds. Please check the logs.]"