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

THE FUSION ROSTER (2026-11-14, Auditor MF1-MF5 on the Governance design). The two roster data
files (ROSTER_FILES) are covered only by the child's Fusion-roster leg: rows derived from BOTH
trees' names and the frozen base grid (ops/release/fusion_roster_grid.json), the same rows on both
trees, every door's outcome compared. A file is covered only where the leg reaches every change
in it (roster_unmeasured: MF6 policy keys and resolved values, MF7 venue blocks only). A missing
or failed leg on either tree is UNMEASURED; a PR
that touches the grid or the leg (ROSTER_HARNESS) FAILS; diffs are printed as kind, symbol and a
sanitised row name, never free text. When the ONLY problem is that rows flip between admitted and
refused, and the flips equal exactly one declared row for this PR number and this full head sha in
the registry at $QUANT_EXPECTED_DIVERGENCE (every refusal carrying its missed_growth line), the
verdict is MATCHES_DECLARED: still a non-zero exit, never a PASS. Any other divergence FAILS.

LIMIT: the PR's code runs in the child that writes its own result, so a PR written to fool this
check can. That is the reviewer's job (independent-review); this check catches regressions.

    python -I ops/release/replay_shadow.py --base <base tree> --head <PR tree> \
        --changed <file listing the PR's changed paths> [--report out.json]
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Callable
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
#: The Fusion roster's data, covered only by the child's roster leg (never by an import).
ROSTER_FILES = ("desks/mt5/data/live_sleeve_policy.json", "desks/mt5/data/CERT_BOOK_LIVE.json")
#: The leg and its frozen grid: a PR touching either can no longer be measured by them (MF2).
ROSTER_HARNESS = ("ops/release/fusion_roster_grid.json", "ops/release/replay_child.py")
ROSTER_GRID = HERE / "fusion_roster_grid.json"
#: A row name that may be printed: no spaces, no paths, no prose (MF5).
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.#=-]{1,96}$")
_BOOK_KEY = re.compile(r"^([A-Z]{6})_([a-z0-9_]+)_([a-z]+)$")
DECLARED_ENV = "QUANT_EXPECTED_DIVERGENCE"
MATCHES_DECLARED = "MATCHES_DECLARED"


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


#: POWERSHELL INSTALLERS, JUDGED STATICALLY (Governance ruling 2026-11-17 18:25Z, option (a)).
#: The replay imports only Python, so a new box task installer under SCRIPT_DIRS read UNMEASURED
#: for ever (#1230). An installer is MEASURED, with its own text as the evidence, only when every
#: script its code names is a target the replay already vouches for: an ENTRY_POINT, a Python file
#: the replay imported, or a row of INSTALLER_TARGETS below. Its code (comments stripped) must
#: register a scheduled task, name no venue or switch word, and run nothing dynamic beyond the
#: scheduled-task verbs. Anything else stays UNMEASURED (fail closed). The allowlist lives HERE,
#: in the harness (the base's checkout), so a PR can never vouch for its own target.
INSTALLER_TARGETS = (
    "scripts/run_alerts.py",  # the pager: reads reports and pages; no order, sizing or switch
    "desks/mt5/scripts/stall_watch.ps1",  # the stall watcher: task health and re-enables
)  # fmt: skip
#: What an installer may do that DYNAMIC reads as dynamic: the scheduled-task verbs, and finding
#: the interpreter by name (`(Get-Command python ...).Source`, a property, not `source`-ing).
#: CONDITIONAL TARGETS (Governance 2026-11-17 18:45Z): a Python target vouched for only while its
#: own text passes a static rule run here, on the PR's tree. ops/box_self_heal.py may stop and
#: start tasks, and only literal names from SELF_HEAL_TASKS; any other action unvouches it.
SELF_HEAL = "ops/box_self_heal.py"
#: The tasks the self-healer may /End or /Run. Never a gateway, terminal, promoter or order task:
#: SELF_HEAL_FORBIDDEN refuses such a name at run time, and a base test pins the exclusion.
SELF_HEAL_TASKS = frozenset({"MT5-IndependenceIntake", "Quant-WorkflowGate"})
SELF_HEAL_FORBIDDEN = re.compile(
    r"gateway|terminal|promot|deadman|e8|ftmo|fusion|order|sizing|alloc|sleeve|prop|"
    r"executor|follower|window.?guard|adopt|release|seal",
    re.IGNORECASE,
)
#: The only modules it may load by path (_load(name, _dep(<file>, <repo path>))).
SELF_HEAL_DEPS = frozenset({"ops/process_health.py", "libs/ops/alert_channels.py"})
_SCHTASKS_VERBS = frozenset({"/Query", "/End", "/Run"})
_BANNED_CALLS = frozenset({
    "os.system", "os.startfile", "os.popen", "os.execv", "os.execve", "os.execl", "os.execlp",
    "os.execvp", "os.spawnl", "os.spawnv", "os.posix_spawn", "subprocess.Popen",
    "subprocess.call", "subprocess.check_call", "subprocess.check_output", "eval", "exec",
    "__import__", "runpy.run_path", "runpy.run_module", "importlib.import_module",
})  # fmt: skip
_TASK_EDIT = re.compile(
    r"(register|unregister|set|new)-scheduledtask|/create\b|/delete\b|/change\b",
    re.IGNORECASE,
)


def _dotted(node: ast.AST) -> str:
    """`a.b.c` for a Name/Attribute chain, else ''."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _literal_strs(node: ast.AST | None) -> set[str] | None:
    """The strings of `frozenset({...})`/`{...}`/`(...)` of literals, else None (not literal)."""
    if isinstance(node, ast.Call) and _dotted(node.func) in {"frozenset", "set"} and node.args:
        node = node.args[0]
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        out = set()
        for e in node.elts:
            if not (isinstance(e, ast.Constant) and isinstance(e.value, str)):
                return None
            out.add(e.value)
        return out
    return None


#: A process launch through the Win32 API (ctypes), which no Python-level ban sees.
_NATIVE_LAUNCH = re.compile(r"createprocess|shellexecute|winexec|createremotethread", re.IGNORECASE)
_GUARDED_MODULES = frozenset(
    {"subprocess", "os", "importlib", "runpy", "ctypes", "multiprocessing"}
)
#: The one guard _schtasks must open with (after `allowed = {...}`), compared as an AST.
_SCHTASKS_GUARD = ast.dump(
    ast.parse("verb not in allowed or task not in allowed[verb]", mode="eval").body
)


#: #1249 audit HOLD 3: the self-healer is judged against an ALLOWLIST, never a banlist. The only
#: modules it may import (`import X`), the only `from` imports, and for each imported module the
#: only attributes it may reach (None: any, for modules with no way to start a process).
_HEAL_IMPORTS = frozenset({
    "argparse", "contextlib", "csv", "ctypes", "importlib.util", "io", "json", "ntpath", "os",
    "psutil", "re", "shlex", "socket", "stat", "subprocess", "sys", "tempfile", "time",
})  # fmt: skip
_HEAL_FROM: dict[str, frozenset[str] | None] = {
    "__future__": None, "collections.abc": None, "dataclasses": None, "datetime": None,
    "pathlib": None, "typing": None, "ctypes": frozenset({"wintypes"}),
}  # fmt: skip
_HEAL_ATTRS: dict[str, frozenset[str] | None] = {
    "argparse": None, "contextlib": None, "csv": None, "io": None, "json": None, "ntpath": None,
    "re": None, "shlex": None, "stat": None, "time": None, "wintypes": None,
    "os": frozenset({"path", "environ", "getenv", "getpid", "replace", "makedirs", "stat",
                     "lstat", "fdopen"}),
    "subprocess": frozenset({"run", "TimeoutExpired"}),
    "psutil": frozenset({"Process", "process_iter", "wait_procs", "NoSuchProcess",
                         "AccessDenied"}),
    "socket": frozenset({"gethostname"}),
    "sys": frozenset({"exit", "platform", "argv", "stdout", "stderr", "modules"}),
    "tempfile": frozenset({"mkstemp"}),
    "importlib": frozenset({"util"}),
    "ctypes": frozenset({"POINTER", "Structure", "WinDLL", "byref", "c_int", "c_ubyte",
                         "c_void_p", "c_wchar_p", "cast", "create_string_buffer",
                         "create_unicode_buffer", "get_last_error", "sizeof", "windll"}),
}  # fmt: skip
#: Full chains pinned below a module's first attribute.
_HEAL_CHAINS = {
    "importlib.util": frozenset({"spec_from_file_location", "module_from_spec"}),
    "ctypes.windll": frozenset({"kernel32.GetSystemDirectoryW"}),
    "sys.modules": frozenset({"get", "pop"}),
}
#: The DLLs it may open with ctypes.WinDLL(<literal>) and the only functions it may reach on them.
_HEAL_DLLS = frozenset({"advapi32", "kernel32"})
_HEAL_DLL_FUNCS = frozenset({
    "LookupAccountNameW", "ConvertSidToStringSidW", "LocalFree", "GetNamedSecurityInfoW", "GetAce",
})  # fmt: skip
_HEAL_BUILTINS_BANNED = frozenset({
    "compile", "breakpoint", "__builtins__", "__loader__", "__spec__", "__import__", "eval",
    "exec", "setattr", "delattr", "vars", "globals", "locals",
})  # fmt: skip
#: SCHTASKS_EXE's one binding and _system32's body, compared as ASTs (docstrings dropped).
_SCHTASKS_EXE_VALUE = ast.dump(
    ast.parse('ntpath.join(_system32(), "schtasks.exe")', mode="eval").body
)
_SYSTEM32_SRC = """
def _system32() -> str:
    if _on_windows():
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260)
            if 0 < n < 260 and ntpath.isabs(buf.value):
                return str(buf.value)
        except Exception:
            pass
    return r"C:\\Windows\\System32"
