"""THE WEAK-SIGNAL BOOK: every judged cell pooled into ONE book, judged out of sample as one.

WHY THIS EXISTS NEXT TO `desks/mt5/research/weak_signal_compiler.py`. That organ votes up to 24
power-deficient cells ON ONE SYMBOL into one ensemble cell. It cannot hold cells across symbols,
it never sees a cell that failed any gate other than power, and it caps the pool at 24. The
architecture that turns weak edges into wealth (many small, weakly correlated bets summed into
one book whose Sharpe grows like sqrt(breadth)) needs the whole judged universe in one pool.

WHAT IS POOLED. Every cell the gauntlet ever judged that has a daily net-R series, whatever its
verdict, plus live sleeves. Nothing is dropped for its verdict: a noisy or losing member is not
removed from the pool, it is given weight zero by the training-block fit, on evidence the test
block never saw. Selecting members by their full-history verdict would be selection on outcome,
which is the leak this desk has removed several times. Only three things refuse a member, and
each is counted: no series at all, an untradeable symbol, and fewer than `min_obs` training days.

HOW IT IS JUDGED, and none of these bars is softer than a single cell's:

  1. PURGED WALK-FORWARD. The calendar is cut into `n_blocks`. Block k is traded with weights fit
     only on days before block k minus an `embargo` gap. The book's OOS series is the
     concatenation of those test blocks; no weight ever saw a day it is scored on.
  2. DEFLATED SHARPE ON THE LIFETIME UNION. `n_trials` is the desk's lifetime trial count (the
     same charge the gauntlet uses) PLUS every combiner recipe ever run (`trials.jsonl`). An
     unmeasured lifetime count fails the gate closed; it is never read as a smaller bar.
  3. COST-AWARE TWICE. Weights are fit on the 1x-cost series; the same frozen weights must also
     earn a positive OOS mean on the 3x-cost series.
  4. MORE THAN ITS BEST PART. The OOS book must beat the OOS Sharpe of the single member a
     training block would have picked. A book that is its best leg in disguise is refused.
  5. ENOUGH OOS. At least `min_oos_days` out-of-sample days.

SIZING IS E[log W] WITHIN SURVIVAL. The unit book (gross weight 1 R) is scaled by the lambda
maximising mean log(1 + lambda r) over the OOS series, capped so that the worst OOS day stays
inside `daily_loss_cap` and the worst OOS drawdown inside `drawdown_cap`. The caps default to
HALF of the tightest firm rail (E8: 2.5% daily, 10% floor), so the book can never be the thing
that breaches a firm. The weights inside the book are the long-only shrunk Kelly solution.

PROPOSES ONLY. Nothing here arms, places or sizes a live trade. A PASS publishes the book and its
members as forward candidates; the certificate path decides the rest.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio

#: Bump when the estimator changes. Each distinct recipe digest is charged as one more trial.
RECIPE_VERSION = 1


@dataclass(frozen=True)
class BookConfig:
    """Pre-registered recipe. Every field enters the digest, so every variant is a charged trial."""
    n_blocks: int = 6
    embargo_days: int = 5
    min_obs: int = 60                 # training days a member needs before it can carry weight
    min_oos_days: int = 250
    max_active: int = 400             # members carried into the covariance solve per fold
    dedupe_corr: float = 0.90         # near-duplicates keep the stronger one
    mean_shrink_k: float = 250.0      # mu * n/(n+k): a member needs ~a year to keep half its mean
    cov_shrink: float = 0.5           # Sigma -> (1-d) Sigma + d diag(Sigma)
    dsr_bar: float = 0.95             # Tier S bar, fixed
    daily_loss_cap: float = 0.0125    # half of E8's 2.5% daily limit
    drawdown_cap: float = 0.05        # half of E8's 10% floor
    lambda_max: float = 0.10          # never more than 10% equity at risk per unit-book day
    solver_iters: int = 400

    def digest(self) -> str:
        blob = json.dumps({"v": RECIPE_VERSION, **asdict(self)}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class Pool:
    """Aligned member matrices. Missing days are 0 R (flat); `avail` marks a member's live span."""
    ids: list[str]
    dates: pd.DatetimeIndex
    r1: np.ndarray                    # T x N net R at 1x cost
    r3: np.ndarray                    # T x N net R at 3x cost (r1 where no 3x arm exists)
    avail: np.ndarray                 # T x N bool: inside [first, last] observed day
    has_3x: np.ndarray                # N bool


