"""Macro Revision Miner — mines the hidden dimension of macro data: revisions.

Most retail focuses on actual vs forecast. The revision vector contains more structure:
- initial print
- previous value
- revised previous value
- revision magnitude
- revision direction
- historical revision tendency

Tests whether markets:
- underreact to revisions
- care more about payroll revision than headline
- react differently when headline/revision disagree
- price persistent revision regimes
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

REV_DIR = DATA_DIR / "macro_revisions"
REV_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MacroRelease:
    """A macro data release with revision history."""
    series_id: str                           # FRED series ID
    release_date: datetime
    actual: float
    forecast: float
    previous: float
    revised_previous: float | None = None
    revision: float = 0.0                    # revised_previous - previous
    revision_direction: str = "none"         # "up", "down", "none"
    surprise: float = 0.0                    # actual - forecast
    surprise_direction: str = "none"
    market_reaction: dict[str, float] = field(default_factory=dict)  # symbol -> move
    regime: str = "normal"


@dataclass
class RevisionSignal:
    """Signal from revision analysis."""
    release_date: datetime
    series_id: str
    signal_type: str                         # "revision_surprise", "headline_revision_diverge", "persistent_regime"
    direction: int
    strength: float
    expected_horizon: str
    context: dict
    subsequent_outcome: dict | None = None


class MacroRevisionCollector:
    """Collects macro releases with revision data from FRED/ALFRED."""

    def __init__(self):
        self.releases: list[MacroRelease] = []

    def load_from_fred(self, series_ids: list[str], start: datetime, end: datetime) -> None:
        """Load releases with revision data from FRED API."""
        try:
            import fredapi
        except ImportError:
            print("fredapi not installed")
            return

        # This would use fredapi in production
        # For now, create synthetic structure
        pass

    def add_release(self, release: MacroRelease) -> None:
        self.releases.append(release)

    def compute_revision_stats(self) -> pd.DataFrame:
        """Compute revision statistics per series."""
        if not self.releases:
            return pd.DataFrame()

        df = pd.DataFrame([{
            "series_id": r.series_id,
            "date": r.release_date,
            "actual": r.actual,
            "forecast": r.forecast,
            "previous": r.previous,
            "revised_previous": r.revised_previous,
            "revision": r.revision,
            "surprise": r.surprise,
        } for r in self.releases])

        stats = df.groupby("series_id").agg(
            mean_revision=("revision", "mean"),
            std_revision=("revision", "std"),
            mean_surprise=("surprise", "mean"),
            std_surprise=("surprise", "std"),
            revision_surprise_corr=("revision", lambda x: x.corr(df.loc[x.index, "surprise"])),
            up_revisions=("revision", lambda x: (x > 0).sum()),
            down_revisions=("revision", lambda x: (x < 0).sum()),
            total=("revision", "count"),
        ).reset_index()

        return stats


class MacroRevisionAnalyzer:
    """Analyzes macro revisions for alpha."""

    def __init__(self):
        self.collector = MacroRevisionCollector()
        self.signals: list[RevisionSignal] = []

    def detect_revision_surprise(self, release: MacroRelease) -> list[RevisionSignal]:
        """Market underreacts to revision vs headline surprise."""
        signals = []

        if release.revised_previous is None:
            return signals

        # Large revision relative to historical
        if abs(release.revision) > 2 * abs(release.surprise):
            # Revision larger than surprise - market may miss it
            signals.append(RevisionSignal(
                release_date=release.release_date,
                series_id=release.series_id,
                signal_type="revision_surprise",
                direction=1 if release.revision > 0 else -1,
                strength=min(abs(release.revision) / (abs(release.surprise) + 1e-12), 1.0),
                expected_horizon="1h_to_1d",
                context={
                    "revision": release.revision,
                    "surprise": release.surprise,
                    "ratio": release.revision / (release.surprise + 1e-12),
                }
            ))

        return signals

    def detect_headline_revision_divergence(self, release: MacroRelease) -> list[RevisionSignal]:
        """Headline and revision disagree (e.g., hot headline but down revision)."""
        signals = []

        if release.revised_previous is None:
            return signals

        surprise_dir = 1 if release.surprise > 0 else (-1 if release.surprise < 0 else 0)
        revision_dir = 1 if release.revision > 0 else (-1 if release.revision < 0 else 0)

        if surprise_dir != 0 and revision_dir != 0 and surprise_dir != revision_dir:
            # Headline and revision point opposite ways
            signals.append(RevisionSignal(
                release_date=release.release_date,
                series_id=release.series_id,
                signal_type="headline_revision_diverge",
                direction=revision_dir,  # Bet on revision direction
                strength=0.8,
                expected_horizon="15m_to_4h",
                context={
                    "surprise": release.surprise,
                    "revision": release.revision,
                    "conflict": "headline_vs_revision",
                }
            ))

        return signals

    def detect_persistent_revision_regime(self, series_id: str, window: int = 12) -> list[RevisionSignal]:
        """Persistent revision regime: consistent up/down revisions."""
        signals = []
        series_releases = [r for r in self.collector.releases if r.series_id == series_id]
        if len(series_releases) < window:
            return signals

        recent = series_releases[-window:]
        revisions = [r.revision for r in recent if r.revised_previous is not None]

        if len(revisions) < window // 2:
            return signals

        up_count = sum(1 for rev in revisions if rev > 0)
        down_count = sum(1 for rev in revisions if rev < 0)

        # Strong bias
        if up_count / len(revisions) > 0.75:
            signals.append(RevisionSignal(
                release_date=series_releases[-1].release_date,
                series_id=series_id,
                signal_type="persistent_revision_regime",
                direction=1,  # Expect upward revisions to continue
                strength=(up_count / len(revisions)) - 0.5,
                expected_horizon="1m_to_3m",
                context={
                    "up_ratio": up_count / len(revisions),
                    "window": window,
                }
            ))
        elif down_count / len(revisions) > 0.75:
            signals.append(RevisionSignal(
                release_date=series_releases[-1].release_date,
                series_id=series_id,
                signal_type="persistent_revision_regime",
                direction=-1,
                strength=(down_count / len(revisions)) - 0.5,
                expected_horizon="1m_to_3m",
                context={
                    "down_ratio": down_count / len(revisions),
                    "window": window,
                }
            ))

        return signals

    def detect_payroll_revision_dominance(self) -> list[RevisionSignal]:
        """Payroll revision often matters more than headline NFP."""
        signals = []
        nfp_releases = [r for r in self.collector.releases if r.series_id == "PAYEMS"]

        for i, r in enumerate(nfp_releases):
            if r.revised_previous is None or i == 0:
                continue

            prev = nfp_releases[i-1]
            # If previous month revised significantly
            if prev.revised_previous is not None:
                prev_revision = prev.revised_previous - prev.previous
                if abs(prev_revision) > abs(r.surprise):
                    signals.append(RevisionSignal(
                        release_date=r.release_date,
                        series_id="PAYEMS",
                        signal_type="payroll_revision_dominance",
                        direction=1 if prev_revision > 0 else -1,
                        strength=min(abs(prev_revision) / (abs(r.surprise) + 1e-12), 1.0),
                        expected_horizon="1h_to_1d",
                        context={
                            "prev_revision": prev_revision,
                            "current_surprise": r.surprise,
                            "dominance": "revision_over_headline",
                        }
                    ))

        return signals

    def generate_all_signals(self) -> list[RevisionSignal]:
        """Generate all revision signals."""
        all_signals = []

        for release in self.collector.releases:
            all_signals.extend(self.detect_revision_surprise(release))
            all_signals.extend(self.detect_headline_revision_divergence(release))

        # Series-level signals
        series_ids = set(r.series_id for r in self.collector.releases)
        for sid in series_ids:
            all_signals.extend(self.detect_persistent_revision_regime(sid))

        all_signals.extend(self.detect_payroll_revision_dominance())

        self.signals = all_signals
        return all_signals

    def record_outcome(self, signal: RevisionSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 8) -> list[SideChannelHypothesis]:
        """Generate hypotheses from revision signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.signal_type}_{s.series_id}"
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
                    axis=SideChannelAxis.MACRO,
                    source="macro_revision_miner",
                    mechanism=f"Macro revision signal: {example.signal_type} on {example.series_id}. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} releases. "
                              f"Markets underreact to revision information.",
                    symbols=["DXY", "XAUUSD", "US10Y", "US2Y", "EURUSD", "USDJPY", "US500"],
                    timing={
                        "series_id": example.series_id,
                        "signal_type": example.signal_type,
                    },
                    falsifier=f"Avg return drops below 0 over 20+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="institutional",
                    metadata={
                        "series_id": example.series_id,
                        "signal_type": example.signal_type,
                        "avg_return_r": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(REV_DIR / "releases.json", "w") as f:
            json.dump([{
                "series_id": r.series_id,
                "date": r.release_date.isoformat(),
                "actual": r.actual,
                "forecast": r.forecast,
                "previous": r.previous,
                "revised_previous": r.revised_previous,
                "revision": r.revision,
                "surprise": r.surprise,
            } for r in self.collector.releases], f, indent=2, default=str)

        with open(REV_DIR / "signals.json", "w") as f:
            json.dump([{
                "date": s.release_date.isoformat(),
                "series_id": s.series_id,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    collector = MacroRevisionCollector()
    dates = pd.date_range("2025-01-01", periods=24, freq="M", tz=UTC)

    for i, d in enumerate(dates):
        collector.add_release(MacroRelease(
            series_id="PAYEMS",
            release_date=d,
            actual=200 + np.random.randn() * 50,
            forecast=200,
            previous=180 + np.random.randn() * 30,
            revised_previous=190 + np.random.randn() * 20,
            revision=10 + np.random.randn() * 15,
            surprise=np.random.randn() * 40,
        ))
        collector.add_release(MacroRelease(
            series_id="CPIAUCSL",
            release_date=d,
            actual=3.2 + np.random.randn() * 0.3,
            forecast=3.1,
            previous=3.0 + np.random.randn() * 0.2,
            revised_previous=3.1 + np.random.randn() * 0.15,
            revision=0.1 + np.random.randn() * 0.1,
            surprise=np.random.randn() * 0.2,
        ))

    analyzer = MacroRevisionAnalyzer()
    analyzer.collector = collector
    signals = analyzer.generate_all_signals()
    print(f"Generated {len(signals)} revision signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} revision hypotheses")