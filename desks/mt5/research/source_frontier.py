"""M10 -- THE SOURCE-SPACE FRONTIER: where the unseen mechanisms are, and which source earns
a scout.

THE GAP THIS CLOSES. `scout_roster` answers WHO IS COVERING WHAT. It cannot answer the question
that decides where the next hour of crawling goes: WHERE IS THERE ANYTHING LEFT TO FIND. A ground
read three hundred times that yields the same ten mechanisms is saturated; a ground read twice that
yielded two mechanisms nobody has seen elsewhere is a frontier -- and a roster scores them
identically, because both are "covered". The English finance web is the easiest ground to reach and
the most picked-over, so a scout allocator with no unseen-mass term walks back into it every hour.

WHAT A CELL IS. language x country x source_type x asset_class x mechanism_class: the axes along
which the OUTSIDE WORLD is partitioned, not the axes along which the desk's own hypotheses are
(that grid is `registry.GRID_AXES`, a different map of a different territory). A cell is the unit
an assignment can be written against -- "Korean community sources on metals, positioning
mechanisms" is an instruction; "look harder" is not.

THE MAP IS OF OCCUPIED AND COLD CELLS, NEVER THE CROSS PRODUCT. 26 languages x 51 countries x 16
kinds x 9 asset classes x 10 mechanism classes is 1.9 million cells, every one of them empty -- the
denominator trick the laws forbid, dressed as a coverage map. So cells are built from what sources
ACTUALLY PRODUCED (one per claim, by its own axes) plus one COLD cell per source that has never
produced a lead. Both are real readings; the second is the more valuable one.

UNSEEN MASS IS CHAO1: f1^2 / (2 f2), singletons squared over twice the doubletons, with the
bias-corrected f1(f1-1)/2 branch when a cell holds no doubleton at all -- the branch a thinly read
ground is nearly always in. The estimator reads REPEATS: a cell that keeps telling you the same
three mechanisms is exhausted, and a cell whose every mechanism arrived exactly once is still
hiding most of what it holds. `unseen_frontier.chao1` says this of mechanisms per GROUND; this says
it of the source SPACE in the same closed form, so the two can never disagree.

SOURCE ROI IS A POSTERIOR, NOT A COUNT: four Beta posteriors per source under Jeffreys
Beta(1/2, 1/2) -- P(novel mechanism), P(testable), P(survivor), P(independent survivor). Jeffreys
rather than Laplace because the honest statement about a source with two leads and no survivor is
"almost nothing is known" (Beta(1,1) says 0.25, Jeffreys 0.17), and because it is the reference
prior for a binomial, so the number does not depend on who wrote this file. A posterior with n=0 is
PRIOR ONLY and says so in its own row; the crawl gate refuses a prior-only parent by name.

EXPECTED MARGINAL LOG GROWTH IS UNMEASURED UNTIL A GENERATOR YIELD CARRIES IT: survivors x the mean
delta E[log W] of survivors is the only honest price of a source, `generator_yield.delta_elogw` the
only place the desk records it, and it is absent everywhere today. Published as UNMEASURED by name
rather than a zero that reads as measured worthlessness (L1.28a).

    python desks/mt5/research/source_frontier.py [--dry-run] [--top 40]
    python desks/mt5/research/source_frontier.py --assign 6 --mode exploration
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402

#: The declared forest (500 grounds, 26 languages) and the desk's measured source registry. BOTH
#: seed the graph: the first is what the desk declared it would read, the second what it observed
#: itself reading, and a source in one and not the other is exactly the interesting case.
GROUNDS = DESK / "data" / "deep_forest_sources.json"
REGISTRY_JSON: tuple[Path, ...] = (DESK / "data" / "source_registry.json",
                                   ROOT / "data" / "source_registry.json")
OUT = DESK / "reports" / "SOURCE_FRONTIER.json"

TOP_CELLS = 40
#: A cell scouted inside this window is not an exploration target: exploration means ground the
#: desk has NOT just walked.
RECENT_SCOUT_S = 6 * 3600.0
#: Jeffreys Beta(1/2, 1/2), the reference prior for a binomial rate.
JEFFREYS = 0.5
#: The swarm crawls a candidate source only when its PARENT's P(testable) posterior clears this.
CRAWL_P_TESTABLE = 0.10
#: The constitutional cold-search floor (`research_os_archive.COLD_SEARCH_FLOOR`), repeated so this
#: organ honours it even when the archive is unreadable. Read, never lowered.
COLD_FLOOR = 0.10
#: Leads per bucket of the discovery curve: new mechanisms per this many leads, in arrival order.
LEAD_BUCKET = 10
#: The five axes of source space, in the order the cell key joins them.
AXES: tuple[str, ...] = ("language", "country", "source_type", "asset_class", "mechanism_class")
#: What an axis value is when nothing measured it. Never blank and never "unknown": the laws
#: distinguish "we looked and found nothing" from "nobody looked", and this is the second.
UNMEASURED = "UNMEASURED"
_WS = re.compile(r"\s+")


# ------------------------------------------------------------------------------- small readers

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    """Write whole or not at all; a half-written frontier reads as a saturated one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            os.replace(tmp, path)
        except PermissionError:
            # WinError 5 on a read-only destination: legal on POSIX, fatal here. The desk has lost
            # a fix to exactly this before (CLAUDE.md, the world_frontier port).
            path.write_text(text, encoding="utf-8")
            Path(tmp).unlink(missing_ok=True)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _age_s(at: Any, ref: datetime) -> float | None:
    """Seconds since an ISO stamp; None when it cannot be read, which is never a zero age."""
    try:
        d = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return (ref - (d if d.tzinfo else d.replace(tzinfo=UTC))).total_seconds()


