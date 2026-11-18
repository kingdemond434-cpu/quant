"""THE UNKNOWN-UNKNOWN LANE: what moves on the desk's own bars that no family explains.

WHY THIS EXISTS (build check 2026-11-18, row 20, "Unknown-unknown research org")

Every generator on the desk starts from a mechanism somebody named: a family, a driver set, a
claim, a source. That is a search bounded by imagination. This one starts from the other end. It
takes each hypothesis-lane symbol's hourly returns, removes everything the desk ALREADY knows how
to say about them, and looks at what is left:

    r_t = a + b_mkt * MKT_t + b_cls * CLASS_t + sum_f c_f * EXPOSURE_f,t + eps_t

  MKT_t        the equal-weight mean hourly log return of every OTHER hypothesis-lane symbol
               (leave-one-out, so a symbol never explains itself).
  CLASS_t      the same mean inside the symbol's peer class (`universe_policy.peer_class`), USD
               pairs oriented as the non-USD currency in dollars, also leave-one-out.
  EXPOSURE_f,t the net position family f holds on bar t at its registered defaults: every price-
               only family (`miner_candidate_compiler._FAMILY_VOCAB` that `mt5desk.families`
               registers) is run on the symbol's bars, and a signal stamped at bar s holds its
               side over bars s+1 .. s+ttl. The return of bar t is explained only by positions
               opened on or before bar t-1.

The betas are CAUSAL: `mt5desk.causal_residual` fits beta[t] on rows [t-BETA_WIN, t-1], the same
primitive `family_cross_asset_residual` and `factor_residual_engine` use. eps_t is standardised by
the residual's own trailing sd over [t-Z_WIN, t-1]. Nothing at bar t is priced by anything that
has seen bar t's outcome; `test_residual_anomaly_scan` asserts it by altering the future.

WHAT IT LOOKS FOR in eps, per symbol:
  SHOCKS        |z| >= EXTREME_Z, against the count a normal residual would give.
  PERSISTENCE   lag 1..3 autocorrelation of z, and Ljung-Box over five lags.
  AFTER-SHOCK   the signed cumulative residual over the next h bars after a |z| >= SHOCK_Z bar,
                non-overlapping: positive is continuation, negative is reversion.
  CLOCK         mean z by UTC hour; an hour its neighbour cancels is a quote bounce (spread or
                rollover artefact), reported and never donated.
and across symbols:
  CO-MOVEMENT   pairwise correlation of z, judged against the demeaning floor -1/(N-1) (L0044:
                removing a common factor manufactures negative correlation), clustered as the
                connected components of pairs above CLUSTER_RHO. Two FX pairs that share a
                currency leg co-move for a reason any desk can name: reported, never donated.

A PATTERN IS DONATED ONLY WHEN IT RECURS AND SURVIVES ITS OWN SEARCH. Recurs: the sample is cut
in two halves and both carry the same sign. Survives: its full-sample t, deflated by the expected
maximum of every test this pass ran (`multiplicity.deflate_t`), clears DONATE_DEFLATED_T. Every
test is counted in `trials`, and the report carries every pattern whether or not it was donated.

WHAT A DONATION IS. A row in `data/intelligence/residual_scan/discoveries_<stamp>.json` in the
shapes `miner_candidate_compiler` already compiles: `{"kind": "hypothesis", "family": ...,
"symbols": [...]}` (STRUCTURED_HYPOTHESIS) for a one-symbol pattern mapped to the nearest
registered executable, and `{"kind": "anomaly", "family_hint": "cross_asset_residual", "against":
peer, "horizon": h}` (STRUCTURED_CROSS_ASSET_RESIDUAL) for a residual co-movement pair. The map
from pattern to family is fixed and stated in PATTERN_FAMILY; a pattern with no registered
executable is reported and not donated. The gauntlet's ten gates decide; this module admits
nothing.

NEIGHBOURS, AND WHY THIS IS NOT ONE OF THEM. `residual_hunt` hunts the WORLD MODEL's epsilon;
`factor_residual_engine` the residual against NAMED economic drivers; `residual_search` the
BOOK's trade residual; `unknown_unknowns` raw price-space anomalies. None of them removes the
desk's own families first, so none can say "this move is not something we already trade".

REPORT ONLY. Nothing here is read by the gateway, the promoter, admission, the allocator or any
sizing path. UNMEASURED is a verdict (L1.28a): a symbol with too few bars, a family that raised,
or a symbol the budget did not reach is named in the report, never silently absent.

    python desks/mt5/research/residual_anomaly_scan.py [--budget-s 240] [--dry-run]
        -> desks/mt5/reports/UNEXPLAINED_RESIDUALS.json
        -> desks/mt5/data/intelligence/residual_scan/discoveries_<stamp>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "residual_scan"
UNIVERSE = BASE / "data" / "universe"
REPORT = BASE / "reports" / "UNEXPLAINED_RESIDUALS.json"
DONATIONS = BASE / "data" / "intelligence" / SEAT
SEEN = BASE / "data" / "residual_scan_seen.json"

#: Bars read per symbol (the most recent). ~4 months of H1: enough for BETA_WIN + Z_WIN of warm-up
#: and two halves of residual, small enough that the whole universe fits the build box's memory.
MAX_BARS = 3_000
#: Rows each causal beta is fitted on (~1 month of H1).
BETA_WIN = 500
#: Rows the residual's trailing sd is measured on before it standardises bar t.
Z_WIN = 500
#: Standardised residuals a symbol needs before any statistic is read from it.
MIN_RESID_N = 600
SHOCK_Z = 3.0
EXTREME_Z = 4.0
DRIFT_H: tuple[int, ...] = (1, 3, 6, 12)
AC_LAGS: tuple[int, ...] = (1, 2, 3)
LB_LAGS = 5
#: Residual correlation above which two symbols share a co-movement cluster.
CLUSTER_RHO = 0.35
#: Overlapping standardised residuals a pair needs before its correlation is read.
MIN_OVERLAP = 300
#: Deflated |t| a recurring pattern must clear to be donated.
DONATE_DEFLATED_T = 1.0
MAX_DONATIONS = 12
MAX_SEEN = 5_000
#: The horizon written onto a co-movement donation. NOT MEASURED: one trading day, stated as such
#: on the row, because the compiler requires a horizon and the scan measures correlation, not a
#: reversion time.
PAIR_HORIZON = 24
#: An hour whose neighbour's mean residual cancels it to within this share is a quote bounce.
BOUNCE_FRAC = 0.5
#: Other members a peer class needs among the scanned symbols before it is a regressor.
MIN_CLASS_PEERS = 2
#: Share of the budget the family-exposure stage may spend before later symbols are regressed on
#: market and class factors only (named in the report as `families_unmeasured`).
FAMILY_STAGE_SHARE = 0.6

#: Pattern -> the registered price-only family that is its nearest executable statement. Fixed,
#: so the map can be read and argued with; a pattern absent here is reported and not donated.
PATTERN_FAMILY: dict[str, str] = {
    "after_shock_reversion": "mean_reversion_bollinger",
    "after_shock_continuation": "momentum_volgate",
    "autocorr_reversion": "mean_reversion_rsi",
    "autocorr_continuation": "trend_ma_cross",
}
#: UTC hours whose residual drift has a registered session executable. The Asia hours start at
#: 02:00, after the 21:00-01:00 rollover whose wide spreads put quote artefacts in the residual.
HOUR_FAMILY: dict[int, str] = {**{h: "asia_momentum" for h in range(2, 7)},
                               15: "london_close_momentum", 16: "london_close_momentum"}


# ------------------------------------------------------------------------------------- inputs

def hypothesis_symbols(universe_dir: Path = UNIVERSE) -> list[str]:
    """Symbols with H1 bars whose lane is the hypothesis lane. Never a symbol list."""
    import universe_policy as up
    out = []
    for p in sorted(universe_dir.glob("*_H1.parquet")):
        sym = p.stem.removesuffix("_H1")
        if up.lane(sym) == up.HYPOTHESIS:
            out.append(sym)
    return out


def load_bars(symbol: str, universe_dir: Path = UNIVERSE, max_bars: int = MAX_BARS
              ) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(universe_dir / f"{symbol}_H1.parquet")
    except Exception:
        return None
    if not isinstance(df.index, pd.DatetimeIndex) or "close" not in df:
        return None
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.tail(max_bars)


def regressor_families() -> tuple[dict[str, Callable[..., Any]], list[str]]:
    """{name: func} for every price-only family the desk registers, and the vocabulary names it
    does not (reported as not regressed, never silently dropped)."""
    from mt5desk import families as fam_mod
    try:
        from miner_candidate_compiler import _FAMILY_VOCAB
    except ImportError:                                    # pragma: no cover
        from research.miner_candidate_compiler import _FAMILY_VOCAB
    reg = fam_mod.FAMILY_REGISTRY
    have = {n: reg[n]["func"] for n in _FAMILY_VOCAB if n in reg}
    return have, sorted(n for n in _FAMILY_VOCAB if n not in reg)


def family_exposure(df: pd.DataFrame, func: Callable[..., Any]) -> np.ndarray:
    """Net side family `func` holds on each bar of `df`, at its defaults.

    A signal stamped at bar s is decided on bar s's close and enters at the next open, so it
    holds over bars s+1 .. s+ttl. The return of bar t (close[t-1] -> close[t]) is therefore only
    ever explained by signals stamped at or before t-1.
    """
    n = len(df)
    diff = np.zeros(n + 1)
    idx = df.index
    for sig in func(df) or []:
        side = int(getattr(sig, "side", 0) or 0)
        if side == 0:
            continue
        p = int(idx.searchsorted(pd.Timestamp(sig.time), side="left"))
        if p >= n or idx[p] != pd.Timestamp(sig.time):
            continue
        ttl = max(1, int(getattr(sig, "ttl_bars", 1) or 1))
        lo, hi = p + 1, min(n, p + 1 + ttl)
        if lo < hi:
            diff[lo] += side
            diff[hi] -= side
    return np.cumsum(diff)[:n]


def factor_panel(rets: dict[str, pd.Series], classes: dict[str, str | None],
                 orient: dict[str, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(sum, count) panels over the union clock: column MKT and one per peer class."""
    frame = pd.DataFrame(rets)
    sums, counts = {}, {}
    finite = frame.notna()
    sums["MKT"] = frame.fillna(0.0).sum(axis=1)
    counts["MKT"] = finite.sum(axis=1)
    for klass in sorted({c for c in classes.values() if c}):
        cols = [s for s in frame.columns if classes.get(s) == klass]
        sub = frame[cols] * pd.Series({s: orient.get(s, 1) for s in cols})
        sums[f"CLS:{klass}"] = sub.fillna(0.0).sum(axis=1)
        counts[f"CLS:{klass}"] = sub.notna().sum(axis=1)
    return pd.DataFrame(sums), pd.DataFrame(counts)


