"""Mis-credit fence, concentration maths and idempotency for the holder collector (R0100 axis 4).

The axis is the DELTA between successive daily snapshots, so a duplicated (date, token) row would
fabricate a zero-delta and a row credited to the WRONG asset would fabricate a concentration
number for an asset nobody measured. Both are structural, both are pinned here.

NO NETWORK: `collect` already takes its HTTP reader as an injectable `fetch` argument, so every
test drives it with an in-memory Ethplorer payload and `sleep_s=0.0`.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from scripts import collect_holder_concentration as hc


def _holders(shares: list[float]) -> list[dict]:
    return [{"address": f"0x{i:040x}", "share": s} for i, s in enumerate(shares)]


def _fake_ethplorer(*, symbol_of=None, holders_of=None, fail: tuple[str, ...] = (),
                    empty_holders: tuple[str, ...] = ()):
    """Route by address, so a test can break exactly one token and leave the other 21 healthy."""
    symbol_of = symbol_of or {addr: sym for sym, addr, _ in hc.UNIVERSE}
    holders_of = holders_of or {}
    default = _holders([12.0, 8.0, 5.0] + [1.0] * 9)

    def fetch(url: str):
        addr = url.rsplit("/", 1)[1].split("?")[0]
        if addr in fail:
            return None, "URLError: <urlopen error timed out>"
        if "getTokenInfo" in url:
            return {"symbol": symbol_of.get(addr, ""), "holdersCount": 4242}, ""
        if addr in empty_holders:
            return {"holders": []}, ""
        return {"holders": holders_of.get(addr, default)}, ""

    return fetch


def _rows(root) -> list[dict]:
    p = root / "data/holder_concentration.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


# ------------------------------------------------------------------------ concentration maths

def test_concentration_sorts_defensively_before_taking_the_top_ten():
    """Ethplorer's ordering is not a contract. A holder table returned ascending would otherwise
    report the SMALLEST ten as the top-10 share -- a plausible number that is simply wrong."""
    ascending = _holders([0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 20.0])
    got = hc.concentration(ascending)
    assert got["top10_share"] == pytest.approx(20 + 10 + 9 + 8 + 7 + 6 + 5 + 4 + 3 + 2)
    assert got["top100_share"] == pytest.approx(sum(h["share"] for h in ascending))
    assert got["n_top_returned"] == 12


def test_top100_share_is_capped_at_one_hundred_holders():
    got = hc.concentration(_holders([1.0] * 150))
    assert got["top100_share"] == pytest.approx(100.0)
    assert got["n_top_returned"] == 150


def test_concentration_ignores_non_dict_entries():
    got = hc.concentration([*_holders([10.0, 5.0]), None, "junk", 7])
    assert got["n_top_returned"] == 2
    assert got["top10_share"] == pytest.approx(15.0)


def test_concentration_of_an_empty_table_is_zero_shares_of_zero_holders():
    """The count is what makes this honest downstream: 0.0 with n_top_returned=0 is a measurement
    of nothing, not a measurement of a perfectly-distributed token."""
    assert hc.concentration([]) == {"top10_share": 0.0, "top100_share": 0.0, "n_top_returned": 0}


def test_concentration_rounds_to_four_places():
    got = hc.concentration(_holders([1.234567, 2.345678]))
    assert got["top10_share"] == 3.5802


# ------------------------------------------------------------------------------ mis-credit fence

def test_a_wrong_on_chain_symbol_refuses_the_row_rather_than_crediting_it(tmp_path):
    """A wrong address must surface as an error, never as a plausible concentration number
    credited to the wrong asset. This is the whole reason getTokenInfo is called at all."""
    sym, addr, _perp = hc.UNIVERSE[0]
    symbols = {a: s for s, a, _ in hc.UNIVERSE}
    symbols[addr] = "NOTLINK"
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(symbol_of=symbols), sleep_s=0.0)

    assert "mis-credit fence" in rep["token_errors"][sym]
    assert "NOTLINK" in rep["token_errors"][sym]
    assert sym not in {r["token"] for r in _rows(tmp_path)}, "no row written for the bad address"
    assert rep["status"] == "DEGRADED"


def test_the_fence_compares_case_insensitively_on_the_chain_side(tmp_path):
    """getTokenInfo returns the on-chain symbol verbatim; a lowercase 'link' is still LINK and
    must not be refused, or the fence becomes a noise generator nobody reads."""
    symbols = {a: s.lower() for s, a, _ in hc.UNIVERSE}
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(symbol_of=symbols), sleep_s=0.0)
    assert rep["token_errors"] == {}
    assert rep["n_new"] == len(hc.UNIVERSE)


def test_universe_addresses_and_perp_targets_are_unique():
    """A duplicated address would double-count a token into the panel; a duplicated perp would
    make two tokens claim the same target series."""
    symbols = [s for s, _, _ in hc.UNIVERSE]
    addrs = [a.lower() for _, a, _ in hc.UNIVERSE]
    perps = [p for _, _, p in hc.UNIVERSE]
    assert len(set(symbols)) == len(symbols)
    assert len(set(addrs)) == len(addrs)
    assert len(set(perps)) == len(perps)
    for _, a, _ in hc.UNIVERSE:
        assert a.startswith("0x") and len(a) == 42
        int(a, 16)                                   # raises if it is not a hex address


# ------------------------------------------------------------------------- row shape + clock

def test_a_row_carries_the_recv_only_clock_and_the_perp_join_key(tmp_path):
    """L1.46: chain state has no single venue instant for a holder table, so t is OUR receipt and
    c must say recv_only. perp_symbol is the join into the desk's own futclose lake."""
    hc.collect(tmp_path, fetch=_fake_ethplorer(), sleep_s=0.0)
    rows = {r["token"]: r for r in _rows(tmp_path)}
    assert set(rows) == {s for s, _, _ in hc.UNIVERSE}
    for sym, addr, perp in hc.UNIVERSE:
        r = rows[sym]
        assert r["c"] == "recv_only" and isinstance(r["t"], int) and r["t"] > 1_700_000_000_000
        assert r["perp_symbol"] == perp and r["address"] == addr
        assert r["date"] == datetime.now(tz=UTC).date().isoformat()
        assert r["holders_count"] == 4242
        assert r["source"] == "ethplorer(freekey)"
        assert r["top10_share"] == pytest.approx(12 + 8 + 5 + 1 * 7)


