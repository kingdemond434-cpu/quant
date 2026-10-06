"""The compiler mints every chart a symbol holds bars for, M1 through D1, not M5/M15/M30 only
(principal 2026-10-06: all timeframes and all sessions), and only charts the family can run on."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mcc  # noqa: E402


@pytest.fixture
def plain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(mcc, "UNIVERSE", tmp_path)
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None)
    monkeypatch.setattr(mcc, "_session_slots",
                        lambda fam, base, sym, axis=mcc.SESSION_AXIS: [
                            (s, {**base, **({"session": s} if s != "all" else {})}, None)
                            for s in axis])
    return tmp_path


def _charts(out: list[dict[str, Any]]) -> dict[str, int]:
    seen: dict[str, int] = {}
    for v in out:
        seen[v["axis"]["chart"]] = seen.get(v["axis"]["chart"], 0) + 1
    return seen


def test_every_chart_with_bars_is_minted_and_d1_carries_no_session(plain: Path) -> None:
    for tf in ("M1", "M5", "H4", "D1"):
        (plain / f"EURUSD_{tf}.parquet").write_bytes(b"")
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": "fam_x", "params": {}}])
    n = len(mcc.SESSION_AXIS)
    assert _charts(out) == {"M1": n, "M5": n, "H4": n, "D1": 1, "H1": n}
    assert {v["params"].get("timeframe") for v in out} == {"M1", "M5", "H4", "D1", None}
    assert all(v["priority"] == (1 if v["axis"]["chart"] == "H1" else 0) for v in out)


def test_a_chart_without_bars_is_not_minted(plain: Path) -> None:
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": "fam_x", "params": {}}])
    assert _charts(out) == {"H1": len(mcc.SESSION_AXIS)}


def test_a_chart_the_family_cannot_run_on_is_not_minted(plain: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    for tf in ("M1", "D1"):
        (plain / f"EURUSD_{tf}.parquet").write_bytes(b"")
    monkeypatch.setattr(mcc, "_chart_refused", lambda fam, tf: tf == "D1")
    out = mcc.expand_axes([{"symbol": "EURUSD", "family": "fam_x", "params": {}}])
    assert "D1" not in _charts(out) and "M1" in _charts(out)


def test_the_refusal_is_the_familys_own_declaration() -> None:
    from mt5desk.families_orthogonal import FAMILY_TIMEFRAMES
    if not FAMILY_TIMEFRAMES:
        pytest.skip("no family declares a chart restriction")
    fam, (allowed, _why) = next(iter(FAMILY_TIMEFRAMES.items()))
    off = next((t for t in mcc.CHARTS if t not in allowed), None)
    if off is None:
        pytest.skip("the first declared family runs on every chart")
    assert mcc._chart_refused(fam, off) is True
    assert mcc._chart_refused(fam, "H1") is False
