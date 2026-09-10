"""WHAT A RESEARCH HIT IS WORTH TO THE PORTFOLIO, not what it is worth on its own.

    "Every candidate should receive Score_i = P(real) x dE[log W] x Capacity x Persistence, not
     standalone Sharpe. That should also become your research search priority."
    "ResearchValue_j = P(survivor) x E[dE log W] x Capacity x Novelty / ComputeCost. Your
     research allocator should respond to portfolio weaknesses."      -- the principal, 2026-09-07

THE DEFECT THIS EXISTS TO FIX, MEASURED ON THIS TREE 2026-09-07. `libs/research/bandit.py` scores
each research arm at `E[dElogW] x P(survivor) / cost` and its E[dElogW] term -- `worth` -- came
back **1.000 for all eleven arms**, because `_marginal_by_arm` needs a `pf_allocator.json` with
certified sleeves attributable to arms and there is not one. With `worth` flat and nine of the
eleven arms carrying zero judged hypotheses, the score collapses to `p_pooled / cost` and the
budget is decided by the DECLARED COST TABLE: corr(share, 1/cost) = 0.87 across the eleven arms.

The consequence is the exact opposite of the desk's stated priority. `new_mechanism` -- the arm
that owns `empty_alpha_cluster`, and therefore the ONLY arm that can occupy any of the eleven
unoccupied alpha clusters -- costs 9 units and receives **5.81%** of research compute, while
`combine_survivors` costs 3 and receives **13.57%** for building ensembles out of sleeves the
book already holds. The desk was spending its compute buying more of the bet it already owned,
and the mechanism that made it do so was a price list.

THE MISSING TERM IS NOT A PREFERENCE, IT IS ARITHMETIC.

For a Kelly-sized book of equal-quality sleeves, growth per unit time is

    E[log W] ~ (1/2) S_p^2       and      S_p = s_bar * sqrt(k_eff)

so E[log W] is PROPORTIONAL TO k_eff, and therefore

    dE[log W] from admitting a sleeve  is proportional to  dk_eff from admitting it.

That is the whole derivation. It means the portfolio dE[log W] the principal asked for is, up to
a constant that cancels in any ranking, the marginal effective breadth -- a quantity this desk
already measures every pass. Reducing the book to one aggregate bet of nominal risk n and
variance n^2/k, a new unit-risk sleeve at correlation rho to that aggregate gives

    k' = (n + 1)^2 / (n^2/k + 1 + 2 rho n / sqrt(k))          dk = k' - k

Measured on this book (n = 31 nominal sleeves, k = 1.324, `reports/EFFECTIVE_BREADTH.json`):

    rho = 0.00   dk = +0.0847     a genuinely new payer
    rho = 0.21   dk = +0.0630     a new payer at the desk's own measured cross-correlation
    rho = 0.75   dk = +0.0109     another sleeve in an occupied cluster
    rho = 1.00   dk = -0.0124     a duplicate: it REDUCES effective breadth

THE NEGATIVE BRANCH IS THE POINT AND IT FALLS OUT OF THE ALGEBRA RATHER THAN BEING ASSERTED. A
perfectly correlated addition makes the book WORSE -- one bet wearing more tickers, at more
nominal risk -- which is precisely the "31 nominal exposures, 1.32 effective bets" finding, and
nothing in a standalone screen can express it.

WHERE rho COMES FROM, AND THE HONEST ADMISSION IN IT. An arm's rho is estimated from WHICH ALPHA
CLUSTER its output lands in: work landing in a cluster the book already occupies inherits the
book's own IMPLIED correlation (rho_book, solved from the measured k_eff and n, not assumed);
work landing in an empty cluster is credited at the desk's measured CROSS-INSTRUMENT mean
pairwise correlation -- 0.2118 here -- and NOT at zero, because nothing has measured a new
mechanism to be independent and assuming independence is the error that raises leverage.

Two layers, and the output always says which it used:

    MEASURED    the arm has at least MIN_CLASSIFIED classified hypotheses in the graph; its
                occupied share is counted from them
    DECLARED    it does not; `ARM_OCCUPIED_SHARE` supplies a stated share with a stated reason
    UNMEASURED  no breadth report at all -- every credit is 1.0, which changes nothing

NOTHING HERE ALLOCATES CAPITAL, AND THE CREDIT IS BOUNDED ON PURPOSE. It re-weights RESEARCH
COMPUTE only, it is normalised so the mean credit across arms is 1.0 (it redistributes, it does
not inflate), and it is clipped to [MIN_CREDIT, MAX_CREDIT] so no arithmetic can hand one arm the
whole budget -- a machine trapped by its own model is the failure the exploration floor exists to
prevent, and a model with an unbounded multiplier walks straight into it.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
BREADTH_REPORT = DESK / "reports" / "EFFECTIVE_BREADTH.json"

MEASURED, DECLARED, UNMEASURED = "MEASURED", "DECLARED", "UNMEASURED"

#: Classified hypotheses an arm needs before its occupied share is counted rather than declared.
#: Low, because the quantity is a SHARE and not a rate: ten classified proposals already say
#: whether an arm works in occupied ground or empty ground, which is all this asks of them.
MIN_CLASSIFIED = 10

#: The credit is clipped here. Not a tuning knob -- a guard against the model. The unclipped
#: ratio between an empty-cluster hit and a duplicate on this book is roughly 8x, and letting
#: that through intact would hand `new_mechanism` most of the budget on the strength of an
#: equal-quality assumption that has never been tested. Four-to-one is a strong steer and still
#: leaves every arm a working share.
MIN_CREDIT, MAX_CREDIT = 0.25, 4.0

#: Correlation assumed for an arm's output when the desk cannot measure a cross-cluster one. This
#: is the FALLBACK for `rho_cross` only; the live value is read from the breadth report's own
#: full-sample mean pairwise correlation. 0.21 is what that read on 2026-09-05.
DEFAULT_RHO_CROSS = 0.21

#: HOW MUCH OF AN ARM'S GROWTH RUNS THROUGH THE BREADTH CHANNEL AT ALL, and the correction that
#: this table exists to make. E[log W] ~ (1/2) s_bar^2 k_eff has TWO factors, and the derivation
#: at the top of this file only covers the second:
#:
#:     BREADTH channel   the arm ADMITS A SLEEVE -- its growth is dk_eff, measured here
#:     QUALITY channel   the arm makes the sleeves the book ALREADY HOLDS better or cheaper --
#:                       its growth is 2 ds_bar / s_bar, multiplicative across the whole book,
#:                       and this instrument cannot measure it at all
#:
#: The first version of this module scored every arm on the breadth channel alone, which cut
#: `execution_improvement` from 12.2% of research compute to 3.6% -- on an instrument that has
#: nothing to say about execution. That is not a finding, it is a category error: reducing spread
#: on a held sleeve raises s_bar and buys real growth while buying exactly zero breadth, and the
#: desk's own law is that UNMEASURED is a verdict rather than a zero.
#:
#: So the credit is `w * breadth_credit + (1 - w) * 1.0`. An arm with w = 0 comes out at exactly
#: 1.0 -- untouched, because this measurement does not reach it. Only the arms that produce
#: SLEEVES are re-weighted by what those sleeves do to the book's correlation structure.
#:
#: THE UNMEASURED HALF IS A NAMED GAP, NOT A DEFAULT. Once `execution.matched_fills` is non-zero
#: the desk can measure ds_bar per unit of execution research directly, and the quality channel
#: stops being a neutral 1.0 and starts being a number. Until then, neutral is the honest value.
ARM_BREADTH_WEIGHT: dict[str, float] = {
    "new_mechanism": 1.00,          # its entire output is a sleeve that did not exist
    "cross_asset_signal": 1.00,     # residual and lead-lag cells are new sleeves
    "alt_data_hypothesis": 1.00,    # a dataset the desk lacks becomes a sleeve or nothing
    "external_screen": 1.00,        # screened claims become candidate sleeves
    "failure_derived": 0.90,        # revivals are sleeves; some are process lessons
    "conditional_state_edge": 0.90, # a state-conditioned cell is a sleeve with a narrower clock
    "mutate_survivor": 0.70,        # a new sleeve at high rho, AND a better-parameterised one
    "combine_survivors": 0.70,      # an ensemble is a sleeve, and a better-weighted one
    "model_architecture": 0.50,     # expert routers add sleeves; better models sharpen held ones
    "exit_improvement": 0.00,       # reshapes a held sleeve's payoff -- pure s_bar, zero breadth
    "execution_improvement": 0.00,  # cheaper fills on held sleeves -- pure s_bar, zero breadth
}

#: DECLARED occupied-share per arm, used only where the graph cannot supply a measured one, with
#: the reason each number is what it is. These are claims about what an arm STRUCTURALLY does, so
#: they are stable facts about the research method rather than estimates of its success -- but
#: they are still declarations, they are still reported as DECLARED, and a measured share always
#: wins over one of these.
ARM_OCCUPIED_SHARE: dict[str, tuple[float, str]] = {
    "new_mechanism": (0.30, "a family never run before; it CAN land in occupied ground and often "
                            "does, but it is the only arm whose output can occupy an empty "
                            "cluster at all"),
    "mutate_survivor": (1.00, "a re-parameterisation of a certified cell monetises the same payer "
                              "by construction -- that is what a mutation IS"),
    "combine_survivors": (1.00, "an ensemble of held sleeves cannot reach a payer none of its "
                                "members reach"),
    "conditional_state_edge": (0.85, "conditioning an existing edge on a state changes WHEN it "
                                     "trades, not who pays; some of the time the state itself is "
                                     "the mechanism, which is the 0.15"),
    "execution_improvement": (1.00, "spread, fill and plumbing work makes the SAME edges cheaper "
                                    "-- real growth, and zero new breadth"),
    "exit_improvement": (1.00, "an exit rule reshapes an existing sleeve's payoff; the payer is "
                               "unchanged"),
    "cross_asset_signal": (0.20, "residual and lead-lag cells take money from slow updaters, a "
                                 "payer this book does not currently hold at all"),
    "alt_data_hypothesis": (0.25, "a dataset the desk lacks is usually a new payer, but the arm "
                                  "also produces re-statements of held mechanisms in new data"),
    "failure_derived": (0.80, "the graveyard is mostly the desk's own occupied ground, reworked"),
    "model_architecture": (0.90, "a better model of the same phenomenon is the same phenomenon; "
                                 "expert routers occasionally surface a distinct one"),
    "external_screen": (0.60, "screened external claims land wherever they land; the measured "
                              "share should replace this one first, since this arm has 23k rows"),
}


def marginal_k_eff(n_nominal: float, k_eff: float, rho: float) -> float:
    """dk_eff from admitting ONE unit-risk sleeve at correlation `rho` to the aggregate book.

    The book is reduced to a single aggregate bet carrying nominal risk `n_nominal` and variance
    `n^2 / k_eff` -- which is what k_eff MEANS, so the reduction is a restatement rather than an
    approximation. The addition is one more unit of standalone risk, which is what this desk's
    sizing makes true of every sleeve.

    Returns a signed number. NEGATIVE at high `rho` is correct and is the finding: a duplicate
    adds nominal risk and no bets, so the ratio (sum|w|)^2 / x'Cx falls.
    """
    n, k, r = float(n_nominal), float(k_eff), float(rho)
    if not all(math.isfinite(v) for v in (n, k, r)) or n <= 0 or k <= 0:
        raise ValueError(f"cannot take a marginal against n={n_nominal!r}, k_eff={k_eff!r}")
    var = (n * n) / k + 1.0 + 2.0 * r * n / math.sqrt(k)
    if var <= 0:
        raise ValueError("the implied portfolio variance is not positive; fix the measurement")
    return ((n + 1.0) ** 2) / var - k


def implied_rho(n_nominal: float, k_eff: float) -> float | None:
    """The book's OWN average correlation, solved from what was measured rather than assumed.

    k_eff = n / (1 + (n-1) rho)  =>  rho = (n/k_eff - 1) / (n - 1)

    On this book (n=31, k=1.324) that is 0.747 -- and the fact that it lands where the desk's
    same-mechanism sleeves were independently estimated (rho ~ 0.7, the prop-firm sizing work) is
    a check on both, not a coincidence to be pleased about.
    """
    n, k = float(n_nominal), float(k_eff)
    if n <= 1 or k <= 0 or not math.isfinite(n) or not math.isfinite(k):
        return None
    rho = (n / k - 1.0) / (n - 1.0)
    return float(min(max(rho, 0.0), 0.999)) if math.isfinite(rho) else None


def _report(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or BREADTH_REPORT).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def book_state(doc: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """n, k_eff, rho_book, rho_cross and the occupied cluster set -- all read, none assumed."""
    d = dict(doc) if doc is not None else _report()
    eff = d.get("effective") or {}
    n = eff.get("n_nominal")
    k = eff.get("effective_breadth")
    if not isinstance(n, (int, float)) or not isinstance(k, (int, float)) or n <= 1 or k <= 0:
        return {"status": UNMEASURED,
                "why": "no readable effective-breadth report: every arm's credit is 1.0"}
    rho_cross = DEFAULT_RHO_CROSS
    rho_cross_src = f"default {DEFAULT_RHO_CROSS}"
    for r in eff.get("readings") or []:
        if isinstance(r, dict) and r.get("name") == "exposure_full_sample":
            mp = (r.get("detail") or {}).get("mean_pairwise_corr")
            if isinstance(mp, (int, float)) and math.isfinite(float(mp)):
                rho_cross, rho_cross_src = float(mp), "measured full-sample mean pairwise"
            break
    rho_book = implied_rho(n, k)
    if rho_book is None:
        return {"status": UNMEASURED, "why": "the book's implied correlation is not solvable"}
    clusters = d.get("clusters") or {}
    return {
        "status": MEASURED, "n_nominal": float(n), "k_eff": float(k),
        "rho_book": rho_book, "rho_cross": float(rho_cross), "rho_cross_source": rho_cross_src,
        "occupied": sorted(str(c) for c in (clusters.get("occupied_either") or [])),
        "empty": sorted(str(c) for c in (clusters.get("empty_in_both") or [])),
        "why": (f"{n:.0f} nominal sleeves at k_eff {k:.3f} imply rho_book {rho_book:.3f}; "
                f"cross-cluster rho {rho_cross:.3f} ({rho_cross_src}). A new payer is credited at "
                "the cross correlation and NOT at zero -- nothing has measured a new mechanism to "
                "be independent, and assuming it is the error that raises leverage."),
    }


def occupied_shares(rows: Iterable[Mapping[str, Any]],
                    arm_of: Callable[[Mapping[str, Any]], str | None],
                    cluster_of: Callable[[Mapping[str, Any]], str | None],
                    occupied: set[str]) -> dict[str, dict[str, Any]]:
    """Per arm: the share of its CLASSIFIED output that lands in ground the book already holds.

    `arm_of(row)` and `cluster_of(row)` are injected so this stays free of both the bandit's
    routing table and the cluster taxonomy -- the two things most likely to be rewritten. Rows
    whose cluster cannot be named are counted in `unclassified` and excluded from the share: an
    unclassifiable proposal is evidence the desk cannot name the phenomenon, which is a finding,
    not a vote for either bucket.
    """
    acc: dict[str, dict[str, int]] = {}
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        arm = arm_of(r)
        if not arm:
            continue
        a = acc.setdefault(str(arm), {"in_occupied": 0, "in_empty": 0, "unclassified": 0})
        key = cluster_of(r)
        if not key:
            a["unclassified"] += 1
        elif str(key) in occupied:
            a["in_occupied"] += 1
        else:
            a["in_empty"] += 1
    out: dict[str, dict[str, Any]] = {}
    for arm, c in acc.items():
        n_cls = c["in_occupied"] + c["in_empty"]
        out[arm] = {**c, "n_classified": n_cls,
                    "share": (c["in_occupied"] / n_cls) if n_cls else None}
    return out


def credits(arms: Iterable[str], *, doc: Mapping[str, Any] | None = None,
            measured_shares: Mapping[str, Mapping[str, Any]] | None = None,
            min_classified: int = MIN_CLASSIFIED) -> dict[str, Any]:
    """The per-arm multiplier on E[dE log W], normalised to mean 1.0 across the arms.

    NORMALISED, NOT SCALED. The credit redistributes the budget between arms and never inflates
    it: whatever the arithmetic says, the arms still divide one budget. That is what makes it safe
    to apply to a quantity (`worth`) that is otherwise flat -- it cannot change the total, only
    who gets it.

    A NEGATIVE MARGINAL BECOMES THE FLOOR, NOT A NEGATIVE SHARE. An arm whose output would reduce
    effective breadth deserves the smallest share the exploration floor allows, and that is what
    MIN_CREDIT expresses. A negative multiplier in a Thompson allocation is not a smaller share,
    it is a meaningless one.
    """
    names = [str(a) for a in arms]
    state = book_state(doc)
    if state.get("status") != MEASURED:
        return {"status": UNMEASURED, "why": state.get("why", "no breadth measurement"),
                "credit": dict.fromkeys(names, 1.0), "book": state}
    n, k = state["n_nominal"], state["k_eff"]
    rho_book, rho_cross = state["rho_book"], state["rho_cross"]
    ms = dict(measured_shares or {})
    rows: dict[str, dict[str, Any]] = {}
    raw: dict[str, float] = {}
    for a in names:
        m = ms.get(a) or {}
        share = m.get("share")
        if isinstance(share, (int, float)) and int(m.get("n_classified", 0)) >= int(min_classified):
            src, why = MEASURED, (f"{m['in_occupied']}/{m['n_classified']} classified proposals "
                                  "landed in ground the book already occupies")
            s = float(share)
        else:
            s, declared_why = ARM_OCCUPIED_SHARE.get(a, (0.75, "unrouted arm: assumed to work "
                                                              "mostly in occupied ground"))
            src, why = DECLARED, declared_why
        s = min(max(float(s), 0.0), 1.0)
        rho = s * rho_book + (1.0 - s) * rho_cross
        try:
            dk = marginal_k_eff(n, k, rho)
        except ValueError as exc:
            return {"status": UNMEASURED, "why": str(exc),
                    "credit": dict.fromkeys(names, 1.0), "book": state}
        raw[a] = dk
        rows[a] = {"occupied_share": round(s, 4), "source": src, "why": why,
                   "rho_to_book": round(rho, 4), "delta_k_eff": round(dk, 6)}
    # Normalised over the arms that ACTUALLY RUN THROUGH THIS CHANNEL. Including the pure-quality
    # arms in the mean would drag the normaliser toward a number that describes nothing they do.
    positive = [v for a, v in raw.items() if v > 0 and ARM_BREADTH_WEIGHT.get(a, 1.0) > 0.0]
    scale = (sum(positive) / len(positive)) if positive else 1.0
    credit: dict[str, float] = {}
    for a in names:
        w = float(min(max(ARM_BREADTH_WEIGHT.get(a, 1.0), 0.0), 1.0))
        c_breadth = raw[a] / scale if scale > 0 else 1.0
        # THE QUALITY CHANNEL IS NEUTRAL, NOT ZERO. `1.0` is what "this instrument does not
        # measure your channel" looks like in a multiplier -- it leaves the arm exactly where the
        # evidence and the cost table put it, and lets the breadth term move only the arms whose
        # output actually changes the book's correlation structure.
        c = w * c_breadth + (1.0 - w) * 1.0
        c = min(max(c, MIN_CREDIT), MAX_CREDIT)
        credit[a] = round(float(c), 4)
        rows[a]["breadth_weight"] = round(w, 3)
        rows[a]["credit_breadth_channel"] = round(float(c_breadth), 4)
        rows[a]["credit"] = credit[a]
        if w <= 0.0:
            rows[a]["why"] = (
                "this arm raises s_bar on sleeves the book already holds and admits none: its "
                "growth is real and runs through a channel this instrument cannot measure, so it "
                "is left NEUTRAL at 1.0 rather than scored as zero breadth. Measurable once "
                "execution.matched_fills is non-zero.")
        elif raw[a] <= 0:
            rows[a]["why"] += ("; this arm's output REDUCES effective breadth on the current "
                               "book, so its breadth channel is floored at the minimum credit")
    return {
        "status": MEASURED, "credit": credit, "arms": rows, "book": state,
        "normaliser": round(float(scale), 8),
        "bounds": [MIN_CREDIT, MAX_CREDIT],
        "rule": ("credit = dk_eff(rho_arm) / mean(positive dk_eff), clipped to "
                 f"[{MIN_CREDIT}, {MAX_CREDIT}] and mean-normalised so it redistributes the "
                 "research budget without inflating it. dE[log W] is proportional to dk_eff for a "
                 "Kelly book of equal-quality sleeves, which is the assumption this rests on and "
                 "the one to attack first: an empty cluster may be empty because there is no edge "
                 "in it, and only P(survivor) -- measured separately, per arm -- can say so."),
    }
