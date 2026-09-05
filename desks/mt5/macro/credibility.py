"""SOURCE CREDIBILITY AS A LEARNED HIERARCHY -- a prior ordering that the record is allowed to
overturn.

WHY NOT A TIER LIST. A fixed table saying "official releases are true, social media is not" is
right often enough to feel safe and wrong in exactly the cases that matter: the official
statistic that gets revised, the wire that ran an unconfirmed line, the specialist account that
was forty minutes ahead of everyone on a refinery outage. It also cannot improve. The tiers here
are PRIORS -- a defensible starting ordering -- and both levels of the hierarchy update from
measured outcomes.

TWO LEVELS, BOTH FITTED.

    tier      Beta(a_t, b_t), re-estimated by moment-matching the verification rates of the
              sources IN that tier. A tier whose members keep being wrong loses its prior
              strength; a tier with too few measured sources keeps the seeded prior and SAYS so.
    source    Beta(a_t + verified_s, b_t + falsified_s). A source with no record IS its tier --
              which is the right amount of trust for a source nobody has checked -- and moves to
              its own evidence as the record accumulates. Shrinkage is automatic and is the whole
              reason for the hierarchy.

VERIFICATION IS MEASURED, NEVER ASSUMED. `attribution.py` is the only writer of verified /
falsified counts, and it stamps them from what actually happened after the claim. Nothing in this
module infers that a source was right because it agreed with another source; that would make
credibility a popularity measure and would let a cluster of sources bootstrap each other.

SPEED IS A SEPARATE AXIS, AND IT HAD BETTER BE. A source can be perfectly reliable and useless:
if its median arrival is after the price has already moved, its unpriced fraction is zero every
time. `SourcePosterior.lead_s` carries the measured median of (first cross-asset move) minus
(received), so a source can be reliable-and-late, and the report says which. Conflating the two
into one "quality" score is how a desk ends up paying for accurate history.

INDEPENDENT CONFIRMATIONS RAISE THE POSTERIOR; CORRELATED ONES MOSTLY DO NOT. Three wires quoting
one wire is one observation wearing three coats. Log-odds are summed with a weight that is
discounted by the MEASURED co-report rate between sources, so a redundancy the ledger can see is
a redundancy the arithmetic charges for.

A CONTESTED REPORT'S HONEST OUTPUT IS A PROBABILITY AND MORE UNCERTAINTY, NOT A DIRECTION.
`combine` never returns a confident answer when sources disagree: `uncertainty_mult` rises with
the strength of the opposing evidence, and it divides importance downstream, so a contested claim
is structurally incapable of producing a large allocation change. Both branches are carried.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from .ledger import MACRO_DIR, MIN_SOURCE_N, write_json_atomic
from .schema import Credibility, Status, now_iso

CREDIBILITY_PATH = MACRO_DIR / "source_credibility.json"

#: THE PRIOR ORDERING. Pseudo-counts, not probabilities: (a, b) means "as if we had seen a
#: verified and b falsified claims". OFFICIAL is strong because a central bank's own press
#: release is the primary document rather than a report about one; SOCIAL_OSINT is weak but NOT
#: zero, because a weak prior that evidence can move is the point of the hierarchy -- a zero
#: prior can never be updated out of.
#:
#: These numbers are the only judgement in this file, they are visible, and `fit_tiers` overwrites
#: them from measured verification rates the moment there is sample to do it with.
TIER_PRIOR: dict[str, tuple[float, float]] = {
    "OFFICIAL": (40.0, 1.0),
    "WIRE": (20.0, 2.0),
    "SPECIALIST": (8.0, 3.0),
    "SOCIAL_OSINT": (3.0, 4.0),
    "UNKNOWN": (1.0, 1.0),
}

#: Sources with a measured record needed before a TIER's prior is re-fitted from its members.
#: Below this the tier keeps its seeded prior and the report says UNMEASURED -- re-fitting a
#: tier from two sources would let one bad source rewrite the prior for every source under it.
MIN_TIER_SOURCES = 4

#: Cap on total pseudo-count after a tier re-fit. An unbounded fitted prior would make the tier
#: so strong that no individual source could ever move away from it, which defeats the hierarchy.
MAX_TIER_STRENGTH = 80.0

__all__ = [
    "MIN_TIER_SOURCES",
    "TIER_PRIOR",
    "Claim",
    "CredibilityModel",
    "SourcePosterior",
]


@dataclass(frozen=True)
class SourcePosterior:
    source_id: str
    tier: str
    alpha: float
    beta: float
    n_verified: int
    n_falsified: int
    status: str
    #: Median seconds between this source's arrival and the first cross-asset move attributable
    #: to the claim. NEGATIVE means the source arrives BEFORE the move -- the only kind of source
    #: whose information can still be traded.
    lead_s: float | None = None
    n_speed: int = 0

    @property
    def p_true(self) -> float:
        return float(self.alpha / (self.alpha + self.beta))

    @property
    def log_odds(self) -> float:
        p = min(max(self.p_true, 1e-6), 1.0 - 1e-6)
        return math.log(p / (1.0 - p))


@dataclass(frozen=True)
class Claim:
    """One source's assertion about one underlying claim.

    `supports=False` is a source REFUTING the claim, which is not the same as a source being
    silent. Silence is absence of evidence and contributes nothing here; contradiction is
    evidence and contributes negatively AND raises uncertainty.
    """

    source_id: str
    supports: bool = True
    received_at: str = ""


class CredibilityModel:
    """The two-level Beta hierarchy, its persistence, and the combination rule."""

    def __init__(self, tiers: Mapping[str, tuple[float, float]] | None = None,
                 path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else CREDIBILITY_PATH
        self.tiers: dict[str, tuple[float, float]] = dict(tiers or TIER_PRIOR)
        self.tier_status: dict[str, str] = dict.fromkeys(self.tiers, Status.UNMEASURED)
        self.sources: dict[str, SourcePosterior] = {}
        #: source -> tier, declared by `sources.py`. A source not registered here is UNKNOWN,
        #: which is the weakest prior -- never a default of trust.
        self.tier_of: dict[str, str] = {}
        #: Measured co-report rate: how often two sources carry the same claim. The independence
        #: discount comes from here, so it is evidence rather than an assumption about newsrooms.
        self.redundancy: dict[tuple[str, str], float] = {}

    # -------------------------------------------------------------------- fit ----
    def fit(self, outcomes: Mapping[str, Mapping[str, Any]],
            tier_of: Mapping[str, str] | None = None,
            redundancy: Mapping[tuple[str, str], float] | None = None) -> CredibilityModel:
        """Fit both levels from `{source_id: {"verified": n, "falsified": n, "leads": [...]}}`.

        Order matters: tiers are fitted FIRST from the sources that have sample, then every
        source's posterior is formed against its (possibly updated) tier. Doing it the other way
        would let a source's own evidence enter its prior twice.
        """
        if tier_of:
            self.tier_of.update(tier_of)
        if redundancy:
            self.redundancy.update(redundancy)
        self._fit_tiers(outcomes)
        for sid, rec in outcomes.items():
            self.sources[sid] = self._posterior(sid, rec)
        return self

    def _fit_tiers(self, outcomes: Mapping[str, Mapping[str, Any]]) -> None:
        by_tier: dict[str, list[float]] = {}
        for sid, rec in outcomes.items():
            v = int(rec.get("verified", 0) or 0)
            f = int(rec.get("falsified", 0) or 0)
            if v + f < MIN_SOURCE_N:
                continue
            by_tier.setdefault(self.tier_of.get(sid, "UNKNOWN"), []).append(v / (v + f))
        for tier, rates in by_tier.items():
            if len(rates) < MIN_TIER_SOURCES:
                continue
            m = sum(rates) / len(rates)
            var = sum((r - m) ** 2 for r in rates) / max(len(rates) - 1, 1)
            m = min(max(m, 1e-3), 1.0 - 1e-3)
            # Method of moments for a Beta: strength = m(1-m)/var - 1. Degenerate (var ~ 0)
            # means the members agree perfectly, which on a handful of sources is far more
            # likely to be small-sample luck than a genuinely certain tier, so the strength is
            # capped rather than allowed to run to infinity.
            if var <= 1e-9:
                strength = MAX_TIER_STRENGTH
            else:
                strength = max(1.0, min(MAX_TIER_STRENGTH, m * (1.0 - m) / var - 1.0))
            self.tiers[tier] = (m * strength, (1.0 - m) * strength)
            self.tier_status[tier] = Status.MEASURED

    def _posterior(self, source_id: str, rec: Mapping[str, Any]) -> SourcePosterior:
        tier = self.tier_of.get(source_id, "UNKNOWN")
        a0, b0 = self.tiers.get(tier, self.tiers["UNKNOWN"])
        v = int(rec.get("verified", 0) or 0)
        f = int(rec.get("falsified", 0) or 0)
        leads = [float(x) for x in (rec.get("leads") or []) if isinstance(x, int | float)]
        return SourcePosterior(
            source_id=source_id, tier=tier, alpha=a0 + v, beta=b0 + f,
            n_verified=v, n_falsified=f,
            status=Status.MEASURED if v + f >= MIN_SOURCE_N else Status.UNMEASURED,
            lead_s=float(median(leads)) if len(leads) >= MIN_SOURCE_N else None,
            n_speed=len(leads))

    def posterior(self, source_id: str) -> SourcePosterior:
        """A source we have never measured is its tier prior. That is the honest answer, and it
        is why an unregistered source lands on UNKNOWN rather than on trust."""
        if source_id in self.sources:
            return self.sources[source_id]
        return self._posterior(source_id, {})

    # --------------------------------------------------------------- combining ----
    def _independence_weight(self, sid: str, earlier: Sequence[str]) -> float:
        """1 for the first voice; discounted by the MEASURED co-report rate with the voices
        already counted. Three outlets that always carry the same wire contribute barely more
        than one, and the ledger is what says they do."""
        rho = 0.0
        for other in earlier:
            key = (sid, other) if sid < other else (other, sid)
            rho = max(rho, float(self.redundancy.get(key, 0.0)))
        return 1.0 / (1.0 + max(0.0, min(1.0, rho)) * max(0, len(earlier)))

    def combine(self, claims: Sequence[Claim]) -> Credibility:
        """P(claim true) from independent-ish log-odds, and an uncertainty that RISES on conflict.

        The prior is deliberately 0.5 in log-odds terms (0.0): this module has no opinion about
        whether an unspecified world event is true before it hears from anybody.
        """
        if not claims:
            return Credibility(0.5, 1.0, 1.0, status=Status.UNMEASURED,
                               basis="no claims", uncertainty_mult=2.0)
        total = 0.0
        counted: list[str] = []
        w_support = 0.0
        w_refute = 0.0
        alpha = 1.0
        beta = 1.0
        n_v = n_f = 0
        for c in claims:
            post = self.posterior(c.source_id)
            w = self._independence_weight(c.source_id, counted)
            contribution = w * post.log_odds
            total += contribution if c.supports else -contribution
            # alpha/beta here are the EVIDENCE WEIGHTS behind p_true, not a second Beta fit:
            # they let a consumer see how much independent voice sits on each side, which is the
            # thing a bare probability hides.
            if c.supports:
                w_support += w * abs(post.log_odds)
                alpha += w
            else:
                w_refute += w * abs(post.log_odds)
                beta += w
            n_v += post.n_verified
            n_f += post.n_falsified
            counted.append(c.source_id)
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, total))))
        contested = w_support > 0.0 and w_refute > 0.0
        # Conflict penalty: 1 at no conflict, 2 when the two sides are exactly balanced. It
        # DIVIDES importance downstream, so a contested claim cannot produce a large move no
        # matter how credible either side is on its own.
        if contested:
            balance = min(w_support, w_refute) / (w_support + w_refute)
            unc = 1.0 + 2.0 * balance
        else:
            unc = 1.0
        measured = any(self.posterior(c.source_id).status == Status.MEASURED for c in claims)
        basis = (f"{len(claims)} claim(s), {sum(1 for c in claims if c.supports)} supporting; "
                 f"log-odds {total:+.2f}"
                 + ("; CONTESTED -- both branches carried, uncertainty raised" if contested
                    else ""))
        return Credibility(
            p_true=round(p, 6), alpha=round(alpha, 4), beta=round(beta, 4),
            n_verified=n_v, n_falsified=n_f, uncertainty_mult=round(unc, 4),
            contested=contested,
            status=Status.MEASURED if measured else Status.UNMEASURED,
            basis=basis)

    # ------------------------------------------------------------------ report ----
    def report(self) -> dict[str, Any]:
        rows = []
        for sid, p in sorted(self.sources.items()):
            rows.append({
                "source": sid, "tier": p.tier, "p_true": round(p.p_true, 4),
                "n_verified": p.n_verified, "n_falsified": p.n_falsified,
                "status": p.status, "lead_s": p.lead_s, "n_speed": p.n_speed,
                "verdict": ("reliable_and_early" if p.lead_s is not None and p.lead_s > 0
                            else "reliable_but_late" if p.lead_s is not None
                            else "speed UNMEASURED"),
            })
        return {
            "at": now_iso(),
            # UNROUNDED on purpose: this is the LEARNED STATE, not a display value. `save` and
            # `load` are the persistence path for the hierarchy, and rounding here would let the
            # fitted prior drift a little on every restart -- a slow corruption of the one thing
            # in this module that accumulates.
            "tiers": {t: {"alpha": a, "beta": b,
                          "status": self.tier_status.get(t, Status.UNMEASURED)}
                      for t, (a, b) in sorted(self.tiers.items())},
            "min_tier_sources": MIN_TIER_SOURCES,
            "min_source_n": MIN_SOURCE_N,
            "sources": rows,
            "note": ("Tier priors are a starting ordering; both levels re-fit from measured "
                     "verification outcomes written by attribution.py. Speed is reported "
                     "SEPARATELY from reliability -- a reliable source that arrives after the "
                     "move has an unpriced fraction of zero and is worth nothing to trade on."),
        }

    def save(self) -> None:
        write_json_atomic(self.path, self.report())

    def load(self) -> CredibilityModel:
        if not self.path.exists():
            return self
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return self
        for tier, d in (raw.get("tiers") or {}).items():
            try:
                self.tiers[tier] = (float(d["alpha"]), float(d["beta"]))
                self.tier_status[tier] = str(d.get("status", Status.UNMEASURED))
            except (KeyError, TypeError, ValueError):
                continue
        for row in raw.get("sources") or []:
            sid = str(row.get("source", ""))
            if not sid:
                continue
            self.tier_of.setdefault(sid, str(row.get("tier", "UNKNOWN")))
        return self


def redundancy_from_ledger(groups: Iterable[Sequence[str]]) -> dict[tuple[str, str], float]:
    """Measure how often two sources report the SAME claim, from clustered ledger items.

    `groups` is an iterable of source-id lists, one per claim cluster. The rate is
    co-occurrences / min(appearances), which is asymmetric-aware: a small specialist source that
    is always echoed by a wire is highly redundant WITH that wire even though the wire is not
    redundant with it. Using the minimum keeps the discount conservative in the direction that
    matters -- it is easier to over-count independence than under-count it, and over-counting is
    what turns one report into three.
    """
    appear: dict[str, int] = {}
    co: dict[tuple[str, str], int] = {}
    for g in groups:
        uniq = sorted(set(g))
        for s in uniq:
            appear[s] = appear.get(s, 0) + 1
        for i, a in enumerate(uniq):
            for b in uniq[i + 1:]:
                co[(a, b)] = co.get((a, b), 0) + 1
    out: dict[tuple[str, str], float] = {}
    for (a, b), c in co.items():
        denom = min(appear.get(a, 1), appear.get(b, 1))
        out[(a, b)] = round(min(1.0, c / max(1, denom)), 4)
    return out
