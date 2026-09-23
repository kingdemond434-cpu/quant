"""MQL5 Articles Miner — mines strategy ideas, execution tricks, indicators from articles."""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


@dataclass
class MQL5Article:
    """An MQL5 article."""
    source_id: str
    url: str
    title: str
    author: str
    published_at: str
    content: str
    category: str = "Articles"
    extracted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict = field(default_factory=dict)


class MQL5ArticleParser:
    """Parses MQL5 articles for strategy content."""
    
    # Keywords that indicate strategy content
    STRATEGY_KEYWORDS = [
        "strategy", "system", "indicator", "signal", "entry", "exit",
        "stop loss", "take profit", "trailing", "position", "risk",
        "backtest", "optimization", "walk forward", "forward test",
        "session", "timeframe", "volatility", "trend", "reversal",
        "breakout", "pullback", "retracement", "support", "resistance",
        "moving average", "ema", "sma", "rsi", "macd", "stochastic",
        "bollinger", "atr", "fibonacci", "pivot", "pattern",
    ]
    
    # Keywords that indicate execution/implementation details
    EXECUTION_KEYWORDS = [
        "order send", "ordersend", "order close", "orderclose",
        "position open", "position close", "stop loss", "take profit",
        "trailing stop", "trailing", "slippage", "spread", "commission",
        "lot size", "position sizing", "risk management", "money management",
        "margin", "leverage", "freeze level", "stop level",
    ]
    
    def parse(self, article: MQL5Article) -> dict | None:
        """Parse article for strategy content."""
        content_lower = article.content.lower()
        
        # Check if article has strategy content
        strategy_score = sum(1 for kw in self.STRATEGY_KEYWORDS if kw in content_lower)
        execution_score = sum(1 for kw in self.EXECUTION_KEYWORDS if kw in content_lower)
        
        if strategy_score < 3:
            return None
        
        # Extract structured info
        extracted = {
            "source_id": article.source_id,
            "url": article.url,
            "title": article.title,
            "author": article.author,
            "strategy_keywords_found": [kw for kw in self.STRATEGY_KEYWORDS if kw in article.content.lower()],
            "execution_keywords_found": [kw for kw in self.EXECUTION_KEYWORDS if kw in article.content.lower()],
            "code_snippets": self._extract_code_snippets(article.content),
            "rules_text": self._extract_rules_text(article.content),
            "indicators_mentioned": self._extract_indicators(article.content),
            "timeframes_mentioned": self._extract_timeframes(article.content),
            "sessions_mentioned": self._extract_sessions(article.content),
            "symbols_mentioned": self._extract_symbols(article.content),
            "risk_management": self._extract_risk_management(article.content),
        }
        
        return extracted
    
    def _extract_code_snippets(self, content: str) -> list[str]:
        """Extract MQL5 code snippets from article."""
        snippets = []
        # Look for code blocks
        code_blocks = re.findall(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL | re.IGNORECASE)
        code_blocks += re.findall(r'<code[^>]*>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
        for block in code_blocks:
            clean = re.sub(r'<[^>]+>', '', block).strip()
            if len(clean) > 50:
                snippets.append(clean[:2000])
        return snippets[:5]
    
    def _extract_rules_text(self, content: str) -> list[str]:
        """Extract natural language trading rules."""
        rules = []
        # Look for rule-like sentences
        rule_patterns = [
            r'(?:buy|sell|enter|exit|close|stop|profit|target)[^.]*?(?:when|if|above|below|cross|touch|break)[^.]*\.',
            r'(?:entry|exit|stop|profit|sl|tp|take profit|stop loss)[^.]*?(?:at|when|if|above|below|cross)[^.]*\.',
        ]
        for pattern in self._compile_patterns(self.STRATEGY_KEYWORDS):
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                rules.append(m.strip()[:300])
        return rules[:10]
    
    def _compile_patterns(self, keywords: list[str]) -> list:
        return [re.compile(rf'\b{kw}\b[^.]*?\b(?:when|if|above|below|cross|touch|break|above|below)\b[^.]*\.', re.IGNORECASE) for kw in keywords]
    
    def _extract_indicators(self, content: str) -> list[str]:
        indicators = set()
        indicator_names = [
            "MA", "EMA", "SMA", "LWMA", "SMMA",
            "RSI", "MACD", "Stochastic", "ATR", "Bands", "Bollinger",
            "Keltner", "Donchian", "CCI", "ADX", "SAR", "Ichimoku", "Alligator",
            "Fractals", "DeMarker", "Force", "Momentum", "WPR", "OsMA",
            "AD", "OBV", "Volumes", "MFI", "TEMA", "TRIX", "Vigor",
            "ROC", "BearsPower", "BullsPower", "StdDev", "Variance",
            "Envelopes", "ParabolicSAR", "Supertrend", "Super Trend",
        ]
        for ind in indicator_names:
            if re.search(rf'\b{re.escape(ind)}\b', content, re.IGNORECASE):
                indicators.add(ind)
        return list(indicators)
    
    def _extract_timeframes(self, content: str) -> list[str]:
        tfs = set()
        tf_patterns = [
            r'\b(M1|M5|M15|M30|H1|H4|D1|W1|MN)\b',
            r'\b(1m|5m|15m|30m|1h|4h|1d|1w|1M)\b',
            r'(?:timeframe|period)\s*(?:=|:|is)?\s*(M1|M5|M15|M30|H1|H4|D1|W1|MN)',
        ]
        for pattern in tf_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    tfs.add(m[0])
                else:
                    tfs.add(m)
        return list(tfs)
    
    def _extract_sessions(self, content: str) -> list[str]:
        sessions = set()
        session_names = [
            "asian", "london", "new york", "ny", "tokyo", "sydney",
            "frankfurt", "european", "american", "pacific",
            "open", "close", "overlap", "pre-market", "after-hours",
        ]
        for name in session_names:
            if re.search(rf'\b{re.escape(name)}\b', content, re.IGNORECASE):
                sessions.add(name)
        return list(sessions)
    
    def _extract_symbols(self, content: str) -> list[str]:
        symbols = set()
        # Common forex pairs
        pairs = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
            "EURJPY", "EURGBP", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
            "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
            "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
            "CADJPY", "CHFJPY", "NZDJPY", "NZDCHF", "NZDCAD",
            "XAUUSD", "XAGUSD", "XAU", "XAG", "GOLD", "SILVER",
            "USOIL", "UKOIL", "WTI", "BRENT",
            "US500", "US30", "USTEC", "SPX", "DJI", "NAS100",
            "DE40", "EU50", "UK100", "JP225", "HK50", "CN50",
            "BTCUSD", "ETHUSD", "BTC", "ETH",
        ]
        for pair in pairs:
            if re.search(rf'\b{re.escape(pair)}\b', content, re.IGNORECASE):
                symbols.add(pair)
        return list(symbols)
    
    def _extract_risk_management(self, content: str) -> dict:
        risk = {}
        patterns = {
            "stop_loss": r'(?:stop\s*loss|stoploss|sl)\s*[=:]\s*([^.\n]{1,50})',
            "take_profit": r'(?:take\s*profit|takeprofit|tp)\s*[=:]\s*([^.\n]{1,50})',
            "risk_percent": r'(?:risk|position\s*size)\s*[=:]\s*([^.\n]{1,50})',
            "lot_size": r'(?:lot|volume|position)\s*[=:]\s*([^.\n]{1,50})',
            "rr_ratio": r'(?:rr|risk\s*reward|r:r)\s*[=:]\s*([^.\n]{1,50})',
        }
        for key, pattern in patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                risk[key] = matches[:3]
        return risk


