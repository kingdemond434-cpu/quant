"""What the desk ASKED for versus what it GOT. The only honest measure of execution.

WHY THIS EXISTS

Every return figure this desk has ever produced assumes fills at exactly the bracket price. The
backtest engine fills a stop order at its trigger level, the battery charges a modelled spread and
commission on top, and nothing has ever checked either assumption against a real fill.

That assumption is worst exactly where this desk lives. Session-range breakout enters on STOP
orders into a fast move -- the single worst case for slippage, because the order becomes a market
order precisely when the book is thinnest and moving away. A backtest that fills those at the
trigger price is describing a trade nobody got.

THE PRECEDENT, from this same repository. The crypto desk's cost surface said 0.35bps for a BNB
round trip; its own fills said ~16bps. Fifty times. The entry gate had been admitting carries that
needed twelve days of funding to repay one entry, and every hold bucket came back negative while
the gate believed it was selecting winners. That desk found it only after someone compared
intents to fills. This module is that comparison, wired from the first trade rather than after a
bad quarter.

WHAT IT MEASURES

    entry_slip = (fill - intended) * direction        quote units, SIGNED
                                                      positive = worse than asked

Signed and direction-adjusted, because a buy filled ABOVE its trigger and a sell filled BELOW its
trigger are the same event and must not cancel each other in a mean. Reported in R as well as in
account currency, since R is the unit every gate and sizing decision on this desk is written in:
a 0.10R average slip is not a rounding error, it is 63% of the gold book's +0.159R edge.

THE R DENOMINATOR IS THE INTENT'S STOP DISTANCE IN PRICE (2026-10-14, agreed with the
Max-growth lane, whose #391 rebases on this). `slip_r` was `slip_quote / risk_quote`, and the live
ledger's `risk_quote` is ACCOUNT MONEY at the traded lot (4.00 EUR on a 0.01-lot gold short, 10.81
on a 0.03-lot one), not a price distance: FX rows read ~1e-5 R whatever they slipped, and one gold
short whose stop sat 0.10 from its fill (ticket 222937609, risk_quote 0.087 EUR) read -44.3R and
alone moved the book mean to -0.20R. `slip_r` is now price over price (`slip_stop_frac`); the old
quotient is kept as `slip_r_money` for audit only, and the pooled `mean_slip_r` averages the
CLEAN (non-quarantined) rows. Slip is reported here and charged nowhere.

THE SIGN IS UNCHANGED AND IT IS NOT INVERTED: positive is a COST (filled worse than asked),
negative is price IMPROVEMENT. A negative `edge_share` therefore says execution GAVE edge, not
that it ate it. The 2026-10-13 reading "-0.202R eats 127% of the edge" read the sign backwards and
the magnitude through the unit defect above; both readings are retired by `slip_breakdown`, which
states the sign in its own payload.

IMPLAUSIBLE ROWS ARE QUARANTINED BY NAME, NEVER DROPPED. A fill more than half the intent's own
stop distance from its intended price (price over price, so the unit is coherent on every symbol), or more than 20 decision-time spreads from it, is not slippage: it is a
stale intended price (the signal's reference rather than the live quote) or a mis-joined deal.
Such rows stay in the pooled all-rows figures (existing readers see every fill) and are listed
with their reasons; the `clean` statistics beside them exclude them.

WHAT IT REFUSES TO DO

Infer. An intent with no matching deal is an UNFILLED bracket, not a zero-slippage fill, and it is
reported separately -- counting it as zero would drag the mean toward "no slippage" using orders
that never traded, the same fabrication as writing 0.0 for a day a sleeve did not trade. A deal
with no matching intent is reported too: it means something placed an order this module cannot
account for, which is a reconciliation problem and not a statistic.

    python -m mt5desk.markout            # once trades exist
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mt5desk.provenance import DEMO, UNKNOWN, row_account, split_by_account

#: MT5 order type constants, inlined so this module imports on a research box where the
#: MetaTrader5 package does not exist. Fixed by the platform, not by the broker.
_BUY_TYPES = {0, 2, 4}       # BUY, BUY_LIMIT, BUY_STOP
_SELL_TYPES = {1, 3, 5}      # SELL, SELL_LIMIT, SELL_STOP


def _direction(side: Any) -> int:
    """+1 long, -1 short, 0 unknown. Accepts the numeric deal type or the intent's side string."""
    if isinstance(side, str):
        s = side.lower()
        if "buy" in s:
            return 1
        if "sell" in s:
            return -1
        return 0
    try:
        t = int(side)
    except (TypeError, ValueError):
        return 0
    return 1 if t in _BUY_TYPES else (-1 if t in _SELL_TYPES else 0)


