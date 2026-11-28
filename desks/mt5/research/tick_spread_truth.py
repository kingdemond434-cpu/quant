#!/usr/bin/env python3
"""WHAT A FILL ACTUALLY CROSSES, per instrument, from the desk's own tick tape.

THE DEFECT THIS ENDS. MEASURED 2026-11-10 on the trading box against 57-61 days of recorded ticks
(`reports/box_reads/spread_column_regime_2026-11-10T1818Z.json`): the `spread` column of a bar
file is THE BAR'S MINIMUM QUOTED SPREAD. It equals the rounded tape minimum on 98.9% of matched
M30 bars and the spread at the bar's open on 6.3%. Zeros in it are real quotes (the tape minimum
was under half a point on every zero bar), and before about December 2020 it is a filled
constant. So every statistic the desk has taken of that column -- the H1 median `fetch_universe`
writes, the M1 median `fusion_spread_tape` writes -- is a statistic of the CHEAPEST instant of
each bar, never of the book an order meets. The registry scalar every gate divides by is
therefore wrong in BOTH directions against the tape:

    UNDER-CHARGED  USDNOK 136 vs ~244-260   GBPSEK 246 vs ~288   USDTHB 424 vs 430-530
                   AUDSGD / GBPJPY / GBPCAD / NZDCAD charged 0-1 vs 2-5
    OVER-CHARGED   AUDCHF 110.5 vs 2        NZDJPY 15 vs 3       XAUUSD 14.5 vs 5-7

Under-charging certifies edges that are not there. Over-charging refuses real ones and shrinks
size on the ones that pass. Neither direction is the safe one (GROWTH GOVERNANCE Rule 1 and 2),
so this module reports and writes BOTH.

THE STATISTIC, AND WHY IT IS NOT THE TAPE FEATURES' ONE.
For each recorded day the two-sided ticks are reduced to ONE reading per ticked minute -- the
median spread quoted inside that minute -- and the symbol's value is the median of those minutes
over full-session days. Three deliberate choices:

  * A MINUTE, NOT A TICK, IS THE UNIT. Ticks cluster where the book is moving, so a tick-weighted
    median describes the busiest seconds of the day. An order placed at a clock time meets the
    book of a typical minute; each ticked minute counts once.
  * ZEROS ARE KEPT. `microstructure.quoted_spread_pts` drops zero-spread ticks because it
    measures the spread WHEN there is one; that is the right conditional statistic for a fill
    model and the wrong one for "what does this instrument cost". On a Zero account a 0-point
    quote is the reading.
  * A ZERO CENTRAL VALUE IS NEVER WRITTEN. Same rule, same reason as `fusion_spread_tape`: a
    registry spread of 0.0 prices the instrument at no cost and lets a non-edge certify, so the
    symbol keeps its old value and is NAMED. Absence never resolves to a clean verdict.

THE WINDOW IS THE INSTRUMENT'S OWN: days carrying at least `SESSION_SHARE` of the symbol's own
ticked minutes per day, by `cost_surface.session_bars`, imported and not re-derived. A symbol
with fewer than `MIN_FULL_DAYS` such days is UNMEASURED and keeps its old value.

IT READS THE SILVER TAPE (`data/tape/ticks/<SYM>/<DAY>.parquet`, written by
`recorders/tape_features.py`) AND CACHES ONE SMALL FRAME PER SYMBOL-DAY under
`data/tape/minute_spread/`, so the hourly pass re-reads only days whose ticks changed. The cache
is a rebuildable aggregate: deleting it costs one slow pass and nothing else.

IT VETOES NOTHING AND SIZES NOTHING. It measures, and it names every symbol whose charge would
move and in which direction. The registry is written only through
`scripts/repair_universe_spreads.py --source ticks --apply`, stamped `tick_tape_median`.

IT IS A LIBRARY ON AN EXISTING CLOCK, NOT A NEW EXECUTABLE. `repair_universe_spreads.py` calls
`measure` on every pass, and its default pass is the hourly `spread_provenance` leg, which
writes `reports/TICK_SPREAD_TRUTH.json`. To read it by hand:

    python desks/mt5/scripts/repair_universe_spreads.py --source ticks      # report only
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The stamp a reader sees in `universe.json:_provenance.median_spread_pts.source`. Ranked in
#: `universe_registry.MEDIAN_SPREAD_PRODUCERS` above every bar-column statistic, because those
#: all read the bar's minimum, and below `realized_fills`, because an execution beats a quote.
SOURCE = "tick_tape_median"

#: Full-session days a symbol must hold before it may carry a number. Twenty trading days is one
#: calendar month of the instrument's own book: enough that a single event week is a minority of
#: the window. A floor, not a tuning knob -- raising it only makes more symbols UNMEASURED.
MIN_FULL_DAYS = 20
#: The most recent day files read per symbol. Bounds the pass and keeps the value a description
#: of the CURRENT book rather than of a quote regime the broker has since left.
WINDOW_DAYS = 90

#: Mirrors `cost_surface` so the registry and the surface cannot disagree about what a session
#: is. Used only when that module cannot be imported, and the artifact says which one ran.
SESSION_SHARE_FALLBACK = 0.75
MIN_SESSION_BARS_FALLBACK = 2

#: Two readings of the same quantity differing by more than this have different CONSEQUENCES:
#: 3.0 is the gauntlet's own `stress_costs` multiple, past which a cell cannot pass whatever its
#: edge. Mirrored from `fusion_spread_tape.DISAGREE_RATIO`, never chosen here.
DISAGREE_RATIO = 3.0

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

_COLS = ("minute", "spread_pts", "n_ticks")


def _desk(root: Path) -> Path:
    return root / "desks" / "mt5"


def _session() -> tuple[float, int, Any, str]:
    """`cost_surface`'s own session rule, imported rather than re-derived."""
    for mod in ("research.cost_surface", "desks.mt5.research.cost_surface", "cost_surface"):
        try:
            m = __import__(mod, fromlist=["SESSION_SHARE"])
            return (float(m.SESSION_SHARE), int(m.MIN_SESSION_BARS), m.session_bars,
                    "cost_surface")
        except (ImportError, AttributeError):
            continue
    return SESSION_SHARE_FALLBACK, MIN_SESSION_BARS_FALLBACK, None, "fallback literals"


