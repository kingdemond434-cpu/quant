"""TURN A REACHABLE DATA AXIS INTO A SERIES A FAMILY CAN ACTUALLY CONDITION ON.

`data_axis_miner` answers "can this box reach the source". This answers the only question after
it: "is there a dated series on disk, in the shape the family's signature asks for". A source that
is reachable and unparsed unblocks nothing -- the breadth board would still read BLOCKED, and
correctly, because `family_cot_positioning(df, cot=None)` returns no signals.

THE SHAPES ARE NOT NEGOTIABLE -- they are read off the family signatures:

    family_cot_positioning(df, *, cot: pd.DataFrame | None)   net positioning, dated, per market
    family_macro_conditional(df, *, macro: pd.Series | None)  one state variable, dated

So the ingester's job is a DataFrame and a Series, both indexed by the date the desk could have
known the value -- not the date the value describes. Those differ for every economic release and
conflating them is the lookahead this desk has already paid for once, in the regime labels.

THE CFTC RELEASE LAG IS REAL AND IS APPLIED. A COT report is stamped with Tuesday's positions and
published the following Friday at 15:30 ET. Indexing it on Tuesday would hand every backtest three
days of knowledge nobody had. `KNOWABLE_LAG_DAYS` shifts the index to the publication date, and
the shift is deliberately generous rather than exact: being a day late costs a little edge, being
a day early invents it.

SIGN CONVENTIONS ARE THE SECOND TRAP. CME currency futures are quoted as FOREIGN/USD -- a long
JPY futures position is a SHORT USDJPY position. A net-positioning series wired in with the wrong
sign is not a weak signal, it is a confidently inverted one, and it would pass every gate that
tests for significance rather than direction. `INVERT` names every market where the desk's symbol
runs the other way.

    python desks/mt5/research/axis_ingest.py [--axis cot] [--apply]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_DIR = DESK / "data" / "axes"
REPORT = DESK / "reports" / "AXIS_INGEST.json"
UA = "quant-desk-axis-ingest/1.0 (research)"
TIMEOUT = 40

COT_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"

#: ONE WEEK IS NOT A HISTORY. `deafut.txt` carries the CURRENT report only -- 26 rows across 21
#: MT5 symbols -- and `family_cot_positioning` asks for `lookback_weeks=156` to place today's
#: reading in a three-year percentile. A percentile of one observation is 100% or 0% and nothing
#: else, so ingesting the weekly file alone would have produced an axis that is present, dated,
#: correctly signed and completely unable to fire.
#:
#: The CFTC publish per-year archives containing `annual.txt` with a header row. Four years is
#: 208 weekly observations, comfortably past the 156 the family needs, and the archives are
#: immutable once the year closes -- so this is a backfill that never has to be repeated.
COT_HISTORY_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
COT_HISTORY_YEARS = 4

#: Tuesday's positions, published Friday 15:30 ET. Three days, rounded UP to four so a holiday
#: week cannot make the series knowable before it was published. Late costs edge; early invents it.
KNOWABLE_LAG_DAYS = 4

#: CFTC market name (prefix match, upper-cased) -> the MT5 instrument it conditions.
#: Prefix match rather than exact because the CFTC appends the exchange and renames it over the
#: years; the commodity half is stable and the exchange half is not.
COT_MARKETS: dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "COPPER": "XCUUSD",
    "PLATINUM": "XPTUSD",
    "PALLADIUM": "XPDUSD",
    "CRUDE OIL, LIGHT SWEET": "XTIUSD",
    "WTI-PHYSICAL": "XTIUSD",
    "NATURAL GAS": "XNGUSD",
    "EURO FX": "EURUSD",
    "BRITISH POUND": "GBPUSD",
    "JAPANESE YEN": "USDJPY",
    "SWISS FRANC": "USDCHF",
    "CANADIAN DOLLAR": "USDCAD",
    "AUSTRALIAN DOLLAR": "AUDUSD",
    "NEW ZEALAND DOLLAR": "NZDUSD",
    "MEXICAN PESO": "USDMXN",
    "SOUTH AFRICAN RAND": "USDZAR",
    "E-MINI S&P 500": "US500",
    "NASDAQ MINI": "NAS100",
    "DJIA": "US30",
    "WHEAT-SRW": "WHEAT",
    "CORN": "CORN",
    "SOYBEANS": "SOYBEAN",
    "SUGAR NO. 11": "SUGAR",
    "COTTON NO. 2": "COTTON",
}

#: Markets whose CFTC contract runs OPPOSITE to the desk's symbol. CME quotes currency futures as
#: FOREIGN/USD, so long JPY futures is short USDJPY. An inverted positioning series is not a weak
#: signal -- it is a confident wrong one, and every significance test would pass it.
INVERT = {"USDJPY", "USDCHF", "USDCAD", "USDMXN", "USDZAR"}

#: Legacy `deafut.txt` column offsets, 0-based, from the CFTC's own published layout.
C_NAME, C_DATE, C_OI = 0, 2, 7
C_NC_LONG, C_NC_SHORT, C_NC_SPREAD = 8, 9, 10
C_COMM_LONG, C_COMM_SHORT = 11, 12


def _live_urlopen(req: urllib.request.Request, timeout: float) -> Any:
    """THE ONE FETCH DOOR, LIVE INPUT (`terms_fence.guarded_urlopen(live_input=True)`): the
    first URL and every redirect hop must be a live-input route; a 30x into a held or
    IDEAS_ONLY route raises TermsFenced (pass-6 audit cf305e3d2 SHOULD-FIX 1)."""
    # polite_fetch's seam opens through that door AND checks the site's holds and the origin's
    # robots.txt on every hop first (LAWS 5e amended 2026-10-14); 401/403/429 hold the site.
    from libs.data import polite_fetch as _pf
    return _pf.polite_urlopen(req, timeout=timeout, live_input=True, leg="axis_ingest")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _live_urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _symbol_for(name: str) -> str | None:
    up = name.upper().strip().strip('"')
    for prefix, sym in COT_MARKETS.items():
        if up.startswith(prefix):
            return sym
    return None


def _cot_history_text(years: int) -> list[tuple[int, str]]:
    """(year, annual.txt) for as many years back as the archives will give.

    A year that cannot be fetched is SKIPPED WITH ITS REASON rather than failing the ingest: a
    four-year backfill that loses 2023 still places today's reading in a three-year window, and
    refusing the whole axis because one archive 404s would be absence resolving to a verdict.
    """
    import zipfile
    out: list[tuple[int, str]] = []
    this_year = datetime.now(tz=UTC).year
    for y in range(this_year, this_year - years, -1):
        try:
            req = urllib.request.Request(COT_HISTORY_URL.format(year=y),
                                         headers={"User-Agent": UA})
            with _live_urlopen(req, timeout=TIMEOUT) as r:
                blob = r.read()
            z = zipfile.ZipFile(io.BytesIO(blob))
            out.append((y, z.read(z.namelist()[0]).decode("utf-8", "replace")))
        except Exception as exc:
            print(f"  history {y}: SKIPPED -- {type(exc).__name__}: {str(exc)[:70]}")
    return out


def ingest_cot() -> dict:
    """Net speculative positioning per MT5 symbol, indexed by the date it became KNOWABLE.

    `net_pct_oi` rather than raw contracts, because contract counts are not comparable across
    markets or across decades of changing contract sizes, and the family's `extreme_pct` asks for
    a percentile of a stationary quantity. Net non-commercial as a share of open interest is the
    standard normalisation and is the one the mechanism is stated in.
    """
    blocks = [("current", _fetch(COT_URL))]
    blocks += [(str(y), txt) for y, txt in _cot_history_text(COT_HISTORY_YEARS)]
    rows: list[dict] = []
    unmapped: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for _src, raw in blocks:
      for rec in csv.reader(io.StringIO(raw)):
        if len(rec) <= C_COMM_SHORT:
            continue
        # The annual archives carry a header row; the weekly file does not.
        if rec[C_NAME].strip().strip('"').upper().startswith("MARKET AND EXCHANGE"):
            continue
        sym = _symbol_for(rec[C_NAME])
        if not sym:
            unmapped.add(rec[C_NAME].strip().strip('"')[:60])
            continue
        try:
            as_of = datetime.strptime(rec[C_DATE].strip(), "%Y-%m-%d").replace(tzinfo=UTC)
            oi = float(rec[C_OI])
            nc_long, nc_short = float(rec[C_NC_LONG]), float(rec[C_NC_SHORT])
            comm_long, comm_short = float(rec[C_COMM_LONG]), float(rec[C_COMM_SHORT])
        except (ValueError, IndexError):
            continue
        if oi <= 0:
            continue
        net_nc = nc_long - nc_short
        net_comm = comm_long - comm_short
        if sym in INVERT:
            net_nc, net_comm = -net_nc, -net_comm
        if (sym, rec[C_DATE].strip()) in seen_keys:
            continue                      # the current file overlaps this year's archive
        seen_keys.add((sym, rec[C_DATE].strip()))
        rows.append({
            "symbol": sym,
            # THE INDEX IS THE PUBLICATION DATE, NOT THE SURVEY DATE. See KNOWABLE_LAG_DAYS.
            "knowable_at": (as_of + timedelta(days=KNOWABLE_LAG_DAYS)).date().isoformat(),
            "as_of": as_of.date().isoformat(),
            "open_interest": oi,
            "net_noncommercial": net_nc,
            "net_commercial": net_comm,
            "net_pct_oi": round(net_nc / oi, 6),
            "comm_pct_oi": round(net_comm / oi, 6),
            "inverted": sym in INVERT,
        })
    rows.sort(key=lambda r: (r["symbol"], r["knowable_at"]))
    syms = sorted({r["symbol"] for r in rows})
    return {
        "axis": "positioning", "id": "cftc_cot_legacy", "source": COT_URL,
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_rows": len(rows), "symbols": syms, "n_symbols": len(syms),
        "knowable_lag_days": KNOWABLE_LAG_DAYS,
        "shape": "rows indexed by (symbol, knowable_at); family_cot_positioning reads net_pct_oi",
        "unmapped_markets_sample": sorted(unmapped)[:12],
        "n_unmapped": len(unmapped),
        "rows": rows,
    }


# ---------------------------------------------------------------------------- MACRO STATE AXES

#: BIS policy rates, every reporting central bank, one flat CSV inside a zip. THE CARRY FAMILY'S
#: ACTUAL INPUT: carry IS a rate differential, and until now the desk priced it off broker swap
#: quotes -- a vendor's number for the thing, net of the vendor's own spread, rather than the
#: thing. A policy rate is published and never revised in place, so this axis is PIT-safe by
#: construction and has no vintage games at all.
BIS_URL = "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip"

BIS_AREA_CCY = {
    "US": "USD", "XM": "EUR", "JP": "JPY", "GB": "GBP", "CH": "CHF", "CA": "CAD",
    "AU": "AUD", "NZ": "NZD", "SE": "SEK", "NO": "NOK", "MX": "MXN", "ZA": "ZAR",
    "TR": "TRY", "PL": "PLN", "HU": "HUF", "CZ": "CZK", "IL": "ILS", "KR": "KRW",
    "IN": "INR", "BR": "BRL", "CN": "CNY", "DK": "DKK", "SG": "SGD",
}

#: MT5 pair -> (base, quote). The differential the carry family wants is base minus quote, which
#: is the return to being long the pair and holding it -- so the SIGN follows the desk's symbol
#: convention, not the currency's. USDJPY carry is US minus Japan; EURUSD is euro area minus US.
CARRY_PAIRS = {
    "EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"), "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"), "USDJPY": ("USD", "JPY"), "USDCHF": ("USD", "CHF"),
    "USDCAD": ("USD", "CAD"), "USDMXN": ("USD", "MXN"), "USDZAR": ("USD", "ZAR"),
    "USDTRY": ("USD", "TRY"), "USDSEK": ("USD", "SEK"), "USDNOK": ("USD", "NOK"),
    "USDPLN": ("USD", "PLN"), "USDHUF": ("USD", "HUF"), "USDCZK": ("USD", "CZK"),
    "EURGBP": ("EUR", "GBP"), "EURJPY": ("EUR", "JPY"), "EURCHF": ("EUR", "CHF"),
    "GBPJPY": ("GBP", "JPY"), "AUDJPY": ("AUD", "JPY"), "CADJPY": ("CAD", "JPY"),
    "NZDJPY": ("NZD", "JPY"), "CHFJPY": ("CHF", "JPY"), "AUDNZD": ("AUD", "NZD"),
    "EURAUD": ("EUR", "AUD"), "EURCAD": ("EUR", "CAD"), "GBPAUD": ("GBP", "AUD"),
    "GBPCAD": ("GBP", "CAD"), "GBPCHF": ("GBP", "CHF"), "EURNOK": ("EUR", "NOK"),
    "EURSEK": ("EUR", "SEK"), "EURPLN": ("EUR", "PLN"), "EURHUF": ("EUR", "HUF"),
}

#: FRED'S EDGE ALLOWLISTS THE CLIENT TOKEN, AND `UA` IS NOT ON IT -- which is why this axis read
#: 0 series for its entire life while the other three worked on the same clock, the same box and
#: the same IP.
#:
#: MEASURED ON THE TRADING BOX 2026-09-24, one series (DGS10), same URL, same process, back to
#: back -- the only variable is this header:
#:
#:     "quant-desk-axis-ingest/1.0 (research)"      ConnectionResetError 10054 after 19.2 s
#:     "curl/8.4.0"                                 HTTP 200, 268,823 B, 0.04 s
#:     "curl/8.4.0 quant-desk-axis-ingest/1.0"      HTTP 200, 268,823 B, 0.04 s
#:     "quant-desk-axis-ingest/1.0 curl/8.4.0"      TimeoutError after 30.0 s
#:     "python-urllib/3.14"                         HTTP 200, 268,823 B, 0.11 s
#:
#: The FIRST token decides: an Akamai edge accepts the TLS handshake, then tarpits or resets the
#: response body for a token it does not recognise. No HTTP status is ever returned, so the
#: failure arrives as a timeout and reads exactly like a network fault -- which is how it survived
#: as "FRED currently times out and resets from this box's IP (7/7)", a fact about the publisher.
#: It was a fact about this string.
#:
#: AN HONEST TOKEN, NEVER ANOTHER CLIENT'S (audit of #138, MF2). The first token is the client
#: this request actually comes from -- urllib's own `Python-urllib/<version>`, exactly what
#: urllib sends with no header at all, and measured above at HTTP 200 -- and the desk's identity
#: is the second token so the publisher can see who is asking. Claiming to be `curl` to clear an
#: edge filter would be impersonating another client to pass that filter, which the desk's
#: no-bypassing data rule forbids even where, as here, the data itself is keyless and public.
#:
#: SCOPED TO FRED ON PURPOSE. `UA` is shared with BIS, COT and ECB, which were ingesting 85.9 MB,
#: 1.1 MB and 786 KB on this exact header; changing it globally would put three working axes at
#: risk to repair a fourth.
FRED_UA = f"Python-urllib/{urllib.request.__version__} quant-desk-axis-ingest/1.0"

ECB_URL = ("https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
           "?lastNObservations={n}&format=csvdata")
ECB_SERIES = {
    "eur_usd_ref": ("EXR", "D.USD.EUR.SP00.A", "ECB euro reference rate vs USD"),
    "eur_aaa_1y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y", "euro-area AAA 1y spot yield"),
    "eur_aaa_2y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y", "euro-area AAA 2y spot yield"),
    "eur_aaa_10y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "euro-area AAA 10y spot yield"),
    "eur_aaa_30y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y", "euro-area AAA 30y spot yield"),
}


def _bis_col(row, want):
    """BIS columns are 'CODE:Label'. Match on the CODE so a label change cannot break this."""
    for k in row:
        if k and k.split(":")[0].strip().upper() == want:
            return k
    return None


def ingest_bis():
    """Policy rates -> a dated carry differential for every MT5 pair we can form both legs of."""
    import zipfile
    req = urllib.request.Request(BIS_URL, headers={"User-Agent": UA})
    with _live_urlopen(req, timeout=TIMEOUT * 2) as r:
        blob = r.read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    text = z.read(z.namelist()[0]).decode("utf-8", "replace")

    by_ccy = {}
    c_area = c_time = c_val = None
    for row in csv.DictReader(io.StringIO(text)):
        if c_area is None:
            c_area = _bis_col(row, "REF_AREA")
            c_time = _bis_col(row, "TIME_PERIOD")
            c_val = _bis_col(row, "OBS_VALUE")
            if not (c_area and c_time and c_val):
                break
        area = str(row.get(c_area, "")).split(":")[0].strip().upper()
        ccy = BIS_AREA_CCY.get(area)
        if not ccy:
            continue
        try:
            v = float(row[c_val])
        except (TypeError, ValueError):
            continue
        day = str(row[c_time]).strip()[:10]
        if len(day) < 7:
            continue
        by_ccy.setdefault(ccy, {})[day] = v

    rows = []
    for sym, (base, quote) in CARRY_PAIRS.items():
        b, q = by_ccy.get(base), by_ccy.get(quote)
        if not b or not q:
            continue
        for day in sorted(set(b) & set(q)):
            rows.append({"symbol": sym, "knowable_at": day, "base": base, "quote": quote,
                         "base_rate": b[day], "quote_rate": q[day],
                         "carry_differential": round(b[day] - q[day], 6)})
    syms = sorted({r["symbol"] for r in rows})
    return {"axis": "policy", "id": "bis_policy_rates", "source": BIS_URL,
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_rows": len(rows), "symbols": syms, "n_symbols": len(syms),
            "currencies": sorted(by_ccy),
            "shape": "(symbol, knowable_at, carry_differential) -- the carry family's own input",
            "rows": rows}


def _csv_series(text, date_col, val_col):
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        d, v = row.get(date_col), row.get(val_col)
        if not d or v in (None, "", "."):
            continue
        try:
            out.append((str(d)[:10], float(v)))
        except (TypeError, ValueError):
            continue
    return sorted(out)


#: THE LIVE FRED INPUT IS PUBLIC-DOMAIN H.15 / H.10 DATA ONLY (2026-10-29).
#:
#: Read off each series' FRED page that day: DGS10, DGS2 and DFII10 (H.15 Selected Interest Rates)
#: and DTWEXBGS (H.10 Foreign Exchange Rates) are tagged "Public Domain: Citation Requested", source
#: the Board of Governors. None is discontinued.
FRED_SERIES = {
    "DGS10": "US 10y constant-maturity yield",
    "DGS2": "US 2y constant-maturity yield",
    # 2026-11-03, read off the series pages: DGS30 "Public Domain: Citation Requested", source
    # the Board of Governors, release "H.15 Selected Interest Rates". DGS5 is the same release
    # and source; its page's tag line was not read that day, so it carries the H.15 basis only.
    "DGS30": "US 30y constant-maturity yield",
    "DGS5": "US 5y constant-maturity yield",
    "DFII10": "US 10y TIPS real yield (the breakeven's second leg)",
    "DTWEXBGS": "broad trade-weighted USD index",
}

#: THE TWO SPREADS ARE DERIVED HERE, FROM THE PUBLIC-DOMAIN LEGS, UNDER THEIR OLD IDS.
#: FRED's own T10Y2Y and T10YIE pages are tagged "Copyrighted: Citation Required" (St. Louis Fed
#: computed series). Both are arithmetic on H.15 legs FRED names in their notes -- T10Y2Y is the
#: 10y minus the 2y constant-maturity yield, T10YIE the 10y nominal minus the 10y TIPS yield -- so
#: the desk computes them from the public-domain legs, on dates both legs print, and keeps the ids
#: every reader of `data/axes/fred.json` already joins on.
FRED_DERIVED = {
    "T10Y2Y": ("DGS10", "DGS2", "10y-2y term spread (derived: DGS10 - DGS2)"),
    "T10YIE": ("DGS10", "DFII10", "10y breakeven inflation (derived: DGS10 - DFII10)"),
}

#: THIRD-PARTY COPYRIGHTED SERIES: IDEAS_ONLY, NEVER LIVE INPUT (auditor ruling 2026-10-14:
#: "FRED/CBOE copyrighted series are IDEAS_ONLY"). Each is recorded in the axis document so its
#: absence reads as a terms decision, never as an empty fetch and never as zero.
FRED_IDEAS_ONLY = {
    "VIXCLS": ("Chicago Board Options Exchange: 'Copyright, 2016, Chicago Board Options Exchange, "
               "Inc. Reprinted with permission.' FRED tag 'Copyrighted: Citation Required'"),
    "BAMLH0A0HYM2": ("ICE Data Indices: 'Reproduction of this data in any form is prohibited "
                     "except with the prior written permission of ICE Data Indices.' FRED tag "
                     "'Copyrighted: Pre-Approval Required'; history cut to 3 years from 2026-04"),
}
#: The missed-growth line every hold carries: what the desk gives up is not measured.
FRED_IDEAS_ONLY_MISSED_GROWTH = {
    "delta_elogw": "UNMEASURED",
    "cause": ("third-party copyrighted series held out of live input; no conditioning family "
              "has been judged with and without it, so the forgone E[log W] is not measured"),
}

#: TWO TRANSPORTS, AND WHY THE ORDER IS THE FIX.
#:
#: The old ingester read `fred.stlouisfed.org/graph/fredgraph.csv` -- the WEBSITE's graph
#: download -- with no key. Measured on the box 2026-09-12 (data/axes/fred.json, published): 7
#: of 7 series failed, three `TimeoutError: The read operation timed out` and four
#: `ConnectionResetError: [WinError 10054]`. Every series failing at the transport, none at
#: parse, is one host refusing that address -- not seven discontinued ids (each id's FRED page
#: read 2026-10-29: none discontinued). The keyed collector reads a different host,
#: `api.stlouisfed.org` (scripts/collect_fred_macro.py: "the registry's old 'blocked' note was
#: the website host, not api.stlouisfed.org"), and the desk already holds that key at
#: `data/secrets/fred.json` on both boxes. This ingester simply never used it.
#:
#: So the keyed API (`api_key` is a query parameter -- the FRED API documents no header form) is
#: tried first, and the graph CSV is only the no-key fallback. A missing key reads NEEDS_KEY in the
#: per-series reason, never zero. The key never appears in a log, a reason or an artifact.
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
FRED_KEY_FILE = ROOT / "data" / "secrets" / "fred.json"
#: A refused rate (HTTP 429) stops the pass: no further FRED request this run. Never retried
#: around, never spread across hosts; the next scheduled run is the back-off.
FRED_RETRY_STATES = ("TIMEOUT", "RESET")


def _fred_key() -> str | None:
    """The FRED API key: `FRED_API_KEY` env, else `data/secrets/fred.json` resolved from the repo
    root (the scheduled task does not set a working directory, so a cwd-relative path would read
    NEEDS_KEY on a box that holds the key). Returned, never printed."""
    import os
    k = (os.environ.get("FRED_API_KEY") or "").strip()
    if k:
        return k
    try:
        k = str(json.loads(FRED_KEY_FILE.read_text("utf-8"))["key"]).strip()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return k or None


def _redact(text: str, key: str | None) -> str:
    return text.replace(key, "<key>") if key else text


def _classify(exc: BaseException) -> str:
    """One word per failure mode, so a reader can count them without parsing prose."""
    import socket
    import urllib.error
    if isinstance(exc, urllib.error.HTTPError):
        return "RATE_LIMITED" if exc.code == 429 else f"HTTP_{exc.code}"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    if isinstance(exc, ConnectionResetError):
        return "RESET"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "TIMEOUT"
        if isinstance(reason, ConnectionResetError):
            return "RESET"
        return "UNREACHABLE"
    return "ERROR"


def _http_error_detail(exc: BaseException) -> str:
    """FRED's API answers a refusal with a JSON `error_message`; that sentence IS the cause."""
    import urllib.error
    if not isinstance(exc, urllib.error.HTTPError):
        return ""
    try:
        body = exc.read().decode("utf-8", "replace")
        return str(json.loads(body).get("error_message") or "")[:160]
    except Exception:
        return ""


