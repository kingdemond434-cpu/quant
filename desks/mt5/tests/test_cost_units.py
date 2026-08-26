"""Two unit traps in one cost model, both found 2026-08-26, both undercharging.

`Costs` divides `per_oz_roundtrip()` by `contract_oz` to land on a PRICE-unit cost:

    spread_per_lot      built as pts * tick_size * contract_size, so the division cancels and
                        it arrives as a price-unit spread. CORRECT, and the class docstring
                        already said so.
    commission_per_lot  a CURRENCY amount. Dividing it by contract_size asserts that one unit of
                        the account's currency is one unit of PRICE -- true only when the symbol
                        is quoted in the account's own currency. On a EUR account it made CADJPY
                        commission 184x too small.

Plus the hardcode the class docstring warned about and the money path kept anyway: gold's spread
passed as dollars per OUNCE into a per-LOT field, charging 3% of a real spread.

Both errors point the same way -- cheaper trading, better-looking cells -- and both land hardest
on the JPY crosses, which is where this desk's surviving edges live.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs  # noqa: E402

#: A EUR account: one yen of price is worth 0.005418 EUR for one lot.
CADJPY = {"median_spread_pts": 1.0, "tick_size": 0.001,
          "contract_size": 100000.0, "tick_value": 0.5418}
XAUUSD = {"median_spread_pts": 10.0, "tick_size": 0.01,
          "contract_size": 100.0, "tick_value": 0.8632}
#: Quoted in the account's own currency: the conversion must be exactly 1.0 and change nothing.
EURCHF_LIKE = {"median_spread_pts": 12.0, "tick_size": 1e-05,
               "contract_size": 100000.0, "tick_value": 1.0}


def price_cost(costs: Costs) -> float:
    """What the engine actually charges, in price units (see `run_backtest`)."""
    return costs.per_oz_roundtrip() / costs.contract_oz


def test_jpy_commission_was_184x_too_small() -> None:
    fixed = Costs.from_symbol(CADJPY, commission_per_lot=3.50)
    # 7.00 EUR round turn / 541.8 EUR per yen of price = 0.012920 yen.
    commission_only = price_cost(fixed) - CADJPY["median_spread_pts"] * CADJPY["tick_size"]
    assert commission_only == pytest.approx(0.012920, rel=0.01)

    broken = Costs(spread_per_lot=100.0, commission_per_lot=3.50, contract_oz=100000.0)
    broken_commission = price_cost(broken) - 0.001
    assert broken_commission == pytest.approx(7.0 / 100000.0, rel=0.01)
    assert commission_only / broken_commission == pytest.approx(184.6, rel=0.02)


def test_the_fix_only_ever_raises_the_cost() -> None:
    # A correction that could LOWER a cost can manufacture a survivor. This one cannot.
    for meta in (CADJPY, XAUUSD, EURCHF_LIKE):
        fixed = Costs.from_symbol(meta, commission_per_lot=3.50)
        unconverted = Costs(spread_per_lot=fixed.spread_per_lot, commission_per_lot=3.50,
                            contract_oz=fixed.contract_oz)
        assert price_cost(fixed) >= price_cost(unconverted) - 1e-12


def test_account_quoted_symbol_is_unchanged() -> None:
    # quote_per_account defaults to 1.0 precisely so no existing hand-rolled call site moves.
    fixed = Costs.from_symbol(EURCHF_LIKE, commission_per_lot=3.50)
    assert fixed.quote_per_account == pytest.approx(1.0, rel=1e-9)
    assert Costs(spread_per_lot=1.0, commission_per_lot=3.50,
                 contract_oz=100.0).quote_per_account == 1.0


def test_missing_tick_value_falls_back_rather_than_dividing_by_zero() -> None:
    # An uncosted symbol must not crash the engine, and must not silently invent a conversion.
    fixed = Costs.from_symbol({"median_spread_pts": 1.0, "tick_size": 0.001,
                               "contract_size": 100000.0}, commission_per_lot=3.50)
    assert fixed.quote_per_account == 1.0


def test_gold_hardcode_charged_three_percent_of_its_spread() -> None:
    hardcoded = Costs(spread_per_lot=max(0.48, 0.05), commission_per_lot=3.50, contract_oz=100.0)
    hardcoded_spread = 0.48 / 100.0
    assert hardcoded_spread == pytest.approx(0.0048)
    registry_spread = XAUUSD["median_spread_pts"] * XAUUSD["tick_size"]
    assert registry_spread == pytest.approx(0.10)
    assert registry_spread / hardcoded_spread > 20
    fixed = Costs.from_symbol(XAUUSD, commission_per_lot=3.50)
    assert price_cost(fixed) > price_cost(hardcoded)


def test_money_path_uses_the_sanctioned_constructor_not_a_hand_roll() -> None:
    """The regression test for the actual failure: the fix existed and the money path bypassed it.

    `Costs.from_symbol` carried both corrections for weeks while `shadow_forward` hand-rolled the
    arithmetic beside it, so the money path -- the one producing forward evidence -- received
    neither. A grep is the honest test here: the defect was not a wrong number, it was a call
    site that never asked.
    """
    import ast  # noqa: PLC0415

    src = (_DESK / "research" / "shadow_forward.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "per_symbol_costs")
    # Strip the docstring: this function's prose NAMES the constants it must no longer compute,
    # so a plain substring search over the source would fail on its own explanation.
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    code = "\n".join(ast.unparse(node) for node in body)
    assert "Costs.from_symbol" in code, "money path stopped using the sanctioned constructor"
    assert "0.48" not in code, "the gold per-ounce hardcode came back"
    assert "median_spread_pts" not in code, "the spread arithmetic was hand-rolled again"


def test_shadow_costs_on_the_real_registry_are_positive_and_account_correct() -> None:
    """End-to-end over the registry as it actually stands on disk."""
    import json  # noqa: PLC0415

    registry = json.loads(
        (_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for sym in ("CADJPY", "EURJPY", "USDJPY", "XAUUSD", "XAGUSD"):
        meta = registry.get(sym)
        if not meta:
            pytest.skip(f"{sym} absent from the registry on this box")
        costs = Costs.from_symbol(meta, commission_per_lot=3.50)
        assert costs.quote_per_account > 0
        assert price_cost(costs) > 0, f"{sym} costs nothing to trade, which is never true"
        if sym.endswith("JPY"):
            # The conversion has to be the ~185 yen-per-EUR figure, not 1.0.
            assert costs.quote_per_account > 100, f"{sym} reverted to the unconverted commission"
