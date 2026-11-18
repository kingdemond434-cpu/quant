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
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.proctree import run as _checkout_run  # noqa: E402

#: LAW FENCES -- portable. They read the REPO (constitution, doctrine, matrix, prompts, manifest),
#: so they mean the same thing in CI, in a fresh clone, and on the box. These gate every commit
#: and every push: a breach here is a breach anywhere.
_LAW_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # 2026-11-18 (zuck, "Simplify rules to a small core"): nothing outside the five core rules
    # may block a commit, a push or CI. The five rules are enforced where they act: prop-firm
    # limits by ops/release/risk_invariants.py and the halt rails, money-path code by
    # replay-shadow and the box auto-revert, secrets by the gate and .gitignore, data terms by
    # robots_gate, ROOT files by zuck. Research tools and health readings run in the STATE
    # battery below as readings. The full verdict list: simplify/fence_verdicts.csv.
    #
    # Two fences stay here because they guard hard rules, not paperwork (Auditor HOLD on #1289):
    # SEAL_CLEARS.jsonl stays append-only and parseable, so an Audit HOLD row cannot be dropped
    # or rewritten (sign_train.py auto-signs on a CLEAR row there); and every destructive pass
    # must check a live reference first, so no ledger, certificate, tape or evidence row is
    # retired against an empty or stale source.
    ("check_seal_clears.py", ()),
    ("check_no_retirement_on_absence.py", ()),
)

_STATE_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # READINGS, NOT RULES (2026-11-18). Research tools that catch fake edges and health readings
    # that name a silent organ. They run on the box's hourly rotation and report; none is one of
    # the five core rules, so none gates a commit, push or CI run.
    ("check_judging_coverage.py", ()),
    ("check_source_drain.py", ()),
    ("check_box_state_freshness.py", ()),
    ("check_own_clock_legs.py", ()),
    ("check_universe_integrity.py", ()),
    ("check_sandbox_liveness.py", ()),
    ("check_exploration.py", ()),
    ("check_calibration.py", ()),
    ("check_strategy_breadth.py", ()),
    ("run_organ_er.py", ()),
    ("check_scheduler_manifest.py", ()),
    ("check_mechanism_attribution.py", ()),
    ("check_organ_liveness.py", ()),
    ("check_seat_health.py", ()),
    ("check_leg_rotation.py", ()),
    ("check_promotion_gate.py", ()),
    ("check_clock_provenance.py", ()),
    ("check_heat_floor_wiring.py", ()),
    ("check_cost_truth.py", ()),
    ("check_cost_surface.py", ()),
    ("check_live_sleeve_cost.py", ()),
    ("check_clock_liveness.py", ()),
    ("check_certificate_clock_law.py", ()),
    ("check_ingestion_exploitation.py", ()),
    ("check_conversion_debt.py", ()),
    ("check_certificate_truth.py", ("--require-state",)),
    ("check_organ_census.py", ("--require-state",)),
    ("check_regional_parity.py", ("--strict",)),
    ("check_no_staleness.py", ()),
    ("check_judge_coverage.py", ("--require-state",)),
    ("check_plumbing_watchdog.py", ()),
    ("check_adoption_freshness.py", ()),
    ("check_placement_interlock.py", ()),
    ("check_dead_architecture.py", ("--ratchet",)),
    ("check_allocator_liveness.py", ()),
    ("check_write_or_explain.py", ("--require-state",)),
    ("check_box_reversion.py", ("--require-git",)),
    ("check_formal_claim.py", ("--require-state",)),
    ("check_paid_substitute_coverage.py", ("--require-state",)),
    ("check_organ_cadence.py", ()),
    ("check_sizing_derivation.py", ()),
    ("check_extractor_invariants.py", ()),
    ("check_family_evaluability.py", ()),
    ("check_known_by_date.py", ()),
)


def fast_gate(root: Path | None = None) -> dict[str, Any]:
    """The organ-spawn gate: the one condition under which no organ may start (a tampered core).

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

    # (2026-11-18) The doctrine-family check that stood here is gone with the law families:
    # it was a rule about rules, and it tied every organ spawn to the wording of docs/LAWS.md.

    return {"mode": "fast", "ok": not failures, "failures": failures,
            "generated": datetime.now(tz=UTC).isoformat()}


def _dirty(root: Path) -> list[str]:
    """Files that differ from HEAD, tracked or not. Empty means the tree IS HEAD."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []                          # no git -- nothing to reconcile against, judge in place
    return [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()] \
        if out.returncode == 0 else []


