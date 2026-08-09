"""SCREEN-STAGE SELECTION -- gap #71 (gate-optimality), and it activates a module the desk owned.

THE DEFECT, stated as the desk's own law rather than as an opinion. TWO_STAGE_DISCOVERY_LAW:
*"the backtest gauntlet is a SCREEN with ZERO promotion authority -- generation volume there is
unbounded and can never create a phantom edge, since nothing it produces reaches capital. Promotion
comes ONLY from pre-registered forward evidence, where the only multiplicity is the concurrent slot
count (Holm-corrected, MAX_FORWARD_SLOTS=12). The confirmation bar is a CONSTANT FOR LIFE: it never
rises with generation."*

The screen currently gates on Romano-Wolf FWER across ALL N candidates. FWER across N is, by
construction, a bar that RISES WITH GENERATION VOLUME -- the exact thing the law forbids -- and it
is measurably absolute: on the real 420-candidate campaign the best adjusted p is **0.522** at the
min-length window and **0.089** at the max-observation window, so **0 of 420 are selectable at any
window**. A gate that admits nobody carries zero information about candidate quality, which is the
same failure the campaign-constant PBO had (0/420 identically). Removing one weld and leaving the
other is not a fix.

THE CORRECTION, and it loosens NOTHING that guards capital:
  * SCREEN stage (no promotion authority) -> control the expected FALSE-DISCOVERY PROPORTION among
    the shortlist with Benjamini-Hochberg. FDR controls a PROPORTION, so the bar does not escalate
    as generation grows: 5% of a 20-name shortlist and 5% of a 200-name shortlist are the same
    guarantee per selected name. That is what a ranking/filtering stage should control.
  * PROMOTION stage (forward clocks, real capital) -> UNCHANGED. Holm/FWER across the bounded
    concurrent slot count (MAX_FORWARD_SLOTS=12), pre-registered, never loosened. Every candidate
    still has to earn forward evidence before a cent moves.
Total error control is therefore intact and STRICTER where it matters: nothing reaches capital
without surviving both a proportion-controlled screen and a family-wise-controlled forward clock.

WHAT THIS IS NOT: it is not a new statistic. `libs/validation/fdr.py` (Benjamini-Hochberg /
Benjamini-Yekutieli) has existed and been tested in this repo the whole time and was ORPHANED from
the gauntlet -- an unused capability, which L2.9 counts as a defect. This module activates it.

DEPENDENCE: candidate returns in one campaign are heavily correlated (same universe, same era), and
plain BH assumes independence or positive regression dependence. `method="by"` selects
Benjamini-Yekutieli, which is valid under ARBITRARY dependence at the cost of a log(m) factor --
available and reported so the choice is explicit rather than assumed.

Pure numpy + the existing FDR primitives. import from libs.validation.screen_select.
"""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.fdr import benjamini_hochberg, benjamini_yekutieli
from libs.validation.stepwise import StepdownResult

Method = Literal["bh", "by"]

# The screen's q is the SAME 5% the family-wise bar used. Only the error rate being controlled
# changes (proportion of false discoveries among selected, instead of probability of any false
# discovery anywhere) -- not the tolerance.
_DEFAULT_Q = 0.05


class ScreenSelection(BaseModel):
    """Which candidates the SCREEN shortlists, and the honest error statement for that list."""

    model_config = ConfigDict(frozen=True)

    selected: list[bool]
    p_values: list[float]
    q: float
    method: str
    threshold: float
    n_selected: int
    n_candidates: int
    fwer_n_selected: int
    """How many the family-wise (Romano-Wolf) rule would have admitted -- kept alongside so the
    difference is always visible and never silently assumed away."""
    resolvable: bool
    """Whether the bootstrap is fine-grained enough for the SELECTION BOUNDARY to be meaningful.
    Bootstrap p-values are DISCRETE with atoms at k/B, and p=0 is attainable (no draw exceeded the
    observed statistic), so a coarse bootstrap does not make selection impossible -- the first
    version of this module claimed that and it was WRONG, corrected here rather than shipped. What
    coarseness actually costs is DISCRIMINATION: every candidate that beats all B draws ties at
    p=0 and the procedure cannot rank among them. False when the granularity 1/B is coarser than
    the q/m boundary, i.e. when the boundary falls inside one atom."""
    min_representable_p: float
    """1/B -- the smallest NON-ZERO p the bootstrap can express."""
    ties_at_floor: int
    """How many candidates share the minimum p. If this exceeds n_selected, the shortlist is cut
    through a tie and the ranking inside it is undetermined by this statistic alone."""
    required_n_boot: int
    """Draws needed for the q/m boundary to sit on an atom rather than inside one."""
    error_statement: str
    """Plain-language statement of exactly what is controlled, carried WITH the result so no
    downstream reader can mistake a shortlist for a promotion."""