@dataclass(frozen=True)
class Markout:
    n_deals: int
    n_matched: int
    n_unfilled_intents: int
    n_unmatched_deals: int
    mean_slip_quote: float
    median_slip_quote: float
    worst_slip_quote: float
    #: None when no matched row carries a stop or every one is quarantined (L1.28a): never 0.0.
    mean_slip_r: float | None
    edge_share: float | None
    rows: list[dict[str, Any]]
    why: str = ""
    #: Which kind of account produced these fills. A markout is only meaningful against one.
    account_kind: str = UNKNOWN
    mixed: bool = False
    #: Deals the desk can walk back to an intent, whether or not both prices survived. The
    #: attribution number the review found at zero: target is every deal this magic placed.
    attributed_deals: int = 0
    #: One row per attributed deal: intent -> release/state -> entry order/deal -> close deal ->
    #: realised R. The chain, materialised, so "which research made this euro" is a lookup.
    chain: list[dict[str, Any]] = field(default_factory=list)
    #: Per-sleeve and per-(symbol, broker hour) slip, with the quarantine; see `slip_breakdown`.
    slip: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.n_matched > 0 and not self.mixed

    @property
    def attributed_share(self) -> float | None:
        return (self.attributed_deals / self.n_deals) if self.n_deals else None


#: The ledger fields that can carry the intent's ticket, in the order they are trusted. For a
#: pending stop the entry order's ticket IS the position id; `order` on a CLOSING deal is the
#: server's stop/target order and matches nothing, and is kept last only for rows written before
#: the position id was recorded.
_JOIN_KEYS = ("entry_order", "position_id", "order")


def _join_ticket(deal: dict, by_ticket: dict) -> Any:
    for key in _JOIN_KEYS:
        value = deal.get(key)
        if value is not None and value in by_ticket:
            return value
    return None


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def position_direction(deal: dict) -> int:
    """+1 / -1 for the POSITION a live-ledger row closed. 0 when nothing on the row says.

    THE LEDGER'S `side` IS THE CLOSING DEAL'S TYPE, NOT THE POSITION'S (measured 2026-09-30 on
    the 151 committed live deals: 112 closing BUYS whose stop sits above the entry -- shorts -- and
    39 closing SELLS whose stop sits below it -- longs; 151 of 151 opposite). Every reader that
    took `side` as the trade's direction inverted it: the symbol/minute fallback could never pair
    an intent with its own fill, and the slippage sign below flipped on every short.

    Order of trust: `entry_side` (the opening deal's own type, on rows written since the gateway
    started recording it), then the stop/target geometry around the entry, then the closing side
    inverted.
    """
    es = deal.get("entry_side")
    if es is not None:
        d = _direction(es)
        if d:
            return d
    entry, sl, tp = _num(deal.get("entry_price")), _num(deal.get("sl")), _num(deal.get("tp"))
    if entry and entry > 0:
        if sl and sl > 0 and sl != entry:
            return 1 if sl < entry else -1
        if tp and tp > 0 and tp != entry:
            return 1 if tp > entry else -1
    closing = _direction(deal.get("side"))
    return -closing


def _echo(sent: Any, held: Any) -> bool:
    """True when `held` (the position's stop or target, as the venue stores it) is `sent` (the
    number the gateway asked for) rounded to the venue's digits.

    The venue rounds: the gateway sent 4339.891681552983 and the position holds 4339.89. The
    tolerance is half a point of the HELD value's own printed precision, so 4339.89 accepts
    anything within 0.005 and 0.85669 anything within 0.000005 -- read off the row, never assumed.
    """
    x, y = _num(sent), _num(held)
    if x is None or y is None or x <= 0 or y <= 0:
        return False
    txt = f"{y:.8f}".rstrip("0")
    dec = len(txt.split(".")[1]) if "." in txt else 0
    tol = 0.5 * (10.0 ** -max(dec, 1)) + 1e-9 * abs(y)
    return abs(x - y) <= tol