#: A lawgate HEAD checkout CANNOT outlive its own run: the re-exec is capped at timeout=1800 and
#: the `worktree add` at 300, so ~35min is the ceiling on a live one. Two hours is >3x that, which
#: keeps the reaper off a sibling law gate that is merely slow -- the only way to be wrong here is
#: to delete a checkout still being read, so the threshold is deliberately far past the maximum.
_ORPHAN_AFTER_S = 2 * 60 * 60


def _is_tmpfs(path: Path) -> bool:
    """True only when `path` demonstrably sits on a tmpfs. Unknown reads as False.

    Longest-prefix match against /proc/mounts, the way the kernel resolves it. Unknown must NOT
    read as tmpfs: the consequence of a wrong True is relocating a checkout onto a path that may
    not exist on a host this gate has never seen, and this gate's verdict must never depend on
    where its scratch landed.
    """
    try:
        lines = Path("/proc/mounts").read_text("utf-8").splitlines()
    except OSError:
        return False
    best, fstype = "", ""
    for line in lines:
        parts = line.split()
        if len(parts) > 2 and str(path).startswith(parts[1]) and len(parts[1]) > len(best):
            best, fstype = parts[1], parts[2]
    return fstype == "tmpfs"


def _checkout_base() -> Path:
    """Where a HEAD checkout is allocated: DISK, never RAM.

    THE DEFECT THIS CLOSES (gap-fixer 2026-08-29). `_reap_stale_checkouts` below already knows
    this checkout lands on a tmpfs -- its own docstring says "150MB of tmpfs owned by no
    process" -- and answered by reaping it after two hours. That treats the symptom. Measured
    this cycle the checkout is 297MB, it has DOUBLED since that note was written, and the box
    has 3815MB with ZERO swap: one law gate on a dirty tree claims ~50% of typical free RAM for
    its whole run, and a reaper cannot help while the run is legitimately alive. Four of these
    were allocated inside thirty minutes on this box.

    Disk is the correct home for a throwaway checkout and there is 12GB of it. `~/.cache` is the
    conventional place, is outside the repo (a checkout INSIDE it would show up in `git status`
    and is the mass-deletion launder R0423 names), and is verified not to be a tmpfs itself
    before it is used. Any failure -- no HOME, unwritable, or itself in RAM -- falls back to
    `tempfile.gettempdir()`, which is exactly today's behaviour, so this can only improve.
    """
    try:
        base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "quant-lawgate"
        if _is_tmpfs(base.parent if not base.exists() else base):
            return Path(tempfile.gettempdir())
        base.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        return Path(tempfile.gettempdir())
    return base


