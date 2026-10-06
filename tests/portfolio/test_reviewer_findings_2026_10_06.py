"""ACCEPTANCE TESTS OWED: the principal's external reviewer, 2026-10-06 (portfolio library half).

Each finding carries two tests:

  * a PLAIN test that pins the reproduction at LIVE 2d61e69a1 -- the defect exists today, with the
    numbers measured on the real functions (never a re-implementation);
  * a STRICT XFAIL acceptance test that asserts the CORRECT behaviour. CI stays green while the
    defect stands; the day a builder fixes it the acceptance test XPASSes, strict turns that into a
    failure, and the fixer must delete the marker AND the now-false reproduction pin in the same
    change. That is the point: the fix cannot land silently.

Owner of every finding in this file: the "Growth allocator overhaul" thread (desktop).
The desk-side half (allocator_trigger, fast-path cache, heat_policy, forecast_contract,
acquire_datasets, source_evig) lives in desks/mt5/tests/test_reviewer_findings_2026_10_06.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from libs.portfolio import robust_elog as re_
from libs.portfolio.models import PortfolioConstraints
from libs.portfolio.multiperiod import MultiPeriodOptimizer
from libs.portfolio.robust_elog import (
    SleeveEvidence,
    WorldConfig,
    Worlds,
    decay_prob_of,
    optimise,
    sample_worlds,
    score_book,
)
from libs.research import perishability

OWNER = "owner: Growth allocator overhaul (desktop)"

# ============================================================== finding 1: concavity claim is false
#
# robust_elog.py:1099-1101 claims "concave in h ... minus a positive-semidefinite quadratic", and
# the solver is projected gradient ascent with no certificate (robust_elog.py:1150-1176). The
# redundancy charge `_redundancy` (robust_elog.py:846-855) is h'|C|h - h'h = h'(|C|-I)h, and
# |C|-I has a zero diagonal, so it is INDEFINITE whenever any off-diagonal is non-zero: for two
# identical sleeves |C|-I = [[0,1],[1,0]], eigenvalues -1 and +1. Charging it with a minus sign
# makes the objective CONVEX along h1-h2 at fixed total, so the symmetric point is a MINIMUM on
# the feasible segment and the ascent "converges" exactly there.


def _twin_book() -> tuple[list[SleeveEvidence], WorldConfig, Worlds]:
    """Two IDENTICAL sleeves on IDENTICAL worlds.

    `sample_worlds` draws an independent posterior mean per sleeve, which breaks the symmetry by
    luck; to measure the objective's SHAPE the second sleeve's world columns are a byte copy of
    the first's, drawn by the module's own `sample_worlds`. Every score below comes from the real
    `optimise` / `score_book` / `_objective`.
    """
    r = np.tile([0.01, -0.005], 150)
    ev = [SleeveEvidence("a", r.copy()), SleeveEvidence("b", r.copy())]
    cfg = WorldConfig(n_worlds=32, n_rows=64, seed=0)
    one = sample_worlds(ev[:1], cfg)
    worlds = Worlds(r=np.concatenate([one.r, one.r], axis=2), names=("a", "b"),
                    crisis=one.crisis,
                    mu_draws=np.concatenate([one.mu_draws, one.mu_draws], axis=1))
    return ev, cfg, worlds


def test_reproduction_twin_sleeves_converge_at_a_beaten_point() -> None:
    """REPRODUCED at 2d61e69a1: cold start returns 0.10/0.10 with converged=True, objective
    -0.002724057723898416; the feasible 0.15/0.05 (same total 0.20, same 0.15 per-sleeve cap)
    scores -0.001974057731828799 -- higher is better, so the "converged" book is beaten by 0.00075,
    which is exactly redundancy_lambda (0.15) x 2 x (0.10*0.10 - 0.15*0.05).

    The reviewer's own figures (-0.002250804 vs -0.001500804) came from an unstated stream; the
    gap is the same 0.00075 because the gap is the redundancy term alone.
    """
    ev, cfg, worlds = _twin_book()
    res = optimise(ev, hard_cap=0.20, target=0.20, max_per_sleeve=0.15, cfg=cfg, worlds=worlds)
    assert res.heat == pytest.approx({"a": 0.10, "b": 0.10}, abs=1e-12)
    assert res.converged is True
    assert res.robust_score == pytest.approx(-0.002724057723898416, abs=1e-12)
    better = score_book(ev, {"a": 0.15, "b": 0.05}, cfg=cfg, worlds=worlds)["robust_score"]
    assert better == pytest.approx(-0.001974057731828799, abs=1e-12)
    assert better - res.robust_score == pytest.approx(0.00075, abs=1e-9)
    # The non-PSD charge itself, on the module's own |C|.
    c = re_._corr_abs(ev)
    eig = np.linalg.eigvalsh(c - np.eye(2))
    assert eig.min() == pytest.approx(-1.0) and eig.max() == pytest.approx(1.0)


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: robust_elog objective is not concave -- redundancy "
    "h'(|C|-I)h is indefinite (libs/portfolio/robust_elog.py:846-855, claim at :1099-1101); "
    "optimise returns converged=True at 0.10/0.10 while feasible 0.15/0.05 scores higher. "
    + OWNER))
def test_acceptance_solver_never_certifies_a_beaten_point() -> None:
    """Either restore concavity (e.g. a PSD redundancy charge) or certify the solution under
    non-convexity (multi-start, vertex check, or converged=False). What is not acceptable is
    converged=True at a point a feasible book beats on the solver's OWN objective."""
    ev, cfg, worlds = _twin_book()
    res = optimise(ev, hard_cap=0.20, target=0.20, max_per_sleeve=0.15, cfg=cfg, worlds=worlds)
    rival = score_book(ev, {"a": 0.15, "b": 0.05}, cfg=cfg, worlds=worlds)["robust_score"]
    assert not (res.converged and rival > res.robust_score + 1e-12), (
        f"converged=True at {res.heat} ({res.robust_score!r}) but 0.15/0.05 scores {rival!r}")


