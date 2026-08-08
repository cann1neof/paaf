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
from collections.abc import Sequence
from typing import Any

import pytest

pytest.importorskip("langchain")

import paaf_llm._engine as engine_module
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)
from langchain_core.messages.ai import UsageMetadata
from langchain_core.messages.tool import tool_call_chunk
from paaf_llm import cli
from paaf_llm._engine import (
    PROVIDER_STRINGS,
    UNAUTHENTICATED_API_KEY,
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
    ToolCall,
    ToolCallingChatAdapter,
    ToolSpec,
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
        self,
        *,
        chunks: tuple[Any, ...] = (),
        error: BaseException | None = None,
        bind_tools_error: BaseException | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.bind_tools_error = bind_tools_error
        self.seen: list[Any] = []
        #: Every ``bind_tools`` call, in order. An EMPTY list is the assertion
        #: that matters for the no-tools path: the port says offering nothing
        #: must behave exactly like ``stream``, and the only way to prove the
        #: branch was not taken is to record that it never ran.
        self.bound_tools: list[list[Any]] = []

    def bind_tools(self, tools: list[Any]) -> Any:
        if self.bind_tools_error is not None:
            raise self.bind_tools_error
        self.bound_tools.append(list(tools))
        return self

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


def _openai_compatible(
    *,
    path: str | None = "/v1",
    unauthenticated: bool = True,
    api_key_ref: str | None = None,
) -> ModelProfile:
    """A LAN OpenAI-compatible server — the vLLM / llama.cpp / LM Studio shape.

    Mirrors :func:`_ollama`. ``path`` and ``unauthenticated`` are settable
    because the controls in this file work by varying exactly one of them and
    asserting the outcome changes.
    """
    return ModelProfile(
        provider="openai_compatible",
        model="qwen3:32b",
        endpoint_host="192.168.1.20",
        endpoint_port=8000,
        endpoint_path=path,
        endpoint_unauthenticated=unauthenticated,
        api_key_ref=api_key_ref,
    )


#: Attribute names a bound client may expose its base URL under. The OpenAI and
#: Ollama bindings do NOT agree on one, so the assertion tries each — and fails
#: loudly if none matched, rather than passing vacuously.
_BASE_URL_ATTRS = ("openai_api_base", "base_url", "openai_base_url", "_base_url")


def _bound_base_url(model: Any) -> str | None:
    """Return the base URL ``model`` carries, or ``None`` if no attribute matched."""
    for name in _BASE_URL_ATTRS:
        value = getattr(model, name, None)
        if value is not None:
            return str(value)
    return None


async def _drain(adapter: LangChainAdapter, profile: ModelProfile) -> list[str]:
    return [token async for token in adapter.stream(profile, [Message("user", "hi")])]


async def _drain_with_tools(
    adapter: LangChainAdapter, profile: ModelProfile, tools: Sequence[ToolSpec]
) -> list[str]:
    return [
        token
        async for token in adapter.stream_with_tools(
            profile, [Message("user", "hi")], tools
        )
    ]


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


# ------------------------------------------------- MODEL-08: one EngineError --


def test_engine_error_is_the_class_the_port_declares() -> None:
    """The adapter raises the SAME class object the port declares — not a twin.

    This is the control that matters, and the only one that can catch the
    failure it guards. Two same-named classes would let this adapter raise one
    while the framework-free CLI's ``except`` clause names the other; the
    traceback would come straight back and every other test in both files would
    still be green, because none of them ever compares the two identities.
    """
    from paaf_llm._engine import EngineError as adapter_engine_error
    from paaf_llm.ports import EngineError as port_engine_error

    assert adapter_engine_error is port_engine_error
    assert EngineError is port_engine_error


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
    assert (
        LangChainAdapter.base_url(ModelProfile(provider="anthropic", model="c")) is None
    )


# ------------------------------------ MODEL-02: the openai_compatible provider --


def test_an_unauthenticated_openai_compatible_profile_binds_at_a_v1_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The test whose absence let BOTH of Gap 3's failures ship.

    ``openai_compatible`` was exercised only at the provider-string level, so
    nothing ever bound one — and two independent defects hid behind that: the
    schema could not express ``/v1`` (where vLLM, llama.cpp's server and LM
    Studio actually serve), and an unauthenticated local server could not bind at
    all because the OpenAI binding demands a credential the schema had no way to
    say was unnecessary.

    ``delenv`` is load-bearing: on a developer machine with ``OPENAI_API_KEY``
    exported, this would pass on an ambient credential and prove nothing about
    the declaration under test.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    profile = _openai_compatible()
    adapter = LangChainAdapter()  # deliberately NO secret store

    assert adapter.base_url(profile) == "http://192.168.1.20:8000/v1"
    assert adapter.model_kwargs(profile)["api_key"] == UNAUTHENTICATED_API_KEY

    bound = adapter.bind(profile)  # must not raise

    carried = _bound_base_url(bound)
    # Asserted FIRST, so a bound client exposing its base URL under some name
    # this file does not know cannot make the check below pass vacuously.
    assert carried is not None, f"no attribute in {_BASE_URL_ATTRS} on {type(bound)}"
    assert "http://192.168.1.20:8000/v1" in carried


def test_two_profiles_differing_only_in_the_auth_declaration_do_not_share_a_binding() -> (
    None
):
    """The auth flag is in the cache key, because it is derivable from nothing else.

    ``base_url`` already carries the path, but two profiles differing ONLY in
    ``endpoint_unauthenticated`` derive the same URL, the same provider string
    and the same temperature. Without the flag in the key they collide, and the
    second silently inherits the FIRST one's credential posture — an
    unauthenticated client answering for a profile the user gave a key.
    """
    adapter = LangChainAdapter(secret_store=_Secrets(local_key="sk-local"))
    no_auth = _openai_compatible()
    with_key = _openai_compatible(unauthenticated=False, api_key_ref="local_key")

    assert adapter.cache_key(no_auth) != adapter.cache_key(with_key)
    assert adapter.bind(no_auth) is not adapter.bind(with_key)
    assert adapter.bind(no_auth) is adapter.bind(no_auth)  # still cached per profile


def test_an_openai_compatible_profile_without_the_auth_declaration_still_needs_a_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEGATIVE CONTROL on the flag — the test that makes the flag load-bearing.

    Without this, a ``model_kwargs`` that supplied the placeholder
    UNCONDITIONALLY would satisfy every positive assertion above while sending an
    invented credential to every OpenAI-compatible endpoint, authenticated or
    not. Removing the declaration must reproduce the verifier's original
    ``Missing credentials`` failure, and here it does.

    ``delenv`` is what makes it deterministic: on a developer machine with
    ``OPENAI_API_KEY`` exported the bind would succeed on an ambient credential
    and the control would silently stop controlling anything.

    ``not isinstance(..., AdapterError)`` is the second load-bearing assertion. A
    missing credential is a configuration error, not a degraded provider; if it
    were the latter the ordered fallback chain would swallow it and let another
    model quietly answer for the profile the user configured.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    profile = _openai_compatible(unauthenticated=False)
    adapter = LangChainAdapter()  # no secret store, and the profile names no ref

    with pytest.raises(EngineError) as raised:
        adapter.bind(profile)

    assert not isinstance(raised.value, AdapterError)


def test_base_url_appends_nothing_the_user_did_not_declare() -> None:
    """NEGATIVE CONTROL on the path: PAAF adds no segment the user did not write.

    Plan 03-08 refused to append a ``/v1`` suffix on the user's behalf, and that
    decision survives the path becoming expressible: declaring it is now the
    user's to make, and an undeclared one stays undeclared.

    Asserted with ``==`` against the whole string rather than ``in`` or
    ``startswith``, so a trailing slash or a helpfully-invented ``/v1`` fails
    here instead of reaching a dialed URL.
    """
    profile = _openai_compatible(path=None)
    assert LangChainAdapter.base_url(profile) == "http://192.168.1.20:8000"


def test_two_profiles_differing_only_in_the_endpoint_path_do_not_share_a_binding() -> (
    None
):
    """MODEL-06 applied to the provider that had no binding coverage at all.

    The same reasoning that makes two LAN Ollama boxes two clients makes two
    paths two clients: ``/v1`` and the server's root are different servers as far
    as a request is concerned, and one cache entry answering for both would serve
    one endpoint's client to the other.
    """
    adapter = LangChainAdapter()
    with_path = _openai_compatible(path="/v1")
    without_path = _openai_compatible(path=None)

    assert adapter.cache_key(with_path) != adapter.cache_key(without_path)
    assert adapter.bind(with_path) is not adapter.bind(without_path)


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
        (
            anthropic.InternalServerError("boom", response=server, body=None),
            ServerError,
        ),
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
            [
                Message("system", "be kind"),
                Message("user", "hi"),
                Message("assistant", "yo"),
            ],
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


# -------------------------------------------- MESH-01: the tool-calling half --
#
# The framework's tool vocabulary appears in exactly one file, and this is the
# section that holds it to that. Everything below is decidable offline: the
# translation is a pure dict, the aggregation is a real ``AIMessageChunk`` sum,
# and only the streaming call is stubbed — the same bargain the rest of this
# module strikes.
#
# ``_to_framework_tools`` is reached through ``engine_module`` rather than
# imported by name because it is private to the adapter: the test may read it,
# but nothing should be able to mistake it for part of the package's surface.

#: A tool that takes no arguments — the shape EVERY handoff tool has, because
#: ``mesh.handoff_tools`` puts the target in the name and gives the model no
#: argument to get wrong. So the "empty parameters" case below is not an edge:
#: it is the only case Phase 4 actually ships.
_PING = ToolSpec(name="ping", description="Say pong.", parameters={})

#: A tool WITH parameters, so the translation is proven to pass a real schema
#: through untouched rather than to always emit the empty-object placeholder.
_ASK = ToolSpec(
    name="transfer_to_ada",
    description="Hand the conversation to Ada, who does maths.",
    parameters={"type": "object", "properties": {"reason": {"type": "string"}}},
)


def _handoff_chunks() -> tuple[Any, Any]:
    """Two chunks whose tool-call arguments are split MID-JSON, as a provider's are.

    This is the whole reason ``_tool_calls_of`` reads the aggregate: the split is
    inside the JSON literal, so neither chunk alone carries parseable arguments.
    """
    return (
        AIMessageChunk(
            content="",
            tool_call_chunks=[
                tool_call_chunk(
                    name="transfer_to_ada", args='{"rea', id="call_1", index=0
                )
            ],
        ),
        AIMessageChunk(
            content="",
            tool_call_chunks=[
                tool_call_chunk(name=None, args='son": "maths"}', id=None, index=0)
            ],
        ),
    )


def test_the_real_adapter_is_a_tool_calling_chat_adapter() -> None:
    """The moment the mesh stops being a test fixture (MESH-01, D-01).

    Until now only ``FakeAdapter`` satisfied the second protocol, so every mesh
    test in the suite proved something about the fake. The engine feature-detects
    with exactly this ``isinstance``, so this assertion is the difference between
    a handoff being reachable against a real provider and not being reachable at
    all.

    ``ChatAdapter`` is asserted alongside it because the second protocol EXTENDS
    the first (D-02): an adapter that gained tools and lost ``stream`` would
    satisfy neither the port nor Phase 3.
    """
    adapter = LangChainAdapter()
    assert isinstance(adapter, ToolCallingChatAdapter)
    assert isinstance(adapter, ChatAdapter)


def test_a_tool_spec_translates_to_one_openai_style_function_dict() -> None:
    """The ONE translation, asserted whole — no framework tool object is built.

    Compared with ``==`` against the entire structure rather than by probing
    keys, because an extra key is as much a leak of adapter opinion into the
    model's steering text as a missing one would be.
    """
    assert engine_module._to_framework_tools([_ASK]) == [
        {
            "type": "function",
            "function": {
                "name": "transfer_to_ada",
                "description": "Hand the conversation to Ada, who does maths.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                },
            },
        }
    ]


def test_a_tool_with_no_parameters_still_declares_an_empty_schema_object() -> None:
    """Empty parameters become ``{"type": "object", "properties": {}}``, not a gap.

    Every handoff tool has no arguments, so this is the shape the mesh actually
    ships. Emitting ``{}`` — or omitting the key — is the natural implementation
    and is rejected by real providers, which would make the entire mesh fail
    against a live model while every fake-driven test stayed green.
    """
    [translated] = engine_module._to_framework_tools([_PING])
    assert translated["function"]["parameters"] == {"type": "object", "properties": {}}


def test_the_translation_preserves_the_offered_order() -> None:
    """``peers`` order is the user's, and it survives the crossing (MESH-01)."""
    names = [
        entry["function"]["name"]
        for entry in engine_module._to_framework_tools([_ASK, _PING])
    ]
    assert names == ["transfer_to_ada", "ping"]


async def test_offering_no_tools_never_calls_bind_tools() -> None:
    """An empty ``tools`` is byte-identical to Phase 3 (the port says so).

    Not merely "the same output" — the same CALL. A ``bind_tools([])`` on the
    no-peer path would put every single-agent user behind the exact provider
    behaviour Pitfall 3 warns about, and an output-only assertion could not tell
    the difference.
    """
    adapter = LangChainAdapter()
    model = _StubModel(chunks=(AIMessageChunk(content="hi"),))
    _stub(adapter, model)

    assert await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), ()) == [
        "hi"
    ]
    assert model.bound_tools == []
    assert adapter.last_tool_calls() == ()


