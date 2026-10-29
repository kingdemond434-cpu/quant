#!/usr/bin/env python3
"""The replay-shadow job: the live E8 gold book, base against PR, over a fixed scenario grid.

Each scenario is one server day (a seeded price path, an account, an optional open position)
stepped through the hours where the book acts. ops/release/replay_child.py runs it once on the
base tree and once on the PR's tree, each in a fresh process and an empty directory, unarmed. The
PR PASSES only when every step decides the same thing on both: the windows placed and skipped,
every intended order (side, price, stop, target, lot, risk fraction and its source), every
management action, the guard's verdict and the sizing inputs. Prose (`why`, `sizing`) and
timestamps are not decisions and are left out.

A difference is not judged good or bad here: a PR that changes what the live book does is not
eligible for a merge with no human, so it FAILS and takes the manual path (CLEAR + APPROVE
MERGES). It also FAILS when:

- it changes a money-path file the replay never imported (the Fusion gateway, a data or state
  file, another book): nothing here measured it, and an unmeasured change is never a pass. The
  money path is DERIVED from the base, not listed by hand: the static import closure (an AST
  walk, nothing run) of every entry point the box's tasks run to size or place orders, plus the
  desk's books and state directories, plus every script that runs or names any of it
  (`money_scripts`; a script that names none is reported, not measured) (#457 audit MF2);
- it changes a module-level UPPER_CASE constant in a money-path file (a knob: a rail count, a
  margin, a grace) that ops/release/ceilings.json does not already bound. A grid exercises the
  knobs it reaches; this catches the ones it does not (#457 audit MF1);
- the base tree cannot run a scenario, or places nothing anywhere on the grid (UNMEASURED);
- the PR's tree raises where the base did not.

LIMIT: the PR's code runs in the child that writes its own result, so a PR written to fool this
check can. That is the reviewer's job (independent-review); this check catches regressions.

    python -I ops/release/replay_shadow.py --base <base tree> --head <PR tree> \
        --changed <file listing the PR's changed paths> [--report out.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHILD = HERE / "replay_child.py"
CEILINGS = HERE / "ceilings.json"
#: Always money path, whatever imports them.
MONEY_PATH = (
    "desks/mt5/mt5desk/", "desks/mt5/prop/", "desks/mt5/data/", "desks/mt5/scripts/",
    "desks/mt5/ops/", "data/", "libs/execution/", "libs/risk/", "libs/portfolio/",
)  # fmt: skip
#: What the box's tasks run to size or place orders (Install-QuantWindows.ps1,
#: install_e8_tasks.ps1, install_ftmo_follower_task.ps1). Their import closure is money path.
ENTRY_POINTS = (
    "desks/mt5/research/run_gateway_loop.py", "desks/mt5/research/gateway_resident.py",
    "desks/mt5/research/pf_allocator.py", "desks/mt5/proposals/fusion_deadman.py",
    "desks/mt5/prop/e8_executor.py", "desks/mt5/prop/e8_gold.py", "desks/mt5/prop/e8_book.py",
    "desks/mt5/prop/ftmo_follower.py",
)  # fmt: skip
#: SCRIPTS ARE MONEY PATH BY WHAT THEY RUN, NOT BY WHERE THEY SIT (2026-10-29). The replay only
#: imports Python, so a .ps1 under desks/mt5/scripts/ could never be "imported" and every change
#: to one was UNMEASURED forever (#439, a CRO lane installer that runs no order code). A script
#: under these directories is money path when its base OR PR text names a money-path Python file
#: (the import closure or an entry point, by file name or dotted module), a word of the venue
#: (MONEY_WORDS), or another money-path script, to a fixed point. Every other script is listed
#: as `not_money_scripts` in the report, never silently passed. Data, state and config files
#: under MONEY_PATH stay money path whatever they say.
SCRIPT_EXTS = (".ps1", ".psm1", ".cmd", ".bat", ".sh")
SCRIPT_DIRS = ("desks/mt5/scripts/", "desks/mt5/ops/")
MONEY_WORDS = re.compile(
    r"terminal64|metatrader|autotrading|mt5[-_]gateway|ftmo|fusion|\be8[-_]|order_send",
    re.IGNORECASE,
)
#: Where `import x` resolves on the box: the repository root and the desk.
IMPORT_ROOTS = ("", "desks/mt5")
KNOB = re.compile(r"^[A-Z][A-Z0-9_]*$")
#: Keys that carry prose or a wall-clock time, never a decision.
PROSE = frozenset(
    {
        "at",
        "why",
        "sizing",
        "alerts",
        "xacct_unpublished",
        "fusion_why",
        "detail",
        "note",
        "msg",
        "message",
    }
)
#: Server hours stepped each day: before, on and after every window's signal hour, and late.
HOURS = (0.5, 6.95, 7.03, 7.25, 8.0, 10.0, 13.03, 13.5, 15.0, 17.03, 17.5, 19.0, 21.5, 23.9)
SHAPES = ("range", "up_break", "down_break", "wide", "gap")
DAYS = ("2026-10-13", "2026-10-15")
TIMEOUT_S = 300


def _long(day: str, qty: float = 0.15) -> dict[str, Any]:
    from datetime import UTC, datetime

    opened = datetime.fromisoformat(day).replace(hour=7, minute=40, tzinfo=UTC)
    return {
        "id": 9001,
        "tradableInstrumentId": 6102,
        "side": "buy",
        "qty": qty,
        "avgPrice": 4310.0,
        "stopLossId": 9002,
        "openDate": int(opened.timestamp() * 1000),
    }


def scenarios() -> list[dict[str, Any]]:
    """The fixed grid: every shape x day x account. Deterministic, so both trees see the same."""
    out = []
    for day in DAYS:
        for shape in SHAPES:
            for acct, equity in (
                ("flat", 100_000.0),
                ("near_floor", 91_500.0),
                ("day_loss_edge", 98_310.0),
                ("profit_cap", 103_000.0),
                ("long_open", 100_000.0),
                ("heavy_open", 100_000.0),
                ("venue_refuses", 100_000.0),
                ("no_stop", 100_000.0),
                ("stale_tick", 100_000.0),
            ):
                sc: dict[str, Any] = {
                    "id": f"{day}/{shape}/{acct}",
                    "day": day,
                    "shape": shape,
                    "seed": len(out),
                    "equity": equity,
                    "hours": list(HOURS),
                }
                if acct == "day_loss_edge":  # down 1,690 today: the risk budget's margin binds
                    sc["guard"] = {"day_start": 100_000.0, "peak_equity": 100_000.0}
                if acct in ("long_open", "heavy_open", "venue_refuses"):
                    # heavy: the budget's margin binds; refuses: every stop move, cancel and
                    # close is refused, so the refusal rails run (#457 audit MF1)
                    sc["positions"] = [_long(day, 0.335 if acct == "heavy_open" else 0.15)]
                    sc["orders"] = [{"id": 9002, "stopPrice": 4270.0}]
                if acct in ("long_open", "venue_refuses", "no_stop"):  # the book owns it
                    sc["own"] = {
                        "placed_hour": 7.0, "hi": 4310.0, "lo": 4290.0, "position_id": 9001,
                        "shadow": False, "orders": {
                            "buy_stop": {"id": 8001, "price": 4310.0, "sl": 4270.0,
                                         "tp": 4390.0, "lot": 0.15},
                            "sell_stop": {"id": 8002, "price": 4290.0, "sl": 4330.0,
                                          "tp": 4210.0, "lot": 0.15}}}  # fmt: skip
                if acct == "venue_refuses":
                    sc["venue_ok"] = False
                if acct == "no_stop":  # a position the venue holds with no protective stop
                    sc["positions"] = [{**_long(day), "stopLossId": None}]
                if acct == "stale_tick":  # the terminal's clock lags the server by 3 hours
                    sc["tick_lag_s"] = 3 * 3600
                out.append(sc)
    return out


def _is_git(tree: Path) -> bool:
    return (tree / ".git").exists()


def tree_files(tree: Path) -> set[str]:
    """Every path the tree holds at HEAD (from git when it is a checkout, so a sparse or blobless
    checkout still answers), else from the disk."""
    if _is_git(tree):
        p = subprocess.run(
            ["git", "-C", str(tree), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
        return set(p.stdout.splitlines())
    out = set()
    for d, _, names in os.walk(tree):
        for n in names:
            out.add((Path(d) / n).relative_to(tree).as_posix())
    return out


def read(tree: Path, path: str) -> str | None:
    if _is_git(tree):
        p = subprocess.run(
            ["git", "-C", str(tree), "show", f"HEAD:{path}"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        return p.stdout if p.returncode == 0 else None
    f = tree / path
    return f.read_text("utf-8", errors="replace") if f.is_file() else None


def _module_files(dotted: str, files: set[str]) -> list[str]:
    parts = dotted.split(".")
    out = []
    for root in IMPORT_ROOTS:
        base = "/".join(x for x in (root, *parts) if x)
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            if cand in files:
                out.append(cand)
        for i in range(1, len(parts)):  # the packages on the way
            pkg = "/".join(x for x in (root, *parts[:i]) if x) + "/__init__.py"
            if pkg in files:
                out.append(pkg)
    return out


def import_closure(tree: Path, entries: tuple[str, ...] = ENTRY_POINTS) -> set[str]:
    """Every repository file the entry points can import, statically: `import` statements read
    by ast, never run. Dynamic imports are not seen; the MONEY_PATH directories cover those."""
    files = tree_files(tree)
    seen: set[str] = set()
    todo = [e for e in entries if e in files]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        try:
            node = ast.parse(read(tree, f) or "")
        except (SyntaxError, ValueError):
            continue
        pkg = Path(f).parent.as_posix().split("/")
        for root in IMPORT_ROOTS:  # the module's own dotted package, under its import root
            if root and f.startswith(root + "/"):
                pkg = Path(f[len(root) + 1 :]).parent.as_posix().split("/")
        names: list[str] = []
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                names += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                if n.level:
                    up = pkg[: len(pkg) - (n.level - 1)] if n.level > 1 else pkg
                    mod = ".".join(x for x in (*up, mod) if x and x != ".")
                names.append(mod)
                names += [f"{mod}.{a.name}" for a in n.names if mod]
        for name in names:
            todo += [m for m in _module_files(name, files) if m not in seen]
    return seen


def is_script(path: str) -> bool:
    return path.startswith(SCRIPT_DIRS) and path.lower().endswith(SCRIPT_EXTS)


_BLOCK_COMMENT = re.compile(r"<#.*?#>", re.DOTALL)
_LINE_COMMENT = re.compile(r"^[ \t]*(?:#|rem\b|::).*$", re.IGNORECASE | re.MULTILINE)


def _code(src: str) -> str:
    """A script's text without its comments, lower-cased: prose that mentions the venue runs
    nothing. A `#` after code on the same line is kept (it may sit inside a string)."""
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", src)).lower()


def _names_any(text: str, names: set[str]) -> bool:
    """Any name as a whole path segment or module (`\\e8_gold.py`, `-m mt5desk.gateway`), never
    as the tail of a longer name (`backup.py` inside `offsite_backup.py`)."""
    return any(re.search(r"(?<![\w.-])" + re.escape(n) + r"(?![\w])", text) for n in names)


def money_scripts(trees: tuple[Path, ...], closure: set[str]) -> set[str]:
    """The scripts under SCRIPT_DIRS that run, or name, the money path in ANY of `trees` (the base
    and the PR: a script that was money path stays so whatever the PR rewrites it to)."""
    py = {*closure, *ENTRY_POINTS}
    names = {Path(f).name.lower() for f in py if Path(f).name != "__init__.py"}
    for f in py:  # `-m mt5desk.gateway` as well as `mt5desk\gateway.py`
        for root in IMPORT_ROOTS:
            if root and f.startswith(root + "/"):
                f = f[len(root) + 1 :]
        dotted = f[:-3].replace("/", ".").lower()
        if f.endswith(".py") and not f.endswith("__init__.py") and "." in dotted:
            names.add(dotted)  # package-qualified only: a bare `config` is in every script
    text: dict[str, str] = {}
    for tree in trees:
        for f in tree_files(tree):
            if is_script(f):
                text[f] = text.get(f, "") + "\n" + _code(read(tree, f) or "")
    money = {f for f, t in text.items() if MONEY_WORDS.search(t) or _names_any(t, names)}
    while True:  # a script that calls a money-path script is one
        called = {Path(f).name.lower() for f in money}
        more = {f for f, t in text.items() if f not in money and _names_any(t, called)}
        if not more:
            return money
        money |= more


def is_money(path: str, closure: set[str], scripts: set[str] | None = None) -> bool:
    if scripts is not None and is_script(path):
        return path in scripts
    return path.startswith(MONEY_PATH) or path in closure


def knobs(src: str) -> dict[str, list[str]]:
    """{name: [ast of every value it is given]} for the knobs a file sets: module-level and
    class-level UPPER_CASE names (`Class.NAME`), and every function's parameter defaults
    (`f(arg=)`, `Class.f(arg=)`), since a rail can move through any of them (#457 audit)."""
    out: dict[str, list[str]] = {}

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for n in body:
            if isinstance(n, ast.ClassDef):
                walk(n.body, f"{prefix}{n.name}.")
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = n.args
                pos = [*a.posonlyargs, *a.args]
                pairs = list(zip(pos[len(pos) - len(a.defaults) :], a.defaults, strict=True))
                pairs += [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults, strict=True) if d]
                for arg, default in pairs:
                    out.setdefault(f"{prefix}{n.name}({arg.arg}=)", []).append(ast.dump(default))
                walk(n.body, f"{prefix}{n.name}.")  # nested functions' defaults too
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                # a constant set inside a guard is still a knob
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(n, part, None) or [], prefix)
                for h in getattr(n, "handlers", None) or []:
                    walk(h.body, prefix)
            elif isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Name) and KNOB.match(t.id):
                        out.setdefault(f"{prefix}{t.id}", []).append(ast.dump(n.value))

    walk(ast.parse(src).body, "")
    return out


