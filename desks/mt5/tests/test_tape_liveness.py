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


#: Every class has been open for 3h, so a stale symbol in an open class is settled and RED.
SETTLED = {"classes": {c: {"open": True, "open_since": (NOW - timedelta(hours=3)).isoformat()}
                       for c in ("Commodities", "Forex", "Crypto", "Equities")}}


def _reader_seeing(state: dict, lag_h: float = 0.0, spread: float = 0.1):
    def read(sym: str):
        t = datetime.fromisoformat(state[sym]["last_tick_utc"]) - timedelta(hours=lag_h)
        return _frame(t, spread=spread)
    return read


def test_closed_equities_are_not_red_but_a_dead_fx_symbol_in_an_open_class_is():
    block, red, _ = tl.recorder_block(_state(LIVE), UNIVERSE, NOW, SETTLED)
    assert red == []
    assert block["classes"]["Equities"]["open"] is False
    ages = dict(LIVE, USDJPY=5.0)
    _, red, _ = tl.recorder_block(_state(ages), UNIVERSE, NOW, SETTLED)
    assert any(r.startswith("SYMBOL_STALE") and "USDJPY" in r for r in red)


def test_a_class_that_just_opened_does_not_flap_red_for_its_thin_names():
    """Session open: half the names have ticked, the thin ones still carry last night's stamp."""
    ages = dict(LIVE, Apple=0.1, Tesla=16.0)
    block, red, _ = tl.recorder_block(_state(ages), UNIVERSE, NOW, prior={"classes": {}})
    assert block["classes"]["Equities"]["open"] is True
    assert block["classes"]["Equities"]["settled"] is False
    assert red == []
    # ... and the same reading 2h+ later, the class still open, is RED for the dead name.
    later = NOW + timedelta(hours=2, minutes=5)
    st = {s: {"last_tick_utc": (later - timedelta(hours=h)).isoformat()} for s, h in ages.items()}
    _, red, _ = tl.recorder_block(st, UNIVERSE, later, prior=block)
    assert any(r.startswith("SYMBOL_STALE") and "Tesla" in r for r in red)


def test_recorder_down_when_crypto_stops_even_on_a_weekend():
    ages = dict.fromkeys(LIVE, 30.0)
    _, red, _ = tl.recorder_block(_state(ages), UNIVERSE, NOW, SETTLED)
    assert any(r.startswith("RECORDER_DOWN") for r in red)


def test_retired_and_untaped_symbols_are_amber_not_red():
    state = _state(dict(LIVE, Palantir=1300.0))
    state.pop("Tesla")
    block, red, amber = tl.recorder_block(state, UNIVERSE, NOW, SETTLED)
    assert red == []
    assert block["retired"] == ["Palantir"]
    assert block["untaped_universe_symbols"] == ["Tesla"]
    assert len(amber) == 2


def test_no_universe_is_unmeasured_not_green():
    _, red, amber = tl.recorder_block(_state(LIVE), {}, NOW, SETTLED)
    assert red == []
    assert any("universe.json absent" in a for a in amber)
    assert any("no Crypto class" in a for a in amber)


def test_blind_reader_is_red_while_the_recorder_is_green():
    """The 2026-10-29 failure: recorder fresh, the reader returning nothing."""
    state = _state(LIVE)
    _, red, _ = tl.reader_block(state, NOW, reader=lambda sym: None)
    assert len([r for r in red if r.startswith("READER_BLIND")]) == len(tl.PROBES)


def test_a_blind_reader_on_an_untaped_probe_is_unmeasured_not_green():
    _, red, amber = tl.reader_block({}, NOW, reader=lambda sym: None)
    assert red == []
    assert len(amber) == len(tl.PROBES)


def test_reader_behind_the_recorder_is_red():
    state = _state(LIVE)
    _, red, _ = tl.reader_block(state, NOW, reader=_reader_seeing(state, lag_h=24 * 40))
    assert any(r.startswith("READER_BLIND") and "behind" in r for r in red)
    _, red, amber = tl.reader_block(state, NOW, reader=_reader_seeing(state))
    assert red == [] and amber == []


def test_zero_spread_is_red():
    state = _state(LIVE)
    _, red, _ = tl.reader_block(state, NOW, reader=_reader_seeing(state, spread=0.0))
    assert any(r.startswith("ZERO_SPREAD") for r in red)


def test_a_reader_that_raises_is_a_finding_not_a_crash():
    def boom(sym: str):
        raise OSError("disk")
    out, red, _ = tl.reader_block(_state(LIVE), NOW, reader=boom)
    assert all(out[s]["verdict"] == "BLIND" for s in tl.PROBES)
    assert red


def test_tape_cells_mined_but_never_judged_is_red():
    cov = {"at": NOW.isoformat(), "families": {
        "liquidity_regime": {"mined": 24963, "judged_total": 0},
        "orderflow_imbalance": {"mined": 41330, "judged_total": 12},
        "execution_state": {"mined": 0, "judged_total": 0}}}
    _, red, amber = tl.judge_block(cov, NOW)
    assert red == ["TAPE_NEVER_JUDGED: liquidity_regime has 24963 mined cells and 0 verdicts"]
    assert amber == []


def test_absent_or_stale_coverage_is_unmeasured():
    _, red, amber = tl.judge_block(None, NOW)
    assert red == [] and any("absent" in a for a in amber)
    old = {"at": (NOW - timedelta(hours=7238)).isoformat(), "families": {
        f: {"mined": 10, "judged_total": 3} for f in tl.TAPE_FAMILIES}}
    _, red, amber = tl.judge_block(old, NOW)
    assert red == [] and any("old" in a for a in amber)


