#!/usr/bin/env python3
"""FENCE: the E8 scheduled-release fence is WIRED, its calendar can SEE, and its pass REPORTED.

WHY (patch e8_news_fence/v1, 2026-10-29). `calendar_us.blackout` existed for weeks while no live
code imported it, so the 10-02 12:30Z print gapped an E8 gold position 1.23R through its stop with
the rail "built" and idle. This goes RED on the states in which the fence silently protects
nothing:

  * UNWIRED  -- prop/e8_gold.py no longer imports mt5desk.news_fence or calls `verdict`;
  * FLAG     -- data/E8_NEWS_FENCE.json exists but is unreadable or malformed (it reads OFF);
  * BLIND    -- the fence is ON and the calendar refuses this year or holds no date for a
                monthly tier-1 family (CPI, PPI, PCE, GDP, NFP) in this or next WHOLE month: a gap is a
                release the fence cannot see, never a quiet month;
  * SILENT   -- the lane's last completed (status OK) report, under 1h old, carries no
                `news_fence` verdict, i.e. a pass ran the old code (NO_BARS / a failed pass
                return before the fence is asked and are not SILENT);
  * FAILED OPEN -- that report's verdict carries an `error`: the fence could not be asked and
                the pass ran unfenced.

With the fence OFF a calendar gap is UNMEASURED (printed, exit 0): the shadow journal still runs
and the gap is published, but nothing is being relied on. No report on this host is UNMEASURED.

    python scripts/check_news_fence_liveness.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LANE = DESK / "prop" / "e8_gold.py"
REPORT = DESK / "reports" / "E8_GOLD.json"
REPORT_MAX_AGE_H = 1.0


def assess(*, today: date | None = None, lane: Path = LANE, report: Path = REPORT,
           flag: Path | None = None) -> dict[str, Any]:
    from mt5desk import news_fence as nf

    red: list[str] = []
    unmeasured: list[str] = []
    day = today or datetime.now(tz=UTC).date()
    try:
        src = lane.read_text("utf-8")
    except OSError as exc:
        src = ""
        red.append(f"UNWIRED: {lane.name} unreadable ({exc})")
    if src and not ("news_fence as _nf" in src and "_nf.verdict(" in src):
        red.append(f"UNWIRED: {lane.name} does not import mt5desk.news_fence / call verdict")
    fp = nf.FLAG if flag is None else flag
    enabled, pre, post, fwhy = nf.read_flag(fp)
    if fp.exists() and ("unreadable" in fwhy or "malformed" in fwhy):
        red.append(f"FLAG: {fwhy}")
    nxt = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
    end = (nxt + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    gaps = nf.uncovered_families(day.replace(day=1), end)
    if gaps:
        msg = f"calendar blind to {', '.join(gaps)}"
        (red if enabled else unmeasured).append(("BLIND: " if enabled else "") + msg)
    if report.exists():
        try:
            doc = json.loads(report.read_text("utf-8"))
            at = datetime.fromisoformat(str(doc.get("at")))
            age_h = (datetime.now(tz=UTC) - at).total_seconds() / 3600.0
            fresh = age_h <= REPORT_MAX_AGE_H
            # A NO_BARS or failed pass returns before the fence is asked: not SILENT (v2).
            if fresh and doc.get("status") == "OK" and "news_fence" not in doc:
                red.append(f"SILENT: {report.name} ({age_h:.2f}h old) has no news_fence verdict")
            err = (doc.get("news_fence") or {}).get("error") if fresh else None
            if err:
                red.append(f"FAILED OPEN: the lane's last pass could not ask the fence ({err})")
        except (OSError, ValueError, TypeError) as exc:
            unmeasured.append(f"{report.name} unreadable ({type(exc).__name__})")
    else:
        unmeasured.append(f"no {report.name} on this host: the lane's pass is not observable")
    verdict = "RED" if red else ("UNMEASURED" if unmeasured else "GREEN")
    return {"verdict": verdict, "enabled": enabled, "pre_min": pre, "post_min": post,
            "flag": fwhy, "red": red, "unmeasured": unmeasured, "calendar_gaps": list(gaps)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = assess()
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"NEWS FENCE {out['verdict']}  enabled={out['enabled']} "
              f"-{out['pre_min']}/+{out['post_min']} min")
        for line in out["red"]:
            print(f"  RED  {line}")
        for line in out["unmeasured"]:
            print(f"  UNMEASURED  {line}")
    return 1 if out["red"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
