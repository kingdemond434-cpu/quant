"""TAPE_LIVENESS goes RED at the first break between writer, reader and judge -- and only then."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("tape_liveness", _DESK / "moat" / "tape_liveness.py")
assert _spec is not None and _spec.loader is not None
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)

NOW = datetime(2026, 10, 29, 14, 30, tzinfo=UTC)
UNIVERSE = {
    "XAUUSD": {"asset_class": "Commodities"}, "XAGUSD": {"asset_class": "Commodities"},
    "EURUSD": {"asset_class": "Forex"}, "GBPUSD": {"asset_class": "Forex"},
    "USDJPY": {"asset_class": "Forex"},
    "BTCUSD": {"asset_class": "Crypto"}, "ETHUSD": {"asset_class": "Crypto"},
    "Apple": {"asset_class": "Equities"}, "Tesla": {"asset_class": "Equities"},
}


def _state(ages_h: dict[str, float]) -> dict:
    return {s: {"last_tick_utc": (NOW - timedelta(hours=h)).isoformat()} for s, h in ages_h.items()}


LIVE = {"XAUUSD": 0.1, "XAGUSD": 0.1, "EURUSD": 0.05, "GBPUSD": 0.05, "USDJPY": 0.05,
        "BTCUSD": 0.01, "ETHUSD": 0.01, "Apple": 16.0, "Tesla": 16.0}


def _frame(newest: datetime, n: int = 200, spread: float = 0.1) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp(newest), periods=n, freq="1s")
    return pd.DataFrame({"bid": 1.0, "ask": 1.0 + spread}, index=idx)


def _reader_seeing(state: dict, lag_h: float = 0.0, spread: float = 0.1):
    def read(sym: str):
        t = datetime.fromisoformat(state[sym]["last_tick_utc"]) - timedelta(hours=lag_h)
        return _frame(t, spread=spread)
    return read


def test_closed_equities_are_not_red_but_a_dead_fx_symbol_in_an_open_class_is():
    block, red, _ = tl.recorder_block(_state(LIVE), UNIVERSE, NOW)
    assert red == []
    assert block["classes"]["Equities"]["open"] is False
    ages = dict(LIVE, USDJPY=5.0)
    _, red, _ = tl.recorder_block(_state(ages), UNIVERSE, NOW)
    assert any(r.startswith("SYMBOL_STALE") and "USDJPY" in r for r in red)


def test_recorder_down_when_crypto_stops_even_on_a_weekend():
    ages = dict.fromkeys(LIVE, 30.0)
    _, red, _ = tl.recorder_block(_state(ages), UNIVERSE, NOW)
    assert any(r.startswith("RECORDER_DOWN") for r in red)


def test_retired_and_untaped_symbols_are_amber_not_red():
    state = _state(dict(LIVE, Palantir=1300.0))
    state.pop("Tesla")
    block, red, amber = tl.recorder_block(state, UNIVERSE, NOW)
    assert red == []
    assert block["retired"] == ["Palantir"]
    assert block["untaped_universe_symbols"] == ["Tesla"]
    assert len(amber) == 2


def test_blind_reader_is_red_while_the_recorder_is_green():
    """The 2026-10-29 failure: recorder fresh, research reader returning nothing."""
    state = _state(LIVE)
    _, red = tl.reader_block(state, NOW, reader=lambda sym: None)
    assert len([r for r in red if r.startswith("READER_BLIND")]) == len(tl.PROBES)


def test_reader_behind_the_recorder_is_red():
    state = _state(LIVE)
    _, red = tl.reader_block(state, NOW, reader=_reader_seeing(state, lag_h=24 * 40))
    assert any(r.startswith("READER_BLIND") and "behind" in r for r in red)
    _, red = tl.reader_block(state, NOW, reader=_reader_seeing(state))
    assert red == []


def test_zero_spread_is_red():
    state = _state(LIVE)
    _, red = tl.reader_block(state, NOW, reader=_reader_seeing(state, spread=0.0))
    assert any(r.startswith("ZERO_SPREAD") for r in red)


def test_a_reader_that_raises_is_a_finding_not_a_crash():
    def boom(sym: str):
        raise OSError("disk")
    out, red = tl.reader_block(_state(LIVE), NOW, reader=boom)
    assert all(out[s]["verdict"] == "BLIND" for s in tl.PROBES)
    assert red


def test_tape_cells_mined_but_never_judged_is_red():
    cov = {"at": NOW.isoformat(), "families": {
        "liquidity_regime": {"mined": 24963, "judged_total": 0},
        "orderflow_imbalance": {"mined": 41330, "judged_total": 12},
        "execution_state": {"mined": 0, "judged_total": 0}}}
    _, red = tl.judge_block(cov, NOW)
    assert red == ["TAPE_NEVER_JUDGED: liquidity_regime has 24963 mined cells and 0 verdicts"]


def test_run_is_green_end_to_end(tmp_path, monkeypatch):
    import json
    state = _state(LIVE)
    (tmp_path / "state.json").write_text(json.dumps(state))
    (tmp_path / "universe.json").write_text(json.dumps(UNIVERSE))
    (tmp_path / "cov.json").write_text(json.dumps({"at": NOW.isoformat(), "families": {
        f: {"mined": 10, "judged_total": 3} for f in tl.TAPE_FAMILIES}}))
    monkeypatch.setattr(tl, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(tl, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(tl, "JUDGE_COVERAGE", tmp_path / "cov.json")
    rep = tl.run(now=NOW, reader=_reader_seeing(state))
    assert rep["verdict"] == "GREEN", rep["red"] + rep["amber"]
