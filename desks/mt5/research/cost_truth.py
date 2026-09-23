#!/usr/bin/env python3
"""COST TRUTH -- what the model CHARGES, against what the broker QUOTES and what the desk PAID.

THE WORRY THIS ANSWERS, in the principal's own words (2026-09-23): "double check if the costs
are actually Fusion costs, spreads etc, accurate -- just in case we dismissed edges net based on
overcharged false costs." The net-edge spine had just refused 14 cells as COST_DEAD and flipped
23 more to negative AFTER costs, on a box where `EXECUTION_COST_SURFACE.json` was ABSENT, where
only 61 of 273 rows carried a priced spread at all, and where market impact is UNMEASURED
everywhere because `matched_fills` is 0. An overcharged cost model kills real edge silently:
there is no alert, the cell simply never appears again.

THREE READINGS PER SYMBOL, AND THEY ARE DIFFERENT MEASUREMENTS, NEVER THE SAME ONE RENAMED:

  CHARGED   what the desk's own model bills -- `universe.json:median_spread_pts` (the scalar
            every gate divides by), `FUSION_COST.json:round_trip_per_lot` (the venue split the
            net-edge spine turns into a commission term) and `COST_TO_EDGE.json:spread_r/swap_r`.
  QUOTED    what THIS broker quotes on THIS account, read from the live terminal: the symbol's
            own `symbol_info` (point, digits, contract size, swap long/short, stop level, tick
            value) and the M1 tape's own `spread` column, bucketed by SESSION -- a single
            snapshot is not the cost a strategy pays, so the distribution is published and the
            snapshot is only one row of it.
  REALISED  what the account actually paid: `history_deals_get` over the whole account, which
            carries commission and swap per deal in account currency, joined to the desk's own
            `live_ledger.jsonl` (risk_quote -> R) and `order_intents.jsonl` (intended price ->
            entry slippage).

WHAT THE FIRST RUN MEASURED, on account 495044 (Fusion Markets Pty Ltd, FusionMarkets-Live, EUR)
from 433 deals between 2026-08-23 and 2026-09-22 and the terminal's own M1 tape:

  COMMISSION IS 2.00 EUR PER LOT PER SIDE, on every one of the 12 symbols the desk has traded,
  gold included -- flat, with no exceptions. The model charges 2.25 (`fusion_cost.py:84`,
  `engine.Costs.commission_per_lot`), documented as "USD 2.25 per lot per side" and then applied
  as ACCOUNT currency. So the contractual term is charged at 1.125x reality before any modelling
  choice is made.

  AND THE SPINE MULTIPLIES THAT BY FIVE MORE. `net_edge_spine.commission_term` derives the
  commission-to-spread ratio as `zero / (raw - zero)` from the FUSION_COST round trip. But RAW
  is the 0.2x regime (`fusion_cost.COST_REGIMES = {"WIDE": 2.0, "RAW": 0.2, "ZERO": 0.0}`), so
  `raw - zero` is ONE FIFTH of the spread, not the spread: the correct ratio against a one-way
  `spread_r` is `RAW_MULT * zero / (raw - zero)`. Measured on AUDCAD the spine charges 48.45x
  the spread term where the arithmetic gives 9.69x; on AUDNZD 59.64x against 11.93x. Commission
  is a MEDIAN 98% of the charged cost on this account, so this is not a rounding argument: it is
  the dominant term of every refusal, charged at 5.625x (5x regime, 1.125x rate) reality.

  THE SPREAD IS CHARGED ABOVE THE BOOK TOO, and in the direction that kills. XAUUSD is charged
  14.5 pts against a live book quoting 6; EURUSD is charged against a bar median of 12 pts while
  the terminal quotes 0.0 and has quoted a median 0.0 over every M1 bar of the window -- Fusion
  Zero is genuinely commission-only there. The desk's stored tape overstates because an H1 bar's
  `spread` stamp samples the widest instant of its hour (`cost_surface.py` says so in its own
  docstring); M1 is the granularity at which a fill actually happens.

WHAT IS NOT MEASURED, AND STAYS THAT WAY. Market impact needs matched fills at size and the desk
has none, so impact is UNMEASURED here as it is in CAPACITY.json -- it is NOT replaced by a
pessimistic default, because an unpriced term makes net a BOUND (which `libs/research/net_edge`
already models) and a default would make it a verdict. Exit slippage is measured only where the
exit was at a recorded SL/TP level. A symbol with fewer than MIN_DEALS deals reports UNMEASURED
and keeps its modelled charge; absence never resolves to a clean verdict (L1.28a / WS-005).

IT VETOES NOTHING AND SIZES NOTHING. Every correction here moves cost DOWN toward the measured
median, never up: the organ exists because overcharging is the false-null direction the desk has
no other instrument for. Where a refusal was made on an overcharged cost, a missed-growth line
is written for the period it stood (GROWTH GOVERNANCE Rule 1), and the cell is named in
`restored_to_queue` so the intake can rank it again.

Run:   python desks/mt5/research/cost_truth.py --once --budget-s 600
Fence: scripts/check_cost_truth.py
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
REPORTS = DESK / "reports"
DATA = DESK / "data"
DOCS = ROOT / "docs" / "research"

if str(ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(ROOT))

OUT = REPORTS / "COST_TRUTH.json"
MD = DOCS / "COST_TRUTH.md"
#: The artifact `net_edge_spine.exec_cell_index` reads and that NOTHING on this desk wrote --
#: measured 2026-09-23: `cost_surface.py` writes `reports/COST_SURFACE.json` under the same
#: shape, and the spine looks for this name, so the realised surface never reached the consumer.
EXEC_SURFACE = REPORTS / "EXECUTION_COST_SURFACE.json"
#: The terminal readings, cached so a box with no terminal still publishes the last measurement
#: WITH ITS AGE rather than silently reverting to the model it is supposed to check.
QUOTES = DATA / "cost_truth_quotes.json"
CURSOR = DATA / "cost_truth_cursor.json"
MISSED = DATA / "missed_growth.jsonl"

UNIVERSE = DATA / "universe" / "universe.json"
FUSION_COST = REPORTS / "FUSION_COST.json"
COST_TO_EDGE = REPORTS / "COST_TO_EDGE.json"
NET_EDGE = REPORTS / "NET_EDGE.json"
RANKS = DATA / "net_edge_ranks.json"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
INTENTS = DATA / "order_intents.jsonl"

SEAT = "cost_truth"
MEASURED, MODELLED, UNMEASURED = "MEASURED", "MODELLED", "UNMEASURED"
OVERCHARGED, OK, UNDERCHARGED = "OVERCHARGED", "OK", "UNDERCHARGED"

#: A per-symbol realised verdict needs this many deals. Below it the reading is UNMEASURED and
#: the modelled charge stands: a thin sample must not be able to cheapen the book.
MIN_DEALS = 5
#: A session bucket needs this many M1 bars before its percentiles are a reading.
MIN_BARS = 120
#: The fence's tolerance: charged may sit this far above the measured realised cost before it is
#: a defect. 1.5x is the desk's own "two estimators disagreeing" band from `fusion_cost.py`.
OVERCHARGE_TOL = 1.5
#: The organ's own cadence (hourly leg). The fence fails on an artifact older than this.
CADENCE_S = 3600
#: How stale the published surface may be before the fence calls it a defect: four missed hours.
STALE_AFTER_S = 4 * CADENCE_S
#: Session buckets in UTC, mirroring `cost_surface._PHASES` exactly so the two agree.
PHASES = ((0, 7, "asia"), (7, 12, "london"), (12, 17, "ny"), (17, 24, "late"))
#: Bytes one M1 bar costs in the terminal's numpy record, measured: 8+5*8+8+8 -> 64, +50% slack.
BAR_BYTES = 96
#: Floors, so an unreadable memory counter changes nothing (never a machine-size constant).
MIN_BARS_PER_SYMBOL = 10_080          # seven days of M1
MAX_BARS_PER_SYMBOL = 44_640          # thirty-one days of M1: the account's whole deal history


# ----------------------------------------------------------------------------------- reading


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if len(out) >= limit:
                    break
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return out
    return out


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def free_bytes() -> tuple[float | None, str]:
    """Measured free physical memory on THIS box, with its source named.

    NEVER a machine-size constant: the desk has already paid for a floor sized off the other
    box (CLAUDE.md, 2026-09-15). psutil first, then the desk's own `stall_watch.json`, then an
    honest None which lands the caller on its floor.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return float(psutil.virtual_memory().available), "psutil.virtual_memory().available"
    except Exception:
        pass
    sw = _json(DATA / "stall_watch.json")
    mb = _f(((sw or {}).get("memory") or {}).get("free_phys_mb")) if isinstance(sw, dict) else None
    if mb is not None:
        return mb * 1024.0 * 1024.0, "data/stall_watch.json memory.free_phys_mb"
    return None, "no readable memory counter on this box"


