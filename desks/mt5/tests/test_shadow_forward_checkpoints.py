"""A forward pass that is killed must keep what it evaluated, and the next one must move on.

`shadow_forward.main` wrote `shadow_state.json` once, after the last row. Every caller runs it
under a kill (enrol_clocks 2,700 s, clock_fixer <= 600 s, MT5-Shadow's task limit), so a pass
long enough to be cut wrote nothing, and the next pass walked the same alphabetical prefix and
was cut again: every clock kept status ACTIVE while its tick only aged (ENGINE_SILENT).

These pin the three properties of the fix: checkpoints survive a kill, a cut pass starts where
the book waited longest, and a write merges instead of reverting other organs' rows.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward  # noqa: E402

_META = {"contract_size": 100000.0, "tick_size": 0.001, "tick_value": 0.5,
         "min_volume": 0.01, "volume_step": 0.01, "median_spread_pts": 10.0}


@dataclass
class _FakeBars:
    df: pd.DataFrame
    source: str = "MT5:Test"
    evidence_venue: str = "Test"
    stale: bool = False
    promotion_authority: bool = True

    def stamp(self) -> dict[str, Any]:
        return {"bar_source": self.source}


@dataclass
class _FakeResult:
    trades: list[Any]


class _Killed(BaseException):
    """What a task-scheduler kill looks like from inside the loop: nothing catches it."""


def _bars() -> _FakeBars:
    idx = pd.date_range("2026-08-16", periods=48, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0,
                          "tick_volume": 1, "spread": 1, "real_volume": 0}, index=idx)
    return _FakeBars(df=frame)


def _wire(monkeypatch, tmp_path: Path, symbols: list[str], fetch=None) -> Path:
    universe = tmp_path / "universe"
    universe.mkdir(parents=True)
    (universe / "universe.json").write_text(json.dumps(dict.fromkeys(symbols, _META)), "utf-8")
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir(parents=True)
    enrolled = [(s, "asia", {}, "session_range_breakout") for s in symbols]
    monkeypatch.setattr(shadow_forward, "UNI", universe)
    monkeypatch.setattr(shadow_forward, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(shadow_forward, "SLEEVES", [])
    monkeypatch.setattr(shadow_forward, "certified_sleeves", lambda: list(enrolled))
    monkeypatch.setattr(shadow_forward, "fetch_h1",
                        fetch or (lambda sym, timeframe="H1": _bars()))
    monkeypatch.setattr(shadow_forward, "_family_fn",
                        lambda fam: (lambda df, **kw: pd.Series(0, index=df.index)))
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)
    monkeypatch.setattr(shadow_forward, "_enrolment_watermark", lambda *a: None)
    import mt5desk.engine as engine
    monkeypatch.setattr(engine, "run_backtest", lambda *a, **k: _FakeResult(trades=[]))
    import sleeve_registry
    monkeypatch.setattr(sleeve_registry, "REGISTRY", tmp_path / "sleeve_registry.json")
    import research.clock_ledger as clock_ledger
    monkeypatch.setattr(clock_ledger, "LEDGER", tmp_path / "forward_clock_ledger.json")
    monkeypatch.setattr(clock_ledger.stamp, "__kwdefaults__",
                        {"path": tmp_path / "forward_clock_ledger.json"})
    return shadow_dir


def test_a_killed_pass_keeps_the_rows_it_evaluated(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1") -> _FakeBars:
        calls.append(sym)
        if sym == "GBPUSD":
            raise _Killed()
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD", "EURUSD", "GBPUSD"], fetch)
    monkeypatch.setattr(shadow_forward, "CHECKPOINT_S", 0.0)
    with pytest.raises(_Killed):
        shadow_forward.main()

    state = json.loads((shadow_dir / "shadow_state.json").read_text("utf-8"))
    for key in ("AUDUSD.asia", "EURUSD.asia"):
        assert state.get(key, {}).get("last_attempt_at"), (
            f"{key} was evaluated before the kill and its tick was thrown away with the pass")
    assert state["engine_pass"]["complete"] is False
    assert not list(shadow_dir.glob(".*.tmp")), "a checkpoint left its temp file behind"


def test_the_next_pass_starts_where_the_book_waited_longest(tmp_path: Path,
                                                            monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1") -> _FakeBars:
        calls.append(sym)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD", "EURUSD", "GBPUSD"], fetch)
    (shadow_dir / "shadow_state.json").write_text(json.dumps({
        "AUDUSD.asia": {"status": "ACTIVE", "last_attempt_at": "2026-09-30T10:00:00+00:00"},
        "EURUSD.asia": {"status": "ACTIVE", "last_attempt_at": "2026-09-23T10:00:00+00:00"},
    }), "utf-8")
    shadow_forward.main()
    assert calls == ["GBPUSD", "EURUSD", "AUDUSD"], (
        f"visited {calls}: never-attempted first, then oldest tick -- a cut pass must not "
        "spend itself on the prefix the last pass already reached")


def test_a_write_merges_rows_other_organs_wrote_during_the_pass(tmp_path: Path,
                                                               monkeypatch) -> None:
    holder: dict[str, Path] = {}

    def fetch(sym: str, timeframe: str = "H1") -> _FakeBars:
        path = holder["dir"] / "shadow_state.json"
        doc = json.loads(path.read_text("utf-8"))
        doc["OTHER.asia"] = {"status": "RETIRED_ORPHAN", "written_by": "another organ"}
        doc.pop("GONE.asia", None)
        path.write_text(json.dumps(doc), "utf-8")
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD"], fetch)
    holder["dir"] = shadow_dir
    (shadow_dir / "shadow_state.json").write_text(json.dumps({
        "GONE.asia": {"status": "RETIRED_NO_CERTIFICATE"}}), "utf-8")
    shadow_forward.main()
    state = json.loads((shadow_dir / "shadow_state.json").read_text("utf-8"))
    assert state["OTHER.asia"]["written_by"] == "another organ", (
        "the pass wrote back its start-of-pass snapshot over another organ's row")
    assert "GONE.asia" not in state, "a row another organ evacuated was resurrected"
    assert state["AUDUSD.asia"]["last_attempt_at"]
    assert state["engine_pass"]["complete"] is True


def test_the_write_survives_a_windows_replace_refusal(tmp_path: Path, monkeypatch) -> None:
    """os.replace onto a read-only or open file raises WinError 5 on Windows; publish anyway."""
    target = tmp_path / "shadow_state.json"
    target.write_text("{}", "utf-8")

    def refuse(src: Any, dst: Any) -> None:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(shadow_forward.os, "replace", refuse)
    monkeypatch.setattr(shadow_forward.time, "sleep", lambda s: None)
    shadow_forward._atomic_write_text(target, '{"k": 1}')
    assert json.loads(target.read_text("utf-8")) == {"k": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["shadow_state.json"]
    assert os.access(target, os.W_OK)
