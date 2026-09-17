"""The program-alpha lane: its seeds, its optimiser, its memory, and what it refuses to donate.

WHAT IS PINNED HERE, and why each one is a thing a reading cannot establish:

  THE TEMPLATES ARE RUNNABLE PROGRAMS, not illustrations. Each one validates, evaluates on bars
  and compiles to signals -- a seed library whose seeds cannot fire is a lane that searches
  nothing and reports zero as if it were a finding.

  THE OPTIMISER ACTUALLY OPTIMISES. A planted optimum is recovered: the last draws sit closer to
  it than the first. A TPE that never concentrates is a uniform sampler with a citation.

  THE DATABASE IS A DATABASE. It survives a round trip and DEDUPES BY FINGERPRINT, so a program
  rediscovered next hour accumulates evidence instead of becoming a second row that splits it.

  THE WIRING GAP IS HONEST. Winners are written with their full IR and marked unexecutable, and
  the lane does not donate them into the miner-discovery contract under a family that cannot run
  them. `--dry-run` writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import program_ir as ir  # noqa: E402
from research import program_alpha_lane as lane  # noqa: E402


def _bars(n: int = 1200, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 1900.0 * np.exp(np.cumsum(rng.normal(0.0, 0.0012, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0.0, 0.7, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.0, 0.7, n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(60, 600, n).astype(float)}, index=idx)


def _extras(bars: pd.DataFrame) -> ir.Extras:
    cal = [{"kind": k, "window_start_utc": t.isoformat()}
           for k in ("month_end", "fixing")
           for t in pd.date_range(bars.index[0], bars.index[-1], freq="7D")]
    return ir.Extras(cross={"GBPUSD": _bars(len(bars), seed=8)}, calendar=cal, symbol="EURUSD")


# --------------------------------------------------------------------------- the seed library
def test_every_template_validates_evaluates_and_compiles() -> None:
    bars = _bars()
    extras = _extras(bars)
    tmpl = lane.templates("EURUSD")
    assert set(tmpl) >= {"session_range_breakout", "event_clock_drift", "adaptive_reversion"}
    for name, tree in tmpl.items():
        assert ir.validate(tree) == [], f"{name}: {ir.validate(tree)}"
        series = ir.evaluate(tree, bars, extras)
        assert len(series) == len(bars)
        nonzero = int((series.fillna(0.0) != 0.0).sum())
        assert nonzero > 0, f"{name} never leaves zero -- a seed that cannot fire"
        sigs = ir.compile_program(tree, extras, tag=lane.SOURCE)(bars, 1)
        assert sigs, f"{name} compiled to no signals"
        assert {s.side for s in sigs} <= {1, -1}


def test_templates_cover_the_four_program_shapes() -> None:
    """One template per thing an EXPRESSION cannot say. That is the lane's whole reason."""
    trees = lane.templates("EURUSD")
    kinds = {name: {type(n).__name__ for n in ir.walk(tree)} for name, tree in trees.items()}
    assert "State" in kinds["session_range_breakout"]
    assert "EventClock" in kinds["event_clock_drift"]
    assert "Adaptive" in kinds["adaptive_reversion"]
    assert "CrossRef" in kinds["cross_asset_residual"]
    assert all("Slot" in k for k in kinds.values()), "a template with no slot cannot be tuned"


def test_cross_asset_template_is_absent_without_a_peer_on_disk() -> None:
    """An absent reference is not a reason to substitute a different instrument."""
    assert "cross_asset_residual" not in lane.templates("NOSUCHSYM")


# --------------------------------------------------------------------------- the optimiser
def test_tpe_recovers_a_planted_optimum() -> None:
    box = [ir.Slot("w", 5.0, 200.0, 50.0), ir.Slot("k", 0.0, 4.0, 2.0)]
    planted = {"w": 140.0, "k": 0.7}
    rng = np.random.default_rng(0)
    history: list[tuple[dict[str, float], float]] = []
    errors: list[float] = []
    for _ in range(60):
        vals = lane._tpe_ask(box, history, rng)
        err = abs(vals["w"] - planted["w"]) / 195.0 + abs(vals["k"] - planted["k"]) / 4.0
        history.append((vals, -err))
        errors.append(err)
    assert float(np.mean(errors[-10:])) < 0.6 * float(np.mean(errors[:10]))


