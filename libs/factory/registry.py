"""Factory governance: dataset registry, edge-family targets, Sharpe milestones, paid-data ranking.

This is the *information-advantage* ledger that turns the sleeve/portfolio machinery into a
continuously-evolving research org. It does NOT rebuild research; it scores and prioritizes.
All scores are honest explicit estimates (0..1 unless noted), not fabricated precision -- they
drive "what to research next", not deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- edge families (breadth target)
# A mature factory has >= TARGET_PER_FAMILY independent sleeves in each family.
TARGET_PER_FAMILY = 3
EDGE_FAMILIES = (
    "trend", "momentum", "carry", "positioning", "macro",
    "relative_value", "volatility", "seasonality", "flow", "structural",
)

# Map existing sleeve names -> family (used to measure breadth from the portfolio report).
SLEEVE_FAMILY = {
    "trend_all": "trend", "crypto_trend": "trend", "index_trend": "trend",
    "xsec_mom_all": "momentum", "metals_mom": "momentum", "fx_mom": "momentum",
    "gold_silver_rv": "relative_value", "gold_plat_rv": "relative_value",
    "wti_brent_rv": "relative_value",
    "cot_positioning": "positioning", "cot_timeseries": "positioning",
    "swap_carry": "carry", "macro_calendar": "seasonality",
    "gold_crisis_hedge": "macro",
    # ETF sleeves (free expansion) fill the previously-empty macro/structural/flow families
    "rates_trend": "macro", "curve_rv": "structural", "credit_rv": "structural",
    "sector_rotation": "flow",
}

# Portfolio Sharpe milestones the factory drives toward.
MILESTONES = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


@dataclass(frozen=True)
class Dataset:
    name: str
    source: str
    frequency: str
    cost: str                      # "free" | "low" | "med" | "high"
    pit: bool                      # point-in-time reconstructable (no look-ahead risk)
    status: str                    # "in_use" | "reachable" | "blocked" | "candidate"
    families: tuple[str, ...]      # edge families it could unlock
    exp_alpha: float               # 0..1 expected standalone edge strength
    exp_diversification: float     # 0..1 orthogonality to current book
    impl_difficulty: float         # 0..1 (1 = hard)
    notes: str = ""

    def roi(self) -> float:
        """Expected portfolio ROI = (impact x orthogonality) discounted by cost & difficulty."""
        cost_pen = {"free": 1.0, "low": 0.85, "med": 0.6, "high": 0.35}.get(self.cost, 0.5)
        return round(self.exp_alpha * (0.4 + 0.6 * self.exp_diversification)
                     * cost_pen * (1.0 - 0.5 * self.impl_difficulty), 3)


# Curated dataset registry: what we use, what's reachable, what's blocked, and the paid path.
DATASETS: tuple[Dataset, ...] = (
    Dataset("MT5 OHLC (30 instruments)", "IC Markets MT5", "D1", "free", True, "in_use",
            ("trend", "momentum", "relative_value", "seasonality"), 0.55, 0.2, 0.2,
            "core price lake; trend/momentum already mined to ~0.6 ceiling"),
    Dataset("CFTC Commitments of Traders", "publicreporting.cftc.gov", "weekly", "free", True,
            "in_use", ("positioning",), 0.35, 0.7, 0.3, "orthogonal but weak standalone (~0.1)"),
    Dataset("Broker swap rates", "MT5 symbol_info", "daily", "free", False, "in_use",
            ("carry",), 0.45, 0.75, 0.4, "no history -> forward-only; the live carry hope"),
    Dataset("Binance funding/OI", "Binance fapi", "8h", "free", True, "in_use",
            ("carry", "flow"), 0.8, 0.6, 0.3, "best edge (0.96) but NOT MT5-executable (cashflow)"),
    Dataset("US Treasury par yields", "home.treasury.gov", "daily", "free", True, "reachable",
            ("carry", "macro"), 0.4, 0.6, 0.4, "rates curve; SSL-blocked here, retry path"),
    Dataset("ECB / central-bank rates", "data-api.ecb.europa.eu", "daily", "free", True,
            "reachable", ("carry", "macro"), 0.45, 0.65, 0.5, "EUR reachable; FX carry"),
    Dataset("FRED macro series", "api.stlouisfed.org", "daily", "free", True, "reachable",
            ("macro", "carry"), 0.5, 0.7, 0.4,
            "collector wired 2026-07-16 (api host OK from VPS); key pending (operator)"),
    # ---- FREE expansion candidates (no budget): the real remaining levers ----
    Dataset("MT5 ETF CFDs (TLT/IEF/SHY/LQD/EMB + sectors)", "IC Markets MT5", "D1", "free", True,
            "in_use", ("trend", "macro", "structural", "flow"), 0.15, 0.7, 0.3,
            "ingested; sleeves DON'T clear -- price-only CFD (dividend drag) corrupts bond ETF "
            "trend (-1.2); sector/curve/credit ~0. Tested, mostly rejected."),
    Dataset("MT5 cold indices (NAS100/GER40/JPN225/EU50/HK50)", "IC Markets MT5", "D1", "free",
            True, "candidate", ("trend", "momentum", "seasonality"), 0.4, 0.4, 0.2,
            "more index breadth for rotation + cross-sectional; warm the terminal then ingest"),
    Dataset("CFTC disaggregated / TFF", "publicreporting.cftc.gov", "weekly", "free", True,
            "candidate", ("positioning",), 0.35, 0.7, 0.4,
            "managed-money / leveraged-funds split: cleaner than legacy non-comm"),
    Dataset("Price-derived seasonality", "(from MT5 lake)", "D1", "free", True, "candidate",
            ("seasonality",), 0.25, 0.55, 0.2,
            "turn-of-month done (~0.1); day-of-week / pre-holiday / month effects untested"),
)


def free_next_priorities(top_n: int = 6) -> list[dict[str, object]]:
    """Free/reachable datasets ranked by expected portfolio ROI (the only path -- no budget)."""
    free = [d for d in DATASETS if d.cost == "free" and d.status in {"candidate", "reachable"}]
    ranked = sorted(free, key=lambda d: d.roi(), reverse=True)
    return [{"name": d.name, "status": d.status, "families": list(d.families), "roi": d.roi(),
             "pit": d.pit, "notes": d.notes} for d in ranked[:top_n]]

# Paid datasets ranked by expected portfolio-Sharpe contribution. DEFERRED: no budget -> the factory
# only recommends these once the free path is 100% exhausted. Kept for honest completeness.
@dataclass(frozen=True)
class PaidDataset:
    name: str
    source: str
    cost_usd_per_month: str
    families: tuple[str, ...]
    exp_sharpe_contribution: float   # expected ADD to portfolio Sharpe if it works
    confidence: float                # 0..1
    impl_difficulty: float           # 0..1
    rationale: str = ""

    def priority(self) -> float:
        return round(self.exp_sharpe_contribution * self.confidence
                     * (1.0 - 0.4 * self.impl_difficulty), 3)


PAID_DATASETS: tuple[PaidDataset, ...] = (
    PaidDataset("Futures continuous + term structure", "Nasdaq Data Link (Quandl)", "$50-100",
                ("carry", "structural"), 0.30, 0.6, 0.4,
                "roll-yield carry: real, uncorrelated to trend; MT5-tradeable legs"),
    PaidDataset("Options IV / vol surface", "ORATS / CBOE DataShop", "$100-300",
                ("volatility",), 0.35, 0.55, 0.7,
                "vol-risk-premium: highest premium, but MT5 can't trade options directly"),
    PaidDataset("Economic surprise / calendar (actual vs survey)", "Econoday / TradingEconomics",
                "$50-150", ("macro",), 0.20, 0.5, 0.4,
                "macro-surprise event drift on FX/indices/gold; genuinely orthogonal"),
    PaidDataset("ETF / fund flows", "State Street / ETF.com Pro", "$100-500", ("flow",), 0.20, 0.4,
                0.6, "flow-driven index/sector rotation; capacity-rich but noisy"),
    PaidDataset("Cross-exchange crypto basis/funding history", "Kaiko / Amberdata", "$100-500",
                ("carry", "flow"), 0.25, 0.5, 0.5,
                "deeper funding/basis history to harden the carry sleeve before live"),
)


@dataclass
class MilestoneStatus:
    current: float
    next_milestone: float | None
    gap: float
    families_complete: int
    families_total: int = len(EDGE_FAMILIES)
    bottleneck: str = ""
    notes: list[str] = field(default_factory=list)


def milestone_path(current_sharpe: float, family_counts: dict[str, int]) -> MilestoneStatus:
    nxt = next((m for m in MILESTONES if m > current_sharpe + 1e-9), None)
    complete = sum(1 for f in EDGE_FAMILIES if family_counts.get(f, 0) >= TARGET_PER_FAMILY)
    # the bottleneck family = the one most under target that is also genuinely orthogonal
    deficits = {f: TARGET_PER_FAMILY - family_counts.get(f, 0) for f in EDGE_FAMILIES}
    bottleneck = max(deficits, key=lambda f: deficits[f]) if deficits else ""
    return MilestoneStatus(
        current=round(current_sharpe, 3),
        next_milestone=nxt, gap=round((nxt - current_sharpe), 3) if nxt else 0.0,
        families_complete=complete, bottleneck=bottleneck,
    )


def best_dataset_priorities(top_n: int = 5) -> list[dict[str, object]]:
    ranked = sorted(DATASETS, key=lambda d: d.roi(), reverse=True)
    return [{"name": d.name, "cost": d.cost, "status": d.status, "families": list(d.families),
             "roi": d.roi(), "pit": d.pit, "notes": d.notes} for d in ranked[:top_n]]


def information_advantage_score(
    *, datasets_in_use: int, mechanisms: int, active_sleeves: int, validated_sleeves: int,
    orthogonal_sleeves: int, archive_days: int,
) -> dict[str, object]:
    """Composite information-advantage score -- progress even when no deployable edge exists yet.

    Rewards breadth (datasets/mechanisms), depth (forward archive days), and -- most -- the count of
    genuinely ORTHOGONAL validated sleeves (the scarce resource). Unitless, monotonic; track it up.
    """
    breadth = datasets_in_use * 1.0 + mechanisms * 1.5
    depth = min(archive_days / 30.0, 12.0)                # forward archive maturity (capped ~1yr)
    sleeves = active_sleeves * 0.5 + validated_sleeves * 2.0 + orthogonal_sleeves * 3.0
    score = round(breadth + depth + sleeves, 1)
    return {"score": score, "breadth": round(breadth, 1), "depth": round(depth, 1),
            "sleeve_value": round(sleeves, 1), "datasets_in_use": datasets_in_use,
            "mechanisms": mechanisms, "active_sleeves": active_sleeves,
            "validated_sleeves": validated_sleeves, "orthogonal_sleeves": orthogonal_sleeves,
            "archive_days": archive_days}


def paid_data_path(top_n: int = 5) -> list[dict[str, object]]:
    ranked = sorted(PAID_DATASETS, key=lambda d: d.priority(), reverse=True)
    return [{"name": d.name, "source": d.source, "cost": d.cost_usd_per_month,
             "families": list(d.families), "exp_sharpe_add": d.exp_sharpe_contribution,
             "confidence": d.confidence, "priority": d.priority(), "rationale": d.rationale}
            for d in ranked[:top_n]]
