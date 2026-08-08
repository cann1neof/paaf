# SPDX-License-Identifier: Apache-2.0
"""SC#5 / PERS-04/05: the surface where the user reads what their model is told.

This module is deliberately the thinnest file in the package (D-01). Every
correctness claim it makes is one the library already proves against the shipped
fake — the turn loop, the ordered fallback, the composed prompt. The CLI wires
those together and renders them; it holds no logic the library lacks, because a
CLI that owned any of it would be a second implementation nobody tests.

**The one thing this file exists to guarantee (D-02).** ``paaf prompt`` and
``paaf chat --show-prompt`` print the prompt by asking the SAME
:class:`~paaf_llm.compose.PromptComposer` the agent asks — ``--show-prompt``
literally calls :meth:`~paaf_llm.agent.Agent.system_prompt`, and ``paaf prompt``
calls ``compose`` with the same base prompt and the same fragments
:func:`build_agent` hands the agent. Nothing here re-assembles a prompt string.
A second derivation is the only way an inspector can quietly understate what was
sent (T-03-17/T-03-18), so there is not one.

``paaf prompt`` writes the composed prompt to stdout and **nothing else — not
even a trailing newline**. ``paaf prompt --config x.yaml > sent.txt`` therefore
yields the exact bytes the model receives, and ``diff`` against a captured prompt
is meaningful. That is PERS-04 as a byte-level property rather than a claim.

**The provenance view is opt-in and never authoritative (D-03).** The default
output is the raw prompt. ``--provenance`` re-renders the SAME segments with
``base`` / ``skill:<name>`` labels; the labels are an audit aid laid *around* the
content, never a filter over it.

**Framework-uninstalled by construction (SC#1).** Nothing at module scope imports
:mod:`paaf_llm._engine`. The real adapter is built inside :func:`_default_adapter`
and only when a turn is actually about to run, so ``import paaf_llm.cli`` — and
the whole test suite that injects the fake through :func:`build_agent` — works
with the agent framework absent.

**The trace is opt-in, and PAAF names no file on the user's behalf.**
``paaf chat --trace-db <path>`` records each turn into the SQLite store
(``served_by``, the composed prompt, and every fallback hop — SC#4 / D-06).
Without the flag no store is constructed and nothing is written: a CLI that
created a database at an invented path would be writing files nobody asked for,
and filesystem conventions for the daemon belong to Phase 9 (APP-*), not here.

**Config text is never interpreted.** The :class:`rich.console.Console` is built
with ``markup=False, highlight=False``, so a profile whose ``capabilities`` string
contains ``[/]`` cannot restyle, hide, or truncate the surrounding output. The
byte-exact prompt path skips rich entirely and uses :func:`click.echo`.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import click
import yaml
from paaf_core.secrets import EncryptedFileSecretStore, InvalidPassphraseError
from paaf_trace.store import TraceStore
from pydantic import ValidationError
from rich.console import Console

from . import mesh
from .agent import Agent
from .compose import PromptComposer
from .observer import UNOBSERVED_NOTICE
from .ports import AdapterError, AllProvidersFailed, EngineError, UndeclaredPeer
from .profiles import LlmConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .agent import SecretResolver, TraceSink
    from .ports import ChatAdapter
    from .profiles import ModelProfile

#: The per-hop fallback notice (D-06). Brief on purpose: "nothing hidden" is one
#: line per hop naming where the turn went and why, not a stack trace.
FALLBACK_NOTICE = "↳ fell back to {to} ({reason})"

#: Printed for a hop whose degraded profile was LAST in the chain, where the
#: engine records an empty target. Inventing a profile name would misreport it.
NO_FALLBACK_TARGET = "(nowhere — end of chain)"

#: The ``--provenance`` segment label (D-03). Exported so the test that
#: reconstructs the raw prompt from the labeled view parses the format this
#: module actually emits instead of a copy of it.
PROVENANCE_LABEL = "--- {source} ---"

#: Printed when ``--agent`` names a profile that was never declared (T-04-23).
#: The value is untrusted CLI input that would otherwise index
#: ``config.profiles``, so it is validated and REPORTED — naming what was asked
#: for and what exists instead, because a bare "unknown agent" sends the user
#: back to their own YAML to find out what they were allowed to type.
UNKNOWN_AGENT = (
    "--agent {name!r} is not a declared profile. The profiles in this config "
    "are: {declared}."
)

#: Stated wherever the peer graph is shown. Through Phase 3 this said the graph
#: was inert; as of Phase 4 (MESH-01/02) it is live, and the honest description
#: of what "live" means here is the interesting part: PAAF offers the choice and
#: refuses an undeclared answer, and it never picks a target. The user reading
#: their own peer graph should know both halves.
MESH_LIVE_NOTE = (
    "The peer graph is live: the awake model is offered one handoff tool per "
    "declared peer and chooses for itself. PAAF never picks the target, and a "
    "target outside the declared peers is refused rather than followed."
)

#: The two mesh-level facts a user needs to reason about a whole turn (D-08/D-09)
#: — how many handoffs one turn may make, and who speaks when they run out. Shown
#: with the peer graph because a graph without them does not predict a turn.
MESH_LIMITS = "mesh — hop budget: {budget} handoff(s) per turn, home agent: {home}"

#: Printed for `default_agent` when the user declared none. Spelled out rather
#: than left blank: with no home agent the currently-awake agent answers with the
#: handoff tools withdrawn (OQ-2), and a blank would read as a missing value
#: rather than as a deliberate absence.
NO_HOME_AGENT = "(none declared — whoever is awake answers)"

#: Printed when a model names a handoff target its agent was never given. The
#: detail is ``UndeclaredPeer``'s own message, which already names the attempted
#: target AND the declared peers — the two things a user needs to decide whether
#: to fix the config or the prompt.
UNDECLARED_PEER_NOTICE = (
    "the model attempted a handoff PAAF refused: {detail}. Nothing was "
    "re-routed and no fallback was tried — this is a routing violation, not a "
    "provider having a bad minute."
)

#: Printed when a profile cannot be USED as configured — a credential that will
#: not resolve, a model the provider does not have. One line, because the detail
#: is already the adapter's own scrubbed message (T-03-04) and the CLI holds no
#: logic the library lacks (D-01). This is emphatically not a fallback notice:
#: chain exhaustion keeps its own wording, since a config error is not a
#: degraded provider and saying so would be the confident wrong explanation.
CONFIG_FAILURE_NOTICE = "paaf could not use the model you configured: {detail}"

#: Printed when a provider dies AFTER it has begun replying. ``{reason}`` is
#: formatted from ``AdapterError.reason.value`` — the same ``FallbackReason`` the
#: trace records (D-06) — never from the exception's class name, so the terminal
#: message and the trace row cannot disagree about why the turn ended. The notice
#: says out loud that no re-route was attempted, because silence there would read
#: as the fallback chain having failed to do its job rather than having
#: deliberately declined to swap models mid-sentence.
MID_REPLY_FAILURE_NOTICE = (
    "the model failed after it had begun replying ({reason}); the chain does not "
    "re-route once a reply has started: {detail}"
)

#: The environment variable the store passphrase is read from. Deliberately NOT
#: a command-line option (T-03-32): a passphrase on ``argv`` is visible in ``ps``
#: to every other user on the box and lands in shell history. A module constant
#: for the same reason every other user-facing string here is one — the tests
#: assert against the name the CLI actually reads, not a copy of it.
SECRET_PASSPHRASE_ENV = "PAAF_SECRET_PASSPHRASE"

#: Printed when a profile names a key but no store was named to find it in.
#: Lists the offending profiles, because "some profile needs a secret" sends the
#: user hunting through their own YAML for something the CLI already knows.
SECRETS_PATH_REQUIRED = (
    "these profiles declare an api_key_ref: {profiles}. The key value is never "
    "read from YAML, so name the encrypted store holding it with --secrets, and "
    "supply that store's passphrase in the {env} environment variable."
)

#: Printed when the store was named but no passphrase reached us and stdin is a
#: pipe rather than a terminal. Says which of the two it is, because "supply a
#: passphrase" is not actionable when the obvious way to supply one — typing it
#: — is exactly what a non-interactive session cannot do.
PASSPHRASE_REQUIRED = (
    "the secret store cannot be unlocked: no passphrase was supplied and stdin "
    "is not a terminal, so there is nothing to prompt. Set the passphrase in the "
    "{env} environment variable."
)

#: Printed when the store exists but will not open. Interpolates the PATH and
#: NOTHING ELSE (T-03-33). Echoing the supplied passphrase back is the obvious
#: "helpful" thing to do here and the one thing that must never happen: this
#: string reaches terminals, scrollback, logs, and pasted bug reports.
SECRET_STORE_LOCKED = (
    "the secret store at {path} could not be unlocked with the supplied "
    "passphrase. Check the passphrase, and that this is the right store file."
)


def _config_failure(exc: Exception) -> click.ClickException:
    """Wrap a configuration failure as the one-line error the user reads.

    One helper for both reachable sites — a profile that fails at bind time and
    one that fails when the factory validates the provider table — so the two
    surfaces cannot drift into two different wordings for the same problem.

    The text lives in :data:`CONFIG_FAILURE_NOTICE` rather than inline, following
    this module's convention for every user-facing string: a test then asserts
    against the notice the CLI actually emits instead of against a copy of it.
    """
    return click.ClickException(CONFIG_FAILURE_NOTICE.format(detail=exc))


def load_llm_config(path: str) -> LlmConfig:
    """Read the YAML at ``path`` and validate it through :class:`LlmConfig`.

    ``safe_load`` rather than ``load``: a config file is hand-edited, untrusted
    input, and the full loader can construct arbitrary Python objects from it.
    Validation itself belongs to the schema (CORE-01) — the CLI parses no fields
    and knows no defaults, so a schema change cannot leave this file stale.
    """
    with open(path, "rb") as handle:
        parsed = yaml.safe_load(handle)
    try:
        return LlmConfig.model_validate({} if parsed is None else parsed)
    except ValidationError as exc:
        raise click.ClickException(
            f"{path} is not a valid PAAF LLM config:\n{exc}"
        ) from exc


def load_skill_fragments(config: LlmConfig) -> list[tuple[str, str]]:
    """Return the ordered ``(skill_name, fragment_text)`` pairs for ``config``.

    The D-09 stub source, and deliberately a *named seam* rather than an inline
    ``[]``: it is the ONE place both the agent and the prompt inspector read
    their fragments from, so the two cannot drift apart when Phase 6 replaces
    this body with real skill discovery (PERS-02).
    """
    return []


def profiles_needing_secrets(config: LlmConfig) -> list[str]:
    """Return the sorted names of profiles that declare an ``api_key_ref``.

    The ONE place that decides whether this config needs a secret store at all,
    so the decision cannot be made twice with two different answers — the guard
    that refuses to unlock a store nobody asked for and the guard that demands
    ``--secrets`` are the same question, and they read it here.

    ``api_key_ref`` holds the NAME of a ``paaf_core`` SecretStore key (CORE-04),
    never the value, so a profile declaring one is exactly a profile whose
    credential lives outside the YAML and must be fetched from somewhere.
    """
    return sorted(
        name for name, profile in config.profiles.items() if profile.api_key_ref
    )


def open_secret_store(
    config: LlmConfig, secrets_path: str | None, passphrase: str | None
) -> SecretResolver | None:
    """Return an unlocked store for ``config``, or ``None`` if it needs none.

    **The early return is the load-bearing line** (T-03-34). A config in which no
    profile names an ``api_key_ref`` returns ``None`` before the filesystem is
    touched and before a passphrase is even looked for: an all-local setup must
    never be asked to unlock anything, and a store built "just in case" would be
    a credential prompt the user's config never justified.

    Only past that point do the three failure branches apply. They live here
    rather than at the store constructor because ``Path(None)`` and
    ``None.encode`` are tracebacks, and a traceback on the headline command is
    the failure mode this CLI's error handling exists to eliminate.

    **The prompt is gated on a TTY, and that gate is load-bearing** (T-03-35).
    ``paaf chat`` reads the conversation from stdin, so prompting on a pipe would
    silently swallow the user's first message and feed it to the KDF — producing
    a wrong-passphrase error about a line they meant as a question.
    """
    needed = profiles_needing_secrets(config)
    if not needed:
        return None

    if secrets_path is None:
        raise click.ClickException(
            SECRETS_PATH_REQUIRED.format(
                profiles=", ".join(needed), env=SECRET_PASSPHRASE_ENV
            )
        )

    if not passphrase:
        if click.get_text_stream("stdin").isatty():
            passphrase = click.prompt(
                "Passphrase for the secret store", hide_input=True
            )
        else:
            raise click.ClickException(
                PASSPHRASE_REQUIRED.format(env=SECRET_PASSPHRASE_ENV)
            )

    try:
        return EncryptedFileSecretStore(secrets_path, passphrase)
    except InvalidPassphraseError as exc:
        # The path, never the passphrase and never a stored value (T-03-33).
        raise click.ClickException(
            SECRET_STORE_LOCKED.format(path=secrets_path)
        ) from exc


def _default_adapter(
    config: LlmConfig, secret_store: SecretResolver | None = None
) -> ChatAdapter:
    """Build the real framework-backed adapter, importing it only now (SC#1).

    The import lives inside this function on purpose. At module scope it would
    make the agent framework a hard dependency of ``import paaf_llm.cli`` and
    break the promise that ``pip install paaf-llm`` (no ``[engine]`` extra) runs
    the whole fake-adapter suite standalone.

    This is also where the suite injects the shipped fake: a test that monkey-
    patches this function drives the real ``chat`` command end to end without a
    provider, which is the only honest way to test the command path itself
    rather than a hand-assembled stand-in for it.
    """
    try:
        # Lazy by design — see the docstring. Not a module-scope import.
        from ._engine import build_engine_adapter
    except ImportError as exc:
        raise click.ClickException(
            "Talking to a real model needs the optional engine extra, which is "
            "not installed (or not built yet in this checkout). Install it with:"
            "\n\n    pip install 'paaf-llm[engine]'\n\n"
            "Everything that does not call a model — `paaf prompt`, "
            "`paaf profiles` — works without it."
        ) from exc
    return build_engine_adapter(config, secret_store=secret_store)


def build_agent(
    config: LlmConfig,
    adapter: ChatAdapter | None = None,
    *,
    skill_fragments: Sequence[tuple[str, str]] | None = None,
    trace: TraceSink | None = None,
    secret_store: SecretResolver | None = None,
) -> Agent:
    """Return the :class:`Agent` this CLI drives, optionally with an injected adapter.

    ``adapter`` is the test seam: passing one keeps the whole command path
    framework-uninstalled, which is how ``tests/test_inspector.py`` exercises
    ``chat`` without a provider. Passing ``None`` builds the real adapter, and
    only then.

    ``secret_store`` goes to the ADAPTER FACTORY and nowhere else. ``Agent`` has
    a ``secret_store`` parameter of its own, and it stays unused on purpose —
    its docstring says key resolution belongs to the real adapter rather than to
    the turn loop, and passing the store in both places would imply a second
    consumer that does not exist.

    Fragments default to :func:`load_skill_fragments`, the same call
    :func:`prompt` makes — that shared default is what makes the inspector's
    output byte-identical to the agent's system message rather than merely
    similar to it (D-02).
    """
    fragments = list(
        load_skill_fragments(config) if skill_fragments is None else skill_fragments
    )
    return Agent.build(
        config,
        adapter if adapter is not None else _default_adapter(config, secret_store),
        trace=trace,
        skill_fragments=fragments,
    )


def render_profiles(config: LlmConfig, console: Console) -> None:
    """Print the mesh as configured: manifests, peers, and the turn's two limits.

    What each model says it handles (free text, by D-08/D-12 — there is no
    routing DSL to display), which peers it may hand off to, and the two
    mesh-level facts that decide how a whole turn can unfold: the hop budget
    (D-08) and the home agent (D-09). A peer graph shown without those two does
    not let a user predict a turn — it says where the conversation *could* go and
    nothing about when it must stop or who ends it.

    :data:`MESH_LIVE_NOTE` states plainly that the graph now routes, and states
    the limit on that too: the model chooses, PAAF does not. Through Phase 3 this
    line said the opposite, and leaving it saying so would have been the more
    misleading of the two errors.

    Everything goes through the caller's :func:`_make_console`
    (``markup=False, highlight=False``), so a manifest containing rich markup
    cannot restyle or swallow the lines around it (T-04-14).
    """
    console.print("profiles — capability manifest and peer graph", style="bold")
    for name, profile in config.profiles.items():
        roles = []
        if name == config.active_profile:
            roles.append("active")
        if name in config.fallback_chain:
            roles.append(f"fallback #{config.fallback_chain.index(name) + 1}")
        suffix = f"  [{', '.join(roles)}]" if roles else ""
        console.print(f"  {name} ({profile.provider}:{profile.model}){suffix}")
        console.print(f"    capabilities: {profile.capabilities or '(none declared)'}")
        console.print(f"    peers: {', '.join(profile.peers) or '(none)'}")
        if profile.constraints:
            console.print(f"    constraints: {'; '.join(profile.constraints)}")
    console.print(
        MESH_LIMITS.format(
            budget=config.hop_budget,
            home=config.default_agent or NO_HOME_AGENT,
        )
    )
    console.print(MESH_LIVE_NOTE, style="dim")
    if mesh.OBSERVER_PROFILE_NAME not in config.profiles:
        console.print(UNOBSERVED_NOTICE, style="yellow")


def _make_console() -> Console:
    """A console that renders text as text.

    ``markup=False`` and ``highlight=False`` are the load-bearing arguments:
    profile names, capability manifests, and model replies all reach this console,
    and rich's markup would let any of them restyle or swallow the output around
    them. ``soft_wrap=True`` keeps long lines intact so what is printed is what
    was produced.
    """
    return Console(markup=False, highlight=False, soft_wrap=True)


def _print_fallback_trail(
    trail: Sequence[tuple[str, str, str]], console: Console
) -> None:
    """Print one brief notice per hop the turn took (D-06)."""
    for _frm, to, reason in trail:
        console.print(
            FALLBACK_NOTICE.format(to=to or NO_FALLBACK_TARGET, reason=reason),
            style="yellow",
        )


async def _chat_loop(agent: Agent, *, show_prompt: bool, console: Console) -> None:
    """Read a line, serve a turn, print the reply — until stdin ends.

    ``warmup`` runs first because the per-turn first-token deadline is meant to
    measure a *warm* model: charging a cold local model's load time against it
    would make the very first turn of every session look degraded.
    """
    await agent.warmup()
    stdin = click.get_text_stream("stdin")
    interactive = stdin.isatty()

    while True:
        if interactive:
            click.echo("you> ", nl=False)
        line = stdin.readline()
        if not line:  # EOF
            break
        user_text = line.strip()
        if not user_text:
            continue

        if show_prompt:
            # The agent's OWN derivation, not a reconstruction of it (D-02).
            click.echo(agent.system_prompt())

        try:
            result = await agent.turn(user_text)
        except UndeclaredPeer as exc:
            # A ROUTING violation, and the taxonomy is what makes this its own
            # clause. `UndeclaredPeer` is a sibling of `AllProvidersFailed` and
            # `EngineError` and subclasses neither `AdapterError` nor
            # `EngineError`, so nothing below can shadow it: filing it under
            # `AdapterError` would let the fallback loop absorb it and print
            # `↳ fell back to cloud (connection)` at a mis-route, and filing it
            # under `EngineError` would blame the user's YAML when `_check_refs`
            # already proved the peer graph integral.
            #
            # Surfacing it here as a plain ClickException — one line, no
            # traceback — is what makes MESH-02's "a catchable error rather than
            # silently followed" true for the USER and not only for the library.
            # The library refusing where nobody can see it is half a guarantee.
            raise click.ClickException(
                UNDECLARED_PEER_NOTICE.format(detail=exc)
            ) from exc
        except AllProvidersFailed as exc:
            # Chain exhaustion already reads well and names every hop, so it
            # keeps its own wording — prefixing it with the config notice would
            # blame the user's YAML for a run of unreachable providers.
            raise click.ClickException(str(exc)) from exc
        except EngineError as exc:
            raise _config_failure(exc) from exc
        except AdapterError as exc:
            # Reaching here means the turn loop had already COMMITTED to a
            # profile: a pre-commit AdapterError is caught inside
            # agent._run_chain and becomes a fallback hop, never an error. This
            # clause therefore does not duplicate the fallback loop — it covers
            # the case the loop declines on purpose, once a reply is underway.
            raise click.ClickException(
                MID_REPLY_FAILURE_NOTICE.format(reason=exc.reason.value, detail=exc)
            ) from exc

        _print_fallback_trail(result.fallback_trail, console)
        console.print(f"{result.served_by}> {result.text}")


async def _chat_session(
    config: LlmConfig,
    *,
    show_prompt: bool,
    console: Console,
    secret_store: SecretResolver | None,
    trace_db_path: str | None,
) -> None:
    """Own the trace store's lifecycle around one ``paaf chat`` conversation.

    **Why this coroutine exists at all.** :class:`~paaf_trace.store.TraceStore`
    owns a writer task and a bounded ``asyncio.Queue``, and both belong to the
    running loop — a store constructed before :func:`asyncio.run` would bind its
    queue to a loop that never runs it. The agent is handed that store as its
    sink, so the agent has to be built in here too. That is the whole reason
    ``build_agent`` moved out of the :func:`chat` command body: not a new
    parameter, a new place to stand.

    ``stop()`` is awaited in a ``finally`` and that placement is load-bearing. It
    is what joins the queue, so every event already emitted is written AND
    committed before the process leaves. Stopping only on the happy path would
    discard exactly the rows a session that ended badly most needs to have kept.

    ``trace_db_path`` is ``None`` unless the user named a file. Nothing is
    constructed and nothing is written in that case — PAAF does not create a
    database at a path nobody asked for.
    """
    store = TraceStore(trace_db_path) if trace_db_path is not None else None
    if store is not None:
        # Returns once the schema is applied, so the sink is usable immediately.
        await store.start()
    try:
        # The second reachable config-failure site: the factory validates every
        # declared profile's provider before a single turn runs, so a config
        # error can land here rather than mid-conversation.
        try:
            agent = build_agent(config, secret_store=secret_store, trace=store)
        except EngineError as exc:
            raise _config_failure(exc) from exc
        await _chat_loop(agent, show_prompt=show_prompt, console=console)
    finally:
        if store is not None:
            await store.stop()


_config_option = click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the YAML config declaring your model profiles.",
)


@click.group()
@click.version_option(package_name="paaf-llm")
def main() -> None:
    """PAAF — read and drive the assistant's mind.

    `paaf prompt` prints the exact system prompt your model receives.
    `paaf chat` holds a conversation over your configured profiles.
    """


@main.command()
@_config_option
@click.option(
    "--show-prompt",
    is_flag=True,
    help="Echo the exact system prompt sent, before each reply (D-02).",
)
@click.option(
    "--secrets",
    "secrets_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help=(
        "Path to the encrypted store holding the keys your profiles name with "
        f"api_key_ref. Its passphrase is read from the {SECRET_PASSPHRASE_ENV} "
        "environment variable, never from the command line."
    ),
)
@click.option(
    "--trace-db",
    "trace_db_path",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help=(
        "Record each turn — the prompt sent, which profile served it, and every "
        "fallback hop — into a local SQLite file at this path, created on first "
        "use. Nothing is written unless you give this flag."
    ),
)
def chat(
    config_path: str,
    show_prompt: bool,
    secrets_path: str | None,
    trace_db_path: str | None,
) -> None:
    """Hold a conversation, falling back down your chain when a provider drops."""
    config = load_llm_config(config_path)
    console = _make_console()
    render_profiles(config, console)
    # Returns None — and opens nothing — unless a profile actually named a key.
    store = open_secret_store(
        config, secrets_path, os.environ.get(SECRET_PASSPHRASE_ENV)
    )
    # Everything past here runs inside the loop, because the trace sink and the
    # agent that writes to it both belong to it. See _chat_session's docstring.
    asyncio.run(
        _chat_session(
            config,
            show_prompt=show_prompt,
            console=console,
            secret_store=store,
            trace_db_path=trace_db_path,
        )
    )


@main.command()
@_config_option
@click.option(
    "--provenance",
    is_flag=True,
    help=(
        "Label each part of the prompt with its source (base / skill:<name> / "
        "mesh:<layer>), then show every handoff tool this agent is offered, with "
        "the exact name and description the model is sent."
    ),
)
@click.option(
    "--agent",
    "agent_name",
    default=None,
    help=(
        "Read this profile's prompt instead of the active one. Works for a peer "
        "that is not currently awake, and for the observer, which never is."
    ),
)
def prompt(config_path: str, provenance: bool, agent_name: str | None) -> None:
    """Print the exact system prompt your model receives. No model is called.

    A pure dry run: no adapter is constructed and no network is touched, so this
    is safe to pipe, diff, and paste. The default output is the composed prompt
    and nothing else — the trailing newline is omitted deliberately so
    ``paaf prompt --config x.yaml > sent.txt`` captures the exact bytes (PERS-04).

    ``--provenance`` shows the SAME content with source labels (D-03), and then
    the handoff tools this agent is offered, each with the exact name and
    description the model is sent. It is opt-in because the raw view is the
    authoritative one; annotation is an audit aid laid around the prompt, never a
    rendering of it.

    ``--agent <name>`` aims the plain view at a different declared profile
    (D-19). The default — the active agent — is unchanged, because that is the
    prompt a turn starts from and it is what a user diffing captured output
    expects. The flag exists for the two prompts that are otherwise unreadable: a
    peer that is not currently awake, and the observer, which is never awake at
    all. It is the only way to read either.
    """
    config = load_llm_config(config_path)
    # Validated BEFORE it is used as a key. `--agent` is untrusted CLI input, and
    # `config.profiles[name]` on an unknown value is a KeyError traceback that
    # names the missing key and nothing a user could act on (T-04-23).
    if agent_name is not None and agent_name not in config.profiles:
        raise _config_failure(
            ValueError(
                UNKNOWN_AGENT.format(name=agent_name, declared=sorted(config.profiles))
            )
        )
    target = agent_name if agent_name is not None else config.active_profile
    profile = config.profiles[target]

    # The same fragment source build_agent hands the agent — one call, so the
    # inspector cannot show a prompt assembled from different parts (D-02).
    fragments = load_skill_fragments(config)
    # ...and the same two mesh helpers `Agent.system_prompt` calls, for the same
    # reason. A per-agent base prompt or an explainer re-derived here would be a
    # second derivation, which is the only way an inspector can quietly
    # understate what was sent (D-17, MESH-04).
    base_prompt = mesh.base_prompt_for(profile, config)
    mesh_fragments = mesh.mesh_fragments_for(target, profile, config)
    composer = PromptComposer()

    if provenance:
        for segment in composer.segments(base_prompt, fragments, mesh_fragments):
            click.echo(PROVENANCE_LABEL.format(source=segment.source))
            click.echo(segment.text)
        _render_tool_surface(config, target, profile)
        return

    # No prefix, no suffix, no newline: stdout IS the prompt (PERS-04/05, D-10).
    click.echo(composer.compose(base_prompt, fragments, mesh_fragments), nl=False)


def _render_tool_surface(
    config: LlmConfig, agent_name: str, profile: ModelProfile
) -> None:
    """Print every handoff tool ``agent_name`` is offered, name and description.

    **This is not decoration, and it is the reason plan 04-05 exists.** A tool's
    name and its description are sent to the model and steer it — a peer's
    manifest riding on ``transfer_to_chef`` is exactly as persuasive as a
    sentence in the system prompt — and they are NOT part of the system prompt.
    An inspector that rendered only :class:`PromptComposer` segments would
    therefore satisfy every Phase-3 test and still hide behaviour-steering text,
    which is precisely what PERS-05 forbids (RESEARCH Finding 1).

    The surface is read from :func:`paaf_llm.mesh.tools_for_leg` — the ONE
    function that decides a leg's moves — rather than rebuilt here, so the
    inspector cannot show a surface the engine would not offer. ``hops_used=0``
    means "the first leg of a turn", which is the only honest answer outside a
    turn; the hop budget WITHDRAWS this surface at the wall (D-08), so what is
    shown is the most the model is ever offered, never less.

    Rendered under ``--provenance`` only (OQ-3). The default output keeps its
    byte-exact, pipe-safe contract: PERS-05 is satisfied because the surface is
    REACHABLE, not because it is default.

    ``click.echo`` rather than a rich console, and deliberately: a description is
    the user's own manifest text, and echo interprets nothing whatsoever — no
    markup, and none of rich's own substitutions either. That is strictly
    stronger than ``_make_console()``'s ``markup=False`` for the one thing this
    command exists to guarantee, which is that what is printed is what was sent
    (T-04-24).
    """
    tools = mesh.tools_for_leg(
        agent_name, profile, config.profiles, 0, config.hop_budget
    )
    if tools:
        for tool in tools:
            click.echo(
                PROVENANCE_LABEL.format(
                    source=f"{mesh.MESH_TOOL_SOURCE_PREFIX}{tool.name}"
                )
            )
            click.echo(tool.description)
        click.echo(PROVENANCE_LABEL.format(source=mesh.MESH_RETRY_SOURCE))
        click.echo(mesh.DEFAULT_RETRY_TEMPLATE)


@main.command()
@_config_option
def profiles(config_path: str) -> None:
    """Show the mesh: each profile's manifest and peers, the budget, the home agent."""
    render_profiles(load_llm_config(config_path), _make_console())
