#!/usr/bin/env python3
"""PERP-DEX FUNDING, ACCESS-SEGMENTED VENUES (R0100 axis 5) -- Aster + Lighter, with
screen-on-discovery.

MECHANISM (stated before any screen): participant segmentation, the opposite end of the card-22
logic. Perp-DEX funding is set by a degen-retail cohort that cannot (or will not) touch the CEX;
the SPREAD between that cohort's funding and Binance's is a leverage-demand divergence between two
access-segmented populations, orthogonal to the funding LEVEL the desk already collects.

VENUES AND HISTORY, verified live 2026-08-05:
  * Aster (fapi.asterdex.com) -- Binance-compatible market-data REST, keyless. fundingRate serves
    HISTORY with startTime/endTime/limit (BTCUSDT back to 2021-08-27, 8h prints; ApolloX
    heritage). 8h klines back to 2021-09-01 serve as the venue-consistent screen target.
    exchangeInfo declares REQUEST_WEIGHT 2400/min; this collector stays under ~200/min.
  * Lighter (mainnet.zklighter.elliot.ai) -- zk perp DEX, keyless REST. /api/v1/fundings serves
    hourly funding history per market_id (BTC/ETH from 2025-01-19; max 750 rows/call, so paging
    windows stay at 28 days = 672 rows). UNITS: the `rate` field is PERCENT PER HOUR, signed via
    `direction` ("long" = longs pay = positive by CEX convention). Rows retain the raw fields
    verbatim AND a normalised signed decimal `rate`, so the normalisation is auditable.

CLOCK PROVENANCE (L1.46, libs/research/clock_provenance.py convention): every row carries
  t = the VENUE's own settlement stamp (ms), c = "venue", r = OUR receipt instant (ms).
Both venues publish stamps; nothing here is recv_only. Aster fundingTime carries +-6ms jitter
(observed: 1700006400002); consumers snap to the hour grid via _snap_ms before joining.

SCREEN-ON-DISCOVERY: history exists NOW, so the audited harness (libs.research.axis_screen.
stage_a_screen -- the de-contamination gate is baked in, never hand-rolled) runs in the same
organ after each append and writes reports/axis_screens/perpdex_funding.json. Every construction
tried is logged there -- spread, level and USDT-denominated builds are separate trials, all
reported, never only the winner. Alignment is declared in _ALIGNMENT below. Stage A only: ZERO
promotion authority; a pass earns a forward clock, never capital.

    .venv/bin/python scripts/collect_perpdex_funding.py [--skip-screen] [--json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = "data/perpdex_funding.jsonl"
_KLINES = "data/perpdex_klines_8h.jsonl"
_STATUS = "data/perpdex_funding_status.json"
_SCREEN_REPORT = "reports/axis_screens/perpdex_funding.json"
_CLOCK = "data/perpdex_funding_clock.jsonl"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 25
_SLEEP_S = 0.3          # between HTTP calls -- Aster declares 2400 weight/min, we use <200

_ASTER = "https://fapi.asterdex.com"
_LIGHTER = "https://mainnet.zklighter.elliot.ai"

#: Top-N shared majors: intersection of both venues' books with the desk's Binance perp universe
#: (data/funding_settlements/*.parquet). Aster symbols are Binance-compatible names.
ASTER_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "LINKUSDT", "SUIUSDT", "AVAXUSDT")
#: Lighter market_id map read live off /api/v1/orderBooks 2026-08-05 (symbol -> market_id).
LIGHTER_MARKETS: dict[str, int] = {
    "BTC": 1, "ETH": 0, "SOL": 2, "XRP": 7, "DOGE": 3,
    "LINK": 8, "BNB": 25, "ADA": 39, "SUI": 16, "AVAX": 9}
#: Maps a Lighter symbol to the desk's Binance perp name for the cross-venue join.
LIGHTER_TO_PERP: dict[str, str] = {s: f"{s}USDT" for s in LIGHTER_MARKETS}

_H8_MS = 8 * 3600 * 1000
_H1_MS = 3600 * 1000
_LIGHTER_EPOCH_S = 1_737_000_000          # 2025-01-16, just before the first markets went live
_ASTER_EPOCH_MS = 1_600_000_000_000       # 2020-09 -- before any Aster/ApolloX history
_MAX_PAGES = 80                           # per (venue, symbol) per run -- first-run backfill cap

#: The screen's honest floor: stage_a_screen returns INSUFFICIENT-DATA below n(zv)=30, i.e.
#: 51 aligned periods (zwin 20 + 30 + 1). Used for the UNSCREENABLE refusal message.
_HARNESS_MIN_PERIODS = 51


def _now_ms() -> int:
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def _snap_ms(t: int, grid_ms: int = _H1_MS) -> int:
    """Settlement stamps carry +-6ms venue jitter (observed 1700006400002); snap to the hour."""
    return int(round(t / grid_ms) * grid_ms)


def _get_json(url: str) -> tuple[Any, str]:
    """(payload, error). Never raises: one dead venue must not kill the other's archive."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        return json.loads(raw), ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:140]}"