class MQL5ArticlesMiner:
    """Mines MQL5 Articles for strategy ideas."""
    
    BASE_URL = "https://www.mql5.com"
    ARTICLES_URL = "https://www.mql5.com/en/articles"
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.parser = MQL5ArticleParser()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; QuantResearchBot/1.0)"
        })
        self.data_dir = DATA_DIR / "mql5_articles"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.data_dir / "processed_articles.json"
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
        """Discover new MQL5 articles."""
        items = []
        
        try:
            response = self.session.get(self.ARTICLES_URL, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find article links
            article_links = soup.find_all("a", href=re.compile(r"/en/articles/\d+"))
            
            for link in article_links[:15]:
                href = link.get("href")
                if not href:
                    continue
                
                article_id = href.split("/")[-1]
                if article_id in self.processed:
                    continue
                
                article_url = urljoin(self.BASE_URL, href)
                try:
                    article_resp = self.session.get(article_url, timeout=15)
                    article_soup = BeautifulSoup(article_resp.text, "html.parser")
                    
                    # Extract title
                    title_elem = article_soup.find("h1", class_="article-title") or article_soup.find("h1")
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract author
                    author_elem = article_soup.find("a", class_="author-link") or article_soup.find("span", class_="author")
                    author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                    
                    # Extract date
                    date_elem = article_soup.find("span", class_="date") or article_soup.find("time")
                    published = date_elem.get("datetime") if date_elem and date_elem.has_attr("datetime") else datetime.now(UTC).isoformat()
                    
                    # Extract content
                    content_elem = article_soup.find("div", class_="article-content") or article_soup.find("article") or article_soup.find("div", class_="content")
                    content = content_elem.get_text() if content_elem else ""
                    
                    if len(content) < 500:
                        continue
                    
                    item = MQL5Article(
                        source_id=f"mql5_article_{article_id}",
                        url=f"https://www.mql5.com{href}",
                        title=title,
                        author=author,
                        published_at=published,
                        content=content,
                        metadata={"article_id": article_id},
                    )
                    items.append(item)
                    self.processed.add(article_id)
                    
                except Exception:
                    continue
            
            self._save_processed()
            
        except Exception as e:
            print(f"MQL5 Articles discover error: {e}")
        
        return items
    
    def acquire(self, config, budget) -> list:
        return []
    
    def extract(self, config, items) -> list:
        hypotheses = []
        for item in items:
            if isinstance(item, MQL5Article):
                extracted = self.parser.parse(item)
                if extracted:
                    hypothesis = self._extracted_to_hypothesis(item, extracted)
                    if hypothesis:
                        yield hypothesis
    
    def _extracted_to_hypothesis(self, item, extracted) -> dict | None:
        if not extracted.get("rules_text") and not extracted.get("code_snippets"):
            return None
        
        symbols = extracted.get("symbols_mentioned") or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
        primary = symbols[0]
        
        hypothesis = {
            "id": generate_id(),
            "origin": {
                "region": "global",
                "language": "en",
                "source_type": "mql5_articles",
                "source_id": item.source_id,
                "source_url": item.url,
                "evidence_tier": "practitioner_claim",
            },
            "mechanism": {
                "mechanism_class": "information_shock",
                "participant": "retail",
                "constraint": "technical_pattern",
                "information_source": "mql5_article",
                "why_edge_should_exist": f"MQL5 article describing strategy: {item.title}",
            },
            "market": {
                "symbols": symbols,
                "primary_symbol": primary,
                "timeframe": "H1",
            },
            "rule": {
                "inputs": ["price"] + extracted.get("indicators_mentioned", []),
                "trigger": "; ".join(extracted.get("rules_text", [])[:3]),
                "direction": 0,
                "holding_horizon": "4h",
                "exit": "opposite_signal_or_tp_sl",
                "stop": "atr_1.5",
            },
            "economics": {
                "expected_edge_bps_per_trade": 3.0,
                "expected_trades_per_month": 15,
                "expected_capacity_lots": 20,
                "expected_capacity_category": "small",
            },
            "falsifier": {
                "condition": "exp_r < 0.05R over 100 forward trades",
                "horizon": "100_trades",
                "threshold": 0.05,
                "data_source": "shadow_forward",
            },
            "metadata": {
                "source": "mql5_articles",
                "title": item.title,
                "author": item.author,
                "url": item.url,
                "extracted": extracted,
            },
        }
        return hypothesis


def discover(config, reputation) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5ArticlesMiner(base)
    return miner.discover(config, reputation)


def acquire(config, budget) -> list:
    return []


def extract(config, items) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5ArticlesMiner(base)
    return list(miner.extract(config, items))