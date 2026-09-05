"""THE FRONTIER MINER'S HOURLY CYCLE -- observe, compare, value, and never idle.

    python -m frontier_intel.frontier_supervisor            # one pass, from desks/mt5
    python -m frontier_intel.frontier_supervisor --report   # state only, fetch nothing

WHAT THIS ORGAN IS FOR, and it is not another alpha miner. The existing miners ask "what tradeable
edge exists". This asks "how do the strongest research organisations become better at finding
edges", and its output is mostly upgrades to the desk itself. A finding that implies a trading
hypothesis is handed to the existing alpha pipeline through the deepening queue -- never traded
here, and never given a second alpha factory to live in.

SIX STAGES, and the honest state of each is reported rather than smoothed:

    SCOUT     read the registered organisations and the frontier sources
    EXTRACT   turn a finding into a structured claim with an evidence grade
    COMPARE   map it to a capability and ask what this desk already has
    VALUE     score it with `roi`, which refuses more often than it queues
    PLAN      write the independent-replication plan for the best candidate
    MEASURE   advance what is already in flight and update the rent record

WHAT THIS PASS DOES NOT DO, stated plainly because the mandate asks for more and the difference is
a safety boundary rather than an unfinished edge: it does not write code, open branches or merge
anything. It produces a PLAN and a queue entry, and the existing CI, challenger and measurement
machinery gate everything after that. An LLM that can both propose and merge into the tree that
sizes real positions is one bad extraction away from a live defect, and the mandate's own rule --
"no implementation earns capital merely because an AI wrote it" -- is easier to keep when the
implementer cannot merge at all. The plan is the deliverable; a person or a reviewed pipeline
takes it from there.

NEVER IDLE. When no new external finding appears, the pass works the existing highest-value queue
item instead. An hour with no novelty is not an hour with nothing to do, and a supervisor that
returned early on a quiet hour would do most of its nothing during the quiet weeks when the desk
most needs the backlog worked.

SCOUTING IS OFFLINE HERE. `scout()` reads what other organs have already fetched into the
intelligence roots rather than crawling the web itself: the desk already runs crawlers, and a
second fetch layer in this package would be a second thing to rate-limit, a second thing to get
blocked, and a second copy of the source policy. What this organ adds is the READING, not the
retrieval.
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
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontier_intel import ontology, queue, registry, roi, unknowns  # noqa: E402

REPORT = _DESK / "reports" / "FRONTIER_INTELLIGENCE.json"
GAPS = _DESK / "reports" / "FRONTIER_GAPS.json"
#: Where the desk's existing crawlers already put what they fetched. Read, never written.
INTEL_ROOTS = (_DESK / "data" / "intelligence", _ROOT / "data" / "intelligence")
#: How far back a pass reads. One week: long enough that a quiet day still has material, short
#: enough that the same finding is not re-scored for a month.
WINDOW_DAYS = 7
#: Rows one pass will read. A bound on memory with the same rationale as the compiler's.
MAX_ROWS = 50_000


def scout(now: datetime | None = None) -> list[dict[str, Any]]:
    """Rows from the desk's own intelligence roots that MENTION a tracked organisation.

    The filter is deliberately the firm registry rather than a topic model: this organ is about
    organisations, and a row that names none of them is the alpha miners' business, not this one.
    """
    import time as _t
    cut = (now or datetime.now(tz=UTC)).timestamp() - WINDOW_DAYS * 86400.0
    firms = {f.name.lower(): f.name for f in registry.FIRMS}
    out: list[dict[str, Any]] = []
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json"), key=lambda p: -p.stat().st_mtime
                           if p.exists() else 0):
            try:
                if path.stat().st_mtime < cut:
                    continue
                doc = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            rows_ = doc if isinstance(doc, list) else (
                doc.get("discoveries") or doc.get("items") or [])
            if not isinstance(rows_, list):
                continue
            for r in rows_:
                if not isinstance(r, dict):
                    continue
                text = " ".join(str(r.get(k) or "") for k in
                                ("title", "description", "body", "preview", "question", "note"))
                low = text.lower()
                hit = next((firms[k] for k in firms if k in low), "")
                if not hit:
                    continue
                out.append({"firm": hit, "text": text[:2000],
                            "url": str(r.get("url") or r.get("link") or ""),
                            "source": str(r.get("source") or path.parent.name)})
                if len(out) >= MAX_ROWS:
                    return out
        _t.sleep(0)                    # cooperative: this can walk a large tree
    return out


def extract(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a capability group and an evidence grade to each finding.

    GRADE FROM THE SOURCE CLASS, NOT FROM CONFIDENCE. A row that arrived through a forum crawler
    is Grade D however certain it sounds, and a row from an official research page is Grade A
    however hedged. Confidence is a property of the writer; grade is a property of the channel.
    """
    graded: list[dict[str, Any]] = []
    for f in findings:
        caps = ontology.map_to_capabilities(f.get("text", ""))
        src = str(f.get("source") or "").lower()
        grade = ("A" if any(k in src for k in ("official", "research", "arxiv", "ssrn", "paper"))
                 else "C" if any(k in src for k in ("news", "journal", "media"))
                 else "D")
        graded.append({**f, "capabilities": list(caps), "evidence_grade": grade})
    return graded


