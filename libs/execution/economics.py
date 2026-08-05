"""DAILY EXECUTION ECONOMICS -- the arithmetic behind ``scripts/run_execution_economics.py``.

WHY THIS EXISTS. The desk already measures every PIECE of its execution cost and has never once
added them up on one page: ``run_trade_forensics`` charges the FUTURES commission the venue billed
(and says in its own scope string that spot-leg fees are invisible, so every number it publishes is
a LOWER BOUND -- R0027); ``run_reality_gap._cost_link`` compares a modelled cost to a realised one
at the desk level with no per-symbol breakdown; ``carry_accounting.attribute_non_funding`` computes
an UNEXPLAINED residual whose own docstring says it "deserves a page" while nothing pages on it;
``fill_quality_monitor`` measures maker share. Five instruments, no ledger. The 2026-07 fee fire
($1,750 of commission against ~$126 of logged round-trips) was visible in all five and named by
none, because the question "what did the desk actually net, and where did the rest go" was never
asked as one arithmetic.

THE ONE RULE THIS MODULE IS BUILT AROUND: **a zero in an execution report is a claim that money did
not move.** Every quantity here is ``float | None``; ``None`` renders as ``NOT-READABLE-HERE`` and
NEVER as ``0.0``. An absent artifact, a dead venue read and an unparseable field all collapse to
``None`` on purpose -- the caller's only honest question is "did this measure or not", and a
partially-parsed number is not a measurement (the same doctrine as ``carry_accounting.read_income``,
whose swallowed HTTP 502 published a $0.00 harvest against a ground truth of $101.96).

DIRECTION OF EVERY BOUND. Costs are ``positive means WE PAID`` throughout, matching the executor's
``_tca`` and ``binance_testnet.commission_events``. When a COST term is unmeasured the net is
published as an **UPPER BOUND** (``net_status="UPPER-BOUND"``): an omitted cost can only make the
true net worse, never better. When the funding harvest itself is unmeasured the net is not
published at all -- there is nothing to bound it against.

NO THRESHOLD IS MINTED HERE. The bands this module applies are PARAMETERS, without defaults, so a
caller physically cannot invoke it while inventing a number: the cost bands come from
``run_reality_gap`` (1.5x GAP / 3.0x BREAK), the minimum hold and the round-trip default come from
``run_cashcarry_executor``, and the residual's defect bar comes from ``carry_bleed_report``'s own
``alert_frac``. ``read_source_constant`` is how the first two are READ rather than re-declared.

Pure and dependency-light on purpose (stdlib + ``carry_accounting``): no venue clients, no network,
no argv, so the tests can build every state by hand and a read-only monitor can import it.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from libs.execution.carry_accounting import carry_bleed_report

#: The ONE string this desk uses for "the input for this row is not present on this machine".
#: Deliberately not "0", not "-", not "n/a": it names the READER's state, not the money's.
NOT_READABLE = "NOT-READABLE-HERE"

#: Term/section status vocabulary. Exactly two states, because there are exactly two questions:
#: did we measure it (MEASURED) or did we not (UNMEASURED). Nuance -- partial coverage, a bound
#: that is only one-sided -- rides on `Term.bound` / `Term.coverage`, never on the status word.
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: How a measured number relates to the truth it stands for.
EXACT = "EXACT"
LOWER_BOUND = "LOWER-BOUND"     # the true cost is at least this
UPPER_BOUND = "UPPER-BOUND"     # the true net is at most this


# ---------------------------------------------------------------------------------------------
# Reading a constant OUT OF ITS OWNER, instead of copying it
# ---------------------------------------------------------------------------------------------
def read_source_constant(path: Path, name: str) -> float | None:
    """The value of a module-level numeric constant, read from `path`'s SOURCE. None if absent.

    THE ALTERNATIVE IS A SECOND COPY OF A THRESHOLD, and two copies of one threshold is how a desk
    ends up with two answers to one question (the exact failure `libs/execution/leg_modes` was
    extracted to end). This report has to apply `run_reality_gap`'s cost bands and the executor's
    minimum hold; copying either would mean a future tightening of the gate silently leaves this
    report loosened.

    Source text rather than `import`, for two reasons that both matter on the money path:
      * `run_cashcarry_executor` is a 2,000-line ORDER-PLACING module. Importing it to read one
        float pulls in every venue client it touches; a reporting organ must not be able to reach
        the order path even by accident.
      * a repo-relative source read fails LOUD and locally. If the constant is renamed or moved,
        this returns None and the section that needed it reads NOT-READABLE-HERE -- it does not
        fall back to a plausible number, which is the only failure mode worth engineering against.

    Handles `X = 24.0` and `X = -0.0005` (a negated literal is an ast.UnaryOp, not a Constant).
    """
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:                      # MODULE level only -- a nested constant is
        if not isinstance(node, ast.Assign):    # not the module's published threshold
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        val = node.value
        if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
            inner = val.operand
            if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)):
                return -float(inner.value)
            return None
        if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)) \
                and not isinstance(val.value, bool):
            return float(val.value)
        return None
    return None


def bleed_alert_frac() -> float | None:
    """`carry_bleed_report`'s own `alert_frac` -- the desk's existing "this leak is a defect" bar.

    READ from the function signature, never restated. The residual is a component of exactly the
    leak that alarm polices, so a residual defect bar that disagreed with it would mean the desk
    holds two opinions about how much unexplained money is too much.
    """
    default = inspect.signature(carry_bleed_report).parameters["alert_frac"].default
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        return None
    return float(default)


# ---------------------------------------------------------------------------------------------
# Terms of the net-APR decomposition
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Term:
    """One line of the net-APR decomposition, with its provenance attached to the number.

    `usd` is None for every unmeasured term, and `as_dict` renders that as NOT-READABLE-HERE. A
    Term cannot be constructed in a state where a reader would mistake "we could not look" for
    "it was zero", because the value and the status travel together.
    """

    name: str
    usd: float | None
    status: str                      # MEASURED | UNMEASURED
    source: str                      # WHERE the number came from, precisely enough to re-read it
    bound: str = EXACT               # EXACT | LOWER-BOUND (see module docstring)
    coverage: float | None = None    # share of the window's trips this term could actually see
    note: str = ""

    @property
    def measured(self) -> bool:
        return self.status == MEASURED and self.usd is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "term": self.name,
            "usd": None if self.usd is None else round(self.usd, 4),
            "reads": NOT_READABLE if self.usd is None else round(self.usd, 2),
            "status": self.status,
            "bound": self.bound,
            "coverage": self.coverage,
            "source": self.source,
            "note": self.note,
        }


def unmeasured_term(name: str, source: str, note: str) -> Term:
    """A term whose input is absent HERE. The only constructor for a missing number."""
    return Term(name=name, usd=None, status=UNMEASURED, source=source, note=note)


@dataclass(frozen=True)
class Decomposition:
    """Gross funding, minus every cost the desk can see, equals net -- with the holes named."""

    terms: tuple[Term, ...]
    net_usd: float | None
    net_status: str                  # MEASURED | UPPER-BOUND | UNMEASURED
    net_bps_of_capital: float | None
    net_apr_pct: float | None
    capital_usd: float | None
    capital_source: str
    window_days: float
    unmeasured_terms: tuple[str, ...]
    funding_split_crosscheck: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "terms": [t.as_dict() for t in self.terms],
            "net_usd": None if self.net_usd is None else round(self.net_usd, 4),
            "net_reads": NOT_READABLE if self.net_usd is None else round(self.net_usd, 2),
            "net_status": self.net_status,
            "net_bps_of_capital": (None if self.net_bps_of_capital is None
                                   else round(self.net_bps_of_capital, 3)),
            "net_apr_pct": None if self.net_apr_pct is None else round(self.net_apr_pct, 4),
            "net_apr_reads": (NOT_READABLE if self.net_apr_pct is None
                              else f"{self.net_apr_pct:.2f}%"),
            "capital_usd": None if self.capital_usd is None else round(self.capital_usd, 2),
            "capital_source": self.capital_source,
            "unmeasured_terms": list(self.unmeasured_terms),
            "funding_split_crosscheck": self.funding_split_crosscheck,
        }


def build_decomposition(
    *,
    gross_funding: Term,
    funding_paid: Term,
    futures_commission: Term,
    spot_commission: Term,
    slippage: Term,
    funding_net_fallback: Term,
    capital_usd: float | None,
    capital_source: str,
    window_days: float,
) -> Decomposition:
    """NET = gross funding captured - futures comm - SPOT comm - slippage - funding paid.

    SIGNS. Every argument except `gross_funding` is POSITIVE-MEANS-PAID, the convention the
    executor's `_tca` and `binance_testnet.commission_events` already use, so the arithmetic is a
    plain subtraction and a favourable fill (negative slippage) is a credit rather than a special
    case.

    THE FUNDING SPLIT IS OPTIONAL, THE FUNDING TERM IS NOT. `income_summary` publishes only the NET
    funding (it sums signed FUNDING_FEE rows), so the gross-captured / paid split needs row-level
    access that can fail on its own. When both halves read, they are used and cross-checked against
    the net; when they do not, `funding_net_fallback` carries the harvest as one measured term and
    the two halves publish NOT-READABLE-HERE. Losing the SPLIT must not cost the desk the NET.

    WHY AN UNMEASURED COST DOES NOT KILL THE NET. It bounds it. Every term here is a cost except
    the harvest, so an omitted term can only make the true net smaller -- the published figure is
    then an UPPER BOUND, labelled as one, and the missing terms are named in `unmeasured_terms`.
    That is strictly more useful than refusing to answer AND strictly honest, because the bound
    points the same way as the desk's own tighten-only rule. An unmeasured HARVEST is different:
    it bounds nothing, so `net_status` is UNMEASURED and `net_usd` is None.
    """
    split_ok = gross_funding.measured and funding_paid.measured
    if split_ok:
        harvest_terms: tuple[Term, ...] = (gross_funding, funding_paid)
        # mypy 2.1: `.measured` cannot narrow the attribute, so re-assert the Optionals explicitly.
        g, p = gross_funding.usd, funding_paid.usd
        harvest = (g - p) if (g is not None and p is not None) else None
        crosscheck = _crosscheck_split(harvest, funding_net_fallback)
    else:
        why = ("row-level FUNDING_FEE split unavailable -- the venue's income_summary nets "
               "received against paid, so the harvest is carried whole")
        harvest_terms = (
            unmeasured_term(gross_funding.name, gross_funding.source, why),
            unmeasured_term(funding_paid.name, funding_paid.source, why),
        )
        harvest = funding_net_fallback.usd if funding_net_fallback.measured else None
        crosscheck = ("split UNMEASURED -- net funding used whole"
                      if funding_net_fallback.measured else f"{NOT_READABLE}: no funding read")

    cost_terms = (futures_commission, spot_commission, slippage)
    terms = (*harvest_terms, *cost_terms) if split_ok else (
        *harvest_terms, funding_net_fallback, *cost_terms)

    unmeasured = tuple(t.name for t in terms if not t.measured)

    if harvest is None:
        return Decomposition(
            terms=terms, net_usd=None, net_status=UNMEASURED, net_bps_of_capital=None,
            net_apr_pct=None, capital_usd=capital_usd, capital_source=capital_source,
            window_days=window_days, unmeasured_terms=unmeasured,
            funding_split_crosscheck=crosscheck)

    costs = 0.0
    missing_cost = False
    for t in cost_terms:
        if t.measured and t.usd is not None:
            costs += t.usd
        else:
            missing_cost = True
    # A measured term that is itself a LOWER BOUND (spot fees the venue reports in an asset we
    # cannot value, slippage on rows that carry no mid) leaves the net an UPPER BOUND too.
    bounded = any(t.measured and t.bound == LOWER_BOUND for t in cost_terms)
    net = harvest - costs
    status = UPPER_BOUND if (missing_cost or bounded) else MEASURED

    bps = apr = None
    if capital_usd is not None and capital_usd > 0.0 and window_days > 0.0:
        bps = 1e4 * net / capital_usd
        apr = 100.0 * (net / capital_usd) * (365.0 / window_days)
    return Decomposition(
        terms=terms, net_usd=net, net_status=status, net_bps_of_capital=bps, net_apr_pct=apr,
        capital_usd=capital_usd, capital_source=capital_source, window_days=window_days,
        unmeasured_terms=unmeasured, funding_split_crosscheck=crosscheck)


def _crosscheck_split(harvest: float | None, net_term: Term) -> str:
    """Does gross-minus-paid agree with the venue's own netted funding figure?

    Two independent reads of one fact, so disagreement is information: it means the row-level
    pagination dropped rows the aggregate kept (the 2026-07-26 truncation class) or vice versa.
    Reported, never silently reconciled.
    """
    if harvest is None or not net_term.measured or net_term.usd is None:
        return f"{NOT_READABLE}: only one of the two funding reads is available"
    delta = harvest - net_term.usd
    if abs(delta) <= 0.01:
        return f"OK: split ({harvest:+.2f}) matches income_summary net ({net_term.usd:+.2f})"
    return (f"DISAGREE by {delta:+.2f}: FUNDING_FEE rows sum to {harvest:+.2f} but "
            f"income_summary nets {net_term.usd:+.2f} -- one of the two reads is truncated")


# ---------------------------------------------------------------------------------------------
# The tape, parsed into round trips
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Trip:
    """One closed carry round trip, as the executor's own `_log_trade` close record describes it."""

    symbol: str
    opened: datetime | None
    closed: datetime | None
    held_h: float | None
    notional: float | None
    funding_rate: float | None
    #: signed spot+fut slippage, POSITIVE MEANS WE PAID (the `_tca` convention)
    slip_bps: float | None
    #: |spot| + |fut| -- the definition `run_cashcarry_executor._realised_rt_bps` gates on
    abs_slip_bps: float | None


