"""Scheduler-manifest checker (gap #58) -- can this repo still reconstitute the desk?

2026-07-29: 119/162 scripts had no in-repo scheduler reference and the live VPS crontab was
uncommitted (docs/GAP_REGISTER.md:272), so a GitHub restore yielded a desk that ran NOTHING.
ops/crontab.manifest is the reconstructed DR floor; this checker keeps it honest five ways:

  (a) every script the manifest references must exist in the repo -- a deleted-but-still-
      scheduled script is a silent nightly failure (the DEAD CRON class, scripts/wiring_audit.py:8);
  (b) every committed ops/*.timer's service ExecStart script must exist AND appear in the
      manifest, and every OnCalendar value must exactly match the manifest schedule -- the
      committed units are the one part the manifest CAN be sure of, so a unit or schedule
      missing from it means the manifest has rotted, not the box;
  (c) where `crontab -l` succeeds (the live VPS), live-vs-manifest drift is reported in BOTH
      directions: an extra live line is tomorrow's un-reconstitutable job, a missing one is a
      job the DR floor promises but the box does not run. Root paths are normalized so
      "$QUANT_ROOT" here and /home/quant/quant-platform there compare equal.
  (d) a script scheduled on several cron lines must use ONE lock path or none -- flock cannot
      serialize across distinct lock files, so two `flock -n` lines LOOK mutually exclusive and
      are not (R0326);
  (e) every scheduled .py must be able to IMPORT: its first-party imports have to resolve to a
      file in this tree. (a) catches the organ that dies on ENOENT; (e) catches the strictly
      nastier one that dies on ImportError, which is indistinguishable downstream because it
      still fires on time and still touches its log (R0359).

  (f) DUPLICATE ORGANS across ALL FOUR PLANES (2026-09-08): every live row -- cron lines,
      SYSTEMD units, the box's desks/mt5/ops/box_tasks.manifest and hourly_cycle's `_costed`
      legs -- is grouped by the script it executes, and a script with more than one live
      schedule that does not share ONE lock (one flock path on every line, or a job lock
      inside the script itself) is REPORTED. Never disabled, never an exit code: (d) already
      fails the same shape on cron alone, and the cross-plane case is the one nobody could
      see -- run_frontier_rotation.sh carried four schedules on two planes and external_gauntlet
      runs as a box task and an hourly leg at once. The report is data/duplicate_organs.json.

In this sandbox / on a fresh restore `crontab -l` fails; that path reports 'no live crontab
readable' gracefully and still runs (a)+(b) -- the repo-only checks are exactly the ones a
dead box needs. deploy/reconstitute_cron.sh refuses to install while (a) fails.

Exit: 2 on any (a)/(b) failure; 1 on live drift (suppressed by --report-only); 0 clean.
stdlib-only. --json writes data/scheduler_manifest_report.json (mkdir -p, never crashes the
check itself -- a reporting failure must not mask a scheduling truth).

    python scripts/check_scheduler_manifest.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_REL = "ops/crontab.manifest"
_REPORT_REL = "data/scheduler_manifest_report.json"
# the live box's repo root, hardcoded in its unit files (ops/quant-litminer.service etc.) --
# stripped when mapping ExecStart paths and when normalizing live crontab lines for the diff.
_VPS_ROOT = "/home/quant/quant-platform"
# one cron field: numerics, ranges, steps, lists, or * (day/month names unused on this desk)
_CRON_FIELD = re.compile(r"^[\d*,/-]+$")
_SCRIPT_REF = re.compile(r"(?:scripts|ops|deploy)/[A-Za-z0-9_.\-]+\.(?:py|sh)")
_KV = re.compile(r'(\w+)="([^"]*)"')
_ENV_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class CronEntry:
    schedule: str
    command: str
    line_no: int


@dataclass(frozen=True)
class SystemdEntry:
    unit: str
    on: str
    exec_path: str
    line_no: int


@dataclass
class Manifest:
    path: Path
    root_default: str = _VPS_ROOT
    cron: list[CronEntry] = field(default_factory=list)
    systemd: list[SystemdEntry] = field(default_factory=list)
    raw: str = ""
    parse_problems: list[str] = field(default_factory=list)


def parse_manifest(path: Path) -> Manifest:
    """Parse ops/crontab.manifest. Comments carry the evidence; only three line shapes are
    machine-active: `NAME=value` env lines, `SYSTEMD key="v" ...` unit lines, and real
    5-field cron lines. Anything else non-comment is a parse problem, reported not ignored --
    a silently skipped line would be a scheduled job the DR floor silently dropped."""
    man = Manifest(path=path)
    try:
        man.raw = path.read_text("utf-8")
    except OSError as e:
        man.parse_problems.append(f"manifest unreadable: {e}")
        return man
    for i, line in enumerate(man.raw.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("SYSTEMD"):
            kv = dict(_KV.findall(s))
            unit = kv.get("unit", "")
            if not unit:
                man.parse_problems.append(f"line {i}: SYSTEMD entry without unit=")
                continue
            man.systemd.append(SystemdEntry(unit=unit, on=kv.get("on", ""),
                                            exec_path=kv.get("exec", ""), line_no=i))
            continue
        if _ENV_LINE.match(s):
            name, _, value = s.partition("=")
            if name == "QUANT_ROOT" and value:
                man.root_default = value
            continue
        fields = s.split(None, 5)
        if len(fields) >= 6 and all(_CRON_FIELD.match(f) for f in fields[:5]):
            man.cron.append(CronEntry(schedule=" ".join(fields[:5]), command=fields[5],
                                      line_no=i))
        else:
            man.parse_problems.append(f"line {i}: not a comment, env, SYSTEMD or cron line: "
                                      f"{s[:80]}")
    return man


def referenced_paths(man: Manifest) -> list[str]:
    """Every repo-relative script the manifest schedules, cron and systemd planes both."""
    refs: set[str] = set()
    for c in man.cron:
        refs.update(_SCRIPT_REF.findall(c.command))
    for u in man.systemd:
        if u.exec_path:
            refs.add(u.exec_path)
    return sorted(refs)


def check_scripts_exist(root: Path, man: Manifest) -> list[str]:
    """(a) DEAD-CRON fence: a manifest that references a deleted script would reconstitute a
    desk that fails silently every tick. This is the load-bearing regression check."""
    return [p for p in referenced_paths(man) if not (root / p).is_file()]


_FLOCK_PATH = re.compile(r"\bflock\s+(?:-[a-zA-Z]+\s+)*(\S+)")


def check_lock_coherence(man: Manifest) -> list[str]:
    """(d) SAME-SCRIPT-DIFFERENT-LOCK fence (R0326). Until 2026-08-05 the manifest scheduled
    ops/run_crypto_factory.sh twice -- 30 1 under data/.cron_crypto_factory.lock and an adopted
    live twin at 30 3 under /tmp/crypto_factory.lock. Both lines LOOKED serialized because both
    said `flock -n`, but flock only excludes holders of the SAME lock file, so the two runs
    could overlap freely: mutual exclusion that reads as present and is not. A script scheduled
    on multiple cron lines must either share ONE lock path on every line or carry no flock at
    all anywhere (in which case the duplication is at least visible for what it is)."""
    locks_by_script: dict[str, set[str | None]] = {}
    lines_by_script: dict[str, list[int]] = {}
    for c in man.cron:
        m = _FLOCK_PATH.search(c.command)
        lock = m.group(1) if m is not None else None
        for script in _SCRIPT_REF.findall(c.command):
            locks_by_script.setdefault(script, set()).add(lock)
            lines_by_script.setdefault(script, []).append(c.line_no)
    problems: list[str] = []
    for script, locks in sorted(locks_by_script.items()):
        if len(lines_by_script[script]) < 2 or len(locks) < 2:
            continue
        named = ", ".join(sorted(str(x) for x in locks))
        lines = ", ".join(str(n) for n in lines_by_script[script])
        problems.append(f"{script} scheduled on lines {lines} under different locks "
                        f"({named}) -- flock cannot serialize across distinct lock files")
    return problems


#: Top-level packages that live in THIS repo. A third-party import cannot be resolved from disk
#: and is deliberately NOT checked -- but it is COUNTED, so "0 problems" can never be read as
#: "everything was checked" when the truth is "almost nothing was" (the guard-scope lesson).
_FIRST_PARTY = ("libs", "scripts", "app", "api")


def _module_on_disk(root: Path, dotted: str) -> bool:
    """Does `libs.discovery.cagr_optimizer` correspond to a file or package in this tree?

    Pure PATH resolution, never an import: this fence runs on every push, and importing 184
    organ entry points to find out whether they import would execute module-level code in all
    of them. find_spec is not an option either -- it imports parent packages.
    """
    p = root.joinpath(*dotted.split("."))
    return p.with_suffix(".py").is_file() or (p / "__init__.py").is_file()


def check_imports_resolve(root: Path, man: Manifest) -> tuple[list[str], int, int]:
    """(e) THE SILENT-IMPORTERROR FENCE. Returns (problems, n_checks, n_thirdparty_skipped).

    WHY EXISTENCE IS NOT ENOUGH, and why this is a different failure from check (a). Check (a)
    catches a manifest entry whose FILE is gone -- the organ dies on ENOENT. This catches the
    strictly nastier case where the file is present and dies on ImportError, because the two are
    indistinguishable downstream: the organ fires on time, writes a log, and every
    freshness-shaped check reads a minutes-old log and reports it healthy. "A heartbeat proves
    the loop is alive, NEVER that the pipe is."

    THE MEASURED INSTANCE (R0359). scripts/run_geometric_review.py -- the one entry point wiring
    the desk's SUPREME OBJECTIVE, E[log wealth], to something runnable -- was dead from
    2026-07-30 to 2026-08-05 importing two modules that did not exist.

    AND NOTE THE ACTUAL MECHANISM, because the row that asked for this misdiagnosed it: the
    dormancy scan was NOT blind to scripts/. It already grepped scripts/ at 3be2e3e, and
    scripts/run_geometric_review.py DID NOT EXIST in the tree that retirement was computed
    against -- it was added by fee1214a on the OTHER lineage, which is not an ancestor of
    3be2e3e. The retirement's "zero external importers" claim was TRUE of its own tree. The
    breakage was born in the MERGE that later united the two lineages: the caller arrived from
    master and the callees stayed deleted. No reachability scan on either side could have seen
    that, because neither tree was ever wrong -- only their union was. That is precisely why the
    check belongs HERE, at the schedule boundary, rather than in the dormancy hunter.
    """
    problems: list[str] = []
    n_checks = 0
    n_skipped = 0
    for rel in referenced_paths(man):
        if not rel.endswith(".py"):
            continue
        f = root / rel
        if not f.is_file():
            continue                      # already reported by check (a); not double-counted
        try:
            tree = ast.parse(f.read_text("utf-8", errors="ignore"))
        except (SyntaxError, ValueError) as e:
            problems.append(f"{rel}: does not parse ({e}) -- it cannot start at all")
            continue
        for node in ast.walk(tree):       # ast.walk, so a function-local import counts too
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] not in _FIRST_PARTY:
                        n_skipped += 1
                        continue
                    n_checks += 1
                    if not _module_on_disk(root, a.name):
                        problems.append(f"{rel}: `import {a.name}` -- no such module in the repo")
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] not in _FIRST_PARTY:
                    n_skipped += 1
                    continue
                n_checks += 1
                if not _module_on_disk(root, node.module):
                    problems.append(f"{rel}: `from {node.module} import ...` -- no such module")
                    continue
                pkg = root.joinpath(*node.module.split("."))
                init = pkg / "__init__.py"
                if not init.is_file():
                    continue
                src = init.read_text("utf-8", errors="ignore")
                for a in node.names:
                    # `import *` names nothing checkable; a re-export is matched by NAME in the
                    # package __init__ rather than by parsing it, which keeps this cheap and
                    # errs toward silence -- a false MISSING here would block every push.
                    if a.name == "*":
                        continue
                    n_checks += 1
                    if (pkg / f"{a.name}.py").is_file() or (pkg / a.name / "__init__.py").is_file():
                        continue
                    if not re.search(rf"\b{re.escape(a.name)}\b", src):
                        problems.append(f"{rel}: `from {node.module} import {a.name}` -- "
                                        f"neither a submodule nor named in {node.module}.__init__")
    return problems, n_checks, n_skipped


def _exec_script_of(service_text: str) -> str | None:
    """Last .py/.sh token of the service's ExecStart line, or None when there is none."""
    for line in service_text.splitlines():
        if line.strip().startswith("ExecStart="):
            # A unit written as `/bin/bash -c './ops/gates.sh --full ...'` hands whitespace
            # tokenisation the QUOTE as part of the path, and `./ops/gates.sh` then failed both
            # the exists check and the manifest lookup for a script that is right there --
            # the same stripping _unit_scripts already does for installed units.
            tokens = [t.strip("'\"") for t in line.strip().removeprefix("ExecStart=").split()]
            hits = [t for t in tokens if t.endswith((".py", ".sh"))]
            if hits:
                return hits[-1].removeprefix("./")
    return None


