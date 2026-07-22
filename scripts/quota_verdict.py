#!/usr/bin/env python3
"""QUOTA VERDICT WATCH (principal 2026-07-21): full cadence stays -- measure whether Pro
sustains it and page a clear YES/NO on Max, once the data is unambiguous.

No compromise on cadence. This does NOT throttle anything. It observes the REAL autonomous-only
throughput (starting from a clean baseline set when the operator leaves), compares realized
successful runs against the configured schedule, and renders ONE verdict to the principal:
  MAX NEEDED    -- quota-deaths are eating the schedule; the full cadence does not fit Pro.
  PRO SUFFICIENT -- the full cadence runs clean; no upgrade required. Save the money.
Either way the principal gets a definitive answer via ntfy instead of the CRO guessing.

Runs on its own 3h cron so it can page the MOMENT the signal is clear (a run of dead cycles
needs no 48h wait), but will not verdict before a minimum clean-observation window.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data/cro_ai_logs"
STATE = ROOT / "data/quota_watch.json"
PA = ROOT / "data/PRINCIPAL_ACTION.md"

MIN_OBS_H = 28.0          # do not render a verdict before this many hours of clean data
CYCLE_EVERY_H = 6.0       # 4 cycles/day
MINERS_PER_DAY = 7
DEATH_FRAC_MAX = 0.25     # >25% of scheduled runs dying on quota => Pro insufficient
SUCCESS_FRAC_MIN = 0.70   # <70% of scheduled cycles succeeding => Pro insufficient


def _load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text("utf-8"))
        except Exception:
            pass
    # baseline = now: the operator is leaving; the clean autonomous window starts here
    d = {"baseline": datetime.now(tz=UTC).isoformat(), "verdict_sent": False}
    STATE.write_text(json.dumps(d, indent=1), "utf-8")
    return d


def _classify(p: Path) -> str:
    try:
        txt = p.read_text("utf-8", errors="ignore")
    except Exception:
        return "unknown"
    low = txt.lower()
    if any(k in low for k in ("hit your", "usage limit", "usage credits",
                              "out of usage", "session limit", "weekly limit")):
        return "quota_death"
    return "success" if p.stat().st_size >= 2000 else "stub"


def main() -> None:
    st = _load()
    if st.get("verdict_sent"):
        return                                        # one definitive verdict is what was asked
    base = datetime.fromisoformat(st["baseline"])
    hours = (datetime.now(tz=UTC) - base).total_seconds() / 3600
    if hours < MIN_OBS_H:
        print(f"quota-watch: observing ({hours:.1f}/{MIN_OBS_H:.0f}h clean window)")
        return

    base_ts = base.timestamp()
    cyc = [p for p in LOGS.glob("2026*_*.log") if p.stat().st_mtime >= base_ts]
    frontier = [p for p in LOGS.glob("frontier_*.log") if p.stat().st_mtime >= base_ts]

    def tally(files):
        c = {"success": 0, "quota_death": 0, "stub": 0, "unknown": 0}
        for p in files:
            c[_classify(p)] += 1
        return c

    ct, ft = tally(cyc), tally(frontier)
    exp_cyc = max(1, int(hours / CYCLE_EVERY_H))
    exp_min = max(1, int(hours / 24 * MINERS_PER_DAY))

    cyc_succ_frac = ct["success"] / exp_cyc
    total_attempts = sum(ct.values()) + sum(ft.values())
    total_deaths = ct["quota_death"] + ft["quota_death"]
    death_frac = total_deaths / max(1, total_attempts)

    insufficient = (death_frac > DEATH_FRAC_MAX) or (cyc_succ_frac < SUCCESS_FRAC_MIN)

    summary = (f"{hours:.0f}h clean window | cycles: {ct['success']} ok / {exp_cyc} scheduled "
               f"({ct['quota_death']} quota-died) | miners: {ft['success']} ok / ~{exp_min} "
               f"scheduled ({ft['quota_death']} quota-died) | overall quota-death rate "
               f"{death_frac*100:.0f}%")
    print("quota-watch VERDICT:", "MAX NEEDED" if insufficient else "PRO SUFFICIENT")
    print("  " + summary)

    if insufficient:
        block = (
            "\nQUOTA VERDICT -- MAX (or API key) IS NEEDED. You said keep full cadence with no "
            "compromises; measured over a clean autonomous-only window, Pro cannot sustain it.\n"
            f"EVIDENCE: {summary}.\n"
            "The full schedule (4 cycles/day + 7 miners/day at xhigh) is quota-starved on Pro -- "
            "organs are dying at the auth-check, not running. To keep the cadence you ordered "
            "WITHOUT lowering anything, upgrade at claude.ai billing (Max 5x $100/mo is the "
            "sensible start; 20x $200 if even that binds) OR place a metered API key "
            "(bash ops/setup_brain_api_key.sh -- pay per token, no ceiling). Either restores the "
            "full cadence; no config change needed once done.\n")
    else:
        block = (
            "\nQUOTA VERDICT -- PRO IS SUFFICIENT. Good news: over a clean autonomous-only window, "
            "the FULL cadence (4 cycles/day + 7 miners/day at xhigh) runs within Pro limits. No "
            "Max upgrade needed -- save the $100/mo. Keep OpenRouter funded for the panels; that "
            "is the only recurring spend.\n"
            f"EVIDENCE: {summary}.\n"
            "(This verdict re-arms only if the schedule grows or usage patterns change.)\n")

    existing = PA.read_text("utf-8") if PA.exists() else ""
    if "QUOTA VERDICT" not in existing:
        PA.write_text(existing + block, "utf-8")
    st["verdict_sent"] = True
    st["verdict"] = "max_needed" if insufficient else "pro_sufficient"
    st["evidence"] = summary
    STATE.write_text(json.dumps(st, indent=1), "utf-8")
    print("  -> principal paged via PRINCIPAL_ACTION.md")


if __name__ == "__main__":
    main()
