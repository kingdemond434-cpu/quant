"""The decay kill switch compares each live sleeve with its own backtest (2026-11-13).

Pinned: a VETOED certificate or a live record that contradicts a reproducing backtest moves a
HEALTHY sleeve to FADE, one step, and nothing else; gold_asia is exempt; the comparison is on
sign and t (unit-free); the monitor publishes the reading per sleeve, judges every name that
traded (roster or not) without acting on unrostered ones, counts R coverage, and the step is
priced like any other decay step.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import decay_backtest as B  # noqa: E402
import decay_monitor as D  # noqa: E402
import decay_regime as R  # noqa: E402

CELL = "external.USDNOK@M5.carry.p=ff35bb7c8427d66f"


def _row(cell: str = CELL) -> dict:
    return {"name": "usdnok_carry", "status": "LIVE", "certificate": {"cell": cell}}


def _rev(verdict: str, t: float | None = 4.0) -> dict:
    return {"cell": CELL, "verdict": verdict, "at": "2026-11-11T10:00:00+00:00",
            "reproduced": {"n": 900, "t": t, "expectancy": 0.1}}


def test_reference_reads_the_certificate_and_its_latest_review() -> None:
    assert B.reference({"name": "x"}, {})["status"] == "UNMEASURED"
    assert B.reference(_row(), {})["status"] == "UNMEASURED"
    reviews = B.latest_reviews([_rev("PASS"), _rev("VETO")])
    ref = B.reference(_row(), reviews)
    assert ref["status"] == "MEASURED" and ref["verdict"] == "VETO"
    # a roster row carrying the bare cell still finds a `<hunt>.<cell>` ledger key
    bare = B.reference(_row("USDNOK@M5.carry.p=ff35bb7c8427d66f"), reviews)
    assert bare["status"] == "MEASURED"


@pytest.mark.parametrize("s,rev,want", [
    ({"n": 30, "t": 1.5, "exp_r": 0.2}, _rev("VETO"), "VETO"),
    ({"n": 30, "t": -2.5, "exp_r": -0.3}, _rev("PASS", 4.0), "CONTRADICTS"),
    ({"n": 9, "t": -3.0, "exp_r": -0.3}, _rev("PASS", 4.0), "AGREES"),       # too few trades
    ({"n": 30, "t": -2.5, "exp_r": -0.3}, _rev("PASS", 1.0), "AGREES"),      # repro not strong
    ({"n": 30, "t": -1.0, "exp_r": -0.1}, _rev("PASS", 4.0), "AGREES"),      # live not strong
])
def test_the_gap_is_judged_on_sign_and_t(s: dict, rev: dict, want: str) -> None:
    ref = B.reference(_row(), B.latest_reviews([rev]))
    assert B.gap(s, ref)[0] == want


def test_it_fades_a_healthy_sleeve_one_step_and_never_retires() -> None:
    ref = B.reference(_row(), B.latest_reviews([_rev("VETO")]))
    s = {"n": 30, "t": 1.0, "exp_r": 0.1}
    assert B.adjust("usdnok_carry", "HEALTHY", "w", s, ref)[:3][0::2] == \
        ("FADE", "HEALTHY->FADE:veto")
    for v in ("FADE", "RETIRE"):
        got = B.adjust("usdnok_carry", v, "w", s, ref)
        assert got[0] == v and got[2] is None
    assert B.adjust("gold_asia", "HEALTHY", "w", s, ref)[0] == "HEALTHY"


def test_the_step_is_priced_as_the_move_it_makes() -> None:
    assert R.step_value("HEALTHY->FADE:veto", [-1.0, -1.0])["value_r"] == pytest.approx(1.0)
    assert R.step_value("HEALTHY->FADE:contradicts", [1.5])["value_r"] == pytest.approx(-0.75)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(D, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(D, "CLOSE_QUEUE", tmp_path / "close_queue.json")
    monkeypatch.setattr(D, "SHADOW_LEDGER_DIRS", (tmp_path / "shadow",))
    return tmp_path


def _ledger(desk: Path, rs_by_name: dict[str, list]) -> None:
    t0 = datetime.now(tz=UTC) - timedelta(days=2)
    with (desk / "live_ledger.jsonl").open("w", encoding="utf-8") as fh:
        for n, rs in rs_by_name.items():
            for i, r in enumerate(rs):
                row = {"time": (t0 + timedelta(minutes=i)).isoformat(), "sleeve": n,
                       "r_multiple": r}
                if r is None:
                    row["r_multiple"] = 0.0
                    row["r_unreconstructible"] = True
                fh.write(json.dumps(row) + "\n")


def test_the_monitor_fades_a_vetoed_live_sleeve_and_reads_everything_that_traded(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "usdnok_carry", "status": "LIVE", "family": "carry", "symbol": "USDNOK",
             "risk_frac": 0.03, "certificate": {"cell": CELL}},
            {"name": "old_one", "status": "RETIRED", "family": "carry", "symbol": "EURNOK"}]
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    healthy = [1.0, -0.5, 0.8, 0.6, -0.4, 0.9, 0.7, -0.3]
    _ledger(desk, {"usdnok_carry": healthy, "gold_london_am": [-1.0, -1.0, -1.0, -1.0, -1.0],
                   "gold_asia": [0.5], "x": [None, None]})
    monkeypatch.setattr(D, "_reviews", lambda: (B.latest_reviews([_rev("VETO")]), None))
    assert D.main(write_queue=False) == 0
    out = json.loads((desk / "decay_live.json").read_text("utf-8"))
    v = out["verdicts"]["usdnok_carry"]
    assert v["ladder_verdict"] == "HEALTHY" and v["verdict"] == "FADE"
    assert v["backtest"]["gap"] == "VETO" and v["regime_step"] == "HEALTHY->FADE:veto"
    roster = json.loads((desk / "sleeves.json").read_text("utf-8"))["sleeves"]
    assert next(r for r in roster if r["name"] == "usdnok_carry").get("decay_faded")
    un = out["unrostered_verdicts"]
    assert un["gold_london_am"]["verdict"] == "FADE" and un["gold_london_am"]["acted"] is False
    assert un["gold_asia"]["exempt"] is True
    assert out["r_coverage"]["unreconstructible"] == 2
    assert out["backtest_reference"]["gaps"]["VETO"] == 1
    assert out["roster_status_counts"] == {"LIVE": 1, "RETIRED": 1}


def test_an_unreadable_review_ledger_moves_nothing(desk: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"name": "usdnok_carry", "status": "LIVE", "family": "carry", "symbol": "USDNOK",
             "risk_frac": 0.03, "certificate": {"cell": CELL}}]
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    _ledger(desk, {"usdnok_carry": [1.0, -0.5, 0.8, 0.6, -0.4, 0.9]})
    monkeypatch.setattr(D, "_reviews", lambda: ({}, "UNMEASURED: x"))
    assert D.main(write_queue=False) == 0
    out = json.loads((desk / "decay_live.json").read_text("utf-8"))
    assert out["verdicts"]["usdnok_carry"]["verdict"] == "HEALTHY"
    assert out["verdicts"]["usdnok_carry"]["backtest"]["gap"] == "UNMEASURED"
