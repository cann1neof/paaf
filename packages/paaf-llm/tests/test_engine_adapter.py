# SPDX-License-Identifier: Apache-2.0
"""The real adapter's wiring and failure translation, proven OFFLINE.

Two boundaries this file respects, both load-bearing:

**It never runs without the extra.** ``pytest.importorskip("langchain")`` skips
the whole module when ``paaf-llm[engine]`` is absent, which is the state the
framework-uninstalled suite (SC#1) runs in. The guard is not taken on faith:
:func:`test_engine_module_refuses_to_import_without_the_extra` spawns a pristine
interpreter with ``langchain`` hidden and proves ``paaf_llm._engine`` raises
``ImportError`` there — the negative control for the whole optional-extra design.

**It never opens a socket.** The suite runs under ``--disable-socket``, and that
is a feature here rather than an obstacle: everything this file asserts —
provider-string mapping, ``base_url`` derivation, key-by-reference resolution,
and the translation of a provider's failure into a PAAF ``AdapterError`` — is
decidable without a model. Binding a chat model contacts nobody, so those
assertions run against the REAL framework objects; only the streaming call itself
is stubbed. Live round-trips against a real Ollama box and real cloud keys are
the phase's documented MANUAL verification, and pretending to automate them here
would replace a real check with a fake one.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from typing import Any

import pytest

pytest.importorskip("langchain")

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)
from langchain_core.messages.ai import UsageMetadata
from paaf_llm._engine import (
    PROVIDER_STRINGS,
    EngineError,
    LangChainAdapter,
    build_engine_adapter,
    classify,
)
from paaf_llm.ports import (
    AdapterError,
    ChatAdapter,
    ConnectionFailed,
    Message,
    RateLimited,
    RequestTimedOut,
    ServerError,
)
from paaf_llm.profiles import LlmConfig, ModelProfile

# --------------------------------------------------------------------- fakes --


class _StubModel:
    """Stands in for a bound chat model: scripted chunks, or one failure.

    Only the streaming CALL is stubbed. Every other assertion in this file runs
    against a real framework-built model, because building one touches no
    network — so the parts that can be checked honestly offline are.
    """

    def __init__(
        self, *, chunks: tuple[Any, ...] = (), error: BaseException | None = None
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.seen: list[Any] = []

    async def astream(self, messages: list[Any]) -> Any:
        self.seen = list(messages)
        if self.error is not None:
            raise self.error
        for chunk in self.chunks:
            yield chunk


class _Secrets:
    """A minimal SecretStore: names in, values out, nothing else observable."""

    def __init__(self, **values: str) -> None:
        self._values = values

    def get(self, key: str) -> str | None:
        return self._values.get(key)


def _stub(adapter: LangChainAdapter, model: _StubModel) -> None:
    """Point every bind on ``adapter`` at ``model`` (no provider is contacted)."""
    adapter.bind = lambda profile: model  # type: ignore[method-assign]


def _ollama(name: str, host: str) -> ModelProfile:
    return ModelProfile(
        provider="ollama", model=name, endpoint_host=host, endpoint_port=11434
    )


async def _drain(adapter: LangChainAdapter, profile: ModelProfile) -> list[str]:
    return [token async for token in adapter.stream(profile, [Message("user", "hi")])]


# ------------------------------------------------------- the optional extra --


def test_engine_module_refuses_to_import_without_the_extra() -> None:
    """Without the extra, importing the adapter raises ImportError (SC#1 control).

    This is what makes ``cli._default_adapter``'s friendly "install the extra"
    message reachable: it wraps only the ``from ._engine import ...`` statement,
    so if this module imported cleanly and failed later, a user without the extra
    would get a bare ``ModuleNotFoundError`` mid-conversation instead.

    Run in a child interpreter because it must observe module IMPORT time, which
    has already happened in this process.
    """
    script = textwrap.dedent(
        """
        import importlib.util
        real = importlib.util.find_spec
        importlib.util.find_spec = (
            lambda name, package=None: None if name == "langchain"
            else real(name, package)
        )
        try:
            import paaf_llm._engine
        except ImportError as exc:
            assert "paaf-llm[engine]" in str(exc), str(exc)
            print("REFUSED")
        else:
            raise AssertionError("_engine imported with the extra hidden")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "REFUSED" in result.stdout


def test_importing_paaf_llm_still_loads_no_framework() -> None:
    """The extra being INSTALLED must not make the package import it (SC#1).

    The wheel job proves the framework-absent half. This proves the other half,
    which only a machine with the extra installed can: even here, ``import
    paaf_llm`` pulls in no ``langchain*`` module, so the adapter is genuinely
    lazy rather than merely optional at install time.
    """
    probe = (
        "import sys, paaf_llm; "
        "print([m for m in sys.modules if m.startswith(('langchain', 'langgraph'))])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


# ------------------------------------------------------ MODEL-01/02: mapping --


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("ollama", "ollama:m"),
        ("openai_compatible", "openai:m"),
        ("anthropic", "anthropic:m"),
    ],
)
def test_provider_string_covers_every_declared_provider(
    provider: str, expected: str
) -> None:
    """Each schema provider maps to its init_chat_model prefix (MODEL-02)."""
    profile = ModelProfile(provider=provider, model="m")
    assert LangChainAdapter.provider_string(profile) == expected


