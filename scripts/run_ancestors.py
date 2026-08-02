#!/usr/bin/env python3
"""THE ANCESTOR ORGANS, RUN EVERY CYCLE -- lineage, breeding, theory, invention, market.

WHY THIS RUNS AT ALL WITH ZERO SURVIVORS. Four libraries landed with tests and no caller, which is
the exact "built but never runs" class this desk has been hunting all session. A library with no
caller produces nothing, teaches nothing, and decays -- and the moment it is finally wired, its
first run is against a codebase that moved six weeks underneath it. So it runs now, on the data
that exists now, and reports honestly where that data is thin.

WHAT IT ACTUALLY HAS TO WORK WITH TODAY. `docs/graveyard.md` holds 42 permanently-killed
hypotheses with tags and kill reasons -- real specimens with real parentage, in git, available
immediately. `data/hypothesis_queue.jsonl` and `data/gauntlet_candidates.json` add live ones when
they exist. That is enough for a lineage graph and a fertility ranking today; it is NOT enough for
theory induction, which stays dormant and says so rather than inducing a principle from zero
survivors.

THE FIVE PASSES:

  LINEAGE     which families and lenses get FURTHEST, rate-adjusted. With zero survivors this
              ranks by depth reached, which is the only signal available and is still strictly
              better than allocating generation uniformly over ground of unknown fertility.
  BREEDING    crosses of eligible parents, with the incest bound and the earned-rights floor.
              Rejections are reported: "4 children" and "4 children from 190 pairings, 186
              rejected as near-duplicates" describe completely different populations.
  THEORY      dormant until 3 survivors share a mechanism. Arms from a data condition.
  INVENTION   composed feature candidates ranked by REPLICATION COST, moat-derived first.
  MARKET      calibration-weighted seat aggregation, uniform until seats have settled records.

MAX CADENCE, BUDGETED, AND WITH NO PROMOTION AUTHORITY. Every output is a CANDIDATE or a report.
Nothing here pre-registers a hypothesis, promotes anything, or moves a gate.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hypmax.genealogy import (  # noqa: E402
    BREEDING_MIN_STAGE,
    Lineage,
    Specimen,
    breed,
    diversity,
    effective_population,
    induce_theory,
    lineage_report,
)
from libs.hypmax.invention import invent  # noqa: E402
from libs.llm.market import InformationMarket  # noqa: E402

GRAVEYARD = ROOT / "docs/graveyard.md"
QUEUE = ROOT / "data/hypothesis_queue.jsonl"
CANDIDATES = ROOT / "data/gauntlet_candidates.json"
VERDICTS = ROOT / "data/panel_verdicts.jsonl"
OUT = ROOT / "data/ancestors.json"

MAX_CHILDREN = int(os.environ.get("ANCESTORS_MAX_CHILDREN") or 24)
MAX_FEATURES = int(os.environ.get("ANCESTORS_MAX_FEATURES") or 40)

#: Words too generic to identify a hypothesis. Left in, every specimen shares them and the
#: similarity measure collapses -- every pair reads as near-identical and breeding refuses
#: everything, which would look exactly like a converged population.
_STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "with", "is", "are",
         "at", "by", "from", "vs", "per", "xsec", "cross", "premium", "signal", "effect"}


def _terms(text: str) -> tuple[str, ...]:
    words = [w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP]
    return tuple(sorted(set(words))[:12])


def _from_graveyard() -> list[Specimen]:
    """42 permanently-killed hypotheses with tags. Dead lines are EVIDENCE, not clutter.

    A graveyard entry reached the gauntlet and died there, so its stage is recorded as the
    breeding floor: it got far enough to have been genuinely tested, which is exactly the
    property breeding rights are meant to select for. Recording it lower would make the whole
    population ineligible and breeding would silently do nothing.
    """
    out: list[Specimen] = []
    if not GRAVEYARD.exists():
        return out
    for line in GRAVEYARD.read_text("utf-8", errors="ignore").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Hypothesis |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0]:
            continue
        name, verdict, tag = cells[0], cells[1], cells[2].strip("`")
        out.append(Specimen(
            id=f"grave:{name[:60]}",
            family=tag or "untagged",
            mechanism=tag or "untagged",
            lens="graveyard",
            terms=_terms(f"{name} {verdict}"),
            stage=BREEDING_MIN_STAGE,
            survived=False,
        ))
    return out


def _from_queue() -> list[Specimen]:
    out: list[Specimen] = []
    if not QUEUE.exists():
        return out
    for line in QUEUE.read_text("utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or d.get("hypothesis") or "")[:60]
        if not name:
            continue
        out.append(Specimen(
            id=f"queue:{name}",
            family=str(d.get("family") or d.get("tag") or "ungrouped"),
            mechanism=str(d.get("mechanism") or "")[:80],
            lens=str(d.get("lens") or d.get("seat") or ""),
            terms=_terms(f"{name} {d.get('mechanism', '')} {d.get('data_source', '')}"),
            stage=int(d.get("stage") or 0),
            survived=bool(d.get("survived")),
        ))
    return out


def _market() -> dict:
    """Seat calibration from settled panel verdicts, or an honest uniform report.

    UNIFORM IS THE CORRECT OUTPUT WITH NO SETTLED HISTORY, not a limitation. With nothing settled
    there is no evidence any seat is better than any other, and manufacturing weights would be
    fabrication wearing the costume of sophistication.
    """
    m = InformationMarket()
    n_rows = 0
    if VERDICTS.exists():
        for line in VERDICTS.read_text("utf-8", errors="ignore").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            seat, claim = str(d.get("seat") or d.get("model") or ""), str(d.get("claim") or "")
            p = d.get("confidence", d.get("p"))
            if seat and claim and isinstance(p, int | float):
                m.stake(seat, claim, float(p), str(d.get("rationale") or "")[:200])
                n_rows += 1
            if isinstance(d.get("outcome"), bool):
                m.settle(claim, bool(d["outcome"]))
    return {
        "stakes": n_rows,
        "settled_claims": len(m.outcomes),
        "weights": m.weights(),
        "records": m.records(),
        "note": ("weights are UNIFORM because no claim has settled yet. That is the correct "
                 "output, not a limitation -- with no record there is no evidence any seat is "
                 "better, and manufacturing weights would be fabrication. The market sharpens "
                 "itself the first time a staked claim resolves."
                 if not m.outcomes else
                 "weights are calibration-derived: a seat's realised log score IS its weight, so "
                 "nobody has to decide who to trust"),
    }


def main() -> int:
    t0 = time.time()
    grave, queued = _from_graveyard(), _from_queue()
    specimens = grave + queued

    lin = Lineage()
    for s in specimens:
        lin.add(s)

    lineage = lineage_report(lin)
    parents = [s for s in specimens if s.stage >= BREEDING_MIN_STAGE]
    bred = breed(parents, max_children=MAX_CHILDREN)
    theory = induce_theory(specimens)
    features = invent(limit=MAX_FEATURES)
    market = _market()

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "specimens": len(specimens),
        "sources": {"graveyard": len(grave), "queue": len(queued)},
        "lineage": lineage,
        "population": {
            "diversity": diversity(specimens),
            "effective_population": effective_population(specimens),
            "note": ("effective population sees through paraphrases -- 200 restatements of one "
                     "idea have an effective size near 1, and a desk counting 200 believes it "
                     "is exploring"),
        },
        "breeding": {k: v for k, v in bred.items() if k != "children"},
        "children": [{"id": c.id, "mechanism": c.mechanism, "terms": list(c.terms),
                      "parents": list(c.parents), "generation": c.generation}
                     for c in bred["children"]],
        "theory": theory,
        "invention": {k: v for k, v in features.items() if k != "kept"},
        "features": [{"name": f.name, "moat_derived": f.moat_derived,
                      "fingerprint": f.fingerprint} for f in features["kept"]],
        "market": market,
        "authority": ("NONE. Every child and every feature here is a CANDIDATE entering the "
                      "funnel at the full bar. Parentage confers no credibility -- inherited "
                      "standing is how a breeding programme launders a weak idea."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"ancestors: {len(specimens)} specimens ({out['sources']['graveyard']} graveyard, "
          f"{out['sources']['queue']} queue) | {lineage['survivors']} survivors, "
          f"max depth {lineage['reached_breeding_stage']} | {out['seconds']}s")
    if lineage["by_family"] and lineage.get("discriminating", True):
        top = lineage["by_family"][0]
        print(f"  most fertile line: {top['family']} "
              f"(n={top['n']}, fertility {top['fertility']})")
    print(f"  bred {len(bred['children'])} candidate(s) from {bred['eligible_parents']} eligible "
          f"parent(s); {bred['n_rejected']} pairing(s) rejected as near-duplicates")
    if bred["diversity_warning"]:
        print(f"  {bred['diversity_warning']}")
    if bred.get("scan_note"):
        print(f"  {bred['scan_note']}")
    if not lineage.get("discriminating", True):
        print(f"  FERTILITY NOT DISCRIMINATING -- {lineage['note'][:130]}")
    print(f"  theory: {theory['state']}"
          + (f" -- {theory['note'][:90]}" if theory["state"] == "DORMANT" else ""))
    print(f"  invented {features['n_kept']} feature candidate(s) from {features['composed']} "
          f"compositions ({features['moat_derived_kept']} moat-derived)")
    print(f"  market: {market['stakes']} stake(s), {market['settled_claims']} settled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
