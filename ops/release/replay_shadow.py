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


# ------------------------------------------------------------- box-task installers (#1107)
#: A BOX-TASK INSTALLER IS MEASURED BY THE ONE THING IT SCHEDULES (2026-11-13; the Auditor's
#: ruling on #1107: no false-fail and no not_money_scripts.txt listing). An installer is a .ps1
#: under SCRIPT_DIRS, so it stays money path (is_money) and reads UNMEASURED unless
#: `installer_target` shows, from its text alone (nothing is run), that:
#:   - every code line is inside a fixed vocabulary (INSTALLER_CMDLETS at command position,
#:     INSTALLER_ENUMS as parameter values, literals, variables, `-f` formats, `if`/`else`
#:     blocks): no other command or alias, no redirection, call operator, subexpression, script
#:     block, method call (but the Date arithmetic), here-string or non-ASCII character;
#:   - it registers ONE task under ONE literal name, through exactly one New-ScheduledTaskAction
#:     whose -Execute / -Argument / -WorkingDirectory evaluate, through the variables the script
#:     assigns (each once), to one fixed command line that runs EXACTLY ONE file of the tree. That
#:     file must be a Python module, or a .cmd runner outside MONEY_PATH and SCRIPT_DIRS that is
#:     read the same way to the one .py it runs. Zero files, two, a script, or anything that does
#:     not evaluate: UNMEASURED;
#:   - no code line but that registration and the Unregister of the same name is DYNAMIC.
#: The module is MONEY when it is in the base's closure, an entry point or under MONEY_PATH; when
#: its path, the installer's text, the runner's text or the command line names a venue or state
#: word (MONEY_WORDS, STATE_WORDS); when its own import closure in the PR's tree reaches MONEY_PATH
#: or an entry point, names an entry point, or starts processes or imports dynamically; or when
#: the task is a row of a money lane in either tree's manifest. A money module is measured only
#: when the base's replay imported it; a control-plane task (components.py) never is.
INSTALLER_CMDLETS = frozenset(
    c.lower()
    for c in (
        "New-ScheduledTaskAction", "New-ScheduledTaskTrigger", "New-ScheduledTaskSettingsSet",
        "New-ScheduledTaskPrincipal", "Register-ScheduledTask", "Unregister-ScheduledTask",
        "Get-ScheduledTask", "Get-ScheduledTaskInfo", "New-TimeSpan", "Get-Date", "Join-Path",
        "Resolve-Path", "Split-Path", "Test-Path", "New-Item", "Out-Null", "Write-Host",
        "Get-Command",
    )
)  # fmt: skip
INSTALLER_ENUMS = frozenset(
    e.lower()
    for e in (
        "IgnoreNew", "Parallel", "Queue", "ServiceAccount", "S4U", "Interactive", "Highest",
        "Limited", "Directory", "SilentlyContinue", "Stop", "SYSTEM",
    )
)  # fmt: skip
_PS_KEYWORDS = frozenset({"if", "else", "throw", "exit", "param"})
#: The cmdlets that name a task: each must name it by -TaskName (never a pipeline or an object).
_TASK_CMDLETS = frozenset(
    {"register-scheduledtask", "unregister-scheduledtask", "get-scheduledtask",
     "get-scheduledtaskinfo"}
)  # fmt: skip
_PS_METHODS = frozenset({".addhours", ".addminutes", ".adddays", ".addseconds"})
#: Variables an installer may never assign: automatic, preference and environment variables
#: change what the cmdlets above do.
_PS_RESERVED = frozenset({"psscriptroot", "pscommandpath", "psdefaultparametervalues", "args",
                          "input", "this", "_", "true", "false", "null", "home", "pwd", "host",
                          "myinvocation", "executioncontext", "profile", "pshome"})  # fmt: skip
