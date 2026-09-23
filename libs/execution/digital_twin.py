"""The Execution Digital Twin: every live intent is a simulation test case.

THE PRINCIPAL'S ORDER. "Every live intent becomes a simulation test case. Compare PredictedFill
vs ActualFill. Train fill probability, slippage, latency, partial fill, reject, spread expansion,
market impact proxy. Then your backtester recalibrates itself from live execution." This module
is the pure half of that loop: it joins what the desk ASKED for to what the venue DID, measures
the gap on every axis the desk can actually observe, and turns the gap into the correction the
simulator should apply. It reads nothing from disk, sends nothing, and imports only numpy; the
hourly organ (`desks/mt5/research/execution_twin.py`) owns the ledgers, the watermark and the
report.

WHAT IS OBSERVABLE, AND FROM WHERE. Three append-only ledgers already exist on the desk, each
written at a different moment by a different event, which is why they carry different halves of
every case:

    data/order_intents.jsonl           what was asked: symbol, side, lot, the reference quote
                                       (`intended`), stop, the spread at decision (bracket path),
                                       the venue's retcode -- so REJECTS live here
    data/execution_algo_outcomes.jsonl what the plan expected against what printed: the algo,
                                       expected_p_fill, expected_cost, realised_cost, filled_frac
                                       -- so PREDICTED vs ACTUAL for market plans lives here
    data/live_ledger.jsonl             the closed deal, with the position's entry price and the
                                       account that produced it -- so the FILL of a resting
                                       bracket, and demo-vs-live PROVENANCE, live here

THE JOIN, HONESTLY. Nothing links an intent to its outcome today: the gateway writes the intent
with a `ticket` and `record_outcome` writes the outcome with neither ticket nor id, seconds later
in the same pass. So `join_cases` joins on the gateway's `intent_id` WHEN BOTH ROWS CARRY ONE
(the handoff field), and otherwise on (symbol, side, lots, |t_outcome - t_intent| <= window),
nearest first, each outcome used once. Deals join to intents by order ticket, the convention
`markout.py` already uses. Every case records which key joined it, so the report can say how much
of the dataset rests on the fuzzy join and the gateway owner can see the fuzzy share go to zero
once `intent_id` ships.

SMALL SAMPLES ARE REPORTED, NEVER FILLED IN. Every estimate carries n and a 95% interval; below
MIN_N per bucket the bucket is UNMEASURED and its numeric fields are None. This is the same rule
`fill_surface` (needs MIN_FILLS to fit), `decision_ledger` (MIN_POPULATION_FOR_BIAS) and
`markout` ("execution is UNMEASURED until a fill exists") already follow, and it matters more
here than anywhere: the output of this module is a number the gauntlet will charge, and a fake
number in that seat manufactures survivors.

THE RECALIBRATION IS ASYMMETRIC ON PURPOSE. `recalibration` never LOWERS a cost the simulator
charges on fewer than MIN_N_RECAL cases; a cost may go UP on thin evidence (MIN_N) and DOWN only
on thick evidence with the interval clear of the modelled number. Likewise a fill probability may
fall on thin evidence and rise only on thick. The gauntlet is never made easier by a small
sample: an optimistic simulator is the failure this desk has paid for repeatedly (the 0.48 gold
spread, the 184x commission, the 6x fill-hour spread -- every one in the survivor-manufacturing
direction), and a pessimistic one only costs a candidate a longer wait for evidence.

DEMO FILLS ARE SEGREGATED. `provenance` documents why a demo server's fills are optimistic in
exactly the dimension this module measures (they fill at the trigger and do not slip). Cases
carry `account_kind` when a deal supplied it; `recalibration` excludes demo cases and reports how
many it excluded. Outcomes and intents carry no provenance today, so an unjoined market case is
"unknown", not "live".

CONVENTIONS. Slippage is a FRACTION OF PRICE relative to the reference quote the intent records
(ask for a buy, bid for a sell), signed so that worse-than-asked is positive -- the axis
`FillSurface.expected_slip` is fitted in, `execution_registry.record_outcome` records in and
`markout` measures in, so predicted and realised sit on one axis without a translation nobody
will keep in step. R is that fraction divided by the intent's stop distance as a fraction of
price. Hours are UTC; sessions are the coarse UTC bands named in SESSIONS.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import numpy as np

__all__ = [
    "CALIBRATED",
    "JOIN_WINDOW_S",
    "MIN_N",
    "MIN_N_RECAL",
    "RESOLVE_AFTER_S",
    "SESSIONS",
    "SIM_TOO_OPTIMISTIC",
    "SIM_TOO_PESSIMISTIC",
    "UNMEASURED",
    "SimCost",
    "TwinCase",
    "case_from_row",
    "execution_choice_value",
    "fill_calibration",
    "impact_proxy",
    "join_cases",
    "latency_summary",
    "recalibration",
    "reject_model",
    "session_of",
    "size_bucket",
    "slippage_calibration",
    "spread_bucket",
    "spread_expansion",
]

#: Below this many cases a bucket, a symbol or a table is UNMEASURED: n is reported, nothing else.
MIN_N = 10
#: Below this many cases a correction may only make the simulator MORE pessimistic. See the
#: module docstring: costs go up on thin evidence, down only on thick.
MIN_N_RECAL = 100
#: The fuzzy join's window between an intent's `time` and its outcome's `at`. Both are written in
#: the same gateway pass, seconds apart; two minutes covers a slow terminal round trip and is far
#: inside the gateway's own cadence, so two orders on one symbol/side/lot cannot be confused.
JOIN_WINDOW_S = 120.0
#: A resting order older than this with no deal against it counts as UNFILLED (its broker-side
#: expiry is at most the trading day). Younger and still dealless, it is unresolved, not unfilled.
RESOLVE_AFTER_S = 2 * 86400.0
#: Two lot sizes closer than this are the same order size for the fuzzy join.
LOT_TOL = 1e-6
Z95 = 1.959964

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
CALIBRATED = "CALIBRATED"
SIM_TOO_OPTIMISTIC = "SIM_TOO_OPTIMISTIC"
SIM_TOO_PESSIMISTIC = "SIM_TOO_PESSIMISTIC"

#: MT5 retcodes that mean the venue accepted the request: 10008 placed (pending), 10009 done.
OK_RETCODES: frozenset[int] = frozenset({10008, 10009})
#: MT5 platform retcodes (fixed by MetaQuotes, not by the broker), named so a reject histogram
#: reads as reasons rather than integers. Unknown codes are reported as `retcode_<n>`.
RETCODE_NAMES: dict[int, str] = {
    10004: "requote", 10006: "rejected", 10007: "cancelled", 10010: "partial_done",
    10011: "error", 10012: "timeout", 10013: "invalid_request", 10014: "invalid_volume",
    10015: "invalid_price", 10016: "invalid_stops", 10017: "trade_disabled",
    10018: "market_closed", 10019: "no_money", 10020: "price_changed", 10021: "no_prices",
    10022: "invalid_expiration", 10023: "order_changed", 10024: "too_many_requests",
    10025: "no_changes", 10026: "server_disables_autotrading",
    10027: "client_disables_autotrading", 10028: "locked", 10029: "frozen",
    10030: "invalid_fill_mode", 10031: "no_connection", 10032: "only_real", 10033: "limit_orders",
    10034: "limit_volume", 10035: "invalid_order", 10036: "position_closed",
    10038: "invalid_close_volume", 10039: "close_order_exists", 10040: "limit_positions",
    10041: "reject_cancel", 10042: "long_only", 10043: "short_only", 10044: "close_only",
    10045: "fifo_close",
}

#: (name, first UTC hour, last UTC hour exclusive). Coarse on purpose: the twin conditions on a
#: handful of bands so every cell can reach MIN_N; the fill surface is where the hour is a
#: continuous feature.
SESSIONS: tuple[tuple[str, int, int], ...] = (
    ("asia", 0, 7), ("london", 7, 13), ("overlap", 13, 17), ("newyork", 17, 22), ("late", 22, 24),
)
#: Absolute lot buckets. Lots are the venue's own size unit and the one the outcome ledger records.
SIZE_BUCKETS: tuple[tuple[float, str], ...] = (
    (0.05, "xs<=0.05"), (0.2, "s<=0.2"), (1.0, "m<=1"), (math.inf, "l>1"),
)
#: Spread buckets in basis points of price: gold and the majors sit under 1bp, crosses 1-3bp,
#: exotics 3-10bp and above (USDZAR's fill-hour spread measured at ~11bp, cost_surface.py).
SPREAD_BUCKETS_BPS: tuple[tuple[float, str], ...] = (
    (1.0, "tight<=1bp"), (3.0, "normal<=3bp"), (10.0, "wide<=10bp"), (math.inf, "extreme>10bp"),
)
_FILL_BINS: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0 + 1e-9)


# --------------------------------------------------------------------------- small helpers
def _f(x: Any) -> float | None:
    """A finite float or None. Bools are not numbers here (`filled: true` is not a 1.0 slip)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _i(x: Any) -> int | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _parse_time(s: Any) -> datetime | None:
    """ISO text (or a datetime) as an aware UTC datetime; naive input is taken as UTC, which is
    what the gateway's `now()` writes. None when unparseable -- an intent without a time cannot
    be joined by time and is reported as such rather than guessed."""
    if isinstance(s, datetime):
        d = s
    else:
        try:
            d = datetime.fromisoformat(str(s))
        except (TypeError, ValueError):
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def _side(raw: Any) -> tuple[str, int] | None:
    """("buy", +1) / ("sell", -1) from the intent's side string (`buy`, `sell_stop`, ...) or an MT5
    numeric order type (0/2/4 buy, 1/3/5 sell)."""
    if isinstance(raw, str):
        s = raw.lower()
        if "buy" in s:
            return "buy", 1
        if "sell" in s:
            return "sell", -1
        return None
    t = _i(raw)
    if t is None:
        return None
    if t in (0, 2, 4):
        return "buy", 1
    if t in (1, 3, 5):
        return "sell", -1
    return None


