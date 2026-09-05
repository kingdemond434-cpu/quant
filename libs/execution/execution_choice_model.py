"""E[post-fill alpha | style, spread, volatility, momentum, session] -- and the gate in front of it.

THE PRINCIPAL'S ORDER. "For every signal, learn E[R | market entry] vs E[R | limit] vs E[R | wait
5s] vs E[R | wait for retrace], conditioned on spread, volatility, momentum and session ... then
let the engine choose the style that maximises it."

THE HARNESS SHIPS; THE MODEL SHIPS WHEN THE SAMPLE DOES. This module is deliberately built in
that order. `fit` assembles the full conditional surface -- every style in every cell, with n, a
mean and an interval -- and then REFUSES to return a usable policy until the thinnest arm in the
compared cell clears the sample size the desk's own power calculation demands. `choose` returns
the caller's fallback, unchanged, whenever that gate is shut. A model that pretends to know is
worse than a collection harness that admits it does not: the harness costs a wait, the pretender
costs money and hides the fact that it is costing money behind a number.

THE AXIS DECIDES THE PRICE OF THE ANSWER. This is the finding the sample-size table makes
unavoidable, and it is worth more than the model would be. The same 0.04R question costs three
wildly different sample sizes depending on what is measured:

    basis            what it is                              sigma    n/arm at delta=0.04R
    slip_r           the execution cost at the fill           ~0.05R   tens
    markout_5m_r     post-fill alpha over five minutes        ~0.25R   hundreds
    realized_r       the whole trade's outcome                ~1.2R    tens of thousands

All three answer "which style is better", and only the first is reachable on a solo desk's order
flow this year. So the harness measures on the TIGHTEST axis that answers the question, records
which axis every observation used, and never averages two bases into one cell -- a mean over a
mixture of a cost and a trade outcome is a number with no units.

CONDITIONING COSTS SAMPLE, AND THE COST IS CHARGED. Four styles across spread x volatility x
momentum x session is 180 cells and 540 pairwise comparisons; Bonferroni at that width roughly
triples the per-arm requirement. `TIERS` names four conditioning depths from unconditional to
full, and `requirements()` prices every one of them, so the desk can see that the unconditional
comparison is affordable now and the full cross is not -- and can decide to buy the cheap answer
first rather than wait years for the expensive one.

NOTHING HERE SENDS AN ORDER, CHANGES A SIZE, OR ADMITS A SIGNAL. It ranks styles for an order the
desk has already decided to send. `execution_policy.choose` remains the only chooser on the money
path; this is the surface that would inform it, and it stays advisory until its own gate opens.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from libs.execution.fill_corpus import FillRecord, record_from_row
from libs.execution.sample_power import (
    DEFAULT_ALPHA,
    DEFAULT_POWER,
    PowerVerdict,
    sigma_of,
)
from libs.execution.sample_power import (
    verdict as power_verdict,
)

__all__ = [
    "BASES",
    "CONDITION_DIMS",
    "MOMENTUM_BUCKETS",
    "STYLE_ALIASES",
    "TARGET_DELTA_R",
    "TIERS",
    "VOL_BUCKETS",
    "ChoiceSurface",
    "condition_of",
    "fit",
    "post_fill_alpha",
    "requirements",
]

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
Z95 = 1.959964

#: The desk's execution algorithms, mapped onto the principal's vocabulary. The LEFT side is what
#: `execution_registry` names and what the outcome ledger records, so it is what the corpus
#: carries and what this model keys on; the right side is only how it reads in a report.
STYLE_ALIASES: dict[str, str] = {
    "market": "market entry",
    "pullback": "wait for retrace (passive limit better than the quote)",
    "sniper": "wait for the spread to narrow, market at the timeout",
    "twap": "slice on a clock",
    "iceberg": "rest at the touch, hidden size",
}
#: The style every other style is compared against. The baseline must be the thing the desk does
#: today, or a positive result means nothing operational.
BASELINE_STYLE = "market"

#: The edge the principal asked to recover. Every sample-size number here is the answer to
#: "how many fills before a difference of THIS SIZE is distinguishable from noise".
TARGET_DELTA_R = 0.04

#: AN ABSOLUTE FLOOR ON TOP OF THE POWER CALCULATION, and never below it. The power number is the
#: sample needed at a KNOWN sigma; on a handful of rows sigma is itself an estimate, and a cell
#: whose four observations happen to be identical reports zero variance, an infinitely tight
#: interval and a confident winner. That is the exact failure this module exists to refuse, so a
#: cell needs `max(power_n, MIN_CELL_N)` per arm. The same floor `digital_twin.MIN_N` uses, so a
#: sample that clears one gate on this desk cannot fail another.
MIN_CELL_N = 20

#: Per-observation dispersion by basis, in R. DECLARED REFERENCES, not measurements -- they are
#: what `requirements()` prices with until the corpus can supply its own sigma, and every verdict
#: says which it used. Chosen on the conservative side (a larger sigma asks for MORE data), for
#: the standing reason that an optimistic gate is the failure this desk has paid for repeatedly.
REFERENCE_SIGMA_R: dict[str, float] = {
    "slip_r": 0.05,          # execution cost at the fill, in units of the trade's own stop
    "markout_30s_r": 0.15,
    "markout_5m_r": 0.25,    # a five-minute move measured against an H1-scale stop distance
    "realized_r": 1.20,      # a stop-and-target trade is bimodal near -1R and +2R
}
#: Bases in preference order. `fit` uses the tightest basis that has enough populated rows, and
#: never mixes two of them inside one cell.
BASES: tuple[str, ...] = ("slip_r", "markout_30s_r", "markout_5m_r", "realized_r")
#: Bases where a LARGER number is worse (a cost), so the sign flips before styles are ranked.
_COST_BASES: frozenset[str] = frozenset({"slip_r"})

#: Volatility buckets as a fraction of price. Coarse on purpose: a cell that never reaches n is a
#: cell that teaches nothing, and three buckets is already 3x the sample requirement.
VOL_BUCKETS: tuple[tuple[float, str], ...] = (
    (0.0015, "low<=15bp"), (0.005, "mid<=50bp"), (math.inf, "high>50bp"),
)
#: Momentum in z-units of the signal's own lookback, signed WITH the trade direction: positive
#: means the market was already moving the desk's way when the order was sent, which is exactly
#: the state where waiting for a retrace should lose and paying up should win.
MOMENTUM_BUCKETS: tuple[tuple[float, str], ...] = (
    (-0.5, "against<=-0.5z"), (0.5, "flat"), (math.inf, "with>0.5z"),
)
#: The four conditioning dimensions, in the order `TIERS` adds them.
CONDITION_DIMS: tuple[str, ...] = ("session", "spread", "vol", "momentum")

#: (name, the dimensions conditioned on, how many cells that is). The cell counts are the
#: product of the bucket counts and are what `requirements()` charges Bonferroni on.
TIERS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("unconditional", (), 1),
    ("session", ("session",), 5),
    ("session_x_spread", ("session", "spread"), 5 * 4),
    ("full", ("session", "spread", "vol", "momentum"), 5 * 4 * 3 * 3),
)


def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _bucket(v: float | None, table: Sequence[tuple[float, str]]) -> str:
    if v is None:
        return "unknown"
    for edge, name in table:
        if v <= edge:
            return name
    return table[-1][1]


#: `digital_twin.spread_bucket`, resolved once. Reused rather than re-derived so the corpus and
#: the twin bucket a spread identically; imported LAZILY (digital_twin pulls in numpy) and cached,
#: because `condition_of` runs once per record and an import inside that loop is a tax that grows
#: with the asset.
_SPREAD_BUCKET: Any = None


def _spread_bucket(rec: FillRecord) -> str:
    global _SPREAD_BUCKET
    if _SPREAD_BUCKET is None:
        from libs.execution.digital_twin import spread_bucket
        _SPREAD_BUCKET = spread_bucket
    return str(_SPREAD_BUCKET(_f(rec.spread_frac_at_decision)))


def condition_of(rec: FillRecord, dims: Sequence[str] = CONDITION_DIMS) -> str:
    """The conditioning cell a fill belongs to, as a stable string key over `dims`."""
    parts: list[str] = []
    for d in dims:
        if d == "session":
            parts.append(f"session={rec.session or 'unknown'}")
        elif d == "spread":
            parts.append(f"spread={_spread_bucket(rec)}")
        elif d == "vol":
            parts.append(f"vol={_bucket(_f(rec.vol_frac), VOL_BUCKETS)}")
        elif d == "momentum":
            parts.append(f"momentum={_bucket(_f(rec.momentum_z), MOMENTUM_BUCKETS)}")
    return "|".join(parts) if parts else "all"


def post_fill_alpha(rec: FillRecord, basis: str) -> float | None:
    """The observation this model learns from, on ONE named basis, signed so bigger is better.

    A cost basis (`slip_r`) is negated: paying less to get in is worth exactly as much as making
    more after getting in, and putting them on one sign is what lets a report say "this style is
    worth +0.03R" without a footnote about which direction is good.
    """
    v = _f(getattr(rec, basis, None))
    if v is None:
        return None
    return -v if basis in _COST_BASES else v


def _mean_ci(xs: Sequence[float]) -> tuple[float, float, float, float]:
    """(mean, lo, hi, se)."""
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return m, m - Z95 * se, m + Z95 * se, se


def _choose_basis(recs: Sequence[FillRecord], min_rows: int) -> tuple[str, dict[str, int]]:
    """The tightest basis with at least `min_rows` populated observations, and the census.

    Tightest FIRST, because the tightest axis answers the same question with the least data. A
    basis with fewer rows than the loosest is still preferred when it clears the floor: 60 rows
    of slippage settle a 0.04R question that 600 rows of trade P&L would not.
    """
    census = {b: sum(1 for r in recs if post_fill_alpha(r, b) is not None) for b in BASES}
    for b in BASES:
        if census[b] >= min_rows:
            return b, census
    best = max(census, key=lambda b: census[b]) if census else BASES[0]
    return best, census


@dataclass(frozen=True)
class ChoiceSurface:
    """The fitted surface, plus the reason it may or may not be used."""

    status: str
    basis: str
    dims: tuple[str, ...]
    #: cell -> style -> {n, mean, ci95, se}
    cells: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    #: cell -> {best, advantage_r, advantage_ci95, status, why}
    verdicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    power: dict[str, Any] = field(default_factory=dict)
    basis_census: dict[str, int] = field(default_factory=dict)
    n_observations: int = 0
    why: str = ""

    @property
    def usable(self) -> bool:
        return self.status == MEASURED

    def to_row(self) -> dict[str, Any]:
        return {"status": self.status, "basis": self.basis, "dims": list(self.dims),
                "n_observations": self.n_observations, "basis_census": self.basis_census,
                "cells": self.cells, "verdicts": self.verdicts, "power": self.power,
                "why": self.why, "styles": STYLE_ALIASES, "baseline": BASELINE_STYLE}

    def choose(self, condition: str, available: Sequence[str] = (),
               fallback: str = BASELINE_STYLE) -> tuple[str, str]:
        """The style to use, and why. Returns `fallback` unchanged whenever the gate is shut.

        THE REFUSAL IS THE FEATURE. A cell that has not reached its required n returns the
        caller's own fallback with an UNMEASURED reason, so a caller wiring this in cannot
        accidentally start routing on noise by forgetting to check a status field.
        """
        if not self.usable:
            return fallback, f"{UNMEASURED}: {self.why}"
        v = self.verdicts.get(condition)
        if not v or v.get("status") != MEASURED:
            why = (v or {}).get("why", "no cell for this condition")
            return fallback, f"{UNMEASURED}: {why}"
        best = str(v.get("best") or "")
        if available and best not in set(available):
            return fallback, (f"{UNMEASURED}: best measured style {best!r} is not available for "
                              "this order")
        return best, (f"{MEASURED}: {best} beats {BASELINE_STYLE} by "
                      f"{v.get('advantage_r')}R on {self.basis}, CI {v.get('advantage_ci95')}")


def fit(records: Iterable[FillRecord | Mapping[str, Any]], *,
        dims: Sequence[str] = CONDITION_DIMS,
        target_delta_r: float = TARGET_DELTA_R,
        alpha: float = DEFAULT_ALPHA, power: float = DEFAULT_POWER,
        min_rows_for_basis: int = 30) -> ChoiceSurface:
    """Assemble the conditional surface, then gate it.

    The gate is `sample_power.verdict` on the THINNEST arm of the cell being compared, charged
    Bonferroni for every (cell, non-baseline style) pair the fit examined. A cell passes only when
    it has the required n on both arms AND the advantage interval excludes zero; a surface passes
    only when at least one cell does.
    """
    recs = [r if isinstance(r, FillRecord) else record_from_row(r) for r in records]
    #: Only FILLED rows: a rejected order has no post-fill alpha, and a style that rejects more
    #: often is penalised through the fill rate the twin already measures, not by silently
    #: contributing zeros here.
    recs = [r for r in recs if r.status == "FILLED"]
    dims_t = tuple(dims)
    basis, census = _choose_basis(recs, min_rows_for_basis)
    obs: list[tuple[str, str, float]] = []
    for r in recs:
        y = post_fill_alpha(r, basis)
        style = (r.algo or r.execution_style or "").strip()
        if y is None or not style:
            continue
        obs.append((condition_of(r, dims_t), style, y))

    cells: dict[str, dict[str, dict[str, Any]]] = {}
    for cell, style, y in obs:
        cells.setdefault(cell, {}).setdefault(style, {"n": 0, "_xs": []})
        cells[cell][style]["_xs"].append(y)
    n_pairs = 0
    for styles in cells.values():
        for style, blob in styles.items():
            xs = blob.pop("_xs")
            m, lo, hi, se = _mean_ci(xs)
            blob.update({"n": len(xs), "mean": round(m, 8),
                         "ci95": ([round(lo, 8), round(hi, 8)] if len(xs) > 1 else None),
                         "se": round(se, 8)})
            if style != BASELINE_STYLE:
                n_pairs += 1
    n_comparisons = max(1, n_pairs)

    sigma = sigma_of([y for _, _, y in obs])
    verdicts: dict[str, dict[str, Any]] = {}
    any_measured = False
    for cell, styles in cells.items():
        base = styles.get(BASELINE_STYLE)
        others = {s: b for s, b in styles.items() if s != BASELINE_STYLE}
        if base is None or not others:
            verdicts[cell] = {"status": UNMEASURED, "best": None, "why": (
                "a choice needs the baseline style and at least one alternative in the same "
                f"cell; this cell has {sorted(styles)}")}
            continue
        best_style, best_adv, best_ci, best_pv = None, None, None, None
        for s, b in others.items():
            n_arm = min(int(base["n"]), int(b["n"]))
            pv: PowerVerdict = power_verdict(
                n_have=n_arm, delta_target=target_delta_r, sigma=sigma,
                reference_sigma=REFERENCE_SIGMA_R.get(basis, 1.0), alpha=alpha, power=power,
                n_comparisons=n_comparisons, what=f"{cell} {s} vs {BASELINE_STYLE} on {basis}")
            adv = float(b["mean"]) - float(base["mean"])
            sd = math.sqrt(float(b["se"]) ** 2 + float(base["se"]) ** 2)
            ci = [adv - Z95 * sd, adv + Z95 * sd]
            enough = pv.status == MEASURED and n_arm >= MIN_CELL_N
            if enough and ci[0] > 0 and (best_adv is None or adv > best_adv):
                best_style, best_adv, best_ci, best_pv = s, adv, ci, pv
            if best_pv is None:
                best_pv = pv
        if best_style is None:
            thinnest = min((int(b["n"]) for b in styles.values()), default=0)
            need = max(best_pv.n_required, MIN_CELL_N) if best_pv else MIN_CELL_N
            verdicts[cell] = {
                "status": UNMEASURED, "best": None,
                "n_needed_per_arm": need,
                "shortfall_per_arm": max(0, need - thinnest),
                "why": (f"no alternative style beats {BASELINE_STYLE} with an interval clear of "
                        f"zero at the required sample (power says "
                        f"{best_pv.n_required if best_pv else '?'} per arm, floored at "
                        f"{MIN_CELL_N}); " + (best_pv.why if best_pv else ""))}
            continue
        any_measured = True
        verdicts[cell] = {"status": MEASURED, "best": best_style,
                          "advantage_r": round(best_adv or 0.0, 8),
                          "advantage_ci95": [round(best_ci[0], 8), round(best_ci[1], 8)]
                          if best_ci else None,
                          "power": best_pv.to_row() if best_pv else None,
                          "why": f"{best_style} beats {BASELINE_STYLE} on {basis}"}

    total_arm = min((int(b["n"]) for st in cells.values() for b in st.values()), default=0)
    gate = power_verdict(n_have=total_arm, delta_target=target_delta_r, sigma=sigma,
                         reference_sigma=REFERENCE_SIGMA_R.get(basis, 1.0), alpha=alpha,
                         power=power, n_comparisons=n_comparisons,
                         what=f"thinnest arm on {basis}")
    status = MEASURED if any_measured else UNMEASURED
    why = ("at least one cell has a style beating the baseline at the required sample"
           if any_measured else
           (f"{len(obs)} usable observations on basis {basis!r} across {len(cells)} cells; no "
            f"cell reaches the sample a {target_delta_r:g}R difference needs. "
            "Harness is live and collecting; the model is NOT fitted."))
    return ChoiceSurface(status=status, basis=basis, dims=dims_t, cells=cells,
                         verdicts=verdicts, basis_census=census, n_observations=len(obs),
                         power={"gate": gate.to_row(), "comparisons_charged": n_comparisons,
                                "target_delta_r": target_delta_r},
                         why=why)


def requirements(*, target_delta_r: float = TARGET_DELTA_R, alpha: float = DEFAULT_ALPHA,
                 power: float = DEFAULT_POWER, n_styles: int = 4,
                 sigma_by_basis: Mapping[str, float] | None = None) -> dict[str, Any]:
    """The collection target, priced. What sample each tier x basis needs before it may be fitted.

    THIS IS THE DELIVERABLE WHEN THE MODEL IS NOT. It is a table the desk can plan against: it
    says the unconditional slippage comparison is reachable in tens of fills, the session-level
    one in low hundreds, and the full four-dimensional cross on trade P&L is not reachable at any
    plausible order rate -- which is the argument for measuring execution on markouts and
    slippage rather than on realised trade outcomes, made in numbers rather than in prose.
    """
    from libs.execution.sample_power import required_n
    sig = dict(REFERENCE_SIGMA_R)
    sig.update(sigma_by_basis or {})
    out: dict[str, Any] = {
        "target_delta_r": target_delta_r, "alpha": alpha, "power": power,
        "n_styles": n_styles, "baseline": BASELINE_STYLE,
        "sigma_by_basis": sig,
        "note": ("n is PER ARM per cell; a two-arm comparison needs 2n filled observations in "
                 "that cell, and a tier needs that in every cell it wants a verdict for. "
                 "sigma values are declared references until the corpus supplies its own."),
        "tiers": {},
    }
    per_cell_pairs = max(1, n_styles - 1)
    for name, dims, n_cells in TIERS:
        comparisons = per_cell_pairs * n_cells
        row: dict[str, Any] = {"dims": list(dims), "n_cells": n_cells,
                               "comparisons_charged": comparisons, "by_basis": {}}
        for basis, s in sig.items():
            n = required_n(s, target_delta_r, alpha=alpha, power=power,
                           n_comparisons=comparisons)
            row["by_basis"][basis] = {
                "sigma": s, "n_per_arm": n, "n_per_cell": n * n_styles,
                "n_total_fills": n * n_styles * n_cells,
            }
        out["tiers"][name] = row
    # THE ANSWER THE DESK CAN ACT ON, said first rather than left in the table. A collection
    # target of 29 million fills is a number nobody plans against; the cheapest cell that settles
    # the same question is, and it is reachable inside one live quarter.
    cheap = out["tiers"]["unconditional"]["by_basis"][BASES[0]]
    out["cheapest_measurable"] = {
        "tier": "unconditional", "basis": BASES[0],
        "n_per_arm": max(cheap["n_per_arm"], MIN_CELL_N),
        "n_total_fills": max(cheap["n_per_arm"], MIN_CELL_N) * n_styles,
        "floor_applied": cheap["n_per_arm"] < MIN_CELL_N,
        "why": ("start here. Comparing execution styles on the SLIPPAGE they paid answers "
                f"'which style is cheaper' at a {target_delta_r:g}R resolution for two orders of "
                "magnitude less data than comparing them on trade P&L, because the numerator's "
                "dispersion -- not the desk's cleverness -- sets the sample. Condition later: "
                "each dimension added multiplies the requirement by its bucket count AND widens "
                "the multiplicity charge."),
        "then": ["session", "session_x_spread", "full"],
    }
    return out
