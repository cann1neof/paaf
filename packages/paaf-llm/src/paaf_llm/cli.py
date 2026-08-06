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
from pydantic import ValidationError
from rich.console import Console

from .agent import Agent
from .compose import PromptComposer
from .ports import AdapterError, AllProvidersFailed, EngineError
from .profiles import LlmConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .agent import SecretResolver, TraceSink
    from .ports import ChatAdapter

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

#: Stated wherever the peer graph is shown. MODEL-05 is inert data in this phase
#: (D-07): the graph is declared, validated, and displayed, and nothing routes on
#: it. Saying so in the output keeps the surface from implying a behavior that
#: Phase 4 has not built yet.
NO_HANDOFF_NOTE = (
    "The peer graph is inert in this phase: it is declared and validated data, "
    "and no handoff is performed."
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
    """Print every profile's capability manifest and peer graph (MODEL-05, SC#4).

    Inert data, rendered as data: what each model says it handles (free text, by
    D-08 — there is no routing DSL to display) and which peers it *may* one day
    hand off to. Nothing here reads the graph to make a decision, and
    :data:`NO_HANDOFF_NOTE` says so out loud so the surface cannot be mistaken
    for a mesh that already works.
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
    console.print(NO_HANDOFF_NOTE, style="dim")


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
def chat(config_path: str, show_prompt: bool, secrets_path: str | None) -> None:
    """Hold a conversation, falling back down your chain when a provider drops."""
    config = load_llm_config(config_path)
    console = _make_console()
    render_profiles(config, console)
    # Returns None — and opens nothing — unless a profile actually named a key.
    store = open_secret_store(
        config, secrets_path, os.environ.get(SECRET_PASSPHRASE_ENV)
    )
    # The second reachable failure site: the factory validates every declared
    # profile's provider before a single turn runs, so a config error can land
    # here rather than mid-conversation.
    try:
        agent = build_agent(config, secret_store=store)
    except EngineError as exc:
        raise _config_failure(exc) from exc
    asyncio.run(_chat_loop(agent, show_prompt=show_prompt, console=console))


@main.command()
@_config_option
@click.option(
    "--provenance",
    is_flag=True,
    help="Label each part of the prompt with its source (base / skill:<name>).",
)
def prompt(config_path: str, provenance: bool) -> None:
    """Print the exact system prompt your model receives. No model is called.

    A pure dry run: no adapter is constructed and no network is touched, so this
    is safe to pipe, diff, and paste. The default output is the composed prompt
    and nothing else — the trailing newline is omitted deliberately so
    ``paaf prompt --config x.yaml > sent.txt`` captures the exact bytes (PERS-04).

    ``--provenance`` shows the SAME content with source labels (D-03). It is
    opt-in because the raw view is the authoritative one; annotation is an audit
    aid laid around the prompt, never a rendering of it.
    """
    config = load_llm_config(config_path)
    # The same fragment source build_agent hands the agent — one call, so the
    # inspector cannot show a prompt assembled from different parts (D-02).
    fragments = load_skill_fragments(config)
    composer = PromptComposer()

    if provenance:
        for segment in composer.segments(config.base_prompt, fragments):
            click.echo(PROVENANCE_LABEL.format(source=segment.source))
            click.echo(segment.text)
        return

    # No prefix, no suffix, no newline: stdout IS the prompt (PERS-04/05, D-10).
    click.echo(composer.compose(config.base_prompt, fragments), nl=False)


@main.command()
@_config_option
def profiles(config_path: str) -> None:
    """Show each profile's capability manifest and peer graph (inert data)."""
    render_profiles(load_llm_config(config_path), _make_console())