def lighter_rate_decimal(rate_pct: float, direction: str) -> float:
    """Lighter publishes PERCENT PER HOUR + a direction. CEX convention: positive = longs pay.

    direction "long" means longs pay shorts -> positive; "short" -> negative. The raw fields are
    retained on every row so this normalisation stays auditable against the source.

    AN UNRECOGNISED DIRECTION REFUSES, IT DOES NOT DEFAULT (L2.4). This was `else -1.0`, which
    mapped a MISSING field, a capitalised "Long" or a renamed value to NEGATIVE -- a silently
    sign-flipped row is indistinguishable from a real one downstream, and the sign IS the
    mechanism here (the spread's direction is the whole hypothesis). A venue schema change would
    have inverted part of a 131k-row corpus with nothing to detect it. Raising is safe because
    the caller records the raw fields verbatim and drops only the unparseable row.
    """
    if direction not in ("long", "short"):
        raise ValueError(
            f"unrecognised Lighter funding direction {direction!r} -- expected 'long' or "
            "'short'; refusing to guess a sign (a wrong sign silently inverts the mechanism)")
    sign = 1.0 if direction == "long" else -1.0
    return sign * rate_pct / 100.0


# ------------------------------------------------------------------ fetchers (paged, resumable)

def fetch_aster_funding(symbol: str, since_ms: int) -> tuple[list[dict[str, Any]], str]:
    """Full paged history from since_ms forward. Returns (rows, error). Partial pages are kept."""
    rows: list[dict[str, Any]] = []
    cursor = max(since_ms, _ASTER_EPOCH_MS)
    for _ in range(_MAX_PAGES):
        url = f"{_ASTER}/fapi/v1/fundingRate?symbol={symbol}&startTime={cursor}&limit=1000"
        doc, err = _get_json(url)
        recv = _now_ms()
        if err:
            return rows, err
        if not isinstance(doc, list) or not doc:
            return rows, ""
        for d in doc:
            try:
                rows.append({"t": int(d["fundingTime"]), "c": "venue", "r": recv,
                             "venue": "aster", "symbol": symbol, "kind": "funding",
                             "rate": float(d["fundingRate"])})
            except (KeyError, TypeError, ValueError):
                continue                       # a malformed row is skipped, the page is kept
        cursor = int(doc[-1]["fundingTime"]) + 1
        if len(doc) < 1000:
            return rows, ""
        time.sleep(_SLEEP_S)
    return rows, ""


def fetch_aster_klines_8h(symbol: str, since_ms: int) -> tuple[list[dict[str, Any]], str]:
    """8h close series -- the venue-consistent screen target. Same paging contract as funding."""
    rows: list[dict[str, Any]] = []
    cursor = max(since_ms, _ASTER_EPOCH_MS)
    for _ in range(_MAX_PAGES):
        url = f"{_ASTER}/fapi/v1/klines?symbol={symbol}&interval=8h&startTime={cursor}&limit=1000"
        doc, err = _get_json(url)
        recv = _now_ms()
        if err:
            return rows, err
        if not isinstance(doc, list) or not doc:
            return rows, ""
        for k in doc:
            try:
                rows.append({"t": int(k[0]), "close_t": int(k[6]), "c": "venue", "r": recv,
                             "venue": "aster", "symbol": symbol, "kind": "kline_8h",
                             "close": float(k[4])})
            except (IndexError, TypeError, ValueError):
                continue
        cursor = int(doc[-1][0]) + 1
        if len(doc) < 1000:
            return rows, ""
        time.sleep(_SLEEP_S)
    return rows, ""