def _working_dir_of(service_text: str) -> str | None:
    """The unit's WorkingDirectory, mapped onto this repo, or None when it declares none.

    SYSTEMD RESOLVES A RELATIVE ExecStart AGAINST WorkingDirectory, and ignoring that produced a
    false BREACH that blocked the trading box's push. `quant-nightly-catchup.service` declares
    WorkingDirectory=<root>/desks/mt5 and runs `research/nightly_catchup.py`, which is correct and
    on disk -- but resolved against the REPO ROOT it looks absent, so the fence reported a dead
    unit for an organ that runs fine. Worse, that organ is the one whose `enrol_clocks` step puts
    certified sleeves on forward clocks, so the false report pointed away from working machinery.

    This file's own standing rule for a false positive is to fix the CHECK, never to reword the
    organ to satisfy it.
    """
    for line in service_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WorkingDirectory=") and not stripped.startswith("#"):
            wd = stripped.removeprefix("WorkingDirectory=").strip().strip("'\"")
            if wd.startswith(_VPS_ROOT + "/"):
                return wd[len(_VPS_ROOT) + 1:]
            if wd == _VPS_ROOT:
                return ""
            return None if wd.startswith("/") else wd
    return None


def _to_repo_rel(root: Path, path_str: str, work_dir: str | None = None) -> str:
    """Map a unit-file ExecStart path (VPS-absolute) onto this repo. Strip the known VPS
    prefix first; fall back to basename search under ops/ then scripts/ so a moved checkout
    still resolves; return the raw string when unmappable (it will fail the exists check,
    which is the honest outcome)."""
    if path_str.startswith(_VPS_ROOT + "/"):
        return path_str[len(_VPS_ROOT) + 1:]
    if not path_str.startswith("/"):
        # RELATIVE TO THE UNIT'S WorkingDirectory, exactly as systemd resolves it.
        if work_dir:
            joined = f"{work_dir.rstrip('/')}/{path_str}"
            if (root / joined).is_file():
                return joined
        return path_str
    base = Path(path_str).name
    for cand in (f"ops/{base}", f"scripts/{base}"):
        if (root / cand).is_file():
            return cand
    return path_str