def _fred_api_points(sid: str, key: str, fetch=None) -> list[tuple[str, float]]:
    import urllib.parse
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json"})
    text = (fetch or _fetch)(f"{FRED_API_URL}?{q}")
    doc = json.loads(text)
    out = []
    for o in doc.get("observations") or []:
        v = o.get("value")
        if v in (None, "", "."):                  # FRED encodes a missing print as "."
            continue
        try:
            out.append((str(o["date"])[:10], float(v)))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out)


def _fred_csv_points(sid: str, fetch=None) -> list[tuple[str, float]]:
    text = (fetch or _fetch_fredgraph)(FRED_URL.format(sid=sid))
    lines = text.splitlines()
    if not lines or "," not in lines[0]:
        # An HTML block page or a bare error string is not a CSV. Parsing it as one returns zero
        # rows, which used to vanish into neither `series` nor `failed`.
        raise ValueError(f"NOT_CSV: response does not start with a CSV header "
                         f"({(lines[0] if lines else '')[:40]!r})")
    hdr = lines[0].split(",")
    return _csv_series(text, hdr[0], hdr[1] if len(hdr) > 1 else sid)


def _series_doc(what: str, pts: list[tuple[str, float]], **extra) -> dict:
    return {"what": what, "n": len(pts), "first": pts[0][0], "last": pts[-1][0], **extra,
            "points": [{"d": d, "v": v} for d, v in pts]}


