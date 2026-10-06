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

THE TERMS GATE COMES FIRST (2026-10-06). SGE's own market-data licensing page says: "Without
the permission of SGE or Information Company, no institution or individual may disseminate,
operate or use the trading information of SGE" (en.sge.com.cn/data_Licensed). That is recorded in
`alt_proxies.TERMS["cn_sge_premium"]` as `refused`, and this module asks `terms_gate` before any
request: while the decision is not `confirmed` it fetches NOTHING, computes nothing from the host's
data and reports BLOCKED_ON_TERMS (a named state, never UNAVAILABLE and never a zero). The day the
desk holds a licence the one TERMS line flips and everything below runs unchanged.

WHAT RUNS WHEN IT IS CONFIRMED (audit 2026-10-06 rows 8-10, 37):
  * every print is appended to `sge_vintages.jsonl` (append-only; the daily table is a VIEW);
  * the Shanghai Gold / Silver Benchmark AM/PM history from the benchmark page and the daily quote
    table (Au99.99, Au(T+D), Ag(T+D): OHLC, weighted average, volume, turnover, open interest,
    delivery), each a vintage;
  * the USD/oz premium at the BENCHMARK instant (10:15 / 14:15 Beijing) against XAUUSD and USDCNH
    from the desk's own H1 bars, converted into the bars' broker clock by `libs.research.bar_clock`
    (a day whose instant cannot be placed is dropped, never guessed);
  * the premium's derivatives (change, acceleration, z, percentile, x CNH state, x USD state)
    published as `data/lake/series/sge_premium_features.parquet` with `available_time`, which the
    dislocation lab and `family_exogenous_conditioner` read.

    python research/fetch_sge_premium.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
#: EVERY print and table row ever read, append-only. The daily parquet above is a VIEW of it.
VINTAGES = OUT / "sge_vintages.jsonl"
#: First-release view of the benchmark vintages: one row per (date, metal) with AM/PM.
BENCHMARK = OUT / "sge_benchmark.parquet"
#: The premium and its derivatives, PIT-stamped, where the lab and the conditioner family read it.
FEATURES = OUT / "series" / "sge_premium_features.parquet"
UNIVERSE = BASE / "data" / "universe"
SGE_DAILY_QUOTE = "https://www.sge.com.cn/sjzx/mrhq"
SGE_BENCHMARK = "https://www.sge.com.cn/sjzx/jzj"
#: The Shanghai Gold Benchmark auctions open at 10:15 and 14:15 Beijing (02:15 / 06:15 UTC); the
#: price is published minutes later, so it is usable from +15 minutes.
BENCH_UTC: dict[str, tuple[int, int]] = {"am": (2, 15), "pm": (6, 15)}
BENCH_PUBLISH_DELAY = timedelta(minutes=15)

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
    except Exception as exc:
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
        except Exception as exc:
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
    # THE VINTAGE FIRST: every print the fetch saw, appended. The daily table below keeps the
    # session's freshest print (a session is not over until it closes), and that upsert is a VIEW
    # -- the intermediate prints survive here, so nothing the desk read is ever lost.
    append_vintages([{"kind": "graph_print", "contract": col, "session_date": str(d.date()),
                      "cny": float(px)} for col, (d, px) in prints.items()],
                    fetched_at, prov)
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
    except Exception as exc:
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


# =============================================================================== terms + vintages
def terms_state() -> tuple[str, str]:
    """The one terms decision for the SGE host. FAIL CLOSED: an unreadable table is not consent."""
    try:
        from research.alt_proxies import terms_gate
    except Exception as exc:
        return "unreadable", f"terms table unimportable ({type(exc).__name__}); fail closed"
    return terms_gate(SGE_GRAPH)


