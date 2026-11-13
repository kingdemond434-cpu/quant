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

try:
    from . import DATA_DIR, SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis
except ImportError:  # pragma: no cover - exercised by the hourly leg, which runs this file
    # RUNNABLE AS A SCRIPT (the `leadership_atlas` hourly leg runs this file by path); the
    # package import stays first, as in alpha_periodic_table.
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from side_channels import (  # type: ignore[no-redef]
        DATA_DIR,
        SideChannelAxis,
        SideChannelHypothesis,
        generate_id,
        save_hypothesis,
    )

#: DONATIONS ONLY. `miner_candidate_compiler` reads every file under data/intelligence/**, so the
#: atlas's state, its edge table and its matrix live in WORK_DIR (gitignored) and only
#: `discoveries_*.json` lands here (Auditor HOLD on #1146, MF4).
LEAD_DIR = DATA_DIR / "leadership_atlas"
WORK_DIR = Path(__file__).resolve().parents[1] / "data" / "leadership_atlas"


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
    direction_agreement: float = float("nan")  # share of events where B moved A's way
    wilson_lb: float = 0.0                   # lower 95% bound on lead_consistency
    median_lag_seconds: float = float("nan")


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
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORK_DIR / "leadership_atlas.json", "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load atlas from disk."""
        import json
        path = WORK_DIR / "leadership_atlas.json"
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


# =============================================================================================
# THE FEED, THE CLOCK AND THE JUDGE DOOR (2026-11-13; Auditor HOLD on #1146 answered same day)
#
# Until now nothing ever called `record_event`: the atlas was a data structure with no input, no
# clock and no consumer. What closes it, end to end:
#
#   1. EVENTS. `mt5desk.release_calendar.calendar_events` -- the ONE reader the executing family
#      also uses: release instants in `data/calendar_backfill/` and the calendar miner's
#      `ff_calendar_vintage`. Only zoned clock-time stamps are instants; date-only, naive and
#      ALFRED realtime_start rows are skipped and counted (SF3).
#   2. MOVES. Each watched instrument's own broker quotes (`data/tape/ticks/<SYM>/<day>.parquet`),
#      converted from broker time to true UTC with the desk's one clock rule
#      (`libs.regime.session_clock.server_to_utc`). A symbol's FIRST MARKET MOVE is the first
#      second after the event at which its mid has left the pre-event price by more than
#      k x sigma_1s x sqrt(t), sigma measured on the 30 minutes BEFORE the event. Its BROKER
#      QUOTE MOVE is the first quote revision.
#   3. REGIME. A symbol's pre-event sigma against the median of its own pre-event sigmas on the
#      PRIOR releases of the same type (>= MIN_PRIOR, else unknown): "calm" / "stressed". Each
#      pair is keyed on EACH member's regime, and an edge keeps only the key conditioned on its
#      LEADER, so the regime always names the leader's state (SF4). `family_release_lead_lag`
#      computes the same definition on bars.
#   4. EDGES. Per (leader, follower, event type, move type, regime): every signed lag; the median
#      lag, the leader-first share with its Wilson bound, and the direction agreement.
#   5. MULTIPLE TESTING (MF3). The leader is chosen after looking, so the lead p-value is the
#      TWO-SIDED exact binomial; direction agreement is a second two-sided binomial; an edge's p
#      is the larger of the two (an intersection-union test). Benjamini-Hochberg at FDR_Q runs
#      over EVERY key the atlas holds -- all pairs x events x move types x regimes, whatever their
#      sample -- so the family-wise search is paid before anything is donated. Each donation also
#      names its claim family (`leadership_atlas:<event type>`) and the keys searched for that type
#      as `claim_selection_trials`, which the compiler stamps and the trial ledger charges once.
#   6. JUDGE (MF2). A surviving edge is donated as `family_hint: release_lead_lag` with its event
#      type, regime and chart, which the compiler maps to `family_release_lead_lag` with all three
#      on the recipe and the chart pinned -- the claim the atlas measured, not an unconditional
#      lead-lag on every chart. Only NEW or CHANGED edges are donated (SF2): a re-donation would
#      bump the registry's search_count for a test already charged.
#   7. NEVER READS THE JUDGE'S LOCKBOX (Auditor HOLD on #1146, round 2). An event is processed
#      only when its whole post window ends a full day before the campaign lockbox cut the
#      gauntlet last used (`research.lockbox_cut`, published to reports/LOCKBOX_CUT.json; the day
#      covers the broker clock running ahead of UTC). Later events wait, unmarked, until the cut
#      moves past them. No readable cut: nothing is processed and nothing is donated.
#   8. NEVER COUNTED TWICE, AND BOUNDED (SF6). Processed event ids are kept (newest
#      MAX_PROCESSED), lags per key are capped at MAX_LAGS, and the state lives in the gitignored
#      `data/leadership_atlas/`, never in data/intelligence.
#
# Clock: hourly leg `leadership_atlas` (research/hourly_cycle.py), 240 s. Artifacts:
# reports/LEADERSHIP_ATLAS.json, data/intelligence/leadership_atlas/discoveries_*.json.
# =============================================================================================

