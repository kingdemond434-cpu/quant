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

THE PROOF IS CONDITIONAL ON THE MARKET (2026-09-05). One global certificate says "the dynamic
allocator beat the bench ON AVERAGE ACROSS ALL WORLDS", which is the wrong question: an optimiser
that is superb in trends and worse than inverse-vol in a fused, high-volatility state wins the
average and loses the desk money in the state it is actually in. So the contest is ALSO run per
admitted state bucket -- the worlds' own regime labels, stamped with whichever state dimensions
`reports/STATE_ADMISSION.json` has admitted -- and `certify` writes `by_state` beside the global
verdict:

    ProofCertificate(StateCluster)      per-bucket {passed, best, scores, n_worlds}
    select(cert, state_id) -> A*_t      the meta-allocator: argmax_A E[log W | X_t, A]

`select` returns "dynamic" in the buckets the dynamic book wins and the winning CHALLENGER's name
in the buckets it does not, so authority is held state by state instead of all-or-nothing. A
bucket too thin to judge falls back to the global verdict and says so; nothing is granted
authority by an unmeasured state.
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

#: Worlds a state bucket needs before a per-state verdict may be reached. At cvar_alpha 0.20 this
#: puts ~5 worlds in the CVaR tail; below it the "robust score" of a bucket is two draws wearing a
#: distribution, and a certificate granted on that would be authority handed to noise. Matches
#: `heat_policy.MIN_STATE_WORLDS` -- one number for "a bucket big enough to judge".
MIN_STATE_WORLDS = 24

PROOF = "reports/ALLOCATOR_PROOF.json"
#: Where the admitted state dimensions are recorded (`research/state_admission_run.py`). Read
#: fail-open: an unreadable report means the state id carries the regime alone, never that an
#: un-admitted dimension quietly starts conditioning capital.
STATE_ADMISSION = "desks/mt5/reports/STATE_ADMISSION.json"


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


# ------------------------------------------------------------------------------ state clusters
def state_id(now_buckets: Mapping[str, str] | None, regime: str) -> str:
    """The name of one market state: the admitted dimensions' current buckets plus the regime.

    STAMPED WITH THE STATE THE DESK IS IN, so a certificate earned in the London session during a
    bull trend can never be read as authority for the Asia session in a fused market. The admitted
    dimensions are constant across a pass (the desk is in one session now), so they are a prefix;
    the regime varies world by world, so it is the suffix `select` can fall back to matching on.
    """
    have = dict(now_buckets or {})
    parts = [f"{k}={have[k]}" for k in sorted(have) if have[k]]
    parts.append(f"regime={regime or 'unconditioned'}")
    return "|".join(parts)


def admitted_now(root: Path | None, now_buckets: Mapping[str, str] | None,
                 ) -> tuple[dict[str, str], str]:
    """The caller's current state buckets, filtered to the dimensions admission has ADMITTED.

    Fails open to the regime alone: an unreadable admission report withdraws every dimension from
    the state id rather than letting an unjudged one condition capital. That is the conservative
    direction here -- a coarser state means the certificate covers more worlds, never fewer.
    """
    if not now_buckets:
        return {}, "no state buckets offered by the caller"
    if root is None:
        return {}, "no desk root to read STATE_ADMISSION.json from; regime only"
    try:
        doc = json.loads((root / STATE_ADMISSION).read_text(encoding="utf-8"))
        ok = {str(d) for d in (doc.get("admitted") or [])}
    except (OSError, ValueError) as exc:
        return {}, f"STATE_ADMISSION.json unreadable ({type(exc).__name__}); regime only"
    kept = {k: str(v) for k, v in now_buckets.items() if k in ok and v}
    return kept, (f"admitted dimensions {sorted(ok) or '(none)'}; "
                  f"{len(kept)} of {len(now_buckets)} offered bucket(s) condition the state id")


def buckets_from_worlds(worlds: Worlds, now_buckets: Mapping[str, str] | None = None, *,
                        min_worlds: int = MIN_STATE_WORLDS) -> dict[str, list[int]]:
    """World indices grouped by state id. Buckets under `min_worlds` are dropped, not merged.

    Merging thin buckets into a residual "other" would invent a state nobody is ever in and then
    grant authority in it. A dropped bucket simply has no per-state verdict, and `select` falls
    back to the global one there.
    """
    labels = tuple(worlds.regimes) if worlds.regimes else ()
    if len(labels) != int(worlds.r.shape[0]):
        return {}
    out: dict[str, list[int]] = {}
    for i, lab in enumerate(labels):
        out.setdefault(state_id(now_buckets, str(lab)), []).append(i)
    return {k: v for k, v in out.items() if len(v) >= min_worlds}