def test_every_schema_provider_has_a_binding() -> None:
    """The schema's Literal and the adapter's table cannot drift apart.

    Reads the allowed values off ``ModelProfile`` itself rather than restating
    them, so widening the schema without teaching the adapter fails here instead
    of at someone's first turn.
    """
    declared = set(ModelProfile.model_fields["provider"].annotation.__args__)
    assert declared == set(PROVIDER_STRINGS)


# --------------------------------------------------- MODEL-06: two LAN boxes --


def test_two_lan_profiles_distinct_base_urls() -> None:
    """Two same-provider LAN profiles are two distinct bindings (MODEL-06).

    The headline of this requirement: a user with two Ollama boxes declares two
    profiles and gets two servers, not one client reused twice. Asserted at three
    levels — the derived URL, the cache identity, and the ``base_url`` the real
    bound model actually carries.
    """
    first, second = _ollama("qwen3", "192.168.1.10"), _ollama("qwen3", "192.168.1.11")
    adapter = LangChainAdapter()

    assert adapter.base_url(first) == "http://192.168.1.10:11434"
    assert adapter.base_url(second) == "http://192.168.1.11:11434"
    assert adapter.base_url(first) != adapter.base_url(second)
    assert adapter.cache_key(first) != adapter.cache_key(second)

    bound_first, bound_second = adapter.bind(first), adapter.bind(second)
    assert bound_first is not bound_second
    assert bound_first.base_url == "http://192.168.1.10:11434"
    assert bound_second.base_url == "http://192.168.1.11:11434"


def test_two_cloud_profiles_on_one_model_do_not_share_a_binding() -> None:
    """The cache must not collapse two endpoint-less profiles into one.

    The failure this guards is silent: two Anthropic profiles naming the same
    model both declare no endpoint, so a cache keyed on provider+base_url alone
    would hand the second profile the FIRST one's temperature and credential, and
    nothing would look wrong.
    """
    adapter = LangChainAdapter(secret_store=_Secrets(k1="sk-one", k2="sk-two"))
    hot = ModelProfile(
        provider="anthropic", model="claude", temperature=1.4, api_key_ref="k1"
    )
    cold = ModelProfile(
        provider="anthropic", model="claude", temperature=0.1, api_key_ref="k2"
    )

    assert adapter.cache_key(hot) != adapter.cache_key(cold)
    assert adapter.bind(hot) is not adapter.bind(cold)
    assert adapter.bind(hot) is adapter.bind(hot)  # still cached per profile


def test_a_profile_with_no_endpoint_declares_no_base_url() -> None:
    """A cloud profile has no PAAF endpoint to declare — that is not a hidden one."""
    assert LangChainAdapter.base_url(ModelProfile(provider="anthropic", model="c")) is None


# ------------------------------------------------------ CORE-04: key by ref --


def test_api_key_is_resolved_by_reference_not_read_from_config() -> None:
    """The profile carries the key's NAME; the value comes from the store."""
    adapter = LangChainAdapter(secret_store=_Secrets(anthropic="sk-live-value"))
    profile = ModelProfile(provider="anthropic", model="c", api_key_ref="anthropic")

    assert adapter.api_key(profile) == "sk-live-value"
    assert adapter.model_kwargs(profile)["api_key"] == "sk-live-value"


def test_an_unresolvable_key_reference_is_a_config_error_not_a_fallback() -> None:
    """A missing credential must not degrade quietly into "try the next model".

    Falling back here would leave the user believing their cloud profile works
    while another model silently answers for it.
    """
    adapter = LangChainAdapter(secret_store=_Secrets())
    profile = ModelProfile(provider="anthropic", model="c", api_key_ref="absent")

    with pytest.raises(EngineError) as raised:
        adapter.api_key(profile)
    assert not isinstance(raised.value, AdapterError)
    assert "absent" in str(raised.value)


