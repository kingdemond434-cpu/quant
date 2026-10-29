"""EXIT NEWS TAGS -- every live stop exit carries the economic calendar it happened inside.

2026-10-29 (slip microstructure, row 244): two of 22 E8 stop exits carried ~95% of the slip
(09-24 13:03Z, 10-02 12:30Z). 12:30Z is the US 08:30 ET data slot. Whether a scheduled release
explains the tail is a question the desk could not answer, because no exit row says where it sat
against the calendar. This enricher answers it for every exit, every hour, research-side only:
it never touches the gateway or a ledger writer.

For each exit: `news_window` = the nearest scheduled HIGH-impact release within +-15 min
({name, currency, minutes_from_release, release_utc, source}), or null.

NULL IS NOT CLEAN UNLESS THE CALENDAR COVERED THAT DAY (WS-005, libs/research/event_calendar.py).
Two lawful sources are already in the repo and nothing is invented here:

  * `data/event_calendar.json` -- FOMC decisions from federalreserve.gov, valid to 2027-12. CPI and
    NFP are DELIBERATELY absent (its `pending_sources`: bls.gov refused this host).
  * `desks/mt5/data/intelligence/ff_calendar_vintage/` -- point-in-time ForexFactory week
    snapshots (all currencies, impact graded), covering only the days the snapshots span.

So each row carries `calendar_coverage`: FULL (the vintage covers the day -- every graded
release), or FOMC_ONLY (null there means "no FOMC", and CPI/NFP/... are UNMEASURED), or NONE.

Output: reports/EXIT_NEWS_TAGS.jsonl, one row per exit keyed by `exit_id`, rewritten each run.

    python desks/mt5/research/exit_news_tag.py [--csv stop_exits.csv] [--out path]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]          # desks/mt5
ROOT = BASE.parents[1]
FOMC_FILE = ROOT / "data" / "event_calendar.json"
FF_DIR = BASE / "data" / "intelligence" / "ff_calendar_vintage"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
PROP_LEDGER = BASE / "data" / "live_ledger_prop.jsonl"        # ftmo_follower exits
E8_EXITS = BASE / "data" / "e8_gold_exit_fills.jsonl"
OUT = BASE / "reports" / "EXIT_NEWS_TAGS.jsonl"

WINDOW_MIN = 15.0
SCHEMA = "exit_news_tag/v1"


def _ts(s: object) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


# ---------------------------------------------------------------- calendar
def load_fomc(path: Path = FOMC_FILE) -> tuple[list[dict], tuple[str, str] | None]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    evs = []
    for e in doc.get("events") or []:
        t = _ts(e.get("utc"))
        if t and str(e.get("impact", "")).lower() == "high":
            evs.append({"utc": t, "name": e.get("name", "FOMC decision"), "currency": "USD",
                        "source": e.get("source", "federalreserve.gov")})
    if not evs:
        return [], None
    lo = min(e["utc"] for e in evs).date().isoformat()
    hi = str(doc.get("valid_through") or max(e["utc"] for e in evs).date().isoformat())
    return evs, (lo, hi)


def _ff_rows(d: Path):
    if not d.is_dir():
        return
    for p in sorted(d.iterdir()):
        try:
            if p.name.endswith(".jsonl.gz"):
                with gzip.open(p, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            yield json.loads(line)
                        except ValueError:
                            continue
            elif p.suffix == ".json":
                doc = json.loads(p.read_text(encoding="utf-8"))
                rows = doc if isinstance(doc, list) else (doc.get("discoveries") or
                                                          doc.get("items") or [])
                yield from (r for r in rows if isinstance(r, dict))
        except (OSError, ValueError, EOFError):
            continue


def load_ff(d: Path = FF_DIR) -> tuple[list[dict], tuple[str, str] | None]:
    """High-impact releases from the vintage snapshots, de-duplicated; span = days seen at all."""
    seen: dict[tuple[str, str], dict] = {}
    days: list[str] = []
    for r in _ff_rows(d):
        t = _ts(r.get("event_date"))
        if t is None:
            continue
        days.append(t.date().isoformat())
        if str(r.get("impact", "")).lower() != "high":
            continue
        title = str(r.get("title") or "")
        sym = (r.get("symbols") or [""])[0] or title[:3]
        name = title[len(sym) + 1:] if title.startswith(sym + " ") else title
        seen[(t.isoformat(), title)] = {"utc": t, "name": name, "currency": sym,
                                        "source": "forexfactory (ff_calendar_vintage)"}
    return list(seen.values()), ((min(days), max(days)) if days else None)


def load_calendar(fomc: Path = FOMC_FILE, ff: Path = FF_DIR) -> dict:
    fe, fspan = load_fomc(fomc)
    xe, xspan = load_ff(ff)
    return {"events": sorted(fe + xe, key=lambda e: e["utc"]), "fomc_span": fspan,
            "ff_span": xspan}


def _covered(span: tuple[str, str] | None, day: str) -> bool:
    return bool(span) and span[0] <= day <= span[1]


def tag(exit_utc: datetime, cal: dict, window_min: float = WINDOW_MIN) -> dict:
    day = exit_utc.date().isoformat()
    if _covered(cal["ff_span"], day):
        cov, unmeasured = "FULL", []
    elif _covered(cal["fomc_span"], day):
        cov, unmeasured = "FOMC_ONLY", ["CPI", "NFP", "all non-FOMC releases"]
    else:
        cov, unmeasured = "NONE", ["all"]
    best = None
    for e in cal["events"]:
        m = (exit_utc - e["utc"]).total_seconds() / 60.0
        if abs(m) <= window_min and (best is None or abs(m) < abs(best[0])):
            best = (m, e)
    nw = None
    if best:
        m, e = best
        nw = {"name": e["name"], "currency": e["currency"],
              "minutes_from_release": round(m, 2),
              "release_utc": e["utc"].strftime("%Y-%m-%dT%H:%M:%SZ"), "source": e["source"]}
    return {"news_window": nw, "calendar_coverage": cov, "unmeasured_series": unmeasured,
            "in_window": True if nw else (False if cov == "FULL" else None)}


# ---------------------------------------------------------------- exits
def _jsonl(p: Path):
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def ledger_exits() -> list[dict]:
    out = []
    for src, p in (("live_ledger", LIVE_LEDGER), ("ftmo_follower", PROP_LEDGER),
                   ("e8_gold_exit_fills", E8_EXITS)):
        for r in _jsonl(p):
            t = _ts(r.get("exit_time") or r.get("time") or r.get("exit_utc"))
            if t is None:
                continue
            key = r.get("position_id") or r.get("deal") or r.get("close_order")
            out.append({"exit_id": f"{src}:{key if key else t.isoformat()}", "source": src,
                        "exit_utc": t, "symbol": r.get("symbol"),
                        "exit_reason": r.get("exit_reason") or r.get("exit_type"),
                        "slip_pts": r.get("slip_pts")})
    return out


def csv_exits(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            t = _ts(r.get("exit_utc"))
            if t is None:
                continue
            try:
                slip = float(r.get("slip_pts", ""))
            except ValueError:
                slip = None
            out.append({"exit_id": f"{r.get('account')}:{r.get('exit_utc')}:{r.get('side')}:{i}",
                        "source": f"csv:{path.name}", "account": r.get("account"),
                        "exit_utc": t, "symbol": r.get("symbol"), "slip_pts": slip,
                        "exit_reason": r.get("basis")})
    return out


def enrich(exits: list[dict], cal: dict) -> list[dict]:
    rows = []
    for x in exits:
        row = {**x, "exit_utc": x["exit_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"),
               "schema": SCHEMA, "window_min": WINDOW_MIN}
        row.update(tag(x["exit_utc"], cal))
        rows.append(row)
    return rows


def _stats(v: list[float]) -> dict:
    if not v:
        return {"n": 0, "median": None, "max": None}
    s = sorted(v)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return {"n": n, "median": med, "max": s[-1]}


def slip_split(rows: list[dict]) -> dict:
    slip = [r for r in rows if isinstance(r.get("slip_pts"), (int, float))]
    return {"in_window": _stats([r["slip_pts"] for r in slip if r["in_window"] is True]),
            "out_of_window_measured": _stats([r["slip_pts"] for r in slip
                                              if r["in_window"] is False]),
            "untagged_unmeasured": _stats([r["slip_pts"] for r in slip
                                           if r["in_window"] is None]),
            "no_release_found_any_coverage": _stats([r["slip_pts"] for r in slip
                                                     if r["news_window"] is None])}


def write(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    cal = load_calendar()
    exits = csv_exits(a.csv) if a.csv else ledger_exits()
    rows = enrich(exits, cal)
    write(rows, a.out)
    summ = {"exits": len(rows), "in_window": sum(r["in_window"] is True for r in rows),
            "fomc_span": cal["fomc_span"], "ff_span": cal["ff_span"],
            "slip": slip_split(rows)}
    print("exit_news_tag:", json.dumps(summ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
