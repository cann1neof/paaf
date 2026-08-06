# SPDX-License-Identifier: Apache-2.0
"""PERS-04/05 + MODEL-05: the inspector cannot understate what was sent.

The promise this file makes mechanical is the project's core value stated as a
byte comparison: *what ``paaf prompt`` prints is what the model receives.* The
central test does not compare the CLI to the composer and stop there — comparing
two calls to the same pure function would pass even if the agent sent something
else entirely. It compares three things:

1. what ``paaf prompt`` wrote to stdout,
2. what :meth:`PromptComposer.compose` returns for that config, and
3. **the ``system`` message the adapter actually received** on a real turn,
   read back off :attr:`FakeAdapter.calls`.

Only (3) closes the loop. It is the difference between "the inspector calls the
composer" and "the inspector shows what crossed the port" (T-03-17/T-03-18).

Every claim here carries a negative control, because a check that cannot fail is
not a check: the byte-identity is re-run with NON-EMPTY skill fragments (an empty
base prompt makes ``"" == ""`` pass against a CLI that prints nothing); the
fallback notice is paired with a healthy turn that must print none; and
``--show-prompt`` is paired with a run that must not leak the prompt without it.

The whole file runs framework-uninstalled (SC#1): the fake is injected through
:func:`paaf_llm.cli._default_adapter`, so the *real* ``chat`` command path is
exercised end to end without a provider, a socket, or the ``[engine]`` extra.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from paaf_llm import cli
from paaf_llm.cli import (
    CONFIG_FAILURE_NOTICE,
    NO_HANDOFF_NOTE,
    PROVENANCE_LABEL,
    build_agent,
    load_llm_config,
    load_skill_fragments,
    main,
)
from paaf_llm.compose import SEGMENT_SEPARATOR, PromptComposer
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    ChatAdapter,
    ConnectionFailed,
    EngineError,
    ServerError,
    Usage,
)
from paaf_llm.profiles import LlmConfig, ModelProfile

#: A base prompt and two persona fragments with enough shape that a CLI which
#: trimmed, reordered, or re-wrapped any of it would fail the byte comparison.
BASE_PROMPT = "You are Ada.\nAnswer plainly, and say when you do not know."
FRAGMENTS: list[tuple[str, str]] = [
    ("timekeeper", "When asked the time, give it in the user's local zone."),
    ("kitchen", "Measurements are metric.\nNever guess an oven temperature."),
]


# --------------------------------------------------------------------- helpers


def write_config(tmp_path: Path, config: LlmConfig) -> str:
    """Serialize ``config`` to a YAML file and return its path.

    Round-tripping the validated model (rather than hand-writing YAML) means the
    file the CLI reads and the object the test asserts against cannot drift: a
    schema change that broke the CLI's load path would break this helper too.
    """
    path = tmp_path / "paaf.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")), encoding="utf-8")
    return str(path)


def make_config(**overrides: Any) -> LlmConfig:
    """A two-profile config: ``local`` active with ``cloud`` behind it."""
    fields: dict[str, Any] = {
        "base_prompt": BASE_PROMPT,
        "active_profile": "local",
        "fallback_chain": ["cloud"],
        "profiles": {
            "local": ModelProfile(provider="ollama", model="local"),
            "cloud": ModelProfile(provider="anthropic", model="cloud"),
        },
    }
    fields.update(overrides)
    return LlmConfig(**fields)


def inject(monkeypatch: pytest.MonkeyPatch, adapter: ChatAdapter) -> None:
    """Make the real ``chat`` command build ``adapter`` instead of a provider.

    Patching the adapter FACTORY rather than ``build_agent`` keeps the command's
    own wiring — config load, fragment source, agent construction — inside the
    test. Stubbing ``build_agent`` would test the stub.

    Typed to the PORT rather than to :class:`FakeAdapter`, because the failure
    tests below inject local adapters that model what the shipped fake cannot:
    the fake fails only with an ``AdapterError``, and every exception class that
    matters here is one the fallback loop deliberately does not catch.
    """
    monkeypatch.setattr(cli, "_default_adapter", lambda _config: adapter)


def label_parts() -> tuple[str, str]:
    """Split :data:`PROVENANCE_LABEL` into its prefix and suffix around the source."""
    prefix, suffix = PROVENANCE_LABEL.split("{source}")
    return prefix, suffix


def parse_provenance(output: str) -> list[tuple[str, str]]:
    """Recover ``[(source, text), ...]`` from a ``--provenance`` run.

    Parsed from the format :data:`PROVENANCE_LABEL` actually declares, so the
    test cannot pass against a CLI that renders a different one.

    The single trailing newline is the terminator of the last ``click.echo``, not
    part of the final segment, so it is removed before splitting.
    """
    prefix, suffix = label_parts()
    pairs: list[tuple[str, str]] = []
    source: str | None = None
    buffer: list[str] = []

    for line in output.removesuffix("\n").split("\n"):
        is_label = (
            line.startswith(prefix)
            and line.endswith(suffix)
            and len(line) > len(prefix + suffix)
        )
        if is_label:
            if source is not None:
                pairs.append((source, "\n".join(buffer)))
            source = line[len(prefix) : len(line) - len(suffix)]
            buffer = []
        else:
            buffer.append(line)

    if source is not None:
        pairs.append((source, "\n".join(buffer)))
    return pairs


def system_message_actually_sent(config: LlmConfig, fragments: Any = None) -> str:
    """Run one real turn through the fake and return the ``system`` message it got.

    This is the "as sent" half of PERS-04. The agent is built through the CLI's
    own :func:`build_agent`, so the fragments it composes with are the ones the
    CLI would use — not a set the test chose.
    """
    adapter = FakeAdapter()
    adapter.program("local", tokens=["ok"])
    agent = build_agent(config, adapter, skill_fragments=fragments)

    import asyncio

    asyncio.run(agent.turn("hello"))

    _profile_key, messages = adapter.calls[0]
    assert messages[0].role == "system"
    return messages[0].content


# ------------------------------------------------------- PERS-04 byte-identity


def test_prompt_byte_exact(tmp_path: Path) -> None:
    """``paaf prompt`` == ``compose(...)`` == the system message the adapter got.

    The three-way identity (PERS-04). The third leg is what makes it a real
    guarantee: an inspector wired to its own derivation would satisfy the first
    two and still lie about the turn.
    """
    config = make_config()
    path = write_config(tmp_path, config)

    result = CliRunner().invoke(main, ["prompt", "--config", path])
    assert result.exit_code == 0, result.output

    loaded = load_llm_config(path)
    fragments = load_skill_fragments(loaded)
    composed = PromptComposer().compose(loaded.base_prompt, fragments)

    assert result.output == composed
    assert result.output == system_message_actually_sent(loaded)


def test_prompt_byte_exact_with_skill_fragments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL for the identity: it holds with fragments present too.

    Phase 3's fragment source is a stub that returns nothing (D-09), so
    :func:`test_prompt_byte_exact` alone would also pass against a CLI that
    printed only the base prompt and silently dropped every skill (PERS-02).
    Pointing the shared source at real fragments removes that escape: the CLI
    must now surface text it does not know about in advance.
    """
    monkeypatch.setattr(cli, "load_skill_fragments", lambda _config: list(FRAGMENTS))
    config = make_config()
    path = write_config(tmp_path, config)

    result = CliRunner().invoke(main, ["prompt", "--config", path])
    assert result.exit_code == 0, result.output

    for _name, text in FRAGMENTS:
        assert text in result.output

    composed = PromptComposer().compose(config.base_prompt, list(FRAGMENTS))
    assert result.output == composed
    assert result.output == system_message_actually_sent(config, list(FRAGMENTS))


