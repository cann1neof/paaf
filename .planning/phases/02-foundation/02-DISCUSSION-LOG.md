# Phase 2: Foundation — Discussion Log

**Date:** 2026-07-25
_Human-reference only. Not consumed by downstream agents._

## Areas offered
Secret store mechanism · Scaffold scope · TTFA regression guard · App license (AGPL?)

User selected the first three to discuss; delegated the app-license call to Claude.

## Area 1 — Secret store (CORE-04)
- **Options presented:** encrypted file + pluggable interface (recommended) / OS keyring only / encrypted file only.
- **User answer:** "find an open source solution for storing secrets. It should be trustable."
- **Captured as:** D-01..D-04 — separate encrypted store, established/audited open-source crypto only (no hand-rolled), headless + offline-verifiable, behind a pluggable `SecretStore` interface. Concrete library selection handed to the researcher; leading candidates `age` and pyca `cryptography` Fernet.

## Area 2 — Scaffold scope (FOUND-01..04)
- **Options presented:** all 5 skeletons + 2 real (recommended) / only active packages / all 7 including apps.
- **User answer:** All 5 skeletons, 2 real.
- **Captured as:** D-05..D-07 — five framework packages as importable skeletons, real impl only in `paaf-core` + `paaf-trace`, apps not scaffolded.

## Area 3 — TTFA regression guard (TRACE-03/04)
- **Options presented:** accounting accuracy + overhead (recommended) / fixed budget / both.
- **User answer:** Both.
- **Captured as:** D-08..D-09 — fake TTS, assert both accounting accuracy+overhead and a fixed budget ceiling; budget is an overhead-regression guardrail, not a shipped-latency claim (Phase-1 evidence).

## Claude's discretion
- **App license:** leaned Apache-2.0 for the apps in v1; recorded AGPL as an open governance question in DECISIONS.md rather than deciding by default.

## Deferred
AGPL for apps · OS-keyring backend · app scaffolding · SOPS/secrets-in-git.
