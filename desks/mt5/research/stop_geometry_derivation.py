#!/usr/bin/env python3
"""STOP GEOMETRY DERIVATION: the two stop-geometry constants, solved rather than chosen.

Two money-path numbers carried an argument and no measurement (`check_sizing_derivation`,
2026-09-30):

    gateway.MIN_STOP_SPREAD_MULT     3.0   a scalp stop closer than m spreads is widened to m
                                           spreads, stop and target scaled together (R:R kept)
    decision_core.ENTRY_DRIFT_TOL_FRAC 0.25 a family entry within tau of the certified stop from
                                           the signal close keeps the certified LEVELS; past it
                                           the certified DISTANCES are re-laid from the entry

Both are set here by the same solve `kelly_survival` runs for the gold book:

    maximise   ruin-counted E[log W]                      (kelly_survival.ruin_counted_elog)
    subject to P(equity <= 20% of start within 60 days) <= 5%   (DEATH_LINE, EPS_DEATH, HORIZON)

over a grid of each constant, every trade at the risk fraction the allocator gives its lane
today. Neither constant changes the EUR at risk per trade (`promoted_lot` sizes against the
stop actually sent), so neither can raise or lower heat; what they change is the lot per EUR of
risk, and therefore how much of the spread and its widening each R carries. That is where the
growth is won or lost, and it is what the solve prices.

THE TRADE MODEL, every input measured from the desk's own files:

    x     plan stop distance in spreads: stop_atr x ATR(14) / spread, per bar, on the bars the
          lane trades (scalp: the sleeve's own timeframe; family: H1, ATR(20), stop_atr 2.0,
          the `family_discovered` defaults the certified specs run with)
    W     spread widening over the hold: max(spread over the next H bars) / spread at entry,
          from the same bars' spread column. A stop m spreads from the touch is taken by the
          quote alone when W >= 2m - 1 (the entry pays half the entry spread, the widened
          quote pays half of W spreads, the mid need not move).
    e     the lane's per-trade expectancy in R: the certified/forward prior (scalp: the LIVE
          sleeves' `shadow_exp`; family: the certificates' `expected_value.ev`) moved by the
          live ledger on the desk's posterior convention (`posterior_growth`: K_SLEEVE,
          LIVE_WEIGHT), exactly as `kelly_survival.posterior_shift` does.
    a     family entry drift, in certified stop units, over the measured signal-to-entry delay
          (`family_bracket`'s own measurement, 2026-09-16: 4 to 14 minutes; one M15 bar covers
          it), from the M15 bars of the family symbols.

A certificate's R is net of the spread it modelled at its own geometry, so its price edge is
`e*x + 1` spreads. Held for a fixed number of bars, that price edge does not grow when the
bracket is widened: at stop distance x' it is worth (e*x + 1)/x' R gross, less 1/x' R of spread,
and the trade is lost outright (-1R less spread) with P(W >= 2x' - 1). Wider stops therefore
buy fewer quote-taken stops at the price of a diluted edge; the solve finds where that trade-off
maximises E[log W].

WHAT IT CANNOT SEE, stated so the number is read with it: the bar spread column is the bar's
recorded spread, not its intrabar maximum, so W is understated and the derived m is a lower
bound; commission is not modelled (it scales with 1/x' exactly like the spread, so it would push
m the same way); and the family drift delay is a single measurement from one session.

An absent input is UNMEASURED, never a default: the report names what it needs.

PUBLISHED IS NOT ADOPTED. Each constant carries `adopt` / `adopt_value` from `robustness_gate`,
and the money path runs `adopt_value`: the derived number replaces today's only when (a) the
lane's live trades span the N distinct days `days_needed` derives from the distance to the
break-even edge, (b) the measurement covers at least half the lane's symbols, and (c) the gain
holds on BOTH the certificate-only and the live-adjusted edge. The gate is two-sided: a move
toward MORE aggressive passes through the same three tests (GROWTH_GOVERNANCE Rules 1 and 2).

    python desks/mt5/research/stop_geometry_derivation.py   # writes the report below
    -> desks/mt5/reports/STOP_GEOMETRY_DERIVATION.json
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from kelly_survival import (  # type: ignore[import-not-found]  # noqa: E402
    DEATH_LINE,
    EPS_DEATH,
    HORIZON,
    deal_r,
    posterior_shift,
    ruin_counted_elog,
)

SLEEVES = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
SURVIVORS = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
COST_SURFACE = BASE / "data" / "cost_surface.json"
BARS = BASE / "data" / "universe"
OUT = BASE / "reports" / "STOP_GEOMETRY_DERIVATION.json"

#: The values the money path carries today, read for the missed-growth comparison only.
TODAY_MIN_STOP_SPREAD_MULT = 3.0
TODAY_ENTRY_DRIFT_TOL_FRAC = 0.25

#: The grids searched. m below 1 would place the stop inside the entry spread itself; tau at 1
#: is the stale-signal line `family_bracket` already draws, so neither grid can leave its domain.
M_GRID = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0)
TAU_GRID = (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9)
N_PATHS = 4000
#: The family lane's certified bracket (`families_orthogonal.family_discovered` defaults; the
#: certified shadow specs carry no override) and the scalp lane's ATR length (`scalp_exec`).
FAMILY_STOP_ATR, FAMILY_RR, FAMILY_ATR_N, SCALP_ATR_N = 2.0, 1.5, 20, 14
#: Signal-to-entry delay of the family lane, measured 2026-09-16 in `family_bracket`'s
#: docstring as 4 to 14 minutes. No organ journals it yet; one M15 bar is its upper bound.
FAMILY_DELAY_M15_BARS = 1
#: Samples below which a distribution is UNMEASURED rather than thin.
MIN_SAMPLES = 200


def _rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        out.append(row)
    except OSError:
        pass
    return out


def _sleeves() -> list[dict[str, Any]]:
    doc = _read_json(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [s for s in (rows or []) if isinstance(s, dict)]


def _tick_size(symbol: str) -> float | None:
    doc = _read_json(COST_SURFACE)
    row = ((doc or {}).get("symbols") or {}).get(symbol) or {}
    v = row.get("tick_size")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


@functools.lru_cache(maxsize=64)
def _read_parquet(path: Path) -> Any:
    import pandas as pd
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _bars(symbol: str, tf: str) -> Any:
    """Keyed on the full path, so a test that repoints BARS never reads a cached frame."""
    return _read_parquet(BARS / f"{symbol}_{tf}.parquet")


def _atr(df: Any, n: int) -> np.ndarray:
    h, lo, c = (df[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - lo, np.abs(h - pc), np.abs(lo - pc)])
    k = np.ones(n) / n
    atr = np.convolve(tr, k, mode="full")[: len(tr)]
    atr[: n - 1] = np.nan
    return atr


def spread_geometry(df: Any, tick: float, stop_atr: float, atr_n: int,
                    hold: int) -> tuple[np.ndarray, np.ndarray]:
    """(x, W) per usable bar: stop distance in spreads, and the spread's widening over the hold."""
    sp = df["spread"].to_numpy(dtype=float) * tick
    atr = _atr(df, atr_n)
    n = len(sp)
    xs, ws = [], []
    for i in range(atr_n, n - hold):
        s0 = sp[i]
        if not (s0 > 0 and math.isfinite(atr[i]) and atr[i] > 0):
            continue
        xs.append(stop_atr * atr[i] / s0)
        ws.append(float(np.max(sp[i + 1:i + 1 + hold])) / s0)
    return np.asarray(xs), np.asarray(ws)