def _reap_stale_checkouts(root: Path, *, now: float | None = None) -> int:
    """Delete lawgate HEAD checkouts left by runs that DIED before reaching their own cleanup.

    THE DEFECT THIS CLOSES (R0407 one producer further on). `_at_head` allocates a 150MB detached
    worktree under /tmp and `full_gate` removes it in a `finally` -- which covers every path the
    interpreter walks out of, and NOT the one that actually leaks: SIGKILL. A law gate killed by
    the OOM killer never runs `finally`, so its checkout becomes 150MB of tmpfs owned by no
    process, and tmpfs is never reclaimed under pressure. That closes a loop on itself: low memory
    makes the kill likelier, the kill orphans another 150MB, and the next run starts poorer. Two
    such orphans (300MB, both clean, neither open by any process) were measured on 2026-08-13 with
    MemAvailable at 270MB against a 400MB floor -- the box could not have run its own test suite.

    WHY THE REAPER LIVES HERE AND NOT IN THE FENCE. `max_audit.check_host_memory_headroom` watches
    total /tmp occupancy and deliberately deletes NOTHING, because /tmp is shared with the live
    executor, three recorders and several concurrent agent sessions, and reaping another process's
    scratch mid-run is a worse failure than the one it fixes. That reasoning is right, and it is
    exactly why the cleanup belongs to the PRODUCER: this function touches only the `lawgate-head-`
    prefix it alone creates, and only past a lifetime a live run cannot reach. A watcher of a
    shared resource cannot safely free it; the process that allocated it can.

    Best-effort by construction. A reaper that raised would turn a disk-hygiene problem into a
    refused push, and the law gate's verdict must never depend on whether /tmp was tidy.
    """
    now = now if now is not None else time.time()
    reaped = 0
    # BOTH bases, always. The gate RE-EXECS HEAD's copy of itself, so an older HEAD still
    # allocates under gettempdir() -- and every orphan that predates the move lives there too.
    # Sweeping only the new base would strand exactly the pile this relocation exists to stop.
    candidates: list[Path] = []
    for base in {_checkout_base(), Path(tempfile.gettempdir())}:
        try:
            candidates.extend(base.glob("lawgate-head-*"))
        except OSError:
            continue                        # unreadable base is not this gate's verdict to fail
    candidates.sort()
    for d in candidates:
        try:
            if not d.is_dir() or now - d.stat().st_mtime < _ORPHAN_AFTER_S:
                continue
        except OSError:
            continue                        # vanished under us -- a concurrent reaper is fine
        subprocess.run(["git", "worktree", "remove", "--force", str(d / "t")],
                       cwd=root, capture_output=True, text=True, timeout=120, check=False)
        shutil.rmtree(d, ignore_errors=True)
        reaped += 1
    if reaped:
        # Leave no stale registration behind: `git worktree list` would keep naming a path that
        # no longer exists, and a later `worktree add` at the same path then fails outright.
        subprocess.run(["git", "worktree", "prune"], cwd=root, capture_output=True,
                       text=True, timeout=120, check=False)
    return reaped


def _at_head(root: Path) -> tuple[Path, str, list[str]]:
    """(where to run, what that place IS, why it is not HEAD). A pristine checkout when dirty.

    THE DEFECT THIS CLOSES (R0402). laws_only exists for CI and the pre-push hook, both of which
    judge COMMITTED state -- and both read the shared working tree instead. On this box that is
    not a technicality: sibling sessions build continuously in the same checkout, and on
    2026-08-05 the gate returned rc=2 on nine scripts "scheduled by the manifest but absent from
    the repo" where every one of those manifest lines existed ONLY in another session's
    uncommitted ops/crontab.manifest. `git show HEAD:ops/crontab.manifest` had zero occurrences.
    So the pre-push hook refused EVERY push on this box for a breach owned by somebody else's
    unsaved files, and the only way out was --no-verify -- which trains the desk to bypass its
    own law gate, the exact "a gate that cries wolf gets disabled" death L1.37 rule 1 names.

    A CLEAN TREE IS ALREADY HEAD, so the checkout is paid for ONLY when the verdict would
    otherwise be wrong: CI and a fresh clone are untouched and cost nothing extra.
    """
    dirt = _dirty(root)
    sparse = subprocess.run(["git", "config", "--bool", "core.sparseCheckout"],
                            cwd=root, capture_output=True, text=True, timeout=10)
    if not dirt and sparse.stdout.strip() != "true":
        return root, "cwd==HEAD (tree clean)", []
    _reap_stale_checkouts(root)             # sweep our own dead before allocating another 150MB
    tmp = Path(tempfile.mkdtemp(prefix="lawgate-head-", dir=_checkout_base()))
    wt = tmp / "t"
    try:
        # HEAD now contains 49,295 files / 3.8GB on the trading host. Parallel
        # checkout preserves the full tree and the existing 300-second budget.
        # On timeout, stop git's reset child before removing its private tree.
        r = _checkout_run(["git", "-c", "checkout.workers=8", "worktree", "add",
                           "--detach", str(wt), "HEAD"],
                          cwd=root, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout).strip()[:200])
        # Git copies the caller's sparse-checkout settings into a new worktree.
        # A law verdict must cover all committed policy/evidence files, including
        # paths intentionally absent from an operator's source-only checkout.
        # Disable sparsity only in this private HEAD checkout; never in the caller.
        r = _checkout_run(["git", "-c", "checkout.workers=8", "-C", str(wt),
                           "sparse-checkout", "disable"],
                          cwd=root, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout).strip()[:200])
        # Individually skipped files (for example a seal added with --sparse)
        # can retain that index bit after sparsity is disabled. Restore every
        # committed path explicitly; this checkout has no operator changes.
        r = _checkout_run(["git", "-c", "checkout.workers=8", "-C", str(wt),
                           "restore", "--source=HEAD", "--worktree",
                           "--ignore-skip-worktree-bits", "--", "."],
                          cwd=root, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout).strip()[:200])
    except (OSError, subprocess.SubprocessError) as exc:
        # NEVER silently fall back to the dirty tree: the whole point is that the verdict names
        # its own subject. Judging in place is still better than no verdict, but it is REPORTED.
        shutil.rmtree(tmp, ignore_errors=True)
        return root, f"cwd (HEAD CHECKOUT UNAVAILABLE: {exc}) -- verdict covers UNCOMMITTED work", \
            [f"head-checkout-unavailable: {exc}"]
    return wt, f"HEAD in a detached worktree ({len(dirt)} file(s) dirty in cwd, excluded)", []


