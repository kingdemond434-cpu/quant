"""MQL5 Forum Miner — mines obscure strategies, failure reports, broker quirks from forums."""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


@dataclass
class MQL5ForumPost:
    """An MQL5 forum post/thread."""
    source_id: str
    url: str
    title: str
    author: str
    published_at: str
    content: str
    replies: int = 0
    views: int = 0
    category: str = "Forum"
    extracted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict = field(default_factory=dict)


class MQL5ForumParser:
    """Parses MQL5 forum posts for strategy content and failure reports."""
    
    STRATEGY_KEYWORDS = [
        "strategy", "system", "ea", "expert advisor", "indicator", "signal",
        "entry", "exit", "stop loss", "take profit", "trailing", "position",
        "backtest", "forward test", "live account", "real account",
        "drawdown", "profit factor", "sharpe", "recovery factor",
        "grid", "martingale", "averaging", "hedging", "scalping",
        "breakout", "reversal", "trend", "mean reversion", "range",
    ]
    
    FAILURE_KEYWORDS = [
        "blow", "blew", "margin call", "stop out", "lost", "loss", "drawdown",
        "failed", "fail", "stop working", "stopped working", "bug", "error",
        "scam", "fake", "fake results", "curve fitting", "overfit",
        "doesn't work", "does not work", "not profitable", "losing",
        "margin call", "stop out", "blown account", "wiped",
    ]
    
    BROKER_KEYWORDS = [
        "spread", "slippage", "requote", "freeze level", "stop level",
        "commission", "swap", "rollover", "execution", "latency",
        "server time", "gmt offset", "dst", "spread widening",
    ]
    
    def parse(self, post: MQL5ForumPost) -> dict | None:
        """Parse forum post for strategy content or failure reports."""
        content_lower = post.content.lower()
        
        strategy_score = sum(1 for kw in self.STRATEGY_KEYWORDS if kw in content_lower)
        failure_score = sum(1 for kw in self.FAILURE_KEYWORDS if kw in content_lower)
        broker_score = sum(1 for kw in self.BROKER_KEYWORDS if kw in content_lower)
        
        if strategy_score < 2 and failure_score < 1 and broker_score < 1:
            return None
        
        extracted = {
            "source_id": post.source_id,
            "url": post.url,
            "title": post.title,
            "author": post.author,
            "strategy_keywords": [kw for kw in self.STRATEGY_KEYWORDS if kw in post.content.lower()],
            "failure_keywords": [kw for kw in self.FAILURE_KEYWORDS if kw in post.content.lower()],
            "broker_keywords": [kw for kw in self.BROKER_KEYWORDS if kw in post.content.lower()],
            "code_snippets": self._extract_code(post.content),
            "rules_text": self._extract_rules(post.content),
            "indicators": self._extract_indicators(post.content),
            "symbols": self._extract_symbols(post.content),
            "timeframes": self._extract_timeframes(post.content),
            "is_failure_report": failure_score > 0,
            "is_broker_report": broker_score > 0,
        }
        
        return extracted
    
    def _extract_code(self, content: str) -> list[str]:
        snippets = []
        code_blocks = re.findall(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL | re.IGNORECASE)
        code_blocks += re.findall(r'<code[^>]*>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
        for block in code_blocks:
            clean = re.sub(r'<[^>]+>', '', block).strip()
            if len(clean) > 50:
                snippets.append(clean[:2000])
        return snippets[:5]
    
    def _extract_rules(self, content: str) -> list[str]:
        rules = []
        rule_patterns = [
            r'(?:buy|sell|enter|exit|close|stop|profit|target)[^.]*?(?:when|if|above|below|cross|touch|break)[^.]*\.',
            r'(?:entry|exit|stop|profit|sl|tp|take profit|stop loss)[^.]*?(?:at|when|if|above|below|cross)[^.]*\.',
        ]
        for pattern in self._compile_patterns(self.STRATEGY_KEYWORDS):
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                rules.append(m.strip()[:300])
        return rules[:10]
    
    def _compile_patterns(self, keywords):
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
        ]
        for ind in indicator_names:
            if re.search(rf'\b{re.escape(ind)}\b', content, re.IGNORECASE):
                indicators.add(ind)
        return list(indicators)
    
    def _extract_symbols(self, content: str) -> list[str]:
        symbols = set()
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
            "BTCUSD", "ETHUSD",
        ]
        for pair in pairs:
            if re.search(rf'\b{re.escape(pair)}\b', content, re.IGNORECASE):
                symbols.add(pair)
        return list(symbols)


