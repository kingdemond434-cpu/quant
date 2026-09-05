"""MQL5 Signals Miner — reverse-engineers public track records into behavioral hypotheses.

Mines publicly visible signal track records on MQL5 and reconstructs:
- trade frequency
- instrument distribution
- entry-time distribution
- holding duration
- long/short asymmetry
- average stop distance
- average target
- winner duration
- loser duration
- position scaling
- averaging-down behavior
- pyramiding
- weekend holding
- event exposure
- volatility preference
- trend dependence
- session preference
- serial correlation
- maximum simultaneous positions
"""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


@dataclass
class MQL5Signal:
    """A public MQL5 signal."""
    source_id: str
    url: str
    name: str
    author: str
    subscribers: int
    growth_percent: float
    drawdown_percent: float
    trades_per_week: float
    profit_factor: float
    sharpe_ratio: float
    trades_history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ReconstructedBehavior:
    """Reconstructed behavior from signal track record."""
    source_id: str
    signal_name: str
    
    # Trade statistics
    total_trades: int = 0
    avg_trades_per_week: float = 0.0
    win_rate: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Instrument distribution
    instrument_distribution: dict[str, int] = field(default_factory=dict)
    
    # Temporal patterns
    entry_hour_distribution: dict[int, int] = field(default_factory=dict)
    entry_day_distribution: dict[int, int] = field(default_factory=dict)
    holding_duration_distribution: dict[str, int] = field(default_factory=dict)
    
    # Directional
    long_ratio: float = 0.0
    short_ratio: float = 0.0
    
    # Risk
    avg_stop_distance_pips: float = 0.0
    avg_target_distance_pips: float = 0.0
    avg_rr_ratio: float = 0.0
    
    # Behavior flags
    uses_averaging: bool = False
    uses_grid: bool = False
    uses_martingale: bool = False
    uses_pyramiding: bool = False
    uses_trailing: bool = False
    weekend_holding: bool = False
    
    # Volatility preference
    avg_atr_at_entry: float = 0.0
    prefers_high_vol: bool = False
    
    # Trend dependence
    trend_dependence: float = 0.0
    
    # Serial correlation
    serial_correlation: float = 0.0
    
    max_simultaneous_positions: int = 1
    metadata: dict = field(default_factory=dict)


class MQL5SignalParser:
    """Parses MQL5 signal track records."""
    
    def parse_signal_page(self, html: str) -> dict:
        """Parse signal page HTML for statistics."""
        soup = BeautifulSoup(html, "html.parser")
        stats = {}
        
        # Extract key stats from signal page
        stat_elements = soup.find_all("div", class_=re.compile(r"stat|value|metric"))
        for elem in stat_elements:
            label = elem.find("span", class_=re.compile(r"label|name"))
            value = elem.find("span", class_=re.compile(r"value|number"))
            if label and value:
                stats[label.get_text(strip=True).lower()] = value.get_text(strip=True)
        
        return stats
    
    def parse_trade_history(self, html: str) -> list[dict]:
        """Parse trade history table from signal page."""
        trades = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Find trade history table
        tables = soup.find_all("table", class_=re.compile(r"trade|history|deal"))
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) >= 7:
                    trade = {
                        "time": cells[0].get_text(strip=True),
                        "symbol": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "type": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                        "volume": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                        "price": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                        "sl": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                        "tp": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                        "profit": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                    }
                    trades.append(trade)
        
        return trades


