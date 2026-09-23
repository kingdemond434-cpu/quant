"""THE STANDING BATTERIES -- every organ the desk built, on a clock, in rotation.

    python desks/mt5/research/batteries.py --battery fences --once --budget-s 180
    python desks/mt5/research/batteries.py --battery organs --once --budget-s 300
    python desks/mt5/research/batteries.py --roster            # what is rostered, and why

THE DEFECT THIS CLOSES (principal, 2026-09-22: "hunt all unwired unused unscheduled etc n make
all wired used scheduled everything. 100 percent of everything built always must be used never
forgotten"). `scripts/check_component_registry.py` counts executables with a `main()` and no
clock anywhere in the repository. It read 684 on 2026-09-17 and 200 on 2026-09-22 after nine
builders wired their own organs by hand. The residue is not one missing leg: it is a LONG TAIL of
fences, standing fixers and region organs, each too small to deserve an hourly leg of its own and
each, on its own, invisible the moment it stopped being run -- UNWIRED OR IDLE IS A DEFECT
(LAWS 7 / III.16), and a fence that never runs is a claim the desk cannot cash (L1.49).

WHAT A BATTERY IS. A named ROSTER of organs the desk owns, run IN ROTATION under one hourly
budget: as many as the budget affords this hour, starting where the last pass stopped, so every
rostered organ runs within `len(roster) / per_pass` hours and the artifact publishes, per organ,
its last verdict and the AGE of that verdict. A rotation is a real clock -- slower than hourly,
named, measured, and never a mood.

WHY NOT ONE LEG EACH. Fifty-five legs already run in the hour and each costs an interpreter
start plus its own budget; forty more would spend the hour on process starts. Why not
`data/auto_legs.json` (`wiring_ceo.auto_legs`, `hourly_cycle.run_auto_legs`)? That machinery
exists and is EMPTY -- `{"at": "2026-09-16T21:33:23+00:00", "legs": []}` on the box, measured the
day this was written -- because it only ever clocks what PROBATION has just proven, and probation
has not run. The batteries are the standing half: a curated roster, in the source, that a reader
can open, that `components.scripts_named_in` can see, and that does not depend on a queue.

THE ROSTERS, and the rule each one obeys:

  fences  READ-ONLY verdict producers -- `scripts/check_*.py` that no law-gate battery runs,
          the audits and the monitors. They measure and print; they never write desk state.
          Every one was MEASURED runnable with no arguments before it was rostered (the probe of
          2026-09-22); an organ that needs an operator's argument is not rostered, it is retired.
  organs  Everything else that runs unattended: the standing fixers (`heal_*`, `reap_*`), the
          region organs, the report builders. A fixer runs in its PRODUCTION mode, never
          `--dry-run`: the dry-run trap (`wiring_ceo`, 2026-09-17) is an organ that holds a clock
          and donates nothing, which is what being unwired already produced.

WHAT IS NOT HERE. An organ whose docstring says it places orders, copies the money path, or
migrates an identity is NEVER rostered: the gateway and the promoter own the money path and a
battery may not become a second writer of it. Those are retired instead, with a row in
`docs/research/retirements.jsonl` naming the replacement.

THE ARTIFACT (`desks/mt5/reports/BATTERY_<NAME>.json`, every hour) publishes the roster with each
organ's last rc, duration and output tail, the ones that have NEVER run, and `failing` -- the
organs whose last verdict was non-zero. `research/wiring_ceo.py` reads it (`battery_state`), so a
rostered organ that has been failing for a day appears on the CEO docket rather than in silence.

THE BUDGET IS DERIVED, NEVER SIZED OFF A MACHINE. Each organ gets a share of the budget this
pass was given (floored, so a forty-organ roster does not hand each one three seconds), and a new
organ is not started when free physical memory has fallen below a share of what this machine
actually has -- measured here, never assumed (CLAUDE.md: the 96 GB note that was about the other
box). An unreadable memory counter is UNMEASURED and starts the organ: absence is not a verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]

STATE = DESK / "data" / "battery_state.json"

#: A rostered organ gets at most this share of the pass budget, so one slow organ cannot eat a
#: whole rotation, and at least MIN_SLICE_S, so a long roster does not degenerate into timeouts.
PER_ENTRY_SHARE = 0.34
MIN_SLICE_S = 20.0
MAX_SLICE_S = 150.0
#: A new organ is not started when free physical memory is below this share of TOTAL measured
#: physical memory on THIS machine. A share, never a megabyte count: the desk has twice sized a
#: floor off the wrong box's RAM.
MEM_FLOOR_SHARE = 0.06


@dataclass(frozen=True)
class Entry:
    """One rostered organ: the path a clock can run, the argv it needs, and why it is here."""

    path: str
    argv: tuple[str, ...]
    why: str


def _e(path: str, why: str, *argv: str) -> Entry:
    return Entry(path=path, argv=tuple(argv), why=why)


#: THE FENCE ROSTER -- read-only verdicts, each measured runnable with no arguments 2026-09-22.
FENCES: tuple[Entry, ...] = (
    _e("scripts/check_bar_coverage.py", "every symbol the desk claims to trade has bars"),
    _e("scripts/check_bar_coverage_ratchet.py",
       "instruments-by-timeframe goes UP and never down, per host"),
    _e("scripts/check_bar_history_floor.py", "H1 history may never silently collapse"),
    _e("scripts/check_blueprint_coverage.py", "a capability's claim may not outrun its evidence"),
    _e("scripts/check_breadth_mandate.py", "an alpha cluster that received NO attempt is a defect"),
    _e("scripts/check_cert_yield.py", "when the pipeline certifies nothing, say WHICH nothing"),
    _e("scripts/check_credentials.py", "what needs a credential, and what breaks without it"),
    _e("scripts/check_data_recoverability.py", "L1.65 -- lost span, and can it be bought back"),
    _e("scripts/check_desk_manifest.py", "the manifest describes the repo that exists"),
    _e("scripts/check_dig_roi.py", "a cycle is scored by candidates and certificates"),
    _e("scripts/check_disposition_landed.py", "R0742 -- `implemented` cites a commit in branch"),
    _e("scripts/check_frozen_values.py", "L1.66 -- a daemon's config is the config on disk"),
    _e("scripts/check_governance_pulse.py", "the governing documents, in the GROWTH direction"),
    _e("scripts/check_ground_conversion.py", "a ground with no converter is a defect"),
    _e("scripts/check_knob_sensitivity.py", "does the protection constant change anything"),
    _e("scripts/check_ledger_reversion.py", "no merge may un-decide a recommendation"),
    _e("scripts/check_oom_pressure.py", "organ deaths by OOM, the largest unmeasured loss"),
    _e("scripts/check_pegged_duplicates.py", "two tickers, one bet: the orthogonality hole"),
    _e("scripts/check_perishability.py", "does delay cost DELAY, or THE DATA"),
    _e("scripts/check_producer_yield.py", "every producer produces, or it is replaced"),
    _e("scripts/check_reachability.py", "every capability reaches a decision, or is advisory"),
    _e("scripts/check_research_allocation.py", "what the search budget bought, per mechanism"),
    _e("scripts/check_research_health.py", "the WHOLE hourly loop, and the call for repair"),
    _e("scripts/check_row_conversion.py", "every mined row converts to cells, or is refused"),
    _e("scripts/check_scheduled_tasks.py", "a missing scheduled task is the invisible failure"),
    _e("scripts/check_shell_hygiene.py", "the ops launchers stay POSIX-clean"),
    _e("scripts/check_swap_reliability.py", "R0595 -- an upgrade is gauntleted on capability"),
    _e("scripts/check_tier5_audit.py", "the audit cannot claim what the repository lacks"),
    _e("scripts/check_unmeasurable_claims.py", "every 'cannot measure' is re-litigated"),
    _e("scripts/audit_mt5_capability_reuse.py", "every shared library organ mapped to this desk"),
    _e("scripts/monitor_data_decay.py", "the decay of what the desk already ingested"),
    _e("scripts/monitor_mt5_shadow_sync.py", "read-only watchdog on the synced shadow state"),
    _e("scripts/info_class_map.py", "the information-class map (L5 modality-blind mandate)"),
    _e("scripts/have_memory.py", "the ExecCondition probe: is there room to start a job"),
    _e("desks/mt5/scripts/check_desk_health.py", "is the desk running, in plain English"),
    _e("desks/mt5/scripts/check_llm_seat.py", "why this box has no seat, without printing a key"),
    _e("desks/mt5/scripts/disk_census.py", "what is on this disk, and what deleting it costs"),
    # Landed by another builder on 2026-09-23 with no clock of their own; both are read-only and
    # were measured runnable the same day. If either later joins the law gate, the registry will
    # show that clock beside this one -- a fence running twice is cheap, a fence running nowhere
    # is the defect.
    _e("scripts/check_seat_health.py", "every configured seat donates, or it is named"),
    _e("scripts/check_recommendation_flow.py", "the lane from recommendation to implementation "
       "must DRAIN"),
    # --- THE THREE DETECTORS `self_repair_registry` NAMES AND NOTHING RAN (2026-09-23).
    # Each is the declared detector of a defect class, and each had no clock on either box, so
    # its class read MANUAL or UNMEASURED -- "found by a person" -- when in fact the detector
    # existed, worked, and was simply never fired. That is the registry measuring the absence of
    # a clock and reporting it as the absence of a detector.
    #   check_box_tasks     BOX_TASKS.json was 168.7h old on the trading box against a 24h
    #                       window. Its only "schedule" was `invoked:libs/research/forests.py`,
    #                       which the registry derived from forests.py naming it in PROSE: a
    #                       comment is not a clock. Measured rc=2 there (5 UNDECLARED triggers),
    #                       so the silence was hiding a live breach, not a clean class.
    #   check_claim_consistency  writes data/claim_consistency.json. Its only callers are
    #                       autofix_defects/blindspot_autofix, which invoke it through
    #                       `.venv/bin/python` -- a POSIX path that does not exist on either
    #                       Windows box, so it had never run on either.
    #   check_protected_records  ran ONLY from ops/githooks/pre-commit. `--range HEAD~1 HEAD`
    #                       makes the clocked pass audit the commit that just landed, which is a
    #                       real measurement; with no argument it would compare an empty index
    #                       against HEAD and publish a vacuous OK.
    _e("scripts/check_box_tasks.py", "a scheduled task that expired, was disabled, or was never "
       "registered at all"),
    _e("scripts/check_claim_consistency.py", "L1.61 -- two organs, one word, two measurements"),
    _e("scripts/check_protected_records.py", "a ledger may not lose records to a second writer",
       "--range", "HEAD~1", "HEAD"),
)

#: THE ORGAN ROSTER -- standing fixers, region organs and report builders. Production mode.
ORGANS: tuple[Entry, ...] = (
    # THE ONLY CLOCK A COVERAGE GAP HAS. `refresh_bars` -> `refresh_tail.py` extends charts that
    # EXIST and returns `no-cache` for one that does not, and `expand_universe.py` (which can
    # create one) is on no clock at all -- so until this entry, a missing (symbol, timeframe)
    # stayed missing until somebody ran a script by hand. Bounded per pass by the organ's own
    # cap, so it shares the hour rather than owning it.
    _e("desks/mt5/scripts/fill_bar_gaps.py", "a missing (symbol, timeframe) is fetched or "
       "carries a named venue verdict"),
    _e("desks/mt5/scripts/heal_orphaned_clocks.py", "resume clocks retired as ORPHAN"),
    _e("desks/mt5/scripts/heal_silent_demotions.py", "restore sleeves demoted with no reason"),
    _e("scripts/heal_forward_lane.py", "every certificate gathers forward evidence"),
    _e("desks/mt5/scripts/retire_uncashable_certs.py", "L1.49 -- a cert this desk cannot trade"),
    _e("desks/mt5/scripts/reap_orphaned_workers.py", "the orphan reaper, a control-plane actuator"),
    _e("scripts/reap_worktrees.py", "reap agent worktrees whose work has LANDED"),
    _e("scripts/check_worktree_reap.py", "the scheduled caller for the worktree reaper"),
    _e("scripts/check_desk_cycles.py", "watch the gates and the local cycles, and correct them"),
    _e("scripts/check_unit_health.py", "the watcher of the watchers: a failed organ restarts"),
    _e("scripts/autofix_defects.py", "the standing auto-fixer for the recurring defect classes"),
    _e("scripts/backfill_pit.py", "stamp intelligence rows with the PIT they can honestly carry"),
    _e("scripts/build_family_evidence.py", "pool each mechanism's forward panel"),
    _e("scripts/build_graveyard_priors.py", "the ONE canonical machine graveyard"),
    _e("scripts/build_scoreboard.py", "every research run into one honest scoreboard"),
    _e("scripts/build_audit_shards.py", "give the audit panel real code coverage"),
    _e("scripts/build_mt5_midnight_state.py", "the read-only snapshot the midnight lane reads"),
    _e("scripts/build_midnight_operations_report.py", "nightly conservation, SLAs, forward truth"),
    _e("scripts/convert_question_queues.py", "questions must meet a brain: queues -> cards"),
    _e("scripts/sync_research_ledger.py", "the desk's real results into the research store"),
    _e("scripts/research_allocator.py", "the adaptive exploration budget"),
    _e("scripts/collector_author.py", "the conversion bottleneck: author the collector"),
    _e("scripts/score_panel.py", "score each advisory provider by validated hit-rate"),
    _e("scripts/stageb_capacity.py", "how many forward clocks SHOULD run at once"),
    _e("scripts/compare_book_growth.py", "which book grows fastest: sleeves, replacements, union"),
    _e("scripts/run_factory_status.py", "the factory's information-advantage panel"),
    _e("scripts/run_restore_drill.py", "prove the forward evidence can actually come back"),
    _e("scripts/probe_language_moat.py", "R0594 -- is the language really the moat"),
    _e("desks/mt5/research/frontier_ceo.py", "the CEO docket: the frontier proposes, a decision "
       "is required", "--apply"),
    _e("desks/mt5/research/hour_surface.py", "WHEN the book earns, measured by UTC hour"),
    _e("desks/mt5/research/hour_prior.py", "that surface as the allocation prior the desk reads"),
    _e("desks/mt5/research/axis_ingest_all.py", "ingest every data axis, every pass"),
    _e("desks/mt5/research/empty_cluster_forcer.py", "force cells into every EMPTY alpha cluster"),
    _e("desks/mt5/research/institutional_cards.py", "mechanism cards for never-certified axes"),
    _e("desks/mt5/research/local_converter.py", "mined rows -> candidates, no seat, no network"),
    _e("desks/mt5/research/index_discovery.py", "index-driven discovery: addresses, not crawls"),
    _e("desks/mt5/research/asia_transmission.py", "the Asian production-chain transmission graph"),
    _e("desks/mt5/research/africa_interaction.py", "African state as an exogenous sensor"),
    _e("desks/mt5/research/middle_east_interaction.py", "six mechanism families, two triples"),
    _e("desks/mt5/research/south_america_interaction.py", "local state as a SENSOR, not a trade"),
    _e("desks/mt5/research/countries/kr/miners.py", "the Korea miner registry: twelve agents"),
    _e("desks/mt5/research/countries/kr/nowcast.py", "the Korean trade nowcasting factory"),
    _e("desks/mt5/research/japan/miners.py", "the Japan miner registry and its context"),
    _e("desks/mt5/research/japan/dashboard.py", "the Japan department's dashboard (section 43)"),
    _e("desks/mt5/moat/moat_lifecycle.py", "the moat grows without clogging the box"),
    _e("desks/mt5/scripts/fxblue_digest.py", "compact the FX Blue harvest into one artifact"),
    _e("desks/mt5/scripts/fxblue_mechanism_summary.py", "that corpus as MECHANISM structure"),
    # --- the organs whose only importer was an organ retired on 2026-09-23: each was reached
    # ONLY through dead code, which is the quietest way for a build to stop running.
    _e("desks/mt5/research/counterfactual_attribution.py", "what the book would have earned"),
    _e("desks/mt5/research/engine_registry.py", "every engine the desk owns, and its state"),
    _e("desks/mt5/research/event_surprise.py", "the surprise component of a scheduled event"),
    _e("desks/mt5/research/macro_state_engine.py", "the macro state the sleeves condition on"),
    _e("desks/mt5/research/research_artifacts.py", "every research artifact, and who reads it"),
    _e("desks/mt5/research/search_paradigm_census.py", "which search paradigms ran, and yielded"),
    _e("desks/mt5/research/trend_core.py", "the trend core the gate studies were built on"),
    _e("desks/mt5/research/counterexample_agent.py", "the standing counterexample hunt"),
    _e("desks/mt5/research/validate_fusion.py", "the Fusion cost audit and re-validation"),
    _e("desks/mt5/research/countries/kr/lattice.py", "the KR candidate lattice, never a product"),
    _e("desks/mt5/research/gold_hour_sweep.py", "re-earn the gold entry hours, never inherit them",
       "--apply"),
    _e("scripts/check_forward_clock.py", "the forward clock must move forward; repair it"),
    _e("scripts/daily_max.py", "the daily maximisation loop: audit, remediate, verify, escalate"),
    _e("scripts/run_allocation.py", "allocate across families, bounded by what the book carries"),
    _e("scripts/run_ict_strategy.py", "the ICT setup, audited by the tool built to doubt others"),
    _e("scripts/study_promotion_selection_bias.py", "R0574 -- does the shrink absorb the winner's "
       "curse"),
    _e("scripts/backfill_live_ledger_r.py", "the R multiple on rows the writer floored at zero",
       "--apply"),
    _e("desks/mt5/scripts/migrate_identity_venue.py", "no sleeve identity frozen on a transport"),
    _e("scripts/overnight_frontier_handoff.py", "the renewable overnight frontier's baseline",
       "snapshot"),
    _e("scripts/controller_checkpoint.py", "the shared control plane's claim and heartbeat",
       "status"),
)

ROSTERS: dict[str, tuple[Entry, ...]] = {"fences": FENCES, "organs": ORGANS}


def report_path(battery: str, base: Path | None = None) -> Path:
    return (base or DESK) / "reports" / f"BATTERY_{battery.upper()}.json"


# --------------------------------------------------------------------------- measured limits
def free_memory() -> tuple[float | None, float | None]:
    """(free MB, total MB) of PHYSICAL memory on this machine, or (None, None) UNMEASURED.

    Measured, never assumed: this desk has twice sized a floor off a machine the code was not
    running on (CLAUDE.md, 2026-09-12 and 2026-09-15), and both times the floor was wrong.
    """
    try:
        import psutil  # type: ignore[import-untyped]
    except Exception:
        return (None, None)
    try:
        vm = psutil.virtual_memory()
        return (float(vm.available) / 1e6, float(vm.total) / 1e6)
    except Exception:
        return (None, None)


def slice_s(budget_s: float) -> float:
    """Seconds one rostered organ may take: a share of the pass budget, floored and capped."""
    return max(MIN_SLICE_S, min(MAX_SLICE_S, budget_s * PER_ENTRY_SHARE))


# ------------------------------------------------------------------------------- the rotation
def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _age_s(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        return max(0.0, (datetime.now(tz=UTC) - datetime.fromisoformat(stamp)).total_seconds())
    except (TypeError, ValueError):
        return None


def run_one(entry: Entry, timeout_s: float, root: Path | None = None) -> dict[str, Any]:
    """Run one rostered organ as a subprocess. It never raises: a battery that can be taken
    down by the organ it exercises is a battery that gets removed within a week."""
    base = root or ROOT
    p = base / entry.path
    if not p.exists():
        return {"rc": None, "s": 0.0, "verdict": "MISSING",
                "tail": "the rostered path does not exist in this tree"}
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(p), *entry.argv], capture_output=True,
                           text=True, timeout=max(5.0, timeout_s), cwd=str(base))
        lines = (r.stdout or r.stderr or "").strip().splitlines()
        return {"rc": r.returncode, "s": round(time.time() - t0, 1),
                "verdict": "OK" if r.returncode == 0 else "FAILED",
                "tail": lines[-1][:220] if lines else ""}
    except subprocess.TimeoutExpired:
        return {"rc": None, "s": round(time.time() - t0, 1), "verdict": "TIMEOUT",
                "tail": f"did not finish in {timeout_s:.0f}s of this pass's budget"}
    except (OSError, ValueError) as exc:
        return {"rc": None, "s": round(time.time() - t0, 1), "verdict": "UNRUNNABLE",
                "tail": str(exc)[:220]}


def run_battery(battery: str, budget_s: float, *, root: Path | None = None,
                state_path: Path | None = None, roster: tuple[Entry, ...] | None = None,
                out: Path | None = None) -> dict[str, Any]:
    """One pass of one battery: rotate from the stored cursor until the budget is spent."""
    base = root or ROOT
    entries = roster if roster is not None else ROSTERS.get(battery, ())
    sp = state_path or STATE
    state = _read(sp)
    raw = state.get(battery)
    mine: dict[str, Any] = raw if isinstance(raw, dict) else {}
    runs: dict[str, Any] = dict(mine.get("runs") or {})
    cursor = int(mine.get("cursor") or 0) % max(1, len(entries))

    free_mb, total_mb = free_memory()
    floor_mb = (total_mb * MEM_FLOOR_SHARE) if total_mb else None
    per = slice_s(budget_s)
    t0 = time.time()
    ran: list[str] = []
    skipped: list[dict[str, str]] = []
    # THE CURSOR IS READ ONCE. Advancing it inside the loop while also indexing from it skips
    # every second organ, which is how a rotation silently exercises half a roster forever.
    start = cursor
    for i in range(len(entries)):
        remaining = budget_s - (time.time() - t0)
        if remaining < MIN_SLICE_S:
            break
        entry = entries[(start + i) % len(entries)]
        free_now, _ = free_memory()
        if floor_mb is not None and free_now is not None and free_now < floor_mb:
            skipped.append({"path": entry.path,
                            "why": f"free {free_now:.0f}MB below the derived floor "
                                   f"{floor_mb:.0f}MB ({MEM_FLOOR_SHARE:.0%} of "
                                   f"{total_mb:.0f}MB measured here)"})
            break
        res = run_one(entry, min(per, remaining), base)
        runs[entry.path] = {**res, "at": _now()}
        ran.append(entry.path)
        cursor = (start + i + 1) % len(entries)

    state[battery] = {"cursor": cursor, "runs": runs, "at": _now()}
    _atomic(sp, state)

    rows = []
    for e in entries:
        last = runs.get(e.path) or {}
        rows.append({"path": e.path, "why": e.why, "argv": list(e.argv),
                     "verdict": last.get("verdict", "NEVER_RUN"), "rc": last.get("rc"),
                     "s": last.get("s"), "at": last.get("at"), "tail": last.get("tail"),
                     "age_s": _age_s(last.get("at"))})
    never = [r["path"] for r in rows if r["verdict"] == "NEVER_RUN"]
    failing = [r["path"] for r in rows if r["verdict"] in ("FAILED", "TIMEOUT", "UNRUNNABLE",
                                                           "MISSING")]
    ages = [r["age_s"] for r in rows if isinstance(r["age_s"], float)]
    doc = {
        "battery": battery, "at": _now(), "budget_s": budget_s,
        "wall_s": round(time.time() - t0, 1),
        "rostered": len(entries), "ran": ran, "n_ran": len(ran), "skipped": skipped,
        "cursor": cursor, "slice_s": round(per, 1),
        "memory": {"free_mb": None if free_mb is None else round(free_mb),
                   "total_mb": None if total_mb is None else round(total_mb),
                   "floor_mb": None if floor_mb is None else round(floor_mb),
                   "state": "UNMEASURED" if total_mb is None else "measured"},
        "never_run": never, "n_never_run": len(never),
        "failing": failing, "n_failing": len(failing),
        "oldest_age_s": max(ages) if ages else None,
        "rotation_hours": (len(entries) / len(ran)) if ran else None,
        "rows": rows,
        "law": "UNWIRED OR IDLE IS A DEFECT (LAWS 7 / III.16): a rostered organ runs in rotation "
               "and its verdict carries an age; NEVER_RUN and `failing` are the worklist.",
    }
    _atomic(out or report_path(battery, base / "desks" / "mt5"), doc)
    return doc


def roster_table() -> str:
    return "\n".join(f"{name:8s} {e.path:60s} {e.why}"
                     for name, entries in ROSTERS.items() for e in entries)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--battery", default="fences", choices=sorted(ROSTERS),
                    help="which roster to rotate this pass")
    ap.add_argument("--budget-s", type=float, default=180.0,
                    help="seconds this pass may spend; each organ gets a floored share of it")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--roster", action="store_true", help="print the roster and exit")
    a = ap.parse_args(argv)
    if a.roster:
        print(roster_table())
        return 0
    doc = run_battery(a.battery, a.budget_s)
    rot = doc["rotation_hours"]
    rot_s = "UNMEASURED" if rot is None else f"{rot:.0f}h"
    print(f"battery {doc['battery']}: ran {doc['n_ran']}/{doc['rostered']} in "
          f"{doc['wall_s']}s (slice {doc['slice_s']}s), {doc['n_failing']} failing, "
          f"{doc['n_never_run']} never run, full rotation {rot_s}")
    for path in doc["failing"][:8]:
        row = next(r for r in doc["rows"] if r["path"] == path)
        print(f"   {row['verdict']:10s} {path}: {(row['tail'] or '')[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
