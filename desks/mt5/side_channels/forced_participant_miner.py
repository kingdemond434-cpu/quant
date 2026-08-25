"""Forced Participant Miner — mines who has to trade even when they don't want to.

Who must transact:
- Index trackers / ETF APs
- Options dealers (delta hedging)
- Pensions (liability matching)
- CTAs (trend following rules)
- Volatility-control funds (target vol)
- Margin-liquidated accounts
- Corporate hedgers (FX exposure)
- Commodity producers (revenue hedging)
- Importers/exporters (FX needs)
- Month-end currency hedgers
- Central banks (policy implementation)
- Systematic risk parity (vol targeting)
- Futures roll participants

Maps constraint → observable proxy → timing → affected instruments →
expected forced flow → falsifier
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

FORCED_DIR = DATA_DIR / "forced_participants"
FORCED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ForcedParticipant:
    """A participant forced to trade by constraints."""
    name: str
    category: str                              # "index_tracker", "option_dealer", "pension", "CTA", etc.
    constraint: str                            # what forces them
    observable_proxy: str                      # how we detect their activity
    timing: dict                               # when they act
    affected_instruments: list[str]            # symbols affected
    forced_direction: str                      # "buy", "sell", "both", "delta_neutral"
    size_estimate: str                         # "large", "medium", "small", "unknown"
    falsifier: str                             # what would disprove
    metadata: dict = field(default_factory=dict)


@dataclass
class ForcedFlowSignal:
    """Signal from forced participant flow."""
    timestamp: datetime
    participant: str
    symbol: str
    expected_direction: int                    # +1 buy pressure, -1 sell pressure
    strength: float
    horizon: str                               # "intraday", "1d", "1w", "monthly"
    context: dict
    subsequent_outcome: dict | None = None


# Canonical forced participants
FORCED_PARTICIPANTS = [
    ForcedParticipant(
        name="SP500_Index_Trackers",
        category="index_tracker",
        constraint="must replicate SP500 weights exactly",
        observable_proxy="SP500 constituents volume surge at rebalance, MOC orders",
        timing={"frequency": "quarterly", "day": "3rd_friday", "window": "last_30min"},
        affected_instruments=["SP500_constituents", "SP500_futures", "SPY"],
        forced_direction="rebalance_weights",
        size_estimate="large",
        falsifier="No volume surge at rebalance, or weights tracked via sampling",
    ),
    ForcedParticipant(
        name="MSCI_ACWI_Rebalance",
        category="index_tracker",
        constraint="must match MSCI index changes on effective date",
        observable_proxy="ADR volume, emerging market FX flows, announcement-to-effective drift",
        timing={"frequency": "quarterly", "announce": "30_days_before", "effective": "quarter_end"},
        affected_instruments=["EM_equities", "EM_FX", "ADR"],
        forced_direction="rebalance",
        size_estimate="large",
        falsifier="No price drift between announce and effective",
    ),
    ForcedParticipant(
        name="ETF_AP_Gold",
        category="ETF_AP",
        constraint="must create/redeem GLD/IAU shares at NAV",
        observable_proxy="GLD premium/discount to NAV, gold lease rate, COMEX delivery",
        timing={"frequency": "daily", "nav_calc": "15:00_ET", "creation_unit": "100k_shares"},
        affected_instruments=["XAUUSD", "GLD", "IAU", "GC_futures"],
        forced_direction="arbitrage",
        size_estimate="medium",
        falsifier="GLD tracks NAV perfectly without creation/redemption",
    ),
    ForcedParticipant(
        name="Option_Dealer_Delta_Hedge",
        category="option_dealer",
        constraint="must delta-hedge option book continuously",
        observable_proxy="gamma exposure (GEX), open interest changes, pin risk at strikes",
        timing={"frequency": "continuous", "peak": "expiry_week", "session": "all"},
        affected_instruments=["underlying_equity", "index_futures", "VIX"],
        forced_direction="delta_neutral",
        size_estimate="large",
        falsifier="No price magnetism at major strikes near expiry",
    ),
    ForcedParticipant(
        name="CTA_Trend_Follow",
        category="CTA",
        constraint="systematic rules force position changes at trend breaks",
        observable_proxy="breakout levels, moving average crosses, volatility targeting",
        timing={"frequency": "continuous", "rebalance": "daily_EOD", "vol_target": "10-15%"},
        affected_instruments=["ALL_FUTURES", "FX", "commodities", "equity_indices"],
        forced_direction="trend",
        size_estimate="large",
        falsifier="No systematic flow at trend break levels",
    ),
    ForcedParticipant(
        name="Vol_Control_Fund",
        category="vol_control",
        constraint="must reduce leverage when vol spikes, increase when vol drops",
        observable_proxy="VIX term structure, equity vol, risk parity allocation shifts",
        timing={"frequency": "daily_EOD", "trigger": "vol_threshold_breach"},
        affected_instruments=["US500", "VIX_futures", "bonds", "gold"],
        forced_direction="delever_long_vol",
        size_estimate="medium",
        falsifier="No mechanical selling at vol thresholds",
    ),
    ForcedParticipant(
        name="Risk_Parity_Fund",
        category="risk_parity",
        constraint="equal risk allocation across asset classes",
        observable_proxy="bond/equity/commodity correlation shifts, leverage changes",
        timing={"frequency": "monthly_rebalance", "vol_window": "60d"},
        affected_instruments=["bonds", "equities", "commodities", "FX"],
        forced_direction="rebalance_to_target_vol",
        size_estimate="large",
        falsifier="No mechanical rebalancing at month-end",
    ),
    ForcedParticipant(
        name="Corporate_FX_Hedger",
        category="corporate_hedger",
        constraint="must hedge FX exposure per accounting rules",
        observable_proxy="month-end FX volume, WM/Reuters fix, quarter-end rebalancing",
        timing={"frequency": "monthly", "peak": "last_3_days", "window": "16:00_London"},
        affected_instruments=["ALL_FX", "EURUSD", "GBPUSD", "USDJPY"],
        forced_direction="hedge",
        size_estimate="medium",
        falsifier="No month-end FX patterns",
    ),
    ForcedParticipant(
        name="Commodity_Producer_Hedge",
        category="commodity_producer",
        constraint="must lock in revenue per budget/credit facility",
        observable_proxy="futures curve structure, producer hedging pressure, OI changes",
        timing={"frequency": "quarterly_budget", "rolling": "12m_forward"},
        affected_instruments=["USOIL", "XAUUSD", "XAGUSD", "COPPER", "CORN", "WHEAT"],
        forced_direction="sell_forward",
        size_estimate="medium",
        falsifier="No systematic selling pressure at budget dates",
    ),
    ForcedParticipant(
        name="Month_End_Pension_Hedger",
        category="pension",
        constraint="liability matching requires duration hedging at month-end",
        observable_proxy="long-bond demand, swap spreads, LDI flows",
        timing={"frequency": "monthly", "window": "last_5_days"},
        affected_instruments=["US30Y", "US10Y", "EU30Y", "UK30Y", "swaps"],
        forced_direction="receive_fixed",
        size_estimate="large",
        falsifier="No month-end bond rally pattern",
    ),
    ForcedParticipant(
        name="Central_Bank_Policy",
        category="central_bank",
        constraint="must implement policy rate, FX intervention, yield curve control",
        observable_proxy="policy rate changes, FX reserve changes, balance sheet operations",
        timing={"frequency": "scheduled_meetings", "unscheduled": "emergency"},
        affected_instruments=["DXY", "EURUSD", "USDJPY", "XAUUSD", "bonds"],
        forced_direction="policy",
        size_estimate="institutional",
        falsifier="No market reaction to policy surprises",
    ),
    ForcedParticipant(
        name="Futures_Roll_Participant",
        category="futures_roller",
        constraint="must roll positions before expiry to maintain exposure",
        observable_proxy="calendar spread volume, OI shift, term structure changes",
        timing={"frequency": "monthly_quarterly", "window": "5_days_before_expiry"},
        affected_instruments=["ALL_FUTURES", "CL", "GC", "ES", "NQ", "6E", "6J"],
        forced_direction="roll",
        size_estimate="large",
        falsifier="No calendar spread widening before roll",
    ),
    ForcedParticipant(
        name="Margin_Liquidation",
        category="margin_liquidation",
        constraint="forced close when equity < maintenance margin",
        observable_proxy="rapid price gaps, volume spikes, exchange margin calls",
        timing={"frequency": "stress_events", "trigger": "margin_breach"},
        affected_instruments=["ALL_LEVERAGED", "crypto", "futures", "CFDs"],
        forced_direction="sell",
        size_estimate="variable",
        falsifier="No gap-down volume spikes at support levels",
    ),
]


class ForcedParticipantAnalyzer:
    """Analyzes forced participant flows for alpha."""

    def __init__(self):
        self.participants = FORCED_PARTICIPANTS
        self.signals: list[ForcedFlowSignal] = []

    def get_participants_for_symbol(self, symbol: str) -> list[ForcedParticipant]:
        """Get forced participants affecting a symbol."""
        result = []
        for p in self.participants:
            if "ALL" in p.affected_instruments or symbol in p.affected_instruments:
                result.append(p)
            elif any(sym in str(p.affected_instruments) for sym in [symbol[:3], symbol[-3:]]):
                result.append(p)
        return result

    def generate_calendar_signals(self, start: datetime, end: datetime) -> list[ForcedFlowSignal]:
        """Generate forced flow signals from known calendar events."""
        signals = []

        for p in self.participants:
            # Generate expected activity periods
            freq = p.timing.get("frequency", "")
            if freq == "quarterly":
                # Quarterly events
                for q in [3, 6, 9, 12]:
                    # Approximate quarter end
                    year = start.year
                    while datetime(year, q, 1, tzinfo=UTC) < end:
                        event_date = datetime(year, q, 1, tzinfo=UTC) - timedelta(days=1)
                        if start <= event_date <= end:
                            # Rebalance window
                            for d in range(3):
                                sig_date = event_date - timedelta(days=d)
                                if start <= sig_date <= end:
                                    for sym in p.affected_instruments[:5]:
                                        if sym != "ALL":
                                            signals.append(ForcedFlowSignal(
                                                timestamp=sig_date,
                                                participant=p.name,
                                                symbol=sym,
                                                expected_direction=0,  # Rebalance = both directions
                                                strength=0.7,
                                                horizon="intraday",
                                                context={"event": f"{p.name}_rebalance", "days_to_event": d}
                                            ))
                        year += 1

            elif freq == "monthly":
                # Monthly events (month-end)
                current = start.replace(day=1)
                while current <= end:
                    month_end = (current + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    if start <= month_end <= end:
                        for d in range(5):
                            sig_date = month_end - timedelta(days=d)
                            if start <= sig_date <= end:
                                for sym in p.affected_instruments[:5]:
                                    if sym != "ALL":
                                        signals.append(ForcedFlowSignal(
                                            timestamp=sig_date,
                                            participant=p.name,
                                            symbol=sym,
                                            expected_direction=0,
                                            strength=0.6,
                                            horizon="intraday",
                                            context={"event": f"{p.name}_monthend", "days_to_end": d}
                                        ))
                    current = (current + timedelta(days=32)).replace(day=1)

            elif freq == "daily" and "nav_calc" in p.timing:
                # Daily NAV calculation (ETF APs)
                current = start
                while current <= end:
                    if current.weekday() < 5:  # Business days only
                        for sym in p.affected_instruments[:3]:
                            if sym != "ALL":
                                signals.append(ForcedFlowSignal(
                                    timestamp=current.replace(hour=19, minute=0),  # 15:00 ET = 19:00 UTC
                                    participant=p.name,
                                    symbol=sym,
                                    expected_direction=0,
                                    strength=0.5,
                                    horizon="1h",
                                    context={"event": "NAV_calculation"}
                                ))
                    current += timedelta(days=1)

        return signals

    def generate_option_expiry_signals(self, symbols: list[str],
                                        start: datetime, end: datetime) -> list[ForcedFlowSignal]:
        """Generate signals from option expiry pin risk."""
        signals = []
        # Monthly equity options expiry: 3rd Friday
        current = start
        while current <= end:
            # Find 3rd Friday
            first_friday = current.replace(day=1)
            while first_friday.weekday() != 4:
                first_friday += timedelta(days=1)
            third_friday = first_friday + timedelta(days=14)

            if start <= third_friday <= end:
                # Expiry week: pin risk
                for d in range(5):  # Mon-Fri of expiry week
                    exp_date = third_friday - timedelta(days=4) + timedelta(days=d)
                    if start <= exp_date <= end:
                        for sym in symbols:
                            if "US500" in sym or "SPY" in sym or "USTEC" in sym:
                                signals.append(ForcedFlowSignal(
                                    timestamp=exp_date.replace(hour=15, minute=0),
                                    participant="Option_Dealer_Delta_Hedge",
                                    symbol=sym,
                                    expected_direction=0,  # Pin risk = magnet to strike
                                    strength=0.8,
                                    horizon="intraday",
                                    context={"event": "monthly_equity_expiry", "day_of_week": d}
                                ))
            current = (current + timedelta(days=32)).replace(day=1)

        return signals

    def generate_futures_roll_signals(self, symbols: list[str],
                                       start: datetime, end: datetime) -> list[ForcedFlowSignal]:
        """Generate signals from futures roll."""
        signals = []
        # Monthly/quarterly rolls
        current = start
        while current <= end:
            # Assume roll week = week of 3rd Friday for quarterly
            first_friday = current.replace(day=1)
            while first_friday.weekday() != 4:
                first_friday += timedelta(days=1)
            third_friday = first_friday + timedelta(days=14)

            roll_start = third_friday - timedelta(days=7)
            if start <= roll_start <= end:
                for d in range(5):
                    roll_date = roll_start + timedelta(days=d)
                    if start <= roll_date <= end:
                        for sym in symbols:
                            if sym in ["USOIL", "XAUUSD", "XAGUSD", "US500", "US30", "USTEC"]:
                                signals.append(ForcedFlowSignal(
                                    timestamp=roll_date.replace(hour=13, minute=30),
                                    participant="Futures_Roll_Participant",
                                    symbol=sym,
                                    expected_direction=0,  # Roll = simultaneous buy/sell
                                    strength=0.8,
                                    horizon="1d",
                                    context={"event": "futures_roll", "days_to_expiry": 7-d}
                                ))
            current = (current + timedelta(days=32)).replace(day=1)

        return signals

    def record_outcome(self, signal: ForcedFlowSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 10) -> list[SideChannelHypothesis]:
        """Generate hypotheses from forced participant signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.participant}_{s.symbol}"
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
                    axis=SideChannelAxis.FLOW,
                    source="forced_participant_miner",
                    mechanism=f"Forced flow: {example.participant} on {example.symbol}. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} occurrences. "
                              f"Constraint: {[p.constraint for p in self.participants if p.name == example.participant][0]}",
                    symbols=[example.symbol],
                    timing={
                        "participant": example.participant,
                        "horizon": example.horizon,
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.horizon,
                    capacity_estimate="institutional" if "large" in [p.size_estimate for p in self.participants if p.name == example.participant][0] else "small",
                    metadata={
                        "participant": example.participant,
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
        with open(FORCED_DIR / "participants.json", "w") as f:
            json.dump([{
                "name": p.name,
                "category": p.category,
                "constraint": p.constraint,
                "observable_proxy": p.observable_proxy,
                "timing": p.timing,
                "instruments": p.affected_instruments,
                "direction": p.forced_direction,
                "size": p.size_estimate,
                "falsifier": p.falsifier,
            } for p in self.participants], f, indent=2)

        with open(FORCED_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "participant": s.participant,
                "symbol": s.symbol,
                "direction": s.expected_direction,
                "strength": s.strength,
                "horizon": s.horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    analyzer = ForcedParticipantAnalyzer()

    # Generate calendar signals for next 30 days
    start = datetime.now(UTC)
    end = start + timedelta(days=30)
    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "US500", "US30", "USTEC", "USOIL"]

    cal_signals = analyzer.generate_calendar_signals(start, end)
    opt_signals = analyzer.generate_option_expiry_signals(symbols, start, end)
    roll_signals = analyzer.generate_futures_roll_signals(symbols, start, end)

    analyzer.signals = cal_signals + opt_signals + roll_signals
    print(f"Generated {len(analyzer.signals)} forced participant signals")

    # Print calendar
    for s in sorted(analyzer.signals, key=lambda x: x.timestamp)[:20]:
        print(f"  {s.timestamp}: {s.participant} -> {s.symbol} ({s.horizon})")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} forced participant hypotheses")