async def test_offered_tools_reach_bind_tools_translated_once() -> None:
    """The offered specs arrive at the provider as the translated dicts, once."""
    adapter = LangChainAdapter()
    model = _StubModel(chunks=(AIMessageChunk(content="hi"),))
    _stub(adapter, model)

    await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_ASK, _PING])
    assert model.bound_tools == [engine_module._to_framework_tools([_ASK, _PING])]


def test_tool_calls_are_read_off_the_aggregate_never_off_a_chunk() -> None:
    """T-04-16: a mid-stream read yields a call whose arguments are simply GONE.

    Both halves are asserted deliberately. The aggregate carries
    ``{"reason": "maths"}``; the first chunk on its own carries ``{}`` — the
    framework cannot parse ``'{"rea'`` and does not pretend to. A per-chunk
    implementation would therefore not fail loudly, it would hand the mesh a
    plausible-looking ``ToolCall`` with its arguments silently dropped.
    """
    first, second = _handoff_chunks()

    assert LangChainAdapter._tool_calls_of(first) == (
        ToolCall(name="transfer_to_ada", arguments={}, call_id="call_1"),
    )
    assert LangChainAdapter._tool_calls_of(first + second) == (
        ToolCall(
            name="transfer_to_ada", arguments={"reason": "maths"}, call_id="call_1"
        ),
    )