def bars_per_symbol(n_symbols: int) -> tuple[int, str]:
    """M1 bars to pull per symbol, DERIVED from measured free memory, floored at seven days."""
    avail, src = free_bytes()
    if avail is None or n_symbols <= 0:
        return MIN_BARS_PER_SYMBOL, f"floor: {src}"
    room = int((avail * 0.25) / BAR_BYTES / max(1, n_symbols))
    cap = max(MIN_BARS_PER_SYMBOL, min(MAX_BARS_PER_SYMBOL, room))
    return cap, f"{src} -> 25% / {BAR_BYTES}B per bar / {n_symbols} symbols"


# ------------------------------------------------------------------------------- statistics


def pcts(values: list[float]) -> dict[str, Any]:
    """The distribution, never one number. `zero_frac` is published because a zero spread is a
    REAL reading on a commission-only venue and a fabricated one on a symbol that quotes."""
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0, "status": UNMEASURED}
    n = len(vals)

    def q(p: float) -> float:
        idx = min(n - 1, max(0, round(p * (n - 1))))
        return vals[idx]

    return {"n": n, "status": MEASURED, "p10": round(q(0.10), 4), "p50": round(q(0.50), 4),
            "p90": round(q(0.90), 4), "max": round(vals[-1], 4),
            "mean": round(statistics.fmean(vals), 4),
            "zero_frac": round(sum(1 for v in vals if v == 0.0) / n, 4)}


def session_of(hour_utc: int, rollover_hour: int | None) -> str:
    """Which session bucket an hour belongs to. The rollover hour -- the server's own midnight,
    MEASURED from the terminal's clock offset, never assumed -- is its own bucket because the
    swap is charged there and the book is thinnest there."""
    if rollover_hour is not None and int(hour_utc) == int(rollover_hour):
        return "rollover"
    for lo, hi, name in PHASES:
        if lo <= hour_utc < hi:
            return name
    return "late"


# ---------------------------------------------------------------------------- what is charged


def raw_regime_mult() -> tuple[float, str]:
    """The RAW regime's spread multiplier, from the desk's own table rather than a copy."""
    try:
        from libs.portfolio.fusion_cost import COST_REGIMES
        mult = _f(COST_REGIMES.get("RAW"))
        if mult and mult > 0:
            return float(mult), "libs/portfolio/fusion_cost.COST_REGIMES['RAW']"
    except Exception:
        pass
    return 0.2, "fallback 0.2: libs/portfolio/fusion_cost could not be imported"


def model_commission_per_side() -> tuple[float, str]:
    try:
        from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE
        return float(COMMISSION_PER_LOT_PER_SIDE), "libs/portfolio/fusion_cost"
    except Exception:
        return 2.25, "fallback 2.25: libs/portfolio/fusion_cost could not be imported"


def charged_reading(symbol: str, meta: dict[str, Any] | None, fusion_row: dict[str, Any] | None,
                    cost_row: dict[str, Any] | None) -> dict[str, Any]:
    """What the desk's own model bills for this symbol, with every source named.

    `spine_commission_ratio` is the multiplier `net_edge_spine.commission_term` applies to the
    one-way `spread_r`; `true_commission_ratio` is what the same two numbers imply once the RAW
    regime's 0.2x is divided back out. The gap between them is charged to every cell that owns a
    fusion row, and commission is a median 98% of the charged cost on this account.
    """
    mult, mult_src = raw_regime_mult()
    out: dict[str, Any] = {"symbol": symbol, "raw_regime_mult": mult,
                           "raw_regime_source": mult_src}
    m = meta if isinstance(meta, dict) else {}
    out["charged_pts"] = _f(m.get("median_spread_pts"))
    out["charged_pts_source"] = "data/universe/universe.json median_spread_pts"
    out["spread_pts_at_collection"] = _f(m.get("spread_pts_at_collection"))
    out["tick_size"] = _f(m.get("tick_size"))
    out["contract_size"] = _f(m.get("contract_size"))
    out["swap_long_charged"] = _f(m.get("swap_long"))
    out["swap_short_charged"] = _f(m.get("swap_short"))
    rt = (fusion_row or {}).get("round_trip_per_lot") or {}
    raw, zero, wide = _f(rt.get("RAW")), _f(rt.get("ZERO")), _f(rt.get("WIDE"))
    out["round_trip_per_lot"] = {"RAW": raw, "ZERO": zero, "WIDE": wide}
    if raw is not None and zero is not None and raw > zero:
        spine = zero / (raw - zero)
        out["spine_commission_ratio"] = round(spine, 4)
        out["true_commission_ratio"] = round(spine * mult, 4)
        out["commission_ratio_overcharge"] = round(1.0 / mult, 4)
    else:
        out["spine_commission_ratio"] = None
        out["true_commission_ratio"] = None
        out["commission_ratio_overcharge"] = None
    if isinstance(cost_row, dict):
        out["spread_r"] = _f(cost_row.get("spread_r"))
        out["swap_r"] = _f(cost_row.get("swap_r"))
        out["stop_pts"] = _f(cost_row.get("stop_pts"))
    return out


# ----------------------------------------------------------------------------- what is quoted


