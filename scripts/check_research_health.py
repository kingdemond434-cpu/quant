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
    if ds is None:
        breaches.append("SHADOW: desk_state.json not pulled -- no off-box view of the clocks")
    else:
        fwd = ds.get("forward") or ds.get("shadow") or {}
        rows_f = fwd.get("rows") if isinstance(fwd, dict) else None
        if isinstance(rows_f, list) and rows_f:
            stale = [r.get("key") for r in rows_f
                     if isinstance(r, dict) and r.get("status") == "ACTIVE"
                     and (_age_h(r.get("last_attempt_at"), now) or 99) > 1.0]
            m["active_clocks"] = sum(1 for r in rows_f
                                     if isinstance(r, dict) and r.get("status") == "ACTIVE")
            m["stale_clocks"] = len(stale)
            if stale:
                breaches.append(f"SHADOW: {len(stale)} ACTIVE clock(s) not stamped for >1h "
                                f"(15-min engine): {', '.join(str(s) for s in stale[:5])}")
        else:
            m["active_clocks"] = "UNMEASURED (desk_state carries no forward rows)"

    return breaches, m


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
    if not breaches:
        print(f"research health: ALL FLOWING at {m['at']} "
              f"(targets={m.get('mined_targets_n')}, docket={m.get('docket_rows')}, "
              f"certs={m.get('certs_n')}, moat_syms={m.get('moat_symbols')})")
        return 0
    print(f"RESEARCH HEALTH BREACH {m['at']}\n")
    for b in breaches:
        print(f"  - {b}")
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