def _subworlds(worlds: Worlds, idx: Sequence[int]) -> Worlds:
    """The same population restricted to one state's worlds -- same books, same costs, fewer
    draws. Nothing is re-sampled: re-drawing per bucket would compare books on different worlds,
    which is the rigged comparison this whole module exists to avoid."""
    take = np.asarray(list(idx), dtype=int)
    regimes = tuple(worlds.regimes[i] for i in take) if worlds.regimes else ()
    return Worlds(r=worlds.r[take], names=worlds.names, crisis=worlds.crisis[take],
                  mu_draws=worlds.mu_draws[take], regimes=regimes,
                  note=f"{worlds.note} | state subset of {take.size} world(s)")


def _judge(scored: Mapping[str, Mapping[str, float]]) -> tuple[bool, str, str]:
    """Did the dynamic book beat the best rival by the margin? Returns (passed, why, best_name).

    One arithmetic, used by the global verdict and by every per-state one, so a bucket can never
    be judged on a softer rule than the population it came from.
    """
    dyn = float(scored["dynamic"]["robust_score"])
    rivals = {k: float(v["robust_score"]) for k, v in scored.items() if k != "dynamic"}
    best_name = max(rivals, key=lambda k: rivals[k]) if rivals else ""
    best = rivals.get(best_name, float("-inf"))
    if not math.isfinite(dyn):
        return False, f"dynamic book has no finite robust score ({dyn!r})", best_name
    if not rivals:
        return False, "no baselines could be scored -- an uncontested win is not a win", best_name
    if not math.isfinite(best):
        # Every baseline ruinous and the dynamic book finite is a genuine, large win.
        return True, "every baseline is ruinous on these worlds; dynamic is finite", best_name
    need = best + abs(best) * MARGIN_FRAC
    return (dyn > need,
            f"dynamic {dyn:.6f} vs best baseline {best_name} {best:.6f} "
            f"(needs > {need:.6f}, margin {MARGIN_FRAC:.0%})", best_name)


def contest(ev: Sequence[SleeveEvidence], dynamic: Mapping[str, float],
            incumbent: Mapping[str, float] | None = None, *,
            cfg: WorldConfig | None = None,
            worlds: Worlds | None = None,
            state_buckets: Mapping[str, Sequence[int]] | None = None,
            now_buckets: Mapping[str, str] | None = None,
            root: Path | None = None) -> dict[str, Any]:
    """Score the dynamic book against every baseline on one shared world population.

    `state_buckets` maps a state id to the indices of the worlds drawn in that state; when it is
    not supplied the buckets are derived from the population's own regime labels, stamped with
    whichever of `now_buckets` the admission report has admitted. The same books, scored again on
    each bucket, give the per-state certificate -- no re-optimisation, no re-drawing.
    """
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
    passed, why, best_name = _judge(scored)

    # ------------------------------------------------------------------ the per-state contest
    by_state: dict[str, Any] = {}
    state_why = "no world population: the certificate is global only"
    if worlds is not None:
        kept, adm_why = admitted_now(root, now_buckets)
        buckets = (dict(state_buckets) if state_buckets is not None
                   else buckets_from_worlds(worlds, kept))
        state_why = (f"{len(buckets)} state bucket(s) of >= {MIN_STATE_WORLDS} worlds; {adm_why}"
                     if buckets else
                     f"no state bucket reached {MIN_STATE_WORLDS} worlds; {adm_why}")
        for sid, idx in sorted(buckets.items()):
            if len(idx) < MIN_STATE_WORLDS:
                continue
            try:
                sub = _subworlds(worlds, idx)
                s_scored = {k: score_book(ev, b, cfg=cfg, worlds=sub) for k, b in books.items()}
            except (IndexError, ValueError, KeyError) as exc:
                by_state[sid] = {"passed": False, "n_worlds": len(idx),
                                 "why": f"unscorable ({type(exc).__name__}: {exc})",
                                 "best": "", "scores": {}}
                continue
            s_passed, s_why, s_best = _judge(s_scored)
            by_state[sid] = {
                "passed": bool(s_passed), "why": s_why, "best": s_best,
                "n_worlds": len(idx),
                "scores": {k: round(float(v["robust_score"]), 8) for k, v in s_scored.items()},
            }
    return {"passed": bool(passed), "why": why, "best_baseline": best_name,
            "scores": scored, "total_heat_equalised": total,
            "posterior_certificate": posterior_cert,
            # PER-STATE VERDICTS. `select(cert, state_id)` reads these to pick A*_t; a state with
            # no entry falls back to the global verdict, never to an unmeasured claim.
            "by_state": by_state, "by_state_why": state_why,
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
        # THE CONDITIONAL CERTIFICATE, beside the global one and never instead of it: which
        # allocator won in which state, on how many worlds. `select` turns this into A*_t.
        "by_state": result.get("by_state", {}),
        "by_state_why": result.get("by_state_why", ""),
        "min_state_worlds": MIN_STATE_WORLDS,
        # Every contested book at the equalised heat, so a caller that `select`s a challenger can
        # size with it instead of only learning its name.
        "books": result.get("books", {}),
        "margin_frac": MARGIN_FRAC,
        "max_age_s": MAX_AGE_S,
        "note": ("Beating four baselines on sampled worlds is EVIDENCE, not proof of future "
                 "superiority. This certificate expires, so authority is re-earned rather than "
                 "granted once."),
    }, indent=1, default=str), encoding="utf-8")
    return out


