"""The missed-growth ledger: what every rail cost, or saved, in forward log-wealth.

    OpportunityCost(rail) = E[log W without rail] - E[log W with rail]

THE ANTI-TIMID MECHANISM. Every veto, shrinkage, cap, gate and inertia threshold on the desk is
registered in `libs.portfolio.rails`; this measures each one from the ledgers the desk already
keeps and gives it a verdict:

    EARNS_ITS_PLACE   removing the rail would have cost robust forward E[log W]
    COSTS_GROWTH      the rail is reducing growth without proving itself
    NOT_BINDING       the rail did not fire in the window, so it cost nothing and saved nothing
    UNMEASURED        the ledger it needs does not exist on this host (said, never assumed)

A COSTS_GROWTH verdict on a TUNABLE rail moves its multiplier one step toward weaker inside the
rail's declared bounds (`data/rail_calibration.json`, read by the rail on its next pass); on a
binary rail it writes a `rail_review` task for the research queue. A rail is never strengthened
by this loop: the only direction the calibration moves on evidence is toward more growth, and a
rail that earns its place is left exactly as it is.

UNITS. Log-wealth per day, so vetoes (R avoided x heat per trade), inertia (turnover cost saved
minus growth forgone), curve gaps (growth at one heat minus another) and proof fallbacks
(dynamic minus baseline growth) are comparable and summable.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio.rails import CALIBRATION, RAILS, calibration  # noqa: E402

LEDGER = BASE / "data" / "missed_growth.jsonl"
OUT = BASE / "reports" / "MISSED_GROWTH.json"
ALLOC = BASE / "reports" / "pf_allocation.json"
PROOF = BASE / "reports" / "ALLOCATOR_PROOF.json"
FILTER_VALUE = BASE / "reports" / "FILTER_VALUE.json"
STATE_ADM = BASE / "reports" / "STATE_ADMISSION.json"
EARNS, COSTS, NOT_BINDING, UNMEASURED = ("EARNS_ITS_PLACE", "COSTS_GROWTH", "NOT_BINDING",
                                         "UNMEASURED")
MIN_N = 10
STEP = 0.10


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _curve(alloc: dict) -> dict[float, float]:
    try:
        return {float(h): float(g) for h, g in (alloc.get("heat") or {}).get("curve") or []}
    except (TypeError, ValueError):
        return {}


def _growth_at(curve: dict[float, float], heat: float) -> float | None:
    if not curve:
        return None
    h = min(curve, key=lambda x: abs(x - heat))
    return curve[h] if abs(h - heat) <= 0.05 else None


# --------------------------------------------------------------------------- measurements
def measure_veto(r, alloc: dict, fv: dict) -> dict[str, Any]:
    row = (fv.get("filters") or {}).get(r.name)
    if not row:
        return {"verdict": UNMEASURED, "why": "no replayed vetoes for this reason yet"}
    n = int(row.get("n_vetoed_and_triggered", 0))
    if n == 0:
        return {"verdict": NOT_BINDING, "n": 0}
    # R avoided per vetoed trade x the heat one trade carries = log-wealth saved per veto.
    q = float(np.mean(list((alloc.get("book") or {}).values()) or [0.0]))
    per_veto = float(row.get("mean_avoided_r", 0.0)) * q
    t = row.get("t")
    verdict = (EARNS if (row.get("verdict") == "EARNS_ITS_PLACE") else
               (COSTS if row.get("verdict") == "COSTS_EDGE" else UNMEASURED))
    return {"verdict": verdict, "n": n, "value_logw_per_veto": round(per_veto, 6),
            "avoided_r_total": row.get("filter_value_r"), "t": t}


def measure_inertia(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    nt = alloc.get("no_trade") or {}
    if not nt:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    cost = float(nt.get("cost", 0.0))
    benefit = float(nt.get("benefit_over_horizon", 0.0))
    horizon = float(nt.get("horizon_days", 1.0)) or 1.0
    if nt.get("verdict") == "REBALANCE":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    # Holding saved the turnover cost and forwent the growth: positive when the rail earned.
    return {"verdict": "SAMPLE", "value_logw_per_day": round((cost - benefit) / horizon, 8),
            "sample": True}


def measure_shrinkage(r, _alloc: dict, _fv: dict) -> dict[str, Any]:
    adm = _json(STATE_ADM)
    verdicts = adm.get("verdicts") or {}
    if not verdicts:
        return {"verdict": UNMEASURED, "why": "no STATE_ADMISSION.json"}
    admitted = {k: v for k, v in verdicts.items() if str(v.get("verdict", "")).startswith("ADMIT")}
    buried = [k for k, v in verdicts.items() if v.get("verdict") == "GRAVEYARD"]
    return {"verdict": (EARNS if admitted else NOT_BINDING),
            "admitted": {k: v.get("t_deflated", v.get("t")) for k, v in admitted.items()},
            "buried": buried,
            "why": "shrinkage is judged by the admission gauntlet: an admitted dimension "
                   "improved out-of-sample likelihood at k_state=40; a buried one is not used"}


def measure_bounds(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    fill = alloc.get("floor_fill") or {}
    if not alloc:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    relaxed = fill.get("relaxed")
    mine = {"per_sleeve_bounds": "drawdown_bound", "sleeve_share_cap": "share_cap",
            "family_cap": "family_cap"}[r.name]
    if not fill.get("needed"):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    if relaxed == mine or (relaxed == "proportional" and mine == "share_cap"):
        return {"verdict": "SAMPLE", "bound_when_filled": True,
                "value_logw_per_day": -abs(float(fill.get("growth_gap", 0.0))), "sample": True,
                "why": "the floor could not be funded until this bound was relaxed"}
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}


def measure_ceiling(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "ceiling":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    curve = _curve(alloc)
    g_free = _growth_at(curve, float(heat.get("free_optimum", 0.0)))
    g_cap = _growth_at(curve, float(heat.get("hard_ceiling", 0.0)))
    if g_free is None or g_cap is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the free optimum"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_cap - g_free, 8), "sample": True}


def measure_floor(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "mandate":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    curve = _curve(alloc)
    g_free = _growth_at(curve, float(heat.get("free_optimum", 0.0)))
    g_floor = _growth_at(curve, float(heat.get("floor", 0.0)))
    if g_free is None or g_floor is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the free optimum"}
    # The mandate forces heat ABOVE the optimum: positive when the curve's flat top makes that
    # free, negative when it costs. Reported, never tuned: it is the principal's order.
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_floor - g_free, 8),
            "sample": True, "principal_order": True}


def measure_proof(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    proof = alloc.get("proof") or {}
    scores = proof.get("scores") or {}
    if not proof:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if proof.get("passed"):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    dyn = scores.get("dynamic")
    best = scores.get(str(proof.get("best_baseline")))
    if dyn is None or best is None:
        return {"verdict": UNMEASURED, "why": "proof scores not carried on the artifact"}
    # The floor was sized with the baseline: the rail cost (dynamic - baseline) if the dynamic
    # book was genuinely better and only missed the margin, and saved the reverse.
    return {"verdict": "SAMPLE", "value_logw_per_day": round(float(best) - float(dyn), 8),
            "sample": True}


def measure_ramp(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED,
            "why": "needs the live ledger's deployed fractions per sleeve (box only); the ramp "
                   "no longer applies to allocator-book sleeves"}


def measure_fade(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED, "why": "needs live fills of faded vs unfaded sleeves (box)"}


def measure_cost_stress(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0,
            "why": "stressed costs are validation-only; live allocation charges the measured "
                   "per-trade cost (SleeveEvidence.cost_r) with the world's cost uncertainty draw"}


def measure_factor_floor(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED, "why": "needs the live ledger's factor exposures (box)"}


def measure_ruin_guard(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    note = str((alloc.get("growth") or {}).get("annual_growth_pct", ""))
    heat = alloc.get("heat") or {}
    if heat.get("binding") == "catastrophe":
        return {"verdict": "SAMPLE", "value_logw_per_day": 0.0, "fired": True, "sample": True,
                "why": "the objective's own constraint; measured, never tuned"}
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True, "note": note}


MEASURES = {name: fn for name, fn in globals().items() if name.startswith("measure_")}


# --------------------------------------------------------------------------- the ledger
def _rows() -> list[dict]:
    try:
        return [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _verdict_from_samples(samples: list[float]) -> tuple[str, dict[str, Any]]:
    arr = np.asarray(samples, dtype=float)
    if arr.size < MIN_N:
        return UNMEASURED, {"n": int(arr.size), "why": f"under {MIN_N} daily samples"}
    if np.all(arr == 0.0):
        return NOT_BINDING, {"n": int(arr.size), "mean_logw_per_day": 0.0}
    se = float(arr.std(ddof=1) / math.sqrt(arr.size)) if arr.size > 1 else 0.0
    t = float(arr.mean() / se) if se > 0 else (float("inf") if arr.mean() != 0 else 0.0)
    v = EARNS if t > 2.0 else (COSTS if t < -2.0 else UNMEASURED)
    return v, {"n": int(arr.size), "mean_logw_per_day": round(float(arr.mean()), 8),
               "t": round(t, 2), "annualised_logw": round(float(arr.mean()) * 252.0, 6)}


def run(write: bool = True, today: str | None = None) -> dict[str, Any]:
    alloc = _json(ALLOC)
    fv = _json(FILTER_VALUE)
    day = today or datetime.now(tz=UTC).date().isoformat()
    # 1. today's samples, appended once per day per rail
    existing = _rows()
    have_today = {(r.get("rail"), r.get("day")) for r in existing}
    new = []
    live: dict[str, dict[str, Any]] = {}
    for r in RAILS:
        m = MEASURES[r.measure](r, alloc, fv)
        live[r.name] = m
        if m.get("sample") and (r.name, day) not in have_today:
            new.append({"day": day, "rail": r.name, "value": float(m.get("value_logw_per_day", 0.0)),
                        "at": datetime.now(tz=UTC).isoformat()})
    if new and write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for row in new:
                fh.write(json.dumps(row) + "\n")
    rows = existing + new
    # 2. verdicts from the accumulated samples (or the direct measurement for vetoes)
    verdicts: dict[str, dict[str, Any]] = {}
    for r in RAILS:
        m = live[r.name]
        if r.measure == "measure_veto" or r.measure == "measure_shrinkage":
            verdicts[r.name] = {"kind": r.kind, **m}
            continue
        samples = [float(x["value"]) for x in rows if x.get("rail") == r.name]
        if m.get("verdict") == UNMEASURED and not samples:
            verdicts[r.name] = {"kind": r.kind, **m}
            continue
        v, stats = _verdict_from_samples(samples)
        verdicts[r.name] = {"kind": r.kind, "verdict": v, **stats,
                            "today": {k: val for k, val in m.items() if k != "sample"}}
    # 3. calibration: weaken tunable rails that cost growth, within bounds; never strengthen.
    cal = calibration()
    changed = []
    tasks = []
    for r in RAILS:
        v = verdicts[r.name].get("verdict")
        if v != COSTS:
            continue
        if r.tunable:
            cur = float(cal.get(r.name, 1.0))
            nxt = max(r.lo, cur * (1.0 - STEP))
            if nxt < cur - 1e-9:
                cal[r.name] = round(nxt, 4)
                changed.append({"rail": r.name, "from": cur, "to": round(nxt, 4),
                                "means": r.weaken_means})
        else:
            tasks.append({"source": "missed_growth", "kind": "rail_review",
                          "title": f"Rail {r.name} costs growth: {verdicts[r.name]}",
                          "description": (f"The {r.kind} rail {r.name} ({r.where}) has a "
                                          f"measured opportunity cost in forward log-wealth. "
                                          "Under the growth governance a rail that does not "
                                          "prove it raises robust forward E[log W] is weakened "
                                          "or removed. Propose the removal or the continuous "
                                          "replacement, with the evidence."),
                          "rail": r.name, "status": None, "consumer": "principal / research"})
    if write and changed:
        CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
        CALIBRATION.write_text(json.dumps({"generated_utc": datetime.now(tz=UTC).isoformat(),
                                           "multipliers": cal, "changes": changed}, indent=1),
                               "utf-8")
    if write and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="missed_growth")
        except Exception:
            pass
    aggression = alloc.get("aggression") or {}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "day": day,
           "ledger_rows": len(rows), "new_samples": len(new), "rails": verdicts,
           "costs_growth": sorted(k for k, v in verdicts.items() if v.get("verdict") == COSTS),
           "earns": sorted(k for k, v in verdicts.items() if v.get("verdict") == EARNS),
           "unmeasured": sorted(k for k, v in verdicts.items() if v.get("verdict") == UNMEASURED),
           "calibration": cal, "calibration_changes": changed, "review_tasks": len(tasks),
           "aggression_verdict": aggression.get("verdict"),
           "unused_upside_heat": aggression.get("unused_upside_heat"),
           "rule": ("OpportunityCost(rail) = E[log W without] - E[log W with]; a rail that "
                    "COSTS_GROWTH is weakened within its bounds (tunable) or queued for review "
                    "(binary); a rail is never strengthened by this loop")}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    d = run(write=not a.no_write)
    print(f"MISSED GROWTH  {d['ledger_rows']} ledger rows (+{d['new_samples']} today)  "
          f"costs={d['costs_growth']} earns={d['earns']}")
    for name, v in d["rails"].items():
        extra = "".join(f" {k}={v[k]}" for k in ("n", "t", "mean_logw_per_day") if k in v)
        print(f"  {name:26s} {v.get('kind', ''):9s} {v.get('verdict', ''):16s}{extra}")
    if d["calibration_changes"]:
        print(f"  calibration: {d['calibration_changes']}")
    if d.get("aggression_verdict"):
        print(f"  aggression: {d['aggression_verdict']} unused_upside={d['unused_upside_heat']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
