"""ATTENTION SUBSTITUTES -- retail-attention research without Reddit, from lawful keyless doors.

WHY (2026-09-30). Reddit is terms-fenced (libs/data/terms_fence.py): its User Agreement and Data
API terms cover every automated reader, RSS and anonymous JSON included, and require an agreement
for commercial use the desk does not hold. Reddit carried one information class for the desk --
RETAIL ATTENTION to an instrument -- through three readers (side_channels/reddit_miner,
deep_forest_miner's `route: reddit` grounds, and crowding_miner via free_data.reddit_hot). Fencing
them must not lower the desk's attention research volume, so this organ backfills the class from
doors whose terms permit it:

  wikipedia_pageviews  Wikimedia REST pageviews API, keyless. The pageview data is CC0 and the API
                       asks only for an identifying User-Agent, which every request here sends.
  gdelt_doc_timeline   GDELT DOC 2.0 API, keyless; GDELT's data is open for any use, commercial
                       included, with citation (the citation rides on every lake row's source_id).
  google_trends        NOT re-fetched here: `side_channels/google_trends_miner.py` already runs in
                       run_all_miners and its rows reach the compiler; this organ only COUNTS them
                       in the before/after volume so the class is measured whole.

  Considered and NOT added: StockTwits (its Terms s.5 forbid automated extraction without written
  authorization -- fenced in terms_fence.py on the same basis as Reddit), and public Telegram
  channels (deep_forest_miner's `route: telegram` already mines them; nothing is duplicated here).

ONE PASS, inside `--budget-s`:

  1. For every (instrument, door) in ROSTER, fetch the daily series (a bounded window), keep the
     FIRST value seen per day for ever (a later different value is recorded as a revision), and
     time each day's value at the day's END + `LAG_H` hours -- never earlier than the door could
     have published it.
  2. Publish `data/lake/series/attn_<door>__<key>.csv` in the lake's PIT envelope (event_time,
     available_time, value, source_id, vintage_id) -- the frame
     `mt5desk.family_exogenous_conditioner` loads.
  3. Mint `exogenous_conditioner` cells on each mapped instrument ({level_z, delta_z} x
     {1.0, 1.5, 2.0} sd x {+1, -1}), each cell ONCE (never re-charged), up to PER_PASS a pass,
     through `proposer_common.donate`
     -- the stamped, lane-filtered, pre-registered door -- which writes
     `data/intelligence/attention_substitutes/discoveries_*.json` with `tests_run` = cells minted,
     so every one is charged to the trial census. The compiler reads that directory like any seat.
  4. Write `reports/ATTENTION_SUBSTITUTES.json`: per-door status, cells minted, and the attention
     cell VOLUME PER DAY before and after the fence -- Reddit-derived rows per day (from the
     reddit intelligence directory, which stops growing at the fence) beside substitute cells per
     day -- so "volume did not drop" is a measured claim, never an assertion.

An unreachable door is its own named status (NO_DATA / HTTP <code>), never 0 and never a reason to
mint cells on a series that does not exist.

    python desks/mt5/research/attention_substitutes.py --once [--budget-s 240] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402

#: This organ's own artifact (the component registry reads it from here).
REPORT = DESK / "reports" / "ATTENTION_SUBSTITUTES.json"

SEAT = "attention_substitutes"
UNMEASURED = "UNMEASURED"
#: Days of history requested per series on a pass. The z-window of the conditioner is 250 bars
#: of the SERIES' own clock, so a year of dailies is what makes the first cells measurable.
WINDOW_DAYS = 400
#: Hours after a day's end before its value may be used. Wikimedia publishes a day's pageviews
#: within the following day and GDELT's daily counts settle within hours; 24h is the conservative
#: bound for both, and the conditioner holds the series back a further publication day on top.
LAG_H = 24
#: Minimum points before a series may mint cells (the conditioner's own MIN_OBSERVATIONS).
MIN_POINTS = 30
#: New cells donated per pass; a cell already donated is never donated (or charged) again.
PER_PASS = 240
EXO_GRID: dict[str, tuple[Any, ...]] = {"transform": ("level_z", "delta_z"),
                                        "threshold": (1.0, 1.5, 2.0),
                                        "side_when_high": (1, -1)}

UA = "quant-research-desk/1.0 (attention research; keyless REST client)"

#: instrument -> {"wiki": [(project, article)], "gdelt": query}. Articles are the instrument's
#: own page in English plus the edition of the market that trades it most. Symbols are Fusion MT5
#: names; the universe gate drops any the registry does not hold or the two-lane policy refuses.
ROSTER: dict[str, dict[str, Any]] = {
    "XAUUSD": {"wiki": [("en.wikipedia", "Gold_as_an_investment"), ("de.wikipedia", "Gold")],
               "gdelt": '"gold price"'},
    "XAGUSD": {"wiki": [("en.wikipedia", "Silver_as_an_investment")],
               "gdelt": '"silver price"'},
    "XPTUSD": {"wiki": [("en.wikipedia", "Platinum")], "gdelt": '"platinum price"'},
    "XCUUSD": {"wiki": [("en.wikipedia", "Copper")], "gdelt": '"copper price"'},
    "XTIUSD": {"wiki": [("en.wikipedia", "Price_of_oil"),
                        ("en.wikipedia", "West_Texas_Intermediate")],
               "gdelt": '"oil price"'},
    "XBRUSD": {"wiki": [("en.wikipedia", "Brent_Crude")], "gdelt": '"brent crude"'},
    "XNGUSD": {"wiki": [("en.wikipedia", "Natural_gas")], "gdelt": '"natural gas price"'},
    "EURUSD": {"wiki": [("en.wikipedia", "Euro"), ("de.wikipedia", "Euro")],
               "gdelt": '"euro dollar exchange rate"'},
    "USDJPY": {"wiki": [("en.wikipedia", "Japanese_yen"), ("ja.wikipedia", "円_(通貨)")],
               "gdelt": '"yen" "exchange rate"'},
    "GBPUSD": {"wiki": [("en.wikipedia", "Pound_sterling")], "gdelt": '"pound sterling"'},
    "USDCHF": {"wiki": [("en.wikipedia", "Swiss_franc")], "gdelt": '"swiss franc"'},
    "AUDUSD": {"wiki": [("en.wikipedia", "Australian_dollar")], "gdelt": '"australian dollar"'},
    "USDCAD": {"wiki": [("en.wikipedia", "Canadian_dollar")], "gdelt": '"canadian dollar"'},
    "NZDUSD": {"wiki": [("en.wikipedia", "New_Zealand_dollar")], "gdelt": '"new zealand dollar"'},
    "US500": {"wiki": [("en.wikipedia", "S&P_500")], "gdelt": '"S&P 500"'},
    "NAS100": {"wiki": [("en.wikipedia", "Nasdaq-100")], "gdelt": '"nasdaq"'},
    "US30": {"wiki": [("en.wikipedia", "Dow_Jones_Industrial_Average")], "gdelt": '"dow jones"'},
    "GER40": {"wiki": [("de.wikipedia", "DAX")], "gdelt": '"DAX index"'},
    "UK100": {"wiki": [("en.wikipedia", "FTSE_100_Index")], "gdelt": '"FTSE 100"'},
    "JPN225": {"wiki": [("ja.wikipedia", "日経平均株価"), ("en.wikipedia", "Nikkei_225")],
               "gdelt": '"nikkei"'},
    "BTCUSD": {"wiki": [("en.wikipedia", "Bitcoin")], "gdelt": '"bitcoin price"'},
    "ETHUSD": {"wiki": [("en.wikipedia", "Ethereum")], "gdelt": '"ethereum"'},
}

MECHANISM = {
    "wikipedia_pageviews": ("retail attention: an extreme in public lookups of an instrument marks "
                            "a crowd arriving (continuation) or a crowd already in (exhaustion); "
                            "the lawful substitute for the Reddit mention counts"),
    "gdelt_doc_timeline": ("news attention: an extreme in world news volume about an instrument "
                           "precedes a repricing as the marginal trader reacts to the coverage"),
}


class Paths:
    def __init__(self, desk: Path = DESK) -> None:
        self.desk = desk
        self.series = desk / "data" / "lake" / "series"
        self.state = desk / "data" / "attention_substitutes" / "state.json"
        self.obs = desk / "data" / "attention_substitutes" / "obs"
        self.report = desk / "reports" / REPORT.name
        self.universe = desk / "data" / "universe" / "universe.json"
        self.intel = desk / "data" / "intelligence"


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


# ----------------------------------------------------------------------------- doors ------
Fetch = Callable[[str], tuple[int | None, str]]


def _default_fetch(url: str) -> tuple[int | None, str]:
    from libs.data import polite_fetch as pf
    r = pf.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=25.0,
               retries=1, leg=SEAT, max_bytes=4_000_000)
    return r.status, (r.text if r.ok else (r.error or f"HTTP {r.status}"))


def wiki_url(project: str, article: str, start: datetime, end: datetime) -> str:
    return ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"{project}/all-access/user/{urllib.parse.quote(article, safe='')}/daily/"
            f"{start:%Y%m%d}/{end:%Y%m%d}")


def parse_wiki(body: str) -> dict[str, float]:
    """{YYYY-MM-DD: views} from a Wikimedia per-article response."""
    doc = json.loads(body or "{}")
    out: dict[str, float] = {}
    for it in doc.get("items") or []:
        ts = str(it.get("timestamp") or "")
        if len(ts) >= 8:
            out[f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"] = float(it.get("views") or 0)
    return out


def gdelt_url(query: str, days: int) -> str:
    # The DOC API's own limit is three months of timeline; `timelinevolraw` returns raw article
    # counts, summed here to the day.
    span = f"{min(int(days), 90)}d"
    return ("https://api.gdeltproject.org/api/v2/doc/doc?query="
            f"{urllib.parse.quote(query)}&mode=timelinevolraw&format=json&timespan={span}")


def parse_gdelt(body: str) -> dict[str, float]:
    doc = json.loads(body or "{}")
    out: dict[str, float] = {}
    for series in doc.get("timeline") or []:
        for pt in series.get("data") or []:
            d = str(pt.get("date") or "")
            if len(d) >= 8:
                k = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                out[k] = out.get(k, 0.0) + float(pt.get("value") or 0)
    return out


def series_plan() -> list[dict[str, Any]]:
    """Every series this organ reads: id, door, url builder inputs and the instrument it maps."""
    plan: list[dict[str, Any]] = []
    for sym, spec in ROSTER.items():
        for project, article in spec.get("wiki") or []:
            key = f"{project.split('.')[0]}_{article}".replace("/", "_")
            plan.append({"id": f"attn_wiki__{key}", "door": "wikipedia_pageviews",
                         "project": project, "article": article, "symbol": sym})
        if spec.get("gdelt"):
            plan.append({"id": f"attn_gdelt__{sym.lower()}", "door": "gdelt_doc_timeline",
                         "query": spec["gdelt"], "symbol": sym})
    return plan


def fetch_series(row: Mapping[str, Any], now: datetime, fetch: Fetch) -> tuple[dict[str, float],
                                                                               str]:
    """(points, status) for one series. The URL passes the terms fence first."""
    if row["door"] == "wikipedia_pageviews":
        end = now - timedelta(days=1)
        url = wiki_url(str(row["project"]), str(row["article"]),
                       end - timedelta(days=WINDOW_DAYS - 1), end)
        parse = parse_wiki
    else:
        url = gdelt_url(str(row["query"]), WINDOW_DAYS)
        parse = parse_gdelt
    fenced = tf.platform_of_url(url)
    if fenced:                                   # never, by construction -- and pinned by a test
        return {}, f"{tf.PLATFORMS[fenced]['status']}:{fenced}"
    status, body = fetch(url)
    if status is None or not (200 <= int(status) < 300):
        return {}, f"HTTP {status}" if status else f"TRANSPORT: {str(body)[:80]}"
    try:
        pts = parse(body)
    except ValueError as exc:
        return {}, f"PARSE: {type(exc).__name__}"
    # Today's partial day is never kept: it is not a published value yet.
    today = now.strftime("%Y-%m-%d")
    pts = {d: v for d, v in pts.items() if d < today}
    return pts, ("OK" if pts else "NO_DATA")


# ------------------------------------------------------------------------ point-in-time ----
def merge_obs(paths: Paths, sid: str, pts: Mapping[str, float], now: datetime) -> list[dict]:
    """First value seen per day is kept for ever; a different later value is a revision beside
    it. Returns the lake rows, oldest first.

    BACKFILL IS TIMED AT THE PUBLICATION RULE, EVERYTHING AFTER AT max(rule, first seen) -- the
    keyed_sources convention. The series' FIRST successful fetch returns a year of history that
    the door published day by day (Wikimedia's daily pageviews and GDELT's daily counts are
    archival and final once out), so stamping all of it "now" would collapse a year onto one
    instant and leave the conditioner nothing to measure; the rule (day end + LAG_H) is late by
    construction. From the second fetch on, a day is never available before the desk saw it.
    """
    p = paths.obs / f"{sid}.json"
    doc = _read(p, {}) or {}
    first: dict[str, Any] = doc.get("first") or {}
    revisions: list[dict[str, Any]] = doc.get("revisions") or []
    seen = now.isoformat(timespec="seconds")
    backfill = not first
    for d, v in sorted(pts.items()):
        if d not in first:
            first[d] = {"value": v, "first_seen_at": seen, "backfill": backfill}
        elif float(first[d]["value"]) != float(v):
            revisions.append({"day": d, "value": v, "seen_at": seen})
    _atomic(p, {"first": first, "revisions": revisions[-2000:]})
    rows = []
    for d in sorted(first):
        day_end = datetime.fromisoformat(d).replace(tzinfo=UTC) + timedelta(days=1)
        rule = day_end + timedelta(hours=LAG_H)
        avail = (rule if first[d].get("backfill")
                 else max(rule, datetime.fromisoformat(str(first[d]["first_seen_at"]))))
        rows.append({"event_time": day_end.isoformat(timespec="seconds"),
                     "available_time": avail.isoformat(timespec="seconds"),
                     "value": float(first[d]["value"]), "source_id": sid,
                     "vintage_id": f"{sid}:{first[d]['first_seen_at']}"})
    return rows


def write_lake(paths: Paths, sid: str, rows: list[dict]) -> str | None:
    if not rows:
        return None
    import csv
    paths.series.mkdir(parents=True, exist_ok=True)
    target = paths.series / f"{sid}.csv"
    tmp = target.with_suffix(f".tmp{os.getpid()}")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["event_time", "available_time", "value",
                                           "source_id", "vintage_id"])
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, target)
    return target.name


# ------------------------------------------------------------------------------- cells -----
def universe_gate(paths: Paths) -> tuple[Callable[[str], bool] | None, str | None]:
    """The registry AND the two-lane policy, or the named reason. FAILS CLOSED."""
    try:
        from research.universe_policy import may_hypothesise
    except Exception as exc:
        return None, f"BLOCKED_DEPENDENCY:research.universe_policy ({type(exc).__name__})"
    uni = _read(paths.universe, {}) or {}
    if not isinstance(uni, dict) or not uni:
        return None, f"BLOCKED_DEPENDENCY:{paths.universe.name} unreadable"
    return (lambda s: s in uni and bool(may_hypothesise(s))), None


def build_grid(plan: list[dict[str, Any]], lake_points: Mapping[str, int], now: datetime,
               gate: Callable[[str], bool] | None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    from proposer_common import candidate
    cells: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    stamp = now.isoformat(timespec="seconds")
    for row in plan:
        sid, sym = str(row["id"]), str(row["symbol"])
        n = int(lake_points.get(sid) or 0)
        if n < MIN_POINTS:
            skipped[sid] = f"{n} points < {MIN_POINTS}"
            continue
        if gate is None or not gate(sym):
            skipped[sid] = f"{sym}: not a hypothesis-lane instrument in this registry"
            continue
        mech = f"{MECHANISM[row['door']]}; {sid} conditions {sym}"
        for t, thr, side in product(*EXO_GRID.values()):
            c = candidate(SEAT, sym, "exogenous_conditioner",
                          {"source": sid, "signal": "value", "transform": t,
                           "threshold": thr, "side_when_high": side, "lag_hours": 24},
                          mech, f"{sid} ({t} {thr}) -> {sym} [{row['door']}]",
                          {"series": sid, "door": row["door"], "points": n,
                           "substitutes_for": "reddit (terms-fenced 2026-09-30)"})
            c.update({"symbols": [sym], "available_time": stamp, "event_time": stamp,
                      "attention_door": row["door"], "information_class": "retail_attention",
                      "required_data": [f"desks/mt5/data/lake/series/{sid}.csv"],
                      "falsifier": (f"{sid} {t} beyond {thr} sd carries no out-of-sample "
                                    f"information about {sym} H1 returns")})
            cells.append(c)
    return cells, skipped


def cell_key(c: Mapping[str, Any]) -> str:
    p = c.get("params") or {}
    return "|".join(str(x) for x in (c.get("symbol"), c.get("family"), p.get("source"),
                                     p.get("transform"), p.get("threshold"),
                                     p.get("side_when_high")))


def _fresh(cells: list[dict[str, Any]], donated: set[str], n: int) -> list[dict[str, Any]]:
    """Up to `n` cells never donated before. EACH CELL IS DONATED -- AND CHARGED -- ONCE: the
    trial census divides one family-wise error budget across every hypothesis the desk tested,
    so re-donating an identical cell every hour would charge the FX and metals book for trials
    nobody ran. A new series (a door that comes online, a roster row added) mints its cells on
    the next pass."""
    return [c for c in cells if cell_key(c) not in donated][:max(0, n)]


# ---------------------------------------------------------------------------- volume ------
def _day_of_file(p: Path) -> str | None:
    """discoveries_YYYYMMDD_HHMM.json -> YYYY-MM-DD."""
    stem = p.stem
    for part in stem.split("_"):
        if len(part) == 8 and part.isdigit():
            return f"{part[:4]}-{part[4:6]}-{part[6:8]}"
    return None


def _rows_in(p: Path) -> int:
    doc = _read(p)
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, dict):
        for k in ("discoveries", "hypotheses", "candidates", "rows"):
            if isinstance(doc.get(k), list):
                return len(doc[k])
    return 0


def volume_by_day(intel: Path, seat: str, days: int, now: datetime) -> dict[str, Any]:
    """Rows per day donated under `intel/<seat>/discoveries_*.json` over the last `days` days,
    read from the files' own timestamps. UNMEASURED when the directory does not exist."""
    d = intel / seat
    if not d.is_dir():
        return {"status": UNMEASURED, "why": f"{d} does not exist on this host"}
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    per: dict[str, int] = {}
    for p in sorted(d.glob("discoveries_*.json")):
        day = _day_of_file(p)
        if day and day >= cutoff:
            per[day] = per.get(day, 0) + _rows_in(p)
    vals = list(per.values())
    return {"status": "MEASURED", "days_with_rows": len(per), "window_days": days,
            "rows": sum(vals), "per_day_mean_over_window": round(sum(vals) / days, 2),
            "by_day": dict(sorted(per.items())[-days:])}


