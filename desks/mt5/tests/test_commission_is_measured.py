"""THE COMMISSION IS MEASURED, AND IT IS 93% OF THE BILL.

`reports/FUSION_COST.json:median_commission_share_of_raw_cost` reads 0.9298 on this account, so
the spread argument this desk keeps having is an argument about the remaining seven percent while
the term that carries the cost is a flat contract nobody was disputing. It was being charged at
1.75x: `shadow_forward.per_symbol_costs` hardcoded `commission_per_lot=3.50`, a ROUND-TURN figure
in the field `Costs.per_oz_roundtrip` doubles, against the account's own measured 2.00 per side.

MEASURED 2026-09-24 from `history_deals_get` over every deal the account has ever done: 427
priced deals on 13 symbols, and EVERY symbol reads p10 = p50 = p90 = min = 2.00 -- FX majors
(AUDUSD 38, USDCHF 16, EURUSD 2), FX crosses (EURCHF 88, AUDCAD 22, AUDNZD 16, EURGBP 14,
NZDCAD 2), FX exotics (CHFNOK 38, GBPSEK 4, GBPMXN 4, USDMXN 2) and gold (XAUUSD 181). Gold is
181 of the 427, so "a gold rate averaged over a thin tail" was the obvious way to be wrong about
it, and it is not that: the rate is flat across four asset classes.

WHAT THESE PIN, and none of them is the number itself -- a test that asserts 2.00 would have to
be edited the day the account is re-measured, which is the shape that let 3.50 outlive its own
correction by three weeks:

  * the money path READS the desk's one constant rather than copying it, so a re-measurement
    reaches every lane with no edit anywhere;
  * no live lane carries the round-turn literal any more;
  * the class coverage is stated and honest -- five classes this account has never traded
    inherit the rate rather than evidencing it, and absence is not a permission (L1.28a).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

fc = pytest.importorskip("libs.portfolio.fusion_cost")

#: The lanes a CLOCK reaches, and therefore the ones where a wrong rate costs real candidates.
#: `external_gauntlet.costs_for` is absent on purpose: it already passes no override and takes
#: `Costs.from_symbol`'s default, which is the same measured constant.
MONEY_PATH = ("research/shadow_forward.py", "research/qquant_gates.py")

#: The shape the fix removed. A round-turn figure in a field the engine charges per side.
ROUND_TURN_LITERAL = 3.50


def test_the_forward_clocks_read_the_measured_constant_rather_than_a_literal(monkeypatch):
    """Re-measure the account and the forward lane must follow with no edit of its own."""
    engine = pytest.importorskip("mt5desk.engine")
    sf = pytest.importorskip("shadow_forward")
    meta = {"SYM": {"tick_size": 0.01, "contract_size": 100.0, "tick_value": 1.0,
                    "median_spread_pts": 5.0}}
    before = sf.per_symbol_costs(meta, "SYM")
    assert before.commission_per_lot == fc.COMMISSION_PER_LOT_PER_SIDE
    assert before.commission_per_lot != ROUND_TURN_LITERAL, (
        "3.50 is a round-turn figure in a per-side field: per_oz_roundtrip doubles it")
    monkeypatch.setattr(fc, "COMMISSION_PER_LOT_PER_SIDE", 1.23)
    after = sf.per_symbol_costs(meta, "SYM")
    assert after.commission_per_lot == 1.23, (
        "the call site must READ the constant, not copy its value -- a copy is how 3.50 "
        "survived its own correction for three weeks")
    assert isinstance(after, engine.Costs)


@pytest.mark.parametrize("rel", MONEY_PATH)
def test_no_live_lane_still_hardcodes_the_round_turn_figure(rel):
    """Read as an AST, not as text: a comment naming 3.50 is history and must stay readable.

    Every module here documents the defect in prose -- that is the desk remembering why -- so a
    substring search would fail on the explanation rather than on the code. Only a numeric
    literal actually passed as `commission_per_lot` is the defect.
    """
    tree = ast.parse((_DESK / rel).read_text(encoding="utf-8"))
    offenders = [
        f"{rel}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "commission_per_lot"
        and float(_constant_scale(kw.value) or 0.0) >= ROUND_TURN_LITERAL]
    assert not offenders, (
        f"{offenders} charge at least {ROUND_TURN_LITERAL} per SIDE, which is Fusion Zero's "
        "round turn billed twice; read fusion_cost.COMMISSION_PER_LOT_PER_SIDE instead")


def _constant_scale(node: ast.expr) -> float | None:
    """The numeric literal in `X`, `X * mult` or `mult * X`, or None when there is no literal.

    `qquant_gates` multiplies the commission by the stress `mult`, which is a SEPARATE decision
    with its own evidence and deliberately not taken here -- so the literal has to be found
    inside the product rather than only when it stands alone.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        for side in (node.left, node.right):
            found = _constant_scale(side)
            if found is not None:
                return found
    return None


def test_the_class_coverage_is_stated_and_does_not_claim_the_untraded_classes():
    """The rate is evidenced on four classes and INHERITED on five. Say which is which."""
    measured, inherited = fc.COMMISSION_MEASURED_CLASSES, fc.COMMISSION_INHERITED_CLASSES
    assert not set(measured) & set(inherited), "a class is evidenced or inherited, never both"
    assert "metal" in measured and len(measured) > 1, (
        "gold is 181 of the 427 deals, so the claim that matters is that the rate is NOT "
        "gold-specific: it must be evidenced on more than metals")
    assert {"share_cfd", "crypto_cfd"} <= set(inherited), (
        "this account has never traded either, and share CFDs are where a venue most often "
        "prices by notional instead of per lot -- absence is not a permission")
    assert fc.COMMISSION_UNIT == "account currency per lot per side"


def test_the_published_brochure_rate_is_kept_beside_the_measured_one():
    """Both numbers stay visible so the gap between the brochure and the ledger is auditable."""
    assert fc.COMMISSION_PUBLISHED_USD_PER_SIDE > fc.COMMISSION_PER_LOT_PER_SIDE
    assert fc.COMMISSION_PER_LOT_PER_SIDE > 0, "a zero commission is not a Zero account"
