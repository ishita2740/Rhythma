"""Which address a request is attributed to (issue #498).

The behaviour under test is a security control, so the cases are written
as the two questions an attacker and an operator each ask.

*Can I choose my own bucket?* — the spoofing cases. A caller who sends
``X-Forwarded-For`` from a peer nobody declared as a proxy must be
bucketed on the socket they actually connected from, whatever the header
says, and a caller behind a real proxy must not be able to prepend entries
that get read instead of theirs.

*Will my deployment still work?* — the topology cases. One reverse proxy,
two chained proxies, a platform balancer with no publishable address, IPv6
and ports. Each of those is a real shape and each has to resolve to the
client rather than to an internal hop.

``resolve_client_address`` is exercised directly rather than through a
request wherever the request adds nothing: it is a pure function of a peer
and a header, and the interesting cases are all about those two strings.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.client_address import (  # noqa: E402
    MAX_FORWARDED_ENTRIES,
    TRUSTED_PROXY_HOPS_ENV,
    TRUSTED_PROXY_IPS_ENV,
    UNKNOWN_ADDRESS,
    client_address,
    forwarded_chain,
    resolve_client_address,
    trusted_proxy_hops,
    trusted_proxy_spec,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_ambient_proxy_config(monkeypatch):
    """Start every test from an unconfigured deployment.

    Both variables are read from the environment on each call, so a value
    left behind by another test — or present in the developer's shell —
    would silently change what is being asserted here.
    """
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.delenv(TRUSTED_PROXY_HOPS_ENV, raising=False)


class _FakeRequest:
    """The two attributes ``client_address`` reads off a request."""

    def __init__(self, headers=None, host="198.51.100.7"):
        self.headers = headers or {}

        class _Client:
            def __init__(self, host):
                self.host = host

        self.client = _Client(host) if host is not None else None


# ─── The default: nothing in front of us ──────────────────────────────────


def test_an_unconfigured_deployment_ignores_the_header_entirely():
    """The failure #498 is about, asserted directly.

    No ``TRUSTED_PROXY_IPS`` means no proxy, which means a forwarded
    header did not come from one. Unset is also what a forgotten deploy
    variable looks like, so this is the direction that has to fail safe.
    """
    assert (
        resolve_client_address("198.51.100.7", "203.0.113.5") == "198.51.100.7"
    )


def test_an_unconfigured_deployment_still_reports_the_peer():
    assert resolve_client_address("198.51.100.7", None) == "198.51.100.7"


def test_no_peer_is_unknown_whatever_the_header_claims():
    """Unattributable callers share one bucket rather than escaping."""
    assert resolve_client_address(None, "203.0.113.5") == UNKNOWN_ADDRESS
    assert resolve_client_address("", "203.0.113.5") == UNKNOWN_ADDRESS


# ─── Spoofing ─────────────────────────────────────────────────────────────


def test_a_direct_caller_cannot_choose_its_bucket(monkeypatch):
    """The attack: one header, incremented, used to mean unlimited attempts.

    ``10.0.0.1`` is the declared proxy. The caller is not it, so every one
    of these resolves to the address they actually connected from and they
    all land in the same bucket.
    """
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    buckets = {
        resolve_client_address("198.51.100.7", f"203.0.113.{n}")
        for n in range(1, 30)
    }

    assert buckets == {"198.51.100.7"}


def test_a_client_behind_a_proxy_cannot_prepend_its_own_entries(monkeypatch):
    """The subtler attack, and the reason the walk runs right to left.

    The proxy appended ``203.0.113.9`` — its view of who connected to it,
    which is the truth. Everything to the left of that is what the client
    sent, and a left-most read would take ``1.1.1.1``.
    """
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    resolved = resolve_client_address(
        "10.0.0.1", "1.1.1.1, 2.2.2.2, 203.0.113.9"
    )

    assert resolved == "203.0.113.9"


def test_a_spoofed_internal_address_does_not_shorten_the_walk(monkeypatch):
    """Claiming to be the proxy does not get you skipped past.

    The client writes ``10.0.0.1`` — the trusted proxy's own address —
    hoping the walk treats it as one of ours and keeps going left into
    entries it controls. It does keep going left, and the entries it
    finds there are also the client's, so the answer is still the only
    entry a proxy wrote: the one the real proxy appended.
    """
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    resolved = resolve_client_address(
        "10.0.0.1", "1.1.1.1, 10.0.0.1, 203.0.113.9"
    )

    assert resolved == "203.0.113.9"


def test_a_header_made_entirely_of_our_own_proxies_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8")

    assert resolve_client_address("10.0.0.1", "10.1.2.3, 10.4.5.6") == "10.0.0.1"


def test_an_unparseable_header_falls_back_to_the_peer(monkeypatch):
    """A bucket key that is not an address is a bucket key an attacker chose."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert resolve_client_address("10.0.0.1", "not-an-address") == "10.0.0.1"
    assert resolve_client_address("10.0.0.1", " , , ") == "10.0.0.1"


# ─── Real topologies ──────────────────────────────────────────────────────


