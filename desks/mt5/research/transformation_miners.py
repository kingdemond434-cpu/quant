"""TWELVE MINERS, TWELVE DIMENSIONS, AND NOT ONE OF THEM MAY VETO ANOTHER.

THE DEFECT THIS ENDS. A single "expander" that walks one discovery and decides which variants are
worth building is a bottleneck wearing a helpful costume: whichever dimension it reasons about
first crowds out the rest, and the dimensions it never reaches are invisible from the output
because what is missing was never named. Measured on this desk over and over: a discovery about
XAUUSD in the asia session becomes three XAUUSD cells, and the same mechanism on silver, on the
adjacent hour, residualised against the dollar, one frequency slower and with the sign reversed is
NEVER ASKED. Those are the cells with the highest information gain, because they are the ones
nobody else bothered to test either.

So there are twelve miners and each receives the SAME parent independently. A weak miner returns
[] and costs the other eleven nothing: no ordering, no scoring between miners, no budget one
spends out of another's share. The compiler runs all twelve and lets the THREE GATES downstream
do the refusing, with a named reason per refusal.

WHAT A MINER IS. `mine_<name>(parent: dict, ctx: Context) -> list[dict]` -- reads, returns, writes
nothing, judges nothing, tests nothing. When one declines it records WHY on `ctx.notes` and
returns []: a silent empty list is what the principal's rule of 2026-09-17 forbids, and an empty
list with a reason is a disposition.

ECONOMIC COMPATIBILITY, WHICH IS NOT A CARTESIAN PRODUCT. Every mechanism carries a CONTRACT: the
charts, sessions, regimes, asset classes and horizon buckets over which its economics could still
be acting. A session-handover mechanism does not get D1 because a bar longer than the session
window cannot express a rule conditioned on it -- DERIVED from the window, not from a list
somebody maintains. A month-end flow mechanism gets the crosses whose legs carry the rebalancing
flow, not a random exotic. The pruned part is not a random sample of the product: it is
specifically the part with no economic story, which is where false positives come from fastest
(`libs/research/mechanism_ontology.py` states the same law, and the contracts register into it so
one module owns the horizon prune).

NEVER AN EQUITY. The two-lane mandate (principal 2026-09-06) is enforced at the instrument source:
`Context.instruments` comes from `axis_registry.instruments_by_class`, already filtered by
`universe_policy.may_hypothesise`, and every miner that moves the symbol axis re-checks. Trial
count is a shared cost; one single-name equity cell raises the bar every FX and metals cell then
has to clear.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CHART_LADDER",
    "CONTRACTS",
    "MINERS",
    "REGIME_LADDER",
    "SESSION_LADDER",
    "Context",
    "Contract",
    "chart_admits_session",
    "compatible",
    "mine_asset_transfer",
    "mine_cross_asset",
    "mine_execution",
    "mine_failure_resurrection",
    "mine_horizon",
    "mine_interaction",
    "mine_inverse",
    "mine_macro_condition",
    "mine_parameter_neighborhood",
    "mine_regime",
    "mine_residual",
    "mine_session",
    "run_all",
]

#: Charts shortest-first. THE LADDER IS THE ADJACENCY: a horizon child is a NEIGHBOUR, never a
#: jump, because "the same mechanism one step slower" is an economic question and "the same
#: mechanism at any of five frequencies" is a sweep.
CHART_LADDER: tuple[str, ...] = ("M5", "M15", "H1", "H4", "D1")
CHART_MINUTES: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240,
                                 "D1": 1440}
#: Horizon bucket per chart, in `mechanism_ontology.HORIZONS` vocabulary, so a contract's declared
#: span prunes charts without a second list to keep in step.
CHART_HORIZON: dict[str, str] = {"M5": "MINUTES", "M15": "MINUTES", "H1": "HOURLY",
                                 "H4": "HOURLY", "D1": "DAILY"}
#: The desk's own horizon axis (`axis_registry.HORIZONS`), for the breadth grid cell.
CHART_GRID_HORIZON: dict[str, str] = {"M5": "intrabar", "M15": "intrabar", "H1": "sub_4h",
                                      "H4": "sub_1d", "D1": "multi_day"}

#: Session windows as the FORWARD CLOCK reads them (`mt5desk.family_call.SESSIONS`), imported when
#: the desk is importable and seeded here so this module is testable on its own. A seed, never a
#: limit (anti-hardcode law).
SESSION_WINDOWS: dict[str, tuple[int, int] | None] = {"asia": (0, 8), "london": (8, 16),
                                                      "ny": (14, 22), "all": None}
try:                                                                    # pragma: no cover - box
    from mt5desk.family_call import SESSIONS as _DESK_SESSIONS
    if isinstance(_DESK_SESSIONS, dict) and _DESK_SESSIONS:
        SESSION_WINDOWS = dict(_DESK_SESSIONS)
except Exception:
    pass

#: Conditioned sessions ordered by window start; `all` is the UNCONDITIONAL CONTROL and sits
#: outside the ladder, because "no session filter" is not adjacent to anything -- it is the arm
#: every conditioned arm is measured against.
SESSION_LADDER: tuple[str, ...] = tuple(
    s for s, _ in sorted(((s, w) for s, w in SESSION_WINDOWS.items() if w is not None),
                         key=lambda kv: kv[1][0]))

#: The four conditioning states every price mechanism could plausibly differ across. Two
#: volatility states and two risk states, and both pairs are TWO-SIDED on purpose: a conditional
#: that only ever fires in one state is a filter, and a filter needs its missed-growth line.
REGIME_LADDER: tuple[str, ...] = ("high_vol", "low_vol", "risk_on", "risk_off")

#: The three factors this desk can actually residualise against from its own bars.
RESIDUAL_FACTORS: tuple[tuple[str, str], ...] = (
    ("usd", "the dollar leg, so what is left is specific to the cross rather than to USD"),
    ("gold", "the metals/haven leg, so what is left is not a repriced haven bid"),
    ("equity", "the risk-asset leg, so what is left is not equity beta wearing an FX ticker"),
)

#: Entry expressions. `instant` fills on the signal bar's close, `delayed` waits one bar for the
#: adverse move the same information usually produces; `market` pays the spread, `limit` asks to
#: be paid it. These are four different economic claims about the same mechanism, not four
#: parameter values.
EXECUTION_VARIANTS: tuple[tuple[str, str], ...] = (("instant", "market"), ("delayed", "market"),
                                                   ("instant", "limit"), ("delayed", "limit"))

#: Information axes (`axis_registry.INFORMATION_SOURCES`). The interaction miner crosses the
#: mechanism with a SECOND one; `unknown` is never an interaction partner.
INFORMATION_AXES: tuple[str, ...] = ("price_only", "cross_asset", "macro", "positioning", "event",
                                     "carry", "microstructure", "seasonality")


# --------------------------------------------------------------------------- the contracts
@dataclass(frozen=True)
class Contract:
    """One mechanism's economics, and the boundaries of them.

    `charts`, `sessions`, `regimes`, `asset_classes` are ADMISSIBLE SETS, not preferences: a child
    outside them is refused by `compatible` before it costs a gate anything. `currencies` stops a
    flow mechanism spraying across the exotics -- a month-end rebalancing claim names the legs
    that carry the flow, and a cross with neither leg is a different claim nobody made.
    """

    mechanism_id: str
    actor: str
    information: str
    rationale: str
    charts: tuple[str, ...]
    sessions: tuple[str, ...]
    regimes: tuple[str, ...]
    asset_classes: tuple[str, ...]
    horizons: tuple[str, ...]
    falsifier: str
    #: Direction reversal is a THEORY, never a free extra cell. True only where the ontology says
    #: the mechanism is symmetric: continuation and reversion are the same economics with the
    #: sign of one parameter flipped (overshoot vs underreaction), so the inverse is a claim
    #: somebody could defend out loud.
    symmetric: bool = False
    residualisable: bool = True
    currencies: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


_ANY: tuple[str, ...] = ("*",)
_ALL_CHARTS = CHART_LADDER
_SESSION_ALL: tuple[str, ...] = ("all", *SESSION_LADDER)


def _c(mechanism_id: str, actor: str, information: str, rationale: str, *, charts: tuple[str, ...],
       sessions: tuple[str, ...], regimes: tuple[str, ...] = REGIME_LADDER,
       asset_classes: tuple[str, ...] = _ANY, horizons: tuple[str, ...] = ("HOURLY", "DAILY"),
       falsifier: str = "", symmetric: bool = False, residualisable: bool = True,
       currencies: tuple[str, ...] = (), keywords: tuple[str, ...] = ()) -> Contract:
    return Contract(mechanism_id=mechanism_id, actor=actor, information=information,
                    rationale=rationale, charts=charts, sessions=sessions, regimes=regimes,
                    asset_classes=asset_classes, horizons=horizons,
                    falsifier=falsifier or f"{mechanism_id} does not separate forward returns "
                                           "beyond the round trip it must be captured through",
                    symmetric=symmetric, residualisable=residualisable, currencies=currencies,
                    keywords=keywords)


#: THE CONTRACTS. Mechanism ids are `axis_registry.MECHANISM_ACTOR`'s, so a compiled cell's grid
#: coordinate joins the breadth registry the desk already keeps rather than opening a second
#: vocabulary. OPEN, like the ontology it registers into: a mechanism nobody here has thought of
#: is added at runtime, and one with no falsifier is refused.
CONTRACTS: dict[str, Contract] = {c.mechanism_id: c for c in (
    _c("session_handover", "cross_session_risk_transferor", "price_only",
       "risk carried across a session boundary is repriced by the participants who arrive next",
       charts=("M15", "H1", "H4"), sessions=SESSION_LADDER,
       keywords=("session handover", "asia session", "london session", "overnight", "handover",
                 "session open", "prior session")),
    _c("session_information_handoff", "later_session_participant", "price_only",
       "information printed in one session is only acted on when the next session's book opens",
       charts=("M15", "H1", "H4"), sessions=SESSION_LADDER,
       keywords=("handoff", "carry over", "lvc", "prior session", "overnight range")),
    _c("fx_fixing_flow", "benchmark_tracking_customer", "price_only",
       "benchmark-tracking customers must transact AT the fix regardless of price",
       charts=("M5", "M15", "H1"), sessions=("london", "ny"), asset_classes=("forex",
                                                                             "forex exotics"),
       horizons=("MINUTES", "HOURLY"), currencies=("USD", "EUR", "GBP", "JPY"),
       keywords=("fix", "fixing", "wmr", "4pm", "benchmark")),
    _c("hedging_demand_close_flow", "close_rebalancing_issuer", "price_only",
       "a dated hedging obligation must be met at the close whatever the close happens to be",
       charts=("M15", "H1", "H4"), sessions=("london", "ny"),
       regimes=("month_end", "quarter_end", "high_vol", "low_vol"),
       currencies=("USD", "EUR", "GBP", "JPY"),
       keywords=("at the close", "settlement", "rebalanc", "hedging demand", "comex",
                 "london close", "closing auction")),
    _c("calendar_seasonality", "calendar_constrained_allocator", "seasonality",
       "allocators act on a calendar they do not choose, so the flow recurs on dates",
       charts=("H4", "D1"), sessions=("all",),
       regimes=("month_end", "quarter_end", "turn_of_month", "risk_on", "risk_off"),
       horizons=("DAILY", "MULTI_DAY", "WEEKLY"), currencies=("USD", "EUR", "GBP", "JPY"),
       keywords=("month end", "quarter", "turn of month", "seasonal", "day of week", "calendar")),
    _c("macro_release", "scheduled_repricer", "macro",
       "a scheduled number forces every holder to reprice within a known window",
       charts=("M15", "H1", "H4"), sessions=("london", "ny"),
       horizons=("MINUTES", "HOURLY", "DAILY"),
       keywords=("cpi", "nfp", "payroll", "release", "fomc", "ecb", "macro", "announcement")),
    _c("forced_flow", "forced_participant_on_a_dated_calendar", "event",
       "a participant with no discretion must trade on a date somebody else chose",
       charts=("H1", "H4", "D1"), sessions=_SESSION_ALL, horizons=("DAILY", "MULTI_DAY"),
       keywords=("forced", "index rebalance", "roll", "expiry", "mandatory")),
    _c("carry_rollover", "negative_carry_holder", "carry",
       "the holder of the negative-carry leg pays every day and eventually stops paying",
       charts=("H4", "D1"), sessions=("all",), horizons=("DAILY", "MULTI_DAY", "WEEKLY"),
       asset_classes=("forex", "forex exotics", "commodities", "crypto"),
       keywords=("carry", "swap", "rollover", "interest differential", "funding")),
    _c("positioning_crowding", "crowded_speculator", "positioning",
       "a crowded position is an inventory somebody must eventually unwind into a thinner book",
       charts=("H4", "D1"), sessions=("all",), horizons=("DAILY", "MULTI_DAY", "WEEKLY"),
       symmetric=True, keywords=("cot", "positioning", "crowded", "net long", "sentiment")),
    _c("relative_value_dislocation", "relative_value_arbitrageur", "cross_asset",
       "two instruments that share a risk factor cannot diverge beyond the cost of closing it",
       charts=("M15", "H1", "H4"), sessions=_SESSION_ALL, symmetric=True,
       keywords=("residual", "spread", "pair", "cointegrat", "relative value", "triangle")),
    _c("cross_market_lead", "slow_venue_participant", "cross_asset",
       "price is discovered where the informed flow is and repriced where it is not",
       charts=("M5", "M15", "H1"), sessions=_SESSION_ALL, horizons=("MINUTES", "HOURLY"),
       keywords=("lead", "lag", "follows", "leads", "transmission", "spillover")),
    _c("trend_persistence", "underreacting_holder", "price_only",
       "holders update slowly, so information arrives in the price over several bars",
       charts=("M15", "H1", "H4", "D1"), sessions=_SESSION_ALL, symmetric=True,
       horizons=("HOURLY", "DAILY", "MULTI_DAY"),
       keywords=("momentum", "trend", "persistence", "continuation", "breakout hold")),
    _c("range_reversion", "overextended_liquidity_taker", "price_only",
       "a taker who moved the price alone has to give it back when the book refills",
       charts=("M5", "M15", "H1", "H4"), sessions=_SESSION_ALL, symmetric=True,
       horizons=("MINUTES", "HOURLY", "DAILY"),
       keywords=("mean revers", "reversion", "range", "fade", "overextend", "rsi", "bollinger")),
    _c("breakout_liquidity", "stop_loss_holder", "price_only",
       "resting stops beyond a level are fuel somebody else can see and reach for",
       charts=("M15", "H1", "H4"), sessions=SESSION_LADDER, symmetric=True,
       keywords=("breakout", "break", "level", "opening range", "donchian", "stop run")),
    _c("volatility_shock", "short_gamma_hedger", "price_only",
       "a short-gamma hedger must trade in the direction of the move that hurt them",
       charts=("M15", "H1", "H4"), sessions=_SESSION_ALL, symmetric=True,
       keywords=("volatility", "vol shock", "squeeze", "jump", "spike", "atr")),
    _c("regime_transition", "stale_regime_positioner", "price_only",
       "positions sized for the last regime are wrong the moment the regime changes",
       charts=("H1", "H4", "D1"), sessions=("all",), horizons=("DAILY", "MULTI_DAY"),
       keywords=("regime", "transition", "switch", "state change", "drawdown conditional")),
    _c("execution_microstructure", "liquidity_provider", "microstructure",
       "the provider of liquidity is paid the spread and charges more when inventory is risky",
       charts=("M5", "M15", "H1"), sessions=_SESSION_ALL, horizons=("SECONDS", "MINUTES",
                                                                    "HOURLY"),
       keywords=("spread", "liquidity", "microstructure", "order flow", "book", "tick")),
    _c("gamma_hedging_state", "option_dealer", "microstructure",
       "a dealer's hedge is mechanical and its sign is known from their gamma",
       charts=("M15", "H1"), sessions=_SESSION_ALL, horizons=("MINUTES", "HOURLY"),
       symmetric=True, keywords=("gamma", "dealer", "option", "hedge", "pin")),
    _c("inventory_shock", "inventory_laden_dealer", "microstructure",
       "a dealer left holding inventory prices to get rid of it",
       charts=("M5", "M15", "H1"), sessions=_SESSION_ALL, horizons=("MINUTES", "HOURLY"),
       keywords=("inventory", "volume spike", "absorption", "dealer position")),
    _c("forced_liquidation", "margin_called_trader", "positioning",
       "a liquidation engine sells to close an account, not to express a view",
       charts=("M5", "M15", "H1"), sessions=_SESSION_ALL, horizons=("MINUTES", "HOURLY"),
       keywords=("liquidation", "margin call", "stop out", "cascade", "forced sell")),
)}
UNKNOWN_MECHANISM = "unknown"


def register_contracts(ontology: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register the contracts into `mechanism_ontology` so ONE module owns the horizon prune.

    The ontology is OPEN and refuses a mechanism with no falsifier; every contract declares one.
    A tree without the library still gets the contracts: the prune degrades to this module's own
    admissible sets rather than going quiet.
    """
    try:
        from libs.research.mechanism_ontology import CORE_MECHANISMS, Mechanism, register
    except Exception:
        return dict(ontology or {})
    out = dict(ontology if ontology is not None else CORE_MECHANISMS)
    for c in CONTRACTS.values():
        out = register(out, Mechanism(
            mechanism_id=c.mechanism_id, economic_rationale=c.rationale, expected_actors=c.actor,
            observables=("return", "range", "spread", "volume", "open_interest"),
            valid_transforms=("LEVEL", "DIFFERENCE", "ZSCORE", "PERCENTILE", "PERSISTENCE",
                              "RESIDUAL", "INTERACTION"),
            valid_horizons=c.horizons, valid_states=c.regimes, falsifiers=(c.falsifier,)))
    return out


