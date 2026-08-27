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

    # --- searchers: the docket can look fresh on miners alone while both search legs are
    # dead (measured 2026-08-27: edge_search OOM-dead 25h, docket green the whole time --
    # a per-source blind spot). Each producer owes its own freshness.
    for fname, label in (("edge_search_results.json", "SEARCH"),
                         ("orthogonal_candidates.json", "SWEEP")):
        f_age = _mtime_age_h(DESK / "data" / "hypotheses" / fname, now)
        m[f"{label.lower()}_age_h"] = round(f_age, 2) if f_age is not None else None
        if f_age is None or f_age > 3.0:
            breaches.append(f"{label}: {fname} is "
                            f"{'missing' if f_age is None else str(round(f_age, 1)) + 'h old'} "
                            f"(hourly leg) -- the {label.lower()} has stopped producing; the "
                            f"docket is running on miners alone")

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
        if m["certs_n"] < last_n:
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
            breaches.append(f"MEMORY: {avail_kb // 1024}MB available on the research box -- "
                            f"below the 300MB floor at which the kernel OOM killer starts "
                            f"choosing victims among the organs")
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
