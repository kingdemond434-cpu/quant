"""CONVERSION ENGINE -- turn already-mined data into RUNNING experiments, not a list nobody opens.

MY OWN FAILURE, ONE HOUR AFTER SHIPPING THE DETECTOR FOR IT. I generated conversion_queue.json
from /tmp, wired nothing, and reported conversion "maximised". Nothing read it, nothing
regenerated it, and its producer was not even a script. That is precisely the INERT class
module_justification measures -- 90 of 243 modules -- and I added one to the pile while claiming
the opposite.

A queue nobody consumes is a list. Utilisation means something DOWNSTREAM CHANGES.

WHAT THIS DOES, AND WHERE IT LANDS:
  1 regenerates the conversion queue every cycle from the live blind-spot scan
  2 ranks by CONVERSION COST -- not guessed alpha. An unread field on a VERIFIED live source is
    the cheapest experiment that exists: zero acquisition, known provenance, history already
    accumulating.
  3 EMITS the top candidates into data/research_cio.json's schedule, so they compete directly
    against the 447 enumerated constructions in the one queue the desk actually reads.

MINING IS NEVER TOUCHED (principal constraint, honoured literally). Nothing here throttles a
collector, prunes a field, narrows a universe or drops a row. It raises utilisation of what mining
already produced, and if the two ever conflict, mining wins.

STAGE-A ONLY. A converted blind spot is a QUESTION, not an edge. It earns a screen, never capital.
"""
from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/conversion_queue.json"
CIO = ROOT / "data/research_cio.json"


def _j(p, d=None):
    try:
        return json.loads((ROOT / p).read_text("utf-8"))
    except Exception:  # blind-except intentional (BLE001)
        return d


def main() -> None:
    bs = _j("data/blindspot_max.json", {}) or {}
    unread = (_j("data/unobserved_observables.json", {}) or {}).get("fields", [])
    gate = {k: v.get("verdict") for k, v in
            (_j("data/measurement_gate.json", {}) or {}).get("datasets", {}).items()}
    vit = {c["source"]: c for c in (_j("data/data_vitals.json", {}) or {}).get("collectors", [])}

    cands = []
    for r in unread:
        src = r["file"]
        live = "OK" in str(vit.get(src, {}).get("action", ""))
        ver = gate.get(src) == "VERIFIED"
        cands.append({"kind": "unread_field", "target": f"{src}:{r['field']}",
                      "cost": round(1.0 + (0 if ver else 0.5) + (0 if live else 0.5), 2),
                      "verified": ver, "live": live,
                      "why": "collected, never referenced -- acquisition cost already paid"})
    for pair in bs.get("uncrossed_pairs", []):
        a, b = pair[0], pair[1]
        va, vb = gate.get(a) == "VERIFIED", gate.get(b) == "VERIFIED"
        cands.append({"kind": "uncrossed_pair", "target": f"{a} x {b}",
                      "cost": round(2.0 + (0 if va else 0.5) + (0 if vb else 0.5), 2),
                      "verified": va and vb, "live": None,
                      "why": "interaction never examined -- fusion is where weak signals combine"})
    for e in bs.get("unmodelled_entities", []):
        cands.append({"kind": "unmodelled_entity", "target": f"{e['file']}:{e['entity']}",
                      "cost": 1.5, "verified": gate.get(e["file"]) == "VERIFIED", "live": None,
                      "rows": e.get("rows"),
                      "why": "present in our data, named nowhere in our code"})

    cands.sort(key=lambda c: (c["cost"], not c["verified"]))
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(cands),
                               "queue": cands}, indent=1), "utf-8")

    # ---- THE PART THAT MAKES IT UTILISATION RATHER THAN A LIST ----
    cio = _j("data/research_cio.json", {}) or {}
    sched = cio.get("schedule", [])
    injected = 0
    for c in cands[:40]:
        sched.append({"mechanism": "M_CONVERSION", "name": c["target"],
                      "prior": round(1.0 / c["cost"], 3), "advantage": 1.0,
                      "sched_score": round(1.0 / c["cost"], 3),
                      "origin": "conversion_engine", "why": c["why"]})
        injected += 1
    sched.sort(key=lambda x: -x.get("sched_score", 0))
    cio["schedule"] = sched[:120]
    cio["conversion_injected"] = injected
    CIO.write_text(json.dumps(cio, indent=1), "utf-8")

    kinds = {}
    for c in cands:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("=== CONVERSION ENGINE -- already-mined data into running experiments ===")
    print("    a queue nobody consumes is a list; utilisation means something downstream changes\n")
    print(f"  {len(cands)} candidates  {kinds}")
    print(f"  {injected} injected into the research_cio schedule -- they now compete directly")
    print("  against the enumerated construction space in the one queue the desk reads.\n")
    print(f"  {'cost':>5}  {'kind':<20}candidate")
    for c in cands[:10]:
        print(f"  {c['cost']:>5}  {c['kind']:<20}{c['target'][:56]}")
    print("\n  MINING UNTOUCHED. Nothing throttled, pruned, narrowed or dropped -- this only")
    print("  raises utilisation of what mining already produced. If the two ever conflict,")
    print("  mining wins.")
    print("  STAGE-A ONLY: a converted blind spot is a QUESTION, not an edge. It earns a screen,")
    print("  never capital.")
    print(f"\n  -> {OUT}\n  -> {CIO} (schedule now {len(cio['schedule'])} items)")


if __name__ == "__main__":
    main()