def _point(tmp_path, monkeypatch, universe, cov) -> dict:
    import json
    state = _state(LIVE)
    (tmp_path / "state.json").write_text(json.dumps(state))
    if universe is not None:
        (tmp_path / "universe.json").write_text(json.dumps(universe))
    if cov is not None:
        (tmp_path / "cov.json").write_text(json.dumps(cov))
    monkeypatch.setattr(tl, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(tl, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(tl, "JUDGE_COVERAGE", tmp_path / "cov.json")
    monkeypatch.setattr(tl, "OUT", tmp_path / "TAPE_LIVENESS.json")
    ticks = tmp_path / "ticks"
    _probe_files(ticks, ["2026-10-29.parquet", "20261029.parquet"])
    monkeypatch.setattr(tl, "TICKS", ticks)
    return state


def test_run_is_green_end_to_end(tmp_path, monkeypatch):
    cov = {"at": NOW.isoformat(), "families": {
        f: {"mined": 10, "judged_total": 3} for f in tl.TAPE_FAMILIES}}
    state = _point(tmp_path, monkeypatch, UNIVERSE, cov)
    rep = tl.run(now=NOW, reader=_reader_seeing(state), prior=SETTLED)
    assert rep["verdict"] == "GREEN", rep["red"] + rep["amber"]


def test_run_with_nothing_to_measure_is_never_green(tmp_path, monkeypatch):
    state = _point(tmp_path, monkeypatch, None, None)
    rep = tl.run(now=NOW, reader=_reader_seeing(state), prior=SETTLED)
    assert rep["verdict"] == "AMBER"


def test_main_writes_the_report_and_carries_open_since(tmp_path, monkeypatch):
    import json
    cov = {"at": NOW.isoformat(), "families": {
        f: {"mined": 10, "judged_total": 3} for f in tl.TAPE_FAMILIES}}
    state = _point(tmp_path, monkeypatch, UNIVERSE, cov)
    monkeypatch.setattr(tl, "_default_reader", _reader_seeing(state))
    assert tl.main() == 0
    rep = json.loads((tmp_path / "TAPE_LIVENESS.json").read_text())
    assert rep["recorder"]["classes"]["Forex"]["open_since"]
    assert not list(tmp_path.glob("*.tmp"))


def test_a_failed_replace_leaves_no_temp_file(tmp_path, monkeypatch):
    def deny(src, dst):
        raise PermissionError("WinError 5")
    monkeypatch.setattr(tl.os, "replace", deny)
    tl.write_report({"verdict": "RED"}, tmp_path / "TAPE_LIVENESS.json")
    assert not list(tmp_path.iterdir())


def test_a_whole_class_dead_in_its_core_session_is_red():
    """Auditor S1, live on 10-29: every equity last ticked 10-28 22:59Z during the US session.
    Peers cannot catch it (all dead together); the core session can."""
    us_open = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
    st = {s: {"last_tick_utc": (us_open - timedelta(hours=h)).isoformat()}
          for s, h in dict(LIVE, Apple=17.0, Tesla=17.0).items()}
    block, red, _ = tl.recorder_block(st, UNIVERSE, us_open, SETTLED)
    assert block["classes"]["Equities"]["in_core_session"] is True
    assert any(r.startswith("CLASS_DEAD: Equities") for r in red)
    # ... and the same stale equities at 22:00Z, after the session, are not RED.
    late = datetime(2026, 10, 29, 22, 0, tzinfo=UTC)
    st = {s: {"last_tick_utc": (late - timedelta(hours=h)).isoformat()}
          for s, h in dict(LIVE, Apple=2.5, Tesla=2.5).items()}
    _, red, _ = tl.recorder_block(st, UNIVERSE, late, SETTLED)
    assert not any(r.startswith("CLASS_DEAD") for r in red)


def test_a_long_dead_symbol_steps_down_to_amber_and_stays_named():
    """Auditor S2: a suspended name in an open class must not hold the board RED forever."""
    ages = dict(LIVE, USDJPY=5.0)
    prior = dict(SETTLED, stale_since={"USDJPY": (NOW - timedelta(days=4)).isoformat()})
    block, red, amber = tl.recorder_block(_state(ages), UNIVERSE, NOW, prior)
    assert not any("USDJPY" in r for r in red)
    assert any(a.startswith("LONG_DEAD") and "USDJPY" in a for a in amber)
    assert block["stale_since"]["USDJPY"] == prior["stale_since"]["USDJPY"]


def _probe_files(root: Path, names: list[str]) -> None:
    d = root / tl.WRITER_PROBE
    d.mkdir(parents=True)
    for n in names:
        (d / n).write_bytes(b"")


def test_a_dead_compact_writer_is_red_even_while_tape_state_is_fresh(tmp_path):
    """Auditor S3: tape_state.json is only the dashed writer's; the silver needs its own proof."""
    _probe_files(tmp_path, ["2026-10-29.parquet", "20260916.parquet"])
    _, red, _ = tl.writer_block(NOW, tmp_path)
    assert red and "compact" in red[0]
    _probe_files(tmp_path / "ok", ["2026-10-29.parquet", "20261029.parquet"])
    _, red, amber = tl.writer_block(NOW, tmp_path / "ok")
    assert red == [] and amber == []
    _, red, amber = tl.writer_block(NOW, tmp_path / "absent")
    assert red == [] and amber
