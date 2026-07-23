#!/usr/bin/env python3
"""Bulk-download Binance futures metrics history (OI + long/short) for the OI/LS backfill OOS.
data.binance.vision daily metrics zips, BTCUSDT, 2021-06 -> today. Aggregates 5-min -> daily.
Bronze static ingestion (dependency-free stdlib). Idempotent, resilient to missing days."""
import io
import json
import urllib.request
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

OUT = Path("/home/quant/quant-platform/data/oi_ls_history.jsonl")
BASE = "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT"
start = date(2021, 6, 1)
end = datetime.now(tz=UTC).date() - timedelta(days=1)

done = set()
if OUT.exists():
    for ln in OUT.read_text("utf-8").splitlines():
        try:
            done.add(json.loads(ln)["date"])
        except Exception:
            pass

d = start
n_new = n_miss = 0
rows = []
while d <= end:
    ds = d.isoformat()
    if ds in done:
        d += timedelta(days=1); continue
    url = f"{BASE}/BTCUSDT-metrics-{ds}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-metrics"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            lines = zf.read(zf.namelist()[0]).decode().splitlines()
        hdr = lines[0].split(",")
        oi_i = hdr.index("sum_open_interest_value")
        ls_i = hdr.index("sum_toptrader_long_short_ratio")
        tk_i = hdr.index("sum_taker_long_short_vol_ratio")
        ois, lss, tks = [], [], []
        for ln in lines[1:]:
            p = ln.split(",")
            try:
                ois.append(float(p[oi_i])); lss.append(float(p[ls_i])); tks.append(float(p[tk_i]))
            except Exception:
                pass
        if ois:
            rows.append({"date": ds,
                         "oi_value": round(sum(ois) / len(ois), 2),
                         "ls_ratio": round(sum(lss) / len(lss), 5),
                         "taker_ratio": round(sum(tks) / len(tks), 5)})
            n_new += 1
    except Exception:
        n_miss += 1
    if len(rows) >= 50:
        with OUT.open("a", encoding="utf-8") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
        rows = []
    d += timedelta(days=1)

if rows:
    with OUT.open("a", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
print(f"DONE: {n_new} new days, {n_miss} missing, total file {OUT}")
