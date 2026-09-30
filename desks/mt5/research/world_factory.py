#!/usr/bin/env python3
"""THE WORLD FACTORY -- one always-on account of every organ that turns the world into cells.

THE PRINCIPAL'S ASK (2026-09-30). "A global media 24/7 miner or factory section ... for maximum
data and news and macro and datasets and maximum hypothesis and cell mining for the gauntlet."

WHAT THE AUDIT FOUND (reports/global_media_factory_audit_2026-09-30.md). The desk does not lack
miners; it has more than forty of them. What it lacked was ONE place that says, per source and per
hour, how much of the world each organ fetched, how many hypotheses that minted, how many cells it
donated and how many reached the docket -- and it had one real hole under that: the twenty-five
media / news / macro / earnings / sentiment miners of `side_channels/run_all_miners.py` ran on ONE
clock only, the VPS's daily `full-pipeline.timer` (06:00), and since the VPS branch became an
orphan (2026-09-11) nothing it wrote reaches the trading box's compiler. On the box that trades,
those twenty-five were on no clock at all.

TWO MODES, TWO LEGS, ONE FILE.

  --mine    (leg `world_media_miners`, intel department). ORCHESTRATES the units in
            `data/world_factory_sources.json:media_units` -- the run_all_miners roster plus the
            seed-miner sweep -- least-recently-run first, each in its own subprocess under its own
            timeout, until the pass budget is spent. Nothing is re-implemented: each unit is the
            existing miner's own `run_and_save`, writing its own
            `data/intelligence/<seat>/discoveries_*.json`, which `miner_candidate_compiler`
            already reads. A cursor makes a truncated pass resume where it stopped, so every unit
            is reached within a few hours even when the pass is cut short; the ledger
            `data/world_factory_runs.jsonl` records every unit run with its rows and status.

  --measure (leg `world_factory`, core). MEASURES every source in the roster and writes
            `reports/WORLD_FACTORY.json`: per source -- the clock and whether it ran (compute
            ledger), items fetched, hypotheses minted (rows in its seat's discovery files),
            cells donated (the donation contract's `counts.donated` plus the compiler's
            executable candidates), cells reaching the docket (the canonical registry's
            candidates by generator, which `libs.moat.docket_feed` carries into the docket) and
            its region / language coverage. The regional forests are EXPANDED from
            `libs.research.forests.FORESTS` and their coverage is MEASURED against the grounds
            file, so a country a forest declares and no ground serves is a named hole.

UNMEASURED IS NEVER ZERO (L1.28a). A counter that cannot be read says UNMEASURED with the reason;
a zero means the artifact was read and it said zero. Nothing here sizes, vetoes, caps or shrinks:
this organ adds clocks and measurements, never a gate (GROWTH_GOVERNANCE).

    python research/world_factory.py --measure
    python research/world_factory.py --mine --budget-s 1400
    python research/world_factory.py --measure --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
WINDOW_H = 24
ROSTER = DESK / "data" / "world_factory_sources.json"
REPORT = DESK / "reports" / "WORLD_FACTORY.json"
CURSOR = DESK / "data" / "world_factory_cursor.json"
RUNS = DESK / "data" / "world_factory_runs.jsonl"
COMPUTE_LEDGER = DESK / "data" / "compute_ledger.jsonl"
FETCH_RUNS = DESK / "data" / "alt_fetch_runs.jsonl"
COMPILED = DESK / "data" / "hypotheses" / "miner_candidates.json"
GROUNDS = DESK / "data" / "deep_forest_sources.json"
REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
ALT_SOURCES = DESK / "data" / "alt_dataset_sources.json"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
ALT_PLATFORMS = DESK / "data" / "intelligence" / "coverage_registry.json"
INTEL_ROOTS: tuple[Path, ...] = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
SIDE_CHANNELS = DESK / "side_channels"
#: The newest bytes of an append-only ledger worth reading for a 24-hour window. The compute
#: ledger passed 90k rows in September; a day of it is a few MB.
TAIL_BYTES = 48 * 1024 * 1024
#: A discovery file larger than this is counted as a file with UNMEASURED rows rather than parsed.
MAX_PARSE_BYTES = 64 * 1024 * 1024
#: Seconds kept back from the mining budget so the pass can write its ledger and exit cleanly.
RESERVE_S = 30.0
ROW_KEYS = ("discoveries", "rows", "items", "hypotheses", "candidates", "findings", "claims")


# --------------------------------------------------------------------------------------- helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _parse_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _tail_jsonl(path: Path, since: datetime, tail_bytes: int = TAIL_BYTES) -> list[dict] | None:
    """Rows of an append-only jsonl stamped at or after `since`; None when the file is absent."""
    if not path.exists():
        return None
    out: list[dict] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            blob = fh.read()
    except OSError:
        return None
    lines = blob.split(b"\n")
    if len(blob) >= tail_bytes and lines:
        lines = lines[1:]                               # the first line may be cut mid-row
    for raw in lines:
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        at = _parse_at(row.get("at") or row.get("finished_at") or row.get("generated_utc"))
        if at is not None and at >= since:
            out.append(row)
    return out


def _dig(doc: Any, dotted: str) -> Any:
    cur = doc
    for part in dotted.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _as_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def _rows_in(doc: Any) -> int:
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, Mapping):
        for key in ROW_KEYS:
            if isinstance(doc.get(key), list):
                return len(doc[key])
        return 1 if doc else 0
    return 0


def load_roster(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or ROSTER)
    return doc if isinstance(doc, dict) else {}


# ------------------------------------------------------------------------------------ the clocks
def leg_runs(since: datetime, path: Path | None = None) -> dict[str, dict[str, Any]] | None:
    """Per costed run name: runs, ok, timeouts, failures, last outcome -- from the compute ledger."""
    rows = _tail_jsonl(path or COMPUTE_LEDGER, since)
    if rows is None:
        return None
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = str(r.get("run") or "")
        if not name:
            continue
        st = out.setdefault(name, {"runs": 0, "ok": 0, "timeouts": 0, "failed": 0,
                                   "last_at": None, "last_outcome": None, "wall_s": 0.0})
        outcome = str(r.get("outcome") or "")
        st["runs"] += 1
        st["wall_s"] = round(st["wall_s"] + float(r.get("wall_s") or 0.0), 1)
        if outcome == "ok":
            st["ok"] += 1
        elif "TIMEOUT" in outcome.upper():
            st["timeouts"] += 1
        else:
            st["failed"] += 1
        st["last_at"] = r.get("at")
        st["last_outcome"] = outcome[:120]
    return out


def fetch_runs(since: datetime, path: Path | None = None) -> dict[str, dict[str, int]] | None:
    """Per miner leg: fetches / ok fetches / passes, from `alt_fetch_runs.jsonl`."""
    rows = _tail_jsonl(path or FETCH_RUNS, since)
    if rows is None:
        return None
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        leg = str(r.get("leg") or "")
        if not leg:
            continue
        st = out.setdefault(leg, {"passes": 0, "fetches": 0, "ok": 0, "claims_new": 0})
        st["passes"] += 1
        st["fetches"] += int(r.get("fetches") or 0)
        st["ok"] += int(r.get("ok") or 0)
        st["claims_new"] += int(r.get("claims_new") or 0)
    return out


# ------------------------------------------------------------------------------------ the yields
def seat_yield(seats: Iterable[str], since: datetime,
               roots: tuple[Path, ...] | None = None) -> dict[str, Any]:
    """Discovery files a seat wrote inside the window, their rows, and what the contract donated.

    `donated` is the proposer contract's own `counts.donated` (research/proposer_common.donate);
    a miner that writes bare rows has no such counter, and its donated count is UNMEASURED rather
    than assumed equal to its rows."""
    roots = INTEL_ROOTS if roots is None else roots
    seats = list(seats)
    files = rows = donated = 0
    donated_seen = False
    unparsed = 0
    present = False
    cut = since.timestamp()
    for seat in seats:
        for root in roots:
            d = root / seat
            if not d.is_dir():
                continue
            present = True
            try:
                entries = list(d.iterdir())
            except OSError:
                continue
            for p in entries:
                if not (p.is_file() and p.suffix.lower() in (".json", ".jsonl")):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_mtime < cut:
                    continue
                files += 1
                if st.st_size > MAX_PARSE_BYTES:
                    unparsed += 1
                    continue
                if p.suffix.lower() == ".jsonl":
                    try:
                        rows += sum(1 for ln in p.read_text("utf-8").splitlines() if ln.strip())
                    except OSError:
                        unparsed += 1
                    continue
                doc = _read_json(p)
                if doc is None:
                    unparsed += 1
                    continue
                rows += _rows_in(doc)
                n = _as_count(_dig(doc, "counts.donated"))
                if n is not None:
                    donated += n
                    donated_seen = True
    if not present:
        return {"dir_present": False, "files": 0, "rows": UNMEASURED, "unparsed_files": 0,
                "donated": UNMEASURED, "why": f"no seat directory {list(seats)} on this box"}
    rows_out: Any = UNMEASURED if (unparsed and not rows) else rows
    if donated_seen:
        donated_out: Any = donated
    elif files == 0:
        donated_out = 0
    else:
        donated_out = UNMEASURED          # bare miner rows carry no donation counter
    return {"dir_present": True, "files": files, "rows": rows_out, "unparsed_files": unparsed,
            "donated": donated_out}


def compiler_yield(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or COMPILED)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": f"{(path or COMPILED).name} absent or unreadable"}
    ps = doc.get("per_source") if isinstance(doc.get("per_source"), dict) else {}
    return {"status": "MEASURED", "compiled_at": doc.get("compiled_at"), "per_source": ps,
            "seats_dark": doc.get("seats_dark"), "intake": doc.get("intake")}


def registry_yield(since: datetime, path: Path | None = None) -> dict[str, Any]:
    """Candidates in the canonical registry per generator: all, born inside the window, judged.

    READ-ONLY (`mode=ro`), so the measurement can never take a write lock from the donors. Every
    unjudged row here is what `libs.moat.docket_feed.candidate_rows` carries into the docket."""
    p = path or REGISTRY
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p} absent on this box"}
    try:
        conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"registry unreadable: {exc}"}
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(research_candidates)")}
        if "generator" not in cols:
            return {"status": UNMEASURED, "why": "research_candidates has no generator column"}
        judged = "SUM(CASE WHEN judged_at IS NOT NULL THEN 1 ELSE 0 END)" \
            if "judged_at" in cols else "NULL"
        q = (f"SELECT COALESCE(generator, ''), COUNT(*), "  # noqa: S608 -- column names only
             f"SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END), {judged} "
             f"FROM research_candidates GROUP BY generator")
        out: dict[str, dict[str, Any]] = {}
        for gen, n, recent, nj in conn.execute(q, (_iso(since),)):
            out[str(gen)] = {"total": int(n or 0), "born_in_window": int(recent or 0),
                             "judged": UNMEASURED if nj is None else int(nj)}
        return {"status": "MEASURED", "by_generator": out}
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"registry query failed: {exc}"}
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()


def artifact_items(rel: str | None, keys: Iterable[str]) -> dict[str, Any]:
    """The first declared counter the organ's own artifact carries, with the artifact's age."""
    if not rel:
        return {"items": UNMEASURED, "why": "the organ declares no artifact"}
    p = ROOT / rel
    if not p.exists():
        return {"items": UNMEASURED, "why": f"{rel} absent on this box"}
    age_h = round((time.time() - p.stat().st_mtime) / 3600.0, 2)
    doc = _read_json(p)
    if doc is None:
        return {"items": UNMEASURED, "why": f"{rel} unreadable", "artifact_age_h": age_h}
    for k in keys:
        n = _as_count(_dig(doc, k))
        if n is not None:
            return {"items": n, "items_key": k, "artifact_age_h": age_h}
    return {"items": UNMEASURED, "why": f"none of {list(keys)} in {rel}", "artifact_age_h": age_h}


# ---------------------------------------------------------------------------------- coverage
def grounds_index(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or GROUNDS)
    grounds = doc.get("grounds") if isinstance(doc, dict) else None
    if not isinstance(grounds, list):
        return {"status": UNMEASURED, "by_region": {}, "by_language": {}}
    by_region: dict[str, int] = {}
    by_language: dict[str, int] = {}
    for g in grounds:
        if not isinstance(g, dict):
            continue
        r = str(g.get("region") or "").lower()
        lang = str(g.get("language") or "").lower()
        if r:
            by_region[r] = by_region.get(r, 0) + 1
        if lang:
            by_language[lang] = by_language.get(lang, 0) + 1
    return {"status": "MEASURED", "by_region": by_region, "by_language": by_language,
            "n": len(grounds)}


def forest_sources() -> list[dict[str, Any]]:
    """The forest federation expanded into roster rows. Regions and languages come from the
    federation's own registry, never from this file."""
    try:
        from libs.research import forests as fz
    except Exception:
        return []
    out = []
    for fid, f in fz.FORESTS.items():
        out.append({"id": f"forest_{fid}", "kind": "forest", "family": "world_forest",
                    "organ": "desks/mt5/research/forest_runner.py",
                    "clock": {"type": "hourly_cycle", "legs": [f"forest_{fid}"],
                              "box_task": fz.FOREST_TASKS.get(fid)},
                    "seats": [f"forest_{fid}"], "generators": [f"forest_{fid}"],
                    "compiler_sources": [f"forest_{fid}"], "fetch_legs": [f"forest_{fid}"],
                    "countries": [c.lower() for c in f.countries],
                    "ground_regions": [g.lower() for g in f.grounds],
                    "languages": list(f.languages),
                    "licence": "per ground (deep_forest_sources.json: `licence`, else the "
                               "publisher's public terms)"})
    return out


