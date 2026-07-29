"""HYPOTHESIS_MAX_SPEC components 1, 3 and 6 -- the spec's own build order, minus the fossil.

THE SPEC WAS WRITTEN 2026-07-20 AND FIVE OF ITS SIX COMPONENTS WERE NEVER BUILT. The external
panel named the pattern BUILDER'S FOSSIL and put it against this exact file. That matters more
than usual here because the same panel run measured the consequence: **420 candidates tested,
ZERO survivors**, with every one of them burning full gauntlet compute because component 1 --
"build first, pure efficiency win" -- did not exist.

Three components, chosen because the spec itself makes them one object: #3's mechanism
fingerprint is explicitly reused by #6, and #1 consumes both.

  #1 TIERED PRE-FILTER. A cheap analytical stage before recorder-replay. Its governing rule is
     unusual and is honoured literally: **the pre-filter rejects ONLY on cheap, unambiguous
     evidence -- borderline always escalates.** This looks like the fail-open pattern the desk
     bans everywhere else, and it is the one place where fail-open is correct: the failure being
     guarded against is not "a bad candidate gets through" (the full gauntlet is still there,
     unchanged) but "a real alpha is killed silently by a cheap heuristic". Wasted compute is
     recoverable; a discarded edge is not. So `ESCALATE` is the default branch, and REJECT is
     the branch that must be argued for.

  #3 TRIVIAL-VARIATION BLOCKER. Fingerprint = feature family + signal transform + horizon
     bucket. A rejected mechanism blocks its PARAMETER variations, and a variation re-enters
     only by changing the MECHANISM. The horizon BUCKET is what makes this real: without it,
     "same idea at 13h instead of 12h" is a different fingerprint and the blocker does nothing.

  #6 GENERATOR COLLAPSE DETECTOR. Mode collapse is measured throughput rising while INFORMATION
     throughput falls -- entropy dropping while volume holds. This became load-bearing this
     session: hypothesis generation went from one lens per day to a full lens x seat sweep
     (3 -> 15 jobs/run), which is exactly the condition that produces near-identical candidates
     from independent seats.

NEGATIVE KNOWLEDGE IS REVERSIBLE (charter s18). Dead-end families are DEMOTED, never zeroed --
`family_weight` has a floor. A family weighted to zero can never produce the evidence that would
revive it, which converts a measurement into a permanent belief.

Dependency-free by construction: stdlib only. See the package docstring.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

__all__ = [
    "MIN_FAMILY_WEIGHT",
    "BatchDiversity",
    "PrefilterVerdict",
    "TrivialVariationBlocker",
    "batch_diversity",
    "family_weight",
    "fingerprint",
    "horizon_bucket",
    "prefilter",
]

#: Charter s18 floor. A demoted family must stay reachable or the demotion is irreversible.
MIN_FAMILY_WEIGHT = 0.05

#: Cost floor from the spec: "gross edge must exceed 2x modeled round-trip cost".
COST_FLOOR_MULTIPLE = 2.0

#: Horizon buckets in hours. Coarse ON PURPOSE -- the blocker's whole value is that 12h and 13h
#: land in the same bucket, so a parameter tweak cannot mint a fresh fingerprint.
_HORIZON_EDGES = ((1.0, "intraday"), (8.0, "session"), (48.0, "swing"), (240.0, "position"))


def horizon_bucket(hours: float) -> str:
    """Map a holding horizon to its coarse bucket. Sub-hourly is its own regime, not 'intraday'."""
    if not math.isfinite(hours) or hours <= 0:
        return "unknown"
    if hours < 1.0:
        return "micro"
    for edge, name in _HORIZON_EDGES:
        if hours <= edge:
            return name
    return "carry"


def _norm(s: str) -> str:
    """Collapse to a comparable token: letters only, everything else dropped.

    Digits go because `rsi_14` and `rsi_21` are one mechanism wearing two names -- the desk's
    graveyard already records RSI/stochastic/Williams %R dying as a single family. Separators go
    for the same reason, caught by this module's own tests: mapping `z-score` to `z_score` and
    `zscore` to `zscore` left two fingerprints for one transform, which would have let a rejected
    mechanism walk straight back in under a hyphen.
    """
    return re.sub(r"[^a-z]", "", str(s).lower()) or "unknown"


def fingerprint(feature_family: str, transform: str, horizon_h: float) -> str:
    """The spec's mechanism fingerprint, shared by #3 and #6."""
    return f"{_norm(feature_family)}|{_norm(transform)}|{horizon_bucket(horizon_h)}"