_PS_TOKEN = re.compile(
    r"(?P<nl>`?\r?\n)|(?P<ws>[ \t]+)"
    r"|(?P<sq>'(?:[^'\n]|'')*')"
    r'|(?P<dq>"(?:[^"`\n$]|`[^\n]|""|\$(?![({]))*")'
    r"|(?P<var>\$(?:env:)?[A-Za-z_]\w*)"
    r"|(?P<type>\[(?:switch|string|int|TimeSpan)\](?:::Zero)?)"
    r"|(?P<index>\[\d+\])"
    r"|(?P<prop>\.[A-Za-z_]\w*)"
    r"|(?P<param>-[A-Za-z]\w*(?::\$(?:true|false))?)"
    r"|(?P<num>\d+)"
    r"|(?P<punct>[(){},=|@])"
    r"|(?P<word>[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z][A-Za-z0-9]*)?(?:\.exe)?)",
    re.IGNORECASE,
)
#: The repository's root inside an evaluated path: a NUL, which no file's text can hold (_text
#: drops them), so no string an installer writes can pose as it.
_REPO = "\x00repo"
#: The box's checkout, the one absolute root a command line may name.
_BOX_ROOT = "c:\\opt\\quant"
_PY_EXE = re.compile(r"(python[0-9.]*|pythonw|py)(\.exe)?", re.IGNORECASE)
_PS_EXE = re.compile(r"(powershell|pwsh)(\.exe)?", re.IGNORECASE)
_PY_FLAGS = frozenset({"-u", "-B", "-I", "-E", "-s", "-S", "-3", "-O"})
_PLAIN_ARG = re.compile(r"-{0,2}[A-Za-z0-9][A-Za-z0-9_.=,-]*")
_SCRIPTISH = (*SCRIPT_EXTS, ".py", ".pyw", ".exe", ".dll", ".lnk")
#: Severity order: the first kinds are measured, the rest UNMEASURED.
INSTALLER_MEASURED = ("no_order_path_change", "money_target_replayed")
_INSTALLER_KINDS = (
    *INSTALLER_MEASURED, "money_target_unreplayed", "control_plane_task", "target_not_module",
    "dynamic_line", "unresolved_target", "outside_vocabulary", "unreadable",
)  # fmt: skip


def _ps_tokens(code: str) -> list[tuple[str, str, int]] | None:
    """(kind, text, line) for every token of `code`, or None when anything is outside the
    vocabulary's characters (an unknown character, an unclosed or line-spanning string)."""
    out: list[tuple[str, str, int]] = []
    pos, line = 0, 0
    while pos < len(code):
        m = _PS_TOKEN.match(code, pos)
        if not m or m.end() == pos:
            return None
        kind = m.lastgroup or ""
        if kind == "var" and code[m.end() : m.end() + 1] == "(":
            return None  # $x(...): nothing is invoked
        if kind != "ws":
            out.append((kind, m.group(), line))
        line += m.group().count("\n")
        pos = m.end()
    return out


def _ps_group(toks: list[tuple[str, str, int]], i: int) -> int:
    """The index just past the operand that starts at `i`: a balanced (...) group or one token,
    with the .property / [index] tokens that follow it. -1 when it does not close."""
    if i >= len(toks):
        return -1
    if toks[i][1] in ("(", "@"):
        j = i + 1 if toks[i][1] == "(" else i + 2
        depth = 1
        while j < len(toks) and depth:
            depth += {"(": 1, ")": -1}.get(toks[j][1], 0)
            j += 1
        if depth:
            return -1
    else:
        j = i + 1
    while j < len(toks) and toks[j][0] in ("prop", "index"):
        j += 1
    return j


def _ps_value(toks: list[tuple[str, str, int]], env: dict[str, str | None]) -> str | None:
    """The string an expression evaluates to, for the few shapes an installer builds paths and
    command lines with; None for anything else (never a guess)."""
    if not toks:
        return None
    kinds = [k for k, _, _ in toks]
    texts = [t for _, t, _ in toks]
    low = [t.lower() for t in texts]
    if len(toks) == 1:
        if kinds[0] == "sq":
            return texts[0][1:-1].replace("''", "'")
        if kinds[0] == "dq" and not re.search(r"[$`]", texts[0]):
            return texts[0][1:-1].replace('""', '"')
        if kinds[0] == "var":
            return env.get(texts[0][1:].lower())
        return None
    if texts[0] == "(" and _ps_group(toks, 0) == len(toks):
        end = len(toks)
        while kinds[end - 1] == "prop":
            end -= 1
        inner, props = toks[1 : end - 1], low[end:]
        if props == [".path"] and inner and inner[0][1].lower() == "resolve-path":
            v = _ps_value(inner[1:], env)
            return _norm_win(v) if v is not None else None
        if props == [".source"] and [t.lower() for _, t, _ in inner] in (
            ["get-command", "powershell.exe"],
            ["get-command", "pwsh.exe"],
        ):
            return inner[1][1]
        return _ps_value(inner, env) if not props else None
    if low[0] == "resolve-path":
        v = _ps_value(toks[1:], env)
        return _norm_win(v) if v is not None else None
    if low[0] == "join-path":
        a = _ps_group(toks, 1)
        if a < 0 or _ps_group(toks, a) != len(toks):
            return None
        x, y = _ps_value(toks[1:a], env), _ps_value(toks[a:], env)
        return None if x is None or y is None else f"{x}\\{y}"
    if kinds[0] == "sq" and low[1:2] == ["-f"]:
        args: list[str] = []
        i = 2
        while i < len(toks):
            j = _ps_group(toks, i)
            v = _ps_value(toks[i:j], env) if j > i else None
            if v is None:
                return None
            args.append(v)
            if j < len(toks) and texts[j] != ",":
                return None
            i = j + 1
        fmt = texts[0][1:-1].replace("''", "'")
        try:
            return re.sub(
                r"\{\{|\}\}|\{(\d+)\}",
                lambda m: args[int(m.group(1))] if m.group(1) else m.group()[0],
                fmt,
            )
        except IndexError:
            return None
    return None