def attention_volume(paths: Paths, now: datetime) -> dict[str, Any]:
    """BEFORE / AFTER, measured from the donation files: the Reddit directory (the old attention
    donor, frozen at the fence) against this seat and the Google Trends miner."""
    before = volume_by_day(paths.intel, "reddit", 60, now)
    after = volume_by_day(paths.intel, SEAT, 7, now)
    trends = volume_by_day(paths.intel, "google_trends", 7, now)
    out: dict[str, Any] = {"reddit_rows_60d": before, "substitute_cells_7d": after,
                           "google_trends_rows_7d": trends}
    if before.get("status") == "MEASURED" and after.get("status") == "MEASURED":
        b_days = int(before.get("days_with_rows") or 0)
        b = (float(before["rows"]) / b_days) if b_days else None
        a = float(after["per_day_mean_over_window"])
        out["reddit_rows_per_active_day"] = round(b, 2) if b is not None else UNMEASURED
        out["substitute_cells_per_day"] = a
        out["volume_held"] = (UNMEASURED if b is None else bool(a >= b))
    else:
        out["volume_held"] = UNMEASURED
    return out


# ------------------------------------------------------------------------------- pass -----
def run(*, budget_s: float = 240.0, fetch: Fetch | None = None, dry_run: bool = False,
        paths: Paths | None = None, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    paths = paths or Paths()
    now = now or datetime.now(UTC)
    fetch = fetch or _default_fetch
    state = _read(paths.state, {}) or {}
    last: dict[str, str] = state.get("last_fetch") or {}
    plan = series_plan()
    # STALEST FIRST, so a pass cut by the budget still advances the series it has not touched.
    plan_order = sorted(plan, key=lambda r: str(last.get(r["id"]) or ""))
    recs: dict[str, dict[str, Any]] = {}
    lake_points: dict[str, int] = {}
    for row in plan_order:
        sid = str(row["id"])
        if time.monotonic() - t0 > budget_s * 0.7:
            recs[sid] = {"status": "BUDGET_DEFERRED", "door": row["door"]}
            continue
        pts, status = fetch_series(row, now, fetch)
        rec: dict[str, Any] = {"status": status, "door": row["door"], "symbol": row["symbol"],
                               "points_fetched": len(pts)}
        if pts and not dry_run:
            lake_rows = merge_obs(paths, sid, pts, now)
            rec["lake"] = write_lake(paths, sid, lake_rows)
            rec["lake_points"] = len(lake_rows)
            last[sid] = now.isoformat(timespec="seconds")
            state["last_fetch"] = last
            _atomic(paths.state, state)
        recs[sid] = rec
    # A series fetched on an EARLIER pass still mints: read the lake that is on disk.
    for row in plan:
        sid = str(row["id"])
        p = paths.series / f"{sid}.csv"
        if p.exists():
            try:
                with p.open(encoding="utf-8") as fh:
                    lake_points[sid] = max(0, sum(1 for _ in fh) - 1)
            except OSError:
                pass
    gate, gate_why = universe_gate(paths)
    cells, skipped = build_grid(plan, lake_points, now, gate)
    donated_keys = set(state.get("donated") or [])
    take = _fresh(cells, donated_keys, PER_PASS)
    donation: dict[str, Any] = {"donated": 0}
    if take and not dry_run:
        from proposer_common import donate, donation_counts
        path = donate(SEAT, take, len(take))
        donation = {**donation_counts(), "path": str(path) if path else None}
        if path:
            state["donated"] = sorted(donated_keys | {cell_key(c) for c in take})
            _atomic(paths.state, state)
    by_door: dict[str, int] = {}
    for r in recs.values():
        k = f"{r['door']}:{str(r['status']).split(':', 1)[0]}"
        by_door[k] = by_door.get(k, 0) + 1
    doc = {"generated_at": now.isoformat(timespec="seconds"),
           "writer": "desks/mt5/research/attention_substitutes.py",
           "status": "DRY_RUN" if dry_run else "RAN",
           "fenced_platforms": tf.registry_rows(),
           "series": recs, "status_counts": by_door,
           "cells": {"grid": len(cells), "built": len(take),
                     "donated_ever": len(state.get("donated") or []),
                     "minted": int(donation.get("donated") or 0),
                     "trials_charged": 0 if dry_run else int(donation.get("donated") or 0),
                     "universe_gate": gate_why or "OK", "skipped": skipped,
                     "donation": donation},
           "attention_volume": attention_volume(paths, now),
           "seconds": round(time.monotonic() - t0, 1),
           "rule": ("an unreachable door is a named status, never 0; every minted cell is "
                    "charged through tests_run on its donation file")}
    if not dry_run:
        _atomic(paths.report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"attention_substitutes: {doc['status_counts']}; grid {doc['cells']['grid']}, "
          f"minted {doc['cells']['minted']}; volume_held="
          f"{doc['attention_volume'].get('volume_held')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