@dataclass(frozen=True)
class PrefilterVerdict:
    """PASS -> full gauntlet. REJECT -> graveyard, zero heavy compute. ESCALATE -> full gauntlet.

    PASS and ESCALATE both proceed; they are kept distinct so the false-reject audit can measure
    how often the cheap stage actually had an opinion. A pre-filter that escalates everything is
    doing nothing, and that is only visible if 'proceeded because confident' and 'proceeded
    because unsure' are counted separately.
    """

    decision: str
    reasons: tuple[str, ...] = ()
    fingerprint: str = ""

    @property
    def proceeds(self) -> bool:
        return self.decision in ("PASS", "ESCALATE")


def prefilter(
    *,
    feature_family: str,
    transform: str,
    horizon_h: float,
    t_stat: float | None = None,
    ic: float | None = None,
    turnover: float | None = None,
    gross_edge_bps: float | None = None,
    round_trip_cost_bps: float | None = None,
    sign_stability: float | None = None,
    blocker: TrivialVariationBlocker | None = None,
) -> PrefilterVerdict:
    """Component #1. Cheap, unambiguous evidence only -- everything else escalates.

    Every `None` input is MISSING EVIDENCE and can never contribute to a rejection. This is the
    inverse of the desk's usual fail-closed rule and it is deliberate: for a safety gate, unknown
    must block; for a discovery screen, unknown must not kill. Confusing the two directions is
    how a cheap heuristic quietly becomes the thing that decides what the desk is allowed to find.
    """
    fp = fingerprint(feature_family, transform, horizon_h)
    reasons: list[str] = []

    if blocker is not None and blocker.is_blocked(fp):
        return PrefilterVerdict(
            "REJECT", (f"trivial variation of a mechanism already rejected: {fp} "
                       f"({blocker.reason(fp)})",), fp)

    # COST FLOOR. The one economic test that is unambiguous: an edge smaller than twice the
    # modelled cost of harvesting it cannot survive, and no amount of statistics changes that.
    if (gross_edge_bps is not None and round_trip_cost_bps is not None
            and round_trip_cost_bps > 0
            and gross_edge_bps < COST_FLOOR_MULTIPLE * round_trip_cost_bps):
        reasons.append(
            f"cost floor: gross {gross_edge_bps:.2f}bps < {COST_FLOOR_MULTIPLE:.0f}x "
            f"round-trip {round_trip_cost_bps:.2f}bps -- the edge does not pay for its own "
            f"execution before any statistical question is asked")

    # DEGENERATE TURNOVER. Zero turnover is not a signal; absurd turnover is a cost machine.
    if turnover is not None and (turnover <= 0.0 or turnover > 50.0):
        reasons.append(f"degenerate turnover {turnover:.3f} -- no positions taken, or a "
                       f"rebalancing schedule no cost model survives")

    # STATISTICS: only a MASSIVE shortfall counts as cheap and unambiguous. The thresholds are
    # deliberately far below any promotion bar -- this stage removes the hopeless, it does not
    # adjudicate the marginal.
    if t_stat is not None and abs(t_stat) < 0.5:
        reasons.append(f"|t| {abs(t_stat):.2f} < 0.50 in-sample -- not a borderline call")
    if ic is not None and abs(ic) < 0.005:
        reasons.append(f"|IC| {abs(ic):.4f} < 0.005 -- indistinguishable from zero")
    if sign_stability is not None and sign_stability < 0.35:
        reasons.append(f"sign stability {sign_stability:.2f} < 0.35 -- the sign itself is a "
                       f"coin flip, so there is no direction to trade")

    if reasons:
        return PrefilterVerdict("REJECT", tuple(reasons), fp)
    decided = any(x is not None for x in (t_stat, ic, gross_edge_bps, turnover, sign_stability))
    if not decided:
        return PrefilterVerdict("ESCALATE", ("no cheap evidence available -- the pre-filter "
                                             "must never reject on absence",), fp)
    return PrefilterVerdict("PASS", (), fp)


