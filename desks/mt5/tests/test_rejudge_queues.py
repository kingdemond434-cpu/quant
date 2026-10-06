"""The two re-judge queues that go to the front of the sealed sweep, right after v4 re-mint.

* the engine rollover trigger (`research/rollover_rejudge.py`): desktop pass 2 row 6 moves the
  backtest's swap charge from stamp 21:00 to stamp midnight; on that change every certified sleeve
  and every judged cell whose trades span stamp 21:00-24:00 or hold >= 24 h is queued;
* the zero-spread stress list (`research/zero_spread_rejudge.py`): once the sealed 3x arm charges
  a real basis on the 14 zero-spread FX majors, every cell there that passed `stress_costs` is
  queued -- and never before the patch lands.
"""
from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import rollover_rejudge as RR  # noqa: E402
from research import stage1_record as REC  # noqa: E402
from research import zero_spread_rejudge as ZR  # noqa: E402


def test_a_holding_period_spans_the_evening_or_the_night() -> None:
    ts = pd.Timestamp
    cases = [(ts("2026-03-02 20:00"), ts("2026-03-02 23:00"), 1),   # crosses the old 21:00
             (ts("2026-03-02 10:00"), ts("2026-03-02 14:00"), 0),   # a day trade
             (ts("2026-03-02 22:00"), ts("2026-03-03 20:00"), 1),   # crosses midnight
             (ts("2026-03-03 01:00"), ts("2026-03-03 03:00"), 0),   # after midnight only
             (ts("2026-03-02 09:00"), ts("2026-03-04 09:00"), 1),   # multi-day
             (ts("2026-03-02 21:30"), ts("2026-03-02 23:30"), 1)]   # inside the band
    for e, x, want in cases:
        assert RR.spans_evening([e], [x]) == (1, want), (e, x)
    assert RR.spans_evening([], []) == (0, 0)


def test_the_trigger_fires_on_a_rollover_change_and_only_then(tmp_path: Path, monkeypatch) -> None:
    con = REC.connect(tmp_path / "r.sqlite")
    old = {"rollover_hour": 21, "triple_swap_weekday": 2, "counter_sha": "a", "fp": "21/2/a"}
    new = {"rollover_hour": 24, "triple_swap_weekday": 2, "counter_sha": "b", "fp": "24/2/b"}
    assert RR.detect_change(con, old)["active"] is False        # baseline at the old value
    assert RR.detect_change(con, old)["active"] is False
    ch = RR.detect_change(con, new)
    assert ch["active"] and ch["from"] == "21/2/a" and ch["to"] == "24/2/b"
    assert RR.detect_change(con, new)["active"]                  # stays active once changed
    con.close()
    # first sight already changed (pass 2 landed before this organ ran): fires
    con2 = REC.connect(tmp_path / "r2.sqlite")
    assert RR.detect_change(con2, new)["active"]
    con2.close()
    # the live engine today is the pre-pass-2 value
    assert RR.fingerprint()["rollover_hour"] in (21, 24)


def test_the_queue_holds_every_certified_sleeve_and_every_spanning_cell(
        tmp_path: Path, monkeypatch) -> None:
    con = REC.connect(tmp_path / "r.sqlite")
    REC.set_meta(con, RR.META_FP, "21/2/old")
    con.commit()
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps({"survivors": {"a": {"cell": "EURUSD.x.p=1"},
                                               "b": {"cell": "XAUUSD.y.p=2"}}}))
    spans = {"c1": 1, "c2": 0, "c3": None}

    def _pool(specs, workers, budget_s):
        return [{"cid": sp["cid"], "span": spans[sp["cid"]], "n_trades": 3,
                 "n_spanning": spans[sp["cid"]] or 0, "why": "measured"} for sp in specs]
    monkeypatch.setattr(RR, "_pool", _pool)
    q = tmp_path / "priority_rollover_rejudge.json"
    judged = [{"cid": c, "sym": "EURUSD", "family": "f", "params": {}, "tf": "H1"}
              for c in spans]
    doc = RR.run(con, judged, workers=1, budget_s=10, queue_path=q, canon_path=canon)
    assert doc["status"] == "QUEUED" and doc["certified_sleeves"] == 2
    assert doc["spanning_cells"] == 1 and doc["pending_measurement"] == 1   # c3 unmeasured
    cells = json.loads(q.read_text())["cells"]
    assert set(cells) == {"EURUSD.x.p=1", "XAUUSD.y.p=2", "c1"}
    # the stage-2 order reads it as named priority
    t = REC.tiers(["c1", "c2"], tmp_path / "none.sqlite", REC.priority_cells([q]))
    assert t["c1"] == (REC.TIER_PRIORITY, 0.0) and t["c2"] == REC.UNRULED_RANK
    con.close()