def _dt(value: Any) -> datetime | None:
    """A timezone-AWARE datetime, or None. A naive stamp is REFUSED, not localised.

    The desk is timestamp-governed (8h funding boundaries, freshness SLAs); silently stamping UTC
    onto a naive value would make a mis-clocked writer's rows land in whatever window suits them.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    try:
        out = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo is not None else None


def _f(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_trips(rows: Iterable[dict[str, Any]]) -> list[Trip]:
    """Close events -> Trips. Rows that cannot be read are DROPPED, never defaulted to zero."""
    out: list[Trip] = []
    for r in rows:
        if r.get("event") != "close":
            continue
        sp, ft = _f(r.get("spot_slip_bps")), _f(r.get("fut_slip_bps"))
        # A leg with no recorded mid contributes nothing and makes the pair's cost unknowable;
        # requiring BOTH legs keeps a one-legged read from posing as a round-trip cost.
        signed = (sp + ft) if (sp is not None and ft is not None) else None
        absolute = (abs(sp) + abs(ft)) if (sp is not None and ft is not None) else None
        out.append(Trip(
            symbol=str(r.get("symbol") or ""),
            opened=_dt(r.get("opened")), closed=_dt(r.get("closed")),
            held_h=_f(r.get("held_hours")), notional=_f(r.get("notional")),
            funding_rate=_f(r.get("funding_rate")),
            slip_bps=signed, abs_slip_bps=absolute))
    return out


def in_window(trips: Sequence[Trip], start: datetime, end: datetime) -> list[Trip]:
    """Trips CLOSED inside [start, end]. A trip with no readable close stamp is excluded."""
    return [t for t in trips if t.closed is not None and start <= t.closed <= end]


def slippage_usd(trips: Sequence[Trip]) -> tuple[float | None, float | None]:
    """(signed slippage paid in USD, coverage). None when no trip in the window carries TCA.

    Coverage is the share of the window's trips whose fills carried both legs' mids. Anything
    under 1.0 makes the number a LOWER BOUND on what was really paid -- the uncovered trips did
    not cost nothing, they were not watched.
    """
    if not trips:
        return None, None
    usd = 0.0
    seen = 0
    for t in trips:
        if t.slip_bps is None or t.notional is None:
            continue
        seen += 1
        usd += t.notional * t.slip_bps / 1e4
    if seen == 0:
        return None, 0.0
    return usd, seen / len(trips)


def time_weighted_capital(trips: Sequence[Trip], start: datetime, end: datetime) -> float | None:
    """Average capital deployed across the window, from the tape's own open/close intervals.

    Sum of (notional x hours the trip overlapped the window) / window hours. None when nothing in
    the window carries both an interval and a notional.

    THIS IS A LOWER BOUND and the caller must treat it as one: positions still OPEN at the window's
    end never close inside it, so their capital is invisible here. A denominator that is too small
    INFLATES an APR, which is the loosening direction -- `capital_base` therefore takes the LARGER
    of this and the live book's deployed notional.
    """
    window_h = (end - start).total_seconds() / 3600.0
    if window_h <= 0.0:
        return None
    total = 0.0
    seen = False
    for t in trips:
        if t.notional is None or t.opened is None or t.closed is None:
            continue
        lo, hi = max(t.opened, start), min(t.closed, end)
        overlap = (hi - lo).total_seconds() / 3600.0
        if overlap <= 0.0:
            continue
        seen = True
        total += t.notional * overlap
    return (total / window_h) if seen else None


def capital_base(tape_twa: float | None, deployed_now: float | None) -> tuple[float | None, str]:
    """The APR denominator: the LARGER of the two readable capital measures, or None.

    MAX, never mean, and the direction is the whole argument. A bigger denominator can only SHRINK
    a reported return; picking the smaller one would let a half-readable tape publish a flattering
    APR. This is the same tighten-only rule the executor applies to `_rt_bps` (reality FLOORS the
    model, `max()` never average).
    """
    vals = [(v, src) for v, src in ((tape_twa, "tape time-weighted deployed notional"),
                                    (deployed_now, "live book deployed_notional"))
            if v is not None and v > 0.0]
    if not vals:
        return None, NOT_READABLE
    best = max(vals, key=lambda x: x[0])
    if len(vals) == 2:
        return best[0], f"max(tape TWA, live deployed) -> {best[1]}"
    return best[0], best[1]


# ---------------------------------------------------------------------------------------------
# 2. CHURN -- round trips per position per day against the hold the gate assumed
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ChurnRow:
    """Per-symbol churn: how often the desk paid to re-take a position it had just left."""

    symbol: str
    n_round_trips: int
    round_trips_per_day: float
    avg_hold_h: float | None
    min_hold_h: float
    short_hold_trips: int
    reopens_inside_min_hold: int
    funding_capture_horizon_h: float | None
    churn_cost_usd: float | None
    churn_cost_bps: float | None
    verdict: str                     # CHURN | OK | NOT-READABLE-HERE
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "round_trips": self.n_round_trips,
            "round_trips_per_day": round(self.round_trips_per_day, 3),
            "avg_hold_h": None if self.avg_hold_h is None else round(self.avg_hold_h, 2),
            "avg_hold_reads": (NOT_READABLE if self.avg_hold_h is None
                               else round(self.avg_hold_h, 2)),
            "gate_min_hold_h": self.min_hold_h,
            "short_hold_trips": self.short_hold_trips,
            "reopens_inside_min_hold": self.reopens_inside_min_hold,
            "funding_capture_horizon_h": (None if self.funding_capture_horizon_h is None
                                          else round(self.funding_capture_horizon_h, 2)),
            "churn_cost_usd": (None if self.churn_cost_usd is None
                               else round(self.churn_cost_usd, 2)),
            "churn_cost_bps": (None if self.churn_cost_bps is None
                               else round(self.churn_cost_bps, 2)),
            "churn_cost_reads": (NOT_READABLE if self.churn_cost_bps is None
                                 else round(self.churn_cost_bps, 2)),
            "verdict": self.verdict,
            "why": self.why,
        }


def funding_capture_horizon_h(rt_bps: float | None, funding_rate_8h: float | None) -> float | None:
    """Hours of funding needed to repay one round trip -- the horizon a hold must beat.

    The entry gate's own inequality (`_entry_gate`: funding * 1e4 * periods > rt_bps, periods in
    8h units) solved for time instead of for admission. A position re-opened more often than this
    is paying a round trip to stand still, which is the 2026-07 fee-fire SHAPE and the reason this
    number belongs on a daily page rather than in a post-mortem.

    None when funding at open was not positive: a carry with no premium never repays its round
    trip at any horizon, so there is no finite answer to publish (and an `inf` here would be
    rendered as a number by every downstream reader). None when the cost is unmeasured, likewise.
    """
    if rt_bps is None or funding_rate_8h is None or funding_rate_8h <= 0.0:
        return None
    return 8.0 * rt_bps / (funding_rate_8h * 1e4)


def _open_times(rows: Iterable[dict[str, Any]]) -> dict[str, list[datetime]]:
    """Per-symbol OPEN stamps. `topup` is excluded: adding to a held carry is not a re-entry."""
    out: dict[str, list[datetime]] = {}
    for r in rows:
        if r.get("event") != "open":
            continue
        when = _dt(r.get("opened"))
        if when is None:
            continue
        out.setdefault(str(r.get("symbol") or ""), []).append(when)
    for stamps in out.values():
        stamps.sort()
    return out


def reopen_gaps_h(closes: Sequence[Trip], opens: Sequence[datetime]) -> list[float]:
    """Hours from each close to the NEXT open of the same symbol. The re-entry interval."""
    gaps: list[float] = []
    ordered = sorted(opens)
    for trip in closes:
        if trip.closed is None:
            continue
        nxt = next((o for o in ordered if o > trip.closed), None)
        if nxt is None:
            continue
        gaps.append((nxt - trip.closed).total_seconds() / 3600.0)
    return gaps


def churn_report(
    rows: Sequence[dict[str, Any]],
    trips: Sequence[Trip],
    *,
    min_hold_h: float,
    window_days: float,
    default_rt_bps: float,
) -> list[ChurnRow]:
    """Per-symbol churn over the window. `min_hold_h` and `default_rt_bps` are READ from the
    executor by the caller -- this module declares neither.

    THREE INDEPENDENT WAYS A POSITION CAN BE CHURNING, all reported, any one of them enough:
      * `short_hold_trips` -- closed younger than the hold the entry gate priced the trade on.
        The gate spent a round trip on the assumption of `min_hold_h` of funding; a shorter hold
        means the desk bought something it then declined to collect.
      * `reopens_inside_min_hold` -- the SAME symbol re-opened less than `min_hold_h` after being
        closed. This is the churn-loop fingerprint proper: two round trips billed for one economic
        position, and it is invisible to any hold-length statistic because both holds can be long.
      * `avg_hold_h < funding_capture_horizon_h` -- the position is closed before its own funding
        has repaid its own round trip, whatever the gate assumed.

    COST. Charged as the realised round-trip slippage of the churning trips only (their |spot| +
    |fut| bps against their own notional), falling back to the executor's pessimistic
    `_DEFAULT_RT_BPS` for a trip whose TCA is absent -- the same fail-closed direction the gate
    uses for an unmeasured symbol. Fees are NOT included (spot commission is not visible per trip;
    R0027), so this cost is a LOWER BOUND on what churn really took.
    """
    opens = _open_times(rows)
    by_symbol: dict[str, list[Trip]] = {}
    for t in trips:
        by_symbol.setdefault(t.symbol, []).append(t)

    out: list[ChurnRow] = []
    for symbol in sorted(by_symbol):
        group = by_symbol[symbol]
        holds = [t.held_h for t in group if t.held_h is not None]
        avg_hold = (sum(holds) / len(holds)) if holds else None
        short = sum(1 for h in holds if h < min_hold_h)
        gaps = reopen_gaps_h(group, opens.get(symbol, []))
        reopens = sum(1 for g in gaps if g < min_hold_h)

        rts = [t.abs_slip_bps for t in group if t.abs_slip_bps is not None]
        rts.sort()
        median_rt = rts[len(rts) // 2] if rts else None
        fundings = [t.funding_rate for t in group if t.funding_rate is not None]
        median_fr = sorted(fundings)[len(fundings) // 2] if fundings else None
        horizon = funding_capture_horizon_h(median_rt, median_fr)

        churning = [t for t in group if t.held_h is not None and t.held_h < min_hold_h]
        cost_usd: float | None = None
        cost_bps: float | None = None
        notional_all = sum(t.notional for t in group if t.notional is not None)
        if churning:
            acc = 0.0
            for t in churning:
                if t.notional is None:
                    continue
                bps = t.abs_slip_bps if t.abs_slip_bps is not None else default_rt_bps
                acc += t.notional * bps / 1e4
            cost_usd = acc
            cost_bps = (1e4 * acc / notional_all) if notional_all > 0.0 else None

        horizon_breach = (avg_hold is not None and horizon is not None and avg_hold < horizon)
        reasons: list[str] = []
        if reopens:
            reasons.append(f"{reopens} re-open(s) within {min_hold_h:g}h of a close")
        if short:
            reasons.append(
                f"{short}/{len(group)} trip(s) held under the {min_hold_h:g}h gate floor")
        if horizon_breach and avg_hold is not None and horizon is not None:
            reasons.append(f"avg hold {avg_hold:.1f}h < {horizon:.1f}h funding-capture horizon")

        if avg_hold is None and not gaps:
            verdict, why = NOT_READABLE, "no readable hold or re-entry interval in the window"
        elif reasons:
            verdict = "CHURN"
            why = "; ".join(reasons) + " -- fees paid to stand still"
        else:
            verdict, why = "OK", (
                f"avg hold {avg_hold:.1f}h clears the {min_hold_h:g}h floor with no fast re-entry"
                if avg_hold is not None else "no fast re-entry observed")

        out.append(ChurnRow(
            symbol=symbol, n_round_trips=len(group),
            round_trips_per_day=(len(group) / window_days) if window_days > 0 else 0.0,
            avg_hold_h=avg_hold, min_hold_h=min_hold_h, short_hold_trips=short,
            reopens_inside_min_hold=reopens, funding_capture_horizon_h=horizon,
            churn_cost_usd=cost_usd, churn_cost_bps=cost_bps, verdict=verdict, why=why))
    return out


# ---------------------------------------------------------------------------------------------
# 3. COST-MODEL DRIFT -- realised round-trip bps vs data/cost_model.json, per symbol
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DriftRow:
    """One symbol's modelled-vs-realised round-trip cost, judged on run_reality_gap's bands."""

    symbol: str
    modelled_bps: float | None
    realised_bps: float | None
    n: int
    ratio: float | None
    verdict: str                     # OK | GAP | BREAK | NO-DATA
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "modelled_bps": None if self.modelled_bps is None else round(self.modelled_bps, 3),
            "modelled_reads": (NOT_READABLE if self.modelled_bps is None
                               else round(self.modelled_bps, 3)),
            "realised_bps": None if self.realised_bps is None else round(self.realised_bps, 3),
            "realised_reads": (NOT_READABLE if self.realised_bps is None
                               else round(self.realised_bps, 3)),
            "n_trips": self.n,
            "ratio": None if self.ratio is None else round(self.ratio, 3),
            "verdict": self.verdict,
            "detail": self.detail,
        }


def modelled_rt_bps(cost_model: Any, symbol: str, bucket: str = "500") -> float | None:
    """`data/cost_model.json` -> this symbol's modelled pair round-trip bps, or None.

    Reads the SAME path `run_cashcarry_executor._rt_bps` gates on
    (`symbols[sym]["pair"][bucket]["pair_roundtrip_bps"]`) so the drift measured here is drift in
    the number the gate actually used -- a report comparing against a different field of the same
    file would be measuring its own arithmetic.
    """
    if not isinstance(cost_model, dict):
        return None
    try:
        pair = cost_model["symbols"][symbol]["pair"][bucket]
    except (KeyError, TypeError, IndexError):
        return None
    return _f(pair.get("pair_roundtrip_bps")) if isinstance(pair, dict) else None


def realised_rt_bps(trips: Sequence[Trip], *, min_n: int) -> float | None:
    """Median realised round trip (|spot| + |fut| slippage bps), or None below `min_n` samples.

    MEDIAN and |.| both mirror `run_cashcarry_executor._realised_rt_bps` exactly: one catastrophic
    fill should cost a trade, not condemn a symbol, and a favourable leg must not net off an
    adverse one when the question is "what did the round trip cost to cross". `min_n` is the
    executor's own `_MIN_FILLS_FOR_REALISED`, read by the caller.
    """
    vals = sorted(t.abs_slip_bps for t in trips if t.abs_slip_bps is not None)
    if len(vals) < min_n:
        return None
    return vals[len(vals) // 2]


def drift_verdict(modelled: float | None, realised: float | None, *,
                  band: float, break_at: float) -> tuple[str, float | None, str]:
    """`run_reality_gap._cmp`'s ratio arithmetic, applied per symbol on the bands READ from it.

    Same three rules, deliberately not re-derived: a SIGN FLIP is always a BREAK whatever the
    magnitude, a ~0 upstream makes the ratio undefined (NO-DATA rather than a division), and
    otherwise the ratio is judged against `band` (GAP) and `break_at` (BREAK). The desk owns one
    definition of "the modelled and realised cost cannot describe the same strategy"; this applies
    it to a finer grain, it does not mint a second one.
    """
    if modelled is None or realised is None:
        missing = "modelled" if modelled is None else "realised"
        return "NO-DATA", None, f"{missing} cost {NOT_READABLE}"
    if modelled * realised < 0:
        return "BREAK", None, "SIGN FLIP -- modelled and realised disagree on direction"
    if abs(modelled) < 1e-9:
        return "NO-DATA", None, "modelled ~0, ratio undefined"
    ratio = realised / modelled
    if ratio > break_at or ratio < 1.0 / break_at:
        return "BREAK", ratio, f"realised is {ratio:.2f}x modelled (BREAK band {break_at:g}x)"
    if ratio > band or ratio < 1.0 / band:
        return "GAP", ratio, f"realised is {ratio:.2f}x modelled (GAP band {band:g}x)"
    return "OK", ratio, f"realised is {ratio:.2f}x modelled"


def cost_drift(trips: Sequence[Trip], cost_model: Any, *,
               band: float, break_at: float, min_n: int) -> list[DriftRow]:
    """Per-symbol modelled-vs-realised round-trip drift over the window."""
    by_symbol: dict[str, list[Trip]] = {}
    for t in trips:
        by_symbol.setdefault(t.symbol, []).append(t)
    out: list[DriftRow] = []
    for symbol in sorted(by_symbol):
        group = by_symbol[symbol]
        modelled = modelled_rt_bps(cost_model, symbol)
        realised = realised_rt_bps(group, min_n=min_n)
        verdict, ratio, detail = drift_verdict(modelled, realised, band=band, break_at=break_at)
        out.append(DriftRow(symbol=symbol, modelled_bps=modelled, realised_bps=realised,
                            n=len(group), ratio=ratio, verdict=verdict, detail=detail))
    return out


# ---------------------------------------------------------------------------------------------
# 4. THE UNEXPLAINED RESIDUAL -- promoted from footnote to first-class defect
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResidualReport:
    """`carry_accounting.attribute_non_funding`'s residual, with the page it never had."""

    residual_usd: float | None
    basis_usd: float | None
    fut_fees_usd: float | None
    funding_usd: float | None
    alert_frac: float | None
    threshold_usd: float | None
    verdict: str                     # DEFECT | OK | NOT-READABLE-HERE
    why: str
    scope: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "residual_usd": None if self.residual_usd is None else round(self.residual_usd, 2),
            "residual_reads": (NOT_READABLE if self.residual_usd is None
                               else round(self.residual_usd, 2)),
            "basis_usd": self.basis_usd,
            "fut_fees_usd": self.fut_fees_usd,
            "funding_usd": self.funding_usd,
            "defect_threshold_frac_of_harvest": self.alert_frac,
            "defect_threshold_usd": (None if self.threshold_usd is None
                                     else round(self.threshold_usd, 2)),
            "verdict": self.verdict,
            "why": self.why,
            "scope": self.scope,
        }


