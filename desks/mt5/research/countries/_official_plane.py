"""A COUNTRY'S OFFICIAL PLANE, READ FROM THE ALT-DATA FACTORY'S OWN STORES -- one report per pack.

WHY THIS EXISTS (asia directive PARTS X / XI, audit rows 31-34, 2026-10-06). The Korea department
declared sixteen miners in modules that were never committed, so its official-data lane -- the
part the directive names first (BOK ECOS, the customs 10/20-day prints) -- ran nowhere in this
repository, and Hong Kong had no department miner at all. The series themselves are fetched,
parsed, PIT-stamped, vintaged and turned into cells by ONE organ, `research.alt_proxies` (its
hourly leg): this module fetches nothing and parses nothing. It reads that organ's vintage stores
for one region and publishes, per series, the five alpha objects (level, change, acceleration,
surprise, revision) with their s2.5 clock names, the cells the organ judged for those series
through its door (`gain_tests` -> `proposer_common.donate`, every look charged), the refused
hosts with their verbatim terms, and the region's EVENT OBJECTS (the Korea customs 10-/20-day
prints, the Hong Kong Convertibility Undertaking FX legs) with lifecycle states.

THE FOUR STATES A LANE CAN BE IN, each named, none a zero: PARSED (points exist), and otherwise the
organ's own status -- BLOCKED_ON_KEY:<ENV>, UNCONFIGURED:<ENV>, BLOCKED_ON_TERMS:<terms> -- or
UNMEASURED_LIVE_YIELD when the box has not run the fetch yet.

ZERO CAPITAL AUTHORITY. The report sizes nothing; its consumers are the department loop
(`global_research_os` via each pack's `miners.py`) and the allocation-intel artifact the organ
already writes.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[2]
REPORTS = DESK / "reports"
UNMEASURED = "UNMEASURED"
OWNER = "research/alt_proxies.py (hourly_cycle leg alt_proxies)"
#: Fields of the latest point carried into the report (the s2.5 names beside the desk's own).
LATEST_FIELDS = ("d", "value", "delta", "acceleration", "pace", "expected_value", "raw_surprise",
                 "surprise_z", "percentile", "revision_delta", "knowable_at", "received_at",
                 "pit_quality")


def report_path(code: str) -> Path:
    return REPORTS / f"{code.upper()}_OFFICIAL_PLANE.json"


def alt() -> Any:
    """The alt-data factory module, under whichever root the caller's path resolves."""
    try:
        from research import alt_proxies
    except ImportError:                                        # pragma: no cover - path variant
        import alt_proxies  # type: ignore[import-not-found,no-redef]
    return alt_proxies


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def lane(A: Any, src: Any, paths: Any, gains: dict[str, Any]
         ) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """One source's lane: status, per-series alpha objects, and the cells judged on it."""
    status = A.status_of(src)
    store = _read(paths.obs_dir / f"{src.id}.json")
    pts: dict[str, list[dict[str, Any]]] = (A.build_points(src, store)
                                            if store and src.terms == "confirmed" else {})
    # Revisions are their own vintages, each knowable only from the instant it was first seen
    # (alt_proxies.revision_points), never folded back onto the first print.
    revs: dict[str, list[dict[str, Any]]] = (A.revision_points(src, store)
                                             if pts else {})
    series: dict[str, Any] = {}
    for name, rows in sorted(pts.items()):
        if not rows:
            continue
        last = rows[-1]
        rv = revs.get(name) or []
        series[name] = {"n": len(rows), "first": rows[0]["d"], "last": last["d"],
                        "n_revised": len({r["d"] for r in rv}), "n_revision_vintages": len(rv),
                        "signal": name in src.signal_series,
                        "latest": {k: last.get(k) for k in LATEST_FIELDS},
                        "latest_revision": ({k: rv[-1].get(k) for k in (
                            "d", "value", "revision_delta", "knowable_at", "vintage_n",
                            "revision_of")} if rv else None)}
    cell_keys = [k for k in gains if k.startswith(f"{src.id}|")]
    verdicts = Counter(str(gains[k].get("verdict")) for k in cell_keys)
    mapped = sorted({sym for s in src.signal_series for sym in src.instruments_for(s)})
    unmeasured: list[dict[str, Any]] = []
    if not series:
        unmeasured.append({"what": src.id, "verdict": UNMEASURED,
                           "why": (f"{status}: no parsed point in {OWNER}'s store on this host"
                                   if store or status != "UNMEASURED_LIVE_YIELD" else
                                   f"{status}: the box has not run the fetch yet")})
    row = {"dataset": src.id, "source": src.name, "status": "PARSED" if series else status,
           "organ_status": status, "terms": src.terms, "cadence": src.cadence,
           "key_env": src.key_env, "licence": src.licence, "url": src.url.split("?")[0],
           "acquisition_owner": OWNER, "series": series,
           "stored": len(series), "vintages": sum(int(v["n"]) for v in series.values()),
           "signal_series": list(src.signal_series), "mapped_instruments": mapped,
           "minting_instruments": [s for s in mapped if A.may_mint(s)],
           "cells": {"tested": sum(verdicts.values()), "verdicts": dict(verdicts),
                     "door": "alt_proxies.gain_tests -> direct_cells -> proposer_common.donate "
                             "(every look charged as a trial; PASS only is donated)"},
           "uses": ["direct_cells", "indirect_cells (params.conditioner)", "allocation_intel"],
           "unmeasured": unmeasured}
    if getattr(src, "data_source", ""):
        row["data_source"] = src.data_source
    # A fenced lane's lawful stand-in and its #152 verdict (COVERED only when measured).
    cands = (getattr(A, "SUBSTITUTE_CANDIDATES", {}) or {}).get(src.id) or {}
    if cands:
        row["substitute_candidates"] = [A.substitute_check(src.id, x) for x in cands]
    return row, pts


