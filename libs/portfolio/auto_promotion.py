"""AUTO-PROMOTION -- the wire from EVIDENCE to CAPITAL, with the principal's arming kept intact.

THE MEASURED DEFICIT THIS CLOSES (L1.59). "The desk's measured deficit is not its science; it is
the clock between holding evidence and holding a position." Stage-B already publishes ELIGIBLE the
moment the evidence bar is met, and `run_live_ladder` then correctly declares
`authority: NONE -- recommendations only`. So a candidate that has EARNED capital sits in a report
until a human reads it. Every day in that gap is economic life thrown away by the desk's own
validator -- the exact waste `evidence_clock` was written to end one stage earlier.

**WHAT IS AUTOMATED IS THE DECISION, NEVER THE ARMING.** The principal arms live trading ONCE,
explicitly, by writing `data/auto_promotion_armed.json`. That act is unchanged and remains theirs:
this module refuses everything while it is absent, and the Tier-3 ruin rail
(`scripts/run_deadman_switch.py`) is untouched and unreadable from here. What stops being manual is
the PER-CANDIDATE decision, which was never a judgement call -- it was a lookup against a bar that
was already computed.

**EVIDENCE DETERMINES SIZE; TIME DOES NOT.** There is no calendar gate here and none may be added.
A strategy reaching the bar in nine days is promoted in nine days; one that never reaches it is
never promoted, however long it runs. Adding "and at least N days" would reintroduce precisely the
grandma-time habit L1.48 abolished.

**IT SIZES SMALL AND IT SIZES ONCE.** A first live allocation is an EXPERIMENT whose purpose is to
produce execution evidence that shadow cannot: real fills, real slippage, real adverse selection.
Its size is therefore set by what the desk can afford to be wrong about, not by how good the
evidence looks -- confidence scales the clip only within a hard cap, because the failure this
guards against is a correct edge with a broken implementation, and that failure is invisible in
every backtest and every shadow run.

**IT PLACES NOTHING.** Returns a decision. The executor places orders, the risk kernel bounds them,
and the deadman can stop everything regardless of what this module concluded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ARMED_MARKER",
    "MAX_FIRST_CLIP_FRAC",
    "MAX_LIVE_STRATEGIES",
    "PromotionDecision",
    "decide",
    "is_armed",
]

_ROOT = Path(__file__).resolve().parents[2]

#: The principal's explicit arming. Absent = every promotion refused. Under data/, so it is
#: gitignored and cannot travel with the repo into a clone that would then believe it is armed.
ARMED_MARKER = "data/auto_promotion_armed.json"

#: Hard ceiling on a FIRST live clip, as a fraction of deployable equity. Not a tuning parameter:
#: the first allocation exists to buy execution evidence, and the amount of money required to
#: learn that fills are worse than modelled is small. Confidence may scale WITHIN this; nothing
#: scales past it.
MAX_FIRST_CLIP_FRAC = 0.02

#: How many strategies may hold auto-promoted capital at once. A cap on CONCURRENT automated
#: decisions, deliberately separate from the Holm cohort cap: that one bounds multiplicity, this
#: one bounds how much of the book can be sitting on decisions no human reviewed.
MAX_LIVE_STRATEGIES = 3


@dataclass(frozen=True)
class PromotionDecision:
    """PROMOTE / REFUSE, the clip, and the reason -- which is the part that gets read later."""

    promote: bool
    clip_frac: float
    why: str
    candidate: str = ""

    @property
    def refused(self) -> bool:
        return not self.promote


def is_armed(root: Path | str | None = None) -> tuple[bool, str]:
    """Has the principal armed automated promotion? Fail-closed, and never inferred.

    Deliberately NOT derivable from config, from an env var alone, or from the presence of API
    keys. Keys mean the desk CAN trade; this marker means the principal has decided it MAY promote
    without being asked each time. Conflating the two would let installing credentials silently
    grant an authority nobody granted.
    """
    base = Path(root) if root is not None else _ROOT
    p = base / ARMED_MARKER
    try:
        blob = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return False, (
            f"{ARMED_MARKER} absent or unreadable -- automated promotion is NOT armed. Every "
            "candidate is refused and the ladder stays advisory. This file is the principal's "
            "act and is never written by an organ")
    if blob.get("armed") is not True:
        return False, f"{ARMED_MARKER} present but `armed` is not true -- refusing"
    return True, f"armed by the principal at {blob.get('armed_at') or 'an unrecorded time'}"


def decide(
    candidate: dict[str, Any],
    *,
    live_count: int,
    rails_ok: bool,
    rails_why: str = "",
    root: Path | str | None = None,
    max_clip: float = MAX_FIRST_CLIP_FRAC,
    max_live: int = MAX_LIVE_STRATEGIES,
    deployable_usd: float | None = None,
    min_notional_usd: float | None = None,
) -> PromotionDecision:
    """Should this Stage-B-eligible candidate receive a first live clip, and how large?

    `candidate` is a row from `web/axis_shadows.json` (or any Stage-B artifact of the same shape):
    it must carry `verdict`, `forward_days`, `nw_t` and `holm_bar`. Every gate below is a REFUSAL
    that must pass; there is no scoring, because a weighted score lets a strong number on one axis
    buy its way past a hard requirement on another.
    """
    name = str(candidate.get("axis") or candidate.get("name") or "?")

    armed, why_armed = is_armed(root)
    if not armed:
        return PromotionDecision(False, 0.0, why_armed, name)

    if not rails_ok:
        return PromotionDecision(False, 0.0, (
            f"risk rails are not clear ({rails_why or 'unstated'}) -- evidence never overrides a "
            "rail. A rail holding the book is a statement about survival; a Stage-B verdict is a "
            "statement about one edge, and the first cannot be outvoted by the second"), name)

    if live_count >= max_live:
        return PromotionDecision(False, 0.0, (
            f"{live_count} strategies already hold auto-promoted capital (cap {max_live}) -- this "
            "bounds how much of the book sits on decisions no human reviewed, separately from the "
            "Holm cohort cap which bounds multiplicity"), name)

    verdict = str(candidate.get("verdict") or "")
    if verdict != "ELIGIBLE":
        return PromotionDecision(False, 0.0, (
            f"verdict is {verdict or 'ABSENT'}, not ELIGIBLE -- Stage-B has not ruled that the "
            "evidence bar is met. Backtest evidence has ZERO promotion authority under the "
            "two-stage law, so nothing upstream of this verdict can substitute for it"), name)

    t = candidate.get("nw_t")
    bar = candidate.get("holm_bar")
    if not isinstance(t, (int, float)) or not isinstance(bar, (int, float)):
        return PromotionDecision(False, 0.0, (
            "the t-statistic or the Holm bar is UNMEASURED on this row -- an ELIGIBLE verdict "
            "whose own arithmetic cannot be re-checked here is not evidence this module may act "
            "on. Absence must never resolve to the answer that spends money"), name)
    if float(t) < float(bar):
        return PromotionDecision(False, 0.0, (
            f"t={float(t):.3f} is below the Holm bar {float(bar):.3f} -- the verdict and the "
            "arithmetic disagree, which is a defect to investigate rather than a promotion to "
            "take. Re-checking rather than trusting the label is the whole point of reading both"),
            name)

    obs = candidate.get("forward_days")
    need = candidate.get("need")
    if not isinstance(obs, (int, float)) or (isinstance(need, (int, float))
                                             and float(obs) < float(need)):
        return PromotionDecision(False, 0.0, (
            f"forward observations {obs!r} short of the required {need!r} -- and this counts "
            "EFFECTIVE INDEPENDENT observations, never elapsed days, so a busy afternoon cannot "
            "buy eligibility"), name)

    # CLIP: confidence scales the experiment only WITHIN the cap, and the cap is what binds. The
    # margin over the bar is a t-ratio, so it is already scale-free; halving it again keeps even a
    # spectacular t from spending more than a modest fraction of the ceiling.
    margin = float(t) / float(bar) if float(bar) > 0 else 1.0
    clip = min(max_clip, max_clip * min(1.0, (margin - 1.0) / 2.0 + 0.5))
    clip = max(clip, max_clip * 0.25)          # never so small the fills teach nothing

    # A CLIP BELOW VENUE MINIMUM NOTIONAL IS NOT A SMALL POSITION, IT IS AN UNPLACEABLE ONE.
    # Found the moment a real small book was proposed (2026-08-14, $200 deployable): 2% of $200 is
    # $4, and Binance minimum notional is roughly $5-10 PER LEG, so a carry needs ~$10-20. Without
    # this check the module returns PROMOTE with a clip the executor cannot place, and the failure
    # surfaces as a rejected order rather than as a refused promotion -- a decision that looks
    # taken, is logged as taken, and never happens.
    #
    # THE HONEST RESOLUTION IS TO REFUSE, NOT TO ROUND UP. Rounding the clip up to the venue
    # minimum would breach the cap this module exists to enforce, and would do it silently, in the
    # one direction that puts more money on an unproven edge than the principal authorised. What is
    # too small to place at 2% is too concentrated to place at all.
    if deployable_usd is not None and min_notional_usd is not None:
        clip_usd = clip * float(deployable_usd)
        if clip_usd < float(min_notional_usd):
            need_frac = float(min_notional_usd) / float(deployable_usd)
            return PromotionDecision(False, 0.0, (
                f"the clip this candidate earned is ${clip_usd:,.2f} ({clip:.2%} of "
                f"${float(deployable_usd):,.2f}), BELOW the venue minimum notional of "
                f"${float(min_notional_usd):,.2f}. It cannot be placed. Reaching the minimum would "
                f"require {need_frac:.1%} of deployable equity against a {max_clip:.1%} cap -- so "
                "this is not a sizing question, it is a statement that the book is too small to "
                "hold this position at the authorised concentration. Rounding up to the minimum "
                "would breach the cap silently, in the direction that puts more money on an "
                "unproven edge than the principal approved. Fund more, or place a first clip BY "
                "HAND as an explicit execution experiment"), name)

    return PromotionDecision(True, round(clip, 6), (
        f"ELIGIBLE with t={float(t):.3f} against a Holm bar of {float(bar):.3f} on {obs} effective "
        f"independent forward observations, rails clear, {live_count}/{max_live} auto-promoted "
        f"slots in use. {why_armed}. FIRST CLIP {clip:.4%} of deployable equity -- an experiment "
        "sized to buy execution evidence (real fills, real slippage, real adverse selection) that "
        "no shadow run can produce, not sized to the strength of the edge"), name)


def summarise(decisions: list[PromotionDecision]) -> dict[str, Any]:
    """What the cycle prints and the dashboard reads. REFUSALS ARE THE INTERESTING HALF."""
    promoted = [d for d in decisions if d.promote]
    return {
        "n_considered": len(decisions),
        "n_promoted": len(promoted),
        "n_refused": len(decisions) - len(promoted),
        "promoted": [{"candidate": d.candidate, "clip_frac": d.clip_frac, "why": d.why}
                     for d in promoted],
        "refusals": [{"candidate": d.candidate, "why": d.why}
                     for d in decisions if d.refused],
        "note": ("Automated promotion decides WHICH eligible candidate receives a first live clip. "
                 "It does not arm live trading, does not place orders, does not size beyond the "
                 "cap, and cannot clear a risk rail. Every refusal states its own reason, because "
                 "a promotion path whose refusals are silent is indistinguishable from one that "
                 "is not running."),
    }
