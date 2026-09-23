"""MQL5 CodeBase Miner — parses public .mq5 source code for exact rules.

Mines MQL5 CodeBase (public source) → parses exact rules → canonical hypotheses.
"""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


@dataclass
class MQL5CodeItem:
    """A parsed MQL5 code item."""
    source_id: str                          # e.g., "mql5_codebase_12345"
    url: str
    title: str
    author: str
    code: str                               # raw .mq5 source
    language: str = "mq5"
    category: str = "CodeBase"              # CodeBase, Articles, Signals, Forum
    extracted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedMQL5Strategy:
    """Parsed strategy from MQL5 code."""
    source_id: str
    entry_rules: list[str] = field(default_factory=list)
    exit_rules: list[str] = field(default_factory=list)
    stop_loss: str | None = None
    take_profit: str | None = None
    trailing_stop: str | None = None
    position_sizing: str | None = None
    session_filters: list[str] = field(default_factory=list)
    timeframe: str | None = None
    symbols: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    grid_martingale: bool = False
    averaging_down: bool = False
    hedging: bool = False
    direction: Literal["long", "short", "both"] = "both"
    raw_code: str = ""


class MQL5CodeParser:
    """Parses MQL5 (.mq5) source code into structured strategy rules."""
    
    def __init__(self):
        # MQL5 patterns for extraction
        self.patterns = {
            "input_params": re.compile(r'input\s+\w+\s+\w+\s*=', re.IGNORECASE),
            "order_send": re.compile(r'OrderSend\s*\([^)]*\)', re.IGNORECASE),
            "order_open": re.compile(r'(?:OrderSend|PositionOpen)\s*\([^)]*\)', re.IGNORECASE),
            "sl_tp": re.compile(r'(?:StopLoss|TakeProfit)\s*[=:]\s*[^;,)]+', re.IGNORECASE),
            "trailing": re.compile(r'TrailingStop|Trailing\s*[=:]\s*[^;,)]+', re.IGNORECASE),
            "entry_condition": re.compile(r'(?:if|while)\s*\([^)]*(?:Buy|Sell|OrderSend)[^)]*\)', re.IGNORECASE),
            "exit_condition": re.compile(r'(?:if|while)\s*\([^)]*(?:Close|Delete|Modify)[^)]*\)', re.IGNORECASE),
            "indicators": re.compile(r'i(?:MA|RSI|MACD|Stochastic|ATR|Bands|CCI|ADX|SAR|Ichimoku|Alligator|Fractals|DeMarker|Force|Momentum|WPR|CCI|OsMA|BWMFI|AD|OBV|Volumes|MFI|TEMA|TRIX|Vigor|ROC|BearsPower|BullsPower|StdDev|Variance)\s*\(', re.IGNORECASE),
            "time_check": re.compile(r'TimeHour|TimeMinute|TimeSeconds|Hour|Minute|Second|TimeCurrent|iTime', re.IGNORECASE),
            "symbol_check": re.compile(r'Symbol\(\)|_Symbol', re.IGNORECASE),
            "grid_logic": re.compile(r'(?:for|while)\s*\([^)]*OrdersTotal\s*\([^)]*\)', re.IGNORECASE),
            "martingale": re.compile(r'Lot\s*\*=\s*2|Lot\s*\+\s*=|Double\s+Lot', re.IGNORECASE),
            "averaging": re.compile(r'(?:Buy|Sell)\s*[+-]?\s*\d+\s*(?:pips|points|pip)', re.IGNORECASE),
            "position_sizing": re.compile(r'(?:Lot|Volume|Lots)\s*[=:]\s*[^;,)]+', re.IGNORECASE),
            "risk_percent": re.compile(r'(?:Risk|risk)\s*[=:]\s*[^;,)]+', re.IGNORECASE),
        }
    
    def parse(self, code: str, source_id: str) -> ParsedMQL5Strategy:
        """Parse MQL5 code into structured strategy."""
        strategy = ParsedMQL5Strategy(source_id=source_id, raw_code=code)
        
        # Extract entry rules
        strategy.entry_rules = self._extract_entry_conditions(code)
        
        # Extract exit rules
        strategy.exit_rules = self._extract_exit_conditions(code)
        
        # Extract SL/TP
        strategy.stop_loss = self._extract_sl_tp(code, "stop")
        strategy.take_profit = self._extract_sl_tp(code, "profit")
        
        # Extract trailing stop
        strategy.trailing_stop = self._extract_trailing(code)
        
        # Extract position sizing
        strategy.position_sizing = self._extract_position_sizing(code)
        
        # Check for grid/martingale
        strategy.grid_martingale = self._detect_grid_martingale(code)
        strategy.averaging_down = self._detect_averaging(code)
        strategy.hedging = self._detect_hedging(code)
        
        # Extract session filters
        strategy.session_filters = self._extract_session_filters(code)
        
        # Extract timeframe
        strategy.timeframe = self._extract_timeframe(code)
        
        # Extract symbols
        strategy.symbols = self._extract_symbols(code)
        
        # Extract indicators
        strategy.indicators = self._extract_indicators(code)
        
        return strategy
    
    def _extract_entry_conditions(self, code: str) -> list[str]:
        """Extract entry/buy/sell conditions."""
        rules = []
        
        # Look for OrderSend calls with conditions
        orders = re.findall(r'OrderSend\s*\([^)]+\)', code, re.IGNORECASE)
        for order in orders:
            # Extract condition before OrderSend
            before = code[:code.find(order)]
            if_match = re.search(r'if\s*\(([^)]+)\)\s*{[^}]*' + re.escape(order), before[::-1])  # Reverse search
            if if_match:
                condition = if_match.group(1)[::-1].strip()
                rules.append(f"Entry: {condition}")
        
        # Direct pattern search
        entry_patterns = [
            r'if\s*\(([^)]*(?:Cross|Break|Breakout|Touch|Reach|Above|Below|>|<|==|!=)[^)]*)\)\s*{[^}]*OrderSend',
            r'if\s*\(([^)]*(?:RSI|MACD|MA|EMA|SMA|Bollinger|Donchian|Keltner|Ichimoku)[^)]*)\)\s*{[^}]*OrderSend',
        ]
        
        for pattern in entry_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE | re.DOTALL)
            for m in matches:
                rules.append(f"Entry condition: {m.strip()[:200]}")
        
        return rules[:10]  # Limit
    
    def _extract_exit_conditions(self, code: str) -> list[str]:
        """Extract exit/close conditions."""
        rules = []
        
        # Look for OrderClose, PositionClose, OrderDelete
        close_patterns = [
            r'OrderClose\s*\([^)]+\)',
            r'PositionClose\s*\([^)]+\)',
            r'OrderDelete\s*\([^)]+\)',
        ]
        
        for pattern in close_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            for m in matches:
                rules.append(f"Exit call: {m[:200]}")
        
        return rules[:10]
    
    def _extract_sl_tp(self, code: str, which: str) -> str | None:
        """Extract stop loss or take profit."""
        if which == "stop":
            patterns = [r'StopLoss\s*[=:]\s*([^;,)]+)', r'SL\s*[=:]\s*([^;,)]+)']
        else:
            patterns = [r'TakeProfit\s*[=:]\s*([^;,)]+)', r'TP\s*[=:]\s*([^;,)]+)']
        
        for pattern in patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_trailing(self, code: str) -> str | None:
        match = re.search(r'TrailingStop\s*[=:]\s*([^;,)]+)', code, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Look for custom trailing logic
        trail_matches = re.findall(r'(?:if|while)\s*\([^)]*(?:Trail|trail)[^)]*\)', code, re.IGNORECASE)
        if trail_matches:
            return trail_matches[0][:200]
        return None
    
    def _extract_position_sizing(self, code: str) -> str | None:
        patterns = [
            r'(?:Lot|Volume|Lots)\s*[=:]\s*([^;,)]+)',
            r'(?:Risk|risk)\s*[=:]\s*[^;,)]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _detect_grid_martingale(self, code: str) -> bool:
        """Detect grid/martingale patterns."""
        grid_indicators = [
            r'for\s*\([^)]*OrdersTotal\s*\(',
            r'while\s*\([^)]*OrdersTotal\s*\(',
            r'Lot\s*\*=\s*2',
            r'Lot\s*\+\s*=',
            r'Double\s+Lot',
            r'Lot\s*=\s*Lot\s*\*',
        ]
        for pattern in grid_indicators:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def _detect_averaging(self, code: str) -> bool:
        patterns = [
            r'(?:Buy|Sell)\s*[+-]\s*\d+\s*(?:pips|points)',
            r'Average\s*Price|Average\s*Entry',
            r'Grid\s*Step',
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def _detect_hedging(self, code: str) -> bool:
        patterns = [
            r'Hedge\s*[=:]\s*true',
            r'Hedging\s*[=:]\s*true',
            r'Buy\s*[^;]*Sell|Sell\s*[^;]*Buy',
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def _extract_session_filters(self, code: str) -> list[str]:
        sessions = []
        patterns = [
            (r'Hour\s*[=!<>]=?\s*(\d+)', "hour"),
            (r'TimeHour\s*\(\s*\)\s*[=!<>]+\s*(\d+)', "hour"),
            (r'TimeCurrent\s*\(\s*\)\s*[=!<>]+\s*(\d+)', "time"),
            (r'DayOfWeek\s*\(\s*\)\s*[=!<>]+\s*(\d+)', "day"),
        ]
        for pattern, typ in patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            for m in matches:
                sessions.append(f"{typ}_filter: {m}")
        return sessions
    
    def _extract_timeframe(self, code: str) -> str | None:
        match = re.search(r'PERIOD_[A-Z]+|_Period\s*[=:]\s*PERIOD_\w+', code, re.IGNORECASE)
        if match:
            return match.group(0)
        return None
    
    def _extract_symbols(self, code: str) -> list[str]:
        symbols = set()
        # Symbol() or _Symbol
        matches = re.findall(r'Symbol\s*\(\s*\)|_Symbol', code, re.IGNORECASE)
        if matches:
            symbols.add("current")
        
        # Explicit symbol strings
        sym_matches = re.findall(r'["\']([A-Z]{6,7})["\']', code)
        for m in sym_matches:
            if len(m) >= 6 and m.isupper():
                symbols.add(m)
        
        return list(symbols)[:10]
    
    def _extract_indicators(self, code: str) -> list[str]:
        indicators = set()
        indicator_names = [
            "MA", "EMA", "SMA", "LWMA", "SMMA",
            "RSI", "MACD", "MACDHistogram", "MACDSignal",
            "Stochastic", "StochSlow", "StochFast",
            "ATR", "Bands", "Bollinger", "Keltner", "Donchian",
            "CCI", "ADX", "SAR", "Ichimoku", "Alligator",
            "Fractals", "DeMarker", "Force", "Momentum",
            "WPR", "OsMA", "AD", "OBV", "Volumes", "MFI",
            "TEMA", "TRIX", "Vigor", "ROC", "BearsPower", "BullsPower",
            "StdDev", "Variance", "Envelopes", "ParabolicSAR"
        ]
        for ind in indicator_names:
            if re.search(rf'i{ind}\s*\(', code, re.IGNORECASE):
                indicators.add(ind)
        return list(indicators)


class MQL5CodeBaseMiner:
    """Mines MQL5 CodeBase for public .mq5 source code."""
    
    BASE_URL = "https://www.mql5.com"
    CODEBASE_URL = "https://www.mql5.com/en/code"
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.parser = MQL5CodeParser()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; QuantResearchBot/1.0)"
        })
        self.data_dir = DATA_DIR / "mql5_codebase"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.data_dir / "processed_codes.json"
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
        """Discover new MQL5 CodeBase items."""
        items = []
        
        try:
            # Fetch CodeBase listing
            response = self.session.get(self.CODEBASE_URL, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find code listings
            code_links = soup.find_all("a", href=re.compile(r"/en/code/\d+"))
            
            for link in code_links[:20]:  # Limit per cycle
                href = link.get("href")
                if not href:
                    continue
                
                code_id = href.split("/")[-1]
                if code_id in self.processed:
                    continue
                
                # Fetch individual code page
                code_url = urljoin(self.BASE_URL, href)
                try:
                    code_resp = self.session.get(code_url, timeout=15)
                    code_soup = BeautifulSoup(code_resp.text, "html.parser")
                    
                    # Extract title
                    title_elem = code_soup.find("h1", class_="article-title") or code_soup.find("h1")
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract author
                    author_elem = code_soup.find("a", class_="author-link") or code_soup.find("span", class_="author")
                    author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                    
                    # Extract code
                    code_elem = code_soup.find("pre", class_="code") or code_soup.find("code") or code_soup.find("pre")
                    code = code_elem.get_text() if code_elem else ""
                    
                    if len(code) < 100:  # Too short
                        continue
                    
                    item = MQL5CodeItem(
                        source_id=f"mql5_codebase_{code_id}",
                        url=code_url,
                        title=title,
                        author=author,
                        code=code,
                        metadata={"code_id": code_id},
                    )
                    items.append(item)
                    self.processed.add(code_id)
                    
                except Exception:
                    continue
            
            self._save_processed()
            
        except Exception as e:
            print(f"MQL5 CodeBase discover error: {e}")
        
        return items
    
    def acquire(self, config, budget) -> list:
        """Acquire full code content (already done in discover for CodeBase)."""
        return []
    
    def extract(self, config, items) -> list:
        """Extract structured strategies from code."""
        hypotheses = []
        
        for item in items:
            if isinstance(item, MQL5CodeItem):
                # Parse the code
                strategy = self.parser.parse(item.code, item.source_id)
                
                # Create hypothesis from parsed strategy
                hypothesis = self._strategy_to_hypothesis(item, strategy)
                if hypothesis:
                    yield hypothesis
    
    def _strategy_to_hypothesis(self, item, strategy) -> dict | None:
        """Convert parsed strategy to hypothesis dict."""
        if not strategy.entry_rules:
            return None
        
        # Determine primary symbol
        symbols = strategy.symbols or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
        primary = symbols[0]
        
        # Build hypothesis
        hypothesis = {
            "id": generate_id(),
            "origin": {
                "region": "global",
                "language": "en",
                "source_type": "mql5_codebase",
                "source_id": item.source_id,
                "source_url": item.url,
                "evidence_tier": "code_derived",
            },
            "mechanism": {
                "mechanism_class": "information_shock",
                "participant": "retail",
                "constraint": "technical_pattern",
                "information_source": "mql5_public_code",
                "why_edge_should_exist": f"Public MQL5 strategy with explicit rules: {item.title}",
            },
            "market": {
                "symbols": strategy.symbols or [primary],
                "primary_symbol": primary,
                "timeframe": strategy.timeframe or "H1",
                "session": "all" if not strategy.session_filters else ",".join(strategy.session_filters),
            },
            "rule": {
                "inputs": ["price", "indicators"] + strategy.indicators,
                "trigger": "; ".join(strategy.entry_rules[:3]),
                "direction": 1 if "long" in strategy.direction.lower() else (-1 if "short" in strategy.direction.lower() else 0),
                "holding_horizon": "4h",
                "exit": "; ".join(strategy.exit_rules[:3]) or "opposite_signal_or_tp_sl",
                "stop": strategy.stop_loss or "atr_1.5",
                "trail": strategy.trailing_stop,
            },
            "economics": {
                "expected_edge_bps_per_trade": 5.0,
                "expected_trades_per_month": 20,
                "expected_capacity_lots": 10,
                "expected_capacity_category": "small",
            },
            "falsifier": {
                "condition": "exp_r < 0.05R over 100 forward trades",
                "horizon": "100_trades",
                "threshold": 0.05,
                "data_source": "shadow_forward",
            },
            "metadata": {
                "source": "mql5_codebase",
                "title": item.title,
                "author": item.author,
                "url": item.url,
                "entry_rules": strategy.entry_rules,
                "exit_rules": strategy.exit_rules,
                "indicators": strategy.indicators,
                "timeframe": strategy.timeframe,
                "grid_martingale": strategy.grid_martingale,
                "averaging_down": strategy.averaging_down,
            },
        }
        return hypothesis


def discover(config, reputation) -> list:
    """Entry point for CodeBase discovery."""
    base = Path("/home/quant/quant-platform")
    miner = MQL5CodeBaseMiner(base)
    return miner.discover(config, reputation)


def acquire(config, budget) -> list:
    return []


def extract(config, items) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5CodeBaseMiner(base)
    return list(miner.extract(config, items))


if __name__ == "__main__":
    # Test parser
    test_code = """
    input double StopLoss = 500;
    input double TakeProfit = 1000;
    input double Lot = 0.1;
    
    void OnTick() {
        double ma_fast = iMA(_Symbol, PERIOD_H1, 10, 0, MODE_EMA, PRICE_CLOSE, 0);
        double ma_slow = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE, 0);
        
        if (ma_fast > ma_slow && OrdersTotal() == 0) {
            OrderSend(Symbol(), OP_BUY, 0.1, Ask, 3, Bid - 500*Point, Ask + 1000*Point, "EMA Cross", 123, 0, clrGreen);
        }
        if (ma_fast < ma_slow && OrdersTotal() == 0) {
            OrderSend(Symbol(), OP_SELL, 0.1, Bid, 3, Ask + 500*Point, Bid - 1000*Point, "EMA Cross", 123, 0, clrRed);
        }
    }
    """
    
    parser = MQL5CodeParser()
    strategy = parser.parse(test_code, "test_123")
    print(f"Entry rules: {strategy.entry_rules}")
    print(f"Exit rules: {strategy.exit_rules}")
    print(f"Stop loss: {strategy.stop_loss}")
    print(f"Take profit: {strategy.take_profit}")
    print(f"Indicators: {strategy.indicators}")
    print(f"Grid: {strategy.grid_martingale}")