def test_an_aggregate_with_no_tool_calls_reports_an_empty_tuple() -> None:
    """``()``, never ``None`` — an ordinary answered turn is the common case.

    ``None`` is also covered: it is what ``aggregate`` still is when a provider
    yielded nothing at all, and an ``AttributeError`` on that path would turn a
    silent provider into a crash.
    """
    assert LangChainAdapter._tool_calls_of(AIMessageChunk(content="hi")) == ()
    assert LangChainAdapter._tool_calls_of(None) == ()


def test_a_fresh_adapter_reports_no_tool_calls() -> None:
    """Nothing streamed yet is an empty tuple, not an attribute error."""
    assert LangChainAdapter().last_tool_calls() == ()


async def test_stream_with_tools_publishes_the_call_after_the_stream_drains() -> None:
    """The end-to-end seam: prose streams, and the call lands once aggregated.

    Deliberately interleaves text with the split tool-call fragments, because
    that is D-11's pre-handoff-prose case and the ordering is what would break if
    the publish moved inside the loop.
    """
    adapter = LangChainAdapter()
    first, second = _handoff_chunks()
    _stub(
        adapter,
        _StubModel(
            chunks=(
                AIMessageChunk(content="Let me "),
                first,
                AIMessageChunk(content="ask Ada."),
                second,
            )
        ),
    )

    tokens = await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_ASK])

    assert tokens == ["Let me ", "ask Ada."]
    # T-04-18: the framework's TextAccessor is a str SUBCLASS, so an `isinstance`
    # check here would pass while a framework type crossed the port.
    assert [type(token) for token in tokens] == [str, str]
    assert adapter.last_tool_calls() == (
        ToolCall(
            name="transfer_to_ada", arguments={"reason": "maths"}, call_id="call_1"
        ),
    )