def screen_select(stepdown: StepdownResult, *, q: float = _DEFAULT_Q,
                  method: Method = "by") -> ScreenSelection:
    """Shortlist candidates at the SCREEN stage under FDR control.

    stepdown: the Romano-Wolf result already computed for the campaign. FDR is applied to its
      `raw_p` -- the UNADJUSTED per-candidate bootstrap p-values. This is not a detail: feeding
      `adjusted_p` would be a DOUBLE correction (family-wise first, then FDR on top), which is
      statistically incoherent and was caught in calibration by evicting a known Sharpe-3 winner
      from a 60-null batch. Reusing the same bootstrap pass costs nothing.
    method: "by" (Benjamini-Yekutieli, valid under arbitrary dependence) by DEFAULT, because
      candidates within one campaign are correlated by construction. "bh" is available for
      genuinely independent families and is the less conservative of the two.

    ZERO PROMOTION AUTHORITY. A True here means "worth a pre-registered forward clock", never
    "deployable". The forward clock's Holm/FWER bar is untouched by this function.
    """
    raw = list(stepdown.raw_p) or list(stepdown.adjusted_p)   # legacy results carry no raw_p
    p = np.asarray(raw, dtype="float64")
    if p.size == 0:
        return ScreenSelection(
            selected=[], p_values=[], q=q, method=method, threshold=0.0, n_selected=0,
            n_candidates=0, fwer_n_selected=0, resolvable=False,
            min_representable_p=1.0, ties_at_floor=0, required_n_boot=0,
            error_statement="empty campaign -- nothing to select")
    res = benjamini_yekutieli(p, alpha=q) if method == "by" else benjamini_hochberg(p, alpha=q)
    n_sel = int(sum(res.rejected))
    fwer_n = int(sum(bool(x) for x in stepdown.rejected))
    # GRANULARITY REPORT. Bootstrap p-values are discrete atoms at k/B. Measured in calibration
    # 2026-07-30: at m=61 a KNOWN Sharpe-3 candidate landed at raw p=0.070, rank 4 of 61 -- THREE
    # NULLS scored better on that draw. That is sampling variance at T=500 with fat tails, not a
    # procedure defect, and the honest consequence is that a screen cannot be judged on whether one
    # seeded winner appears; it is judged on calibration across draws. What granularity DOES cost
    # is discrimination among candidates tied at the floor, which is what these fields report.
    m = int(p.size)
    min_p = 1.0 / float(stepdown.n_boot) if stepdown.n_boot else 1.0
    need = q / m if m else q
    resolvable = min_p <= need
    ties = int(np.count_nonzero(p <= p.min() + 1e-12))
    required = int(np.ceil(1.0 / need)) if need > 0 else 0
    name = "Benjamini-Yekutieli (arbitrary dependence)" if method == "by" \
        else "Benjamini-Hochberg (independence / PRDS)"
    return ScreenSelection(
        selected=[bool(x) for x in res.rejected],
        p_values=[float(x) for x in p],
        q=q, method=method, threshold=float(res.threshold),
        n_selected=n_sel, n_candidates=m, fwer_n_selected=fwer_n,
        resolvable=resolvable, min_representable_p=min_p, ties_at_floor=ties,
        required_n_boot=required,
        error_statement=(
            (f"COARSE BOOTSTRAP: {stepdown.n_boot} draws give granularity {min_p:.2g}, coarser "
             f"than the q/m boundary {need:.2g}, and {ties} candidate(s) tie at the minimum p. "
             f"Selection is still possible (p=0 is attainable) but the ranking among tied "
             f"candidates is undetermined by this statistic; n_boot >= {required} puts the "
             f"boundary on an atom. A measurement limit, NOT evidence about the candidates. ")
            if not resolvable else "")
            + (f"{name} at q={q:.0%}: among the {n_sel} shortlisted candidate(s), the EXPECTED "
            f"PROPORTION that are false discoveries is <= {q:.0%}. This is a SCREEN with zero "
            f"promotion authority; the family-wise rule would have admitted {fwer_n}. Promotion "
            f"still requires pre-registered forward evidence under the unchanged Holm/FWER bar "
            f"across the bounded concurrent-slot count."),
    )


def screen_report(stepdown: StepdownResult, *, q: float = _DEFAULT_Q) -> dict[str, Any]:
    """Both dependence assumptions side by side -- so the choice is a decision, not a default."""
    by = screen_select(stepdown, q=q, method="by")
    bh = screen_select(stepdown, q=q, method="bh")
    return {
        "n_candidates": by.n_candidates,
        "q": q,
        "fwer_selected": by.fwer_n_selected,
        "by_selected": by.n_selected,
        "bh_selected": bh.n_selected,
        "by_threshold": by.threshold,
        "bh_threshold": bh.threshold,
        "min_p": float(min(by.p_values)) if by.p_values else None,
        "resolvable": by.resolvable,
        "ties_at_floor": by.ties_at_floor,
        "min_representable_p": by.min_representable_p,
        "required_n_boot": by.required_n_boot,
        "note": "fwer_selected is the incumbent gate's answer. A screen that admits nobody at any "
                "window carries zero information about candidate quality -- measured 0/420 with "
                "min adjusted p 0.522 (min-length window) and 0.089 (max-observation window).",
    }
