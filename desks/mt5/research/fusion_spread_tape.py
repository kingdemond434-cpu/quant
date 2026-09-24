#!/usr/bin/env python3
"""WHAT THE SPREAD ALWAYS IS ON THIS ACCOUNT, per instrument, from the broker's own minute tape.

THE NUMBER THIS REPLACES AND WHY IT WAS NEVER A MEASUREMENT.
`scripts/repair_universe_spreads.py` recomputes `median_spread_pts` as the median of the NON-ZERO
bars of a symbol's H1 parquet. On this box that statistic does not describe this broker at all:

    sym      H1 nonzero median   H1 p25   M1 median   live symbol_info
    AUDUSD          50.0          50.0       0.0            0
    EURUSD          50.0          50.0       0.0            0
    GBPUSD          50.0          50.0       0.0            0
    AUDCHF         160.0           3.0       0.0            1
    EURCAD         160.0           3.0       0.0            2
    AUDJPY         120.0          10.0       0.0            1
    XAUUSD           4.0           2.0       5.0            6

A value of exactly 50.0 on three unrelated majors, and exactly 160.0 on two unrelated crosses, is
not a spread. MEASURED 2026-09-24 on all 248 H1 parquets the box holds:

  * every symbol carries ONE constant spread on EVERY bar from the start of its history to a
    single cut-over -- 2020-12-11 01:00 for the FX book, 2020-12-31 for the CFDs -- and the
    constant is per symbol: AUDUSD/EURUSD/GBPUSD 50 (5.0 pips), AUDCAD/AUDSGD 200, AUDNZD 240,
    AUDCHF/CADCHF 160, AUDJPY/CADJPY 120 (12 pips at 3 digits), 154 symbols 0.
  * the same constant, the same cut-over, appears in H1, H4 and D1 and in NO other column. It is
    absent from M1/M5/M15, whose history begins in 2024-2026 -- after the cut-over.
  * ~7,635 bars per FX symbol carry it, and 121 symbols begin it at the same instant,
    2018-01-02 00:00.

So it is not a desk writer and not a fill-forward. It is THE BROKER'S OWN HISTORY: Fusion's
server did not record a per-bar spread before December 2020 and serves that era at a FIXED
per-symbol spread, which the desk's downloader copied faithfully. The bug is not in the column,
it is in the statistic: after December 2020 this account quotes 0 points on 80-96% of FX bars,
so "non-zero bars only" DELETES the modern era and leaves the 2018-2020 fixed-spread block as
the majority of what survives. The exclusion selects for the placeholder.

WHAT IS USED INSTEAD, and why the zero is kept.
The M1 tape is the granularity at which a fill happens and, on this box, it begins after the
cut-over. Every M1 bar it holds carries ticks (measured: 0 no-tick bars over 248 symbols), so a
0 there is the broker's own quote and not absence -- confirmed against the live terminal on an
OPEN market: EURUSD/AUDUSD/GBPUSD/USDJPY quote bid == ask, `symbol_info.spread == 0`. That is
what a Zero account is: commission instead of spread. Dropping those bars is what produced 50.0.

BUT A ZERO IS NEVER WRITTEN. A registry spread of 0.0 prices an instrument at no cost at all and
lets a non-edge certify -- the desk already carries nine such symbols. A symbol whose central
value lands on 0 at this venue's integer-point resolution is UNMEASURED here: it keeps its old
value and is named. Absence never resolves to a clean verdict (L1.28a / WS-005).

THE WINDOW IS THE INSTRUMENT'S OWN. The session filter is `cost_surface`'s -- days carrying at
least SESSION_SHARE of the symbol's OWN measured session, never a fixed bar count -- so the
crypto CFDs keep their weekends (a Saturday is a full session for BTCUSD and does not exist for
EURUSD), a US share CFD keeps its 6.5-hour day, and no asset-class list appears anywhere.

DISPERSION IS PUBLISHED, NOT COLLAPSED. An instrument whose spread is 2 for twenty-three hours
and 158 at the rollover is not honestly described by either number: p25/p50/p75/p90/p99 and the
per-hour p50/p90 ride with every row, because the sleeves that fire at the rollover pay the tail.

THE TAPE'S CLOCK IS THE SERVER'S. Measured 2026-09-24: the parquet index runs three hours ahead
of UTC (last M1 bar 13:00 at 10:07 UTC), i.e. it is Fusion's own UTC+3 wall clock stored as if it
were UTC. Hours here are therefore SERVER hours and are labelled as such; hour 00 is the rollover
and is the widest hour on every FX cross measured.

FOUR SOURCES, NEVER AVERAGED. The tape is the source of record; the live `symbol_info` snapshot,
the quote at the desk's OWN fill minutes, and the same statistic over the longer M5 window are
CROSS-CHECKS. Where they disagree materially the disagreement is published per symbol -- that is
the finding, and averaging it would destroy it.

    python desks/mt5/research/fusion_spread_tape.py --root C:/opt/quant --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The stamp a reader sees in `universe.json:_provenance.median_spread_pts.source`. It must be
#: distinguishable from `realized_fills` (the desk's executions), from `h1_spread_median` (the
#: poisoned statistic this replaces) and from an unstamped `download_all_symbols` snapshot.
SOURCE = "fusion_zero_m1_tape"

#: The timeframe whose bars price a fill. M1 is the finest the box stores and the only one whose
#: history begins after the broker's fixed-spread era ended.
PRIMARY_TF = "M1"
#: The longer window the primary reading is checked against for stability -- "what it ALWAYS is"
#: is a claim about time, so it is tested over more of it. Never blended into the value.
STABILITY_TF = "M5"

#: Minimum ticked, session-filtered bars before a symbol may carry a number. Mirrors
#: `cost_surface.MIN_OBS` so the registry and the surface cannot disagree about what a spread is.
MIN_OBS_FALLBACK = 200
SESSION_SHARE_FALLBACK = 0.75
MIN_SESSION_BARS_FALLBACK = 2

#: Two readings of the same quantity differing by more than this are a DISAGREEMENT rather than
#: noise. 3.0 is the gauntlet's own `stress_costs` multiple, not a number chosen here: past it a
#: cell can never pass whatever its edge, so the two readings have different consequences.
DISAGREE_RATIO = 3.0

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"


def _shared() -> tuple[int, float, int, Any]:
    """`cost_surface`'s own exclusions, imported rather than re-derived.

    Two modules computing "the spread" with different filters is the producer collapse the
    registry already paid for. Falls back to the literals above only when the import fails, and
    the fallback is reported in the artifact so a reader can tell which one ran.
    """
    try:
        from research.cost_surface import (  # type: ignore[import-not-found]
            MIN_OBS,
            MIN_SESSION_BARS,
            SESSION_SHARE,
            session_bars,
        )
        return int(MIN_OBS), float(SESSION_SHARE), int(MIN_SESSION_BARS), session_bars
    except ImportError:
        pass
    try:
        from desks.mt5.research.cost_surface import (  # type: ignore[import-not-found]
            MIN_OBS,
            MIN_SESSION_BARS,
            SESSION_SHARE,
            session_bars,
        )
        return int(MIN_OBS), float(SESSION_SHARE), int(MIN_SESSION_BARS), session_bars
    except ImportError:
        return MIN_OBS_FALLBACK, SESSION_SHARE_FALLBACK, MIN_SESSION_BARS_FALLBACK, None


def _pcts(series: Any) -> dict[str, float]:
    q = series.quantile([0.25, 0.5, 0.75, 0.9, 0.99])
    return {"p25": round(float(q.iloc[0]), 2), "p50": round(float(q.iloc[1]), 2),
            "p75": round(float(q.iloc[2]), 2), "p90": round(float(q.iloc[3]), 2),
            "p99": round(float(q.iloc[4]), 2), "max": round(float(series.max()), 2),
            "mean": round(float(series.mean()), 4)}


def read_tape(universe: Path, sym: str, timeframe: str = PRIMARY_TF) -> dict[str, Any]:
    """One symbol's spread distribution from its own bars, by `cost_surface`'s exclusions.

    TWO EXCLUSIONS AND ONE DELIBERATE NON-EXCLUSION.

      * bars with NO TICKS are dropped: a minute in which nothing quoted is absence, and its
        spread stamp prices nothing.
      * days carrying less than the symbol's own session are dropped -- the splice rule, measured
        per symbol so a 1440-bar crypto Saturday and a 390-bar equity day are both handled.
      * ZERO-SPREAD TICKED BARS ARE KEPT. On a raw account a 0-point quote is the reading, not a
        gap; dropping them is exactly what left the pre-2021 fixed-spread block as the median.
        `zero_frac` is published so a reader can see how much of the window it is.
    """
    import numpy as np
    import pandas as pd

    min_obs, share, min_sess, session_bars = _shared()
    f = universe / f"{sym}_{timeframe}.parquet"
    if not f.exists():
        return {"status": UNMEASURED, "why": f"no local {timeframe} bars on this box"}
    try:
        df = pd.read_parquet(f, columns=["spread", "tick_volume"])
    except (OSError, ValueError, KeyError):
        try:
            df = pd.read_parquet(f, columns=["spread"])
            df["tick_volume"] = 1
        except (OSError, ValueError, KeyError):
            return {"status": UNMEASURED, "why": f"no spread column in the {timeframe} parquet"}
    if df.empty:
        return {"status": UNMEASURED, "why": f"empty {timeframe} frame"}
    idx = pd.DatetimeIndex(df.index)
    ticked = np.asarray(df["tick_volume"].astype(float) > 0)
    n_noquote = int(df.shape[0] - ticked.sum())
    df, idx = df.loc[ticked], idx[ticked]
    if df.empty:
        return {"status": UNMEASURED, "why": "every bar in the window is a no-quote bar"}
    if session_bars is None:
        bpd = pd.Series(1, index=idx).groupby(idx.date).size()
        mode = int(bpd.mode().iloc[0]) if not bpd.mode().empty else 0
        sess = max(mode, int(bpd.quantile(0.90)))
    else:
        sess = int(session_bars(idx))
    if sess < min_sess:
        return {"status": UNMEASURED,
                "why": "session unestablishable (<2 bars/day at mode and p90)"}
    thr = max(min_sess, int(np.ceil(share * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    full = np.asarray(per_day >= thr)
    kept = df.loc[full, "spread"].astype(float)
    kept_idx = idx[full]
    if int(kept.size) < min_obs:
        return {"status": UNMEASURED,
                "why": (f"{int(kept.size)} ticked bars on full-session days, below the "
                        f"{min_obs} floor -- no number is emitted, so no consumer can read one")}
    hours = {str(h): {"p50": round(float(v.median()), 2),
                      "p90": round(float(v.quantile(0.90)), 2), "n": int(v.size)}
             for h, v in kept.groupby(kept_idx.hour)}
    out: dict[str, Any] = {
        "status": MEASURED, "timeframe": timeframe,
        "n": int(kept.size), "n_bars_total": int(df.shape[0] + n_noquote),
        "n_no_quote_bars": n_noquote,
        "zero_frac": round(float((kept == 0).mean()), 4),
        "session_bars": int(sess), "session_threshold": int(thr),
        "days_full": int(np.unique(kept_idx.date).size),
        "days_total": int(np.unique(idx.date).size),
        "first": str(kept_idx.min()), "last": str(kept_idx.max()),
        "hours_traded": sorted(int(h) for h in hours),
        "by_server_hour": hours,
        "clock": "server wall clock (Fusion UTC+3), stored as if UTC; hour 00 is the rollover",
    }
    out.update(_pcts(kept))
    return out


def quote_at_fill_minutes(universe: Path, sym: str, deals: list[dict[str, Any]]) -> dict[str, Any]:
    """The broker's quoted spread at the minutes THIS desk actually filled -- ground truth.

    Not the pooled median and not the median of the hour: the quote at the desk's own fills. It
    is the only reading that answers "was the charge fair on the trades we really did", and it is
    a CROSS-CHECK rather than the value, because it covers 13 of 251 symbols and is biased to the
    hours those sleeves fire.
    """
    import pandas as pd

    mine = [d for d in deals if d.get("sym") == sym and d.get("epoch")]
    if not mine:
        return {"status": UNMEASURED, "why": "this desk has never filled this symbol"}
    f = universe / f"{sym}_{PRIMARY_TF}.parquet"
    if not f.exists():
        return {"status": UNMEASURED, "why": "no M1 bars to look the fill minutes up in"}
    try:
        df = pd.read_parquet(f, columns=["spread"])
    except (OSError, ValueError, KeyError):
        return {"status": UNMEASURED, "why": "no spread column in the M1 parquet"}
    by_minute = {int(t.timestamp()): float(s)
                 for t, s in zip(pd.DatetimeIndex(df.index), df["spread"].astype(float),
                                 strict=False)}
    seen = [by_minute[m] for m in (int(float(d["epoch"]) // 60) * 60 for d in mine)
            if m in by_minute]
    if not seen:
        return {"status": UNMEASURED, "n_deals": len(mine),
                "why": ("no M1 bar in the stored window covers this symbol's fill minutes -- the "
                        "tape is shorter than the deal history")}
    out: dict[str, Any] = {"status": MEASURED, "n_deals": len(mine), "n_matched": len(seen)}
    out.update(_pcts(pd.Series(seen, dtype="float64")))
    return out


def live_snapshot(symbols: list[str]) -> dict[str, Any]:  # pragma: no cover - needs a terminal
    """`symbol_info.spread` and the book itself, right now, for every symbol.

    A SNAPSHOT IS NEVER THE VALUE and this function's existence is not a vote for it. One reading
    taken while the venue is shut writes zeros onto the majors -- the exact shape that prices an
    instrument at no cost. It is published as one row of the distribution so a reader can see
    whether the tape's central value is anywhere near the live book, and `tick_age_s` is carried
    so a stale reading identifies itself instead of passing as current.
    """
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        return {"status": UNMEASURED, "why": f"MetaTrader5 is not importable here: {exc}"}
    if not mt5.initialize():
        return {"status": UNMEASURED, "why": f"terminal did not initialise: {mt5.last_error()}"}
    now = datetime.now(tz=UTC).timestamp()
    out: dict[str, Any] = {"status": MEASURED, "at": datetime.now(tz=UTC).isoformat(
        timespec="seconds"), "symbols": {}}
    try:
        acct = mt5.account_info()
        out["account"] = {"login": getattr(acct, "login", None),
                          "currency": getattr(acct, "currency", None),
                          "company": getattr(acct, "company", None),
                          "server": getattr(acct, "server", None)}
        for sym in symbols:
            info = mt5.symbol_info(sym)
            if info is None:
                out["symbols"][sym] = {"status": UNMEASURED,
                                       "why": "symbol not in this terminal's registry"}
                continue
            tick = mt5.symbol_info_tick(sym)
            bid, ask = getattr(tick, "bid", None), getattr(tick, "ask", None)
            out["symbols"][sym] = {
                "status": MEASURED, "spread_pts": float(info.spread),
                "point": float(info.point), "digits": int(info.digits),
                "spread_float": bool(info.spread_float),
                "book_pts": (round((ask - bid) / info.point, 2)
                             if (bid is not None and ask is not None and info.point) else None),
                # NEGATIVE means the server clock is AHEAD of UTC, which is how this venue's
                # +3 offset shows up; a large POSITIVE age is a shut market.
                "tick_age_s": (round(now - float(tick.time)) if tick is not None else None)}
    finally:
        mt5.shutdown()
    return out


def deals_from_terminal() -> list[dict[str, Any]]:  # pragma: no cover - needs a terminal
    """Every deal the account has ever done: ticket, symbol, minute, volume, commission."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return []
    if not mt5.initialize():
        return []
    try:
        from datetime import timedelta
        rows = mt5.history_deals_get(datetime(2000, 1, 1, tzinfo=UTC),
                                     datetime.now(tz=UTC) + timedelta(days=2))
        return [{"sym": d.symbol, "epoch": int(d.time), "vol": float(d.volume),
                 "comm": float(d.commission), "swap": float(d.swap),
                 "entry": int(d.entry)} for d in (rows or [])]
    finally:
        mt5.shutdown()


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(max(a / b, b / a), 3)


