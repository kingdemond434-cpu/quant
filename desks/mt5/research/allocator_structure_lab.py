"""THE ALLOCATOR'S STRUCTURE LAB -- cleaned correlation, factor risk, neutralisation, the
diversification multiplier and crowding, each with an out-of-sample log-growth verdict.

    GAP_MAP rows (Max-growth / Growth allocator overhaul / Tier-1 gap H6), built 2026-11-13:
      "Random-matrix cleaning of the cert correlation matrix before the allocator solve"
      "Risk model and factor neutralisation (Barra users, DE Shaw, CN shops)"
      "Forecast/instrument diversification multiplier (Carver, AHL, Winton)"
      "H6 CROWDING AWARENESS"

WHAT IT READS (all box state, all optional; an absent input is UNMEASURED and named):
    data/pf_allocator_cache/daily_r.parquet   the allocator's own daily-R matrix (dates x sleeves)
    reports/pf_allocation.json                the book in heat (`book`) the allocator published
    data/universe/<SYM>_H1.parquet            bars for the observable style factors
    data/carry_state.json                     which side of each FX pair is paid carry
    data/cot/<ccy>.parquet                    CFTC positioning for the crowding pressure signal

WHAT IT WRITES:
    reports/ALLOCATOR_STRUCTURE.json          the whole measurement (schema below)
    data/allocator_structure_history.jsonl    one summary row per run, append-only
    data/pf_allocator_cache/structure_corr.npz  the four correlation estimates + names, for the
                                              allocator's challenger books and later consumers

    {
      "at", "status": MEASURED | PARTIAL | UNMEASURED, "why",
      "panel": {sleeves, days, held},
      "rmt": {n, t_eff, q, sigma2_bulk, mp_upper, n_signal_eigen, market_mode_share,
              effective_bets{sample,clipped,rie,lw}, condition_number{...}, ...},
      "factor_model": {factors, factor_vol_annual, book risk decomposition, top exposures},
      "neutralisation": {neutralised_against, turnover, book_exposure_before/after},
      "diversification": {dm_sample, dm_rie, heat_at_floor_risk, instrument_dm},
      "crowding": {by_family comomentum, top crowded sleeves, signals coverage},
      "proof": {baseline, rebalances, oos_days, by_variant{verdict, delta_elog_annual, t, ...},
                gmv_oos_var{sample, lw, clipped, rie}},
      "adoption": {input -> ADOPT | REJECT | INCONCLUSIVE | UNMEASURED}
    }

AUTHORITY. None, in this change, on purpose and by the desk's own rule (pf_allocator, "a new
state dimension takes capital authority by improving calibration or marginal E[log W] against the
existing gates -- never by being plausible, and never in the change that introduces it"). The
`adoption` block is the measured case for that later step; the allocator's contest can read
`structure_corr.npz` the moment a verdict says ADOPT.

    python desks/mt5/research/allocator_structure_lab.py --once [--budget-s 600]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import rmt  # noqa: E402
from libs.portfolio import structure as st  # noqa: E402

R = DESK / "reports"
DATA = DESK / "data"
OUT = R / "ALLOCATOR_STRUCTURE.json"
HISTORY = DATA / "allocator_structure_history.jsonl"
CACHE = DATA / "pf_allocator_cache"
PANEL = CACHE / "daily_r.parquet"
CORR_OUT = CACHE / "structure_corr.npz"
ALLOCATION = R / "pf_allocation.json"
UNIVERSE = DATA / "universe"
CARRY = DATA / "carry_state.json"
COT_DIR = DATA / "cot"

#: Bayesian shrink of the mean toward zero, the same constant the challenger books use.
BAYES_K = 250.0
#: Days a sleeve needs in the panel to enter the structure measurement at all.
MIN_SLEEVE_DAYS = 120
#: Bars older than this are not read for the factors (the panel itself is rarely longer).
FACTOR_YEARS = 6
FACTOR_SYMBOLS = tuple(dict.fromkeys(st.USD_BASE_LONG + st.USD_QUOTE + st.EQUITY + st.GOLD
                                     + st.OIL + st.JPY_CROSSES))
STYLE = ("trend", "carry", "reversal")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(path: Path, doc: Any) -> None:
    """Atomic, LF on every box (desks/mt5/.gitattributes stores *.json as eol=lf)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, default=_json_default)
    os.replace(tmp, path)


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.floating, np.integer)):
        v = o.item()
        return None if isinstance(v, float) and not math.isfinite(v) else v
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _clean(v: Any) -> Any:
    """Recursively replace non-finite floats with None so the JSON is strict."""
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return round(f, 8) if math.isfinite(f) else None
    if isinstance(v, np.integer):
        return int(v)
    return v


