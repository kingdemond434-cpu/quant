"""Physical gold premiums outside China: Korea, India, Turkey (audit 2026-10-06, repair #4).

THE SAME FRAMEWORK AS THE SGE PREMIUM (fetch_sge_premium), one adapter per market:

    local price (local currency per declared unit)  ->  per gram of fine gold
    parity  = XAUUSD * USD<local> / 31.1034768 * purity * (1 + import duty) [* (1 + GST)]
    premium = local / parity - 1                 (percent; and in USD/oz beside it)

both legs read at the OPEN of the H1 bar containing the market's close instant, placed on the
measured bar clock (`libs.research.bar_clock`); a day the clock cannot place is dropped and
counted, never guessed. Every fetched table is appended to the SGE vintage ledger
(`data/lake/sge_vintages.jsonl`, kind `physical`, contract = market id) and the first-release view
feeds the premium; features (change, acceleration, z, percentile, x CNH/USD state) come from
`fetch_sge_premium.premium_features`, and the series is published as
`data/lake/series/physical_premium_<market>.parquet`, which the dislocation lab screens.

THE TERMS GATE FIRST. Each market has a gate-only row in `alt_proxies.GATE_TERMS` (KRX, IBJA,
Borsa Istanbul: all `to_confirm` on 2026-10-06, evidence quoted there). A market is fetched only
when its row reads `confirmed`; until then it reports BLOCKED_ON_TERMS and makes no request. A
market with no verified route reads UNCONFIGURED (set `PHYS_GOLD_URL_<MARKET>` to a verified
route on the box).

DECLARED CONSTANTS, NOT MEASUREMENTS: India's effective gold import duty schedule (basic customs
duty + AIDC + surcharge, by Union Budget) and the GST flag. IBJA rates are quoted ex-GST, so GST
is not applied to its parity; a market whose price includes GST sets `includes_gst`.

Parsers are built against fixtures that reproduce the documented layouts
(tests/fixtures/cn_official/README.md); live yield is UNMEASURED.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

GRAMS_PER_TROY_OZ = 31.1034768
SERIES = Path(__file__).resolve().parent.parent / "data" / "lake" / "series"
#: India's effective gold import duty by date it took effect (declared, from the Union Budgets).
IN_GOLD_DUTY: tuple[tuple[date, float], ...] = (
    (date(2019, 7, 6), 0.125),       # 12.5% basic customs duty
    (date(2021, 2, 2), 0.1075),      # 7.5% BCD + 2.5% AIDC + surcharge
    (date(2022, 7, 1), 0.15),        # 12.5% BCD + 2.5% AIDC
    (date(2024, 7, 24), 0.06),       # Budget 2024-25: 5% BCD + 1% AIDC
)
GST_GOLD = 0.03


@dataclass(frozen=True)
class Market:
    id: str
    country: str
    fx: str                    # MT5 symbol quoting local currency per USD
    grams_per_unit: float      # the quoted unit, in grams
    purity: float              # fineness of the quoted product
    close_local: tuple[int, int]
    tz_hours: float
    url: str | None
    date_keys: tuple[str, ...]
    price_keys: tuple[str, ...]
    duty: tuple[tuple[date, float], ...] = ()
    includes_gst: bool = False
    publish_delay_min: int = 30
    decimal_comma: bool = False    # "4.120,50" (Turkish / continental grouping)


MARKETS: dict[str, Market] = {
    # KRX gold market (금 99.99_1Kg board, KRW per gram), close 15:30 KST.
    "kr_krx_gold": Market("kr_krx_gold", "KR", "USDKRW", 1.0, 0.9999, (15, 30), 9.0, None,
                          ("TRD_DD", "일자", "date"), ("TDD_CLSPRC", "종가", "close")),
    # IBJA 999 rate (INR per 10 g, ex-GST), closing rate published ~17:00 IST.
    "in_ibja_gold": Market("in_ibja_gold", "IN", "USDINR", 10.0, 0.999, (17, 0), 5.5,
                           "https://ibjarates.com/", ("date",), ("999", "gold 999", "fine gold"),
                           duty=IN_GOLD_DUTY),
    # Borsa Istanbul precious metals market, standard gold 995/1000 (TRY per gram), close 17:00.
    "tr_borsa_gold": Market("tr_borsa_gold", "TR", "USDTRY", 1.0, 0.995, (17, 0), 3.0, None,
                            ("tarih", "date"), ("kapanış", "kapanis", "close"),  # noqa: RUF001
                            decimal_comma=True),
}


def duty_at(m: Market, d: date) -> float:
    rate = 0.0
    for start, r in m.duty:
        if d >= start:
            rate = r
    return rate


def market_url(m: Market) -> str | None:
    return os.environ.get(f"PHYS_GOLD_URL_{m.id.upper()}") or m.url


# =============================================================================== parsing
def _date(text: str) -> str | None:
    t = str(text or "").strip()
    mt = re.search(r"(\d{4})\D(\d{1,2})\D(\d{1,2})", t)
    if mt:
        return f"{mt.group(1)}-{int(mt.group(2)):02d}-{int(mt.group(3)):02d}"
    mt = re.search(r"(\d{1,2})\D(\d{1,2})\D(\d{4})", t)          # dd/mm/yyyy (IBJA, Borsa)
    if mt:
        return f"{mt.group(3)}-{int(mt.group(2)):02d}-{int(mt.group(1)):02d}"
    if re.fullmatch(r"\d{8}", t):
        return f"{t[:4]}-{t[4:6]}-{t[6:]}"
    return None


def _hit(header: str, keys: tuple[str, ...]) -> bool:
    h = header.strip().lower()
    return any(k.lower() in h for k in keys)


def _value(v: Any, m: Market) -> float | None:
    from research.cn_official_tables import to_number
    if m.decimal_comma and isinstance(v, str):
        v = v.strip().replace(".", "").replace(",", ".")
    return to_number(v)


def parse_price_table(body: bytes | str, m: Market) -> list[dict[str, Any]]:
    """Rows {kind, contract, session_date, price_local} from a JSON list-of-records (KRX's
    `output` / `OutBlock_1`) or an HTML table whose headers name a date and a price column."""
    from research.cn_official_tables import html_tables
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    out: list[dict[str, Any]] = []
    doc: Any = None
    if text.lstrip()[:1] in "[{":
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
    if doc is not None:
        recs = doc if isinstance(doc, list) else next(
            (doc[k] for k in ("output", "OutBlock_1", "data", "rows") if isinstance(
                doc.get(k), list)), [])
        for r in recs:
            if not isinstance(r, dict):
                continue
            dk = next((k for k in r if _hit(k, m.date_keys)), None)
            pk = next((k for k in r if _hit(k, m.price_keys)), None)
            d = _date(r.get(dk, "")) if dk else None
            v = _value(r.get(pk), m) if pk else None
            if d and v is not None and v > 0:
                out.append({"kind": "physical", "contract": m.id, "session_date": d,
                            "price_local": v})
        return out
    for rows in html_tables(text):
        if not rows:
            continue
        hdr = rows[0]
        di = next((j for j, h in enumerate(hdr) if _hit(h, m.date_keys)), None)
        pi = next((j for j, h in enumerate(hdr) if _hit(h, m.price_keys)), None)
        if di is None or pi is None:
            continue
        for r in rows[1:]:
            if max(di, pi) >= len(r):
                continue
            d, v = _date(r[di]), _value(r[pi], m)
            if d and v is not None and v > 0:
                out.append({"kind": "physical", "contract": m.id, "session_date": d,
                            "price_local": v})
    return out


def physical_view(market: str, path: Path | None = None) -> pd.DataFrame:
    """First-release view of one market's vintages (the first value read for each date)."""
    from research import fetch_sge_premium as S
    p = path or S.VINTAGES
    first: dict[str, dict[str, Any]] = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                pay = json.loads(r["payload"])
            except (ValueError, KeyError, TypeError):
                continue
            if pay.get("kind") == "physical" and pay.get("contract") == market:
                first.setdefault(str(r["key"]), {**pay, "received_at": r.get("received_at")})
    if not first:
        return pd.DataFrame()
    return pd.DataFrame(list(first.values())).sort_values("session_date").reset_index(drop=True)


