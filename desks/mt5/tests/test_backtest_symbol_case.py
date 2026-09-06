"""A cell admitted by the eligibility gate must not die one function later on letter case.

THE SHAPE OF THE LOSS. Fusion names its share CFDs in mixed case -- `Apple`, `Berkshire`,
`AlibabaGroup`, `Coca-Cola` -- 98 of the 251 symbols in the registry. The docket carries them
uppercased. `hold_uncoverable` compares `sym.upper()` on both sides, so every one of those cells
passed the gate whose entire job is to hold cells that cannot be replayed. Then `bars()` built
`f"{sym}_{tf}.parquet"` from the docket's spelling, asked for `ACCENTURE_H1.parquet` while the
file on disk is `Accenture_H1.parquet`, and raised inside a worker -- and the cost lookup missed
the same registry row for the same reason a few lines earlier.

Both failures are counted downstream as "produced no result", which is indistinguishable from a
cell that ran honestly and had nothing to say. MEASURED 2026-09-06: 8,057 cells run, 2,619
results, and the coverage report -- case-insensitive itself -- listed not one of them as held.
A cell held for want of plumbing is not evidence about the cell.

The two tests that matter here pull in opposite directions and both are load-bearing: case MUST
fold, and nothing beyond case may.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "side_channels"))

UNIVERSE = DESK / "data" / "universe"


@pytest.fixture(scope="module")
def mod():
    return pytest.importorskip("run_external_backtest")


@pytest.fixture(scope="module")
def mixed_case_symbols() -> list[str]:
    reg = UNIVERSE / "universe.json"
    if not reg.exists():
        pytest.skip("no universe registry on this host")
    names = [str(k) for k in json.loads(reg.read_text("utf-8")) if str(k) != str(k).upper()]
    if not names:
        pytest.skip("this registry carries no mixed-case symbols")
    return sorted(names)


def test_an_uppercased_symbol_resolves_to_the_brokers_spelling(mod, mixed_case_symbols) -> None:
    wrong = [s for s in mixed_case_symbols if mod.canonical_symbol(s.upper()) != s]
    assert not wrong, (
        "symbols whose uppercased docket spelling does not resolve back to the broker's -- "
        f"every cell on these dies inside bars(): {wrong[:10]}"
    )


def test_resolution_is_idempotent_and_case_blind(mod, mixed_case_symbols) -> None:
    sym = mixed_case_symbols[0]
    for variant in (sym, sym.upper(), sym.lower()):
        assert mod.canonical_symbol(variant) == sym, f"{variant!r} did not resolve to {sym!r}"
    assert mod.canonical_symbol(mod.canonical_symbol(sym)) == sym


def test_it_folds_case_and_nothing_else(mod) -> None:
    """CASE ONLY. `AAPL` must never become `Apple`.

    Case is not semantic in a broker's symbol table, so folding it recovers the SAME instrument
    with certainty. A ticker-to-name guess is a DIFFERENT instrument wearing a plausible label,
    and certifying a cell against the wrong instrument is the exact failure this stage exists to
    prevent. The docket really does carry `AAPL`, `AAPL.24H` and `AAPLUSD` alongside Fusion's
    `Apple`, so this is a live hazard and not a hypothetical one.
    """
    for ticker in ("AAPL", "AAPL.24H", "AAPLUSD", "ABBVIE", "ALIBABA"):
        got = mod.canonical_symbol(ticker)
        assert got == ticker or got.upper() == ticker.upper(), (
            f"canonical_symbol({ticker!r}) returned {got!r} -- that is a different instrument, "
            "not a case fold"
        )


def test_an_unknown_symbol_is_returned_unchanged(mod) -> None:
    """It must fail visibly downstream, never quietly become something that does exist."""
    assert mod.canonical_symbol("NOT_A_REAL_SYMBOL_XYZ") == "NOT_A_REAL_SYMBOL_XYZ"


def test_bars_loads_for_an_uppercased_mixed_case_symbol(mod) -> None:
    """The payoff, measured on a real chart rather than on the lookup table."""
    candidates = [p.stem.rpartition("_")[0] for p in UNIVERSE.glob("*_H1.parquet")]
    mixed = sorted({s for s in candidates if s != s.upper()})
    if not mixed:
        pytest.skip("no mixed-case H1 parquet on this host")
    sym = mixed[0]
    frame = mod.bars(sym.upper(), "H1")
    assert len(frame) > 0, f"bars({sym.upper()!r}) returned an empty frame"