def build_pool(series: Mapping[str, tuple[pd.Series, pd.Series | None]]) -> Pool:
    """Align every member's daily series onto one calendar.

    A day with no trade is a 0 R day, but only between the member's first and last observed day;
    outside that span the member did not exist and `avail` is False, so training statistics never
    count invented zeros before a member's history begins.
    """
    ids = sorted(k for k, (s1, _) in series.items() if s1 is not None and len(s1))
    if not ids:
        return Pool([], pd.DatetimeIndex([]), np.zeros((0, 0)), np.zeros((0, 0)),
                    np.zeros((0, 0), bool), np.zeros(0, bool))
    idx = pd.DatetimeIndex(sorted(set().union(
        *(pd.to_datetime(series[k][0].index) for k in ids))))
    t, n = len(idx), len(ids)
    r1 = np.zeros((t, n), np.float32)
    r3 = np.zeros((t, n), np.float32)
    avail = np.zeros((t, n), bool)
    has3 = np.zeros(n, bool)
    pos = {d: i for i, d in enumerate(idx)}
    for j, k in enumerate(ids):
        s1, s3 = series[k]
        d1 = pd.to_datetime(s1.index)
        v1 = np.nan_to_num(s1.to_numpy(np.float64))
        rows = np.fromiter((pos[d] for d in d1), int, len(d1))
        r1[rows, j] = v1
        avail[rows.min():rows.max() + 1, j] = True
        if s3 is not None and len(s3):
            has3[j] = True
            d3 = pd.to_datetime(s3.index)
            rows3 = np.fromiter((pos[d] for d in d3 if d in pos), int)
            v3 = s3.to_numpy(np.float64)
            vals3 = np.nan_to_num(np.asarray(
                [v for d, v in zip(d3, v3, strict=True) if d in pos], np.float64))
            r3[rows3, j] = vals3
        else:
            r3[:, j] = r1[:, j]
    return Pool(ids, idx, r1, r3, avail, has3)


def _member_stats(r: np.ndarray, avail: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = avail.sum(0).astype(float)
    safe = np.maximum(n, 1.0)
    rm = np.where(avail, r, 0.0)
    mu = rm.sum(0) / safe
    var = (np.where(avail, (r - mu) ** 2, 0.0)).sum(0) / np.maximum(n - 1, 1.0)
    return mu, np.sqrt(var), n


def _project_nonneg(w: np.ndarray) -> np.ndarray:
    return np.maximum(w, 0.0)


def fit_weights(r: np.ndarray, avail: np.ndarray, cfg: BookConfig) -> tuple[np.ndarray, dict]:
    """Long-only shrunk Kelly weights from TRAINING rows only. Returns (w over all N, receipt).

    Kelly in the quadratic (log-growth) approximation: maximise w'mu - 0.5 w'Sigma w, w >= 0.
    The mean is shrunk toward zero by n/(n+k) and the covariance toward its diagonal, which is
    what keeps a fit over hundreds of members from reading the training block's noise as edge.
    Members with a non-positive shrunk mean, too few days, or that duplicate a stronger member
    get weight 0 IN THIS FOLD -- they stay in the pool and are re-fit next fold.
    """
    t, n = r.shape
    w = np.zeros(n)
    mu, sd, nobs = _member_stats(r, avail)
    mu_s = mu * nobs / (nobs + cfg.mean_shrink_k)
    ok = (nobs >= cfg.min_obs) & (sd > 0) & (mu_s > 0)
    receipt = {"members": n, "enough_obs": int((nobs >= cfg.min_obs).sum()),
               "positive_train_mean": int(ok.sum())}
    if not ok.any():
        receipt.update(active=0, deduped=0)
        return w, receipt
    score = np.where(ok, mu_s / np.where(sd > 0, sd, np.inf), -np.inf)
    cand = [int(i) for i in np.argsort(-score)[: cfg.max_active * 3] if ok[i]]
    # Greedy dedupe on the training block's correlation, strongest first. Standardised over the
    # candidate columns only: the pool can hold tens of thousands of members.
    keep: list[int] = []
    examined = 0
    xc = np.where(avail[:, cand], r[:, cand], 0.0)
    sdc = xc.std(0)
    xs = (xc - xc.mean(0)) / np.where(sdc > 0, sdc, 1.0)
    kept_cols: list[int] = []
    for col, i in enumerate(cand):
        if len(keep) >= cfg.max_active:
            break
        examined += 1
        if kept_cols:
            rho = (xs[:, kept_cols].T @ xs[:, col]) / t
            if np.max(np.abs(rho)) > cfg.dedupe_corr:
                continue
        keep.append(i)
        kept_cols.append(col)
    receipt["deduped"] = examined - len(keep)
    k = np.asarray(keep, int)
    xk = np.where(avail[:, k], r[:, k], 0.0).astype(np.float64)
    cov = np.cov(xk, rowvar=False, ddof=1) if len(k) > 1 else np.atleast_2d(xk.var(ddof=1))
    cov = (1 - cfg.cov_shrink) * cov + cfg.cov_shrink * np.diag(np.diag(cov))
    m = mu_s[k]
    # Projected gradient ascent on the concave quadratic; step = 1 / largest eigenvalue.
    lmax = float(np.linalg.eigvalsh(cov)[-1]) if len(k) > 1 else float(cov[0, 0])
    step = 1.0 / max(lmax, 1e-12)
    wk = _project_nonneg(m / np.maximum(np.diag(cov), 1e-12) / max(len(k), 1))
    for _ in range(cfg.solver_iters):
        wk = _project_nonneg(wk + step * (m - cov @ wk))
    w[k] = wk
    receipt["active"] = int((wk > 0).sum())
    return w, receipt


def _blocks(t: int, n_blocks: int) -> list[tuple[int, int]]:
    edges = np.linspace(0, t, n_blocks + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_blocks)]


