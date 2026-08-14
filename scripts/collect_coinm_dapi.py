#!/usr/bin/env python3
"""COIN-M (dapi) backfill -- R0462 / data_axis_watchlist card 31.

WHAT THIS COLLECTS AND WHY IT IS SPLIT ACROSS TWO ROUTES. The home venue's coin-margined book has
two halves and they are NOT reachable the same way (both measured 2026-08-13):

    LIVE instruments   -> dapi REST  (/dapi/v1/{klines,markPriceKlines,indexPriceKlines,
                                       premiumIndexKlines,fundingRate}), keyless, no daemon
    EXPIRED quarterlies-> data.binance.vision ARCHIVE ONLY

because `/dapi/v1/klines?symbol=BTCUSD_250926` answers HTTP 400 -1121 "Invalid symbol" while the
USDT-M twin `/fapi/v1/klines?symbol=BTCUSDT_250926` serves the same delivered contract happily.
A collector built symmetrically on REST therefore concludes "COIN-M has no quarterly history" and
is wrong about 212+ contracts. Card 31 already warned that `exchangeInfo` omits them from the
UNIVERSE; this adds that the kline endpoint omits them from the PRICES too.

THE TWO FAILURE MODES THIS FILE IS SHAPED AROUND, both of which fail silently:

  1. TRUNCATION. Every venue history endpoint here has a per-call cap (REST klines 1500, REST
     fundingRate 1000, S3 listing MaxKeys 1000) and NONE of them signal that more exists. The
     recorded desk lesson: "past the cap the numbers keep looking plausible and every derived
     total silently understates" -- an unpaginated listing of one COIN-M feed read 500 files
     ending 2022-11 where the true answer was 1,754 ending 2026-08, a 3.7-YEAR understatement
     that looked complete. So: the REST paginator is `libs.data.crypto_source`'s (one paginator,
     already audited), the S3 lister below follows continuation tokens to `IsTruncated=false`,
     and every series is CONTIGUITY-ASSERTED after assembly rather than trusted.

  2. GUESSED DENOMINATORS. Month ranges are LISTED from the bucket, never generated from a start/
     end guess, so "files we fetched" is checked against "files that exist" and a gap is a
     COUNTED number rather than an invisible one (L1.60). A quarterly contract's live window is
     not knowable a priori; enumerating it is cheap and asserting it is free.

CLOCK PROVENANCE (L1.46) IS DECLARED, NOT ASSUMED. Every row written here carries the explicit
marker `libs.research.clock_provenance.MARKER` = CLOCK_VENUE: `t` is the venue's own bar-open
stamp, in ms, UTC, and the venue's bar-CLOSE stamp is retained alongside it as `T`. Nothing in
this backfill is receipt-stamped, so no file this script writes is mixed-clock. That is a
property of the source (archive CSVs and REST klines are both venue event-time), and it is
recorded per row rather than left to a reader's inference.

RATE LIMITS ARE RESPECTED AND NOT LOOSENED. REST goes through `crypto_source._get`, which honours
the cross-process ban latch at `data/BINANCE_BAN_UNTIL` -- a 418 from any organ stops this one
too. The archive is a different host (a public S3/CDN bucket, no trading rate limit) and is
fetched with a small bounded pool.

    .venv/bin/python scripts/collect_coinm_dapi.py --what all
    .venv/bin/python scripts/collect_coinm_dapi.py --what quarterly --roots BTCUSD,ETHUSD
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import (  # noqa: E402
    coinm_instruments,
    fetch_coinm_funding,
    fetch_coinm_index_klines,
    fetch_coinm_klines,
    fetch_coinm_mark_klines,
    fetch_coinm_premium_klines,
    fetch_funding,
    fetch_index_klines,
    fetch_klines,
)
from libs.research.clock_provenance import CLOCK_VENUE, MARKER  # noqa: E402

OUT = _ROOT / "data" / "coinm"
_S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
_VISION = "https://data.binance.vision"
_UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36")}

#: The five quarterly underlyings card 31 names. COIN-M spelling.
QUARTERLY_ROOTS = ("BTCUSD", "ETHUSD", "BNBUSD", "SOLUSD", "XRPUSD")

#: Bars whose open_time gap exceeds this are a real hole in a 24/7 market, not a weekend.
_DAY_MS = 86_400_000


# --------------------------------------------------------------------------- archive route -----
def _http(url: str, *, tries: int = 3) -> bytes | None:
    """Bytes, or None ONLY for an HTTP 404 -- the bucket saying "this file is not published".

    Every other outcome raises. Collapsing a 403/429/5xx/timeout into "absent" is how a throttled
    connection becomes a short price history that reads as the archive's own gap: the series comes
    back shorter, nothing errors, and every statistic downstream is computed over a silently
    truncated sample (L1.28a -- absence must not resolve to a clean answer).
    """
    last: Exception | None = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=120) as r:
                return bytes(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last = exc
            if 400 <= exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"archive refused {url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        if attempt < tries - 1:
            time.sleep(1.5 * (2 ** attempt))
    raise RuntimeError(f"archive GET failed after {tries}: {url} :: {last}")


def s3_list(prefix: str, *, delimiter: str = "") -> list[str]:
    """Every key (or common prefix) under `prefix`, FOLLOWING CONTINUATION TOKENS TO THE END.

    The unpaginated version of this call returns at most 1000 entries and sets IsTruncated=true,
    which nothing checks unless it is written to. That single omission understated one COIN-M feed
    by 3.7 years while looking complete.
    """
    out: list[str] = []
    token: str | None = None
    tag = "CommonPrefixes><Prefix" if delimiter else "Contents><Key"
    pat = re.compile(rf"<{tag}>([^<]+)</{tag.split('><')[1]}>")
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        raw = _http(f"{_S3}?{urllib.parse.urlencode(q)}")
        if raw is None:
            break
        xml = raw.decode()
        out.extend(pat.findall(xml))
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if "<IsTruncated>true</IsTruncated>" not in xml or not m:
            break
        token = m.group(1)
        time.sleep(0.1)
    return out


def archive_symbols(market: str, *, interval: str = "1d") -> list[str]:
    """The POINT-IN-TIME instrument universe: every symbol the archive ever published klines for.

    This, not `exchangeInfo`, is the universe. Measured: cm archive 272 vs exchangeInfo 30, so an
    exchangeInfo-driven collector omits 89% of instrument history and every one of the expired
    quarterlies a same-expiry basis study needs. Reconstructing a universe from today's live list
    is a look-ahead in the UNIVERSE and it fails toward a false null.
    """
    pref = f"data/futures/{market}/monthly/klines/"
    return sorted(p[len(pref):].rstrip("/") for p in s3_list(pref, delimiter="/"))


def archive_months(market: str, symbol: str, interval: str, kind: str = "klines") -> list[str]:
    """Months the archive actually publishes for this symbol -- LISTED, never generated.

    Returning the true file set is what makes "we fetched everything that exists" checkable. A
    generated month range makes a missing file indistinguishable from a month the contract did
    not trade in.
    """
    pref = (f"data/futures/{market}/monthly/{kind}/{symbol}/{interval}/" if kind == "klines"
            else f"data/futures/{market}/monthly/{kind}/{symbol}/")
    keys = s3_list(pref)
    return sorted({m.group(1) for k in keys if (m := re.search(r"(\d{4}-\d{2})\.zip$", k))})


def _rows_from_zip(raw: bytes) -> list[list[str]]:
    """CSV rows from a monthly zip, header rows dropped by CONTENT not by position.

    The archive grew a header row on 2022-07-01 and has none before it. A reader hardcoding
    `header=0` silently deletes the first real bar of every pre-2022-07 file -- no error, just a
    missing bar per month across the earliest months, which is exactly the regime an OOS split is
    starved for. Testing `row[0].isdigit()` is immune to the seam in both directions.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    return [r for r in csv.reader(io.StringIO(text)) if r and r[0].strip().isdigit()]


