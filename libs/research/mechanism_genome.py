"""THE ELEVEN-SLOT MECHANISM GENOME, and recombination at the level of the ECONOMICS. C5.

WHAT WAS THERE AND WHY IT WAS NOT THIS. `desks/mt5/research/alpha_genome.py` fingerprints the
certified canon STRUCTURALLY -- symbol, asset class, family, mechanism class, clock, factor
roles, feature ids -- and `alpha_evolution` recombines GRAMMAR: operators and parameters of an
expression. Both are real and neither says what the alpha claims about the world. C5's list is a
claim: an actor under a constraint, an observable that reveals it, a trigger, a catalyst, a
transmission channel, an entry, an exit, a holding period, a capacity, a decay risk. Crossing two
alphas at that level asks "does this actor's pressure, reached through that channel, admit this
trigger" -- a question a grammar crossover cannot pose and cannot answer.

THE COMPATIBILITY TABLE IS THE POINT, AND IT IS A FILTER ON NONSENSE, NOT A GATE ON RESEARCH.
`recombine` emits only children whose transmission admits their trigger and whose holding period
admits their exit; an incompatible pair produces NO CHILD rather than a child with a refusal
stamped on it, because the desk's trial budget is shared (LAWS: the deflated-Sharpe charge and
the program SPA divide one family-wise error budget) and spending a trial on a cell that cannot
be true raises the bar every other cell must clear. Nothing here refuses, caps or shrinks an
EXISTING alpha: it decides which NEW ones are worth minting, which is the opposite direction.

EVERY SLOT IS DECLARED, NEVER INFERRED. `from_family` reads a table written against the families
`mt5desk.families` registers. A family the table does not carry returns a genome whose slots are
UNDECLARED -- not guessed from its name, because the name is the one thing a mechanism claim must
not be derived from (an `overnight_drift` cell that turns out to trade the London fix would be
given the wrong actor forever).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

#: The eleven slots, in the order the principal's blueprint names them. The order is part of the
#: declaration: a reader comparing two genomes compares them slot by slot.
SLOTS: tuple[str, ...] = ("actor", "constraint", "observable", "trigger", "catalyst",
                          "transmission", "entry", "exit", "holding", "capacity", "decay_risk")

#: What an undeclared slot reads as. Never "" and never "unknown": UNDECLARED says the desk has
#: not written the claim down, which is different from having written that there is none.
UNDECLARED = "UNDECLARED"

#: WHICH TRIGGERS A TRANSMISSION CHANNEL ADMITS. A channel is how the actor's pressure reaches
#: the price; a trigger is what tells the desk the pressure is on. A `flow` channel cannot be
#: triggered by a `valuation_gap` -- flow is observed as it happens and valuation is observed as
#: a level -- and a `risk_premium` channel cannot be triggered by a `microstructure` event.
#: Declared here once, so two organs cannot disagree about what is coherent.
TRANSMISSION_TRIGGERS: dict[str, frozenset[str]] = {
    # Flow is observed AS IT HAPPENS: a clock, a scheduled event, a volume print, the book.
    # `volatility_state` belongs here because a VOL-TARGETING MANDATE turns a change in
    # realised vol into forced flow -- that is the whole mechanism `momentum_volgate` claims.
    "flow": frozenset({"time_of_day", "calendar_event", "volume_shock", "microstructure",
                       "price_pattern", "volatility_state"}),
    # A risk premium is EARNED OVER A WINDOW, so a clock triggers it as legitimately as a vol
    # state does. The first table omitted `time_of_day` and declared `overnight_drift` -- the
    # canonical earn-it-overnight premium -- incoherent, which is how a table meant to catch
    # nonsense catches the desk's own live sleeves instead.
    "risk_premium": frozenset({"volatility_state", "carry_level", "calendar_event",
                               "positioning", "time_of_day"}),
    # Information arrives on a release, in the news, in positioning, or as a volatility shock.
    "information": frozenset({"calendar_event", "surprise", "news", "positioning",
                              "volatility_state"}),
    # Inventory pressure is revealed by price EXTENSION as much as by volume: that is what a
    # liquidity provider's mean reversion claims, and the first table refused it.
    "inventory": frozenset({"volume_shock", "microstructure", "time_of_day", "positioning",
                            "price_pattern", "price_level", "volatility_state"}),
    "valuation": frozenset({"valuation_gap", "carry_level", "volatility_state", "price_level"}),
    "behavioural": frozenset({"price_pattern", "time_of_day", "volatility_state",
                              "price_level", "positioning"}),
    UNDECLARED: frozenset(),
}

#: WHICH EXITS A HOLDING PERIOD ADMITS. An `intraday` alpha cannot exit on a `weekly_rebalance`
#: and a `multiweek` one cannot exit on a `session_close` without becoming a different alpha.
HOLDING_EXITS: dict[str, frozenset[str]] = {
    "intraday": frozenset({"session_close", "time_stop", "target", "stop", "signal_flip"}),
    "overnight": frozenset({"next_open", "time_stop", "target", "stop"}),
    "multiday": frozenset({"time_stop", "target", "stop", "signal_flip"}),
    "multiweek": frozenset({"time_stop", "signal_flip", "weekly_rebalance", "stop"}),
    UNDECLARED: frozenset(),
}

#: THE DECLARED GENOME OF EVERY FAMILY THIS DESK REGISTERS. Written against
#: `mt5desk.families.FAMILY_REGISTRY`; a family absent here is UNDECLARED in every slot and is
#: reported as such by `census`, which is how the table is kept honest as families are added.
FAMILY_GENOME: dict[str, dict[str, str]] = {
    "session_range_breakout": {
        "actor": "session_participants", "constraint": "session_open_inventory",
        "observable": "prior_session_range", "trigger": "time_of_day",
        "catalyst": "session_open", "transmission": "flow", "entry": "stop_through_level",
        "exit": "session_close", "holding": "intraday", "capacity": "spread_bound",
        "decay_risk": "crowding"},
    "level_breakout": {
        "actor": "stop_holders", "constraint": "protective_stop_placement",
        "observable": "swing_level", "trigger": "price_level", "catalyst": "level_touch",
        "transmission": "inventory", "entry": "stop_through_level", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "crowding"},
    "failed_breakout": {
        "actor": "breakout_chasers", "constraint": "late_entry_stops",
        "observable": "range_edge_rejection", "trigger": "price_pattern",
        "catalyst": "failed_extension", "transmission": "behavioural",
        "entry": "limit_on_reversal", "exit": "target", "holding": "intraday",
        "capacity": "spread_bound", "decay_risk": "crowding"},
    "asia_momentum": {
        "actor": "asian_session_flow", "constraint": "thin_book",
        "observable": "asia_session_return", "trigger": "time_of_day",
        "catalyst": "tokyo_open", "transmission": "flow", "entry": "market_on_signal",
        "exit": "session_close", "holding": "intraday", "capacity": "depth_bound",
        "decay_risk": "liquidity_regime"},
    "overnight_drift": {
        "actor": "overnight_risk_holders", "constraint": "overnight_risk_limits",
        "observable": "close_to_open_gap", "trigger": "time_of_day", "catalyst": "session_close",
        "transmission": "risk_premium", "entry": "market_on_close", "exit": "next_open",
        "holding": "overnight", "capacity": "swap_bound", "decay_risk": "financing_change"},
    "monday_gap": {
        "actor": "weekend_risk_holders", "constraint": "weekend_gap_risk",
        "observable": "friday_close_to_monday_open", "trigger": "calendar_event",
        "catalyst": "weekend", "transmission": "risk_premium", "entry": "market_on_open",
        "exit": "time_stop", "holding": "overnight", "capacity": "swap_bound",
        "decay_risk": "financing_change"},
    "dow_effect": {
        "actor": "calendar_rebalancers", "constraint": "mandate_calendar",
        "observable": "day_of_week_return", "trigger": "calendar_event",
        "catalyst": "weekday", "transmission": "flow", "entry": "market_on_open",
        "exit": "time_stop", "holding": "intraday", "capacity": "depth_bound",
        "decay_risk": "crowding"},
    "comex_settlement": {
        "actor": "futures_settlement_desks", "constraint": "settlement_window",
        "observable": "settlement_window_drift", "trigger": "time_of_day",
        "catalyst": "comex_settlement", "transmission": "flow", "entry": "limit_in_window",
        "exit": "session_close", "holding": "intraday", "capacity": "depth_bound",
        "decay_risk": "venue_rule_change"},
    "usd_session_shock": {
        "actor": "macro_traders", "constraint": "dollar_funding",
        "observable": "usd_index_move", "trigger": "volatility_state",
        "catalyst": "us_session_open", "transmission": "information",
        "entry": "market_on_signal", "exit": "time_stop", "holding": "intraday",
        "capacity": "depth_bound", "decay_risk": "regime_shift"},
    "london_close_momentum": {
        "actor": "fix_participants", "constraint": "benchmark_fix_obligation",
        "observable": "pre_fix_drift", "trigger": "time_of_day", "catalyst": "london_fix",
        "transmission": "flow", "entry": "market_on_signal", "exit": "session_close",
        "holding": "intraday", "capacity": "depth_bound", "decay_risk": "venue_rule_change"},
    "momentum_volgate": {
        "actor": "trend_followers", "constraint": "vol_targeting_mandate",
        "observable": "trend_with_vol_state", "trigger": "volatility_state",
        "catalyst": "vol_regime_change", "transmission": "flow", "entry": "market_on_signal",
        "exit": "signal_flip", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "regime_shift"},
    "trend_ma_cross": {
        "actor": "trend_followers", "constraint": "vol_targeting_mandate",
        "observable": "moving_average_relation", "trigger": "price_pattern",
        "catalyst": "trend_onset", "transmission": "behavioural", "entry": "market_on_signal",
        "exit": "signal_flip", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "crowding"},
    "mean_reversion_rsi": {
        "actor": "liquidity_providers", "constraint": "inventory_limits",
        "observable": "oscillator_extreme", "trigger": "price_pattern",
        "catalyst": "overextension", "transmission": "inventory", "entry": "limit_on_reversal",
        "exit": "target", "holding": "intraday", "capacity": "spread_bound",
        "decay_risk": "crowding"},
    "mean_reversion_bollinger": {
        "actor": "liquidity_providers", "constraint": "inventory_limits",
        "observable": "band_excursion", "trigger": "price_pattern", "catalyst": "overextension",
        "transmission": "inventory", "entry": "limit_on_reversal", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "crowding"},
    "range_reversion": {
        "actor": "liquidity_providers", "constraint": "inventory_limits",
        "observable": "range_position", "trigger": "price_level", "catalyst": "range_edge",
        "transmission": "inventory", "entry": "limit_on_reversal", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "regime_shift"},
    "volatility_squeeze": {
        "actor": "option_hedgers", "constraint": "gamma_hedging",
        "observable": "realised_vol_compression", "trigger": "volatility_state",
        "catalyst": "vol_expansion", "transmission": "inventory", "entry": "stop_through_level",
        "exit": "target", "holding": "intraday", "capacity": "depth_bound",
        "decay_risk": "regime_shift"},
    "volume_spike": {
        "actor": "informed_flow", "constraint": "execution_urgency",
        "observable": "volume_zscore", "trigger": "volume_shock", "catalyst": "block_trade",
        "transmission": "inventory", "entry": "market_on_signal", "exit": "time_stop",
        "holding": "intraday", "capacity": "depth_bound", "decay_risk": "liquidity_regime"},
    "cot_net_fade": {
        "actor": "speculators", "constraint": "position_limits",
        "observable": "cot_net_position", "trigger": "positioning", "catalyst": "cot_release",
        "transmission": "risk_premium", "entry": "market_on_signal", "exit": "signal_flip",
        "holding": "multiweek", "capacity": "depth_bound", "decay_risk": "reporting_change"},
    "cot_change_fade": {
        "actor": "speculators", "constraint": "position_limits",
        "observable": "cot_net_change", "trigger": "positioning", "catalyst": "cot_release",
        "transmission": "risk_premium", "entry": "market_on_signal", "exit": "signal_flip",
        "holding": "multiweek", "capacity": "depth_bound", "decay_risk": "reporting_change"},
    "cot_change_momentum": {
        "actor": "speculators", "constraint": "position_limits",
        "observable": "cot_net_change", "trigger": "positioning", "catalyst": "cot_release",
        "transmission": "information", "entry": "market_on_signal", "exit": "signal_flip",
        "holding": "multiweek", "capacity": "depth_bound", "decay_risk": "reporting_change"},
    "cot_comm_follow": {
        "actor": "commercial_hedgers", "constraint": "hedging_mandate",
        "observable": "commercial_net_position", "trigger": "positioning",
        "catalyst": "cot_release", "transmission": "information", "entry": "market_on_signal",
        "exit": "signal_flip", "holding": "multiweek", "capacity": "depth_bound",
        "decay_risk": "reporting_change"},
    "pullback_entry": {
        "actor": "trend_followers", "constraint": "entry_discipline",
        "observable": "retracement_depth", "trigger": "price_pattern", "catalyst": "pullback",
        "transmission": "behavioural", "entry": "limit_on_reversal", "exit": "target",
        "holding": "multiday", "capacity": "depth_bound", "decay_risk": "crowding"},
    "pin_bar_reversal": {
        "actor": "stop_holders", "constraint": "protective_stop_placement",
        "observable": "rejection_candle", "trigger": "price_pattern", "catalyst": "level_touch",
        "transmission": "behavioural", "entry": "stop_through_level", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "crowding"},
    "engulfing_reversal": {
        "actor": "stop_holders", "constraint": "protective_stop_placement",
        "observable": "engulfing_candle", "trigger": "price_pattern", "catalyst": "reversal_bar",
        "transmission": "behavioural", "entry": "market_on_signal", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "crowding"},
    "ict_fvg": {
        "actor": "algorithmic_retail", "constraint": "published_playbook",
        "observable": "fair_value_gap", "trigger": "price_pattern", "catalyst": "imbalance",
        "transmission": "behavioural", "entry": "limit_on_reversal", "exit": "target",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "crowding"},
    "retail_overlap_reversal": {
        "actor": "retail_traders", "constraint": "leverage_limits",
        "observable": "retail_positioning_overlap", "trigger": "positioning",
        "catalyst": "session_overlap", "transmission": "behavioural",
        "entry": "limit_on_reversal", "exit": "time_stop", "holding": "intraday",
        "capacity": "spread_bound", "decay_risk": "broker_mix_change"},
    "adx_channel_hybrid": {
        "actor": "trend_followers", "constraint": "vol_targeting_mandate",
        "observable": "trend_strength_with_channel", "trigger": "price_pattern",
        "catalyst": "channel_break", "transmission": "behavioural",
        "entry": "stop_through_level", "exit": "signal_flip", "holding": "multiday",
        "capacity": "depth_bound", "decay_risk": "regime_shift"},
    # ------------------------------------------------------------------ THE CERTIFIED CANON
    # `mt5desk.families.FAMILY_REGISTRY` is the GRID's vocabulary; the certified canon uses a
    # wider one (alpha_genome.MECHANISM_CLASS), and a table covering only the grid left the
    # canon with two declared families and therefore no cross to make. These are the families
    # the desk has actually certified or hunts as mechanisms.
    "overnight_gap_decay": {
        "actor": "overnight_risk_holders", "constraint": "overnight_risk_limits",
        "observable": "opening_gap", "trigger": "time_of_day", "catalyst": "session_open",
        "transmission": "inventory", "entry": "market_on_open", "exit": "session_close",
        "holding": "intraday", "capacity": "spread_bound", "decay_risk": "liquidity_regime"},
    "carry": {
        "actor": "leveraged_carry_holders", "constraint": "funding_cost",
        "observable": "interest_rate_differential", "trigger": "carry_level",
        "catalyst": "rate_decision", "transmission": "risk_premium",
        "entry": "market_on_signal", "exit": "signal_flip", "holding": "multiweek",
        "capacity": "swap_bound", "decay_risk": "financing_change"},
    "cross_asset_residual": {
        "actor": "cross_asset_arbitrageurs", "constraint": "balance_sheet",
        "observable": "residual_after_factors", "trigger": "valuation_gap",
        "catalyst": "dislocation", "transmission": "valuation", "entry": "limit_on_reversal",
        "exit": "target", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "factor_change"},
    "relative_value": {
        "actor": "relative_value_desks", "constraint": "balance_sheet",
        "observable": "pair_spread", "trigger": "valuation_gap", "catalyst": "spread_widening",
        "transmission": "valuation", "entry": "limit_on_reversal", "exit": "target",
        "holding": "multiday", "capacity": "depth_bound", "decay_risk": "factor_change"},
    "pca_residual": {
        "actor": "factor_investors", "constraint": "factor_mandate",
        "observable": "principal_component_residual", "trigger": "valuation_gap",
        "catalyst": "dislocation", "transmission": "valuation", "entry": "limit_on_reversal",
        "exit": "target", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "factor_change"},
    "clock_transition": {
        "actor": "session_handover_desks", "constraint": "book_handover",
        "observable": "session_boundary_behaviour", "trigger": "time_of_day",
        "catalyst": "session_handover", "transmission": "flow", "entry": "market_on_signal",
        "exit": "time_stop", "holding": "intraday", "capacity": "spread_bound",
        "decay_risk": "venue_rule_change"},
    "cot_positioning": {
        "actor": "speculators", "constraint": "position_limits",
        "observable": "cot_net_position", "trigger": "positioning", "catalyst": "cot_release",
        "transmission": "risk_premium", "entry": "market_on_signal", "exit": "signal_flip",
        "holding": "multiweek", "capacity": "depth_bound", "decay_risk": "reporting_change"},
    "event_reaction": {
        "actor": "macro_traders", "constraint": "information_processing_speed",
        "observable": "release_surprise", "trigger": "surprise", "catalyst": "macro_release",
        "transmission": "information", "entry": "market_on_signal", "exit": "time_stop",
        "holding": "intraday", "capacity": "depth_bound", "decay_risk": "regime_shift"},
    "vol_mean_reversion": {
        "actor": "option_hedgers", "constraint": "gamma_hedging",
        "observable": "realised_vol_level", "trigger": "volatility_state",
        "catalyst": "vol_spike", "transmission": "inventory", "entry": "limit_on_reversal",
        "exit": "target", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "regime_shift"},
    "vol_transition": {
        "actor": "vol_targeters", "constraint": "vol_targeting_mandate",
        "observable": "vol_regime_state", "trigger": "volatility_state",
        "catalyst": "vol_regime_change", "transmission": "flow", "entry": "market_on_signal",
        "exit": "signal_flip", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "regime_shift"},
    "orderflow_imbalance": {
        "actor": "informed_flow", "constraint": "execution_urgency",
        "observable": "signed_order_flow", "trigger": "microstructure",
        "catalyst": "imbalance", "transmission": "inventory", "entry": "market_on_signal",
        "exit": "time_stop", "holding": "intraday", "capacity": "depth_bound",
        "decay_risk": "liquidity_regime"},
    "turn_of_month": {
        "actor": "calendar_rebalancers", "constraint": "mandate_calendar",
        "observable": "month_end_flow_window", "trigger": "calendar_event",
        "catalyst": "month_end", "transmission": "flow", "entry": "market_on_signal",
        "exit": "time_stop", "holding": "multiday", "capacity": "depth_bound",
        "decay_risk": "crowding"},
    "joint_genome": {
        "actor": "composite", "constraint": "composite", "observable": "composite",
        "trigger": "price_pattern", "catalyst": "composite", "transmission": "behavioural",
        "entry": "market_on_signal", "exit": "signal_flip", "holding": "multiday",
        "capacity": "depth_bound", "decay_risk": "composite"},
}


@dataclass(frozen=True)
class Genome:
    """One alpha's economic claim, eleven slots wide. Every field defaults to UNDECLARED."""

    actor: str = UNDECLARED
    constraint: str = UNDECLARED
    observable: str = UNDECLARED
    trigger: str = UNDECLARED
    catalyst: str = UNDECLARED
    transmission: str = UNDECLARED
    entry: str = UNDECLARED
    exit: str = UNDECLARED
    holding: str = UNDECLARED
    capacity: str = UNDECLARED
    decay_risk: str = UNDECLARED
    family: str = ""
    declared: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def n_declared(self) -> int:
        return sum(1 for s in SLOTS if getattr(self, s) != UNDECLARED)


