"""B3 -- A PER-ASSET REGIME HIERARCHY, plus the two states the desk never measured.

THE BLUEPRINT ITEM: "probabilistic market world model: P(state|history) + transitions, not one
regime label". The desk HAD the machinery -- `libs/regime/hmm.py` is a self-contained
Baum-Welch HMM with a causal forward filter, `libs/regime/transitions.py` forecasts from a
transition matrix -- and used it on ONE series: XAUUSD daily closes, as the global regime.

WHAT MEASURING IT FOUND, 2026-09-23. `state_vector_build` already intends per-asset states, and
on this box its `assets` block is `{}` with its own gaps naming the two causes:

    "factor:USD@daily": "USDX@daily: ModuleNotFoundError: No module named 'sklearn'"
    "global":           "XAUUSD@daily: 75 daily bars, needs 250"

So the per-asset half of the world model was dark for a missing optional dependency (the GMM
agreement check, not the HMM) and for a daily-bar floor, while the same instruments carry
thousands of H1 bars in `data/universe`. This organ takes the path that does not depend on
either: numpy + scipy only, daily closes RESAMPLED from the H1 lake, and no GMM.

THE HIERARCHY IS THE POINT, not a per-symbol fit repeated N times. Each symbol's transition
matrix is shrunk toward the POOLED matrix of its asset class with weight n/(n+N0) -- so a symbol
with 4000 days is essentially its own model, a symbol with 300 days borrows most of its dynamics
from its class, and no symbol gets a confident transition matrix it has not paid for. The
divergence between own and pooled is REPORTED per symbol, so "the hierarchy did something" is a
number rather than a claim.

THE TWO MISSING STATES, from the item's own gap text:
  LIQUIDITY  the instrument's own H1 range and spread percentiles against its own history --
             never a cross-instrument constant, because a 2-point spread is thin for EURUSD and
             deep for a share CFD.
  CROWDING   the share of the symbol's daily-return variance explained by the first principal
             component of its asset-class peers. A symbol moving entirely with its class is one
             whose edge is being traded by everyone who trades the class.

IT SIZES NOTHING. The artifact is information: `pf_allocator` records it beside the state vector
and the allocator's fractions are unchanged by this file. A state dimension takes capital
authority by improving calibration or marginal E[log W] against the existing gates, never by
being plausible (the same rule the state vector's own comment states).

    python desks/mt5/research/regime_hierarchy.py [--once] [--budget-s 600]
        -> desks/mt5/reports/REGIME_HIERARCHY.json
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
UNI = DESK / "data" / "universe"
OUT = DESK / "reports" / "REGIME_HIERARCHY.json"
SLEEVES = DESK / "data" / "sleeves.json"
CANON = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"

#: States. Three is what the desk's global engine uses and what a few hundred daily bars can
#: identify; more states on this much data is fitting noise and calling it a regime.
K_STATES = 3
#: Daily bars a symbol must carry before its OWN fit is admitted at all. Below this the symbol
#: is reported as borrowing its class's pooled dynamics entirely, which is a verdict, not a gap.
MIN_DAYS = 180
#: The hierarchical prior's strength, in days. A symbol with N0 days splits its transition matrix
#: half from itself and half from its class.
N0_DAYS = 400.0
#: Trailing window for the liquidity and crowding measurements, in daily observations.
STATE_WINDOW = 250


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def book_symbols(limit: int) -> list[str]:
    """The instruments the desk actually holds or has certified, then its largest-history
    neighbours, never a hand-written list."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(sym: Any) -> None:
        s = str(sym or "").upper()
        if s and s not in seen and (UNI / f"{s}_H1.parquet").exists():
            seen.add(s)
            out.append(s)

    sl = _read(SLEEVES)
    if isinstance(sl, dict):
        for row in (sl.get("sleeves") or sl.get("rows") or []):
            if isinstance(row, dict):
                _add(row.get("symbol"))
    canon = _read(CANON)
    if isinstance(canon, dict):
        for cert in (canon.get("survivors") or {}).values():
            if isinstance(cert, dict):
                _add(cert.get("sym") or (cert.get("shadow_spec") or {}).get("symbol"))
    reg = _read(UNI / "universe.json")
    if isinstance(reg, dict):
        rows = sorted(((str(k), int((v or {}).get("bars") or 0)) for k, v in reg.items()
                       if isinstance(v, dict)), key=lambda kv: -kv[1])
        for sym, _n in rows:
            if len(out) >= limit:
                break
            _add(sym)
    return out[:limit]


