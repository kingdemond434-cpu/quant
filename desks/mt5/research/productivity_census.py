#!/usr/bin/env python3
"""THE RESEARCH PRODUCTIVITY CENSUS -- which organs have EARNED their compute.

An external reviewer's verdict (2026-09-23) was that the architecture is ~95% present and
closed-loop, and that NOT ONE organ has been shown to be PRODUCTIVE. "The code exists and it is
scheduled" is what `check_component_registry.py` and `check_producer_schedules.py` already prove;
"it produces measurable cells" is a different claim and no artifact on this desk made it. That is
the gap this organ closes, and it is the only scoreboard on the desk that can end a producer.

WHAT IT MEASURES, per PRODUCER (crawler, forest, country pack, sandbox system, factory, seat), is
one funnel with eleven stages and no gaps allowed between them:

    sources visited -> documents retained -> raw mechanism claims -> canonical mechanisms
    -> raw cells -> unique cells after dedup -> gauntlet submitted -> cheap-stage survivors
    -> certificates -> forward enrolled -> live contribution

and four MARGINAL ratios, which are what turns a report into a decision:

    cells per source, survivors per source, certificates per compute hour, survivors per region.

THE DEDUP COUNT IS THE POINT, not a footnote. A hundred thousand documents that collapse into
twenty duplicated momentum rules is the exact failure this exists to expose, and the only way to
see it is to count RAW cells and UNIQUE cells separately with the desk's own dedup chain --
`research_candidates.content_hash`, the same hash `enqueue_candidate` dedups on. A producer whose
collapse ratio is 40:1 is not a producer of forty things.

THE REGION ROLL-UP IS THE QUESTION ACTUALLY BEING ASKED. "Is the world crawler a major alpha
contributor or sophisticated noise" cannot be answered producer by producer, because the crawler
is fifty country packs wearing one name. Rolled up by region -- Japan, Korea, China, SEA,
Russia/CIS, India, Europe, North America, LatAm, Oceania, MENA, Africa -- the answer is a table
with survivors in it or a table of zeros, and either one is an answer.

THREE RULES MAKE IT HONEST, and without them it is a vanity dashboard:

  1. A STAGE WITH NO MEASUREMENT READS `UNMEASURED` WITH ITS REASON, NEVER ZERO (L1.28a). The
     registry's `mechanisms` table is EMPTY on this box -- canonical mechanisms therefore read
     UNMEASURED with that sentence attached, not 0, because 0 would say the producers failed to
     canonicalise when in truth nothing wrote the table.
  2. EVERY NUMBER NAMES ITS SOURCE. The JSON carries a `sources` block mapping each stage to the
     artifact path or the exact registry query behind it. A number whose provenance is not
     stated is a number a reader cannot check, and this desk has been burned by those.
  3. NOTHING IS HAND-LISTED. The producer roster is the union of the two rosters that already
     exist -- `reports/PRODUCER_CENSUS.json` and `reports/COMPONENT_REGISTRY.json` -- plus any
     generator the registry itself has seen. A producer that appears only in the registry is
     itself a finding (something produces that no roster knows about), never a silent add.

THE DELIVERABLE A READER WILL ACT ON is `zero_cell_compute`: producers that consumed compute and
produced NO unique cell, ranked by compute spent. That list is the census's whole reason to run.

IT DOES NOT JUDGE LOW PRODUCTIVITY. A genuinely exploratory organ is allowed to be unproductive
if it SAYS SO -- `scripts/check_productivity_census.py` fails on staleness and on silent
zero-yield past a stated window, never on a small number. The census measures; the fence asks for
a named blocker; neither one cuts a budget, because that is the allocator's job and the
principal's standing order is that this desk never reduces its aggressiveness by fiat.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
REPORTS = DESK / "reports"
OUT = REPORTS / "PRODUCTIVITY_CENSUS.json"
DOC = ROOT / "docs" / "research" / "PRODUCTIVITY_CENSUS.md"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"

PRODUCER_CENSUS = REPORTS / "PRODUCER_CENSUS.json"
COMPONENT_REGISTRY = REPORTS / "COMPONENT_REGISTRY.json"
UNIVERSAL_SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
SLEEVE_REGISTRY = DESK / "data" / "sleeve_registry.json"
SLEEVES = DESK / "data" / "sleeves.json"
FOREST_SOURCES = DESK / "data" / "deep_forest_sources.json"
#: The attribution stamp's artifact (desks/mt5/research/attribution_census.py). Read for the
#: modal region of each producer's OWN cells -- the route a producer's NAME could never give.
ATTRIBUTION = REPORTS / "ATTRIBUTION_COVERAGE.json"
#: THE ORTHOGONALITY COLUMN'S ONE SOURCE (scripts/check_producer_yield.py). Breadth is the
#: participation ratio of a singular-value spectrum over the producer x cell matrix, and that
#: machinery already runs on a clock and already publishes a marginal contribution per producer.
#: This census READS it and never re-derives it: a second SVD here would cost the box an hour it
#: does not have and would give a reader two different answers to one question. An absent or
#: stale artifact makes the column UNMEASURED WITH ITS REASON, never zero (L1.28a).
PRODUCER_YIELD = REPORTS / "PRODUCER_YIELD.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.research import attribution as _attr  # noqa: E402

# The window every rate in this census is computed over. Compute hours come from the compute
# ledger, whose own window is days; funnel counts are cumulative registry state, which the JSON
# says plainly so nobody divides a lifetime count by a three-day hour budget without knowing it.
COMPUTE_WINDOW_DAYS = 7.0

# THE REGION TABLES ARE NOT KEPT HERE. They were, in a copy that had already drifted 29 country
# codes behind `libs/research/attribution.py` -- the module that STAMPS the registry at birth --
# so this file could read `Europe` for a ground the stamp called `Russia/CIS`. One rule, one table:
# the names stay bound so an outside importer still resolves, and the values come from the helper.
REGION_OF_CODE: dict[str, str] = _attr.REGION_OF_CODE
NAME_TO_CODE: dict[str, str] = _attr.NAME_TO_CODE
REGIONS: tuple[str, ...] = _attr.REGIONS

#: THE VERDICT THAT IS NOT A GAP. A method, a desk organ, a compiler or a declared seat belongs to
#: no region BY CONSTRUCTION, and `libs/research/attribution.py` names that state rather than
#: leaving it blank. It gets its own roll-up bucket beside the twelve: filing desk machinery under
#: `unattributed` is what made 1,940 of 1,981 producers read as an attribution gap when the real
#: gap was a tenth of that.
NOT_REGIONAL = _attr.NOT_REGIONAL
UNATTRIBUTED = "unattributed"
#: Every bucket the region roll-up publishes, in the order it renders. The denominator is always
#: every bucket the desk NAMES -- a ratio improved by dropping a region is a lie (L1.50).
ROLLUP_BUCKETS: tuple[str, ...] = (*REGIONS, NOT_REGIONAL, UNATTRIBUTED)

UNMEASURED = "UNMEASURED"

#: THE SIX COLUMNS THE PRODUCERS PANEL RENDERS, published at the TOP LEVEL of every producer row.
#: They lived inside `funnel` alone, and `desk_dashboard_state._producers` reads the row's top
#: level -- so `compute_hours` (the one field that was already top-level) was the ONLY column that
#: ever rendered, and all five measurements beside it read UNMEASURED for 1,981 of 1,981 rows.
#: The desk therefore published exactly what each producer COST and nothing about what it MADE.
#: Named here so the contract is one list a test can pin rather than five scattered writes.
PANEL_COLUMNS: tuple[str, ...] = ("cells", "unique_cells", "cells_judged", "certificates",
                                  "orthogonality_added", "compute_hours")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _age_hours(stamp: Any) -> float | None:
    """Hours since an ISO stamp, or None when it cannot be read. Never raises: a census that
    crashed while dating another organ's artifact would report nothing at all."""
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return round((datetime.now(UTC) - when).total_seconds() / 3600.0, 3)


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _region_for(token: str | None) -> str | None:
    """Map a producer name, generator prefix or source country onto one of the twelve.

    DELEGATED, NEVER RE-DERIVED (2026-09-23). The rule lives in `libs/research/attribution.py`,
    which is also what stamps the registry at birth; a second copy here is how two organs come to
    disagree about which region a producer belongs to. Returns None rather than a default,
    because an unattributable producer belongs in the `unattributed` bucket by name -- silently
    filing it under "Global" would inflate exactly the row a reader is least able to check.
    """
    return _attr.region_of(token)


