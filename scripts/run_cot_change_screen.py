"""KRT position-CHANGE liquidity screen -- the construction the 41y COT screen never charged.

Pre-registered in docs/research/AXIS_PREREGISTRATIONS.md ("C. krt_position_change_liquidity",
2026-08-25) BEFORE this file was written; every constant below is fixed there. Stage-A SCREEN
with ZERO promotion authority (L1.6): a survivor becomes a hypothesis card for the canonical
10-gate door, never a sleeve.

Mechanism (Kang-Rouwenhorst-Tang JF 2020; Marechal JFM 2023 replication): noncommercials
demanding immediacy move futures away from value; commercials accommodate and earn the
reversion at ~weekly horizon -- so the desk FADES the weekly position CHANGE. Sign expected
NEGATIVE on every cell. The LEVEL channel is already dead on desk data (COT_SCREEN_RESULT.md,
pooled NW t=-0.64) and is not re-litigated here.

Release alignment is stricter than the 41y screen's: that screen's return window started the
Wednesday AFTER the Tuesday snapshot -- two sessions before the Friday 15:30 ET publication.
Here entry is the first close STRICTLY after report_date+3d and exit the first close STRICTLY
after report_date+10d, so only post-release prices are ever touched.

    python scripts/run_cot_change_screen.py [--offline]
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scripts.run_cot_screen import _fred, _nw_t

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/cot_change_screen.json"
_DOC = _ROOT / "docs/research/COT_SCREEN_RESULT.md"
_COT_DIR = _ROOT / "desks/mt5/cot"
_H1_DIR = _ROOT / "desks/mt5/universe"

# asset -> (price source, invert). FRED DEX* orientation is corrected to the CONTRACT underlying
# (a JPY futures long is long yen; DEXJPUS is yen-per-dollar). Preregistered, not tuned.
_LEGS: dict[str, tuple[str, str, bool]] = {
    "gold": ("h1", "XAUUSD", False),
    "silver": ("h1", "XAGUSD", False),
    "aud": ("fred", "DEXUSAL", False),
    "cad": ("fred", "DEXCAUS", True),
    "chf": ("fred", "DEXSZUS", True),
    "gbp": ("fred", "DEXUSUK", False),
    "jpy": ("fred", "DEXJPUS", True),
    "nzd": ("fred", "DEXUSNZ", False),
    "sp500": ("fred", "SP500", False),
    "nasdaq100": ("fred", "NASDAQCOM", False),  # composite as NAS100 proxy -- stated in prereg
}
_MIN_WEEKS = 100          # per-asset guard (prereg)
_STD_WIN = 104            # past-only std window for pooled standardization (prereg)
_RECENT_DAYS = 730        # trailing 24 months (RESEARCH 6b)
_BAR = -1.96              # survive iff pooled dx1 t <= _BAR (prereg KILL rule)


def _prices(asset: str, *, offline: bool) -> dict[str, float]:
    """Daily close keyed YYYY-MM-DD, oriented to the contract underlying."""
    kind, key, invert = _LEGS[asset]
    if kind == "h1":
        df = pd.read_parquet(_H1_DIR / f"{key}_H1.parquet")
        col = "close" if "close" in df.columns else df.columns[-1]
        s = df[col].astype(float)
        idx = pd.to_datetime(df.index if df.index.name else df["timestamp"], utc=True)
        daily = s.groupby(idx.date).last()
        out = {str(d): float(v) for d, v in daily.items() if np.isfinite(v) and v > 0}
    else:
        if offline:
            raise OSError(f"offline and {key} not cached")
        out = {d: v for d, v in _fred(key).items() if v > 0}
    if invert:
        out = {d: 1.0 / v for d, v in out.items()}
    return out


def _panel(asset: str) -> pd.DataFrame:
    df = pd.read_parquet(_COT_DIR / f"{asset}.parquet")
    df = df.dropna(subset=["report_date", "open_interest_all"]).copy()
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True)
    df = df.sort_values("report_date").drop_duplicates("report_date", keep="last")
    oi = df["open_interest_all"].astype(float).clip(lower=1.0)
    df["spec_share"] = (df["noncomm_positions_long_all"].astype(float)
                        - df["noncomm_positions_short_all"].astype(float)) / oi
    return df[["report_date", "spec_share"]].reset_index(drop=True)


def _post_release_returns(prices: dict[str, float], report_dates: list[str]) -> np.ndarray:
    """Return over first-close-after(d+3) -> first-close-after(d+10). Post-release only."""
    keys = sorted(prices)
    out = np.full(len(report_dates), np.nan)
    for i, d in enumerate(report_dates):
        day = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=UTC)
        lo = (day + timedelta(days=3)).strftime("%Y-%m-%d")
        hi = (day + timedelta(days=10)).strftime("%Y-%m-%d")
        start = next((k for k in keys if k > lo), None)
        end = next((k for k in keys if k > hi), None)
        if start is None or end is None or end <= start:
            continue
        out[i] = prices[end] / prices[start] - 1.0
    return out


def _past_std(x: np.ndarray, win: int) -> np.ndarray:
    """Trailing std over the PRIOR win observations (never includes t)."""
    out = np.full(len(x), np.nan)
    for t in range(win, len(x)):
        w = x[t - win:t]
        w = w[np.isfinite(w)]
        if len(w) >= win // 2 and w.std() > 0:
            out[t] = w.std()
    return out


def _cell(y: np.ndarray, x: np.ndarray) -> dict[str, Any]:
    m = np.isfinite(y) & np.isfinite(x)
    beta, t = _nw_t(y[m], x[m]) if m.sum() >= 30 else (0.0, 0.0)
    return {"beta": round(float(beta), 6), "t": round(float(t), 2), "n": int(m.sum())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    trials = 0
    per_asset: list[dict[str, Any]] = []
    dropped: list[str] = []
    # pooled arrays: (date, y, x1_std, x4_std) kept aligned for full/recent splits and XS
    rows: list[tuple[str, str, float, float, float]] = []

    for asset in _LEGS:
        path = _COT_DIR / f"{asset}.parquet"
        if not path.exists():
            dropped.append(f"{asset}: no COT parquet")
            continue
        pan = _panel(asset)
        try:
            prices = _prices(asset, offline=args.offline)
        except (OSError, ValueError, KeyError) as e:
            dropped.append(f"{asset}: price leg unavailable ({type(e).__name__})")
            continue
        dates = [str(d)[:10] for d in pan["report_date"]]
        share = pan["spec_share"].to_numpy(dtype=float)
        dx1 = np.diff(share, prepend=np.nan)
        dx4 = share - np.roll(share, 4)
        dx4[:4] = np.nan
        ret = _post_release_returns(prices, dates)
        usable = np.isfinite(ret) & np.isfinite(dx1)
        if usable.sum() < _MIN_WEEKS:
            dropped.append(f"{asset}: {int(usable.sum())} usable weeks < {_MIN_WEEKS}")
            continue
        row: dict[str, Any] = {"asset": asset, "n_weeks": int(usable.sum())}
        for name, dx in (("dx1", dx1), ("dx4", dx4)):
            trials += 1
            row[name] = _cell(ret, dx)
        per_asset.append(row)
        sd1, sd4 = _past_std(dx1, _STD_WIN), _past_std(dx4, _STD_WIN)
        for i, d in enumerate(dates):
            if np.isfinite(ret[i]):
                rows.append((d, asset,
                             float(ret[i]),
                             float(dx1[i] / sd1[i]) if np.isfinite(dx1[i]) and np.isfinite(sd1[i]) else float("nan"),
                             float(dx4[i] / sd4[i]) if np.isfinite(dx4[i]) and np.isfinite(sd4[i]) else float("nan")))

    cutoff = (datetime.now(tz=UTC) - timedelta(days=_RECENT_DAYS)).strftime("%Y-%m-%d")
    pooled: dict[str, Any] = {}
    for win_name, keep in (("full", lambda d: True), ("recent24m", lambda d: d >= cutoff)):
        y = np.array([r[2] for r in rows if keep(r[0])])
        x1 = np.array([r[3] for r in rows if keep(r[0])])
        x4 = np.array([r[4] for r in rows if keep(r[0])])
        pooled[win_name] = {"dx1": _cell(y, x1), "dx4": _cell(y, x4)}
        trials += 2

    # XS: weekly Spearman across assets, weeks with >= 6 assets (prereg)
    xs: dict[str, Any] = {}
    bydate: dict[str, list[tuple[float, float, float]]] = {}
    for d, _a, yv, x1v, x4v in rows:
        bydate.setdefault(d, []).append((yv, x1v, x4v))
    for name, xi in (("dx1", 1), ("dx4", 2)):
        ics = []
        for d in sorted(bydate):
            grp = [(v[0], v[xi]) for v in bydate[d] if np.isfinite(v[xi])]
            if len(grp) >= 6:
                yy = pd.Series([g[0] for g in grp]).rank()
                xx = pd.Series([g[1] for g in grp]).rank()
                if xx.std() > 0 and yy.std() > 0:
                    ics.append(float(np.corrcoef(xx, yy)[0, 1]))
        trials += 1
        if len(ics) >= 30:
            arr = np.asarray(ics)
            xs[name] = {"mean_ic": round(float(arr.mean()), 4),
                        "t": round(float(arr.mean() / arr.std() * np.sqrt(len(arr))), 2),
                        "n_weeks": len(arr)}
        else:
            xs[name] = {"mean_ic": None, "t": None, "n_weeks": len(ics)}

    prim = pooled["full"]["dx1"]
    survived = prim["beta"] < 0 and prim["t"] <= _BAR
    flip = survived and pooled["recent24m"]["dx1"]["beta"] >= 0
    verdict = ("SURVIVE -> hypothesis card for the 10-gate door"
               + (" [DECAY FLAG: recent-window sign flip]" if flip else "")
               if survived else
               "SCREEN-KILL: pooled dx1 fails the preregistered bar (beta >= 0 or t > -1.96)")

    payload = {
        "measured": datetime.now(tz=UTC).isoformat(),
        "prereg": "docs/research/AXIS_PREREGISTRATIONS.md C. krt_position_change_liquidity",
        "cost_basis": "gross",
        "trials_charged": trials,
        "primary": prim, "pooled": pooled, "xs": xs,
        "per_asset": per_asset, "dropped": dropped,
        "verdict": verdict,
    }
    _OUT.write_text(json.dumps(payload, indent=2))
    with _DOC.open("a") as f:
        f.write(
            f"\n\n## KRT position-CHANGE screen (2026-08-25, card #40 conversion)\n\n"
            f"Prereg: AXIS_PREREGISTRATIONS.md C. Primary pooled dx1: beta={prim['beta']}, "
            f"NW t={prim['t']}, n={prim['n']}; recent24m dx1 t={pooled['recent24m']['dx1']['t']}; "
            f"XS dx1 mean IC={xs['dx1']['mean_ic']} (t={xs['dx1']['t']}). "
            f"{trials} trials charged; dropped: {dropped or 'none'}.\n\n**{verdict}**\n"
        )
    print(json.dumps({"verdict": verdict, "primary": prim,
                      "recent24m_dx1": pooled["recent24m"]["dx1"],
                      "xs_dx1": xs["dx1"], "trials": trials, "dropped": dropped}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