def residual_report(*, leak: Any, funding: float | None, alert_frac: float | None,
                    scope: str) -> ResidualReport:
    """Judge the residual against the desk's OWN leak bar -- no new threshold.

    `attribute_non_funding` splits the carry leak into basis, futures fees and a residual that is
    "everything neither explains: SPOT commission, slippage, and hedge-drift incidents", and its
    docstring says a large one "deserves a page". Nothing paged. This is that page.

    THE BAR IS BORROWED ON PURPOSE. `carry_bleed_report` already rules that a leak worth
    `alert_frac` of the funding harvest is an alarm; the residual is a COMPONENT of that same leak,
    so it is a DEFECT at the same fraction. Minting a second number here would let the desk hold
    two opinions about how much unexplained money is acceptable -- and the residual is the single
    most dangerous line in the report precisely because nobody can say what it is.

    NO HARVEST TO MEASURE AGAINST -> ANY non-zero residual is a defect, which is exactly what
    `carry_bleed_report` does when `funding <= 0` (it alarms on any drain at all). An unmeasured
    residual or an unmeasured harvest reads NOT-READABLE-HERE; neither is ever scored clean.
    """
    if not isinstance(leak, dict):
        return ResidualReport(
            residual_usd=None, basis_usd=None, fut_fees_usd=None, funding_usd=funding,
            alert_frac=alert_frac, threshold_usd=None, verdict=NOT_READABLE,
            why=("no leak_attribution available -- the executor publishes it only when BOTH the "
                 "non-funding PnL and the futures fee bill are measured"),
            scope=scope)
    residual = _f(leak.get("residual"))
    basis, fees = _f(leak.get("basis")), _f(leak.get("fut_fees"))
    if residual is None:
        return ResidualReport(
            residual_usd=None, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
            alert_frac=alert_frac, threshold_usd=None, verdict=NOT_READABLE,
            why="leak_attribution carries no readable residual", scope=scope)
    if alert_frac is None:
        return ResidualReport(
            residual_usd=residual, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
            alert_frac=None, threshold_usd=None, verdict=NOT_READABLE,
            why=("carry_bleed_report.alert_frac could not be read, so the desk's own defect bar "
                 "is unavailable -- refusing to invent one"),
            scope=scope)
    if funding is None:
        return ResidualReport(
            residual_usd=residual, basis_usd=basis, fut_fees_usd=fees, funding_usd=None,
            alert_frac=alert_frac, threshold_usd=None, verdict=NOT_READABLE,
            why=(f"residual {residual:+.2f} is UNJUDGEABLE: the harvest it is measured against "
                 "was not read. An unmeasured denominator is not a clean verdict"),
            scope=scope)
    if funding > 0.0:
        threshold = alert_frac * funding
        if abs(residual) >= threshold:
            return ResidualReport(
                residual_usd=residual, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
                alert_frac=alert_frac, threshold_usd=threshold, verdict="DEFECT",
                why=(f"UNEXPLAINED {residual:+.2f} is {abs(residual) / funding:.0%} of the "
                     f"{funding:+.2f} harvest, at or past the {alert_frac:.0%} bar "
                     "carry_bleed_report already alarms on -- money the desk cannot attribute"),
                scope=scope)
        return ResidualReport(
            residual_usd=residual, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
            alert_frac=alert_frac, threshold_usd=threshold, verdict="OK",
            why=(f"unexplained {residual:+.2f} is {abs(residual) / funding:.0%} of the "
                 f"{funding:+.2f} harvest, under the {alert_frac:.0%} bar"),
            scope=scope)
    if residual != 0.0:
        return ResidualReport(
            residual_usd=residual, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
            alert_frac=alert_frac, threshold_usd=0.0, verdict="DEFECT",
            why=(f"UNEXPLAINED {residual:+.2f} with NO funding harvest to offset it -- every "
                 "dollar of it is unattributed loss"),
            scope=scope)
    return ResidualReport(
        residual_usd=0.0, basis_usd=basis, fut_fees_usd=fees, funding_usd=funding,
        alert_frac=alert_frac, threshold_usd=0.0, verdict="OK",
        why="residual is exactly zero on a zero harvest", scope=scope)


