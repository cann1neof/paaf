# SPDX-License-Identifier: Apache-2.0
"""CORE-05: the common network-endpoint declaration interface (SC#4, endpoint half).

Offline enforcement must be *architectural*, not a scattered set of ``if offline:``
checks. Every network-touching component declares its endpoints through one
interface (:class:`NetworkComponent`); an :class:`Endpoint` can classify itself
LAN vs non-LAN with **no DNS lookup**; an :class:`EndpointRegistry` aggregates
declarations so a single caller can enumerate everything.

Phase 2 ships the interface, registry, and classification. Phase 9's APP-08
daemon iterates the registry and refuses to start on any ``non_lan_endpoints()``.

``is_lan()`` classifies numeric addresses with the stdlib :mod:`ipaddress` module
and hostnames with a suffix check only — it never resolves a name, so it is safe
under the suite-wide ``--disable-socket`` default (threat T-02-16).
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Hostname suffixes / names that are LAN by construction without any resolution.
_LAN_HOSTNAME_SUFFIXES = (".local",)
_LAN_HOSTNAMES = frozenset({"localhost"})


@dataclass(frozen=True)
class Endpoint:
    """A single network endpoint a component intends to reach or expose.

    ``host`` may be a numeric address (IPv4/IPv6) or a hostname. Classification
    is purely lexical/numeric — no socket is opened and no name is resolved.
    """

    host: str
    port: int
    scheme: str
    #: The URL path this component serves under, empty by default and appended
    #: VERBATIM by :meth:`url`. An OpenAI-compatible server commonly serves at
    #: ``/v1``; PAAF never guesses that suffix, it only carries the one the user
    #: declared. Classification does not read this field — see :meth:`is_lan`.
    #:
    #: Declared LAST, and defaulted, because existing callers construct
    #: ``Endpoint(host, port, scheme)`` positionally; an inserted field would
    #: silently reassign their arguments.
    path: str = ""

    def url(self) -> str:
        """Return this endpoint as one URL string: scheme, host, port, path.

        The assembly lives here rather than in each caller so there is exactly
        one answer to "what URL does this endpoint mean" — and so the value a
        component dials is character-for-character the value the registry (and
        Phase-9's APP-08 offline check) classifies.

        ``path`` is appended exactly as declared: nothing is stripped, prepended,
        rewritten, or guessed. A URL segment PAAF invented would be one the user
        never wrote, which is the hidden behavior this project refuses. A path
        that is malformed is a config error the DECLARING schema rejects at load,
        not something this method repairs.
        """
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"

    def is_lan(self) -> bool:
        """Return ``True`` when this endpoint is provably LAN-local offline.

        LAN means: an IP loopback (127.0.0.0/8, ``::1``), an RFC1918 / private
        range (10/8, 172.16/12, 192.168/16 and their IPv6 analogues), a
        link-local address (169.254/16, ``fe80::/10``), or a hostname that is
        ``localhost`` or ends in ``.local``. Everything else — including any
        public IP or resolvable public hostname — is treated as non-LAN.
        """
        host = self.host.strip()
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            # Not a numeric address: a hostname. Classify by suffix ONLY —
            # resolving it would require a socket and break offline-safety.
            lowered = host.lower()
            if lowered in _LAN_HOSTNAMES:
                return True
            return lowered.endswith(_LAN_HOSTNAME_SUFFIXES)
        return addr.is_loopback or addr.is_private or addr.is_link_local


@runtime_checkable
class NetworkComponent(Protocol):
    """Any component that reaches or exposes network endpoints.

    Implementing this one method is how a component opts into offline
    enforcement: it declares — truthfully — every endpoint it will touch, so
    the :class:`EndpointRegistry` (and APP-08) can reason about it centrally.
    """

    def declare_endpoints(self) -> list[Endpoint]:
        """Return every endpoint this component intends to reach or expose."""
        ...


class EndpointRegistry:
    """Collects endpoint declarations from many components for one caller.

    Phase 9's APP-08 daemon registers every :class:`NetworkComponent`, then
    refuses to start if :meth:`non_lan_endpoints` is non-empty while offline
    mode is on. Registration order is preserved for stable enumeration.
    """

    def __init__(self) -> None:
        self._components: list[NetworkComponent] = []

    def register(self, component: NetworkComponent) -> None:
        """Add ``component`` so its endpoints appear in later enumerations."""
        self._components.append(component)

    def all_endpoints(self) -> list[Endpoint]:
        """Return every declared endpoint across all registered components."""
        endpoints: list[Endpoint] = []
        for component in self._components:
            endpoints.extend(component.declare_endpoints())
        return endpoints

    def non_lan_endpoints(self) -> list[Endpoint]:
        """Return only the endpoints that classify as non-LAN.

        This is exactly the set APP-08 will refuse under offline mode.
        """
        return [ep for ep in self.all_endpoints() if not ep.is_lan()]
