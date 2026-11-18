"""RED-TEAM THE NEVER-RUN ORGANS: run each NO_CLOCK organ once, bounded, and record what happened.

    py -3 desks/mt5/research/organ_redteam.py                 # one pass: up to 3 organs
    py -3 desks/mt5/research/organ_redteam.py --per-pass 5 --cap-s 60
    py -3 desks/mt5/research/organ_redteam.py --plan-only     # classify the rotation, run nothing

`scripts/check_dead_architecture.py` names every organ that SOMETHING READS and NOTHING RUNS
(NO_CLOCK: 297 of 796 on 2026-11-18). Each is a claim the desk cannot cash: a reader trusts a file
whose writer has not been started, perhaps for months, and nobody knows whether that writer still
imports, still finds its inputs, or crashes on line one. Build-check row 13 ("red-team the 760
never-run organs") asked for the cheapest possible answer: start each one, once, and write down
whether it lived.

ONE PASS, BOUNDED ON EVERY AXIS:
  * a ROTATION. The cursor is the NAME of the next organ (not an index), so a census that gains or
    loses organs between passes moves the cursor to the next name rather than skipping a stretch.
  * a HARD TIME CAP per organ, enforced by killing the whole process tree (`libs.ops.proctree`
    kill_tree -- L0373: `subprocess.run(timeout=)` kills only the child and leaks its pool).
  * a MEMORY GUARD: the tree's RSS is polled and the tree killed above a cap DERIVED from the
    machine's free memory (never a hard-coded figure: the two boxes differ twelve-fold), and the
    pass stands down entirely when free memory cannot cover the cap twice.
  * a DRY or READ-ONLY flag whenever the organ's own argparse declares one.

WHAT IS NEVER STARTED (the denylist, each reason pinned by a test):
  * anything under desks/mt5/scripts/ (the box's own launchers);
  * anything on the money path (ops/money_closure.txt), and the gateway package;
  * anything whose source can place, close or cancel an order or talk to the terminal;
  * anything that mutates git, the scheduler or a service (commit/push/checkout, schtasks,
    systemctl ...) -- tracked state is changed by its own organ on its own clock, never here;
  * orchestrators that would start the cycle again (hourly_cycle, controllers, residents);
  * an organ whose named artifact is a TRACKED file, unless it declares a dry/read-only flag;
  * an organ that, once run, left a tracked path changed that was clean before: it goes to the
    QUARANTINE list in the report and is never started again by this organ (the change itself is
    left for a person -- reverting here could destroy another writer's work).

OUTCOMES (exactly these): ran_ok / crashed (exception TYPE only, never the message: a message can
carry a path, a key fragment or an account number) / no_output / timeout / skipped_denylisted.
Report only. Nothing is retired, scheduled or repaired by this file; it is the evidence a person
or the clock-enrolment organ acts on.

Writes desks/mt5/reports/ORGAN_REDTEAM.json.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = DESK / "reports" / "dead_architecture.json"
OUT = DESK / "reports" / "ORGAN_REDTEAM.json"
MONEY_CLOSURE = ROOT / "ops" / "money_closure.txt"
SELF = "desks/mt5/research/organ_redteam.py"

RAN_OK, CRASHED, NO_OUTPUT, TIMEOUT, SKIPPED = (
    "ran_ok", "crashed", "no_output", "timeout", "skipped_denylisted")
OUTCOMES = (RAN_OK, CRASHED, NO_OUTPUT, TIMEOUT, SKIPPED)

PER_PASS = 3
CAP_S = 45.0
BUDGET_S = 200.0
#: The memory cap is a quarter of what is free right now, inside these bounds. The floor keeps a
#: plain import-and-read organ runnable on the 8 GB build box; the ceiling keeps one stray organ
#: from taking the trading box's headroom from the legs that matter.
MEM_SHARE = 0.25
MEM_FLOOR_MB = 256
MEM_CEIL_MB = 2048

#: PATH PREFIXES never started. desks/mt5/scripts/ is the box's launcher tree (order tools, task
#: installers, the adopt-and-seal path); ops/ is release, push and unit plumbing; mt5desk/ is the
#: gateway's own package; _retired/ is retired on purpose.
DENY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("desks/mt5/scripts/", "box_scripts_dir"),
    ("desks/mt5/mt5desk/", "gateway_package"),
    ("ops/", "ops_plumbing"),
    ("scripts/_retired/", "retired"),
)
#: A `_retired` directory anywhere is retired on purpose: never started again.
RETIRED_SEGMENT = "/_retired/"
#: ORCHESTRATORS: starting one would start the cycle (or a resident) again from inside it.
DENY_NAME = re.compile(r"(hourly_cycle|hourly_controller|nightly_catchup|department_resident|"
                       r"supervisor|gateway|run_law_gate|adopt|release|deadman|organ_redteam)",
                       re.IGNORECASE)
#: SOURCE TOKENS that mean the organ can reach the broker or the terminal.
DENY_BROKER = re.compile(r"(order_send|OrderSend|order_check|positions_close|close_position|"
                         r"place_order|cancel_order|TRADE_ACTION_|MetaTrader5|"
                         r"mt5\.initialize|mt5\.login|terminal_path|terminal64|Mt5TickSource|"
                         r"recorders\.tick_source|mt5_session)")
#: SOURCE TOKENS that mutate git, the scheduler or a service.
DENY_MUTATE = re.compile(
    r"""["']git["']\s*,\s*["'](?:commit|push|checkout|reset|stash|merge|rebase|add|rm|restore|"""
    r"""apply|clean|pull|tag|switch|cherry-pick|revert|worktree|update-ref)["']|"""
    r"""git\s+(?:commit|push|checkout|reset|stash|merge|rebase|restore|clean|pull)\b|"""
    r"""schtasks|Register-ScheduledTask|Unregister-ScheduledTask|systemctl|Stop-Process|"""
    r"""shutil\.rmtree\(\s*ROOT""")