def test_tpe_with_no_history_is_a_draw_inside_the_box() -> None:
    """A surrogate fitted on nothing is a prior, not a model -- and it stays inside the bounds."""
    box = [ir.Slot("w", 5.0, 200.0, 50.0)]
    rng = np.random.default_rng(1)
    for _ in range(20):
        vals = lane._tpe_ask(box, [], rng)
        assert 5.0 <= vals["w"] <= 200.0


def test_t_net_is_the_screen_t_after_the_round_trip() -> None:
    sc = {"gross_per_trade": 0.0010, "cost_frac": 0.0004, "t_gross": 5.0}
    assert lane._t_net(sc) == pytest.approx(3.0)        # (10 - 4) / 10 * 5
    assert lane._t_net({"gross_per_trade": 0.0, "cost_frac": 0.0, "t_gross": 4.0}) == float("-inf")


# --------------------------------------------------------------------------- the database
def _program(name: str, tree: ir.Node, evals: list[dict] | None = None) -> lane.Program:
    return lane.Program(ir.fingerprint(tree), name, tree, {"op": "template"}, evals or [],
                        "2026-09-17T00:00:00+00:00")


def test_program_db_round_trips_and_dedupes_by_fingerprint(tmp_path: Path) -> None:
    db_path = tmp_path / "program_db.jsonl"
    tree = lane.templates("EURUSD")["adaptive_reversion"]
    first = _program("adaptive_reversion", tree, [{"symbol": "EURUSD", "t_net": 1.5}])
    lane.save_db({first.fingerprint: first}, db_path)

    # A SECOND ROW FOR THE SAME LOGIC, as a careless appender would write it.
    with db_path.open("a", encoding="utf-8") as handle:
        duplicate = _program("adaptive_reversion", ir.from_json(ir.to_json(tree)),
                             [{"symbol": "XAUUSD", "t_net": 2.5}])
        handle.write(json.dumps(duplicate.row(), default=str) + "\n")

    back = lane.load_db(db_path)
    assert len(back) == 1, "two spellings of one program must not become two rows"
    only = next(iter(back.values()))
    assert only.tree == tree
    assert {e["symbol"] for e in only.evaluations} == {"EURUSD", "XAUUSD"}
    assert only.best() == pytest.approx(2.5)

    lane.save_db(back, db_path)
    assert len(lane.load_db(db_path)) == 1
    row = json.loads(db_path.read_text("utf-8").splitlines()[0])
    assert row["fingerprint"] == ir.fingerprint(tree)
    assert ir.from_json(row["tree"]) == tree
    assert row["describe"] and row["best_t_net"] == pytest.approx(2.5)


def test_program_db_drops_rows_the_ir_would_refuse_today(tmp_path: Path) -> None:
    """The caps are the contract. A program that would be refused may not re-enter a population."""
    db_path = tmp_path / "program_db.jsonl"
    db_path.write_text(json.dumps({"fingerprint": "x", "name": "bad", "tree":
                                   {"node": "series", "field": "vwap"}}) + "\n"
                       + json.dumps({"fingerprint": "y", "name": "torn"}) + "\n", "utf-8")
    assert lane.load_db(db_path) == {}


def test_missing_database_is_empty_not_an_error(tmp_path: Path) -> None:
    assert lane.load_db(tmp_path / "absent.jsonl") == {}


