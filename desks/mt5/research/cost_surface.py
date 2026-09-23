#!/usr/bin/env python3
"""COST SURFACE (L1.5 / L1.28a) -- spread is a symbol x HOUR state, not one scalar per symbol.

WHAT WAS MISSING. `universe.json` carries exactly ONE cost number per symbol,
`median_spread_pts`, and it is the number every gate, certificate, stress scenario and forward
clock divides by. It is created by collapsing the per-bar `spread` column at ingest
(`fetch_universe.py:103`, `expand_universe.py:136`: `float(df["spread"].median())`), so the hour
structure is destroyed BEFORE any consumer exists and no consumer can miss it. `Costs.from_symbol`
has no hour parameter; `engine.run_backtest` computes `per_oz_cost` ONCE per cell (engine.py:248)
and charges it identically at every fill (engine.py:422) although it knows each fill bar's
timestamp. ~25 hunt/screen modules read the same scalar, so every cross-check agrees.

The desk DID already measure per-hour spread -- `moat/moat_miner.mine_symbol` builds exactly this
profile from the tick tape. It emits SEARCH POINTERS (hypothesis cards ranked by
`dear_over_cheap`) and feeds no cost model, runs on a 40-symbol rotation, and needs
`bronze/mt5_ticks`, which exists only on the trading box. That is the producer/consumer collapse
this desk keeps paying for: the distinction was computed and the consumer flattened it.

WHAT IT COSTS, measured 2026-08-29 on the desk's own artifacts with the engine's own backtest.
`family_overnight_gap_decay` signals on the first bar of the day and `wait_bars=1` puts the FILL
on the next bar -- hour 01 broker time, in a book carrying ~3% of the day's peak tick volume.

    symbol   pooled scalar   spread on its OWN fill bars   error
    USDZAR       329 pts              2028 pts            6.16x   (p90 5544 pts = 16.9x)
    EURZAR       310 pts              1918 pts            6.19x   (p90 6108 pts = 19.7x)

Both hold ten-gate certificates in `UNIVERSAL_SURVIVORS.canon.json` and both are on LIVE forward
clocks (`sleeve_registry.json`, forward_start 2026-08-27). Re-priced at their own fill-hour
spread, with the mult held EQUAL on both arms so only the spread number moves:

    mult=1.0   USDZAR +0.2951R -> +0.0802R      EURZAR +0.3316R -> +0.1293R
    mult=2.0   USDZAR +0.2535R -> -0.1764R      EURZAR +0.2926R -> -0.1120R   <-- NEGATIVE

mult=2.0 is the desk's own declared honest baseline (`Costs.from_symbol`: "a round trip crosses
the spread on the way in and again on the way out"). At that baseline both live sleeves are
LOSING sleeves, and the two-stage law is currently deciding their fate on a number 6x wrong.

THE DAMAGE IS NOT UNIFORM, which is why sampling never caught it: EURUSD is EXACTLY 12 pts at all
24 hours and XAUUSD EXACTLY 16 -- administered spreads, flat by construction -- so any spot-check
on the majors returns clean. The error concentrates in the crosses and exotics.

THE OTHER DIRECTION MATTERS MORE. A cell whose fill hour is CHEAPER than the pooled scalar is
being OVERCHARGED, and an overcharged cell dies in the gauntlet without ever raising an alert.
That is the false-null direction, the only one this desk has no instrument for.

TWO EXCLUSIONS, BOTH VERIFIED NECESSARY (not judgement calls):

1. PARTIAL DAYS are the D1/H1 splice recorded in the vault -- days carrying less than 75% of
   THIS SYMBOL'S OWN session length (`session_bars`), never a fixed bar count; see SESSION_SHARE
   for the 74-symbol defect a fixed count caused on this module's first run. They are separable
   with certainty, not by assumption: on USDZAR the h00 bar of a partial day carries median
   tick_volume 66,507 and `spread == 0` in 99.9% of cases, while the h00 bar of a full day
   carries 127 ticks and a 3,606-pt spread. A spliced DAILY bar aggregates a whole day of ticks;
   a genuine dead-book hour cannot. 524x apart -- two populations, not one noisy one. The ratio
   is PUBLISHED per symbol as `splice_tickvol_ratio` so the exclusion is auditable rather than
   asserted (measured: USDZAR 18.4x, EURZAR 14.8x; 3M 0.7x, i.e. 3M's dropped days are ordinary
   half-sessions and only 0.7% of its days).

2. `spread == 0` BARS are absence, not a free trade. They are dropped from the percentiles and
   their share is PUBLISHED as `zero_frac`, because a symbol whose spread column is mostly zero
   has no cost observable at all and must not be able to report a confident cheap number.

`n_nonzero` below `MIN_OBS` yields `UNMEASURED` for that cell and never a value. Absence never
resolves to a clean verdict (L1.28a / WS-005).

WHAT IS NOT CLOSED HERE, stated plainly. The `spread` column is the broker's own recorded spread
for the bar; whether it is EXECUTABLE at hour 01 needs `symbol_info_tick` from the trading box,
which this box cannot reach. The tape evidence says the quotes are live rather than frozen -- the
h01 bar's own high-low range is a median 2.2x its spread on USDZAR, so price moves through the
wide book -- but a live-tick confirmation is owed and is recorded as such.

Run:  .venv/bin/python desks/mt5/research/cost_surface.py [--out PATH]
Fence: scripts/check_cost_surface.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parent.parent
_UNIVERSE = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "cost_surface.json"

#: Minimum non-zero spread observations in a symbol x hour cell before it may carry a number.
#: Below this the cell is UNMEASURED and consumers must refuse it, not round it to the pooled
#: scalar -- rounding to the pooled scalar is exactly the defect this module exists to end.
MIN_OBS = 200

#: A day carrying less than this SHARE of the symbol's own normal session is the D1/H1 splice.
#:
#: THIS IS DELIBERATELY NOT A BAR COUNT, and the first run of this module is why. The obvious
#: version -- "a real day has >= 20 H1 bars" -- is a 24-hour-FX threshold applied as a universal
#: boundary, and it silently excluded ALL 74 US share CFDs, which trade a 6.5-hour cash session
#: and can never carry 20 bars. Their spread columns are 96%+ non-zero and perfectly usable; the
#: artifact reported them as "no usable spread column" and read as successfully built. That is
#: the anti-hardcode law (LAWS section 1) and WS-005 in one defect: a literal calibrated on one
#: asset class capping exploration, with the resulting absence rendered as a clean verdict.
#:
#: The session length is measured PER SYMBOL from its own tape instead (`session_bars`), so a
#: 24-bar FX day and a 7-bar equity day are both handled with no asset-class list anywhere.
SESSION_SHARE = 0.75

#: Never trust a session estimate below this many bars -- one bar cannot evidence a session.
MIN_SESSION_BARS = 2

#: Cells whose |log ratio| to the pooled scalar exceeds this are reported as material. 2.0x in
#: EITHER direction: undercharging manufactures survivors, overcharging kills real edges silently.
MATERIAL_RATIO = 2.0

SCHEMA = "cost-surface-1"


def session_bars(idx: pd.DatetimeIndex) -> int:
    """How many H1 bars this symbol's own NORMAL day carries.

    `max(mode, p90)` rather than the median, because on the spliced series the splice is the
    MAJORITY: USDZAR's median bars/day is 1 (58% of its days are single daily bars), so a median
    would declare a one-bar day normal and exclude nothing. The mode fails the same way on
    Accenture (mode 1 over 6,305 days). Either statistic alone is defeated by a different symbol;
    the max of the two is defeated by neither, and both describe the FULL day rather than the
    contaminated middle of the distribution.
    """
    bpd = pd.Series(1, index=idx).groupby(idx.date).size()
    if bpd.empty:
        return 0
    mode = int(bpd.mode().iloc[0]) if not bpd.mode().empty else 0
    return max(mode, int(bpd.quantile(0.90)))


def profile_symbol(df: pd.DataFrame) -> dict | None:
    """Per-hour spread percentiles for one symbol, splice-excluded and zero-excluded.

    Returns None when the frame carries no usable `spread` column at all -- distinct from a
    frame that yields UNMEASURED hours, which is a real (and reportable) measurement.
    """
    if "spread" not in df.columns or df.empty:
        return None
    idx = pd.DatetimeIndex(df.index)
    # Exclusion 1: keep only days carrying a full session BY THIS SYMBOL'S OWN STANDARD.
    sess = session_bars(idx)
    if sess < MIN_SESSION_BARS:
        return None
    thr = max(MIN_SESSION_BARS, int(np.ceil(SESSION_SHARE * sess)))
    per_day = pd.Series(1, index=idx).groupby(idx.date).transform("size")
    full = np.asarray(per_day >= thr)
    d = df.loc[full]
    if d.empty:
        return None
    hours: dict[str, dict] = {}
    hh = pd.DatetimeIndex(d.index).hour
    for h in range(24):
        cell = d.loc[hh == h, "spread"]
        n_bars = int(cell.size)
        if n_bars == 0:
            continue
        nz = cell[cell > 0].astype(float)
        n_nz = int(nz.size)
        row: dict[str, object] = {
            "n_bars": n_bars,
            "n_nonzero": n_nz,
            "zero_frac": round(float(1.0 - n_nz / n_bars), 4),
        }
        if n_nz < MIN_OBS:
            # Exclusion 2 + L1.28a: too few priced bars to state a cost. No number is emitted,
            # so no consumer can accidentally read one.
            row["status"] = "UNMEASURED"
        else:
            row["status"] = "MEASURED"
            row["p50"] = round(float(nz.median()), 2)
            row["p75"] = round(float(nz.quantile(0.75)), 2)
            row["p90"] = round(float(nz.quantile(0.90)), 2)
        hours[str(h)] = row
    if not hours:
        return None
    measured = {h: r for h, r in hours.items() if r["status"] == "MEASURED"}
    out: dict[str, object] = {
        "session_bars": int(sess),
        "session_threshold": int(thr),
        "bars_used": len(d),
        "bars_total": len(df),
        "days_full": int(np.unique(pd.DatetimeIndex(d.index).date).size),
        "days_total": int(np.unique(idx.date).size),
        "first": str(idx.min()),
        "last": str(idx.max()),
        "hours": hours,
        "n_hours_measured": len(measured),
    }
    # PUBLISH THE EVIDENCE FOR THE EXCLUSION, never just the exclusion (L2.4). A spliced DAILY
    # bar aggregates the whole day's ticks, so if the dropped days really are the splice their
    # tick volume dwarfs the kept days' (measured: USDZAR 18x, Accenture 4120x). A ratio near 1
    # means the dropped days were ordinary short sessions -- holidays and early closes -- and
    # the exclusion is costing real data rather than removing an artifact. That distinction is
    # not assertable from the bar count alone, and this is the number that settles it.
    if "tick_volume" in df.columns and len(d) < len(df):
        kept_tv = float(df.loc[full, "tick_volume"].median())
        drop_tv = float(df.loc[~full, "tick_volume"].median())
        out["excluded_days"] = int(np.unique(idx[~full].date).size)
        out["splice_tickvol_ratio"] = (round(drop_tv / kept_tv, 1) if kept_tv > 0 else None)
    if measured:
        p50s = {int(h): float(r["p50"]) for h, r in measured.items()}  # type: ignore[arg-type]
        cheap = min(p50s, key=lambda k: p50s[k])
        dear = max(p50s, key=lambda k: p50s[k])
        out["cheapest_hour"] = cheap
        out["dearest_hour"] = dear
        out["dear_over_cheap"] = round(p50s[dear] / p50s[cheap], 2) if p50s[cheap] else None
        # A flat 24h profile is an ADMINISTERED spread (the broker marks it up to a constant)
        # rather than a passed-through market one. Nothing else on this desk records which
        # symbols are which, and it decides whether an hour-conditioned cost is even meaningful.
        out["administered"] = bool(len(set(p50s.values())) == 1)
        # The desk's cost-stress multiple is a GUESSED 3x. This is the measured one.
        p90s = {int(h): float(r["p90"]) for h, r in measured.items()}  # type: ignore[arg-type]
        ratios = [p90s[h] / p50s[h] for h in p50s if p50s[h] > 0]
        out["stress_p90_over_p50"] = round(float(np.median(ratios)), 2) if ratios else None
    return out


def build(universe_dir: Path | None = None) -> dict:
    """Build the whole surface from the H1 parquets the engine already loads."""
    u = universe_dir or _UNIVERSE
    reg_path = u / "universe.json"
    registry = json.loads(reg_path.read_text("utf-8")) if reg_path.exists() else {}
    surface: dict[str, dict] = {}
    skipped: list[str] = []
    for f in sorted(u.glob("*_H1.parquet")):
        sym = f.name[: -len("_H1.parquet")]
        try:
            df = pd.read_parquet(f, columns=["spread", "tick_volume"])
        except (OSError, ValueError, KeyError) as exc:      # unreadable / column absent
            skipped.append(f"{sym}: unreadable ({type(exc).__name__})")
            continue
        prof = profile_symbol(df)
        if prof is None:
            # SAY WHICH REFUSAL THIS IS. The first version reported every skip as "no usable
            # spread column", which was false for the 74 equity CFDs it was actually dropping
            # for a session-length reason -- and a wrong reason is worse than no reason,
            # because it closes the investigation.
            if "spread" not in df.columns or df.empty:
                why = "no spread column" if not df.empty else "empty frame"
            elif session_bars(pd.DatetimeIndex(df.index)) < MIN_SESSION_BARS:
                why = "session unestablishable (<2 bars/day at mode and p90)"
            else:
                why = "no day meets its own session threshold"
            skipped.append(f"{sym}: {why}")
            continue
        meta = registry.get(sym) or {}
        pooled = meta.get("median_spread_pts")
        prof["pooled_median_spread_pts"] = float(pooled) if pooled is not None else None
        prof["tick_size"] = float(meta.get("tick_size", 0.0) or 0.0)
        prof["contract_size"] = float(meta.get("contract_size", 0.0) or 0.0)
        surface[sym] = prof
    return {
        "schema": SCHEMA,
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "min_obs": MIN_OBS,
        "session_share": SESSION_SHARE,
        "source": str(u.relative_to(_DESK.parent.parent)) if u == _UNIVERSE else str(u),
        "n_symbols": len(surface),
        "n_skipped": len(skipped),
        "skipped": skipped[:50],
        "symbols": surface,
    }


def spread_pts(surface: dict, symbol: str, hour: int | None) -> float | None:
    """The measured spread in POINTS for one symbol at one hour, or None.

    None means "this desk does not know", and every caller must treat it as a refusal rather
    than substituting the pooled scalar (L1.28a). `hour=None` returns None deliberately: a
    caller that has not said WHEN it fills has not asked this question.
    """
    if hour is None:
        return None
    sym = (surface.get("symbols") or {}).get(symbol)
    if not sym:
        return None
    cell = (sym.get("hours") or {}).get(str(int(hour)))
    if not cell or cell.get("status") != "MEASURED":
        return None
    v = cell.get("p50")
    return float(v) if v is not None else None


# ===================================================================================
# THE EXECUTION INTELLIGENCE COMMAND (Tier-1 W8 / C12): Cost(asset, time, size, state,
# order) and NetAlpha = RawAlpha - ExpectedExecutionCost.
#
# WHAT THE SURFACE ABOVE IS AND IS NOT. Everything above this line is ONE dimension pair --
# symbol x hour, measured off the bars' own spread column -- and it is the dense half: every
# symbol has 24 hours of bars. The item W8 names five dimensions, and the other three (size,
# market state, order type) can only be measured from the desk's OWN recorded execution, which
# is thin and stays thin until the book trades more. That is the honest shape of the problem,
# so it is the shape of the artifact: a cell with evidence carries a MEASURED number with its
# n, a thin cell is SHRUNK toward its parent margin with n_eff stated, and a cell the desk has
# never traded is UNMEASURED and falls back to the MODELLED spread -- never to zero, which is
# the number that manufactures survivors.
#
# IT VETOES NOTHING. NetAlpha is published for the gauntlet's own cost model and the allocator
# to read. No candidate is blocked, no size is shrunk and no promotion is gated here; the
# sign-flip list is evidence, and the desk never reduces its aggressiveness by fiat.
# ===================================================================================

#: The recorded execution evidence. Absent on a research box, present on the trading box.
_LIVE_LEDGER = _DESK / "data" / "live_ledger.jsonl"
_FILL_CORPUS = _DESK / "data" / "fill_corpus.jsonl"
_SURVIVORS = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
_POSTERIOR_ALPHA = _DESK / "reports" / "POSTERIOR_ALPHA.json"
_EXEC_OUT = _DESK / "reports" / "COST_SURFACE.json"

#: The five dimensions, in the order the item names them. The hierarchy drops them from the
#: right, so a thin (asset, time, size, state, order) cell borrows from (asset, time, size,
#: state), then (asset, time, size), then (asset, time), then (asset), then the desk.
DIMENSIONS = ("asset", "time", "size", "state", "order")

#: Pseudo-observations of the parent margin mixed into a thin cell. A cell with n = K_SHRINK is
#: believed exactly half; n_eff = n + K_SHRINK is published so the shrinkage is auditable.
K_SHRINK = 8.0

#: Size buckets are DERIVED from the desk's own traded volumes (terciles), never a lot ladder
#: copied from a venue: a book that trades 0.01 lots has no 5-lot evidence and must not pretend.
N_SIZE_BUCKETS = 3
#: Time buckets: the four trading phases the desk already names everywhere else.
_PHASES = ((0, 7, "asia"), (7, 12, "london"), (12, 17, "ny"), (17, 24, "late"))


def _jsonl(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    """Every readable row of a JSONL file. A truncated last line is skipped, never fatal."""
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
        return []
    return out


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _phase(hour: int) -> str:
    for lo, hi, name in _PHASES:
        if lo <= hour < hi:
            return name
    return "late"


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def deal_costs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """One row per recorded deal: its realised execution cost in R, and its five coordinates.

    THE COST IS IN R AND NOT IN QUOTE, because R is the unit the edge is quoted in and a cost
    in dollars cannot be subtracted from an edge in R. `risk_quote` is the deal's own recorded
    risk (stop distance x contract size x volume), so commission + swap over |risk_quote| is
    exactly the share of one unit of risk the venue took. A deal with no recorded risk cannot
    be expressed in R and is COUNTED as unpriceable rather than dropped silently.
    """
    out: list[dict[str, Any]] = []
    notes: list[str] = []
    n_norisk = 0
    vols = [v for v in (_num(r.get("volume")) for r in rows) if v and v > 0]
    edges = (np.quantile(vols, [1 / 3, 2 / 3]).tolist() if len(vols) >= 3 * N_SIZE_BUCKETS
             else [])
    for r in rows:
        risk = _num(r.get("risk_quote"))
        vol = _num(r.get("volume"))
        if risk is None or abs(risk) <= 0 or vol is None or vol <= 0:
            n_norisk += 1
            continue
        comm = abs(_num(r.get("commission")) or 0.0)
        swap = -(_num(r.get("swap")) or 0.0)          # a swap CREDIT lowers the cost
        cost_r = (comm + swap) / abs(risk)
        stamp = str(r.get("time") or "")
        try:
            hour = datetime.fromisoformat(stamp).astimezone(UTC).hour
        except ValueError:
            hour = -1
        if edges:
            size = "small" if vol <= edges[0] else ("large" if vol > edges[1] else "medium")
        else:
            size = "UNMEASURED"
        out.append({
            "asset": str(r.get("symbol") or "?"),
            "time": _phase(hour) if hour >= 0 else "UNMEASURED",
            "hour": hour,
            "size": size,
            "volume": vol,
            "state": "UNMEASURED",                    # filled in by `state_of` below
            "order": "UNMEASURED",                    # filled in from the fill corpus below
            "sleeve": str(r.get("sleeve") or ""),
            "cost_r": round(float(cost_r), 8),
            "commission_quote": round(comm, 4),
            "swap_quote": round(float(swap), 4),
        })
    if n_norisk:
        notes.append(f"{n_norisk} deal(s) carry no recorded risk_quote and cannot be expressed "
                     f"in R; they are counted, never assumed free")
    if not edges and out:
        notes.append(f"fewer than {3 * N_SIZE_BUCKETS} sized deals: the size dimension is "
                     f"UNMEASURED and every cell falls back to its (asset, time) parent")
    return out, notes


def state_of(surface: dict[str, Any], asset: str, hour: int) -> str:
    """The market state this desk can actually measure at a fill: its own spread regime.

    Not an invented volatility label. The surface above already knows what this symbol's
    spread does at each of its 24 hours, so a fill lands in a CHEAP, NORMAL or DEAR book by
    that symbol's own standard -- the state that moves execution cost, measured from the same
    tape the fill happened on.
    """
    sym = (surface.get("symbols") or {}).get(asset) or {}
    hours = sym.get("hours") or {}
    p50s = [float(c["p50"]) for c in hours.values()
            if isinstance(c, dict) and c.get("status") == "MEASURED" and c.get("p50") is not None]
    cell = hours.get(str(int(hour))) if hour >= 0 else None
    if not p50s or not isinstance(cell, dict) or cell.get("status") != "MEASURED":
        return "UNMEASURED"
    here = float(cell["p50"])
    lo, hi = float(np.quantile(p50s, 1 / 3)), float(np.quantile(p50s, 2 / 3))
    return "cheap" if here <= lo else ("dear" if here > hi else "normal")


def order_types(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int], str]:
    """(sleeve, symbol, hour) -> the order type the desk actually sent, from the fill corpus."""
    out: dict[tuple[str, str, int], str] = {}
    for r in rows:
        kind = str(r.get("order_type") or r.get("type") or "")
        if not kind:
            rid = str(r.get("intent_id") or r.get("record_id") or "")
            parts = rid.split("|")
            kind = parts[2] if len(parts) > 2 else ""
        if not kind:
            continue
        try:
            h = int(r.get("hour"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        out[(str(r.get("sleeve") or ""), str(r.get("symbol") or ""), h)] = kind
    return out


def _key(row: dict[str, Any], depth: int) -> tuple[str, ...]:
    return tuple(str(row.get(d, "UNMEASURED")) for d in DIMENSIONS[:depth])


def cells(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every cell at every depth, each SHRUNK toward its own parent margin.

    The hierarchy is the five dimensions read left to right, so the full cell's parent is the
    same cell without its order type, and so on up to the desk-wide margin. A cell with n
    observations and a parent mean m reports (n*own + K*m)/(n + K) and publishes n_eff = n + K,
    so a one-deal cell cannot state a confident number and is not thrown away either.
    """
    by_depth: dict[int, dict[tuple[str, ...], list[float]]] = {
        d: {} for d in range(len(DIMENSIONS) + 1)}
    for row in rows:
        c = float(row["cost_r"])
        for d in range(len(DIMENSIONS) + 1):
            by_depth[d].setdefault(_key(row, d), []).append(c)
    out: dict[str, dict[str, Any]] = {}
    for depth in range(len(DIMENSIONS) + 1):
        for key, vals in sorted(by_depth[depth].items()):
            arr = np.asarray(vals, dtype=float)
            n = int(arr.size)
            own = float(arr.mean())
            parent = None
            if depth > 0:
                pvals = by_depth[depth - 1].get(key[:-1])
                parent = float(np.asarray(pvals, dtype=float).mean()) if pvals else None
            if parent is None:
                shrunk, n_eff = own, float(n)
            else:
                shrunk = (n * own + K_SHRINK * parent) / (n + K_SHRINK)
                n_eff = n + K_SHRINK
            out["|".join(key) if key else "(desk)"] = {
                "depth": depth,
                "dims": {d: key[i] for i, d in enumerate(DIMENSIONS[:depth])},
                "n": n,
                "n_eff": round(n_eff, 2),
                "cost_r_measured": round(own, 8),
                "cost_r_shrunk": round(float(shrunk), 8),
                "sd_r": round(float(arr.std(ddof=1)), 8) if n >= 2 else None,
                "parent_cost_r": None if parent is None else round(parent, 8),
                "status": "MEASURED" if n >= 2 else "THIN",
            }
    return out


