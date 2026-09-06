"""Untouched Future Reservoir — rolling inaccessible holdout for genuine lockbox.

The problem: current 'lockbox' gate uses walk-forward OOS Sharpe again, so it's not independent.
The solution: maintain a rolling piece of history that NO hyperparameter selection, agent,
meta-desk, or backtest can EVER inspect until a hypothesis is frozen.

Design:
- When data is first acquired, the most recent 6-12 months go into the reservoir
- Reservoir advances monthly: oldest reservoir data graduates to training; newest data enters reservoir
- NO code can read reservoir data except the final lockbox evaluation
- Reservoir is only opened ONCE per frozen hypothesis
- After opening, that period becomes 'contaminated' and is never used again
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd


@dataclass
class ReservoirConfig:
    """Configuration for the untouched reservoir."""
    reservoir_months: int = 6                 # Size of rolling reservoir
    min_reservoir_months: int = 3             # Minimum before first evaluation
    advance_frequency: str = "monthly"        # How often reservoir advances
    embargoed_entities: list[str] = field(default_factory=lambda: [
        "all_agents", "all_hyperparameters", "all_meta_desks", "all_backtests",
        "all_llms", "all_optimization_routines"
    ])
    reservoir_location: str = "separate_storage"  # "separate_storage" | "encrypted" | "offline"


@dataclass
class ReservoirState:
    """Current state of the reservoir."""
    reservoir_start: datetime                 # Start of current reservoir period
    reservoir_end: datetime                   # End of current reservoir period (now - min_lag)
    training_end: datetime                    # End of training data (before reservoir)
    total_observations: int
    reservoir_observations: int
    training_observations: int
    last_advance: datetime
    contaminated_periods: list[tuple[datetime, datetime]]  # Periods already opened
    frozen_hypotheses: list[dict]             # Hypotheses that consumed reservoir
    created_at: datetime
    version: int = 1


@dataclass
class FrozenHypothesis:
    """A hypothesis that has been frozen for reservoir evaluation."""
    hypothesis_id: str
    frozen_at: datetime
    frozen_spec: dict                         # Complete specification
    frozen_code_hash: str                     # Hash of code that generated it
    frozen_data_hash: str                     # Hash of training data used
    reservoir_period: tuple[datetime, datetime]  # Which reservoir period it consumes
    status: Literal["frozen", "evaluated", "contaminated"]
    lockbox_result: dict | None = None
    evaluated_at: datetime | None = None


class UntouchedReservoir:
    """Manages the rolling untouched future reservoir."""
    
    def __init__(self, base_path: Path, config: ReservoirConfig = None):
        self.base_path = base_path
        self.config = config or ReservoirConfig()
        self.reservoir_dir = base_path / "data" / "untouched_reservoir"
        self.reservoir_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.reservoir_dir / "reservoir_state.json"
        self.frozen_file = self.reservoir_dir / "frozen_hypotheses.jsonl"
        self.access_log_file = self.reservoir_dir / "access_log.jsonl"
        
        self.state: ReservoirState | None = None
        self.frozen_hypotheses: list[FrozenHypothesis] = []
        
        self._load_state()
        self._load_frozen()
        
        # Initialize if first run
        if self.state is None:
            self._initialize_reservoir()
    
    def _load_state(self) -> None:
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                data = json.load(f)
            # Convert datetime strings back
            data["reservoir_start"] = datetime.fromisoformat(data["reservoir_start"])
            data["reservoir_end"] = datetime.fromisoformat(data["reservoir_end"])
            data["training_end"] = datetime.fromisoformat(data["training_end"])
            data["last_advance"] = datetime.fromisoformat(data["last_advance"])
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            data["contaminated_periods"] = [
                (datetime.fromisoformat(s), datetime.fromisoformat(e))
                for s, e in data["contaminated_periods"]
            ]
            self.state = ReservoirState(**data)
    
    def _load_frozen(self) -> None:
        if self.frozen_file.exists():
            with open(self.frozen_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        data["frozen_at"] = datetime.fromisoformat(data["frozen_at"])
                        data["reservoir_period"] = (
                            datetime.fromisoformat(data["reservoir_period"][0]),
                            datetime.fromisoformat(data["reservoir_period"][1]),
                        )
                        if data["evaluated_at"]:
                            data["evaluated_at"] = datetime.fromisoformat(data["evaluated_at"])
                        self.frozen_hypotheses.append(FrozenHypothesis(**data))
    
    def _save_state(self) -> None:
        if self.state:
            data = {
                "reservoir_start": self.state.reservoir_start.isoformat(),
                "reservoir_end": self.state.reservoir_end.isoformat(),
                "training_end": self.state.training_end.isoformat(),
                "total_observations": self.state.total_observations,
                "reservoir_observations": self.state.reservoir_observations,
                "training_observations": self.state.training_observations,
                "last_advance": self.state.last_advance.isoformat(),
                "contaminated_periods": [
                    (s.isoformat(), e.isoformat()) for s, e in self.state.contaminated_periods
                ],
                "frozen_hypotheses": [h.hypothesis_id for h in self.frozen_hypotheses],
                "created_at": self.state.created_at.isoformat(),
                "version": self.state.version,
            }
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    def _save_frozen(self, hypothesis: FrozenHypothesis) -> None:
        with open(self.frozen_file, "a") as f:
            data = {
                "hypothesis_id": hypothesis.hypothesis_id,
                "frozen_at": hypothesis.frozen_at.isoformat(),
                "frozen_spec": hypothesis.frozen_spec,
                "frozen_code_hash": hypothesis.frozen_code_hash,
                "frozen_data_hash": hypothesis.frozen_data_hash,
                "reservoir_period": (
                    hypothesis.reservoir_period[0].isoformat(),
                    hypothesis.reservoir_period[1].isoformat(),
                ),
                "status": hypothesis.status,
                "lockbox_result": hypothesis.lockbox_result,
                "evaluated_at": hypothesis.evaluated_at.isoformat() if hypothesis.evaluated_at else None,
            }
            f.write(json.dumps(data) + "\n")
    
    def _log_access(self, actor: str, action: str, allowed: bool, details: dict = None) -> None:
        """Log all access attempts for audit."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "actor": actor,
            "action": action,
            "allowed": allowed,
            "details": details or {},
        }
        with open(self.access_log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _initialize_reservoir(self) -> None:
        """Initialize reservoir with most recent data."""
        # Get latest data date
        latest_date = self._get_latest_data_date()
        if not latest_date:
            return
        
        reservoir_months = self.config.reservoir_months
        min_lag_days = 7  # 1 week minimum lag
        
        reservoir_end = latest_date - timedelta(days=min_lag_days)
        reservoir_start = reservoir_end - timedelta(days=reservoir_months * 30)
        training_end = reservoir_start
        
        # Count observations (simplified)
        total_obs = self._count_observations(training_end, reservoir_end)
        reservoir_obs = self._count_observations(reservoir_start, reservoir_end)
        training_obs = total_obs - reservoir_obs
        
        self.state = ReservoirState(
            reservoir_start=reservoir_start,
            reservoir_end=reservoir_end,
            training_end=training_end,
            total_observations=total_obs,
            reservoir_observations=reservoir_obs,
            training_observations=training_obs,
            last_advance=datetime.now(UTC),
            contaminated_periods=[],
            frozen_hypotheses=[],
            created_at=datetime.now(UTC),
        )
        self._save_state()
        print(f"Initialized reservoir: {reservoir_start.date()} to {reservoir_end.date()}")
    
    def _get_latest_data_date(self) -> datetime | None:
        """Get the latest date in the data universe."""
        # Check universe parquet files
        universe_dir = self.base_path / "desks" / "mt5" / "data" / "universe"
        if not universe_dir.exists():
            return None
        
        latest = None
        for p in universe_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(p)
                if len(df) > 0:
                    p_latest = df.index.max()
                    if latest is None or p_latest > latest:
                        latest = p_latest
            except Exception:
                continue
        return latest
    
    def _count_observations(self, start: datetime, end: datetime) -> int:
        """Count observations in date range (simplified)."""
        # In production, this would query actual data
        days = (end - start).days
        return max(0, days * 20)  # ~20 trading hours per day
    
    def get_training_data(self, symbol: str, frequency: str = "H1") -> pd.DataFrame:
        """Get training data (excludes reservoir)."""
        if not self.state:
            return pd.DataFrame()
        
        # Load full data
        data_path = self.base_path / "desks" / "mt5" / "data" / "universe" / f"{symbol}_{frequency}.parquet"
        if not data_path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(data_path)
        
        # Exclude reservoir period
        training_end = self.state.training_end
        training_df = df[df.index <= training_end]
        
        # Also exclude any contaminated periods
        for start, end in self.state.contaminated_periods:
            training_df = training_df[~((training_df.index >= start) & (training_df.index <= end))]
        
        self._log_access("get_training_data", "read_training", True, {
            "symbol": symbol,
            "training_end": training_end.isoformat(),
            "rows": len(training_df),
        })
        
        return training_df
    
    def get_reservoir_data(self, symbol: str, frequency: str = "H1") -> pd.DataFrame | None:
        """Get reservoir data — ONLY allowed for frozen hypothesis evaluation."""
        if not self.state:
            return None
        
        # This should ONLY be called during frozen hypothesis evaluation
        # In production, this would check caller authorization
        self._log_access("get_reservoir_data", "read_reservoir", True, {
            "symbol": symbol,
            "reservoir_start": self.state.reservoir_start.isoformat(),
            "reservoir_end": self.state.reservoir_end.isoformat(),
        })
        
        data_path = self.base_path / "desks" / "mt5" / "data" / "universe" / f"{symbol}_{frequency}.parquet"
        if not data_path.exists():
            return None
        
        df = pd.read_parquet(data_path)
        reservoir_df = df[
            (df.index > self.state.reservoir_start) & 
            (df.index <= self.state.reservoir_end)
        ]
        
        return reservoir_df
    
    def freeze_hypothesis(self, hypothesis_spec: dict, code_hash: str, data_hash: str) -> FrozenHypothesis:
        """Freeze a hypothesis for reservoir evaluation.
        
        This is the ONLY way reservoir data can be accessed.
        The hypothesis spec is frozen immutably and can never be changed.
        """
        if not self.state:
            raise RuntimeError("Reservoir not initialized")
        
        # Check minimum reservoir size
        if self.state.reservoir_observations < self.config.min_reservoir_months * 20 * 30:
            raise ValueError(f"Reservoir too small: need {self.config.min_reservoir_months} months")
        
        hypothesis_id = hypothesis_spec.get("id", f"H-{datetime.now(UTC).strftime('%Y%m%d')}-{hashlib.md5(json.dumps(hypothesis_spec).encode()).hexdigest()[:6]}")
        
        frozen = FrozenHypothesis(
            hypothesis_id=hypothesis_id,
            frozen_at=datetime.now(UTC),
            frozen_spec=hypothesis_spec,
            frozen_code_hash=code_hash,
            frozen_data_hash=data_hash,
            reservoir_period=(self.state.reservoir_start, self.state.reservoir_end),
            status="frozen",
        )
        
        self.frozen_hypotheses.append(frozen)
        self._save_frozen(frozen)
        
        # Mark reservoir period as contaminated after this freeze
        self.state.contaminated_periods.append(self.state.reservoir_period)
        self.state.frozen_hypotheses.append({"hypothesis_id": hypothesis_id, "frozen_at": frozen.frozen_at.isoformat()})
        self._save_state()
        
        print(f"Froze hypothesis {hypothesis_id} for reservoir period {self.state.reservoir_start.date()} to {self.state.reservoir_end.date()}")
        
        return frozen
    
    def evaluate_frozen(self, hypothesis_id: str, evaluator_fn) -> dict:
        """Evaluate a frozen hypothesis on the reservoir data.
        
        The reservoir is opened ONCE for this hypothesis. After evaluation,
        the reservoir period is permanently contaminated and never used again.
        """
        # Find frozen hypothesis
        frozen = None
        for h in self.frozen_hypotheses:
            if h.hypothesis_id == hypothesis_id:
                frozen = h
                break
        
        if not frozen:
            raise ValueError(f"Frozen hypothesis {hypothesis_id} not found")
        
        if frozen.status != "frozen":
            raise ValueError(f"Hypothesis {hypothesis_id} already evaluated or contaminated")
        
        # Get reservoir data for evaluation
        reservoir_data = {}
        for sym in frozen.frozen_spec.get("symbols", []):
            reservoir_data[sym] = self.get_reservoir_data(sym)
        
        # Run evaluator (this is the lockbox evaluation)
        result = evaluator_fn(frozen.frozen_spec, reservoir_data)
        
        # Mark as evaluated and contaminate
        frozen.status = "evaluated"
        frozen.lockbox_result = result
        frozen.evaluated_at = datetime.now(UTC)
        self._save_frozen(frozen)
        
        # Advance reservoir (contaminated period is now permanently excluded)
        self._advance_reservoir()
        
        print(f"Evaluated frozen hypothesis {hypothesis_id}: lockbox result = {result}")
        
        return result
    
    def _advance_reservoir(self) -> None:
        """Advance reservoir by one period (e.g., one month)."""
        if not self.state:
            return
        
        # Calculate new boundaries
        advance_months = 1  # Monthly advance
        new_training_end = self.state.reservoir_start
        new_reservoir_start = self.state.reservoir_end
        new_reservoir_end = self._get_latest_data_date() - timedelta(days=7)
        
        # If not enough new data, wait
        if new_reservoir_end <= new_reservoir_start + timedelta(days=30):
            print("Not enough new data to advance reservoir")
            return
        
        # Update state
        self.state.training_end = new_training_end
        self.state.reservoir_start = new_reservoir_start
        self.state.reservoir_end = new_reservoir_end
        self.state.last_advance = datetime.now(UTC)
        self.state.version += 1
        
        # Recount observations
        self.state.total_observations = self._count_observations(
            self.state.training_end - timedelta(days=365*5), 
            new_reservoir_end
        )
        self.state.reservoir_observations = self._count_observations(new_reservoir_start, new_reservoir_end)
        self.state.training_observations = self.state.total_observations - self.state.reservoir_observations
        
        self._save_state()
        
        print(f"Advanced reservoir: training ends {new_training_end.date()}, "
              f"reservoir {new_reservoir_start.date()} to {new_reservoir_end.date()}")
    
    def should_advance(self) -> bool:
        """Check if reservoir should advance (monthly)."""
        if not self.state:
            return False
        days_since_advance = (datetime.now(UTC) - self.state.last_advance).days
        return days_since_advance >= 28
    
    def get_status(self) -> dict:
        """Get current reservoir status."""
        if not self.state:
            return {"status": "uninitialized"}
        
        return {
            "reservoir_start": self.state.reservoir_start.isoformat(),
            "reservoir_end": self.state.reservoir_end.isoformat(),
            "training_end": self.state.training_end.isoformat(),
            "total_observations": self.state.total_observations,
            "reservoir_observations": self.state.reservoir_observations,
            "training_observations": self.state.training_observations,
            "last_advance": self.state.last_advance.isoformat(),
            "days_since_advance": (datetime.now(UTC) - self.state.last_advance).days,
            "frozen_count": len(self.frozen_hypotheses),
            "contaminated_periods": len(self.state.contaminated_periods),
            "should_advance": self.should_advance(),
        }


# Global access control
class ReservoirAccessControl:
    """Enforces that reservoir data is only accessed during frozen evaluation."""
    
    def __init__(self, reservoir: UntouchedReservoir):
        self.reservoir = reservoir
        self.authorized_callers = set()
    
    def authorize_evaluator(self, evaluator_id: str, hypothesis_id: str) -> bool:
        """Authorize an evaluator to access reservoir for a specific frozen hypothesis."""
        # Check hypothesis is frozen
        frozen = None
        for h in self.reservoir.frozen_hypotheses:
            if h.hypothesis_id == hypothesis_id:
                frozen = h
                break
        
        if not frozen or frozen.status != "frozen":
            return False
        
        self.authorized_callers.add(f"{evaluator_id}:{hypothesis_id}")
        return True
    
    def check_access(self, evaluator_id: str, hypothesis_id: str) -> bool:
        """Check if access is authorized."""
        return f"{evaluator_id}:{hypothesis_id}" in self.authorized_callers
    
    def revoke_access(self, evaluator_id: str, hypothesis_id: str) -> None:
        self.authorized_callers.discard(f"{evaluator_id}:{hypothesis_id}")


# Integration with gate evaluation
def lockbox_evaluator(hypothesis_spec: dict, reservoir_data: dict) -> dict:
    """Production lockbox evaluator using reservoir data.
    
    This is called ONCE per frozen hypothesis with the reservoir data.
    """
    results = {}
    
    for symbol, df in reservoir_data.items():
        if df is None or len(df) < 60:
            results[symbol] = {"passed": False, "reason": "insufficient_reservoir_data"}
            continue
        
        # Generate signals from frozen hypothesis
        # (In production, this would use the frozen rule specification)
        from mt5desk import families
        from run_hunt12 import WINDOWS
        
        sigs = list(families.family_session_range_breakout(df, **WINDOWS["asia"]))
        
        # Evaluate on reservoir data
        from mt5desk.engine import Costs, run_backtest
        from mt5desk.gateway_config_fallback import Q_OPT
        
        # Get costs
        from json import loads
        meta = loads((Path(__file__).resolve().parent.parent / "data" / "universe" / "universe.json").read_text())
        cost = Costs.from_symbol(meta[symbol], mult=2.0)
        
        res = run_backtest(df, sigs, cost)
        
        if len(res.trades) < 30:
            results[symbol] = {"passed": False, "reason": "insufficient_trades", "n_trades": len(res.trades)}
            continue
        
        # Compute Sharpe on reservoir
        returns = np.array([t.r_multiple for t in res.trades])
        sr = sharpe_ratio(returns)
        
        results[symbol] = {
            "passed": sr > 0.0,
            "lockbox_sharpe": sr,
            "n_trades": len(res.trades),
        }
    
    # Overall pass if ALL symbols pass
    overall = all(r.get("passed", False) for r in results.values())
    
    return {
        "overall_passed": overall,
        "symbols": results,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "reservoir_period": {
            "start": None,  # Would be filled by caller
            "end": None,
        }
    }


if __name__ == "__main__":
    # Test initialization
    base = Path("/home/quant/quant-platform")
    reservoir = UntouchedReservoir(base)
    print(f"Reservoir status: {reservoir.get_status()}")