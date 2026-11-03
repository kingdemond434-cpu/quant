"""The meta-labeler organ (research/meta_labeler.py): causal features, purged walk-forward,
two-sided AFML bet sizing, the trial charge, and the verdicts.

Pinned here:
  * features are CAUSAL: perturbing every bar at or after entry_time (and the bar still forming
    at an off-the-hour entry) leaves them unchanged; trail_win ignores a trade not yet closed;
  * a planted predictable label is recovered OOS (AUC well above 0.5), the verdict is GAIN, the
    published multiplier exceeds 1 where the planted feature is good and falls below 1 where bad;
  * pure-noise labels give NO_GAIN and a multiplier of exactly 1.0;
  * the purge excludes a training trade overlapping the test block or its embargo;
  * too few trades is UNMEASURED with its reason;
  * every sleeve x model configuration is charged once to the lifetime trial ledger.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import meta_labeler as ML  # noqa: E402

N_BARS = 5000


def _bars(seed: int = 0, end_hour: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = pd.Timestamp("2026-06-30 00:00", tz="UTC") + pd.Timedelta(hours=end_hour)
    idx = pd.date_range(end=end, periods=N_BARS, freq="1h")
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, N_BARS)))
    o = np.concatenate(([c[0]], c[:-1]))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0005, N_BARS)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0005, N_BARS)))
    sp = rng.integers(5, 15, N_BARS).astype(float)
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "spread": sp}, index=idx)


def _ledger(bars: pd.DataFrame, *, planted: bool, seed: int = 1, n: int = 500) -> list[dict]:
    """Trades every 7 h after the warm-up, 2 h long. Planted: a morning (UTC 00-11) entry
    wins with probability 0.9, an afternoon one with 0.1. Noise: a fair coin."""
    rng = np.random.default_rng(seed)
    rows = []
    starts = bars.index[300::7][:n]
    for t in starts:
        side = int(rng.choice([-1, 1]))
        p_win = (0.9 if t.hour < 12 else 0.1) if planted else 0.5
        win = rng.random() < p_win
        rows.append({"entry_time": str(t), "exit_time": str(t + pd.Timedelta(hours=2)),
                     "side": side, "entry": 1.0, "exit": 1.0,
                     "r_multiple": 1.0 if win else -1.0, "reason": "target" if win else "stop"})
    return rows


def _setup(tmp: Path, rows: list[dict], bars: pd.DataFrame, stem: str = "EURUSD_testfam"
           ) -> dict[str, Path]:
    led, bd = tmp / "ledgers", tmp / "bars"
    led.mkdir()
    bd.mkdir()
    (led / f"ledger_{stem}.json").write_text(json.dumps(rows), "utf-8")
    bars.to_parquet(bd / "EURUSD_H1.parquet")
    return {"ledger_dirs": led, "bar_dirs": bd, "sleeves": tmp / "sleeves.json",
            "out": tmp / "META_LABEL.json", "trials": tmp / "trials.jsonl"}


def _run(p: dict[str, Path]) -> dict:
    return ML.run(ledger_dirs=(p["ledger_dirs"],), bar_dirs=(p["bar_dirs"],),
                  sleeves_path=p["sleeves"], out=p["out"], trials_path=p["trials"],
                  budget_s=120)


def test_features_are_causal() -> None:
    bars = _bars()
    t = bars.index[1000]
    base = ML.bar_features(bars, t, 1)
    assert base is not None
    poked = bars.copy()
    poked.loc[poked.index >= t, ["open", "high", "low", "close", "spread"]] *= 3.0
    assert ML.bar_features(poked, t, 1) == base
    # An off-the-hour entry: the bar opened at t (10:00-ish) is still FORMING at t + 30 min.
    t_mid = t + pd.Timedelta(minutes=30)
    base_mid = ML.bar_features(bars, t_mid, -1)
    poked2 = bars.copy()
    poked2.loc[poked2.index >= t, ["high", "low", "close"]] *= 5.0
    assert ML.bar_features(poked2, t_mid, -1) == base_mid
    # trail_win counts only trades closed strictly before t.
    hist = [ML.Trade(t - pd.Timedelta(hours=5), t - pd.Timedelta(hours=3), 1, 1.0),
            ML.Trade(t - pd.Timedelta(hours=1), t + pd.Timedelta(hours=2), 1, -1.0)]
    assert ML.trail_win(hist, t) == (1 + 1) / (1 + 2)


def test_purge_excludes_overlapping_trades() -> None:
    t0 = pd.Timestamp("2026-01-10 00:00", tz="UTC")
    entries = [t0 - pd.Timedelta(hours=100), t0 - pd.Timedelta(hours=30),
               t0 - pd.Timedelta(hours=10), t0 + pd.Timedelta(hours=1)]
    exits = [t0 - pd.Timedelta(hours=90), t0 - pd.Timedelta(hours=26),
             t0 + pd.Timedelta(hours=2), t0 + pd.Timedelta(hours=3)]
    # #0 is clean; #1 exits inside the 24 h embargo; #2 overlaps the block; #3 is in it.
    assert ML.purged_train_index(entries, exits, t0, embargo_h=24.0) == [0]
    assert ML.purged_train_index(entries, exits, t0, embargo_h=0.0) == [0, 1]


def test_planted_label_is_recovered_and_sized_two_sided(tmp_path: Path) -> None:
    bars = _bars(end_hour=4)            # the next signal is at 05:00 UTC: a planted morning
    p = _setup(tmp_path, _ledger(bars, planted=True), bars)
    doc = _run(p)
    row = doc["sleeves"]["EURUSD_testfam"]
    assert row["verdict"] == "GAIN", row.get("why")
    assert row["oos"]["auc"] > 0.75
    assert row["oos"]["delta_elogw_per_trade"] > 0
    cur = row["current_multiplier"]
    assert cur["long"] > 1.0 and cur["short"] > 1.0
    # Two-sided: an afternoon occurrence is sized DOWN by the same fitted model.
    trades = ML.parse_trades(_ledger(bars, planted=True))
    x, keep = ML.features(trades, bars)
    y = np.asarray([1.0 if trades[i].r > 0 else 0.0 for i in keep])
    model = ML.fit_logistic(x, y, 1.0)
    hours = np.asarray([trades[i].entry.hour for i in keep])
    m = ML.bet_multiplier(ML.predict(model, x), float(y.mean()), len(y))
    assert m[hours < 12].mean() > 1.0 > m[hours >= 12].mean()
    assert m.min() >= 0.0 and m.max() <= ML.MAX_MULT


def test_noise_labels_give_no_gain_and_unit_multiplier(tmp_path: Path) -> None:
    bars = _bars(seed=3)
    p = _setup(tmp_path, _ledger(bars, planted=False, seed=7), bars)
    doc = _run(p)
    row = doc["sleeves"]["EURUSD_testfam"]
    assert row["verdict"] == "NO_GAIN", row.get("why")
    assert row["multiplier"] == 1.0
    assert row["current_multiplier"]["long"] == 1.0 == row["current_multiplier"]["short"]
    assert json.loads(p["out"].read_text("utf-8"))["summary"]["n_gain"] == 0


def test_too_few_trades_is_unmeasured(tmp_path: Path) -> None:
    bars = _bars()
    p = _setup(tmp_path, _ledger(bars, planted=True, n=30), bars)
    doc = _run(p)
    row = doc["sleeves"]["EURUSD_testfam"]
    assert row["verdict"] == "UNMEASURED"
    assert "< 80" in row["why"]
    assert row["multiplier"] == 1.0
    assert doc["status"].startswith("UNMEASURED")
    assert doc["trials"]["n_raw_this_pass"] == 0


def test_trials_are_charged_once_per_sleeve_and_config(tmp_path: Path) -> None:
    bars = _bars()
    p = _setup(tmp_path, _ledger(bars, planted=False), bars)
    d1 = _run(p)
    assert d1["trials"]["n_raw_this_pass"] == len(ML.MODEL_CONFIGS)
    assert d1["trials"]["n_raw_lifetime"] == len(ML.MODEL_CONFIGS)
    assert d1["trials"]["expected_max_z"] > 0
    row = d1["sleeves"]["EURUSD_testfam"]
    assert row["oos"]["t_deflated"] < row["oos"]["t_uplift"]
    _run(p)
    lines = [ln for ln in p["trials"].read_text("utf-8").splitlines() if ln.strip()]
    assert len(lines) == len(ML.MODEL_CONFIGS)       # a re-run never re-charges


def test_report_names_where_it_would_be_consumed_and_is_not_wired() -> None:
    assert ML.CONSUMPTION["wired"] is False
    assert "resolve_family_order" in ML.CONSUMPTION["where"]
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/decision_core.py",
                "desks/mt5/mt5desk/sizing.py"):
        assert "meta_labeler" not in (_ROOT / rel).read_text("utf-8")