def ingest_fred(fetch=None, key: str | None | bool = True) -> dict:
    """US rates, the dollar and the two spreads built from them -- the macro STATE series.

    EVERY SERIES ENDS IN EXACTLY ONE OF `series` OR `failed`. The old loop dropped a series that
    fetched cleanly and parsed to nothing into neither, so an empty answer looked like a smaller
    list rather than a failure. Now an empty response is `EMPTY: ...` in `failed`, with its reason,
    and `series_state[sid]` names the outcome of every series this pass asked for.

    THE VINTAGE CAVEAT IS REAL AND RECORDED. FRED serves the CURRENT vintage, so a revised series
    silently back-dates knowledge. For DAILY MARKET series -- yields, the dollar index -- there is
    nothing to revise. It would NOT be negligible for GDP or payrolls, and none is in this list.

    `fetch` and `key` exist for the fixture tests: `fetch(url) -> text`; `key=True` resolves the
    real key, `None`/`False` forces the no-key path.
    """
    import free_data as fd
    api_key = _fred_key() if key is True else (key or None)
    series, failed, state = {}, {}, {}
    transport: dict[str, str] = {}
    rate_limited = False
    # THIRD-PARTY FRED SERIES (terms_fence fred_copyrighted: VIXCLS, BAMLH0A0HYM2, ...) are
    # IDEAS_ONLY: refused BEFORE any request and carried by name as UNMEASURED_NO_LICENSED_SOURCE
    # with their missed-growth line -- never a point, never zero. The held-out FRED_IDEAS_ONLY ids
    # are recorded here without a request; a FRED_SERIES id the fence refuses ends in `failed`.
    cut: dict[str, dict] = {}
    for sid in FRED_IDEAS_ONLY:
        row = fd.fred_refusal(sid, "axis_ingest.fred")
        if row is not None:
            cut[sid] = {"what": sid, **row}
    for sid, what in FRED_SERIES.items():
        row = fd.fred_refusal(sid, "axis_ingest.fred")
        if row is not None:
            cut[sid] = {"what": what, **row}
            failed[sid] = f"TERMS: {row.get('status')} (terms_fence fred_copyrighted); not asked"
            state[sid] = "UNMEASURED_NO_LICENSED_SOURCE"
            continue
        if rate_limited:
            failed[sid] = "RATE_LIMITED: an earlier request this pass got HTTP 429; not asked"
            state[sid] = "RATE_LIMITED"
            continue
        reasons = []
        pts: list[tuple[str, float]] = []
        routes = ([("api", lambda s=sid: _fred_api_points(s, api_key, fetch))] if api_key
                  else []) + [("fredgraph", lambda s=sid: _fred_csv_points(s, fetch))]
        if not api_key:
            reasons.append("NEEDS_KEY: no FRED_API_KEY and no data/secrets/fred.json")
        for route, call in routes:
            for attempt in (1, 2):
                try:
                    pts = call()
                except Exception as exc:
                    kind = _classify(exc)
                    detail = _http_error_detail(exc) or str(exc)[:80]
                    reasons.append(_redact(f"{route}: {kind}: {type(exc).__name__}: {detail}",
                                           api_key))
                    if kind == "RATE_LIMITED":
                        rate_limited = True
                        break
                    if kind in FRED_RETRY_STATES and attempt == 1:
                        continue          # one polite retry for a transient edge failure
                    break
                if not pts:
                    reasons.append(f"{route}: EMPTY: the response parsed to 0 observations")
                break
            if pts or rate_limited:
                if pts:
                    transport[sid] = route
                break
        if pts:
            series[sid] = _series_doc(what, pts, transport=transport[sid])
            state[sid] = "OK"
        else:
            failed[sid] = "; ".join(reasons)[:400]
            state[sid] = ("RATE_LIMITED" if rate_limited else
                          "EMPTY" if all("EMPTY" in r or "NEEDS_KEY" in r for r in reasons)
                          else "ERROR")

    for sid, (a, b, what) in FRED_DERIVED.items():
        la, lb = series.get(a), series.get(b)
        if not la or not lb:
            missing = [x for x, leg in ((a, la), (b, lb)) if not leg]
            failed[sid] = f"EMPTY: derived from {a} - {b}; leg(s) {', '.join(missing)} absent"
            state[sid] = "EMPTY"
            continue
        vb = {p["d"]: p["v"] for p in lb["points"]}
        pts = [(p["d"], round(p["v"] - vb[p["d"]], 6)) for p in la["points"] if p["d"] in vb]
        if not pts:
            failed[sid] = f"EMPTY: {a} and {b} share no date"
            state[sid] = "EMPTY"
            continue
        series[sid] = _series_doc(what, pts, derived_from=[a, b])
        state[sid] = "OK"

    return {"axis": "macro_state", "id": "fred_series",
            "source": "api.stlouisfed.org (keyed), fredgraph.csv fallback",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            "series_state": state,
            "key_present": bool(api_key),
            "transport": transport,
            "ideas_only": {sid: {"terms": why, "missed_growth": FRED_IDEAS_ONLY_MISSED_GROWTH}
                           for sid, why in FRED_IDEAS_ONLY.items()},
            "vintage_note": ("CURRENT vintage only. Daily market series barely revise; no survey "
                             "or national-accounts series is in this list on purpose."),
            "shape": "series[sid].points -- one dated state variable each",
            "series": series,
            "unmeasured_no_licensed_source": cut,
            "missed_growth": [v["missed_growth"] for v in cut.values()
                              if isinstance(v.get("missed_growth"), dict)]}


