#!/usr/bin/env python3
"""FORWARD LANE FENCE -- every forward lane ticking, every certificate in a lane, or it is red.

THE PRINCIPAL (2026-10-13): "all forward lanes must be running actively not stale ever n all
certis must always be put in forward lanes".

WHAT ALREADY HOLDS EACH PIECE, AND WHAT DID NOT. `forward_enrolment` censuses certificates
against the promoting lanes' clocks, `clock_liveness` repairs a single frozen clock, and
`stall_watch.ps1` restarts a scheduled task. Nothing asked the LANE question: is each lane's
state file actually advancing, and is every certificate in SOME lane, the near-miss farm (which
runs the certificates the integrity door has not admitted yet) included. Measured on the box
2026-10-13: 974 certificates, 847 in a promoting lane, 127 held at the door for 27.7h to 448h
with no clock anywhere, and 17 clocks blocked on bars. `forward_enrolment` counted the 127 as
HELD, a named decision, so no fence ever went red on them.

THE VERDICTS, per lane (`LANES`):

    FRESH        the lane's `updated_at` is inside its allowance (two of its own cadences)
    STALE        older than that: RED, and the lane's own engine is re-run on this pass
    RETIRED      the lane declares itself retired (`pipeline_status: RETIRED_*`)
    UNMEASURED   no state file on this host; a real answer, never a pass (L1.28a)

and per certificate: in a promoting lane, in the farm, or in NO lane. A certificate in no lane
for longer than one cycle is RED.

ONLY THE FARM IS EVER RESTARTED HERE, and only when its own ledger is stale. A stale promoting
lane is reported RED and left to its scheduled task and stall_watch. THE RESTART IS THE FARM'S OWN
ENGINE, run as a subprocess inside this leg's budget, skipped when
a process already runs that script (a hung engine is `stall_watch`'s to kill, not this leg's),
and proved only by the lane's `updated_at` moving -- never by a return code.

COMMON CLOCK (the tier-1 gap of 2026-10-13: ~15 independent bets need ~600 days of OVERLAPPING
forward history). Every accruing clock runs on the same wall clock already; what the desk lacked
was the count. `common_clock` publishes, for each horizon, how many accruing clocks have at least
that many days of forward history, which is the population a correlation or breadth estimate on
that horizon can use.

Artifact: `reports/FORWARD_LANE_FENCE.json`. Clock: hourly leg `forward_lane_fence`. Exit 1 when
red, so the cycle's failure ledger carries it.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW = BASE / "reports" / "shadow"
ENROLMENT = BASE / "reports" / "FORWARD_ENROLMENT.json"
OUT = BASE / "reports" / "FORWARD_LANE_FENCE.json"
UNMEASURED = "UNMEASURED"
FRESH, STALE, RETIRED = "FRESH", "STALE", "RETIRED"
CYCLE_HOURS = 1.0
#: Each lane: its state file under reports/shadow, the engine that advances it, its cadence in
#: hours. The main lane runs every 15 minutes (MT5-Shadow) and on the hourly `enrol_clocks` leg;
#: the others on the hourly cycle. The allowance is two cadences, the same rule clock_liveness
#: applies to one clock.
LANES: dict[str, dict[str, Any]] = {
    "main": {"state": "shadow_state.json", "engine": "research/shadow_forward.py",
             "cadence_h": 0.25, "promoting": True},
    "qquant": {"state": "qquant_shadow_state.json", "engine": "research/qquant_shadow.py",
               "cadence_h": 1.0, "promoting": True},
    "scalp": {"state": "scalp_shadow_state.json", "engine": "research/scalp_shadow.py",
              "cadence_h": 1.0, "promoting": True},
    "external": {"state": "external_shadow_state.json", "engine": None,
                 "cadence_h": 1.0, "promoting": True},
    "farm": {"state": "farm/near_miss_farm.json", "engine": "research/near_miss_farm.py",
             "cadence_h": 1.0, "promoting": False},
}
ACTIVE = frozenset({"ACTIVE", "PROMOTION CANDIDATE", ""})
#: One clock not reached by its engine for this long is silent: the same limit
#: `forward_enrolment.SILENT_TICK_HOURS` names (three hourly cycles).
SILENT_TICK_H = 3.0
HORIZONS_D = (14, 30, 90, 180, 365, 600)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _hours(now: datetime, raw: Any) -> float | None:
    t = _ts(raw)
    return None if t is None else round((now - t).total_seconds() / 3600.0, 3)


def lane_rows(doc: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(doc, dict):
        return {}
    rows = {k: v for k, v in doc.items() if isinstance(v, dict) and k != "sleeves"}
    sleeves = doc.get("sleeves")
    if isinstance(sleeves, dict):
        rows.update({k: v for k, v in sleeves.items() if isinstance(v, dict)})
    return rows


def lane_verdict(name: str, spec: dict[str, Any], doc: Any, now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {"lane": name, "state": f"reports/shadow/{spec['state']}",
                           "cadence_h": spec["cadence_h"], "allowance_h": 2 * spec["cadence_h"],
                           "promoting": spec["promoting"]}
    if not isinstance(doc, dict):
        return {**out, "verdict": UNMEASURED, "why": "no readable state file on this host"}
    if str(doc.get("pipeline_status") or "").startswith("RETIRED"):
        return {**out, "verdict": RETIRED, "why": str(doc.get("pipeline_status"))}
    age = _hours(now, doc.get("updated_at"))
    rows = lane_rows(doc)
    active = [r for r in rows.values() if str(r.get("status") or "").upper() in ACTIVE]
    ticks = [_hours(now, r.get("last_attempt_at")) for r in active]
    entries = [_hours(now, r.get("last_entry")) for r in active]
    out.update({
        "updated_age_h": age if age is not None else UNMEASURED,
        "rows": len(rows), "active_rows": len(active),
        "active_silent": sum(1 for h in ticks if h is not None and h > SILENT_TICK_H),
        "active_untimed": sum(1 for h in ticks if h is None),
        "rows_with_entry_24h": sum(1 for h in entries if h is not None and h <= 24),
        "rows_with_entry_7d": sum(1 for h in entries if h is not None and h <= 168),
    })
    if age is None:
        return {**out, "verdict": UNMEASURED, "why": "state file carries no updated_at"}
    if age > out["allowance_h"]:
        return {**out, "verdict": STALE,
                "why": f"updated {age:.1f}h ago, allowance {out['allowance_h']:.2f}h"}
    if out["active_silent"]:
        # The file moves while some clocks in it do not: the lane is stale for those clocks.
        return {**out, "verdict": STALE,
                "why": f"{out['active_silent']} active clock(s) not reached in "
                       f"{SILENT_TICK_H:.0f}h although the lane file is fresh"}
    return {**out, "verdict": FRESH, "why": ""}


def enrolment_census(now: datetime) -> tuple[dict[str, Any], str]:
    """The enrolment organ's own census: its artifact when it is fresh, else measured here."""
    doc = _read(ENROLMENT)
    age = _hours(now, doc.get("at")) if isinstance(doc, dict) else None
    if isinstance(doc, dict) and age is not None and age <= 2 * CYCLE_HOURS:
        return doc, f"reports/FORWARD_ENROLMENT.json ({age:.1f}h old)"
    try:
        from research import forward_enrolment as fe
        return fe.run(write=False, do_repair=False), (
            f"measured here: FORWARD_ENROLMENT.json is "
            f"{'absent' if age is None else f'{age:.1f}h old'}")
    except Exception as exc:
        return {}, f"{UNMEASURED}: forward_enrolment failed ({type(exc).__name__}: {exc})"