def _order_type(row: Mapping[str, Any], side_raw: Any) -> str:
    ot = row.get("order_type")
    if isinstance(ot, str) and ot:
        return ot
    s = str(side_raw or "").lower()
    if s.endswith("_stop"):
        return "pending_stop"
    if s.endswith("_limit"):
        return "limit"
    return "market"


def session_of(hour: int) -> str:
    h = int(hour) % 24
    for name, lo, hi in SESSIONS:
        if lo <= h < hi:
            return name
    return SESSIONS[-1][0]


def size_bucket(lots: float) -> str:
    for edge, name in SIZE_BUCKETS:
        if lots <= edge:
            return name
    return SIZE_BUCKETS[-1][1]


def spread_bucket(spread_frac: float | None) -> str:
    if spread_frac is None:
        return "unknown"
    bps = spread_frac * 1e4
    for edge, name in SPREAD_BUCKETS_BPS:
        if bps <= edge:
            return name
    return SPREAD_BUCKETS_BPS[-1][1]


def _reject_reason(retcode: int | None) -> str:
    if retcode is None:
        return "no_result"
    if retcode in OK_RETCODES:
        return ""
    return RETCODE_NAMES.get(retcode, f"retcode_{retcode}")


def _mean_ci(xs: Sequence[float]) -> tuple[float, float, float]:
    """(mean, lo, hi): a normal 95% interval on the sample mean. A t-quantile would need scipy;
    at MIN_N the z-interval is a few percent narrow, which is one reason MIN_N_RECAL, not MIN_N,
    is where a cost may fall."""
    n = len(xs)
    a = np.asarray(xs, dtype=float)
    m = float(a.mean()) if n else float("nan")
    if n < 2:
        return m, m, m
    se = float(a.std(ddof=1)) / math.sqrt(n)
    return m, m - Z95 * se, m + Z95 * se


def _wilson(k: int, n: int) -> tuple[float, float, float]:
    """(rate, lo, hi): Wilson's interval on a proportion -- it does not collapse to zero width at
    0 or n successes the way the normal one does, which is exactly where small fill samples sit."""
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    z2 = Z95 * Z95
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def _r(x: float | None, nd: int = 8) -> float | None:
    return None if x is None or not math.isfinite(x) else round(x, nd)