def _fetch_fredgraph(url: str) -> str:
    """The fredgraph.csv website host, read with the honest `FRED_UA` its edge accepts."""
    req = urllib.request.Request(url, headers={"User-Agent": FRED_UA})
    with _live_urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def ingest_ecb():
    """Euro-area reference rates and the AAA curve -- the state the EUR crosses condition on."""
    series, failed = {}, {}
    for name, (flow, key, what) in ECB_SERIES.items():
        try:
            url = ECB_URL.format(flow=flow, key=key, n=4000)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with _live_urlopen(req, timeout=TIMEOUT) as r:
                text = r.read().decode("utf-8", "replace")
            pts = _csv_series(text, "TIME_PERIOD", "OBS_VALUE")
            if pts:
                series[name] = _series_doc(what, pts)
            else:
                # The same silent hole FRED had: a clean fetch that parses to nothing is a
                # failure with a reason, never a series quietly missing from the list.
                failed[name] = "EMPTY: the response parsed to 0 observations"
        except Exception as exc:
            failed[name] = f"{_classify(exc)}: {type(exc).__name__}: {str(exc)[:60]}"
    state = {n: ("OK" if n in series else str(failed.get(n, "")).split(":")[0] or "ERROR")
             for n in ECB_SERIES}
    return {"axis": "macro_state", "id": "ecb_sdw", "source": "data-api.ecb.europa.eu",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            "series_state": state,
            "vintage_note": "SDMX carries the vintage; these are published and not revised.",
            "shape": "series[name].points -- one dated state variable each",
            "series": series}