def quoted_reading(info: dict[str, Any] | None, spreads: list[tuple[int, float]],
                   rollover_hour: int | None) -> dict[str, Any]:
    """The broker's own spread, as a DISTRIBUTION over the session, plus the live snapshot.

    `spreads` is (hour_utc, spread_pts) per M1 bar of the window. One snapshot is not the cost a
    strategy pays, so the snapshot is published as one row of the distribution and never as the
    reading.
    """
    if not isinstance(info, dict):
        return {"status": UNMEASURED,
                "why": "no terminal reading for this symbol on this box"}
    out: dict[str, Any] = {"status": MEASURED, "live_spread_pts": _f(info.get("spread")),
                           "point": _f(info.get("point")), "digits": info.get("digits"),
                           "contract_size": _f(info.get("trade_contract_size")),
                           "swap_long": _f(info.get("swap_long")),
                           "swap_short": _f(info.get("swap_short")),
                           "swap_mode": info.get("swap_mode"),
                           "swap_rollover3days": info.get("swap_rollover3days"),
                           "stops_level_pts": _f(info.get("trade_stops_level")),
                           "freeze_level_pts": _f(info.get("trade_freeze_level")),
                           "tick_value": _f(info.get("trade_tick_value")),
                           "tick_size": _f(info.get("trade_tick_size")),
                           "volume_min": _f(info.get("volume_min")),
                           "volume_step": _f(info.get("volume_step")),
                           "spread_float": info.get("spread_float"),
                           "currency_profit": info.get("currency_profit"),
                           "currency_margin": info.get("currency_margin"),
                           "at": info.get("at")}
    if not spreads:
        out["tape"] = {"status": UNMEASURED, "why": "no M1 bars pulled for this symbol yet"}
        return out
    out["tape"] = {"pooled": pcts([s for _h, s in spreads]),
                   "by_session": {}, "window_bars": len(spreads)}
    buckets: dict[str, list[float]] = {}
    for hour, spread in spreads:
        buckets.setdefault(session_of(hour, rollover_hour), []).append(spread)
    for name, vals in sorted(buckets.items()):
        cell = pcts(vals)
        if cell.get("n", 0) < MIN_BARS:
            cell = {"n": cell.get("n", 0), "status": UNMEASURED,
                    "why": f"under {MIN_BARS} M1 bars in this bucket"}
        out["tape"]["by_session"][name] = cell
    return out


# --------------------------------------------------------------------------- what was realised


