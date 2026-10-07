"""The control room's regime weights may not reach money unbilled (growth governance, Rule 1).

`libs.regime.control_room.sleeve_weights` (and its `kernel`) reshape how much each day of a
sleeve's history counts. Today they feed research contracts only. The day a money-path module
(order path, sizing, allocator, promoter, the forward chain) reads them, the weights become a
capital modifier, and GROWTH_GOVERNANCE requires every capital modifier to be two-sided
(`libs/portfolio/capital_modifiers.py`) and billed by a missed-growth line (a `Rail` in
`libs/portfolio/rails.py` whose `where` names the consumer, measured by
`research/missed_growth.py`). This fence fails the first commit that wires it without both.

WHAT IS WALKED. The release's own list (`libs.ops.release.MONEY_PATH`), every file under the
money-path directories (`libs/execution`, `libs/risk`, `libs/portfolio`, `desks/mt5/mt5desk`,
and the parents of every listed module under `libs/`), and the IMPORT CLOSURE of all of that
inside this repository -- so a helper a money-path module imports, which itself calls the
weights, is a reach of the money path. A symlink is read as the file it points at.

WHAT COUNTS AS A REACH, per file, by an AST read that resolves aliases and folds constants:
  * importing the weight functions, or the control-room organs (`research.control_room`,
    `regime_allocation_contract`, `control_room_mechanisms`, `bench_bridge`,
    `practitioner_processes`), or a bare `control_room`;
  * any use of the `libs.regime.control_room` module through an alias (reassigned aliases
    included) other than its day-label readers (`label_days`, `daily_frame`);
  * DEFINING a function named `sleeve_weights` or `kernel` -- a copy of the library is the
    library;
  * a string the code can build -- folded across `+`, f-strings, `%`, `.format`, `"".join`,
    `[::-1]`, `chr(...)`, `bytes.fromhex(...)` and names bound to constants -- that names a
    weight, an organ or one of their reports; and any 2-4 string pieces in ONE scope (a
    function, or the module body) that join to such a name, which is how a glob filtered by
    name pieces or a dict of pieces is caught;
  * `getattr`, `operator.attrgetter`/`methodcaller`, `importlib.import_module`, `__import__`
    or `spec_from_file_location` whose folded argument names one of them.
Docstrings are not code. PowerShell is scanned only where it launches the money path (a
script naming a MONEY_PATH module), with its comments removed.
"""
from __future__ import annotations

import ast
import itertools
import re
from pathlib import Path

from libs.ops.release import MONEY_PATH
from libs.portfolio.rails import RAILS

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

_LIB_MODULE = "libs.regime.control_room"
_LIB_FILE = (ROOT / "libs" / "regime" / "control_room.py").resolve()
_WEIGHT_NAMES = frozenset({"sleeve_weights", "kernel"})
#: The library's day-label readers: a signal conditioner a family may test like any feature.
_LABEL_NAMES = frozenset({"label_days", "daily_frame"})
_ORGANS = frozenset({"regime_allocation_contract", "control_room_mechanisms", "bench_bridge",
                     "practitioner_processes"})
_TOKENS = ("control_room", "regime_allocation_contract", "bench_bridge",
           "practitioner_processes", "sleeve_weights", "control_room_kernel")
_TOKEN_RE = re.compile("|".join(_TOKENS), re.IGNORECASE)
_DYNAMIC = frozenset({"import_module", "__import__", "getattr", "spec_from_file_location",
                      "attrgetter", "methodcaller"})
#: Directories that ARE the money path, walked whole.
_MONEY_DIRS = ("libs/execution", "libs/risk", "libs/portfolio", "desks/mt5/mt5desk")


# ------------------------------------------------------------------ what is walked
def _roots() -> list[str]:
    dirs = {str(Path(p).parent) for p in MONEY_PATH if p.startswith("libs/")}
    return sorted(set(MONEY_PATH) | set(_MONEY_DIRS) | dirs)


