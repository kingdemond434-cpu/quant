"""THE DEEP FOREST ON THE BOX, REGION BY REGION (zuck 2026-11-25 17:48Z: box only, at least as good
as the cloud pass; then the cloud pass shuts off).

THE BAR (handoff/deep-forest-box-parity.md). The cloud pass runs `deep_forest_miner.py --region R
--budget-s 900 --workers 4` (hard timeout 1000 s) per region, the producing regions every pass with
Asia first, the always-zero regions only when the UTC hour is a multiple of 6, and publishes each
region's new claims every pass. In practice it reaches one or two regions an hour. The box had no
per-region schedule and published nothing per region since 10-28.

WHAT THIS DOES, as the MT5-DeepForestRegions task (hourly, one instance at a time):
  * the SAME miner, the same defaults (robots gate, honest UA), the same per-region budget and hard
    timeout -- nothing about how a ground is fetched changes here;
  * EVERY REGION IN THE GROUNDS FILE, derived at run time (222 on 11-25), never a fixed list;
  * a priority queue rebuilt from the run ledger each pass: first every region past the 24 h floor
    (or never run), oldest first; then regions due by their own cadence -- 3 h for a region that
    produced claims in the last 48 h, 6 h for a zero-yield one -- yielding first, Asia first;
  * up to PARALLEL regions at once (the claims ledger and seen-set are cross-process locked by
    the miner; politeness stays per host), each its own subprocess with its own log;
  * ONE POLITENESS GATE ACROSS THE PROCESSES: every miner subprocess books its per-host slots in
    the same folder (polite_fetch.SharedHostGate via QUANT_HOST_GATE_DIR), so 4 processes never
    hit a shared host faster than one would (Audit H1);
  * a pass stops launching at PASS_BUDGET_S (40 min), so the last region's 1,000 s timeout still
    ends inside the task's 58-minute limit, and each finished region is appended and published
    AS IT COMPLETES -- a killed pass loses nothing already done (Audit H2);
  * every region's result is appended to data/deep_forest_region_runs.jsonl and the rolling view
    is published to reports/DEEP_FOREST_REGIONS.json (per region: last start/end, rc, new claims,
    24 h claims and passes, cadence, floor), which the guardian reads (check_deep_forest_regions:
    a region with no finished pass inside the 24 h floor is DARK and paged).

    python desks/mt5/research/deep_forest_regions.py             # one pass
    python desks/mt5/research/deep_forest_regions.py --dry-run   # print the plan only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
STATE = DESK / "data" / "deep_forest_regions_state.json"
RUNS = DESK / "data" / "deep_forest_region_runs.jsonl"
REPORT = DESK / "reports" / "DEEP_FOREST_REGIONS.json"
LOGS = DESK / "logs" / "deep_forest"
MINER = DESK / "research" / "deep_forest_miner.py"

#: THE REGIONS ARE DERIVED, NEVER LISTED (Data 2026-11-25 17:53Z): every distinct `region` in the
#: grounds file (desks/mt5/data/deep_forest_sources.json: 222 on 11-25, the ISO countries of the
#: global-grounds packet plus `global` and `institutional`). A ground added later is picked up
#: with no code change. A ground with no region is the founding Chinese forest (miner.cluster_of).
SOURCES = DESK / "data" / "deep_forest_sources.json"
#: Asia first (the cloud pass's order), as a tie-break inside each priority band.
ASIA_FIRST = ("cn", "jp", "kr", "tw", "hk", "my", "id", "th", "vn", "ph", "in", "pk", "au")
#: Every region is attempted at least once per REGION_FLOOR_H (= deep_forest_miner.REGION_FLOOR_H,
#: the floor country_census.floor_breaches checks). Regions that produced claims in the last
#: YIELD_LOOKBACK_H come back every YIELD_CADENCE_H (compute follows measured yield); zero-yield
#: regions every ZERO_CADENCE_H when capacity is left, and never later than the floor.
REGION_FLOOR_H = 24.0
YIELD_LOOKBACK_H = 48.0
YIELD_CADENCE_H = 3.0
ZERO_CADENCE_H = 6.0
REGION_BUDGET_S = 900
REGION_TIMEOUT_S = 1000
WORKERS = 4
PARALLEL = int(os.environ.get("QUANT_DEEP_FOREST_PARALLEL", "4") or 4)
PASS_BUDGET_S = 2400        # last launch at 40 min + 1,000 s timeout < the 58-minute task limit
HOST_GATE = DESK / "data" / ".host_gate"
_CLAIMS = re.compile(r"claims_new=(\d+)\b.*?total=(\d+)")

Runner = Callable[[str], dict[str, Any]]


def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def regions(sources: Path | None = None) -> list[str]:
    try:
        cfg = json.loads((sources or SOURCES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted({str(g.get("region") or "cn") for g in cfg.get("grounds") or []
                   if isinstance(g, dict)})


def _history(rows: Sequence[dict[str, Any]], now: datetime) -> dict[str, dict[str, Any]]:
    since = now - timedelta(hours=YIELD_LOOKBACK_H)
    h: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            end = datetime.fromisoformat(str(r.get("end")))
        except ValueError:
            continue
        g = h.setdefault(str(r.get("region")), {"last_end": None, "claims_lookback": 0})
        if g["last_end"] is None or end > g["last_end"]:
            g["last_end"] = end
        if end >= since:
            g["claims_lookback"] += int(r.get("claims_new") or 0)
    return h


def cadence_h(hist: dict[str, Any] | None) -> float:
    return YIELD_CADENCE_H if (hist or {}).get("claims_lookback") else ZERO_CADENCE_H


def plan(names: Sequence[str], rows: Sequence[dict[str, Any]], now: datetime) -> list[str]:
    """This pass's queue, most urgent first: (1) regions past the 24 h floor or never run, oldest
    first; (2) regions due by their own cadence, yielding before zero, most overdue first. Asia
    leads inside each band. Regions not yet due are left for a later pass."""
    hist = _history(rows, now)
    asia = {r: i for i, r in enumerate(ASIA_FIRST)}

    def age_h(r: str) -> float:
        end = (hist.get(r) or {}).get("last_end")
        return float("inf") if end is None else (now - end).total_seconds() / 3600

    floor = [r for r in names if age_h(r) >= REGION_FLOOR_H]
    floor.sort(key=lambda r: (-min(age_h(r), 1e9), asia.get(r, 99), r))
    due = [r for r in names if r not in floor and age_h(r) >= cadence_h(hist.get(r))]
    due.sort(key=lambda r: (cadence_h(hist.get(r)), asia.get(r, 99),
                            -age_h(r) / cadence_h(hist.get(r)), r))
    return floor + due


def run_region(region: str) -> dict[str, Any]:
    """One region, the cloud's exact command line, with its own log and a hard timeout."""
    LOGS.mkdir(parents=True, exist_ok=True)
    start = _now()
    argv = [sys.executable, str(MINER), "--region", region, "--budget-s", str(REGION_BUDGET_S),
            "--workers", str(WORKERS)]
    try:
        HOST_GATE.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "QUANT_HOST_GATE_DIR": str(HOST_GATE)}
        p = subprocess.run(argv, cwd=str(DESK / "research"), capture_output=True, text=True,
                           env=env,
                           encoding="utf-8", errors="replace", timeout=REGION_TIMEOUT_S)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        rc = 124
        out = str(exc.stdout or "") if not isinstance(exc.stdout, bytes) else exc.stdout.decode(
            "utf-8", "replace")
    (LOGS / f"{region}.log").write_text(out[-200_000:], encoding="utf-8")
    m = _CLAIMS.search(out)
    return {"region": region, "start": start.isoformat(timespec="seconds"),
            "end": _now().isoformat(timespec="seconds"), "rc": rc,
            "claims_new": int(m.group(1)) if m else None,
            "claims_total": int(m.group(2)) if m else None}


