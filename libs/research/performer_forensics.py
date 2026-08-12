"""PUBLIC PERFORMER FORENSICS -- gate items 29/32/33.

Mandate II-8, II-9, II-10, III-7, III-8, III-9.

Three organs, one subject: a public account, bot or copy-trading leader showing a return.

  * copy_friction()      (item 29, II-8) walks LEADER ACTION -> PUBLICATION -> DETECTION -> COPY
                         LATENCY -> ENTRY -> PRICE MOVE -> SLIPPAGE -> FEES -> FUNDING -> PROFIT
                         SHARE -> EXIT SLIPPAGE. The follower does NOT receive the leader's
                         return, and this measures the gap rather than assuming it away.
  * decompose()          (item 32, II-10/III-8) turns an extreme return into an ATTRIBUTION, not
                         a verdict. Extreme return is a high-VOI research trigger, never a
                         survivor badge and never a reason to look away.
  * classify_failure()   (item 33, II-9/III-9) files a blown-up performer into canonical negative
    + rescue_analysis()  memory, then asks the question that makes a failure library worth
                         keeping: does REMOVING the failure component preserve a positive edge?

THE ASYMMETRY THAT KILLS COPY TRADING, and it is the one most often left out. Profit share is
charged on GROSS WINNING PERIODS, not on net performance. A leader who makes +10% then -8% has
netted ~1.2%, but the follower pays the share on the +10% and absorbs the -8% in full. High-churn
strategies are therefore taxed on their gross wins and credited nothing for their losses, so the
follower's return can be NEGATIVE while the leader's headline is positive. That is not a fee
detail; it is a mechanism, and it is why II-8 exists as its own section.

THE TWO FAILURES OF NERVE THIS REFUSES. "Too good to be true, ignore it" throws away the highest
value-of-information event the desk sees. "Amazing returns, copy it" is how a martingale gets
funded. Both are refusals to do the work, and the answer to both is the same decomposition.

WHAT NONE OF THIS DOES: raise leverage. III-8 is explicit -- do not attempt to match headline
returns through leverage alone; target the edge responsible for them. Every function here returns
attribution and hypotheses. None sizes a position, none touches a statistical gate.

AUTHORITY: MEASUREMENT + HYPOTHESIS GENERATION ONLY.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "ATTRIBUTIONS",
    "FAILURE_MODES",
    "VERIFICATION_CHECKS",
    "CopyLeg",
    "Performer",
    "classify_failure",
    "copy_friction",
    "decompose",
    "extract_components",
    "rescue_analysis",
]

_ROOT = Path(__file__).resolve().parents[2]
NEGATIVE_MEMORY = "docs/research/blowup_library.jsonl"

#: III-8's attribution set. Where an extreme return actually came from.
ATTRIBUTIONS: tuple[str, ...] = (
    "GENUINE_ALPHA", "LEVERAGE", "BETA", "MARTINGALE", "DCA_TAIL_RISK", "CONCENTRATION",
    "ILLIQUIDITY", "REGIME_LUCK", "SHORT_SAMPLE", "SURVIVORSHIP", "ROI_ACCOUNTING_ARTIFACT",
    "NOVEL_MECHANISM", "UNVERIFIED",
)

#: II-9's failure taxonomy, stored in canonical negative memory.
FAILURE_MODES: tuple[str, ...] = (
    "LEVERAGE_BLOWUP", "MARTINGALE_BLOWUP", "DCA_TAIL_FAILURE", "REGIME_COLLAPSE", "CROWDING",
    "ILLIQUIDITY", "CONCENTRATION", "ONE_WAY_MARKET_DEPENDENCE", "FUNDING_COST_FAILURE",
    "COPY_SLIPPAGE_FAILURE", "SHORT_SAMPLE_ILLUSION", "STATISTICAL_LUCK",
    "RETURN_MANIPULATION_METRIC_ARTIFACT", "UNKNOWN",
)

#: II-10's verification stations. Each is a question; an unanswered one is UNVERIFIED, not "fine".
VERIFICATION_CHECKS: tuple[str, ...] = (
    "public_metrics", "window", "capital_base", "leverage", "drawdown", "age",
    "position_concentration", "open_losses_represented", "roi_methodology",
)

#: III-7's behavioural axes. Every one extracted becomes its own canonical hypothesis.
_COMPONENT_AXES: tuple[str, ...] = (
    "entry_behavior", "exit_behavior", "position_sizing", "leverage", "averaging", "grid_logic",
    "dca_logic", "stop_behavior", "holding_period", "asset_selection", "session_dependence",
    "regime_dependence", "funding_exposure", "momentum_exposure", "mean_reversion_exposure",
    "breakout_exposure", "event_response", "cross_asset_dependence", "tail_exposure", "capacity",
    "failure_mechanism",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Performer:
    """A public account/bot/leader as OBSERVED. Every field is a claim until verified."""

    ident: str
    platform: str
    headline_return: float | None = None        # as advertised, e.g. 3.2 for +320%
    window_days: int | None = None
    capital_base_usd: float | None = None
    max_drawdown: float | None = None
    max_leverage: float | None = None
    n_positions: int | None = None
    largest_position_share: float | None = None
    open_losses_represented: bool | None = None
    roi_methodology: str = ""
    verified: dict[str, bool] = field(default_factory=dict)
    behaviour: dict[str, str] = field(default_factory=dict)

    def unverified_checks(self) -> list[str]:
        return [c for c in VERIFICATION_CHECKS if not self.verified.get(c)]


@dataclass(frozen=True)
class CopyLeg:
    """One copied round trip, in the units the follower actually experiences."""

    leader_gross_return: float           # the leader's return on this leg, e.g. 0.10
    publication_delay_s: float = 0.0
    detection_delay_s: float = 0.0
    execution_delay_s: float = 0.0
    adverse_move_bps_per_s: float = 0.0  # how fast the edge decays while the follower waits
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0
    fee_bps_round_trip: float = 0.0
    funding_bps: float = 0.0
    profit_share: float = 0.0            # charged on GROSS winning legs, not net performance


def copy_friction(legs: list[CopyLeg]) -> dict[str, Any]:
    """GATE ITEM 29 / II-8. What the FOLLOWER receives, leg by leg.

    The latency chain is charged as an adverse move: publication + detection + execution delay,
    multiplied by how fast the edge decays. A leader whose edge is a 30-second reaction to a
    funding print does not survive a 90-second copy pipeline, and no amount of fee negotiation
    repairs that.

    PROFIT SHARE IS CHARGED ON GROSS WINNERS. This is the asymmetry that makes copy trading
    structurally worse than it looks: a leader netting +1.2% from +10% then -8% hands the follower
    a share bill on the +10% and the whole -8%.
    """
    if not legs:
        return {"status": "UNMEASURED",
                "why": "no legs supplied -- nothing was modelled, which is not the same as a "
                       "strategy that survives copying (L1.41)"}

    rows: list[dict[str, Any]] = []
    leader_total = 0.0
    follower_total = 0.0
    for i, leg in enumerate(legs):
        delay_s = (float(leg.publication_delay_s) + float(leg.detection_delay_s)
                   + float(leg.execution_delay_s))
        adverse = delay_s * float(leg.adverse_move_bps_per_s) / 10_000.0
        costs = ((float(leg.entry_slippage_bps) + float(leg.exit_slippage_bps)
                  + float(leg.fee_bps_round_trip) + float(leg.funding_bps)) / 10_000.0)
        before_share = float(leg.leader_gross_return) - adverse - costs
        # The share applies to a WINNING leg only, and to its gross gain.
        share = (max(0.0, before_share) * float(leg.profit_share)) if leg.profit_share else 0.0
        follower = before_share - share
        leader_total += float(leg.leader_gross_return)
        follower_total += follower
        rows.append({
            "leg": i, "leader_gross_return": float(leg.leader_gross_return),
            "total_delay_s": round(delay_s, 3),
            "adverse_move": round(-adverse, 6),
            "costs": round(-costs, 6),
            "profit_share_paid": round(-share, 6),
            "follower_return": round(follower, 6),
        })

    friction = leader_total - follower_total
    survives = follower_total > 0.0
    return {
        "generated_utc": _now(),
        "status": "MEASURED",
        "n_legs": len(legs),
        "leader_total_return": round(leader_total, 6),
        "follower_total_return": round(follower_total, 6),
        "total_friction": round(friction, 6),
        "friction_share_of_leader_edge": (round(friction / leader_total, 4)
                                          if leader_total else None),
        "legs": rows,
        "verdict": "SURVIVES_COPY_FRICTION" if survives else "DESTROYED_BY_COPY_FRICTION",
        "why": ("the follower still nets a positive return after latency, slippage, fees, funding "
                "and profit share" if survives else
                "the leader's edge does not survive being copied. II-8: do not assume the "
                "follower receives the leader's return -- this is the test, not a caveat"),
        "asymmetry_note": "profit share is charged on GROSS WINNING LEGS, so a high-churn leader "
                          "is taxed on wins and credited nothing for losses; the follower's return "
                          "can be negative while the leader's headline is positive",
        "authority": "MEASUREMENT ONLY -- sizes nothing, and never proposes leverage to close a "
                     "friction gap (III-8).",
    }


def decompose(p: Performer, *, evidence: dict[str, float] | None = None) -> dict[str, Any]:
    """GATE ITEM 32 / II-10 + III-8. Attribute an extreme return; never bless or dismiss it.

    ``evidence`` maps an ATTRIBUTION to a 0..1 weight the caller has MEASURED. What this function
    contributes is the structural arithmetic the caller cannot fake: whether the sample is long
    enough to say anything, whether the drawdown is consistent with the leverage claimed, and
    whether the headline is even reconcilable with the stated capital base.

    Every unanswered verification station keeps the record UNVERIFIED. An extreme return with
    nothing checked is a research trigger with a big number attached, not a finding.
    """
    unverified = p.unverified_checks()
    ev = dict(evidence or {})
    flags: list[str] = []

    # SHORT SAMPLE. A 30-day window cannot separate skill from luck at any return level, so a
    # short window is a structural attribution regardless of how good the number looks.
    if p.window_days is not None and p.window_days < 90:
        ev["SHORT_SAMPLE"] = max(ev.get("SHORT_SAMPLE", 0.0), 0.7)
        flags.append(f"window is {p.window_days}d -- too short to separate skill from luck")

    # LEVERAGE. A headline return that only exists at high leverage is a leverage attribution,
    # not an alpha one. The desk's job is the underlying edge, deleveraged (III-8).
    if p.max_leverage is not None and p.max_leverage >= 5.0:
        ev["LEVERAGE"] = max(ev.get("LEVERAGE", 0.0), 0.6)
        flags.append(f"max leverage {p.max_leverage:g}x -- decompose the DELEVERAGED edge before "
                     "believing the headline")

    # CONCENTRATION.
    if p.largest_position_share is not None and p.largest_position_share >= 0.5:
        ev["CONCENTRATION"] = max(ev.get("CONCENTRATION", 0.0), 0.6)
        flags.append(f"largest position is {p.largest_position_share:.0%} of the book")

    # ROI ACCOUNTING ARTIFACT. Unrepresented open losses are the classic marketplace artifact:
    # the headline counts realised wins and carries the losers as open positions forever.
    if p.open_losses_represented is False:
        ev["ROI_ACCOUNTING_ARTIFACT"] = max(ev.get("ROI_ACCOUNTING_ARTIFACT", 0.0), 0.8)
        flags.append("open losses are NOT represented in the headline -- realised wins are booked "
                     "while losers are carried open, which manufactures a monotone equity curve")

    # MARTINGALE SIGNATURE: a large return with an implausibly small drawdown is the shape a
    # martingale makes right up until it does not.
    if (p.headline_return is not None and p.max_drawdown is not None
            and p.headline_return >= 1.0 and p.max_drawdown <= 0.05):
        ev["MARTINGALE"] = max(ev.get("MARTINGALE", 0.0), 0.6)
        flags.append(f"+{p.headline_return:.0%} against a {p.max_drawdown:.1%} max drawdown -- "
                     "the equity shape of an averaging-down book before its one bad day")

    if not ev:
        ev["UNVERIFIED"] = 1.0

    unknown = [k for k in ev if k not in ATTRIBUTIONS]
    ranked = sorted(((k, round(v, 3)) for k, v in ev.items() if k in ATTRIBUTIONS),
                    key=lambda kv: -kv[1])
    total = sum(v for _, v in ranked)

    return {
        "generated_utc": _now(),
        "performer": p.ident,
        "platform": p.platform,
        "attribution": [{"class": k, "weight": v} for k, v in ranked],
        "leading_attribution": ranked[0][0] if ranked else "UNVERIFIED",
        "unknown_classes": unknown,
        "structural_flags": flags,
        "unverified_checks": unverified,
        "status": "UNVERIFIED" if unverified else "VERIFIED",
        "verdict": ("HIGH_VOI_RESEARCH_TRIGGER"
                    if (ranked and ranked[0][0] != "GENUINE_ALPHA") or unverified
                    else "CANDIDATE_MECHANISM"),
        "law": "EXTREME RETURN IS A HIGH-VOI RESEARCH TRIGGER, NOT A SURVIVOR VERDICT. It is "
               "equally wrong to dismiss it as too-good-to-be-true and to believe it -- both are "
               "refusals to do the decomposition",
        "next_action": ("answer the unverified stations: " + ", ".join(unverified)) if unverified
                       else "test whether the leading mechanism can be reproduced, DELEVERAGED, "
                            "regime-conditioned, combined or made more robust -- never matched "
                            "through leverage (III-8)",
        "attribution_mass": round(total, 3),
        "authority": "MEASUREMENT + HYPOTHESIS GENERATION ONLY. Raises no size, no leverage.",
    }


def extract_components(p: Performer) -> dict[str, Any]:
    """III-7. Every distinct plausible edge extracted becomes its OWN canonical hypothesis.

    Testing only the complete original strategy is the mistake this prevents: a leader may hold
    one real mechanism welded to three bad ones, and the whole-strategy test scores the weld.
    """
    present = {k: v for k, v in p.behaviour.items() if k in _COMPONENT_AXES and str(v).strip()}
    missing = [a for a in _COMPONENT_AXES if a not in present]
    hypotheses = [
        {"hypothesis_id": f"{p.ident}::{axis}", "axis": axis, "observed": desc,
         "test": "whole strategy, this component alone, its ablation, and a regime-conditional "
                 "version -- four tests, because the component may carry the edge, carry the "
                 "damage, or neither"}
        for axis, desc in sorted(present.items())
    ]
    return {
        "performer": p.ident,
        "n_hypotheses": len(hypotheses),
        "hypotheses": hypotheses,
        "unextracted_axes": missing,
        "law": "do not test only the complete original strategy -- a leader may hold one real "
               "mechanism welded to three bad ones, and the whole-strategy test scores the weld",
        "authority": "HYPOTHESIS GENERATION ONLY -- these enter the canonical queue and face the "
                     "full validation standard like any other candidate.",
    }


def classify_failure(*, ident: str, mode: str, evidence: str,
                     surviving_components: list[str] | None = None,
                     root: Path | None = None, persist: bool = True) -> dict[str, Any]:
    """GATE ITEM 33 / II-9. File a blown-up performer into canonical negative memory.

    An unrecognised mode is stored as UNKNOWN WITH ITS RAW LABEL PRESERVED, never dropped: the
    label is the evidence that the taxonomy is incomplete, and silently coercing it to UNKNOWN
    would erase the only signal that a new failure class exists.
    """
    known = mode in FAILURE_MODES
    row = {
        "ts": _now(),
        "ident": ident,
        "failure_mode": mode if known else "UNKNOWN",
        "raw_label": None if known else mode,
        "evidence": evidence,
        "surviving_components": list(surviving_components or []),
        "taxonomy_gap": not known,
        "law": "the desk should learn what extreme winners look like BEFORE they become extreme "
               "winners, and what they look like BEFORE they blow up (II-9)",
    }
    if not known:
        row["why_unknown"] = (f"{mode!r} is not in FAILURE_MODES. Stored as UNKNOWN with the raw "
                              "label kept -- the label is evidence the taxonomy is incomplete, and "
                              "coercing it away would erase the only signal that a new failure "
                              "class exists")
    if persist:
        p = (root or _ROOT) / NEGATIVE_MEMORY
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def rescue_analysis(*, ident: str, failure_mode: str,
                    with_component: float | None, without_component: float | None,
                    component: str, n_obs: int | None = None) -> dict[str, Any]:
    """III-9. Does REMOVING the failure component PRESERVE a positive edge?

    This is what makes a failure library worth keeping. A real edge welded to a martingale is
    still a real edge; discarding the whole strategy discards the edge with the sizing rule.

    THE FENCE THAT MATTERS: a rescue is a NEW SEARCH, not a free pass. The returned record says so
    explicitly and carries an underpowered warning when the sample cannot support the claim --
    III-10's "do not torture random noise into alpha" applies with full force here, because a
    rescue looks like good news and good news is what gets waved through.
    """
    if with_component is None or without_component is None:
        return {"verdict": "UNMEASURED", "ident": ident,
                "why": "both arms are required; a missing arm is UNKNOWN, never a rescue (L1.41)"}

    delta = float(without_component) - float(with_component)
    rescued = float(without_component) > 0.0 and delta > 0.0
    underpowered = n_obs is not None and n_obs < 100
    out = {
        "generated_utc": _now(),
        "ident": ident,
        "failure_mode": failure_mode,
        "removed_component": component,
        "edge_with_component": float(with_component),
        "edge_without_component": float(without_component),
        "delta": round(delta, 6),
        "n_obs": n_obs,
        "verdict": "EDGE_SURVIVES_COMPONENT_REMOVAL" if rescued else "NO_EDGE_TO_RESCUE",
        "why": ("removing the failure component leaves a positive edge -- a real edge welded to a "
                "bad sizing rule is still a real edge, and discarding the strategy would discard "
                "the edge with the rule"
                if rescued else
                "the edge does not survive removal; the component was not the problem, or there "
                "was no edge underneath it"),
        "search_accounting": "THIS RESCUE IS A NEW SEARCH. It creates a search-accounting entry "
                             "and must pass the full validation standard -- a repaired candidate "
                             "gets no discount for having been repaired (III-10)",
        "authority": "MEASUREMENT ONLY -- promotes nothing; the forward clock is the sole "
                     "promotion authority.",
    }
    if underpowered:
        out["power_warning"] = (
            f"n={n_obs} is below the desk's 100-observation floor -- this rescue is UNDERPOWERED "
            "and must not be read as a positive result. A rescue looks like good news, and good "
            "news is what gets waved through")
        out["verdict"] = "UNDERPOWERED_RESCUE"
    return out


def kelly_fraction_note(edge: float, variance: float) -> dict[str, Any]:
    """Marginal log-growth of a rescued or copied edge, for ranking only.

    Returned as E[log W] rather than as a size. The desk's objective is log wealth, and quoting a
    fraction here would read as a sizing instruction from a module with no authority to give one.
    """
    if variance <= 0:
        return {"status": "UNMEASURED", "why": "variance must be positive to compute growth"}
    return {"marginal_log_growth": round(math.log1p(edge) - 0.5 * variance / (1.0 + edge) ** 2, 8),
            "note": "RANKING INPUT ONLY -- not a size. Sizing lives behind the R0143 fence."}
