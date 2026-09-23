"""Bring a hibernated sleeve back when ITS HABITAT returns, not when its P&L happens to.

`regime_monitor` hibernates a sleeve when live expectancy falls below -0.10R over 90 trades and
wakes it when SHADOW expectancy recovers above -0.05R. That is a P&L thermostat: it cannot tell a
sleeve whose edge is gone from one whose market went away for a season. Brown said publicly that
Renaissance kept cold signals because they could return; this is what "return" means.

A HABITAT IS A STATE BUCKET THE SLEEVE PAID IN -- from the same point-in-time labelling
`regime_coverage` uses. Each day, for each hibernated sleeve:

    RESURRECT   habitat present AND recent shadow expectancy back above cost
    WATCH       habitat present, shadow not yet confirming -- keep clocking
    DORMANT     habitat absent -- the sleeve is not wrong, its market is elsewhere
    DEAD        habitat present >= DEAD_AFTER_DAYS and shadow still losing -- the edge did not
                come back when its conditions did, which is what decay actually looks like

RESURRECT is a recommendation into the existing wake path, never an arming: the same hysteresis
and the same human arm apply as to any other wake.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import Trade  # noqa: E402

OUT = BASE / "reports" / "RESURRECTION.json"
REGIME_STATE = BASE / "data" / "regime_state.json"
STATE_VECTOR = BASE / "data" / "state_vector.json"
K_STATE = 40.0
MIN_N = 8
HABITAT_R = 0.05
RECENT = 30
DEAD_AFTER_DAYS = 60
RESURRECT, WATCH, DORMANT, DEAD = "RESURRECT", "WATCH", "DORMANT", "DEAD"


def hibernated() -> dict[str, dict]:
    try:
        doc = json.loads(REGIME_STATE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in (doc.get("sleeves") or {}).items()
            if isinstance(v, dict) and v.get("flag") == "hibernate"}


def habitats(trades: list[Trade], dims: tuple[str, ...]) -> dict[str, dict[str, dict]]:
    """sleeve -> {bucket: {n, shrunk_r}} for the buckets where the sleeve paid."""
    by_sleeve: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        by_sleeve[t.sleeve].append(t.r)
    mean = {k: float(np.mean(v)) for k, v in by_sleeve.items()}
    cell: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in trades:
        if any(not t.buckets.get(d) for d in dims):
            continue
        cell[t.sleeve]["|".join(f"{d}={t.buckets[d]}" for d in dims)].append(t.r)
    out: dict[str, dict[str, dict]] = {}
    for sleeve, buckets in cell.items():
        for key, rs in buckets.items():
            n = len(rs)
            if n < MIN_N:
                continue
            lam = n / (n + K_STATE)
            cond = lam * float(np.mean(rs)) + (1.0 - lam) * mean[sleeve]
            if cond >= HABITAT_R:
                out.setdefault(sleeve, {})[key] = {"n": n, "shrunk_r": round(cond, 4)}
    return out


def current_bucket(dims: tuple[str, ...]) -> str | None:
    try:
        from libs.regime.state_vector import StateVector
        sv = StateVector.from_dict(json.loads(STATE_VECTOR.read_text("utf-8")))
    except Exception:                                            # noqa: BLE001
        return None
    parts = []
    for d in dims:
        v = {"global": (sv.global_state.top if sv.global_state else ""),
             "session": str(sv.session.get("phase") or ""),
             "event": str(sv.event.get("phase") or ""),
             "weekday": datetime.now(tz=UTC).strftime("%a")}.get(d, "")
        if not v:
            return None
        parts.append(f"{d}={v}")
    return "|".join(parts)


def judge(sleeve: str, hab: dict[str, dict], now_bucket: str | None,
          recent_shadow: list[float], cost_r: float, days_habitat_present: int) -> dict:
    present = bool(now_bucket and now_bucket in hab)
    recent = recent_shadow[-RECENT:]
    exp = float(np.mean(recent)) if recent else float("nan")
    if not hab:
        verdict, why = DORMANT, "no habitat could be measured: never paid in any labelled bucket"
    elif not present:
        verdict, why = DORMANT, f"habitat absent: now in {now_bucket or 'UNKNOWN'}"
    elif len(recent) >= MIN_N and exp > cost_r:
        verdict, why = RESURRECT, (f"habitat present and shadow expectancy {exp:+.3f}R over "
                                   f"{len(recent)} trades clears cost {cost_r:.3f}R")
    elif days_habitat_present >= DEAD_AFTER_DAYS:
        verdict, why = DEAD, (f"habitat present {days_habitat_present}d and shadow still "
                              f"{exp:+.3f}R: the edge did not return with its conditions")
    else:
        verdict, why = WATCH, (f"habitat present; shadow {exp:+.3f}R over {len(recent)} trades "
                               "not yet confirming")
    return {"sleeve": sleeve, "verdict": verdict, "why": why, "habitat": hab,
            "now": now_bucket, "recent_shadow_n": len(recent),
            "recent_shadow_r": (round(exp, 4) if recent else None),
            "days_habitat_present": days_habitat_present}


def run() -> dict:
    from research.regime_coverage import DIMENSIONS, _admitted, _label
    from research.state_admission_run import load_trades

    admitted = _admitted()
    dims = tuple(d for d in DIMENSIONS if d in admitted)
    trades = load_trades("shadow")
    labelled, gaps = _label(trades, dims)
    used = tuple(d for d in ("global",) + dims if d not in gaps)
    hab = habitats(labelled, used)
    now_bucket = current_bucket(used)
    hib = hibernated()
    prev: dict[str, dict] = {}
    try:
        prev = {r["sleeve"]: r for r in json.loads(OUT.read_text("utf-8")).get("verdicts", [])}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    shadow_by_sleeve: dict[str, list[float]] = defaultdict(list)
    for t in sorted(trades, key=lambda x: x.when):
        shadow_by_sleeve[t.sleeve].append(t.r)

    verdicts = []
    for sleeve in sorted(hib):
        key = sleeve.replace("|", "_")
        h = hab.get(key) or hab.get(sleeve) or {}
        present_days = 0
        if now_bucket and now_bucket in h:
            present_days = int((prev.get(sleeve) or {}).get("days_habitat_present", 0)) + 1
        verdicts.append(judge(sleeve, h, now_bucket,
                              shadow_by_sleeve.get(key) or shadow_by_sleeve.get(sleeve) or [],
                              cost_r=0.0, days_habitat_present=present_days))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "dimensions": list(used),
           "now": now_bucket, "gaps": gaps, "n_hibernated": len(hib),
           "n_with_habitat": sum(1 for v in verdicts if v["habitat"]), "verdicts": verdicts,
           "resurrect": [v["sleeve"] for v in verdicts if v["verdict"] == RESURRECT],
           "dead": [v["sleeve"] for v in verdicts if v["verdict"] == DEAD]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    doc = run()
    print(f"RESURRECTION  now={doc['now']}  hibernated={doc['n_hibernated']} "
          f"with_habitat={doc['n_with_habitat']}")
    for v in doc["verdicts"]:
        print(f"  {v['sleeve']:40s} {v['verdict']:10s} {v['why']}")
    for g, why in doc["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