def _stamp(x: Any) -> float | None:
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def echo_join(intents: list[dict], deals: list[dict], used_intents: set[int],
              used_deals: set[Any]) -> list[tuple[dict, dict]]:
    """Pair a deal that carries NO entry-order key with the intent whose stop and target the
    position still holds.

    THE LEGACY ROWS. Deals recorded before 2026-09-08 carry only `order`, which on a closing deal
    is the server's own stop/target order -- a ticket the desk never saw -- so no ticket join can
    ever reach them. What they DO carry is the position's stop and target, and the gateway wrote
    the same two numbers onto the intent it sent: an exact echo (to half a point), on the same
    symbol, in the same POSITION direction, from an intent that the venue accepted (ticket > 0)
    and was sent no later than the row was recorded. Measured on the committed ledgers: 13 of 13
    key-less deals find exactly one such intent (two of them share one stop/target pair across two
    tickets and take them one each, in time order). A position whose stop was moved no longer
    echoes and stays unjoined, which is the conservative outcome.

    `used_intents` holds `id()` of intents already consumed; `used_deals` the deal tickets. Both
    are updated in place. One-to-one; each deal takes the LATEST qualifying intent before it.
    """
    out: list[tuple[dict, dict]] = []
    for d in deals:
        if d.get("entry_order") is not None or d.get("position_id") is not None:
            continue
        if d.get("deal") in used_deals:
            continue
        dirn = position_direction(d)
        t_deal = _stamp(d.get("entry_time")) or _stamp(d.get("time"))
        best, best_t = None, None
        for it in intents:
            if id(it) in used_intents:
                continue
            try:
                if int(it.get("ticket") or 0) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            if str(it.get("symbol") or "") != str(d.get("symbol") or ""):
                continue
            if dirn and _direction(it.get("side")) != dirn:
                continue
            if not (_echo(it.get("sl"), d.get("sl")) and _echo(it.get("tp"), d.get("tp"))):
                continue
            ti = _stamp(it.get("time"))
            if t_deal is not None and ti is not None and ti > t_deal:
                continue
            if best is None or (ti is not None and (best_t is None or ti > best_t)):
                best, best_t = it, ti
        if best is None:
            continue
        used_intents.add(id(best))
        used_deals.add(d.get("deal"))
        out.append((best, d))
    return out


def _entry_fill(deal: dict) -> Any:
    """The price the ENTRY executed at. A closing deal's `fill_price` is the exit; slippage
    against the intended entry must use the position's opening deal."""
    try:
        if float(deal.get("entry_price") or 0.0) > 0:
            return deal["entry_price"]
    except (TypeError, ValueError):
        pass
    return deal.get("fill_price")


def load_jsonl(path: Path) -> list[dict]:
    from libs.ops.live_ledger_view import ledger_path

    if not path.exists():
        return []
    out = []
    for line in ledger_path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


#: SIGN, stated in every payload so no reader has to infer it.
SLIP_SIGN = ("positive = cost (filled worse than intended); negative = price improvement. "
             "slip_quote = (fill - intended) * direction")
#: A sleeve or cell with fewer clean fills than this is flagged `n_small`: its mean is reported
#: but a reader must shrink it (see research.entry_hour_cost.hour_slip_pts).
SLIP_N_SMALL = 10
#: |slip| above this share of the intent's own stop distance (price / price) is not slippage.
IMPLAUSIBLE_STOP_FRAC = 0.5
#: |slip| above this many decision-time spreads is not slippage either.
IMPLAUSIBLE_SPREAD_MULT = 20.0
_BROKER_TZ = ZoneInfo("America/New_York")


