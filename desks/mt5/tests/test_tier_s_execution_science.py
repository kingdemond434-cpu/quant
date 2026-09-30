"""Tier S layer 23: execution researched like alpha, signal alpha split from execution drag.

The organ (`research/execution_science.py`, hourly leg `execution_science`) scores ONE signal list
twice -- frictionless and costed -- so what the idea earned and what the round trip took are
separate numbers. These tests drive it on synthetic fills whose alpha and drag are known by
construction, and pin that the report is written on every run, UNMEASURED included.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import execution_science as xs  # noqa: E402

# ------------------------------------------------------------------------------ per-fill split


def test_split_fills_separates_alpha_from_drag_exactly() -> None:
    fills = [
        # long: signal at 100, filled 100.2 (slipped 0.2), exit 102, stop 1.0, cost 0.1
        {"side": 1, "signal_price": 100.0, "fill_price": 100.2, "exit_price": 102.0,
         "stop_dist": 1.0, "cost": 0.1},
        # short: signal at 50, filled 49.9 (slipped 0.1 against), exit 49.0, stop 0.5
        {"side": -1, "signal_price": 50.0, "fill_price": 49.9, "exit_price": 49.0,
         "stop_dist": 0.5},
    ]
    out = xs.split_fills(fills)
    assert out["status"] == "MEASURED" and out["n"] == 2
    # alpha: +2.0R and +2.0R; drag: 0.2+0.1=0.3R and 0.2R
    assert out["mean_signal_alpha_r"] == pytest.approx(2.0)
    assert out["mean_execution_drag_r"] == pytest.approx(0.25)
    assert out["mean_net_r"] == pytest.approx(1.75)
    assert out["mean_net_r"] + out["mean_execution_drag_r"] == pytest.approx(
        out["mean_signal_alpha_r"])
    assert out["diagnosis"].startswith("SURVIVES_EXECUTION")


def test_a_working_signal_eaten_by_execution_is_named_not_abandoned() -> None:
    fills = [{"side": 1, "signal_price": 100.0, "fill_price": 100.6, "exit_price": 100.5,
              "stop_dist": 1.0} for _ in range(5)]
    out = xs.split_fills(fills)
    assert out["mean_signal_alpha_r"] == pytest.approx(0.5)
    assert out["mean_net_r"] == pytest.approx(-0.1)
    assert out["diagnosis"].startswith("EATEN_BY_EXECUTION")
    dead = xs.split_fills([{"side": 1, "signal_price": 100.0, "fill_price": 100.0,
                            "exit_price": 99.0, "stop_dist": 1.0}])
    assert dead["diagnosis"].startswith("NO_SIGNAL")


def test_split_fills_skips_unusable_rows_and_is_unmeasured_when_empty() -> None:
    out = xs.split_fills([{"side": 1, "signal_price": 1.0, "fill_price": 1.0, "exit_price": 1.1,
                           "stop_dist": 0.0}, {"side": 1}])
    assert out["status"] == "UNMEASURED" and out["skipped"] == 2


# ------------------------------------------------------------------------ the organ, end to end

class _Sig(SimpleNamespace):
    pass


def _fake_world(n_sig: int = 60, alpha_r: float = 0.4, cost_r: float = 0.1) -> tuple[Any, Any]:
    """An evaluator whose frictionless path pays `alpha_r` per trade and whose costed path pays
    `alpha_r - cost_r`: signal alpha and drag known by construction."""

    class Eval:
        @staticmethod
        def costs_for(sym: str, meta: Any, mult: float) -> Any:
            return SimpleNamespace(mult=float(mult))

        @staticmethod
        def daily_series(test: Any, sigs: list[Any], costs: Any) -> pd.Series:
            vals = [float(s.r) - costs.mult * cost_r for s in sigs]
            return pd.Series(vals)

    rng = np.random.default_rng(3)

    def fam(test: Any) -> list[Any]:
        return [_Sig(r=alpha_r + float(rng.normal(0, 0.05))) for _ in range(n_sig)]

    def apply_layers(sigs: list[Any], h1: Any, **genes: Any) -> list[Any]:
        if genes.get("session") == "london":
            return sigs[: len(sigs) // 3]          # a SELECTION variant: keeps a third
        return sigs

    fams = SimpleNamespace(FAMILY_REGISTRY={f: {"func": fam} for f in xs.FAMILIES},
                           _h1=lambda t: t, apply_layers=apply_layers)
    return Eval, fams


def _bars(sym: str) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=3000, freq="h")
    return pd.DataFrame({"close": np.linspace(1.0, 1.1, len(idx))}, index=idx)


def test_build_attributes_drag_to_execution_on_synthetic_fills() -> None:
    ev, fams = _fake_world(alpha_r=0.4, cost_r=0.1)
    doc = xs.build(evaluator=ev, families=fams, meta={}, symbols=["EURUSD"], bars=_bars)
    assert doc["status"] == "OK"
    cells = [c for c in doc["cells"] if c["variant"] == "market_next_open"]
    assert cells, "the base variant must be scored"
    for c in cells:
        # the frictionless path is signal alpha; costed is lower by exactly the drag
        assert c["signal_alpha_frictionless"] > c["net_growth"] > 0
        assert c["execution_drag"] == pytest.approx(
            c["signal_alpha_frictionless"] - c["net_growth"], abs=1e-8)
        # drag ~ log1p(0.4%) - log1p(0.3%) at the 1% ranking fraction
        assert c["execution_drag"] == pytest.approx(
            np.log1p(0.004) - np.log1p(0.003), rel=0.2)
        assert c["diagnosis"].startswith("SURVIVES_EXECUTION")
    by = {v["variant"]: v for v in doc["variants"]}
    assert by["session_london_only"]["like_for_like"] is False
    assert by["market_next_open"]["like_for_like"] is True
    assert doc["best_like_for_like_variant"]["like_for_like"] is True
    assert doc["attribution"]["median_execution_drag"] > 0


def test_build_names_a_signal_that_execution_eats() -> None:
    ev, fams = _fake_world(alpha_r=0.05, cost_r=0.2)
    doc = xs.build(evaluator=ev, families=fams, meta={}, symbols=["EURUSD"], bars=_bars)
    assert doc["status"] == "OK"
    assert doc["attribution"]["diagnoses"].get("EATEN_BY_EXECUTION", 0) > 0
    assert all(c["net_growth"] < 0 < c["signal_alpha_frictionless"] for c in doc["cells"])


def test_build_is_unmeasured_with_its_reason_when_inputs_are_absent() -> None:
    ev, fams = _fake_world()
    none = xs.build(evaluator=ev, families=fams, meta={}, symbols=[], bars=_bars)
    assert none["status"] == "UNMEASURED" and "LIVE sleeve" in none["why"]
    short = xs.build(evaluator=ev, families=fams, meta={}, symbols=["EURUSD"],
                     bars=lambda s: None)
    assert short["status"] == "UNMEASURED"
    assert short["skipped"][0]["symbol"] == "EURUSD"
    assert "live_fill_calibration" in short


def test_main_writes_the_report_on_every_run_including_unmeasured(
        tmp_path: Path, monkeypatch: Any) -> None:
    out = tmp_path / "EXECUTION_SCIENCE.json"
    monkeypatch.setattr(xs, "OUT", out)
    monkeypatch.setattr(xs, "LEDGER", tmp_path / "absent.jsonl")
    monkeypatch.setattr(xs, "build", lambda: xs._unmeasured(
        xs.datetime.now(tz=xs.UTC), "no bars on this host"))
    assert xs.main(["--apply"]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "UNMEASURED" and doc["why"] == "no bars on this host"
    out.unlink()
    assert xs.main([]) == 0 and out.exists(), "written without --apply too"
    out.unlink()
    assert xs.main(["--dry-run"]) == 0 and not out.exists()


def test_main_writes_the_ok_report(tmp_path: Path, monkeypatch: Any) -> None:
    out = tmp_path / "EXECUTION_SCIENCE.json"
    ev, fams = _fake_world()
    monkeypatch.setattr(xs, "OUT", out)
    monkeypatch.setattr(xs, "LEDGER", tmp_path / "absent.jsonl")
    doc = xs.build(evaluator=ev, families=fams, meta={}, symbols=["EURUSD"], bars=_bars)
    monkeypatch.setattr(xs, "build", lambda: doc)
    assert xs.main(["--apply"]) == 0
    assert json.loads(out.read_text("utf-8"))["status"] == "OK"


def test_the_hourly_leg_runs_the_organ() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("execution_science", "research/execution_science.py"' in src
