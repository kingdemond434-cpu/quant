"""Priced-in-ness (QG25-26): pre-event probabilities, leakage refusal, expanding recalibration,
reaction joins and the monotone / incremental contracts on synthetic history."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402
from research import priced_in as pi  # noqa: E402

LEGS = ["EURUSD", "USDJPY", "XAUUSD", "US500", "NAS100"]
REG = {s: {"symbol": s} for s in LEGS}


def _iso(t: datetime) -> str:
    return t.isoformat()


def _rows(key: str, at: datetime, p_first: float, p_last: float, outcome: float,
          category: str = "rates") -> list[dict[str, Any]]:
    return [
        {"forecast_id": key, "category": category, "p": p_first,
         "stored_at": _iso(at - timedelta(days=2)), "resolves_at": _iso(at)},
        {"forecast_id": key, "category": category, "p": p_last,
         "stored_at": _iso(at - timedelta(hours=1)), "resolves_at": _iso(at)},
        # the post-release price: the card's named leakage, refused
        {"forecast_id": key, "category": category, "p": outcome,
         "stored_at": _iso(at + timedelta(minutes=5)), "resolves_at": _iso(at)},
        {"forecast_id": key, "category": category, "outcome": outcome,
         "stored_at": _iso(at + timedelta(hours=2)), "resolves_at": _iso(at)},
    ]


def test_events_first_and_last_snapshot_and_leakage_refused() -> None:
    at = datetime(2026, 9, 17, 18, 0, tzinfo=UTC)
    rows = [*_rows("fomc-sep", at, 0.6, 0.9, 1.0),
            *_rows("election", at, 0.5, 0.5, 1.0, category="elections"),
            {"forecast_id": "open", "category": "cpi", "p": 0.4, "stored_at": _iso(at),
             "resolves_at": _iso(at + timedelta(days=3))}]
    events, acc = pi.build_events(rows)
    assert len(events) == 1 and acc["not_macro"] == 1 and acc["no_outcome"] == 1
    ev = events[0]
    assert ev["p_first"] == 0.6 and ev["p_last"] == 0.9 and ev["measure"] == "Q"
    assert ev["surprise_pm"] == pytest.approx(0.1) and ev["surprise_pm_first"] == pytest.approx(0.4)
    assert acc["post_event_snapshots_refused"] == 1
    assert -1.0 <= ev["surprise_pm"] <= 1.0


def test_recalibration_is_expanding_and_only_when_measured() -> None:
    rng = np.random.default_rng(3)
    t0 = datetime(2025, 1, 1, 13, 30, tzinfo=UTC)
    rows: list[dict[str, Any]] = []
    for i in range(120):
        p = float(rng.uniform(0.05, 0.95))
        true = 1 / (1 + math.exp(-1.6 * math.log(p / (1 - p))))       # an under-confident market
        rows += _rows(f"e{i}", t0 + timedelta(days=3 * i), p, p, float(rng.random() < true))
    events, _ = pi.build_events(rows)
    n = pi.adjust(events)
    assert events[0]["surprise_pm_adj"] == pi.UNMEASURED            # nothing before it
    assert events[10]["surprise_pm_adj"] == pi.UNMEASURED           # under MIN_FORECASTS
    assert 0 < n < len(events)
    last = events[-1]
    assert last["adj_measure"] == "P_recalibrated" and last["adj_fit_n"] < len(events)
    # the fit for event i never saw event i or anything after it
    k = next(i for i, e in enumerate(events) if isinstance(e["surprise_pm_adj"], float))
    assert events[k]["adj_fit_n"] <= k


def test_reaction_day_and_z() -> None:
    assert pi.reaction_day(datetime(2026, 9, 17, 18, 0, tzinfo=UTC)) == date(2026, 9, 17)
    assert pi.reaction_day(datetime(2026, 9, 17, 21, 0, tzinfo=UTC)) == date(2026, 9, 18)
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(80)]
    px = [100.0 * math.exp(0.01 * ((-1) ** i)) for i in range(80)]
    closes = [(d.isoformat(), p) for d, p in zip(days, px, strict=True)]
    assert pi.reaction_z(closes, days[70]) == pytest.approx(1.0, rel=0.02)
    assert pi.reaction_z(closes, days[10]) is None                  # not enough history
    assert pi.resolve_legs({"EURUSD": {}, "USTEC": {}, "GOLD": {}}) == ["EURUSD", "GOLD", "USTEC"]


# ------------------------------------------------------------------ synthetic history
def _world(n_events: int, planted: bool, seed: int = 11, z_only: bool = False
           ) -> tuple[list[dict[str, Any]], dict[str, list[tuple[str, float]]],
                      list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    start = date(2024, 1, 1)
    days = [start + timedelta(days=i) for i in range(70 + 2 * n_events + 5)]
    rows: list[dict[str, Any]] = []
    shocks: dict[str, float] = {}
    consensus: list[dict[str, Any]] = []
    for i in range(n_events):
        d = days[70 + 2 * i]
        at = datetime(d.year, d.month, d.day, 13, 30, tzinfo=UTC)
        p = float(rng.uniform(0.05, 0.95))
        y = float(rng.random() < p)
        z = float(rng.normal())
        size = (abs(z) if z_only else (abs(y - p) if planted else float(rng.random())))
        if z_only:                       # |surprise_pm| is a function of |z| and nothing else
            a = float(np.clip(0.1 + 0.2 * abs(z), 0.05, 0.95))
            p = 1.0 - a if y else a
        rows += _rows(f"ev{i}", at, p, p, y)
        shocks[d.isoformat()] = size
        consensus.append({"at": _iso(at), "z": z})
    closes: dict[str, list[tuple[str, float]]] = {}
    for s in LEGS:
        px, out = 100.0, []
        for d in days:
            r = rng.normal(0.0, 0.01)
            if d.isoformat() in shocks:
                r = 0.3 * r + math.copysign(0.03 * shocks[d.isoformat()], rng.normal())
            px *= math.exp(r)
            out.append((d.isoformat(), px))
        closes[s] = out
    return rows, closes, consensus


def _run(tmp_path: Path, rows: list[dict[str, Any]], closes: dict[str, Any],
         consensus: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    return pi.run(now=now, forecasts=rows, registry=REG, closes_fn=lambda s, n: closes[s],
                  consensus=consensus, ledger=sc.SensorLedger(tmp_path / "sensors"),
                  lake_root=tmp_path / "lake", contracts_root=tmp_path / "c",
                  report=tmp_path / "R.json", emit_cells=False, **kw)


def test_monotone_and_incremental_gain_on_planted_history(tmp_path: Path) -> None:
    rows, closes, consensus = _world(220, planted=True)
    doc = _run(tmp_path, rows, closes, consensus)
    raw, adj, inc = doc["contracts"]
    assert doc["events"] == 220 and doc["with_reaction"] == 220
    assert raw["verdict"] == se.GAIN and raw["value"] > 0.3, raw
    assert raw["measure"] == "Q" and adj["measure"] == "P_recalibrated"
    assert inc["verdict"] == se.GAIN and "consensus z" in inc["baseline"], inc
    assert doc["lake"]["status"] == "WRITTEN" and doc["lake"]["rows"] == 220
    assert doc["ledger"]["appended"] == len(LEGS) and doc["ledger"]["refused"] == 0
    assert (tmp_path / "c" / "priced_in.json").exists() and (tmp_path / "R.json").exists()


def test_noise_is_no_gain_and_thin_history_is_unmeasured(tmp_path: Path) -> None:
    rows, closes, consensus = _world(220, planted=False, seed=12)
    raw = _run(tmp_path, rows, closes, consensus)["contracts"][0]
    assert raw["verdict"] == se.NO_GAIN
    rows, closes, consensus = _world(40, planted=True, seed=13)
    doc = _run(tmp_path / "thin", rows, closes, consensus)
    assert {c["verdict"] for c in doc["contracts"]} == {se.UNMEASURED}


def test_a_surprise_that_only_restates_consensus_adds_nothing(tmp_path: Path) -> None:
    rows, closes, consensus = _world(220, planted=False, seed=14, z_only=True)
    inc = _run(tmp_path, rows, closes, consensus)["contracts"][2]
    assert inc["verdict"] != se.GAIN


def test_cells_both_sides_on_the_legs_dry_run(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import terms_hold as th
    rows, closes, consensus = _world(5, planted=True)
    # the forecast store has no recorded terms basis: the closed gate holds it (audit #211)
    monkeypatch.setattr(th, "CLEARANCES", tmp_path / "none.json")
    doc = pi.run(now=datetime(2026, 10, 6, tzinfo=UTC), forecasts=rows, registry=REG,
                 closes_fn=lambda s, n: closes[s], consensus=consensus, dry_run=True)
    assert doc["cells"]["status"] == "HELD_TERMS" and doc["cells"]["emitted"] == 0
    # a quoted clearance admits it, both sides on every leg
    (tmp_path / "clear.json").write_text(json.dumps({"prediction_markets": {
        "status": "CLEARED", "terms_url": "https://example.test/terms",
        "terms_quote": "machine use permitted"}}), "utf-8")
    monkeypatch.setattr(th, "CLEARANCES", tmp_path / "clear.json")
    doc = pi.run(now=datetime(2026, 10, 6, tzinfo=UTC), forecasts=rows, registry=REG,
                 closes_fn=lambda s, n: closes[s], consensus=consensus, dry_run=True)
    assert doc["cells"]["emitted"] == 2 * len(LEGS) * 3 * 2
    assert doc["lake"]["status"] == "DRY_RUN"