async def test_stream_with_tools_still_publishes_usage() -> None:
    """The tool path must not lose the usage seam it was copied from."""
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

    await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_PING])
    usage = adapter.last_usage()
    assert (usage.prompt_tokens, usage.completion_tokens) == (11, 5)


async def test_stream_with_tools_drops_empty_chunks_like_stream_does() -> None:
    """The first-token deadline must measure real content on this path too."""
    adapter = LangChainAdapter()
    _stub(
        adapter,
        _StubModel(chunks=(AIMessageChunk(content=""), AIMessageChunk(content="hi"))),
    )
    assert await _drain_with_tools(
        adapter, _ollama("qwen3", "192.168.1.10"), [_PING]
    ) == ["hi"]


async def test_a_degraded_provider_on_the_tool_path_still_translates() -> None:
    """The ``_translate`` boundary carries over verbatim — the fallback loop needs it.

    Without this the mesh path would raise a framework exception straight through
    the port, and the fallback chain — which classifies by reading ``.reason`` —
    would not recognise a hop it handles perfectly well on the Phase-3 path.
    """
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(error=ConnectError("all connection attempts failed")))

    with pytest.raises(ConnectionFailed) as raised:
        await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_PING])
    assert raised.value.reason is ConnectionFailed.reason


async def test_a_bind_tools_failure_is_a_config_error_not_a_degraded_provider() -> None:
    """A tool surface the provider refuses is a configuration problem.

    ``not isinstance(..., AdapterError)`` is the load-bearing half. A model that
    cannot accept tools will not accept them from the next profile either, so
    degrading here would walk the whole fallback chain, print ``↳ fell back``
    three times, and end on a generic failure that names nothing the user can
    fix.
    """
    adapter = LangChainAdapter()
    _stub(
        adapter,
        _StubModel(bind_tools_error=TypeError("this model does not support tools")),
    )

    with pytest.raises(EngineError) as raised:
        await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_PING])

    assert not isinstance(raised.value, AdapterError)
    assert "does not support tools" in str(raised.value)


