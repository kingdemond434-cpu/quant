"""WHICH CHART THIS RESEARCH RUN HUNTS ON -- allocated, and deliberately away from H1.

THE BOTTLENECK THIS EXISTS FOR, measured 2026-09-15. The desk holds 56 certificates and ALL 56
are H1. `frontier_ceo` names the constraint in its own binding-constraint line: "n_eff and AXIS
COUNT, never sleeve count ... exactly ONE of 76 (chart, session) axes has ever produced a
certificate." Sixty-five live sleeves behave as 5.6 independent bets, and a thirteenth FX pair on
H1 is not a fourteenth bet -- a different CHART is, because a five-minute mean reversion and a
daily gap fade are driven by different participants at different horizons.

IT IS NOT A DATA PROBLEM. The universe carries near-equal coverage on every rung of the ladder:
H1 299 parquets, D1 250, H4 248, M15 248, M30 248, M5 248, M1 236. `orthogonal_sweep` already
interleaves its (symbol, chart) pairs evenly -- measured, its first 200 pairs are 16% H1, 14.5%
D1, 14.5% H4. The ladder works.

IT IS A GENERATION PROBLEM, AND IT IS CONCENTRATED IN ONE PRODUCER. Of the 26,925 docket rows:

    edge_search    19,996 rows   100% H1     <- 74% of every candidate the desk has proposed
    session sweep   2,488 rows    89% non-H1 <- the only real multi-chart producer
    orthogonal      1,960 rows     1% non-H1
    miner           1,292 rows   100% H1
    breadth           814 rows   100% H1

`edge_search` hard-codes `{symbol}_H1.parquet`. It cannot propose a non-H1 cell, so three
quarters of the funnel can only ever feed the one axis that is already saturated.

HOW THE WEIGHTS ARE CHOSEN, and why this is not just "prefer what we have not tried". Effort goes
where the desk is most IGNORANT, measured as the share of candidates each chart already holds:
a chart with 74% of the docket has had its question asked, and a chart with 1% has not. The
weight is inverse to that share, so the allocation self-corrects as coverage evens out and stops
favouring any chart once the docket is balanced. H1 additionally carries an explicit floor rather
than a ban -- it is the reference chart, every existing certificate and clock lives there, and
starving it would trade one monoculture for another.

NOTHING HERE TOUCHES CAPITAL. This allocates RESEARCH effort -- which chart a hunting run reads.
The principal's standing order that aggressiveness is never reduced governs the book; it does not
require the desk to keep asking the same question. Reducing H1's share of HUNTING while the live
H1 sleeves trade exactly as they do is the opposite of a smaller book: it is the only way to find
the independent bets that let the same heat buy more n_eff.

    python desks/mt5/research/chart_allocator.py          # report the allocation
    python desks/mt5/research/chart_allocator.py --pick   # print one chart, for a shell caller

Artifact: desks/mt5/reports/CHART_ALLOCATION.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe"
OUT = DESK / "reports" / "CHART_ALLOCATION.json"

#: The reference chart. Every certificate, clock and cache entry the desk already holds is H1, and
#: `frontier_identity` spells H1 by ABSENCE -- so H1 is never removed, only rebalanced.
REFERENCE = "H1"

#: H1's guaranteed share of hunting effort, however saturated the docket gets. A floor rather than
#: a cap on the others: the live book is H1 and its ground must keep being re-asked as the market
#: moves. 0.15 leaves 85% for the seventy-five axes that have never produced a certificate.
H1_FLOOR = float(os.environ.get("CHART_H1_FLOOR", "0.15"))

#: H1's share is also CAPPED, because the inverse-coverage rule alone would still hand it a large
#: slice on the day coverage evens out. This is the "reduce H1 heavily" instruction expressed as a
#: number that stops binding once the desk is balanced.
H1_CEILING = float(os.environ.get("CHART_H1_CEILING", "0.25"))

#: Charts with no parquet coverage are not allocated -- an allocation to ground the desk cannot
#: read is effort thrown away, and it would hide the real coverage gap behind a busy log.
MIN_PARQUETS = int(os.environ.get("CHART_MIN_PARQUETS", "20"))


def coverage() -> dict[str, int]:
    """Parquet files per chart -- the ground the desk can actually read."""
    c: Counter[str] = Counter()
    for p in UNIVERSE.glob("*_*.parquet"):
        c[p.stem.rsplit("_", 1)[-1].upper()] += 1
    return dict(c)


def docket_share() -> dict[str, int]:
    """Candidates per chart already proposed -- how much each question has been asked."""
    c: Counter[str] = Counter()
    try:
        rows = json.loads(DOCKET.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        c[str((r.get("params") or {}).get("timeframe") or REFERENCE).upper()] += 1
    return dict(c)


def weights() -> tuple[dict[str, float], str]:
    """Hunting effort per chart, and the reason -- inverse to how much each is already asked."""
    cov = {k: v for k, v in coverage().items() if v >= MIN_PARQUETS}
    if not cov:
        return {REFERENCE: 1.0}, (f"no chart has {MIN_PARQUETS}+ parquets; hunting stays on "
                                  f"{REFERENCE}")
    have = docket_share()
    total = sum(have.values()) or 1
    # INVERSE COVERAGE, SMOOTHED. `1 - share` would hand an unexplored chart the same weight as
    # one at 5%; the +1 smoothing keeps a chart that has been asked a little from being treated
    # as if it had never been asked at all, and cannot divide by zero on a fresh docket.
    raw = {tf: 1.0 / (1.0 + (have.get(tf, 0) / total) * len(cov)) for tf in cov}
    s = sum(raw.values()) or 1.0
    w = {k: v / s for k, v in raw.items()}

    # H1 IS BOUNDED ON BOTH SIDES, and the ceiling is the instruction this module was asked for.
    h1 = w.get(REFERENCE, 0.0)
    target = min(max(h1, H1_FLOOR), H1_CEILING)
    if REFERENCE in w and abs(target - h1) > 1e-9:
        rest = 1.0 - target
        others = {k: v for k, v in w.items() if k != REFERENCE}
        so = sum(others.values()) or 1.0
        w = {REFERENCE: target, **{k: v / so * rest for k, v in others.items()}}
    why = (f"inverse docket coverage over {len(cov)} chart(s); {REFERENCE} held to "
           f"[{H1_FLOOR:.0%}, {H1_CEILING:.0%}] and given {w.get(REFERENCE, 0):.0%}")
    return w, why


def pick(seed: int | None = None) -> tuple[str, str]:
    """One chart for this run, sampled from the weights. Sampling, not round-robin, so parallel
    runs do not all land on the same chart and a truncated schedule still covers the ladder."""
    w, why = weights()
    # UNSEEDED DRAWS COME FROM THE OS, not the clock. Seeding on `datetime.now()` gives every run
    # started in the same second the SAME chart -- and the schedule starts research runs in
    # parallel, which is exactly when the spread matters most. A caller-supplied seed is honoured
    # so a test can pin the draw.
    rnd = random.Random(seed) if seed is not None else random.SystemRandom()
    keys = sorted(w)
    r, acc = rnd.random(), 0.0
    for k in keys:
        acc += w[k]
        if r <= acc:
            return k, why
    return keys[-1] if keys else REFERENCE, why


def report() -> dict[str, Any]:
    w, why = weights()
    have = docket_share()
    total = sum(have.values()) or 1
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "why": why,
        "h1_floor": H1_FLOOR, "h1_ceiling": H1_CEILING,
        "coverage_parquets": coverage(),
        "docket_rows_per_chart": have,
        "docket_share": {k: round(v / total, 4) for k, v in sorted(have.items())},
        "hunting_weights": {k: round(v, 4) for k, v in sorted(w.items())},
        "rule": (
            "Research effort per chart, inverse to how much of the docket each chart already "
            "holds, with H1 bounded on both sides. This allocates HUNTING, never capital: the "
            "live book is untouched and no sleeve is resized."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pick", action="store_true", help="print one allocated chart and exit")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    if a.pick:
        print(pick(a.seed)[0])
        return 0
    doc = report()
    print(f"chart allocation: {doc['why']}")
    print(f"{'chart':8}{'parquets':>10}{'docket':>9}{'share':>8}{'hunt weight':>13}")
    for tf in sorted(doc["hunting_weights"], key=lambda k: -doc["hunting_weights"][k]):
        print(f"{tf:8}{doc['coverage_parquets'].get(tf, 0):>10}"
              f"{doc['docket_rows_per_chart'].get(tf, 0):>9}"
              f"{doc['docket_share'].get(tf, 0):>8.1%}{doc['hunting_weights'][tf]:>13.1%}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
