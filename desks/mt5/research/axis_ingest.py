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
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

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

#: CFTC CONTRACT MARKET CODE (legacy column 3, `CFTC_Contract_Market_Code`) -> (MT5 instrument,
#: the market names the CFTC has filed that code under). THE CODE DECIDES; the name is only a
#: cross-check.
#:
#: THIS WAS A NAME-PREFIX MATCH UNTIL 2026-10-14, and a prefix is not an identity. "EURO FX"
#: is also the prefix of "EURO FX/BRITISH POUND XRATE" (299741) and "EURO FX/JAPANESE YEN XRATE"
#: (399741), so all three contracts mapped to EURUSD and the `(symbol, as_of)` dedupe kept
#: WHICHEVER ROW THE CFTC FILE HAPPENED TO LIST FIRST -- the committed axis was right only because
#: the outright sorted ahead of its crosses that week. "GOLD" likewise caught Coinbase's
#: "GOLD -1 TROY OUNCE" (088LM1), "CRUDE OIL, LIGHT SWEET" caught ICE Europe's WTI look-alike
#: (067411), and "NATURAL GAS" caught an ICE basis index while missing the NYMEX contract itself
#: (filed today as "NAT GAS NYME"). Codes survive the CFTC's renames; names do not.
#:
#: Every code verified 2026-10-14 against publicreporting.cftc.gov dataset 6dca-aqww (the legacy
#: futures-only report this file's deafut.txt/deacot<year>.zip carry), weeks after 2026-09-01.
#: The aliases are the names a code has been filed under (current name first); a row whose name
#: matches none is still mapped -- the code is authoritative -- and is COUNTED in
#: `name_mismatches` so a CFTC renumbering is seen rather than silently adopted.
COT_CODES: dict[str, tuple[str, tuple[str, ...]]] = {
    "088691": ("XAUUSD", ("GOLD",)),
    "084691": ("XAGUSD", ("SILVER",)),
    "085692": ("XCUUSD", ("COPPER- #1", "COPPER-GRADE #1", "COPPER")),
    "076651": ("XPTUSD", ("PLATINUM",)),
    "075651": ("XPDUSD", ("PALLADIUM",)),
    "067651": ("XTIUSD", ("WTI-PHYSICAL", "CRUDE OIL, LIGHT SWEET")),
    "023651": ("XNGUSD", ("NAT GAS NYME", "NATURAL GAS", "NATURAL GAS (NYME)")),
    "099741": ("EURUSD", ("EURO FX",)),
    "096742": ("GBPUSD", ("BRITISH POUND", "BRITISH POUND STERLING", "POUND STERLING")),
    "097741": ("USDJPY", ("JAPANESE YEN",)),
    "092741": ("USDCHF", ("SWISS FRANC",)),
    "090741": ("USDCAD", ("CANADIAN DOLLAR",)),
    "232741": ("AUDUSD", ("AUSTRALIAN DOLLAR",)),
    "112741": ("NZDUSD", ("NZ DOLLAR", "NEW ZEALAND DOLLAR")),
    "095741": ("USDMXN", ("MEXICAN PESO",)),
    "122741": ("USDZAR", ("SO AFRICAN RAND", "SOUTH AFRICAN RAND")),
    "13874A": ("US500", ("E-MINI S&P 500", "E-MINI S&P 500 STOCK INDEX")),
    "209742": ("NAS100", ("NASDAQ MINI", "NASDAQ-100 STOCK INDEX (MINI)")),
    "124603": ("US30", ("DJIA X $5", "DOW JONES INDUSTRIAL AVG- X $5", "DJIA")),
    "001602": ("WHEAT", ("WHEAT-SRW", "WHEAT")),
    "002602": ("CORN", ("CORN",)),
    "005602": ("SOYBEAN", ("SOYBEANS",)),
    "080732": ("SUGAR", ("SUGAR NO. 11",)),
    "033661": ("COTTON", ("COTTON NO. 2",)),
}

#: Kept for readers that list the axis's markets by name; DERIVED from `COT_CODES`, never matched.
COT_MARKETS: dict[str, str] = {names[0]: sym for sym, names in COT_CODES.values()}

#: Markets whose CFTC contract runs OPPOSITE to the desk's symbol. CME quotes currency futures as
#: FOREIGN/USD, so long JPY futures is short USDJPY. An inverted positioning series is not a weak
#: signal -- it is a confident wrong one, and every significance test would pass it.
INVERT = {"USDJPY", "USDCHF", "USDCAD", "USDMXN", "USDZAR"}

#: Legacy `deafut.txt` column offsets, 0-based, from the CFTC's own published layout.
#: Column 3 is `CFTC_Contract_Market_Code`, the identity `COT_CODES` is keyed on.
C_NAME, C_DATE, C_CODE, C_OI = 0, 2, 3, 7
C_NC_LONG, C_NC_SHORT, C_NC_SPREAD = 8, 9, 10
C_COMM_LONG, C_COMM_SHORT = 11, 12


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _market_name(name: str) -> str:
    """The commodity half of a CFTC market name ("EURO FX - CHICAGO MERCANTILE EXCHANGE" ->
    "EURO FX"), upper-cased, quotes stripped, whitespace collapsed."""
    up = " ".join(name.upper().replace('"', "").replace("'", "").split())
    return up.split(" - ")[0].strip()


