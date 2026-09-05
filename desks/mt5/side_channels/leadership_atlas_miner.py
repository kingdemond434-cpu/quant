"""Information Propagation / Leadership Atlas Miner.

Records timestamp differences for every important piece of public information:
- scheduled_time
- first_source_publish_time
- RSS_time
- API_time
- webpage_time
- translation_time
- first_market_move
- second_market_move
- broker_quote_move

Builds leadership atlas: event_type × regime × instrument A → instrument B × lag
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

LEAD_DIR = DATA_DIR / "leadership_atlas"
LEAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class InformationTimestamp:
    """Complete timestamp chain for one information event."""
    event_id: str
    event_type: str                          # "CPI", "NFP", "Fed", "Trump_post", "earnings", "geopolitical"
    source: str                              # "BLS", "FederalReserve", "TruthSocial", "Reuters", "Bloomberg"
    scheduled_time: datetime | None = None
    first_source_publish: datetime | None = None
    rss_time: datetime | None = None
    api_time: datetime | None = None
    webpage_time: datetime | None = None
    translation_time: datetime | None = None
    first_market_move: dict[str, datetime] = field(default_factory=dict)   # symbol -> time
    second_market_move: dict[str, datetime] = field(default_factory=dict)
    broker_quote_move: dict[str, datetime] = field(default_factory=dict)   # symbol -> time


@dataclass
class LeadershipEdge:
    """A leads B by X seconds for this event type and regime."""
    leader: str
    follower: str
    event_type: str
    regime: str
    lag_seconds: float
    confidence: float                        # 0-1
    sample_size: int
    last_updated: str
    lead_consistency: float                  # fraction of events where A leads B


class LeadershipAtlas:
    """Builds and maintains the cross-asset leadership atlas."""

    def __init__(self):
        self.edges: dict[tuple, LeadershipEdge] = {}
        self.timestamps: list[InformationTimestamp] = []

    def record_event(self, ts: InformationTimestamp) -> None:
        """Record a new information event and update leadership edges."""
        self.timestamps.append(ts)
        self._update_edges(ts)

    def _update_edges(self, ts: InformationTimestamp) -> None:
        """Update leadership edges from new timestamp data."""
        # Get all symbols that moved
        all_symbols = set()
        all_symbols.update(ts.first_market_move.keys())
        all_symbols.update(ts.second_market_move.keys())
        all_symbols.update(ts.broker_quote_move.keys())

        symbols = list(all_symbols)
        if len(symbols) < 2:
            return

        # For each pair, determine lead/lag
        for i, a in enumerate(symbols):
            for b in symbols[i+1:]:
                # Check first market move
                t_a = ts.first_market_move.get(a)
                t_b = ts.first_market_move.get(b)
                if t_a and t_b:
                    lag = (t_b - t_a).total_seconds()
                    self._record_edge(a, b, lag, ts.event_type, "first_move")

                # Check broker quote move
                t_a = ts.broker_quote_move.get(a)
                t_b = ts.broker_quote_move.get(b)
                if t_a and t_b:
                    lag = (t_b - t_a).total_seconds()
                    self._record_edge(a, b, lag, ts.event_type, "broker_quote")

    def _record_edge(self, leader: str, follower: str, lag: float,
                     event_type: str, move_type: str) -> None:
        """Record or update a leadership edge."""
        key = (leader, follower, event_type, move_type)
        if key not in self.edges:
            self.edges[key] = LeadershipEdge(
                leader=leader,
                follower=follower,
                event_type=event_type,
                regime="all",  # TODO: regime detection
                lag_seconds=lag,
                confidence=0.5,
                sample_size=1,
                last_updated=datetime.now(UTC).isoformat(),
                lead_consistency=1.0 if lag > 0 else 0.0,
            )
        else:
            edge = self.edges[key]
            # Exponential moving average update
            alpha = 0.1
            edge.lag_seconds = (1 - alpha) * edge.lag_seconds + alpha * lag
            edge.confidence = min(1.0, edge.confidence + 0.05)
            edge.sample_size += 1
            edge.last_updated = datetime.now(UTC).isoformat()
            # Update consistency
            edge.lead_consistency = (edge.lead_consistency * (edge.sample_size - 1) +
                                     (1.0 if lag > 0 else 0.0)) / edge.sample_size

    def get_leader(self, follower: str, event_type: str) -> list[tuple[str, float]]:
        """Get instruments that lead the given follower for event type."""
        leads = []
        for (a, b, et, mt), edge in self.edges.items():
            if b == follower and et == event_type and edge.lead_consistency > 0.6:
                leads.append((a, edge.lag_seconds))
        return sorted(leads, key=lambda x: x[1])

    def get_follower(self, leader: str, event_type: str) -> list[tuple[str, float]]:
        """Get instruments that follow the given leader for event type."""
        follows = []
        for (a, b, et, mt), edge in self.edges.items():
            if a == leader and et == event_type and edge.lead_consistency > 0.6:
                follows.append((b, edge.lag_seconds))
        return sorted(follows, key=lambda x: x[1])

    def save(self) -> None:
        """Save atlas to disk."""
        import json
        data = {
            "edges": {f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": {
                "leader": e.leader, "follower": e.follower,
                "event_type": e.event_type, "regime": e.regime,
                "lag_seconds": e.lag_seconds, "confidence": e.confidence,
                "sample_size": e.sample_size, "last_updated": e.last_updated,
                "lead_consistency": e.lead_consistency,
            } for k, e in self.edges.items()},
            "saved_at": datetime.now(UTC).isoformat(),
        }
        with open(LEAD_DIR / "leadership_atlas.json", "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load atlas from disk."""
        import json
        path = LEAD_DIR / "leadership_atlas.json"
        if not path.exists():
            return
        with open(path, "r") as f:
            data = json.load(f)
        for k_str, v in data.get("edges", {}).items():
            k = tuple(k_str.split("|"))
            self.edges[k] = LeadershipEdge(**v)