import json
import math
import time

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_DESK))
from mt5desk.release_calendar import EVENT_PATTERNS, calendar_events, classify_event  # noqa: E402

TICKS = _DESK / "data" / "tape" / "ticks"
UNIVERSE = _DESK / "data" / "universe"
STATE = WORK_DIR / "atlas_state.json"
REPORT = _DESK / "reports" / "LEADERSHIP_ATLAS.json"

__all__ = ["EVENT_PATTERNS", "calendar_events", "classify_event"]

#: Instruments watched around every event: the majors, gold and silver, the dollar index, the
#: big indices, oil and the curve proxy the broker quotes. Only ones in the universe are read.
WATCH: tuple[str, ...] = (
    "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "USDCNH", "USDMXN", "USDX", "US500", "NAS100", "US30",
    "GER40", "UK100", "EUSTX50", "FRA40", "JPN225", "HK50", "AUS200", "XTIUSD", "XBRUSD",
    "XNGUSD", "UST10Y", "CORN", "WHEAT", "SOYBEAN")

PRE_S = 1800            # seconds of quotes before the event that set sigma and the reference
POST_S = 1800           # seconds after the event searched for a first passage
K_SIGMA = 4.0           # envelope width: k sigma_1s sqrt(t)
MIN_PRE_TICKS = 30      # fewer quotes than this before the event: the symbol is UNMEASURED
MIN_EVENTS = 12         # events an edge needs before it may reach the judge
MIN_WILSON = 0.60       # lower bound on "leader first" an edge must clear (reported, and kept)
MIN_AGREE_GAP = 0.20    # |direction agreement - 0.5| for the sign to be decisive
FDR_Q = 0.05            # Benjamini-Hochberg false discovery rate over every key held
MIN_PRIOR = 10          # prior releases of the type before a regime is named
MAX_LAGS = 500          # lags kept per key (oldest dropped)
MAX_PROCESSED = 20000   # processed event ids kept (oldest dropped; far older than any re-read)
CHARTS = (("M1", 1), ("M5", 5), ("M15", 15), ("H1", 60))


def load_mid(symbol: str, start: pd.Timestamp, end: pd.Timestamp,
             ticks_root: Path | None = None) -> pd.Series:
    """The symbol's mid quote, true-UTC indexed, over [start, end]. Empty when unheld."""
    from libs.regime.session_clock import server_to_utc
    root = (ticks_root or TICKS) / symbol
    parts = []
    # the broker clock runs ahead of UTC, so a UTC window can sit in the next broker day file
    for day in pd.date_range((start - pd.Timedelta(hours=12)).normalize(),
                             (end + pd.Timedelta(hours=12)).normalize(), freq="D"):
        p = root / f"{day.date().isoformat()}.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if "time_msc" in df.columns:
            ts = pd.to_datetime(df["time_msc"], unit="ms")
        elif "ts" in df.columns:
            ts = pd.to_datetime(df["ts"])
        else:
            continue
        bid = pd.to_numeric(df.get("bid"), errors="coerce")
        ask = pd.to_numeric(df.get("ask"), errors="coerce")
        mid = ((bid + ask) / 2.0).where((bid > 0) & (ask > 0))
        utc = server_to_utc(pd.DatetimeIndex(ts))
        parts.append(pd.Series(mid.to_numpy(), index=utc))
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s[(s.index >= start) & (s.index <= end)]


