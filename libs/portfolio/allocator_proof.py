"""The dynamic allocator must BEAT the simple answers before it may size anything.

    from libs.portfolio.allocator_proof import contest, certify

WHY THIS GATES AUTHORITY. A dynamic allocator is the highest-variance component a desk can add:
it sits above every edge and reallocates, so it can destroy compounding faster than any single
sleeve can. The only honest defence is the one this module implements -- make it compete, on the
desk's own sampled worlds, against the allocations anyone could have written in an afternoon:

    EQUAL WEIGHT      the null hypothesis of allocation
    INVERSE VOL       the cheapest real risk adjustment there is
    STATIC INCUMBENT  what the desk is holding right now, i.e. doing nothing
    RISK PARITY       equal risk contribution, the standard institutional answer

If the optimiser cannot beat those four after costs, its extra machinery is not earning its
variance and it should not be sizing positions. That is not a philosophical position: measured
across many desks, most dynamic allocators lose to inverse-vol once turnover is charged.

THE CONTEST IS FAIR BY CONSTRUCTION. Every book is scored by `score_book` on the SAME world
population, from the SAME evidence, with the SAME objective and the SAME total heat. Only the
weights differ. Scoring the dynamic book on its own optimised worlds and the baselines on
freshly drawn ones would be the classic rigged comparison, so the worlds are drawn once and
passed to all five.

TOTAL HEAT IS EQUALISED, and this is the point most easily got wrong. An optimiser that simply
deploys MORE capital will beat every baseline on raw growth while being strictly worse per unit
of risk. Each baseline is therefore scaled to the dynamic book's own total heat, so the contest
measures ALLOCATION SKILL and nothing else.

WHAT A PASS DOES NOT MEAN. Beating four baselines on sampled worlds is evidence, not proof of
future superiority, and the certificate says so in its own text. It expires, so authority has to
be re-earned rather than granted once.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, Worlds, score_book

#: How much better than the BEST baseline the dynamic book must be, in robust score. Not zero:
#: a hair's-breadth win is inside the noise of a sampled-world estimate, and granting authority
#: on it would be granting it to luck. 2% of the baseline's own magnitude is small enough that a
#: genuinely better allocator clears it and large enough that a tie does not.
MARGIN_FRAC = 0.02

#: A certificate older than this is not evidence about today's book. The allocator re-solves
#: hourly on its heavy clock, so a day-old proof describes a book that no longer exists.
MAX_AGE_S = 26 * 3600

PROOF = "reports/ALLOCATOR_PROOF.json"


def _equal_weight(names: Sequence[str], total: float) -> dict[str, float]:
    return {n: total / len(names) for n in names} if names else {}


def _inverse_vol(ev: Sequence[SleeveEvidence], total: float) -> dict[str, float]:
    """Weight inversely to each sleeve's own daily volatility."""
    inv = []
    for e in ev:
        sd = float(np.std(e.daily_r, ddof=1)) if e.daily_r.size > 1 else 0.0
        inv.append(1.0 / sd if sd > 1e-12 else 0.0)
    s = sum(inv)
    if s <= 0:
        return _equal_weight([e.name for e in ev], total)
    return {e.name: total * v / s for e, v in zip(ev, inv, strict=True)}


def _risk_parity(ev: Sequence[SleeveEvidence], total: float) -> dict[str, float]:
    """Equal risk contribution under the measured covariance, by simple fixed-point iteration.

    Deliberately the textbook estimator rather than a tuned one. The baseline's job is to be the
    obvious thing a competent person would do; making it clever would flatter the optimiser by
    comparison to something nobody would actually have written.
    """
    n = len(ev)
    if n == 0:
        return {}
    m = min(len(e.daily_r) for e in ev)
    if m < 2:
        return _equal_weight([e.name for e in ev], total)
    x = np.vstack([np.asarray(e.daily_r[-m:], dtype=float) for e in ev])
    cov = np.cov(x)
    if cov.ndim == 0:
        cov = cov.reshape(1, 1)
    w = np.full(n, 1.0 / n)
    for _ in range(500):
        mrc = cov @ w
        mrc = np.where(np.abs(mrc) < 1e-15, 1e-15, mrc)
        w_new = 1.0 / mrc
        w_new = np.clip(w_new, 0.0, None)
        if w_new.sum() <= 0:
            return _equal_weight([e.name for e in ev], total)
        w_new /= w_new.sum()
        if np.max(np.abs(w_new - w)) < 1e-10:
            w = w_new
            break
        w = w_new
    return {e.name: float(total * wi) for e, wi in zip(ev, w, strict=True)}