def _slug(text: Any) -> str:
    return _WS.sub("_", str(text or "").strip())[:120]


def _jload(raw: Any, default: Any) -> Any:
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------------- the seeding

def _registry_json() -> dict[str, dict[str, Any]]:
    for p in REGISTRY_JSON:
        doc = _read_json(p, None)
        src = doc.get("sources") if isinstance(doc, dict) else None
        if isinstance(src, dict) and src:
            return {str(k): v for k, v in src.items() if isinstance(v, dict)}
    return {}


def _grounds() -> list[dict[str, Any]]:
    doc = _read_json(GROUNDS, {}) or {}
    return [g for g in (doc.get("grounds") or []) if isinstance(g, dict)]


def register_source(source_id: str, *, url: str = "", kind: str = "", language: str = "",
                    country: str = "", asset_classes: list[str] | None = None,
                    discovered_from: str = "", discovered_via: str = "seed",
                    status: str = "active", licence_note: str = "", meta: Any = None,
                    last_crawled: str | None = None, conn: Any = None) -> bool:
    """Put ONE source in the graph; True when the row is new. A re-seed never overwrites an
    existing row -- its `first_seen`, its discovery edge and all the swarm learned survive. Only
    `last_crawled` moves, and only when the caller passes it."""
    c = conn or reg.connect()
    try:
        row = c.execute("SELECT source_id FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if row is None:
            c.execute("INSERT INTO sources(source_id, url, kind, language, country, "
                      "asset_classes_json, discovered_from, discovered_via, first_seen, "
                      "last_crawled, status, licence_note, meta_json) VALUES(?,?,?,?,?,?,?,?,?,?,"
                      "?,?,?)",
                      (source_id, url, kind, language, country,
                       json.dumps(sorted(asset_classes or []), ensure_ascii=False),
                       discovered_from, discovered_via, now(), last_crawled, status, licence_note,
                       json.dumps(meta or {}, ensure_ascii=False, default=str)))
            c.commit()
            return True
        if last_crawled is not None:
            c.execute("UPDATE sources SET last_crawled=? WHERE source_id=?",
                      (last_crawled, source_id))
            c.commit()
        return False
    finally:
        if conn is None:
            c.close()


def seed_sources(conn: Any = None) -> dict[str, int]:
    """The graph's founder population: every declared ground and every measured registry row.
    `discovered_via="seed"` marks them, so an expansion edge the swarm adds later is
    distinguishable from ground the desk declared for itself -- the only way to answer whether
    the forest is still growing."""
    c = conn or reg.connect()
    try:
        out = {"grounds": 0, "registry_rows": 0, "inserted": 0, "yields_seeded": 0}
        for row in _registry_json().values():
            out["registry_rows"] += 1
            sid = str(row.get("source_id") or "").strip()
            if not sid:
                continue
            out["inserted"] += int(register_source(
                sid, url=str(row.get("url") or ""), kind=str(row.get("kind") or ""),
                language=str(row.get("language") or ""), country=str(row.get("region") or ""),
                asset_classes=[str(a) for a in (row.get("asset_classes") or [])],
                discovered_from="data/source_registry.json",
                licence_note=str(row.get("licence_note") or ""),
                meta={"name": row.get("name"), "ground": row.get("ground"),
                      "weight": row.get("weight")}, conn=c))
            out["yields_seeded"] += int(_seed_yield_from_registry(sid, row, conn=c))
        for g in _grounds():
            out["grounds"] += 1
            name = str(g.get("name") or "").strip()
            if not name:
                continue
            out["inserted"] += int(register_source(
                f"ground:{g.get('region')}:{_slug(name)}",
                url=str(g.get("url") or g.get("site") or ""), kind=str(g.get("kind") or ""),
                language=str(g.get("language") or ""), country=str(g.get("region") or ""),
                discovered_from="desks/mt5/data/deep_forest_sources.json",
                licence_note="WEB-PUBLIC; concept reimplemented, provenance cited, nothing copied",
                meta={"name": name, "weight": g.get("weight"), "route": g.get("route")}, conn=c))
        return out
    finally:
        if conn is None:
            c.close()


def _seed_yield_from_registry(sid: str, row: dict[str, Any], conn: Any) -> bool:
    """Carry the source registry's ALREADY MEASURED counters into `source_yield`, once.

    Without this every seeded source is COLD on day one -- and a ground with 21 measured leads
    published as "no lead ever" is not a degenerate start, it is a false statement that would send
    the cold lane at ground that is already yielding. Seeded only when the source has no yield row,
    so the swarm's own measurements are never overwritten by a re-seed.
    """
    def _n(key: str) -> float:
        v = row.get(key)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0

    leads = _n("n_leads")
    if leads <= 0:
        return False
    if conn.execute("SELECT 1 FROM source_yield WHERE source_id=?", (sid,)).fetchone() is not None:
        return False
    bump_source_yield(sid, conn=conn, leads=leads, candidates=_n("n_testable"),
                      survivors=_n("n_certified"),
                      independent_survivors=_n("n_independent_certified"))
    return True


def sources(conn: Any = None) -> dict[str, dict[str, Any]]:
    c = conn or reg.connect()
    try:
        return {str(r["source_id"]): dict(r) for r in c.execute("SELECT * FROM sources")}
    finally:
        if conn is None:
            c.close()


def bump_source_yield(source_id: str, conn: Any = None, **inc: float) -> None:
    """Additive counters on `source_yield`. The registry has a writer for GENERATOR yield and
    none for SOURCE yield; this is it, additive for the same reason that one is -- a pass reports
    what it produced, never what it thinks the total should now be."""
    fields = ("leads", "claims", "mechanisms", "candidates", "donated", "judged", "survivors",
              "independent_survivors", "compute_s")
    c = conn or reg.connect()
    try:
        row = c.execute("SELECT * FROM source_yield WHERE source_id=?", (source_id,)).fetchone()
        cur = dict(row) if row is not None else {}
        vals = {k: float(cur.get(k) or 0.0) + float(inc.get(k, 0.0)) for k in fields}
        c.execute("INSERT OR REPLACE INTO source_yield(source_id, leads, claims, mechanisms, "
                  "candidates, donated, judged, survivors, independent_survivors, compute_s, "
                  "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (source_id, int(vals["leads"]), int(vals["claims"]), int(vals["mechanisms"]),
                   int(vals["candidates"]), int(vals["donated"]), int(vals["judged"]),
                   int(vals["survivors"]), int(vals["independent_survivors"]), vals["compute_s"],
                   now()))
        c.commit()
    finally:
        if conn is None:
            c.close()


