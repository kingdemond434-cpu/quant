"""Synthetic Price / Residual Miner — builds fair value models and trades deviations.

Markets that mathematically should agree:
- FX triangles: EURUSD × USDJPY ≈ EURJPY
- Metals: gold = f(real yields, USD, risk, vol)
- Oil/FX: oil → CAD/NOK crosses
- Equity index: CFD vs futures vs sector baskets
- Synthetic indices: index vs constituent/sector proxies
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

SYNTH_DIR = DATA_DIR / "synthetic_models"
SYNTH_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SyntheticModel:
    """A synthetic/fair value model for an instrument."""
    name: str
    target_symbol: str
    drivers: list[str]                         # input symbols/features
    model_type: str                            # "linear", "ml", "arbitrage", "structural"
    coefficients: dict[str, float]             # model parameters
    r2: float                                  # in-sample fit
    oos_r2: float                              # out-of-sample fit
    last_trained: str
    regime_dependent: bool = False


@dataclass
class SyntheticResidual:
    """Residual between actual and synthetic price."""
    timestamp: datetime
    symbol: str
    synthetic_model: str
    actual_price: float
    synthetic_price: float
    residual: float                            # actual - synthetic
    z_score: float                             # residual / rolling_std
    regime: str


class FXTriangleModel:
    """EURUSD × USDJPY = EURJPY (and all other triangles)."""

    TRIANGLES = {
        "EURJPY": ("EURUSD", "USDJPY"),
        "EURGBP": ("EURUSD", "GBPUSD"),
        "EURCHF": ("EURUSD", "USDCHF"),
        "EURAUD": ("EURUSD", "AUDUSD"),
        "EURCAD": ("EURUSD", "USDCAD"),
        "GBPJPY": ("GBPUSD", "USDJPY"),
        "GBPCHF": ("GBPUSD", "USDCHF"),
        "GBPAUD": ("GBPUSD", "AUDUSD"),
        "GBPCAD": ("GBPUSD", "USDCAD"),
        "AUDJPY": ("AUDUSD", "USDJPY"),
        "AUDCHF": ("AUDUSD", "USDCHF"),
        "AUDCAD": ("AUDUSD", "USDCAD"),
        "CADJPY": ("USDCAD", "USDJPY"),
        "CHFJPY": ("USDCHF", "USDJPY"),
        "NZDJPY": ("NZDUSD", "USDJPY"),
        "NZDCHF": ("NZDUSD", "USDCHF"),
        "NZDCAD": ("NZDUSD", "USDCAD"),
    }

    def __init__(self):
        self.residuals: dict[str, pd.Series] = {}

    def compute_synthetic(self, prices: dict[str, pd.Series]) -> dict[str, pd.Series]:
        """Compute synthetic prices for all triangles."""
        synthetic = {}
        for target, (leg1, leg2) in self.TRIANGLES.items():
            if leg1 in prices and leg2 in prices:
                # Align indices
                common_idx = prices[leg1].index.intersection(prices[leg2].index)
                if len(common_idx) > 100:
                    synthetic[target] = prices[leg1].loc[common_idx] * prices[leg2].loc[common_idx]
        return synthetic

    def compute_residuals(self, prices: dict[str, pd.Series],
                          synthetic: dict[str, pd.Series]) -> dict[str, pd.Series]:
        """Compute residuals: actual - synthetic."""
        residuals = {}
        for target in self.TRIANGLES:
            if target in prices and target in synthetic:
                common_idx = prices[target].index.intersection(synthetic[target].index)
                if len(common_idx) > 50:
                    res = prices[target].loc[common_idx] - synthetic[target].loc[common_idx]
                    residuals[target] = res
        return residuals

    def get_tradeable_residuals(self, residuals: dict[str, pd.Series],
                                 z_threshold: float = 2.0) -> list[SyntheticResidual]:
        """Find residuals exceeding z-score threshold."""
        trades = []
        for target, res in residuals.items():
            if len(res) < 100:
                continue
            rolling_mean = res.rolling(200).mean()
            rolling_std = res.rolling(200).std()
            z = (res - rolling_mean) / (rolling_std + 1e-12)

            # Find extreme residuals
            extreme = z[abs(z) > z_threshold]
            for ts, z_val in extreme.items():
                if pd.isna(z_val):
                    continue
                trades.append(SyntheticResidual(
                    timestamp=ts,
                    symbol=target,
                    synthetic_model="fx_triangle",
                    actual_price=prices[target].loc[ts] if target in prices and ts in prices[target].index else 0,
                    synthetic_price=synthetic[target].loc[ts] if target in synthetic and ts in synthetic[target].index else 0,
                    residual=res.loc[ts],
                    z_score=z_val,
                    regime=self._get_regime(ts),
                ))
        return trades

    def _get_regime(self, ts: datetime) -> str:
        hour = ts.hour
        if 7 <= hour < 16:
            return "london"
        elif 13 <= hour < 22:
            return "ny"
        else:
            return "asia"


class MetalsModel:
    """Gold = f(real yields, USD, risk, vol, silver, miners)."""

    def __init__(self):
        self.model: SyntheticModel | None = None

    def train(self, data: dict[str, pd.Series]) -> SyntheticModel:
        """Train gold synthetic model."""
        # Align all series
        required = ["XAUUSD", "REAL_YIELD_10Y", "DXY", "VIX", "XAGUSD", "US500"]
        if not all(k in data for k in required):
            raise ValueError(f"Missing required data: {set(required) - set(data.keys())}")

        common_idx = data["XAUUSD"].index
        for k in required[1:]:
            common_idx = common_idx.intersection(data[k].index)

        if len(common_idx) < 200:
            raise ValueError("Insufficient overlapping data")

        X = pd.DataFrame({
            "real_yield": data["REAL_YIELD_10Y"].loc[common_idx],
            "dxy": data["DXY"].loc[common_idx],
            "vix": data["VIX"].loc[common_idx],
            "silver": data["XAGUSD"].loc[common_idx],
            "equity": data["US500"].loc[common_idx],
        })
        y = data["XAUUSD"].loc[common_idx]

        # Log returns for stationarity
        X_log = np.log(X / X.shift(1)).dropna()
        y_log = np.log(y / y.shift(1)).dropna()
        common = X_log.index.intersection(y_log.index)
        X_log = X_log.loc[common]
        y_log = y_log.loc[common]

        # OLS
        X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.index)
        X_with_const = pd.concat([X_with_const, X_log], axis=1)
        coeffs = np.linalg.lstsq(X_with_const, y_log, rcond=None)[0]

        # Predictions
        y_pred_log = X_with_const @ coeffs
        y_pred = np.exp(y_pred_log.cumsum()) * y.iloc[0] / np.exp(y_pred_log.iloc[0])

        r2 = 1 - np.sum((y - y_pred) ** 2) / np.sum((y - y.mean()) ** 2)

        # OOS: last 20%
        split = int(len(common) * 0.8)
        y_oos = y.iloc[split:]
        y_pred_oos = y_pred.iloc[split:]
        oos_r2 = 1 - np.sum((y_oos - y_pred_oos) ** 2) / np.sum((y_oos - y_oos.mean()) ** 2)

        self.model = SyntheticModel(
            name="metals_gold_model",
            target_symbol="XAUUSD",
            drivers=required[1:],
            model_type="linear_log",
            coefficients=dict(zip(X_with_const.columns, coeffs)),
            r2=float(r2),
            oos_r2=float(oos_r2),
            last_trained=datetime.now(UTC).isoformat(),
            regime_dependent=True,
        )
        return self.model

    def predict(self, data: dict[str, pd.Series]) -> pd.Series:
        """Generate synthetic gold price."""
        if self.model is None:
            self.train(data)

        required = ["REAL_YIELD_10Y", "DXY", "VIX", "XAGUSD", "US500"]
        common_idx = data[required[0]].index
        for k in required[1:]:
            common_idx = common_idx.intersection(data[k].index)

        X = pd.DataFrame({k: data[k].loc[common_idx] for k in required})
        X_log = np.log(X / X.shift(1)).dropna()

        X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.index)
        X_with_const = pd.concat([X_with_const, X_log], axis=1)

        coeffs = np.array([self.model.coefficients.get(c, 0) for c in X_with_const.columns])
        y_pred_log = X_with_const @ coeffs

        # Reconstruct price level
        base_price = data["XAUUSD"].loc[X_log.index[0]] if X_log.index[0] in data["XAUUSD"].index else 2000
        y_pred = np.exp(y_pred_log.cumsum()) * base_price / np.exp(y_pred_log.iloc[0])

        return y_pred

    def compute_residuals(self, data: dict[str, pd.Series]) -> pd.Series:
        """Compute gold residuals."""
        synthetic = self.predict(data)
        actual = data["XAUUSD"].loc[synthetic.index]
        return actual - synthetic


class OilFXModel:
    """Oil-sensitive FX: CAD, NOK, RUB, MXN = f(oil, USD, risk)."""

    OIL_SENSITIVE = ["USDCAD", "USDNOK", "USDRUB", "USDMXN", "CADJPY", "NOKJPY"]

    def __init__(self):
        self.models: dict[str, SyntheticModel] = {}

    def train_all(self, data: dict[str, pd.Series]) -> dict[str, SyntheticModel]:
        """Train models for all oil-sensitive pairs."""
        required = ["USOIL", "UKOIL", "DXY", "VIX", "US10Y"]
        if not all(k in data for k in required):
            raise ValueError("Missing required data")

        for pair in self.OIL_SENSITIVE:
            if pair not in data:
                continue

            common_idx = data[pair].index
            for k in required:
                common_idx = common_idx.intersection(data[k].index)

            if len(common_idx) < 150:
                continue

            X = pd.DataFrame({
                "wti": data["USOIL"].loc[common_idx],
                "brent": data["UKOIL"].loc[common_idx],
                "dxy": data["DXY"].loc[common_idx],
                "vix": data["VIX"].loc[common_idx],
                "yields": data["US10Y"].loc[common_idx],
            })
            y = data[pair].loc[common_idx]

            # Log returns
            X_log = np.log(X / X.shift(1)).dropna()
            y_log = np.log(y / y.shift(1)).dropna()
            common = X_log.index.intersection(y_log.index)

            X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.loc[common].index)
            X_with_const = pd.concat([X_with_const, X_log.loc[common]], axis=1)

            try:
                coeffs = np.linalg.lstsq(X_with_const, y_log.loc[common], rcond=None)[0]
            except np.linalg.LinAlgError:
                continue

            y_pred_log = X_with_const @ coeffs
            r2 = 1 - np.sum((y_log.loc[common] - y_pred_log) ** 2) / np.sum((y_log.loc[common] - y_log.loc[common].mean()) ** 2)

            self.models[pair] = SyntheticModel(
                name=f"oil_fx_{pair}",
                target_symbol=pair,
                drivers=required,
                model_type="linear_log",
                coefficients=dict(zip(X_with_const.columns, coeffs)),
                r2=float(r2),
                oos_r2=float(r2),  # Simplified
                last_trained=datetime.now(UTC).isoformat(),
            )

        return self.models

    def compute_residuals(self, data: dict[str, pd.Series]) -> dict[str, pd.Series]:
        """Compute residuals for all pairs."""
        residuals = {}
        for pair, model in self.models.items():
            if pair not in data:
                continue
            required = ["USOIL", "UKOIL", "DXY", "VIX", "US10Y"]
            common_idx = data[pair].index
            for k in required:
                common_idx = common_idx.intersection(data[k].index)

            X = pd.DataFrame({k: data[k].loc[common_idx] for k in required})
            X_log = np.log(X / X.shift(1)).dropna()
            X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.index)
            X_with_const = pd.concat([X_with_const, X_log], axis=1)

            coeffs = np.array([model.coefficients.get(c, 0) for c in X_with_const.columns])
            y_pred_log = X_with_const @ coeffs

            base = data[pair].loc[X_log.index[0]] if X_log.index[0] in data[pair].index else 1.0
            y_pred = np.exp(y_pred_log.cumsum()) * base / np.exp(y_pred_log.iloc[0])

            actual = data[pair].loc[y_pred.index]
            residuals[pair] = actual - y_pred

        return residuals


class SyntheticResidualMiner:
    """Master miner for all synthetic models."""

    def __init__(self):
        self.fx_triangle = FXTriangleModel()
        self.metals = MetalsModel()
        self.oil_fx = OilFXModel()
        self.residuals: list[SyntheticResidual] = []

    def train_all(self, data: dict[str, pd.Series]) -> None:
        """Train all synthetic models."""
        self.metals.train(data)
        self.oil_fx.train_all(data)

    def compute_all_residuals(self, data: dict[str, pd.Series]) -> list[SyntheticResidual]:
        """Compute residuals across all models."""
        all_residuals = []

        # FX Triangles
        synthetic_fx = self.fx_triangle.compute_synthetic(data)
        residuals_fx = self.fx_triangle.compute_residuals(data, synthetic_fx)
        all_residuals.extend(self.fx_triangle.get_tradeable_residuals(residuals_fx))

        # Metals
        if all(k in data for k in ["XAUUSD", "REAL_YIELD_10Y", "DXY", "VIX", "XAGUSD", "US500"]):
            gold_res = self.metals.compute_residuals(data)
            if len(gold_res) > 50:
                rolling_mean = gold_res.rolling(200).mean()
                rolling_std = gold_res.rolling(200).std()
                z = (gold_res - rolling_mean) / (rolling_std + 1e-12)
                extreme = z[abs(z) > 2.0]
                for ts, z_val in extreme.items():
                    if pd.isna(z_val):
                        continue
                    self.residuals.append(SyntheticResidual(
                        timestamp=ts,
                        symbol="XAUUSD",
                        synthetic_model="metals_gold_model",
                        actual_price=actual.loc[ts],
                        synthetic_price=synthetic.loc[ts],
                        residual=gold_res.loc[ts],
                        z_score=z_val,
                        regime=self._get_regime(ts),
                    ))

        # Oil FX
        oil_residuals = self.oil_fx.compute_residuals(data)
        for pair, res in oil_residuals.items():
            if len(res) > 50:
                rolling_mean = res.rolling(200).mean()
                rolling_std = res.rolling(200).std()
                z = (res - rolling_mean) / (rolling_std + 1e-12)
                extreme = z[abs(z) > 2.0]
                for ts, z_val in extreme.items():
                    if pd.isna(z_val):
                        continue
                    self.residuals.append(SyntheticResidual(
                        timestamp=ts,
                        symbol=pair,
                        synthetic_model=f"oil_fx_{pair}",
                        actual_price=data[pair].loc[ts],
                        synthetic_price=data[pair].loc[ts] - res.loc[ts],
                        residual=res.loc[ts],
                        z_score=z_val,
                        regime=self._get_regime(ts),
                    ))

        return self.residuals

    def _get_regime(self, ts: datetime) -> str:
        hour = ts.hour
        if 7 <= hour < 16:
            return "london"
        elif 13 <= hour < 22:
            return "ny"
        else:
            return "asia"

    def generate_hypotheses(self, min_z: float = 2.5) -> list[SideChannelHypothesis]:
        """Generate hypotheses from synthetic residuals."""
        hypotheses = []

        for res in self.residuals:
            if abs(res.z_score) < min_z:
                continue

            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.RELATIVE_VALUE,
                source="synthetic_residual_miner",
                mechanism=f"{res.symbol} deviates from synthetic fair value "
                          f"({res.synthetic_model}: z={res.z_score:.2f}). "
                          f"Mean reversion expected.",
                symbols=[res.symbol],
                timing={
                    "model": res.synthetic_model,
                    "z_score": res.z_score,
                    "residual": res.residual,
                    "regime": res.regime,
                },
                falsifier=f"Residual persists beyond 3 std for >10 bars without mean reversion",
                expected_horizon="15m_to_4h",
                capacity_estimate="micro",
                metadata={
                    "model": res.synthetic_model,
                    "z_score": res.z_score,
                    "residual": res.residual,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        """Save models and residuals."""
        import json
        # Save models
        models_data = {
            "metals": self.metals.model.__dict__ if self.metals.model else None,
            "oil_fx": {k: v.__dict__ for k, v in self.oil_fx.models.items()},
        }
        with open(SYNTH_DIR / "models.json", "w") as f:
            json.dump(models_data, f, indent=2, default=str)

        # Save residuals
        res_data = [{
            "timestamp": r.timestamp.isoformat(),
            "symbol": r.symbol,
            "model": r.synthetic_model,
            "actual": r.actual_price,
            "synthetic": r.synthetic_price,
            "residual": r.residual,
            "z_score": r.z_score,
            "regime": r.regime,
        } for r in self.residuals]
        with open(SYNTH_DIR / "residuals.json", "w") as f:
            json.dump(res_data, f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    dates = pd.date_range("2026-01-01", periods=500, freq="1H", tz=UTC)
    np.random.seed(42)

    # Create synthetic correlated data
    base = np.cumsum(np.random.randn(500) * 0.001)
    data = {
        "EURUSD": pd.Series(1.08 + base * 0.005, index=dates),
        "USDJPY": pd.Series(150 + base * -0.02 + np.random.randn(500) * 0.1, index=dates),
        "GBPUSD": pd.Series(1.27 + base * 0.004, index=dates),
        "USDCHF": pd.Series(0.90 + base * -0.003, index=dates),
        "AUDUSD": pd.Series(0.65 + base * 0.006, index=dates),
        "USDCAD": pd.Series(1.36 + base * 0.002, index=dates),
        "XAUUSD": pd.Series(2000 + base * 10 + np.random.randn(500) * 2, index=dates),
        "REAL_YIELD_10Y": pd.Series(2.0 + base * -0.01, index=dates),
        "DXY": pd.Series(103 + base * -0.1, index=dates),
        "VIX": pd.Series(15 + np.abs(base) * 5, index=dates),
        "XAGUSD": pd.Series(24 + base * 0.1, index=dates),
        "US500": pd.Series(5000 + base * 50, index=dates),
        "USOIL": pd.Series(75 + base * 2, index=dates),
        "UKOIL": pd.Series(78 + base * 2, index=dates),
    }

    miner = SyntheticResidualMiner()
    miner.train_all(data)
    residuals = miner.compute_all_residuals(data)
    print(f"Found {len(residuals)} tradeable residuals")

    hyps = miner.generate_hypotheses()
    print(f"Generated {len(hyps)} synthetic residual hypotheses")