def first_passage(mid: pd.Series, t0: pd.Timestamp, k: float = K_SIGMA, pre_s: int = PRE_S,
                  post_s: int = POST_S) -> dict[str, Any] | None:
    """{first_move, sign, quote_move, sigma_1s} or None when the pre-event tape is too thin.

    sigma_1s is the std of 1-second log returns on the pre-event grid; the envelope at t seconds
    is k sigma_1s sqrt(t). Nothing after t0 informs the reference or sigma."""
    pre = mid[(mid.index >= t0 - pd.Timedelta(seconds=pre_s)) & (mid.index < t0)]
    post = mid[(mid.index >= t0) & (mid.index <= t0 + pd.Timedelta(seconds=post_s))]
    if len(pre) < MIN_PRE_TICKS or post.empty:
        return None
    grid = pre.resample("1s").last().ffill()
    r = np.log(grid).diff().dropna()
    sigma = float(r.std(ddof=0)) if len(r) > 10 else float("nan")
    if not np.isfinite(sigma) or sigma <= 0:
        return None
    ref = float(pre.iloc[-1])
    moved = post[post != ref]
    quote_move = moved.index[0] if len(moved) else None
    secs = np.maximum((post.index - t0).total_seconds().to_numpy(), 1.0)
    dev = np.log(post.to_numpy() / ref)
    hit = np.nonzero(np.abs(dev) > k * sigma * np.sqrt(secs))[0]
    if not len(hit):
        return {"first_move": None, "sign": 0, "quote_move": quote_move, "sigma_1s": sigma}
    i = int(hit[0])
    return {"first_move": post.index[i], "sign": int(np.sign(dev[i])),
            "quote_move": quote_move, "sigma_1s": sigma}


def wilson_lb(k: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - a) / den)