# ------------------------------------------------------------------------------- the estimators

def chao1_unseen(counts: Any) -> float:
    """UNSEEN MECHANISM MASS from a multiset of per-mechanism frequencies: f1^2 / (2 f2), and the
    bias-corrected f1(f1-1)/2 when f2 = 0."""
    freqs = [int(c) for c in list(counts) if int(c) > 0]
    f1 = sum(1 for c in freqs if c == 1)
    f2 = sum(1 for c in freqs if c == 2)
    if f2 > 0:
        return float(f1 * f1) / (2.0 * f2)
    return float(f1 * (f1 - 1)) / 2.0


def beta_posterior(k: float, n: float) -> dict[str, Any]:
    """Jeffreys posterior mean for k successes in n trials, and its honesty flag. `prior_only` is
    the field that matters: n=0 returns 0.5, which is the prior's opinion and not the source's
    record, and nothing here spends on a prior-only row."""
    n_i = max(0.0, float(n))
    k_i = min(max(0.0, float(k)), n_i)
    return {"p": round((k_i + JEFFREYS) / (n_i + 2.0 * JEFFREYS), 6), "k": k_i, "n": n_i,
            "prior_only": n_i <= 0.0}


def _mean_survivor_elogw(conn: Any) -> tuple[float | None, str]:
    """Mean delta E[log W] over generators that actually produced survivors, or UNMEASURED."""
    vals: list[float] = []
    for r in conn.execute("SELECT survivors, delta_elogw FROM generator_yield"):
        try:
            surv, d = float(r["survivors"] or 0.0), float(r["delta_elogw"] or 0.0)
        except (TypeError, ValueError):
            continue
        if surv > 0 and d != 0.0:
            vals.append(d)
    if not vals:
        return None, (f"{UNMEASURED} -- no generator_yield row carries a non-zero delta_elogw with "
                      "survivors, so a source's marginal log growth has no price")
    return float(np.mean(vals)), f"mean delta_elogw over {len(vals)} generator(s) with survivors"


