"""Every live trade is DEFECT, SUBOPTIMAL, EDGE_DECAY or NATURAL; an open finding fails loudly.

Principal 2026-10-13: "it fixes its own losses if theyre bottlenecks flaws defects etc". The case
that started it is pinned first: the 2026-10-12 AUDCHF trade risked 13.0% of equity against the
10% envelope, and that must read DEFECT until the commit that fixed it is named.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loss_autopsy as la  # noqa: E402

#: The box publishes data/e8_ledger.jsonl; these tests decide E8's state themselves.
la.E8_LEDGER = DESK / "tests" / "__no_e8_ledger__.jsonl"
la.SHADOW_STATE = DESK / "tests" / "__no_shadow_state__.json"

NOW = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
NAME = "audchf_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007"
AUDCHF = {"time": "2026-10-13T03:07:30+00:00", "sleeve": NAME[:27], "symbol": "AUDCHF",
          "entry_time": "2026-10-13T01:41:26.403000+00:00", "side": 1, "pl_quote": -74.58,
          "r_multiple": -1.0219, "volume": 0.79, "commission": -1.6, "swap": 0.0,
          "deal": 210461494, "fill_price": 0.57994, "entry_price": 0.5808, "sl": 0.57994,
          "position_id": 234810421, "account_kind": "live", "risk_quote": 60.0}
INTENT = {"sleeve": NAME, "symbol": "AUDCHF", "side": "buy", "lot": 0.79, "intended": 0.58085,
          "sl": 0.57994, "ticket": 234810421, "retcode": 10009, "decision_bid": 0.58072,
          "decision_ask": 0.5808, "latency_ms": 90.0, "time": "2026-10-12T22:41:26+00:00",
          "intent_id": "i1", "release_id": "r", "state_vector_id": "s"}
CERT = {"enabled": True, "fusion": {"AUDCHF_overnight_gap_decay_asia": 0.1}}
SLEEVES = {"sleeves": [{"name": NAME, "status": "LIVE", "shadow_exp": 0.2}]}


#: The certificate's cost model for AUDCHF: one 10-point spread per side, 0.12R of an 86-point stop.
UNIVERSE = {"AUDCHF": {"median_spread_pts": 10.0, "tick_size": 1e-05}}
#: Stands in for git: the AUDCHF fix is a real commit in the running release, nothing else is.
REAL_FIX = "441071a47"


def _verified(v: object) -> bool:
    return str(v).split()[0] == REAL_FIX if isinstance(v, str) and v.strip() else False


def _build(deals, intents=(INTENT,), resolved=None, balance=484.83, e8=None, blocked=(),
           sleeves=None, cert=None):
    return la.build(NOW, deals=list(deals), intents=list(intents),
                    sleeves_doc=sleeves or SLEEVES, cert=CERT if cert is None else cert,
                    account={"balance": balance}, drift={}, resolved=resolved or {},
                    e8_ledger=e8, e8_journals=[], blocked=blocked, universe=UNIVERSE,
                    verify_fix=_verified)


def test_the_audchf_loss_is_an_oversize_defect_until_its_fix_is_named() -> None:
    doc = _build([AUDCHF], balance=561.26 - 74.58)
    row = doc["rows"][0]
    assert row["verdict"] == la.DEFECT and row["open"]
    kinds = {f["defect"] for f in row["defects"]}
    assert kinds == {"oversize", "over_allocation"}, row["defects"]
    assert any(f["fix_id"] == "loss:210461494:oversize" for f in doc["fix_queue"])
    fixed = {"resolved": {"210461494": {"oversize": "441071a47", "over_allocation": "441071a47"}}}
    after = _build([AUDCHF], resolved=fixed, balance=561.26 - 74.58)
    assert not after["rows"][0]["open"]
    assert [f["fix_id"] for f in after["fix_queue"]] == ["loss:e8:no_close_ledger"]
    assert _build([AUDCHF], resolved=fixed, balance=561.26 - 74.58, e8=[])["fix_queue"] == []


def test_a_clean_minus_one_r_inside_the_envelope_is_natural() -> None:
    small = {**AUDCHF, "pl_quote": -40.0, "r_multiple": -1.0, "commission": -0.8}
    row = _build([small], balance=400.0 - 40.0)["rows"][0]      # 10% of 400, the book's size
    assert row["verdict"] == la.NATURAL and not row["defects"]


def test_an_untraced_or_unattributed_close_is_a_defect() -> None:
    orphan = {**AUDCHF, "pl_quote": -10.0, "r_multiple": -1.0, "commission": 0.0}
    row = _build([orphan], intents=[], balance=1000.0)["rows"][0]
    assert {f["defect"] for f in row["defects"]} >= {"untraced"}
    bare = {**orphan, "sleeve": "[sl 0.57994]"}
    row = _build([bare], intents=[], balance=1000.0)["rows"][0]
    assert {"untraced", "unattributed"} <= {f["defect"] for f in row["defects"]}


def test_slippage_is_measured_against_the_quote_sent_on_not_the_signal_bar() -> None:
    # the signal fired at 0.58120 but the ask was 0.58080 and the fill 0.58080: no slippage
    drift = {**INTENT, "intended": 0.58120}
    clean = {**AUDCHF, "pl_quote": -40.0, "r_multiple": -1.0, "commission": 0.0}
    row = _build([clean], intents=[drift], balance=1000.0)["rows"][0]
    assert "entry_slippage" not in {f["defect"] for f in row["defects"]}
    bad = {**clean, "entry_price": 0.58110}          # 30 points over an 86-point stop: 0.35R
    row = _build([bad], balance=1000.0)["rows"][0]
    assert "entry_slippage" in {f["defect"] for f in row["defects"]}


def test_a_broker_stamp_is_three_hours_ahead_of_utc_and_that_is_not_a_clock_defect() -> None:
    clean = {**AUDCHF, "pl_quote": -40.0, "r_multiple": -1.0, "commission": 0.0}
    row = _build([clean], balance=1000.0)["rows"][0]
    assert "clock" not in {f["defect"] for f in row["defects"]}
    skewed = {**clean, "entry_time": "2026-10-12T22:41:26+00:00"}  # UTC written as broker time
    row = _build([skewed], balance=1000.0)["rows"][0]
    assert "clock" in {f["defect"] for f in row["defects"]}


def test_history_is_reported_never_queued_and_e8_is_a_standing_gap() -> None:
    old = {**AUDCHF, "time": "2026-09-20T03:07:30+00:00", "deal": 1}
    doc = _build([old], intents=[], balance=561.26 - 74.58)
    assert doc["rows"][0]["historical"] and not doc["rows"][0]["open"]
    assert [f["fix_id"] for f in doc["fix_queue"]] == ["loss:e8:no_close_ledger"]
    assert doc["e8"]["status"] == la.UNMEASURED


def test_the_fix_queue_is_appended_once_per_fix(tmp_path: Path) -> None:
    doc = _build([AUDCHF], balance=561.26 - 74.58)
    queue = tmp_path / "q.jsonl"
    first = la.queue_fixes(doc, queue)
    assert first == len(doc["fix_queue"]) and la.queue_fixes(doc, queue) == 0
    assert doc["verdict"] == "FAIL"
    assert len(queue.read_text().splitlines()) == first


def test_e8_losses_are_autopsied_from_the_close_ledger_and_its_absence_is_a_fix_row() -> None:
    gold = {"time": "2026-10-13T08:00:00+00:00", "venue": "e8", "position_id": 77,
            "sleeve": "gold_asia", "symbol": "XAUUSD", "r_multiple": -1.0, "risk_frac": 0.01,
            "pl_usd_est": -1000.0, "latency_send_to_ack_ms": 120.0}
    cert = {"enabled": True, "e8": {"gold_asia": 0.01}}
    doc = la.build(NOW, deals=[], intents=[], sleeves_doc=SLEEVES, cert=cert, account={},
                   drift={}, resolved={}, e8_ledger=[gold], e8_journals=[], blocked=[])
    assert doc["e8"]["status"] == "MEASURED" and doc["rows"][0]["verdict"] == la.NATURAL
    assert doc["fix_queue"] == []
    big = {**gold, "position_id": 78, "risk_frac": 0.02}
    doc = la.build(NOW, deals=[], intents=[], sleeves_doc=SLEEVES, cert=cert, account={},
                   drift={}, resolved={}, e8_ledger=[big], e8_journals=[], blocked=[])
    assert [f["fix_id"] for f in doc["fix_queue"]] == ["loss:e8:e8:78:over_allocation"]


def test_a_winner_sized_timidly_is_suboptimal_and_queued() -> None:
    win = {**AUDCHF, "pl_quote": 30.0, "r_multiple": 1.0, "commission": 0.0, "deal": 9}
    row = _build([win], balance=1000.0, e8=[])["rows"][0]       # 3% risked, book funds 10%
    assert row["outcome"] == "win" and row["verdict"] == la.SUBOPTIMAL
    assert [f["finding"] for f in row["suboptimal"]] == ["undersize"]
    full = {**win, "pl_quote": 100.0}
    assert _build([full], balance=1100.0, e8=[])["rows"][0]["verdict"] == la.NATURAL


def test_slow_sends_late_fills_and_wide_spreads_are_suboptimal() -> None:
    win = {**AUDCHF, "pl_quote": 100.0, "r_multiple": 1.0, "commission": 0.0}
    slow = {**INTENT, "latency_ms": 900.0, "spread_at_decision": 0.0001}
    row = _build([win], intents=[slow], balance=1000.0, e8=[])["rows"][0]
    assert {"slow_send", "wide_spread"} <= {f["finding"] for f in row["suboptimal"]}
    late = {**win, "entry_time": "2026-10-13T01:43:26+00:00"}       # 120 s after the intent
    row = _build([late], balance=1000.0, e8=[])["rows"][0]
    assert "late_fill" in {f["finding"] for f in row["suboptimal"]}


def test_a_refused_send_is_a_missed_trade() -> None:
    refused = {**INTENT, "ticket": 0, "retcode": 10027, "intent_id": "miss1",
               "time": "2026-10-13T05:00:00+00:00"}
    doc = _build([], intents=[INTENT, refused], e8=[])
    assert [m["id"] for m in doc["missed_sends"]] == ["miss1"]
    assert [f["fix_id"] for f in doc["fix_queue"]] == ["missed:fusion:miss1"]


def test_a_fault_between_signal_and_venue_is_a_missed_trade_and_a_decision_is_not() -> None:
    stale = {"time": "2026-10-13T05:00:00+00:00", "sleeve": NAME, "symbol": "AUDCHF",
             "stage": "desk_stale", "why": "desk state 3h old", "bar": "2026-10-13 04:00"}
    zero = {**stale, "stage": "no_heat", "why": "allocator gave this sleeve no heat"}
    doc = _build([], intents=[], e8=[], blocked=[stale, zero])
    assert [m["why"][:20] for m in doc["missed_sends"]] == ["blocked at desk_stal"]
    assert [b["stage"] for b in doc["blocked_decisions"]] == ["no_heat"]


def test_a_clock_entry_the_live_sleeve_never_sent_is_a_missed_trade() -> None:
    # 2026-10-13: all three gap-decay clocks entered on the 01:00 broker bar; AUDCHF sent at
    # 22:41 UTC, the ZAR sleeves (LIVE since 10-07) sent nothing and nothing said so.
    zar = NAME.replace("audchf", "usdzar")
    roster = {"sleeves": [
        {"name": NAME, "symbol": "AUDCHF", "family": "overnight_gap_decay", "selector": "asia",
         "exec": "family_market", "status": "LIVE", "promoted_at": "2026-10-07T15:30:44+00:00"},
        {"name": zar, "symbol": "USDZAR", "family": "overnight_gap_decay", "selector": "asia",
         "exec": "family_market", "status": "LIVE", "promoted_at": "2026-10-07T15:30:44+00:00"},
        {"name": NAME.replace("audchf", "eurzar"), "symbol": "EURZAR",
         "family": "overnight_gap_decay", "selector": "asia", "exec": "family_market",
         "status": "LIVE", "promoted_at": "2026-10-07T15:30:44+00:00"}]}
    entry = {"status": "ACTIVE", "last_entry": "2026-10-13 01:00:00+00:00"}
    shadow = {"AUDCHF.overnight_gap_decay.asia": entry, "USDZAR.overnight_gap_decay.asia": entry}
    spread = {"time": "2026-10-12T22:20:00+00:00", "sleeve": zar, "symbol": "USDZAR",
              "stage": "quote_spread", "why": "spread crosses the certified target"}
    doc = la.build(NOW, deals=[], intents=[INTENT], sleeves_doc=roster, cert=CERT,
                   account={}, drift={}, resolved={}, e8_ledger=[], e8_journals=[],
                   blocked=[spread], shadow=shadow)
    got = {m["symbol"]: m for m in doc["clock_misses"]}
    assert set(got) == {"USDZAR", "EURZAR"}                  # AUDCHF sent inside the window
    assert got["USDZAR"]["kind"] == "clock_fired" and got["USDZAR"]["blocked_at"] == [
        "quote_spread"]
    assert got["EURZAR"]["kind"] == "unclocked"
    assert {f["fix_id"] for f in doc["fix_queue"]} == {
        f"clock:{zar}|2026-10-13 01:00:00+00:00",
        f"clock:unclocked:{NAME.replace('audchf', 'eurzar')}"}
    early = la.build(datetime(2026, 10, 12, 23, 0, tzinfo=UTC), deals=[], intents=[],
                     sleeves_doc=roster, cert=CERT, account={}, drift={}, resolved={},
                     e8_ledger=[], e8_journals=[], blocked=[], shadow=shadow)
    assert [m["kind"] for m in early["clock_misses"]] == ["unclocked"]   # still in its grace


# ------------------------------------------------- audit 2026-10-13: defects that read NATURAL

CLEAN = {**AUDCHF, "pl_quote": -40.0, "r_multiple": -1.0, "commission": 0.0}


def _kinds(deal, intent=INTENT, **kw):
    row = _build([deal], intents=[intent], balance=400.0 - 40.0, **kw)["rows"][0]
    return row, {f["defect"] for f in row["defects"]}


def test_each_fault_the_audit_named_is_a_defect_not_natural() -> None:
    row, kinds = _kinds(CLEAN)
    assert row["verdict"] == la.NATURAL and not kinds          # the clean trade stays clean
    pend = {**INTENT, "order_type": "pending_stop", "intended": 0.5808}
    assert "entry_slippage" in _kinds({**CLEAN, "entry_price": 0.58110}, pend)[1]
    assert "lot_mismatch" in _kinds({**CLEAN, "volume": 1.58})[1]
    assert "no_stop" in _kinds(CLEAN, {**INTENT, "sl": None})[1]
    # +2h where the venue runs EEST (+3h) that date: the old "either offset" rule passed it
    assert "clock" in _kinds({**CLEAN, "entry_time": "2026-10-13T00:41:26+00:00"})[1]
    stale = {**INTENT, "signal_bar": "2026-10-12 23:00:00+00:00"}      # closed 21:00 UTC
    assert "stale_signal" in _kinds(CLEAN, stale)[1]
    fresh = {**INTENT, "signal_bar": "2026-10-13 00:00:00+00:00"}      # closed 22:00 UTC
    assert "stale_signal" not in _kinds(CLEAN, fresh)[1]
    late = {**INTENT, "ttl_until": "2026-10-13 02:00:00+00:00"}        # 23:00 UTC; closed 03:07
    assert "missed_time_exit" in _kinds({**CLEAN, "fill_price": 0.5803}, late)[1]
    assert "missed_time_exit" not in _kinds(CLEAN, late)[1]           # closed AT its stop
    twin = {**INTENT, "intent_id": "i2", "ticket": 1}
    doc = _build([CLEAN], intents=[{**twin, "time": "2026-10-12T22:41:05+00:00"}, INTENT],
                 balance=360.0)
    assert "duplicate_order" in {f["defect"] for f in doc["rows"][0]["defects"]}


def test_over_allocation_reads_the_roster_when_the_book_is_off() -> None:
    big = {"sleeves": [{"name": NAME, "status": "LIVE", "risk_frac": 0.05}]}
    row = _build([CLEAN], balance=360.0, sleeves=big, cert={"enabled": False})["rows"][0]
    assert "over_allocation" in {f["defect"] for f in row["defects"]}
    bare = {"sleeves": [{"name": NAME, "status": "LIVE"}]}
    row = _build([CLEAN], balance=360.0, sleeves=bare, cert={"enabled": False})["rows"][0]
    assert row["verdict"] == la.UNMEASURED and "over_allocation" in row["unmeasured"]


def test_an_unmeasured_check_or_a_missing_r_is_never_natural() -> None:
    blind = {k: v for k, v in INTENT.items() if k not in ("latency_ms",)}
    row = _build([CLEAN], intents=[blind], balance=360.0)["rows"][0]
    assert row["verdict"] == la.UNMEASURED and "stale_quote" in row["unmeasured"]
    no_r = {**CLEAN, "r_multiple": None}
    doc = _build([no_r], balance=360.0, e8=[])
    assert doc["rows"][0]["verdict"] == la.UNMEASURED and doc["verdict"] == la.UNMEASURED


def test_a_fix_closes_a_defect_only_as_a_real_commit_in_the_running_release() -> None:
    for fake in ("x", True, "deadbeef0", ""):
        bad = {"resolved": {"210461494": {"oversize": fake, "over_allocation": fake}}}
        assert _build([AUDCHF], resolved=bad, balance=561.26 - 74.58)["rows"][0]["open"]
    assert not la.fix_commit_ok("x", "HEAD") and not la.fix_commit_ok(True, "HEAD")
    assert not la.fix_commit_ok("441071a47", None)                    # no release: unproven


def test_the_broker_offset_follows_eu_summer_time() -> None:
    assert la.broker_offset_h(datetime(2026, 10, 13, tzinfo=UTC)) == 3
    assert la.broker_offset_h(datetime(2026, 10, 26, tzinfo=UTC)) == 2   # after 10-25
    assert la.broker_offset_h(datetime(2026, 3, 30, tzinfo=UTC)) == 3    # after 03-29