# ------------------------------------------------------------ JGB benchmark yields (MoF) ----
#: JAPAN MoF JGB CONSTANT-MATURITY YIELDS, the English pair of the daily `jgbcm.csv`: the current
#: month and the history since 1974, both listed on the MoF interest-rate page (read 2026-11-03).
#: Terms are the `jp_mof` row of terms_fence (PDL 1.0: "Commercial use of 'This Content' is also
#: permitted"; cite the source). Fetched with the honest `UA`, never another client's token.
JGB_URLS = ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",
            "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/"
            "jgbcme_all.csv")
JGB_TENORS = {"jgb_2y": 2, "jgb_10y": 10, "jgb_30y": 30}
#: Japanese-era prefixes the Japanese-language `jgbcm.csv` dates its rows in (R6.1.4).
_ERA = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}


def _jgb_date(cell: str) -> str | None:
    import re
    c = cell.strip()
    m = re.match(r"^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", c)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.match(r"^([MTSHR])(\d{1,2})[/.-](\d{1,2})[/.-](\d{1,2})$", c, re.I)
        if not m:
            return None
        y = _ERA[m.group(1).upper()] + int(m.group(2))
        mo, d = int(m.group(3)), int(m.group(4))
    try:
        return datetime(y, mo, d, tzinfo=UTC).date().isoformat()
    except ValueError:
        return None