def coverage(census: dict[str, Any], farm_keys: set[str], now: datetime) -> dict[str, Any]:
    certs = [c for c in (census.get("certificates") or []) if isinstance(c, dict)]
    if not certs:
        return {"verdict": UNMEASURED, "why": "no certificate census"}
    in_lane = [c for c in certs if c.get("enrolled")]
    lane_less = [c for c in certs if not c.get("enrolled")]
    in_farm = [c for c in lane_less if str(c.get("key")) in farm_keys]
    nowhere = [c for c in lane_less if str(c.get("key")) not in farm_keys]
    overdue = [c for c in nowhere if isinstance(c.get("clockless_hours"), (int, float))
               and float(c["clockless_hours"]) > CYCLE_HOURS]
    blocked = [c for c in (census.get("blocked") or []) if isinstance(c, dict)]
    return {
        "certificates": len(certs), "in_promoting_lane": len(in_lane),
        "in_farm_only": len(in_farm), "in_no_lane": len(nowhere),
        "in_no_lane_over_one_cycle": len(overdue),
        "share_in_a_lane": round((len(in_lane) + len(in_farm)) / len(certs), 4),
        "share_in_promoting_lane": round(len(in_lane) / len(certs), 4),
        "blocked_in_lane": len(blocked),
        "blocked_by_reason": _count(str(c.get("blocker") or c.get("status"))[:80]
                                    for c in blocked),
        "no_lane": [{"key": c.get("key"), "family": c.get("family"),
                     "clockless_hours": c.get("clockless_hours"), "why": c.get("why")}
                    for c in sorted(nowhere, key=_clockless, reverse=True)][:200],
        "verdict": "RED" if overdue else "GREEN",
    }


def _clockless(c: dict[str, Any]) -> float:
    h = c.get("clockless_hours")
    return float(h) if isinstance(h, (int, float)) else 0.0