def source_roi(source_id: str, conn: Any = None) -> dict[str, Any]:
    """FOUR POSTERIORS AND A PRICE for one source, from its `source_yield` counters. Novel and
    testable are per LEAD -- the denominator is what the source gave the desk to read. Survival is
    per JUDGED CELL, because a lead the gauntlet never reached says nothing about whether this
    source's ideas survive, and using leads there would charge it for the desk's own queue."""
    c = conn or reg.connect()
    try:
        row = c.execute("SELECT * FROM source_yield WHERE source_id=?", (source_id,)).fetchone()
        y = dict(row) if row is not None else {}

        def _n(key: str) -> float:
            try:
                return float(y.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        leads, judged = _n("leads"), _n("judged")
        # THE SURVIVAL DENOMINATOR FALLS BACK TO LEADS, BY NAME. Judged cells are the right
        # denominator and nothing records them per source yet; `data/source_registry.json`'s own
        # reputation block already scores p_survivor over leads, so the fallback keeps the two
        # readings comparable instead of silently clamping k>n and discarding a real survivor.
        denom = judged if judged > 0 else leads
        p_novel = beta_posterior(_n("mechanisms"), leads)
        p_testable = beta_posterior(_n("candidates"), leads)
        p_surv = beta_posterior(_n("survivors"), denom)
        p_indep = beta_posterior(_n("independent_survivors"), denom)
        elogw, basis = _mean_survivor_elogw(c)
        marginal: float | str = UNMEASURED if elogw is None else round(_n("survivors") * elogw, 9)
        return {
            "source_id": source_id, "leads": leads, "judged": judged, "p_novel": p_novel,
            "survival_denominator": ("judged cells" if judged > 0 else
                                     f"leads ({UNMEASURED} judged cells for this source)"),
            "p_testable": p_testable, "p_survivor": p_surv, "p_independent_survivor": p_indep,
            "roi_score": round(p_novel["p"] * p_testable["p"], 9),
            "measured": not (p_novel["prior_only"] and p_surv["prior_only"]),
            "expected_marginal_log_growth": marginal, "elogw_basis": basis,
            "compute_s": _n("compute_s"),
            "rule": ("novel and testable per LEAD, survival per JUDGED cell, Jeffreys Beta(1/2, "
                     "1/2) throughout; a prior-only row is nobody's evidence"),
        }
    finally:
        if conn is None:
            c.close()


def roi_table(conn: Any = None, limit: int = 200) -> list[dict[str, Any]]:
    """Every source with a yield row, best posterior product first. Sources with no row are absent
    by design: they are the COLD population, and the cold lane is how they get looked at."""
    c = conn or reg.connect()
    try:
        ids = [str(r["source_id"]) for r in c.execute("SELECT source_id FROM source_yield")]
        rows = [source_roi(sid, conn=c) for sid in ids]
        rows.sort(key=lambda r: (-float(r["roi_score"]), r["source_id"]))
        return rows[:limit]
    finally:
        if conn is None:
            c.close()


def may_crawl(source_id: str, conn: Any = None, threshold: float = CRAWL_P_TESTABLE
              ) -> tuple[bool, str]:
    """THE CRAWL GATE. A source discovered by expansion is crawled only once its PARENT has shown
    P(testable) above the threshold on MEASURED leads. A prior-only parent never opens it: 0.5 from
    an empty posterior is the prior talking, and crawling on that is how a self-expanding swarm
    walks into an unbounded fetch of everything anything ever linked to."""
    p = source_roi(source_id, conn=conn)["p_testable"]
    if p["prior_only"]:
        return False, (f"{UNMEASURED} parent: {source_id} has no measured lead, so its "
                       f"P(testable)={p['p']} is the Jeffreys prior, not evidence")
    if float(p["p"]) <= threshold:
        return False, f"parent P(testable)={p['p']:.3f} <= {threshold} on {p['n']:.0f} lead(s)"
    return True, f"parent P(testable)={p['p']:.3f} > {threshold} on {p['n']:.0f} lead(s)"


# ------------------------------------------------------------------------------------ the cells

def cell_key(language: str, country: str, source_type: str, asset_class: str,
             mechanism_class: str) -> str:
    return "|".join(str(v or UNMEASURED).strip().lower() or UNMEASURED.lower()
                    for v in (language, country, source_type, asset_class, mechanism_class))


def _mechanism_class(text: str) -> str:
    try:
        from libs.research.mechanism_claims import mechanism_class
        return str(mechanism_class(text or "") or "other")
    except Exception:                                    # a classifier is never fatal
        return UNMEASURED


def _asset_class(instruments: Any, declared: list[str]) -> str:
    """The claim's own instrument decides, through MetaTrader's registry -- never a symbol list. A
    symbol the registry does not classify is UNCLASSIFIED and hunted by nothing until it is
    (the two-lane door: absence is not a permission)."""
    syms = [str(s) for s in (instruments or []) if str(s).strip()]
    try:
        from universe_policy import asset_class_of
    except Exception:
        asset_class_of = None                            # type: ignore[assignment]
    for s in syms if asset_class_of is not None else ():
        try:
            klass = str(asset_class_of(s) or "").lower()
        except Exception:
            continue
        if klass and klass not in ("unknown", "unclassified"):
            return klass
    if declared:
        return str(declared[0]).lower()
    return "unclassified" if syms else UNMEASURED


def _claim_rows(conn: Any) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(
            "SELECT claim_id, created_at, source_id, text, language, mechanism_id, "
            "instruments_json FROM claims ORDER BY created_at, claim_id")]
    except Exception:                                    # a bad row never stops the map
        return []