# ============================================================ finding 4: multiperiod ignores cost
#
# multiperiod.py:63-77 interpolates toward the supplied target with a turnover cap and adds
# `moved * cost_per_turnover` to total_cost AFTERWARDS (multiperiod.py:73). Nothing in the path
# reads the cost, so it is a glide path with a cost REPORT, not a cost-aware optimisation.

_UNCAPPED = PortfolioConstraints(max_weight=1.0)


def _plan(cost: float) -> object:
    return MultiPeriodOptimizer(constraints=_UNCAPPED, cost_per_turnover=cost,
                                max_step_turnover=0.20).plan(
        current={"a": 0.5, "b": 0.5}, target={"a": 0.1, "b": 0.9}, n_steps=5)


def test_reproduction_multiperiod_cost_changes_only_the_report() -> None:
    """REPRODUCED at 2d61e69a1: cost_per_turnover 0.0 / 0.0005 / 0.5 / 5.0 give the IDENTICAL
    path (a: 0.5 -> 0.3 -> 0.1, turnover 0.2 then 0.2); only total_cost moves (0 .. 2.0)."""
    plans = {c: _plan(c) for c in (0.0, 0.0005, 0.5, 5.0)}
    paths = {c: p.path for c, p in plans.items()}  # type: ignore[attr-defined]
    first = paths[0.0]
    assert all(p == first for p in paths.values())
    assert [round(s["a"], 12) for s in first] == [0.3, 0.1]
    costs = [plans[c].total_cost for c in (0.0, 0.0005, 0.5, 5.0)]  # type: ignore[attr-defined]
    assert costs == pytest.approx([0.0, 0.0002, 0.2, 2.0])


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: multiperiod path is cost-blind -- cost is summed after the "
    "glide (libs/portfolio/multiperiod.py:63-77, cost at :73). " + OWNER))
def test_acceptance_multiperiod_cost_changes_the_chosen_path() -> None:
    """A genuine multi-period optimiser trades tracking error against turnover cost: at a
    prohibitive cost it must trade LESS (end farther from the target) than at zero cost."""
    free, dear = _plan(0.0), _plan(5.0)
    assert free.path != dear.path  # type: ignore[attr-defined]
    moved_free = sum(free.step_turnover)  # type: ignore[attr-defined]
    moved_dear = sum(dear.step_turnover)  # type: ignore[attr-defined]
    assert moved_dear < moved_free


# ================================================== finding 5: decay channel is relief-only (min)
#
# robust_elog.decay_prob_of (robust_elog.py:614-631) returns min(v, blanket) with the blanket
# WorldConfig.decay_prob = 0.30 (robust_elog.py:218). A sleeve whose measured hazard is 0.90 is
# charged 0.30. tests/portfolio/test_robust_elog_per_sleeve.py:59 PINS that. The hazard scale is
# perishability.HAZARD_SCALE_DAYS = 120.0 (perishability.py:413), "DECLARED, not fitted"
# (perishability.py:73), so a two-sided channel is owed TOGETHER with a calibration artifact.


def test_reproduction_decay_hazard_cannot_exceed_the_blanket() -> None:
    """REPRODUCED at 2d61e69a1: decay_prob_i=0.90 -> 0.30; 0.05 -> 0.05 (relief only)."""
    cfg = WorldConfig()
    assert cfg.decay_prob == 0.30
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.90), cfg) == 0.30
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.05), cfg) == 0.05
    assert perishability.HAZARD_SCALE_DAYS == 120.0
    src = Path(perishability.__file__).read_text(encoding="utf-8")
    assert "The scale is DECLARED, not fitted" in src


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: decay_prob_of returns min(v, 0.30) so a deteriorating "
    "sleeve's hazard is never charged (libs/portfolio/robust_elog.py:614-631); the pin at "
    "tests/portfolio/test_robust_elog_per_sleeve.py:59 must be retired with the fix. " + OWNER))
def test_acceptance_decay_channel_is_two_sided() -> None:
    """A measured, calibrated hazard above the blanket must raise the charged decay."""
    cfg = WorldConfig()
    assert decay_prob_of(SleeveEvidence("x", np.zeros(3), decay_prob_i=0.90), cfg) > 0.30


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: the 120-day hazard scale is declared, not fitted "
    "(libs/research/perishability.py:71-73, :413); a two-sided decay channel needs a "
    "calibration artifact. " + OWNER))
def test_acceptance_hazard_scale_has_a_calibration_artifact() -> None:
    """Contract (rename freely, keep the substance): `perishability.HAZARD_SCALE_ARTIFACT` names
    a committed JSON whose `basis` is "fitted", whose `scale_days` is the constant in use, and
    whose `n_edges` says how many retired/decayed edges the fit stands on."""
    path = Path(getattr(perishability, "HAZARD_SCALE_ARTIFACT", ""))
    assert path.is_file(), f"no calibration artifact at {path!s}"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc.get("basis") == "fitted"
    assert float(doc["scale_days"]) == pytest.approx(perishability.HAZARD_SCALE_DAYS)
    assert int(doc.get("n_edges", 0)) > 0