def _count(items: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def common_clock(docs: dict[str, Any], now: datetime) -> dict[str, Any]:
    """How many accruing clocks hold at least H days of forward history, per horizon H."""
    days: list[float] = []
    for doc in docs.values():
        for row in lane_rows(doc).values():
            if str(row.get("status") or "").upper() not in ACTIVE:
                continue
            h = _hours(now, row.get("forward_start") or row.get("enrolled_at"))
            if h is not None:
                days.append(h / 24.0)
    days.sort()
    if not days:
        return {"accruing_clocks": 0, "status": UNMEASURED}
    return {"accruing_clocks": len(days),
            "median_forward_days": round(days[len(days) // 2], 1),
            "max_forward_days": round(days[-1], 1),
            "clocks_with_at_least_days": {str(h): sum(1 for d in days if d >= h)
                                          for h in HORIZONS_D},
            "why": ("every accruing clock runs on one wall clock; the overlap any two share is "
                    "the younger one's history, so the count at H is the population an H-day "
                    "breadth or correlation estimate can use")}


def _running(script: str) -> bool:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return False
    name = Path(script).name
    for proc in psutil.process_iter(["cmdline"]):
        try:
            if any(name in str(part) for part in (proc.info.get("cmdline") or [])):
                return True
        except Exception:
            continue
    return False


def restart(name: str, spec: dict[str, Any], deadline: float) -> dict[str, Any]:
    script = spec.get("engine")
    if not script:
        return {"lane": name, "status": "NO_ENGINE"}
    if _running(str(script)):
        return {"lane": name, "status": "ALREADY_RUNNING",
                "why": "a process already runs this engine; a hang is stall_watch's to kill"}
    remaining = deadline - time.monotonic()
    if remaining < 60.0:
        return {"lane": name, "status": "SKIPPED_BUDGET", "why": f"{remaining:.0f}s left"}
    before = (_read(SHADOW / spec["state"]) or {}).get("updated_at")
    try:
        proc = subprocess.run([sys.executable, str(BASE / str(script))], cwd=str(BASE),
                              timeout=remaining, capture_output=True, text=True, check=False)
        rc: Any = proc.returncode
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        rc, tail = "TIMEOUT", []
    after = (_read(SHADOW / spec["state"]) or {}).get("updated_at")
    moved = bool(after) and after != before
    return {"lane": name, "status": "RESTARTED" if moved else "RESTART_DID_NOT_ADVANCE",
            "rc": rc, "updated_before": before, "updated_after": after, "tail": tail}


def run(*, budget_s: float = 900.0, repair: bool = True,
        out: Path | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, budget_s)
    now = _now()
    docs = {name: _read(SHADOW / spec["state"]) for name, spec in LANES.items()}
    lanes = [lane_verdict(n, LANES[n], docs[n], now) for n in LANES]
    census, census_source = enrolment_census(now)
    farm_keys = set(lane_rows(docs.get("farm")))
    cov = coverage(census, farm_keys, now)
    repairs: list[dict[str, Any]] = []
    if repair:
        for lane in lanes:
            if lane["verdict"] != STALE:
                continue
            if LANES[lane["lane"]].get("promoting"):
                # A PROMOTING LANE IS NEVER RESTARTED FROM HERE (audit on #487, 2026-10-29): its
                # engine is owned by its scheduled task (MT5-Shadow every 15 min, 2,700 s budget),
                # a restart inside this leg's 900 s would be killed partway, and "not running"
                # races that task. The lane is RED in this report and in the failure ledger;
                # killing a hung engine is stall_watch's.
                repairs.append({"lane": lane["lane"], "status": "REPORTED",
                                "why": "promoting lane: owned by its scheduled task and "
                                       "stall_watch, never restarted by this leg"})
                continue
            repairs.append(restart(lane["lane"], LANES[lane["lane"]], deadline))
        if repairs:
            now = _now()
            docs = {name: _read(SHADOW / spec["state"]) for name, spec in LANES.items()}
            lanes = [lane_verdict(n, LANES[n], docs[n], now) for n in LANES]
            cov = coverage(census, set(lane_rows(docs.get("farm"))), now)
    stale = [lane["lane"] for lane in lanes if lane["verdict"] == STALE]
    red = bool(stale) or cov.get("verdict") == "RED"
    doc: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"),
        "producer": "desks/mt5/research/forward_lane_fence.py",
        "verdict": "RED" if red else ("GREEN" if cov.get("verdict") == "GREEN" else UNMEASURED),
        "stale_lanes": stale, "lanes": lanes, "coverage": cov,
        "census_source": census_source, "repairs": repairs,
        "common_clock": common_clock({k: v for k, v in docs.items()
                                      if LANES[k]["promoting"] or k == "farm"}, now),
        "rule": ("principal 2026-10-13: every forward lane running, never stale; every "
                 "certificate in a forward lane. A farm clock carries no promotion authority; "
                 "the integrity door still decides entry to a promoting lane"),
    }
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--no-repair", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, repair=not args.no_repair, out=args.out)
    cov = doc["coverage"]
    print(f"forward_lane_fence: {doc['verdict']} stale={doc['stale_lanes']} "
          f"certs={cov.get('certificates')} lane={cov.get('in_promoting_lane')} "
          f"farm={cov.get('in_farm_only')} none={cov.get('in_no_lane')} "
          f"repairs={[r.get('status') for r in doc['repairs']]}")
    return 1 if doc["verdict"] == "RED" else 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
