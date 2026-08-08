# SPDX-License-Identifier: Apache-2.0
"""CORE-05: LAN vs non-LAN endpoint classification + registry aggregation.

These tests are the SC#4 (endpoint half) contract: every network-touching
component declares its endpoints through one interface, an ``Endpoint`` can
classify itself LAN vs non-LAN without any DNS lookup, and a registry
aggregates declarations so Phase-9's APP-08 daemon can refuse non-LAN endpoints.

The whole module runs under the suite-wide ``--disable-socket`` default, so a
classification that reached for ``socket.getaddrinfo`` would fail the build —
that is the T-02-16 (no-DNS) guard, enforced mechanically.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from paaf_core.net import Endpoint, EndpointRegistry, NetworkComponent


class TestEndpointClassification:
    """``is_lan()`` classifies numeric ranges and ``.local`` offline."""

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",  # IPv4 loopback
            "127.5.6.7",  # anywhere in 127.0.0.0/8
            "::1",  # IPv6 loopback
            "10.0.0.4",  # RFC1918 10/8
            "172.16.9.9",  # RFC1918 172.16/12
            "192.168.1.50",  # RFC1918 192.168/16
            "169.254.10.10",  # IPv4 link-local
            "fe80::1",  # IPv6 link-local
            "device.local",  # mDNS / .local
            "MyBox.LOCAL",  # .local is case-insensitive
        ],
    )
    def test_lan_hosts_classify_lan(self, host: str) -> None:
        assert Endpoint(host, 8080, "http").is_lan() is True

    @pytest.mark.parametrize(
        "host",
        [
            "api.openai.com",  # the negative control
            "8.8.8.8",  # public IPv4
            "example.com",  # public hostname
            "2606:4700:4700::1111",  # public IPv6
        ],
    )
    def test_public_hosts_classify_non_lan(self, host: str) -> None:
        assert Endpoint(host, 443, "https").is_lan() is False

    def test_endpoint_is_frozen(self) -> None:
        ep = Endpoint("127.0.0.1", 8080, "http")
        with pytest.raises(FrozenInstanceError):
            ep.host = "10.0.0.1"  # type: ignore[misc]


class TestEndpointUrl:
    """``path`` is declared, appended verbatim, and never classifies anything."""

    def test_path_defaults_to_empty(self) -> None:
        # The default must stay "" rather than None: url() concatenates it, and a
        # future default change would otherwise silently produce "…:8000None".
        assert Endpoint("192.168.1.20", 8000, "http").path == ""

    def test_url_without_a_path_is_scheme_host_port(self) -> None:
        # No trailing slash and no invented suffix — the endpoint means exactly
        # what the user declared.
        assert (
            Endpoint("192.168.1.20", 8000, "http").url() == "http://192.168.1.20:8000"
        )

    def test_url_with_a_path_appends_it_verbatim(self) -> None:
        # /v1 is where vLLM, llama.cpp's server and LM Studio actually serve.
        endpoint = Endpoint("192.168.1.20", 8000, "http", "/v1")
        assert endpoint.url() == "http://192.168.1.20:8000/v1"

    @pytest.mark.parametrize(
        ("host", "expected"),
        [("192.168.1.20", True), ("api.openai.com", False)],
        ids=["lan", "public"],
    )
    def test_a_path_does_not_change_classification(
        self, host: str, expected: bool
    ) -> None:
        # is_lan() reads the HOST. A path is addressing, not trust: letting it
        # shift classification would make Phase-9's offline refusal depend on a
        # string the user typed for a completely unrelated reason.
        assert Endpoint(host, 8000, "http").is_lan() is expected
        assert Endpoint(host, 8000, "http", "/v1").is_lan() is expected

    def test_two_endpoints_differing_only_in_path_are_distinct(self) -> None:
        # NOT incidental. The adapter's model cache is keyed on the derived URL;
        # two paths collapsing into one set member (or one cache entry) would
        # silently serve one server's client for another's.
        with_path = Endpoint("192.168.1.20", 8000, "http", "/v1")
        without = Endpoint("192.168.1.20", 8000, "http")

        assert with_path != without
        assert len({with_path, without}) == 2


class _FakeComponent:
    """A minimal ``NetworkComponent`` used to exercise the registry."""

    def __init__(self, *endpoints: Endpoint) -> None:
        self._endpoints = list(endpoints)

    def declare_endpoints(self) -> list[Endpoint]:
        return list(self._endpoints)


class TestEndpointRegistry:
    """The registry aggregates declarations and isolates non-LAN endpoints."""

    def test_all_endpoints_aggregates_two_components(self) -> None:
        lan_a = Endpoint("127.0.0.1", 8080, "http")
        lan_b = Endpoint("192.168.1.50", 80, "http")
        public = Endpoint("api.openai.com", 443, "https")
        comp_one = _FakeComponent(lan_a, public)
        comp_two = _FakeComponent(lan_b)

        registry = EndpointRegistry()
        registry.register(comp_one)
        registry.register(comp_two)

        assert set(registry.all_endpoints()) == {lan_a, lan_b, public}

    def test_non_lan_endpoints_returns_only_public(self) -> None:
        lan = Endpoint("10.0.0.4", 8000, "http")
        public = Endpoint("api.openai.com", 443, "https")
        registry = EndpointRegistry()
        registry.register(_FakeComponent(lan, public))

        assert registry.non_lan_endpoints() == [public]

    def test_empty_registry_has_no_endpoints(self) -> None:
        registry = EndpointRegistry()
        assert registry.all_endpoints() == []
        assert registry.non_lan_endpoints() == []

    def test_fake_component_satisfies_protocol(self) -> None:
        assert isinstance(_FakeComponent(), NetworkComponent)
