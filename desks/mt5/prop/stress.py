"""THE WORST HISTORICAL DAY OF A PROP BOOK, WITH ITS CORRELATIONS, AGAINST THE FIRM'S DAILY LIMIT.

A prop account dies on one bad day (E8: 2.5% of the day's starting balance; FTMO: 5%). A flat size
per sleeve with no family or correlation term lets near-copies of one mechanism lose together, and
the executors' whole-book check counts risk AT THE STOPS -- a gap or slippage day goes through
them. So before a book is traded its worst historical day is measured here: every (path, day) of
the desk's joint return tensor (`kelly_survival.WORLDS`, one row per day across every column, so
the correlation between sleeves is the one history showed, not an assumption), loss = -sum(h_k *
r_k). A column the tensor does not carry is charged its full risk on that day (rho = 1, fail
closed), and an unreadable tensor charges every sleeve in full.

THE CAP: the worst day must stay under STRESS_CAP_FRAC (60%) of the firm's daily limit (CIO review
2026-11-19 move #1, coordinator 16:59Z). This is the firm's breach rule plus a margin for gaps and
slippage -- a breach ends the account, which is the whole pass probability -- not a size cut by
fiat: every cut is billed as missed growth (`cuts`), and the kill criterion is published: a book
whose worst day is under KILL_FRAC (30%) of the limit with every sleeve in it never binds this.
REVERT: STRESS_CAP_FRAC = None reports the stress and cuts nothing.

THE CAP SCALES, IT DOES NOT ZERO (Audit ruling 2026-11-25, audits/ruling-stress-crisis-clip).
Dropping whole sleeves until the worst day fits sent a book of five certified sleeves to ZERO
whenever the fixed gold lane alone sat near the cap: each drop removed a bet the account could
have carried at a smaller size. STRESS_MODE = "scale" finds the LARGEST common factor k in [0, 1]
on every non-fixed sleeve's risk with the worst day still under the cap (the worst day is convex
in k, so the feasible set is an interval from 0 and bisection finds its end), writes k into each
row through `set_risk`, and bills (1 - k) of each sleeve as missed growth. The cap itself is
unchanged. A fixed lane that breaches the cap on its own is reported as `fixed_breach`, never
hidden in the sleeves' cut. STRESS_MODE = "cut" is the revert to the drop-the-weakest rule.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

STRESS_CAP_FRAC: float | None = 0.60
#: "scale" (default) or "cut" (the revert): see the module docstring.
STRESS_MODE = "scale"
#: Bisection steps for the common scale: 2**-40 of the book's risk is far below any lot step.
_SCALE_STEPS = 40
KILL_FRAC = 0.30


def load_days(worlds: Path | None = None) -> tuple[list[str], Any] | None:
    """(column names, r[n_w, n_t, n_c]) from the desk's world tensor, or None when unreadable."""
    try:
        import numpy as np
        if worlds is None:
            import kelly_survival as ks
            worlds = ks.WORLDS
        z = np.load(worlds, allow_pickle=True)
        return [str(x) for x in z["names"]], np.asarray(z["r"], dtype=float)
    except Exception:
        return None


def worst_day(cols: Sequence[str], risk: Sequence[float],
              days: tuple[list[str], Any] | None) -> dict[str, Any]:
    """The book's worst day as a fraction of equity, and each column's share of that day."""
    import numpy as np
    risk_a = np.asarray(list(risk), dtype=float)
    if not len(risk_a):
        return {"loss": 0.0, "status": "EMPTY", "by_col": {}, "unmeasured": []}
    if days is None:
        return {"loss": float(risk_a.sum()), "status": "UNMEASURED: world tensor unreadable, "
                "every sleeve charged its full risk (rho = 1)",
                "by_col": {c: float(h) for c, h in zip(cols, risk_a, strict=True)},
                "unmeasured": list(cols)}
    names, r = days
    idx = {n: k for k, n in enumerate(names)}
    have = [k for k, c in enumerate(cols) if c in idx]
    miss = [k for k, c in enumerate(cols) if c not in idx]
    flat = r.reshape(-1, r.shape[-1])
    sub = flat[:, [idx[cols[k]] for k in have]] if have else np.zeros((1, 0))
    pnl = sub @ risk_a[have] if have else np.zeros(1)
    t = int(np.argmin(pnl))
    by_col = {cols[k]: float(-sub[t, j] * risk_a[k]) for j, k in enumerate(have)}
    by_col.update({cols[k]: float(risk_a[k]) for k in miss})
    loss = float(-pnl[t] + risk_a[miss].sum())
    return {"loss": max(loss, 0.0), "status": "MEASURED" if not miss else
            "MEASURED (columns absent from the tensor charged in full)",
            "by_col": by_col, "unmeasured": [cols[k] for k in miss]}