def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial p-value against 1/2 (the leader is picked after looking)."""
    if n <= 0:
        return 1.0
    from scipy.stats import binomtest
    return float(binomtest(int(k), int(n), 0.5, alternative="two-sided").pvalue)


def bh_reject(pvals: dict[str, float], q: float = FDR_Q, m: int | None = None) -> set[str]:
    """Benjamini-Hochberg: the keys rejected at FDR q, with m >= len(pvals) tests charged."""
    if not pvals:
        return set()
    m_ = max(int(m or 0), len(pvals))
    ranked = sorted(pvals.items(), key=lambda kv: kv[1])
    cut = 0
    for i, (_k, p) in enumerate(ranked, start=1):
        if p <= q * i / m_:
            cut = i
    return {k for k, _p in ranked[:cut]}


def _bar_charts(symbol: str, root: Path | None = None) -> set[str]:
    d = root or UNIVERSE
    return {c for c, _m in CHARTS if (d / f"{symbol}_{c}.parquet").exists()}


def judge_lag(lag_s: float, leader: str, follower: str, root: Path | None = None
              ) -> tuple[str, int] | None:
    """The finest chart both instruments have bars on, and the lag in its bars (>= 1)."""
    both = _bar_charts(leader, root) & _bar_charts(follower, root)
    for chart, minutes in CHARTS:
        if chart in both:
            bars = int(round(lag_s / (60.0 * minutes)))
            if 1 <= bars <= 168:
                return chart, bars
    return None


class AtlasRun:
    """One hourly pass: new events -> moves -> lags -> edges -> donations + report."""

    def __init__(self, state: dict[str, Any] | None = None):
        st = state or {}
        self.processed: list[str] = list(st.get("processed") or [])
        self._processed_set = set(self.processed)
        self.lags: dict[str, list[list[float]]] = {k: list(v) for k, v in
                                                   (st.get("lags") or {}).items()}
        self.pre_sigma: dict[str, list[float]] = {k: list(v) for k, v in
                                                  (st.get("pre_sigma") or {}).items()}
        self.donated: dict[str, list[Any]] = dict(st.get("donated") or {})
        self.events_seen = 0
        self.unmeasured: dict[str, int] = {}

    def is_processed(self, eid: str) -> bool:
        return eid in self._processed_set

    def mark(self, eid: str) -> None:
        self.processed.append(eid)
        self._processed_set.add(eid)

    def state(self) -> dict[str, Any]:
        return {"processed": self.processed[-MAX_PROCESSED:], "lags": self.lags,
                "pre_sigma": self.pre_sigma, "donated": self.donated,
                "saved_at": datetime.now(UTC).isoformat()}

    def _regime(self, sym: str, event_type: str, sigma: float) -> str:
        key = f"{sym}|{event_type}"
        prior = self.pre_sigma.get(key) or []
        reg = "unknown" if len(prior) < MIN_PRIOR else (
            "stressed" if sigma > float(np.median(prior)) else "calm")
        self.pre_sigma.setdefault(key, []).append(sigma)
        self.pre_sigma[key] = self.pre_sigma[key][-MAX_LAGS:]
        return reg

    def record(self, event: dict[str, Any], moves: dict[str, dict[str, Any]]) -> None:
        """Signed lags for every pair that both passed, keyed on each member's own regime."""
        et = event["event_type"]
        regimes = {s: self._regime(s, et, float(m["sigma_1s"])) for s, m in sorted(moves.items())}
        syms = sorted(s for s, m in moves.items() if m.get("first_move") is not None)
        for i, a in enumerate(syms):
            for b in syms[i + 1:]:
                for mt, field_ in (("first_move", "first_move"), ("broker_quote", "quote_move")):
                    ta, tb = moves[a].get(field_), moves[b].get(field_)
                    if ta is None or tb is None:
                        continue
                    lag = (tb - ta).total_seconds()
                    agree = float(moves[a]["sign"] * moves[b]["sign"] > 0)
                    conds = ["all"] + [f"{s}={regimes[s]}" for s in (a, b)
                                       if regimes[s] != "unknown"]
                    for cond in conds:
                        rows = self.lags.setdefault(f"{a}|{b}|{et}|{mt}|{cond}", [])
                        rows.append([lag, agree])
                        del rows[:-MAX_LAGS]

    def edges(self) -> tuple[dict[str, LeadershipEdge], dict[str, float]]:
        """Every keyed lag set as an oriented edge, and every key's edge p-value.

        A regime-conditioned key survives as an edge only when the symbol it is conditioned on is
        the LEADER after orientation; its p-value is still counted (it was looked at)."""
        out: dict[str, LeadershipEdge] = {}
        pvals: dict[str, float] = {}
        now = datetime.now(UTC).isoformat()
        for key, rows in self.lags.items():
            a, b, et, mt, cond = key.split("|")
            arr = np.asarray(rows, dtype=float)
            lags, agree = arr[:, 0], arr[:, 1]
            nz_mask = lags != 0
            nz = lags[nz_mask]
            if not len(nz):
                pvals[key] = 1.0
                continue
            first = int((nz > 0).sum())
            if first < len(nz) - first:          # B moved first more often: B is the leader
                a, b, nz, first = b, a, -nz, len(nz) - first
            n_agree = int(agree[nz_mask].sum())
            p = max(binom_two_sided(first, len(nz)), binom_two_sided(n_agree, len(nz)))
            pvals[key] = p
            if cond == "all":
                reg = "all"
            else:
                sym, reg = cond.split("=", 1)
                if sym != a:
                    continue                      # conditioned on the follower: not this edge
            e = LeadershipEdge(
                leader=a, follower=b, event_type=et, regime=reg,
                lag_seconds=float(np.median(nz[nz > 0])) if first else 0.0,
                confidence=wilson_lb(first, len(nz)), sample_size=len(nz),
                last_updated=now, lead_consistency=first / len(nz),
                direction_agreement=n_agree / len(nz), wilson_lb=wilson_lb(first, len(nz)),
                median_lag_seconds=float(np.median(nz)))
            out[f"{a}|{b}|{et}|{mt}|{reg}"] = e
        return out, pvals


