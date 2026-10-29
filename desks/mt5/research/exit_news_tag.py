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

Output: reports/EXIT_NEWS_TAGS.jsonl, one row per exit keyed by `exit_id` (source:position:deal),
rewritten each run, and reports/EXIT_NEWS_TAGS_SUMMARY.json (the contract's organ: n_in_window,
n_out_of_window, n_unmeasured, n_measured, median slip per group).

TIME (v2, audit HOLD on v1). The ledgers stamp BROKER WALL TIME with "+00:00" (basis
broker_deal_epoch / mt5_server_epoch); it is converted through bars_state.broker_to_utc, and with
no server anchor the row is UNMEASURED. A row with no exit_time is UNMEASURED -- `time` is the write
time and is never used. Coverage is the set of days the snapshots actually carry, and the whole
+-15 min window must sit inside it.

`e8_gold_exit_fills.jsonl` has no writer in this repo (the real E8 source is the box-only
e8_gold_exit_fills.csv); the path is read when it appears and skipped otherwise.

    python desks/mt5/research/exit_news_tag.py [--csv stop_exits.csv] [--out path]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]          # desks/mt5
ROOT = BASE.parents[1]
FOMC_FILE = ROOT / "data" / "event_calendar.json"
FF_DIR = BASE / "data" / "intelligence" / "ff_calendar_vintage"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
PROP_LEDGER = BASE / "data" / "live_ledger_prop.jsonl"        # ftmo_follower exits
E8_EXITS = BASE / "data" / "e8_gold_exit_fills.jsonl"
OUT = BASE / "reports" / "EXIT_NEWS_TAGS.jsonl"
SUMMARY = BASE / "reports" / "EXIT_NEWS_TAGS_SUMMARY.json"

WINDOW_MIN = 15.0
SCHEMA = "exit_news_tag/v2"


def _ts(s: object) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


# ---------------------------------------------------------------- calendar
def _days(lo: str, hi: str) -> set[str]:
    a, b = date.fromisoformat(lo), date.fromisoformat(hi)
    return {(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)}