@dataclass
class TrivialVariationBlocker:
    """Component #3. Blocks PARAMETER variations of a rejected mechanism, never new mechanisms."""

    _blocked: dict[str, str] = field(default_factory=dict)

    def block(self, feature_family: str, transform: str, horizon_h: float, reason: str) -> str:
        fp = fingerprint(feature_family, transform, horizon_h)
        self._blocked[fp] = reason
        return fp

    def is_blocked(self, fp: str) -> bool:
        return fp in self._blocked

    def reason(self, fp: str) -> str:
        return self._blocked.get(fp, "")

    def unblock(self, fp: str) -> bool:
        """Reversible by construction (charter s18): a mechanism can be released when new
        evidence arrives. A blocklist with no exit is a permanent belief, not a measurement."""
        return self._blocked.pop(fp, None) is not None

    def __len__(self) -> int:
        return len(self._blocked)


def family_weight(rejections: int, total: int, *, floor: float = MIN_FAMILY_WEIGHT) -> float:
    """Component #2's weighting rule: demote dead-end families, NEVER to zero.

    Zero weight is self-sealing -- a family that can never be proposed can never produce the
    evidence that would revive it, so a finite sample becomes a permanent verdict.
    """
    if total <= 0:
        return 1.0
    survival = max(0.0, 1.0 - rejections / total)
    return max(floor, survival)


@dataclass(frozen=True)
class BatchDiversity:
    """Component #6's measurement. `collapsed` is the judgement; the rest is the evidence."""

    n: int
    distinct: int
    entropy: float
    max_entropy: float
    normalised: float
    duplicate_rate: float
    top_fingerprint: str
    collapsed: bool
    reasons: tuple[str, ...] = ()


def batch_diversity(
    fingerprints: list[str],
    *,
    prior_normalised: float | None = None,
    entropy_drop: float = 0.40,
    max_duplicate_rate: float = 0.25,
) -> BatchDiversity:
    """Component #6. Collapse = entropy falling while volume holds.

    Thresholds are the spec's own: entropy drop >40% vs the prior batch, or duplicate rate >25%.
    Normalised entropy (0..1) is what gets compared across batches -- raw entropy rises with
    batch size, so comparing raw values would report "improving diversity" for a batch that
    merely got bigger, which is precisely the illusion this component exists to strip out.
    """
    n = len(fingerprints)
    if n == 0:
        return BatchDiversity(0, 0, 0.0, 0.0, 0.0, 0.0, "", False,
                              ("empty batch -- nothing to measure",))
    counts = Counter(fingerprints)
    distinct = len(counts)
    ent = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_ent = math.log2(distinct) if distinct > 1 else 0.0
    norm = (ent / max_ent) if max_ent > 0 else (0.0 if n > 1 else 1.0)
    dup = 1.0 - distinct / n
    top, top_n = counts.most_common(1)[0]

    reasons: list[str] = []
    if dup > max_duplicate_rate:
        reasons.append(f"duplicate rate {dup:.0%} > {max_duplicate_rate:.0%} -- {top_n}/{n} "
                       f"candidates share fingerprint {top}")
    if prior_normalised is not None and prior_normalised > 0:
        drop = 1.0 - norm / prior_normalised
        if drop > entropy_drop:
            reasons.append(f"normalised entropy fell {drop:.0%} ({prior_normalised:.3f} -> "
                           f"{norm:.3f}) while {n} candidates were produced -- volume held and "
                           f"information did not")
    return BatchDiversity(n, distinct, round(ent, 4), round(max_ent, 4), round(norm, 4),
                          round(dup, 4), top, bool(reasons), tuple(reasons))