def bounded() -> dict[str, set[str]]:
    """{file: names ops/release/ceilings.json already holds to a ceiling}."""
    doc = json.loads(CEILINGS.read_text("utf-8"))
    out: dict[str, set[str]] = {}
    for kind in ("max", "equal"):
        for f, names in (doc.get(kind) or {}).items():
            out.setdefault(f, set()).update(names)
    for f, name in (doc.get("superset") or {}).items():
        out.setdefault(f, set()).add(name)
    return out


def knob_changes(base: Path, head: Path, changed: list[str], closure: set[str]) -> list[str]:
    problems = []
    held = bounded()
    for f in changed:
        if not f.endswith(".py") or not is_money(f, closure):
            continue
        try:
            was = knobs(read(base, f) or "")
            now = knobs(read(head, f) or "")
        except SyntaxError as exc:
            problems.append(f"{f}: cannot be parsed ({exc.msg}); its knobs are unmeasured")
            continue
        for name in sorted(set(was) | set(now)):
            if was.get(name) != now.get(name) and name not in held.get(f, set()):
                problems.append(
                    f"{f}: the money-path knob {name} changed; knobs the ceilings do not bound "
                    "take the manual path"
                )
    return problems


def canon(value: Any) -> Any:
    """The decision content of a value: prose keys, `*_at` keys and free text dropped."""
    if isinstance(value, dict):
        return {
            k: canon(v)
            for k, v in sorted(value.items())
            if k not in PROSE and not str(k).endswith("_at")
        }
    if isinstance(value, list):
        return [canon(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str) and len(value) > 48 and " " in value:
        return "<text>"
    return value


def decisions(step: dict[str, Any]) -> dict[str, Any]:
    doc = step.get("doc") or {}
    guard = doc.get("guard_decision") or {}
    return canon(
        {
            "error": (step.get("error") or "").split(":", 1)[0] or None,
            "status": doc.get("status"),
            "placed": doc.get("placed"),
            "actions": doc.get("actions"),
            "skipped": sorted(
                str(s.get("window")) for s in doc.get("skipped") or [] if isinstance(s, dict)
            ),
            "sizing_source": doc.get("sizing_source"),
            "kelly_risk": doc.get("kelly_risk"),
            "cert_ceiling": doc.get("e8_cert_ceiling"),
            "risk_usd": doc.get("risk_usd"),
            "guard": {k: guard.get(k) for k in ("verdict", "flatten", "may_open")},
            "committed_usd": (doc.get("committed_risk") or {}).get("total_usd"),
            "windows": ((doc.get("state") or {}).get("windows")),
            "intents": step.get("intents"),
        }
    )


def run_tree(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
    """One scenario on one tree, in a fresh process and an empty directory."""
    with tempfile.TemporaryDirectory(prefix=secrets.token_hex(4)) as tmp:
        work = Path(tmp)
        (work / "scenario.json").write_text(json.dumps(sc), "utf-8")
        out = work / "out.json"
        try:
            p = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(CHILD),
                    str(tree.resolve()),
                    str(work / "scenario.json"),
                    str(out),
                ],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"crash": f"timed out after {TIMEOUT_S}s"}
        if p.returncode != 0 or not out.exists():
            return {"crash": f"rc {p.returncode}: {(p.stderr or p.stdout)[-600:]}"}
        return json.loads(out.read_text("utf-8"))