def realised_reading(symbol: str, deals: list[dict[str, Any]], ledger: list[dict[str, Any]],
                     intents_by_ticket: dict[int, dict[str, Any]],
                     meta: dict[str, Any] | None,
                     info: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the account actually paid on this symbol: commission, swap, slippage, all in R.

    Commission and swap come from the terminal's own deal records, which carry them in ACCOUNT
    currency. The R denominator is built from the row's OWN stop distance through the terminal's
    `trade_tick_value` / `trade_tick_size` -- account currency per tick per lot -- so numerator
    and denominator are the same currency by construction.

    `live_ledger.risk_quote` is NOT used and the reason is measured (2026-09-23): it holds a
    stop distance in PRICE units on some rows (EURCHF 0.00034, XAUUSD 2.06) and a money amount
    on others (EURGBP 5.67), and `r_multiple` is 0.0 on every row of the four symbols sampled.
    Dividing a EUR commission by a price distance produced a 45R commission on EURCHF -- a
    number that would have justified any refusal at all.

    Entry slippage is `fill - intended` against the desk's OWN decision reference, signed so
    POSITIVE is adverse; in R it is simply `slip / stop_distance`, in which the lot size and the
    tick value cancel. Exit slippage is measured only where the exit was at a recorded SL/TP
    level -- a discretionary exit has no reference and reports nothing rather than zero.
    """
    mine = [d for d in deals if d.get("sym") == symbol]
    entries = [d for d in mine if d.get("entry") == 0 and (_f(d.get("vol")) or 0) > 0]
    exits = [d for d in mine if d.get("entry") == 1 and (_f(d.get("vol")) or 0) > 0]
    out: dict[str, Any] = {"symbol": symbol, "n_deals": len(mine), "n_entries": len(entries),
                           "n_exits": len(exits)}
    if len(mine) < MIN_DEALS:
        out["status"] = UNMEASURED
        out["why"] = (f"{len(mine)} deal(s) on this symbol, under MIN_DEALS={MIN_DEALS}: the "
                      "modelled charge stands and is not cheapened by a thin sample")
        return out
    out["status"] = MEASURED
    per_side = [abs(_f(d.get("comm")) or 0.0) / (_f(d.get("vol")) or 1.0)
                for d in mine if (_f(d.get("vol")) or 0) > 0 and _f(d.get("comm")) is not None
                and d.get("entry") in (0, 1)]
    out["commission_per_lot_per_side"] = pcts(per_side)
    swaps = [_f(d.get("swap")) or 0.0 for d in mine]
    out["swap_total_account_ccy"] = round(sum(swaps), 4)
    out["swap_nonzero_deals"] = sum(1 for s in swaps if s != 0.0)
    # -- slippage against the desk's own decision reference
    point = (_f((info or {}).get("trade_tick_size"))
             or _f((meta or {}).get("tick_size")) or 0.0)
    tick_value = (_f((info or {}).get("trade_tick_value"))
                  or _f((meta or {}).get("tick_value")) or 0.0)
    slip_entry: list[float] = []
    slip_exit: list[float] = []
    cost_rs: list[float] = []
    comm_rs: list[float] = []
    stops_pts: list[float] = []
    for row in ledger:
        if row.get("symbol") != symbol:
            continue
        direction = 1 if _f(row.get("side")) == 0 else -1
        entry_px = _f(row.get("entry_price"))
        fill_px = _f(row.get("fill_price"))
        vol = _f(row.get("volume")) or 0.0
        sl = _f(row.get("sl"))
        # THE R DENOMINATOR: the row's own stop distance, through the terminal's tick value.
        stop_px = abs(entry_px - sl) if (entry_px is not None and sl) else None
        if stop_px and point > 0:
            stops_pts.append(stop_px / point)
        risk_acct = ((stop_px / point) * tick_value * vol
                     if (stop_px and point > 0 and tick_value > 0 and vol > 0) else 0.0)
        comm = abs(_f(row.get("commission")) or 0.0)
        swap = -(_f(row.get("swap")) or 0.0)
        if risk_acct > 0:
            comm_rs.append((comm + max(swap, 0.0)) / risk_acct)
        intent = None
        for key in ("entry_order", "order", "position_id", "entry_deal"):
            ticket = row.get(key)
            if ticket is not None and int(ticket) in intents_by_ticket:
                intent = intents_by_ticket[int(ticket)]
                break
        if intent is not None and point > 0 and entry_px is not None:
            want = _f(intent.get("intended"))
            if want is not None:
                slip_entry.append((entry_px - want) * direction / point)
                if stop_px:
                    # lot size and tick value cancel: slip in R is slip over the stop
                    cost_rs.append(abs(entry_px - want) / stop_px)
        # the exit reference is the recorded stop or target it was sent to
        if point > 0 and fill_px is not None:
            for level_key in ("sl", "tp"):
                level = _f(row.get(level_key))
                if level is None or level <= 0:
                    continue
                if abs(fill_px - level) / max(point, 1e-12) <= 500:
                    slip_exit.append((level - fill_px) * direction / point)
                    break
    out["entry_slip_pts"] = pcts(slip_entry)
    out["exit_slip_pts"] = pcts(slip_exit)
    out["commission_swap_r"] = pcts(comm_rs)
    out["entry_slip_r"] = pcts(cost_rs)
    out["stop_pts_realised"] = pcts(stops_pts)
    out["impact"] = {"status": UNMEASURED,
                     "why": "market impact needs matched fills at size and matched_fills is 0; "
                            "an unpriced term makes net a BOUND, never a zero"}
    return out


def realised_spread_at_fills(symbol: str, deals: list[dict[str, Any]],
                             bars: dict[int, float]) -> dict[str, Any]:
    """The broker's OWN quoted spread at the minutes the desk actually filled.

    This is the reading that decides whether a charge was fair: not the pooled median of the
    symbol, and not the median of the hour, but the spread quoted at the desk's own fill times.
    `bars` maps an M1 bar's epoch-minute to its spread in points.
    """
    seen: list[float] = []
    for deal in deals:
        if deal.get("sym") != symbol:
            continue
        stamp = _f(deal.get("epoch"))
        if stamp is None:
            continue
        spread = bars.get(int(stamp // 60) * 60)
        if spread is not None:
            seen.append(float(spread))
    cell = pcts(seen)
    if cell.get("n", 0) == 0:
        return {"status": UNMEASURED,
                "why": "no M1 bar in the window covers this symbol's fill minutes"}
    return cell


# ------------------------------------------------------------------------------- the compare


def compare(charged: dict[str, Any], quoted: dict[str, Any],
            realised: dict[str, Any], at_fill: dict[str, Any]) -> dict[str, Any]:
    """Charged against quoted against realised, with the ratio named in both directions.

    A ratio ABOVE 1 is the model charging more than the venue -- the false-null direction, the
    one the desk has no other instrument for. A ratio below 1 is an undercharge and is reported
    with the same weight; neither is silently corrected here.
    """
    out: dict[str, Any] = {"verdict": UNMEASURED}
    ch = _f(charged.get("charged_pts"))
    tape = (quoted.get("tape") or {}) if isinstance(quoted, dict) else {}
    pooled = tape.get("pooled") or {}
    quoted_p50 = _f(pooled.get("p50")) if pooled.get("status") == MEASURED else None
    quoted_p90 = _f(pooled.get("p90")) if pooled.get("status") == MEASURED else None
    live = _f(quoted.get("live_spread_pts")) if isinstance(quoted, dict) else None
    fill_p50 = _f(at_fill.get("p50")) if at_fill.get("status") == MEASURED else None
    out["charged_pts"] = ch
    out["quoted_p50_pts"] = quoted_p50
    out["quoted_p90_pts"] = quoted_p90
    out["quoted_live_pts"] = live
    out["quoted_at_fills_p50_pts"] = fill_p50
    reference = fill_p50 if fill_p50 is not None else quoted_p50
    out["reference_pts"] = reference
    out["reference_basis"] = ("quoted spread at the desk's own fill minutes" if fill_p50
                              is not None else "pooled M1 median over the window")
    if ch is None or reference is None:
        out["why"] = "no charged scalar or no terminal reading: the comparison is unmeasured"
    elif reference > 0:
        ratio = ch / reference
        out["spread_charged_over_quoted"] = round(ratio, 4)
        out["verdict"] = (OVERCHARGED if ratio > OVERCHARGE_TOL
                          else UNDERCHARGED if ratio < 1.0 / OVERCHARGE_TOL else OK)
    elif ch <= 0:
        out["verdict"] = OK
    else:
        # THE MEDIAN IS ZERO. MT5 stores a bar's spread as a WHOLE number of points, so a book
        # quoting half a point reads 0 at the median and the charge can still be honest. The
        # comparison falls to the widest readings the same tape holds -- p90, then the live
        # tick -- and only calls the charge manufactured when EVERY one of them is zero too.
        fallback = next((v for v in (quoted_p90, live) if v is not None and v > 0), None)
        if fallback is None:
            out["spread_charged_over_quoted"] = None
            out["verdict"] = OVERCHARGED
            out["why"] = (f"charged {ch} pts against a venue quoting 0.0 at the median, at the "
                          f"p90 and live over {pooled.get('n')} M1 bars: Fusion Zero is "
                          "genuinely commission-only here, so the spread charge is manufactured")
        else:
            ratio = ch / fallback
            out["spread_charged_over_quoted"] = round(ratio, 4)
            out["reference_pts"] = fallback
            out["reference_basis"] = ("the median M1 spread is 0 at this venue's point "
                                      "resolution; compared against the p90 / live quote")
            out["verdict"] = (OVERCHARGED if ratio > OVERCHARGE_TOL
                              else UNDERCHARGED if ratio < 1.0 / OVERCHARGE_TOL else OK)
    # -- the commission term, which is a median 98% of the charged cost on this account
    model_c, model_src = model_commission_per_side()
    real = (realised.get("commission_per_lot_per_side") or {}) if isinstance(realised, dict) \
        else {}
    real_c = _f(real.get("p50")) if real.get("status") == MEASURED else None
    out["commission_model_per_side"] = model_c
    out["commission_model_source"] = model_src
    out["commission_realised_per_side"] = real_c
    if real_c and real_c > 0:
        out["commission_rate_overcharge"] = round(model_c / real_c, 4)
    ratio_over = _f(charged.get("commission_ratio_overcharge"))
    if ratio_over is not None:
        rate_over = _f(out.get("commission_rate_overcharge")) or 1.0
        out["commission_total_overcharge"] = round(ratio_over * rate_over, 4)
    return out


# --------------------------------------------------------------------------------- re-judging


def rejudge(net_edge_doc: Any, ranks_doc: Any,
            by_symbol: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Re-price the spine's OWN published rows with the corrected commission and spread.

    Nothing here edits the spine or its artifact: its published `terms` block carries every
    number needed to restate the arithmetic, so the correction is applied to the rows as
    published and the difference is the answer to "how many refusals survive honest costs".
    """
    rows: list[dict[str, Any]] = []
    doc = net_edge_doc if isinstance(net_edge_doc, dict) else {}
    cells = (ranks_doc or {}).get("by_cell") if isinstance(ranks_doc, dict) else {}
    pool: list[tuple[str, dict[str, Any]]] = []
    for row in doc.get("cost_dead") or []:
        if isinstance(row, dict):
            pool.append(("cost_dead", row))
    for key, row in (cells or {}).items():
        if isinstance(row, dict):
            row = {**row, "symbol": str(key).split("|")[0], "family": str(key).split("|")[-1],
                   "key": row.get("cell") or key}
            pool.append(("ranked", row))
    survived = restored = 0
    for lane, row in pool:
        terms = row.get("terms") or {}
        sym = str(row.get("symbol") or "")
        corr = by_symbol.get(sym) or {}
        gross = _f(row.get("gross"))
        net = _f(row.get("net"))
        if gross is None or net is None:
            continue
        comm = _f((terms.get("commission") or {}).get("value")) or 0.0
        spread = _f((terms.get("spread_slippage") or {}).get("value")) or 0.0
        over_c = _f(corr.get("commission_total_overcharge")) or 1.0
        over_s = _f(corr.get("spread_charged_over_quoted"))
        comm_fixed = comm / over_c if over_c > 0 else comm
        spread_fixed = spread / over_s if (over_s and over_s > 1.0) else spread
        delta = (comm - comm_fixed) + (spread - spread_fixed)
        net_fixed = net + delta
        if delta <= 0:
            continue
        flipped_back = net < 0 <= net_fixed
        if flipped_back:
            restored += 1
        if net_fixed >= 0:
            survived += 1
        rows.append({"lane": lane, "cell": row.get("key") or row.get("cell"), "symbol": sym,
                     "family": row.get("family"), "gross": round(gross, 8),
                     "net_as_charged": round(net, 8), "net_on_measured_cost": round(net_fixed, 8),
                     "commission_charged": round(comm, 8),
                     "commission_measured": round(comm_fixed, 8),
                     "spread_charged": round(spread, 8), "spread_measured": round(spread_fixed, 8),
                     "overcharge_removed_r": round(delta, 8),
                     "restored_to_queue": flipped_back,
                     "why": ("refused on a cost the broker does not charge" if flipped_back
                             else "still negative on measured costs: the refusal earns its place")})
    rows.sort(key=lambda r: -float(r["overcharge_removed_r"]))
    return {"n_rows_repriced": len(rows), "n_positive_on_measured_cost": survived,
            "n_restored_to_queue": restored, "rows": rows[:120],
            "rule": ("the spine's own published terms, re-priced with the measured commission "
                     "rate and the measured regime multiplier and with the spread capped at the "
                     "broker's quoted median; no file of the spine's is edited")}


def missed_lines(rejudged: dict[str, Any], since: str | None) -> list[dict[str, Any]]:
    """The GROWTH-GOVERNANCE bill for every cell refused on a cost the venue does not charge."""
    day = datetime.now(tz=UTC).date().isoformat()
    out: list[dict[str, Any]] = []
    for row in rejudged.get("rows") or []:
        if not row.get("restored_to_queue"):
            continue
        out.append({"day": day, "rail": "cost_truth_overcharge",
                    "value": round(float(row["overcharge_removed_r"]), 8),
                    "at": _now(), "cell": row.get("cell"), "symbol": row.get("symbol"),
                    "family": row.get("family"),
                    "net_as_charged": row.get("net_as_charged"),
                    "net_on_measured_cost": row.get("net_on_measured_cost"),
                    "refused_since": since, "two_sided": True,
                    "why": ("this cell was refused on an overcharged cost; the growth given up "
                            "is its own net at the measured cost over the period the refusal "
                            "stood (Rule 1: a risk reduction must prove it raises E[log W])")})
    return out


# ----------------------------------------------------------------------- the execution surface


def execution_surface(symbols: list[dict[str, Any]]) -> dict[str, Any]:
    """The realised surface in the SHAPE `net_edge_spine.exec_cell_index` already reads.

    cost_r here is the desk's realised EXECUTION cost -- the broker's quoted spread at the
    desk's own fill minutes, crossed once, over the cell's own risk, plus measured adverse entry
    slippage where the intent join exists. It deliberately EXCLUDES commission and swap: the
    spine charges those as their own terms, and `cost_surface.deal_costs` builds a cost_r that
    is commission + swap ONLY, so feeding that number into the spine's spread slot charges
    commission twice. This one is a spread/slippage reading and says so in every row.
    """
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        realised = sym.get("realised") or {}
        cmp_ = sym.get("compare") or {}
        if realised.get("status") != MEASURED:
            continue
        stop_pts = _f((sym.get("charged") or {}).get("stop_pts"))
        stop_basis = "COST_TO_EDGE.json stop_pts"
        if stop_pts is None or stop_pts <= 0:
            # the desk's OWN stops on this symbol, when the cost report never priced the cell
            own = realised.get("stop_pts_realised") or {}
            stop_pts = _f(own.get("p50")) if own.get("status") == MEASURED else None
            stop_basis = "median stop distance of this symbol's own live trades"
        ref = _f(cmp_.get("reference_pts"))
        if stop_pts is None or stop_pts <= 0 or ref is None:
            continue
        slip = (realised.get("entry_slip_r") or {})
        # A SINGLE FILL IS NOT A SLIPPAGE READING. Measured 2026-09-23: EURGBP's one joinable
        # intent slipped 14 pts on a 26 pt stop, which alone would have published a 0.54R
        # execution cost and killed the symbol. Under MIN_DEALS the term stays UNMEASURED and
        # the published cost is a LOWER BOUND -- which `net_edge` already models as a bound.
        slip_r = (_f(slip.get("p50")) if slip.get("status") == MEASURED
                  and int(slip.get("n") or 0) >= MIN_DEALS else None)
        cost_r = ref / stop_pts + (slip_r or 0.0)
        rows.append({"asset": sym["symbol"], "cost_basis": MEASURED,
                     "cost_r": round(float(cost_r), 8),
                     "cost_n": int(realised.get("n_deals") or 0),
                     "cost_resolved_at": _now(),
                     "cost_terms": ["quoted_spread_at_fill_minutes",
                                    "measured_entry_slippage" if slip_r is not None
                                    else "entry_slippage_UNMEASURED"],
                     "excludes": ["commission", "swap", "market_impact"],
                     "slippage_status": MEASURED if slip_r is not None else UNMEASURED,
                     "slippage_n": int(slip.get("n") or 0),
                     "cost_r_is_bound": slip_r is None,
                     "stop_pts": round(float(stop_pts), 4), "stop_basis": stop_basis,
                     "why": (f"{ref} pts quoted at this symbol's own fill minutes over a "
                             f"{stop_pts} pt stop ({stop_basis})"
                             + (f", plus a measured {slip_r:+.5f}R entry slip" if slip_r
                                is not None else "; entry slippage is UNMEASURED and is not "
                                "replaced by a default"))})
    return {"at": _now(), "producer": "desks/mt5/research/cost_truth.py",
            "unit": "R per round trip, spread and slippage only",
            "n_cells": len(rows), "net_alpha": rows,
            "rule": ("the realised execution surface the spine reads. Commission and swap are "
                     "NOT in cost_r: the spine prices them as their own terms. Market impact is "
                     "UNMEASURED and makes net a BOUND rather than a zero.")}


# ------------------------------------------------------------------------------- the terminal


def terminal_snapshot(symbols: list[str], budget_s: float, bars_cap: int,
                      ) -> dict[str, Any]:  # pragma: no cover - needs a live terminal
    """Every measurable broker fact for `symbols`, from the terminal on THIS box.

    A box with no terminal is not an error: the block comes back UNMEASURED with the reason and
    the cached readings keep their age. The desk never fabricates a venue number.
    """
    try:
        import MetaTrader5 as mt5
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"MetaTrader5 is not importable here: {exc}"}
    if not mt5.initialize():
        return {"status": UNMEASURED, "why": f"terminal did not initialise: {mt5.last_error()}"}
    started = time.monotonic()
    out: dict[str, Any] = {"status": MEASURED, "symbols": {}, "bars": {}, "deals": []}
    try:
        acct = mt5.account_info()
        term = mt5.terminal_info()
        out["account"] = {"login": getattr(acct, "login", None),
                          "currency": getattr(acct, "currency", None),
                          "company": getattr(acct, "company", None),
                          "server": getattr(acct, "server", None),
                          "margin_mode": getattr(acct, "margin_mode", None),
                          "leverage": getattr(acct, "leverage", None)}
        out["terminal"] = {"name": getattr(term, "name", None),
                           "connected": getattr(term, "connected", None),
                           "build": getattr(term, "build", None)}
        probe = mt5.symbol_info_tick(symbols[0]) if symbols else None
        if probe is not None and getattr(probe, "time", None):
            offset = (datetime.fromtimestamp(probe.time, tz=UTC)
                      - datetime.now(tz=UTC)).total_seconds() / 3600.0
            out["server_utc_offset_hours"] = round(offset)
            out["rollover_hour_utc"] = int((24 - round(offset)) % 24)
        # -- deal history: the account's whole realised record
        deals = mt5.history_deals_get(datetime(2020, 1, 1, tzinfo=UTC),
                                      datetime.now(tz=UTC) + timedelta(days=2))
        for deal in deals or []:
            out["deals"].append({"ticket": deal.ticket, "order": deal.order,
                                 "position": deal.position_id, "epoch": int(deal.time),
                                 "at": datetime.fromtimestamp(deal.time, tz=UTC).isoformat(),
                                 "sym": deal.symbol, "type": int(deal.type),
                                 "entry": int(deal.entry), "vol": float(deal.volume),
                                 "price": float(deal.price), "comm": float(deal.commission),
                                 "swap": float(deal.swap), "profit": float(deal.profit),
                                 "fee": float(getattr(deal, "fee", 0.0) or 0.0)})
        for symbol in symbols:
            if time.monotonic() - started > budget_s:
                out["budget_exhausted_at"] = symbol
                break
            info = mt5.symbol_info(symbol)
            if info is None:
                out["symbols"][symbol] = {"status": UNMEASURED,
                                          "why": "symbol not in this terminal's registry"}
                continue
            tick = mt5.symbol_info_tick(symbol)
            out["symbols"][symbol] = {
                "at": _now(), "spread": info.spread, "point": info.point,
                "digits": info.digits, "trade_contract_size": info.trade_contract_size,
                "swap_long": info.swap_long, "swap_short": info.swap_short,
                "swap_mode": int(info.swap_mode),
                "swap_rollover3days": int(getattr(info, "swap_rollover3days", -1)),
                "trade_stops_level": info.trade_stops_level,
                "trade_freeze_level": getattr(info, "trade_freeze_level", None),
                "trade_tick_value": info.trade_tick_value,
                "trade_tick_size": info.trade_tick_size,
                "volume_min": info.volume_min, "volume_step": info.volume_step,
                "spread_float": bool(info.spread_float),
                "currency_profit": info.currency_profit,
                "currency_margin": info.currency_margin,
                "bid": getattr(tick, "bid", None), "ask": getattr(tick, "ask", None),
                "live_spread_pts": (round((tick.ask - tick.bid) / info.point, 2)
                                    if tick is not None and info.point else None)}
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, int(bars_cap))
            if rates is None or len(rates) == 0:
                continue
            out["bars"][symbol] = [(int(r["time"]), float(r["spread"])) for r in rates]
    finally:
        mt5.shutdown()
    out["elapsed_s"] = round(time.monotonic() - started, 2)
    return out


