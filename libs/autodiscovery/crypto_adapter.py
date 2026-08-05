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
    # The reference's RANGE too: intermarket differencing normalises each leg by its own ATR
    # before subtracting, and a close-only reference cannot supply one.
    btc_high = btc["high"] if btc is not None else None
    btc_low = btc["low"] if btc is not None else None

    def provider(symbol: str) -> MarketSeries | None:
        df = frames.get(symbol)
        if df is None or len(df) < min_bars:
            return None
        funding = df["funding"].to_numpy("float64") if "funding" in df.columns else None
        ref_close = ref_high = ref_low = None
        if btc_close is not None and symbol != "BTCUSDT":
            ref = btc_close.reindex(df.index).ffill()
            if not ref.isna().any():
                ref_close = ref.to_numpy("float64")
                # ALL THREE OR NONE. A reference whose close is aligned but whose range is not
                # would put the two legs of the difference on different bars, which reads as a
                # signal and is a join bug.
                if btc_high is not None and btc_low is not None:
                    rh = btc_high.reindex(df.index).ffill()
                    rl = btc_low.reindex(df.index).ffill()
                    if not rh.isna().any() and not rl.isna().any():
                        ref_high = rh.to_numpy("float64")
                        ref_low = rl.to_numpy("float64")
        return MarketSeries(
            close=df["close"].to_numpy("float64"),
            high=df["high"].to_numpy("float64"),
            low=df["low"].to_numpy("float64"),
            volume=df["volume"].to_numpy("float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"),
            ref_close=ref_close,
            ref_high=ref_high,
            ref_low=ref_low,
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
    API call, so no network/geo-block failure mode in the daily cycle.

    WHY THE CAP EXISTS, RE-DERIVED 2026-08-05 (R0241b), because the reason on this docstring was
    partly UNCONSTITUTIONAL and would have kept the cap forever.

    RETIRED REASON -- "adds near-zero-capacity candidates". That is a capacity TILT, and §42
    capacity parity is explicit that an edge is an edge: never prefer a large-capacity edge over a
    small one, and "fund-shaped" and "niche-only" are the SAME defect pointed opposite ways. The
    only legitimate capacity kill is SUB-VIABLE -- cannot support a handful of economic round-trips
    at venue minimums -- which is a per-candidate test, not a universe filter. Small is the desk's
    stated advantage (§42, L1.28a), so smallness may not be a reason to exclude.

    THE REAL BINDING CONSTRAINT IS MEMORY, and it is now measured rather than asserted. 285 of the
    lake's symbols clear ``min_bars`` today; at 48 hypotheses per symbol that is 13,680 candidates.
    Profiling ``stratified_campaign_gates`` over exactly that many candidate series OOM-killed this
    box (MemAvailable fell to 296 MB and took the CI pytest step down with it, SIGKILL). That is a
    NAMED RESOURCE CEILING with a re-test condition -- raise the cap when the campaign holds
    candidate series in a chunked/streaming form rather than all at once -- not a statistical or
    economic preference.

    THE MULTIPLICITY COST IS REAL BUT SMALL, AND IS NOT THE BLOCKER. Measured with the desk's own
    preflight at full available depth: 30 symbols (N=1,440) gives hurdle annSR 1.41 at 98.2% power;
    285 symbols (N=13,680) gives 1.57 at 93.5%. Both POWERED. So multiplicity alone would NOT
    justify the cap -- 9.5x the candidate supply for 4.7 points of power is a trade the desk should
    take, once the memory ceiling allows it.

    ``limit=None`` keeps every symbol and is what the profiling above used; it is available for
    deliberate, resourced runs, not for the daily cycle.
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
    timeframe: Timeframe,
    families: Sequence[Family] | None = DEFAULT_FAMILIES,
    cost_per_side: float = COST_PER_SIDE,
) -> AutoDiscoveryLab:
    """Wire a crypto-fed :class:`AutoDiscoveryLab` (flat per-side cost, family-restricted).

    ``timeframe`` is REQUIRED and must be the interval ``provider`` was built on
    (:func:`lake_provider` / :func:`load_universe`). It is not defaulted to ``D1`` alongside them
    on purpose: this is the argument that annualises every Sharpe the lab stores, and a D1 default
    here would silently mis-annualise an H8 universe by sqrt(3) -- a smaller version of the exact
    defect R0086 records (see libs/autodiscovery/validation.py). Crypto trades 24/7, so the lab's
    365-day calendar default is the right one for every provider this module builds.
    """
    return AutoDiscoveryLab(
        db,
        provider,
        bar=timeframe,
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
    # Full history on purpose: a cumulative gate-kill tally must not shrink when candidates are
    # later retired for capacity (status -> archived); their gate history really happened.
    for rec in store.all(include_retired=True):
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
