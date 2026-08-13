"""Crypto perpetual data (Level-3): daily OHLCV + funding rate, from Binance USD-M futures.

Funding rate is the highest-information, free, solo-accessible signal we ranked top: it measures
leverage demand (longs paying shorts when positive). This source returns daily bars with an extra
``funding`` column (the day's summed funding), aligned to the canonical bar schema so it lands in
the existing Parquet lake unchanged. Public REST, no key. Read-only.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_FAPI = "https://fapi.binance.com"

# Cross-process rate-ban latch (2026-07-31 incident: premiumIndex returned 418 -- Binance's
# IP auto-ban -- and every retry from every respawning process EXTENDED the ban). A file, not
# a module global, because the callers are short-lived: cron collectors, the 3-min refresh
# chain, and systemd-respawned executors each start cold.
_BAN_FILE = Path("data/BINANCE_BAN_UNTIL")


def _ban_remaining() -> float:
    try:
        until = float(_BAN_FILE.read_text("utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0
    return max(0.0, until - time.time())
_SPOT = "https://api.binance.com"


def _get(url: str, *, tries: int = 4) -> Any:
    rem = _ban_remaining()
    if rem > 0:
        raise RuntimeError(f"binance rate-ban latched for {rem:.0f}s more "
                           f"(data/BINANCE_BAN_UNTIL): refusing {url}")
    last: Exception | None = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # 418 = IP auto-ban, 429 = rate limit. Requests sent while banned EXTEND the
            # ban, so latch a cross-process cooldown and fail fast instead of retrying.
            if exc.code in (418, 429):
                ra = exc.headers.get("Retry-After") if exc.headers else None
                default_wait = 7200.0 if exc.code == 418 else 120.0
                try:
                    # honour the venue's own clock; absent/unparseable falls to the default
                    wait = max(60.0, float(ra)) if ra else default_wait
                except ValueError:
                    wait = default_wait
                try:
                    _BAN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _BAN_FILE.write_text(
                        f"{time.time() + wait:.0f} code={exc.code} retry_after={ra}\n",
                        "utf-8")
                except OSError:
                    pass
                raise RuntimeError(f"binance rate-ban {exc.code} on {url}: latched "
                                   f"{wait:.0f}s cooldown") from exc
            last = exc
            time.sleep(1.5)
        except Exception as exc:  # transient network
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"GET failed after {tries}: {url} :: {last}")


def _klines(
    base: str, path: str, symbol: str, interval: str, start_ms: int, *, limit: int,
    param: str = "symbol",
) -> pd.DataFrame:
    """Paginated kline fetch. ``param`` is the venue's name for the instrument selector.

    ``param="pair"`` exists for the index-price endpoints: BOTH books spell that one differently
    (``/dapi/v1/indexPriceKlines?pair=BTCUSD``, ``/fapi/v1/indexPriceKlines?pair=BTCUSDT``) and
    answer HTTP 400 -1102 to ``symbol=``. Threading it here rather than forking the function keeps
    ONE paginator -- and the paginator is the part that matters, because truncation past the
    per-call cap is the venue failure mode that never throws.
    """
    rows: list[list[Any]] = []
    cur = start_ms
    while True:
        url = (f"{base}{path}?{param}={symbol}&interval={interval}"
               f"&limit={limit}&startTime={cur}")
        batch = _get(url)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:          # full page -> more to fetch; partial -> done
            break
        cur = int(batch[-1][0]) + 1
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    # kline cols: ...,5=base vol,7=quote vol,10=taker-buy quote vol -> taker-buy fraction = flow.
    qv = np.array([float(r[7]) for r in rows])
    tbq = np.array([float(r[10]) for r in rows])
    return pd.DataFrame({
        "timestamp": pd.to_datetime([r[0] for r in rows], unit="ms", utc=True),
        "open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows],
        "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
        "volume": [float(r[5]) for r in rows],
        # >0.5 = net taker buying (flow). `np.where(qv > 0, tbq / qv, 0.5)` was WRONG in a way that
        # only shows on a zero-volume bar: np.where selects AFTER both branches are evaluated, so
        # `tbq / qv` still divides by zero for every such bar and emits
        # "invalid value encountered in divide". This repo runs `filterwarnings = error`, so the
        # whole fetch RAISED on any symbol with one untraded interval -- and untraded intervals are
        # the normal state of an illiquid perp, which is exactly the breadth this source exists to
        # provide. `np.divide(..., where=)` never evaluates the excluded lanes.
        "taker_buy_frac": np.divide(tbq, qv, out=np.full(qv.shape, 0.5), where=qv > 0),
    })


def list_perp_symbols() -> list[str]:
    """All actively-trading USDT-margined perpetuals (the free cross-sectional universe)."""
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    return sorted(
        s["symbol"] for s in syms
        if s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
    )


def perp_quote_volumes() -> dict[str, float]:
    """24h quote volume per actively-trading USDT perp -- the liquidity axis, BOTH tails.

    list_liquid_perps() serves the top; the thin tail is §42 named ground (thin-pair
    cross-venue funding, R0295), so the raw map is exposed rather than only its head."""
    perps = set(list_perp_symbols())
    tickers = _get(f"{_FAPI}/fapi/v1/ticker/24hr")
    return {t["symbol"]: float(t.get("quoteVolume", 0.0))
            for t in tickers if t.get("symbol") in perps}


def list_liquid_perps(*, top_n: int = 100) -> list[str]:
    """Top-N USDT perps by 24h quote volume -- the TRADEABLE universe (realistic-cost names)."""
    rows = sorted(perp_quote_volumes().items(), key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:top_n]]


def fetch_klines(symbol: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated klines for a USD-M PERP. Canonical OHLCV, UTC timestamps (futures cap 1500)."""
    return _klines(_FAPI, "/fapi/v1/klines", symbol, interval, start_ms, limit=1500)