# --------------------------------------------------------------------------- compatibility
def chart_admits_session(chart: str, session: str) -> bool:
    """A bar longer than half the session window cannot express a rule conditioned on it.

    DERIVED, NOT LISTED. `asia` is an 8h window; a D1 bar spans 24h, so a D1 "asia breakout" is a
    daily rule with a session label stapled on. Two bars inside the window is the minimum for the
    condition to mean anything -- which is why a session mechanism never gets D1 and no line
    anywhere says "no D1".
    """
    win = SESSION_WINDOWS.get(str(session or "all").lower())
    if win is None:
        return True
    span = max(1, (int(win[1]) - int(win[0])) % 24 or 24) * 60
    return CHART_MINUTES.get(str(chart or "").upper(), 10 ** 6) * 2 <= span


def compatible(contract: Contract | None, *, chart: str = "", session: str = "", regime: str = "",
               asset_class: str = "") -> tuple[bool, str]:
    """May this cell be constructed at all? THE PRUNE, and it runs before anything costs."""
    if contract is None:
        # UNKNOWN is a recorded verdict, not a refusal: an uninterpreted discovery still gets its
        # closure, it just gets the conservative one (price-only charts, no regime claim).
        if chart and chart.upper() not in CHART_LADDER:
            return False, f"{chart} is not a chart this desk keeps bars for"
        if session and not chart_admits_session(chart, session):
            return False, f"a {chart} bar spans more than the {session} window"
        return True, "mechanism UNKNOWN: the conservative closure applies"
    ch = str(chart or "").upper()
    se = str(session or "all").lower()
    rg = str(regime or "").lower()
    ac = " ".join(str(asset_class or "").lower().replace("_", " ").split())
    if ch and ch not in contract.charts:
        return False, (f"{ch} is outside the span over which {contract.mechanism_id} could still "
                       f"be acting ({list(contract.charts)})")
    if se and se not in contract.sessions:
        return False, f"{contract.mechanism_id} is not a {se}-session claim"
    if ch and se and not chart_admits_session(ch, se):
        return False, (f"a {ch} bar spans more than half the {se} window, so the session "
                       "condition cannot be expressed on it")
    if rg and rg not in ("", "unconditional") and rg not in contract.regimes:
        return False, (f"{rg!r} is not a state in which {contract.mechanism_id} is expected to "
                       "differ")
    if ac and contract.asset_classes != _ANY and ac not in contract.asset_classes:
        return False, f"{contract.mechanism_id} does not act on {ac}"
    return True, f"{contract.mechanism_id} admits {ch or '*'} x {se} x {rg or 'unconditional'}"


