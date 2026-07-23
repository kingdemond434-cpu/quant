"""Crypto Parquet-lake -> autodiscovery factory adapter (industrialized hypothesis throughput).

Turns lake D1/H8 crypto bars into ``MarketSeries`` (with Level-3 perp ``funding`` attached) so the
generic :class:`AutoDiscoveryLab` can run the SAME validation gauntlet over the whole crypto
universe, net of real perp cost, with cross-campaign DSR deflation on the cumulative trial count.

Honesty: the ``funding_stress_reversal`` generator (LIQUIDITY family) is the one genuinely
crypto-native hypothesis here -- fading crowded perp leverage, economically distinct from the
funding *carry* the desk already harvests. The price-pattern families are EXPECTED to re-confirm
the graveyard (trend/momentum/mean-reversion over crypto majors already failed the gauntlet). That
is the honest point, not a defect: the store's content-hash dedup makes re-tests free after the
first cycle, and cumulative-trial DSR deflation makes a false survivor from breadth-mining
statistically harder, not easier. The factory's durable value is (1) the new funding-stress test,
(2) trial-count accounting across the universe, and (3) reusable infrastructure that auto-tests each
new free data axis (OI / LS / liquidations / stablecoin flows) as its forward clock matures.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import CycleResult, Family, MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.store.connection import Database

DataProvider = Callable[[str], MarketSeries | None]

_LAKE_ROOT = "data/lake"
_MIN_BARS = 250
# ~4 bps taker + slippage per side on a liquid perp; backtests are ALWAYS net of this.
COST_PER_SIDE = 5e-4
# Price patterns that fit crypto + LIQUIDITY (carries funding_stress_reversal). Crowded price-only
# families stay in to keep the trial count honest; the gauntlet, not omission, rejects them.
DEFAULT_FAMILIES: tuple[Family, ...] = (
    Family.LIQUIDITY,
    Family.MOMENTUM,
    Family.MEAN_REVERSION,
    Family.TREND,
    Family.VOLATILITY_EXPANSION,
    Family.VOLATILITY_COMPRESSION,
    Family.CROSS_ASSET,  # BTC-relative; ref_close populated below (no-lookahead)
)


def crypto_symbols(
    timeframe: Timeframe = Timeframe.D1, *, lake_root: str = _LAKE_ROOT
) -> list[str]:
    """Every crypto symbol with bars at ``timeframe`` in the lake (sorted, deterministic)."""
    root = Path(lake_root) / "bronze" / "crypto"
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if (d / timeframe.value).exists())


def _read_frames(symbols: Sequence[str], timeframe: Timeframe, lake_root: str) -> dict[str, Any]:
    """Read + cache each symbol's lake frame once (indexed by timestamp)."""
    lake = ParquetLake(lake_root)
    frames = {}
    for s in symbols:
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        frames[s] = lake.read_bars(Layer.BRONZE, s, timeframe).set_index("timestamp")
    return frames


def _provider_from_frames(frames: dict[str, Any], min_bars: int) -> DataProvider:
    # BTC is the cross-asset reference (feeds MarketSeries.ref_close -> the CROSS_ASSET generator).
    # NO-LOOKAHEAD: reindex BTC's close onto each symbol's bar index with PAST-ONLY ffill (a bar's
    # ref is BTC's contemporaneous close, gaps filled from the last KNOWN past close); net_returns
    # then applies lag-1, so the position never sees future data. Leading gaps (symbol older than
    # BTC -- effectively never) leave ref_close None so the generator honestly skips (zeros).
    btc = frames.get("BTCUSDT")
    btc_close = btc["close"] if btc is not None else None

    def provider(symbol: str) -> MarketSeries | None:
        df = frames.get(symbol)
        if df is None or len(df) < min_bars:
            return None
        funding = df["funding"].to_numpy("float64") if "funding" in df.columns else None
        ref_close = None
        if btc_close is not None and symbol != "BTCUSDT":
            ref = btc_close.reindex(df.index).ffill()
            if not ref.isna().any():
                ref_close = ref.to_numpy("float64")
        return MarketSeries(
            close=df["close"].to_numpy("float64"),
            high=df["high"].to_numpy("float64"),
            low=df["low"].to_numpy("float64"),
            volume=df["volume"].to_numpy("float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"),
            ref_close=ref_close,
            funding=funding,
        )

    return provider


