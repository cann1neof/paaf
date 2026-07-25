---
phase: 02-foundation
plan: 06
subsystem: core
tags: [core-05, offline, network, endpoint, lan-classification, ipaddress, protocol, registry, tdd]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "paaf-core package (src/ layout, hatchling), --disable-socket test default (02-01)"
provides:
  - "paaf_core.net.Endpoint — frozen dataclass (host/port/scheme) with offline is_lan()"
  - "paaf_core.net.NetworkComponent — runtime_checkable Protocol (declare_endpoints)"
  - "paaf_core.net.EndpointRegistry — aggregates declarations, non_lan_endpoints() isolates the APP-08 refusal set"
  - "LAN classification (loopback / RFC1918 / link-local / .local / localhost) via stdlib ipaddress + suffix, no DNS"
affects: [09-* APP-08 offline-enforcement daemon]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "classify network locality with stdlib ipaddress (is_loopback/is_private/is_link_local), never a socket"
    - "hostname LAN check is a lexical suffix match (.local) + localhost — no name resolution (offline-safe)"
    - "runtime_checkable Protocol as the component-facing declaration interface (matches SecretStore pattern)"
    - "submodule net/__init__.py re-exports; top-level paaf_core/__init__.py untouched"

key-files:
  created:
    - packages/paaf-core/src/paaf_core/net/__init__.py
    - packages/paaf-core/src/paaf_core/net/endpoint.py
    - packages/paaf-core/tests/test_endpoint_declaration.py
  modified: []

key-decisions:
  - "is_lan() uses ipaddress is_loopback OR is_private OR is_link_local — one numeric predicate covers loopback, RFC1918, and link-local for both IPv4 and IPv6"
  - "hostname LAN set = trailing .local suffix + exact localhost; everything else non-LAN (a public hostname is never LAN without resolution, which we refuse to do)"
  - "added localhost as a LAN hostname beyond the plan's .local requirement — correctness (Rule 2): localhost is provably loopback but is a name, not a numeric address"

requirements-completed: [CORE-05]

coverage:
  - id: D1
    description: "loopback, RFC1918, and .local endpoints each classify LAN"
    requirement: "CORE-05"
    verification:
      - kind: unit
        ref: "test_lan_hosts_classify_lan (parametrized: 127.0.0.1, ::1, 10/8, 172.16/12, 192.168/16, 169.254, fe80::, device.local, MyBox.LOCAL)"
        status: pass
    human_judgment: false
  - id: D2
    description: "public endpoint (api.openai.com:443) classifies non-LAN and appears in non_lan_endpoints() — the negative control APP-08 will refuse"
    requirement: "CORE-05"
    verification:
      - kind: unit
        ref: "test_public_hosts_classify_non_lan + test_non_lan_endpoints_returns_only_public"
        status: pass
    human_judgment: false
  - id: D3
    description: "classification performs no DNS lookup — passes under --disable-socket"
    requirement: "CORE-05"
    verification:
      - kind: unit
        ref: "uv run pytest packages/paaf-core/tests/test_endpoint_declaration.py -q --disable-socket => 19 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "registry aggregates endpoints from two NetworkComponent implementations"
    requirement: "CORE-05"
    verification:
      - kind: unit
        ref: "test_all_endpoints_aggregates_two_components + test_fake_component_satisfies_protocol"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 06: Network-Endpoint Declaration Interface Summary

**A single `NetworkComponent` interface in paaf-core through which every network-touching component declares its endpoints, an `Endpoint` that classifies itself LAN vs non-LAN offline (stdlib `ipaddress` + `.local` suffix, zero DNS), and an `EndpointRegistry` whose `non_lan_endpoints()` is exactly the set Phase-9's APP-08 daemon will refuse — the architectural basis for offline enforcement, not scattered `if offline:` checks.**

## Performance
- **Duration:** ~8 min
- **Completed:** 2026-07-25
- **Tasks:** 1 (TDD)
- **Files created:** 3 (0 modified)