# =============================================================================== premium
def market_premium(m: Market, view: pd.DataFrame, xau: pd.DataFrame, fx: pd.DataFrame,
                   clock_root: Path | None = None) -> tuple[pd.DataFrame, dict[str, int]]:
    """Premium of the local price over the landed international parity, per session date."""
    from research.fetch_sge_premium import _bar_open_at
    rows: list[dict[str, Any]] = []
    dropped: dict[str, int] = {}
    if view is None or view.empty:
        return pd.DataFrame(), dropped
    hh, mm = m.close_local
    for _, r in view.iterrows():
        d = datetime.strptime(str(r["session_date"]), "%Y-%m-%d").replace(tzinfo=UTC)
        inst = d + timedelta(hours=hh, minutes=mm) - timedelta(hours=m.tz_hours)
        x, why_x = _bar_open_at(xau, inst, clock_root)
        c, why_c = _bar_open_at(fx, inst, clock_root)
        if x is None or c is None or c <= 0 or x <= 0:
            why = (why_x if x is None else why_c).split(":")[0]
            dropped[why] = dropped.get(why, 0) + 1
            continue
        duty = duty_at(m, d.date())
        landed = x * c / GRAMS_PER_TROY_OZ * m.purity * (1.0 + duty) * (
            1.0 + GST_GOLD if m.includes_gst else 1.0)
        local_g = float(r["price_local"]) / m.grams_per_unit
        local_usd_oz = local_g / m.purity * GRAMS_PER_TROY_OZ / c
        rows.append({"event_time": inst, "fix": "close", "price_local": float(r["price_local"]),
                     "fx": c, "xau_usd_oz": x, "duty": duty, "landed_local_g": landed,
                     "local_usd_oz": local_usd_oz,
                     "premium_usd_oz": local_usd_oz / (1.0 + duty) - x,
                     "premium_pct": (local_g / landed - 1.0) * 100.0,
                     "available_time": inst + timedelta(minutes=m.publish_delay_min)})
    return (pd.DataFrame(rows).sort_values("event_time") if rows else pd.DataFrame()), dropped


