"""Keep the desk box running the code that was committed here -- and re-ship it when it drifts.

WHY THIS EXISTS

Deploying to the desk box is verified by hash, which answers "did this land". It does not answer
"is this still there", and only the second question matters an hour later. Measured 2026-08-28:
job_lock.py was deployed and hash-verified TWICE, and both times was gone within the hour --
the box was running a copy with no memory admission at all, so the cache warmer died on
`TypeError: exclusive_job() got an unexpected keyword argument 'need_mb'`. orthogonal_sweep.py
went the same way an hour later, taking the calendar-key repair with it.

The box holds its own git checkout on a branch that diverged hundreds of commits ago, and
something there restores the working tree from it. So a fix does not fail on arrival; it decays
afterwards, silently, and the desk quietly resumes running last week's engine while every log
says the deployment succeeded.

WHAT THIS DOES

Compares each remotely-executed module's `git hash-object` on both boxes and re-ships the ones
that drifted. Cheap enough to run every few minutes, which is the point: the window between a
revert and the next sweep is where the damage happens.

THE ONE SAFETY PROPERTY THAT MATTERS: it only ever ships a file that matches HEAD. This box has a
replayer of its own that reverts working-tree files to ancient copies, and a healer that shipped
whatever happened to be on disk would faithfully propagate a trampled file to the box that
trades. A dirty file is REPORTED and skipped, never sent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "desk_module_drift.json"
REMOTE = "contabo-mt5"

#: Everything the desk box EXECUTES that is authored here. Keep this list in step with
#: run_external_pipeline's REMOTE_MODULES plus the PowerShell the box runs on a schedule; a
#: module missing from here is one that can silently decay back to the box's own stale branch.
MODULES = [
    "desks/mt5/mt5desk/families.py",
    "desks/mt5/mt5desk/families_orthogonal.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/universe.py",
    "desks/mt5/research/job_lock.py",
    "desks/mt5/research/edge_search.py",
    "desks/mt5/research/orthogonal_sweep.py",
    "desks/mt5/research/merge_hypotheses.py",
    "desks/mt5/research/hourly_cycle.py",
    # The admission door and the promoter: they decide what may gather forward evidence
    # and what may be promoted. Neither was watched, and both were just changed to open
    # the cure lane beyond one family -- a revert here silently re-closes it.
    "desks/mt5/research/shadow_admission.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/side_channels/promoter_fixed.py",
    "desks/mt5/research/backfill_coverage.py",
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/scripts/warm_gauntlet_cache.py",
    "desks/mt5/scripts/stall_watch.ps1",
    "libs/research/bar_span.py",
    # The program-level gates the sweep imports. reality_check was NOT on this list and
    # was stale on the box by a full optimisation (2026-08-28) -- a module can be central
    # to certification and still be invisible to every sync, because nothing names it.
    "libs/validation/reality_check.py",
    "libs/validation/pbo.py",
    "libs/validation/bootstrap.py",
    # THE REST OF THE GAUNTLET'S IMPORT CLOSURE. The list above was hand-typed from whatever was
    # being fixed the day the deploy path was built (2026-08-27), which is why reality_check --
    # central to certification -- sat six weeks stale on the box, at the 2026-07-16 baseline,
    # invisible to every sync because no list named it. A watchlist that does not follow the
    # import graph will always be missing exactly the module nobody thought about.
    # Derived by walking `external_gauntlet`'s imports; re-derive it when the graph changes.
    "libs/validation/dsr.py",
    "libs/validation/cpcv.py",
    "libs/validation/walk_forward.py",
    "libs/validation/revalidation.py",
    "libs/validation/errors.py",
    "libs/core/errors.py",
    "libs/core/time.py",
    "libs/self_improvement/models.py",
    "desks/mt5/mt5desk/canonical.py",
    "desks/mt5/research/frontier_identity.py",
    # The gate POLICY and the spec it reads. The box was running the pre-YAML loader while the
    # spec beside it was already the current one; both must move together or the loader reads a
    # file it does not expect. Safe to heal automatically only because this ships nothing that
    # differs from HEAD -- an unreviewed local edit can never reach certification this way.
    "desks/mt5/research/gate_policy.py",
    "desks/mt5/policy/gate_spec.yaml",
    # THE DAILY MONEY-PATH CHAIN, added 2026-08-28 after it decayed exactly as the comment at the
    # head of this list predicted. `hourly_cycle` was watched; `daily_cycle` -- the module it
    # calls, which IS the chain -- was not, so the caller was pinned to HEAD while the callee
    # silently sat on the box's own stale branch. MEASURED that day: the box's STEPS tuple began
    # at `futures_curves` and held SIX steps against HEAD's fourteen, and the string "decay" did
    # not appear in the file at all (findstr, positive-controlled against "markout"). So
    # refresh_bars, cost_fields, reconcile, qquant_shadow, execution, portfolio, decay and zentech
    # had never run on the machine that trades -- including decay_monitor, which LAWS L1.59 has
    # required since 2026-08-25 and whose absence means seven live sleeves carry no decay clock:
    # nothing on that box would fade a sleeve at t<=0 or retire one at maxDD<=-25R.
    # This fence reported "all 32 match HEAD on both boxes" throughout. A watchlist that does not
    # follow the import graph will always be missing exactly the module nobody thought about --
    # and here it was missing the one that decides what the book keeps holding.
    "desks/mt5/research/daily_cycle.py",
    "desks/mt5/research/decay_monitor.py",
    "desks/mt5/research/forward_reconcile.py",
    "desks/mt5/research/portfolio_evidence.py",
    "desks/mt5/research/shadow_forward.py",
    "desks/mt5/research/qquant_shadow.py",
    "desks/mt5/research/curve_strategy_screen.py",
    "desks/mt5/research/fetch_futures_curves.py",
    "desks/mt5/mt5desk/markout.py",
    "desks/mt5/mt5desk/shadow_execution.py",
    "desks/mt5/scripts/refresh_tail.py",
    "desks/mt5/scripts/refresh_cost_fields.py",
    "scripts/build_zentech_state.py",
    # DETECTED BUT NEVER HEALED. `check_desk_code_parity.py` had been reporting these two DIVERGED
    # while this fence -- the only one that ships -- did not carry them, so the desk held the
    # finding and no organ closed it. Verified before adding: both box blobs are objects that
    # EXIST IN THIS HISTORY (git cat-file -e) and both files are clean against HEAD here, so the
    # box is simply behind and healing destroys no operator hotfix. sleeve_registry.py is the
    # money path's own registry and the box was missing 4fb548e4 ("six clocks died against a
    # families.py that no longer exists"); scalp_shadow.py is one of the two bespoke shadow
    # engines RESEARCH 6d already carries as a standing defect.
    "desks/mt5/research/sleeve_registry.py",
    "desks/mt5/research/scalp_shadow.py",
    # THE MOAT PAIR. Both run on the box (they read C:\moat\bronze and write the tape summary
    # this box then pulls), so a fix committed here is INERT until it ships -- which is the
    # failure this whole list exists to stop. moat_miner just had its alphabetical-prefix
    # selection replaced with a rotation cursor: 40 of 245 tick symbols were being re-mined
    # every run and 205 had never been mined at all.
    "desks/mt5/moat/moat_miner.py",
    "desks/mt5/moat/moat_silver.py",
    # The task installer lives on the box beside the PowerShell it registers.
    "desks/mt5/scripts/install_moat_miner_task.ps1",
]


def _run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def _local_hash(rel: str) -> str | None:
    rc, out = _run(["git", "hash-object", str(ROOT / rel)])
    return out if rc == 0 and out else None


def _head_hash(rel: str) -> str | None:
    """The hash HEAD says this file should have -- the only version safe to ship."""
    rc, out = _run(["git", "rev-parse", f"HEAD:{rel}"])
    return out if rc == 0 and out else None


def _remote_hash(rel: str) -> str | None:
    rc, out = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                    f"cd C:\\opt\\quant && git hash-object {rel}"])
    if rc != 0:
        return None
    line = out.replace("\r", "").strip().splitlines()
    return line[-1].strip() if line else None


def main() -> int:
    now = datetime.now(tz=UTC)
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "drifted": [], "healed": [], "dirty_skipped": [], "unreachable": []}

    for rel in MODULES:
        if not (ROOT / rel).exists():
            continue
        local, head = _local_hash(rel), _head_hash(rel)
        if local is None or head is None:
            report["unreachable"].append(rel)
            continue
        # NEVER SHIP WHAT DOES NOT MATCH HEAD. A trampled local file is exactly the thing this
        # must not propagate to the box that trades.
        if local != head:
            report["dirty_skipped"].append(rel)
            print(f"  DIRTY {rel}: local copy differs from HEAD -- not shipped (heal it here "
                  f"first; shipping a trampled file is how the desk got an ancient engine)")
            continue
        remote = _remote_hash(rel)
        if remote is None:
            report["unreachable"].append(rel)
            continue
        if remote == local:
            continue
        report["drifted"].append(rel)
        rc, _ = _run(["scp", "-o", "ConnectTimeout=45", "-q",
                      str(ROOT / rel), f"{REMOTE}:C:/opt/quant/{rel}"], timeout=180)
        after = _remote_hash(rel) if rc == 0 else None
        if after == local:
            report["healed"].append(rel)
            print(f"  RE-SHIPPED {rel}: box had {remote[:8]}, now {after[:8]} (matches HEAD)")
        else:
            print(f"  FAILED to re-ship {rel}: box still {str(after)[:8]}")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    n_d, n_h = len(report["drifted"]), len(report["healed"])
    if report["dirty_skipped"]:
        print(f"DIRTY LOCALLY (not shipped): {', '.join(report['dirty_skipped'])}")
    if n_d:
        print(f"desk module drift: {n_d} drifted, {n_h} healed -> {OUT}")
        return 1
    print(f"desk modules: all {len(MODULES)} match HEAD on both boxes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
