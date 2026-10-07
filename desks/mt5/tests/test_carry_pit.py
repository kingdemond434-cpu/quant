"""`family_carry` is point-in-time: a bar sees only the swap knowable at its close.

The EliteQuant review found `family_carry` applying TODAY's swap (`_swap_terms`, the newest row
on disk) to every past bar. These pin the repair: changing today's swap leaves every past signal
alone, nothing is backfilled before the first observation, a row is usable only 3 h after its
own `observed_at`, and a symbol whose honest history is below the lockbox floor reads
PENDING_HISTORY by name.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_carry as fc  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

SYM = "TESTFX"
FIRST_OBS = pd.Timestamp("2026-03-01T00:00:00Z")
N_DAYS = 50


@pytest.fixture
def tape(monkeypatch, tmp_path):
    terms = tmp_path / "contract_terms"
    terms.mkdir()
    monkeypatch.setattr(fc, "TERMS_DIR", terms)
    monkeypatch.setattr(fc, "PANEL_DIR", tmp_path / "no_panel")
    monkeypatch.setattr(fc, "UNITS", tmp_path / "no_units.json")
    monkeypatch.setattr(fc, "_CACHE", {"key": None, "hist": None, "stats": None})
    monkeypatch.setattr(fo, "TERMS", terms)
    monkeypatch.setattr(fo, "_TERMS_CACHE", None)

    def write(day: int, lo: float, sh: float, *, hour: int = 0) -> pd.Timestamp:
        at = FIRST_OBS + pd.Timedelta(days=day, hours=hour)
        pd.DataFrame([{"observed_at": at.isoformat(), "symbol": SYM, "swap_long": lo,
                       "swap_short": sh, "swap_mode": 1, "point": 1e-5,
                       "contract_size": 100_000.0}]).to_parquet(
            terms / f"{at:%Y-%m-%dT%H}.parquet", index=False)
        fc._CACHE["key"] = None
        fo._TERMS_CACHE = None
        return at

    return write


def _bars(start: str = "2026-02-15", end: str = "2026-04-25") -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="1h", tz="UTC")
    return pd.DataFrame({"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0}, index=idx)


def _carry(df: pd.DataFrame) -> list:
    return fo.family_carry(df, symbol=SYM, require_quiet=False)


def _decision(sig_time: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(sig_time) + pd.Timedelta(hours=1)          # H1 bar close


def test_changing_todays_swap_leaves_every_past_signal_unchanged(tape) -> None:
    for d in range(N_DAYS):
        tape(d, 5.0, -5.0)                                          # long pays every day
    before = _carry(_bars())
    assert before and {s.side for s in before} == {1}

    today = tape(N_DAYS, -5.0, 5.0)                                 # today's swap flips the side
    after = _carry(_bars())
    knowable = today + pd.Timedelta(hours=3)
    past_before = [(s.time, s.side, s.stop, s.target) for s in before
                   if _decision(s.time) < knowable]
    past_after = [(s.time, s.side, s.stop, s.target) for s in after
                  if _decision(s.time) < knowable]
    assert past_before and past_after == past_before, "today's swap reached a past bar"
    # ...and the flip is honoured exactly from the instant it became knowable.
    assert {s.side for s in after if _decision(s.time) >= knowable} == {-1}


def test_no_bar_before_the_first_observation_gets_a_signal(tape) -> None:
    for d in range(N_DAYS):
        tape(d, 5.0, -5.0)
    sigs = _carry(_bars())
    assert sigs
    first_usable = FIRST_OBS + pd.Timedelta(hours=3)
    assert min(_decision(s.time) for s in sigs) >= first_usable
    # A history that lies wholly before the tape began is not backfilled at all.
    assert _carry(_bars("2025-10-01", "2026-02-27")) == []


def test_a_row_is_usable_only_three_hours_after_its_own_observed_at(tape) -> None:
    for d in range(N_DAYS):
        tape(d, 5.0, -5.0)
    sigs = _carry(_bars())
    first = min(_decision(s.time) for s in sigs)
    assert first == FIRST_OBS + pd.Timedelta(hours=3)


def test_below_the_lockbox_floor_the_cell_reads_pending_history(tape) -> None:
    for d in range(5):
        tape(d, 5.0, -5.0)
    st = fo.carry_history_status(SYM, floor_days=40)
    assert st["status"] == "PENDING_HISTORY" and st["ready"] is False
    assert st["honest_days"] == 5 and st["floor_days"] == 40
    for d in range(5, 40):
        tape(d, 5.0, -5.0)
    st = fo.carry_history_status(SYM, floor_days=40)
    assert st["status"] == "READY" and st["ready"] is True and st["honest_days"] == 40


def test_the_default_floor_is_the_gauntlets_own_lockbox(tape) -> None:
    from research.gate_policy import LOCKBOX_MIN_DAYS
    tape(0, 5.0, -5.0)
    st = fo.carry_history_status(SYM)
    assert st["floor_days"] == int(LOCKBOX_MIN_DAYS)
    assert st["status"] == "PENDING_HISTORY"


def test_a_symbol_never_observed_is_pending_and_emits_nothing(tape) -> None:
    st = fo.carry_history_status("NEVERSEEN", floor_days=40)
    assert st["status"] == "PENDING_HISTORY" and st["honest_days"] == 0
    assert fo.family_carry(_bars(), symbol="NEVERSEEN") == []


def test_the_orthogonal_sweep_names_pending_history_instead_of_proposing() -> None:
    src = (DESK / "research" / "orthogonal_sweep.py").read_text("utf-8")
    assert "carry_history_status(sym)" in src and 'carry:{_hs.get(\'status\')}' in src
