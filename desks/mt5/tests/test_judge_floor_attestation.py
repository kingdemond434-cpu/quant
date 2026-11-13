"""Judge floor attestation: pace against the 150k/day floor, the idle gap measured against one of
the judge's own sweeps (never a constant), the core floor, daily rows, and UNMEASURED on absence."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_floor_attestation as jfa  # noqa: E402

NOW = datetime(2026, 11, 14, 1, 30, tzinfo=UTC)


def _rate(d24: int, d7: int | None = None, last: datetime | None = None,
          at: datetime = NOW) -> dict:
    return {"at": at.isoformat(), "verdicts": {
        "status": "MEASURED",
        "last_verdict_at": (last or NOW - timedelta(hours=1)).isoformat(),
        "first_terminal_counts": {"1h": 0, "24h": d24, "7d": d24 * 7 if d7 is None else d7}}}


def _resident(sweep_s: float, rc: int = 0) -> dict:
    return {"last_sweep_s": sweep_s, "last_rc": rc, "heartbeat_utc": NOW.isoformat()}


def _core(busy: float, floor: float = 6, mode: str = "FLOOR") -> dict:
    return {"at": NOW.isoformat(), "floor": floor, "judge_busy_cores": busy, "mode": mode,
            "reserved_cores": list(range(int(floor))), "miner_busy_cores": 10.0,
            "pace": {"floor": 150_000}}


def test_floor_met_and_clean_is_green() -> None:
    doc = jfa.assess(NOW, rate=_rate(160_000), stall=None, resident=_resident(6 * 3600),
                     core=_core(6.5), history=[])
    assert doc["pace"]["status"] == "MET" and doc["idle_gap"]["status"] == "OK"
    assert doc["cores"]["status"] == "OK" and doc["status"] == "GREEN"


def test_tenth_of_the_floor_is_red_with_the_shortfall_named() -> None:
    doc = jfa.assess(NOW, rate=_rate(15_625, 79_515), stall=None,
                     resident=_resident(6 * 3600), core=_core(6.5), history=[])
    p = doc["pace"]
    assert p["status"] == "BELOW" and doc["status"] == "RED"
    assert p["shortfall_cells_7d"] == 7 * 150_000 - 79_515
    assert "10.4%" in doc["why"][0]


def test_short_of_floor_is_amber() -> None:
    doc = jfa.assess(NOW, rate=_rate(130_000), stall=None, resident=_resident(6 * 3600),
                     core=_core(6.5), history=[])
    assert doc["pace"]["status"] == "SHORT" and doc["status"] == "AMBER"


def test_idle_gap_limit_is_the_judges_own_sweep_not_a_constant() -> None:
    last = NOW - timedelta(hours=9)
    # a 6 h sweep: 9 h without a verdict is IDLE (limit 7.5 h) ...
    doc = jfa.assess(NOW, rate=_rate(160_000, last=last), stall=None,
                     resident=_resident(6 * 3600), core=_core(6.5), history=[])
    assert doc["idle_gap"]["status"] == "IDLE" and doc["status"] == "RED"
    assert doc["idle_gap"]["limit_h"] == 7.5
    # ... a 10 h sweep: the same 9 h is inside one sweep.
    doc = jfa.assess(NOW, rate=_rate(160_000, last=last), stall=None,
                     resident=_resident(10 * 3600), core=_core(6.5), history=[])
    assert doc["idle_gap"]["status"] == "OK"


def test_lane_held_or_no_op_sweep_never_sets_the_limit() -> None:
    hist = [{"at": (NOW - timedelta(hours=5)).isoformat(), "completed_sweep_s": 6 * 3600.0}]
    # current sweep was lane-held (rc 75) after 29 s: the recorded 6 h sweep is the limit
    g = jfa.idle_gap(_rate(1, last=NOW - timedelta(hours=3)), None, _resident(29, rc=75),
                     hist, NOW)
    assert g["status"] == "OK" and g["sweep_s"] == 6 * 3600.0
    # a 29 s sweep that exited 0 does not shrink the limit below the longest completed one
    g = jfa.idle_gap(_rate(1, last=NOW - timedelta(hours=3)), None, _resident(29, rc=0),
                     hist, NOW)
    assert g["sweep_s"] == 6 * 3600.0


def test_newest_verdict_stamp_wins_across_rate_and_stall() -> None:
    stall = {"last_verdict": {"at": (NOW - timedelta(hours=1)).isoformat()}}
    g = jfa.idle_gap(_rate(1, last=NOW - timedelta(hours=20)), stall, _resident(6 * 3600),
                     [], NOW)
    assert g["status"] == "OK" and "JUDGE_STALL" in g["last_verdict_source"]


def test_burst_gaps_from_the_ledger_tail_when_no_sweep_is_recorded(tmp_path: Path) -> None:
    led = tmp_path / "gate_verdict_ledger.jsonl"
    rows = []
    for b in range(7):                                  # a burst every 6 h, 50 verdicts each
        t0 = NOW - timedelta(hours=6 * (7 - b))
        rows += [{"at": (t0 + timedelta(seconds=i)).isoformat(), "cell": f"c{b}_{i}"}
                 for i in range(50)]
    led.write_text("".join(json.dumps(r) + "\n" for r in rows))
    g = jfa.idle_gap(_rate(1, last=NOW - timedelta(hours=8)), None, _resident(29, rc=75), [],
                     NOW, led)
    assert g["burst_gaps_14d"]["n"] == 6 and g["limit_h"] < 6.1
    assert g["status"] == "IDLE"


def test_core_floor_below_once_then_breach() -> None:
    c = jfa.cores(_core(2.0), [], NOW)
    assert c["status"] == "BELOW"
    hist = [{"at": (NOW - timedelta(hours=1)).isoformat(), "core_under": True}]
    c = jfa.cores(_core(2.0), hist, NOW)
    assert c["status"] == "BREACH" and c["consecutive_under"] == 2
    assert jfa.cores(_core(0.0, mode="IDLE"), hist, NOW)["status"] == "NOT_APPLICABLE"


def test_absent_inputs_are_unmeasured_never_green() -> None:
    doc = jfa.assess(NOW, rate=None, stall=None, resident=None, core=None, history=[])
    assert doc["status"] == "UNMEASURED"
    stale = _rate(160_000, at=NOW - timedelta(hours=5))
    doc = jfa.assess(NOW, rate=stale, stall=None, resident=_resident(6 * 3600),
                     core=_core(6.5), history=[])
    assert doc["pace"]["status"] == "UNMEASURED" and doc["status"] == "UNMEASURED"


def test_daily_rows_and_streak() -> None:
    hist = []
    for k in range(1, 5):                     # readings at 00:40 UTC for the last 4 days
        at = NOW.replace(hour=0, minute=40) - timedelta(days=k - 1)
        hist.append({"at": at.isoformat(), "first_terminal_24h": 160_000 if k <= 2 else 9_000})
    hist.append({"at": (NOW.replace(hour=12) - timedelta(days=1)).isoformat(),
                 "first_terminal_24h": 1})            # midday reading: not a day's row
    d = jfa.daily_attestation(hist, NOW, 150_000, days=5)
    assert [r["verdict"] for r in d["days"]] == ["UNMEASURED", "BELOW", "BELOW", "MET", "MET"]
    assert d["met_streak_days"] == 2 and d["days_measured"] == 4


def test_run_writes_report_and_bounded_history(tmp_path: Path) -> None:
    rp, rs = tmp_path / "rate.json", tmp_path / "res.json"
    rp.write_text(json.dumps(_rate(15_625)))
    rs.write_text(json.dumps(_resident(6 * 3600)))
    h = tmp_path / "h.jsonl"
    for i in range(3):
        doc = jfa.run(NOW + timedelta(hours=i), out=tmp_path / "o.json", history_path=h,
                      rate_p=rp, stall_p=tmp_path / "x", resident_p=rs,
                      core_p=tmp_path / "y", ledger_p=tmp_path / "z")
    assert doc["schema"] == jfa.SCHEMA and doc["status"] == "RED"
    rows = [json.loads(x) for x in h.read_text().splitlines()]
    assert len(rows) == 3 and rows[-1]["completed_sweep_s"] == 6 * 3600
    assert json.loads((tmp_path / "o.json").read_text())["status"] == "RED"
