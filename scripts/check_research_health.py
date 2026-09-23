"""RESEARCH HEALTH FENCE -- one organ that checks the WHOLE hourly loop and calls for repair.

WHY ONE CONSOLIDATED FENCE (principal 2026-08-27: "make sure the miners run optimally, all
retrieving data, pipeline working, gauntlet working, candidates not frozen in shadow -- and fix
them, noticing"). Every one of these has failed at least once, and each failure was invisible
from every OTHER organ's vantage point:

  * the moat recorder died and stayed dead 9 hours while its coverage summary kept rebuilding
    green (day-counts stay warm for a week after the tape stops);
  * 20 of 42 miners produced rows naming no symbol and scored "zero-yield" for weeks;
  * an empty docket cascaded into a canon wipe that only the moneypath fence caught;
  * certificate enrolment died on an ImportError and shadow saved "0 sleeves" for hours;
  * the warm sweep ran at cold speed because every cache save failed inside `except: pass`.

The per-organ fences (moneypath, same-day, job manifest, desk tasks, queue guard) stay -- they
are closer to their subjects and fire faster. This fence watches the FLOW between them: data in,
candidates through, verdicts out, clocks advancing. Silence in the flow is what nothing else
measures.

CONTINUOUS (default, cron every 30 min): freshness and liveness of every stage, repair-invoke
on breach. WEEKLY (--weekly, Sunday): the deep audit -- 7-day yield per stage, certs delta,
forward evidence accrued, miner usable rates, breach history from this fence's own journal --
written to reports/weekly_research_health.json where the vault and the dashboard can read it.
UNMEASURED is reported as UNMEASURED (L1.28a); absence of a file is never health.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
STATE = ROOT / "data" / "research_health_state.json"
WEEKLY_OUT = DESK / "reports" / "weekly_research_health.json"

#: Stage freshness ceilings, in hours. The loop is HOURLY, so 2h means "missed a beat and the
#: next one"; the moat tape gets 26h because weekend markets legitimately go quiet (crypto CFDs
#: keep printing, but the fence must not page every Saturday for FX being closed).
FRESH_H = {
    "mined_targets": 2.5, "docket": 2.5, "certs": 3.0,
    "moat_coverage_builder": 0.5, "moat_tape": 26.0, "desk_state": 0.5,
}


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _revocation_recorded(doc: object) -> bool | None:
    """Did this artifact record an explicit revocation? Delegates to the authority ratchet.
    True yes, False no, None COULD NOT ASK -- and the three are not interchangeable.

    ONE DETECTOR, NOT FOUR. The ratchet defines what counts as a sanctioned fall in earned
    evidence; every other fence that reacts to a falling count must ask IT, or the desk ends up
    with several answers to one question and finds out which is wrong only when they disagree.

    WHY THIS RETURNS THREE THINGS NOW (measured 2026-09-05, on the live box). It returned False
    on failure -- "the alarm still fires, which is the safe direction" -- and that reasoning was
    wrong twice over. First, the failure was not hypothetical: `check_authority_ratchet` imports
    `libs.ops.canon_lease` at module scope, and when THIS file runs as a script `sys.path[0]` is
    `scripts/`, not the repo root, so that import raised ModuleNotFoundError on EVERY run. The
    bare `except` swallowed it and the detector answered False forever. Called by hand from the
    repo root it answered True, which is why it read as correct.

    Second, and worse: the alarm it fired says "restore from canon before anything else", and
    following it would have restored six AFG and two AFL certificates the desk had just retired
    with a full record for being uncashable. An alarm that instructs a destructive repair is not
    the safe direction when it cannot tell whether the repair is needed. Silence about a real
    wipe is bad; a confident instruction to undo a correct decision is worse.

    So the path is repaired AND the uncertainty is reported as uncertainty.
    """
    try:
        import importlib.util
        # THE REPO ROOT, NOT JUST scripts/. The ratchet imports `libs.*` at module scope.
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location(
            "_car_for_health", ROOT / "scripts" / "check_authority_ratchet.py")
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return bool(mod._has_revocation(doc))
    except Exception:
        return None


def _age_h(ts: str | None, now: datetime) -> float | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts))
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return (now - t).total_seconds() / 3600.0
    except ValueError:
        return None


def _live_desk_procs(now) -> tuple[set[str], float | None]:
    """Producer names currently alive on the desk box, from the stall watchdog's own table.

    Returns an EMPTY set when the snapshot is missing or stale, so an unreadable liveness signal
    can never be mistaken for "nothing is running" -- callers then fall back to age alone, which
    is the conservative direction (it reports a breach rather than hiding one). UNMEASURED is a
    real answer; it just is not a reassuring one.
    """
    snap = _read(DESK / "data" / "stall_watch.json")
    if not isinstance(snap, dict):
        return set(), None
    age_h = _age_h(snap.get("checked_at"), now)
    # The watchdog runs every few minutes; anything older than 20 describes a box we no longer
    # have current information about.
    if age_h is None or age_h > (20.0 / 60.0):
        return set(), (round(age_h, 2) if age_h is not None else None)
    procs = snap.get("procs")
    if not isinstance(procs, dict):
        return set(), round(age_h, 2)
    # Keys are "<script>.<pid>"; the script name is the identity that matters here.
    return {str(k).rsplit(".", 1)[0] for k in procs}, round(age_h, 2)


def _mtime_age_h(p: Path, now: datetime) -> float | None:
    try:
        return (now - datetime.fromtimestamp(p.stat().st_mtime, UTC)).total_seconds() / 3600.0
    except OSError:
        return None


def collect(now: datetime) -> tuple[list[str], dict]:
    """One pass over the flow. Returns (breaches, measurements)."""
    breaches: list[str] = []
    m: dict = {"at": now.isoformat(timespec="seconds")}

    # --- miners: are they producing, and is their output usable?
    mt = _read(DESK / "data" / "hypotheses" / "mined_targets.json")
    if mt is None:
        breaches.append("MINERS: mined_targets.json missing/unreadable -- the attention list "
                        "the searcher digs first does not exist")
    else:
        age = _age_h(mt.get("built_at"), now)
        m["mined_targets_age_h"] = round(age, 2) if age is not None else None
        m["mined_targets_n"] = len(mt.get("targets") or [])
        dead = mt.get("miners_naming_no_symbol") or []
        health = mt.get("miner_health") or {}
        m["miner_sources"] = len(health)
        m["miners_naming_no_symbol"] = len(dead)
        if age is None or age > FRESH_H["mined_targets"]:
            breaches.append(f"MINERS: mined_targets is {age and round(age, 1)}h old "
                            f"(ceiling {FRESH_H['mined_targets']}h) -- the hourly stage stopped")
        if not m["mined_targets_n"]:
            breaches.append("MINERS: zero targets -- every miner is silent or unparseable")
        all_err = sorted(k for k, v in health.items()
                         if isinstance(v, dict) and v.get("rows") and
                         v.get("fetch_errors") == v.get("rows"))
        m["miners_all_errors"] = len(all_err)
        if health and len(all_err) >= max(3, len(health) // 3):
            breaches.append(f"MINERS: {len(all_err)}/{len(health)} sources produce ONLY fetch "
                            f"errors -- dead selectors or blocked endpoints, not quiet ground: "
                            f"{', '.join(all_err[:6])}")
        if health and len(dead) >= max(3, len(health) // 2):
            breaches.append(f"MINERS: {len(dead)}/{len(health)} sources produce rows naming NO "
                            f"symbol -- their selectors are broken ground, not absence of edge: "
                            f"{', '.join(sorted(dead)[:6])}")

    # --- docket: do candidates actually reach the gauntlet?
    docket = DESK / "data" / "hypotheses" / "external_survivors.json"
    rows = _read(docket)
    age = _mtime_age_h(docket, now)
    m["docket_age_h"] = round(age, 2) if age is not None else None
    m["docket_rows"] = len(rows) if isinstance(rows, list) else 0
    if age is None or age > FRESH_H["docket"]:
        breaches.append(f"DOCKET: external_survivors is {age and round(age, 1)}h old -- "
                        f"merge/scp leg of the hourly pipeline stopped")
    elif not m["docket_rows"]:
        breaches.append("DOCKET: zero candidate rows shipped -- the empty-docket seals held "
                        "upstream, but the flow itself is dry")

    # --- TRADING ITSELF. Checked FIRST because it outranks every research question here: a desk
    # that is not trading has no upside to protect, and a research pipeline in perfect health is
    # worth nothing while the book is inert. The desk auto-paused on 2026-08-25 with a message
    # naming the exact cause -- the terminal's AutoTrading button was off -- and sat that way for
    # three days because no fence read the marker it had written.
    # REPORT ONLY, NEVER CURED HERE. Re-arming means placing live orders, and nothing on this box
    # gets to make that decision on its own; the money path takes no autonomous fixer by standing
    # rule. Naming it loudly every five minutes is the entire job.
    paused = DESK / "data" / "GATEWAY_PAUSED"
    if paused.exists():
        try:
            why = paused.read_text("utf-8").strip().splitlines()
            first = next((ln.strip() for ln in why if ln.strip()), "no reason recorded")
            cause = next((ln.strip() for ln in why[1:] if ln.strip()), "")
        except OSError:
            first, cause = "unreadable marker", ""
        halt_age = _mtime_age_h(paused, now)
        m["trading_halted"] = True
        m["trading_halted_hours"] = round(halt_age, 1) if halt_age is not None else None
        days = f"{halt_age / 24:.1f} day(s)" if halt_age is not None else "an unknown period"
        breaches.append(
            f"TRADING HALTED for {days} -- THE DESK IS NOT TRADING. {first}"
            + (f" || {cause}" if cause else "")
            + " || This is never auto-cleared: re-arming places live orders. Delete "
              "desks/mt5/data/GATEWAY_PAUSED on the desk box once the cause is fixed.")
    else:
        m["trading_halted"] = False

    # --- searchers: the docket can look fresh on miners alone while both search legs are
    # dead (measured 2026-08-27: edge_search OOM-dead 25h, docket green the whole time --
    # a per-source blind spot). Each producer owes its own freshness.
    # STILL WORKING IS NOT STOPPED. These producers write their artifact ONCE, at the end, and a
    # full search takes well over an hour -- so artifact age alone calls a healthy long run dead.
    # That is not a harmless false positive: the SEARCH fixer responds by clearing the job lock,
    # which invites a SECOND searcher onto a box that has already been driven to 0.3GB free by
    # one (2026-08-28). The fence would have been manufacturing the collision it exists to catch.
    # The desk box's own stall watchdog already publishes a live process table with per-process
    # CPU, and that artifact is pulled here, so liveness costs nothing extra to consult.
    live_procs, procs_age_h = _live_desk_procs(now)
    m["desk_procs_age_h"] = procs_age_h
    for fname, label, proc in (("edge_search_results.json", "SEARCH", "edge_search"),
                               ("orthogonal_candidates.json", "SWEEP", "orthogonal_sweep")):
        f_age = _mtime_age_h(DESK / "data" / "hypotheses" / fname, now)
        m[f"{label.lower()}_age_h"] = round(f_age, 2) if f_age is not None else None
        running = proc in live_procs
        m[f"{label.lower()}_running"] = running
        if f_age is not None and f_age <= 3.0:
            continue
        # A run that is alive but has produced nothing for this long is no longer "in progress",
        # it is stuck -- so liveness postpones the breach, it never cancels it.
        if running and (f_age is not None and f_age <= 6.0):
            m.setdefault("notes", []).append(
                f"{label}: artifact is "
                f"{str(round(f_age, 1)) + 'h old' if f_age is not None else 'missing'} but "
                f"{proc} is RUNNING on the desk box -- in progress, not stopped. No fixer.")
            continue
        breaches.append(f"{label}: {fname} is "
                        f"{'missing' if f_age is None else str(round(f_age, 1)) + 'h old'} "
                        f"(hourly leg) -- the {label.lower()} has stopped producing; the "
                        f"docket is running on miners alone"
                        + (f" ({proc} is alive but has produced nothing in "
                           f"{round(f_age, 1)}h -- stuck, not working)" if running else ""))

    # --- gauntlet: last sweep's actual judgment numbers, for the dashboard pulse
    gates = _read(DESK / "reports" / "universal_gates_external.json") or {}
    verd = gates.get("verdicts")
    if isinstance(verd, list):
        m["last_sweep_judged"] = len(verd)
        m["last_sweep_passed"] = sum(1 for v in verd if isinstance(v, dict) and v.get("passed"))

    # --- gauntlet: verdicts still being minted, canon never shrinking?
    surv = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
    if surv is None:
        breaches.append("GAUNTLET: UNIVERSAL_SURVIVORS.json unreadable -- no canon at all")
    else:
        age = _age_h(surv.get("swept_at"), now)
        m["certs_swept_age_h"] = round(age, 2) if age is not None else None
        m["certs_n"] = int(surv.get("n") or 0)
        if age is None or age > FRESH_H["certs"]:
            breaches.append(f"GAUNTLET: canon last swept {age and round(age, 1)}h ago "
                            f"(hourly cadence) -- the desk gauntlet or the cert pull stopped")
        prior = _read(STATE) or {}
        last_n = int((prior.get("ratchet") or {}).get("certs_n") or 0)
        # A RECORDED REVOCATION IS NOT A WIPE, AND THIS IS THE THIRD PLACE THAT HAD TO LEARN IT.
        # check_authority_ratchet owns the question "was this fall sanctioned"; the precommit
        # guard re-implemented the answer and got it wrong, and so did this. Measured 2026-09-03:
        # eight uncashable certificates (six AFG, two AFL, on symbols absent from the registry
        # with no H1 parquet -- L1.49, a gate that cannot be cashed is not a survivor) were
        # retired WITH a full `retired_certificates` record, and this fence reported it as "a
        # wipe got past the writer seals; restore from canon before anything else". Acting on
        # that advice would have restored the very rows the desk had just decided it can never
        # trade. Import the one detector rather than writing a fourth copy of it.
        if m["certs_n"] < last_n:
            sanctioned = _revocation_recorded(surv)
            m["canon_fall_sanctioned"] = sanctioned
            if sanctioned is None:
                # COULD NOT ASK. Report the fall and say the question is unanswered; do NOT
                # instruct a restore, because the restore is destructive when the fall was
                # sanctioned and this branch is precisely where that is unknown.
                breaches.append(
                    f"GAUNTLET: canon fell {last_n} -> {m['certs_n']} and the authority ratchet "
                    f"could not be asked whether it was sanctioned -- UNMEASURED, not a wipe. "
                    f"Check retired_certificates before restoring anything.")
            elif not sanctioned:
                breaches.append(f"GAUNTLET: canon SHRANK {last_n} -> {m['certs_n']} -- a wipe got "
                                f"past the writer seals; restore from canon before anything else")

    # --- data feeds: a starved input idles whole families while reading as quiet ground
    # (measured: macro 5 days stale -> macro_conditional produced zero signals on 297 straight
    # passes). Each feed owes its own freshness; fixers re-run the producer, and the producers
    # now carry alternate foreign-ecosystem routes (DBnomics mirror) when a primary blocks.
    for label, path, max_h in (
            ("DATA-MACRO", DESK / "data" / "macro_state.json", 26.0),
            ("DATA-COT", ROOT / "data" / "cot_zcache.parquet", 8 * 24.0),
            ("DATA-EVENTS", DESK / "data" / "intelligence" / "ff_calendar_vintage", 26.0)):
        try:
            if path.is_dir():
                newest = max((f.stat().st_mtime for f in path.iterdir()), default=None)
                f_age = ((now.timestamp() - newest) / 3600.0) if newest else None
            else:
                f_age = _mtime_age_h(path, now)
        except OSError:
            f_age = None
        m[label.lower().replace("-", "_") + "_age_h"] = (round(f_age, 2)
                                                          if f_age is not None else None)
        if f_age is None or f_age > max_h:
            breaches.append(f"{label}: {path.name} is "
                            f"{'missing' if f_age is None else str(round(f_age, 1)) + 'h old'} "
                            f"(ceiling {max_h:.0f}h) -- the families reading it are starving "
                            f"while the staleness reads as quiet ground")

    # --- BREADTH + FAMILY REACHABILITY on the FAST fence (principal 2026-08-28: "as frequent
    # as possible"). Governance re-checks these against ratchets every 15 minutes; a class that
    # drops out of the docket or a family that becomes unreachable is discovery capacity lost by
    # the hour, so the 5-minute pass carries them too.
    try:
        import sys as _sb
        _sb.path.insert(0, str(DESK))
        _sb.path.insert(0, str(DESK / "side_channels"))
        from mt5desk.universe import classify_all
        _inst = classify_all(json.loads((DESK / "data" / "universe" / "universe.json")
                                        .read_text("utf-8")))
        _usable = {i.symbol: i.asset_class for i in _inst if i.usable}
        _hunted = {r.get("symbol") or r.get("sym") for r in (rows or [])}
        _per: dict[str, int] = {}
        for _sym in _hunted:
            _c = _usable.get(str(_sym))
            if _c:
                _per[_c] = _per.get(_c, 0) + 1
        m["classes_hunted"] = _per
        _missing = sorted(c for c in set(_usable.values()) if c not in _per)
        if _missing:
            breaches.append(f"BREADTH: zero docket coverage for {', '.join(_missing)} -- "
                            f"ground the desk owns and never hunts")
        import run_external_backtest as _sa
        from mt5desk import families as _fam
        from mt5desk import families_orthogonal as _fo
        _reg = ({n[7:] for n in dir(_fam) if n.startswith("family_")}
                | set(_fo.ORTHOGONAL_FAMILIES))
        _unreach = sorted(_reg - set(_sa.FAMILY_FUNCS))
        m["families_reachable"] = len(set(_sa.FAMILY_FUNCS))
        if _unreach:
            breaches.append(f"FAMILIES: {len(_unreach)} registered family(ies) unreachable "
                            f"from the backtest door: {', '.join(_unreach[:5])}")
    except Exception as exc:
        m["classes_hunted"] = f"UNMEASURED ({type(exc).__name__})"

    # --- SEAT YIELD: the daily Claude cycles are the desk's discovery brains, and their own
    # meter (data/seat_launch_yield.json) measured 107 launches -> 21 produced over 7 days,
    # 23.9%, with five regional seats that have NEVER produced. Nothing consumed that finding,
    # so it sat in a file: a measurement organ whose output no fence reads is a log line.
    # AUTH_UNAVAILABLE is EXPECTED inside a quota window (the memo records the wall and
    # organ_catchup re-fires when it lifts) -- so a wall is never the breach. A seat that
    # produces NOTHING across the whole window is, because that is capacity the desk pays for
    # and never receives.
    sy = _read(ROOT / "data" / "seat_launch_yield.json")
    if sy:
        sy_age = _age_h(sy.get("measured_at"), now)
        m["seat_yield_pct"] = sy.get("yield_pct")
        m["seat_dead"] = len(sy.get("dead_seats") or [])
        m["seat_yield_age_h"] = round(sy_age, 2) if sy_age is not None else None
        if sy_age is None or sy_age > 26:
            breaches.append(f"SEATS: launch-yield meter is "
                            f"{'missing' if sy_age is None else str(round(sy_age, 1)) + 'h old'} "
                            f"-- the brains' own scorecard has stopped being measured")
        dead = sy.get("dead_seats") or []
        if dead:
            breaches.append(f"SEATS: {len(dead)} seat(s) produced NOTHING in "
                            f"{sy.get('window_days')}d -- launches spent, capacity never "
                            f"received: {', '.join(str(x) for x in dead[:6])}")
        # RECENT crashes only. The 7-day window includes deaths whose cause is already fixed
        # (six gap-wirer OOM kills, bounded 2026-08-27) and paging on history trains the reader
        # to ignore the row -- while a crash TODAY is a live defect.
        died_recent = int(sy.get("died_recent_24h") or 0)
        m["seat_deaths_24h"] = died_recent
        if died_recent >= 3:
            breaches.append(f"SEATS: {died_recent} launch(es) died in the last 24h (not quota "
                            f"walls) -- a crashing seat is a defect, not a closed window")

    # --- LOCAL MINER CONTRIBUTION. Every producer that feeds the docket owes a measurable
    # share; an aggregate "docket is healthy" hides a dead producer behind a busy one. A
    # producer that has been contributing and drops to zero is a named breach with a fixer.
    roi_doc = _read(ROOT / "data" / "dig_roi.json") or {}
    by_prod = roi_doc.get("by_producer") or {}
    if by_prod:
        m["producers_contributing"] = roi_doc.get("producers_contributing")
        m["by_producer"] = by_prod
        known = ("edge_search_results.json", "orthogonal_candidates.json",
                 "miner_candidates.json", "external_backtest_results.json")
        silent = [k for k in known if int(by_prod.get(k) or 0) == 0]
        if len(silent) >= 3:
            breaches.append(f"MINERS: {len(silent)} of {len(known)} local producers contribute "
                            f"ZERO testable candidates: {', '.join(silent)} -- the docket is "
                            f"carried by one source and the rest are not hunting")

    # --- certificates in the pipeline: the same-day fence is the authority on
    # CERTIFIED-NOT-ENROLLED / UNSTAMPED / IDLE-CLOCK; its verdict rides every pulse so the
    # dashboard shows certificate wiring at the same cadence as everything else.
    try:
        import subprocess as _sp
        r = _sp.run([sys.executable, str(ROOT / "scripts" / "check_sameday_pipeline.py")],
                    capture_output=True, text=True, timeout=120, check=False)
        lines = [ln.strip()[2:].strip() for ln in (r.stdout or "").splitlines()
                 if ln.strip().startswith("- ")]
        m["certs_pipeline"] = "OK" if r.returncode == 0 else "BREACH"
        for ln in lines[:4]:
            breaches.append(f"CERTS: {ln[:220]}")
    except Exception as exc:
        m["certs_pipeline"] = f"UNMEASURED ({type(exc).__name__})"

    # --- moat: is the tape actually being written, not just summarized?
    mc = _read(DESK / "data" / "moat_coverage.json")
    if mc is None:
        breaches.append("MOAT: moat_coverage.json missing -- the desk state builder is not "
                        "publishing, so the moat contributes zero off-box")
    else:
        b_age = _age_h(mc.get("built_at"), now)
        t_age = _age_h(mc.get("newest_tape_write"), now)
        m["moat_builder_age_h"] = round(b_age, 2) if b_age is not None else None
        m["moat_newest_write_age_h"] = round(t_age, 2) if t_age is not None else None
        m["moat_symbols"] = len(mc.get("coverage") or {})
        if b_age is None or b_age > FRESH_H["moat_coverage_builder"]:
            breaches.append(f"MOAT: coverage summary is {b_age and round(b_age, 1)}h old -- the "
                            f"5-minute desk state builder stopped")
        if t_age is None:
            m["moat_tape"] = "UNMEASURED (builder does not publish newest_tape_write yet)"
        elif t_age > FRESH_H["moat_tape"]:
            breaches.append(f"MOAT: newest tape write is {round(t_age, 1)}h old -- the recorder "
                            f"is DEAD while its coverage summary stays green; restart "
                            f"MT5-MoatRecorder on the desk box")

    # --- shadow: clocks stamping themselves, nothing silently stopped?
    ds = _read(ROOT / "web" / "desk_state.json")
    ds_age = _age_h((ds or {}).get("generated_at"), now)
    m["desk_state_age_h"] = round(ds_age, 2) if ds_age is not None else None
    if ds is None:
        breaches.append("SHADOW: desk_state.json not pulled -- no off-box view of the clocks")
    elif ds_age is not None and ds_age > FRESH_H["desk_state"]:
        breaches.append(f"PULL: desk_state is {round(ds_age, 1)}h old (5-min builder + 2-min "
                        f"pull) -- the desk->VPS artery is down; every desk-side reading on "
                        f"this pulse is that stale too")
    else:
        # forward_detail is what the dashboard itself renders -- one source, same numbers
        rows_f = (ds.get("pipeline") or {}).get("forward_detail")
        if isinstance(rows_f, list) and rows_f:
            stale = [r.get("key") or r.get("name") for r in rows_f
                     if isinstance(r, dict) and r.get("status") == "ACTIVE"
                     and r.get("last_attempt_at")
                     and (_age_h(r.get("last_attempt_at"), now) or 0) > 1.0]
            m["active_clocks"] = sum(1 for r in rows_f
                                     if isinstance(r, dict) and r.get("status") == "ACTIVE")
            m["stale_clocks"] = len(stale)
            if stale:
                breaches.append(f"SHADOW: {len(stale)} ACTIVE clock(s) not stamped for >1h "
                                f"(15-min engine): {', '.join(str(s) for s in stale[:5])}")
        else:
            m["active_clocks"] = "UNMEASURED (desk_state carries no forward rows)"
        # FORWARD EVIDENCE MUST ACCRUE, not merely stamp. Clocks can tick every 15 minutes
        # (last_attempt fresh, status ACTIVE) while every n stays 0 -- coverage refusals, a
        # broken family constructor, a data gap. Three days of that across the WHOLE book is a
        # pipeline fault, not patience (single quiet sleeves are normal; a silent BOOK is not).
        if isinstance(rows_f, list) and rows_f:
            active = [r for r in rows_f if isinstance(r, dict) and r.get("status") == "ACTIVE"]
            with_n = sum(1 for r in active if (r.get("n") or r.get("trades") or 0) > 0)
            oldest_days = max((int(r.get("days") or r.get("days_active") or 0)
                               for r in active), default=0)
            m["clocks_with_trades"] = with_n
            m["oldest_clock_days"] = oldest_days
            if active and with_n == 0 and oldest_days >= 3:
                breaches.append(f"FORWARD: {len(active)} ACTIVE clock(s), oldest {oldest_days}d, "
                                f"and not one holds a forward trade -- the book is stamping "
                                f"without accruing; something upstream of every sleeve is broken")

        # BLOCKED CLOCKS ARE A BREACH, NOT A ROW STATE. A sleeve that errors out of evaluation
        # (KeyError from a gutted registry, a missing input) keeps its certificate and its
        # window while accruing NOTHING -- measured 2026-08-27: both gap-decay clocks sat
        # BLOCKED_SLEEVE_ERROR while every fence read green, because "blocked" lived only as a
        # string inside one row. The fixer heals the usual causes (the desk watchdog restores a
        # shrunken registry) and re-runs the engine.
        if isinstance(rows_f, list):
            blocked = [str(r.get("name") or r.get("key")) for r in rows_f
                       if isinstance(r, dict)
                       and str(r.get("status") or "").upper().startswith("BLOCKED")]
            m["blocked_clocks"] = len(blocked)
            if blocked:
                breaches.append(f"CLOCKS: {len(blocked)} sleeve(s) BLOCKED from evaluation -- "
                                f"certificates with windows accruing nothing: "
                                f"{', '.join(blocked[:4])}")

        sw = ds.get("stall_watch") or {}
        sw_age = _age_h(sw.get("checked_at"), now)
        m["stall_watch_age_h"] = round(sw_age, 2) if sw_age is not None else None
        m["stall_watch_actions"] = sw.get("actions") or []
        if sw_age is None:
            m["stall_watch"] = "UNMEASURED (watchdog has not reported yet)"
        elif sw_age > 0.5:
            breaches.append(f"STALL-WATCH: the watchdog itself has been silent "
                            f"{round(sw_age, 1)}h (10-min cadence) -- the healer needs healing")

    # --- the box itself: available memory. The kernel OOM killer chose the REPAIR ORGAN as
    # its victim at 09:01 today; below this floor it will choose again, and whichever organ
    # dies will die silently. Report-only: killing things to free memory is the kernel's
    # mistake, not a fixer to imitate.
    try:
        avail_kb = int(next(ln for ln in Path("/proc/meminfo").read_text().splitlines()
                            if ln.startswith("MemAvailable")).split()[1])
        m["mem_available_mb"] = avail_kb // 1024
        if avail_kb < 300 * 1024:
            # WHO HOLDS IT, NOT ONLY HOW LITTLE IS LEFT. "238MB available" on an 8 GB box was
            # read for days as "the box is small" when it meant "7.7 GB is resident in something
            # nobody named". scripts/enforce_mt5_mandate.py writes the census on every pipeline
            # cycle; the top three holders ride on the breach so the reader knows where to look
            # and whether the enforcer already dealt with it.
            who = ""
            try:
                doc = json.loads((ROOT / "data" / "mandate_enforcement.json")
                                 .read_text(encoding="utf-8"))
                top = [f"{r['rss_mb']}MB {str(r['cmd']).split()[-1][:44]}"
                       for r in (doc.get("census_top") or [])[:3]]
                forb = float(doc.get("held_by_forbidden_mb") or 0.0)
                who = (" -- held by: " + "; ".join(top)) if top else ""
                if forb > 0:
                    who += (f"; {forb}MB of it in mandate-forbidden organs the enforcer is "
                            f"stopping")
            except (OSError, ValueError, KeyError, TypeError):
                who = " -- no census (scripts/enforce_mt5_mandate.py has not run here)"
            breaches.append(f"MEMORY: {avail_kb // 1024}MB available on the research box -- "
                            f"below the 300MB floor at which the kernel OOM killer starts "
                            f"choosing victims among the organs{who}")
    except (OSError, StopIteration, ValueError):
        m["mem_available_mb"] = None

    return breaches, m


def publish_pulse(breaches: list[str], m: dict) -> None:
    """The dashboard IS the proof of life (principal 2026-08-27: "if I don't see it, I'll
    assume it isn't working"). Every fence run lands its verdict and the stage ages where the
    brain page reads them -- nobody should ever have to ask a session whether the loop ran."""
    try:
        (ROOT / "web" / "research_pulse.json").write_text(json.dumps({
            "at": m.get("at"),
            "verdict": "ALL FLOWING" if not breaches else "BREACH",
            "breaches": breaches,
            "measurements": m,
        }, indent=1), "utf-8")
    except OSError as exc:
        print(f"pulse publish failed ({exc}) -- the fence verdict stands regardless")


def journal(breaches: list[str], m: dict) -> None:
    state = _read(STATE) or {}
    state.setdefault("journal", []).append({"at": m["at"], "breaches": breaches,
                                            "measurements": m})
    state["journal"] = state["journal"][-720:]  # ~15 days at 30-min cadence
    state["ratchet"] = {"certs_n": max(int(m.get("certs_n") or 0),
                                       int((state.get("ratchet") or {}).get("certs_n") or 0))}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), "utf-8")


def weekly() -> int:
    """The deep audit: what did the week actually produce, stage by stage?"""
    now = datetime.now(tz=UTC)
    state = _read(STATE) or {}
    cut = (now - timedelta(days=7)).isoformat()
    week = [j for j in state.get("journal", []) if str(j.get("at")) >= cut]
    breach_counts: dict[str, int] = {}
    for j in week:
        for b in j.get("breaches", []):
            key = b.split(":", 1)[0]
            breach_counts[key] = breach_counts.get(key, 0) + 1
    certs = [j["measurements"].get("certs_n") for j in week
             if isinstance(j.get("measurements"), dict)
             and j["measurements"].get("certs_n") is not None]
    dockets = [j["measurements"].get("docket_rows") for j in week
               if isinstance(j.get("measurements"), dict)
               and j["measurements"].get("docket_rows") is not None]
    breaches_now, m = collect(now)
    report = {
        "built_at": now.isoformat(timespec="seconds"),
        "window": "7d",
        "checks_in_window": len(week),
        "breach_counts_by_stage": breach_counts,
        "certs_start_end": [certs[0], certs[-1]] if certs else "UNMEASURED (no journal yet)",
        "docket_rows_median": (sorted(dockets)[len(dockets) // 2]
                               if dockets else "UNMEASURED"),
        "current": m,
        "current_breaches": breaches_now,
        "note": ("The weekly audit reads this fence's own 30-minute journal. A week with an "
                 "empty journal means the CONTINUOUS fence was not running -- which is itself "
                 "the first defect to fix (III.16: unwired or idle is a defect)."),
    }
    WEEKLY_OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"weekly research health -> {WEEKLY_OUT}")
    for k, v in breach_counts.items():
        print(f"  {k}: {v} breach(es) this week")
    if not week:
        print("  JOURNAL EMPTY -- the continuous fence has not been running; wire it first")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true")
    args = ap.parse_args()
    if args.weekly:
        return weekly()
    now = datetime.now(tz=UTC)
    breaches, m = collect(now)
    journal(breaches, m)
    publish_pulse(breaches, m)
    if not breaches:
        print(f"research health: ALL FLOWING at {m['at']} "
              f"(targets={m.get('mined_targets_n')}, docket={m.get('docket_rows')}, "
              f"certs={m.get('certs_n')}, moat_syms={m.get('moat_symbols')})")
        return 0
    print(f"RESEARCH HEALTH BREACH {m['at']}\n")
    for b in breaches:
        print(f"  - {b}")
    # IMMEDIATE FIRST-AID before the analyst. Deterministic per-class fixers run NOW (cleared
    # locks, re-triggered tasks, re-run merges) -- rate-limited and journaled in
    # data/auto_fixer_state.json, surfaced on the pulse. The gap-wirer below remains the
    # deep-repair path for whatever first aid cannot close.
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from auto_fixers import apply as _apply_fixers
        m["fixer_actions"] = _apply_fixers(breaches)
        publish_pulse(breaches, m)      # re-publish so the dashboard shows the first aid
    except Exception as exc:
        print(f"  auto-fixers unavailable ({type(exc).__name__}: {exc}); breach stands")
    try:
        sys.path.insert(0, str(ROOT))
        from libs.ops.repair_invoke import request_repair
        print()
        request_repair("research-health breach: " + "; ".join(b.split(":")[0]
                                                              for b in breaches))
    except Exception as exc:
        print(f"\nrepair-invoke unavailable ({type(exc).__name__}: {exc}); breach stands")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
