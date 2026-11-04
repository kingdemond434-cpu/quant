"""Accrue genuine contract-level gold and WTI curves for MT5 research.

Continuous front-month prices cannot identify roll yield or calendar spreads. This collector keeps
each delayed public contract separately, including its expiry and volume, and publishes a long
point-in-time panel. Missing contracts remain missing; no synthetic curve is manufactured.

THE YAHOO CUT (coordinator + auditor ruling 2026-10-14). The contract quotes used to come from
Yahoo's chart API, which is an IDEAS_ONLY row of libs/data/terms_fence.SOURCE_POLICY (Terms
2.d.9): never live input. `fetch_contract` now asks THE ONE FETCH DOOR with live_input=True and
is refused before any request. The substitutes, each read from a row whose own terms were quoted:

    CL  EIA's NYMEX futures contracts 1-4 (RCLC1..RCLC4, daily, keyless hist_xls files; EIA
        `eia_open_data`: "You may use and/or distribute any of our data, files, databases ...").
        Rank-based, so the expiry is DERIVED from the NYMEX CL rule (third business day before
        the 25th of the month before delivery, holidays not modelled) and labelled so.
    GC  NO LICENSED SOURCE: COMEX contract quotes are CME's (held route), and no public-domain
        publisher carries a gold contract curve. GC is UNMEASURED_NO_LICENSED_SOURCE with a
        missed_growth line; nothing is filled.

A curve file a Yahoo pass wrote is moved aside (`*.yahoo_ideas_only`), never read again and never
deleted; only a curve whose `source` column names a licensed row is published.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from libs.data.polite_fetch import DESK_UA
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA

BASE = Path(__file__).resolve().parent.parent
if str(BASE.parent.parent) not in sys.path:      # the repo root, for libs.data.terms_fence
    sys.path.append(str(BASE.parent.parent))
OUT = BASE / "data" / "futures_curves"
REPORT = BASE / "reports" / "futures_curve_coverage.json"
UA = DESK_UA
MONTH_CODE = dict(zip(range(1, 13), "FGHJKMNQUVXZ", strict=True))
PRODUCTS = {
    "GC": {"suffix": "CMX", "months": (2, 4, 6, 8, 10, 12)},
    "CL": {"suffix": "NYM", "months": tuple(range(1, 13))},
}
CODE_MONTH = {code: month for month, code in MONTH_CODE.items()}

UNMEASURED_NO_LICENSED_SOURCE = "UNMEASURED_NO_LICENSED_SOURCE"
#: The licensed substitute per root (terms_fence row, series ids), or None when there is none.
SUBSTITUTES: dict[str, dict[str, Any] | None] = {
    "CL": {"route": "eia_open_data", "series": ("RCLC1", "RCLC2", "RCLC3", "RCLC4"),
           "url": "https://www.eia.gov/dnav/pet/hist_xls/{sid}d.xls",
           "pit_lag_h": 27.0,
           "pit_basis": ("NYMEX 2:30pm ET closes posted by EIA the same evening; read under the "
                         "cross_asset_anchors 27h lag (late-biased)")},
    "GC": None,
}
NO_GC_SOURCE = ("COMEX gold contract quotes are CME's (cmegroup.com is a held route: s.12 bars "
                "copying, s.8(vi) bars ML use) and Yahoo, which served them, is IDEAS_ONLY; no "
                "public-domain publisher carries a gold contract curve")


def contract_symbol(root: str, year: int, month: int) -> str:
    return f"{root}{MONTH_CODE[month]}{year % 100:02d}.{PRODUCTS[root]['suffix']}"


def contract_month_anchor(symbol: str) -> pd.Timestamp:
    """Return the contract delivery-month end encoded in a standard Yahoo futures symbol.

    This is not claimed to be the exchange's exact last-trade timestamp. It is a transparent
    ordering/tenor anchor when Yahoo omits ``expireDate``; exact-expiry-sensitive trading remains
    blocked pending an authoritative contract calendar.
    """
    match = re.match(r"^[A-Z]+([FGHJKMNQUVXZ])(\d{2})\.", symbol)
    if not match or match.group(1) not in CODE_MONTH:
        return pd.NaT
    month, year = CODE_MONTH[match.group(1)], 2000 + int(match.group(2))
    return pd.Timestamp(year=year, month=month, day=1, tz="UTC") + pd.offsets.MonthEnd(0)


def fetch_contract(symbol: str) -> tuple[pd.DataFrame, dict]:
    """REFUSED AS LIVE INPUT (2026-10-14): Yahoo is IDEAS_ONLY, so THE ONE FETCH DOOR is asked with
    live_input=True and raises TermsFenced before any request is built. Kept so a stale caller
    fails closed; `main` no longer calls it."""
    encoded = urllib.parse.quote(symbol, safe="")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
           "?period1=0&period2=4102444800&interval=1d&events=history")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        from libs.data import terms_fence as _tf
        with _tf.guarded_urlopen(req, timeout=45, live_input=True) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return pd.DataFrame(), {"symbol": symbol, "status": "NOT_LISTED"}
        raise
    result = (payload.get("chart", {}).get("result") or [])
    if not result:
        return pd.DataFrame(), {"symbol": symbol, "status": "NO_RESULT"}
    raw = result[0]
    stamps = raw.get("timestamp") or []
    quote = (raw.get("indicators", {}).get("quote") or [{}])[0]
    meta = raw.get("meta") or {}
    if not stamps:
        return pd.DataFrame(), {"symbol": symbol, "status": "EMPTY"}
    frame = pd.DataFrame({
        "date": pd.to_datetime(stamps, unit="s", utc=True).normalize(),
        "open": quote.get("open"), "high": quote.get("high"),
        "low": quote.get("low"), "close": quote.get("close"),
        "volume": quote.get("volume"),
    }).dropna(subset=["close"])
    expiry = meta.get("expireDate")
    expiry_source = "yahoo_expireDate" if expiry else "contract_code_month_end_anchor"
    expiry_value = (pd.to_datetime(expiry, unit="s", utc=True).normalize()
                    if expiry else contract_month_anchor(symbol))
    frame["symbol"] = symbol
    frame["expiration"] = expiry_value
    frame["expiration_source"] = expiry_source
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return frame, {"symbol": symbol, "status": "OK", "rows": len(frame),
                   "expiration": None if pd.isna(expiry_value) else str(expiry_value),
                   "expiration_source": expiry_source}


def missed_growth_line(root: str, status: str) -> dict[str, Any]:
    """The cut Yahoo input's missed-growth line (terms_fence.held_missed_growth, kind
    ideas_only_refusal): delta E[log W] UNMEASURED, never zero."""
    from libs.data import terms_fence as _tf
    sub = SUBSTITUTES.get(root)
    line = _tf.held_missed_growth("yahoo", None, source=f"fetch_futures_curves:{root}",
                                  live_input_refusal=True)
    line.update({"series_status": status,
                 "substitute": (f"{sub['route']}:{','.join(sub['series'])}" if sub else None)})
    if status == UNMEASURED_NO_LICENSED_SOURCE:
        line["why_unsubstituted"] = NO_GC_SOURCE if root == "GC" else "no licensed source"
    return line


def eia_get(url: str, timeout: float = 45.0) -> bytes:
    """One EIA file through polite_fetch's door (`fenced_urlopen`, live_input=True: an IDEAS_ONLY
    or held first URL or redirect hop raises TermsFenced), with the desk's honest User-Agent."""
    from libs.data import polite_fetch
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with polite_fetch.fenced_urlopen(req, timeout=timeout, live_input=True) as response:
        return bytes(response.read())


