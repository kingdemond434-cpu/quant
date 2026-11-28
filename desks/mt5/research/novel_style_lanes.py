#!/usr/bin/env python3
"""NOVEL-STYLE LANES: two mechanisms the certificate book does not hold, built through the organs
the desk already owns (principal, 2026-10-13: "hunt tons of unknown styles").

WHY A NEW ORGAN AND NOT AN EXTENSION, checked first. Grepping the tree on 2026-10-13 found no
reader of FX option prints and no strike ladder anywhere: `forced_flow_calendar` dates EQUITY
option expiries by rule (a third Friday, no strikes), and nothing parses a swap/option data
repository. The Swiss customs lane is NOT here: it is a `Source` row in `research/alt_proxies.py`
(`ch_bazg_gold_exports`), which already owns monthly customs series, the PIT vintage store, the
lake writer and the `exogenous_conditioner` direct cells. This organ only reads that row back to
classify it. What is new here is N1's strike-ladder builder, its cell grid and the novelty verdict
for both lanes.

N1  FX OPTION-EXPIRY STRIKE PINNING into the 10:00 New York cut, then release, on EURUSD,
    USDJPY, AUDUSD and GBPUSD. Data: public FX-option prints (DTCC's public price dissemination
    of swap data, CFTC Part 43). From each print: pair, expiry date, strike and USD notional,
    stamped `available_time` = the print's own DISSEMINATION TIMESTAMP (GD audit 2026-10-14:
    Part 43 block and large-notional delays can run past any fixed slack after execution, so an
    execution-based stamp can be early). A print without a readable dissemination timestamp is
    DROPPED and counted (fail closed), never stamped from its execution time. `first_seen_at` =
    when this box read it. Aggregated into a per-(pair, expiry, strike) open-interest PROXY by
    the family itself at each decision instant, so the ladder is exactly what was known then.
    Executed by the minimal family `mt5desk.family_fx_expiry_pin` (modes `pin` and `release`).
N2  SWISS GOLD/SILVER EXPORTS BY DESTINATION (BAZG monthly customs, tariff 7108 / 7106) as a
    regime state for XAUUSD / XAGUSD: `alt_proxies.ch_bazg_gold_exports`. Its cells are the
    exogenous_conditioner direct cells and the conditioned-parent indirect cells that organ
    already mints, gated by its own release-gain test.

TERMS ARE FAIL CLOSED AND BOTH LANES ARE HELD (read 2026-10-13, quoted in TERMS_RECORD and in
alt_proxies.TERMS_EVIDENCE). DTCC's terms page, as served, says content "is proprietary or used
with permission, and unauthorized use, reproduction, or distribution is prohibited", with rights
"subject to separate agreements with DTCC"; no clause permitting automated access was readable, so
nothing is fetched and N1 is IDEAS_ONLY/HELD. BAZG grants "Freie Nutzung" but "Kommerzielle
Nutzung nur mit Bewilligung des Datenlieferanten zulässig"; a trading desk's use is commercial,
so N2 is HELD until that Bewilligung is on file. Nothing here fetches anything.

TRIALS. A HELD cell is never donated, never judged and never charged. The cell grid is published
as IDEAS_ONLY so the trial count it WILL cost is visible before any data exists; counting it is a
measurement, not a trial.

NOVELTY. Classified against `reports/STYLE_NOVELTY.json` `dominant_style_counts`, produced by
`research/style_novelty.py` (PR #377, not on this base). Import and artifact are both guarded:
absent -> UNMEASURED, never "novel". Present -> the declared closest known style is compared with
the book's dominant styles, and the return-novelty reading stays UNMEASURED until a certificate's
own signals exist (style_novelty measures certificates, and neither lane holds one).

    python desks/mt5/research/novel_style_lanes.py --once [--dry-run]
        [--fixtures DIR (only with --dry-run or --out DIR)]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "NOVEL_STYLE_LANES.json"
STYLE_NOVELTY = DESK / "reports" / "STYLE_NOVELTY.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
UNMEASURED = "UNMEASURED"
SOURCE_ID = "dtcc_ppd_fx_options"
N2_SOURCE = "ch_bazg_gold_exports"
#: (DISSEMINATION_SLACK = execution + 2h was the PIT stamp until the GD audit of 2026-10-14: Part
#: 43 block/large-notional dissemination delays can exceed any fixed slack. The print's own
#: dissemination timestamp is the stamp now, used at max(dissemination, execution).)
#: Strike buckets: the grid expiry headlines quote ("EUR 1.2bn at 1.0850"), per quote currency.
STRIKE_STEP = {"EURUSD": 0.0025, "GBPUSD": 0.0025, "AUDUSD": 0.0025, "USDJPY": 0.25}
PAIRS = ("EURUSD", "USDJPY", "AUDUSD", "GBPUSD")

# --------------------------------------------------------------------------- terms (fail closed)
TERMS_RECORD: dict[str, dict[str, Any]] = {
    SOURCE_ID: {
        "verdict": "HELD",
        "lane": "N1",
        "status": "IDEAS_ONLY",
        "terms_url": "https://www.dtcc.com/terms",
        "terms_quote": ("Content on DTCC.com is proprietary or used with permission, and "
                        "unauthorized use, reproduction, or distribution is prohibited."),
        "terms_quote_2": ("your rights to use certain material available on or through the DTCC "
                          "Site may be subject to separate agreements with DTCC"),
        "data_url": "https://pddata.dtcc.com/ppd/",
        "data_page": ("Public Price Dissemination Dashboard: a JS application; the fetched page "
                      "carried no terms, licence or download text"),
        "robots": "pddata.dtcc.com/robots.txt could not be read (fetch error)",
        "judgement": ("no clause on DTCC's own terms page that clearly permits automated access "
                      "for internal research was readable (the body past the introduction did "
                      "not render); the readable text prohibits unauthorised use. FAIL CLOSED: "
                      "never fetched. Unblock: a DTCC data agreement, or a terms clause read on "
                      "dtcc.com that permits it, recorded here verbatim"),
        "checked_at": "2026-10-13",
    },
    N2_SOURCE: {
        "verdict": "HELD",
        "lane": "N2",
        "status": "HELD_COMMERCIAL_PERMISSION",
        "terms_url": "https://www.bazg.admin.ch/de/schweizerische-aussenhandelsstatistik-aktuelle-daten",
        "terms_quote": ("Freie Nutzung. Quellenangabe ist Pflicht. Kommerzielle Nutzung nur mit "
                        "Bewilligung des Datenlieferanten zulässig."),
        "recorded_in": "desks/mt5/research/alt_proxies.py TERMS / TERMS_EVIDENCE",
        "checked_at": "2026-10-13",
    },
}


# --------------------------------------------------------------------------- N1: parse prints
#: Header words per field, matched case-insensitively against the PPD CSV header. The CFTC
#: Part 43 rewrite (2022-12) and the older slice format name the same fields differently.
_COLS: dict[str, tuple[str, ...]] = {
    "action": ("action type", "action"),
    "executed": ("execution timestamp", "execution_timestamp"),
    "disseminated": ("dissemination timestamp", "dissemination_timestamp",
                     "dissemination time", "disseminated timestamp"),
    "expiry": ("expiration date", "expiration_date", "end date"),
    "strike": ("strike price", "option strike price", "strike"),
    "pair": ("strike price currency/currency pair", "underlier id-leg 1", "underlying asset 1",
             "currency pair"),
    "n1": ("notional amount-leg 1", "notional amount leg 1", "rounded notional amount 1"),
    "c1": ("notional currency-leg 1", "notional currency leg 1", "notional currency 1"),
    "n2": ("notional amount-leg 2", "notional amount leg 2", "rounded notional amount 2"),
    "c2": ("notional currency-leg 2", "notional currency leg 2", "notional currency 2"),
    "otype": ("option type", "option_type", "embedded option type"),
    "asset": ("asset class", "asset_class", "product name", "upi fisn"),
    "id": ("dissemination identifier", "dissemination id"),
}
_SKIP_ACTIONS = frozenset({"CANC", "CANCEL", "ERRO", "ERROR", "TERM", "PRTO", "EROR"})


def _col(header: list[str], field: str) -> int | None:
    low = [h.strip().strip('"').lower() for h in header]
    for want in _COLS[field]:
        if want in low:
            return low.index(want)
    return None


def _amount(s: str) -> tuple[float | None, bool]:
    """A disseminated notional: digits, possibly capped ('1,000,000,000+'). (value, capped)."""
    raw = str(s or "").strip()
    capped = raw.endswith("+")
    try:
        v = float(raw.rstrip("+").replace(",", ""))
    except ValueError:
        return None, capped
    return (v if v > 0 else None), capped


def _ts(s: str) -> datetime | None:
    raw = str(s or "").strip()
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _pair(raw: str, c1: str, c2: str) -> str | None:
    s = re.sub(r"[^A-Z]", "", str(raw or "").upper())
    if len(s) >= 6 and s[:6] in PAIRS:
        return s[:6]
    a, b = str(c1 or "").upper().strip(), str(c2 or "").upper().strip()
    for p in PAIRS:
        if {a, b} == {p[:3], p[3:]}:
            return p
    return None


def _usd(pair: str, strike: float, legs: list[tuple[float | None, str]]) -> float | None:
    """The USD notional: a USD leg if printed; else the base-currency leg times the strike."""
    for amt, ccy in legs:
        if amt and ccy == "USD":
            return amt
    base, quote = pair[:3], pair[3:]
    for amt, ccy in legs:
        if amt and ccy == base and quote == "USD":
            return amt * strike
        if amt and ccy == quote and base == "USD" and strike > 0:
            return amt / strike
    return None


def bucket(pair: str, strike: float) -> float:
    step = STRIKE_STEP.get(pair, 0.0025)
    return round(round(strike / step) * step, 6)


def parse_ppd_csv(body: bytes, first_seen: datetime,
                  dropped: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """One row per new FX VANILLA option print on the four pairs; everything else is dropped.

    Cancels and errors are skipped, not netted: a strike never LOSES notional here, which only
    overstates a pin the gauntlet must then find (it cannot leak a future cancellation backward).
    A print is public at its own dissemination timestamp; a print without one is dropped and
    counted in `dropped["no_dissemination_time"]` (a file without the column drops every print).
    """
    drops = dropped if dropped is not None else {}
    drops.setdefault("no_dissemination_time", 0)
    text = body.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    head = rows[0]
    ix = {f: _col(head, f) for f in _COLS}
    if any(ix[f] is None for f in ("executed", "expiry", "strike")):
        return []

    def g(r: list[str], f: str) -> str:
        i = ix[f]
        return r[i] if i is not None and i < len(r) else ""

    out: list[dict[str, Any]] = []
    for r in rows[1:]:
        if str(g(r, "action")).strip().upper() in _SKIP_ACTIONS:
            continue
        asset = g(r, "asset").upper()
        if asset and not any(w in asset for w in ("FX", "FOREX", "CU", "CURRENCY")):
            continue
        if not g(r, "otype").strip():
            continue                                   # not an option print
        pair = _pair(g(r, "pair"), g(r, "c1"), g(r, "c2"))
        executed = _ts(g(r, "executed"))
        try:
            expiry = date.fromisoformat(g(r, "expiry").strip()[:10])
            strike = float(g(r, "strike").replace(",", ""))
        except ValueError:
            continue
        if pair is None or executed is None or strike <= 0 or expiry < executed.date():
            continue
        n1, cap1 = _amount(g(r, "n1"))
        n2, cap2 = _amount(g(r, "n2"))
        usd = _usd(pair, strike, [(n1, g(r, "c1").upper().strip()),
                                   (n2, g(r, "c2").upper().strip())])
        if usd is None:
            continue
        disseminated = _ts(g(r, "disseminated"))
        if disseminated is None:
            drops["no_dissemination_time"] += 1          # FAIL CLOSED: never execution-stamped
            continue
        avail = max(disseminated, executed)
        vid = hashlib.sha1(f"{g(r, 'id')}|{executed.isoformat()}|{pair}|{strike}|{usd}"
                           .encode()).hexdigest()[:16]
        out.append({"pair": pair, "expiry_date": expiry.isoformat(),
                    "strike": bucket(pair, strike), "strike_raw": strike,
                    "notional_usd": round(usd, 2), "notional_capped": bool(cap1 or cap2),
                    "event_time": executed.isoformat(timespec="seconds"),
                    "available_time": avail.isoformat(timespec="seconds"),
                    "published_time": avail.isoformat(timespec="seconds"),
                    "pit_basis": "dissemination_timestamp",
                    "retrieval_time": first_seen.isoformat(timespec="seconds"),
                    "revision_time": None, "source_id": SOURCE_ID, "vintage_id": vid})
    return out


def write_strike_series(rows: list[dict[str, Any]], series_dir: Path = SERIES_DIR) -> str | None:
    """The lake frame `mt5desk.family_fx_expiry_pin` reads. Append-only by vintage_id."""
    if not rows:
        return None
    import pandas as pd
    series_dir.mkdir(parents=True, exist_ok=True)
    target = series_dir / "fx_option_expiry_strikes.csv"
    new = pd.DataFrame(rows)
    if target.exists():
        try:
            old = pd.read_csv(target)
            new = pd.concat([old, new[~new["vintage_id"].isin(set(old["vintage_id"]))]])
        except Exception:
            pass
    tmp = target.with_suffix(f".tmp{os.getpid()}")
    new.to_csv(tmp, index=False)
    os.replace(tmp, target)
    return target.name


def ladder_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, dict[str, float]] = {}
    for r in rows:
        key = f"{r['pair']}|{r['expiry_date']}"
        by.setdefault(key, {})
        by[key][str(r["strike"])] = by[key].get(str(r["strike"]), 0.0) + float(r["notional_usd"])
    return {k: dict(sorted(v.items(), key=lambda kv: -kv[1])[:5]) for k, v in sorted(by.items())}


# --------------------------------------------------------------------------- cells
N1_GRID = {"mode": ("pin", "release"), "proximity_atr": (0.5, 1.0),
           "min_notional_usd": (5.0e8, 1.0e9)}


def n1_cells(status: str) -> list[dict[str, Any]]:
    """The pre-registered N1 grid. HELD -> IDEAS_ONLY: published, never donated, never charged."""
    out: list[dict[str, Any]] = []
    for sym in PAIRS:
        for mode in N1_GRID["mode"]:
            for prox in N1_GRID["proximity_atr"]:
                for floor in N1_GRID["min_notional_usd"]:
                    params = {"symbol": sym, "mode": mode, "proximity_atr": prox,
                              "min_notional_usd": floor, "clock": "utc"}
                    cid = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
                    out.append({
                        "cell_id": f"fx_expiry_pin.{cid}", "family": "fx_expiry_pin",
                        "symbol": sym, "chart": "H1", "params": params, "status": status,
                        "donated": False,
                        "mechanism": ("dealers long gamma at a large strike re-hedge toward it "
                                      "into the 10:00 New York cut; the hedge dies at the cut"),
                        "payer": "short-gamma option holders and spot takers hedged against the "
                                 "strike",
                        "falsifier": (f"{mode} returns on {sym} expiry days within {prox} ATR of "
                                      f"a >= {floor:.0e} USD strike are indistinguishable from "
                                      "the same bars on non-expiry days")})
    return out


#: The N2 regime cells alt_proxies mints once its terms clear: exogenous_conditioner on each
#: signal series (direct) and certified gold/silver parents gated on pace>0 / pace<0 (indirect).
N2_SIGNAL_SERIES = ("gold_exp_asia_share", "gold_exp_uk_t", "silver_exp_total_t")


def n2_cells(status: str) -> list[dict[str, Any]]:
    """The shape `alt_proxies.direct_cells` mints for each signal series x mapped instrument (the
    side is the MEASURED IC sign there, so it is left out here), plus the indirect regime gate."""
    out = []
    for series in N2_SIGNAL_SERIES:
        syms = ("XAGUSD",) if series.startswith("silver") else ("XAUUSD", "XAGUSD")
        for sym in syms:
            out.append({"family": "exogenous_conditioner", "symbol": sym, "chart": "H1",
                        "use": "direct",
                        "params": {"source": f"alt_{N2_SOURCE}__{series}",
                                   "signal": "surprise_z", "transform": "level_z",
                                   "threshold": 1.0, "lag_hours": 24},
                        "status": status, "donated": False,
                        "minted_by": "research/alt_proxies.py direct_cells (after its "
                                     "release-gain test passes on the box)"})
            out.append({"family": "<certified parent on " + sym + ">", "symbol": sym,
                        "use": "indirect",
                        "params": {"conditioner": f"alt:alt_{N2_SOURCE}__{series}:pace:gt:0"},
                        "status": status, "donated": False,
                        "minted_by": "research/alt_proxies.py indirect_cells (regime gate "
                                     "pace>0 / pace<0, applied by mt5desk.cell_modifiers)"})
    return out


# --------------------------------------------------------------------------- novelty
#: The closest known style each lane's DIRECTION CHOICE resembles, declared before any data.
#: style_novelty's ten styles are price-path styles; a pin trades toward a strike level that
#: no price window names, a release trades the departure from it.
DECLARED = {
    "N1": {"family": "fx_expiry_pin", "closest_styles": ["reversal_1bar", "momentum_6bar"],
           "why": ("pin: toward an exogenous strike level (neither side of a fixed window nor a "
                   "range edge); release: the first post-cut departure, nearest intraday "
                   "momentum")},
    "N2": {"family": "exogenous_conditioner", "closest_styles": ["trend_20d"],
           "why": ("a monthly physical-flow regime held for days: if its direction tracks the "
                   "trailing month it is trend in disguise")},
}


def _style_novelty_module() -> Any:
    """The producer on PR #377, when this host has it; None (UNMEASURED) otherwise."""
    try:
        return importlib.import_module("research.style_novelty")
    except Exception:
        return None