#: Flags an organ may declare that make it read-only or dry, in order of preference.
DRY_FLAGS = ("--dry-run", "--read-only", "--readonly", "--no-write", "--dry", "--report-only",
             "--check")
_FLAG_DECL = re.compile(r"""add_argument\(\s*["'](--[\w-]+)["']""")
_MAIN = re.compile(r"""^if\s+__name__\s*==\s*["']__main__["']\s*:""", re.MULTILINE)
_EXC = re.compile(r"^([A-Za-z_][\w.]*"
                  r"(?:Error|Exception|Exit|Interrupt|Fault|Warning|Refused))(?::|\s*$)")
#: Where an organ's named artifact lands when it is not tracked (gitignored reports and data).
ARTIFACT_DIRS = ("desks/mt5/reports", "desks/mt5/data", "reports", "data", "docs/research")


#: THE WRITE GUARD, the prevention half (the git-status drift check is the detection half). The
#: organ is started through this bootstrap, which installs a `sys.addaudithook` before running the
#: organ as __main__: every write-mode open, rename, replace, remove or truncate of a path INSIDE
#: the repository is refused with TrackedStateWriteRefused unless it lands under a `reports/`
#: directory (gitignored as `**/reports/*`) on a path git does not track. Writes outside the
#: repository (temp, caches) pass. Each refusal is appended to `_refused` in the sandbox, so an
#: organ that swallows the PermissionError is still seen to have tried. Measured 2026-11-18 on
#: the first real pass: alpha_genome.py appended to the TRACKED data/preregistrations.jsonl
#: through an imported donation helper -- no filename literal the static gate could see.
BOOTSTRAP = r"""
import os, sys, runpy
_ROOT = os.path.normcase(os.path.abspath(os.environ["QUANT_REDTEAM_ROOT"]))
_SANDBOX = os.environ["QUANT_REDTEAM_SANDBOX"]
with open(os.environ["QUANT_REDTEAM_TRACKED"], encoding="utf-8") as _f:
    _TRACKED = frozenset(ln.strip() for ln in _f if ln.strip())
_W = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_busy = [False]
class TrackedStateWriteRefused(PermissionError):
    pass
def _norm(p):
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    if not isinstance(p, (str, os.PathLike)):
        return None
    return os.path.normcase(os.path.abspath(os.fspath(p)))
def _refuse(p):
    n = _norm(p)
    if n is None or not (n == _ROOT or n.startswith(_ROOT + os.sep)):
        return False
    parts = n[len(_ROOT):].split(os.sep)
    return not ("reports" in parts and n not in _TRACKED)
def _hook(event, args):
    if _busy[0]:
        return
    paths = ()
    if event == "open":
        mode, flags = args[1], args[2]
        w = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            mode is None and isinstance(flags, int) and bool(flags & _W))
        paths = (args[0],) if w else ()
    elif event in ("os.rename", "os.link", "os.symlink"):
        paths = (args[0], args[1])
    elif event in ("os.remove", "os.rmdir", "os.truncate", "shutil.rmtree", "sqlite3.connect"):
        paths = (args[0],)
    for p in paths:
        if _refuse(p):
            _busy[0] = True
            try:
                with open(os.path.join(_SANDBOX, "_refused"), "a", encoding="utf-8") as f:
                    f.write(os.path.relpath(_norm(p), _ROOT) + "\n")
            finally:
                _busy[0] = False
            raise TrackedStateWriteRefused(f"organ_redteam: repository write refused: {event}")
_organ = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path[0] = os.path.dirname(os.path.abspath(_organ))
sys.addaudithook(_hook)
runpy.run_path(_organ, run_name="__main__")
"""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def money_closure(path: Path = MONEY_CLOSURE) -> frozenset[str]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(ln.strip() for ln in lines if ln.strip() and not ln.startswith("#"))


