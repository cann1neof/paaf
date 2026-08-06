# SPDX-License-Identifier: Apache-2.0
"""MESH-01/02: build the handoff surface, and validate whatever the model calls.

This module makes exactly one thing mechanical: **only a declared peer is
reachable**, and it enforces that twice, deliberately (Pattern 2).

* :func:`handoff_tools` shapes the surface — one ``transfer_to_<peer>`` tool per
  name in the awake agent's ``peers``, and nothing else. A target that is not a
  peer is not *offerable*. This is capability removal, the mesh's house style:
  the model is not instructed to behave, it is handed a smaller set of moves.
* :func:`resolve_handoff` checks the answer anyway, against ``awake.peers`` and
  never against ``LlmConfig.profiles``. A target that merely EXISTS is not a
  target this agent may reach. The second check is not belt-and-braces caution —
  models routinely emit tool names that were never bound, so a design resting on
  the surface alone would make MESH-02's "rejected, never silently followed"
  contingent on the provider behaving (Pitfall 4).

The guard is the one mesh guarantee that holds in every configuration, observed
or not (D-13): the observer can be absent, unreachable, or ungranted, and this
still refuses.

**No routing rule lives here, and none can.** PAAF never picks a target. It
offers the choice, in the user's declared order, described in the user's own
free text — and then validates. There is no keyword matching, no capability
scoring, and no config key that could express one (MESH-01).

The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the half of the mesh that decides what is reachable cannot
depend on anything swappable (SC#5).
"""

from __future__ import annotations

#: The prefix every handoff tool's name carries. Three independent
#: implementations converged on this exact spelling — the OpenAI Agents SDK
#: (``transfer_to_<agent_name>``, its documented default) and ``langgraph-swarm``
#: (``create_handoff_tool`` produces the same) — which is the strongest available
#: evidence that D-01's tool-call signal is the right shape.
#:
#: The target lives in the tool NAME, never in arguments. That is why every
#: handoff tool takes no parameters at all: there is no argument for a model to
#: hallucinate, mistype, or smuggle something into, and the set of names it was
#: offered IS the set of moves available.
HANDOFF_TOOL_PREFIX = "transfer_to_"

#: How many handoffs one user turn may make before the engine stops offering the
#: tools (T-04-04). Three is the smallest value that leaves headroom above the
#: legitimate A→B→A hand-back, which is two hops.
#:
#: Enforced from this plan onward so that no unbounded hop loop ships even for a
#: single wave — every hop is a full model round-trip on the latency path
#: (Pitfall 6), so "we will bound it next plan" is a real cost, not a formality.
#: Plan 04-03 makes it user-configurable (with this value as the floor) and adds
#: the withdrawal-at-the-wall and exhaustion paths.
DEFAULT_HOP_BUDGET = 3