def _norm_win(path: str) -> str | None:
    """A path under the repository marker with `.` and `..` resolved (None when it climbs out);
    any other path unchanged."""
    if not path.startswith(_REPO):
        return path
    parts: list[str] = []
    for seg in re.split(r"[\\/]", path[len(_REPO) :]):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(seg)
    return "\\".join((_REPO, *parts))


def _repo_file(token: str, wd: str | None = None) -> str | None:
    """The repo-relative path a command-line token names: under the repository marker or the
    box's checkout, or relative to a known working directory. None for anything else."""
    t = token
    if t.lower().startswith(_BOX_ROOT + "\\"):
        t = _REPO + t[len(_BOX_ROOT) :]
    elif not t.startswith(_REPO):
        if wd is None or not re.fullmatch(r"[A-Za-z0-9_][\w.\\/-]*", t):
            return None
        t = f"{wd}\\{t}"
    n = _norm_win(t)
    if n is None or not n.startswith(_REPO):
        return None
    return n[len(_REPO) :].replace("\\", "/").strip("/") or None


def _split_cmd(line: str) -> list[str] | None:
    """Whitespace-separated words, a "double-quoted" word kept whole; None for a stray quote."""
    out = []
    for m in re.finditer(r'"([^"]*)"|(\S+)', line):
        word = m.group(1) if m.group(1) is not None else m.group(2)
        if m.group(2) is not None and '"' in word:
            return None
        out.append(word)
    return out


def _command_file(words: list[str], wd: str | None, files: set[str]) -> str | None:
    """The ONE tree file a command runs: an interpreter's script or `-m` module, PowerShell's
    -File, or the program itself; every other word a plain flag or value. None otherwise."""
    if not words:
        return None
    prog = _repo_file(words[0])
    rest: list[str]
    if prog is not None:
        target, rest = prog, words[1:]
    elif _PY_EXE.fullmatch(re.split(r"[\\/]", words[0])[-1]):
        i = 1
        while i < len(words) and words[i] in _PY_FLAGS:
            i += 1
        if i + 1 < len(words) and words[i] == "-m":
            dotted = words[i + 1]
            if not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", dotted):
                return None
            rel = dotted.replace(".", "/")
            roots = {r for r in (*IMPORT_ROOTS, _repo_file(wd) if wd else None) if r is not None}
            if wd is not None and wd.rstrip("\\") == _REPO:
                roots.add("")
            found = {
                c
                for r in roots
                for c in (f"{r}/{rel}.py".lstrip("/"), f"{r}/{rel}/__main__.py".lstrip("/"))
                if c in files
            }
            if len(found) != 1:
                return None
            target, rest = found.pop(), words[i + 2 :]
        elif i < len(words):
            f = _repo_file(words[i], wd)
            if f is None or not f.endswith(".py"):
                return None
            target, rest = f, words[i + 1 :]
        else:
            return None
    elif _PS_EXE.fullmatch(re.split(r"[\\/]", words[0])[-1]):
        i = 1
        while i < len(words) and words[i].lower() in ("-noprofile", "-noninteractive", "-nologo"):
            i += 1
        if i + 1 < len(words) and words[i].lower() == "-executionpolicy":
            if words[i + 1].lower() not in ("bypass", "remotesigned", "allsigned"):
                return None
            i += 2
        if i + 1 >= len(words) or words[i].lower() != "-file":
            return None
        f = _repo_file(words[i + 1], wd)
        if f is None:
            return None
        target, rest = f, words[i + 2 :]
    else:
        return None
    if target not in files:
        return None
    for w in rest:  # a plain flag or value: never a path, a script or a second program
        if not _PLAIN_ARG.fullmatch(w) or w.lower().endswith(_SCRIPTISH):
            return None
    return target


def _shadowed(program: str, wd: str | None, files: set[str]) -> bool:
    """Whether a bare program name (no directory) could run a file of the tree: cmd.exe and
    CreateProcess look in the working directory before the system's, so a `py.cmd` beside the
    task's working directory would run instead of the interpreter."""
    if re.search(r"[\\/]", program) or wd is None:
        return False
    norm = _norm_win(wd)
    if norm is None or not norm.startswith(_REPO):
        return True
    here = norm[len(_REPO) :].replace("\\", "/").strip("/")
    name = program.casefold()
    return any(
        (f.rsplit("/", 1)[0] if "/" in f else "") == here
        and (
            Path(f).name.casefold() == name or ("." not in name and Path(f).stem.casefold() == name)
        )
        for f in files
    )


