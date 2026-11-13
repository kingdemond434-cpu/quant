"""qlib adapter -- REBUILT: Qlib's Alpha158 factor bank screened by walk-forward rank IC on the
desk's own MT5 bars, the strongest holdout-stable factors donated as exact family recipes.

WHAT QLIB CONTRIBUTES THAT THE DESK DID NOT HAVE. Alpha158 is a fixed, published library of
price/volume operators (KMID/KLEN/KSFT candle shape, ROC, MA, STD, BETA, RSQR, RESI, MAX/MIN,
QTLU/QTLD, RSV, IMAX/IMIN, CNTP/CNTN, SUMP, VMA, VSTD, CORR) evaluated across windows
(5, 10, 20, 30, 60) -- a *screening protocol* (rank IC on the next-period return, one IC per
factor, train then holdout) rather than a single strategy. The rebuild computes that bank in
numpy on each H1 frame of the bundle, charges one trial per (factor, window), and keeps a factor
only when its rank IC holds the SAME SIGN on the chronological holdout as on the train span.

WHY NOT THE UPSTREAM. `pyqlib==0.9.6` has no distribution for the box's interpreter (measured
in sandbox_install_ledger: PERMANENTLY_UNAVAILABLE) and needs a `provider_uri` data directory
of China A-share bars; its benchmark universe is the event lane. The OPERATORS transfer; the
universe does not.

THE DOOR. Each surviving factor maps to the family whose mechanism it measures (a positive
holdout IC on ROC/MA/RSV-high is persistence -> momentum_volgate / trend_ma_cross; a negative
one is reversion -> mean_reversion_rsi / mean_reversion_bollinger; STD/VSTD/KLEN -> squeeze;
VMA/CNTP volume shape -> volume_spike) at the factor's own window.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "qlib"
CAPABILITY_FAMILY = "representation_learning"
LICENCE_EXPECTED = "MIT"
MODULE = "qlib"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (Alpha158 factor screen, rebuilt)"
WINDOWS: tuple[int, ...] = (5, 10, 20, 30, 60)
HORIZON = 12
TOP_PER_FRAME = 2

#: factor -> the mechanism kind a POSITIVE holdout IC means (a negative IC flips persistence
#: into reversion; volatility and volume shapes keep their own kind).
KIND_OF: dict[str, str] = {"ROC": "momentum", "MA": "trend", "RSV": "momentum",
                           "QTLU": "momentum", "IMAX": "momentum", "BETA": "trend",
                           "RSQR": "trend", "RESI": "momentum", "CNTP": "momentum",
                           "SUMP": "momentum", "STD": "squeeze", "VSTD": "volume",
                           "VMA": "volume", "CORR": "volume", "KMID": "momentum"}


def alpha158(a: dict[str, Any], w: int) -> dict[str, Any]:
    """The Alpha158 operators at window w, each normalised by the close as Qlib does."""
    import numpy as np
    c, h, lo, o, v = a["c"], a["h"], a["l"], a["o"], a["v"]
    n = c.shape[0]
    cp = np.maximum(c, 1e-12)
    out: dict[str, Any] = {}
    out["KMID"] = (c - o) / np.maximum(o, 1e-12)
    lag = np.full(n, np.nan)
    lag[w:] = c[:-w]
    out["ROC"] = lag / cp
    out["MA"] = K.sma(c, w) / cp
    out["STD"] = K.rolling_std(c, w) / cp
    hi = np.full(n, np.nan)
    lw = np.full(n, np.nan)
    for i in range(w - 1, n):
        hi[i] = float(np.max(h[i - w + 1:i + 1]))
        lw[i] = float(np.min(lo[i - w + 1:i + 1]))
    out["RSV"] = (c - lw) / np.maximum(hi - lw, 1e-12)
    out["IMAX"] = np.array([float(np.argmax(h[i - w + 1:i + 1])) / w if i >= w - 1 else np.nan
                            for i in range(n)])
    t = np.arange(w, dtype=float)
    tc = t - t.mean()
    beta = np.full(n, np.nan)
    rsq = np.full(n, np.nan)
    resi = np.full(n, np.nan)
    for i in range(w - 1, n):
        y = c[i - w + 1:i + 1]
        b = float(np.dot(tc, y - y.mean()) / np.dot(tc, tc))
        fit = y.mean() + b * tc
        ss = float(np.sum((y - y.mean()) ** 2))
        beta[i] = b / max(c[i], 1e-12)
        rsq[i] = 1.0 - float(np.sum((y - fit) ** 2)) / ss if ss > 0 else np.nan
        resi[i] = (y[-1] - fit[-1]) / max(c[i], 1e-12)
    out["BETA"], out["RSQR"], out["RESI"] = beta, rsq, resi
    up = np.diff(c, prepend=c[0]) > 0
    out["CNTP"] = K.sma(up.astype(float), w)
    d = np.diff(c, prepend=c[0])
    pos = K.sma(np.maximum(d, 0.0), w)
    tot = K.sma(np.abs(d), w)
    out["SUMP"] = pos / np.maximum(tot, 1e-12)
    vv = np.maximum(v, 0.0)
    out["VMA"] = K.sma(vv, w) / np.maximum(vv + 1e-12, 1e-12)
    out["VSTD"] = K.rolling_std(vv, w) / np.maximum(vv + 1e-12, 1e-12)
    corr = np.full(n, np.nan)
    lv = np.log1p(vv)
    for i in range(w - 1, n):
        x, y = c[i - w + 1:i + 1], lv[i - w + 1:i + 1]
        sx, sy = float(np.std(x)), float(np.std(y))
        if sx > 0 and sy > 0:
            corr[i] = float(np.mean((x - x.mean()) * (y - y.mean())) / (sx * sy))
    out["CORR"] = corr
    return out


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        if deadline.expired():
            break
        a = K.arrays(f)
        fwd = K.forward_return(a["c"], HORIZON)
        cut = K.split(a["c"].shape[0])
        rows: list[dict[str, Any]] = []
        for w in WINDOWS:
            if deadline.expired():
                break
            for name, x in alpha158(a, w).items():
                trials += 1
                ic_tr = K.rank_ic(x[:cut], fwd[:cut])
                ic_ho = K.rank_ic(x[cut:], fwd[cut:])
                stable = ic_tr != 0 and np.sign(ic_tr) == np.sign(ic_ho)
                rows.append({"factor": name, "window": w, "ic_train": round(ic_tr, 5),
                             "ic_holdout": round(ic_ho, 5), "sign_stable": bool(stable),
                             "holdout_t": abs(ic_ho) if stable else float("nan")})
        reps.append({"kind": "alpha158_ic_table", "symbol": f.symbol, "horizon_bars": HORIZON,
                     "rows": sorted(rows, key=lambda r: -abs(r["ic_holdout"]))[:20]})
        for r in K.best(rows)[:TOP_PER_FRAME]:
            kind = KIND_OF.get(str(r["factor"]), "momentum")
            if kind in ("momentum", "trend") and float(r["ic_holdout"]) < 0:
                kind = "reversion" if kind == "momentum" else "band_reversion"
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: Qlib Alpha158 {r['factor']}{r['window']} kept the sign of its "
                f"rank IC from train ({r['ic_train']:+.3f}) to holdout ({r['ic_holdout']:+.3f}) "
                f"on the {HORIZON}-bar return; a {kind} hypothesis at that window",
                horizon_label=bundle.horizons[-1], ev={k: r[k] for k in (
                    "factor", "window", "ic_train", "ic_holdout")},
                window=int(r["window"]), horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "Alpha158 operator bank + rank-IC screen",
                              "pyqlib has no wheel for the box interpreter and needs an A-share "
                              "provider_uri; the operators are reproduced in numpy")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