def walk_forward(pool: Pool, cfg: BookConfig) -> dict:
    """Purged, embargoed, anchored walk-forward. Block 0 only trains; blocks 1.. are OOS.

    Each OOS block is traded with the UNIT direction (weights / sum) fit before it, so the OOS
    series is the book at gross 1 R and sizing is chosen afterwards, on the OOS series alone.
    The single best member is picked by the same training block (highest shrunk Sharpe) and
    traded through the same test block, which is the comparison rule 4 needs.
    """
    t = pool.r1.shape[0]
    oos1, oos3, best1, folds = [], [], [], []
    share3: list[float] = []
    oos_dates: list[pd.Timestamp] = []
    for k, (a, b) in enumerate(_blocks(t, cfg.n_blocks)):
        if k == 0:
            continue
        end = max(a - cfg.embargo_days, 0)
        if end < cfg.min_obs:
            continue
        w, rec = fit_weights(pool.r1[:end], pool.avail[:end], cfg)
        s = w.sum()
        mu, sd, nobs = _member_stats(pool.r1[:end], pool.avail[:end])
        sh = np.where((nobs >= cfg.min_obs) & (sd > 0),
                      mu * nobs / (nobs + cfg.mean_shrink_k) / np.where(sd > 0, sd, 1), -np.inf)
        bi = int(np.argmax(sh)) if np.isfinite(sh).any() else -1
        d = w / s if s > 0 else w
        share3.append(float(d[pool.has_3x].sum()) if s > 0 else 1.0)
        oos1.append(pool.r1[a:b] @ d)
        oos3.append(pool.r3[a:b] @ d)
        best1.append(pool.r1[a:b, bi] if bi >= 0 else np.zeros(b - a))
        oos_dates.extend(pool.dates[a:b])
        folds.append({"block": k, "train_end": str(pool.dates[end - 1].date()),
                      "test": [str(pool.dates[a].date()), str(pool.dates[b - 1].date())],
                      "invested": bool(s > 0), "best_single": pool.ids[bi] if bi >= 0 else None,
                      **rec})
    def cat(xs: list) -> np.ndarray:
        return np.concatenate(xs) if xs else np.zeros(0)

    return {"oos1": cat(oos1), "oos3": cat(oos3), "best1": cat(best1),
            "dates": pd.DatetimeIndex(oos_dates), "folds": folds,
            "fold_lengths": [len(x) for x in oos1],
            "real_3x_weight_share": min(share3) if share3 else 1.0}