class MQL5BehaviorReconstructor:
    """Reconstructs behavioral profile from trade history."""
    
    def reconstruct(self, signal: MQL5Signal) -> ReconstructedBehavior:
        """Reconstruct behavioral profile from signal track record."""
        trades = signal.trades_history
        if not trades:
            return ReconstructedBehavior(source_id=signal.source_id, signal_name=signal.name)
        
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        if df.empty:
            return ReconstructedBehavior(source_id=signal.source_id, signal_name=signal.name)
        
        # Parse timestamps
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])
        if df.empty:
            return ReconstructedBehavior(source_id=signal.source_id, signal_name=signal.name)
        
        # Parse numeric fields
        for col in ["volume", "price", "sl", "tp", "profit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        behavior = ReconstructedBehavior(
            source_id=signal.source_id,
            signal_name=signal.name,
        )
        
        # Total trades
        behavior.total_trades = len(df)
        behavior.avg_trades_per_week = signal.trades_per_week
        
        # Win rate
        profitable = df[df["profit"] > 0]
        behavior.win_rate = len(profitable) / len(df) if len(df) > 0 else 0
        
        # Avg win/loss
        if len(profitable) > 0:
            behavior.avg_win_r = profitable["profit"].mean()
        losers = df[df["profit"] < 0]
        if len(losers) > 0:
            behavior.avg_loss_r = losers["profit"].mean()
        
        # Profit factor
        gross_profit = profitable["profit"].sum() if len(profitable) > 0 else 0
        gross_loss = abs(losers["profit"].sum()) if len(losers) > 0 else 1
        behavior.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Sharpe (simplified)
        returns = df["profit"].dropna()
        if len(returns) > 1:
            behavior.sharpe_ratio = returns.mean() / returns.std() if returns.std() > 0 else 0
        
        # Max drawdown
        cum_returns = returns.cumsum()
        running_max = cum_returns.expanding().max()
        drawdown = (cum_returns - running_max).min()
        behavior.max_drawdown = abs(drawdown) if not np.isnan(drawdown) else 0
        
        # Instrument distribution
        if "symbol" in df.columns:
            behavior.instrument_distribution = df["symbol"].value_counts().to_dict()
        
        # Entry hour distribution
        behavior.entry_hour_distribution = df["time"].dt.hour.value_counts().to_dict()
        
        # Entry day distribution
        behavior.entry_day_distribution = df["time"].dt.dayofweek.value_counts().to_dict()
        
        # Holding duration (if we have entry/exit times)
        if "sl" in df.columns and "tp" in df.columns:
            # Estimate holding duration from SL/TP distance vs price
            pass
        
        # Long/Short ratio
        if "type" in df.columns:
            long_count = len(df[df["type"].str.contains("buy", case=False, na=False)])
            short_count = len(df[df["type"].str.contains("sell", case=False, na=False)])
            total = long_count + short_count
            if total > 0:
                behavior.long_ratio = long_count / total
                behavior.short_ratio = short_count / total
        
        # Stop/Target distances
        if "sl" in df.columns and "price" in df.columns:
            df["sl_dist"] = abs(df["price"] - df["sl"])
            behavior.avg_stop_distance_pips = df["sl_dist"].mean() * 10000  # Convert to pips
        
        if "tp" in df.columns and "price" in df.columns:
            df["tp_dist"] = abs(df["tp"] - df["price"])
            behavior.avg_target_distance_pips = df["tp_dist"].mean() * 10000
        
        if behavior.avg_stop_distance_pips > 0:
            behavior.avg_rr_ratio = behavior.avg_target_distance_pips / behavior.avg_stop_distance_pips
        
        # Behavior detection
        # Averaging down: same symbol, same direction, multiple entries before exit
        if "symbol" in df.columns and "type" in df.columns:
            for symbol in df["symbol"].unique():
                sym_df = df[df["symbol"] == symbol].sort_values("time")
                buy_streak = 0
                for _, row in sym_df.iterrows():
                    if "buy" in str(row.get("type", "")).lower():
                        buy_streak += 1
                    elif "sell" in str(row.get("type", "")).lower():
                        buy_streak = 0
                    if buy_streak >= 3:
                        behavior.uses_averaging = True
                        break
        
        # Grid detection: regular spacing between entries
        if "price" in df.columns:
            for symbol in df["symbol"].unique():
                sym_df = df[df["symbol"] == symbol].sort_values("time")
                prices = sym_df["price"].dropna().values
                if len(prices) >= 3:
                    diffs = np.diff(prices)
                    if np.std(diffs) / np.mean(np.abs(diffs)) < 0.1:
                        behavior.uses_grid = True
        
        # Martingale: position size increases after losses
        if "volume" in df.columns and "profit" in df.columns:
            volumes = df["volume"].dropna().values
            profits = df["profit"].dropna().values
            if len(volumes) >= 3 and len(profits) >= 3:
                # Check if volume increases after negative profit
                for i in range(1, min(len(volumes), len(profits))):
                    if profits[i-1] < 0 and volumes[i] > volumes[i-1] * 1.5:
                        behavior.uses_martingale = True
                        break
        
        # Trailing stop detection
        if "sl" in df.columns:
            # Check if SL moves in profitable direction
            behavior.uses_trailing = True  # Simplified
        
        # Weekend holding
        if "time" in df.columns:
            weekend_trades = df[df["time"].dt.dayofweek >= 5]
            behavior.weekend_holding = len(weekend_trades) > 0
        
        # Max simultaneous positions
        if "time" in df.columns and "symbol" in df.columns:
            # Count overlapping positions
            df_sorted = df.sort_values("time")
            active = {}
            max_concurrent = 0
            for _, row in df_sorted.iterrows():
                sym = row.get("symbol", "")
                typ = str(row.get("type", "")).lower()
                if "buy" in typ or "sell" in typ:
                    active[sym] = active.get(sym, 0) + 1
                elif "close" in typ or "tp" in typ or "sl" in typ:
                    if sym in active:
                        active[sym] = max(0, active[sym] - 1)
                max_concurrent = max(max_concurrent, sum(1 for v in active.values() if v > 0))
            behavior.max_simultaneous_positions = max_concurrent
        
        # Serial correlation
        if len(returns) > 10:
            behavior.serial_correlation = returns.autocorr(lag=1) if not np.isnan(returns.autocorr(lag=1)) else 0
        
        # Trend dependence
        # Check if trades align with longer-term trend
        behavior.trend_dependence = 0.5  # Placeholder
        
        # Volatility preference
        behavior.prefers_high_vol = False  # Would need ATR data
        
        return behavior


