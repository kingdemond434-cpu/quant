"""The decay monitor's MODEL half: a fitted half-life per sleeve, and a successor hunt in time.

AUDIT P7 (2026-09-08): the demotion half was lit; the model half was absent -- no per-sleeve
half-life, and the allocator charged every sleeve one blanket 30% decay probability. AUDIT P16:
replacement began only AFTER a retirement, so the lead time was exactly zero.

What is pinned, and each is a way this could quietly become the demotion rule it must not be:

  * the fit RECOVERS a known exponential: a series decaying with a 10-day half-life reads 10;
  * a rising series is MEASURED with no finite half-life, never a fabricated one;
  * too few trades, no positive expectancy to decay from, or no calendar span reads UNMEASURED
    with the n -- a number about noise is worse than a refusal;
  * `t_to_fade` is measured to the desk's OWN weak-edge bar (promoter.RETIRE_MIN_EXP) and the
    successor lead time is the forward bar (shadow_forward.VERDICT_MIN_DAYS), both pinned equal;
  * the model reads BOTH roster shapes (the promoter writes a list; the verdict loop reads a
    dict) and moves NO verdict, action, size or slot -- the FADE/RETIRE constants and the verdict
    function are byte-for-byte what they were;
  * a successor_hunt goes into the deepening queue under source `decay_monitor`, replacing only
    its own rows, and only for a LIVE sleeve whose half-life is under 2x the forward window.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.regime_coverage as rc  # noqa: E402
from research import decay_monitor as D  # noqa: E402

NOW = datetime.now(tz=UTC).replace(microsecond=0)
HL = 10.0
LAM = math.log(2.0) / HL


def _exp_series(days: int = 30, e0: float = 0.5, lam: float = LAM) -> list[tuple[float, float]]:
    """One trade per day whose R IS the expectancy e0 * exp(-lam t): the rolling mean of an
    exponential over equally spaced trades is an exponential with the same rate, so the fit is
    exact and the test can check the number, not just its sign."""
    return [(float(d), e0 * math.exp(-lam * d)) for d in range(days)]


def _stamped(name: str, series: list[tuple[float, float]]) -> list[dict]:
    last = max(t for t, _ in series)
    return [{"sleeve": name, "r_multiple": r,
             "time": (NOW - timedelta(days=last - t)).isoformat()} for t, r in series]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Every path the monitor reads or writes on tmp_path -- the roster, ledgers, artifact, the
    forward-clock ledgers AND the deepening queue, through the real shared writer."""
    monkeypatch.setattr(D, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(D, "SHADOW_LEDGER_DIRS", (tmp_path / "shadow",))
    monkeypatch.setattr(rc, "QUEUE", tmp_path / "queue.json")

    class Desk:
        root = tmp_path

        def roster_list(self, rows: list[dict]) -> None:            # the promoter's shape
            (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")

        def roster_dict(self, rows: dict[str, dict]) -> None:       # the verdict loop's shape
            (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")

        def live(self, rows: list[dict]) -> None:
            (tmp_path / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), "utf-8")

        def shadow(self, name: str, rows: list[dict]) -> None:
            d = tmp_path / "shadow"
            d.mkdir(exist_ok=True)
            (d / f"ledger_{name.replace('.', '_')}.json").write_text(json.dumps(rows), "utf-8")

        def queue(self, rows: list[dict]) -> None:
            (tmp_path / "queue.json").write_text(json.dumps({"tasks": rows}), "utf-8")

        def read_queue(self) -> list[dict]:
            p = tmp_path / "queue.json"
            return json.loads(p.read_text("utf-8"))["tasks"] if p.exists() else []

        def out(self) -> dict:
            return json.loads((tmp_path / "decay_live.json").read_text("utf-8"))

    return Desk()


# --------------------------------------------------------------------------------- the fit
def test_the_fit_recovers_a_known_half_life_and_the_time_to_the_floor() -> None:
    m = D.fit_half_life(_exp_series(), "live_ledger")
    assert m["status"] == "MEASURED" and m["direction"] == "decaying"
    assert m["half_life_days"] == pytest.approx(HL, abs=0.05)
    assert m["lambda_per_day"] == pytest.approx(LAM, abs=1e-4)
    assert m["fit_r2"] == pytest.approx(1.0, abs=1e-3)
    assert m["n"] == 30 and m["fit_points"] == 26 and m["basis"] == "live_ledger"
    # continued from its last fitted point at the fitted rate, the expectancy reaches the floor
    e_now, ttf = m["expectancy_now_r"], m["t_to_fade_days"]
    assert 0.0 < ttf < HL
    assert e_now * math.exp(-LAM * ttf) == pytest.approx(D.FADE_FLOOR_R, rel=0.02)
    assert "halves every 10.0 day(s)" in m["why"]


def test_a_rising_edge_is_measured_with_no_finite_half_life() -> None:
    m = D.fit_half_life(_exp_series(lam=-LAM, e0=0.05), "live_ledger")
    assert m["status"] == "MEASURED" and m["direction"] == "rising"
    assert m["half_life_days"] is None and m["t_to_fade_days"] is None
    assert m["lambda_per_day"] < 0 and "not finite" in m["why"]


def test_a_flat_edge_reads_flat_not_decaying() -> None:
    m = D.fit_half_life([(float(d), 0.3) for d in range(20)], "live_ledger")
    assert m["status"] == "MEASURED" and m["direction"] == "flat"
    assert m["half_life_days"] is None


def test_too_few_trades_is_unmeasured_with_the_n() -> None:
    m = D.fit_half_life(_exp_series(days=D.MIN_FIT_TRADES - 1), "live_ledger")
    assert m["status"] == "UNMEASURED" and m["n"] == D.MIN_FIT_TRADES - 1
    assert m["half_life_days"] is None and f"{D.MIN_FIT_TRADES - 1} trailing trade" in m["why"]
    assert D.fit_half_life([], "none")["why"].startswith("0 trailing trade(s)")


def test_an_edge_that_is_absent_has_no_half_life_and_says_the_demotion_half_owns_that() -> None:
    m = D.fit_half_life([(float(d), -1.0 + 0.01 * (d % 3)) for d in range(30)], "live_ledger")
    assert m["status"] == "UNMEASURED" and m["fit_points"] == 0
    assert "positive rolling-expectancy point" in m["why"] and "demotion half" in m["why"]


def test_no_calendar_span_is_unmeasured_because_a_rate_needs_time() -> None:
    within_an_hour = [(d / 1440.0, 0.5 - 0.01 * d) for d in range(15)]
    m = D.fit_half_life(within_an_hour, "live_ledger")
    assert m["status"] == "UNMEASURED" and "calendar time" in m["why"]
    assert m["span_days"] < D.MIN_FIT_SPAN_DAYS


# --------------------------------------------------------------------------- the constants
def test_the_floor_and_the_lead_time_are_the_desks_own_bars_and_no_verdict_moved() -> None:
    import promoter
    assert D.FADE_FLOOR_R == promoter.RETIRE_MIN_EXP == 0.05
    src = (_DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert int(re.search(r"^VERDICT_MIN_DAYS = (\d+)", src, re.M).group(1)) == D.FORWARD_BAR_DAYS
    assert D.FORWARD_BAR_DAYS == 14 and D.SUCCESSOR_HALF_LIFE_MULT == 2.0
    # the demotion half, exactly as it stood
    assert (D.T_PROMOTE, D.N_MIN_VERDICT, D.DD_HARD_R, D.FADE_FACTOR) == (2.5, 20, -25.0, 0.5)
    assert (D.TRAIL_DAYS, D.TRAIL_MAX_TRADES) == (45, 60)
    dsrc = (_DESK / "research" / "decay_monitor.py").read_text("utf-8")
    verdict_src = dsrc[dsrc.index("def verdict("):dsrc.index("def source_state(")]
    assert "half_life" not in verdict_src and "t_to_fade" not in verdict_src
    loop = dsrc[dsrc.index("    live = {k: v for k, v in sleeves.items()"):
                dsrc.index("    if changed:")]
    assert "half_life" not in loop and "models" not in loop, (
        "the verdict loop must read nothing from the model")


# ----------------------------------------------------------------- the pass, both shapes
def _live_row(name: str, **kw) -> dict:
    return {"name": name, "symbol": "CADJPY", "family": "session_range_breakout",
            "window": "asia", "state": None, "status": "LIVE", "risk_frac": 0.03, **kw}


def test_a_promoter_shaped_roster_gets_a_half_life_and_a_successor_hunt_and_no_verdict(desk):
    """The promoter writes a LIST. The verdict loop reads a DICT and judges none of it -- a
    standing defect this wave reports and does not touch. The model half reads both."""
    name = "CADJPY.asia"
    desk.roster_list([_live_row(name)])
    before = (desk.root / "sleeves.json").read_bytes()
    desk.live(_stamped(name, _exp_series()))
    desk.queue([{"source": "alpha_breadth", "kind": "empty_alpha_cluster", "title": "keep me"},
                {"source": "decay_monitor", "kind": "successor_hunt", "title": "stale"}])
    assert D.main() == 0
    out = desk.out()
    m = out["decay_model"][name]
    assert m["status"] == "MEASURED" and m["half_life_days"] == pytest.approx(HL, abs=0.05)
    assert m["basis"] == "live_ledger" and m["roster_status"] == "LIVE"
    assert out["verdicts"] == {} and out["actions_taken"] == []        # the loop, unchanged
    assert out["live_sleeves"] == 0 and out["roster_rows_seen"] == 1
    assert "LIST" in out["roster_shape_note"] and "NOT changed" in out["roster_shape_note"]
    assert (desk.root / "sleeves.json").read_bytes() == before, "the model must not edit the roster"
    assert not (desk.root / "decay_actions.jsonl").exists()
    (task,) = out["successor_hunts"]
    assert task["source"] == "decay_monitor" and task["kind"] == "successor_hunt"
    assert task["sleeve"] == name and task["symbol"] == "CADJPY"
    assert task["family"] == task["mechanism"] == "session_range_breakout"
    assert task["selector"] == "asia" and task["status"] is None
    assert task["half_life_days"] == m["half_life_days"]
    assert task["remaining_forward_window_days"] == D.FORWARD_BAR_DAYS
    assert task["successor_lead_days"] == 2 * D.FORWARD_BAR_DAYS
    assert task["title"] == ("Successor hunt: session_range_breakout on CADJPY "
                             "(incumbent CADJPY.asia)")
    assert "Nothing retires" in task["description"] and "different payer" in task["description"]
    datetime.fromisoformat(task["issued_at"])
    assert out["queue"]["written"] is True and out["queue"]["n_tasks"] == 1
    # the shared writer replaced ONLY this source's rows
    q = desk.read_queue()
    assert [t["title"] for t in q if t["source"] == "alpha_breadth"] == ["keep me"]
    assert [t["title"] for t in q if t["source"] == "decay_monitor"] == [task["title"]]


def test_a_dict_shaped_roster_carries_the_half_life_on_its_verdict_row_and_hunts_nothing_slow(
        desk):
    name = "EURJPY.asia"
    desk.roster_dict({name: {"symbol": "EURJPY", "family": "session_range_breakout",
                             "risk_frac": 0.03}})
    desk.live(_stamped(name, _exp_series(lam=math.log(2.0) / 200.0)))   # 200-day half-life
    assert D.main() == 0
    out = desk.out()
    v = out["verdicts"][name]
    assert v["verdict"] == "HEALTHY" and "decay_faded" not in json.dumps(out["verdicts"])
    assert v["half_life_days"] == pytest.approx(200.0, rel=0.02)
    assert v["decay_model"] == "MEASURED" and v["t_to_fade_days"] > 2 * D.FORWARD_BAR_DAYS
    assert out["successor_hunts"] == [] and out["queue"]["written"] is False
    assert "no LIVE sleeve" in out["queue"]["why"]
    assert out["roster_shape_note"] is None and out["live_sleeves"] == 1
    assert desk.read_queue() == []


def test_a_standby_sleeve_is_modelled_but_not_hunted_for(desk):
    name = "USDJPY.asia"
    desk.roster_list([_live_row(name, status="STANDBY")])
    desk.live(_stamped(name, _exp_series()))
    assert D.main() == 0
    out = desk.out()
    assert out["decay_model"][name]["half_life_days"] == pytest.approx(HL, abs=0.05)
    assert out["decay_model"][name]["roster_status"] == "STANDBY"
    assert out["successor_hunts"] == []


def test_a_retired_row_is_not_modelled(desk):
    desk.roster_list([_live_row("GBPJPY.asia", status="RETIRED")])
    assert D.main() == 0
    assert desk.out()["decay_model"] == {}


def test_a_thin_live_ledger_falls_back_to_the_sleeves_own_forward_clock_and_says_so(desk):
    name = "AUDNZD.asia"
    desk.roster_list([_live_row(name, symbol="AUDNZD")])
    series = _exp_series()
    last = max(t for t, _ in series)
    fwd = [{"entry_time": (NOW - timedelta(days=last - t, hours=1)).isoformat(),
            "exit_time": (NOW - timedelta(days=last - t)).isoformat(),
            "r_multiple": r, "phase": "forward"} for t, r in series]
    desk.shadow(name, fwd)
    assert D.main() == 0
    m = desk.out()["decay_model"][name]
    assert m["basis"] == "shadow_forward" and m["half_life_days"] == pytest.approx(HL, abs=0.05)
    # only historical rows: every row is used and the basis names it
    desk.shadow(name, [{**r, "phase": "historical"} for r in fwd])
    D.main()
    assert desk.out()["decay_model"][name]["basis"] == "shadow_all"
    # nothing at all: UNMEASURED at n=0, basis none
    desk.shadow(name, [])
    D.main()
    m = desk.out()["decay_model"][name]
    assert m["status"] == "UNMEASURED" and m["n"] == 0 and m["basis"] == "none"


def test_the_scalp_ledger_schema_is_read_too(desk):
    name = "xau_m5_test"
    desk.roster_list([_live_row(name, symbol="XAUUSD", family="gold_scalp")])
    series = _exp_series()
    last = max(t for t, _ in series)
    desk.shadow(name, [{"opened_at": (NOW - timedelta(days=last - t, hours=1)).isoformat(),
                        "closed_at": (NOW - timedelta(days=last - t)).isoformat(),
                        "direction": -1, "r": r} for t, r in series])
    D.main()
    assert desk.out()["decay_model"][name]["half_life_days"] == pytest.approx(HL, abs=0.05)


def test_no_queue_publishes_the_model_and_writes_no_task(desk):
    name = "CADJPY.asia"
    desk.roster_list([_live_row(name)])
    desk.live(_stamped(name, _exp_series()))
    assert D.main(write_queue=False) == 0
    out = desk.out()
    assert len(out["successor_hunts"]) == 1 and out["queue"]["written"] is False
    assert "disabled" in out["queue"]["why"] and desk.read_queue() == []


def test_an_unmeasured_roster_publishes_no_model_and_still_fails_loud(desk):
    (desk.root / "sleeves.json").write_text("{not json", "utf-8")
    assert D.main() == 1
    out = desk.out()
    assert out["live_sleeves"] is None and out["decay_model"] == {}
    assert out["successor_hunts"] == []


def test_the_series_uses_the_same_trailing_window_as_the_verdicts(desk):
    name = "CADJPY.asia"
    old = [{"sleeve": name, "r_multiple": 0.9,
            "time": (NOW - timedelta(days=D.TRAIL_DAYS + 5 + i)).isoformat()} for i in range(20)]
    desk.live(old + _stamped(name, _exp_series(days=12)))
    pts, basis, n = D.sleeve_series(name, NOW)
    assert n == 12 and basis == "live_ledger" and len(pts) == 12
    assert pts[0][0] == 0.0 and pts[-1][0] == pytest.approx(11.0)