class MQL5ForumMiner:
    """Mines MQL5 Forum for strategies and failure reports."""
    
    BASE_URL = "https://www.mql5.com"
    FORUM_URL = "https://www.mql5.com/en/forum"
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.parser = MQL5ForumParser()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; QuantResearchBot/1.0)"
        })
        self.data_dir = DATA_DIR / "mql5_forum"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.data_dir / "processed_forum.json"
        self.processed: set[str] = self._load_processed()
    
    def _load_processed(self) -> set[str]:
        processed_file = self.data_dir / "processed_forum.json"
        if processed_file.exists():
            with open(processed_file, "r") as f:
                return set(json.load(f))
        return set()
    
    def _save_processed(self) -> None:
        processed_file = self.data_dir / "processed_forum.json"
        with open(processed_file, "w") as f:
            json.dump(list(self.processed), f)
    
    def discover(self, config, reputation) -> list:
        items = []
        
        try:
            response = self.session.get(self.FORUM_URL, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find thread links
            thread_links = soup.find_all("a", href=re.compile(r"/en/forum/\d+"))
            
            for link in thread_links[:15]:
                href = link.get("href")
                if not href:
                    continue
                
                thread_id = href.split("/")[-1]
                if thread_id in self.processed:
                    continue
                
                thread_url = urljoin(self.BASE_URL, href)
                try:
                    thread_resp = self.session.get(thread_url, timeout=15)
                    thread_soup = BeautifulSoup(thread_resp.text, "html.parser")
                    
                    # Extract title
                    title_elem = thread_soup.find("h1") or thread_soup.find("h2")
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract author
                    author_elem = thread_soup.find("a", class_="author-link") or thread_soup.find("span", class_="author")
                    author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                    
                    # Extract date
                    date_elem = thread_soup.find("span", class_="date") or thread_soup.find("time")
                    published = date_elem.get("datetime") if date_elem and date_elem.has_attr("datetime") else datetime.now(UTC).isoformat()
                    
                    # Extract content (first post)
                    content_elem = thread_soup.find("div", class_="post-content") or thread_soup.find("div", class_="message")
                    content = content_elem.get_text() if content_elem else ""
                    
                    if len(content) < 200:
                        continue
                    
                    item = MQL5ForumPost(
                        source_id=f"mql5_forum_{thread_id}",
                        url=f"https://www.mql5.com{href}",
                        title=title,
                        author=author,
                        published_at=published,
                        content=content,
                        metadata={"thread_id": thread_id},
                    )
                    items.append(item)
                    self.processed.add(thread_id)
                    
                except Exception:
                    continue
            
            self._save_processed()
            
        except Exception as e:
            print(f"MQL5 Forum discover error: {e}")
        
        return items
    
    def acquire(self, config, budget) -> list:
        return []
    
    def extract(self, config, items) -> list:
        hypotheses = []
        for item in items:
            if isinstance(item, MQL5ForumPost):
                extracted = self.parser.parse(item)
                if extracted:
                    hypothesis = self._extracted_to_hypothesis(item, extracted)
                    if hypothesis:
                        yield hypothesis
    
    def _extracted_to_hypothesis(self, item, extracted) -> dict | None:
        is_failure = extracted.get("is_failure_report", False)
        is_broker = extracted.get("is_broker_report", False)
        
        if not is_failure and not is_broker and len(extracted.get("strategy_keywords", [])) < 2:
            return None
        
        symbols = extracted.get("symbols") or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
        primary = symbols[0]
        
        if is_failure:
            mechanism_class = "crowding_unwind"
            why = f"Failure report analysis: {item.title}. Failed strategies can be inverted or used as veto signals."
            capacity = "micro"
        elif is_broker:
            mechanism_class = "execution_alpha"
            why = f"Broker behavior report: {item.title}. Broker-specific execution patterns can be exploited."
            capacity = "small"
        else:
            mechanism_class = "information_shock"
            why = f"Forum strategy discussion: {item.title}"
            capacity = "small"
        
        hypothesis = {
            "id": generate_id(),
            "origin": {
                "region": "global",
                "language": "en",
                "source_type": "mql5_forum",
                "source_id": item.source_id,
                "source_url": item.url,
                "evidence_tier": "practitioner_claim",
            },
            "mechanism": {
                "mechanism_class": mechanism_class,
                "participant": "retail",
                "constraint": "forum_discussion",
                "information_source": "mql5_forum",
                "why_edge_should_exist": why,
            },
            "market": {
                "symbols": extracted.get("symbols", []) or [primary],
                "primary_symbol": primary,
                "timeframe": "H1",
            },
            "rule": {
                "inputs": ["price"] + extracted.get("indicators", []),
                "trigger": "; ".join(extracted.get("rules_text", [])[:3]),
                "direction": 0,
                "holding_horizon": "4h",
                "exit": "opposite_signal_or_tp_sl",
                "stop": "atr_1.5",
            },
            "economics": {
                "expected_edge_bps_per_trade": 1.0 if is_failure else 3.0,
                "expected_trades_per_month": 10,
                "expected_capacity_lots": 5,
                "expected_capacity_category": capacity,
            },
            "falsifier": {
                "condition": "exp_r < 0.05R over 50 forward trades",
                "horizon": "50_trades",
                "threshold": 0.05,
                "data_source": "shadow_forward",
            },
            "metadata": {
                "source": "mql5_forum",
                "title": item.title,
                "author": item.author,
                "url": item.url,
                "is_failure_report": is_failure,
                "is_broker_report": is_broker,
                "extracted": extracted,
            },
        }
        return hypothesis


def discover(config, reputation) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5ForumMiner(base)
    return miner.discover(config, reputation)


def acquire(config, budget) -> list:
    return []


def extract(config, items) -> list:
    base = Path("/home/quant/quant-platform")
    miner = MQL5ForumMiner(base)
    return list(miner.extract(config, items))