def _seed_files() -> set[Path]:
    out: set[Path] = set()
    for rel in _roots():
        p = ROOT / rel
        if p.is_file() and p.suffix == ".py":
            out.add(p)
        elif p.is_dir():
            out |= {f for f in p.rglob("*.py") if "__pycache__" not in f.parts}
    return out


def _module_file(dotted: str) -> Path | None:
    """The repository file a dotted import names, under the roots the desk's code imports from."""
    parts = dotted.split(".")
    for base in (ROOT, DESK):
        for cand in (base.joinpath(*parts).with_suffix(".py"),
                     base.joinpath(*parts) / "__init__.py"):
            if cand.is_file():
                return cand
    return None


def _imports(path: Path) -> set[Path]:
    try:
        tree = ast.parse(path.read_text("utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set[Path] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                f = _module_file(a.name)
                if f:
                    out.add(f)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                mod = base.joinpath(*(node.module or "").split(".")) if node.module else base
                for cand in [mod.with_suffix(".py"), mod / "__init__.py",
                             *[mod / f"{a.name}.py" for a in node.names]]:
                    if cand.is_file():
                        out.add(cand)
                continue
            for name in [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]:
                f = _module_file(name)
                if f:
                    out.add(f)
    return out


def money_path_closure() -> list[Path]:
    """The money path and everything inside this repository it imports, transitively."""
    seen: set[Path] = set()
    todo = list(_seed_files())
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        todo.extend(i for i in _imports(f) if i not in seen)
    return sorted(seen)


def _launcher_scripts() -> list[Path]:
    """PowerShell that launches a money-path module (names one of them)."""
    stems = {Path(m).name for m in MONEY_PATH}
    out = []
    for d in ("desks/mt5/scripts", "ops"):
        for p in sorted((ROOT / d).rglob("*.ps1")):
            text = _ps_code(p.read_text("utf-8", errors="replace"))
            if any(s.lower() in text for s in stems):
                out.append(p)
    return out


def _ps_code(src: str) -> str:
    """PowerShell with `<# #>` and `#` comments removed, lower-cased (strings kept)."""
    src = re.sub(r"<#.*?#>", "", src, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in src.splitlines()).lower()


# ------------------------------------------------------------------ constant folding
def _fold(node: ast.AST | None, env: dict[str, str]) -> str | None:
    """The string an expression builds from constants, or None when it is not decidable."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else (
            str(node.value) if isinstance(node.value, int) else None)
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                parts.append(_fold(v.value, env) or "")
            else:
                parts.append(_fold(v, env) or "")
        return "".join(parts)
    if isinstance(node, ast.BinOp):
        left, right = _fold(node.left, env), node.right
        if isinstance(node.op, ast.Add):
            r = _fold(right, env)
            return (left or "") + (r or "") if (left or r) else None
        if isinstance(node.op, ast.Mod) and left is not None:
            args = right.elts if isinstance(right, ast.Tuple) else [right]
            vals = tuple(_fold(a, env) or "" for a in args)
            try:
                return left % vals
            except (TypeError, ValueError):
                return left + "".join(vals)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        inner = _fold(node.value, env)
        step = node.slice.step
        if inner is not None and isinstance(step, ast.UnaryOp) and isinstance(step.op, ast.USub):
            return inner[::-1]
        return inner
    if isinstance(node, ast.Call):
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        args = [_fold(a, env) for a in node.args]
        if name == "format" and isinstance(f, ast.Attribute):
            base = _fold(f.value, env)
            if base is not None:
                try:
                    return base.format(*[a or "" for a in args])
                except (IndexError, KeyError, ValueError):
                    return base + "".join(a or "" for a in args)
        if name == "join" and isinstance(f, ast.Attribute) and node.args:
            sep = _fold(f.value, env) or ""
            seq = node.args[0]
            if isinstance(seq, (ast.List, ast.Tuple)):
                return sep.join(_fold(e, env) or "" for e in seq.elts)
            if isinstance(seq, ast.Call) and getattr(seq.func, "id", "") in ("map",) \
                    and len(seq.args) == 2 and getattr(seq.args[0], "id", "") == "chr" \
                    and isinstance(seq.args[1], (ast.List, ast.Tuple)):
                try:
                    return sep.join(chr(int(_fold(e, env) or "")) for e in seq.args[1].elts)
                except ValueError:
                    return None
        if name == "chr" and args and args[0] is not None:
            try:
                return chr(int(args[0]))
            except ValueError:
                return None
        if name == "decode" and isinstance(f, ast.Attribute):
            inner = f.value
            if isinstance(inner, ast.Call) and getattr(inner.func, "attr", "") == "fromhex":
                hexed = _fold(inner.args[0], env) if inner.args else None
                try:
                    return bytes.fromhex(hexed or "").decode("utf-8", "replace")
                except ValueError:
                    return None
        if name in ("str", "lower", "upper", "strip") and isinstance(f, ast.Attribute):
            return _fold(f.value, env)
        if name in ("joinpath", "Path") or (isinstance(f, ast.Name) and f.id == "Path"):
            return "/".join(a or "" for a in args) or None
    if isinstance(node, ast.Dict):
        return "".join(_fold(v, env) or "" for v in node.values)
    if isinstance(node, (ast.List, ast.Tuple)):
        return "".join(_fold(e, env) or "" for e in node.elts)
    return None


def _names_a_token(text: str | None) -> bool:
    if not text:
        return False
    return bool(_TOKEN_RE.search(text) or _TOKEN_RE.search(text[::-1]))


def _pieces_join_to_a_token(pieces: set[str]) -> bool:
    """Do 2-4 string pieces of one scope join (bare or with '_') into a token, in any order?"""
    cand = sorted({p.lower().strip("_*./") for p in pieces
                   if len(p.strip("_*./")) >= 3
                   and any(p.lower().strip("_*./") in t for t in _TOKENS)})
    if len(cand) < 2:
        return False
    cand = cand[:12]
    for n in (2, 3, 4):
        for combo in itertools.permutations(cand, n):
            for sep in ("", "_"):
                if any(t in sep.join(combo) for t in _TOKENS):
                    return True
    return False


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


# ------------------------------------------------------------------ the read
def reaches(src: str) -> list[str]:
    """Why this source reaches the control room's weights ([] when it does not)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["unparseable: cannot be shown not to reach"]
    why: list[str] = []
    docs = _docstrings(tree)
    env: dict[str, str] = {}
    lib_aliases: set[str] = set()
    # pass 1: bindings -- constants (folded in source order) and aliases of the library
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                last = a.name.split(".")[-1]
                if last in _ORGANS:
                    why.append(f"imports {a.name}")
                elif a.name == _LIB_MODULE or a.name == "regime.control_room":
                    lib_aliases.add(a.asname or a.name)
                elif last == "control_room":
                    why.append(f"imports {a.name} (the control-room organ)")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                if mod.split(".")[-1] in _ORGANS or a.name in _ORGANS:
                    why.append(f"imports from {mod or '.'} {a.name}")
                elif mod.endswith("control_room"):
                    if mod not in (_LIB_MODULE, "regime.control_room"):
                        why.append(f"imports from {mod} (the control-room organ)")
                    elif a.name not in _LABEL_NAMES:
                        why.append(f"from {mod} import {a.name}")
                elif a.name == "control_room":
                    if mod in ("libs.regime", "regime"):
                        lib_aliases.add(a.asname or a.name)
                    else:
                        why.append(f"from {mod} import control_room (the organ)")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name in _WEIGHT_NAMES:
            why.append(f"defines {node.name} (a copy of the weights)")
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            v = _fold(node.value, env)
            if v is not None:
                env[node.targets[0].id] = v
    # alias reassignment, to a fixed point
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Name, ast.Attribute)):
                src_name = ast.unparse(node.value)
                if src_name in lib_aliases:
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id not in lib_aliases:
                            lib_aliases.add(t.id)
                            changed = True
    # pass 2: uses
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = ast.unparse(node.value)
            if (base in lib_aliases or base == _LIB_MODULE) and node.attr not in _LABEL_NAMES:
                why.append(f"{base}.{node.attr}")
        elif isinstance(node, ast.Name) and node.id in lib_aliases \
                and isinstance(node.ctx, ast.Load):
            parent_attr = False
            for p in ast.walk(tree):
                if isinstance(p, ast.Attribute) and p.value is node:
                    parent_attr = True
                    break
            if not parent_attr:
                why.append(f"passes the control_room module around as {node.id}")
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _DYNAMIC:
                for a in node.args:
                    text = _fold(a, env)
                    if text and (_names_a_token(text) or text in _WEIGHT_NAMES
                                 or text.endswith("control_room")):
                        why.append(f"{name}({text[:60]!r})")
        if isinstance(node, ast.expr) and id(node) not in docs \
                and not isinstance(node, ast.Name):
            text = _fold(node, env)
            if _names_a_token(text):
                why.append(f"builds {text[:60]!r}")
    # pieces per scope (a function, a class, or the module body outside them)
    scopes: list[ast.AST] = [n for n in ast.walk(tree)
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for scope in [tree, *scopes]:
        pieces = {n.value for n in ast.walk(scope)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and id(n) not in docs}
        pieces |= set(env.values()) if scope is tree else set()
        if _pieces_join_to_a_token(pieces):
            why.append("string pieces in one scope join to a control-room name")
            break
    return sorted(set(why))


def violations(files: list[Path], rails=RAILS) -> list[str]:
    """Money-path files that reach the weights without a two-sided modifier and a rail line."""
    bad = []
    for f in files:
        real = f.resolve()
        if real == _LIB_FILE and real == f.absolute():
            # the library itself enters the closure through a day-label import; its
            # importers are judged by reaches(), which admits the label names only
            continue
        if real == _LIB_FILE or real.stem in _ORGANS or (
                real.stem == "control_room" and real.parent.name == "research"):
            why = [f"is (or links to) {real.name}"] if real != f.absolute() else [
                f"{real.name} is itself in the money path's closure"]
        elif f.suffix == ".ps1":
            text = _ps_code(f.read_text(encoding="utf-8", errors="replace"))
            why = [f"text {m.group(0)!r}" for m in _TOKEN_RE.finditer(text)]
        else:
            why = reaches(real.read_text(encoding="utf-8", errors="replace"))
        if not why:
            continue
        src = real.read_text(encoding="utf-8", errors="replace")
        two_sided = "capital_modifiers" in src
        billed = any(f.stem in r.where for r in rails)
        if not (two_sided and billed):
            rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
            bad.append(f"{rel}: {why[:3]} two_sided={two_sided} missed_growth_line={billed}")
    return bad


# ------------------------------------------------------------------ the fences
def test_the_walk_covers_every_money_path_directory_and_the_import_closure():
    files = {p.relative_to(ROOT).as_posix() for p in money_path_closure()}
    missing = [m for m in MONEY_PATH if m not in files and (ROOT / m).exists()]
    assert missing == []
    for d in _MONEY_DIRS:
        on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / d).rglob("*.py")
                   if "__pycache__" not in p.parts}
        assert on_disk and on_disk <= files, f"{d}: {sorted(on_disk - files)[:5]}"
    seeds = {p.relative_to(ROOT).as_posix() for p in _seed_files()}
    assert len(files) > len(seeds), "the import closure added nothing; the resolver broke"