def size_lambda(r: np.ndarray, cfg: BookConfig) -> dict:
    """lambda maximising mean log(1 + lambda r) inside the daily-loss and drawdown caps."""
    if len(r) == 0 or not np.any(r):
        return {"lambda": 0.0, "lambda_growth_opt": 0.0, "lambda_survival": 0.0,
                "binding": "no OOS series"}
    worst = float(-r.min()) if r.min() < 0 else 0.0
    lam_daily = cfg.daily_loss_cap / worst if worst > 0 else cfg.lambda_max

    def max_dd(lam: float) -> float:
        lw = np.cumsum(np.log1p(np.maximum(lam * r, -0.999999)))
        peak = np.maximum.accumulate(np.concatenate([[0.0], lw]))[1:]
        return float(1 - np.exp(np.min(lw - peak)))

    lo, hi = 0.0, min(lam_daily, cfg.lambda_max)
    if max_dd(hi) > cfg.drawdown_cap:
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if max_dd(mid) <= cfg.drawdown_cap else (lo, mid)
        lam_surv = lo
    else:
        lam_surv = hi
    grid = np.linspace(0, cfg.lambda_max, 2001)[1:]
    grid = grid[grid * worst < 0.999] if worst > 0 else grid
    g = [float(np.mean(np.log1p(lam * r))) for lam in grid]
    lam_opt = float(grid[int(np.argmax(g))]) if len(g) else 0.0
    lam = min(lam_opt, lam_surv)
    if max(g, default=0.0) <= 0:
        lam = 0.0
    binding = ("no positive growth" if lam == 0.0 else
               "growth optimum" if lam == lam_opt else
               "daily loss cap" if lam_surv >= lam_daily - 1e-12 else "drawdown cap")
    return {"lambda": lam, "lambda_growth_opt": lam_opt, "lambda_survival": lam_surv,
            "lambda_daily_cap": min(lam_daily, cfg.lambda_max), "binding": binding,
            "oos_growth_per_day": float(np.mean(np.log1p(lam * r))) if lam > 0 else 0.0,
            "oos_worst_day": float(lam * r.min()),
            "oos_max_drawdown": max_dd(lam) if lam > 0 else 0.0}


