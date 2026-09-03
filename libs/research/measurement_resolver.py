"""THE resolver: what can this desk actually measure for a hypothesis, and may it attribute?

WHY A RESOLVER AND NOT JUST A TABLE. `measurement.py` already owns the CLASSES (DIRECT,
VALIDATED_PROXY, HEURISTIC_PROXY, UNMEASURABLE), the contract shape and the attribution rule --
and it answers for events already written into `GENERIC_CONTRACTS` / `EDGE_QUEUE_CONTRACTS`. That
is exactly the easy half. The hard half is a hypothesis whose event is NOT in the table, which is
every hypothesis a miner, a crawler or an LLM has ever proposed, and there the desk had no answer
at all. No answer is where guessing lives: something downstream picks a plausible observable, the
cell runs, and a number comes back that nobody can attribute to the mechanism it claims.

THE RULE THIS ENFORCES. A hypothesis names an observable it needs. Either the desk HOLDS that
observable, holds a defensible stand-in, holds a loose one, or holds nothing -- and those are four
different verdicts, not one. Only the first two may update belief about the mechanism
(`MIN_ATTRIBUTABLE`); the third may EXPLORE under its own label; the fourth does not run.

REFUSAL IS THE DEFAULT, AND THAT IS THE POINT (L1.28a). An unrecognised observable resolves to
UNMEASURABLE, not to the nearest price series. This desk has measured what the other choice costs:
`family_carry` returned [] for every symbol for the life of the desk because a reader looked for
`*.json` where the producer wrote `*.parquet`, and the gate report said "0 daily observations" --
which reads as a mechanism that rarely fires rather than as a reader that never opened a file.
A resolver that guesses produces exactly that shape, with a mechanism name attached to it.

NO SECOND STANDARD. Classes, contract and the attribution threshold are IMPORTED from
`measurement`; nothing here re-defines them. This adds resolution, not policy.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from libs.research.measurement import (
    CLASSES,
    MIN_ATTRIBUTABLE,
    MeasurementContract,
    contract_for,
)

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"

#: Observables the desk holds directly from its own H1 bars. Anything derivable from OHLCV by
#: arithmetic alone is DIRECT: no second feed, no vendor, no point-in-time hazard beyond the bar.
_PRICE_NATIVE = (
    "return", "close", "open", "high", "low", "volume", "range", "gap", "volatility",
    "realised_vol", "realized_vol", "atr", "drawdown", "momentum", "zscore", "quantile",
    "session", "hour", "weekday", "month", "spread_high_low",
)

#: Observables the desk holds because it RECORDS them, each with the artifact that proves it.
#: A claim here is checked against the filesystem, never assumed -- an entry whose file is absent
#: resolves UNMEASURABLE, which is how a retired feed stops silently certifying things.
_RECORDED: dict[str, tuple[str, str]] = {
    "swap": ("data/intelligence/broker_swaps", "broker swap tables, per symbol per side, dated"),
    "carry": ("data/intelligence/broker_swaps", "carry IS the swap differential"),
    "calendar": ("data/intelligence/ff_calendar_vintage", "point-in-time economic calendar"),
    "event_time": ("data/intelligence/ff_calendar_vintage", "scheduled release timestamps"),
    "positioning": ("data/intelligence/cot", "CFTC Commitments of Traders, weekly, dated"),
    "cot": ("data/intelligence/cot", "CFTC COT"),
    "macro": ("data/macro_state.json", "macro state snapshot"),
    "regime": ("data/regime_state.json", "the desk's own regime labels"),
    "tick": ("moat", "the desk's own recorded tick tape"),
    "spread": ("moat", "recorded spread from the desk's own tape"),
    "orderflow": ("moat", "recorded tape"),
}

#: Observables that are REAL but that this desk does not hold. Named explicitly so the verdict
#: says WHY rather than "unknown" -- a hypothesis about options hedging is not badly worded, it is
#: unmeasurable here, and the difference tells the research loop whether to acquire data or drop it.
_KNOWN_ABSENT: dict[str, str] = {
    "options": "no options chain, greeks or dealer-gamma feed on this desk",
    "gamma": "no dealer positioning feed",
    "dealer": "no dealer positioning feed",
    "order_book": "no L2 book for MT5 instruments (the moat tape is trades, not depth)",
    "depth": "no L2 depth for MT5 instruments",
    "flow": "no client-flow or internalisation feed",
    "benchmark_flow": "no index-fund or benchmark rebalancing flow feed",
    "fixing": "no WM/R or ECB fixing print feed at fixing granularity",
    "sentiment": "no licensed sentiment feed; crawler prose is not a measurement",
    "news": "no timestamped machine-readable news feed with point-in-time guarantees",
    "earnings": "no per-instrument earnings feed for the CFD universe",
    "short_interest": "no short-interest feed",
    "etf": "no ETF creation/redemption feed",
}


@dataclass(frozen=True)
class Resolution:
    """What the desk can measure for one hypothesis, and what that permits."""

    mechanism: str
    required_observable: str
    resolved_observable: str
    measurement_class: str
    why: str
    evidence: str = ""
    contract: MeasurementContract | None = None
    unmet: tuple[str, ...] = field(default_factory=tuple)

    @property
    def may_run(self) -> bool:
        return self.measurement_class != "UNMEASURABLE"

    @property
    def attribution_allowed(self) -> bool:
        return CLASSES.index(self.measurement_class) >= CLASSES.index(MIN_ATTRIBUTABLE)

    def as_record(self) -> dict[str, Any]:
        return {
            "mechanism": self.mechanism,
            "required_observable": self.required_observable,
            "resolved_observable": self.resolved_observable,
            "measurement_class": self.measurement_class,
            "may_run": self.may_run,
            "attribution_allowed": self.attribution_allowed,
            "why": self.why,
            "evidence": self.evidence,
            "unmet": list(self.unmet),
        }


@lru_cache(maxsize=1)
def _holdings() -> dict[str, bool]:
    """Which recorded observables actually exist on disk RIGHT NOW.

    Checked, never assumed. A feed that was retired, or a path that moved, must make its
    observable UNMEASURABLE rather than keep certifying hypotheses from a table entry.
    """
    out: dict[str, bool] = {}
    for key, (rel, _why) in _RECORDED.items():
        if rel == "moat":
            out[key] = (_DESK / "moat").exists()
            continue
        p = _DESK / rel
        out[key] = p.exists() and (not p.is_dir() or any(p.iterdir()))
    return out


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9_]+", str(text or "").lower()) if t]


def resolve(mechanism: str, required_observable: str = "",
            *, event: str = "", proposed_observable: str = "") -> Resolution:
    """Resolve ONE hypothesis to a measurement class. Refuses rather than guesses.

    `mechanism` is the causal claim; `required_observable` is what it needs measured. `event` is
    an optional key into the existing contract tables -- when it hits, that contract is returned
    unchanged, because a hand-classified contract beats inference every time and there must be
    exactly one answer per event.
    """
    need = required_observable or proposed_observable or mechanism

    # 1. A hand-written contract is authoritative. One event, one answer.
    if event:
        c = contract_for(event)
        if c is not None:
            return Resolution(
                mechanism=c.mechanism, required_observable=c.required_observable,
                resolved_observable=c.actual_observable, measurement_class=c.measurement_class,
                why=c.verdict(), evidence=f"hand-written contract for event {event!r}",
                contract=c)

    toks = set(_tokens(need)) | set(_tokens(mechanism))

    # 2. Named-absent beats everything else: say WHY, so the loop can choose to acquire data.
    for key, why in _KNOWN_ABSENT.items():
        if key in toks:
            return Resolution(
                mechanism=mechanism, required_observable=need, resolved_observable="",
                measurement_class="UNMEASURABLE",
                why=(f"UNMEASURABLE: {need!r} needs {key!r} and {why}. Running a price proxy "
                     f"under this mechanism's name would test something else."),
                evidence="named-absent observable", unmet=(key,))

    # 3. Recorded observables -- but only if the artifact is on disk.
    have = _holdings()
    for key, (rel, why) in _RECORDED.items():
        if key not in toks:
            continue
        if have.get(key):
            return Resolution(
                mechanism=mechanism, required_observable=need, resolved_observable=key,
                measurement_class="DIRECT",
                why=f"DIRECT: {why}; the desk records it and the artifact is present.",
                evidence=rel)
        return Resolution(
            mechanism=mechanism, required_observable=need, resolved_observable="",
            measurement_class="UNMEASURABLE",
            why=(f"UNMEASURABLE: {need!r} needs {key!r}, which this desk is supposed to record "
                 f"at {rel} -- and that artifact is ABSENT. A missing feed is not a null result."),
            evidence=rel, unmet=(key,))

    # 4. Price-native: arithmetic on bars the desk already holds.
    for key in _PRICE_NATIVE:
        if key in toks:
            return Resolution(
                mechanism=mechanism, required_observable=need, resolved_observable=key,
                measurement_class="DIRECT",
                why=f"DIRECT: {key!r} is arithmetic on H1 bars this desk holds.",
                evidence="H1 bars")

    # 5. Nothing matched. THIS IS A REFUSAL, NOT A FALLBACK.
    return Resolution(
        mechanism=mechanism, required_observable=need, resolved_observable="",
        measurement_class="UNMEASURABLE",
        why=(f"UNMEASURABLE: no observable on this desk resolves {need!r}. Naming one would be a "
             f"guess, and a guessed observable produces a number attributed to a mechanism it "
             f"never measured (L1.28a)."),
        evidence="no match in price-native, recorded, or named-absent observables")


def audit_holdings() -> dict[str, Any]:
    """What the resolver believes the desk holds, and what is missing. For the health fences."""
    have = _holdings()
    return {
        "recorded_present": sorted(k for k, v in have.items() if v),
        "recorded_absent": sorted(k for k, v in have.items() if not v),
        "price_native": sorted(_PRICE_NATIVE),
        "known_absent": sorted(_KNOWN_ABSENT),
        "note": ("Presence is checked on disk at call time. An absent recorded observable makes "
                 "its hypotheses UNMEASURABLE rather than silently proxied."),
    }


if __name__ == "__main__":
    print(json.dumps(audit_holdings(), indent=1))