"""
_ARGV_VALUE = ast.dump(ast.parse('[SCHTASKS_EXE, verb, "/TN", task, *tail]', mode="eval").body)


#: #1249 audit HOLD 4: the kill path. The healer's deny list, identity reads and _kill_tree are
#: pinned to this file (read from the BASE harness) by AST; the process-ending methods may be
#: reached only inside _kill_tree, and the pass reaches _kill_tree only as `self.box.kill(...)`.
SELF_HEAL_PINS = HERE / "self_heal_pinned.txt"
_KILL_METHODS = frozenset({"kill", "terminate", "suspend", "resume", "send_signal", "wait_procs"})
_DUNDER_BANNED = frozenset({
    "__getattribute__", "__getattr__", "__dict__", "__class__", "__globals__", "__builtins__",
    "__subclasses__", "__mro__", "__bases__", "__code__", "__closure__", "__self__", "__func__",
    "__call__", "__reduce__", "__reduce_ex__",
})  # fmt: skip


def _strip_docs(node: ast.AST) -> ast.AST:
    """A copy of `node` with every function and class docstring removed."""
    node = copy.deepcopy(node)
    for x in ast.walk(node):
        if (
            isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and x.body
            and isinstance(x.body[0], ast.Expr)
            and isinstance(x.body[0].value, ast.Constant)
            and isinstance(x.body[0].value.value, str)
        ):
            x.body = x.body[1:] or [ast.Pass()]
    return node


def _top_name(node: ast.AST) -> str | None:
    """The name a module-level def, class or single-target assignment binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id
    return None


def _bindings(tree: ast.AST, name: str) -> int:
    """How many places bind `name` anywhere: assignments, defs, classes, args, imports, except."""
    n = 0
    for x in ast.walk(tree):
        if (
            (isinstance(x, ast.Name) and x.id == name and not isinstance(x.ctx, ast.Load))
            or (
                isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and x.name == name
            )
            or (isinstance(x, ast.arg) and x.arg == name)
            or (isinstance(x, ast.alias) and (x.asname or x.name.split(".")[0]) == name)
            or (isinstance(x, ast.ExceptHandler) and x.name == name)
        ):
            n += 1
        elif isinstance(x, (ast.Global, ast.Nonlocal)) and name in x.names:
            n += 2
    return n


def _pin_problems(tree: ast.Module) -> list[str]:
    """Each definition in SELF_HEAL_PINS is defined once, at module level, AST-equal, and its
    name is bound nowhere else."""
    try:
        pinned = ast.parse(SELF_HEAL_PINS.read_text("utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ["the harness's self-heal pins are unreadable"]
    why: list[str] = []
    top: dict[str, list[ast.stmt]] = {}
    for st in tree.body:
        nm = _top_name(st)
        if nm is not None:
            top.setdefault(nm, []).append(st)
    for want in pinned.body:
        nm = _top_name(want)
        if nm is None:
            continue
        got = top.get(nm, [])
        if len(got) != 1 or ast.dump(_strip_docs(got[0])) != ast.dump(_strip_docs(want)):
            why.append(f"{nm} is not the pinned definition")
        elif _bindings(tree, nm) != 1:
            why.append(f"{nm} is bound more than once")
    return why


def _undoc(fn: ast.FunctionDef) -> str:
    """ast.dump of a function without its docstring."""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    clone = ast.FunctionDef(
        name=fn.name, args=fn.args, body=body, decorator_list=fn.decorator_list,
        returns=fn.returns, type_comment=None, type_params=getattr(fn, "type_params", []),
    )  # fmt: skip
    return ast.dump(clone, annotate_fields=False, include_attributes=False)


def _heal_allowlist(tree: ast.Module, owner: dict[int, str]) -> list[str]:
    """The allowlist half of self_heal_problems (#1249 audit HOLD 3)."""
    why: list[str] = []
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for al in node.names:
                if al.name not in _HEAL_IMPORTS or al.asname:
                    why.append(f"imports {al.name} (not on the self-heal import allowlist)")
                roots.add(al.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = "." * node.level + (node.module or "")
            names = {a.name for a in node.names}
            if mod not in _HEAL_FROM or any(a.asname for a in node.names):
                why.append(f"from-imports {mod} (not on the self-heal import allowlist)")
            else:
                allowed = _HEAL_FROM[mod]
                if allowed is not None and not names <= allowed:
                    why.append(f"from-imports {sorted(names - allowed)} from {mod}")
                if mod == "ctypes":
                    roots |= names
    dlls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _dotted(node.func) == "ctypes.WinDLL":
            up = parent.get(id(node))
            lit = node.args[0] if node.args else None
            if not (
                isinstance(up, ast.Assign)
                and len(up.targets) == 1
                and isinstance(up.targets[0], ast.Name)
                and isinstance(lit, ast.Constant)
                and lit.value in _HEAL_DLLS
            ):
                why.append("opens a DLL that is not a literal advapi32/kernel32 bound to a name")
            else:
                dlls.add(up.targets[0].id)
    for node in ast.walk(tree):
        up = parent.get(id(node))
        if isinstance(node, ast.Name) and node.id in _HEAL_BUILTINS_BANNED:
            why.append(f"names {node.id}")
        elif isinstance(node, ast.Name) and node.id in roots:
            if not isinstance(node.ctx, ast.Load):
                why.append(f"rebinds the module name {node.id}")
            elif not (isinstance(up, ast.Attribute) and up.value is node):
                why.append(f"uses the module {node.id} as a value")
        elif isinstance(node, ast.Name) and node.id in dlls and isinstance(node.ctx, ast.Load):
            if not (
                isinstance(up, ast.Attribute) and up.value is node and up.attr in _HEAL_DLL_FUNCS
            ):
                why.append(f"reaches {node.id} other than through an allowlisted function")
        elif isinstance(node, ast.Attribute) and not (
            isinstance(up, ast.Attribute) and up.value is node
        ):
            chain = _dotted(node)
            head, _, rest = chain.partition(".")
            if head not in roots or head not in _HEAL_ATTRS:
                continue
            allowed = _HEAL_ATTRS[head]
            first, _, tail = rest.partition(".")
            if allowed is not None and first not in allowed:
                why.append(f"reaches {head}.{first} (not on the allowlist)")
                continue
            pinned = _HEAL_CHAINS.get(f"{head}.{first}")
            if (
                pinned is not None
                and tail
                and not any(tail == p or tail.startswith(p + ".") for p in pinned)
            ):
                why.append(f"reaches {chain} (not on the allowlist)")
            if f"{head}.{first}" == "ctypes.windll" and tail not in pinned:  # type: ignore[operator]
                why.append(f"reaches {chain} (not on the allowlist)")
            if f"{head}.{first}" == "sys.modules":
                if owner.get(id(node)) not in {"_load", "_running_states"}:
                    why.append("touches sys.modules outside _load")
                elif not tail and not (
                    isinstance(up, ast.Subscript) and isinstance(up.ctx, ast.Store)
                ):
                    why.append("reads sys.modules by subscript")
        elif isinstance(node, ast.Call) and _dotted(node.func) == "getattr":
            name_arg = node.args[1] if len(node.args) > 1 else None
            obj = node.args[0] if node.args else None
            if not (
                (isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str))
                or (isinstance(obj, ast.Name) and obj.id == "self")
            ):
                why.append("calls getattr with a computed name")
        elif isinstance(node, ast.Call) and _dotted(node.func) == "_load":
            arg = node.args[0] if node.args else None
            fn_owner = owner.get(id(node), "")
            lits = []
            if isinstance(arg, ast.Constant):
                lits = [arg.value]
            elif isinstance(arg, ast.Name):
                fns = [
                    f for f in ast.walk(tree)
                    if isinstance(f, ast.FunctionDef) and f.name == fn_owner
                ]  # fmt: skip
                lits = [
                    a.value.value
                    for f in fns
                    for a in ast.walk(f)
                    if isinstance(a, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == arg.id for t in a.targets)
                    and isinstance(a.value, ast.Constant)
                ] + [
                    None
                    for f in fns
                    for a in ast.walk(f)
                    if isinstance(a, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For))
                    and not (isinstance(a, ast.Assign) and isinstance(a.value, ast.Constant))
                    and any(
                        isinstance(t, ast.Name) and t.id == arg.id
                        for t in (a.targets if isinstance(a, ast.Assign) else [a.target])
                    )
                ]
            if len(lits) != 1 or not (
                isinstance(lits[0], str) and lits[0].startswith("_box_self_heal_")
            ):
                why.append("loads under a module name that is not a literal _box_self_heal_*")
    # The kill path (HOLD 4): pinned definitions; process-ending methods only in _kill_tree.
    why.extend(_pin_problems(tree))
    for node in ast.walk(tree):
        up = parent.get(id(node))
        if isinstance(node, ast.Attribute) and node.attr in _DUNDER_BANNED:
            why.append(f"reaches {node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr in _KILL_METHODS:
            via_box = (
                _dotted(node) == "self.box.kill"
                and isinstance(node.ctx, ast.Load)
                and isinstance(up, ast.Call)
                and up.func is node
            )
            if owner.get(id(node)) != "_kill_tree" and not via_box:
                why.append(f"reaches .{node.attr} outside _kill_tree")
        elif isinstance(node, ast.Call) and _dotted(node.func) in {"getattr", "hasattr"}:
            lit = node.args[1] if len(node.args) > 1 else None
            if isinstance(lit, ast.Constant) and (
                lit.value in _KILL_METHODS or str(lit.value).startswith("__")
            ):
                why.append(f"reaches {lit.value!r} by name")
        elif isinstance(node, ast.Call) and _dotted(node.func) == "Box":
            kill = [k for k in node.keywords if k.arg == "kill"]
            if (
                node.args
                or any(k.arg is None for k in node.keywords)
                or len(kill) != 1
                or not (isinstance(kill[0].value, ast.Name) and kill[0].value.id == "_kill_tree")
            ):
                why.append("builds a Box whose kill is not _kill_tree")
    # SCHTASKS_EXE: bound once, at module level, to the pinned expression; _system32 pinned.
    exe_binds = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Name) and n.id in {"SCHTASKS_EXE", "_system32", "_schtasks"}
        and not isinstance(n.ctx, ast.Load)
    ]  # fmt: skip
    top = [
        n for n in tree.body
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "SCHTASKS_EXE"
    ]  # fmt: skip
    if (
        len(top) != 1
        or len(exe_binds) != 1
        or ast.dump(top[0].value) != _SCHTASKS_EXE_VALUE
        or any(isinstance(n, ast.Global) for n in ast.walk(tree))
    ):
        why.append("SCHTASKS_EXE is not bound exactly once to ntpath.join(_system32(), ...)")
    s32 = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.name == "_system32"
    ]  # fmt: skip
    canon = ast.parse(_SYSTEM32_SRC).body[0]
    if (
        len(s32) != 1
        or s32[0] not in tree.body
        or not isinstance(s32[0], ast.FunctionDef)
        or _undoc(s32[0]) != _undoc(canon)  # type: ignore[arg-type]
    ):
        why.append("_system32 is not the pinned System32 lookup")
    return why