def judge(pool: Pool, cfg: BookConfig, *, n_trials: int | None,
          variance_of_sharpes: float | None = None,
          recipe_sharpes: Sequence[float] = ()) -> dict:
    """Run the walk-forward, the five gates, the sizing, and the final full-history weights."""
    wf = walk_forward(pool, cfg)
    o1, o3, b1 = wf["oos1"], wf["oos3"], wf["best1"]
    gates: dict[str, dict] = {}
    gates["oos_days"] = {"passed": len(o1) >= cfg.min_oos_days, "days": len(o1),
                         "required": cfg.min_oos_days}
    sr = sharpe_ratio(o1) if len(o1) > 1 else 0.0
    if n_trials is None or n_trials < 1 or len(o1) < 3:
        gates["deflated_sharpe"] = {"passed": False, "why": "n_trials UNMEASURED or no OOS: "
                                    "fails closed", "n_trials": n_trials}
    else:
        # THE LARGER OF TWO DISPERSION BASES (audit 11-03): members' full-history Sharpes, and
        # the OOS Sharpes of every book recipe tried. A larger variance raises SR0: strict side.
        var_members = None
        if variance_of_sharpes is None:
            mu, sd, nobs = _member_stats(pool.r1, pool.avail)
            shs = np.where((nobs >= cfg.min_obs) & (sd > 0), mu / np.where(sd > 0, sd, 1), np.nan)
            shs = shs[np.isfinite(shs)]
            var_members = float(np.var(shs, ddof=1)) if len(shs) > 1 else 1.0
            variance_of_sharpes = var_members
        rs = np.asarray([x for x in recipe_sharpes if x is not None and np.isfinite(x)], float)
        var_recipes = float(np.var(rs, ddof=1)) if len(rs) > 1 else None
        if var_recipes is not None:
            variance_of_sharpes = max(variance_of_sharpes, var_recipes)
        d = deflated_sharpe_ratio(o1, n_trials=int(n_trials),
                                  variance_of_sharpes=variance_of_sharpes, threshold=cfg.dsr_bar)
        gates["deflated_sharpe"] = {"passed": bool(d.passed), "dsr": round(float(d.dsr), 4),
                                    "sr0": round(float(d.sr0_threshold), 4),
                                    "sr_daily": round(float(d.sr_observed), 4),
                                    "n_trials": int(n_trials),
                                    "variance_of_sharpes": round(float(variance_of_sharpes), 6),
                                    "variance_members": var_members,
                                    "variance_recipes": var_recipes}
    # NEVER VACUOUS (L1.49, audit 11-03): a member with no 3x arm carries r3 = r1, so the gate
    # holds only when every unit of OOS weight sat on members with a real 3x series.
    share = float(wf["real_3x_weight_share"])
    gates["cost_3x"] = {"passed": bool(len(o3) and o3.mean() > 0 and share >= 1.0 - 1e-9),
                        "oos_mean_r_3x": float(o3.mean()) if len(o3) else None,
                        "real_3x_weight_share_min_fold": round(share, 6)}
    sb = sharpe_ratio(b1) if len(b1) > 1 else 0.0
    gates["beats_best_single"] = {"passed": bool(sr > sb), "book_sr_daily": round(sr, 4),
                                  "best_single_sr_daily": round(sb, 4)}
    passed = all(g["passed"] for g in gates.values())
    w, rec = fit_weights(pool.r1, pool.avail, cfg)
    s = w.sum()
    unit = w / s if s > 0 else w
    sizing = size_lambda(o1, cfg)
    sizing["oos_growth_per_day_note"] = "in-sample for lambda: lambda was chosen on this series"
    fl = wf["fold_lengths"]
    if len(fl) >= 2 and fl[-1] > 0:
        head, tail = o1[: -fl[-1]], o1[-fl[-1]:]
        lam_h = size_lambda(head, cfg)["lambda"]
        sizing["holdout"] = {
            "lambda_from_earlier_folds": lam_h,
            "last_fold_days": fl[-1],
            "last_fold_growth_per_day": (float(np.mean(np.log1p(lam_h * tail)))
                                         if lam_h > 0 else 0.0),
            "last_fold_worst_day": float(lam_h * tail.min()) if lam_h > 0 else 0.0}
    # ARMED = the smaller of the full-OOS lambda and the one the holdout supports (audit 11-03),
    # and zero when the holdout fold lost money at its own lambda.
    lam = sizing["lambda"]
    h = sizing.get("holdout")
    if h is not None:
        lam = min(lam, h["lambda_from_earlier_folds"])
        if h["last_fold_growth_per_day"] <= 0:
            lam = 0.0
    lam = lam if passed else 0.0
    members = sorted(((pool.ids[i], float(unit[i])) for i in np.flatnonzero(unit > 0)),
                     key=lambda x: -x[1])
    return {
        "recipe": cfg.digest(), "config": asdict(cfg),
        "passed": passed, "gates": gates,
        "oos": {"days": len(o1), "sr_daily": round(sr, 4),
                "sr_annual": round(sr * math.sqrt(252), 3),
                "mean_r_1x": float(o1.mean()) if len(o1) else None,
                "mean_r_3x": float(o3.mean()) if len(o3) else None,
                "first": str(wf["dates"][0].date()) if len(wf["dates"]) else None,
                "last": str(wf["dates"][-1].date()) if len(wf["dates"]) else None},
        "folds": wf["folds"],
        "sizing": {**sizing, "lambda_armed": lam,
                   "note": "lambda is equity at risk per unit-book day; member risk = "
                           "lambda * weight. Zero unless every gate passed."},
        "final_fit": rec,
        "members": [{"cell": c, "weight": round(wt, 6),
                     "risk_per_trade_frac": round(lam * wt, 7)} for c, wt in members],
    }


@dataclass
class Coverage:
    """Eligible versus ingested, by cause. Any gap is RED: no signal may silently go missing."""
    eligible: int = 0
    ingested: int = 0
    gaps: dict[str, int] = field(default_factory=dict)
    refused: dict[str, int] = field(default_factory=dict)
    examples: dict[str, list[str]] = field(default_factory=dict)

    def gap(self, cause: str, cid: str) -> None:
        self.gaps[cause] = self.gaps.get(cause, 0) + 1
        ex = self.examples.setdefault(cause, [])
        if len(ex) < 5:
            ex.append(cid)

    def refuse(self, cause: str) -> None:
        self.refused[cause] = self.refused.get(cause, 0) + 1

    def as_dict(self) -> dict:
        missing = sum(self.gaps.values())
        return {"status": "GREEN" if missing == 0 and self.eligible > 0 else "RED",
                "eligible": self.eligible, "ingested": self.ingested,
                "missing": missing, "missing_by_cause": dict(sorted(self.gaps.items())),
                "refused_by_rule": dict(sorted(self.refused.items())),
                "examples": self.examples,
                "rule": "eligible = every cell the gauntlet ever judged + every live sleeve; "
                        "refused_by_rule cells are counted, not missing; anything else without a "
                        "series in the pool is a gap and turns this RED"}


def recipe_trials(ledger_rows: Sequence[Mapping]) -> int:
    """Distinct recipes ever run: each is one more trial in the book's DSR charge."""
    return len({str(r.get("recipe")) for r in ledger_rows if r.get("recipe")})