# ---------------------------------------------------------------------------------------------
# 5. THE ACTION LIST -- what makes this a daily organ rather than a dashboard
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Action:
    """One recoverable cost, its size, and the SPECIFIC fix that recovers it."""

    label: str
    bps: float | None                # recoverable bps; None = size unknown (a defect in itself)
    fix: str
    evidence: str
    status: str = MEASURED           # MEASURED | UNQUANTIFIED
    basis: str = ""                  # what the bps is a fraction OF

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.label,
            "recoverable_bps": None if self.bps is None else round(self.bps, 2),
            "recoverable_reads": NOT_READABLE if self.bps is None else round(self.bps, 2),
            "status": self.status,
            "basis": self.basis,
            "fix": self.fix,
            "evidence": self.evidence,
        }


def rank_actions(actions: Iterable[Action]) -> list[Action]:
    """Largest measured recoverable bps first; UNQUANTIFIED blind spots last, never dropped.

    The ordering rule has one deliberate asymmetry worth stating: an unquantified item is NOT
    small, it is unmeasured, so it cannot be ranked against a measured one without inventing its
    size. It goes at the bottom of the ORDER and to the top of the duty list -- closing a blind
    spot is what makes the ranking above it trustworthy.
    """
    measured = sorted((a for a in actions if a.bps is not None), key=lambda a: -abs(a.bps or 0.0))
    blind = [a for a in actions if a.bps is None]
    return [*measured, *blind]