def _owner_map(tree: ast.AST) -> dict[int, str]:
    """id(node) -> the name of the innermost function holding it."""
    owner: dict[int, str] = {}

    def visit(node: ast.AST, fn: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            owner[id(child)] = name
            visit(child, name)

    visit(tree, "")
    return owner


def self_heal_problems(head: Path) -> list[str]:
    """Why ops/box_self_heal.py is not a vouched target on `head`; [] when it is. Static only
    (Governance 2026-11-17 18:45Z; #1249 audit MF2):
    - the process and loader modules are imported plainly (`import subprocess`), never aliased or
      from-imported, and the name `subprocess` is used only inside `_schtasks`;
    - no banned call or attribute anywhere (os.system, Popen, exec, eval, runpy, getattr on a
      guarded module, ...);
    - ENDABLE_TASKS / RUNNABLE_TASKS are literal sets inside SELF_HEAL_TASKS, and no task name in
      them matches SELF_HEAL_FORBIDDEN;
    - `_schtasks(verb, task, ...)` opens with `allowed = {<literal verbs>: <those sets>}` and the
      exact guard `if verb not in allowed or task not in allowed[verb]: raise`, never rebinds
      `verb`, `task` or `allowed`, so every call site, whatever it passes, is checked at the call;
    - modules load by path only inside `_load`, and only literal SELF_HEAL_DEPS."""
    if any(SELF_HEAL_FORBIDDEN.search(t) for t in SELF_HEAL_TASKS):
        return ["the harness allowlist names an order-path task"]  # never true on a pinned base
    src = read(head, SELF_HEAL)
    if src is None:
        return ["unreadable"]
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["cannot be parsed"]
    why: list[str] = []
    if _TASK_EDIT.search(src):
        why.append("names a task-editing verb")
    docs = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):  # code only: identifiers and non-docstring strings
        text = (
            node.id
            if isinstance(node, ast.Name)
            else node.attr
            if isinstance(node, ast.Attribute)
            else node.value
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docs
            else ""
        )
        if _NATIVE_LAUNCH.search(text):
            why.append("names a native process launch")
            break
    owner = _owner_map(tree)
    why.extend(_heal_allowlist(tree, owner))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for al in node.names:
                if al.name.split(".")[0] in _GUARDED_MODULES and al.asname:
                    why.append(f"aliases {al.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            plain_wintypes = mod == "ctypes" and [a.name for a in node.names] == ["wintypes"]
            if mod.split(".")[0] in _GUARDED_MODULES and not plain_wintypes:
                why.append(f"from-imports {mod}")
        elif isinstance(node, ast.Name) and node.id == "subprocess":
            if owner.get(id(node)) != "_schtasks":
                why.append("uses subprocess outside _schtasks")
        elif isinstance(node, ast.Attribute):
            name = _dotted(node)
            if name in _BANNED_CALLS:
                why.append(f"names {name}")
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name in _BANNED_CALLS or name in {
                "setattr",
                "vars",
                "globals",
                "locals",
                "__import__",
            }:
                why.append(f"calls {name}")
            elif name == "getattr" and (
                not node.args
                or (isinstance(node.args[0], ast.Name) and node.args[0].id in _GUARDED_MODULES)
            ):
                why.append("calls getattr on a process or loader module")
            elif (
                name == "importlib.util.spec_from_file_location" and owner.get(id(node)) != "_load"
            ):
                why.append("loads a module by path outside _load")
            elif name == "_load":
                dep = node.args[1] if len(node.args) > 1 else None
                lits = (
                    [a.value for a in dep.args if isinstance(a, ast.Constant)]
                    if isinstance(dep, ast.Call) and _dotted(dep.func) == "_dep"
                    else []
                )
                ok = len(lits) == 2 == len(dep.args) and lits[1] in SELF_HEAL_DEPS  # type: ignore[union-attr]
                if not ok:
                    why.append("loads a module that is not a literal SELF_HEAL_DEPS path")
    sets: dict[str, set[str] | None] = {}
    for n in tree.body:
        target = (
            n.target
            if isinstance(n, ast.AnnAssign)
            else (n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else None)
        )
        value = n.value if isinstance(n, (ast.AnnAssign, ast.Assign)) else None
        if isinstance(target, ast.Name) and target.id in {"ENDABLE_TASKS", "RUNNABLE_TASKS"}:
            if target.id in sets:
                sets[target.id] = None  # bound twice
            else:
                sets[target.id] = _literal_strs(value)
    for node in ast.walk(tree):  # rebinding anywhere else (a function, an augmented assign)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and node not in tree.body:
            tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(t, ast.Name) and t.id in {"ENDABLE_TASKS", "RUNNABLE_TASKS"}
                for t in tgts
            ):
                why.append("rebinds a task set")
    for name in ("ENDABLE_TASKS", "RUNNABLE_TASKS"):
        got = sets.get(name)
        if got is None:
            why.append(f"{name} is not one literal set of task names")
        elif not got <= SELF_HEAL_TASKS:
            why.append(
                f"{name} names a task outside the allowlist: {sorted(got - SELF_HEAL_TASKS)}"
            )
        elif any(SELF_HEAL_FORBIDDEN.search(t) for t in got):
            why.append(f"{name} names an order-path task")
    schs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_schtasks"]
    if len(schs) != 1:
        why.append("has no single module-level _schtasks")
    else:
        sch = schs[0]
        params = [a.arg for a in sch.args.args]
        body = [
            st
            for st in sch.body
            if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant))
        ]
        tab = body[0] if body else None
        guard = body[1] if len(body) > 1 else None
        verbs: set[str] = set()
        if not (
            isinstance(tab, ast.Assign)
            and len(tab.targets) == 1
            and isinstance(tab.targets[0], ast.Name)
            and tab.targets[0].id == "allowed"
            and isinstance(tab.value, ast.Dict)
        ):
            why.append("_schtasks does not open with a literal `allowed` table")
        else:
            for k, v in zip(tab.value.keys, tab.value.values, strict=True):
                verbs.add(
                    k.value
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    else "<computed>"
                )
                names = {x.id for x in ast.walk(v) if isinstance(x, ast.Name)}
                if not names or not names <= {"ENDABLE_TASKS", "RUNNABLE_TASKS"}:
                    why.append(
                        "_schtasks's table maps a verb to something other than the task sets"
                    )
            if not verbs or not verbs <= _SCHTASKS_VERBS:
                why.append(f"_schtasks allows verbs beyond /Query, /End, /Run: {sorted(verbs)}")
        if params[:2] != ["verb", "task"] or not (
            isinstance(guard, ast.If)
            and ast.dump(guard.test) == _SCHTASKS_GUARD
            and len(guard.body) == 1
            and isinstance(guard.body[0], ast.Raise)
            and not guard.orelse
        ):
            why.append("_schtasks does not open with the exact verb/task guard")
        for node in ast.walk(sch):
            tgts = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.NamedExpr))
                else []
            )
            if node is not tab and any(
                isinstance(t, ast.Name) and t.id in {"verb", "task", "allowed"} for t in tgts
            ):
                why.append("_schtasks rebinds verb, task or allowed")
        # argv[0] is SCHTASKS_EXE: argv bound once to the pinned list, tail only from literals,
        # and every subprocess call is subprocess.run(argv, ...) with no executable/shell.
        binds: dict[str, list[ast.AST]] = {}
        for node in ast.walk(sch):
            tgts = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.NamedExpr))
                else []
            )
            for t in tgts:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        binds.setdefault(x.id, []).append(node)
        argv_b = binds.get("argv", [])
        tail_b = binds.get("tail", [])
        if not (
            len(argv_b) == 1
            and isinstance(argv_b[0], ast.Assign)
            and ast.dump(argv_b[0].value) == _ARGV_VALUE
        ):
            why.append("_schtasks does not build argv as [SCHTASKS_EXE, verb, '/TN', task, *tail]")
        if not (
            len(tail_b) == 1
            and isinstance(tail_b[0], ast.Assign)
            and {x.id for x in ast.walk(tail_b[0].value) if isinstance(x, ast.Name)}
            <= {"xml", "verb"}
            and all(
                (isinstance(x.value, str) and x.value.startswith("/")) or x.value == "CSV"
                for x in ast.walk(tail_b[0].value)
                if isinstance(x, ast.Constant)
            )
            and not any(isinstance(x, ast.Call) for x in ast.walk(tail_b[0].value))
        ):
            why.append("_schtasks's tail is not built from literal switches")
        for node in ast.walk(sch):
            if isinstance(node, ast.Call) and _dotted(node.func).startswith("subprocess."):
                first = node.args[0] if node.args else None
                if not (
                    _dotted(node.func) == "subprocess.run"
                    and isinstance(first, ast.Name)
                    and first.id == "argv"
                    and len(node.args) == 1
                    and not any(k.arg in {"executable", "shell", "args"} for k in node.keywords)
                    and all(k.arg is not None for k in node.keywords)
                ):
                    why.append("_schtasks launches something other than subprocess.run(argv)")
    return list(dict.fromkeys(why))