def load_fomc(path: Path = FOMC_FILE) -> tuple[list[dict], set[str]]:
    """FOMC decisions; covered days = first decision .. valid_through (a published schedule)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], set()
    evs = []
    for e in doc.get("events") or []:
        t = _ts(e.get("utc"))
        if t and str(e.get("impact", "")).lower() == "high":
            evs.append({"utc": t, "name": e.get("name", "FOMC decision"), "currency": "USD",
                        "source": e.get("source", "federalreserve.gov")})
    if not evs:
        return [], set()
    lo = min(e["utc"] for e in evs).date().isoformat()
    hi = str(doc.get("valid_through") or max(e["utc"] for e in evs).date().isoformat())
    return evs, _days(lo, hi)


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


def load_ff(d: Path = FF_DIR) -> tuple[list[dict], set[str]]:
    """High-impact releases from the vintage snapshots, de-duplicated.

    COVERAGE IS THE SET OF UTC DAYS THE SNAPSHOTS ACTUALLY CARRY A ROW FOR (any impact), never
    min..max: a week the capture missed is a gap, and a gap is not "no release"."""
    seen: dict[tuple[str, str], dict] = {}
    days: set[str] = set()
    for r in _ff_rows(d):
        t = _ts(r.get("event_date"))
        if t is None:
            continue
        days.add(t.date().isoformat())
        if str(r.get("impact", "")).lower() != "high":
            continue
        title = str(r.get("title") or "")
        sym = (r.get("symbols") or [""])[0] or title[:3]
        name = title[len(sym) + 1:] if title.startswith(sym + " ") else title
        seen[(t.isoformat(), title)] = {"utc": t, "name": name, "currency": sym,
                                        "source": "forexfactory (ff_calendar_vintage)"}
    return list(seen.values()), days


def load_calendar(fomc: Path = FOMC_FILE, ff: Path = FF_DIR) -> dict:
    fe, fdays = load_fomc(fomc)
    xe, xdays = load_ff(ff)
    return {"events": sorted(fe + xe, key=lambda e: e["utc"]), "fomc_days": fdays,
            "ff_days": xdays}


def _span(days: set[str]) -> list[str] | None:
    return [min(days), max(days)] if days else None


def _window_inside(days: set[str], t: datetime, window_min: float) -> bool:
    """The WHOLE +-window must sit on covered days (23:55Z on the last day is not covered)."""
    w = timedelta(minutes=window_min)
    return bool(days) and all(x.date().isoformat() in days for x in (t - w, t, t + w))


def tag(exit_utc: datetime, cal: dict, window_min: float = WINDOW_MIN) -> dict:
    if _window_inside(cal["ff_days"], exit_utc, window_min):
        cov, unmeasured = "FULL", []
    elif _window_inside(cal["fomc_days"], exit_utc, window_min):
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
#: Bases whose "+00:00" stamp is really BROKER WALL TIME (gateway.py and ftmo_follower.py write
#: datetime.fromtimestamp(deal.time, tz=UTC), and MT5's deal.time is server-clock seconds).
BROKER_WALL_BASES = frozenset({"broker_deal_epoch", "mt5_server_epoch"})
TRUE_UTC_BASES = frozenset({"utc", "true_utc"})


def _broker_anchor():
    try:
        if str(BASE / "research") not in sys.path:
            sys.path.insert(0, str(BASE / "research"))
        import bars_state
        return bars_state
    except Exception:
        return None


def exit_true_utc(raw: object, basis: object, anchor=None) -> tuple[datetime | None, str]:
    """(true UTC, why). None with an UNMEASURED reason when the time cannot be lawfully placed."""
    t = _ts(raw)
    if t is None:
        return None, "UNMEASURED: no exit_time on the row"
    b = str(basis or "")
    if b in TRUE_UTC_BASES:
        return t, "utc"
    if b in BROKER_WALL_BASES:
        bs = _broker_anchor()
        if bs is None:
            return None, "UNMEASURED: bars_state.broker_to_utc unavailable"
        u = bs.broker_to_utc(t.replace(tzinfo=None), anchor) if anchor is not None else (
            bs.broker_to_utc(t.replace(tzinfo=None)))
        if u is None:
            return None, "UNMEASURED: no broker server anchor"
        return u, "broker_wall->utc via bars_state.broker_to_utc"
    return None, f"UNMEASURED: unknown timestamp_basis {b!r}"


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


def ledger_rows(src: str, rows, anchor=None) -> list[dict]:
    """Exit rows from one ledger. NEVER falls back to `time` (the write time): a row with no
    exit_time is kept, as UNMEASURED, and never tagged."""
    out = []
    for i, r in enumerate(rows):
        u, why = exit_true_utc(r.get("exit_time") or r.get("exit_utc"),
                               r.get("timestamp_basis"), anchor)
        pid = r.get("position_id") or r.get("close_order")
        deal = r.get("deal") or r.get("close_order")
        key = f"{pid}:{deal}" if (pid or deal) else f"row{i}"
        out.append({"exit_id": f"{src}:{key}", "source": src, "exit_utc": u,
                    "exit_time_raw": r.get("exit_time"), "time_basis": why,
                    "symbol": r.get("symbol"), "deal": deal, "position_id": pid,
                    "exit_reason": r.get("exit_reason") or r.get("exit_type"),
                    "slip_pts": r.get("slip_pts")})
    return out


def ledger_exits(anchor=None) -> list[dict]:
    out = []
    for src, p in (("live_ledger", LIVE_LEDGER), ("ftmo_follower", PROP_LEDGER),
                   ("e8_gold_exit_fills", E8_EXITS)):
        out += ledger_rows(src, _jsonl(p), anchor)
    return out


def csv_exits(path: Path, basis: str = "utc") -> list[dict]:
    """The row-244 slip extract: its README states E8 times are UTC and FTMO was shifted -3h."""
    out = []
    with path.open(encoding="utf-8") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            u, why = exit_true_utc(r.get("exit_utc"), basis)
            try:
                slip = float(r.get("slip_pts", ""))
            except ValueError:
                slip = None
            out.append({"exit_id": f"{r.get('account')}:{r.get('exit_utc')}:{r.get('side')}:{i}",
                        "source": f"csv:{path.name}", "account": r.get("account"),
                        "exit_utc": u, "time_basis": why, "symbol": r.get("symbol"),
                        "slip_pts": slip, "exit_reason": r.get("basis")})
    return out


def enrich(exits: list[dict], cal: dict) -> list[dict]:
    rows = []
    for x in exits:
        t = x["exit_utc"]
        row = {**x, "exit_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None,
               "schema": SCHEMA, "window_min": WINDOW_MIN}
        if t is None:
            row.update({"news_window": None, "calendar_coverage": "UNMEASURED",
                        "unmeasured_series": ["all"], "in_window": None})
        else:
            row.update(tag(t, cal))
        rows.append(row)
    return rows


def _stats(v: list[float]) -> dict:
    if not v:
        return {"n": 0, "median": None, "max": None}
    s = sorted(v)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return {"n": n, "median": med, "max": s[-1]}


def summary(rows: list[dict], cal: dict) -> dict:
    """The falsifiable organ: counts and median slip per group. One JSON object."""
    groups = {"in_window": [r for r in rows if r["in_window"] is True],
              "out_of_window": [r for r in rows if r["in_window"] is False],
              "unmeasured": [r for r in rows if r["in_window"] is None]}
    doc: dict = {"schema": SCHEMA + "/summary",
                 "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "n_exits": len(rows), "window_min": WINDOW_MIN,
                 "ff_span": _span(cal["ff_days"]), "ff_days_covered": len(cal["ff_days"]),
                 "fomc_span": _span(cal["fomc_days"])}
    for g, rs in groups.items():
        st = _stats([r["slip_pts"] for r in rs if isinstance(r.get("slip_pts"), (int, float))])
        doc[f"n_{g}"] = len(rs)
        doc[f"median_slip_{g}"] = st["median"]
        doc[f"max_slip_{g}"] = st["max"]
        doc[f"n_slip_{g}"] = st["n"]
    doc["n_measured"] = doc["n_in_window"] + doc["n_out_of_window"]
    return doc


def slip_split(rows: list[dict]) -> dict:
    slip = [r for r in rows if isinstance(r.get("slip_pts"), (int, float))]
    return {"in_window": _stats([r["slip_pts"] for r in slip if r["in_window"] is True]),
            "out_of_window_measured": _stats([r["slip_pts"] for r in slip
                                              if r["in_window"] is False]),
            "untagged_unmeasured": _stats([r["slip_pts"] for r in slip
                                           if r["in_window"] is None]),
            "no_release_found_any_coverage": _stats([r["slip_pts"] for r in slip
                                                     if r["news_window"] is None])}


def write(rows: list[dict], out: Path, summ: dict | None = None,
          summary_path: Path | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, out)
    if summ is not None and summary_path is not None:
        t2 = summary_path.with_suffix(".tmp")
        t2.write_text(json.dumps(summ, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(t2, summary_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--summary", type=Path, default=SUMMARY)
    a = ap.parse_args(argv)
    cal = load_calendar()
    exits = csv_exits(a.csv) if a.csv else ledger_exits()
    rows = enrich(exits, cal)
    summ = summary(rows, cal)
    write(rows, a.out, summ, a.summary)
    print("exit_news_tag:", json.dumps({k: summ[k] for k in sorted(summ) if k != "generated_at"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