def judge(sym: str, tape: dict[str, Any], stability: dict[str, Any],
          live: dict[str, Any], fills: dict[str, Any], old: float | None) -> dict[str, Any]:
    """One symbol's verdict: the value, its dispersion, and every source that disagrees.

    THE ONLY TWO REFUSALS, both of them the principal's rule and neither of them a cap:

      * an UNMEASURED tape -- no bars, too few bars, no session -- keeps the old value.
      * a central value of 0.0 keeps the old value. A zero prices the instrument at no cost and
        lets a non-edge certify; at this venue's integer-point resolution it is also the shape a
        sub-point book takes, so it is honestly UNMEASURED rather than honestly free.

    A material disagreement is NOT a refusal. It is published per symbol -- the tape is the
    source of record and the disagreement is the finding, so burying it behind a refusal would
    lose it as surely as averaging would.
    """
    row: dict[str, Any] = {"symbol": sym, "old": old, "source": SOURCE}
    if tape.get("status") != MEASURED:
        row.update({"status": UNMEASURED, "new": None,
                    "why": f"{tape.get('why')}; keeps its old value {old}"})
        return row
    value = float(tape["p50"])
    row["dispersion"] = {k: tape[k] for k in ("p25", "p50", "p75", "p90", "p99", "max", "mean")}
    row["window"] = {k: tape[k] for k in ("n", "first", "last", "days_full", "days_total",
                                          "zero_frac", "session_bars", "session_threshold")}
    row["hours_traded"] = tape["hours_traded"]
    row["by_server_hour"] = tape["by_server_hour"]
    live_pts = (live or {}).get("spread_pts") if (live or {}).get("status") == MEASURED else None
    fills_p50 = (fills or {}).get("p50") if (fills or {}).get("status") == MEASURED else None
    stab_p50 = (stability or {}).get("p50") if (stability or {}).get("status") == MEASURED \
        else None
    row["cross_checks"] = {
        "live_symbol_info_pts": live_pts,
        "live_tick_age_s": (live or {}).get("tick_age_s"),
        "quote_at_own_fills_p50": fills_p50,
        "n_own_fills_matched": (fills or {}).get("n_matched"),
        f"{STABILITY_TF}_long_window_p50": stab_p50,
        f"{STABILITY_TF}_window_first": (stability or {}).get("first"),
    }
    disagree = []
    r_stab = _ratio(value, stab_p50)
    if r_stab is not None and r_stab > DISAGREE_RATIO:
        disagree.append(f"{STABILITY_TF} over a longer window reads {stab_p50} against {value} "
                        f"({r_stab}x): the spread is not stable across the two windows")
    r_fill = _ratio(value, fills_p50)
    if r_fill is not None and r_fill > DISAGREE_RATIO:
        disagree.append(f"the quote at this desk's own fill minutes is {fills_p50} against a "
                        f"window median of {value} ({r_fill}x): the sleeves fire in a different "
                        "book from the one the window describes")
    if (live_pts is not None and value > 0
            and not (tape["p25"] <= live_pts <= tape["p99"])):
        disagree.append(f"the live book quotes {live_pts} pts, outside this symbol's own "
                        f"p25..p99 band of {tape['p25']}..{tape['p99']}")
    row["disagreements"] = disagree
    if value <= 0:
        row.update({"status": UNMEASURED, "new": None,
                    "why": (f"the central value is 0.0 over {tape['n']} ticked bars "
                            f"({tape['zero_frac']:.0%} of them zero). A registry spread of 0.0 "
                            "prices this instrument at no cost at all and lets a non-edge "
                            f"certify, so it keeps its old value {old}. Its tail is real and is "
                            f"published: p90 {tape['p90']}, p99 {tape['p99']}, max "
                            f"{tape['max']}")})
        return row
    row.update({"status": MEASURED, "new": value,
                "why": (f"median of {tape['n']} ticked bars on full-session days "
                        f"({tape['days_full']}/{tape['days_total']} days, "
                        f"{tape['first']}..{tape['last']}), by cost_surface's own exclusions")})
    if old is not None and old > 0:
        row["move"] = round(value / old, 4)
        row["direction"] = ("dearer" if value > old else
                            "cheaper" if value < old else "unchanged")
    elif old == 0:
        row["direction"] = "priced_from_zero"
    if row.get("direction") == "cheaper":
        row.update(corroborate_cheapening(float(old or 0.0), live, fills, stability))
    return row


