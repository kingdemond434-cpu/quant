"""Theoretical sleeve positions, netted into one portfolio target per instrument.

WonderTrader's separation, reimplemented: each sleeve keeps its THEORETICAL position (what its
strategy wants, in lots, signed) and its own virtual P&L; the venue sees only the NET target per
symbol. Two sleeves long and short the same instrument at once do not pay two spreads, two
swaps and double margin to hold a position the account does not have.

    theoretical:  A XAUUSD +0.20   B XAUUSD -0.08   C XAUUSD +0.05
    net target:   XAUUSD +0.17
    saved:        0.16 lots of round trips that would have cancelled

ATTRIBUTION IS PRESERVED. Virtual P&L is marked per sleeve from the sleeve's own theoretical
position and the instrument's price path, never from the netted fills, so netting changes what
the broker sees and nothing about what each edge is credited with.

WHAT THIS MODULE DOES ON THE DESK TODAY. The bracket sleeves place two-sided pending stops and
resolve their direction only on a fill, so netting applies to the family-market sleeves and to
open positions. `net_targets` is the pure function; `savings_report` measures, from the intent
ledger, how much opposing exposure the desk has actually been carrying -- the number that says
whether routing through the netting engine is worth the execution change. Routing itself is a
money-path change and is left to a separate, box-verified step; this measures first.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
INTENTS = BASE / "data" / "order_intents.jsonl"
REPORT = BASE / "reports" / "NETTING.json"


@dataclass(frozen=True)
class Theoretical:
    sleeve: str
    symbol: str
    lots: float                      # signed: +long, -short


def net_targets(positions: Iterable[Theoretical], lot_step: float = 0.01
                ) -> dict[str, dict[str, Any]]:
    """Per symbol: the net target, the gross the sleeves wanted, and what netting saved."""
    by_sym: dict[str, list[Theoretical]] = {}
    for p in positions:
        by_sym.setdefault(p.symbol, []).append(p)
    out: dict[str, dict[str, Any]] = {}
    for sym, ps in by_sym.items():
        net = sum(p.lots for p in ps)
        gross = sum(abs(p.lots) for p in ps)
        net_r = round(round(net / lot_step) * lot_step, 8)
        out[sym] = {"net_lots": net_r, "gross_lots": round(gross, 8),
                    "saved_lots": round(gross - abs(net), 8),
                    "legs": {p.sleeve: p.lots for p in ps},
                    "opposing": bool(any(p.lots > 0 for p in ps) and any(p.lots < 0 for p in ps))}
    return out


def virtual_pnl(theoretical: Mapping[str, Theoretical], price_now: Mapping[str, float],
                price_prev: Mapping[str, float], point_value: Mapping[str, float]
                ) -> dict[str, float]:
    """Mark each sleeve's theoretical position on the instrument's move. Attribution survives
    netting because it never looks at the netted fill."""
    out: dict[str, float] = {}
    for name, t in theoretical.items():
        if t.symbol not in price_now or t.symbol not in price_prev:
            continue
        dp = float(price_now[t.symbol]) - float(price_prev[t.symbol])
        out[name] = round(t.lots * dp * float(point_value.get(t.symbol, 1.0)), 6)
    return out


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def savings_report(intents: list[dict[str, Any]] | None = None, *, window_h: float = 24.0,
                   write: bool = True) -> dict[str, Any]:
    """How much opposing exposure the desk carried, per symbol, from the intent ledger.

    Intents within `window_h` of each other on the same symbol with opposite sides are the
    round trips netting would have collapsed. Reported in lots and as a share of gross.
    """
    rows = intents if intents is not None else _rows(INTENTS)
    by_sym: dict[str, list[tuple[datetime, float]]] = {}
    for r in rows:
        try:
            t = datetime.fromisoformat(str(r.get("time")))
            lot = float(r.get("lot") or 0.0)
            side = str(r.get("side") or "")
        except (TypeError, ValueError):
            continue
        sgn = 1.0 if side.startswith("buy") else (-1.0 if side.startswith("sell") else 0.0)
        if sgn == 0.0 or lot <= 0:
            continue
        by_sym.setdefault(str(r.get("symbol")), []).append((t, sgn * lot))
    per: dict[str, dict[str, float]] = {}
    tot_gross = tot_saved = 0.0
    for sym, xs in by_sym.items():
        xs.sort()
        gross = sum(abs(l) for _, l in xs)
        saved = 0.0
        i = 0
        while i < len(xs):
            j = i
            bucket = []
            while j < len(xs) and (xs[j][0] - xs[i][0]).total_seconds() <= window_h * 3600:
                bucket.append(xs[j][1])
                j += 1
            saved += sum(abs(l) for l in bucket) - abs(sum(bucket))
            i = j
        per[sym] = {"gross_lots": round(gross, 4), "opposing_lots": round(saved, 4),
                    "share": round(saved / gross, 4) if gross > 0 else 0.0}
        tot_gross += gross
        tot_saved += saved
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "intents": len(rows),
           "window_h": window_h, "per_symbol": per, "gross_lots": round(tot_gross, 4),
           "opposing_lots": round(tot_saved, 4),
           "opposing_share": round(tot_saved / tot_gross, 4) if tot_gross > 0 else 0.0,
           "verdict": ("NETTING_WORTH_ROUTING" if tot_gross > 0 and tot_saved / tot_gross > 0.05
                       else ("NETTING_IMMATERIAL" if tot_gross > 0 else "UNMEASURED")),
           "rule": "opposing exposure inside one window on one symbol is what a netting engine "
                   "would have collapsed; attribution stays per sleeve on theoretical positions"}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc
