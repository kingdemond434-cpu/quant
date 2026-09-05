"""The private tape is mined on a CYCLE, never as a fixed alphabetical prefix.

MEASURED 2026-08-28 from the trading box's own `moat_miner_state.json`: `symbols_profiled: 40`
against 245 recorded tick-symbol directories under `C:\\moat\\bronze\\mt5_ticks`. The selection
was `sorted(...)[:MAX_SYMBOLS]` -- a fixed alphabetical prefix with no cursor -- so the same
first 40 symbols were re-mined on every run and 205 (83.7%) had never been mined and never would
be. On alphabetical order the untouched set is every metal, every index, energy, softs and all
but a handful of FX crosses: the tape the desk pays to record and nobody else can buy.

TWO LAWS IN ONE LINE. The sealed core: "a count is a quota in disguise and a quota acts as a
CEILING -- rank-and-truncate is the same defect wearing an ordering", and under-exploration of an
owned dataset is a BREACH rather than a backlog. RESEARCH 6c-bis: the searcher carries a rotation
cursor, each run covers a budgeted slice, the cursor advances, and every symbol is re-searched on
newer ticks forever -- so "exhausted" is never a state.

SECOND SIGHTING OF THIS CLASS, which is why it is fenced rather than merely corrected:
`orthogonal_sweep` was pairing XAUUSD with 3M off `sorted()[:12]` over the same universe.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from moat.moat_miner import _next_slice  # noqa: E402
from moat import moat_miner as M  # noqa: E402


def _syms(n: int) -> list[str]:
    return [f"S{i:03d}" for i in range(n)]


def test_the_whole_tape_is_covered_rather_than_an_alphabetical_head(monkeypatch) -> None:
    monkeypatch.setattr(M, "SLICE_SYMBOLS", 40)
    syms, seen, cursor, runs = _syms(245), set(), 0, 0
    while len(seen) < len(syms) and runs < 100:
        picked, cursor = _next_slice(syms, cursor)
        seen.update(picked)
        runs += 1
    assert seen == set(syms), f"{len(syms) - len(seen)} symbols unreachable"
    assert runs == 7, f"245 symbols at a 40-slice should close in 7 runs, took {runs}"


def test_the_cursor_wraps_so_coverage_is_a_cycle_not_a_sweep(monkeypatch) -> None:
    """A cursor that stops at the end declares the tape finished -- absence as a verdict."""
    monkeypatch.setattr(M, "SLICE_SYMBOLS", 40)
    syms, cursor = _syms(245), 0
    for _ in range(7):                       # one full pass
        _, cursor = _next_slice(syms, cursor)
    seen, runs = set(), 0
    while len(seen) < len(syms) and runs < 100:
        picked, cursor = _next_slice(syms, cursor)
        seen.update(picked)
        runs += 1
    assert seen == set(syms), "the second pass did not re-cover the tape"


def test_a_slice_never_repeats_a_symbol_within_itself(monkeypatch) -> None:
    """Wrapping must not spend the budget mining the same symbol twice in one run."""
    monkeypatch.setattr(M, "SLICE_SYMBOLS", 40)
    syms = _syms(10)                          # slice wider than the tape
    picked, _ = _next_slice(syms, 3)
    assert len(picked) == len(set(picked)) == 10


def test_an_empty_tape_is_not_a_crash_and_not_a_moved_cursor() -> None:
    assert _next_slice([], 5) == ([], 0)


def test_the_budget_is_named_a_budget_not_a_ceiling() -> None:
    """Caps on owned-data coverage are compute budgets and must SAY SO (LAWS/6c-bis)."""
    src = (_DESK / "moat" / "moat_miner.py").read_text("utf-8")
    assert "PER-RUN COMPUTE BUDGET, NOT A LIMIT" in src
    assert "sorted([d for d in tick_root.iterdir() if d.is_dir()])[:" not in src, \
        "the alphabetical-prefix selection is back"


def test_the_cursor_is_persisted_or_it_resets_to_the_same_head_every_run() -> None:
    """An in-memory cursor is the original defect with extra steps."""
    src = (_DESK / "moat" / "moat_miner.py").read_text("utf-8")
    assert '"cursor": cursor' in src
    assert '.get("cursor", 0)' in src
