#!/usr/bin/env python3
# RETIRED, GENUINELY VENUE-SPECIFIC (2026-08-23): Fusion's MT5 catalogue carries no options, so
# there is no MT5 translation of a crypto options vol surface. Kept per standing instruction, but
# never wire this into any live schedule again.
#
# INTENDED CADENCE (NOT wired here -- ops/crontab.manifest is owned by another agent this wave, so
# this comment is the REQUEST, not the installation):
#
#     17 9 * * *   cd /opt/quant && python3 scripts/collect_deribit_vol_markets.py --mode snapshot
#     41 3 * * 0   cd /opt/quant && python3 scripts/collect_deribit_vol_markets.py --mode backfill
#
# DAILY at 09:17 UTC: 77 minutes after Deribit's 08:00 UTC daily stamp, so the previous bar is
# closed and settled before it is read, and off the hour so it never lands on the executor's beat.
# The snapshot is what keeps the panel alive going forward.
# WEEKLY on Sunday for the backfill: it re-derives history from currently-listed instruments and is
# the only step that can RECOVER a missed day, but it costs ~3.7k HTTP calls, so it runs weekly and
# not daily. Both are keyless, read-only against a public API, and write only under data/.
#
# R0083 recorded that scripts/collect_deribit_surface.py is reachable ONLY via the executor's daily
# flywheel with no cron line of its own. That is the cadence half of census gap #5; the coverage
# half is that it archives 2 currencies and 3 aggregate numbers. This collector is the widening --
# it does NOT replace collect_deribit_surface.py and does not touch its file.
"""WIDENED DERIBIT VOL-MARKET COLLECTOR -- the breadth input for census gap #5.

WHAT WAS MISSING, MEASURED RATHER THAN ASSERTED. The desk's graveyard row `options_vrp` is its BEST
measured IC anywhere (+0.06) and `data/mechanism_census.json` (rank 5, gap 0.3264, TESTED-SHALLOW)
records that it died on BREADTH and not on sign: it ran on the Deribit DVOL index, and DVOL exists
for exactly two currencies. Probed live before this file was written:

    get_volatility_index_data   BTC yes, ETH yes, SOL/XRP/AVAX/PAXG empty, TRX/HYPE HTTP 400
    get_instruments kind=option BTC 834, ETH 688 (coin-settled)
                                +2202 USDC-settled across AVAX, BTC, ETH, HYPE, SOL, TRX, XRP

So the index feed is capped at 2 markets forever, while the CHAIN carries 7 underlyings over 5-12
listed expiries each. This collector reads the chain.

THREE WIDENINGS, ALL OF THEM THE ONES THE CENSUS ASKED FOR:
  MORE UNDERLYINGS  currency=any rather than a hardcoded ("BTC", "ETH") -- 7 today, and whatever
                    Deribit lists tomorrow, because the currency list is DISCOVERED, never typed.
  MORE EXPIRIES     every listed expiry, each carrying its own days-to-expiry, rather than one
                    ~30-day ATM number per currency.
  MORE STRIKES      the whole ladder per expiry, which is what makes the forward recoverable from
                    put-call parity instead of borrowed from a perpetual with a basis error in it.

TWO MODES, AND THE SECOND IS WHY THIS RUNS TODAY RATHER THAN IN A YEAR.
  --mode snapshot   the live chain, marked now, one row per (underlying, expiry). Forward
                    accumulation, exactly like collect_deribit_surface.py but 7 underlyings wide
                    and per-expiry deep.
  --mode backfill   HISTORY, reconstructed. Per-strike implied vol has no free history and that is
                    the documented reason the desk archives forward -- but every still-listed
                    instrument's MARK PRICE history is public via get_tradingview_chart_data, and
                    inverting Black-76 on it recovers the implied vol nobody was recording. The
                    inversion was verified against the live book before this was built: it
                    reproduces Deribit's own mark_iv to within 0.01 vol points on both the inverse
                    (coin-quoted) and the linear (USDC-quoted) families.

WHAT THE BACKFILL CANNOT DO, WRITTEN INTO EVERY ROW IT EMITS. Only STILL-LISTED instruments have
retrievable history, so already-expired expiries are gone. At a past date the recoverable chain
therefore holds only contracts that were long-dated AT that date, and short-tenor buckets begin
later than long ones. That is a tenor-composition bias, NOT a selection on outcome -- an option is
not delisted for performing badly, and for any non-expired expiry the strike ladder is complete.
Rows carry `source` so the screen can report which half of the panel it is standing on.

ONE CLOCK, DECLARED. Deribit stamps daily bars and settles options at 08:00 UTC; the perpetual
bars this collector archives for realised variance carry the SAME stamp (verified: option and perp
1D ticks land on identical 08:00 UTC timestamps). Implied and realised therefore share a venue and
a stamp, which makes the session-offset artifact that killed kimchi/Turkey/Coinbase unavailable
rather than merely unlikely.

NEVER SIMULATES. No generator is in this file's import graph. An unreachable API writes a status
artifact naming the exact endpoints that failed and exits 0.

Keyless public REST. Writes only under data/. No order path, no promotion authority.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.vol_risk_premium import (  # noqa: E402
    atm_implied_vol,
    bucket_of,
)

SCHEMA_VERSION = "1.0.0"
BASE = "https://www.deribit.com/api/v2/public"
UA = "quant-platform/1.0"

PANEL = ROOT / "data/deribit_vol_markets.jsonl"
BARS = ROOT / "data/deribit_underlying_bars.jsonl"
STATUS = ROOT / "data/deribit_vol_markets_status.json"
#: THE CHART CACHE IS DOT-PREFIXED, AND THAT IS LOAD-BEARING RATHER THAN COSMETIC. A backfill
#: caches one small JSON per option instrument -- ~3,700 files, all freshly written -- and
#: `libs/research/cro_role._inventory` walks data/ recursively, sorts NEWEST FIRST and caps at 400
#: slots. Undotted, this cache takes every slot and truncates every real artifact off the CRO's
#: "full desk inventory", which then looks like coverage while showing nothing but cache entries.
#: That exact failure has already happened once on this desk (data/.fresh_markers), and the fix
#: adopted then was the dot prefix, which `_inventory` skips by path component. A cache is not an
#: artifact; it must not sit where the desk inventories artifacts.
CACHE = ROOT / "data/.cache/deribit_chart"

#: Currency buckets Deribit groups its option books under. `any` returns every book in one call;
#: the others are probed only if `any` is rejected by a future API change, so the discovery can
#: never silently degrade to the two-currency world this collector exists to leave.
CURRENCY_QUERIES = ("any", "BTC", "ETH", "USDC")

#: Backfill window. A year is what get_tradingview_chart_data serves for the perpetuals (401 daily
#: bars observed); options simply return less where they were listed later, which the panel records
#: as a later start date rather than as a gap.
BACKFILL_DAYS = 400

#: Parallel fetches. Deliberately small: this is a keyless public endpoint and the desk does not
#: buy its breadth by hammering a venue that is doing it a favour.
WORKERS = 4

#: Instruments whose whole retrievable history is shorter than this are not worth a call: they were
#: listed days ago and contribute a stub column that the date intersection would then impose on
#: every other market.
MIN_TICKS = 5


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _get(url: str, *, timeout: int = 25) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data if isinstance(data, dict) else {"result": data}


def _get_retry(url: str, *, attempts: int = 3) -> dict[str, Any] | None:
    """None on persistent failure. A failed fetch is a MISSING row, never a zero and never a guess."""
    for i in range(attempts):
        try:
            return _get(url)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            if i == attempts - 1:
                return None
            time.sleep(0.6 * (i + 1))
    return None


def discover_option_instruments() -> tuple[list[dict[str, Any]], list[str]]:
    """Every listed option instrument, DISCOVERED not typed. Returns (instruments, endpoints_tried).

    The currency axis is the one the previous attempt was pinned on, so it is the one thing this
    function must never hardcode. `any` is asked first; the per-currency queries are a fallback so
    an API change degrades to fewer books with a visible reason rather than to the old two.
    """
    tried: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    for cur in CURRENCY_QUERIES:
        url = f"{BASE}/get_instruments?currency={cur}&kind=option&expired=false"
        tried.append(url)
        res = _get_retry(url)
        rows = (res or {}).get("result")
        if not isinstance(rows, list):
            continue
        for r in rows:
            if isinstance(r, dict) and isinstance(r.get("instrument_name"), str):
                seen.setdefault(str(r["instrument_name"]), r)
        if cur == "any" and len(seen) > 100:
            break                              # `any` served the whole book; no need to re-ask
    return list(seen.values()), tried


def _meta(inst: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise one instrument record, or None when a field the maths needs is missing."""
    name = str(inst.get("instrument_name", ""))
    base = str(inst.get("base_currency", "") or name.split("-")[0].split("_")[0]).upper()
    settle = str(inst.get("settlement_currency", "")).upper()
    try:
        strike = float(inst.get("strike"))                       # type: ignore[arg-type]
        exp_ms = int(inst.get("expiration_timestamp"))           # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    otype = str(inst.get("option_type", "")).lower()
    if strike <= 0 or exp_ms <= 0 or otype not in ("call", "put") or not base:
        return None
    return {"name": name, "underlying": base, "strike": strike, "expiry_ms": exp_ms,
            "is_call": otype == "call",
            # INVERSE = settled in the coin it is written on, so the mark is a FRACTION of the
            # underlying. The two families need different parity algebra and different price
            # scaling, and getting it from the venue's own settlement field means the screen never
            # has to guess from an instrument-name pattern.
            "inverse": settle == base}