def test_status_artifact_carries_the_free_tier_attribution(tmp_path):
    """Ethplorer's stated free-tier condition is a reference in every artifact -- the licence is
    what makes the collection lawful under §13, so it travels with the data."""
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(), sleep_s=0.0)
    assert "Ethplorer.io" in rep["attribution"]
    assert "recv_only" in rep["clock_provenance"] and "L1.46" in rep["clock_provenance"]


# --------------------------------------------------------------------------------- idempotency

def test_a_rerun_costs_zero_api_budget(tmp_path):
    """freekey allows 1000 calls/24h and one run spends 44. A rerun must spend NOTHING and must
    not append a second row for the day -- a duplicate day is a fabricated zero-delta."""
    hc.collect(tmp_path, fetch=_fake_ethplorer(), sleep_s=0.0)

    def explode(url: str):
        raise AssertionError(f"a rerun must not call the API: {url}")

    rep = hc.collect(tmp_path, fetch=explode, sleep_s=0.0)
    assert rep["n_new"] == 0
    assert rep["n_already_today"] == len(hc.UNIVERSE)
    assert len(_rows(tmp_path)) == len(hc.UNIVERSE)
    assert rep["status"] == "OK"


def test_yesterdays_rows_do_not_suppress_todays_snapshot(tmp_path):
    yday = (date.fromisoformat(datetime.now(tz=UTC).date().isoformat())
            - timedelta(days=1)).isoformat()
    out = tmp_path / "data/holder_concentration.jsonl"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps({"date": yday, "token": "LINK"}) + "\n", "utf-8")
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(), sleep_s=0.0)
    assert rep["n_new"] == len(hc.UNIVERSE), "the delta series needs one row PER DAY"


def test_today_tokens_skips_a_corrupt_line(tmp_path):
    p = tmp_path / "hc.jsonl"
    p.write_text(json.dumps({"date": "2026-08-05", "token": "LINK"}) + "\n{truncated\n", "utf-8")
    assert hc._today_tokens(p, "2026-08-05") == {"LINK"}


# ------------------------------------------------------------------------------- refusal ladder

def test_every_token_failing_is_not_a_quiet_day(tmp_path):
    """L1.28a: main() returns 2 on this status. An all-dead run must never exit green."""
    all_addrs = tuple(a for _, a, _ in hc.UNIVERSE)
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(fail=all_addrs), sleep_s=0.0)
    assert rep["status"] == "ALL-TOKENS-FAILED"
    assert len(rep["token_errors"]) == len(hc.UNIVERSE)
    assert _rows(tmp_path) == []


def test_an_empty_holder_table_is_an_error_not_a_zero_concentration(tmp_path):
    """An empty table means the holder endpoint gave us nothing. Writing top10_share=0.0 would
    make an UNMEASURED token look like the least concentrated asset in the universe."""
    sym, addr, _ = hc.UNIVERSE[3]
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(empty_holders=(addr,)), sleep_s=0.0)
    assert "empty holder table" in rep["token_errors"][sym]
    assert sym not in {r["token"] for r in _rows(tmp_path)}


def test_one_dead_token_is_degraded_and_the_rest_still_land(tmp_path):
    sym, addr, _ = hc.UNIVERSE[1]
    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(fail=(addr,)), sleep_s=0.0)
    assert rep["status"] == "DEGRADED"
    assert rep["n_new"] == len(hc.UNIVERSE) - 1
    assert list(rep["token_errors"]) == [sym]


def test_a_catch_up_run_whose_tokens_all_fail_is_not_an_idempotent_rerun(tmp_path):
    done_addr = hc.UNIVERSE[0][1]
    rest = tuple(a for _, a, _ in hc.UNIVERSE[1:])
    hc.collect(tmp_path, fetch=_fake_ethplorer(fail=rest), sleep_s=0.0)   # only LINK lands
    assert {r["token"] for r in _rows(tmp_path)} == {hc.UNIVERSE[0][0]}

    rep = hc.collect(tmp_path, fetch=_fake_ethplorer(fail=(*rest, done_addr)), sleep_s=0.0)
    assert rep["n_new"] == 0 and len(rep["token_errors"]) == len(hc.UNIVERSE) - 1
    assert rep["status"] != "NO-NEW-ROWS (idempotent rerun)"


# ------------------------------------------------------------------ declared screen deferral

def test_screenable_from_is_the_harness_floor_not_a_round_number():
    """51 = zwin(20) + n_min(30) + 1 daily observations; starting on the first snapshot they land
    50 calendar days later. A slip here would license a screen that can only say
    INSUFFICIENT-DATA."""
    d = hc.SCREEN_DEFER
    assert d["harness_min_daily_obs"] == 20 + 30 + 1
    span = date.fromisoformat(d["screenable_from"]) - date.fromisoformat(d["first_snapshot"])
    assert span == timedelta(days=d["harness_min_daily_obs"] - 1)
