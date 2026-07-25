# SPDX-License-Identifier: Apache-2.0
"""CORE-05: network-endpoint declaration interface, registry, and LAN classification.

The interface lives in ``paaf-core`` so every package implements it without
importing ``paaf-llm`` or ``paaf-voice`` (FOUND-04-safe). Phase 9's APP-08
iterates :class:`EndpointRegistry` to enforce offline mode.
"""
from __future__ import annotations

from paaf_core.net.endpoint import Endpoint, EndpointRegistry, NetworkComponent

__all__ = [
    "Endpoint",
    "EndpointRegistry",
    "NetworkComponent",
]