def parse_jgb_csv(text: str) -> dict[str, list[tuple[str, float]]]:
    """MoF's JGB CSV -> {name: [(date, yield %)]} for the tenors in `JGB_TENORS`.

    The file opens with a title line, then a header whose first cell is `Date` (English) or
    `基準日` (Japanese) and whose tenor cells read `10Y` or `10年`. A missing print is `-`."""
    import re
    rows = list(csv.reader(io.StringIO(text)))
    hdr_at = next((i for i, r in enumerate(rows)
                   if r and r[0].strip().lstrip("﻿") in ("Date", "基準日")), None)
    if hdr_at is None:
        raise ValueError("NOT_JGB_CSV: no header row starting Date/基準日")
    col: dict[str, int] = {}
    for j, h in enumerate(rows[hdr_at]):
        m = re.match(r"^\s*(\d+)\s*(Y|年)\s*$", h)
        if m:
            for name, tenor in JGB_TENORS.items():
                if int(m.group(1)) == tenor:
                    col[name] = j
    out: dict[str, list[tuple[str, float]]] = {n: [] for n in JGB_TENORS}
    for r in rows[hdr_at + 1:]:
        d = _jgb_date(r[0]) if r else None
        if not d:
            continue
        for name, j in col.items():
            try:
                out[name].append((d, float(r[j])))
            except (IndexError, ValueError):
                continue                       # "-" is a missing print, never zero
    return {n: sorted(dict(v).items()) for n, v in out.items()}