def refused_lanes(A: Any, ids: Iterable[str]) -> list[dict[str, Any]]:
    out = []
    for sid in ids:
        meta = dict(A.KR_HK_REFUSED.get(sid) or {})
        ev = dict(A.KR_HK_TERMS_EVIDENCE.get(sid) or {})
        out.append({"dataset": sid, "status": meta.get("status", "BLOCKED_ON_TERMS:refused"),
                    "terms": "refused", "stored": 0, "vintages": 0,
                    "would_carry": meta.get("would_carry", []),
                    "nearest_lawful": meta.get("nearest_lawful", []),
                    "why_not_a_substitute": meta.get("why_not_a_substitute", ""),
                    "terms_url": ev.get("terms_url"), "terms_quote": ev.get("terms_quote"),
                    "checked_at": ev.get("checked_at"),
                    "unmeasured": [{"what": sid, "verdict": UNMEASURED,
                                    "why": "BLOCKED_ON_TERMS:refused -- the publisher's terms "
                                           "refuse commercial use or systematic retrieval, so "
                                           "no fetcher is built (fail closed)"}]})
    return out


EventFn = Callable[[dict[str, dict[str, list[dict[str, Any]]]], datetime], list[dict[str, Any]]]


def run(*, code: str, region: str, refused: Iterable[str] = (), events: EventFn | None = None,
        budget_s: float = 300.0, no_fetch: bool = True, dry_run: bool = False,
        registry: Any = None, report_default: Path | None = None, paths: Any = None,
        now: datetime | None = None) -> dict[str, Any]:
    """Measure the region's lanes from the factory's stores; write `<CODE>_OFFICIAL_PLANE.json`."""
    del budget_s, registry
    A = alt()
    paths = paths or A.DEFAULT_PATHS
    now = now or datetime.now(UTC)
    rep = _read(paths.report)
    gains = rep.get("gain_tests") if isinstance(rep.get("gain_tests"), dict) else {}
    lanes: list[dict[str, Any]] = []
    points: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for src in A.SOURCES:
        if str(src.region).upper() != region.upper():
            continue
        row, pts = lane(A, src, paths, gains or {})
        lanes.append(row)
        if pts:
            points[src.id] = pts
    lanes.extend(refused_lanes(A, refused))
    ev = events(points, now) if events is not None else []
    doc = {"at": now.isoformat(timespec="seconds"), "country": code, "region": region,
           "acquisition_owner": OWNER, "no_fetch_is_owned": True,
           "fetch_requested_here": not no_fetch,
           "factory_report_at": rep.get("at") or UNMEASURED,
           "lanes": lanes, "events": ev,
           "declared": len(lanes), "parsed": sum(1 for r in lanes if r["status"] == "PARSED"),
           "blocked": Counter(str(r["status"]).split(":")[0] for r in lanes
                              if r["status"] != "PARSED"),
           "cells_tested": sum(int((r.get("cells") or {}).get("tested") or 0) for r in lanes),
           "unresolved": sum(1 for r in lanes if r.get("unmeasured")),
           "live_yield": ("UNMEASURED until the trading box runs alt_proxies: the authoring "
                          "container cannot reach these hosts"),
           "rule": ("a lane is PARSED only when the factory holds PIT points for it; every other "
                    "state is named, and nothing here has capital authority")}
    if not dry_run:
        target = report_default or report_path(code)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
        tmp.replace(target)
    return doc


def scheduled_after(now: datetime, days_of_month: tuple[int, ...], hour_utc: int = 0
                    ) -> list[datetime]:
    """The next release instants on the given days of the month (rolled past weekends)."""
    out: list[datetime] = []
    y, m = now.year, now.month
    for _ in range(3):
        for dom in days_of_month:
            t = datetime(y, m, dom, hour_utc, tzinfo=UTC)
            while t.weekday() >= 5:
                t += timedelta(days=1)
            if t > now:
                out.append(t)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return sorted(out)[:len(days_of_month)]


def released_events(pts: list[dict[str, Any]], *, event: str, period_filter: Callable[[date], bool]
                    | None = None, extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """RELEASED event objects from one series' PIT points, s2.5-named."""
    out = []
    for p in pts:
        d = date.fromisoformat(str(p["d"])[:10])
        if period_filter is not None and not period_filter(d):
            continue
        out.append({"event": event, "lifecycle": "RELEASED", "event_time": p["d"],
                    "knowable_at": p.get("knowable_at"), "received_at": p.get("received_at"),
                    "value": p.get("value"), "expected_value": p.get("expected_value"),
                    "raw_surprise": p.get("raw_surprise"), "surprise_z": p.get("surprise_z"),
                    "revision_delta": p.get("revision_delta"), **(extra or {})})
    return out


__all__ = ["OWNER", "alt", "lane", "refused_lanes", "released_events", "report_path", "run",
           "scheduled_after"]