def _chart(name: str, start_ms: int, end_ms: int, *,
           use_cache: bool) -> tuple[list[int], list[float]] | None:
    """Daily (tick_ms, close) for one instrument. Cached on disk so a re-run is nearly free."""
    cpath = CACHE / f"{name}.json"
    if use_cache and cpath.is_file():
        try:
            blob = json.loads(cpath.read_text("utf-8"))
            return [int(t) for t in blob["ticks"]], [float(c) for c in blob["close"]]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    res = _get_retry(f"{BASE}/get_tradingview_chart_data?instrument_name={name}"
                     f"&start_timestamp={start_ms}&end_timestamp={end_ms}&resolution=1D")
    body = (res or {}).get("result")
    if not isinstance(body, dict) or str(body.get("status")) != "ok":
        return None
    ticks = body.get("ticks")
    close = body.get("close")
    if not isinstance(ticks, list) or not isinstance(close, list) or len(ticks) != len(close):
        return None
    out_t = [int(t) for t in ticks]
    out_c = [float(c) for c in close]
    if use_cache:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({"ticks": out_t, "close": out_c}), "utf-8")
        except OSError:
            pass
    return out_t, out_c


def perpetual_name(underlying: str) -> str:
    """The perpetual whose closes supply realised variance, on the SAME 08:00 UTC daily stamp."""
    u = underlying.upper()
    return f"{u}-PERPETUAL" if u in ("BTC", "ETH") else f"{u}_USDC-PERPETUAL"