def leave_one_out(sums: pd.DataFrame, counts: pd.DataFrame, col: str, own: pd.Series,
                  weight: int = 1) -> pd.Series:
    """Mean of `col` without `own` (oriented by `weight`); NaN when fewer than two others."""
    s = sums[col].reindex(own.index)
    c = counts[col].reindex(own.index)
    mine = own.fillna(0.0) * weight
    k = c - own.notna().astype(int)
    out = (s - mine) / k.where(k >= 2)
    return out


# ------------------------------------------------------------------------------- the residual

def standardised_residual(y: np.ndarray, X: np.ndarray, beta_win: int = BETA_WIN,
                          z_win: int = Z_WIN) -> tuple[np.ndarray, np.ndarray]:
    """(eps, z): causal residual and its standardisation by the PRIOR z_win residuals' sd."""
    from mt5desk.causal_residual import causal_residual
    eps = causal_residual(y, X, beta_win)
    sd = pd.Series(eps).rolling(z_win, min_periods=max(30, z_win // 2)).std().shift(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = eps / sd.to_numpy()
    z[~np.isfinite(z)] = np.nan
    return eps, z


def residual_for(symbol: str, df: pd.DataFrame, sums: pd.DataFrame, counts: pd.DataFrame,
                 klass: str | None, orient: int,
                 families: dict[str, Callable[..., Any]] | None,
                 note: dict[str, Any], class_peers: int = 0) -> pd.Series | None:
    """The standardised residual series of one symbol, indexed by its own bar clock."""
    close = df["close"].astype(float)
    r = np.log(close).diff()
    cols: dict[str, np.ndarray] = {}
    cols["MKT"] = leave_one_out(sums, counts, "MKT", r).to_numpy()
    # The class column is chosen by MEMBERSHIP, never by how often it was defined over the whole
    # sample: a class with fewer than MIN_CLASS_PEERS other members is not regressed at all.
    if klass and f"CLS:{klass}" in sums and class_peers >= MIN_CLASS_PEERS:
        cols[f"CLS:{klass}"] = leave_one_out(sums, counts, f"CLS:{klass}", r,
                                             weight=orient).to_numpy()
    failed: dict[str, str] = {}
    used: list[str] = []
    for name, func in (families or {}).items():
        try:
            e = family_exposure(df, func)
        except Exception as exc:                          # a family that raises is named
            failed[name] = f"{type(exc).__name__}: {str(exc)[:80]}"
            e = np.zeros(len(df))          # the column set stays fixed (see below)
        # A family that never fires here is KEPT as a zero column. Dropping it because the whole
        # sample is silent would let a signal that fires only in the future change the model
        # every earlier residual was fitted with -- a lookahead in the column set itself.
        cols[f"FAM:{name}"] = e
        if np.count_nonzero(e):
            used.append(name)
    # A factor that is undefined on a bar (fewer than two peers trading) is absent, not zero: the
    # row is left out of the window's sums by `rolling_betas` rather than read as a flat market.
    X = np.column_stack(list(cols.values()))
    _eps, z = standardised_residual(r.to_numpy(), X)
    note.update(regressors=list(cols), families_used=used, families_failed=failed)
    return pd.Series(z, index=df.index, name=symbol)


# ------------------------------------------------------------------------------- statistics

def _t(mean: float, sd: float, n: int) -> float:
    if n < 2 or not (sd > 0) or not math.isfinite(mean):
        return 0.0
    return float(mean / (sd / math.sqrt(n)))


def _halves_agree(values: np.ndarray) -> bool:
    v = values[np.isfinite(values)]
    if v.size < 8:
        return False
    a, b = v[: v.size // 2], v[v.size // 2:]
    return bool(np.sign(a.mean()) == np.sign(b.mean()) != 0)


def autocorr(z: np.ndarray, lag: int) -> tuple[float, int]:
    a, b = z[:-lag], z[lag:]
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30:
        return float("nan"), int(m.sum())
    return float(np.corrcoef(a[m], b[m])[0, 1]), int(m.sum())


def symbol_stats(z: pd.Series) -> dict[str, Any]:
    """Every per-symbol statistic, with the number of tests it ran in `tests`."""
    zz = z.to_numpy(dtype=float)
    fin = np.isfinite(zz)
    n = int(fin.sum())
    out: dict[str, Any] = {"n": n, "patterns": [], "tests": 0}
    if n < MIN_RESID_N:
        out["state"] = f"UNMEASURED: {n} standardised residuals < {MIN_RESID_N}"
        return out
    out["state"] = "MEASURED"
    zf = zz[fin]
    p_ext = math.erfc(EXTREME_Z / math.sqrt(2))
    n_ext = int((np.abs(zf) >= EXTREME_Z).sum())
    out["shocks"] = {"extreme_z": EXTREME_Z, "count": n_ext,
                     "normal_expectation": round(n * p_ext, 3),
                     "excess_ratio": round(n_ext / max(n * p_ext, 1e-9), 1),
                     "kurtosis_excess": round(float(pd.Series(zf).kurt()), 2)}
    top = z[fin].abs().sort_values(ascending=False).head(5)
    out["shocks"]["largest"] = [{"at": t.isoformat(), "z": round(float(z[t]), 2)}
                                for t in top.index]

    # PERSISTENCE: lag autocorrelations and Ljung-Box.
    acs = {}
    q = 0.0
    for lag in range(1, LB_LAGS + 1):
        rho, m = autocorr(zz, lag)
        if math.isfinite(rho):
            q += rho * rho / max(n - lag, 1)
        if lag in AC_LAGS:
            acs[lag] = (rho, m)
    q *= n * (n + 2)
    out["ljung_box_q5"] = round(q, 2)
    out["autocorr"] = {str(k): round(v[0], 4) if math.isfinite(v[0]) else None
                       for k, v in acs.items()}
    for lag, (rho, m) in acs.items():
        out["tests"] += 1
        if not math.isfinite(rho):
            continue
        a, b = zz[:-lag], zz[lag:]
        prod = a * b
        out["patterns"].append({
            "pattern": "autocorr_" + ("continuation" if rho > 0 else "reversion"),
            "lag": lag, "effect": round(rho, 4), "t": round(rho * math.sqrt(m), 2), "n": m,
            "recurs": _halves_agree(prod)})

    # AFTER-SHOCK: signed forward cumulative residual, non-overlapping.
    shock_pos = np.flatnonzero(fin & (np.abs(np.nan_to_num(zz)) >= SHOCK_Z))
    for h in DRIFT_H:
        out["tests"] += 1
        vals, last = [], -10**9
        for p in shock_pos:
            if p - last < h or p + h >= len(zz):
                continue
            fwd = zz[p + 1: p + 1 + h]
            if not np.isfinite(fwd).all():
                continue
            vals.append(float(np.sign(zz[p]) * fwd.sum() / math.sqrt(h)))
            last = p
        v = np.asarray(vals)
        if v.size < 12:
            continue
        mean = float(v.mean())
        out["patterns"].append({
            "pattern": "after_shock_" + ("continuation" if mean > 0 else "reversion"),
            "horizon": h, "effect": round(mean, 4), "t": round(_t(mean, float(v.std(ddof=1)),
                                                                   v.size), 2),
            "n": int(v.size), "recurs": _halves_agree(v)})

    # CLOCK: mean z by UTC hour. A significant hour whose neighbour carries the opposite mean of
    # about the same size is a QUOTE BOUNCE -- a bid that dips while the rollover spread is wide
    # and comes back the next bar -- not a drift anybody can earn; it is reported as such.
    hours = z.index.hour
    by_hour: dict[int, np.ndarray] = {hr: zz[(hours == hr) & fin] for hr in range(24)}
    means = {hr: float(v.mean()) if v.size >= 40 else float("nan") for hr, v in by_hour.items()}
    for hr, sel in by_hour.items():
        out["tests"] += 1
        mean = means[hr]
        if not math.isfinite(mean):
            continue
        t = _t(mean, float(sel.std(ddof=1)), sel.size)
        if abs(t) < 2.0:
            continue
        pat: dict[str, Any] = {"pattern": "hour_drift_" + ("up" if mean > 0 else "down"),
                               "hour_utc": hr, "effect": round(mean, 4), "t": round(t, 2),
                               "n": int(sel.size), "recurs": _halves_agree(sel)}
        prev, nxt = means[(hr - 1) % 24], means[(hr + 1) % 24]
        nbs = [m for m in (prev, nxt) if math.isfinite(m)]
        # Cancelled by one neighbour, or by the two together (a rollover distorts several bars).
        cancelled = any(m * mean < 0 and abs(mean + m) < BOUNCE_FRAC * abs(mean) for m in nbs)
        cancelled |= (any(m * mean < 0 for m in nbs)
                      and abs(mean + sum(nbs)) < BOUNCE_FRAC * abs(mean))
        if cancelled:
            pat["known_structure"] = (f"quote bounce: neighbouring hours' mean z "
                                      f"{prev:+.2f} / {nxt:+.2f} cancel it -- a spread or "
                                      "rollover artefact, not a drift")
        out["patterns"].append(pat)
    return out


def shared_leg(a: str, b: str) -> str | None:
    """The currency two six-letter pairs share, or None. Two pairs on one currency co-move for a
    reason every FX desk can name; that is known structure, reported and never donated as an
    unknown."""
    import universe_policy as up
    fx = ("fx_usd", "fx_cross")
    if up.peer_class(a) not in fx or up.peer_class(b) not in fx:
        return None                    # XAUUSD and XAGUSD share a quote, not a currency bet
    la = {a[:3].upper(), a[3:].upper()} if len(a) == 6 and a.isalpha() else set()
    lb = {b[:3].upper(), b[3:].upper()} if len(b) == 6 and b.isalpha() else set()
    common = sorted(la & lb)
    return common[0] if common else None


def comovement(zs: dict[str, pd.Series]) -> dict[str, Any]:
    """Pairwise residual correlation, judged against -1/(N-1), clustered above CLUSTER_RHO."""
    if len(zs) < 3:
        return {"state": f"UNMEASURED: {len(zs)} symbols with a residual < 3", "pairs": [],
                "clusters": [], "tests": 0}
    frame = pd.DataFrame(zs)
    corr = frame.corr(min_periods=MIN_OVERLAP)
    overlap = frame.notna().astype(int).T @ frame.notna().astype(int)
    syms = list(frame.columns)
    nsym = len(syms)
    floor = -1.0 / (nsym - 1)
    pairs, tests = [], 0
    adj: dict[str, set[str]] = {s: set() for s in syms}
    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            rho = corr.at[a, b]
            if not np.isfinite(rho):
                continue
            tests += 1
            n = int(overlap.at[a, b])
            row = {"a": a, "b": b, "rho": round(float(rho), 4), "n": n,
                   "t": round(float((rho - floor) * math.sqrt(n)), 2)}
            if rho >= CLUSTER_RHO:
                adj[a].add(b)
                adj[b].add(a)
                ha = frame[[a, b]].dropna()
                half = len(ha) // 2
                r1 = float(ha.iloc[:half].corr().iat[0, 1])
                r2 = float(ha.iloc[half:].corr().iat[0, 1])
                row["recurs"] = bool(r1 > floor and r2 > floor and min(r1, r2) > 0)
                row["halves"] = [round(r1, 4), round(r2, 4)]
                leg = shared_leg(a, b)
                if leg:
                    row["known_structure"] = f"shared currency leg {leg}"
                pairs.append(row)
    clusters, seen = [], set()
    for s in syms:
        if s in seen or not adj[s]:
            continue
        stack, comp = [s], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack.extend(adj[x] - comp)
        seen |= comp
        clusters.append(sorted(comp))
    pairs.sort(key=lambda r: -r["rho"])
    mean_off = float(np.nanmean(corr.where(~np.eye(nsym, dtype=bool)).to_numpy()))
    return {"state": "MEASURED", "symbols": nsym, "demeaning_floor": round(floor, 4),
            "mean_offdiag_rho": round(mean_off, 4), "cluster_rho": CLUSTER_RHO,
            "pairs": pairs, "clusters": clusters, "tests": tests}


# ----------------------------------------------------------------------------- the donations

def _key(*parts: Any) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20]


def donation_rows(per_symbol: dict[str, dict[str, Any]], co: dict[str, Any], trials: int,
                  seen: set[str], max_rows: int = MAX_DONATIONS) -> tuple[list[dict], list[dict]]:
    """(rows to donate, every eligible pattern with its disposition)."""
    from multiplicity import deflate_t
    eligible: list[dict[str, Any]] = []
    for sym, st in per_symbol.items():
        for p in st.get("patterns", []):
            td = deflate_t(abs(float(p["t"])), trials)
            if not p.get("recurs") or td < DONATE_DEFLATED_T:
                continue
            family = (PATTERN_FAMILY.get(p["pattern"])
                      or (HOUR_FAMILY.get(p["hour_utc"]) if "hour_utc" in p else None))
            eligible.append({"symbol": sym, **p, "t_deflated": round(td, 2),
                             "family": family})
    for pr in co.get("pairs", []):
        td = deflate_t(abs(float(pr["t"])), trials)
        if pr.get("recurs") and td >= DONATE_DEFLATED_T:
            eligible.append({"symbol": pr["a"], "against": pr["b"], "pattern": "comovement",
                             "effect": pr["rho"], "t": pr["t"], "n": pr["n"],
                             "t_deflated": round(td, 2), "family": "cross_asset_residual",
                             **({"known_structure": pr["known_structure"]}
                                if pr.get("known_structure") else {})})
    eligible.sort(key=lambda e: -e["t_deflated"])
    rows: list[dict[str, Any]] = []
    for e in eligible:
        if e.get("known_structure"):
            e["disposition"] = f"REPORTED: {e['known_structure']}; not an unknown"
            continue
        if e["family"] is None:
            e["disposition"] = "REPORTED: no registered executable states this pattern"
            continue
        axis = e.get("lag") or e.get("horizon") or e.get("hour_utc") or e.get("against")
        k = _key(e["symbol"], e["pattern"], axis, e["family"])
        if k in seen:
            e["disposition"] = "SEEN: donated on an earlier pass"
            continue
        if len(rows) >= max_rows:
            e["disposition"] = f"DEFERRED: {max_rows} donations per pass"
            continue
        seen.add(k)
        e["disposition"] = "DONATED"
        evidence = {k2: e[k2] for k2 in ("pattern", "lag", "horizon", "hour_utc", "effect", "t",
                                         "t_deflated", "n") if k2 in e}
        if e["pattern"] == "comovement":
            rows.append({
                "kind": "anomaly", "family_hint": "cross_asset_residual",
                "symbol": e["symbol"], "symbols": [e["symbol"]], "against": e["against"],
                "horizon": PAIR_HORIZON, "corr": e["effect"], "source": SEAT,
                "mechanism_status": "UNNAMED",
                "title": (f"{e['symbol']} and {e['against']}: residual co-movement "
                          f"rho={e['effect']} after market, class and family factors"),
                "text": (f"After removing the market, peer-class and every registered price-only "
                         f"family's exposure, {e['symbol']} and {e['against']} still co-move "
                         f"(rho {e['effect']}, n {e['n']}, recurs in both halves, deflated t "
                         f"{e['t_deflated']} over {trials} tests). Horizon {PAIR_HORIZON} is one "
                         "trading day, not measured. An observation for the gauntlet."),
                "residual_scan": evidence, "trials": trials})
        else:
            rows.append({
                "kind": "hypothesis", "family": e["family"], "symbols": [e["symbol"]],
                "source": SEAT,
                "title": (f"{e['symbol']}: unexplained residual {e['pattern']} "
                          f"(t {e['t']}, deflated {e['t_deflated']})"),
                "text": (f"{e['symbol']}'s hourly residual after market, peer-class and family "
                         f"factors shows {e['pattern'].replace('_', ' ')} (effect {e['effect']}, "
                         f"n {e['n']}, both halves agree, {trials} tests this pass). "
                         f"{e['family']} at its defaults is the nearest registered executable; "
                         "a hypothesis for the ten gates, not a claim."),
                "residual_scan": evidence, "trials": trials})
    return rows, eligible


# ------------------------------------------------------------------------------------- build

def scan(symbols: Iterable[str], *, budget_s: float = 240.0, universe_dir: Path = UNIVERSE,
         families: dict[str, Callable[..., Any]] | None = None,
         max_bars: int = MAX_BARS) -> tuple[dict[str, pd.Series], dict[str, Any]]:
    """Standardised residuals for each symbol the budget reaches, and the per-symbol notes."""
    import universe_policy as up
    t0 = time.monotonic()
    syms = list(symbols)
    bars: dict[str, pd.DataFrame] = {}
    notes: dict[str, Any] = {}
    for s in syms:
        df = load_bars(s, universe_dir, max_bars)
        if df is None or len(df) < BETA_WIN + 50:
            notes[s] = {"state": "UNMEASURED: bars unreadable or shorter than "
                                 f"{BETA_WIN + 50}"}
            continue
        bars[s] = df
    rets = {s: np.log(df["close"].astype(float)).diff() for s, df in bars.items()}
    classes = {s: up.peer_class(s) for s in bars}
    orient = {s: up.usd_orientation(s) if classes[s] == "fx_usd" else 1 for s in bars}
    sums, counts = factor_panel(rets, classes, orient)
    zs: dict[str, pd.Series] = {}
    fam_deadline = t0 + budget_s * FAMILY_STAGE_SHARE
    for s, df in bars.items():
        if time.monotonic() - t0 > budget_s * 0.85:
            notes[s] = {"state": "UNMEASURED: budget spent before this symbol"}
            continue
        note: dict[str, Any] = {"peer_class": classes[s]}
        use_fam = families if time.monotonic() < fam_deadline else None
        if families and use_fam is None:
            note["families_unmeasured"] = "family stage budget spent; market and class only"
        peers = sum(1 for o in bars if o != s and classes[o] and classes[o] == classes[s])
        if classes[s] and peers < MIN_CLASS_PEERS:
            note["class_factor"] = (f"not regressed: {peers} other {classes[s]} member(s) with "
                                    f"bars < {MIN_CLASS_PEERS}")
        z = residual_for(s, df, sums, counts, classes[s], orient[s], use_fam, note,
                         class_peers=peers)
        if z is not None:
            zs[s] = z
        notes[s] = note
    return zs, notes


def _rotate(symbols: list[str], now: datetime) -> list[str]:
    """Start at a different symbol each hour so a truncated pass is not the same prefix."""
    if not symbols:
        return symbols
    k = (now.toordinal() * 24 + now.hour) % len(symbols)
    return symbols[k:] + symbols[:k]


def _load_seen() -> set[str]:
    try:
        doc = json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    keys = doc.get("keys") if isinstance(doc, dict) else None
    return {str(k) for k in keys} if isinstance(keys, list) else set()


def build(budget_s: float = 240.0, *, universe_dir: Path = UNIVERSE,
          symbols: list[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]],
                                                     set[str]]:
    now = datetime.now(UTC)
    t0 = time.monotonic()
    syms = _rotate(symbols if symbols is not None else hypothesis_symbols(universe_dir), now)
    families, not_registered = regressor_families()
    zs, notes = scan(syms, budget_s=budget_s, universe_dir=universe_dir, families=families)
    per_symbol: dict[str, dict[str, Any]] = {}
    trials = 0
    for s, z in zs.items():
        st = symbol_stats(z)
        st.update(notes.get(s, {}))
        trials += int(st.get("tests", 0))
        per_symbol[s] = st
    co = comovement({s: z for s, z in zs.items() if per_symbol[s].get("state") == "MEASURED"})
    trials += int(co.get("tests", 0))
    seen = _load_seen()
    rows, eligible = donation_rows(per_symbol, co, trials, seen)
    unmeasured = {s: n["state"] for s, n in notes.items()
                  if str(n.get("state", "")).startswith("UNMEASURED")}
    for s, st in per_symbol.items():
        if str(st.get("state", "")).startswith("UNMEASURED"):
            unmeasured[s] = st["state"]
    measured = [s for s, st in per_symbol.items() if st.get("state") == "MEASURED"]
    ranked = sorted(measured, key=lambda s: -float(per_symbol[s].get("ljung_box_q5", 0.0)))
    report = {
        "at": now.isoformat(timespec="seconds"),
        "state": "MEASURED" if measured else "UNMEASURED: no symbol produced a residual",
        "model": {"target": "hourly log return", "regressors": ["MKT (leave-one-out)",
                  "peer class (leave-one-out, USD pairs oriented)",
                  "net exposure of each registered price-only family at defaults, lagged"],
                  "beta": f"causal rolling OLS with intercept, rows [t-{BETA_WIN}, t-1]",
                  "standardised_by": f"trailing sd of the residual over [t-{Z_WIN}, t-1]",
                  "bars_per_symbol": MAX_BARS},
        "families_regressed": sorted(families),
        "families_not_regressed": {n: "not in mt5desk.families.FAMILY_REGISTRY"
                                   for n in not_registered},
        "symbols_requested": len(syms), "symbols_measured": len(measured),
        "unmeasured": unmeasured,
        "trials": trials,
        "donate_rule": {"recurs": "same sign in both halves of the sample",
                        "deflated_t_min": DONATE_DEFLATED_T,
                        "deflation": "multiplicity.deflate_t against every test this pass ran"},
        "most_persistent": [{"symbol": s, "ljung_box_q5": per_symbol[s]["ljung_box_q5"],
                             "autocorr": per_symbol[s]["autocorr"]} for s in ranked[:10]],
        "per_symbol": per_symbol,
        "comovement": co,
        "eligible_patterns": eligible,
        "cells_donated": len(rows),
        "donations_to": f"data/intelligence/{SEAT}/",
        "consumer": ("desks/mt5/research/miner_candidate_compiler.py "
                     "(STRUCTURED_HYPOTHESIS, STRUCTURED_CROSS_ASSET_RESIDUAL)"),
        "sizing_reads": "none: a research report; no gateway, promoter, admission or allocator "
                        "path reads it",
        "elapsed_s": round(time.monotonic() - t0, 1),
        "budget_s": budget_s,
    }
    return report, rows, seen


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any], rows: list[dict[str, Any]], seen: set[str]) -> Path:
    if rows:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        _atomic_write(DONATIONS / f"discoveries_{stamp}.json",
                      json.dumps({"discoveries": rows}, indent=1, ensure_ascii=False))
    _atomic_write(SEEN, json.dumps({"keys": sorted(seen)[-MAX_SEEN:]}, indent=0))
    _atomic_write(REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return REPORT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="residuals no family explains")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    budget = args.budget_s
    with_env = os.environ.get("QUANT_LEG_BUDGET_S")
    if with_env:
        try:
            budget = min(budget, max(30.0, float(with_env) - 60.0))
        except ValueError:
            pass
    report, rows, seen = build(budget)
    target = "DRY RUN (nothing written)" if args.dry_run else str(write(report, rows, seen))
    print(f"UNEXPLAINED_RESIDUALS {report['at']}  measured {report['symbols_measured']}/"
          f"{report['symbols_requested']}  trials {report['trials']}  eligible "
          f"{len(report['eligible_patterns'])}  donated {report['cells_donated']}  "
          f"{report['elapsed_s']}s -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