def minute_frame(ticks: Any) -> Any:
    """One reading per ticked minute: the MEDIAN spread quoted inside it, zeros kept.

    `ticks` is a silver frame (`ts`, `bid`, `ask`, and `spread_pts` when the producer wrote it).
    Rows without a two-sided quote are dropped, exactly as `microstructure.quote_frame` drops
    them; a crossed quote (ask < bid) is dropped too, because it is a feed artefact and not a
    spread anyone could cross.
    """
    import numpy as np
    import pandas as pd

    if ticks is None or len(ticks) == 0 or "spread_pts" not in ticks.columns:
        return pd.DataFrame(columns=list(_COLS))
    sp = pd.to_numeric(ticks["spread_pts"], errors="coerce")
    ts = pd.to_datetime(ticks["ts"], utc=True, errors="coerce")
    ok = np.asarray(sp.notna() & ts.notna() & (sp >= 0))
    if "bid" in ticks.columns and "ask" in ticks.columns:
        ok = ok & np.asarray((ticks["bid"] > 0) & (ticks["ask"] > 0))
    if not ok.any():
        return pd.DataFrame(columns=list(_COLS))
    s = pd.Series(np.asarray(sp[ok], dtype=np.float64),
                  index=pd.DatetimeIndex(ts[ok]).floor("min"))
    g = s.groupby(level=0)
    out = pd.DataFrame({"spread_pts": g.median(), "n_ticks": g.size()})
    out.index.name = "minute"
    return out.reset_index()


def _atomic_parquet(df: Any, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + f".{os.getpid()}.tmp")
    df.to_parquet(tmp, index=False)
    try:
        os.replace(tmp, dst)
    except OSError:
        # A destination another process holds open on Windows: the cache is a rebuildable
        # aggregate, so the frame just computed is still returned and the next pass retries.
        with contextlib.suppress(OSError):
            tmp.unlink()


def day_minutes(silver: Path, cache: Path) -> Any:
    """The minute frame for one symbol-day, from the cache when the ticks have not changed."""
    import pandas as pd

    try:
        if cache.exists() and cache.stat().st_mtime >= silver.stat().st_mtime:
            got = pd.read_parquet(cache)
            if set(_COLS) <= set(got.columns):
                return got
    except (OSError, ValueError, KeyError):
        pass
    try:
        ticks = pd.read_parquet(silver, columns=["ts", "bid", "ask", "spread_pts"])
    except (OSError, ValueError, KeyError):
        return None
    out = minute_frame(ticks)
    _atomic_parquet(out, cache)
    return out


