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
  desk's books and state directories, plus every script under desks/mt5/scripts/ and ops/
  except the reviewed exceptions in ops/release/not_money_scripts.txt (`money_scripts`, fail
  closed) (#457 audit MF2, #508 audit);
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
import unicodedata
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
#: SCRIPTS: MONEY PATH UNLESS SHOWN OTHERWISE (2026-10-29; #508 audit HOLD on a text scan that
#: failed OPEN). Every shell script and stand-alone Python tool under SCRIPT_DIRS is money path
#: (the replay imports only Python, so a change to one reads UNMEASURED: the manual path). The
#: one way out is a REVIEWED exception: listed in ops/release/not_money_scripts.txt, read from
#: THIS checkout (the base's, PROTECTED: a PR can never list itself), and then only while
#:   - neither the base's nor the PR's text, raw (comments too: stripping can only remove money),
#:     names a money-path module or package (any form: file, stem, dotted, package-prefixed),
#:     a venue word (MONEY_WORDS), a state or switch file the money path reads (derived from the
#:     closure's own string literals, plus STATE_WORDS), or a money-path script;
#:   - the PR adds no line of dynamic execution (DYNAMIC) the reviewed base did not have;
#:   - no money-path script calls, sources or names it (the callee direction);
#:   - it can be read in every tree it is in (a read failure is money path).
SCRIPT_EXTS = (".ps1", ".psm1", ".cmd", ".bat", ".sh")
SCRIPT_DIRS = ("desks/mt5/scripts/", "desks/mt5/ops/")
NOT_MONEY = HERE / "not_money_scripts.txt"
MONEY_WORDS = re.compile(
    r"terminal64|metatrader|autotrading|mt5[-_]?gateway|ftmo|fusion|(?<![a-z0-9])e8(?![0-9])"
    r"|order_send|order_check|positions_get",
    re.IGNORECASE,
)
#: The floor of switch and book names; `state_names` adds every file and flag name the closure's
#: own code spells out.
STATE_WORDS = re.compile(
    r"sleeves\.json|gateway_state|gateway_paused|cashcarry_kill|deadman|freeze|live_door"
    r"|sleeve_registry|account_state|retired|minlot|min_lot|sovereign|release_stop|kill",
    re.IGNORECASE,
)
#: A line that can run something no scan can name: indirect calls, encoded or evaluated text,
#: task starts, sourcing, and Python's dynamic import and process calls.
DYNAMIC = re.compile(
    r"invoke-expression|\biex\b|-enc(odedcommand)?\b|-e\s+[a-z0-9+/=]{20,}|start-process|start-job"
    r"|invoke-command|start-scheduledtask|register-scheduledtask|schtasks|\bcall\b|^\s*\.\s"
    r"|\bsource\b|importlib|__import__|runpy|\bexec\s*\(|\beval\s*\(|subprocess|os\.system"
    r"|os\.popen|os\.exec|os\.spawn|&\s*[$(\"']|cmd(\.exe)?\s+/[ck]|powershell(\.exe)?\s"
    r"|pwsh(\.exe)?\s|python\S*\s+-[cm]\b|sys\.path"
    # #508 v2 audit
    r"|scriptblock|invokescript|invoke-item|(set|disable|unregister)-scheduledtask|stop-process"
    r"|getattr\s*\(|__builtins__|\bcompile\s*\(|pickle|posix_spawn|\bpty\b|from\s+os\s+import",
    re.IGNORECASE | re.MULTILINE,
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
            capture_output=True, check=False,
        )  # fmt: skip
        return _text(p.stdout) if p.returncode == 0 else None
    f = tree / path
    return _text(f.read_bytes()) if f.is_file() else None


def _text(raw: bytes) -> str:
    """Any encoding reads (#508 audit: a UTF-16 script crashed the run): undecodable bytes are
    replaced, NULs dropped and the text NFKC-normalised, so every scan sees plain words."""
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    return unicodedata.normalize("NFKC", text)  # fullwidth letters read as ASCII


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
    """A shell script or a stand-alone Python tool under SCRIPT_DIRS."""
    return path.startswith(SCRIPT_DIRS) and path.lower().endswith((*SCRIPT_EXTS, ".py"))


def listed_not_money(path: Path = NOT_MONEY) -> set[str]:
    """The reviewed exceptions: one repo path per line, `#` starts a comment (the why)."""
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return set()
    return {ln.split("#", 1)[0].strip() for ln in lines if ln.split("#", 1)[0].strip()}


def state_names(tree: Path, closure: set[str]) -> set[str]:
    """Every file or flag name the money path's own code spells out: string literals that end in
    a data extension (by base name and stem), and UPPER_SNAKE names a flag file may carry."""
    out: set[str] = set()
    for f in closure:
        try:
            node = ast.parse(read(tree, f) or "")
        except (SyntaxError, ValueError):
            continue
        for n in ast.walk(node):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                continue
            v = n.value.strip()
            base = re.split(r"[\\/]", v)[-1]
            m = re.fullmatch(r"([\w.-]+)\.(json|jsonl|csv|parquet|flag|lock|txt|ya?ml)", base)
            if m and len(m.group(1)) >= 4:
                out |= {base.lower(), m.group(1).lower()}
            elif re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)+", v) and len(v) >= 6:
                out.add(v.lower())
    return out


