from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

MODULE = Path(__file__).resolve().parents[1] / "research" / "unknown_unknowns.py"
SPEC = importlib.util.spec_from_file_location("mt5_unknown_unknowns", MODULE)
assert SPEC and SPEC.loader
uu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(uu)


def _touch(root: Path, name: str) -> None:
    (root / name).touch()


def test_available_cells_cover_every_bar_timeframe_but_not_single_stocks(
        tmp_path: Path, monkeypatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.canon.json").write_text(json.dumps({
        "XAUUSD": {"asset_class": "Commodities"},
        "EURUSD": {"asset_class": "Forex"},
        "AAPL": {"asset_class": "Equities"},
    }), encoding="utf-8")
    for name in ("XAUUSD_M1.parquet", "XAUUSD_H1.parquet", "EURUSD_M15.parquet",
                 "EURUSD_D1.parquet", "AAPL_H1.parquet"):
        _touch(uni, name)
    monkeypatch.setattr(uu, "UNI", uni)
    monkeypatch.setattr(uu, "UNIVERSE_CANON", uni / "universe.canon.json")

    cells = uu._available_cells()

    assert ("XAUUSD", "M1", "Commodities") in cells
    assert ("XAUUSD", "H1", "Commodities") in cells
    assert ("EURUSD", "M15", "Forex") in cells
    assert ("EURUSD", "D1", "Forex") in cells
    assert not any(symbol == "AAPL" for symbol, _tf, _asset in cells)


def test_selection_always_includes_all_sleeve_cells_and_rotates_frontier(
        tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state.json"
    monkeypatch.setattr(uu, "STATE", state)
    monkeypatch.setattr(uu, "ROTATION_CELLS", 1)
    monkeypatch.setattr(uu, "_sleeve_symbols", lambda: ["XAUUSD"])
    monkeypatch.setattr(uu, "_available_cells", lambda: [
        ("XAUUSD", "M1", "Commodities"),
        ("XAUUSD", "H1", "Commodities"),
        ("EURUSD", "H1", "Forex"),
        ("UST10Y", "H1", "Bonds"),
    ])

    first, first_state = uu._selected_cells()
    state.write_text(json.dumps(first_state), encoding="utf-8")
    second, _second_state = uu._selected_cells()

    sleeve = {("XAUUSD", "M1", "Commodities"), ("XAUUSD", "H1", "Commodities")}
    assert sleeve <= set(first)
    assert sleeve <= set(second)
    assert (set(first) - sleeve) != (set(second) - sleeve)


def test_anomaly_fingerprint_separates_timeframes() -> None:
    base = {"kind": "unexplained_move", "symbol": "XAUUSD", "at": "2026-01-01"}
    assert uu._fingerprint({**base, "timeframe": "M5"}) != uu._fingerprint(
        {**base, "timeframe": "H1"})


def test_directed_pair_search_is_bounded_and_resumable(monkeypatch) -> None:
    monkeypatch.setattr(uu, "PAIR_BUDGET", 2)
    frame = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
    state = {"pair_cursors": {}}

    first = uu._pair_slice(frame, state, "H1")
    second = uu._pair_slice(frame, state, "H1")

    assert len(first) == len(second) == 2
    assert set(first).isdisjoint(second)
    assert state["directed_pairs_available"]["H1"] == 6
    assert state["directed_pairs_scanned"]["H1"] == 2


def test_latent_features_are_ontology_free_and_measured() -> None:
    rng = np.random.default_rng(7)
    series = pd.Series(rng.normal(0, 0.01, 700))
    distance = uu._latent_features(series, np, pd)

    assert distance is not None
    assert len(distance) >= 6 * uu.LATENT_WINDOW
    assert np.isfinite(distance.iloc[-1])
