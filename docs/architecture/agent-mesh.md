# Agent Mesh Architecture

PAAF features an LLM-driven agent mesh allowing specialized model profiles to delegate conversations seamlessly.

## Handoff Mechanism

- **Peer Graphs:** Profiles declare allowed target peers using the `peers` field in `paaf.yaml`.
- **Handoff Tools:** For each declared peer, PAAF exposes a `transfer_to_<peer>` tool dynamically to the active agent.
- **Hop Budgeting:** Configurable `hop_budget` prevents infinite handoff loops between models.
- **Trace Auditing:** Every handoff step is recorded into local SQLite trace logs without external data egress.