def build_cells(conn: Any = None) -> list[dict[str, Any]]:
    """THE MAP: one cell per claim's own axes, plus one COLD cell per source that never produced a
    lead. Nothing enumerates the cross product -- an empty cell nobody could have filled is not a
    gap, and counting it would turn 1.9 million imaginary cells into a coverage denominator."""
    c = conn or reg.connect()
    try:
        srcs = sources(conn=c)
        leads_by_source = {str(r["source_id"]): int(r["leads"] or 0)
                           for r in c.execute("SELECT source_id, leads FROM source_yield")}
        cells: dict[str, dict[str, Any]] = {}

        def _cell(key: str) -> dict[str, Any]:
            row = cells.get(key)
            if row is None:
                row = {"cell": key, "n_leads": 0, "src": set(), "mech": Counter(), "order": [],
                       "last_scouted": None, **dict(zip(AXES, key.split("|"), strict=True))}
                cells[key] = row
            return row

        claimed: set[str] = set()
        for row in _claim_rows(c):
            sid = str(row.get("source_id") or "")
            src = srcs.get(sid, {})
            claimed.add(sid)
            mech_class = _mechanism_class(str(row.get("text") or ""))
            key = cell_key(str(src.get("language") or row.get("language") or UNMEASURED),
                           str(src.get("country") or UNMEASURED),
                           str(src.get("kind") or UNMEASURED),
                           _asset_class(_jload(row.get("instruments_json"), []),
                                        [str(a) for a in _jload(src.get("asset_classes_json"),
                                                                [])]),
                           mech_class)
            cell = _cell(key)
            cell["n_leads"] += 1
            cell["src"].add(sid)
            mech = str(row.get("mechanism_id") or "") or f"class:{mech_class}"
            cell["mech"][mech] += 1
            cell["order"].append(mech)
            at = str(row.get("created_at") or "")
            if at and at > str(cell["last_scouted"] or ""):
                cell["last_scouted"] = at
        for sid, src in srcs.items():
            n = int(leads_by_source.get(sid, 0))
            if sid in claimed and n <= 0:
                continue
            declared = [str(a) for a in _jload(src.get("asset_classes_json"), [])]
            cell = _cell(cell_key(str(src.get("language") or UNMEASURED),
                                  str(src.get("country") or UNMEASURED),
                                  str(src.get("kind") or UNMEASURED),
                                  declared[0] if declared else UNMEASURED, UNMEASURED))
            cell["src"].add(sid)
            # A source with yield counters but no claim ROW still produced leads; calling it cold
            # would send the cold lane at ground that is already yielding.
            cell["n_leads"] += n if sid not in claimed else 0
            crawled = str(src.get("last_crawled") or "")
            if crawled and crawled > str(cell["last_scouted"] or ""):
                cell["last_scouted"] = crawled
        return [_finish_cell(cell) for cell in cells.values()]
    finally:
        if conn is None:
            c.close()