def generate_hypotheses_from_atlas(atlas: LeadershipAtlas, min_consistency: float = 0.7,
                                   min_lag: float = 1.0) -> list[SideChannelHypothesis]:
    """Generate hypotheses from leadership atlas."""
    hypotheses = []

    for (leader, follower, event_type, move_type), edge in atlas.edges.items():
        if edge.lead_consistency < min_consistency:
            continue
        if abs(edge.lag_seconds) < min_lag:
            continue

        # Only trade if lag is actionable (>1 sec, <5 min for retail)
        if not (1.0 <= edge.lag_seconds <= 300.0):
            continue

        h = SideChannelHypothesis(
            id=generate_id(),
            axis=SideChannelAxis.MICROSTRUCTURE,
            source="leadership_atlas",
            mechanism=f"{leader} leads {follower} by {edge.lag_seconds:.1f}s on {event_type} "
                      f"({edge.sample_size} events, consistency={edge.lead_consistency:.2f}). "
                      f"Trade {follower} in direction of {leader}'s move.",
            symbols=[follower],
            timing={
                "event_type": event_type,
                "leader": leader,
                "lag_seconds": edge.lag_seconds,
                "consistency": edge.lead_consistency,
                "move_type": move_type,
            },
            falsifier=f"Leadership reverses or lag exceeds 300s for {event_type} over 10+ events",
            expected_horizon=f"{int(edge.lag_seconds)}s_to_5m",
            capacity_estimate="micro",
            metadata={
                "leader": leader,
                "follower": follower,
                "event_type": event_type,
                "lag_seconds": edge.lag_seconds,
                "consistency": edge.lead_consistency,
                "sample_size": edge.sample_size,
            }
        )
        hypotheses.append(h)
        save_hypothesis(h)

    return hypotheses