def publish(names: Sequence[str], rows: Sequence[dict[str, Any]],
            now: datetime) -> dict[str, Any]:
    """Per region: the newest finished pass, its cadence and the floor, and the last 24 hours."""
    since = now - timedelta(hours=24)
    hist = _history(rows, now)
    regs: dict[str, dict[str, Any]] = {
        r: {"last_end": None, "last_start": None, "last_rc": None, "last_claims_new": None,
            "claims_24h": 0, "passes_24h": 0, "cadence_h": cadence_h(hist.get(r)),
            "floor_h": REGION_FLOOR_H} for r in names}
    for row in sorted(rows, key=lambda x: str(x.get("end"))):
        g = regs.get(str(row.get("region")))
        try:
            end = datetime.fromisoformat(str(row.get("end")))
        except ValueError:
            continue
        if g is None:
            continue
        if end >= since:
            g["passes_24h"] += 1
            g["claims_24h"] += int(row.get("claims_new") or 0)
        g.update(last_end=row.get("end"), last_start=row.get("start"), last_rc=row.get("rc"),
                 last_claims_new=row.get("claims_new"))
    doc = {"schema": "deep_forest_regions/2", "at": now.isoformat(timespec="seconds"),
           "regions_from": str(SOURCES.name), "n_regions": len(names), "parallel": PARALLEL,
           "region_budget_s": REGION_BUDGET_S, "floor_h": REGION_FLOOR_H,
           "claims_24h": sum(g["claims_24h"] for g in regs.values()),
           "regions": regs}
    _write_atomic(REPORT, doc)
    return doc


def _rows(since: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = RUNS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines[-20_000:]:
        try:
            r = json.loads(line)
            if datetime.fromisoformat(str(r.get("end"))) >= since:
                out.append(r)
        except (ValueError, TypeError):
            continue
    return out


def run_pass(now: datetime | None = None, *, runner: Runner = run_region,
             clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    t = now or _now()
    names = regions()
    queue = plan(names, _rows(t - timedelta(days=3)), t)
    started = clock()
    done: list[dict[str, Any]] = []

    def launch(r: str) -> dict[str, Any] | None:
        if clock() - started > PASS_BUDGET_S:
            return None
        return runner(r)

    with ThreadPoolExecutor(max_workers=max(1, PARALLEL)) as pool:
        futures = [pool.submit(launch, r) for r in queue]
        for fut in as_completed(futures):
            res = fut.result()
            if res is None:
                continue
            done.append(res)
            RUNS.parent.mkdir(parents=True, exist_ok=True)
            with RUNS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(res) + "\n")
            # publish after EVERY region: a pass killed at the task limit keeps what it finished
            publish(names, _rows(t - timedelta(days=3)), _now() if now is None else t)
    _write_atomic(STATE, {"last_pass": t.isoformat(timespec="seconds"), "queued": len(queue),
                          "ran": len(done)})
    doc = publish(names, _rows(t - timedelta(days=3)), _now() if now is None else t)
    return {"ran": [r["region"] for r in done],
            "claims_new": sum(int(r.get("claims_new") or 0) for r in done),
            "queued": len(queue), "regions": len(names), "claims_24h": doc["claims_24h"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.dry_run:
        print(" ".join(plan(regions(), _rows(_now() - timedelta(days=3)), _now())))
        return 0
    print(json.dumps(run_pass()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
