"""CADENCE ENGINE -- review/generation frequency as CODE, stage-aware, zero human scheduling.

Principal directive 2026-07-17: cadences must adjust to the max-ROI schedule automatically.
Before this, the weekly panel depended on the AI brain remembering to fire it -- cadence by
LLM memory is a reliability hole. This script runs inside the daily cycle and deterministically
fires what is due, per stage (data/stage_state.json):

  S0 (pre-live, current):  panel every 7d (mission rotation) | tier1 every 14d (was documented as 28d while the constant read 14 -- that contradiction produced a 34-day error in a live briefing) |
                           generation DATA-TRIGGERED (a 40d clock maturing or a new family
                           landing flags a scoped generate run for the brain)
  S1/S2 (live, flipped by the live-connector deployment): all of the above PLUS generation
                           weekly -- live trading mints fresh data (fills/slippage/tape)
                           every week, so weekly IS data-triggered post-Gate-0.

State in data/cadence_state.json (last-run dates). The brain TRIAGES panel output; it no
longer schedules panels. Scoped generate runs + monthly prompt self-improvement stay
brain-executed (judgment tasks) -- this engine flags them in docs/research/cadence_duties.md.
CADENCE FLOORS below enforce the never-sleepier invariant; violations are paged.

    python scripts/run_cadence.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_STATE = Path("data/cadence_state.json")
_STAGE = Path("data/stage_state.json")
_HEALTH = Path("web/health.json")
_DUE_NOTE = Path("docs/research/cadence_duties.md")
_VIOLATION = Path("data/cadence_violation.json")
_PANEL_EVERY_D = 3
_TIER1_EVERY_D = 14
_PROMPT_REVIEW_D = 28
_CLOCK_MATURITY_D = 40

# CADENCE FLOORS (principal invariant 2026-07-17): the system may never get SLEEPIER where
# sleep can kill it. Each artifact must be at most this many HOURS old; a violation is paged
# (run_alerts reads data/cadence_violation.json). Stage transitions may only ADD floors or
# TIGHTEN them (S1/S2 extras below) -- loosening or deleting any floor is a Tier-3-class
# action: principal sign-off only, never automation, never the self-improvement engine.
_FLOORS_S0: dict[str, float] = {
    "data/deadman_heartbeat": 0.2,               # ruin rail alive (1-min loop + slack)
    "data/cashcarry_exec_heartbeat": 0.5,        # executor alive
    "data/.last_alerts.json": 1.0,               # pager tick running
    "web/venue_equity.json": 1.0,                # venue-truth feed fresh
    "docs/research/micro_audit_inbox.md": 48.0,  # daily cold eyes actually ran
}
_FLOORS_S1_EXTRA: dict[str, float] = {           # live adds floors; never removes any
    "data/canary_state.json": 12.0,              # 6h canary round-trip (post-connector)
}
# state-tracked floors (days): review cycles may never stretch past these
_STATE_FLOORS_D = {"last_panel": 4.0, "last_tier1": 16.0, "last_prompt_review": 35.0,
                   "last_prospector": 35.0, "last_blind_rediscovery": 100.0,
                   "last_lit_deepdive": 35.0, "last_decision_scoring": 35.0,
                   "last_memory_consolidation": 100.0}


def _load(p: Path, default: dict) -> dict:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def _days_since(state: dict, key: str) -> float:
    try:
        then = datetime.fromisoformat(str(state[key]))
        return (datetime.now(tz=UTC) - then).total_seconds() / 86400.0
    except (KeyError, ValueError, TypeError):
        return 1e9                                    # never ran -> due


def _run_panel(mission: str | None) -> bool:
    """Regenerate the dossier, then fire the panel (optionally with a forced mission)."""
    env = None
    if mission:
        import os
        env = {**os.environ, "PANEL_MISSION": mission}
    r1 = subprocess.run([sys.executable, "scripts/generate_external_review_doc.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    if r1.returncode != 0:
        print(f"cadence: dossier regen failed rc={r1.returncode} -- panel skipped")
        return False
    # PRODUCTION, NOT EXIT CODE (2026-07-26). This returned rc==0, and the caller stamps
    # last_panel on True -- so a panel that wrote NOTHING still marked the duty done. That is
    # how cadence_state came to claim a panel ran 2026-07-25 while panel_verdicts.jsonl had not
    # been appended since 2026-07-21 (126h, cadence 96h). The mechanism is funding: the
    # pre-flight check sizes a run at ~$0.05/seat and the account holds $3.40, so the run starts,
    # exhausts mid-flight, seats return HTTP 402, the sanitizer drops the partial roster, and the
    # process still exits clean. An exit code proves a process ended, never that it PRODUCED --
    # the same state-touched-but-nothing-produced class check_production exists to catch. A run
    # that appended no verdict now leaves the duty OWED (this only ever makes cadence stricter;
    # no floor is touched).
    _verdicts = Path("data/panel_verdicts.jsonl")   # module runs cwd=repo root, as _STATE does
    try:
        _before = _verdicts.stat().st_size
    except OSError:
        _before = -1
    r2 = subprocess.run([sys.executable, "scripts/run_external_panel.py"],
                        capture_output=True, text=True, timeout=720, check=False, env=env)
    tail = (r2.stdout or r2.stderr or "").strip().splitlines()[-1:] or [""]
    try:
        _after = _verdicts.stat().st_size
    except OSError:
        _after = -1
    _produced = _after > _before
    _grew = f"+{_after - _before}b" if _produced else "+0b (NOT PRODUCED)"
    print(f"cadence: panel[{mission or 'rotation'}] rc={r2.returncode} "
          f"verdicts {_grew} | {tail[0][:120]}")
    if r2.returncode == 0 and not _produced:
        print("cadence: panel exited clean but appended NO verdict -- duty stays OWED "
              "(check OpenRouter funding: a half-funded roster 402s mid-run and emits nothing)")
    return r2.returncode == 0 and _produced


def _assert_floors(state: dict, stage: str) -> None:
    """Never-sleepier invariant: page (via run_alerts pickup) if any floor is stale."""
    import time
    floors = dict(_FLOORS_S0)
    if stage in ("S1", "S2"):
        floors.update(_FLOORS_S1_EXTRA)              # monotone by construction: add-only
    bad: list[str] = []
    now_s = time.time()
    for path, max_h in floors.items():
        p = Path(path)
        if not p.exists():
            if stage == "S0" and path in _FLOORS_S1_EXTRA:
                continue                             # live-only artifact, not yet due
            bad.append(f"{path}: MISSING (floor {max_h}h)")
        elif (age := (now_s - p.stat().st_mtime) / 3600.0) > max_h:
            bad.append(f"{path}: {age:.1f}h old (floor {max_h}h)")
    for key, max_d in _STATE_FLOORS_D.items():
        if (d := _days_since(state, key)) > max_d and d < 1e8:
            bad.append(f"{key}: {d:.1f}d since last run (floor {max_d}d)")
    if bad:
        _VIOLATION.write_text(json.dumps(
            {"ts": datetime.now(tz=UTC).isoformat(), "violations": bad}), "utf-8")
        print(f"cadence: FLOOR VIOLATION x{len(bad)} -> {_VIOLATION} (pager will fire)")
    elif _VIOLATION.exists():
        _VIOLATION.unlink()                          # self-clearing when floors recover
        print("cadence: floor violation cleared")


_ROOT_DIR = Path(__file__).resolve().parent.parent
_FREEZE_STATUS = Path("data/freeze_exit_status.json")

#: criterion -> (artifact it reads, the module/script that WRITES that artifact).
#: The second element is the whole point. A deployment criterion reading a file with no writer is
#: not a strict gate, it is an unsatisfiable one, and the two are indistinguishable from the
#: outside: both simply read False forever. Naming the writer makes the claim checkable, and
#: check_freeze_exit_sources() below turns it into a test.
_FREEZE_SOURCES: dict[str, tuple[str, str]] = {
    "gate0": ("data/gate0_complete", "scripts/max_audit.py"),
    "fills_4wk": ("data/moat/execution_tape/cashcarry_trades.jsonl",
                  "libs/execution/execution_tape.py"),
    "cost_model": ("data/cost_model.json", "scripts/run_cost_model.py"),
    "calib_10": ("data/forecast_log.json", "libs/self_improvement/forecast_calibration.py"),
    "no_criticals": ("data/DEADMAN_FIRED", "scripts/run_deadman_switch.py"),
}


def check_freeze_exit_sources() -> list[str]:
    """Every freeze-exit criterion must read an artifact something in this repo WRITES.

    THE GENERALISED FORM of the 2026-07-30 defect. Three of five criteria read invented filenames
    (fills.csv, weekly_cost_summary.json, calibration.csv) that no code anywhere produces. Each
    read False forever, which is indistinguishable from "the desk has not earned it yet" -- so the
    gate looked strict while being unsatisfiable, and nobody could tell the difference by looking
    at the output. This checks the WRITER exists, not the artifact: pre-launch the artifacts are
    legitimately absent, but their writer must be real today.
    """
    problems = []
    for crit, (artifact, writer) in _FREEZE_SOURCES.items():
        if not (_ROOT_DIR / writer).exists():
            problems.append(f"{crit}: writer {writer} does not exist -- {artifact} can never "
                            "appear, so this criterion is unsatisfiable, not strict")
    return problems


def _freeze_exit_met() -> tuple[bool, str]:
    """The 5 lockdown exit criteria. All must hold. Returns (met, human-status).

    REWRITTEN 2026-07-30. THREE of the five criteria read files that NOTHING IN THIS REPO WRITES,
    so they could never become True no matter how well the desk performed:

      fills_4wk   read `data/fills.csv`   -- no writer anywhere. Fills go to
                  data/cashcarry_trades.json and data/moat/execution_tape/cashcarry_trades.jsonl.
      cost_model  read `data/weekly_cost_summary.json` -- no writer. run_cost_model.py writes
                  data/cost_model.json.
      calib_10    read `data/calibration.csv` -- no writer. Forecast outcomes live in
                  data/forecast_log.json via libs/self_improvement/forecast_calibration.py.

    And fills_4wk was additionally INVERTED: it compared `now - file mtime > 28 days`, which reads
    "this feed has been DEAD for a month". A healthy, actively-appended fill feed has mtime ~= now
    and failed forever; only an abandoned one could pass. Satisfying the gate honestly would have
    required creating a fills file and then abandoning it for four weeks.

    Consequence, and it is the reason this is a launch blocker rather than a tidy-up: the desk's
    whole research apparatus funnels into a deployment gate that was not merely unmet but
    UNSATISFIABLE, and the only place that fact was stated was a status string nobody read. The
    desk could have compiled a flawless track record and the freeze would never have lifted.

    Every criterion now reads the artifact that actually exists, and `days` is measured from the
    oldest ROW TIMESTAMP (execution_tape.coverage), never from a file's mtime.
    """
    checks: dict[str, bool] = {}
    checks["gate0"] = Path("data/gate0_complete").exists()

    # >=4 weeks of live fills, measured on row timestamps in the tape that Gate 0 is scored on.
    try:
        from libs.execution.execution_tape import coverage
        cov = coverage()
        checks["fills_4wk"] = float(cov.get("days", 0.0)) >= 28.0 and int(cov.get("n", 0)) > 50
    except (ImportError, OSError, ValueError, TypeError):
        checks["fills_4wk"] = False

    checks["cost_model"] = Path("data/cost_model.json").exists()

    try:
        from libs.self_improvement.forecast_calibration import report
        checks["calib_10"] = int(report().get("n_resolved", 0)) >= 10
    except (ImportError, OSError, ValueError, TypeError):
        checks["calib_10"] = False

    checks["no_criticals"] = not Path("data/DEADMAN_FIRED").exists()
    met = all(checks.values())
    return met, ", ".join(f"{k}={v}" for k, v in checks.items())


def main() -> None:
    now = datetime.now(tz=UTC)
    state = _load(_STATE, {})
    stage = str(_load(_STAGE, {"stage": "S0"}).get("stage", "S0"))
    fired: list[str] = []

    if _days_since(state, "last_tier1") >= _TIER1_EVERY_D:
        if _run_panel("tier1"):
            state["last_tier1"] = now.isoformat()
            state["last_panel"] = now.isoformat()     # tier1 counts as this week's panel
            fired.append("tier1")
    elif _days_since(state, "last_panel") >= _PANEL_EVERY_D and _run_panel(None):
        state["last_panel"] = now.isoformat()
        fired.append("panel")

    # generation triggers -> flagged for the brain (scoped runs are a judgment task)
    due: list[str] = []
    health = _load(_HEALTH, {})
    for ds in health.get("datasets", []):
        name, days = str(ds.get("name")), int(ds.get("days") or 0)
        if days >= _CLOCK_MATURITY_D and not state.get(f"gen_done_{name}"):
            due.append(f"{name}: clock matured ({days}d) -- scoped generate run owed, PLUS a "
                       "graveyard re-mine pass: any killed entry whose kill-reason this new "
                       "data invalidates gets a fresh pre-registration (no silent revivals)")
    if Path("data/fred_macro.json").exists() and not state.get("gen_done_fred_macro_family"):
        due.append("fred_macro family: deep history available -- scoped generate run owed")
    if stage in ("S1", "S2") and _days_since(state, "last_live_generate") >= 7:
        due.append("LIVE (S1+): weekly generation vs fresh fills/slippage/tape is due")
    # Digging cadence tracks UNMINED INVENTORY (principal 2026-07-18): 14d while the source
    # backlog is being mined; the brain sets digging_saturated=true when every coverage
    # family has >=2 sessions AND 2 consecutive sessions produced zero cards -> relax to 28d.
    dig_every = 14 if state.get("digging_saturated") else 7
    if _days_since(state, "last_prospector") >= dig_every:
        due.append(
            f"PROSPECTOR (every {dig_every}d): execute docs/research/PROSPECTOR_SPEC.md with "
            "real web search -- UNCAPPED/exhaustive (dedicated quant-prospector.timer, "
            "biweekly), provenance-graded mechanism cards -> EV gate "
            "+ pre-registration; update docs/research/prospector_watchlist.md; mark done: "
            "last_prospector in data/cadence_state.json. NEVER at the expense of the lockdown "
            "priorities (recorder/connector) -- they own the cycle first.")
    if _days_since(state, "last_data_axis_dig") >= 7:                     # WEEKLY (never relaxed)
        due.append(
            "DATA-AXIS / FREE-DATA-ALTERNATIVE DIG (WEEKLY/7d, UNCAPPED budget -- operator accepts "
            "token cost; dig ALL 6 categories to EXHAUSTION every run, no rotating "
            "subset): execute the FULL "
            "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md -- 6 source categories (exchange-native "
            "dumps, on-chain reconstruction, non-English/regional venues, community lakes, "
            "alt/sentiment, vendor-replacement); language-blind; VERIFY-DON'T-TRUST vs ground "
            "truth; DATA GENEALOGY on every adopted set; automatic replacement monitoring; "
            "source-failure intelligence; query evolution (>=25% exploration quota); cross-source "
            "synthesis; temporal rediscovery; discovery-ROI + maintainer tracking; SEARCH-SPACE "
            "EXPANSION quota. Catalog -> data/data_universe_map.json "
            "(source+grade+lineage+failure-modes+yield); verified axes -> EV gate "
            "(new_orthogonal_data). Mark done: last_data_axis_dig. Lockdown priorities own the "
            "cycle first.")
    if _days_since(state, "last_lit_deepdive") >= dig_every:
        due.append(
            f"LITERATURE DEEP-MINER (every {dig_every}d, UNCAPPED/exhaustive, dedicated "
            "quant-litminer.timer biweekly): execute "
            "docs/research/LITERATURE_SPEC.md -- inbox triage to MECHANISMS (never "
            "summaries), 2-level citation-chain digs, replication scans, coverage rotation; "
            "cards -> EV gate + pre-registration; mark done: last_lit_deepdive. Lockdown "
            "priorities own the cycle first.")
    if _days_since(state, "last_blind_rediscovery") >= 90:
        due.append(
            "BLIND REDISCOVERY (quarterly): NO external search -- per the companion section "
            "of PROSPECTOR_SPEC.md, invent up to 5 unpublished mechanisms from internal "
            "artifacts only; pre-register via the gauntlet; log for the 12-month literature "
            "comparison; mark done: last_blind_rediscovery.")
    if _days_since(state, "last_decision_scoring") >= 28:
        due.append(
            "DECISION OUTCOME SCORING (monthly -- closes the self-improvement loop): "
            "for every ledger decision past its review horizon (>=30d old) not yet "
            "scored, judge predicted-vs-ACTUAL: did expected_benefit materialize? was "
            "success_metric met? did reversal_condition fire? Append to "
            "data/decision_outcomes.jsonl (id, predicted, actual, hit/miss, lesson), "
            "then update EV-gate priors from the hit-rate -- the desk must learn "
            "whether its OWN predictions are any good. Mark done: last_decision_scoring.")
    if _days_since(state, "last_memory_consolidation") >= 90:
        due.append(
            "MEMORY CONSOLIDATION (quarterly -- anti-bloat for a lifetime system): "
            "consolidate ops/memory + knowledge base -- merge superseded/duplicate "
            "addenda, archive resolved items to a dated file, compress recurring "
            "lessons into principles, fix stale facts, keep MEMORY.md lean. Memory "
            "must get SIMPLER as it learns, not only longer. NEVER delete the ledger "
            "or graveyard (append-only truth) -- consolidate the NARRATIVE layer only. "
            "Mark done: last_memory_consolidation.")
    if _days_since(state, "last_prompt_review") >= _PROMPT_REVIEW_D:
        due.append(
            "PROMPT SELF-IMPROVEMENT (monthly): score every mission prompt + auditor against "
            "verified-hit evidence (panel_rulings.md, inboxes, micro_audit_log.jsonl). Rewrite "
            "ONLY the worst performer; ledger the revision with a pre-registered success "
            "metric (verified-finding rate over its next 2 runs) and an auto-revert condition. "
            "Prompts live in git -- every revision is diffable and revertible. Mark done: set "
            "last_prompt_review in data/cadence_state.json.")
    if due:
        _DUE_NOTE.parent.mkdir(parents=True, exist_ok=True)
        _DUE_NOTE.write_text(
            f"# Generation due -- {now.isoformat()[:16]}Z (stage {stage})\n\n"
            "The cadence engine flags these; the brain executes SCOPED generate runs "
            "(graveyard-excluded, pre-registration mandatory) and then marks them done by "
            "setting gen_done_<name> / last_live_generate in data/cadence_state.json.\n\n"
            + "\n".join(f"- {d}" for d in due) + "\n", "utf-8")
        print(f"cadence: {len(due)} generation trigger(s) flagged -> {_DUE_NOTE}")

    # FREEZE-EXIT (deterministic; principal 2026-07-18): evaluate the 5 lockdown exit
    # criteria every cycle so the freeze lifts on EVIDENCE, not on memory. Pre-Gate-0
    # these read cleanly as not-met; the moment live data satisfies them, the manifest
    # is flagged for activation. No human or brain memory is the trigger -- the code is.
    if stage == "S0" and not state.get("post_gate0_activated"):
        met, why = _freeze_exit_met()
        # ALWAYS write the status, and write it where something READS it. Previously this was set
        # only in the else-branch, into a state key with ONE writer and ZERO readers -- no fence,
        # no page, no dashboard. That is how three unsatisfiable criteria sat in the deployment
        # gate unnoticed: the single place the failure was stated was a string nobody opened.
        state["freeze_exit_status"] = why
        _FREEZE_STATUS.parent.mkdir(parents=True, exist_ok=True)
        _FREEZE_STATUS.write_text(json.dumps({
            "generated": datetime.now(tz=UTC).isoformat(),
            "met": met, "why": why,
            "criteria_sources": _FREEZE_SOURCES,
            "note": "Every criterion must read an artifact something in this repo WRITES. "
                    "check_freeze_exit_sources() fences that; three criteria failed it on "
                    "2026-07-30 (fills.csv, weekly_cost_summary.json, calibration.csv).",
        }, indent=2), "utf-8")
        if met:
            due.append("FREEZE-EXIT CRITERIA MET -- activate docs/POST_GATE0_MANIFEST.md "
                       "top to bottom; flip stage_state to S1; set post_gate0_activated. "
                       "Nothing deferred may be skipped.")
    _assert_floors(state, stage)
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")
    print(f"cadence[{stage}]: fired={fired or 'nothing due'} | "
          f"panel due in {max(0.0, _PANEL_EVERY_D - _days_since(state, 'last_panel')):.1f}d | "
          f"tier1 due in {max(0.0, _TIER1_EVERY_D - _days_since(state, 'last_tier1')):.1f}d")


if __name__ == "__main__":
    main()