def test_prompt_adds_no_text_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PERS-05 / D-10 at the CLI: the output is the user's text and nothing else.

    Reconstructed from the RAW inputs rather than from the composer, so this is
    independent of :mod:`paaf_llm.compose`: no banner, no header, no separator of
    the CLI's own invention, and no trailing newline can survive it.
    """
    monkeypatch.setattr(cli, "load_skill_fragments", lambda _config: list(FRAGMENTS))
    path = write_config(tmp_path, make_config())

    result = CliRunner().invoke(main, ["prompt", "--config", path])

    expected = SEGMENT_SEPARATOR.join(
        [BASE_PROMPT, *(text for _name, text in FRAGMENTS)]
    )
    assert result.output == expected


def test_prompt_calls_no_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NEGATIVE CONTROL: the dry run constructs no adapter and streams nothing.

    ``paaf prompt`` must be safe to run against a config whose provider is down,
    absent, or expensive. The factory is replaced with one that fails the test if
    it is ever reached.
    """

    def explode(_config: LlmConfig) -> Any:
        pytest.fail("paaf prompt constructed an adapter — it must be a pure dry run")

    monkeypatch.setattr(cli, "_default_adapter", explode)
    path = write_config(tmp_path, make_config())

    result = CliRunner().invoke(main, ["prompt", "--config", path])
    assert result.exit_code == 0, result.output


