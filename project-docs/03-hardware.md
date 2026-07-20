# 03 — Hardware

## What the architecture demands

The embedded app runs the framework locally — Python, LangChain, STT, TTS on the device itself. That sets the floor: **a Linux-class computer**, not a microcontroller. This is a feature, not a limitation: it's exactly what keeps "hardware is completely up to the user" true — any machine that runs Linux and has a mic and a speaker is a valid body. No custom firmware, no special boards, no soldering required unless the user wants it.

## The hardware ladder

| Tier | Machine | ~Cost | What runs locally | Experience |
|---|---|---|---|---|
| Any computer | Old laptop / desktop you already own | $0 | Everything the machine can carry | The zero-cost entry; also your dev setup |
| Classic | Raspberry Pi 5 (8 GB) + mic + speaker | ~$120–160 | Wake word, Piper TTS, whisper small/Speech-level STT; LLM via API or a small local model (slow) | The iconic build; hybrid mode recommended |
| Sweet spot | Intel N100/N305 mini-PC (16–32 GB) | ~$180–280 | Comfortable full-local STT/TTS + 3–4B local LLM; great hybrid host | Recommended default in the docs |
| Flagship | Any PC + used GPU (RTX 3060 12 GB / 3090 24 GB) | ~$450–950 | GPU Whisper (sub-second), Kokoro TTS, 8–30B local models at 1–2 s | Fully local, no cloud at all |

Rules of thumb for the docs: VRAM is the binding constraint for local LLMs (≈4 GB → 3–4B models, 12 GB → 8–14B, 24 GB → 30B-class); CPU-only LLM inference is fine for testing and painful for daily voice; hybrid (local voice pipeline + API model) is the best experience per dollar and is a first-class mode, not a compromise.

One optional split for advanced users: the device can point its model profile at Ollama running on another machine in the house (the gaming PC). That's just a URL in the model config — no architecture change.

## Audio: the part that actually decides quality

Far-field voice is won or lost in the microphone, not the CPU.

**Microphone** — three good options, all USB (USB keeps it universal across every tier):
1. **ReSpeaker-class USB mic array (XMOS DSP)** — 4 mics, hardware acoustic echo cancellation, noise suppression, 360° pickup. Hardware AEC is what lets the assistant hear you *over its own music* — the hardest acoustic problem — so this is the recommended pick for the main room (~$60–80).
2. **ReSpeaker 2-mic class devices** — cheaper, fine for desk/bedroom distance (~$25).
3. **Any USB conference speakerphone** (e.g., used Jabra/Anker) — built-in AEC, mic and speaker in one box, often the best value on the used market.

**Speaker** — any powered speaker or the speakerphone above; 3.5 mm or USB. For the "premium toy" feel, a small full-range driver in a printed enclosure with an amp HAT is a lovely optional build, not a requirement.

## The trust build (reference design, optional but signature)

For users who share your point #2 — not trusting a firmware mute — the reference build guide includes a **hardware mic-kill switch**: a physical toggle wired in series with the USB mic's VBUS (power) line, in an inline pigtail or inside the printed enclosure. Switch open = the microphone has no power = electrically deaf, regardless of any software state. Add an LED across the mic's power side so "mic is powered" is reported by the circuit itself, not by code. The guide includes multimeter checkpoints and a tcpdump recipe (assistant traffic stays on LAN in offline mode) so the user can verify both promises themselves. Total parts: a toggle switch, an LED, a resistor, a sacrificial USB cable — under $10 and one evening.

## Reference build: **Sovereign One** (the documented premium toy)

The build guide the project ships, so "anyone can build it" has a concrete answer:

Pi 5 or N100 mini-PC as the brain; ReSpeaker-class USB array; small amp + full-range driver; the mic-kill switch mod; a 3D-printable enclosure (fabric grille, light pipe for a status LED, switch on the front where you can see it); flashable OS image or one-line install script. Publish STL/STEP files and invite enclosure remixes — case design is the easiest community contribution surface there is. The result should photograph like a product and assemble in an evening with zero or minimal soldering.

## Your personal dev bench

Phase 0–1: just your laptop (CLI chat, Ollama-on-CPU with a 3–4B model, API keys for cloud profiles). Phase 2: add a USB mic (even a cheap one) and any speaker — that's a complete voice dev rig; a used speakerphone (~$20–30) upgrades it nicely. Phase 4: one Pi 5 or N100 box to validate the reference build on real target hardware. Hard minimum to start today: **$0**.

## Out of scope

Custom PCBs, microcontroller satellites, manufacturing, certifications, selling kits. If multi-room becomes a demanded feature later, the honest v2 answer is running multiple devices (they're cheap at the N100/Pi tier) — not inventing a satellite protocol.
