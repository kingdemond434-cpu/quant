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
import urllib.error
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


def _head_ok(url: str) -> bool | None:
    """True/False for the object, and None when the network could not answer (R0466).

    None IS A THIRD STATE ON PURPOSE. `except Exception: return False` made a 403, a 429, a 5xx
    and a timeout indistinguishable from the 404 that means "this symbol genuinely has no metrics
    at the cohort date". Every one of those silently DROPPED the symbol from the tranche-1 cohort,
    so a venue throttling a 20-thread HEAD sweep -- the single most likely thing to happen to this
    exact code -- would hand the study a quietly smaller universe and nothing anywhere would say
    so. A blocked ground reading as an empty one is WS-005/L1.28a, and here it is also a silent
    change to the UNIVERSE a result is computed over.
    """
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "quant-oils-backfill"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as exc:
        return False if exc.code == 404 else None      # only 404 is "it is not there"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def enumerate_symbols() -> list[str]:
    xml = _get(S3, timeout=30).decode()
    syms = re.findall(r"<Prefix>data/futures/um/daily/metrics/([A-Z0-9]+)/</Prefix>", xml)
    return sorted(s for s in syms if s.endswith("USDT"))


def probe_cohort(symbols: list[str]) -> tuple[list[str], list[str]]:
    """(cohort, unknown) -- symbols whose metrics exist by the tranche-1 depth date, and the ones
    the archive would not answer for.

    THE SECOND LIST IS THE POINT. It used to not exist: an unanswered probe fell into the same
    bucket as a confirmed-absent one and the caller could not have told the difference if it had
    wanted to. Returning them separately is what lets main() refuse to treat a probe outage as a
    universe definition (R0466).
    """
    keep: list[str] = []
    unknown: list[str] = []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(
            _head_ok, f"{BASE}/daily/metrics/{s}/{s}-metrics-{COHORT_PROBE}.zip"): s
            for s in symbols}
        for f in as_completed(futs):
            got = f.result()
            if got is None:
                unknown.append(futs[f])
            elif got:
                keep.append(futs[f])
    return sorted(keep), sorted(unknown)


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
    cohort, unknown = probe_cohort(allsyms)
    print(f"tranche-1 cohort (metrics by {COHORT_PROBE}): {len(cohort)} symbols", flush=True)
    if unknown:
        # LOUD, and it stops the run. A cohort built while the archive was refusing some fraction
        # of the probes is not a smaller cohort, it is an UNKNOWN one, and backfilling against it
        # would bake a probe outage into the universe every downstream number is computed over.
        raise SystemExit(
            f"REFUSING TO DEFINE THE UNIVERSE: {len(unknown)} of {len(allsyms)} cohort probes "
            f"were not answered (not a 404 -- refused, timed out, or the transport failed), so "
            f"whether these symbols belong in tranche-1 is UNMEASURED, not False: "
            f"{', '.join(unknown[:12])}{' ...' if len(unknown) > 12 else ''}. Re-run when the "
            f"archive answers; a cohort silently shrunk by a throttle is a false universe.")
    done = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(worker, s) for s in cohort]
        for _ in as_completed(futs):
            done += 1
            if done % 10 == 0:
                with _print_lock:
                    print(f"--- {done}/{len(cohort)} symbols complete ---", flush=True)
    print(f"DONE: {done} symbols", flush=True)


if __name__ == "__main__":
    main()