def _norm_ms(v: float) -> int:
    """Milliseconds. Binance flipped archive open_time to MICROseconds in the 2025+ files."""
    return int(v / 1000.0) if v > 1e14 else int(v)


def fetch_archive_klines(market: str, symbol: str, interval: str = "1d") -> dict[str, Any]:
    """One symbol's full archived kline history + the denominator that proves it is full."""
    months = archive_months(market, symbol, interval)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    base = f"{_VISION}/data/futures/{market}/monthly/klines/{symbol}/{interval}"

    def one(mo: str) -> tuple[str, bytes | None]:
        return mo, _http(f"{base}/{symbol}-{interval}-{mo}.zip")

    with ThreadPoolExecutor(max_workers=6) as pool:
        for mo, raw in pool.map(one, months):
            if raw is None:
                missing.append(mo)
                continue
            for r in _rows_from_zip(raw):
                rows.append({
                    "t": _norm_ms(float(r[0])), MARKER: CLOCK_VENUE, "k": f"kline{interval}",
                    "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "cl": float(r[4]),
                    "v": float(r[5]), "T": _norm_ms(float(r[6])), "qv": float(r[7]),
                    "n": int(float(r[8])), "src": "vision-archive",
                })
    rows.sort(key=lambda x: int(x["t"]))
    dedup: list[dict[str, Any]] = []
    for r in rows:
        if not dedup or r["t"] > dedup[-1]["t"]:
            dedup.append(r)
    return {"rows": dedup, "months_listed": len(months), "months_missing": missing,
            "dupes_dropped": len(rows) - len(dedup)}


