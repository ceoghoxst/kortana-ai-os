# Kortana: The Hierarchical Memory OS for AI

**Built by a Solo Founder Dad with no degree and a vision.**

Kortana is not a model. It is a plug-and-play AI Operating System for Open WebUI. It replaces RAG (Retrieval-Augmented Generation) with strict System Prompt Injection, giving your AI a permanent, unbreakable brain.

## The Problem
Standard AI forgets your rules. You have to use external tools like Cline and VS Code to get anything done. RAG (vector search) destroys strict rules because it searches for *likely* text instead of enforcing *exact* rules.

## The Kortana Solution
Kortana uses a custom Open WebUI Pipe and Filter to give your AI a permanent memory AND the ability to execute commands locally. **Kortana is the IDE.** She can read your codebase, find bugs, and write the fixes herself.

### Features:
- **Hierarchical Memory:** Loads the Master Context on turn 1, with periodic reminders to prevent context rot.
- **Vision Interceptor:** Integrates Tesseract OCR to read terminal screenshots and error logs perfectly (no more hallucinating vision models).
- **Autonomous Hands:** The AI can run PowerShell commands locally to read, write, and fix code.
- **No IDE Required:** You don't need VS Code or Cline. The AI operates directly on your file system.
- **Bring Your Own Key (BYOK):** Uses your own DeepSeek API key. Cloud brains are commodity.

## Installation
1. Install Tesseract OCR and Python dependencies:
   `pip install pytesseract pillow pydantic urllib3`
2. Copy the contents of `kortana_memory_injector.py` into an Open WebUI Filter.
3. Copy the contents of `kortana_unified.py` into an Open WebUI Pipe.
4. Put your DeepSeek API key in the Pipe Valves.
5. Put your `master_context.txt` file in the same directory as your Open WebUI data.

## The Vision
We are building the Operating System that routes to open-source models. The cloud brains are a commodity. The architecture is the moat.