def forest_coverage(src: Mapping[str, Any], gidx: Mapping[str, Any]) -> dict[str, Any]:
    by_r = gidx.get("by_region") or {}
    by_l = gidx.get("by_language") or {}
    regions = sorted({*src.get("countries", []), *src.get("ground_regions", [])})
    served = [r for r in regions if by_r.get(r)]
    langs = [str(x).lower() for x in src.get("languages", [])]
    return {"regions_declared": regions, "regions_with_grounds": served,
            "regions_without_grounds": [r for r in regions if not by_r.get(r)],
            "languages_declared": langs,
            "languages_with_grounds": [x for x in langs if by_l.get(x)],
            "languages_without_grounds": [x for x in langs if not by_l.get(x)],
            "grounds": sum(int(by_r.get(r) or 0) for r in regions)}


# ------------------------------------------------------------------------------------ alt data
def alt_platforms(since: datetime, path: Path | None = None) -> dict[str, Any]:
    """The regional copy/PAMM platforms (`regional_survivor_hunters`): which were ATTEMPTED in
    the window and which yielded. A platform whose last attempt predates the window is reported
    as NOT_ATTEMPTED -- the ALT_DATA_YIELD "0 of 14" is that, not fourteen failures."""
    doc = _read_json(path or ALT_PLATFORMS)
    plats = doc.get("platforms") if isinstance(doc, dict) else None
    if not isinstance(plats, dict):
        return {"status": UNMEASURED, "why": "coverage_registry.json absent or unreadable"}
    rows: dict[str, dict[str, Any]] = {}
    for name, p in plats.items():
        if not isinstance(p, dict):
            continue
        last = _parse_at(p.get("last_attempt"))
        attempted = bool(last and last >= since)
        rows[str(name)] = {"attempted_in_window": attempted, "last_attempt": p.get("last_attempt"),
                           "last_state": p.get("last_state"), "best_rows": p.get("best_rows"),
                           "yielding": attempted and str(p.get("last_state")) == "ok"
                           and int(p.get("best_rows") or 0) > 0,
                           "region": p.get("region"), "lang": p.get("lang")}
    return {"status": "MEASURED", "n": len(rows),
            "attempted_in_window": sum(r["attempted_in_window"] for r in rows.values()),
            "yielding": sum(r["yielding"] for r in rows.values()),
            "last_attempt_any": max((str(r["last_attempt"] or "") for r in rows.values()),
                                    default=None),
            "platforms": rows}


