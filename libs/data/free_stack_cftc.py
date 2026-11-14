"""OPTIONS-IMPLIED POSITIONING FROM THE CFTC -- the lawful stand-in for exchange options OI.

Why this exists (2026-11-13): a dealer-gamma / options-flow family needs options open interest,
and every exchange that publishes it (Cboe, CME, OCC, Nasdaq, MIAX, Montreal, ASX, Eurex) either
refuses automated collection in its terms or walls bots off (reports/free_terminal_alternatives/
JOURNAL.md, 22:10Z and 22:15Z). The CFTC is a US federal agency: its Commitments of Traders
reports are public domain, served keyless through its Socrata portal, and it publishes the same
legacy report twice -- FUTURES ONLY and FUTURES-AND-OPTIONS COMBINED, where each option is
counted at its delta. The difference between the two IS the options book, per trader class:

    <SYM>_spec_net_comb    non-commercial net (futures + delta-adjusted options) / combined OI
    <SYM>_spec_opt_delta   (combined net - futures-only net) for non-commercials / combined OI:
                           speculators' net options delta, the side the public is on in options
    <SYM>_comm_opt_delta   the same for commercials: the hedgers' and dealers' options delta,
                           the closest public reading of who is short gamma
    <SYM>_opt_oi_share     (combined OI - futures OI) / combined OI: how much of the market's
                           exposure is carried as options this week

Every value is sign-aligned to the MT5 instrument (`cot_source.COT_MAP` convention: JPY / CHF /
CAD futures are inverted for USDJPY / USDCHF / USDCAD). Weekly, Tuesday as-of, published Friday
15:30 ET; the roster row's `lag_hours` (96) times every value from Tuesday's end to Saturday.

FAIL CLOSED. robots.txt is evaluated for the agent actually sent before EVERY request, and a
refusal sends nothing. A dataset whose rows lack the expected fields reads UNMEASURED with the
missing field named -- never a zero. The dataset ids are the CFTC's published Socrata ids; the
build sandbox cannot reach cftc.gov, so the first live reading is the box's.
"""
from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

BASE = "https://publicreporting.cftc.gov/resource/"
#: Legacy report, futures only / futures-and-options combined.
FUTURES_ONLY = "6dca-aqww"
COMBINED = "jun7-fc8e"
#: The agent sent and the agent robots is evaluated for (the same one `cot_source` sends).
AGENT = "quant-research"
FIELDS = ("report_date_as_yyyy_mm_dd", "open_interest_all", "noncomm_positions_long_all",
          "noncomm_positions_short_all", "comm_positions_long_all", "comm_positions_short_all")
#: After the first (backfill) pass, re-read this many days so a CFTC revision lands as a vintage.
REREAD_D = 28

#: MT5 symbol -> (CFTC legacy contract_market_code, sign vs the MT5 instrument). The metals,
#: FX and crude rows are `cot_source.COT_MAP`; the equity-index rows are the E-mini contracts.
CONTRACTS: dict[str, tuple[str, float]] = {
    "XAUUSD": ("088691", 1.0), "XAGUSD": ("084691", 1.0), "XPTUSD": ("076651", 1.0),
    "XPDUSD": ("075651", 1.0), "EURUSD": ("099741", 1.0), "GBPUSD": ("096742", 1.0),
    "AUDUSD": ("232741", 1.0), "USDJPY": ("097741", -1.0), "USDCHF": ("092741", -1.0),
    "USDCAD": ("090741", -1.0), "XTIUSD": ("067411", 1.0),
    "US500": ("13874A", 1.0), "NAS100": ("209742", 1.0), "US30": ("124603", 1.0),
}
#: A column also conditions these related instruments (risk-off carriers for the index books).
RELATED: dict[str, tuple[str, ...]] = {
    "US500": ("NAS100", "US30", "USDJPY", "AUDJPY"), "NAS100": ("US500",),
    "XAUUSD": ("XAGUSD",), "XTIUSD": ("XBRUSD", "USDCAD"),
}


def _robots(url: str) -> str | None:
    from libs.data.datahub_feeds import robots_refusal
    return robots_refusal(url, agent=AGENT)


#: Injected in tests; the live gate is the shared robots reader for AGENT.
ROBOTS: Callable[[str], str | None] = _robots


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def query_url(dataset: str, code: str, since: str | None) -> str:
    where = f"cftc_contract_market_code='{code}'"
    if since:
        where += f" AND report_date_as_yyyy_mm_dd >= '{since}'"
    q = {"$where": where, "$select": ",".join(FIELDS),
         "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": "5000"}
    return BASE + dataset + ".json?" + urllib.parse.urlencode(q)