def fetch_lighter_funding(symbol: str, market_id: int,
                          since_s: int) -> tuple[list[dict[str, Any]], str]:
    """Hourly funding history, paged in 28-day windows (max 750 rows/call per their docs)."""
    rows: list[dict[str, Any]] = []
    window_s = 28 * 86400
    cursor = max(since_s, _LIGHTER_EPOCH_S)
    now_s = int(datetime.now(tz=UTC).timestamp())
    for _ in range(_MAX_PAGES):
        if cursor >= now_s:
            return rows, ""
        end = min(cursor + window_s, now_s)
        url = (f"{_LIGHTER}/api/v1/fundings?market_id={market_id}&resolution=1h"
               f"&start_timestamp={cursor}&end_timestamp={end}&count_back=0")
        doc, err = _get_json(url)
        recv = _now_ms()
        if err:
            return rows, err
        got = doc.get("fundings") if isinstance(doc, dict) else None
        if isinstance(got, list):
            for f in got:
                try:
                    pct = float(f["rate"])
                    rows.append({"t": int(f["timestamp"]) * 1000, "c": "venue", "r": recv,
                                 "venue": "lighter", "symbol": symbol, "kind": "funding",
                                 "rate": lighter_rate_decimal(pct, str(f.get("direction", ""))),
                                 "rate_pct_raw": pct,
                                 "direction": str(f.get("direction", "")),
                                 "value_quote": float(f.get("value", 0.0))})
                except (KeyError, TypeError, ValueError):
                    continue
        cursor = end                            # advance even through empty pre-listing windows
        time.sleep(_SLEEP_S)
    return rows, ""


# ------------------------------------------------------------------ archive (append-only, dedup)

def _load_keys_and_max(path: Path) -> tuple[set[tuple[str, str, int]], dict[tuple[str, str], int]]:
    """Dedup keys (venue, symbol, snapped t) + resume cursor max t per (venue, symbol)."""
    keys: set[tuple[str, str, int]] = set()
    maxes: dict[tuple[str, str], int] = {}
    if not path.exists():
        return keys, maxes
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                k = (d["venue"], d["symbol"], _snap_ms(int(d["t"])))
            except (ValueError, KeyError, TypeError):
                continue                        # a corrupt line must not poison the archive read
            keys.add(k)
            mk = (d["venue"], d["symbol"])
            maxes[mk] = max(maxes.get(mk, 0), int(d["t"]))
    return keys, maxes


def _append_new(path: Path, rows: list[dict[str, Any]],
                keys: set[tuple[str, str, int]]) -> int:
    fresh = []
    for row in rows:
        k = (row["venue"], row["symbol"], _snap_ms(int(row["t"])))
        if k in keys:
            continue
        keys.add(k)
        fresh.append(row)
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")
    return len(fresh)


