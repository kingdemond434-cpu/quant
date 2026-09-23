"""THE FACTORY BOTTLENECK LAW (Tier-5 mandate 131/132): the funnel's slowest stage, measured
hourly from the registry's own counts, and the compute shift that attacks it.

The desk already MEASURES conversion (`conversion_ledger.binding_stage`, daily) and stage counts
(`research_productivity`, daily, from artifacts). Neither runs hourly, neither reads the canonical
registry, and neither moves compute: the binding stage was a sentence in a report. This organ reads
the registry (`data/alpha_registry.sqlite`) and the desk's own sleeve roster every hour, names the
transition with the lowest throughput ratio, names the DEPARTMENT that owns it, and publishes a
`compute_shift` factor for that department. The shift is consumed by `research_auction` (the
bottleneck department's bid rises) and so reaches `research_budget.budget_s` next epoch.

WHAT IT NEVER DOES: cut anything. A factor here is >= 1.0 for the binding department and 1.0
for everyone else; the auction's two-sided normalisation is where a loser's share falls, inside
research_budget's own [0.5, 2.0] clip, and never to zero (exploration floor).

Stages (in -> out), with the owning department:
    discovered  -> converted     discoveries UNPROCESSED -> QUEUED/EXPANDED       intel/discovery
    converted   -> candidates    discoveries converted   -> research_candidates   discovery
    candidates  -> executable    status queued           -> status donated        discovery
    executable  -> judged        donated                 -> judged_at set         validate
    judged      -> certified     judged                  -> UNIVERSAL_SURVIVORS   validate
    certified   -> forward       survivors               -> sleeves STANDBY/LIVE  forward
    forward     -> live          STANDBY                 -> LIVE                  forward
A stage whose input count is zero is UNMEASURED, never a bottleneck: absence of flow upstream is
the upstream stage's finding.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "BOTTLENECK_LAW.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = BASE / "data" / "sleeves.json"
CONVERSION = BASE / "data" / "conversion_ledger.json"
LATENCY = BASE / "reports" / "RESEARCH_LATENCY.json"

#: transition name -> department that owns its service rate.
OWNER: dict[str, str] = {
    "discovered->converted": "intel",
    "converted->candidates": "discovery",
    "candidates->executable": "discovery",
    "executable->judged": "validate",
    "judged->certified": "validate",
    "certified->forward": "forward",
    "forward->live": "forward",
}
MAX_SHIFT = 2.0


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def registry_counts(conn: Any | None = None) -> dict[str, int]:
    """The funnel's counts, straight from the registry tables. Missing tables count zero and are
    named in `unmeasured` by the caller."""
    from libs.moat import registry
    c = conn or registry.connect()
    out: dict[str, int] = {}
    try:
        def q(sql: str) -> int:
            try:
                row = c.execute(sql).fetchone()
                return int(row[0] or 0) if row is not None else 0
            except Exception:
                return 0
        out["discovered"] = q("SELECT COUNT(*) FROM discoveries")
        out["unprocessed"] = q("SELECT COUNT(*) FROM discoveries WHERE state='UNPROCESSED'")
        out["blocked"] = q("SELECT COUNT(*) FROM discoveries WHERE state='BLOCKED'")
        out["converted"] = q("SELECT COUNT(*) FROM discoveries WHERE state IN "
                             "('QUEUED','EXPANDED','COMPILED','TESTED')")
        out["candidates"] = q("SELECT COUNT(*) FROM research_candidates")
        out["queued"] = q("SELECT COUNT(*) FROM research_candidates WHERE status='queued'")
        out["executable"] = q("SELECT COUNT(*) FROM research_candidates WHERE status IN "
                              "('donated','claimed','judged','certified','rejected')")
        out["judged"] = q("SELECT COUNT(*) FROM research_candidates WHERE judged_at IS NOT NULL "
                          "AND judged_at!=''")
    finally:
        if conn is None:
            c.close()
    return out


def roster_counts(sleeves_doc: dict[str, Any], survivors_doc: dict[str, Any]) -> dict[str, int]:
    rows = _lst(sleeves_doc.get("sleeves"))
    status = [str(r.get("status") or "") for r in rows if isinstance(r, dict)]
    sv = survivors_doc.get("survivors")
    n_cert = len(sv) if isinstance(sv, (dict, list)) else int(survivors_doc.get("n") or 0)
    return {"certified": n_cert, "forward": status.count("STANDBY") + status.count("LIVE"),
            "live": status.count("LIVE")}


def transitions(reg: dict[str, int], roster: dict[str, int]) -> list[dict[str, Any]]:
    pairs = [
        ("discovered->converted", reg.get("discovered", 0), reg.get("converted", 0)),
        ("converted->candidates", reg.get("converted", 0), reg.get("candidates", 0)),
        ("candidates->executable", reg.get("candidates", 0), reg.get("executable", 0)),
        ("executable->judged", reg.get("executable", 0), reg.get("judged", 0)),
        ("judged->certified", reg.get("judged", 0), roster.get("certified", 0)),
        ("certified->forward", roster.get("certified", 0), roster.get("forward", 0)),
        ("forward->live", roster.get("forward", 0), roster.get("live", 0)),
    ]
    out: list[dict[str, Any]] = []
    for name, n_in, n_out in pairs:
        measured = n_in > 0
        ratio = (min(n_out, n_in) / n_in) if measured else None
        out.append({"stage": name, "in": int(n_in), "out": int(n_out),
                    "ratio": round(ratio, 6) if ratio is not None else None,
                    "backlog": max(int(n_in) - int(n_out), 0), "measured": measured,
                    "owner": OWNER[name]})
    return out


def binding(trans: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The measured transition with the lowest throughput ratio; ties go to the larger backlog,
    which is the one holding more work hostage."""
    measured = [t for t in trans if t["measured"] and t["ratio"] is not None]
    if not measured:
        return None
    return min(measured, key=lambda t: (float(t["ratio"]), -int(t["backlog"])))


