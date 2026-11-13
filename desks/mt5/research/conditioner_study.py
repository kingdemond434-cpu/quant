#!/usr/bin/env python3
"""HMM, GARCH AND BAYES AS CONDITIONERS, THE WAY FUNDS USE THEM: scored out of sample.

    python desks/mt5/research/conditioner_study.py [--symbol EURUSD ...] [--budget-s 2400]

THE QUESTION (principal, 2026-11-13): "how does ours not, funds literally have edges from them".
The desk's 2026-09-30 HMM test was a blunt on/off gate on a thin book (D-20260930-007: the gold
HMM conditioning lost 0.10 log/yr, CI spanning zero). Funds do not use these models as edges;
they use them to WEIGHT and SIZE many weak signals. This study does exactly that, on one book of
many members, and asks whether each conditioner adds E[log W] out of sample:

    ew          every member equally weighted                                   (the baseline)
    raw         weight ~ max(mean, 0) / variance, from the training window, UNSHRUNK
    bayes       the same, with each member's mean shrunk by empirical Bayes toward the pooled
                mean (James-Stein: B = noise var / (noise var + between-member var))
    hmm         bayes, with each member's mean estimated INSIDE its symbol's current HMM
                volatility state and shrunk toward its unconditional mean (hierarchical): the
                regime chooses the weights, it never switches a member off by fiat
    hmm_garch   hmm, with each member's weight scaled by clip(sigma_bar / sigma_hat) from its
                symbol's walk-forward GARCH forecast (two-sided)

MEMBERS: every price-only base family of `regime_split_miner.BASE_FAMILIES` at its defaults, on
every symbol, screened by `proposer_common.screen` net of the instrument's round trip -- the same
cheap weak signals the weak-signal compiler combines. A member's daily return is the sum of its
net trade log returns by entry day.

OUT OF SAMPLE: expanding training window (MIN_TRAIN_DAYS first), weights frozen and applied to
the next TEST_DAYS, refit, repeat. Every variant is scaled to the same training-window volatility
(TARGET_VOL), so a variant wins by TIMING and SELECTION, never by leverage. The HMM state for day
t is filtered from returns before t on a model fitted before the block; the GARCH forecast for t
uses returns before t.

THE JUDGE'S CHARGES: each variant's per-day log-growth difference against `ew` gets a
stationary block-bootstrap 90% CI; the one-sided p-values are Holm-adjusted across the four
variants tested, and every variant ever run is counted in the report. A variant EARNS only when
its Holm-adjusted p <= 0.05 AND its CI lower bound is above zero.

Writes reports/CONDITIONER_STUDY.json. Sizes nothing; a variant that EARNS goes to the weak-signal
compiler as a recipe through its own door.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.hmm import GaussianHMM  # noqa: E402
from libs.research import garch as G  # noqa: E402

from research import proposer_common as pc  # noqa: E402

REPORT = _DESK / "reports" / "CONDITIONER_STUDY.json"
VARIANTS = ("ew", "raw", "bayes", "hmm", "hmm_garch")
TESTED = VARIANTS[1:]
MIN_TRAIN_DAYS = 756
TEST_DAYS = 126
TARGET_VOL = 0.10 / math.sqrt(252)
MIN_MEMBER_TRADES = 20
MIN_STATE_DAYS = 40
W_MIN, W_MAX = 0.5, 2.0
BLOCK = 20
HMM_REFIT_DAYS = 252
CORE = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY",
        "GBPJPY", "AUDJPY", "XAUUSD", "XAGUSD")


# ----------------------------------------------------------------------------- members
def _daily_close(d: pd.DataFrame) -> pd.Series:
    c = pd.to_numeric(d["close"], errors="coerce")
    c = c[np.isfinite(c) & (c > 0)]
    day = c.index.floor("D")
    n = c.groupby(day).size()
    return c.groupby(day).last()[n >= 12]


def members_for(sym: str, d: pd.DataFrame, meta: dict) -> dict[str, pd.Series]:
    """member name -> net daily log return by entry day (0 on days it took no trade)."""
    from research import regime_split_miner as rsm
    cost = pc.cost_frac(sym, meta, d["close"])
    if cost is None:
        return {}
    unfillable = pc.artifact_hours(d)
    out: dict[str, pd.Series] = {}
    days = d.index.floor("D")
    for base in rsm.BASE_FAMILIES:
        fn = rsm._base_fn(base)
        if fn is None:
            continue
        try:
            sc = pc.screen(d, fn(d), cost, unfillable, detail=True)
        except Exception:      # a family that cannot run on this symbol is not a member
            continue
        if not sc or len(sc.get("pnl") or []) < MIN_MEMBER_TRADES:
            continue
        net = np.asarray(sc["pnl"], dtype=float) - cost
        ent = days[np.asarray(sc["entry_pos"], dtype=int)]
        out[f"{sym}.{base}"] = pd.Series(net, index=ent).groupby(level=0).sum()
    return out


# ----------------------------------------------------------------------------- conditioners
def hmm_high_vol(r: pd.Series) -> pd.Series:
    """P(high-variance state) for day t, filtered from returns BEFORE t; 2-state HMM refit
    every HMM_REFIT_DAYS on everything before the refit point."""
    x = r.to_numpy(dtype=float)
    sd = pd.Series(x).shift(1).rolling(252, min_periods=60).std().to_numpy()
    z = np.where(np.isfinite(sd) & (sd > 0), x / np.where(sd > 0, sd, 1.0), np.nan)
    out = np.full(len(x), np.nan)
    zz = np.nan_to_num(z, nan=0.0)
    for lo in range(MIN_TRAIN_DAYS // 2, len(x), HMM_REFIT_DAYS):
        hi = min(lo + HMM_REFIT_DAYS, len(x))
        tr = zz[:lo]
        if np.isfinite(z[:lo]).sum() < 250:
            continue
        m = GaussianHMM(2, n_iter=40, seed=0).fit(tr.reshape(-1, 1))
        post = m.filter_posterior(zz[:hi].reshape(-1, 1))
        hi_state = int(np.argmax(m.vars[:, 0]))
        # posterior after day t-1 is the state belief FOR day t
        out[lo:hi] = post[lo - 1:hi - 1, hi_state]
    return pd.Series(out, index=r.index)


def garch_weight(r: pd.Series) -> pd.Series:
    var = pd.Series(G.walk_forward_variance(r.to_numpy(dtype=float)), index=r.index)
    v = var.where(var > 0)
    ref = v.shift(1).rolling(252, min_periods=126).mean()
    return np.sqrt(ref / v).clip(W_MIN, W_MAX)


def eb_shrink(means: np.ndarray, se2: np.ndarray) -> np.ndarray:
    """James-Stein / empirical Bayes: shrink each mean toward the precision-weighted pooled mean
    by B_i = se2_i / (se2_i + tau2), tau2 the method-of-moments between-member variance."""
    ok = np.isfinite(means) & np.isfinite(se2) & (se2 > 0)
    if ok.sum() < 3:
        return np.where(ok, means, 0.0)
    w = 1.0 / se2[ok]
    grand = float(np.sum(w * means[ok]) / np.sum(w))
    tau2 = max(float(np.var(means[ok]) - np.mean(se2[ok])), 0.0)
    b = se2 / (se2 + tau2) if tau2 > 0 else np.ones_like(se2)
    return np.where(ok, grand + (1.0 - b) * (means - grand), 0.0)


def _stats(x: np.ndarray) -> tuple[float, float, float]:
    n = np.isfinite(x).sum()
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    m = float(np.nanmean(x))
    v = float(np.nanvar(x, ddof=1))
    return m, v, v / n


def fit_weights(train: pd.DataFrame, state_tr: pd.DataFrame | None,
                state_now: pd.Series | None, variant: str) -> pd.Series:
    """Member weights for ONE test day's state (variant hmm) or for the whole block (others)."""
    cols = train.columns
    if variant == "ew":
        return pd.Series(1.0, index=cols)
    m = np.empty(len(cols))
    v = np.empty(len(cols))
    s2 = np.empty(len(cols))
    for j, c in enumerate(cols):
        m[j], v[j], s2[j] = _stats(train[c].to_numpy())
    if variant == "raw":
        mu = m
    else:
        mu = eb_shrink(m, s2)
    if variant in ("hmm", "hmm_garch") and state_tr is not None and state_now is not None:
        mu_c = mu.copy()
        for j, c in enumerate(cols):
            st = state_now.get(c)
            if st is None or not np.isfinite(st):
                continue
            inside = (state_tr[c] > 0.5) == (st > 0.5)
            x = train[c][inside.reindex(train.index).fillna(False).to_numpy()].to_numpy()
            if len(x) < MIN_STATE_DAYS:
                continue
            ms, _vs, s2s = _stats(x)
            # hierarchical: the in-state mean shrunk toward the member's shrunk unconditional
            # mean, by the same James-Stein weight with tau2 = the between-state spread
            tau2 = (ms - mu[j]) ** 2
            b = s2s / (s2s + tau2) if tau2 > 0 else 1.0
            mu_c[j] = mu[j] + (1.0 - b) * (ms - mu[j])
        mu = mu_c
    w = np.where(np.isfinite(v) & (v > 0), np.maximum(mu, 0.0) / v, 0.0)
    return pd.Series(w, index=cols)