# ------------------------------------------------------------- D-03 provenance


def test_provenance_same_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The labeled view's segment texts rejoin into the byte-exact raw view."""
    monkeypatch.setattr(cli, "load_skill_fragments", lambda _config: list(FRAGMENTS))
    path = write_config(tmp_path, make_config())
    runner = CliRunner()

    raw = runner.invoke(main, ["prompt", "--config", path])
    labeled = runner.invoke(main, ["prompt", "--config", path, "--provenance"])
    assert raw.exit_code == 0 and labeled.exit_code == 0, labeled.output

    parsed = parse_provenance(labeled.output)
    assert [source for source, _text in parsed] == [
        "base",
        "skill:timekeeper",
        "skill:kitchen",
    ]
    assert SEGMENT_SEPARATOR.join(text for _source, text in parsed) == raw.output


def test_provenance_is_not_the_default(tmp_path: Path) -> None:
    """NEGATIVE CONTROL for D-03: the raw view carries no labels at all.

    The raw output is authoritative; a label leaking into it would put text in
    the prompt the user never wrote.
    """
    prefix, _suffix = label_parts()
    path = write_config(tmp_path, make_config())

    result = CliRunner().invoke(main, ["prompt", "--config", path])
    assert prefix not in result.output


# ------------------------------------------------- MODEL-05 manifest + peers


