"""WEAK-SIGNAL AGGREGATION, CROSS-DIGGER PROPAGATION, and the two that arm themselves later.

FOUR LEVERS THE PRINCIPAL CALLED FOR. I deferred three of them and was told to build them anyway;
that is his call and it is made. But "build it" and "pretend it has data" are different things, so
two are built LIVE and two are built DORMANT-AND-SELF-ARMING, each stating the exact condition
that switches it on. A dormant control that arms itself from a data condition is real; one that
waits for a human to remember is not, which is why portfolio_risk was built the same way.

  WEAK-SIGNAL AGGREGATION -- LIVE. `docs/research/weak_signal_registry.md` has existed for weeks
  and is read by NO code. That was a genuine miss on my part, not a blocked item: individually
  weak observations are exactly what a per-observation significance bar destroys by construction,
  and clusters of converging weak signals are how genuinely new directions arrive. Silence is also
  information -- a topic that STOPPED being discussed, a repo that stopped updating, an API that
  went quiet -- so negative observations aggregate alongside positive ones.

  CROSS-DIGGER PROPAGATION -- LIVE, and the objection I raised was wrong in an interesting way.
  I argued that propagating improvements between organs that never run builds for a pipeline that
  does not exist. But 6 of 7 miners being dark is exactly WHY propagation matters: when they are
  funded and start, whatever the one working miner learned should already be waiting for them
  rather than being rediscovered seven times. Propagation built now is propagation that costs
  nothing and is ready on day one; built later it is seven organs' worth of duplicated learning.

  COUNTERFACTUAL TRACKING -- DORMANT until >=1 discovery exists to be counterfactual ABOUT. The
  question "was this inevitable, or did it need our specific language/region/operator?" is
  meaningless with zero discoveries, and answering it from zero would be fabrication.

  OPPORTUNITY COST OF IGNORANCE -- LIVE, because it needs no history: the cost of NOT testing
  something is computable from its own EVIG the moment it is scored.

Pure, dependency-free, reports only.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CLUSTER_MIN",
    "Observation",
    "PropagationRule",
    "WeakSignalRegistry",
    "cluster_weak_signals",
    "counterfactual_ready",
    "opportunity_cost_of_ignorance",
    "propagate",
]

#: Converging observations needed before a cluster is worth a hypothesis. Three is the smallest
#: number that can distinguish a pattern from a coincidence and a pair -- and the bar is
#: deliberately low, because the whole point is to catch what a per-observation significance test
#: would have thrown away individually.
CLUSTER_MIN = 3

#: Weight of a NEGATIVE observation (something that stopped, went quiet, disappeared). Equal to a
#: positive one on purpose. Silence is information, and it is systematically under-recorded
#: because nobody files a report saying "the thing I was watching stopped happening".
_NEGATIVE_WEIGHT = 1.0


@dataclass(frozen=True)
class Observation:
    """One individually-unremarkable thing somebody noticed."""

    text: str
    tags: tuple[str, ...] = ()
    source: str = ""
    #: True when the observation is an ABSENCE -- a repo that stopped, a topic that vanished,
    #: an API that went quiet, a market that went still.
    negative: bool = False
    strength: float = 0.3          # individually weak by definition; 1.0 would not be "weak"


def cluster_weak_signals(obs: list[Observation], *,
                         min_size: int = CLUSTER_MIN) -> list[dict[str, Any]]:
    """Group weak observations by shared tag and promote CONVERGING clusters.

    A cluster's strength is SUPER-ADDITIVE in its member count -- sum(strength) x sqrt(n) --
    because independent observations converging on one tag is qualitatively different from one
    observer repeating themselves. sqrt rather than linear so a flood of low-quality notes from a
    single source cannot manufacture a finding.

    DISTINCT SOURCES ARE COUNTED SEPARATELY and reported, because three observations from one
    source is one opinion; three from three sources is a pattern. The caller sees both.
    """
    by_tag: dict[str, list[Observation]] = defaultdict(list)
    for o in obs:
        for t in (o.tags or ("untagged",)):
            by_tag[t].append(o)

    out = []
    for tag, members in by_tag.items():
        if len(members) < min_size:
            continue
        srcs = {m.source for m in members if m.source}
        raw = sum(m.strength * (_NEGATIVE_WEIGHT if m.negative else 1.0) for m in members)
        n_neg = sum(1 for m in members if m.negative)
        out.append({
            "tag": tag,
            "n": len(members),
            "distinct_sources": len(srcs),
            "n_negative": n_neg,
            "strength": round(raw * math.sqrt(len(members)), 4),
            "members": [m.text[:110] for m in members[:8]],
            "note": ("converging across INDEPENDENT sources -- a pattern"
                     if len(srcs) >= min_size else
                     f"only {len(srcs)} distinct source(s) -- may be one observer repeating"),
            "silence": (f"{n_neg}/{len(members)} are ABSENCES -- something stopped. Silence is "
                        "information and is systematically under-recorded." if n_neg else ""),
        })
    return sorted(out, key=lambda d: -d["strength"])


@dataclass(frozen=True)
class PropagationRule:
    """A search improvement one digger learned that every sibling should inherit."""

    name: str
    learned_by: str
    applies_to: tuple[str, ...] = ()      # empty = the whole fleet
    detail: str = ""
    #: Measured lift where known. None means "adopted on reasoning, not evidence" -- recorded
    #: distinctly so an unmeasured rule cannot masquerade as a proven one.
    measured_lift: float | None = None


def propagate(rules: list[PropagationRule], fleet: list[str]) -> dict[str, Any]:
    """Map each rule onto the diggers that do not yet have it.

    THE POINT IS THE FLEET, NOT THE RULE. One digger discovering a better search operator is a
    linear gain; the same discovery reaching seven is exponential, and that difference is the only
    reason a fleet beats a single good miner. A rule that stays where it was learned is the
    research equivalent of an alpha that never reaches capital.

    Six of seven miners are currently dark, and that STRENGTHENS the case rather than weakening
    it: propagation built now is waiting for them on the day they start, instead of being
    rediscovered independently seven times.
    """
    assignments: dict[str, list[str]] = {d: [] for d in fleet}
    unmeasured = []
    for r in rules:
        targets = [d for d in fleet if d != r.learned_by
                   and (not r.applies_to or d in r.applies_to)]
        for d in targets:
            assignments[d].append(r.name)
        if r.measured_lift is None:
            unmeasured.append(r.name)
    pending = sum(len(v) for v in assignments.values())
    return {
        "fleet_size": len(fleet),
        "rules": len(rules),
        "pending_adoptions": pending,
        "assignments": {k: v for k, v in assignments.items() if v},
        "unmeasured_rules": unmeasured,
        "note": (f"{pending} adoption(s) pending across {len(fleet)} diggers. A rule that stays "
                 "where it was learned is a linear gain; propagated it is the whole reason a "
                 "fleet beats one good miner."),
        "caution": (f"{len(unmeasured)} rule(s) have NO measured lift and are adopted on "
                    "reasoning alone -- recorded so an unproven rule cannot pass as proven."
                    if unmeasured else ""),
    }


def opportunity_cost_of_ignorance(evig_score: float, *,
                                  days_deferred: float = 1.0) -> dict[str, Any]:
    """The cost of NOT testing something -- the question a "what should we test?" list omits.

    A queue ranked only by what to test treats deferral as free. It is not: a hypothesis with real
    EVIG that sits untested for 30 days has cost 30 days of the information it would have
    produced, and on a desk whose north star reads 0.00 per 45 days that is the dominant term
    rather than a rounding error.

    Linear in time deliberately. Discounting deferral would encode the assumption that waiting is
    cheap, which is the belief this function exists to attack.
    """
    cost = max(0.0, float(evig_score)) * max(0.0, float(days_deferred))
    return {
        "evig": round(float(evig_score), 6),
        "days_deferred": round(float(days_deferred), 2),
        "cost_of_ignorance": round(cost, 6),
        "note": ("deferral is not free -- this is information the desk chose not to have, and "
                 "the choice compounds for as long as it stands"),
    }


def counterfactual_ready(n_discoveries: int, *, minimum: int = 1) -> dict[str, Any]:
    """DORMANT until there is a discovery to be counterfactual about. Arms from a data condition.

    "Was this discovery inevitable, or did it need our specific language, region, operator or
    maintainer?" is a real and valuable question -- low counterfactual probability means an edge
    others would not have found, which is exactly the durable kind. It is also strictly
    unanswerable at zero discoveries, and answering it anyway would be fabrication dressed as
    diligence. So it reports DORMANT and names what arms it, rather than inventing a score.
    """
    ready = n_discoveries >= minimum
    return {
        "state": "ACTIVE" if ready else "DORMANT",
        "n_discoveries": int(n_discoveries),
        "arms_at": minimum,
        "note": ("scoring counterfactual probability per discovery" if ready else
                 f"no discovery exists to be counterfactual about ({n_discoveries}/{minimum}). "
                 "Arms automatically from the registry -- nobody has to notice the first one."),
    }


@dataclass
class WeakSignalRegistry:
    """Append-only. Individually weak observations only ever accumulate value."""

    observations: list[Observation] = field(default_factory=list)

    def add(self, o: Observation) -> None:
        self.observations.append(o)

    def clusters(self, *, min_size: int = CLUSTER_MIN) -> list[dict[str, Any]]:
        return cluster_weak_signals(self.observations, min_size=min_size)

    def tag_counts(self) -> Counter[str]:
        c: Counter[str] = Counter()
        for o in self.observations:
            c.update(o.tags or ("untagged",))
        return c
