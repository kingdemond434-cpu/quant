#!/usr/bin/env python3
"""PAPER BOOK RESOLVER (R0133) -- marks every paper call against what price actually did.

WHY THIS EXISTS, and why it is the most important thing either trading sleeve was missing. R0122
and R0125 both write pre-registered calls to a book and then never look at them again. An unmarked
book is the purest form of the defect this desk fences everywhere else (L1.28a): it accumulates
confident-looking rows, reports no failure, and reads as though the sleeve is working. It is not
evidence of anything. The principal asked what these sleeves return -- that question is
UNANSWERABLE until the book is marked, and answering it with a plausible estimate instead of a
measurement is exactly the behaviour the 420-tested/0-survived record exists to prevent.

WHAT IT DOES:
  * fetches real OHLC bars over each call's own window (Binance USD-M first, OKX fallback --
    Binance answers 451 from some egress regions and a resolver that dies on that is a resolver
    that never runs),
  * WALKS THE RECORDED MANAGEMENT LADDER bar by bar for conviction calls: stop, trail to
    breakeven, adds, trail behind the running extreme -- so the number it reports is the P&L of
    the strategy as specified, not of a naive entry-to-horizon mark that would flatter or damn it
    for the wrong reasons,
  * marks event-sleeve calls at their horizon,
  * benchmarks every call against unlevered buy-and-hold over the SAME window, because beating
    buy-and-hold is the L1.6 promotion condition and a levered sleeve that merely tracks it is
    taking risk for nothing,
  * feeds every resolved outcome back into the L1.29 calibration fence, which is what makes an
    over-confident sleeve shrink its own future size automatically.

THREE CONVENTIONS, stated because each one decides the answer:

  ADVERSE-FIRST. When a single bar's range contains both the stop and the next ladder trigger,
  the STOP is assumed to hit first. Intrabar order is unknowable at this resolution and the
  favourable assumption is how backtests lie; this one always resolves ambiguity against the
  desk.

  THE TRAIL IS SIMULATED MECHANICALLY. Live, the rule is "trail behind the most recent swing".
  A swing is only identifiable after the fact, so the simulation uses the running favourable
  extreme minus 1R as its proxy. This is an APPROXIMATION and it is named as one: a real swing
  trail is usually tighter, so the simulated result is, if anything, the generous version of the
  late-stage exits. It is not generous about entries or stops, which is where the money is.

  FILLS ARE AT THE LEVEL, BUT COSTS ARE REAL. Stop fills are assumed at the stop price -- the
  gap-risk stress in the sizer (SLIP_STRESS_PCT) carries the cost of that being wrong. Fees,
  slippage and funding, however, are DEDUCTED: at 6.7x leverage a round trip is ~24% of a full R,
  which moves the breakeven hit rate from 25.0% to 31.1%. A gross mark would show a 30% hit rate
  as profitable when it is a loser, so `equity_return` is NET and gross is reported beside it.

REFUSES RATHER THAN GUESSES: no bars, no mark. A row whose window cannot be fetched is
UNRESOLVABLE and is reported as such -- it never silently becomes a zero, which would drag every
aggregate toward "fine" using rows that were never measured at all.

    python scripts/resolve_paper_book.py [--json] [--report-only]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_CONVICTION_BOOK = "data/conviction_book.jsonl"
_EVENT_BOOK = "data/llm_trader_book.jsonl"
_MARKS = "data/paper_book_marks.jsonl"
_STATE = "data/paper_book_pnl.json"

BAR = "15m"
_BAR_MS = 15 * 60 * 1000
MAX_PAGES = 12                              # bounded paging: ~1200 bars = 12 days at 15m

#: EXECUTION COSTS, and the reason a mark without them is a flattering number rather than a
#: result. Binance USD-M non-VIP: taker 0.045%/side, maker 0.018%/side, funding ~0.01% per 8h
#: stamp. These are charged on NOTIONAL, so at 6.7x leverage a taker round trip costs ~0.9% of
#: sleeve equity -- 15% of a full 6% R, before slippage. Measured against the sizer's own numbers:
#: total realistic cost is ~24% of one R at taker-in/taker-out, which raises the breakeven hit
#: rate from 25.0% to 31.1%. An unmarked-for-costs book would show a 30% hit rate as profitable
#: when it is not, which is precisely the class of self-flattery this resolver exists to prevent.
TAKER_FEE = 0.00045
#: 0.00018 = Binance USD-M published non-VIP maker fee, 0.018%/side. A venue schedule, not a
#: choice: it moves only when the fee tier does. Worth ~0.4% of equity per trade vs taker.
MAKER_FEE = 0.00018
#: 0.00015 = 1.5bp/side, the observed order-book depth cost on majors at sub-$10k clip -- top-of-
#: book spread on BTC/ETH perps runs 0.5-1bp and this allows ~2x that for the level not being
#: exactly where the order rests. DELIBERATELY PESSIMISTIC: understating slippage is the standard
#: way a paper book flatters itself, and at 10x notional each 1bp is 0.1% of equity per side.
SLIPPAGE = 0.00015
#: 0.0001 = 0.01% per 8h stamp, the observed typical Binance USD-M funding magnitude on majors.
#: Sign deliberately ignored and always charged AS A COST: a directional sleeve is as often on the
#: paying side as the receiving one, and assuming the favourable sign would flatter every long in
#: a positive-funding regime -- roughly 0.25% of equity per 20h hold at 10x notional.
FUNDING_PER_8H = 0.0001


def trade_cost(leverage: float, units: float, hold_hours: float, *,
               entry_maker: bool = True) -> dict[str, float]:
    """Round-trip cost as a fraction of sleeve equity.

    entry_maker defaults TRUE because this sleeve enters with a resting order AT a named level --
    it bids support rather than chasing, so a limit order is the correct type anyway and the maker
    rebate is free. The EXIT is assumed taker: a stop is a taker fill by definition. Being wrong
    about the entry costs ~0.4% of equity per trade, so it is reported separately rather than
    buried in a single number."""
    notional = max(0.0, leverage) * max(0.0, units)
    entry = (MAKER_FEE if entry_maker else TAKER_FEE) * notional
    exit_ = TAKER_FEE * notional
    slip = (1 if entry_maker else 2) * SLIPPAGE * notional
    funding = FUNDING_PER_8H * notional * max(0.0, hold_hours) / 8.0
    total = entry + exit_ + slip + funding
    return {"entry_fee": round(entry, 6), "exit_fee": round(exit_, 6), "slippage": round(slip, 6),
            "funding": round(funding, 6), "total": round(total, 6),
            "entry_side": "maker" if entry_maker else "taker"}


def _http(url: str, *, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


#: Interval names differ per venue; one mapping so callers speak a single dialect.
_INTERVALS: dict[str, tuple[str, str, int]] = {          # ours -> (binance, okx, ms)
    "15m": ("15m", "15m", 15 * 60 * 1000),
    "1h": ("1h", "1H", 60 * 60 * 1000),
    "4h": ("4h", "4H", 4 * 60 * 60 * 1000),
    "1d": ("1d", "1D", 24 * 60 * 60 * 1000),
}


def _binance_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
                  ) -> list[tuple[int, float, float, float, float]]:
    iv = _INTERVALS[bar][0]
    url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={iv}"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in _http(url)]


def _okx_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
              ) -> list[tuple[int, float, float, float, float]]:
    inst = f"{symbol[:-4]}-USDT" if symbol.endswith("USDT") else symbol
    iv, step = _INTERVALS[bar][1], _INTERVALS[bar][2]
    got: dict[int, tuple[int, float, float, float, float]] = {}
    cursor = end_ms + step
    for _ in range(MAX_PAGES):
        d = _http(f"https://www.okx.com/api/v5/market/history-candles?instId={inst}"
                  f"&bar={iv}&limit=100&after={cursor}")
        rows = d.get("data") or []
        if not rows:
            break
        for r in rows:
            ts = int(r[0])
            got[ts] = (ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]))
        cursor = min(int(r[0]) for r in rows)
        if cursor <= start_ms:
            break
        time.sleep(0.15)
    return [v for _, v in sorted(got.items()) if start_ms <= v[0] <= end_ms]


def fetch_bars(symbol: str, start_ms: int, end_ms: int, bar: str = BAR
               ) -> tuple[list[tuple[int, float, float, float, float]], str]:
    """Bars from the first venue that answers. Returns ([], reason) rather than inventing a mark."""
    if bar not in _INTERVALS:
        return [], f"UNRESOLVABLE -- unknown interval {bar}"
    errors = []
    for name, fn in (("binance", _binance_bars), ("okx", _okx_bars)):
        try:
            bars = fn(symbol, start_ms, end_ms, bar)
            if bars:
                return bars, name
            errors.append(f"{name}: empty")
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__} {str(exc)[:60]}")
    return [], "UNRESOLVABLE -- " + "; ".join(errors)


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def walk_ladder(row: dict[str, Any], bars: list[tuple[int, float, float, float, float]]
                ) -> dict[str, Any]:
    """Simulate the RECORDED management plan against real bars. The number this returns is the
    P&L of the strategy as specified -- ladder, trail and adds included -- which is the only mark
    that says anything about whether trend-riding earns its complexity."""
    plan = row.get("management") or {}
    stages = plan.get("stages") or []
    if not stages or not bars:
        return {"outcome": "UNRESOLVABLE", "why": "no plan stages or no bars"}
    sign = 1.0 if row["direction"] == "LONG" else -1.0
    entry = float(row["entry_ref"])
    r_price = float(plan.get("r_price") or abs(entry - float(row["invalidation"])))
    if r_price <= 0:
        return {"outcome": "UNRESOLVABLE", "why": "zero-width R"}
    risk_fraction = float((row.get("sizing") or {}).get("risk_fraction") or 0.0)

    tranches: list[tuple[float, float]] = [(entry, float(stages[0]["units"]))]
    stop = float(stages[0]["stop"])
    stage_i = 0
    extreme = entry                                   # running favourable extreme, for the trail
    exit_px: float | None = None
    exit_ts = bars[-1][0]
    outcome = "OPEN"

    for ts, _o, hi, lo, close in bars:
        # 1. ADVERSE-FIRST: the stop is tested before any favourable progression in the same bar.
        if (sign > 0 and lo <= stop) or (sign < 0 and hi >= stop):
            exit_px, exit_ts, outcome = stop, ts, ("STOPPED" if stage_i == 0 else "TRAILED-OUT")
            break
        # 2. ladder progression -- at most one rung per bar, again the conservative reading.
        if stage_i + 1 < len(stages):
            nxt = stages[stage_i + 1]
            trig = float(nxt["trigger"])
            if (sign > 0 and hi >= trig) or (sign < 0 and lo <= trig):
                stage_i += 1
                stop = float(nxt["stop"])
                added = round(float(nxt["units"]) - sum(u for _, u in tranches), 6)
                if added > 0:
                    tranches.append((trig, added))
        # 3. past the last rung the trail follows the running extreme, one R behind (the
        #    mechanical proxy for "behind the most recent swing" -- see the module docstring).
        extreme = max(extreme, hi) if sign > 0 else min(extreme, lo)
        if stage_i + 1 >= len(stages):
            stop = max(stop, extreme - r_price) if sign > 0 else min(stop, extreme + r_price)

    if exit_px is None:                               # ran out of bars while still open
        exit_px, exit_ts = bars[-1][4], bars[-1][0]

    r_units = sum(u * (exit_px - e) * sign / r_price for e, u in tranches)
    units = sum(u for _, u in tranches)
    gross = r_units * risk_fraction
    hold_h = (exit_ts - bars[0][0]) / 3_600_000.0
    cost = trade_cost(float((row.get("sizing") or {}).get("leverage") or 0.0), units, hold_h)
    net = gross - cost["total"]
    return {
        "outcome": outcome, "exit_price": round(exit_px, 8),
        "exit_at": datetime.fromtimestamp(exit_ts / 1000, tz=UTC).isoformat(),
        "stage_reached": stage_i, "max_stage": len(stages) - 1,
        "units_at_exit": round(units, 4),
        "realised_R": round(r_units, 4),
        "gross_return": round(gross, 6),
        "cost": cost, "hold_hours": round(hold_h, 2),
        # NET is the number that carries the name. A gross mark shows a 30% hit rate as profitable
        # when costs make it a loser -- the exact self-flattery this resolver exists to prevent.
        "equity_return": round(net, 6),
        "profitable": net > 0,
        "bars_used": len(bars),
    }


def mark_event_row(row: dict[str, Any], bars: list[tuple[int, float, float, float, float]]
                   ) -> dict[str, Any]:
    """The event sleeve carries no stop or ladder -- it is marked flat at its own horizon."""
    if not bars:
        return {"outcome": "UNRESOLVABLE", "why": "no bars"}
    sign = 1.0 if row["direction"] == "LONG" else -1.0
    first, last = bars[0][1], bars[-1][4]
    gross = (last - first) / first * sign
    hold_h = (bars[-1][0] - bars[0][0]) / 3_600_000.0
    cost = trade_cost(1.0, 1.0, hold_h)          # event sleeve is unlevered, 1 unit
    net = gross - cost["total"]
    return {"outcome": "MARKED", "entry_price": first, "exit_price": last,
            "realised_R": None, "gross_return": round(gross, 6), "cost": cost,
            "hold_hours": round(hold_h, 2),
            "equity_return": round(net, 6), "profitable": net > 0,
            "bars_used": len(bars)}


def _benchmark(bars: list[tuple[int, float, float, float, float]]) -> float | None:
    """Unlevered buy-and-hold over the SAME window -- the L1.6 bar a levered sleeve must clear."""
    if not bars:
        return None
    return round((bars[-1][4] - bars[0][1]) / bars[0][1], 6)


def equity_curve(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """The sleeve's own equity path, high-water mark and drawdown.

    This is the number that decides whether the sleeve may ever take live size, and it is not
    optional colour: at a 20% risk budget per trade a losing run bites hard and fast (three stops
    in a row is -49%), so a sleeve-level drawdown rail has to exist BEFORE real money does, not
    after the first bad week. run_conviction_trader reads it and halts on breach.

    APPROXIMATION, named: calls overlap in time (one every four hours, horizons of 8-48), so
    compounding them in exit order is not the same as running the book. It is the honest
    conservative reading -- overlapping positions would drawdown TOGETHER, so the real path is
    rougher than this one, never smoother."""
    eq, hwm, mdd = 1.0, 1.0, 0.0
    path = []
    for m in resolved:
        eq *= 1.0 + float(m.get("equity_return") or 0.0)
        hwm = max(hwm, eq)
        mdd = max(mdd, (hwm - eq) / hwm if hwm > 0 else 0.0)
        path.append(round(eq, 6))
    return {"n": len(resolved), "final": round(eq, 6), "high_water": round(hwm, 6),
            "max_drawdown": round(mdd, 6),
            "current_drawdown": round((hwm - eq) / hwm if hwm > 0 else 0.0, 6),
            "path": path[-50:],
            "note": "compounded in exit order; overlapping calls drawdown together, so the live "
                    "path is rougher than this, never smoother"}


def _rows(path: Path) -> list[dict[str, Any]]:
    out = []
    try:
        for ln in path.read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue                          # a torn line is skipped, never guessed at
    except OSError:
        return []
    return out


def resolve_book(root: Path, *, now: datetime | None = None,
                 fetch=fetch_bars) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    marks: list[dict[str, Any]] = []

    for book, kind in ((_CONVICTION_BOOK, "conviction"), (_EVENT_BOOK, "event")):
        for row in _rows(root / book):
            if row.get("action") == "PASS" or not row.get("symbol"):
                continue
            try:
                start = _ms(row["at"])
                due = datetime.fromisoformat(row["resolve_by"])
            except (KeyError, ValueError):
                marks.append({"kind": kind, "key": row.get("at"), "outcome": "UNRESOLVABLE",
                              "why": "unparseable timestamps"})
                continue
            end = int(min(due, now).timestamp() * 1000)
            if end - start < _BAR_MS:
                marks.append({"kind": kind, "key": row.get("at"), "outcome": "TOO-EARLY",
                              "why": "less than one bar has elapsed"})
                continue
            bars, source = fetch(row["symbol"], start, end)
            if not bars:
                marks.append({"kind": kind, "key": row.get("at"), "symbol": row.get("symbol"),
                              "outcome": "UNRESOLVABLE", "why": source})
                continue
            res = (walk_ladder(row, bars) if kind == "conviction" and row.get("management")
                   else mark_event_row(row, bars))
            marks.append({"kind": kind, "key": row.get("at"), "symbol": row.get("symbol"),
                          "direction": row.get("direction"),
                          "probability": row.get("probability"), "source": source,
                          "buy_and_hold": _benchmark(bars),
                          "closed": datetime.fromisoformat(row["resolve_by"]) <= now, **res})

    resolved = [m for m in marks if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED")
                and m.get("closed")]
    resolved.sort(key=lambda m: m.get("exit_at") or m.get("key") or "")
    curve = equity_curve(resolved)
    unresolvable = [m for m in marks if m.get("outcome") == "UNRESOLVABLE"]
    wins = [m for m in resolved if m.get("profitable")]
    sleeve = sum(float(m.get("equity_return") or 0.0) for m in resolved)
    bh = sum(float(m["buy_and_hold"]) * (1.0 if m.get("direction") == "LONG" else -1.0)
             for m in resolved if m.get("buy_and_hold") is not None)

    if not resolved:
        status, detail = "UNMEASURED", (
            f"{len(marks)} book rows, 0 resolvable closed calls -- this sleeve has produced NO "
            "evidence yet and must not be read as working (L1.28a)")
    else:
        status = "MEASURED"
        detail = (f"{len(resolved)} closed calls: {len(wins)}/{len(resolved)} profitable, "
                  f"sleeve {sleeve:+.2%} vs directional buy-and-hold {bh:+.2%} over the same "
                  f"windows; equity x{curve['final']:.3f}, max DD {curve['max_drawdown']:.1%}; "
                  f"{len(unresolvable)} unresolvable")

    return {
        "generated": now.isoformat(),
        "law": "L1.28a/L1.6 -- an unmarked paper book is not evidence; every call is marked "
               "against real bars, benchmarked against buy-and-hold, and fed to calibration.",
        "status": status, "detail": detail,
        "n_rows": len(marks), "n_resolved": len(resolved), "n_unresolvable": len(unresolvable),
        "n_open": len([m for m in marks if m.get("outcome") == "OPEN"]),
        "win_rate": round(len(wins) / len(resolved), 4) if resolved else None,
        "sleeve_return": round(sleeve, 6) if resolved else None,
        "buy_and_hold_return": round(bh, 6) if resolved else None,
        "beats_buy_and_hold": (sleeve > bh) if resolved else None,
        "mean_R": (round(sum(float(m["realised_R"]) for m in resolved
                             if m.get("realised_R") is not None)
                         / max(1, len([m for m in resolved if m.get("realised_R") is not None])),
                         4) if resolved else None),
        "equity": curve,
        "costs_deducted": {"taker": TAKER_FEE, "maker": MAKER_FEE, "slippage_per_side": SLIPPAGE,
                           "funding_per_8h": FUNDING_PER_8H,
                           "note": "entry assumed MAKER (a resting order at the named level), exit "
                                   "assumed TAKER (a stop is a taker fill). Returns are NET."},
        "conventions": ["adverse-first intrabar", "swing trail simulated as extreme-minus-1R",
                        "fills at the level; fees, slippage and funding ARE deducted",
                        "equity compounded in exit order despite overlapping positions"],
        "marks": marks,
    }


def feed_calibration(report: dict[str, Any]) -> list[str]:
    """Resolved outcome -> L1.29. This is the loop that makes an over-confident sleeve shrink."""
    fed = []
    try:
        from libs.self_improvement import forecast_calibration as fc
    except ImportError as exc:
        return [f"UNFED: calibration module unavailable ({exc})"]
    for m in report["marks"]:
        if m.get("outcome") in ("STOPPED", "TRAILED-OUT", "MARKED") and m.get("closed"):
            key = f"{'conviction' if m['kind'] == 'conviction' else 'llm_trader'}:{m['key']}"
            try:
                fc.resolve(key, bool(m.get("profitable")))
                fed.append(key)
            except (KeyError, ValueError, OSError) as exc:
                fed.append(f"UNFED {key}: {exc}")
    return fed


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = resolve_book(_ROOT)
    rep["calibration_fed"] = feed_calibration(rep)

    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    with (_ROOT / _MARKS).open("a", encoding="utf-8") as fh:
        for m in rep["marks"]:
            fh.write(json.dumps({"marked_at": rep["generated"], **m}) + "\n")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"paper book (R0133): {rep['status']} -- {rep['detail']}")
    if args.report_only:
        return 0
    # UNMEASURED is not a failure of this organ -- it is the true state of an unproven sleeve, and
    # the fence that must escalate it is the calibration/conversion pair, not this resolver.
    return 0


if __name__ == "__main__":
    sys.exit(main())