def test_no_money_path_module_reads_control_room_weights_unbilled():
    assert violations(money_path_closure() + _launcher_scripts()) == []


def test_every_route_the_audit_named_is_a_reach():
    routes = {
        "plain": "from libs.regime.control_room import sleeve_weights\n",
        "alias_module": "import libs.regime.control_room as cr\nw = cr.kernel(a, b)\n",
        "alias_main": "import libs.regime.control_room as cr\ncr.main()\n",
        "bare_alias": "import control_room as cr\nw = cr.main()\n",
        "from_package": "from libs.regime import control_room as c\nc.kernel(p, n)\n",
        "multiline": "from libs.regime.control_room import (\n    label_days,\n    kernel,\n)\n",
        "dotted": "import libs.regime.control_room\nlibs.regime.control_room.kernel(p, n)\n",
        "reassigned": "from libs.regime import control_room as a\nb = a\nc = b\nc.kernel()\n",
        "passed_around": "from libs.regime import control_room as a\nuse(a)\n",
        "alloc_field": "k = alloc.get('control_room_kernel')\n",
        "importlib": "m = importlib.import_module('libs.regime.' + 'control_room')\n",
        "dunder": "m = __import__(f'libs.regime.{\"control_room\"}')\n",
        "getattr": "w = getattr(mod, 'sleeve_' + 'weights')\n",
        "attrgetter": "w = operator.attrgetter('kern' + 'el')(mod)\n",
        "methodcaller": "w = operator.methodcaller('sleeve_weights', 'X')(mod)\n",
        "fstring_report": "p = REPORTS / f'{name}_CONTROL_ROOM.json'\n",
        "concat_report": "p = str(R) + '/REGIME_ALLOCATION_CONTRACT.json'\n",
        "joinpath": "p = R.joinpath('reports', 'BENCH_BRIDGE.json')\n",
        "lower_glob": "ps = R.glob('control_room*.json')\n",
        "practitioner": "p = R / 'PRACTITIONER_PROCESSES.json'\n",
        "organ_import": "from research import regime_allocation_contract\n",
        "format": "p = '{}_{}.json'.format('control', 'room')\n",
        "percent": "p = '%s_room.json' % 'control'\n",
        "reversed": "p = 'moor_lortnoc'[::-1]\n",
        "chr": "exec(''.join(map(chr, [99, 111, 110, 116, 114, 111, 108, 95, 114, 111, 111, "
               "109])))\n",
        "hex": "n = bytes.fromhex('636f6e74726f6c5f726f6f6d').decode()\n",
        "named_constant": "A = 'control_'\nB = A + 'room'\nopen(B)\n",
        "other_function": "def a():\n    return 'control_'\ndef b():\n    return a() + 'room'\n",
        "dict_pieces": "P = {'x': 'control', 'y': '_room'}\nopen(''.join(P.values()))\n",
        "glob_by_pieces": "fs = [p for p in R.glob('*.json') if 'CONTROL' in p.name "
                          "and 'ROOM' in p.name]\n",
        "copied_kernel": "def kernel(prior, now, eps):\n    return prior\n",
        "copied_weights": "def sleeve_weights(symbol, dates):\n    return []\n",
    }
    missed = [k for k, src in routes.items() if not reaches(src)]
    assert missed == []


