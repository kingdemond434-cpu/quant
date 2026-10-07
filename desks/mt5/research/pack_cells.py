"""EVERY DATA PACK PRODUCES CELLS, or names the reason it cannot.

THE PRINCIPAL, 2026-09-23: *"every data pack must produce cells -- this is the whole point of the
global build and it currently produces almost none."*

MEASURED ON THE BOX THE MORNING THIS WAS WRITTEN. Of 85 registered sources: 39 never collected,
40 stopped at BYTES, 1 ingested, 5 credited with a cell, 0 with a judged cell. The break was never
coverage -- it was between BYTES and REPRESENTATION, and then between representation and the one
gauntlet. `source_drain` prices and repairs the first half and publishes the chain; it enqueues a
DISCOVERY for a represented source and stops there, eight per pass, because a discovery is not a
cell and the compiler decides its own clock. Nothing turned a stamped series into CELLS.

WHAT THIS ORGAN DOES, and every clause is a number it publishes per pack:

  1. READS THE CHAIN IT DOES NOT OWN. `source_drain.chain_state()` is the per-source stage; this
     organ never re-derives it and never edits that module. A pack the chain calls REPRESENTED is
     eligible; every other pack is published with the stage it stopped at, which IS its reason.

  2. TURNS A STAMPED SERIES INTO SIGNALS. The point-in-time envelope written by
     `asia_parser`/`libs.data.pit_stamp` is stripped off, and every remaining column that carries
     numbers is a candidate conditioner. A pack whose frame carries no numeric column is not a
     silent zero: `reason` says "the series carries no numeric column", which is a fact about the
     page, not about this organ.

  3. EMITS THROUGH THE ONE DOOR. `libs.moat.registry.record_discovery` for the pack (once, keyed
     by the pack) and `enqueue_candidate` for each (signal x transform x target symbol x chart)
     cell, carrying `source_id` so the credit is attributable and `discovery_id` so the lineage
     is. No store beside the registry, no second gauntlet, no judging here.

  4. REACHES EVERY PACK. The emission order is a ROUND ROBIN over eligible packs from a saved
     cursor, so a pack at the end of the alphabet is not starved behind a pack with four hundred
     columns -- the same anti-starvation rule `source_drain.drain` applies to fetching.

  5. PUBLISHES CELLS_EMITTED AND CELLS_JUDGED PER PACK. Emitted is counted in the registry, not
     in this organ's own bookkeeping. Judged is counted in `trials_ledger`, which is the one
     gauntlet's own record of having tested a candidate -- a pack at zero judged with cells
     emitted is waiting on the gauntlet's clock, and the report says exactly that.

NOTHING HERE IS A CAP. The per-pass budget is a wall clock, not a quota: a pack not reached this
pass leads the next one, nothing is refused, nothing is throttled, and no pack is ever removed
from the eligible set. It never judges, never sizes and never vetoes.

    python desks/mt5/research/pack_cells.py --once --budget-s 240
    python desks/mt5/research/pack_cells.py --once --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "asia_sources.json"
SERIES = DESK / "data" / "lake" / "series"
CURSOR = DESK / "data" / "pack_cells_cursor.json"
OUT = DESK / "reports" / "PACK_CELLS.json"

#: The point-in-time envelope. These columns are the stamp, never a signal.
STAMP_COLUMNS: frozenset[str] = frozenset({
    "event_time", "published_time", "available_time", "revision_time", "retrieval_time",
    "ingested_time", "source_id", "vintage_id"})

#: How a conditioner reads a column. Three shapes, all price-free and all computable from the
#: series alone, so the gauntlet is judging the PACK's information and not a modelling choice.
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")

#: The charts a macro conditioner is asked on. H4 and D1 because a published statistic moves a
#: market for longer than an hour; H1 because that is the chart the desk holds most bars for.
#: Never a filter -- this is the ORDER the cells are minted in.
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")

#: A column with fewer distinct values than this is a label, a flag or a key, not a series.
MIN_DISTINCT = 4
#: Signals taken per pack per pass. The cursor carries the offset, so the next pass takes the
#: next ones and every column of every pack is reached. Not a cap on what a pack may emit.
SIGNALS_PER_PACK_PER_PASS = 6


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def packs() -> list[dict[str, Any]]:
    """The registered data packs. One registry row is one pack; transports are not packs."""
    reg = _read(REGISTRY, {}) or {}
    rows = reg.get("sources") if isinstance(reg, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id")
            and str(r.get("role") or "mechanism") != "transport"]


def chain() -> dict[str, dict[str, Any]]:
    """The chain state `source_drain` publishes. Empty when that organ has not run here, which
    is UNMEASURED and reported as such -- never silently treated as "no pack is eligible"."""
    try:
        from research.source_drain import chain_state
        return chain_state()
    except Exception:
        return {}


def series_path(pack_id: str) -> Path | None:
    """The pack's canonical frame, written under its bare id by `asia_parser._canonicalise`."""
    for suffix in (".parquet", ".csv"):
        p = SERIES / f"{pack_id}{suffix}"
        if p.exists():
            return p
    return None


def signals_of(path: Path) -> tuple[list[str], int, str]:
    """(numeric signal columns, row count, why there are none).

    The stamp columns are stripped first; a column that is constant, or carries fewer than
    MIN_DISTINCT distinct values, is a key or a flag and not a conditioner.
    """
    try:
        import pandas as pd
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:
        return [], 0, f"series unreadable: {type(exc).__name__}: {str(exc)[:60]}"
    if df.empty:
        return [], 0, "the series frame is empty"
    import pandas as pd
    cols: list[str] = []
    for name in df.columns:
        if str(name) in STAMP_COLUMNS:
            continue
        col = pd.to_numeric(df[name], errors="coerce")
        if col.notna().mean() < 0.6:
            continue
        if int(col.nunique(dropna=True)) < MIN_DISTINCT:
            continue
        cols.append(str(name))
    if not cols:
        return [], len(df), ("the series carries no numeric column with "
                            f"{MIN_DISTINCT}+ distinct values: every column is a label, a key "
                            "or a constant")
    return cols, len(df), ""


def targets_of(pack: dict[str, Any]) -> list[str]:
    """The MT5 instruments this pack claims to condition, as the registry declares them."""
    raw = pack.get("targets") or []
    return [str(t) for t in raw if str(t).strip()][:8]


#: A CELL IS JUDGED WHEN A JUDGE RECORDED A VERDICT AGAINST IT, and the desk has three registers
#: that can carry one: the gauntlet's own `trials_ledger.candidate_id`, and the candidate's own
#: `judged_at` / `terminal_gate`. This union is the honest measure -- counting only the first one
#: reported zero for a structural reason (see `judged_registers`) and looked like a slow clock.
JUDGED_SQL = (
    "SELECT c.source_id, COUNT(DISTINCT c.id) FROM research_candidates c "
    "LEFT JOIN trials_ledger t ON t.candidate_id = c.id "
    "WHERE c.source_id IS NOT NULL AND c.source_id != '' AND ("
    "t.candidate_id IS NOT NULL OR c.judged_at IS NOT NULL OR "
    "(c.terminal_gate IS NOT NULL AND c.terminal_gate != '')) GROUP BY c.source_id")


#: WHY A REGIONAL CELL IS NEVER JUDGED. Traced end to end 2026-09-23 on the trading box; every
#: clause is a file and a line, and NOT ONE of them is this organ's to change. Published here so
#: the next session inherits a work order with an owner instead of a mystery.
WHY_REGIONAL_CELLS_ARE_NOT_JUDGED: dict[str, str] = {
    "0_the_judge_does_not_read_this_registry": (
        "desks/mt5/scripts/external_gauntlet.py:2602 main() reads ONE file, "
        "data/hypotheses/external_survivors.json. It never opens data/alpha_registry.sqlite. The "
        "registry table is the record written AFTER a verdict, never the judge's work queue, so "
        "minting a cell into it does not put that cell in front of a judge."),
    "1_the_docket_is_built_from_json_not_from_the_registry": (
        "desks/mt5/research/merge_hypotheses.py (leg `merge_docket`) is the only writer of "
        "external_survivors.json and it reads seven JSON files under data/intelligence/ and "
        "data/hypotheses/. The ONLY door out of sqlite into those files is "
        "moat_candidate_compiler.claim_and_donate -> proposer_common.donate, leased by "
        "libs/moat/registry.claim_candidates at CLAIM_PER_DEPARTMENT=12 x 5 departments = 60 rows "
        "an hour against 323,542 candidates. pack_cells, discovery_compiler and the miner:* "
        "producers all call enqueue_candidate DIRECTLY and donate nothing."),
    "2_the_families_are_not_implemented": (
        "miner_candidate_compiler._registered_family requires family_<name> in mt5desk/families.py "
        "or membership of families_orthogonal.ORTHOGONAL_FAMILIES. Neither "
        "`regional_information` (this organ's world lane) nor `exogenous_conditioner` (its pack "
        "lane) exists in either, so a donated regional row exits compile_row as "
        "NEEDS_EXACT_RULE_EXTRACTION into miner_deepening_queue.json and never reaches a docket."),
    "3_a_verdict_can_only_land_on_the_oldest_row_of_its_identity": (
        "libs/moat/registry.candidate_identity_index builds symbol|family|session with "
        "setdefault() over ORDER BY seq, so the LOWEST-seq row permanently owns each identity and "
        "every later candidate with the same triple is structurally unreachable by a verdict. "
        "Measured: 4,539 distinct identities against 323,542 candidates, and ~40% of gauntlet "
        "verdicts resolve to `cell_name_unjoined` and update zero rows. That ceiling -- not a "
        "slow clock and not this organ's output -- is why 1,228 candidates carry judged_at."),
    "4_this_organ_runs_after_the_judge": (
        "in desks/mt5/research/hourly_cycle.py the legs run in source order: merge_docket then "
        "external_gauntlet, and `pack_cells` several hundred lines later. A cell minted this hour "
        "cannot be in this hour's docket even in principle."),
    "owners": (
        "hourly_cycle leg order; mt5desk/families*.py; the donation path "
        "(moat_candidate_compiler / proposer_common); libs/moat/registry."
        "candidate_identity_index. pack_cells owns NONE of them: it mints, it measures, and it "
        "publishes this. desks/mt5/scripts/external_gauntlet.py is SEALED."),
}