#: Python targets vouched for only while their rule finds nothing on the PR's tree.
DASHBOARD = "scripts/serve_dashboard.py"
#: THE DASHBOARD SERVER IS VOUCHED BY ITS EXACT TEXT (Audit #1249 MF1-6). A rule over the file's
#: shape is a blacklist: each closed hole leaves its neighbour open (a transitive subclass, a
#: __getattr__ dispatch, an aliased base, a helper that reads a file). A content pin has no
#: neighbour: the vouch holds for these sha256 digests of the file as `read()` returns it and for
#: nothing else, so ANY edit to the server (one byte) reads UNMEASURED until a digest is added
#: HERE, in the harness, which a PR cannot touch for its own target. The file is a read-only
#: static server: GET/HEAD only, an allowlist of web/ files, no per-request process, and the
#: login token handled exactly as before.
DASHBOARD_PINS = frozenset({
    "fff98e13978b1133e11f11e5cd80fc72d9cee040649286fa8c650bab98ec4ccc",
})  # fmt: skip


def dashboard_problems(head: Path) -> list[str]:
    """Why scripts/serve_dashboard.py is not a vouched target on `head`; [] when its text is one
    of DASHBOARD_PINS. Fails closed: unreadable, or any difference at all, is UNMEASURED."""
    src = read(head, DASHBOARD)
    if src is None:
        return ["unreadable"]
    digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
    if digest in DASHBOARD_PINS:
        return []
    return [f"its text is not a pinned digest ({digest[:12]}...)"]


CONDITIONAL_TARGETS: dict[str, Callable[[Path], list[str]]] = {
    SELF_HEAL: self_heal_problems,
    DASHBOARD: dashboard_problems,
}

_INSTALLER_VERBS = re.compile(
    r"(register|set|disable|enable|unregister|start|get|new)-scheduledtask\w*"
    r"|\(get-command\s+(python|py|pythonw)\b[^)]*\)\.source\b",
    re.IGNORECASE,
)
_SCRIPT_REF = re.compile(r"[A-Za-z0-9_.\\/:-]+\.(?:py|ps1|psm1|cmd|bat|sh)\b", re.IGNORECASE)


def _is_row_installer(attrs: dict[str, str], path: str) -> bool:
    """Whether `path` is the row's `installer` (never its `runs` or `also_runs`)."""
    return path == attrs.get("installer", "").strip()


#: A process launch DYNAMIC does not spell: .NET's Process.Start / ProcessStartInfo, WMI and COM.
_DOTNET_LAUNCH = re.compile(
    r"diagnostics\.process|processstartinfo|::start\s*\(|win32_process|invoke-wmimethod"
    r"|invoke-cimmethod|new-object\s+-com|wscript\.shell|shell\.application",
    re.IGNORECASE,
)


def _installer_code(text: str) -> str:
    """The installer's code: `<# ... #>` blocks and whole-line `#` comments dropped. A trailing
    ` # ...` is KEPT (#1249 audit MF2): inside a quoted -Argument it is not a comment at all, and
    keeping it can only make the scan see more."""
    text = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _resolve_ref(ref: str, files: set[str]) -> set[str]:
    """The repo files a script reference can mean: the longest repo-relative tail that names a
    file, backslashes read as slashes. Empty when nothing in the tree matches (unresolved)."""
    parts = [x for x in ref.replace("\\", "/").split("/") if x and not x.endswith(":")]
    for i in range(len(parts)):
        tail = "/".join(parts[i:])
        hit = {f for f in files if f == tail or f.endswith("/" + tail)}
        if hit:
            return hit
    return set()


#: An action's -Execute / -Argument value: a quoted string, a parenthesised expression, a variable.
_VALUE = r"(?P<v>'[^']*'|\"(?:`.|[^\"`])*\"|\((?:[^()]|\([^()]*\))*\)|\$\w+|\S+)"
_EXECUTE = re.compile(r"-execute\s+" + _VALUE, re.IGNORECASE)
_ARGUMENT = re.compile(r"-argument\s+" + _VALUE, re.IGNORECASE)
#: What may never appear in an expanded argument: a module or code flag, a shell chain.
_ARG_BANNED = re.compile(
    r"(?<![\w-])-[mc]\b|(?<![\w])/[ck]\b|&&|\|\||[;&|<>]|\bcmd(\.exe)?\b|powershell|pwsh",
    re.IGNORECASE,
)
_PYTHON_EXE = re.compile(r"^[^'\";|&\s]*\b(python|pythonw|py)(\d[\d.]*)?(\.exe)?$", re.IGNORECASE)
#: Interpreter flags that may come before the script: they run nothing of their own.
_PY_FLAGS_1 = frozenset({"-u", "-b", "-B", "-E", "-I", "-s", "-S", "-O", "-OO", "-q"})
_PY_FLAGS_2 = frozenset({"-W", "-X"})
#: Indirect or typed variable binding, which the one-assignment model cannot follow.
_INDIRECT_VAR = re.compile(
    r"\b(set|new)-variable\b|(?<![\w-])(sv|nv)\s|\$\{|\$(script|global|local|private):"
    r"|\[ref\]|-outvariable\b|-ov\b",
    re.IGNORECASE,
)
#: A typed binding (`[string]$x = ...`, a param() entry): the caller can override a parameter,
#: so a variable bound this way is a binding the leg cannot evaluate.
_TYPED_BIND = re.compile(r"\[[\w.\[\]]+\]\s*\$(\w+)")
_ASSIGN = re.compile(r"^\s*\$(\w+)\s*=\s*(.+?)\s*$")
_ROOT_MARK = "\x00ROOT\x00"
_PY_MARK = "\x00PYTHON\x00"


