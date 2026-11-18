"""Every multiplier that touches a sleeve's capital, registered, two-sided, and scored.

THE GOVERNANCE RULE THIS ENFORCES. A risk system that only knows how to cut exposure turns into
a risk officer; the desk's rule is that every capital modifier must be able to say BOOST as well
as REDUCE, and every category it emits must prove incremental forward E[log W] or lose its
authority. So:

    STRONG_VETO   0.0x   the state's conditional expectancy is negative with evidence
    REDUCE        0.5x   clearly below unconditional
    NORMAL        1.0x   indistinguishable from unconditional
    BOOST         1.5x   clearly above unconditional
    STRONG_BOOST  2.0x   far above, with evidence

are the categories of the AI CAPITAL MODIFIER: the shrunk ratio of a sleeve's state-conditional
posterior mean to its unconditional mean, exactly the quantity `robust_elog._posterior_mu`
applies continuously inside the allocator. The categories do not re-size anything -- the
posterior already did, continuously -- they are the LEDGER of what the conditioning claimed,
so that `score()` can later ask, per category, whether trades it labelled BOOST outperformed
NORMAL out of sample. A category that does not prove its increment is reported COSTS_GROWTH and
the missed-growth ledger carries it.

THE REGISTRY lists every modifier on the desk with its range. The growth-governance fence
refuses a modifier whose range cannot exceed 1.0 unless it is declared an integrity kill-switch
(broker down, stale prices, margin anomaly) or a reduce-only decay signal that is itself a
registered, measured rail.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
LEDGER = DESK / "data" / "capital_modifier_ledger.jsonl"
REPORT = DESK / "reports" / "CAPITAL_MODIFIERS.json"

CATEGORIES: dict[str, float] = {"STRONG_VETO": 0.0, "REDUCE": 0.5, "NORMAL": 1.0,
                                "BOOST": 1.5, "STRONG_BOOST": 2.0}
K_STATE = 40.0

#: Conviction scaling bounds and shape (see `conviction_factors`).
CONV_LO, CONV_HI = 0.5, 2.0
#: Days of evidence at which the strength term carries half its weight.
CONV_K_N = 120.0
#: Half-width of the strength band: DSR 1.0 with infinite n reads 1 + CONV_SPAN.
CONV_SPAN = 0.5
#: Two sleeves are INDEPENDENT signals when the allocator's own |corr| between them is below this.
RHO_INDEP = 0.3
AGREE_LO, AGREE_HI = 0.75, 1.5
#: The switch. Absent, unreadable or anything but {"mode": "LIVE"} reads SHADOW.
CONVICTION_SWITCH = DESK / "data" / "CONVICTION_SCALING.json"
#: Forward passes (distinct UTC days) the shadow comparison needs before it may flip the switch.
CONV_PROMOTE_N = 20


@dataclass(frozen=True)
class Modifier:
    name: str
    lo: float
    hi: float
    #: "two_sided" (must be able to boost), "integrity" (kill switch: broker/data/margin),
    #: "reduce_only" (a decay signal that must be a measured rail).
    kind: str
    where: str
    proof: str


REGISTRY: tuple[Modifier, ...] = (
    Modifier("state_posterior", 0.0, 2.0, "two_sided",
             "libs/portfolio/robust_elog._posterior_mu (state level of the hierarchy)",
             "desks/mt5/reports/STATE_ADMISSION.json"),
    Modifier("ai_capital_modifier", 0.0, 2.0, "two_sided",
             "libs/portfolio/capital_modifiers.category, ledgered by pf_allocator every pass",
             "desks/mt5/reports/CAPITAL_MODIFIERS.json"),
    Modifier("heat_resolution", 1.0, 1.5, "two_sided",
             "research/heat_policy.resolve: floor 20%, growth free to the 30% ceiling",
             "desks/mt5/reports/pf_allocation.json (aggression)"),
    Modifier("breadth_budget", 1.0, 1.5, "two_sided",
             "gateway.heat_budget: sqrt(k_eff) ladder above the base budget",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    # TWO-SIDED BY CONSTRUCTION, and registered here so the growth fence can hold it to that.
    # It damps an order that piles onto a currency leg the book already holds and BOOSTS one that
    # opens a leg the book does not hold, by the same bound -- the band is symmetric about 1.0 on
    # purpose. Total heat is decided upstream by `heat_budget` and is untouched; what this moves
    # is which bets that heat buys. Measured 2026-09-15: eight forex positions closed on their
    # stops for -34.05 EUR, and six of them were one bet (EURCHF short x4 and USDCHF short x2 are
    # both long CHF). Replaying that cluster through this, the 3rd and 4th EURCHF shorts size at
    # 0.55x and the CHF leg lands at 0.166 lots instead of 0.200, with 1.45x available on any leg
    # the book was not already holding.
    # THE CURRENCY-LEVEL MACRO LEAN, two-sided by construction (2026-09-16). Sizes an order
    # UP when it agrees with the lean of the currencies it expresses and DOWN by the same
    # bound when it opposes them; heat is unchanged and no trade is refused. Measured the
    # night it landed: every currency leg the book held was losing at once, and the view --
    # on 12-day-stale FRED data -- leaned CHF -0.31 while the desk was short EURCHF and
    # USDCHF, its three largest losers. Confidence decays to zero with data age, so a stale
    # view tilts gently and says so rather than pretending to be current.
    Modifier("macro_view", 0.6, 1.4, "two_sided",
             "mt5desk.macro_view.multiplier, applied in gateway.resolve_family_order beside "
             "leg_balance, before the venue lot step",
             "desks/mt5/reports/MACRO_VIEW.json"),
    Modifier("leg_balance", 0.55, 1.45, "two_sided",
             "mt5desk.leg_balance.multiplier, applied in gateway.resolve_family_order after "
             "promoted_lot and before the venue lot step",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    # THE MACRO REGIME, AT THE ALLOCATOR (2026-09-16). Each sleeve's OWN returns, kernel-weighted
    # by how much each historical day's macro state (dollar, risk, rates ranks from the FRED
    # archive) resembles today's, as a CONTRAST against its unconditional mean: a sleeve that
    # earned more on days like today is tilted up, one that earned less is tilted down, shrunk
    # at k=60 effective days and bounded by the posterior's own magnitude. Two-sided by
    # construction and heat-neutral: it moves capital BETWEEN sleeves, never the total. This is
    # the level that lets a strong-dollar regime fund the dollar-bull sleeves and defund the
    # bears without any sleeve being told which way to trade.
    Modifier("macro_regime", 0.0, 2.0, "two_sided",
             "libs/portfolio/robust_elog._posterior_mu (macro level of the hierarchy, from "
             "SleeveEvidence.macro_w set by pf_allocator via libs.portfolio.macro_state)",
             "desks/mt5/reports/pf_allocation.json (macro_regime)"),
    # THE ALLOCATOR-V2 EVIDENCE (LAWS 5m, 2026-09-22): lineage concentration x research ROI as
    # a bounded, two-sided tilt of each sleeve's posterior mean, and the venue's financing as a
    # signed level shift where the replay never charged it -- both INPUTS to the E[log W]
    # solve, never a multiplier on its answer. Heat-neutral on the lineage half by
    # construction; a unique lineage, a high-ROI mechanism or a carry credit RAISES a sleeve.
    # Neutral (1.0 / 0.0) whenever data/allocator_evidence.json or roi_capital_evidence.json
    # is absent or stale.
    Modifier("allocator_evidence", 0.5, 2.0, "two_sided",
             "pf_allocator.apply_allocator_evidence <- data/allocator_evidence.json "
             "(research/financing_lab.py) and data/roi_capital_evidence.json "
             "(research/research_roi.py), applied to SleeveEvidence.daily_r before the solve",
             "desks/mt5/reports/FINANCING_LAB.json"),
    # CONVICTION SCALING (Build C row 143, 2026-11-18). Each sleeve's evidence weight times
    # (a) its evidence STRENGTH -- the deflated Sharpe probability, shrunk by sample length --
    # and (b) how many INDEPENDENT signals agree with it (same instrument, another mechanism,
    # |corr| under RHO_INDEP, positive expectancy), relative to the book's median count. Enters
    # as a tilt of the posterior mean BEFORE the E[log W] solve, never on its answer. Two-sided:
    # a deflated-Sharpe-strong, well-corroborated sleeve reaches 2.0x. SHADOW by default
    # (`CONVICTION_SWITCH`); `research/conviction_shadow.py` flips it LIVE on forward evidence.
    Modifier("conviction", CONV_LO, CONV_HI, "two_sided",
             "capital_modifiers.conviction_factors -> pf_allocator.apply_conviction (LIVE only; "
             "SHADOW leaves the evidence byte-identical)",
             "desks/mt5/reports/CONVICTION_SHADOW.json"),
    Modifier("fade", 0.5, 1.0, "reduce_only",
             "mt5desk.sizing.decay_factor (L1.59 fade flag from decay_monitor)",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    Modifier("authority_ramp", 0.25, 1.0, "reduce_only",
             "gateway.promoted_lot ramp -- NOT applied to allocator-book sleeves",
             "desks/mt5/reports/MISSED_GROWTH.json"),
    Modifier("catastrophe_override", 0.0, 1.0, "integrity",
             "research/heat_policy.catastrophe_override: broker/prices/reconcile/margin",
             "n/a (integrity kill switch)"),
)


def category(mu_state: float, mu_uncond: float, n_state: int, k: float = K_STATE
             ) -> tuple[str, float]:
    """Category and continuous multiplier from the SHRUNK conditional/unconditional ratio."""
    if not (math.isfinite(mu_state) and math.isfinite(mu_uncond)) or n_state <= 0:
        return "NORMAL", 1.0
    lam = n_state / (n_state + k)
    if abs(mu_uncond) < 1e-12:
        ratio = 1.0 + lam * (1.0 if mu_state > 0 else -1.0)
    else:
        ratio = 1.0 + lam * (mu_state / mu_uncond - 1.0)
    mult = float(min(2.0, max(0.0, ratio)))
    if mult <= 0.05:
        return "STRONG_VETO", mult
    if mult < 0.7:
        return "REDUCE", mult
    if mult < 1.3:
        return "NORMAL", mult
    if mult < 1.8:
        return "BOOST", mult
    return "STRONG_BOOST", mult


def record(ev: Sequence[Any], book: dict[str, float], state_key: str,
           at: str | None = None) -> list[dict[str, Any]]:
    """Ledger one row per funded sleeve with state evidence. Never raises."""
    rows = []
    try:
        ts = at or datetime.now(tz=UTC).isoformat()
        for e in ev:
            h = float(book.get(e.name, 0.0))
            if h <= 1e-6:
                continue
            sr = np.asarray(getattr(e, "state_r", np.array([])), dtype=float)
            dr = e.own_r      # defect #4: compare the state's days to days it actually traded
            if sr.size == 0 or dr.size == 0:
                continue
            cat, mult = category(float(sr.mean()), float(dr.mean()), int(sr.size))
            rows.append({"t": ts, "sleeve": e.name, "state": state_key, "category": cat,
                         "multiplier": round(mult, 4), "n_state": int(sr.size),
                         "mu_state": round(float(sr.mean()), 6),
                         "mu_uncond": round(float(dr.mean()), 6), "heat": round(h, 6)})
        if rows:
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
    except Exception:
        return rows
    return rows


def _realized_by_sleeve_day() -> dict[tuple[str, str], float]:
    """Realised R per (sleeve, day) from the live and shadow ledgers, when present."""
    out: dict[tuple[str, str], float] = {}
    try:
        from research.state_admission_run import load_trades  # type: ignore[import-not-found]
        for t in load_trades("shadow"):
            day = str(t.when)[:10]
            out[(t.sleeve, day)] = out.get((t.sleeve, day), 0.0) + float(t.r)
    except Exception:
        pass
    return out


def score(write: bool = True) -> dict[str, Any]:
    """Per category: realised R on the days it was claimed, against NORMAL. The proof."""
    try:
        rows = [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        rows = []
    realized = _realized_by_sleeve_day()
    by_cat: dict[str, list[float]] = {c: [] for c in CATEGORIES}
    for r in rows:
        key = (str(r.get("sleeve")), str(r.get("t"))[:10])
        if key in realized:
            by_cat[str(r.get("category"))].append(realized[key])
    base = np.asarray(by_cat.get("NORMAL", []), dtype=float)
    out = {}
    for cat, rs in by_cat.items():
        arr = np.asarray(rs, dtype=float)
        if arr.size < 20 or base.size < 20:
            out[cat] = {"n": int(arr.size), "verdict": "UNMEASURED",
                        "mean_r": (round(float(arr.mean()), 4) if arr.size else None)}
            continue
        diff = float(arr.mean() - base.mean())
        se = math.sqrt(arr.var(ddof=1) / arr.size + base.var(ddof=1) / base.size)
        t = diff / se if se > 0 else 0.0
        want_up = CATEGORIES[cat] > 1.0
        want_down = CATEGORIES[cat] < 1.0
        verdict = ("PROVES_INCREMENT" if ((want_up and t > 2.0) or (want_down and t < -2.0))
                   else ("COSTS_GROWTH" if ((want_up and t < -2.0) or (want_down and t > 2.0))
                         else ("NORMAL" if cat == "NORMAL" else "UNPROVEN")))
        out[cat] = {"n": int(arr.size), "mean_r": round(float(arr.mean()), 4),
                    "vs_normal": round(diff, 4), "t": round(t, 2), "verdict": verdict}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "ledger_rows": len(rows),
           "matched_rows": int(sum(len(v) for v in by_cat.values())), "categories": out,
           "registry": [m.__dict__ for m in REGISTRY],
           "rule": ("a BOOST category proves itself when its realised R exceeds NORMAL's at "
                    "t > 2; a REDUCE category when it falls short at t < -2; anything else is "
                    "UNPROVEN and carries no authority beyond the continuous posterior")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


# ------------------------------------------------------------------ CONVICTION SCALING (row 143)
def conviction_mode(path: Path | None = None) -> str:
    """LIVE only when the switch file says so; everything else (absent too) reads SHADOW."""
    try:
        doc = json.loads((path or CONVICTION_SWITCH).read_text("utf-8"))
    except (OSError, ValueError):
        return "SHADOW"
    return "LIVE" if isinstance(doc, dict) and doc.get("mode") == "LIVE" else "SHADOW"


def _finite(a: Any) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    out: np.ndarray = arr[np.isfinite(arr)]
    return out


def evidence_strength(r: np.ndarray, n_trials: int, var_sharpes: float) -> tuple[float, float]:
    """(deflated Sharpe probability, strength multiplier) for one sleeve's daily R.

    strength = 1 + lam_n x (2 x DSR - 1) x CONV_SPAN, lam_n = n / (n + CONV_K_N). DSR 0.5 (the
    observed Sharpe is exactly what the search would produce by luck) is neutral; a deflated
    probability near 1 on a long record lifts toward 1 + CONV_SPAN and one near 0 cuts toward
    1 - CONV_SPAN. A short record is pulled toward 1.0 either way.
    """
    from libs.validation.dsr import expected_max_sharpe, probabilistic_sharpe_ratio
    x = _finite(r)
    n = int(x.size)
    if n < 3 or float(x.std()) <= 0:
        return 0.5, 1.0
    sr0 = expected_max_sharpe(max(int(n_trials), 1), max(float(var_sharpes), 0.0))
    dsr = float(probabilistic_sharpe_ratio(x, sr_benchmark=sr0))
    if not math.isfinite(dsr):
        return 0.5, 1.0
    lam = n / (n + CONV_K_N)
    return dsr, float(1.0 + lam * (2.0 * dsr - 1.0) * CONV_SPAN)


def agreement_counts(ev: Sequence[Any], corr_abs: np.ndarray) -> list[int]:
    """Per sleeve: other sleeves on the SAME instrument, of ANOTHER mechanism (family), with a
    positive mean and |corr| < RHO_INDEP to it. Zero for a sleeve whose own mean is not positive
    (it has no direction for anything to agree with)."""
    means = [float(_finite(e.daily_r).mean()) if _finite(e.daily_r).size else 0.0 for e in ev]
    out = []
    for i, e in enumerate(ev):
        if means[i] <= 0 or not getattr(e, "symbol", ""):
            out.append(0)
            continue
        k = 0
        for j, o in enumerate(ev):
            if (j != i and getattr(o, "symbol", "") == e.symbol
                    and getattr(o, "family", "") != getattr(e, "family", "")
                    and means[j] > 0 and float(corr_abs[i, j]) < RHO_INDEP):
                k += 1
        out.append(k)
    return out


def conviction_factors(ev: Sequence[Any], corr_abs: np.ndarray | None = None
                       ) -> dict[str, dict[str, Any]]:
    """One conviction multiplier per sleeve, two-sided, in [CONV_LO, CONV_HI].

    conviction = clip(strength x agreement), agreement = clip(sqrt((1 + k) / (1 + k_ref))) with
    k the sleeve's count of agreeing independent signals and k_ref the median count over the
    positive-mean sleeves -- so a sleeve corroborated more than the book's typical sleeve is
    lifted and one corroborated less is lowered, and a book where nothing corroborates anything
    reads 1.0 on this term. `corr_abs` defaults to the allocator's own `_corr_abs`.
    """
    if not ev:
        return {}
    if corr_abs is None:
        from libs.portfolio.robust_elog import _corr_abs
        corr_abs = _corr_abs(ev)
    from libs.validation.dsr import sharpe_ratio
    srs = [sharpe_ratio(_finite(e.daily_r)) for e in ev if _finite(e.daily_r).size >= 3]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) >= 2 else 0.0
    ks = agreement_counts(ev, corr_abs)
    pos = [k for e, k in zip(ev, ks, strict=True)
           if _finite(e.daily_r).size and float(_finite(e.daily_r).mean()) > 0]
    k_ref = float(np.median(pos)) if pos else 0.0
    out: dict[str, dict[str, Any]] = {}
    for e, k in zip(ev, ks, strict=True):
        dsr, strength = evidence_strength(e.daily_r, int(getattr(e, "n_trials", 1) or 1), var_sr)
        agree = float(min(AGREE_HI, max(AGREE_LO, math.sqrt((1.0 + k) / (1.0 + k_ref)))))
        mult = float(min(CONV_HI, max(CONV_LO, strength * agree)))
        out[e.name] = {"dsr": round(dsr, 6), "n": int(_finite(e.daily_r).size),
                       "n_trials": int(getattr(e, "n_trials", 1) or 1),
                       "strength": round(strength, 6), "agreeing": int(k),
                       "k_ref": k_ref, "agreement": round(agree, 6), "factor": round(mult, 6)}
    return out


def apply_conviction(ev: Sequence[Any], factors: Mapping[str, Mapping[str, Any]]) -> list[Any]:
    """A NEW list with each sleeve's posterior mean tilted by its conviction factor:
    mean += (factor - 1) x |mean|, dispersion unchanged (the `allocator_evidence` rule). The
    input list and its arrays are never touched."""
    from dataclasses import replace as _replace
    out = []
    for e in ev:
        f = float((factors.get(e.name) or {}).get("factor", 1.0))
        arr = np.asarray(e.daily_r, dtype=float)
        mask = np.isfinite(arr)
        if abs(f - 1.0) < 1e-12 or not mask.any():
            out.append(e)
            continue
        new = arr.copy()
        new[mask] = new[mask] + (f - 1.0) * abs(float(arr[mask].mean()))
        out.append(_replace(e, daily_r=new))
    return out


def conviction_promotion(deltas: Sequence[float], current: str, n: int = CONV_PROMOTE_N
                         ) -> dict[str, Any]:
    """THE SWITCH'S RULE, in code and with no human gate.

    `deltas` are forward realised dE[log W] per pass (conviction book minus base book, one per
    distinct UTC day, oldest first). Over the last `n`:
      * SHADOW -> LIVE when mean - se > 0 (robustly positive forward growth);
      * LIVE -> SHADOW when mean + se < 0 (robustly negative: the modifier lost its authority);
      * otherwise the mode stands. Fewer than `n` matured passes is UNMEASURED and stands.
    """
    arr = np.asarray([float(d) for d in deltas if math.isfinite(float(d))][-n:], dtype=float)
    if arr.size < n:
        return {"mode": current, "changed": False, "verdict": "UNMEASURED", "n": int(arr.size),
                "need": n}
    mean = float(arr.mean())
    se = float(arr.std(ddof=1) / math.sqrt(arr.size)) if arr.size > 1 else 0.0
    nxt = current
    if current != "LIVE" and mean - se > 0:
        nxt = "LIVE"
    elif current == "LIVE" and mean + se < 0:
        nxt = "SHADOW"
    verdict = ("RAISES_ELOG" if mean - se > 0 else
               ("LOWERS_ELOG" if mean + se < 0 else "UNPROVEN"))
    return {"mode": nxt, "changed": nxt != current, "verdict": verdict, "n": int(arr.size),
            "mean_delta_logw": round(mean, 10), "se": round(se, 10)}