def judged_registers() -> dict[str, Any]:
    """WHY THE END OF THE CHAIN IS OPEN, measured in the three registers that could close it.

    THE EARLIER READING HERE IS SUPERSEDED AND IS LEFT DESCRIBED SO THE CHANGE IS VISIBLE. It said
    `trials_ledger` held 140 rows with not one candidate_id, and concluded that "the one write that
    closes it" was passing a candidate_id. That write LANDED -- measured 2026-09-23 on the trading
    box, trials_ledger holds 25,824 rows, 25,592 of them carrying a candidate_id and 7,819 joining
    a registry candidate, and 1,228 candidates now carry judged_at and a terminal_gate. So the
    register is no longer the blocker and this function no longer says it is.

    WHAT IS STILL OPEN IS ROUTING, NOT RECORDING, and it is a different defect with different
    owners: see `WHY_REGIONAL_CELLS_ARE_NOT_JUDGED`. A regional cell never enters the judge's
    docket at all, so no register can record a verdict that was never reached. This organ mints and
    measures; it owns none of the four clauses and edits none of those files.
    """
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unavailable: {type(exc).__name__}: {exc}"}
    try:
        def one(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0])
            except Exception:
                return -1
        n_trials = one("SELECT COUNT(*) FROM trials_ledger")
        n_with_cand = one("SELECT COUNT(*) FROM trials_ledger WHERE candidate_id IS NOT NULL "
                          "AND candidate_id != ''")
        n_joined = one("SELECT COUNT(*) FROM trials_ledger t JOIN research_candidates c "
                       "ON c.id = t.candidate_id")
        n_judged_at = one("SELECT COUNT(*) FROM research_candidates WHERE judged_at IS NOT NULL")
        n_terminal = one("SELECT COUNT(*) FROM research_candidates WHERE terminal_gate IS NOT "
                         "NULL AND terminal_gate != ''")
        n_cands = one("SELECT COUNT(*) FROM research_candidates")
        total = max(n_with_cand, 0) + max(n_judged_at, 0) + max(n_terminal, 0)
        # WHERE THE VERDICTS ACTUALLY ARE. The gauntlet does not write the registry: it appends to
        # `data/hypotheses/gate_verdict_ledger.jsonl`, and `libs.moat.registry.sync_from_desk`
        # (hourly leg `registry_sync`) is the organ that pours those rows in as trials WITH a
        # candidate_id and marks the candidate judged. Both halves are measured here because the
        # difference between "no verdict exists" and "the verdict never crossed" is the whole job.
        ledger = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
        try:
            with ledger.open(encoding="utf-8", errors="ignore") as fh:
                n_verdicts = sum(1 for _ in fh)
        except OSError:
            n_verdicts = -1
        cursor_row = None
        try:
            cursor_row = conn.execute("SELECT value FROM sync_cursor WHERE key = 'gate_verdicts'"
                                      ).fetchone()
        except Exception:
            cursor_row = None
        return {
            "verdicts_on_disk": n_verdicts,
            "verdict_ledger": str(ledger),
            "sync_cursor_gate_verdicts": (str(cursor_row[0]) if cursor_row else None),
            "the_verdicts_never_crossed": (
                f"{n_verdicts} gauntlet verdicts sit in {ledger.name} and the registry's "
                "sync_cursor holds NO 'gate_verdicts' key, so libs.moat.registry.sync_from_desk "
                "(hourly leg `registry_sync`, desks/mt5/research/registry_sync.py:42) has not "
                "poured a single one in since the registry was restored from backup on "
                "2026-09-17. That is the first half of the job and it is a RUN, not a build. The "
                "second half is measured and still open: the sampled verdict rows carry "
                "graph_id=None, so sync_from_desk falls back to the cell NAME as the candidate "
                "edge, which joins to no research_candidates.id (those are cand_<hex>) -- the "
                "verdict would land as a trial with a candidate_id that matches nothing. Both "
                "halves belong to registry_sync/sync_from_desk, neither to this organ."
                if n_verdicts > 0 and not cursor_row else ""),
            "status": "OPEN" if total <= 0 else "OK",
            "trials_ledger_rows": n_trials,
            "trials_ledger_rows_carrying_a_candidate_id": n_with_cand,
            "trials_ledger_rows_joining_a_registry_candidate": n_joined,
            "candidates": n_cands,
            "candidates_with_judged_at": n_judged_at,
            "candidates_with_a_terminal_gate": n_terminal,
            "why": ("no judge writes a verdict back against a registry candidate id: "
                    f"{n_trials} trial rows carry {n_with_cand} candidate ids, and {n_cands} "
                    f"candidates carry {n_judged_at} judged_at and {n_terminal} terminal_gate "
                    "values. cells_judged is therefore structurally zero for every source and "
                    "every region, and minting more cells cannot move it"
                    if total <= 0 else "verdicts are recorded against candidate ids"),
            "the_one_write_that_closes_it": (
                "SUPERSEDED AND LANDED: this said `pass the registry candidate_id when appending "
                f"to trials_ledger`, and that write now happens -- {n_with_cand} of {n_trials} "
                f"trial rows carry one and {n_joined} join a registry candidate. Recording is no "
                "longer the blocker."
                if n_with_cand > 0 else
                "pass the registry candidate_id when appending to trials_ledger (it is already "
                "an identity key in libs/research/trial_ledger.py:283), or set "
                "research_candidates.judged_at + terminal_gate on the judged row."),
            "what_is_still_open_is_routing_not_recording": WHY_REGIONAL_CELLS_ARE_NOT_JUDGED,
        }
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def judged_by_stamped_region() -> dict[str, Any]:
    """JUDGED CELLS PER REGION, keyed on the CELL's own attribution stamp, not on its ground.

    WHY THE OTHER KEY READS ZERO FOR EVERY REGION AND ALWAYS WILL. `judged_by_region` below counts
    a region's judged cells through its GROUNDS: `sources.source_id -> research_candidates.
    source_id -> a verdict`. Measured 2026-09-23 on the trading box, 1,210 of the 1,228 judged
    candidates were produced by `external`, which carries NO source_id at all -- so no ground could
    be credited with them and all fourteen regions read zero BY CONSTRUCTION, whatever the judge
    did. The cells were judged; the join used the wrong key.

    A cell's region is stamped on the cell (`libs/research/attribution.py`), so this counts what
    was actually judged by the region that actually produced it. Both numbers are published: the
    per-ground one still answers "which GROUND has earned a verdict", which is a different and
    also useful question, and neither is allowed to stand in for the other.
    """
    try:
        from libs.moat.registry import connect
        from libs.research import attribution as attr
        conn = connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unavailable: {type(exc).__name__}: {exc}"}
    try:
        rows = conn.execute(
            "SELECT COALESCE(NULLIF(c.region,''),'UNMEASURED'), "
            "COUNT(DISTINCT COALESCE(NULLIF(c.grid_cell,''), c.content_hash)) "
            "FROM research_candidates c LEFT JOIN trials_ledger t ON t.candidate_id = c.id "
            "WHERE c.judged_at IS NOT NULL OR (c.terminal_gate IS NOT NULL AND "
            "c.terminal_gate != '') OR t.candidate_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"query failed: {type(exc).__name__}: {exc}"}
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    by = {str(r[0]): int(r[1] or 0) for r in rows}
    return {"status": "OK", "by_region": by, "spread": attr.region_spread(by),
            "basis": ("distinct grid_cell else content_hash over candidates carrying judged_at, a "
                      "terminal_gate, or a trials_ledger row -- keyed on the CELL's own region"),
            "regions_with_a_judged_cell": sorted(r for r in attr.REGIONS if by.get(r, 0) > 0),
            "regions_with_no_judged_cell": sorted(r for r in attr.REGIONS if by.get(r, 0) <= 0)}


def _registry_counts() -> tuple[dict[str, dict[str, int]], str]:
    """Per source id: cells the registry holds, and cells the ONE gauntlet has judged.

    Emitted is counted in `research_candidates`, judged in `trials_ledger` -- the gauntlet's own
    append-only record that it tested a candidate. Neither number is this organ's bookkeeping.
    """
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return {}, f"registry unavailable: {type(exc).__name__}: {exc}"
    out: dict[str, dict[str, int]] = {}
    try:
        for sid, n in conn.execute("SELECT source_id, COUNT(*) FROM research_candidates "
                                   "WHERE source_id IS NOT NULL AND source_id != '' "
                                   "GROUP BY source_id"):
            out.setdefault(str(sid), {"emitted": 0, "judged": 0})["emitted"] = int(n)
        for sid, n in conn.execute(JUDGED_SQL):
            out.setdefault(str(sid), {"emitted": 0, "judged": 0})["judged"] = int(n)
    except Exception as exc:
        return out, f"registry query failed: {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    return out, ""


# ============================================================ the world lane (regional grounds)
#: The world crawler's grounds are a SECOND pack population and a much larger zero. Measured
#: 2026-09-23: `sources` holds 2,214 registered grounds, 621 crawled, and 121 of them hold 963
#: verbatim claims -- documents already fetched, on disk, costing nothing more to read. Every one
#: of those 121 has ZERO cells, and not one claim carries a mechanism_id. The ground is there;
#: nothing walked it to the door.
_PACK_CACHE: dict[str, tuple[tuple[str, ...], str]] = {}
#: Claims read per source per pass. A ground with three hundred documents is not more important
#: than one with three; the cursor advances so the rest are read next pass.
CLAIMS_PER_SOURCE = 4

#: HOW THE ONE WALL CLOCK IS SHARED, and it is a share, never a cap. Both lanes carry a cursor, so
#: a lane stopped by the clock leads the next pass and nothing it would have minted is refused.
#: Measured 2026-09-23 on the trading box: the pack lane and the world lane's own mapping ladder
#: consumed the entire 240s budget and the world lane -- the ONLY lane that mints a cell carrying a
#: region -- reached 0 grounds with 425 in its backlog. A first-come clock is not neutral between
#: two lanes; it silently gives everything to whichever runs first, and the regional lane ran
#: second. This reserves the rest of the hour for it rather than reducing anything.
PACK_LANE_SHARE = 0.5


def country_pack(code: str) -> tuple[tuple[str, ...], str]:
    """(the country's MT5-executable instruments, its command region) from its own pack module.

    The 75 country packs under `research/countries/` already declare `EXECUTABLE_INSTRUMENTS` and
    `REGION_COMMAND`; nothing here re-types either. A country with no pack returns an empty tuple
    and "UNMAPPED", which is the honest reason its grounds cannot yet name an instrument -- never
    a guessed currency pair.
    """
    key = (code or "").strip().lower()
    if not key:
        return (), "UNMAPPED"
    if key in _PACK_CACHE:
        return _PACK_CACHE[key]
    try:
        mod = __import__(f"countries.{key}.pack", fromlist=["pack"])
        instruments = tuple(str(s) for s in (getattr(mod, "EXECUTABLE_INSTRUMENTS", ()) or ()))
        region = str(getattr(mod, "REGION_COMMAND", "") or "UNMAPPED").strip().upper()
    except Exception:
        instruments, region = (), "UNMAPPED"
    _PACK_CACHE[key] = (instruments, region)
    return instruments, region


# ---------------------------------------------------------------- the mapping ladder
# MEASURED 2026-09-23, AND IT IS NOT WHAT THE BACKLOG SAID. The 29 grounds this organ could not
# convert are not countries missing a pack: every one of them carries country = NULL. They are
# LANES -- `github`, `mql5_signals`, `literature`, `asia:cfets_fixing`, `deep_forest` -- whose
# documents come from many hosts, and whose jurisdiction is a property of the DOCUMENT, not of
# the registry row. Meanwhile every country that does name itself (cz, az, ca, au, kz, ar, ge,
# cl, br, idn, ea, bd, ind, ch, lk, co) already has a pack, so "write 29 packs" would have been
# 29 files nobody needed.
#
# So the resolution is a LADDER, and every rung is derived from something the desk already
# declares. Nothing below is a typed table:
#
#   1. country_pack                     the registry's own country column -> the pack's own
#                                       EXECUTABLE_INSTRUMENTS (the rung that already existed)
#   2. jurisdiction_of_documents        the ccTLD of the hosts the ground's OWN held documents
#                                       were fetched from, against an index inverted out of the
#                                       packs' own JURISDICTIONS tuples and directory names
#   3. instruments_named_in_documents   the MT5 symbols named verbatim in the held text, against
#                                       the desk's own universe registry, routed through
#                                       universe_policy so a single-name equity never becomes a
#                                       statistical hypothesis (LAWS: two lanes)
#   4. UNMAPPED                         with the hosts it saw and the rung that failed, which is
#                                       a named owned reason and not a silent zero
#
# A rung is never a filter: rung 2 cannot narrow rung 1, and a ground that clears rung 1 never
# reaches rung 2. The ladder only ADDS grounds that had nothing.
_JURIS_INDEX: dict[str, str] | None = None
_UNIVERSE: frozenset[str] | None = None
#: Documents sampled to resolve a ground's jurisdiction. The dominant host wins, so one stray
#: link cannot move a ground; the sample is bounded because a ground with 300 documents is
#: resolved by the same hosts as a ground with 12.
RESOLVE_SAMPLE = 24


def jurisdiction_index() -> dict[str, str]:
    """Every jurisdiction the desk's packs cover -> the pack that covers it. DERIVED, never typed.

    A two-letter pack directory IS its ISO-3166 alpha-2 code; a regional pack declares the codes
    it covers in its own `JURISDICTIONS` tuple. A code absent from this index is covered by no
    pack on the desk, which is the only honest ground for writing a new one.
    """
    global _JURIS_INDEX
    if _JURIS_INDEX is not None:
        return _JURIS_INDEX
    idx: dict[str, str] = {}
    base = Path(__file__).resolve().parent / "countries"
    try:
        dirs = sorted(p for p in base.iterdir() if (p / "pack.py").exists())
    except OSError:
        dirs = []
    for d in dirs:
        if len(d.name) == 2:
            idx.setdefault(d.name.lower(), d.name)
        try:
            mod = __import__(f"countries.{d.name}.pack", fromlist=["pack"])
        except Exception:
            continue
        for j in (getattr(mod, "JURISDICTIONS", ()) or ()):
            code = str(j).strip().lower()
            if code:
                idx.setdefault(code, d.name)
    _JURIS_INDEX = idx
    return idx


def universe_symbols() -> frozenset[str]:
    """The MT5 symbols the broker actually quotes, from the desk's own universe registry."""
    global _UNIVERSE
    if _UNIVERSE is not None:
        return _UNIVERSE
    doc = _read(DESK / "data" / "universe" / "universe.json", {}) or {}
    names = list(doc) if isinstance(doc, dict) else []
    _UNIVERSE = frozenset(str(n) for n in names if str(n).strip())
    return _UNIVERSE


def _host_of(url: str) -> str:
    raw = str(url or "").strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    return raw.split("/", 1)[0].split("@")[-1].split(":")[0].strip().lower()


def _cctld(host: str) -> str:
    """The host's country code, when its last label IS one. `boj.or.jp` -> `jp`; `mql5.com` -> ''.

    A generic top-level domain has no jurisdiction and returns "", which is a measurement about
    the host and the reason such a ground falls through to rung 3.
    """
    label = host.rsplit(".", 1)[-1] if "." in host else ""
    return label if len(label) == 2 and label.isalpha() else ""


def held_documents(source_id: str, limit: int = RESOLVE_SAMPLE) -> list[dict[str, str]]:
    """(url, text) for the documents this ground already holds, from the claims' own provenance."""
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception:
        return []
    try:
        out: list[dict[str, str]] = []
        for r in conn.execute("SELECT text, provenance_json FROM claims WHERE source_id = ? "
                              "ORDER BY created_at LIMIT ?", (source_id, int(limit))):
            prov = _read_json_str(str(r["provenance_json"] or ""))
            out.append({"url": str(prov.get("url") or ""), "text": str(r["text"] or "")})
        return out
    except Exception:
        return []
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def _read_json_str(raw: str) -> dict[str, Any]:
    try:
        doc = json.loads(raw or "{}")
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def named_instruments(texts: list[str]) -> list[str]:
    """MT5 symbols named verbatim in the held documents, in the order the universe declares them.

    Routed through `universe_policy.may_hypothesise`, which is the mandate's own asset-class
    router: a single-name equity is traded on its disclosures and never minted as a statistical
    hypothesis, so it is set aside here by the same rule the backtest router uses.
    """
    blob = " ".join(texts)
    if not blob:
        return []
    upper = blob.upper()
    try:
        from research.universe_policy import may_hypothesise
    except Exception:   # an absent router never filters
        def may_hypothesise(symbol: str, family: object = None) -> bool:
            return True
    hits: list[str] = []
    for sym in sorted(universe_symbols()):
        if len(sym) < 5 or not sym.isalnum():
            continue                                   # a 3-letter token matches too much prose
        if sym.upper() in upper and may_hypothesise(sym):
            hits.append(sym)
    return hits


def resolve_ground(row: dict[str, Any]) -> dict[str, Any]:
    """The ladder, applied to ONE ground: (targets, region, mapped_by, reason, hosts).

    Called only for a ground that rung 1 left with no instrument AND that holds documents, so it
    costs one bounded claims read per unmapped ground per pass and nothing at all for the rest.
    """
    sid = str(row.get("id") or "")
    docs = held_documents(sid)
    hosts = [_host_of(d["url"]) for d in docs if d.get("url")]
    reg_host = _host_of(str(row.get("url") or ""))
    if reg_host:
        hosts.append(reg_host)
    codes = [c for c in (_cctld(h) for h in hosts) if c]
    idx = jurisdiction_index()
    ranked = sorted({c: codes.count(c) for c in codes}.items(), key=lambda kv: (-kv[1], kv[0]))
    for code, _n in ranked:
        pack = idx.get(code)
        if not pack:
            continue
        instruments, region = country_pack(pack)
        if instruments:
            return {"targets": list(instruments[:8]), "region": region,
                    "mapped_by": "jurisdiction_of_documents",
                    "reason": "", "hosts": sorted(set(hosts))[:6], "code": code, "pack": pack}
    named = named_instruments([d["text"] for d in docs])
    if named:
        return {"targets": named[:8], "region": "GLOBAL",
                "mapped_by": "instruments_named_in_documents", "reason": "",
                "hosts": sorted(set(hosts))[:6], "code": "", "pack": ""}
    unknown = sorted({c for c in codes if c and c not in idx})
    return {"targets": [], "region": "UNMAPPED", "mapped_by": "none",
            "hosts": sorted(set(hosts))[:6], "code": "", "pack": "",
            # THE NEXT JOB, WITH AN OWNER, so the backlog is a work order and not a mystery.
            "next_job": (
                f"WRITE A PACK: research/countries/{unknown[0]}/pack.py with "
                "EXECUTABLE_INSTRUMENTS and REGION_COMMAND; this ground converts on the next pass"
                if unknown else
                "CRAWL DEPTH (owner: the crawler that fetched it -- world_crawler / "
                "deep_forest_miner): the documents held are landing or navigation pages that "
                "name no MT5 symbol. Fetching the data page this ground actually publishes "
                "closes it; no pack and no code here can"),
            "reason": (
                "no rung resolves it: its documents come from "
                + (", ".join(sorted(set(hosts))[:4]) or "no recorded host")
                + (f"; the country code(s) {', '.join(unknown)} are covered by no pack under "
                   "research/countries/ -- writing one closes it" if unknown else
                   "; those hosts carry a generic top-level domain, and no MT5 symbol is named "
                   "verbatim in the documents held, so the ground names no instrument yet"))}


def world_rows(resolved: dict[str, dict[str, Any]] | None = None
               ) -> tuple[list[dict[str, Any]], str]:
    """Every registered world ground with the documents it already holds and the cells it owes.

    `n_documents` is the crawler's own claim count for that ground -- documents ALREADY FETCHED,
    which is the ranking the next pass (or the next session) should start from.
    """
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return [], f"registry unavailable: {type(exc).__name__}: {exc}"
    try:
        docs = {str(sid): int(n) for sid, n in
                conn.execute("SELECT source_id, COUNT(*) FROM claims GROUP BY source_id")}
        cells = {str(sid): int(n) for sid, n in
                 conn.execute("SELECT source_id, COUNT(*) FROM research_candidates "
                              "WHERE source_id IS NOT NULL AND source_id != '' "
                              "GROUP BY source_id")}
        disc = {str(sid): int(n) for sid, n in
                conn.execute("SELECT source_id, COUNT(*) FROM discoveries "
                             "WHERE source_id IS NOT NULL AND source_id != '' "
                             "GROUP BY source_id")}
        judged = {str(sid): int(n) for sid, n in conn.execute(JUDGED_SQL)}
        out: list[dict[str, Any]] = []
        for r in conn.execute("SELECT source_id, country, kind, url, status, last_crawled "
                              "FROM sources"):
            sid = str(r["source_id"])
            instruments, region = country_pack(str(r["country"] or ""))
            out.append({"id": sid, "lane": "world", "country": str(r["country"] or ""),
                        "region": region, "kind": str(r["kind"] or ""),
                        "url": str(r["url"] or ""), "status": str(r["status"] or ""),
                        "crawled": bool(str(r["last_crawled"] or "")),
                        "targets": list(instruments[:8]),
                        "n_documents": docs.get(sid, 0),
                        "cells_emitted": cells.get(sid, 0),
                        "discoveries": disc.get(sid, 0),
                        "cells_judged": judged.get(sid, 0)})
        rows_out = out
    except Exception as exc:
        return [], f"registry query failed: {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    # THE LADDER, and only where rung 1 left nothing. A ground that already names instruments is
    # never re-resolved, and a ground holding no document costs nothing here: the whole ladder is
    # one bounded claims read per UNMAPPED ground that has something to convert.
    # THE LADDER IS PAID FOR ONCE PER PASS, NOT TWICE. `build()` calls this function a second time
    # after emission so its numbers are POST-pass, and each `resolve_ground` opens its own registry
    # connection for one bounded claims read: 425 unmapped grounds holding documents cost 850 of
    # them per pass. Measured 2026-09-23 on the trading box that was enough to consume the whole
    # 240s budget inside the diagnostics, so the world lane reached ZERO grounds with a backlog of
    # 425 -- the regional lane starved by its own measurement. The caller now hands back what the
    # first pass resolved; nothing is skipped and no ground is dropped.
    cache = resolved if isinstance(resolved, dict) else None
    for w in rows_out:
        w["mapped_by"] = "country_pack" if w["targets"] else "none"
        if w["targets"] or w["n_documents"] <= 0:
            continue
        res = (cache or {}).get(w["id"]) or resolve_ground(w)
        if cache is not None:
            cache.setdefault(w["id"], res)
        w["mapped_by"] = res["mapped_by"]
        w["hosts"] = res["hosts"]
        if res.get("next_job"):
            w["next_job"] = res["next_job"]
        if res["targets"]:
            w["targets"] = res["targets"]
            w["region"] = res["region"]
        if res["reason"]:
            w["reason"] = res["reason"]
    return rows_out, ""


def _claims_for(source_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception:
        return []
    try:
        return [{"claim_id": str(r["claim_id"]), "text": str(r["text"] or ""),
                 "knowable_at": str(r["knowable_at"] or ""),
                 "media_type": str(r["media_type"] or "")}
                for r in conn.execute(
                    "SELECT claim_id, text, knowable_at, media_type FROM claims "
                    "WHERE source_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
                    (source_id, int(limit), int(offset)))]
    except Exception:
        return []
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def emit_world(row: dict[str, Any], *, dry_run: bool = False,
               offset: int = 0) -> dict[str, Any]:
    """A ground's already-held documents, walked to the one door.

    One DISCOVERY per claim, keyed by the ground and carrying the country pack's executable
    instruments as its assets, so `miner_candidate_compiler` mints the cells on its own clock --
    the desk's documented path from a verbatim claim to a testable rule. Plus one cell per
    (instrument x chart) so the ground has a registry-visible presence even before the compiler
    reaches it. Nothing is judged here and no claim is filtered.
    """
    sid = str(row["id"])
    claims = _claims_for(sid, CLAIMS_PER_SOURCE, offset)
    if not claims:
        return {"id": sid, "emitted": 0, "created": 0, "discoveries": 0,
                "reason": ("no document is held for this ground: the crawler has fetched "
                           "nothing from it yet" if not row["n_documents"]
                           else "every held document has already been walked to the door")}
    targets = list(row.get("targets") or [])
    if not targets:
        return {"id": sid, "emitted": 0, "created": 0, "discoveries": 0,
                "reason": (str(row.get("reason") or "")
                           or f"country {row['country']!r} has no pack under "
                           "research/countries/, so the ground names no MT5 instrument; add "
                           "the pack (EXECUTABLE_INSTRUMENTS) and it converts on the next pass")}
    made = created = n_disc = 0
    errors: list[str] = []
    for cl in claims:
        text = " ".join(cl["text"].split())[:600]
        mech = (f"{row['region']} ground {sid} ({row['kind']}) reports: {text}" if text
                else f"{row['region']} ground {sid} ({row['kind']}) holds an unparsed document")
        if dry_run:
            n_disc += 1
            continue
        try:
            from libs.moat.registry import record_discovery
            _did, _new = record_discovery(
                source_id=sid, source_type="world_ground", mechanism=mech,
                origin="pack_cells", generator="pack_cells.world",
                assets=targets, exact_rule_if_known="", horizons=list(CHARTS),
                note=(f"claim {cl['claim_id']} held since the crawl; knowable_at "
                      f"{cl['knowable_at'] or 'UNMEASURED'}"))
            n_disc += 1
        except Exception as exc:
            errors.append(f"{sid}: {type(exc).__name__}: {str(exc)[:50]}")
            break
    mech_src = (f"the {row['region']} ground {sid} publishes information about "
                f"{', '.join(targets[:4])} that price alone does not carry")
    for sym in targets:
        for chart in CHARTS:
            made += 1
            if dry_run:
                continue
            try:
                from libs.moat.registry import enqueue_candidate
                _cid, was_new = enqueue_candidate(
                    family="regional_information", symbol=sym,
                    params={"source": sid, "region": row["region"],
                            "country": row["country"], "kind": row["kind"]},
                    origin="pack_cells", mechanism=mech_src, chart=chart, horizon=chart,
                    # THE REGION IS STAMPED AT BIRTH, not left in `params` where no reader looks.
                    # `pack_cells.world` is desk machinery by name, so without this the cell the
                    # REGIONAL lane exists to mint was stamped NOT_REGIONAL -- the one producer
                    # whose whole purpose is a region, filed as belonging to none.
                    # `attribution.region_of_command` crosswalks the pack vocabulary (EUROPE,
                    # RUSSIA_CIS, MEA, ...) onto the census's regions, so both stay whole.
                    region=row["region"],
                    source_id=sid, generator="pack_cells.world", department="information",
                    transformation="world_ground", pit_status="UNMEASURED",
                    causal_rationale=mech_src,
                    falsifier=(f"documents from {sid} have no measurable relation to {sym} "
                               f"at {chart} out of sample"))
                created += int(bool(was_new))
            except Exception as exc:
                errors.append(f"{sid}/{sym}/{chart}: {type(exc).__name__}: {str(exc)[:40]}")
    return {"id": sid, "emitted": made, "created": created, "discoveries": n_disc,
            "claims_read": len(claims), "errors": errors[:3]}


#: VERDICTS UNDER WHICH THE RAW-PACK LANE MAY MINT FROM A PACK'S LAKE FRAME: `confirmed` ONLY,
#: a terms row read and its permitting clause quoted (coordinator's ruling on #229, 2026-10-07).
#: Terms fail closed and need a quoted clause; `ungoverned` (a URL on a host no terms row governs)
#: has none, so it mints nothing. asia_collector may still FETCH such a pack -- raw collection
#: neither mints nor trades -- but its frame is HELD here until its host has a confirmed row.
#: Measured on this registry 2026-10-07: 224 of 242 packs are ungoverned; the lane comes back
#: host by host as terms rows land in alt_proxies, never by widening this set. Everything else
#: -- ungoverned, refused, to_confirm, an unknown terms id, a pack with no terms_ref and no URL --
#: mints nothing (fail closed).
PACK_MINT_VERDICTS: frozenset[str] = frozenset({"confirmed"})
_VERDICT_RANK = {"refused": 0, "to_confirm": 1, "ungoverned": 2, "confirmed": 3}


def _has_quote(ref_or_url: str) -> bool:
    """True when the terms row deciding this id or URL records a terms_url and a verbatim
    terms_quote (alt_proxies TERMS_EVIDENCE / GATE_TERMS_EVIDENCE)."""
    try:
        from research.alt_proxies import GATE_TERMS_EVIDENCE, TERMS_EVIDENCE, _terms_id
    except Exception:
        return False
    sid = _terms_id(ref_or_url) or ""
    ev = TERMS_EVIDENCE.get(sid) or GATE_TERMS_EVIDENCE.get(sid) or {}
    return bool(str(ev.get("terms_quote") or "").strip() and ev.get("terms_url"))


def pack_terms(pack: dict[str, Any]) -> dict[str, Any]:
    """{terms, terms_ref, why} for one raw pack, read through the SAME gate the semantic lane
    uses (`alt_proxies.terms_gate`): the row's own `terms_ref`, its adapter's terms id
    (`cn_official_tables.ADAPTER_TERMS`) and its URL's host, worst verdict wins. A pack none of
    which resolves has no terms mapping and reads `to_confirm` -- never permission."""
    refs: list[str] = []
    if pack.get("terms_ref"):
        refs.append(str(pack["terms_ref"]))
    try:
        from research.cn_official_tables import ADAPTER_TERMS
        ad = ADAPTER_TERMS.get(str(pack.get("adapter") or ""))
        if ad and ad not in refs:
            refs.append(ad)
    except Exception:
        pass
    url = str(pack.get("url_override") or pack.get("url") or "")
    try:
        from research.alt_proxies import terms_gate
    except Exception as exc:
        return {"terms": "to_confirm", "terms_ref": refs[0] if refs else "",
                "why": f"terms gate unimportable ({type(exc).__name__}): fail closed"}
    verdicts: list[tuple[str, str, str]] = [(*terms_gate(r), r) for r in refs]
    if "://" in url:
        st, why = terms_gate(url)
        if st != "ungoverned" or not refs:
            verdicts.append((st, why, url.split("?")[0][:120]))
    # A QUOTED CLAUSE OR NOTHING (#229 ruling): a `confirmed` row with no recorded terms_quote
    # (an older row decided before evidence was kept) reads to_confirm for this lane.
    verdicts = [(st, why, r) if st != "confirmed" or _has_quote(r) else
                ("to_confirm", f"{r}: confirmed row carries no quoted clause -- fail closed "
                 "until its terms_url and verbatim terms_quote are recorded", r)
                for st, why, r in verdicts]
    if not verdicts:
        return {"terms": "to_confirm", "terms_ref": "",
                "why": "no terms_ref, adapter or URL resolves a terms decision: fail closed"}
    worst = min(verdicts, key=lambda v: _VERDICT_RANK.get(v[0], 1))
    return {"terms": worst[0], "terms_ref": worst[2], "why": worst[1]}


#: The census buckets, in the order the report prints them. `to_confirm_fetch_blocked` is a
#: to_confirm whose deciding row could not be read from the authoring container (its evidence
#: names a box_action); `ungoverned` should read 0 once every pack host has a row.
CENSUS_BUCKETS: tuple[str, ...] = ("confirmed", "to_confirm", "to_confirm_fetch_blocked",
                                   "refused", "ungoverned")


def _pack_host(pack: dict[str, Any]) -> str:
    url = str(pack.get("url_override") or pack.get("url") or "")
    if "://" not in url:
        return ""
    import urllib.parse
    return urllib.parse.urlsplit(url).netloc.lower().split(":")[0]


def _census_bucket(verdict: str, ref: str) -> str:
    if verdict == "to_confirm":
        try:
            from research.alt_proxies import terms_fetch_status
            if terms_fetch_status(ref) == "FETCH_BLOCKED":
                return "to_confirm_fetch_blocked"
        except Exception:
            pass
    return verdict if verdict in CENSUS_BUCKETS else "to_confirm"


def terms_census(rows_in: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """{bucket: {hosts, packs}} over the registry's packs, read through the same gate the lane
    mints by. PACKS are bucketed by `pack_terms` (the verdict that decides minting); HOSTS by the
    host's own row (`alt_proxies.terms_gate(url)`, a confirmed row with no quote counting as
    to_confirm, as it does for minting). Only `confirmed` mints."""
    packs_ = packs() if rows_in is None else rows_in
    out: dict[str, dict[str, Any]] = {b: {"hosts": 0, "packs": 0} for b in CENSUS_BUCKETS}
    host_bucket: dict[str, str] = {}
    try:
        from research.alt_proxies import terms_gate
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"terms gate unimportable: {type(exc).__name__}"}
    for p in packs_:
        gate = pack_terms(p)
        out[_census_bucket(str(gate["terms"]), str(gate["terms_ref"]))]["packs"] += 1
        host = _pack_host(p)
        if host and host not in host_bucket:
            url = str(p.get("url_override") or p.get("url"))
            hv = terms_gate(url)[0]
            hv = "to_confirm" if hv == "confirmed" and not _has_quote(url) else hv
            host_bucket[host] = _census_bucket(hv, url)
    for b in host_bucket.values():
        out[b]["hosts"] += 1
    return {"status": "OK", "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_packs": len(packs_), "n_hosts": len(host_bucket), "buckets": out,
            "mints": "confirmed only (PACK_MINT_VERDICTS)",
            "rule": ("packs by the verdict that decides minting (pack_terms: own terms_ref, "
                     "adapter and host, worst wins); hosts by the host's own terms row")}


def emit_for(pack: dict[str, Any], signals: list[str], targets: list[str], *,
             dry_run: bool = False, offset: int = 0) -> dict[str, Any]:
    """Every (signal x transform x target x chart) cell for one pack, through the one door.
    Nothing is minted unless the pack's terms read a PACK_MINT_VERDICTS verdict."""
    pid = str(pack.get("id"))
    gate = pack_terms(pack)
    if gate["terms"] not in PACK_MINT_VERDICTS:
        return {"id": pid, "emitted": 0, "created": 0,
                "status": f"BLOCKED_ON_TERMS:{gate['terms']}", "terms": gate["terms"],
                "terms_ref": gate["terms_ref"], "error": f"BLOCKED_ON_TERMS:{gate['terms']}"}
    take = signals[offset % max(len(signals), 1):][:SIGNALS_PER_PACK_PER_PASS]
    if not take:
        take = signals[:SIGNALS_PER_PACK_PER_PASS]
    mech = (f"the {pid} release conditions {', '.join(targets)}: a move in its published series "
            "carries information about the instrument's next move that price alone does not")
    did = ""
    if not dry_run:
        try:
            from libs.moat.registry import record_discovery
            did, _created = record_discovery(
                source_id=pid, source_type="data_pack", mechanism=mech,
                origin="pack_cells", generator="pack_cells", assets=list(targets),
                exact_rule_if_known="", horizons=list(CHARTS),
                note="represented pack; cells minted per signal, transform, target and chart")
        except Exception as exc:
            return {"id": pid, "emitted": 0, "created": 0,
                    "error": f"record_discovery: {type(exc).__name__}: {str(exc)[:70]}"}
    made = created = 0
    errors: list[str] = []
    att = pack_attribution(pack)
    extra: dict[str, Any] = {"lineage": {"attribution": att}} if att else {}
    for sig in take:
        for tf in TRANSFORMS:
            for sym in targets:
                for chart in CHARTS:
                    made += 1
                    if dry_run:
                        continue
                    try:
                        from libs.moat.registry import enqueue_candidate
                        _cid, was_new = enqueue_candidate(
                            family="exogenous_conditioner", symbol=sym,
                            params={"source": pid, "signal": sig, "transform": tf},
                            origin="pack_cells", mechanism=mech, chart=chart,
                            horizon=chart, source_id=pid, discovery_id=did or None,
                            generator="pack_cells", department="information",
                            asset_class="", transformation="pack_signal",
                            required_data=[f"desks/mt5/data/lake/series/{pid}.parquet"],
                            pit_status="STAMPED",
                            causal_rationale=mech,
                            falsifier=(f"the {tf} of {pid}.{sig} has no measurable relation to "
                                       f"{sym} at {chart} out of sample"),
                            **extra)
                        created += int(bool(was_new))
                    except Exception as exc:
                        errors.append(f"{sig}/{tf}/{sym}/{chart}: "
                                      f"{type(exc).__name__}: {str(exc)[:50]}")
    return {"id": pid, "discovery_id": did, "signals_used": take, "emitted": made,
            "created": created, "errors": errors[:5]}


def drain_reachability(st: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """DOES THE DRAIN'S REPAIR PATH REACH WHAT IS STILL AT ZERO, and where not, WHAT SHAPE.

    `source_drain.repair` owns two repairs and this organ neither edits nor duplicates them: bytes
    with no stamped series go to `asia_parser.parse_all`; a represented source with no cell is
    enqueued as a discovery. Its reach is therefore exactly:

      never collected            NOT reachable by repair -- it is the COLLECTOR's queue (`drain`),
                                 and the shape that defeats it is the last collector status
      collected, not represented REACHABLE: `asia_parser` is handed it every pass, highest EVIG
                                 first, and the parse error IS the reader job when its dispatch
                                 fails
      represented, no cell       REACHABLE by both organs now: the drain enqueues a discovery and
                                 `pack_cells` mints the cells directly from the stamped frame
      cells, none judged         NOT reachable by either -- see `judged_registers`

    The shapes are grouped so the next reader is a KNOWN JOB and not a search: one row per
    distinct failure text, with the sources that share it.
    """
    if not st:
        return {"status": "UNMEASURED",
                "why": "source_drain has published no chain state on this host"}
    buckets: dict[str, list[str]] = {}
    shapes: dict[str, dict[str, Any]] = {}
    for sid, row in st.items():
        if not isinstance(row, dict):
            continue
        stage = str(row.get("stage_reached") or "none")
        collected = bool(row.get("collected"))
        represented = bool(row.get("represented"))
        emitted = int(row.get("cells_emitted") or 0)
        if not collected:
            key = "never_collected"
            shape = str(row.get("last_status") or "no collector attempt recorded")
        elif not represented:
            key = "collected_not_represented"
            shape = str(row.get("parse_error") or "no parse error recorded: the reader produced "
                        "no frame and said nothing")
        elif emitted <= 0:
            key = "represented_no_cell"
            shape = str(row.get("why") or stage)
        else:
            key = "cells_emitted_none_judged" if int(row.get("cells_judged") or 0) <= 0 \
                else "converted"
            shape = ""
        buckets.setdefault(key, []).append(sid)
        if shape:
            s = shapes.setdefault(f"{key}: {shape[:110]}",
                                  {"bucket": key, "shape": shape[:300], "n": 0, "sources": []})
            s["n"] += 1
            if len(s["sources"]) < 8:
                s["sources"].append(sid)
    reach = {
        "never_collected": ("NOT the repair path: these are the COLLECTOR's queue, handed out by "
                            "source_drain.drain half by EVIG and half by staleness every pass"),
        "collected_not_represented": ("REACHED: source_drain.repair hands the top 8 by EVIG to "
                                      "asia_parser.parse_all every pass; a survivor is a reader "
                                      "job and its parse error is the specification"),
        "represented_no_cell": ("REACHED TWICE now: source_drain.repair enqueues a discovery and "
                                "pack_cells mints the cells from the stamped frame the same hour"),
        "cells_emitted_none_judged": ("NOT reachable by either organ: no judge writes a verdict "
                                      "back against a candidate id (see judged_registers)"),
        "converted": "converted: cells reached a judge",
    }
    return {
        "status": "OK",
        "n_sources": len(st),
        "counts": {k: len(v) for k, v in sorted(buckets.items())},
        "reached_by_repair": reach,
        "defeating_shapes": sorted(shapes.values(), key=lambda s: -int(s["n"]))[:20],
        "rule": ("grouped by the text that defeated the desk's own reader, so the next reader is "
                 "a named job with its sources attached and never a search"),
    }


def build(budget_s: float = 240.0, *, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    rows_in = packs()
    st = chain()
    cursor = _read(CURSOR, {}) or {}
    offsets: dict[str, int] = dict(cursor.get("offsets") or {})
    start = int(cursor.get("next_pack") or 0)

    rows: list[dict[str, Any]] = []
    eligible: list[tuple[dict[str, Any], list[str], list[str], int]] = []
    for p in rows_in:
        pid = str(p.get("id"))
        stage = str((st.get(pid) or {}).get("stage_reached") or "unmeasured")
        targets = targets_of(p)
        row: dict[str, Any] = {"id": pid, "stage": stage, "targets": targets,
                               "cadence": p.get("cadence")}
        # THE TERMS GATE, BEFORE ANY FRAME IS READ (the semantic lane's rule, for raw packs): a
        # lake frame on disk is not a licence to use it. Nothing is minted and the frame is HELD.
        gate = pack_terms(p)
        row.update({"terms": gate["terms"], "terms_ref": gate["terms_ref"]})
        if gate["terms"] not in PACK_MINT_VERDICTS:
            row.update({"status": f"BLOCKED_ON_TERMS:{gate['terms']}",
                        "reason": (f"BLOCKED_ON_TERMS:{gate['terms']}: "
                                   f"{str(gate['why'])[:240]}")})
            held = series_path(pid)
            if held is not None and not dry_run:
                from mt5desk.family_exogenous_conditioner import hold_series
                row["held_series"] = hold_series(pid, row["status"], held.parent)
            rows.append(row)
            continue
        if not st:
            row["reason"] = ("UNMEASURED: source_drain has not published a chain state on this "
                             "host, so no pack's stage is known")
            rows.append(row)
            continue
        if stage not in ("represented", "cells_emitted", "cells_judged"):
            row["reason"] = str((st.get(pid) or {}).get("why")
                                or f"the chain stops at {stage}: no stamped series to read")
            rows.append(row)
            continue
        path = series_path(pid)
        if path is None:
            row["reason"] = ("the chain calls it represented and no canonical frame "
                             f"{pid}.parquet|.csv is on disk; asia_parser writes that alias")
            rows.append(row)
            continue
        sigs, n_rows, why = signals_of(path)
        row.update({"series": path.name, "n_rows": n_rows, "n_signals": len(sigs)})
        if not sigs:
            row["reason"] = why
            rows.append(row)
            continue
        if not targets:
            row["reason"] = ("the registry declares no MT5 target for this pack, so there is no "
                             "instrument to condition; add `targets` to its registry row")
            rows.append(row)
            continue
        eligible.append((p, sigs, targets, offsets.get(pid, 0)))
        rows.append(row)

    by_id = {r["id"]: r for r in rows}
    order = eligible[start % max(len(eligible), 1):] + eligible[:start % max(len(eligible), 1)] \
        if eligible else []
    emitted_this_pass = created_this_pass = 0
    reached: list[str] = []
    for p, sigs, targets, off in order:
        if time.monotonic() - t0 > budget_s * PACK_LANE_SHARE:
            break
        res = emit_for(p, sigs, targets, dry_run=dry_run, offset=off)
        pid = res["id"]
        reached.append(pid)
        emitted_this_pass += int(res.get("emitted") or 0)
        created_this_pass += int(res.get("created") or 0)
        offsets[pid] = off + SIGNALS_PER_PACK_PER_PASS
        by_id[pid].update({k: res[k] for k in ("discovery_id", "signals_used", "emitted",
                                               "created", "errors") if k in res})
        if res.get("error"):
            by_id[pid]["reason"] = res["error"]

    if not dry_run:
        _write(CURSOR, {"at": now, "offsets": offsets,
                        "next_pack": (start + len(reached)) % max(len(eligible), 1),
                        "rule": ("a round robin over eligible packs and a per-pack signal "
                                 "offset, so every pack and every column is reached; a pack not "
                                 "reached this pass leads the next one")})

    # ---------------------------------------------------------------- the world lane
    # DOCUMENTS ALREADY HELD, HIGHEST FIRST. A ground the crawler has already paid to fetch and
    # that has never produced a cell is the cheapest cell on the desk; one that holds nothing is
    # a crawl problem, not a conversion one. The order IS the ranking, so a pass cut short leaves
    # the next one starting at the top of the list rather than searching for it.
    ladder_cache: dict[str, dict[str, Any]] = {}
    wrows, world_why = world_rows(ladder_cache)
    woffsets: dict[str, int] = dict(cursor.get("world_offsets") or {})
    backlog = sorted([w for w in wrows if w["n_documents"] > 0 and w["cells_emitted"] <= 0],
                     key=lambda w: (-w["n_documents"], w["id"]))
    world_emitted = world_created = world_disc = 0
    world_reached: list[str] = []
    for w in backlog:
        if time.monotonic() - t0 > budget_s:
            break
        res = emit_world(w, dry_run=dry_run, offset=woffsets.get(w["id"], 0))
        world_reached.append(w["id"])
        world_emitted += int(res.get("emitted") or 0)
        world_created += int(res.get("created") or 0)
        world_disc += int(res.get("discoveries") or 0)
        woffsets[w["id"]] = woffsets.get(w["id"], 0) + int(res.get("claims_read") or 0)
        if res.get("reason"):
            w["reason"] = res["reason"]

    if not dry_run:
        _write(CURSOR, {"at": now, "offsets": offsets, "world_offsets": woffsets,
                        "next_pack": (start + len(reached)) % max(len(eligible), 1),
                        "rule": ("a round robin over eligible packs and a per-pack signal "
                                 "offset, so every pack and every column is reached; the world "
                                 "lane is ordered by documents already held, highest first")})

    counts, counts_why = _registry_counts()
    for r in rows:
        c = counts.get(r["id"]) or {}
        r["cells_emitted"] = int(c.get("emitted") or 0)
        r["cells_judged"] = int(c.get("judged") or 0)
        if r["cells_emitted"] > 0 and r["cells_judged"] == 0 and not r.get("reason"):
            r["reason"] = ("cells are in the registry and the one gauntlet has not reached them "
                           "yet; trials_ledger holds no trial for this pack's candidates")
    # re-read the world lane after emission, so its numbers are POST-pass like the packs'
    wrows_after, _ = world_rows(ladder_cache) if not dry_run else (wrows, "")
    for w in wrows_after:
        prev = next((x for x in wrows if x["id"] == w["id"]), None)
        if prev is not None and prev.get("reason"):
            w["reason"] = prev["reason"]
        if w["cells_emitted"] <= 0 and not w.get("reason"):
            w["reason"] = ("no document held: the crawler has not fetched this ground yet"
                           if w["n_documents"] <= 0 else
                           "documents held and not yet walked to the door; it leads the backlog")

    by_region: dict[str, dict[str, int]] = {}
    for w in wrows_after:
        reg = by_region.setdefault(str(w["region"] or "UNMAPPED"),
                                   {"grounds": 0, "with_documents": 0, "documents": 0,
                                    "grounds_with_cells": 0, "cells_emitted": 0,
                                    "cells_judged": 0, "discoveries": 0})
        reg["grounds"] += 1
        reg["with_documents"] += int(w["n_documents"] > 0)
        reg["documents"] += int(w["n_documents"])
        reg["grounds_with_cells"] += int(w["cells_emitted"] > 0)
        reg["cells_emitted"] += int(w["cells_emitted"])
        reg["cells_judged"] += int(w["cells_judged"])
        reg["discoveries"] += int(w["discoveries"])
    # EUROPE IS REPORTED BY NAME because it is the biggest zero: the region's grounds are the
    # largest block in the registry and carried no cell at all when this lane was written.
    europe = {k: v for k, v in by_region.items()
              if "EUROPE" in k or k in ("CEE", "CEE_BALKANS", "EA", "NORDIC", "BLACK_SEA")}
    europe_total = {k: sum(int(v.get(k) or 0) for v in europe.values())
                    for k in ("grounds", "with_documents", "documents", "grounds_with_cells",
                              "cells_emitted", "cells_judged", "discoveries")}

    # ---- STEP 1 PUBLISHED AS A NUMBER: how each ground got its instruments, by rung.
    mapped_by: dict[str, int] = {}
    for w in wrows_after:
        mapped_by[str(w.get("mapped_by") or "none")] = \
            mapped_by.get(str(w.get("mapped_by") or "none"), 0) + 1
    still_unmapped = [{"id": w["id"], "n_documents": w["n_documents"], "kind": w["kind"],
                       "hosts": w.get("hosts") or [], "reason": w.get("reason") or "",
                       "next_job": w.get("next_job") or ""}
                      for w in sorted(wrows_after, key=lambda x: -x["n_documents"])
                      if not w.get("targets") and w["n_documents"] > 0]
    mapping = {
        "by_rung": dict(sorted(mapped_by.items(), key=lambda kv: -kv[1])),
        "grounds_with_documents_now_naming_an_instrument": sum(
            1 for w in wrows_after if w["n_documents"] > 0 and w.get("targets")),
        "grounds_with_documents": sum(1 for w in wrows_after if w["n_documents"] > 0),
        "still_unmapped": still_unmapped[:40],
        "n_still_unmapped": len(still_unmapped),
        "rungs": ["country_pack (the registry's country column)",
                  "jurisdiction_of_documents (the ccTLD of the hosts its documents came from, "
                  "against an index inverted out of the packs' own JURISDICTIONS)",
                  "instruments_named_in_documents (MT5 symbols named verbatim, routed through "
                  "universe_policy so a single-name equity is never minted as a hypothesis)"],
        "rule": ("a rung never narrows the one above it: the ladder only reaches grounds that "
                 "had no instrument at all, and a ground it cannot resolve carries the hosts it "
                 "saw and the rung that failed"),
    }

    # ---- STEP 3 PUBLISHED AS A NUMBER: judged per region, which is the end of the chain.
    judged_by_region = {k: int(v["cells_judged"]) for k, v in by_region.items()}
    regions_judged = sorted(k for k, v in judged_by_region.items() if v > 0)
    regions_none = sorted(k for k, v in judged_by_region.items() if v <= 0)
    jr = judged_registers()
    dr = drain_reachability(st)
    # THE SAME QUESTION ON THE KEY THAT CAN ANSWER IT. `judged_by_region` above is per GROUND and
    # is structurally zero for every region while the judged cells carry no source_id; this is per
    # CELL, off its own birth stamp. Both are published so neither can stand in for the other.
    jstamped = judged_by_stamped_region()

    n_emit = sum(1 for r in rows if r["cells_emitted"] > 0)
    n_judged = sum(1 for r in rows if r["cells_judged"] > 0)
    zero = [{"id": r["id"], "stage": r["stage"], "reason": r.get("reason") or "unexplained"}
            for r in rows if r["cells_emitted"] <= 0]
    remaining = [{"id": w["id"], "region": w["region"], "country": w["country"],
                  "n_documents": w["n_documents"], "kind": w["kind"],
                  "reason": w.get("reason") or ""}
                 for w in sorted(wrows_after, key=lambda x: (-x["n_documents"], x["id"]))
                 if w["n_documents"] > 0 and w["cells_emitted"] <= 0][:200]
    return {
        "world": {
            "n_grounds": len(wrows_after),
            "n_with_documents": sum(1 for w in wrows_after if w["n_documents"] > 0),
            "n_documents": sum(int(w["n_documents"]) for w in wrows_after),
            "grounds_with_cells": sum(1 for w in wrows_after if w["cells_emitted"] > 0),
            "grounds_with_a_judged_cell": sum(1 for w in wrows_after if w["cells_judged"] > 0),
            "cells_emitted_total": sum(int(w["cells_emitted"]) for w in wrows_after),
            "cells_judged_total": sum(int(w["cells_judged"]) for w in wrows_after),
            "cells_emitted_this_pass": world_emitted,
            "cells_created_this_pass": world_created,
            "discoveries_this_pass": world_disc,
            "grounds_reached_this_pass": len(world_reached),
            "backlog_with_documents_and_no_cell": len(backlog),
            "why": world_why or "",
            "by_region": dict(sorted(by_region.items(),
                                     key=lambda kv: -kv[1]["documents"])),
            "mapping": mapping,
            "judged_by_region": dict(sorted(judged_by_region.items(), key=lambda kv: -kv[1])),
            "judged_by_region_basis": (
                "PER GROUND: sources.source_id -> research_candidates.source_id -> a verdict. A "
                "judged cell that carries no source_id can never be credited to a ground, so this "
                "number is zero for every region while the judges' output has no ground key -- "
                "which is a fact about the key, not about the regions. "
                "`judged_by_stamped_region` is the same question keyed on the cell's own region."),
            "judged_by_stamped_region": jstamped,
            "regions_with_a_judged_cell": regions_judged,
            "regions_with_no_judged_cell": regions_none,
            "judged_by_source": {w["id"]: int(w["cells_judged"]) for w in wrows_after
                                 if int(w["cells_judged"]) > 0},
            "europe": {"regions": sorted(europe), **europe_total},
            "remaining_ranked_by_documents_held": remaining,
            "rule": ("ordered by documents ALREADY FETCHED, highest first: a ground the crawler "
                     "has paid for and that has never produced a cell is the cheapest cell on "
                     "the desk. A pass cut short leaves this list for the next one."),
        },
        "at": now,
        "status": "OK" if rows else "UNMEASURED",
        "n_packs": len(rows),
        "n_eligible": len(eligible),
        "n_reached_this_pass": len(reached),
        "packs_with_cells": n_emit,
        "packs_with_a_judged_cell": n_judged,
        "cells_emitted_total": sum(int(r["cells_emitted"]) for r in rows),
        "cells_judged_total": sum(int(r["cells_judged"]) for r in rows),
        "cells_emitted_this_pass": emitted_this_pass,
        "cells_created_this_pass": created_this_pass,
        "counts_basis": (counts_why or "research_candidates.source_id for emitted; "
                         "trials_ledger.candidate_id for judged (the one gauntlet's own record)"),
        "judged_registers": jr,
        "judged_by_pack": {r["id"]: int(r["cells_judged"]) for r in rows
                           if int(r["cells_judged"]) > 0},
        "drain_reachability": dr,
        "packs_at_zero": zero,
        "blocked_on_terms": {r["id"]: r["status"] for r in rows
                             if str(r.get("status", "")).startswith("BLOCKED_ON_TERMS")},
        "terms_census": terms_census(rows_in),
        "rows": rows,
        "dry_run": bool(dry_run),
        "consumers": [
            "libs/moat/registry.py research_candidates -> the one gauntlet claims and judges "
            "these cells like any other; no second store and no second judge",
            "desks/mt5/reports/PACK_CELLS.json -> CELLS EMITTED and CELLS JUDGED per pack, and "
            "the named reason for every pack still at zero",
            "desks/mt5/research/source_drain.py -> reads the same registry credit, so its "
            "cells_emitted stage advances as this organ mints",
        ],
        "boundary": ("MINTS ONLY. Nothing here judges, sizes, vetoes or refuses a pack; the "
                     "per-pass budget is a wall clock and a pack not reached leads the next "
                     "pass."),
        "seconds": round(time.monotonic() - t0, 2),
    }


# =============================================================================== semantic lane
# THE CHINA OFFICIAL PACKS GET SEMANTIC TRANSFORMS, NOT THREE GENERIC ONES (audit 2026-10-06,
# rows 1-5 and 7). `level_z / delta / delta_z` of any numeric column cannot see a
# settlement-sales IMBALANCE, a PMI orders-inventory GAP, a curve SLOPE or a fixing SURPRISE:
# each is a relation between columns or against a model, and each is what the directive names
# as the observable ("do not use the fixing level alone"). This lane reads the append-only
# ledgers `asia_parser` keeps (first-release view only, so no revised value is ever back-dated),
# builds those features with the PIT `available_time` of their newest input, writes them as
# `series/<pack>__sem.parquet`, and sends exogenous-conditioner cells on them through THE DOOR:
# `proposer_common.screen` (family signals on the target's own bars, net of cost) ->
# `deflate` (charged for every look this pass) -> `donate`, with a null pass charged to
# `data/null_pass_trials.jsonl` so no look is free. Targets are the registry's, resolved to the
# MT5 universe and routed by asset class through `universe_policy`.

SEM_SEAT = "pack_cells_cn"
SEM_CURSOR = DESK / "data" / "pack_cells_sem_cursor.json"
NULL_TRIALS = DESK / "data" / "null_pass_trials.jsonl"

#: Semantic builder per registry pack. Packs sharing a builder are merged first (the CFETS daily
#: payload and its history endpoint describe the same fixings).
SEMANTIC_PACKS: dict[str, tuple[str, ...]] = {
    "safe_settlement": ("safe_fx_settlement",),
    "safe_cross_border": ("safe_cross_border",),
    "safe_reserves": ("safe_reserves",),
    "cfets_fix": ("cfets_fixing", "cfets_fixing_history"),
    "shibor": ("cn_shibor",),
    "omo": ("pboc_open_market",),
    "pmi_mfg": ("nbs_pmi",),
    "pmi_nonmfg": ("nbs_pmi_nonmfg",),
    "macro_industrial": ("nbs_industrial",),
    "macro_prices": ("nbs_prices",),
    "customs": ("china_customs", "cn_customs_detail"),
}
#: THE DATA SOURCE EACH SEMANTIC BUILDER'S CELLS DECLARE, `<provider>:<dataset>` -- the shape the
#: world-sensor cell contract (#211, emit_conditioner_cells) requires so a terms hold can be
#: matched to a cell. Carried on every candidate row this lane donates.
SEM_DATA_SOURCE: dict[str, str] = {
    "safe_settlement": "safe:fx_settlement", "safe_cross_border": "safe:cross_border",
    "safe_reserves": "safe:reserves", "cfets_fix": "cfets:ccpr", "shibor": "cfets:shibor",
    "omo": "pboc:omo", "pmi_mfg": "nbs:pmi", "pmi_nonmfg": "nbs:pmi_nonmfg",
    "macro_industrial": "nbs:industrial", "macro_prices": "nbs:prices",
    "customs": "customs:trade",
}
#: THE TERMS EACH SEMANTIC BUILDER'S PUBLISHER IS HELD TO (#229 terms ruling, 2026-10-06), the
#: ids of `alt_proxies.GATE_TERMS` / `cn_official_tables.ADAPTER_TERMS`. Declared per builder so a
#: builder whose registry row is missing is still governed; the member rows' own `terms_ref` (or
#: their adapter's) is read as well, and EVERY id must read `confirmed` or the builder mints
#: nothing: no frame read, no screen, no donation, no trial charged. Today only the statistics
#: bureau (stats.gov.cn) is confirmed; CFETS (chinamoney.com.cn, shibor.org: CCPR and SHIBOR)
#: reads `refused`, and SAFE, the PBOC and customs `to_confirm`. The fixing-TIME window studies
#: (country_lab's 01:15 / 08:30 UTC USDCNH windows) read only the broker's own tape and are not
#: builders of this lane, so nothing here holds them.
SEM_TERMS_REF: dict[str, str] = {
    "safe_settlement": "cn_safe_official", "safe_cross_border": "cn_safe_official",
    "safe_reserves": "cn_safe_official", "cfets_fix": "cn_cfets_chinamoney",
    "shibor": "cn_cfets_chinamoney", "omo": "cn_pboc_official", "pmi_mfg": "cn_nbs_official",
    "pmi_nonmfg": "cn_nbs_official", "macro_industrial": "cn_nbs_official",
    "macro_prices": "cn_nbs_official", "customs": "cn_customs_official",
}
#: Registry target spellings that are not MT5 symbols, resolved to the universe's own names.
TARGET_ALIASES: dict[str, str] = {"Copper": "XCUUSD", "CN50": "CHINAH", "CHINA50": "CHINAH",
                                  "A50": "CHINAH"}
#: Customs commodities the directive names first (Part I.D), matched on the printed name.
CUSTOMS_PRIORITY: tuple[str, ...] = ("铁矿", "铜", "原油", "天然气", "煤", "黄金", "金", "银",
                                     "大豆", "粮食", "钢", "铝", "镍", "锂", "多晶硅", "集成电路")
SEM_GRID: dict[str, tuple[Any, ...]] = {"threshold": (1.0, 1.5), "side_when_high": (1, -1)}
SEM_FEATURES_PER_PASS = 8
SEM_BUDGET_SHARE = 0.35
#: The fixing model's rolling fit: observations strictly BEFORE the fix being explained.
FIX_FIT_WINDOW = 120
FIX_FIT_MIN = 40


def sem_terms(builder: str, reg: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """{terms, terms_ref, why} for one semantic builder, FAIL CLOSED.

    `terms` is `confirmed` only when the declared id AND every member row's own terms id read
    `confirmed` through `alt_proxies.terms_gate`; otherwise the worst of them (`refused` before
    `to_confirm`). An unknown builder, an unreadable gate or an id the gate does not know is
    `to_confirm`, never permission."""
    refs = [SEM_TERMS_REF.get(builder, f"pack_cells_sem:{builder}")]
    adapter_terms: dict[str, str] = {}
    try:
        from research.cn_official_tables import ADAPTER_TERMS
        adapter_terms = dict(ADAPTER_TERMS)
    except Exception:
        pass
    for pid in SEMANTIC_PACKS.get(builder, ()):
        row = (reg or {}).get(pid) or {}
        ref = str(row.get("terms_ref") or adapter_terms.get(str(row.get("adapter") or ""), ""))
        if ref and ref not in refs:
            refs.append(ref)
    try:
        from research.alt_proxies import terms_gate
    except Exception as exc:
        return {"terms": "to_confirm", "terms_ref": refs[0],
                "why": f"terms gate unimportable ({type(exc).__name__}): fail closed"}
    worst: tuple[str, str, str] | None = None
    for ref in refs:
        state, why = terms_gate(ref)
        if state == "confirmed":
            continue
        state = "refused" if state == "refused" else "to_confirm"
        if worst is None or (state == "refused" and worst[0] != "refused"):
            worst = (state, ref, why)
    if worst is None:
        return {"terms": "confirmed", "terms_ref": refs[0], "why": ""}
    return {"terms": worst[0], "terms_ref": worst[1], "why": worst[2]}


def _sem_frame(packs_: tuple[str, ...]) -> tuple[Any, str]:
    """The first-release wide frames of the packs, merged on event_time (earliest availability
    wins only where the packs agree on a period: the second source cannot make the first known
    earlier than it was)."""
    import pandas as pd
    try:
        from research.asia_parser import first_release_frame, read_ledger
    except Exception as exc:
        return None, f"asia_parser unimportable: {type(exc).__name__}"
    frames = []
    for pid in packs_:
        rows = read_ledger(pid)
        if not rows:
            continue
        wide, _why = first_release_frame(pid, rows)
        if wide is not None and not wide.empty:
            frames.append(wide)
    if not frames:
        return None, ("UNMEASURED: no ledger rows for " + ", ".join(packs_)
                      + " on this host (asia_parser has not read a vintage of it)")
    df = pd.concat(frames, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
    df["available_time"] = pd.to_datetime(df["available_time"], utc=True, errors="coerce")
    num = [c for c in df.columns if c not in STAMP_COLUMNS and c != "event_time"]
    agg: dict[str, Any] = dict.fromkeys(num, "first")
    agg["available_time"] = "min"
    out = df.groupby("event_time", as_index=False).agg(agg).sort_values("event_time")
    return out.reset_index(drop=True), f"{len(out)} period(s) from {len(frames)} ledger(s)"


def _col(df: Any, metric: str, entity_has: str | None = None,
         unit_pref: tuple[str, ...] = ()) -> Any:
    """The first column for a metric (optionally whose entity contains a substring)."""
    cands = [c for c in df.columns if c == metric or c.startswith(metric + "|")]
    if entity_has is not None:
        cands = [c for c in cands if entity_has in c]
    for u in unit_pref:
        pref = [c for c in cands if u in c]
        if pref:
            return df[pref[0]]
    return df[cands[0]] if cands else None


def surprise(s: Any, *, monthly: bool) -> tuple[Any, Any, Any]:
    """(expected, raw surprise, surprise z) against the series' OWN prior history only.

    Monthly: the same calendar month's mean change over prior years when two exist (a seasonal
    expectation), else the trailing six-period mean. The z divides by the std of PRIOR
    surprises, so a value is never scored against a dispersion that includes itself."""
    import pandas as pd
    s = pd.Series(s, dtype=float)
    trail = s.shift(1).rolling(6, min_periods=3).mean()
    exp = trail
    if monthly and isinstance(s.index, pd.DatetimeIndex) and len(s) >= 25:
        seas = s.groupby(s.index.month).transform(
            lambda x: x.shift(1).expanding(min_periods=2).mean())
        exp = seas.where(seas.notna(), trail)
    raw = s - exp
    sd = raw.shift(1).rolling(24, min_periods=6).std(ddof=0)
    return exp, raw, raw / sd.where(sd > 0)


def _add_generic(feats: dict[str, Any], name: str, s: Any, monthly: bool) -> None:
    """Level, change, acceleration and the surprise trio for one series."""
    feats[name] = s
    feats[f"{name}_delta"] = s.diff()
    feats[f"{name}_accel"] = s.diff().diff()
    _e, raw, z = surprise(s, monthly=monthly)
    feats[f"{name}_surprise"] = raw
    feats[f"{name}_surprise_z"] = z


def semantic_features(builder: str, df: Any, *, bars_fn: Any = None,
                      clock_root: Path | None = None) -> tuple[Any, str]:
    """The builder's features on the merged first-release frame. (frame, why) -- frame None with
    the reason when an input is missing; INSUFFICIENT_HISTORY is a verdict, not a zero."""
    import numpy as np
    import pandas as pd
    if df is None or df.empty:
        return None, "no frame"
    idx = pd.DatetimeIndex(df["event_time"])
    d = df.set_index(idx)
    feats: dict[str, Any] = {}
    if builder == "safe_settlement":
        up_ = ("美元", "人民币")
        sett, sales = _col(d, "settlement", unit_pref=up_), _col(d, "sales", unit_pref=up_)
        if sett is None or sales is None:
            return None, "settlement / sales not both in the ledger"
        tot = (sett + sales).where((sett + sales) != 0)
        feats["imbalance"] = (sett - sales) / tot
        feats["imbalance_delta"] = feats["imbalance"].diff()
        feats["imbalance_accel"] = feats["imbalance_delta"].diff()
        _e, _raw, z = surprise(sett - sales, monthly=True)
        feats["net_surprise_z"] = z
        cs, cp = (_col(d, "customer_settlement", unit_pref=up_),
                  _col(d, "customer_sales", unit_pref=up_))
        if cs is not None and cp is not None:
            feats["customer_imbalance"] = (cs - cp) / (cs + cp).where((cs + cp) != 0)
        fs, fp = (_col(d, "forward_settlement", unit_pref=up_),
                  _col(d, "forward_sales", unit_pref=up_))
        if fs is not None and fp is not None:
            feats["forward_hedge_imbalance"] = (fs - fp) / (fs + fp).where((fs + fp) != 0)
            feats["forward_hedge_imbalance_delta"] = feats["forward_hedge_imbalance"].diff()
        roll = feats["imbalance"].rolling(36, min_periods=12)
        feats["imbalance_pct_rank"] = roll.rank(pct=True)
    elif builder == "safe_cross_border":
        r, p = _col(d, "receipts", unit_pref=("美元",)), _col(d, "payments", unit_pref=("美元",))
        if r is None or p is None:
            return None, "receipts / payments not both in the ledger"
        feats["receipts_payments_ratio"] = r / p.where(p != 0)
        feats["payment_imbalance"] = (r - p) / (r + p).where((r + p) != 0)
        feats["payment_imbalance_accel"] = feats["payment_imbalance"].diff().diff()
        _e, _raw, feats["payment_imbalance_surprise_z"] = surprise(feats["payment_imbalance"],
                                                                   monthly=True)
    elif builder == "safe_reserves":
        fx = _col(d, "fx_reserves", unit_pref=("美元",))
        if fx is None:
            return None, "fx_reserves not in the ledger"
        _add_generic(feats, "fx_reserves_change", fx.diff(), monthly=True)
        gold = _col(d, "gold_reserves", unit_pref=("盎司", "美元"))
        if gold is not None:
            _add_generic(feats, "gold_reserves_change", gold.diff(), monthly=True)
    elif builder == "cfets_fix":
        fx = cfets_fix_surprise(d, bars_fn=bars_fn, clock_root=clock_root)
        if isinstance(fx, str):
            return None, fx
        out = fx
        out["source_id"] = "cfets_fix__sem"
        return out, f"{int(out['fix_surprise_pips'].notna().sum())} modelled fix surprise(s)"
    elif builder == "shibor":
        on, w1 = _col(d, "shibor", "O/N"), _col(d, "shibor", "1W")
        m3, y1 = _col(d, "shibor", "3M"), _col(d, "shibor", "1Y")
        if on is None or y1 is None:
            return None, "O/N and 1Y SHIBOR not both in the ledger"
        feats["curve_slope"] = y1 - on
        if m3 is not None:
            feats["curve_curvature"] = 2.0 * m3 - on - y1
        feats["on_delta"] = on.diff()
        feats["liquidity_impulse_5"] = on.diff(5)
        if w1 is not None:
            feats["w1_on_spread"] = w1 - on
    elif builder == "omo":
        net = _col(d, "omo_net_injection")
        if net is None:
            return None, "no net injection in the ledger (maturity never stated)"
        feats["net_injection"] = net
        feats["net_injection_5"] = net.rolling(5, min_periods=3).sum()
        feats["net_injection_accel"] = feats["net_injection_5"].diff()
    elif builder.startswith("pmi"):
        subs = {c.split("|")[0]: d[c] for c in d.columns
                if c not in STAMP_COLUMNS and c not in ("available_time", "event_time")}
        head = subs.get("pmi") if builder == "pmi_mfg" else subs.get("business_activity")
        if head is not None:
            _add_generic(feats, "headline", head, monthly=True)
        comp = pd.DataFrame({k: v for k, v in subs.items() if k not in ("pmi",)})
        if comp.shape[1] >= 3:
            feats["diffusion"] = (comp > 50.0).mean(axis=1)
            feats["breadth"] = (comp.diff() > 0).mean(axis=1)
            feats["disagreement"] = comp.diff().std(axis=1, ddof=0)
        no = subs.get("new_orders")
        inv = subs.get("finished_goods_inventory")
        if inv is None:
            inv = subs.get("raw_material_inventory")
        if no is not None and inv is not None:
            _add_generic(feats, "orders_inventory_gap", no - inv, monthly=True)
        if subs.get("new_export_orders") is not None:
            feats["export_order_impulse"] = subs["new_export_orders"].diff()
        if subs.get("input_prices") is not None and subs.get("production") is not None:
            feats["price_production_divergence"] = subs["input_prices"] - subs["production"]
        for k in ("new_orders", "production", "employment", "input_prices"):
            if subs.get(k) is not None:
                _add_generic(feats, k, subs[k], monthly=True)
    elif builder.startswith("macro"):
        cols = [c for c in d.columns if c not in STAMP_COLUMNS
                and c not in ("available_time", "event_time")][:20]
        for c in cols:
            _add_generic(feats, re.sub(r"[^A-Za-z0-9]+", "_", c)[:40] or "series",
                         pd.to_numeric(d[c], errors="coerce"), monthly=True)
    elif builder == "customs":
        for c in d.columns:
            if "|" not in c:
                continue
            metric, ent = c.split("|", 1)
            if not any(k in ent for k in CUSTOMS_PRIORITY):
                continue
            slug = hashlib.sha1(ent.encode()).hexdigest()[:6]
            if metric.endswith("_quantity"):
                _e, _raw, feats[f"{metric}_surprise_z_{slug}"] = surprise(d[c], monthly=True)
                feats[f"{metric}_pace_{slug}"] = d[c].rolling(3, min_periods=2).mean()
            elif metric.endswith("_unit_value"):
                q = d.get(c.replace("_unit_value|", "_quantity|"))
                uv = d[c].pct_change()
                if q is not None:
                    qc = q.pct_change()
                    zuv = (uv - uv.shift(1).rolling(12, min_periods=4).mean()) / uv.shift(
                        1).rolling(12, min_periods=4).std(ddof=0)
                    zq = (qc - qc.shift(1).rolling(12, min_periods=4).mean()) / qc.shift(
                        1).rolling(12, min_periods=4).std(ddof=0)
                    feats[f"unit_value_divergence_{slug}"] = zuv - zq
    else:
        return None, f"unknown builder {builder!r}"
    if not feats:
        return None, "INSUFFICIENT_HISTORY: no feature could be formed"
    out = pd.DataFrame(feats, index=idx).replace([np.inf, -np.inf], np.nan)
    out.insert(0, "available_time", d["available_time"].to_numpy())
    out.insert(0, "event_time", idx)
    out = out.reset_index(drop=True)
    keep = [c for c in out.columns if c in ("event_time", "available_time")
            or out[c].notna().sum() >= 3]
    out = out[keep]
    if len(keep) <= 2:
        return None, "INSUFFICIENT_HISTORY: every feature has fewer than 3 values"
    out["source_id"] = f"{builder}__sem"
    return out, f"{len(out)} period(s) x {len(keep) - 2} feature(s)"


def bar_value_at(bars: Any, instant_utc: datetime, field: str,
                 clock_root: Path | None = None) -> float | None:
    """A field of the H1 bar CONTAINING a genuinely-UTC instant, on the bars' broker clock.

    None when `bar_clock` cannot place the instant (no measured clock, shoulder month) or the bar
    is absent -- the observation is dropped, never placed on a guessed offset."""
    import pandas as pd

    from libs.research.bar_clock import to_bar_time
    conv, _status, _why = to_bar_time(instant_utc, clock_root)
    if conv is None:
        return None
    stamp = pd.Timestamp(conv).tz_convert("UTC").floor("h")
    if stamp not in bars.index:
        return None
    return float(bars.loc[stamp, field])


def cfets_fix_surprise(d: Any, *, bars_fn: Any = None, clock_root: Path | None = None) -> Any:
    """The CNY central-parity SURPRISE against the documented fixing model.

    THE MODEL (PBOC/CFETS 2016-: "previous close + basket"): the parity is set from the previous
    day's 16:30 Beijing USD/CNY close plus the move that would keep the CFETS basket stable
    overnight; what is left -- the counter-cyclical / discretionary part -- is the policy signal.
    Here, with the desk's own bars:

        close_prev   USDCNH, CLOSE of the H1 bar containing 08:30 UTC (16:30 Beijing) the
                     previous fixing day (the offshore rate stands in for the onshore close);
        basket move  USDX log return from that bar's close to the OPEN of the bar containing
                     01:00 UTC on the fix day (before the 01:15 UTC announcement);
        implied_t    close_prev + a + b * close_prev * basket_move, with (a, b) fitted by OLS on
                     the previous FIX_FIT_WINDOW fixings ONLY (never on t or later);
        surprise_t   fix_t - implied_t, in pips (1e-4 CNY), and its z against prior residuals.

    No basket weights are invented: b is estimated, so the model is the data's own reading of how
    much basket stabilisation the parity carried. Returns a frame or the reason it cannot."""
    import numpy as np
    import pandas as pd
    fix = _col(d, "central_parity", "USD/CNY")
    if fix is None:
        return "no USD/CNY central parity in the ledger"
    fix = fix.dropna()
    if len(fix) < FIX_FIT_MIN + 5:
        return f"INSUFFICIENT_HISTORY: {len(fix)} fixings < {FIX_FIT_MIN + 5}"
    bars_fn = bars_fn or (lambda s: __import__("research.proposer_common",
                                               fromlist=["bars"]).bars(s))
    cnh, usdx = bars_fn("USDCNH"), bars_fn("USDX")
    if cnh is None or usdx is None:
        return "UNMEASURED: USDCNH or USDX H1 bars absent on this host"
    rows = []
    days = list(fix.index)
    for i in range(1, len(days)):
        t, prev = days[i], days[i - 1]
        prev_close_at = datetime(prev.year, prev.month, prev.day, 8, 30, tzinfo=UTC)
        basket_end = datetime(t.year, t.month, t.day, 1, 0, tzinfo=UTC)
        c_prev = bar_value_at(cnh, prev_close_at, "close", clock_root)
        x0 = bar_value_at(usdx, prev_close_at, "close", clock_root)
        x1 = bar_value_at(usdx, basket_end, "open", clock_root)
        if c_prev is None or x0 is None or x1 is None or x0 <= 0 or x1 <= 0:
            continue
        rows.append({"event_time": t, "fix": float(fix.loc[t]), "cnh_prev_close": c_prev,
                     "basket_move": math.log(x1 / x0)})
    if len(rows) < FIX_FIT_MIN + 5:
        return (f"INSUFFICIENT_HISTORY: {len(rows)} fixings placeable on the bars' clock "
                f"(of {len(fix)}); shoulder months and missing bars are dropped, never guessed")
    m = pd.DataFrame(rows).set_index("event_time")
    y = (m["fix"] - m["cnh_prev_close"]).to_numpy()
    x = (m["cnh_prev_close"] * m["basket_move"]).to_numpy()
    implied = np.full(len(m), np.nan)
    beta = np.full(len(m), np.nan)
    for i in range(len(m)):
        lo = max(0, i - FIX_FIT_WINDOW)
        if i - lo < FIX_FIT_MIN:
            continue
        X = np.column_stack([np.ones(i - lo), x[lo:i]])
        coef, *_ = np.linalg.lstsq(X, y[lo:i], rcond=None)
        implied[i] = m["cnh_prev_close"].iloc[i] + coef[0] + coef[1] * x[i]
        beta[i] = coef[1]
    m["implied_fix"] = implied
    m["basket_beta"] = beta
    m["fix_surprise"] = m["fix"] - m["implied_fix"]
    m["fix_surprise_pips"] = m["fix_surprise"] * 1e4
    prior_sd = m["fix_surprise_pips"].shift(1).rolling(60, min_periods=20).std(ddof=0)
    m["fix_surprise_z"] = m["fix_surprise_pips"] / prior_sd.where(prior_sd > 0)
    m["fix_defence_index_20"] = m["fix_surprise_pips"].rolling(20, min_periods=10).mean()
    m["fix_vs_cnh_gap_pips"] = (m["fix"] - m["cnh_prev_close"]) * 1e4
    avail = pd.to_datetime(d["available_time"], utc=True).reindex(m.index)
    out = m.reset_index()
    # The surprise is knowable when the fix is (09:15 Beijing, the ledger's own stamp) AND the
    # basket bar has opened (01:00 UTC): the later of the two.
    bar_open = out["event_time"].dt.floor("D") + pd.Timedelta(hours=1)
    out.insert(1, "available_time", np.maximum(avail.to_numpy(), bar_open.to_numpy()))
    return out


def resolve_targets(raw: list[str]) -> list[str]:
    """Registry targets -> MT5 symbols the hypothesis lane may mint on, routed by asset class."""
    syms: list[str] = []
    reg = universe_symbols()
    from research import universe_policy as up
    for t in raw:
        s = TARGET_ALIASES.get(t, t)
        if reg and s not in reg:
            continue
        if not up.may_hypothesise(s, "exogenous_conditioner"):
            continue
        if s not in syms:
            syms.append(s)
    return syms


def semantic_lane(budget_s: float = 80.0, *, dry_run: bool = False,
                  bars_fn: Any = None) -> dict[str, Any]:
    """Build every semantic pack's features, then screen -> deflate -> donate its cells."""
    t0 = time.monotonic()
    reg = {str(p.get("id")): p for p in packs()}
    cursor = _read(SEM_CURSOR, {}) or {}
    offsets: dict[str, int] = dict(cursor.get("offsets") or {})
    out: dict[str, Any] = {}
    cands_all: list[dict[str, Any]] = []
    screened: list[dict[str, Any]] = []
    for builder, members in SEMANTIC_PACKS.items():
        row: dict[str, Any] = {"packs": list(members)}
        out[builder] = row
        gate = sem_terms(builder, reg)
        row.update({"terms": gate["terms"], "terms_ref": gate["terms_ref"]})
        if gate["terms"] != "confirmed":
            # HELD ON TERMS: a ledger already on disk is not a licence to use it. No frame is
            # read, no cell screened, nothing donated and no look charged (there was none).
            row.update({"status": f"BLOCKED_ON_TERMS:{gate['terms']}",
                        "why": str(gate["why"])[:300], "tests": 0})
            if not dry_run:
                # A frame this builder wrote while its terms read `confirmed` stays on disk as a
                # record, HELD: the conditioner family never serves it as a current input.
                from mt5desk.family_exogenous_conditioner import hold_series
                row["held_series"] = hold_series(f"{builder}__sem",
                                                 f"BLOCKED_ON_TERMS:{gate['terms']}", SERIES)
            continue
        df, why = _sem_frame(members)
        if df is None:
            row.update({"status": "UNMEASURED", "why": why})
            continue
        feats, fwhy = semantic_features(builder, df, bars_fn=bars_fn)
        if feats is None:
            row.update({"status": ("INSUFFICIENT_HISTORY" if "INSUFFICIENT" in fwhy
                                   else "UNMEASURED"), "why": fwhy})
            continue
        sid = f"{builder}__sem"
        if not dry_run:
            from mt5desk.family_exogenous_conditioner import release_series
            SERIES.mkdir(parents=True, exist_ok=True)
            feats.to_parquet(SERIES / f"{sid}.parquet", index=False)
            release_series(sid, SERIES)
        cols = [c for c in feats.columns if c not in ("event_time", "available_time",
                                                       "source_id")]
        targets: list[str] = []
        for pid in members:
            targets += [t for t in targets_of(reg.get(pid) or {}) if t not in targets]
        syms = resolve_targets(targets)
        row.update({"status": "BUILT", "why": fwhy, "series": f"{sid}.parquet",
                    "features": cols, "targets": syms,
                    "last_available": str(feats["available_time"].max())[:25]})
        off = offsets.get(builder, 0)
        take = (cols[off % len(cols):] + cols[:off % len(cols)])[:SEM_FEATURES_PER_PASS]
        offsets[builder] = off + len(take)
        tests_here = 0
        for sig in take:
            for sym in syms:
                if time.monotonic() - t0 > budget_s:
                    row["stopped"] = "budget"
                    break
                for thr in SEM_GRID["threshold"]:
                    for side in SEM_GRID["side_when_high"]:
                        res = _screen_one(sid, sig, sym, float(thr), int(side), bars_fn)
                        tests_here += 1
                        if res is not None:
                            screened.append(res)
        row["tests"] = tests_here
    # ---- deflate over EVERY look of the pass, then donate what clears it
    donation: dict[str, Any] = {"donated": 0}
    n_tests = sum(int(r.get("tests") or 0) for r in out.values())
    if screened:
        from research import proposer_common as pc
        pc.deflate(screened)
        best = pc.best_per_cell(screened)
        for r in best:
            cands_all.append(r["candidate"])
    if not dry_run and n_tests > 0:
        donation = _sem_donate(cands_all, n_tests)
        _write(SEM_CURSOR, {"at": datetime.now(UTC).isoformat(timespec="seconds"),
                            "offsets": offsets})
    return {"rule": ("semantic features on the first-release ledger view; cells screened on the "
                     "target's bars net of cost, deflated by every look this pass, donated "
                     "through proposer_common; a null pass is charged to null_pass_trials"),
            "seat": SEM_SEAT, "packs": out, "tests_run": n_tests,
            "blocked_on_terms": sorted(b for b, r in out.items()
                                       if str(r.get("status", "")).startswith("BLOCKED_ON_TERMS")),
            "screened_measurable": len(screened),
            "proposed": len(cands_all), "donation": donation,
            "seconds": round(time.monotonic() - t0, 2)}


def _screen_one(sid: str, sig: str, sym: str, thr: float, side: int,
                bars_fn: Any = None, *, seat: str = SEM_SEAT, series_root: Path | None = None,
                mechanism: str | None = None, data_source: str | None = None,
                terms_ref: str | None = None) -> dict[str, Any] | None:
    """One cell through `proposer_common.screen`. None = not measurable (too few trades).

    `seat` / `series_root` / `mechanism` let another organ (the dislocation lab's hard-series
    spreads) send its own series through the same door instead of growing a second one."""
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner

    from research import proposer_common as pc
    bars = bars_fn(sym) if bars_fn is not None else pc.bars(sym)
    if bars is None or len(bars) < 500:
        return None
    params: dict[str, Any] = {"source": sid, "signal": sig, "transform": "level_z",
                              "threshold": thr, "side_when_high": side}
    try:
        sigs = family_exogenous_conditioner(bars, source=sid, signal=sig, transform="level_z",
                                            threshold=thr, side_when_high=side,
                                            series_root=series_root or SERIES)
    except Exception:
        return None
    cost = pc.cost_frac(sym, pc.universe_meta(), bars["close"])
    if cost is None:
        return None
    res = pc.screen(bars, sigs, cost)
    if res is None:
        return None
    cell = f"{sym}.exogenous_conditioner.{sid}.{sig}"
    mech = mechanism or (f"{sid}.{sig}: China official data ({sid.split('__')[0]}) at an "
                         f"extreme conditions {sym}")
    cand = pc.candidate(seat, sym, "exogenous_conditioner", params, mech,
                        f"exogenous_conditioner {sid}.{sig} -> {sym} thr {thr} side {side}",
                        dict(res))
    cand["required_data"] = [f"desks/mt5/data/lake/series/{sid}.parquet"]
    # `<provider>:<dataset>`: the caller's, else the semantic builder's; never left blank.
    cand["data_source"] = (data_source or SEM_DATA_SOURCE.get(sid.split("__")[0])
                           or f"desk:{sid}")
    # The credit the publisher's terms oblige (NBS: cite 国家统计局网站 and www.stats.gov.cn),
    # with the terms link, carried as a field on the cell itself.
    att = attribution_of(terms_ref or SEM_TERMS_REF.get(sid.split("__")[0], ""))
    if att:
        cand["attribution"] = att
    cand["falsifier"] = (f"{sid}.{sig} at |z| >= {thr} carries no measurable relation to "
                         f"{sym}'s forward return out of sample")
    return {**res, "cell": cell, "candidate": cand}


def attribution_of(ref_or_url: str) -> dict[str, str] | None:
    """`alt_proxies.attribution_for`, or None when the terms table is unimportable (a missing
    table never invents a credit, and the terms gate has already failed such a source closed)."""
    if not ref_or_url:
        return None
    try:
        from research.alt_proxies import attribution_for
    except Exception:
        return None
    return attribution_for(ref_or_url)


def pack_attribution(pack: dict[str, Any]) -> dict[str, str] | None:
    """The credit a registry pack's cells carry: its own `terms_ref`, else its URL's host."""
    return attribution_of(str(pack.get("terms_ref") or "")) or attribution_of(
        str(pack.get("url") or ""))


def _sem_donate(cands: list[dict[str, Any]], tests_run: int, *, seat: str = SEM_SEAT,
                why: str = "semantic China cells tested; no discovery file carried them this pass"
                ) -> dict[str, Any]:
    """Donate through the door; a pass that donates nothing charges its looks to the side
    ledger so the lifetime trial count never forgets them (one of the two, never both)."""
    res: dict[str, Any] = {"donated": 0, "path": None}
    if cands:
        try:
            from research import proposer_common as pc
            path = pc.donate(seat, cands, max(1, tests_run))
            res = {**pc.donation_counts(), "path": str(path) if path else None}
        except Exception as exc:
            res = {"donated": 0, "path": None,
                   "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    if tests_run > 0 and not res.get("path"):
        row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "source": seat,
               "tests_run": int(tests_run), "by_family": {"exogenous_conditioner": tests_run},
               "why": why}
        try:
            NULL_TRIALS.parent.mkdir(parents=True, exist_ok=True)
            with NULL_TRIALS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            res["null_trials_charged"] = int(tests_run)
        except OSError as exc:
            res["null_trials_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="count the cells this pass would mint and write nothing")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    try:
        doc["semantic"] = semantic_lane(budget_s=a.budget_s * SEM_BUDGET_SHARE,
                                        dry_run=a.dry_run)
    except Exception as exc:                 # one lane's defect never costs the pack report
        doc["semantic"] = {"status": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:200]}"}
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"pack cells: could not write {OUT}: {exc}")
        return 1
    print(f"pack cells: {doc['n_packs']} pack(s), {doc['n_eligible']} eligible, "
          f"{doc['n_reached_this_pass']} reached this pass")
    print(f"  cells emitted this pass {doc['cells_emitted_this_pass']} "
          f"({doc['cells_created_this_pass']} new); registry total "
          f"{doc['cells_emitted_total']}, judged {doc['cells_judged_total']}")
    print(f"  packs with cells {doc['packs_with_cells']}/{doc['n_packs']}, "
          f"with a judged cell {doc['packs_with_a_judged_cell']}")
    for r in doc["packs_at_zero"][:8]:
        print(f"   ZERO {str(r['id'])[:28]:<28} stage={r['stage']:<14} {r['reason'][:58]}")
    w = doc.get("world") or {}
    if w:
        print(f"  world grounds {w['n_grounds']}, {w['n_with_documents']} holding "
              f"{w['n_documents']} document(s); with cells {w['grounds_with_cells']}, with a "
              f"judged cell {w['grounds_with_a_judged_cell']}")
        print(f"   this pass: {w['grounds_reached_this_pass']} ground(s), "
              f"{w['cells_emitted_this_pass']} cell(s) ({w['cells_created_this_pass']} new), "
              f"{w['discoveries_this_pass']} discovery(ies); backlog "
              f"{w['backlog_with_documents_and_no_cell']}")
        eu = w.get("europe") or {}
        print(f"   EUROPE {eu.get('regions')}: grounds {eu.get('grounds')}, documents "
              f"{eu.get('documents')}, cells emitted {eu.get('cells_emitted')}, judged "
              f"{eu.get('cells_judged')}")
        for reg, row in list((w.get("by_region") or {}).items())[:8]:
            print(f"    {reg:<18} grounds {row['grounds']:<5} docs {row['documents']:<6} "
                  f"cells {row['cells_emitted']:<6} judged {row['cells_judged']}")
        m = w.get("mapping") or {}
        print(f"   MAPPED {m.get('grounds_with_documents_now_naming_an_instrument')}/"
              f"{m.get('grounds_with_documents')} grounds holding documents name an instrument; "
              f"by rung {m.get('by_rung')}; still unmapped {m.get('n_still_unmapped')}")
        print(f"   JUDGED regions with a judged cell {w.get('regions_with_a_judged_cell')}; "
              f"without {len(w.get('regions_with_no_judged_cell') or [])}")
        js = w.get("judged_by_stamped_region") or {}
        sp = js.get("spread") or {}
        print(f"   JUDGED BY CELL STAMP {js.get('status')}: "
              f"{sp.get('regions_holding')}/{sp.get('regions_named')} regions hold a judged "
              f"cell, total {sp.get('total')}, evenness {sp.get('evenness')}; "
              f"{js.get('regions_with_a_judged_cell')}")
        for row in (w.get("remaining_ranked_by_documents_held") or [])[:6]:
            print(f"    NEXT {str(row['id'])[:38]:<38} docs {row['n_documents']:<4} "
                  f"{row['region']}")
    jr = doc.get("judged_registers") or {}
    print(f"  JUDGED REGISTERS {jr.get('status')}: {str(jr.get('why'))[:150]}")
    dr = doc.get("drain_reachability") or {}
    print(f"  DRAIN REACH {dr.get('status')}: {dr.get('counts')}")
    sem = doc.get("semantic") or {}
    print(f"  SEMANTIC (China official): tests {sem.get('tests_run')}, proposed "
          f"{sem.get('proposed')}, donation {sem.get('donation')}; "
          + ", ".join(f"{k}={v.get('status')}" for k, v in (sem.get('packs') or {}).items()))
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
