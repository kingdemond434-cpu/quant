"""CROSS-ECOSYSTEM CONVERGENCE -- and the provenance check that decides whether it means anything.

THE IDEA, WHICH IS A GOOD ONE. The desk mines seven language regions plus WorldQuant, academic
literature and its own tape. When researchers in unrelated ecosystems independently describe the
same market mechanism, that is evidence of something real: they had different data, different
venues, different regulatory regimes and different incentives, and they arrived at the same place
anyway. A mechanism found once is a lead. The same mechanism found in Korea and Brazil and Russia,
independently, is a much stronger prior than three leads.

**AND IT IS THE EASIEST FALSE SIGNAL THIS DESK COULD POSSIBLY BUILD.** Ecosystems are not
independent. A Korean blog post, a Brazilian thread and a Russian Telegram summary describing the
same effect are, far more often than not, THREE READINGS OF ONE ENGLISH PAPER. The apparent
convergence is propagation, and it has a direction: ideas flow from the English-language arXiv /
SSRN / WorldQuant layer outward. Counting the echoes as independent confirmations is the desk's
single most-repeated defect -- GAP #85, `n` counting READINGS OF THE WORLD rather than EVENTS IN
THE WORLD -- and here it would be worse than usual, because the number it inflates is precisely
the number used to promote a mechanism above its evidence.

So this module's real job is not finding matches. Matching is easy and `mechanism_fingerprint`
already does it. The job is REFUSING TO CALL A MATCH A CONFIRMATION until provenance says the
observers could not have been reading each other.

THREE VERDICTS, AND THE THIRD IS THE ONE THAT MATTERS::

    INDEPENDENT_CONVERGENCE   provenance recorded, and no shared origin -> genuine, elevate
    SHARED_SOURCE_ECHO        a common origin (or one cites another) -> ONE observation, not k
    UNVERIFIABLE_PROVENANCE   nobody recorded where the finding came from -> CANNOT SAY

UNVERIFIABLE is not a soft INDEPENDENT. It is the default state of every finding the miners
currently produce, because none of them record what a source derives from -- and if absence
resolved to "independent" this module would elevate every echo in the corpus on day one. It
therefore reports the independent count as an UPPER BOUND and elevates nothing.

WHAT THIS DOES NOT DO. It confers no belief about whether the mechanism WORKS. Ten independent
ecosystems can all be wrong about the same thing, and folk finance is exactly the domain where
they are: a widely-held retail belief is widely held BECAUSE it is intuitive, not because it is
true. Convergence buys a queue place ahead of a singleton lead. It never buys a bar reduction, and
a converged mechanism owes the identical pre-registration, deflation and out-of-sample evidence as
one nobody else mentioned.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

__all__ = [
    "MIN_REGIONS",
    "ConvergenceVerdict",
    "Observation",
    "assess",
    "elevate",
    "group_by_mechanism",
    "provenance_clusters",
]

#: Distinct ecosystems required before the word "convergence" is used at all. Two is the minimum
#: that can mean anything, and the bar that matters is not this number -- it is whether the two are
#: provenance-independent. Ten dependent observations are weaker evidence than two independent ones.
MIN_REGIONS: int = 2

#: Hosts that are ORIGIN LAYERS rather than ecosystems: the places regional communities read FROM.
#: Two regional findings that both cite arXiv are one observation of arXiv, and the flow direction
#: is why this list is not symmetric with the region list -- ideas propagate outward from here.
ORIGIN_HOSTS: frozenset[str] = frozenset({
    "arxiv.org", "ssrn.com", "papers.ssrn.com", "worldquantbrain.com", "worldquant.com",
    "nber.org", "sciencedirect.com", "jstor.org", "researchgate.net", "semanticscholar.org",
})


@dataclass(frozen=True)
class Observation:
    """One ecosystem's sighting of one mechanism.

    `origins_recorded` IS A SEPARATE FIELD FROM `origins` ON PURPOSE, and it is the whole
    honesty of this module. An empty `origins` tuple is ambiguous between "the miner checked and
    this finding cites nothing" and "nobody looked", and those are opposite facts: the first is
    evidence of independence, the second is the absence of evidence. Collapsing them into one
    empty tuple would make every unexamined finding look original (L1.28a).
    """

    region: str
    mechanism: str
    source: str = ""
    origins: tuple[str, ...] = ()
    origins_recorded: bool = False
    observed: str = ""
    note: str = ""

    @property
    def host(self) -> str:
        return _host(self.source)


def _host(url: str) -> str:
    if not url:
        return ""
    raw = url if "//" in url else "//" + url
    return (urlsplit(raw).hostname or "").lower().removeprefix("www.")


def _keys(o: Observation) -> set[str]:
    """Every provenance token an observation carries: its own locator plus what it derives from.

    The observation's OWN source is included deliberately. If a Brazilian post cites a Korean blog,
    the Korean blog appears as the Brazilian's origin AND as the Korean's source, so the two share
    a token and collapse -- which is the citation case, and the one most likely to look like
    convergence to a reader skimming two languages.
    """
    toks = {_host(x) or x.strip().lower() for x in o.origins if x.strip()}
    if o.source:
        toks.add(_host(o.source) or o.source.strip().lower())
    return {t for t in toks if t}


def provenance_clusters(obs: list[Observation]) -> list[list[int]]:
    """Group observations that cannot be treated as independent.

    Union-find over shared provenance tokens, the same instrument
    `alpha_factory.independence.cluster` uses on returns and for the same reason: single linkage
    is CONSERVATIVE here. Merging A and C because both merely touch B reports FEWER independent
    observations, and every other linkage choice would flatter the count. The number exists to be
    honest rather than encouraging.
    """
    parent = list(range(len(obs)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_token: dict[str, int] = {}
    for i, o in enumerate(obs):
        for tok in _keys(o):
            if tok in by_token:
                parent[find(i)] = find(by_token[tok])
            else:
                by_token[tok] = i

    groups: dict[int, list[int]] = {}
    for i in range(len(obs)):
        groups.setdefault(find(i), []).append(i)
    return [sorted(v) for v in groups.values()]


@dataclass(frozen=True)
class ConvergenceVerdict:
    """What a set of sightings of one mechanism is actually worth."""

    mechanism: str
    verdict: str                      # INDEPENDENT_CONVERGENCE | SHARED_SOURCE_ECHO
    #                                 # | UNVERIFIABLE_PROVENANCE | SINGLE_ECOSYSTEM
    regions: tuple[str, ...]
    n_observations: int
    independent_clusters: int
    unrecorded: int
    shared_origins: tuple[str, ...] = ()
    reason: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def elevates(self) -> bool:
        """Only genuine independence earns a queue place ahead of a singleton lead."""
        return self.verdict == "INDEPENDENT_CONVERGENCE"


def group_by_mechanism(obs: list[Observation]) -> dict[str, list[Observation]]:
    """Bucket sightings by mechanism.

    MECHANISM, NOT PHRASE. `mechanism_fingerprint.fingerprint()` is the intended key: two posts in
    two languages describing "funding flips negative before a squeeze" share no vocabulary and are
    the same claim, while "momentum works" in two languages is two different claims wearing one
    phrase. Matching on words would do both errors at once.
    """
    out: dict[str, list[Observation]] = {}
    for o in obs:
        out.setdefault(o.mechanism, []).append(o)
    return out


def assess(mechanism: str, obs: list[Observation], *, min_regions: int = MIN_REGIONS,
           ) -> ConvergenceVerdict:
    """Is this convergence, an echo, or unknowable?

    ORDER OF CHECKS IS LOAD-BEARING. Unverifiable provenance is tested BEFORE independence,
    because an unrecorded origin cannot be shown absent -- and testing independence first would
    let a corpus with no provenance at all report a clean sweep of independent convergences, which
    is exactly the state the miners are in today.
    """
    regions = tuple(sorted({o.region for o in obs if o.region}))
    clusters = provenance_clusters(obs)
    unrecorded = sum(1 for o in obs if not o.origins_recorded)

    shared: list[str] = []
    counts: Counter[str] = Counter()
    for o in obs:
        for tok in {_host(x) or x.strip().lower() for x in o.origins if x.strip()}:
            counts[tok] += 1
    shared = sorted(t for t, c in counts.items() if c > 1 or t in ORIGIN_HOSTS)

    if len(regions) < min_regions:
        return ConvergenceVerdict(
            mechanism, "SINGLE_ECOSYSTEM", regions, len(obs), len(clusters), unrecorded,
            tuple(shared),
            f"seen in {len(regions)} ecosystem(s); convergence needs {min_regions}. A single "
            "ecosystem repeating itself is one observation with a loud voice.")

    if unrecorded:
        return ConvergenceVerdict(
            mechanism, "UNVERIFIABLE_PROVENANCE", regions, len(obs), len(clusters), unrecorded,
            tuple(shared),
            f"{unrecorded} of {len(obs)} sighting(s) never recorded what they derive from, so "
            "shared origin can be neither shown nor ruled out. This is an INABILITY TO CHECK, not "
            "independence -- and ideas propagate outward from the English-language origin layer, "
            "so the untested hypothesis is that these are echoes. The "
            f"{len(clusters)} apparent independent cluster(s) are an UPPER BOUND.",
            ("elevates nothing: an unverified match is a lead, exactly like a singleton",))

    if len(clusters) < min_regions:
        return ConvergenceVerdict(
            mechanism, "SHARED_SOURCE_ECHO", regions, len(obs), len(clusters), unrecorded,
            tuple(shared),
            f"{len(obs)} sighting(s) across {len(regions)} ecosystem(s) collapse to "
            f"{len(clusters)} provenance cluster(s) via {shared or 'a citation chain'}. That is "
            "ONE observation reported k times, and counting it as k is the desk's most-repeated "
            "defect (GAP #85: n counting readings, not events).")

    return ConvergenceVerdict(
        mechanism, "INDEPENDENT_CONVERGENCE", regions, len(obs), len(clusters), unrecorded,
        tuple(shared),
        f"{len(clusters)} provenance-independent cluster(s) across {len(regions)} ecosystem(s) "
        f"({', '.join(regions)}), with origins recorded for every sighting and no common source. "
        "Different data, venues and regimes reaching the same mechanism.",
        ("A QUEUE PLACE, NOT A LOWER BAR. Ten ecosystems can be wrong about the same thing, and "
         "folk finance is where they are -- a belief is widely held because it is intuitive. This "
         "owes the same pre-registration, deflation and out-of-sample evidence as a singleton.",))


def elevate(obs: list[Observation], *, min_regions: int = MIN_REGIONS,
            ) -> tuple[list[ConvergenceVerdict], dict[str, int]]:
    """Assess every mechanism; return verdicts ranked by strength, plus the corpus tally.

    THE TALLY IS THE POINT ON DAY ONE. With no provenance recorded anywhere, every verdict is
    UNVERIFIABLE and the elevated list is empty -- which reads as a broken feature and is in fact
    the correct measurement of a corpus that never recorded where its findings came from. The
    tally makes that visible as a fixable gap rather than as silence.
    """
    verdicts = [assess(m, o, min_regions=min_regions)
                for m, o in sorted(group_by_mechanism(obs).items())]
    rank = {"INDEPENDENT_CONVERGENCE": 0, "UNVERIFIABLE_PROVENANCE": 1,
            "SHARED_SOURCE_ECHO": 2, "SINGLE_ECOSYSTEM": 3}
    verdicts.sort(key=lambda v: (rank[v.verdict], -v.independent_clusters, -len(v.regions)))
    return verdicts, dict(Counter(v.verdict for v in verdicts))