async def test_a_bind_tools_failure_is_never_reclassified_as_a_transport_error() -> (
    None
):
    """NEGATIVE CONTROL on the clause above — and on the obvious implementation.

    Routing the bind through ``_translate`` (which is what the surrounding code
    does for the STREAM) reads as the consistent choice and is wrong here: the
    classifier reads exception TYPE NAMES, so a provider binding that happens to
    raise something named like a transport failure would be reported as a
    degraded provider and swallowed by the fallback loop. Binding contacts
    nobody, exactly as ``bind()`` does not — so it is raised the way ``bind()``
    raises, unconditionally as an ``EngineError``.
    """
    adapter = LangChainAdapter()
    _stub(adapter, _StubModel(bind_tools_error=ConnectError("refused")))

    with pytest.raises(EngineError) as raised:
        await _drain_with_tools(adapter, _ollama("qwen3", "192.168.1.10"), [_PING])

    assert not isinstance(raised.value, AdapterError)
    assert classify(ConnectError("refused")) is ConnectionFailed  # it WOULD classify


async def test_a_resolved_key_never_appears_in_a_bind_tools_failure() -> None:
    """T-04-15: the new raise site keeps T-03-04's scrubber on it.

    A provider echoing the credential it rejected is the one realistic leak, and
    a new raise site that skipped ``_scrub`` would reopen it in a place the
    Phase-3 test cannot see.
    """
    secret = "sk-super-secret-value"
    adapter = LangChainAdapter(secret_store=_Secrets(cloud=secret))
    profile = ModelProfile(provider="anthropic", model="c", api_key_ref="cloud")
    adapter.api_key(profile)  # resolve it, so the scrubber knows the value

    _stub(adapter, _StubModel(bind_tools_error=RuntimeError(f"bad key: {secret}")))
    with pytest.raises(EngineError) as raised:
        await _drain_with_tools(adapter, profile, [_PING])

    assert secret not in str(raised.value)
    assert "***" in str(raised.value)


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


