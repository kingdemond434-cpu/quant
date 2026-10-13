"""Meta-label conditioner: point-in-time features, purged walk-forward, honest UNMEASURED,
once-only trial charging, Tier S judge, and hourly wiring."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK.parent.parent))

from research import meta_label as ml  # noqa: E402


def _frame(days: int = 260, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    idx = [(t0 + timedelta(days=i)).date().isoformat() for i in range(days)]
    return pd.DataFrame({"EUR": rng.normal(0, 0.003, days), "USD": rng.normal(0, 0.003, days),
                         "JPY": rng.normal(0, 0.003, days), "d_vix": rng.normal(0, 0.05, days),
                         "d_r10": rng.normal(0, 0.03, days)}, index=idx)


def _write_ledger(d: Path, name: str, frame: pd.DataFrame, n: int, fwd_from: int,
                  informative: bool) -> None:
    rows = []
    leg = (frame["EUR"] - frame["USD"]).to_numpy()
    rng = np.random.default_rng(7)
    for i in range(n):
        day = 150 + i // 2
        entry = datetime.fromisoformat(frame.index[day]).replace(hour=1, tzinfo=UTC)
        mom = float(leg[day - 5:day].sum())
        r = (1.0 if mom > 0 else -1.0) if informative else float(rng.choice([1.0, -1.0]))
        rows.append({"entry_time": str(entry), "exit_time": str(entry + timedelta(hours=2)),
                     "side": 1, "r_multiple": r,
                     "phase": "forward" if i >= fwd_from else "historical"})
    d.mkdir(parents=True, exist_ok=True)
    (d / f"ledger_{name}.json").write_text(json.dumps(rows), "utf-8")


def test_features_are_point_in_time() -> None:
    f = _frame()
    t = ml.Trade("EURUSD_x", "EURUSD", datetime.fromisoformat(f.index[100]).replace(
        tzinfo=UTC), datetime.fromisoformat(f.index[100]).replace(tzinfo=UTC), 1, 1.0, True)
    x0 = ml.build_features([t], f)
    g = f.copy()
    g.iloc[100:] = 99.0                    # poison the signal day and everything after it
    g.iloc[99, g.columns.get_loc("d_vix")] = 99.0     # macro lags one more day
    x1 = ml.build_features([t], g)
    assert np.allclose(x0, x1, equal_nan=True)
    assert np.isfinite(x0[0, :4]).all()


def test_walk_forward_never_trains_on_overlapping_outcomes() -> None:
    base = datetime(2026, 3, 1, tzinfo=UTC)
    trades = [ml.Trade("s", "EURUSD", base + timedelta(hours=i), base + timedelta(hours=i + 1),
                       1, 1.0 if i % 2 else -1.0, False) for i in range(60)]
    X = np.random.default_rng(0).normal(size=(60, 5))
    p = ml.walk_forward(trades, X, [0, 1])
    # all trades within one day and < embargo of each other: nothing is scorable
    assert np.isnan(p).all()


def test_insufficient_data_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = ml.run(tmp_path / "none", tmp_path / "out.json", frame=_frame(),
                 charged=tmp_path / "c.json", trials=tmp_path / "t.jsonl")
    assert doc["status"] == ml.UNMEASURED and doc["best_tier_s"] == ml.UNMEASURED
    assert ml.lift(np.array([1.0, -1.0]), np.array([0.6, 0.4]), 0.5)["status"] == ml.UNMEASURED


def test_informative_state_produces_positive_lift(tmp_path: Path) -> None:
    f = _frame()
    sd = tmp_path / "shadow"
    _write_ledger(sd, "EURUSD_demo", f, 200, 120, informative=True)
    doc = ml.run(sd, tmp_path / "META_LABEL.json", frame=f,
                 charged=tmp_path / "c.json", trials=tmp_path / "t.jsonl")
    assert doc["status"] == "MEASURED"
    pair = next(v for v in doc["variants"] if v["features"] == ["mom5_aligned", "vol_ratio"])
    pooled = pair["pooled_forward"]
    assert pooled["lift_r_per_signal"] > 0 and pooled["lift_ci95"][0] > 0
    assert pair["tier_s"]["n_trials"] >= ml.TIER_S_MIN_N
    assert "EURUSD_demo" in pair["per_sleeve"]
    assert json.loads((tmp_path / "META_LABEL.json").read_text())["schema"] == ml.SCHEMA


def test_tier_s_bar_rejects_noise() -> None:
    d = np.random.default_rng(3).normal(0, 1, 200)
    assert ml.tier_s_judge(d, 5)["status"] == "FAIL"


def test_variants_charged_once_ever(tmp_path: Path) -> None:
    c, t = tmp_path / "c.json", tmp_path / "t.jsonl"
    assert ml.charge(charged=c, trials=t) == (len(ml.VARIANTS), len(ml.VARIANTS))
    assert ml.charge(charged=c, trials=t) == (0, len(ml.VARIANTS))
    rows = [json.loads(x) for x in t.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["by_family"] == {"meta_label": len(ml.VARIANTS)}
    assert len({v.trial_id for v in ml.VARIANTS}) == len(ml.VARIANTS)


def test_wired_as_an_hourly_leg_and_report_only() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("meta_label", lambda: _producer(' in src
    assert '"meta_label", "research/meta_label.py", "--once"' in src
    from libs.research import layers
    assert layers.LEG_LAYER["meta_label"] == "execution"
    assert ml.OUT.name == "META_LABEL.json" and ml.OUT.parent.name == "reports"
    for p in (DESK / "mt5desk").glob("*.py"):
        assert "META_LABEL" not in p.read_text("utf-8", errors="ignore")