def parse_rows(raw: bytes | None) -> tuple[dict[str, dict[str, float]], str]:
    """{as-of date: {field: value}} and why-not. A missing field is named, never zero-filled."""
    try:
        rows = json.loads((raw or b"").decode("utf-8", "replace") or "null")
    except ValueError:
        return {}, "response is not JSON"
    if not isinstance(rows, list):
        return {}, "response is not a row list"
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        day = str(r.get("report_date_as_yyyy_mm_dd") or "")[:10]
        vals = {f: _num(r.get(f)) for f in FIELDS[1:]}
        miss = [f for f, v in vals.items() if v is None]
        if not day or miss:
            if rows and not out:
                return {}, f"rows lack {', '.join(miss) or 'report_date_as_yyyy_mm_dd'}"
            continue
        out[day] = {k: float(v) for k, v in vals.items() if v is not None}
    return out, "" if out else "no rows"


def columns_for(fut: Mapping[str, Mapping[str, float]], comb: Mapping[str, Mapping[str, float]],
                sign: float) -> dict[str, dict[str, float]]:
    """{column suffix: {as-of date: value}} on the dates both reports carry."""
    out: dict[str, dict[str, float]] = {k: {} for k in (
        "spec_net_comb", "spec_opt_delta", "comm_opt_delta", "opt_oi_share")}
    for day in sorted(set(fut) & set(comb)):
        f, c = fut[day], comb[day]
        oi_c, oi_f = c["open_interest_all"], f["open_interest_all"]
        if oi_c <= 0:
            continue
        spec_c = c["noncomm_positions_long_all"] - c["noncomm_positions_short_all"]
        spec_f = f["noncomm_positions_long_all"] - f["noncomm_positions_short_all"]
        comm_c = c["comm_positions_long_all"] - c["comm_positions_short_all"]
        comm_f = f["comm_positions_long_all"] - f["comm_positions_short_all"]
        out["spec_net_comb"][day] = sign * spec_c / oi_c
        out["spec_opt_delta"][day] = sign * (spec_c - spec_f) / oi_c
        out["comm_opt_delta"][day] = sign * (comm_c - comm_f) / oi_c
        out["opt_oi_share"][day] = (oi_c - oi_f) / oi_c
    return out


WHY = {"spec_net_comb": "CFTC non-commercial net incl. delta-adjusted options, share of OI",
       "spec_opt_delta": "CFTC speculators' net options delta (combined minus futures-only)",
       "comm_opt_delta": "CFTC commercials' net options delta: the hedger/dealer gamma side",
       "opt_oi_share": "options share of combined open interest (options activity)"}


def fetch_cftc_options(fetch: Any, row: Mapping[str, Any], cursor: Mapping[str, Any],
                       now: datetime) -> Any:
    """The `cftc_options` kind of the free stack: one Harvest for every mapped contract."""
    from libs.data.free_stack import Harvest, _get
    h = Harvest(str(row["id"]))
    since = None
    if cursor.get("backfilled"):
        since = (now - timedelta(days=REREAD_D)).date().isoformat()
    headers = {"User-Agent": AGENT}
    gaps: list[str] = []
    for sym, (code, sign) in CONTRACTS.items():
        reports: list[dict[str, dict[str, float]]] = []
        for ds in (FUTURES_ONLY, COMBINED):
            url = query_url(ds, code, since)
            why = ROBOTS(url)
            if why:
                h.failures["robots"] += 1
                gaps.append(f"{sym}: ROBOTS_REFUSED ({why})")
                break
            parsed, why = parse_rows(_get(fetch, h, url, headers))
            if not parsed:
                gaps.append(f"{sym} {ds}: {why}")
                break
            reports.append(parsed)
        if len(reports) < 2:
            continue
        for suffix, series in columns_for(reports[0], reports[1], sign).items():
            if not series:
                continue
            col = f"{sym}_{suffix}"
            h.columns[col] = {"hypothesis": [sym, *RELATED.get(sym, ())], "event": [],
                              "why": WHY[suffix]}
            h.obs.extend({"key": col, "period_end": d, "value": round(v, 6),
                          "source_id": h.source_id, "entity": f"CFTC:{code}",
                          "asset_domain": "futures", "metric": suffix,
                          "event_time": d, "licence": "US government work, public domain"}
                         for d, v in series.items())
    h.notes.extend(gaps[:12])
    if h.obs:
        h.cursor = {"backfilled": True}
    else:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = "; ".join(gaps[:4]) or "no rows"
    return h
