"""BUYBACK BLACKOUT CALENDAR -- when each repurchasing issuer is out of the market, point-in-time.

THE MECHANISM (sweep row A23). Most US issuers stop discretionary open-market repurchases from
roughly five weeks before an earnings release until shortly after it (an insider-trading-policy
blackout, not a law; 10b5-1 plans keep some buying going). Corporate repurchases are a large,
price-insensitive bid in US equities, so the FRACTION of index repurchase dollars that is in
blackout is a candidate conditioner for the index: a thinner corporate bid in peak blackout.
This module computes that fraction. It mints no cell and sizes nothing -- it publishes a FEATURE
(`data/lake/series/buyback_blackout_share.csv`, in the envelope `exogenous_conditioner` reads),
and the gauntlet decides whether it is worth anything.

EVERY INPUT IS A PUBLIC SEC FILING, DATED AT ITS ACCEPTANCE:

  EARNINGS   8-K item 2.02 ("Results of Operations") acceptances from the issuer's submissions
             index, which `form4_lane.fetch_pass` already reads once a pass. No vendor calendar.
  REPURCHASE `PaymentsForRepurchaseOfCommonStock` from the XBRL company-concept API
             (`data.sec.gov/api/xbrl/companyconcept/...`): the cash-flow line the 10-Q/10-K
             repurchase disclosure ties to. Each fact is known at its filing's ACCEPTANCE time
             (looked up by accession in the submissions index; a fact whose filing is not in the
             index is known the day AFTER its `filed` date -- late, never early).

THE WINDOW AT A DAY d, USING ONLY WHAT WAS PUBLIC BY THE END OF d:

  last  = the latest earnings acceptance at or before the end of d
  gap   = the median of up to the last four gaps between known releases (91 days with fewer
          than two), so the NEXT release is PROJECTED, never read from the future
  next  = last + gap; when d has passed it with no release, the issuer is still pending (up to
          `LATE_GRACE_D` days), which is what a blackout is
  in blackout  iff  d in [next - BLACKOUT_PRE_D, next)  or  d in [last, last + POST_H hours]

CAVEATS, CARRIED ON THE SERIES' REPORT: index membership is today's (the desk holds no PIT
membership list; NAS100 = the SEC's "Nasdaq" exchange tag, US30 = a hand list, US500 = every US
domestic filer in the share-CFD list), and the issuer set is the broker's share CFDs, not the
whole index. Both are survivorship-shaped and say so.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

try:
    from research import form4_lane as fl
except ImportError:                                         # pragma: no cover - layout
    import form4_lane as fl  # type: ignore[no-redef,import-not-found]

SERIES_DIR = fl.DESK / "data" / "lake" / "series"
SERIES = "buyback_blackout_share"
CONCEPT_URL = ("https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/"
               "PaymentsForRepurchaseOfCommonStock.json")

BLACKOUT_PRE_D = 35          # about five weeks before the release
POST_H = 48                  # to 48 hours after it
DEFAULT_GAP_D = 91
LATE_GRACE_D = 30
CONCEPT_REFRESH_D = 7
CONCEPTS_PER_PASS = 25
HISTORY_D = 400

#: Today's Dow 30, by US ticker. A hand list: the SEC publishes no index membership. Names the
#: broker does not list simply never appear.
US30_TICKERS = frozenset({
    "MMM", "AXP", "AMGN", "AMZN", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO", "DIS", "GS", "HD",
    "HON", "IBM", "JNJ", "JPM", "MCD", "MRK", "MSFT", "NKE", "NVDA", "PG", "CRM", "SHW", "TRV",
    "UNH", "VZ", "V", "WMT"})
INDICES = ("US500", "NAS100", "US30")
RULE = (f"in blackout iff the day is within {BLACKOUT_PRE_D} days before the PROJECTED next "
        f"8-K item 2.02 acceptance or within {POST_H}h after the last one; projected from the "
        "median gap of releases public by the end of that day")
CAVEATS = (
    "MEMBERSHIP IS TODAY'S: NAS100 = SEC exchange tag 'Nasdaq', US30 = a hand list of today's "
    "Dow 30, US500 = every US domestic filer among the broker's share CFDs; no point-in-time "
    "membership list exists on this desk",
    "COVERAGE IS THE BROKER'S SHARE CFDs, not the whole index; the share is of THOSE names' "
    "repurchase dollars",
    "THE NEXT RELEASE IS PROJECTED from the median gap of past 8-K item 2.02 acceptances; a "
    "blackout policy is the issuer's own and 10b5-1 plans buy through it",
)


# ------------------------------------------------------------------------------- repurchases

def parse_concept(raw: bytes, periodic: Mapping[str, str]) -> list[dict[str, Any]]:
    """XBRL company-concept JSON -> [{start, end, val, known_at, form}], USD only."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return []
    units = ((doc or {}).get("units") or {}).get("USD") or []
    out: list[dict[str, Any]] = []
    for u in units:
        if not isinstance(u, dict) or str(u.get("form") or "") not in fl.PERIODIC_FORMS:
            continue
        try:
            start = date.fromisoformat(str(u["start"]))
            end = date.fromisoformat(str(u["end"]))
            val = float(u["val"])
        except (KeyError, TypeError, ValueError):
            continue
        known = periodic.get(str(u.get("accn") or ""))
        if not known:
            try:
                filed = date.fromisoformat(str(u.get("filed")))
            except (TypeError, ValueError):
                continue
            known = (datetime(filed.year, filed.month, filed.day, tzinfo=UTC)
                     + timedelta(days=1)).isoformat()
        out.append({"start": start.isoformat(), "end": end.isoformat(), "val": val,
                    "known_at": known, "form": str(u.get("form"))})
    return out