def fetch_price_at(symbol: str, when_ms: int) -> float | None:
    """Close of the 1m PERP candle containing ``when_ms`` -- one defined instant, never 'now'.

    A POINT QUERY, deliberately not `fetch_klines(interval="1m")`: that paginates forward from
    start_ms to the present, so asking what BTCUSDT was worth eight hours ago would pull every
    minute since. This asks for the three candles around the instant and takes the nearest.

    Returns None rather than a nearby price when the venue has no candle there. A grader that
    silently substitutes a different instant's price is worse than one that refuses: the
    substitution is invisible in the output and biases every outcome it touches.
    """
    url = (f"{_FAPI}/fapi/v1/klines?symbol={symbol}&interval=1m"
           f"&startTime={when_ms - 60_000}&endTime={when_ms + 60_000}&limit=3")
    try:
        rows = _get(url)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(rows, list) or not rows:
        return None
    best = min(rows, key=lambda r: abs(int(r[0]) - when_ms))
    return float(best[4])


def fetch_spot_klines(symbol: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated klines for the SPOT pair (spot API caps limit at 1000 -- must paginate)."""
    return _klines(_SPOT, "/api/v3/klines", symbol, interval, start_ms, limit=1000)


def current_funding() -> dict[str, float]:
    """Latest funding rate per USD-M perp (mainnet premiumIndex) -- the live carry signal."""
    data = _get(f"{_FAPI}/fapi/v1/premiumIndex")
    if not isinstance(data, list):
        return {}
    return {d["symbol"]: float(d.get("lastFundingRate", 0.0)) for d in data
            if isinstance(d, dict) and d.get("symbol")}


def fetch_open_interest(symbol: str) -> float:
    """Current open interest (contracts) for a perp. History is 30d-capped, so log this forward."""
    data = _get(f"{_FAPI}/fapi/v1/openInterest?symbol={symbol}")
    return float(data.get("openInterest", 0.0)) if isinstance(data, dict) else 0.0


def _funding(base: str, path: str, symbol: str, start_ms: int) -> pd.DataFrame:
    """Paginated funding-rate history for either book. (timestamp, funding).

    THE PAGINATION IS THE POINT. Binance caps this endpoint at 1000 rows and returns the cap
    without any signal that more exists; a single unpaginated call on a 2020-listed perp reads as
    ~2.3 years of a 6-year series and every derived total silently understates. Same recorded
    failure mode as the S3 lister's MaxKeys=1000 truncation.
    """
    rows: list[dict[str, Any]] = []
    cur = start_ms
    while True:
        url = f"{base}{path}?symbol={symbol}&limit=1000&startTime={cur}"
        batch = _get(url)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        cur = int(batch[-1]["fundingTime"]) + 1
        time.sleep(0.25)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([r["fundingTime"] for r in rows], unit="ms", utc=True),
        "funding": [float(r["fundingRate"]) for r in rows],
    })


def fetch_funding(symbol: str, *, start_ms: int = 0) -> pd.DataFrame:
    """Paginated funding-rate history (every 8h) for a USD-M perp. (timestamp, funding)."""
    return _funding(_FAPI, "/fapi/v1/fundingRate", symbol, start_ms)


# ------------------------------------------------------------------ COIN-M (dapi), card 31 -----
# The home venue's OTHER futures book: coin-margined (inverse) contracts. Same endpoint family and
# the same keyless posture as the fapi above, so it reuses THIS module's paginator and THIS
# module's cross-process rate-ban latch rather than opening a second, unlatched HTTP path -- a
# collector that retried its way through a 418 on a private helper would extend the ban for every
# other organ on the box.
#
# TWO PROPERTIES THAT ARE NOT SYMMETRIC WITH THE fapi, BOTH MEASURED 2026-08-13:
#
#   1. `/dapi/v1/klines` REFUSES EXPIRED SYMBOLS -- `symbol=BTCUSD_250926` answers HTTP 400
#      {"code":-1121,"msg":"Invalid symbol."} while the fapi serves its own expired quarterlies
#      over REST quite happily. COIN-M delivered-contract history is therefore ARCHIVE-ONLY
#      (data.binance.vision, `99-binance-coinm-vision-archive`). A collector built symmetrically
#      on REST reads "COIN-M has no quarterly history" and is wrong.
#   2. VOLUME COLUMNS MEAN SOMETHING ELSE. On an inverse contract index 5 is volume in CONTRACTS
#      (USD notional), index 7 is BASE-asset volume (coin) and index 10 is taker-buy BASE volume.
#      The `taker_buy_frac` this module computes is therefore a coin-denominated taker-buy share
#      here and a quote-denominated one on the fapi. Both are valid fractions; they are not the
#      same statistic, and averaging them across books would be a units error that looks fine.
_DAPI = "https://dapi.binance.com"


def coinm_instruments() -> list[dict[str, Any]]:
    """LIVE COIN-M instruments from `/dapi/v1/exchangeInfo`.

    NOT A UNIVERSE BUILDER, AND THE DISTINCTION IS LOAD-BEARING (card 31). Measured 2026-08-13:
    exchangeInfo returns 30 instruments while the archive holds 272 kline symbols, so 242 (89%)
    of instrument history -- including all 212+ expired quarterlies -- is invisible here. Building
    a research universe from this call is a LOOK-AHEAD IN THE UNIVERSE, the same class as a
    `pct_circ_now` denominator leak, and it fails toward a FALSE NULL. Use it for what it is: the
    live contract SPECIFICATIONS (contractSize, deliveryDate, pair), which the archive does not
    carry.
    """
    info = _get(f"{_DAPI}/dapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    return [s for s in syms if isinstance(s, dict)]


def fetch_coinm_klines(symbol: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated COIN-M klines. LIVE symbols only -- expired contracts answer -1121 (see above)."""
    return _klines(_DAPI, "/dapi/v1/klines", symbol, interval, start_ms, limit=1500)


def fetch_coinm_mark_klines(symbol: str, *, interval: str = "1d",
                            start_ms: int = 0) -> pd.DataFrame:
    """Paginated COIN-M MARK-price klines (the venue's own fair price, what liquidation uses)."""
    return _klines(_DAPI, "/dapi/v1/markPriceKlines", symbol, interval, start_ms, limit=1500)


def fetch_coinm_index_klines(pair: str, *, interval: str = "1d",
                             start_ms: int = 0) -> pd.DataFrame:
    """Paginated COIN-M INDEX-price klines. Keyed by PAIR (e.g. ``BTCUSD``), never by symbol.

    This is the coin/USD index -- note it is a USD index, while the fapi's same-named endpoint
    returns a coin/USDT index. Any COIN-M-minus-USDT-M basis built from the two therefore carries
    the USDT-vs-USD basis inside it. That is a real component, not an error, but it must be
    declared by anything that differences them.
    """
    return _klines(_DAPI, "/dapi/v1/indexPriceKlines", pair, interval, start_ms, limit=1500,
                   param="pair")


def fetch_coinm_premium_klines(symbol: str, *, interval: str = "1d",
                               start_ms: int = 0) -> pd.DataFrame:
    """Paginated COIN-M PREMIUM-INDEX klines -- the pre-quantisation input to funding.

    Read this in preference to the realised funding rate where the mechanism is about premium:
    the published funding rate is a CLAMPED, CAPPED, QUANTISED and lagged function of the premium
    index (R0021), so it discards exactly the variation a premium hypothesis is about.
    """
    return _klines(_DAPI, "/dapi/v1/premiumIndexKlines", symbol, interval, start_ms, limit=1500)


def fetch_coinm_funding(symbol: str, *, start_ms: int = 0) -> pd.DataFrame:
    """Paginated COIN-M funding-rate history. (timestamp, funding). Perps only -- a delivery
    contract has no funding, and the endpoint returns an empty list for one rather than erroring."""
    return _funding(_DAPI, "/dapi/v1/fundingRate", symbol, start_ms)


def fetch_index_klines(pair: str, *, interval: str = "1d", start_ms: int = 0) -> pd.DataFrame:
    """Paginated USD-M INDEX-price klines, keyed by PAIR (e.g. ``BTCUSDT``). The USDT-M twin of
    ``fetch_coinm_index_klines`` -- present so a cross-book basis uses one code path per leg."""
    return _klines(_FAPI, "/fapi/v1/indexPriceKlines", pair, interval, start_ms, limit=1500,
                   param="pair")


def bars_with_funding(
    symbol: str, *, interval: str = "1d", start: str = "2019-01-01"
) -> pd.DataFrame:
    """OHLCV + a ``funding`` column at the requested interval.

    ``1d``: funding is the SUM of the day's payments (the daily carry cost). ``8h``: funding settles
    every 8h, so each 8h bar maps to exactly one payment (its native frequency) -- this is the right
    resolution for funding-driven hypotheses and gives ~3x the independent observations.
    """
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    klines = fetch_klines(symbol, interval=interval, start_ms=start_ms)
    funding = fetch_funding(symbol, start_ms=start_ms)
    if klines.empty:
        return klines
    klines = klines.set_index("timestamp")
    if funding.empty:
        klines["funding"] = 0.0
    elif interval == "1d":
        daily = funding.set_index("timestamp")["funding"].resample("1D").sum()
        klines["funding"] = daily.reindex(klines.index).fillna(0.0)
    else:
        f = funding.set_index("timestamp")["funding"].sort_index()
        aligned = f.reindex(klines.index, method="nearest", tolerance=pd.Timedelta("4h"))
        klines["funding"] = aligned.fillna(0.0)
    return klines.reset_index()


def daily_with_funding(symbol: str, *, start: str = "2019-01-01") -> pd.DataFrame:
    """Daily OHLCV + a ``funding`` column (sum of the day's funding payments)."""
    return bars_with_funding(symbol, interval="1d", start=start)


def daily_enriched(symbol: str, *, start: str = "2019-01-01") -> pd.DataFrame:
    """Daily bars + funding + taker-buy flow + perp-spot BASIS (all FULL history, free).

    ``basis`` = perp_close / spot_close - 1 (positive = perp premium / contango; negative =
    backwardation). The spot pair shares the perp's ticker (BTCUSDT perp <-> BTCUSDT spot).
    """
    bars = bars_with_funding(symbol, interval="1d", start=start)
    if bars.empty:
        return bars
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    spot = fetch_spot_klines(symbol, interval="1d", start_ms=start_ms)
    bars = bars.set_index("timestamp")
    if spot.empty:
        bars["basis"] = 0.0
    else:
        sp = spot.set_index("timestamp")["close"].reindex(bars.index)
        bars["basis"] = (bars["close"] / sp - 1.0).fillna(0.0)
    if "taker_buy_frac" not in bars.columns:
        bars["taker_buy_frac"] = 0.5
    return bars.reset_index()


def fetch_long_short_ratio(symbol: str, *, period: str = "1d") -> pd.DataFrame:
    """Global account long/short ratio (30d-capped -> archive forward). (ts, ls_ratio)."""
    url = (f"{_FAPI}/futures/data/globalLongShortAccountRatio"
           f"?symbol={symbol}&period={period}&limit=30")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "ls_ratio": [float(r["longShortRatio"]) for r in data],
    })