## Accomplishments
- `Endpoint(host, port, scheme)` is a frozen dataclass; `is_lan()` returns True for IP loopback (127.0.0.0/8, `::1`), RFC1918 / private ranges, link-local (169.254/16, `fe80::/10`), and the `localhost` / `.local` hostnames — and False for every public address or resolvable public hostname (the `api.openai.com:443` negative control).
- Classification uses stdlib `ipaddress` for numeric addresses and a lexical suffix check for hostnames; it opens no socket and resolves no name, so the whole test module passes under the suite-wide `--disable-socket` default (threat T-02-16 enforced mechanically).
- `NetworkComponent` is a `runtime_checkable` Protocol exposing one method (`declare_endpoints`), matching the established `SecretStore` interface pattern; `EndpointRegistry` aggregates declarations in registration order and `non_lan_endpoints()` isolates precisely the set APP-08 will refuse.
- The interface lives in `paaf-core` and imports nothing from `paaf-llm`/`paaf-voice`, keeping it FOUND-04-safe; it is exported from `net/__init__.py` without touching the top-level `paaf_core/__init__.py`.

## Task Commits

TDD cycle (RED → GREEN, no refactor needed):

1. **RED — failing tests** (test) - `93bd831`
2. **GREEN — interface + classification + registry** (feat) - `826f4d6`

## Files Created
- `packages/paaf-core/src/paaf_core/net/endpoint.py` - `Endpoint` frozen dataclass with offline `is_lan()`, `NetworkComponent` Protocol, `EndpointRegistry`.
- `packages/paaf-core/src/paaf_core/net/__init__.py` - submodule re-exports (`Endpoint`, `EndpointRegistry`, `NetworkComponent`).
- `packages/paaf-core/tests/test_endpoint_declaration.py` - 19 tests: parametrized LAN/non-LAN classification, frozen-instance guard, and registry aggregation over two fake components.

## Decisions Made
- **One numeric predicate for locality** — `is_loopback or is_private or is_link_local` on the parsed `ipaddress` object covers loopback, RFC1918, and link-local for both IPv4 and IPv6 without hand-coding CIDR blocks.
- **Hostnames are LAN only by lexical rule** — a trailing `.local` (case-insensitive) or exact `localhost`. A public hostname is never treated as LAN because confirming it would require DNS, which the offline-safety contract forbids.
- **Added `localhost` beyond the plan's `.local` requirement** — see Deviations (Rule 2 correctness).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing correctness] Classify bare `localhost` as LAN**
- **Found during:** Task 1 (implementation)
- **Issue:** The plan specified `.local` suffix + numeric ranges, but `localhost` is a bare hostname (not numeric, no `.local` suffix) that is provably loopback. Omitting it would misclassify the single most common LAN service address as non-LAN, which APP-08 would then wrongly refuse.
- **Fix:** Added an exact-match `localhost` set alongside the `.local` suffix check. Still no DNS — it is a lexical constant.
- **Files modified:** `packages/paaf-core/src/paaf_core/net/endpoint.py`
- **Commit:** `826f4d6`

**Total deviations:** 1 auto-fixed (Rule 2). No architectural or scope changes; no new dependencies.

## TDD Gate Compliance
- RED gate: `test(02-06)` commit `93bd831` present; tests failed with `ModuleNotFoundError: paaf_core.net` before implementation (no premature-pass).
- GREEN gate: `feat(02-06)` commit `826f4d6` present after RED; 19/19 tests pass.

## Issues Encountered
None. Ruff auto-fixed import ordering and `__all__` sorting during verification; the blind-`Exception` assert was tightened to `FrozenInstanceError`.

## User Setup Required
None.

## Next Phase Readiness
- Phase 9's APP-08 daemon can register every `NetworkComponent` and gate startup on `EndpointRegistry.non_lan_endpoints()` being empty under offline mode — no per-component offline logic required.
- The classification is DNS-free, so APP-08 enforcement remains valid under `--disable-socket` and in a genuinely offline runtime.

## Self-Check: PASSED
- All 3 created files verified present on disk.
- Both task commits (`93bd831`, `826f4d6`) verified in git log.
- `uv run pytest packages/paaf-core/tests/test_endpoint_declaration.py -q --disable-socket` => 19 passed; full suite 56 passed; ruff + mypy clean.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
