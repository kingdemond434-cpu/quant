"""EXECUTION TRUTH BEFORE CAPITAL -- decision to quote to order to fill to markout, on real ticks.

THE PROBLEM THIS SOLVES. `markout.py` compares intents to fills and is correct, but it can only
speak once real orders exist: today it reports 0 matched fills because nothing is live, so the
desk's execution assumptions have never been tested at all. Meanwhile every R figure it produces
assumes a fill at exactly the bracket price -- and session-range breakout enters on STOP orders
into a fast move, the single worst case for slippage, because the order becomes a market order
precisely when the book is thinnest and moving away. Waiting for live fills to discover that is
paying tuition to learn something the tape already knows.

WHAT THIS DOES INSTEAD. It reconstructs the whole execution chain for every shadow decision
against the venue's own recorded quotes:

    decision (bar close that fired) -> quote (real bid/ask at that instant)
      -> simulated STOP order at the intended level
      -> fill (the first tick that touches it, taken at the far side of the spread)
      -> markouts at +1 / +5 / +15 / +60 minutes from the fill

Every number comes from Fusion's own tick tape. Nothing is modelled except the ONE thing a tape
cannot show -- whether the desk's own order would have moved the price -- and that is reported as
a capacity bound rather than assumed away.

WHY MEASURING THIS ON HISTORICAL TRADES IS LEGITIMATE, when counting them as forward evidence is
not. A markout measures the VENUE, not the strategy: spread, latency and slippage at 09:00 on a
Tuesday are facts about Fusion's book, and they do not become more true because a hypothesis was
frozen first. Selection bias is a claim about which STRATEGY was chosen; it has no purchase on
what the spread was. Both arms are reported separately anyway, so the distinction stays visible.

WHAT IT REFUSES. A decision whose stop is never touched is an UNFILLED order, reported as a
rejection rate -- never as a zero-slippage fill, which would drag every mean toward "no slippage"
using orders that never traded. A symbol with no tape for the day is UNMEASURED, never zero.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
TAPE = BASE / "data" / "tape" / "ticks"
SHADOW = BASE / "reports" / "shadow"
OUT = BASE / "reports" / "execution_quality.json"

#: Markout horizons. Short ones show adverse selection (did the price keep going against the
#: fill?); the hour shows whether the entry was into a real move or into noise.
HORIZONS_MIN = (1, 5, 15, 60)
#: A fill is only credible if a tick touches the level within this window of the decision. Beyond
#: it the "fill" is a different trade in a different market state.
FILL_WINDOW_MIN = 90
#: Execution evidence older than this cannot gate a promotion -- the book changes.
STALE_HOURS = 36.0


@dataclass
class Exec:
    """One reconstructed execution chain."""

    sleeve: str
    symbol: str
    session: str
    phase: str
    direction: int
    decided_at: str
    intended: float
    quote_bid: float | None = None
    quote_ask: float | None = None
    fill_price: float | None = None
    filled_at: str | None = None
    latency_s: float | None = None
    spread_at_fill: float | None = None
    slip_price: float | None = None
    risk_distance: float | None = None
    slip_r: float | None = None
    markouts: dict[str, float] = field(default_factory=dict)
    ticks_in_window: int = 0
    unfilled_reason: str | None = None


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(value: Any) -> datetime | None:
    try:
        import pandas as pd
        t = pd.Timestamp(str(value)).to_pydatetime()
        return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)
    except Exception:
        return None


def load_ticks(symbol: str, day: datetime):
    """One day of the venue's own quotes, or None. Absence is UNMEASURED, never zero."""
    path = TAPE / symbol / f"{day.date().isoformat()}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        if "ts" not in df.columns:
            return None
        df = df[["ts", "bid", "ask"]].dropna()
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values("ts").reset_index(drop=True)
    except Exception:
        return None