def trade_r(x: np.ndarray, rr: np.ndarray, edge_price: np.ndarray, w: np.ndarray,
            u_win: np.ndarray) -> np.ndarray:
    """Net R of one trade at stop distance x spreads, R:R rr, price edge (spreads, gross) and
    spread widening w, on common random numbers. Quote-taken when w >= 2x - 1."""
    cost = 1.0 / x
    mu = edge_price / x                                  # gross expectancy in R at this geometry
    q = np.clip((1.0 + mu) / (1.0 + rr), 0.0, 1.0)       # two-point {-1, +rr} with that mean
    win = u_win < q
    gross = np.where(win, rr, -1.0)
    quote_taken = w >= (2.0 * x - 1.0)
    gross = np.where(quote_taken, -1.0, gross)
    return gross - cost


#: Two paired standard errors: a grid value whose E[log W] sits within this of the best is a
#: tie on the evidence (common random numbers, so the SE is of the DIFFERENCE, path by path).
TIE_SE = 2.0


def _path_logw(daily: np.ndarray, f: float) -> np.ndarray:
    """Per-path ruin-counted log wealth per day -- the vector whose mean `ruin_counted_elog`
    reports, kept so a difference between two grid values carries its own standard error."""
    x = 1.0 + daily[:, :, 0] * f
    cum = np.cumsum(np.log(np.clip(x, 1e-12, None)), axis=1)
    dead = cum.min(axis=1) <= math.log(DEATH_LINE)
    out: np.ndarray = np.where(dead, math.log(DEATH_LINE), cum[:, -1]) / daily.shape[1]
    return out


