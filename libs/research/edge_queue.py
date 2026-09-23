"""Four mechanisms with published evidence, as testable specs the desk can actually run.

WHY THIS EXISTS (principal, 2026-08-29)

The allocator has an exploration floor and nothing new to spend it on: every family it can reach
was already in the docket. A floor with no fresh mechanisms just re-runs old ground more evenly.
These four come from published evidence rather than from a parameter sweep, and each names a
PAYER -- a participant who must trade for a reason that is not a forecast. That is the property
that makes an edge survive: arbitrage cannot compete away a flow whose source is not choosing.

WHAT A SPEC HERE IS, AND IS NOT. It is a preregistration: claim, payer, observables, the
prediction, and the falsifiers that would kill it -- written BEFORE any trial is spent, so the
test cannot be redefined once results arrive. It is NOT a strategy, carries no parameters, and
has no promotion authority whatsoever. It enters the funnel at the same place every other
candidate does and faces the identical gauntlet.

EVERY SPEC CARRIES FALSIFIERS, and they are the most important field. A mechanism that cannot say
what would disprove it is not a hypothesis, and the desk has 12,535 candidates that never had to
answer the question. The randomised-clock falsifier in particular kills the most common failure
mode for all four of these: an effect that is really just generic intraday mean reversion wearing
an institutional story.

SOURCES are recorded per spec. A spec whose evidence cannot be traced is an assertion, and this
desk does not spend trials on assertions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from libs.research.semantic_space import Coordinate


@dataclass(frozen=True)
class EdgeSpec:
    """A preregistered mechanism. Frozen -- a hypothesis edited after results is not a test."""

    id: str
    claim: str
    payer: str
    constraint: str
    coordinate: Coordinate
    universe: tuple[str, ...]
    observables: tuple[str, ...]
    prediction: str
    conditioning: tuple[str, ...]
    falsifiers: tuple[str, ...]
    alternative_explanation: str
    distinguishing_test: str
    data_requirements: tuple[str, ...]
    source: str
    secondary: str = ""
    notes: str = ""

    def is_complete(self) -> tuple[bool, str]:
        """Every field a real trial requires. Missing any of them means DO NOT SPEND A TRIAL."""
        missing = [f for f in ("claim", "payer", "constraint", "prediction",
                               "alternative_explanation", "distinguishing_test", "source")
                   if not getattr(self, f)]
        if not self.falsifiers:
            missing.append("falsifiers")
        if not self.observables:
            missing.append("observables")
        if missing:
            return False, (f"incomplete preregistration, missing {', '.join(missing)} -- a "
                           f"hypothesis that cannot say what would disprove it is not testable "
                           f"and must not consume a trial")
        return True, "complete"


#: 1. HEDGING-DEMAND INTRADAY CONTINUATION.
#: Rest-of-day return predicts the final 30 minutes, with the effect reversing over following
#: days. Short-gamma dealers and leveraged-product rebalancers must trade WITH the move into the
#: close to stay hedged; that flow is mechanical, and its reversal once the constraint clears is
#: the second, independently falsifiable half of the claim.
HEDGING_DEMAND_CLOSE_FLOW = EdgeSpec(
    id="H-2026-0001-HEDGING_DEMAND_CLOSE_FLOW",
    claim=("Return from the previous session close to T-30m predicts the final 30-minute return "
           "in the same direction, and that displacement partially reverses over 1-3 days."),
    payer=("short-gamma dealers and leveraged/inverse product issuers, who must rebalance in the "
           "direction of the move to remain hedged, and cannot wait for a better price"),
    constraint="the hedge must be executed before the close, at whatever price exists",
    coordinate=Coordinate("options_hedging", "new_york", "magnitude", "continuation", "15m"),
    universe=("XAUUSD", "XAGUSD", "US500", "US30", "NAS100", "EURUSD", "USDJPY", "GBPUSD",
              "USOIL", "UKOIL"),
    observables=("rest_of_day_return", "final_30m_return", "realized_vol", "volume",
                 "spread", "session_clock"),
    prediction=("larger |rest-of-day return| -> larger same-direction final-30m return; effect "
                "increasing in realized volatility (a proxy for the size of the hedging need)"),
    conditioning=("abs_rod_return", "realized_vol", "implied_vol_if_available",
                  "estimated_gamma_environment", "liquidity", "is_macro_event_day"),
    falsifiers=(
        "randomised 'close' times reproduce the effect -> it is not about the close",
        "effect vanishes at measured broker cost -> it is not tradeable here",
        "effect exists in only one symbol -> it is a fluke, not a mechanism",
        "DST/session misalignment destroys it -> the clock was fitted, not found",
        "effect is equally strong far from the institutional close -> no hedging story",
        "no relation between effect strength and volatility/gamma proxies -> mechanism absent",
    ),
    alternative_explanation="generic intraday momentum unrelated to hedging flow",
    distinguishing_test=("concentration of the effect in the final 30 minutes specifically, and "
                         "its scaling with volatility, neither of which generic momentum predicts"),
    data_requirements=("H1 or finer bars with correct session boundaries",
                       "broker-clock to UTC offset", "per-hour spread surface"),
    source="Journal of Financial Economics, 60+ futures across 4 asset classes, 1974-2020",
    secondary="1-3 day partial reversal after closing-flow pressure clears",
)

#: 2. TEMPORARY BENCHMARK-FLOW REVERSAL (FX fixings).
#: V-shaped moves around Tokyo and European fixes across G9. The mechanism is observable in the
#: microstructure work: predictable customer order imbalance creates price pressure, which
#: reverses once the temporary demand is gone.
FX_FIXING_REVERSAL = EdgeSpec(
    id="H-2026-0002-FX_FIXING_REVERSAL",
    claim=("Abnormal directional displacement in the window before a currency fix reverses after "
           "it, in proportion to the displacement."),
    payer=("benchmark-tracking funds and corporate hedgers who must transact AT the fix "
           "regardless of price, plus the dealers warehousing that imbalance"),
    constraint="execution must occur inside the fixing window; the participant cannot wait",
    coordinate=Coordinate("benchmark_flow", "london", "magnitude", "reversal", "15m"),
    universe=("USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
              "EURJPY", "EURGBP"),
    observables=("pre_fix_displacement", "post_fix_return", "pre_fix_volatility", "spread",
                 "prior_directional_persistence"),
    prediction="larger abnormal pre-fix displacement -> larger subsequent reversal",
    conditioning=("displacement_magnitude", "pre_fix_vol", "spread", "currency", "is_month_end",
                  "weekday", "macro_event_proximity", "which_fix"),
    falsifiers=(
        "randomised fix times give the same reversal -> not about the fix",
        "reversal is symmetric far from the window -> generic short-horizon reversal",
        "effect dies at measured spread -> untradeable on this venue",
        "no scaling with displacement -> no temporary-impact mechanism",
        "month-end conditioning removes rather than strengthens it -> flow story is wrong",
    ),
    alternative_explanation="generic short-horizon mean reversion at any time of day",
    distinguishing_test=("concentration around the true fix clock and amplification at month-end, "
                         "when benchmark flow is largest"),
    data_requirements=("intraday bars", "exact fix timestamps per venue in UTC",
                       "per-hour spread surface"),
    source="Journal of Finance (V-shaped reversals, G9, Tokyo and European fixes); Tokyo "
           "microstructure literature on customer order imbalance",
    notes=("test the MECHANISM SURFACE, not 'USDJPY reverses at 10am'. The conditioning axes "
           "give hundreds of controlled children of ONE causal parent -- which is NOT the same "
           "as hundreds of independent trials and must not be charged as such."),
)

#: 3. SESSION INFORMATION HANDOFF (gold).
#: After China introduced night trading, the first half hour of the NIGHT session replaced the
#: daytime first half hour as the informative predictor. The transferable claim is not the hour:
#: it is that the segment which first processes global information becomes the informative one.
GOLD_SESSION_HANDOFF = EdgeSpec(
    id="H-2026-0003-GOLD_SESSION_HANDOFF",
    claim=("The session segment that first processes global information predicts later-session "
           "returns; which segment that is changes when market hours change."),
    payer=("participants who cannot access the first-processing session and must transact later, "
           "paying for immediacy to whoever carried the position across the handoff"),
    constraint="a segment of the market is closed while information arrives",
    coordinate=Coordinate("session_transition", "asia", "cross_market_confirmation",
                          "continuation", "1h"),
    universe=("XAUUSD", "XAGUSD"),
    observables=("initial_15m_return", "initial_30m_return", "initial_60m_return",
                 "absolute_return", "realized_vol", "range_expansion"),
    prediction=("later-session continuation OR reversal CONDITIONAL on the information and "
                "liquidity state -- the direction is learned, never assumed"),
    conditioning=("preceding_comex_volatility", "preceding_abs_return", "news_surprise",
                  "cross_market_agreement", "liquidity_state"),
    falsifiers=(
        "no segment predicts better than any other -> no handoff",
        ("the predictive segment does not move when session hours change "
         "-> not a handoff, just momentum"),
        "no relation to preceding COMEX volatility -> the information story is absent",
        "effect dies at cost",
    ),
    alternative_explanation="simple overnight momentum in gold",
    distinguishing_test=("the predictive segment MOVES when trading hours change -- overnight "
                         "momentum makes no such prediction"),
    data_requirements=("intraday XAUUSD/XAGUSD bars", "session calendars including changes",
                       "COMEX reference series"),
    source="2025 study on Chinese gold and silver futures, momentum and reversal, with OOS "
           "analysis supporting the post-night-session change",
    notes="learn P(continuation|state) and P(reversal|state) separately; assuming momentum here "
          "would hide whichever regime is the smaller half",
)

#: 4. LIQUIDITY / GAMMA-CONDITIONED REVERSAL.
#: Intraday reversals linked to gamma exposure, vega hedging and liquidity state -- with HIGH
#: liquidity showing stronger reversal and low liquidity weaker trend. That conditional is the
#: whole content; unconditional "large move reverses" is a coin flip with a story attached.
LIQUIDITY_GAMMA_REVERSAL = EdgeSpec(
    id="H-2026-0004-LIQUIDITY_GAMMA_REVERSAL",
    claim=("Large displacement reverses when liquidity is ample and hedging flow is unwinding, "
           "and persists when liquidity is thin and hedging flow is accumulating."),
    payer=("liquidity providers compensated for absorbing a displacement, and hedgers forced to "
           "unwind once their exposure clears"),
    constraint="the provider must quote and the hedger must unwind, neither at a chosen price",
    coordinate=Coordinate("liquidity_shock", "high_liquidity", "failed_continuation",
                          "reversal", "15m"),
    universe=("XAUUSD", "XAGUSD", "USOIL", "UKOIL", "US500", "NAS100", "US30"),
    observables=("displacement", "spread", "realized_vol", "volume", "continuation_failure"),
    prediction=("P(reversal) increases with displacement AND liquidity; trend persistence "
                "increases as liquidity thins"),
    conditioning=("displacement_size", "liquidity_state", "volatility_state",
                  "derivative_hedging_state", "failure_to_continue"),
    falsifiers=(
        "reversal is unconditional on liquidity -> it is just mean reversion",
        "the liquidity relation has the OPPOSITE sign -> mechanism is misidentified",
        "effect dies at measured cost, which thin liquidity guarantees is larger",
        "no interaction with volatility state -> no hedging content",
    ),
    alternative_explanation="unconditional short-horizon mean reversion (RSI-style)",
    distinguishing_test=("the SIGN of the liquidity interaction -- unconditional reversal "
                         "predicts no interaction at all"),
    data_requirements=("intraday bars", "per-hour spread surface as the liquidity proxy",
                       "realized volatility"),
    source="Chinese commodity futures/options study, 1-minute data, gamma and vega hedging "
           "linked to intraday reversal",
)

QUEUE: tuple[EdgeSpec, ...] = (
    HEDGING_DEMAND_CLOSE_FLOW,
    FX_FIXING_REVERSAL,
    GOLD_SESSION_HANDOFF,
    LIQUIDITY_GAMMA_REVERSAL,
)


def validate_queue() -> list[tuple[str, str]]:
    """Every spec must be a complete preregistration before it may consume a trial."""
    out = []
    for spec in QUEUE:
        ok, why = spec.is_complete()
        if not ok:
            out.append((spec.id, why))
    return out


def as_records() -> list[dict[str, Any]]:
    """Queue as plain records for the docket, with the coordinate flattened."""
    rows = []
    for s in QUEUE:
        rows.append({
            "hypothesis_id": s.id, "claim": s.claim, "payer": s.payer,
            "constraint": s.constraint, "coordinate": s.coordinate.key(),
            "region": "|".join(s.coordinate.region), "universe": list(s.universe),
            "observables": list(s.observables), "prediction": s.prediction,
            "conditioning": list(s.conditioning), "falsifiers": list(s.falsifiers),
            "alternative_explanation": s.alternative_explanation,
            "distinguishing_test": s.distinguishing_test,
            "data_requirements": list(s.data_requirements), "source": s.source,
            "secondary": s.secondary, "notes": s.notes,
            "promotion_authority": False,
        })
    return rows
