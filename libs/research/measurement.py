"""Does the experiment measure the thing the hypothesis names? Four answers, and one is fatal.

WHY THIS EXISTS (external audit of desk-sync-clean, 2026-08-29 -- and the audit is right)

    "Make absolutely sure that when AI says it has a hypothesis about phenomenon X, the
     experiment genuinely measures X."

Verified against this desk's own `family_generic` the moment the claim was made:

    macro_release       ->  d["close"].diff()
    options_hedging     ->  d["close"].diff()          IDENTICAL
    session_transition  ->  d["close"] - d["open"]
    benchmark_flow      ->  d["close"] - d["open"]     IDENTICAL

Four named mechanisms, two actual tests. A "dealer gamma hedging" result and a "macro surprise"
result were the same computation wearing different labels, and nothing in the desk could tell.

WHY THIS IS WORSE THAN A NORMAL BUG. It has two failure modes and both poison the learning loop:

  FALSE NEGATIVE   the mechanism is real, the proxy cannot see it, the test fails, and the desk
                   writes the mechanism into the graveyard. A good research direction is killed
                   without ever being tested.
  FALSE POSITIVE   the proxy happens to work. The desk records "options hedging survived" when
                   what survived was a one-bar momentum rule. That label then flows into
                   genealogy, mechanism fertility, allocator priors, breeding rights and
                   second-order generation -- every one of which now believes something false.

A backtest bug costs a wrong number. This costs a wrong BELIEF, and the desk compounds beliefs.

THE FOUR CLASSES, and the boundary that matters is between the second and third:

    DIRECT            the variable the mechanism names is the variable measured.
    VALIDATED_PROXY   not the variable itself, but there is a defensible argument that it moves
                      with it, recorded here in words a reader can dispute.
    HEURISTIC_PROXY   a loose approximation. May EXPLORE; may never certify the mechanism.
    UNMEASURABLE      the observable does not exist on this desk. Running it anyway does not
                      test the mechanism -- it tests something else under the mechanism's name.

ENFORCEMENT IS THE POINT. `attribution_allowed` is False below VALIDATED_PROXY, so a heuristic
cell's result may not update any belief about the mechanism it is named after. The cell still
runs -- exploration is cheap and sometimes finds something -- but it reports under its own
coordinate, not as evidence about a mechanism it cannot see.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Ordered weakest to strongest. Comparisons use the index, so inserting a class changes policy
#: everywhere at once -- which is correct, because this ordering IS the policy.
CLASSES = ("UNMEASURABLE", "HEURISTIC_PROXY", "VALIDATED_PROXY", "DIRECT")

#: Below this class, a result may not be attributed to the mechanism it is named after.
MIN_ATTRIBUTABLE = "VALIDATED_PROXY"


@dataclass(frozen=True)
class MeasurementContract:
    """What a hypothesis claims to measure, versus what the implementation actually measures."""

    mechanism: str
    required_observable: str
    actual_observable: str
    measurement_class: str
    justification: str
    data_source: str = "H1 bars"
    available_at_decision_time: bool = True

    def __post_init__(self) -> None:
        if self.measurement_class not in CLASSES:
            raise ValueError(f"measurement_class must be one of {CLASSES}")

    @property
    def attribution_allowed(self) -> bool:
        """May a result from this implementation update beliefs about `mechanism`?"""
        return (CLASSES.index(self.measurement_class)
                >= CLASSES.index(MIN_ATTRIBUTABLE))

    @property
    def may_run(self) -> bool:
        """UNMEASURABLE does not run. Everything else may, under its own label."""
        return self.measurement_class != "UNMEASURABLE"

    def verdict(self) -> str:
        if not self.may_run:
            return (f"UNMEASURABLE: {self.mechanism} requires {self.required_observable}, which "
                    f"this desk does not have. Running {self.actual_observable} instead would "
                    f"test something else under this mechanism's name.")
        if not self.attribution_allowed:
            return (f"EXPLORATION ONLY: {self.actual_observable} is a heuristic stand-in for "
                    f"{self.required_observable}. The cell may run; its result may NOT be read "
                    f"as evidence about {self.mechanism}.")
        return (f"ATTRIBUTABLE ({self.measurement_class}): {self.actual_observable} measures "
                f"{self.required_observable}. {self.justification}")


#: EVERY `family_generic` event, classified honestly. This table is the audit's finding written
#: down, and most of it is uncomfortable -- which is the sign it was done properly rather than to
#: flatter the code.
GENERIC_CONTRACTS: dict[str, MeasurementContract] = {
    "session_transition": MeasurementContract(
        mechanism="session_transition",
        required_observable="displacement within a named session window",
        actual_observable="close - open, masked to the session's broker hours",
        measurement_class="DIRECT",
        justification=("the session clock comes from the bar index and the displacement IS the "
                       "quantity the claim is about; nothing is standing in for anything")),
    "volatility_shock": MeasurementContract(
        mechanism="volatility_shock",
        required_observable="realised volatility relative to its own recent level",
        actual_observable="bar range minus its 20-bar mean",
        measurement_class="DIRECT",
        justification="range IS a realised-volatility measure at bar resolution"),
    "liquidity_shock": MeasurementContract(
        mechanism="liquidity_shock",
        required_observable="spread, depth, or order-book thinness",
        actual_observable="bar range relative to its median",
        measurement_class="HEURISTIC_PROXY",
        justification=("range widens in thin markets AND in fast markets; it cannot separate "
                       "them, so a result here does not identify liquidity as the cause")),
    "inventory_rebalance": MeasurementContract(
        mechanism="inventory_rebalance",
        required_observable="dealer inventory or a flow imbalance",
        actual_observable="distance from a 20-bar mean",
        measurement_class="HEURISTIC_PROXY",
        justification="distance from a mean is consistent with inventory pressure and with "
                      "twenty other things; it identifies none of them"),
    "forced_deleveraging": MeasurementContract(
        mechanism="forced_deleveraging",
        required_observable="margin utilisation, liquidation prints, or a stop cascade",
        actual_observable="bar return scaled by ATR",
        measurement_class="HEURISTIC_PROXY",
        justification="a large ATR-scaled move is what forced selling LOOKS like and also what "
                      "ordinary news looks like"),
    "positioning_extreme": MeasurementContract(
        mechanism="positioning_extreme",
        required_observable="COT/TFF net positioning versus its own history",
        actual_observable=("net non-commercial positioning / open interest, z-scored over 52 "
                           "weeks, lagged 4 days to publication (CotPositioningAdapter)"),
        measurement_class="VALIDATED_PROXY",
        data_source="desks/mt5/data/cot/*.parquet",
        justification=("UNBLOCKED 2026-08-29: the desk always had COT parquets and the generic "
                       "family used price extension instead. The adapter reads the real series "
                       "and lags it to publication so no bar sees a report before it was public. "
                       "VALIDATED_PROXY rather than DIRECT because the release is weekly while "
                       "the claim is intraday -- the level is real, its resolution is coarse.")),
    "cross_market_move": MeasurementContract(
        mechanism="cross_market_move",
        required_observable="a SECOND instrument's move leading this one",
        actual_observable="a named peer's return, lagged >=1 bar (CrossAssetAdapter)",
        measurement_class="DIRECT",
        data_source="desks/mt5/data/universe/<peer>_H1.parquet",
        justification=("UNBLOCKED 2026-08-29: 251 instruments were on disk while the generic "
                       "family looked at one instrument's own return. The adapter takes a real "
                       "peer, lags it strictly (lag>=1 is asserted, not assumed), and picks an "
                       "unnamed peer by shared currency -- NEVER by correlation, which would "
                       "select on the outcome being tested.")),
    "macro_release": MeasurementContract(
        mechanism="macro_release",
        required_observable="a scheduled announcement's surprise versus consensus",
        actual_observable="previous-bar return",
        measurement_class="UNMEASURABLE",
        justification=("no event calendar is attached, so the cell fires on every bar and tests "
                       "one-bar momentum. Identical implementation to options_hedging.")),
    "options_hedging": MeasurementContract(
        mechanism="options_hedging",
        required_observable="dealer gamma, open interest, or implied volatility",
        actual_observable="previous-bar return",
        measurement_class="UNMEASURABLE",
        justification=("this desk has no options data. The implementation is byte-identical to "
                       "macro_release, so a 'gamma hedging' survivor and a 'macro surprise' "
                       "survivor would be the same test wearing two labels.")),
    "carry_change": MeasurementContract(
        mechanism="carry_change",
        required_observable="the swap/rate differential actually paid",
        actual_observable=("swap_money_per_lot_night, long minus short, from recorded contract "
                           "terms (CarryAdapter)"),
        measurement_class="VALIDATED_PROXY",
        data_source="desks/mt5/data/carry_state.json",
        justification=("UNBLOCKED 2026-08-29: 388KB of real financing sat unused while the "
                       "generic family used a 24-bar price return. VALIDATED_PROXY not DIRECT "
                       "because carry_state is a SNAPSHOT -- it gives today's level, not its "
                       "history, so a cell measures cross-sectional carry rather than carry "
                       "CHANGE. Recording a time series is what would make this DIRECT.")),
    "benchmark_flow": MeasurementContract(
        mechanism="benchmark_flow",
        required_observable="a fixing or rebalance window with its own timestamp",
        actual_observable="close - open",
        measurement_class="UNMEASURABLE",
        justification=("without the fixing calendar the cell fires on every bar in the context "
                       "window. Identical implementation to session_transition.")),
}


#: The four HAND-WRITTEN edge-queue families, held to the same standard. Exempting them because
#: a human wrote them would be exactly the bias this module exists to remove -- the question is
#: what the code measures, not who typed it.
#:
#: They score better than the generic proxies because each conditions on the thing its claim
#: names -- a session clock, a fix window, a liquidity state -- rather than on a bare price
#: difference. None reaches DIRECT, because the observable each mechanism truly requires (dealer
#: gamma, the venue's own fixing timestamp) is data this desk does not have.
EDGE_QUEUE_CONTRACTS: dict[str, MeasurementContract] = {
    "hedging_demand_close": MeasurementContract(
        mechanism="options_hedging",
        required_observable="dealer gamma exposure into the close",
        actual_observable=("rest-of-day displacement, fired only in the closing hour, gated on "
                           "elevated realised volatility"),
        measurement_class="HEURISTIC_PROXY",
        justification=("realised vol is an acknowledged stand-in for the gamma environment and "
                       "is named as one in the parameter. The CLOCK is real -- the cell fires "
                       "only at the close -- so it tests a closing-hour effect honestly; it does "
                       "not establish that dealer hedging causes it")),
    "fx_fixing_reversal": MeasurementContract(
        mechanism="benchmark_flow",
        required_observable="the venue's actual fixing window timestamp",
        actual_observable="a fixed broker hour believed to contain the fix, with pre/post windows",
        measurement_class="HEURISTIC_PROXY",
        justification=("a hardcoded hour is close to the fix but is not the fix; the "
                       "randomised-clock falsifier in the preregistration is what would "
                       "distinguish them, and it has not been run")),
    "session_handoff": MeasurementContract(
        mechanism="session_transition",
        required_observable="the first segment of a named session, and the later session's return",
        actual_observable="exactly that, from the bar index",
        measurement_class="DIRECT",
        justification=("both quantities are observable in H1 bars and the session boundaries "
                       "come from the index; nothing stands in for anything")),
    "liquidity_gamma_reversal": MeasurementContract(
        mechanism="liquidity_shock",
        required_observable="spread or depth, plus dealer hedging state",
        actual_observable="bar range versus its median, plus a failed-continuation condition",
        measurement_class="HEURISTIC_PROXY",
        justification=("range is a weak liquidity measure and there is no hedging observable at "
                       "all; the conditional structure is right and the inputs are approximate")),
}


def contract_for(event: str) -> MeasurementContract | None:
    """Contract for a generic event OR a hand-written family. One lookup, one standard."""
    return GENERIC_CONTRACTS.get(event) or EDGE_QUEUE_CONTRACTS.get(event)


def audit() -> dict[str, Any]:
    """Every generic event, by class. The uncomfortable summary is the useful one."""
    by_class: dict[str, list[str]] = {c: [] for c in CLASSES}
    for name, c in GENERIC_CONTRACTS.items():
        by_class[c.measurement_class].append(name)
    runnable = [n for n, c in GENERIC_CONTRACTS.items() if c.may_run]
    attributable = [n for n, c in GENERIC_CONTRACTS.items() if c.attribution_allowed]
    return {
        "events": len(GENERIC_CONTRACTS),
        "by_class": by_class,
        "runnable": sorted(runnable),
        "attributable": sorted(attributable),
        "blocked": sorted(n for n, c in GENERIC_CONTRACTS.items() if not c.may_run),
        "note": ("an UNMEASURABLE event is removed from the search, not downgraded: running it "
                 "produces a result labelled with a mechanism it cannot see, and that label "
                 "then poisons genealogy, fertility and allocator priors"),
    }