def _on_calendar_values(timer_text: str) -> list[str]:
    """Return active OnCalendar expressions exactly as systemd will parse them."""
    values: list[str] = []
    for line in timer_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.startswith("OnCalendar="):
            values.append(stripped.removeprefix("OnCalendar=").strip())
    return values


def check_committed_timers(root: Path, man: Manifest) -> list[str]:
    """Fence committed timer wiring and exact calendar agreement with the manifest.

    The unit files are executable ground truth. A manifest that names the right script but a
    different time is not reconstitutable: it certifies one cadence and deploys another.
    """
    problems: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        service = timer.with_suffix(".service")
        rel_timer = timer.relative_to(root).as_posix()
        if not service.is_file():
            problems.append(f"{rel_timer}: no companion {service.name} committed")
            continue
        service_text = service.read_text("utf-8")
        exec_raw = _exec_script_of(service_text)
        if exec_raw is None:
            problems.append(f"{service.relative_to(root).as_posix()}: no ExecStart script")
            continue
        rel = _to_repo_rel(root, exec_raw, _working_dir_of(service_text))
        if not (root / rel).is_file():
            problems.append(f"{rel_timer}: ExecStart script {rel} does not exist in repo")
        if rel not in man.raw:
            problems.append(
                f"{rel_timer}: ExecStart script {rel} is absent from the manifest"
                " -- the manifest has rotted behind the committed units"
            )

        calendars = _on_calendar_values(timer.read_text("utf-8"))
        if not calendars:
            continue
        entries = [entry for entry in man.systemd if entry.unit == timer.name]
        if len(entries) != 1:
            problems.append(
                f"{rel_timer}: expected exactly one matching SYSTEMD entry, found {len(entries)}"
            )
            continue
        if len(calendars) != 1:
            problems.append(
                f"{rel_timer}: expected exactly one OnCalendar value, found {len(calendars)}"
            )
            continue
        actual = calendars[0]
        declared = entries[0].on
        if actual != declared:
            problems.append(
                f"{rel_timer}: OnCalendar={actual!r} does not exactly match manifest "
                f"on={declared!r}"
            )
    return problems