def append_vintages(rows: list[dict[str, Any]], fetched_at: str, source: str) -> int:
    """Append rows to the vintage ledger, skipping a row identical to the last one recorded for
    the same (kind, contract/metal, session date). Never rewrites a line."""
    if not rows:
        return 0
    last: dict[str, str] = {}
    if VINTAGES.exists():
        for ln in VINTAGES.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict):
                last[str(r.get("key"))] = str(r.get("payload"))
    n = 0
    VINTAGES.parent.mkdir(parents=True, exist_ok=True)
    with VINTAGES.open("a", encoding="utf-8") as fh:
        for r in rows:
            key = "|".join(str(r.get(k) or "") for k in ("kind", "contract", "metal",
                                                         "session_date"))
            payload = json.dumps(dict(sorted(r.items())), ensure_ascii=False,
                                 default=str)
            if last.get(key) == payload:
                continue
            fh.write(json.dumps({"key": key, "payload": payload, "received_at": fetched_at,
                                 "source": source, "revision": key in last},
                                ensure_ascii=False) + "\n")
            last[key] = payload
            n += 1
    return n


# =============================================================================== table parsers
def _tables(html: str) -> list[list[list[str]]]:
    from research.cn_official_tables import html_tables
    return html_tables(html)


def _num(v: Any) -> float | None:
    from research.cn_official_tables import to_number
    return to_number(v)


def parse_benchmark(html: str) -> list[dict[str, Any]]:
    """Shanghai Gold Benchmark (早盘价 / 午盘价, CNY/g) and Silver Benchmark (基准价, CNY/kg)."""
    out: list[dict[str, Any]] = []
    for rows in _tables(html):
        hdr = rows[0]
        di = next((j for j, h in enumerate(hdr) if "日期" in h), None)
        if di is None:
            continue
        am = next((j for j, h in enumerate(hdr) if "早盘" in h), None)
        pm = next((j for j, h in enumerate(hdr) if "午盘" in h), None)
        one = next((j for j, h in enumerate(hdr) if "基准价" in h), None)
        metal = "silver" if (am is None and pm is None and one is not None) else "gold"
        for r in rows[1:]:
            m = re.search(r"(\d{4})\D(\d{1,2})\D(\d{1,2})", r[di] if di < len(r) else "")
            if m is None:
                continue
            d = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            if metal == "gold":
                a = _num(r[am]) if am is not None and am < len(r) else None
                b = _num(r[pm]) if pm is not None and pm < len(r) else None
                if a is None and b is None:
                    continue
                out.append({"kind": "benchmark", "metal": "gold", "session_date": d,
                            "am_cny_g": a, "pm_cny_g": b})
            else:
                v = _num(r[one]) if one is not None and one < len(r) else None
                if v is not None:
                    out.append({"kind": "benchmark", "metal": "silver", "session_date": d,
                                "pm_cny_kg": v})
    return out


_QUOTE_COLS = {"开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "加权平均": "wavg",
               "成交量": "volume", "成交金额": "turnover", "持仓": "open_interest",
               "交收量": "delivery_volume"}


def parse_daily_quote(html: str, session_date: str | None = None) -> list[dict[str, Any]]:
    """SGE 每日行情: one row per contract with OHLC, weighted average, volume, turnover, open
    interest and delivery volume where printed. `-` is UNMEASURED (None), never zero."""
    if session_date is None:
        from research.cn_official_tables import _strip_tags
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", _strip_tags(html)[:2000])
        session_date = m.group(0) if m else None
    out: list[dict[str, Any]] = []
    if session_date is None:
        return out
    for rows in _tables(html):
        hdr = rows[0]
        ci = next((j for j, h in enumerate(hdr) if "合约" in h or "品种" in h), None)
        if ci is None:
            continue
        cols = {j: name for j, h in enumerate(hdr) for k, name in _QUOTE_COLS.items() if k in h}
        for r in rows[1:]:
            if ci >= len(r) or not r[ci]:
                continue
            row: dict[str, Any] = {"kind": "daily_quote", "contract": r[ci].strip(),
                                   "session_date": session_date}
            for j, name in cols.items():
                row[name] = _num(r[j]) if j < len(r) else None
            if row.get("close") is not None or row.get("wavg") is not None:
                out.append(row)
    return out


