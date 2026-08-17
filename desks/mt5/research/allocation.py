"""Posterior E[log W] allocator (ADVISORY - backtest basis only).

Maximizes mean log growth over the 2018-2026 daily-R matrix with per-sleeve
weights (positive, sum=1), total risk q_total fixed. Reports:
  - optimal weights vs equal weight
  - net Sharpe + CAGR of the weighted book at q_total = 5.5%/day-R
  - concentration (HHI) and marginal contribution ranking

Forward evidence (live ledger) overrides any backtest allocation; this is the
prior the forward ledger will update.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio_projection import build_daily, build_sleeves  # noqa: E402

BASE = Path(__file__).resolve().parent.parent

# THE DESK HAS ONE RISK BUDGET AND IT LIVES IN THE GATEWAY. This read 0.055 -- the old
# ~92%-of-Kelly setting -- while gateway.Q_OPT was moved to 0.0075, so the allocator was
# optimising and reporting a book at seven times the risk the account actually runs. Two files
# disagreeing about the risk budget is how a superseded number gets quoted back as evidence.
# Imported rather than copied, so it can never drift again.
try:
    from mt5desk.gateway import Q_OPT as Q_TOTAL          # noqa: E402
except Exception:                                          # MetaTrader5 absent (research boxes)
    from mt5desk.gateway_config_fallback import Q_OPT as Q_TOTAL  # type: ignore  # noqa: E402
LR = 5e-3
ITERS = 4000


def main() -> None:
    sv = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
    if not sv.exists():
        print("waiting for UNIVERSAL_SURVIVORS.json (universal 10-gate survivors) ...",
              flush=True)
        while not sv.exists():
            time.sleep(60)
    sleeves = build_sleeves()
    daily = build_daily(sleeves)
    R = np.nan_to_num(daily.to_numpy(dtype=float), nan=0.0)
    names = list(daily.columns)

    w = np.full(len(names), 1.0 / len(names))
    best_w, best_g = w.copy(), -np.inf
    g = []
    for i in range(ITERS):
        rets = (1.0 + Q_TOTAL * (R @ w))
        if (rets <= 0).any():
            break
        lg = np.mean(np.log(rets))
        grad = Q_TOTAL * (R.T @ (1.0 / rets)) / len(rets)
        w += LR * grad
        w = np.clip(w, 0.0, None)
        if w.sum() > 0:
            w = w / w.sum()
        g.append(lg)
        if lg > best_g:
            best_g, best_w = lg, w.copy()

    port_eq = daily.fillna(0.0).sum(axis=1)
    port_opt = daily.fillna(0.0) @ best_w
    sh_eq = port_eq.mean() / port_eq.std(ddof=1) * np.sqrt(252)
    sh_opt = port_opt.mean() / port_opt.std(ddof=1) * np.sqrt(252)

    def cagr(p: pd.Series, q: float) -> float:
        wl = (1.0 + q * p).prod()
        years = (p.index.max() - p.index.min()).days / 365.25
        return wl ** (1 / years) - 1

    hhi = float((best_w ** 2).sum())
    order = np.argsort(-best_w)
    print(f"{'sleeve':<26} {'weight':>8} {'annSharpe(w)':>12}")
    for i in order:
        s = daily[names[i]].dropna()
        ann = s.mean() / s.std(ddof=1) * np.sqrt(252) if len(s) > 1 and s.std(ddof=1) > 0 else 0
        print(f"{names[i]:<26} {best_w[i]:8.4f} {ann:12.2f}")

    print(f"\nq_total={Q_TOTAL}:")
    print(f"equal weight : Sharpe {sh_eq:.2f} | 8y CAGR {cagr(port_eq, Q_TOTAL)*100:.1f}%")
    print(f"optimal      : Sharpe {sh_opt:.2f} | 8y CAGR {cagr(port_opt, Q_TOTAL)*100:.1f}%")
    print(f"weights HHI = {hhi:.3f} (1/N = {1/len(names):.3f})")
    print(f"mean log-growth gain vs equal: {best_g - g[0]:+.4f}/day")

    out = dict(weights={names[i]: float(best_w[i]) for i in order},
               sharpe_equal=sh_eq, sharpe_optimal=sh_opt,
               cagr_equal=cagr(port_eq, Q_TOTAL), cagr_optimal=cagr(port_opt, Q_TOTAL),
               hhi=hhi, q_total=Q_TOTAL, advisory=True,
               note="backtest basis only; forward ledger overrides")
    (BASE / "reports" / "allocation.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    (BASE / "reports" / "DONE_allocation").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print("\n-> reports/allocation.json (ADVISORY) + DONE_allocation")


if __name__ == "__main__":
    main()