def tracked_files(root: Path = ROOT) -> list[str] | None:
    """Every tracked path (repo-relative), or None when git cannot answer."""
    try:
        cp = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                            timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return None
    return [p for p in cp.stdout.decode("utf-8", "replace").split("\0") if p]


def tracked_basenames(files: Sequence[str] | None) -> frozenset[str] | None:
    """Basenames of every tracked file; None when git cannot answer (then ALL count as tracked)."""
    return None if files is None else frozenset(p.rsplit("/", 1)[-1] for p in files)


def tracked_dirty(root: Path = ROOT) -> frozenset[str] | None:
    """Tracked paths modified, and NEW files git would see, right now; None when git cannot answer.

    Untracked-but-not-ignored files count: a new file under a box state path is committed by the
    box's next sync, so it is tracked state in all but name.
    """
    try:
        cp = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal", "-z"],
                            cwd=root, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return None
    return frozenset(e[3:] for e in cp.stdout.decode("utf-8", "replace").split("\0") if len(e) > 3)


def classify(organ: str, source: str | None, artifacts: Sequence[str], *,
             money: frozenset[str], tracked: frozenset[str] | None,
             quarantine: Iterable[str] = ()) -> dict[str, Any]:
    """Decide whether `organ` may be started, and how. Pure: every input is passed in.

    Returns {"run": bool, "reason": str, "args": [...], "mode": str}. `run` is False with a reason
    for every denylist hit; True with the dry flag (if any) it will be started under.
    """
    def deny(reason: str) -> dict[str, Any]:
        return {"run": False, "reason": reason, "args": [], "mode": "none"}

    rel = organ.replace("\\", "/").lstrip("./")
    for prefix, reason in DENY_PREFIXES:
        if rel.startswith(prefix):
            return deny(reason)
    if RETIRED_SEGMENT in f"/{rel}":
        return deny("retired")
    if rel in money:
        return deny("money_path")
    if rel in set(quarantine):
        return deny("quarantined_tracked_drift")
    if DENY_NAME.search(rel.rsplit("/", 1)[-1]):
        return deny("orchestrator_or_release")
    if source is None:
        return deny("source_unreadable")
    if DENY_BROKER.search(source):
        return deny("broker_or_orders")
    if DENY_MUTATE.search(source):
        return deny("mutates_git_or_scheduler")
    if not _MAIN.search(source):
        return deny("no_entrypoint")
    declared = set(_FLAG_DECL.findall(source))
    dry = next((f for f in DRY_FLAGS if f in declared), None)
    writes_tracked = (tracked is None and bool(artifacts)) or any(
        a in (tracked or ()) for a in artifacts)
    if writes_tracked and dry is None:
        return deny("writes_tracked_state" if tracked is not None else "tracked_state_unknowable")
    return {"run": True, "reason": "", "args": [dry] if dry else [],
            "mode": dry.lstrip("-") if dry else "plain"}


