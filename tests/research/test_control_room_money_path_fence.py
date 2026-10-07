"""The control room's regime weights may not reach money unbilled (growth governance, Rule 1).

`libs.regime.control_room.sleeve_weights` (and its `kernel`) reshape how much each day of a
sleeve's history counts. Today they feed research contracts only. The day a money-path module
(order path, sizing, allocator, promoter, the forward chain) reads them, the weights become a
capital modifier, and GROWTH_GOVERNANCE requires every capital modifier to be two-sided
(`libs/portfolio/capital_modifiers.py`) and billed by a missed-growth line (a `Rail` in
`libs/portfolio/rails.py` whose `where` names the consumer, measured by
`research/missed_growth.py`). This fence fails the first commit that wires it without both.

THE MONEY PATH IS THE RELEASE'S OWN LIST (`libs.ops.release.MONEY_PATH`, the modules the box
seals and smoke-tests) plus every file under its library and mt5desk directory roots, never a
hand-picked tuple: a tuple misses the next module someone adds to the release.

THE READ IS AN AST WALK THAT RESOLVES ALIASES, because a grep for `sleeve_weights` misses
`import libs.regime.control_room as cr; cr.kernel(...)`, a parenthesised multi-line
`from ... import (kernel,)`, a dynamic `importlib.import_module`/`__import__`/`getattr`, and the
planned route itself -- the allocator reading a `control_room_kernel` field out of its own
allocation file (`practitioner_processes.py`, `_contract`). String constants are folded across
`+` and f-string pieces and matched case-insensitively, so a report path built by concatenation,
`joinpath` pieces or a lower-case glob is still a reach. Docstrings are not code and are skipped.
PowerShell under the box's scripts and `ops/` is scanned as text.

Day LABELS (`label_days`, `daily_frame`) are a signal conditioner a family may test like any
other feature, so importing those names from the library is not a weight read.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from libs.ops.release import MONEY_PATH
from libs.portfolio.rails import RAILS

ROOT = Path(__file__).resolve().parents[2]

#: The library whose weight functions are the reach; only these names of it are weights.
_LIB = "control_room"
_WEIGHT_NAMES = frozenset({"sleeve_weights", "kernel"})
#: The daily organs that publish the weights or their admission: ANY import of one is a reach.
_ORGANS = frozenset({"regime_allocation_contract", "control_room_mechanisms", "bench_bridge",
                     "practitioner_processes"})
#: Fragments that, inside any string the code builds, mean the weights or their reports.
_TOKENS = re.compile(r"control_room|regime_allocation_contract|bench_bridge|"
                     r"practitioner_processes|sleeve_weights", re.IGNORECASE)
_DYNAMIC = frozenset({"import_module", "__import__", "getattr", "spec_from_file_location"})


def _roots() -> list[str]:
    dirs = {str(Path(p).parent) for p in MONEY_PATH}
    return sorted(set(MONEY_PATH)
                  | {d for d in dirs if d.startswith(("libs/", "desks/mt5/mt5desk"))})


def _money_path_files(suffix: str = ".py") -> list[Path]:
    out: set[Path] = set()
    for rel in _roots():
        p = ROOT / rel
        if p.is_file() and p.suffix == suffix:
            out.add(p)
        elif p.is_dir():
            out |= {f for f in p.rglob(f"*{suffix}") if "__pycache__" not in f.parts}
    if suffix == ".ps1":
        for d in ("desks/mt5/scripts", "ops"):
            out |= set((ROOT / d).rglob("*.ps1"))
    return sorted(out)


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _strings(node: ast.AST) -> str:
    """Every constant string fragment inside an expression, concatenated: `"CONTROL_" + x +
    "ROOM.json"` and `f"{d}/control_room.json"` both read as text the token can match."""
    return "".join(n.value for n in ast.walk(node)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str))


def _is_lib(mod: str) -> bool:
    return mod.split(".")[-1] == _LIB


def reaches(src: str) -> list[str]:
    """Why this source reaches the control room's weights ([] when it does not)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["unparseable: cannot be shown not to reach"]
    why: list[str] = []
    lib_aliases: set[str] = set()
    docs = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[-1] in _ORGANS:
                    why.append(f"imports {a.name}")
                elif _is_lib(a.name):
                    lib_aliases.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                if mod.split(".")[-1] in _ORGANS or a.name in _ORGANS:
                    why.append(f"imports from {mod or '.'} {a.name}")
                elif _is_lib(mod) and (a.name in _WEIGHT_NAMES or a.name == "*"):
                    why.append(f"from {mod} import {a.name}")
                elif a.name == _LIB:
                    lib_aliases.add(a.asname or a.name)
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _DYNAMIC and node.args:
                text = "".join(_strings(x) for x in node.args)
                if _TOKENS.search(text) or any(w in text for w in _WEIGHT_NAMES):
                    why.append(f"{name}({text[:60]!r})")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docs and _TOKENS.search(node.value):
            why.append(f"string {node.value[:60]!r}")
        elif isinstance(node, ast.JoinedStr) and _TOKENS.search(_strings(node)):
            why.append(f"f-string {_strings(node)[:60]!r}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) \
                and _TOKENS.search(_strings(node)):
            why.append(f"concatenation {_strings(node)[:60]!r}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _WEIGHT_NAMES:
            base = ast.unparse(node.value)
            if base in lib_aliases or _is_lib(base):
                why.append(f"{base}.{node.attr}")
    return why


def violations(files: list[Path], rails=RAILS) -> list[str]:
    """Money-path files that reach the weights without a two-sided modifier and a rail line."""
    bad = []
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix == ".ps1":
            why = [f"text {m.group(0)!r}" for m in _TOKENS.finditer(src)]
        else:
            why = reaches(src)
        if not why:
            continue
        two_sided = "capital_modifiers" in src
        billed = any(f.stem in r.where for r in rails)
        if not (two_sided and billed):
            rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
            bad.append(f"{rel}: {why[:3]} two_sided={two_sided} missed_growth_line={billed}")
    return bad


def test_the_walk_covers_the_release_money_path():
    files = {p.relative_to(ROOT).as_posix() for p in _money_path_files()}
    missing = [m for m in MONEY_PATH if m not in files and (ROOT / m).exists()]
    assert missing == []
    assert len(files) > 50, "money-path walk found too little; the roots moved"


def test_no_money_path_module_reads_control_room_weights_unbilled():
    assert violations(_money_path_files() + _money_path_files(".ps1")) == []


def test_every_route_the_audit_named_is_a_reach():
    routes = {
        "plain": "from libs.regime.control_room import sleeve_weights\n",
        "alias_module": "import libs.regime.control_room as cr\nw = cr.kernel(a, b)\n",
        "bare_alias": "import control_room as cr\nw = cr.sleeve_weights('X', d)\n",
        "from_package": "from libs.regime import control_room as c\nc.kernel(p, n)\n",
        "multiline": "from libs.regime.control_room import (\n    label_days,\n    kernel,\n)\n",
        "dotted": "import libs.regime.control_room\nlibs.regime.control_room.kernel(p, n)\n",
        "alloc_field": "k = alloc.get('control_room_kernel')\n",
        "importlib": "m = importlib.import_module('libs.regime.' + 'control_room')\n",
        "dunder": "m = __import__(f'libs.regime.{\"control_room\"}')\n",
        "getattr": "w = getattr(mod, 'sleeve_' + 'weights')\n",
        "fstring_report": "p = REPORTS / f'{name}_CONTROL_ROOM.json'\n",
        "concat_report": "p = str(R) + '/REGIME_ALLOCATION_CONTRACT.json'\n",
        "joinpath": "p = R.joinpath('reports', 'BENCH_BRIDGE.json')\n",
        "lower_glob": "ps = R.glob('control_room*.json')\n",
        "practitioner": "p = R / 'PRACTITIONER_PROCESSES.json'\n",
        "organ_import": "from research import regime_allocation_contract\n",
    }
    missed = [k for k, src in routes.items() if not reaches(src)]
    assert missed == []


def test_day_labels_and_docstrings_are_not_a_reach():
    src = ('"""Conditions on libs.regime.control_room day labels."""\n'
           "from libs.regime.control_room import daily_frame, label_days\n"
           "def f():\n    '''uses control_room labels'''\n    return label_days\n")
    assert reaches(src) == []


def test_the_fence_needs_both_halves(tmp_path):
    from libs.portfolio.rails import Rail
    f = tmp_path / "sizer.py"
    f.write_text("import libs.regime.control_room as cr\nw = cr.kernel\n", encoding="utf-8")
    assert len(violations([f])) == 1
    f.write_text("import libs.regime.control_room as cr\n"
                 "from libs.portfolio import capital_modifiers\nw = cr.kernel\n", encoding="utf-8")
    assert len(violations([f])) == 1, "two-sided alone is not enough without a rail line"
    rail = Rail("regime_weights", "shrink", "sizer.regime_tilt <- control_room",
                "measure_shrinkage")
    assert violations([f], rails=(rail,)) == []


def test_powershell_is_scanned(tmp_path):
    f = tmp_path / "Run-Gateway.ps1"
    f.write_text("$k = Get-Content reports\\CONTROL_ROOM.json\n", encoding="utf-8")
    assert len(violations([f])) == 1
