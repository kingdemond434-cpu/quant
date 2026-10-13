"""The standing check that every live sleeve can trade on Fusion and E8 and every order traces.

Principal 2026-10-13: "make sure all live sleeves etc r traceable on e8 n mt5 able to place
orders all sleeves n all future must too". These pin that a future sleeve which cannot place, or
an order that cannot be walked back, turns the check red rather than passing silently.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_live_tradability as clt  # noqa: E402

NOW = datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
UNIVERSE = {"AUDCHF": {"tick_size": 1e-05, "tick_value": 1.06, "volume_step": 0.01},
            "XAUUSD": {"tick_size": 0.01, "tick_value": 0.86, "volume_step": 0.01}}
CERT = {"enabled": True, "fusion": {"AUDCHF_overnight_gap_decay_asia": 0.1, "gold_asia": 0.08},
        "e8": {"AUDCHF_overnight_gap_decay_asia": 0.01}}
ROW = {"name": "audchf_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007",
       "symbol": "AUDCHF", "family": "overnight_gap_decay", "selector": "asia",
       "exec": "family_market", "status": "LIVE", "risk_frac": 0.1}


def _fusion(row=ROW, *, refuse=lambda r, p: None, gap=None, universe=UNIVERSE, tags=None):
    return clt.fusion_checks(row, policy=object(), refuse=refuse,
                             executor_gap=lambda *a: gap, universe=universe, cert=CERT,
                             tags=tags if tags is not None else {})


def test_a_tradable_sleeve_passes_every_fusion_check() -> None:
    out = _fusion()
    assert {k: v["status"] for k, v in out.items()} == dict.fromkeys(
        ("admitted", "executor", "priceable", "sized", "tag_unique"), clt.PASS)


def test_each_reason_a_sleeve_cannot_place_fails_loudly() -> None:
    assert _fusion(refuse=lambda r, p: "outside live_symbols")["admitted"]["status"] == clt.FAIL
    assert _fusion(gap="no constructor")["executor"]["status"] == clt.FAIL
    assert _fusion(universe={"EURUSD": {}})["priceable"]["status"] == clt.FAIL
    assert _fusion(universe={})["priceable"]["status"] == clt.UNMEASURED   # snapshot absent
    unsized = {**ROW, "symbol": "AUDCHF", "risk_frac": 0.0, "family": "carry"}
    assert _fusion(unsized)["sized"]["status"] == clt.FAIL
    twin = {clt.order_comment(ROW["name"]): [ROW["name"], ROW["name"] + "_twin"]}
    assert _fusion(tags=twin)["tag_unique"]["status"] == clt.FAIL


def test_the_tag_mirror_matches_the_gateway() -> None:
    """The check's `order_comment` is a copy (the gateway imports the terminal package); the copy
    must produce the gateway's exact tag or a collision verdict is about the wrong string."""
    import ast
    import hashlib
    src = (DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert f"COMMENT_MAX = {clt.COMMENT_MAX}\n" in src
    assert f"TAG_HASH = {clt.TAG_HASH}\n" in src
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "order_comment")
    ns: dict = {"hashlib": hashlib, "COMMENT_MAX": clt.COMMENT_MAX, "TAG_HASH": clt.TAG_HASH}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gw>", "exec"), ns)
    for name in ("gold_asia", "a" * 27, ROW["name"], ROW["name"] + "_twin"):
        assert clt.order_comment(name) == ns["order_comment"](name)
    assert clt.order_comment(ROW["name"]) != clt.order_comment(ROW["name"] + "_twin")


def test_e8_unlisted_is_a_declared_venue_fact_and_lapses_once_e8_lists_it() -> None:
    ok = clt.e8_checks(ROW, catalogue={"AUDCHF"}, cert=CERT, e8_book=None)
    assert ok["listed"]["status"] == ok["booked"]["status"] == clt.PASS
    zar = {**ROW, "symbol": "EURZAR"}
    bad = clt.e8_checks(zar, catalogue={"AUDCHF"}, cert=CERT, e8_book=None)
    assert bad["listed"]["status"] == bad["booked"]["status"] == clt.VENUE_UNLISTED
    declared = {"EURZAR": "not in E8's 46-instrument catalogue"}
    off = clt.e8_checks(zar, catalogue=None, cert=CERT, e8_book=None, declared=declared)
    assert off["listed"]["status"] == clt.VENUE_UNLISTED
    # E8 lists ZAR one day: the declaration lapses and the sleeve must be booked like any other
    listed = clt.e8_checks(zar, catalogue={"EURZAR"}, cert=CERT, e8_book=None, declared=declared)
    assert listed["listed"]["status"] == clt.PASS and listed["booked"]["status"] == clt.FAIL
    unread = clt.e8_checks(ROW, catalogue=None, cert=CERT, e8_book=None)
    assert unread["listed"]["status"] == clt.UNMEASURED


def test_gold_windows_join_the_live_set_from_the_book_and_the_gateway() -> None:
    rows = clt.live_rows([ROW], CERT, {"brackets": {"gold_london_am": {}}})
    assert [r["name"] for r in rows] == [ROW["name"], "gold_asia", "gold_london_am"]
    gold = _fusion(rows[1])
    assert gold["executor"]["status"] == gold["sized"]["status"] == clt.PASS


def test_trace_fails_on_a_close_with_no_intent_and_on_an_intent_missing_its_ids() -> None:
    intent = {"sleeve": ROW["name"], "ticket": 7, "retcode": 10009, "account_kind": "live",
              "time": "2026-10-12T22:41:26+00:00", "intent_id": "i", "release_id": "r",
              "state_vector_id": "s"}
    close = {"position_id": 7, "time": "2026-10-13T03:07:30+00:00", "account_kind": "live"}
    assert clt.trace([intent], [close], now=NOW)["status"] == clt.PASS
    orphan = {"position_id": 9, "time": "2026-10-13T03:07:30+00:00", "account_kind": "live"}
    assert clt.trace([intent], [close, orphan], now=NOW)["status"] == clt.FAIL
    bare = {k: v for k, v in intent.items() if k != "state_vector_id"}
    assert clt.trace([bare], [close], now=NOW)["status"] == clt.FAIL
    pending = {**intent, "ticket": 8}
    assert clt.trace([intent, pending], [close], now=NOW)["status"] == clt.PASS, \
        "an unfilled pending twin has no close and is not an orphan"


def test_absent_journals_are_unmeasured_and_e8_trace_is_said_unmeasured() -> None:
    now = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    assert clt.trace(None, [], now=now)["status"] == clt.UNMEASURED
    assert clt.trace([], None, now=now)["status"] == clt.UNMEASURED


def test_a_hold_across_the_window_boundary_is_traced_not_an_orphan() -> None:
    now = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    old = {"ticket": 7, "retcode": 10009, "time": "2026-09-28T10:00:00+00:00", "sleeve": "s",
           "intent_id": "i", "release_id": "r", "state_vector_id": "v"}
    close = {"time": "2026-10-01T10:00:00+00:00", "position_id": 7, "sleeve": "s"}
    assert clt.trace([old], [close], now=now)["orphan_closes"] == []


def test_e8_symbols_compare_through_the_venue_normaliser() -> None:
    assert clt.norm_symbol("EURUSD+") == "EURUSD" == clt.norm_symbol("eur/usd")
