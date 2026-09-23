"""The rule protecting the desk's own fills was protecting the two worst numbers in the registry.

`repair_universe_spreads` refused to touch any row stamped `realized_fills`, unconditionally:
"THE DESK'S OWN EXECUTIONS BEAT AN ESTIMATE FROM BARS, ALWAYS. Ten symbols carry this and none of
them is touched: a repair that overwrote a measurement with an inference would be the same
producer collapse in a new direction."

The reasoning is right and the "ALWAYS" was not. MEASURED 2026-09-10, against each symbol's own
H1 bar median:

    GBPCHF   fills 165.0 pts vs bars   7.0  = 23.6x   (16.5 pips)
    NZDJPY   fills 147.0 pts vs bars  15.0  =  9.8x   (14.7 pips)

A bar stamp samples the WIDEST instant of its hour, so the bar median is already the wide reading
of a symbol's spread. A fills-derived value far above it is not a better measurement -- it is a
broken estimate, almost certainly slippage or a rollover caught in a handful of fills. And past
3x, a cell can never clear its own `stress_costs` gate whatever its edge, so the number is
suppressing the instrument rather than pricing it.

THE EXCEPTION IS NARROW AND THE LINE IS THE GAUNTLET'S. Inside 3x the original rule stands
untouched, which is where it was right. Only past it does the repair overrule a measurement with
an inference -- and every instance is named in its own list, because that is the one place this
tool does something it otherwise refuses to do.

AND IT STILL GOES THROUGH THE CHEAPER GATE. The override makes NZDJPY CHEAPER, which is the
direction that manufactures survivors, so it lands in `made_cheaper` and is named for a reviewer
exactly like any other cheapening repair. `--apply` remains a deliberate act.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "scripts"), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "repair_universe_spreads", _DESK / "scripts" / "repair_universe_spreads.py")
rus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rus)


def test_the_line_is_the_gauntlets_stress_multiple():
    """Not a number chosen here: past 3x a cell cannot clear its own stress_costs gate."""
    from libs.portfolio import fusion_cost as fc
    assert rus.FILLS_IMPLAUSIBLE_ABOVE_BARS == fc.IMPLAUSIBLE_ABOVE_BAR == 3.0


def _registry(tmp_path: Path, monkeypatch, rows: dict) -> None:
    """Point the repair at a throwaway registry. `run(write=False)` never touches it either."""
    reg = tmp_path / "universe.json"
    reg.write_text(json.dumps({"symbols": rows}), encoding="utf-8")
    monkeypatch.setattr(rus, "REGISTRY", reg)


def _fills(pts: float) -> dict:
    return {"median_spread_pts": pts,
            "_provenance": {"median_spread_pts": {"source": "realized_fills"}}}


def test_a_plausible_fills_value_is_still_never_touched(tmp_path, monkeypatch):
    """Inside 3x the original rule stands. XAUUSD carries fills 14.5 against bars of 16."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (16.0, "ok", {"n_priced": 5000}))
    _registry(tmp_path, monkeypatch, {"XAUUSD": _fills(14.5)})
    rep = rus.run(apply=False, write=False)
    assert rep["kept_realized_fills"] == ["XAUUSD"]
    assert rep["n_fills_overridden"] == 0


def test_an_implausible_fills_value_is_overruled_and_named(tmp_path, monkeypatch):
    """NZDJPY: 147.0 against a bar median of 15.0."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (15.0, "ok", {"n_priced": 53886}))
    _registry(tmp_path, monkeypatch, {"NZDJPY": _fills(147.0)})
    rep = rus.run(apply=False, write=False)
    assert rep["n_fills_overridden"] == 1
    row = rep["fills_overridden"][0]
    assert row["symbol"] == "NZDJPY" and row["old"] == 147.0 and row["new"] == 15.0
    assert row["over_bars"] == pytest.approx(9.8)
    assert "nothing on this symbol can pass" in row["why"]
    assert "NZDJPY" not in rep["kept_realized_fills"]


def test_the_override_still_reports_as_cheaper(tmp_path, monkeypatch):
    """It moves the charge DOWN, which is the direction that manufactures survivors, so it must
    reach a reviewer through the same gate as any other cheapening repair."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (15.0, "ok", {"n_priced": 53886}))
    _registry(tmp_path, monkeypatch, {"NZDJPY": _fills(147.0)})
    rep = rus.run(apply=False, write=False)
    assert rep["n_made_cheaper"] == 1
    assert [c["symbol"] for c in rep["made_cheaper"]] == ["NZDJPY"]


def test_the_override_has_its_own_list_and_does_not_pollute_suspect(tmp_path, monkeypatch):
    """`suspect` means "a >50x move" and is read as such. Folding a different finding into it
    would make both counts mean neither."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (15.0, "ok", {"n_priced": 53886}))
    _registry(tmp_path, monkeypatch, {"NZDJPY": _fills(147.0)})
    rep = rus.run(apply=False, write=False)
    assert rep["n_suspect"] == 0, "a 9.8x override was counted as a >50x move"
    assert rep["n_fills_overridden"] == 1


def test_a_fills_row_whose_bars_are_unmeasurable_is_left_alone(tmp_path, monkeypatch):
    """No bars, no comparison, no override. GBPCHF is in this state on a research checkout."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (None, "no local H1 bars", {}))
    _registry(tmp_path, monkeypatch, {"GBPCHF": _fills(165.0)})
    rep = rus.run(apply=False, write=False)
    assert rep["n_fills_overridden"] == 0
    assert rep["kept_realized_fills"] == ["GBPCHF"]


def test_report_mode_writes_no_registry(tmp_path, monkeypatch):
    """--apply rewrites the number every backtest, gauntlet verdict and certificate is priced
    against, and the clocks rebase on the next pass. It stays a deliberate act."""
    monkeypatch.setattr(rus, "measured_spread", lambda sym: (15.0, "ok", {"n_priced": 100}))
    _registry(tmp_path, monkeypatch, {"X": _fills(147.0)})
    before = (tmp_path / "universe.json").read_text(encoding="utf-8")
    rus.run(apply=False, write=False)
    assert (tmp_path / "universe.json").read_text(encoding="utf-8") == before
