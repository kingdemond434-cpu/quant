"""Why a plan-time fire-count prescreen cannot park UNKNOWN cells outside the sealed judge.

    python -m pytest desks/mt5/tests/test_fire_prescreen_not_separable.py -q

Coordinator queue row 176 (2026-10-20) asked for a prescreen that parks never_fires, too_rare and
lockbox_consumed_history cells before any shard is built, with prescreen + judge giving verdicts
and trial accounting byte-identical to the judge alone. This harness runs the sealed judge
(`external_gauntlet.run_gauntlet`) on synthetic dockets twice: once whole, and once with the
UNKNOWN cells taken out, as a prescreen would take them. It pins the three facts that make that
equivalence impossible:

  1. A too_rare cell moves the campaign lockbox cut. `gate_policy.lockbox_cut` is taken over the
     UNION of every cell's days. A rarely-firing cell that trades on a date no other cell holds
     (a crypto CFD firing on a Saturday) adds that date to the union, so taking it out moves the
     cut, and with it the NAMED verdicts of every other cell.
  2. Taking cells out changes the sweep's reported trial statistics: `n_cells` and the
     structural effective-trial census are computed over every cell, UNKNOWN ones included.
  3. Even the one separable case, an empty series (never fires), is only known from the series
     itself. Its verdict carries `days`, `n_signals` and `days_before_lockbox`, and the series is
     the output of the build the prescreen was meant to skip.

Nothing here changes a verdict or the judge. It is the equivalence harness, run to its result.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    return external_gauntlet


_META = {s: {"median_spread_pts": 10.0, "tick_size": 1e-5, "tick_value": 0.9,
             "contract_size": 1e5, "swap_long": -3.0, "swap_short": 1.0}
         for s in ("EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "XAUUSD")}

_START = date(2020, 1, 6)        # a Monday


def _weekdays(n: int, start: date = _START) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _series(days: list[date], seed: int, mu: float = 0.1) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mu, 1.0, len(days)), index=days, dtype=float)


def _cell(sym: str, fam: str, ds: pd.Series, seed: int) -> dict:
    return {"sym": sym, "family": fam, "params": {"seed": seed},
            "_cached_ds": ds, "_cached_ds3": ds - 0.01}


def _named() -> list[dict]:
    days = _weekdays(700)
    return [_cell("EURUSD", "carry", _series(days, 1, 0.15), 1),
            _cell("GBPUSD", "carry", _series(days, 2, 0.12), 2),
            _cell("USDJPY", "carry", _series(days, 3, 0.10), 3)]


def _never_fires() -> dict:
    return _cell("XAUUSD", "event_reaction", pd.Series([], index=[], dtype=float), 10)


def _too_rare_on_weekends() -> dict:
    sats = [d for d in (_START + timedelta(days=i) for i in range(980)) if d.weekday() == 5]
    return _cell("BTCUSD", "vol_transition", _series(sats[-30:], 11), 11)


def _lockbox_consumed() -> dict:
    # 80 weekday days, all after the campaign cut of the 700-day named panel: >= 60 before the
    # carve, 0 after it, and too short for a cell-own tail (80 - 40 < 60).
    return _cell("EURUSD", "pca_residual", _series(_weekdays(700)[-80:], 12), 12)


def _judge(eg, cells: list[dict]) -> dict:
    return eg.run_gauntlet([dict(c) for c in cells], "prescreen_harness", _META)


def _named_rows(out: dict) -> dict[str, dict]:
    return {v["cell"]: v for v in out["verdicts"] if not v.get("unmeasured")}


@pytest.fixture
def _no_terminal(monkeypatch):
    monkeypatch.setattr("research.cost_to_edge.verdict",
                        lambda *a, **k: (False, "", {"measured": False, "why": "no terminal"}))


def test_the_three_unknown_classes_are_what_the_judge_names(eg, _no_terminal,
                                                            measured_dsr_inputs) -> None:
    out = _judge(eg, [*_named(), _never_fires(), _too_rare_on_weekends(), _lockbox_consumed()])
    unk = {v["family"]: v for v in out["verdicts"] if v.get("unmeasured")}
    assert set(unk) == {"event_reaction", "vol_transition", "pca_residual"}
    assert unk["event_reaction"]["days"] == 0
    assert unk["vol_transition"]["days_before_lockbox"] == 30
    assert 0 < unk["vol_transition"]["days"] < 60
    assert unk["pca_residual"]["days_before_lockbox"] == 80
    assert unk["pca_residual"]["days"] < 60
    if "unknown_reason" in unk["pca_residual"]:          # stamped on the sealed stack's image
        assert unk["pca_residual"]["unknown_reason"] == "lockbox_consumed_history"
        assert unk["vol_transition"]["unknown_reason"] == "too_rare"


def test_parking_a_too_rare_cell_moves_the_cut_and_the_named_verdicts(eg, _no_terminal,
                                                                      measured_dsr_inputs) -> None:
    whole = _judge(eg, [*_named(), _too_rare_on_weekends()])
    parked = _judge(eg, _named())
    a, b = _named_rows(whole), _named_rows(parked)
    assert set(a) == set(b)
    cuts_a = {c: v["stages"]["lockbox"]["cut"] for c, v in a.items()}
    cuts_b = {c: v["stages"]["lockbox"]["cut"] for c, v in b.items()}
    assert cuts_a != cuts_b, "the too_rare cell's weekend days must move the union cut"
    assert any(a[c]["days"] != b[c]["days"] for c in a), \
        "a moved cut changes every named cell's development window"


def test_parking_changes_the_sweeps_trial_statistics(eg, _no_terminal,
                                                     measured_dsr_inputs) -> None:
    whole = _judge(eg, [*_named(), _never_fires(), _lockbox_consumed()])
    parked = _judge(eg, _named())
    # The named verdicts survive this pair: neither UNKNOWN cell adds a date to the union.
    assert _named_rows(whole) == _named_rows(parked)
    # The program statistics computed over the matrix (valid cells only) are unchanged ...
    assert whole["n_trials"] == parked["n_trials"]
    assert whole["program_level"] == parked["program_level"]
    # ... but the sweep's cell count and its structural trial census are not.
    assert whole["n_cells"] == parked["n_cells"] + 2
    assert whole["effective_trials"] != parked["effective_trials"]
    assert whole["n_unmeasured"] == parked["n_unmeasured"] + 2


def test_the_empty_series_is_known_only_from_the_series(eg, _no_terminal,
                                                        measured_dsr_inputs) -> None:
    out = _judge(eg, [*_named(), _never_fires()])
    nf = next(v for v in out["verdicts"] if v["family"] == "event_reaction")
    assert nf["unmeasured"] is True and nf["days"] == 0
    # The verdict records what the build produced; a cell that was never built has no series to
    # read these from, so a prescreen that skipped the build could not write this row.
    assert nf["days_before_lockbox"] == 0
    assert "n_signals" not in nf or nf["n_signals"] is None
