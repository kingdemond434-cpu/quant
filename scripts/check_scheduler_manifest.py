"""Scheduler-manifest checker (gap #58) -- can this repo still reconstitute the desk?

2026-07-29: 119/162 scripts had no in-repo scheduler reference and the live VPS crontab was
uncommitted (docs/GAP_REGISTER.md:272), so a GitHub restore yielded a desk that ran NOTHING.
ops/crontab.manifest is the reconstructed DR floor; this checker keeps it honest three ways:

  (a) every script the manifest references must exist in the repo -- a deleted-but-still-
      scheduled script is a silent nightly failure (the DEAD CRON class, scripts/wiring_audit.py:8);
  (b) every committed ops/*.timer's service ExecStart script must exist AND appear in the
      manifest -- the committed units are the one part the manifest CAN be sure of, so a unit
      missing from it means the manifest has rotted, not the box;
  (c) where `crontab -l` succeeds (the live VPS), live-vs-manifest drift is reported in BOTH
      directions: an extra live line is tomorrow's un-reconstitutable job, a missing one is a
      job the DR floor promises but the box does not run. Root paths are normalized so
      "$QUANT_ROOT" here and /home/quant/quant-platform there compare equal.

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
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
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


def _exec_script_of(service_text: str) -> str | None:
    """Last .py/.sh token of the service's ExecStart line, or None when there is none."""
    for line in service_text.splitlines():
        if line.strip().startswith("ExecStart="):
            tokens = line.strip().removeprefix("ExecStart=").split()
            hits = [t for t in tokens if t.endswith((".py", ".sh"))]
            if hits:
                return hits[-1]
    return None


def _to_repo_rel(root: Path, path_str: str) -> str:
    """Map a unit-file ExecStart path (VPS-absolute) onto this repo. Strip the known VPS
    prefix first; fall back to basename search under ops/ then scripts/ so a moved checkout
    still resolves; return the raw string when unmappable (it will fail the exists check,
    which is the honest outcome)."""
    if path_str.startswith(_VPS_ROOT + "/"):
        return path_str[len(_VPS_ROOT) + 1:]
    if not path_str.startswith("/"):
        return path_str
    base = Path(path_str).name
    for cand in (f"ops/{base}", f"scripts/{base}"):
        if (root / cand).is_file():
            return cand
    return path_str


def check_committed_timers(root: Path, man: Manifest) -> list[str]:
    """(b) every committed ops/*.timer must resolve to an existing ExecStart script that the
    manifest names. The committed units are ground truth; the manifest must never lag them."""
    problems: list[str] = []
    for timer in sorted((root / "ops").glob("*.timer")):
        service = timer.with_suffix(".service")
        rel_timer = timer.relative_to(root).as_posix()
        if not service.is_file():
            problems.append(f"{rel_timer}: no companion {service.name} committed")
            continue
        exec_raw = _exec_script_of(service.read_text("utf-8"))
        if exec_raw is None:
            problems.append(f"{service.relative_to(root).as_posix()}: no ExecStart script")
            continue
        rel = _to_repo_rel(root, exec_raw)
        if not (root / rel).is_file():
            problems.append(f"{rel_timer}: ExecStart script {rel} does not exist in repo")
        if rel not in man.raw:
            problems.append(f"{rel_timer}: ExecStart script {rel} is absent from the manifest"
                            f" -- the manifest has rotted behind the committed units")
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help=f"also write {_REPORT_REL} (machine-readable)")
    ap.add_argument("--report-only", action="store_true",
                    help="report live-crontab drift without failing on it "
                         "(missing scripts / rotted timers still exit 2)")
    ap.add_argument("--root", type=Path, default=_ROOT,
                    help="repo root (tests point this at fixture trees)")
    args = ap.parse_args(argv)
    root: Path = args.root.resolve()

    man = parse_manifest(root / _MANIFEST_REL)
    missing = check_scripts_exist(root, man)
    timer_problems = check_committed_timers(root, man)
    structural = list(man.parse_problems) + timer_problems

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
    if live is None:
        print("  live crontab: no live crontab readable (sandbox/fresh restore) -- "
              "repo-only checks (a)+(b) still ran")
    else:
        for d in drift_missing:
            print(f"  DRIFT   manifest-only (box does not run it): {d}")
        for d in drift_extra:
            print(f"  DRIFT   live-only (repo cannot reconstitute it): {d}")
        for d in drift_dupes:
            print(f"  DUPE    scheduled more often than declared: {d}")
        if not (drift_missing or drift_extra or drift_dupes):
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
                "parse": {"ok": not man.parse_problems, "problems": man.parse_problems},
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