# ------------------------------------------------------------------------------ REST route -----
def _df_rows(df: Any, kind: str, src: str) -> list[dict[str, Any]]:
    """A pandas kline frame from `crypto_source` -> venue-clock-stamped JSONL rows."""
    if df is None or len(df) == 0:
        return []
    out: list[dict[str, Any]] = []
    for rec in df.to_dict("records"):
        ts = rec.get("timestamp")
        row: dict[str, Any] = {"t": int(ts.value // 1_000_000), MARKER: CLOCK_VENUE,
                               "k": kind, "src": src}
        for src_key, dst in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "cl"),
                             ("volume", "v"), ("funding", "f"), ("taker_buy_frac", "tbf")):
            if src_key in rec:
                row[dst] = float(rec[src_key])
        out.append(row)
    return out


# ------------------------------------------------------------------------------- assertions ----
def contiguity(rows: list[dict[str, Any]], step_ms: int) -> dict[str, Any]:
    """Is this series actually contiguous, or did a cap quietly end it early?

    Returned rather than raised: a delivered quarterly legitimately STOPS, and a real interior
    hole (the archive has documented ones) is a fact to record, not a crash. What must never
    happen is the gap going unmeasured -- that is the whole truncation failure mode.
    """
    if len(rows) < 2:
        return {"n": len(rows), "gaps": [], "contiguous": len(rows) > 0}
    ts = [int(r["t"]) for r in rows]
    gaps = [{"after": datetime.fromtimestamp(a / 1000, UTC).date().isoformat(),
             "missing_periods": round((b - a) / step_ms) - 1}
            for a, b in pairwise(ts) if b - a > step_ms]
    return {"n": len(rows), "first": datetime.fromtimestamp(ts[0] / 1000, UTC).date().isoformat(),
            "last": datetime.fromtimestamp(ts[-1] / 1000, UTC).date().isoformat(),
            "gaps": gaps[:20], "n_gaps": len(gaps),
            "missing_periods_total": sum(g["missing_periods"] for g in gaps),
            "contiguous": not gaps}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    return len(rows)


