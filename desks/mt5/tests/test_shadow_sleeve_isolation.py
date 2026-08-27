"""One unevaluable sleeve must never discard the whole forward pass.

THE ORIGINAL FAILURE, measured live on contabo-mt5 2026-08-27. `shadow_forward.main` evaluated
sleeves in a bare loop and wrote `shadow_state.json` only AFTER the loop finished. A certificate
existed for `EURZAR`, a symbol absent from that box's 23-row cost map, so `per_symbol_costs`
raised `KeyError: 'EURZAR'` -- and every sleeve already evaluated in that pass (CADJPY and EURJPY
had both produced trades) was thrown away with it. Repeated every 15 minutes for 5.5 hours: the
desk's entire forward book stopped accruing while the logs showed sleeves being evaluated.

Forward evidence is this desk's stated readiness blocker, so a pass that computes evidence and
then discards it is the most expensive silence available in this file. The test pins the
PROPERTY -- one bad row costs one row -- rather than the EURZAR instance, because the next
missing key will have a different name.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward  # noqa: E402


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


def _bars() -> _FakeBars:
    idx = pd.date_range("2026-08-16", periods=48, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0,
         "tick_volume": 1, "spread": 1, "real_volume": 0}, index=idx)
    return _FakeBars(df=frame)


def _wire(monkeypatch, tmp_path: Path, enrolled: list[tuple[str, str, dict]], meta: dict) -> Path:
    universe = tmp_path / "universe"
    universe.mkdir(parents=True)
    (universe / "universe.json").write_text(json.dumps(meta), encoding="utf-8")
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir(parents=True)

    monkeypatch.setattr(shadow_forward, "UNI", universe)
    monkeypatch.setattr(shadow_forward, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(shadow_forward, "SLEEVES", [])
    monkeypatch.setattr(shadow_forward, "certified_sleeves", lambda: enrolled)
    monkeypatch.setattr(shadow_forward, "fetch_h1", lambda sym: _bars())
    monkeypatch.setattr(shadow_forward, "_family_fn",
                        lambda fam: (lambda df, **kw: pd.Series(0, index=df.index)))
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)

    import mt5desk.engine as engine
    monkeypatch.setattr(engine, "run_backtest", lambda *a, **k: _FakeResult(trades=[]))

    # HERMETIC BY PATH, NOT BY CWD. `sleeve_registry` resolves its file from `__file__`, so a
    # `cwd=tmp_path` would NOT redirect it and this test would freeze identities into -- and
    # compare against -- the desk's live registry. Redirect the module global instead.
    import sleeve_registry
    monkeypatch.setattr(sleeve_registry, "REGISTRY", tmp_path / "sleeve_registry.json")
    return shadow_dir


def test_missing_cost_map_entry_blocks_one_sleeve_and_never_the_book(
    tmp_path: Path, monkeypatch,
) -> None:
    """The exact 2026-08-27 shape: the FIRST sleeve is uncostable, the rest must still land."""
    good_meta = {"contract_size": 100000.0, "tick_size": 0.001, "tick_value": 0.5,
                 "min_volume": 0.01, "volume_step": 0.01, "median_spread_pts": 10.0}
    enrolled = [
        ("EURZAR", "asia", {}, "overnight_gap_decay"),   # absent from the cost map
        ("EURJPY", "asia", {}, "session_range_breakout"),
        ("CADJPY", "asia", {}, "session_range_breakout"),
    ]
    shadow_dir = _wire(monkeypatch, tmp_path, enrolled, {"EURJPY": good_meta, "CADJPY": good_meta})

    shadow_forward.main()

    state_path = shadow_dir / "shadow_state.json"
    assert state_path.exists(), "the pass wrote nothing at all -- one bad sleeve killed the book"
    state = json.loads(state_path.read_text("utf-8"))

    # Every costable sleeve was evaluated and recorded, even though a sleeve BEFORE them failed.
    for key in ("EURJPY.asia", "CADJPY.asia"):
        assert key in state, f"{key} was evaluated but discarded with the failing sleeve"
        assert state[key]["status"] == "ACTIVE"
        assert state[key].get("last_attempt_at"), f"{key} did not sign its evaluation"

    # The failure is RECORDED, not swallowed: it must be visible as an explicit blocked status.
    bad = state["EURZAR.overnight_gap_decay.asia"]
    assert bad["status"] == "BLOCKED_SLEEVE_ERROR"
    assert "KeyError" in bad["last_error"] and "EURZAR" in bad["last_error"]
    assert bad["last_error_at"]


def test_blocked_status_is_counted_as_evidence_blocked_by_the_cycle() -> None:
    """Isolation without visibility would be a worse trade than the crash it replaced.

    `shadow_cycle` publishes `evidence_blocked_sleeves`, which the read-only watchdog turns into
    a defect. If the isolation status is missing from that set, a permanently unevaluable sleeve
    reads as a healthy book -- absence as a clean verdict (WS-005).
    """
    source = (DESK / "research" / "shadow_cycle.py").read_text("utf-8")
    assert "BLOCKED_SLEEVE_ERROR" in source, (
        "shadow_forward can emit BLOCKED_SLEEVE_ERROR but shadow_cycle does not count it")


def test_a_terminal_verdict_survives_a_blocked_evaluation(tmp_path: Path, monkeypatch) -> None:
    """A KILL or PROMOTION CANDIDATE is a decision; a transient failure must not undo it."""
    enrolled = [("EURZAR", "asia", {}, "overnight_gap_decay")]
    shadow_dir = _wire(monkeypatch, tmp_path, enrolled, {})
    (shadow_dir / "shadow_state.json").write_text(json.dumps({
        "EURZAR.overnight_gap_decay.asia": {"n": 51, "cum_r": 3.0, "exp_r": 0.06,
                                            "max_dd_r": -2.0, "status": "KILL"},
    }), encoding="utf-8")

    shadow_forward.main()

    row = json.loads((shadow_dir / "shadow_state.json").read_text("utf-8"))[
        "EURZAR.overnight_gap_decay.asia"]
    assert row["status"] == "KILL", "a blocked pass overwrote a verdict the desk already reached"
    assert row["n"] == 51, "a blocked pass destroyed evidence it did not re-measure"
    assert "KeyError" in row["last_error"]
