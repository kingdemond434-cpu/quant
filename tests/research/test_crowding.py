"""The residual crowding measure must separate a COMPETITOR from a REGIME.

That separation is the whole reason this module exists alongside `run_carry_crowding.py`, so it is
the property under test: a universe-wide compression (a regime) and a compression confined to our
held names (a competitor) produce the same top-20 average and must produce DIFFERENT verdicts here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research.crowding import (
    MIN_SNAPSHOTS,
    assess,
    percentile_of,
    residual_bps,
    symbol_crowding,
)


def _universe(base: float, n: int = 200) -> list[float]:
    """A cross-section spread around ``base`` -- deterministic, no RNG."""
    return [base + (i - n / 2) * 1e-6 for i in range(n)]


def test_percentile_counts_ties_as_at_or_below() -> None:
    # Hundreds of perps pin at the same base rate; a strict inequality would read a name sitting
    # exactly at the mode as being at the bottom of it.
    assert percentile_of(0.0, [0.0, 0.0, 0.0, 0.0]) == 1.0
    assert percentile_of(-1.0, [0.0, 0.0]) == 0.0
    assert percentile_of(0.5, [0.0, 1.0]) == 0.5


def test_percentile_and_residual_refuse_an_empty_universe() -> None:
    # No denominator must never read as a neutral position in the distribution.
    assert percentile_of(0.01, []) != percentile_of(0.01, [])   # NaN != NaN
    assert residual_bps(0.01, []) != residual_bps(0.01, [])


def test_residual_uses_the_median_not_the_mean() -> None:
    # One squeezed name must not drag the benchmark and manufacture a residual out of arithmetic.
    uni = [0.0, 0.0, 0.0, 0.0, 1.0]
    assert residual_bps(0.0, uni) == 0.0


def test_alignment_is_required_not_assumed() -> None:
    # A residual taken against a different instant's universe is not a residual.
    rates = [0.001] * MIN_SNAPSHOTS
    assert symbol_crowding("X", rates, [_universe(0.0)] * (MIN_SNAPSHOTS - 1)) is None
    assert symbol_crowding("X", rates[:2], [_universe(0.0)] * 2) is None


def test_regime_wide_compression_is_not_read_as_crowding() -> None:
    """THE CORE TEST. Everything compresses together -- our name's RESIDUAL is unchanged."""
    n = 24
    rates, universes = [], []
    for i in range(n):
        base = 0.0010 - i * 0.00004        # the whole universe compresses hard
        rates.append(base + 0.0002)        # our name keeps its SAME premium over the universe
        universes.append(_universe(base))
    sc = symbol_crowding("REGIME", rates, universes)
    assert sc is not None
    assert abs(sc.residual_drift_bps) < 0.5, sc
    assert assess([sc])["verdict"] == "OK"


def test_targeted_compression_on_our_name_is_caught() -> None:
    """The competitor case: the universe is flat and OUR name alone decays."""
    n = 24
    rates, universes = [], []
    for i in range(n):
        universes.append(_universe(0.0010))
        rates.append(0.0016 - i * 0.00004)   # our premium erodes while the universe sits still
    sc = symbol_crowding("TARGET", rates, universes)
    assert sc is not None
    assert sc.residual_drift_bps < -1.0, sc
    assert sc.percentile_drift < 0.0, sc
    assert sc.sufficient, sc.reason
    out = assess([sc])
    assert out["verdict"] == "CROWDING", out
    assert out["confirmed_both_tells"] == ["TARGET"]


def test_a_residual_move_without_a_rank_move_is_only_partial() -> None:
    # Either tell alone is defeatable, so neither alone may raise the book-level alarm.
    n = 24
    rates, universes = [], []
    for i in range(n):
        # Universe RISES; our name holds flat. Residual falls, but our rank does not, because we
        # stay above every universe member throughout.
        universes.append(_universe(0.0002 + i * 0.00004))
        rates.append(0.0050)
    sc = symbol_crowding("SHIFT", rates, universes)
    assert sc is not None
    assert sc.residual_drift_bps < -1.0
    assert sc.percentile_drift == 0.0
    assert assess([sc])["verdict"] == "PARTIAL"


def test_no_held_evidence_is_never_ok() -> None:
    # L1.28a: an empty input is louder than a healthy desk, never quieter.
    assert assess([])["verdict"] == "NO-HELD-EVIDENCE"


def test_immaterial_drift_does_not_alarm_however_significant() -> None:
    """A statistically clean move inside one round trip's noise is not actionable."""
    n = 40
    rates, universes = [], []
    for i in range(n):
        universes.append(_universe(0.0010))
        rates.append(0.0012 - i * 1e-7)     # a real but tiny slope: << MATERIAL_BPS overall
    sc = symbol_crowding("TINY", rates, universes)
    assert sc is not None
    assert abs(sc.residual_drift_bps) < 1.0
    assert assess([sc])["verdict"] in ("OK", "PARTIAL")


# ---------------------------------------------------------------------------------------------
# Fence-level behaviour: the statuses that must stay DISTINCT from OK.
# ---------------------------------------------------------------------------------------------

@pytest.fixture()
def fence():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_crowding", Path(__file__).resolve().parents[2] / "scripts/check_crowding.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flat_book_is_not_ok(fence) -> None:
    """A paused sleeve must not read as a healthy one for as long as the pause lasts."""
    tape = [{"t": 1_000 + i, "rates": {"AAAUSDT": 0.001}, "n": 1} for i in range(MIN_SNAPSHOTS)]
    rep = fence.build_report(tape=tape, held={})
    assert rep["status"] == "FLAT-BOOK"
    assert rep["status"] != "OK"


def test_absent_tape_is_not_ok(fence) -> None:
    rep = fence.build_report(tape=[], held={})
    assert rep["status"] == "NO-TAPE"
    assert any("NO-TAPE" in b for b in rep["breaches"])


def test_held_name_below_snapshot_floor_reads_unmeasured(fence) -> None:
    tape = [{"t": 1_000 + i, "rates": {"AAAUSDT": 0.001}, "n": 1} for i in range(MIN_SNAPSHOTS)]
    held = {"AAAUSDT": {"opened": "2099-01-01T00:00:00+00:00"}}   # opened after every snapshot
    rep = fence.build_report(tape=tape, held=held)
    assert rep["status"] == "UNMEASURED"
    assert "AAAUSDT" in rep["accruing"]


def test_the_live_tape_row_is_shaped_as_the_fence_expects(fence) -> None:
    """Guards the producer/consumer seam: the collector's row must parse here."""
    p = Path(__file__).resolve().parents[2] / "data/funding_cross_section.jsonl"
    if not p.exists():
        pytest.skip("collector has not run on this box")
    first = json.loads(p.read_text("utf-8").splitlines()[0])
    assert isinstance(first["rates"], dict) and first["t"] and first["n"] >= 200
    assert first["c"] in ("venue", "recv_only")     # L1.46: the clock is declared
    assert fence._load_tape(p)                      # the fence accepts what the collector writes