# --------------------------------------------------------------------------- the candidates path
def test_winners_are_written_with_their_ir_and_marked_unexecutable(tmp_path: Path,
                                                                   monkeypatch) -> None:
    tree = lane.templates("EURUSD")["session_range_breakout"]
    winner = {"symbol": "XAUUSD", "name": "session_range_breakout", "side": 1,
              "fingerprint": ir.fingerprint(tree), "tree": ir.to_json(tree),
              "describe": ir.describe(tree), "slots": {"range_n": 24.0, "stop_atr": 1.2},
              "n_independent": 91, "gross_per_trade": 0.0011, "net_per_trade": 0.0006,
              "cost_frac": 0.0005, "t_gross": 3.1, "t_deflated_sweep": 2.4, "n_tests_sweep": 40}
    out = tmp_path / "program_candidates.jsonl"
    monkeypatch.setattr(lane, "CANDIDATES", out)
    rows = lane._write_candidates([winner], tests_run=40)
    assert len(rows) == 1
    written = json.loads(out.read_text("utf-8").splitlines()[0])
    assert written["family"] == lane.SOURCE
    assert written["executable"] is False and written["why_not_donated"]
    assert ir.from_json(written["program"]) == tree, "the full IR must ride on the candidate"
    assert written["available_time"], "an unstamped row may not be written (PIT contract)"
    assert written["evidence"]["t_deflated_sweep"] == pytest.approx(2.4)
    # Appending is how the file grows; the fingerprint is what keeps it joinable.
    lane._write_candidates([winner], tests_run=40)
    assert len(out.read_text("utf-8").splitlines()) == 2


def test_no_registered_family_can_execute_a_program() -> None:
    """The wiring gap, measured rather than asserted -- this is why nothing is donated."""
    from mt5desk.families import get_family_func
    assert get_family_func(lane.SOURCE) is None
    from mt5desk.family_generic import supported
    axes = supported()
    assert set(axes) == {"event", "context", "direction", "output"}
    assert not any("state" in v or "program" in v for vals in axes.values() for v in vals)


# --------------------------------------------------------------------------- the run
def test_budget_is_binding_and_reported_as_unmeasured(tmp_path: Path) -> None:
    rep = lane.run(symbols=["EURUSD", "XAUUSD"], budget_s=0.0, max_programs=3, dry_run=True,
                   db_path=tmp_path / "db.jsonl")
    assert rep["n_evaluated"] == 0
    assert any("budget" in v for v in rep["unmeasured"].values())
    assert rep["top"] == [] and rep["n_donated"] == 0


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    report = tmp_path / "PROGRAM_ALPHA_LANE.json"
    cands = tmp_path / "program_candidates.jsonl"
    db = tmp_path / "program_db.jsonl"
    monkeypatch.setattr(lane, "REPORT", report)
    monkeypatch.setattr(lane, "CANDIDATES", cands)
    monkeypatch.setattr(lane, "PROGRAM_DB", db)
    assert lane.main(["--dry-run", "--symbols", "EURUSD", "--budget-s", "0"]) == 0
    assert not report.exists() and not cands.exists() and not db.exists()
    assert "DRY RUN" in capsys.readouterr().out


@pytest.mark.skipif(not (DESK / "data" / "universe" / "EURUSD_H1.parquet").exists(),
                    reason="no EURUSD H1 parquet on this box")
def test_a_real_pass_publishes_the_report_and_remembers_the_programs(tmp_path: Path,
                                                                     monkeypatch) -> None:
    report = tmp_path / "PROGRAM_ALPHA_LANE.json"
    db = tmp_path / "program_db.jsonl"
    monkeypatch.setattr(lane, "REPORT", report)
    monkeypatch.setattr(lane, "CANDIDATES", tmp_path / "program_candidates.jsonl")
    rep = lane.run(symbols=["EURUSD"], budget_s=25.0, max_programs=2, seed=3, db_path=db)

    assert set(rep) >= {"at", "n_seeds", "n_evaluated", "n_donated", "top", "db_size",
                        "unmeasured", "rule"}
    assert rep["n_seeds"] > 0 and rep["db_size"] > 0
    assert report.exists()
    published = json.loads(report.read_text("utf-8"))
    assert published["n_evaluated"] == rep["n_evaluated"] and published["wiring_gap"]
    for row in published["top"]:
        assert set(row) == {"fingerprint", "describe", "symbol", "t", "n", "slots"}

    # THE MEMORY IS THE POINT: a second pass sees the first one's evaluations.
    remembered = lane.load_db(db)
    assert remembered and any(p.evaluations for p in remembered.values())
    again = lane.run(symbols=["EURUSD"], budget_s=15.0, max_programs=2, seed=4, db_path=db)
    assert again["n_seeds"] >= rep["n_seeds"]
    assert len(lane.load_db(db)) >= len(remembered), "a rerun must not lose a program"