def _stat(xs: Sequence[float], min_n: int) -> dict[str, Any]:
    """n, mean, ci95 -- or n alone with status UNMEASURED. The shape every table here uses."""
    n = len(xs)
    if n < min_n:
        return {"n": n, "mean": None, "ci95": None, "status": UNMEASURED}
    m, lo, hi = _mean_ci(xs)
    return {"n": n, "mean": _r(m), "ci95": [_r(lo), _r(hi)], "status": MEASURED}


def _rate(k: int, n: int, min_n: int) -> dict[str, Any]:
    if n < min_n:
        return {"n": n, "k": k, "rate": None, "ci95": None, "status": UNMEASURED}
    p, lo, hi = _wilson(k, n)
    return {"n": n, "k": k, "rate": _r(p, 6), "ci95": [_r(lo, 6), _r(hi, 6)],
            "status": MEASURED}


# --------------------------------------------------------------------------- the case
@dataclass(frozen=True)
class TwinCase:
    """One live intent joined to its outcome: the simulation test case the principal asked for.

    `predicted_*` is what the desk believed when it sent the order (the outcome ledger's
    `expected_*` for a plan that ran; the gateway's explicit prediction fields when it carries
    them; otherwise the simulator's own assumption -- a market order fills, a pending stop fills
    at its trigger with zero slip). `filled` is None when the case is not yet resolved (a recent
    resting order with no deal), never False by default: an unresolved order is not an unfilled
    one (`markout`'s rule). `join_key` names what linked intent to outcome.
    """

    intent_id: str
    symbol: str
    sleeve: str
    time: str
    hour: int
    session: str
    side: str
    direction: int
    order_type: str
    algo: str
    lots: float
    price_ref: float
    stop_frac: float | None
    spread_frac: float | None
    distance_frac: float | None
    vol_frac: float | None
    latency_ms: float | None
    predicted_p_fill: float | None
    predicted_slip_frac: float | None
    retcode: int | None
    rejected: bool
    reject_reason: str
    filled: bool | None
    filled_frac: float | None
    actual_slip_frac: float | None
    spread_at_fill_frac: float | None
    account_kind: str
    join_key: str
    joined_outcome: bool
    joined_deal: bool

    @property
    def size_bucket(self) -> str:
        return size_bucket(self.lots)

    @property
    def spread_bucket(self) -> str:
        return spread_bucket(self.spread_frac)

    @property
    def resting(self) -> bool:
        return self.order_type != "market"

    def _in_r(self, frac: float | None) -> float | None:
        if frac is None or self.stop_frac is None or self.stop_frac <= 0:
            return None
        return frac / self.stop_frac

    @property
    def expected_cost_r(self) -> float | None:
        return self._in_r(self.predicted_slip_frac)

    @property
    def realised_cost_r(self) -> float | None:
        return self._in_r(self.actual_slip_frac)

    @property
    def resolution(self) -> str:
        """The mutable half of a case, as text: what can change when a deal arrives later. The
        organ appends a case again only when this changes, so the dataset is append-only and
        still converges on the resolved row."""
        return (f"{self.filled}|{self.filled_frac}|{self.actual_slip_frac}|{self.rejected}|"
                f"{self.join_key}|{self.account_kind}|{self.spread_at_fill_frac}")

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["size_bucket"] = self.size_bucket
        d["spread_bucket"] = self.spread_bucket
        return d


def case_from_row(row: Mapping[str, Any]) -> TwinCase:
    """A case back from `to_row()`; derived columns are recomputed, not trusted."""
    def s(k: str) -> str:
        return str(row.get(k) or "")

    hour = _i(row.get("hour")) or 0
    filled = row.get("filled")
    return TwinCase(
        intent_id=s("intent_id"), symbol=s("symbol"), sleeve=s("sleeve"), time=s("time"),
        hour=hour, session=s("session") or session_of(hour), side=s("side"),
        direction=_i(row.get("direction")) or 0, order_type=s("order_type"), algo=s("algo"),
        lots=_f(row.get("lots")) or 0.0, price_ref=_f(row.get("price_ref")) or 0.0,
        stop_frac=_f(row.get("stop_frac")), spread_frac=_f(row.get("spread_frac")),
        distance_frac=_f(row.get("distance_frac")), vol_frac=_f(row.get("vol_frac")),
        latency_ms=_f(row.get("latency_ms")), predicted_p_fill=_f(row.get("predicted_p_fill")),
        predicted_slip_frac=_f(row.get("predicted_slip_frac")), retcode=_i(row.get("retcode")),
        rejected=bool(row.get("rejected")), reject_reason=s("reject_reason"),
        filled=None if filled is None else bool(filled), filled_frac=_f(row.get("filled_frac")),
        actual_slip_frac=_f(row.get("actual_slip_frac")),
        spread_at_fill_frac=_f(row.get("spread_at_fill_frac")),
        account_kind=s("account_kind") or "unknown", join_key=s("join_key") or "none",
        joined_outcome=bool(row.get("joined_outcome")), joined_deal=bool(row.get("joined_deal")))


# --------------------------------------------------------------------------- the join
@dataclass
class _Outcome:
    idx: int
    row: Mapping[str, Any]
    at: datetime | None
    symbol: str
    side: str
    lots: float
    intent_id: str


def _outcomes(rows: Iterable[Mapping[str, Any]]) -> list[_Outcome]:
    out: list[_Outcome] = []
    for i, r in enumerate(rows):
        if not isinstance(r, Mapping):
            continue
        sd = _side(r.get("side"))
        lots = _f(r.get("lots"))
        if sd is None or lots is None:
            continue
        out.append(_Outcome(i, r, _parse_time(r.get("at")), str(r.get("symbol") or ""), sd[0],
                            lots, str(r.get("intent_id") or "")))
    return out


def _deals_by_ticket(rows: Iterable[Mapping[str, Any]] | None) -> dict[str, Mapping[str, Any]]:
    """Deals by the order ticket they belong to. A position closes in one deal; when two rows
    claim one ticket the one carrying an entry price wins, since that is the field the fill
    needs."""
    by: dict[str, Mapping[str, Any]] = {}
    for d in rows or ():
        if not isinstance(d, Mapping):
            continue
        t = d.get("order")
        if t is None:
            continue
        key = str(t)
        have = by.get(key)
        if have is None or ((_f(d.get("entry_price")) or 0.0) > 0
                            and (_f(have.get("entry_price")) or 0.0) <= 0):
            by[key] = d
    return by