def full_gate(root: Path | None = None, *, laws_only: bool = False,
              in_place: bool = False) -> dict[str, Any]:
    """Every fence, all failures collected. Never first-failure-only.

    laws_only=True runs the portable LAW fences alone -- the correct mode for CI and the
    pre-push hook, where live desk state does not exist and its absence is not a breach. It also
    judges HEAD rather than the working tree (R0402), because that is what those two boundaries
    are actually gating; pass in_place=True to judge the tree as it sits.

    The HEAD run RE-EXECS this script from the checkout, so the fence LIST is HEAD's too. A gate
    that judged HEAD's files against the working tree's roster would be a third artifact, which
    is the same confusion one layer down.
    """
    root = root or _ROOT
    in_place = in_place or os.environ.get("QUANT_LAWGATE_IN_PLACE") == "1"
    if laws_only and not in_place:
        where, subject, why = _at_head(root)
        if where != root:
            try:
                # RECURSION IS SUPPRESSED BY ENV, NOT BY A FLAG, and the difference is
                # load-bearing: the checkout is of HEAD, which may predate this very code. An
                # unknown --in-place makes an older copy die in argparse with empty stdout (this
                # bug, hit on the first run); an unknown env var is ignored, and an older copy
                # then does exactly what it always did -- judge in place, no recursion possible.
                env = {**os.environ, "QUANT_LAWGATE_IN_PLACE": "1",
                       "QUANT_LAWGATE_SOURCE_VIEW": "1"}
                r = subprocess.run([sys.executable, str(where / "scripts/run_law_gate.py"),
                                    "--laws-only", "--json"], cwd=where, env=env,
                                   capture_output=True, text=True, timeout=1800)
                rep = json.loads(r.stdout)
                rep["subject"] = subject
                return rep
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                why = [f"head-gate-unrunnable: {exc} -- counts as FAILED, never skipped"]
                return {"mode": "laws", "ok": False, "n_fences": 0, "n_failed": len(why),
                        "failures": why, "results": [], "subject": subject,
                        "generated": datetime.now(tz=UTC).isoformat()}
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(where)],
                               cwd=root, capture_output=True, text=True, timeout=120)
                shutil.rmtree(where.parent, ignore_errors=True)
        head_note, head_why = subject, why
    else:
        head_note, head_why = ("cwd (in-place: the working tree as it sits)"
                               if laws_only else "cwd (full gate judges LIVE state)"), []
    battery = _LAW_FENCES if laws_only else _LAW_FENCES + _STATE_FENCES
    # A LAWS-ONLY RUN IS A SOURCE VIEW WHETHER OR NOT THE TREE WAS CLEAN (2026-10-13). The HEAD
    # re-exec above already sets QUANT_LAWGATE_SOURCE_VIEW; a clean tree skipped that branch and
    # judged in place WITHOUT it, so one commit read two ways. Since the box publishes
    # gateway_state.json and JUDGE_COVERAGE.json to origin every 15 minutes, a clean CI or cloud
    # checkout read those copies as its own runtime: check_self_repair took the copied gateway
    # stamps for a live trading host (manual 0 -> 11) and check_birth_obligations judged a
    # six-day-old judge report as fresh (60 families "arrived"). Host state is judged by the
    # state battery (`--require-state`, full mode) on the host that writes it, never here.
    fence_env = {**os.environ, "QUANT_LAWGATE_SOURCE_VIEW": "1"} if laws_only else None
    results, failures = [], []
    for script, extra in battery:
        p = root / "scripts" / script
        if not p.exists():
            failures.append(f"{script}: MISSING -- an absent fence is a failed fence")
            results.append({"fence": script, "ok": False, "detail": "missing"})
            continue
        try:
            r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                               text=True, timeout=600, cwd=root, env=fence_env)
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
    failures += head_why
    return {"mode": "laws" if laws_only else "full", "ok": not failures,
            "n_fences": len(battery), "subject": head_note,
            "n_failed": len(failures), "failures": failures, "results": results,
            "generated": datetime.now(tz=UTC).isoformat()}