def build_leadership_matrix(atlas: LeadershipAtlas) -> pd.DataFrame:
    """Build leadership matrix for visualization."""
    symbols = set()
    for (a, b, _, _), edge in atlas.edges.items():
        symbols.add(a)
        symbols.add(b)
    symbols = sorted(symbols)

    matrix = pd.DataFrame(index=symbols, columns=symbols, dtype=float)
    for (a, b, et, mt), edge in atlas.edges.items():
        if edge.lead_consistency > 0.6:
            matrix.loc[a, b] = edge.lag_seconds
    return matrix


# Event type definitions with expected leadership patterns
EVENT_TYPES = {
    "US_CPI": {
        "expected_leader": ["US10Y", "US2Y", "DXY"],
        "expected_followers": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "US500"],
        "schedule": "monthly_2nd_week_wed_12:30_UTC",
    },
    "US_NFP": {
        "expected_leader": ["US2Y", "US10Y", "DXY"],
        "expected_followers": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "US500", "USOIL"],
        "schedule": "monthly_1st_friday_12:30_UTC",
    },
    "FOMC_Statement": {
        "expected_leader": ["US2Y", "FED_FUNDS", "DXY"],
        "expected_followers": ["XAUUSD", "ALL_FX", "US500", "US10Y"],
        "schedule": "8_per_year_wed_18:00_UTC",
    },
    "FOMC_Minutes": {
        "expected_leader": ["US10Y", "DXY"],
        "expected_followers": ["XAUUSD", "EURUSD", "GBPUSD", "US500"],
        "schedule": "3_weeks_after_FOMC_wed_18:00_UTC",
    },
    "ECB_Statement": {
        "expected_leader": ["DE10Y", "EURUSD"],
        "expected_followers": ["EURGBP", "EURJPY", "EURCHF", "EU50", "XAUUSD"],
        "schedule": "monthly_thu_12:45_UTC",
    },
    "BOE_Statement": {
        "expected_leader": ["UK10Y", "GBPUSD"],
        "expected_followers": ["EURGBP", "GBPJPY", "UK100"],
        "schedule": "monthly_thu_12:00_UTC",
    },
    "BOJ_Statement": {
        "expected_leader": ["JP10Y", "USDJPY"],
        "expected_followers": ["EURJPY", "GBPJPY", "AUDJPY", "JP225"],
        "schedule": "monthly_varies",
    },
    "Trump_Truth_Social": {
        "expected_leader": ["TruthSocial_API", "RSS"],
        "expected_followers": ["XAUUSD", "USOIL", "DXY", "US500", "USDJPY", "USDCNH"],
        "schedule": "unscheduled",
        "domains": ["tariff", "geopolitical", "fed_criticism", "fiscal", "china", "sanctions", "energy"],
    },
    "Earnings_Surprise": {
        "expected_leader": ["individual_stock", "sector_ETF"],
        "expected_followers": ["index", "related_stocks", "options_skew"],
        "schedule": "quarterly",
    },
    "Geopolitical_Escalation": {
        "expected_leader": ["news_wire", "official_statement"],
        "expected_followers": ["XAUUSD", "USOIL", "DXY", "safe_haven_FX", "defense_stocks"],
        "schedule": "unscheduled",
    },
}


def get_expected_leadership(event_type: str) -> dict:
    """Get expected leadership pattern for an event type."""
    return EVENT_TYPES.get(event_type, {"expected_leader": [], "expected_followers": []})


if __name__ == "__main__":
    atlas = LeadershipAtlas()
    atlas.load()
    print(f"Loaded {len(atlas.edges)} leadership edges")

    # Generate hypotheses
    hyps = generate_hypotheses_from_atlas(atlas)
    print(f"Generated {len(hyps)} leadership hypotheses")

    # Build matrix
    matrix = build_leadership_matrix(atlas)
    matrix.to_csv(LEAD_DIR / "leadership_matrix.csv")
    print(f"Saved leadership matrix to {LEAD_DIR}/leadership_matrix.csv")

    atlas.save()
    print("Atlas saved")