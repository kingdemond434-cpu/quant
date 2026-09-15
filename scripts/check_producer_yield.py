"""EVERY PRODUCER PRODUCES, OR IT IS REPLACED. Names the dead, and names what takes their budget.

THE LAW (principal, 2026-09-15): every single miner, source, seat and proposer must produce. One
that cannot is replaced with an alternative.

WHY THIS IS A DIFFERENT LAW FROM THE TWO NEXT TO IT, because all three sound similar and they
catch different failures:

    check_ground_conversion   a ground must have MACHINERY pointing at the gauntlet.
    check_row_conversion      a mined row must reach a TERMINAL disposition.
    this file                 a producer must have OUTPUT. Machinery that runs, converts, and
                              yields nothing for weeks is not a pipeline, it is a heater.

AND THE THREE VERDICTS ARE NOT THE SAME PROBLEM. Collapsing them is how a desk spends a year
"fixing the miners":

    PRODUCING   output in the window. Nothing to do.
    STARVED     output, but far below its peers. Usually a BUDGET or an input problem, never a
                reason to delete the producer. `alpha_evolution` measured 2026-09-15: it runs,
                it does not crash, and it proposed ONE cell from 72 tests -- because it evolves
                against a book `pf_allocation` reports as 1 funded sleeve. Deleting it would
                have thrown away a working organ for the sin of being fed nothing.
    DEAD        zero output across the whole window. THIS is the one the law is about, and the
                remedy is not another look: it is a named REPLACEMENT that takes the budget.
    UNMEASURED  no artifact records this producer's output at all. A verdict, never a pass, and
                in practice the most common real state of a new organ (L1.28a).

A REPLACEMENT MUST BE NAMED, NOT IMPLIED. "Try something else" is not a remedy; it is the absence
of one. Every producer declared here carries the alternative that inherits its budget when it
dies, so the decision is made once, in advance, by whoever understood the producer -- and not at
3am by whoever happened to notice the zero.

    python scripts/check_producer_yield.py
    python scripts/check_producer_yield.py --window-days 7
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "PRODUCER_YIELD.json"

#: Output below this share of the median producer's output is STARVED rather than healthy. It is
#: a RATIO and not a count on purpose: an absolute floor would condemn a deliberately narrow
#: producer and excuse a broad one that collapsed.
STARVED_FRACTION = 0.05

#: producer -> the alternative that inherits its budget if it is ever declared DEAD. Declared in
#: advance, by intent, so a dead producer has a decision attached to it rather than a question.
REPLACEMENTS: dict[str, str] = {
    "alpha_evolution": "representation_discovery -- same expression search, driven by measured "
                       "representations rather than by a funded book it does not have",
    "plumbing_miner": "microstructure_miner",
    "transition_alpha": "regime_transition sweep inside external_gauntlet",
    "weak_signal_compiler": "combination lane of external_gauntlet",
    "fund_playbook": "institutional_cards -- the same mechanism claims, declared rather than mined",
    "microstructure_miner": "execution_twin markout study",
    "style_premia_sweep": "cross_sectional family sweep",
    "cross_asset_graph": "asia_transmission -- economically declared chains at the CAUSAL_ROLE bar",
    "anomaly_factory": "external_gauntlet exploration floor",
    "tail_alpha_search": "drawdown_conditional family sweep",
    "survivor_distiller": "survivor_neighbourhood",
    "factor_model_coevolution": "residual_factors",
    "deep_forest_miner": "asia_plane -- the hard-data half, where the number is the observation",
    "asia_plane": "deep_forest_miner -- the practitioner half; each is the other's fallback",
    "asia_transmission": "cross_asset_graph",
    # The eight seats measured DEAD on 2026-09-15. Each gets a named inheritor rather than a
    # question mark: three of them are MQL5 sub-crawlers whose work the surviving MQL5 seats
    # already do, and the rest have a live organ covering the same ground.
    "brain": "deepening_worker -- the same LLM reasoning, on the queue rather than freeform",
    "cohorts": "cohort_independence in libs/research",
    "fxmerge": "fxblue -- the same public MT4/MT5 account statistics, from a live route",
    "mql5_catalog": "mql5_signals -- the catalogue is a crawl of what the signals seat already reads",
    "mql5_prospector": "mql5_survivors -- survivorship-aware and still writing",
    "mql5_reputation": "mql5_survivors -- reputation is one of its phenotypes",
    "plumbing": "plumbing_miner (the proposer), which is the organ this seat fed",
    "scheduled_chatgpt": "deepseek_cycle -- the seat that is actually donating today",
}


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _seat_output(window_days: float) -> dict[str, int]:
    """Rows each intelligence seat donated inside the window, from the files themselves.

    Measured off FILE MTIME rather than a row's own stamp: a seat that stopped writing is the
    thing being looked for, and a stale row's internal timestamp would report it as alive.
    """
    cutoff = time.time() - window_days * 86400.0
    out: Counter = Counter()
    for root in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        for pat in ("*/*.json", "*/*.jsonl"):
            for f in glob.glob(str(root / pat)):
                seat = os.path.basename(os.path.dirname(f))
                try:
                    if os.path.getmtime(f) < cutoff:
                        out.setdefault(seat, 0)
                        continue
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        n = sum(1 for _ in fh)
                except OSError:
                    continue
                out[seat] += max(n, 1)
    return dict(out)


def audit(window_days: float = 3.0) -> dict[str, Any]:
    seats = _seat_output(window_days)
    rows: list[dict[str, Any]] = []

    # THE PROPOSERS, from the daily cycle's own list rather than a copy of it. A list that can
    # drift from the runner is a list that reports on organs nobody runs.
    proposers: list[str] = []
    try:
        src = (DESK / "research" / "daily_cycle.py").read_text(encoding="utf-8")
        start = src.find('for name in ("plumbing_miner"')
        if start > 0:
            block = src[start:src.find("):", start)]
            proposers = [t.strip().strip('"') for t in block.split("(", 1)[1].split(",")
                         if t.strip().strip('"').isidentifier()]
    except OSError:
        pass

    # THE SEAT DIRECTORY IS NOT ALWAYS THE MODULE NAME, and a mismatch reads as DEAD. `asia_plane`
    # donates into `data/intelligence/asia/`, so without this it would be reported as producing
    # nothing on the same night it produced 513 cells -- the exact false negative this gate
    # exists to avoid making about anything else.
    for producer, seat in (("asia_plane", "asia"), ("asia_transmission", "asia_transmission"),
                           ("deep_forest_miner", "deep_forest")):
        if producer not in seats and seat in seats:
            seats[producer] = seats[seat]

    universe = list(seats.values())
    median = sorted(universe)[len(universe) // 2] if universe else 0

    for name in sorted(set(proposers) | set(seats) | set(REPLACEMENTS)):
        n = seats.get(name)
        rec: dict[str, Any] = {"producer": name, "rows_in_window": n,
                               "window_days": window_days}
        if n is None:
            rec.update({"verdict": "UNMEASURED",
                        "why": ("no intelligence seat records this producer's output. It may "
                                "write elsewhere, or it may write nowhere -- and those are not "
                                "the same thing, so neither is assumed.")})
        elif n == 0:
            rec.update({"verdict": "DEAD",
                        "why": f"zero rows in {window_days:g} day(s)",
                        "replacement": REPLACEMENTS.get(name,
                                                        "NONE DECLARED -- a dead producer with "
                                                        "no named alternative is an open "
                                                        "decision, which is the defect")})
        elif median and n < median * STARVED_FRACTION:
            rec.update({"verdict": "STARVED",
                        "why": (f"{n} row(s) against a median of {median}. A budget or input "
                                f"problem, NOT a reason to replace the producer.")})
        else:
            rec["verdict"] = "PRODUCING"
        rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    dead = [r for r in rows if r["verdict"] == "DEAD"]
    undeclared = [r for r in dead if "NONE DECLARED" in str(r.get("replacement"))]
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY PRODUCER PRODUCES, OR IT IS REPLACED BY A NAMED ALTERNATIVE. Zero output "
                "is DEAD and carries a replacement; low output is STARVED and carries a budget "
                "question; no artifact is UNMEASURED and carries neither."),
        "window_days": window_days,
        "median_rows": median,
        "n_producers": len(rows),
        "census": dict(census),
        "dead_without_a_declared_replacement": undeclared,
        "producers": sorted(rows, key=lambda r: (r["verdict"], -(r["rows_in_window"] or 0))),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window-days", type=float, default=3.0)
    args = ap.parse_args(argv)

    doc = audit(window_days=args.window_days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"producer yield: {doc['n_producers']} producer(s) over {args.window_days:g}d -> "
          f"{doc['census']}   (median {doc['median_rows']} rows)")
    for v in ("DEAD", "STARVED", "UNMEASURED"):
        rs = [r for r in doc["producers"] if r["verdict"] == v]
        if not rs:
            continue
        print(f"\n  {v} {len(rs)}:")
        for r in rs[:12]:
            tail = (f" -> {str(r.get('replacement'))[:60]}" if v == "DEAD"
                    else f"  {str(r.get('why'))[:60]}")
            print(f"    {str(r['producer'])[:26]:26} {r['rows_in_window']!s:>7}{tail}")
    print(f"  -> {OUT}")
    # A dead producer with NO declared alternative is the fatal state: the law says replace, and
    # there is nothing to replace it with.
    return 1 if doc["dead_without_a_declared_replacement"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