def read_live_crontab() -> str | None:
    """`crontab -l`, or None wherever that is impossible (no binary, no crontab for user --
    the sandbox and any fresh restore land here; that is a report line, never a crash)."""
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10,
                           check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _norm(line: str, roots: list[str]) -> str:
    """Whitespace-collapse + root-path normalization so the same job compares equal whether
    it is written against $QUANT_ROOT, the VPS path, or this checkout's path."""
    s = " ".join(line.split())
    for r in roots:
        if r:
            s = s.replace(r, "<ROOT>")
    return s.replace('"<ROOT>"', "<ROOT>")


def diff_live(root: Path, man: Manifest, live: str) -> tuple[list[str], list[str], list[str]]:
    """(c) both-direction drift: (missing_in_live, extra_in_live, duplicated_in_live), normalized.

    COMPARED AS A MULTISET, AND THAT IS THE WHOLE POINT. This compared `set`s until 2026-08-01, so
    a job scheduled TWICE was invisible: set subtraction collapses the copies and both differences
    come back empty. Measured on this box the day it was fixed -- 154 live job lines against 137
    manifest entries, and the fence printed "matches manifest (normalized)" and exited OK while 17
    jobs ran twice. The legacy pre-marker block was an exact duplicate of the managed block, which
    is precisely the shape a set cannot see; 14 of the 17 were saved from real concurrency only by
    `flock -n`, and the other 3 genuinely double-ran.

    A fence that reports OK on a real breach is worse than no fence: it is the breach plus a
    certificate saying there isn't one.
    """
    roots = ["${QUANT_ROOT}", "$QUANT_ROOT", _VPS_ROOT, man.root_default, str(root)]
    want = Counter(_norm(f"{c.schedule} {c.command}", roots) for c in man.cron)
    have: Counter[str] = Counter()
    for line in live.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or _ENV_LINE.match(s):
            continue
        have[_norm(s, roots)] += 1
    missing_in_live = sorted(want - have)          # in manifest, not (enough) on the box
    extra_in_live = sorted(set(have) - set(want))  # on the box, unknown to the manifest
    # Scheduled more times than the manifest declares -- the case set-difference erased.
    duplicated = sorted(f"{k} (live x{have[k]}, manifest x{want[k]})"
                        for k in want if have[k] > want[k])
    return missing_in_live, extra_in_live, duplicated