def _currencies(symbol: str) -> tuple[str, ...]:
    s = str(symbol or "").upper()
    return (s[:3], s[3:6]) if len(s) == 6 and s.isalpha() else (s,)


def currency_ok(contract: Contract | None, symbol: str) -> bool:
    """A flow contract that names its legs only gets instruments carrying one of them."""
    if contract is None or not contract.currencies:
        return True
    return bool(set(_currencies(symbol)) & set(contract.currencies))


# --------------------------------------------------------------------------- the context
@dataclass
class Context:
    """Everything the twelve need, BUILT ONCE PER RUN.

    Once, because the alternative is twelve miners reopening the universe registry per parent --
    the shape of slowness that turns a 240s budget into four parents an hour. `notes`, `priors`
    and `truncated` are where a miner's REFUSAL lands, and the compiler copies all three into the
    artifact and the registry's memory.
    """

    instruments: dict[str, list[str]] = field(default_factory=dict)
    families: frozenset[str] = frozenset()
    defaults: dict[str, dict[str, Any]] = field(default_factory=dict)
    ontology: dict[str, Contract] = field(default_factory=lambda: dict(CONTRACTS))
    macro_states: dict[str, list[str]] = field(default_factory=dict)
    bars_available: Callable[[str, str], bool] | None = None
    lane_ok: Callable[[str], bool] | None = None
    conn: Any = None
    notes: list[dict[str, Any]] = field(default_factory=list)
    priors: list[dict[str, Any]] = field(default_factory=list)
    truncated: list[dict[str, Any]] = field(default_factory=list)
    max_per_miner: int = 8

    def contract(self, mechanism_id: Any) -> Contract | None:
        return self.ontology.get(str(mechanism_id or "").strip().lower())

    def has_bars(self, symbol: str, chart: str) -> bool:
        """ABSENCE IS NOT PERMISSION: with no probe wired this answers False, and the data gate
        blocks the child with a reason naming the path it wanted."""
        if self.bars_available is None:
            return False
        try:
            return bool(self.bars_available(symbol, chart))
        except Exception:
            return False

    def hypothesis_lane(self, symbol: str) -> bool:
        s = str(symbol or "").upper()
        if self.lane_ok is not None:
            try:
                return bool(self.lane_ok(s))
            except Exception:
                return False
        return any(s in syms for syms in self.instruments.values())

    def class_of(self, symbol: str) -> str:
        s = str(symbol or "").upper()
        for klass, syms in self.instruments.items():
            if s in syms:
                return klass
        return ""

    def peers(self, asset_class: str, exclude: str = "") -> list[str]:
        ex = str(exclude or "").upper()
        return [s for s in self.instruments.get(asset_class, []) if s != ex]

    def note(self, miner: str, parent_id: str, why: str) -> None:
        self.notes.append({"miner": miner, "discovery_id": parent_id, "why": why})

    def prior_down(self, mechanism_id: str, why: str) -> None:
        self.priors.append({"mechanism_id": mechanism_id, "direction": "down", "why": why})