def _cmd_line(exe: str, arg: str, wd: str | None, files: set[str]) -> str | None:
    """The one tree file a task action runs (`exe` with `arg`, both evaluated)."""
    if _shadowed(exe, wd, files):
        return None
    if re.split(r"[\\/]", exe)[-1].lower() in ("cmd", "cmd.exe"):
        m = re.fullmatch(r"((?:/[dDsS]\s+)*)/[cC]\s+(.*)", arg.strip(), re.DOTALL)
        if not m:
            return None
        rest = m.group(2).strip()
        if "s" in m.group(1).lower():
            if len(rest) < 2 or rest[0] != '"' or rest[-1] != '"':
                return None
            inner = rest[1:-1]
        elif re.fullmatch(r'"[^"]+"', rest):
            inner = rest
        else:
            return None
        inner = re.sub(r'\s*>>\s*"[^"&|<>^%!()\r\n]+\.log"\s+2>&1\s*$', "", inner)
        if re.search(r"[&|<>^%!()`;\r\n]", inner):
            return None
        words = _split_cmd(inner)
        if words and _shadowed(words[0], wd, files):
            return None
    else:
        if re.search(r"[&|<>^%!()`;\r\n]", arg):
            return None
        words = _split_cmd(f'"{exe}" {arg}' if '"' not in exe else "")
    return _command_file(words, wd, files) if words else None


def _runner_module(tree: Path, runner: str, files: set[str]) -> tuple[str | None, str]:
    """(the one .py a .cmd runner runs, its text). The runner may hold only `@echo off`, `rem`,
    `set "LOG=<x>.log"`, `set "PYTHONPATH=<the box's import roots>"`, `exit /b`, and ONE
    interpreter line; anything else, or a second line that runs something, resolves to None."""
    text = read(tree, runner)
    if text is None:
        return None, ""
    env: dict[str, str] = {}
    runs: list[str] = []
    roots = {"\\".join(x for x in (_BOX_ROOT, r.replace("/", "\\")) if x) for r in IMPORT_ROOTS}
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        low = s.lower()
        if not s.isascii() or "^" in s:
            return None, text
        if low == "@echo off" or re.match(r"rem(\s|$)", low):
            continue
        m = re.fullmatch(r'set "([A-Za-z_]\w*)=([^"%&|<>^!()]*)"', s)
        if m:
            name, value = m.group(1).upper(), m.group(2)
            if name in env or name not in ("LOG", "PYTHONPATH"):
                return None, text
            if name == "LOG" and not value.lower().endswith(".log"):
                return None, text
            if name == "PYTHONPATH" and not {v.lower() for v in value.split(";")} <= roots:
                return None, text
            env[name] = value
            continue
        if re.fullmatch(r"exit /b (%errorlevel%|\d+)", low):
            continue
        runs.append(s)
    if len(runs) != 1:
        return None, text
    line = runs[0]
    if "LOG" in env:
        line = re.sub(r'\s*>>\s*"?%LOG%"?\s+2>&1\s*$', "", line, flags=re.IGNORECASE)
    if re.search(r"[&|<>^%!()`;]", line):
        return None, text
    words = _split_cmd(line)
    if not words or not _PY_EXE.fullmatch(re.split(r"[\\/]", words[0])[-1]):
        return None, text
    target = _command_file(words, None, files)
    return (target if target and target.endswith(".py") else None), text