def asset_class_of(symbol: str) -> str:
    try:
        import sys
        if str(DESK) not in sys.path:
            sys.path.insert(0, str(DESK))
        from research.universe_policy import asset_class_of as _ac
        return str(_ac(symbol) or "unclassified")
    except Exception:
        reg = _read(UNI / "universe.json")
        row = reg.get(symbol) if isinstance(reg, dict) else None
        return str((row or {}).get("asset_class") or "unclassified").lower()


def daily_closes(symbol: str) -> Any:
    """Daily closes resampled from the H1 lake, and the H1 frame for the liquidity state."""
    try:
        import pandas as pd
    except ImportError:
        return None, None
    path = UNI / f"{symbol}_H1.parquet"
    # ONLY THE FIVE COLUMNS THIS ORGAN READS. Measured 2026-09-23: the whole-file read cost
    # ~100 s per symbol on 50,255-row parquets and three symbols exhausted a 300 s budget, so
    # the per-asset world model was bounded by pandas rather than by the fit.
    cols = ["close", "high", "low", "spread", "tick_volume"]
    try:
        df = pd.read_parquet(path, columns=cols)
    except Exception:
        try:
            df = pd.read_parquet(path)
        except Exception:
            return None, None
    if df is None or df.empty:
        return None, None
    # THE UNIVERSE PARQUETS CARRY TIME AS THE INDEX, not as a column (measured 2026-09-23:
    # XAUUSD_H1.parquet is 50,255 rows indexed by `time`). A reader that only looks for a column
    # reports "0 daily bars" for every symbol in the book, which is how a per-asset world model
    # reads UNMEASURED on a box holding fifty thousand bars per instrument.
    df = df.copy()
    tcol = next((c for c in ("time", "timestamp", "date", "datetime") if c in df.columns), None)
    if tcol is not None:
        df[tcol] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
        df = df.dropna(subset=[tcol]).sort_values(tcol).set_index(tcol)
    else:
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        df.index = idx
        df = df[~df.index.isna()].sort_index()
    if "close" not in df.columns or df.empty:
        return None, None
    daily = df["close"].resample("1D").last().dropna()
    return daily, df