def parse_eia_daily(raw: bytes) -> dict[date, float]:
    """{trade date: value} from an EIA `hist_xls` workbook: the data sheet's rows whose first cell
    is an Excel serial date and whose second is a number. Header and note rows are skipped."""
    from libs.data.xls_reader import read_xls
    out: dict[date, float] = {}
    for sheet in read_xls(raw):
        for row in sheet.rows():
            if len(row) < 2:
                continue
            d, v = row[0], row[1]
            if isinstance(d, (int, float)) and isinstance(v, (int, float)) and 20000 < d < 80000:
                out[date(1899, 12, 30) + timedelta(days=int(d))] = float(v)
    return out


def _business_days_before(d: date, n: int) -> date:
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def cl_last_trade(delivery_year: int, delivery_month: int) -> date:
    """NYMEX CL last trade: three business days before the 25th of the month BEFORE delivery
    (before the last business day preceding the 25th when the 25th is not one). Holidays are not
    modelled, so this is an anchor, not an exchange calendar."""
    y, m = (delivery_year, delivery_month - 1) if delivery_month > 1 else (delivery_year - 1, 12)
    d25 = date(y, m, 25)
    anchor = d25 if d25.weekday() < 5 else _business_days_before(d25, 1)
    return _business_days_before(anchor, 3)