def _stamped_regions() -> dict[str, str]:
    """producer -> the region its OWN registry rows carry, from `ATTRIBUTION_COVERAGE.json`.

    THE ROUTE A NAME COULD NEVER GIVE. This organ resolved a producer's region from its NAME, so
    1,521 of 1,586 producers holding 4,725 unique cells fell into `unattributed` and the board
    read `Europe: 1,973 sources, 0 cells`. `desks/mt5/research/attribution_census.py` stamps every
    cell with the region its lineage reaches and publishes the modal region per producer; this
    reads that. An absent artifact changes nothing -- the name routes stay, and the producers it
    could not place stay in `unattributed`, which is UNMEASURED and not a zero (L1.28a).
    """
    doc = _load_json(ATTRIBUTION)
    block = doc.get("producer_region") if isinstance(doc, dict) else None
    regions = block.get("regions") if isinstance(block, dict) else None
    if not isinstance(regions, dict):
        return {}
    # NOT_REGIONAL IS AN ANSWER AND WAS BEING THROWN AWAY. This filter read `in REGIONS`, so a
    # producer the stamp had positively judged to belong to no region -- a compiler, a method, a
    # declared seat -- was dropped here and fell through to `unattributed`, which says the desk
    # could not tell. Those are opposite facts (L1.28a). UNATTRIBUTABLE is still refused: it is
    # the stamp saying it does not know, and this ladder has further routes to try.
    keep = (*REGIONS, NOT_REGIONAL)
    return {_norm(k): str(v) for k, v in regions.items() if str(v) in keep}


def _norm(name: str) -> str:
    """Canonical producer key: `exe:` prefixes and path shapes collapse onto the stem."""
    raw = str(name or "").strip()
    if raw.startswith("exe:"):
        raw = raw[4:]
    if "/" in raw or raw.endswith(".py"):
        raw = Path(raw).stem
    return raw.strip().lower()


# --------------------------------------------------------------------------------------- roster

