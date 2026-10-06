#!/usr/bin/env python3
"""TRADE PATHOLOGY -- which of the desk's real trades went wrong in a way that is not the market.

A losing trade is the strategy's business. A trade that lost because it filled far from where the
signal priced it, gapped through its stop over a weekend, entered on a spread spike or was stopped
out inside a bar or two of entry is the MACHINE's business: those are execution and scheduling
defects, and each one has a fix that is not "a better signal". Nothing on this desk sorted the
live book's bad trades into those classes, so a slippage outlier and an honest stop-out read the
same in every P&L.

READ FROM THE LEDGERS THE GATEWAY ALREADY WRITES, never from a new store:

    desks/mt5/data/live_ledger.jsonl     closed deals: entry, exit, stop, target, R, close time
    desks/mt5/data/order_intents.jsonl   the decision: intended price, bid/ask, spread, time
    desks/mt5/data/fill_corpus.jsonl     fill_recorder's join (order outcome, rejects, retcodes)
    desks/mt5/data/universe/universe.json  median spread and point size per symbol

joined on the bridge MT5 offers (`intent.ticket == deal.entry_order`, then `== position_id`).

THE CLASSES, each with the threshold it uses written into the artifact:

    SLIPPAGE_OUTLIER    adverse entry slippage beyond the pooled robust bar (median + 3.5 MAD, in
                        R) AND beyond twice the symbol's median spread
    FAR_FROM_SIGNAL     the entry filled more than 0.25R from the price the signal asked for,
                        either direction (a stale signal or a mis-priced pending order)
    EARLY_STOPOUT       stopped out within N bars (default 3 H1 bars) of the decision
    WEEKEND_GAP         the position was held across a weekend and exited worse than its stop
    STOP_SLIPPAGE       exited worse than its stop by more than 0.2R without a weekend in between
    SPREAD_SPIKE        the spread at decision was more than 3x the symbol's median spread

UNMEASURED IS A VERDICT (L1.28a): a class whose inputs are absent for every trade (no joined
intent, no stop, no spread) reads UNMEASURED with its reason and its n, never zero. Below
MIN_JOIN_COVERAGE (half the deals joined to their intent) the reading is PARTIAL, with the join
rate published, and a book with no join at all is UNMEASURED.

REPORT ONLY. It vetoes, sizes and routes nothing; the fixes it points at are for the execution
owners to make on evidence.

    python desks/mt5/research/trade_pathology.py --once [--early-bars 3]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
LEDGER = DATA / "live_ledger.jsonl"
INTENTS = DATA / "order_intents.jsonl"
CORPUS = DATA / "fill_corpus.jsonl"
UNIVERSE = DATA / "universe" / "universe.json"
OUT = DESK / "reports" / "TRADE_PATHOLOGY.json"

SCHEMA = "trade-pathology/1"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
PARTIAL = "PARTIAL"

#: MINIMUM JOIN COVERAGE (audit 2026-10-06). Five of the six classes need the deal joined to its
#: intent; a book where 3 of 151 deals joined (2%) was published as MEASURED, so "0 SPREAD_SPIKE"
#: there described three trades and silently stood in for the other 148. Below this share of
#: deals joined, the reading -- and every join-dependent class -- is PARTIAL with the join rate
#: published; with nothing joined at all it is UNMEASURED. Never a clean MEASURED on a sliver.
MIN_JOIN_COVERAGE = 0.5
#: The classes whose inputs come only through the deal->intent join.
JOIN_DEPENDENT = frozenset({"SLIPPAGE_OUTLIER", "FAR_FROM_SIGNAL", "EARLY_STOPOUT",
                            "WEEKEND_GAP", "SPREAD_SPIKE"})

#: Thresholds, published in the artifact so a reader can re-derive every flag.
EARLY_BARS = 3
BAR_SECONDS = 3600
FAR_FROM_SIGNAL_R = 0.25
STOP_OVERSHOOT_R = 0.2
SPREAD_SPIKE_X = 3.0
SLIP_MAD_Z = 3.5
SLIP_SPREAD_X = 2.0
MAX_FLAGGED_ROWS = 300

CLASSES: dict[str, str] = {
    "SLIPPAGE_OUTLIER": "adverse entry slippage beyond median + 3.5 MAD (R) and 2x median spread",
    "FAR_FROM_SIGNAL": "entry filled more than 0.25R from the signal's intended price",
    "EARLY_STOPOUT": "stopped out within N bars of the decision",
    "WEEKEND_GAP": "held across a weekend and exited worse than its stop",
    "STOP_SLIPPAGE": "exited worse than its stop by more than 0.2R, no weekend in between",
    "SPREAD_SPIKE": "spread at decision more than 3x the symbol's median spread",
}
#: The inputs each class needs; a class none of whose trades carry them is UNMEASURED.
NEEDS: dict[str, str] = {
    "SLIPPAGE_OUTLIER": "joined intent (intended price) and a stop distance",
    "FAR_FROM_SIGNAL": "joined intent (intended price) and a stop distance",
    "EARLY_STOPOUT": "joined intent (decision time) and a stop",
    "WEEKEND_GAP": "a stop, and a joined intent for the entry time",
    "STOP_SLIPPAGE": "a stop distance",
    "SPREAD_SPIKE": "joined intent with spread_at_decision and a registry median spread",
}


def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        return []
    return out


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _i(x: Any) -> int | None:
    v = _f(x)
    return int(v) if v is not None else None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _point(meta: dict[str, Any] | None, intent: dict[str, Any] | None) -> float | None:
    p = _f((intent or {}).get("point"))
    if p:
        return p
    digits = _i((meta or {}).get("digits"))
    return 10.0 ** -digits if digits is not None else None


def direction(deal: dict[str, Any]) -> int | None:
    """The POSITION's direction. The ledger's `side` is the CLOSING deal's type (0 = a buy that
    closes a short), so the stop's side of the entry is read first and `side` only as a fallback."""
    entry, sl = _f(deal.get("entry_price")), _f(deal.get("sl"))
    if entry is not None and sl is not None and sl != entry and sl > 0:
        return -1 if sl > entry else 1
    side = _i(deal.get("side"))
    if side in (0, 1):
        return -1 if side == 0 else 1
    return None