def test_day_labels_and_docstrings_are_not_a_reach():
    src = ('"""Conditions on libs.regime.control_room day labels."""\n'
           "from libs.regime.control_room import daily_frame, label_days\n"
           "from libs.regime import control_room as cr\n"
           "x = cr.label_days\n"
           "def f():\n    '''uses control_room labels'''\n    return label_days\n")
    assert reaches(src) == []


def test_a_transitive_reader_and_a_symlink_are_reaches(tmp_path, monkeypatch):
    helper = tmp_path / "helper.py"
    helper.write_text("from libs.regime.control_room import sleeve_weights\n", "utf-8")
    assert reaches(helper.read_text("utf-8"))
    link = tmp_path / "sizing_view.py"
    link.symlink_to(_LIB_FILE)
    assert violations([link]), "a symlink to the library is the library"


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


def test_powershell_that_launches_the_money_path_is_scanned_without_its_comments(tmp_path):
    f = tmp_path / "Run-Gateway.ps1"
    f.write_text("# reads CONTROL_ROOM.json? never\n& python gateway.py\n", encoding="utf-8")
    assert violations([f]) == []
    f.write_text("$k = Get-Content reports\\CONTROL_ROOM.json\n& python gateway.py\n",
                 encoding="utf-8")
    assert len(violations([f])) == 1