def _parse_installer(text: str, path: str, files: set[str]) -> tuple[str, str, str] | str:
    """(the task's name, the one tree file its action runs, the evaluated command line), or the
    kind that stops it."""
    lines = text.splitlines()
    code = "\n".join("" if ln.lstrip().startswith("#") else ln for ln in lines)
    if not code.isascii() or "@'" in code or '@"' in code or "<#" in code:
        return "outside_vocabulary"
    toks = _ps_tokens(code)
    if toks is None:
        return "outside_vocabulary"
    sig = [t for t in toks if t[0] != "nl" or not t[1].startswith("`")]
    # the vocabulary, token by token
    opener: list[str] = []  # the open parentheses
    prev: tuple[str, str, int] | None = None
    for i, (kind, text_, _) in enumerate(sig):
        low = text_.lower()
        cmd_pos = prev is None or prev[0] == "nl" or prev[1] in ("(", "{", "}", "|", "=")
        if kind == "word":
            if cmd_pos:
                if low not in INSTALLER_CMDLETS and low not in _PS_KEYWORDS:
                    return "outside_vocabulary"
            elif not (
                (prev is not None and prev[0] == "param" and low in INSTALLER_ENUMS)
                or (prev is not None and prev[1].lower() == "get-command"
                    and low in ("powershell.exe", "pwsh.exe"))
            ):  # fmt: skip
                return "outside_vocabulary"
        elif kind == "prop" and i + 1 < len(sig) and sig[i + 1][1] == "(":
            if low not in _PS_METHODS:
                return "outside_vocabulary"
        elif kind == "punct":
            if text_ == "(":
                opener.append("(")
            elif text_ == ")":
                if not opener:
                    return "outside_vocabulary"
                opener.pop()
            elif text_ == "{":
                if not (prev is not None and (prev[1].lower() == "else" or (
                        prev[1] == ")" and _if_paren(sig, i - 1)))):  # fmt: skip
                    return "outside_vocabulary"  # a script block is never data here
            elif text_ == "|":
                if i + 1 >= len(sig) or sig[i + 1][1].lower() != "out-null":
                    return "outside_vocabulary"
            elif text_ == "@":
                j = _ps_group(sig, i)
                if (
                    j < 0
                    or i + 1 >= len(sig)
                    or sig[i + 1][1] != "("
                    or any(
                        k not in ("var", "punct") or (k == "punct" and t not in ",")
                        for k, t, _ in sig[i + 2 : j - 1]
                    )
                ):
                    return "outside_vocabulary"
            elif text_ == "=" and (prev is None or not (
                    (prev[0] == "var" and not prev[1].lower().startswith("$env:")
                     and prev[1][1:].lower() not in _PS_RESERVED
                     and not re.match(r"ps.", prev[1][1:], re.IGNORECASE)
                     and (not prev[1].lower().endswith("preference")
                          or prev[1].lower() == "$erroractionpreference"))
                    or (prev[0] == "prop" and prev[1].lower() == ".repetition")
            )):  # fmt: skip
                return "outside_vocabulary"
        prev = (kind, text_, 0) if kind != "nl" else ("nl", "\n", 0)
    if opener:
        return "outside_vocabulary"
    stmts = _ps_statements(sig)
    # one action, one registration, at most one Unregister; New-Item only makes a directory
    every = [t[1].lower() for t in sig if t[0] == "word"]
    if every.count("new-scheduledtaskaction") != 1 or every.count("register-scheduledtask") != 1:
        return "unresolved_target"
    if every.count("unregister-scheduledtask") > 1:
        return "unresolved_target"
    for s in stmts:
        low_s = [t[1].lower() for t in s]
        if {"-inputobject", "-cimsession"} & set(low_s):
            return "unresolved_target"  # a task named by anything but its one literal name
        if sum(x in _TASK_CMDLETS for x in low_s) > low_s.count("-taskname"):
            return "unresolved_target"
        if "new-item" in low_s:
            k = low_s.index("new-item")
            if low_s[k + 1 : k + 3] != ["-itemtype", "directory"] or "-value" in low_s:
                return "outside_vocabulary"
    # the variables, each assigned once
    env: dict[str, str | None] = {
        "psscriptroot": _REPO + "\\" + str(Path(path).parent).replace("/", "\\")
    }
    seen: set[str] = set()
    action_var = None
    action: list[tuple[str, str, int]] = []
    for s in stmts:
        if s and s[0][1].lower() == "param":
            i = 2
            while i < len(s) - 1:
                if s[i][0] == "type":
                    i += 1
                if i >= len(s) or s[i][0] != "var":
                    return "outside_vocabulary"
                name = s[i][1][1:].lower()
                if name in seen:
                    return "unresolved_target"
                seen.add(name)
                j = i + 1
                if j < len(s) and s[j][1] == "=":
                    k = _ps_group(s, j + 1)
                    env[name] = _ps_value(s[j + 1 : k], env) if k > 0 else None
                    j = k
                else:
                    env[name] = None
                if j < 0 or j >= len(s):
                    return "outside_vocabulary"
                i = j + 1 if s[j][1] == "," else j
            continue
        if len(s) > 2 and s[0][0] == "var" and s[1][1] == "=":
            name = s[0][1][1:].lower()
            if name in seen:
                return "unresolved_target"  # a second value: no single command line
            seen.add(name)
            if s[2][1].lower() == "new-scheduledtaskaction":
                action_var, action = name, s[3:]
                env[name] = None
            else:
                env[name] = _ps_value(s[2:], env)
    if action_var is None:
        return "unresolved_target"
    # -TaskName: one literal name, everywhere
    tasks = set()
    for k, t in enumerate(sig):
        if t[0] == "param" and t[1].lower() == "-taskname":
            j = _ps_group(sig, k + 1)
            v = _ps_value(sig[k + 1 : j], env) if j > k + 1 else None
            if v is None:
                return "unresolved_target"
            tasks.add(v.casefold())
    if len(tasks) != 1 or re.search(r"[*?\[\]]", next(iter(tasks))):
        return "unresolved_target"  # one name, and never a wildcard
    reg = next(s for s in stmts if s and s[0][1].lower() == "register-scheduledtask")
    reg_low = [t[1].lower() for t in reg]
    if (
        reg_low.count("-action") != 1
        or reg_low[reg_low.index("-action") + 1] != f"${action_var}"
        or {"-xml", "-inputobject"} & set(reg_low)
    ):
        return "unresolved_target"
    # the action: -Execute, -Argument, -WorkingDirectory, each once and each evaluated
    got: dict[str, str | None] = {}
    i = 0
    while i < len(action):
        p = action[i][1].lower()
        if action[i][0] != "param" or p not in ("-execute", "-argument", "-workingdirectory"):
            return "unresolved_target"
        j = _ps_group(action, i + 1)
        if p in got or j < 0:
            return "unresolved_target"
        got[p] = _ps_value(action[i + 1 : j], env)
        i = j
    exe, arg = got.get("-execute"), got.get("-argument", "")
    wd = got.get("-workingdirectory")
    if exe is None or arg is None or ("-workingdirectory" in got and wd is None):
        return "unresolved_target"
    wd_norm = _norm_win(wd) if wd is not None else None
    if wd is not None and (wd_norm is None or not wd_norm.startswith(_REPO)):
        return "unresolved_target"
    # DYNAMIC: only the registration's own lines, and the Unregister of the same name
    allowed = set()
    for s in stmts:
        if s and s[0][1].lower() in ("register-scheduledtask", "unregister-scheduledtask"):
            allowed |= set(range(s[0][2], s[-1][2] + 1))
    for n, ln in enumerate(code.splitlines()):
        if DYNAMIC.search(ln) and n not in allowed:
            return "dynamic_line"
    target = _cmd_line(exe, arg, wd_norm, files)
    if target is None:
        return "unresolved_target"
    return tasks.pop(), target, f"{exe} {arg}"


