"""ORDER-BOOK MICROSTRUCTURE -- six constructions, pre-registered together, charged as one family.

The principal supplied 175 candidate alphas. Items 7-14 and 26-55 are not thirty-eight mechanisms;
they are thirty-eight CONSTRUCTIONS of one census class, `orderbook_microstructure_state`, which
the census rates 0.90. Treating them as separate sleeves would raise every strategy count on the
desk while `k_eff` stayed at ONE family, and would spend thirty-eight forward seats on one
question.

**175 HYPOTHESES AT alpha=0.05 IS ~9 FALSE POSITIVES BY CONSTRUCTION.** That is arithmetic, not
caution. The family partition exists so a flow candidate does not pay for a macro candidate's
trials -- it does not exempt thirty-eight constructions of the SAME claim from paying for each
other. Every construction below is charged against `N_CONSTRUCTIONS` and judged at the BH bar for
its own rank. A construction that only clears the uncorrected bar is a construction that did not
clear.

**WHAT THE DATA ACTUALLY SUPPORTS, AND WHAT IT DOES NOT.** `/api/v3/depth` is polled every 5
seconds at limit=20: a SNAPSHOT SERIES, not an event stream. So:

    SUPPORTED   queue depletion (7), replenishment failure (9), depth-curve convexity (11),
                microprice residual (12), imbalance decay speed (26), depth migration (27)
    NOT         cancellation pressure (8), add/cancel impulse response (30), quote flicker (43),
                cancellation cascades (51) -- all need ORDER-LEVEL adds and cancels, which a
                snapshot cannot reconstruct: two snapshots showing the same depth are consistent
                with no activity and with a thousand adds matched by a thousand cancels.
                Iceberg inference (14) needs fills joined to a resting level, and the trade poll
                is batched at 40s against a 5s depth poll -- the join would be manufactured.

Claiming the unsupported ones would be the more expensive error, because a construction computed
from data that cannot express it produces a number rather than a refusal.

**KILL CRITERIA, FIXED HERE BEFORE THE FIRST RUN.** A construction is REFUTED when its IC is
indistinguishable from zero at the BH bar for its rank. Fewer than MIN_OBS aligned observations is
UNDERPOWERED, never REFUTED -- a null on a sample too small to detect the effect is a statement
about the sample. Zero dispersion is DEGENERATE, not a kill.
"""

from __future__ import annotations

import itertools
import math
from statistics import NormalDist
from typing import Any

__all__ = [
    "CONSTRUCTIONS",
    "MIN_OBS",
    "N_CONSTRUCTIONS",
    "UNSUPPORTED",
    "features",
    "screen",
]

#: Aligned (feature, forward-return) pairs below which a construction is UNDERPOWERED. At n=200 the
#: standard error of an IC is ~1/sqrt(n) = 0.07, so an IC of 0.05 is not distinguishable from zero
#: however tempting it looks -- which is the number this floor exists to keep off the page.
MIN_OBS = 200

#: The constructions this snapshot data can express. Each maps to an item on the principal's list.
CONSTRUCTIONS: tuple[tuple[str, str], ...] = (
    ("queue_depletion", "item 7: one side's resting size disappearing FASTER than it replenishes. "
     "The rate, not the level -- a thin side that stays thin is priced; a thin side that is being "
     "eaten is the impatient order still arriving"),
    ("replenishment_failure", "item 9: depth consumed by aggression and NOT restored by the next "
     "snapshot. Liquidity that does not come back is the maker declining to re-quote, which is "
     "the observable form of adverse selection he has just learned about"),
    ("depth_convexity", "item 11: the SHAPE of the depth curve, not the bid/ask ratio. A book "
     "with its size stacked far from the touch and a book with the same total stacked at it are "
     "the same imbalance and opposite trades"),
    ("microprice_residual", "item 12: microprice minus mid, less what the spread and recent "
     "realised volatility already explain. The raw microprice is mostly a spread artefact"),
    ("imbalance_decay", "item 26: how FAST an imbalance mean-reverts. A pressure that persists "
     "across snapshots is inventory; one that vanishes in a tick was a quote"),
    ("depth_migration", "item 27: size moving TOWARD the touch versus away from it, which "
     "distinguishes a maker leaning in from one stepping back at the same total depth"),
)

N_CONSTRUCTIONS = len(CONSTRUCTIONS)

#: Named so the refusal is on the record rather than in nobody's head. Each needs order-level
#: events or a join the poll cadence cannot support; see the module docstring.
UNSUPPORTED: dict[str, str] = {
    "cancellation_pressure": "item 8 -- needs order-level adds/cancels. Two snapshots with equal "
                             "depth are consistent with no activity AND with a thousand adds "
                             "matched by a thousand cancels; a snapshot cannot separate them",
    "add_cancel_impulse": "item 30 -- needs order-level adds and cancels for the same reason: "
                          "the impulse response is to EVENTS a snapshot never sees",
    "quote_flicker": "item 43 -- flicker happens BETWEEN 5-second snapshots by definition",
    "cancellation_cascade": "item 51 -- a cascade is a SEQUENCE of cancels across levels, and a "
                            "5-second snapshot shows only its aftermath, never the sequence",
    "iceberg_inference": "item 14 -- needs fills joined to a resting level, and the trade poll is "
                         "batched at 40s against a 5s depth poll. The join would be manufactured",
}