# ---------------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------------
@dataclass
class WindowReport:
    """One trailing window (a day or a week), fully assembled."""

    label: str
    start: datetime
    end: datetime
    days: float
    decomposition: Decomposition
    churn: list[ChurnRow] = field(default_factory=list)
    drift: list[DriftRow] = field(default_factory=list)
    n_trips: int = 0
    trips_source: str = NOT_READABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "window": self.label,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days": self.days,
            "n_round_trips": self.n_trips,
            "trips_source": self.trips_source,
            "net_apr": self.decomposition.as_dict(),
            "churn": [c.as_dict() for c in self.churn],
            "cost_model_drift": [d.as_dict() for d in self.drift],
        }


def overall_status(windows: Iterable[WindowReport], residual: ResidualReport) -> str:
    """One word for the cron log. DEFECT beats CHURN beats BREAK beats GAP beats OK/UNMEASURED.

    UNMEASURED is NOT an OK: it means the report could not see the money path, and a desk that
    cannot see its own execution costs is in a worse state than one whose costs are merely high.
    It ranks below the defect classes only because it names a reader problem, not a money problem.
    """
    if residual.verdict == "DEFECT":
        return "DEFECT"
    verdicts = {c.verdict for w in windows for c in w.churn}
    drifts = {d.verdict for w in windows for d in w.drift}
    if "CHURN" in verdicts:
        return "CHURN"
    if "BREAK" in drifts:
        return "BREAK"
    if "GAP" in drifts:
        return "GAP"
    measured = any(w.decomposition.net_usd is not None for w in windows)
    return "OK" if measured else UNMEASURED


def window_bounds(now: datetime, days: float) -> tuple[datetime, datetime]:
    """[now - days, now], timezone-aware. Raises on a naive `now` rather than assuming UTC."""
    if now.tzinfo is None:
        raise ValueError("window_bounds requires a timezone-aware `now`")
    return now - timedelta(days=days), now