def _if_paren(sig: list[tuple[str, str, int]], close: int) -> bool:
    """Whether the ")" at `close` ends an `if (...)` condition."""
    depth = 0
    for k in range(close, -1, -1):
        depth += {")": 1, "(": -1}.get(sig[k][1], 0)
        if depth == 0:
            return k > 0 and sig[k - 1][1].lower() == "if"
    return False


def _ps_statements(sig: list[tuple[str, str, int]]) -> list[list[tuple[str, str, int]]]:
    """Statements: split at a newline outside parentheses, and at { and }."""
    out: list[list[tuple[str, str, int]]] = [[]]
    depth = 0
    for t in sig:
        depth += {"(": 1, ")": -1}.get(t[1], 0)
        if (t[0] == "nl" and depth == 0) or t[1] in ("{", "}"):
            out.append([])
        elif t[0] != "nl":
            out[-1].append(t)
    return [s for s in out if s]


#: What a module may never do and still be called no order-path change: start a process or import
#: by name at run time (either can reach any order code with no import a scan sees).
_LAUNCH_MODULES = frozenset(
    {"subprocess", "importlib", "runpy", "pty", "multiprocessing", "concurrent", "builtins"}
)
_LAUNCH_NAMES = frozenset({"exec", "eval", "__import__", "compile", "__builtins__"})
_OS_LAUNCH = ("system", "popen", "exec", "spawn", "posix_spawn", "startfile", "fork",
              "create_subprocess")  # fmt: skip
#: Modules that are launches only through these attributes (any reference to one is a launch).
_ATTR_LAUNCH: dict[str, tuple[str, ...]] = {
    "os": _OS_LAUNCH, "posix": _OS_LAUNCH, "nt": _OS_LAUNCH,
    "asyncio": (*_OS_LAUNCH, "subprocess"),
    "psutil": ("Popen",), "sys": ("modules",),
}  # fmt: skip
#: Modules whose attributes may never be looked up by name (getattr, __getattribute__,
#: __dict__), and never passed around bare: what they hand back no scan can see (#1107 MF1).
_ROOTS_BY_NAME = frozenset({*_LAUNCH_MODULES, *_ATTR_LAUNCH, "ctypes"})
#: CTYPES (#1107 audit ruling): a launch, unless EVERY use in the file is a C type, byref, or a
#: kernel32 call from this read-only allowlist (mt5_session.py reads its Windows session id).
_CTYPES_OK = re.compile(
    r"ctypes\.(c_\w+|byref|windll\.kernel32\.(ProcessIdToSessionId|GetCurrentProcessId))"
)


