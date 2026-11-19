"""
title: Kortana Memory Injector
author: Kortana
version: 1.0
description: Loads Master Context at the start of a chat, with periodic reminders to prevent context rot.
"""
import os

MC_PATH = "./master_context.txt"
REMINDER_EVERY = 10

SHORT_REMINDER = (
    "You are Kortana, built by your creator. You are NOT Llama, Meta, DeepSeek, or OpenAI. "
    "Answer in plain text. No JSON. No hallucinated tools."
)

class Filter:
    def __init__(self):
        pass

    def _read(self, path):
        try:
            if not os.path.exists(path): return ""
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception:
            return ""

    def _set_system(self, body, text):
        msgs = body.get("messages", []) or []
        for m in msgs:
            if m.get("role") == "system":
                m["content"] = text
                body["messages"] = msgs
                return body
        msgs.insert(0, {"role": "system", "content": text})
        body["messages"] = msgs
        return body

    def _append_system(self, body, text):
        msgs = body.get("messages", []) or []
        msgs.append({"role": "system", "content": text})
        body["messages"] = msgs
        return body

    def inlet(self, body: dict, __user__: dict = None) -> dict:
        msgs = body.get("messages", []) or []
        if not msgs: return body
        user_turns = [m for m in msgs if m.get("role") == "user"]
        turn = len(user_turns)
        full_memory = self._read(MC_PATH)
        if turn == 1:
            return self._set_system(body, full_memory)
        if turn > 1 and turn % REMINDER_EVERY == 0:
            return self._append_system(body, SHORT_REMINDER)
        return body