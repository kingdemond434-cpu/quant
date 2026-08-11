#!/usr/bin/env python3
"""Universe OI/LS metrics + futures-klines history downloader (Bronze static ingestion).

Feeds the CROSS-SECTIONAL held-out OOS for the two pre-registered derivative sleeves
(oi_divergence, ls_contrarian in scripts/run_derivative_shadow.py). Single-asset history is a
construction mismatch for cross-sectional hypotheses, so this pulls the UNIVERSE.

FIELD MAPPING (construction-critical, pinned 2026-07-23 against libs/data/crypto_source.py):
  forward open_interest = /fapi/v1/openInterest = CONTRACTS -> archive `sum_open_interest`
      (NOT sum_open_interest_value, which is USD)
  forward ls_ratio = globalLongShortAccountRatio -> archive `count_long_short_ratio`
      (NOT sum_toptrader_long_short_ratio, which is the top-trader POSITION ratio)

SURVIVORSHIP: the universe is enumerated from the archive's own S3 listing (906 symbol dirs,
including delisted names), NOT from today's live universe -- the cross-section is what existed
then. Tranche 1 = symbols with metrics available by 2022-07-01 (deep cohort); later listings are
tranche 2 (directive oi-ls-universe-metrics-backfill).

Resumable, threaded, stdlib-only. Writes:
  data/lake/bronze/oi_ls_daily/{SYM}.jsonl   one row per day: daily MEAN of the 5-min series
                                             + first-bucket snapshot (for diff-verify vs the
                                             forward point-in-time collector)
  data/lake/bronze/futclose_daily/{SYM}.jsonl  daily futures closes from the SAME archive
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
MET_DIR = ROOT / "data/lake/bronze/oi_ls_daily"
PX_DIR = ROOT / "data/lake/bronze/futclose_daily"
S3 = ("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
      "?delimiter=/&prefix=data/futures/um/daily/metrics/")
BASE = "https://data.binance.vision/data/futures/um"
START = date(2021, 6, 1)
END = datetime.now(tz=UTC).date() - timedelta(days=1)
COHORT_PROBE = "2022-07-01"          # tranche-1 depth requirement
WORKERS = 20
_print_lock = threading.Lock()


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-oils-backfill"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _head_ok(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "quant-oils-backfill"})
        urllib.request.urlopen(req, timeout=8)
        return True
    except Exception:
        return False


def enumerate_symbols() -> list[str]:
    xml = _get(S3, timeout=30).decode()
    syms = re.findall(r"<Prefix>data/futures/um/daily/metrics/([A-Z0-9]+)/</Prefix>", xml)
    return sorted(s for s in syms if s.endswith("USDT"))


def probe_cohort(symbols: list[str]) -> list[str]:
    """Symbols whose metrics exist by the tranche-1 depth date (threaded HEAD probes)."""
    keep: list[str] = []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(
            _head_ok, f"{BASE}/daily/metrics/{s}/{s}-metrics-{COHORT_PROBE}.zip"): s
            for s in symbols}
        for f in as_completed(futs):
            if f.result():
                keep.append(futs[f])
    return sorted(keep)


def _months() -> list[str]:
    out, d = [], date(START.year, START.month, 1)
    while d <= END:
        out.append(f"{d.year:04d}-{d.month:02d}")
        d = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return out


def pull_klines(sym: str) -> int:
    """Monthly 1d futures klines -> daily closes jsonl. Same archive as the metrics."""
    out = PX_DIR / f"{sym}.jsonl"
    have: set[str] = set()
    if out.exists():
        for ln in out.read_text("utf-8").splitlines():
            with contextlib.suppress(Exception):
                have.add(json.loads(ln)["date"])
    rows = []
    for m in _months():
        if f"{m}-15" in have:                      # month already ingested (mid-month sentinel)
            continue
        url = f"{BASE}/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip"
        try:
            raw = _get(url)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                lines = zf.read(zf.namelist()[0]).decode().splitlines()
        except Exception:
            continue
        for ln in lines:
            p = ln.split(",")
            try:
                ts = int(p[0])
                ds = datetime.fromtimestamp(ts / 1000, tz=UTC).date().isoformat()
                if ds not in have:
                    rows.append({"date": ds, "close": float(p[4])})
                    have.add(ds)
            except Exception:
                continue
    # TAIL REPAIR (found 2026-08-11 via a starved breadth screen; R0085's "+0 closes x139" was
    # this): the monthly zip for the CURRENT month is only published after the month ends, so
    # in-month the loop above 404s and closes arrive in month-sized batches up to 31 days late --
    # while the metrics leg (daily zips) stays current. Every axis screen's TARGET feed was
    # therefore up to a month staler than its signals. Fetch the daily kline zips for the recent
    # gap exactly the way pull_metrics fetches its dailies. Bounded to 45 days: older holes are
    # the monthly loop's job and stay visible in its `missing` count.
    tail_start = max(START, END - timedelta(days=45))
    d = tail_start
    while d <= END:
        ds = d.isoformat()
        if ds not in have:
            url = f"{BASE}/daily/klines/{sym}/1d/{sym}-1d-{ds}.zip"
            try:
                raw = _get(url)
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    lines = zf.read(zf.namelist()[0]).decode().splitlines()
                for ln in lines:
                    p = ln.split(",")
                    try:
                        ts = int(p[0])
                        pd_ = datetime.fromtimestamp(ts / 1000, tz=UTC).date().isoformat()
                        if pd_ not in have:
                            rows.append({"date": pd_, "close": float(p[4])})
                            have.add(pd_)
                    except (ValueError, IndexError):
                        continue
            except Exception:
                pass                      # unpublished/delisted day; the missing count keeps it visible
        d += timedelta(days=1)
    if rows:
        rows.sort(key=lambda r: r["date"])
        with out.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return len(rows)


def pull_metrics(sym: str) -> tuple[int, int]:
    """Daily metrics zips -> one daily row (mean of 5-min series + first-bucket snapshot)."""
    out = MET_DIR / f"{sym}.jsonl"
    have: set[str] = set()
    if out.exists():
        for ln in out.read_text("utf-8").splitlines():
            with contextlib.suppress(Exception):
                have.add(json.loads(ln)["date"])
    n_new = n_miss = 0
    buf: list[dict] = []
    d = START
    while d <= END:
        ds = d.isoformat()
        d += timedelta(days=1)
        if ds in have:
            continue
        try:
            raw = _get(f"{BASE}/daily/metrics/{sym}/{sym}-metrics-{ds}.zip", timeout=15)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                lines = zf.read(zf.namelist()[0]).decode().splitlines()
            hdr = lines[0].split(",")
            oi_i = hdr.index("sum_open_interest")            # CONTRACTS (matches forward)
            ls_i = hdr.index("count_long_short_ratio")       # global accounts (matches forward)
            tk_i = hdr.index("sum_taker_long_short_vol_ratio")
            ois, lss, tks = [], [], []
            for ln in lines[1:]:
                p = ln.split(",")
                try:
                    ois.append(float(p[oi_i]))
                    lss.append(float(p[ls_i]))
                    tks.append(float(p[tk_i]))
                except Exception:
                    continue
            if ois:
                buf.append({
                    "date": ds,
                    "oi": round(sum(ois) / len(ois), 3),
                    "ls": round(sum(lss) / len(lss), 5),
                    "taker": round(sum(tks) / len(tks), 5),
                    "oi_first": round(ois[0], 3),            # 00:00 bucket, diff-verify anchor
                    "ls_first": round(lss[0], 5),
                })
                n_new += 1
        except Exception:
            n_miss += 1
        if len(buf) >= 100:
            with out.open("a", encoding="utf-8") as f:
                for r in buf:
                    f.write(json.dumps(r) + "\n")
            buf = []
    if buf:
        with out.open("a", encoding="utf-8") as f:
            for r in buf:
                f.write(json.dumps(r) + "\n")
    return n_new, n_miss


def worker(sym: str) -> str:
    k = pull_klines(sym)
    n, m = pull_metrics(sym)
    with _print_lock:
        print(f"{sym}: +{n} metric days ({m} missing), +{k} closes", flush=True)
    return sym


def main() -> None:
    MET_DIR.mkdir(parents=True, exist_ok=True)
    PX_DIR.mkdir(parents=True, exist_ok=True)
    allsyms = enumerate_symbols()
    print(f"archive lists {len(allsyms)} USDT perp symbol dirs (incl. delisted)", flush=True)
    cohort = probe_cohort(allsyms)
    print(f"tranche-1 cohort (metrics by {COHORT_PROBE}): {len(cohort)} symbols", flush=True)
    # TRANCHE 2 (directive oi-ls-universe-metrics-backfill: "the full universe 2021->now").
    # The probe orders, it no longer excludes: deep-cohort symbols download first (they feed the
    # cross-sectional OOS harness), then every later listing. Idempotent per-day skips make the
    # first full pass the only expensive one; after that the daily cron only tops up.
    tranche2 = [s for s in allsyms if s not in set(cohort)]
    ordered = cohort + tranche2
    print(f"tranche-2 (later listings): {len(tranche2)} symbols -- ingested after tranche 1",
          flush=True)
    done = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(worker, s) for s in ordered]
        for _ in as_completed(futs):
            done += 1
            if done % 10 == 0:
                with _print_lock:
                    print(f"--- {done}/{len(ordered)} symbols complete ---", flush=True)
    print(f"DONE: {done} symbols", flush=True)


if __name__ == "__main__":
    main()