def record_physical_premiums(fetched_at: str, *, fetch: Callable[..., Any] | None = None,
                             bars_fn: Callable[[str], Any] | None = None,
                             clock_root: Path | None = None,
                             series_dir: Path | None = None) -> dict[str, Any]:
    """Every market: terms gate -> route -> fetch -> vintages -> premium -> features -> series."""
    from research import fetch_sge_premium as S
    from research.alt_proxies import terms_gate
    bars_fn = bars_fn or S._bars
    out_dir = series_dir or SERIES
    report: dict[str, Any] = {}
    for mid, m in MARKETS.items():
        state, why = terms_gate(mid)
        row: dict[str, Any] = {"terms": state, "fx": m.fx}
        report[mid] = row
        if state != "confirmed":
            row.update({"status": "BLOCKED_ON_TERMS", "why": why[:300]})
            # a premium series an earlier confirmed pass wrote is HELD, never read as current
            from mt5desk.family_exogenous_conditioner import hold_series
            row["held_series"] = hold_series(f"physical_premium_{mid}",
                                             f"BLOCKED_ON_TERMS:{state}", out_dir)
            continue
        url = market_url(m)
        if not url:
            row.update({"status": "UNCONFIGURED",
                        "why": f"no verified route: set PHYS_GOLD_URL_{mid.upper()} on the box"})
        else:
            try:
                if fetch is None:
                    import requests  # type: ignore[import-untyped,unused-ignore]
                    fetch = requests.get
                r = fetch(url, timeout=45, headers={"User-Agent": "quant-research-desk/1.0"})
                r.raise_for_status()
                rows = parse_price_table(r.content, m)
                row.update({"status": "PARSED" if rows else "NO_TABLE", "rows": len(rows),
                            "appended": S.append_vintages(rows, fetched_at, url)})
            except Exception as exc:
                row.update({"status": "UNMEASURED",
                            "why": f"{type(exc).__name__}: {str(exc)[:160]}"})
        xau, fx = bars_fn("XAUUSD"), bars_fn(m.fx)
        if xau is None or fx is None:
            row["premium"] = {"status": "UNMEASURED", "why": f"XAUUSD or {m.fx} bars absent"}
            continue
        prem, dropped = market_premium(m, physical_view(mid), xau, fx, clock_root)
        feats = S.premium_features(prem, bars_fn("USDCNH"), bars_fn("USDX"))
        if not feats.empty:
            feats["source_id"] = f"physical_premium_{mid}"
            out_dir.mkdir(parents=True, exist_ok=True)
            feats.to_parquet(out_dir / f"physical_premium_{mid}.parquet", index=False)
            from mt5desk.family_exogenous_conditioner import release_series
            release_series(f"physical_premium_{mid}", out_dir)
        row["premium"] = {"status": "OK" if not feats.empty else "INSUFFICIENT_HISTORY",
                          "rows": len(feats), "dropped_unplaceable": dropped}
    return report
