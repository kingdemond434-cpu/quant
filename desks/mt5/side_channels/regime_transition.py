"""Regime Transition Engine — models P(regime changes within N bars).

Instead of just labeling regimes, predicts the PROBABILITY of regime transitions.
Many strategies lose most money around transitions. This creates:
1. Standalone transition alpha
2. Universal portfolio risk/activation overlay
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import logsumexp


@dataclass
class RegimeState:
    """A market regime state."""
    name: str
    features: dict[str, float]               # defining characteristics
    transition_matrix: dict[str, float]      # P(next_regime | current)
    typical_duration_bars: float             # expected persistence
    entry_signals: list[str]                 # what typically precedes entry
    exit_signals: list[str]                  # what typically precedes exit
    risk_profile: dict                       # vol, skew, correlation profile


@dataclass
class TransitionPrediction:
    """Prediction of regime transition."""
    current_regime: str
    target_regime: str
    probability: float                       # P(transition within horizon)
    horizon_bars: int                        # prediction horizon
    confidence: float                        # model confidence
    key_drivers: list[str]                   # features driving prediction
    expected_duration: float | None = None   # expected duration of new regime
    risk_implication: str = ""               # portfolio implication


@dataclass
class RegimeTransitionModel:
    """Trained regime transition model."""
    regimes: list[RegimeState]
    feature_names: list[str]
    transition_models: dict[str, Any]        # regime -> model
    hazard_models: dict[str, Any]            # regime -> duration model
    feature_scaler: Any
    trained_at: datetime
    performance: dict                        # out-of-sample metrics
    metadata: dict = field(default_factory=dict)


class RegimeTransitionEngine:
    """Models and predicts regime transitions."""
    
    def __init__(self, base_path: Path, n_regimes: int = 5, lookback_days: int = 500):
        self.base_path = base_path
        self.n_regimes = n_regimes
        self.lookback_days = lookback_days
        self.model_dir = base_path / "data" / "regime_transition"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.model_file = self.model_dir / "regime_transition_model.pkl"
        self.state_file = self.model_dir / "regime_state.json"
        
        self.model: RegimeTransitionModel | None = None
        self.current_regime: str | None = None
        self.regime_history: list[dict] = []
        
        self._load_model()
    
    def _load_model(self) -> None:
        if self.model_file.exists():
            with open(self.model_file, "rb") as f:
                self.model = pickle.load(f)
        
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                state = json.load(f)
                self.current_regime = state.get("current_regime")
                self.regime_history = state.get("history", [])
    
    def _save_model(self) -> None:
        if self.model:
            with open(self.model_file, "wb") as f:
                pickle.dump(self.model, f)
        
        with open(self.state_file, "w") as f:
            json.dump({
                "current_regime": self.current_regime,
                "history": self.regime_history[-1000:],  # Keep last 1000
                "updated_at": datetime.now(UTC).isoformat(),
            }, f, indent=2)
    
    def prepare_features(self, price_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Extract regime-relevant features from price data."""
        features = {}
        
        # Use primary symbol (XAUUSD) or first available
        primary = "XAUUSD"
        if primary not in price_data:
            primary = list(price_data.keys())[0]
        
        df = price_data[primary].copy()
        
        # Volatility features
        returns = np.log(df["close"]).diff()
        features["vol_5"] = returns.rolling(5).std() * np.sqrt(252)
        features["vol_20"] = returns.rolling(20).std() * np.sqrt(252)
        features["vol_60"] = returns.rolling(60).std() * np.sqrt(252)
        features["vol_ratio_5_20"] = features["vol_5"] / features["vol_20"]
        features["vol_ratio_20_60"] = features["vol_20"] / features["vol_60"]
        
        # Trend features
        features["sma_20"] = df["close"].rolling(20).mean()
        features["sma_60"] = df["close"].rolling(60).mean()
        features["trend_strength"] = (features["sma_20"] - features["sma_60"]) / features["sma_60"]
        features["price_vs_sma20"] = (df["close"] - features["sma_20"]) / features["sma_20"]
        features["price_vs_sma60"] = (df["close"] - features["sma_60"]) / features["sma_60"]
        
        # Momentum
        features["mom_5"] = df["close"].pct_change(5)
        features["mom_20"] = df["close"].pct_change(20)
        features["mom_60"] = df["close"].pct_change(60)
        
        # Volatility of volatility
        features["vol_of_vol"] = features["vol_20"].rolling(20).std()
        
        # Skewness and kurtosis
        features["skew_20"] = returns.rolling(20).skew()
        features["kurt_20"] = returns.rolling(20).kurt()
        
        # Volume/liquidity
        if "tick_volume" in df.columns:
            features["vol_z"] = (df["tick_volume"] - df["tick_volume"].rolling(50).mean()) / df["tick_volume"].rolling(50).std()
            features["spread_z"] = (df["spread"] - df["spread"].rolling(50).mean()) / df["spread"].rolling(50).std()
        
        # Cross-asset features (if available)
        if len(price_data) > 1:
            # Correlation with other assets
            other_returns = {}
            for sym, df_other in price_data.items():
                if sym != primary:
                    other_returns[sym] = np.log(df_other["close"]).diff()
            
            if other_returns:
                other_df = pd.DataFrame(other_returns, index=returns.index)
                features["avg_cross_corr"] = other_df.rolling(20).corrwith(returns).mean(axis=1)
                features["max_cross_corr"] = other_df.rolling(20).corrwith(returns).max(axis=1)
        
        # Session/time features
        features["hour"] = features.index.hour
        features["day_of_week"] = features.index.dayofweek
        features["is_london"] = ((features["hour"] >= 7) & (features["hour"] < 16)).astype(float)
        features["is_ny"] = ((features["hour"] >= 13) & (features["hour"] < 22)).astype(float)
        features["is_asia"] = ((features["hour"] >= 0) & (features["hour"] < 7)).astype(float)
        
        feature_df = pd.DataFrame(features)
        feature_df = feature_df.dropna()
        
        return feature_df
    
    def identify_regimes(self, features: pd.DataFrame, method: str = "hmm") -> tuple[np.ndarray, list[RegimeState]]:
        """Identify regimes from features."""
        from sklearn.preprocessing import StandardScaler
        from sklearn.mixture import GaussianMixture
        
        # Prepare data
        X = features.select_dtypes(include=[np.number]).dropna()
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        if method == "hmm":
            # Gaussian Mixture Model (simplified HMM)
            gmm = GaussianMixture(n_components=self.n_regimes, covariance_type="full", random_state=42)
            labels = gmm.fit_predict(X_scaled)
            
            # Compute regime states
            regimes = []
            for i in range(self.n_regimes):
                mask = labels == i
                if mask.sum() < 10:
                    continue
                
                regime_features = X[mask].mean().to_dict()
                
                # Compute transition probabilities
                transitions = {}
                for j in range(self.n_regimes):
                    trans_count = np.sum((labels[:-1] == i) & (labels[1:] == j))
                    total_from_i = np.sum(labels[:-1] == i)
                    transitions[f"regime_{j}"] = trans_count / total_from_i if total_from_i > 0 else 0
                
                # Duration
                durations = []
                current = 0
                for label in labels:
                    if label == i:
                        current += 1
                    elif current > 0:
                        durations.append(current)
                        current = 0
                if current > 0:
                    durations.append(current)
                
                typical_duration = np.mean(durations) if durations else 1
                
                regimes.append(RegimeState(
                    name=f"regime_{i}",
                    features=regime_features,
                    transition_matrix=transitions,
                    typical_duration_bars=float(typical_duration),
                    entry_signals=[],  # Would compute from feature changes
                    exit_signals=[],
                    risk_profile={},
                ))
        
        return np.array(labels), regimes
    
    def build_transition_models(self, features: pd.DataFrame, labels: np.ndarray) -> dict:
        """Build predictive models for regime transitions."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.calibration import CalibratedClassifierCV
        
        models = {}
        
        # For each regime, build a classifier predicting transition TO that regime
        for i in range(self.n_regimes):
            # Create binary target: will transition TO regime i within N bars?
            horizon = 20  # bars
            target = np.zeros(len(labels), dtype=int)
            
            for j in range(len(labels) - horizon):
                if labels[j] != i and labels[j + horizon] == i:
                    target[j] = 1
            
            # Features for prediction
            X = features.select_dtypes(include=[np.number]).dropna()
            target = target[:len(X)]
            
            if target.sum() < 10:
                continue
            
            # Train calibrated classifier
            clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, class_weight="balanced")
            clf = CalibratedClassifierCV(clf, cv=3, method="isotonic")
            
            try:
                clf.fit(X, target)
                models[f"to_regime_{i}"] = clf
            except Exception:
                continue
        
        return models
    
    def build_hazard_models(self, labels: np.ndarray) -> dict:
        """Build duration/hazard models for each regime."""
        from lifelines import WeibullAFTFitter
        import warnings
        warnings.filterwarnings("ignore")
        
        hazard_models = {}
        
        for i in range(self.n_regimes):
            # Extract durations for regime i
            durations = []
            current = 0
            for label in labels:
                if label == i:
                    current += 1
                elif current > 0:
                    durations.append(current)
                    current = 0
            if current > 0:
                durations.append(current)
            
            if len(durations) < 5:
                continue
            
            # Fit Weibull AFT model
            try:
                df_dur = pd.DataFrame({"duration": durations})
                aft = WeibullAFTFitter()
                aft.fit(df_dur, duration_col="duration")
                hazard_models[f"regime_{i}"] = aft
            except Exception:
                pass
        
        return hazard_models
    
    def train(self, price_data: dict[str, pd.DataFrame]) -> RegimeTransitionModel:
        """Train the full regime transition model."""
        print("Preparing features...")
        features = self.prepare_features(price_data)
        
        print("Identifying regimes...")
        labels, regimes = self.identify_regimes(features)
        
        print("Building transition models...")
        transition_models = self.build_transition_models(features, labels)
        
        print("Building hazard models...")
        hazard_models = self.build_hazard_models(labels)
        
        # Current regime
        current = f"regime_{labels[-1]}" if len(labels) > 0 else "regime_0"
        
        # Record history
        self.regime_history.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "regime": current,
            "features": features.iloc[-1].to_dict() if len(features) > 0 else {},
        })
        
        self.model = RegimeTransitionModel(
            regimes=regimes,
            feature_names=list(features.columns),
            transition_models=transition_models,
            hazard_models=hazard_models,
            feature_scaler=None,  # Would store scaler
            trained_at=datetime.now(UTC),
            performance=self._evaluate_model(features, labels, transition_models),
            metadata={"n_regimes": self.n_regimes, "training_samples": len(features)},
        )
        
        self.current_regime = current
        self._save_model()
        
        return self.model
    
    def _evaluate_model(self, features: pd.DataFrame, labels: np.ndarray, 
                         models: dict) -> dict:
        """Evaluate model performance."""
        # Simple evaluation
        return {
            "n_regimes": self.n_regimes,
            "training_samples": len(features),
            "regime_distribution": {f"regime_{i}": int(np.sum(labels == i)) for i in range(self.n_regimes)},
        }
    
    def predict_transition(self, price_data: dict[str, pd.DataFrame],
                            horizon_bars: int = 20) -> list[TransitionPrediction]:
        """Predict regime transitions."""
        if not self.model:
            return []
        
        features = self.prepare_features(price_data)
        if features.empty:
            return []
        
        X = features.select_dtypes(include=[np.number]).dropna().iloc[[-1]]
        
        predictions = []
        current = self.current_regime
        
        for model_name, clf in self.model.transition_models.items():
            target_regime = model_name.replace("to_regime_", "regime_")
            if target_regime == current:
                continue
            
            try:
                prob = clf.predict_proba(X)[0, 1]
                if prob > 0.1:  # Only report meaningful probabilities
                    pred = TransitionPrediction(
                        current_regime=current,
                        target_regime=target_regime,
                        probability=float(prob),
                        horizon_bars=20,
                        confidence=min(prob * 2, 1.0),
                        key_drivers=[],  # Would extract feature importance
                        risk_implication=self._get_risk_implication(current, target_regime),
                    )
                    predictions.append(pred)
            except Exception:
                continue
        
        predictions.sort(key=lambda x: -x.probability)
        return predictions
    
    def _get_risk_implication(self, from_regime: str, to_regime: str) -> str:
        """Determine portfolio risk implication of transition."""
        # Simplified mapping
        risky_transitions = {
            ("regime_0", "regime_1"): "vol_expansion_reduce_leverage",
            ("regime_1", "regime_0"): "vol_contraction_increase_size",
            ("regime_2", "regime_3"): "trend_break_reduce_directional",
        }
        return risky_transitions.get((from_regime, to_regime), "monitor")
    
    def get_current_state(self) -> dict:
        """Get current regime state."""
        if not self.model:
            return {"status": "untrained"}
        
        return {
            "current_regime": self.current_regime,
            "regime_history": self.regime_history[-10:],
            "n_regimes": self.n_regimes,
            "trained_at": self.model.trained_at.isoformat() if self.model else None,
            "regimes": [{"name": r.name, "duration": r.typical_duration_bars} for r in self.model.regimes],
        }
    
    def should_reduce_risk(self, price_data: dict[str, pd.DataFrame]) -> tuple[bool, str]:
        """Check if portfolio should reduce risk based on regime transition."""
        preds = self.predict_transition(price_data)
        
        for p in preds:
            if p.probability > 0.6 and "reduce" in p.risk_implication:
                return True, f"High probability ({p.probability:.1%}) of {p.target_regime}: {p.risk_implication}"
        
        return False, ""


def compute_regime_overlay(state: dict, portfolio_state: dict) -> dict:
    """Compute regime transition overlay for portfolio."""
    if not state or state.get("status") == "untrained":
        return {"active": False, "reason": "model_not_trained"}
    
    current = state.get("current_regime", "unknown")
    
    # Base allocation by regime
    regime_allocations = {
        "regime_0": {"leverage": 1.0, "max_dd": 0.5},   # Low vol trending
        "regime_1": {"leverage": 0.7, "max_dd": 0.3},   # High vol
        "regime_2": {"leverage": 1.0, "max_dd": 0.4},   # Trending
        "regime_3": {"leverage": 0.5, "max_dd": 0.2},   # Crisis
        "regime_4": {"leverage": 1.2, "max_dd": 0.5},   # Low vol mean reversion
    }
    
    base = regime_allocations.get(current, {"leverage": 1.0, "max_dd": 0.5})
    
    return {
        "active": True,
        "current_regime": current,
        "leverage_multiplier": base["leverage"],
        "max_drawdown_limit": base["max_dd"],
        "transition_risk": "low",  # Would check predictions
    }


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    
    # Load price data
    universe_dir = base / "desks" / "mt5" / "data" / "universe"
    price_data = {}
    for p in sorted(universe_dir.glob("*.parquet")):
        sym = p.stem
        price_data[sym] = pd.read_parquet(p)
    
    print(f"Loaded {len(price_data)} symbols")
    
    engine = RegimeTransitionEngine(base, n_regimes=5)
    
    print("Training regime transition model...")
    model = engine.train(price_data)
    
    print(f"Trained with {model.metadata['training_samples']} samples")
    print(f"Regimes: {[r.name for r in model.regimes]}")
    
    print("\nCurrent state:", engine.get_current_state())