def compare(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each finding, what this desk already has for that capability.

    MISSING means no module on this tree owns the capability at all -- read off the ontology's
    `owner`, which is a fact about our own repo rather than a judgement. PARTIAL means a module
    exists; whether it is as good is exactly what replication and measurement decide, and this
    stage must not pretend to know.
    """
    out = []
    for f in findings:
        for cap in f.get("capabilities") or []:
            known = ontology.BY_NAME.get(cap)
            owner = known.owner if known else ""
            out.append({**f, "capability": cap, "our_owner": owner,
                        "gap": "MISSING" if not owner else "PARTIAL",
                        "level": known.level if known else ""})
    return out


def gap_matrix() -> dict[str, Any]:
    """The capability matrix: every group, who owns it here, and which firms are watched for it.

    KNOWABLE WITHOUT CRAWLING ANYTHING, which is why it is written every pass even when the scout
    finds nothing. "No module on this tree owns MARKET_IMPACT" is a measurement about us, and it
    is the kind of gap that stays open for years because nothing ever names it out loud.
    """
    rows_ = []
    for c in ontology.CAPABILITIES:
        watched = [f.name for f in registry.FIRMS if c.name in f.domains]
        rows_.append({"capability": c.name, "level": c.level, "ours": c.owner or None,
                      "gap": "MISSING" if not c.owner else "PARTIAL",
                      "what": c.what, "watched_firms": watched})
    missing = [r for r in rows_ if r["gap"] == "MISSING"]
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "capabilities": rows_,
        "n_missing": len(missing),
        "missing": [r["capability"] for r in missing],
        "most_watched_missing": sorted(
            ({"capability": r["capability"], "watched_by": len(r["watched_firms"])}
             for r in missing), key=lambda r: -r["watched_by"])[:8],
        "rule": ("cross-firm convergence is a PRIOR, never proof: several elite organisations "
                 "investing in a capability we lack raises its investigation priority and "
                 "decides nothing about whether it works here"),
    }


def one_pass(*, fetch: bool = True) -> dict[str, Any]:
    """One hourly cycle. Never raises on a data gap: every refusal is a reported reason."""
    started = datetime.now(tz=UTC)
    raw = scout(started) if fetch else []
    graded = extract(raw)
    compared = compare(graded)

    # DISCOVERY IS RECORDED BEFORE IT IS SCORED, so a finding that the ROI later refuses is still
    # in the ledger with its reason -- "no discovery disappears" is a property of the queue, not
    # of the ones that happened to score well.
    entered = 0
    for c in compared:
        row = queue.discover(firm=str(c.get("firm") or ""), capability=str(c["capability"]),
                             source_url=str(c.get("url") or ""), claim=str(c.get("text") or ""),
                             evidence_grade=str(c.get("evidence_grade") or "D"),
                             source_kind="public_forum")
        entered += 0 if row.get("already_known") else 1

    matrix = gap_matrix()
    unknown = unknowns.survey(texts=[f.get("text", "") for f in raw], findings=compared)

    # NEVER IDLE. With no new finding the pass still has the standing gaps -- capabilities no
    # module on this tree owns -- and those are real candidates that simply have not been scored.
    cands = [roi.Candidate(
        frontier_id=queue.candidate_id("standing-gap", cap, "", cap),
        firm="standing-gap", capability=cap, evidence_grade="A", gap="MISSING",
        expected_delta_elog=None, intermediate="information_gain", intermediate_value=0.5,
        p_success=0.4, evsi=0.1, breadth=1.5, persistence_years=3.0, novelty=1.0,
        costs={"engineering": 20.0, "compute": 2.0, "data": 2.0,
               "complexity": 3.0, "operational_risk": 1.0})
        for cap in matrix["missing"]]
    ranked = roi.rank(cands)

    doc = {
        "generated_utc": started.isoformat(timespec="seconds"),
        "fetched": fetch,
        "rows_scouted": len(raw), "findings_graded": len(graded),
        "capability_hits": len(compared), "new_candidates": entered,
        "queue": queue.summary(),
        "ranked": {"n_queued": ranked["n_queued"], "n_refused": ranked["n_refused"],
                   "best": ranked["best"], "top": ranked["queued"][:10]},
        "unknowns": unknown,
        "largest_gap": (ranked["queued"][0] if ranked["queued"] else None),
        "capability_matrix_missing": matrix["n_missing"],
        "boundary": ("this organ produces plans and queue entries. It does not write code, open "
                     "branches or merge: an implementer that can both propose and merge into the "
                     "tree that sizes real positions is one bad extraction from a live defect"),
        "rent": {
            "module": "frontier_intel",
            "rule": "E[logW] with the imported capability - E[logW] without, measured forward",
            "value": None, "status": "UNMEASURED",
            "why": ("no imported capability has reached PROVEN, so there is no with-minus-without "
                    "to measure. Candidates entered and gaps named are the leading indicators "
                    "until one does"),
        },
    }
    for path, payload in ((REPORT, doc), (GAPS, matrix)):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
        except OSError:
            pass
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the frontier miner's hourly cycle")
    ap.add_argument("--report", action="store_true", help="state only; read no intelligence roots")
    args = ap.parse_args(argv)
    doc = one_pass(fetch=not args.report)
    print(f"frontier: {doc['rows_scouted']} row(s) scouted, {doc['new_candidates']} new "
          f"candidate(s), {doc['capability_matrix_missing']} capability group(s) with no module "
          f"here, {doc['ranked']['n_queued']} queued / {doc['ranked']['n_refused']} refused")
    if doc["largest_gap"]:
        g = doc["largest_gap"]
        print(f"  largest gap: {g['capability']} (level {g['level']}, "
              f"priority {g['priority']:.5f})")
    print(f"  unknowns: {doc['unknowns']['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
