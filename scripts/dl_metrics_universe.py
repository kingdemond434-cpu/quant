#!/usr/bin/env python3
"""Bulk-download Binance futures metrics history for the FULL perp universe (OI/LS OOS backfill).

Closes work order 'oi-ls-universe-metrics-backfill': the registered OI/LS hypotheses
(oi_divergence, ls_contrarian) are CROSS-SECTIONAL over the perp universe, so a single-asset
backfill is a construction mismatch (the kimchi-bug class). This ingests
data.binance.vision/data/futures/um/daily/metrics/<SYMBOL>/ for every symbol the FORWARD
collector tracks (data/crypto_metrics.parquet -- the OOS must mirror that universe), aggregating
5-min rows -> one daily row per (symbol, date).

CLOCK PROVENANCE (L1.46): the daily key is the archive zip's VENUE UTC calendar date; values are
means over that UTC day. The 5-min source rows are venue-stamped. Any OOS join must decide its
label lag explicitly against the forward collector's convention -- that alignment (and its
diff-verify vs crypto_metrics.parquet) is the separate, careful half of the work order
(directive-overdue-oi-ls-oos-alignment-fix) and is deliberately NOT decided here. Bronze only.

DISK: raw zips are NOT persisted -- binance.vision is a stable, re-fetchable public archive and
tape-disk-deadline names disk as the binding constraint; only the ~70MB daily aggregate is kept.
The Bronze-forever rule binds hardest on data destroyed at source; this source is not.

Discovery is via the S3 listing API (2 requests/symbol) rather than blind date-probing
(~250k requests). Idempotent: (symbol, date) pairs already in the output are skipped, so it
resumes from wherever it died. Sequential-with-small-pool on purpose: 6 workers is polite to a
public CDN and still finishes in hours.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:          # `python scripts/x.py` puts scripts/ on sys.path, not ROOT
    sys.path.insert(0, str(ROOT))

from libs.ops.lawful import guard  # noqa: E402

OUT = ROOT / "data/oi_ls_universe.jsonl"
COVERAGE = ROOT / "data/oi_ls_universe_coverage.json"
LIST_BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
GET_BASE = "https://data.binance.vision/"
PREFIX = "data/futures/um/daily/metrics/"
WORKERS = 6
_KEY_RE = re.compile(r"<Key>([^<]+\.zip)</Key>")
_TRUNC_RE = re.compile(r"<IsTruncated>true</IsTruncated>")
_write_lock = threading.Lock()


def _http(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-metrics-universe"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def list_symbol_zips(symbol: str) -> list[str]:
    """All metrics zip keys for one symbol via the S3 listing API (paginated, ~2 calls)."""
    keys: list[str] = []
    marker = ""
    while True:
        q = urllib.parse.urlencode({"prefix": f"{PREFIX}{symbol}/", "marker": marker})
        xml = _http(f"{LIST_BASE}?{q}").decode("utf-8", "replace")
        page = [k for k in _KEY_RE.findall(xml) if k.endswith(".zip")]
        keys.extend(page)
        if not _TRUNC_RE.search(xml) or not page:
            return keys
        marker = page[-1]


def aggregate_day(csv_lines: list[str]) -> dict[str, float] | None:
    """Mean of the 5-min columns over one UTC day. Returns None when no parseable row exists."""
    hdr = csv_lines[0].split(",")
    try:
        oi_i = hdr.index("sum_open_interest_value")
        ls_i = hdr.index("sum_toptrader_long_short_ratio")
        tk_i = hdr.index("sum_taker_long_short_vol_ratio")
    except ValueError:
        return None
    ois, lss, tks = [], [], []
    for ln in csv_lines[1:]:
        p = ln.split(",")
        with contextlib.suppress(ValueError, IndexError):
            o, ls_v, tk = float(p[oi_i]), float(p[ls_i]), float(p[tk_i])
            ois.append(o)
            lss.append(ls_v)
            tks.append(tk)
    if not ois:
        return None
    return {"oi_value": round(sum(ois) / len(ois), 2),
            "ls_ratio": round(sum(lss) / len(lss), 5),
            "taker_ratio": round(sum(tks) / len(tks), 5)}


def _universe() -> list[str]:
    import pandas as pd
    df = pd.read_parquet(ROOT / "data/crypto_metrics.parquet", columns=["symbol"])
    return sorted(df["symbol"].unique().tolist())


def _done() -> set[tuple[str, str]]:
    have: set[tuple[str, str]] = set()
    if OUT.exists():
        with OUT.open(encoding="utf-8") as f:
            for ln in f:
                with contextlib.suppress(Exception):
                    r = json.loads(ln)
                    have.add((r["symbol"], r["date"]))
    return have


def _work_symbol(symbol: str, have: set[tuple[str, str]], stats: dict) -> None:
    try:
        keys = list_symbol_zips(symbol)
    except Exception as e:                              # listing failure = symbol unmeasured, said
        stats.setdefault("list_failed", []).append(f"{symbol}: {e}")
        return
    rows, misses = [], 0
    for key in keys:
        ds = key.rsplit("-metrics-", 1)[-1].removesuffix(".zip")
        if (symbol, ds) in have:
            continue
        try:
            raw = _http(GET_BASE + key)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                lines = zf.read(zf.namelist()[0]).decode("utf-8", "replace").splitlines()
            agg = aggregate_day(lines)
            if agg is not None:
                rows.append(json.dumps({"symbol": symbol, "date": ds, **agg}))
        except Exception:
            misses += 1
        if len(rows) >= 200:
            with _write_lock, OUT.open("a", encoding="utf-8") as f:
                f.write("\n".join(rows) + "\n")
            rows = []
    if rows:
        with _write_lock, OUT.open("a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    with _write_lock:
        stats["symbols_done"] = stats.get("symbols_done", 0) + 1
        stats["misses"] = stats.get("misses", 0) + misses
        print(f"[{stats['symbols_done']}] {symbol}: {len(keys)} archive days, {misses} misses",
              flush=True)


def _coverage() -> None:
    cov: dict[str, dict] = {}
    with OUT.open(encoding="utf-8") as f:
        for ln in f:
            with contextlib.suppress(Exception):
                r = json.loads(ln)
                c = cov.setdefault(r["symbol"], {"days": 0, "first": r["date"], "last": r["date"]})
                c["days"] += 1
                c["first"] = min(c["first"], r["date"])
                c["last"] = max(c["last"], r["date"])
    COVERAGE.write_text(json.dumps(
        {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "n_symbols": len(cov), "n_rows": sum(c["days"] for c in cov.values()),
         "symbols": cov}, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    guard()
    syms = _universe()
    have = _done()
    print(f"universe={len(syms)} symbols; {len(have)} (symbol,day) rows already on disk",
          flush=True)
    stats: dict = {}
    pending = list(syms)
    threads: list[threading.Thread] = []

    def runner() -> None:
        while True:
            with _write_lock:
                if not pending:
                    return
                s = pending.pop()
            _work_symbol(s, have, stats)

    for _ in range(WORKERS):
        t = threading.Thread(target=runner, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    _coverage()
    failed = stats.get("list_failed", [])
    print(f"DONE: {stats.get('symbols_done', 0)} symbols, {stats.get('misses', 0)} missing days, "
          f"{len(failed)} symbols UNLISTED (unmeasured, not empty): {failed[:5]}", flush=True)
    return 1 if failed and not stats.get("symbols_done") else 0


if __name__ == "__main__":
    raise SystemExit(main())
