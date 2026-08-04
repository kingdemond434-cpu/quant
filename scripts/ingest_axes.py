#!/usr/bin/env python3
"""ORTHOGONAL-AXES INGESTER (principal order 2026-07-21; Bronze carve-out class: stdlib-only,
static files, no scrapers).

Ingests the top of the hunt-now list:
 1. FED NET-LIQUIDITY -- WALCL + RRP (FRED csv, no key) + TGA daily (Treasury FiscalData API)
    -> bronze/fed/, plus a clearly-labelled DERIVED net_liquidity series (self-computed, the
    free-first reconstruction of every "global liquidity" vendor chart).
 2. BINANCE FUTURES METRICS BACKFILL -- data.binance.vision daily metrics zips (5-min rows:
    sum open interest, top-trader long/short ACCOUNT and POSITION ratios, taker buy/sell
    ratio). The forward collector (oi_ls_taker) has ~22d; this backfills years. Raw zips to
    bronze/binance_metrics/<SYM>/, skip-existing so the daily cron keeps it current forever.
 3. FARSIDE ETF FLOWS -- attempted; Cloudflare 403s datacenter IPs. On failure this registers
    a dated directive (alternate route: miner web-fetch lane or issuer-page reconstruction)
    instead of pretending. Honest residue beats silent absence.

Verify-don't-trust: each ingester prints row/byte counts + a sample-parse check; the gauntlet
still runs its own diffs before any pipeline consumes these.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import certifi

ROOT = Path("/home/quant/quant-platform")
BRONZE = ROOT / "data/lake/bronze"
CTX = ssl.create_default_context(cafile=certifi.where())
UA = {"User-Agent": "Mozilla/5.0 (research; solo desk; contact via repo)"}

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
METRICS_START = date(2023, 1, 1)


def curl(url: str, timeout: int = 90) -> bytes:
    """Some hosts (FRED, Treasury) serve curl but hang urllib -- TLS fingerprint blocking.
    Verified 2026-07-21: curl instant, urllib timed out twice on the same URL."""
    import subprocess
    r = subprocess.run(
        ["curl", "-sSL", "--compressed", "--max-time", str(timeout),
         "-A", "Mozilla/5.0 (research; solo quant desk)", url],
        capture_output=True, timeout=timeout + 15)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl failed rc={r.returncode}: {r.stderr[:160]!r}")
    return r.stdout


def fetch(url: str, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for attempt in (1, 2):                       # one retry -- transient read timeouts
        try:
            r = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
                return resp.read()
        except Exception as e:
            last = e
            time.sleep(3 * attempt)
    # `raise None` is a TypeError that MASKS the real network failure -- found by the type gate
    # when scripts/ entered it (2026-07-25).
    raise last if last is not None else RuntimeError(f"fetch failed with no exception: {url}")


# ---------------- 1. Fed net-liquidity ----------------
def ingest_fed() -> None:
    """Fed liquidity plumbing from PRIMARY sources (NY Fed + Treasury). FRED is IP-blocked
    from this host since 2026-07-21 -- these are the upstream publishers anyway."""
    out = BRONZE / "fed"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")

    # --- RRP: NY Fed repo operations (per-operation detail) ---
    rrp_daily: dict[str, float] = {}
    raw = curl("https://markets.newyorkfed.org/api/rp/reverserepo/propositions/"
               "search.json?startDate=2015-01-01", timeout=120)
    (out / f"nyfed_rrp_{stamp}.json").write_bytes(raw)
    for op in json.loads(raw).get("repo", {}).get("operations", []):
        if "Reverse" in (op.get("operationType") or ""):
            d = op.get("operationDate")
            rrp_daily[d] = rrp_daily.get(d, 0.0) + float(op.get("totalAmtAccepted") or 0)
    print(f"  fed/RRP (NY Fed): {len(rrp_daily):,} days, latest "
          f"{max(rrp_daily) if rrp_daily else 'n/a'}")

    # --- SOMA: the Fed's actual holdings (WALCL's main component) ---
    soma_total: dict[str, float] = {}
    raw = curl("https://markets.newyorkfed.org/api/soma/summary.json", timeout=120)
    (out / f"nyfed_soma_{stamp}.json").write_bytes(raw)
    for row in json.loads(raw).get("soma", {}).get("summary", []):
        tot = 0.0
        for k in ("mbs", "cmbs", "tips", "frn", "tipsInflationCompensation",
                  "notesbonds", "bills", "agencies"):
            try:  # noqa: SIM105 -- suppress import avoided in this stdlib-lean ingester
                tot += float(row.get(k) or 0)
            except (TypeError, ValueError):
                pass
        if tot:
            soma_total[row["asOfDate"]] = tot
    print(f"  fed/SOMA (NY Fed): {len(soma_total):,} obs, latest "
          f"{max(soma_total) if soma_total else 'n/a'}")

    # --- TGA: Treasury DTS (recent-first, stop at 2020) ---
    tga: dict[str, str] = {}
    page = 1
    while page < 40:
        u = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/"
             "dts/operating_cash_balance?fields=record_date,account_type,open_today_bal"
             f"&page%5Bsize%5D=1000&page%5Bnumber%5D={page}&sort=-record_date")
        d = json.loads(curl(u, timeout=120))
        recs = d.get("data", [])
        for rec in recs:
            if "Treasury General Account" in (rec.get("account_type") or ""):
                v = rec.get("open_today_bal")
                if v and v != "null":
                    tga[rec["record_date"]] = v
        if not recs or not d.get("links", {}).get("next") or recs[-1]["record_date"] < "2020-01-01":
            break
        page += 1
    (out / f"TGA_daily_{stamp}.csv").write_text(
        "date,tga_open_musd\n" + "\n".join(f"{k},{v}" for k, v in sorted(tga.items())), "utf-8")
    print(f"  fed/TGA (Treasury): {len(tga):,} obs")

    # --- DERIVED net liquidity, self-computed ---
    def ffill(d: dict, on: str):
        ks = [k for k in d if k <= on]
        return d[max(ks)] if ks else None

    lines = ["date,soma_usd,rrp_usd,tga_musd,net_liquidity_busd  # DERIVED self-computed "
             "(SOMA - RRP - TGA); FRED WALCL unavailable from this host"]
    for day in sorted(tga):
        so, rr = ffill(soma_total, day), ffill(rrp_daily, day)
        if so is None:
            continue
        net = (so - (rr or 0.0) - float(tga[day]) * 1e6) / 1e9
        lines.append(f"{day},{so:.0f},{(rr or 0):.0f},{tga[day]},{net:.1f}")
    (out / "net_liquidity_DERIVED.csv").write_text("\n".join(lines), "utf-8")
    print(f"  fed/net_liquidity_DERIVED: {len(lines)-1:,} rows")
    if len(lines) > 1:
        print(f"    latest: {lines[-1]}")


# ---------------- 2. Binance metrics backfill ----------------
def ingest_binance_metrics(max_files: int | None = None) -> None:
    base = "https://data.binance.vision/data/futures/um/daily/metrics"
    got = skipped = missing = 0
    end = datetime.now(UTC).date() - timedelta(days=1)
    for sym in SYMBOLS:
        out = BRONZE / "binance_metrics" / sym
        out.mkdir(parents=True, exist_ok=True)
        d = METRICS_START
        while d <= end:
            fn = f"{sym}-metrics-{d.isoformat()}.zip"
            fp = out / fn
            if fp.exists() and fp.stat().st_size > 0:
                skipped += 1
            else:
                try:
                    fp.write_bytes(fetch(f"{base}/{sym}/{fn}", timeout=45))
                    got += 1
                    if max_files and got >= max_files:
                        print(f"  metrics: tranche cap {max_files} hit "
                              f"(got {got}, have {skipped}, missing {missing})")
                        return
                except Exception:
                    missing += 1              # early dates don't exist for every symbol
                time.sleep(0.15)              # be polite to the public bucket
            d += timedelta(days=1)
    print(f"  metrics: downloaded {got}, already had {skipped}, not-on-server {missing}")


def verify_metrics_sample() -> None:
    zips = sorted((BRONZE / "binance_metrics" / "BTCUSDT").glob("*.zip"))
    if not zips:
        print("  metrics VERIFY: no files yet")
        return
    with zipfile.ZipFile(zips[-1]) as z:
        name = z.namelist()[0]
        head = z.read(name).decode().splitlines()
    print(f"  metrics VERIFY ({zips[-1].name}): {len(head)-1} rows")
    print(f"    columns: {head[0]}")
    need = ("sum_toptrader_long_short_ratio", "count_long_short_ratio",
            "sum_taker_long_short_vol_ratio")
    ok = all(any(n in head[0] for n in (c,)) for c in need)
    print(f"    positioning columns present: {ok}")


# ---------------- 3. Farside (expected 403 -> directive) ----------------
def ingest_farside() -> None:
    out = BRONZE / "etf_flows"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    try:
        raw = fetch("https://farside.co.uk/btc/", timeout=30)
        (out / f"farside_btc_{stamp}.html").write_bytes(raw)
        print(f"  farside: fetched {len(raw):,}b (snapshot saved)")
    except Exception as e:
        print(f"  farside: BLOCKED from VPS ({e!r}) -- registering directive for alternate route")
        dp = ROOT / "data/max_audit_directives.json"
        ds = json.loads(dp.read_text()) if dp.exists() else []
        if not any(x.get("id") == "etf-flows-alt-route" for x in ds):
            ds.append({"id": "etf-flows-alt-route",
                       "msg": "Farside ETF flow tables 403 datacenter IPs (Cloudflare). Route via "
                              "the miner/dig web-fetch lane (Claude sessions CAN read it) writing "
                              "daily snapshots to bronze/etf_flows/, or reconstruct from issuer "
                              "pages (shares outstanding x NAV). Post-2024 marginal flow driver -- "
                              "do not leave dark.",
                       "due": "2026-07-24T23:59:00+00:00"})
            dp.write_text(json.dumps(ds, indent=1))


def ingest_wikipedia() -> None:
    """Attention factor: per-article daily pageviews, official API, cleaner + longer than
    Google Trends (addenda item 66). Full history per article since 2015-07."""
    out = BRONZE / "wikipedia"
    out.mkdir(parents=True, exist_ok=True)
    for art in ("Bitcoin", "Ethereum", "Cryptocurrency", "Solana", "Dogecoin",
                "Binance", "Coinbase"):
        fp = out / f"{art}_daily.json"
        u = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
             f"en.wikipedia/all-access/user/{art}/daily/20150701/"
             + datetime.now(tz=UTC).strftime("%Y%m%d"))
        raw = fetch(u, timeout=60)
        fp.write_bytes(raw)
        n = raw.count(b'"views"')
        print(f"  wikipedia/{art}: {n:,} daily obs")


def ingest_crossasset() -> None:
    """Risk-on/off layer at $0 (addenda item 58): Stooq full-history CSVs + CBOE VIX +
    UST yield curve. Fenced per-source -- symbol availability varies."""
    out = BRONZE / "crossasset"
    out.mkdir(parents=True, exist_ok=True)
    for sym, label in (("^spx", "SPX"), ("^ndq", "NASDAQ"), ("xauusd", "GOLD"),
                       ("cl.f", "WTI"), ("dx.f", "DXY_fut")):
        try:
            raw = fetch(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=45)
            if len(raw) > 1000 and b"Date" in raw[:100]:
                (out / f"stooq_{label}.csv").write_bytes(raw)
                print(f"  crossasset/{label}: {raw.count(chr(10).encode()):,} rows")
            else:
                print(f"  crossasset/{label}: stooq returned no data (symbol?)")
        except Exception as e:
            print(f"  crossasset/{label}: FAILED {e!r}")
    try:
        raw = fetch("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
                    timeout=60)
        (out / "VIX_history.csv").write_bytes(raw)
        print(f"  crossasset/VIX: {raw.count(chr(10).encode()):,} rows (CBOE official)")
    except Exception as e:
        print(f"  crossasset/VIX: FAILED {e!r}")
    got = 0
    for yr in range(2018, datetime.now(tz=UTC).year + 1):
        try:
            u = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                 f"daily-treasury-rates.csv/{yr}/all?type=daily_treasury_yield_curve"
                 f"&field_tdr_date_value={yr}&page&_format=csv")
            raw = fetch(u, timeout=60)
            if len(raw) > 500:
                (out / f"ust_curve_{yr}.csv").write_bytes(raw)
                got += 1
        except Exception:
            pass
    print(f"  crossasset/UST curve: {got} yearly files")


def ingest_mining() -> None:
    """Miner-economics axis (addenda item 73/energy layer): blockchain.com charts API,
    free, no key -- hashrate + miner revenue since 2009."""
    out = BRONZE / "mining"
    out.mkdir(parents=True, exist_ok=True)
    for chart in ("hash-rate", "miners-revenue", "difficulty"):
        raw = fetch(f"https://api.blockchain.info/charts/{chart}"
                    "?timespan=all&format=csv&sampled=false", timeout=90)
        (out / f"{chart}.csv").write_bytes(raw)
        print(f"  mining/{chart}: {raw.count(chr(10).encode()):,} rows")


def main() -> None:
    tranche = int(sys.argv[sys.argv.index("--tranche") + 1]) if "--tranche" in sys.argv else None
    for label, fn in [("FED NET-LIQUIDITY", ingest_fed),
                      ("FARSIDE ETF FLOWS", ingest_farside),
                      ("BINANCE METRICS BACKFILL",
                       lambda: ingest_binance_metrics(max_files=tranche)),
                      ("METRICS VERIFY", verify_metrics_sample),
                      ("WIKIPEDIA ATTENTION", ingest_wikipedia),
                      ("CROSS-ASSET", ingest_crossasset),
                      ("MINING ECONOMICS", ingest_mining)]:
        print(f"=== {label} ===")
        try:
            fn()
        except Exception as e:                    # fenced: one axis failing never kills the rest
            print(f"  {label} FAILED: {e!r} -- continuing")
    print("=== BRONZE TOTALS ===")
    for sub in ("fed", "binance_metrics", "etf_flows", "cme", "wikipedia", "crossasset", "mining"):
        p = BRONZE / sub
        if p.exists():
            n = sum(1 for _ in p.rglob("*") if _.is_file())
            b = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            print(f"  {sub:<16} {n:>6} files  {b/1e6:>9.1f} MB")


if __name__ == "__main__":
    main()
