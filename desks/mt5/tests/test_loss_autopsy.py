"""Every live loss is a DEFECT, an EDGE_DECAY or NATURAL, and an unresolved defect fails loudly.

Principal 2026-10-13: "it fixes its own losses if theyre bottlenecks flaws defects etc". The case
that started it is pinned first: the 2026-10-12 AUDCHF trade risked 13.0% of equity against the
10% envelope, and that must read DEFECT until the commit that fixed it is named.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loss_autopsy as la  # noqa: E402

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


def _build(deals, intents=(INTENT,), resolved=None, balance=484.83):
    return la.build(NOW, deals=list(deals), intents=list(intents), sleeves_doc=SLEEVES,
                    cert=CERT, account={"balance": balance}, drift={},
                    resolved=resolved or {}, e8_intents=[])


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


def test_a_clean_minus_one_r_inside_the_envelope_is_natural() -> None:
    small = {**AUDCHF, "pl_quote": -40.0, "r_multiple": -1.0, "commission": -0.8}
    row = _build([small], balance=1000.0 - 40.0)["rows"][0]
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
    out, queue = tmp_path / "LOSS_AUTOPSY.json", tmp_path / "q.jsonl"
    first = la.publish(doc, out, queue)
    assert first == len(doc["fix_queue"]) and la.publish(doc, out, queue) == 0
    assert json.loads(out.read_text())["verdict"] == "FAIL"
    assert len(queue.read_text().splitlines()) == first
