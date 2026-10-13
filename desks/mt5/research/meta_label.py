#!/usr/bin/env python3
"""META-LABEL CONDITIONER -- a second-stage take/skip (and size-tilt) model over existing edges.

WHAT IT IS. Every certified and forward sleeve writes its replayed trades to
`reports/shadow/**/ledger_*.json` (`shadow_forward.py`: entry/exit time, side, R, phase). The
BASE rule decides WHEN to trade; this organ asks a narrower question of every signal the base
rule already fired: given the point-in-time cross-asset and macro state at signal time, was this
one worth taking? It is Lopez de Prado's meta-labelling: label = 1 if the trade's R > 0, a
ridge-logistic model over state features, take when P(win) >= threshold, and tilt size by P.

IT FILTERS, IT DOES NOT RE-TEST THE BASE RULE. The base rule's trades are fixed inputs; the only
new degrees of freedom are the conditioner VARIANTS (feature set x threshold), and each one is
charged ONCE as a trial over its lifetime (`data/meta_label_charged.json` -> a row in
`data/null_pass_trials.jsonl`, which `libs.research.experiment_ledger` already sums). Nothing is
donated, so it is a null pass by that ledger's own definition.

POINT IN TIME. Features come from `libs.portfolio.leg_factors.daily_factor_returns` (currency
basket legs from the H1 tape, daily VIX / 10-year changes from the macro archive). A trade
entered on broker date E reads currency rows with date < E (the day closed before the signal)
and macro rows with date < E - 1 (FRED prints a day's close the next morning). The model that
scores a trade is fitted only on trades whose EXIT + `EMBARGO_H` precedes that trade's ENTRY --
purged, embargoed, expanding walk-forward. No trade is ever scored by a model that saw it.

THE BAR. The quantity judged is the filter's own per-signal value d_i = R_i * take_i - R_i
(what skipping bought) on FORWARD-phase trades only, under the Tier S deflated-Sharpe bar:
`libs.validation.dsr.deflated_sharpe_ratio` with N = max(5, variants charged), Var(SR) =
1/(T-1), DSR >= 0.95 (t ~ 2.84 at N = 5). Lift per sleeve is reported with a seeded bootstrap
95% CI; a sleeve with too few forward trades is UNMEASURED with its n, never a zero.

REPORT ONLY. No money path reads META_LABEL.json; no veto, cap or size change is applied, so no
rails / missed-growth registration is owed (GROWTH_GOVERNANCE Rule 1 binds the day it sizes).

    python desks/mt5/research/meta_label.py --once
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHADOW_DIR = DESK / "reports" / "shadow"
OUT = DESK / "reports" / "META_LABEL.json"
CHARGED = DESK / "data" / "meta_label_charged.json"
TRIALS = DESK / "data" / "null_pass_trials.jsonl"

SCHEMA = "meta-label-1"
UNMEASURED = "UNMEASURED"
FAMILY = "meta_label"
#: Hours after a training trade's exit before a scored trade may enter (purge + embargo).
EMBARGO_H = 24
#: Labelled trades a model needs before it may score anything; below it the trade is unscored.
MIN_TRAIN = 40
#: Forward trades a sleeve needs before its lift is a number.
MIN_FORWARD = 10
#: The Tier S bar: minimum trial count, DSR threshold.
TIER_S_MIN_N = 5
DSR_THRESHOLD = 0.95
RIDGE = 1.0
BOOT = 2000
SEED = 20261013

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "pair": ("mom5_aligned", "vol_ratio"),
    "pair_macro": ("mom5_aligned", "vol_ratio", "d_vix5", "d_r10_5"),
    "full": ("mom5_aligned", "vol_ratio", "d_vix5", "d_r10_5", "dispersion5"),
}


@dataclass(frozen=True)
class Variant:
    features: str
    threshold: float

    @property
    def trial_id(self) -> str:
        spec = json.dumps({"family": FAMILY, "features": FEATURE_SETS[self.features],
                           "threshold": self.threshold, "embargo_h": EMBARGO_H,
                           "ridge": RIDGE, "label": "R>0"}, sort_keys=True)
        return "ml_" + hashlib.sha256(spec.encode()).hexdigest()[:16]


#: Five variants -- the Tier S N. Every one is charged; adding one here charges one more.
VARIANTS: tuple[Variant, ...] = (
    Variant("pair", 0.5), Variant("pair_macro", 0.5), Variant("full", 0.5),
    Variant("full", 0.45), Variant("full", 0.55))


@dataclass
class Trade:
    sleeve: str
    symbol: str
    entry: datetime
    exit: datetime
    side: int
    r: float
    forward: bool


def _ts(v: Any) -> datetime | None:
    try:
        import pandas as pd
        t = pd.Timestamp(v)
    except (ValueError, TypeError):
        return None
    if t is pd.NaT:
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.to_pydatetime()


def load_trades(shadow_dir: Path = SHADOW_DIR) -> list[Trade]:
    """Every replayed trade of every sleeve ledger under `shadow_dir`, sorted by entry."""
    out: list[Trade] = []
    for f in sorted(glob.glob(str(shadow_dir / "**" / "ledger_*.json"), recursive=True)):
        p = Path(f)
        sleeve = p.stem[len("ledger_"):]
        symbol = sleeve.split("_", 1)[0]
        try:
            rows = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            e, x = _ts(row.get("entry_time")), _ts(row.get("exit_time"))
            try:
                r = float(row.get("r_multiple"))
                side = int(row.get("side") or 0)
            except (TypeError, ValueError):
                continue
            if e is None or x is None or not math.isfinite(r):
                continue
            out.append(Trade(sleeve, symbol, e, x, side, r, row.get("phase") == "forward"))
    out.sort(key=lambda t: (t.entry, t.sleeve))
    return out


def _factor_frame() -> Any:
    try:
        from libs.portfolio.leg_factors import daily_factor_returns
        return daily_factor_returns()
    except Exception:
        return None


def build_features(trades: Sequence[Trade], frame: Any) -> np.ndarray:
    """(n, 5) features in FEATURE_SETS['full'] order, NaN where the state is not knowable.

    Currency rows strictly before the entry's date; macro rows strictly before entry date - 1."""
    names = FEATURE_SETS["full"]
    X = np.full((len(trades), len(names)), np.nan)
    if frame is None or len(trades) == 0:
        return X
    try:
        from libs.risk.fx_factors import split_pair
    except ImportError:
        return X
    idx = np.array([str(d) for d in frame.index])
    ccy_cols = [c for c in frame.columns if c not in ("d_vix", "d_r10")]
    disp = frame[ccy_cols].std(axis=1).to_numpy(dtype=float) if ccy_cols else None
    cols = {c: frame[c].to_numpy(dtype=float) for c in frame.columns}

    def win(a: np.ndarray, end: int, n: int) -> np.ndarray:
        w = a[max(0, end - n):end]
        return w[np.isfinite(w)]

    for i, t in enumerate(trades):
        d = t.entry.date()
        end = int(np.searchsorted(idx, d.isoformat(), side="left"))          # rows < d
        mend = int(np.searchsorted(idx, (d - timedelta(days=1)).isoformat(), side="left"))
        pair = split_pair(t.symbol)
        if pair and pair[0] in cols and pair[1] in cols:
            leg = cols[pair[0]] - cols[pair[1]]
            m5 = win(leg, end, 5)
            if m5.size >= 3:
                X[i, 0] = float(m5.sum()) * (1 if t.side >= 0 else -1)
            s20, s120 = win(leg, end, 20), win(leg, end, 120)
            if s20.size >= 10 and s120.size >= 60 and np.std(s120) > 0:
                X[i, 1] = float(np.std(s20) / np.std(s120))
        for j, name in ((2, "d_vix"), (3, "d_r10")):
            if name in cols:
                w = win(cols[name], mend, 5)
                if w.size >= 3:
                    X[i, j] = float(w.sum())
        if disp is not None:
            w = win(disp, end, 5)
            if w.size >= 3:
                X[i, 4] = float(w.mean())
    return X