#: HOW LONG A FENCE'S VERDICT STANDS, and therefore how long the rotation has to reach every
#: fence in the battery. MEASURED, not chosen for comfort: `full_gate` gives each of the 53
#: fences up to 600 s, so one battery can cost eight hours and no hourly window can hold it --
#: which is exactly why `data/law_gate.json` on the trading box was 270 h old with 14 of 53
#: fences in it, and why every green claim the desk made rested on a gate that had not run.
#: A fence whose verdict is older than this window is DROPPED from the record, so the watchdog
#: reports it as never run. That is the measurement (L1.49), never a failure of the record.
ROTATION_WINDOW_H: float = 48.0

#: The longest a single fence may hold the rotation, matching `full_gate`'s own per-fence bound.
ROTATION_FENCE_TIMEOUT_S: float = 600.0

#: The least budget a fence may be started with. Below this the pass ends instead of starting a
#: fence it cannot let finish.
_ROTATION_FLOOR_S: float = 120.0

#: A fence cut short by the budget this many passes running is recorded FAILED: a deferral that
#: keeps repeating is a fence that no longer fits the battery, and that must be seen, not carried.
ROTATION_MAX_BUDGET_CUTS: int = 3


def _run_fence(root: Path, script: str, extra: tuple[str, ...],
               timeout: float) -> dict[str, Any]:
    """One fence, one verdict. An absent or unrunnable fence FAILS, it is never skipped."""
    p = root / "scripts" / script
    if not p.exists():
        return {"fence": script, "ok": False, "detail": "missing"}
    try:
        r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                           text=True, timeout=timeout, cwd=root)
    except subprocess.TimeoutExpired as exc:
        return {"fence": script, "ok": False, "timed_out": True, "timeout_s": round(timeout, 1),
                "detail": f"unrunnable: {exc} -- counts as FAILED, never skipped"}
    except OSError as exc:
        return {"fence": script, "ok": False,
                "detail": f"unrunnable: {exc} -- counts as FAILED, never skipped"}
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    return {"fence": script, "ok": r.returncode == 0, "rc": r.returncode,
            "detail": tail[-1][:200] if tail else ""}