def _logical_lines(code: str) -> list[str]:
    """Lines with PowerShell's backtick continuations joined."""
    return re.sub(r"`[ \t]*\r?\n\s*", " ", code).splitlines()


class _Unresolved(Exception):
    pass


def _expander(code: str) -> Callable[[str], str]:
    """expand(expr) -> the literal string an installer expression evaluates to, under a model
    that accepts only: 'lit', "text" with $var / $($var) inside, (\"fmt\" -f a, b), $var bound
    by exactly ONE plain `$var = <one of these>` line, `Join-Path $x 'lit'` (a path under some
    root), and `(Get-Command python ...).Source`. Anything else raises _Unresolved."""
    binds: dict[str, list[str]] = {}
    for ln in _logical_lines(code):
        m = _ASSIGN.match(ln)
        if m:
            binds.setdefault(m.group(1).lower(), []).append(m.group(2))
    for m in _TYPED_BIND.finditer(code):  # typed or param() bindings: never evaluable
        binds.setdefault(m.group(1).lower(), []).append("<typed>")
    for ln in _logical_lines(code):  # foreach / pipeline bindings to a name are other binders
        for m in re.finditer(r"foreach\s*\(\s*\$(\w+)", ln, re.IGNORECASE):
            binds.setdefault(m.group(1).lower(), []).append("<loop>")

    def var(name: str, depth: int) -> str:
        rhs = binds.get(name.lower(), [])
        if len(rhs) != 1:
            raise _Unresolved(f"${name} is bound {len(rhs)} times")
        return expand(rhs[0], depth + 1)

    def expand(expr: str, depth: int = 0) -> str:
        if depth > 8:
            raise _Unresolved("too deep")
        e = expr.strip()
        if re.fullmatch(r"'[^']*'", e):
            return e[1:-1]
        if re.fullmatch(r"\"(?:`.|[^\"`])*\"", e):
            body = e[1:-1].replace('`"', '"')
            if re.search(r"\$\((?!\$\w+\))", body):
                raise _Unresolved("a subexpression in a string")
            return re.sub(
                r"\$\(\$(\w+)\)|\$(\w+)",
                lambda m: var(m.group(1) or m.group(2), depth),
                body,
            )
        if re.fullmatch(r"\$\w+", e):
            return var(e[1:], depth)
        m = re.fullmatch(
            r"\(\s*get-command\s+(python|pythonw|py)\b[^()]*\)\.source", e, re.IGNORECASE
        )
        if m:
            return _PY_MARK
        m = re.fullmatch(r"join-path\s+\$\w+\s+('[^']*')", e, re.IGNORECASE)
        if m:
            return _ROOT_MARK + "/" + m.group(1)[1:-1]
        m = re.fullmatch(r"\(\s*(\"(?:`.|[^\"`])*\"|'[^']*')\s+-f\s+(.+)\)", e, re.IGNORECASE)
        if m:
            fmt = expand(m.group(1), depth + 1)
            args = [expand(x, depth + 1) for x in m.group(2).split(",")]
            try:
                return fmt.format(*args)
            except (IndexError, KeyError, ValueError) as exc:
                raise _Unresolved("a format that does not fill") from exc
        if re.fullmatch(r"\(([^()]*)\)", e):
            return expand(e[1:-1], depth + 1)
        raise _Unresolved(f"cannot evaluate {e[:40]!r}")

    return expand


def _argv(arg: str) -> list[str]:
    """Whitespace tokens of an expanded argument string, quotes dropped."""
    return [t.strip("'\"") for t in arg.split() if t.strip("'\"")]


def installer_problems(head: Path, path: str) -> list[str]:
    """Why a changed PowerShell installer is not MEASURED by its own text; [] when it is.

    #1249 audit: a target is vouched ONLY by INSTALLER_TARGETS (or a conditional target whose
    rule passes), never by ENTRY_POINTS or the replay's imports (MF1 v1). Every action's
    -Execute and -Argument, wherever they sit on the (continuation-joined) line, are EVALUATED
    under a one-plain-assignment model (_expander); anything it cannot evaluate, any typed or
    indirect binding, is UNMEASURED (MF1 v2). The evaluated -Execute must be python; the
    evaluated -Argument may carry no module/code flag or shell chain, and its first token after
    interpreter flags must be a vouched script (MF3). Every script the code names anywhere must
    resolve and be vouched."""
    if not path.lower().endswith(".ps1"):
        return ["not a PowerShell installer"]
    raw = read(head, path)
    if raw is None:
        return ["unreadable"]
    code = _installer_code(raw)
    if not re.search(r"new-scheduledtaskaction", code, re.IGNORECASE):
        return ["registers no scheduled task action"]
    why: list[str] = []
    low = code.lower()
    if MONEY_WORDS.search(low) or STATE_WORDS.search(low):
        why.append("its code names a venue or switch word")
    if _INDIRECT_VAR.search(code):
        why.append("binds a variable indirectly or with a type, which the leg cannot follow")
    for ln in code.splitlines():
        if _DOTNET_LAUNCH.search(ln) or DYNAMIC.search(_INSTALLER_VERBS.sub("", ln)):
            why.append(f"dynamic execution beyond the scheduled-task verbs: {ln.strip()[:80]}")
            break
    files = tree_files(head)
    heal_ok = not self_heal_problems(head) if SELF_HEAL in files else False

    def vouched(f: str) -> bool:
        if f in INSTALLER_TARGETS:
            return True
        if f in CONDITIONAL_TARGETS:
            return not CONDITIONAL_TARGETS[f](head)
        return f in SELF_HEAL_DEPS and heal_ok

    for ref in sorted({m.group(0) for m in _SCRIPT_REF.finditer(code)}):
        hit = _resolve_ref(ref, files)
        if not hit:
            why.append(f"the code names a script the tree does not hold: {ref[:80]}")
        elif not all(vouched(f) for f in hit):
            bad = sorted(f for f in hit if not vouched(f))[0]
            why.append(f"the code names a target the replay does not vouch for: {bad}")
    expand = _expander(code)
    actions = [
        ln
        for ln in _logical_lines(code)
        if re.search(r"new-scheduledtaskaction", ln, re.IGNORECASE)
    ]
    for ln in actions:
        ex, ar = _EXECUTE.search(ln), _ARGUMENT.search(ln)
        if ex is None or ar is None:
            why.append("an action has no -Execute or no -Argument the leg can read")
            continue
        try:
            exe, arg = expand(ex.group("v")), expand(ar.group("v"))
        except _Unresolved as exc:
            why.append(f"an action cannot be evaluated: {exc}")
            continue
        if exe != _PY_MARK and not _PYTHON_EXE.match(exe):
            why.append(f"an action executes {exe[:40]!r}, which is not python")
        if _ARG_BANNED.search(arg):
            why.append("an action's arguments carry a module flag or a shell chain")
        toks = _argv(arg)
        i = 0
        while i < len(toks) and toks[i].startswith("-"):
            i += 2 if toks[i] in _PY_FLAGS_2 else 1 if toks[i] in _PY_FLAGS_1 else len(toks)
        first = toks[i] if i < len(toks) else ""
        hit = (
            _resolve_ref(first.replace(_ROOT_MARK + "/", ""), files)
            if _SCRIPT_REF.fullmatch(first.replace(_ROOT_MARK + "/", ""))
            else set()
        )
        if not hit or not all(vouched(f) for f in hit):
            why.append(f"an action's script is not a vouched target: {first[:60]!r}")
    return list(dict.fromkeys(why))


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
    base: Path,
    head: Path,
    closure: set[str],
    money: set[str],
    exempt: set[str],
    measured: frozenset[str] | set[str] = frozenset(),
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
    names |= {
        n for m in money - set(measured) for n in (Path(m).name.lower(), Path(m).stem.lower())
    }
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
            if _is_row_installer(attrs, p) and p in measured:
                continue  # an installer the installer leg MEASURED by its own text
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
    return bindings(src, lambda n: bool(KNOB.match(n)))


