"""Operational Calendar Miner — hunts forced participant behavior around known deadlines.

Markets are surrounded by operational processes that force participants to transact:
- Settlement windows (T+1, T+2)
- Fixing windows (WM/Reuters, ECB, LIBOR/SOFR)
- Futures rolls (index, commodity, FX)
- Margin changes (CCP, broker)
- Broker swap changes
- Contract specification changes
- Index rebalance notices
- Exchange circulars
- Auction schedules (Treasury, central bank)
- Central bank liquidity operations
- ETF rebalance dates
- Pension rebalancing
- Commodity delivery dates
- Exchange holidays / half-days / local banking holidays
- Month-end / quarter-end accounting
- Quarter-end balance-sheet constraints
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

CAL_DIR = DATA_DIR / "operational_calendar"
CAL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class OperationalEvent:
    """A scheduled operational deadline that forces participant behavior."""
    name: str
    category: str                          # settlement, fixing, roll, margin, swap, index, auction, holiday, accounting
    frequency: str                         # daily, weekly, monthly, quarterly, annually, ad_hoc
    timing: dict                           # {"hour": 16, "minute": 0, "timezone": "UTC", "session": "ny_close"}
    affected_instruments: list[str]        # symbols or "ALL"
    forced_participants: list[str]         # "ETF_AP", "index_tracker", "pension", "dealer", "hedger", "CTA"
    forced_action: str                     # "buy", "sell", "rebalance", "roll", "hedge", "settle"
    urgency: str                           # "hard_deadline" | "soft_window" | "discretionary"
    lookback_days: int = 5                 # how many days before the deadline the edge activates
    metadata: dict = field(default_factory=dict)


# Canonical operational calendar — extendable
OPERATIONAL_EVENTS = [
    # FIXINGS
    OperationalEvent(
        name="WM_Reuters_4PM_London_Fix",
        category="fixing",
        frequency="daily",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "london_close"},
        affected_instruments=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "EURGBP", "EURCHF"],
        forced_participants=["corporate_hedger", "pension", "ETF_AP", "index_tracker"],
        forced_action="rebalance",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"window_minutes": 5, "benchmark": "WM/Reuters"}
    ),
    OperationalEvent(
        name="ECB_Fix_1_15PM_CET",
        category="fixing",
        frequency="daily",
        timing={"hour": 12, "minute": 15, "timezone": "UTC", "session": "london_am"},
        affected_instruments=["EURUSD", "EURJPY", "EURGBP", "EURCHF", "EURAUD", "EURCAD"],
        forced_participants=["corporate_hedger", "ECB_counterparty"],
        forced_action="settle",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"benchmark": "ECB"}
    ),
    OperationalEvent(
        name="SOFR_LIBOR_Transition_Fix",
        category="fixing",
        frequency="daily",
        timing={"hour": 11, "minute": 0, "timezone": "UTC", "session": "ny_open"},
        affected_instruments=["USDJPY", "USDCHF", "USDCAD", "XAUUSD", "XAGUSD"],
        forced_participants=["dealer", "bank", "CCP"],
        forced_action="hedge",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"benchmark": "SOFR/LIBOR fallback"}
    ),

    # FUTURES ROLLS
    OperationalEvent(
        name="Equity_Index_Futures_Roll",
        category="roll",
        frequency="quarterly",
        timing={"hour": 13, "minute": 30, "timezone": "UTC", "session": "ny_open"},
        affected_instruments=["US500", "US30", "USTEC", "DE40", "UK100", "JP225", "HK50"],
        forced_participants=["CTA", "risk_parity", "ETF_AP", "index_tracker"],
        forced_action="roll",
        urgency="hard_deadline",
        lookback_days=7,
        metadata={"roll_week": "third_friday", "months": [3, 6, 9, 12]}
    ),
    OperationalEvent(
        name="Gold_Futures_Roll",
        category="roll",
        frequency="monthly",
        timing={"hour": 18, "minute": 30, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["XAUUSD", "XAGUSD", "GC_futures"],
        forced_participants=["producer", "ETF_AP", "CTA"],
        forced_action="roll",
        urgency="hard_deadline",
        lookback_days=5,
        metadata={"roll_day": "last_business_day_before_25th"}
    ),
    OperationalEvent(
        name="Oil_Futures_Roll",
        category="roll",
        frequency="monthly",
        timing={"hour": 17, "minute": 30, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["USOIL", "UKOIL", "XNGUSD"],
        forced_participants=["producer", "refiner", "ETF_AP", "CTA"],
        forced_action="roll",
        urgency="hard_deadline",
        lookback_days=7,
        metadata={"roll_day": "3rd_business_day_before_25th"}
    ),
    OperationalEvent(
        name="FX_Futures_Roll_CME",
        category="roll",
        frequency="quarterly",
        timing={"hour": 13, "minute": 30, "timezone": "UTC", "session": "ny_open"},
        affected_instruments=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD"],
        forced_participants=["CTA", "corporate_hedger", "bank"],
        forced_action="roll",
        urgency="hard_deadline",
        lookback_days=5,
        metadata={"roll_week": "third_friday", "months": [3, 6, 9, 12]}
    ),

    # SETTLEMENT
    OperationalEvent(
        name="T1_Settlement_Equities",
        category="settlement",
        frequency="daily",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["US500", "US30", "USTEC", "EU50", "UK100", "JP225"],
        forced_participants=["custodian", "broker", "ETF_AP"],
        forced_action="settle",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"cycle": "T+1"}
    ),
    OperationalEvent(
        name="T2_Settlement_FX",
        category="settlement",
        frequency="daily",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["ALL_FX"],
        forced_participants=["bank", "corporate_hedger", "CCP"],
        forced_action="settle",
        urgency="hard_deadline",
        lookback_days=2,
        metadata={"cycle": "T+2"}
    ),

    # MARGIN CHANGES
    OperationalEvent(
        name="CCP_Margin_Review",
        category="margin",
        frequency="monthly",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["ALL"],
        forced_participants=["CTA", "dealer", "hedge_fund"],
        forced_action="reduce_risk",
        urgency="soft_window",
        lookback_days=10,
        metadata={"review_day": "1st_business_day"}
    ),

    # BROKER SWAP CHANGES
    OperationalEvent(
        name="Broker_Swap_Update",
        category="swap",
        frequency="daily",
        timing={"hour": 22, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["ALL_FX", "XAUUSD", "XAGUSD", "USOIL", "US500"],
        forced_participants=["carry_trader", "swing_trader"],
        forced_action="adjust_position",
        urgency="soft_window",
        lookback_days=1,
        metadata={"triple_swap_wednesday": True}
    ),

    # INDEX REBALANCES
    OperationalEvent(
        name="SP500_Quarterly_Rebalance",
        category="index",
        frequency="quarterly",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["US500", "US30", "USTEC", "constituents"],
        forced_participants=["ETF_AP", "index_tracker", "pension"],
        forced_action="rebalance",
        urgency="hard_deadline",
        lookback_days=10,
        metadata={"rebalance_friday": "3rd_friday", "months": [3, 6, 9, 12]}
    ),
    OperationalEvent(
        name="MSCI_Quarterly_Review",
        category="index",
        frequency="quarterly",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["GLOBAL_EQUITIES"],
        forced_participants=["ETF_AP", "index_tracker", "pension", "sovereign_wealth"],
        forced_action="rebalance",
        urgency="hard_deadline",
        lookback_days=30,
        metadata={"announce_lead_time": "30_days", "effective": "quarter_end"}
    ),
    OperationalEvent(
        name="FTSE_Russell_Rebalance",
        category="index",
        frequency="quarterly",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["US_SMALL_CAP", "UK100", "EU_SMALL_CAP"],
        forced_participants=["ETF_AP", "index_tracker"],
        forced_action="rebalance",
        urgency="hard_deadline",
        lookback_days=10,
        metadata={"rebalance_friday": "last_friday", "months": [3, 6, 9, 12]}
    ),

    # TREASURY AUCTIONS
    OperationalEvent(
        name="US_Treasury_Auction_Cycle",
        category="auction",
        frequency="weekly",
        timing={"hour": 17, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["US10Y", "US30Y", "US2Y", "US5Y", "DXY", "XAUUSD", "USDJPY"],
        forced_participants=["primary_dealer", "foreign_official", "pension", "bank"],
        forced_action="position_for_auction",
        urgency="hard_deadline",
        lookback_days=3,
        metadata={"schedule": "published_monthly", "bill_weekly": "weekly", "note_monthly": "monthly", "bond_monthly": "monthly"}
    ),

    # CENTRAL BANK OPERATIONS
    OperationalEvent(
        name="Fed_Reverse_Repo_Operation",
        category="liquidity_op",
        frequency="daily",
        timing={"hour": 15, "minute": 30, "timezone": "UTC", "session": "ny_open"},
        affected_instruments=["DXY", "US10Y", "XAUUSD", "US500"],
        forced_participants=["money_fund", "bank", "dealer"],
        forced_action="park_cash",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"operation_time": "11:30_ET", "results": "11:45_ET"}
    ),
    OperationalEvent(
        name="ECB_MRO_LTRO",
        category="liquidity_op",
        frequency="weekly",
        timing={"hour": 9, "minute": 45, "timezone": "UTC", "session": "london_am"},
        affected_instruments=["EURUSD", "EU50", "DE10Y", "FR10Y"],
        forced_participants=["bank", "dealer"],
        forced_action="borrow_liquidity",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"operation": "MRO_tuesday", "LTRO_quarterly": "quarterly"}
    ),

    # HOLIDAYS / HALF-DAYS
    OperationalEvent(
        name="US_Market_Holiday",
        category="holiday",
        frequency="ad_hoc",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "closed"},
        affected_instruments=["ALL_US", "US500", "US30", "USTEC", "XAUUSD", "USOIL", "DXY"],
        forced_participants=["all"],
        forced_action="reduced_liquidity",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"source": "NYSE_NASDAQ_calendar"}
    ),
    OperationalEvent(
        name="US_Half_Day_Thanksgiving_Christmas_Eve",
        category="holiday",
        frequency="annually",
        timing={"hour": 18, "minute": 0, "timezone": "UTC", "session": "early_close"},
        affected_instruments=["ALL_US"],
        forced_participants=["all"],
        forced_action="early_close_liquidity_drain",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"close_time": "13:00_ET"}
    ),
    OperationalEvent(
        name="London_Holiday",
        category="holiday",
        frequency="ad_hoc",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "closed"},
        affected_instruments=["ALL_EUR", "ALL_GBP", "FTSE100", "EU50", "XAUUSD"],
        forced_participants=["all"],
        forced_action="reduced_liquidity",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"source": "LSE_calendar"}
    ),
    OperationalEvent(
        name="Tokyo_Holiday",
        category="holiday",
        frequency="ad_hoc",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "closed"},
        affected_instruments=["ALL_JPY", "JP225", "USDJPY", "EURJPY", "XAUUSD"],
        forced_participants=["all"],
        forced_action="reduced_liquidity",
        urgency="hard_deadline",
        lookback_days=1,
        metadata={"source": "TSE_calendar", "golden_week": "late_apr_early_may"}
    ),

    # MONTH-END / QUARTER-END
    OperationalEvent(
        name="Month_End_FX_Hedging",
        category="accounting",
        frequency="monthly",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "london_close"},
        affected_instruments=["ALL_FX", "XAUUSD"],
        forced_participants=["corporate_hedger", "pension", "sovereign_wealth", "ETF_AP"],
        forced_action="hedge_rebalance",
        urgency="hard_deadline",
        lookback_days=3,
        metadata={"window": "last_3_business_days", "peak": "last_day_16:00_London"}
    ),
    OperationalEvent(
        name="Quarter_End_Balance_Sheet",
        category="accounting",
        frequency="quarterly",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "london_close"},
        affected_instruments=["ALL", "DXY", "XAUUSD", "US10Y", "EU10Y", "JP10Y"],
        forced_participants=["bank", "dealer", "pension", "insurance", "sovereign_wealth"],
        forced_action="balance_sheet_management",
        urgency="hard_deadline",
        lookback_days=10,
        metadata={"window": "last_10_business_days", "peak": "quarter_end", "regulatory": "Basel_III_leverage_ratio"}
    ),
    OperationalEvent(
        name="Year_End_Tax_Loss_Harvesting",
        category="accounting",
        frequency="annually",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["US_EQUITIES", "HIGH_BETA", "LOSERS_YTD"],
        forced_participants=["retail", "taxable_account", "fund"],
        forced_action="tax_loss_sell",
        urgency="hard_deadline",
        lookback_days=15,
        metadata={"window": "dec_15_to_dec_31", "wash_sale_rule": "30_days"}
    ),

    # ETF REBALANCE
    OperationalEvent(
        name="GLD_IAU_Gold_ETF_Rebalance",
        category="index",
        frequency="daily",
        timing={"hour": 16, "minute": 0, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["XAUUSD", "GLD", "IAU"],
        forced_participants=["ETF_AP", "authorized_participant"],
        forced_action="creation_redemption",
        urgency="soft_window",
        lookback_days=1,
        metadata={"nav_calculation": "15:00_ET", "creation_unit": "100k_shares"}
    ),
    OperationalEvent(
        name="USO_Oil_ETF_Roll",
        category="roll",
        frequency="monthly",
        timing={"hour": 17, "minute": 30, "timezone": "UTC", "session": "ny_close"},
        affected_instruments=["USOIL", "USO", "BNO"],
        forced_participants=["ETF_AP", "authorized_participant"],
        forced_action="roll",
        urgency="hard_deadline",
        lookback_days=7,
        metadata={"roll_schedule": "published_monthly"}
    ),

    # COMMODITY DELIVERY
    OperationalEvent(
        name="Gold_Comex_Delivery_Notice",
        category="delivery",
        frequency="monthly",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["XAUUSD", "GC_futures"],
        forced_participants=["producer", "refiner", "ETF_AP", "dealer"],
        forced_action="delivery_or_roll",
        urgency="hard_deadline",
        lookback_days=10,
        metadata={"first_notice_day": "last_business_day_before_25th"}
    ),
    OperationalEvent(
        name="Oil_NYMEX_Delivery",
        category="delivery",
        frequency="monthly",
        timing={"hour": 0, "minute": 0, "timezone": "UTC", "session": "asia_open"},
        affected_instruments=["USOIL", "CL_futures"],
        forced_participants=["producer", "refiner", "storage_operator"],
        forced_action="delivery_or_roll",
        urgency="hard_deadline",
        lookback_days=10,
        metadata={"first_notice_day": "varies_by_contract"}
    ),
]


def get_events_for_symbol(symbol: str) -> list[OperationalEvent]:
    """Get all operational events affecting a symbol."""
    out = []
    for ev in OPERATIONAL_EVENTS:
        if "ALL" in ev.affected_instruments or symbol in ev.affected_instruments:
            out.append(ev)
        elif symbol.replace("USD", "") in str(ev.affected_instruments):
            out.append(ev)
    return out


def get_events_in_window(start: datetime, end: datetime) -> list[OperationalEvent]:
    """Get events occurring in a time window (approximate by next occurrence)."""
    out = []
    for ev in OPERATIONAL_EVENTS:
        # Simplified: check if event frequency matches window
        next_occurrence = _next_occurrence(ev, start)
        if start <= next_occurrence <= end:
            out.append(ev)
    return out


def _next_occurrence(ev: OperationalEvent, after: datetime) -> datetime:
    """Estimate next occurrence of an operational event."""
    # Simplified implementation — in production use actual calendars
    if ev.frequency == "daily":
        return after.replace(hour=ev.timing["hour"], minute=ev.timing["minute"], second=0, microsecond=0)
    elif ev.frequency == "weekly":
        # Assume Tuesday for weekly
        days_ahead = (1 - after.weekday()) % 7
        return after + timedelta(days=days_ahead)
    elif ev.frequency == "monthly":
        # Assume month-end
        next_month = after.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=1) - timedelta(days=1)
    elif ev.frequency == "quarterly":
        next_q = ((after.month - 1) // 3 + 1) * 3 + 1
        year = after.year + (next_q // 13)
        month = ((next_q - 1) % 12) + 1
        return datetime(year, month, 1, tzinfo=UTC) - timedelta(days=1)
    elif ev.frequency == "annually":
        return datetime(after.year, 12, 31, tzinfo=UTC)
    else:
        return after + timedelta(days=365)  # ad_hoc fallback


def generate_hypotheses_from_calendar(symbols: list[str] | None = None) -> list[SideChannelHypothesis]:
    """Generate side-channel hypotheses from operational calendar."""
    if symbols is None:
        symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
                   "US500", "US30", "USTEC", "USOIL", "UKOIL", "XAGUSD"]

    hypotheses = []

    for symbol in symbols:
        events = get_events_for_symbol(symbol)
        for ev in events:
            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.SEASONALITY,
                source="operational_calendar",
                mechanism=f"{ev.forced_action} forced by {ev.category}: {ev.name} "
                          f"({ev.forced_participants} must {ev.forced_action} at {ev.timing})",
                symbols=[symbol],
                timing={
                    "category": ev.category,
                    "frequency": ev.frequency,
                    "hour_utc": ev.timing["hour"],
                    "minute_utc": ev.timing["minute"],
                    "session": ev.timing.get("session", "unknown"),
                    "lookback_days": ev.lookback_days,
                    "urgency": ev.urgency,
                },
                falsifier=f"No {ev.forced_action} pressure observed in {ev.lookback_days}d before {ev.name} "
                          f"for {symbol} across 20+ occurrences",
                expected_horizon="session_to_1d",
                capacity_estimate="small" if "ALL" not in str(ev.affected_instruments) else "micro",
                metadata={
                    "operational_event": ev.name,
                    "category": ev.category,
                    "forced_participants": ev.forced_participants,
                    "forced_action": ev.forced_action,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

    return hypotheses


def build_operational_calendar_dataframe() -> pd.DataFrame:
    """Build a DataFrame of all operational events for analysis."""
    rows = []
    for ev in OPERATIONAL_EVENTS:
        rows.append({
            "name": ev.name,
            "category": ev.category,
            "frequency": ev.frequency,
            "hour_utc": ev.timing.get("hour"),
            "minute_utc": ev.timing.get("minute"),
            "session": ev.timing.get("session"),
            "instruments": ",".join(ev.affected_instruments),
            "forced_participants": ",".join(ev.forced_participants),
            "forced_action": ev.forced_action,
            "urgency": ev.urgency,
            "lookback_days": ev.lookback_days,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Generate hypotheses for all symbols
    hyps = generate_hypotheses_from_calendar()
    print(f"Generated {len(hyps)} operational calendar hypotheses")

    # Save calendar as CSV for analysis
    df = build_operational_calendar_dataframe()
    df.to_csv(CAL_DIR / "operational_calendar.csv", index=False)
    print(f"Saved calendar to {CAL_DIR}/operational_calendar.csv")

    # Research targets: empty mechanism-axis pairs
    from . import get_research_targets
    targets = get_research_targets()
    print(f"\nResearch targets (empty mechanism-axis cells): {len(targets)}")
    for mech, axis in targets[:20]:
        print(f"  {mech} x {axis.value}")