def _weekend_between(a: datetime, b: datetime) -> bool:
    """True when the interval [a, b] contains any part of a Saturday (UTC)."""
    if b <= a:
        return False
    days = (b.date() - a.date()).days
    return any((a.toordinal() + k) % 7 == 6 for k in range(days + 1)) and days >= 1


def classify(deal: dict[str, Any], intent: dict[str, Any] | None, meta: dict[str, Any] | None,
             early_bars: int = EARLY_BARS) -> dict[str, Any]:
    """Every fact the classes need for one closed trade, and which classes it trips.

    `flags` holds the classes the trade tripped; `measured` holds the classes whose inputs this
    trade carried (a trade can only be counted against a class it could have tripped)."""
    d = direction(deal)
    entry, exit_, sl = _f(deal.get("entry_price")), _f(deal.get("fill_price")), _f(deal.get("sl"))
    risk = abs(entry - sl) if entry is not None and sl is not None and sl > 0 else None
    risk = risk if risk else None
    closed = _ts(deal.get("time"))
    decided = _ts((intent or {}).get("time"))
    point = _point(meta, intent)
    med_spread_pts = _f((meta or {}).get("median_spread_pts"))
    out: dict[str, Any] = {
        "deal": deal.get("deal"), "symbol": deal.get("symbol"), "sleeve": deal.get("sleeve"),
        "account_kind": deal.get("account_kind"), "closed_at": deal.get("time"),
        "r_multiple": _f(deal.get("r_multiple")), "joined": intent is not None,
        "flags": [], "measured": []}
    if d is None:
        out["why"] = "direction unreadable (no stop and no side)"
        return out
    # The ledger's r_multiple is 0.0 on rows it could not reconstruct; the price path is not.
    if risk and entry is not None and exit_ is not None:
        out["price_r"] = round((exit_ - entry) * d / risk, 4)
    # --- exit against the stop
    if risk and exit_ is not None and sl is not None:
        overshoot_r = (sl - exit_) * d / risk          # >0: exited worse than the stop
        out["stop_overshoot_r"] = round(overshoot_r, 4)
        stopped = abs(exit_ - sl) <= 0.25 * risk or overshoot_r > 0
        out["stopped_out"] = stopped
        weekend = (decided is not None and closed is not None
                   and _weekend_between(decided, closed))
        out["held_over_weekend"] = weekend if decided is not None else UNMEASURED
        out["measured"].append("STOP_SLIPPAGE")
        if decided is not None:
            out["measured"].append("WEEKEND_GAP")
        if overshoot_r > STOP_OVERSHOOT_R:
            out["flags"].append("WEEKEND_GAP" if weekend else "STOP_SLIPPAGE")
        if decided is not None and closed is not None:
            held_s = (closed - decided).total_seconds()
            out["held_s"] = round(held_s, 1)
            out["measured"].append("EARLY_STOPOUT")
            if stopped and 0 <= held_s <= early_bars * BAR_SECONDS:
                out["flags"].append("EARLY_STOPOUT")
    # --- entry against the signal
    intended = _f((intent or {}).get("intended"))
    if intent is not None and intended is not None and entry is not None and risk:
        slip = (entry - intended) * d                  # >0: adverse
        out["entry_slip_r"] = round(slip / risk, 5)
        if point:
            out["entry_slip_pts"] = round(slip / point, 2)
        out["measured"] += ["FAR_FROM_SIGNAL", "SLIPPAGE_OUTLIER"]
        if abs(slip) / risk > FAR_FROM_SIGNAL_R:
            out["flags"].append("FAR_FROM_SIGNAL")
    # --- spread at decision
    spread = _f((intent or {}).get("spread_at_decision"))
    if spread is not None and point and med_spread_pts:
        pts = spread / point
        out["spread_pts_at_decision"] = round(pts, 2)
        out["median_spread_pts"] = med_spread_pts
        out["measured"].append("SPREAD_SPIKE")
        if pts > SPREAD_SPIKE_X * med_spread_pts:
            out["flags"].append("SPREAD_SPIKE")
    return out