def collect(root: Path) -> dict[str, Any]:
    """Pull whatever each venue holds beyond our archive; append with (venue,symbol,t) dedup."""
    out, kl = root / _OUT, root / _KLINES
    keys, maxes = _load_keys_and_max(out)
    kkeys, kmaxes = _load_keys_and_max(kl)
    errors: dict[str, str] = {}
    appended = {"aster": 0, "lighter": 0, "aster_klines": 0}

    for sym in ASTER_SYMBOLS:
        rows, err = fetch_aster_funding(sym, maxes.get(("aster", sym), 0) + 1)
        if err:
            errors[f"aster:{sym}"] = err
        appended["aster"] += _append_new(out, rows, keys)
        time.sleep(_SLEEP_S)
        krows, kerr = fetch_aster_klines_8h(sym, kmaxes.get(("aster", sym), 0) + 1)
        if kerr:
            errors[f"aster_klines:{sym}"] = kerr
        appended["aster_klines"] += _append_new(kl, krows, kkeys)
        time.sleep(_SLEEP_S)

    for sym, mid in LIGHTER_MARKETS.items():
        since_s = maxes.get(("lighter", sym), 0) // 1000 + 1
        rows, err = fetch_lighter_funding(sym, mid, since_s)
        if err:
            errors[f"lighter:{sym}"] = err
        appended["lighter"] += _append_new(out, rows, keys)
        time.sleep(_SLEEP_S)

    aster_dead = all(f"aster:{s}" in errors for s in ASTER_SYMBOLS)
    lighter_dead = all(f"lighter:{s}" in errors for s in LIGHTER_MARKETS)
    n_archive = len(keys)
    status = ("ALL-VENUES-DOWN" if (aster_dead and lighter_dead) else
              "DEGRADED" if errors else
              "OK-UP-TO-DATE" if sum(appended.values()) == 0 else "OK")
    spans: dict[str, str] = {}
    for (venue, sym), mx in sorted(maxes.items()):
        spans[f"{venue}:{sym}"] = datetime.fromtimestamp(mx / 1000, tz=UTC).isoformat()
    return {"generated": datetime.now(tz=UTC).isoformat(), "status": status,
            "appended": appended, "n_archive_rows": n_archive,
            "n_kline_rows": len(kkeys), "venue_errors": errors, "latest_by_stream": spans,
            "clock_provenance": "t=venue settlement stamp (ms), c=venue, r=receipt ms (L1.46)",
            "detail": (f"{sum(appended.values())} new rows "
                       f"(aster {appended['aster']}, lighter {appended['lighter']}, "
                       f"klines {appended['aster_klines']}); archive {n_archive} rows; "
                       f"{len(errors)} stream error(s)")}


# ------------------------------------------------------------------ screen-on-discovery (Stage A)

_ALIGNMENT = (
    "DECLARED PER L1.46 -- cross-venue join on the venue's OWN settlement stamps. (a) Both Aster "
    "and Binance settle on the same 00/08/16 UTC grid; stamps are snapped to the hour "
    "(_snap_ms) to kill the +-6ms venue jitter observed on Aster (e.g. 1700006400002). "
    "(b) 8h cells: the funding print PAID at settlement T is computed over [T-8h, T) and is "
    "public exactly at T, so signal[period ending T] = print at T, and the harness pairs it "
    "with the NEXT 8h bar's return (kline [T, T+8h), Aster's own 8h klines) -- signal is fully "
    "public before the target window opens, zero overlap. (c) daily cells (Lighter is hourly): "
    "day-d signal sums prints stamped in [d 00:00, d+1 00:00) UTC; the LAST constituent lands "
    "16:00 UTC (Aster/Binance) or 23:00 UTC (Lighter), 8h/1h BEFORE the day-d close that opens "
    "the target window (futclose_daily = Binance USD-M UTC-day closes, the desk's canonical "
    "target; label date d closes 23:59:59.999 d). The boundary print at d+1 00:00 is EXCLUDED "
    "from day d -- conservative, discards rather than risks the boundary instant. "
    "(d) LOOK-AHEAD RISK FLAGGED: the USDT-denominated builds multiply the day-d rate sum by the "
    "day-d CLOSE, so that signal completes exactly AT the boundary instant (23:59:59.999), not "
    "8h before it -- the same class as the oi_ls '5-minute objection'. The rate-only builds are "
    "immune; any conclusion must not rest on the USDT cells alone. (e) The Binance leg "
    "(data/funding_settlements/*.parquet) ends 2026-08-01; joins truncate there rather than "
    "extrapolate. (f) 8h-grid gaps (venue outages) are stitched by joining on the settlement "
    "grid intersection; gap counts are reported per trial as n_grid_gaps -- stitching adds "
    "noise, it cannot manufacture a lead.")

