#!/usr/bin/env python3
"""ADAPTIVE DATA ACQUISITION AGENT (triage #93) -- what to acquire NEXT, ranked on measurement.

WHY #93 SAT UNBUILT. It was blocked on "Information Advantage Score (item 17) existing first",
item 17 shipped 2026-07-29, and the row has been UNBLOCKED and untouched since -- caught
mechanically by check_triage_disposition, not by anyone re-reading it.

WHAT MAKES IT ADAPTIVE, AND WHY THE OBVIOUS BUILD WOULD NOT HAVE BEEN. `research_cio.py`'s
INFORMATION ADVANTAGE SCORE is a hardcoded table: uniqueness, predictive power, persistence and
replication difficulty, all hand-assigned per source class. Ranking acquisitions by that table
produces a confident-looking order built entirely out of somebody's priors, dressed in the
vocabulary of measurement -- the exact failure libs/doctrine/contribution.py refuses, and the
reason a "made-up basis" is rejected at construction there.

So this agent scores on what the desk has actually LEARNED, and the learning enters through one
term: the ontology's own record of attempts and survivors per frontier region.

  * A source that would inform regions the desk has hammered with ZERO survivors is scored DOWN.
    That is evidence, gathered here, that this class of data is barren for this desk -- and it is
    the term that makes the ranking move as the desk works, which a static table cannot do.
  * A source that would REOPEN an under-explored region is scored UP. `ontology.map_dataset`
    already answers "which questions would this dataset help answer", and `ontology.priority`
    already folds in exhaustion with a revival floor -- because a barren region reopened by new
    data is precisely where a desk finds what everyone else gave up on.
  * REPLICATION DIFFICULTY MULTIPLIES, exactly as in EVIG. A source anyone can pull yields edge
    that is already priced; the desk's own measured advantage ranks self-recorded tape at 1.03
    against 0.37 for the next best thing.
  * COST DIVIDES. Free-and-adequate beats paid-and-marginal every time under a log objective.

WHAT IT REFUSES. A candidate whose grade, cost or region mapping cannot be read is scored
UNMEASURED and ranked with an honest penalty -- never given a plausible default. That is WS-005
applied at construction: the least-known source must not become the most attractive one by virtue
of nobody having checked it.

NO ACQUISITION AUTHORITY. This ranks and explains. It spends nothing, signs nothing and starts no
collector; a human or a later organ acts on the ordering. Read-only. No keys, no order paths.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hypmax.evig import information_gain  # noqa: E402
from libs.hypmax.ontology import (  # noqa: E402
    SEED_QUESTIONS,
    load_state,
    map_dataset,
    priority,
)

UNIVERSE = ROOT / "data/data_universe_map.json"
ONTOLOGY_STATE = ROOT / "data/ontology_state.json"
MOAT = ROOT / "data/moat_mine.json"
REPORT = ROOT / "data/acquisition_plan.json"
HISTORY = ROOT / "data/acquisition_history.jsonl"

#: Source grade -> (P(the data is usable as claimed), why). Grades are the digger's own vocabulary
#: and already carry a verification level, so this maps VERIFICATION to a probability rather than
#: inventing one. A grade nobody assigned falls to the unmeasured floor, never to a middling guess.
GRADE_P: dict[str, tuple[float, str]] = {
    "verified-clean": (0.90, "URL opened and directly confirmed"),
    "needs-monitoring": (0.60, "corroborated but never diffed against ground truth"),
    "reconstructable": (0.50, "methodology is public; the series must be rebuilt, not fetched"),
    "unverified": (0.25, "found, not confirmed -- the desk's own rule says do not adopt"),
    "destroyed-at-source": (0.02, "honest negative: no free path found this session"),
}
#: Applied when a candidate carries no grade at all. Deliberately BELOW the worst real grade: an
#: ungraded source is less known than one somebody looked at and rejected, and ranking it above
#: `unverified` would reward never checking.
UNGRADED_P = 0.01

#: Replication difficulty by access class -- how hard it is for a competitor to hold the same data.
#: Anchored to the desk's OWN measured advantage figures (self-recorded tape 1.03, next-best 0.37)
#: rather than to opinion, and everything public collapses toward the bottom because it must.
REPLICATION: dict[str, tuple[float, str]] = {
    "self-recorded": (1.03, "cannot be bought at any price -- our snapshots, from our clock"),
    "reconstructed": (0.55, "public inputs, private method: replicable only by redoing the work"),
    "gated-free": (0.37, "free but rate-limited or keyed -- a real if modest barrier"),
    "public": (0.10, "pullable in an afternoon by anyone, so any edge found is already priced"),
}

#: Relative cost, in the same units EVIG uses: 1.0 is one routine collector build.
COST: dict[str, float] = {
    "self-recorded": 3.0,      # a recorder, plus disk, plus supervision, forever
    "reconstructed": 2.0,      # rebuild the methodology and diff it
    "gated-free": 1.0,
    "public": 0.5,
}


def _rel(p: Path) -> str:
    """Display path, relative to the repo when it is inside it. `relative_to` RAISES on a path
    outside ROOT, so the unguarded version turned an honest 'the file is missing' report into a
    ValueError the moment the constant was repointed -- an error path that only breaks when it is
    needed is the worst kind."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path):
    try:
        if not p.exists() or p.stat().st_size <= 2:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _grade_p(grade: str) -> tuple[float, str]:
    g = (grade or "").strip().lower()
    for key, (p, why) in GRADE_P.items():
        if key in g:
            return p, why
    return UNGRADED_P, ("NO GRADE RECORDED -- ranked below every graded source, including the "
                        "rejected ones. An unchecked source must never outrank a checked-and-poor "
                        "one, or the ranking rewards not looking")


