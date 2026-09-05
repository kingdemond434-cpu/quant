"""The counterfactual world: what each decision was worth against the ones the desk did not make.

    for each decision D_t: simulate entered / skipped / 0.5x / 1.0x / 1.5x / market / limit /
    delayed N / fixed TP / trail / hold-to-ttl / partial, and return dElog_decision per arm

WHY THIS AND NOT THE ENGINES THAT ALREADY EXIST. Five feedback engines already price the desk's
own behaviour and every one of them prices ONE arm. `counterfactual_markout` replays the brackets
a veto refused, and only those. `action_counterfactuals` asks whether a closed trade should have
been held, and only that. `excursions` measures MFE/MAE, `exit_accounts` splits the exit, and
`missed_growth` values the rails from those reports. Nothing has ever priced the SIZE the desk
chose, and nothing at all has priced the EXECUTION: `execution_policy` scores market against limit
against delayed at decision time, writes the loser's utility onto the intent row, and the desk
then records only the `market` plan's realised cost -- so the alternatives it rejected have never
once been settled against the tape. This module prices every arm of one decision on one axis, so
Veto, Sizing, Execution, Exit and Missed-Trade alpha are five readings of one measurement rather
than five engines that cannot be added up.

THE SIGN CONVENTION, ONE FOR ALL FIVE CLASSES, because a mixed one is how a report gets read
backwards. **Every number here is the ALTERNATIVE minus the DESK**: positive means the road not
taken was better and the desk's own choice cost growth; negative means the desk was right. So
MISSED_TRADE_ALPHA > 0 is a bill for the trades it skipped, SIZING_ALPHA's 1.5x arm < 0 says
sizing up would have hurt, and a class that reads negative is the desk being RIGHT and is
reported exactly as loudly as one that reads positive. Nothing here is hidden for reading badly:
a veto that earns its place shows up as a negative missed-trade number and that is the point.

    VETO_ALPHA is the one exception and it is deliberate. `missed_growth.measure_veto` values a
    rail in the OPPOSITE sense -- `filter_value_r = -(sum of counterfactual R)`, positive when
    the veto saved money -- and it reads those field names off `FILTER_VALUE.json`. So each veto
    reason carries BOTH: `mean_d_elog` in this module's convention, and `mean_avoided_r` /
    `filter_value_r` / `t` / `verdict` in the rail's, under the names the rail already reads.

LIKE FOR LIKE, WHICH IS THE WHOLE MEASUREMENT. A taken trade has a realised R on the ledger and
its alternatives can only ever be replayed. Differencing the two would put the replay's own error
-- the bar granularity, the intrabar tie-break, the cost model -- straight into every alpha. So
the baseline the arms are differenced against is the REPLAY of what the desk actually did, and
the realised R is carried beside it as `r_realised` with `replay_error_r` between them. The
alphas are then differences of replays, in which the replay error cancels; `replay_error_r` is
how a reader sees whether the replay deserves to be believed at all.

A BRACKET THE MARKET NEVER OFFERED IS NOT A ZERO. It is NOT_TRIGGERED and it enters no class,
for the reason `counterfactual_markout` already wrote down: counting it as +0 drags every veto
toward "harmless". Likewise a limit arm that never filled is a real zero for THAT arm (the order
existed and did not fill) but a decision whose market arm never triggered is not a decision at
all.

THE COST POSTERIOR IS THE DESK'S OWN AND THE ROW SAYS WHICH ONE. `resolve_cost_model` prefers the
execution twin's per-symbol recalibration (live fills, calibrated), then the fitted fill surface,
then the registry spread at the honest baseline (`Costs.from_symbol`'s own mult=2.0: a round trip
crosses the spread twice and half of all fills are worse than the median). Whichever answered is
stamped on every priced row as `cost_model.source` with the reason it was the best available, so
no alpha can be read without knowing what priced it.

UNITS. R is against the decision's OWN stated risk |entry - stop|, one denominator for every arm
so the arms are comparable. Log-wealth is `log(1 + f * m * R)` with `f` the sleeve's risk fraction
from the allocator's book at that minute and `m` the size multiple -- which is why 1.5x on a loser
reads worse than 1.5x on a winner reads better, and why sizing alpha is not just R times a number.

Prices and aggregates. Trades nothing, promotes nothing, and reads no file: the dataset row and
the bars come in as arguments, so the pricing is testable without a desk under it.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "ALPHA_CLASSES",
    "BRACKET_LIVE_BARS",
    "DEFAULT_RISK_FRACTION",
    "DELAY_BARS",
    "EXECUTION_ARMS",
    "EXIT_ARMS",
    "HONEST_SPREAD_MULT",
    "LIMIT_OFFSET_SPREADS",
    "MIN_N",
    "MIN_N_VETO",
    "NOT_TRIGGERED",
    "NO_BARS",
    "PRICED",
    "PRICER_VERSION",
    "SIZE_ARMS",
    "TTL_BARS",
    "UNMEASURED",
    "UNPRICED",
    "Bar",
    "CostModel",
    "aggregate",
    "bars_from_rows",
    "cost_model_baseline",
    "cost_model_from_surface",
    "cost_model_from_twin",
    "price_row",
    "resolve_cost_model",
    "top_decisions",
]

#: Bumped when the PRICING changes meaning, so a re-priced dataset row is a new version rather
#: than a silent overwrite. The dataset's own schema_version covers the row SHAPE; this covers
#: what the numbers in it mean.
PRICER_VERSION: int = 1

PRICED = "PRICED"
NO_BARS = "NO_BARS"
UNPRICED = "UNPRICED"
NOT_TRIGGERED = "NOT_TRIGGERED"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"

#: The five readings the principal named. Every one is (alternative - desk) in log-wealth.
ALPHA_CLASSES: tuple[str, ...] = (
    "VETO_ALPHA", "SIZING_ALPHA", "EXECUTION_ALPHA", "EXIT_ALPHA", "MISSED_TRADE_ALPHA",
)
#: The size menu, as multiples of what the allocator said. 0.5x is the capital modifier's REDUCE
#: category, 1.5x its BOOST; 1.0x is carried explicitly so a reader sees the baseline in the table.
SIZE_ARMS: tuple[float, ...] = (0.5, 1.0, 1.5)
#: The three the execution policy already chooses between and only ever settles one of.
EXECUTION_ARMS: tuple[str, ...] = ("market", "limit", "delayed")
#: The four exit rules the desk's own engine can express (`Signal.bank_frac`, `runner_trail_k`).
EXIT_ARMS: tuple[str, ...] = ("fixed_tp", "trail", "hold", "partial")

#: Bars a resting bracket stays live before the desk's housekeeping would have pulled it. Twelve
#: H1 bars is `counterfactual_markout.BRACKET_LIVE_H`, kept identical so the two engines can be
#: cross-read against each other rather than argued about.
BRACKET_LIVE_BARS: int = 12
#: Bars a counterfactual position may run before the time exit -- `counterfactual_markout`'s
#: HOLD_BARS, and the families' own TTL order of magnitude.
TTL_BARS: int = 24
#: The limit arm rests this many spreads BETTER than the market arm's fill reference: same signal,
#: entered on a pullback, filled only if the market came back for it. "at a stated distance" --
#: the distance is stated here and carried on every priced row.
LIMIT_OFFSET_SPREADS: float = 1.0
#: The delayed arm enters this many bars after the market arm would have. Two bars is long enough
#: to matter on an H1 clock and short enough that the signal is still the one that was measured.
DELAY_BARS: int = 2
#: The trail arm's stop rides this many R behind the best excursion so far, and the partial arm
#: banks half at this R with the runner's stop at break-even -- the engine's own `bank_protect_k=0`
#: convention, so these arms are rules the desk could actually place.
TRAIL_R: float = 1.0
PARTIAL_AT_R: float = 1.0
PARTIAL_FRACTION: float = 0.5

#: `Costs.from_symbol`'s own words: "mult=2.0 is the honest baseline rather than a stress -- a
#: round trip crosses the spread on the way in and again on the way out, and a median is a median".
HONEST_SPREAD_MULT: float = 2.0
#: Fusion Zero's published contract, per lot per side.
COMMISSION_PER_LOT: float = 2.25
#: The risk fraction one trade carries when the allocator's book does not name the sleeve. The
#: desk's heat target is 20% across the book; one sleeve's trade is a per-cent of wealth, not a
#: tenth. Used only as a stated fallback and reported as such on the row.
DEFAULT_RISK_FRACTION: float = 0.01
#: 1 + f*R can go non-positive on a fabricated row; the log is floored rather than raised, because
#: a pricing fault must cost a number and never a pass.
RUIN_FLOOR: float = 1e-6

#: Below this many priced rows a class is UNMEASURED: n is reported and nothing else. Ten is the
#: execution twin's MIN_N and `missed_growth`'s, so the three engines agree on what a sample is.
MIN_N: int = 10
#: A veto REASON is a rule, and a rule needs more than a bucket before its verdict is a verdict.
#: Twenty is `counterfactual_markout`'s own threshold, kept so the vocabulary is one vocabulary.
MIN_N_VETO: int = 20
Z95: float = 1.959964


# --------------------------------------------------------------------------- bars
@dataclass(frozen=True)
class Bar:
    """One bar, in the only four fields a counterfactual needs. The organ converts whatever frame
    it has; keeping this module free of pandas is what lets a test build a world by hand."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float


