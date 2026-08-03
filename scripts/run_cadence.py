"""CADENCE ENGINE -- review/generation frequency as CODE, stage-aware, zero human scheduling.

Principal directive 2026-07-17: cadences must adjust to the max-ROI schedule automatically.
Before this, the weekly panel depended on the AI brain remembering to fire it -- cadence by
LLM memory is a reliability hole. This script runs inside the daily cycle and deterministically
fires what is due, per stage (data/stage_state.json):

  S0 (pre-live, current):  panel every 7d (mission rotation) | tier1 every 28d |
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

import contextlib
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
_MODEL_UPGRADE_D = 30            # monthly, matching the roster-governance cadence
_META_RESEARCH_D = 1             # CIO review: mechanical, seconds, no LLM -- every cycle
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
                   "last_model_upgrade": 45.0, "last_meta_research": 3.0,
                   "last_fill_quality": 10.0,
                   # Both are DAILY organs with a 1.0d gate; the floor is the outer bound past
                   # which a skipped duty stops being a quiet cycle and becomes a defect.
                   "last_breadth_expansion": 3.0, "last_hypothesis_generation": 3.0,
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


_FUNDING_STATE = Path("data/panel_funding_state.json")


def _funding_restored() -> bool:
    """True when the panel has been funded since the last flagship sweep ran.

    A 30-day clock is the right cadence for "has a better model shipped?" -- catalogs move
    slowly. It is the WRONG cadence for "the desk just got paid". Without this, credits landing
    on a Friday could be followed by up to a month of running the previous roster on the new
    money, and the whole point of funding the panel is the panel it funds.

    The flag is latched by run_external_panel on the unfunded->funded edge and cleared here only
    after a sweep actually produced, so a cadence run that skipped the upgrade leaves the debt
    standing rather than consuming it.
    """
    try:
        return bool(json.loads(_FUNDING_STATE.read_text("utf-8")).get("upgrade_owed"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


def _clear_funding_debt() -> None:
    """Clear the latch -- ONLY after a sweep genuinely evaluated the catalog."""
    with contextlib.suppress(OSError, json.JSONDecodeError, TypeError, ValueError):
        d = json.loads(_FUNDING_STATE.read_text("utf-8"))
        d["upgrade_owed"] = False
        d["upgrade_ran"] = datetime.now(tz=UTC).isoformat()
        _FUNDING_STATE.write_text(json.dumps(d, indent=1), "utf-8")


def _run_model_upgrade() -> bool:
    """Monthly: roll back regressed promotions, then auto-upgrade both model surfaces.

    ROLLBACK RUNS FIRST AND UNCONDITIONALLY. It costs nothing (it reads blank telemetry, makes
    no API call), and a seat that regressed must be healed before we consider adding another
    change on top of it.

    PRODUCTION, NOT EXIT CODE -- the same lesson _run_panel records above. Both engines exit 0
    when the catalog is unreachable or the balance is too low to run a gauntlet, so an exit code
    would stamp the duty done for a check that never actually looked at anything. The honest
    signal is a FRESH `checked` timestamp in the engine's own state file: only a run that
    genuinely evaluated the catalog writes one, so a skipped run correctly leaves the duty OWED.
    """
    subprocess.run([sys.executable, "scripts/model_upgrade.py", "--rollback", "--apply"],
                   capture_output=True, text=True, timeout=300, check=False)
    produced = 0
    for script, state_file in (("scripts/model_upgrade.py", "data/model_upgrade.json"),
                               ("scripts/brain_model_upgrade.py",
                                "data/brain_model_upgrade.json")):
        r = subprocess.run([sys.executable, script, "--apply"],
                           capture_output=True, text=True, timeout=1800, check=False)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        fresh = False
        try:
            checked = json.loads(Path(state_file).read_text("utf-8")).get("checked")
            fresh = bool(checked) and _days_since({"c": checked}, "c") < 1.0
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            fresh = False
        produced += int(fresh)
        print(f"cadence: {Path(script).stem} rc={r.returncode} "
              f"{'evaluated' if fresh else 'DID NOT EVALUATE'} | {tail[0][:110]}")
    return produced == 2


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


def _freeze_exit_met() -> tuple[bool, str]:
    """The 5 lockdown exit criteria. All must hold. Returns (met, human-status)."""
    import time
    checks = {}
    checks["gate0"] = Path("data/gate0_complete").exists()
    fills = Path("data/fills.csv")
    checks["fills_4wk"] = (fills.exists()
                           and time.time() - fills.stat().st_mtime < 1e9
                           and sum(1 for _ in fills.open()) > 50
                           and (time.time() - _oldest_line_age(fills)) > 28 * 86400)
    checks["cost_model"] = Path("data/weekly_cost_summary.json").exists()
    try:
        calib = Path("data/calibration.csv")
        n = sum(1 for ln in calib.open() if "resolved" in ln.lower()) if calib.exists() else 0
        checks["calib_10"] = n >= 10
    except OSError:
        checks["calib_10"] = False
    checks["no_criticals"] = not Path("data/DEADMAN_FIRED").exists()
    met = all(checks.values())
    return met, ", ".join(f"{k}={v}" for k, v in checks.items())


def _oldest_line_age(p: Path) -> float:
    """Best-effort mtime proxy for oldest fill; refined when fills.csv exists."""
    import time
    return p.stat().st_mtime if p.exists() else time.time()


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

    # META-RESEARCH REVIEW (§ docs/research/META_RESEARCH_DIRECTIVE.md). Mechanical half runs
    # EVERY cycle: it is seconds, no LLM, no context cost, and a prompt-only duty would be
    # skipped on a busy cycle exactly as this desk's own record predicts.
    if _days_since(state, "last_meta_research") >= _META_RESEARCH_D:
        _r = subprocess.run([sys.executable, "scripts/meta_research_review.py"],
                            capture_output=True, text=True, timeout=300, check=False)
        if Path("data/meta_research_review.json").exists():
            state["last_meta_research"] = now.isoformat()
            fired.append("meta-research")
        else:
            print(f"cadence: meta-research produced nothing rc={_r.returncode} -- duty stays OWED")

    # BREADTH EXPANSION + HYPOTHESIS GENERATION (daily). BOTH SHIPPED UNSCHEDULED, and the
    # allocator only surfaced it once its writer-attribution was corrected: an organ that writes
    # an artifact nothing calls is indistinguishable, in every report, from an organ that does not
    # exist. breadth_expander is the desk's only GENERATIVE source discovery ("here is territory
    # you have not looked at") and hypothesis_generator is the only generator that can see the
    # graveyard -- the one that stops the desk re-proposing the dead, which is exactly how the
    # principal's 50-hypothesis slate arrived three-quarters already-refuted.
    #
    # PRODUCTION, NOT EXIT CODE. Both are LLM organs against a shared wallet. A half-funded
    # roster 402s mid-run, the sanitiser drops the partial result, and the process exits clean --
    # the precise shape that let cadence_state claim a panel ran while nothing had been appended
    # for five days. So the duty is stamped on the ARTIFACT GROWING, never on the return code,
    # and their own budget guards handle the money.
    for _name, _script, _artifact, _key in (
            ("breadth-expansion", "scripts/breadth_expander.py",
             "data/breadth_expansion.jsonl", "last_breadth_expansion"),
            ("hypothesis-generation", "scripts/hypothesis_generator.py",
             "data/hypothesis_queue.jsonl", "last_hypothesis_generation")):
        if _days_since(state, _key) < 1.0:
            continue
        _p = Path(_artifact)
        try:
            _before = _p.stat().st_size
        except OSError:
            _before = -1
        _r = subprocess.run([sys.executable, _script],
                            capture_output=True, text=True, timeout=900, check=False)
        try:
            _after = _p.stat().st_size
        except OSError:
            _after = -1
        _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
        if _after > _before:
            state[_key] = now.isoformat()
            fired.append(_name)
            print(f"cadence: {_name} +{_after - _before}b | {_tail[0][:110]}")
        else:
            print(f"cadence: {_name} rc={_r.returncode} appended NOTHING -- duty stays OWED "
                  f"| {_tail[0][:110]}")

    # FILL QUALITY (weekly). The ledger ordered "re-measure WEEKLY until >60%" after the
    # patient-opens fix; that order never became code, so the fix has been unverified since it
    # shipped. Cheap, read-only, no keys.
    if _days_since(state, "last_fill_quality") >= 7:
        subprocess.run([sys.executable, "scripts/fill_quality_monitor.py"],
                       capture_output=True, text=True, timeout=120, check=False)
        if Path("data/fill_quality.json").exists():
            state["last_fill_quality"] = now.isoformat()
            fired.append("fill-quality")

    # DESK METRICS (every cycle). Durable trend, not a snapshot -- libs/monitoring persists
    # each value and raises a real Alert on threshold breach. Runs AFTER meta-research so it
    # records that cycle's freshly computed numbers, not the previous one's.
    _r = subprocess.run([sys.executable, "scripts/record_desk_metrics.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/desk_metrics.sqlite").exists():
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: desk-metrics rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("desk-metrics")

    # PORTFOLIO RISK (every cycle, self-arming). Dormant below 3 sleeves and load-bearing at
    # or above -- the gate is a DATA condition read from the shadow registry, so nobody has to
    # notice the third sleeve landing for correlation-shock control to start running.
    _r = subprocess.run([sys.executable, "scripts/run_portfolio_risk.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/portfolio_risk.json").exists():
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: portfolio-risk rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("portfolio-risk")

    # PROMOTION GATE (every cycle). Renders the eight-gate barrier explicitly and records the
    # verdict, so a promotion prerequisite can be audited after the fact instead of being
    # assembled implicitly per screen. Fail-closed: unchecked gates reject.
    _r = subprocess.run([sys.executable, "scripts/promotion_gate.py"],
                        capture_output=True, text=True, timeout=180, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/promotion_gate.json").exists():
        # SILENT STEPS ARE UNMONITORED STEPS. These three were fired with their output
        # discarded, so a crash or an empty run looked identical to success -- the same
        # state-touched-but-nothing-produced class _run_panel exists to catch.
        print(f"cadence: promotion-gate rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("promotion-gate")

    # DAILY HYPOTHESIS FUNNEL. Generation is the desk's #2 supreme objective and its output
    # was going straight into a queue nobody screened. This runs the arithmetic stage every
    # cycle -- cost floor, degenerate turnover, trivial-variation fingerprint, batch diversity --
    # so the gauntlet receives screened candidates and the desk can SEE its conversion rate.
    # No bar is moved: the screen rejects only on cheap unambiguous evidence and escalates
    # everything else, and no statistics are ever asked of a model.
    _r = subprocess.run([sys.executable, "scripts/hypothesis_screen.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0:
        print(f"cadence: hypothesis-funnel rc={_r.returncode} | {_tail[0][:110]}")
    else:
        fired.append("hypothesis-funnel")

    # CONSTITUTION (EVERY CYCLE). max_pi E[log W_T] is the desk's sole objective and the
    # aggression ratchet is what stops it eroding. Raising the high-water mark here means a
    # STRENGTHENED principle is locked in the same cycle it lands, with no ceremony -- while a
    # weakened one has nowhere to hide, because the mark it fell below is already committed.
    # Asymmetry is the whole design: strengthening is frictionless, weakening costs a hand-edit.
    try:
        from libs.doctrine.ratchet import check as _rcheck
        from libs.doctrine.ratchet import sync_preamble as _rsync
        from libs.doctrine.ratchet import update_high_water as _rraise
        _rep = _rcheck()
        if _rep.ok:
            _rraise()
            # The doctrine file holds a COPY of the constitution because a prompt cannot import
            # Python. Resyncing here, one-directionally from code to prompt, is what stops the
            # organs running on a superseded objective while the audit enforces the current one.
            _sync = _rsync()
            if _sync not in ("in-sync", "doctrine-missing"):
                print(f"cadence: constitution block {_sync} into ops/principal_doctrine.txt")
            fired.append("constitution")
            if _rep.raised:
                print(f"cadence: constitution STRENGTHENED -- {'; '.join(_rep.raised)}")
        else:
            print("cadence: CONSTITUTION RATCHET VIOLATED -- " + " | ".join(_rep.violations))
    except Exception as _e:       # a doctrine check must never be what stops a cycle
        print(f"cadence: constitution check failed to run ({type(_e).__name__}: {_e}) -- "
              "the objective is unenforced this cycle")

    # MOAT MINING (EVERY CYCLE, maximum cadence). The desk's information-advantage ranking puts
    # self-recorded order books at 1.03 and the next source at 0.37 -- the only asset here that
    # cannot be bought, scraped or replicated, and it sat at 0.4% exploitation with ZERO
    # mechanisms tested while every other organ was maximised. Hole-first and budgeted, so it
    # mines cells nobody has ever measured before re-measuring anything: that ordering is what
    # converges on 100% exploration instead of re-grinding the same convenient symbol. Runs every
    # cycle deliberately -- the archive only grows, so any cycle that skips it is coverage the
    # desk permanently ran late on.
    _r = subprocess.run([sys.executable, "scripts/mine_moat.py"],
                        capture_output=True, text=True, timeout=420, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/moat_mine.json").exists():
        print(f"cadence: moat-mine rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("moat-mine")
        print(f"cadence: {_tail[0][:150]}")

    # MOAT SCREENING AND SURVIVOR EXPLOITATION (EVERY CYCLE). Mining DESCRIBES the tape; screening
    # ASKS it whether any mechanism predicts, and promotion turns a persistent answer into a
    # forward clock. Running the first every cycle and the other two never was the asymmetry that
    # left the desk's one irreplaceable asset measured everywhere and exploited nowhere.
    #
    # The order is load-bearing: screen writes the registry, promote reads it. Promotion runs even
    # when screening produced nothing this pass, because persistence accumulates ACROSS passes and
    # a candidate can cross the bar on a cycle that found no new survivor at all.
    for _organ, _script, _artifact in (
            ("moat-screen", "scripts/screen_moat.py", "data/moat_screen.json"),
            ("moat-promote", "scripts/promote_moat_survivors.py", "data/moat_promotion.json"),
            # And the only OUT-OF-SAMPLE question in the whole pipeline: does a candidate that was
            # pre-registered still predict on tape recorded AFTER it was named? Everything above
            # this line is answered on tape that already existed when the candidate was chosen.
            ("moat-clocks", "scripts/review_moat_clocks.py", "data/moat_clock_review.json"),
            # THE CALLERS THAT WERE THEMSELVES ORPHANS. Each of these was written to make a
            # library module reachable -- emergence, wallet_graph, ict.cross_sectional -- and then
            # nothing ran the caller. The libs orphan check went green because the import existed,
            # which is how a wiring fix can be one link short and still report success. Each exits
            # cleanly naming its own blocker when its input is absent, so running them every cycle
            # costs seconds and turns "no data yet" into a dated statement rather than a silence.
            ("weak-signals", "scripts/cluster_weak_signals.py", "data/weak_signal_clusters.json"),
            ("wallet-graph", "scripts/resolve_wallets.py", "data/wallet_entities.json"),
            ("ict-xsec", "scripts/run_ict_cross_sectional.py", "data/ict_cross_sectional.json"),
            # SOLE IMPORTERS THAT NOTHING RAN -- found by the same sweep, pre-existing rather than
            # mine. run_axis_generate keeps libs.research.alpha_economics reachable and completes
            # in seconds; run_prediction_markets keeps libs.data.prediction_markets reachable and
            # now reports an empty fetch instead of dying on a pandas KeyError, so a cycle where
            # the venue is unreachable costs a line of output rather than a traceback.
            ("axis-generate", "scripts/run_axis_generate.py", "data/cadence_state.json"),
            ("prediction-markets", "scripts/run_prediction_markets.py", "data/cadence_state.json")):
        _r = subprocess.run([sys.executable, _script],
                            capture_output=True, text=True, timeout=420, check=False)
        _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
        if _r.returncode != 0 or not Path(_artifact).exists():
            print(f"cadence: {_organ} rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
        else:
            fired.append(_organ)
            print(f"cadence: {_tail[0][:150]}")

    # GAUNTLET CALIBRATION (EVERY CYCLE). 420 candidates tested, 420 died -- and "the candidates
    # were worthless" and "the screen cannot detect an edge it is handed" fit that observation
    # equally well while demanding opposite responses. Live data can never separate them because
    # the truth is never available; a planted edge of known strength can. The detection floor it
    # produces is the desk's one progress metric that cannot be gamed: hypothesis count rises by
    # generating more and survivor count rises by lowering the bar, but the floor moves only when
    # the desk genuinely gets better at finding weak edges.
    _r = subprocess.run([sys.executable, "scripts/calibrate_gauntlet.py"],
                        capture_output=True, text=True, timeout=420, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/gauntlet_calibration.json").exists():
        print(f"cadence: gauntlet-calibration rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("gauntlet-calibration")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # ANCESTOR ORGANS (EVERY CYCLE). Lineage, breeding, theory induction, feature invention and
    # the internal information market. Built with tests and no caller, which is the exact
    # "built but never runs" class this desk keeps finding in itself -- and a library wired six
    # weeks late meets a codebase that moved underneath it. Runs on the graveyard's 42 real
    # specimens today and reports honestly where that data cannot support a conclusion.
    _r = subprocess.run([sys.executable, "scripts/run_ancestors.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/ancestors.json").exists():
        print(f"cadence: ancestors rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("ancestors")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # TAPE -> BARS (EVERY CYCLE, BEFORE THE SCREEN). The recorders write 15s L2+trades; every
    # screen, feature and label on this desk eats OHLCV bars, and nothing converted between them --
    # so the ICT family reported NO BARS while 8.2GB of its input sat on disk in the wrong shape.
    # Ordered before screen_ict deliberately: screening last cycle's bars would silently evaluate
    # a stale window and report it as current.
    _r = subprocess.run([sys.executable, "scripts/build_bars.py"],
                        capture_output=True, text=True, timeout=900, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/build_bars.json").exists():
        fired.append("build-bars")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: build-bars rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # ICT SCREEN (EVERY CYCLE). The second strategy family landed with full test suites and NO
    # CALLER -- the desk's own "built but never runs" class, committed while fixing instances of it
    # elsewhere. Cheap (seconds, no network) and it refuses to synthesise bars when there are none,
    # so a fresh checkout reports NO BARS rather than screening a generator.
    _r = subprocess.run([sys.executable, "scripts/screen_ict.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/ict_screen.json").exists():
        fired.append("ict-screen")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: ict-screen rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # CANARIES (EVERY CYCLE). Charter §21 promised "re-run every 4 days" and nothing ran them:
    # the file was seeded 2026-07-19 with placeholder baselines and never executed, so no shift was
    # detectable in principle for two weeks. Cheap -- nine HTTP calls, seconds -- and the one that
    # matters (C9) guards a LIVE data path rather than merely informing a digger.
    _r = subprocess.run([sys.executable, "scripts/run_canaries.py"],
                        capture_output=True, text=True, timeout=300, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/canary_run.json").exists():
        fired.append("canaries")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: canaries rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # ACQUISITION PLAN (EVERY CYCLE). Triage #93, unblocked 2026-07-29 and unbuilt until now.
    # Ranks what data to acquire NEXT on measured terms rather than on research_cio's hardcoded
    # advantage table -- the adaptive term is the ontology's own attempts/survivors record, so a
    # class of data this desk has worked to exhaustion falls from EVIDENCE. Ranks only; it spends
    # nothing and starts no collector.
    _r = subprocess.run([sys.executable, "scripts/acquire_data.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[:1] or [""]
    if Path("data/acquisition_plan.json").exists():
        fired.append("acquisition")
        print(f"cadence: {_tail[0][:150]}")
    else:
        print(f"cadence: acquisition rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")

    # GAP-REGISTER MECHANICAL PASS (EVERY CYCLE). The register is, by the doctrine's own words,
    # "the only organ that DRIVES work" -- and its stated cadence ("re-ranked at the START of
    # every daily cycle") was executed by an LLM remembering to do it, which is precisely the
    # reliability hole this module's docstring exists to close. Seven days and fifty open rows.
    #
    # This is the MECHANICAL half only: deadlines, parked rows, ownership and starvation, all
    # computable and none of them opinions. It writes a stamp that deliberately does NOT match the
    # `Re-ranked` regex, so it cannot discharge the judgment duty -- an organ that cleared a check
    # it had not satisfied would stop the defect being reported and the work being done at the
    # same moment, and only the first of those is visible.
    _r = subprocess.run([sys.executable, "scripts/rerank_gaps.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/gap_rerank.json").exists():
        print(f"cadence: gap-rerank rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("gap-rerank")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # CONTRIBUTION ESTIMATES (EVERY CYCLE, BEFORE THE ALLOCATOR). run_allocator has reported the
    # same binding constraint on every cycle it has ever run -- "CONTRIBUTION ESTIMATES" -- and
    # P4 says the marginal resource goes to argmax_i |dE[log W]/dC_i|, an argmax that was being
    # taken over an empty set. This organ derives what it can from artifacts ON DISK and emits
    # NEVER_EXECUTED for the rest, so absence stays ranked and costed rather than being silently
    # read as zero. Ordered before the allocator deliberately: the allocator consumes its output,
    # and a stale contributions file would rank this cycle on last cycle's evidence.
    _r = subprocess.run([sys.executable, "scripts/estimate_contributions.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/contributions.json").exists():
        print(f"cadence: contributions rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("contributions")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # ALLOCATOR (EVERY CYCLE). The governing layer landed with full test suites and no caller,
    # which governs nothing: the constitution says every subsystem optimises dE[log W]/dx_i, and
    # until something computes those derivatives that sentence is decoration. With 0 alphas, 0
    # trials and 0 fills there is no honest contribution estimate for ANY subsystem, so this
    # deliberately produces NO ranking -- it reports the instrumentation gap, which is what P11
    # mandates when evidence is insufficient. The day the first real estimate lands, the allocator
    # is already running and already correct rather than written six weeks late.
    _r = subprocess.run([sys.executable, "scripts/run_allocator.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/allocator.json").exists():
        print(f"cadence: allocator rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("allocator")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:150]}")

    # P&L WATCHDOG (EVERY CYCLE, every mode). The desk's only P&L record is a once-a-day NAV
    # attestation that nothing read: between attestations a leak is invisible, and across them it
    # was visible only if somebody opened the file. A loss nobody looks at compounds exactly the
    # way the objective says wealth compounds, downward. This makes "why are we down?" a question
    # the desk asks itself rather than one a human has to think to ask.
    _r = subprocess.run([sys.executable, "scripts/watch_pnl.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/pnl_watch.json").exists():
        print(f"cadence: pnl-watch rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("pnl-watch")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:170]}")

    # CONSTITUTIONAL ENFORCEMENT (EVERY CYCLE). The constitutional checks were themselves pure
    # DETECTORS -- they produced defect entries and nothing repaired anything, which is exactly
    # what P25 forbids. This resolves every breach into AUTOFIX (applied here), PATCH_READY (the
    # exact edit, chased) or BLOCKED-by-design (the ratchet, where silent repair would destroy
    # the mechanism while appearing to defend it), and ages every one so a standing breach cannot
    # read as a fresh finding each morning.
    _r = subprocess.run([sys.executable, "scripts/enforce_constitution.py"],
                        capture_output=True, text=True, timeout=240, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/constitution_enforcement.json").exists():
        print(f"cadence: constitution-enforce rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("constitution-enforce")
        for _ln in (_r.stdout or "").strip().splitlines()[:1]:
            print(f"cadence: {_ln[:170]}")

    # COEXISTENCE (EVERY CYCLE). No sleeve, family or engine may cost another its growth, and
    # every one expands to its own maximum. Dormant until two families have a record -- MC_i is
    # undefined with one -- but the ORDER it enforces (orthogonality before retirement) binds
    # immediately and needs no data at all.
    _r = subprocess.run([sys.executable, "scripts/run_coexistence.py"],
                        capture_output=True, text=True, timeout=120, check=False)
    _tail = (_r.stdout or _r.stderr or "").strip().splitlines()[-1:] or [""]
    if _r.returncode != 0 or not Path("data/coexistence.json").exists():
        print(f"cadence: coexistence rc={_r.returncode} NO ARTIFACT | {_tail[0][:110]}")
    else:
        fired.append("coexistence")

    # MODEL UPGRADE (monthly). The desk's models used to be frozen literals that only ever moved
    # when a human noticed a newer flagship -- so seats aged silently (llama-4-maverick sat 15
    # months stale). This makes "are we on the best model available?" a cadence question with a
    # floor, answered by live evidence rather than by anyone remembering to ask.
    # FUNDING IS ALSO A TRIGGER, not just the calendar. Credits landing is exactly when the
    # question "what is the best model available?" becomes worth money, and the monthly clock
    # would otherwise sit on the answer for up to 30 days after payment.
    _funded_now = _funding_restored()
    if ((_days_since(state, "last_model_upgrade") >= _MODEL_UPGRADE_D or _funded_now)
            and _run_model_upgrade()):
        state["last_model_upgrade"] = now.isoformat()
        fired.append("model-upgrade" + (" (FUNDING-TRIGGERED)" if _funded_now else ""))
        _clear_funding_debt()
    elif _funded_now:
        # Debt deliberately NOT cleared: a sweep that could not evaluate the catalog has not
        # answered the question, and an unanswered question must stay owed.
        print("cadence: funding restored, flagship sweep OWED but DID NOT EVALUATE -- "
              "debt retained for the next run")

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
        if met:
            due.append("FREEZE-EXIT CRITERIA MET -- activate docs/POST_GATE0_MANIFEST.md "
                       "top to bottom; flip stage_state to S1; set post_gate0_activated. "
                       "Nothing deferred may be skipped.")
        else:
            state["freeze_exit_status"] = why
    _assert_floors(state, stage)
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")
    print(f"cadence[{stage}]: fired={fired or 'nothing due'} | "
          f"panel due in {max(0.0, _PANEL_EVERY_D - _days_since(state, 'last_panel')):.1f}d | "
          f"tier1 due in {max(0.0, _TIER1_EVERY_D - _days_since(state, 'last_tier1')):.1f}d")


if __name__ == "__main__":
    main()