def reconstruct(row: dict, sleeve: str, symbol: str, session: str) -> Exec | None:
    """Walk the tape from the decision to the fill, then out to each markout horizon."""
    decided = _ts(row.get("entry_time"))
    if decided is None:
        return None
    direction = 1 if str(row.get("side", "")).upper().startswith(("B", "L")) else -1
    intended = float(row.get("entry") or 0.0)
    if not intended:
        return None
    ex = Exec(sleeve=sleeve, symbol=symbol, session=session,
              phase=str(row.get("phase") or "unknown"), direction=direction,
              decided_at=decided.isoformat(), intended=intended)

    ticks = load_ticks(symbol, decided)
    if ticks is None or ticks.empty:
        ex.unfilled_reason = "no tape for this symbol/day -- UNMEASURED, not a zero-cost fill"
        return ex

    window = ticks[(ticks["ts"] >= decided)
                   & (ticks["ts"] <= decided + timedelta(minutes=FILL_WINDOW_MIN))]
    ex.ticks_in_window = len(window)
    if window.empty:
        ex.unfilled_reason = "tape has no quotes in the fill window"
        return ex

    first = window.iloc[0]
    ex.quote_bid, ex.quote_ask = float(first["bid"]), float(first["ask"])

    # A STOP order fills when the market TRADES THROUGH the level, and the taker pays the far
    # side: a buy stop lifts the ask, a sell stop hits the bid. Using the mid here -- or the
    # trigger price, as the backtest does -- is precisely the fiction this module exists to end.
    if direction > 0:
        touched = window[window["ask"] >= intended]
        px_col = "ask"
    else:
        touched = window[window["bid"] <= intended]
        px_col = "bid"
    if touched.empty:
        ex.unfilled_reason = (f"level {intended} never touched within {FILL_WINDOW_MIN}m -- an "
                              f"UNFILLED bracket, not a free fill")
        return ex

    hit = touched.iloc[0]
    filled_at = hit["ts"].to_pydatetime()
    ex.fill_price = float(hit[px_col])
    ex.filled_at = filled_at.isoformat()
    ex.latency_s = round((filled_at - decided).total_seconds(), 3)
    ex.spread_at_fill = round(float(hit["ask"]) - float(hit["bid"]), 6)
    # SIGNED and direction-adjusted: a buy filled above its trigger and a sell filled below are
    # the same event, and must not cancel in a mean. Positive = worse than asked.
    ex.slip_price = round((ex.fill_price - intended) * direction, 6)
    # SLIPPAGE IN R IS THE NUMBER THAT DECIDES THINGS. Price units hide the severity: 0.03 on
    # CADJPY sounds like nothing until it is expressed against the stop distance the sizing model
    # uses, because every gate, every expectancy and every Kelly fraction on this desk is written
    # in R. The stop distance is recovered from the trade's own outcome -- r_multiple is
    # (exit-entry)*dir / risk -- so it is the SAME denominator the backtest used, not a new
    # assumption layered on top.
    try:
        _exit = float(row.get("exit") or 0.0)
        _r = float(row.get("r_multiple") or 0.0)
        if _exit and abs(_r) > 1e-9:
            risk = abs((_exit - intended) * direction / _r)
            if risk > 0:
                ex.risk_distance = round(risk, 6)
                ex.slip_r = round(ex.slip_price / risk, 5)
                for _h in HORIZONS_MIN:
                    if f"m{_h}" in ex.markouts:
                        ex.markouts[f"m{_h}_r"] = round(ex.markouts[f"m{_h}"] / risk, 5)
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    for h in HORIZONS_MIN:
        later = ticks[ticks["ts"] >= filled_at + timedelta(minutes=h)]
        if later.empty:
            continue
        row_l = later.iloc[0]
        mid = (float(row_l["bid"]) + float(row_l["ask"])) / 2.0
        ex.markouts[f"m{h}"] = round((mid - ex.fill_price) * direction, 6)
    return ex