# ---------------------------------------------------------------------------------------------
# THE SECOND AND THIRD SCHEDULER PLANES (added 2026-08-29)
#
# This fence compared the manifest against `crontab -l` ALONE. That was true when it was written
# and stopped being true on 2026-08-20, when root `cron.service` OOM-died and the desk migrated
# its live jobs onto systemd USER timers plus scripts/run_manifest_dispatch.py. From that day the
# fence printed 232 identical `DRIFT manifest-only (box does not run it)` lines -- including one
# for every row that WAS running perfectly well under a timer -- and a fence whose every line is
# noise cannot signal the one line that matters. The 08-20 death itself hid inside this output
# for six days.
#
# A row is COVERED when some executor demonstrably runs it, and the three planes are asked in
# order of evidence strength: the dispatcher's state file records that a row ACTUALLY FIRED and
# when; a unit's ExecStart records that something is CONFIGURED to run it. Neither is a claim
# from the manifest about itself, which is the only kind of evidence this fence must not accept.
# ---------------------------------------------------------------------------------------------

_UNIT_DIRS = (Path.home() / ".config/systemd/user", Path("/etc/systemd/system"))
_SCRIPT_TOKEN = re.compile(r"[\w/.\-]+\.(?:py|sh)")
_DISPATCH_STATE_REL = "data/manifest_dispatch_state.json"
#: A dispatcher row counts as covering the manifest only if it fired inside this window. A row
#: that fired once a fortnight ago is a dead row with a memory, not a live executor.
_DISPATCH_FRESH_H = 26.0 * 7


def _unit_scripts() -> set[str]:
    """Every script basename named by an installed unit's ExecStart, both planes.

    Basename and not full path on purpose: units invoke scripts through wrappers, `flock`,
    `/bin/bash -c '...'` and quoted forms, and a path-exact match would report a running organ as
    dead. The failure direction of a basename match is a false COVERED, which this fence reports
    as a count rather than silence so the looseness stays visible.
    """
    found: set[str] = set()
    for d in _UNIT_DIRS:
        try:
            units = list(d.glob("*.service"))
        except OSError:
            continue
        for u in units:
            try:
                txt = u.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for line in txt.splitlines():
                if line.strip().startswith("ExecStart"):
                    for m in _SCRIPT_TOKEN.finditer(line):
                        found.add(m.group(0).strip("'\"").split("/")[-1])
    return found