def bindings(src: str, keep: Callable[[str], bool]) -> dict[str, list[str]]:
    """{name: [every way the file binds it]} at module and class scope, for the names `keep`
    accepts, plus every function's parameter defaults. A plain `NAME = value` records the
    value's ast; any other binding records a marked entry that can never equal a pinned value,
    so a ceiling row sees it as a second value (#554 audit SF): `NAME += 1`, a tuple or starred
    target, a walrus, `global NAME` assigned in a function, `del NAME`, `import x as NAME`, a
    for/with/except target, and every guarded body (if, for, while, with, try, try*, match)."""
    out: dict[str, list[str]] = {}

    def put(name: str, val: str) -> None:
        if keep(name.rsplit(".", 1)[-1].split("(", 1)[0]) or name.endswith("=)"):
            out.setdefault(name, []).append(val)

    def target(t: ast.expr, prefix: str, val: str) -> None:
        if isinstance(t, ast.Name):
            put(f"{prefix}{t.id}", val)
        elif isinstance(t, ast.Tuple | ast.List):
            for e in t.elts:
                target(e, prefix, f"UNPACKED {val}")
        elif isinstance(t, ast.Starred):
            target(t.value, prefix, f"STARRED {val}")

    def walrus(node: ast.AST, prefix: str) -> None:
        for n in ast.walk(node):
            if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
                put(f"{prefix}{n.target.id}", f"WALRUS {ast.dump(n.value)}")

    def globals_in(fn: ast.AST) -> None:
        """`global NAME` in a function: its assignments there bind the module's NAME."""
        names = {g for n in ast.walk(fn) if isinstance(n, ast.Global) for g in n.names}
        for n in ast.walk(fn):
            ts: list[ast.expr] = []
            if isinstance(n, ast.Assign):
                ts = list(n.targets)
            elif isinstance(n, ast.AugAssign | ast.AnnAssign):
                ts = [n.target]
            for t in ts:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name) and x.id in names:
                        put(x.id, f"GLOBAL {ast.dump(n)}")

    def walk(body: list[ast.stmt], prefix: str, guarded: bool = False) -> None:
        for n in body:
            if isinstance(n, ast.ClassDef):
                walk(n.body, f"{prefix}{n.name}.")
            elif isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef):
                a = n.args
                pos = [*a.posonlyargs, *a.args]
                pairs = list(zip(pos[len(pos) - len(a.defaults) :], a.defaults, strict=True))
                pairs += [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults, strict=True) if d]
                for arg, default in pairs:
                    out.setdefault(f"{prefix}{n.name}({arg.arg}=)", []).append(ast.dump(default))
                walk(n.body, f"{prefix}{n.name}.")  # nested functions' defaults too
                globals_in(n)
            elif isinstance(n, ast.Assign):
                walrus(n.value, prefix)
                for t in n.targets:
                    plain = isinstance(t, ast.Name) and not guarded
                    target(t, prefix, ast.dump(n.value) if plain else f"BOUND {ast.dump(n.value)}")
            elif isinstance(n, ast.AnnAssign):
                if n.value is not None:
                    walrus(n.value, prefix)
                    v = ast.dump(n.value)
                    target(n.target, prefix, v if not guarded else f"BOUND {v}")
            elif isinstance(n, ast.AugAssign):
                target(n.target, prefix, f"AUGMENTED {ast.dump(n)}")
            elif isinstance(n, ast.Delete):
                for t in n.targets:
                    target(t, prefix, "DELETED")
            elif isinstance(n, ast.Import | ast.ImportFrom):
                for al in n.names:
                    name = al.asname or al.name.split(".", 1)[0]
                    put(f"{prefix}{name}", f"IMPORTED {ast.dump(n)}")
            elif isinstance(n, ast.For | ast.AsyncFor):
                target(n.target, prefix, f"LOOPED {ast.dump(n.iter)}")
                walrus(n.iter, prefix)
                walk(n.body + n.orelse, prefix, True)
            elif isinstance(n, ast.With | ast.AsyncWith):
                for item in n.items:
                    walrus(item.context_expr, prefix)
                    if item.optional_vars is not None:
                        target(item.optional_vars, prefix, "WITH")
                walk(n.body, prefix, True)
            elif isinstance(n, ast.If | ast.While):
                walrus(n.test, prefix)
                walk(n.body + n.orelse, prefix, True)
            elif isinstance(n, ast.Try | ast.TryStar):
                walk(n.body + n.orelse + n.finalbody, prefix, True)
                for h in n.handlers:
                    if h.name:
                        put(f"{prefix}{h.name}", "EXCEPT")
                    walk(h.body, prefix, True)
            elif isinstance(n, ast.Match):
                walrus(n.subject, prefix)
                for case in n.cases:
                    for x in ast.walk(case.pattern):
                        bound = getattr(x, "name", None) or getattr(x, "rest", None)
                        if isinstance(bound, str):
                            put(f"{prefix}{bound}", "MATCHED")
                    walk(case.body, prefix, True)
            else:
                walrus(n, prefix)

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
    for f, names in (doc.get("source") or {}).items():
        out.setdefault(f, set()).update(names)
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


def new_and_bounded(base: Path, head: Path, head_imported: set[str]) -> set[str]:
    """New money files the HEAD's replay ran (no base can import a file it lacks) whose every
    knob a ceiling already holds, from the base's ceilings.json. The replay shows their code
    decides like the base on the grid; the ceilings, not the replay, vouch for their values
    (#553 audit: a clean replay never measures a knob). A file with one unbounded knob stays
    UNMEASURED."""
    held = bounded()
    out = set()
    for f in head_imported:
        if not f.endswith(".py") or read(base, f) is not None:
            continue
        try:
            names = set(knobs(read(head, f) or ""))
        except SyntaxError:
            continue
        if names <= held.get(f, set()):
            out.add(f)
    return out


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
            # the FTMO lane at the same step (replay_child.ftmo_step): executor and reader
            "ftmo": step.get("ftmo"),
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


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _symbol_of(name: str) -> str:
    head = name.split("_", 1)[0].split(".", 1)[0].upper()
    if head in ("GOLD", "XAU"):
        return "XAUUSD"
    return head if re.fullmatch(r"[A-Z]{6}", head) else ""


def _policy_values(trees: tuple[Path, ...]) -> dict[str, set[str]]:
    """Every banned family, timeframe and exec either tree's policy file names."""
    fams: set[str] = set()
    tfs: set[str] = set()
    execs: set[str] = set()
    for tree in trees:
        pol = _load(tree / ROSTER_FILES[0])
        pol = pol if isinstance(pol, dict) else {}
        fams |= {str(f).lower() for f in _as_list(pol.get("banned_families"))}
        execs |= {str(e).lower() for e in _as_list(pol.get("banned_execs"))}
        bt = pol.get("banned_timeframes")
        for vals in bt.values() if isinstance(bt, dict) else []:
            tfs |= {str(v).upper() for v in _as_list(vals)}
    return {"families": fams, "timeframes": tfs, "execs": execs}


def _as_list(x: Any) -> list[Any]:
    return x if isinstance(x, list) else []