def contest(ev: Sequence[SleeveEvidence], dynamic: Mapping[str, float],
            incumbent: Mapping[str, float] | None = None, *,
            cfg: WorldConfig | None = None,
            worlds: Worlds | None = None) -> dict[str, Any]:
    """Score the dynamic book against four baselines on one shared world population."""
    cfg = cfg or WorldConfig()
    names = [e.name for e in ev]
    total = float(sum(max(0.0, float(v)) for v in dynamic.values()))

    books: dict[str, Mapping[str, float]] = {
        "dynamic": dict(dynamic),
        "equal_weight": _equal_weight(names, total),
        "inverse_vol": _inverse_vol(ev, total),
        "risk_parity": _risk_parity(ev, total),
    }
    # STATIC INCUMBENT IS "DO NOTHING", so it is scored at the heat the desk ACTUALLY holds, not
    # rescaled to the dynamic total. Rescaling it would turn the do-nothing baseline into a
    # different, more-levered strategy nobody is running, and the question this baseline answers
    # is precisely whether moving at all was worth it.
    if incumbent:
        books["static_incumbent"] = dict(incumbent)
    # THE CHALLENGER BENCH (2026-09-04): HRP, HERC, min-variance, mean-CVaR and three Kellys,
    # all long-only at the same total heat. More rivals can only make the proof harder; the
    # dynamic book keeps authority by beating the best of them on these worlds.
    try:
        from libs.portfolio.challengers import all_books
        for k, b in all_books(ev, total).items():
            books.setdefault(k, b)
    except Exception:
        pass
    posterior_cert: dict[str, Any] | None = None
    if worlds is not None:
        try:
            from libs.portfolio.multiperiod_worlds import plan
            mp = plan(worlds, incumbent or {}, target=total, cap=max(total, 1e-9))
            h_now = {k: v for k, v in mp["h_now"].items() if v > 0}
            s = sum(h_now.values())
            if s > 0:
                books.setdefault("multiperiod", {k: v * total / s for k, v in h_now.items()})
        except Exception:
            pass
        # THE POSTERIOR CHALLENGER: the multi-period book solved over a posterior on worlds,
        # rescaled to the same total heat. When pf_allocator has already adopted it as the
        # dynamic book the two are one book, and a rival identical to the contestant is not a
        # rival -- it would make the margin unbeatable -- so it is only entered when distinct.
        try:
            from libs.portfolio.multiperiod_worlds import plan_posterior
            mp = plan_posterior(worlds, incumbent or {}, target=total, cap=max(total, 1e-9),
                                ev=ev)
            posterior_cert = mp.get("certificate")
            h_now = {k: v for k, v in mp["h_now"].items() if v > 0}
            s = sum(h_now.values())
            if s > 0:
                cand = {k: v * total / s for k, v in h_now.items()}
                keys = set(cand) | set(dynamic)
                same = all(abs(float(cand.get(k, 0.0)) - float(dynamic.get(k, 0.0))) < 1e-6
                           for k in keys)
                if not same:
                    books.setdefault("posterior", cand)
        except Exception:
            pass

    scored = {k: score_book(ev, b, cfg=cfg, worlds=worlds) for k, b in books.items()}
    dyn = scored["dynamic"]["robust_score"]
    rivals = {k: v["robust_score"] for k, v in scored.items() if k != "dynamic"}
    best_name = max(rivals, key=lambda k: rivals[k]) if rivals else ""
    best = rivals.get(best_name, float("-inf"))

    if not math.isfinite(dyn):
        passed, why = False, f"dynamic book has no finite robust score ({dyn!r})"
    elif not rivals:
        passed, why = False, "no baselines could be scored -- an uncontested win is not a win"
    elif not math.isfinite(best):
        # Every baseline ruinous and the dynamic book finite is a genuine, large win.
        passed, why = True, "every baseline is ruinous on these worlds; dynamic is finite"
    else:
        need = best + abs(best) * MARGIN_FRAC
        passed = dyn > need
        why = (f"dynamic {dyn:.6f} vs best baseline {best_name} {best:.6f} "
               f"(needs > {need:.6f}, margin {MARGIN_FRAC:.0%})")
    return {"passed": bool(passed), "why": why, "best_baseline": best_name,
            "scores": scored, "total_heat_equalised": total,
            "posterior_certificate": posterior_cert,
            # THE BOOKS THEMSELVES, so a failed proof can hand the floor to the best baseline
            # rather than to nothing (gateway.allocator_book reads `book_fallback`).
            "books": {k: {str(n): float(v) for n, v in b.items()} for k, b in books.items()}}


def certify(result: dict[str, Any], *, root: Path, book: Mapping[str, float]) -> Path:
    """Write the certificate the gateway must find before the book may size anything."""
    out = root / PROOF
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "passed": bool(result.get("passed")),
        "why": result.get("why", ""),
        "best_baseline": result.get("best_baseline", ""),
        "book": {k: float(v) for k, v in book.items()},
        "scores": result.get("scores", {}),
        "margin_frac": MARGIN_FRAC,
        "max_age_s": MAX_AGE_S,
        "note": ("Beating four baselines on sampled worlds is EVIDENCE, not proof of future "
                 "superiority. This certificate expires, so authority is re-earned rather than "
                 "granted once."),
    }, indent=1, default=str), encoding="utf-8")
    return out


def read_certificate(root: Path, *, now: float | None = None) -> tuple[dict[str, Any] | None, str]:
    """The live certificate, or None with the reason it may not be used. Fails closed."""
    import time as _time
    p = root / PROOF
    if not p.exists():
        return None, "no ALLOCATOR_PROOF.json -- the allocator has not beaten the baselines"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"ALLOCATOR_PROOF.json unreadable ({type(exc).__name__})"
    if not doc.get("passed"):
        return None, f"allocator did not beat the baselines: {doc.get('why', '')}"
    age = (now if now is not None else _time.time()) - p.stat().st_mtime
    if age > MAX_AGE_S:
        return None, f"proof is {age / 3600:.1f}h old (max {MAX_AGE_S / 3600:.0f}h)"
    return doc, f"proof {age / 3600:.1f}h old, beat {doc.get('best_baseline', '?')}"