def _launches(src: str) -> bool:
    """Whether Python source can start a process or import or call by name at run time
    (unparsable: True). Every import and its alias is mapped, so `import os as o; o.system`
    resolves to os.system; a by-name lookup on such a module, any reference to __builtins__,
    builtins or sys.modules, and any ctypes use outside _CTYPES_OK (or a ctypes import with no
    allowlisted use at all) are launches."""
    try:
        node = ast.parse(src)
    except (SyntaxError, ValueError):
        return True
    alias: dict[str, str] = {}
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    alias[a.asname] = a.name
                else:
                    top = a.name.split(".")[0]
                    alias[top] = top
                if a.name.split(".")[0] in _LAUNCH_MODULES:
                    return True
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if n.level:
                continue  # a relative import is the repository's own; the closure reads it
            if mod.split(".")[0] in _LAUNCH_MODULES:
                return True
            for a in n.names:
                if a.name == "*" and mod.split(".")[0] in _ROOTS_BY_NAME:
                    return True
                alias[a.asname or a.name] = f"{mod}.{a.name}"

    def dotted(e: ast.expr) -> str | None:
        if isinstance(e, ast.Name):
            return alias.get(e.id, e.id)
        if isinstance(e, ast.Attribute):
            v = dotted(e.value)
            return None if v is None else f"{v}.{e.attr}"
        return None

    def is_launch(d: str) -> bool:
        parts = d.split(".")
        if parts[0] in _LAUNCH_MODULES or parts[0] in _LAUNCH_NAMES:
            return True
        prefixes = _ATTR_LAUNCH.get(parts[0])
        return prefixes is not None and len(parts) > 1 and parts[1].startswith(prefixes)

    inner = {id(n.value) for n in ast.walk(node) if isinstance(n, ast.Attribute)}
    ctypes_uses = 0
    for n in ast.walk(node):
        if isinstance(n, ast.Name | ast.Attribute):
            d = dotted(n)
            if d is None:
                if isinstance(n, ast.Attribute) and n.attr in ("__getattribute__", "__dict__"):
                    return True
                continue
            if is_launch(d):
                return True
            parts = d.split(".")
            if parts[-1] in ("__getattribute__", "__dict__") and parts[0] in _ROOTS_BY_NAME:
                return True
            if id(n) in inner:
                continue  # judged as part of the longer chain it starts
            if parts[0] == "ctypes":
                if not _CTYPES_OK.fullmatch(d):
                    return True  # CreateProcess, CDLL, cast, or ctypes handed on bare
                ctypes_uses += 1
            if len(parts) == 1 and parts[0] in _ROOTS_BY_NAME:
                return True  # `o = os`: the module handed on, no longer readable by name
        elif isinstance(n, ast.Call) and n.args:
            f = dotted(n.func) if isinstance(n.func, ast.Name | ast.Attribute) else None
            first = dotted(n.args[0]) if isinstance(n.args[0], ast.Name | ast.Attribute) else None
            if (
                f in ("getattr", "builtins.getattr", "object.__getattribute__")
                and first is not None and first.split(".")[0] in _ROOTS_BY_NAME
            ):  # fmt: skip
                return True
    # imported and never used the allowlisted way: nothing shows what it is for
    return "ctypes" in {v.split(".")[0] for v in alias.values()} and not ctypes_uses


def _module_is_money(head: Path, module: str, closure: set[str]) -> bool:
    """Whether running `module` (in the PR's tree) can reach the order path; see the note above
    INSTALLER_CMDLETS."""
    if module in closure or module in ENTRY_POINTS or module.startswith(MONEY_PATH):
        return True
    if MONEY_WORDS.search(module) or STATE_WORDS.search(module):
        return True
    entries = _money_names(head, set())  # the entry points' own names, every form
    for f in import_closure(head, (module,)) or {module}:
        if f in ENTRY_POINTS or f.startswith(MONEY_PATH):
            return True
        src = read(head, f)
        if src is None or _launches(src) or _names_any(src.lower(), entries):
            return True
    return False


def _task_lanes(tree: Path, task: str) -> list[str] | None:
    """The lanes the manifest gives `task` in `tree` (None when it cannot be read)."""
    text = read(tree, MANIFEST)
    if text is None:
        return None
    rows = [dict(_ATTR.findall(x)) for x in text.splitlines() if x.strip().startswith("TASK ")]
    return [r.get("lane", "") for r in rows if r.get("name", "").casefold() == task]