_HARNESS_CAVEAT = (
    "Declared, not patched (the harness is audited and was not modified): stage_a_screen's "
    "n_eff = n/horizon_days assumes DAILY sampling of overlapping h-day returns. The 8h cells "
    "pass horizon_days=1/3 (the true target period, so Sharpe annualises by sqrt(1095) "
    "correctly), but that formula then reports n_eff = 3n for NON-overlapping 8h observations. "
    "The honest independent count is n itself; min_detectable_ic_honest = 1.96/sqrt(n) is "
    "reported beside every 8h trial and is the number to trust. Verdict labels are the "
    "harness's own and were not overridden in either direction.")


def _read_funding(path: Path) -> dict[tuple[str, str], dict[int, float]]:
    """{(venue, symbol) -> {snapped settlement ms -> decimal rate}} from the archive."""
    series: dict[tuple[str, str], dict[int, float]] = {}
    if not path.exists():
        return series
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                if d.get("kind") != "funding":
                    continue
                series.setdefault((d["venue"], d["symbol"]), {})[
                    _snap_ms(int(d["t"]))] = float(d["rate"])
            except (ValueError, KeyError, TypeError):
                continue
    return series


def _read_klines(path: Path) -> dict[str, dict[int, float]]:
    """{symbol -> {open ms -> close}} for aster 8h bars."""
    kl: dict[str, dict[int, float]] = {}
    if not path.exists():
        return kl
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                if d.get("kind") == "kline_8h":
                    kl.setdefault(d["symbol"], {})[_snap_ms(int(d["t"]))] = float(d["close"])
            except (ValueError, KeyError, TypeError):
                continue
    return kl


def _read_binance_funding(root: Path, symbol: str) -> dict[int, float]:
    """Binance 8h settlements from the lake (data/funding_settlements/<sym>.parquet)."""
    p = root / "data/funding_settlements" / f"{symbol}.parquet"
    if not p.exists():
        return {}
    import pandas as pd
    df = pd.read_parquet(p)
    out: dict[int, float] = {}
    for ts, f in zip(df["timestamp"], df["funding"], strict=True):
        out[_snap_ms(int(ts.timestamp() * 1000))] = float(f)
    return out


def _read_futclose(root: Path, symbol: str) -> dict[str, float]:
    p = root / "data/lake/bronze/futclose_daily" / f"{symbol}.jsonl"
    out: dict[str, float] = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                out[str(d["date"])] = float(d["close"])
            except (ValueError, KeyError, TypeError):
                continue
    return out


def daily_sums(prints_ms: dict[int, float]) -> dict[str, float]:
    """Sum prints stamped in [d 00:00, d+1 00:00) UTC into day d. A print at exactly 00:00
    belongs to the day it OPENS, so day d's signal completes at its last intra-day print and the
    d+1 boundary print is excluded from day d (conservative; declared in _ALIGNMENT (c))."""
    out: dict[str, float] = {}
    for t, r in prints_ms.items():
        key = datetime.fromtimestamp(t / 1000, tz=UTC).date().isoformat()
        out[key] = out.get(key, 0.0) + r
    return out


def align_8h(dex: dict[int, float], cex: dict[int, float],
             kl: dict[int, float]) -> tuple[list[int], list[float], list[float], list[float], int]:
    """Settlement grid intersection: T where both prints exist and klines give the return of the
    period ENDING at T. Returns (T list, dex rates, cex rates, period returns, n_grid_gaps)."""
    ts, dr, cr, rets = [], [], [], []
    common = sorted(t for t in dex
                    if t in cex and (t - _H8_MS) in kl and (t - 2 * _H8_MS) in kl)
    gaps = sum(1 for a, b in itertools.pairwise(common) if b - a != _H8_MS)
    for t in common:
        prev_close, close = kl[t - 2 * _H8_MS], kl[t - _H8_MS]
        if prev_close <= 0:
            continue
        ts.append(t)
        dr.append(dex[t])
        cr.append(cex[t])
        rets.append(close / prev_close - 1.0)
    return ts, dr, cr, rets, gaps