def compute_shift(bind: dict[str, Any] | None) -> dict[str, float]:
    """Factor >= 1 for the binding department, 1.0 elsewhere: 1 + (1 - ratio), capped."""
    depts = sorted(set(OWNER.values()))
    shift = dict.fromkeys(depts, 1.0)
    if bind is not None:
        ratio = float(bind["ratio"] or 0.0)
        shift[str(bind["owner"])] = round(min(MAX_SHIFT, 1.0 + max(0.0, 1.0 - ratio)), 4)
    return shift


def build(now: datetime | None = None, conn: Any | None = None,
          sleeves_doc: dict[str, Any] | None = None,
          survivors_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    unmeasured: list[str] = []
    try:
        reg = registry_counts(conn)
    except Exception as exc:  # the registry is the measurement; its absence is named
        reg = {}
        unmeasured.append(f"registry unavailable: {type(exc).__name__}: {exc}")
    roster = roster_counts(sleeves_doc if sleeves_doc is not None else _read(SLEEVES),
                           survivors_doc if survivors_doc is not None else _read(SURVIVORS))
    trans = transitions(reg, roster)
    unmeasured.extend(f"{t['stage']}: no input flow" for t in trans if not t["measured"])
    bind = binding(trans)
    shift = compute_shift(bind)
    conv = _read(CONVERSION)
    lat = _read(LATENCY)
    doc: dict[str, Any] = {
        "at": at, "counts": {**reg, **roster}, "transitions": trans,
        "binding": bind, "compute_shift": shift,
        "cross_reference": {
            "conversion_ledger_binding_stage": conv.get("binding_stage"),
            "conversion_ledger_binding_rate": conv.get("binding_rate"),
            "research_latency_slowest": (lat.get("slowest") if isinstance(lat, dict) else None),
        },
        "unmeasured": unmeasured,
        "consumer": "research_auction (bid bonus for the binding department) -> "
                    "research_budget.budget_s next epoch; RESEARCH_DASHBOARD",
        "rule": ("the binding transition is the measured stage with the lowest out/in ratio; "
                 "its owner's factor rises to 1+(1-ratio) <= 2.0; nothing is cut here and no "
                 "department can reach zero (research_budget clips to [0.5, 2.0])"),
    }
    doc["headline"] = (f"binding {bind['stage']} ratio {bind['ratio']} backlog {bind['backlog']} "
                       f"-> shift {bind['owner']} x{shift[str(bind['owner'])]}"
                       if bind else "UNMEASURED: no transition carries input flow")
    return doc


def publish(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from libs.moat import registry
        b = doc.get("binding") or {}
        registry.remember("bottleneck_law", doc["headline"], kind="binding_stage",
                          memory_key="bottleneck_law:binding",
                          metrics={"stage": b.get("stage"), "ratio": b.get("ratio"),
                                   "backlog": b.get("backlog"), "owner": b.get("owner"),
                                   "at": doc["at"]})
    except Exception as exc:
        doc.setdefault("unmeasured", []).append(f"registry memory not written: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out)
    print(f"bottleneck law: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
