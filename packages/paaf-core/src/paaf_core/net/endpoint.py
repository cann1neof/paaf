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
