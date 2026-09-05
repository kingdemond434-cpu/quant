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
    # The one forward verdict all three engines call, and the portfolio-contribution
    # multiplier the gateway sizes with. Both are NEW modules, which is exactly the class
    # the healer used to skip: absent on the box scored the same as an unreachable box.
    "desks/mt5/research/forward_verdict.py",
    "desks/mt5/mt5desk/portfolio_weight.py",
    "desks/mt5/mt5desk/sizing.py",
    "desks/mt5/research/shadow_admission.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/side_channels/promoter_fixed.py",
    "desks/mt5/research/backfill_coverage.py",
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/scripts/warm_gauntlet_cache.py",
    "desks/mt5/scripts/stall_watch.ps1",
    "libs/research/bar_span.py",
    # THE ALPHA SEARCH'S IMPORT CLOSURE (2026-09-05). `alpha_evolution` runs on the box every
    # hour and now imports the modules that decide what it can even PROPOSE: the grammar (whose
    # production screen is structure + type + UNITS), the typed samplers, the portfolio-aware
    # fitness and the nine-population registry. A stale grammar on the box is a box constructing
    # arithmetic this tree forbids, with every fence reporting all-match.
    "desks/mt5/research/alpha_evolution.py",
    "libs/research/alpha_grammar.py",
    "libs/research/generators.py",
    "libs/research/alpha_fitness.py",
    "libs/research/search_populations.py",
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
    # The recertification audit: it decides whether a STANDING certificate still holds,
    # and it was unwatched. Its 2026-08-27 run failed 15 of 17 on deflated_sharpe against
    # the inflated hurdle, so a stale copy here silently re-condemns the book.
    "desks/mt5/scripts/recertify_canon.py",
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
    # Every step the daily chain imports, as tests/ops/test_desk_module_drift_covers_the_daily_chain
    # enforces: a step added to STEPS without a line here decays on the box unwatched.
    "desks/mt5/research/conservation_ledger.py",
    "desks/mt5/research/research_bandit.py",
    "desks/mt5/research/state_admission_run.py",
    "desks/mt5/research/decay_monitor.py",
    "desks/mt5/research/forward_reconcile.py",
    "desks/mt5/research/portfolio_evidence.py",
    "desks/mt5/research/shadow_forward.py",
    # Imported by edge_search while rebuilding `discovered` runtime inputs. Its absence blocked
    # seven live EURCHF forward clocks even though family_inputs and shadow_forward both matched.
    "desks/mt5/research/carry_state.py",
    # The shared runtime-input reconstruction. Both the gauntlet and the forward engine
    # depend on it; a stale copy on the box means 344 near-certificates silently stop
    # accruing the forward evidence that is their only route to a certificate.
    "desks/mt5/mt5desk/family_inputs.py",
    # THE RECORDER. Only the desk box can read the terminal, so it is the sole producer of
    # the contract/swap terms every carry cell is judged on -- and it was unwatched. Its
    # `point` field (the UNIT that makes a POINTS-mode swap convertible to money) was
    # added here and never reached the box, so a fresh recording on 2026-08-29 still wrote
    # rows without it and `swap_money_per_lot` correctly refused every one. 72 carry
    # candidates could not accrue forward evidence because a file nothing named was stale.
    "desks/mt5/mt5desk/tape.py",
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
    # THE BOX'S OWN SYNC AND THE MONEY PATH IT RUNS (2026-09-05). sync_shadow_to_git.ps1 was
    # fixed on 2026-09-03 and the fix was inert for two days: the script that fetches code on the
    # box is the script that was broken, so the box could never fetch its own repair (no
    # "mt5 shadow state sync" commit has reached the remote since 2026-08-26). This channel is
    # the one that still works -- ssh from the VPS -- so it carries the sync script and every
    # module the gateway, the promoter and the forward clocks import. The scalp executor and the
    # netting ledger are here because a promotion that reaches `sleeves.json` on the box with an
    # executor the box does not have is a certified sleeve that can never trade.
    "desks/mt5/scripts/sync_shadow_to_git.ps1",
    "desks/mt5/scripts/sync_to_vps.ps1",
    "desks/mt5/mt5desk/gateway.py",
    # THE DECISIONS THE GATEWAY SENDS (2026-09-05 split). gateway.py imports
    # `mt5desk.decision_core` at module scope, so a box without this file cannot import the
    # gateway at all -- the hourly pass dies at import and the desk stops trading with no
    # signal that a module went missing. It ships with the gateway or the gateway does not run.
    "desks/mt5/mt5desk/decision_core.py",
    # WHICH CERTIFIED FAMILIES THE GATEWAY CAN TRADE. `research/promoter.py` imports this to
    # decide whether a PROMOTION CANDIDATE gets a LIVE row or a named `executor_gap`, so a box
    # that has the new promoter and not this file raises ImportError mid-promotion and the whole
    # pass dies. Measured 2026-09-05: the healer re-shipped promoter.py the minute the merge
    # landed and this file was not on the list -- shipping a caller without its callee.
    "desks/mt5/mt5desk/executables.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py",
    "desks/mt5/mt5desk/scalp_exec.py",
    "desks/mt5/mt5desk/netting.py",
    "desks/mt5/mt5desk/execution_policy.py",
    "desks/mt5/mt5desk/execution_registry.py",
    "desks/mt5/mt5desk/fill_surface.py",
    # THE STATE VECTOR THE BOX BUILDS AND THE ALLOCATOR SIZES FROM (2026-09-05). `hourly_cycle`
    # is watched and IMPORTS state_vector_build, which was not -- the caller was pinned to HEAD
    # while the callee could sit on the box's own stale branch, the defect at the head of this
    # list. It now also reads the world causal graph's hints and weights every input by
    # libs.research.information_decay, so the module, the graph organ and the two libs must move
    # together: a box with the new consumer and an old decay registry weights a weekly COT read
    # as if it were an hourly bar.
    "desks/mt5/research/state_vector_build.py",
    "desks/mt5/research/world_causal_graph.py",
    "libs/regime/state_vector.py",
    "libs/research/causal_graph.py",
    "libs/research/information_decay.py",
    # THE FEATURE WAREHOUSE and its lifecycle. feature_roi runs on the box's daily chain and
    # writes a status onto every sidecar that decides whether an organ may spend compute on that
    # feature; a box with an old lifecycle table spends effort the ledger already withdrew.
    "desks/mt5/research/feature_roi.py",
    "libs/data/feature_store.py",
    "libs/data/feature_lifecycle.py",
    "libs/data/pit_certificate.py",
    # THE COUNTERFACTUAL WORLD and its import closure. The organ is on the daily chain and both
    # libs modules are authored here and executed there; a module missing from this list is one
    # that can silently revert to the box's own branch.
    "desks/mt5/research/counterfactual_replay.py",
    "libs/research/counterfactual_world.py",
    "libs/research/decision_dataset.py",
    "libs/research/decision_ledger.py",
    # The execution digital twin runs on the box because only the box has the three ledgers.
    "desks/mt5/research/execution_twin.py",
    "libs/execution/digital_twin.py",
    "desks/mt5/mt5desk/risk_units.py",
    "desks/mt5/mt5desk/position_manager.py",
    "desks/mt5/mt5desk/provenance.py",
    "desks/mt5/mt5desk/independence.py",
    "desks/mt5/mt5desk/multiplicity.py",
    "desks/mt5/mt5desk/config.py",
    "desks/mt5/research/run_gateway_loop.py",
    "desks/mt5/mt5desk/release_identity.py",
    "desks/mt5/scripts/smoke_release.py",
    "desks/mt5/research/shadow_cycle.py",
    "desks/mt5/research/external_shadow.py",
    "desks/mt5/research/scalp_family_expansion.py",
    # THE SCALP LANE'S GAUNTLET (2026-09-05): imported by the daily chain, its report read by
    # the canon writer; a stale copy on the box is a lane back to forward-clock-only certificates
    # while the fence reports all-match.
    "desks/mt5/scripts/scalp_gauntlet.py",
    "desks/mt5/mt5desk/scalp_families.py",
    "desks/mt5/research/scalp_reverse_engineering.py",
    "desks/mt5/research/pf_allocator.py",
    "desks/mt5/research/heat_policy.py",
    "desks/mt5/research/allocation.py",
    "desks/mt5/research/live_manifest.py",
    "desks/mt5/research/run_hunt12.py",
    "desks/mt5/research/run_hunt16.py",
    "desks/mt5/research/qquant_gates.py",
    "desks/mt5/research/universal_gate.py",
    "libs/portfolio/robust_elog.py",
    "libs/portfolio/allocator_proof.py",
    "libs/portfolio/posterior_growth.py",
    "libs/portfolio/multiperiod_worlds.py",
    "libs/portfolio/rails.py",
    "libs/portfolio/capital_modifiers.py",
    "libs/portfolio/kelly_surface.py",
    "libs/portfolio/challengers.py",
    "libs/portfolio/aggression.py",
    "libs/risk/fx_factors.py",
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