def memory_cap_mb() -> tuple[int, float | None]:
    """(cap, available) in MB, the cap derived from MEASURED free memory on this machine."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        avail = float(psutil.virtual_memory().available) / 1024 ** 2
    except Exception:
        return MEM_FLOOR_MB, None
    return int(min(MEM_CEIL_MB, max(MEM_FLOOR_MB, avail * MEM_SHARE))), avail


def _tree_rss_mb(pid: int) -> float:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        root = psutil.Process(pid)
        procs = [root, *root.children(recursive=True)]
    except Exception:
        return 0.0
    total = 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except Exception:
            continue
    return total / 1024 ** 2


def _kill(pid: int) -> None:
    try:
        from libs.ops.proctree import kill_tree
        kill_tree(pid)
    except Exception:
        with contextlib.suppress(OSError):
            os.kill(pid, 9)


def exception_type(stderr: str) -> str | None:
    """The LAST exception type in a traceback tail -- the type only, never its message."""
    found = None
    for line in stderr.splitlines():
        m = _EXC.match(line.strip())
        if m:
            found = m.group(1).rsplit(".", 1)[-1]
    return found


def _artifact_touched(artifacts: Sequence[str], since: float, root: Path) -> bool:
    for a in artifacts:
        for d in ARTIFACT_DIRS:
            p = root / d / a
            try:
                if p.stat().st_mtime >= since:
                    return True
            except OSError:
                continue
    return False


def run_one(organ: str, args: Sequence[str], artifacts: Sequence[str], *, cap_s: float,
            mem_mb: int, root: Path = ROOT,
            tracked_reports: Sequence[str] = ()) -> dict[str, Any]:
    """Start one organ in a scratch cwd under a time cap and a memory guard; classify the end."""
    started = time.time()
    env = dict(os.environ)
    env.update({"PYTHONPATH": os.pathsep.join([str(root), str(root / "desks" / "mt5")]),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
                "MPLBACKEND": "Agg", "QUANT_ORGAN_REDTEAM": "1"})
    with tempfile.TemporaryDirectory(prefix="organ_redteam_") as sandbox:
        out_p, err_p = Path(sandbox) / "_stdout", Path(sandbox) / "_stderr"
        tracked_p = Path(sandbox) / "_tracked"
        tracked_p.write_text("\n".join(os.path.normcase(os.path.abspath(root / t))
                                       for t in tracked_reports), "utf-8")
        env.update({"QUANT_REDTEAM_ROOT": str(root), "QUANT_REDTEAM_SANDBOX": sandbox,
                    "QUANT_REDTEAM_TRACKED": str(tracked_p)})
        killed = None
        peak = 0.0
        with out_p.open("wb") as fo, err_p.open("wb") as fe:
            try:
                proc = subprocess.Popen([sys.executable, "-c", BOOTSTRAP, str(root / organ), *args],
                                        cwd=sandbox,
                                        env=env, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe)
            except OSError as exc:
                return {"outcome": CRASHED, "exception": type(exc).__name__, "rc": None,
                        "elapsed_s": 0.0}
            while proc.poll() is None:
                if time.time() - started > cap_s:
                    killed = TIMEOUT
                elif (rss := _tree_rss_mb(proc.pid)) > mem_mb:
                    killed = "memory"
                    peak = max(peak, rss)
                else:
                    peak = max(peak, rss)
                if killed:
                    _kill(proc.pid)
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(timeout=10)
                    break
                time.sleep(0.25)
        rc = proc.returncode
        elapsed = round(time.time() - started, 2)
        stdout_n = out_p.stat().st_size if out_p.exists() else 0
        stderr = err_p.read_bytes()[-8192:].decode("utf-8", "replace") if err_p.exists() else ""
        refused_p = Path(sandbox) / "_refused"
        refused = (sorted(set(refused_p.read_text("utf-8").splitlines()))
                   if refused_p.exists() else [])
        wrote_sandbox = any(p.name not in ("_stdout", "_stderr", "_tracked", "_refused")
                            for p in Path(sandbox).iterdir())
    base: dict[str, Any] = {"rc": rc, "elapsed_s": elapsed, "peak_rss_mb": round(peak, 1)}
    if refused:
        base["refused_writes"] = refused[:20]
    if killed == TIMEOUT:
        return {"outcome": TIMEOUT, **base}
    if killed == "memory":
        return {"outcome": CRASHED, "exception": "MemoryGuard", **base}
    if rc != 0:
        return {"outcome": CRASHED, "exception": exception_type(stderr) or f"exit_{rc}", **base}
    if stdout_n or wrote_sandbox or _artifact_touched(artifacts, started, root):
        return {"outcome": RAN_OK, **base}
    return {"outcome": NO_OUTPUT, **base}


def next_names(names: Sequence[str], cursor: str | None) -> list[str]:
    """The rotation from `cursor` (a NAME; the first name >= it), wrapping once."""
    ordered = sorted(names)
    if not ordered:
        return []
    start = 0
    if cursor:
        start = next((i for i, n in enumerate(ordered) if n >= cursor), 0)
    return ordered[start:] + ordered[:start]


def run_pass(*, per_pass: int = PER_PASS, cap_s: float = CAP_S, budget_s: float = BUDGET_S,
             plan_only: bool = False, source: Path = SOURCE, out: Path = OUT,
             root: Path = ROOT, runner: Any = None) -> dict[str, Any]:
    runner = runner or run_one
    prev = _read_json(out) or {}
    census = _read_json(source)
    doc: dict[str, Any] = {
        "at": _now(), "source": str(source.relative_to(root)) if source.is_relative_to(root)
        else str(source), "per_pass": per_pass, "time_cap_s": cap_s,
        "outcomes": list(OUTCOMES), "organs": dict(prev.get("organs") or {}),
        "quarantine": sorted(set(prev.get("quarantine") or [])),
        "cursor": prev.get("cursor"), "this_pass": [],
    }
    if not census or not isinstance(census.get("no_clock"), list):
        doc.update(status="UNMEASURED",
                   why=f"{source.name} is absent or carries no no_clock list; nothing was run")
        return doc
    no_clock = [str(n) for n in census["no_clock"]]
    organs_meta = census.get("organs") or {}
    doc["source_at"] = census.get("at")
    doc["n_no_clock"] = len(no_clock)
    money = money_closure(root / "ops" / "money_closure.txt")
    files = tracked_files(root)
    tracked = tracked_basenames(files)
    tracked_reports = [f for f in files or () if "reports" in f.split("/")]
    mem_mb, avail = memory_cap_mb()
    doc["memory_cap_mb"], doc["memory_available_mb"] = mem_mb, (
        round(avail) if avail is not None else None)
    stand_down = avail is not None and avail < 2 * mem_mb
    t0 = time.time()
    ran = 0
    rotation = next_names(no_clock, doc["cursor"])
    cursor: str | None = None
    for name in rotation:
        if ran >= per_pass or time.time() - t0 + cap_s > budget_s:
            cursor = name
            break
        arts = list((organs_meta.get(name) or {}).get("artifacts") or [])
        try:
            src: str | None = (root / name).read_text("utf-8", "replace")
        except OSError:
            src = None
        c = classify(name, src, arts, money=money, tracked=tracked, quarantine=doc["quarantine"])
        row: dict[str, Any] = {"organ": name, "at": _now(), "mode": c["mode"]}
        if not c["run"]:
            row.update(outcome=SKIPPED, reason=c["reason"])
        elif plan_only or stand_down:
            row.update(outcome=None, reason="plan_only" if plan_only else "memory_stand_down")
            doc["this_pass"].append(row)
            if stand_down:
                cursor = name
                break
            continue
        else:
            before = tracked_dirty(root)
            row.update(runner(name, c["args"], arts, cap_s=cap_s, mem_mb=mem_mb, root=root,
                              tracked_reports=tracked_reports))
            after = tracked_dirty(root)
            drift = sorted(after - before) if before is not None and after is not None else []
            if drift:
                # Another writer may share the window, so this is a suspicion, recorded as one;
                # the organ is never started here again either way.
                row["tracked_drift"] = drift[:20]
                doc["quarantine"] = sorted({*doc["quarantine"], name})
            ran += 1
        doc["this_pass"].append(row)
        doc["organs"][name] = {k: v for k, v in row.items() if k != "organ"}
    else:
        # The whole list was walked: the next pass starts where this one did.
        cursor = rotation[0] if rotation else None
    doc["cursor"] = cursor
    live = set(no_clock)
    doc["organs"] = {k: v for k, v in sorted(doc["organs"].items()) if k in live}
    counts = Counter(str(v.get("outcome")) for v in doc["organs"].values())
    doc["counts"] = dict(sorted(counts.items()))
    doc["n_ran_this_pass"] = ran
    doc["n_classified"] = len(doc["organs"])
    doc["coverage"] = round(len(doc["organs"]) / len(no_clock), 4) if no_clock else None
    doc["status"] = "STOOD_DOWN" if stand_down else ("PLAN_ONLY" if plan_only else "OK")
    doc["why"] = ("NO_CLOCK organs are read by something and started by nothing; each pass "
                  "starts a few of them once, bounded, and records whether they lived. "
                  "Report only: nothing is scheduled, retired or repaired here")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-pass", type=int, default=PER_PASS)
    ap.add_argument("--cap-s", type=float, default=CAP_S)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--plan-only", action="store_true", help="classify the rotation, run nothing")
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run_pass(per_pass=a.per_pass, cap_s=a.cap_s, budget_s=a.budget_s,
                   plan_only=a.plan_only, source=a.source, out=a.out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, a.out)
    print(f"organ_redteam: {doc.get('status')}; ran {doc.get('n_ran_this_pass', 0)} this pass; "
          f"{doc.get('n_classified', 0)}/{doc.get('n_no_clock', 0)} NO_CLOCK organs classified; "
          f"{doc.get('counts', {})}; next {doc.get('cursor')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