def ttm_repurchase(facts: Sequence[Mapping[str, Any]], at: datetime) -> float | None:
    """Trailing-twelve-month repurchase dollars as known at `at`, or None when unknown.

    Annual if the latest known period is a fiscal year; otherwise prior FY + YTD now - YTD a
    year earlier (the comparative a 10-Q carries). Falls back to the latest annual figure.
    """
    known = [f for f in facts if (fl.parse_time(f.get("known_at")) or at) <= at]
    if not known:
        return None

    def span(f: Mapping[str, Any]) -> int:
        return (date.fromisoformat(str(f["end"])) - date.fromisoformat(str(f["start"]))).days

    annual = sorted((f for f in known if 340 <= span(f) <= 380), key=lambda f: str(f["end"]))
    latest_end = max(str(f["end"]) for f in known)
    if annual and str(annual[-1]["end"]) == latest_end:
        return max(0.0, float(annual[-1]["val"]))
    ytd = sorted((f for f in known if str(f["end"]) == latest_end and span(f) < 340),
                 key=span)
    if ytd and annual:
        now_f = ytd[-1]
        end = date.fromisoformat(str(now_f["end"]))
        d = span(now_f)
        prev = [f for f in known if abs(span(f) - d) <= 10
                and abs((end - date.fromisoformat(str(f["end"]))).days - 365) <= 10]
        fy = [f for f in annual
              if abs((date.fromisoformat(str(now_f["start"]))
                      - date.fromisoformat(str(f["end"]))).days) <= 10]
        if prev and fy:
            return max(0.0, float(fy[-1]["val"]) + float(now_f["val"]) - float(prev[-1]["val"]))
    return max(0.0, float(annual[-1]["val"])) if annual else None


# ------------------------------------------------------------------------------- the window

def window_at(earnings: Sequence[str], day: date) -> dict[str, Any] | None:
    """The blackout reading for one issuer at the END of `day`, from releases public by then."""
    end = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
    known = sorted(t for e in earnings if (t := fl.parse_time(e)) is not None and t < end)
    if not known:
        return None
    last = known[-1]
    gaps = [(b - a).days for a, b in pairwise(known[-5:])
            if 40 <= (b - a).days <= 200]
    gap = statistics.median(gaps) if gaps else DEFAULT_GAP_D
    nxt = last + timedelta(days=gap)
    if end > nxt + timedelta(days=LATE_GRACE_D):
        return {"last": last.isoformat(), "next": nxt.isoformat(), "in_blackout": False,
                "stale": True}
    pre = nxt - timedelta(days=BLACKOUT_PRE_D) <= end - timedelta(seconds=1)
    post = end - timedelta(seconds=1) <= last + timedelta(hours=POST_H)
    return {"last": last.isoformat(), "next": nxt.isoformat(),
            "blackout_start": (nxt - timedelta(days=BLACKOUT_PRE_D)).isoformat(),
            "blackout_end": (nxt + timedelta(hours=POST_H)).isoformat(),
            "in_blackout": bool(pre or post), "stale": False}


def members(sym: str, ticker: str, exchange: str) -> list[str]:
    out = ["US500"]
    if exchange.lower() == "nasdaq":
        out.append("NAS100")
    if ticker.upper() in US30_TICKERS:
        out.append("US30")
    return out


def daily_series(issuer_facts: Mapping[str, Mapping[str, Any]], names: Mapping[str, str],
                 now: datetime) -> list[dict[str, Any]]:
    """Per complete UTC day: per index, the equal-weight and repurchase-dollar-weighted share of
    ACTIVE repurchasers (TTM repurchases > 0 as known that day) that are in blackout."""
    first = (now - timedelta(days=HISTORY_D)).date()
    last_day = (now - timedelta(days=1)).date()
    rows: list[dict[str, Any]] = []
    d = first
    while d <= last_day:
        end = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
        acc = {ix: {"n": 0, "in": 0, "w": 0.0, "w_in": 0.0} for ix in INDICES}
        for sym, f in issuer_facts.items():
            if sym not in names:
                continue
            w = ttm_repurchase(f.get("repurchases") or [], end)
            if not w:
                continue
            win = window_at(f.get("earnings") or [], d)
            if win is None or win.get("stale"):
                continue
            for ix in members(sym, names[sym], str(f.get("exchange") or "")):
                a = acc[ix]
                a["n"] += 1
                a["w"] += w
                if win["in_blackout"]:
                    a["in"] += 1
                    a["w_in"] += w
        row: dict[str, Any] = {"event_time": d.isoformat(), "available_time": end.isoformat()}
        any_n = False
        for ix, a in acc.items():
            any_n = any_n or a["n"] > 0
            row[f"share_{ix}"] = round(a["in"] / a["n"], 6) if a["n"] else ""
            row[f"wshare_{ix}"] = round(a["w_in"] / a["w"], 6) if a["w"] else ""
            row[f"n_{ix}"] = a["n"]
        if any_n:
            rows.append(row)
        d += timedelta(days=1)
    return rows


