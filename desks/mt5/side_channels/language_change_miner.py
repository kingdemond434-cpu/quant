"""Language Change Miner — mines linguistic deltas in central bank / policy documents.

Don't ask LLMs for sentiment. Diff documents:
- Fed statements / minutes
- ECB statements / accounts
- BOE minutes / reports
- BOJ statements / outlook
- Earnings releases
- Corporate guidance
- Regulator notices

Extract: sentence added/removed, word changed, numeric guidance changed,
ordering changed, uncertainty language changed.

Connect specific linguistic deltas to subsequent markets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

LANG_DIR = DATA_DIR / "language_changes"
LANG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DocumentVersion:
    """A version of a tracked document."""
    source: str                              # "FED_STATEMENT", "ECB_MINUTES", "FOMC_MINUTES", "BOE_REPORT", "EARNINGS"
    document_id: str                         # e.g., "FOMC_2026_07_31"
    version: int
    timestamp: datetime
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class LanguageDelta:
    """A detected change between document versions."""
    source: str
    document_id: str
    prev_version: int
    curr_version: int
    timestamp: datetime
    delta_type: str                          # "sentence_added", "sentence_removed", "word_changed", "numeric_changed", "ordering_changed", "uncertainty_changed"
    original: str                            # old text
    modified: str                            # new text
    location: str                            # paragraph/section
    significance: float                      # 0-1
    metadata: dict = field(default_factory=dict)


@dataclass
class LanguageSignal:
    """Alpha signal from language change."""
    timestamp: datetime
    source: str
    document_id: str
    delta_type: str
    direction: int                             # market direction implied
    strength: float
    expected_horizon: str
    affected_symbols: list[str]
    context: dict
    subsequent_outcome: dict | None = None


# Document sources to track
DOCUMENT_SOURCES = {
    "FED_STATEMENT": {
        "schedule": "8_per_year",
        "url_pattern": "https://www.federalreserve.gov/monetarypolicy/fomcstatements{year}.htm",
        "sections": ["policy_rate", "balance_sheet", "economic_assessment", "forward_guidance"],
        "symbols": ["DXY", "US10Y", "US2Y", "XAUUSD", "EURUSD", "USDJPY", "US500"],
    },
    "FOMC_MINUTES": {
        "schedule": "3_weeks_after_statement",
        "url_pattern": "https://www.federalreserve.gov/monetarypolicy/fomcminutes{year}.htm",
        "sections": ["discussion", "policy_deliberation", "risk_assessment"],
        "symbols": ["DXY", "US10Y", "US2Y", "XAUUSD", "US500"],
    },
    "ECB_STATEMENT": {
        "schedule": "monthly",
        "url_pattern": "https://www.ecb.europa.eu/press/pr/date/{year}/html/index.en.html",
        "sections": ["rate_decision", "asset_purchases", "forward_guidance", "economic_assessment"],
        "symbols": ["EURUSD", "EURGBP", "EURJPY", "DE10Y", "EU50", "XAUUSD"],
    },
    "ECB_ACCOUNTS": {
        "schedule": "2_weeks_after_statement",
        "url_pattern": "https://www.ecb.europa.eu/press/accounts/date/{year}/html/index.en.html",
        "sections": ["monetary_policy", "financial_stability"],
        "symbols": ["EURUSD", "DE10Y", "EU50"],
    },
    "BOE_MINUTES": {
        "schedule": "monthly",
        "url_pattern": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes",
        "sections": ["vote", "economic_outlook", "policy_discussion"],
        "symbols": ["GBPUSD", "GBPJPY", "UK10Y", "UK100"],
    },
    "BOJ_STATEMENT": {
        "schedule": "monthly",
        "url_pattern": "https://www.boj.or.jp/en/announcements/release_{year}/index.htm",
        "sections": ["yield_curve_control", "etf_purchases", "forward_guidance"],
        "symbols": ["USDJPY", "EURJPY", "JP225", "JP10Y"],
    },
    "BOJ_OUTLOOK": {
        "schedule": "quarterly",
        "url_pattern": "https://www.boj.or.jp/en/mopo/outlook/index.htm",
        "sections": ["growth", "inflation", "risk_balance"],
        "symbols": ["USDJPY", "JP225", "JP10Y"],
    },
}


class DocumentTracker:
    """Tracks document versions and detects changes."""

    def __init__(self):
        self.versions: dict[str, list[DocumentVersion]] = {}
        self.deltas: list[LanguageDelta] = []

    def add_version(self, source: str, document_id: str, text: str, metadata: dict = None) -> DocumentVersion:
        """Add a new document version."""
        if source not in self.versions:
            self.versions[source] = []

        version_num = len(self.versions[source]) + 1
        version = DocumentVersion(
            source=source,
            document_id=document_id,
            version=version_num,
            timestamp=datetime.now(UTC),
            text=text,
            metadata=metadata or {},
        )
        self.versions[source].append(version)

        # Compare with previous version
        if version_num > 1:
            self._detect_deltas(version, self.versions[source][-2])

        return version

    def _detect_deltas(self, curr: DocumentVersion, prev: DocumentVersion) -> list[LanguageDelta]:
        """Detect linguistic changes between versions."""
        deltas = []

        # Simple sentence-level diff
        prev_sentences = self._split_sentences(prev.text)
        curr_sentences = self._split_sentences(curr.text)

        # Sentence added/removed
        prev_set = set(prev_sentences)
        curr_set = set(curr_sentences)

        for sent in curr_set - prev_set:
            deltas.append(LanguageDelta(
                source=curr.source,
                document_id=curr.document_id,
                prev_version=prev.version,
                curr_version=curr.version,
                timestamp=curr.timestamp,
                delta_type="sentence_added",
                original="",
                modified=sent[:200],
                location="unknown",
                significance=0.7,
                metadata={"length": len(sent)}
            ))

        for sent in prev_set - curr_set:
            deltas.append(LanguageDelta(
                source=curr.source,
                document_id=curr.document_id,
                prev_version=prev.version,
                curr_version=curr.version,
                timestamp=curr.timestamp,
                delta_type="sentence_removed",
                original=sent[:200],
                modified="",
                location="unknown",
                significance=0.8,  # Removal often more significant
                metadata={"length": len(sent)}
            ))

        # Numeric changes (rates, dates, percentages)
        numeric_deltas = self._detect_numeric_changes(prev.text, curr.text)
        for nd in numeric_deltas:
            deltas.append(LanguageDelta(
                source=curr.source,
                document_id=curr.document_id,
                prev_version=prev.version,
                curr_version=curr.version,
                timestamp=curr.timestamp,
                delta_type="numeric_changed",
                original=nd["old"],
                modified=nd["new"],
                location=nd["context"],
                significance=0.9,  # Numeric changes highly significant
                metadata=nd["metadata"]
            ))

        # Uncertainty language changes
        uncertainty_deltas = self._detect_uncertainty_changes(prev.text, curr.text)
        for ud in uncertainty_deltas:
            deltas.append(LanguageDelta(
                source=curr.source,
                document_id=curr.document_id,
                prev_version=prev.version,
                curr_version=curr.version,
                timestamp=curr.timestamp,
                delta_type="uncertainty_changed",
                original=ud["old"],
                modified=ud["new"],
                location=ud["context"],
                significance=0.85,
                metadata=ud["metadata"]
            ))

        self.deltas.extend(deltas)
        return deltas

    def _split_sentences(self, text: str) -> list[str]:
        """Simple sentence splitting."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _detect_numeric_changes(self, old: str, new: str) -> list[dict]:
        """Detect changes in numbers (rates, dates, percentages)."""
        import re
        changes = []

        # Pattern for numbers with context
        num_pattern = r'(\b\d+(?:\.\d+)?\s*(?:%|percent|basis points?|bps|percentage points?)\b)'

        old_nums = re.findall(num_pattern, old, re.IGNORECASE)
        new_nums = re.findall(num_pattern, new, re.IGNORECASE)

        if set(old_nums) != set(new_nums):
            # Find context around changed numbers
            for num in set(new_nums) - set(old_nums):
                context = self._get_context(new, num)
                changes.append({
                    "old": "not present",
                    "new": num,
                    "context": context,
                    "metadata": {"type": "added", "value": num}
                })

            for num in set(old_nums) - set(new_nums):
                context = self._get_context(old, num)
                changes.append({
                    "old": num,
                    "new": "removed",
                    "context": context,
                    "metadata": {"type": "removed", "value": num}
                })

        return changes

    def _get_context(self, text: str, target: str, window: int = 100) -> str:
        """Get surrounding context for a target string."""
        idx = text.find(target)
        if idx == -1:
            return "unknown"
        start = max(0, idx - window)
        end = min(len(text), idx + len(target) + window)
        return text[start:end].replace("\n", " ")

    def _detect_uncertainty_changes(self, old: str, new: str) -> list[dict]:
        """Detect changes in uncertainty language."""
        import re

        uncertainty_words = [
            "uncertain", "uncertainty", "unclear", "unknown", "difficult",
            "risk", "risk-weighted", "downside risk", "upside risk",
            "may", "might", "could", "possible", "potential",
            "monitor", "monitoring", "watch", "watching",
            "data dependent", "data-dependent", "meeting by meeting",
            "flexible", "patient", "cautious", "vigilant",
            "confident", "assured", "certain", "clear",
        ]

        changes = []

        for word in uncertainty_words:
            old_count = len(re.findall(rf'\b{re.escape(word)}\b', old, re.IGNORECASE))
            new_count = len(re.findall(rf'\b{re.escape(word)}\b', new, re.IGNORECASE))

            if old_count != new_count:
                # Find context
                context = self._get_context(new if new_count > old_count else old, word)
                changes.append({
                    "old": word * old_count,
                    "new": word * new_count,
                    "context": context,
                    "metadata": {
                        "word": word,
                        "old_count": old_count,
                        "new_count": new_count,
                        "change": new_count - old_count,
                    }
                })

        return changes


