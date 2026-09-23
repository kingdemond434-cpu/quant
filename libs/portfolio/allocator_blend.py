"""BLEND THE ALLOCATORS BY HOW LIKELY EACH IS TO BE BEST, instead of winner-take-all.

    "Take it to A*_t = argmax_A E[log W | X_t, A]. Better still, don't necessarily
     winner-take-all. Learn w_A = P(A is best | X_t) and blend allocations. Then your portfolio
     allocator itself becomes an ensemble."               -- the principal, 2026-09-07

WHAT `allocator_proof.select` DOES TODAY, and why it throws information away. It returns ONE
source name -- "dynamic" if the dynamic book beat the bench in this state, otherwise the single
challenger that did. The certificate it reads carries a score for EVERY contested book (HRP,
HERC, min-variance, mean-CVaR, three Kellys, the multi-period posterior book, equal-weight,
inverse-vol, risk parity, the incumbent), and `select` uses exactly one of them and discards the
rest. When HRP scores 0.00191 and mean-CVaR scores 0.00190, picking HRP outright is a claim the
evidence does not support: those two numbers are the same number.

THE TEMPERATURE IS NOT A NEW KNOB, AND THAT IS THE WHOLE DESIGN. The blend is

    w_A  proportional to  exp( (score_A - score_best) / (MARGIN_FRAC * |score_best|) )

where MARGIN_FRAC is the desk's OWN already-declared noise margin -- the fraction of the
incumbent's growth rate that `allocator_proof` demands before it calls one book better than
another, and the same bar `pf_allocator.marginal_admission` uses to refuse a candidate. Books
within one margin of the best are near-indistinguishable and share; a book ten margins below gets
e^-10 and effectively nothing. Nobody chose a temperature: the desk had already stated what
"different enough to matter" means and this reuses it.

THREE PROPERTIES THAT MAKE BLENDING SAFE, and each is a consequence rather than a hope:

  * RUIN IS CONVEX, SO THE BLEND CANNOT INVENT IT. Ruin in a world is `1 + h'r <= 0`, which is
    LINEAR in h. If every book in the mixture survives a world, so does every convex combination
    of them -- exactly, not approximately. A blend of non-ruinous books is non-ruinous.
  * TOTAL HEAT IS PRESERVED EXACTLY. Convex weights over books that all sum to H give a book that
    sums to H, so the blend cannot smuggle exposure past `heat_policy.resolve`.
  * IT DEGENERATES TO TODAY'S BEHAVIOUR. One dominant book takes essentially all the weight and
    the blend IS the winner; one scorable book takes all of it by construction. So this can only
    change the answer where the evidence was genuinely ambiguous, which is the only place it
    should.

THE CERTIFICATION LAW IS NOT LOOSENED, AND THIS IS THE CLAUSE THAT MATTERS MOST. A book that LOST
its state does not get a small weight back -- it is excluded from the mixture entirely. Blending
the dynamic allocator in at 15% after the proof refused it in this state would grant, quietly and
fractionally, exactly the authority the proof denied. `eligible` is decided by the certificate
before any arithmetic happens here.

NOTHING HERE SIZES OR SOLVES. It mixes books somebody else already solved and certified, at the
heat somebody else already resolved.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "MIN_WEIGHT",
    "blend_books",
    "blend_weights",
    "select_blend",
]

#: Weight below which a book is dropped from the mixture rather than carried at a sliver. A book
#: at 0.4% of the blend moves no position the broker can express (the desk's lot floor is 0.01)
#: and only adds names to the artifact. Dropped weight is renormalised across the survivors.
MIN_WEIGHT = 0.02


def blend_weights(scores: Mapping[str, Any], *, margin_frac: float,
                  eligible: Sequence[str] | None = None,
                  min_weight: float = MIN_WEIGHT) -> tuple[dict[str, float], str]:
    """P(A is best) as a softmax over scores at the desk's own noise margin. Returns (w, why).

    `scores` maps a book name to its score in this state. A non-finite score is a book that was
    wiped out in a sampled world; it is EXCLUDED rather than floored, because "least ruinous" is
    not a ranking -- `allocator_proof.select` already refuses to treat it as one.

    `eligible` restricts the mixture to the books the certificate permits in this state. Omit it
    and every scorable book is eligible, which is the right default for a caller that has already
    filtered.
    """
    ok: dict[str, float] = {}
    for name, raw in (scores or {}).items():
        if eligible is not None and str(name) not in set(eligible):
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            ok[str(name)] = v
    if not ok:
        return {}, "no book carries a finite score here: nothing to blend and nothing to size"
    best_name = max(ok, key=lambda k: ok[k])
    best = ok[best_name]
    if len(ok) == 1:
        return {best_name: 1.0}, f"{best_name} is the only scorable book here"
    # The scale is the desk's own noise margin ON THE BEST SCORE. A near-zero best score would
    # make the scale zero and the softmax a hard argmax -- which is the correct degenerate
    # behaviour (nothing is distinguishable from nothing), so it is allowed rather than floored
    # into a fake spread.
    scale = abs(best) * float(margin_frac)
    if not math.isfinite(scale) or scale <= 0:
        return {best_name: 1.0}, (f"the best score is {best:.6g}: no measurable scale to blend "
                                  f"over, so {best_name} takes the book outright")
    raw_w = {k: math.exp(max((v - best) / scale, -50.0)) for k, v in ok.items()}
    total = sum(raw_w.values())
    w = {k: v / total for k, v in raw_w.items()}
    kept = {k: v for k, v in w.items() if v >= float(min_weight)}
    if not kept:
        kept = {best_name: 1.0}
    tot = sum(kept.values())
    w = {k: round(v / tot, 6) for k, v in kept.items()}
    top = sorted(w.items(), key=lambda kv: -kv[1])
    return w, (f"{len(w)} book(s) within the {margin_frac:.0%} noise margin of {best_name} "
               f"({best:.6g}/day): " + ", ".join(f"{k} {v:.0%}" for k, v in top[:5])
               + (f" (+{len(w) - 5} more)" if len(w) > 5 else ""))


def blend_books(books: Mapping[str, Mapping[str, float]],
                weights: Mapping[str, float]) -> dict[str, float]:
    """The convex mixture of the named books. Missing sleeves count as zero heat, correctly.

    A book that does not hold a sleeve holds ZERO of it, so the mixture's weight on that sleeve is
    the weighted average including those zeros -- not the average over the books that happen to
    hold it. The second reading would let a sleeve held by one book at 4% appear in the blend at
    4% however little weight that book carries, which is how an ensemble quietly becomes its most
    concentrated member.
    """
    names: set[str] = set()
    for b in books.values():
        if isinstance(b, Mapping):
            names.update(str(k) for k in b)
    out: dict[str, float] = {}
    for sleeve in sorted(names):
        acc = 0.0
        for book, w in weights.items():
            b2 = books.get(book)
            if isinstance(b2, Mapping):
                acc += float(w) * float(b2.get(sleeve, 0.0) or 0.0)
        if acc > 0.0:
            out[sleeve] = acc
    return out


def select_blend(cert: Mapping[str, Any] | None, state: str | None, *,
                 margin_frac: float, min_weight: float = MIN_WEIGHT) -> dict[str, Any]:
    """The ENSEMBLE book for this state: which allocators, at what weights, and why.

    Layered on `allocator_proof.select` rather than replacing it -- that function decides
    AUTHORITY (who may size here at all, and it is the one the certification law runs through),
    and this decides the MIXTURE among the books that authority admits. When `select` returns a
    single winner and no other book is close, this returns that winner at weight 1.0 and the
    caller cannot tell the difference.

    Returns `{"book", "weights", "source", "why", "status"}`. `book` is empty whenever no book may
    size -- no certificate, no scorable book, or an entry the proof refused -- and an empty book
    is a refusal, never a reason to fall back to an unblended one.
    """
    from libs.portfolio.allocator_proof import select as _select

    src, why = _select(cert, state)
    if not src:
        return {"book": {}, "weights": {}, "source": "", "status": "REFUSED", "why": why}
    if not isinstance(cert, Mapping):
        return {"book": {}, "weights": {}, "source": "", "status": "REFUSED",
                "why": "no certificate"}

    books = cert.get("books") or {}
    by_state = cert.get("by_state") or {}
    entry: Mapping[str, Any] | None = None
    if state and isinstance(by_state, Mapping) and isinstance(by_state.get(state), Mapping):
        entry = by_state[state]
    scores = (entry or {}).get("scores") or cert.get("scores") or {}

    # THE ELIGIBLE SET IS THE CERTIFICATE'S, NOT THIS FUNCTION'S. When `select` named a challenger
    # the dynamic book LOST here, so it is excluded outright: a book the proof refused in this
    # state does not get a fractional weight back. That would be the certification law loosened by
    # arithmetic, which is the one way this module could do harm.
    eligible = [k for k in scores if k in books or k == "dynamic"]
    if src != "dynamic":
        eligible = [k for k in eligible if k != "dynamic"]
        law = "dynamic lost this state and is EXCLUDED from the mixture, not down-weighted"
    else:
        law = "dynamic won this state and competes in the mixture on its score"

    w, blend_why = blend_weights(scores, margin_frac=margin_frac, eligible=eligible,
                                 min_weight=min_weight)
    if not w:
        return {"book": {}, "weights": {}, "source": src, "status": "REFUSED",
                "why": f"{why}; {blend_why}"}
    if set(w) == {src} or len(w) == 1:
        only = next(iter(w))
        return {"book": {str(k): float(v) for k, v in (books.get(only) or {}).items()},
                "weights": {only: 1.0}, "source": only, "status": "SINGLE",
                "why": f"{why}; {blend_why}"}

    pool = {k: books.get(k) or {} for k in w if isinstance(books.get(k), Mapping)}
    missing = [k for k in w if k not in pool]
    if missing:
        # A weight on a book whose composition the certificate did not record cannot be spent.
        # Renormalise over what IS recorded and say which names were dropped -- silently
        # rescaling would hand their weight to the others without saying so.
        w = {k: v for k, v in w.items() if k in pool}
        tot = sum(w.values())
        if tot <= 0:
            return {"book": {}, "weights": {}, "source": src, "status": "REFUSED",
                    "why": f"{why}; no blended book's composition is on the certificate"}
        w = {k: round(v / tot, 6) for k, v in w.items()}
    mixed = blend_books(pool, w)
    return {
        "book": mixed, "weights": w, "source": "blend", "status": "BLENDED",
        "n_books": len(w), "total_heat": round(sum(mixed.values()), 6),
        "dropped_no_composition": missing,
        "why": (f"{why}; ENSEMBLE: {blend_why}. {law}. Ruin is linear in h, so a convex mixture "
                "of books that survive a world survives it too, and the mixture holds the same "
                "total heat every member holds."),
    }
