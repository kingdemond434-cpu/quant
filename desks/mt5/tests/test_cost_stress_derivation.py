"""A COST-STRESS SCENARIO MUST BE STRICTLY MORE EXPENSIVE THAN THE BASELINE IT STRESSES.

THE DEFECT, measured live 2026-08-27 on the certificate path. Every stress scenario on this desk
rebuilt `Costs(...)` positionally from three fields of an existing cost model, so the fourth --
`quote_per_account` -- reverted to its 1.0 default and un-did the account-currency conversion the
baseline had already applied. `universal_gate`'s x3 scenario on CADJPY:

    baseline round trip  1699.29
    "x3" as written       607.00      <-- 0.36x the baseline it is supposed to stress
    x3 correct           1899.29

The gate whose entire purpose is proving a candidate survives three times its costs was testing it
at a THIRD of them, on the JPY crosses where this desk's live family sits. `quote_per_account`
defaults to 1.0 so that adding the field moved no existing call site -- which is right for a
construction and exactly wrong for a RE-derivation, where the safe default becomes a silent
revert. The same omission plus a per-OUNCE gold spread in a per-LOT field made
`external_gauntlet.costs_for` -- the one function deciding who gets a ten-gate certificate --
undercharge USDJPY 184.31x, CADJPY 8.21x, EURJPY 6.19x, GBPJPY 4.12x, XAUUSD 2.43x, all in the
direction that manufactures survivors.

These tests pin the property rather than the instances: derivation carries every field, the
certificate path constructs costs only through the sanctioned constructors, and no correction may
ever LOWER a cost -- a fix that could lower one could manufacture a survivor, which is worse than
the bug.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from mt5desk.engine import Costs  # noqa: E402

#: One symbol per denomination class. JPY crosses and gold are where the desk's live family sits.
SYMBOLS = ("XAUUSD", "USDJPY", "CADJPY", "EURJPY", "GBPJPY", "EURUSD", "EURZAR")


def _meta() -> dict:
    path = BASE / "data" / "universe" / "universe.json"
    if not path.is_file():
        pytest.skip("universe.json absent in this checkout")
    return json.loads(path.read_text("utf-8"))


@pytest.mark.parametrize("mult", [1.5, 2.0, 3.0])
def test_a_stressed_cost_is_never_cheaper_than_its_baseline(mult):
    """THE REGRESSION, in the form that catches it for any symbol and any multiplier."""
    meta = _meta()
    for sym in SYMBOLS:
        if sym not in meta:
            continue
        base = Costs.from_symbol(meta[sym], mult=2.0, commission_per_lot=3.50)
        stressed = base.stressed(mult)
        assert stressed.per_oz_roundtrip() > base.per_oz_roundtrip(), (
            f"{sym}: a x{mult} stress must cost MORE than the baseline; this is the exact "
            f"comparison that read 607.00 < 1699.29 on CADJPY")
        assert stressed.quote_per_account == base.quote_per_account, (
            f"{sym}: derivation must carry quote_per_account -- dropping it is the whole defect")
        assert stressed.contract_oz == base.contract_oz


def test_derivation_carries_fields_added_later():
    """The property that makes the class unreachable rather than this instance of it.

    `stressed` must copy the WHOLE dataclass, so a field added tomorrow is carried without any
    call site being edited. Compared field-by-field against the declared field set so that adding
    a field to `Costs` and forgetting it here fails HERE rather than silently in a gate.
    """
    base = Costs(spread_per_lot=100.0, commission_per_lot=3.5, contract_oz=1e5,
                 quote_per_account=185.61)
    got = base.stressed(2.0)
    for field in base.__dataclass_fields__:
        if field == "spread_per_lot":
            assert getattr(got, field) == pytest.approx(200.0)
        else:
            assert getattr(got, field) == getattr(base, field), (
                f"{field} was not carried through the derivation")


def test_the_gauntlet_never_hand_rolls_a_cost_model():
    """AST-level, because the defect is a SHAPE: arithmetic beside the constructor, not inside it.

    `external_gauntlet.costs_for` is the function that decides who gets a ten-gate certificate.
    It must call `Costs.from_symbol` and must not compute a spread of its own -- the hand-rolled
    body is what carried the per-ounce gold spread and the missing currency conversion for weeks
    after both were fixed elsewhere (GAP 144's residual).
    """
    src = (BASE / "scripts" / "external_gauntlet.py").read_text("utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "costs_for")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    sanctioned = [c for c in calls if isinstance(c.func, ast.Attribute)
                  and c.func.attr in {"from_symbol", "stressed"}]
    assert sanctioned, "costs_for must build costs through Costs.from_symbol"
    assert not any(isinstance(c.func, ast.Name) and c.func.id == "Costs" for c in calls), (
        "costs_for must not construct Costs directly -- that is where the hand-rolled "
        "per-ounce gold spread and the missing quote_per_account lived")
    assert "median_spread_pts" not in ast.dump(fn), (
        "costs_for must not recompute a spread beside the constructor; from_symbol owns it")


def test_no_certificate_path_module_rebuilds_costs_positionally():
    """The sweep, pinned so it cannot rot back one file at a time.

    Every module on the certificate/forward path must derive stress costs rather than
    reconstructing them. A `Costs(` call whose first argument is an attribute of another cost
    model is the rebuild signature, and it is what silently dropped the fourth field.
    """
    guarded = ["research/universal_gate.py", "research/run_hunt12.py", "research/run_hunt17.py",
               "research/fragility.py", "research/regime_discovery.py",
               "side_channels/ug_remote.py", "scripts/external_gauntlet.py"]
    offenders = []
    for rel in guarded:
        path = BASE / rel
        if not path.is_file():
            continue
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "Costs"):
                continue
            args = list(node.args) + [k.value for k in node.keywords]
            if any("spread_per_lot" in ast.dump(a) for a in args):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        f"rebuilt cost models on the certificate path: {offenders} -- use `.stressed()`, which "
        f"carries every field, instead of reconstructing from a subset")


def test_the_correction_only_ever_raises_a_cost():
    """It must be impossible for this repair to manufacture a survivor.

    A cost fix that could LOWER a cost is strictly more dangerous than the bug it replaces, so the
    sanctioned constructor is compared against the hand-rolled form it replaced on the live
    universe: every symbol must be charged MORE, never less.
    """
    meta = _meta()
    checked = 0
    for sym in SYMBOLS:
        m = meta.get(sym)
        if not m:
            continue
        spread = m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5)
        hand = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(spread, 0.05),
                     commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
        fixed = Costs.from_symbol(m, mult=1.0, commission_per_lot=3.50)
        assert fixed.per_oz_roundtrip() >= hand.per_oz_roundtrip(), (
            f"{sym}: the corrected cost model must never charge LESS than the hand-rolled one it "
            f"replaces -- that direction manufactures survivors")
        checked += 1
    assert checked >= 4, "the live family must actually be present to have been checked (L1.28a)"
