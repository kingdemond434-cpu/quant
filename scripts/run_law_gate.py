#!/usr/bin/env python3
"""THE LAW GATE (L1.37) -- every law, enforced at every boundary, continuously.

PRINCIPAL ORDER (2026-07-31): *"make all these principles enforced 24/7 with every interaction
with anything."*

THE GAP THIS CLOSES, and it was large. Every fence this desk owns ran on a CRON TICK and nowhere
else. Between ticks -- and CI ran only pytest, with no git hooks at all -- a commit could land, a
push could ship, and an organ could spawn under a tampered constitution, a stripped doctrine, or
a broken law family, with nothing watching until the next scheduled run hours later. Laws were
enforced PERIODICALLY. This makes them enforced AT EVERY BOUNDARY:

    boundary                     mode      what it stops
    ------------------------------------------------------------------------------------------
    organ spawn (brain_env.sh)   --fast    an organ running under a tampered core or a doctrine
                                           that no longer carries the laws it is meant to obey
    git push (pre-push hook)     full      a breach leaving the box for master
    CI (every push + PR)         full      a breach entering the tree from anywhere
    hourly cron                  full      drift that arrives without a commit (state, artifacts)

TWO MODES, because a gate that is too slow to run at a boundary will be removed from it:
  --fast  (~1s, no subprocesses): the immutable-core seal + doctrine carries every family's laws.
          These are the two conditions under which an organ must NEVER be allowed to start.
  full    every fence, each in its own process, all failures collected and reported together --
          never first-failure-only, because a gate that hides four breaches behind one is a gate
          that gets run once and disbelieved.

REFUSAL IS THE DEFAULT. An unrunnable fence counts as a FAILED fence, never a skipped one: if
this gate cannot prove a law holds, it must not claim it does (L1.28a's rule applied to
enforcement itself).

    python scripts/run_law_gate.py [--fast] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: LAW FENCES -- portable. They read the REPO (constitution, doctrine, matrix, prompts, manifest),
#: so they mean the same thing in CI, in a fresh clone, and on the box. These gate every commit
#: and every push: a breach here is a breach anywhere.
_LAW_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_constitution_core.py", ()),        # L2.8a -- the sealed core is intact
    ("check_law_families.py", ()),             # L1.36 -- families complete/fenced/reaching/guarded
    ("check_timidity_language.py", ()),        # L1.28 -- incl. all 18 prompt surfaces
    ("build_enforcement_matrix.py", ()),       # L2.0 -- no law is prose, no fence is an orphan
    # --report-only: the LAW half is manifest<->repo integrity (exit 2). Live-crontab DRIFT
    # (exit 1) is BOX STATE -- on a red-parked box the manifest is *supposed* to be ahead of
    # the installed crontab until the puller vets the commit, so drift failing CI/pre-push
    # wedges the exact push that would heal it. The bare run lives in _STATE_FENCES.
    ("check_scheduler_manifest.py", ("--report-only",)),  # L1.28c -- every line is decided
    ("check_build_standard.py", ()),           # L1.41 -- nothing enters below standard
    ("check_sizing_derivation.py", ()),        # L1.41 -- no money number chosen by feel
    ("check_return_targeting.py", ()),         # handoff 2026-07-12 -- no CAGR target
)

#: STATE FENCES -- box-only. They measure LIVE STATE (artifacts, ledgers, organ freshness) that
#: exists solely on the VPS, so in CI or a fresh clone their "failure" means "this machine has no
#: desk state", not "a law was broken". Running them as a commit gate would make the gate cry
#: wolf on every PR, and a gate that cries wolf gets disabled -- which is how enforcement dies.
#: They run in the hourly box gate, where their verdict is real.
_STATE_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_conversion.py", ()),               # L1.28b -- FLATLINE fails
    ("check_exploration.py", ()),              # L1.32 -- no exploration organ gone dark
    ("check_calibration.py", ()),              # L1.29 -- no ungraded past-due forecast
    ("check_replacement_rate.py", ()),         # L1.30 -- births vs deaths
    ("check_change_window.py", ()),            # L1.38 -- money-path freeze windows
    ("check_scheduler_manifest.py", ()),       # L1.28c state half -- live crontab drift (rc=1)
    ("check_mechanism_attribution.py", ()),    # L1.6 -- no survival on unexplained P&L
    ("check_organ_liveness.py", ()),           # L1.28c -- every organ actually produces
    ("check_promotion_gate.py", ()),           # L1.6 -- expansion is bought with evidence
)


def fast_gate(root: Path | None = None) -> dict[str, Any]:
    """The organ-spawn gate: the two conditions under which no organ may ever start.

    Deliberately in-process and dependency-free -- it runs before EVERY organ, so anything
    slower would be deleted from the spawn path the first time someone profiled a cycle."""
    root = root or _ROOT
    failures: list[str] = []

    # 1. THE SEALED CORE. An organ running under a tampered constitution is worse than no organ.
    try:
        r = subprocess.run([sys.executable, str(root / "scripts/check_constitution_core.py")],
                           capture_output=True, text=True, timeout=60, cwd=root)
        if r.returncode != 0:
            failures.append(f"CORE-SEAL: {(r.stdout + r.stderr).strip()[:200]}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(f"CORE-SEAL unrunnable ({exc}) -- counts as FAILED, never skipped")

    # 2. THE DOCTRINE CARRIES EVERY FAMILY. The doctrine is what reaches the organ; if a family's
    #    laws are missing from it, that organ is about to run without them (the L2.3 defect).
    try:
        from scripts.check_law_families import FAMILIES
        doctrine = (root / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
        for fam, (members, _fence, _prevents) in FAMILIES.items():
            missing = [m for m in members if m not in doctrine]
            if missing:
                failures.append(f"DOCTRINE-GAP: family '{fam}' missing {missing} -- an organ "
                                "spawning now would never be told these laws")
    except Exception as exc:
        failures.append(f"DOCTRINE-CHECK unrunnable ({exc}) -- counts as FAILED")

    return {"mode": "fast", "ok": not failures, "failures": failures,
            "generated": datetime.now(tz=UTC).isoformat()}


def full_gate(root: Path | None = None, *, laws_only: bool = False) -> dict[str, Any]:
    """Every fence, all failures collected. Never first-failure-only.

    laws_only=True runs the portable LAW fences alone -- the correct mode for CI and the
    pre-push hook, where live desk state does not exist and its absence is not a breach."""
    root = root or _ROOT
    battery = _LAW_FENCES if laws_only else _LAW_FENCES + _STATE_FENCES
    results, failures = [], []
    for script, extra in battery:
        p = root / "scripts" / script
        if not p.exists():
            failures.append(f"{script}: MISSING -- an absent fence is a failed fence")
            results.append({"fence": script, "ok": False, "detail": "missing"})
            continue
        try:
            r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                               text=True, timeout=600, cwd=root)
            ok = r.returncode == 0
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            results.append({"fence": script, "ok": ok, "rc": r.returncode,
                            "detail": tail[-1][:200] if tail else ""})
            if not ok:
                failures.append(f"{script} (rc={r.returncode}): "
                                f"{tail[-1][:160] if tail else 'no output'}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"fence": script, "ok": False, "detail": f"unrunnable: {exc}"})
            failures.append(f"{script}: UNRUNNABLE ({exc}) -- counts as FAILED, never skipped")
    return {"mode": "laws" if laws_only else "full", "ok": not failures,
            "n_fences": len(battery),
            "n_failed": len(failures), "failures": failures, "results": results,
            "generated": datetime.now(tz=UTC).isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="organ-spawn gate: sealed core + doctrine carries every family")
    ap.add_argument("--laws-only", action="store_true",
                    help="portable law fences only -- for CI and the pre-push hook, where live "
                         "desk state does not exist and its absence is not a breach")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = fast_gate() if args.fast else full_gate(laws_only=args.laws_only)
    if not args.fast:
        (_ROOT / "data/law_gate.json").write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        head = "LAW GATE" + (" (fast)" if args.fast else f" -- {rep.get('n_fences', 0)} fences")
        print(f"{head}: {'PASS' if rep['ok'] else 'FAIL'}")
        for f in rep["failures"]:
            print(f"  BREACH  {f}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