class LanguageChangeAnalyzer:
    """Analyzes language deltas for market signals."""

    def __init__(self):
        self.tracker = DocumentTracker()
        self.signals: list[LanguageSignal] = []

    def process_document(self, source: str, document_id: str, text: str, metadata: dict = None) -> list[LanguageDelta]:
        """Process a new document version."""
        version = self.tracker.add_version(source, document_id, text, metadata)
        return [d for d in self.tracker.deltas if d.document_id == document_id and d.curr_version == version.version]

    def generate_signals_from_deltas(self, deltas: list[LanguageDelta]) -> list[LanguageSignal]:
        """Convert language deltas to trading signals."""
        signals = []

        for delta in deltas:
            source_info = DOCUMENT_SOURCES.get(delta.source, {})
            symbols = source_info.get("symbols", [])

            if delta.delta_type == "numeric_changed":
                # Numeric changes in policy rates, projections = high significance
                direction = self._interpret_numeric_change(delta, source_info)
                if direction != 0:
                    signals.append(LanguageSignal(
                        timestamp=delta.timestamp,
                        source=delta.source,
                        document_id=delta.document_id,
                        delta_type=delta.delta_type,
                        direction=direction,
                        strength=min(delta.significance * 1.2, 1.0),
                        expected_horizon="15m_to_4h",
                        affected_symbols=symbols,
                        context={
                            "original": delta.original,
                            "modified": delta.modified,
                            "location": delta.location,
                        }
                    ))

            elif delta.delta_type == "sentence_removed":
                # Removal of dovish/hawkish language
                direction = self._interpret_removal(delta, source_info)
                if direction != 0:
                    signals.append(LanguageSignal(
                        timestamp=delta.timestamp,
                        source=delta.source,
                        document_id=delta.document_id,
                        delta_type=delta.delta_type,
                        direction=direction,
                        strength=delta.significance,
                        expected_horizon="1h_to_1d",
                        affected_symbols=symbols,
                        context={"removed": delta.original}
                    ))

            elif delta.delta_type == "uncertainty_changed":
                # Uncertainty reduction = confidence
                direction = self._interpret_uncertainty(delta, source_info)
                if direction != 0:
                    signals.append(LanguageSignal(
                        timestamp=delta.timestamp,
                        source=delta.source,
                        document_id=delta.document_id,
                        delta_type=delta.delta_type,
                        direction=direction,
                        strength=delta.significance * 0.8,
                        expected_horizon="1h_to_1d",
                        affected_symbols=symbols,
                        context={
                            "word": delta.metadata.get("word"),
                            "change": delta.metadata.get("change"),
                        }
                    ))

        self.signals.extend(signals)
        return signals

    def _interpret_numeric_change(self, delta: LanguageDelta, source_info: dict) -> int:
        """Interpret numeric change for market direction."""
        # Simplified: higher rates = stronger currency, lower gold
        try:
            old_val = float(re.search(r'[\d.]+', delta.original).group())
            new_val = float(re.search(r'[\d.]+', delta.modified).group())

            if "rate" in delta.location.lower() or "rate" in delta.context.lower():
                if new_val > old_val:  # Rate hike
                    return -1 if "XAUUSD" in str(source_info.get("symbols", [])) else 1  # USD up, gold down
                else:
                    return 1 if "XAUUSD" in str(source_info.get("symbols", [])) else -1
        except Exception:
            pass
        return 0

    def _interpret_removal(self, delta: LanguageDelta, source_info: dict) -> int:
        """Interpret sentence removal."""
        text = delta.original.lower()
        # Dovish language removed = hawkish
        dovish = ["patient", "accommodative", "supportive", "gradual", "lower for longer"]
        hawkish = ["restrictive", "tightening", "higher for longer", "vigilant", "inflation"]

        for w in dovish:
            if w in text:
                return 1  # USD up, gold down
        for w in hawkish:
            if w in text:
                return -1  # USD down, gold up
        return 0

    def _interpret_uncertainty(self, delta: LanguageDelta, source_info: dict) -> int:
        """Interpret uncertainty language change."""
        change = delta.metadata.get("change", 0)
        word = delta.metadata.get("word", "")

        # Uncertainty reduction = confidence = policy continuity
        if change < 0:  # Less uncertainty
            if "rate" in word or "inflation" in word:
                return 1  # Hawkish confidence
        elif change > 0:  # More uncertainty
            return -1  # Dovish uncertainty
        return 0

    def record_outcome(self, signal: LanguageSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 5) -> list[SideChannelHypothesis]:
        """Generate hypotheses from language signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.delta_type}_{s.source}"
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
                    axis=SideChannelAxis.EVENT,
                    source="language_change_miner",
                    mechanism=f"Language delta: {example.delta_type} in {example.source}. "
                              f"Specific word/number change predicts market move. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} occurrences.",
                    symbols=example.affected_symbols,
                    timing={
                        "source": example.source,
                        "delta_type": example.delta_type,
                    },
                    falsifier=f"Avg return drops below 0 over 15+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="institutional",
                    metadata={
                        "source": example.source,
                        "delta_type": example.delta_type,
                        "avg_return_r": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(LANG_DIR / "deltas.json", "w") as f:
            json.dump([{
                "source": d.source,
                "document_id": d.document_id,
                "prev_version": d.prev_version,
                "curr_version": d.curr_version,
                "timestamp": d.timestamp.isoformat(),
                "delta_type": d.delta_type,
                "original": d.original,
                "modified": d.modified,
                "location": d.location,
                "significance": d.significance,
            } for d in self.tracker.deltas], f, indent=2, default=str)

        with open(LANG_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "source": s.source,
                "document_id": s.document_id,
                "delta_type": s.delta_type,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "symbols": s.affected_symbols,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    tracker = DocumentTracker()

    # Simulate FOMC statement change
    old_statement = """The Committee decided to maintain the target range for the federal funds rate at 5.25-5.50 percent. The Committee is strongly committed to returning inflation to its 2 percent objective. The Committee will continue to monitor the implications of incoming information for the economic outlook."""

    new_statement = """The Committee decided to maintain the target range for the federal funds rate at 5.25-5.50 percent. The Committee is strongly committed to returning inflation to its 2 percent objective. The Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. The Committee does not expect it will be appropriate to reduce the target range until it has gained greater confidence that inflation is moving sustainably toward 2 percent."""

    tracker.add_version("FED_STATEMENT", "FOMC_2026_07_31", old_statement)
    deltas = tracker.add_version("FED_STATEMENT", "FOMC_2026_07_31", new_statement)

    print(f"Detected {len(deltas)} language deltas:")
    for d in deltas:
        print(f"  {d.delta_type}: {d.original[:50]}... -> {d.modified[:50]}...")

    analyzer = LanguageChangeAnalyzer()
    analyzer.tracker = tracker
    signals = analyzer.generate_signals_from_deltas(deltas)
    print(f"Generated {len(signals)} language signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} language hypotheses")