def _quote_of(row: Mapping[str, Any], direction: int) -> float | None:
    """The reference quote at decision: ask for a buy, bid for a sell -- the side the order pays."""
    return _f(row.get("decision_ask") if direction > 0 else row.get("decision_bid"))


def join_cases(intents_rows: Iterable[Mapping[str, Any]],
               outcome_rows: Iterable[Mapping[str, Any]],
               deals_rows: Iterable[Mapping[str, Any]] | None = None, *,
               window_s: float = JOIN_WINDOW_S, asof: datetime | str | None = None,
               resolve_after_s: float = RESOLVE_AFTER_S) -> list[TwinCase]:
    """Every intent as a TwinCase, joined to its outcome and its deal where one exists.

    JOIN ORDER, per intent: (1) `intent_id` carried by both rows; (2) the fuzzy key -- same
    symbol, same side, lots within LOT_TOL, outcome `at` within `window_s` of the intent `time`,
    nearest first, each outcome used at most once; (3) no outcome. Deals join by
    `deal["order"] == intent["ticket"]`. The fuzzy join is what the desk has TODAY because
    `record_outcome` writes no ticket and no id; `join_key` on every case says which rule
    linked it, and the handoff for the gateway owner is one stable `intent_id` on both rows.

    RESOLUTION. A rejected retcode is a reject (never a fill). A joined outcome resolves fill and
    slip from the plan that ran. A joined deal resolves a resting order's fill from the position's
    entry price. A market DONE (10009) with no outcome row is filled with slip UNMEASURED. A
    resting order with no deal is UNFILLED only when `deals_rows` was supplied and the intent is
    older than `resolve_after_s` as of `asof` (default: now); otherwise it is unresolved (None).
    """
    now = _parse_time(asof) if asof is not None else datetime.now(tz=UTC)
    outs = _outcomes(outcome_rows)
    by_id: dict[str, _Outcome] = {}
    by_fuzzy: dict[tuple[str, str], list[_Outcome]] = {}
    for o in outs:
        if o.intent_id and o.intent_id not in by_id:
            by_id[o.intent_id] = o
        by_fuzzy.setdefault((o.symbol, o.side), []).append(o)
    deals = _deals_by_ticket(deals_rows)
    have_deals = deals_rows is not None
    used: set[int] = set()
    cases: list[TwinCase] = []

    for row in intents_rows:
        if not isinstance(row, Mapping):
            continue
        sd = _side(row.get("side"))
        lots = _f(row.get("lot")) if row.get("lot") is not None else _f(row.get("lots"))
        price = _f(row.get("intended")) or _f(row.get("price"))
        if sd is None or lots is None or lots <= 0 or price is None or price <= 0:
            continue
        side, direction = sd
        symbol = str(row.get("symbol") or "")
        sleeve = str(row.get("sleeve") or "")
        t = _parse_time(row.get("time"))
        time_iso = t.isoformat() if t is not None else str(row.get("time") or "")
        hour = t.hour if t is not None else 0
        order_type = _order_type(row, row.get("side"))
        ticket = row.get("ticket")
        explicit_id = str(row.get("intent_id") or "")
        intent_id = explicit_id or (
            f"{sleeve}|{symbol}|{row.get('side')}|{lots:.4f}|{time_iso}|{ticket}")

        # ---- the outcome, by id then by the fuzzy key
        outcome: _Outcome | None = None
        join_key = "none"
        if explicit_id and explicit_id in by_id and by_id[explicit_id].idx not in used:
            outcome, join_key = by_id[explicit_id], "intent_id"
        elif t is not None:
            best: tuple[float, _Outcome] | None = None
            for o in by_fuzzy.get((symbol, side), ()):
                if o.idx in used or o.at is None or abs(o.lots - lots) > LOT_TOL:
                    continue
                dt = abs((o.at - t).total_seconds())
                if dt <= window_s and (best is None or dt < best[0]):
                    best = (dt, o)
            if best is not None:
                outcome, join_key = best[1], "fuzzy"
        if outcome is not None:
            used.add(outcome.idx)

        # ---- the deal, by ticket
        deal = deals.get(str(ticket)) if ticket is not None else None
        if deal is not None and join_key == "none":
            join_key = "ticket"

        # ---- the state at decision
        spread_abs = _f(row.get("spread_at_decision"))
        bid, ask = _f(row.get("decision_bid")), _f(row.get("decision_ask"))
        if spread_abs is None and bid is not None and ask is not None:
            spread_abs = ask - bid
        spread_frac = _f(row.get("spread_frac"))
        if spread_frac is None and spread_abs is not None:
            spread_frac = spread_abs / price
        distance_frac = _f(row.get("distance_frac"))
        if distance_frac is None:
            if order_type == "market":
                distance_frac = 0.0
            else:
                q = _quote_of(row, direction)
                distance_frac = abs(price - q) / price if q is not None and q > 0 else None
        stop_frac: float | None = None
        sl = _f(row.get("sl"))
        if sl is not None and sl > 0:
            stop_frac = abs(price - sl) / price
        vol_frac = _f(row.get("atr_frac")) or _f(row.get("vol_frac")) or _f(row.get("vol"))
        latency_ms = _f(row.get("latency_ms"))
        retcode = _i(row.get("retcode"))
        rejected = retcode is None or retcode not in OK_RETCODES

        # ---- predictions: the plan that ran > the gateway's explicit field > the simulator's own
        # assumption (a market order fills; a pending stop fills at its trigger with zero slip)
        p_pred = _f(outcome.row.get("expected_p_fill")) if outcome is not None else None
        if p_pred is None:
            p_pred = _f(row.get("predicted_p_fill"))
        if p_pred is None:
            if order_type == "market":
                p_pred = 1.0
            elif distance_frac is not None and spread_frac is not None and spread_frac > 0:
                # FillSurface.p_fill's own prior for a resting order, restated here so the twin
                # scores the same belief the policy priced with before the surface was fitted.
                p_pred = math.exp(-distance_frac / spread_frac) if distance_frac > 0 else 1.0
        s_pred = _f(outcome.row.get("expected_cost")) if outcome is not None else None
        if s_pred is None:
            s_pred = _f(row.get("predicted_slip_frac"))
        if s_pred is None and order_type == "pending_stop":
            s_pred = 0.0
        algo = str(outcome.row.get("algo") or "") if outcome is not None else ""
        if not algo:
            algo = "market" if order_type == "market" else order_type

        # ---- what the venue did
        filled: bool | None
        filled_frac: float | None
        actual: float | None = None
        spread_fill_frac = _f(row.get("spread_at_fill_frac"))
        account_kind = "unknown"
        if rejected:
            filled, filled_frac = False, 0.0
        elif outcome is not None:
            ff = _f(outcome.row.get("filled_frac"))
            if ff is None:
                fl = _f(outcome.row.get("filled_lots"))
                ff = (fl / lots) if fl is not None else None
            filled_frac = ff
            filled = (ff > 0) if ff is not None else None
            actual = _f(outcome.row.get("realised_cost")) if filled else None
            sf = _f(outcome.row.get("spread_at_fill"))
            if sf is not None:
                spread_fill_frac = sf / price
        elif deal is not None:
            fill_px = _f(deal.get("entry_price"))
            if fill_px is None or fill_px <= 0:
                fill_px = _f(deal.get("fill_price"))
            vol = _f(deal.get("volume"))
            filled = True
            filled_frac = min(vol / lots, 1.0) if vol is not None and vol > 0 else 1.0
            if fill_px is not None and fill_px > 0:
                actual = (fill_px - price) * direction / price
        elif order_type == "market" and retcode == 10009:
            filled, filled_frac = True, 1.0
        elif have_deals and t is not None and now is not None \
                and (now - t).total_seconds() > resolve_after_s:
            filled, filled_frac = False, 0.0
        else:
            filled, filled_frac = None, None
        if deal is not None:
            account_kind = str(deal.get("account_kind") or "unknown")
            sf = _f(deal.get("spread_at_fill"))
            if sf is not None and spread_fill_frac is None:
                spread_fill_frac = sf / price

        cases.append(TwinCase(
            intent_id=intent_id, symbol=symbol, sleeve=sleeve, time=time_iso, hour=hour,
            session=session_of(hour), side=side, direction=direction, order_type=order_type,
            algo=algo, lots=lots, price_ref=price, stop_frac=stop_frac, spread_frac=spread_frac,
            distance_frac=distance_frac, vol_frac=vol_frac, latency_ms=latency_ms,
            predicted_p_fill=p_pred, predicted_slip_frac=s_pred, retcode=retcode,
            rejected=rejected, reject_reason=_reject_reason(retcode), filled=filled,
            filled_frac=filled_frac, actual_slip_frac=actual,
            spread_at_fill_frac=spread_fill_frac, account_kind=account_kind, join_key=join_key,
            joined_outcome=outcome is not None, joined_deal=deal is not None))
    return cases


