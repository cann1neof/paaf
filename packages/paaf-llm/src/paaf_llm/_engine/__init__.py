# SPDX-License-Identifier: Apache-2.0
"""MODEL-01/02/06: the real framework-backed adapter — and the ONLY langchain site.

This subpackage is where the swappability promise is cashed in. Everything else
in ``paaf_llm`` is written against :class:`~paaf_llm.ports.ChatAdapter`; this
module is the single file that knows an agent framework exists. Replacing the
framework means rewriting this file and nothing else, which is the property
MODEL-08 exists to preserve.

**The permitted-import edge, stated accurately.** ``.importlinter``'s
``langchain-confined-to-adapter`` contract forbids ``langchain``, ``langgraph``,
``langchain_core``, ``langchain_mcp_adapters``, and the three provider bindings
framework-wide, then whitelists exactly two importers: ``paaf_llm._engine`` and
``paaf_llm._engine.**``. This docstring previously advertised the shorthand
``paaf_llm._engine.* -> langchain*``; plan 03-03 established that spelling is
wrong twice over, and it is corrected here so the marker does not keep teaching
an expression that fails:

* import-linter wildcards replace a WHOLE module segment, so ``langchain*`` is a
  ``ValidationError`` rather than a prefix match — each forbidden module is named
  in full;
* ``*``/``**`` match STRICT descendants, so ``paaf_llm._engine.**`` would not
  cover ``paaf_llm._engine`` itself — which is this file, where the adapter's own
  imports live. Both names are therefore listed.

**Lazy, and optional.** ``langchain`` is an optional ``[engine]`` extra, never a
base dependency. Nothing here imports it at module scope: the framework is pulled
in inside :func:`_framework`, on the first bind. What this module *does* check at
import time is whether the extra is installed at all (via
:func:`importlib.util.find_spec`, which imports nothing) — because
:func:`paaf_llm.cli._default_adapter` wraps its ``from ._engine import
build_engine_adapter`` in ``except ImportError`` to print an actionable "install
the extra" message. Without this probe that handler could never fire, and a user
without the extra would get a bare ``ModuleNotFoundError`` mid-conversation
instead.

**No HTTP client.** This adapter never imports ``httpx`` (or ``requests``, or
``aiohttp``). The provider bindings own the network client, so the framework's
``no-network-client-in-framework`` contract stays literally true of PAAF source
rather than true-with-an-exception (RESEARCH Pitfall 3).

**Failure translation is the reason this file exists.** The engine's fallback
loop (:mod:`paaf_llm.agent`) classifies a hop by reading ``AdapterError.reason``
and never by matching a foreign exception type. So every transport failure a
provider can produce is mapped here onto exactly one of the four PAAF errors —
structurally, by reading an HTTP status and the exception chain, rather than by
importing each provider's exception classes (which would drag three optional
dependencies into this module's import graph to do a job duck-typing does).

**What is deliberately NOT translated.** An ``AdapterError`` means "this provider
degraded, try the next one". A missing API key, a model name the provider does
not have, or a bug in this adapter is not a degraded provider — it is a
configuration error the user must fix. Translating those into a fallback reason
would print ``↳ fell back to cloud (connection)`` at someone whose real problem
is a typo, which is precisely the kind of hidden behavior this project refuses.
They surface as :class:`~paaf_llm.ports.EngineError`, which is PAAF-typed (so no
framework exception escapes the port) and pointedly not an ``AdapterError`` (so
the fallback loop cannot swallow it as one more plausible hop). That class is
DEFINED IN THE PORT, not here, and is merely imported and re-exported by this
module. The placement is deliberate: this package is unimportable without the
optional extra, so a framework-free caller — :mod:`paaf_llm.cli` — could not name
a locally-defined class in an ``except`` clause, and the single most likely
first-run failure (a credential that will not resolve) would reach the user as a
traceback. Defining it in the port is what makes it catchable.

**Secrets.** An API key is fetched by REFERENCE at bind time
(``SecretStore.get(profile.api_key_ref)``, CORE-04) and never read from YAML. Any
resolved value is also scrubbed from every message this module raises, because
the one place a key can realistically leak is a provider echoing the credential
it rejected back inside an error string (T-03-04).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

from ..ports import (
    ConnectionFailed,
    EngineError,
    Message,
    RateLimited,
    RequestTimedOut,
    ServerError,
    Usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from ..agent import SecretResolver
    from ..ports import AdapterError, ChatAdapter
    from ..profiles import LlmConfig, ModelProfile

# Checked with find_spec rather than an import: this must not load langchain (the
# whole point of the lazy adapter), but it MUST fail at *import* of this module
# when the extra is absent, because that is the only moment cli._default_adapter
# can catch it and say something useful. find_spec only consults path finders.
if find_spec("langchain") is None:  # pragma: no cover - exercised by the wheel job
    raise ImportError(
        "paaf_llm._engine needs the optional agent framework, which is not "
        "installed. Install it with:  pip install 'paaf-llm[engine]'"
    )

#: ``ModelProfile.provider`` -> the ``init_chat_model`` provider prefix. The
#: mapping is explicit rather than derived because the two vocabularies are
#: deliberately different: ``openai_compatible`` says what the profile MEANS (any
#: endpoint speaking the OpenAI wire format — vLLM, llama.cpp, LM Studio, a
#: cloud), while ``openai:`` is merely the binding that speaks it.
PROVIDER_STRINGS: dict[str, str] = {
    "ollama": "ollama",
    "openai_compatible": "openai",
    "anthropic": "anthropic",
}

#: Providers whose models are loaded from disk on first use and therefore have a
#: cold-start cost worth paying at :meth:`LangChainAdapter.preload` time. A hosted
#: provider has no cold load, so preloading one would spend the user's tokens and
#: money on every ``paaf chat`` start to warm something that was never cold.
PRELOADABLE_PROVIDERS: frozenset[str] = frozenset({"ollama"})

#: The throwaway prompt :meth:`LangChainAdapter.preload` sends to force a cold
#: model off disk. Deliberately not the empty string: several providers reject an
#: empty user turn outright, which would make warmup a silent no-op exactly where
#: it is needed most.
PRELOAD_MESSAGE = Message("user", "ping")

#: PAAF role -> the framework message class attribute name. Kept as strings so
#: this table can live at module scope without importing the framework.
_ROLE_TO_MESSAGE_CLASS: dict[str, str] = {
    "system": "system",
    "user": "human",
    "assistant": "ai",
}

#: Substrings that identify a failure class from an exception's TYPE NAME, used
#: when no HTTP status is available. Duck-typing beats importing three provider
#: SDKs here: `ollama.ResponseError`, `openai.APITimeoutError`, and
#: `httpx.ConnectError` are all recognized without this module depending on any
#: of them. Order matters — see :func:`_classify_one`.
_RATE_LIMIT_MARKERS = ("ratelimit", "toomanyrequests", "overloaded")
_SERVER_MARKERS = (
    "internalserver",
    "serviceunavailable",
    "badgateway",
    "servererror",
    "apistatuserror",
)
_TIMEOUT_MARKERS = ("timeout", "timedout")
_CONNECTION_MARKERS = ("connect", "unreachable", "resolution", "dnserror")

#: Attributes an HTTP status may hide behind across the provider SDKs.
_STATUS_ATTRS = ("status_code", "status", "http_status")

#: How far to walk an exception's ``__cause__``/``__context__`` chain. Bounded
#: because a chain can be cyclic and this runs on a failure path.
_MAX_CHAIN_DEPTH = 12


@dataclass(frozen=True, slots=True)
class _Framework:
    """The three framework symbols this adapter uses, resolved once, lazily.

    Bundling them in one frozen record keeps every ``langchain*`` import inside
    :func:`_framework` — so "which line imports the framework?" has exactly one
    answer, and the import-linter whitelist covers exactly one call site.
    """

    init_chat_model: Any
    message_classes: dict[str, Any]


_FRAMEWORK: _Framework | None = None


def _framework() -> _Framework:
    """Import the agent framework on first use and cache it.

    THE lazy import site. At module scope these imports would make ``langchain``
    a hard dependency of merely *touching* the adapter package, which the
    ``[engine]``-extra design (SC#1) exists to prevent.
    """
    global _FRAMEWORK
    if _FRAMEWORK is None:
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        _FRAMEWORK = _Framework(
            init_chat_model=init_chat_model,
            message_classes={
                "system": SystemMessage,
                "human": HumanMessage,
                "ai": AIMessage,
            },
        )
    return _FRAMEWORK


def _status_of(exc: BaseException) -> int | None:
    """Return the HTTP status carried by ``exc``, or ``None``.

    Reads the attribute names the provider SDKs actually use (``ollama``'s
    ``status_code``, ``openai``/``anthropic``'s ``status_code``, and a nested
    ``response.status_code``). Anything non-integer is ignored rather than
    coerced — a truthy-but-meaningless attribute must not become a 5xx.
    """
    candidates: list[Any] = [getattr(exc, name, None) for name in _STATUS_ATTRS]
    response = getattr(exc, "response", None)
    if response is not None:
        candidates.append(getattr(response, "status_code", None))
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _classify_one(exc: BaseException) -> type[AdapterError] | None:
    """Map ONE exception onto a PAAF adapter error, or ``None`` if unrecognized.

    Status wins over name because it is the provider's own statement about what
    happened. Among the name checks, rate-limit and server precede timeout and
    connection, and timeout precedes connection, because the SDK hierarchies
    genuinely nest that way — ``openai.APITimeoutError`` subclasses
    ``APIConnectionError``, and ``httpx.ConnectTimeout`` is both — so testing
    connection first would silently reclassify every timeout.
    """
    status = _status_of(exc)
    if status == 429:
        return RateLimited
    if status is not None and 500 <= status < 600:
        return ServerError

    name = type(exc).__name__.lower()
    if any(marker in name for marker in _RATE_LIMIT_MARKERS):
        return RateLimited
    if any(marker in name for marker in _SERVER_MARKERS):
        return ServerError
    if any(marker in name for marker in _TIMEOUT_MARKERS) or isinstance(
        exc, TimeoutError
    ):
        return RequestTimedOut
    if any(marker in name for marker in _CONNECTION_MARKERS) or isinstance(
        exc, (ConnectionError, OSError)
    ):
        return ConnectionFailed
    return None


def _chain(exc: BaseException) -> list[BaseException]:
    """Return ``exc`` followed by its causes, bounded and cycle-safe.

    Providers wrap: ``ollama.ResponseError`` may arrive with an ``httpx``
    transport error as its ``__cause__``, and the useful signal is sometimes only
    on the inner one. Walking the chain is what makes the classifier work against
    wrappers it has never seen.
    """
    seen: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and len(seen) < _MAX_CHAIN_DEPTH:
        if any(current is item for item in seen):
            break
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def classify(exc: BaseException) -> type[AdapterError] | None:
    """Return the PAAF adapter error ``exc`` means, or ``None`` if it means none.

    ``None`` is a real answer, not a fallback-to-guessing: it says "this is not
    one of the four degraded triggers", and the caller turns it into an
    :class:`EngineError` rather than inventing a reason.
    """
    for link in _chain(exc):
        translated = _classify_one(link)
        if translated is not None:
            return translated
    return None


class LangChainAdapter:
    """A :class:`~paaf_llm.ports.ChatAdapter` backed by the real agent framework.

    One instance serves every profile: models are built per profile and cached,
    so a fallback chain does not re-construct a client on every turn. The cache
    key includes the endpoint and model, which is what makes MODEL-06 work — two
    Ollama profiles at ``192.168.1.10`` and ``192.168.1.11`` are two distinct
    bindings with two distinct ``base_url``s, not one shared client.
    """

    def __init__(self, secret_store: SecretResolver | None = None) -> None:
        self._secret_store = secret_store
        self._models: dict[tuple[str, ...], Any] = {}
        self._last_usage = Usage()
        #: Resolved key values, kept ONLY so they can be scrubbed out of error
        #: text (T-03-04). They are already in memory inside the provider client;
        #: holding the same string here adds no exposure and buys a redaction.
        self._secret_values: set[str] = set()

    # ------------------------------------------------------------- mapping --

    @staticmethod
    def provider_string(profile: ModelProfile) -> str:
        """Return the ``init_chat_model`` string for ``profile`` (e.g. ``ollama:qwen3``).

        Raises:
            EngineError: the schema declares a provider this adapter cannot bind.
                That is unreachable today (``ModelProfile.provider`` is a
                ``Literal``) and is exactly why it is checked: the guard exists
                for the day someone widens the Literal and forgets this table.
        """
        prefix = PROVIDER_STRINGS.get(profile.provider)
        if prefix is None:
            raise EngineError(
                f"no binding for provider {profile.provider!r}; "
                f"this adapter maps {sorted(PROVIDER_STRINGS)}"
            )
        return f"{prefix}:{profile.model}"

    @staticmethod
    def base_url(profile: ModelProfile) -> str | None:
        """Return ``profile``'s declared endpoint as a URL, or ``None``.

        ``None`` means "use the provider's own default", which is the honest
        reading of a profile that declared no host/port — a cloud profile is not
        hiding an endpoint, it simply has none of PAAF's to declare (CORE-05).
        The URL is built from the ``paaf_core`` ``Endpoint`` that
        ``ModelProfile.endpoint()`` returns, so the same value Phase-9's offline
        check classifies is the one actually dialed.

        Note the schema's current limit: ``Endpoint`` carries scheme/host/port and
        no PATH, so an OpenAI-compatible server that serves under ``/v1`` cannot
        be fully addressed yet. This method does NOT guess a suffix — silently
        rewriting a user's declared endpoint is the kind of hidden behavior the
        project refuses. See the plan summary's deferred note.
        """
        endpoint = profile.endpoint()
        if endpoint is None:
            return None
        return f"{endpoint.scheme}://{endpoint.host}:{endpoint.port}"

    def api_key(self, profile: ModelProfile) -> str | None:
        """Resolve ``profile``'s API key BY REFERENCE, or ``None`` if none is named.

        The key value never appears in the config tree — ``api_key_ref`` is the
        NAME of a ``paaf_core`` SecretStore entry (CORE-04). A profile that names
        a reference nobody can resolve is a configuration error and is raised as
        one: falling back would leave the user believing a cloud profile works.

        Raises:
            EngineError: ``api_key_ref`` is set but no store was provided, or the
                store has no such key. The message names the REFERENCE only.
        """
        ref = profile.api_key_ref
        if ref is None:
            return None
        if self._secret_store is None:
            raise EngineError(
                f"profile declares api_key_ref {ref!r} but no secret store was "
                f"provided to the adapter; the key value is never read from YAML"
            )
        value = self._secret_store.get(ref)
        if value is None:
            raise EngineError(f"secret store has no key named {ref!r}")
        self._secret_values.add(value)
        return value

    def model_kwargs(self, profile: ModelProfile) -> dict[str, Any]:
        """Return the keyword arguments ``profile`` contributes to its binding.

        ``temperature`` rides along because it is the user's setting and silently
        dropping it would make a documented knob do nothing.
        """
        kwargs: dict[str, Any] = {"temperature": profile.temperature}
        base_url = self.base_url(profile)
        if base_url is not None:
            kwargs["base_url"] = base_url
        key = self.api_key(profile)
        if key is not None:
            kwargs["api_key"] = key
        return kwargs

    @staticmethod
    def cache_key(profile: ModelProfile) -> tuple[str, ...]:
        """Return the identity of ``profile``'s binding, for the model cache.

        EVERY field that changes the binding is in the key, and the key is built
        from the profile rather than from the resolved kwargs, so the secret VALUE
        never becomes a dict key: ``api_key_ref`` (the name) distinguishes two
        profiles using different credentials without holding either.

        Keying on the provider string alone — or on provider plus ``base_url`` —
        looks sufficient and is not: two Anthropic profiles naming the same model
        both declare no endpoint, so they would collide and the second would
        silently inherit the first's temperature and credential.
        """
        return (
            LangChainAdapter.provider_string(profile),
            LangChainAdapter.base_url(profile) or "",
            repr(profile.temperature),
            profile.api_key_ref or "",
        )

    def bind(self, profile: ModelProfile) -> Any:
        """Return the cached chat model for ``profile``, building it on first use.

        Building is offline — no provider is contacted — so a failure here is a
        configuration problem (an unresolvable key, a rejected argument), never a
        degraded provider. It is raised as :class:`EngineError` accordingly.
        """
        provider_string = self.provider_string(profile)
        cache_key = self.cache_key(profile)
        cached = self._models.get(cache_key)
        if cached is not None:
            return cached
        try:
            model = _framework().init_chat_model(
                provider_string, **self.model_kwargs(profile)
            )
        except Exception as exc:  # re-raised as a PAAF type below
            raise EngineError(
                f"could not bind {provider_string!r}: {self._scrub(str(exc))}"
            ) from exc
        self._models[cache_key] = model
        return model

    # ------------------------------------------------------------ streaming --

    def _to_framework_messages(self, messages: Sequence[Message]) -> list[Any]:
        """Map PAAF :class:`Message` values onto the framework's message classes."""
        classes = _framework().message_classes
        return [
            classes[_ROLE_TO_MESSAGE_CLASS[message.role]](content=message.content)
            for message in messages
        ]

    def _scrub(self, text: str) -> str:
        """Remove any resolved secret value from ``text`` (T-03-04).

        The adapter never formats a key into a message itself; this guards the
        case it cannot control — a provider echoing the credential it rejected
        back inside its own error string, which would then reach a log or the
        user's terminal through the exception this module raises.
        """
        for value in self._secret_values:
            if value and value in text:
                text = text.replace(value, "***")
        return text

    def _translate(self, exc: Exception) -> Exception:
        """Return the PAAF exception ``exc`` should surface as.

        One of the four :class:`~paaf_llm.ports.AdapterError` subclasses when the
        failure is a recognizable transport/status degradation, and an
        :class:`EngineError` otherwise. Either way no framework exception crosses
        the port, and either way the message is scrubbed of resolved secrets.
        """
        detail = self._scrub(f"{type(exc).__name__}: {exc}")
        translated = classify(exc)
        if translated is not None:
            return translated(detail)
        return EngineError(f"provider call failed and is not a degraded provider: {detail}")

    @staticmethod
    def _usage_of(aggregate: Any) -> Usage:
        """Read token counts off the AGGREGATED stream, never off a chunk.

        SPIKE-05: Ollama publishes usage on roughly one chunk in 334, so a
        per-chunk read reports ``None`` almost always. ``None`` survives when the
        provider genuinely said nothing — that is information the user should
        see, and inventing a zero would make the trace lie (see
        :class:`~paaf_llm.ports.Usage`).
        """
        metadata = getattr(aggregate, "usage_metadata", None) or {}
        return Usage(
            prompt_tokens=metadata.get("input_tokens"),
            completion_tokens=metadata.get("output_tokens"),
        )

    async def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        """Stream ``profile``'s reply as plain ``str`` tokens.

        Raises:
            AdapterError: one of the four subclasses when the provider degrades.
            EngineError: a configuration problem, or a failure that is not one of
                the four degraded triggers.
        """
        model = self.bind(profile)
        framework_messages = self._to_framework_messages(messages)
        aggregate: Any = None

        try:
            async for chunk in model.astream(framework_messages):
                aggregate = chunk if aggregate is None else aggregate + chunk
                # str() is not decoration: `.text` is a framework TextAccessor
                # (a str subclass), and letting it cross the port would leak a
                # framework type through a PAAF-typed stream (MODEL-08).
                text = str(getattr(chunk, "text", "") or "")
                if text:
                    # Empty chunks are dropped so the engine's first-token
                    # deadline measures real content: yielding "" would satisfy
                    # the budget with nothing and mask a genuinely slow provider.
                    yield text
        except Exception as exc:  # translated to a PAAF type just below
            # GeneratorExit and CancelledError are BaseException and pass
            # through untouched, which is what lets the engine's timeout
            # aclose() this generator cleanly.
            raise self._translate(exc) from exc

        self._last_usage = self._usage_of(aggregate)

    def last_usage(self) -> Usage:
        """Return the usage published by the most recently completed stream."""
        return self._last_usage

    # -------------------------------------------------------------- warmup --

    async def preload(self, profile: ModelProfile) -> None:
        """Pay ``profile``'s cold-load cost now so the turn deadline sees a warm model.

        Called by :meth:`paaf_llm.agent.Agent.warmup`. Two deliberate limits:

        * Only providers in :data:`PRELOADABLE_PROVIDERS` are actually exercised.
          A hosted model has no cold load, so warming one would spend the user's
          tokens on every session start for no latency gain.
        * Every failure is swallowed. Warmup is an optimization; a provider that
          is down at startup must not stop the session, because the fallback loop
          already handles exactly that at turn time — and reporting it here would
          report it twice.
        """
        if profile.provider not in PRELOADABLE_PROVIDERS:
            return
        try:
            model = self.bind(profile)
            # One token is enough to force the load, and stopping at the first
            # chunk keeps the cost at one token rather than a whole reply.
            async for _chunk in model.astream(
                self._to_framework_messages([PRELOAD_MESSAGE])
            ):
                break
        except Exception:  # noqa: BLE001 - warmup is best-effort; see the docstring
            return


def build_engine_adapter(
    config: LlmConfig, secret_store: SecretResolver | None = None
) -> ChatAdapter:
    """Return the real adapter for ``config`` — the factory the CLI imports lazily.

    :func:`paaf_llm.cli._default_adapter` calls exactly this, inside a function,
    so ``import paaf_llm.cli`` stays framework-free (SC#1).

    Every declared profile's provider is checked up front. The check cannot fail
    against today's schema, and that is the point: ``ModelProfile.provider`` is a
    ``Literal`` whose members must stay in step with
    :data:`PROVIDER_STRINGS`, and the day someone widens the Literal this raises
    at startup naming the offending profile instead of at the first turn that
    happens to use it.
    """
    adapter = LangChainAdapter(secret_store=secret_store)
    for name, profile in config.profiles.items():
        try:
            LangChainAdapter.provider_string(profile)
        except EngineError as exc:
            raise EngineError(f"profile {name!r}: {exc}") from exc
    return adapter


__all__ = [
    "PRELOADABLE_PROVIDERS",
    "PRELOAD_MESSAGE",
    "PROVIDER_STRINGS",
    "EngineError",
    "LangChainAdapter",
    "build_engine_adapter",
    "classify",
]
