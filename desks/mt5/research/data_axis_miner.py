"""HUNT DATA AXES, NOT MORE STRATEGY PROSE.

THE DISTINCTION THIS ORGAN EXISTS FOR. `deep_forest_miner` already hunts 502 grounds across 51
regions for CLAIMS -- somebody's account of a mechanism, which the desk converts into a testable
cell. That corpus is 204,581 rows and converts to 125 distinct exposures, and measured 2026-09-12
adding 74 more symbol aliases moved it by ONE. The corpus is not the constraint; the number of
distinct things it can say is, and everything it says is a claim about PRICE.

A DATA AXIS is a different object. It is an input the desk does not currently hold at all --
positioning, flow, inventories, shipping, credit, weather, nowcasts -- against which price becomes
conditionable in a way no amount of price-only mining can reproduce. The desk's own
`GAP_ANALYSIS.md` reached this conclusion independently: the binding constraint is new free data
axes, not more hypothesis-generation compute. Six of the seven REACHABLE breadth gaps are blocked
on an INPUT, not on research.

WHY THIS RAISES THE CEILING AND MORE SLEEVES DO NOT. Measured: 15 funded sleeves behave as ~7.9
independent bets, and the growth curve stops paying above 22.5% heat because of that
concentration. A new price-only family is correlated with what is already there by construction --
it reads the same bars. A new AXIS is the only thing that can add a bet whose errors are
structurally independent, which is what n_eff counts and what the heat ceiling is set by.

WHAT IT WILL NOT DO. It does not download anything, it does not ingest, and it never marks an axis
usable from a URL alone. Each candidate is PROBED for reachability and recorded with what was
actually observed: reachable, refused, or unmeasured with the error. A source that cannot be
reached from this box is not a capability the desk has, whatever its documentation says --
`fetch_dukascopy` was ported, offline-tested and then found unreachable (URLError), and that is
exactly the shape this file is built to surface rather than hide.

PIT-SAFETY IS A FIRST-CLASS FIELD. An axis whose history is silently revised is worse than no
axis: it back-dates knowledge the desk never had and every backtest conditioned on it is void.
`revision_safe` records whether the publisher stamps vintages. Unknown is recorded as unknown.

    python desks/mt5/research/data_axis_miner.py [--probe] [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "DATA_AXES.json"
CATALOGUE = DESK / "data" / "data_axes.json"

UA = "quant-desk-axis-miner/1.0 (research; contact via repo)"
TIMEOUT = 20

#: EVERY AXIS IS FREE AND KEYLESS. That is the entry bar, not a preference: a source behind a key
#: is a dependency on a relationship, and this desk has been burned by an exposed key already.
#: A paid source may still be the right answer -- it is then a PURCHASE decision for the principal,
#: recorded in the CEO docket, never a silent dependency introduced by a miner.
#:
#: `binds_to` names the MT5 instruments the axis can actually condition. An axis that conditions
#: nothing the desk trades is intellectually interesting and worth zero here, and saying so in the
#: record is how the catalogue avoids becoming a list of nice ideas.
AXES: tuple[dict, ...] = (
    # ---------------------------------------------------------------- POSITIONING
    {"axis": "positioning", "id": "cftc_cot_legacy",
     "what": "CFTC Commitments of Traders: commercial / non-commercial net positioning, weekly",
     "url": "https://www.cftc.gov/dea/newcot/deafut.txt",
     "binds_to": ["XAUUSD", "XAGUSD", "XTIUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "US500"],
     "unblocks": ["cot_positioning"],
     "revision_safe": "yes -- weekly release, dated, never revised in place",
     "why_independent": "a weekly positioning extreme is not a function of the intraday range; "
                        "its errors have no reason to correlate with a breakout family's"},
    {"axis": "positioning", "id": "cftc_cot_disaggregated",
     "what": "CFTC disaggregated COT: producer/swap/managed-money split",
     "url": "https://www.cftc.gov/dea/newcot/f_disagg.txt",
     "binds_to": ["XAUUSD", "XAGUSD", "XTIUSD", "XNGUSD", "WHEAT", "CORN", "SUGAR"],
     "unblocks": ["cot_positioning"],
     "revision_safe": "yes",
     "why_independent": "separates hedger from speculator flow, which the legacy report blends"},
    # ---------------------------------------------------------------- MACRO STATE
    {"axis": "macro_state", "id": "fred_series",
     "what": "FRED: rates, spreads, DXY, real yields, breakevens -- daily, dated",
     "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
     "binds_to": ["XAUUSD", "USDJPY", "EURUSD", "UST10Y", "US500", "NAS100"],
     "unblocks": ["macro_conditional"],
     "revision_safe": "VINTAGES EXIST (ALFRED) but the plain CSV is the CURRENT vintage only -- "
                      "conditioning on it is a lookahead unless the vintage endpoint is used",
     "why_independent": "changes WHEN other sleeves should fire rather than adding a signal"},
    {"axis": "macro_state", "id": "ecb_sdw",
     "what": "ECB Statistical Data Warehouse: euro-area rates, FX references",
     "url": ("https://data-api.ecb.europa.eu/service/data/EXR/"
             "D.USD.EUR.SP00.A?lastNObservations=5&format=csvdata"),
     "binds_to": ["EURUSD", "EURGBP", "EURJPY", "GER40", "EUSTX50"],
     "unblocks": ["macro_conditional"],
     "revision_safe": "yes -- SDMX carries the vintage",
     "why_independent": "a euro-area policy series conditions the EUR crosses specifically"},
    # ---------------------------------------------------------------- ENERGY / INVENTORIES
    {"axis": "inventories", "id": "eia_petroleum",
     "what": "EIA weekly petroleum status: crude/product stocks, dated",
     "url": "https://ir.eia.gov/wpsr/psw01.txt",
     "binds_to": ["XTIUSD", "XBRUSD", "XNGUSD"],
     "unblocks": ["macro_conditional", "event_reaction"],
     "revision_safe": "yes -- weekly, dated, revisions published as new rows",
     "why_independent": "a physical stock level is not derivable from the price series"},
    {"axis": "inventories", "id": "eia_natgas",
     "what": "EIA weekly natural gas storage",
     "url": "https://ir.eia.gov/ngs/wngsr.txt",
     "binds_to": ["XNGUSD"],
     "unblocks": ["macro_conditional"],
     "revision_safe": "yes",
     "why_independent": "storage against a five-year band is a seasonal state the "
                        "price series does not carry"},
    # ---------------------------------------------------------------- TRADE / SHIPPING
    {"axis": "trade_flow", "id": "un_comtrade",
     "what": "UN Comtrade: bilateral goods flows, monthly",
     "url": "https://comtradeapi.un.org/public/v1/preview/C/A/HS",
     "binds_to": ["AUDUSD", "USDZAR", "USDMXN", "USDCNH", "XCUUSD"],
     "unblocks": ["macro_conditional"],
     "revision_safe": "revised -- vintage must be captured at read time",
     "why_independent": "a commodity exporter's terms of trade drives its currency on a monthly "
                        "clock no intraday family observes"},
    # ---------------------------------------------------------------- WEATHER / HARVEST
    {"axis": "weather", "id": "noaa_cpc",
     "what": "NOAA Climate Prediction Center: drought / precipitation anomalies",
     "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/cdus/degree_days/",
     "binds_to": ["WHEAT", "CORN", "SOYBEAN", "SUGAR", "XNGUSD"],
     "unblocks": ["macro_conditional"],
     "revision_safe": "yes -- observations are dated and not revised",
     "why_independent": "a physical supply shock to softs is orthogonal to every FX mechanism"},
    # ---------------------------------------------------------------- MICROSTRUCTURE
    {"axis": "microstructure", "id": "dukascopy_ticks",
     "what": "Dukascopy tick bid/ask back to ~2003 -- the SPREAD SERIES itself",
     "url": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/05/03/14h_ticks.bi5",
     "binds_to": ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY"],
     "unblocks": ["liquidity_regime"],
     "revision_safe": "yes -- tick history is not revised",
     "why_independent": "an execution-derived state; the only axis that makes liquidity_regime "
                        "testable at all"},
    # ---------------------------------------------------------------- CREDIT / SOVEREIGN
    {"axis": "credit", "id": "ecb_yield_curve",
     "what": "ECB euro-area AAA yield curve, daily",
     "url": ("https://data-api.ecb.europa.eu/service/data/YC/"
             "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y?lastNObservations=5&format=csvdata"),
     "binds_to": ["EURUSD", "GER40", "EUSTX50", "UST10Y"],
     "unblocks": ["macro_conditional", "cross_asset_residual"],
     "revision_safe": "yes",
     "why_independent": "curve shape conditions risk appetite across every book simultaneously"},
    # ---------------------------------------------------------------- OFFICIAL RATES
    {"axis": "policy", "id": "bis_policy_rates",
     "what": "BIS central bank policy rates, all reporting countries",
     "url": "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip",
     "binds_to": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDZAR", "USDMXN", "USDTRY"],
     "unblocks": ["carry", "macro_conditional"],
     "revision_safe": "yes -- dated, and the carry differential is the mechanism itself",
     "why_independent": "the policy differential IS the carry family's input; without it carry is "
                        "priced off broker swap quotes alone"},
)


def probe(url: str) -> dict:
    """Reach it, or say exactly why not. A source is never marked usable from documentation."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t0 = datetime.now(tz=UTC)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(4096)
            return {"reachable": True, "status": getattr(r, "status", 200),
                    "bytes_sampled": len(body),
                    "ms": int((datetime.now(tz=UTC) - t0).total_seconds() * 1000)}
    except urllib.error.HTTPError as e:
        return {"reachable": False, "status": e.code, "why": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"reachable": False, "status": None,
                "why": f"URLError: {e.reason} -- egress to this host may be refused on this box"}
    except Exception as e:
        return {"reachable": False, "status": None, "why": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------------- DISCOVERY

#: Hosts that publish DATA, as opposed to hosts that publish opinions about data. A mined corpus
#: is mostly forum prose and blog posts, so a bare URL count is noise; these are the domains whose
#: appearance in a claim usually means somebody is citing a SERIES.
DATA_HOST_HINTS: tuple[str, ...] = (
    "stlouisfed.org", "ecb.europa.eu", "bis.org", "imf.org", "worldbank.org", "oecd.org",
    "eia.gov", "cftc.gov", "sec.gov", "treasury.gov", "bls.gov", "census.gov", "noaa.gov",
    "usda.gov", "eurostat", "ons.gov.uk", "statcan.gc.ca", "stat.go.jp", "rba.gov.au",
    "boj.or.jp", "bankofengland.co.uk", "snb.ch", "comtrade", "nasdaq.com/data",
    "data.gov", "datahub", "opendata", "dataset", "timeseries", "stats.gov.cn", "customs.gov.cn",
    "kaggle.com/datasets", "zenodo.org", "figshare", "dataverse", "/api/", "api.",
)

#: Phrases that name a MEASUREMENT rather than a mechanism. A claim carrying one of these is worth
#: reading for an axis even with no URL attached, because the phrase names the series well enough
#: that the source can be found from the name.
AXIS_WORDS: tuple[str, ...] = (
    "open interest", "positioning", "commitments of traders", "net long", "net short",
    "inventories", "stockpiles", "storage report", "rig count", "shipments", "freight rate",
    "baltic dry", "port congestion", "order book", "bid-ask", "auction", "issuance",
    "yield curve", "term spread", "breakeven", "swap spread", "credit spread", "repo rate",
    "funding rate", "basis", "carry", "nowcast", "surprise index", "revision", "consensus",
    "fund flows", "etf flows", "short interest", "borrow rate", "seasonality", "harvest",
    "drought", "crop condition", "weather anomaly", "tariff", "sanction", "export ban",
    "quota", "production cut", "customs", "electricity demand", "pipeline flow",
)

_URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)([^\s\"'<>\]\\)]*)")


def discover(limit_files: int = 1200) -> dict:
    """Read the mined corpus for DATA SOURCES rather than for strategy claims.

    THE SAME CORPUS, A DIFFERENT QUESTION. `local_converter` asks each mined row "does this name a
    mechanism I can test". This asks "does this name a MEASUREMENT I do not hold". The second
    question has barely been asked, and it is the one whose answers raise n_eff: 204,581 rows
    convert to 125 exposures and adding 74 conversion aliases moved that by one, because the
    corpus is saturated in mechanisms. It is not saturated in CITATIONS.

    THIS IS WHERE EVERY SEAT'S AXIS HUNTING LANDS. deepseek, kimi, the blind researcher, the
    strategic director and the hypothesis generator all carry DATA_AXIS_MANDATE now and all donate
    into `data/intelligence/<seat>/`, which is exactly the tree this walks. So a seat naming a
    Chinese customs series or a Brazilian port-congestion feed shows up here as a candidate host
    on the next hourly pass, with no per-seat plumbing.

    IT PROPOSES, IT DOES NOT INGEST. A discovered host is a CANDIDATE with a count and an example,
    written into the report for the CEO docket to rank. Nothing is probed, trusted or ingested
    from a mention: a URL in a forum post is evidence that somebody cited a source, never evidence
    that the source exists, is free, is dated, or binds to anything this desk trades.
    """
    roots = [ROOT / "data" / "intelligence", DESK / "data" / "intelligence"]
    hosts: Counter[str] = Counter()
    words: Counter[str] = Counter()
    examples: dict[str, str] = {}
    seats: Counter[str] = Counter()
    known = {a["url"].split("/")[2].lower() for a in AXES if "://" in a["url"]}
    n_files = 0

    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl")):
            if n_files >= limit_files:
                break
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            n_files += 1
            low = text.lower()
            for w in AXIS_WORDS:
                c = low.count(w)
                if c:
                    words[w] += c
            seat = p.parent.name
            for m in _URL_RE.finditer(text):
                host = m.group(1).lower()
                path = (m.group(2) or "").lower()
                if host in known:
                    continue
                if not any(h in host or h in path for h in DATA_HOST_HINTS):
                    continue
                hosts[host] += 1
                seats[seat] += 1
                examples.setdefault(host, m.group(0)[:180])

    cands = [{"host": h, "mentions": n, "example": examples.get(h),
              "status": "CANDIDATE -- cited in the corpus, never probed",
              "next": "probe it, then bind it to the MT5 instruments it can condition"}
             for h, n in hosts.most_common(40)]
    return {
        "files_scanned": n_files,
        "n_candidate_hosts": len(cands),
        "candidate_hosts": cands,
        "by_seat": dict(seats.most_common(15)),
        "axis_vocabulary_hits": dict(words.most_common(30)),
        "why": ("the corpus is saturated in MECHANISMS and not in CITATIONS. Which MEASUREMENTS "
                "it mentions is a different question with a different ceiling, and its answers "
                "are the only ones that lower rho rather than approach 1/rho."),
        "boundary": ("a mention is not a source. Nothing here is probed, ingested or trusted -- "
                     "these are candidates for the CEO docket to rank."),
    }


def build(do_probe: bool) -> dict:
    rows = []
    for a in AXES:
        row = dict(a)
        row["probe"] = probe(a["url"]) if do_probe else {"reachable": None,
                                                         "why": "not probed this pass"}
        rows.append(row)
    reach = [r for r in rows if r["probe"].get("reachable") is True]
    unreach = [r for r in rows if r["probe"].get("reachable") is False]
    unblocks: dict[str, list[str]] = {}
    for r in reach:
        for fam in r.get("unblocks") or []:
            unblocks.setdefault(fam, []).append(r["id"])
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "discovery": discover(),
        "n_axes": len(rows),
        "n_distinct_axis_kinds": len({r["axis"] for r in rows}),
        "n_reachable": len(reach),
        "n_unreachable": len(unreach),
        "probed": do_probe,
        "families_unblocked_by_a_reachable_source": unblocks,
        "axes": rows,
        "rule": ("free and keyless is the entry bar. A paid source may still be right, but it is "
                 "a PURCHASE decision recorded in the CEO docket, never a silent dependency. An "
                 "axis is usable only when a PROBE reached it from this box -- documentation is "
                 "not a capability."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true", help="actually reach each source")
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build(a.probe)
    print(f"data axes: {doc['n_axes']} candidate(s) across "
          f"{doc['n_distinct_axis_kinds']} axis kinds")
    for r in doc["axes"]:
        p = r["probe"]
        mark = "OK  " if p.get("reachable") else ("FAIL" if p.get("reachable") is False else "—   ")
        extra = (f" {p.get('ms')}ms" if p.get("ms")
                 else (f" {str(p.get('why'))[:58]}" if p.get("why") else ""))
        print(f"  {mark} {r['axis']:<15} {r['id']:<26} -> {','.join(r['unblocks'])}{extra}")
    if doc["families_unblocked_by_a_reachable_source"]:
        print("  families a reachable source would unblock:")
        for fam, ids in doc["families_unblocked_by_a_reachable_source"].items():
            print(f"     {fam:<22} {', '.join(ids)}")
    d = doc.get("discovery") or {}
    if d.get("n_candidate_hosts"):
        print(f"  DISCOVERY: {d['n_candidate_hosts']} candidate host(s) cited across "
              f"{d['files_scanned']} corpus file(s), none probed")
        for c in d["candidate_hosts"][:10]:
            print(f"     {c['mentions']:>6}x  {c['host'][:56]}")
        top = list((d.get("axis_vocabulary_hits") or {}).items())[:6]
        if top:
            print("     vocabulary: " + ", ".join(f"{k} x{v}" for k, v in top))
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