def modelled_cost_r(surface: dict[str, Any], asset: str, hour: int,
                    stop_pts: float | None) -> float | None:
    """The fallback an UNMEASURED cell falls back to: the MODELLED spread at that hour, in R.

    Returns None -- not 0.0 -- when the surface has no number for that symbol-hour or the
    caller has not said how wide its stop is. A cost of zero is the one answer that is always
    wrong, and this desk has already paid for it once (see the module docstring).
    """
    pts = spread_pts(surface, asset, hour if hour >= 0 else None)
    if pts is None or stop_pts is None or stop_pts <= 0:
        return None
    return float(2.0 * pts / stop_pts)            # a round trip crosses the spread twice


def lookup(surf: dict[str, Any], *, asset: str, time: str, size: str, state: str,
           order: str) -> dict[str, Any]:
    """The cost at a cell, falling back UP the hierarchy and naming which level answered."""
    coords = {"asset": asset, "time": time, "size": size, "state": state, "order": order}
    # THE FALLBACK STOPS AT THE ASSET AND DOES NOT REACH THE DESK-WIDE MARGIN. A desk average
    # over every symbol it has ever traded is not an estimate of an untraded symbol's cost --
    # it is the pooled scalar this module exists to end, one level up. An asset with no
    # execution evidence at all is UNMEASURED and the MODELLED spread answers instead.
    for depth in range(len(DIMENSIONS), 0, -1):
        key = "|".join(str(coords[d]) for d in DIMENSIONS[:depth]) or "(desk)"
        cell = (surf.get("cells") or {}).get(key)
        if cell and int(cell.get("n") or 0) > 0:
            return {"cost_r": cell["cost_r_shrunk"], "n": cell["n"], "n_eff": cell["n_eff"],
                    "resolved_at": "|".join(DIMENSIONS[:depth]) or "(desk)",
                    "status": "MEASURED" if depth == len(DIMENSIONS) else "SHRUNK_TO_PARENT"}
    return {"cost_r": None, "n": 0, "n_eff": 0.0, "resolved_at": None,
            "status": "UNMEASURED",
            "why": "the desk has never traded this cell; the modelled spread is the fallback"}