def test_manifest_surfaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``paaf chat`` shows each profile's capabilities and peers, and no handoff.

    The manifest is free text by D-08 — there is no routing DSL to render — so
    the assertion is simply that every declared string reaches the user, plus the
    explicit statement that the graph is inert (SC#4).
    """
    config = make_config(
        profiles={
            "local": ModelProfile(
                provider="ollama",
                model="local",
                capabilities="fast local chat, never leaves the device",
                peers=["cloud"],
            ),
            "cloud": ModelProfile(
                provider="anthropic",
                model="cloud",
                capabilities="long-context reasoning and code",
                constraints=["never send private files"],
            ),
        }
    )
    path = write_config(tmp_path, config)
    adapter = FakeAdapter()
    adapter.program("local", tokens=["hi"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")
    assert result.exit_code == 0, result.output

    for name, profile in config.profiles.items():
        assert name in result.output
        assert profile.capabilities in result.output
    assert "cloud" in result.output  # local's declared peer
    assert "never send private files" in result.output
    assert NO_HANDOFF_NOTE in result.output


def test_manifest_performs_no_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL: declaring a peer does not route anything to it.

    ``local`` names ``cloud`` as a peer and is healthy. ``cloud`` is deliberately
    left UNPROGRAMMED, so the fake raises ``LookupError`` — not an
    ``AdapterError`` the loop could swallow — the moment anything contacts it.
    A green run is proof the peer graph stayed inert (MODEL-05, D-07).
    """
    config = make_config(
        fallback_chain=[],
        profiles={
            "local": ModelProfile(provider="ollama", model="local", peers=["cloud"]),
            "cloud": ModelProfile(provider="anthropic", model="cloud"),
        },
    )
    path = write_config(tmp_path, config)
    adapter = FakeAdapter()
    adapter.program("local", tokens=["served ", "by ", "local"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")
    assert result.exit_code == 0, result.output
    assert [key for key, _messages in adapter.calls] == ["local"]
    assert "local> served by local" in result.output


def test_profiles_command_surfaces_the_same_manifest(tmp_path: Path) -> None:
    """The non-interactive surface shows the manifest without touching a model."""
    config = make_config(
        profiles={
            "local": ModelProfile(
                provider="ollama", model="local", capabilities="local chat"
            ),
            "cloud": ModelProfile(
                provider="anthropic", model="cloud", capabilities="big context"
            ),
        }
    )
    path = write_config(tmp_path, config)

    result = CliRunner().invoke(main, ["profiles", "--config", path])
    assert result.exit_code == 0, result.output
    assert "local chat" in result.output
    assert "big context" in result.output
    assert NO_HANDOFF_NOTE in result.output


# ----------------------------------------------------------- D-06 chat surface


def test_fallback_notice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hop prints one brief inline notice naming where it went and why."""
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", fail=ConnectionFailed)
    adapter.program("cloud", tokens=["still ", "here"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")
    assert result.exit_code == 0, result.output
    assert "↳ fell back to cloud (connection)" in result.output
    assert "cloud> still here" in result.output


def test_healthy_turn_prints_no_fallback_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL for D-06: no hop, no notice — the notice is not decoration."""
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", tokens=["fine"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")
    assert result.exit_code == 0, result.output
    assert "fell back" not in result.output
    assert "local> fine" in result.output


def test_show_prompt_echoes_what_was_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--show-prompt`` echoes the exact system message the adapter received (D-02)."""
    monkeypatch.setattr(cli, "load_skill_fragments", lambda _config: list(FRAGMENTS))
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", tokens=["ok"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(
        main, ["chat", "--config", path, "--show-prompt"], input="hello\n"
    )
    assert result.exit_code == 0, result.output

    _key, messages = adapter.calls[0]
    assert messages[0].content in result.output


def test_chat_without_show_prompt_stays_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL: the prompt is echoed only when the user asks for it."""
    monkeypatch.setattr(cli, "load_skill_fragments", lambda _config: list(FRAGMENTS))
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", tokens=["ok"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")
    assert result.exit_code == 0, result.output
    assert BASE_PROMPT not in result.output


def test_multi_turn_conversation_continues_across_a_hop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two lines on stdin are two turns, and the second sees the first (D-01).

    The CLI is thin, so this asserts the wiring rather than the loop: history is
    the library's, and the command must not reset it between lines.
    """
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", fail=ConnectionFailed)
    adapter.program("cloud", tokens=["ack"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(
        main, ["chat", "--config", path], input="first\nsecond\n"
    )
    assert result.exit_code == 0, result.output
    assert result.output.count("↳ fell back to cloud (connection)") == 2

    _key, second_turn = adapter.calls[-1]
    contents = [message.content for message in second_turn]
    assert "first" in contents and "ack" in contents and "second" in contents


# ------------------------------------------------------ SC#1 framework-freedom


def test_build_agent_accepts_an_injected_adapter() -> None:
    """The seam the whole suite rests on: an injected adapter serves the turn."""
    adapter = FakeAdapter()
    adapter.program("local", tokens=["yes"])
    agent = build_agent(make_config(), adapter)

    import asyncio

    result = asyncio.run(agent.turn("hi"))
    assert result.text == "yes"
    assert result.served_by == "local"


def test_engine_import_is_lazy_in_the_source() -> None:
    """The adapter package is imported INSIDE a function, never at module scope.

    A source assertion because no runtime test can catch this regression from
    inside a process that has already imported the module successfully — and in
    a checkout where the extra happens to be installed, an eager import would
    work fine right up until a user installs the wheel without it (SC#1).
    """
    source = Path(cli.__file__).read_text(encoding="utf-8")
    engine_imports = [
        line for line in source.splitlines() if "from ._engine import" in line
    ]
    assert engine_imports, "expected the lazy _engine import to exist in cli.py"
    for line in engine_imports:
        assert line.startswith("    "), (
            f"_engine must be imported inside a function, not at module scope: {line!r}"
        )
    assert "import langchain" not in source
    assert "import langgraph" not in source


def test_importing_the_cli_loads_no_framework_and_no_engine() -> None:
    """A pristine interpreter importing ``paaf_llm.cli`` pulls in neither.

    Run in a subprocess because this test session has already imported plenty;
    an in-process check would be measuring the fixture, not the import.
    """
    probe = (
        "import sys, paaf_llm.cli;"
        "leaked=[m for m in sys.modules if m.split('.')[0] in "
        "('langchain','langgraph') or m.startswith('langchain_')];"
        "assert not leaked, leaked;"
        "assert 'paaf_llm._engine' not in sys.modules, 'engine imported eagerly';"
        "print('clean')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert "clean" in completed.stdout


def test_invalid_config_is_a_readable_error(tmp_path: Path) -> None:
    """A hand-edited config that names an undeclared profile fails legibly.

    The schema does the rejecting (CORE-01); the CLI's only job is to surface it
    as a message instead of a traceback, because the person fixing the YAML is
    the person reading the output.
    """
    path = tmp_path / "broken.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "active_profile": "missing",
                "profiles": {"local": {"provider": "ollama", "model": "local"}},
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["prompt", "--config", str(path)])
    assert result.exit_code != 0
    assert "is not a valid PAAF LLM config" in result.output
    assert "missing" in result.output


# ------------------------------------------------- readable failure surfaces --
#
# Gap 2 of 03-VERIFICATION: `EngineError` escaped `paaf chat` as a raw traceback,
# reproduced live twice by the verifier. For a phase whose thesis is "nothing
# hidden from the user, readable output", a traceback on the headline command is
# the one failure mode that contradicts it outright.
#
# Every test here is paired: a positive claim that a named failure reads well,
# and a control proving the handler that made it read well did not become a
# catch-all. `test_an_unexpected_exception_still_escapes` is the control for the
# whole section — a handler written over the base exception class would satisfy
# every positive assertion below and still be wrong.


class _RaisingAdapter:
    """Fails on the FIRST token with a supplied exception, and records the call.

    Deliberately not the shipped fake: the fake fails only with an
    ``AdapterError``, which is the one class these tests must not use — the whole
    question here is what happens to an exception the fallback loop is designed
    NOT to catch. ``_SlowLaterTokensAdapter`` in ``tests/test_fallback.py`` is the
    precedent for a local adapter modelling what the fake cannot.
    """

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[str] = []

    async def stream(self, profile: Any, messages: Any) -> Any:
        self.calls.append(profile.model)
        raise self._error
        yield ""  # unreachable, and required: it is what makes this a generator

    def last_usage(self) -> Usage:
        return Usage()


def test_a_bind_failure_is_reported_readably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A profile that cannot be bound prints one line, not a traceback (Gap 2).

    The detail is the verifier's own reproduced text — a profile declaring an
    ``api_key_ref`` with no secret store behind it, which is the single most
    likely real first-run failure.

    ``result.exception`` is the load-bearing assertion. Asserting only on the
    exit code and the output would pass against a CLI that crashed, because a
    traceback also exits non-zero and also contains the message.
    """
    path = write_config(tmp_path, make_config())
    detail = (
        "profile declares api_key_ref 'anthropic_key' but no secret store was "
        "provided to the adapter"
    )
    inject(monkeypatch, _RaisingAdapter(EngineError(detail)))

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")

    assert result.exit_code != 0
    assert CONFIG_FAILURE_NOTICE.format(detail=detail) in result.output
    assert not isinstance(result.exception, EngineError)


def test_a_build_time_failure_is_reported_readably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OTHER reachable site: the factory validates providers before any turn.

    ``build_engine_adapter`` checks every declared profile up front, so a config
    error can land before a single token is asked for. One helper serves both
    sites precisely so the two cannot drift into different wordings.
    """
    path = write_config(tmp_path, make_config())
    detail = "profile 'cloud': no binding for provider 'moon'"

    def explode(_config: LlmConfig) -> Any:
        raise EngineError(detail)

    monkeypatch.setattr(cli, "_default_adapter", explode)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")

    assert result.exit_code != 0
    assert CONFIG_FAILURE_NOTICE.format(detail=detail) in result.output
    assert not isinstance(result.exception, EngineError)


def test_an_unexpected_exception_still_escapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL for the whole section: the handlers name types, never all.

    A ``LookupError`` is neither a configuration failure nor a degraded provider
    — from the fake it means a test forgot to program a profile, which must stay
    loud. If either handler were widened to the base exception class, this test
    is the only one in the file that would turn red.
    """
    path = write_config(tmp_path, make_config())
    inject(monkeypatch, _RaisingAdapter(LookupError("no program for 'local'")))

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")

    assert result.exit_code != 0
    assert isinstance(result.exception, LookupError)


class _FailsAfterFirstTokenAdapter:
    """Yields one token, commits the profile, then fails mid-reply.

    The shipped fake cannot do this — it fails before its first token, which is
    the case the fallback loop handles. This models the case the loop
    deliberately does NOT handle: past ``# Committed: this profile serves the
    turn``, an ``AdapterError`` is left to propagate on purpose, because
    re-routing a half-spoken reply to a different model is worse than stopping.
    """

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[str] = []

    async def stream(self, profile: Any, messages: Any) -> Any:
        self.calls.append(profile.model)
        yield "half-a-"
        raise self._error

    def last_usage(self) -> Usage:
        return Usage()


def test_a_failure_after_the_reply_began_is_reported_readably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-commit provider failure reads as one line naming the reason.

    The reason is asserted as ``http_5xx`` — the ``FallbackReason`` VALUE, the
    same string the trace records (D-06) — rather than as a class name, so the
    terminal message and the trace row cannot disagree about why the turn died.

    The call count is the second half of the claim: exactly one stream call means
    the chain did not quietly try ``cloud`` after ``local`` had already begun
    speaking. Without it the test would pass against an engine that re-routed
    mid-reply and merely happened to fail again.
    """
    path = write_config(tmp_path, make_config())
    adapter = _FailsAfterFirstTokenAdapter(ServerError("upstream exploded"))
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")

    assert result.exit_code != 0
    assert "http_5xx" in result.output
    assert "upstream exploded" in result.output
    assert not isinstance(result.exception, ServerError)
    assert adapter.calls == ["local"]


def test_a_failure_before_the_reply_began_still_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NEGATIVE CONTROL for the mid-reply handler: a PRE-commit failure still hops.

    This is the control that protects MODEL-03/04 from the fix above. A handler
    that intercepted every ``AdapterError`` before the engine's fallback loop saw
    one would satisfy the positive test completely, while silently turning the
    ordered fallback chain — the headline feature — into an error message.
    """
    path = write_config(tmp_path, make_config())
    adapter = FakeAdapter()
    adapter.program("local", fail=ConnectionFailed)
    adapter.program("cloud", tokens=["still ", "here"])
    inject(monkeypatch, adapter)

    result = CliRunner().invoke(main, ["chat", "--config", path], input="hello\n")

    assert result.exit_code == 0, result.output
    assert "↳ fell back to cloud (connection)" in result.output
    assert "Error:" not in result.output