def collect_bars(underlyings: list[str], *, start_ms: int, end_ms: int,
                 use_cache: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Daily perpetual closes per underlying. Returns (rows, underlyings that failed)."""
    rows: list[dict[str, Any]] = []
    failed: list[str] = []
    for u in sorted(set(underlyings)):
        got = _chart(perpetual_name(u), start_ms, end_ms, use_cache=use_cache)
        if got is None or len(got[0]) < MIN_TICKS:
            failed.append(perpetual_name(u))
            continue
        for t, c in zip(got[0], got[1], strict=True):
            if math.isfinite(c) and c > 0.0:
                rows.append({"ts_ms": int(t), "underlying": u, "close": float(c),
                             "source": perpetual_name(u)})
    return rows, failed


def _ladder_rows(under: str, expiry_ms: int, inverse: bool,
                 legs: dict[tuple[float, bool], tuple[list[int], list[float]]],
                 ) -> list[dict[str, Any]]:
    """Per-date ATM implied vol for ONE (underlying, expiry) from its whole strike ladder.

    The ladder is rebuilt independently on every date: the forward comes from put-call parity at
    that date's nearest-the-money strike, and the vol is inverted at the strike nearest THAT
    forward. Nothing is carried across dates, so a day on which the book was thin produces no row
    instead of a stale one.
    """
    by_date: dict[int, dict[float, dict[str, float]]] = {}
    for (strike, is_call), (ticks, closes) in legs.items():
        for t, c in zip(ticks, closes, strict=True):
            if not (math.isfinite(c) and c > 0.0):
                continue
            by_date.setdefault(int(t), {}).setdefault(float(strike), {})[
                "c" if is_call else "p"] = float(c)
    out: list[dict[str, Any]] = []
    for ts in sorted(by_date):
        dte_days = (expiry_ms - ts) / 86_400_000.0
        if dte_days <= 0.0:
            continue
        bucket = bucket_of(dte_days)
        if bucket is None:
            continue
        pairs = [(k, v["c"], v["p"]) for k, v in sorted(by_date[ts].items())
                 if "c" in v and "p" in v]
        if len(pairs) < 2:
            continue
        strikes = [p[0] for p in pairs]
        calls = [p[1] for p in pairs]
        puts = [p[2] for p in pairs]
        got = atm_implied_vol(strikes, calls, puts,
                              t_years=dte_days / 365.0, inverse=inverse)
        if got is None:
            continue
        iv, fwd = got
        out.append({
            "ts_ms": int(ts),
            "date": datetime.fromtimestamp(ts / 1000.0, tz=UTC).date().isoformat(),
            "underlying": under, "expiry_ms": int(expiry_ms),
            "dte_days": round(dte_days, 4), "bucket": bucket,
            "forward": round(fwd, 8), "atm_iv": round(iv, 6),
            # THE UNIT, WRITTEN INTO EVERY ROW. Deribit publishes `mark_iv` in PERCENT and this
            # collector emits the Black-76 inversion in DECIMAL, so the two conventions differ by
            # 100x on a field that looks identical either way. Stating it per row means a consumer
            # never has to infer it from magnitude -- an inference that silently succeeds on a 45%
            # vol read as 0.45 and silently fails on a 4.5% one.
            "atm_iv_unit": "decimal_annualised",
            "n_strikes": len(pairs), "inverse": bool(inverse),
            "source": "backfill_chart_black76",
        })
    return out


def backfill(instruments: list[dict[str, Any]], *, start_ms: int, end_ms: int,
             budget: int, use_cache: bool) -> tuple[list[dict[str, Any]], int, int]:
    """Reconstruct per-(underlying, expiry, date) ATM implied vol. Returns (rows, fetched, failed).

    Expiries are worked LONGEST-DATED FIRST because those are the instruments with the most
    retrievable history -- if the call budget runs out, what is lost is the shallow end of the
    panel rather than its depth.
    """
    groups: dict[tuple[str, int, bool], list[dict[str, Any]]] = {}
    for inst in instruments:
        m = _meta(inst)
        if m is None:
            continue
        groups.setdefault((str(m["underlying"]), int(m["expiry_ms"]), bool(m["inverse"])),
                          []).append(m)
    rows: list[dict[str, Any]] = []
    fetched = failed = 0
    for key in sorted(groups, key=lambda k: -k[1]):
        under, expiry_ms, inverse = key
        members = groups[key]
        if budget <= 0:
            break
        take = members[:budget]
        budget -= len(take)
        legs: dict[tuple[float, bool], tuple[list[int], list[float]]] = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = list(pool.map(
                lambda m: (m, _chart(str(m["name"]), start_ms, end_ms, use_cache=use_cache)),
                take))
        for m, got in results:
            if got is None or len(got[0]) < MIN_TICKS:
                failed += 1
                continue
            fetched += 1
            legs[(float(m["strike"]), bool(m["is_call"]))] = got
        if legs:
            rows.extend(_ladder_rows(under, expiry_ms, inverse, legs))
    return rows, fetched, failed


def snapshot(instruments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """The live chain, marked now: one row per (underlying, expiry) from the full strike ladder.

    Uses `mark_price` from the book summary -- the same quantity the backfill's chart closes are --
    so a snapshot row and a backfill row for the same day are the same measurement taken twice, not
    two different definitions sharing a column name.
    """
    meta: dict[str, dict[str, Any]] = {}
    for inst in instruments:
        m = _meta(inst)
        if m is not None:
            meta[str(m["name"])] = m
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    tried: list[str] = []
    ladders: dict[tuple[str, int, bool], dict[float, dict[str, float]]] = {}
    for cur in ("BTC", "ETH", "USDC"):
        url = f"{BASE}/get_book_summary_by_currency?currency={cur}&kind=option"
        tried.append(url)
        res = _get_retry(url)
        rows = (res or {}).get("result")
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            m = meta.get(str(r.get("instrument_name", "")))
            px = r.get("mark_price")
            if m is None or not isinstance(px, (int, float)) or not (float(px) > 0.0):
                continue
            key = (str(m["underlying"]), int(m["expiry_ms"]), bool(m["inverse"]))
            ladders.setdefault(key, {}).setdefault(float(m["strike"]), {})[
                "c" if m["is_call"] else "p"] = float(px)
    out: list[dict[str, Any]] = []
    for (under, expiry_ms, inverse), ladder in sorted(ladders.items()):
        dte_days = (expiry_ms - now_ms) / 86_400_000.0
        bucket = bucket_of(dte_days) if dte_days > 0.0 else None
        if bucket is None:
            continue
        pairs = [(k, v["c"], v["p"]) for k, v in sorted(ladder.items()) if "c" in v and "p" in v]
        if len(pairs) < 2:
            continue
        got = atm_implied_vol([p[0] for p in pairs], [p[1] for p in pairs], [p[2] for p in pairs],
                              t_years=dte_days / 365.0, inverse=inverse)
        if got is None:
            continue
        iv, fwd = got
        # STAMPED TO THE 08:00 UTC BAR THIS SNAPSHOT FALLS IN, not to the wall clock. The panel's
        # whole alignment guarantee is that every series shares Deribit's daily stamp; a row
        # carrying "now" would be the one observation in the file on a different clock.
        bar_ms = ((now_ms - 8 * 3_600_000) // 86_400_000) * 86_400_000 + 8 * 3_600_000
        out.append({
            "ts_ms": int(bar_ms),
            "date": datetime.fromtimestamp(bar_ms / 1000.0, tz=UTC).date().isoformat(),
            "underlying": under, "expiry_ms": int(expiry_ms),
            "dte_days": round(dte_days, 4), "bucket": bucket,
            "forward": round(fwd, 8), "atm_iv": round(iv, 6),
            "atm_iv_unit": "decimal_annualised",          # see _ladder_rows: never inferred
            "n_strikes": len(pairs), "inverse": bool(inverse),
            "source": "snapshot_chain_black76",
        })
    return out, tried


def merge_jsonl(path: Path, rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> int:
    """Idempotent append: existing keys keep their first value, new keys are added. Returns added.

    FIRST WRITE WINS on a duplicate key. A later run re-deriving the same (date, market) must not
    silently overwrite the observation the desk already reasoned about -- that is how a panel
    quietly changes underneath a screen artifact that cites it.
    """
    existing: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                existing.setdefault(tuple(rec.get(k) for k in key_fields), rec)
    added = 0
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        if k not in existing:
            existing[k] = r
            added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(existing.values(),
                     key=lambda r: tuple(str(r.get(f, "")) for f in key_fields))
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in ordered), "utf-8")
    return added


def status_artifact(*, status: str, endpoints: list[str], missing: list[str],
                    detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "script": "scripts/collect_deribit_vol_markets.py",
        "status": status,
        "mechanism_class": "volatility_risk_premium",
        "census_rank": 5,
        "endpoints_tried": endpoints,
        "missing": missing,
        "detail": detail,
        "refusal": (
            "no synthetic chain is generated and no implied vol is imputed. A premium measured on "
            "a simulated surface is a fact about the simulator, and it would enter the funnel "
            "wearing the same vocabulary as a real one."
        ),
        "vps_runnable": (
            "keyless public REST against www.deribit.com; needs only outbound HTTPS. Re-run "
            "unchanged on the box once egress is available."
        ),
        "authority": "NONE -- a collector. No screen verdict, no promotion, no order path.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Widened Deribit vol-market collector (gap #5)")
    ap.add_argument("--mode", choices=("snapshot", "backfill", "both"), default="snapshot")
    ap.add_argument("--days", type=int, default=BACKFILL_DAYS)
    ap.add_argument("--budget", type=int, default=6000,
                    help="max option instruments fetched in one backfill run")
    ap.add_argument("--no-cache", action="store_true", help="ignore the on-disk chart cache")
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--bars", type=Path, default=BARS)
    ap.add_argument("--status", type=Path, default=STATUS)
    a = ap.parse_args(argv)

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - int(a.days) * 86_400_000
    use_cache = not bool(a.no_cache)

    instruments, tried = discover_option_instruments()
    if not instruments:
        art = status_artifact(
            status="NOT-READABLE-HERE", endpoints=tried,
            missing=["deribit get_instruments (kind=option) returned nothing on every currency "
                     "query -- no egress, DNS, or an API change"],
            detail={"mode": a.mode, "underlyings": 0})
        Path(a.status).parent.mkdir(parents=True, exist_ok=True)
        Path(a.status).write_text(json.dumps(art, indent=1), "utf-8")
        print("deribit-vol-markets: NOT-READABLE-HERE -- option chain unreachable")
        for u in tried:
            print(f"    TRIED {u}")
        print("  no synthetic chain is generated; re-run unchanged where egress exists")
        return 0

    metas = [m for m in (_meta(i) for i in instruments) if m is not None]
    underlyings = sorted({str(m["underlying"]) for m in metas})
    expiries = {(str(m["underlying"]), int(m["expiry_ms"])) for m in metas}
    rows: list[dict[str, Any]] = []
    fetched = failed = 0

    if a.mode in ("snapshot", "both"):
        snap, snap_tried = snapshot(instruments)
        tried.extend(snap_tried)
        rows.extend(snap)
    if a.mode in ("backfill", "both"):
        back, fetched, failed = backfill(instruments, start_ms=start_ms, end_ms=end_ms,
                                         budget=int(a.budget), use_cache=use_cache)
        rows.extend(back)

    bar_rows, bar_failed = collect_bars(underlyings, start_ms=start_ms, end_ms=end_ms,
                                        use_cache=use_cache)
    added_panel = merge_jsonl(Path(a.panel), rows, ("date", "underlying", "expiry_ms"))
    added_bars = merge_jsonl(Path(a.bars), bar_rows, ("ts_ms", "underlying"))

    markets = sorted({f"{r['underlying']}:{r['bucket']}" for r in rows})
    art = status_artifact(
        status="COLLECTED" if rows else "EMPTY",
        endpoints=tried,
        missing=[f"perpetual bars unavailable: {n}" for n in bar_failed],
        detail={
            "mode": a.mode,
            "underlyings": underlyings,
            "n_underlyings": len(underlyings),
            "n_listed_expiries": len(expiries),
            "n_option_instruments": len(metas),
            "instruments_fetched": fetched, "instruments_failed": failed,
            "rows_emitted": len(rows), "rows_added_to_panel": added_panel,
            "bar_rows_added": added_bars,
            "markets_seen": markets, "n_markets_seen": len(markets),
            "prior_attempt_markets": 2,
            "prior_attempt": ("scripts/run_options_vrp_backtest.py -- DVOL index, BTC + ETH only; "
                              "the census records the kill as BREADTH, not sign"),
            "panel": _rel(Path(a.panel)), "bars": _rel(Path(a.bars)),
            "tenor_composition_bias": (
                "backfill rows exist only for STILL-LISTED instruments, so short-tenor buckets "
                "start later than long ones. This is composition, not outcome selection: an "
                "option is never delisted for performing badly."),
        })
    Path(a.status).parent.mkdir(parents=True, exist_ok=True)
    Path(a.status).write_text(json.dumps(art, indent=1), "utf-8")

    print(f"deribit-vol-markets [{a.mode}]: {len(underlyings)} underlyings "
          f"({', '.join(underlyings)}), {len(expiries)} listed expiries, "
          f"{len(metas)} option instruments")
    print(f"  {len(rows)} rows ({added_panel} new) -> {_rel(Path(a.panel))}; "
          f"{added_bars} bar rows -> {_rel(Path(a.bars))}")
    print(f"  markets seen this run: {len(markets)} (prior VRP attempt had 2)")
    if failed:
        print(f"  {failed} instrument fetch(es) failed -- recorded as missing rows, never as zeros")
    for n in bar_failed:
        print(f"    MISSING perpetual bars {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