def _dispatched_scripts(root: Path, now: datetime | None = None) -> set[str]:
    """Script basenames the manifest dispatcher has actually fired inside the freshness window."""
    now = now or datetime.now(UTC)
    try:
        state = json.loads((root / _DISPATCH_STATE_REL).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    live: set[str] = set()
    for token, row in (state.get("rows") or {}).items():
        try:
            fired = datetime.fromisoformat(str(row.get("last_fired", "")))
        except ValueError:
            continue
        if (now - fired).total_seconds() / 3600.0 <= _DISPATCH_FRESH_H:
            live.add(str(token).split("/")[-1])
    return live


def split_by_plane(root: Path, drift_missing: list[str]) -> tuple[list[str], dict[str, int]]:
    """Rows the crontab does not run, split into GENUINELY uncovered and covered-elsewhere.

    Returns the uncovered rows (the real drift) and a per-plane count of what was absorbed, so
    the coverage claim carries its own denominator instead of quietly shrinking the number.
    """
    units, dispatched = _unit_scripts(), _dispatched_scripts(root)
    uncovered: list[str] = []
    absorbed = {"systemd_unit": 0, "manifest_dispatcher": 0}
    for row in drift_missing:
        names = {m.group(0).split("/")[-1] for m in _SCRIPT_TOKEN.finditer(row)}
        if names & dispatched:
            absorbed["manifest_dispatcher"] += 1
        elif names & units:
            absorbed["systemd_unit"] += 1
        else:
            uncovered.append(row)
    return uncovered, absorbed


# ---------------------------------------------------------------------------------------------
# (f) DUPLICATE ORGANS -- one script, several live schedules, no shared lock
# ---------------------------------------------------------------------------------------------

_BOX_TASKS_REL = "desks/mt5/ops/box_tasks.manifest"
_HOURLY_REL = "desks/mt5/research/hourly_cycle.py"
_DUP_REPORT_REL = "data/duplicate_organs.json"
_TASK_LINE = re.compile(r"^TASK\s+(.*)$")
_COSTED = re.compile(r'_costed\(\s*"([A-Za-z0-9_]+)"\s*,\s*([A-Za-z0-9_.]+)')
_PRODUCER = re.compile(r'_producer\(\s*"([A-Za-z0-9_]+)"\s*,\s*"([^"]+)"')
_DEF = re.compile(r"^def ([A-Za-z0-9_]+)\(", re.M)
#: A script that serialises ITSELF: the desk's own job lock (research.job_lock.exclusive_job),
#: a flock in a shell wrapper, or a raw file lock. Any of these makes every schedule of the
#: script wait on the same lock, whichever plane fired it.
_SELF_LOCK = re.compile(r"exclusive_job\(|job_lock|\bflock\b|fcntl\.(?:flock|lockf)|"
                        r"msvcrt\.locking|single_instance")
SERIALISED, UNSERIALISED = "SERIALISED", "UNSERIALISED"


@dataclass(frozen=True)
class ScheduleRow:
    plane: str        # cron | systemd | box_task | hourly_leg
    script: str       # repo-relative path, or `hourly_cycle:<leg>` for an in-process leg
    schedule: str
    lock: str | None
    where: str        # manifest line, unit, task name or leg -- for the report


def _box_rows(root: Path) -> tuple[list[ScheduleRow], str]:
    p = root / _BOX_TASKS_REL
    try:
        text = p.read_text("utf-8")
    except OSError:
        return [], f"{_BOX_TASKS_REL}: absent"
    rows: list[ScheduleRow] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = _TASK_LINE.match(line.strip())
        if not m:
            continue
        kv = dict(_KV.findall(m.group(1)))
        runs = kv.get("runs", "")
        if not runs or runs == "UNKNOWN" or not runs.endswith((".py", ".sh", ".ps1", ".cmd")):
            continue
        rows.append(ScheduleRow("box_task", runs, kv.get("trigger", "UNDECLARED"), None,
                                f"{kv.get('name', '?')} (line {i})"))
    return rows, f"{_BOX_TASKS_REL}: {len(rows)} task row(s) naming a script"


def _hourly_rows(root: Path) -> tuple[list[ScheduleRow], str]:
    p = root / _HOURLY_REL
    try:
        src = p.read_text("utf-8", errors="ignore")
    except OSError:
        return [], f"{_HOURLY_REL}: absent"
    # The body of every top-level def, so a leg's callee can be searched for the script it
    # runs: `_costed("deep_forest", deep_forest)` wraps `_producer("deep_forest_miner",
    # "research/deep_forest_miner.py")`, and the leg name is not the file's name.
    defs = list(_DEF.finditer(src))
    bodies = {m.group(1): src[m.end():(defs[i + 1].start() if i + 1 < len(defs) else len(src))]
              for i, m in enumerate(defs)}
    rows: list[ScheduleRow] = []
    seen: set[str] = set()
    for m in _COSTED.finditer(src):
        leg, callee = m.group(1), m.group(2)
        if leg in seen:
            continue
        seen.add(leg)
        line = src[src.rfind("\n", 0, m.start()) + 1:src.find("\n", m.end())]
        pm = _PRODUCER.search(line) or _PRODUCER.search(bodies.get(callee, ""))
        path = pm.group(2) if pm else None
        script = f"hourly_cycle:{leg}"
        cands = ([path, f"desks/mt5/{path}"] if path else []) + [
            f"desks/mt5/research/{leg}.py", f"desks/mt5/scripts/{leg}.py", f"scripts/{leg}.py"]
        for c in cands:
            if (root / c).is_file():
                script = c
                break
        rows.append(ScheduleRow("hourly_leg", script, "hourly_cycle leg (every hour)", None,
                                f"_costed({leg!r})"))
    return rows, f"{_HOURLY_REL}: {len(rows)} _costed leg(s)"


def schedule_rows(root: Path, man: Manifest) -> tuple[list[ScheduleRow], dict[str, str]]:
    """Every live schedule on the four planes, one row per (plane, script)."""
    rows: list[ScheduleRow] = []
    for c in man.cron:
        m = _FLOCK_PATH.search(c.command)
        lock = m.group(1) if m is not None else None
        for script in _SCRIPT_REF.findall(c.command):
            rows.append(ScheduleRow("cron", script, c.schedule, lock, f"line {c.line_no}"))
    for u in man.systemd:
        if u.exec_path:
            rows.append(ScheduleRow("systemd", u.exec_path, u.on, None, u.unit))
    box, box_note = _box_rows(root)
    hourly, hourly_note = _hourly_rows(root)
    rows.extend(box)
    rows.extend(hourly)
    return rows, {"cron": f"{_MANIFEST_REL}: {len(man.cron)} live cron line(s)",
                  "systemd": f"{_MANIFEST_REL}: {len(man.systemd)} SYSTEMD row(s)",
                  "box_tasks": box_note, "hourly_cycle": hourly_note}


def _organ_key(script: str) -> str:
    """Group by the executed file's stem: `ops/run_x.sh`, `/home/quant/.../run_x.sh` and a
    box task naming `desks/mt5/scripts/x.py` beside an hourly leg `x` are one organ."""
    return Path(script.split(":", 1)[1] if script.startswith("hourly_cycle:") else script).stem


def _self_lock_evidence(root: Path, scripts: set[str]) -> str:
    for s in sorted(scripts):
        if s.startswith("hourly_cycle:"):
            continue
        try:
            src = (root / _to_repo_rel(root, s)).read_text("utf-8", errors="ignore")
        except OSError:
            continue
        m = _SELF_LOCK.search(src)
        if m:
            return f"{s}: {m.group(0)}"
    return ""


def check_duplicate_organs(root: Path, man: Manifest) -> dict:
    """(f) Report every organ with more than one live schedule and whether one lock covers
    them all. REPORT ONLY: nothing here changes an exit code or a schedule."""
    rows, planes = schedule_rows(root, man)
    by_key: dict[str, list[ScheduleRow]] = {}
    for r in rows:
        by_key.setdefault(_organ_key(r.script), []).append(r)
    groups: dict[str, dict] = {}
    for key, rs in sorted(by_key.items()):
        if len(rs) < 2:
            continue
        locks = sorted({r.lock for r in rs if r.lock})
        one_lock_everywhere = len(locks) == 1 and all(r.lock for r in rs)
        evidence = _self_lock_evidence(root, {r.script for r in rs})
        serialised = one_lock_everywhere or bool(evidence)
        why = ("every schedule takes the same flock path" if one_lock_everywhere else
               f"the script serialises itself ({evidence})" if evidence else
               (f"{len(locks)} distinct flock path(s) across {len(rs)} schedules and no lock "
                f"inside the script: the runs can overlap" if locks else
                f"{len(rs)} schedules, no flock on any line and no lock inside the script"))
        groups[key] = {"n_schedules": len(rs), "planes": sorted({r.plane for r in rs}),
                       "scripts": sorted({r.script for r in rs}), "locks": locks,
                       "self_lock": evidence or None,
                       "verdict": SERIALISED if serialised else UNSERIALISED, "why": why,
                       "rows": [asdict(r) for r in rs]}
    unser = sorted(k for k, g in groups.items() if g["verdict"] == UNSERIALISED)
    return {"n_rows": len(rows),
            "by_plane": {p: sum(1 for r in rows if r.plane == p)
                         for p in ("cron", "systemd", "box_task", "hourly_leg")},
            "planes_read": planes, "n_duplicated": len(groups), "unserialised": unser,
            "serialised": sorted(k for k in groups if k not in unser), "groups": groups,
            "note": ("REPORT ONLY. A script on more than one live schedule is SERIALISED when "
                     "every line takes one flock path or the script holds its own job lock, "
                     "else UNSERIALISED -- the runs can overlap. Nothing here disables a "
                     "schedule or fails the check; a person decides which schedule to keep.")}


def write_duplicate_report(root: Path, report: dict) -> Path | None:
    out = root / _DUP_REPORT_REL
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat(
            timespec="seconds"), **report}, indent=1) + "\n", "utf-8")
        return out
    except OSError as e:                              # reporting must never mask the check
        print(f"  duplicate-organ report unwritable ({e}) -- check result stands",
              file=sys.stderr)
        return None