def _solve(grid: tuple[float, ...], r_of: Any, active: np.ndarray, f: float,
           today: float, more_aggressive_is: str,
           against: float | None = None) -> dict[str, Any]:
    """Grid solve: maximise E[log W] subject to P(death) <= EPS_DEATH.

    Ties (within TIE_SE paired SEs of the best) go to aggression, as in kelly_survival. When
    EVERY surviving value ties, the data do not identify the constant: the report says
    NOT_IDENTIFIED, names the value the tie rule would give, and leaves today's standing -- a
    flat objective is not evidence for moving a money-path number in either direction."""
    rows, lw = [], {}
    for v in grid:
        r = r_of(v)
        daily = np.where(active, r, 0.0).sum(axis=2)[:, :, None]
        el, p_dead, p_dd = ruin_counted_elog(daily, np.array([f]))
        lw[v] = _path_logw(daily, f)
        rows.append({"value": v, "elog_per_day": round(el, 8), "p_death": round(p_dead, 4),
                     "p_dd35": round(p_dd, 4), "survives": p_dead <= EPS_DEATH,
                     "mean_r_per_trade": round(float(r[active].mean()), 5)
                     if active.any() else None})
    ok = [r for r in rows if r["survives"]]
    if not ok:
        return {"status": "NO_SURVIVING_VALUE: every value crosses the death line; today stands",
                "grid": rows, "derived": None, "today": today}
    best = max(ok, key=lambda r: lw[r["value"]].mean())
    for r in rows:
        d = lw[r["value"]] - lw[best["value"]]
        se = float(d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else 0.0
        r["delta_vs_best"], r["se_delta"] = round(float(d.mean()), 9), round(se, 9)
        r["tied_with_best"] = bool(r["survives"] and abs(float(d.mean())) <= TIE_SE * se + 1e-12)
    tied = [r for r in ok if r["tied_with_best"]]
    agg = min if more_aggressive_is == "lower" else max
    pick = agg(tied, key=lambda r: r["value"])
    t_row = next((r for r in rows if abs(r["value"] - today) < 1e-12), None)
    # MOVING A MONEY-PATH NUMBER NEEDS A SIGNIFICANT GAIN. If today's value is itself tied with
    # the best, the evidence does not say it is wrong, and a move would be noise wearing a
    # derivation's clothes; today's value stands and the report says so.
    moved = not (t_row and t_row["tied_with_best"])
    v = pick["value"] if moved else today
    less = (v > today) if more_aggressive_is == "lower" else (v < today)
    # THE GAP A MOVE RESTS ON: the named value (default: the one chosen) against today's, paired
    # path by path. `holds` only when it is ahead by more than TIE_SE of its own SE.
    cand = v if against is None else against
    gap: dict[str, Any] | None = None
    if cand in lw and today in lw:
        d = lw[cand] - lw[today]
        se = float(d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else 0.0
        gap = {"value": cand, "delta_elog_per_day": round(float(d.mean()), 9),
               "se": round(se, 9),
               "holds": bool(abs(cand - today) > 1e-12 and float(d.mean()) > TIE_SE * se)}
    return {"status": "OK" if moved else "TODAY_OPTIMAL_WITHIN_NOISE",
            "gap_vs_today": gap,
            "derived": v, "today": today,
            "tie_rule_value": pick["value"],
            "why": (f"E[log W] is maximised at {pick['value']:g} and today's {today:g} is "
                    f"{abs(t_row['delta_vs_best']) / max(t_row['se_delta'], 1e-15):.1f} paired "
                    f"SEs below it" if moved and t_row else
                    f"E[log W] is maximised (ties to aggression) at {pick['value']:g}"
                    if moved else
                    f"today's {today:g} is within {TIE_SE:g} paired SEs of the best on the "
                    f"measured lane, so it stands (the tie rule alone would give "
                    f"{pick['value']:g}; {len(tied)} of {len(ok)} surviving values tie)"),
            "chosen": pick if moved else t_row, "today_row": t_row,
            "vs_today": ({"delta_elog_per_day": round(pick["elog_per_day"]
                                                      - t_row["elog_per_day"], 8)}
                         if t_row else None),
            "more_aggressive_is": more_aggressive_is,
            "less_aggressive_than_today": bool(less),
            "grid": rows}


#: The ledger's sleeve field is the order comment, which the venue truncates (27 characters
#: measured: 'eurgbp_discovered_asia_p_8e'); a truncated name matches the sleeve it prefixes, and a
#: prefix shorter than this is too short to name one sleeve.
MIN_SLEEVE_PREFIX = 16


def ledger_r(d: dict[str, Any]) -> float | None:
    """A deal's realised R, only where the ledger reconstructed it against a POSITIVE quote risk.

    `kelly_survival.deal_r` falls back to P/L over `risk_quote`, which on the 2026-09-16 family
    rows is a signed PRICE distance (-0.00026 on EURGBP), not money: the fallback reads those as
    -16R and -4R. A zero `r_multiple` there means "not reconstructed", not a scratch trade."""
    risk = d.get("risk_quote")
    if not (isinstance(risk, (int, float)) and risk > 0):
        return None
    r = deal_r(d)
    return r if r is not None and r != 0.0 else None


def _sleeve_of(d: dict[str, Any], names: set[str]) -> bool:
    tag = str(d.get("sleeve") or "")
    return tag in names or (len(tag) >= MIN_SLEEVE_PREFIX
                            and any(n.startswith(tag) for n in names))


def _posterior_edge(prior: float, sleeve_names: set[str],
                    deals: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    rows = [(str(d.get("time") or "")[:10], r) for d in deals if _sleeve_of(d, sleeve_names)
            and str(d.get("account_kind") or "live") == "live"
            for r in [ledger_r(d)] if r is not None]
    live = [r for _, r in rows]
    by_day: dict[str, list[float]] = {}
    for day, r in rows:
        by_day.setdefault(day, []).append(r)
    day_means = [float(np.mean(v)) for v in by_day.values()]
    mean, w = posterior_shift(prior, live)
    return mean, {"prior_r": round(prior, 5), "live_n": len(live),
                  "live_days": len(by_day),
                  "live_day_mean_sd": (round(float(np.std(day_means, ddof=1)), 5)
                                       if len(day_means) > 1 else None),
                  "live_mean_r": round(float(np.mean(live)), 5) if live else None,
                  "live_weight": round(w, 4), "posterior_r": round(mean, 5)}


def _activity(rng: np.random.Generator, rate: float, slots: int) -> np.ndarray:
    n = rng.poisson(rate, size=(N_PATHS, HORIZON))
    return np.arange(slots)[None, None, :] < np.minimum(n, slots)[:, :, None]


def derive_min_stop_spread_mult(deals: list[dict[str, Any]], seed: int = 0,
                                prior_only: bool = False,
                                edge_override: float | None = None,
                                grid: tuple[float, ...] | None = None,
                                against: float | None = None) -> dict[str, Any]:
    lane = [s for s in _sleeves() if s.get("exec") == "scalp_market"]
    # Geometry from every scalp sleeve (a STANDBY row is promoted with no human act, so its bars
    # are the lane's too); edge, rate and risk from the LIVE rows the book actually carries.
    scalps = [s for s in lane if s.get("status") == "LIVE"]
    if not scalps:
        return {"status": "UNMEASURED: no LIVE scalp_market sleeve in sleeves.json -- needs one "
                          "(its timeframe, stop_atr, target_atr, max_hold, shadow_exp, risk_frac)"}
    xs, ws, need = [], [], []
    for s in lane:
        sym, tf = str(s.get("symbol")), str(s.get("timeframe") or "")
        tick, df = _tick_size(sym), _bars(sym, tf)
        if tick is None or df is None or "spread" not in getattr(df, "columns", []):
            need.append(f"{sym}_{tf}.parquet with a spread column and a cost_surface tick_size")
            continue
        x, w = spread_geometry(df, tick, float(s.get("stop_atr") or 1.0), SCALP_ATR_N,
                               int(s.get("max_hold") or 1))
        xs.append(x)
        ws.append(w)
    if not xs or sum(len(x) for x in xs) < MIN_SAMPLES:
        return {"status": "UNMEASURED: too few bars with a recorded spread", "needs": need}
    x_all, w_all = np.concatenate(xs), np.concatenate(ws)
    n_sh = sum(float(s.get("shadow_n") or 0) for s in scalps)
    if n_sh <= 0:
        return {"status": "UNMEASURED: no scalp sleeve carries a forward shadow_exp/shadow_n",
                "needs": ["the forward clock's shadow_exp and shadow_n on the LIVE scalp rows"]}
    prior = sum(float(s.get("shadow_exp") or 0.0) * float(s.get("shadow_n") or 0)
                for s in scalps) / n_sh
    names = {str(s.get("name")) for s in _sleeves() if s.get("exec") == "scalp_market"}
    e, post = _posterior_edge(prior, names, [] if prior_only else deals)
    if edge_override is not None:
        e = edge_override
    days = sum(float(s.get("shadow_days") or 0) for s in scalps)
    rate = n_sh / days if days > 0 else float("nan")
    if not (rate > 0):
        return {"status": "UNMEASURED: no shadow_days to measure the lane's trade rate"}
    f = float(np.median([float(s.get("risk_frac") or 0.0) for s in scalps]))
    rr = float(np.median([float(s.get("target_atr") or 1.5) / float(s.get("stop_atr") or 1.0)
                          for s in scalps]))
    rng = np.random.default_rng(seed)
    slots = max(4, int(rate * 4) + 4)
    active = _activity(rng, rate, slots)
    shape = active.shape
    idx = rng.integers(0, len(x_all), size=shape)
    x0, w0 = x_all[idx], w_all[idx]
    u_w = rng.random(shape)
    edge_price = e * x0 + 1.0

    def r_of(m: float) -> np.ndarray:
        x_eff = np.maximum(x0, m)
        return trade_r(x_eff, np.full(shape, rr), edge_price, w0, u_w)

    res = _solve(grid or M_GRID, r_of, active, f, TODAY_MIN_STOP_SPREAD_MULT, "lower", against)
    n_bind = int((active & (x0 < max(M_GRID))).sum())
    res["binding_trades_simulated"] = n_bind
    if n_bind < MIN_SAMPLES and res.get("status") == "OK":
        # A floor that never binds cannot be priced by the lane it guards: any move is noise.
        res.update({"status": "TODAY_OPTIMAL_WITHIN_NOISE", "derived": res["today"],
                    "chosen": res["today_row"], "less_aggressive_than_today": False,
                    "why": f"the floor binds on {n_bind} simulated trades (< {MIN_SAMPLES}); "
                           f"E[log W] cannot tell the grid apart, so today's value stands"})
    res["inputs"] = {
        "geometry_sleeves": sorted(str(s.get("name")) for s in lane),
        "edge_sleeves": sorted(str(s.get("name")) for s in scalps),
        "n_bars": len(x_all),
        "x_spreads_quantiles": {q: round(float(np.quantile(x_all, q)), 3)
                                for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        "share_below_today_floor": round(float((x_all < TODAY_MIN_STOP_SPREAD_MULT).mean()), 4),
        "share_below_grid_top": round(float((x_all < max(M_GRID)).mean()), 4),
        "widening_quantiles": {q: round(float(np.quantile(w_all, q)), 3)
                               for q in (0.5, 0.9, 0.99, 0.999)},
        "edge": post, "trades_per_day": round(rate, 4), "risk_frac": f, "rr": rr,
        "coverage": {"measured": len(lane) - len(need), "of": len(lane),
                     "unit": "scalp sleeves whose bars carry a spread"},
        "needs_but_missing": need,
    }
    return res


def derive_entry_drift_tol_frac(deals: list[dict[str, Any]], seed: int = 1,
                                prior_only: bool = False,
                                edge_override: float | None = None,
                                grid: tuple[float, ...] | None = None,
                                against: float | None = None) -> dict[str, Any]:
    fams = [s for s in _sleeves() if s.get("exec") == "family_market"
            and s.get("status") == "LIVE"]
    if not fams:
        return {"status": "UNMEASURED: no LIVE family_market sleeve in sleeves.json"}
    surv = ((_read_json(SURVIVORS) or {}).get("survivors") or {})
    evs = []
    for s in fams:
        cell = (s.get("certificate") or {}).get("cell") if isinstance(s.get("certificate"),
                                                                        dict) else None
        v = surv.get(str(cell)) if cell else None
        ev = (((v or {}).get("gates") or {}).get("expected_value") or {}).get("ev")
        if isinstance(ev, (int, float)) and math.isfinite(ev):
            evs.append(float(ev))
    if not evs:
        return {"status": "UNMEASURED: no LIVE family sleeve's certificate carries "
                          "expected_value.ev in UNIVERSAL_SURVIVORS.canon.json"}
    prior = float(np.median(evs))
    e, post = _posterior_edge(prior, {str(s.get("name")) for s in fams},
                              [] if prior_only else deals)
    if edge_override is not None:
        e = edge_override
    syms = sorted({str(s.get("symbol")) for s in fams})
    drifts, xs, ws, used, need = [], [], [], [], []
    for sym in syms:
        h1, m15, tick = _bars(sym, "H1"), _bars(sym, "M15"), _tick_size(sym)
        if h1 is None or m15 is None or tick is None:
            need.append(f"{sym}: H1 and M15 bars and a cost_surface tick_size")
            continue
        atr = _atr(h1, FAMILY_ATR_N)
        d_stop = FAMILY_STOP_ATR * atr
        close = h1["close"].to_numpy(dtype=float)
        # H1 bars are stamped at their open; the signal bar closes one hour later, and the entry
        # comes one M15 bar after that.
        import pandas as pd
        t_close = h1.index + pd.Timedelta(hours=1)
        m_close = m15["close"]
        # indexed by each M15 bar's CLOSE time, looked up one delay after the H1 close
        later = pd.Series(m_close.to_numpy(dtype=float), index=m15.index + pd.Timedelta(minutes=15))
        px_entry = later.reindex(
            t_close + pd.Timedelta(minutes=15 * FAMILY_DELAY_M15_BARS)).to_numpy(dtype=float)
        ok = np.isfinite(px_entry) & np.isfinite(d_stop) & (d_stop > 0)
        if ok.sum() == 0:
            need.append(f"{sym}: no overlapping H1/M15 history")
            continue
        drifts.append((px_entry[ok] - close[ok]) / d_stop[ok])
        # W over the family hold (12 M15 bars = the certified 3-bar H1 horizon); the family's
        # stop in spreads is its own 2 x ATR20(H1) over the symbol's median M15 spread.
        _x, w = spread_geometry(m15, tick, 1.0, SCALP_ATR_N, 12)
        sp = m15["spread"].to_numpy(dtype=float) * tick
        med_sp = float(np.median(sp[sp > 0])) if (sp > 0).any() else float("nan")
        if math.isfinite(med_sp) and med_sp > 0:
            xs.append(d_stop[ok] / med_sp)
        ws.append(w)
        used.append(sym)
    n_d = sum(len(d) for d in drifts)
    if n_d < MIN_SAMPLES or not xs or not ws:
        return {"status": "UNMEASURED: too little overlapping H1/M15 history on the family "
                          "symbols to measure entry drift",
                "needs": need or ["M15 bars for the LIVE family symbols"],
                "family_symbols": syms}
    d_all = np.concatenate(drifts)
    x_all, w_all = np.concatenate(xs), np.concatenate(ws)
    fam_names = {str(s.get("name")) for s in fams}
    fam_deals = [d for d in deals if _sleeve_of(d, fam_names)]
    # SIGNALS, not deal rows: the lane slices one signal into several orders that share ONE
    # risk budget (`slice_lot`), and every LIVE family sleeve trades the one asia session a day,
    # so a sleeve's rows on one date are one bet at the sleeve's risk fraction.
    n_trades = len({(str(d.get("sleeve")), str(d.get("time"))[:10]) for d in fam_deals})
    times = sorted(str(d.get("time")) for d in fam_deals)
    last = max((str(d.get("time")) for d in deals), default="")
    span = ((datetime.fromisoformat(last) - datetime.fromisoformat(times[0])).days + 1
            if times and last else 0)
    if not (n_trades > 0 and span > 0):
        return {"status": "UNMEASURED: the live ledger holds no family-lane position to measure "
                          "the lane's trade rate", "needs": ["family-lane rows in live_ledger"]}
    rate = n_trades / span
    f = float(np.median([float(s.get("risk_frac") or 0.0) for s in fams]))
    rr = FAMILY_RR
    rng = np.random.default_rng(seed)
    slots = max(4, int(rate * 4) + 4)
    active = _activity(rng, rate, slots)
    shape = active.shape
    sgn = np.where(rng.random(shape) < 0.5, 1.0, -1.0)
    a = sgn * d_all[rng.integers(0, len(d_all), size=shape)]   # adverse > 0, in stop units
    x0 = x_all[rng.integers(0, len(x_all), size=shape)]
    w0 = w_all[rng.integers(0, len(w_all), size=shape)]
    u_w = rng.random(shape)
    edge_price = e * x0 + 1.0
    stale = (a >= 1.0) | (-a / rr >= 1.0)
    active = active & ~stale
    r_re = trade_r(x0, np.full(shape, rr), edge_price, w0, u_w)
    x_v = x0 * np.clip(1.0 - a, 1e-6, None)
    rr_v = (rr + a) / np.clip(1.0 - a, 1e-6, None)
    r_vb = trade_r(x_v, rr_v, edge_price, w0, u_w)

    def r_of(tau: float) -> np.ndarray:
        return np.where(np.abs(a) <= tau, r_vb, r_re)

    res = _solve(grid or TAU_GRID, r_of, active, f, TODAY_ENTRY_DRIFT_TOL_FRAC, "higher",
                 against)
    res["inputs"] = {
        "family_symbols_used": used, "n_drift_samples": int(n_d),
        "abs_drift_quantiles": {q: round(float(np.quantile(np.abs(d_all), q)), 4)
                                for q in (0.5, 0.9, 0.99)},
        "x_spreads_median": round(float(np.median(x_all)), 3),
        "widening_quantiles": {q: round(float(np.quantile(w_all, q)), 3)
                               for q in (0.5, 0.9, 0.99)},
        "edge": post, "certificates_with_ev": len(evs), "trades_per_day": round(rate, 4),
        "rate_basis": f"{n_trades} sleeve-days over {span} ledger day(s)",
        "risk_frac": f, "rr": rr, "delay_m15_bars": FAMILY_DELAY_M15_BARS,
        "coverage": {"measured": len(used), "of": len(syms),
                     "unit": "LIVE family symbols with H1+M15 bars for entry drift"},
        "needs_but_missing": need,
    }
    return res


#: How far past the prior and live edges the break-even search looks, in R per trade, and the
#: bisection steps within it. A break-even edge farther than this from the live one is reported
#: as "beyond", and the day count is sized to this distance (a floor on what is needed).
EDGE_SEARCH_R = 1.0
BISECT_STEPS = 8


def _gap_at(fn: Any, deals: list[dict[str, Any]], edge: float, today: float,
            cand: float) -> float:
    r = fn(deals, edge_override=edge, grid=tuple(sorted({today, cand})), against=cand)
    g = r.get("gap_vs_today") or {}
    return float(g.get("delta_elog_per_day") or 0.0)


def break_even_edge(fn: Any, deals: list[dict[str, Any]], edge: float, today: float,
                    cand: float) -> tuple[float | None, float]:
    """The per-trade edge at which the candidate and today's value tie on E[log W].

    Returns (e*, distance from the live edge); e* is None when no sign change lies within
    EDGE_SEARCH_R of the live edge, and the distance is then EDGE_SEARCH_R."""
    g0 = _gap_at(fn, deals, edge, today, cand)
    for k in (0.125, 0.25, 0.5, 1.0):
        # Both sides at each radius, and the nearer root wins: the gap need not be monotone in
        # the edge (far below zero every value dies and the two tie again).
        roots = []
        for sgn in (-1.0, 1.0):
            e1 = edge + sgn * k * EDGE_SEARCH_R
            if (_gap_at(fn, deals, e1, today, cand) > 0) == (g0 > 0):
                continue
            lo, hi = edge, e1
            for _ in range(BISECT_STEPS):
                mid = 0.5 * (lo + hi)
                if (_gap_at(fn, deals, mid, today, cand) > 0) == (g0 > 0):
                    lo = mid
                else:
                    hi = mid
            roots.append(0.5 * (lo + hi))
        if roots:
            e_star = min(roots, key=lambda x: abs(x - edge))
            return e_star, abs(e_star - edge)
    return None, EDGE_SEARCH_R


def days_needed(sigma_day: float, delta_edge: float) -> int:
    """Distinct live days before the live edge is known to within the distance that would flip
    the decision: TIE_SE standard errors of a per-day mean R inside delta_edge.

        N = ceil((TIE_SE * sigma_day / delta_edge)^2)

    Days, not trades: one session's trades share one market and are not independent draws."""
    if not (delta_edge > 0 and math.isfinite(sigma_day)):
        return 10 ** 6
    return max(1, math.ceil((TIE_SE * sigma_day / delta_edge) ** 2))


def bet_sigma(edge_r: float, rr: float) -> float:
    """SD of one R outcome of a +rr/-1 bracket whose mean is edge_r: the per-day dispersion
    floor when the ledger has too few days to measure one."""
    p = min(max((1.0 + edge_r) / (1.0 + rr), 1e-6), 1.0 - 1e-6)
    return (1.0 + rr) * math.sqrt(p * (1.0 - p))


def robustness_gate(fn: Any, deals: list[dict[str, Any]], res: dict[str, Any],
                    prior_res: dict[str, Any]) -> dict[str, Any]:
    """May the derived value replace today's? Two-sided (GROWTH_GOVERNANCE Rules 1 and 2): the
    same three tests stand between the report and the money path whichever way the value moves.

      (a) the lane's live trades span at least N distinct days, N from `days_needed` at the
          distance between the live edge and the break-even edge where the two values tie;
      (b) the measurement covers at least half the lane's symbols/sleeves;
      (c) the E[log W] gap in the candidate's favour holds (> TIE_SE paired SEs) on BOTH the
          certificate/forward edge alone and the live-adjusted edge.

    Until all three pass, `adopt` is False and today's value is the one to run."""
    today = res.get("today")
    if res.get("status") != "OK":
        return {"adopt": False, "adopt_value": today,
                "reason": f"no move to adopt: {res.get('why') or res.get('status')}"}
    cand = float(res["derived"])
    inp = res.get("inputs") or {}
    edge = inp.get("edge") or {}
    e_live = float(edge.get("posterior_r") or 0.0)
    rr = float(inp.get("rr") or 1.5)
    measured_sd = edge.get("live_day_mean_sd")
    sigma = max(bet_sigma(e_live, rr),
                float(measured_sd) if isinstance(measured_sd, (int, float)) else 0.0)
    e_star, dist = break_even_edge(fn, deals, e_live, float(today or 0.0), cand)
    need_days = days_needed(sigma, dist)
    have_days = int(edge.get("live_days") or 0)
    a = {"pass": have_days >= need_days, "live_days": have_days, "days_needed": need_days,
         "break_even_edge_r": round(e_star, 5) if e_star is not None else
         f"beyond +/-{EDGE_SEARCH_R:g}R of the live edge",
         "edge_distance_r": round(dist, 5), "sigma_day_r": round(sigma, 5),
         "sigma_basis": ("max(bet SD at the live edge, measured per-day SD)"
                         if isinstance(measured_sd, (int, float)) else
                         "bet SD at the live edge (fewer than 2 live days to measure one)")}
    cov = inp.get("coverage") or {}
    n_m, n_of = int(cov.get("measured") or 0), int(cov.get("of") or 0)
    b = {"pass": n_of > 0 and 2 * n_m >= n_of, "measured": n_m, "of": n_of,
         "unit": cov.get("unit")}
    g_live = res.get("gap_vs_today") or {}
    g_prior = prior_res.get("gap_vs_today") or {}
    c = {"pass": bool(g_live.get("holds")) and bool(g_prior.get("holds")),
         "live_adjusted": g_live, "certificate_only": g_prior}
    adopt = a["pass"] and b["pass"] and c["pass"]
    fails = [f"(a) {have_days} live day(s) of {need_days} needed" if not a["pass"] else "",
             f"(b) measured on {n_m} of {n_of} ({cov.get('unit')})" if not b["pass"] else "",
             "(c) the gap does not hold on the certificate-only edge" if not g_prior.get("holds")
             else ("(c) the gap does not hold on the live-adjusted edge"
                   if not g_live.get("holds") else "")]
    return {"adopt": adopt, "adopt_value": cand if adopt else today,
            "direction": ("less_aggressive" if res.get("less_aggressive_than_today")
                          else "more_aggressive"),
            "reason": ("all three robustness tests pass" if adopt else
                       "evidence-pending, today's value holds: "
                       + "; ".join(x for x in fails if x)),
            "a_live_days": a, "b_coverage": b, "c_gap_on_both_edges": c}


def derive() -> dict[str, Any]:
    deals = _read_jsonl(LEDGER)
    doc: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "objective": "max ruin-counted E[log W] s.t. P(equity <= death_line within horizon) "
                     "<= eps (kelly_survival.ruin_counted_elog)",
        "death_line": DEATH_LINE, "eps_death": EPS_DEATH, "horizon_days": HORIZON,
        "n_paths": N_PATHS,
        "provenance": {"module": "desks/mt5/research/stop_geometry_derivation.py",
                       "inputs": [_rel(p) for p in
                                  (SLEEVES, LEDGER, SURVIVORS, COST_SURFACE, BARS)]},
        "aggressiveness_note": "neither constant changes EUR at risk per trade (promoted_lot "
                               "sizes against the stop sent); lower m and higher tau keep the "
                               "larger lot per EUR of risk",
    }
    doc["MIN_STOP_SPREAD_MULT"] = derive_min_stop_spread_mult(deals)
    doc["ENTRY_DRIFT_TOL_FRAC"] = derive_entry_drift_tol_frac(deals)
    # SENSITIVITY: the same solve on the certified/forward prior alone, before the live ledger
    # moves it. When the two disagree, the live evidence is what moved the number, and the
    # reader should know how few trades that was (`inputs.edge.live_n`).
    for k, fn in (("MIN_STOP_SPREAD_MULT", derive_min_stop_spread_mult),
                  ("ENTRY_DRIFT_TOL_FRAC", derive_entry_drift_tol_frac)):
        main_derived = doc[k].get("derived")
        alt = fn(deals, prior_only=True,
                 against=float(main_derived) if isinstance(main_derived, (int, float)) else None)
        doc[k]["prior_only"] = {"status": alt.get("status"), "derived": alt.get("derived"),
                                "why": alt.get("why"),
                                "gap_vs_today_of_the_live_derived": alt.get("gap_vs_today"),
                                "edge_r": ((alt.get("inputs") or {}).get("edge") or {})
                                .get("posterior_r")}
        # THE ROBUSTNESS GATE: what the money path may run. The derived value is PUBLISHED
        # either way; it replaces today's only when this says adopt.
        doc[k]["robustness"] = robustness_gate(fn, deals, doc[k], alt)
        doc[k]["adopt"] = doc[k]["robustness"]["adopt"]
        doc[k]["adopt_value"] = doc[k]["robustness"]["adopt_value"]
    states = [doc[k].get("status", "") for k in ("MIN_STOP_SPREAD_MULT", "ENTRY_DRIFT_TOL_FRAC")]
    # SOLVED covers "today's value is optimal within noise": the solve ran and answered.
    solved = {"OK", "TODAY_OPTIMAL_WITHIN_NOISE"}
    doc["status"] = "OK" if all(s in solved for s in states) else (
        "PARTIAL" if any(s in solved for s in states) else "UNMEASURED")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = derive()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    tmp.replace(a.out)
    for k in ("MIN_STOP_SPREAD_MULT", "ENTRY_DRIFT_TOL_FRAC"):
        r = doc[k]
        print(f"{k}: {r.get('status')} derived={r.get('derived')} today={r.get('today')} "
              f"less_aggressive={r.get('less_aggressive_than_today')} adopt={r.get('adopt')} "
              f"({(r.get('robustness') or {}).get('reason')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
