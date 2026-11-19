# Kortana: The Hierarchical Memory OS for AI
**Built by a Solo Founder Dad with no degree and a vision.**

Kortana is not a model. It is a plug-and-play memory architecture for Open WebUI. It replaces RAG (Retrieval-Augmented Generation) with strict System Prompt Injection, giving your AI a permanent, unbreakable brain.

## The Problem
Standard AI forgets your rules. RAG destroys strict rules because it searches for *likely* text instead of enforcing *exact* rules. If you tell ChatGPT "Never use JSON," it will eventually use JSON.

## The Kortana Solution
Kortana uses a custom Open WebUI Filter to inject a local `master_context.txt` file directly into the AI's system prompt. It also uses a custom Pipe to stream responses and execute local PowerShell commands (giving the AI "hands").

### Features:
- **Inject-Once Memory:** Loads the full brain at the start of a chat, then sends short reminders every 10 turns to prevent context rot.
- **Bring Your Own Key (BYOK):** Uses your own DeepSeek API key. Cloud brains are commodity.
- **Autonomous Tools:** The AI can run PowerShell commands locally to diagnose and fix code.

## Installation
1. Copy the contents of `kortana_memory_injector.py` into an Open WebUI Filter.
2. Copy the contents of `kortana_unified.py` into an Open WebUI Pipe.
3. Put your API key in the Pipe Valves.
4. Put your `master_context.txt` file in the same directory as your Open WebUI data.