def _decode_mof(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _live_urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def ingest_jgb(fetch=None) -> dict:
    """JGB 2y/10y/30y constant-maturity yields from MoF, current month merged over the history.

    `fetch(url) -> bytes` exists for the fixture tests. A 401/403/429 is a hard stop for the pass
    (recorded, never retried around); every series ends in `series` or `failed`."""
    merged: dict[str, dict[str, float]] = {n: {} for n in JGB_TENORS}
    reasons: list[str] = []
    for url in JGB_URLS[::-1]:                      # history first, current month overwrites
        try:
            got = parse_jgb_csv(_decode_mof((fetch or _fetch_bytes)(url)))
        except Exception as exc:
            kind = _classify(exc)
            reasons.append(f"{url.rsplit('/', 1)[-1]}: {kind}: {type(exc).__name__}: "
                           f"{str(exc)[:60]}")
            if kind in ("RATE_LIMITED", "HTTP_401", "HTTP_403"):
                break                              # a person decides; no further request
            continue
        for n, pts in got.items():
            merged[n].update(dict(pts))
    series, failed = {}, {}
    for n, tenor in JGB_TENORS.items():
        pts = sorted(merged[n].items())
        if pts:
            series[n] = _series_doc(f"JGB {tenor}y constant-maturity yield (MoF)", pts)
        else:
            failed[n] = ("; ".join(reasons)
                         or "EMPTY: the response parsed to 0 observations")[:400]
    state = {n: ("OK" if n in series else "EMPTY" if not reasons else "ERROR") for n in JGB_TENORS}
    return {"axis": "macro_state", "id": "jp_mof_jgb", "source": "www.mof.go.jp (jgbcme.csv)",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            "series_state": state,
            "terms": "terms_fence jp_mof (PDL 1.0, commercial use permitted)",
            "shape": "series[name].points -- one dated state variable each",
            "series": series}


# ------------------------------------------------------- yield-curve lake-series packs ----
#: THE CURVES AS LAKE PACKS, so `pack_cells` mints `exogenous_conditioner` cells on them. The bond
#: CFD bars stop at 2025-12-31 (UST10Y), so FX, index and bond cells need a free point-in-time
#: yield conditioner that does not depend on them. Each pack is a registry row in
#: `data/asia_sources.json` (targets declared there) and a frame at `data/lake/series/<id>.csv`.
#:
#: POINT IN TIME, PER PUBLISHER, read off each publisher's own page on 2026-11-03. Every row is
#: stamped at its AVAILABILITY, never its period date; a late stamp costs edge, an early one
#: invents it, so each rule rounds late:
#:   FRED H.15  value for day D posted the NEXT business day        -> D+1bd 22:00 UTC
#:   ECB YC     "updated every TARGET business day at noon (12:00 CET)" for the previous day, and
#:              "may ... be postponed to the following TARGET business day" -> D+1bd 12:00 UTC
#:              (later than noon CET in either season; the conditioner's own 24h lag covers a slip)
#:   MoF JGB    "released at 9:30 a.m. on the next business day" (qa.htm)  -> D+1bd 01:00 UTC
#:              (09:30 JST is 00:30 UTC). NOT same-day close: the brief's same-day reading would
#:              have stamped every JGB row up to fifteen hours early.
#: Business days are Mon-Fri; a publisher holiday makes the true time later still, and
#: `family_exogenous_conditioner` holds every series back a further 24h before it may condition.
PIT_RULES = {"fred": (22, 0), "ecb": (12, 0), "jgb": (1, 0)}

YIELD_PACKS: dict[str, dict[str, Any]] = {
    "yc_us_treasury": {"axis": "fred", "legs": {"us_2y": "DGS2", "us_5y": "DGS5",
                                                "us_10y": "DGS10", "us_30y": "DGS30"},
                       "slope": ("us_2s10s", "us_10y", "us_2y")},
    "yc_ea_aaa": {"axis": "ecb", "legs": {"ea_2y": "eur_aaa_2y", "ea_10y": "eur_aaa_10y",
                                          "ea_30y": "eur_aaa_30y"},
                  "slope": ("ea_2s10s", "ea_10y", "ea_2y")},
    "yc_jp_jgb": {"axis": "jgb", "legs": {"jp_2y": "jgb_2y", "jp_10y": "jgb_10y",
                                          "jp_30y": "jgb_30y"},
                  "slope": ("jp_2s10s", "jp_10y", "jp_2y")},
}
#: Cross-market 10y spreads. The euro leg is the ECB euro-area AAA curve, which is the free,
#: reusable stand-in for the Bund (Germany is the curve's largest AAA issuer); the column is named
#: for what it is, never `us_de`.
SPREAD_PACK = "yc_xmkt_spreads"
SPREADS = {"us_ea_aaa_10y": (("fred", "DGS10"), ("ecb", "eur_aaa_10y")),
           "us_jp_10y": (("fred", "DGS10"), ("jgb", "jgb_10y"))}
#: The MT5 instruments each pack conditions (registry `targets`, mirrored here for the tests).
PACK_TARGETS = {
    "yc_us_treasury": ["UST10Y", "UST05Y", "US500", "EURUSD", "USDJPY", "UKGILT"],
    "yc_ea_aaa": ["EURUSD", "GER40", "UKGILT", "UST10Y"],
    "yc_jp_jgb": ["USDJPY", "JPN225", "UST10Y"],
    SPREAD_PACK: ["EURUSD", "USDJPY", "GER40", "JPN225", "US500", "UST10Y", "UST05Y", "UKGILT"],
}
LAKE_SERIES = DESK / "data" / "lake" / "series"
LAKE_VAULT = DESK / "data" / "lake" / "vault"

#: THE CNY CENTRAL PARITY (CFETS fix, 09:15 Beijing) -- UNMEASURED_NO_LICENSED_SOURCE. Tried in the
#: coordinator's order on 2026-11-03: (1) chinamoney.com.cn's legal statement (/chinese/flsm/)
#: returned a client error to the reader and the PBoC host is robots-disallowed to it (terms_fence
#: cn_credit_contagion, 2026-10-14) -- no reuse clause was read, and UNREAD terms never permit
#: automated input; (2) FRED carries no CFETS fix: DEXCHUS is the H.10 noon New York buying rate,
#: a different print at a different hour, and using it as "the fix" would be a mislabelled series.
CNY_FIX_HOLD = {
    "series": "cny_central_parity",
    "status": "UNMEASURED_NO_LICENSED_SOURCE",
    "tried": {"chinamoney.com.cn/chinese/flsm/": "client_error 2026-11-03: terms UNREAD",
              "pbc.gov.cn": "ROBOTS_DISALLOWED to the reader (terms_fence, 2026-10-14)",
              "FRED DEXCHUS": "H.10 noon NY buying rate, not the 09:15 CST CFETS fix"},
    "unblock": "a CFETS or PBoC terms page read on the publisher's domain with a reuse clause",
    "missed_growth": {"delta_elogw": "UNMEASURED",
                      "cause": ("the forward farm's fix-vs-model residual has no PIT fix series; "
                                "no family has been judged with and without it")},
}


def _next_bday(d: str):
    from datetime import date
    day = date.fromisoformat(d[:10]) + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def available_time(axis: str, d: str) -> str:
    """When a value for period date `d` from `axis` could first be known, UTC ISO."""
    h, m = PIT_RULES[axis]
    nb = _next_bday(d)
    return datetime(nb.year, nb.month, nb.day, h, m, tzinfo=UTC).isoformat()


def _points(doc: dict | None, name: str) -> dict[str, float]:
    s = ((doc or {}).get("series") or {}).get(name) or {}
    return {str(p["d"])[:10]: float(p["v"]) for p in s.get("points") or []}


def _weekly_change(vals: dict[str, float]) -> dict[str, float]:
    """value(d) - the last value at or before d-7 calendar days, on the series' own dates."""
    import bisect
    days = sorted(vals)
    out: dict[str, float] = {}
    for d in days:
        back = (datetime.fromisoformat(d) - timedelta(days=7)).date().isoformat()
        i = bisect.bisect_right(days, back) - 1
        if i >= 0:
            out[d] = round(vals[d] - vals[days[i]], 6)
    return out


def build_yield_packs(docs: dict[str, dict | None]) -> dict[str, list[dict[str, Any]]]:
    """{pack id: rows}. Every row carries `event_time` (the period date), `available_time` (the
    PIT stamp above) and `source_id`; level, 2s10s slope and its weekly change are the signals."""
    packs: dict[str, list[dict[str, Any]]] = {}
    for pid, spec in YIELD_PACKS.items():
        doc = docs.get(spec["axis"])
        legs = {col: _points(doc, sid) for col, sid in spec["legs"].items()}
        name, hi, lo = spec["slope"]
        slope = {d: round(legs[hi][d] - legs[lo][d], 6) for d in legs[hi] if d in legs[lo]}
        wchg = _weekly_change(slope)
        rows = []
        for d in sorted(set().union(*legs.values())):
            row: dict[str, Any] = {"event_time": d, "source_id": pid,
                                   "available_time": available_time(spec["axis"], d)}
            row.update({c: legs[c].get(d) for c in legs})
            row[name] = slope.get(d)
            row[f"{name}_wchg"] = wchg.get(d)
            rows.append(row)
        packs[pid] = rows
    spread: dict[str, dict[str, float]] = {}
    stamp: dict[str, str] = {}
    for c, ((ax_a, sid_a), (ax_b, sid_b)) in SPREADS.items():
        la, lb = _points(docs.get(ax_a), sid_a), _points(docs.get(ax_b), sid_b)
        spread[c] = {d: round(la[d] - lb[d], 6) for d in la if d in lb}
        for d in spread[c]:
            # A spread is knowable only once BOTH legs are: the later of the two stamps.
            stamp[d] = max(stamp.get(d, ""), available_time(ax_a, d), available_time(ax_b, d))
    rows = []
    wch = {c: _weekly_change(v) for c, v in spread.items()}
    for d in sorted(stamp):
        row = {"event_time": d, "available_time": stamp[d], "source_id": SPREAD_PACK}
        for c in SPREADS:
            row[c] = spread[c].get(d)
            row[f"{c}_wchg"] = wch[c].get(d)
        rows.append(row)
    packs[SPREAD_PACK] = rows
    return packs


def publish_yield_packs(docs: dict[str, dict | None], *, series_dir: Path | None = None,
                        vault_dir: Path | None = None, apply: bool = True) -> dict[str, Any]:
    """Write each pack's frame, its PIT record and its collection marker; never replace a frame
    on disk with an empty one. Returns an axis-shaped summary `axis_ingest_all` judges liveness
    on (`series_state` per pack)."""
    import pandas as pd
    sdir, vdir = series_dir or LAKE_SERIES, vault_dir or LAKE_VAULT
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    state, failed, written = {}, {}, {}
    for pid, rows in build_yield_packs(docs).items():
        if not rows:
            state[pid] = "EMPTY"
            failed[pid] = "EMPTY: no leg delivered a dated value this pass; frame on disk kept"
            continue
        state[pid] = "OK"
        written[pid] = len(rows)
        if not apply:
            continue
        sdir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(rows)
        tmp = sdir / f"{pid}.csv.tmp"
        df.to_csv(tmp, index=False)
        os.replace(tmp, sdir / f"{pid}.csv")
        (sdir / f"{pid}.pit.json").write_text(json.dumps({
            "n_rows": len(rows), "at": now, "writer": "axis_ingest.publish_yield_packs",
            "frames": [{"status": "STAMPED", "n_rows": len(rows),
                        "available_time": "per-row; see axis_ingest.PIT_RULES",
                        "rule": PIT_RULES}]}, indent=1), encoding="utf-8")
        (vdir / pid).mkdir(parents=True, exist_ok=True)
        (vdir / pid / "door.json").write_text(json.dumps({
            "collected_by": "axis_ingest (MT5-AxisIngest)", "at": now,
            "legs": YIELD_PACKS.get(pid, {}).get("legs") or SPREADS}, default=str, indent=1),
            encoding="utf-8")
    return {"axis": "yield_packs", "id": "yield_curve_packs", "at": now,
            "n_series": len(written), "n_failed": len(failed), "failed": failed,
            "series_state": state, "rows": written, "pit_rules": PIT_RULES,
            "held": {CNY_FIX_HOLD["series"]: CNY_FIX_HOLD},
            "missed_growth": [CNY_FIX_HOLD["missed_growth"]]}


def ingest_gnn_forecast():
    """The graph-propagation miner's walk-forward next-day forecast, per instrument, as a dated
    conditioning series (`research/learned_miners.forecast_axis`). Every row is a prediction the
    desk could have made at its `knowable_at`: the model that produced it was fitted on closes
    before its `as_of` date, and `knowable_at` is the next broker day's 03:00, after the close
    the forecast used on either reading of the bar clock."""
    import learned_miners
    return learned_miners.forecast_axis("gnn")


def ingest_attention_forecast():
    """The attention miner's walk-forward next-day forecast, same shape and same clock."""
    import learned_miners
    return learned_miners.forecast_axis("attention")


INGESTERS = {"cot": ingest_cot, "bis": ingest_bis,
              "fred": ingest_fred, "ecb": ingest_ecb,
              "jgb": ingest_jgb,
              "gnn_forecast": ingest_gnn_forecast,
              "attention_forecast": ingest_attention_forecast}


def publish(axis: str, doc: dict, out_dir: Path | None = None,
            report: Path | None = REPORT) -> Path:
    """Write one ingested axis where `alpha_dsl.axis_fields` and every axis reader find it.

    The ONE write path for `data/axes/<axis>.json`, shared by `--apply` below and by producers
    that already hold the series in memory (`learned_miners.run`, which passes `report=None` so
    its hourly publish never overwrites the last manual ingest's summary)."""
    base = out_dir or OUT_DIR
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{axis}.json"
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({k: v for k, v in doc.items() if k != "rows"}, indent=1),
                          encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--axis", default="cot", choices=sorted(INGESTERS))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    try:
        doc = INGESTERS[a.axis]()
    except Exception as exc:
        print(f"{a.axis}: INGEST FAILED -- {type(exc).__name__}: {exc}")
        print("  UNMEASURED, not empty: a failed fetch is not evidence that the axis is barren.")
        return 1
    if "n_rows" in doc:
        print(f"{a.axis}: {doc['n_rows']} row(s) over {doc['n_symbols']} MT5 symbol(s)")
        print(f"  symbols  : {', '.join(doc['symbols'])}")
        if "knowable_lag_days" in doc:
            print(f"  lag      : {doc['knowable_lag_days']}d (survey -> publication)")
        if "n_unmapped" in doc:
            print(f"  unmapped : {doc['n_unmapped']} market(s) with no MT5 instrument")
        if "currencies" in doc:
            print(f"  ccys     : {', '.join(doc['currencies'])}")
    else:
        print(f"{a.axis}: {doc['n_series']} series, {doc['n_failed']} failed")
        for k, v in (doc.get("series") or {}).items():
            print(f"    {k:<14} {v['n']:>6} pts  {v['first']} -> {v['last']}  {v['what'][:42]}")
        for k, v in (doc.get("failed") or {}).items():
            print(f"    {k:<14} FAILED {v[:58]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    out = publish(a.axis, doc)
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
