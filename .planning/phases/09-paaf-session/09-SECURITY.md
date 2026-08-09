---
phase: 09
slug: paaf-session
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-09
---

# Phase 09 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Audio Source -> Session | Mic input must be sanitized/bounded to prevent DoS via infinite capture |
| Voice input -> Memory | Prevent untrusted partial input during barge-in from corrupting conversation state |
| Behaviors -> System | Ensure behavior configuration cannot execute arbitrary code |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-09-01 | Denial of Service | orchestrator | medium | accept | Enforce absolute timeout boundaries on capture and TTS synthesis | closed |
| T-09-02 | Information Disclosure | memory | low | accept | Truncation might discard part of AI response, but safe | closed |
| T-09-03 | Tampering | behaviors | low | accept | Behavior table is loaded from trusted config YAML, no dynamic exec | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-09-01 | T-09-01 | User accepted open threat instead of verifying mitigation | USER | 2026-08-09 |
| R-09-02 | T-09-02 | Truncation might discard part of AI response, but safe | USER | 2026-08-09 |
| R-09-03 | T-09-03 | Behavior table is loaded from trusted config YAML, no dynamic exec | USER | 2026-08-09 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-09 | 3 | 3 | 0 | gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-09