def _record_age_s(row: dict[str, Any], now: datetime) -> float:
    """Seconds since this fence last ran; infinite when the record cannot be read."""
    try:
        return (now - datetime.fromisoformat(str(row.get("ran_at")))).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def _expected_s(row: dict[str, Any]) -> float:
    """How long this fence is expected to take, from its own last pass. A fence with no
    measured pass is assumed short (the first rotation measured 18 fences in 120 s)."""
    try:
        last = float(row.get("elapsed_s"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _ROTATION_FLOOR_S
    return min(ROTATION_FENCE_TIMEOUT_S, max(_ROTATION_FLOOR_S, 1.25 * last + 10.0))


def rotate_gate(root: Path | None = None, *, budget_s: float = 1800.0,
                now: datetime | None = None) -> dict[str, Any]:
    """THE WHOLE BATTERY, IN ROTATION, INSIDE A STATED WINDOW.

    The full battery does not fit an hourly window, and a gate that cannot fit its window does
    not run at all -- which is how the box reached 270 h with no battery record. This mode runs
    the fences that have gone longest without a verdict until the budget is spent, then MERGES
    them into `data/law_gate.json` so the record carries every fence with the time it ran.

    Three properties the record must keep, because the whole point is that it can be cashed:

      EVERY FENCE NAMES ITS OWN HOUR.  Each row carries `ran_at` and `elapsed_s`, so "the gate
      is green" can always be answered with "measured when?".

      THE WINDOW IS STATED AND ENFORCED.  A verdict older than ROTATION_WINDOW_H is dropped,
      not carried forward -- a fence that stops running disappears from the record within the
      window and is reported as never run.

      NOTHING IS EVER SKIPPED FOR BEING SLOW.  Oldest-first ordering means a slow fence cannot
      be starved by fast ones: it only ever climbs the queue.

    A FENCE IS NEVER STARTED ON A CLOCK IT CANNOT FINISH IN (Desk health, 2026-11-06 00:47Z:
    passes ran 1,800-2,027 s against the 1,800 s budget and five fences were recorded FAILED as
    "unrunnable ... timed out" -- verdicts about the budget, not about the desk). After the
    first fence of a pass, a fence starts only when the budget left covers its own expected time
    (its last measured pass, plus a margin); one that does not fit is DEFERRED and stays at the
    head of the queue, so the next pass starts with it on the full per-fence clock. Faster fences
    still use the rest of this pass. A fence cut short by the BUDGET (its timeout was below the
    full ROTATION_FENCE_TIMEOUT_S) gets no verdict this pass: its last real verdict, with its own
    `ran_at`, is kept and ages out inside the window as before. A fence that times out on the
    FULL per-fence clock still FAILS, exactly as before. No fence is dropped and no bar moves.
    """
    root = root or _ROOT
    t0 = now or datetime.now(tz=UTC)
    # One entry per fence SCRIPT, carrying every argument set the battery declares for it (the
    # same script rides both batteries with different flags; the record is keyed by name because
    # `check_fences_ran` asks by name).
    declared: dict[str, list[tuple[str, ...]]] = {}
    for script, extra in (*_LAW_FENCES, *_STATE_FENCES):
        declared.setdefault(script, []).append(tuple(extra))
    prior: dict[str, dict[str, Any]] = {}
    try:
        doc = json.loads((root / "data/law_gate.json").read_text("utf-8"))
        rec = doc.get("fences") if isinstance(doc, dict) else None
        if isinstance(rec, dict):
            prior = {str(k): dict(v) for k, v in rec.items() if isinstance(v, dict)}
    except (OSError, ValueError):
        prior = {}
    due = sorted(declared, key=lambda n: (-_record_age_s(prior.get(n, {}), t0), n))
    ran: list[str] = []
    deferred: list[str] = []
    for name in due:
        left = budget_s - (datetime.now(tz=UTC) - t0).total_seconds()
        # A FENCE IS NEVER JUDGED ON A TRUNCATED CLOCK. Measured on the first rotation pass:
        # check_enforcement_execution was started with 32 s of budget left, timed out, and was
        # recorded as FAILED -- a verdict about the budget wearing the costume of a verdict about
        # the desk. Below the floor the pass simply ends and the fence stays at the head of the
        # queue for the next one.
        if ran and left < _ROTATION_FLOOR_S:
            break
        first = not ran and not deferred
        if not first and _expected_s(prior.get(name, {})) > left:
            deferred.append(name)
            continue
        started = datetime.now(tz=UTC)
        rows = []
        for extra in declared[name]:
            left = budget_s - (datetime.now(tz=UTC) - t0).total_seconds()
            # The first fence of a pass gets the full per-fence clock on EVERY argument set (Auditor
            # SF1 on 6c98f5ff9), so the head of the queue is never cut by the budget.
            clock = ROTATION_FENCE_TIMEOUT_S if first else min(ROTATION_FENCE_TIMEOUT_S, left)
            rows.append(_run_fence(root, name, extra, max(clock, 1.0)))
        cut = any(r.get("timed_out") and r.get("timeout_s", 0) < ROTATION_FENCE_TIMEOUT_S
                  for r in rows)
        cuts = int(prior.get(name, {}).get("budget_cuts") or 0) + 1 if cut else 0
        if cut and cuts < ROTATION_MAX_BUDGET_CUTS:
            # Cut short by the budget: no verdict, first in line next pass. The count is kept so
            # the deferral cannot repeat silently (Auditor SF2 on 6c98f5ff9).
            prior[name] = {**prior.get(name, {}), "budget_cuts": cuts}
            deferred.append(name)
            continue
        if cut:
            rows = [{"fence": name, "ok": False, "timed_out": True,
                     "detail": f"cut short by the rotation budget {cuts} passes running -- "
                               "counts as FAILED, never carried"}]  # fmt: skip
        bad = [r for r in rows if not r["ok"]]
        row = dict(bad[0] if bad else rows[0])
        row["ok"] = not bad
        row["n_invocations"] = len(declared[name])
        row["budget_cuts"] = cuts
        row["ran_at"] = started.isoformat()
        row["elapsed_s"] = round((datetime.now(tz=UTC) - started).total_seconds(), 1)
        prior[name] = row
        ran.append(name)
    t1 = datetime.now(tz=UTC)
    window_s = ROTATION_WINDOW_H * 3600.0
    fences = {n: r for n, r in prior.items()
              if n in declared and _record_age_s(r, t1) <= window_s}
    results = [fences[n] for n in sorted(fences)]
    failures = [f"{r['fence']} (rc={r.get('rc', '?')}): {r.get('detail', '')}"
                for r in results if not r.get("ok")]
    missing = sorted(n for n in declared if n not in fences)
    failures += [f"{n}: no verdict inside the {ROTATION_WINDOW_H:.0f}h rotation window -- "
                 f"a gate that never ran is a claim the desk cannot cash (L1.49)"
                 for n in missing]
    return {"mode": "rotation", "ok": not failures, "n_fences": len(declared),
            "subject": f"cwd (rotation judges LIVE state; {ROTATION_WINDOW_H:.0f}h window)",
            "n_failed": len(failures), "failures": failures, "results": results,
            "fences": fences,
            "rotation": {"window_h": ROTATION_WINDOW_H, "budget_s": budget_s,
                         "ran_this_pass": ran, "deferred_this_pass": deferred,
                         "n_recorded": len(fences),
                         "n_declared": len(declared), "never_recorded": missing,
                         "oldest_ran_at": min((str(r.get("ran_at")) for r in results),
                                              default=None)},
            "generated": t1.isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="organ-spawn gate: sealed core + doctrine carries every family")
    ap.add_argument("--laws-only", action="store_true",
                    help="portable law fences only -- for CI and the pre-push hook, where live "
                         "desk state does not exist and its absence is not a breach")
    ap.add_argument("--in-place", action="store_true",
                    help="judge the working tree as it sits instead of HEAD. --laws-only judges "
                         "HEAD by default because that is what a push and CI actually gate; this "
                         "is the escape hatch, and the re-exec inside the HEAD checkout uses it")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rotate", action="store_true",
                    help="run the OLDEST fences until --budget-s is spent and merge them into "
                         "data/law_gate.json: the battery costs hours and no clock window holds "
                         "it, so it rides a rotation whose window is stated in the record")
    ap.add_argument("--budget-s", type=float, default=1800.0,
                    help="seconds of fence time one rotation pass may spend (default 1800)")
    args = ap.parse_args()
    if args.fast:
        rep = fast_gate()
    elif args.rotate:
        rep = rotate_gate(budget_s=args.budget_s)
    else:
        rep = full_gate(laws_only=args.laws_only, in_place=args.in_place)
    if not args.fast:
        (_ROOT / "data/law_gate.json").write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        head = "LAW GATE" + (" (fast)" if args.fast
                             else f" -- {rep.get('n_fences', 0)} fences")
        rot = rep.get("rotation")
        if isinstance(rot, dict):
            head += (f" [rotation: {len(rot.get('ran_this_pass') or [])} ran this pass, "
                     f"{rot.get('n_recorded')} of {rot.get('n_declared')} inside "
                     f"{rot.get('window_h')}h]")
        print(f"{head}: {'PASS' if rep['ok'] else 'FAIL'}")
        # The verdict NAMES ITS OWN SUBJECT (R0402): "PASS" is meaningless until you know which
        # artifact passed -- HEAD, or a working tree three sessions are writing to right now.
        if not args.fast and rep.get("subject"):
            print(f"  judged: {rep['subject']}")
        for f in rep["failures"]:
            print(f"  BREACH  {f}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
