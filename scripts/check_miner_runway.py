"""MINER RUNWAY DOCTOR -- why a seat has never produced, not just that it hasn't.

MEASURED STATE 2026-07-29: 6 of 7 frontier regions have ZERO runs EVER. `max_audit`'s ORGANS
table already checks log FRESHNESS, but a never-run organ and a stale organ look identical to it,
and neither answer says WHY -- so the condition persisted while being technically monitored. Worse,
a never-run duty is deliberately exempt from the cadence floor (so brand-new cadence items do not
page), which is exactly how "never executed since being wired" survived from 07-18 (register #29).

This checks the RUNWAY -- everything that must be true BEFORE a seat can produce:
  prompt   the mission prompt file exists and is non-empty
  runner   the shell runner exists
  unit     a committed systemd unit/timer names that runner (or the manifest schedules it)
  creds    an auth credential is present on the box (existence ONLY -- never a value, never a
           prefix; a doctor that prints secrets is a worse defect than the one it diagnoses)
  ran      evidence of ANY run ever, from the organ's own log glob, with its age

STATUS is the diagnosis, and the distinction is the whole point:
  unobservable     THIS HOST CANNOT SEE THE LOGS -- says nothing about the seats (see below)
  ok               produced inside its max age
  stale            produced before, not recently  -> a runtime failure, look at the log
  never-ran        runway complete, zero output   -> scheduling/quota, not configuration
  creds-missing    cannot possibly run            -> a HUMAN step, and the real blocker today
  not-scheduled    nothing would ever invoke it   -> a wiring defect in the repo
  missing-prompt   configuration incomplete

OBSERVABILITY IS CHECKED FIRST (2026-08-01). data/cro_ai_logs is gitignored and VPS-local, so
running this from a dev clone or an agent container finds no logs AND no credential -- and the
old ladder then reported "creds-missing" for all eleven seats. That is a verdict about the HOST
wearing the costume of a verdict about the DESK. It cost real confusion: a reader concluded the
miners had never run, while docs/research/deep_sweep/20260801_*.md sat in the same repo as proof
that they had. Config facts (prompt/runner/unit) come from the repo and are true anywhere; every
RUN fact needs the logs, and when they are absent this now says so instead of guessing.

Exit code is nonzero when any seat is creds-missing / never-ran / not-scheduled / unobservable,
so this is cron-able as a pager check on the box. --report-only always exits 0.

    python scripts/check_miner_runway.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_LOGDIR = _ROOT / "data/cro_ai_logs"
_OUT = _ROOT / "data/miner_runway.json"

# Credentials: EITHER path arms every claude organ (brain_env walks the chain), so this is an
# any-of check. Values are never read -- existence only.
_CRED_ANY = ("data/secrets/claude_oauth_token", "data/secrets/anthropic_api_key")
_CRED_HOME = Path.home() / ".claude/.credentials.json"

# seat -> (prompt, runner, log glob, max_age_h). Max ages mirror scripts/max_audit.py ORGANS so
# the two organs cannot disagree about what "stale" means.
_SEATS: dict[str, tuple[str, str, str, float]] = {
    "frontier-en": ("ops/frontier_en_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_en_*.log", 36.0),
    "frontier-cn": ("ops/frontier_cn_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_cn_*.log", 36.0),
    "frontier-ru": ("ops/frontier_ru_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_ru_*.log", 36.0),
    "frontier-kr": ("ops/frontier_kr_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_kr_*.log", 36.0),
    "frontier-jp": ("ops/frontier_jp_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_jp_*.log", 36.0),
    "frontier-ar": ("ops/frontier_ar_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_ar_*.log", 36.0),
    "frontier-br": ("ops/frontier_br_prompt.txt", "ops/run_frontier_miner.sh",
                    "frontier_br_*.log", 36.0),
    "prospector": ("ops/prospector_dig_prompt.txt", "ops/run_prospector_dig.sh",
                   "prospector_*.log", 216.0),
    "litminer": ("ops/litminer_dig_prompt.txt", "ops/run_litminer_dig.sh",
                 "litminer_*.log", 216.0),
    "dataaxis": ("ops/dataaxis_dig_prompt.txt", "ops/run_dataaxis_dig.sh",
                 "dataaxis_*.log", 96.0),
    "blindrediscovery": ("ops/blindrediscovery_dig_prompt.txt",
                         "ops/run_blindrediscovery_dig.sh",
                         "blindrediscovery_*.log", 840.0),
}

_BAD = ("creds-missing", "never-ran", "not-scheduled", "missing-prompt", "unobservable")
#: "unobservable" is BAD on purpose. A run that cannot see the logs has not verified anything, and
#: exiting 0 would let a green check stand in for a check that never happened.


def _creds_present() -> bool:
    if _CRED_HOME.exists():
        return True
    if any((_ROOT / p).exists() for p in _CRED_ANY):
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


def _scheduled(runner: str) -> bool:
    """A runner is scheduled if a committed systemd unit invokes it, or the crontab manifest does.
    Both are in-repo evidence -- the point of gap #58 was that live-only scheduling is invisible."""
    name = Path(runner).name
    for unit in (_ROOT / "ops").glob("*.service"):
        if name in unit.read_text("utf-8", errors="ignore"):
            return True
    # The frontier rotation wrapper invokes the per-region runner; treat that as scheduling too.
    for wrapper in (_ROOT / "ops").glob("run_*rotation*.sh"):
        if name in wrapper.read_text("utf-8", errors="ignore"):
            for unit in (_ROOT / "ops").glob("*.service"):
                if wrapper.name in unit.read_text("utf-8", errors="ignore"):
                    return True
    manifest = _ROOT / "ops/crontab.manifest"
    return manifest.exists() and name in manifest.read_text("utf-8", errors="ignore")