def from_family(family: str, params: Mapping[str, Any] | None = None) -> Genome:
    """The declared genome of `family`, or an all-UNDECLARED one carrying the family name.

    `params` is accepted and deliberately unused for the slot VALUES: a parameter changes how
    hard a trigger is pulled, never which actor is being traded against, and letting numbers edit
    the economic claim is how a genome silently becomes a second copy of the parameter grid.
    """
    row = FAMILY_GENOME.get(str(family))
    if not row:
        return Genome(family=str(family), declared=False)
    return Genome(family=str(family), declared=True,
                  **{s: row.get(s, UNDECLARED) for s in SLOTS})


def compatible(g: Genome) -> tuple[bool, str]:
    """Whether this genome's slots can all be true at once, and the first reason they cannot.

    Two checks, both declared above: the transmission must admit the trigger, and the holding
    period must admit the exit. A genome with an UNDECLARED transmission or holding is NOT
    incompatible -- it is unjudged, and saying otherwise would turn a missing table row into a
    verdict about an alpha (L1.28a).
    """
    if g.transmission != UNDECLARED and g.trigger != UNDECLARED:
        allowed = TRANSMISSION_TRIGGERS.get(g.transmission)
        if allowed is not None and g.trigger not in allowed:
            return False, (f"transmission {g.transmission!r} does not admit trigger "
                           f"{g.trigger!r}")
    if g.holding != UNDECLARED and g.exit != UNDECLARED:
        allowed = HOLDING_EXITS.get(g.holding)
        if allowed is not None and g.exit not in allowed:
            return False, f"holding {g.holding!r} does not admit exit {g.exit!r}"
    if g.transmission != UNDECLARED and g.transmission not in TRANSMISSION_TRIGGERS:
        return True, f"transmission {g.transmission!r} is not in the declared table: UNJUDGED"
    return True, ""


