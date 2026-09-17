"""THE ARCHAEOLOGY CIVILIZATION -- twenty families a pass, every source paid by measured survivors.

THE PRINCIPAL'S ORDER (2026-09-17, permanent): turn the entire observable history of trading
systems, traders, bots, competitions, products, code and failed experiments into mechanism
hypotheses for the gauntlet. Copy-trading is five to ten percent of it.

WHAT THIS ORGAN IS. One bounded pass over twenty families of archaeology -- populations,
competitions, products, code, forums, lineages, institutions, graveyards, trade paths,
fingerprints, decompiled mechanisms, counterfactuals, a controlled candidate explosion, cross-era
synthesis, version evolution, negative space, crowding, survivorship, source archaeology and the
permanent source scout -- inside a budget, with each family's output measured or named UNMEASURED,
and one report: `desks/mt5/reports/TRADING_ARCHAEOLOGY.json`.

HOW THE HOUR IS SPENT, AND WHY IT IS NOT SPENT EVENLY. Platform budgets are set by MEASURED ROI
off the registry's own `source_yield` -- independent survivors per compute second first, survivors
second, claims last -- shrunk toward a prior so a ground that got lucky once does not own the hour,
with an exploration floor so a ground nobody has measured is tried rather than starved. A source
earns its budget by producing survivors; it never earns it by being famous.

THE SOURCE SCOUT IS PERMANENT, because the coverage ceiling is set by what the desk KNOWS ABOUT.
Every pass scores candidate grounds by

    V_s = observability x verification x mechanism_inferability x novelty x P(useful descendant)
          / (selection bias + collection cost + legal/access cost)

and registers them with a `machine_use_allowed` decided from robots or terms WHEN READABLE and
`unknown` otherwise -- and unknown resolves to NOT FETCHED. A ground that forbids automated
extraction is registered as unavailable and is never fetched, on this pass or any later one.

    python desks/mt5/research/archaeology/civilization.py --budget-s 600
    python desks/mt5/research/archaeology/civilization.py --dry-run --no-fetch
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_DESK = Path(__file__).resolve().parents[2]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402
import moat_collectors as mc  # noqa: E402
import source_frontier as sf  # noqa: E402
import transformation_miners as TM  # noqa: E402
from archaeology import decompiler as dc  # noqa: E402
from archaeology import phenotype as ph  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

from libs.moat import registry as reg  # noqa: E402

UNMEASURED = "UNMEASURED"
REPORT: Path = _DESK / "reports" / "TRADING_ARCHAEOLOGY.json"
BUDGET_S = 600.0
#: Never spend less than this on a platform the pass chose: below it a fetch cannot finish and
#: the slot is spent proving nothing.
MIN_PLATFORM_S = 8.0
#: The ROI prior. A platform with no measured yield is not zero -- it is UNMEASURED, and it gets
#: the prior's share so the pass keeps exploring rather than re-reading its three best grounds.
PRIOR_NUM, PRIOR_S = 0.25, 60.0
MAX_EXPLOSION = 60
RULE = ("public trading history is a prior generator for the gauntlet: phenotypes, archetypes and "
        "decompiled mechanisms, never copied trades; winners and graveyards alike; every source "
        "earns its budget by measured survivors")


@dataclass(frozen=True)
class Family:
    """One of the twenty. `stage` says which pass of the organ does its work."""

    name: str
    what: str
    stage: str


FAMILIES: tuple[Family, ...] = (
    Family("performance_archaeology", "periodic snapshots of every accessible track-record "
           "population: winners, mediocre, failed, removed", "snapshot"),
    Family("competition_archaeology", "championship and contest standings, archived: LEADS, "
           "never evidence", "snapshot"),
    Family("product_archaeology", "EA/product descriptions, parameters, symbols, timeframe, "
           "update history, reviews, changelog, claimed mechanism", "snapshot"),
    Family("code_archaeology", "repositories, commit history, deleted approaches, parameter "
           "changes, abandoned branches", "snapshot"),
    Family("forum_archaeology", "the forum era by year, including the dead boards", "snapshot"),
    Family("trader_lineage", "one author across forum -> product -> account -> failure -> new "
           "system, as a genealogy", "lineage"),
    Family("institutional_archaeology", "filings, letters, patents, papers, talks: lawfully "
           "observable FUNCTIONS, never undisclosed positions", "snapshot"),
    Family("failure_graveyard", "the native-language failure vocabulary in six languages: blown "
           "accounts, dead EAs, broker changes, spread kills", "failure"),
    Family("trade_path_reconstruction", "observable timestamps aligned to the desk's PIT bars: "
           "state at entry, session, vol, add-ons, exits, inactivity", "phenotype"),
    Family("behavioural_fingerprinting", "phi over fourteen dimensions and the archetype "
           "clustering", "phenotype"),
    Family("mechanism_decompiler", "competing explanations per archetype with falsifiers",
           "decompile"),
    Family("counterfactual_reconstruction", "strip leverage, martingale, concentration and the "
           "good window; does the information still pay", "decompile"),
    Family("candidate_explosion", "the twelve transformation miners under an EVIG/UCB budget, "
           "never the Cartesian product", "explode"),
    Family("cross_archaeology_synthesis", "the same mechanism across eras, countries and "
           "platforms is a stronger prior", "synthesis"),
    Family("evolution_mining", "what changed in successive versions before performance moved",
           "evolution"),
    Family("negative_space", "what successful systems avoid: hours, sessions, weekdays, symbols",
           "phenotype"),
    Family("crowding_ecology", "thousands converging on one structure is congestion, and "
           "congestion is a mechanism", "phenotype"),
    Family("survivorship", "P(survive_{t+h} | phi_t) from prospective snapshots", "survivorship"),
    Family("source_archaeology", "authors, communities, competitions, platforms and periods "
           "scored by DOWNSTREAM survivors", "scout"),
    Family("source_scout", "new grounds scored by V_s, registered with machine_use_allowed",
           "scout"),
)

#: THE GRAVEYARD'S OWN VOCABULARY, in the languages the failures were written in. A blown account
#: is described the same way everywhere and indexed nowhere: these are the strings that find it.
FAILURE_VOCAB: dict[str, tuple[str, ...]] = {
    "en": ("blew the account", "blown account", "margin call", "stopped working", "no longer "
           "works", "backtest failed live", "curve fitted", "martingale blew", "broker change "
           "killed", "spread destroyed", "ea died", "account wiped"),
    "ru": ("слил счет", "слил депозит", "маржин колл", "перестал работать", "слив депозита",
           "поделка", "перестала работать"),
    "zh": ("爆仓", "亏损出局", "策略失效", "回测好实盘差", "穿仓", "止损失效"),
    "ja": ("破産", "強制ロスカット", "資金溶かした", "機能しなくなった", "バックテストと乖離"),
    "ko": ("깡통", "마진콜", "전략이 안 먹힌다", "계좌 터짐"),
    "es": ("quemé la cuenta", "llamada de margen", "dejó de funcionar", "cuenta liquidada"),
    "pt": ("estourei a conta", "chamada de margem", "parou de funcionar", "conta zerada"),
}
#: The scout's factor tables. Every factor is in (0, 1]; every cost is in [0, 1].
OBSERVABILITY: dict[str, float] = {"track_record": 0.90, "code": 0.85, "competition": 0.75,
                                   "product": 0.60, "forum": 0.50, "institutional": 0.40,
                                   "archive": 0.55}
INFERABILITY: dict[str, float] = {"track_record": 0.75, "code": 0.95, "competition": 0.55,
                                  "product": 0.60, "forum": 0.45, "institutional": 0.35,
                                  "archive": 0.45}
SELECTION_BIAS: dict[str, float] = {"track_record": 0.55, "competition": 0.80, "product": 0.60,
                                    "code": 0.25, "forum": 0.30, "institutional": 0.35,
                                    "archive": 0.30}
COLLECTION_COST: dict[str, float] = {"track_record": 0.30, "code": 0.20, "competition": 0.35,
                                     "product": 0.30, "forum": 0.45, "institutional": 0.55,
                                     "archive": 0.40}
LEGAL_COST: dict[str, float] = {snap.ALLOWED: 0.05, snap.UNKNOWN: 0.50, snap.FORBIDDEN: 1.00}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- budgets by ROI
def _yields(conn: Any) -> dict[str, dict[str, Any]]:
    try:
        return {str(r["source_id"]): dict(r)
                for r in conn.execute("SELECT * FROM source_yield")}
    except Exception:
        return {}


def source_id_of(platform: str) -> str:
    return f"archaeology:{platform}"


def platform_budgets(platforms: Sequence[snap.Platform], budget_s: float, conn: Any
                     ) -> list[dict[str, Any]]:
    """Per-platform seconds, by MEASURED ROI with an exploration floor.

    The numerator is the registry's own downstream measure -- independent survivors first, then
    survivors, then claims at a twentieth of the weight -- because a ground is paid for what it
    produced at the END of the pipeline, never for how much it emitted at the start. Shrunk toward
    a prior so one lucky pass cannot own the hour, and floored so an unmeasured ground is tried.
    """
    ys = _yields(conn)
    rows: list[dict[str, Any]] = []
    for p in platforms:
        y = ys.get(source_id_of(p.name)) or {}
        num = (float(y.get("independent_survivors") or 0.0)
               + 0.5 * float(y.get("survivors") or 0.0)
               + 0.05 * float(y.get("claims") or 0.0))
        compute = float(y.get("compute_s") or 0.0)
        weight = (num + PRIOR_NUM) / (compute + PRIOR_S)
        rows.append({"platform": p.name, "kind": p.kind, "family": p.family,
                     "roi": [round(v, 8) for v in mc.source_roi(y or None)],
                     "measured": bool(y), "weight": round(weight, 8),
                     "basis": ("registry source_yield" if y else
                               "UNMEASURED: no yield row yet -- this platform draws the "
                               "exploration prior, which is a floor, not a score")})
    total = sum(r["weight"] for r in rows) or 1.0
    for r in rows:
        r["budget_s"] = round(max(MIN_PLATFORM_S, budget_s * r["weight"] / total), 2)
    rows.sort(key=lambda r: (-r["weight"], r["platform"]))
    return rows


# --------------------------------------------------------------------------- the source scout
def _machine_use_from_robots(url: str, *, fetch: bool) -> tuple[str, str]:
    """Read the operator's own policy when it is readable -- reading robots.txt is always
    permitted and is what it is for -- and answer `unknown` otherwise. Unknown is NOT FETCHED."""
    host = urlparse(url).netloc
    if not host:
        return snap.UNKNOWN, "no host in the candidate url"
    if not fetch:
        return snap.UNKNOWN, ("--no-fetch: the operator's policy was not read, so automated use "
                              "is unknown and this ground is not fetched")
    body, status, err = mc.fetch_text(f"https://{host}/robots.txt")
    if not body:
        return snap.UNKNOWN, (f"robots.txt unreadable (status {status}{', ' + err if err else ''})"
                              ": absence of a readable permission is not permission")
    low = body.lower()
    for agent in ("claudebot", "anthropic", "gptbot", "ccbot"):
        if agent in low:
            return snap.FORBIDDEN, f"robots.txt names the agent family ({agent}) on {host}"
    if "user-agent: *" in low and "disallow: /\n" in low.replace("\r", ""):
        return snap.FORBIDDEN, f"robots.txt carries a wildcard Disallow: / on {host}"
    return snap.ALLOWED, f"robots.txt on {host} is readable and refuses neither this agent nor all"


def v_s(candidate: Mapping[str, Any], *, known_on_host: int = 0,
        host_yield: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """THE SOURCE SCOUT'S SCORE, with every factor named and every cost paid.

        V_s = observability x verification x mechanism_inferability x novelty
              x P(useful descendant) / (selection bias + collection cost + legal/access cost)

    A forbidden ground scores near zero because its legal cost is 1.0, not because it is filtered:
    the score stays visible so the desk can see what it is refusing rather than losing the row.
    """
    kind = str(candidate.get("kind") or "forum")
    access = str(candidate.get("machine_use_allowed") or snap.UNKNOWN)
    verification = snap.VERIFICATION.get(str(candidate.get("verification_class") or "unverified"),
                                         0.15)
    observability = OBSERVABILITY.get(kind, 0.45)
    inferability = INFERABILITY.get(kind, 0.40)
    novelty = 1.0 / (1.0 + float(max(0, known_on_host)))
    hy = dict(host_yield or {})
    compute = max(float(hy.get("compute_s") or 0.0), 1.0)
    measured = float(hy.get("independent_survivors") or 0.0) / compute
    p_useful = min(0.95, 0.15 + 4.0 * measured) if hy else 0.15
    selection = SELECTION_BIAS.get(kind, 0.40)
    collection = COLLECTION_COST.get(kind, 0.40)
    legal = LEGAL_COST.get(access, 0.50)
    cost = max(selection + collection + legal, 0.10)
    score = (observability * verification * inferability * novelty * p_useful) / cost
    return {"v_s": round(score, 8),
            "factors": {"observability": observability, "verification": verification,
                        "mechanism_inferability": inferability, "novelty": round(novelty, 6),
                        "p_useful_descendant": round(p_useful, 6)},
            "costs": {"selection_bias": selection, "collection_cost": collection,
                      "legal_access_cost": legal, "total": round(cost, 6)},
            "p_useful_basis": ("measured host yield" if hy else
                               "UNMEASURED host: the 0.15 prior, never a zero")}


def scout(conn: Any, *, discovered: Sequence[Mapping[str, Any]] = (), fetch: bool = False,
          limit: int = 25, dry_run: bool = False) -> dict[str, Any]:
    """Score and register candidate grounds. Nothing here fetches CONTENT; at most it reads an
    operator's robots.txt, which is what robots.txt is published for."""
    try:
        known = sf.sources(conn=conn)
    except Exception:
        known = {}
    hosts: dict[str, int] = {}
    for row in known.values():
        host = str(row.get("url") or "").split("/")[2] if "//" in str(row.get("url") or "") else ""
        if host:
            hosts[host] = hosts.get(host, 0) + 1
    ys = _yields(conn)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    pool: list[Mapping[str, Any]] = [
        *({"name": p.name, "url": p.root, "kind": p.kind, "region": p.region,
           "language": p.language, "verification_class": p.verification_class,
           "machine_use_allowed": snap.machine_use(p)[0], "why": snap.machine_use(p)[1],
           "found_via": "platform table"} for p in snap.PLATFORMS),
        *discovered]
    for cand in pool:
        sid = source_id_of(str(cand.get("name") or cand.get("url") or ""))
        if sid in seen:
            continue
        seen.add(sid)
        url = str(cand.get("url") or "")
        host = url.split("/")[2] if "//" in url else ""
        access = str(cand.get("machine_use_allowed") or "")
        why = str(cand.get("why") or "")
        if not access:
            access, why = _machine_use_from_robots(url, fetch=fetch)
        score = v_s({**cand, "machine_use_allowed": access},
                    known_on_host=hosts.get(host, 0),
                    host_yield=ys.get(sid))
        candidates.append({**dict(cand), "source_id": sid, "host": host,
                           "machine_use_allowed": access, "access_why": why[:240],
                           "registered": False, "fetchable": access == snap.ALLOWED, **score})
    candidates.sort(key=lambda c: -float(c["v_s"]))
    registered = 0
    for cand in candidates[:limit]:
        if dry_run:
            continue
        try:
            new = sf.register_source(
                str(cand["source_id"]), url=str(cand.get("url") or ""),
                kind=str(cand.get("kind") or ""), language=str(cand.get("language") or ""),
                country=str(cand.get("region") or ""),
                discovered_from="archaeology.civilization.scout",
                discovered_via=str(cand.get("found_via") or "scout"),
                status=("active" if cand["fetchable"] else "candidate"),
                licence_note=("WEB-PUBLIC; concept reimplemented, provenance cited, nothing "
                              "copied" if cand["fetchable"] else
                              f"NOT FETCHED ({cand['machine_use_allowed']}): "
                              f"{cand['access_why']}"),
                meta={"machine_use_allowed": cand["machine_use_allowed"],
                      "verification_class": cand.get("verification_class"),
                      "v_s": cand["v_s"], "factors": cand["factors"], "costs": cand["costs"],
                      "family": cand.get("family")},
                conn=conn)
        except Exception as exc:
            cand["register_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            continue
        cand["registered"] = True
        cand["new_source"] = bool(new)
        registered += int(bool(new))
    return {"n_candidates": len(candidates), "n_registered_new": registered,
            "scored": candidates[:limit],
            "never_fetched": sorted({str(c["source_id"]) for c in candidates
                                     if not c["fetchable"]}),
            "formula": "V_s = observability x verification x mechanism_inferability x novelty x "
                       "P(useful descendant) / (selection bias + collection cost + legal cost)",
            "rule": "a ground that forbids automated extraction is registered as unavailable and "
                    "never fetched; unknown resolves to not fetched"}


# --------------------------------------------------------------------------- the small families
def failure_scan(texts: Sequence[str]) -> dict[str, Any]:
    """FAMILY 8. The graveyard's own words, in six languages. A hit is a LEAD to a failure story,
    and a failure story names a mechanism that stopped paying -- which is negative knowledge the
    desk did not have to buy."""
    hits: dict[str, list[str]] = {}
    for text in texts:
        low = str(text or "").lower()
        for lang, words in FAILURE_VOCAB.items():
            for w in words:
                if w.lower() in low:
                    hits.setdefault(lang, []).append(w)
    if not texts:
        return {"status": UNMEASURED, "why": "no captured text this pass to scan",
                "languages": sorted(FAILURE_VOCAB)}
    return {"status": "measured", "n_texts": len(texts),
            "by_language": {k: sorted(set(v)) for k, v in sorted(hits.items())},
            "n_hits": sum(len(v) for v in hits.values()),
            "languages": sorted(FAILURE_VOCAB)}


def lineage(population: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """FAMILY 6. One author across platforms is a GENEALOGY, and a genealogy is the only place a
    failure and its successor can be seen as one story rather than two rows."""
    by_author: dict[str, list[dict[str, Any]]] = {}
    for row in population:
        author = str((row.get("raw") or {}).get("author") if isinstance(row.get("raw"), Mapping)
                     else "") or str(row.get("author") or "")
        if author:
            by_author.setdefault(author, []).append(dict(row))
    chains = [{"author": a, "n": len(rows),
               "platforms": sorted({str(r.get("platform")) for r in rows}),
               "systems": sorted({str(r.get("system_id")) for r in rows})[:20]}
              for a, rows in by_author.items() if len(rows) > 1]
    chains.sort(key=lambda c: (-len(c["platforms"]), -c["n"]))
    if not by_author:
        return {"status": UNMEASURED, "why": "no population row carries an author; lineage is "
                                             "unmeasured, not absent"}
    return {"status": "measured", "n_authors": len(by_author), "n_chains": len(chains),
            "cross_platform": [c for c in chains if len(c["platforms"]) > 1][:20],
            "top": chains[:20]}


#: THE RECURSIVE EXPANSION LADDER (principal, 2026-09-17). A recovered source is never the end of
#: a branch: it names PEOPLE, who wrote PAPERS, which used DATASETS, which shipped as APPS, which
#: were argued about in FORUMS, where the CODE was posted, which names new SOURCES. The ladder is
#: a cycle on purpose -- that is what makes it recursive rather than a seven-step pipeline.
EXPANSION_LADDER: tuple[str, ...] = ("source", "people", "papers", "datasets", "apps", "forums",
                                     "code", "sources")
#: Marginal value decays with depth: a ground four hops from the seed is four inferences from the
#: evidence, and the desk pays for evidence.
HOP_DECAY = 0.65
MAX_EXPANSION_NODES = 120


def expand_recursively(seeds: Sequence[Mapping[str, Any]], *, neighbours: Any,
                       opportunity_floor: float, max_nodes: int = MAX_EXPANSION_NODES,
                       max_hops: int = len(EXPANSION_LADDER), conn: Any = None) -> dict[str, Any]:
    """EVERY RECOVERED SOURCE EXPANDS UNTIL ITS MARGINAL VALUE FALLS BELOW OTHER OPPORTUNITIES,
    and the STOPPING REASON IS RECORDED -- for the whole walk and for every branch that ends.

    THE STOP IS THE PRODUCT, not the walk. An expansion that runs out of budget and an expansion
    that ran out of value are the same empty frontier to anybody reading the output later, and
    they imply opposite next actions: the first is owed compute, the second is finished ground.
    So every branch ends with one of four named reasons -- `marginal_value_below_opportunity`,
    `node_budget`, `hop_ladder_exhausted`, `frontier_exhausted` -- and the counts are reported.

    `opportunity_floor` is the value of the BEST ALTERNATIVE this hour could buy instead (the
    organ passes the median V_s of the platforms already in its budget), so "below other
    opportunities" is a measured comparison rather than a constant somebody chose.
    """
    frontier: list[dict[str, Any]] = [
        {**dict(s), "hop": 0, "hop_kind": "source", "value": float(s.get("v_s") or 1.0),
         "parent": ""} for s in seeds]
    if not frontier:
        return {"status": UNMEASURED, "why": "no recovered source to expand from this pass",
                "ladder": list(EXPANSION_LADDER)}
    seen: set[str] = {str(n.get("url") or n.get("name") or "") for n in frontier}
    visited: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = []
    while frontier:
        frontier.sort(key=lambda n: -float(n["value"]))
        node = frontier.pop(0)
        if len(visited) >= max_nodes:
            stops.append({"node": node.get("name"), "hop": node["hop"],
                          "reason": "node_budget",
                          "why": f"{max_nodes} nodes walked this pass; the branch is OWED, not "
                                 "exhausted -- it resumes from here next pass"})
            continue
        if float(node["value"]) < opportunity_floor:
            stops.append({"node": node.get("name"), "hop": node["hop"],
                          "reason": "marginal_value_below_opportunity",
                          "why": f"marginal value {float(node['value']):.4f} is below the best "
                                 f"alternative this hour ({opportunity_floor:.4f}); this ground "
                                 "is finished for now, not unreachable"})
            continue
        if node["hop"] >= max_hops:
            stops.append({"node": node.get("name"), "hop": node["hop"],
                          "reason": "hop_ladder_exhausted",
                          "why": f"the ladder {' -> '.join(EXPANSION_LADDER)} completed one full "
                                 "cycle from this seed"})
            continue
        visited.append(node)
        try:
            kids = list(neighbours(node) or [])
        except Exception as exc:
            stops.append({"node": node.get("name"), "hop": node["hop"],
                          "reason": "frontier_exhausted",
                          "why": f"neighbour lookup raised {type(exc).__name__}: {str(exc)[:120]}"
                                 " -- counted, never swallowed"})
            continue
        fresh = 0
        for kid in kids:
            key = str(kid.get("url") or kid.get("name") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            fresh += 1
            hop = node["hop"] + 1
            frontier.append({
                **dict(kid), "hop": hop,
                "hop_kind": EXPANSION_LADDER[min(hop, len(EXPANSION_LADDER) - 1)],
                "parent": str(node.get("name") or node.get("url") or ""),
                # VALUE COMPOUNDS DOWN THE WALK, and it did not until 2026-09-17: the child took
                # its OWN v_s whenever it declared one, so a frontier of equally-rated neighbours
                # sat at a constant 0.65 forever and no branch could ever stop on value -- the
                # walk only ever ran out of budget or of links. The child's v_s is its RELATIVE
                # worth against its parent (1.0 when it does not say), so five hops of
                # equally-good neighbours decay to 0.65^5 and the marginal-value stop can fire,
                # which is the whole point of a recursion bounded by opportunity cost.
                "value": float(node["value"]) * float(kid.get("v_s", 1.0) or 1.0) * HOP_DECAY})
        if fresh == 0:
            stops.append({"node": node.get("name"), "hop": node["hop"],
                          "reason": "frontier_exhausted",
                          "why": "this node links to nothing the desk has not already seen"})
    by_reason: dict[str, int] = {}
    for s in stops:
        by_reason[s["reason"]] = by_reason.get(s["reason"], 0) + 1
    by_hop: dict[str, int] = {}
    for v in visited:
        by_hop[str(v["hop_kind"])] = by_hop.get(str(v["hop_kind"]), 0) + 1
    return {"status": "measured", "n_seeds": len(seeds), "n_visited": len(visited),
            "n_discovered": len(seen) - len(seeds), "max_hop": max((v["hop"] for v in visited),
                                                                   default=0),
            "opportunity_floor": round(float(opportunity_floor), 6),
            "by_hop_kind": by_hop, "stopped_by_reason": by_reason, "stops": stops[:40],
            "ladder": list(EXPANSION_LADDER),
            "discovered": [{"name": n.get("name"), "url": n.get("url"), "hop": n["hop"],
                            "hop_kind": n["hop_kind"], "parent": n.get("parent")}
                           for n in visited if n["hop"] > 0][:60],
            "rule": "expansion runs until marginal information value falls below other "
                    "opportunities, and the stopping reason is recorded for every branch"}


def _evig(child: Mapping[str, Any], seen_cells: Mapping[str, int]) -> float:
    """EXPECTED VALUE OF THE INFORMATION this child would buy: an EMPTY breadth cell is worth
    most, a crowded one least, and the transformation's own cost divides. This is what replaces
    the Cartesian product -- the closure is enumerated, the BUDGET is spent on its best members,
    and everything not built is owed rather than forgotten (L1.61)."""
    cell = reg.grid_cell(child)
    crowd = float(seen_cells.get(cell, 0))
    novelty = 1.0 / (1.0 + crowd)
    cost = 1.0 + 0.25 * float(len(child.get("params") or {}))
    return float(novelty / cost)


def explode(parents: Sequence[Mapping[str, Any]], ctx: TM.Context, *, budget: int = MAX_EXPLOSION,
            conn: Any = None) -> dict[str, Any]:
    """FAMILY 13. A CONTROLLED explosion: the twelve miners on every parent, then a UCB walk over
    the parents so the budget lands where the information is, never a product of every axis.

    UCB because the choice is a bandit: a parent that has produced novel cells deserves more of
    the budget, and a parent nobody has expanded yet must still be reachable -- the exploration
    term is what keeps the twelfth mechanism from being invisible behind the first.
    """
    if not parents:
        return {"status": UNMEASURED, "why": "no discovery parents this pass to expand"}
    try:
        seen = reg.grid_coverage(conn=conn)
    except Exception:
        seen = {}
    pulls: dict[int, int] = dict.fromkeys(range(len(parents)), 0)
    value: dict[int, float] = dict.fromkeys(range(len(parents)), 0.0)
    kept: list[dict[str, Any]] = []
    total = 0
    while len(kept) < budget and total < budget * 3:
        total += 1
        n = max(1, sum(pulls.values()))
        i = max(range(len(parents)), key=lambda j: (
            (value[j] / pulls[j] if pulls[j] else 1.0)
            + 1.4 * math.sqrt(math.log(n + 1) / (pulls[j] + 1))))
        pulls[i] += 1
        produced = TM.run_all(parents[i], ctx)
        children = [c for rows in produced.values() for c in rows]
        if not children:
            value[i] -= 0.1
            if all(p > 0 for p in pulls.values()):
                break
            continue
        scored = sorted(children, key=lambda c: -_evig(c, seen))
        take = scored[: max(1, budget // max(1, len(parents)))]
        for c in take:
            cell = reg.grid_cell(c)
            seen[cell] = int(seen.get(cell, 0)) + 1
            kept.append(c)
        value[i] += float(sum(_evig(c, seen) for c in take))
        if len(kept) >= budget:
            break
    return {"status": "measured", "n_parents": len(parents), "n_children": len(kept),
            "budget": budget, "pulls": {str(k): v for k, v in pulls.items() if v},
            "truncated": [dict(t) for t in ctx.truncated][:20],
            "notes": [dict(t) for t in ctx.notes][:20],
            "method": "twelve transformation miners per parent; UCB1 over parents; children "
                      "ranked by EVIG (empty breadth cell / transformation cost); never the "
                      "Cartesian product"}


# --------------------------------------------------------------------------- the pass
def _texts_from(pages: Sequence[tuple[str, str]]) -> list[str]:
    return [dfm.html_text(body)[:20000] for _url, body in pages]


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False, fetch: bool = True,
        conn: Any = None, fixtures: Mapping[str, Sequence[tuple[str, str]]] | None = None,
        bars: Any = None, trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        versions: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        expansion_neighbours: Any = None, probe: bool = False, at: str = "") -> dict[str, Any]:
    """ONE PASS OF THE CIVILIZATION. Returns the report payload; writes nothing when `dry_run`."""
    started = time.monotonic()
    close_after = conn is None
    c = conn if conn is not None else reg.connect()
    stamp = at or snap.today()
    report: dict[str, Any] = {
        "at": _now(), "snapshot_at": stamp, "budget_s": float(budget_s), "dry_run": bool(dry_run),
        "fetch": bool(fetch), "platforms": [], "budgets": [],
        "population": {"n": 0, "new": 0, "disappeared": 0, "by_platform": {}},
        "archetypes": [], "survivorship": {}, "decompiled": 0, "discoveries_recorded": 0,
        "synthesis_top": [], "negative_space_top": {}, "crowding_top": {},
        "source_scout": {}, "families": [], "counterfactuals": 0,
        "archive_layer": {}, "labels": {}, "quarantined": 0, "access_refused_rows": 0,
        "expansion": {}, "explanation_table": [], "unmeasured": [], "rule": RULE,
    }
    fam_status: dict[str, dict[str, Any]] = {
        f.name: {"name": f.name, "stage": f.stage, "what": f.what, "ran": False,
                 "produced": {}, "why": ""} for f in FAMILIES}
    try:
        report["platforms"] = snap.as_rows()
        budgets = platform_budgets(list(snap.PLATFORMS), budget_s * 0.55, c)
        report["budgets"] = budgets
        by_name = {b["platform"]: b for b in budgets}

        # ---- families 1-5, 7: the populations -------------------------------------------
        rows_all: list[dict[str, Any]] = []
        captured_pages: list[tuple[str, str]] = []
        diffs: dict[str, dict[str, Any]] = {}
        for p in snap.PLATFORMS:
            left = budget_s - (time.monotonic() - started)
            if left <= 0:
                report["unmeasured"].append("budget spent before every platform was reached; the "
                                            "remainder is owed, not empty")
                break
            pages = list((fixtures or {}).get(p.name) or [])
            before = snap.load_population(p.name)
            got = snap.snapshot(p, min(by_name.get(p.name, {}).get("budget_s", MIN_PLATFORM_S),
                                       left),
                                fetch=fetch, pages=pages, at=stamp, write=not dry_run,
                                probe=probe)
            report["population"]["by_platform"][p.name] = {
                "n": len(got["rows"]), "captures_new": got["captures_new"],
                "captures_duplicate": got["captures_duplicate"],
                "machine_use_allowed": got.get("machine_use_allowed"),
                "access_label": got.get("access_label"),
                "credibility": got.get("credibility"),
                "quarantined_rows": got.get("quarantined_rows", 0),
                "refused_rows": got.get("refused_rows", 0),
                "refused": got.get("refused", ""), "fetched": got.get("fetched", 0)}
            report["quarantined"] += int(got.get("quarantined_rows", 0))
            report["access_refused_rows"] += int(got.get("refused_rows", 0))
            report["unmeasured"].extend(got.get("unmeasured") or [])
            rows_all.extend(got["rows"])
            captured_pages.extend(got.get("bodies") or pages)
            prev_dates = sorted({str(r.get("snapshot_at")) for r in before} - {stamp})
            if prev_dates and got["rows"]:
                d = snap.diff(snap.load_population(p.name, prev_dates[-1]), got["rows"])
                diffs[p.name] = d
                report["population"]["disappeared"] += d["n_disappeared"]
                report["population"]["new"] += d["n_appeared"]
            st = fam_status.get(p.family)
            if st is not None:
                st["ran"] = st["ran"] or bool(got["rows"])
                st["produced"][p.name] = len(got["rows"])
        report["population"]["n"] = len(rows_all)
        # THE ARCHIVE LAYER: every region x archive-kind cell, ground or NAMED ABSENCE. And the
        # three labels, censused -- a population whose licence and credibility are not counted is
        # a population whose usability nobody can state.
        layer = snap.archive_layer()
        report["archive_layer"] = {**{k: v for k, v in layer.items() if k != "cells"},
                                   "absences": [f"{c['region']}/{c['archive_kind']}"
                                                for c in layer["cells"]
                                                if c["state"] == "NAMED_ABSENCE"]}
        census: dict[str, dict[str, int]] = {"access_label": {}, "credibility": {},
                                             "predictive_state": {}}
        for r in rows_all:
            for axis in census:
                key = str(r.get(axis) or UNMEASURED)
                census[axis][key] = census[axis].get(key, 0) + 1
        report["labels"] = census
        # QUARANTINED ROWS ARE KEPT AND EXCLUDED. They stay in the population file as evidence
        # objects and leave the pipeline here: nothing downstream fingerprints, clusters,
        # decompiles or donates an ACCESS_UNCLEAR row until its terms are resolved.
        usable_rows = [r for r in rows_all if r.get("usable", True)]
        report["population"]["usable"] = len(usable_rows)
        for name in ("performance_archaeology", "competition_archaeology", "product_archaeology",
                     "code_archaeology", "forum_archaeology", "institutional_archaeology"):
            if not fam_status[name]["ran"]:
                fam_status[name]["why"] = ("no accessible population this pass: every platform in "
                                           "this family is unknown/forbidden or unfetched")

        # ---- families 6, 8 -----------------------------------------------------------------
        lin = lineage(usable_rows)
        fam_status["trader_lineage"].update(ran=lin.get("status") == "measured", produced=lin,
                                            why=str(lin.get("why") or ""))
        fail = failure_scan(_texts_from(captured_pages))
        fam_status["failure_graveyard"].update(ran=fail.get("status") == "measured",
                                               produced=fail, why=str(fail.get("why") or ""))

        # ---- families 9, 10, 16, 17: the phenotypes ---------------------------------------
        phis = ph.fingerprint_population(usable_rows, bars, trade_paths)
        with_path = [p for p in phis if p["source"] == "trade_path"]
        fam_status["trade_path_reconstruction"].update(
            ran=bool(with_path), produced={"n_trade_path": len(with_path),
                                           "n_stats_only": len(phis) - len(with_path)},
            why=("" if with_path else "no platform in reach publishes a trade path; the trade-path "
                                      "phenotype is UNMEASURED, the stats phenotype stands"))
        arch = ph.archetypes(phis) if phis else {"status": UNMEASURED, "why": "no fingerprints"}
        report["archetypes"] = arch.get("clusters", [])
        report["archetype_stability"] = {k: arch.get(k) for k in
                                         ("k", "silhouette", "stability_rand", "split_half_rand",
                                          "stable", "warning", "method")}
        fam_status["behavioural_fingerprinting"].update(
            ran=arch.get("status") == "measured",
            produced={"n_phi": len(phis), "k": arch.get("k"),
                      "stability": arch.get("stability_rand")},
            why=str(arch.get("why") or ""))
        ns_rows = [(sid, list(tp)) for sid, tp in (trade_paths or {}).items()]
        ns_best: dict[str, Any] = {}
        for sid, tp in ns_rows:
            got = ph.negative_space(tp)
            if got.get("status") == "measured":
                ns_best = {"system_id": sid, **got}
                break
        report["negative_space_top"] = ns_best or {
            "status": UNMEASURED,
            "why": "negative space needs a trade path with enough entries; none in reach"}
        fam_status["negative_space"].update(ran=bool(ns_best), produced=ns_best,
                                            why=str(report["negative_space_top"].get("why") or ""))
        counts = ph.archetype_counts(arch.get("clusters", []))
        crowd = ph.crowding(counts)
        report["crowding_top"] = crowd
        fam_status["crowding_ecology"].update(ran=crowd.get("status") == "measured",
                                              produced=crowd, why=str(crowd.get("why") or ""))

        # ---- family 18: survivorship --------------------------------------------------------
        pop_all = [r for r in (snap.load_population() + ([] if not dry_run else rows_all))
                   if r.get("usable", True)]
        surv = ph.survivorship(pop_all, phis=phis)
        report["survivorship"] = surv
        fam_status["survivorship"].update(ran=surv.get("status") == "measured", produced={
            "n_snapshots": surv.get("n_snapshots"),
            "horizons": list((surv.get("horizons") or {}).keys())},
            why=str(surv.get("why") or ""))

        # ---- families 11, 12: decompile ------------------------------------------------------
        decompiled: list[dict[str, Any]] = []
        recorded = 0
        for cluster in arch.get("clusters", []):
            got = dc.decompile(cluster, source_id=source_id_of("archetypes"),
                               family="behavioural_fingerprinting", trade_paths=trade_paths,
                               bars=bars, conn=c, dry_run=dry_run)
            decompiled.append(got)
            recorded += int(got["discoveries"]["recorded"])
            if got["counterfactual"].get("status") == "measured":
                report["counterfactuals"] += 1
        report["decompiled"] = len(decompiled)
        report["discoveries_recorded"] = recorded
        report["explanation_table"] = dc.explanation_table(
            [str(cl.get("archetype")) for cl in arch.get("clusters", [])])
        fam_status["mechanism_decompiler"].update(
            ran=bool(decompiled), produced={"archetypes": len(decompiled),
                                            "discoveries": recorded},
            why=("" if decompiled else "no archetype to decompile this pass"))
        fam_status["counterfactual_reconstruction"].update(
            ran=bool(report["counterfactuals"]),
            produced={"measured": report["counterfactuals"]},
            why=("" if report["counterfactuals"] else
                 "no archetype member publishes a trade path: the counterfactual is UNMEASURED"))

        # ---- family 14: synthesis ------------------------------------------------------------
        mech_rows: list[dict[str, Any]] = []
        for row in usable_rows:
            fp = next((x for x in phis if x.get("system_id") == row.get("system_id")), None)
            cl = next((cl for cl in arch.get("clusters", [])
                       if str(row.get("system_id")) in (cl.get("members") or [])), None)
            if cl is None or fp is None:
                continue
            mech_rows.extend(dc.mechanism_rows(
                str(cl.get("archetype")), platform=str(row.get("platform")),
                era=dc.era_of(str(row.get("snapshot_at"))), region=str(row.get("region") or ""),
                source_id=str(row.get("system_id"))))
        syn = dc.synthesis(mech_rows)
        report["synthesis_top"] = syn[:15]
        fam_status["cross_archaeology_synthesis"].update(
            ran=bool(syn), produced={"n_mechanisms": len(syn)},
            why=("" if syn else "no mechanism observed on two grounds this pass"))

        # ---- family 15: evolution -------------------------------------------------------------
        evos = {k: dc.evolution(v) for k, v in (versions or {}).items()}
        measured_evo = {k: v for k, v in evos.items() if v.get("status") == "measured"}
        report["evolution"] = {"n_products": len(evos), "measured": len(measured_evo),
                               "top": list(measured_evo.values())[:5]}
        fam_status["evolution_mining"].update(
            ran=bool(measured_evo), produced={"n_products": len(evos)},
            why=("" if measured_evo else "no product version history in reach: version evolution "
                                         "is UNMEASURED this pass"))

        # ---- family 13: the controlled explosion ------------------------------------------------
        parents = [dict(d) for d in reg.discoveries(state="UNPROCESSED", origin=dc.ORIGIN,
                                                    limit=20, conn=c)] if not dry_run else []
        ctx = TM.Context(instruments={}, max_per_miner=4)
        boom = explode([_parent_spec(p) for p in parents], ctx,
                       budget=min(MAX_EXPLOSION, 20), conn=c)
        report["explosion"] = boom
        fam_status["candidate_explosion"].update(
            ran=boom.get("status") == "measured", produced={"n_children": boom.get("n_children")},
            why=str(boom.get("why") or ""))

        # ---- families 19, 20: the sources --------------------------------------------------------
        found = _discovered_grounds(captured_pages)
        sc = scout(c, discovered=found, fetch=fetch and not dry_run, dry_run=dry_run)
        report["source_scout"] = sc
        # THE RECURSIVE EXPANSION. Every recovered ground expands source -> people -> papers ->
        # datasets -> apps -> forums -> code -> new sources until its marginal value falls below
        # what else this hour could buy, and the stop is RECORDED rather than implied.
        floor = _opportunity_floor(sc["scored"])
        seeds = [{"name": g["name"], "url": g["url"], "kind": "archive",
                  "v_s": 1.0, "region": g["region"]}
                 for g in snap.archive_layer()["cells"] if g["state"] == "GROUND"]
        seeds.extend({"name": str(cd.get("name")), "url": str(cd.get("url")),
                      "kind": str(cd.get("kind") or "forum"), "v_s": float(cd["v_s"])}
                     for cd in sc["scored"][:10] if cd.get("fetchable"))
        exp = expand_recursively(seeds, neighbours=expansion_neighbours or _link_neighbours(
            captured_pages), opportunity_floor=floor, conn=c)
        report["expansion"] = exp
        fam_status["source_scout"].update(ran=bool(sc["n_candidates"]), produced={
            "n_candidates": sc["n_candidates"], "registered": sc["n_registered_new"],
            "never_fetched": len(sc["never_fetched"]),
            "expansion": {k: exp.get(k) for k in ("n_visited", "n_discovered",
                                                  "stopped_by_reason")}})
        roi_rows = [{"platform": b["platform"], "roi": b["roi"], "measured": b["measured"],
                     "budget_s": b["budget_s"]} for b in budgets]
        fam_status["source_archaeology"].update(
            ran=any(b["measured"] for b in budgets), produced={"scored": roi_rows[:20]},
            why=("" if any(b["measured"] for b in budgets) else
                 "no platform has a measured yield row yet: every budget is the exploration "
                 "prior, which is UNMEASURED ROI, not zero ROI"))

        if not dry_run:
            reg.remember("archaeology", "one archaeology pass", kind="organ_pass",
                         memory_key=f"archaeology:{stamp}",
                         metrics={"population": report["population"]["n"],
                                  "discoveries": recorded,
                                  "archetypes": len(report["archetypes"])},
                         payload={"budgets": budgets[:10], "families":
                                  [f["name"] for f in fam_status.values() if f["ran"]]},
                         conn=c)
            c.commit()
    finally:
        if close_after:
            c.close()
    report["families"] = list(fam_status.values())
    report["families_ran"] = sum(1 for f in fam_status.values() if f["ran"])
    report["families_unmeasured"] = [f["name"] for f in fam_status.values() if not f["ran"]]
    report["seconds"] = round(time.monotonic() - started, 2)
    return report


def _opportunity_floor(scored: Sequence[Mapping[str, Any]]) -> float:
    """What else this hour could buy. The MEDIAN V_s of the fetchable grounds already in front of
    the pass -- so "marginal value below other opportunities" is a comparison against the desk's
    actual alternatives, not against a constant somebody picked."""
    values = sorted(float(s.get("v_s") or 0.0) for s in scored if s.get("fetchable"))
    if not values:
        return 0.0
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else 0.5 * (values[mid - 1] + values[mid])


def _link_neighbours(pages: Sequence[tuple[str, str]]) -> Any:
    """The default neighbour function: what the captured pages themselves link to, judged by the
    crawler's own relevance vocabulary. Offline (no captures) it returns nothing, and the
    expansion then stops with `frontier_exhausted` -- which is the honest verdict, not a failure.
    """
    grounds = _discovered_grounds(pages)
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for g in grounds:
        by_parent.setdefault(str(g.get("found_via") or ""), []).append(g)

    def neighbours(node: Mapping[str, Any]) -> list[dict[str, Any]]:
        key = str(node.get("url") or "")
        return by_parent.get(key, []) if key else []

    return neighbours


def _parent_spec(disc: Mapping[str, Any]) -> dict[str, Any]:
    payload = disc.get("payload_json")
    spec: dict[str, Any] = {}
    if isinstance(payload, str) and payload.startswith("{"):
        try:
            spec = json.loads(payload)
        except ValueError:
            spec = {}
    return {"discovery_id": str(disc.get("discovery_id") or ""),
            "symbol": str(spec.get("symbol") or ""), "family": str(spec.get("family") or ""),
            "chart": str(spec.get("chart") or "H1"), "session": str(spec.get("session") or "all"),
            "mechanism_id": str(spec.get("mechanism_id") or ""),
            "information": str(spec.get("information") or "price_only"),
            "economic_actor": str(spec.get("economic_actor") or ""),
            "horizon": str(spec.get("horizon") or "sub_4h"), "params": {}}


def _discovered_grounds(pages: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    """New grounds found in what was already captured -- the crawler's own relevance vocabulary
    decides, so this module adds no second opinion about what a trading page looks like."""
    try:
        from world_frontier import worth_following
    except Exception:
        return []
    out: dict[str, dict[str, Any]] = {}
    for url, body in pages:
        for href, anchor in dfm.html_links(body, url)[:200]:
            if not worth_following(href, anchor):
                continue
            host = href.split("/")[2] if "//" in href else ""
            if not host or host in out:
                continue
            out[host] = {"name": host, "url": f"https://{host}", "kind": "forum",
                         "verification_class": "unverified", "found_via": url,
                         "region": "global", "language": ""}
    return list(out.values())[:40]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="plan the pass and print it; write nothing anywhere")
    ap.add_argument("--no-fetch", action="store_true",
                    help="use fixtures/archive only; reach no host")
    ap.add_argument("--once", action="store_true", help="one pass and exit (the default)")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, fetch=not a.no_fetch)
    if not a.dry_run:
        mc._atomic_json(Path(a.report), doc)
    slim = {k: v for k, v in doc.items()
            if k not in ("platforms", "families", "explanation_table", "archetypes")}
    print(json.dumps(slim, indent=1, default=str))
    for f in doc["families"]:
        mark = "ran" if f["ran"] else "UNMEASURED"
        print(f"  {mark:<10} {f['name']:<32} {f['why'][:80]}")
    if a.dry_run:
        print("  (dry run: nothing fetched beyond fixtures, nothing written)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
