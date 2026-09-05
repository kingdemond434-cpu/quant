"""Research coordinates that name an ECONOMIC CLAIM, not a formula.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    "Benchmark flow x London x abnormal magnitude x reversal x 15m"
    instead of
    "RSI(14) < 30"

The desk's search currently enumerates families and parameters. `discovered` alone emitted 10,624
candidates for 7 certificates -- 0.07% -- because a parameter sweep can generate unlimited
variations of the same idea and nothing in the coordinate system notices they are the same idea.
A family label is not a mechanism, and a parameter grid is not a hypothesis space.

A semantic coordinate fixes that by construction: two cells differ only if they make DIFFERENT
ECONOMIC CLAIMS. `EMA breakout` and `Donchian breakout` occupy one coordinate because they assert
the same thing about the same participants; `benchmark_flow x london x reversal` and
`options_hedging x us_close x continuation` occupy two, because they name different payers, times
and directions.

WHY THE FIVE AXES ARE THESE FIVE. Each answers a question a mechanism must answer to be testable:

    EVENT      what happens? -- the thing that creates the opportunity
    CONTEXT    when/where? -- the state in which it happens
    QUALITY    how is it measured? -- the observable that scales it
    DIRECTION  what should price do? -- the falsifiable prediction
    OUTPUT     over what horizon? -- the window the claim is about

Drop any one and the coordinate stops being falsifiable. Without DIRECTION there is no
prediction; without OUTPUT the claim cannot be wrong at any particular time; without QUALITY
there is nothing to condition on and the cell degenerates into "sometimes this happens".

REGIONS, NOT POINTS. `coverage()` reports attempts per REGION rather than per cell, because the
space is 11 x 15 x 8 x 6 x 6 = 47,520 cells and no desk tests 47,520 things. A region is an
(event, direction) pair -- the two axes that carry the economic claim -- and its neighbours are
the same claim under different conditioning, which is what a search should explore next.

BARREN REQUIRES EVIDENCE (LAWS L1.51). A region with fewer than `MIN_ATTEMPTS_TO_CALL_BARREN`
attempts is UNTESTED, never barren, and `coverage` says so in words. This desk has already
labelled seven mechanisms "confidently barren" on evidence gathered through a validator that was
itself broken; the same mistake at coordinate level would write off whole regions of economics.
"""
from __future__ import annotations

import itertools
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: WHAT HAPPENS. Every entry names a participant under constraint -- someone who must trade for a
#: reason that is not a forecast. That is the only kind of event that pays a premium repeatedly,
#: because it is the only kind arbitrage cannot compete away: the payer is not choosing.
EVENTS = (
    "liquidity_shock", "benchmark_flow", "macro_release", "session_transition",
    "options_hedging", "forced_deleveraging", "inventory_rebalance", "volatility_shock",
    "carry_change", "cross_market_move", "positioning_extreme",
)

#: WHEN AND WHERE. Sessions are named explicitly because this desk's mechanisms are overwhelmingly
#: session-bound and a coordinate that cannot say "London" cannot express most of them.
CONTEXTS = (
    "high_vol", "low_vol", "high_liquidity", "low_liquidity",
    "asia", "london", "new_york", "overlap",
    "trend", "range", "pre_event", "post_event", "month_end", "risk_on", "risk_off",
    # A HYPOTHESIS THAT NAMES NO SESSION IS A CLAIM ABOUT EVERY BAR, and until this value
    # existed the compiler had to choose between guessing a session the proposal never named
    # and refusing it outright. 240 proposals were refused for exactly that on 2026-09-04.
    # This is a real region, not a null: it is the unconditioned test of the mechanism.
    "unconditioned",
)

#: HOW IT IS MEASURED. The observable that scales the event -- what makes a big instance different
#: from a small one. Without this the cell has no conditioning variable and cannot be a test.
QUALITIES = (
    "magnitude", "persistence", "acceleration", "surprise",
    "dispersion", "imbalance", "failed_continuation", "cross_market_confirmation",
)

#: THE FALSIFIABLE PREDICTION. `continuation` and `reversal` of the SAME event are different
#: hypotheses about the same mechanism and must not share a coordinate -- one of them is wrong.
DIRECTIONS = (
    "continuation", "reversal", "convergence", "divergence",
    "volatility_expansion", "volatility_compression",
)