async def test_a_resolved_key_never_appears_in_a_raised_message(monkeypatch) -> None:
    """T-03-04: a provider echoing the credential back cannot leak it onward.

    The adapter never formats a key into a message itself; the realistic leak is
    a provider quoting the credential it rejected inside its own error string,
    which would then reach a log or the user's terminal.
    """
    secret = "sk-super-secret-value"
    adapter = LangChainAdapter(secret_store=_Secrets(cloud=secret))
    profile = ModelProfile(provider="anthropic", model="c", api_key_ref="cloud")
    adapter.api_key(profile)  # resolve it, so the scrubber knows the value

    _stub(adapter, _StubModel(error=RuntimeError(f"invalid api key: {secret}")))
    with pytest.raises(EngineError) as raised:
        await _drain(adapter, profile)

    assert secret not in str(raised.value)
    assert "***" in str(raised.value)


# ------------------------------------------ MODEL-03/04: exception translation --


class _Status(Exception):
    """A provider error carrying an HTTP status, as every SDK here does."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConnectError(Exception):
    """Named to mirror ``httpx.ConnectError`` — the classifier reads type names."""


class ReadTimeout(Exception):
    """Named to mirror ``httpx.ReadTimeout``."""


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConnectError("all connection attempts failed"), ConnectionFailed),
        (ReadTimeout("timed out"), RequestTimedOut),
        (_Status("upstream exploded", 503), ServerError),
        (_Status("slow down", 429), RateLimited),
    ],
    ids=["connection", "timeout", "http_5xx", "http_429"],
)
async def test_exception_translation(
    error: Exception, expected: type[AdapterError]
) -> None:
    """Each transport failure becomes its PAAF error, carrying the right reason.

    This is what lets the engine's already-proven fallback loop work over real
    providers unchanged: it classifies a hop by reading ``.reason``, never by
    matching a provider's exception type.
    """
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(error=error))

    with pytest.raises(expected) as raised:
        await _drain(adapter, _ollama("qwen3", "192.168.1.10"))

    assert raised.value.reason is expected.reason
    assert raised.value.__cause__ is error


def test_translation_matches_the_real_provider_exception_types() -> None:
    """The duck-typed classifier is checked against the SDKs it must recognize.

    The risk of classifying structurally instead of importing each provider's
    exception classes is that the structure is guessed wrong. So the guess is
    tested against the real articles — every failure mode of all three bindings
    plus the shared transport layer underneath them.
    """
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx")
    ollama = pytest.importorskip("ollama")
    openai = pytest.importorskip("openai")

    request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    server = httpx.Response(503, request=request)
    limited = httpx.Response(429, request=request)

    expected: list[tuple[BaseException, type[AdapterError]]] = [
        (ollama.ResponseError("boom", 503), ServerError),
        (ollama.ResponseError("slow down", 429), RateLimited),
        (httpx.ConnectError("all connection attempts failed"), ConnectionFailed),
        (httpx.ReadTimeout("timed out"), RequestTimedOut),
        # Subclasses BOTH TimeoutException and TransportError — the classifier
        # must read it as a timeout, not as a connection failure.
        (httpx.ConnectTimeout("timed out"), RequestTimedOut),
        (openai.APIConnectionError(request=request), ConnectionFailed),
        # Subclasses APIConnectionError; same ordering trap as ConnectTimeout.
        (openai.APITimeoutError(request=request), RequestTimedOut),
        (openai.RateLimitError("rate", response=limited, body=None), RateLimited),
        (openai.InternalServerError("boom", response=server, body=None), ServerError),
        (anthropic.APIConnectionError(request=request), ConnectionFailed),
        (anthropic.APITimeoutError(request=request), RequestTimedOut),
        (anthropic.RateLimitError("rate", response=limited, body=None), RateLimited),
        (anthropic.InternalServerError("boom", response=server, body=None), ServerError),
    ]

    assert [classify(exc) for exc, _ in expected] == [want for _, want in expected]


def test_a_wrapped_transport_failure_is_still_classified() -> None:
    """Providers wrap; the signal is sometimes only on the inner exception."""
    outer = RuntimeError("streaming failed")
    outer.__cause__ = _Status("upstream exploded", 503)
    assert classify(outer) is ServerError


async def test_an_unclassifiable_failure_is_not_turned_into_a_fallback_reason() -> None:
    """The classifier must decline to guess — the control on all of the above.

    Without this, a translator that mapped everything to ``ConnectionFailed``
    would pass every test above while reporting "fell back (connection)" at a
    user whose real problem is a typo in a model name.
    """
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(error=ValueError("model 'qwn3' not found")))

    with pytest.raises(EngineError) as raised:
        await _drain(adapter, _ollama("qwn3", "192.168.1.10"))

    assert classify(ValueError("model 'qwn3' not found")) is None
    assert not isinstance(raised.value, AdapterError)


# ---------------------------------------------------------------- streaming --


async def test_streams_plain_str_tokens_and_maps_the_roles() -> None:
    """Tokens cross the port as plain ``str``, and PAAF roles map to the framework.

    ``str()`` around the token is not decoration: ``AIMessageChunk.text`` is a
    framework ``TextAccessor``, and letting one cross a PAAF-typed stream would
    leak a framework type through the port MODEL-08 exists to keep clean.
    """
    adapter = LangChainAdapter()
    model = _StubModel(
        chunks=(AIMessageChunk(content="he"), AIMessageChunk(content="llo"))
    )
    _stub(adapter, model)

    tokens = [
        token
        async for token in adapter.stream(
            _ollama("qwen3", "192.168.1.10"),
            [Message("system", "be kind"), Message("user", "hi"), Message("assistant", "yo")],
        )
    ]

    assert tokens == ["he", "llo"]
    assert [type(token) for token in tokens] == [str, str]
    assert [type(m) for m in model.seen] == [SystemMessage, HumanMessage, AIMessage]
    assert [m.content for m in model.seen] == ["be kind", "hi", "yo"]


async def test_empty_chunks_are_not_yielded_as_first_tokens() -> None:
    """An empty chunk must not satisfy the engine's first-token budget.

    Yielding ``""`` would let a provider that has produced nothing look like it
    answered promptly, masking exactly the slow provider D-04 exists to catch.
    """
    adapter = LangChainAdapter()
    _stub(
        adapter,
        _StubModel(chunks=(AIMessageChunk(content=""), AIMessageChunk(content="hi"))),
    )
    assert await _drain(adapter, _ollama("qwen3", "192.168.1.10")) == ["hi"]


async def test_usage_is_read_after_aggregation() -> None:
    """SPIKE-05: usage arrives on ONE chunk, so it is read off the aggregate.

    A per-chunk read reports ``None`` roughly 333 times out of 334 against
    Ollama. The scripted stream reproduces that shape: only the last chunk
    carries counts.
    """
    adapter = LangChainAdapter()
    _stub(
        adapter,
        _StubModel(
            chunks=(
                AIMessageChunk(content="he"),
                AIMessageChunk(
                    content="llo",
                    usage_metadata=UsageMetadata(
                        input_tokens=11, output_tokens=5, total_tokens=16
                    ),
                ),
            )
        ),
    )

    await _drain(adapter, _ollama("qwen3", "192.168.1.10"))
    usage = adapter.last_usage()
    assert (usage.prompt_tokens, usage.completion_tokens) == (11, 5)


async def test_usage_stays_none_when_the_provider_reported_none() -> None:
    """``None`` means "the provider did not say" — inventing a zero would lie."""
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(chunks=(AIMessageChunk(content="hi"),)))

    await _drain(adapter, _ollama("qwen3", "192.168.1.10"))
    usage = adapter.last_usage()
    assert (usage.prompt_tokens, usage.completion_tokens) == (None, None)


# ------------------------------------------------------- warmup and factory --


async def test_preload_warms_a_local_model_and_skips_a_hosted_one() -> None:
    """``Agent.warmup`` calls this hook; it warms what is actually cold.

    Preloading a hosted model would spend the user's tokens on every session
    start to warm something that was never cold, so only local providers are
    exercised.
    """
    adapter = LangChainAdapter()
    model = _StubModel(chunks=(AIMessageChunk(content="pong"),))
    _stub(adapter, model)

    await adapter.preload(_ollama("qwen3", "192.168.1.10"))
    assert [m.content for m in model.seen] == ["ping"]

    model.seen = []
    await adapter.preload(ModelProfile(provider="anthropic", model="claude"))
    assert model.seen == []


async def test_preload_survives_a_provider_that_is_down() -> None:
    """Warmup is an optimization: a dead provider must not stop the session.

    The fallback loop already handles a down provider at turn time, and reporting
    it here too would report it twice.
    """
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(error=ConnectError("refused")))
    await adapter.preload(_ollama("qwen3", "192.168.1.10"))  # must not raise


def test_build_engine_adapter_is_the_factory_the_cli_imports() -> None:
    """``cli._default_adapter`` calls ``build_engine_adapter(config)`` — unchanged.

    Pinning the name and the one-argument call keeps ``paaf chat`` working
    without a CLI edit, which is the whole point of the port.
    """
    config = LlmConfig(
        active_profile="a",
        profiles={
            "a": _ollama("qwen3", "192.168.1.10"),
            "b": _ollama("qwen3", "192.168.1.11"),
        },
        fallback_chain=["b"],
    )
    adapter = build_engine_adapter(config)

    assert isinstance(adapter, LangChainAdapter)
    assert isinstance(adapter, ChatAdapter)
    assert callable(adapter.preload)