def corroborate_cheapening(old: float, live: dict[str, Any], fills: dict[str, Any],
                           stability: dict[str, Any]) -> dict[str, Any]:
    """Does any source OTHER than the tape agree the old value was too wide?

    A CHEAPENING IS THE DIRECTION THAT MINTS CLAIMS and it gets a second opinion; a widening
    cannot mint one and does not need it. This is not a cap and it lowers nothing: it decides
    whether the tape may lower a charge ALONE.

    Three independent sources may corroborate, and each is a different measurement:
      * the live `symbol_info` quote, but ONLY while the tick is fresh -- a snapshot taken while
        the venue is shut is the widest number of the week and is evidence of nothing.
      * the same statistic over the longer M5 window.
      * the broker's quote at the desk's OWN fill minutes.
    If every source that CAN speak says the old value was right, the correction is refused and
    the symbol is named. If none can speak the tape stands alone and says so, because ~100,000
    ticked bars against one point-in-time snapshot is not a close call.
    """
    agree: list[str] = []
    against: list[str] = []
    if (live or {}).get("status") == MEASURED and (live or {}).get("fresh"):
        pts = live.get("spread_pts")
        (agree if pts is not None and pts <= old else against).append(
            f"live book {pts} pts (tick fresh)")
    if (stability or {}).get("status") == MEASURED:
        pts = stability.get("p50")
        (agree if pts is not None and pts <= old else against).append(
            f"{STABILITY_TF} long window {pts} pts")
    if (fills or {}).get("status") == MEASURED:
        pts = fills.get("p50")
        (agree if pts is not None and pts <= old else against).append(
            f"quote at this desk's own fills {pts} pts over {fills.get('n_matched')} deals")
    if agree:
        return {"corroboration": "CORROBORATED", "corroborated_by": agree,
                "contradicted_by": against}
    if against:
        return {"corroboration": "CONTRADICTED", "corroborated_by": [],
                "contradicted_by": against,
                "why_refused": ("every source that can speak reads the old charge as fair or "
                                "low, so the tape may not lower it alone: " + "; ".join(against))}
    return {"corroboration": "TAPE_ONLY", "corroborated_by": [], "contradicted_by": [],
            "why_tape_only": ("no fresh live quote, no longer window and no fill of this desk's "
                              "own -- the correction rests on the tape alone")}