#: THE HORIZON THE CLAIM IS ABOUT. A mechanism that works at 15m and not at daily is not a weaker
#: version of the same finding; it is a different finding about a different decay rate.
OUTPUTS = ("1m", "5m", "15m", "1h", "4h", "daily")

#: Below this many attempts a region is UNTESTED, never barren (LAWS L1.51: "exhausted" requires
#: per-axis evidence). Twenty is the same floor the forward verdict uses for effective evidence,
#: kept identical so "enough to conclude" means one thing across the desk.
MIN_ATTEMPTS_TO_CALL_BARREN = 20


@dataclass(frozen=True)
class Coordinate:
    """One research coordinate. Frozen: a coordinate that mutates is not a record of anything."""

    event: str
    context: str
    quality: str
    direction: str
    output: str

    def __post_init__(self) -> None:
        for name, value, allowed in (
            ("event", self.event, EVENTS), ("context", self.context, CONTEXTS),
            ("quality", self.quality, QUALITIES), ("direction", self.direction, DIRECTIONS),
            ("output", self.output, OUTPUTS),
        ):
            if value not in allowed:
                raise ValueError(
                    f"{name}={value!r} is not in the semantic space. Adding an axis value is a "
                    f"deliberate widening of what this desk can express, not a typo to absorb "
                    f"silently -- extend the tuple in semantic_space.py and say why.")

    @property
    def region(self) -> tuple[str, str]:
        """(event, direction) -- the pair carrying the economic claim itself."""
        return (self.event, self.direction)

    def key(self) -> str:
        return f"{self.event}|{self.context}|{self.quality}|{self.direction}|{self.output}"

    def claim(self) -> str:
        """The coordinate as an English sentence.

        If this does not read as a falsifiable claim, the coordinate is not one.
        """
        return (f"When {self.event.replace('_', ' ')} occurs in a {self.context.replace('_', ' ')} "
                f"state, larger {self.quality.replace('_', ' ')} predicts "
                f"{self.direction.replace('_', ' ')} over {self.output}.")


def size() -> int:
    return len(EVENTS) * len(CONTEXTS) * len(QUALITIES) * len(DIRECTIONS) * len(OUTPUTS)


def regions() -> list[tuple[str, str]]:
    return [(e, d) for e in EVENTS for d in DIRECTIONS]


def enumerate_region(event: str, direction: str) -> list[Coordinate]:
    """Every coordinate making this economic claim, under all conditionings."""
    return [Coordinate(event, c, q, direction, o)
            for c, q, o in itertools.product(CONTEXTS, QUALITIES, OUTPUTS)]


def coverage(attempts: dict[str, int]) -> dict[str, Any]:
    """Attempts per region, and which regions the desk may NOT call barren.

    `attempts` maps a Coordinate key to how many trials it has received. Regions with too few
    attempts are reported as UNTESTED with the number they would need -- the distinction between
    "we looked and found nothing" and "we never looked" is the whole point, and collapsing it is
    how a desk convinces itself a mechanism is dead.
    """
    per_region: Counter[tuple[str, str]] = Counter()
    for k, n in attempts.items():
        parts = k.split("|")
        if len(parts) == 5:
            per_region[(parts[0], parts[3])] += n

    all_regions = regions()
    tested = {r: per_region.get(r, 0) for r in all_regions}
    untouched = [r for r, n in tested.items() if n == 0]
    untested = [r for r, n in tested.items() if 0 < n < MIN_ATTEMPTS_TO_CALL_BARREN]
    conclusive = [r for r, n in tested.items() if n >= MIN_ATTEMPTS_TO_CALL_BARREN]
    return {
        "space_size": size(),
        "regions": len(all_regions),
        "regions_never_touched": len(untouched),
        "regions_untested": len(untested),
        "regions_with_conclusive_evidence": len(conclusive),
        "coverage_pct": round(100.0 * len(conclusive) / len(all_regions), 2) if all_regions else 0,
        "never_touched": [f"{e}|{d}" for e, d in sorted(untouched)][:40],
        "note": (f"a region under {MIN_ATTEMPTS_TO_CALL_BARREN} attempts is UNTESTED, never "
                 f"barren (LAWS L1.51); absence of a finding is not a finding"),
    }


def load_attempts(path: Path) -> dict[str, int]:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): int(v) for k, v in (d.get("attempts") or {}).items()}
