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
  * a ROTATION that never restarts at the top: a cursor in data/deep_forest_regions_state.json
    carries the next producing region across passes, so all 33 are reached in turn (Asia first
    in the order), and the 20 always-zero regions are queued FIRST in any pass that starts in a
    UTC hour divisible by 6 (once per 6-hour window);
  * up to PARALLEL regions at once (the claims ledger and seen-set are cross-process locked by
    the miner; politeness stays per host), each its own subprocess with its own log;
  * a pass stops launching at PASS_BUDGET_S so the next hourly pass starts clean;
  * every region's result is appended to data/deep_forest_region_runs.jsonl and the rolling view
    is published to reports/DEEP_FOREST_REGIONS.json (per region: last start/end, rc, new claims,
    24 h claims and passes, kind, cadence), which the guardian reads (check_deep_forest_regions:
    a region with no finished pass inside twice its cadence is DARK and paged).

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
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
STATE = DESK / "data" / "deep_forest_regions_state.json"
RUNS = DESK / "data" / "deep_forest_region_runs.jsonl"
REPORT = DESK / "reports" / "DEEP_FOREST_REGIONS.json"
LOGS = DESK / "logs" / "deep_forest"
MINER = DESK / "research" / "deep_forest_miner.py"

#: The cloud pass's lists, verbatim (handoff/deep-forest-box-parity.md), Asia first.
PRODUCING = (
    "cn", "jp", "kr", "tw", "hk", "my", "id", "th", "vn", "ph", "in", "pk", "au", "global",
    "institutional", "us", "de", "ru", "tr", "ng", "ma", "fr", "nl", "es", "pl", "se", "dk", "fi",
    "br", "ar", "cl", "co", "ch",
)
ZERO = (
    "mx", "eg", "hu", "ca", "it", "nz", "ea", "bd", "sa", "ke", "lk", "ua", "za", "ae", "gb", "cz",
    "il", "no", "pe", "sg",
)
REGION_BUDGET_S = 900
REGION_TIMEOUT_S = 1000
WORKERS = 4
PARALLEL = int(os.environ.get("QUANT_DEEP_FOREST_PARALLEL", "4") or 4)
PASS_BUDGET_S = 3300        # stop launching new regions after 55 min; the next pass continues
ZERO_EVERY_H = 6
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


def plan(state: dict[str, Any], now: datetime) -> list[str]:
    """This pass's queue: zero regions first when a 6-hour window opens, then the producing
    regions from the saved cursor round the ring (each once)."""
    window = f"{now:%Y-%m-%d}T{now.hour - now.hour % ZERO_EVERY_H:02d}"
    q: list[str] = []
    if now.hour % ZERO_EVERY_H == 0 and state.get("zero_window") != window:
        q += ZERO
    i = int(state.get("cursor") or 0) % len(PRODUCING)
    q += [*PRODUCING[i:], *PRODUCING[:i]]
    return q


def run_region(region: str) -> dict[str, Any]:
    """One region, the cloud's exact command line, with its own log and a hard timeout."""
    LOGS.mkdir(parents=True, exist_ok=True)
    start = _now()
    argv = [sys.executable, str(MINER), "--region", region, "--budget-s", str(REGION_BUDGET_S),
            "--workers", str(WORKERS)]
    try:
        p = subprocess.run(argv, cwd=str(DESK / "research"), capture_output=True, text=True,
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
            "claims_total": int(m.group(2)) if m else None,
            "kind": "zero" if region in ZERO else "producing"}


def publish(rows: Sequence[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Per region: the newest finished pass, and the last 24 hours' claims and passes."""
    since = now - timedelta(hours=24)
    regions: dict[str, dict[str, Any]] = {
        r: {"kind": "zero" if r in ZERO else "producing", "last_end": None, "last_start": None,
            "last_rc": None, "last_claims_new": None, "claims_24h": 0, "passes_24h": 0}
        for r in (*PRODUCING, *ZERO)}
    for row in rows:
        g = regions.get(str(row.get("region")))
        try:
            end = datetime.fromisoformat(str(row.get("end")))
        except ValueError:
            continue
        if g is None:
            continue
        if end >= since:
            g["passes_24h"] += 1
            g["claims_24h"] += int(row.get("claims_new") or 0)
        if g["last_end"] is None or end > datetime.fromisoformat(g["last_end"]):
            g.update(last_end=row.get("end"), last_start=row.get("start"), last_rc=row.get("rc"),
                     last_claims_new=row.get("claims_new"))
    # Cadence: a full producing rotation at PARALLEL regions per ~REGION_TIMEOUT_S, and 6 h for
    # the zero regions; the guardian calls a region dark past twice its cadence.
    rotation_h = round(len(PRODUCING) / max(1, PARALLEL) * REGION_TIMEOUT_S / 3600 + 1, 2)
    for g in regions.values():
        g["cadence_h"] = float(ZERO_EVERY_H) if g["kind"] == "zero" else rotation_h
    doc = {"schema": "deep_forest_regions/1", "at": now.isoformat(timespec="seconds"),
           "parallel": PARALLEL, "region_budget_s": REGION_BUDGET_S,
           "claims_24h": sum(g["claims_24h"] for g in regions.values()),
           "regions": regions}
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
    state = _read(STATE) or {}
    queue = plan(state, t)
    started = clock()
    done: list[dict[str, Any]] = []
    zero_left = set(ZERO) if queue and queue[0] in ZERO else set()

    def launch(r: str) -> dict[str, Any] | None:
        if clock() - started > PASS_BUDGET_S:
            return None
        return runner(r)

    with ThreadPoolExecutor(max_workers=max(1, PARALLEL)) as pool:
        for res in pool.map(launch, queue):
            if res is None:
                continue
            done.append(res)
            RUNS.parent.mkdir(parents=True, exist_ok=True)
            with RUNS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(res) + "\n")
            zero_left.discard(res["region"])
    ran_producing = [r["region"] for r in done if r["region"] in PRODUCING]
    if ran_producing:
        state["cursor"] = (PRODUCING.index(ran_producing[-1]) + 1) % len(PRODUCING)
    if queue and queue[0] in ZERO and not zero_left:
        state["zero_window"] = f"{t:%Y-%m-%d}T{t.hour - t.hour % ZERO_EVERY_H:02d}"
    state["last_pass"] = t.isoformat(timespec="seconds")
    _write_atomic(STATE, state)
    doc = publish(_rows(t - timedelta(days=2)), _now() if now is None else t)
    return {"ran": [r["region"] for r in done], "claims_new": sum(int(r.get("claims_new") or 0)
                                                                   for r in done),
            "report": str(REPORT), "claims_24h": doc["claims_24h"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.dry_run:
        print(" ".join(plan(_read(STATE) or {}, _now())))
        return 0
    print(json.dumps(run_pass()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