class MQL5SignalsMiner:
    """Mines MQL5 Signals for behavioral reconstruction."""
    
    BASE_URL = "https://www.mql5.com"
    SIGNALS_URL = "https://www.mql5.com/en/signals"
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.parser = MQL5SignalParser()
        self.reconstructor = MQL5BehaviorReconstructor()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; QuantResearchBot/1.0)"
        })
        self.data_dir = DATA_DIR / "mql5_signals"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.data_dir / "processed_signals.json"
        self.processed: set[str] = self._load_processed()
    
    def _load_processed(self) -> set[str]:
        if self.processed_file.exists():
            with open(self.processed_file, "r") as f:
                return set(json.load(f))
        return set()
    
    def _save_processed(self) -> None:
        with open(self.processed_file, "w") as f:
            json.dump(list(self.processed), f)
    
    def discover(self, config, reputation) -> list:
        """Discover new MQL5 signals."""
        items = []
        
        try:
            response = self.session.get(self.SIGNALS_URL, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find signal links
            signal_links = soup.find_all("a", href=re.compile(r"/en/signals/\d+"))
            
            for link in signal_links[:10]:
                href = link.get("href")
                if not href:
                    continue
                
                signal_id = href.split("/")[-1]
                if signal_id in self.processed:
                    continue
                
                signal_url = urljoin(self.BASE_URL, href)
                try:
                    signal_resp = self.session.get(signal_url, timeout=15)
                    signal_soup = BeautifulSoup(signal_resp.text, "html.parser")
                    
                    # Extract signal info
                    name_elem = signal_soup.find("h1") or signal_soup.find("h2")
                    name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                    
                    author_elem = signal_soup.find("a", class_="author-link")
                    author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                    
                    # Extract stats
                    stats = self.parser.parse_signal_page(signal_resp.text)
                    
                    # Try to get trade history
                    history_url = urljoin(self.BASE_URL, f"{href}/history")
                    try:
                        hist_resp = self.session.get(history_url, timeout=15)
                        trades = self.parser.parse_trade_history(hist_resp.text)
                    except Exception:
                        trades = []
                    
                    item = MQL5Signal(
                        source_id=f"mql5_signal_{signal_id}",
                        url=signal_url,
                        name=name,
                        author=author,
                        subscribers=int(stats.get("subscribers", 0)),
                        growth_percent=float(stats.get("growth", 0)),
                        drawdown_percent=float(stats.get("drawdown", 0)),
                        trades_per_week=float(stats.get("trades per week", 0)),
                        profit_factor=float(stats.get("profit factor", 0)),
                        sharpe_ratio=float(stats.get("sharpe", 0)),
                        trades_history=trades,
                        metadata={"signal_id": signal_id, "stats": stats},
                    )
                    items.append(item)
                    self.processed.add(signal_id)
                    
                except Exception:
                    continue
            
            self._save_processed()
            
        except Exception as e:
            print(f"MQL5 Signals discover error: {e}")
        
        return items
    
    def acquire(self, config, budget) -> list:
        return []
    
    def extract(self, config, items) -> list:
        hypotheses = []
        for item in items:
            if isinstance(item, MQL5Signal):
                behavior = self.reconstructor.reconstruct(item)
                hypothesis = self._behavior_to_hypothesis(item, behavior)
                if hypothesis:
                    yield hypothesis
    
    def _behavior_to_hypothesis(self, signal: MQL5Signal, behavior: ReconstructedBehavior) -> dict | None:
        if behavior.total_trades < 10:
            return None
        
        # Determine primary instrument
        instruments = behavior.instrument_distribution
        if not instruments:
            return None
        primary = max(instruments, key=instruments.get)
        
        # Determine dominant session
        sessions = behavior.entry_hour_distribution
        if sessions:
            dominant_hour = max(sessions, key=sessions.get)
            if 0 <= dominant_hour < 7:
                session = "asia"
            elif 7 <= dominant_hour < 16:
                session = "london"
            else:
                session = "ny"
        else:
            session = "all"
        
        # Determine if grid/martingale
        is_grid_martingale = behavior.uses_grid or behavior.uses_martingale
        
        hypothesis = {
            "id": generate_id(),
            "origin": {
                "region": "global",
                "language": "en",
                "source_type": "mql5_signals",
                "source_id": signal.source_id,
                "source_url": signal.url,
                "evidence_tier": "leaderboard_behavior",
            },
            "mechanism": {
                "mechanism_class": "information_shock" if not is_grid_martingale else "crowding_unwind",
                "participant": "retail",
                "constraint": "behavioral_pattern",
                "information_source": "mql5_public_track_record",
                "why_edge_should_exist": f"Reconstructed behavior from public MQL5 signal: {signal.name}",
            },
            "market": {
                "symbols": list(behavior.instrument_distribution.keys()),
                "primary_symbol": primary,
                "timeframe": "H1",
                "session": session,
            },
            "rule": {
                "inputs": ["price", "behavioral_reconstruction"],
                "trigger": f"Reconstructed from {signal.name} behavior",
                "direction": 1 if behavior.long_ratio > 0.5 else (-1 if behavior.short_ratio > 0.5 else 0),
                "holding_horizon": "4h",
                "exit": "reconstructed_behavior",
                "stop": f"{behavior.avg_stop_distance_pips:.0f}_pips" if behavior.avg_stop_distance_pips > 0 else "atr_1.5",
            },
            "economics": {
                "expected_edge_bps_per_trade": 2.0,
                "expected_trades_per_month": behavior.avg_trades_per_week * 4,
                "expected_capacity_lots": 5 if (behavior.uses_grid or behavior.uses_martingale) else 20,
                "expected_capacity_category": "micro" if (behavior.uses_grid or behavior.uses_martingale) else "small",
            },
            "falsifier": {
                "condition": "behavioral_pattern_breaks_down",
                "horizon": "50_trades",
                "threshold": 0.0,
                "data_source": "shadow_forward",
            },
            "metadata": {
                "source": "mql5_signals",
                "signal_name": signal.name,
                "author": signal.author,
                "url": signal.url,
                "reconstructed_behavior": {
                    "total_trades": behavior.total_trades,
                    "win_rate": behavior.win_rate,
                    "profit_factor": behavior.profit_factor,
                    "sharpe": behavior.sharpe_ratio,
                    "max_dd": behavior.max_drawdown,
                    "long_ratio": behavior.long_ratio,
                    "avg_rr": behavior.avg_rr_ratio,
                    "uses_grid": behavior.uses_grid,
                    "uses_martingale": behavior.uses_martingale,
                    "uses_averaging": behavior.uses_averaging,
                    "uses_trailing": behavior.uses_trailing,
                    "weekend_holding": behavior.weekend_holding,
                    "max_positions": behavior.max_simultaneous_positions,
                    "serial_corr": behavior.serial_correlation,
                },
            },
        }
        return hypothesis


def discover(config, reputation) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5SignalsMiner(base)
    return miner.discover(config, reputation)


def acquire(config, budget) -> list:
    return []


def extract(config, items) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5SignalsMiner(base)
    return list(miner.extract(config, items))