def run_screen(root: Path) -> dict[str, Any]:
    """Every construction is a logged trial; the harness's verdicts are never overridden."""
    import numpy as np

    from libs.research.axis_screen import stage_a_screen

    funding = _read_funding(root / _OUT)
    klines = _read_klines(root / _KLINES)
    trials: list[dict[str, Any]] = []
    unscreenable: list[str] = []
    clock = str(root / _CLOCK)

    def _log(name: str, sig: list[float], rets: list[float], *, horizon_days: float,
             extra: dict[str, Any]) -> None:
        if len(sig) < _HARNESS_MIN_PERIODS:
            unscreenable.append(f"{name}: {len(sig)} aligned periods < harness minimum "
                                f"{_HARNESS_MIN_PERIODS} (INSUFFICIENT-DATA by construction)")
            return
        out = stage_a_screen(np.array(sig), np.array(rets), name=name,
                             horizon_days=horizon_days, clock=clock)
        n = out.get("n", 0)
        out["min_detectable_ic_honest_nonoverlap"] = (
            round(float(1.96 / np.sqrt(n)), 4) if n else None)
        out.update(extra)
        trials.append(out)

    # ---- Aster vs Binance, 8h resolution (the powered cells: ~5,400 non-overlapping periods)
    for sym in ("BTCUSDT", "ETHUSDT"):
        dex = funding.get(("aster", sym), {})
        cex = _read_binance_funding(root, sym)
        kl = klines.get(sym, {})
        if not dex or not cex or not kl:
            unscreenable.append(f"aster:{sym}: missing input (dex={len(dex)} cex={len(cex)} "
                                f"klines={len(kl)}) -- NO-DATA, screen refused for this cell")
            continue
        ts, dr, cr, rets, gaps = align_8h(dex, cex, kl)
        extra = {"venue": "aster", "symbol": sym, "resolution": "8h", "n_grid_gaps": gaps,
                 "span": [datetime.fromtimestamp(ts[0] / 1000, tz=UTC).date().isoformat(),
                          datetime.fromtimestamp(ts[-1] / 1000, tz=UTC).date().isoformat()]
                 if ts else None}
        spread = [a - b for a, b in zip(dr, cr, strict=True)]
        closes = [kl[t - _H8_MS] for t in ts]
        _log(f"perpdex_funding::aster_{sym}_spread_rate::8h", spread, rets,
             horizon_days=1 / 3, extra=extra)
        _log(f"perpdex_funding::aster_{sym}_level_rate::8h", dr, rets,
             horizon_days=1 / 3, extra=extra)
        _log(f"perpdex_funding::aster_{sym}_spread_usdt::8h",
             [s * c for s, c in zip(spread, closes, strict=True)], rets,
             horizon_days=1 / 3,
             extra={**extra, "lookahead_note": "signal uses the close of the period ENDING at "
                    "the settlement -- known at T^-, clean; see alignment (d)"})

    # ---- Lighter vs Binance, daily resolution (accruing cells -- declared underpowered)
    for lsym, perp in (("BTC", "BTCUSDT"), ("ETH", "ETHUSDT")):
        dex = funding.get(("lighter", lsym), {})
        cex = _read_binance_funding(root, perp)
        closes = _read_futclose(root, perp)
        if not dex or not cex or not closes:
            unscreenable.append(f"lighter:{lsym}: missing input (dex={len(dex)} "
                                f"cex={len(cex)} futclose={len(closes)}) -- NO-DATA")
            continue
        ddex, dcex = daily_sums(dex), daily_sums(cex)
        days = sorted(d for d in ddex if d in dcex and d in closes)
        sig_spread, sig_level, sig_usdt, rets, kept = [], [], [], [], []
        n_day_gaps = 0
        for d in days:
            # the day-d return is close(d)/close(d-1): it exists only when the PREVIOUS
            # CALENDAR day has a close -- a gap must never be mislabelled as a 1-day return
            prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
            if prev not in closes or closes[prev] <= 0:
                n_day_gaps += 1
                continue
            kept.append(d)
            sig_spread.append(ddex[d] - dcex[d])
            sig_level.append(ddex[d])
            sig_usdt.append((ddex[d] - dcex[d]) * closes[d])
            rets.append(closes[d] / closes[prev] - 1.0)
        extra = {"venue": "lighter", "symbol": lsym, "resolution": "daily",
                 "span": [kept[0], kept[-1]] if kept else None, "n_day_gaps": n_day_gaps,
                 "power_note": "single daily series: min-detectable IC at this depth is above "
                               "ic_min -- the harness will honestly read UNDERPOWERED until "
                               "depth accrues; the hourly-resolution route is the powered "
                               "next step (rowed in the report)"}
        _log(f"perpdex_funding::lighter_{lsym}_spread_rate::daily", sig_spread, rets,
             horizon_days=1.0, extra=extra)
        _log(f"perpdex_funding::lighter_{lsym}_level_rate::daily", sig_level, rets,
             horizon_days=1.0, extra=extra)
        _log(f"perpdex_funding::lighter_{lsym}_spread_usdt::daily", sig_usdt, rets,
             horizon_days=1.0,
             extra={**extra, "lookahead_note": "day-d close in the signal completes exactly at "
                    "the boundary instant -- flagged per alignment (d); rate-only builds are "
                    "immune"})

    verdicts: dict[str, int] = {}
    for t in trials:
        verdicts[t["verdict"]] = verdicts.get(t["verdict"], 0) + 1
    interesting = [t["name"] for t in trials if t["verdict"] == "SCREEN-INTERESTING"]
    report = {
        "axis": "perpdex_funding (R0100 axis 5 -- access-segmented venue funding cohort)",
        "updated": datetime.now(tz=UTC).isoformat(),
        "stage": "A (zero promotion authority)",
        "mechanism_prior_stated_before_screening": (
            "Perp-DEX funding is set by an access-segmented degen-retail cohort; its spread over "
            "Binance funding measures leverage-demand divergence between populations (card-22 "
            "logic, opposite end). Spread is the mechanism; level is the control; the "
            "USDT-denominated build restates the spread in carry-per-unit terms."),
        "alignment_declaration": _ALIGNMENT,
        "harness_caveats": _HARNESS_CAVEAT,
        "method": "libs.research.axis_screen.stage_a_screen ONLY (angle-20 de-contamination "
                  "gate baked in). Nothing outside the harness produced a verdict.",
        "trial_accounting": {
            "constructions": 3, "venues": 2, "symbols": 2,
            "trials_this_run": len(trials),
            "note": "every cell of the declared grid is logged below, including nulls and "
                    "refusals -- never only the winner. Any nominal pass carries this "
                    "multiplicity burden."},
        "verdict_summary": verdicts,
        "screen_interesting": interesting,
        "unscreenable_cells": unscreenable,
        "screen_outputs": trials,
        "authority": "Stage A only. ZERO promotion authority. A pass starts a forward clock "
                     "(data/perpdex_funding_clock.jsonl), never capital (L1.6).",
    }
    out = root / _SCREEN_REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), "utf-8")
    return report


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-screen", action="store_true",
                    help="collect only (the screen re-runs on the next full tick)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = collect(_ROOT)
    screen_summary: dict[str, Any] | None = None
    if not args.skip_screen:
        screen = run_screen(_ROOT)
        screen_summary = {"verdict_summary": screen["verdict_summary"],
                          "screen_interesting": screen["screen_interesting"],
                          "n_trials": screen["trial_accounting"]["trials_this_run"],
                          "n_unscreenable": len(screen["unscreenable_cells"]),
                          "report": _SCREEN_REPORT}
        rep["screen"] = screen_summary
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2), "utf-8")

    print(json.dumps(rep, indent=2) if args.json else
          f"perpdex funding (R0100 axis 5): {rep['status']} -- {rep['detail']}"
          + (f" | screen: {screen_summary['verdict_summary']}" if screen_summary else ""))
    if rep["status"] == "ALL-VENUES-DOWN" and rep["n_archive_rows"] == 0:
        print("REFUSED: no venue reachable and no archive exists -- this run produced NO-DATA "
              "and must not read as a quiet success", file=sys.stderr)
        return 2
    if rep["status"] == "ALL-VENUES-DOWN":
        print("NO-DATA this run: every venue stream errored; archive intact but STALE from "
              f"{max(rep['latest_by_stream'].values(), default='never')}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