def applicable(row: dict[str, Any]) -> tuple[float | None, str]:
    """The value this row may be WRITTEN with, or None and the reason it may not be.

    Measuring and writing are two decisions and this is the second one. A row can be a perfectly
    good measurement and still not be writable -- a measured zero, a cheapening every other
    source contradicts -- and in both cases the symbol keeps its old value and is named.
    """
    if row.get("status") != MEASURED or row.get("new") is None:
        return None, str(row.get("why") or "unmeasured")
    if row.get("corroboration") == "CONTRADICTED":
        return None, str(row.get("why_refused") or "cheapening contradicted by every other source")
    return float(row["new"]), str(row.get("why") or "")


#: A live tick further than this from the book's own baseline is a shut market, not a quote.
LIVE_FRESH_S = 900


def mark_fresh(live: dict[str, Any]) -> dict[str, Any]:
    """Stamp each live reading `fresh` or not, against a baseline MEASURED from the book itself.

    THE OFFSET IS NEVER HARDCODED. `symbol_info_tick.time` is the server's wall clock stored as a
    Unix epoch, so on this venue every live symbol reads about three hours in the future and a
    naive age is negative. The baseline is the MEDIAN age across the whole registry -- most
    symbols are open at any hour the desk runs -- so the venue's offset cancels and a genuinely
    stale symbol stands out against its own peers. A desk that re-homes its server changes
    nothing here; a hardcoded +3 would have to be found and changed.
    """
    if live.get("status") != MEASURED:
        return {"status": UNMEASURED, "why": live.get("why")}
    ages = sorted(float(r["tick_age_s"]) for r in (live.get("symbols") or {}).values()
                  if isinstance(r, dict) and r.get("tick_age_s") is not None)
    if not ages:
        return {"status": UNMEASURED, "why": "no tick carried a timestamp"}
    base = ages[len(ages) // 2]
    n_fresh = 0
    for r in (live.get("symbols") or {}).values():
        if not isinstance(r, dict) or r.get("tick_age_s") is None:
            continue
        r["fresh"] = abs(float(r["tick_age_s"]) - base) <= LIVE_FRESH_S
        r["staleness_s"] = round(float(r["tick_age_s"]) - base)
        n_fresh += int(bool(r["fresh"]))
    return {"status": MEASURED, "baseline_tick_age_s": base, "fresh_within_s": LIVE_FRESH_S,
            "n_fresh": n_fresh, "n_symbols": len(ages),
            "why": ("the baseline is the median tick age over the whole registry, so the venue's "
                    "own clock offset cancels and only a genuinely shut symbol reads stale")}


def measure(root: Path, symbols: list[str] | None = None,
            with_terminal: bool = True) -> dict[str, Any]:
    """Every symbol in the registry, priced from the tape and cross-checked against the venue."""
    desk = root / "desks" / "mt5"
    universe = desk / "data" / "universe"
    try:
        doc = json.loads((universe / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": UNMEASURED, "why": f"registry unreadable: {type(exc).__name__}"}
    rows = doc.get("symbols") if isinstance(doc, dict) and "symbols" in doc else doc
    if not isinstance(rows, dict):
        return {"status": UNMEASURED, "why": "registry is not a symbol map"}
    syms = sorted(symbols or rows)
    live = live_snapshot(syms) if with_terminal else {"status": UNMEASURED,
                                                      "why": "terminal not asked for"}
    baseline = mark_fresh(live)
    deals = deals_from_terminal() if with_terminal else []
    out_rows: dict[str, Any] = {}
    for sym in syms:
        meta = rows.get(sym) if isinstance(rows.get(sym), dict) else {}
        old_raw = (meta or {}).get("median_spread_pts")
        old = float(old_raw) if isinstance(old_raw, (int, float)) else None
        tape = read_tape(universe, sym, PRIMARY_TF)
        stability = read_tape(universe, sym, STABILITY_TF)
        fills = quote_at_fill_minutes(universe, sym, deals)
        one_live = (live.get("symbols") or {}).get(sym, {}) if live.get("status") == MEASURED \
            else {}
        out_rows[sym] = judge(sym, tape, stability, one_live, fills, old)
    measured = [r for r in out_rows.values() if r["status"] == MEASURED]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "producer": "desks/mt5/research/fusion_spread_tape.py",
        "source": SOURCE, "primary_timeframe": PRIMARY_TF,
        "stability_timeframe": STABILITY_TF,
        "account": live.get("account"), "terminal_status": live.get("status"),
        "terminal_why": live.get("why"), "live_freshness": baseline,
        "n_symbols": len(syms), "n_measured": len(measured),
        "n_unmeasured": len(syms) - len(measured),
        "n_dearer": sum(1 for r in measured if r.get("direction") == "dearer"),
        "n_cheaper": sum(1 for r in measured if r.get("direction") == "cheaper"),
        "n_unchanged": sum(1 for r in measured if r.get("direction") == "unchanged"),
        "n_priced_from_zero": sum(1 for r in measured
                                  if r.get("direction") == "priced_from_zero"),
        "n_cheaper_contradicted": sum(1 for r in measured
                                      if r.get("corroboration") == "CONTRADICTED"),
        "n_cheaper_tape_only": sum(1 for r in measured
                                   if r.get("corroboration") == "TAPE_ONLY"),
        "cheaper_contradicted": sorted(s for s, r in out_rows.items()
                                       if r.get("corroboration") == "CONTRADICTED"),
        "n_with_disagreement": sum(1 for r in out_rows.values() if r.get("disagreements")),
        "unmeasured": {s: r.get("why") for s, r in out_rows.items()
                       if r["status"] == UNMEASURED},
        "by_symbol": out_rows,
        "rule": ("median_spread_pts is the median of the symbol's own M1 spread column over "
                 "ticked bars on full-session days, by cost_surface's exclusions, with zero-spread "
                 "ticked bars KEPT (on a raw account a 0-point quote is the reading) and a zero "
                 "central value never WRITTEN (it would price the instrument at no cost). The "
                 "live snapshot, the quote at the desk's own fills and the longer M5 window are "
                 "cross-checks and are never averaged into the value."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    # `__file__` is "<stdin>" when this module is piped to an interpreter, which is how the build
    # box reaches the trading box (no shared filesystem, and the box adopts code hourly). Falling
    # back to the cwd keeps that path working with no hardcoded machine path anywhere; the caller
    # passes --root explicitly there.
    try:
        here = Path(globals()["__file__"]).resolve().parents[3]
    except (KeyError, IndexError, OSError, ValueError):
        here = Path.cwd()
    ap.add_argument("--root", type=Path, default=here)
    ap.add_argument("--symbols", default="", help="comma-separated subset (default: all)")
    ap.add_argument("--no-terminal", action="store_true",
                    help="skip the live snapshot and the deal history")
    ap.add_argument("--json", action="store_true", help="dump the whole artifact")
    ap.add_argument("--out", type=Path, default=None, help="write the artifact here")
    a = ap.parse_args(argv)
    for p in (str(a.root), str(a.root / "desks" / "mt5"),
              str(a.root / "desks" / "mt5" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    doc = measure(a.root, [s for s in a.symbols.split(",") if s] or None,
                  with_terminal=not a.no_terminal)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"fusion spread tape: {doc.get('n_symbols')} symbols  "
              f"measured={doc.get('n_measured')} unmeasured={doc.get('n_unmeasured')}  "
              f"dearer={doc.get('n_dearer')} cheaper={doc.get('n_cheaper')} "
              f"from_zero={doc.get('n_priced_from_zero')}  "
              f"disagreements={doc.get('n_with_disagreement')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