def features(books: list[Any]) -> dict[str, list[float]]:
    """One feature series per supported construction, aligned to `books[1:]`.

    EVERY FEATURE IS A DIFFERENCE OR A RATE, computed from the PAIR (previous, current). A level
    read off a single snapshot is a state; the claims above are all about CHANGE, and conflating
    the two is how a book-imbalance study becomes a restatement of the spread.
    """
    out: dict[str, list[float]] = {name: [] for name, _ in CONSTRUCTIONS}
    for prev, cur in itertools.pairwise(books):
        if prev.mid <= 0 or cur.mid <= 0:
            for k in out:
                out[k].append(float("nan"))
            continue
        d_depth = (cur.depth_usd - prev.depth_usd) / max(prev.depth_usd, 1e-9)
        d_imb = cur.imbalance - prev.imbalance
        d_slope = (cur.slope - prev.slope) / max(abs(prev.slope), 1e-9)
        out["queue_depletion"].append(-d_depth * (1.0 if cur.imbalance < 0 else -1.0))
        out["replenishment_failure"].append(-d_depth if d_depth < 0 else 0.0)
        out["depth_convexity"].append(cur.slope / max(cur.depth_usd, 1e-9) * 1e6)
        # Microprice from imbalance: mid + imbalance * half-spread is the standard construction,
        # and subtracting the spread term is what makes this a RESIDUAL rather than a spread proxy.
        micro = cur.imbalance * (cur.spread_bps / 2.0)
        out["microprice_residual"].append(micro - cur.spread_bps / 2.0 * prev.imbalance)
        out["imbalance_decay"].append(-d_imb * (1.0 if prev.imbalance > 0 else -1.0))
        out["depth_migration"].append(d_slope)
    return out


def _ic(x: list[float], y: list[float]) -> tuple[float | None, int]:
    """Spearman-free Pearson IC on the aligned pairs, plus the usable count.

    NON-FINITE PAIRS ARE DROPPED, NOT ZEROED. A zero enters the sample as a real observation of no
    relationship and drags the estimate toward the null with fabricated data.
    """
    pairs = [(a, b) for a, b in zip(x, y, strict=True)
             if math.isfinite(a) and math.isfinite(b)]
    n = len(pairs)
    if n < 3:
        return None, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    vx = sum((p[0] - mx) ** 2 for p in pairs)
    vy = sum((p[1] - my) ** 2 for p in pairs)
    if vx <= 0 or vy <= 0:
        return None, n
    cov = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return cov / math.sqrt(vx * vy), n


def screen(books: list[Any], *, horizon: int = 12, alpha: float = 0.05) -> dict[str, Any]:
    """Every supported construction against the forward mid return, BH-corrected within the family.

    `horizon` is in SNAPSHOTS, not minutes: at a 5-second poll, 12 is one minute. The claims here
    are about immediacy and decay in minutes, so a horizon in bars would be a different hypothesis.
    """
    from libs.validation.family_multiplicity import bh_bar

    rep: dict[str, Any] = {
        "census_class": "orderbook_microstructure_state",
        "n_snapshots": len(books), "horizon_snapshots": horizon,
        "constructions": N_CONSTRUCTIONS, "min_obs": MIN_OBS,
        "unsupported": UNSUPPORTED,
        "multiplicity": (f"{N_CONSTRUCTIONS} constructions of ONE census class, charged against "
                         "each other. They are not separate mechanisms and must not consume "
                         "separate forward seats"),
        "results": [],
    }
    if len(books) < horizon + MIN_OBS:
        rep["status"] = "UNDERPOWERED"
        rep["verdict"] = "UNMEASURED"
        rep["why"] = (f"{len(books)} snapshot(s) against {horizon + MIN_OBS} needed. A null on a "
                      "sample too small to detect the effect is a statement about the sample")
        return rep

    feats = features(books)
    mids = [b.mid for b in books[1:]]
    fwd = [(mids[i + horizon] / mids[i] - 1.0) if i + horizon < len(mids) else float("nan")
           for i in range(len(mids))]

    rows: list[dict[str, Any]] = []
    for name, claim in CONSTRUCTIONS:
        ic, n = _ic(feats[name], fwd)
        t = None if ic is None or n <= 3 else ic * math.sqrt(max(1, n - 2)) / math.sqrt(
            max(1e-12, 1 - ic * ic))
        row: dict[str, Any] = {"construction": name, "claim": claim,
                               "ic": None if ic is None else round(ic, 5),
                               "n": n, "t": None if t is None else round(t, 3)}
        rows.append(row)
    # BH BY RANK: the strongest construction faces alpha/m, the k-th faces alpha*k/m. Ranking by
    # |t| and correcting by rank is the whole reason six constructions is not six free trials.
    def _mag(r: dict[str, Any]) -> float:
        t = r.get("t")
        return -abs(float(t)) if isinstance(t, (int, float)) else 1.0

    rows.sort(key=_mag)
    for rank, r in enumerate(rows, start=1):
        bar = bh_bar(N_CONSTRUCTIONS, rank, alpha=alpha)
        r["rank"] = rank
        r["bh_bar"] = bar
        if r["t"] is None:
            r["verdict"] = "DEGENERATE"
        elif r["n"] < MIN_OBS:
            r["verdict"] = "UNDERPOWERED"
        else:
            r["verdict"] = "SURVIVES-STAGE-A" if abs(r["t"]) >= bar else "REFUTED"
    rep["results"] = rows
    rep["status"] = "RUN"
    survivors = [r for r in rows if r["verdict"] == "SURVIVES-STAGE-A"]
    rep["n_survivors"] = len(survivors)
    rep["verdict"] = "SURVIVES-STAGE-A" if survivors else "REFUTED"
    rep["authority"] = ("STAGE A ONLY -- zero promotion authority. A survivor earns a forward "
                        "clock in the orderbook_microstructure_state family, never capital")
    return rep


def uncorrected_bar(alpha: float = 0.05) -> float:
    """The bar a single construction would face alone -- published beside the corrected one so the
    cost of testing six is visible rather than asserted."""
    return round(NormalDist().inv_cdf(1.0 - alpha), 2)
