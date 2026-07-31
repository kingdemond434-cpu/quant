"""R0206 attribution instrument -- the parts that decide whether its verdict can be trusted.

These are not "does it run" tests. Each pins one property that, if it broke, would let the
instrument print a CONFIDENT WRONG ANSWER about the only sleeve this desk deploys:

  1. SIGN CONVENTION. ``basis_leg_bps = -1e4 * dbasis`` must match the desk's own carry
     accounting (libs/research/cashcarry.py: ``basis_pnl = -(w * dbasis)``). Flip this and a
     widening basis reads as profit -- the exact error that would have "confirmed" BR-08.
  2. NO LOOK-AHEAD IN THE FUNDING LEG. The harvest must sum funding strictly AFTER entry. If it
     included the ranking bar's own funding, the top-funding bucket would book the very number
     it was selected on, manufacturing a huge fake harvest.
  3. THE REFUSAL PATH IS REAL (L1.41 condition 1). Thin evidence must return UNMEASURED, never a
     verdict. An organ with no vocabulary for "I could not measure" reports OK on absent input.
  4. EVERY DECLARED TRIAL IS REPORTED. Silently dropping a cell is how a 4-cell sweep becomes a
     1-cell result and the multiplicity count becomes a lie.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "screen_carry_basis_path", ROOT / "scripts/screen_carry_basis_path.py")
sc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sc)


def _panel(n_days: int, n_syms: int, *, basis_drift: float, funding: float):
    """Synthetic panel with a KNOWN answer: every symbol's basis drifts by ``basis_drift``/day."""
    idx = pd.date_range("2020-01-01", periods=n_days, freq="D", tz="UTC")
    cols = [f"S{i}USDT" for i in range(n_syms)]
    f = pd.DataFrame(funding, index=idx, columns=cols)
    # Break ranking ties deterministically WITHOUT perturbing the harvest: at 1e-8 the spread is
    # 1e-4 bps, far below any tolerance here. (An earlier 1e-4 spread put ~0.95 bps of the
    # tie-breaker into the top-4 bucket and made the harvest assertion fail on the fixture,
    # not on the code -- kept as a note because it is the same "selection leaks into the
    # measurement" shape the instrument itself is testing for.)
    f = f + np.linspace(0, 1e-8, n_syms)[None, :]
    drift = np.tile(np.arange(n_days, dtype=float)[:, None] * basis_drift, (1, n_syms))
    b = pd.DataFrame(drift, index=idx, columns=cols)
    return f, b


def test_widening_basis_is_a_LOSS_on_the_short_perp_leg():
    """A basis that widens by +10 bps/day must print basis_leg_bps ~ -10, not +10."""
    f, b = _panel(400, 30, basis_drift=+0.0010, funding=0.0)
    cell = sc._cell(f, b, construction="literal", h=1)
    assert cell["verdict"] != "UNMEASURED"
    assert cell["basis_leg_bps"] == pytest.approx(-10.0, abs=0.5), (
        "sign convention broken: a WIDENING basis must lose money on the short-perp leg "
        "(desk convention, libs/research/cashcarry.py: basis_pnl = -(w * dbasis))")
    assert cell["verdict"] == "CONFIRMED-WIDENING"


def test_converging_basis_is_a_GAIN_and_reads_as_refuted():
    f, b = _panel(400, 30, basis_drift=-0.0010, funding=0.0)
    cell = sc._cell(f, b, construction="literal", h=1)
    assert cell["basis_leg_bps"] == pytest.approx(+10.0, abs=0.5)
    assert cell["verdict"] == "REFUTED-CONVERGING"


def test_funding_harvest_excludes_the_ranking_bar():
    """h=1 must harvest exactly ONE funding period -- the one AFTER entry, never the ranking bar.

    If the ranking bar leaked in, the harvest would be ~2x and the top bucket would be booking
    the number it was selected on.
    """
    f, b = _panel(400, 30, basis_drift=0.0, funding=0.0010)   # 10 bps per day, flat basis
    cell = sc._cell(f, b, construction="literal", h=1)
    assert cell["funding_leg_bps"] == pytest.approx(10.0, abs=0.6), (
        "funding harvest must cover exactly the HOLD (h periods strictly after entry); "
        f"got {cell['funding_leg_bps']} for h=1 at 10 bps/period")
    cell5 = sc._cell(f, b, construction="literal", h=5)
    assert cell5["funding_leg_bps"] == pytest.approx(50.0, abs=3.0)


def test_thin_evidence_REFUSES_rather_than_reporting_a_verdict():
    """L1.41 condition 1: the refusal path must exist and must fire."""
    f, b = _panel(12, 30, basis_drift=+0.0010, funding=0.0)   # far below MIN_BLOCKS
    cell = sc._cell(f, b, construction="literal", h=1)
    assert cell["verdict"] == "UNMEASURED", "thin evidence must not produce a verdict"
    assert "reason" in cell and str(sc.MIN_BLOCKS) in cell["reason"]
    for k in ("basis_leg_bps", "net_bps"):
        assert k not in cell, (
            f"UNMEASURED cell must not publish {k} -- a number with no evidence behind it")


def test_too_narrow_a_cross_section_is_also_refused():
    """Fewer than MIN_XSEC names on a date cannot support a cross-sectional rank."""
    f, b = _panel(400, 5, basis_drift=+0.0010, funding=0.0)   # 5 < MIN_XSEC
    cell = sc._cell(f, b, construction="literal", h=1)
    assert cell["verdict"] == "UNMEASURED"
    assert cell["n_blocks"] == 0


def test_every_declared_trial_is_reported():
    """The sweep must report CONSTRUCTIONS x HORIZONS cells -- dropping one falsifies the count."""
    assert len(sc.CONSTRUCTIONS) * len(sc.HORIZONS) == sc.N_TRIALS
    f, b = _panel(400, 30, basis_drift=+0.0005, funding=0.0002)
    cells = [sc._cell(f, b, construction=c, h=h)
             for c in sc.CONSTRUCTIONS for h in sc.HORIZONS]
    assert len(cells) == sc.N_TRIALS
    seen = {(c["construction"], c["horizon_d"]) for c in cells}
    assert seen == {(c, h) for c in sc.CONSTRUCTIONS for h in sc.HORIZONS}


def test_lag1_entry_uses_a_later_bar_than_literal():
    """The noise-robust construction must actually shift the entry, or it controls nothing.

    A CONSTANT drift cannot detect this -- both constructions measure the same slope -- and a
    one-off spike cancels out across blocks. So the fixture uses an ACCELERATING basis
    (b = c*t^2): literal measures c*(2t+1) per step, lag1 measures c*(2t+3), a mean gap of
    exactly 2c*1e4 bps. That gap is zero if and only if the entry offset is not applied.
    """
    c = 1e-7
    f, _ = _panel(400, 30, basis_drift=0.0, funding=0.0)
    quad = np.tile((np.arange(400, dtype=float) ** 2 * c)[:, None], (1, 30))
    b = pd.DataFrame(quad, index=f.index, columns=f.columns)
    lit = sc._cell(f, b, construction="literal", h=1)
    lag = sc._cell(f, b, construction="lag1", h=1)
    assert lit["basis_leg_bps"] - lag["basis_leg_bps"] == pytest.approx(2 * c * 1e4, abs=1e-3), (
        "lag1 did not shift the entry bar by exactly one period relative to literal "
        f"(literal {lit['basis_leg_bps']}, lag1 {lag['basis_leg_bps']})")