def benchmark_view(path: Path | None = None) -> pd.DataFrame:
    """First-release view of the benchmark vintages: per (date, metal) the first values read."""
    p = path or VINTAGES
    first: dict[str, dict[str, Any]] = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                pay = json.loads(r["payload"])
            except (ValueError, KeyError, TypeError):
                continue
            if pay.get("kind") == "benchmark":
                first.setdefault(str(r["key"]), {**pay, "received_at": r.get("received_at")})
    if not first:
        return pd.DataFrame()
    return pd.DataFrame(list(first.values())).sort_values(["metal", "session_date"])


# =============================================================================== premium + features
def _bars(sym: str) -> pd.DataFrame | None:
    p = UNIVERSE / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()].sort_index()


def _bar_open_at(bars: pd.DataFrame, instant_utc: datetime, root: Path | None = None
                 ) -> tuple[float | None, str]:
    """The OPEN of the H1 bar containing a genuinely-UTC instant, placed on the bars' broker clock.

    The open, not the close: it is a price from before the benchmark instant, so the comparison
    never borrows the next 45 minutes. An instant `bar_clock` cannot place (no measured clock, or
    a shoulder month) is UNMEASURED and the day is dropped."""
    from libs.research.bar_clock import to_bar_time
    conv, status, why = to_bar_time(instant_utc, root)
    if conv is None:
        return None, f"{status}: {why}"
    stamp = pd.Timestamp(conv).tz_convert("UTC").floor("h")
    if stamp not in bars.index:
        return None, f"no bar at {stamp}"
    return float(bars.loc[stamp, "open"]), "ok"


def benchmark_premium(bench: pd.DataFrame, xau: pd.DataFrame, cnh: pd.DataFrame,
                      clock_root: Path | None = None) -> tuple[pd.DataFrame, dict[str, int]]:
    """USD/oz premium of each gold benchmark fix over XAUUSD, with USDCNH at the same instant.

        sge_usd_oz = benchmark_CNY_per_g * 31.1034768 / USDCNH
        premium    = sge_usd_oz - XAUUSD           (both at the bar containing the fix instant)
    """
    rows: list[dict[str, Any]] = []
    dropped: dict[str, int] = {}
    if bench is None or bench.empty:
        return pd.DataFrame(), dropped
    gold = bench[bench["metal"] == "gold"]
    for _, r in gold.iterrows():
        d = datetime.strptime(str(r["session_date"]), "%Y-%m-%d").replace(tzinfo=UTC)
        for fix, (hh, mm) in BENCH_UTC.items():
            px = r.get(f"{fix}_cny_g")
            if px is None or pd.isna(px):
                continue
            inst = d.replace(hour=hh, minute=mm)
            x, why_x = _bar_open_at(xau, inst, clock_root)
            c, why_c = _bar_open_at(cnh, inst, clock_root)
            if x is None or c is None or c <= 0:
                why = (why_x if x is None else why_c).split(":")[0]
                dropped[why] = dropped.get(why, 0) + 1
                continue
            sge_usd = float(px) * GRAMS_PER_TROY_OZ / c
            rows.append({"event_time": inst, "fix": fix, "sge_cny_g": float(px), "usdcnh": c,
                         "xau_usd_oz": x, "sge_usd_oz": sge_usd, "premium_usd_oz": sge_usd - x,
                         "premium_pct": (sge_usd - x) / x * 100.0,
                         "available_time": inst + BENCH_PUBLISH_DELAY})
    return (pd.DataFrame(rows).sort_values("event_time") if rows else pd.DataFrame()), dropped