def test_the_cli_default_adapter_forwards_the_store_to_the_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression test for the exact line Gap 1 blamed — and for a shape of miss.

    Both SIDES of this seam were already covered and the seam itself was not.
    Every test in ``test_inspector.py`` replaces ``cli._default_adapter``
    wholesale (``inject`` and ``spy_adapter_factory`` both do), and every other
    test in this section calls ``build_engine_adapter`` directly. So the one line
    that joins them — ``_default_adapter``'s own body — was executed by nothing,
    and it was the line that silently passed one argument too few. That is
    precisely how Gap 1 shipped past a green suite.

    A source grep proves the argument is present today and then goes cold. This
    test is what stays red if someone drops it again.

    ``monkeypatch.setattr`` targets the attribute on the MODULE, not the name
    imported into this file: ``_default_adapter``'s import is lazy and in-function
    (SC#1), so it re-resolves ``build_engine_adapter`` off the module on every
    call — which is exactly what makes it interceptable here.
    """
    sentinel = object()
    recorded: dict[str, Any] = {}

    def recorder(config: LlmConfig, *, secret_store: Any = None) -> Any:
        recorded["config"] = config
        recorded["secret_store"] = secret_store
        return sentinel

    monkeypatch.setattr(engine_module, "build_engine_adapter", recorder)

    config = LlmConfig(
        active_profile="a", profiles={"a": _ollama("qwen3", "192.168.1.10")}
    )
    store = _Secrets(anthropic_key="sk-live-value")

    returned = cli._default_adapter(config, secret_store=store)

    assert recorded["secret_store"] is store
    assert recorded["config"] is config
    assert returned is sentinel


def _cloud_with_a_ref() -> tuple[LlmConfig, ModelProfile]:
    """An Anthropic profile naming a key, plus the config that activates it."""
    profile = ModelProfile(
        provider="anthropic", model="claude-sonnet-4-5", api_key_ref="anthropic_key"
    )
    return LlmConfig(active_profile="cloud", profiles={"cloud": profile}), profile


def test_the_factory_carries_a_secret_store_through_to_key_resolution() -> None:
    """The store handed to the FACTORY reaches key resolution (CORE-04).

    Asserted through ``build_engine_adapter`` rather than by constructing
    ``LangChainAdapter`` directly, because the direct construction is already
    covered by ``test_api_key_is_resolved_by_reference_not_read_from_config`` —
    and the seam that actually broke was the factory call, not the class.
    """
    config, profile = _cloud_with_a_ref()
    adapter = build_engine_adapter(
        config, secret_store=_Secrets(anthropic_key="sk-live-value")
    )

    assert adapter.api_key(profile) == "sk-live-value"
    assert adapter.model_kwargs(profile)["api_key"] == "sk-live-value"


def test_the_factory_without_a_store_fails_as_a_config_error() -> None:
    """The verifier's reproduced failure, encoded as a permanent test.

    This is the exact case that blocked SC#2 twice:
    ``EngineError: could not bind 'anthropic:claude-sonnet-4-5': profile declares
    api_key_ref 'anthropic_key' but no secret store was provided``.

    ``not isinstance(..., AdapterError)`` is the load-bearing assertion. If a
    missing credential were a degraded provider, the fallback chain would swallow
    it and quietly let another model answer for the cloud profile the user
    configured — leaving them believing it works.
    """
    config, profile = _cloud_with_a_ref()
    adapter = build_engine_adapter(config)

    with pytest.raises(EngineError) as raised:
        adapter.api_key(profile)

    assert not isinstance(raised.value, AdapterError)
    assert "anthropic_key" in str(raised.value)
    assert "sk-" not in str(raised.value)


def test_build_engine_adapter_is_the_factory_the_cli_imports() -> None:
    """Pins the factory NAME and its optional ``secret_store`` keyword.

    ``cli._default_adapter`` imports exactly this name, lazily, and supplies
    ``secret_store`` — which is how a profile's ``api_key_ref`` gets resolved from
    a real store rather than from the provider SDK's own environment variable.

    That the CLI *actually* supplies it is proven by
    ``test_the_cli_default_adapter_forwards_the_store_to_the_factory``, not here:
    this test builds the adapter itself, so it would pass unchanged against a CLI
    that had dropped the argument. That gap is what Gap 1 was.
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
