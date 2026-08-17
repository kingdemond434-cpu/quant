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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    @property
    def usable(self) -> bool:
        return self.n_matched > 0


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
    by_ticket = {}
    for i in intents:
        t = i.get("ticket")
        if t is not None:
            by_ticket[t] = i

    rows, unmatched = [], 0
    matched_tickets = set()
    for d in deals:
        t = d.get("order")
        intent = by_ticket.get(t) if t is not None else None
        if intent is None:
            unmatched += 1
            continue
        matched_tickets.add(t)
        want = intent.get("intended")
        got = d.get("fill_price")
        if want is None or got is None:
            continue
        dirn = _direction(d.get("side", intent.get("side")))
        if dirn == 0:
            continue
        slip_quote = (float(got) - float(want)) * dirn
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
                            "execution is UNMEASURED until a fill exists."))

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
        why="matched on order ticket; slip signed so a bad buy and a bad sell do not cancel")


def render(m: Markout) -> str:
    L = ["EXECUTION MARKOUT -- intended versus filled", ""]
    if not m.usable:
        L += [f"  {m.why}", "",
              f"  deals seen {m.n_deals} | intents awaiting a fill {m.n_unfilled_intents}"]
        return "\n".join(L)
    L += [f"  matched fills        {m.n_matched}",
          f"  unfilled brackets    {m.n_unfilled_intents}   (cancelled or never triggered)",
          f"  unmatched deals      {m.n_unmatched_deals}   "
          f"{'<- RECONCILE: orders this desk cannot account for' if m.n_unmatched_deals else ''}",
          "",
          f"  mean slip            {m.mean_slip_quote:+.5f} quote  ({m.mean_slip_r:+.4f} R)",
          f"  median slip          {m.median_slip_quote:+.5f} quote",
          f"  worst slip           {m.worst_slip_quote:+.5f} quote", ""]
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