def _fit(close: Any) -> dict[str, Any] | None:
    """One symbol's own HMM: causal posterior, transitions, per-state character."""
    try:
        import numpy as np

        from libs.regime.features import regime_features
        from libs.regime.hmm import GaussianHMM
    except ImportError:
        return None
    x, raw = regime_features(close)
    if x.shape[0] < MIN_DAYS:
        return None
    hmm = GaussianHMM(n_states=K_STATES, seed=20260923).fit(x)
    post = hmm.filter_posterior(x)
    labels = np.argmax(post, axis=1).astype(int)
    vol = []
    for j in range(K_STATES):
        sel = raw[labels == j]
        vol.append(float(np.std(sel)) if sel.size > 2 else float("nan"))
    order = sorted(range(K_STATES), key=lambda j: (math.inf if math.isnan(vol[j]) else vol[j]))
    names = {order[0]: "quiet", order[len(order) // 2]: "normal", order[-1]: "stress"}
    trans = np.asarray(hmm.transmat, dtype=float)
    return {
        "n_days": int(x.shape[0]),
        "posterior": {names[j]: round(float(post[-1, j]), 4) for j in range(K_STATES)},
        "state_now": names[int(labels[-1])],
        "transmat_own": [[round(float(v), 4) for v in row] for row in trans],
        "state_order": [names[j] for j in range(K_STATES)],
        "expected_duration_days": {names[j]: (round(1.0 / max(1e-9, 1.0 - float(trans[j, j])), 2))
                                   for j in range(K_STATES)},
        "mean_daily_return": {names[j]: round(float(np.mean(raw[labels == j])), 6)
                              if int((labels == j).sum()) > 2 else None
                              for j in range(K_STATES)},
        "_trans": trans, "_labels": labels, "_raw": raw,
    }


def _liquidity(h1: Any, symbol: str) -> dict[str, Any]:
    """The instrument's own range and spread percentiles, against its own history."""
    try:
        import numpy as np
    except ImportError:
        return {"state": "UNMEASURED", "why": "numpy absent"}
    if h1 is None or getattr(h1, "empty", True):
        return {"state": "UNMEASURED", "why": "no H1 bars"}
    out: dict[str, Any] = {}
    try:
        hi, lo = h1["high"].to_numpy(dtype=float), h1["low"].to_numpy(dtype=float)
        cl = h1["close"].to_numpy(dtype=float)
        rng = np.divide(hi - lo, np.where(cl == 0, np.nan, cl))
        rng = rng[np.isfinite(rng)]
        if rng.size > 50:
            recent = float(np.nanmedian(rng[-24:]))
            pct = float((rng[-STATE_WINDOW * 24:] <= recent).mean())
            out["range_percentile"] = round(pct, 4)
    except (KeyError, ValueError, TypeError):
        pass
    try:
        if "spread" in h1.columns:
            sp = h1["spread"].to_numpy(dtype=float)
            sp = sp[np.isfinite(sp)]
            if sp.size > 50:
                recent = float(np.nanmedian(sp[-24:]))
                out["spread_percentile"] = round(float((sp <= recent).mean()), 4)
                out["spread_median_recent"] = round(recent, 4)
    except (KeyError, ValueError, TypeError):
        pass
    pct = out.get("spread_percentile", out.get("range_percentile"))
    if pct is None:
        return {"state": "UNMEASURED", "why": f"{symbol}: neither spread nor range measurable",
                **out}
    out["state"] = "thin" if pct >= 0.80 else "deep" if pct <= 0.20 else "normal"
    out["basis"] = ("spread percentile against this instrument's own H1 history"
                    if "spread_percentile" in out else
                    "bar-range percentile against this instrument's own H1 history")
    return out


def _crowding(per_symbol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Share of each symbol's daily variance explained by its class's first principal component.

    ONE PC, AND THE CLASS IS THE PEER SET. A symbol whose returns are nearly the class's first
    component is one whose edge is the class's edge: the desk can hold it, and should know it is
    not holding an independent bet. Classes with fewer than three members are UNMEASURED -- a
    principal component of two series is the pair correlation wearing a hat.
    """
    try:
        import numpy as np
    except ImportError:
        return {}
    by_class: dict[str, list[str]] = {}
    for sym, row in per_symbol.items():
        by_class.setdefault(str(row.get("asset_class") or "unclassified"), []).append(sym)
    out: dict[str, dict[str, Any]] = {}
    for cls, syms in by_class.items():
        series = {s: per_symbol[s].get("_returns") for s in syms
                  if per_symbol[s].get("_returns") is not None}
        if len(series) < 3:
            for s in syms:
                out[s] = {"state": "UNMEASURED",
                          "why": f"asset class {cls} has {len(series)} measurable member(s), "
                                 f"needs 3"}
            continue
        n = min(min(len(v) for v in series.values()), STATE_WINDOW)
        mat = np.vstack([np.asarray(v[-n:], dtype=float) for v in series.values()])
        mat = mat - mat.mean(axis=1, keepdims=True)
        sd = mat.std(axis=1, keepdims=True)
        mat = np.divide(mat, np.where(sd == 0, np.nan, sd))
        mat = np.nan_to_num(mat)
        try:
            u, s, _ = np.linalg.svd(mat, full_matrices=False)
        except np.linalg.LinAlgError:
            continue
        pc1 = u[:, 0] * s[0]
        total = float(np.sum(s ** 2)) or 1.0
        share_class = float(s[0] ** 2 / total)
        loads = np.abs(pc1) / (np.linalg.norm(pc1) or 1.0)
        for i, sym in enumerate(series):
            share = round(float(share_class * (loads[i] ** 2) * len(series)), 4)
            share = min(1.0, max(0.0, share))
            out[sym] = {"state": "crowded" if share >= 0.60 else
                        "independent" if share <= 0.25 else "shared",
                        "class_pc1_share": round(share_class, 4),
                        "own_share_of_pc1": share, "peers": len(series), "asset_class": cls}
    return out


def _shrink(own: Any, pooled: Any, n_days: int) -> tuple[list[list[float]], float, float]:
    """Hierarchical shrink toward the class's pooled transitions, and how far apart they were."""
    import numpy as np
    w = float(n_days) / (float(n_days) + N0_DAYS)
    blended = w * np.asarray(own, dtype=float) + (1.0 - w) * np.asarray(pooled, dtype=float)
    blended = blended / np.clip(blended.sum(axis=1, keepdims=True), 1e-9, None)
    l1 = float(np.abs(np.asarray(own, dtype=float) - np.asarray(pooled, dtype=float)).sum() / 2.0)
    return ([[round(float(v), 4) for v in row] for row in blended], round(w, 4), round(l1, 4))


def build(budget_s: float = 600.0, limit: int = 40) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    t0 = time.monotonic()
    syms = book_symbols(limit)
    per: dict[str, Any] = {}
    skipped: dict[str, str] = {}
    for sym in syms:
        if time.monotonic() - t0 > budget_s:
            skipped[sym] = "budget exhausted"
            continue
        daily, h1 = daily_closes(sym)
        if daily is None or len(daily) < MIN_DAYS:
            skipped[sym] = f"{0 if daily is None else len(daily)} daily bars, needs {MIN_DAYS}"
            continue
        fit = _fit(daily)
        if fit is None:
            skipped[sym] = "fit refused (too few usable rows or regime libs absent)"
            continue
        per[sym] = {**fit, "asset_class": asset_class_of(sym),
                    "liquidity": _liquidity(h1, sym),
                    "_returns": list(fit["_raw"][-STATE_WINDOW:])}
    # THE POOLED PRIOR, PER CLASS: the average of the class's own transition matrices, weighted
    # by the days behind each. A class of one is its own prior, and says so.
    pooled: dict[str, Any] = {}
    if per:
        import numpy as np
        by_class: dict[str, list[str]] = {}
        for sym, row in per.items():
            by_class.setdefault(str(row["asset_class"]), []).append(sym)
        for cls, members in by_class.items():
            w = np.array([float(per[s]["n_days"]) for s in members])
            mats = np.array([per[s]["_trans"] for s in members])
            pm = np.tensordot(w / w.sum(), mats, axes=(0, 0))
            pooled[cls] = {"transmat": [[round(float(v), 4) for v in row] for row in pm],
                           "members": len(members), "days": int(w.sum()), "_m": pm}
    crowd = _crowding(per)
    assets: dict[str, Any] = {}
    for sym, row in per.items():
        cls = str(row["asset_class"])
        pm = (pooled.get(cls) or {}).get("_m")
        blended, weight, l1 = (_shrink(row["_trans"], pm, int(row["n_days"]))
                               if pm is not None else
                               (row["transmat_own"], 1.0, 0.0))
        assets[sym] = {
            "asset_class": cls, "n_days": row["n_days"],
            "posterior": row["posterior"], "state_now": row["state_now"],
            "state_order": row["state_order"],
            "transmat": blended, "transmat_own": row["transmat_own"],
            "own_weight": weight, "own_vs_pooled_l1": l1,
            "expected_duration_days": row["expected_duration_days"],
            "mean_daily_return": row["mean_daily_return"],
            "liquidity": row["liquidity"],
            "crowding": crowd.get(sym, {"state": "UNMEASURED", "why": "no class peer set"}),
        }
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK" if assets else "UNMEASURED",
        "n_assets": len(assets), "n_classes": len(pooled),
        "n_skipped": len(skipped), "skipped": dict(sorted(skipped.items())[:25]),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "assets": assets,
        "classes": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                    for k, v in pooled.items()},
        "hierarchy": {
            "prior_days": N0_DAYS, "k_states": K_STATES, "min_days": MIN_DAYS,
            "why": ("each symbol's transition matrix is its own fit shrunk toward its asset "
                    "class's pooled matrix with weight n/(n+N0); own_vs_pooled_l1 is how far "
                    "the two were apart before blending, per symbol"),
        },
        "dependencies": ("numpy + scipy only: libs/regime/hmm.py is a self-contained Baum-Welch "
                         "HMM and the GMM agreement check (sklearn) is deliberately not used, "
                         "because sklearn is absent on this box and that absence is what left "
                         "state_vector_build's per-asset block empty"),
        "authority": ("INFORMATION, NOT AUTHORITY. pf_allocator records this beside the state "
                      "vector; no fraction, floor or heat changes because of it. A state "
                      "dimension earns capital authority by improving calibration or marginal "
                      "E[log W] against the existing gates, never by being plausible."),
        "consumers": ["desks/mt5/research/pf_allocator.py (recorded in pf_allocation.json)",
                      "desks/mt5/research/regime_hierarchy.py::load (per-sleeve regime reads)"],
    }
    return doc


def load(max_age_s: float = 7200.0) -> tuple[dict[str, Any] | None, str]:
    """The artifact, if fresh. Consumers read THIS rather than re-fitting."""
    try:
        age = time.time() - OUT.stat().st_mtime
    except OSError:
        return None, "no REGIME_HIERARCHY.json"
    if age > max_age_s:
        return None, f"REGIME_HIERARCHY.json is {age / 3600.0:.1f}h old"
    doc = _read(OUT)
    if not isinstance(doc, dict):
        return None, "REGIME_HIERARCHY.json unreadable"
    return doc, (f"{doc.get('n_assets')} asset(s) in {doc.get('n_classes')} class(es), "
                 f"{age / 60.0:.0f}m old")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--limit", type=int, default=40, help="symbols, most bars first")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, limit=a.limit)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"regime hierarchy: {doc['status']}  {doc['n_assets']} asset(s), "
          f"{doc['n_classes']} class(es), {doc['n_skipped']} skipped, {doc['elapsed_s']}s")
    for sym, row in list(doc["assets"].items())[:8]:
        print(f"  {sym:<10} {row['state_now']:<7} P={row['posterior']}  own_w={row['own_weight']}"
              f"  l1={row['own_vs_pooled_l1']}  liq={row['liquidity'].get('state')}"
              f"  crowd={row['crowding'].get('state')}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
