"""
title: Kortana Unified Brain
author: Kortana
version: 1.0
description: Routes to DeepSeek API with streaming and local PowerShell execution.
"""
import os, json, urllib.request, subprocess, time
from pydantic import BaseModel, Field

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 4
POWERSHELL_TIMEOUT = 120

BUILTIN_TOOLS = [
    {"type":"function","function":{
        "name":"run_powershell",
        "description":"Executes a PowerShell command on the local machine and returns the output.",
        "parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}}
]

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
    try:
        r=subprocess.run(["powershell","-NoProfile","-Command",command or ""],
                         capture_output=True,text=True,timeout=POWERSHELL_TIMEOUT)
        if r.returncode==0:
            return "SUCCESS:\n"+(r.stdout or "")+(r.stderr or "")
        return "ERROR:\n"+(r.stderr or "")+(r.stdout or "")
    except Exception as e:
        return "EXECUTION FAILED: "+str(e)

def _exec_tool(name,args):
    if name=="run_powershell": return _run_powershell(args.get("command",""))
    return "UNKNOWN TOOL: "+name

class Pipe:
    class Valves(BaseModel):
        deepseek_model: str = Field(default="deepseek-chat")
        deepseek_key: str = Field(default="")

    def __init__(self):
        self.type="pipe"; self.id="kortana_unified"; self.name="Kortana"
        self.valves=self.Valves()

    def _stream_cloud(self, messages, tools):
        key = self.valves.deepseek_key.strip() or os.environ.get("DEEPSEEK_API_KEY","")
        if not key:
            raise RuntimeError("No DeepSeek key. Set in Valves or DEEPSEEK_API_KEY env.")
        data={"model":self.valves.deepseek_model,"messages":_clean(messages),
              "max_tokens":MAX_TOKENS,"tools":tools,"stream": True}
        body=json.dumps(data).encode()
        req=urllib.request.Request(DEEPSEEK_URL,data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
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
        work=list(messages)
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
                if not tool_calls: return
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
                for tc_id,name,args_dict in exec_plan:
                    yield "\n> "+name+"\n"
                    result=_exec_tool(name,args_dict)
                    work.append({"role":"tool","tool_call_id":tc_id,"content":_truncate(result,8000)})
            except Exception as e:
                yield "\n\n[Kortana Error: " + str(e) + "]"
                return