def _finish_cell(cell: dict[str, Any]) -> dict[str, Any]:
    counts = list(cell["mech"].values())
    out = {k: cell[k] for k in ("cell", *AXES)}
    out.update({
        "n_sources": len(cell["src"]), "n_leads": int(cell["n_leads"]),
        "n_distinct": len(counts), "n_singletons": sum(1 for v in counts if v == 1),
        "n_doubletons": sum(1 for v in counts if v == 2),
        "chao1_unseen": round(chao1_unseen(counts), 6) if counts else None,
        "discovery_curve": discovery_curve(cell["order"]), "last_scouted": cell["last_scouted"],
        "cold": int(cell["n_leads"]) <= 0, "sources": sorted(cell["src"])[:12],
    })
    return out


def discovery_curve(order: list[str]) -> list[dict[str, int]] | None:
    """New mechanisms per LEAD_BUCKET leads, in the order the cell yielded them. A curve gone
    flat is a saturated cell however many leads it still produces."""
    if not order:
        return None
    seen: set[str] = set()
    out: list[dict[str, int]] = []
    for i in range(0, len(order), LEAD_BUCKET):
        chunk = order[i:i + LEAD_BUCKET]
        # DISTINCT new mechanisms, not new SIGHTINGS: a bucket that told the same story ten times
        # discovered one mechanism, and counting ten would make a saturated ground look fertile.
        fresh = len(set(chunk) - seen)
        seen.update(chunk)
        out.append({"leads": i + len(chunk), "new_mechanisms": fresh, "distinct_so_far": len(seen)})
    return out


def write_frontier_map(cells: list[dict[str, Any]], conn: Any = None) -> int:
    """UPSERT into `registry.frontier_map`: the table is the durable record, the report a
    reading of it, and a second pass over the same evidence must not double the row count."""
    c = conn or reg.connect()
    try:
        for cell in cells:
            c.execute(
                "INSERT INTO frontier_map(cell, language, country, source_type, asset_class, "
                "mechanism_class, n_sources, n_leads, n_distinct, n_singletons, n_doubletons, "
                "chao1_unseen, last_scouted, cold, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,"
                "?,?) ON CONFLICT(cell) DO UPDATE SET n_sources=excluded.n_sources, "
                "n_leads=excluded.n_leads, n_distinct=excluded.n_distinct, "
                "n_singletons=excluded.n_singletons, n_doubletons=excluded.n_doubletons, "
                "chao1_unseen=excluded.chao1_unseen, last_scouted=excluded.last_scouted, "
                "cold=excluded.cold, updated_at=excluded.updated_at",
                (cell["cell"], cell["language"], cell["country"], cell["source_type"],
                 cell["asset_class"], cell["mechanism_class"], cell["n_sources"], cell["n_leads"],
                 cell["n_distinct"], cell["n_singletons"], cell["n_doubletons"],
                 cell["chao1_unseen"], cell["last_scouted"], int(bool(cell["cold"])), now()))
        c.commit()
        return len(cells)
    finally:
        if conn is None:
            c.close()


def mark_scouted(cell: str, conn: Any = None, at: str | None = None) -> None:
    """The swarm stamps a cell it actually worked, so exploration stops returning it next pass."""
    c = conn or reg.connect()
    try:
        c.execute("UPDATE frontier_map SET last_scouted=?, updated_at=? WHERE cell=?",
                  (at or now(), now(), cell))
        c.commit()
    finally:
        if conn is None:
            c.close()


# ------------------------------------------------------------------------------- the assignment

def _neighbourhood(cells: list[dict[str, Any]], seed: dict[str, Any]) -> list[dict[str, Any]]:
    """OCCUPIED cells one axis away. Not the cross product's neighbours -- those are imaginary;
    these are places the desk has already proved a source exists."""
    return [x for x in cells if x["cell"] != seed["cell"]
            and sum(1 for a in AXES if str(x[a]) != str(seed[a])) == 1]


def _row(cell: dict[str, Any], mode: str, why: str) -> dict[str, Any]:
    return {"cell": cell["cell"], "mode": mode, "axes": {a: cell[a] for a in AXES}, "why": why}