def _scale(train_ret: pd.Series) -> float:
    sd = float(train_ret.std(ddof=1))
    return TARGET_VOL / sd if np.isfinite(sd) and sd > 0 else 0.0


def walk_forward(M: pd.DataFrame, state: pd.DataFrame, gw: pd.DataFrame,
                 diag: dict[str, Any] | None = None) -> dict[str, pd.Series]:
    """Out-of-sample daily book returns per variant, every variant on the same days. `diag`,
    when given, receives per block how many members sat out (too few training trades to have a
    measurable mean), so a book that drops members says so."""
    days = M.index
    out: dict[str, list[pd.Series]] = {v: [] for v in VARIANTS}
    for lo in range(MIN_TRAIN_DAYS, len(days), TEST_DAYS):
        hi = min(lo + TEST_DAYS, len(days))
        tr, te = M.iloc[:lo], M.iloc[lo:hi]
        st_tr = state.iloc[:lo]
        live = tr.columns[(tr != 0).sum() >= MIN_MEMBER_TRADES]
        if diag is not None:
            diag.setdefault("members_sat_out_by_block", []).append(
                {"block_start": str(days[lo].date()), "sat_out": int(len(tr.columns) - len(live)),
                 "of": int(len(tr.columns))})
        if len(live) < 3:
            continue
        tr, te, st_tr = tr[live], te[live], st_tr[live]
        for v in ("ew", "raw", "bayes"):
            w = fit_weights(tr, None, None, v)
            k = _scale(tr @ w)
            out[v].append(te @ (w * k))
        # hmm / hmm_garch: weights for each test day from that day's (pre-day) state
        # GROSS-MATCHED to the bayes book every day: the regime may move weight between
        # members, never add exposure, so a win is selection and not leverage. The GARCH weight
        # on top is the two-sided exposure change being tested.
        w_b = fit_weights(tr, None, None, "bayes")
        gross = float(w_b.abs().sum())
        rows_h, rows_g = [], []
        for t in te.index:
            w = fit_weights(tr, st_tr, state.loc[t, live], "hmm")
            gh = float(w.abs().sum())
            w = w * (gross / gh) if gh > 0 else w_b
            rows_h.append(float(te.loc[t] @ w))
            g = gw.loc[t, live].fillna(1.0)
            rows_g.append(float(te.loc[t] @ (w * g)))
        k = _scale(tr @ w_b)
        out["hmm"].append(pd.Series(rows_h, index=te.index) * k)
        out["hmm_garch"].append(pd.Series(rows_g, index=te.index) * k)
    return {v: (pd.concat(s) if s else pd.Series(dtype=float)) for v, s in out.items()}


