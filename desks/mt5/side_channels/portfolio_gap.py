"""Portfolio-Gap-Driven Discovery — calculates what the current book lacks.

Before spending compute, the hunter calculates what's missing:
- too much trend?
- too much XAU?
- too much London?
- no carry?
- no event alpha?
- no relative value?
- no short-horizon reversal?

Then the hourly hunter gets paid more for filling those holes.
A standalone Sharpe 0.8 edge with near-zero correlation can be worth more
to geometric growth than another Sharpe 1.3 breakout cousin.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats

from .gate_policy import GATES


@dataclass
class PortfolioGapConfig:
    """Configuration for portfolio gap analysis."""
    lookback_days: int = 252                    # 1 year for correlation estimates
    min_live_trades: int = 20                   # Minimum trades for live correlation
    correlation_threshold: float = 0.6          # Above this = "too much"
    concentration_threshold: float = 0.4        # Above this = concentrated
    target_effective_bets: float = 5.0          # Target k_eff
    max_symbol_allocation: float = 0.35         # Max fraction to one symbol
    max_mechanism_allocation: float = 0.50      # Max fraction to one mechanism
    max_session_allocation: float = 0.40        # Max fraction to one session
    min_diversification_gain: float = 0.10      # Minimum marginal E[log W] improvement


@dataclass
class GapSignal:
    """A detected portfolio gap."""
    gap_type: str                               # "symbol", "mechanism", "session", "horizon", "regime"
    gap_subtype: str                            # Specific gap (e.g., "no_carry", "no_relative_value")
    severity: float                             # 0-1, how big the gap
    description: str                            # Human-readable
    target_characteristics: dict                # What would fill this gap
    marginal_elogw_estimate: float              # Expected ΔE[log W] from filling
    confidence: float                           # 0-1
    priority: int                               # 1=highest
    metadata: dict = field(default_factory=dict)


@dataclass
class PortfolioState:
    """Current portfolio composition from live/shadow sleeves."""
    sleeves: list[dict]                         # Live + shadow sleeves
    daily_returns: pd.DataFrame                 # Daily R per sleeve
    symbols: list[str]
    mechanisms: list[str]
    sessions: list[str]
    horizons: list[str]
    regimes: list[str]


class PortfolioGapAnalyzer:
    """Analyzes current portfolio for structural gaps."""
    
    def __init__(self, base_path: Path, config: PortfolioGapConfig = None):
        self.base_path = base_path
        self.config = config or PortfolioGapConfig()
        self.sleeves_file = base_path / "desks" / "mt5" / "data" / "sleeves.json"
        self.ledger_file = base_path / "desks" / "mt5" / "data" / "live_ledger.jsonl"
        self.shadow_dir = base_path / "desks" / "mt5" / "reports" / "shadow"
    
    def load_portfolio_state(self) -> PortfolioState:
        """Load current portfolio from live + shadow sleeves."""
        # Load live sleeves
        live_sleeves = []
        if self.sleeves_file.exists():
            with open(self.sleeves_file, "r") as f:
                data = json.load(f)
            live_sleeves = [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
        
        # Load shadow candidates
        shadow_sleeves = []
        shadow_state_file = self.shadow_dir / "shadow_state.json"
        if shadow_state_file.exists():
            with open(shadow_state_file, "r") as f:
                shadow = json.load(f)
            for key, st in shadow.items():
                if isinstance(st, dict) and st.get("status") in {"ACTIVE", "PROMOTION CANDIDATE", "PROXY_SHADOW"}:
                    shadow_sleeves.append({
                        "name": key,
                        "symbol": st.get("certificate", "").split(".")[0] if "." in st.get("certificate", "") else "UNKNOWN",
                        "status": "SHADOW",
                        "exp_r": st.get("exp_r", 0),
                        "n": st.get("n", 0),
                    })
        
        all_sleeves = live_sleeves + shadow_sleeves
        
        # Build daily returns from ledger
        daily_returns = self._build_daily_returns()
        
        # Extract characteristics
        symbols = list(set(s.get("symbol", "") for s in all_sleeves if s.get("symbol")))
        mechanisms = list(set(s.get("state", s.get("mechanism", "unknown")) for s in all_sleeves))
        sessions = list(set(s.get("window", s.get("session", "unknown")) for s in all_sleeves))
        horizons = list(set(s.get("horizon", "intraday") for s in all_sleeves))
        regimes = list(set(s.get("regime", "all") for s in all_sleeves))
        
        return PortfolioState(
            sleeves=all_sleeves,
            daily_returns=daily_returns,
            symbols=symbols,
            mechanisms=mechanisms,
            sessions=sessions,
            horizons=horizons,
            regimes=regimes,
        )
    
    def _build_daily_returns(self) -> pd.DataFrame:
        """Build daily returns matrix from live ledger."""
        if not self.ledger_file.exists():
            return pd.DataFrame()
        
        rows = []
        with open(self.ledger_file, "r") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        df["entry_time"] = pd.to_datetime(df["entry_time"])
        df["date"] = df["entry_time"].dt.date
        
        # Pivot to daily returns per sleeve
        daily = df.pivot_table(
            index="date",
            columns="sleeve",
            values="r_multiple",
            aggfunc="sum",
            fill_value=0.0
        )
        
        return daily
    
    def compute_correlation_matrix(self, state: PortfolioState) -> pd.DataFrame:
        """Compute correlation matrix of sleeve returns."""
        daily = state.daily_returns
        if daily.empty or len(daily.columns) < 2:
            return pd.DataFrame()
        
        # Use lookback window
        cutoff = daily.index.max() - timedelta(days=self.config.lookback_days)
        recent = daily[daily.index >= cutoff]
        
        if len(recent) < 30:
            return pd.DataFrame()
        
        return recent.corr()
    
    def compute_effective_bets(self, corr_matrix: pd.DataFrame) -> float:
        """Compute effective number of independent bets (k_eff)."""
        if corr_matrix.empty:
            return 1.0
        
        # Eigenvalue method
        eigvals = np.linalg.eigvalsh(corr_matrix.values)
        eigvals = np.maximum(eigvals, 1e-12)
        k_eff = (eigvals.sum() ** 2) / (eigvals ** 2).sum()
        return float(k_eff)
    
    def detect_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect all structural gaps in current portfolio."""
        gaps = []
        
        # 1. Symbol concentration gap
        gaps.extend(self._detect_symbol_gaps(state))
        
        # 2. Mechanism gap
        gaps.extend(self._detect_mechanism_gaps(state))
        
        # 3. Session gap
        gaps.extend(self._detect_session_gaps(state))
        
        # 4. Horizon gap
        gaps.extend(self._detect_horizon_gaps(state))
        
        # 5. Regime gap
        gaps.extend(self._detect_regime_gaps(state))
        
        # 6. Correlation/Diversification gap
        gaps.extend(self._detect_diversification_gaps(state))
        
        # 7. Capacity gap
        gaps.extend(self._detect_capacity_gaps(state))
        
        # 8. Tail protection gap
        gaps.extend(self._detect_tail_gaps(state))
        
        # Sort by priority (severity * confidence * marginal E[log W])
        gaps.sort(key=lambda g: -(g.severity * g.confidence * g.marginal_elogw_estimate * 100 + g.priority))
        
        return gaps
    
    def _detect_symbol_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect over-concentration in specific symbols."""
        gaps = []
        if state.daily_returns.empty:
            return gaps
        
        # Compute symbol-level returns (sum across sleeves for same symbol)
        symbol_returns = pd.DataFrame()
        for col in state.daily_returns.columns:
            # Extract symbol from sleeve name
            sym = col.split(".")[0] if "." in col else col
            if sym not in symbol_returns.columns:
                symbol_returns[sym] = 0.0
            symbol_returns[sym] += state.daily_returns[col]
        
        # Total portfolio return
        portfolio = symbol_returns.sum(axis=1)
        
        # Marginal contribution of each symbol
        for sym in symbol_returns.columns:
            if sym not in symbol_returns.columns:
                continue
            
            # Portfolio variance with and without this symbol
            port_var = portfolio.var()
            without = portfolio - symbol_returns[sym]
            without_var = without.var()
            
            # Marginal risk contribution
            mrc = (port_var - without_var) / port_var if port_var > 0 else 0
            
            # If one symbol contributes >40% of portfolio variance
            if mrc > self.config.max_symbol_allocation:
                gaps.append(GapSignal(
                    gap_type="symbol",
                    gap_subtype="overconcentration",
                    severity=min(mrc / self.config.max_symbol_allocation, 1.0),
                    description=f"{sym} contributes {mrc:.1%} of portfolio variance (threshold: {self.config.max_symbol_allocation:.0%})",
                    target_characteristics={
                        "action": "reduce",
                        "symbol": sym,
                        "target_mrc": self.config.max_symbol_allocation,
                    },
                    marginal_elogw_estimate=0.0,  # Computed later
                    confidence=0.9,
                    priority=1,
                    metadata={"marginal_risk_contribution": mrc},
                ))
        
        # Check for missing major asset classes
        major_classes = {
            "XAUUSD": "gold",
            "EURUSD": "major_fx", "GBPUSD": "major_fx", "USDJPY": "major_fx",
            "US500": "equity_index", "US30": "equity_index", "USTEC": "equity_index",
            "USOIL": "energy", "XAGUSD": "metals",
        }
        
        for sym, asset_class in major_classes.items():
            if sym not in symbol_returns.columns:
                gaps.append(GapSignal(
                    gap_type="symbol",
                    gap_subtype="missing_asset_class",
                    severity=0.7,
                    description=f"Missing {asset_class}: {sym}",
                    target_characteristics={
                        "action": "add",
                        "symbol": sym,
                        "asset_class": asset_class,
                    },
                    marginal_elogw_estimate=0.0,
                    confidence=0.8,
                    priority=2,
                    metadata={"asset_class": asset_class},
                ))
        
        return gaps
    
    def _detect_mechanism_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect missing mechanism types."""
        gaps = []
        
        # Define mechanism categories
        mechanism_categories = {
            "breakout": ["session_range_breakout", "level_breakout", "failed_breakout"],
            "trend": ["trend_follow", "ema_crossover", "donchian"],
            "mean_reversion": ["fair_value_gap", "order_block", "rsi_reversion"],
            "carry": ["carry_trade", "swap_arbitrage", "roll_yield"],
            "event": ["news_reaction", "macro_surprise", "earnings_drift"],
            "relative_value": ["fx_triangle", "metals_fair_value", "oil_fx"],
            "execution_alpha": ["spread_compression", "tick_acceleration", "pre_session"],
            "microstructure": ["order_flow", "volume_profile", "book_pressure"],
            "volatility": ["vol_breakout", "vol_mean_reversion", "gamma_scalping"],
            "regime_transition": ["regime_switch", "transition_alpha", "correlation_breakdown"],
        }
        
        present_mechanisms = set(state.mechanisms)
        
        for category, mechanisms in mechanism_categories.items():
            # Check if ANY mechanism in this category is present
            has_category = any(m in present_mechanisms for m in mechanisms)
            
            if not has_category:
                gaps.append(GapSignal(
                    gap_type="mechanism",
                    gap_subtype=f"missing_{category}",
                    severity=0.8,
                    description=f"No {category} mechanism in portfolio",
                    target_characteristics={
                        "action": "add",
                        "mechanism_category": category,
                        "candidate_mechanisms": mechanisms,
                    },
                    marginal_elogw_estimate=0.0,
                    confidence=0.85,
                    priority=2,
                    metadata={"category": category, "mechanisms": mechanisms},
                ))
        
        # Check for over-concentration in one mechanism
        if len(present_mechanisms) == 1:
            gaps.append(GapSignal(
                gap_type="mechanism",
                gap_subtype="single_mechanism_risk",
                severity=0.9,
                description=f"Portfolio relies on single mechanism: {list(present_mechanisms)[0]}",
                target_characteristics={
                    "action": "diversify",
                    "current_mechanism": list(present_mechanisms)[0],
                },
                marginal_elogw_estimate=0.0,
                confidence=1.0,
                priority=1,
                metadata={"current": list(present_mechanisms)},
            ))
        
        return gaps
    
    def _detect_session_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect session concentration."""
        gaps = []
        if state.daily_returns.empty:
            return gaps
        
        # Map sleeves to sessions
        session_returns = {}
        for col in state.daily_returns.columns:
            session = "unknown"
            for sess in ["asia", "london_am", "ny_open", "afternoon", "london_close", "ny_close"]:
                if sess in col:
                    session = sess
                    break
            
            if session not in session_returns:
                session_returns[session] = 0.0
            session_returns[session] = session_returns.get(session, 0) + state.daily_returns[col].sum()
        
        total = sum(abs(v) for v in session_returns.values())
        if total == 0:
            return gaps
        
        # Check concentration
        for sess, ret in session_returns.items():
            weight = abs(ret) / total
            if weight > self.config.max_session_allocation:
                gaps.append(GapSignal(
                    gap_type="session",
                    gap_subtype="overconcentration",
                    severity=min(weight / self.config.max_session_allocation, 1.0),
                    description=f"Session {sess} has {weight:.1%} of absolute returns (threshold: {self.config.max_session_allocation:.0%})",
                    target_characteristics={
                        "action": "reduce",
                        "session": sess,
                        "target_weight": self.config.max_session_allocation,
                    },
                    marginal_elogw_estimate=0.0,
                    confidence=0.85,
                    priority=2,
                    metadata={"session_weight": weight},
                ))
        
        # Check for missing major sessions
        major_sessions = ["asia", "london_am", "ny_open", "afternoon"]
        for sess in major_sessions:
            if sess not in session_returns or session_returns[sess] == 0:
                gaps.append(GapSignal(
                    gap_type="session",
                    gap_subtype="missing_session",
                    severity=0.6,
                    description=f"Missing session: {sess}",
                    target_characteristics={
                        "action": "add",
                        "session": sess,
                    },
                    marginal_elogw_estimate=0.0,
                    confidence=0.7,
                    priority=3,
                    metadata={"missing_session": sess},
                ))
        
        return gaps
    
    def _detect_horizon_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect missing holding horizons."""
        gaps = []
        
        horizons_present = set(state.horizons)
        
        # Check for short-horizon reversal (intraday < 1h)
        if not any("15m" in h or "30m" in h or "1h" in h for h in horizons_present):
            gaps.append(GapSignal(
                gap_type="horizon",
                gap_subtype="missing_short_horizon",
                severity=0.7,
                description="No short-horizon (<1h) strategies",
                target_characteristics={
                    "action": "add",
                    "horizon": "15m_to_1h",
                    "mechanism_candidates": ["microstructure", "execution_alpha", "vol_breakout"],
                },
                marginal_elogw_estimate=0.0,
                confidence=0.75,
                priority=2,
                metadata={},
            ))
        
        # Check for medium-term (1-5 day)
        if not any("1d" in h or "2d" in h or "5d" in h for h in horizons_present):
            gaps.append(GapSignal(
                gap_type="horizon",
                gap_subtype="missing_medium_horizon",
                severity=0.6,
                description="No medium-horizon (1-5 day) strategies",
                target_characteristics={
                    "action": "add",
                    "horizon": "1d_to_5d",
                    "mechanism_candidates": ["trend", "carry", "event_drift"],
                },
                marginal_elogw_estimate=0.0,
                confidence=0.7,
                priority=3,
                metadata={},
            ))
        
        return gaps
    
    def _detect_regime_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect missing regime coverage."""
        gaps = []
        
        regime_types = ["trend_up", "trend_down", "range", "high_vol", "low_vol", "crisis", "transition"]
        
        # This would need regime-labeled data; simplified check
        if len(state.regimes) < 3:
            gaps.append(GapSignal(
                gap_type="regime",
                gap_subtype="limited_regime_coverage",
                severity=0.7,
                description=f"Only {len(state.regimes)} regime types covered: {state.regimes}",
                target_characteristics={
                    "action": "add",
                    "missing_regimes": [r for r in regime_types if r not in state.regimes],
                },
                marginal_elogw_estimate=0.0,
                confidence=0.6,
                priority=3,
                metadata={"current_regimes": state.regimes},
            ))
        
        return gaps
    
    def _detect_diversification_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect insufficient diversification."""
        gaps = []
        
        corr = self.compute_correlation_matrix(state)
        if corr.empty:
            return gaps
        
        k_eff = self.compute_effective_bets(corr)
        
        if k_eff < self.config.target_effective_bets:
            gaps.append(GapSignal(
                gap_type="diversification",
                gap_subtype="insufficient_k_eff",
                severity=min(1.0, (self.config.target_effective_bets - k_eff) / self.config.target_effective_bets),
                description=f"Effective independent bets k_eff = {k_eff:.1f} (target: {self.config.target_effective_bets})",
                target_characteristics={
                    "action": "add_orthogonal",
                    "current_k_eff": k_eff,
                    "target_k_eff": self.config.target_effective_bets,
                    "avg_correlation": corr.values[np.triu_indices_from(corr.values, k=1)].mean(),
                },
                marginal_elogw_estimate=0.0,
                confidence=0.9,
                priority=1,
                metadata={"k_eff": k_eff, "target_k_eff": self.config.target_effective_bets},
            ))
        
        # Check average correlation
        avg_corr = corr.values[np.triu_indices_from(corr.values, k=1)].mean()
        if avg_corr > self.config.correlation_threshold:
            gaps.append(GapSignal(
                gap_type="diversification",
                gap_subtype="high_avg_correlation",
                severity=min(avg_corr / self.config.correlation_threshold, 1.0),
                description=f"Average correlation {avg_corr:.2f} exceeds threshold {self.config.correlation_threshold}",
                target_characteristics={
                    "action": "add_orthogonal",
                    "current_avg_corr": avg_corr,
                    "target_avg_corr": self.config.correlation_threshold,
                },
                marginal_elogw_estimate=0.0,
                confidence=0.85,
                priority=2,
                metadata={"avg_corr": avg_corr},
            ))
        
        return gaps
    
    def _detect_capacity_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect capacity concentration."""
        gaps = []
        
        # Count sleeves by capacity category
        capacity_counts = {"micro": 0, "small": 0, "medium": 0, "large": 0, "institutional": 0}
        for s in state.sleeves:
            cat = s.get("capacity_category", s.get("capacity", "unknown"))
            if cat in capacity_counts:
                capacity_counts[cat] += 1
        
        # If all micro/small, missing institutional capacity edges
        if capacity_counts["micro"] + capacity_counts["small"] == len(state.sleeves):
            gaps.append(GapSignal(
                gap_type="capacity",
                gap_subtype="no_institutional_capacity",
                severity=0.5,
                description="All strategies are micro/small capacity; missing institutional-scale edges",
                target_characteristics={
                    "action": "add",
                    "capacity_target": "institutional",
                },
                marginal_elogw_estimate=0.0,
                confidence=0.6,
                priority=4,
                metadata={"capacity_counts": capacity_counts},
            ))
        
        return gaps
    
    def _detect_tail_gaps(self, state: PortfolioState) -> list[GapSignal]:
        """Detect missing tail protection."""
        gaps = []
        
        if state.daily_returns.empty:
            return gaps
        
        portfolio = state.daily_returns.sum(axis=1)
        
        # Check for tail asymmetry
        skew = portfolio.skew()
        kurt = portfolio.kurtosis()
        
        # If negatively skewed (left tail risk)
        if skew < -0.5:
            gaps.append(GapSignal(
                gap_type="tail",
                gap_subtype="negative_skew",
                severity=min(abs(skew) / 1.5, 1.0),
                description=f"Portfolio has negative skew ({skew:.2f}) - left tail risk",
                target_characteristics={
                    "action": "add",
                    "mechanism_target": "tail_protection",
                    "candidates": ["long_vol", "tail_hedge", "convex_payoff", "negative_skew_hedge"],
                },
                marginal_elogw_estimate=0.0,
                confidence=0.8,
                priority=2,
                metadata={"skew": skew, "kurtosis": kurt},
            ))
        
        return gaps
    
    def estimate_marginal_elogw(self, gap: GapSignal, state: PortfolioState) -> float:
        """Estimate marginal ΔE[log W] from filling a gap.
        
        This is the key metric for prioritizing gaps.
        """
        # Simplified estimation based on gap type
        base_estimates = {
            "symbol": 0.02,
            "mechanism": 0.03,
            "session": 0.015,
            "horizon": 0.015,
            "regime": 0.02,
            "diversification": 0.025,
            "capacity": 0.01,
            "tail": 0.02,
        }
        
        base = base_estimates.get(gap.gap_type, 0.01)
        
        # Adjust by severity and confidence
        return base * gap.severity * gap.confidence
    
    def prioritize_gaps(self, gaps: list[GapSignal], state: PortfolioState) -> list[GapSignal]:
        """Prioritize gaps by estimated marginal E[log W]."""
        for gap in gaps:
            gap.marginal_elogw_estimate = self.estimate_marginal_elogw(gap, state)
        
        # Sort by priority score
        gaps.sort(key=lambda g: -(
            g.marginal_elogw_estimate * 100 + 
            (5 - g.priority) * 0.1 + 
            g.severity * 0.05
        ))
        
        return gaps
    
    def generate_gap_report(self, gaps: list[GapSignal]) -> dict:
        """Generate human-readable gap report."""
        report = {
            "total_gaps": len(gaps),
            "by_type": {},
            "top_5": [],
            "estimated_total_marginal_elogw": sum(g.marginal_elogw_estimate for g in gaps),
        }
        
        for g in gaps:
            t = g.gap_type
            if t not in report["by_type"]:
                report["by_type"][t] = {"count": 0, "total_severity": 0}
            report["by_type"][t]["count"] += 1
            report["by_type"][t]["total_severity"] += g.severity
        
        report["top_5"] = [
            {
                "type": g.gap_type,
                "subtype": g.gap_subtype,
                "severity": g.severity,
                "description": g.description,
                "marginal_elogw": g.marginal_elogw_estimate,
                "priority": g.priority,
            }
            for g in gaps[:5]
        ]
        
        return report


def compute_portfolio_gap_budget(gaps: list[GapSignal], total_budget_fraction: float = 0.5) -> dict:
    """Allocate discovery budget proportional to gap marginal E[log W]."""
    total_marginal = sum(g.marginal_elogw_estimate for g in gaps)
    
    if total_marginal == 0:
        return {}
    
    allocation = {}
    for g in gaps:
        allocation[g.gap_subtype] = (g.marginal_elogw_estimate / total_marginal) * total_budget_fraction
    
    return allocation


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    analyzer = PortfolioGapAnalyzer(base)
    
    print("Loading portfolio state...")
    state = analyzer.load_portfolio_state()
    print(f"Loaded {len(state.sleeves)} sleeves")
    print(f"Symbols: {state.symbols}")
    print(f"Mechanisms: {state.mechanisms}")
    print(f"Sessions: {state.sessions}")
    
    print("\nDetecting gaps...")
    gaps = analyzer.detect_gaps(state)
    gaps = analyzer.prioritize_gaps(gaps, state)
    
    print(f"\nFound {len(gaps)} gaps:")
    for g in gaps[:10]:
        print(f"  [{g.gap_type}] {g.gap_subtype}: {g.description}")
        print(f"    Severity: {g.severity:.2f}, Marginal E[log W]: {g.marginal_elogw_estimate:.4f}")
    
    report = analyzer.generate_gap_report(gaps)
    print(f"\nTotal estimated marginal E[log W] from filling all gaps: {report['estimated_total_marginal_elogw']:.4f}")
    
    budget = compute_portfolio_gap_budget(gaps)
    print(f"\nBudget allocation (50% of discovery):")
    for k, v in sorted(budget.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v:.1%}")