def build_roster() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The producer roster, REUSED from the two rosters that already exist.

    `PRODUCER_CENSUS.json` knows every seat, miner and research organ with a declared clock;
    `COMPONENT_REGISTRY.json` knows every executable with a ComponentSpec. Neither is re-derived
    here. Missing rosters do not zero the census -- they make it UNMEASURED and say which file
    was absent, because a census built on half a roster silently exonerates the other half.
    """
    roster: dict[str, dict[str, Any]] = {}
    notes: dict[str, Any] = {}

    pc = _load_json(PRODUCER_CENSUS)
    if isinstance(pc, dict) and isinstance(pc.get("rows"), list):
        for row in pc["rows"]:
            if not isinstance(row, dict):
                continue
            key = _norm(row.get("producer", ""))
            if not key:
                continue
            roster.setdefault(key, {
                "producer": row.get("producer"),
                "kind": row.get("kind") or "producer",
                "clock": row.get("clock"),
                "clock_host": row.get("clock_host"),
                "roster_source": "reports/PRODUCER_CENSUS.json",
            })
        notes["producer_census"] = f"{len(pc['rows'])} rows, generated {pc.get('generated_utc')}"
    else:
        notes["producer_census"] = f"{UNMEASURED}: {PRODUCER_CENSUS} absent or unreadable"

    cr = _load_json(COMPONENT_REGISTRY)
    if isinstance(cr, dict):
        fresh = cr.get("freshness")
        rows = fresh if isinstance(fresh, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _norm(str(row.get("component_id") or ""))
            if not key:
                continue
            entry = roster.setdefault(key, {
                "producer": row.get("component_id"),
                "kind": row.get("kind") or "component",
                "clock": row.get("schedule"),
                "roster_source": "reports/COMPONENT_REGISTRY.json",
            })
            entry.setdefault("clock", row.get("schedule"))
        notes["component_registry"] = f"{cr.get('components')} components, at {cr.get('at')}"
    else:
        notes["component_registry"] = f"{UNMEASURED}: {COMPONENT_REGISTRY} absent or unreadable"

    return roster, notes


# ------------------------------------------------------------------------------------- registry

def _rows(cur: sqlite3.Cursor, sql: str) -> list[tuple[Any, ...]]:
    try:
        return list(cur.execute(sql))
    except sqlite3.Error:
        return []


def _table_count(cur: sqlite3.Cursor, table: str) -> int | None:
    try:
        row = cur.execute(f"select count(*) from {table}").fetchone()  # noqa: S608
        return int(row[0]) if row else None
    except sqlite3.Error:
        return None


def measure_registry(db: Path) -> dict[str, Any]:
    """Every funnel stage the alpha registry can answer, keyed by producer.

    ONE CONNECTION, READ ONLY, NO WRITES. This organ measures the registry; a census that could
    mutate the thing it counts would be worthless as evidence the first time anyone doubted it.
    """
    out: dict[str, Any] = {"available": False, "why": "", "by_producer": {},
                           "totals": {}, "unmeasured": {}}
    if not db.exists():
        out["why"] = f"{UNMEASURED}: registry {db} does not exist on this host"
        return out
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=20.0)
    except sqlite3.Error as exc:
        out["why"] = f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
        return out
    out["available"] = True
    per: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    try:
        cur = con.cursor()

        # STAGE 1-2: sources visited, and the documents kept off them. `sources.discovered_via`
        # names the producer that found the source; `claims.doc_id` is the retained document.
        src_producer: dict[str, str] = {}
        src_region: dict[str, str] = {}
        for sid, via, country, last_crawled in _rows(
                cur, "select source_id, discovered_via, country, last_crawled from sources"):
            key = _norm(str(via or "")) or "_unattributed_source"
            src_producer[str(sid)] = key
            reg = _region_for(country) or _region_for(via)
            if reg:
                src_region[str(sid)] = reg
            per[key]["sources_visited"] += 1
            if last_crawled:
                per[key]["sources_crawled"] += 1

        for sid, ndocs, nclaims in _rows(
                cur, "select source_id, count(distinct doc_id), count(*) from claims "
                     "group by source_id"):
            key = src_producer.get(str(sid), "_unattributed_source")
            per[key]["documents_retained"] += int(ndocs or 0)
            per[key]["raw_mechanism_claims"] += int(nclaims or 0)

        # STAGE 3: canonical mechanisms. The registry has a `mechanisms` table for exactly this;
        # when it is EMPTY the stage is UNMEASURED with that sentence, never zero (L1.28a).
        n_mech = _table_count(cur, "mechanisms")
        if n_mech:
            for sid, n in _rows(cur, "select source_id, count(*) from mechanisms group by 1"):
                per[src_producer.get(str(sid), "_unattributed_source")][
                    "canonical_mechanisms"] += int(n or 0)
        else:
            out["unmeasured"]["canonical_mechanisms"] = (
                "registry table `mechanisms` holds 0 rows on this host: no organ has written a "
                "canonicalised mechanism, so this stage is UNMEASURED and not zero -- the "
                "fallback below counts DISTINCT mechanism_id stamped on discoveries instead")
            for gen, n in _rows(
                    cur, "select generator, count(distinct mechanism_id) from discoveries "
                         "where mechanism_id is not null and mechanism_id != '' group by 1"):
                per[_norm(str(gen or "_unattributed_generator"))][
                    "canonical_mechanisms_proxy"] += int(n or 0)

        # STAGE 4-5: raw cells and UNIQUE cells, AND THIS IS THE STAGE THE CENSUS EXISTS FOR.
        #
        # `content_hash` is the desk's dedup chain -- `enqueue_candidate` dedups on it -- and
        # measuring the collapse on it returns exactly 1.00x, because the dedup is enforced AT
        # THE DOOR and a duplicate hash never becomes a row. That number is worth publishing (it
        # proves the door works) and it is USELESS as an answer to "did a hundred thousand
        # documents collapse into twenty momentum rules", because two rows that differ in one
        # parameter digit carry different hashes and are, as research, the same rule twice.
        #
        # So the census counts THREE identities and prints all three:
        #   content_hash  -- the door. 1.00x by construction; a number above 1 is a door defect.
        #   grid_cell     -- the docket coordinate the gauntlet actually sweeps. THE unique cell.
        #   mechanism     -- the economic claim. The collapse a reader was asking about.
        # `coalesce` makes an absent identity its OWN row rather than merging every unstamped
        # candidate into one: absence never manufactures a duplicate (L1.28a).
        #
        # AND THE CREDIT GOES TO THE PRODUCER THAT CAUSED THE CELL, NOT THE COMPILER THAT STAMPED
        # IT. That is not a new opinion -- `scripts/check_producer_yield._window_cells` already
        # ruled it, and this census disagreeing with the desk's own fence about who made a cell is
        # itself the defect. Cells reach `research_candidates` through `discovery_compiler`, which
        # writes its OWN generator; reading the candidate's stamp alone credits one pass-through
        # with the desk's whole output and reports every real producer as barren. The link that
        # survives the compiler is `discovery_id`. Measured 2026-09-24 on the trading box: the
        # candidate stamp knows 143 producers, the lineage knows 200 -- credit is ADDED, never
        # moved off anybody, and the stamped count is published beside it so the pass-through
        # remains visible.
        lineage = ("lower(coalesce(nullif(d.generator,''), nullif(c.generator,''),"
                   "'_unattributed_generator'))")
        joined = ("research_candidates c left join discoveries d "
                  "on d.discovery_id = c.discovery_id")
        for gen, raw, uniq_h, uniq_c, uniq_m in _rows(
                cur, f"select {lineage}, count(*), count(distinct c.content_hash), "  # noqa: S608
                     "count(distinct coalesce(nullif(c.grid_cell,''), c.content_hash)), "
                     "count(distinct coalesce(nullif(c.mechanism,''), c.content_hash)) "
                     f"from {joined} group by 1"):
            key = _norm(str(gen or "")) or "_unattributed_generator"
            per[key]["raw_cells"] += int(raw or 0)
            per[key]["unique_cells"] += int(uniq_c or 0)
            per[key]["unique_by_content_hash"] += int(uniq_h or 0)
            per[key]["unique_mechanisms"] += int(uniq_m or 0)
        for gen, raw in _rows(
                cur, "select generator, count(*) from research_candidates group by 1"):
            per[_norm(str(gen or "")) or "_unattributed_generator"][
                "raw_cells_stamped_on_candidate"] += int(raw or 0)

        # CELLS JUDGED -- the stage the panel names and the census never had. `gauntlet_submitted`
        # below is the judge's DOOR (donated, claimed, retired, queued for judging); this is the
        # count that came back out of it carrying a verdict, which is a different and smaller
        # number: 1,228 of 356,085 on the trading box. Both are published, because reading one as
        # the other is how a desk believes it has judged what it has only queued.
        judged_expr = ("(c.judged_at is not null and c.judged_at != '') or "
                       "(c.terminal_gate is not null and c.terminal_gate != '')")
        for gen, n in _rows(
                cur, f"select {lineage}, count(*) from {joined} "  # noqa: S608
                     f"where {judged_expr} group by 1"):
            per[_norm(str(gen or "")) or "_unattributed_generator"][
                "cells_judged"] += int(n or 0)

        # STAGE 6-7: submitted to the gauntlet, and what cleared the cheap stages.
        for gen, n in _rows(
                cur, "select generator, count(*) from research_candidates "
                     "where donated_cell is not null or status in "
                     "('donated','claimed','retired','judged') group by 1"):
            per[_norm(str(gen or "_unattributed_generator"))][
                "gauntlet_submitted"] += int(n or 0)
        # CHEAP-STAGE SURVIVORS, AND THE CASE WHERE THE COLUMN IS A LIE OF OMISSION. `survived`
        # defaults to 0, so a registry in which NOTHING has ever been judged returns 0 survivors
        # for every producer and reads exactly like a registry in which everything was judged and
        # everything failed. Those are opposite facts. The census separates them: if no row
        # carries a judge stamp at all, the stage is UNMEASURED with that sentence and the yield
        # tables' own survivor counts are published as the named proxy (L1.28a, WS-005).
        judged_any = _rows(cur, "select count(*) from research_candidates "
                                "where judged_at is not null and judged_at != ''")
        n_judged = int(judged_any[0][0]) if judged_any else 0
        if n_judged:
            for gen, n in _rows(
                    cur, "select generator, count(*) from research_candidates "
                         "where survived = 1 group by 1"):
                per[_norm(str(gen or "_unattributed_generator"))][
                    "cheap_survivors"] += int(n or 0)
        else:
            out["unmeasured"]["cheap_survivors"] = (
                "no research_candidates row carries a judge stamp (`judged_at` null on all "
                f"{_table_count(cur, 'research_candidates')} rows, `terminal_gate` likewise), so "
                "`survived = 0` everywhere is the column's DEFAULT and not a verdict: the cheap "
                "stage is UNMEASURED, not zero. Proxy published as `yield_survivors` from "
                "generator_yield/source_yield, which the producers write themselves")

        # Discoveries: the upstream shape of a cell, and the only stage a seat that donates prose
        # rather than parameters ever reaches. Counted separately so a seat is never read as
        # silent merely because the compiler, not the seat, owns the candidate row.
        for gen, n, uniq in _rows(
                cur, "select generator, count(*), count(distinct content_hash) "
                     "from discoveries group by 1"):
            key = _norm(str(gen or "")) or "_unattributed_generator"
            per[key]["discoveries"] += int(n or 0)
            per[key]["unique_discoveries"] += int(uniq or 0)

        # COMPUTE, from the registry's own yield tables. These are seconds the producers charged
        # themselves; the compute ledger below adds the seconds the CLOCK charged them, and the
        # census keeps the two apart because they answer different questions.
        for gen, gen_n, don, judged, surv, comp in _rows(
                cur, "select generator, generated, donated, judged, survivors, compute_s "
                     "from generator_yield"):
            key = _norm(str(gen or "")) or "_unattributed_generator"
            per[key]["yield_generated"] += float(gen_n or 0)
            per[key]["yield_donated"] += float(don or 0)
            per[key]["yield_judged"] += float(judged or 0)
            per[key]["yield_survivors"] += float(surv or 0)
            per[key]["registry_compute_s"] += float(comp or 0)
        for sid, comp, surv in _rows(
                cur, "select source_id, compute_s, survivors from source_yield"):
            key = src_producer.get(str(sid), "_unattributed_source")
            per[key]["registry_compute_s"] += float(comp or 0)
            per[key]["source_survivors"] += float(surv or 0)

        # REGION, from the sources a producer actually touched. A producer whose sources carry no
        # country reaches the region table only through its own name.
        reg_by_producer: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for sid, key in src_producer.items():
            reg = src_region.get(sid)
            if reg:
                reg_by_producer[key][reg] += 1
        out["region_hits"] = {k: dict(v) for k, v in reg_by_producer.items()}

        # THE BIRTH STAMP, READ WHERE IT IS WRITTEN. `libs/research/attribution.attribute()` now
        # stamps `region` on every row at both registry doors, and on the trading box 356,946 of
        # 356,946 candidates and 79,634 of 79,634 discoveries carry one. The modal stamp over a
        # producer's own rows is the region its evidence actually reached -- an answer no producer
        # NAME could ever give. UNATTRIBUTABLE is deliberately not selectable here: it is the stamp
        # saying it does not know, and the ladder in `build()` has further routes to try.
        stamp_hits: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for gen, where, n in _rows(
                cur, f"select {lineage}, "  # noqa: S608
                     "coalesce(nullif(c.region,''), nullif(d.region,'')), count(*) "
                     f"from {joined} where coalesce(nullif(c.region,''), nullif(d.region,'')) "
                     "is not null group by 1, 2"):
            if str(where) in (*REGIONS, NOT_REGIONAL):
                stamp_hits[_norm(str(gen or "")) or "_unattributed_generator"][
                    str(where)] += int(n or 0)
        out["region_stamp"] = {k: max(v.items(), key=lambda kv: kv[1])[0]
                               for k, v in stamp_hits.items() if v}

        # THE LINEAGE A CERTIFICATE IS JOINED BY. A certificate names a cell
        # (`external.XAUUSD.session_range_breakout`), not a producer; the only non-guess route
        # back is the FAMILY, because `research_candidates` records which generator produced
        # candidates of that family. Modal generator wins and the count rides along, so a reader
        # can see how confident the attribution is instead of taking it on faith.
        fam_gen: dict[str, tuple[str, int]] = {}
        for fam, gen, n in _rows(
                cur, "select family, generator, count(*) from research_candidates "
                     "where family is not null and family != '' group by 1,2"):
            fkey = str(fam).strip().lower()
            gkey = _norm(str(gen or ""))
            if not gkey:
                continue
            prev = fam_gen.get(fkey)
            if prev is None or int(n or 0) > prev[1]:
                fam_gen[fkey] = (gkey, int(n or 0))
        out["family_to_generator"] = {k: v[0] for k, v in fam_gen.items()}

        out["totals"] = {
            "sources": _table_count(cur, "sources"),
            "claims": _table_count(cur, "claims"),
            "mechanisms": n_mech,
            "discoveries": _table_count(cur, "discoveries"),
            "research_candidates": _table_count(cur, "research_candidates"),
            "provenance_edges": _table_count(cur, "provenance"),
        }
        uniq_all = _rows(
            cur, "select count(distinct content_hash), "
                 "count(distinct coalesce(nullif(grid_cell,''), content_hash)), "
                 "count(distinct coalesce(nullif(mechanism,''), content_hash)) "
                 "from research_candidates")
        if uniq_all:
            out["totals"]["unique_by_content_hash"] = int(uniq_all[0][0])
            out["totals"]["unique_cells"] = int(uniq_all[0][1])
            out["totals"]["unique_mechanisms"] = int(uniq_all[0][2])
    finally:
        con.close()
    out["by_producer"] = {k: {kk: (int(vv) if float(vv).is_integer() else round(float(vv), 3))
                              for kk, vv in v.items()} for k, v in per.items()}
    return out


# -------------------------------------------------------------------------------------- compute

def measure_compute(window_days: float) -> dict[str, Any]:
    """Compute hours per named run, from the compute ledger that already prices every leg.

    The ledger is the desk's only real denominator (`libs/ops/compute_ledger`), so the census
    reads it rather than timing anything itself. An absent ledger is UNMEASURED with a reason:
    certificates-per-compute-hour then has no denominator and the ratio is published as
    UNMEASURED, which is a verdict a reader can act on.
    """
    out: dict[str, Any] = {"available": False, "why": "", "hours": {},
                           "window_days": window_days}
    try:
        sys.path.insert(0, str(ROOT))
        from libs.ops.compute_ledger import cost_by_run
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: libs.ops.compute_ledger unimportable ({type(exc).__name__})"
        return out
    try:
        agg = cost_by_run(window_days=int(max(1, round(window_days))))
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: cost_by_run failed ({type(exc).__name__}: {exc})"
        return out
    out["available"] = True
    out["hours"] = {_norm(k): {"hours": float(v.get("hours") or 0.0),
                               "runs": int(v.get("runs") or 0),
                               "failure_rate": v.get("failure_rate")}
                    for k, v in agg.items()}
    out["n_runs_priced"] = len(out["hours"])
    if not out["hours"]:
        out["why"] = (f"{UNMEASURED}: compute ledger holds no costed run in the last "
                      f"{window_days:g} days on this host")
    return out


# -------------------------------------------------------------------------------- orthogonality

def measure_orthogonality(path: Path | None = None) -> dict[str, Any]:
    """Marginal breadth each producer ADDED, reused from `scripts/check_producer_yield.py`.

    THE COLUMN VOLUME CANNOT MOVE. `libs.research.sandbox_rotation.breadth` is the participation
    ratio of the singular-value spectrum of the producer x (family|symbol|horizon) matrix, and a
    producer's score is the drop when its row is removed -- so a hundred copies of one momentum
    rule score as one cell's worth and the census cannot be gamed by emitting more of the same.

    READ, NEVER RE-DERIVED. That SVD already runs on a clock and already publishes a number per
    producer; computing a second one here would cost the 8 GB box an hour it does not have and
    would hand a reader two answers to one question. The artifact's age travels with the number,
    because a breadth figure from last week is a different claim from one from this hour, and an
    absent artifact is UNMEASURED WITH ITS REASON rather than a zero for every organ (L1.28a).
    """
    # RESOLVED AT CALL TIME, NEVER BOUND AS A DEFAULT. A default argument freezes the path at
    # import and quietly ignores every later reconfiguration -- the same trap
    # `check_producer_yield._window_cells` already names, and the reason a probe of this census
    # read `C:\Users\Administrator\desks\...` while measuring the desk's real registry.
    path = PRODUCER_YIELD if path is None else path
    out: dict[str, Any] = {"available": False, "why": "", "added": {}, "source": str(
        path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)}
    doc = _load_json(path)
    if not isinstance(doc, dict):
        out["why"] = (f"{UNMEASURED}: {path.name} is absent or unreadable on this host, so the "
                      "orthogonality each producer added has no source. The fence that writes it "
                      "is `scripts/check_producer_yield.py`; run it and this column fills in.")
        return out
    inner = doc.get("cells_owed")
    block: dict[str, Any] = inner if isinstance(inner, dict) else doc
    rows = block.get("producers") if isinstance(block.get("producers"), list) else None
    if not rows:
        out["why"] = (f"{UNMEASURED}: {path.name} carries no per-producer row under "
                      "`cells_owed.producers`, so no producer's marginal breadth can be read")
        return out
    raw_breadth = block.get("breadth")
    breadth: dict[str, Any] = raw_breadth if isinstance(raw_breadth, dict) else {}
    if not breadth.get("available"):
        out["why"] = (f"{UNMEASURED}: the yield fence reports its breadth matrix unavailable "
                      f"({breadth.get('why') or 'no reason recorded'}), so every marginal it "
                      "published would be a zero standing in for an unmeasured spectrum")
        return out
    added: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _norm(str(row.get("key") or row.get("producer") or ""))
        val = row.get("orthogonality_added")
        if key and isinstance(val, (int, float)) and not isinstance(val, bool):
            added[key] = float(val)
    out["available"] = bool(added)
    out["added"] = added
    out["n_producers"] = len(added)
    out["at"] = doc.get("generated_utc")
    out["window_hours"] = block.get("window_hours")
    out["age_hours"] = _age_hours(doc.get("generated_utc"))
    out["basis"] = ("marginal effective rank from libs.research.sandbox_rotation.breadth over the "
                    "producer x (family|symbol|horizon) matrix of the yield fence's own window, "
                    "published by scripts/check_producer_yield.py")
    if not added:
        out["why"] = (f"{UNMEASURED}: {path.name} holds {len(rows)} producer row(s) and none "
                      "carries a numeric `orthogonality_added`")
    return out


# --------------------------------------------------------------------- certificates and forward

def _cert_tokens(key: str, row: dict[str, Any]) -> set[str]:
    """Every token a certificate can be joined to a producer by, lowercased."""
    toks: set[str] = set()
    for part in str(key).replace(".", " ").replace("_", " ").split():
        if part:
            toks.add(part.lower())
    for field in ("hunt", "sym", "symbol", "family", "lane", "origin", "generator"):
        val = row.get(field)
        if isinstance(val, str) and val:
            toks.add(val.lower())
            toks.add(Path(val).stem.lower())
    return toks


def measure_terminal(reg: dict[str, Any]) -> dict[str, Any]:
    """Certificates, forward enrolments and live rows, attributed where attribution EXISTS.

    A certificate whose lineage does not name a producer is counted at the TOP LEVEL as
    unattributed, never spread across producers by guesswork. The desk has one certificate truth
    (`UNIVERSAL_SURVIVORS.json`, written by the sealed gauntlet) and this reads that file only.
    """
    out: dict[str, Any] = {"certificates": {}, "forward": {}, "live": {},
                           "unattributed": {}, "why": {}, "attribution": {}}
    fam_gen: dict[str, str] = reg.get("family_to_generator") or {}
    known = {k for k in reg.get("by_producer", {}) if not k.startswith("_")}

    def _attribute(key: str, row: dict[str, Any]) -> tuple[str | None, str]:
        """Producer behind one certificate/sleeve, and HOW it was reached.

        Two routes, tried in order, and the route is recorded beside the count: a direct name
        match against a producer the registry knows, then the family lineage in
        `research_candidates`. A row that neither route reaches is UNATTRIBUTED by name -- it is
        never spread across producers, because a certificate credited to the wrong organ is worse
        than a certificate credited to nobody.
        """
        toks = _cert_tokens(key, row)
        hit = sorted(toks & known)
        if hit:
            return hit[0], "direct name match against a registry producer"
        for tok in sorted(toks):
            gen = fam_gen.get(tok)
            if gen:
                return gen, f"family `{tok}` -> modal generator in research_candidates"
        return None, "no name and no family in research_candidates reaches a producer"

    us = _load_json(UNIVERSAL_SURVIVORS)
    surv = us.get("survivors") if isinstance(us, dict) else None
    if not isinstance(surv, dict):
        out["why"]["certificates"] = (
            f"{UNMEASURED}: {UNIVERSAL_SURVIVORS.name} absent or carries no `survivors` map")
    else:
        unattr = 0
        routes: dict[str, int] = defaultdict(int)
        for key, row in surv.items():
            row = row if isinstance(row, dict) else {}
            who, how = _attribute(str(key), row)
            routes[how] += 1
            if who:
                out["certificates"][who] = out["certificates"].get(who, 0) + 1
            else:
                unattr += 1
        out["attribution"]["certificates"] = dict(routes)
        out["unattributed"]["certificates"] = unattr
        out["unattributed"]["certificates_why"] = (
            "no name and no family lineage on the certificate reaches a producer the registry "
            "knows: these certificates are REAL and their producer is UNMEASURED, which is a gap "
            "in lineage stamping, not a zero for anybody")
        out["n_certificates"] = len(surv)

    for path, field, label in ((SLEEVE_REGISTRY, "forward", "forward enrolments"),
                               (SLEEVES, "live", "live sleeve rows")):
        blob = _load_json(path)
        rows: list[Any] = []
        if isinstance(blob, dict):
            for cand in ("sleeves", "rows", "registry", "entries"):
                if isinstance(blob.get(cand), list):
                    rows = blob[cand]
                    break
            else:
                rows = [v for v in blob.values() if isinstance(v, dict)]
        elif isinstance(blob, list):
            rows = blob
        if not rows:
            out["why"][field] = f"{UNMEASURED}: {path.name} absent or holds no {label}"
            continue
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            if field == "live" and str(row.get("status") or "").upper() != "LIVE":
                continue
            count += 1
            who, _how = _attribute(str(row.get("name") or ""), row)
            if who:
                out[field][who] = out[field].get(who, 0) + 1
        out[f"n_{field}"] = count
    return out


# ---------------------------------------------------------------------------------------- build

def _ratio(num: Any, den: Any) -> float | str:
    """A ratio, or UNMEASURED -- and it must survive being handed the WORD `UNMEASURED`.

    It used to take only numbers or None, because an unmeasured stage arrived here as None. Now
    that an unmeasured stage carries the word itself, a bare `float()` on it raised ValueError and
    took the whole census down on any host whose registry will not open -- a clean checkout, CI,
    and the box on the day the registry is locked. A measurement organ that crashes when a
    measurement is missing reports nothing at all, which is the one outcome worse than UNMEASURED.
    """
    if not isinstance(num, (int, float)) or isinstance(num, bool):
        return UNMEASURED
    if not isinstance(den, (int, float)) or isinstance(den, bool) or not den:
        return UNMEASURED
    return round(float(num) / float(den), 4)


#: Roster kinds that name a way the DESK RUNS SOMETHING rather than a place evidence came from.
#: DERIVED, never a producer list: `PRODUCER_CENSUS.json` and `COMPONENT_REGISTRY.json` assign
#: these kinds themselves, so an organ that lands next month inherits the verdict. A producer
#: filed under one of them whose name, ground, sources and birth stamp ALL reach no region is desk
#: machinery -- `executable:scripts/acquire_data.py` is a script on this desk, not a country --
#: and NOT_REGIONAL is that verdict (L1.28a). It is consulted LAST, so a regional department filed
#: as a `leg` still wins on its own name: 1,279 of the 1,624 producers that had no region at all
#: were executables, libraries, timers, legs, tasks and batteries of this repository.
DESK_EXECUTION_KINDS: frozenset[str] = frozenset({
    "executable", "library", "leg", "timer", "task", "battery", "component", "seat",
    "daily_step", "resident", "federation_worker", "service", "script", "producer", "organ",
    "fence", "check", "hook", "cron", "worker", "step", "job",
})


def measurement_coverage(rows: list[dict[str, Any]],
                         ortho: dict[str, Any] | None = None) -> dict[str, Any]:
    """PER-PRODUCER MEASUREMENT COVERAGE: the share of rows on which each column is a number.

    THE DEFECT THIS NUMBER EXISTS TO MAKE IMPOSSIBLE AGAIN. On 2026-09-24 the producers panel
    listed 1,981 producers with compute hours on every row and UNMEASURED in all five columns
    beside them -- the desk knew exactly what each organ COST and nothing about what it MADE,
    which is precisely the wrong half of the pair to have. Nothing measured that, so nothing
    could fail on it.

    IT IS A RATCHET AND THE DENOMINATOR IS PART OF IT. `n_producers` travels with every ratio so
    coverage can never be improved by dropping producers out of the bottom: a census of the twelve
    organs that happen to be measurable is not a census (L1.50, and the standing order that the
    producer count only ever goes up). `region_coverage` counts a NOT_REGIONAL verdict as covered
    -- it is an answer about desk machinery -- and `unattributed` as not, because that is the
    state where the desk genuinely does not know.
    """
    total = len(rows)
    per: dict[str, Any] = {}
    for col in PANEL_COLUMNS:
        n = sum(1 for r in rows
                if isinstance(r.get(col), (int, float)) and not isinstance(r.get(col), bool))
        per[col] = {"measured": n, "of": total,
                    "coverage": round(n / total, 4) if total else UNMEASURED,
                    "nonzero": sum(1 for r in rows if isinstance(r.get(col), (int, float))
                                   and not isinstance(r.get(col), bool) and r[col])}
    regional = sum(1 for r in rows if r.get("region") in REGIONS)
    not_regional = sum(1 for r in rows if r.get("region") == NOT_REGIONAL)
    unattributed = sum(1 for r in rows if r.get("region") == UNATTRIBUTED)
    routes: dict[str, int] = defaultdict(int)
    for r in rows:
        routes[str(r.get("region_route") or "none").split(":")[0]] += 1
    worst = min((v["coverage"] for v in per.values()
                 if isinstance(v["coverage"], float)), default=UNMEASURED)
    return {
        "n_producers": total,
        "columns": per,
        "worst_column_coverage": worst,
        "fully_measured_rows": sum(
            1 for r in rows
            if all(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool)
                   for c in PANEL_COLUMNS)),
        "region": {
            "regional": regional, "not_regional": not_regional,
            "unattributed": unattributed, "of": total,
            "coverage": round((regional + not_regional) / total, 4) if total else UNMEASURED,
            "routes": dict(sorted(routes.items(), key=lambda kv: -kv[1])),
            "rule": ("a NOT_REGIONAL verdict is COVERED -- it is the answer for a method, a "
                     "compiler or a declared seat. Only `unattributed` counts as a gap, and it "
                     "is a gap the desk can name rather than a silence."),
        },
        "orthogonality_source": (ortho or {}).get("source"),
        "orthogonality_age_hours": (ortho or {}).get("age_hours"),
        "law": ("COVERAGE RATCHETS UP ONLY, AND NEVER BY SHRINKING THE DENOMINATOR. "
                "`n_producers` is published with every ratio; a pass that raises a share by "
                "dropping producers is a regression wearing an improvement's number (L1.50)."),
    }


def _resolve_region(key: str, name: str, meta: dict[str, Any], reg: dict[str, Any],
                    stamped: dict[str, str]) -> tuple[str, str]:
    """The producer's region and the ROUTE that reached it. Every rule delegated to the helper.

    SIX ROUTES, TRIED IN THE ORDER THE EVIDENCE DESERVES, and the route rides along so a reader
    can see how a row got its answer instead of taking it on faith:

        name              `libs.research.attribution.region_of` on the producer's own name
        namespace         the same rule on each COLON SEGMENT of a filed name. `forest_runner:
                          china:academic` is the China lane of the forest runner, and neither the
                          whole string nor its head is a region token -- so 243 registry-seen
                          generators, the whole forest federation among them, read `unattributed`
                          while their middle segment named the ground outright.
        sources           the modal country of the sources the producer actually crawled
        ground            `region_of_ground`: the producer's OWN declared source in the desk's
                          source registry (`rba_tables` -> rba.gov.au -> Oceania)
        birth stamp       the modal region its own registry rows carry, written at the two
                          registry doors by `attribution.attribute()` -- the route a NAME can
                          never give, and the reason `attribution_census` exists
        desk machinery    `is_non_regional`, then the roster's own execution kind -> NOT_REGIONAL

    Only then `unattributed`, which now means what it says: nothing about this producer, its
    filing, its sources, its ground, its cells or its kind reaches a region. That is a real
    verdict and it is UNMEASURED, never a zero for any region (L1.28a).
    """
    for token in (name, key):
        hit = _region_for(token)
        if hit:
            return hit, "name"
    # THE NAMESPACE LADDER, applied to the segments the helper's own prefix table cannot peel.
    # The RULE stays in the helper -- this only decides which tokens to offer it -- and a segment
    # of two characters or fewer is never offered, because `is`, `na`, `no` and `in` are ISO codes
    # AND ordinary lane names, and a false Iceland is worse than an honest gap.
    for token in (name, key):
        for seg in str(token).split(":"):
            seg = seg.strip()
            if len(seg) <= 2:
                continue
            hit = _attr.region_of_command(seg) or _region_for(seg)
            if hit:
                return hit, "namespace"
    hits = (reg.get("region_hits") or {}).get(key) or {}
    if hits:
        return max(hits.items(), key=lambda kv: kv[1])[0], "sources"
    for token in (name, key):
        hit = _attr.region_of_ground(token)
        if hit:
            return hit, "ground"
    hit = (reg.get("region_stamp") or {}).get(key)
    if hit:
        return hit, "birth_stamp_registry"
    hit = stamped.get(key) or stamped.get(_norm(name))
    if hit:
        return hit, "birth_stamp_census"
    if _attr.is_non_regional(name) or _attr.is_non_regional(key):
        return NOT_REGIONAL, "method_or_desk_organ"
    if str(meta.get("kind") or "").strip().lower() in DESK_EXECUTION_KINDS:
        return NOT_REGIONAL, f"roster_kind:{meta.get('kind')}"
    return UNATTRIBUTED, "none"


def build(window_days: float = COMPUTE_WINDOW_DAYS,
          db: Path | None = None) -> dict[str, Any]:
    """The whole census: roster x funnel x ratios, rolled up by region, with the zero list."""
    t0 = time.time()
    # Resolved here, not in the signature: a default argument freezes the registry path at import.
    db = REGISTRY_DB if db is None else db
    roster, roster_notes = build_roster()
    reg = measure_registry(db)
    comp = measure_compute(window_days)
    term = measure_terminal(reg)
    ortho = measure_orthogonality()
    stamped = _stamped_regions()
    scanned = bool(reg.get("available"))
    # THE ZERO THAT IS A MEASUREMENT. When the registry opened, every GROUP BY below ran over the
    # WHOLE table -- so a producer missing from a result is a producer with no row, which is a
    # measured zero and a finding, not an absence. Publishing UNMEASURED there said the desk had
    # not looked, when it had looked at all 356,946 candidates and found none of this producer's.
    # The distinction is the whole of L1.28a and it runs both ways: when the registry could NOT be
    # opened, every one of these stages stays UNMEASURED, which the block further down enforces.
    zero_if_scanned: Any = 0 if scanned else UNMEASURED

    # Every key the registry has seen that no roster knows about is ITSELF a finding.
    per = reg.get("by_producer", {})
    for key in per:
        if key.startswith("_"):
            continue
        roster.setdefault(key, {
            "producer": key, "kind": "generator", "clock": None,
            "roster_source": "data/alpha_registry.sqlite (generator seen, no roster row)",
        })

    rows: list[dict[str, Any]] = []
    for key, meta in sorted(roster.items()):
        m = per.get(key, {})
        hours_row = comp.get("hours", {}).get(key) or {}
        ledger_h = float(hours_row.get("hours") or 0.0)
        reg_h = float(m.get("registry_compute_s") or 0.0) / 3600.0
        total_h = round(ledger_h + reg_h, 4)
        name = str(meta.get("producer") or key)
        raw = m.get("raw_cells", zero_if_scanned)
        uniq = m.get("unique_cells", zero_if_scanned)
        srcs = m.get("sources_visited", zero_if_scanned)
        judged_cells = m.get("cells_judged", zero_if_scanned)
        certs = term["certificates"].get(key, 0)
        region, region_route = _resolve_region(key, name, meta, reg, stamped)
        funnel = {
            "sources_visited": srcs,
            "documents_retained": m.get("documents_retained", zero_if_scanned),
            "raw_mechanism_claims": m.get("raw_mechanism_claims", zero_if_scanned),
            "canonical_mechanisms": (
                m.get("canonical_mechanisms")
                if "canonical_mechanisms" in m
                else {"verdict": UNMEASURED,
                      "why": reg.get("unmeasured", {}).get("canonical_mechanisms", ""),
                      "proxy_distinct_mechanism_ids": m.get("canonical_mechanisms_proxy", 0)}),
            "raw_cells": raw,
            "raw_cells_stamped_on_candidate": m.get("raw_cells_stamped_on_candidate",
                                                    zero_if_scanned),
            "unique_cells": uniq,
            "gauntlet_submitted": m.get("gauntlet_submitted", zero_if_scanned),
            "cells_judged": judged_cells,
            "cheap_survivors": (
                m.get("cheap_survivors", zero_if_scanned)
                if "cheap_survivors" not in reg.get("unmeasured", {})
                else {"verdict": UNMEASURED,
                      "why": reg["unmeasured"]["cheap_survivors"],
                      "proxy_yield_survivors": m.get("yield_survivors", 0)}),
            "certificates": certs,
            "forward_enrolled": term["forward"].get(key, 0),
            "live_contribution": term["live"].get(key, 0),
        }
        if not scanned:
            for stage in ("sources_visited", "documents_retained", "raw_mechanism_claims",
                          "raw_cells", "raw_cells_stamped_on_candidate", "unique_cells",
                          "gauntlet_submitted", "cells_judged", "cheap_survivors"):
                funnel[stage] = UNMEASURED
        surv_v = funnel["cheap_survivors"]
        surv = surv_v if isinstance(surv_v, (int, float)) else (m.get("yield_survivors") or 0)
        added = ortho.get("added", {}).get(key)
        rows.append({
            "producer": name,
            "key": key,
            "kind": meta.get("kind"),
            "clock": meta.get("clock"),
            "roster_source": meta.get("roster_source"),
            "region": region,
            "region_route": region_route,
            "funnel": funnel,
            "discoveries": m.get("discoveries", zero_if_scanned),
            "dedup_collapse": (round(float(raw) / float(uniq), 3)
                               if isinstance(raw, (int, float)) and isinstance(uniq, (int, float))
                               and raw and uniq else UNMEASURED),
            # ---------------------------------------------------------- THE SIX PANEL COLUMNS
            # Top level, beside `compute_hours`, because that is where every reader of this
            # artifact looks -- `desk_dashboard_state._producers` reads `row.get(<name>)` and
            # nothing nested, so five of the six rendered UNMEASURED for every producer while
            # the funnel below held four of them all along. `cells` is the name the panel falls
            # through to; the funnel keeps every stage it had. Nothing is renamed or removed.
            "cells": raw,
            "unique_cells": uniq,
            "cells_judged": judged_cells,
            "certificates": certs,
            "orthogonality_added": added if added is not None else UNMEASURED,
            "compute_hours": total_h if (ledger_h or reg_h) else (
                UNMEASURED if not comp.get("available") else 0.0),
            "compute_hours_ledger": ledger_h,
            "compute_hours_registry": round(reg_h, 4),
            "ratios": {
                "cells_per_source": _ratio(uniq, srcs),
                "survivors_per_source": _ratio(surv, srcs),
                "certificates_per_compute_hour": (
                    _ratio(certs or 0, total_h) if (ledger_h or reg_h) else UNMEASURED),
            },
        })

    # ----------------------------------------------------------------- region roll-up
    by_region: dict[str, dict[str, Any]] = {}
    for bucket in ROLLUP_BUCKETS:
        by_region[bucket] = {"producers": 0, "sources_visited": 0, "documents_retained": 0,
                             "raw_cells": 0, "unique_cells": 0, "gauntlet_submitted": 0,
                             "cells_judged": 0, "cheap_survivors": 0, "certificates": 0,
                             "compute_hours": 0.0}
    for row in rows:
        b = by_region.setdefault(row["region"], dict(by_region[UNATTRIBUTED]))
        b["producers"] += 1
        for stage in ("sources_visited", "documents_retained", "raw_cells", "unique_cells",
                      "gauntlet_submitted", "cells_judged", "cheap_survivors", "certificates"):
            v = row["funnel"].get(stage)
            if isinstance(v, (int, float)):
                b[stage] += v
        if isinstance(row["compute_hours"], (int, float)):
            b["compute_hours"] += float(row["compute_hours"])
    # THE CELL-LEVEL COUNT, BESIDE THE PRODUCER-LEVEL ONE, BECAUSE THEY ANSWER DIFFERENT
    # QUESTIONS. `unique_cells` above rolls a producer's WHOLE output into the producer's ONE
    # region, so a compiler that works every ground is credited entirely to its modal one and
    # every other region reads zero -- which is exactly how Europe came to show 1,973 sources and
    # no cells. `unique_cells_stamped` is the per-CELL count from the birth stamp
    # (attribution_census.unique_cells_by_region), where a cell is counted under the ground its
    # own lineage reached. UNMEASURED when the artifact is absent, never zero (L1.28a).
    stamped_cells = _load_json(ATTRIBUTION)
    cell_block = (stamped_cells or {}).get("unique_cells_by_region") \
        if isinstance(stamped_cells, dict) else None
    cells_by_region = (cell_block or {}).get("by_region") if isinstance(cell_block, dict) else None
    for name, b in by_region.items():
        b["unique_cells_stamped"] = (int(cells_by_region.get(name, 0))
                                     if isinstance(cells_by_region, dict) else UNMEASURED)
    for b in by_region.values():
        b["compute_hours"] = round(b["compute_hours"], 4)
        b["survivors_per_region"] = b["cheap_survivors"]
        b["cells_per_source"] = _ratio(b["unique_cells"], b["sources_visited"])
        b["survivors_per_source"] = _ratio(b["cheap_survivors"], b["sources_visited"])
        b["certificates_per_compute_hour"] = _ratio(b["certificates"], b["compute_hours"])
        b["dedup_collapse"] = _ratio(b["raw_cells"], b["unique_cells"])

    # ------------------------------------------------------- THE DELIVERABLE: compute, no cells
    zero: list[dict[str, Any]] = []
    for row in rows:
        h = row["compute_hours"]
        if not isinstance(h, (int, float)) or h <= 0:
            continue
        uniq = row["funnel"].get("unique_cells")
        disc = row.get("discoveries") or 0
        if isinstance(uniq, (int, float)) and uniq > 0:
            continue
        if isinstance(disc, (int, float)) and disc > 0:
            continue
        zero.append({
            "producer": row["producer"], "key": row["key"], "kind": row["kind"],
            "clock": row["clock"], "region": row["region"],
            "compute_hours": h,
            "compute_hours_ledger": row["compute_hours_ledger"],
            "compute_hours_registry": row["compute_hours_registry"],
            "sources_visited": row["funnel"].get("sources_visited"),
            "unique_cells": uniq,
            "why": ("consumed measured compute and produced no unique cell and no discovery in "
                    "the registry: either it is exploratory and must say so, or it is a defect"),
        })
    zero.sort(key=lambda r: -float(r["compute_hours"]))

    # THE LEDGER CAN BE PRESENT AND STILL SAY NOTHING ABOUT THESE PRODUCERS. `cost_by_run` keys
    # on the LEG name; if no leg in the window matches a roster producer, every ledger hour in
    # the census is 0.0 and `certificates_per_compute_hour` is being divided by a registry number
    # alone. A reader must be told that, or they will read a small denominator as a cheap organ.
    # AND A NULL NOTE SAID TWO DIFFERENT THINGS, WHICH IS WHY IT IS NOW ALWAYS WRITTEN. This
    # field was `None` both when there was no caveat to make (the ledger matched producers and
    # the hours are real) and when the caveat could not be computed at all (the ledger is not
    # available). A reader downstream -- the desk dashboard among them -- rendered that null as
    # UNMEASURED, which was wrong in the first case and not specific enough in the second: a
    # measured emptiness is a MEASUREMENT, and only a genuine hole may wear the word UNMEASURED.
    # So all three states are now named, and the field is never null.
    matched_ledger = sum(1 for r in rows if r["compute_hours_ledger"] > 0)
    if not comp.get("available"):
        ledger_note = (
            f"{UNMEASURED}: the compute ledger itself is unavailable on this host "
            f"({comp.get('why') or 'no reason recorded'}), so no caveat about it could be "
            "computed. Every compute hour in this census comes from the producers' own "
            "generator_yield/source_yield compute_s.")
    elif not matched_ledger:
        ledger_note = (
            f"{UNMEASURED}: the compute ledger holds {comp.get('n_runs_priced', 0)} priced run(s) "
            f"in the last {window_days:g} days and NONE of them names a roster producer "
            "(cost_by_run keys on the leg name), so every ledger hour here is 0.0 and all compute "
            "in this census comes from generator_yield/source_yield compute_s, which the "
            "producers charge themselves. Certificates-per-compute-hour is a registry ratio on "
            "this host, not a wall-clock one.")
    else:
        ledger_note = (
            f"NO CAVEAT: the compute ledger is available and {matched_ledger} roster producer(s) "
            f"match a priced run in the last {window_days:g} days, so certificates-per-compute-"
            "hour has a wall-clock denominator for those producers. A producer outside that set "
            "still charges itself through generator_yield/source_yield compute_s.")

    def _certs(r: dict[str, Any]) -> int:
        v = r["funnel"].get("certificates")
        return int(v) if isinstance(v, (int, float)) else 0

    def _cells(r: dict[str, Any]) -> int:
        v = r["funnel"].get("unique_cells")
        return int(v) if isinstance(v, (int, float)) else 0

    # CERTIFICATES FIRST, CELLS AS THE TIE-BREAK. Ordering on certificates alone puts 1,400
    # producers that have neither at the top in alphabetical order, which is a table that says
    # nothing; the tie-break makes the top of the list the producers that actually did something.
    top_certs = [r for r in sorted(rows, key=lambda r: (-_certs(r), -_cells(r), r["key"]))
                 if _certs(r) or _cells(r)][:10]
    productive = [r for r in rows if _cells(r) > 0]
    coverage = measurement_coverage(rows, ortho)

    census = {
        "at": _now(),
        "elapsed_s": round(time.time() - t0, 3),
        "law": ("PRODUCTIVITY IS MEASURED PER PRODUCER OR IT IS NOT CLAIMED. Code that exists "
                "and is scheduled is not code that produces cells; this census measures the "
                "eleven-stage funnel and the four marginal ratios for every producer on the two "
                "existing rosters, rolls it up by region, and publishes the producers that "
                "consumed compute and produced nothing. A stage with no measurement reads "
                "UNMEASURED with its reason and never zero (L1.28a). Low productivity is NOT a "
                "failure -- an exploratory organ is allowed to be unproductive if it says so."),
        "host": os.environ.get("COMPUTERNAME") or os.uname().nodename,  # type: ignore[attr-defined]
        "window_days": window_days,
        "n_producers": len(rows),
        "n_productive": len(productive),
        "n_zero_cell_with_compute": len(zero),
        "roster_notes": roster_notes,
        "registry_available": reg.get("available"),
        "registry_why": reg.get("why"),
        "registry_totals": reg.get("totals"),
        "compute_available": comp.get("available"),
        "compute_why": comp.get("why"),
        "compute_ledger_matched_producers": matched_ledger,
        "compute_ledger_note": ledger_note,
        "unmeasured_stages": reg.get("unmeasured", {}),
        # THE RATCHET'S SOURCE OF TRUTH: how much of each published column is actually measured.
        # A compute cost with no output measurement beside it is the one number a reader cannot
        # act on, so the share of rows carrying each is itself published and may only rise.
        "measurement_coverage": coverage,
        "orthogonality": {k: v for k, v in ortho.items() if k != "added"},
        "totals": {
            "sources_visited": sum(v for r in rows
                                   if isinstance(v := r["funnel"]["sources_visited"], int)),
            "raw_cells": sum(v for r in rows
                             if isinstance(v := r["funnel"]["raw_cells"], int)),
            "unique_cells": reg.get("totals", {}).get("unique_cells"),
            "certificates": term.get("n_certificates", UNMEASURED),
            "forward_enrolled": term.get("n_forward", UNMEASURED),
            "live": term.get("n_live", UNMEASURED),
            "unattributed_certificates": term.get("unattributed", {}).get("certificates"),
        },
        "dedup": {
            "raw_cells": reg.get("totals", {}).get("research_candidates"),
            "unique_by_content_hash": reg.get("totals", {}).get("unique_by_content_hash"),
            "unique_cells": reg.get("totals", {}).get("unique_cells"),
            "unique_mechanisms": reg.get("totals", {}).get("unique_mechanisms"),
            "collapse_at_the_door": _ratio(reg.get("totals", {}).get("research_candidates"),
                                           reg.get("totals", {}).get("unique_by_content_hash")),
            "collapse": _ratio(reg.get("totals", {}).get("research_candidates"),
                               reg.get("totals", {}).get("unique_cells")),
            "collapse_to_mechanism": _ratio(reg.get("totals", {}).get("research_candidates"),
                                            reg.get("totals", {}).get("unique_mechanisms")),
            "chain": ("research_candidates.content_hash -- the SAME hash "
                      "libs/moat/registry.enqueue_candidate dedups on, so the collapse is the "
                      "desk's own dedup and not a second opinion invented here. It reads 1.00x "
                      "because the dedup is enforced AT THE DOOR; the collapse a reader wants is "
                      "to `grid_cell` (the docket coordinate the gauntlet sweeps) and to "
                      "`mechanism` (the economic claim), both published beside it."),
        },
        "by_region": by_region,
        "top_by_certificates": [
            {"producer": r["producer"], "certificates": _certs(r),
             "unique_cells": r["funnel"].get("unique_cells"),
             "compute_hours": r["compute_hours"], "region": r["region"]}
            for r in top_certs],
        "zero_cell_compute": zero[:60],
        "producers": rows,
        "sources": {
            "roster": "reports/PRODUCER_CENSUS.json + reports/COMPONENT_REGISTRY.json",
            "sources_visited": "data/alpha_registry.sqlite: sources GROUP BY discovered_via",
            "documents_retained": "data/alpha_registry.sqlite: count(distinct claims.doc_id)",
            "raw_mechanism_claims": "data/alpha_registry.sqlite: count(claims) per source",
            "canonical_mechanisms": "data/alpha_registry.sqlite: mechanisms (empty -> UNMEASURED,"
                                    " proxy = distinct discoveries.mechanism_id)",
            "raw_cells": "data/alpha_registry.sqlite: count(research_candidates) per producer, "
                         "credited through discoveries.discovery_id so the compiler that stamped "
                         "a cell is never credited with the producer that caused it (the same "
                         "rule scripts/check_producer_yield._window_cells already applies)",
            "raw_cells_stamped_on_candidate": "the same count read off research_candidates."
                                              "generator alone, published so the pass-through "
                                              "share stays visible",
            "unique_cells": "count(distinct coalesce(grid_cell, content_hash)) per producer",
            "gauntlet_submitted": "research_candidates where donated_cell not null or status in "
                                  "(donated, claimed, retired, judged) -- the judge's DOOR",
            "cells_judged": "research_candidates carrying a verdict stamp (judged_at non-empty "
                            "or terminal_gate non-empty) -- what came back OUT of that door",
            "cheap_survivors": "research_candidates where survived = 1",
            "certificates": "desks/mt5/reports/UNIVERSAL_SURVIVORS.json survivors map",
            "forward_enrolled": "desks/mt5/data/sleeve_registry.json",
            "live_contribution": "desks/mt5/data/sleeves.json rows with status LIVE",
            "orthogonality_added": "desks/mt5/reports/PRODUCER_YIELD.json cells_owed.producers[]."
                                   "orthogonality_added -- marginal effective rank from "
                                   "libs.research.sandbox_rotation.breadth, READ and never "
                                   "re-derived here",
            "compute_hours": "libs/ops/compute_ledger.cost_by_run + registry generator_yield/"
                             "source_yield compute_s",
            "region": "libs/research/attribution.py, delegated in full: producer name -> colon "
                      "namespace segment -> modal sources.country -> the producer's own declared "
                      "ground -> the birth stamp on its registry rows -> NOT_REGIONAL for a "
                      "method, desk organ or declared execution kind. `region_route` on each row "
                      "names which of those answered.",
            "measured_zero": "when the registry opened, every per-producer GROUP BY ran over the "
                             "whole table, so a producer absent from a result has a MEASURED "
                             "zero. When it did not open, every registry stage is UNMEASURED.",
        },
    }
    return census


# --------------------------------------------------------------------------------------- render

def _fmt(v: Any, width: int = 9) -> str:
    if isinstance(v, float):
        return f"{v:>{width}.3f}"
    if isinstance(v, int):
        return f"{v:>{width}d}"
    s = str(v)
    return f"{s[:width]:>{width}}"


def render(census: dict[str, Any]) -> str:
    """One screen. A census a reader scrolls is a census a reader does not read."""
    L: list[str] = []
    L.append("# RESEARCH PRODUCTIVITY CENSUS")
    L.append("")
    L.append(f"_Derived by `desks/mt5/research/productivity_census.py` at "
             f"{census['at']}; DO NOT EDIT -- regenerate._")
    L.append("")
    t = census["totals"]
    d = census["dedup"]
    L.append(f"**{census['n_producers']} producers** | productive "
             f"**{census['n_productive']}** | compute-with-zero-cells "
             f"**{census['n_zero_cell_with_compute']}** | certificates "
             f"**{t['certificates']}** (unattributed {t['unattributed_certificates']}) | "
             f"forward {t['forward_enrolled']} | live {t['live']}")
    L.append("")
    L.append(f"**Dedup (three identities, all measured):** {d['raw_cells']} raw cells -> "
             f"{d['unique_by_content_hash']} distinct `content_hash` "
             f"({d['collapse_at_the_door']}x -- the door, 1.00 means it works) -> "
             f"**{d['unique_cells']} distinct `grid_cell` ({d['collapse']}x)** -> "
             f"{d['unique_mechanisms']} distinct `mechanism` "
             f"({d['collapse_to_mechanism']}x). The last two are the duplication a reader was "
             f"asking about; the first cannot show it.")
    if census.get("unmeasured_stages"):
        for stage, why in census["unmeasured_stages"].items():
            L.append(f"**UNMEASURED `{stage}`:** {why}")
    if not census.get("compute_available"):
        L.append(f"**UNMEASURED compute:** {census.get('compute_why')}")
    if census.get("compute_ledger_note"):
        # The note now names the no-caveat case too, so the label is neutral: calling a clean
        # reading a "caveat" is the same class of mislabel this pass exists to remove.
        L.append(f"**Compute ledger:** {census['compute_ledger_note']}")
    if census.get("totals", {}).get("unattributed_certificates"):
        L.append(f"**{census['totals']['unattributed_certificates']} of "
                 f"{census['totals']['certificates']} certificates are UNATTRIBUTED** -- no name "
                 f"and no family lineage reaches a producer. That is a lineage-stamping gap, not "
                 f"a zero for any organ.")
    L.append("")
    cov = census.get("measurement_coverage") or {}
    if cov:
        L.append("")
        L.append("## Per-producer measurement coverage -- THE RATCHET")
        L.append("")
        L.append(f"_Denominator is **{cov.get('n_producers')} producers** and travels with every "
                 "ratio: coverage improved by dropping producers is a regression wearing an "
                 "improvement's number (L1.50)._")
        L.append("")
        L.append("| column | measured | of | coverage | non-zero |")
        L.append("|---|--:|--:|--:|--:|")
        for col, v in (cov.get("columns") or {}).items():
            L.append(f"| `{col}` | {v['measured']} | {v['of']} | {v['coverage']} | "
                     f"{v['nonzero']} |")
        rg = cov.get("region") or {}
        L.append("")
        L.append(f"**Region:** {rg.get('regional')} regional + {rg.get('not_regional')} "
                 f"NOT_REGIONAL = {rg.get('coverage')} of {rg.get('of')}; "
                 f"{rg.get('unattributed')} still `unattributed`. Routes: "
                 + ", ".join(f"{k} {v}" for k, v in (rg.get("routes") or {}).items()))
    L.append("")
    L.append("## By region")
    L.append("")
    L.append("| region | prod | sources | docs | raw cells | uniq | submitted | judged | surv "
             "| certs | cpu h | cells/src | surv/src | certs/h |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for name in ROLLUP_BUCKETS:
        b = census["by_region"].get(name)
        if not b:
            continue
        L.append(f"| {name} | {b['producers']} | {b['sources_visited']} | "
                 f"{b['documents_retained']} | {b['raw_cells']} | {b['unique_cells']} | "
                 f"{b['gauntlet_submitted']} | {b.get('cells_judged', 0)} | "
                 f"{b['cheap_survivors']} | {b['certificates']} | "
                 f"{b['compute_hours']:.2f} | {b['cells_per_source']} | "
                 f"{b['survivors_per_source']} | {b['certificates_per_compute_hour']} |")
    L.append("")
    L.append("## Top producers by certificates")
    L.append("")
    L.append("| producer | certs | unique cells | cpu h | region |")
    L.append("|---|--:|--:|--:|---|")
    for r in census["top_by_certificates"][:10]:
        L.append(f"| `{r['producer']}` | {r['certificates']} | {r['unique_cells']} | "
                 f"{r['compute_hours']} | {r['region']} |")
    L.append("")
    L.append("## Compute spent, no unique cell -- THE LIST TO ACT ON")
    L.append("")
    L.append("| producer | cpu h | ledger h | registry h | sources | clock | region |")
    L.append("|---|--:|--:|--:|--:|---|---|")
    for r in census["zero_cell_compute"][:25]:
        L.append(f"| `{r['producer']}` | {r['compute_hours']} | {r['compute_hours_ledger']} | "
                 f"{r['compute_hours_registry']} | {r['sources_visited']} | "
                 f"{r['clock'] or '-'} | {r['region']} |")
    if not census["zero_cell_compute"]:
        L.append("| _none: every producer with measured compute produced at least one cell_ "
                 "| | | | | | |")
    L.append("")
    L.append("## Where each number comes from")
    L.append("")
    for k, v in census["sources"].items():
        L.append(f"- `{k}` <- {v}")
    L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------ cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass and exit (the leg's mode)")
    ap.add_argument("--budget-s", type=float, default=300.0,
                    help="wall-clock budget; the census is read-only and normally finishes in "
                         "seconds, so this bounds a pathological registry, never the work")
    ap.add_argument("--window-days", type=float, default=COMPUTE_WINDOW_DAYS)
    ap.add_argument("--json", action="store_true", help="print the census to stdout")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    census = build(window_days=args.window_days)
    census["budget_s"] = args.budget_s
    census["over_budget"] = bool(time.time() - t0 > args.budget_s)
    if census["over_budget"]:
        census["over_budget_why"] = (
            f"the pass took {time.time() - t0:.1f}s against a {args.budget_s:g}s budget: the "
            "numbers stand, the schedule does not")

    if not args.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(census, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text(render(census), encoding="utf-8")
        try:
            sys.path.insert(0, str(ROOT))
            from libs.ops.events import emit
            emit("productivity_census",
                 n_producers=census["n_producers"],
                 n_productive=census["n_productive"],
                 n_zero_cell_with_compute=census["n_zero_cell_with_compute"],
                 worst_column_coverage=census["measurement_coverage"][
                     "worst_column_coverage"],
                 region_coverage=census["measurement_coverage"]["region"]["coverage"],
                 dedup_collapse=census["dedup"]["collapse"])
        except Exception:
            pass  # the events log is a convenience; the artifact is the record

    if args.json:
        print(json.dumps(census, indent=2, default=str))
    else:
        cov = census["measurement_coverage"]
        print(f"productivity_census: {census['n_producers']} producers, "
              f"{census['n_productive']} productive, "
              f"{census['n_zero_cell_with_compute']} burning compute for no cell, "
              f"dedup collapse {census['dedup']['collapse']}x -> {OUT}")
        print("  column coverage: " + "  ".join(
            f"{c}={v['coverage']}" for c, v in cov["columns"].items()))
        print(f"  region coverage: {cov['region']['coverage']} "
              f"({cov['region']['regional']} regional + {cov['region']['not_regional']} "
              f"NOT_REGIONAL, {cov['region']['unattributed']} unattributed of "
              f"{cov['region']['of']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
