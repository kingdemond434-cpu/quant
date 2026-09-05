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
    premium     = XAU_SGE_USD - XAUUSD_fusion_0700Z_close

WHAT THIS MODULE WILL NOT DO

The SGE publishes no bulk free history (the CN s12 dig's bulk pull was throttle-blocked), so
history is SELF-RECORDED FORWARD (free-frontier law): each daily run captures that session's
last print into data/lake/sge_daily.parquet, and the premium series grows from the wiring date.
This fails closed. If it cannot obtain a genuine SGE print it writes UNAVAILABLE and stops.
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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "lake"
OUT.mkdir(parents=True, exist_ok=True)
REPORTS = BASE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
#: Forward-accumulated raw SGE prints, one row per Beijing trading date.
HISTORY = OUT / "sge_daily.parquet"

GRAMS_PER_TROY_OZ = 31.1034768

#: The international USD/oz leg is the desk's OWN broker feed: the XAUUSD H1 close of the
#: 07:00 UTC bar — the bar containing the SGE day-session close (15:30 Beijing = 07:30 UTC).
#: This replaced the LBMA PM fix after FRED 404'd GOLDPMGBD228NLBM (series withdrawn; measured
#: 2026-08-26), and it is the better leg anyway: the premium conditions XAUUSD trades, so the
#: spread vs the desk's actually-tradeable price IS the signal, and the file is on disk with no
#: network dependency.
XAU_H1 = BASE / "data" / "universe" / "XAUUSD_H1.parquet"

#: USDCNY primary: ECB reference rates, USD and CNY from the SAME 16:00 CET snapshot, crossed.
#: Keyless, daily, ~0-1 day lag. Fallback: FRED DEXCHUS (H.10 noon-NY), keyless but published
#: with weeks of lag. One source per run for the WHOLE join — never mixed day-by-day — and the
#: report records which.
ECB_90D = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
USDCNY_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS"

#: SGE official graph endpoint (R0649, verified live 2026-08-26). Serves ONE contract's
#: current-session minute curve:
#:   {"times": ["20:00", ...], "data": ["990.08", null, ...], "heyue": "Au99.99",
#:    "delaystr": "2026年08月26日 02:29:56", "min": ..., "max": ...}
#: `instid` selects the contract; `delaystr` is the LAST-QUOTE Beijing timestamp (not wall
#: clock), which is what dates the print. The previous parser here expected dated rows with
#: instid/close keys and could parse nothing from this shape — the exact III.16
#: built-never-run defect the CN s12 card recorded.
SGE_GRAPH = "https://www.sge.com.cn/graph/quotations"
#: history column -> SGE contract. Au99.99 is the REQUIRED spot leg; Au(T+D) is the deferred
#: contract whose basis to spot carries the 递延费 (deferred-fee) pressure direction.
SGE_CONTRACTS = {"au9999_cny_g": "Au99.99", "au_td_cny_g": "Au(T+D)"}

_DELAY_RE = re.compile(r"(\d{4})年(\d{2})月(\d{2})日")


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


def _parse_graph(payload: object, instid: str) -> tuple[pd.Timestamp, float] | None:
    """(session date, last traded price) from one graph payload, or None.

    The date comes from `delaystr` — the Beijing timestamp of the LAST QUOTE — never from the
    fetch clock: a weekend fetch returns Friday's session and must be dated Friday. `heyue` is
    checked against the requested contract because the endpoint silently falls back to Au99.99
    for an unknown instid, and recording that fallback under Au(T+D) would fabricate a zero
    basis.
    """
    if not isinstance(payload, dict) or payload.get("heyue") != instid:
        return None
    m = _DELAY_RE.search(str(payload.get("delaystr") or ""))
    if m is None:
        return None
    vals = [v for v in (payload.get("data") or []) if v not in (None, "", "null")]
    try:
        last = float(vals[-1])
    except (IndexError, ValueError, TypeError):
        return None
    if not 10.0 < last < 100_000.0:   # CNY/gram sanity: gold ~1000, silver ~10
        return None
    return pd.Timestamp(f"{m.group(1)}-{m.group(2)}-{m.group(3)}"), last


def fetch_sge() -> tuple[dict[str, tuple[pd.Timestamp, float]], str]:
    """Latest SGE print per contract. Returns ({col: (date, cny_per_gram)}, provenance).

    An empty dict (or one missing au9999_cny_g) means the REQUIRED leg failed; Au(T+D) is
    enrichment and its absence is logged, not fatal.
    """
    prints: dict[str, tuple[pd.Timestamp, float]] = {}
    for col, instid in SGE_CONTRACTS.items():
        try:
            r = requests.get(SGE_GRAPH, params={"instid": instid}, timeout=45,
                             headers={"User-Agent": "quant-research-desk/1.0"})
            r.raise_for_status()
            parsed = _parse_graph(r.json(), instid)
        except Exception as exc:                                    # noqa: BLE001
            print(f"  {instid}: {type(exc).__name__}: {exc}", flush=True)
            parsed = None
        if parsed is None:
            print(f"  {instid}: no usable print", flush=True)
            continue
        prints[col] = parsed
    return prints, "sge_official_graph"


def record_history(prints: dict[str, tuple[pd.Timestamp, float]], prov: str,
                   fetched_at: str) -> pd.DataFrame:
    """Upsert today's prints into the forward-accumulated history, idempotently by date.

    Re-running on the same day overwrites that day's row with the fresher print; it can never
    duplicate a date, so the timer's cadence cannot inflate the series.
    """
    rows: dict[pd.Timestamp, dict[str, object]] = {}
    for col, (d, px) in prints.items():
        rows.setdefault(d.normalize(), {})[col] = px
    add = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    add["source"] = prov
    add["fetched_at"] = fetched_at
    if HISTORY.exists():
        hist = pd.read_parquet(HISTORY)
        hist = add.combine_first(hist)
    else:
        hist = add
    hist = hist.sort_index()
    if {"au9999_cny_g", "au_td_cny_g"} <= set(hist.columns):
        # Au(T+D) trades at a basis to spot; its SIGN is the market-priced read on which side
        # of the 递延费 (deferred fee) is under pressure — the direction leg of this card.
        hist["agtd_basis_cny_g"] = hist["au_td_cny_g"] - hist["au9999_cny_g"]
    hist.to_parquet(HISTORY)
    return hist


def _desk_xau_usd_oz() -> pd.Series | None:
    """XAUUSD close of the 07:00 UTC H1 bar per date, from the desk's own synced feed."""
    if not XAU_H1.exists():
        return None
    df = pd.read_parquet(XAU_H1)
    at7 = df[df.index.hour == 7]["close"]
    if at7.empty:
        return None
    s = at7.copy()
    s.index = s.index.tz_convert("UTC").normalize().tz_localize(None)
    s = s[~s.index.duplicated(keep="last")]
    s.name = "intl_usd_oz"
    return s


def _ecb_usdcny() -> pd.Series | None:
    """USDCNY crossed from ECB reference EUR rates (same 16:00 CET snapshot both legs)."""
    import xml.etree.ElementTree as ET
    try:
        r = requests.get(ECB_90D, timeout=45)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:                                        # noqa: BLE001
        print(f"  ecb_usdcny: {type(exc).__name__}: {exc}", flush=True)
        return None
    ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    recs: dict[pd.Timestamp, float] = {}
    for day in root.findall(".//e:Cube[@time]", ns):
        rates = {c.get("currency"): c.get("rate") for c in day.findall("e:Cube", ns)}
        try:
            usd, cny = float(rates["USD"]), float(rates["CNY"])
        except (KeyError, TypeError, ValueError):
            continue
        recs[pd.Timestamp(str(day.get("time")))] = cny / usd
    if not recs:
        return None
    s = pd.Series(recs).sort_index()
    s.name = "usdcny"
    return s


def build_premium(sge_cny_g: pd.Series, intl_usd_oz: pd.Series,
                  usdcny: pd.Series) -> pd.DataFrame:
    """Join on date and compute the premium. INNER JOIN, deliberately.

    A day missing any leg is a day the premium is unknown, and it is dropped rather than
    forward-filled. Carrying yesterday's premium across a Chinese holiday would invent
    agreement or disagreement on a day no Shanghai price existed -- and disagreement is the
    entire signal.
    """
    df = pd.concat({"sge_cny_g": sge_cny_g, "intl_usd_oz": intl_usd_oz,
                    "usdcny": usdcny}, axis=1).dropna()
    df["sge_usd_oz"] = df["sge_cny_g"] * GRAMS_PER_TROY_OZ / df["usdcny"]
    df["premium_usd_oz"] = df["sge_usd_oz"] - df["intl_usd_oz"]
    df["premium_pct"] = df["premium_usd_oz"] / df["intl_usd_oz"] * 100.0
    return df


def main() -> int:
    report: dict[str, object] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    print("SGE Au99.99 + Au(T+D)...", flush=True)
    prints, prov = fetch_sge()
    if "au9999_cny_g" not in prints:
        # FAILS CLOSED. No interpolation, no proxy, no carry-forward: the value of this series
        # is that it DISAGREES with the Western price, so a fabricated version would disagree
        # in invented places and the desk would trade the invention.
        report.update({
            "status": "UNAVAILABLE", "missing_legs": ["SGE"], "sge_detail": prov,
            "reason": ("the SGE graph endpoint yielded no usable Au99.99 print; nothing "
                       "recorded -- no interpolation, no proxy, no carry-forward"),
            "fix": ("check https://www.sge.com.cn/graph/quotations?instid=Au99.99 by hand; "
                    "if the payload shape changed again, update _parse_graph and its fixture "
                    "test in tests/test_sge_premium.py")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("\nSGE PREMIUM UNAVAILABLE -- no SGE print")
        return 2

    hist = record_history(prints, prov, str(report["at"]))
    latest = {col: {"date": str(d.date()), "cny_per_gram": px}
              for col, (d, px) in prints.items()}
    report.update({"history_rows": int(len(hist)), "history_path": str(HISTORY),
                   "source_sge": prov, "latest": latest})
    print(f"history: {len(hist)} day(s) recorded -> {HISTORY}", flush=True)

    print("XAUUSD 07:00Z leg (desk feed) + USDCNY (ECB, FRED fallback)...", flush=True)
    intl = _desk_xau_usd_oz()
    cny = _ecb_usdcny()
    cny_source = "ecb_cross"
    if cny is None:
        cny = _fred_csv(USDCNY_FRED, "usdcny")
        cny_source = "fred_dexchus"
    missing = [n for n, s in (("XAUUSD_H1", intl), ("USDCNY", cny)) if s is None]
    if missing:
        report.update({
            "status": "SGE_RECORDED_LEG_MISSING", "missing_legs": missing,
            "reason": ("today's SGE print IS recorded (self-recorded history never skips a "
                       "day), but the premium needs the XAUUSD and USDCNY legs and one was "
                       "not obtainable -- see stderr above for the fetch error")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nlegs missing: {', '.join(missing)} -- SGE history still recorded")
        return 1

    assert intl is not None and cny is not None
    report["usdcny_source"] = cny_source
    df = build_premium(hist["au9999_cny_g"].dropna(), intl, cny)
    if df.empty:
        # Expected while the forward-recorded SGE history is younger than FRED's publication
        # lag (LBMA/DEXCHUS trail by days-to-weeks): all legs healthy, no overlapping date yet.
        report.update({"status": "ACCUMULATING",
                       "reason": ("all legs fetched; no common trading day yet between the "
                                  "self-recorded SGE history and the rate legs -- the overlap "
                                  "arrives within a day as the legs publish")})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("\nno overlapping days yet (rate-leg publication lag); SGE history recorded and growing")
        return 0

    df["source_sge"] = prov
    df["intl_source"] = "fusion_xauusd_h1_0700Z"
    df["usdcny_source"] = cny_source
    df["fetched_at"] = report["at"]
    df.to_parquet(OUT / "sge_premium.parquet")
    recent = df["premium_usd_oz"].tail(20)
    report.update({"status": "OK", "rows": int(len(df)),
                   "first": str(df.index.min().date()), "last": str(df.index.max().date()),
                   "premium_usd_oz_last": float(df["premium_usd_oz"].iloc[-1]),
                   "premium_pct_last": float(df["premium_pct"].iloc[-1]),
                   "premium_usd_oz_mean_20": float(recent.mean()),
                   "path": str(OUT / "sge_premium.parquet")})
    (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{len(df):,} premium day(s) {df.index.min().date()} -> {df.index.max().date()}")
    print(f"latest premium {df['premium_usd_oz'].iloc[-1]:+.2f} USD/oz "
          f"({df['premium_pct'].iloc[-1]:+.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