def write_series(rows: list[dict[str, Any]], root: Path | None = None) -> Path | None:
    if not rows:
        return None
    base = root or SERIES_DIR
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{SERIES}.csv"
    head = ["event_time", "available_time", "source_id", "vintage_id",
            *[f"{p}_{ix}" for ix in INDICES for p in ("share", "wshare", "n")]]
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=head)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "source_id": SERIES, "vintage_id": r["available_time"]})
    os.replace(tmp, target)
    return target


# ------------------------------------------------------------------------------- the pass

def fetch_concepts(client: fl.EdgarClient | None, state: dict[str, Any],
                   names: Mapping[str, str]) -> dict[str, Any]:
    """Refresh each issuer's repurchase facts at most weekly, round-robin within the budget."""
    rep: dict[str, Any] = {"concepts_read": 0, "no_concept": 0}
    if client is None:
        return rep
    facts: dict[str, Any] = state.setdefault("filings", {})
    rp: dict[str, Any] = state.setdefault("repurchases", {})
    done = 0
    for sym in sorted(names):
        if client.stopped or done >= CONCEPTS_PER_PASS:
            break
        f = facts.get(sym)
        if not isinstance(f, dict) or not f.get("cik"):
            continue
        prior = rp.get(sym)
        held: dict[str, Any] = prior if isinstance(prior, dict) else {}
        when = fl.parse_time(held.get("at"))
        if when is not None and when > client.now - timedelta(days=CONCEPT_REFRESH_D):
            continue
        got = client.fetch(CONCEPT_URL.format(cik=int(f["cik"])))
        if got is None:
            break
        done += 1
        if got[0] == 404:
            rp[sym] = {"at": client.now.isoformat(), "facts": [], "why": "no such XBRL concept"}
            rep["no_concept"] += 1
            continue
        if got[0] != 200:
            continue
        rp[sym] = {"at": client.now.isoformat(),
                   "facts": parse_concept(got[1], f.get("periodic") or {})}
        rep["concepts_read"] += 1
    return rep


def windows_now(issuer_facts: Mapping[str, Mapping[str, Any]], names: Mapping[str, str],
                now: datetime) -> list[dict[str, Any]]:
    """The per-name blackout window as of now (yesterday's close), for the report and store."""
    day = (now - timedelta(days=1)).date()
    end = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
    out: list[dict[str, Any]] = []
    for sym in sorted(issuer_facts):
        if sym not in names:
            continue
        f = issuer_facts[sym]
        win = window_at(f.get("earnings") or [], day)
        if win is None:
            continue
        out.append({"symbol": sym, "ticker": names[sym], "known_at": end.isoformat(),
                    "ttm_repurchase_usd": ttm_repurchase(f.get("repurchases") or [], end),
                    "indices": members(sym, names[sym], str(f.get("exchange") or "")), **win})
    return out


def run(client: fl.EdgarClient | None, state: dict[str, Any], *, names: dict[str, str],
        state_dir: Path, now: datetime, series_root: Path | None = None) -> dict[str, Any]:
    fetched = fetch_concepts(client, state, names)
    filings = state.get("filings") or {}
    rp = state.get("repurchases") or {}
    issuer_facts = {sym: {"earnings": (filings.get(sym) or {}).get("earnings") or [],
                          "exchange": (filings.get(sym) or {}).get("exchange") or "",
                          "repurchases": (rp.get(sym) or {}).get("facts") or []}
                    for sym in names if sym in filings}
    rows = daily_series(issuer_facts, names, now)
    path = write_series(rows, series_root)
    wins = windows_now(issuer_facts, names, now)
    fl.write_json(state_dir / "blackout_windows.json",
                  {"generated_utc": now.isoformat(), "rule": RULE, "windows": wins})
    latest = rows[-1] if rows else {}
    return {"fetch": fetched, "issuers_with_earnings": sum(1 for f in issuer_facts.values()
                                                           if f["earnings"]),
            "issuers_with_repurchases": sum(1 for f in issuer_facts.values()
                                            if f["repurchases"]),
            "names_in_blackout_now": sorted(w["symbol"] for w in wins if w["in_blackout"]),
            "series": {"id": SERIES, "points": len(rows), "path": str(path) if path else None,
                       "latest": latest, "role": "candidate FEATURE (exogenous_conditioner "
                       "source); no cell minted, no size changed", "caveats": list(CAVEATS)},
            "windows": str(state_dir / "blackout_windows.json")}