# ------------------------------------------------------------------------------------- build


def build(universe: dict[str, Any], fusion: Any, cost_to_edge: Any, snapshot: dict[str, Any],
          ledger: list[dict[str, Any]], intents: list[dict[str, Any]],
          net_edge_doc: Any, ranks_doc: Any, symbols: list[str]) -> dict[str, Any]:
    """The whole report: charged vs quoted vs realised per symbol, then the re-judge."""
    fusion_rows = {str(r.get("symbol")): r for r in ((fusion or {}).get("symbols") or [])
                   if isinstance(r, dict) and r.get("symbol")}
    cost_rows: dict[str, dict[str, Any]] = {}
    for row in ((cost_to_edge or {}).get("by_cost") or []):
        if isinstance(row, dict) and row.get("symbol") and row.get("measured"):
            cost_rows.setdefault(str(row["symbol"]), row)
    deals = list(snapshot.get("deals") or [])
    intents_by_ticket = {int(i["ticket"]): i for i in intents
                         if isinstance(i, dict) and _f(i.get("ticket"))}
    rollover = snapshot.get("rollover_hour_utc")
    rows: list[dict[str, Any]] = []
    by_symbol_cmp: dict[str, dict[str, Any]] = {}
    for symbol in sorted(set(symbols)):
        meta = universe.get(symbol) if isinstance(universe, dict) else None
        info = (snapshot.get("symbols") or {}).get(symbol)
        bars = (snapshot.get("bars") or {}).get(symbol) or []
        spreads = [(datetime.fromtimestamp(int(t), tz=UTC).hour, float(s)) for t, s in bars]
        bar_by_minute = {int(t): float(s) for t, s in bars}
        charged = charged_reading(symbol, meta, fusion_rows.get(symbol), cost_rows.get(symbol))
        quoted = quoted_reading(info if isinstance(info, dict) and info.get("status") != UNMEASURED
                                else None, spreads, rollover)
        realised = realised_reading(symbol, deals, ledger, intents_by_ticket, meta,
                                    info if isinstance(info, dict) else None)
        at_fill = realised_spread_at_fills(symbol, deals, bar_by_minute)
        cmp_ = compare(charged, quoted, realised, at_fill)
        by_symbol_cmp[symbol] = cmp_
        rows.append({"symbol": symbol, "charged": charged, "quoted": quoted,
                     "realised": realised, "quoted_at_fills": at_fill, "compare": cmp_})
    over = [{"symbol": r["symbol"],
             "spread_charged_over_quoted": r["compare"].get("spread_charged_over_quoted"),
             "commission_total_overcharge": r["compare"].get("commission_total_overcharge"),
             "charged_pts": r["compare"].get("charged_pts"),
             "reference_pts": r["compare"].get("reference_pts"),
             "verdict": r["compare"].get("verdict")}
            for r in rows
            if r["compare"].get("verdict") == OVERCHARGED
            or (_f(r["compare"].get("commission_total_overcharge")) or 0) > OVERCHARGE_TOL]
    over.sort(key=lambda r: -((_f(r.get("spread_charged_over_quoted")) or 0.0)
                              + (_f(r.get("commission_total_overcharge")) or 0.0)))
    judged = rejudge(net_edge_doc, ranks_doc, by_symbol_cmp)
    model_c, model_src = model_commission_per_side()
    realised_c = [r["realised"]["commission_per_lot_per_side"]["p50"] for r in rows
                  if (r["realised"].get("commission_per_lot_per_side") or {}).get("status")
                  == MEASURED]
    mult, mult_src = raw_regime_mult()
    return {
        "at": _now(), "seat": SEAT,
        "account": snapshot.get("account"), "terminal": snapshot.get("terminal"),
        "terminal_status": snapshot.get("status", UNMEASURED),
        "terminal_why": snapshot.get("why"),
        "server_utc_offset_hours": snapshot.get("server_utc_offset_hours"),
        "rollover_hour_utc": rollover,
        "cadence_s": CADENCE_S, "stale_after_s": STALE_AFTER_S,
        "overcharge_tolerance": OVERCHARGE_TOL,
        "n_symbols": len(rows), "n_deals": len(deals),
        "n_symbols_measured": sum(1 for r in rows if r["realised"].get("status") == MEASURED),
        "commission": {
            "model_per_lot_per_side": model_c, "model_source": model_src,
            "realised_per_lot_per_side": pcts(realised_c),
            "rate_overcharge": (round(model_c / statistics.fmean(realised_c), 4)
                                if realised_c else None),
            "regime_multiplier": mult, "regime_source": mult_src,
            "ratio_overcharge": round(1.0 / mult, 4) if mult else None,
            "total_overcharge": (round((model_c / statistics.fmean(realised_c)) / mult, 4)
                                 if realised_c and mult else None),
            "why": ("the spine derives commission/spread as zero/(raw-zero), but raw is the "
                    f"{mult}x regime, so raw-zero is {mult} of the spread and the ratio is "
                    f"{round(1.0 / mult, 2) if mult else '?'}x too large; the rate itself is "
                    "charged in account currency at a figure documented as USD")},
        "consumer_defects": consumer_defects(mult),
        "overcharged": over, "n_overcharged": len(over),
        "rejudge": judged,
        "impact": {"status": UNMEASURED,
                   "why": "matched_fills is 0: market impact is unpriced, so every net that "
                          "needs it is a BOUND and the verdict says so"},
        "symbols": rows,
        "rule": ("three independent readings per symbol -- what the model charges, what the "
                 "broker quotes over the whole session, and what the account actually paid. A "
                 "correction only ever moves the charge toward the measured MEDIAN; an "
                 "unmeasured term stays UNMEASURED and makes net a bound. Nothing here vetoes, "
                 "sizes or promotes."),
    }


