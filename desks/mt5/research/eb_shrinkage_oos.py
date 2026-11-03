"""Preregistered out-of-sample test: fixed-k vs empirical-Bayes shrinkage of sleeve means.

The preregistration is `docs/research/EB_SHRINKAGE_PREREGISTRATION.md`; this harness is its only
executor, and the bars below are copied from it verbatim. Nothing here changes a gate, a cap or a
survival rail; the only action it can take is to place `EB_SHRINKAGE_ARMED`
(`pf_allocator.py --eb-oos --eb-arm-on-pass`),
and only when BOTH preregistered bars pass.

WALK-FORWARD. The book's calendar is cut at `N_FOLDS` expanding-window origins spread over its
second half. At each origin every sleeve's evidence is truncated to the days before it -- forward
and live counts zeroed, state and macro inputs cleared, so neither mode sees a day after the
origin -- and the next `HORIZON` days are held out.

  P1 PREDICTIVE: per fold, the day-weighted squared error of each mode's posterior mean against
     the sleeve's realised held-out mean (sleeves with >= MIN_TEST_DAYS held-out days). The noise
     in the realised mean is common to both modes, so the difference is the estimator's.
  P2 GROWTH: per fold, each mode's book solved as production solves it -- `optimise` free up to
     the 30% ceiling, then scaled up to the 20% floor if it solved below it (pf_allocator's
     proportional floor fill) -- so the posterior moves total heat as well as the split.
     Scored on the held-out days as realised mean log(1 + h . r_t) (an absent day is flat).
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.eb_shrinkage import ARM_FILE  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    _posterior_mu,
    optimise,
)

OUT = BASE / "reports" / "EB_SHRINKAGE_OOS.json"

# ---- preregistered constants (docs/research/EB_SHRINKAGE_PREREGISTRATION.md) -- do not tune
N_FOLDS = 6
HORIZON = 126
MIN_TRAIN_DAYS = 60
MIN_TEST_DAYS = 20
P1_FOLD_WIN_SHARE = 0.50
P1_POOLED_MSE_RATIO = 1.00
HARD_CAP = 0.30
HEAT_FLOOR = 0.20
SEED = 20261103


def _truncate(e: SleeveEvidence, lo: int, hi: int) -> SleeveEvidence:
    return dataclasses.replace(e, daily_r=np.asarray(e.daily_r[lo:hi], dtype=float),
                               forward_days=0, live_days=0,
                               state_r=np.array([], dtype=float),
                               macro_w=np.array([], dtype=float))


def _own(a: np.ndarray) -> np.ndarray:
    return a[np.isfinite(a)]


def fold_origins(n_days: int) -> list[int]:
    lo = max(n_days // 2, MIN_TRAIN_DAYS)
    hi = n_days - HORIZON
    if hi <= lo:
        return []
    return sorted({int(x) for x in np.linspace(lo, hi, N_FOLDS)})


def run_folds(ev: Sequence[SleeveEvidence], *, with_books: bool = True,
              cfg_kw: dict[str, Any] | None = None) -> dict[str, Any]:
    n_days = min(e.daily_r.size for e in ev)
    folds: list[dict[str, Any]] = []
    for t in fold_origins(n_days):
        train = [_truncate(e, 0, t) for e in ev]
        keep = [i for i, e in enumerate(train) if _own(e.daily_r).size >= MIN_TRAIN_DAYS]
        if len(keep) < 3:
            continue
        train = [train[i] for i in keep]
        test = np.stack([np.asarray(ev[i].daily_r[t:t + HORIZON], dtype=float) for i in keep],
                        axis=1)
        n_te = np.isfinite(test).sum(axis=0).astype(float)
        realised = np.array([float(np.nanmean(test[:, j])) if n_te[j] else 0.0
                             for j in range(test.shape[1])])
        scored = n_te >= MIN_TEST_DAYS
        row: dict[str, Any] = {"origin": t, "n_sleeves": len(keep), "n_scored": int(scored.sum())}
        for mode, eb in (("fixed", False), ("eb", True)):
            _, post = _posterior_mu(train, np.random.default_rng(SEED), 1, eb=eb)
            w = n_te[scored]
            err = (post[scored] - realised[scored]) ** 2
            row[f"mse_{mode}"] = float((w * err).sum() / w.sum()) if w.sum() else None
            if with_books:
                cfg = WorldConfig(seed=SEED, n_worlds=128, n_rows=256, eb_shrinkage=eb,
                                  **(cfg_kw or {}))
                # AS PRODUCTION: free up to the ceiling; below the floor, the solved book is
                # scaled up to it (pf_allocator.fill_floor's proportional fill), so the
                # posterior's split survives the fill. `optimise(target=...)` far above the free
                # optimum returns a uniform book and would make the two modes tie by construction.
                book = optimise(train, hard_cap=HARD_CAP, cfg=cfg)
                h = np.array([book.heat.get(e.name, 0.0) for e in train])
                if h.sum() < HEAT_FLOOR:
                    h = (h * (HEAT_FLOOR / h.sum()) if h.sum() > 1e-12
                         else np.full(h.size, HEAT_FLOOR / h.size))
                port = np.nan_to_num(test, nan=0.0) @ h
                row[f"elog_{mode}"] = float(np.mean(np.log(np.clip(1.0 + port, 1e-12, None))))
                row[f"heat_{mode}"] = float(h.sum())
        folds.append(row)
    return {"folds": folds, **verdict(folds, with_books=with_books)}


def verdict(folds: list[dict[str, Any]], *, with_books: bool = True) -> dict[str, Any]:
    ok = [f for f in folds if f.get("mse_fixed") is not None and f.get("mse_eb") is not None]
    if not ok:
        return {"verdict": "UNMEASURED", "why": "no scorable fold"}
    wins = sum(1 for f in ok if f["mse_eb"] < f["mse_fixed"])
    ratio = (sum(f["mse_eb"] for f in ok) / sum(f["mse_fixed"] for f in ok)
             if sum(f["mse_fixed"] for f in ok) > 0 else 1.0)
    p1 = wins / len(ok) >= P1_FOLD_WIN_SHARE and ratio <= P1_POOLED_MSE_RATIO
    out: dict[str, Any] = {"p1": {"pass": p1, "fold_wins": wins, "folds": len(ok),
                                  "pooled_mse_ratio": ratio}}
    if with_books:
        b = [f for f in ok if "elog_eb" in f]
        tot_eb, tot_fx = sum(f["elog_eb"] for f in b), sum(f["elog_fixed"] for f in b)
        worst_eb = min(f["elog_eb"] for f in b) if b else 0.0
        worst_fx = min(f["elog_fixed"] for f in b) if b else 0.0
        p2 = bool(b) and tot_eb >= tot_fx and worst_eb >= worst_fx
        out["p2"] = {"pass": p2, "sum_elog_eb": tot_eb, "sum_elog_fixed": tot_fx,
                     "worst_fold_eb": worst_eb, "worst_fold_fixed": worst_fx}
        out["verdict"] = "PASS" if (p1 and p2) else "FAIL"
    else:
        out["verdict"] = "PASS_P1_ONLY" if p1 else "FAIL"
    return out


def load_box_evidence() -> list[SleeveEvidence]:
    """The allocator's own evidence, assembled exactly as `pf_allocator.run` assembles it."""
    import pf_allocator as pf
    daily, forward = pf.build_evidence(force=False)
    live = pf.live_days_by_sleeve()
    certified, cert_acct = pf.certified_evidence()
    scalp, _ = pf.scalp_evidence()
    daily = pf.align(pf.align(daily, certified), scalp)
    forward, _ = pf.join_forward([str(c) for c in daily.columns], forward)
    ev = pf.sleeve_evidence(daily, forward, live, pf.search_trials(),
                            forward_only_days={n: len(sr) for n, sr in scalp.items()},
                            identity=cert_acct.get("identity"))
    pf.apply_culture_labels(ev)
    return list(ev)


def measure(*, books: bool = True, arm_on_pass: bool = False) -> dict[str, Any]:
    """Run the preregistered test on the box's evidence and write the report.

    Entry point: `pf_allocator.py --eb-oos [--eb-arm-on-pass]` (the allocator's own clocked
    organ and lock), never a standalone script."""
    ev = load_box_evidence()
    res = run_folds(ev, with_books=books)
    res.update({"asof": datetime.now(UTC).isoformat(timespec="seconds"),
                "n_sleeves": len(ev), "prereg": "docs/research/EB_SHRINKAGE_PREREGISTRATION.md"})
    armed = False
    if arm_on_pass and res.get("verdict") == "PASS":
        ARM_FILE.parent.mkdir(parents=True, exist_ok=True)
        ARM_FILE.write_text(json.dumps({"armed_at": res["asof"], "by": "eb_shrinkage_oos"}))
        armed = True
    res["armed"] = armed
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str))
    return res

