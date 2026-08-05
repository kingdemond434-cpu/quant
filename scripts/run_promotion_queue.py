"""PROMOTION QUEUE -- forward slots go to the edges that will EXPIRE first (L1.18a, L1.28a).

THE PRINCIPAL'S CONCERN, stated exactly: the shadow->live process must not be so slow that *"by
the time they reach live the capital is already outgrown its capacity."*

`libs.autodiscovery.validation.capacity_race` has answered "does this edge reach live before the
book outgrows it?" since 2026-07-30 -- and until this script, EVERY CALLER WAS A TEST passing a
hardcoded `validation_days=90`. A mechanism with only test callers is the desk's own named defect
("an orphan is fixed by a caller, not by deletion"), and it meant the race was both un-run and
run against an assumption. This is the caller, and it feeds the race a MEASURED latency.

WHAT IT CHANGES, concretely. Forward slots are capped at MAX_FORWARD_SLOTS=12, because that cap is
what keeps the Holm bar fixed. Slots were filled in whatever order candidates arrived. Ordering by
ARRIVAL is the worst available policy when capacity decays: a long-runway edge loses nothing by
waiting a month, while a short-runway one loses EVERYTHING -- so arrival order systematically
sacrifices exactly the edges that cannot afford to wait. The queue is therefore ordered by EXPIRY,
SHORTEST RUNWAY FIRST.

WHAT IT REFUSES TO DO, and this is the part that keeps it honest. A DOA edge is never rescued by a
shorter clock or a lower bar (L1.6, and L2.8a makes that direction un-amendable). The only honest
accelerants are the two in libs/research/promotion_latency.py:
  * NOT QUEUEING -- give it a slot now rather than later. Free, and this script's whole job.
  * MORE OBSERVATIONS PER DAY -- and ONLY where the P&L is event-driven and the event rate
    genuinely rises. For diffusive (price-change) P&L it is false: drift estimation depends on the
    HORIZON, not the sampling rate, so "accelerating" by sampling faster manufactures a t-stat out
    of oversampling. The accelerant is refused by default.
If neither applies, the edge is recorded STRUCTURALLY-UNREACHABLE at this equity -- an honest
result, not a silent shelving, and it re-tests automatically as the book grows.

    python scripts/run_promotion_queue.py [--json] [--equity USD] [--growth 1.0]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "data/promotion_queue.json"
#: The lab candidate store. Was `data/research_memory.db` until 2026-08-01 (R0079) -- a path
#: NOTHING in this repo has ever written. `_DB.exists()` was therefore always False, this returned
#: [], and the queue reported a structural `n_candidates: 0` on every 6-hourly run while looking
#: perfectly healthy: the READ-WITHOUT-WRITER class (L1.40), which does not crash, it takes the
#: empty branch and reports a plausible zero.
_DB = _ROOT / "data/sor_research.sqlite"


def _candidates() -> list[dict[str, Any]]:
    """SURVIVORS with a capacity. Empty (not fatal) when the lab db is absent -- this box may not
    be the research box, and an empty queue is a fact worth reporting.

    SURVIVORS ONLY, NEVER A FALLBACK TO `all()` (R0079, 2026-08-01). This read
    `store.survivors() or store.all()`, which is a silent substitution the two-stage law forbids:
    the store holds 1,673 candidates and every one is `survived = 0`, so the instant the path above
    was repointed at the real db that `or` would have fed 1,673 GAUNTLET-REJECTED candidates into
    the forward-slot queue as promotion inventory. The bug was invisible for exactly as long as the
    phantom path was, and repointing without removing it would have converted a dormant defect into
    a live phantom-edge factory -- which is why the two land in one commit.

    An empty survivor set is a SUPPLY problem upstream (discovery/gauntlet) and is reported as
    such. Ranking rejects is not a degraded answer to "what should get a forward slot", it is a
    wrong one, and 0 is the honest number.
    """
    if not _DB.exists():
        return []
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        store = CandidateStore(Database(_DB, read_only=True))
        rows = store.survivors()
    except (ImportError, OSError, ValueError, AttributeError, TypeError):
        return []
    out = []
    for c in rows:
        cap = float(getattr(getattr(c, "metrics", None), "capacity_usd", 0.0) or 0.0)
        if cap <= 0:
            continue
        out.append({"id": getattr(c, "id", "?"), "family": getattr(c, "family", "?"),
                    "symbol": getattr(c, "symbol", "?"), "capacity_usd": cap,
                    "status": str(getattr(c, "status", "?"))})
    return out


def _merge_history(derived: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fold the observed forward cohort into the append-only birth record (L1.30, R0113).

    REFUSAL PATH, and it is the whole point: when the cohort could not be derived at all, this
    returns the PRIOR history untouched with `retirement_checked: False`. An unreadable registry
    means "we do not know which clocks are live", never "no clocks are live" -- retiring the whole
    book on a failed import would book twelve deaths and then twelve births on the next good run.
    """
    from libs.research.promotion_history import update

    try:
        prior = json.loads(_OUT.read_text("utf-8"))
    except (OSError, ValueError):
        prior = {}
    previous = prior.get("promotion_history") if isinstance(prior, dict) else None
    previous = previous if isinstance(previous, list) else None

    if derived is None:
        return (previous or []), {
            "rows": len(previous or []), "born_this_run": [], "retired_this_run": [],
            "undated_rows": sum(1 for r in (previous or [])
                                if isinstance(r, dict) and r.get("provenance") == "UNKNOWN"),
            "bootstrap": previous is None, "retirement_checked": False,
            "note": "slot registry unreadable -- history carried forward unchanged, nothing "
                    "retired (an unreadable cohort is unknown, never empty)",
        }
    return update(list(derived.get("slots") or []),
                  complete=bool(derived.get("complete")),
                  now=datetime.now(tz=UTC), previous=previous)


