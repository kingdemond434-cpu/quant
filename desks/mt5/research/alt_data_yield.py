"""ALT_DATA_YIELD.json -- what the alt-data miners actually reach, per platform, vector and leg.

    python research/alt_data_yield.py          # rebuild the artifact from the ledgers

NOT A LEG OF ITS OWN. The artifact is rewritten at the end of every pass of the organs that move
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
* the week: vectors attempted in the last seven days against vectors named.

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
          compute_ledger: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    coverage = coverage or COVERAGE
    frontier = frontier or FRONTIER
    vector_stats = vector_stats or VECTOR_STATS
    runs = runs or RUNS
    compute_ledger = compute_ledger or COMPUTE_LEDGER
    plat = platforms(_json(coverage))
    vec = vectors(_json(frontier), _json(vector_stats), now)
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
        },
        "platforms": plat, "vectors": vec, "legs": leg,
        "sources": {"platforms": str(coverage), "vectors": [str(frontier), str(vector_stats)],
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
    doc = build(**{k: Path(v) for k, v in paths.items() if v is not None})
    _atomic(out or OUT, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    return doc


def main() -> int:
    doc = write()
    s = doc["summary"]
    print(f"ALT_DATA_YIELD platforms {s['platforms_yielding']}/{s['platforms']} yielding; "
          f"vectors attempted this week {s['vectors_attempted_this_week']}/{s['vectors_named']}"
          f"; never attempted {s['vectors_never_attempted']}; written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