def test_the_zero_spread_list_waits_for_the_patch_then_queues_once(tmp_path: Path) -> None:
    meta = {"EURUSD": {"median_spread_pts": 0.0}, "USDJPY": {"median_spread_pts": 0.0},
            "EURZAR": {"median_spread_pts": 300.0}}
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps({"survivors": {
        "1": {"cell": "EURUSD.a", "sym": "EURUSD", "gates": {"stress_costs": {"passed": True}}},
        "2": {"cell": "EURZAR.b", "sym": "EURZAR", "gates": {"stress_costs": {"passed": True}}},
        "3": {"cell": "USDJPY.c", "sym": "USDJPY", "gates": {"stress_costs": {"passed": False}}},
    }}))
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in (
        {"at": "2026-09-01T00:00:00+00:00", "cell": "USDJPY.d", "sym": "USDJPY",
         "terminal_gate": "lockbox"},
        {"at": "2026-09-01T00:00:00+00:00", "cell": "USDJPY.e", "sym": "USDJPY",
         "terminal_gate": "cpcv"},
        {"at": "2026-09-01T00:00:00+00:00", "cell": "EURUSD.f", "sym": "EURUSD",
         "terminal_gate": "PASSED"})) + "\n")
    lst = tmp_path / "priority_rejudge_zero_spread.json"
    con = REC.connect(tmp_path / "r.sqlite")

    def _G(landed: bool):
        def costs_for(sym, meta_, mult=1.0):
            return types.SimpleNamespace(spread_per_lot=0.05 * (mult if landed else 1.0))
        return types.SimpleNamespace(costs_for=costs_for, COST_SCENARIO=3.0)
    kw = {"list_path": lst, "canon": canon, "report": tmp_path / "none.json", "ledger": ledger}
    doc = ZR.run(con, _G(False), meta, **kw)
    assert doc["status"] == "WAITING_FOR_SEALED_PATCH" and doc["would_queue"] == 3
    assert json.loads(lst.read_text())["cells"] == []
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    doc = ZR.run(con, _G(True), meta, now=t0, **kw)
    assert doc["status"] == "QUEUED"
    assert json.loads(lst.read_text())["cells"] == ["EURUSD.a", "EURUSD.f", "USDJPY.d"]
    assert REC.tiers(["USDJPY.d"], tmp_path / "x.sqlite",
                     REC.priority_cells([lst]))["USDJPY.d"] == (REC.TIER_PRIORITY, 0.0)
    # re-judged after landing: it leaves the list
    with ledger.open("a") as fh:
        fh.write(json.dumps({"at": "2026-10-01T06:00:00+00:00", "cell": "USDJPY.d",
                             "sym": "USDJPY", "terminal_gate": "stress_costs"}) + "\n")
    ZR.run(con, _G(True), meta, now=t0 + timedelta(hours=7), **kw)
    assert json.loads(lst.read_text())["cells"] == ["EURUSD.a", "EURUSD.f"]
    # and the list is a one-time front: it expires
    doc = ZR.run(con, _G(True), meta, now=t0 + timedelta(days=ZR.TTL_DAYS + 1), **kw)
    assert doc["status"] == "EXPIRED" and json.loads(lst.read_text())["cells"] == []
    con.close()