def bars_from_rows(rows: Iterable[Mapping[str, Any]] | Iterable[Sequence[Any]]) -> list[Bar]:
    """Bars from mappings (`{"ts"/"time", "open", "high", "low", "close"}`) or 5-tuples, sorted by
    time. A row that cannot be read is dropped rather than guessed at."""
    out: list[Bar] = []
    for r in rows:
        try:
            if isinstance(r, Mapping):
                ts = _ts(r.get("ts") if r.get("ts") is not None else r.get("time"))
                vals = (r.get("open"), r.get("high"), r.get("low"), r.get("close"))
            else:
                seq = list(r)
                ts = _ts(seq[0])
                vals = (seq[1], seq[2], seq[3], seq[4])
            if ts is None:
                continue
            o, h, lo, c = (float(v) for v in vals)  # type: ignore[arg-type]
        except (IndexError, TypeError, ValueError):
            continue
        if not all(math.isfinite(x) for x in (o, h, lo, c)):
            continue
        out.append(Bar(ts=ts, open=o, high=h, low=lo, close=c))
    out.sort(key=lambda b: b.ts)
    return out


def _ts(v: Any) -> datetime | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo is not None else v.replace(tzinfo=UTC)
    s = str(v).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d.astimezone(UTC) if d.tzinfo is not None else d.replace(tzinfo=UTC)


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _d(v: Any) -> dict[str, Any]:
    return {str(k): val for k, val in v.items()} if isinstance(v, Mapping) else {}