def alt_datasets(since: datetime, rows_path: Path | None = None,
                 acquired_path: Path | None = None) -> dict[str, Any]:
    """The satellite / supply-chain / patent rows and what the acquirer made of each."""
    doc = _read_json(rows_path or ALT_SOURCES)
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return {"status": UNMEASURED, "why": "alt_dataset_sources.json absent"}
    acq = _read_json(acquired_path or ACQUIRED)
    by_url = (acq or {}).get("by_url") if isinstance(acq, dict) else None
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        stem = str(r.get("url") or "").split("{today}", 1)[0]
        hit = None
        if isinstance(by_url, dict):
            hits = [(u, m) for u, m in by_url.items() if str(u).startswith(stem)]
            hit = max(hits, key=lambda um: str((um[1] or {}).get("at") or ""), default=None)
        if not r.get("fetch"):
            status = "REGISTERED_BLOCKED"
        elif by_url is None:
            status = UNMEASURED
        elif hit is None:
            status = "NOT_YET_ATTEMPTED"
        else:
            status = str((hit[1] or {}).get("status") or UNMEASURED)
        out.append({"name": r.get("name"), "class": r.get("class"), "status": status,
                    "series": list((hit[1] or {}).get("series") or []) if hit else [],
                    "refusal": (hit[1] or {}).get("refusal") if hit else None,
                    "blocker": r.get("blocker"), "instruments": r.get("instruments"),
                    "licence": r.get("licence")})
    classes = sorted({str(x["class"]) for x in out})
    return {"status": "MEASURED" if by_url is not None else UNMEASURED,
            "why": None if by_url is not None else "data/acquired/registry.json absent on this box",
            "n": len(out), "by_class": {c: {
                "rows": sum(1 for x in out if x["class"] == c),
                "fetchable": sum(1 for x in out if x["class"] == c
                                 and x["status"] != "REGISTERED_BLOCKED"),
                "acquired": sum(1 for x in out if x["class"] == c
                                and x["status"] in ("SUCCESS", "PARTIAL"))} for c in classes},
            "rows": out,
            "cell_route": ("acquired series become PIT-certified `ext_<name>` primitives; on this "
                           "tree the only family that executes an ext_ feature is the banned "
                           "`discovered`, so these rows reach the anomaly factory, the "
                           "transmission graph and the global research OS but NOT the docket. "
                           "The cell route is the `world_macro_state` family of the unmerged "
                           "world-dataset-hunter branch (PR #92), which reloads a series by key "
                           "inside the family so the sealed gauntlet needs no change.")}


