"""Alpha factory: the production caller for the research-coordination engines.

Measured 2026-07-27: 17 of 21 `libs/alpha_factory` modules were unreachable from any entry point.
The audit tracked `crypto-factory` as an organ owing `web/autodiscovery_crypto.json` every 30h and
reported it had never produced output -- consistent, because the engines behind it were never
called. The controller imported fifteen engines and its `run()` used two.

Inputs are the desk's own files, not fixtures:
  research_agenda.json  queue_ranked_by_expected_research_roi  -> the candidates
                        do_not_repeat                          -> novelty (already-killed families)
  alpha_pipeline.json   alphas + deployed                      -> portfolio gaps, crowding, lineage

Recommend-only by construction: the controller raises on promote/retire/capital/threshold changes.
This script writes a recommendation artifact and nothing else -- no candidate reaches capital
without the validation gauntlet.

    python scripts/run_alpha_factory.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.alpha_factory.alpha_dna import build_alpha_dna, dna_distance
from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
from libs.alpha_factory.models import AlphaCategory, IdeaCandidate

_ROOT = Path(__file__).resolve().parent.parent
_AGENDA = _ROOT / "research_agenda.json"
_PIPELINE = _ROOT / "alpha_pipeline.json"
_OUT = _ROOT / "web" / "alpha_factory.json"

#: Average daily volume assumed per category when the desk has no measured figure. Deliberately
#: CONSERVATIVE -- capacity that is guessed high sends research budget at concepts that cannot
#: hold the book, which is the expensive direction of this error.
_ADV_FALLBACK_USD = 5_000_000.0

_CROWDING = {"low": 0.2, "medium": 0.5, "high": 0.8, "unknown": 0.5}


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _novelty(text: str, killed: list[str]) -> float:
    """1.0 = nothing like it in the do-not-repeat list, 0.0 = an exact family match.

    Token-overlap against 42 already-killed families. Coarse on purpose: the job here is to stop
    the factory spending budget re-deriving `funding_carry`, not to adjudicate near-misses -- and
    a scorer that claims more precision than substring matching has would be lying about it.
    """
    t = text.lower().replace("-", "_")
    for k in killed:
        kk = str(k).lower().replace("-", "_")
        if kk and kk in t:
            return 0.0
    words = {w for w in t.replace("_", " ").split() if len(w) > 3}
    if not words:
        return 1.0
    hits = sum(1 for k in killed
               if {w for w in str(k).lower().replace("_", " ").split() if len(w) > 3} & words)
    return max(0.0, 1.0 - hits / max(4.0, len(killed) / 4.0))


def _candidates(agenda: dict[str, Any], deployed: list[str],
                killed: list[str]) -> list[IdeaCandidate]:
    out: list[IdeaCandidate] = []
    queue = agenda.get("queue_ranked_by_expected_research_roi", [])
    n = max(1, len(queue))
    for i, q in enumerate(queue):
        if not isinstance(q, dict):
            continue
        text = f"{q.get('id','')} {q.get('family','')} {q.get('mechanism','')}"
        # `rank` is hand-maintained and is sometimes prose ("low-rank (near-miss; re-estimate at
        # panel)"). An unparseable rank sorts to the BACK rather than raising or being treated as
        # rank 1 -- the desk wrote words instead of a number precisely when it was unsure.
        # A RANK BELOW 1 IS UNRANKED, NOT BETTER-THAN-FIRST -- and the difference crashed this
        # organ on its very first candidate, so it has never run against real desk data.
        # `research_agenda.json` carries `rank: 0` on 12 of its 20 rows (the axis generator writes
        # a STRING rank, so a 0 means nobody ranked it). Feeding 0 into the prior below gives
        # 1.0 - (0-1)/20 = 1.05, and `IdeaCandidate.expected_edge` is bounded `le=1.0`, so pydantic
        # raised before the first candidate was built. The one-sided `max(0.0, ...)` guarded only
        # the direction the author was thinking about.
        # Unranked is treated exactly as an unparseable rank already is -- sorted to the BACK --
        # because a 0 means the desk did not rank it, and reading that as the top prior would let
        # the unranked out-rank everything the desk actually ranked.
        try:
            rank = float(q.get("rank", i + 1))
            if rank < 1.0:
                rank = float(n)
        except (TypeError, ValueError):
            rank = float(n)
        # the agenda's own rank is the desk's stated prior; converted to 0-1 so the factory's
        # ranking can AGREE or DISAGREE with it visibly rather than silently re-deriving it.
        # Clamped BOTH ends. The comment above says "converted to 0-1"; the arithmetic only ever
        # guaranteed >= 0, so any future rank the desk invents can no longer kill the organ.
        prior = min(1.0, max(0.0, 1.0 - (rank - 1.0) / n))
        out.append(IdeaCandidate(
            idea_id=str(q.get("id", f"idea_{i}")),
            category=str(q.get("family", "uncategorised")),
            statement=str(q.get("mechanism", ""))[:400],
            expected_edge=round(prior, 3),
            expected_robustness=round(prior * 0.8, 3),
            expected_capacity=0.5,
            novelty=round(_novelty(text, killed), 3),
            crowding=_CROWDING["unknown"],
            regime_need=0.0,
            # a family the desk has NOT deployed is a portfolio gap by definition
            portfolio_need=0.0 if str(q.get("family", "")) in deployed else 1.0,
        ))
    return out


#: The desk's free-text family names -> the Stage-13 AlphaCategory vocabulary the allocator
#: budgets against. An explicit table rather than a fuzzy match: the allocator splits research
#: budget by category, so a silently mis-mapped family sends effort at the wrong thing, and a
#: silently DROPPED family gets no budget at all while still looking present in the queue.
_FAMILY_TO_CATEGORY = {
    "cross-exchange": AlphaCategory.STATISTICAL_ARBITRAGE,
    "derivative-microstructure": AlphaCategory.MICROSTRUCTURE,
    "derivative-data": AlphaCategory.MICROSTRUCTURE,
    "execution-alpha": AlphaCategory.MARKET_MAKING,
    "on-chain-flow": AlphaCategory.ALTERNATIVE_DATA,
    "options": AlphaCategory.OPTIONS,
    "crypto-sleeve": AlphaCategory.CARRY,
}


def _categories(pipeline: dict[str, Any], agenda: dict[str, Any]) -> tuple[
        list[AlphaCategory], list[str]]:
    """(categories for the allocator, family names that had no mapping).

    Unmapped names are RETURNED, not swallowed. The first version caught the exception and
    continued, which produced "7 candidates over 0 categories" and looked like a working run --
    a research budget allocated across nothing.
    """
    names = {str(a.get("category")) for a in pipeline.get("alphas", [])
             if isinstance(a, dict) and a.get("category")}
    names |= {str(q.get("family")) for q in
              agenda.get("queue_ranked_by_expected_research_roi", [])
              if isinstance(q, dict) and q.get("family")}
    names.discard("None")
    cats, unmapped = set(), []
    for nm in sorted(names):
        cat = _FAMILY_TO_CATEGORY.get(nm)
        if cat is None:
            unmapped.append(nm)
            cats.add(AlphaCategory.OTHER)
        else:
            cats.add(cat)
    return sorted(cats), unmapped


def _dna_of(alpha: dict[str, Any]) -> Any:
    """Coarse DNA from what alpha_pipeline.json actually records.

    Only category, crowding and expected Sharpe are available, so timeframe/holding are marked
    `unknown` rather than guessed -- an invented timeframe would make two unrelated concepts look
    like siblings to the similarity engine, which is exactly the judgement it exists to make.
    """
    return build_alpha_dna(
        signal_type=str(alpha.get("category", "unknown")),
        market="crypto",
        timeframe="unknown",
        holding_period=str(alpha.get("expected_half_life", "unknown")),
        capacity_estimate=0.0,
        risk_profile=_CROWDING.get(str(alpha.get("crowding_risk", "unknown")), 0.5),
    )


def main() -> int:
    agenda = _load(_AGENDA, {})
    pipeline = _load(_PIPELINE, {})
    if not agenda and not pipeline:
        print("alpha factory: no research_agenda.json / alpha_pipeline.json -- nothing to do")
        return 0

    killed = [str(x) for x in agenda.get("do_not_repeat", []) if isinstance(x, str)]
    deployed = [str(x) for x in pipeline.get("deployed", [])]
    alphas = [a for a in pipeline.get("alphas", []) if isinstance(a, dict)]

    cands = _candidates(agenda, deployed, killed)
    cats, unmapped_families = _categories(pipeline, agenda)
    if not cands:
        print("alpha factory: research queue is empty -- no candidates to coordinate")
        return 0

    # The factory needs a Database for ResearchMemory. Kept IN-MEMORY and migrated fresh each
    # run: a recommendation pass must never be able to write production state, and the
    # governance guards on the controller only cover the methods, not the connection it holds.
    from migrations import MIGRATIONS

    from libs.store.connection import Database
    from libs.store.migrations import run_migrations
    db = Database(":memory:")
    run_migrations(db, MIGRATIONS)
    ctl = AlphaFactoryController(db)

    portfolio_gaps = {c.category: 1.0 for c in cands if c.portfolio_need > 0}
    crowding = {c.category: c.crowding for c in cands}
    report = ctl.run(candidates=cands, categories=cats,
                     portfolio_gaps=portfolio_gaps, crowding=crowding)

    assessments = [ctl.assess(candidate=c, adv_usd=_ADV_FALLBACK_USD) for c in cands]

    # duplication: does any candidate's family already exist in the deployed book?
    deployed_dna = {f"deployed::{a['alpha']}": _dna_of(a) for a in alphas
                    if str(a.get("alpha", "")).split("::")[-1] in deployed
                    or str(a.get("alpha", "")) in deployed}
    cand_dna = {c.idea_id: build_alpha_dna(signal_type=c.category, market="crypto",
                                           timeframe="unknown", holding_period="unknown")
                for c in cands}
    clusters = [c for c in ctl.duplicates_of(cand_dna, deployed_dna) if len(c) > 1]

    for a in alphas:
        ctl.record_lineage(str(a.get("alpha", "?")), mutation_type="pipeline",
                           performance=float(a.get("expected_sharpe", 0.0) or 0.0))

    nearest = {}
    for cid, d in cand_dna.items():
        if deployed_dna:
            k, dd = min(((k, dna_distance(d, v)) for k, v in deployed_dna.items()),
                        key=lambda kv: kv[1])
            nearest[cid] = {"closest_deployed": k, "dna_distance": round(dd, 4)}

    out = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "n_candidates": len(cands),
        "n_categories": len(cats),
        "unmapped_families": unmapped_families,
        "n_killed_families_screened": len(killed),
        "deployed": deployed,
        "research_priorities": [
            {"idea_id": p.idea_id, "category": p.category,
             "priority": round(p.idea_priority_score, 2), "components": p.components}
            for p in report.research_priorities],
        "allocation": (report.allocation.allocations if report.allocation else {}),
        "allocation_rationale": (report.allocation.rationale if report.allocation else {}),
        "assessments": assessments,
        "duplicate_clusters": clusters,
        "nearest_deployed": nearest,
        "portfolio_gaps": report.portfolio_gaps,
        "best_lineage": [n.alpha_id for n in ctl.family_tree.best_lineage()],
        "notes": report.notes,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")

    top = out["research_priorities"][:3]
    print(f"alpha factory: {len(cands)} candidates over {len(cats)} categories, "
          f"screened against {len(killed)} killed families")
    if unmapped_families:
        print(f"  UNMAPPED families (budgeted as OTHER, add to _FAMILY_TO_CATEGORY): "
              f"{', '.join(unmapped_families)}")
    for p in top:
        a = next((x for x in assessments if x["idea_id"] == p["idea_id"]), {})
        print(f"  {p['priority']:5.1f}  {p['idea_id']:<32} "
              f"research_score={a.get('research_score', 0):.1f} "
              f"scalability={a.get('scalability_score', 0):.0f}")
    if clusters:
        print(f"  DUPLICATE clusters vs deployed: {clusters}")
    # a display path must never be able to fail the run: _OUT is relocatable (tests, and
    # any operator who redirects it), and relative_to() raises outside the repo root.
    try:
        shown = _OUT.relative_to(_ROOT)
    except ValueError:
        shown = _OUT
    print(f"  -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