def _r(x: float | None, nd: int = 6) -> float | None:
    return None if x is None or not math.isfinite(x) else round(x, nd)


# --------------------------------------------------------------------------- the cost posterior
@dataclass(frozen=True)
class CostModel:
    """What one symbol costs, and WHICH of the desk's own posteriors said so.

    `source` is stamped on every row this model priced. It is not decoration: the twin's number
    is measured on live fills, the surface's is fitted on the box's own markout rows, and the
    registry baseline is a median spread doubled -- three different claims to believe, and an
    alpha read without knowing which one is behind it is not a measurement.

    Fractions of price throughout, the axis `fill_surface.expected_slip`,
    `execution_registry.record_outcome` and `digital_twin` already share.
    """

    source: str
    why: str
    #: Round-trip spread as a fraction of price. Half of it is charged on each side.
    spread_frac: float
    #: One-way slip beyond the reference quote a market order pays, fraction of price.
    slip_frac: float
    #: Round-trip commission as a fraction of price.
    commission_frac: float = 0.0
    #: Additive correction to the resting-order fill prior, from the twin's calibration.
    fill_shift: float = 0.0
    #: Cases or fills behind the numbers, so a thin posterior is visible in the report.
    n: int = 0

    def entry_cost_frac(self, execution: str) -> float:
        """What crossing costs on the way IN. A passive limit fill crosses nothing: it waits and
        is paid the queue, so it carries neither the half spread nor the market order's slip --
        which is precisely the saving the execution arm exists to price."""
        if execution == "limit":
            return 0.0
        return 0.5 * self.spread_frac + self.slip_frac

    def exit_cost_frac(self) -> float:
        """The way OUT is always taken at market: a stop, a target and a time exit all cross."""
        return 0.5 * self.spread_frac + self.slip_frac

    def p_fill(self, distance_frac: float) -> float:
        """P(a resting order `distance_frac` from the quote fills), the prior `FillSurface.p_fill`
        and `digital_twin` both fall back to, shifted by the twin's measured calibration. Reported
        on the row; it never overrides the tape, because where bars exist the tape is the answer
        and a probability is only a belief about one."""
        if self.spread_frac <= 0:
            return 1.0 if distance_frac <= 0 else 0.5
        p = 1.0 if distance_frac <= 0 else math.exp(-distance_frac / self.spread_frac)
        return min(1.0, max(0.0, p + self.fill_shift))

    def to_row(self) -> dict[str, Any]:
        return {"source": self.source, "why": self.why, "spread_frac": _r(self.spread_frac, 9),
                "slip_frac": _r(self.slip_frac, 9), "commission_frac": _r(self.commission_frac, 9),
                "fill_shift": _r(self.fill_shift, 6), "n": self.n}


def cost_model_from_twin(symbol: str, twin: Mapping[str, Any], *,
                         min_n: int = MIN_N) -> CostModel | None:
    """The execution twin's per-symbol recalibration as a cost model, or None when it has not
    measured this symbol. THE FIRST CHOICE: it is the only one of the three fitted on what the
    venue actually did to this desk's own orders, and its asymmetry (costs rise on thin evidence,
    fall only on thick) is exactly the direction a counterfactual must not be optimistic in."""
    recal = _d(twin.get("recalibration"))
    row = _d(_d(recal.get("symbols")).get(symbol))
    if not row:
        return None
    slip = _d(row.get("slip"))
    n = int(_f(slip.get("n")) or 0)
    applied = _f(slip.get("applied_frac"))
    if applied is None or n < min_n:
        return None
    sims = _d(twin.get("sim_costs"))
    spread = _f(_d(sims.get(symbol)).get("spread_frac"))
    shift = _f(_d(row.get("fill")).get("applied_shift")) or 0.0
    return CostModel(
        source="execution_twin",
        why=(f"EXECUTION_TWIN recalibration for {symbol}: slip applied_frac from {n} live cases "
             f"({slip.get('why') or 'measured'})"),
        spread_frac=abs(spread) if spread is not None else 0.0,
        slip_frac=max(applied, 0.0), fill_shift=shift, n=n)


def cost_model_from_surface(symbol: str, surface: Mapping[str, Any], *,
                            spread_frac: float | None = None,
                            min_fills: int = 30) -> CostModel | None:
    """The fitted fill surface's measured mean slip, or None when the box has not filled enough
    orders to have fitted anything.

    THE SURFACE'S COEFFICIENTS ARE NOT USED AND THAT IS ON PURPOSE. `FillSurface.expected_slip`
    needs a seven-feature vector (spread, vol, hour, size, direction, distance) in the surface's
    own units; a dataset row carries the quote and the hour but not the vol or the distance the
    fit was made on, and inventing the missing three to reach a per-row number would be a fitted
    surface evaluated at made-up points. Its `mean_slip_measured` over the fills it DID see is a
    real measurement of this box's tape, so that is what is used, and this note is why.
    """
    n = int(_f(surface.get("n_fills")) or 0)
    slip = _f(surface.get("mean_slip_measured"))
    if slip is None or n < min_fills:
        return None
    return CostModel(
        source="fill_surface",
        why=(f"FILL_SURFACE mean measured slip over {n} joined fills ({surface.get('note')}); "
             "the fitted coefficients need features the dataset row does not carry"),
        spread_frac=abs(spread_frac) if spread_frac is not None else 0.0,
        slip_frac=max(slip, 0.0), n=n)