# ---------------------------------------------------------------------------------- measure
def _sum_or_unmeasured(values: list[Any]) -> Any:
    nums = [v for v in values if isinstance(v, int)]
    if nums:
        return sum(nums)
    return UNMEASURED


def measure_source(src: Mapping[str, Any], *, since: datetime,
                   legs: dict[str, dict[str, Any]] | None,
                   fetches: dict[str, dict[str, int]] | None,
                   compiled: Mapping[str, Any], registry: Mapping[str, Any],
                   gidx: Mapping[str, Any]) -> dict[str, Any]:
    clock = dict(src.get("clock") or {})
    organ = str(src.get("organ") or "")
    row: dict[str, Any] = {"id": src.get("id"), "kind": src.get("kind"),
                           "family": src.get("family"), "organ": organ,
                           "organ_on_tree": bool(organ) and (ROOT / organ).exists(),
                           "clock": clock, "licence": src.get("licence") or UNMEASURED}
    # --- did it run
    run_legs = list(clock.get("legs") or [])
    if clock.get("type") == "hourly_cycle" and run_legs:
        if legs is None:
            row["ran"] = {"status": UNMEASURED, "why": "compute ledger absent on this box"}
        else:
            per = {leg: legs.get(leg) for leg in run_legs}
            runs = sum(int((v or {}).get("runs") or 0) for v in per.values())
            row["ran"] = {"status": "MEASURED", "runs": runs,
                          "ok": sum(int((v or {}).get("ok") or 0) for v in per.values()),
                          "timeouts": sum(int((v or {}).get("timeouts") or 0)
                                          for v in per.values()),
                          "failed": sum(int((v or {}).get("failed") or 0) for v in per.values()),
                          "per_leg": per}
    else:
        row["ran"] = {"status": UNMEASURED,
                      "why": f"clock `{clock.get('type') or 'none'}` is not costed on the hourly "
                             f"compute ledger this organ reads"}
    # --- items fetched
    items: Any = UNMEASURED
    how = "no counter"
    fl = list(src.get("fetch_legs") or [])
    if fl and fetches is not None and any(leg in fetches for leg in fl):
        items = sum(int(fetches[leg]["fetches"]) for leg in fl if leg in fetches)
        how = "alt_fetch_runs.jsonl fetches"
    elif src.get("artifact"):
        got = artifact_items(src.get("artifact"), src.get("items_keys") or [])
        items, how = got.get("items", UNMEASURED), got.get("items_key") or got.get("why")
        row["artifact_age_h"] = got.get("artifact_age_h")
    row["items_fetched"] = items
    row["items_how"] = how
    # --- hypotheses minted / donated
    seats = list(src.get("seats") or [])
    if seats:
        sy = seat_yield(seats, since)
        row["seat"] = sy
        row["hypotheses_minted"] = sy["rows"]
        row["cells_donated_contract"] = sy["donated"]
    else:
        row["hypotheses_minted"] = UNMEASURED
        row["cells_donated_contract"] = UNMEASURED
    # --- compiler (donation files -> executable candidates)
    if compiled.get("status") == "MEASURED":
        ps = compiled.get("per_source") or {}
        keys = [k for k in (src.get("compiler_sources") or seats) if k in ps]
        row["compiler"] = {k: ps[k] for k in keys}
        row["cells_compiled"] = sum(int((ps[k] or {}).get("candidates") or 0) for k in keys)
    else:
        row["cells_compiled"] = UNMEASURED
    # --- registry (-> docket)
    if registry.get("status") == "MEASURED":
        bg = registry.get("by_generator") or {}
        gens = [g for g in (src.get("generators") or []) if g in bg]
        row["registry"] = {g: bg[g] for g in gens}
        row["cells_reaching_docket"] = sum(int(bg[g]["born_in_window"]) for g in gens)
        row["cells_in_registry_total"] = sum(int(bg[g]["total"]) for g in gens)
    else:
        row["cells_reaching_docket"] = UNMEASURED
    row["cells_donated"] = _sum_or_unmeasured([row.get("cells_donated_contract"),
                                               row.get("cells_compiled")])
    # --- coverage
    if src.get("kind") == "forest":
        row["coverage"] = forest_coverage(src, gidx)
    else:
        row["coverage"] = {"regions_declared": list(src.get("regions") or []),
                           "languages_declared": list(src.get("languages") or []),
                           "source_types": list(src.get("source_types") or [])}
    return row