def _last_run(glob: str) -> tuple[str | None, float | None, int | None]:
    try:
        logs = sorted(_LOGDIR.glob(glob), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None, None, None
    if not logs:
        return None, None, None
    last = logs[-1]
    return last.name, (time.time() - last.stat().st_mtime) / 3600.0, last.stat().st_size


def audit() -> dict[str, Any]:
    # OBSERVABILITY FIRST -- this check is worthless, and worse than worthless, when it cannot see
    # the run history. data/cro_ai_logs is VPS-local and gitignored, so running this anywhere else
    # (a dev clone, a CI box, an agent container) finds no logs AND no credentials, and the old
    # ladder then reported "creds-missing" for all eleven seats. That is a verdict about the
    # MACHINE masquerading as a verdict about the DESK, and on 2026-08-01 it convinced a reader
    # that eleven working seats had never run -- while docs/research/deep_sweep/20260801_*.md sat
    # in the same repo as proof they had.
    observable = _LOGDIR.is_dir()
    creds = _creds_present()
    seats: dict[str, Any] = {}
    for seat, (prompt, runner, glob, max_age_h) in _SEATS.items():
        p, r = _ROOT / prompt, _ROOT / runner
        prompt_ok = p.exists() and p.stat().st_size > 0
        runner_ok = r.exists()
        sched = _scheduled(runner)
        name, age_h, size = _last_run(glob)

        if not observable:
            # BEFORE every other verdict. Config facts (prompt/runner/unit) are read from the repo
            # and stay true anywhere; RUN facts are not knowable without the log directory. Saying
            # anything about whether a seat ran, from a box that cannot see its logs, is a guess.
            status = "unobservable"
        elif not prompt_ok:
            status = "missing-prompt"
        elif not runner_ok or not sched:
            status = "not-scheduled"
        elif not creds:
            # Ordered deliberately BEFORE never-ran: with no credentials the seat CANNOT run, so
            # reporting "never-ran" would name the symptom and hide the cause (register #89's
            # lesson -- group by blocker, report the cause with its blast radius).
            status = "creds-missing"
        elif name is None:
            status = "never-ran"
        elif age_h is not None and age_h > max_age_h:
            status = "stale"
        else:
            status = "ok"
        seats[seat] = {"prompt": prompt_ok, "runner": runner_ok, "unit": sched, "creds": creds,
                       "last_run": name, "age_h": round(age_h, 1) if age_h is not None else None,
                       "last_bytes": size, "max_age_h": max_age_h, "status": status}

    by_status: dict[str, list[str]] = {}
    for seat, row in seats.items():
        by_status.setdefault(str(row["status"]), []).append(seat)
    blockers = []
    if not observable:
        blockers.append({
            "blocker": f"log directory {_LOGDIR} is absent -- run history is UNREADABLE here",
            "human_step": "run this ON the box that owns the logs; it is gitignored and local",
            "blast_radius": len(seats),
            "note": "this report says NOTHING about whether the seats ran. Config facts below "
                    "(prompt/runner/unit) are read from the repo and remain true anywhere; every "
                    "RUN fact is unknown. On 2026-08-01 the previous version reported "
                    "'creds-missing' for all eleven seats from a box that simply could not see "
                    "them, and a reader concluded the miners had never run while that same repo "
                    "held today's dig output."})
    if not creds:
        blockers.append({"blocker": "no claude credential on this host",
                         "human_step": "bash ops/setup_brain_token.sh (or setup_brain_api_key.sh)",
                         "blast_radius": len([s for s, r in seats.items()
                                              if r["status"] == "creds-missing"]),
                         "note": "ONE human step unblocks every seat counted here -- reported as "
                                 "a cause, not as N unrelated dead organs"})
    return {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "observable": observable, "log_dir": str(_LOGDIR),
            "creds_present": creds, "seats": seats, "by_status": by_status,
            "blockers": blockers,
            "n_bad": sum(1 for r in seats.values() if r["status"] in _BAD)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0 (record the state without failing a cron)")
    args = ap.parse_args()
    rep = audit()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"miner runway | creds={'present' if rep['creds_present'] else 'MISSING'} "
              f"| {rep['n_bad']} of {len(rep['seats'])} seats cannot produce")
        for seat, row in rep["seats"].items():
            age = f"{row['age_h']}h" if row["age_h"] is not None else "never"
            print(f"  {row['status']:14} {seat:18} prompt={int(bool(row['prompt']))} "
                  f"runner={int(bool(row['runner']))} sched={int(bool(row['unit']))} "
                  f"last={age}")
        for b in rep["blockers"]:
            print(f"  BLOCKER: {b['blocker']} -> {b['human_step']} "
                  f"(unblocks {b['blast_radius']} seats)")
    return 0 if args.report_only else (1 if rep["n_bad"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
