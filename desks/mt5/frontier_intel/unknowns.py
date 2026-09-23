"""THE UNKNOWN UNKNOWNS: organisations nobody listed, and capabilities nobody named.

    "it also mines all unknowns of unknowns abt these chinese western firms ai ml quant shops etc
     all asian etc"                                                  -- the principal, 2026-09-05

WHY A REGISTRY IS NOT ENOUGH, and why this file is the one that keeps the miner from going stale.
`registry.FIRMS` is a list somebody wrote down, so it can only ever find what that person already
knew to look for. Every genuinely new capability arrives from an organisation not on the list, in
a capability group the ontology has no row for, or through a claim nobody has verified -- and a
miner that only walks its registry converges on confirming what it already believed within weeks.

THREE KINDS OF UNKNOWN, and they need different machinery:

  UNKNOWN FIRM        an organisation this registry has never named. Discovered by co-occurrence:
                      a name that keeps appearing beside organisations we DO track, in sources we
                      already read, is a candidate for the registry. Cheap, and it is how every
                      list of firms actually grows.
  UNKNOWN CAPABILITY  a finding that maps to NO ontology group. The ontology deliberately refuses
                      to fuzzy-match, so these land here rather than being forced into the nearest
                      row -- and a cluster of them is the signal that the ontology itself is
                      short a category, which is a bigger finding than any single card.
  UNADDRESSED         a capability group the ontology names and this desk has NO module for. Not
                      "we are weak at it" -- "we have never done it". These are where the largest
                      real differences to an elite organisation live, and they are knowable today
                      without crawling anything.

THE ANTI-CONVERGENCE BUDGET. §29 of the mandate reserves exploration capital so exploitation does
not make the research system intellectually stagnant, and the same argument applies one level up:
a fixed fraction of every cycle goes to the unknown lanes REGARDLESS of their score, because their
score is computed from a model that by construction does not know about them. Spending zero on
unknowns is how a miner becomes a search for confirmation.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import ontology, registry

BASE = Path(__file__).resolve().parent.parent
CANDIDATES = BASE / "frontier_intel" / "data" / "firm_candidates.jsonl"

#: Fraction of each cycle's attention reserved for the unknown lanes whatever they score.
#: DERIVED FROM THE MANDATE'S OWN RANGE (5-15% for unknown-unknowns) and set at the middle of it.
#: Higher would starve the queue the desk can actually price; lower stops being a budget and
#: becomes a rounding error that the first busy hour spends elsewhere.
EXPLORATION_FRACTION = 0.10

#: An organisation-shaped token: two-to-four capitalised words, or a known corporate suffix. Kept
#: crude ON PURPOSE -- this proposes candidates for a human-or-agent decision, it does not admit
#: them. A precise extractor here would be a second, worse named-entity recogniser.
_ORG = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&.\-]+(?:\s+|-)){1,3}"
    r"(?:Capital|Asset|Assets|Management|Investment|Investments|Technologies|Technology|"
    r"Research|Securities|Trading|Partners|Fund|Funds|Quant|Quantitative|Labs|Lab|AI))\b")

#: Words that make an organisation-shaped token a false positive: our own vocabulary, and the
#: generic phrases every article about quant funds contains.
_NOISE = frozenset({
    "the fund", "a fund", "hedge fund", "quant fund", "mutual fund", "index fund",
    "asset management", "investment management", "artificial intelligence",
    "machine learning", "quantitative research", "quantitative trading",
})


#: Words that appear in half of all firm names and identify none of them. A candidate matched to a
#: tracked firm on one of these alone would collapse every "X Capital" into whichever tracked firm
#: happened to contain "capital".
_GENERIC = frozenset({
    "capital", "asset", "assets", "management", "investment", "investments", "technologies",
    "technology", "research", "securities", "trading", "partners", "fund", "funds", "quant",
    "quantitative", "labs", "lab", "ai", "group", "invest", "holdings", "the", "and",
})


def _distinctive(name: str) -> frozenset[str]:
    """The tokens that actually identify a firm: everything minus the industry vocabulary."""
    return frozenset(t for t in name.lower().replace("-", " ").split() if t not in _GENERIC)


def _same_firm(candidate: str, known: set[str]) -> bool:
    """Is this candidate a tracked firm written a different way?

    TOKEN OVERLAP, NOT SUBSTRING, and this file's own test found why. "Man AHL Capital" keys to
    "AHL Capital"; the registry holds "Man AHL"; neither string contains the other, so a substring
    test reported a tracked firm as an exciting new discovery. Sharing a DISTINCTIVE token --
    "ahl" -- is the signal, and dropping the industry vocabulary first is what stops every
    "<Something> Capital" collapsing into the first tracked firm whose name contains "capital".
    """
    mine = _distinctive(candidate)
    return bool(mine) and any(mine & _distinctive(k) for k in known)


@dataclass(frozen=True)
class Unknown:
    """One thing the miner did not previously know about, and why it is worth a look."""

    kind: str               # FIRM | CAPABILITY | UNADDRESSED
    name: str
    mentions: int
    seen_with: tuple[str, ...]
    why: str


def unknown_firms(texts: list[str], min_mentions: int = 2) -> list[Unknown]:
    """Organisation names appearing in what we already read that the registry does not know.

    CO-OCCURRENCE IS THE WHOLE SIGNAL. A name appearing once in one article is noise; a name
    appearing repeatedly, in sources we read because they discuss firms we track, is what the
    registry is missing. `min_mentions` is the only knob and it is deliberately low: the cost of a
    false candidate is one investigation, and the cost of a missed one is a permanent blind spot.
    """
    known = {n.lower() for n in registry.BY_NAME}
    counts: Counter[str] = Counter()
    beside: dict[str, set[str]] = {}
    for text in texts:
        found = {m.group(1).strip() for m in _ORG.finditer(text or "")}
        tracked = {f for f in registry.BY_NAME if f.lower() in (text or "").lower()}
        for name in found:
            # KEYED ON THE LAST TWO WORDS, because the same organisation is written several ways
            # in the same corpus: "Shanghai Qingyuan Capital" in one article and "Qingyuan
            # Capital" in the next are one candidate, and counting them separately halves every
            # mention count and pushes real firms below `min_mentions`. The trailing tokens are
            # the stable part of a firm name; the leading ones are cities and qualifiers.
            key = " ".join(name.split()[-2:]).strip()
            low = key.lower()
            if low in known or low in _NOISE or len(key) < 4:
                continue
            if _same_firm(low, known):
                continue                      # a tracked firm written a different way
            counts[key] += 1
            beside.setdefault(key, set()).update(tracked)
    out = []
    for name, n in counts.most_common():
        if n < min_mentions:
            continue
        with_ = tuple(sorted(beside.get(name, ())))
        out.append(Unknown(
            "FIRM", name, n, with_,
            why=(f"named {n} time(s) in sources we already read"
                 + (f", beside {', '.join(with_[:3])}" if with_ else "")
                 + " -- the registry does not know it, and a registry only finds what its author "
                   "already knew to list")))
    return out


def unknown_capabilities(findings: list[dict[str, Any]]) -> list[Unknown]:
    """Findings that map to no ontology group -- and the ontology gap a cluster of them implies.

    `ontology.map_to_capabilities` refuses to fuzzy-match on purpose, so an unmappable finding is
    not silently filed under the nearest row. It lands here. ONE of them is a badly-extracted
    card; a CLUSTER of them saying similar things is the ontology missing a category, which is a
    larger finding than any card in the cluster.
    """
    out: list[Unknown] = []
    for f in findings:
        text = " ".join(str(f.get(k) or "") for k in
                        ("capability_domain", "public_observation", "underlying_principle"))
        if ontology.map_to_capabilities(text):
            continue
        out.append(Unknown(
            "CAPABILITY", str(f.get("frontier_id") or f.get("title") or "?"), 1,
            (str(f.get("firm") or ""),),
            why=("maps to no capability group: either the extraction failed to name one, or the "
                 "ontology is short a category. A cluster of these is the second, and the "
                 "ontology is edited once rather than per article")))
    return out


def unaddressed_capabilities() -> list[Unknown]:
    """Capability groups the ontology names and this desk has NO module for.

    KNOWABLE WITHOUT CRAWLING ANYTHING, which is what makes this the cheapest high-value query in
    the package: it is a fact about our own tree. "We are weak at execution research" is an
    opinion; "no module on this desk addresses MARKET_IMPACT" is a measurement, and it is the kind
    of gap that stays open for years precisely because nothing ever names it.
    """
    return [Unknown("UNADDRESSED", name, 0, (),
                    why=(f"{ontology.BY_NAME[name].what} -- and no module on this tree owns it. "
                         f"Not a weakness: a category of work never started"))
            for name in ontology.unaddressed()]


def record_candidates(rows: list[Unknown], path: Path | None = None) -> int:
    """Append discovered unknowns, so a candidate found once is not rediscovered for ever."""
    p = CANDIDATES if path is None else path
    if not rows:
        return 0
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({"kind": r.kind, "name": r.name, "mentions": r.mentions,
                                     "seen_with": list(r.seen_with), "why": r.why}) + "\n")
    except OSError:
        return 0
    return len(rows)


def survey(texts: list[str] | None = None,
           findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every unknown lane in one pass, with the exploration budget attached.

    Returns the three lanes and the fraction of the cycle reserved for them. THE BUDGET IS
    REPORTED RATHER THAN ENFORCED HERE: this module discovers, the supervisor spends. A discovery
    module that also controlled the schedule would be able to justify its own budget.
    """
    firms = unknown_firms(texts or [])
    caps = unknown_capabilities(findings or [])
    unaddressed = unaddressed_capabilities()
    return {
        "exploration_fraction": EXPLORATION_FRACTION,
        "why_reserved": ("the score of an unknown is computed by a model that by construction "
                         "does not know about it, so a purely scored queue spends zero here and "
                         "the miner converges on confirming what it already believed"),
        "unknown_firms": [u.__dict__ for u in firms],
        "unknown_capabilities": [u.__dict__ for u in caps],
        "unaddressed_capabilities": [u.__dict__ for u in unaddressed],
        "counts": {"firms": len(firms), "capabilities": len(caps),
                   "unaddressed": len(unaddressed)},
    }
