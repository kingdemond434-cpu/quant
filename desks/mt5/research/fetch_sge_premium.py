"""Shanghai gold premium: the price of physical gold in China against the international price.

THE MECHANISM, WHICH IS WHY THIS IS WORTH FETCHING

China is the largest physical gold consumer, and its domestic market is not freely arbitrageable:
bullion import requires a PBoC licence, so the SGE price can and does detach from London/COMEX.
The spread between them is therefore not a quote artefact — it is a direct read on physical
demand pressure that cannot equalise itself.

    premium > 0   domestic demand exceeding licensed import supply
    premium < 0   domestic weakness, or import quota running ahead of demand

The premium widened sharply through 2013 and 2016 physical-buying episodes and went NEGATIVE
during 2020 Chinese demand collapse while the Western price rallied — the two markets moving
oppositely, which no single-venue feed can see. For a desk whose armed book is three legs of
XAUUSD, a demand signal orthogonal to the Western session is worth more than another Western
indicator.

    XAU_SGE_USD = SGE_Au9999_CNY_per_gram * 31.1035 / USDCNY      (USD per troy ounce)
    premium     = XAU_SGE_USD - LBMA_PM_USD

WHAT THIS MODULE WILL NOT DO

The SGE publishes Au99.99 benchmark prices, but not through a documented, stable, free JSON API,
and its site structure changes. Every "free SGE API" this desk could verify was either a
scraped mirror with no provenance or behind a paid wall.

So this fails closed. If it cannot obtain a genuine SGE print it writes UNAVAILABLE and stops.
It does NOT interpolate, does not carry the last value forward across a gap, and does not
substitute a proxy while calling it SGE. A fabricated premium would be worse than no premium:
the whole value of this series is that it disagrees with the Western price, so a filled-in
version would disagree in invented places and the desk would trade the invention.

Provenance is recorded per row — which source, fetched when — because a number whose origin is
unknown cannot be audited later, and this series will be used to justify positions.

    python research/fetch_sge_premium.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import DATA, REPORTS  # noqa: E402

OUT = DATA / "lake"
OUT.mkdir(parents=True, exist_ok=True)

GRAMS_PER_TROY_OZ = 31.1034768

#: LBMA PM fix via FRED — free, no key, long history. The international leg.
LBMA_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GOLDPMGBD228NLBM"
#: USDCNY via FRED, same terms.
USDCNY_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS"

#: Candidate SGE sources, tried in order. Each must yield a dated Au99.99 CNY/gram price.
#: Declared as data so adding a source is a one-line change and its provenance is explicit.
SGE_SOURCES = [
    {"name": "sge_official_json",
     "url": "https://www.sge.com.cn/graph/quotations",
     "kind": "json",
     "note": "SGE official quotations endpoint; structure is not contractual and may change"},
]


def _fred_csv(url: str, col: str, timeout: int = 45) -> pd.Series | None:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:                                        # noqa: BLE001
        print(f"  {col}: {type(exc).__name__}: {exc}", flush=True)
        return None
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    s = df.dropna(subset=[date_col]).set_index(date_col)[val_col].dropna()
    s.name = col
    return s if len(s) else None


def fetch_sge() -> tuple[pd.Series | None, str]:
    """Au99.99 in CNY per gram. Returns (series, provenance) or (None, reason)."""
    for src in SGE_SOURCES:
        try:
            r = requests.get(src["url"], timeout=45,
                             headers={"User-Agent": "quant-research-desk/1.0"})
            if r.status_code != 200:
                print(f"  {src['name']}: HTTP {r.status_code}", flush=True)
                continue
            if src["kind"] == "json":
                payload = r.json()
                rows = payload if isinstance(payload, list) else payload.get("data") or []
                recs = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    var = str(row.get("instid") or row.get("variety") or "")
                    if "Au99.99" not in var and "Au9999" not in var.replace(".", ""):
                        continue
                    d = row.get("date") or row.get("time") or row.get("updatetime")
                    v = row.get("close") or row.get("lastprice") or row.get("price")
                    if d is None or v is None:
                        continue
                    try:
                        recs.append((pd.to_datetime(str(d)[:10]), float(v)))
                    except (ValueError, TypeError):
                        continue
                if recs:
                    s = pd.Series(dict(recs)).sort_index()
                    s.name = "sge_au9999_cny_g"
                    return s, src["name"]
        except Exception as exc:                                    # noqa: BLE001
            print(f"  {src['name']}: {type(exc).__name__}: {exc}", flush=True)
            continue
    return None, "no configured SGE source returned a usable Au99.99 series"


def build_premium(sge_cny_g: pd.Series, lbma_usd_oz: pd.Series,
                  usdcny: pd.Series) -> pd.DataFrame:
    """Join on date and compute the premium. INNER JOIN, deliberately.

    A day missing any leg is a day the premium is unknown, and it is dropped rather than
    forward-filled. Carrying yesterday's premium across a Chinese holiday would invent
    agreement or disagreement on a day no Shanghai price existed -- and disagreement is the
    entire signal.
    """
    df = pd.concat({"sge_cny_g": sge_cny_g, "lbma_usd_oz": lbma_usd_oz,
                    "usdcny": usdcny}, axis=1).dropna()
    df["sge_usd_oz"] = df["sge_cny_g"] * GRAMS_PER_TROY_OZ / df["usdcny"]
    df["premium_usd_oz"] = df["sge_usd_oz"] - df["lbma_usd_oz"]
    df["premium_pct"] = df["premium_usd_oz"] / df["lbma_usd_oz"] * 100.0
    return df


def main() -> int:
    report = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    print("LBMA PM fix + USDCNY (FRED)...", flush=True)
    lbma = _fred_csv(LBMA_FRED, "lbma_usd_oz")
    cny = _fred_csv(USDCNY_FRED, "usdcny")
    print("SGE Au99.99...", flush=True)
    sge, prov = fetch_sge()

    missing = [n for n, s in (("LBMA", lbma), ("USDCNY", cny), ("SGE", sge)) if s is None]
    if missing:
        # FAILS CLOSED. No interpolation, no proxy, no forward-fill across the gap. The value of
        # this series is that it DISAGREES with the Western price; a fabricated version would
        # disagree in invented places and the desk would trade the invention.
        report.update({
            "status": "UNAVAILABLE", "missing_legs": missing, "sge_detail": prov,
            "reason": ("the premium needs all three legs on the same day. A leg was not "
                       "obtainable, so nothing is written -- no interpolation, no proxy, no "
                       "carry-forward. An invented premium is worse than no premium."),
            "fix": ("If SGE is the missing leg: it publishes Au99.99 without a stable free API, "
                    "so add a licensed source to SGE_SOURCES or record the daily benchmark "
                    "manually. If LBMA or USDCNY is missing, that is a network or FRED problem, "
                    "not a licensing one -- both are keyless and public.")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSGE PREMIUM UNAVAILABLE -- missing: {', '.join(missing)}")
        print(report["fix"])
        return 2

    df = build_premium(sge, lbma, cny)
    if df.empty:
        report.update({"status": "EMPTY",
                       "reason": "all three legs fetched but share no common trading day"})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("no overlapping days across the three legs")
        return 1

    df["source_sge"] = prov
    df["fetched_at"] = report["at"]
    df.to_parquet(OUT / "sge_premium.parquet")
    recent = df["premium_usd_oz"].tail(20)
    report.update({"status": "OK", "rows": int(len(df)),
                   "first": str(df.index.min().date()), "last": str(df.index.max().date()),
                   "source_sge": prov,
                   "premium_usd_oz_last": float(df["premium_usd_oz"].iloc[-1]),
                   "premium_pct_last": float(df["premium_pct"].iloc[-1]),
                   "premium_usd_oz_mean_20": float(recent.mean()),
                   "path": str(OUT / "sge_premium.parquet")})
    (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{len(df):,} days {df.index.min().date()} -> {df.index.max().date()}")
    print(f"latest premium {df['premium_usd_oz'].iloc[-1]:+.2f} USD/oz "
          f"({df['premium_pct'].iloc[-1]:+.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