def compare(
    base: Path, head: Path, changed: list[str], grid: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    grid = scenarios() if grid is None else grid
    # fresh fingerprints each run, the same for both trees: fooling the replay needs code that
    # hunts for the harness, which the reviewer's rule 5 names (#457 audit should-fix)
    who = {"account_id": 10_000 + secrets.randbelow(89_999_999), "server": secrets.token_hex(5)}
    grid = [{**who, **sc} for sc in grid]
    problems: list[str] = []
    imported: set[str] = set()
    placed = 0
    for sc in grid:
        b, h = run_tree(base, sc), run_tree(head, sc)
        if "crash" in b:
            problems.append(f"UNMEASURED {sc['id']}: the base tree cannot run it ({b['crash']})")
            continue
        if "crash" in h:
            problems.append(f"{sc['id']}: the PR's tree crashed ({h['crash']})")
            continue
        base_root = str(base.resolve())
        imported.update(
            Path(f).relative_to(base_root).as_posix()
            for f in b["imported"]
            if f.startswith(base_root + "/")
        )
        for bs, hs in zip(b["steps"], h["steps"], strict=True):
            if bs.get("error"):
                problems.append(f"UNMEASURED {sc['id']} @{bs['hour']}: base raised {bs['error']}")
                continue
            placed += sum(1 for r in bs.get("intents") or [] if isinstance(r, dict))
            db, dh = decisions(bs), decisions(hs)
            if db != dh:
                keys = sorted(k for k in db if db.get(k) != dh.get(k))
                was = json.dumps({k: db.get(k) for k in keys})[:400]
                now = json.dumps({k: dh.get(k) for k in keys})[:400]
                problems.append(
                    f"{sc['id']} @{bs['hour']}: the PR decides differently on "
                    f"{', '.join(keys)}: base {was} PR {now}"
                )
    if not placed:
        problems.append("UNMEASURED: the base tree placed nothing anywhere on the grid")
    closure = import_closure(base)
    scripts = money_scripts((base, head), closure)
    uncovered = sorted(f for f in changed if is_money(f, closure, scripts) and f not in imported)
    not_money = sorted(f for f in changed if is_script(f) and f not in scripts)
    problems += [
        f"UNMEASURED money-path change (the replay never imported it): {f}" for f in uncovered
    ]
    problems += knob_changes(base, head, changed, closure)
    return {
        "verdict": "FAIL" if problems else "PASS",
        "scenarios": len(grid),
        "steps": len(grid) * len(HOURS),
        "intents_compared": placed,
        "problems": problems,
        # changed scripts that name no money-path file, venue word or money-path script
        "not_money_scripts": not_money,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--changed", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args(argv)
    changed = [x.strip() for x in a.changed.read_text("utf-8").splitlines() if x.strip()]
    rep = compare(a.base, a.head, changed)
    if a.report:
        a.report.write_text(json.dumps(rep, indent=1), "utf-8")
    print(
        f"REPLAY-SHADOW {rep['verdict']}: {rep['scenarios']} scenarios, {rep['steps']} steps, "
        f"{rep['intents_compared']} intended orders compared"
    )
    for p in rep["problems"][:200]:
        print(" -", p)
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
