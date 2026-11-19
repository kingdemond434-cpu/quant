"""fill_proven: forward R after the tape's spread, outside rollover, fails closed."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from research import fill_proven as fp


def _tape(root: Path, sym: str, day: str, hour_spreads: dict[int, float], mid: float = 1.0) -> None:
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for h, frac in hour_spreads.items():
        for m in range(0, 60, 10):
            half = mid * frac / 2
            rows.append({"ts": pd.Timestamp(f"{day} {h:02d}:{m:02d}:00", tz="UTC"),
                         "bid": mid - half, "ask": mid + half})
    pd.DataFrame(rows).to_parquet(d / f"{day}.parquet", index=False)


def _ledger(shadow: Path, label: str, trades: list[tuple[int, float]], *, entry: float = 1.0,
            risk: float = 0.01, phase: str = "forward") -> None:
    shadow.mkdir(parents=True, exist_ok=True)
    rows = [{"entry_time": f"2026-11-{(i % 9) + 10:02d} {h:02d}:00:00", "entry": entry,
             "stop": entry - risk, "exit": entry + r * risk, "r_multiple": r, "side": 1,
             "phase": phase} for i, (h, r) in enumerate(trades)]
    (shadow / f"ledger_{label}.json").write_text(json.dumps(rows), encoding="utf-8")


NOW = datetime(2026, 11, 19, 19, 0, tzinfo=UTC)


def test_positive_outside_rollover_is_admitted_and_rollover_is_cut(tmp_path: Path) -> None:
    ticks, shadow = tmp_path / "ticks", tmp_path / "shadow"
    _tape(ticks, "AUDCAD", "2026-11-18", {0: 0.005, 9: 0.0001})
    # 12 good trades at 09 and 5 rollover trades that look good on bid only.
    _ledger(shadow, "AUDCAD_x_asia", [(9, 0.5)] * 12 + [(0, 0.3)] * 5)
    doc = fp.build(shadow, ticks, NOW)
    row = doc["table"][0]
    assert row["n_out"] == 12 and row["n_rollover"] == 5
    # 09: 0.0001 * 1 / 0.01 = 0.01R charged
    assert row["adjR_out"] == pytest.approx(0.49, abs=1e-3)
    # 00: 0.005 / 0.01 = 0.5R charged, so the bid-only +0.3 becomes -0.2
    assert row["adjR_rollover"] == pytest.approx(-0.2, abs=1e-3)
    assert [(s["sleeve"], s["n_out"], s["adjR_out"]) for s in doc["sleeves"]] == [
        ("AUDCAD_x_asia", 12, row["adjR_out"])]


def test_thin_or_negative_sleeves_are_not_admitted(tmp_path: Path) -> None:
    ticks, shadow = tmp_path / "ticks", tmp_path / "shadow"
    _tape(ticks, "EURUSD", "2026-11-18", {9: 0.0001})
    _ledger(shadow, "EURUSD_thin", [(9, 1.0)] * 9)
    _ledger(shadow, "EURUSD_neg", [(9, -0.1)] * 20)
    doc = fp.build(shadow, ticks, NOW)
    assert doc["sleeves"] == []
    assert doc["n_sleeves_read"] == 2


def test_no_tape_is_unmeasured_never_free(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    _ledger(shadow, "USDSGD_carry", [(9, 1.0)] * 30)
    doc = fp.build(shadow, tmp_path / "no_ticks", NOW)
    row = doc["table"][0]
    assert row["n_unmeasured"] == 30 and row["n_out"] == 0
    assert doc["sleeves"] == [] and doc["symbols_without_tape"] == ["USDSGD"]


def test_backtest_phase_rows_are_ignored(tmp_path: Path) -> None:
    ticks, shadow = tmp_path / "ticks", tmp_path / "shadow"
    _tape(ticks, "XAUUSD", "2026-11-18", {9: 0.0001})
    _ledger(shadow, "XAUUSD_asia", [(9, 1.0)] * 20, phase="historical")
    assert fp.build(shadow, ticks, NOW)["table"] == []


def test_frozen_shared_ledger_is_never_read(tmp_path: Path) -> None:
    ticks, shadow = tmp_path / "ticks", tmp_path / "shadow"
    _tape(ticks, "GBPAUD", "2026-11-18", {9: 0.0001})
    _ledger(shadow, "GBPAUD_shared_asia", [(9, 1.0)] * 20)
    (shadow / "shared_ledgers.json").write_text(
        json.dumps({"files": {"ledger_GBPAUD_shared_asia.json": {"members": ["a", "b"]}}}), encoding="utf-8")
    assert fp.build(shadow, ticks, NOW)["sleeves"] == []


def test_stop_distance_falls_back_to_the_trade_outcome() -> None:
    assert fp.stop_distance({"entry": 2.0, "exit": 2.03, "r_multiple": 1.5}) == pytest.approx(0.02)
    assert fp.stop_distance({"entry": 2.0}) is None


def test_write_and_main_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "FILL_PROVEN.json"
    real_build, real_write = fp.build, fp.write
    monkeypatch.setattr(fp, "build", lambda: real_build(tmp_path / "shadow", tmp_path / "ticks", NOW))
    monkeypatch.setattr(fp, "write", lambda doc: real_write(doc, out))
    assert fp.main(["--once"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema"] == fp.SCHEMA and doc["sleeves"] == []


def test_noise_positives_fail_the_fdr_and_are_not_admitted(tmp_path: Path) -> None:
    """A barely positive, noisy mean among many tried sleeves is not admitted."""
    ticks, shadow = tmp_path / "ticks", tmp_path / "shadow"
    _tape(ticks, "EURUSD", "2026-11-18", {9: 0.0001})
    noisy = [(9, 1.5), (9, -1.4)] * 6  # mean ~ +0.04R, sd ~ 1.5R, n = 12
    for i in range(20):
        _ledger(shadow, f"EURUSD_noise{i}_asia", noisy)
    _ledger(shadow, "EURUSD_real_asia", [(9, 0.6), (9, 0.4)] * 10)
    doc = fp.build(shadow, ticks, NOW)
    assert [s["sleeve"] for s in doc["sleeves"]] == ["EURUSD_real_asia"]
    assert doc["n_positive_failing_fdr"] == 20
    assert doc["rule"]["n_tested"] == 21


def test_moat_compact_file_without_ts_is_read_from_time_msc(tmp_path: Path) -> None:
    ticks = tmp_path / "ticks"
    d = ticks / "AUDCAD"
    d.mkdir(parents=True)
    ms = int(pd.Timestamp("2026-11-18 09:00", tz="UTC").timestamp() * 1000)
    pd.DataFrame({"time_msc": [ms, ms + 1000], "bid": [0.999, 0.999],
                  "ask": [1.001, 1.001]}).to_parquet(d / "20261118.parquet", index=False)
    spreads, used = fp.spread_by_hour("AUDCAD", ticks)
    assert used == 1 and spreads[9] == pytest.approx(0.002, rel=1e-3)
