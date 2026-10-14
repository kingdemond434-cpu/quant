"""A `LIVE` sleeve_registry row is a frozen forward-clock identity, never a trade (2026-10-14).

`research/sleeve_registry.freeze()` stamps EVERY clock it freezes `status: LIVE`: on 2026-10-14
all 319 registry rows read LIVE (EURUSD.cot_positioning among them) while data/sleeves.json held
three LIVE rows. The two words are different questions -- "does this identity still hold" versus
"may this place an order" -- so a set-equality fence between them would be red by design.

The invariant that matters is that no module which sizes, funds or places an order reads the
registry at all: placement is `gateway.load_sleeves` over data/sleeves.json, behind the book
overlay and the promoter's replication door. This pins it by reading each module's code (imports
and string constants, not comments), so a future edit that reaches for the registry's LIVE set on
the money path fails here first.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MONEY_PATH = (
    "desks/mt5/mt5desk/gateway.py",
    "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/mt5desk/kelly_sizing.py",
    "desks/mt5/mt5desk/sizing.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/research/pf_allocator.py",
)


def _registry_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)}
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[-1] == "sleeve_registry"]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[-1] == "sleeve_registry" or any(
                    a.name == "sleeve_registry" for a in node.names):
                hits.append(f"from {mod} import ...")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs and "sleeve_registry" in node.value):
            hits.append(repr(node.value[:80]))
    return hits


@pytest.mark.parametrize("rel", MONEY_PATH)
def test_no_money_path_module_reads_the_registry(rel: str) -> None:
    path = ROOT / rel
    assert path.exists(), f"{rel} moved: update MONEY_PATH so this fence still covers it"
    assert _registry_reads(path) == [], (
        f"{rel} reads sleeve_registry: a registry LIVE row is a frozen clock identity, not a "
        "sleeve the desk may trade or fund -- read data/sleeves.json instead")