# --------------------------------------------------------------------------- calibration tables
def _group(cases: Iterable[TwinCase], key: str) -> dict[str, list[TwinCase]]:
    by: dict[str, list[TwinCase]] = {}
    for c in cases:
        by.setdefault(str(getattr(c, key)), []).append(c)
    return dict(sorted(by.items()))


def fill_calibration(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """The reliability table of P(fill): predicted-probability bins against the realised fill
    rate, with the Brier score and the expected calibration error (ECE, bin-weighted |rate -
    mean prediction|). Uses accepted orders whose fill is resolved; rejects are the reject
    model's business and an unresolved order is neither a fill nor a miss."""
    use = [c for c in cases if not c.rejected and c.filled is not None
           and c.predicted_p_fill is not None]
    n = len(use)
    out: dict[str, Any] = {"n": n, "min_n": min_n, "brier": None, "ece": None, "bins": [],
                           "by_order_type": {}, "status": UNMEASURED}
    if n == 0:
        return out
    p = np.asarray([float(c.predicted_p_fill or 0.0) for c in use])
    y = np.asarray([1.0 if c.filled else 0.0 for c in use])
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for lo, hi in pairwise(_FILL_BINS):
        m = (p >= lo) & (p < hi)
        k = int(m.sum())
        row: dict[str, Any] = {"lo": lo, "hi": min(hi, 1.0), "n": k}
        if k >= min_n:
            rate, clo, chi = _wilson(int(y[m].sum()), k)
            row.update({"predicted_mean": _r(float(p[m].mean()), 6), "realised_rate": _r(rate, 6),
                        "ci95": [_r(clo, 6), _r(chi, 6)], "status": MEASURED})
            ece += (k / n) * abs(rate - float(p[m].mean()))
        else:
            row.update({"predicted_mean": None, "realised_rate": None, "ci95": None,
                        "status": UNMEASURED})
        bins.append(row)
    out["bins"] = bins
    if n >= min_n:
        out["brier"] = _r(float(np.mean((p - y) ** 2)), 6)
        out["ece"] = _r(ece, 6)
        out["status"] = MEASURED
    for ot, cs in _group(use, "order_type").items():
        k = sum(1 for c in cs if c.filled)
        r = _rate(k, len(cs), min_n)
        r["predicted_mean"] = _r(float(np.mean([c.predicted_p_fill or 0.0 for c in cs])), 6)
        out["by_order_type"][ot] = r
    return out


def _bias_table(cs: Sequence[TwinCase], min_n: int) -> dict[str, Any]:
    d = [float(c.actual_slip_frac or 0.0) - float(c.predicted_slip_frac or 0.0) for c in cs]
    st = _stat(d, min_n)
    row: dict[str, Any] = {"n": st["n"], "bias": st["mean"], "ci95": st["ci95"],
                           "status": st["status"], "mae": None, "mean_predicted": None,
                           "mean_actual": None}
    if st["status"] == MEASURED:
        row["mae"] = _r(float(np.mean(np.abs(d))))
        row["mean_predicted"] = _r(float(np.mean([c.predicted_slip_frac or 0.0 for c in cs])))
        row["mean_actual"] = _r(float(np.mean([c.actual_slip_frac or 0.0 for c in cs])))
    return row


def slippage_calibration(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """Predicted against realised slip on filled cases: bias (realised - predicted), MAE and the
    interval on the bias, overall and by symbol / session / size bucket / order type. Fractions
    of price; positive bias means the venue was worse than the desk believed."""
    use = [c for c in cases if c.filled and c.actual_slip_frac is not None
           and c.predicted_slip_frac is not None]
    out: dict[str, Any] = {"unit": "fraction_of_price", "min_n": min_n,
                           "overall": _bias_table(use, min_n)}
    for key in ("symbol", "session", "size_bucket", "order_type"):
        out["by_" + key] = {k: _bias_table(cs, min_n) for k, cs in _group(use, key).items()}
    return out


def reject_model(cases: Sequence[TwinCase], *, alpha: float = 1.0,
                 min_n: int = MIN_N) -> dict[str, Any]:
    """P(reject | symbol, session, spread bucket, size bucket), Laplace-smoothed with `alpha`
    pseudo-counts on each side, with the raw k/n and a Wilson interval beside it. The smoothed
    number is the one to PRICE with (a cell that has never rejected is not a cell that cannot);
    the interval is the one to BELIEVE, and below `min_n` only n and k are reported. The
    marginals by each factor are given as well, since the joint cells are thin by construction."""
    use = [c for c in cases if c.retcode is not None or c.rejected]
    n_all = len(use)
    k_all = sum(1 for c in use if c.rejected)

    def cell(cs: Sequence[TwinCase]) -> dict[str, Any]:
        n = len(cs)
        k = sum(1 for c in cs if c.rejected)
        row = _rate(k, n, min_n)
        row["p_smoothed"] = _r((k + alpha) / (n + 2 * alpha), 6) if n > 0 else None
        return row

    joint: dict[str, dict[str, Any]] = {}
    for c in use:
        key = f"{c.symbol}|{c.session}|{c.spread_bucket}|{c.size_bucket}"
        joint.setdefault(key, {"cases": []})["cases"].append(c)
    reasons: dict[str, int] = {}
    for c in use:
        if c.rejected:
            reasons[c.reject_reason] = reasons.get(c.reject_reason, 0) + 1
    out: dict[str, Any] = {"alpha": alpha, "min_n": min_n, "overall": cell(use),
                           "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
                           "cells": {k: cell(v["cases"]) for k, v in sorted(joint.items())}}
    for key in ("symbol", "session", "spread_bucket", "size_bucket"):
        out["by_" + key] = {k: cell(cs) for k, cs in _group(use, key).items()}
    out["status"] = MEASURED if n_all >= min_n else UNMEASURED
    out["n"], out["k"] = n_all, k_all
    return out


def latency_summary(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """order_send round trip in ms where the gateway recorded it. Today no intent carries
    `latency_ms`; until the handoff field ships this reports UNMEASURED with that reason."""
    xs = [float(c.latency_ms) for c in cases if c.latency_ms is not None]
    n = len(xs)
    if n < min_n:
        return {"n": n, "status": UNMEASURED, "unit": "ms",
                "why": ("no intent carries latency_ms" if n == 0 else
                        f"{n} intents carry latency_ms, need {min_n}")}
    a = np.asarray(xs)
    out: dict[str, Any] = {"n": n, "status": MEASURED, "unit": "ms",
                           "mean": _r(float(a.mean()), 3),
                           "p50": _r(float(np.percentile(a, 50)), 3),
                           "p90": _r(float(np.percentile(a, 90)), 3),
                           "p99": _r(float(np.percentile(a, 99)), 3), "by_symbol": {}}
    for sym, cs in _group([c for c in cases if c.latency_ms is not None], "symbol").items():
        out["by_symbol"][sym] = _stat([float(c.latency_ms or 0.0) for c in cs], min_n)
    return out


def spread_expansion(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """spread at fill / spread at intent on filled cases where both are known. A ratio above one
    is the venue widening into the desk's order; the share above 1.5 is the tail that matters.
    Nothing records the spread at fill today (handoff), so this is UNMEASURED until it does."""
    use = [c for c in cases if c.filled and c.spread_frac and c.spread_at_fill_frac is not None]
    ratios = [float(c.spread_at_fill_frac or 0.0) / float(c.spread_frac or 1.0) for c in use]
    n = len(ratios)
    if n < min_n:
        return {"n": n, "status": UNMEASURED,
                "why": ("no case carries both spread_at_intent and spread_at_fill" if n == 0
                        else f"{n} cases carry both spreads, need {min_n}")}
    a = np.asarray(ratios)
    out: dict[str, Any] = {"n": n, "status": MEASURED, "mean_ratio": _r(float(a.mean()), 6),
                           "p90_ratio": _r(float(np.percentile(a, 90)), 6),
                           "share_above_1p5": _r(float(np.mean(a > 1.5)), 6), "by_session": {}}
    for s, cs in _group(use, "session").items():
        out["by_session"][s] = _stat(
            [float(c.spread_at_fill_frac or 0.0) / float(c.spread_frac or 1.0) for c in cs], min_n)
    return out


def impact_proxy(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """Realised slip against order size: the market-impact proxy the desk can observe without a
    book. Mean slip per size bucket with n and interval, and the least-squares slope of slip on
    lots (fraction of price per lot) overall and per symbol where the sample carries it."""
    use = [c for c in cases if c.filled and c.actual_slip_frac is not None]

    def slope(cs: Sequence[TwinCase]) -> dict[str, Any]:
        n = len(cs)
        lots = np.asarray([c.lots for c in cs], dtype=float)
        # one order size is no regressor: the range test, not std(), because thirty copies of
        # 0.1 have a floating-point std of 1e-17 and polyfit would run on a rank-deficient design
        if n < min_n or float(lots.max() - lots.min()) <= LOT_TOL:
            return {"n": n, "slope_per_lot": None, "status": UNMEASURED}
        slip = np.asarray([float(c.actual_slip_frac or 0.0) for c in cs])
        b = np.polyfit(lots, slip, 1)
        return {"n": n, "slope_per_lot": _r(float(b[0])), "intercept": _r(float(b[1])),
                "status": MEASURED}

    out: dict[str, Any] = {"unit": "fraction_of_price", "min_n": min_n,
                           "by_size_bucket": {}, "slope": slope(use), "by_symbol": {}}
    for k, cs in _group(use, "size_bucket").items():
        out["by_size_bucket"][k] = _stat([float(c.actual_slip_frac or 0.0) for c in cs], min_n)
    for sym, cs in _group(use, "symbol").items():
        out["by_symbol"][sym] = {"slope": slope(cs), "by_size_bucket": {
            k: _stat([float(c.actual_slip_frac or 0.0) for c in xs], min_n)
            for k, xs in _group(cs, "size_bucket").items()}}
    return out


# --------------------------------------------------------------------------- the recalibration
@dataclass(frozen=True)
class SimCost:
    """What the simulator assumes for one symbol, on the twin's axis.

    `slip_frac`: the one-way slip the simulator charges beyond the reference quote, as a fraction
    of price. `engine.run_backtest` fills at the bar open or the trigger and charges spread and
    commission only, so its slip is 0.0. `p_fill`: the probability the simulator gives a resting
    entry that the bar touched (the engine: 1.0). `spread_frac`: the round-trip spread the
    simulator charges as a fraction of price at mult=1.0 (`median_spread_pts x point / price`),
    used only to express the correction as the multiplier `Costs.from_symbol(mult=...)` takes;
    None when unknown, in which case the correction is reported as slip to add and no multiplier.
    """

    slip_frac: float = 0.0
    p_fill: float = 1.0
    spread_frac: float | None = None


def _slip_verdict(realised: float, lo: float, hi: float, modelled: float) -> str:
    if lo <= modelled <= hi:
        return CALIBRATED
    return SIM_TOO_OPTIMISTIC if realised > modelled else SIM_TOO_PESSIMISTIC


def _fill_verdict(rate: float, lo: float, hi: float, modelled: float) -> str:
    if lo <= modelled <= hi:
        return CALIBRATED
    # fewer fills than the simulator assumed is the optimistic simulator
    return SIM_TOO_OPTIMISTIC if rate < modelled else SIM_TOO_PESSIMISTIC


def recalibration(cases: Sequence[TwinCase], current_costs: Mapping[str, SimCost] | None = None,
                  *, min_n: int = MIN_N, min_n_recal: int = MIN_N_RECAL) -> dict[str, Any]:
    """The correction the SIMULATOR should apply, per symbol, from live execution.

    For each symbol: the realised one-way slip (mean, n, 95% interval) against the slip the
    simulator charges; the realised fill rate of resting orders against the fill probability the
    simulator assumes; the reject rate the simulator ignores; and a verdict --

        CALIBRATED           the modelled number sits inside the realised interval
        SIM_TOO_OPTIMISTIC   the venue is worse than the simulator: more slip, fewer fills
        SIM_TOO_PESSIMISTIC  the venue is better than the simulator
        UNMEASURED           fewer than `min_n` cases: n is reported and nothing is applied

    THE ASYMMETRY. `applied_slip_frac` and `applied_fill_shift` are what the simulator should use.
    A correction that makes the simulator MORE pessimistic (more slip, fewer fills) is applied
    from the point estimate at `min_n`. A correction that makes it LESS pessimistic is applied
    only at `min_n_recal` AND with the interval clear of the modelled number; below that the
    modelled number is kept and `held` is True with the reason. So three cases can never lower a
    cost the gauntlet charges and three hundred can; the gauntlet is never made easier by a
    small sample. `slippage_multiplier` restates the applied slip as the factor on the round-trip
    spread charge -- (spread + 2 x applied slip) / (spread + 2 x modelled slip) -- which is what
    `Costs.from_symbol(mult=)` and `external_gauntlet.costs_for(mult=)` take; it composes with
    whatever `mult` the caller already passes. Demo cases are excluded (they cannot slip).
    """
    costs = dict(current_costs or {})
    live = [c for c in cases if c.account_kind != "demo"]
    n_demo = len(cases) - len(live)
    symbols: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {CALIBRATED: 0, SIM_TOO_OPTIMISTIC: 0, SIM_TOO_PESSIMISTIC: 0,
                              UNMEASURED: 0}
    for sym, cs in _group(live, "symbol").items():
        sim = costs.get(sym, SimCost())
        slips = [float(c.actual_slip_frac or 0.0) for c in cs
                 if c.filled and c.actual_slip_frac is not None]
        n_slip = len(slips)
        slip: dict[str, Any] = {"n": n_slip, "modelled_frac": _r(sim.slip_frac),
                                "realised_frac": None, "ci95": None, "bias_frac": None,
                                "verdict": UNMEASURED, "applied_frac": _r(sim.slip_frac),
                                "held": False, "why": ""}
        if n_slip >= min_n:
            m, lo, hi = _mean_ci(slips)
            v = _slip_verdict(m, lo, hi, sim.slip_frac)
            slip.update({"realised_frac": _r(m), "ci95": [_r(lo), _r(hi)],
                         "bias_frac": _r(m - sim.slip_frac), "verdict": v})
            if m > sim.slip_frac:
                slip["applied_frac"] = _r(m)
                slip["why"] = f"raised on {n_slip} cases (point estimate; up is allowed thin)"
            elif m < sim.slip_frac:
                if n_slip >= min_n_recal and v == SIM_TOO_PESSIMISTIC:
                    slip["applied_frac"] = _r(max(m, 0.0))
                    slip["why"] = f"lowered on {n_slip} cases with the interval clear"
                else:
                    slip["held"] = True
                    slip["why"] = (f"not lowered: {n_slip} cases < {min_n_recal}"
                                   if n_slip < min_n_recal else
                                   "not lowered: interval still covers the modelled slip")
        elif n_slip:
            slip["why"] = f"{n_slip} filled cases, need {min_n}"
        else:
            slip["why"] = "no filled case with a measured slip"
        mult: float | None = None
        if sim.spread_frac is not None and sim.spread_frac > 0:
            base = sim.spread_frac + 2.0 * sim.slip_frac
            mult = (sim.spread_frac + 2.0 * float(slip["applied_frac"] or 0.0)) / base

        rest = [c for c in cs if c.resting and not c.rejected and c.filled is not None
                and c.predicted_p_fill is not None]
        n_fill = len(rest)
        k_fill = sum(1 for c in rest if c.filled)
        fill: dict[str, Any] = {"n": n_fill, "k": k_fill, "modelled_p_fill": _r(sim.p_fill, 6),
                                "predicted_mean": None, "realised_rate": None, "ci95": None,
                                "verdict": UNMEASURED, "shift": None, "applied_shift": 0.0,
                                "held": False, "why": ""}
        if n_fill >= min_n:
            rate, lo, hi = _wilson(k_fill, n_fill)
            pm = float(np.mean([c.predicted_p_fill or 0.0 for c in rest]))
            v = _fill_verdict(rate, lo, hi, pm)
            shift = rate - pm
            fill.update({"predicted_mean": _r(pm, 6), "realised_rate": _r(rate, 6),
                         "ci95": [_r(lo, 6), _r(hi, 6)], "verdict": v, "shift": _r(shift, 6)})
            if shift < 0:
                fill["applied_shift"] = _r(shift, 6)
                fill["why"] = f"fill probability lowered on {n_fill} resting orders"
            elif shift > 0:
                if n_fill >= min_n_recal and v == SIM_TOO_PESSIMISTIC:
                    fill["applied_shift"] = _r(shift, 6)
                    fill["why"] = f"fill probability raised on {n_fill} resting orders"
                else:
                    fill["held"] = True
                    fill["why"] = (f"not raised: {n_fill} resting orders < {min_n_recal}"
                                   if n_fill < min_n_recal else
                                   "not raised: interval still covers the predicted rate")
        elif n_fill:
            fill["why"] = f"{n_fill} resolved resting orders, need {min_n}"
        else:
            fill["why"] = "no resolved resting order"

        rej = _rate(sum(1 for c in cs if c.rejected), len(cs), min_n)
        verdicts = [slip["verdict"], fill["verdict"]]
        if SIM_TOO_OPTIMISTIC in verdicts:
            overall = SIM_TOO_OPTIMISTIC
        elif SIM_TOO_PESSIMISTIC in verdicts:
            overall = SIM_TOO_PESSIMISTIC
        elif CALIBRATED in verdicts:
            overall = CALIBRATED
        else:
            overall = UNMEASURED
        counts[overall] += 1
        symbols[sym] = {"n": len(cs), "verdict": overall, "slip": slip,
                        "slippage_multiplier": _r(mult, 6),
                        "multiplier_basis": ("round-trip spread + 2 x one-way slip, at mult=1.0"
                                             if mult is not None else
                                             "no spread_frac supplied: apply applied_frac as slip"),
                        "fill": fill, "reject": rej}
    return {"min_n": min_n, "min_n_recal": min_n_recal, "unit": "fraction_of_price",
            "n_cases": len(live), "n_demo_excluded": n_demo, "symbols": symbols,
            "counts": counts,
            "rule": ("costs rise on the point estimate at min_n; fall only at min_n_recal with "
                     "the interval clear of the modelled number. The gauntlet is never made "
                     "easier by a small sample.")}


# --------------------------------------------------------------------------- the choice value
def execution_choice_value(cases: Sequence[TwinCase], *, min_n: int = MIN_N) -> dict[str, Any]:
    """What each execution algorithm actually cost, per symbol, in R, against the market baseline
    -- the realised half of `a* = argmax_a E[dlogW | s, X_t, a]` that `execution_policy.choose`
    prices from the surface's expectations.

    Per (symbol, algo): n, fill rate, mean realised cost in R with its interval, mean expected
    cost in R, and `value_vs_market_r` = market's realised cost - this algo's, with an interval
    from the two standard errors, positive when the algorithm saved R against sending at market.
    `best_measured` per symbol names the cheapest algorithm among those with `min_n` cases; a
    symbol with only one measured algorithm has no comparison and says so. This is the per-symbol,
    R-denominated table; the per-algorithm fraction-of-price board over the same outcome rows is
    `execution_registry.scoreboard`, which the organ reports beside this rather than re-deriving.
    """
    use = [c for c in cases if c.joined_outcome and not c.rejected]
    symbols: dict[str, dict[str, Any]] = {}
    for sym, cs in _group(use, "symbol").items():
        algos: dict[str, dict[str, Any]] = {}
        se: dict[str, tuple[float, float, int]] = {}
        for algo, xs in _group(cs, "algo").items():
            r = [float(c.realised_cost_r or 0.0) for c in xs if c.realised_cost_r is not None]
            e = [float(c.expected_cost_r or 0.0) for c in xs if c.expected_cost_r is not None]
            k = sum(1 for c in xs if c.filled)
            st = _stat(r, min_n)
            row: dict[str, Any] = {"n": len(xs), "n_filled": k,
                                   "fill_rate": _r(k / len(xs), 6) if xs else None,
                                   "realised_cost_r": st["mean"], "ci95": st["ci95"],
                                   "expected_cost_r": _r(float(np.mean(e))) if e else None,
                                   "status": st["status"]}
            if st["status"] == MEASURED:
                m, lo, hi = _mean_ci(r)
                se[algo] = (m, (hi - lo) / (2 * Z95), len(r))
            algos[algo] = row
        mk = se.get("market")
        for algo, row in algos.items():
            if mk is None or algo not in se or algo == "market":
                row["value_vs_market_r"] = None
                row["value_ci95"] = None
                continue
            m, s, _ = se[algo]
            d = mk[0] - m
            sd = math.sqrt(mk[1] ** 2 + s ** 2)
            row["value_vs_market_r"] = _r(d)
            row["value_ci95"] = [_r(d - Z95 * sd), _r(d + Z95 * sd)]
        measured = {a: v[0] for a, v in se.items()}
        best = min(measured, key=lambda a: measured[a]) if measured else None
        symbols[sym] = {"algos": algos, "best_measured": best,
                        "comparison": (MEASURED if len(measured) >= 2 else UNMEASURED),
                        "why": ("" if len(measured) >= 2 else
                                f"{len(measured)} algorithm(s) with >= {min_n} cases; a choice "
                                "needs two")}
    return {"unit": "R", "min_n": min_n, "n_cases": len(use), "symbols": symbols}