def _installer_in(
    base: Path, head: Path, tree: Path, path: str, closure: set[str], imported: set[str]
) -> dict[str, Any]:
    """`tree`'s version of an installer, read and classified (see INSTALLER_CMDLETS); the
    control plane is the base's, and a money lane in either manifest is money."""
    out: dict[str, Any] = {"target": None, "via": None, "task": None}
    text = read(tree, path)
    if text is None:
        return {**out, "kind": "unreadable"}
    files = tree_files(tree)
    got = _parse_installer(text, path, files)
    if isinstance(got, str):
        return {**out, "kind": got}
    task, target, line = got
    out["task"] = task
    words = [text.lower(), task, line.lower()]
    if target.endswith(".py"):
        module: str | None = target
    elif (
        target.lower().endswith((".cmd", ".bat")) and not is_script(target)
        and not target.startswith(MONEY_PATH) and target not in closure
    ):  # fmt: skip
        module, runner = _runner_module(tree, target, files)
        out["via"] = target
        words.append(runner.lower())
    else:
        return {**out, "target": target, "kind": "target_not_module"}
    if module is None:
        return {**out, "kind": "unresolved_target"}
    out["target"] = module
    held = _held_tasks(base)
    if held is None or task in {t.casefold() for t in held}:
        return {**out, "kind": "control_plane_task"}
    lanes = [_task_lanes(t, task) for t in (base, head)]
    money = (
        any(MONEY_WORDS.search(w) or STATE_WORDS.search(w) for w in words)
        or any(ln is None or any(x not in _FREE_LANES for x in ln) for ln in lanes)
        or _module_is_money(tree, module, closure)
    )
    if not money:
        return {**out, "kind": "no_order_path_change"}
    replayed = module in imported
    return {**out, "kind": "money_target_replayed" if replayed else "money_target_unreplayed"}


def installer_targets(
    base: Path, head: Path, changed: list[str], closure: set[str], imported: set[str]
) -> dict[str, dict[str, Any]]:
    """{installer: {target, via, kind}} for every changed .ps1 under SCRIPT_DIRS that registers a
    scheduled task. `target` and `via` are repo-relative paths (or None); `kind` is one of
    _INSTALLER_KINDS, and only INSTALLER_MEASURED kinds are measured. An installer the base also
    holds is judged on both versions (the same task, and the worse kind)."""
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(changed):
        if not (is_script(f) and f.lower().endswith(".ps1")):
            continue
        texts = [read(t, f) for t in (base, head)]
        if not any(t and "register-scheduledtask" in t.lower() for t in texts):
            continue
        now = _installer_in(base, head, head, f, closure, imported)
        if texts[0] is not None:
            was = _installer_in(base, head, base, f, closure, imported)
            if was["task"] != now["task"] or was["target"] != now["target"]:
                now = {**now, "kind": max(now["kind"], "unresolved_target",
                                          key=_INSTALLER_KINDS.index)}  # fmt: skip
            else:
                now["kind"] = max(now["kind"], was["kind"], key=_INSTALLER_KINDS.index)
        out[f] = {k: now[k] for k in ("target", "via", "kind")}
    return out


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
    installers: frozenset[str] = frozenset(),
) -> bool:
    """Whether the change to MANIFEST is money path. Comments and blank lines are prose. Every
    other added or removed line must be a TASK row whose raw text names no venue, state or
    money-path name, and whose runs, also_runs and installer are each a file that is not money
    path (a script under SCRIPT_DIRS only when `exempt` clears it). An `installer` attribute may
    also name one of `installers`: the PR's installers `installer_targets` measured as no
    order-path change, and only there (never as `runs` or `also_runs`). Anything else, or a tree
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
        n for m in money - installers for n in (Path(m).name.lower(), Path(m).stem.lower())
    }  # fmt: skip
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
        paths = [(k, p.strip()) for k in ("runs", "also_runs", "installer")
                 for p in attrs.get(k, "").split(",") if p.strip()]  # fmt: skip
        for k, p in paths:
            if not _PLAIN_PATH.fullmatch(p) or any(seg in ("", ".", "..") for seg in p.split("/")):
                return True  # only a plain repo path is compared as the file it names (v3 MF1)
            if k == "installer" and p in installers:
                continue  # measured: it schedules one module that is no order path (#1107)
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


FTMO_EXECUTOR = "desks/mt5/prop/ftmo_executor.py"


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
    closure = import_closure(base)
    covered = imported | new_and_bounded(base, head, head_imported)
    exempt = exempt_scripts((base, head), closure)
    money = money_scripts((base, head), closure)
    installers = installer_targets(base, head, changed, closure, imported)
    measured = {f for f, v in installers.items() if v["kind"] in INSTALLER_MEASURED}
    clear = frozenset(f for f in measured if installers[f]["kind"] == INSTALLER_MEASURED[0])
    rows_only = MANIFEST in changed and not manifest_is_money(
        base, head, closure, money, exempt, clear
    )
    uncovered = sorted(
        f for f in changed
        if is_money(f, closure, exempt=exempt) and f not in covered and f not in measured
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
        # each changed box-task installer: the one module it schedules (`target`, through the
        # .cmd runner `via`), and its kind; only INSTALLER_MEASURED kinds are measured (#1107)
        "installer_targets": installers,
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