def assign(k: int, mode: str = "exploration", cells: list[dict[str, Any]] | None = None,
           conn: Any = None, recent_s: float = RECENT_SCOUT_S,
           now_dt: datetime | None = None) -> list[dict[str, Any]]:
    """THE K CELLS A SCOUT IS SENT TO, and why.

    exploration  highest unseen mass among cells not scouted inside `recent_s`.
    exploitation the neighbourhoods of the sources with the best P(testable) x P(novel).
    cold         cells that have never produced a lead. A PERMANENT SHARE, never earned away:
                 cold ground pays last and rarely, so any short-horizon fitness cuts it first, and
                 a swarm permitted to cut it optimises itself into what it already knows.
    """
    c = conn or reg.connect()
    try:
        rows = cells if cells is not None else build_cells(conn=c)
        ref = now_dt or datetime.now(tz=UTC)
        mode = str(mode or "exploration").lower()
        if mode == "cold":
            pool = sorted((x for x in rows if x["cold"]),
                          key=lambda x: (-int(x["n_sources"]), x["cell"]))
            return [_row(x, "cold", f"no lead ever from {x['n_sources']} source(s) on this cell; "
                                    f"the cold lane is floored at {COLD_FLOOR} and never bid away")
                    for x in pool[:k]]
        if mode == "exploitation":
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for roi in roi_table(conn=c):
                if not roi["measured"] or roi["roi_score"] <= 0:
                    continue
                seeds = [x for x in rows if roi["source_id"] in (x.get("sources") or [])]
                why = (f"{roi['source_id']} P(testable)={roi['p_testable']['p']:.3f} x P(novel)="
                       f"{roi['p_novel']['p']:.3f} on {roi['leads']:.0f} lead(s)")
                for cell in seeds + [n for s in seeds for n in _neighbourhood(rows, s)]:
                    if cell["cell"] in seen:
                        continue
                    seen.add(cell["cell"])
                    out.append(_row(cell, "exploitation", why))
                    if len(out) >= k:
                        return out
            return out
        pool = [x for x in rows if x["chao1_unseen"] is not None]
        fresh = [x for x in pool if x["last_scouted"] is None
                 or (_age_s(x["last_scouted"], ref) or 1e18) > recent_s]
        # EVERY CELL JUST SCOUTED IS STILL AN ANSWER. Returning nothing would hand the beat's
        # exploration seconds back to nobody; the fallback returns the best mass and SAYS it is a
        # fallback, so a reader can tell "the best unexplored cell" from "nothing was unexplored".
        fallback = "" if fresh else ("; FALLBACK -- every cell with unseen mass was scouted inside "
                                     f"the last {recent_s / 3600.0:.1f}h")
        pool = sorted(fresh or pool, key=lambda x: (-float(x["chao1_unseen"] or 0.0), x["cell"]))
        return [_row(x, "exploration",
                     f"unseen mass {x['chao1_unseen']:.2f} from {x['n_singletons']} singleton(s) "
                     f"/ {x['n_doubletons']} doubleton(s) over {x['n_leads']} lead(s); last "
                     f"scouted {x['last_scouted'] or UNMEASURED}{fallback}")
                for x in pool[:k]]
    finally:
        if conn is None:
            c.close()


def search_mix() -> dict[str, float]:
    """The seated ResearchOS miner mix, with the cold floor enforced HERE as well as there: an
    archive this organ cannot read must not be able to zero the one lane the constitution
    protects."""
    mix = {"exploration": 0.30, "exploitation": 0.55, "cold": 0.15}
    try:
        from research_os_archive import active_policy
        got = (active_policy().get("miner") or {}).get("search_mix")
        if isinstance(got, dict) and set(got) >= set(mix):
            mix = {k: max(0.0, float(got[k])) for k in mix}
    except Exception:                                    # a policy reader is never fatal
        pass
    if mix["cold"] < COLD_FLOOR:
        donor = "exploitation" if mix["exploitation"] >= mix["exploration"] else "exploration"
        mix[donor] = max(0.0, mix[donor] - (COLD_FLOOR - mix["cold"]))
        mix["cold"] = COLD_FLOOR
    total = sum(mix.values()) or 1.0
    return {k: round(v / total, 6) for k, v in mix.items()}


def suggest(k: int, cells: list[dict[str, Any]], conn: Any = None) -> list[dict[str, Any]]:
    """k assignments split by the seated search mix, cold never below its floor."""
    mix = search_mix()
    counts = {m: math.floor(k * mix[m]) for m in mix}
    counts["cold"] = max(counts["cold"], math.ceil(k * COLD_FLOOR))
    out: list[dict[str, Any]] = []
    for mode in ("exploration", "exploitation", "cold"):
        out += assign(counts[mode], mode, cells=cells, conn=conn)
    return out


# ----------------------------------------------------------------------------------- the report

