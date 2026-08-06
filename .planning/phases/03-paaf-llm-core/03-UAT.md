---
status: testing
phase: 03-paaf-llm-core
source: [03-VERIFICATION.md]
started: 2026-08-06T17:10:00Z
updated: 2026-08-06T17:10:00Z
---

## Current Test

number: 1
name: Live Anthropic completion through an encrypted secret store
expected: |
  A genuine completion comes back from api.anthropic.com and is printed as
  `<profile>> <reply>`.
awaiting: user response

## Tests

### 1. Live Anthropic completion through an encrypted secret store

expected: With a real `ANTHROPIC_API_KEY` stored in an encrypted `paaf_core` secret store under the name a profile's `api_key_ref` declares, run `paaf chat --config <yaml> --secrets <store>` against a live Anthropic profile and hold one turn. A genuine completion comes back from api.anthropic.com and is printed as `<profile>> <reply>`.
why_human: Requires a real, billable API key. The verifier proved the whole path up to the wire — the key resolves out of a real encrypted store, the Anthropic profile BINDS with it, and it dials a real socket (an Anthropic profile pointed at a dead local port produced a real `ConnectionFailed` and hopped) — but a successful Anthropic completion cannot be produced without a credential.
result: [pending]

### 2. Physical WAN cut mid-conversation

expected: With a real cloud profile as `active_profile` and a real local Ollama profile in `fallback_chain`, start `paaf chat`, send one turn successfully, then physically disconnect the WAN and send a second turn. The second turn prints `↳ fell back to <local> (connection)`, is answered by the local model, and that reply shows it received the first turn's history.
why_human: Cutting a real WAN link is a physical state change no automated check in this repo can produce. The verifier reproduced the equivalent live — an unreachable active profile produced a real ConnectionFailed, the loop hopped to a real local Ollama server, and turn 2's answer recalled turn 1's content — so what is left is confirmation that a WAN cut is indistinguishable from an unreachable endpoint.
result: [pending]

### 3. Cold-start 14B model does not trip the first-token budget

expected: Cold-start a 14B Ollama model and send the first turn of a session. No spurious `slow_first_token` fallback inside the configured `first_token_budget_s` — `Agent.warmup()` / `LangChainAdapter.preload()` absorbs the cold-load cost.
why_human: 03-VALIDATION.md Manual-Only row. Timing against a real cold-loading model cannot be asserted deterministically offline, and the verifier's local model is small and already warm.
result: [pending]

### 4. Two Ollama profiles on two different physical LAN machines

expected: Point two Ollama profiles at two DIFFERENT physical LAN machines and confirm each answers from its own box. `ollama ps` on each machine (or distinct model names) confirms which server ran.
why_human: The verifier has one Ollama server. Distinctness was proven live at the endpoint level — two same-provider profiles at 127.0.0.1:11435 (dead) and 127.0.0.1:11434 (live) did NOT share a binding: the dead one produced a real connection failure rather than being answered by the live one's client. Two physical boxes is the remaining confirmation.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