def _agg(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p90": None}
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    p90 = s[min(n - 1, math.ceil(0.9 * n) - 1)]
    return {"n": n, "mean": round(mean, 6), "median": round(median, 6), "p90": round(p90, 6)}


def summarise(rows: list[Exec]) -> dict:
    filled = [r for r in rows if r.fill_price is not None]
    unfilled = [r for r in rows if r.fill_price is None]
    by_key: dict[str, list[Exec]] = {}
    for r in filled:
        by_key.setdefault(f"{r.symbol}.{r.session}", []).append(r)

    per_cell = {}
    for key, group in sorted(by_key.items()):
        per_cell[key] = {
            "fills": len(group),
            "slippage_price": _agg([r.slip_price for r in group if r.slip_price is not None]),
            "slippage_R": _agg([r.slip_r for r in group if r.slip_r is not None]),
            "spread_at_fill": _agg([r.spread_at_fill for r in group
                                    if r.spread_at_fill is not None]),
            "latency_seconds": _agg([r.latency_s for r in group if r.latency_s is not None]),
            # Ticks available around the decision are the only capacity signal a quote tape
            # carries: a level touched by three quotes is not a level you can size into.
            "quote_density": _agg([float(r.ticks_in_window) for r in group]),
            "markouts_R": {f"m{h}": _agg([r.markouts.get(f"m{h}_r") for r in group
                                          if r.markouts.get(f"m{h}_r") is not None])
                           for h in HORIZONS_MIN},
        }
    reasons: dict[str, int] = {}
    for r in unfilled:
        k = (r.unfilled_reason or "unknown").split("--")[0].strip()[:60]
        reasons[k] = reasons.get(k, 0) + 1
    return {
        "decisions": len(rows), "filled": len(filled), "unfilled": len(unfilled),
        "rejection_rate": round(len(unfilled) / len(rows), 4) if rows else None,
        "unfilled_reasons": reasons,
        "by_symbol_session": per_cell,
        "by_phase": {p: sum(1 for r in filled if r.phase == p)
                     for p in sorted({r.phase for r in filled})},
    }


def collect() -> list[Exec]:
    """Every shadow decision the desk has recorded, as an execution chain."""
    rows: list[Exec] = []
    for ledger in sorted(SHADOW.glob("ledger_*.json")):
        data = _read_json(ledger)
        if not isinstance(data, list) or not data:
            continue
        stem = ledger.stem[len("ledger_"):]
        parts = stem.split("_")
        symbol = parts[0]
        session = "_".join(parts[1:]) or "unknown"
        for row in data:
            if not isinstance(row, dict):
                continue
            ex = reconstruct(row, sleeve=stem, symbol=symbol, session=session)
            if ex is not None:
                rows.append(ex)
    return rows


def main() -> int:
    now = datetime.now(tz=UTC)
    rows = collect()
    report = summarise(rows)
    report["measured_at"] = now.isoformat(timespec="seconds")
    report["source"] = "Fusion tick tape (venue-native quotes)"
    report["horizons_min"] = list(HORIZONS_MIN)
    report["note"] = ("Execution quality measures the VENUE, so historical decisions are valid "
                      "inputs here even though they cannot serve as forward STRATEGY evidence. "
                      "Unfilled brackets are counted as rejections, never as costless fills.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    print(f"execution quality: {report['decisions']} decision(s), {report['filled']} filled, "
          f"{report['unfilled']} unfilled "
          f"(rejection {report['rejection_rate']}), {len(report['by_symbol_session'])} cell(s)")
    for key, cell in list(report["by_symbol_session"].items())[:6]:
        slip_r = cell["slippage_R"]["median"]
        spr = cell["spread_at_fill"]["median"]
        m15 = cell["markouts_R"]["m15"]["median"]
        print(f"   {key:28} fills={cell['fills']:<4} med_slip={slip_r}R "
              f"spread={spr} m15={m15}R")
    return 0


def is_stale(path: Path = OUT, hours: float = STALE_HOURS) -> tuple[bool, str]:
    """Promotion gate: execution evidence must exist and be recent, or nothing may promote."""
    report = _read_json(path)
    if not isinstance(report, dict):
        return True, "no execution measurement exists at all"
    if not report.get("filled"):
        return True, (f"execution measured but 0 fills reconstructed "
                      f"({report.get('unfilled', 0)} unfilled) -- costs are UNMEASURED")
    at = _ts(report.get("measured_at"))
    if at is None:
        return True, "execution measurement carries no timestamp"
    age = (datetime.now(tz=UTC) - at).total_seconds() / 3600
    if age > hours:
        return True, f"execution measurement is {age:.1f}h old (limit {hours}h); the book moves"
    return False, f"execution measured {age:.1f}h ago across {report['filled']} fill(s)"


if __name__ == "__main__":
    raise SystemExit(main())