def _pcts(v: Any) -> dict[str, float]:
    q = v.quantile([0.25, 0.5, 0.75, 0.9, 0.99])
    return {"p25": round(float(q.iloc[0]), 2), "p50": round(float(q.iloc[1]), 2),
            "p75": round(float(q.iloc[2]), 2), "p90": round(float(q.iloc[3]), 2),
            "p99": round(float(q.iloc[4]), 2), "max": round(float(v.max()), 2),
            "mean": round(float(v.mean()), 4)}


def profile(minutes: Any) -> dict[str, Any]:
    """One symbol's distribution over its pooled minute frame, session-filtered."""
    import numpy as np
    import pandas as pd

    share, min_sess, session_bars, basis = _session()
    if minutes is None or len(minutes) == 0:
        return {"status": UNMEASURED, "why": "no ticked minute on the tape"}
    idx = pd.DatetimeIndex(pd.to_datetime(minutes["minute"], utc=True))
    v = pd.Series(np.asarray(minutes["spread_pts"], dtype=np.float64), index=idx)
    if session_bars is None:
        bpd = pd.Series(1, index=idx).groupby(idx.date).size()
        mode = int(bpd.mode().iloc[0]) if not bpd.mode().empty else 0
        sess = max(mode, int(bpd.quantile(0.90)))
    else:
        sess = int(session_bars(idx))
    if sess < min_sess:
        return {"status": UNMEASURED,
                "why": "session unestablishable (<2 ticked minutes/day at mode and p90)"}
    thr = max(min_sess, int(np.ceil(share * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    full = np.asarray(per_day >= thr)
    kept = v[full]
    days_full = int(np.unique(kept.index.date).size)
    days_total = int(np.unique(idx.date).size)
    if days_full < MIN_FULL_DAYS:
        return {"status": UNMEASURED, "days_full": days_full, "days_total": days_total,
                "why": (f"{days_full} full-session tape days, below the {MIN_FULL_DAYS} floor "
                        "-- no number is emitted, so no consumer can read one")}
    hours = {str(h): {"p50": round(float(x.median()), 2),
                      "p90": round(float(x.quantile(0.90)), 2), "n": int(x.size)}
             for h, x in kept.groupby(kept.index.hour)}
    out: dict[str, Any] = {
        "status": MEASURED, "n": int(kept.size),
        "zero_frac": round(float((kept == 0).mean()), 4),
        "session_minutes": int(sess), "session_threshold": int(thr),
        "session_basis": basis,
        "days_full": days_full, "days_total": days_total,
        "first": str(kept.index.min()), "last": str(kept.index.max()),
        "by_tape_hour": hours,
        "clock": "the tape's own clock (the hour convention recorders/tape_features uses)",
    }
    out.update(_pcts(kept))
    return out


def judge(sym: str, prof: dict[str, Any], old: float | None,
          held_source: str | None) -> dict[str, Any]:
    """One symbol's verdict: the value, its dispersion, and which way the charge would move."""
    row: dict[str, Any] = {"symbol": sym, "old": old, "held_source": held_source,
                           "source": SOURCE}
    if prof.get("status") != MEASURED:
        row.update({"status": UNMEASURED, "new": None,
                    "why": f"{prof.get('why')}; keeps its old value {old}"})
        return row
    value = float(prof["p50"])
    row["dispersion"] = {k: prof[k] for k in ("p25", "p50", "p75", "p90", "p99", "max", "mean")}
    row["window"] = {k: prof[k] for k in ("n", "first", "last", "days_full", "days_total",
                                          "zero_frac", "session_minutes", "session_threshold")}
    row["by_tape_hour"] = prof["by_tape_hour"]
    if value <= 0:
        row.update({"status": UNMEASURED, "new": None, "tape_p50": value,
                    "why": (f"the central value is 0.0 over {prof['n']} ticked minutes "
                            f"({prof['zero_frac']:.0%} of them zero). A registry spread of 0.0 "
                            "prices this instrument at no cost at all and lets a non-edge "
                            f"certify, so it keeps its old value {old}. Its tail is real and is "
                            f"published: p90 {prof['p90']}, p99 {prof['p99']}")})
        return row
    row.update({"status": MEASURED, "new": value,
                "why": (f"median of {prof['n']} ticked minutes on full-session tape days "
                        f"({prof['days_full']}/{prof['days_total']} days, "
                        f"{prof['first']}..{prof['last']}), zeros kept")})
    if old is None:
        row["direction"] = "unpriced"
    elif old <= 0:
        row["direction"] = "priced_from_zero"
    else:
        row["move"] = round(value / old, 4)
        row["direction"] = ("under_charged" if value > old else
                            "over_charged" if value < old else "unchanged")
        row["beyond_stress"] = bool(max(value / old, old / value) > DISAGREE_RATIO)
    return row


def applicable(row: dict[str, Any]) -> tuple[float | None, str]:
    """The value this row may be WRITTEN with, or None and the reason it may not be."""
    if row.get("status") != MEASURED or row.get("new") is None:
        return None, str(row.get("why") or "unmeasured")
    return float(row["new"]), str(row.get("why") or "")


def _book(desk: Path) -> dict[str, dict[str, int]]:
    """How many sleeves of each status stand on each symbol, so a re-pricing names what it
    touches. An unreadable roster yields an empty map, and the report says the join is absent."""
    out: dict[str, dict[str, int]] = {}
    for name in ("sleeve_registry.json", "sleeves.json"):
        try:
            doc = json.loads((desk / "data" / name).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc.get("sleeves") if isinstance(doc, dict) else doc
        if isinstance(rows, dict):
            rows = list(rows.values())
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            sym = (r.get("identity") or {}).get("symbol") or r.get("symbol")
            status = str(r.get("status") or "UNKNOWN")
            if sym:
                key = f"{name.removesuffix('.json')}:{status}"
                out.setdefault(str(sym), {})
                out[str(sym)][key] = out[str(sym)].get(key, 0) + 1
    return out


def measure(root: Path, symbols: list[str] | None = None,
            budget_s: float | None = None) -> dict[str, Any]:
    """Every symbol the tape holds, priced from its ticks and compared with what is charged."""
    import pandas as pd

    desk = _desk(root)
    silver_root = desk / "data" / "tape" / "ticks"
    cache_root = desk / "data" / "tape" / "minute_spread"
    try:
        doc = json.loads((desk / "data" / "universe" / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": UNMEASURED, "why": f"registry unreadable: {type(exc).__name__}"}
    rows = doc.get("symbols") if isinstance(doc, dict) and "symbols" in doc else doc
    if not isinstance(rows, dict):
        return {"status": UNMEASURED, "why": "registry is not a symbol map"}
    if not silver_root.is_dir():
        return {"status": UNMEASURED,
                "why": f"no silver tape at {silver_root.as_posix()} on this machine"}
    on_tape = sorted(p.name for p in silver_root.iterdir() if p.is_dir())
    syms = [s for s in on_tape if (symbols is None or s in symbols)]
    t0 = time.monotonic()
    out_rows: dict[str, Any] = {}
    deferred: list[str] = []
    for sym in syms:
        if budget_s is not None and time.monotonic() - t0 > budget_s:
            deferred.append(sym)
            continue
        files = sorted((silver_root / sym).glob("*.parquet"))[-WINDOW_DAYS:]
        frames = []
        for f in files:
            got = day_minutes(f, cache_root / sym / f.name)
            if got is not None and len(got):
                frames.append(got)
        minutes = pd.concat(frames, ignore_index=True) if frames else None
        meta = rows.get(sym) if isinstance(rows.get(sym), dict) else {}
        old_raw = (meta or {}).get("median_spread_pts")
        old = float(old_raw) if isinstance(old_raw, (int, float)) else None
        held = (((meta or {}).get("_provenance") or {}).get("median_spread_pts") or {}).get(
            "source")
        row = judge(sym, profile(minutes), old, held)
        row["in_registry"] = sym in rows
        out_rows[sym] = row
    measured = {s: r for s, r in out_rows.items() if r["status"] == MEASURED}
    book = _book(desk)

    def _side(direction: str) -> list[dict[str, Any]]:
        side = [{"symbol": s, "charged": r["old"], "tape": r["new"], "move": r.get("move"),
                 "held_source": r.get("held_source"), "beyond_stress": r.get("beyond_stress"),
                 "p90": r["dispersion"]["p90"], "days": r["window"]["days_full"],
                 "sleeves": book.get(s, {})}
                for s, r in measured.items() if r.get("direction") == direction]
        def _ratio(e: dict[str, Any]) -> float:
            lo = min(e["tape"] or 0.0, e["charged"] or 0.0)
            hi = max(e["tape"] or 0.0, e["charged"] or 0.0)
            return hi / lo if lo > 0 else float("inf")

        return sorted(side, key=lambda e: (-_ratio(e), e["symbol"]))

    under = _side("under_charged") + _side("priced_from_zero")
    over = _side("over_charged")

    def _fills(below: bool) -> list[dict[str, Any]]:
        """`realized_fills` rows the tape disagrees with past the stress multiple, one side.

        The repair overrules a fills value only when it sits ABOVE the probe by more than 3x; a
        fills value far BELOW the tape is left standing. That asymmetry is not changed here, so
        every such symbol is named with what is known about the fills behind it. The registry
        stamp records when the value was taken and NOT how many fills it was taken from, so the
        count is published as unmeasured rather than implied.
        """
        rows_out = []
        for s, r in sorted(measured.items()):
            if r.get("held_source") != "realized_fills" or not r.get("old"):
                continue
            ratio = (r["new"] / r["old"]) if below else (r["old"] / r["new"])
            if ratio <= DISAGREE_RATIO:
                continue
            stamp = (((rows.get(s) or {}).get("_provenance") or {}).get("median_spread_pts")
                     or {})
            n_fills = stamp.get("n_fills", stamp.get("n"))
            rows_out.append({
                "symbol": s, "fills_value": r["old"], "tape": r["new"],
                "ratio": round(ratio, 2), "stamped_at": stamp.get("at"),
                "n_fills": n_fills if isinstance(n_fills, int) else None,
                "n_fills_why": (None if isinstance(n_fills, int) else
                                "UNMEASURED: the registry stamp records no fill count"),
                "sleeves": book.get(s, {})})
        return rows_out

    fills_below, fills_above = _fills(True), _fills(False)
    # A fills charge on a symbol whose tape centre is 0 cannot be compared by ratio and cannot
    # be replaced (a zero is never written). It is still a disagreement, and is named as one.
    fills_zero_tape = [
        {"symbol": s, "fills_value": r.get("old"), "tape_p50": 0.0, "sleeves": book.get(s, {})}
        for s, r in sorted(out_rows.items())
        if r.get("held_source") == "realized_fills" and r.get("tape_p50") == 0
        and (r.get("old") or 0) > 0]
    return {
        "status": MEASURED,
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "producer": "desks/mt5/research/tick_spread_truth.py", "source": SOURCE,
        "window_days": WINDOW_DAYS, "min_full_days": MIN_FULL_DAYS,
        "n_symbols_on_tape": len(on_tape), "n_judged": len(out_rows),
        "n_measured": len(measured), "n_unmeasured": len(out_rows) - len(measured),
        "n_deferred_over_budget": len(deferred), "deferred_over_budget": deferred,
        "n_not_on_tape": sum(1 for s in rows if s not in on_tape),
        # THE TWO-SIDED IMPACT. Under-charging mints certificates on cost that is not being
        # paid for; over-charging refuses real cells and shrinks the ones that pass. Both are
        # named with the sleeves standing on them, because the count alone hides which is live.
        "impact": {
            "n_under_charged": len(under), "n_over_charged": len(over),
            "n_unchanged": sum(1 for r in measured.values()
                               if r.get("direction") == "unchanged"),
            "n_beyond_stress": sum(1 for r in measured.values() if r.get("beyond_stress")),
            "under_charged": under, "over_charged": over,
            # THE ONE-SIDED RULE, MADE VISIBLE. `fills_above_tape` is what the repair already
            # overrules; `fills_below_tape` is what it leaves under-charged on the strength of
            # an execution estimate nobody can count from the registry.
            "n_fills_below_tape": len(fills_below), "fills_below_tape": fills_below,
            "n_fills_above_tape": len(fills_above), "fills_above_tape": fills_above,
            "n_fills_against_zero_tape": len(fills_zero_tape),
            "fills_against_zero_tape": fills_zero_tape,
            "sleeve_join": ("data/sleeve_registry.json and data/sleeves.json, by symbol and "
                            "status" if book else "ABSENT: neither roster was readable"),
        },
        "measured_zero_keeps_old": sorted(s for s, r in out_rows.items()
                                          if r["status"] == UNMEASURED
                                          and r.get("tape_p50") == 0),
        "unmeasured": {s: r.get("why") for s, r in out_rows.items()
                       if r["status"] == UNMEASURED},
        "by_symbol": out_rows,
        "rule": ("median_spread_pts from this source is the median, over full-session tape "
                 "days, of the per-minute median two-sided quoted spread, zeros kept and a zero "
                 "central value never written. A bar file's spread column is the bar's MINIMUM "
                 "and is not used. Direction is reported both ways and nothing is refused for "
                 "being cheaper: an over-charge is a refusal of real edge."),
    }


def write_report(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)