def build(conn: Any = None, top: int = TOP_CELLS, seed: bool = True) -> dict[str, Any]:
    c = conn or reg.connect()
    try:
        seeded = seed_sources(conn=c) if seed else {"grounds": 0, "registry_rows": 0,
                                                    "inserted": 0}
        cells = build_cells(conn=c)
        write_frontier_map(cells, conn=c)
        by_mass = sorted(cells, key=lambda x: -float(x["chao1_unseen"] or 0.0))
        cold = [x for x in cells if x["cold"]]
        unseen_lang: dict[str, float] = {}
        unseen_asset: dict[str, float] = {}
        for x in cells:
            mass = float(x["chao1_unseen"] or 0.0)
            lang, asset = str(x["language"]), str(x["asset_class"])
            unseen_lang[lang] = round(unseen_lang.get(lang, 0.0) + mass, 6)
            unseen_asset[asset] = round(unseen_asset.get(asset, 0.0) + mass, 6)
        roi = roi_table(conn=c, limit=25)
        elogw, elogw_basis = _mean_survivor_elogw(c)
        n_yield = int(c.execute("SELECT COUNT(*) FROM source_yield").fetchone()[0])
        n_claims = int(c.execute("SELECT COUNT(*) FROM claims").fetchone()[0])
        return {
            "at": now(), "n_cells": len(cells),
            "cells": [{k: v for k, v in x.items() if k != "sources"} for x in by_mass[:top]],
            "cold_cells": [x["cell"] for x in cold[:top]], "n_cold_cells": len(cold),
            "unseen_by_language": dict(sorted(unseen_lang.items(), key=lambda kv: -kv[1])[:20]),
            "unseen_by_asset": dict(sorted(unseen_asset.items(), key=lambda kv: -kv[1])[:20]),
            "assignments_suggested": suggest(12, cells, conn=c), "search_mix": search_mix(),
            "roi_top": [{"source_id": r["source_id"], "roi_score": r["roi_score"],
                         "p_novel": r["p_novel"]["p"], "p_testable": r["p_testable"]["p"],
                         "p_survivor": r["p_survivor"]["p"], "leads": r["leads"],
                         "expected_marginal_log_growth": r["expected_marginal_log_growth"]}
                        for r in roi[:15]],
            "seeded": seeded,
            "unmeasured": {
                "claims_rows": n_claims,
                "claims_basis": (f"{n_claims} claim row(s) in the registry" if n_claims else
                                 f"{UNMEASURED} -- the registry's `claims` table is empty, so "
                                 "mechanism diversity per cell has no evidence and every "
                                 "chao1_unseen is null; lead counts fall back to source_yield"),
                "n_cells_never_scouted": sum(1 for x in cells if not x["last_scouted"]),
                "n_cells_without_unseen_mass": sum(1 for x in cells if x["chao1_unseen"] is None),
                "n_sources_without_yield": max(0, len(sources(conn=c)) - n_yield),
                "marginal_log_growth": (elogw_basis if elogw is None
                                        else f"mean survivor delta_elogw = {elogw:.6f}"),
            },
            "rule": "scouts go where the unseen mass is, never to saturated English finance",
        }
    finally:
        if conn is None:
            c.close()


def _summary(doc: dict[str, Any]) -> list[str]:
    u = doc["unmeasured"]
    tops = "  ".join("{}={}".format(c["cell"], c["chao1_unseen"] if c["chao1_unseen"] is not None
                                    else UNMEASURED) for c in doc["cells"][:3])
    rois = "  ".join(f"{r['source_id']}={r['roi_score']:.4f}" for r in doc["roi_top"][:3])
    return [
        f"source frontier: {doc['n_cells']} cell(s), {doc['n_cold_cells']} cold, "
        f"{u['n_cells_never_scouted']} never scouted",
        "  top unseen: " + (tops or "NONE MEASURED"),
        f"  mix {doc['search_mix']}  suggested {len(doc['assignments_suggested'])} assignment(s)",
        "  roi_top: " + (rois or "NONE MEASURED"),
        f"  {u['claims_basis'][:96]}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M10: the source-space frontier and source ROI")
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--top", type=int, default=TOP_CELLS)
    ap.add_argument("--assign", type=int, default=0, help="print k assignments and exit")
    ap.add_argument("--mode", default="exploration",
                    choices=("exploration", "exploitation", "cold"))
    ap.add_argument("--no-seed", action="store_true", help="do not seed the source graph")
    a = ap.parse_args(argv)
    if a.assign:
        for row in assign(a.assign, a.mode):
            print(f"{row['mode']:12s} {row['cell']}  {row['why']}")
        return 0
    doc = build(top=a.top, seed=not a.no_seed)
    if not a.dry_run:
        _atomic(OUT, doc)
    for line in _summary(doc):
        print(line)
    print(f"  {'wrote' if not a.dry_run else 'DRY RUN, wrote nothing:'} {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