def test_one_reverse_proxy_resolves_to_the_client(monkeypatch):
    """nginx or Caddy on the same host, the most common self-hosted shape."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "127.0.0.1")

    assert resolve_client_address("127.0.0.1", "203.0.113.5") == "203.0.113.5"


def test_two_chained_proxies_skip_both_internal_hops(monkeypatch):
    """A CDN in front of an ingress: both are ours, the client is not."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8, 172.16.0.0/12")

    resolved = resolve_client_address(
        "10.0.0.1", "203.0.113.5, 172.16.4.4, 10.0.0.9"
    )

    assert resolved == "203.0.113.5"


def test_a_cidr_block_covers_a_whole_proxy_pool(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8")

    assert resolve_client_address("10.4.5.6", "203.0.113.5") == "203.0.113.5"
    assert resolve_client_address("11.4.5.6", "203.0.113.5") == "11.4.5.6"


def test_wildcard_with_a_hop_count_reads_past_the_platform_balancer(monkeypatch):
    """Cloud Run, Render, a Vercel rewrite: no publishable balancer address.

    ``*`` accepts any peer as a proxy, and ``TRUSTED_PROXY_HOPS`` says how
    many entries that platform appends. The client is still not free to
    choose which entry is read — only how far right the true one sits, and
    that is fixed by the platform.
    """
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "1")

    resolved = resolve_client_address(
        "169.254.1.1", "1.1.1.1, 203.0.113.5, 169.254.8.8"
    )

    assert resolved == "203.0.113.5"


def test_wildcard_without_hops_reads_the_last_entry(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")

    assert (
        resolve_client_address("169.254.1.1", "1.1.1.1, 203.0.113.5")
        == "203.0.113.5"
    )


def test_a_hop_count_larger_than_the_chain_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "5")

    assert resolve_client_address("10.0.0.1", "203.0.113.5") == "10.0.0.1"


# ─── Address shapes ───────────────────────────────────────────────────────


def test_a_port_suffix_is_stripped(monkeypatch):
    """Some proxies append one even though the header is addresses only."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert resolve_client_address("10.0.0.1", "203.0.113.5:41234") == "203.0.113.5"


def test_ipv6_is_carried_through(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "2001:db8::1") == "2001:db8::1"
    )


def test_bracketed_ipv6_with_a_port_is_unwrapped(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "[2001:db8::1]:8443") == "2001:db8::1"
    )


def test_an_ipv4_mapped_address_folds_to_one_bucket(monkeypatch):
    """The same client must not get two budgets for two spellings."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "::ffff:203.0.113.5") == "203.0.113.5"
    )


def test_an_ipv6_proxy_peer_is_recognised_by_its_network(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "2001:db8::/32")

    assert (
        resolve_client_address("2001:db8::9", "203.0.113.5") == "203.0.113.5"
    )


# ─── Bounds and malformed configuration ───────────────────────────────────


def test_an_absurdly_long_header_is_bounded(monkeypatch):
    """A thousand entries is a valid HTTP request and not a valid chain."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    chain = ", ".join(f"203.0.113.{n % 250 + 1}" for n in range(1000))

    assert len(forwarded_chain(chain)) == MAX_FORWARDED_ENTRIES
    # Still answers, and still with an address rather than the raw header.
    assert resolve_client_address("10.0.0.1", chain).startswith("203.0.113.")


def test_an_over_long_entry_is_not_an_address(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert forwarded_chain("A" * 500) == []
    assert resolve_client_address("10.0.0.1", "A" * 500) == "10.0.0.1"


def test_one_unparseable_proxy_entry_does_not_disable_the_others(monkeypatch):
    """A typo in a comma-separated list must not take the limiter down."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "not-an-ip, 10.0.0.1")

    assert resolve_client_address("10.0.0.1", "203.0.113.5") == "203.0.113.5"
    assert resolve_client_address("10.0.0.2", "203.0.113.5") == "10.0.0.2"


def test_a_nonsense_hop_count_is_treated_as_none(monkeypatch):
    """Fewer skipped entries can only move the answer right, which is safe."""
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "banana")
    assert trusted_proxy_hops() == 0

    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "-3")
    assert trusted_proxy_hops() == 0


def test_the_proxy_spec_is_parsed_from_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, " 10.0.0.1 , 172.16.0.0/12 ,, ")

    assert trusted_proxy_spec() == ["10.0.0.1", "172.16.0.0/12"]


def test_an_empty_proxy_spec_is_no_configuration_at_all(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "   ")

    assert trusted_proxy_spec() == []
    assert resolve_client_address("198.51.100.7", "203.0.113.5") == "198.51.100.7"


# ─── The request wrapper ──────────────────────────────────────────────────


def test_client_address_reads_the_header_off_a_request(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5"}, host="10.0.0.1")

    assert client_address(request) == "203.0.113.5"


def test_client_address_falls_back_to_the_socket_address():
    assert client_address(_FakeRequest(host="198.51.100.7")) == "198.51.100.7"


def test_client_address_is_unknown_when_there_is_nothing_to_read():
    assert client_address(_FakeRequest(host=None)) == UNKNOWN_ADDRESS
    assert client_address(None) == UNKNOWN_ADDRESS


def test_a_malformed_request_object_degrades_rather_than_raising():
    """Reached from ``enforce()`` — a raise here would be a 500, not a 429."""

    class _Broken:
        @property
        def headers(self):
            raise RuntimeError("no headers here")

        client = None

    assert client_address(_Broken()) == UNKNOWN_ADDRESS