def lake_provider(
    symbols: Sequence[str],
    timeframe: Timeframe = Timeframe.D1,
    *,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> DataProvider:
    """Build an injectable ``symbol -> MarketSeries`` provider over cached lake frames.

    Frames are read once and cached; a symbol with fewer than ``min_bars`` bars returns ``None`` so
    the lab skips it honestly rather than testing a too-short series. ``funding`` is attached when
    present (Level-3) so the crypto-native generator is a real test, not a degrade-to-flat.
    """
    return _provider_from_frames(_read_frames(symbols, timeframe, lake_root), min_bars)


def load_universe(
    timeframe: Timeframe = Timeframe.D1,
    *,
    limit: int | None = 30,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> tuple[list[str], DataProvider]:
    """Select the TRADEABLE crypto universe (top-``limit`` by trailing dollar-volume) + a provider.

    Ranking is done OFFLINE from lake bars (median close*volume over the last ~180 bars) -- no live
    API call, so no network/geo-block failure mode in the daily cycle. Capping to the liquid names
    is economically honest AND statistically kinder: testing 200+ microcap perps is breadth-mining
    that inflates the cumulative trial count (harshening the DSR deflation on the real hypotheses)
    while adding near-zero-capacity candidates. It is also operationally robust -- the campaign-wide
    Reality-Check bootstrap over an N-wide candidate matrix is memory-heavy, so an unbounded sweep
    (~1000 candidates) OOM-crashes this box mid-cycle; ~30 liquid names keeps N bounded. The top ~30
    perps hold essentially all real research capacity anyway. ``limit=None`` keeps every symbol.
    """
    all_syms = crypto_symbols(timeframe, lake_root=lake_root)
    frames = _read_frames(all_syms, timeframe, lake_root)
    eligible = [s for s in all_syms if len(frames[s]) >= min_bars]

    def _adv(sym: str) -> float:
        df = frames[sym]
        if "volume" not in df.columns:
            return 0.0
        dollar = (df["close"] * df["volume"]).tail(180)
        return float(dollar.median()) if len(dollar) else 0.0

    eligible.sort(key=_adv, reverse=True)
    selected = eligible if limit is None else eligible[:limit]
    return selected, _provider_from_frames(frames, min_bars)


def build_lab(
    db: Database,
    provider: DataProvider,
    *,
    families: Sequence[Family] | None = DEFAULT_FAMILIES,
    cost_per_side: float = COST_PER_SIDE,
) -> AutoDiscoveryLab:
    """Wire a crypto-fed :class:`AutoDiscoveryLab` (flat per-side cost, family-restricted)."""
    return AutoDiscoveryLab(
        db,
        provider,
        cost_provider=lambda _s: cost_per_side,
        families=list(families) if families is not None else None,
    )


def web_payload(
    store: CandidateStore, result: CycleResult, *, timeframe: str = "D1"
) -> dict[str, object]:
    """Dashboard-ready summary of the crypto factory's cumulative state + this cycle's delta."""
    survivors = [
        {
            "id": r.id,
            "family": r.family,
            "subtype": r.subtype,
            "symbol": r.symbol,
            "annual_sharpe": round(float(r.metrics.annual_sharpe), 3),
            "dsr": round(float(r.metrics.dsr), 3),
        }
        for r in store.survivors()
    ]
    rejection_hist: dict[str, int] = {}
    for rec in store.all():
        if rec.survived or not rec.rejection_reason:
            continue
        body = rec.rejection_reason.removeprefix("failed: ")
        for gate in (g.strip() for g in body.split(",") if g.strip()):
            rejection_hist[gate] = rejection_hist.get(gate, 0) + 1
    return {
        "timeframe": timeframe,
        "cumulative_tested": store.total(),
        "cumulative_survivors": len(survivors),
        "by_family": store.family_counts(),
        "by_status": store.status_counts(),
        "rejection_by_gate": dict(sorted(rejection_hist.items(), key=lambda kv: -kv[1])),
        "this_cycle": {
            "tested": result.tested,
            "skipped_duplicate": result.skipped_duplicate,
            "survivors": result.survivors,
            "rejected": result.rejected,
            "promoted_to_paper": result.promoted_to_paper,
        },
        "survivors": survivors,
        "note": (
            "Industrialized crypto hypothesis factory: same gauntlet, net of real perp cost, "
            "cross-campaign DSR deflation. Zero survivors is the honest expected outcome; the "
            "funding_stress_reversal (LIQUIDITY) generator is the one crypto-native test."
        ),
    }