def _read_json(p: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(p.read_text("utf-8-sig"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------- inputs
def load_panel(path: Path = PANEL) -> tuple[pd.DataFrame | None, str]:
    if not path.exists():
        return None, f"{path.name} absent (the allocator has not cached its daily-R matrix here)"
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        # TYPE ONLY (#1137 audit MF2): pyarrow messages carry the box's absolute paths, and this
        # text is published into a committed artifact.
        return None, f"{path.name} unreadable: {type(exc).__name__}"
    df.index = pd.to_datetime([str(x) for x in df.index], utc=True, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    df = df.apply(pd.to_numeric, errors="coerce")
    keep = df.notna().sum(axis=0) >= MIN_SLEEVE_DAYS
    df = df.loc[:, keep]
    return df, f"{df.shape[1]} sleeves x {df.shape[0]} days (>= {MIN_SLEEVE_DAYS} days each)"


def load_book(path: Path = ALLOCATION) -> tuple[dict[str, float], float | None]:
    doc = _read_json(path) or {}
    book = doc.get("book") if isinstance(doc.get("book"), dict) else {}
    out = {str(k): float(v) for k, v in (book or {}).items()
           if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) > 0}
    total = sum(out.values()) if out else None
    return out, total


def load_closes(symbols: tuple[str, ...] = FACTOR_SYMBOLS, universe: Path = UNIVERSE
                ) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=365 * FACTOR_YEARS)
    for sym in symbols:
        p = universe / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        s = pd.Series(df["close"].to_numpy(float), index=idx).dropna()
        s = s[s.index >= cutoff]
        if s.empty:
            continue
        cols[sym] = s.groupby(s.index.normalize()).last()
    return pd.DataFrame(cols).sort_index()


def carry_signs(path: Path = CARRY) -> tuple[dict[str, int], dict[str, pd.Timestamp]]:
    """({pair: +1 long paid / -1 short paid}, {pair: first day the swap panel observed it}).
    A pair with no observation date is left out: its sign could only be painted backwards."""
    doc = _read_json(path) or {}
    out: dict[str, int] = {}
    since: dict[str, pd.Timestamp] = {}
    for sym, row in (doc.get("symbols") or {}).items():
        if not isinstance(row, dict) or str(row.get("asset_class", "")).lower() != "forex":
            continue
        try:
            lg = float((row.get("long") or {}).get("swap_money_per_lot_night"))
            sh = float((row.get("short") or {}).get("swap_money_per_lot_night"))
            first = pd.Timestamp(str(row.get("first_obs")))
        except (TypeError, ValueError):
            continue
        if first.tzinfo is None:
            first = first.tz_localize("UTC")
        if math.isfinite(lg) and math.isfinite(sh) and lg != sh:
            out[str(sym).upper()] = 1 if lg > sh else -1
            since[str(sym).upper()] = first.normalize()
    return out, since


def load_cot(cot_dir: Path = COT_DIR, as_of: datetime | None = None) -> dict[str, pd.Series]:
    """Each market's net speculative share, cut to what was PUBLISHED by `as_of` (default now):
    a COT report is valid on its Tuesday and released the following Friday, so the series is
    filtered through the declared `cot_fx` publication lag (libs/tiers/data_os) and the latest z
    this lab reports can never be a print the desk could not yet have read."""
    from libs.tiers.data_os import known_as_of

    out: dict[str, pd.Series] = {}
    if not cot_dir.exists():
        return out
    now = as_of or datetime.now(UTC)
    for p in sorted(cot_dir.glob("*.parquet")):
        try:
            out[p.stem.lower()] = known_as_of(st.cot_series(pd.read_parquet(p)), "cot_fx", now)
        except Exception:
            continue
    return out


def cot_for(symbol: str, cot: dict[str, pd.Series]) -> tuple[pd.Series | None, int]:
    """The COT series for a sleeve's market and the sign that maps the futures' long side onto the
    symbol (USDJPY is short the JPY future, so -1)."""
    s = symbol.upper()
    if s.startswith("XAU"):
        return cot.get("gold"), 1
    for key, stem in st.COT_MAP.items():
        if key in ("XAU",):
            continue
        if len(s) >= 6 and s[:3] == key and stem in cot:
            return cot[stem], 1
        if len(s) >= 6 and s[3:6] == key and stem in cot:
            return cot[stem], -1
        if s.startswith(key) and stem in cot:
            return cot[stem], 1
    return None, 1


# ---------------------------------------------------------------------------- measurement
def _mu_shrunk(tr: np.ndarray) -> np.ndarray:
    n = np.isfinite(tr).sum(axis=0).astype(float)
    mu = np.nan_to_num(np.nanmean(tr, axis=0), nan=0.0)
    out: np.ndarray = mu * (n / (n + BAYES_K))
    return out


def _sd(tr: np.ndarray) -> np.ndarray:
    sd = np.nan_to_num(np.nanstd(tr, axis=0, ddof=1), nan=0.0)
    out: np.ndarray = np.where(sd > 0, sd, np.nanmedian(sd[sd > 0]) if (sd > 0).any() else 1.0)
    return out


_MEMO: dict[str, Any] = {"key": None, "cleaned": None}


def _cleaned_for(tr: np.ndarray) -> rmt.Cleaned:
    """One cleaning per training window, shared by every variant and covariance builder of that
    rebalance (eleven consumers; ~0.3 s each at N = 300 un-memoised)."""
    key = (tr.shape, hash(np.nan_to_num(tr, nan=1e300).tobytes()))
    if _MEMO["key"] != key:
        _MEMO["cleaned"] = rmt.clean(tr, [str(i) for i in range(tr.shape[1])],
                                     min_overlap=min(rmt.MIN_OVERLAP, max(20, tr.shape[0] // 4)))
        _MEMO["key"] = key
    out: rmt.Cleaned = _MEMO["cleaned"]
    return out


def _cov_of(kind: str):
    def fn(tr: np.ndarray) -> np.ndarray:
        return rmt.to_cov(_cleaned_for(tr).matrix(kind), _sd(tr))
    return fn


def _train_exposure_matrix(tr: np.ndarray, fac: np.ndarray, min_obs: int = 60
                           ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(B N x K, t N x K, r2 N) by per-sleeve OLS on the training rows, NaN-aware. Vectorised
    enough for a walk-forward (one lstsq per sleeve per rebalance)."""
    n, k = tr.shape[1], fac.shape[1]
    b = np.zeros((n, k))
    t = np.zeros((n, k))
    r2 = np.zeros(n)
    fok = np.isfinite(fac).all(axis=1)
    for j in range(n):
        ok = np.isfinite(tr[:, j]) & fok
        if ok.sum() < min_obs:
            continue
        x = np.column_stack([np.ones(int(ok.sum())), fac[ok]])
        y = tr[ok, j]
        try:
            xtx_inv = np.linalg.inv(x.T @ x + 1e-10 * np.eye(k + 1))
        except np.linalg.LinAlgError:
            continue
        beta = xtx_inv @ (x.T @ y)
        res = y - x @ beta
        se = st.newey_west_se(x, res, xtx_inv)
        b[j] = beta[1:]
        t[j] = np.where(se[1:] > 0, beta[1:] / np.where(se[1:] > 0, se[1:], 1.0), 0.0)
        sst = float(((y - y.mean()) ** 2).sum())
        r2[j] = max(0.0, 1.0 - float(res @ res) / sst) if sst > 0 else 0.0
    return b, t, r2


def build_variants(factors: pd.DataFrame | None, total_heat: float) -> list[st.Variant]:
    def kelly_on(kind: str):
        def fn(tr: np.ndarray, ctx: dict[str, Any]) -> np.ndarray:
            cov = _cov_of(kind)(tr)
            return st.scale_to(st.kelly_direction(_mu_shrunk(tr), cov), total_heat)
        return fn

    def factor_block(ctx: dict[str, Any]) -> np.ndarray | None:
        if factors is None or factors.empty:
            return None
        idx = ctx["train_index"]
        f = factors.reindex(idx).to_numpy(float)
        return f if np.isfinite(f).all(axis=1).sum() >= 60 else None

    def rie_neutral(tr: np.ndarray, ctx: dict[str, Any]) -> np.ndarray:
        w = kelly_on("rie")(tr, ctx)
        f = factor_block(ctx)
        if f is None:
            return w
        b, _t, _ = _train_exposure_matrix(tr, f)
        x = b.T @ w
        fsd = np.nanstd(f, axis=0)
        # neutralise against factors the book is materially exposed to: |x_f| sd_f above 10% of
        # the book's own daily R sd, and where the book shows no paid factor premium in training
        bsd = float(np.nanstd(np.nan_to_num(tr, nan=0.0) @ w)) or 1.0
        fmu = np.nanmean(f, axis=0)
        sel = (np.abs(x) * fsd > 0.10 * bsd) & (x * fmu <= 0)
        if not sel.any():
            return w
        return st.neutralise(w, b[:, sel])

    def rie_idm(tr: np.ndarray, ctx: dict[str, Any]) -> np.ndarray:
        cov = _cov_of("rie")(tr)
        w = st.kelly_direction(_mu_shrunk(tr), cov)
        sd = _sd(tr)
        corr = cov / np.outer(sd, sd)
        _dm, heat = st.idm_heat(corr, w, floor=total_heat)
        return st.scale_to(w, heat)

    def rie_crowd(tr: np.ndarray, ctx: dict[str, Any]) -> np.ndarray:
        w = kelly_on("rie")(tr, ctx)
        f = factor_block(ctx)
        if f is None or factors is None:
            return w
        names = list(factors.columns)
        style_idx = [i for i, n in enumerate(names) if n in STYLE]
        if not style_idx:
            return w
        _b, _t, r2_style = _train_exposure_matrix(tr, f[:, style_idx])
        style_sum = np.nansum(f[:, style_idx], axis=1)
        cut = np.nanquantile(style_sum, 0.05)
        tail = style_sum <= cut
        sd = _sd(tr)
        unwind = -np.nan_to_num(np.nanmean(tr[tail], axis=0), nan=0.0) / sd
        rows = {str(j): {"style_r2": float(r2_style[j]), "unwind_loss": float(unwind[j])}
                for j in range(tr.shape[1])}
        cz = st.crowding_z(rows)
        return st.crowd_tilt(w, np.array([np.nan if cz[str(j)] is None else cz[str(j)]
                                          for j in range(tr.shape[1])], dtype=float))

    return [
        st.Variant("kelly_sample", "long-only Kelly on the PSD-repaired sample covariance "
                   "(baseline)", kelly_on("sample")),
        st.Variant("kelly_lw", "Kelly on Ledoit-Wolf shrinkage to identity", kelly_on("lw")),
        st.Variant("kelly_clipped", "Kelly on MP eigenvalue-clipped correlation",
                   kelly_on("clipped")),
        st.Variant("kelly_rie", "Kelly on the debiased rotationally invariant estimator",
                   kelly_on("rie")),
        st.Variant("kelly_rie_neutral", "RIE Kelly neutralised against unpaid material factor "
                   "exposures (Dykstra projection, same heat)", rie_neutral),
        st.Variant("kelly_rie_idm", "RIE Kelly with heat = floor x IDM, capped at the 30% "
                   "ceiling", rie_idm),
        st.Variant("kelly_rie_crowd", "RIE Kelly tilted two-sided by train-window crowding "
                   "(style R2 + unwind loss)", rie_crowd),
    ]


ADOPTION_MAP = {"rmt_cleaning": "kelly_rie", "rmt_clipping": "kelly_clipped",
                "factor_neutralisation": "kelly_rie_neutral",
                "diversification_multiplier": "kelly_rie_idm",
                "crowding_tilt": "kelly_rie_crowd"}


def measure(panel: pd.DataFrame | None, panel_why: str, book: dict[str, float],
            total: float | None, closes: pd.DataFrame, carry: dict[str, int],
            cot: dict[str, pd.Series], *, budget_s: float = 600.0,
            clock=time.monotonic,
            carry_since: dict[str, pd.Timestamp] | None = None) -> dict[str, Any]:
    t0 = clock()
    doc: dict[str, Any] = {"at": _now(), "status": "UNMEASURED", "why": panel_why,
                           "inputs": {"panel": panel_why, "book_sleeves": len(book),
                                      "book_total_heat": total,
                                      "factor_symbols": list(closes.columns),
                                      "carry_signed_pairs": len(carry),
                                      "cot_markets": sorted(cot)}}
    if panel is None or panel.shape[1] < 5:
        doc["why"] = panel_why if panel is None else f"only {panel.shape[1]} sleeves; need 5"
        doc["adoption"] = dict.fromkeys(ADOPTION_MAP, "UNMEASURED")
        return doc
    names = [str(c) for c in panel.columns]
    held = [n for n in names if book.get(n, 0.0) > 0]
    doc["panel"] = {"sleeves": len(names), "days": int(panel.shape[0]), "held": len(held),
                    "first": str(panel.index[0].date()), "last": str(panel.index[-1].date())}
    notes: list[str] = []

    # ---- RMT on the full panel
    x = st.inlife_zero(panel.to_numpy(float))
    cleaned = rmt.clean(x, names)
    doc["rmt"] = cleaned.summary()
    CORR_OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = CORR_OUT.with_name(CORR_OUT.stem + ".tmp.npz")
    np.savez_compressed(tmp, names=np.array(names), sample=cleaned.sample,
                        clipped=cleaned.clipped, rie=cleaned.rie, lw=cleaned.lw,
                        at=np.array(doc["at"]))
    os.replace(tmp, CORR_OUT)

    # ---- factor model
    factors = (st.style_factors(closes, carry, carry_since or {}) if not closes.empty
               else pd.DataFrame())
    factors = factors.reindex(panel.index) if not factors.empty else factors
    if factors is not None and not factors.empty:
        factors = factors.loc[:, factors.notna().sum() >= 120]
    fnames = [] if factors is None or factors.empty else list(factors.columns)
    exp: dict[str, st.Exposure] = {}
    if fnames:
        exp = st.exposures(panel, factors)
        fcov = st.factor_cov(factors)
        decomp = st.risk_decomposition(book, exp, fcov, fnames) if book else {
            "status": "UNMEASURED", "why": "no published book"}
        top = sorted(((n, f, e.beta[f], e.t[f]) for n, e in exp.items() for f in fnames
                      if abs(e.t[f]) >= 3.0), key=lambda r: -abs(r[3]))[:25]
        doc["factor_model"] = {
            "factors": fnames,
            "factor_vol_annual": {f: math.sqrt(max(fcov[i, i], 0.0) * 252)
                                  for i, f in enumerate(fnames)},
            "factor_corr": np.round(fcov / np.sqrt(np.outer(np.diag(fcov), np.diag(fcov))
                                                   + 1e-30), 3).tolist(),
            "sleeves_fitted": len(exp),
            "median_r2": float(np.median([e.r2 for e in exp.values()])) if exp else None,
            "sleeves_with_significant_exposure": sum(
                1 for e in exp.values() if any(abs(v) >= 3.0 for v in e.t.values())),
            "book": decomp,
            "strongest_exposures": [{"sleeve": n, "factor": f, "beta": b, "t_nw": t}
                                    for n, f, b, t in top],
        }
        # ---- neutralisation of the published book (the measurement; the proof is below)
        if book and decomp.get("status") == "MEASURED":
            held_e = [n for n in held if n in exp]
            w = np.array([book[n] for n in held_e])
            b = np.array([[exp[n].beta[f] for f in fnames] for n in held_e])
            xb = b.T @ w
            fvol = np.sqrt(np.clip(np.diag(fcov), 0.0, None))
            spec = np.array([exp[n].specific_var for n in held_e])
            book_sd = math.sqrt(float(xb @ fcov @ xb) + float((w ** 2 * spec).sum())) or 1.0
            fmu = factors.mean().to_numpy(float)
            sel = (np.abs(xb) * fvol > 0.10 * book_sd) & (xb * fmu <= 0)
            if sel.any():
                wn = st.neutralise(w, b[:, sel])
                doc["neutralisation"] = {
                    "neutralised_against": [f for f, s in zip(fnames, sel, strict=True) if s],
                    "rule": "factor contributes >10% of book sd and the book earns no premium "
                            "from it (exposure x factor mean <= 0)",
                    "turnover_share": float(np.abs(wn - w).sum() / max(w.sum(), 1e-12)),
                    "book_exposure_before": dict(zip(fnames, xb.tolist(), strict=True)),
                    "book_exposure_after": dict(zip(fnames, (b.T @ wn).tolist(), strict=True)),
                    "largest_changes": sorted(
                        ({"sleeve": n, "heat": float(a), "neutral_heat": float(c)}
                         for n, a, c in zip(held_e, w, wn, strict=True)),
                        key=lambda r: -abs(r["neutral_heat"] - r["heat"]))[:15]}
            else:
                doc["neutralisation"] = {"neutralised_against": [],
                                         "why": "no material unpaid factor exposure in the book"}
    else:
        notes.append("no factor bars readable: factor model, neutralisation and style crowding "
                     "UNMEASURED")

    # ---- diversification multiplier
    if held:
        hidx = [names.index(n) for n in held]
        w = np.array([book[n] for n in held])
        sub = np.ix_(hidx, hidx)
        dm_s = st.diversification_multiplier(cleaned.sample[sub], w)
        dm_r, heat = st.idm_heat(cleaned.rie[sub], w)
        sym_w: dict[str, float] = {}
        for n in held:
            sym_w[st.symbol_of(n)] = sym_w.get(st.symbol_of(n), 0.0) + book[n]
        doc["diversification"] = {
            "dm_sample": dm_s, "dm_rie": dm_r,
            "heat_at_floor_risk": heat,
            "rule": "heat that carries the 20% floor's ex-ante risk at the RIE-measured "
                    "diversification, inside [20%, 30%] (two-sided: a concentrated book stays at "
                    "the floor, a diversified one may carry more)",
            "book_total_heat": total,
            "symbols_held": len(sym_w),
            "note": "sample DM overstates diversification in noise modes; RIE is the honest one"}
    else:
        doc["diversification"] = {"status": "UNMEASURED", "why": "no published book"}

    # ---- crowding
    rows: dict[str, dict[str, Any]] = {n: {} for n in names}
    style_cols = [f for f in fnames if f in STYLE]
    if exp and style_cols:
        sub_exp = st.exposures(panel, factors[style_cols])
        for n, e in sub_exp.items():
            rows[n]["style_r2"] = e.r2
        style_sum = factors[style_cols].sum(axis=1, min_count=1)
        for n in names:
            ub = st.unwind_beta(panel[n], style_sum)
            rows[n]["unwind_loss"] = None if ub is None else -ub
    fam = {n: st.family_of(n) for n in names}
    if exp:
        resid = pd.DataFrame({n: panel[n] - (factors[fnames].fillna(0.0).to_numpy(float)
                                             @ np.array([exp[n].beta[f] for f in fnames]))
                              for n in names if n in exp}, index=panel.index)
    else:
        resid = panel
    como = st.comomentum(resid, fam)
    for n in names:
        z = (como.get(fam[n]) or {}).get("z")
        rows[n]["comomentum_z"] = z
    cot_seen = 0
    for n in names:
        series, sign = cot_for(st.symbol_of(n), cot)
        if series is None:
            continue
        p = st.cot_pressure(panel[n].dropna(), series, sign)
        rows[n]["cot_pressure"] = p["pressure"]
        rows[n]["cot"] = p
        cot_seen += p["pressure"] is not None
    cz = st.crowding_z(rows)
    measured = {n: z for n, z in cz.items() if z is not None}
    ranked = sorted(measured.items(), key=lambda kv: -kv[1])
    held_m = [n for n in held if n in measured]
    doc["crowding"] = {
        "signals_coverage": {k: sum(1 for r in rows.values() if r.get(k) is not None)
                             for k in ("style_r2", "comomentum_z", "cot_pressure",
                                       "unwind_loss")},
        "sleeves_measured": len(measured), "sleeves_unmeasured": len(cz) - len(measured),
        "held_measured": len(held_m), "held_unmeasured": len(held) - len(held_m),
        "by_family": dict(sorted(como.items(), key=lambda kv: -(kv[1].get("z") or -9))),
        "most_crowded": [{"sleeve": n, "crowd_z": z, "held_heat": book.get(n, 0.0),
                          **{k: rows[n].get(k) for k in ("style_r2", "comomentum_z",
                                                         "cot_pressure", "unwind_loss")}}
                         for n, z in ranked[:20]],
        "least_crowded": [{"sleeve": n, "crowd_z": z, "held_heat": book.get(n, 0.0)}
                          for n, z in ranked[-10:]],
        "book_crowd_z": (sum(book[n] * measured[n] for n in held_m)
                         / sum(book[n] for n in held_m)) if held_m else None,
        "book_crowd_z_basis": "heat-weighted over the held sleeves with a measured crowd z; "
                              "unmeasured sleeves are counted above, never read as 0",
        "tilt_rule": f"heat x exp(-{st.CROWD_KAPPA} x crowd_z), total unchanged (two-sided)",
    }

    # ---- the proof
    remaining = budget_s - (clock() - t0)
    th = total if total and st.HEAT_FLOOR <= total <= st.HEAT_CEILING else st.HEAT_FLOOR
    variants = build_variants(factors if fnames else None, th)
    proof = st.walk_forward(panel, variants, "kelly_sample", train=250, step=21,
                            budget_s=max(30.0, remaining * 0.85), clock=clock,
                            cov_builders={k: _cov_of(k)
                                          for k in ("sample", "lw", "clipped", "rie")})
    doc["proof"] = {"baseline": "kelly_sample", "total_heat": th,
                    "rebalances": proof.rebalances, "oos_days": proof.oos_days,
                    "train_days": 250, "hold_days": 21,
                    "by_variant": proof.by_variant,
                    "gmv_oos_var": proof.gmv_oos_var,
                    "acceptance": "ADOPT iff the 90% lower bound of the paired Newey-West mean "
                                  "daily log-growth gain over the baseline is > 0"}
    doc["adoption"] = {k: (proof.by_variant.get(v) or {}).get("verdict", "UNMEASURED")
                       for k, v in ADOPTION_MAP.items()}
    full = proof.rebalances > 0 and bool(fnames) and bool(held)
    doc["status"] = "MEASURED" if full else "PARTIAL"
    doc["why"] = ("every input measured" if full else
                  "; ".join(notes) or "partial: see each block")
    doc["notes"] = cleaned.notes + notes
    doc["elapsed_s"] = round(clock() - t0, 1)
    return _clean(doc)


def history_row(doc: dict[str, Any]) -> dict[str, Any]:
    r = doc.get("rmt") or {}
    return {"at": doc.get("at"), "status": doc.get("status"),
            "sleeves": (doc.get("panel") or {}).get("sleeves"),
            "n_signal_eigen": r.get("n_signal_eigen"), "q": r.get("q"),
            "effective_bets_rie": (r.get("effective_bets") or {}).get("rie"),
            "dm_rie": (doc.get("diversification") or {}).get("dm_rie"),
            "book_crowd_z": (doc.get("crowding") or {}).get("book_crowd_z"),
            "factor_share": ((doc.get("factor_model") or {}).get("book") or {}).get(
                "factor_share"),
            "adoption": doc.get("adoption")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    a = ap.parse_args(argv)
    panel, why = load_panel()
    book, total = load_book()
    closes = load_closes()
    signs, since = carry_signs()
    doc = measure(panel, why, book, total, closes, signs, load_cot(),
                  budget_s=a.budget_s, carry_since=since)
    _write(OUT, doc)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(_clean(history_row(doc)), default=_json_default) + "\n")
    print(f"allocator structure: {doc['status']} -- {doc['why']}")
    for k, v in (doc.get("adoption") or {}).items():
        print(f"  {k:<28} {v}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