def consumer_defects(mult: float) -> list[dict[str, Any]]:
    """Every place the desk's own code charges more than the venue, named with its fix.

    These live in files this organ does not own (`net_edge_spine.py` and `net_edge.py` belong to
    another builder, `fusion_cost.py` is on the money path). They are published rather than
    patched, so the correction is a decision with evidence and not a silent re-pricing.
    """
    return [
        {"where": "desks/mt5/research/net_edge_spine.py:commission_term",
         "defect": "ratio = zero / (raw - zero) treats the RAW regime's "
                   f"{mult}x spread as the whole spread",
         "charged_over_true": round(1.0 / mult, 4) if mult else None,
         "fix": f"ratio = {mult} * zero / (raw - zero)  # the RAW regime multiplier, divided out",
         "owner": "net-edge builder", "status": "REPORTED"},
        {"where": "libs/portfolio/fusion_cost.py:COMMISSION_PER_LOT_PER_SIDE",
         "defect": "2.25 is documented as USD and applied as account currency; the account pays "
                   "2.00 EUR per lot per side, measured over every deal it has ever done",
         "charged_over_true": 1.125,
         "fix": "set it from the measured per-side commission published here, or state the "
                "currency and convert",
         "owner": "money path", "status": "REPORTED"},
        {"where": "desks/mt5/research/cost_surface.py:_EXEC_OUT",
         "defect": "writes reports/COST_SURFACE.json while net_edge_spine reads "
                   "reports/EXECUTION_COST_SURFACE.json, so the realised surface never reached "
                   "the consumer and every spread term fell back to the modelled scalar",
         "charged_over_true": None,
         "fix": "this organ now writes EXECUTION_COST_SURFACE.json; the two producers must be "
                "reconciled to one name",
         "owner": "cost-surface builder", "status": "BRIDGED"},
        {"where": "desks/mt5/research/cost_surface.py:deal_costs",
         "defect": "cost_r there is (commission + swap)/risk, and the spine feeds cost_r into "
                   "its SPREAD term and then adds commission again",
         "charged_over_true": None,
         "fix": "keep cost_r to spread and slippage, as the surface written here does",
         "owner": "cost-surface builder", "status": "REPORTED"},
    ]