def _fit_logit(X: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    """Ridge logistic regression by Newton steps; intercept unpenalised. X carries a 1s column."""
    w = np.zeros(X.shape[1])
    pen = np.full(X.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(25):
        z = np.clip(X @ w, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        g = X.T @ (p - y) + pen * w
        h = (X * (p * (1 - p))[:, None]).T @ X + np.diag(pen + 1e-9)
        step = np.linalg.solve(h, g)
        w -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return w


def walk_forward(trades: Sequence[Trade], X: np.ndarray, cols: Sequence[int]) -> np.ndarray:
    """Out-of-sample P(win) per trade (NaN when unscorable), purged and embargoed.

    One fit per distinct entry date: the training set for every trade entered on date D is the
    trades whose exit + EMBARGO_H <= the earliest entry on D, so no score saw its own outcome or
    any outcome overlapping it."""
    n = len(trades)
    p = np.full(n, np.nan)
    if n == 0:
        return p
    Xs = X[:, list(cols)]
    ok = np.all(np.isfinite(Xs), axis=1)
    y = np.array([1.0 if t.r > 0 else 0.0 for t in trades])
    exits = np.array([(t.exit + timedelta(hours=EMBARGO_H)).timestamp() for t in trades])
    by_day: dict[date, list[int]] = {}
    for i, t in enumerate(trades):
        by_day.setdefault(t.entry.date(), []).append(i)
    for _day, members in sorted(by_day.items()):
        cutoff = min(trades[i].entry.timestamp() for i in members)
        tr = np.where(ok & (exits <= cutoff))[0]
        if tr.size < MIN_TRAIN or len(set(y[tr])) < 2:
            continue
        mu = Xs[tr].mean(axis=0)
        sd = Xs[tr].std(axis=0)
        sd[sd == 0] = 1.0
        A = np.column_stack([np.ones(tr.size), (Xs[tr] - mu) / sd])
        w = _fit_logit(A, y[tr])
        for i in members:
            if ok[i]:
                z = float(np.clip(w[0] + ((Xs[i] - mu) / sd) @ w[1:], -30, 30))
                p[i] = 1.0 / (1.0 + math.exp(-z))
    return p


def _boot_ci(d: np.ndarray, seed: int = SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(d, size=(BOOT, d.size), replace=True).mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def lift(r: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, Any]:
    """With-vs-without filter on scored trades. UNMEASURED below MIN_FORWARD."""
    n = int(r.size)
    if n < MIN_FORWARD:
        return {"status": UNMEASURED, "n": n,
                "why": f"{n} scored forward trades < {MIN_FORWARD}"}
    take = p >= threshold
    d = np.where(take, 0.0, -r)                      # what skipping bought, per signal
    tilt = np.clip(0.5 + p, 0.5, 1.5)
    lo, hi = _boot_ci(d)
    return {"status": "MEASURED", "n": n, "n_taken": int(take.sum()),
            "r_per_trade_without": float(r.mean()),
            "r_per_trade_with": float(r[take].mean()) if take.any() else UNMEASURED,
            "r_per_signal_with": float((r * take).mean()),
            "lift_r_per_signal": float(d.mean()), "lift_ci95": [lo, hi],
            "r_per_unit_size_tilted": float((tilt * r).sum() / tilt.sum())}


def tier_s_judge(d: np.ndarray, n_trials: int) -> dict[str, Any]:
    T = int(d.size)
    if T < MIN_FORWARD or float(np.std(d, ddof=1)) == 0.0:
        return {"status": UNMEASURED, "T": T,
                "why": "too few forward trades or a degenerate filter series"}
    from libs.validation.dsr import deflated_sharpe_ratio
    n = max(TIER_S_MIN_N, n_trials)
    res = deflated_sharpe_ratio(d, n_trials=n, variance_of_sharpes=1.0 / (T - 1),
                                threshold=DSR_THRESHOLD)
    return {"status": "PASS" if res.passed else "FAIL", "T": T, "n_trials": n,
            "sr": float(res.sr_observed), "sr0": float(res.sr0_threshold),
            "dsr": float(res.dsr), "threshold": DSR_THRESHOLD,
            "rule": "PSR(d) vs E[max SR] over N=max(5, charged variants), Var(SR)=1/(T-1)"}


def charge(variants: Sequence[Variant] = VARIANTS, *, charged: Path = CHARGED,
           trials: Path = TRIALS) -> tuple[int, int]:
    """(newly charged, lifetime union). Each variant id is charged exactly once, ever."""
    try:
        union = json.loads(charged.read_text("utf-8"))
        union = union if isinstance(union, dict) else {}
    except (OSError, ValueError):
        union = {}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    new = [v.trial_id for v in variants if v.trial_id not in union]
    for tid in new:
        union[tid] = now
    if new:
        charged.parent.mkdir(parents=True, exist_ok=True)
        tmp = charged.with_suffix(".tmp")
        tmp.write_text(json.dumps(union, sort_keys=True), "utf-8")
        tmp.replace(charged)
        with trials.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now, "source": "meta_label", "tests_run": len(new),
                                 "by_family": {FAMILY: len(new)}, "trial_ids": new,
                                 "rule": "each conditioner variant charged once over its "
                                         "lifetime; nothing donated"}) + "\n")
    return len(new), len(union)


def run(shadow_dir: Path = SHADOW_DIR, out: Path | None = OUT, *, frame: Any = None,
        charged: Path = CHARGED, trials: Path = TRIALS) -> dict[str, Any]:
    trades = load_trades(shadow_dir)
    frame = _factor_frame() if frame is None else frame
    X = build_features(trades, frame)
    new, union = charge(charged=charged, trials=trials)
    names = FEATURE_SETS["full"]
    fwd = np.array([t.forward for t in trades], dtype=bool)
    r_all = np.array([t.r for t in trades])
    variants: list[dict[str, Any]] = []
    for v in VARIANTS:
        cols = [names.index(c) for c in FEATURE_SETS[v.features]]
        p = walk_forward(trades, X, cols)
        scored = fwd & np.isfinite(p)
        pooled = lift(r_all[scored], p[scored], v.threshold)
        d = np.where(p[scored] >= v.threshold, 0.0, -r_all[scored])
        per: dict[str, Any] = {}
        for s in sorted({t.sleeve for t in trades if t.forward}):
            m = scored & np.array([t.sleeve == s for t in trades])
            per[s] = lift(r_all[m], p[m], v.threshold)
        variants.append({"trial_id": v.trial_id, "features": list(FEATURE_SETS[v.features]),
                         "threshold": v.threshold, "n_oos_scored": int(np.isfinite(p).sum()),
                         "pooled_forward": pooled, "tier_s": tier_s_judge(d, union),
                         "per_sleeve": per})
    measured = [v for v in variants if v["pooled_forward"]["status"] == "MEASURED"]
    best = max(measured, key=lambda v: v["pooled_forward"]["lift_r_per_signal"], default=None)
    n_fwd = int(fwd.sum())
    status = ("MEASURED" if measured else UNMEASURED)
    doc = {"schema": SCHEMA, "generated_utc": datetime.now(tz=UTC).isoformat(),
           "status": status,
           "why": (None if measured else
                   f"{len(trades)} trades on disk ({n_fwd} forward); a variant needs "
                   f"{MIN_TRAIN} purged training trades and {MIN_FORWARD} scored forward ones"),
           "n_trades": len(trades), "n_forward": n_fwd,
           "n_sleeves": len({t.sleeve for t in trades}),
           "features_knowable_share": (float(np.isfinite(X).all(axis=1).mean())
                                       if len(trades) else UNMEASURED),
           "feature_knowable_share": {
               n: (float(np.isfinite(X[:, j]).mean()) if len(trades) else UNMEASURED)
               for j, n in enumerate(names)},
           "factor_frame": "PRESENT" if frame is not None else UNMEASURED,
           "trials": {"variants": len(VARIANTS), "newly_charged": new, "lifetime": union,
                      "ledger": "desks/mt5/data/null_pass_trials.jsonl (family meta_label)"},
           "best_variant": best["trial_id"] if best else None,
           "best_tier_s": best["tier_s"]["status"] if best else UNMEASURED,
           "variants": variants,
           "embargo_h": EMBARGO_H, "min_train": MIN_TRAIN, "min_forward": MIN_FORWARD,
           "money_path": "NONE: report only; no consumer sizes or vetoes from this file",
           "rule": ("label R>0; ridge logit on PIT state (currency rows < entry date, macro "
                    "rows < entry date - 1); trained only on trades whose exit + embargo "
                    "precedes the scored entry; lift judged on forward-phase trades only")}
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(out)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--shadow-dir", type=Path, default=SHADOW_DIR)
    a = ap.parse_args(argv)
    doc = run(a.shadow_dir)
    print(f"meta_label: {doc['status']} trades={doc['n_trades']} forward={doc['n_forward']} "
          f"best={doc['best_variant']} tier_s={doc['best_tier_s']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