def _mad_bar(xs: list[float]) -> float | None:
    if len(xs) < 5:
        return None
    med = statistics.median(xs)
    mad = statistics.median([abs(x - med) for x in xs])
    return med + SLIP_MAD_Z * 1.4826 * mad if mad > 0 else None


def join(deals: list[dict[str, Any]],
         intents: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """deal index -> the intent that opened it (ticket == entry_order, then == position_id)."""
    by_ticket: dict[int, dict[str, Any]] = {}
    for it in intents:
        t = _i(it.get("ticket"))
        if t:
            by_ticket.setdefault(t, it)
    out: dict[int, dict[str, Any]] = {}
    for k, d in enumerate(deals):
        for key in ("entry_order", "position_id"):
            t = _i(d.get(key))
            if t and t in by_ticket:
                out[k] = by_ticket[t]
                break
    return out


def build(ledger: Path | None = None, intents_p: Path | None = None,
          corpus: Path | None = None, universe: Path | None = None,
          early_bars: int = EARLY_BARS) -> dict[str, Any]:
    deals = _read_jsonl(ledger or LEDGER)
    intents = _read_jsonl(intents_p or INTENTS)
    fills = _read_jsonl(corpus or CORPUS)
    try:
        uni = json.loads((universe or UNIVERSE).read_text("utf-8"))
        uni = uni if isinstance(uni, dict) else {}
    except (OSError, ValueError):
        uni = {}
    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {
        "schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
        "sources": {"ledger": "desks/mt5/data/live_ledger.jsonl",
                    "intents": "desks/mt5/data/order_intents.jsonl",
                    "fill_corpus": "desks/mt5/data/fill_corpus.jsonl",
                    "universe": "desks/mt5/data/universe/universe.json"},
        "thresholds": {"early_bars": early_bars, "bar_seconds": BAR_SECONDS,
                       "min_join_coverage": MIN_JOIN_COVERAGE,
                       "far_from_signal_r": FAR_FROM_SIGNAL_R,
                       "stop_overshoot_r": STOP_OVERSHOOT_R, "spread_spike_x": SPREAD_SPIKE_X,
                       "slip_mad_z": SLIP_MAD_Z, "slip_spread_x": SLIP_SPREAD_X},
        "classes_vocabulary": CLASSES,
        "rule": "report only: nothing here vetoes, sizes or routes an order",
    }
    if not deals:
        doc.update({"status": UNMEASURED, "why": "no closed deal in live_ledger.jsonl on this host",
                    "n_trades": 0, "classes": {c: {"status": UNMEASURED, "n_measured": 0,
                                                   "why": "no closed deal"} for c in CLASSES}})
        return doc
    joined = join(deals, intents)
    rows = [classify(d, joined.get(k), uni.get(str(d.get("symbol"))), early_bars)
            for k, d in enumerate(deals)]
    # SLIPPAGE_OUTLIER needs the pooled distribution, so it is judged after the per-trade pass.
    slips = [r["entry_slip_r"] for r in rows if "entry_slip_r" in r]
    bar = _mad_bar(slips)
    for r in rows:
        if "entry_slip_r" not in r:
            continue
        if bar is None:
            r["measured"] = [c for c in r["measured"] if c != "SLIPPAGE_OUTLIER"]
            continue
        med_pts = _f((uni.get(str(r.get("symbol"))) or {}).get("median_spread_pts"))
        beyond_spread = (med_pts is None or r.get("entry_slip_pts") is None
                         or r["entry_slip_pts"] > SLIP_SPREAD_X * med_pts)
        if r["entry_slip_r"] > bar and beyond_spread:
            r["flags"].append("SLIPPAGE_OUTLIER")
    classes: dict[str, Any] = {}
    for c in CLASSES:
        measured = [r for r in rows if c in r["measured"]]
        hit = [r for r in measured if c in r["flags"]]
        if not measured:
            classes[c] = {"status": UNMEASURED, "n_measured": 0,
                          "why": f"no trade carried the inputs: {NEEDS[c]}"}
            continue
        coverage = len(measured) / len(rows)
        partial = c in JOIN_DEPENDENT and coverage < MIN_JOIN_COVERAGE
        classes[c] = {
            "status": PARTIAL if partial else MEASURED, "n_measured": len(measured),
            "coverage": round(coverage, 6), "count": len(hit),
            "rate": round(len(hit) / len(measured), 6),
            "r_lost": round(sum(min(0.0, r.get("r_multiple") or r.get("price_r") or 0.0)
                                for r in hit), 4),
            "by_sleeve": dict(Counter(str(r.get("sleeve")) for r in hit).most_common(10)),
            "by_symbol": dict(Counter(str(r.get("symbol")) for r in hit).most_common(10)),
            "examples": [{k: r.get(k) for k in ("deal", "symbol", "sleeve", "closed_at",
                                                 "r_multiple", "price_r", "entry_slip_r",
                                                 "stop_overshoot_r", "held_s",
                                                 "spread_pts_at_decision")}
                         for r in hit[:5]],
        }
        if c == "SLIPPAGE_OUTLIER":
            classes[c]["bar_r"] = round(bar, 5) if bar is not None else None
        if partial:
            classes[c]["why"] = (f"only {len(measured)} of {len(rows)} trades carried the inputs "
                                 f"({coverage:.1%} < the {MIN_JOIN_COVERAGE:.0%} minimum): the "
                                 "count describes those trades, not the book")
    # Order-level pathologies the fill corpus already knows: rejects and unfilled orders.
    status = Counter(str(f.get("status")) for f in fills)
    retcodes = Counter(str(f.get("retcode")) for f in fills if f.get("rejected"))
    flagged = [r for r in rows if r["flags"]]
    by_account: dict[str, Counter[str]] = defaultdict(Counter)
    for r in flagged:
        for c in r["flags"]:
            by_account[str(r.get("account_kind"))][c] += 1
    join_rate = len(joined) / len(rows)
    if not joined:
        verdict, why = UNMEASURED, (f"none of {len(rows)} deals joined to an intent: the "
                                   "join-dependent classes cannot be read")
    elif join_rate < MIN_JOIN_COVERAGE:
        verdict, why = PARTIAL, (f"{len(joined)} of {len(rows)} deals joined ({join_rate:.1%}), "
                                f"below the {MIN_JOIN_COVERAGE:.0%} minimum join coverage")
    else:
        verdict, why = MEASURED, f"{join_rate:.1%} of deals joined to their intent"
    doc.update({
        "status": verdict, "why": why, "n_trades": len(rows), "n_joined": len(joined),
        "join_rate": round(join_rate, 6), "min_join_coverage": MIN_JOIN_COVERAGE,
        "n_flagged": len(flagged),
        "flag_rate": round(len(flagged) / len(rows), 6),
        "classes": classes,
        "by_account_kind": {k: dict(v) for k, v in by_account.items()},
        "orders": {"n": len(fills), "by_status": dict(status.most_common()),
                   "reject_retcodes": dict(retcodes.most_common())}
        if fills else {"status": UNMEASURED, "why": "fill_corpus.jsonl absent or empty"},
        "flagged": flagged[-MAX_FLAGGED_ROWS:],
        "top_class": max(((c, v.get("count", 0)) for c, v in classes.items()
                          if v.get("status") == MEASURED), key=lambda x: x[1],
                         default=(None, 0))[0],
    })
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--early-bars", type=int, default=EARLY_BARS)
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(early_bars=a.early_bars)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(a.out)
    counts = ", ".join(f"{c} {v.get('count', v.get('status'))}"
                       for c, v in (doc.get("classes") or {}).items())
    print(f"trade_pathology: {doc['status']} trades={doc.get('n_trades', 0)} "
          f"joined={doc.get('n_joined', 0)} flagged={doc.get('n_flagged', 0)} [{counts}] "
          f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