def _names_any(text: str, names: set[str]) -> bool:
    """Any name as a whole word or path segment, never as the tail of a longer one (`backup.py`
    inside `offsite_backup.py`); `.` and `\\` around it are separators, so `mt5desk.gateway`,
    `from mt5desk import gateway` and `scripts\\x` all count."""
    return any(re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", text) for n in names)


def _money_names(tree: Path, closure: set[str]) -> set[str]:
    """How a script can name the money path's Python: file, stem, every dotted suffix and
    package-prefixed form, and each package directory the closure imports through."""
    names: set[str] = set()
    for f in {*closure, *ENTRY_POINTS}:
        p = Path(f)
        if p.name == "__init__.py":
            names.add(p.parent.name.lower())
            continue
        names |= {p.name.lower(), p.stem.lower()}
        parts = f[:-3].lower().split("/")
        names |= {".".join(parts[i:]) for i in range(len(parts) - 1)}
    return {n for n in names if len(n) >= 3}


def money_scripts(
    trees: tuple[Path, ...], closure: set[str], listed: set[str] | None = None
) -> set[str]:
    """The scripts under SCRIPT_DIRS that are money path in `trees` (the base first, then the
    PR): all of them but the listed exceptions that pass every test in the note above."""
    listed = listed_not_money() if listed is None else listed
    files = {t: tree_files(t) for t in trees}
    scripts = {f for t in trees for f in files[t] if is_script(f)}
    names = _money_names(trees[0], closure)
    states = state_names(trees[0], closure)
    text: dict[str, list[str]] = {}
    money: set[str] = set()
    for f in sorted(scripts):
        got = []
        for t in trees:
            if f in files[t]:
                x = read(t, f)
                if x is None:  # unreadable (a lazy blob on a blobless checkout): money path
                    money.add(f)
                got.append((x or "").lower())
        text[f] = got
    stems = {f: {Path(f).name.lower(), Path(f).stem.lower()} for f in scripts}
    for f in scripts - money:
        if f not in listed or f in closure or f in ENTRY_POINTS:
            money.add(f)
            continue
        got = text[f]
        in_base = f in files[trees[0]]
        base_lines = (
            {ln.strip() for ln in got[0].splitlines() if DYNAMIC.search(ln)} if in_base else set()
        )
        dyn = {ln.strip() for x in got for ln in x.splitlines() if DYNAMIC.search(ln)}
        if (
            any(MONEY_WORDS.search(x) or STATE_WORDS.search(x) for x in got)
            or any(_names_any(x, names | states) for x in got)
            or dyn - base_lines  # dynamic execution the reviewed base did not have
        ):
            money.add(f)
    while True:  # a listed script that names or is named by a money-path script is one
        free = scripts - money
        more = {
            f for f in free
            if any(_names_any(x, set().union(*(stems[m] for m in money))) for x in text[f])
            or any(_names_any(x, stems[f]) for m in money for x in text[m])
        }  # fmt: skip
        if not more:
            return money
        money |= more


def exempt_scripts(
    trees: tuple[Path, ...], closure: set[str], listed: set[str] | None = None
) -> set[str]:
    """The scripts in `trees` that are NOT money path: the only way out for a script. A script
    any caller never showed here (one added only in a tree it did not pass) stays money."""
    scripts = {f for t in trees for f in tree_files(t) if is_script(f)}
    return scripts - money_scripts(trees, closure, listed)


#: The box's task table. A data file under MONEY_PATH, so any change to it is money path, unless
#: every line it changes is a TASK row that names nothing money (manifest_is_money): the rows for
#: the gate's own clocks (the sign train, the sweep's helpers) are not order code.
MANIFEST = "desks/mt5/ops/box_tasks.manifest"
_ATTR = re.compile(r'(\w+)="([^"]*)"')
#: The only path a free row may name: repo-relative, plain (no `..`, `.`, `%VAR%`, `$x`, drive,
#: backslash, quote or space), so the string compared here is the file the box runs (#508 v3 MF1).
_PLAIN_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*")
#: Lanes whose rows may change without the manual path; money and prop rows never do (v3 MF3).
_FREE_LANES = frozenset({"ops", "research", "data"})
COMPONENTS = "desks/mt5/ops/components.py"


def _held_tasks(tree: Path) -> set[str] | None:
    """components.REQUIRED_TASKS and TASK_CANONICAL's keys, read by ast from `tree` (None when
    unreadable): the control plane's own rows, which never change as free rows."""
    try:
        node = ast.parse(read(tree, COMPONENTS) or "")
    except (SyntaxError, ValueError):
        return None
    out: set[str] = set()
    for n in node.body:
        if isinstance(n, ast.AnnAssign) and n.value is not None:
            target, v = n.target, n.value
        elif isinstance(n, ast.Assign) and len(n.targets) == 1:
            target, v = n.targets[0], n.value
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        try:
            if target.id == "REQUIRED_TASKS" and isinstance(v, ast.Call) and v.args:
                out |= {str(x) for x in ast.literal_eval(v.args[0])}
            elif target.id == "TASK_CANONICAL":
                out |= {str(x) for x in ast.literal_eval(v)}
        except ValueError:
            return None
    return out or None


def manifest_is_money(
    base: Path, head: Path, closure: set[str], money: set[str], exempt: set[str]
) -> bool:
    """Whether the change to MANIFEST is money path. Comments and blank lines are prose. Every
    other added or removed line must be a TASK row whose raw text names no venue, state or
    money-path name, and whose runs, also_runs and installer are each a file that is not money
    path (a script under SCRIPT_DIRS only when `exempt` clears it). Anything else, or a tree
    that cannot be read, is money (fail closed)."""
    b, h = read(base, MANIFEST), read(head, MANIFEST)
    if b is None or h is None:
        return True

    def rows(text: str) -> list[str]:
        return [
            x.strip() for x in text.splitlines() if x.strip() and not x.lstrip().startswith("#")
        ]

    was, now = rows(b), rows(h)
    changed = [x for x in now if x not in was] + [x for x in was if x not in now]
    if len(was) != len(now) and not changed:  # a row duplicated or dropped twice over
        return True
    # a package directory's bare name ("ops", "data") is no name here: every row's lane and path
    # use those words, and a path inside such a package is caught below, file by file
    dirs = {Path(f).parent.name.lower() for f in closure} - {
        Path(f).stem.lower() for f in {*closure, *ENTRY_POINTS} if Path(f).name != "__init__.py"
    }
    names = (_money_names(base, closure) - dirs) | state_names(base, closure)
    names |= {n for m in money for n in (Path(m).name.lower(), Path(m).stem.lower())}
    held = _held_tasks(base)
    if held is None:
        return True
    held_cf = {t.casefold() for t in held}

    def names_in(rows_: list[str]) -> list[str]:
        return [dict(_ATTR.findall(x)).get("name", "").casefold() for x in rows_]

    in_was, in_now = names_in(was), names_in(now)
    for line in changed:
        low = line.lower()
        if not line.startswith("TASK "):
            return True
        if MONEY_WORDS.search(low) or STATE_WORDS.search(low) or _names_any(low, names):
            return True
        attrs = dict(_ATTR.findall(line))
        name = attrs.get("name", "").casefold()
        # a row of a money or prop lane, or of the control plane, never changes freely (v3 MF3)
        if not name or attrs.get("lane") not in _FREE_LANES or name in held_cf:
            return True
        # one row per name, any case, in each tree: a second row rebinds that task (v3 MF2)
        if in_was.count(name) > 1 or in_now.count(name) > 1:
            return True
        paths = [p.strip() for k in ("runs", "also_runs", "installer")
                 for p in attrs.get(k, "").split(",") if p.strip()]  # fmt: skip
        for p in paths:
            if not _PLAIN_PATH.fullmatch(p) or any(seg in ("", ".", "..") for seg in p.split("/")):
                return True  # only a plain repo path is compared as the file it names (v3 MF1)
            if p in closure or p in ENTRY_POINTS or p.startswith(MONEY_PATH) or p in money:
                return True
            if is_script(p) and p not in exempt:
                return True
    return False


def is_money(path: str, closure: set[str], *, exempt: set[str] | None = None) -> bool:
    """A script under SCRIPT_DIRS is money unless `exempt` names it (fail closed, #508 audit)."""
    if is_script(path):
        return path not in (exempt or set())
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


def knob_changes(
    base: Path, head: Path, changed: list[str], closure: set[str], exempt: set[str] | None = None
) -> list[str]:
    problems = []
    held = bounded()
    for f in changed:
        if not f.endswith(".py") or not is_money(f, closure, exempt=exempt):
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
    exempt = exempt_scripts((base, head), closure)
    money = money_scripts((base, head), closure)
    rows_only = MANIFEST in changed and not manifest_is_money(base, head, closure, money, exempt)
    uncovered = sorted(
        f for f in changed
        if is_money(f, closure, exempt=exempt) and f not in imported
        and not (f == MANIFEST and rows_only)
    )  # fmt: skip
    not_money = sorted(f for f in changed if is_script(f) and f in exempt)
    problems += [
        f"UNMEASURED money-path change (the replay never imported it): {f}" for f in uncovered
    ]
    problems += knob_changes(base, head, changed, closure, exempt)
    return {
        "verdict": "FAIL" if problems else "PASS",
        "scenarios": len(grid),
        "steps": len(grid) * len(HOURS),
        "intents_compared": placed,
        "problems": problems,
        # changed scripts that are reviewed exceptions (ops/release/not_money_scripts.txt)
        "not_money_scripts": not_money,
        # the manifest changed only in TASK rows that name nothing money (manifest_is_money)
        "not_money_manifest": rows_only,
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