def recombine(a: Genome, b: Genome, *, slots: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Every single-slot cross of `a` and `b` that is internally coherent.

    ONE SLOT AT A TIME, ON PURPOSE. A child differing from its parent in one slot is a
    HYPOTHESIS ABOUT THAT SLOT -- "this actor's pressure reaches price through the other
    channel" -- and its result is attributable. A child differing in six is a new alpha wearing a
    lineage, and no verdict on it says which change mattered.

    Returns rows, not Genomes, so a caller can donate them without importing this module's types:
    each carries the child's slots, the parent families, the slot crossed and the value taken.
    """
    if not (a.declared and b.declared):
        return []
    out: list[dict[str, Any]] = []
    for slot in (slots or SLOTS):
        av, bv = getattr(a, slot, UNDECLARED), getattr(b, slot, UNDECLARED)
        if av == bv or UNDECLARED in (av, bv):
            continue
        vals: dict[str, str] = {s: str(getattr(a, s, UNDECLARED)) for s in SLOTS}
        vals[slot] = str(bv)
        child = Genome(family=f"{a.family}+{b.family}", declared=True, **vals)
        ok, why = compatible(child)
        if not ok:
            continue
        out.append({"slot": slot, "from_family": a.family, "to_family": b.family,
                    "took": bv, "replaced": av, "genome": child.as_dict(),
                    "coherence": why or "coherent under the declared tables"})
    return out


def census(families: Iterable[str]) -> dict[str, Any]:
    """Which registered families carry a declared genome and which do not. Nothing is refused."""
    names = sorted({str(f) for f in families})
    declared = [f for f in names if f in FAMILY_GENOME]
    missing = [f for f in names if f not in FAMILY_GENOME]
    incoherent = []
    for f in declared:
        ok, why = compatible(from_family(f))
        if not ok:
            incoherent.append({"family": f, "why": why})
    return {"n_families": len(names), "n_declared": len(declared), "n_undeclared": len(missing),
            "undeclared": missing, "incoherent": incoherent,
            "slots": list(SLOTS),
            "rule": ("every slot is DECLARED against mt5desk.families, never inferred from a "
                     "family's name; an undeclared family is UNDECLARED in all eleven slots")}
