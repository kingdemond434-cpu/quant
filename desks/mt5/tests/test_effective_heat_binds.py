"""Four sleeves that are one hidden USD factor must not buy the room four independent bets buy.

    python -m pytest desks/mt5/tests/test_effective_heat_binds.py -q

`libs/portfolio/latent_factors.effective` has computed four heats -- nominal, covariance, factor,
tail -- and an N_eff under each since the day it was written. `pf_allocator` called it AFTER the
solve and only REPORTED the answer, so the floor and the ceiling both counted NOMINAL heat and
H_eff = max(covariance, factor, tail) bound nothing at all. A book of XAU long, EURUSD short,
GBPUSD short and AUDUSD short read as 28% of heat under a 30% bar and was waved through, while
the risk it actually carried was one bet at 28%.

WHAT MUST NOT REGRESS:

  1. THE ASYMMETRY. The FLOOR counts nominal heat -- 20% deployed is a standing instruction about
     capital being at work -- and the CEILING counts effective heat, because hidden concentration
     bites at the top of the band and nowhere else.
  2. A concentrated book is HELD AT THE FLOOR, never taken below it: the answer to concentration
     is research that finds independent risk, not a smaller book.
  3. Genuinely independent risk still earns the full 30%.
  4. An unmeasured book keeps the nominal bar and SAYS SO (L1.28a): a broken measurement may not
     cost growth, and it may not pass silently either.
  5. The allocator HEARS the drift monitor: STRUCTURE_SHIFTED raises the crisis-world share,
     a stale report changes nothing, and neither ever lowers it.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.heat_policy import (  # noqa: E402
    EFFECTIVE_BREADTH_REF,
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    effective_ceiling,
    per_sleeve_bounds,
    resolve,
)

from libs.portfolio import rails  # noqa: E402
from libs.portfolio.latent_factors import (  # noqa: E402
    CRISIS_SHARE_MAX,
    crisis_share_from_drift,
    effective,
)
from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

_PF_SRC = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
#: A curve shaped like the measured one, so `certify` has something real to read.
GOOD = {0.05: 0.0010, 0.10: 0.0018, 0.15: 0.0023, 0.20: 0.0025, 0.25: 0.0025, 0.30: 0.0024}


def _one_factor(n: int = 4, days: int = 400, seed: int = 7) -> list[SleeveEvidence]:
    """`n` sleeves that are one latent factor wearing `n` names -- the hidden USD book."""
    rng = np.random.default_rng(seed)
    f = rng.normal(0.0, 0.01, days)
    return [SleeveEvidence(name=f"usd_{i}", daily_r=f + rng.normal(0.0, 0.001, days),
                           family=f"fam{i}") for i in range(n)]


def _independent(n: int = 8, days: int = 400, seed: int = 11) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    return [SleeveEvidence(name=f"ind_{i}", daily_r=rng.normal(0.001, 0.01, days),
                           family=f"fam{i}") for i in range(n)]


# ----------------------------------------------------------------- 1. the concentrated book
def test_four_sleeves_that_are_one_usd_factor_are_capped_by_factor_heat() -> None:
    """Nominal reads UNDER the ceiling and the book is capped anyway -- which is the whole point.

    28% nominal on four sleeves that share one factor is ~27% of single-bet-equivalent risk:
    N_eff barely above 1. Under the desk's own sqrt-breadth law that earns ~13%, and the clip at
    the floor is what turns it into 20%.
    """
    ev = _one_factor()
    book = {e.name: 0.07 for e in ev}                       # 28% nominal, inside the 30% bar
    eff = effective(ev, book)

    assert eff["nominal"] == pytest.approx(0.28)
    assert eff["nominal"] < HEAT_HARD_CEILING, "fixture: nominal must read UNDER the ceiling"
    assert eff["effective"] > 0.9 * eff["nominal"], (
        "fixture: these four sleeves must genuinely be one bet")
    assert min(eff["n_eff"].values()) < 1.5, f"fixture n_eff {eff['n_eff']}"

    cap, why, detail = effective_ceiling(eff)
    assert cap == pytest.approx(HEAT_TARGET), "a one-factor book earns no room above the floor"
    assert "EFFECTIVE-HEAT CEILING" in why and detail["n_eff"] < 1.5

    v = resolve(0.28, curve=GOOD, effective_heat=eff)
    assert v.binding == "effective_ceiling", v.reasons
    assert v.total_heat == pytest.approx(HEAT_TARGET)
    # AND THE FLOOR STILL DEPLOYS 20% NOMINAL. The cap took the upside, not the mandate.
    assert v.total_heat >= v.floor - 1e-12 and v.floor == pytest.approx(HEAT_TARGET)
    assert any("EFFECTIVE-HEAT CEILING BINDS" in r for r in v.reasons)


def test_the_floor_is_nominal_and_the_ceiling_is_effective() -> None:
    """THE ASYMMETRY, pinned. Concentration may take the room above 20% and may never take the
    20% itself: a book that cannot find independent risk is told to go and find some, not
    de-risked to 13% on a correlation estimate."""
    eff = effective(_one_factor(), {f"usd_{i}": 0.07 for i in range(4)})
    for free_optimum in (0.0, 0.05, 0.20, 0.28, 0.45):
        v = resolve(free_optimum, curve=GOOD, effective_heat=eff)
        assert v.total_heat == pytest.approx(HEAT_TARGET), (
            f"free {free_optimum}: a concentrated book runs the floor, no more and no less")
        assert v.total_heat >= HEAT_TARGET - 1e-12
    # mandate off is the only way below the floor, and even then the ceiling is the effective one
    v = resolve(0.28, curve=GOOD, effective_heat=eff, mandate=False)
    assert v.total_heat == pytest.approx(HEAT_TARGET) and v.binding == "effective_ceiling"


def test_independent_risk_still_earns_the_full_ceiling() -> None:
    """Rule 2 in one test: the cap is a concentration charge, not a general tightening."""
    ev = _independent()
    eff = effective(ev, {e.name: 0.28 / len(ev) for e in ev})
    cap, why, detail = effective_ceiling(eff)
    assert cap == pytest.approx(HEAT_HARD_CEILING), why
    assert detail["n_eff"] > EFFECTIVE_BREADTH_REF * (HEAT_HARD_CEILING / HEAT_TARGET) ** 2
    v = resolve(0.28, curve=GOOD, effective_heat=eff)
    assert v.total_heat == pytest.approx(0.28) and v.binding == "growth"
    assert resolve(0.45, curve=GOOD, effective_heat=eff).total_heat == pytest.approx(
        HEAT_HARD_CEILING)


def test_the_cap_moves_with_breadth_and_is_monotone_in_it() -> None:
    conc = effective_ceiling(effective(_one_factor(), {f"usd_{i}": 0.07 for i in range(4)}))[0]
    spread = effective_ceiling(effective(_independent(4, seed=13),
                                         {f"ind_{i}": 0.07 for i in range(4)}))[0]
    wide = effective_ceiling(effective(_independent(8), {f"ind_{i}": 0.035 for i in range(8)}))[0]
    assert conc < spread < wide, f"{conc:.4f} {spread:.4f} {wide:.4f}"
    assert conc == pytest.approx(HEAT_TARGET) and wide == pytest.approx(HEAT_HARD_CEILING)


# ----------------------------------------------------------------- 2. the worst leg binds
def test_the_worst_of_the_three_heats_is_the_one_that_binds() -> None:
    """Covariance says what the sleeves did on average, factor what they are exposed to
    underneath, tail what they do on the book's worst days. The ceiling answers to the worst of
    the three, because that is the day it exists for."""
    base = {"nominal": 0.28, "covariance": 0.10, "factor": 0.12}
    loose = effective_ceiling({**base, "tail": 0.05})[0]
    tight, why, detail = effective_ceiling({**base, "tail": 0.27})
    assert "tail binds" in why and detail["effective"] == pytest.approx(0.27)
    assert tight < loose


def test_effective_heat_can_never_exceed_nominal_so_the_cap_is_never_a_bonus() -> None:
    """A malformed report claiming 5% effective on 28% nominal must not buy a 60% ceiling."""
    cap, _why, _d = effective_ceiling({"nominal": 0.28, "covariance": 0.001, "factor": 0.001,
                                       "tail": 0.001})
    assert cap == pytest.approx(HEAT_HARD_CEILING), "the hard bar is still the hard bar"


# ----------------------------------------------------------------- 3. absence is never health
@pytest.mark.parametrize("doc", [
    None, {}, {"error": "ValueError: boom"}, {"nominal": 0.0, "covariance": 0.0},
    {"nominal": float("nan"), "covariance": 0.1}, {"nominal": 0.2},
    {"nominal": 0.2, "covariance": None, "factor": "x", "tail": float("inf")},
])
def test_an_unmeasured_book_keeps_the_nominal_bar_and_says_so(doc) -> None:
    """L1.28a cuts both ways: a broken measurement may not quietly cost growth, and it may not
    pass unremarked either. The ceiling stands where it stood and the reason names the gap."""
    cap, why, detail = effective_ceiling(doc)
    assert cap == pytest.approx(HEAT_HARD_CEILING)
    assert "UNMEASURED" in why and detail == {}
    v = resolve(0.24, curve=GOOD, effective_heat=doc)
    assert v.total_heat == pytest.approx(0.24), "an unmeasured book is sized as it was before"
    assert any("UNMEASURED" in r for r in v.reasons)


def test_omitting_effective_heat_leaves_every_existing_caller_unchanged() -> None:
    for free_optimum, expect in ((0.08, HEAT_TARGET), (0.23, 0.23), (0.45, HEAT_HARD_CEILING)):
        assert resolve(free_optimum, curve=GOOD).total_heat == pytest.approx(expect)
    assert resolve(0.45, curve=GOOD).binding == "ceiling"


def test_the_cap_never_falls_below_the_floor_however_bad_the_book_looks() -> None:
    for h_eff in (0.05, 0.15, 0.28, 0.30, 1.0):
        cap, _why, _d = effective_ceiling({"nominal": 0.30, "covariance": h_eff,
                                           "factor": h_eff, "tail": h_eff})
        assert HEAT_TARGET - 1e-12 <= cap <= HEAT_HARD_CEILING + 1e-12, h_eff


# ----------------------------------------------------------------- 4. the bounds hear it too
def test_per_sleeve_bounds_tighten_on_a_concentrated_book() -> None:
    """The concentration leg of the per-sleeve bound counts the heat the book's INDEPENDENCE
    earns, not the nominal total it was handed. It can only tighten -- min, never max."""
    eff = effective(_one_factor(), {f"usd_{i}": 0.07 for i in range(4)})
    dd = {"a": 8.0, "b": 33.7}
    plain = per_sleeve_bounds(dd, HEAT_HARD_CEILING)
    tight = per_sleeve_bounds(dd, HEAT_HARD_CEILING, effective_heat=eff)
    assert tight["a"] < plain["a"], "a one-factor book must not earn 30%-sized sleeve bounds"
    assert all(tight[k] <= plain[k] + 1e-12 for k in dd)
    # A diversified book is left exactly where it was.
    wide = effective(_independent(), {f"ind_{i}": 0.035 for i in range(8)})
    assert per_sleeve_bounds(dd, HEAT_HARD_CEILING, effective_heat=wide) == plain


# ----------------------------------------------------------------- 5. the rail is registered
def test_the_cap_is_a_registered_measured_rail() -> None:
    """Growth governance: a new cap that nobody bills is a cap nobody can ever weaken."""
    from research import missed_growth

    r = rails.rail("effective_heat_ceiling")
    assert r.kind == "cap" and "heat_policy" in r.where
    assert r.measure in missed_growth.MEASURES, "the rail has no ledger line"


def test_the_allocator_measures_the_four_heats_before_it_solves() -> None:
    """A measurement taken after the decision is a report, not a control. Pins the wiring."""
    pre = _PF_SRC.index("eff_pre = effective_heat_of(ev, free.heat)")
    call = _PF_SRC.index("verdict = resolve(free.total_heat")
    assert pre < call, "effective heat must be measured BEFORE the heat law resolves"
    assert "effective_heat=eff_pre" in _PF_SRC, "resolve is not told the four heats"
    assert '"effective_ceiling": round(verdict.effective_ceiling, 6)' in _PF_SRC
    assert '"bound_by": verdict.binding' in _PF_SRC, "the artifact must say which bound bound"


# ----------------------------------------------------------------- 6. the drift monitor is heard
def _drift(verdict: str = "STABLE", *, structure: str = "STABLE",
           hazard: float | None = 0.4, age_h: float = 1.0) -> dict:
    when = datetime.now(tz=UTC) - timedelta(hours=age_h)
    return {"generated_utc": when.isoformat(), "verdict": verdict,
            "structure_verdict": structure, "hazard_max": hazard}


def test_a_structure_break_raises_the_crisis_world_share() -> None:
    share, why = crisis_share_from_drift(
        _drift("STRUCTURE_SHIFTED", structure="STRUCTURE_SHIFTED"), 0.06)
    assert share > 0.06 and share == pytest.approx(0.18)
    assert "STRUCTURE_SHIFTED" in why


def test_drift_ahead_raises_it_in_proportion_to_the_hazard() -> None:
    mild = crisis_share_from_drift(_drift("DRIFT_AHEAD", hazard=2.1), 0.06)[0]
    hard = crisis_share_from_drift(_drift("DRIFT_AHEAD", hazard=4.0), 0.06)[0]
    assert 0.06 < mild < hard
    assert hard == pytest.approx(0.18), "twice the drift line reaches the structure-break multiple"
    # A DRIFT_AHEAD with no hazard number moves nothing and says why (never a guessed z).
    none_, why = crisis_share_from_drift(_drift("DRIFT_AHEAD", hazard=None), 0.06)
    assert none_ == pytest.approx(0.06) and "no hazard_max" in why


def test_a_stale_or_absent_report_changes_nothing_and_says_so() -> None:
    for doc, token in ((None, "no readable DRIFT.json"), ({}, "no readable DRIFT.json"),
                       (_drift("STRUCTURE_SHIFTED", structure="STRUCTURE_SHIFTED", age_h=48.0),
                        "old"),
                       ({"verdict": "STRUCTURE_SHIFTED"}, "generated_utc")):
        share, why = crisis_share_from_drift(doc, 0.06)
        assert share == pytest.approx(0.06), why
        assert token in why


def test_a_calm_report_never_lowers_the_crisis_share() -> None:
    """The ratchet: a quiet sample is not a licence to model crises as rarer than the standing
    assumption -- that is how a book learns its real correlations at the worst moment."""
    for verdict in ("STABLE", "WATCH", "UNMEASURED"):
        share, why = crisis_share_from_drift(_drift(verdict, hazard=1.4), 0.06)
        assert share == pytest.approx(0.06) and "stands" in why


def test_the_crisis_share_is_capped_so_a_forecast_never_becomes_a_permanent_crisis() -> None:
    share, why = crisis_share_from_drift(
        _drift("STRUCTURE_SHIFTED", structure="STRUCTURE_SHIFTED"), 0.30)
    assert share == pytest.approx(CRISIS_SHARE_MAX) and "capped" in why


def test_the_allocator_actually_reads_the_drift_report() -> None:
    """A signal nothing opens is a signal that does not exist. Pins the wiring, not the function."""
    assert "drift_doc, drift_why = read_drift()" in _PF_SRC
    assert "crisis_share, crisis_why = crisis_share_from_drift(" in _PF_SRC
    assert "crisis_prob=crisis_share," in _PF_SRC, "the drawn worlds do not use the new share"
    assert '"drift_overlay"' in _PF_SRC, "the artifact does not record what the overlay did"