def _holes(rows: list[dict[str, Any]], roster: Mapping[str, Any]) -> list[dict[str, Any]]:
    holes: list[dict[str, Any]] = []
    for r in rows:
        sid = r["id"]
        clock = r.get("clock") or {}
        if not r.get("organ_on_tree"):
            holes.append({"source": sid, "hole": "ORGAN_NOT_ON_THIS_TREE",
                          "detail": clock.get("note") or r.get("organ")})
            continue
        if clock.get("type") in (None, "", "none"):
            holes.append({"source": sid, "hole": "NO_CLOCK", "detail": clock.get("note")})
        ran = r.get("ran") or {}
        if ran.get("status") == "MEASURED":
            if not ran.get("runs"):
                holes.append({"source": sid, "hole": "DID_NOT_RUN_IN_WINDOW",
                              "detail": f"0 runs of {clock.get('legs')} in {WINDOW_H}h"})
            elif ran.get("timeouts") and not ran.get("ok"):
                holes.append({"source": sid, "hole": "TIMES_OUT_EVERY_PASS",
                              "detail": f"{ran['timeouts']} timeout(s), 0 ok in {WINDOW_H}h"})
        for field in ("items_fetched", "hypotheses_minted", "cells_reaching_docket"):
            if r.get(field) == UNMEASURED:
                holes.append({"source": sid, "hole": f"{field.upper()}_UNMEASURED",
                              "detail": r.get("items_how") if field == "items_fetched" else None})
        if isinstance(r.get("hypotheses_minted"), int) and r["hypotheses_minted"] > 0 \
                and r.get("cells_reaching_docket") == 0 and r.get("cells_compiled") in (0, None):
            holes.append({"source": sid, "hole": "MINTS_BUT_NOTHING_REACHES_THE_DOCKET",
                          "detail": f"{r['hypotheses_minted']} row(s), 0 compiled, 0 registered"})
        cov = r.get("coverage") or {}
        if cov.get("regions_without_grounds"):
            holes.append({"source": sid, "hole": "REGIONS_WITHOUT_GROUNDS",
                          "detail": cov["regions_without_grounds"]})
        if cov.get("languages_without_grounds"):
            holes.append({"source": sid, "hole": "LANGUAGES_WITHOUT_GROUNDS",
                          "detail": cov["languages_without_grounds"]})
    # the world the principal named, against what any source declares or serves
    want = [str(x).lower() for x in (roster.get("required_regions") or [])]
    have: set[str] = set()
    for r in rows:
        cov = r.get("coverage") or {}
        have |= {str(x).lower() for x in cov.get("regions_with_grounds") or []}
        have |= {str(x).lower() for x in cov.get("regions_declared") or []
                 if r.get("kind") != "forest"}
    missing = [w for w in want if w not in have]
    if missing:
        holes.append({"source": "*", "hole": "REQUIRED_REGION_UNSERVED", "detail": missing})
    return holes


