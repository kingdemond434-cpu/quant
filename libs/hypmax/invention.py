"""AUTONOMOUS FEATURE INVENTION -- compose primitives into features nobody wrote down.

WHY COMPOSITION AND NOT GENERATION. A model asked for "new features" returns the features that
appear most often in its training data -- momentum, RSI, realised vol -- which is precisely the
crowded set. Composition inverts that: take the primitives the desk actually owns (its own moat
reconstructions among them), cross them with transforms and windows, and the resulting space is
combinatorially larger than anything anybody has published, because most of its members are
things no human bothered to name.

THE HARD PART IS NOT INVENTING, IT IS REFUSING. The space is enormous and mostly worthless, so
every guard here exists to throw candidates away:

  REDUNDANCY. A feature that is a monotone transform of one already in the library is not a new
  feature, and the gauntlet cannot tell them apart -- it will faithfully rediscover the same edge
  and count it twice, which is how a desk builds a "diversified" book of one bet.

  DEGENERACY. window=1 rolling means, z-scores of constants, ratios that are always 1. These
  produce clean-looking series with no information and they never announce themselves.

  PROVENANCE. A feature composed from proprietary primitives is worth more than the identical
  composition over public data, because its replication cost is unbounded. Ranked accordingly --
  moat-derived features lead.

NO PROMOTION AUTHORITY. Everything here is a CANDIDATE feature. Whether it predicts anything is
a question for the screen, and inventing a feature confers exactly zero standing.

Pure, dependency-free.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass

__all__ = [
    "PRIMITIVES",
    "TRANSFORMS",
    "WINDOWS",
    "Feature",
    "info_class",
    "invent",
    "is_degenerate",
    "is_moat",
    "redundant_with",
]

#: primitive -> (information class, is it moat-derived). The CLASS is what makes interactions
#: refusable: two quantities read off the same underlying observation are not two sources of
#: information, and crossing them produces a smooth function of one wearing the costume of two.
#: `moat=True` means it is reconstructed from the desk's own recorded books, so a competitor
#: cannot obtain it for a past date at any price.
PRIMITIVES: dict[str, tuple[str, bool]] = {
    "withdrawal_rate":        ("book", True),
    "replenishment_halflife": ("book", True),
    "book_slope":             ("book", True),
    "imbalance":              ("book", True),
    "microprice_gap":         ("book", True),
    "effective_spread":       ("book", True),
    "resting_stability":      ("book", True),
    "funding_rate":           ("derivatives", False),
    "open_interest":          ("derivatives", False),
    "basis":                  ("derivatives", False),
    "volume":                 ("flow", False),
    "taker_ratio":            ("flow", False),
    "realised_vol":           ("price", False),
}


def info_class(primitive: str) -> str:
    return PRIMITIVES.get(primitive, ("unknown", False))[0]


def is_moat(primitive: str) -> bool:
    return PRIMITIVES.get(primitive, ("unknown", False))[1]


#: Transforms that change WHAT a series says, not merely its scale. `level` and `zscore` of the
#: same series are near-duplicates for any rank-based screen, so `level` is deliberately absent:
#: including it would double the candidate count and add nothing a rank IC could see.
TRANSFORMS: tuple[str, ...] = (
    "zscore",        # where it sits in its own recent distribution
    "delta",         # how fast it is changing
    "accel",         # whether the change is accelerating -- second derivative, rarely used
    "rank",          # cross-sectional position among symbols
    "dispersion",    # cross-sectional spread: a regime measure, not a symbol measure
    "asymmetry",     # skew of its own recent distribution
    "persistence",   # autocorrelation: how sticky the state is
)

#: Windows in snapshots. Spans three orders of magnitude because the horizon at which a
#: microstructure quantity carries information is exactly what nobody knows in advance.
WINDOWS: tuple[int, ...] = (5, 20, 60, 240, 1440)


@dataclass(frozen=True)
class Feature:
    """One composed candidate. `fingerprint` is what dedupes it across runs and organs."""

    name: str
    primitive: str
    transform: str
    window: int
    interaction: str = ""          # second primitive, when this is a cross-term
    moat_derived: bool = False

    @property
    def fingerprint(self) -> str:
        ops = sorted([self.primitive, self.interaction])
        parts = "|".join([*ops, self.transform, str(self.window)])
        return hashlib.sha1(parts.encode()).hexdigest()[:12]


def is_degenerate(f: Feature) -> str:
    """Reason this composition cannot carry information, or "" if it can.

    Cheap arithmetic checks only, done BEFORE any data is touched. Each of these produces a
    clean-looking series that a screen will happily evaluate -- and a screen's time is the
    scarcest thing here, so a candidate that cannot possibly work must never reach it.
    """
    if f.window <= 1 and f.transform in ("zscore", "dispersion", "asymmetry", "persistence"):
        return f"{f.transform} over a window of {f.window} has no distribution to measure"
    if f.transform == "accel" and f.window < 3:
        return "a second difference needs at least three observations"
    if f.interaction and f.interaction == f.primitive:
        return "a primitive crossed with itself is a transform of itself, not an interaction"
    if f.transform in ("rank", "dispersion") and f.interaction:
        return (f"{f.transform} is cross-sectional; crossing it with another primitive mixes "
                "two different axes and the result means nothing in particular")
    if f.interaction and info_class(f.primitive) == info_class(f.interaction):
        # THE GUARD THAT DOES THE MOST REFUSING, and the one worth arguing for. Two book
        # quantities are two readings of ONE observation -- imbalance and microprice_gap are
        # both functions of the same top-of-book sizes, so their product is a smooth function
        # of the book wearing the costume of an interaction. A cross-CLASS term is different in
        # kind: it asks whether the book agrees with the derivatives market, which is a
        # question neither source can answer alone.
        return (f"both primitives are '{info_class(f.primitive)}' -- same observation read "
                "twice, so the interaction carries no information the single term lacks")
    return ""


def redundant_with(f: Feature, existing: list[Feature]) -> Feature | None:
    """The library member this feature would duplicate, or None.

    SAME PRIMITIVE SET, SAME TRANSFORM, ADJACENT WINDOW is the redundancy that matters. A
    20-period and a 24-period z-score of the same quantity are the same feature; the screen will
    find the same edge in both and the desk will believe it has two. That is not a diversified
    book, it is one bet counted twice -- and the error compounds through every downstream
    allocation.
    """
    for e in existing:
        if e.fingerprint == f.fingerprint:
            return e
        same_inputs = ({e.primitive, e.interaction} == {f.primitive, f.interaction}
                       and e.transform == f.transform)
        if same_inputs and e.window and f.window:
            ratio = max(e.window, f.window) / min(e.window, f.window)
            if ratio < 1.5:            # within 50%: not a different horizon, a different rounding
                return e
    return None


def invent(existing: list[Feature] | None = None, *, limit: int = 200,
           include_interactions: bool = True) -> dict:
    """Compose the space and return what SURVIVES the guards, plus what did not and why.

    Rejections are returned because "we invented 200 features" and "we invented 200 from 4,000
    compositions, 3,800 rejected as degenerate or redundant" describe different systems, and only
    the second lets anyone see the guards are working. A silent filter is indistinguishable from
    a broken one.

    Ordering is by REPLICATION COST, not by novelty: a moat-derived composition and a public-data
    composition may be equally novel, and only one of them is defensible for longer than it takes
    a competitor to read the same public feed.
    """
    have = list(existing or [])
    kept: list[Feature] = []
    degenerate: list[dict] = []
    redundant: list[dict] = []
    n_composed = 0

    singles = [(p, "") for p in PRIMITIVES]
    pairs = ([(a, b) for a, b in itertools.combinations(PRIMITIVES, 2)]
             if include_interactions else [])
    for prim, inter in singles + pairs:
        for tr in TRANSFORMS:
            for w in WINDOWS:
                n_composed += 1
                moat = is_moat(prim) or (bool(inter) and is_moat(inter))
                name = (f"{tr}({prim}" + (f" x {inter}" if inter else "") + f", {w})")
                f = Feature(name=name, primitive=prim, transform=tr, window=w,
                            interaction=inter, moat_derived=bool(moat))
                why = is_degenerate(f)
                if why:
                    degenerate.append({"name": name, "reason": why})
                    continue
                dup = redundant_with(f, have + kept)
                if dup is not None:
                    redundant.append({"name": name, "duplicates": dup.name})
                    continue
                kept.append(f)

    # Replication cost first, then the rarer transforms -- `accel` and `persistence` are the two
    # nobody computes, which is exactly why they are where an unclaimed edge would be hiding.
    rare = {"accel": 0, "persistence": 1, "asymmetry": 2, "dispersion": 3}
    kept.sort(key=lambda f: (not f.moat_derived, rare.get(f.transform, 9), f.window))
    return {
        "composed": n_composed,
        "kept": kept[:limit],
        "n_kept": len(kept),
        "n_degenerate": len(degenerate),
        "n_redundant": len(redundant),
        "degenerate_examples": degenerate[:8],
        "redundant_examples": redundant[:8],
        "moat_derived_kept": sum(1 for f in kept if f.moat_derived),
        "note": ("candidates only. Ranked by REPLICATION COST rather than novelty -- a "
                 "moat-derived composition and a public-data one can be equally novel and only "
                 "one stays defensible once a competitor reads the same feed. Whether any of "
                 "them predicts anything is a question for the screen."),
    }
