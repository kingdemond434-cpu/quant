"""THE FENCE THAT MAKES PLUMBING SILENCE IMPOSSIBLE.

    python scripts/check_plumbing_watchdog.py              # exit 2 on a breach
    python scripts/check_plumbing_watchdog.py --json
    python scripts/check_plumbing_watchdog.py --report-only # measure, never wedge (rc 0)

THE DEFECT CLASS THIS CLOSES. Five plumbing failures were measured on the trading box inside one
day and every one of them was ALREADY BEING REPORTED, correctly, to nothing:

    the adoption task refused the git-writer mutex once an hour for four days,
    the adoption task then expired and vanished from the scheduler,
    72 orphaned workers held 147 GB of commit while every new leg died,
    the recommendation ledger went 11.7 days without a write under a green hourly docket,
    six modules read a report path that no module wrote.

A watchdog alone does not fix that, because a watchdog is just one more thing that can be logged
and ignored. What closes it is a GATE: while `desks/mt5/research/plumbing_watchdog.py` holds an
open defect older than that defect's own escalation window, this fence exits non-zero and the law
gate does not pass. Repairing the plumbing becomes the cheapest way to ship anything else.

AND THE ABSENCE OF THE REPORT IS ITSELF A BREACH. That is the whole point. A watchdog that
stopped running would otherwise be the quietest failure on the desk -- no defects reported,
because nothing reported. So a missing, unreadable or stale `PLUMBING_WATCHDOG.json` fails here
exactly as a real defect does: silence is the failure mode, not the evidence of health.

Registered in `scripts/run_law_gate.py` under `_STATE_FENCES`: it judges LIVE state (the box's
scheduler, its process table, its checkout), so it is meaningless on a clean checkout with no
artifacts and is not asked there.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "PLUMBING_WATCHDOG.json"

#: How old the watchdog's own report may be before the watchdog is itself the defect. It runs
#: every fifteen minutes as MT5-PlumbingWatchdog and hourly as a cycle leg, so two hours is four
#: missed box passes and two missed cycles -- past any ordinary contention, short of a day.
MAX_REPORT_AGE_S = 2 * 3600


def _parse(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def check(report: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The verdict. `breaches` is the list that makes this fence exit non-zero."""
    p = report or REPORT
    t = now or datetime.now(tz=UTC)
    doc: Any = None
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {
            "ok": False, "measured": False,
            "breaches": [{
                "organ": "plumbing_watchdog",
                "check": "watchdog_artifact",
                "age_s": None,
                "why": (f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is absent or "
                        f"unreadable ({type(exc).__name__}). An absent watchdog reports no "
                        f"defects because it reports nothing -- which is the exact silence this "
                        f"organ exists to end, and is therefore a breach and never a pass."),
                "repair": ("python desks/mt5/research/plumbing_watchdog.py --once "
                           "--budget-s 180; if it does not run, MT5-PlumbingWatchdog is the "
                           "task to repair"),
            }],
            "n_defects": None, "at": None,
        }
    if not isinstance(doc, dict):
        return {"ok": False, "measured": False, "n_defects": None, "at": None,
                "breaches": [{"organ": "plumbing_watchdog", "check": "watchdog_artifact",
                              "age_s": None,
                              "why": f"{p} does not hold a watchdog document",
                              "repair": "re-run desks/mt5/research/plumbing_watchdog.py --once"}]}
    at = _parse(str(doc.get("at") or ""))
    age_s = (t - at).total_seconds() if at else None
    breaches: list[dict[str, Any]] = []
    if age_s is None:
        breaches.append({"organ": "plumbing_watchdog", "check": "watchdog_artifact",
                         "age_s": None,
                         "why": f"{p.name} carries no readable `at`, so its freshness is "
                                f"UNMEASURED -- a verdict, never a pass (L1.28a)",
                         "repair": "re-run desks/mt5/research/plumbing_watchdog.py --once"})
    elif age_s > MAX_REPORT_AGE_S:
        breaches.append({"organ": "plumbing_watchdog", "check": "watchdog_artifact",
                         "age_s": int(age_s),
                         "why": (f"the watchdog last ran {age_s / 3600:.1f}h ago, past its "
                                 f"{MAX_REPORT_AGE_S / 3600:.0f}h window. A watchdog that stopped "
                                 f"is the quietest failure on the desk: no defects, because "
                                 f"nothing looked."),
                         "repair": ("Get-ScheduledTask MT5-PlumbingWatchdog -- it runs every "
                                    "15 minutes and is also hourly cycle leg "
                                    "`plumbing_watchdog`")})
    rows = doc.get("defects") or []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("past_escalation_window"):
            continue
        breaches.append({
            "organ": str(r.get("organ")), "check": str(r.get("check")),
            "age_s": int(r.get("age_s") or 0),
            "why": (f"{r.get('organ')} has been broken for "
                    f"{int(r.get('age_s') or 0) / 3600:.1f}h, past the "
                    f"{int(r.get('escalate_after_s') or 0) / 3600:.1f}h escalation window for "
                    f"`{r.get('check')}`: {str(r.get('evidence'))[:400]}"),
            "repair": str(r.get("repair") or ""),
        })
    return {"ok": not breaches, "measured": True, "at": doc.get("at"),
            "age_s": int(age_s) if age_s is not None else None,
            "n_defects": int(doc.get("n_defects") or 0),
            "n_escalated": int(doc.get("n_escalated") or 0),
            "breaches": breaches,
            "rule": ("the law gate does not pass while a plumbing defect is older than its own "
                     "escalation window, and an absent watchdog report is itself such a defect")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="print the verdict and always exit 0 (measurement without the wedge)")
    a = ap.parse_args(argv)
    doc = check()
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"plumbing watchdog fence: ok={doc['ok']} measured={doc['measured']} "
              f"defects={doc['n_defects']} breaches={len(doc['breaches'])} at={doc['at']}")
        for b in doc["breaches"][:25]:
            print(f"  BREACH {b['organ']} ({b['check']}): {str(b['why'])[:220]}")
            if b.get("repair"):
                print(f"         repair: {str(b['repair'])[:200]}")
    if a.report_only or doc["ok"]:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