# --------------------------------------------------------------------------- child helpers
_SPEC_KEYS = ("family", "symbol", "asset_class", "chart", "session", "regime", "params",
              "information", "horizon", "economic_actor", "mechanism_id", "side", "execution",
              "entry_timing")


def _spec(parent: Mapping[str, Any]) -> dict[str, Any]:
    out = {k: parent.get(k) for k in _SPEC_KEYS}
    out["params"] = dict(parent.get("params") or {})
    return out


def _child(parent: Mapping[str, Any], *, transformation: str, axis: str, why: str,
           **over: Any) -> dict[str, Any]:
    """One child, carrying its transformation, its parents, the axis that MOVED and why."""
    spec = _spec(parent)
    params = dict(spec.get("params") or {})
    params.update(over.pop("params", {}) or {})
    spec.update(over)
    spec["params"] = params
    pid = str(parent.get("discovery_id") or "")
    spec.update({"transformation": transformation, "axis": axis, "why": why,
                 "parent_discovery_ids": [pid] if pid else [],
                 "moved_from": parent.get(axis) if axis in parent else None,
                 "moved_to": spec.get(axis)})
    if spec.get("chart"):
        spec["horizon"] = CHART_GRID_HORIZON.get(str(spec["chart"]).upper(), spec.get("horizon"))
    return spec


