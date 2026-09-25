#!/usr/bin/env python3
"""THE REAPER THE SHIP PATH NEVER HAD -- a git writer that has STOPPED is removed, with proof.

    python scripts/reap_hung_git_writers.py            # measure and report; signal nothing
    python scripts/reap_hung_git_writers.py --apply    # kill what was proven stopped
    python scripts/reap_hung_git_writers.py --json

MEASURED 2026-09-24 01:10Z ON THE TRADING BOX, and this is the mechanism behind "fixes keep
evaporating". Four git processes had been alive since 2026-09-23 22:03:53Z:

    git -C C:\\opt\\quant -c merge.autoStash=false merge -s ours d97d2d592a9f ...
    git stash create
    git update-index --ignore-skip-worktree-entries -z --add --remove --stdin

`git update-index --stdin` was blocked on a pipe nobody would ever write to, so `git stash
create` never returned, so the release merge never returned. Across a 20 s window all four moved
0.000 s of CPU and 0 bytes of I/O: not slow, STOPPED. They held `.git/index.lock` and the
`MT5-GitWriter` mutex, and every ship step serialises on that mutex, so:

    22:41Z  adopt-and-seal: another git writer held Local\\MT5-GitWriter for the full 9 min
    22:53Z  adopt-and-seal: another git writer held Local\\MT5-GitWriter for the full 9 min
    23:00Z  adopt-and-seal: another git writer held Local\\MT5-GitWriter for the full 9 min

MT5-IntelShip, MT5-ShadowSync and MT5-SealIfClean refused on the same object, and the box sat
7 commits behind origin running code that was not the shipped code. Nothing was broken, nothing
was disabled, and nothing was reported as failing -- the desk simply stopped shipping, silently,
which is the one failure mode the principal has named as exhausting.

THE DESK ALREADY SAW IT AND COULD NOT ACT ON IT. `scripts/check_scheduled_tasks.py::stuck_writers`
names these pids every pass and its own text says "a hung ssh from 2026-09-12 held it for THREE
DAYS and refused every adopt" -- and then nothing kills them. That is III.16 exactly: an organ
that reports forever and changes nothing. This is the other half.

WHY AN AGE THRESHOLD ALONE WOULD BE WRONG, and why this measures instead. `git gc` on this
repository is legitimately slow and can outlive any threshold anyone is willing to set; killing
it mid-repack is how a repository gets corrupted. So age only makes a process a CANDIDATE. The
proof is movement: a candidate is reaped only if it burns no CPU and moves no bytes across a
sampling window. Slow writers move. Stopped ones do not.

    1. `git` or `ssh` only -- never `sshd`, which is a long-lived daemon by design and was once
       reported as a stuck writer at 3.9 days old on this very box;
    2. older than --min-age-s (default 1800 s), which is past every legitimate writer's OWN
       timeout: the adoption waits 540 s for the mutex and the shadow sync's limit is 600 s;
    3. zero CPU delta AND zero I/O delta across --sample-s;
    4. never this process and never one of its own ancestors.

Everything examined is written to the artifact, INCLUDING what was spared and why, because
"nothing was hung" and "nothing could be measured" must never render identically (L1.28a).
Without psutil the verdict is UNMEASURED and nothing is signalled.

Exit: 0 when the ship path is clear or was cleared; 2 when writers are proven stopped and
--apply was not given, because a blocked ship path is a defect whether or not this run fixed it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.git_writer_lock import (  # noqa: E402
    HUNG_MIN_AGE_S,
    HUNG_SAMPLE_S,
    reap_hung_writers,
)

OUT = _ROOT / "desks" / "mt5" / "reports" / "GIT_WRITER_REAP.json"


def build_report(*, apply: bool, min_age_s: float, sample_s: float,
                 repo: Path | None = None) -> dict[str, Any]:
    rec = reap_hung_writers(apply=apply, min_age_s=min_age_s, sample_s=sample_s,
                            repo=repo if repo is not None else _ROOT)
    n_hung, n_killed = len(rec["hung"]), len(rec["killed"])
    if rec["status"] != "MEASURED":
        verdict = "UNMEASURED"
    elif not n_hung:
        verdict = "CLEAR"
    elif n_killed == n_hung and not rec["failed"]:
        verdict = "REAPED"
    else:
        verdict = "BLOCKED"
    return {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "verdict": verdict,
        "law": ("every ship step on this box -- adopt, seal, intel-ship, shadow-sync -- "
                "serialises on one writer mutex. A process that has STOPPED while holding it "
                "blocks all four silently and forever; detecting it and not removing it is the "
                "same as not detecting it."),
        "n_hung": n_hung, "n_killed": n_killed, "n_failed": len(rec["failed"]),
        "n_spared": len(rec["spared"]),
        **rec,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="kill the writers proven stopped (default: measure and report only)")
    ap.add_argument("--min-age-s", type=float, default=HUNG_MIN_AGE_S)
    ap.add_argument("--sample-s", type=float, default=HUNG_SAMPLE_S)
    ap.add_argument("--repo", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rep = build_report(apply=a.apply, min_age_s=a.min_age_s, sample_s=a.sample_s, repo=a.repo)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"could not write {OUT}: {exc}", file=sys.stderr)

    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"git writer reap: {rep['verdict']} -- {rep['why']}")
        for row in rep["hung"]:
            print(f"  STOPPED  pid={row['pid']} {row['name']}  {row['why']}")
            print(f"           {row['cmd']}")
        for row in rep["killed"]:
            print(f"  KILLED   pid={row['pid']} {row['name']}")
        for row in rep["failed"]:
            print(f"  FAILED   pid={row['pid']} {row['name']}: {row['why']}")
        lock = rep["index_lock"]
        print(f"  index.lock: present={lock['present']} removed={lock['removed']} "
              f"-- {lock['why']}")
        print(f"  -> {OUT}")

    if rep["verdict"] in ("CLEAR", "REAPED"):
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