def raw_alpha_rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Every candidate the desk carries a RawAlpha for, with the unit it is quoted in."""
    inputs: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    canon = _json(_SURVIVORS)
    inputs[_SURVIVORS.name] = "present" if canon else "absent"
    for key, row in (canon.get("survivors") or {}).items():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        val = _num(((row.get("gates") or {}).get("expected_value") or {}).get("ev"))
        if val is None:
            continue
        out.append({"id": str(key), "asset": str(spec.get("symbol") or row.get("sym") or "?"),
                    "family": str(spec.get("family") or ""),
                    "selector": str(spec.get("selector") or ""),
                    "raw_alpha": round(val, 6), "unit": "R_per_trade",
                    "source": "UNIVERSAL_SURVIVORS.canon.json gates.expected_value.ev"})
    post = _json(_POSTERIOR_ALPHA)
    inputs[_POSTERIOR_ALPHA.name] = "present" if post else "absent"
    for row in (post.get("sleeves") or []):
        if not isinstance(row, dict):
            continue
        val = _num(row.get("mu_mean"))
        if val is None:
            continue
        out.append({"id": str(row.get("name") or "?"), "asset": str(row.get("symbol") or "?"),
                    "family": str(row.get("family") or ""),
                    "selector": str(row.get("lane") or ""),
                    "raw_alpha": round(val, 6), "unit": "R_per_day",
                    "source": "POSTERIOR_ALPHA.json mu_mean"})
    return out, inputs


def net_alpha(raws: list[dict[str, Any]], surf: dict[str, Any], spread: dict[str, Any],
              ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """NetAlpha = RawAlpha - ExpectedExecutionCost, and the candidates whose SIGN flips.

    A row whose cost can neither be measured nor modelled carries NetAlpha None with the
    reason: an unpriced candidate is UNMEASURED, never a candidate that is cheap.
    """
    rows: list[dict[str, Any]] = []
    flips: list[dict[str, Any]] = []
    dearest: dict[str, int] = {}
    for a, prof in (spread.get("symbols") or {}).items():
        hour = prof.get("dearest_hour") if isinstance(prof, dict) else None
        if isinstance(hour, int):
            dearest[a] = hour
    for r in raws:
        asset = r["asset"]
        hour = dearest.get(asset, -1)
        hit = lookup(surf, asset=asset, time=_phase(hour) if hour >= 0 else "UNMEASURED",
                     size="UNMEASURED", state=state_of(spread, asset, hour), order="UNMEASURED")
        cost = hit["cost_r"]
        basis = hit["status"]
        if cost is None:
            cost = modelled_cost_r(spread, asset, hour, None)
            basis = "MODELLED" if cost is not None else "UNMEASURED"
        net = None if cost is None else round(float(r["raw_alpha"]) - float(cost), 6)
        rows.append(dict(
            r, cost_r=None if cost is None else round(float(cost), 8), cost_basis=basis,
            cost_resolved_at=hit.get("resolved_at"), cost_n=hit.get("n"),
            cost_n_eff=hit.get("n_eff"), net_alpha=net,
            why=None if cost is not None else hit.get("why", "no measured or modelled cost")))
        if net is not None and float(r["raw_alpha"]) > 0 >= net:
            flips.append({"id": r["id"], "asset": asset, "raw_alpha": r["raw_alpha"],
                          "cost_r": rows[-1]["cost_r"], "net_alpha": net, "unit": r["unit"],
                          "cost_basis": basis})
    rows.sort(key=lambda x: (-(x["net_alpha"] if x["net_alpha"] is not None else -9e9),
                             str(x["id"])))
    return rows, flips


def build_execution_surface(spread: dict[str, Any], *, ledger: Path | None = None,
                            corpus: Path | None = None) -> dict[str, Any]:
    """The five-dimensional surface and the NetAlpha table, built and written every run."""
    lp, cp = ledger or _LIVE_LEDGER, corpus or _FILL_CORPUS
    deals = _jsonl(lp)
    corpus_rows = _jsonl(cp)
    inputs = {lp.name: "present" if deals else "absent",
              cp.name: "present" if corpus_rows else "absent"}
    rows, notes = deal_costs(deals)
    kinds = order_types(corpus_rows)
    for row in rows:
        row["state"] = state_of(spread, row["asset"], int(row["hour"]))
        row["order"] = kinds.get((row["sleeve"], row["asset"], int(row["hour"])), "UNMEASURED")
    surf = {"cells": cells(rows)}
    raws, raw_inputs = raw_alpha_rows()
    inputs.update(raw_inputs)
    net, flips = net_alpha(raws, surf, spread)
    measured = {d: sorted({str(r.get(d)) for r in rows} - {"UNMEASURED"}) for d in DIMENSIONS}
    if not rows:
        notes.append("no recorded deal carries a priceable execution cost on this host: every "
                     "cell is UNMEASURED and every NetAlpha falls back to the modelled spread")
    return {
        "schema": "execution-cost-surface-1",
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "dimensions": list(DIMENSIONS),
        "k_shrink": K_SHRINK,
        "inputs": inputs,
        "n_deals_priced": len(rows),
        "n_cells": len(surf["cells"]),
        "levels_measured": {d: len(v) for d, v in measured.items()},
        "levels": measured,
        "cells": surf["cells"],
        "n_raw_alpha": len(raws),
        "net_alpha": net[:400],
        "n_sign_flips": len(flips),
        "sign_flips": flips[:100],
        "unmeasured": notes,
        "rule": ("Cost(asset, time, size, state, order) in R per trade from the desk's own "
                 "recorded deals, shrunk toward the parent margin at n < K_SHRINK; a cell the "
                 "desk has never traded is UNMEASURED and falls back to the MODELLED spread, "
                 "never to zero. NetAlpha = RawAlpha - ExpectedExecutionCost is EVIDENCE: it "
                 "vetoes nothing, caps nothing and gates no promotion."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=_OUT)
    ap.add_argument("--universe", type=Path, default=None)
    ap.add_argument("--exec-out", type=Path, default=_EXEC_OUT,
                    help="where the five-dimensional execution surface + NetAlpha are written")
    ap.add_argument("--no-execution", action="store_true",
                    help="build only the symbol x hour spread surface (the historic behaviour)")
    args = ap.parse_args(argv)

    rep = build(args.universe)
    if not rep["symbols"]:
        print("cost_surface: NO SYMBOLS PROFILED -- refusing to write an empty surface "
              f"(looked in {args.universe or _UNIVERSE}). Unmeasured is not OK (L1.28a).")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    syms = rep["symbols"]
    admin = sum(1 for v in syms.values() if v.get("administered"))
    unmeas = sum(1 for v in syms.values() for c in v["hours"].values()
                 if c["status"] == "UNMEASURED")
    total_cells = sum(len(v["hours"]) for v in syms.values())
    ratios = [(s, v["dear_over_cheap"]) for s, v in syms.items()
              if v.get("dear_over_cheap")]
    ratios.sort(key=lambda kv: -kv[1])
    print(f"cost_surface: {rep['n_symbols']} symbols, {total_cells} symbol-hour cells, "
          f"{unmeas} UNMEASURED, {admin} administered (flat 24h), "
          f"{rep['n_skipped']} skipped -> {args.out}")
    print("  widest dear/cheap ratios: " +
          ", ".join(f"{s} {r}x" for s, r in ratios[:8]))

    if not args.no_execution:
        ex = build_execution_surface(rep)
        args.exec_out.parent.mkdir(parents=True, exist_ok=True)
        args.exec_out.write_text(json.dumps(ex, indent=1, sort_keys=True) + "\n", "utf-8")
        print(f"  execution surface: {ex['n_deals_priced']} priced deal(s), "
              f"{ex['n_cells']} cell(s) over {len(ex['dimensions'])} dimensions; "
              f"{ex['n_raw_alpha']} RawAlpha row(s), {ex['n_sign_flips']} sign flip(s) "
              f"-> {args.exec_out}")
        for note in ex["unmeasured"][:3]:
            print(f"    UNMEASURED: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
