"""The revival engine: an old alpha may have died of cost, state, venue or sample -- not mechanism.

    P(revival | new data, new state)  ~  P(survivor | features, now) x (1 - P(same death))

For every buried REGION in the hypothesis graph (symbol x family x parameter region), the
engine asks what killed it (the graveyard model's failure class), whether the condition that
killed it has changed -- more history since burial (LOW_SAMPLE), a lower measured cost
(COST_DEATH, from the fill surface / contract terms), a shifted correlation structure or a new
state bucket the coverage map opened (STATE_FRAGILE, via the drift monitor and the coverage
report) -- and, when it has, writes a `revival` task to the deepening queue naming the region,
the death, and what changed. Nothing is re-run wholesale: the meta-model's likelihood decides
what is worth a second look, and the queue's VOI order decides when.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = _DESK / "reports" / "REVIVAL.json"
MAX_TASKS = 25
MIN_AGE_DAYS = 30


def _json(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _what_changed() -> dict[str, Any]:
    """The conditions a revival can cite: drift, new coverage buckets, a fitted fill surface."""
    drift = _json(_DESK / "reports" / "DRIFT.json")
    cov = _json(_DESK / "reports" / "REGIME_COVERAGE.json")
    fill = _json(_DESK / "reports" / "FILL_SURFACE.json")
    return {"structure_shifted": (drift.get("verdict") in ("DRIFT_AHEAD", "STRUCTURE_SHIFTED")),
            "new_buckets": int(cov.get("n_buckets", 0)),
            "fill_surface_fitted": fill.get("n_fills", 0) >= 30,
            "today": datetime.now(tz=UTC)}


def candidates(graph_rows: list[dict[str, Any]], gm: Any, changed: dict[str, Any]) -> list[dict]:
    latest: dict[str, dict[str, Any]] = {}
    for r in graph_rows:
        if isinstance(r, dict) and r.get("id"):
            latest[str(r["id"])] = r
    out = []
    for r in latest.values():
        if r.get("fate") not in ("FAILED", "BURIED"):
            continue
        try:
            at = datetime.fromisoformat(str(r.get("at")))
            age = (changed["today"] - (at if at.tzinfo else at.replace(tzinfo=UTC))).days
        except (TypeError, ValueError):
            age = 0
        if age < MIN_AGE_DAYS:
            continue
        pm = gm.premortem(r) if gm is not None else {"failure_class": "UNKNOWN",
                                                    "p_survivor": None}
        cls = str(pm.get("failure_class"))
        reason = None
        if cls == "LOW_SAMPLE" and age >= 90:
            reason = f"{age} days of new history since burial"
        elif cls == "COST_DEATH" and changed["fill_surface_fitted"]:
            reason = "the measured fill surface replaced the modelled cost"
        elif cls == "STATE_FRAGILE" and (changed["structure_shifted"] or changed["new_buckets"]):
            reason = "the correlation structure shifted or new state buckets exist"
        elif cls == "SELECTION_BIAS" and age >= 180:
            reason = "half a year of out-of-sample bars now exists for a fresh, pre-registered test"
        if reason is None:
            continue
        p = pm.get("p_survivor")
        out.append({"region": r.get("region"), "symbol": r.get("symbol"),
                    "family": r.get("family"), "params": r.get("params"),
                    "died_of": cls, "age_days": age, "p_survivor": p, "why_now": reason})
    out.sort(key=lambda x: -(float(x["p_survivor"] or 0.0)))
    return out[:MAX_TASKS]


def run(write: bool = True) -> dict[str, Any]:
    try:
        from libs.research.graveyard_model import GraveyardModel
        from libs.research.hypothesis_graph import Graph
        rows = Graph().rows()
        gm = GraveyardModel().fit(rows) if rows else None
    except Exception as exc:                                     # noqa: BLE001
        rows, gm = [], None
        err = f"{type(exc).__name__}: {exc}"
    else:
        err = ""
    changed = _what_changed()
    cands = candidates(rows, gm, changed) if rows else []
    tasks = [{"source": "revival_engine", "kind": "revival",
              "title": f"Revive {c['symbol']}.{c['family']}? died of {c['died_of']}: {c['why_now']}",
              "description": (f"Region {c['region']} was buried {c['age_days']} days ago "
                              f"(class {c['died_of']}). What changed: {c['why_now']}. Re-test "
                              "as a NEW pre-registered cell with its lifetime multiplicity "
                              "charge; do not re-parameterise."),
              "symbols": [c["symbol"]], "family": c["family"], "params": c["params"],
              "status": None, "consumer": "proposers / gauntlet"} for c in cands]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "graph_rows": len(rows),
           "changed": {k: v for k, v in changed.items() if k != "today"},
           "candidates": cands, "n_tasks": len(tasks), "error": err}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        if tasks:
            try:
                from research.regime_coverage import _merge_into_queue
                _merge_into_queue(tasks, source="revival_engine")
            except Exception:                                    # noqa: BLE001
                pass
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"REVIVAL  {d['graph_rows']} graph rows, {d['n_tasks']} revival tasks; changed={d['changed']}")
    for c in d["candidates"][:8]:
        print(f"  {c['symbol']}.{c['family']}  died_of={c['died_of']} age={c['age_days']}d "
              f"p={c['p_survivor']}  {c['why_now']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
