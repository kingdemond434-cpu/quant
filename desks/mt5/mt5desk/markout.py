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
    mean_slip_r: float
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
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
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


def compute(intents: list[dict], deals: list[dict],
            book_edge_r: float = 0.159) -> Markout:
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
        risk = float(d.get("risk_quote") or 0.0)
        rows.append({
            "sleeve": d.get("sleeve"), "symbol": d.get("symbol"),
            "intended": float(want), "fill": float(got),
            "slip_quote": slip_quote,
            "slip_r": (slip_quote / risk) if risk > 0 else None,
            "deal": d.get("deal"), "order": t,
        })

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
    srs = [r["slip_r"] for r in rows if r["slip_r"] is not None]
    mean_r = (sum(srs) / len(srs)) if srs else 0.0
    return Markout(
        n_deals=len(deals), n_matched=len(rows), n_unfilled_intents=unfilled,
        n_unmatched_deals=unmatched,
        mean_slip_quote=sum(sq) / len(sq),
        median_slip_quote=sq[len(sq) // 2],
        worst_slip_quote=sq[-1],
        mean_slip_r=mean_r,
        edge_share=(mean_r / book_edge_r) if book_edge_r else None,
        rows=rows,
        why=("matched on the position id (entry order == intent ticket), and legacy key-less "
             "deals on the exact stop/target echo; slip against the ENTRY fill, signed by the "
             "intent's side (the ledger's `side` is the closing deal's) so a bad buy and a bad "
             "sell do not cancel"),
        account_kind=kind, attributed_deals=len(chain), chain=chain)


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
          f"  mean slip            {m.mean_slip_quote:+.5f} quote  ({m.mean_slip_r:+.4f} R)",
          f"  median slip          {m.median_slip_quote:+.5f} quote",
          f"  worst slip           {m.worst_slip_quote:+.5f} quote", ""]
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
    m = compute(load_jsonl(DATA / "order_intents.jsonl"),
                load_jsonl(DATA / "live_ledger.jsonl"))
    print(render(m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
