"""Recorder universe (gap #39 residual, 2026-07-29).

The cost model must be calibrated on symbols the desk ACTUALLY TRADES. Both recorders unioned the
held book at boot only, and with the book halted and flat that union is empty -- so the moat was
20 majors with zero intersection with the traded universe, exactly the state gap #39 was opened
for. These tests pin the three properties that close it: traded names are found from the trade LOG
(not only live positions), traded names OUTRANK majors when the cap binds, and the weight budget
can never be exceeded by a refresh.

Both recorders carry the same ~40-line block by design (standalone processes), so every test runs
against BOTH modules -- a fix that lands in one and not its twin is the failure mode this
parametrisation exists to catch.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_MODULES = ("scripts/run_recorder.py", "scripts/run_recorder_spot.py")


def _load(rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(Path(rel).stem + "_probe", _ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # import only: the polling loop lives behind main()
    return mod


@pytest.fixture(params=_MODULES)
def rec(request: pytest.FixtureRequest, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.chdir(tmp_path)           # every read is relative to cwd; isolate from real data/
    (tmp_path / "data").mkdir()
    return _load(request.param)


def _write_positions(tmp_path: Path, syms: list[str]) -> None:
    (tmp_path / "data/cashcarry_positions.json").write_text(
        json.dumps({"positions": {s: {"qty": 1.0} for s in syms}}), "utf-8")


def _write_trades(tmp_path: Path, syms: list[str], *, ms: float) -> None:
    (tmp_path / "data/cashcarry_trades.json").write_text(
        json.dumps([{"symbol": s, "closed_ms": ms} for s in syms]), "utf-8")


def test_absent_data_files_yield_majors_only(rec: ModuleType) -> None:
    # The DR / sandbox case: no data/ files at all must not crash and must still record majors.
    uni = rec._universe()
    assert uni[:2] == ("BTCUSDT", "ETHUSDT")
    assert "SOLUSDT" in uni


def test_halted_book_still_records_recently_traded(rec: ModuleType, tmp_path: Path) -> None:
    # THE ACTUAL BUG: positions empty (book halted/flat) but the desk traded these last month.
    import time
    _write_positions(tmp_path, [])
    _write_trades(tmp_path, ["COOKIEUSDT", "EDUUSDT", "PEOPLEUSDT"], ms=time.time() * 1000.0)
    uni = rec._universe()
    for s in ("COOKIEUSDT", "EDUUSDT", "PEOPLEUSDT"):
        assert s in uni, f"{s} missing -- the cost model would stay uncalibrated for it"


def test_stale_trades_are_excluded(rec: ModuleType, tmp_path: Path) -> None:
    import time
    old_ms = (time.time() - 400 * 86400.0) * 1000.0        # ~13 months ago
    _write_trades(tmp_path, ["ANCIENTUSDT"], ms=old_ms)
    assert "ANCIENTUSDT" not in rec._universe()


def test_held_positions_are_included(rec: ModuleType, tmp_path: Path) -> None:
    _write_positions(tmp_path, ["AGLDUSDT", "CELRUSDT"])
    uni = rec._universe()
    assert "AGLDUSDT" in uni and "CELRUSDT" in uni


def test_traded_names_outrank_majors_when_the_cap_binds(rec: ModuleType,
                                                       tmp_path: Path) -> None:
    import time
    traded = [f"TRADED{i}USDT" for i in range(30)]
    _write_positions(tmp_path, traded)
    _write_trades(tmp_path, traded, ms=time.time() * 1000.0)
    uni = rec._universe()
    assert len(uni) == rec._MAX_SYMBOLS
    assert uni[0] == "BTCUSDT" and uni[1] == "ETHUSDT"     # benchmark never evicted
    # The cap bound: majors were dropped, traded names survived. Before the fix the order was
    # majors-first, so the traded names were the ones evicted -- the exact defect.
    assert sum(1 for s in uni if s.startswith("TRADED")) >= rec._MAX_SYMBOLS - 4
    assert "OPUSDT" not in uni


def test_weight_cap_trims_from_the_tail(rec: ModuleType) -> None:
    # A refresh that GROWS the set is the 2026-07-21 IP-ban hazard; growth must be bounded by
    # arithmetic. Trimming from the tail means majors go first and traded names are kept.
    big = tuple([*rec._BENCH] + [f"X{i}USDT" for i in range(200)])
    capped = rec._weight_capped(big)
    assert len(capped) < len(big)
    assert capped[0] == "BTCUSDT"
    # The twins' weight helpers take different arguments (futures: the symbol tuple, spot: a
    # count) because each mirrors its own venue's budget. Try both rather than branching on a
    # module name, so this test cannot silently take the wrong path if a signature changes.
    try:
        weight = rec._weight_per_min(capped)
    except TypeError:
        weight = rec._weight_per_min(len(capped))
    assert weight <= rec._WEIGHT_LIMIT_PER_MIN * rec._WEIGHT_TARGET_FRAC


def test_universe_is_deduped(rec: ModuleType, tmp_path: Path) -> None:
    import time
    _write_positions(tmp_path, ["BTCUSDT", "SOLUSDT"])       # already in bench/majors
    _write_trades(tmp_path, ["BTCUSDT", "SOLUSDT"], ms=time.time() * 1000.0)
    uni = rec._universe()
    assert len(uni) == len(set(uni))


def test_refresh_constants_are_sane(rec: ModuleType) -> None:
    assert 300.0 <= rec._UNIVERSE_REFRESH_S <= 86400.0      # hourly-ish, not per-tick
    assert rec._TRADED_LOOKBACK_D >= 7.0
