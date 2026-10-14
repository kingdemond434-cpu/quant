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


# ------------------------------------------------ the transitive walk (auditor ask, 2026-10-14)
#: The direct fence above reads six files; the money path IMPORTS ~300 more (pf_allocator ->
#: promoter -> executables -> ... -> shadow_forward -> sleeve_registry). Every module in that
#: import closure that reads the registry is named here with WHY it is not a sizing read. A new
#: reader fails until it is named; a named entry that stops reading, or leaves the closure, fails
#: too, so the list can only describe what is true.
TRANSITIVE_READERS: dict[str, str] = {
    "desks/mt5/research/promoter.py":
        "stamps the registry sleeve_id onto a promoted row (identity); sizes from the allocator",
    "desks/mt5/research/shadow_forward.py":
        "the forward-clock organ that FREEZES registry identities; it places no order",
    "desks/mt5/research/session_runtime_window.py":
        "reads a clock's frozen session window for the forward clock, not for capital",
    "desks/mt5/research/certificate_truth.py":
        "audits certificate -> clock truth on the research side; writes a report",
    "libs/ops/release.py":
        "names sleeve_registry.py as a release code path (a path string, not a read)",
    "libs/tiers/firewall.py":
        "names the module in the tier firewall's research-side list",
    "libs/tiers/research_live_identity.py":
        "quotes the registry in a refusal message ('no forward clock ... froze this spec')",
}
_SEARCH = ("", "desks/mt5", "desks/mt5/research", "desks/mt5/mt5desk")


def _resolve(dotted: str, here: Path) -> Path | None:
    parts = dotted.split(".")
    for base in (here.parent, *(ROOT / s for s in _SEARCH)):
        for cand in (base.joinpath(*parts).with_suffix(".py"),
                     base.joinpath(*parts, "__init__.py")):
            if cand.is_file():
                return cand
    return None


def _imported(path: Path) -> list[Path]:
    out: list[Path] = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names: list[str] = []
        anchor = path
        if isinstance(n, ast.Import):
            names = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = path.parent
                for _ in range(n.level - 1):
                    base = base.parent
                anchor = base / "_.py"
            mod = n.module or ""
            names = ([mod] if mod else []) + [f"{mod}.{a.name}" if mod else a.name
                                              for a in n.names]
        for name in names:
            hit = _resolve(name, anchor)
            if hit is not None and ROOT in hit.resolve().parents:
                out.append(hit.resolve())
    return out


def money_path_closure() -> set[str]:
    seen: set[str] = set()
    stack = [(ROOT / rel).resolve() for rel in MONEY_PATH]
    while stack:
        p = stack.pop()
        rel = p.relative_to(ROOT).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        stack.extend(_imported(p))
    return seen


def test_every_transitive_registry_reader_on_the_money_path_is_named() -> None:
    closure = money_path_closure()
    assert len(closure) > len(MONEY_PATH), "the import walk resolved nothing: it is broken"
    readers = {rel for rel in closure
               if not rel.endswith("/sleeve_registry.py") and _registry_reads(ROOT / rel)}
    new = sorted(readers - set(TRANSITIVE_READERS))
    stale = sorted(set(TRANSITIVE_READERS) - readers)
    assert not new, (f"money-path import closure gained registry reader(s) {new}: name each in "
                     "TRANSITIVE_READERS with why it is not a sizing read, or read sleeves.json")
    assert not stale, f"TRANSITIVE_READERS names {stale}, which no longer read it: drop them"