# ------------------------------------------------------------------------------------ render


def render_md(rep: dict[str, Any]) -> str:
    """The short human page. Derived: never edited by hand."""
    lines: list[str] = []
    acct = rep.get("account") or {}
    add = lines.append
    add("# COST TRUTH -- charged vs quoted vs realised")
    add("")
    add(f"Generated {rep.get('at')} by `desks/mt5/research/cost_truth.py` "
        "(hourly leg `cost_truth`). DERIVED -- edit the organ, never this page.")
    add("")
    add(f"Account **{acct.get('login')}** ({acct.get('company')}, {acct.get('server')}, "
        f"{acct.get('currency')}), terminal {rep.get('terminal_status')}, "
        f"{rep.get('n_deals')} deals, {rep.get('n_symbols')} symbols, "
        f"{rep.get('n_symbols_measured')} with a realised reading.")
    add("")
    comm = rep.get("commission") or {}
    add("## The commission term, which is ~98% of the charged cost")
    add("")
    add(f"- model charges **{comm.get('model_per_lot_per_side')}** per lot per side "
        f"({comm.get('model_source')})")
    real = (comm.get("realised_per_lot_per_side") or {})
    add(f"- account actually pays **{real.get('p50')}** per lot per side "
        f"(median over {real.get('n')} symbol readings, p10 {real.get('p10')}, "
        f"p90 {real.get('p90')})")
    add(f"- rate overcharge **{comm.get('rate_overcharge')}x**, regime overcharge "
        f"**{comm.get('ratio_overcharge')}x**, total **{comm.get('total_overcharge')}x**")
    add(f"- why: {comm.get('why')}")
    add("")
    add("## Where the model charges more than the venue")
    add("")
    add("| symbol | charged pts | quoted pts (reference) | spread ratio | commission ratio |")
    add("|---|---:|---:|---:|---:|")
    for row in (rep.get("overcharged") or [])[:25]:
        add(f"| {row.get('symbol')} | {row.get('charged_pts')} | {row.get('reference_pts')} | "
            f"{row.get('spread_charged_over_quoted')} | "
            f"{row.get('commission_total_overcharge')} |")
    add("")
    add("## Session structure (M1 spread in points, the broker's own tape)")
    add("")
    add("| symbol | asia | london | ny | late | rollover | live |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for row in (rep.get("symbols") or []):
        tape = ((row.get("quoted") or {}).get("tape") or {}).get("by_session") or {}
        if not tape:
            continue

        def cell(name: str, tape: dict[str, Any] = tape) -> str:
            got = tape.get(name) or {}
            return str(got.get("p50")) if got.get("status") == MEASURED else "-"
        add(f"| {row['symbol']} | {cell('asia')} | {cell('london')} | {cell('ny')} | "
            f"{cell('late')} | {cell('rollover')} | "
            f"{(row.get('quoted') or {}).get('live_spread_pts')} |")
    add("")
    judged = rep.get("rejudge") or {}
    add("## Re-judged on measured costs")
    add("")
    add(f"- {judged.get('n_rows_repriced')} published rows re-priced; "
        f"**{judged.get('n_restored_to_queue')}** were refused on a cost the broker does not "
        f"charge and are restored to the queue; {judged.get('n_positive_on_measured_cost')} are "
        "positive once the overcharge is removed.")
    for row in (judged.get("rows") or [])[:12]:
        add(f"  - `{row.get('cell')}` net {row.get('net_as_charged')} -> "
            f"{row.get('net_on_measured_cost')} ({row.get('why')})")
    add("")
    add("## Named defects in code this organ does not own")
    add("")
    for row in rep.get("consumer_defects") or []:
        add(f"- **{row.get('where')}** -- {row.get('defect')}. Fix: `{row.get('fix')}` "
            f"[{row.get('status')}]")
    add("")
    add(f"Impact: {(rep.get('impact') or {}).get('why')}")
    add("")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------------------------- main


def symbol_universe(ranks_doc: Any, cost_to_edge: Any, ledger: list[dict[str, Any]]) -> list[str]:
    """Every symbol the desk trades or tests, from the three places it says so."""
    syms: set[str] = set()
    for key in ((ranks_doc or {}).get("by_cell") or {}):
        syms.add(str(key).split("|")[0])
    for row in ((cost_to_edge or {}).get("by_cost") or []):
        if isinstance(row, dict) and row.get("symbol"):
            syms.add(str(row["symbol"]))
    for row in ledger:
        if row.get("symbol"):
            syms.add(str(row["symbol"]))
    return sorted(s for s in syms if s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass and exit (the leg's contract)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--md", type=Path, default=MD)
    ap.add_argument("--no-terminal", action="store_true",
                    help="skip the terminal and publish from the cached readings")
    args = ap.parse_args(argv)
    started = time.monotonic()

    universe = _json(UNIVERSE) or {}
    fusion = _json(FUSION_COST)
    cost_to_edge = _json(COST_TO_EDGE)
    net_edge_doc = _json(NET_EDGE)
    ranks_doc = _json(RANKS)
    ledger = _jsonl(LIVE_LEDGER)
    intents = _jsonl(INTENTS)
    symbols = symbol_universe(ranks_doc, cost_to_edge, ledger)

    cursor = _json(CURSOR) or {}
    cached = _json(QUOTES) or {}
    cap, cap_why = bars_per_symbol(max(1, len(symbols)))
    if args.no_terminal:
        snapshot: dict[str, Any] = {"status": UNMEASURED,
                                    "why": "--no-terminal: publishing from the cache"}
    else:
        start_at = int(cursor.get("next_index") or 0) % max(1, len(symbols))
        ordered = symbols[start_at:] + symbols[:start_at]
        snapshot = terminal_snapshot(ordered, max(30.0, args.budget_s * 0.8), cap)
    if snapshot.get("status") == MEASURED:
        merged_syms = dict(cached.get("symbols") or {})
        merged_syms.update(snapshot.get("symbols") or {})
        merged_bars = dict(cached.get("bars") or {})
        merged_bars.update(snapshot.get("bars") or {})
        snapshot["symbols"], snapshot["bars"] = merged_syms, merged_bars
        done = len(snapshot.get("symbols") or {})
        CURSOR.write_text(json.dumps({"at": _now(), "next_index": done % max(1, len(symbols)),
                                      "n_symbols": len(symbols), "bars_cap": cap,
                                      "bars_cap_why": cap_why}, indent=1) + "\n", "utf-8")
        # the cache keeps the readings, never the raw tape: bars are re-pulled, info is not
        QUOTES.write_text(json.dumps({"at": _now(), "account": snapshot.get("account"),
                                      "terminal": snapshot.get("terminal"),
                                      "server_utc_offset_hours":
                                          snapshot.get("server_utc_offset_hours"),
                                      "rollover_hour_utc": snapshot.get("rollover_hour_utc"),
                                      "symbols": snapshot.get("symbols"),
                                      "deals": snapshot.get("deals")},
                                     indent=1, sort_keys=True) + "\n", "utf-8")
    else:
        snapshot = {**cached, "status": UNMEASURED if not cached else MODELLED,
                    "why": snapshot.get("why"), "bars": {},
                    "cached_at": cached.get("at")}

    rep = build(universe, fusion, cost_to_edge, snapshot, ledger, intents,
                net_edge_doc, ranks_doc, symbols)
    rep["bars_cap"] = cap
    rep["bars_cap_why"] = cap_why
    rep["elapsed_s"] = round(time.monotonic() - started, 2)
    rep["budget_s"] = args.budget_s

    lines = missed_lines(rep.get("rejudge") or {}, (net_edge_doc or {}).get("at")
                         if isinstance(net_edge_doc, dict) else None)
    rep["missed_growth_lines"] = lines[:60]
    if lines:
        try:
            MISSED.parent.mkdir(parents=True, exist_ok=True)
            with MISSED.open("a", encoding="utf-8") as fh:
                for row in lines:
                    fh.write(json.dumps(row) + "\n")
        except OSError as exc:
            rep["missed_growth_write"] = f"NOT written: {exc}"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render_md(rep), "utf-8")
    surface = execution_surface(rep.get("symbols") or [])
    EXEC_SURFACE.write_text(json.dumps(surface, indent=1, sort_keys=True) + "\n", "utf-8")

    try:
        from libs.ops.events import emit
        emit("COST_TRUTH_MEASURED", leg=SEAT, n_symbols=rep["n_symbols"],
             n_overcharged=rep["n_overcharged"],
             n_restored=(rep.get("rejudge") or {}).get("n_restored_to_queue"))
    except Exception:
        pass

    print(f"cost_truth: {rep['n_symbols']} symbols, {rep['n_deals']} deals, "
          f"{rep['n_overcharged']} overcharged, "
          f"{(rep.get('rejudge') or {}).get('n_restored_to_queue')} refusals restored, "
          f"commission {rep['commission'].get('total_overcharge')}x -> {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