def _access_class(entry: dict) -> str:
    """Access class from the entry's own fields, never guessed from the name."""
    blob = " ".join(str(entry.get(k, "")) for k in
                    ("access", "class", "kind", "notes", "why", "grade")).lower()
    if "self-record" in blob or "own recorder" in blob:
        return "self-recorded"
    # Prose, not an enum: the digger writes "rebuilt from the public methodology" as readily as
    # "reconstructable". Matching one spelling silently demoted real reconstructions to `public`,
    # which is the most-discounted class -- so the miss was expensive in exactly one direction.
    if any(w in blob for w in ("reconstruct", "rebuil", "re-deriv", "rederiv", "self-comput")):
        return "reconstructed"
    if "key" in blob or "rate-limit" in blob or "gated" in blob or "community" in blob:
        return "gated-free"
    return "public"


def score_candidate(name: str, entry: dict, state: dict) -> dict:
    """One acquisition candidate, scored EVIG-shaped on measured terms.

    score = P(usable) x information_gain(P) x replication_difficulty x region_priority / cost

    Multiplicative for the reason EVIG is: no term rescues a dead one. A perfectly unique source
    informing a region the desk has proved barren is still not worth acquiring, and a rich region
    reachable only through data everyone already has yields edge that is already priced.
    """
    desc = " ".join(str(entry.get(k, "")) for k in ("description", "notes", "why", "metrics"))
    regions = map_dataset(name, desc, SEED_QUESTIONS)
    grade = str(entry.get("grade", ""))
    p, p_why = _grade_p(grade)
    access = _access_class(entry)
    rep, rep_why = REPLICATION[access]
    cost = COST[access]

    # THE ADAPTIVE TERM. Region priority already folds in the desk's recorded attempts and
    # survivors with a revival floor, so a class of data the desk has worked to exhaustion scores
    # down HERE, from evidence, rather than being demoted by an author's opinion in a table.
    by_id = {q.id: q for q in SEED_QUESTIONS}
    prios = [priority(by_id[r], state=state) for r in regions if r in by_id]
    region_p = max(prios) if prios else 0.0
    worked = sum(int(state.get(r, {}).get("attempts", 0)) for r in regions)
    survived = sum(int(state.get(r, {}).get("survivors", 0)) for r in regions)

    score = p * information_gain(p) * rep * region_p / max(cost, 1e-6)
    unmeasured = (p == UNGRADED_P) or not regions
    return {
        "source": name,
        "score": round(score, 6),
        "p_usable": p,
        "grade": grade or "(none)",
        "access_class": access,
        "replication": rep,
        "cost": cost,
        "regions": regions[:8],
        "region_priority": round(region_p, 6),
        "desk_record": f"{survived} survivor(s) from {worked} attempt(s) in these regions",
        "unmeasured": unmeasured,
        "why": (
            f"{p_why}; {rep_why}; "
            + (f"informs {len(regions)} frontier region(s), best priority {region_p:.3f} "
               f"({survived}/{worked} survived there)"
               if regions else
               "MAPS TO NO FRONTIER REGION -- either genuinely off-thesis or the entry carries too "
               "little description to match. Scored zero rather than defaulted: a source nobody "
               "can say what it would answer is not an acquisition, it is a wish")),
    }


def main() -> int:
    t0 = time.time()
    universe = _read(UNIVERSE)
    state = load_state(ONTOLOGY_STATE)
    moat = _read(MOAT) or {}

    if not isinstance(universe, dict) or not universe:
        out = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "state": "NO SOURCE UNIVERSE",
            "reason": (f"{_rel(UNIVERSE)} absent or empty -- the digger publishes it "
                       "and data/ is gitignored, so this is expected in a fresh checkout and a "
                       "REAL blocker on the VPS. No ranking is offered: ranking zero candidates "
                       "would print an empty plan that reads like 'nothing worth acquiring'."),
            "next": "run the data-axis digger (ops/run_dataaxis_dig.sh) to publish the map",
            "candidates": 0,
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"acquire: NO SOURCE UNIVERSE -- {_rel(UNIVERSE)} absent. "
              "Ranking refused rather than faked.")
        return 0

    entries = universe.get("sources", universe)
    rows = [score_candidate(str(k), v if isinstance(v, dict) else {"description": str(v)}, state)
            for k, v in entries.items()]
    rows.sort(key=lambda r: (-r["score"], r["source"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    measured = [r for r in rows if not r["unmeasured"]]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "candidates": len(rows),
        "measured": len(measured),
        "moat_coverage_pct": (moat.get("cumulative_coverage", {}) or {}).get("coverage_pct"),
        "plan": rows[:25],
        "top": rows[0]["source"] if rows else None,
        "note": (
            "score = P(usable) x information_gain(P) x replication_difficulty x region_priority "
            "/ cost. Multiplicative, like EVIG: no term rescues a dead one. The ADAPTIVE term is "
            "region_priority, which reads the ontology's recorded attempts and survivors -- so a "
            "class of data this desk has worked to exhaustion falls from EVIDENCE rather than "
            "from an author's opinion in a table. An ungraded source ranks below every graded "
            "one including the rejected ones, because a ranking that rewards not looking is "
            "worse than no ranking."),
        "authority": ("NONE. This ranks and explains; it spends nothing, signs nothing and starts "
                      "no collector."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "candidates": len(rows),
                             "measured": len(measured),
                             "top": out["top"]}, separators=(",", ":")) + "\n")

    print(f"acquire: {len(rows)} candidate(s), {len(measured)} measured | {out['seconds']}s")
    for r in rows[:8]:
        flag = "    " if not r["unmeasured"] else "UNM "
        print(f"  [{flag}] #{r['rank']:<2} {r['source'][:38]:<38} {r['score']:.5f}  "
              f"{r['access_class']:<14} {r['desk_record']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
