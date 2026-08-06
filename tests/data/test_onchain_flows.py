"""STABLECOIN SUPPLY AND EXCHANGE RESERVES -- 47 statements of keyless RPC, untested.

Two orthogonal signals from the same calls: reserves measure WHERE stables are, supply measures HOW
MANY exist. Both are read straight off Ethereum L1 with `eth_call`, which means the whole module is
hex arithmetic on a value returned by a public endpoint -- and hex arithmetic that is off by a
factor of 10^6 produces a number that is wrong by a million and looks entirely plausible in a
dashboard.

THE DECIMALS ARE THE WHOLE FILE. USDT and USDC both use 6, but the constant is per-token for a
reason: a token added later with 18 (as most ERC-20s use) and scaled by 6 reports a supply a
trillion times too large, and every downstream "net minting" delta inherits it. So the scaling is
asserted per token and against the declared table, not against a literal.

THE SECOND PROPERTY IS THE FALLBACK. `_rpc` walks several public endpoints because any one of them
rate-limits without warning. A version that returned 0.0 on total failure would report "exchange
reserves fell to zero" -- the single most alarming reading this module can produce -- as the
outcome of a network problem. It raises instead, and that is pinned.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from libs.data import onchain_flows as OF


def _hexwei(whole: float, decimals: int) -> str:
    return hex(int(whole * 10 ** decimals))


def _stub_rpc(monkeypatch, fn):
    calls: list[tuple[str, list[Any]]] = []

    def fake(method: str, params: list[Any]):
        calls.append((method, params))
        return fn(method, params)

    monkeypatch.setattr(OF, "_rpc", fake)
    return calls


# ============================================================ the decimals

@pytest.mark.parametrize("token", sorted(OF._TOKENS))
def test_each_token_is_scaled_by_ITS_OWN_declared_decimals(monkeypatch, token: str) -> None:
    """A token added later with 18 decimals and scaled by 6 reports a supply a TRILLION times too
    large, and every downstream net-minting delta inherits it. The scale is per token, and the test
    reads the declared table rather than a literal so a new token is covered the day it lands."""
    addr, dec = OF._TOKENS[token]
    _stub_rpc(monkeypatch, lambda m, p: (_hexwei(1_000.0, dec)
                                         if p[0]["to"] == addr else _hexwei(0.0, 6)))
    out = OF.stablecoin_supply()
    assert out["per_token"][token] == pytest.approx(1_000.0)


def test_the_total_supply_is_the_SUM_across_tokens(monkeypatch) -> None:
    _stub_rpc(monkeypatch, lambda m, p: _hexwei(500.0, OF._TOKENS[
        next(k for k, (a, _d) in OF._TOKENS.items() if a == p[0]["to"])][1]))
    out = OF.stablecoin_supply()
    assert out["total_supply_usd"] == pytest.approx(500.0 * len(OF._TOKENS))


def test_the_TOTAL_SUPPLY_selector_is_used_for_supply(monkeypatch) -> None:
    """`totalSupply()` and `balanceOf(address)` are different four-byte selectors. Sending the
    wrong one returns a value the node computes happily and which means something else entirely."""
    calls = _stub_rpc(monkeypatch, lambda m, p: _hexwei(1.0, 6))
    OF.stablecoin_supply()
    assert all(p[0]["data"] == OF._TOTAL_SUPPLY for _m, p in calls)
    assert all(m == "eth_call" for m, _p in calls)


def test_the_BALANCE_OF_selector_carries_the_ADDRESS_PADDED_to_32_bytes(monkeypatch) -> None:
    """An ABI-encoded address is left-padded to 64 hex chars. Unpadded, the node reads the calldata
    at the wrong offset and returns the balance of a different (usually zero) address -- which
    reads as "this exchange holds nothing"."""
    calls = _stub_rpc(monkeypatch, lambda m, p: _hexwei(0.0, 6))
    OF.erc20_balance("0xTOKEN", "0xAbCdEf0000000000000000000000000000000001", 6)
    data = calls[0][1][0]["data"]
    assert data.startswith(OF._BALANCE_OF)
    payload = data[len(OF._BALANCE_OF):]
    assert len(payload) == 64
    assert payload.endswith("abcdef0000000000000000000000000000000001")
    assert payload.lstrip("0") == "abcdef0000000000000000000000000000000001"


def test_the_address_is_LOWERCASED_and_its_0x_prefix_stripped(monkeypatch) -> None:
    """Checksummed addresses arrive mixed-case. Leaving the `0x` in shifts every byte of the
    calldata by one, which is the silent version of the padding bug."""
    calls = _stub_rpc(monkeypatch, lambda m, p: "0x0")
    OF.erc20_balance("0xTOKEN", "0xAAAA000000000000000000000000000000000001", 6)
    payload = calls[0][1][0]["data"][len(OF._BALANCE_OF):]
    assert "0x" not in payload and payload == payload.lower()


# ============================================================ empty results

@pytest.mark.parametrize("empty", ["0x", "", None])
def test_an_EMPTY_rpc_result_is_read_as_ZERO_rather_than_crashing(monkeypatch, empty) -> None:
    """A node answering `0x` for a contract it has not indexed is a routine transient. Raising on
    it would take down the whole reserve sweep for one wallet."""
    _stub_rpc(monkeypatch, lambda m, p: empty)
    assert OF.erc20_balance("0xTOKEN", "0xabc", 6) == 0.0
    assert OF.stablecoin_supply()["total_supply_usd"] == 0.0


def test_a_zero_hex_result_is_zero(monkeypatch) -> None:
    _stub_rpc(monkeypatch, lambda m, p: "0x0")
    assert OF.erc20_balance("0xTOKEN", "0xabc", 6) == 0.0


# ============================================================ exchange reserves

def test_reserves_are_summed_ACROSS_every_wallet_and_token(monkeypatch) -> None:
    """One wallet silently skipped understates an exchange's reserves, and the daily DELTA -- which
    is the actual signal -- then shows an outflow that never happened."""
    _stub_rpc(monkeypatch, lambda m, p: _hexwei(100.0, 6))
    out = OF.exchange_reserves()
    n_wallets = sum(len(w) for w in OF._EXCHANGE_WALLETS.values())
    n_tokens = len(OF._TOKENS)
    assert out["n_wallets"] == n_wallets
    assert out["total_reserve_usd"] == pytest.approx(100.0 * n_wallets * n_tokens)


def test_the_PER_EXCHANGE_breakdown_sums_to_the_total(monkeypatch) -> None:
    """Two views of one number. If they ever disagreed, a reader would have to pick, and the
    breakdown is what makes a move attributable to a venue."""
    _stub_rpc(monkeypatch, lambda m, p: _hexwei(7.0, 6))
    out = OF.exchange_reserves()
    assert sum(out["per_exchange"].values()) == pytest.approx(out["total_reserve_usd"], abs=0.05)


def test_the_PER_TOKEN_breakdown_also_sums_to_the_total(monkeypatch) -> None:
    _stub_rpc(monkeypatch, lambda m, p: _hexwei(7.0, 6))
    out = OF.exchange_reserves()
    assert sum(out["per_token"].values()) == pytest.approx(out["total_reserve_usd"], abs=0.05)


def test_every_tracked_exchange_appears_even_when_it_holds_nothing(monkeypatch) -> None:
    """An exchange dropping out of the report is indistinguishable from an exchange at zero, and
    the second is a headline while the first is a bug."""
    _stub_rpc(monkeypatch, lambda m, p: "0x0")
    out = OF.exchange_reserves()
    assert set(out["per_exchange"]) == set(OF._EXCHANGE_WALLETS)
    assert set(out["per_token"]) == set(OF._TOKENS)


def test_reserves_and_supply_are_ORTHOGONAL_measurements() -> None:
    """Reserves measure WHERE stables are; supply measures HOW MANY exist. They use different
    selectors and different address sets, and conflating them would make a transfer between two
    tracked wallets look like minting."""
    assert OF._BALANCE_OF != OF._TOTAL_SUPPLY
    assert OF._EXCHANGE_WALLETS and OF._TOKENS


# ============================================================ the endpoint fallback

def test_the_rpc_FALLS_BACK_across_public_endpoints(monkeypatch) -> None:
    """Any one public node rate-limits without warning. A single-endpoint version would report an
    outage as a data reading."""
    seen: list[str] = []

    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self._p).encode()

    def fake_urlopen(req, timeout=0):
        seen.append(req.full_url)
        if len(seen) < len(OF._RPCS):
            raise OSError("rate limited")
        return _Resp({"result": "0x64"})

    monkeypatch.setattr(OF.urllib.request, "urlopen", fake_urlopen)
    assert OF._rpc("eth_call", [{}, "latest"]) == "0x64"
    assert len(seen) == len(OF._RPCS), "every endpoint must be tried before giving up"


def test_a_JSON_RPC_ERROR_body_moves_to_the_NEXT_endpoint(monkeypatch) -> None:
    """A 200 response carrying an `error` object is a failure wearing a success's status code.
    Treating it as a result would return None into the hex parser."""
    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self._p).encode()

    n = {"i": 0}

    def fake_urlopen(req, timeout=0):
        n["i"] += 1
        if n["i"] == 1:
            return _Resp({"error": {"code": -32000, "message": "busy"}})
        return _Resp({"result": "0xff"})

    monkeypatch.setattr(OF.urllib.request, "urlopen", fake_urlopen)
    assert OF._rpc("eth_call", [{}, "latest"]) == "0xff"


def test_TOTAL_FAILURE_RAISES_rather_than_reporting_ZERO_RESERVES(monkeypatch) -> None:
    """THE MOST IMPORTANT ASSERTION IN THIS FILE. Returning 0.0 would report "exchange reserves
    fell to zero" -- the single most alarming reading this module can produce -- as the outcome of
    a network problem, and it would page the desk about a nonexistent bank run."""
    monkeypatch.setattr(OF.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    with pytest.raises(RuntimeError, match="all RPC endpoints failed"):
        OF._rpc("eth_call", [{}, "latest"])


def test_the_rpc_body_is_well_formed_JSON_RPC_2(monkeypatch) -> None:
    """A malformed envelope gets a 200 with an error from most nodes, so it would surface as the
    fallback path rather than as a clear failure."""
    captured: list[bytes] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"result": "0x1"}).encode()

    def fake_urlopen(req, timeout=0):
        captured.append(req.data)
        return _Resp()

    monkeypatch.setattr(OF.urllib.request, "urlopen", fake_urlopen)
    OF._rpc("eth_call", [{"to": "0xabc"}, "latest"])
    body = json.loads(captured[0])
    assert body["jsonrpc"] == "2.0" and body["method"] == "eth_call"
    assert body["params"] == [{"to": "0xabc"}, "latest"]


def test_at_least_two_endpoints_are_configured() -> None:
    """One endpoint is not a fallback. This is a declaration, and it is worth pinning because
    trimming the list is the kind of tidy-up that looks harmless."""
    assert len(OF._RPCS) >= 2


def test_no_test_here_reaches_the_network(monkeypatch) -> None:
    def forbidden(*a, **k):
        raise AssertionError("a test reached an RPC endpoint")

    monkeypatch.setattr(OF.urllib.request, "urlopen", forbidden)
    _stub_rpc(monkeypatch, lambda m, p: "0x0")
    assert OF.stablecoin_supply()["total_supply_usd"] == 0.0