def run(*, budget_s: float = 240.0, calendar_root: Path | None = None,
        vintages_root: Path | None = None, ticks_root: Path | None = None,
        universe_root: Path | None = None, out_dir: Path | None = None,
        work_dir: Path | None = None, report_path: Path | None = None,
        watch: tuple[str, ...] | None = None, write: bool = True,
        cut_provider: Any = None) -> dict[str, Any]:
    t_end = time.monotonic() + budget_s
    campaign = (cut_provider or _campaign_cut)()
    if campaign is not None:
        campaign = pd.Timestamp(campaign)
        campaign = campaign.tz_localize("UTC") if campaign.tzinfo is None else campaign
    od = out_dir or LEAD_DIR
    wd = work_dir or WORK_DIR
    state_p, report_p = wd / STATE.name, report_path or REPORT
    try:
        st = json.loads(state_p.read_text("utf-8"))
    except (OSError, ValueError):
        st = {}
    ar = AtlasRun(st)
    syms = [s for s in (watch or WATCH)
            if (universe_root or UNIVERSE).joinpath(f"{s}_H1.parquet").exists()
            or ((ticks_root or TICKS) / s).exists()]
    tick_syms = [s for s in syms if ((ticks_root or TICKS) / s).exists()]
    cal_counts: dict[str, int] = {}
    evs = calendar_events(calendar_root, vintages_root or (
        Path(calendar_root) / "_no_vintages" if calendar_root else None), cal_counts)
    new = [e for e in evs if not ar.is_processed(f"{e['event_type']}|{e['time'].isoformat()}")]
    deferred = after_cut = 0
    for e in new:
        if time.monotonic() > t_end:
            deferred += 1
            continue
        t0: pd.Timestamp = e["time"]
        if t0 > pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=POST_S):
            continue                                       # its post window has not closed yet
        if campaign is None or (t0 + pd.Timedelta(seconds=POST_S) + pd.Timedelta(days=1)
                                >= campaign):
            after_cut += 1                                 # in (or unknown vs) the lockbox
            continue
        moves: dict[str, dict[str, Any]] = {}
        for s in tick_syms:
            mid = load_mid(s, t0 - pd.Timedelta(seconds=PRE_S), t0 + pd.Timedelta(seconds=POST_S),
                           ticks_root)
            fp = first_passage(mid, t0) if len(mid) else None
            if fp is None:
                ar.unmeasured[s] = ar.unmeasured.get(s, 0) + 1
                continue
            moves[s] = fp
        ar.record(e, moves)
        ar.mark(f"{e['event_type']}|{t0.isoformat()}")
        ar.events_seen += 1
    edges, pvals = ar.edges()
    m_total = len(ar.lags)
    rejected = bh_reject(pvals, FDR_Q, m_total)
    keys_by_type: dict[str, int] = {}
    for k in ar.lags:
        keys_by_type[k.split("|")[2]] = keys_by_type.get(k.split("|")[2], 0) + 1
    atlas = LeadershipAtlas()
    atlas.edges = {tuple(k.split("|")[:4]): v for k, v in edges.items() if k.endswith("|all")}
    donations, too_fast, unchanged, fdr_held = [], [], 0, 0
    for key, e in sorted(edges.items()) if campaign is not None else ():
        if e.sample_size < MIN_EVENTS or e.wilson_lb < MIN_WILSON:
            continue
        if abs(e.direction_agreement - 0.5) < MIN_AGREE_GAP or not np.isfinite(e.lag_seconds):
            continue
        src_keys = [k for k in pvals if _edge_key_matches(k, key)]
        if not any(k in rejected for k in src_keys):
            fdr_held += 1
            continue
        jl = judge_lag(e.lag_seconds, e.leader, e.follower, universe_root)
        if jl is None:
            too_fast.append(key)
            continue
        chart, bars = jl
        corr = 1.0 if e.direction_agreement > 0.5 else -1.0
        sig = [chart, bars, corr]
        if ar.donated.get(key) == sig:
            unchanged += 1
            continue
        ar.donated[key] = sig
        p_edge = min(pvals[k] for k in src_keys)
        donations.append({
            "kind": "anomaly", "family_hint": "release_lead_lag", "source": "leadership_atlas",
            "symbols": [e.follower], "against": e.leader, "horizon": bars, "chart": chart,
            "corr": corr, "condition": f"release_lead_lag_{e.leader}_{e.event_type}_lag{bars}",
            "event_type": e.event_type, "regime": e.regime, "n": e.sample_size,
            "lead_consistency": round(e.lead_consistency, 4),
            "wilson_lb": round(e.wilson_lb, 4),
            "direction_agreement": round(e.direction_agreement, 4),
            "median_lag_seconds": round(e.lag_seconds, 1),
            "p_value": p_edge, "fdr_q": FDR_Q, "tests_charged": m_total,
            "claim_family": f"leadership_atlas:{e.event_type}",
            "claim_selection_trials": int(keys_by_type.get(e.event_type, 0)),
            "mechanism": (f"{e.leader} moves first on {e.event_type} ({e.regime}): median "
                          f"{e.lag_seconds:.0f}s ahead of {e.follower}, first in "
                          f"{e.lead_consistency:.0%} of {e.sample_size} releases (Wilson LB "
                          f"{e.wilson_lb:.2f}), {e.follower} follows its direction in "
                          f"{e.direction_agreement:.0%}; survives Benjamini-Hochberg at "
                          f"q={FDR_Q} over {m_total} keys. Information reaches the leader's "
                          f"market first; the follower's quote catches up."),
            "falsifier": (f"lead share falls below 0.5 or the follower stops following the "
                          f"leader's sign over the next {MIN_EVENTS} {e.event_type} releases"),
            "found_at": datetime.now(UTC).isoformat()})
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "events_held": len(evs), "calendar_skipped": cal_counts,
           "events_new_this_pass": ar.events_seen,
           "events_deferred_budget": deferred, "events_at_or_after_campaign_cut": after_cut,
           "campaign_cut": None if campaign is None else campaign.isoformat(), "events_total_processed": len(ar.processed),
           "symbols_watched": syms, "symbols_with_ticks": tick_syms,
           "symbols_without_ticks": sorted(set(syms) - set(tick_syms)),
           "unmeasured_by_symbol": ar.unmeasured, "edges": len(edges),
           "keys_tested": m_total, "bh_rejected": len(rejected), "held_by_fdr": fdr_held,
           "edges_by_event_type": pd.Series([e.event_type for e in edges.values()],
                                            dtype=object).value_counts().to_dict(),
           "donated": len(donations), "unchanged_not_redonated": unchanged,
           "too_fast_for_held_charts": len(too_fast),
           "thresholds": {"min_events": MIN_EVENTS, "min_wilson": MIN_WILSON,
                          "min_agree_gap": MIN_AGREE_GAP, "k_sigma": K_SIGMA, "fdr_q": FDR_Q,
                          "min_prior": MIN_PRIOR},
           "state": ("UNMEASURED: no readable campaign lockbox cut (reports/LOCKBOX_CUT.json); "
                     "nothing processed or donated" if campaign is None else
                     "PRODUCING" if donations else
                     "UNMEASURED: no tick tape around any held release" if not tick_syms or
                     not ar.processed else "ACCRUING")}
    if write:
        wd.mkdir(parents=True, exist_ok=True)
        state_p.write_text(json.dumps(ar.state()), encoding="utf-8")
        if donations:
            od.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
            (od / f"discoveries_{stamp}.json").write_text(json.dumps(donations, indent=1),
                                                          encoding="utf-8")
        atlas_edges = {k: v.__dict__ for k, v in edges.items()}
        (wd / "leadership_atlas.json").write_text(
            json.dumps({"edges": atlas_edges, "saved_at": doc["generated_utc"]}, indent=1,
                       default=float), encoding="utf-8")
        try:
            build_leadership_matrix(atlas).to_csv(wd / "leadership_matrix.csv")
        except Exception as exc:  # noqa: BLE001 - the matrix is a view; the report says why
            doc["matrix_error"] = type(exc).__name__
        report_p.parent.mkdir(parents=True, exist_ok=True)
        report_p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def _campaign_cut() -> pd.Timestamp | None:
    try:
        from research.lockbox_cut import PUBLISHED, campaign_cut
        return campaign_cut(publish_to=PUBLISHED)
    except Exception:
        return None


def _edge_key_matches(raw: str, edge_key: str) -> bool:
    """True for the raw (unoriented) key an oriented edge key was built from."""
    a, b, et, mt, cond = raw.split("|")
    la, fo, et2, mt2, reg = edge_key.split("|")
    if (et, mt) != (et2, mt2) or {a, b} != {la, fo}:
        return False
    return (cond == "all" and reg == "all") or cond == f"{la}={reg}"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Leadership atlas: who moves first on each release")
    ap.add_argument("--budget-s", type=float, default=240.0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s)
    print(json.dumps({k: doc[k] for k in ("events_new_this_pass", "edges", "donated",
                                           "state")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
