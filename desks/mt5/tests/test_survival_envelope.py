"""The bar that replaced the 30% constant, and the four ways it must refuse to be one.

    "remove 30 heat cap fully so if growth optimum says 35-40 that's allowed aswell until it
     computes something diff the next few moments later minutes wtv it was"
                                                            -- the principal, 2026-09-07

WHAT THE CHANGE ACTUALLY IS, because "remove the cap" is the one description of it that would be
dangerous if taken literally. `HEAT_HARD_CEILING = 0.30` was a MEASUREMENT of one book on one
date -- robust growth positive at 20% and 25%, negative at 30% -- frozen into a permanent law.
Freezing it makes the desk poorer as soon as the opportunity set improves, and does nothing at
all about a book that cannot survive 22%. So it is replaced by two bars the allocator MEASURES
every pass:

    growth ceiling      `heat_policy.measured_ceiling` -- where the curve stops paying
    survival ceiling    `kelly_surface.envelope`       -- where the account dies

and the constant survives ONLY as what holds when neither can be read.

THE ASYMMETRY IS THE ARGUMENT. A broad book with a measured curve earns more than 30%. A thin
book that ruins at 22% is now held at 21%, where the constant would have waved it through to 30%.
Half these tests exist to pin the second direction, because it is the one nobody checks.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.decision_core import (  # noqa: E402
    ABSOLUTE_SIM_MAX,
    MAX_HEAT_CEILING,
    live_heat_ceiling,
)
from libs.portfolio.kelly_surface import (  # noqa: E402
    MAX_MARGIN_USE,
    MEASURED,
    MIN_ENVELOPE_ROWS,
    UNMEASURED,
    envelope,
)

ALPHA = 0.20


def _rows(*spec: tuple[float, float, float]) -> list[dict[str, float]]:
    """(heat, p_ruin, p_dd_over_tolerance) triples as surface rows."""
    return [{"heat": h, "p_ruin": r, "p_dd_over_tolerance": d} for h, r, d in spec]


HEALTHY = _rows((0.10, 0.0, 0.04), (0.20, 0.0, 0.09), (0.30, 0.0, 0.15),
                (0.40, 0.0, 0.19), (0.45, 0.02, 0.41))


# ------------------------------------------------------------------ it can exceed the constant
def test_a_book_that_survives_forty_percent_is_bounded_at_forty_percent() -> None:
    e = envelope(HEALTHY, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["status"] == MEASURED
    assert e["ceiling"] == pytest.approx(0.40)
    assert e["ceiling"] > MAX_HEAT_CEILING, "the recorded constant no longer bounds a measurement"
    assert "p_ruin" in e["stopped_by"]


def test_the_ceiling_never_runs_past_the_last_sampled_heat() -> None:
    """A heat nobody simulated is a heat nobody certified.

    This is what separates removing an arbitrary bound from removing the bound. The envelope
    grows by MEASURING further out, never by asserting further out, and when the highest sampled
    heat is still feasible it says so in as many words so somebody widens the sweep.
    """
    still_climbing = _rows((0.10, 0.0, 0.04), (0.20, 0.0, 0.08), (0.30, 0.0, 0.12))
    e = envelope(still_climbing, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["ceiling"] == pytest.approx(0.30)
    assert e["binding"] == "measurement_edge"
    assert "edge of the measurement" in e["why"]


# ------------------------------------------------------------------ it binds BELOW the constant
def test_a_book_that_ruins_at_twenty_two_percent_is_held_at_fifteen() -> None:
    thin = _rows((0.10, 0.0, 0.05), (0.15, 0.0, 0.11), (0.22, 0.01, 0.30), (0.30, 0.05, 0.52))
    e = envelope(thin, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["status"] == MEASURED
    assert e["ceiling"] == pytest.approx(0.15)
    assert e["ceiling"] < MAX_HEAT_CEILING, (
        "the constant would have waved this book through to 30%")


def test_the_drawdown_tolerance_binds_on_its_own() -> None:
    """Ruin is not the only way to lose the account. The principal's 35% tolerance is a
    constraint in its own right, and it bites long before any world reaches zero."""
    dd_bound = _rows((0.10, 0.0, 0.05), (0.20, 0.0, 0.14), (0.30, 0.0, 0.31), (0.40, 0.0, 0.44))
    e = envelope(dd_bound, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["ceiling"] == pytest.approx(0.20)
    assert e["stopped_by"] == ["p_dd_over_tolerance"]


def test_margin_use_binds_when_the_box_has_measured_it() -> None:
    mu = {0.10: 0.11, 0.20: 0.24, 0.30: 0.38, 0.40: 0.71}
    e = envelope(HEALTHY[:4], alpha=ALPHA, fallback=MAX_HEAT_CEILING, margin_use=mu)
    assert e["ceiling"] == pytest.approx(0.30)
    assert e["stopped_by"] == ["margin_use"]
    assert e["max_margin_use"] == pytest.approx(MAX_MARGIN_USE)


def test_an_unmeasured_margin_carries_no_clause_at_all() -> None:
    """An unmeasured constraint is not a satisfied constraint and it is not a violated one.

    The desk has no margin reading on this host, so the clause is simply absent -- which is the
    honest treatment and the one that does not quietly license heat by pretending margin is fine.
    """
    e = envelope(HEALTHY, alpha=ALPHA, fallback=MAX_HEAT_CEILING, margin_use=None)
    assert e["ceiling"] == pytest.approx(0.40)
    assert "margin" not in e["why"]


def test_capacity_binds_when_it_is_measured() -> None:
    e = envelope(HEALTHY, alpha=ALPHA, fallback=MAX_HEAT_CEILING, capacity_max=0.22)
    assert e["ceiling"] == pytest.approx(0.20)
    assert e["stopped_by"] == ["capacity"]


# ------------------------------------------------------------------------ absence is never permission
def test_a_surface_too_thin_to_read_returns_the_recorded_constant() -> None:
    for rows in ([], _rows((0.1, 0.0, 0.0)), _rows((0.1, 0.0, 0.0), (0.2, 0.0, 0.0))):
        e = envelope(rows, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
        assert e["status"] == UNMEASURED
        assert e["ceiling"] == pytest.approx(MAX_HEAT_CEILING)
        assert e["binding"] == "fallback"
    assert MIN_ENVELOPE_ROWS == 3


def test_a_surface_that_refuses_its_own_smallest_book_is_a_defect_not_a_licence() -> None:
    """If the lowest sampled heat already ruins, the surface has not measured a bound -- it has
    failed. Reading "nothing is feasible" as "zero heat" would stop the desk on a bad sample;
    reading it as permission would be worse. It falls back and says which clause broke."""
    broken = _rows((0.10, 0.4, 0.9), (0.20, 0.6, 0.95), (0.30, 0.8, 0.99))
    e = envelope(broken, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["status"] == UNMEASURED
    assert e["ceiling"] == pytest.approx(MAX_HEAT_CEILING)
    assert "p_ruin" in e["failed_at_lowest"]


def test_non_finite_and_zero_heats_are_dropped_before_anything_is_read() -> None:
    dirty = [{"heat": float("nan"), "p_ruin": 0.0, "p_dd_over_tolerance": 0.0},
             {"heat": 0.0, "p_ruin": 0.0, "p_dd_over_tolerance": 0.0},
             {"heat": "x", "p_ruin": 0.0, "p_dd_over_tolerance": 0.0},
             *HEALTHY]
    e = envelope(dirty, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["ceiling"] == pytest.approx(0.40)
    assert e["n_rows"] == len(HEALTHY)


def test_a_missing_survival_field_is_infeasible_not_ignored() -> None:
    """A row with no p_ruin has not proved P(ruin) = 0; it has proved nothing."""
    partial = [{"heat": 0.10, "p_ruin": 0.0, "p_dd_over_tolerance": 0.05},
               {"heat": 0.20, "p_dd_over_tolerance": 0.09},
               {"heat": 0.30, "p_ruin": 0.0, "p_dd_over_tolerance": 0.12}]
    e = envelope(partial, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["ceiling"] == pytest.approx(0.10)


def test_feasibility_must_be_contiguous_from_the_bottom() -> None:
    """A gap in the middle means the sampler resolved something badly. Taking the far side of it
    would size across a region the surface says is lethal, on the strength of a reading beyond
    it -- so the ceiling is the top of the UNBROKEN feasible run, never the highest good row."""
    gapped = _rows((0.10, 0.0, 0.04), (0.20, 0.3, 0.60), (0.30, 0.0, 0.05), (0.40, 0.0, 0.06))
    e = envelope(gapped, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    assert e["ceiling"] == pytest.approx(0.10)


# ------------------------------------------------------------------------------ the money path
def test_the_gateway_falls_back_to_the_constant_without_an_envelope() -> None:
    for heat in ({}, {"envelope": None}, {"envelope": {}},
                 {"envelope": {"survival": {"status": UNMEASURED, "why": "thin"}}},
                 {"envelope": {"survival": {"status": MEASURED}, "operative_ceiling": None}},
                 {"envelope": {"survival": {"status": MEASURED}, "operative_ceiling": -1.0}},
                 {"envelope": {"survival": {"status": MEASURED},
                               "operative_ceiling": float("inf")}}):
        cap, why = live_heat_ceiling(heat)
        assert cap == pytest.approx(MAX_HEAT_CEILING), (heat, why)


def test_the_gateway_honours_a_measured_envelope_above_the_constant() -> None:
    cap, why = live_heat_ceiling({"envelope": {"survival": {"status": MEASURED},
                                               "operative_ceiling": 0.38}})
    assert cap == pytest.approx(0.38)
    assert cap > MAX_HEAT_CEILING
    assert "measured envelope" in why


def test_the_gateway_honours_a_measured_envelope_below_the_constant() -> None:
    cap, why = live_heat_ceiling({"envelope": {"survival": {"status": MEASURED,
                                                            "why": "ruin at 22%"},
                                               "operative_ceiling": 0.21}})
    assert cap == pytest.approx(0.21)
    assert "BELOW" in why and "ruin at 22%" in why


def test_the_gateway_never_deploys_a_heat_nobody_sampled() -> None:
    cap, _ = live_heat_ceiling({"envelope": {"survival": {"status": MEASURED},
                                             "operative_ceiling": 0.95}})
    assert cap == pytest.approx(ABSOLUTE_SIM_MAX)
    assert ABSOLUTE_SIM_MAX == 0.45, "must equal pf_allocator.CURVE_SAMPLE_MAX"


def test_the_simulation_bound_matches_the_allocators_sampling_bound() -> None:
    """Two numbers that must be one number. `decision_core` may not deploy past where
    `pf_allocator` samples, and restating the constant is the only way the money path can avoid
    importing the research package -- so a test holds them equal instead of an import."""
    from research.pf_allocator import CURVE_SAMPLE_MAX
    assert ABSOLUTE_SIM_MAX == pytest.approx(CURVE_SAMPLE_MAX)


# ------------------------------------------------------------------------------- the derivative
def test_the_growth_derivative_is_signed_correctly_around_a_peak() -> None:
    """dE[logW]/dH is the number the whole law turns on: keep adding risk while it is positive,
    stop where it is zero. A surface that reports the wrong sign at the peak would size straight
    past it."""
    from libs.portfolio.kelly_surface import _derivatives
    rows = [{"heat": h, "mean_growth": g} for h, g in
            [(0.10, 0.0010), (0.20, 0.0018), (0.30, 0.0020), (0.40, 0.0012), (0.50, -0.0005)]]
    _derivatives(rows)
    assert rows[1]["dG_dH"] > 0, "still climbing below the peak"
    assert rows[3]["dG_dH"] < 0, "falling above it"
    # concave through the peak
    assert rows[2]["d2G_dH2"] is not None and rows[2]["d2G_dH2"] < 0


def test_a_non_finite_growth_gives_no_derivative_rather_than_a_fabricated_one() -> None:
    from libs.portfolio.kelly_surface import _derivatives
    rows = [{"heat": 0.1, "mean_growth": 0.001},
            {"heat": 0.2, "mean_growth": 0.002},
            {"heat": 0.3, "mean_growth": -math.inf}]
    _derivatives(rows)
    assert rows[1]["dG_dH"] is None, "a ruined world set has no slope"
    assert rows[1]["d2G_dH2"] is None


# ------------------------------------------------- the join: what the allocator writes is what
#                                                    the gateway reads
def test_the_artifact_block_the_allocator_writes_is_the_one_the_gateway_reads() -> None:
    """The chain end to end, in the shapes the two sides actually use.

    THIS IS THE TEST THAT WOULD HAVE CAUGHT THREE DEFECTS THIS WEEK. Every link here is unit
    tested above and the links are in different packages -- `libs.portfolio` measures, the desk's
    research organ writes JSON, `mt5desk.decision_core` reads it -- so a key renamed on one side
    passes every test on both. Building the block exactly as `pf_allocator.run` builds it and
    feeding it to `live_heat_ceiling` is the only assertion that fails when they drift.
    """
    from research.heat_policy import resolve
    from research.pf_allocator import CURVE_SAMPLE_MAX

    surv = envelope(HEALTHY, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    ceiling_now = 0.42                      # what `measured_ceiling` read off the growth curve
    verdict = resolve(0.38, curve={0.1: 0.001, 0.2: 0.002, 0.3: 0.0025, 0.4: 0.0026},
                      hard_ceiling=ceiling_now,
                      survival_ceiling=surv["ceiling"], survival_why=surv["why"])
    # the literal block from pf_allocator.run
    heat_block = {
        "total": round(verdict.total_heat, 6),
        "envelope": {
            "growth_ceiling": round(float(ceiling_now), 6),
            "survival_ceiling": round(float(surv["ceiling"]), 6),
            "survival": surv,
            "operative_ceiling": round(min(float(ceiling_now), float(surv["ceiling"])), 6),
            "sample_max": CURVE_SAMPLE_MAX,
            "unmeasured_fallback": MAX_HEAT_CEILING,
        },
    }
    cap, why = live_heat_ceiling(heat_block)
    assert cap == pytest.approx(0.40), why
    assert heat_block["total"] <= cap + 1e-12, "the gateway would refuse the book it was handed"
    assert cap > MAX_HEAT_CEILING, "the constant no longer bounds a measured pass"


def test_a_pass_that_bound_on_survival_is_accepted_by_the_gateway_at_that_bar() -> None:
    """The tightening direction through the same join: the artifact says 15%, the gateway caps at
    15%, and a book at 29% -- which the old constant permitted -- is refused."""
    from research.heat_policy import resolve

    thin = _rows((0.10, 0.0, 0.05), (0.15, 0.0, 0.11), (0.22, 0.01, 0.30), (0.30, 0.05, 0.52))
    surv = envelope(thin, alpha=ALPHA, fallback=MAX_HEAT_CEILING)
    verdict = resolve(0.29, curve={0.1: 0.001, 0.2: 0.002, 0.3: 0.0021},
                      hard_ceiling=0.30, survival_ceiling=surv["ceiling"])
    assert verdict.binding == "survival_ceiling"
    assert verdict.total_heat == pytest.approx(0.15)
    cap, _ = live_heat_ceiling({"envelope": {"survival": surv, "operative_ceiling": 0.15}})
    assert cap == pytest.approx(0.15)
    assert not (0.0 < 0.29 <= cap + 1e-12), "29% must not survive the gateway's own check"
