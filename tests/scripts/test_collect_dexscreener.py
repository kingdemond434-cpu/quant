"""Row shape, dedup and refusal ladder for the DexScreener long-tail collector (R0100 axis 3).

The axis is the DELTA between successive daily snapshots, so the two things that can destroy it
silently are (a) a duplicated day, which fabricates a zero-delta, and (b) a snapshot that reads as
a quiet day when the feed was actually down. Both are pinned here, along with the recv_only clock
provenance (DexScreener publishes NO server stamp -- the observation clock is ours, and
`pairCreatedAt` is a venue-stamped EVENT attribute that must never be mistaken for it).

NO NETWORK: `fetch_all` is driven through the module's own `_get` seam, `time.sleep` is
neutralised, and every other function under test is already pure.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta

import pytest

from scripts import collect_dexscreener as dx

_NOW_MS = 1_780_000_000_000
_DAY = 86_400_000


def _pair(addr: str = "0xpair", **over) -> dict:
    base = {"pairAddress": addr, "chainId": "ethereum", "dexId": "uniswap",
            "baseToken": {"symbol": "FOO", "address": "0xfoo"},
            "quoteToken": {"symbol": "WETH", "address": "0xweth"},
            "priceUsd": "1.25", "liquidity": {"usd": 250000.5, "base": 1.0},
            "fdv": 9_000_000, "marketCap": 4_500_000,
            "volume": {"h24": 123456.7, "h6": 1.0},
            "txns": {"h24": {"buys": 900, "sells": 400}},
            "pairCreatedAt": _NOW_MS - 3 * _DAY}
    base.update(over)
    return base


# ----------------------------------------------------------------------------- pure row builder

def test_pair_row_refuses_a_payload_without_the_dedup_key():
    """pairAddress IS the dedup key (R0100). Without it a row cannot be de-duplicated on a rerun,
    so it must be dropped rather than written under an empty key -- absent stays absent."""
    assert dx.pair_row(_pair(addr=""), now_ms=_NOW_MS, date="2026-08-05", feed="profiles") is None
    p = _pair()
    del p["pairAddress"]
    assert dx.pair_row(p, now_ms=_NOW_MS, date="2026-08-05", feed="profiles") is None


def test_pair_row_flattens_the_nested_liquidity_volume_and_txn_blocks():
    row = dx.pair_row(_pair(), now_ms=_NOW_MS, date="2026-08-05", feed="boosts")
    assert row["liquidityUsd"] == pytest.approx(250000.5)
    assert row["volumeH24"] == pytest.approx(123456.7)
    assert row["buysH24"] == 900 and row["sellsH24"] == 400
    assert row["priceUsd"] == pytest.approx(1.25), "string prices must be coerced to float"
    assert row["baseSymbol"] == "FOO" and row["quoteSymbol"] == "WETH"
    assert row["source_feed"] == "boosts" and row["kind"] == "pair"


def test_pair_row_survives_missing_nested_blocks():
    """A long-tail pool with no liquidity/volume/txn block must yield a row with None fields, not
    a KeyError that drops the whole batch."""
    p = _pair()
    for k in ("liquidity", "volume", "txns"):
        p[k] = None
    row = dx.pair_row(p, now_ms=_NOW_MS, date="2026-08-05", feed="profiles")
    assert row is not None
    assert row["liquidityUsd"] is None and row["volumeH24"] is None
    assert row["buysH24"] is None and row["sellsH24"] is None


def test_age_days_is_derived_from_the_venue_stamped_creation_event():
    row = dx.pair_row(_pair(), now_ms=_NOW_MS, date="2026-08-05", feed="profiles")
    assert row["age_days"] == pytest.approx(3.0)
    assert row["pairCreatedAt"] == _NOW_MS - 3 * _DAY, "the raw venue stamp is retained verbatim"


@pytest.mark.parametrize("created", [None, 0, "2026-08-01"])
def test_age_days_is_none_when_creation_is_unusable(created):
    """An unmeasurable age must read as UNMEASURED (None), never as a 0-day-old brand-new pool --
    age is the whole point of a new-listing feed."""
    row = dx.pair_row(_pair(pairCreatedAt=created), now_ms=_NOW_MS, date="2026-08-05",
                      feed="profiles")
    assert row["age_days"] is None


def test_pair_row_carries_the_recv_only_clock():
    """L1.46: DexScreener returns no server stamp on the snapshot, so t is OUR receipt instant and
    the clock class must say so. Stamping c='venue' here would be a provenance lie."""
    row = dx.pair_row(_pair(), now_ms=_NOW_MS, date="2026-08-05", feed="profiles")
    assert row["t"] == _NOW_MS
    assert row["c"] == "recv_only"


@pytest.mark.parametrize(("raw", "want"), [
    (None, None), ("1.25", 1.25), (3, 3.0), ("", None), ("N/A", None), ([], None)])
def test_num_coerces_or_returns_absent(raw, want):
    got = dx._num(raw)
    assert got is None if want is None else got == pytest.approx(want)


# ------------------------------------------------------------------------------ per-day dedup

def _row(kind: str, key: str, day: str) -> dict:
    base = {"t": _NOW_MS, "c": "recv_only", "date": day, "kind": kind}
    base["pairAddress" if kind == "pair" else "key"] = key
    return base


def test_existing_keys_loads_only_todays_rows(tmp_path):
    """A pair seen YESTERDAY must not suppress today's snapshot -- that would erase the delta the
    axis is built from."""
    p = tmp_path / "snap.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in (
        _row("pair", "0xaaa", "2026-08-04"),
        _row("pair", "0xbbb", "2026-08-05"),
        _row("profile", "ethereum:0xfoo", "2026-08-05"))), "utf-8")
    assert dx._existing_keys(p, "2026-08-05") == {
        ("pair", "0xbbb"), ("profile", "ethereum:0xfoo")}


def test_existing_keys_skips_a_corrupt_line(tmp_path):
    p = tmp_path / "snap.jsonl"
    p.write_text(json.dumps(_row("pair", "0xbbb", "2026-08-05")) + "\n{truncated\n", "utf-8")
    assert dx._existing_keys(p, "2026-08-05") == {("pair", "0xbbb")}


def test_collect_is_idempotent_within_a_day(tmp_path):
    """A rerun must never append a second copy: a duplicated day fabricates a zero-delta."""
    day = datetime.now(tz=UTC).date().isoformat()
    rows = [_row("pair", "0xaaa", day), _row("profile", "ethereum:0xfoo", day)]
    first = dx.collect(tmp_path, list(rows), {})
    assert first["status"] == "OK" and first["n_new"] == 2
    second = dx.collect(tmp_path, list(rows), {})
    assert second["n_new"] == 0
    assert second["status"] == "NO-NEW-ROWS (idempotent rerun)"
    written = (tmp_path / "data/dexscreener_snapshots.jsonl").read_text("utf-8")
    assert len(written.strip().splitlines()) == 2


def test_collect_dedupes_within_a_single_batch(tmp_path):
    day = datetime.now(tz=UTC).date().isoformat()
    rep = dx.collect(tmp_path, [_row("pair", "0xaaa", day), _row("pair", "0xaaa", day)], {})
    assert rep["n_new"] == 1


def test_collect_drops_a_row_with_no_dedup_key(tmp_path):
    day = datetime.now(tz=UTC).date().isoformat()
    rep = dx.collect(tmp_path, [_row("pair", "", day), _row("pair", "0xaaa", day)], {})
    assert rep["n_new"] == 1 and rep["n_new_pairs"] == 1


def test_collect_counts_pairs_and_profiles_separately(tmp_path):
    day = datetime.now(tz=UTC).date().isoformat()
    rep = dx.collect(tmp_path, [_row("pair", "0xaaa", day), _row("pair", "0xbbb", day),
                                _row("profile", "ethereum:0xfoo", day)], {})
    assert rep["n_new_pairs"] == 2 and rep["n_new_profiles"] == 1


# ------------------------------------------------------------------------------- refusal ladder

def test_both_feeds_down_is_not_a_quiet_day(tmp_path):
    errors = {feed: "URLError: down" for feed, _ in dx._FEEDS}
    rep = dx.collect(tmp_path, [], errors)
    assert rep["status"] == "ALL-SOURCES-DOWN"
    assert rep["source_errors"] == errors


def test_one_feed_down_is_degraded_not_ok(tmp_path):
    day = datetime.now(tz=UTC).date().isoformat()
    rep = dx.collect(tmp_path, [_row("pair", "0xaaa", day)], {"boosts": "HTTPError: 429"})
    assert rep["status"] == "DEGRADED", "a partial outage must never read as OK"


def test_an_empty_snapshot_with_no_error_is_no_data(tmp_path):
    """The worst case: nothing failed and nothing arrived. L1.28a says that is NO-DATA, and
    main() turns it into a non-zero exit rather than a green cron line."""
    rep = dx.collect(tmp_path, [], {})
    assert rep["status"] == "NO-DATA"


def test_status_ladder_puts_degraded_ahead_of_the_idempotent_branch(tmp_path):
    """An error must outrank 'nothing new today'. (The sibling organ
    collect_holder_concentration.py orders these two the other way round -- see its test file.)"""
    day = datetime.now(tz=UTC).date().isoformat()
    dx.collect(tmp_path, [_row("pair", "0xaaa", day)], {})
    rerun = dx.collect(tmp_path, [_row("pair", "0xaaa", day)], {"profiles": "URLError: down"})
    assert rerun["n_new"] == 0
    assert rerun["status"] == "DEGRADED"


def test_status_artifact_declares_its_clock_and_deferral(tmp_path):
    rep = dx.collect(tmp_path, [], {})
    assert "recv_only" in rep["clock_provenance"] and "L1.46" in rep["clock_provenance"]
    assert rep["screen_deferral"] == dx.SCREEN_DEFER


# ------------------------------------------------------------------ declared screen deferral

def test_screenable_from_is_the_harness_floor_not_a_round_number():
    """51 daily observations starting on the first snapshot land 50 CALENDAR days later. A slip
    here would let the axis be screened before the harness can return anything but
    INSUFFICIENT-DATA, i.e. a screen that is theatre."""
    d = dx.SCREEN_DEFER
    assert d["harness_min_daily_obs"] == 20 + 30 + 1
    span = date.fromisoformat(d["screenable_from"]) - date.fromisoformat(d["first_snapshot"])
    assert span == timedelta(days=d["harness_min_daily_obs"] - 1)


# ---------------------------------------------------------------- fetch_all (network stubbed)

def _stub_get(monkeypatch, responses: dict[str, tuple], calls: list[str]):
    def fake(url: str):
        calls.append(url)
        for frag, resp in responses.items():
            if frag in url:
                return resp
        return None, "URLError: unrouted"
    monkeypatch.setattr(dx, "_get", fake)
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_fetch_all_batches_token_lookups_at_thirty_per_call(monkeypatch):
    """/tokens/v1 accepts at most 30 comma-separated addresses; a 31st silently truncates the
    response, so the batch boundary is load-bearing, not cosmetic."""
    addrs = [f"0x{i:040x}" for i in range(35)]
    profiles = [{"chainId": "ethereum", "tokenAddress": a} for a in addrs]
    calls: list[str] = []
    _stub_get(monkeypatch, {"token-profiles": (profiles, ""),
                            "token-boosts": ([], ""),
                            "/tokens/v1/": ([], "")}, calls)
    rows, errors, n_calls = dx.fetch_all()

    token_calls = [c for c in calls if "/tokens/v1/" in c]
    assert len(token_calls) == 2
    assert len(token_calls[0].rsplit("/", 1)[1].split(",")) == dx._BATCH
    assert len(token_calls[1].rsplit("/", 1)[1].split(",")) == 35 - dx._BATCH
    assert errors == {} and n_calls == len(calls)
    assert sum(1 for r in rows if r["kind"] == "profile") == 35


def test_fetch_all_records_a_feed_failure_under_its_own_name(monkeypatch):
    calls: list[str] = []
    pool = _pair("Pool1", chainId="solana", baseToken={"symbol": "SOL1", "address": "Sol1"})
    _stub_get(monkeypatch, {"token-profiles": (None, "HTTPError: 503"),
                            "token-boosts": ([{"chainId": "solana", "tokenAddress": "Sol1"}], ""),
                            "/tokens/v1/": ([pool], "")}, calls)
    rows, errors, _ = dx.fetch_all()
    assert errors == {"profiles": "HTTPError: 503"}
    assert [r["kind"] for r in rows] == ["profile", "pair"]
    assert rows[1]["source_feed"] == "boosts", "the pair inherits the feed that surfaced it"


def test_feed_attribution_survives_evm_address_case(monkeypatch):
    """Feeds publish lowercase addresses while /tokens/v1 echoes EIP-55 checksummed ones; the
    fallback lookup must still credit the pair to the feed that surfaced it."""
    calls: list[str] = []
    lower = "0x" + "ab" * 20
    pool = _pair("0xpool", baseToken={"symbol": "FOO", "address": lower.upper()})
    _stub_get(monkeypatch, {"token-profiles": ([{"chainId": "ethereum",
                                                 "tokenAddress": lower}], ""),
                            "token-boosts": ([], ""),
                            "/tokens/v1/": ([pool], "")}, calls)
    rows, _, _ = dx.fetch_all()
    assert [r["source_feed"] for r in rows if r["kind"] == "pair"] == ["profiles"]


def test_fetch_all_records_a_token_endpoint_failure_per_chain(monkeypatch):
    calls: list[str] = []
    _stub_get(monkeypatch, {"token-profiles": ([{"chainId": "base", "tokenAddress": "0xb"}], ""),
                            "token-boosts": ([], ""),
                            "/tokens/v1/": (None, "HTTPError: 429")}, calls)
    rows, errors, _ = dx.fetch_all()
    assert errors == {"tokens:base": "HTTPError: 429"}
    assert [r["kind"] for r in rows] == ["profile"]


def test_fetch_all_skips_feed_items_missing_a_chain_or_address(monkeypatch):
    calls: list[str] = []
    _stub_get(monkeypatch, {"token-profiles": ([{"chainId": "ethereum"},
                                                {"tokenAddress": "0xa"},
                                                {"chainId": "ethereum", "tokenAddress": "0xa"}],
                                               ""),
                            "token-boosts": ([], ""),
                            "/tokens/v1/": ([], "")}, calls)
    rows, _, _ = dx.fetch_all()
    assert [r["key"] for r in rows] == ["ethereum:0xa"]


def test_the_same_address_on_two_chains_is_resolved_on_both(monkeypatch):
    """REGRESSION (fixed 2026-08-05). The dedup guard was keyed by ADDRESS ALONE while by_chain
    is per-chain, so a deterministic EVM deploy sharing one address across ethereum/base/bsc was
    resolved on the first chain only and the rest never fetched -- a coverage hole reporting OK."""
    calls: list[str] = []
    _stub_get(monkeypatch, {"token-profiles": ([{"chainId": "ethereum", "tokenAddress": "0xdup"},
                                                {"chainId": "base", "tokenAddress": "0xdup"}], ""),
                            "token-boosts": ([], ""),
                            "/tokens/v1/": ([], "")}, calls)
    rows, _, _ = dx.fetch_all()
    assert sorted(r["key"] for r in rows if r["kind"] == "profile") == [
        "base:0xdup", "ethereum:0xdup"]
    chains_queried = {c.split("/tokens/v1/")[1].split("/")[0] for c in calls if "/tokens/v1/" in c}
    assert chains_queried == {"ethereum", "base"}