# ----------------------------------------------------------------------------- the charges
def _block_boot(d: np.ndarray, reps: int, seed: int = 5) -> np.ndarray:
    n = len(d)
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    p = 1.0 / BLOCK
    for b in range(reps):
        i = int(rng.integers(n))
        idx = np.empty(n, dtype=np.int64)
        jumps = rng.random(n) < p
        starts = rng.integers(n, size=n)
        for k in range(n):
            idx[k] = i
            i = int(starts[k]) if jumps[k] else (i + 1) % n
        means[b] = d[idx].mean()
    return means


def judge(book: dict[str, pd.Series], reps: int) -> dict[str, Any]:
    lg = {v: np.log(np.maximum(1.0 + s.to_numpy(), 1e-9)) for v, s in book.items()}
    out: dict[str, Any] = {"elogw_yr": {v: round(252 * float(x.mean()), 5)
                                         for v, x in lg.items()},
                           "vol_yr": {v: round(float(s.std(ddof=1)) * math.sqrt(252), 4)
                                      for v, s in book.items()},
                           "days": int(len(book["ew"]))}
    ps: dict[str, float] = {}
    rows: dict[str, Any] = {}
    for v in TESTED:
        d = lg[v] - lg["ew"]
        bm = _block_boot(d, reps)
        p = float((bm <= 0).mean())
        lo, hi = np.quantile(bm, [0.05, 0.95])
        ps[v] = p
        rows[v] = {"delta_vs_ew_yr": round(252 * float(d.mean()), 5),
                   "ci90_yr": [round(252 * float(lo), 5), round(252 * float(hi), 5)],
                   "p_one_sided": round(p, 4)}
    order = sorted(ps, key=lambda k: ps[k])
    run = 0.0
    for i, v in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * ps[v]))
        rows[v]["p_holm"] = round(run, 4)
        rows[v]["EARNS"] = bool(run <= 0.05 and rows[v]["ci90_yr"][0] > 0)
    out["vs_ew"] = rows
    # the marginal value of each conditioner over the one it builds on
    pairs = (("bayes", "raw"), ("hmm", "bayes"), ("hmm_garch", "hmm"))
    out["marginal"] = {}
    for a, b in pairs:
        d = lg[a] - lg[b]
        bm = _block_boot(d, reps, seed=9)
        lo, hi = np.quantile(bm, [0.05, 0.95])
        out["marginal"][f"{a}_over_{b}"] = {
            "delta_yr": round(252 * float(d.mean()), 5),
            "ci90_yr": [round(252 * float(lo), 5), round(252 * float(hi), 5)]}
    out["variants_tested"] = len(TESTED)
    return out


