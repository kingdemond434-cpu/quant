"""ALT_DATA_YIELD.json -- what the alt-data miners actually reach, per platform, vector and leg.

A LIBRARY, NOT A LEG OF ITS OWN (no entry point, on purpose: a second clock would be a
shadow). The artifact is rewritten at the end of every pass of the organs that move
it -- `deep_forest_miner.run` (the hourly `deep_forest` leg and, through `forest_runner`'s
practitioner role, every `forest_*` leg) and `regional_survivor_hunters.run_and_save` (the
seed-miner clock). This file only COMPOSES what those organs already record:

* per PLATFORM (the regional copy/PAMM grounds): `data/intelligence/coverage_registry.json`
  -- attempts, successes, rows, last error;
* per VECTOR (the 502 deep-forest grounds): `data/deep_forest_frontier.json` (outcome,
  attempts, findings, blocker) joined with `data/deep_forest_vector_stats.json` (successes,
  rows, datasets, last error, counted per checkpoint since the counter landed);
* per LEG fetch rate: `data/alt_fetch_runs.jsonl` (one line per miner pass: fetches, ok,
  seconds) and, for the `forest_*` legs, the wall/CPU seconds `compute_ledger.jsonl` holds;
* the week: vectors attempted in the last seven days against vectors named;
* per REGION (2026-11-03): named / attempted / YIELDED / EMPTY / BLOCKED, the discovery backend
  that yielded (`research/discovery_backends.py`), the MT5 hypothesis-lane symbols the registry
  lists there, and rule 23's RED flag for a region at 0 YIELDED for seven days on its clock.

UNMEASURED IS NEVER ZERO (L1.28a). A counter that did not exist when a platform was last worked
reads "UNMEASURED" with the reason, never 0; a leg with no fetch-rate line reads UNMEASURED. A
vector that was never attempted has attempts 0 -- that zero IS measured, by the frontier.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ARTIFACT_NAME = "ALT_DATA_YIELD.json"
OUT = DESK / "reports" / ARTIFACT_NAME
COVERAGE = DESK / "data" / "intelligence" / "coverage_registry.json"
FRONTIER = DESK / "data" / "deep_forest_frontier.json"
VECTOR_STATS = DESK / "data" / "deep_forest_vector_stats.json"
RUNS = DESK / "data" / "alt_fetch_runs.jsonl"
COMPUTE_LEDGER = DESK / "data" / "compute_ledger.jsonl"
#: Per region: since when it has yielded nothing, and when it last yielded. Box-local state.
REGION_CLOCK = DESK / "data" / "region_yield_clock.json"
#: Rule 23 (REGION_GAP_RANK_2026-11-03): a region at 0 YIELDED for this long turns RED.
RED_AFTER = timedelta(days=7)
UNMEASURED = "UNMEASURED"
WEEK = timedelta(days=7)
DAY = timedelta(days=1)
#: The fetching legs this artifact accounts for. forest_* are added from the federation.
FETCH_LEGS: tuple[str, ...] = ("regional_survivor_hunters", "deep_forest_miner")


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(p: Path, max_bytes: int = 32 * 1024 * 1024) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            for raw in fh:
                with contextlib.suppress(ValueError):
                    row = json.loads(raw.decode("utf-8", errors="replace"))
                    if isinstance(row, dict):
                        out.append(row)
    except OSError:
        return out
    return out


def _ts(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def forest_legs() -> list[str]:
    try:
        from libs.research import forests as F
        return sorted(f"forest_{fid}" for fid in F.FORESTS)
    except Exception:
        return []


# --------------------------------------------------------------------------- platforms
def platforms(cov: Any) -> dict[str, Any]:
    if not isinstance(cov, dict) or not isinstance(cov.get("platforms"), dict):
        return {"status": UNMEASURED, "why": f"{COVERAGE.name} absent or unreadable here"}
    rows: dict[str, Any] = {}
    for name, e in sorted(cov["platforms"].items()):
        e = e if isinstance(e, dict) else {}
        counted = "successes" in e
        why_unm = "counter landed 2026-09-30; this platform has not been worked since"
        last_err = e.get("last_error")
        if last_err is None:
            st = str(e.get("last_state") or "")
            last_err = "" if st == "ok" else (st or UNMEASURED)
        rows[name] = {
            "region": e.get("region"), "lang": e.get("lang"),
            "attempts": int(e.get("attempts") or 0),
            "successes": int(e.get("successes") or 0) if counted else UNMEASURED,
            "rows": int(e.get("rows_total") or 0) if counted else UNMEASURED,
            "best_rows": int(e.get("best_rows") or 0),
            "last_rows": e.get("last_rows", UNMEASURED),
            "last_state": e.get("last_state") or UNMEASURED,
            "last_error": last_err,
            "last_attempt": e.get("last_attempt") or UNMEASURED,
            "last_success": e.get("last_success") or UNMEASURED,
            "last_via": e.get("last_via") or UNMEASURED,
            "counted_since": e.get("counted_since") or UNMEASURED,
            **({} if counted else {"why_unmeasured": why_unm}),
        }
    yielding = [n for n, r in rows.items()
                if r["best_rows"] > 0 or (isinstance(r["successes"], int) and r["successes"] > 0)]
    return {"n": len(rows), "yielding": len(yielding),
            "never_yielded": sorted(set(rows) - set(yielding)), "rows_by_platform": rows}


# --------------------------------------------------------------------------- vectors
def vectors(frontier: Any, stats: Any, now: datetime) -> dict[str, Any]:
    vec = frontier.get("vectors") if isinstance(frontier, dict) else None
    if not isinstance(vec, dict):
        return {"status": UNMEASURED, "why": f"{FRONTIER.name} absent or unreadable here"}
    st = (stats or {}).get("vectors") if isinstance(stats, dict) else None
    st = st if isinstance(st, dict) else {}
    rows: dict[str, Any] = {}
    outcomes: dict[str, int] = {}
    week = never = 0
    for name, v in sorted(vec.items()):
        v = v if isinstance(v, dict) else {}
        s = st.get(name) if isinstance(st.get(name), dict) else None
        attempts = int(v.get("attempts") or 0)
        outcome = str(v.get("outcome") or "NAMED_ONLY")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        la = _ts(v.get("last_attempt"))
        if attempts == 0:
            never += 1
        if la is not None and now - la <= WEEK:
            week += 1
        if s is not None:
            successes: Any = int(s.get("successes") or 0)
            rows_n: Any = int(s.get("rows") or 0)
        elif attempts == 0:
            successes, rows_n = 0, 0                 # never attempted: a MEASURED zero
        else:
            successes, rows_n = UNMEASURED, UNMEASURED
        rows[name] = {
            "outcome": outcome, "attempts": attempts, "successes": successes,
            "rows": rows_n, "findings_total": int(v.get("findings") or 0),
            "datasets": int(s.get("datasets") or 0) if s is not None else (
                0 if attempts == 0 else UNMEASURED),
            "last_error": (s or {}).get("last_error") or v.get("blocker") or "",
            "last_attempt": v.get("last_attempt") or "",
            "language": v.get("language") or "", "region": v.get("region") or "",
        }
    named = len(rows)
    return {"named": named, "by_outcome": outcomes, "never_attempted": never,
            "attempted_this_week": week,
            "attempted_this_week_share": round(week / named, 4) if named else UNMEASURED,
            "rows_by_vector": rows}


# --------------------------------------------------------------------------- regions
def _clock(p: Path) -> Any:
    """The region clock: its JSON, None when the file does not exist, or a str saying why a file
    that exists could not be used. Absent and corrupt are different answers."""
    try:
        text = p.read_text("utf-8-sig")
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"{p.name} exists but cannot be read ({type(exc).__name__})"
    try:
        doc = json.loads(text)
    except ValueError as exc:
        return f"{p.name} does not parse ({type(exc).__name__})"
    return doc if isinstance(doc, dict) else f"{p.name} is not a JSON object"


def _registry_regions() -> dict[str, int] | str:
    """{region: hypothesis-lane MT5 symbols}, from the broker registry; a string when the
    registry cannot be read (UNMEASURED, never zero)."""
    try:
        from research import universe_policy as up
        got = up.hypothesis_regions()
    except Exception as exc:
        return f"{UNMEASURED}: {type(exc).__name__}"
    if not got:
        return f"{UNMEASURED}: the universe registry is absent or empty here"
    return {r: len(v) for r, v in got.items()}


def regions(frontier: Any, stats: Any, clock: Any, now: datetime,
            symbols_by_region: dict[str, int] | str | None = None) -> dict[str, Any]:
    """PER REGION, every pass: named / attempted (this week) / YIELDED / EMPTY / BLOCKED, the
    discovery backends that yielded, the MT5 symbols the registry lists there, and the rule-23
    flag: RED when a region has been at 0 YIELDED for seven days on its clock.

    The clock (`REGION_CLOCK`) starts a zero streak at the earliest `counted_since` of the
    region's vectors when the counters say it never yielded -- evidence, not the day this code
    landed -- and otherwise at the first pass that saw it at zero. An unreadable frontier is
    UNMEASURED for every region, never zero."""
    vec = frontier.get("vectors") if isinstance(frontier, dict) else None
    if not isinstance(vec, dict):
        return {"status": UNMEASURED, "why": f"{FRONTIER.name} absent or unreadable here"}
    st = (stats or {}).get("vectors") if isinstance(stats, dict) else None
    st = st if isinstance(st, dict) else {}
    # THE CLOCK IS GUARDED LIKE THE FRONTIER. `clock` is the parsed file, None when the file is
    # absent (a first pass: every streak starts on evidence), or a str naming why a file that
    # EXISTS could not be read -- then no streak is restarted, every zero-yield region reads
    # UNMEASURED, and `region_clock_doc` refuses to write over the file.
    clock_bad = clock if isinstance(clock, str) else ""
    clk = clock.get("regions") if isinstance(clock, dict) else None
    if isinstance(clock, dict) and not isinstance(clk, dict):
        clock_bad = "the region clock has no `regions` table"
    clk = clk if isinstance(clk, dict) else {}
    rows: dict[str, dict[str, Any]] = {}
    first_counted: dict[str, datetime] = {}
    last_success: dict[str, datetime] = {}
    for name, v in vec.items():
        v = v if isinstance(v, dict) else {}
        s = st.get(name) if isinstance(st.get(name), dict) else {}
        region = str(v.get("region") or s.get("region") or "unknown") or "unknown"
        r = rows.setdefault(region, {"named": 0, "attempted_this_week": 0, "YIELDED": 0,
                                     "EMPTY": 0, "BLOCKED": 0, "NAMED_ONLY": 0,
                                     "discovery": {}, "yielded_via": {}})
        r["named"] += 1
        outcome = str(v.get("outcome") or "NAMED_ONLY")
        key = outcome if outcome in ("YIELDED", "EMPTY", "BLOCKED") else "NAMED_ONLY"
        r[key] += 1
        la = _ts(v.get("last_attempt"))
        if la is not None and now - la <= WEEK:
            r["attempted_this_week"] += 1
        ds = s.get("discovery_status")
        if ds:
            r["discovery"][str(ds)] = r["discovery"].get(str(ds), 0) + 1
        for b in s.get("yielded_via") or []:
            r["yielded_via"][str(b)] = r["yielded_via"].get(str(b), 0) + 1
        cs = _ts(s.get("counted_since"))
        if cs is not None and (region not in first_counted or cs < first_counted[region]):
            first_counted[region] = cs
        ls = _ts(s.get("last_success"))
        if ls is not None and (region not in last_success or ls > last_success[region]):
            last_success[region] = ls
    out: dict[str, Any] = {}
    red: list[str] = []
    for region, r in sorted(rows.items()):
        prev = clk.get(region) if isinstance(clk.get(region), dict) else {}
        last_y = last_success.get(region) or _ts(prev.get("last_yielded"))
        if r["YIELDED"] > 0:
            zero_since = None
            last_y = last_y or now
        else:
            # A streak starts where it already started, else at the LAST YIELD (a region GREEN
            # yesterday is one day at zero, not "since its counters began"), and only for a
            # region that never yielded at the earliest counter -- evidence, not code age.
            zero_since = (_ts(prev.get("zero_since")) or last_y
                          or first_counted.get(region) or now)
        days = round((now - zero_since).total_seconds() / 86400, 2) if zero_since else 0.0
        if r["YIELDED"] > 0:
            flag = "GREEN"
        elif clock_bad:
            flag, zero_since, days = UNMEASURED, None, UNMEASURED
        elif zero_since is not None and now - zero_since >= RED_AFTER:
            flag = "RED"
            red.append(region)
        else:
            flag = "WATCH"
        syms: Any = (symbols_by_region.get(region, 0) if isinstance(symbols_by_region, dict)
                     else (symbols_by_region or UNMEASURED))
        out[region] = {**r, "attempted": r["attempted_this_week"],
                       "yield_share": round(r["YIELDED"] / r["named"], 4) if r["named"] else 0.0,
                       "backend_that_yielded": (max(r["yielded_via"], key=r["yielded_via"].get)
                                                if r["yielded_via"] else None),
                       "mt5_hypothesis_symbols": syms,
                       "zero_since": zero_since.isoformat(timespec="seconds") if zero_since
                       else None,
                       "last_yielded": last_y.isoformat(timespec="seconds") if last_y else None,
                       "days_at_zero": days, "flag": flag}
    return {"n": len(out), "red": red if not clock_bad else UNMEASURED,
            "clock": f"{UNMEASURED}: {clock_bad}" if clock_bad else "OK",
            "green": [k for k, v in out.items() if v["flag"] == "GREEN"],
            "rule": ("rule 23: RED when a region's vectors stay at 0 YIELDED for 7 days on the "
                     "region clock; WATCH while the streak is younger; UNMEASURED when the "
                     "frontier cannot be read"),
            "by_region": out}


def region_clock_doc(section: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    """What the clock file holds after this pass, or None when the section is UNMEASURED (an
    unreadable frontier must never restart or erase a streak)."""
    rows = section.get("by_region") if isinstance(section, dict) else None
    if not isinstance(rows, dict) or str(section.get("clock", "OK")) != "OK":
        return None
    return {"updated": now.isoformat(timespec="seconds"),
            "regions": {k: {"zero_since": v.get("zero_since"),
                            "last_yielded": v.get("last_yielded")} for k, v in rows.items()}}


# --------------------------------------------------------------------------- legs
def legs(runs: Iterable[dict[str, Any]], ledger: Iterable[dict[str, Any]],
         now: datetime) -> dict[str, Any]:
    agg: dict[str, dict[str, Any]] = {}
    for r in runs:
        at = _ts(r.get("at"))
        if at is None or now - at > WEEK:
            continue
        leg = str(r.get("leg") or "?")
        a = agg.setdefault(leg, {"runs": 0, "fetches": 0, "ok": 0, "http_errors": 0,
                                 "transport_errors": 0, "seconds": 0.0, "rows": 0,
                                 "last_run": ""})
        a["runs"] += 1
        for k in ("fetches", "ok", "http_errors", "transport_errors"):
            a[k] += int(r.get(k) or 0)
        a["seconds"] += float(r.get("seconds") or 0.0)
        a["rows"] += int(r.get("rows") or r.get("claims_new") or 0) + int(
            r.get("datasets_new") or 0)
        a["last_run"] = max(a["last_run"], str(r.get("at") or ""))
    wall: dict[str, dict[str, float]] = {}
    for row in ledger:
        name = str(row.get("run") or "")
        at = _ts(row.get("at"))
        if at is None or now - at > DAY:
            continue
        w = wall.setdefault(name, {"wall_s": 0.0, "cpu_s": 0.0, "runs": 0})
        w["wall_s"] += float(row.get("wall_s") or 0.0)
        w["cpu_s"] += float(row.get("cpu_s") or 0.0)
        w["runs"] += 1
    out: dict[str, Any] = {}
    for leg in (*FETCH_LEGS, *forest_legs(), *sorted(set(agg) - set(FETCH_LEGS))):
        if leg in out:
            continue
        a = agg.get(leg)
        w = wall.get(leg) or wall.get(leg.replace("_miner", ""))
        row: dict[str, Any] = {}
        if a:
            row.update({k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()})
            row["fetches_per_s"] = (round(a["fetches"] / a["seconds"], 4)
                                    if a["seconds"] > 0 else UNMEASURED)
            row["success_rate"] = (round(a["ok"] / a["fetches"], 4)
                                   if a["fetches"] else UNMEASURED)
        else:
            row.update({"runs": UNMEASURED, "fetches": UNMEASURED,
                        "fetches_per_s": UNMEASURED,
                        "why": "no fetch-rate line in the last 7 days for this leg"})
        if w:
            row["wall_s_24h"] = round(w["wall_s"], 1)
            row["cpu_s_24h"] = (round(w["cpu_s"], 1) if w["cpu_s"] > 0 else UNMEASURED)
            if w["cpu_s"] <= 0:
                row["cpu_why"] = ("child CPU was not counted on Windows before 2026-09-30 "
                                  "(os.times() reports children as 0 there); a zero here was "
                                  "never a measurement of idleness")
        else:
            row["wall_s_24h"] = UNMEASURED
        out[leg] = row
    return out


# --------------------------------------------------------------------------- the artifact
def build(*, coverage: Path | None = None, frontier: Path | None = None,
          vector_stats: Path | None = None, runs: Path | None = None,
          compute_ledger: Path | None = None, region_clock: Path | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    coverage = coverage or COVERAGE
    frontier = frontier or FRONTIER
    vector_stats = vector_stats or VECTOR_STATS
    runs = runs or RUNS
    compute_ledger = compute_ledger or COMPUTE_LEDGER
    # The clock lives beside the run ledger (both in data/ on the box), so a caller -- or a test
    # -- that points its ledgers elsewhere never writes the desk's own clock.
    region_clock = region_clock or runs.with_name(REGION_CLOCK.name)
    plat = platforms(_json(coverage))
    front, vstats = _json(frontier), _json(vector_stats)
    vec = vectors(front, vstats, now)
    reg = regions(front, vstats, _clock(region_clock), now, _registry_regions())
    leg = legs(_jsonl(runs), _jsonl(compute_ledger, max_bytes=8 * 1024 * 1024), now)
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "summary": {
            "platforms": plat.get("n", UNMEASURED),
            "platforms_yielding": plat.get("yielding", UNMEASURED),
            "vectors_named": vec.get("named", UNMEASURED),
            "vectors_attempted_this_week": vec.get("attempted_this_week", UNMEASURED),
            "vectors_never_attempted": vec.get("never_attempted", UNMEASURED),
            "vectors_by_outcome": vec.get("by_outcome", UNMEASURED),
            "regions": reg.get("n", UNMEASURED),
            "regions_red": reg.get("red", UNMEASURED),
        },
        "platforms": plat, "vectors": vec, "regions": reg, "legs": leg,
        "sources": {"platforms": str(coverage), "vectors": [str(frontier), str(vector_stats)],
                    "regions": [str(frontier), str(vector_stats), str(region_clock)],
                    "legs": [str(runs), str(compute_ledger)]},
        "rule": ("UNMEASURED is never written as 0; a vector never attempted has attempts 0, "
                 "which the frontier measures. Rewritten by every pass of deep_forest_miner "
                 "(deep_forest and forest_* legs) and regional_survivor_hunters."),
    }


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            with contextlib.suppress(OSError):
                os.chmod(path, 0o666)
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(text, "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def write(out: Path | None = None, **paths: Any) -> dict[str, Any]:
    """Build and write the artifact. `paths` overrides any input (tests point them at tmp)."""
    p = {k: Path(v) for k, v in paths.items() if v is not None}
    doc = build(**p)
    _atomic(out or OUT, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    clock = region_clock_doc(doc.get("regions") or {}, _ts(doc["generated_utc"]) or
                             datetime.now(tz=UTC))
    if clock is not None:
        with contextlib.suppress(OSError):
            _atomic(Path(doc["sources"]["regions"][2]), json.dumps(clock, indent=1))
    return doc
