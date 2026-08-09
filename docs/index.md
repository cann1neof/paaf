# Welcome to PAAF

**PAAF (Personalized Agentic Assistant Framework)** is a local-first, privacy-preserving framework where **the user owns the mind**.

## Core Philosophy

1. **User Owns the Mind:** System prompts, model profiles, peer routing rules, and voice engines are defined transparently in `paaf.yaml`.
2. **Nothing Hidden:** Every system prompt and handoff instruction can be byte-exact inspected via `paaf prompt`. Zero background auto-downloads (`PRIV-06`).
3. **In-Process & Modular Skills:** Extend assistant capabilities cleanly via versioned skills, MCP server integrations, and pluggable STT/TTS voice engines.
4. **Zero-Code Engine Swapping:** Seamlessly switch between STT engines (`faster-whisper` for Mac/CUDA vs `whisper.cpp` for Raspberry Pi) and TTS engines with zero code changes.