def roster_rows(trees: tuple[Path, ...], grid: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for the roster leg, each with a unique printable `id`: every name either tree's policy
    or certified book carries; the probes (symbol x family x timeframe, and symbol x exec) over
    every symbol either tree or the grid names, with the grid's families, timeframes and execs
    PLUS every banned_* value either tree names (MF6); and each named live sleeve again under every
    probed family, timeframe and exec, so a ban still reaches a symbol whose live_sleeves list
    refuses every anonymous probe. Unprintable names are dropped (MF5)."""
    venues = [str(v) for v in grid.get("venues") or []]
    banned = _policy_values(trees)
    fams = sorted({str(f).lower() for f in grid.get("families") or []} | banned["families"])
    tfs = sorted({str(t).upper() for t in grid.get("timeframes") or []} | banned["timeframes"])
    execs = sorted({str(e).lower() for e in grid.get("execs") or []} | banned["execs"])
    symbols = {str(x).upper() for x in grid.get("symbols") or []}
    rows: dict[str, dict[str, Any]] = {}

    def put(rid: str, row: dict[str, Any]) -> None:
        printable = all(
            SAFE_NAME.match(str(v)) for k, v in row.items() if k != "id" and v != ""
        )  # fmt: skip
        if SAFE_NAME.match(rid) and printable and row.get("symbol"):
            rows.setdefault(rid, {"id": rid, "family": "", "timeframe": "", "exec": "", **row})

    named: list[tuple[str, str]] = []
    for tree in trees:
        pol = _load(tree / ROSTER_FILES[0])
        pol = pol if isinstance(pol, dict) else {}
        book = _load(tree / ROSTER_FILES[1])
        book = book if isinstance(book, dict) else {}
        symbols |= {str(x).upper() for x in _as_list(pol.get("live_symbols")) if str(x) != "*"}
        bt = pol.get("banned_timeframes")
        symbols |= {str(k).upper() for k in (bt if isinstance(bt, dict) else {}) if k != "*"}
        ls = pol.get("live_sleeves")
        for sym, names in sorted((ls if isinstance(ls, dict) else {}).items()):
            symbols.add(str(sym).upper())
            named += [(str(n), str(sym).upper()) for n in _as_list(names)]
        keys: set[str] = set()
        for block in (*venues, "e8_pending", "excluded"):
            if isinstance(book.get(block), dict):
                keys |= {str(k) for k in book[block]}
        for k in sorted(keys):
            m = _BOOK_KEY.match(k)
            if m:
                put(k, {"name": k, "book_key": k, "symbol": m.group(1), "family": m.group(2),
                        "selector": m.group(3)})  # fmt: skip
            else:
                put(k, {"name": k, "book_key": k, "symbol": _symbol_of(k)})
    for n, sym in sorted(set(named)):
        put(n, {"name": n, "symbol": sym})
        for fam in fams:
            put(f"{n}=fam.{fam}", {"name": n, "symbol": sym, "family": fam})
        for tf in tfs:
            put(f"{n}=tf.{tf}", {"name": n, "symbol": sym, "timeframe": tf})
        for ex in execs:
            put(f"{n}=exec.{ex}", {"name": n, "symbol": sym, "exec": ex})
    for sym in sorted(x for x in symbols if SAFE_NAME.match(x)):
        for fam in fams:
            for tf in tfs:
                rid = f"probe.{sym}.{fam}.{tf or 'any'}"
                put(rid, {"name": rid, "symbol": sym, "family": fam, "timeframe": tf})
        for ex in execs:
            rid = f"probe.{sym}.exec.{ex or 'none'}"
            put(rid, {"name": rid, "symbol": sym, "exec": ex})
    return [rows[k] for k in sorted(rows)]


def roster_diff(
    b: dict[str, Any], h: dict[str, Any], rows: list[dict[str, Any]]
) -> list[tuple[str, str, str]]:
    """(kind, symbol, row id) for every outcome the head decides differently. Kinds: `admit` and
    `refuse` (the live policy door flipped), `zero:<venue>`, `book:<venue>`, `e8`."""
    sym = {str(r["id"]): str(r["symbol"]) for r in rows}
    out: list[tuple[str, str, str]] = []
    br, hr = b.get("rows") or {}, h.get("rows") or {}
    for rid in sorted(set(br) | set(hr)):
        if rid not in sym:
            continue
        x, y = br.get(rid) or {}, hr.get(rid) or {}
        if bool(x.get("admitted")) != bool(y.get("admitted")):
            out.append(("admit" if y.get("admitted") else "refuse", sym[rid], rid))
        xz, yz = x.get("zero") or {}, y.get("zero") or {}
        for v in sorted(set(xz) | set(yz)):
            if xz.get(v) != yz.get(v):
                out.append((f"zero:{v}", sym[rid], rid))
    bb, hb = b.get("books") or {}, h.get("books") or {}
    for v in sorted(set(bb) | set(hb)):
        x, y = bb.get(v), hb.get(v)
        if (x is None) != (y is None):
            out.append((f"book:{v}", "*", "void" if y is None else "restored"))
            continue
        for k in sorted(set(x or {}) | set(y or {})):
            if (x or {}).get(k) != (y or {}).get(k):
                out.append((f"book:{v}", _symbol_of(k) or "*",
                            k if SAFE_NAME.match(k) else "<unprintable>"))  # fmt: skip
    if (b.get("e8") or {}) != (h.get("e8") or {}):
        out.append(("e8", "*", "live_admissible"))
    return out


#: The live policy keys the leg resolves (replay_child.POLICY_MEASURED) and probes.
POLICY_MEASURED = (
    "live_symbols", "banned_timeframes", "banned_families", "banned_execs", "live_sleeves",
)  # fmt: skip


def _is_test(f: str) -> bool:
    return "tests/" in f or f.rsplit("/", 1)[-1].startswith("test_")


def _read_by_code(trees: tuple[Path, ...], key: str) -> bool:
    """True when any non-test Python file in either tree spells `key` as a string literal: a key
    some code may read is never prose, whatever its name (MF6). Fails closed on a search error."""
    lits = (f'"{key}"', f"'{key}'")
    for tree in trees:
        if _is_git(tree):
            p = subprocess.run(
                ["git", "-C", str(tree), "grep", "-l", "-F", "-e", lits[0], "-e", lits[1],
                 "HEAD", "--", "*.py"],
                capture_output=True, text=True, check=False,
            )  # fmt: skip
            if p.returncode not in (0, 1):
                return True
            hits = [ln.split(":", 1)[-1] for ln in p.stdout.splitlines()]
        else:
            hits = [
                f for f in tree_files(tree)
                if f.endswith(".py") and any(x in (read(tree, f) or x) for x in lits)
            ]  # fmt: skip
        if any(not _is_test(f) for f in hits):
            return True
    return False


def _top_diff(a: Any, b: Any) -> list[str]:
    a = a if isinstance(a, dict) else {}
    b = b if isinstance(b, dict) else {}
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _printable(k: str) -> str:
    return k if SAFE_NAME.match(k) else "<unprintable>"


def roster_unmeasured(
    base: Path,
    head: Path,
    legs: dict[str, Any],
    rows: list[dict[str, Any]],
    flips: list[tuple[str, str, str]],
    venues: list[str],
) -> dict[str, list[str]]:
    """Why each roster file stays UNMEASURED although the leg ran (Auditor MF6, MF7).

    live_sleeve_policy.json: every top-level key that differs must be one the leg resolves
    (POLICY_MEASURED) or prose no code reads; and every value the two RESOLVED policies (code
    defaults included) disagree on must flip at least one row that carries it -- a change the
    probes cannot reach is a change nobody measured.
    CERT_BOOK_LIVE.json: every top-level block that differs must be a venue block the leg reads
    through load_cert_book; every other block has readers the leg never runs."""
    out: dict[str, list[str]] = {f: [] for f in ROSTER_FILES}
    pol_file, book_file = ROSTER_FILES
    for k in _top_diff(_load(base / pol_file), _load(head / pol_file)):
        if k not in POLICY_MEASURED and _read_by_code((base, head), k):
            out[pol_file].append(f"key {_printable(k)} is read by code the leg does not run")
    byid = {str(r["id"]): r for r in rows}
    flipped = [byid[rid] for k, _s, rid in flips if k in ("admit", "refuse") and rid in byid]

    def reached(field: str, value: str, symbol: str = "*") -> bool:
        return any(
            str(r.get(field) or "").upper() == value.upper()
            and (symbol == "*" or str(r.get("symbol")) == symbol)
            for r in flipped
        )  # fmt: skip

    bp = (legs.get("base") or {}).get("policy")
    hp = (legs.get("head") or {}).get("policy")
    if not (isinstance(bp, dict) and isinstance(hp, dict)):
        out[pol_file].append("the leg did not report the resolved policy")
    else:
        for key, field in (("banned_families", "family"), ("banned_execs", "exec")):
            for v in sorted(set(_as_list(bp.get(key))) ^ set(_as_list(hp.get(key)))):
                if not reached(field, str(v)):
                    out[pol_file].append(f"{key} {_printable(str(v))} flips no probed row")
        for v in sorted(
            set(_as_list(bp.get("live_symbols"))) ^ set(_as_list(hp.get("live_symbols")))
        ):
            if not reached("symbol", str(v)):
                out[pol_file].append(f"live_symbols {_printable(str(v))} flips no probed row")
        btf, htf = bp.get("banned_timeframes") or {}, hp.get("banned_timeframes") or {}
        for sym in sorted(set(btf) | set(htf)):
            for v in sorted(set(_as_list(btf.get(sym))) ^ set(_as_list(htf.get(sym)))):
                if not reached("timeframe", str(v), str(sym)):
                    out[pol_file].append(
                        f"banned_timeframes {_printable(str(sym))} {_printable(str(v))} "
                        "flips no probed row"
                    )
        bls, hls = bp.get("live_sleeves") or {}, hp.get("live_sleeves") or {}
        for sym in sorted(set(bls) | set(hls)):
            x, y = bls.get(sym), hls.get(sym)
            if x == y:
                continue
            if x is None or y is None:  # the symbol's restriction appeared or went
                if not reached("symbol", str(sym)):
                    out[pol_file].append(f"live_sleeves {_printable(str(sym))} flips no row")
                continue
            for n in sorted(set(_as_list(x)) ^ set(_as_list(y))):
                if not reached("name", str(n), str(sym)):
                    out[pol_file].append(
                        f"live_sleeves {_printable(str(sym))} {_printable(str(n))} flips no row"
                    )
    for k in _top_diff(_load(base / book_file), _load(head / book_file)):
        if k not in venues:
            out[book_file].append(
                f"block {_printable(k)} has readers the leg does not run (not a venue block)"
            )
    return out


def _pr_and_head() -> tuple[int | None, str]:
    pr, head = os.environ.get("PR") or "", os.environ.get("HEAD_SHA") or ""
    if not (pr and head) and os.environ.get("GITHUB_EVENT_PATH"):
        ev = (_load(Path(os.environ["GITHUB_EVENT_PATH"])) or {}).get("pull_request") or {}
        pr = pr or str(ev.get("number") or "")
        head = head or str((ev.get("head") or {}).get("sha") or "")
    return (int(pr) if pr.isdigit() else None), head


def declared_match(
    diffs: list[tuple[str, str, str]], declared: Any, pr: int | None, head_sha: str
) -> str | None:
    """None when `diffs` equal exactly one declared row for this PR and this full head sha;
    otherwise why not (MF3/MF4). Only admit/refuse flips are declarable."""
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha or "") or pr is None:
        return "no PR number or no full 40-hex head sha to match a declaration against"
    other = sorted({k for k, _s, _n in diffs if k not in ("admit", "refuse")})
    if other:
        return f"undeclarable divergence ({', '.join(other)})"
    rows = declared.get("rows") if isinstance(declared, dict) else declared
    mine = [
        r for r in rows or []
        if isinstance(r, dict) and r.get("pr") == pr and r.get("head_sha") == head_sha
    ]  # fmt: skip
    if len(mine) != 1:
        return f"{len(mine)} declared rows for this PR at this head (exactly one is required)"
    row = mine[0]
    refuse = row.get("refuse") or []
    if not all(
        isinstance(r, dict) and isinstance(r.get("missed_growth"), str)
        and r["missed_growth"].strip() for r in refuse
    ):  # fmt: skip
        return "a declared refusal carries no missed_growth line"
    want_admit = {str(n) for n in row.get("admit") or []}
    want_refuse = {str(r.get("name")) for r in refuse}
    got_admit = {n for k, _s, n in diffs if k == "admit"}
    got_refuse = {n for k, _s, n in diffs if k == "refuse"}
    if (want_admit, want_refuse) != (got_admit, got_refuse):
        return "the measured flips differ from the declared admit/refuse sets"
    return None


def roster_grid() -> dict[str, Any]:
    grid = _load(ROSTER_GRID)
    if not isinstance(grid, dict):
        raise ValueError("ops/release/fusion_roster_grid.json is unreadable")
    return grid


FTMO_EXECUTOR = "desks/mt5/prop/ftmo_executor.py"


def compare(
    base: Path,
    head: Path,
    changed: list[str],
    grid: list[dict[str, Any]] | None = None,
    *,
    declared: Any = None,
    pr: int | None = None,
    head_sha: str | None = None,
) -> dict[str, Any]:
    grid = scenarios() if grid is None else grid
    # fresh fingerprints each run, the same for both trees: fooling the replay needs code that
    # hunts for the harness, which the reviewer's rule 5 names (#457 audit should-fix)
    who = {"account_id": 10_000 + secrets.randbelow(89_999_999), "server": secrets.token_hex(5)}
    grid = [{**who, **sc} for sc in grid]
    problems: list[str] = []
    # The roster leg is owed where the base HAS the roster (as the FTMO leg below). Its rows ride
    # on the first scenario only: one measurement, both trees, the same rows (MF1).
    roster_owed = (base / ROSTER_FILES[0]).is_file()
    roster: dict[str, Any] | None = None
    roster_rows_: list[dict[str, Any]] = []
    if roster_owed and grid:
        rg = roster_grid()
        roster_rows_ = roster_rows((base, head), rg)
        if len(roster_rows_) > int(rg.get("max_rows") or 0):
            problems.append(
                f"UNMEASURED fusion roster: {len(roster_rows_)} rows exceed the grid's max_rows"
            )
            roster_rows_ = []
        else:
            roster = {"rows": roster_rows_, "venues": list(rg.get("venues") or [])}
            grid[0] = {**grid[0], "fusion_roster": roster}
    roster_legs: dict[str, Any] = {}
    imported: set[str] = set()
    head_imported: set[str] = set()
    placed = 0
    ftmo_rows = 0
    # The FTMO leg is owed only where the base HAS the lane (a toy tree, or a base from before
    # the lane existed, has nothing to measure; a head that adds it is a new money file).
    ftmo_owed = (base / FTMO_EXECUTOR).is_file()
    for sc in grid:
        b, h = run_tree(base, sc), run_tree(head, sc)
        if "crash" in b:
            problems.append(f"UNMEASURED {sc['id']}: the base tree cannot run it ({b['crash']})")
            continue
        if "crash" in h:
            problems.append(f"{sc['id']}: the PR's tree crashed ({h['crash']})")
            continue
        if "fusion_roster" in sc:
            roster_legs = {"base": b.get("fusion_roster"), "head": h.get("fusion_roster")}
        base_root, head_root = str(base.resolve()), str(head.resolve())
        imported.update(
            Path(f).relative_to(base_root).as_posix()
            for f in b["imported"]
            if f.startswith(base_root + "/")
        )
        head_imported.update(
            Path(f).relative_to(head_root).as_posix()
            for f in h.get("imported") or []
            if f.startswith(head_root + "/")
        )
        for bs, hs in zip(b["steps"], h["steps"], strict=True):
            fb = bs.get("ftmo") or {}
            ftmo_err = (
                fb.get("setup_error") or fb.get("error") or (fb.get("exec") or {}).get("error")
            )
            if ftmo_err and ftmo_owed:
                # the FTMO leg must run on the base, or its agreement with the head is vacuous
                problems.append(
                    f"UNMEASURED {sc['id']} @{bs['hour']}: the base FTMO leg raised "
                    f"{str(ftmo_err)[:200]}"
                )
            ftmo_rows += len((fb.get("exec") or {}).get("sleeves") or [])
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
    if ftmo_owed and not ftmo_rows:
        problems.append("UNMEASURED: the base FTMO leg decided on no sleeve anywhere on the grid")
    roster_flips: list[tuple[str, str, str]] = []
    roster_ok = False
    if roster is not None:
        for side in ("base", "head"):
            leg = roster_legs.get(side)
            if not isinstance(leg, dict) or "error" in leg:
                kind = "missing" if not isinstance(leg, dict) else str(leg["error"]).split(":")[0]
                kind = kind if SAFE_NAME.match(kind.replace(" ", "_")) else "error"
                problems.append(f"UNMEASURED fusion roster: the {side} leg did not run ({kind})")
        if not any(p.startswith("UNMEASURED fusion roster") for p in problems):
            roster_ok = True
            roster_flips = roster_diff(roster_legs["base"], roster_legs["head"], roster_rows_)
    touched = sorted(f for f in changed if f in ROSTER_HARNESS)
    problems += [
        f"the PR changes the Fusion-roster replay harness (it cannot measure itself): {f}"
        for f in touched
    ]
    closure = import_closure(base)
    covered = imported | new_and_bounded(base, head, head_imported)
    roster_gaps: dict[str, list[str]] = {}
    if roster_ok and roster is not None:
        roster_gaps = roster_unmeasured(
            base, head, roster_legs, roster_rows_, roster_flips, list(roster["venues"])
        )
        for f in ROSTER_FILES:
            if not roster_gaps[f]:
                covered.add(f)
            elif f in changed:
                problems += [f"UNMEASURED fusion roster: {f} {why}" for why in roster_gaps[f]]
    exempt = exempt_scripts((base, head), closure)
    money = money_scripts((base, head), closure)
    # the installer leg: a changed installer the replay could not import, MEASURED by its text
    installers = {
        f for f in changed
        if is_script(f) and f.lower().endswith(".ps1") and f not in exempt and f not in covered
        and not installer_problems(head, f)
    }  # fmt: skip
    rows_only = MANIFEST in changed and not manifest_is_money(
        base, head, closure, money, exempt, measured=installers
    )
    uncovered = sorted(
        f for f in changed
        if is_money(f, closure, exempt=exempt) and f not in covered and f not in installers
        and not (f == MANIFEST and rows_only)
    )  # fmt: skip
    not_money = sorted(f for f in changed if is_script(f) and f in exempt)
    problems += [
        f"UNMEASURED money-path change (the replay never imported it): {f}" for f in uncovered
    ]
    problems += knob_changes(base, head, changed, closure, exempt)
    flips = [f"fusion roster {k} {sym} {name}" for k, sym, name in roster_flips]
    verdict = "FAIL" if problems or flips else "PASS"
    declared_why = "not considered: the PR has other problems" if problems else None
    if flips and not problems:
        if declared is None and os.environ.get(DECLARED_ENV):
            declared = _load(Path(os.environ[DECLARED_ENV]))
        if pr is None and head_sha is None:
            pr, head_sha = _pr_and_head()
        declared_why = (
            "no declared-divergence registry"
            if declared is None
            else declared_match(roster_flips, declared, pr, head_sha or "")
        )
        if declared_why is None:
            verdict = MATCHES_DECLARED
    return {
        "verdict": verdict,
        "fusion_roster": {
            "measured": roster_ok,
            "covered": sorted(f for f in ROSTER_FILES if roster_ok and not roster_gaps.get(f)),
            "rows": len(roster_rows_),
            "divergence": [list(x) for x in roster_flips],
            "declared": None if not flips else (declared_why or "matched"),
        },
        "scenarios": len(grid),
        "steps": len(grid) * len(HOURS),
        "intents_compared": placed,
        "problems": problems + flips,
        # changed scripts that are reviewed exceptions (ops/release/not_money_scripts.txt)
        "not_money_scripts": not_money,
        # the manifest changed only in TASK rows that name nothing money (manifest_is_money)
        "not_money_manifest": rows_only,
        # installers MEASURED by their own text (installer_problems): every target vouched for
        "installers_measured": sorted(installers),
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
    why = (rep.get("fusion_roster") or {}).get("declared")
    if why:
        print(f"FUSION-ROSTER declaration: {why}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
