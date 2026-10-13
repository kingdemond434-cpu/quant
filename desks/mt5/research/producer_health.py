"""PRODUCER HEALTH: every lane LIVE or STALE, WIRED or UNWIRED, its yield against its peers, and
an upgrade for the bottom quartile. Hourly, no LLM.

    "hourly make sure all sources and producers produce nth is stale n unwired n etc thats also
     part of maximising discovery n if one isnt providing s much certis n as others u maximise
     them so they do etc"                                         -- the principal, 2026-10-13

IT OPENS NO SECOND LANE. The roster and every number are read from organs that already measure
them, and joined per lane:

    roster, cells, judged, compute, orthogonality   reports/PRODUCER_YIELD.json["cells_owed"]
        (scripts/check_producer_yield.py, whose roster is PRODUCTIVITY_CENSUS -- itself derived
        from the component registry and the registry's own generators; never a hand list)
    seat output over its window                     reports/PRODUCER_YIELD.json["producers"]
    clock and consumer                              the clock on the cells_owed row, and
                                                    reports/dead_architecture.json
                                                    (scripts/check_dead_architecture.py)
    certificates per producer                       data/certificate_provenance.json (the
                                                    first claimant the provenance law credits)

PER LANE:
  (a) LIVE if it emitted a cell in the yield window (24h) or donated seat rows in the seat window
      (3d), or is a declared exemption that spent compute in the window; else STALE.
  (b) WIRED if it has a clock AND its output reaches the compiler or the docket (cells reaching
      the judge, or seat rows the compiler reads) AND something consumes it (the judge/compiler,
      or a dead-architecture consumer); else UNWIRED, with every missing link named.
  (c) yield: unique cells/h, cells to the judge/h, certificates, and incremental k_eff per
      compute-hour (the leave-one-out effective-rank drop `check_producer_yield` measures, over
      the compute hours the ledger attributes), each against the median of its LIVE peers.
  (d) the BOTTOM QUARTILE of LIVE lanes by that yield, plus every STALE or UNWIRED lane that has a
      clock, gets an automatic UPGRADE action: REPAIR (stale on a clock), WIRE (no clock, no
      reach, or no consumer), CONVERT (it produces, but nothing reaches the judge), MUTATE
      (cells collapse to a few uniques), WIDEN (no orthogonality added: new queries / regions /
      timeframes), or BUDGET_SHIFT (raise the top-quartile peer of
      the same structure). The actions reach `frontier_ceo` as docket proposals, which is the
      desk's existing implement-and-measure loop.

NEVER CUT ANY PRODUCER BELOW ITS CURRENT THROUGHPUT. Every action is additive: a budget shift
RAISES the winning structure and leaves the loser exactly where it is (GROWTH_GOVERNANCE).

THE RATCHET, and why the fence fails on it rather than on the raw count. The roster carries every
sub-source a country pack or playbook declares, most of which have never run. A fence on the raw
STALE count would be red on its first pass and switched off inside a week. So the counts are
carried as a ratchet that may only FALL, and a lane that was LIVE (or WIRED) at the previous
reading and is not now is a REGRESSION -- both fail `scripts/check_producer_health.py` loudly,
with the names. The standing backlog is published in full every hour.

    python desks/mt5/research/producer_health.py          # measure + write the report
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]

REPORTS = BASE / "reports"
OUT = REPORTS / "PRODUCER_HEALTH.json"
PRODUCER_YIELD = REPORTS / "PRODUCER_YIELD.json"
DEAD_ARCH = REPORTS / "dead_architecture.json"
PROVENANCE = BASE / "data" / "certificate_provenance.json"

UNMEASURED = "UNMEASURED"
LIVE, STALE, WIRED, UNWIRED = "LIVE", "STALE", "WIRED", "UNWIRED"
#: Bottom-quartile actions published per pass (the full counts are always published).
MAX_ACTIONS = 200
#: A lane whose unique cells are below this share of its emitted cells is collapsing onto copies.
COLLAPSE_RATIO = 0.2


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rel(p: Path) -> str:
    return p.relative_to(BASE).as_posix() if p.is_relative_to(BASE) else str(p)


def base_name(key: str) -> str:
    """`miner:qd_frontier:explorer` -> `qd_frontier`; `seat:asia` -> `asia`."""
    k = str(key)
    for pre in ("miner:", "seat:", "fence:", "sandbox:cell:", "sandbox:"):
        if k.startswith(pre):
            k = k[len(pre):]
            break
    return k.split(":", 1)[0]


def structure(key: str) -> str:
    """The lane's STRUCTURE -- the class it competes with: the key's first segment."""
    return str(key).split(":", 1)[0]


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _certs_by_producer(path: Path | None = None) -> dict[str, int]:
    doc = _read(path or PROVENANCE)
    out: Counter[str] = Counter()
    for rec in ((doc or {}).get("records") or {}).values():
        if isinstance(rec, dict) and rec.get("producer"):
            out[base_name(str(rec["producer"]))] += 1
    return dict(out)


def _dead_arch_by_stem(path: Path | None = None) -> dict[str, str]:
    doc = _read(path or DEAD_ARCH)
    out: dict[str, str] = {}
    for p, row in ((doc or {}).get("organs") or {}).items():
        if isinstance(row, dict):
            out.setdefault(Path(str(p)).stem, str(row.get("verdict") or ""))
    return out


def _pct_rank(values: list[float], v: float) -> float:
    if not values:
        return 0.5
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return (below + 0.5 * equal) / len(values)


def classify(row: Mapping[str, Any], seat_rows: int | None, dead: Mapping[str, str],
             certs: int) -> dict[str, Any]:
    emitted = _num(row.get("cells_emitted_per_hour")) or 0.0
    unique = _num(row.get("unique_cells_per_hour")) or 0.0
    judged = _num(row.get("cells_to_judge_per_hour")) or 0.0
    compute = _num(row.get("compute_hours_window7d")) or 0.0
    orth = _num(row.get("orthogonality_added")) or 0.0
    declared = row.get("declared") if isinstance(row.get("declared"), dict) else None
    exempt = bool(declared and declared.get("kind") == "EXEMPTION")
    live = emitted > 0 or bool(seat_rows) or (exempt and compute > 0)
    clock = row.get("clock")
    reaches = judged > 0 or bool(seat_rows) or exempt
    da = dead.get(base_name(str(row.get("key") or row.get("producer") or "")), "")
    consumed = reaches or da == "LIVE"
    missing = [m for m, ok in (("no_clock", bool(clock)),
                               ("output_never_reaches_compiler_or_docket", reaches),
                               ("no_consumer", consumed)) if not ok]
    keff_h = (orth / (compute / 7.0)) if compute > 0 else None
    return {
        "lane": str(row.get("key") or row.get("producer")), "structure": structure(
            str(row.get("key") or "")), "clock": clock,
        "live": LIVE if live else STALE, "wired": WIRED if not missing else UNWIRED,
        "unwired_because": missing, "dead_architecture": da or None,
        "cells_emitted_per_hour": emitted, "unique_cells_per_hour": unique,
        "cells_to_judge_per_hour": judged, "certificates": certs,
        "orthogonality_added": orth, "compute_hours_7d": compute,
        "keff_per_compute_hour": round(keff_h, 6) if keff_h is not None else UNMEASURED,
        "seat_rows_in_window": seat_rows, "declared_exemption": exempt,
    }


def _action(lane: dict[str, Any], winners: Mapping[str, str]) -> dict[str, Any]:
    """The upgrade for one lane -- always additive, never a cut."""
    name = lane["lane"]
    if lane["live"] == STALE and lane["clock"]:
        kind, what = "REPAIR", (f"{name} is on a clock ({lane['clock']}) and produced nothing in "
                                f"its window: read its last run's error and fix the input")
    elif lane["wired"] == UNWIRED:
        kind, what = "WIRE", (f"{name}: " + ", ".join(lane["unwired_because"]) +
                              " -- give it a clock and a path into the compiler/docket")
    elif lane["cells_to_judge_per_hour"] <= 0 and (lane["seat_rows_in_window"]
                                                  or lane["cells_emitted_per_hour"] > 0):
        kind, what = "CONVERT", (f"{name} produces ({lane['seat_rows_in_window'] or 0} seat rows, "
                                 f"{lane['cells_emitted_per_hour']:.1f} cells/h) but none reach "
                                 f"the judge: donate structured hypothesis rows (family + "
                                 f"symbols) the compiler builds, and fix what it sets aside")
    elif (lane["cells_emitted_per_hour"] > 0
          and lane["unique_cells_per_hour"] < COLLAPSE_RATIO * lane["cells_emitted_per_hour"]):
        kind, what = "MUTATE", (f"{name} collapses {lane['cells_emitted_per_hour']:.1f}/h to "
                                f"{lane['unique_cells_per_hour']:.1f} unique: mutate its "
                                f"parameter grammar toward unseen mechanisms")
    elif lane["orthogonality_added"] <= 0:
        kind, what = "WIDEN", (f"{name} adds no orthogonality: new queries, regions and "
                               f"timeframes (point it at the breadth enforcer's frontier)")
    else:
        kind, what = "BUDGET_SHIFT", f"{name} trails its peers on every measured yield"
    win = winners.get(lane["structure"])
    out = {"lane": name, "action": kind, "what": what, "never_cut": True}
    if win and win != name:
        out["raise_winner"] = win
        out["what"] += (f"; raise the winning {lane['structure']} structure ({win}) -- additive, "
                        f"{name} keeps its current throughput")
    return out


def build(now: datetime | None = None, *, previous: Mapping[str, Any] | None = None
          ) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    py = _read(PRODUCER_YIELD)
    co = (py or {}).get("cells_owed") if isinstance(py, dict) else None
    rows = (co or {}).get("producers") if isinstance(co, dict) else None
    doc: dict[str, Any] = {"generated_utc": at.isoformat(timespec="seconds"),
                           "sources": {"producer_yield": _rel(PRODUCER_YIELD),
                                       "dead_architecture": _rel(DEAD_ARCH),
                                       "certificates": _rel(PROVENANCE)}}
    if not isinstance(rows, list) or not rows:
        doc.update(verdict=UNMEASURED, why="PRODUCER_YIELD.json absent or has no cells_owed roster")
        return doc
    doc["sources"]["producer_yield_at"] = py.get("generated_utc")
    seats: dict[str, int] = {}
    for r in (py.get("producers") or []):
        if isinstance(r, dict) and r.get("producer"):
            seats[base_name(str(r["producer"]))] = int(r.get("rows_in_window") or 0)
    dead = _dead_arch_by_stem()
    certs = _certs_by_producer()
    lanes = [classify(r, seats.get(base_name(str(r.get("key") or r.get("producer") or ""))),
                      dead, certs.get(base_name(str(r.get("key") or "")), 0))
             for r in rows if isinstance(r, dict)]
    live = [ln for ln in lanes if ln["live"] == LIVE]
    metrics = ("unique_cells_per_hour", "cells_to_judge_per_hour", "certificates",
               "keff_per_compute_hour")
    medians: dict[str, Any] = {}
    pools: dict[str, list[float]] = {}
    for m in metrics:
        vals = [float(ln[m]) for ln in live if isinstance(ln[m], (int, float))]
        pools[m] = vals
        medians[m] = round(statistics.median(vals), 6) if vals else UNMEASURED
    for ln in live:
        ranks = [_pct_rank(pools[m], float(ln[m])) for m in metrics
                 if isinstance(ln[m], (int, float)) and pools[m]]
        ln["yield_score"] = round(sum(ranks) / len(ranks), 4) if ranks else None
        ln["vs_peer_median"] = {m: (round(float(ln[m]) - float(medians[m]), 6)
                                    if isinstance(ln[m], (int, float))
                                    and isinstance(medians[m], (int, float)) else UNMEASURED)
                                for m in metrics}
    scored = sorted((ln for ln in live if ln.get("yield_score") is not None),
                    key=lambda ln: (ln["yield_score"], ln["lane"]))
    q = max(1, len(scored) // 4) if scored else 0
    bottom = scored[:q]
    top = scored[-q:] if q else []
    winners: dict[str, str] = {}
    for ln in sorted(top, key=lambda ln: -ln["yield_score"]):
        winners.setdefault(ln["structure"], ln["lane"])
    if top:
        winners.setdefault("*", top[-1]["lane"])
    for ln in bottom:
        ln["bottom_quartile"] = True
    targets = bottom + [ln for ln in lanes if ln["clock"] and (
        ln["live"] == STALE or ln["wired"] == UNWIRED) and not ln.get("bottom_quartile")]
    actions = [_action(ln, {**winners,
                            ln["structure"]: winners.get(ln["structure"]) or winners.get("*", "")})
               for ln in targets]
    counts = {"lanes": len(lanes), "live": len(live), "stale": len(lanes) - len(live),
              "wired": sum(1 for ln in lanes if ln["wired"] == WIRED),
              "unwired": sum(1 for ln in lanes if ln["wired"] == UNWIRED),
              "clocked": sum(1 for ln in lanes if ln["clock"]),
              "clocked_stale": sum(1 for ln in lanes if ln["clock"] and ln["live"] == STALE),
              "clocked_unwired": sum(1 for ln in lanes if ln["clock"] and ln["wired"] == UNWIRED),
              "bottom_quartile": len(bottom), "actions": len(actions)}
    prev = previous if previous is not None else (_read(OUT) or {})
    prev_lanes = {r["lane"]: r for r in (prev.get("lane_states") or []) if isinstance(r, dict)}
    regressions = []
    for ln in lanes:
        p = prev_lanes.get(ln["lane"])
        if not p:
            continue
        if p.get("live") == LIVE and ln["live"] == STALE:
            regressions.append({"lane": ln["lane"], "went": "LIVE->STALE"})
        if p.get("wired") == WIRED and ln["wired"] == UNWIRED:
            regressions.append({"lane": ln["lane"], "went": "WIRED->UNWIRED",
                                "because": ln["unwired_because"]})
    _pr = prev.get("ratchet")
    pr: dict[str, Any] = _pr if isinstance(_pr, dict) else {}
    ratchet = {k: min(int(pr.get(k, counts[k])), counts[k])
               for k in ("clocked_stale", "clocked_unwired")}
    doc.update({
        "verdict": "MEASURED",
        "rule": ("LIVE = a cell in 24h, seat rows in 3d, or a declared exemption that ran; WIRED "
                 "= clock + output reaching the compiler/docket + a consumer; yield = percentile "
                 "of unique cells/h, cells to judge/h, certificates and k_eff per compute-hour "
                 "among LIVE peers; bottom quartile and every clocked STALE/UNWIRED lane get an "
                 "additive upgrade; nothing is ever cut"),
        "counts": counts, "peer_medians": medians,
        "ratchet": ratchet, "ratchet_previous": pr or None,
        "regressions": regressions,
        "bottom_quartile": [{k: ln[k] for k in ("lane", "structure", "yield_score",
                                                 "unique_cells_per_hour",
                                                 "cells_to_judge_per_hour", "certificates",
                                                 "keff_per_compute_hour", "vs_peer_median")}
                            for ln in bottom],
        "winners_by_structure": winners,
        "actions": actions[:MAX_ACTIONS],
        "actions_by_kind": dict(Counter(a["action"] for a in actions)),
        "stale_clocked_sample": [ln["lane"] for ln in lanes
                                 if ln["clock"] and ln["live"] == STALE][:60],
        "unwired_clocked_sample": [ln["lane"] for ln in lanes
                                   if ln["clock"] and ln["wired"] == UNWIRED][:60],
        "lane_states": [{"lane": ln["lane"], "live": ln["live"], "wired": ln["wired"]}
                        for ln in lanes],
        "lanes": sorted(live, key=lambda ln: -(ln.get("yield_score") or 0.0))[:400],
    })
    return doc


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def proposals(path: Path | None = None, limit: int = 12) -> list[dict[str, Any]]:
    """The bottom-quartile upgrades as `frontier_ceo` proposal rows (its implement loop)."""
    doc = _read(path or OUT) or {}
    out = []
    for a in (doc.get("actions") or [])[:limit]:
        if not isinstance(a, dict):
            continue
        out.append({"id": f"producer_health:{a.get('action', '').lower()}:{a.get('lane')}",
                    "kind": "capability", "adds": str(a.get("what") or "")[:220],
                    "needs": "implementation against this repository",
                    "why_independent": ("a lane producing less than its peers is discovery the "
                                        "desk already paid for and is not receiving"),
                    "experiment": (f"apply {a.get('action')} to {a.get('lane')} and re-read its "
                                   f"PRODUCER_HEALTH yield_score next pass"),
                    "refuted_if": "its yield_score and cells to the judge do not rise",
                    "cost": "low", "blocked_on": None,
                    "rank_note": "PRODUCER_HEALTH bottom quartile (additive, never a cut)"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else None
    prev = _read(out) if out else None
    doc = build(previous=prev or {})
    path = write(doc, out)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        c = doc.get("counts") or {}
        print(f"producer health {doc['generated_utc']}: {doc['verdict']} {c}")
        print(f"  actions: {doc.get('actions_by_kind')}  regressions: "
              f"{len(doc.get('regressions') or [])}")
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