def fetch_open_interest_hist(symbol: str, *, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Historical open interest (USD-M ``openInterestHist``, ~30-day cap). Hourly gives ~480 points
    over ~20 days -- enough samples to backtest now, without waiting for forward accumulation.
    (timestamp, open_interest)."""
    url = (f"{_FAPI}/futures/data/openInterestHist"
           f"?symbol={symbol}&period={period}&limit={limit}")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "open_interest": [float(r["sumOpenInterest"]) for r in data],
    })


def fetch_long_short_hist(symbol: str, *, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Historical global long/short account ratio (~30-day cap). Hourly -> ~480 points.
    (timestamp, ls_ratio)."""
    url = (f"{_FAPI}/futures/data/globalLongShortAccountRatio"
           f"?symbol={symbol}&period={period}&limit={limit}")
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "ls_ratio": [float(r["longShortRatio"]) for r in data],
    })


def fetch_taker_ratio(symbol: str, *, period: str = "1d") -> pd.DataFrame:
    """Taker buy/sell volume ratio from the derivatives-stats endpoint (30d-capped -> archive)."""
    url = f"{_FAPI}/futures/data/takerlongshortRatio?symbol={symbol}&period={period}&limit=30"
    data = _get(url)
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in data], unit="ms", utc=True),
        "taker_ratio": [float(r["buySellRatio"]) for r in data],
    })