def cap_book(rows: list[dict[str, Any]], risk_of: Any, family_of: Any, daily_limit: float,
             days: tuple[list[str], Any] | None, col_of: Any,
             fixed: dict[str, float] | None = None,
             set_risk: Any = None) -> dict[str, Any]:
    """Drop the weakest sleeve of the family that loses most on the worst day until that day is
    under STRESS_CAP_FRAC x the limit. `rows` is best-first within each family; `fixed` is risk
    the same account carries on another lane (E8's gold), counted on every day and never cut.
    Returns the kept rows, the cuts (each a missed-growth line) and the stress before and after."""
    kept = list(rows)
    fixed = {k: float(v) for k, v in (fixed or {}).items() if v > 0}

    def measure(book: list[dict[str, Any]]) -> dict[str, Any]:
        return worst_day([col_of(r) for r in book] + list(fixed),
                         [risk_of(r) for r in book] + list(fixed.values()), days)

    before = measure(kept)
    cuts: list[dict[str, Any]] = []
    cur = before
    cap = None if STRESS_CAP_FRAC is None else STRESS_CAP_FRAC * daily_limit
    scale: float | None = None
    fixed_alone = measure([])["loss"] if fixed else 0.0
    if (STRESS_MODE == "scale" and set_risk is not None and cap is not None and kept
            and cur["loss"] > cap + 1e-12):
        base = [float(risk_of(r)) for r in kept]

        def at(k: float) -> dict[str, Any]:
            return worst_day([col_of(r) for r in kept] + list(fixed),
                             [k * b for b in base] + list(fixed.values()), days)

        lo, hi = 0.0, 1.0
        if at(0.0)["loss"] > cap + 1e-12:
            hi = 0.0                    # the fixed lane alone breaches: nothing a sleeve can fix
        else:
            for _ in range(_SCALE_STEPS):
                mid = 0.5 * (lo + hi)
                if at(mid)["loss"] <= cap + 1e-12:
                    lo = mid
                else:
                    hi = mid
            hi = lo
        scale = hi
        cur = at(scale)
        for r, b in zip(kept, base, strict=True):
            set_risk(r, b * scale)
            cuts.append({"column": col_of(r), "family": family_of(r),
                         "missed_growth_risk_frac": round(b * (1.0 - scale), 8),
                         "scaled_to": round(b * scale, 8), "scale": round(scale, 6),
                         "worst_day_before": round(before["loss"], 6),
                         "why": f"worst historical day {before['loss']:.4%} over the "
                                f"{STRESS_CAP_FRAC:.0%} x {daily_limit:.2%} stress cap; every "
                                f"sleeve scaled by {scale:.4f} to fit"})
        kept = [r for r in kept if scale > 0]
    while (STRESS_MODE != "scale" or set_risk is None) and cap is not None and kept \
            and cur["loss"] > cap + 1e-12:
        fam_loss: dict[str, float] = {}
        if not kept:
            break
        for r in kept:
            fam_loss[family_of(r)] = fam_loss.get(family_of(r), 0.0) + \
                cur["by_col"].get(col_of(r), 0.0)
        worst_fam = max(fam_loss, key=lambda f: fam_loss[f])
        victim = [r for r in kept if family_of(r) == worst_fam][-1]
        kept.remove(victim)
        cuts.append({"column": col_of(victim), "family": worst_fam,
                     "missed_growth_risk_frac": risk_of(victim),
                     "worst_day_before": round(cur["loss"], 6),
                     "why": f"worst historical day {cur['loss']:.4%} over the "
                            f"{STRESS_CAP_FRAC:.0%} x {daily_limit:.2%} stress cap; "
                            f"{worst_fam} lost most on it"})
        cur = measure(kept)
    return {"kept": kept, "cuts": cuts, "daily_limit": daily_limit, "fixed": fixed,
            "cap_frac": STRESS_CAP_FRAC, "kill_frac": KILL_FRAC,
            "mode": STRESS_MODE if set_risk is not None else "cut", "scale": scale,
            "fixed_alone_loss": round(fixed_alone, 6),
            "fixed_breach": bool(cap is not None and fixed and fixed_alone > cap + 1e-12),
            "before": {"loss": round(before["loss"], 6), "status": before["status"],
                       "x_limit": round(before["loss"] / daily_limit, 4),
                       "unmeasured": before["unmeasured"]},
            "after": {"loss": round(cur["loss"], 6), "status": cur["status"],
                      "x_limit": round(cur["loss"] / daily_limit, 4)},
            "kill_criterion_met": before["loss"] < KILL_FRAC * daily_limit}