def repair_schedules(root: Path, man: object) -> list[str]:
    """Rewrite a committed timer's OnCalendar to the manifest's, and say so.

    WHY REPAIR AND NOT ONLY REPORT (2026-09-04). The schedule is declared TWICE -- once in
    `ops/crontab.manifest` and once in a committed `ops/*.timer` -- and two sources of truth drift.
    Measured today: the manifest was corrected to run certify_gauntlet HOURLY and committed, while
    `ops/quant-certify-gauntlet.timer` still said `05:10:00`. An installer copies the ops/ timer
    over the live unit, so every hand-edit to ~/.config was silently undone within the hour, three
    times, and the gauntlet -- the job that MINTS certificates -- kept falling back to daily while
    the desk was asked to grow hourly.

    THE MANIFEST WINS, because it is the file the desk already calls its single source of truth and
    the one a reviewer reads. This only ever rewrites the timer TO the manifest, never the reverse:
    a schedule change is a manifest edit, reviewed and committed, and this closes the gap that let
    an unreviewed copy override it.
    """
    out: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        try:
            text = timer.read_text("utf-8")
        except OSError:
            continue
        cals = [ln.strip().removeprefix("OnCalendar=").strip()
                for ln in text.splitlines()
                if ln.strip().startswith("OnCalendar=")]
        if len(cals) != 1:
            continue
        entries = [e for e in getattr(man, "systemd_entries", []) or []
                   if getattr(e, "timer", "") == timer.name]
        if len(entries) != 1:
            continue
        declared = getattr(entries[0], "on", "")
        if not declared or declared == cals[0]:
            continue
        timer.write_text(text.replace(f"OnCalendar={cals[0]}", f"OnCalendar={declared}", 1),
                         "utf-8")
        out.append(f"  REPAIRED {timer.name}: OnCalendar {cals[0]!r} -> {declared!r} "
                   f"(manifest is the source of truth)")
    return out or ["  schedules: every committed timer already matches the manifest"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help=f"also write {_REPORT_REL} (machine-readable)")
    ap.add_argument("--report-only", action="store_true",
                    help="report live-crontab drift without failing on it "
                         "(missing scripts / rotted timers still exit 2)")
    ap.add_argument("--root", type=Path, default=_ROOT,
                    help="repo root (tests point this at fixture trees)")
    ap.add_argument("--fix-schedules", action="store_true",
                    help="repair a committed timer whose OnCalendar disagrees with the manifest")
    args = ap.parse_args(argv)
    root: Path = args.root.resolve()

    man = parse_manifest(root / _MANIFEST_REL)
    missing = check_scripts_exist(root, man)
    if args.fix_schedules:
        for line in repair_schedules(root, man):
            print(line)
    timer_problems = check_committed_timers(root, man)
    lock_problems = check_lock_coherence(man)
    import_problems, n_import_checks, n_thirdparty = check_imports_resolve(root, man)
    structural = list(man.parse_problems) + timer_problems + lock_problems + import_problems

    live = read_live_crontab()
    drift_missing: list[str] = []
    drift_extra: list[str] = []
    drift_dupes: list[str] = []
    if live is not None:
        drift_missing, drift_extra, drift_dupes = diff_live(root, man, live)

    print(f"scheduler-manifest check | {len(man.cron)} cron entries, "
          f"{len(man.systemd)} systemd entries, {len(referenced_paths(man))} scripts referenced")
    for p in man.parse_problems:
        print(f"  PARSE   {p}")
    for m in missing:
        print(f"  MISSING {m} -- scheduled by the manifest but absent from the repo (dead cron)")
    for p in timer_problems:
        print(f"  TIMER   {p}")
    for p in lock_problems:
        print(f"  LOCK    {p}")
    for p in import_problems:
        print(f"  IMPORT  {p}")
    # L1.57: the denominator is what this RUN resolved, not a roster length. `0 problems` over 0
    # checks is VACUOUS, and printing the count is what makes the difference legible.
    print(f"  imports: {n_import_checks} first-party resolved, "
          f"{n_thirdparty} third-party NOT CHECKED (unresolvable from disk)")
    # (f) duplicate organs, across all four planes. Reported, never an exit code.
    dup = check_duplicate_organs(root, man)
    for key in dup["unserialised"]:
        g = dup["groups"][key]
        print(f"  DUPLICATE {key}: {g['n_schedules']} live schedules on "
              f"{'+'.join(g['planes'])} -- {UNSERIALISED}: {g['why']}")
    dup_out = write_duplicate_report(root, dup)
    print(f"  duplicate organs: {dup['n_rows']} live rows on 4 planes "
          f"({', '.join(f'{k}={v}' for k, v in dup['by_plane'].items())}), "
          f"{dup['n_duplicated']} organ(s) on >1 schedule, {len(dup['unserialised'])} "
          f"unserialised (reported, never disabled)" + (f" -> {dup_out}" if dup_out else ""))
    if live is None:
        print("  live crontab: no live crontab readable (sandbox/fresh restore) -- "
              "repo-only checks (a)+(b) still ran")
    else:
        uncovered, absorbed = split_by_plane(root, drift_missing)
        for d in uncovered:
            print(f"  DRIFT   run by NOTHING on any plane: {d}")
        if absorbed["systemd_unit"] or absorbed["manifest_dispatcher"]:
            print(f"  PLANE   {absorbed['manifest_dispatcher']} manifest row(s) covered by the "
                  f"dispatcher (fired within {_DISPATCH_FRESH_H / 24:.0f}d), "
                  f"{absorbed['systemd_unit']} by an installed systemd unit -- "
                  "not cron drift, and not counted as such")
        for d in drift_extra:
            print(f"  DRIFT   live-only (repo cannot reconstitute it): {d}")
        for d in drift_dupes:
            print(f"  DUPE    scheduled more often than declared: {d}")
        if not (uncovered or drift_extra or drift_dupes):
            print("  live crontab: matches manifest (normalized, multiset)")

    exit_code = 0
    if missing or structural:
        exit_code = 2
    elif (drift_missing or drift_extra or drift_dupes) and not args.report_only:
        exit_code = 1

    if args.json:
        report = {
            "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "manifest": _MANIFEST_REL,
            "cron_entries": len(man.cron),
            "systemd_entries": len(man.systemd),
            "referenced_scripts": referenced_paths(man),
            "checks": {
                "scripts_exist": {"ok": not missing, "missing": missing},
                "committed_timers": {"ok": not timer_problems, "problems": timer_problems},
                "lock_coherence": {"ok": not lock_problems, "problems": lock_problems},
                "imports_resolve": {"ok": not import_problems, "problems": import_problems,
                                    "n_first_party_checked": n_import_checks,
                                    "n_third_party_unchecked": n_thirdparty},
                "parse": {"ok": not man.parse_problems, "problems": man.parse_problems},
                # (f) never affects exit_code; `ok` here means "nothing unserialised", and
                # the full groups live in data/duplicate_organs.json.
                "duplicate_organs": {"ok": not dup["unserialised"],
                                     "n_duplicated": dup["n_duplicated"],
                                     "unserialised": dup["unserialised"],
                                     "serialised": dup["serialised"],
                                     "report": _DUP_REPORT_REL},
                "live_crontab": {
                    "readable": live is not None,
                    "note": None if live is not None else "no live crontab readable",
                    "missing_in_live": drift_missing,
                    "extra_in_live": drift_extra,
                    "duplicated_in_live": drift_dupes,
                },
            },
            "exit_code": exit_code,
        }
        out = root / _REPORT_REL
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=1) + "\n", "utf-8")
            print(f"  -> {out}")
        except OSError as e:  # reporting must never mask the check result
            print(f"  json report unwritable ({e}) -- check result stands", file=sys.stderr)

    verdict = {0: "OK", 1: "DRIFT", 2: "BROKEN"}[exit_code]
    print(f"scheduler-manifest: {verdict}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
