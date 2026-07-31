#!/usr/bin/env python3
"""PAPER BOOK RESOLVER (R0126) -- marks every paper call against what price actually did.

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

  FILLS ARE AT THE LEVEL, NO SLIPPAGE MODELLED HERE. Stop fills are assumed at the stop price.
  The gap-risk stress in the sizer (run_conviction_trader.SLIP_STRESS_PCT) is what carries the
  cost of that assumption being wrong; this resolver reports the clean number and the sizer is
  what keeps the dirty case survivable. Do not read a resolved return as net of execution.

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


def _http(url: str, *, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _binance_bars(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float, float,
                                                                        float, float]]:
    url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={BAR}"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in _http(url)]


def _okx_bars(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float, float,
                                                                     float, float]]:
    inst = f"{symbol[:-4]}-USDT" if symbol.endswith("USDT") else symbol
    got: dict[int, tuple[int, float, float, float, float]] = {}
    cursor = end_ms + _BAR_MS
    for _ in range(MAX_PAGES):
        d = _http(f"https://www.okx.com/api/v5/market/history-candles?instId={inst}"
                  f"&bar={BAR}&limit=100&after={cursor}")
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


def fetch_bars(symbol: str, start_ms: int, end_ms: int) -> tuple[list[tuple[int, float, float,
                                                                            float, float]], str]:
    """Bars from the first venue that answers. Returns ([], reason) rather than inventing a mark."""
    errors = []
    for name, fn in (("binance", _binance_bars), ("okx", _okx_bars)):
        try:
            bars = fn(symbol, start_ms, end_ms)
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
    return {
        "outcome": outcome, "exit_price": round(exit_px, 8),
        "exit_at": datetime.fromtimestamp(exit_ts / 1000, tz=UTC).isoformat(),
        "stage_reached": stage_i, "max_stage": len(stages) - 1,
        "units_at_exit": round(sum(u for _, u in tranches), 4),
        "realised_R": round(r_units, 4),
        "equity_return": round(r_units * risk_fraction, 6),
        "profitable": r_units > 0,
        "bars_used": len(bars),
    }


def mark_event_row(row: dict[str, Any], bars: list[tuple[int, float, float, float, float]]
                   ) -> dict[str, Any]:
    """The event sleeve carries no stop or ladder -- it is marked flat at its own horizon."""
    if not bars:
        return {"outcome": "UNRESOLVABLE", "why": "no bars"}
    sign = 1.0 if row["direction"] == "LONG" else -1.0
    first, last = bars[0][1], bars[-1][4]
    ret = (last - first) / first * sign
    return {"outcome": "MARKED", "entry_price": first, "exit_price": last,
            "realised_R": None, "equity_return": round(ret, 6), "profitable": ret > 0,
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
        "conventions": ["adverse-first intrabar", "swing trail simulated as extreme-minus-1R",
                        "fills at the level, no slippage modelled",
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
        print(f"paper book (R0126): {rep['status']} -- {rep['detail']}")
    if args.report_only:
        return 0
    # UNMEASURED is not a failure of this organ -- it is the true state of an unproven sleeve, and
    # the fence that must escalate it is the calibration/conversion pair, not this resolver.
    return 0


if __name__ == "__main__":
    sys.exit(main())