def _cap(rows: list[dict[str, Any]], ctx: Context, miner: str,
         parent_id: str) -> list[dict[str, Any]]:
    """Carry at most `max_per_miner` forward AND RECORD WHAT WAS NOT CARRIED.

    The cap is a compute budget and it must SAY SO (L1.61): the members it leaves behind are real
    members of the closure, counted as blocked with a named reason rather than vanishing between
    the miner and the artifact. A closure member with no disposition is the defect.
    """
    n = max(1, int(ctx.max_per_miner))
    if len(rows) > n:
        ctx.truncated.append({"miner": miner, "discovery_id": parent_id, "n": len(rows) - n,
                              "why": f"per-miner compute budget {n}: {len(rows) - n} "
                                     "economically admissible child(ren) of this parent were "
                                     "not built THIS pass and are owed, not refused"})
    return rows[:n]


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --------------------------------------------------------------------------- the twelve
def mine_asset_transfer(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The SAME mechanism on the SAME asset class's other instruments. Never an equity.

    The most under-asked question here: a constraint binding one participant in EURUSD binds the
    same participant in every cross they hold. The class boundary is where the economics stop,
    which is why this miner never crosses it -- `mine_cross_asset` does that, separately.
    """
    pid = str(parent.get("discovery_id") or "")
    klass = str(parent.get("asset_class") or "") or ctx.class_of(str(parent.get("symbol") or ""))
    contract = ctx.contract(parent.get("mechanism_id"))
    peers = [s for s in ctx.peers(klass, str(parent.get("symbol") or ""))
             if ctx.hypothesis_lane(s) and currency_ok(contract, s)]
    if not peers:
        ctx.note("asset_transfer", pid, f"no other hypothesis-lane instrument in {klass!r}"
                 + (" carrying a leg this flow contract names" if contract
                    and contract.currencies else ""))
        return []
    return ([_child(parent, transformation="asset_transfer", axis="symbol", symbol=s,
                        asset_class=klass,
                        why=(f"the constraint that makes {parent.get('mechanism_id')} pay in "
                             f"{parent.get('symbol')} binds the same participant in {s}: same "
                             f"asset class, same session clock, different instrument"))
                 for s in peers])


def mine_horizon(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The ADJACENT charts only (M5 < M15 < H1 < H4 < D1), pruned by the contract's span."""
    pid = str(parent.get("discovery_id") or "")
    chart = str(parent.get("chart") or "H1").upper()
    if chart not in CHART_LADDER:
        ctx.note("horizon", pid, f"{chart!r} is not on the chart ladder; no neighbour is defined")
        return []
    i = CHART_LADDER.index(chart)
    contract = ctx.contract(parent.get("mechanism_id"))
    out: list[dict[str, Any]] = []
    for j in (i - 1, i + 1):
        if not 0 <= j < len(CHART_LADDER):
            continue
        nxt = CHART_LADDER[j]
        ok, why = compatible(contract, chart=nxt, session=str(parent.get("session") or "all"))
        if not ok:
            ctx.note("horizon", pid, f"{nxt}: {why}")
            continue
        out.append(_child(parent, transformation="horizon", axis="chart", chart=nxt,
                          why=(f"one step {'slower' if j > i else 'faster'} than {chart}: if the "
                               "mechanism is real it survives a neighbouring frequency, and if it "
                               "only exists at one it is a fitted parameter")))
    if not out:
        ctx.note("horizon", pid, f"no admissible neighbour of {chart} under this contract")
    return out


def mine_session(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The ADJACENT session windows, plus the unconditional control when the parent is
    conditioned. `all` is not adjacent to anything -- it is what a conditional is measured
    against, and proposing it is how a session claim gets a null hypothesis."""
    pid = str(parent.get("discovery_id") or "")
    session = str(parent.get("session") or "all").lower()
    contract = ctx.contract(parent.get("mechanism_id"))
    chart = str(parent.get("chart") or "H1").upper()
    wanted: list[str] = []
    if session in SESSION_LADDER:
        i = SESSION_LADDER.index(session)
        wanted = [SESSION_LADDER[j] for j in (i - 1, i + 1) if 0 <= j < len(SESSION_LADDER)]
        wanted.append("all")
    else:
        wanted = list(SESSION_LADDER)
    out: list[dict[str, Any]] = []
    for s in wanted:
        ok, why = compatible(contract, chart=chart, session=s)
        if not ok:
            ctx.note("session", pid, f"{s}: {why}")
            continue
        out.append(_child(parent, transformation="session", axis="session", session=s,
                          why=("the unconditional control arm for a session-conditioned claim"
                               if s == "all" else
                               f"the window next to {session}: the participants change at the "
                               f"boundary, so the same mechanism has a different counterparty")))
    if not out:
        ctx.note("session", pid, f"no admissible session neighbour of {session!r} on {chart}")
    return out


def mine_regime(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """high_vol / low_vol / risk_on / risk_off, BOTH SIDES OF BOTH PAIRS.

    The regime is part of the candidate's identity (the regime specialisation law): a sleeve is
    never rejected for winning in only some regimes. Proposing only the 'good' side is a filter
    chosen in advance; proposing both is a measurement.
    """
    pid = str(parent.get("discovery_id") or "")
    contract = ctx.contract(parent.get("mechanism_id"))
    current = str(parent.get("regime") or "").lower()
    pool = contract.regimes if contract is not None else REGIME_LADDER
    out: list[dict[str, Any]] = []
    for r in pool:
        if r == current:
            continue
        ok, why = compatible(contract, chart=str(parent.get("chart") or ""),
                             session=str(parent.get("session") or "all"), regime=r)
        if not ok:
            ctx.note("regime", pid, f"{r}: {why}")
            continue
        out.append(_child(parent, transformation="regime", axis="regime", regime=r,
                          params={"regime": r},
                          why=(f"conditioned on {r}: the mechanism's counterparty is under a "
                               "different constraint in this state, and a specialist runs at full "
                               "size in its own regime rather than being blended away")))
    if not out:
        ctx.note("regime", pid, "the contract declares no conditioning state this parent is not "
                                "already in")
    return out


def mine_residual(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The mechanism on what is LEFT once the dollar, metal and equity legs are removed.

    The `residual` tag is honoured by the families that read it (`cross_asset_residual`,
    `pca_residual`, `relative_value`, `triangle`); on one that does not, the tag rides on the
    child and the ECONOMIC gate refuses it BY NAME, rather than the child silently becoming an
    un-residualised duplicate of its parent.
    """
    pid = str(parent.get("discovery_id") or "")
    contract = ctx.contract(parent.get("mechanism_id"))
    if contract is not None and not contract.residualisable:
        ctx.note("residual", pid, f"{contract.mechanism_id} is a claim about the instrument's own "
                                  "flow; residualising it removes the thing being claimed")
        return []
    sym = str(parent.get("symbol") or "").upper()
    out = []
    for factor, why in RESIDUAL_FACTORS:
        if factor == "usd" and "USD" not in _currencies(sym):
            continue
        out.append(_child(parent, transformation="residual", axis="information",
                          information="cross_asset",
                          params={"residual": factor, "residual_tag": "residual"},
                          why=f"residualised against {why}"))
    if not out:
        ctx.note("residual", pid, f"no factor leg applies to {sym}")
    return out


def mine_interaction(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The mechanism CROSSED with a second information axis from the axis registry.

    Not a feature sweep: each axis is a different participant's constraint, and the interaction
    asks whether the parent's mechanism is stronger when that second participant is also pressed.
    """
    pid = str(parent.get("discovery_id") or "")
    own = str(parent.get("information") or "price_only").lower()
    out = [_child(parent, transformation="interaction", axis="information", information=axis,
                  params={"conditioner": axis},
                  why=(f"{parent.get('mechanism_id')} x {axis}: two constraints acting at once is "
                       "a different claim from either alone, and it is the claim with the "
                       "information gain nobody spends trials on"))
           for axis in INFORMATION_AXES if axis not in (own, "price_only")]
    if not out:
        ctx.note("interaction", pid, f"no second information axis distinct from {own!r}")
    return out


def mine_inverse(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The SIGN FLIPPED, and only where the ontology says direction is symmetric.

    A free inverse for every parent doubles the trial count for nothing: the deflated hurdle is a
    shared budget, so an undefended inverse raises the bar on every defended cell. Symmetry is
    declared where continuation and reversion are one economics with one sign flipped; everywhere
    else this returns [] and says so.
    """
    pid = str(parent.get("discovery_id") or "")
    contract = ctx.contract(parent.get("mechanism_id"))
    if contract is None:
        ctx.note("inverse", pid, "mechanism UNKNOWN: symmetry is a claim about economics, and "
                                 "there is no economics named to claim it about")
        return []
    if not contract.symmetric:
        ctx.note("inverse", pid, f"{contract.mechanism_id} is directional by construction "
                                 f"({contract.actor} is pressed one way); an inverse is a "
                                 "different mechanism, not this one reversed")
        return []
    side = str(parent.get("side") or parent.get("params", {}).get("side_mode") or "follow").lower()
    flip = {"follow": "revert", "revert": "follow", "long": "short", "short": "long"}.get(side)
    if flip is None:
        ctx.note("inverse", pid, f"side {side!r} has no declared opposite")
        return []
    return [_child(parent, transformation="inverse", axis="side", side=flip,
                   params={"side_mode": flip},
                   why=(f"{contract.mechanism_id} is symmetric: {contract.actor} can be on either "
                        f"side of the same constraint, so {flip} is a defensible claim rather "
                        "than a free extra cell"))]


def mine_execution(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """instant vs delayed entry, limit vs market. FOUR CLAIMS, NOT FOUR PARAMETERS.

    The bottleneck law: the marginal resource goes to the binding constraint, and here that is far
    more often execution than alpha. A mechanism that dies at market and lives on a limit was
    never a dead mechanism.
    """
    pid = str(parent.get("discovery_id") or "")
    now = (str(parent.get("entry_timing") or "instant").lower(),
           str(parent.get("execution") or "market").lower())
    out = [_child(parent, transformation="execution", axis="execution", execution=style,
                  entry_timing=timing, params={"entry_timing": timing, "execution_style": style},
                  why=(f"{timing} entry at {style}: the same signal expressed through a different "
                       "side of the spread is a different economic bet, and execution is the "
                       "constraint that binds more often than edge"))
           for timing, style in EXECUTION_VARIANTS if (timing, style) != now]
    if not out:
        ctx.note("execution", pid, "the parent already occupies every execution expression")
    return out


def mine_cross_asset(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """The NEAREST instrument of ANOTHER non-equity class -- one per class, never a sweep.

    Nearest is the class's deepest-history instrument, this desk's standing liquidity proxy
    (`axis_registry.instruments_by_class` sorts that way). One per class keeps this a question
    about whether the mechanism crosses a class boundary at all, not a wider asset transfer.
    """
    pid = str(parent.get("discovery_id") or "")
    own = str(parent.get("asset_class") or "") or ctx.class_of(str(parent.get("symbol") or ""))
    contract = ctx.contract(parent.get("mechanism_id"))
    out: list[dict[str, Any]] = []
    for klass in sorted(ctx.instruments):
        if klass == own or "equit" in klass or "share" in klass:
            continue
        if contract is not None and contract.asset_classes != _ANY \
                and klass not in contract.asset_classes:
            ctx.note("cross_asset", pid, f"{klass}: {contract.mechanism_id} does not act on it")
            continue
        nearest = next((s for s in ctx.instruments[klass]
                        if ctx.hypothesis_lane(s) and currency_ok(contract, s)), None)
        if nearest is None:
            continue
        out.append(_child(parent, transformation="cross_asset", axis="symbol", symbol=nearest,
                          asset_class=klass,
                          why=(f"the deepest-history {klass} instrument: does the constraint "
                               "behind this mechanism survive a change of asset class, or was it "
                               "a property of the class all along?")))
    if not out:
        ctx.note("cross_asset", pid, "no other non-equity class carries an admissible instrument")
    return out


def mine_macro_condition(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """Conditioned on a macro state the desk actually HOLDS (`data/axes/*.json`).

    No axis file, no child, and the absence is recorded as UNMEASURED rather than resolved to
    'this mechanism has no macro conditionality' -- which is the WS-005 class: absence read as a
    clean verdict.
    """
    pid = str(parent.get("discovery_id") or "")
    if not ctx.macro_states:
        ctx.note("macro_condition", pid, "UNMEASURED: no macro axis file on this box, so the "
                                         "macro closure is unknown rather than empty")
        return []
    out = []
    for axis, states in sorted(ctx.macro_states.items()):
        for state in list(states)[:2]:
            out.append(_child(parent, transformation="macro_condition", axis="regime",
                              regime=f"{axis}:{state}", information="macro",
                              params={"macro_axis": axis, "macro_state": state},
                              why=(f"conditioned on {axis}={state}: a mechanism whose counterparty "
                                   "is a rates- or policy-constrained holder should be stronger "
                                   "in one state of that axis and weaker in the other")))
    if not out:
        ctx.note("macro_condition", pid, "the macro axis files carry no named state")
    return out


#: What a failure class LICENSES. The graveyard is sacred and re-opening needs a NAMED enabling
#: change addressing the original mechanism of death (L1.16a) -- these ARE those changes, one per
#: cause, and `redundant`/`no_edge` license nothing because nothing about the cause was addressed.
FAILURE_ROUTES: dict[str, str] = {
    "cost_killed": "execution",
    "regime_specific": "regime",
    "wrong_direction": "inverse",
    "wrong_horizon": "horizon",
    "wrong_asset": "asset_transfer",
    "execution_killed": "execution",
    "unstable": "regime",
    "forward_decay": "regime",
}


def mine_failure_resurrection(parent: Mapping[str, Any], ctx: Context) -> list[dict[str, Any]]:
    """A dead cell's failure class is an INSTRUCTION, and two of them say STOP.

    cost_killed -> the limit and delayed expressions, because the edge was there and the round
    trip ate it. regime_specific -> the conditioned variants. wrong_direction -> the inverse.
    wrong_horizon -> the adjacent charts. wrong_asset -> the transfers. redundant -> NOTHING and
    the branch STOPS: a duplicate's children are duplicates and spend a shared multiplicity budget
    on cells the desk already holds. no_edge -> nothing, and the mechanism's prior goes DOWN,
    which is the only way a miner may touch a prior.
    """
    pid = str(parent.get("discovery_id") or "")
    fc = str(parent.get("failure_class") or "").strip().lower()
    if not fc:
        ctx.note("failure_resurrection", pid, "no failure class on this parent; nothing died here "
                                              "and there is nothing to resurrect")
        return []
    if fc == "redundant":
        ctx.note("failure_resurrection", pid, "STOP: the parent was killed as REDUNDANT. Its "
                                              "children are redundant with the same holder, and "
                                              "expanding them spends a shared multiplicity budget "
                                              "on cells the desk already owns")
        return []
    if fc == "no_edge":
        ctx.prior_down(str(parent.get("mechanism_id") or UNKNOWN_MECHANISM),
                       f"a {parent.get('symbol')} cell was judged no_edge: the prior on this "
                       "mechanism falls, and no child is minted from a cause nothing addressed")
        ctx.note("failure_resurrection", pid, "no_edge licenses no transformation: the cause was "
                                              "the mechanism itself. Prior lowered instead")
        return []
    route = FAILURE_ROUTES.get(fc)
    if route is None:
        ctx.note("failure_resurrection", pid, f"failure class {fc!r} has no declared route; "
                                              "counted, never guessed")
        return []
    kids = MINERS[route](parent, ctx)
    out = []
    for k in kids:
        k = dict(k)
        k["transformation"] = "failure_resurrection"
        k["resurrection_of"] = fc
        k["resurrection_route"] = route
        k["why"] = (f"resurrected from a {fc} verdict: {k.get('why')} -- this is the NAMED "
                    "enabling change L1.16a requires, addressing the mechanism of death rather "
                    "than re-litigating the kill")
        if fc == "cost_killed" and route == "execution":
            k["params"] = {**(k.get("params") or {}), "cost_aware": True}
        out.append(k)
    if not out:
        ctx.note("failure_resurrection", pid, f"{fc} routes to {route}, which produced nothing "
                                              "for this parent")
    return out


def mine_parameter_neighborhood(parent: Mapping[str, Any],
                                ctx: Context) -> list[dict[str, Any]]:
    """x0.5 and x2 of each numeric parameter the FAMILY declares. A neighbourhood, not a grid.

    Read from `mt5desk.families` signatures and defaults, so a family that changes its defaults
    moves its own neighbourhood with it. Halving and doubling rather than a fine grid on purpose:
    an edge that needs 1.85 rather than 1.8 is a fitted parameter wearing a hypothesis.
    """
    pid = str(parent.get("discovery_id") or "")
    fam = str(parent.get("family") or "")
    declared = dict(ctx.defaults.get(fam) or {})
    live = {k: v for k, v in (parent.get("params") or {}).items() if _numeric(v)}
    base = {**{k: v for k, v in declared.items() if _numeric(v)}, **live}
    if not base:
        ctx.note("parameter_neighborhood", pid,
                 f"family {fam!r} declares no numeric parameter on this tree; its neighbourhood "
                 "is UNMEASURED, not empty")
        return []
    out: list[dict[str, Any]] = []
    for key in sorted(base):
        for mult in (0.5, 2.0):
            v = base[key]
            nv = max(1, round(v * mult)) if isinstance(v, int) else round(float(v) * mult, 6)
            if nv == v:
                continue
            out.append(_child(parent, transformation="parameter_neighborhood", axis="params",
                              params={key: nv},
                              why=(f"{key} {v} -> {nv} (x{mult}): the family's own declared "
                                   "neighbourhood. An edge that dies at a factor of two was a "
                                   "fitted parameter, and one that survives is worth a gate")))
    return out


#: THE TWELVE, in a stable order so the artifact's `by_miner` block reads the same every run.
#: Order is presentation only -- every miner sees the same parent and none may suppress another.
MINERS: dict[str, Callable[[Mapping[str, Any], Context], list[dict[str, Any]]]] = {
    "asset_transfer": mine_asset_transfer,
    "horizon": mine_horizon,
    "session": mine_session,
    "regime": mine_regime,
    "residual": mine_residual,
    "interaction": mine_interaction,
    "inverse": mine_inverse,
    "execution": mine_execution,
    "cross_asset": mine_cross_asset,
    "macro_condition": mine_macro_condition,
    "failure_resurrection": mine_failure_resurrection,
    "parameter_neighborhood": mine_parameter_neighborhood,
}


def run_all(parent: Mapping[str, Any], ctx: Context,
            only: Iterable[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Every miner on the SAME parent, independently; the compute budget applied ONCE here.

    One miner raising costs the other eleven nothing -- its exception is a note, which is a
    disposition, and the run continues. The cap lives here rather than inside the twelve, so a
    miner called directly returns its WHOLE closure and only the organ's budget truncates it.
    """
    pid = str(parent.get("discovery_id") or "")
    wanted = set(only) if only is not None else set(MINERS)
    out: dict[str, list[dict[str, Any]]] = {}
    for name, fn in MINERS.items():
        if name not in wanted:
            continue
        try:
            out[name] = _cap(list(fn(parent, ctx)), ctx, name, pid)
        except Exception as exc:
            ctx.note(name, pid,
                     f"miner raised {type(exc).__name__}: {exc}; counted, never swallowed")
            out[name] = []
    return out
