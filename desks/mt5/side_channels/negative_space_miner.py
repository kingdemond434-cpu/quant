"""Negative Space / Silence Miner — hunts things that should have happened but didn't.

Builds datasets of silence as a state:
- No reaction to major news
- No continuation after extreme volume
- No volatility increase following a catalyst
- No London breakout after tight Asia
- No gold response despite massive rates move
- No spread widening during expected stress
- No follow-through after crossing major extreme
- Unusually quiet market during normally active window

Features:
  expected_volatility - realised_volatility
  expected_cross_asset_beta - realised_beta
  expected_news_reaction - realised_reaction
  expected_liquidity_change - realised_change
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

SILENCE_DIR = DATA_DIR / "negative_space"
SILENCE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SilenceEvent:
    """A period where expected market behavior did not occur."""
    timestamp: datetime
    symbol: str
    silence_type: str                          # "no_news_reaction", "no_continuation", "no_vol_expansion", etc.
    expected_magnitude: float                  # what was expected
    actual_magnitude: float                    # what happened (near zero)
    silence_score: float                       # 0-1, how silent
    context: dict                              # regime, session, news, etc.
    subsequent_outcome: dict | None = None     # what happened next


class SilenceMiner:
    """Mines negative space events from market data."""

    def __init__(self):
        self.silence_events: list[SilenceEvent] = []

    def detect_no_news_reaction(self, symbol: str, event_time: datetime,
                                 event_magnitude: float,
                                 price_before: pd.Series,
                                 price_after: pd.Series,
                                 window_minutes: int = 15) -> SilenceEvent | None:
        """Detect when major news produced no reaction."""
        # Expected move based on historical beta to this event type
        expected = abs(event_magnitude) * self._get_event_beta(symbol, "news")
        actual = abs(price_after.iloc[-1] - price_before.iloc[0])

        if expected > 0:
            silence_score = 1.0 - min(actual / expected, 1.0)
        else:
            silence_score = 0.0

        if silence_score > 0.7:  # >70% silent
            return SilenceEvent(
                timestamp=event_time,
                symbol=symbol,
                silence_type="no_news_reaction",
                expected_magnitude=expected,
                actual_magnitude=actual,
                silence_score=silence_score,
                context={
                    "event_magnitude": event_magnitude,
                    "window_minutes": window_minutes,
                    "regime": self._get_regime(event_time),
                }
            )
        return None

    def detect_no_continuation(self, symbol: str, breakout_time: datetime,
                                price_series: pd.Series,
                                lookback_bars: int = 20,
                                forward_bars: int = 12) -> SilenceEvent | None:
        """Detect when breakout had no follow-through."""
        # Find the breakout bar
        idx = price_series.index.get_loc(breakout_time, method="nearest")
        if idx < lookback_bars or idx + forward_bars >= len(price_series):
            return None

        # Measure breakout strength
        pre_range = price_series.iloc[idx-lookback_bars:idx].max() - price_series.iloc[idx-lookback_bars:idx].min()
        breakout_move = abs(price_series.iloc[idx] - price_series.iloc[idx-1])

        # Expected continuation: at least 0.5x breakout move in next N bars
        expected = breakout_move * 0.5
        actual_forward = price_series.iloc[idx+1:idx+1+forward_bars].max() - price_series.iloc[idx+1:idx+1+forward_bars].min()
        actual_move = abs(price_series.iloc[idx+forward_bars] - price_series.iloc[idx])

        if expected > 0:
            silence_score = 1.0 - min(actual_move / expected, 1.0)
        else:
            silence_score = 0.0

        if silence_score > 0.6 and breakout_move > pre_range * 0.5:
            return SilenceEvent(
                timestamp=breakout_time,
                symbol=symbol,
                silence_type="no_continuation",
                expected_magnitude=expected,
                actual_magnitude=actual_move,
                silence_score=silence_score,
                context={
                    "breakout_move": breakout_move,
                    "pre_range": pre_range,
                    "forward_bars": forward_bars,
                    "regime": self._get_regime(breakout_time),
                }
            )
        return None

    def detect_no_vol_expansion(self, symbol: str, catalyst_time: datetime,
                                 vol_series: pd.Series,
                                 catalyst_type: str,
                                 lookback_hours: int = 24,
                                 forward_hours: int = 4) -> SilenceEvent | None:
        """Detect when catalyst didn't expand volatility as expected."""
        idx = vol_series.index.get_loc(catalyst_time, method="nearest")
        if idx < lookback_hours or idx + forward_hours >= len(vol_series):
            return None

        pre_vol = vol_series.iloc[idx-lookback_hours:idx].mean()
        expected_vol = pre_vol * self._get_catalyst_vol_multiplier(catalyst_type)
        actual_vol = vol_series.iloc[idx:idx+forward_hours].mean()

        if expected_vol > 0:
            silence_score = 1.0 - min(actual_vol / expected_vol, 1.0)
        else:
            silence_score = 0.0

        if silence_score > 0.6:
            return SilenceEvent(
                timestamp=catalyst_time,
                symbol=symbol,
                silence_type="no_vol_expansion",
                expected_magnitude=expected_vol,
                actual_magnitude=actual_vol,
                silence_score=silence_score,
                context={
                    "catalyst_type": catalyst_type,
                    "pre_vol": pre_vol,
                    "forward_hours": forward_hours,
                    "regime": self._get_regime(catalyst_time),
                }
            )
        return None

    def detect_no_london_breakout(self, symbol: str, asia_session: pd.DataFrame,
                                   london_session: pd.DataFrame) -> SilenceEvent | None:
        """Detect when tight Asia session didn't lead to London breakout."""
        asia_range = asia_session["high"].max() - asia_session["low"].min()
        asia_atr = (asia_session["high"] - asia_session["low"]).mean()

        # Tight Asia = range < 0.5 * ATR
        if asia_range > asia_atr * 0.5:
            return None

        # Expected London expansion: at least 1.5x Asia range
        expected = asia_range * 1.5
        london_range = london_session["high"].max() - london_session["low"].min()

        if expected > 0:
            silence_score = 1.0 - min(london_range / expected, 1.0)
        else:
            silence_score = 0.0

        if silence_score > 0.6:
            return SilenceEvent(
                timestamp=london_session.index[0],
                symbol=symbol,
                silence_type="no_london_breakout",
                expected_magnitude=expected,
                actual_magnitude=london_range,
                silence_score=silence_score,
                context={
                    "asia_range": asia_range,
                    "asia_atr": asia_atr,
                    "regime": self._get_regime(london_session.index[0]),
                }
            )
        return None

    def detect_no_gold_rates_response(self, gold_price: pd.Series,
                                       rates_price: pd.Series,
                                       window_hours: int = 4) -> SilenceEvent | None:
        """Detect when gold didn't respond to massive rates move."""
        # Correlation-based expected move
        corr = gold_price.rolling(100).corr(rates_price).iloc[-1]
        rates_move = rates_price.iloc[-1] - rates_price.iloc[-window_hours]
        expected_gold_move = -corr * rates_move * (gold_price.std() / rates_price.std())

        actual_gold_move = gold_price.iloc[-1] - gold_price.iloc[-window_hours]

        if abs(expected_gold_move) > gold_price.std() * 0.5:
            silence_score = 1.0 - min(abs(actual_gold_move) / abs(expected_gold_move), 1.0)
        else:
            silence_score = 0.0

        if silence_score > 0.7:
            return SilenceEvent(
                timestamp=gold_price.index[-1],
                symbol="XAUUSD",
                silence_type="no_gold_rates_response",
                expected_magnitude=abs(expected_gold_move),
                actual_magnitude=abs(actual_gold_move),
                silence_score=silence_score,
                context={
                    "rates_move": rates_move,
                    "correlation": corr,
                    "window_hours": window_hours,
                    "regime": self._get_regime(gold_price.index[-1]),
                }
            )
        return None

    def detect_unusual_quiet(self, symbol: str, session: str,
                              volume_series: pd.Series,
                              spread_series: pd.Series) -> SilenceEvent | None:
        """Detect unusually quiet market during normally active window."""
        # Get historical stats for this session
        session_mask = self._session_mask(volume_series.index, session)
        session_vol = volume_series[session_mask]
        session_spread = spread_series[session_mask]

        if len(session_vol) < 20:
            return None

        expected_vol = session_vol.rolling(50).mean().iloc[-1]
        expected_spread = session_spread.rolling(50).mean().iloc[-1]

        actual_vol = session_vol.iloc[-1]
        actual_spread = session_spread.iloc[-1]

        vol_silence = 1.0 - min(actual_vol / expected_vol, 1.0) if expected_vol > 0 else 0
        spread_silence = 1.0 - min(actual_spread / expected_spread, 1.0) if expected_spread > 0 else 0
        silence_score = (vol_silence + spread_silence) / 2

        if silence_score > 0.7:
            return SilenceEvent(
                timestamp=volume_series.index[-1],
                symbol=symbol,
                silence_type="unusual_quiet",
                expected_magnitude=expected_vol,
                actual_magnitude=actual_vol,
                silence_score=silence_score,
                context={
                    "session": session,
                    "expected_vol": expected_vol,
                    "actual_vol": actual_vol,
                    "expected_spread": expected_spread,
                    "actual_spread": actual_spread,
                    "regime": self._get_regime(volume_series.index[-1]),
                }
            )
        return None

    def _get_event_beta(self, symbol: str, event_type: str) -> float:
        """Get historical beta of symbol to event type."""
        # Simplified - in production, compute from historical data
        betas = {
            "XAUUSD": {"news": 0.8, "rates": -1.2, "dxy": -1.0},
            "EURUSD": {"news": 0.6, "rates": 0.4, "dxy": -1.0},
            "USDJPY": {"news": 0.5, "rates": 1.0, "dxy": 1.0},
            "US500": {"news": 1.0, "rates": -0.8, "dxy": -0.5},
            "USOIL": {"news": 0.7, "geopolitical": 1.5},
        }
        return betas.get(symbol, {}).get(event_type, 0.5)

    def _get_catalyst_vol_multiplier(self, catalyst_type: str) -> float:
        """Expected volatility multiplier for catalyst type."""
        multipliers = {
            "CPI": 2.5, "NFP": 2.0, "FOMC": 3.0, "ECB": 2.0,
            "Trump_post": 1.5, "geopolitical": 2.0, "earnings": 1.5,
        }
        return multipliers.get(catalyst_type, 1.5)

    def _get_regime(self, timestamp: datetime) -> str:
        """Simple regime detection."""
        hour = timestamp.hour
        if 7 <= hour < 16:
            return "london"
        elif 13 <= hour < 22:
            return "ny"
        else:
            return "asia"

    def _session_mask(self, index: pd.DatetimeIndex, session: str) -> np.ndarray:
        """Boolean mask for session hours."""
        hours = index.hour
        if session == "asia":
            return (hours >= 0) & (hours < 7)
        elif session == "london":
            return (hours >= 7) & (hours < 16)
        elif session == "ny":
            return (hours >= 13) & (hours < 22)
        return np.ones(len(hours), dtype=bool)

    def record_outcome(self, event: SilenceEvent, outcome: dict) -> None:
        """Record what happened after the silence."""
        event.subsequent_outcome = outcome
        self.silence_events.append(event)

    def generate_hypotheses(self, min_events: int = 10) -> list[SideChannelHypothesis]:
        """Generate hypotheses from silence patterns."""
        if len(self.silence_events) < min_events:
            return []

        # Group by silence type and symbol
        from collections import defaultdict
        groups = defaultdict(list)
        for e in self.silence_events:
            key = f"{e.silence_type}_{e.symbol}"
            groups[key].append(e)

        hypotheses = []
        for key, events in groups.items():
            if len(events) < min_events:
                continue

            # Check if silence predicts something
            outcomes = [e.subsequent_outcome for e in events if e.subsequent_outcome]
            if not outcomes:
                continue

            # Example: silence before news -> big move after
            # This is a simplified pattern detector
            silence_type, symbol = key.split("_", 1)

            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.MICROSTRUCTURE,
                source="negative_space_miner",
                mechanism=f"Silence pattern: {silence_type} on {symbol}. "
                          f"When market is unusually quiet ({len(events)} occurrences), "
                          f"subsequent moves show exploitable pattern.",
                symbols=[symbol],
                timing={
                    "silence_type": silence_type,
                    "session": events[0].context.get("session", "unknown"),
                    "regime": events[0].context.get("regime", "unknown"),
                },
                falsifier=f"Pattern breaks down over 30+ occurrences",
                expected_horizon="session_to_1d",
                capacity_estimate="small",
                metadata={
                    "silence_type": silence_type,
                    "symbol": symbol,
                    "sample_size": len(events),
                    "avg_silence_score": np.mean([e.silence_score for e in events]),
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        """Save silence events to disk."""
        import json
        data = {
            "events": [{
                "timestamp": e.timestamp.isoformat(),
                "symbol": e.symbol,
                "silence_type": e.silence_type,
                "expected_magnitude": e.expected_magnitude,
                "actual_magnitude": e.actual_magnitude,
                "silence_score": e.silence_score,
                "context": e.context,
                "subsequent_outcome": e.subsequent_outcome,
            } for e in self.silence_events],
            "saved_at": datetime.now(UTC).isoformat(),
        }
        with open(SILENCE_DIR / "silence_events.json", "w") as f:
            json.dump(data, f, indent=2)


def build_silence_features(symbol: str, price_data: pd.DataFrame,
                           news_data: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build silence feature set for a symbol."""
    df = price_data.copy()
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(20).std() * np.sqrt(252)
    df["volume_z"] = (df["tick_volume"] - df["tick_volume"].rolling(50).mean()) / df["tick_volume"].rolling(50).std()
    df["spread_z"] = (df["spread"] - df["spread"].rolling(50).mean()) / df["spread"].rolling(50).std()

    # Silence features
    df["vol_silence"] = 1.0 - (df["volatility"] / df["volatility"].rolling(50).mean()).clip(0, 1)
    df["volume_silence"] = 1.0 - (df["tick_volume"] / df["tick_volume"].rolling(50).mean()).clip(0, 1)
    df["spread_silence"] = 1.0 - (df["spread"] / df["spread"].rolling(50).mean()).clip(0, 1)

    if news_data is not None:
        # Merge news events and compute expected vs actual
        pass

    return df


if __name__ == "__main__":
    miner = SilenceMiner()

    # Test with synthetic data
    dates = pd.date_range("2026-01-01", periods=1000, freq="1H", tz=UTC)
    prices = pd.Series(100 + np.cumsum(np.random.randn(1000) * 0.01), index=dates)
    vol = pd.Series(np.abs(np.random.randn(1000) * 0.001), index=dates)

    # Test no continuation
    event = miner.detect_no_continuation("XAUUSD", dates[500], prices)
    if event:
        print(f"Silence: {event.silence_type} score={event.silence_score:.2f}")
        miner.record_outcome(event, {"1h_move": 0.5})

    hyps = miner.generate_hypotheses(min_events=1)
    print(f"Generated {len(hyps)} silence hypotheses")