# ------------------------------------------------------------------------------------ main -----
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", default="all",
                    choices=("all", "quarterly", "perps", "universe"))
    ap.add_argument("--roots", default=",".join(QUARTERLY_ROOTS))
    ap.add_argument("--interval", default="1d")
    args = ap.parse_args()
    roots = [r.strip() for r in args.roots.split(",") if r.strip()]
    started = datetime.now(tz=UTC).isoformat()
    man: dict[str, Any] = {
        "generated": started, "row": "R0462", "card": 31, "interval": args.interval,
        "clock_provenance_L1_46": {
            "marker_field": MARKER, "value": CLOCK_VENUE,
            "meaning": ("`t` is the VENUE's own bar-open stamp (ms, UTC); `T` is the venue's "
                        "bar-close stamp. No row written by this collector is receipt-stamped, "
                        "so no file here is mixed-clock."),
        },
        "universe": {}, "series": {}, "notes": [],
    }

    # ---- universe, from the ARCHIVE (never from exchangeInfo) --------------------------------
    cm_arch = archive_symbols("cm", interval=args.interval)
    um_arch = archive_symbols("um", interval=args.interval)
    live = coinm_instruments()
    cm_q = [s for s in cm_arch if re.search(r"_\d{6}$", s)]
    um_q = [s for s in um_arch if re.search(r"_\d{6}$", s)]
    man["universe"] = {
        "cm_archive_symbols": len(cm_arch), "um_archive_symbols": len(um_arch),
        "cm_live_exchangeInfo": len(live),
        "cm_quarterlies": len(cm_q), "um_quarterlies": len(um_q),
        "cm_quarterly_roots": sorted({re.sub(r"_\d{6}$", "", s) for s in cm_q}),
        "um_quarterly_roots": sorted({re.sub(r"_\d{6}$", "", s) for s in um_q}),
        "survivorship_note": (
            f"exchangeInfo shows {len(live)} live instruments; the archive holds {len(cm_arch)}. "
            f"Building the universe from the live list omits {len(cm_arch) - len(live)} "
            f"instruments (a LOOK-AHEAD IN THE UNIVERSE) and every expired quarterly with it."),
    }
    (OUT).mkdir(parents=True, exist_ok=True)
    if args.what == "universe":
        (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1), "utf-8")
        print(json.dumps(man["universe"], indent=1))
        return 0

    def record(name: str, rows: list[dict[str, Any]], step_ms: int,
               extra: dict[str, Any] | None = None) -> None:
        man["series"][name] = {**contiguity(rows, step_ms), **(extra or {})}

    # ---- QUARTERLIES ------------------------------------------------------------------------
    if args.what in ("all", "quarterly"):
        for root in roots:
            for sym in [s for s in cm_q if s.startswith(root + "_")]:
                res = fetch_archive_klines("cm", sym, args.interval)
                write_jsonl(OUT / "klines" / "cm" / f"{sym}.jsonl", res["rows"])
                record(f"cm/{sym}", res["rows"], _DAY_MS,
                       {"months_listed": res["months_listed"],
                        "months_missing": res["months_missing"],
                        "route": "vision-archive (dapi REST refuses expired symbols, -1121)"})
                print(f"cm {sym}: {len(res['rows'])} bars, "
                      f"{res['months_listed']} months listed, "
                      f"{len(res['months_missing'])} missing", flush=True)
        # USDT-M same-expiry counterparts. REST serves expired contracts on this book.
        um_roots = sorted({re.sub(r"_\d{6}$", "", s) for s in um_q})
        for sym in um_q:
            if not any(sym.startswith(r + "_") for r in um_roots):
                continue
            rows = _df_rows(fetch_klines(sym, interval=args.interval, start_ms=0),
                            f"kline{args.interval}", "fapi-rest")
            write_jsonl(OUT / "klines" / "um" / f"{sym}.jsonl", rows)
            record(f"um/{sym}", rows, _DAY_MS, {"route": "fapi REST (serves expired)"})
            print(f"um {sym}: {len(rows)} bars", flush=True)

    # ---- PERPS + the index legs -------------------------------------------------------------
    if args.what in ("all", "perps"):
        perps = [s["symbol"] for s in live if s.get("contractType") == "PERPETUAL"]
        pairs = sorted({s["pair"] for s in live})
        for sym in sorted(perps):
            for fn, kind, sub in (
                (fetch_coinm_klines, "kline", "klines"),
                (fetch_coinm_mark_klines, "mark", "mark"),
                (fetch_coinm_premium_klines, "premium", "premium"),
            ):
                rows = _df_rows(fn(sym, interval=args.interval, start_ms=0),
                                f"{kind}{args.interval}", "dapi-rest")
                write_jsonl(OUT / sub / "cm" / f"{sym}.jsonl", rows)
                record(f"cm/{sym}/{kind}", rows, _DAY_MS, {"route": "dapi REST"})
            frows = _df_rows(fetch_coinm_funding(sym), "funding", "dapi-rest")
            write_jsonl(OUT / "funding" / "cm" / f"{sym}.jsonl", frows)
            record(f"cm/{sym}/funding", frows, 8 * 3600 * 1000, {"route": "dapi REST"})
            um_sym = sym.replace("USD_PERP", "USDT")
            urows = _df_rows(fetch_funding(um_sym), "funding", "fapi-rest")
            write_jsonl(OUT / "funding" / "um" / f"{um_sym}.jsonl", urows)
            record(f"um/{um_sym}/funding", urows, 8 * 3600 * 1000, {"route": "fapi REST"})
            print(f"perp {sym}: funding cm={len(frows)} um={len(urows)}", flush=True)
        for pair in pairs:
            rows = _df_rows(fetch_coinm_index_klines(pair, interval=args.interval, start_ms=0),
                            f"index{args.interval}", "dapi-rest")
            write_jsonl(OUT / "index" / "cm" / f"{pair}.jsonl", rows)
            record(f"cm/{pair}/index", rows, _DAY_MS, {"route": "dapi REST (pair=)"})
            upair = pair + "T"
            urows = _df_rows(fetch_index_klines(upair, interval=args.interval, start_ms=0),
                             f"index{args.interval}", "fapi-rest")
            write_jsonl(OUT / "index" / "um" / f"{upair}.jsonl", urows)
            record(f"um/{upair}/index", urows, _DAY_MS, {"route": "fapi REST (pair=)"})
            print(f"index {pair}: cm={len(rows)} um={len(urows)}", flush=True)

    man["finished"] = datetime.now(tz=UTC).isoformat()
    man["totals"] = {
        "series": len(man["series"]),
        "rows": sum(v.get("n", 0) for v in man["series"].values()),
        "series_with_gaps": sum(1 for v in man["series"].values() if v.get("n_gaps")),
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1), "utf-8")
    print(json.dumps(man["totals"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