def cost_model_baseline(symbol: str, meta: Mapping[str, Any] | None = None, *,
                        price: float | None = None,
                        spread_mult: float = HONEST_SPREAD_MULT) -> CostModel:
    """The registry's own spread at the honest baseline -- `Costs.from_symbol(meta, mult=2.0)`
    restated as fractions of price, which is the axis every other cost on this desk uses.

    THE LAST RESORT, AND IT IS NEVER OPTIMISTIC. With no meta and no price it charges nothing and
    says so: a zero cost model that ANNOUNCES itself is honest, while a fabricated spread would
    make every execution arm look free and manufacture execution alpha out of arithmetic.
    """
    m = _d(meta)
    pts = _f(m.get("median_spread_pts"))
    tick = _f(m.get("tick_size"))
    digits = _f(m.get("digits"))
    if tick is None and digits is not None:
        tick = 10.0 ** (-int(digits))
    px = price if price is not None and price > 0 else None
    spread_frac = 0.0
    if pts is not None and tick is not None and px is not None:
        spread_frac = pts * tick * spread_mult / px
    contract = _f(m.get("contract_size"))
    tick_value = _f(m.get("tick_value"))
    commission_frac = 0.0
    if contract is not None and contract > 0 and px is not None:
        # Commission is a currency amount per lot per side. `contract_size * tick_size /
        # tick_value` is how many price units one unit of account currency buys -- the conversion
        # `Costs.quote_per_account` exists for, and the one whose absence was a 184x undercharge.
        qpa = (contract * tick / tick_value
               if tick is not None and tick_value is not None and tick_value > 0 else 1.0)
        commission_frac = 2.0 * COMMISSION_PER_LOT * qpa / (contract * px)
    why = (f"registry median_spread_pts x {spread_mult:g} (Costs.from_symbol's honest baseline) "
           f"for {symbol}" if spread_frac > 0 else
           f"no spread in the registry for {symbol} and no reference price: costs charged as "
           "zero, and this row says so rather than inventing one")
    return CostModel(source="costs_baseline" if spread_frac > 0 else "none",
                     why=why, spread_frac=spread_frac, slip_frac=0.0,
                     commission_frac=commission_frac, n=0)


def resolve_cost_model(symbol: str, *, twin: Mapping[str, Any] | None = None,
                       surface: Mapping[str, Any] | None = None,
                       meta: Mapping[str, Any] | None = None,
                       price: float | None = None) -> CostModel:
    """The best of the desk's own posteriors for this symbol, with the reason it won.

    Twin, then surface, then the registry baseline. The order is evidence order: live fills of
    this desk's own orders, then this box's fitted tape, then a published median doubled. The
    loser is not silently discarded -- the winner carries `why`, and the organ reports the census
    of sources so a reader can see how much of an alpha rests on which claim.
    """
    base = cost_model_baseline(symbol, meta, price=price)
    if twin is not None:
        m = cost_model_from_twin(symbol, twin)
        if m is not None:
            return CostModel(source=m.source, why=m.why,
                             spread_frac=m.spread_frac or base.spread_frac,
                             slip_frac=m.slip_frac,
                             commission_frac=base.commission_frac, fill_shift=m.fill_shift, n=m.n)
    if surface is not None:
        m = cost_model_from_surface(symbol, surface, spread_frac=base.spread_frac)
        if m is not None:
            return CostModel(source=m.source, why=m.why,
                             spread_frac=m.spread_frac or base.spread_frac,
                             slip_frac=m.slip_frac,
                             commission_frac=base.commission_frac, n=m.n)
    return base


# --------------------------------------------------------------------------- the replay
def _locate(bars: Sequence[Bar], when: datetime) -> int | None:
    """The index of the last bar at or before the decision minute: the bar the desk was looking
    at. None when the decision predates the bars, which is NO_BARS and never an assumption."""
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].ts <= when:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1 if lo > 0 else None


def _reach(bars: Sequence[Bar], start: int, stop: int, direction: int, level: float) -> int | None:
    """The first bar in [start, stop) whose range REACHES `level` in the trade's direction -- a
    buy stop triggering, a sell stop triggering."""
    for j in range(max(start, 0), min(stop, len(bars))):
        b = bars[j]
        if (direction > 0 and b.high >= level) or (direction < 0 and b.low <= level):
            return j
    return None


def _improve(bars: Sequence[Bar], start: int, stop: int, direction: int,
             level: float) -> int | None:
    """The first bar in [start, stop) that comes BACK to `level` -- the limit arm's pullback."""
    for j in range(max(start, 0), min(stop, len(bars))):
        b = bars[j]
        if (direction > 0 and b.low <= level) or (direction < 0 and b.high >= level):
            return j
    return None


@dataclass(frozen=True)
class _Path:
    """One replayed position: where it left, why, and after how many bars."""

    exit_price: float
    reason: str
    bars_held: int
    r_gross: float


