"""Pipeline Stage 5: Allocation — portfolio optimization and capital allocation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent.parent
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"


@dataclass
class AllocationResult:
    """Portfolio allocation result."""
    weights: dict[str, float]        # sleeve -> weight (sums to 1.0)
    q_total: float                   # total risk budget
    k_eff: float                     # effective independent bets
    heat_budget: float               # total portfolio heat
    cagr_optimal: float
    cagr_equal: float
    sharpe_optimal: float
    sharpe_equal: float


def load_live_sleeves() -> list[dict]:
    """Load currently LIVE promoted sleeves."""
    if not SLEEVES_FILE.exists():
        return []
    import json
    with open(SLEEVES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]


def load_live_ledger() -> pd.DataFrame:
    """Load live ledger for forward stats."""
    if not LEDGER.exists():
        return pd.DataFrame()
    import json
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    return pd.DataFrame(rows)


def compute_allocation(sleeves: list[dict]) -> AllocationResult:
    """Compute optimal portfolio allocation using E[log W] maximization.

    Delegates to allocation.py for the actual computation.
    """
    from mt5desk.gateway_config_fallback import Q_OPT, heat_budget
    from mt5desk.independence import measure_from_ledger

    ledger = load_live_ledger()
    k_eff = 1.0
    if not ledger.empty:
        k_eff = measure_from_ledger(ledger)

    budget = heat_budget(k_eff)

    # Get daily returns per sleeve
    daily = pd.DataFrame()
    for s in sleeves:
        name = s["name"]
        # Load forward returns from ledger
        sleeve_trades = ledger[ledger["sleeve"] == name] if not ledger.empty else pd.DataFrame()
        if not sleeve_trades.empty:
            sleeve_trades["entry_time"] = pd.to_datetime(sleeve_trades["entry_time"])
            daily[name] = sleeve_trades.set_index("entry_time")["r_multiple"].resample("D").sum()

    daily = daily.fillna(0.0)

    if daily.empty:
        # No live data yet - equal weight
        n = len(sleeves)
        weights = {s["name"]: 1.0 / n for s in sleeves}
        return AllocationResult(
            weights=weights,
            q_total=budget,
            k_eff=k_eff,
            heat_budget=budget,
            cagr_optimal=0.0,
            cagr_equal=0.0,
            sharpe_optimal=0.0,
            sharpe_equal=0.0,
        )

    # Optimal weights via gradient ascent on E[log(1 + q*R)]
    # (delegates to allocation.py logic)
    names = list(daily.columns)
    n = len(names)
    w = np.ones(n) / n
    best_w = w.copy()
    best_g = -np.inf

    for _ in range(1000):
        r = daily @ w
        g = np.log1p(r * Q_OPT).mean()
        if g > best_g:
            best_g, best_w = g, w.copy()
        grad = daily.T @ (Q_OPT / (1 + Q_OPT * r))
        LR = 0.05 / (np.linalg.norm(grad) + 1e-12)
        w = np.clip(w + LR * grad, 0.0, None)
        if w.sum() > 0:
            w = w / w.sum()

    weights = {names[i]: float(best_w[i]) for i in range(n)}

    port_opt = daily @ best_w
    port_eq = daily.mean(axis=1)  # FIXED: equal weight = mean, not sum

    def cagr(p: pd.Series, q: float) -> float:
        wl = (1.0 + q * p).prod()
        years = (p.index.max() - p.index.min()).days / 365.25
        return wl ** (1 / years) - 1

    return AllocationResult(
        weights=weights,
        q_total=budget,
        k_eff=k_eff,
        heat_budget=budget,
        cagr_optimal=cagr(port_opt, budget),
        cagr_equal=cagr(port_eq, budget),
        sharpe_optimal=port_opt.mean() / port_opt.std(ddof=1) * np.sqrt(252),
        sharpe_equal=port_eq.mean() / port_eq.std(ddof=1) * np.sqrt(252),
    )


def run_allocation() -> AllocationResult:
    """Run allocation for current live sleeves."""
    sleeves = load_live_sleeves()
    return compute_allocation(sleeves)


if __name__ == "__main__":
    result = run_allocation()
    print(f"q_total={result.q_total:.4f}, k_eff={result.k_eff:.2f}")
    print(f"Optimal: CAGR={result.cagr_optimal*100:.1f}%, Sharpe={result.sharpe_optimal:.2f}")
    print(f"Equal:   CAGR={result.cagr_equal*100:.1f}%, Sharpe={result.sharpe_equal:.2f}")
    for name, w in result.weights.items():
        print(f"  {name}: {w:.4f}")