def cl_contract_expiry(trade_date: date, rank: int) -> date:
    """The derived last-trade date of EIA's CL contract `rank` (1 = front) on `trade_date`."""
    y, m = trade_date.year, trade_date.month + 1          # earliest possible delivery month
    if m > 12:
        y, m = y + 1, 1
    if trade_date > cl_last_trade(y, m):
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    for _ in range(rank - 1):
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return cl_last_trade(y, m)


def eia_contract_frame(sid: str, rank: int, values: dict[date, float]) -> pd.DataFrame:
    """One EIA contract series as the frame `build_curve` takes, with its licensed `source`."""
    days = sorted(values)
    return pd.DataFrame({
        "date": pd.to_datetime(days, utc=True).normalize(),
        "close": [values[d] for d in days],
        "symbol": f"CL_EIA_C{rank}",
        "expiration": pd.to_datetime([cl_contract_expiry(d, rank) for d in days], utc=True),
        "expiration_source": "nymex_cl_rule_no_holidays",
        "source": f"eia_open_data:{sid}",
    })


def fetch_substitute(root: str, get: Any = None) -> tuple[list[pd.DataFrame], list[dict]]:
    """(frames, coverage rows) of the licensed substitute for `root`; ([], [UNMEASURED row]) when
    there is none. `get` is an injectable byte fetcher for tests."""
    sub = SUBSTITUTES.get(root)
    if not sub:
        return [], [{"root": root, "status": UNMEASURED_NO_LICENSED_SOURCE,
                     "why": NO_GC_SOURCE if root == "GC" else "no licensed source",
                     "missed_growth": missed_growth_line(root, UNMEASURED_NO_LICENSED_SOURCE)}]
    get = get or eia_get
    frames, rows = [], []
    for rank, sid in enumerate(sub["series"], start=1):
        url = str(sub["url"]).format(sid=sid)
        try:
            values = parse_eia_daily(get(url))
        except Exception as exc:
            rows.append({"root": root, "symbol": sid, "status": "FAILED",
                         "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
            continue
        if not values:
            rows.append({"root": root, "symbol": sid, "status": "EMPTY"})
            continue
        frames.append(eia_contract_frame(sid, rank, values))
        rows.append({"root": root, "symbol": sid, "status": "OK", "rows": len(values),
                     "first": str(min(values)), "last": str(max(values)),
                     "source": f"{sub['route']}:{sid}", "pit_lag_h": sub["pit_lag_h"]})
    return frames, rows


def quarantine_unlicensed(root: str, out: Path | None = None) -> str | None:
    """Move a curve file whose rows do not ALL carry a licensed `source` aside (never deleted, never
    read): a Yahoo-era panel must not keep feeding the curve screen behind the cut."""
    path = (out or OUT) / f"{root}_curve.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=None)
    except (OSError, ValueError):
        frame = pd.DataFrame()
    src = frame.get("source") if isinstance(frame, pd.DataFrame) else None
    licensed = (src is not None and len(frame) > 0
                and src.astype(str).str.startswith("eia_open_data:").all())
    if licensed:
        return None
    aside = path.with_name(path.name + ".yahoo_ideas_only")
    path.replace(aside)
    return str(aside.name)


def build_curve(contracts: list[pd.DataFrame], root: str) -> pd.DataFrame:
    frame = pd.concat(contracts, ignore_index=True)
    # Yahoo mixes timezone-aware chart stamps, timezone-naive metadata and missing expiries across
    # contract vintages. Normalize both columns before subtraction; an unknown expiry cannot define
    # a curve rank and is retained in coverage but excluded from the measured curve.
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.normalize()
    frame["expiration"] = pd.to_datetime(
        frame["expiration"], utc=True, errors="coerce",
    ).dt.normalize()
    frame = frame.dropna(subset=["date", "expiration", "close"])
    frame = frame.sort_values(["date", "expiration", "symbol"])
    frame["root"] = root
    frame["days_to_expiry"] = (frame["expiration"] - frame["date"]).dt.days
    frame = frame[frame["days_to_expiry"] > 0].copy()
    frame["curve_rank"] = frame.groupby("date").cumcount() + 1
    front = frame[frame["curve_rank"] == 1][["date", "close", "expiration"]].rename(
        columns={"close": "front_close", "expiration": "front_expiration"})
    nxt = frame[frame["curve_rank"] == 2][["date", "close", "expiration"]].rename(
        columns={"close": "next_close", "expiration": "next_expiration"})
    pair = front.merge(nxt, on="date", how="left")
    tenor = (pair["next_expiration"] - pair["front_expiration"]).dt.days
    pair["calendar_spread"] = pair["next_close"] - pair["front_close"]
    pair["annualized_roll_yield"] = -(pair["next_close"] / pair["front_close"] - 1.0) * 365 / tenor
    return frame.merge(pair[["date", "calendar_spread", "annualized_roll_yield"]], on="date")


def _cut_status(root: str, per_root: dict[str, str]) -> str:
    if SUBSTITUTES.get(root) is None:
        return UNMEASURED_NO_LICENSED_SOURCE
    return ("SUBSTITUTED" if per_root.get(root) == "MEASURED"
            else "UNMEASURED_SUBSTITUTE_UNREACHABLE")


def main(argv: list[str] | None = None, *, get: Any = None, out: Path | None = None,
         report_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years-back", type=int, default=4, help="kept for callers; unused")
    parser.add_argument("--years-forward", type=int, default=2, help="kept for callers; unused")
    parser.add_argument("--sleep", type=float, default=0.2, help="kept for callers; unused")
    parser.parse_args(argv)
    out = out or OUT
    coverage: list[dict] = []
    usable, quarantined, per_root = 0, [], {}
    for root in PRODUCTS:
        moved = quarantine_unlicensed(root, out)
        if moved:
            quarantined.append(moved)
        frames, rows = fetch_substitute(root, get)
        coverage.extend(rows)
        if not frames:
            per_root[root] = (UNMEASURED_NO_LICENSED_SOURCE if SUBSTITUTES.get(root) is None
                              else "UNMEASURED_SUBSTITUTE_UNREACHABLE")
            continue
        panel = build_curve(frames, root)
        out.mkdir(parents=True, exist_ok=True)
        panel.to_parquet(out / f"{root}_curve.parquet", index=False, compression="zstd")
        n = int(panel["annualized_roll_yield"].notna().sum())
        usable += n
        per_root[root] = "MEASURED" if n else "UNMEASURED"
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": ("licensed substitutes only: EIA NYMEX contracts 1-4 for CL; GC has none. "
                   "Yahoo is IDEAS_ONLY and never asked (2026-10-14)"),
        "per_root": per_root,
        "contracts": coverage,
        "usable_curve_dates": usable,
        "quarantined_yahoo_files": quarantined,
        "missed_growth": [missed_growth_line(r, _cut_status(r, per_root)) for r in PRODUCTS],
        "promotion_authority": False,
        "exact_expiry_sensitive_use": "BLOCKED without authoritative contract calendar",
        "status": "MEASURED" if usable else "UNMEASURED",
    }
    rp = report_path or REPORT
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": report["status"], "usable_curve_dates": usable,
                      "per_root": per_root, "quarantined": quarantined}, indent=2))
    return 0 if usable else 2


if __name__ == "__main__":
    raise SystemExit(main())