def _run(bars: Sequence[Bar], entry_idx: int, direction: int, entry: float, stop: float,
         target: float | None, rule: str, *, ttl: int = TTL_BARS) -> _Path:
    """Walk the bars from the entry under one exit rule and report where the position left.

    THE TIE-BREAK IS PESSIMISTIC AND IT IS THE ONLY DEFENSIBLE ONE. When a bar's range covers both
    the stop and the target, H1 bars cannot say which printed first, and a counterfactual world
    that guesses "target" on every such bar manufactures exactly the alpha it is supposed to
    measure. So the stop is taken. The same rule governs the trail (the trailing level is computed
    from the extreme through the PREVIOUS bar, never the one being tested) and the partial (the
    bank is only credited when the +R was reached on a bar the stop did not also cover).

    Not `libs.validation.replay2`: that replay needs a desk-side `Signal` and a DataFrame, and it
    has no vocabulary for trail, partial or hold-to-ttl, which are three of the four arms here.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return _Path(entry, "no_risk", 0, 0.0)
    last = min(entry_idx + ttl, len(bars) - 1)
    extreme = entry
    banked = 0.0
    bank_done = False
    live_stop = stop
    for j in range(entry_idx, last + 1):
        b = bars[j]
        held = j - entry_idx
        if rule == "trail" and j > entry_idx:
            trail_level = extreme - direction * TRAIL_R * risk
            live_stop = max(live_stop, trail_level) if direction > 0 else min(live_stop,
                                                                             trail_level)
        stop_hit = (b.low <= live_stop) if direction > 0 else (b.high >= live_stop)
        if stop_hit:
            r = ((live_stop - entry) * direction) / risk
            if bank_done:
                r = PARTIAL_FRACTION * PARTIAL_AT_R + (1.0 - PARTIAL_FRACTION) * r
            return _Path(live_stop, "trail_stop" if rule == "trail" else "stop", held, r)
        if rule == "partial" and not bank_done:
            bank_level = entry + direction * PARTIAL_AT_R * risk
            reached = (b.high >= bank_level) if direction > 0 else (b.low <= bank_level)
            if reached:
                bank_done, banked = True, PARTIAL_AT_R
                live_stop = entry  # the runner's stop to break-even: `Signal.bank_protect_k = 0`
        if target is not None and rule in ("fixed_tp", "partial"):
            tgt_hit = (b.high >= target) if direction > 0 else (b.low <= target)
            if tgt_hit:
                r = ((target - entry) * direction) / risk
                if bank_done:
                    r = PARTIAL_FRACTION * banked + (1.0 - PARTIAL_FRACTION) * r
                return _Path(target, "target", held, r)
        extreme = max(extreme, b.high) if direction > 0 else min(extreme, b.low)
    px = bars[last].close
    r = ((px - entry) * direction) / risk
    if bank_done:
        r = PARTIAL_FRACTION * banked + (1.0 - PARTIAL_FRACTION) * r
    return _Path(px, "ttl", last - entry_idx, r)


@dataclass(frozen=True)
class _Arm:
    """One priced alternative: what it made, and what it cost to be wrong about."""

    cls: str
    arm: str
    status: str
    r: float | None
    d_r: float | None
    d_elog: float | None
    detail: dict[str, Any]

    def to_row(self) -> dict[str, Any]:
        return {"class": self.cls, "arm": self.arm, "status": self.status, "r": _r(self.r, 5),
                "d_r": _r(self.d_r, 5), "d_elog": _r(self.d_elog, 9), **self.detail}


def _elog(r: float, f: float, size: float) -> float:
    """log-wealth of one trade at risk fraction `f` and size multiple `size`. Non-linear on
    purpose: it is why 1.5x on a loser costs more than 1.5x on a winner gains."""
    return math.log(max(1.0 + f * size * r, RUIN_FLOOR))


def _entry_of(bars: Sequence[Bar], i0: int, direction: int, is_bracket: bool, level: float,
              cost: CostModel, execution: str) -> tuple[int, float, str] | None:
    """Where each execution arm would have got on, and at what price.

    market   a resting bracket fills the moment its level prints; an immediate order fills at the
             next bar's open. Both cross: half the spread plus the modelled slip.
    limit    the same signal one stated distance BETTER, filled only if the market came back for
             it inside the live window. Crosses nothing.
    delayed  the market arm, DELAY_BARS later, at that bar's open and at market cost.
    """
    window = i0 + 1 + BRACKET_LIVE_BARS
    if is_bracket:
        j = _reach(bars, i0 + 1, window, direction, level)
        ref = level
    else:
        j = i0 + 1 if i0 + 1 < len(bars) else None
        ref = bars[j].open if j is not None else level
    if j is None:
        return None
    if execution == "limit":
        improved = ref - direction * LIMIT_OFFSET_SPREADS * cost.spread_frac * ref
        k = _improve(bars, j, window, direction, improved)
        if k is None:
            return None
        return k, improved, "limit_filled"
    if execution == "delayed":
        k = j + DELAY_BARS
        if k >= len(bars):
            return None
        px = bars[k].open
        return k, px + direction * cost.entry_cost_frac("market") * px, "delayed_open"
    return j, ref + direction * cost.entry_cost_frac("market") * ref, "market_fill"


def _price_path(bars: Sequence[Bar], i0: int, direction: int, is_bracket: bool, level: float,
                stop: float, target: float | None, cost: CostModel, execution: str,
                exit_rule: str) -> tuple[float, dict[str, Any]] | None:
    """One arm end to end: get on, run the bars, get off, and charge the round trip in R.

    The R denominator is the DECISION's own stated risk |level - stop|, identical for every arm,
    so a cheaper entry shows up as more R rather than as a rescaled axis nobody can add up.
    """
    risk = abs(level - stop)
    if risk <= 0:
        return None
    got = _entry_of(bars, i0, direction, is_bracket, level, cost, execution)
    if got is None:
        return None
    j, entry, how = got
    path = _run(bars, j, direction, entry, stop, target, exit_rule)
    exit_px = path.exit_price * (1.0 - direction * cost.exit_cost_frac())
    r = ((exit_px - entry) * direction) / risk - cost.commission_frac * level / risk
    return r, {"entry": _r(entry, 6), "entry_bar": j, "how": how, "exit": _r(exit_px, 6),
               "exit_reason": path.reason, "bars_held": path.bars_held}


# --------------------------------------------------------------------------- pricing one row
def _direction_of(side: str) -> int:
    s = str(side or "").lower()
    if s.startswith("buy"):
        return 1
    if s.startswith("sell"):
        return -1
    return 0


def _risk_fraction(row: Mapping[str, Any], override: float | None) -> tuple[float, str]:
    """The sleeve's fraction of wealth at that minute -- the allocator's own `h` off the world
    state when the dataset carried one, else the stated fallback, named on the row."""
    if override is not None and override > 0:
        return override, "caller"
    h = _f(_d(_d(row.get("world_state")).get("allocator")).get("h"))
    if h is not None and h > 0:
        return h, "pf_forecast_log book h"
    return DEFAULT_RISK_FRACTION, f"default {DEFAULT_RISK_FRACTION:g} (no allocator h on the row)"


def price_row(row: Mapping[str, Any], bars: Sequence[Bar], cost: CostModel, *,
              risk_fraction: float | None = None) -> dict[str, Any]:
    """Every alternative to one decision, priced on the bars around it.

    Returns the block the dataset row carries as `counterfactual_outcomes`: the cost model that
    priced it, the replayed baseline of what the desk actually did, and one entry per arm with
    its R, its delta in R and its delta in log-wealth. A row that cannot be priced says which of
    UNPRICED (no bracket, no stop, no side), NO_BARS (the tape does not cover the minute yet) or
    NOT_TRIGGERED (the market never offered the entry) it is, and enters no class at all.
    """
    chosen = _d(row.get("chosen_action"))
    outcome = _d(row.get("outcome"))
    side = str(row.get("side") or chosen.get("side") or "")
    direction = _direction_of(side)
    level = _f(chosen.get("price"))
    stop = _f(chosen.get("sl"))
    target = _f(chosen.get("tp"))
    minute = _ts(row.get("minute"))
    taken = str(chosen.get("kind") or "") == "enter" or bool(outcome.get("status") == "RESOLVED")
    size0 = _f(chosen.get("size_mult"))
    size0 = size0 if size0 is not None and size0 > 0 else 1.0
    f, f_src = _risk_fraction(row, risk_fraction)
    head: dict[str, Any] = {"pricer_version": PRICER_VERSION, "cost_model": cost.to_row(),
                            "risk_fraction": _r(f, 8), "risk_fraction_source": f_src,
                            "chosen_size_mult": size0, "taken": taken,
                            "limit_offset_spreads": LIMIT_OFFSET_SPREADS,
                            "delay_bars": DELAY_BARS, "ttl_bars": TTL_BARS}
    if direction == 0 or level is None or stop is None or abs(level - stop) <= 0:
        return {**head, "status": UNPRICED, "alternatives": [],
                "why": "the decision row carries no side, no bracket level or no stop: there is "
                       "nothing to replay and a fabricated stop would fabricate every R below"}
    if minute is None or not bars:
        return {**head, "status": NO_BARS, "alternatives": [],
                "why": "no bars for this symbol on this host, or the decision has no minute"}
    i0 = _locate(bars, minute)
    if i0 is None or i0 + 1 >= len(bars):
        return {**head, "status": NO_BARS, "alternatives": [],
                "why": f"the tape does not reach the decision minute {minute.isoformat()}"}
    if i0 + 1 + TTL_BARS >= len(bars):
        return {**head, "status": NO_BARS, "alternatives": [],
                "why": (f"only {len(bars) - i0 - 1} bars after the decision, need "
                        f"{TTL_BARS + 1} to run a position to its time exit -- PENDING, not zero")}

    is_bracket = side.lower().endswith("_stop")
    base = _price_path(bars, i0, direction, is_bracket, level, stop, target, cost,
                       "market", "fixed_tp")
    if base is None:
        return {**head, "status": NOT_TRIGGERED, "alternatives": [],
                "why": ("the market never reached the entry inside the live window: a veto of a "
                        "trade the market did not offer has no P&L in either direction, and "
                        "counting it as zero would drag every filter toward harmless")}
    r_base, base_detail = base
    distance = abs(level - bars[i0].close) / level if level else 0.0
    head["p_fill_model"] = _r(cost.p_fill(distance), 6)
    head["baseline"] = {"r": _r(r_base, 5), **base_detail}
    r_realised = _f(outcome.get("r_multiple"))
    if r_realised is not None:
        head["r_realised"] = _r(r_realised, 5)
        head["replay_error_r"] = _r(r_realised - r_base, 5)

    elog_chosen = _elog(r_base, f, size0) if taken else 0.0
    r_chosen = r_base if taken else 0.0
    head["chosen"] = {"r": _r(r_chosen, 5), "elog": _r(elog_chosen, 9),
                      "exit_rule": str(chosen.get("exit_rule") or "fixed_tp"),
                      "execution": str(chosen.get("execution") or
                                       ("pending_stop" if is_bracket else "market"))}
    arms: list[_Arm] = []

    def add(cls: str, name: str, r: float | None, size: float, detail: dict[str, Any],
            status: str = PRICED) -> None:
        if r is None:
            arms.append(_Arm(cls, name, status, None, None, None, detail))
            return
        e = _elog(r, f, size)
        arms.append(_Arm(cls, name, PRICED, r, r - r_chosen, e - elog_chosen, detail))

    # ---- trade / no-trade. Both directions of the same question, because a desk that only ever
    # asks "what did I miss" learns nothing from the trades it should not have taken.
    if taken:
        add("MISSED_TRADE_ALPHA", "skipped", 0.0, size0,
            {"note": "flat instead: positive means the desk should not have traded this"})
    else:
        add("MISSED_TRADE_ALPHA", "entered", r_base, 1.0,
            {"note": "the desk's own bracket at 1.0x: positive is money the skip left behind",
             **base_detail})
        reason = str(chosen.get("veto_reason") or chosen.get("reason") or "unnamed")
        add("VETO_ALPHA", reason, r_base, 1.0, {"veto_reason": reason, **base_detail})

    if taken:
        for m in SIZE_ARMS:
            add("SIZING_ALPHA", f"{m:.1f}x", r_base, m,
                {"size_mult": m, "vs_chosen": _r(m / size0, 4)})
        for ex in EXECUTION_ARMS:
            got = _price_path(bars, i0, direction, is_bracket, level, stop, target, cost, ex,
                              "fixed_tp")
            if got is None:
                arms.append(_Arm("EXECUTION_ALPHA", ex, NOT_TRIGGERED, None, None, None,
                                 {"why": "this execution never got on inside the live window"}))
                continue
            add("EXECUTION_ALPHA", ex, got[0], size0, got[1])
        for xr in EXIT_ARMS:
            got = _price_path(bars, i0, direction, is_bracket, level, stop, target, cost,
                              "market", xr)
            if got is None:
                arms.append(_Arm("EXIT_ALPHA", xr, NOT_TRIGGERED, None, None, None,
                                 {"why": "the entry never filled, so no exit rule applies"}))
                continue
            add("EXIT_ALPHA", xr, got[0], size0, got[1])

    priced = [a for a in arms if a.d_elog is not None]
    best = max(priced, key=lambda a: a.d_elog or 0.0) if priced else None
    return {**head, "status": PRICED, "alternatives": [a.to_row() for a in arms],
            "n_arms": len(arms),
            "best_alternative": ({"class": best.cls, "arm": best.arm,
                                  "d_elog": _r(best.d_elog, 9)} if best is not None else None),
            "abs_d_elog_max": _r(max((abs(a.d_elog or 0.0) for a in priced), default=0.0), 9)}


# --------------------------------------------------------------------------- aggregation
def _stat(values: Sequence[float], min_n: int) -> dict[str, Any]:
    """n, mean, and a 95% interval on the mean -- or n alone. The interval is normal rather than
    Student's because scipy is not a dependency of this module; at MIN_N it is a few per cent
    narrow, which is why MIN_N is a floor on believing a class at all and not a licence."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "ci95": None, "sd": None, "status": UNMEASURED}
    mean = sum(values) / n
    if n < min_n:
        return {"n": n, "mean": None, "ci95": None, "sd": None, "status": UNMEASURED,
                "why": f"{n} priced decisions, need {min_n}"}
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    se = sd / math.sqrt(n) if n else 0.0
    return {"n": n, "mean": _r(mean, 9), "ci95": [_r(mean - Z95 * se, 9), _r(mean + Z95 * se, 9)],
            "sd": _r(sd, 9), "status": MEASURED}