def run(symbols: list[str] | None = None, budget_s: float = 2400.0, reps: int = 1000
        ) -> dict[str, Any]:
    t0 = time.monotonic()
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = [s for s in (symbols or CORE) if s in have]
    members: dict[str, pd.Series] = {}
    sym_ret: dict[str, pd.Series] = {}
    skipped: dict[str, str] = {}
    for s in todo:
        if time.monotonic() - t0 > budget_s * 0.6:
            skipped[s] = "member budget exhausted"
            continue
        d = pc.bars(s)
        if d is None or len(d) < 24 * 900:
            skipped[s] = "under 900 days of H1 bars"
            continue
        got = members_for(s, d, meta)
        if not got:
            skipped[s] = "no member cleared MIN_MEMBER_TRADES (or no contract terms)"
            continue
        members.update(got)
        c = _daily_close(d)
        sym_ret[s] = np.log(c).diff().dropna()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    if len(members) < 6:
        rep: dict[str, Any] = {"generated_at": now, "status": "UNMEASURED",
                               "why": f"{len(members)} members", "skipped": skipped}
    else:
        days = sorted(set().union(*[set(r.index) for r in sym_ret.values()]))
        idx = pd.DatetimeIndex(days)
        M = pd.DataFrame({k: v.reindex(idx).fillna(0.0) for k, v in members.items()})
        st_sym = {s: hmm_high_vol(r.reindex(idx).fillna(0.0)) for s, r in sym_ret.items()}
        gw_sym = {s: garch_weight(r.reindex(idx).fillna(0.0)) for s, r in sym_ret.items()}
        state = pd.DataFrame({k: st_sym[k.split(".")[0]] for k in M.columns})
        gw = pd.DataFrame({k: gw_sym[k.split(".")[0]] for k in M.columns})
        diag: dict[str, Any] = {}
        book = walk_forward(M, state, gw, diag)
        rep = {"generated_at": now, "status": "MEASURED", "symbols": sorted(sym_ret),
               "members": int(M.shape[1]), "skipped": skipped, **diag,
               "design": {"min_train_days": MIN_TRAIN_DAYS, "test_days": TEST_DAYS,
                          "target_vol_yr": round(TARGET_VOL * math.sqrt(252), 4),
                          "block_days": BLOCK, "boot_reps": reps,
                          "earns": "Holm-adjusted one-sided p <= 0.05 across the variants AND "
                                   "the CI lower bound above zero"},
               "prior_test": "D-20260930-007: HMM as an on/off gate on the gold book lost "
                             "0.10 log/yr (CI spanned zero) -- a gate, not a conditioner",
               **judge(book, reps)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=2400.0)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args(argv)
    rep = run(a.symbol, a.budget_s, a.boot)
    print(json.dumps({k: rep.get(k) for k in ("status", "why", "members", "elogw_yr", "vol_yr",
                                               "vs_ew", "marginal")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
