"""Stale Relationship / Residual Miner.

Instead of just corr(X,Y), model EXPECTED relationship, then hunt when it breaks.

Example:
  gold_normal = f(real yields, USD, risk, vol)

When gold_actual >> model_expected:
- is gold leading?
- are yields stale?
- is there hidden demand?
- does residual mean-revert?
- does residual predict next macro leg?

Generates: mean-reversion alpha, continuation alpha, regime classification, sizing info.
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

STALE_DIR = DATA_DIR / "stale_relationships"
STALE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FairValueModel:
    """A fair value model for an instrument."""
    target: str
    drivers: list[str]
    model_type: str                            # "linear", "ml", "structural"
    coefficients: dict[str, float]
    r2: float
    last_trained: str
    regime_dependent: bool = False


@dataclass
class ResidualSignal:
    """Signal from residual deviation."""
    timestamp: datetime
    symbol: str
    model_name: str
    residual: float
    z_score: float
    direction: int                             # mean-revert (-sign) or continuation (+sign)
    strength: float
    expected_horizon: str
    regime: str
    context: dict
    subsequent_outcome: dict | None = None


class FairValueModeler:
    """Builds and maintains fair value models."""

    def __init__(self):
        self.models: dict[str, FairValueModel] = {}
        self.residuals: dict[str, pd.Series] = {}

    def train_gold_model(self, data: dict[str, pd.Series]) -> FairValueModel:
        """Gold = f(real yields, DXY, VIX, silver, equities)."""
        required = ["XAUUSD", "REAL_YIELD_10Y", "DXY", "VIX", "XAGUSD", "US500"]
        if not all(k in data for k in required):
            raise ValueError("Missing required data")

        common = data["XAUUSD"].index
        for k in required[1:]:
            common = common.intersection(data[k].index)

        if len(common) < 200:
            raise ValueError("Insufficient data")

        X = pd.DataFrame({k: data[k].loc[common] for k in required[1:]})
        y = data["XAUUSD"].loc[common]

        # Log returns
        X_log = np.log(X / X.shift(1)).dropna()
        y_log = np.log(y / y.shift(1)).dropna()
        common_idx = X_log.index.intersection(y_log.index)
        X_log = X_log.loc[common_idx]
        y_log = y_log.loc[common_idx]

        X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.index)
        X_with_const = pd.concat([X_with_const, X_log], axis=1)

        coeffs = np.linalg.lstsq(X_with_const, y_log, rcond=None)[0]
        y_pred = X_with_const @ coeffs
        r2 = 1 - np.sum((y_log - y_pred) ** 2) / np.sum((y_log - y_log.mean()) ** 2)

        model = FairValueModel(
            target="XAUUSD",
            drivers=required[1:],
            model_type="linear_log",
            coefficients=dict(zip(X_with_const.columns, coeffs)),
            r2=float(r2),
            last_trained=datetime.now(UTC).isoformat(),
            regime_dependent=True,
        )
        self.models["gold_fair_value"] = model
        return model

    def train_fx_triangle_models(self, data: dict[str, pd.Series]) -> dict[str, FairValueModel]:
        """Train all FX triangle models: A × B = C."""
        triangles = {
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
            "AUDCAD": ("AUDUSD", "USDCAD"),
            "CADJPY": ("USDCAD", "USDJPY"),
            "CHFJPY": ("USDCHF", "USDJPY"),
            "NZDJPY": ("NZDUSD", "USDJPY"),
            "NZDCHF": ("NZDUSD", "USDCHF"),
            "NZDCAD": ("NZDUSD", "USDCAD"),
        }

        models = {}
        for target, (leg1, leg2) in triangles.items():
            if leg1 not in data or leg2 not in data or target not in data:
                continue

            common = data[leg1].index.intersection(data[leg2].index).intersection(data[target].index)
            if len(common) < 100:
                continue

            # Synthetic = leg1 * leg2
            synthetic = data[leg1].loc[common] * data[leg2].loc[common]
            actual = data[target].loc[common]

            # Log returns
            syn_log = np.log(synthetic / synthetic.shift(1)).dropna()
            act_log = np.log(actual / actual.shift(1)).dropna()
            common_idx = syn_log.index.intersection(act_log.index)

            if len(common_idx) < 50:
                continue

            # Regress actual on synthetic
            X = pd.DataFrame({"const": 1.0, "synthetic": syn_log.loc[common_idx]})
            y = act_log.loc[common_idx]

            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
            y_pred = X @ coeffs
            r2 = 1 - np.sum((y - y_pred) ** 2) / np.sum((y - y.mean()) ** 2)

            models[f"triangle_{target}"] = FairValueModel(
                target=target,
                drivers=[leg1, leg2],
                model_type="triangle_arbitrage",
                coefficients=dict(zip(X.columns, coeffs)),
                r2=float(r2),
                last_trained=datetime.now(UTC).isoformat(),
            )

        self.models.update(models)
        return models

    def train_oil_fx_models(self, data: dict[str, pd.Series]) -> dict[str, FairValueModel]:
        """Oil-sensitive FX: CAD, NOK, RUB, MXN = f(oil, USD, risk)."""
        pairs = ["USDCAD", "USDNOK", "USDRUB", "USDMXN", "CADJPY", "NOKJPY"]
        models = {}

        required = ["USOIL", "DXY", "VIX", "US10Y"]
        if not all(k in data for k in required):
            return models

        for pair in pairs:
            if pair not in data:
                continue

            common = data[pair].index
            for k in required:
                common = common.intersection(data[k].index)

            if len(common) < 150:
                continue

            X = pd.DataFrame({k: data[k].loc[common] for k in required})
            y = data[pair].loc[common]

            X_log = np.log(X / X.shift(1)).dropna()
            y_log = np.log(y / y.shift(1)).dropna()
            common_idx = X_log.index.intersection(y_log.index)

            if len(common_idx) < 100:
                continue

            X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.loc[common_idx].index)
            X_with_const = pd.concat([X_with_const, X_log.loc[common_idx]], axis=1)

            coeffs = np.linalg.lstsq(X_with_const, y_log.loc[common_idx], rcond=None)[0]
            y_pred = X_with_const @ coeffs
            r2 = 1 - np.sum((y_log.loc[common_idx] - y_pred) ** 2) / np.sum((y_log.loc[common_idx] - y_log.loc[common_idx].mean()) ** 2)

            models[f"oil_fx_{pair}"] = FairValueModel(
                target=pair,
                drivers=required,
                model_type="linear_log",
                coefficients=dict(zip(X_with_const.columns, coeffs)),
                r2=float(r2),
                last_trained=datetime.now(UTC).isoformat(),
            )

        self.models.update(models)
        return models


class StaleRelationshipMiner:
    """Mines stale relationships and residual deviations."""

    def __init__(self):
        self.modeler = FairValueModeler()
        self.residual_signals: list = []

    @dataclass
    class ResidualSignal:
        timestamp: datetime
        symbol: str
        model_name: str
        residual: float
        z_score: float
        direction: int
        strength: float
        expected_horizon: str
        regime: str
        context: dict
        subsequent_outcome: dict | None = None

    def train_all_models(self, data: dict[str, pd.Series]) -> None:
        """Train all fair value models."""
        self.modeler.train_gold_model(data)
        self.modeler.train_fx_triangle_models(data)
        self.modeler.train_oil_fx_models(data)

    def compute_residuals(self, data: dict[str, pd.Series]) -> dict[str, pd.Series]:
        """Compute residuals for all models."""
        residuals = {}

        for name, model in self.modeler.models.items():
            if model.model_type == "linear_log":
                # Need all drivers
                drivers = model.drivers
                if not all(d in data for d in drivers):
                    continue

                common = data[model.target].index
                for d in drivers:
                    common = common.intersection(data[d].index)

                if len(common) < 50:
                    continue

                X = pd.DataFrame({d: data[d].loc[common] for d in drivers})
                X_log = np.log(X / X.shift(1)).dropna()
                X_with_const = pd.DataFrame({"const": 1.0}, index=X_log.index)
                X_with_const = pd.concat([X_with_const, X_log], axis=1)

                coeffs = np.array([model.coefficients.get(c, 0) for c in X_with_const.columns])
                y_pred_log = X_with_const @ coeffs

                base = data[model.target].loc[X_log.index[0]] if X_log.index[0] in data[model.target].index else 1.0
                y_pred = np.exp(y_pred_log.cumsum()) * base / np.exp(y_pred_log.iloc[0])

                actual = data[model.target].loc[y_pred.index]
                res = actual - y_pred
                residuals[name] = res

            elif model.model_type == "triangle_arbitrage":
                leg1, leg2 = model.drivers
                target = model.target
                if leg1 not in data or leg2 not in data or target not in data:
                    continue

                common = data[leg1].index.intersection(data[leg2].index).intersection(data[target].index)
                if len(common) < 50:
                    continue

                synthetic = data[leg1].loc[common] * data[leg2].loc[common]
                actual = data[target].loc[common]
                res = actual - synthetic
                residuals[name] = res

        self.modeler.residuals = residuals
        return residuals

    def detect_residual_signals(self, residuals: dict[str, pd.Series],
                                 regime: str = "normal") -> list:
        """Detect tradeable residual deviations."""
        signals = []

        for name, res in residuals.items():
            if len(res) < 100:
                continue

            # Rolling stats
            rolling_mean = res.rolling(200).mean()
            rolling_std = res.rolling(200).std()
            z = (res - rolling_mean) / (rolling_std + 1e-12)

            # Extreme residuals
            extreme = z[abs(z) > 2.5]
            for ts, z_val in extreme.items():
                if pd.isna(z_val):
                    continue

                model = self.modeler.models.get(name)
                if not model:
                    continue

                # Determine direction: mean-revert vs continuation
                # Check if residual tends to mean-revert
                recent_res = res.loc[:ts].tail(20)
                if len(recent_res) < 10:
                    continue

                # Autocorrelation at lag 1
                acf1 = recent_res.autocorr(lag=1) if len(recent_res) > 1 else 0

                if acf1 < 0.3:
                    # Mean-reverting: fade the residual
                    direction = -1 if z_val > 0 else 1
                    strength = min(abs(z_val) / 4, 1.0)
                else:
                    # Trending/persistent: continue
                    direction = 1 if z_val > 0 else -1
                    strength = min(abs(z_val) / 4, 1.0)

                signals.append(self.ResidualSignal(
                    timestamp=ts,
                    symbol=model.target,
                    model_name=name,
                    residual=res.loc[ts],
                    z_score=z_val,
                    direction=direction,
                    strength=strength,
                    expected_horizon="1h_to_4h",
                    regime=regime,
                    context={
                        "residual": res.loc[ts],
                        "z_score": z_val,
                        "acf1": acf1,
                        "model_r2": model.r2,
                    }
                ))

        self.residual_signals.extend(signals)
        return signals

    def detect_stale_driver(self, symbol: str, data: dict[str, pd.Series]) -> list:
        """Detect when a driver is stale (not updating) while target moves."""
        signals = []

        # For gold, check if real yields are stale while gold moves
        if symbol == "XAUUSD" and "REAL_YIELD_10Y" in data and "XAUUSD" in data:
            gold = data["XAUUSD"]
            yields = data["REAL_YIELD_10Y"]

            common = gold.index.intersection(yields.index)
            if len(common) < 50:
                return signals

            gold_log = np.log(gold / gold.shift(1)).dropna()
            yield_log = np.log(yields / yields.shift(1)).dropna()
            common_idx = gold_log.index.intersection(yield_log.index)

            # Rolling correlation
            corr = gold_log.rolling(50).corr(yield_log)
            gold_vol = gold_log.rolling(20).std()

            # Gold moving but correlation breaking down = stale driver
            for ts in common_idx[-20:]:
                if pd.isna(corr.loc[ts]):
                    continue
                if abs(corr.loc[ts]) < 0.3 and gold_vol.loc[ts] > gold_vol.quantile(0.7):
                    signals.append({
                        "timestamp": ts,
                        "symbol": "XAUUSD",
                        "signal_type": "stale_driver",
                        "driver": "REAL_YIELD_10Y",
                        "direction": 1 if gold_log.loc[ts] > 0 else -1,
                        "strength": 0.7,
                        "expected_horizon": "4h_to_1d",
                        "context": {"correlation": corr.loc[ts], "gold_vol": gold_vol.loc[ts]},
                    })

        return signals

    def record_outcome(self, signal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 8) -> list[SideChannelHypothesis]:
        """Generate hypotheses from residual signals."""
        if len(self.residual_signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.residual_signals:
            key = f"{s.model_name}_{s.symbol}"
            groups[key].append(s)

        hypotheses = []
        for key, signals in groups.items():
            if len(signals) < min_signals:
                continue

            outcomes = [s.subsequent_outcome for s in signals if s.subsequent_outcome]
            if not outcomes:
                continue

            returns = []
            for o in outcomes:
                if "return_r" in o:
                    returns.append(o["return_r"])

            if returns and np.mean(returns) > 0:
                example = signals[0]
                h = SideChannelHypothesis(
                    id=generate_id(),
                    axis=SideChannelAxis.RELATIVE_VALUE,
                    source="stale_relationship_miner",
                    mechanism=f"Stale relationship: {example.model_name} for {example.symbol}. "
                              f"Residual z={example.context.get('z_score', 0):.2f} "
                              f"with acf1={example.context.get('acf1', 0):.2f}. "
                              f"Mean-reversion/continuation signal. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} deviations.",
                    symbols=[example.symbol],
                    timing={
                        "model": example.model_name,
                        "z_score": example.context.get("z_score", 0),
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="micro",
                    metadata={
                        "model": example.model_name,
                        "symbol": example.symbol,
                        "avg_return_r": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(STALE_DIR / "models.json", "w") as f:
            json.dump({name: {
                "target": m.target,
                "drivers": m.drivers,
                "model_type": m.model_type,
                "r2": m.r2,
                "last_trained": m.last_trained,
            } for name, m in self.modeler.models.items()}, f, indent=2)

        with open(STALE_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "model": s.model_name,
                "residual": s.residual,
                "z_score": s.z_score,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "regime": s.regime,
                "context": s.context,
            } for s in self.residual_signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    dates = pd.date_range("2026-01-01", periods=500, freq="1H", tz=UTC)
    np.random.seed(42)

    base = np.cumsum(np.random.randn(500) * 0.001)
    data = {
        "XAUUSD": pd.Series(2000 + base * 10 + np.random.randn(500) * 2, index=dates),
        "REAL_YIELD_10Y": pd.Series(2.0 + base * -0.01, index=dates),
        "DXY": pd.Series(103 + base * -0.1, index=dates),
        "VIX": pd.Series(15 + np.abs(base) * 5, index=dates),
        "XAGUSD": pd.Series(24 + base * 0.1, index=dates),
        "US500": pd.Series(5000 + base * 50, index=dates),
        "USOIL": pd.Series(75 + base * 2, index=dates),
        "DXY": pd.Series(103 + base * -0.1, index=dates),
        "US10Y": pd.Series(4.5 + base * 0.01, index=dates),
        "USDJPY": pd.Series(150 + base * -0.02, index=dates),
        "USDCAD": pd.Series(1.35 + base * 0.002, index=dates),
        "USDNOK": pd.Series(10.5 + base * -0.01, index=dates),
        "USDMXN": pd.Series(18.0 + base * 0.01, index=dates),
        "CADJPY": pd.Series(110 + base * 0.1, index=dates),
        "NOKJPY": pd.Series(14.0 + base * 0.05, index=dates),
    }

    miner = StaleRelationshipMiner()
    miner.train_all_models(data)
    residuals = miner.compute_residuals(data)
    print(f"Computed residuals for {len(residuals)} models")

    signals = []
    for name, res in residuals.items():
        s = miner.detect_residual_signals({name: res})
        signals.extend(s)
    print(f"Detected {len(signals)} residual signals")

    hyps = miner.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} stale relationship hypotheses")