def _blocks(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The counterfactual block off a dataset row, or the block itself -- callers hold both."""
    out: list[dict[str, Any]] = []
    for r in rows:
        blk = _d(r.get("counterfactual_outcomes")) if "counterfactual_outcomes" in r else _d(r)
        if blk:
            out.append(blk)
    return out


def aggregate(rows: Iterable[Mapping[str, Any]], *, min_n: int = MIN_N,
              min_n_veto: int = MIN_N_VETO) -> dict[str, Any]:
    """The five alpha classes from priced rows, each arm with its n and its interval.

    Sign, once more, because it is the only thing a reader can get wrong: every mean is the
    ALTERNATIVE minus the DESK, so positive is a bill and negative is the desk being right. A
    class under `min_n` is UNMEASURED with its n and nothing else, and a class that reads
    negative is reported exactly as prominently as one that reads positive.
    """
    blocks = _blocks(rows)
    per_arm: dict[tuple[str, str], list[float]] = {}
    per_arm_r: dict[tuple[str, str], list[float]] = {}
    statuses: dict[str, int] = {}
    sources: dict[str, int] = {}
    for blk in blocks:
        statuses[str(blk.get("status"))] = statuses.get(str(blk.get("status")), 0) + 1
        src = str(_d(blk.get("cost_model")).get("source") or "unknown")
        sources[src] = sources.get(src, 0) + 1
        if str(blk.get("status")) != PRICED:
            continue
        for a in blk.get("alternatives") or []:
            if not isinstance(a, Mapping):
                continue
            de, dr = _f(a.get("d_elog")), _f(a.get("d_r"))
            if de is None:
                continue
            key = (str(a.get("class")), str(a.get("arm")))
            per_arm.setdefault(key, []).append(de)
            if dr is not None:
                per_arm_r.setdefault(key, []).append(dr)

    out: dict[str, Any] = {
        "pricer_version": PRICER_VERSION, "n_rows": len(blocks),
        "n_priced": statuses.get(PRICED, 0), "row_status": dict(sorted(statuses.items())),
        "cost_model_sources": dict(sorted(sources.items())),
        "min_n": min_n, "min_n_veto": min_n_veto,
        "sign": ("every mean is the ALTERNATIVE minus the DESK: positive means the road not "
                 "taken was better and the desk's choice cost growth; negative means the desk "
                 "was right. VETO_ALPHA additionally carries the rail's own sign "
                 "(mean_avoided_r / filter_value_r), positive when the veto SAVED money"),
        "unit": "log-wealth per decision at the sleeve's risk fraction",
    }
    for cls in ALPHA_CLASSES:
        arms = {arm: _stat(vals, min_n_veto if cls == "VETO_ALPHA" else min_n)
                for (c, arm), vals in sorted(per_arm.items()) if c == cls}
        for (c, arm), vals in per_arm_r.items():
            if c != cls or arm not in arms:
                continue
            n = len(vals)
            total = sum(vals)
            mean = total / n if n else 0.0
            arms[arm]["mean_d_r"] = _r(mean, 5)
            if cls == "VETO_ALPHA":
                # The rail's own vocabulary, under the names `missed_growth.measure_veto` and
                # `counterfactual_markout` already read, so the rail needs no translation layer.
                sd = (math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0)
                se = sd / math.sqrt(n) if n else 0.0
                arms[arm].update({
                    "n_vetoed_and_triggered": n, "filter_value_r": _r(-total, 3),
                    "mean_avoided_r": _r(-mean, 4),
                    "t": (_r(-mean / se, 2) if se > 0 else None),
                    "verdict": _veto_verdict(-mean, se, n, min_n_veto)})
        pooled = [v for (c, _a), vals in per_arm.items() if c == cls for v in vals]
        head = _headline(cls, arms)
        out[cls] = {"arms": arms, "n": len(pooled), "pooled": _stat(pooled, min_n),
                    "alpha": head[0], "status": head[1], "reads": head[2]}
    return out


def _veto_verdict(avoided: float, se: float, n: int, min_n: int) -> str:
    """`counterfactual_markout`'s own thresholds, so a rail reading either report gets one answer:
    a veto EARNS_ITS_PLACE when what it avoided is positive at t > 2 on at least `min_n` triggered
    brackets, COSTS_EDGE on the same evidence in the other direction, UNDETERMINED otherwise."""
    if n < min_n or se <= 0:
        return "UNDETERMINED"
    t = avoided / se
    if avoided > 0 and t > 2.0:
        return "EARNS_ITS_PLACE"
    if avoided < 0 and -t > 2.0:
        return "COSTS_EDGE"
    return "UNDETERMINED"


#: The arm whose number IS the class's headline. Sizing, execution and exit have no single arm --
#: the class is a menu -- so the headline is the best-reading arm and the table beside it is the
#: answer; trade/no-trade and the vetoes have one arm each and the headline is that arm.
_HEADLINE_ARM: Mapping[str, str] = {
    "MISSED_TRADE_ALPHA": "entered",
}


def _headline(cls: str, arms: Mapping[str, Mapping[str, Any]]) -> tuple[float | None, str, str]:
    """(alpha, status, what it reads as) for one class."""
    want = _HEADLINE_ARM.get(cls)
    if want is not None:
        row = arms.get(want)
        if row is None:
            return None, UNMEASURED, f"no `{want}` arm priced yet"
        mean = _f(row.get("mean"))
        if row.get("status") != MEASURED or mean is None:
            return None, UNMEASURED, str(row.get("why") or f"{row.get('n', 0)} priced decisions")
        return mean, MEASURED, ("the desk's skips cost growth" if mean > 0 else
                                "the desk's skips saved growth")
    best: tuple[str, float] | None = None
    for arm, row in arms.items():
        mean = _f(row.get("mean"))
        if row.get("status") != MEASURED or mean is None:
            continue
        if best is None or mean > best[1]:
            best = (arm, mean)
    if best is None:
        return None, UNMEASURED, f"no arm of {cls} reached its sample floor"
    if cls == "VETO_ALPHA":
        return best[1], MEASURED, (
            f"`{best[0]}` is the veto with the largest bill: the trades it refused would have "
            "added growth" if best[1] > 0 else
            f"every measured veto saved growth; `{best[0]}` saved the least")
    return best[1], MEASURED, (f"`{best[0]}` would have beaten the desk" if best[1] > 0 else
                               f"the desk beat every arm; `{best[0]}` came closest")


def top_decisions(rows: Iterable[Mapping[str, Any]], k: int = 20) -> list[dict[str, Any]]:
    """The k decisions with the largest |dElog| across their arms -- where the desk's behaviour
    actually moved money, in either direction. Identity comes off the dataset row, so this takes
    full rows rather than the blocks `aggregate` will also accept."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        blk = _d(r.get("counterfactual_outcomes"))
        if str(blk.get("status")) != PRICED:
            continue
        best = _d(blk.get("best_alternative"))
        mag = _f(blk.get("abs_d_elog_max")) or 0.0
        if mag <= 0:
            continue
        scored.append((mag, {
            "row_id": r.get("row_id"), "minute": r.get("minute"), "symbol": r.get("symbol"),
            "sleeve": r.get("sleeve"), "side": r.get("side"),
            "chosen": _d(r.get("chosen_action")).get("kind"),
            "veto_reason": _d(r.get("chosen_action")).get("veto_reason"),
            "baseline_r": _d(blk.get("baseline")).get("r"),
            "best_class": best.get("class"), "best_arm": best.get("arm"),
            "best_d_elog": best.get("d_elog"), "abs_d_elog_max": _r(mag, 9),
            "cost_model": _d(blk.get("cost_model")).get("source")}))
    scored.sort(key=lambda s: -s[0])
    return [row for _m, row in scored[:max(k, 0)]]