def premium_features(prem: pd.DataFrame, cnh: pd.DataFrame | None = None,
                     usdx: pd.DataFrame | None = None, z_window: int = 60,
                     rank_window: int = 250) -> pd.DataFrame:
    """Level, change, acceleration, z, percentile, and the premium x CNH / x USD states.

    Every statistic uses only rows at or before its own: rolling windows end at the row, and the
    CNH / USD state is the 20-bar return ending at the bar BEFORE the fix instant's bar."""
    if prem is None or prem.empty:
        return pd.DataFrame()
    f = prem[["event_time", "available_time", "fix", "premium_usd_oz", "premium_pct"]].copy()
    f = f.sort_values("event_time").reset_index(drop=True)
    p = f["premium_pct"]
    f["premium_delta"] = p.diff()
    f["premium_accel"] = f["premium_delta"].diff()
    mu = p.rolling(z_window, min_periods=20).mean()
    sd = p.rolling(z_window, min_periods=20).std(ddof=0)
    f["premium_z"] = (p - mu) / sd.where(sd > 0)
    f["premium_pct_rank"] = p.rolling(rank_window, min_periods=20).rank(pct=True)
    for name, bars in (("cnh", cnh), ("usd", usdx)):
        col = f"premium_x_{name}"
        if bars is None or bars.empty:
            f[col] = float("nan")
            continue
        ret = (bars["close"].astype(float).pipe(lambda c: c / c.shift(20) - 1.0)).shift(1)
        rz = (ret - ret.rolling(500, min_periods=50).mean()) / ret.rolling(
            500, min_periods=50).std(ddof=0)
        state = rz.reindex(pd.DatetimeIndex(f["event_time"]).floor("h"), method="ffill")
        f[col] = f["premium_z"].to_numpy() * state.to_numpy()
    f["source_id"] = "sge_premium_features"
    return f


def record_benchmark_and_features(fetched_at: str) -> dict[str, Any]:
    """Benchmark AM/PM + daily quotes as vintages, then the benchmark premium and its features.
    Called only behind a `confirmed` terms gate."""
    out: dict[str, Any] = {}
    for url, parser, kind in ((SGE_BENCHMARK, parse_benchmark, "benchmark"),
                              (SGE_DAILY_QUOTE, parse_daily_quote, "daily_quote")):
        try:
            r = requests.get(url, timeout=45, headers={"User-Agent": "quant-research-desk/1.0"})
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            rows = parser(r.text)
        except Exception as exc:
            out[kind] = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:160]}
            continue
        out[kind] = {"status": "PARSED" if rows else "NO_TABLE", "rows": len(rows),
                     "appended": append_vintages(rows, fetched_at, url)}
    xau, cnh = _bars("XAUUSD"), _bars("USDCNH")
    if xau is None or cnh is None:
        out["premium"] = {"status": "UNMEASURED", "why": "XAUUSD or USDCNH H1 bars absent"}
        return out
    prem, dropped = benchmark_premium(benchmark_view(), xau, cnh)
    feats = premium_features(prem, cnh, _bars("USDX"))
    if not feats.empty:
        FEATURES.parent.mkdir(parents=True, exist_ok=True)
        feats.to_parquet(FEATURES, index=False)
    out["premium"] = {"status": "OK" if not feats.empty else "INSUFFICIENT_HISTORY",
                      "rows": len(feats), "dropped_unplaceable": dropped,
                      "path": str(FEATURES)}
    return out


def main() -> int:
    report: dict[str, object] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    state, why = terms_state()
    report["terms"] = {"state": state, "why": why}
    if state != "confirmed":
        # NOTHING IS FETCHED AND NOTHING IS COMPUTED FROM THE HOST'S DATA. A named state, not a
        # failure: the leg ran, read the decision and honoured it.
        report.update({"status": "BLOCKED_ON_TERMS",
                       "reason": ("SGE's terms bar any use of its trading information without "
                                  "permission; flip alt_proxies.TERMS['cn_sge_premium'] only on "
                                  "a held licence"),
                       "history_rows": "UNMEASURED", "premium": "UNMEASURED"})
        (REPORTS / "sge_premium.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"SGE PREMIUM BLOCKED_ON_TERMS ({state}): nothing fetched")
        return 0
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
    report.update({"history_rows": len(hist), "history_path": str(HISTORY),
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
        print("\nno overlapping days yet (rate-leg publication lag); "
              "SGE history recorded and growing")
        return 0

    df["source_sge"] = prov
    df["intl_source"] = "fusion_xauusd_h1_0700Z"
    df["usdcny_source"] = cny_source
    df["fetched_at"] = report["at"]
    df.to_parquet(OUT / "sge_premium.parquet")
    report["benchmark"] = record_benchmark_and_features(str(report["at"]))
    recent = df["premium_usd_oz"].tail(20)
    report.update({"status": "OK", "rows": len(df),
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