def measure(now: datetime | None = None, roster_path: Path | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or _now()
    since = now - timedelta(hours=WINDOW_H)
    roster = load_roster(roster_path)
    sources = [s for s in (roster.get("sources") or []) if isinstance(s, dict)]
    if roster.get("expand_forests", True):
        known = {s.get("id") for s in sources}
        sources += [f for f in forest_sources() if f["id"] not in known]
    for u in roster.get("media_units") or []:
        if isinstance(u, dict) and u.get("name"):
            sources.append({"id": f"media:{u['name']}", "kind": u.get("kind") or "media",
                            "family": "media_miners", "organ": u.get("organ"),
                            "clock": {"type": "hourly_cycle", "legs": ["world_media_miners"],
                                      "unit": u["name"]},
                            "seats": list(u.get("seats") or []),
                            "compiler_sources": list(u.get("seats") or []),
                            "generators": list(u.get("seats") or []),
                            "regions": list(u.get("regions") or []),
                            "languages": list(u.get("languages") or []),
                            "source_types": list(u.get("source_types") or []),
                            "licence": u.get("licence")})
    legs = leg_runs(since)
    fetches = fetch_runs(since)
    compiled = compiler_yield()
    registry = registry_yield(since)
    gidx = grounds_index()
    unit_runs = _unit_runs(since)
    rows = []
    for s in sources:
        r = measure_source(s, since=since, legs=legs, fetches=fetches, compiled=compiled,
                           registry=registry, gidx=gidx)
        unit = (s.get("clock") or {}).get("unit")
        if unit:
            ur = (unit_runs or {}).get(unit)
            r["unit_runs"] = ur if unit_runs is not None else UNMEASURED
            if ur and isinstance(ur.get("rows"), int):
                r["items_fetched"], r["items_how"] = ur["rows"], "world_factory_runs.jsonl rows"
        rows.append(r)
    holes = _holes(rows, roster)
    plats = alt_platforms(since)
    alt = alt_datasets(since)
    if plats.get("status") == "MEASURED" and plats["attempted_in_window"] == 0:
        holes.append({"source": "regional_survivor_hunters", "hole": "ALT_PLATFORMS_NOT_ATTEMPTED",
                      "detail": f"0 of {plats['n']} platforms attempted in {WINDOW_H}h; last "
                                f"attempt {plats['last_attempt_any']}"})
    for r in alt.get("rows") or []:
        if r["status"] == "REGISTERED_BLOCKED":
            holes.append({"source": f"alt:{r['name']}", "hole": "ALT_DATASET_BLOCKED",
                          "detail": r.get("blocker")})
    if alt.get("status") == "MEASURED" or alt.get("rows"):
        holes.append({"source": "alt_datasets", "hole": "NO_CELL_ROUTE_FOR_ACQUIRED_SERIES",
                      "detail": alt.get("cell_route")})
    by_family: dict[str, dict[str, Any]] = {}
    for r in rows:
        fam = by_family.setdefault(str(r.get("family") or r.get("kind")), {
            "sources": 0, "items_fetched": [], "hypotheses_minted": [], "cells_donated": [],
            "cells_reaching_docket": []})
        fam["sources"] += 1
        for k in ("items_fetched", "hypotheses_minted", "cells_donated", "cells_reaching_docket"):
            fam[k].append(r.get(k))
    for fam in by_family.values():
        for k in ("items_fetched", "hypotheses_minted", "cells_donated", "cells_reaching_docket"):
            vals = fam[k]
            fam[k] = {"sum_measured": sum(v for v in vals if isinstance(v, int)),
                      "measured": sum(1 for v in vals if isinstance(v, int)),
                      "unmeasured": sum(1 for v in vals if not isinstance(v, int))}
    languages: set[str] = set()
    regions: set[str] = set()
    for r in rows:
        cov = r.get("coverage") or {}
        languages |= set(cov.get("languages_with_grounds") or [])
        regions |= set(cov.get("regions_with_grounds") or [])
        if r.get("kind") != "forest":
            languages |= set(cov.get("languages_declared") or [])
            regions |= set(cov.get("regions_declared") or [])
    return {
        "generated_at": _iso(now), "window_h": WINDOW_H, "roster": str(ROSTER.relative_to(ROOT)),
        "n_sources": len(rows),
        "inputs": {"compute_ledger": "MEASURED" if legs is not None else UNMEASURED,
                   "alt_fetch_runs": "MEASURED" if fetches is not None else UNMEASURED,
                   "compiler": compiled.get("status"),
                   "compiler_compiled_at": compiled.get("compiled_at"),
                   "registry": registry.get("status"), "registry_why": registry.get("why"),
                   "grounds": gidx.get("status"), "grounds_n": gidx.get("n")},
        "coverage": {"regions": sorted(regions), "languages": sorted(languages),
                     "n_regions": len(regions), "n_languages": len(languages)},
        "by_family": by_family, "sources": rows,
        "alt_platforms": plats, "alt_datasets": alt,
        "holes": holes, "n_holes": len(holes),
        "rule": ("UNMEASURED is never 0: a zero here was read from an artifact that said zero. "
                 "This organ adds clocks and measurements; it never sizes, caps or vetoes."),
        "elapsed_s": round(time.monotonic() - t0, 2),
    }


# ---------------------------------------------------------------------------------- mining
def _unit_runs(since: datetime) -> dict[str, dict[str, Any]] | None:
    rows = _tail_jsonl(RUNS, since)
    if rows is None:
        return None
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        u = str(r.get("unit") or "")
        st = out.setdefault(u, {"runs": 0, "ok": 0, "timeouts": 0, "failed": 0, "rows": 0,
                                "last_at": None, "last_status": None})
        st["runs"] += 1
        status = str(r.get("status") or "")
        key = {"ok": "ok", "timeout": "timeouts"}.get(status, "failed")
        st[key] += 1
        st["rows"] += int(r.get("rows") or 0)
        st["last_at"], st["last_status"] = r.get("at"), status
    return out


def _load_cursor(path: Path | None = None) -> dict[str, str]:
    doc = _read_json(path or CURSOR)
    return {str(k): str(v) for k, v in (doc or {}).items()} if isinstance(doc, dict) else {}


def order_units(units: list[dict[str, Any]], cursor: Mapping[str, str]) -> list[dict[str, Any]]:
    """Never-run first, then least-recently-run; roster order breaks ties."""
    def key(iu: tuple[int, dict[str, Any]]) -> tuple[int, str, int]:
        i, u = iu
        last = cursor.get(str(u.get("name")))
        return (1 if last else 0, last or "", i)
    return [u for _i, u in sorted(enumerate(units), key=key)]


def _run_unit_subprocess(unit: Mapping[str, Any], timeout_s: float) -> dict[str, Any]:
    cmd = [sys.executable, "-u", "-W", "ignore", str(Path(__file__).resolve()),
           "--unit", str(unit["name"])]
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,  # noqa: S603
                           cwd=str(DESK), check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": round(time.monotonic() - t0, 1), "rows": 0}
    rows = 0
    for line in reversed((r.stdout or "").splitlines()):
        if line.startswith("WORLD_FACTORY_UNIT "):
            with contextlib.suppress(ValueError):
                rows = int(json.loads(line.split(" ", 1)[1]).get("rows") or 0)
            break
    return {"status": "ok" if r.returncode == 0 else "failed", "exit": r.returncode,
            "rows": rows, "seconds": round(time.monotonic() - t0, 1),
            "err": (r.stderr or "")[-300:] if r.returncode else ""}


def run_unit(name: str, roster_path: Path | None = None) -> int:
    """In-process body of one unit: import the miner and call its own entry point."""
    roster = load_roster(roster_path)
    unit = next((u for u in roster.get("media_units") or [] if u.get("name") == name), None)
    if unit is None:
        print(f"world_factory: unknown unit {name}")
        return 2
    sc = str(SIDE_CHANNELS)
    if sc not in sys.path:
        sys.path.insert(0, sc)
    import importlib
    mod = importlib.import_module(str(unit["module"]))
    fn = getattr(mod, str(unit.get("callable") or "run_and_save"))
    out = fn()
    rows = 0
    if isinstance(out, list):
        rows = len(out)
    elif isinstance(out, dict):
        summ = out.get("summary") if isinstance(out.get("summary"), dict) else {}
        rows = int(summ.get("total") or out.get("total") or 0) or _rows_in(out)
    print("WORLD_FACTORY_UNIT " + json.dumps({"unit": name, "rows": rows}))
    return 0


def mine(budget_s: float, *, roster_path: Path | None = None, dry_run: bool = False,
         runner: Any = None) -> dict[str, Any]:
    """Run the media units least-recently-run first until the budget is spent."""
    t0 = time.monotonic()
    roster = load_roster(roster_path)
    units = [u for u in roster.get("media_units") or [] if isinstance(u, dict) and u.get("name")]
    cursor = _load_cursor()
    plan = order_units(units, cursor)
    run = runner or _run_unit_subprocess
    done: list[dict[str, Any]] = []
    deferred: list[str] = []
    for u in plan:
        left = budget_s - (time.monotonic() - t0) - RESERVE_S
        timeout = float(u.get("timeout_s") or 180)
        if left < min(timeout, 60.0):
            deferred.append(str(u["name"]))
            continue
        if dry_run:
            done.append({"unit": u["name"], "status": "planned"})
            continue
        res = run(u, min(timeout, left))
        rec = {"at": _iso(_now()), "unit": u["name"], **res}
        done.append(rec)
        cursor[str(u["name"])] = rec["at"]
        with contextlib.suppress(OSError):
            RUNS.parent.mkdir(parents=True, exist_ok=True)
            with RUNS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        with contextlib.suppress(OSError):
            tmp = CURSOR.with_suffix(".tmp")
            tmp.write_text(json.dumps(cursor, indent=1, sort_keys=True), "utf-8")
            os.replace(tmp, CURSOR)
    doc = {"at": _iso(_now()), "units": len(units), "ran": done, "deferred": deferred,
           "elapsed_s": round(time.monotonic() - t0, 1), "dry_run": dry_run}
    print(f"world_factory mine: {len(done)} unit(s) run, {len(deferred)} deferred to the next "
          f"pass (least-recently-run first)", flush=True)
    return doc


# ------------------------------------------------------------------------------------- write
def write(doc: Mapping[str, Any], out: Path | None = None) -> Path:
    p = out or REPORT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--unit", default=None)
    ap.add_argument("--budget-s", type=float, default=1400.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.unit:
        return run_unit(a.unit)
    if a.mine:
        mine(a.budget_s, dry_run=a.dry_run)
        if not a.measure:
            return 0
    doc = measure()
    if a.dry_run:
        print(json.dumps({k: doc[k] for k in ("n_sources", "n_holes", "coverage", "inputs")},
                         indent=1, default=str))
        return 0
    p = write(doc, Path(a.out) if a.out else None)
    print(f"world_factory: {doc['n_sources']} source(s), {doc['n_holes']} hole(s), "
          f"{doc['coverage']['n_regions']} region(s) / {doc['coverage']['n_languages']} "
          f"language(s) -> {p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