def _symbol_for(code: str, name: str = "") -> tuple[str | None, bool]:
    """(MT5 symbol, name agrees) for one CFTC row, decided by its CONTRACT MARKET CODE.

    The name never decides: an unknown code is unmapped whatever it is called, and a known code
    maps whatever it is called. `name agrees` is False only when a name was given and is none of
    the names that code has been filed under -- the caller counts it, never drops the row.
    """
    entry = COT_CODES.get(str(code or "").strip().strip('"').upper())
    if entry is None:
        return None, True
    sym, aliases = entry
    if not name:
        return sym, True
    return sym, _market_name(name) in {a.upper() for a in aliases}


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
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
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
    mismatched: dict[str, str] = {}
    seen_keys: set[tuple[str, str]] = set()
    for _src, raw in blocks:
      for rec in csv.reader(io.StringIO(raw)):
        if len(rec) <= C_COMM_SHORT:
            continue
        # The annual archives carry a header row; the weekly file does not.
        if rec[C_NAME].strip().strip('"').upper().startswith("MARKET AND EXCHANGE"):
            continue
        sym, name_ok = _symbol_for(rec[C_CODE], rec[C_NAME])
        if not sym:
            unmapped.add(rec[C_NAME].strip().strip('"')[:60])
            continue
        if not name_ok:
            mismatched[rec[C_CODE].strip()] = _market_name(rec[C_NAME])[:60]
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
        "mapped_by": "cftc_contract_market_code (column 3); the market name is a cross-check",
        "name_mismatches": dict(sorted(mismatched.items())),
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

FRED_SERIES = {
    "DGS10": "US 10y constant-maturity yield",
    "DGS2": "US 2y constant-maturity yield",
    "T10Y2Y": "10y-2y term spread",
    "DTWEXBGS": "broad trade-weighted USD index",
    "T10YIE": "10y breakeven inflation",
    "BAMLH0A0HYM2": "US high-yield OAS -- credit appetite",
    "VIXCLS": "VIX",
}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

ECB_URL = ("https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
           "?lastNObservations={n}&format=csvdata")
ECB_SERIES = {
    "eur_usd_ref": ("EXR", "D.USD.EUR.SP00.A", "ECB euro reference rate vs USD"),
    "eur_aaa_1y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y", "euro-area AAA 1y spot yield"),
    "eur_aaa_10y": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "euro-area AAA 10y spot yield"),
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
    with urllib.request.urlopen(req, timeout=TIMEOUT * 2) as r:
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


def ingest_fred():
    """US rates, spreads, dollar, breakevens, credit and vol -- the macro STATE series.

    THE VINTAGE CAVEAT IS REAL AND RECORDED. fredgraph.csv serves the CURRENT vintage, so a
    revised series silently back-dates knowledge. For DAILY MARKET series -- yields, the dollar
    index, VIX, OAS -- there is nothing to revise and the risk is negligible. It would NOT be
    negligible for GDP or payrolls, and no survey or national-accounts series is in this list.
    """
    series, failed = {}, {}
    for sid, what in FRED_SERIES.items():
        try:
            req = urllib.request.Request(FRED_URL.format(sid=sid), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                text = r.read().decode("utf-8", "replace")
            hdr = text.splitlines()[0].split(",")
            pts = _csv_series(text, hdr[0], hdr[1] if len(hdr) > 1 else sid)
            if pts:
                series[sid] = {"what": what, "n": len(pts), "first": pts[0][0],
                               "last": pts[-1][0],
                               "points": [{"d": d, "v": v} for d, v in pts]}
        except Exception as exc:
            failed[sid] = f"{type(exc).__name__}: {str(exc)[:60]}"
    return {"axis": "macro_state", "id": "fred_series", "source": "fredgraph.csv",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            "vintage_note": ("CURRENT vintage only. Daily market series barely revise; no survey "
                             "or national-accounts series is in this list on purpose."),
            "shape": "series[sid].points -- one dated state variable each",
            "series": series}


def ingest_ecb():
    """Euro-area reference rates and the AAA curve -- the state the EUR crosses condition on."""
    series, failed = {}, {}
    for name, (flow, key, what) in ECB_SERIES.items():
        try:
            url = ECB_URL.format(flow=flow, key=key, n=4000)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                text = r.read().decode("utf-8", "replace")
            pts = _csv_series(text, "TIME_PERIOD", "OBS_VALUE")
            if pts:
                series[name] = {"what": what, "n": len(pts), "first": pts[0][0],
                                "last": pts[-1][0],
                                "points": [{"d": d, "v": v} for d, v in pts]}
        except Exception as exc:
            failed[name] = f"{type(exc).__name__}: {str(exc)[:60]}"
    return {"axis": "macro_state", "id": "ecb_sdw", "source": "data-api.ecb.europa.eu",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            "vintage_note": "SDMX carries the vintage; these are published and not revised.",
            "shape": "series[name].points -- one dated state variable each",
            "series": series}


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
