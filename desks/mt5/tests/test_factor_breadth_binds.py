"""Four sleeves that are one dollar view must not buy the heat of four independent bets.

    python -m pytest desks/mt5/tests/test_factor_breadth_binds.py -q

`heat_budget(k_eff)` scales the desk's total risk with sqrt(effective breadth), and k_eff came
from realised return correlation alone. Correlation is backward-looking and estimated on the
quiet sample: four sleeves each secretly SHORT USD measure as four bets for as long as the dollar
does not move, and then move together on the day it does.

`libs/risk/fx_factors.py` already decomposed a book into currency legs and already reported the
number that matters -- measured on the live survivor set, `n_effective 1.019 across 17 sleeves`.
It had ZERO non-test callers, and described itself as "a MEASUREMENT, not a gate and not a
sizer", which is exactly why nothing ever changed because of it.

WHAT MUST NOT REGRESS:

  1. the capital number is the MINIMUM of return breadth and factor breadth
  2. an absent or unusable factor measurement NEVER widens the budget
  3. this sizes nothing -- it constrains breadth only
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK.parent.parent))

from mt5desk import independence as ind  # noqa: E402


def _rows(names: list[str], days: int = 40) -> list[dict]:
    """Uncorrelated-looking daily rows: alternating signs per sleeve so rho stays low."""
    out = []
    for i, n in enumerate(names):
        for d in range(days):
            out.append({"sleeve": n, "time": f"2026-07-{(d % 28) + 1:02d}T12:00:00",
                        "r_multiple": (1.0 if (d + i) % 2 else -0.9)})
    return out


# ------------------------------------------------- 1. the tighter bound wins

def test_currency_concentration_binds_below_return_breadth() -> None:
    """Four short-USD expressions: returns may say four bets, the legs say roughly one."""
    names = ["EURUSD_a", "GBPUSD_a", "AUDUSD_a", "NZDUSD_a"]
    # every sleeve long the non-USD leg == short USD four times over
    exposures = {"EURUSD": 1.0, "GBPUSD": 1.0, "AUDUSD": 1.0, "NZDUSD": 1.0}
    k_ret, _ = ind.measure_k_eff(_rows(names))
    k_cap, why = ind.measure_from_ledger(_rows(names), exposures=exposures)
    k_fac, _ = ind.factor_k_eff(exposures)

    assert k_fac is not None, "the currency decomposition must be measurable on plain FX majors"
    assert k_cap is not None
    assert k_cap <= (k_ret if k_ret is not None else k_cap) + 1e-9, (
        "the capital breadth must never exceed the return breadth")
    assert k_cap == min(x for x in (k_ret, k_fac) if x is not None)
    if k_fac < (k_ret or float("inf")):
        assert "BINDS" in why


def test_a_genuinely_spread_book_is_not_punished() -> None:
    """Different currencies on both sides: the factor bound should not be the binding one."""
    exposures = {"EURJPY": 1.0, "AUDCAD": 1.0, "GBPCHF": 1.0}
    k_fac, _ = ind.factor_k_eff(exposures)
    assert k_fac is not None
    assert k_fac > 1.5, f"a spread book collapsed to {k_fac:.2f} effective bets"


# ------------------------------------------------- 2. absence never widens

def test_no_exposures_leaves_the_return_number_untouched() -> None:
    rows = _rows(["a", "b"])
    base, base_why = ind.measure_k_eff(rows)
    same, same_why = ind.measure_from_ledger(rows)
    assert same == base and same_why == base_why


def test_an_unusable_decomposition_does_not_raise_the_budget() -> None:
    rows = _rows(["a", "b"])
    base, _ = ind.measure_k_eff(rows)
    k, why = ind.measure_from_ledger(rows, exposures={})
    assert k == base, "an empty exposure map must leave the budget exactly as it was"
    assert "UNMEASURED" in why


def test_unknown_symbols_are_reported_not_counted_as_diversification() -> None:
    """A silent zero would read exactly like genuine diversification (L1.28a)."""
    k, why = ind.factor_k_eff({"NOTAPAIR": 1.0})
    assert k is None or k >= 1.0
    if k is None:
        assert "UNMEASURED" in why


# ------------------------------------------------- 2b. and now it reaches the CAPITAL BUDGET

def test_the_four_heat_breadth_reaches_the_heat_law_not_just_a_report() -> None:
    """THE SAME DEFECT, ONE LAYER UP (2026-09-05). `fx_factors` measured currency concentration and
    nothing changed because of it; `latent_factors` then measured covariance / latent-factor / tail
    heat and the allocator REPORTED it after the solve, so H_eff bound nothing either. It binds
    now: the breadth those four heats imply sets the CEILING on nominal heat, by the same
    sqrt-breadth law `heat_budget` already applies to k_eff -- and the floor is untouched.
    """
    import sys as _sys
    _sys.path.insert(0, str(DESK / "research"))
    from research.heat_policy import HEAT_HARD_CEILING, HEAT_TARGET, effective_ceiling

    one_bet = {"nominal": 0.28, "covariance": 0.26, "factor": 0.27, "tail": 0.25}
    spread = {"nominal": 0.28, "covariance": 0.09, "factor": 0.10, "tail": 0.08}
    assert effective_ceiling(one_bet)[0] == HEAT_TARGET, (
        "four expressions of one factor must not earn the room four bets earn")
    assert effective_ceiling(spread)[0] == HEAT_HARD_CEILING
    # An unusable measurement NEVER widens the budget past the standing bar -- the same property
    # this file already pins for the currency decomposition.
    assert effective_ceiling(None)[0] <= HEAT_HARD_CEILING
    assert effective_ceiling({"nominal": 0.28, "covariance": 1e-9})[0] <= HEAT_HARD_CEILING


# ------------------------------------------------- 3. it constrains breadth, it does not size

def test_the_module_exposes_no_sizing_authority() -> None:
    """Sizing stays in the gateway -- the only thing that knows Fusion tick value."""
    import inspect
    src = inspect.getsource(ind.factor_k_eff) + inspect.getsource(ind._floor_by_factor)
    for forbidden in ("lot", "order_send", "volume", "position_size"):
        assert forbidden not in src, f"breadth code must not reach into sizing ({forbidden})"
