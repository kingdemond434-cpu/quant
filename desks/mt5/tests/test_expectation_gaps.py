"""DATA-44: multi-sensor nowcasts and expectation gaps -- the posterior, PIT (a later change never
alters an earlier row), the terms gate on each gap, and the planted-effect / noise contracts."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_engines as se  # noqa: E402
from research import expectation_gaps as eg  # noqa: E402

T0 = datetime(2019, 1, 4, 13, 30, tzinfo=UTC)


def _events(n: int, seed: int = 1, *, consensus: bool = True) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    x, out = 0.2, []
    for i in range(n):
        x = 0.1 + 0.5 * x + float(rng.normal(0, 0.1))
        at = T0 + timedelta(days=30 * i)
        ev: dict[str, Any] = {"at": at, "actual": round(x, 3)}
        if consensus:
            ev["consensus"] = round(x + float(rng.normal(0, 0.08)), 2)
            ev["consensus_at"] = at - timedelta(hours=6)
        ev["premove"] = {"EURUSD": float(rng.normal(0, 0.01)), "XAUUSD": float(rng.normal(0, 0.01))}
        ev["premove_at"] = at - timedelta(hours=1)
        out.append(ev)
    return out


def test_fuse_is_precision_weighted_and_never_narrower_than_its_own_errors() -> None:
    fc = {"a": 1.0, "b": 2.0}
    errs = {"a": [0.1, -0.1] * 4, "b": [0.2, -0.2] * 4}
    got = eg.fuse(fc, errs, own_errors=[0.5, -0.5] * 4)
    assert got["status"] == "MEASURED"
    assert got["weights"]["a"] > got["weights"]["b"]            # the precise sensor leads
    assert math.isclose(got["mean"], sum(got["contribution"].values()))
    assert got["sd"] == got["sd_calibrated"] == 0.5             # correlated errors: the wider
    assert got["sd_independent"] < got["sd"]
    thin = eg.fuse(fc, {"a": [0.1]})
    assert thin["status"] == eg.UNMEASURED and thin["mean"] is None


def test_nowcast_has_posterior_revision_acceleration_and_surprise() -> None:
    rows = eg.release_rows("USD CPI m/m", _events(60), series="CPIAUCSL")
    late = rows[-1]
    nc = late["nowcast"]
    assert nc["status"] == "MEASURED" and nc["sd"] > 0
    assert set(nc["weights"]) <= {"ewm12", "last", "mean12", "ar1"} and len(nc["weights"]) >= 3
    assert nc["revision"] is not None and nc["acceleration"] is not None
    assert math.isclose(late["surprise"], late["actual"] - nc["mean"])
    assert rows[0]["nowcast"]["status"] == eg.UNMEASURED      # nothing before the first print
    assert "surprise" not in rows[0]


def test_pit_a_later_change_never_alters_an_earlier_row() -> None:
    evs = _events(60)
    before = eg.release_rows("R", evs[:40], series="S")
    changed = [dict(e) for e in evs]
    for e in changed[40:]:
        e["actual"] = 99.0                                      # later prints revised wildly
    changed[45]["consensus"] = -5.0
    after = eg.release_rows("R", changed, series="S")
    dump = [json.dumps(r, sort_keys=True, default=str) for r in before]
    assert dump == [json.dumps(r, sort_keys=True, default=str) for r in after[:40]]
    # and the knowable instant of every gap precedes its scheduled print
    for r in after:
        for g in r["gaps"].values():
            assert datetime.fromisoformat(g["knowable_at"]) < datetime.fromisoformat(r["at"])


def test_consensus_captured_at_or_after_the_print_is_refused() -> None:
    evs = _events(30)
    evs[-1]["consensus_at"] = evs[-1]["at"]
    rows = eg.release_rows("R", evs, series="S")
    assert "consensus" not in rows[-1]["expectations"]
    assert "consensus" in rows[-2]["expectations"]


def test_held_consensus_carries_its_verdict_and_market_gap_is_admitted() -> None:
    rows = eg.release_rows("R", _events(60), series="PAYEMS")
    gaps = rows[-1]["gaps"]
    assert gaps["nowcast-consensus"]["terms"] == "HELD"
    assert "HELD_TERMS" in gaps["nowcast-consensus"]["terms_why"]
    assert gaps["consensus-market_bars"]["terms"] == "HELD"
    nm = gaps["nowcast-market_bars"]
    assert nm["terms"] == "admitted" and nm["data_source"] == "alfred:PAYEMS+mt5:bars"
    assert nm["uadj"] == nm["gap"] / nm["sd"]
    late = [r["gaps"]["nowcast-consensus"] for r in rows if "nowcast-consensus" in r["gaps"]]
    assert late[-1]["percentile"] is not None and late[-1]["accel_z"] is not None


def _gap_events(n: int, effect: float, seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    out = []
    hist: list[float] = []
    for i in range(n):
        gap = float(rng.normal(0, 1))
        sd = float(rng.uniform(0.5, 2.0))
        uadj = gap / sd
        scale = float(np.std(hist[-24:], ddof=1)) if len(hist) > 2 else None
        pct = (sum(h < gap for h in hist) / len(hist)) if len(hist) >= 10 else None
        acc = (gap - 2 * hist[-1] + hist[-2]) / scale if len(hist) >= 2 and scale else None
        hist.append(gap)
        day = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=3 * i)
        ret = effect * uadj + float(rng.normal(0, 0.004))
        out.append({"gap": {"gap": gap, "sd": sd, "uadj": uadj, "sign": float(np.sign(gap)),
                            "magnitude": abs(gap) / scale if scale else None,
                            "percentile": pct, "accel_z": acc},
                    "ret": ret, "start": day + timedelta(hours=12),
                    "end": day + timedelta(days=1)})
    return out


def test_planted_gap_effect_yields_gain() -> None:
    got = {c["hypothesis"]: c for c in
           eg.hypothesis_contracts(_gap_events(400, 0.004, 5), pair="nowcast-market_bars",
                                   leg="EURUSD")}
    assert set(got) == {*eg.HYPOTHESES, "uncertainty_gate"}
    assert got["uncertainty_adjusted"]["verdict"] == se.GAIN
    assert got["sign"]["verdict"] == se.GAIN
    assert all(c["leg"] == "EURUSD" and c["pair"] == "nowcast-market_bars" for c in got.values())


def test_noise_yields_no_gain() -> None:
    got = eg.hypothesis_contracts(_gap_events(400, 0.0, 9), pair="p", leg="EURUSD")
    assert not any(c["verdict"] == se.GAIN for c in got)
    thin = eg.hypothesis_contracts(_gap_events(40, 0.004, 5), pair="p", leg="EURUSD")
    assert all(c["verdict"] == se.UNMEASURED for c in thin)


def _frame(start: datetime, days: int, seed: int) -> tuple[pd.DataFrame, int]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, idx.size)))
    open_ = np.r_[100.0, close[:-1]]
    return pd.DataFrame({"open": open_, "close": close}, index=idx), 60


class _Ledger:
    def __init__(self) -> None:
        self.rows: list[Any] = []

    def append(self, obs: list[Any], now: datetime) -> dict[str, int]:
        self.rows += obs
        return {"appended": len(obs)}


def test_run_end_to_end_holds_the_consensus_and_writes_only_admitted_series(
        tmp_path: Path) -> None:
    evs = [{k: v for k, v in e.items() if not k.startswith("premove")} for e in _events(70)]
    bars = {leg: _frame(T0 - timedelta(days=30), 30 * 72, i) for i, leg in enumerate(eg.LEGS)}
    led = _Ledger()
    now = T0 + timedelta(days=30 * 71)
    doc = eg.run(now=now, days=5000, releases={"USD CPI m/m": ("CPIAUCSL", evs)},
                 bars_fn=bars.get, pm_values={}, ledger=led, lake_root=tmp_path / "lake",
                 contracts_root=tmp_path / "c", report=tmp_path / "r.json", emit_cells=False,
                 min_n=20)
    assert doc["rows"] == 70 and doc["nowcasts_measured"] > 40
    assert doc["pairs"]["nowcast-consensus"]["terms"] == "HELD"
    assert doc["pairs"]["nowcast-market_bars"]["terms"] == "admitted"
    assert doc["pairs"]["nowcast-market_pm"]["rows"] == 0
    assert doc["lake"]["ws_expgap_nowcast_consensus"]["status"] == "HELD_TERMS"
    assert doc["lake"]["ws_expgap_nowcast_market_bars"]["status"] == "WRITTEN"
    assert not (tmp_path / "lake" / "ws_expgap_nowcast_consensus.csv").exists()
    assert (tmp_path / "c" / "expectation_gaps.json").exists() and led.rows
    assert {c.get("hypothesis") for c in doc["contracts"]} >= {*eg.HYPOTHESES,
                                                               "multi_sensor_nowcast"}
    dry = eg.run(now=now, days=5000, releases={"USD CPI m/m": ("CPIAUCSL", evs)},
                 bars_fn=bars.get, pm_values={}, report=None, dry_run=True, min_n=20)
    assert dry["cells"]["ws_expgap_nowcast_consensus"]["emitted"] == 0
    assert dry["cells"]["ws_expgap_nowcast_market_bars"]["emitted"] > 0


def test_no_first_prints_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = eg.run(now=T0, releases={}, bars_fn=lambda s: None, pm_values={},
                 report=None, dry_run=True)
    assert doc["status"] == eg.UNMEASURED and doc["rows"] == 0
    assert all(c["verdict"] == se.UNMEASURED for c in doc["contracts"])