#: `_remote_hash` returns this when the box simply does not have the file. It is NOT the same
#: answer as None ("I could not ask"), and conflating the two is what let a brand-new module sit
#: unshipped while the healer reported a clean run -- see ABSENT_IS_DRIFT below.
ABSENT = "__absent__"


def _remote_hash(rel: str) -> str | None:
    """Hash of the box's copy, ABSENT if it has none, None if the box could not be asked.

    ABSENT_IS_DRIFT. This used to collapse "no such file" into None along with every ssh failure,
    and `main` skipped both as unreachable. That is backwards for the case that matters most: a
    NEW module is precisely the one the box has never had, so absence was treated as a reason not
    to ship the very file most in need of shipping. It cost 34 live forward clocks -- every sleeve
    in `shadow_state.json` went BLOCKED_SLEEVE_ERROR with `ModuleNotFoundError: No module named
    'mt5desk.family_inputs'` while this check printed a clean run, because the module was on the
    watchlist, matched HEAD, and was absent on the box.

    A missing file and an unreachable box need opposite responses -- ship, versus report and wait
    -- so they must not share a return value.
    """
    rc, out = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                    f"cd C:\\opt\\quant && git hash-object {rel}"])
    text = (out or "").replace("\r", "").strip()
    if rc != 0:
        # Distinguish "git says no such file" from "the box did not answer". Only the former is
        # safe to treat as absence; a timeout that read as ABSENT would ship on every network
        # blip, and worse, would report success for a box that never received anything.
        low = text.lower()
        if "could not open" in low or "no such file" in low or "does not exist" in low:
            return ABSENT
        return None
    line = text.splitlines()
    return line[-1].strip() if line else None


def main() -> int:
    now = datetime.now(tz=UTC)
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "drifted": [], "healed": [], "dirty_skipped": [], "unreachable": [],
                    "absent_on_box": []}

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
        # Absence and drift both end in the same scp; they differ only in what gets reported, and
        # absence is the louder of the two because it means the box has NEVER run this code.
        if remote == ABSENT:
            report["absent_on_box"].append(rel)
            print(f"  ABSENT {rel}: the box has never had this file -- shipping it now")
        else:
            report["drifted"].append(rel)
        rc, _ = _run(["scp", "-o", "ConnectTimeout=45", "-q",
                      str(ROOT / rel), f"{REMOTE}:C:/opt/quant/{rel}"], timeout=180)
        after = _remote_hash(rel) if rc == 0 else None
        if after == local:
            report["healed"].append(rel)
            had = "NOTHING" if remote == ABSENT else remote[:8]
            print(f"  RE-SHIPPED {rel}: box had {had}, now {after[:8]} (matches HEAD)")
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