def build(*, equity_usd: float | None = None, growth: float = 1.0) -> dict[str, Any]:
    from libs.autodiscovery.validation import capacity_race, capacity_status
    from libs.research.promotion_latency import measure

    latency = measure()
    cands = _candidates()
    rows: list[dict[str, Any]] = []
    for c in cands:
        cap = float(c["capacity_usd"])
        admission = capacity_status(cap, equity_usd=equity_usd)
        race = capacity_race(cap, validation_days=latency.total_days,
                             equity_usd=equity_usd, growth_rate_annual=growth)
        rows.append({**c, "admission": admission, **race})

    # EXPIRY ORDER, shortest runway first. SUB-VIABLE candidates are excluded from the queue
    # entirely rather than sorted to the back: they fail execution physics at ANY equity, so a slot
    # spent on one buys nothing at any point in the future (L1.18a -- the only genuine capacity
    # kill). OUTGROWN ones are excluded too: the book has already passed them.
    queue = sorted((r for r in rows if r["admission"] == "ADMIT"),
                   key=lambda r: float(r["runway_days"]))

    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
        derived = derive_slots()
        occupied = len(derived.get("slots", []) or [])
        cap_slots = int(MAX_FORWARD_SLOTS)
    except (ImportError, OSError, ValueError, KeyError):
        derived, occupied, cap_slots = None, 0, 12
    free = max(cap_slots - occupied, 0)

    # L1.30 BIRTHS. Merge the observed cohort into the append-only history BEFORE the report is
    # written, because this function's return value is what overwrites the file -- rebuilding the
    # payload without carrying the prior history forward would truncate the record on every run,
    # which is the same defect as never writing it. `previous is None` (key absent) is the
    # bootstrap signal and is deliberately distinct from `[]` (a history that exists and is empty).
    history, hist_summary = _merge_history(derived)

    for i, r in enumerate(queue):
        r["slot_action"] = "ADMIT-NOW" if i < free else f"WAIT (position {i - free + 1} in queue)"

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    admissions: dict[str, int] = {}
    for r in rows:
        admissions[str(r["admission"])] = admissions.get(str(r["admission"]), 0) + 1

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.18a -- the forward-slot queue is ordered by EXPIRY, shortest runway first: a "
               "long-runway edge loses nothing by waiting, a short-runway one loses everything. "
               "A DOA edge is never rescued by a shorter clock or a lower bar (L1.6).",
        "latency": latency.as_dict(),
        "latency_is_measured": latency.fully_measured,
        "slots": {"occupied": occupied, "cap": cap_slots, "free": free},
        "n_candidates": len(cands), "admission_counts": admissions, "race_counts": counts,
        "promotion_history": history,
        "promotion_history_summary": hist_summary,
        "queue": queue,
        "excluded": [r for r in rows if r["admission"] != "ADMIT"],
    }


def main() -> int:
    # L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate. guard() is
    # TTL-cached and pages-but-does-not-block, so a governance fault never silences the queue.
    from libs.ops.lawful import guard as _law_guard
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--equity", type=float, default=None, help="override desk equity (USD)")
    ap.add_argument("--growth", type=float, default=1.0, help="annual growth, 1.0 = 100%%/yr")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    rep = build(equity_usd=args.equity, growth=args.growth)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    lat = rep["latency"]
    print(f"promotion queue | pipeline latency {lat['total_days']}d "
          f"({'measured' if rep['latency_is_measured'] else 'partly estimated'}) | "
          f"slots {rep['slots']['occupied']}/{rep['slots']['cap']} "
          f"({rep['slots']['free']} free)")
    for name, c in lat["components"].items():
        print(f"    {name:11} {c['days']:>6.1f}d  [{c['provenance']}] {c['detail'][:78]}")
    print(f"  candidates {rep['n_candidates']} | admission {rep['admission_counts']} | "
          f"race {rep['race_counts']}")
    h = rep["promotion_history_summary"]
    print(f"  births (L1.30) | {h['rows']} row(s), {h['undated_rows']} undated"
          f"{' [BOOTSTRAP]' if h['bootstrap'] else ''}"
          f" | +{len(h['born_this_run'])} born, -{len(h['retired_this_run'])} retired"
          f"{'' if h['retirement_checked'] else ' (retirement NOT checked: incomplete read)'}")
    for r in rep["queue"][:args.top]:
        print(f"  {r['verdict']:13} {r['slot_action']:26} runway {r['runway_days']:>7.0f}d  "
              f"${r['capacity_usd']:>12,.0f}  {str(r['family'])[:18]:20} {r['symbol']}")
    if not rep["queue"]:
        print("  QUEUE EMPTY -- no ADMIT-status candidate with a positive capacity. That is a "
              "supply problem upstream (discovery/gauntlet), not a queueing one.")
    print(f"-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