def select(cert: Mapping[str, Any] | None, state: str | None) -> tuple[str, str]:
    """A*_t = argmax_A E[log W | X_t, A]: which allocator may size in THIS state, and why.

    Returns the book's SOURCE NAME -- "dynamic" or a challenger's key in `cert["books"]` -- so the
    caller sizes with the allocator that actually won here rather than with whichever one won the
    average. The order of preference, and each step is a refusal to over-claim:

        1. the state's own verdict, when the bucket was big enough to reach one: "dynamic" if it
           beat the bench there, otherwise the challenger that did;
        2. the same match on the REGIME suffix, when the desk's session/event buckets have moved
           but the regime has not -- the regime is what the worlds were drawn from, so it is the
           part of the state id the population actually knows about;
        3. the global verdict, which is what the desk had before this existed.

    An empty result is not a fallback to "dynamic": no certificate means no authority (the
    gateway's own fail-closed path), and that is returned as ("", why).
    """
    if not isinstance(cert, Mapping) or not cert:
        return "", "no certificate: the allocator may rank but not size"
    by_state = cert.get("by_state") or {}
    entry: Mapping[str, Any] | None = None
    matched = ""
    if state and isinstance(by_state, Mapping):
        if isinstance(by_state.get(state), Mapping):
            entry, matched = by_state[state], state
        else:
            suffix = state.split("|")[-1]
            hits = [k for k in by_state
                    if isinstance(by_state.get(k), Mapping) and str(k).endswith(suffix)]
            if len(hits) == 1:
                entry, matched = by_state[hits[0]], hits[0]
    if entry is not None:
        n = int(entry.get("n_worlds") or 0)
        exact = " (exact)" if matched == state else f" (matched on regime, id {matched!r})"
        if entry.get("passed"):
            return "dynamic", (f"dynamic won state {state!r}{exact} on {n} worlds: "
                               f"{entry.get('why', '')}")
        best = str(entry.get("best") or "")
        score = (entry.get("scores") or {}).get(best)
        finite = isinstance(score, (int, float)) and math.isfinite(float(score))
        if best and (finite or not entry.get("scores")):
            return best, (f"dynamic LOST state {state!r}{exact} on {n} worlds -- {best} allocates "
                          f"here: {entry.get('why', '')}")
        if best:
            # "Least ruinous" is not a winner. Every book wiped out in this state's worlds means
            # the honest answer is no sizing authority here at all, not the best of the wrecks.
            return "", (f"dynamic lost state {state!r}{exact} and {best} has no finite score "
                        f"there either ({score!r}): no book may size in this state")
        return "", (f"dynamic lost state {state!r}{exact} and no challenger was scorable there: "
                    f"{entry.get('why', '')}")
    reason = (f"state {state!r} has no bucket of >= "
              f"{cert.get('min_state_worlds', MIN_STATE_WORLDS)} worlds" if state
              else "no current state id")
    if cert.get("passed"):
        return "dynamic", f"{reason}; the GLOBAL verdict stands: {cert.get('why', '')}"
    best = str(cert.get("best_baseline") or "")
    if best:
        return best, (f"{reason}; the global proof failed, so {best} allocates: "
                      f"{cert.get('why', '')}")
    return "", f"{reason}; the global proof failed and carried no baseline"


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