def broker_hour(ts_utc: Any) -> int | None:
    """The venue's stamp hour (New York wall clock + 7 h, the cost surface's clock) at a UTC
    instant, or None. Same conversion as libs.regime.session_clock, without pandas."""
    from datetime import UTC, datetime, timedelta
    try:
        t = datetime.fromisoformat(str(ts_utc).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return (t.astimezone(_BROKER_TZ) + timedelta(hours=7)).hour


def _stop_distance(intent: dict, deal: dict, want: float, got: float) -> tuple[float | None, str]:
    """The intent's stop distance in PRICE, and where it was read (for the quarantine rule only;
    never `risk_quote`, which is account money)."""
    sl = _num(intent.get("sl"))
    if sl is not None and sl > 0 and abs(want - sl) > 0:
        return abs(want - sl), "intent_stop"
    dsl = _num(deal.get("sl"))
    if dsl is not None and dsl > 0 and abs(got - dsl) > 0:
        return abs(got - dsl), "position_stop"
    return None, "UNMEASURED: no stop on the intent or the position"


def surface_points(path: Path | None = None) -> dict[str, float]:
    """symbol -> point (tick_size) from the cost surface, for intents written before the gateway
    recorded `point`. Empty when the surface is unreadable: points are then UNMEASURED (None)."""
    try:
        if path is None:
            from mt5desk.config import DATA
            path = DATA / "cost_surface.json"
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return {}
    out = {}
    for sym, row in ((doc or {}).get("symbols") or {}).items():
        ts = _num((row or {}).get("tick_size")) if isinstance(row, dict) else None
        if ts and ts > 0:
            out[str(sym)] = ts
    return out


def _quarantine(row: dict) -> list[str]:
    why = []
    f = row.get("slip_stop_frac")
    if f is not None and abs(f) > IMPLAUSIBLE_STOP_FRAC:
        why.append(f"|slip| is {abs(f):.3f} of the intent's stop distance (> "
                   f"{IMPLAUSIBLE_STOP_FRAC}): stale intended price or mis-joined deal, "
                   "not slippage")
    # Market orders only: a pending stop's decision spread is hours older than its fill, and a
    # stop filled through a fast move is exactly the slippage this module exists to measure.
    pts, spr = row.get("slip_pts"), row.get("spread_pts_at_decision")
    if not row.get("pending") and pts is not None and spr is not None and spr > 0 \
            and abs(pts) > IMPLAUSIBLE_SPREAD_MULT * spr:
        why.append(f"|slip| {abs(pts):.1f} pts > {IMPLAUSIBLE_SPREAD_MULT:g} x the "
                   f"{spr:.1f}-pt spread at decision")
    return why


def _q(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolated quantile of an already-sorted list."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    x = p * (len(sorted_vals) - 1)
    lo = int(x)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (x - lo)


def _stats(vals: list[float | None]) -> dict[str, Any]:
    v = sorted(float(x) for x in vals if x is not None)
    if not v:
        return {"n": 0, "mean": None, "median": None, "p75": None, "status": "UNMEASURED"}
    return {"n": len(v), "mean": sum(v) / len(v), "median": _q(v, 0.5), "p75": _q(v, 0.75),
            "status": "MEASURED"}


#: What the breakdown's R column is.
R_UNITS = "slip_quote / |intended - intent stop| (price over price; slip_stop_frac)"


def _block(rows: list[dict]) -> dict[str, Any]:
    clean = [r for r in rows if not r.get("quarantine")]
    out: dict[str, Any] = {"n": len(rows), "n_quarantined": len(rows) - len(clean),
                           "n_clean": len(clean), "n_small": len(clean) < SLIP_N_SMALL}
    for tag, rs in (("all", rows), ("clean", clean)):
        blk = {u: _stats([r.get(f"slip_{u}") for r in rs]) for u in ("quote", "pts")}
        blk["r"] = _stats([r.get("slip_stop_frac") for r in rs])
        out[tag] = blk
    return out


def slip_breakdown(rows: list[dict]) -> dict[str, Any]:
    """Per sleeve, per symbol and per (symbol, broker hour-of-day): n, mean, median and p75 slip in
    quote (price), in points and in R (of the intent's stop), over ALL rows and over the CLEAN
    (non-quarantined) rows, with every
    quarantined row listed and its reason. Cells are keyed on the broker hour so they line up with
    the cost surface's `hours` cells."""
    def group(key: Any) -> dict[str, list[dict]]:
        g: dict[str, list[dict]] = {}
        for r in rows:
            k = key(r)
            if k is not None:
                g.setdefault(str(k), []).append(r)
        return g

    by_symbol_hour: dict[str, dict[str, Any]] = {}
    for sym, rs in group(lambda r: r.get("symbol")).items():
        hours: dict[str, list[dict]] = {}
        for r in rs:
            h = r.get("broker_hour")
            hours.setdefault("unknown" if h is None else str(h), []).append(r)
        by_symbol_hour[sym] = {h: _block(v) for h, v in sorted(hours.items())}
    return {
        "sign": SLIP_SIGN,
        "units": {"quote": "price units", "pts": "slip_quote / the intent's point",
                  "r": R_UNITS},
        "hour_clock": "broker (New York + 7 h), the cost surface's clock; from the entry time "
                      "when the ledger has it, else the intent's send time",
        "rule": {"n_small_below": SLIP_N_SMALL,
                 "implausible_abs_stop_frac": IMPLAUSIBLE_STOP_FRAC,
                 "implausible_spread_mult": IMPLAUSIBLE_SPREAD_MULT,
                 "quarantine": "flagged and listed, kept in `all`, excluded from `clean`"},
        "pooled": _block(rows),
        "by_sleeve": {k: _block(v) for k, v in sorted(group(lambda r: r.get("sleeve")).items())},
        "by_symbol": {k: _block(v) for k, v in sorted(group(lambda r: r.get("symbol")).items())},
        "by_symbol_hour": by_symbol_hour,
        "quarantined": [{k: r.get(k) for k in ("sleeve", "symbol", "deal", "order", "time",
                                                "pending", "intended", "fill", "stop_distance",
                                                "slip_stop_frac", "slip_quote",
                                                "slip_pts", "slip_r", "quarantine")}
                        for r in rows if r.get("quarantine")],
    }


def compute(intents: list[dict], deals: list[dict],
            book_edge_r: float = 0.159, points: dict[str, float] | None = None) -> Markout:
    """Join intents to deals by order ticket and measure the gap.

    `book_edge_r` is the armed gold book's measured expectancy, used only to express slippage as
    a FRACTION OF THE EDGE. That ratio is the number that matters: slippage is not a cost to be
    noted, it is a direct subtraction from the only thing being harvested, and an execution
    problem is invisible in currency terms while being fatal in R terms.
    """
    # ONE ACCOUNT AT A TIME. Averaging a demo fill with a live one produces a number describing
    # neither, and the direction of the error is not conservative: a demo server fills stops at
    # the trigger with no slippage, so every demo row drags the mean toward "no slippage" using
    # trades that could not have slipped. Segregate and refuse rather than blend.
    accounts = {k for k in split_by_account(deals)} if deals else set()
    kinds = {k[2] for k in accounts}
    if len(accounts) > 1:
        listed = ", ".join(f"{login or '?'}@{server or '?'}/{kind}"
                           for login, server, kind in sorted(accounts, key=str))
        return Markout(len(deals), 0, len(intents), 0, 0.0, 0.0, 0.0, 0.0, None, [],
                       why=(f"MIXED ledger -- fills from {len(accounts)} accounts ({listed}). A "
                            "markout across accounts describes none of them; demo fills do not "
                            "slip, so blending them understates live cost. Split the ledger."),
                       account_kind=UNKNOWN, mixed=True)
    kind = next(iter(kinds)) if kinds else UNKNOWN

    pts_of = surface_points() if points is None else points
    by_ticket = {}
    for i in intents:
        t = i.get("ticket")
        if t is not None:
            by_ticket[t] = i

    rows, chain, unmatched = [], [], 0
    matched_tickets = set()
    # THE LEGACY ROWS, JOINED ON THE STOP/TARGET ECHO (2026-09-30). A deal with no entry-order key
    # can never reach an intent by ticket; `echo_join` pairs it with the one intent whose stop and
    # target the position still carries. Intents a ticket already claims are excluded first.
    keyed: set[int] = set()
    for d in deals:
        kt = _join_ticket(d, by_ticket)
        if kt is not None and d.get("entry_order") is not None:
            keyed.add(id(by_ticket[kt]))
    echoed = {id(d): it for it, d in echo_join(intents, deals, keyed, set())}
    for d in deals:
        # THE JOIN (2026-09-08). It was `d["order"]` against the intent's ticket: a closing
        # deal's order is the server's stop/target order, so nothing ever matched and the
        # "fill" it would have compared was the exit price. The position id is the bridge MT5
        # offers, and the gateway now writes it beside the entry order and entry deal.
        t = _join_ticket(d, by_ticket)
        intent = by_ticket.get(t) if t is not None else None
        if intent is None and id(d) in echoed:
            intent = echoed[id(d)]
            t = intent.get("ticket")
        if intent is None:
            unmatched += 1
            continue
        matched_tickets.add(t)
        want = intent.get("intended")
        got = _entry_fill(d)
        link = {
            "sleeve": d.get("sleeve") or intent.get("sleeve"),
            "symbol": d.get("symbol") or intent.get("symbol"),
            "intent_time": intent.get("time"), "release_id": intent.get("release_id"),
            "state_vector_id": intent.get("state_vector_id"), "ticket": t,
            "position_id": d.get("position_id"), "entry_deal": d.get("entry_deal"),
            "close_deal": d.get("deal"), "closed_at": d.get("time"),
            "intended": want, "entry": got, "realized_r": d.get("r_multiple"),
            "pl_quote": d.get("pl_quote"),
        }
        chain.append(link)
        if want is None or got is None:
            continue
        # THE INTENT'S SIDE, THEN THE POSITION'S. The ledger's `side` is the CLOSING deal's type
        # (opposite to the position on 151 of 151 committed rows), so reading it first flipped
        # the sign of every short's slippage.
        dirn = _direction(intent.get("side")) or position_direction(d)
        if dirn == 0:
            continue
        slip_quote = (float(got) - float(want)) * dirn
        link["slip_quote"] = slip_quote
        stop, stop_basis = _stop_distance(intent, d, float(want), float(got))
        risk = float(d.get("risk_quote") or 0.0)
        symbol = d.get("symbol") or intent.get("symbol")
        point = _num(intent.get("point")) or pts_of.get(str(symbol))
        side_txt = str(intent.get("side") or "").lower()
        pending = (str(intent.get("order_type") or "").startswith("pending")
                   or side_txt.endswith(("_stop", "_limit")))
        spread_q = _num(intent.get("spread_at_decision"))
        when = d.get("entry_time") or intent.get("sent_at") or intent.get("time")
        row = {
            "sleeve": d.get("sleeve") or intent.get("sleeve"),
            "symbol": symbol, "pending": pending,
            "intended": float(want), "fill": float(got),
            "slip_quote": slip_quote,
            # Price over price: slip in units of the intent's own stop. See the docstring.
            "slip_r": (slip_quote / stop) if stop else None,
            "slip_r_money": (slip_quote / risk) if risk > 0 else None,
            "stop_distance": stop, "stop_basis": stop_basis,
            "slip_stop_frac": (slip_quote / stop) if stop else None,
            "slip_pts": (slip_quote / point) if point and point > 0 else None,
            "spread_pts_at_decision": ((spread_q / point) if spread_q is not None and point
                                       and point > 0 else None),
            "time": when, "broker_hour": broker_hour(when),
            "deal": d.get("deal"), "order": t,
        }
        row["quarantine"] = _quarantine(row)
        rows.append(row)

    # An intent with no deal is an UNFILLED bracket -- the 20:30 cancel, or a range never broken.
    # Never counted as a zero-slippage fill.
    unfilled = sum(1 for t in by_ticket if t not in matched_tickets)

    if not rows:
        return Markout(len(deals), 0, unfilled, unmatched, 0.0, 0.0, 0.0, 0.0, None, [],
                       why=("no matched intent/deal pairs yet. Nothing has filled, or the gateway "
                            "predates intent recording. This is NOT a clean bill of health -- "
                            "execution is UNMEASURED until a fill exists."),
                       account_kind=kind, attributed_deals=len(chain), chain=chain)

    sq = sorted(r["slip_quote"] for r in rows)
    srs = [r["slip_r"] for r in rows if r["slip_r"] is not None and not r.get("quarantine")]
    mean_r = (sum(srs) / len(srs)) if srs else None
    return Markout(
        n_deals=len(deals), n_matched=len(rows), n_unfilled_intents=unfilled,
        n_unmatched_deals=unmatched,
        mean_slip_quote=sum(sq) / len(sq),
        median_slip_quote=sq[len(sq) // 2],
        worst_slip_quote=sq[-1],
        mean_slip_r=mean_r,
        edge_share=(mean_r / book_edge_r) if book_edge_r and mean_r is not None else None,
        rows=rows,
        why=("matched on the position id (entry order == intent ticket), and legacy key-less "
             "deals on the exact stop/target echo; slip against the ENTRY fill, signed by the "
             "intent's side (the ledger's `side` is the closing deal's) so a bad buy and a bad "
             "sell do not cancel"),
        account_kind=kind, attributed_deals=len(chain), chain=chain,
        slip=slip_breakdown(rows))


def _attribution_line(m: Markout) -> str:
    share = m.attributed_share
    return (f"  attributed deals     {m.attributed_deals}/{m.n_deals}"
            + (f"  ({share * 100:.0f}% -- target 100%)" if share is not None else ""))


def render(m: Markout) -> str:
    L = ["EXECUTION MARKOUT -- intended versus filled", ""]
    if not m.usable:
        L += [f"  {m.why}", "",
              f"  deals seen {m.n_deals} | intents awaiting a fill {m.n_unfilled_intents}",
              _attribution_line(m)]
        return "\n".join(L)
    L += [_attribution_line(m),
          f"  matched fills        {m.n_matched}",
          f"  unfilled brackets    {m.n_unfilled_intents}   (cancelled or never triggered)",
          f"  unmatched deals      {m.n_unmatched_deals}   "
          f"{'<- RECONCILE: orders this desk cannot account for' if m.n_unmatched_deals else ''}",
          "",
          f"  mean slip            {m.mean_slip_quote:+.5f} quote  "
          + (f"({m.mean_slip_r:+.4f} R)" if m.mean_slip_r is not None
             else "(R UNMEASURED: no clean row with a stop)"),
          f"  median slip          {m.median_slip_quote:+.5f} quote",
          f"  worst slip           {m.worst_slip_quote:+.5f} quote"]
    pooled = (m.slip or {}).get("pooled") or {}
    clean_pts = ((pooled.get("clean") or {}).get("pts") or {}).get("mean")
    if pooled:
        L += [f"  quarantined rows     {pooled.get('n_quarantined', 0)}   (implausible; listed, "
              "kept in the quote mean, excluded from R)",
              (f"  clean mean slip      {clean_pts:+.2f} points" if clean_pts is not None
               else "  clean mean slip      UNMEASURED"),
              "  sign: positive = cost, negative = price improvement"]
    L.append("")
    if m.account_kind == DEMO:
        L += ["  MEASURED ON A DEMO ACCOUNT -- not evidence of live execution.",
              "  A demo server has no liquidity behind it and fills stop orders at the trigger",
              "  price. A clean result here is the null outcome a server that CANNOT slip always",
              "  produces, so it confirms nothing about the assumption this module tests. What a",
              "  demo run does prove: contract sizes, stop and freeze levels, symbol suffixes,",
              "  session hours, margin maths, and whether orders are accepted at all.", ""]
    elif m.account_kind == UNKNOWN:
        L += ["  ACCOUNT UNKNOWN -- these fills predate provenance stamping, so the desk cannot",
              "  say whether they are demo or live. Treat as unmeasured.", ""]
    if m.edge_share is not None:
        pct = m.edge_share * 100.0
        verdict = ("execution is eating the edge" if pct >= 50 else
                   "material" if pct >= 20 else "tolerable")
        L += [f"  slippage as a share of the book's +0.159R edge: {pct:.1f}%  -- {verdict}", ""]
        if pct >= 20:
            L.append("  Every backtest figure on this desk assumes fills AT the bracket price.")
            L.append("  Re-run the cost model with this measured slip before sizing on them.")
    return "\n".join(L)


def main() -> int:
    from mt5desk.config import DATA
    from libs.ops.live_ledger_view import ledger_path as _audited_ledger_path
    m = compute(load_jsonl(DATA / "order_intents.jsonl"),
                load_jsonl(_audited_ledger_path(DATA / "live_ledger.jsonl")))
    print(render(m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
