#!/usr/bin/env python3
"""DUTY CYCLE (state fence) -- the desk's mint and judge duty cycles ratchet UP, never down.

The gap this fences is not speed, it is IDLENESS. Measured on the trading box 2026-09-23/24, both
production stages held a demonstrated peak hour and used ~6% and ~8% of it across the day, and the
reason turned out to be a scheduled task whose repetition window had expired: Enabled, a real Last
Run Time, and no next run. Every liveness check in the tree said the judge's clock was fine.

So this fence refuses on exactly the two states that describe that failure:

  * A LANE CLOCK IS DEAD -- a task in the mint or judge lane that is enabled, repeats, and has no
    next run time. That is a stage that will produce nothing until somebody notices.
  * A STAGE FELL BELOW ITS OWN FLOOR -- `desks/mt5/data/duty_cycle_ratchet.json` holds the best
    duty cycle each stage has measured with the market open, and it moves up only.

And on the two that make either claim uncashable: an absent report (a fence that never ran is a
claim the desk cannot cash, L1.49) and a stale one.

UNMEASURED IS NOT A BREACH AND IT IS NOT A PASS. A stage the organ could not measure is reported
as UNMEASURED and does not clear the fence's floor check -- absence never resolves to a clean
verdict (L1.28a) -- but it is not counted as a regression either, because nobody measured one.

    python scripts/check_duty_cycle.py [--json]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "DUTY_CYCLE.json"
RATCHET = DESK / "data" / "duty_cycle_ratchet.json"

#: The report is written by the hourly leg `duty_cycle`. Three clocks of slack, so one missed
#: pass is not a breach and a stopped organ is.
MAX_AGE_S = 3 * 3600


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def check(report: Path | None = None, ratchet: Path | None = None,
          now: float | None = None) -> list[dict[str, str]]:
    rp, fp = Path(report or REPORT), Path(ratchet or RATCHET)
    out: list[dict[str, str]] = []
    doc = _read(rp)
    if not isinstance(doc, dict):
        return [{"check": "ARTIFACT",
                 "why": f"{rp.name} absent or unreadable: the desk's duty cycle is unmeasured, "
                        f"which is never a pass -- run the `duty_cycle` hourly leg"}]
    age = (now or time.time()) - rp.stat().st_mtime
    if age > MAX_AGE_S:
        out.append({"check": "FRESH",
                    "why": f"{rp.name} is {age / 3600:.1f}h old (>{MAX_AGE_S / 3600:.0f}h): the "
                           f"organ that measures idleness has itself stopped"})

    clocks = doc.get("clocks") or {}
    if clocks.get("status") != "MEASURED":
        out.append({"check": "CLOCKS",
                    "why": f"lane clocks are UNMEASURED ({clocks.get('why', 'no reason given')}): "
                           f"a stage whose clock nobody read may already have stopped"})
    for name in clocks.get("dead") or []:
        rec = (clocks.get("tasks") or {}).get(name) or {}
        out.append({"check": "DEAD_CLOCK",
                    "why": f"{name} ({rec.get('lane', 'lane unknown')} lane) is enabled and "
                           f"repeats every {rec.get('every')} but has NO next run time -- its "
                           f"repetition window expired and the stage it drives is idle. Last run "
                           f"{rec.get('last_run')}"})

    floors = ((_read(fp) or {}).get("stages") or {}) if fp.exists() else {}
    closed = bool((doc.get("window") or {}).get("market_closed"))
    for stage, meas in (doc.get("stages") or {}).items():
        cur = meas.get("duty_cycle")
        floor = (floors.get(stage) or {}).get("floor")
        if not isinstance(cur, (int, float)):
            why = meas.get("why") or ("the stage produced nothing, so it has no demonstrated "
                                      "capacity to be a fraction of")
            out.append({"check": "UNMEASURED",
                        "why": f"{stage}: duty cycle is UNMEASURED ({why}) -- an absence, not a "
                               f"zero, and not a pass"})
            continue
        if isinstance(floor, (int, float)) and float(cur) < float(floor) and not closed:
            out.append({"check": "RATCHET",
                        "why": f"{stage}: duty cycle {float(cur):.4f} is below its own floor "
                               f"{float(floor):.4f}. Duty cycle ratchets UP. Something that used "
                               f"to run stopped running -- start at DUTY_CYCLE.json's clocks and "
                               f"hour accounting"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    findings = check()
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=1))
    else:
        print(f"duty cycle: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        for x in findings:
            print(f"  BREACH {x['check']}: {x['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
