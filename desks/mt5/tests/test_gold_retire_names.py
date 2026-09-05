"""The promoter must name the gold sleeves exactly as the gateway emits them.

If these two drift, nothing raises: the promoter evaluates names that do not exist, finds no
ledger rows for them, retires nothing, and reports success. The armed book would silently lose
the decay protection it was just given, and the only symptom would be an absence -- which is
what L1.28a exists to forbid.

The gateway cannot be imported here (it imports MetaTrader5, which is Windows-only), so the
names are read from its source the same way desks/mt5/tests/test_risk_units.py reads gateway.py.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
for p in (str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

_GATEWAY_SRC = (DESK / "mt5desk" / "gateway.py").read_text("utf-8")


def _gold_windows_from_source() -> list[str]:
    """The `label` of every entry in the gateway's GOLD_WINDOWS literal."""
    tree = ast.parse(_GATEWAY_SRC)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "GOLD_WINDOWS" for t in node.targets):
            continue
        assert isinstance(node.value, ast.List), "GOLD_WINDOWS is no longer a list literal"
        out = []
        for elt in node.value.elts:
            assert isinstance(elt, ast.Tuple), "GOLD_WINDOWS entries must stay (label, hour, rng)"
            label = elt.elts[0]
            assert isinstance(label, ast.Constant), "the window label must stay a literal"
            out.append(str(label.value))
        return out
    raise AssertionError("GOLD_WINDOWS not found in gateway.py")


def test_promoter_names_match_the_windows_the_gateway_emits() -> None:
    import promoter

    expected = {f"gold_{label}" for label in _gold_windows_from_source()}
    assert set(promoter.GOLD_SLEEVE_NAMES) == expected, (
        "promoter.GOLD_SLEEVE_NAMES has drifted from gateway.GOLD_WINDOWS; the retire walk would "
        f"evaluate names that are never traded. gateway={sorted(expected)} "
        f"promoter={sorted(promoter.GOLD_SLEEVE_NAMES)}")


def test_both_sides_agree_on_the_retirement_file() -> None:
    """One path, or a retirement is written where nothing reads it."""
    import promoter

    assert "GOLD_RETIRED.json" in _GATEWAY_SRC, "gateway no longer reads the retirement file"
    assert promoter.GOLD_RETIRED_FILE.name == "GOLD_RETIRED.json"
    assert promoter.GOLD_RETIRED_FILE.parent.name == "data"


def test_absent_file_retires_nothing() -> None:
    """The pre-2026-09-01 behaviour must be exactly what an absent file reproduces."""
    import promoter

    missing = promoter.BASE / "data" / "__no_such_gold_retired__.json"
    real = promoter.GOLD_RETIRED_FILE
    try:
        promoter.GOLD_RETIRED_FILE = missing
        assert promoter._load_gold_retired() == {}
    finally:
        promoter.GOLD_RETIRED_FILE = real