def novelty(report_path: Path = STYLE_NOVELTY,
            declared: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Each declared lane against the book's dominant styles; `declared` defaults to N1/N2."""
    try:
        doc = json.loads(report_path.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    sn = _style_novelty_module()
    out: dict[str, Any] = {"producer": "research/style_novelty.py (PR #377)",
                           "producer_importable": sn is not None,
                           "artifact": str(report_path), "artifact_present": doc is not None}
    dom = doc.get("dominant_style_counts") if isinstance(doc, dict) else None
    out["dominant_style_counts"] = dom if isinstance(dom, dict) else UNMEASURED
    lanes: dict[str, Any] = {}
    for lane, dec in (DECLARED if declared is None else declared).items():
        row: dict[str, Any] = {"family": dec["family"], "declared_closest": dec["closest_styles"],
                               "why": dec["why"], "return_novelty": UNMEASURED,
                               "return_novelty_why": ("no certificate: style_novelty measures a "
                                                      "certificate's own signals, and a HELD "
                                                      "lane has none")}
        if sn is not None:
            try:
                g, cls = sn.genealogy(dec["family"])
                row["genealogy"] = {"distance": g, "class": cls}
            except Exception as exc:
                row["genealogy"] = f"{UNMEASURED}: {type(exc).__name__}"
        else:
            row["genealogy"] = UNMEASURED
        if not isinstance(dom, dict) or not dom:
            row["verdict"] = UNMEASURED
            row["verdict_why"] = ("STYLE_NOVELTY.json absent on this host (its producer is on "
                                  "PR #377, not LIVE): no book to compare against")
        else:
            hits = {s: dom[s] for s in dec["closest_styles"] if s in dom}
            top = max(dom, key=lambda k: dom[k])
            row["dominant_overlap"] = hits
            row["book_top_style"] = top
            row["verdict"] = ("DECLARED_OUTSIDE_DOMINANT" if top not in dec["closest_styles"]
                              else "DECLARED_OVERLAPS_DOMINANT")
            row["verdict_why"] = ("declared only: the return-novelty projection is UNMEASURED "
                                  "until a certificate exists, so this is not a NOVEL verdict")
        lanes[lane] = row
    out["lanes"] = lanes
    return out


# --------------------------------------------------------------------------- the pass
def _n2_status() -> dict[str, Any]:
    try:
        import research.alt_proxies as ap
    except Exception as exc:
        return {"status": f"{UNMEASURED}: alt_proxies import failed ({type(exc).__name__})"}
    src = ap.BY_ID.get(N2_SOURCE)
    if src is None:
        return {"status": f"{UNMEASURED}: {N2_SOURCE} not registered"}
    return {"status": ap.status_of(src), "terms": src.terms,
            "held_substitute": dict(getattr(ap, "HELD_NO_SUBSTITUTE", {}).get(N2_SOURCE)
                                    or {"substitute": UNMEASURED}),
            "signal_series": list(src.signal_series), "instruments": src.instruments,
            "organ": "desks/mt5/research/alt_proxies.py (hourly leg alt_proxies)"}


class FixturesIntoProduction(ValueError):
    """A fixtures run aimed at the production report or strike frame."""


def run(*, dry_run: bool = False, fixtures: Path | None = None, now: datetime | None = None,
        report: Path = REPORT, series_dir: Path = SERIES_DIR,
        style_novelty_path: Path = STYLE_NOVELTY) -> dict[str, Any]:
    if fixtures is not None and not dry_run and (
            Path(report) == REPORT or Path(series_dir) == SERIES_DIR):
        raise FixturesIntoProduction(
            "--fixtures writes fixture prints only with --dry-run or with --out redirecting the "
            "report and the strike frame; refused rather than written into production")
    now = now or datetime.now(UTC)
    n1_terms = TERMS_RECORD[SOURCE_ID]
    rows: list[dict[str, Any]] = []
    fixture_files: list[str] = []
    dropped: dict[str, int] = {}
    if fixtures is not None:
        # FIXTURES ONLY: a HELD source is never fetched. A fixture pass proves the parser, the
        # PIT stamp and the lake frame; it is not a yield.
        for p in sorted(fixtures.glob("dtcc_ppd*.csv")):
            fixture_files.append(p.name)
            rows.extend(parse_ppd_csv(p.read_bytes(), now, dropped))
    written = write_strike_series(rows, series_dir) if rows and not dry_run else None
    held = n1_terms["verdict"] != "CONFIRMED"
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "organ": "novel_style_lanes",
        "mode": "fixtures" if fixtures is not None else "held_no_fetch",
        "terms": TERMS_RECORD,
        "N1": {"name": "FX option-expiry strike pinning into the 10:00 NY cut, then release",
               "pairs": list(PAIRS), "family": "fx_expiry_pin",
               "family_module": "desks/mt5/mt5desk/family_fx_expiry_pin.py",
               "data_route": ("DTCC public price dissemination (CFTC Part 43) FX option prints "
                              "-> pair/expiry/strike/USD notional, available_time = the print's "
                              "dissemination timestamp (absent -> dropped and counted), "
                              "lake frame data/lake/series/fx_option_expiry_strikes.csv"),
               "status": "IDEAS_ONLY" if held else "LIVE",
               "fetched": False, "fixture_files": fixture_files,
               "prints_parsed": len(rows) if fixtures is not None else UNMEASURED,
               "prints_dropped_no_dissemination_time": (
                   dropped.get("no_dissemination_time", 0) if fixtures is not None
                   else UNMEASURED),
               "lake_written": written, "ladder_top": ladder_summary(rows) if rows else {},
               "cells": n1_cells("IDEAS_ONLY" if held else "PROPOSED"),
               "trials_charged": 0},
        "N2": {"name": "Swiss gold/silver exports by destination as a regime for XAUUSD/XAGUSD",
               **_n2_status(),
               "cells": n2_cells("HELD" if _n2_status().get("terms") != "confirmed"
                                 else "MINTED_BY_ALT_PROXIES"),
               "trials_charged": 0},
        "novelty": novelty(style_novelty_path),
        "live_yield": ("UNMEASURED: both sources are HELD on terms and nothing is fetched; the "
                       "fixture pass proves only the parser and the PIT frame"),
    }
    doc["N1"]["n_cells"] = len(doc["N1"]["cells"])
    doc["N2"]["n_cells"] = len(doc["N2"]["cells"])
    if not dry_run:
        report.parent.mkdir(parents=True, exist_ok=True)
        tmp = report.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=False, default=str), "utf-8")
        os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="write the report and strike frame under this directory instead")
    a = ap.parse_args(argv)
    paths: dict[str, Any] = {}
    if a.out is not None:
        paths = {"report": a.out / REPORT.name, "series_dir": a.out / "series"}
    try:
        doc = run(dry_run=a.dry_run, fixtures=a.fixtures, **paths)
    except FixturesIntoProduction as exc:
        print(json.dumps({"refused": str(exc)}))
        return 2
    print(json.dumps({"N1": {k: doc["N1"][k] for k in ("status", "prints_parsed", "n_cells")},
                      "N2": {k: doc["N2"].get(k) for k in ("status", "n_cells")},
                      "novelty": {k: v.get("verdict") for k, v in doc["novelty"]["lanes"].items()},
                      "report": (str(paths.get("report", REPORT)) if not a.dry_run
                                 else None)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
