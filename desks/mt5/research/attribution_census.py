"""ATTRIBUTION CENSUS -- who produced every cell, from which region, and what the denominator
honestly is once the ones that cannot be traced are named rather than left silent.

    python desks/mt5/research/attribution_census.py --once --budget-s 240
    python desks/mt5/research/attribution_census.py --once --backfill --budget-s 600

THE STATE THIS CLOSES (measured on the trading box 2026-09-23). `PRODUCTIVITY_CENSUS.json`
attributed 3,663 of 3,862 unique cells to nobody and 33 of 58 certificates to nobody, so the
regional scoreboard read `Europe: 1,973 sources visited, 0 unique cells`. Europe was not barren;
its cells could not be traced back. The lineage was never missing -- 26,199 of 27,307 candidates
carry a `source_id`, 23,239 a `discovery_id`, and `sources.country` knows the ground -- but
nothing joined them, so every reader re-derived the join and each got a different answer.

THE FIX IS AT BIRTH, NOT BY SWEEP. `libs/research/attribution.py` is the ONE helper;
`libs/moat/registry.py` calls it inside `enqueue_candidate` and `record_discovery`, the two doors
every cell and discovery comes through, so a producer that lands next month inherits the stamp
without its author having read either file. This organ does the three things a birth stamp cannot
do by itself:

    MEASURE    coverage of both tables, before and after, by producer and by region
    BACKFILL   what the existing lineage still holds (source country, parent discovery,
               generator, origin) -- a one-time recovery, not a standing mechanism
    DECLARE    every row the lineage cannot reach as UNATTRIBUTABLE with the reason, so the
               denominator is honest: an explicit 3,663 of 3,663 with a named exclusion beats an
               unexplained 94% (the same discipline `certificate_truth.UNIDENTIFIABLE` uses)

CERTIFICATES ARE ATTRIBUTED BY JOIN, NEVER BY WRITE. `reports/UNIVERSAL_SURVIVORS.json` is
written by the sealed gauntlet and this module never touches it: a certificate is attributed here
by joining its cell key to the now-stamped candidate row, and the result is published in this
artifact. A certificate whose key reaches no candidate is UNATTRIBUTABLE and is counted as such.

Artifact: `desks/mt5/reports/ATTRIBUTION_COVERAGE.json`, every run.
Clock:    `hourly_cycle:attribution_census`.
Consumers: `desks/mt5/research/productivity_census.py` (the regional scoreboard reads the stamped
columns instead of re-deriving a region per producer), `scripts/check_birth_obligations.py`
(the `attribution` axis fails on a row born after the obligation date with no producer stamp).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import attribution as A  # noqa: E402

REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
OUT = DESK / "reports" / "ATTRIBUTION_COVERAGE.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"

#: Rows updated per backfill transaction. Bounded so an interrupted pass still commits progress
#: and the next pass continues from it -- the backfill is idempotent by construction.
CHUNK = 2_000

LAW = ("EVERY CELL CARRIES ITS PRODUCER AND, WHERE THE PRODUCER BELONGS TO ONE, ITS REGION -- "
       "stamped by the creating organ through libs/research/attribution.py, never inferred by a "
       "later sweep. A row the lineage cannot reach is UNATTRIBUTABLE with its reason, so the "
       "denominator is honest rather than quietly smaller (L1.28a).")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _connect(db: Path, *, write: bool) -> sqlite3.Connection | None:
    """The registry, or None when it cannot be opened -- UNMEASURED, never an empty census."""
    try:
        if write:
            conn = sqlite3.connect(str(db), timeout=30)
        else:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _has_columns(conn: sqlite3.Connection, table: str) -> bool:
    try:
        cols = {str(r[1]) for r in conn.execute(f"pragma table_info({table})")}
    except sqlite3.Error:
        return False
    return {A.PRODUCER_FIELD, A.REGION_FIELD, A.ROUTE_FIELD} <= cols


def measure(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    """Coverage of one table from the stamped columns alone: rows, attributed, regional, and the
    two DECLARED verdicts kept apart so a reader never has to guess which a gap was."""
    if not _has_columns(conn, table):
        return {"available": False,
                "why": f"{A.UNMEASURED}: {table} carries no attribution columns yet "
                       f"(libs/moat/registry.EXTENSIONS adds them on the next connect())"}
    out: dict[str, Any] = {"available": True, "rows": 0, "attributed": 0,
                           "unattributable_producer": 0, "unstamped": 0,
                           "regional": 0, "not_regional": 0, "unattributable_region": 0,
                           "by_region": {}, "by_producer_top": {}}
    regions = set(A.REGIONS)
    per_region: dict[str, int] = {}
    per_producer: dict[str, int] = {}
    q = (f"select coalesce(nullif({A.PRODUCER_FIELD},''),''), "  # noqa: S608 -- literals only
         f"coalesce(nullif({A.REGION_FIELD},''),''), count(*) from {table} group by 1,2")
    for who, where, n in conn.execute(q):
        n = int(n or 0)
        out["rows"] += n
        if not who:
            out["unstamped"] += n
        elif who == A.UNATTRIBUTABLE:
            out["unattributable_producer"] += n
        else:
            out["attributed"] += n
            per_producer[str(who)] = per_producer.get(str(who), 0) + n
        if where in regions:
            out["regional"] += n
        elif where == A.NOT_REGIONAL:
            out["not_regional"] += n
        else:
            out["unattributable_region"] += n
        per_region[str(where) or A.UNMEASURED] = per_region.get(str(where) or A.UNMEASURED, 0) + n
    out["by_region"] = dict(sorted(per_region.items(), key=lambda kv: -kv[1]))
    out["by_producer_top"] = dict(sorted(per_producer.items(), key=lambda kv: -kv[1])[:40])
    total = out["rows"]
    out["producer_coverage"] = round(out["attributed"] / total, 4) if total else A.UNMEASURED
    out["region_coverage"] = (round((out["regional"] + out["not_regional"]) / total, 4)
                              if total else A.UNMEASURED)
    return out


def unique_cells_by_region(conn: sqlite3.Connection) -> dict[str, Any]:
    """UNIQUE cells per region -- the number the regional scoreboard publishes.

    Unique, not raw: a producer that emitted one rule a thousand times has produced one cell's
    worth of ground, and the scoreboard the principal reads is the unique one.
    """
    if not _has_columns(conn, "research_candidates"):
        return {"available": False, "why": f"{A.UNMEASURED}: no attribution columns"}
    rows = conn.execute(
        f"select coalesce(nullif({A.REGION_FIELD},''),'{A.UNMEASURED}'), "  # noqa: S608
        "count(distinct coalesce(nullif(grid_cell,''), content_hash)) "
        "from research_candidates group by 1 order by 2 desc").fetchall()
    return {"available": True, "basis": "distinct grid_cell, else content_hash",
            "by_region": {str(r[0]): int(r[1] or 0) for r in rows}}


#: A CELL IS JUDGED WHEN A JUDGE RECORDED A VERDICT AGAINST IT. Three registers can carry one and
#: the union is the honest measure -- the same union `pack_cells.JUDGED_SQL` uses, spelled here
#: against the candidate's OWN region stamp rather than against its ground.
#:
#: WHY THAT DIFFERENCE IS THE WHOLE OF STEP 3 (measured 2026-09-23 on the trading box).
#: `PACK_CELLS.json` reported `0 of 14 regions holds a judged cell`, and it was counting judged
#: cells PER GROUND: `sources.source_id -> research_candidates.source_id -> a verdict`. But 1,210
#: of the 1,228 judged candidates were produced by `external`, which carries NO source_id at all,
#: so no ground could ever be credited with them and every region read zero by construction. The
#: cells were judged; the ground join was the wrong key. A cell's REGION is stamped on the cell,
#: so this counts what was actually judged, by the region that actually produced it.
JUDGED_PREDICATE = ("(c.judged_at is not null or coalesce(c.terminal_gate,'') != '' "
                    "or t.candidate_id is not null)")


def judged_by_region(conn: sqlite3.Connection) -> dict[str, Any]:
    """Per-region JUDGED cells, keyed on the cell's own attribution stamp.

    A region with no judged cell cannot contribute an edge however deep its mining goes, so this
    is published beside the unique-cell count and never folded into it.
    """
    if not _has_columns(conn, "research_candidates"):
        return {"available": False, "why": f"{A.UNMEASURED}: no attribution columns"}
    try:
        rows = conn.execute(
            f"select coalesce(nullif(c.{A.REGION_FIELD},''),'{A.UNMEASURED}') r, "  # noqa: S608
            "count(distinct coalesce(nullif(c.grid_cell,''), c.content_hash)) "
            "from research_candidates c left join trials_ledger t on t.candidate_id = c.id "
            f"where {JUDGED_PREDICATE} group by 1 order by 2 desc").fetchall()
    except sqlite3.Error as exc:
        return {"available": False, "why": f"{A.UNMEASURED}: {type(exc).__name__}: {exc}"}
    by = {str(r[0]): int(r[1] or 0) for r in rows}
    out: dict[str, Any] = {"available": True,
                           "basis": "distinct grid_cell else content_hash, over candidates "
                                    "carrying judged_at, a terminal_gate, or a trials_ledger row",
                           "by_region": by, "spread": A.region_spread(by)}
    out["regions_with_a_judged_cell"] = sorted(r for r in A.REGIONS if by.get(r, 0) > 0)
    out["regions_with_no_judged_cell"] = sorted(r for r in A.REGIONS if by.get(r, 0) <= 0)
    return out


# ------------------------------------------------------------------------------- the ratchet
RATCHET = DESK / "reports" / "REGION_RATCHET.json"
#: The two measures this organ ratchets. `scripts/check_region_ratchet.py` reads the same names,
#: and a test pins the two lists equal so the fence can never be checking a measure the organ
#: stopped publishing (that is how a gate goes quietly green on nothing).
MEASURES_ARE: tuple[str, ...] = ("unique_cells", "judged_cells")

RATCHET_LAW = (
    "PER-REGION UNIQUE CELLS AND PER-REGION JUDGED CELLS RATCHET UP ONLY (L1.50). The high-water "
    "mark per region is kept here and never lowered; a region that once held cells and now holds "
    "NONE is a regression and the fence fails on it, as does a fall in the COUNT OF REGIONS THE "
    "DESK NAMES -- a coverage ratio may never be improved by removing a region from the "
    "denominator. A non-zero dip is published as a named regression row rather than failing the "
    "gate, because the unique-cell basis can move under a row without the desk losing ground; the "
    "fall to zero cannot.")


def ratchet(current: dict[str, dict[str, int]], *, path: Path | None = None) -> dict[str, Any]:
    """Update and return the per-region high-water marks. Monotone by construction."""
    out_path = path if path is not None else RATCHET
    try:
        prev = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    prev = prev if isinstance(prev, dict) else {}
    doc: dict[str, Any] = {"at": _now(), "law": RATCHET_LAW, "regions_named": len(A.REGIONS),
                           "regions": list(A.REGIONS), "measures": {}}
    prev_named = int(prev.get("regions_named") or 0)
    doc["regions_named_high_water"] = max(prev_named, len(A.REGIONS))
    doc["regions_named_fell"] = len(A.REGIONS) < prev_named
    fallen_any = bool(doc["regions_named_fell"])
    prev_measures = prev.get("measures")
    prev_measures = prev_measures if isinstance(prev_measures, dict) else {}
    for name, counts in current.items():
        raw_old = prev_measures.get(name)
        old: dict[str, Any] = raw_old if isinstance(raw_old, dict) else {}
        raw_high = old.get("high_water")
        high_prev: dict[str, Any] = raw_high if isinstance(raw_high, dict) else {}
        now = {r: int(counts.get(r) or 0) for r in A.REGIONS}
        high = {r: max(int(high_prev.get(r) or 0), now[r]) for r in A.REGIONS}
        to_zero = sorted(r for r in A.REGIONS if high[r] > 0 and now[r] <= 0)
        dips = [{"region": r, "high_water": high[r], "now": now[r]}
                for r in A.REGIONS if 0 < now[r] < high[r]]
        total_now, total_high = sum(now.values()), max(int(old.get("total_high_water") or 0),
                                                       sum(now.values()))
        fallen_any = fallen_any or bool(to_zero) or total_now < int(old.get(
            "total_high_water") or 0)
        doc["measures"][name] = {
            "current": dict(sorted(now.items(), key=lambda kv: -kv[1])),
            "high_water": high, "fell_to_zero": to_zero, "regressions": dips,
            "total": total_now, "total_high_water": total_high,
            "total_fell": total_now < int(old.get("total_high_water") or 0),
            "spread": A.region_spread(now),
        }
    doc["status"] = "FALLEN" if fallen_any else "OK"
    _atomic(out_path, doc)
    return doc


def producer_region(conn: sqlite3.Connection) -> dict[str, Any]:
    """producer -> the region its OWN rows carry, and how many of them.

    THE MAP THE REGIONAL SCOREBOARD WAS MISSING. `productivity_census.py` resolved a producer's
    region from its NAME, so every producer whose name carries no ground token fell into
    `unattributed` -- 1,521 of 1,586 of them, holding 4,725 unique cells. The registry now knows
    each row's region from its lineage, so the modal region of a producer's rows is the answer
    its name could never give. Ties and thin evidence are visible: `rows` is published beside the
    region so a reader can see what the mode was taken over.
    """
    if not _has_columns(conn, "research_candidates"):
        return {"available": False, "why": f"{A.UNMEASURED}: no attribution columns"}
    best: dict[str, tuple[str, int]] = {}
    q = (f"select {A.PRODUCER_FIELD}, {A.REGION_FIELD}, count(*) "  # noqa: S608 -- literals only
         f"from research_candidates where coalesce({A.PRODUCER_FIELD},'') not in "
         f"('','{A.UNATTRIBUTABLE}') group by 1,2")
    for who, where, n in conn.execute(q):
        w = str(where or A.UNATTRIBUTABLE)
        if w not in A.REGIONS:
            continue                      # a mode is taken over REGIONS; the rest is not a region
        cur = best.get(str(who))
        if cur is None or int(n or 0) > cur[1]:
            best[str(who)] = (w, int(n or 0))
    return {"available": True, "basis": "modal region of the producer's own stamped rows",
            "regions": {k: v[0] for k, v in best.items()},
            "rows": {k: v[1] for k, v in best.items()}}


def _survivors() -> dict[str, Any] | None:
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    surv = doc.get("survivors") if isinstance(doc, dict) else None
    return surv if isinstance(surv, dict) else None


def certificates(conn: sqlite3.Connection) -> dict[str, Any]:
    """Certificates attributed by JOIN to the stamped candidates -- never by writing to the
    sealed authority file, which this module reads and never touches.

    The join keys the gauntlet itself leaves: the certificate's cell key against the candidate's
    id, its `donated_cell` and its `grid_cell`, then the certificate's symbol and family against
    the candidate's own columns. A certificate no key reaches is UNATTRIBUTABLE by name.
    """
    surv = _survivors()
    if surv is None:
        return {"available": False,
                "why": f"{A.UNMEASURED}: {SURVIVORS.name} absent or carries no survivors map"}
    if not _has_columns(conn, "research_candidates"):
        return {"available": False, "why": f"{A.UNMEASURED}: no attribution columns"}
    by_key: dict[str, tuple[str, str]] = {}
    by_sym_fam: dict[str, tuple[str, str]] = {}
    for r in conn.execute(
            f"select id, donated_cell, grid_cell, symbol, family, "  # noqa: S608
            f"{A.PRODUCER_FIELD}, {A.REGION_FIELD} from research_candidates "
            f"where coalesce({A.PRODUCER_FIELD},'') not in ('','{A.UNATTRIBUTABLE}')"):
        pair = (str(r[5]), str(r[6] or A.UNATTRIBUTABLE))
        for k in (r[0], r[1], r[2]):
            if k:
                by_key.setdefault(str(k).strip().lower(), pair)
        if r[3] and r[4]:
            by_sym_fam.setdefault(f"{str(r[3]).lower()}|{str(r[4]).lower()}", pair)
    out: dict[str, Any] = {"available": True, "n": len(surv), "attributed": 0,
                           "unattributable": 0, "by_region": {}, "by_producer": {},
                           "routes": {}, "unattributable_keys": []}
    for key, row in surv.items():
        row = row if isinstance(row, dict) else {}
        raw_spec = row.get("shadow_spec")
        spec: dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
        hit = None
        route = ""
        for cand in (str(key), str(row.get("cell") or ""), str(row.get("hunt") or "")):
            if cand and cand.strip().lower() in by_key:
                hit, route = by_key[cand.strip().lower()], "cell key -> candidate"
                break
        if hit is None:
            sym = str(spec.get("symbol") or row.get("sym") or "").lower()
            fam = str(spec.get("family") or "").lower()
            if sym and fam and f"{sym}|{fam}" in by_sym_fam:
                hit, route = by_sym_fam[f"{sym}|{fam}"], "symbol|family -> candidate"
        if hit is None:
            out["unattributable"] += 1
            out["routes"]["no candidate reaches this certificate"] = out["routes"].get(
                "no candidate reaches this certificate", 0) + 1
            if len(out["unattributable_keys"]) < 40:
                out["unattributable_keys"].append(str(key))
            continue
        out["attributed"] += 1
        out["routes"][route] = out["routes"].get(route, 0) + 1
        out["by_producer"][hit[0]] = out["by_producer"].get(hit[0], 0) + 1
        out["by_region"][hit[1]] = out["by_region"].get(hit[1], 0) + 1
    out["coverage"] = round(out["attributed"] / len(surv), 4) if surv else A.UNMEASURED
    return out


# ----------------------------------------------------------------------------- the backfill
def _countries(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {str(r[0]): str(r[1] or "") for r in
                conn.execute("select source_id, country from sources")}
    except sqlite3.Error:
        return {}


def _discovery_attr(conn: sqlite3.Connection, countries: dict[str, str]
                    ) -> dict[str, A.Attribution]:
    """Every discovery's attribution, computed once so the candidate pass is a dict lookup."""
    out: dict[str, A.Attribution] = {}
    try:
        rows = conn.execute("select discovery_id, generator, origin, source_id from "
                            "discoveries").fetchall()
    except sqlite3.Error:
        return out
    for r in rows:
        sid = str(r["source_id"] or "")
        out[str(r["discovery_id"])] = A.attribute(
            generator=r["generator"], origin=r["origin"],
            source_country=countries.get(sid), source_id=sid or None)
    return out


def backfill(conn: sqlite3.Connection, *, deadline: float) -> dict[str, Any]:
    """Recover from existing lineage what the birth stamp would have written, and DECLARE the
    rest. A one-time recovery: after this, the stamp is written at birth and this pass finds
    nothing to do, which is how it should read on every later hour.

    Idempotent and resumable. A row already carrying a producer is never rewritten -- a stamp
    written by its creator outranks anything recovered here.
    """
    out: dict[str, Any] = {"ran": True, "discoveries": 0, "candidates": 0,
                           "declared_unattributable": 0, "truncated": False,
                           "routes": {}, "why_truncated": ""}
    if not (_has_columns(conn, "discoveries") and _has_columns(conn, "research_candidates")):
        return {"ran": False, "why": f"{A.UNMEASURED}: attribution columns absent"}
    countries = _countries(conn)

    def note(a: A.Attribution) -> None:
        out["routes"][a.route] = out["routes"].get(a.route, 0) + 1
        if a.producer == A.UNATTRIBUTABLE or a.region == A.UNATTRIBUTABLE:
            out["declared_unattributable"] += 1

    # THE SELECTION, AND WHY IT IS A ROWID CURSOR. Rows still unstamped, plus rows whose region
    # the last pass could only declare UNATTRIBUTABLE -- the rule improves (a new regional ground,
    # a producer newly known to be desk machinery) and a row must be allowed to leave the
    # unattributable bucket. Selecting on that predicate with a plain LIMIT would re-read the same
    # rows for ever when they stay unattributable, so the cursor advances on rowid and the pass
    # terminates whatever the rule decides. A row whose CREATOR stamped a producer is never
    # rewritten: its region may be recovered, its producer stands.
    todo = (f"(coalesce({A.PRODUCER_FIELD},'')='' or {A.REGION_FIELD}='{A.UNATTRIBUTABLE}')")

    cursor = 0
    while True:
        rows = conn.execute(
            f"select rowid as rid, discovery_id, generator, origin, source_id "  # noqa: S608
            f"from discoveries where rowid>? and {todo} order by rowid limit {CHUNK}",
            (cursor,)).fetchall()
        if not rows:
            break
        cursor = int(rows[-1]["rid"])
        upd = []
        for r in rows:
            sid = str(r["source_id"] or "")
            a = A.attribute(generator=r["generator"], origin=r["origin"],
                            source_country=countries.get(sid), source_id=sid or None)
            note(a)
            upd.append((a.producer, a.region, a.route, str(r["discovery_id"])))
        conn.executemany(
            f"update discoveries set {A.PRODUCER_FIELD}=?, {A.REGION_FIELD}=?, "  # noqa: S608
            f"{A.ROUTE_FIELD}=? where discovery_id=?", upd)
        conn.commit()
        out["discoveries"] += len(upd)
        if time.monotonic() > deadline:
            out["truncated"] = True
            out["why_truncated"] = "budget reached inside the discovery pass"
            return out

    parents = _discovery_attr(conn, countries)
    cursor = 0
    while True:
        rows = conn.execute(
            f"select rowid as rid, id, generator, origin, department, source_id, "  # noqa: S608
            f"discovery_id, {A.PRODUCER_FIELD} from research_candidates where rowid>? "
            f"and {todo} order by rowid limit {CHUNK}", (cursor,)).fetchall()
        if not rows:
            break
        cursor = int(rows[-1]["rid"])
        upd = []
        for r in rows:
            sid = str(r["source_id"] or "")
            carried = r[A.PRODUCER_FIELD]
            a = A.attribute(producer=None if carried == A.UNATTRIBUTABLE else carried,
                            generator=r["generator"], origin=r["origin"],
                            department=r["department"], source_country=countries.get(sid),
                            source_id=sid or None,
                            parent=parents.get(str(r["discovery_id"] or "")))
            note(a)
            upd.append((a.producer, a.region, a.route, str(r["id"])))
        conn.executemany(
            f"update research_candidates set {A.PRODUCER_FIELD}=?, "  # noqa: S608
            f"{A.REGION_FIELD}=?, {A.ROUTE_FIELD}=? where id=?", upd)
        conn.commit()
        out["candidates"] += len(upd)
        if time.monotonic() > deadline:
            out["truncated"] = True
            out["why_truncated"] = "budget reached inside the candidate pass"
            break
    return out


def run(*, budget_s: float = 240.0, do_backfill: bool = True,
        db: Path | None = None) -> dict[str, Any]:
    """One pass: measure, backfill what lineage holds, measure again, publish both."""
    t0 = time.monotonic()
    path = db if db is not None else REGISTRY
    doc: dict[str, Any] = {"at": _now(), "law": LAW, "rule": A.ATTRIBUTION_RULE,
                           "registry": str(path), "budget_s": budget_s,
                           "birth_obligation_from": A.BIRTH_OBLIGATION_FROM,
                           "helper": "libs/research/attribution.py",
                           "stamped_at_birth_by": ["libs/moat/registry.enqueue_candidate",
                                                   "libs/moat/registry.record_discovery"],
                           "consumers": ["desks/mt5/research/productivity_census.py",
                                         "scripts/check_birth_obligations.py (axis attribution)"]}
    if not path.exists():
        doc["available"] = False
        doc["why"] = f"{A.UNMEASURED}: no registry at {path}"
        return doc
    ro = _connect(path, write=False)
    if ro is None:
        doc["available"] = False
        doc["why"] = f"{A.UNMEASURED}: registry unopenable"
        return doc
    try:
        doc["before"] = {"candidates": measure(ro, "research_candidates"),
                         "discoveries": measure(ro, "discoveries")}
    finally:
        ro.close()
    if do_backfill:
        rw = _connect(path, write=True)
        if rw is None:
            doc["backfill"] = {"ran": False, "why": f"{A.UNMEASURED}: registry not writable"}
        else:
            try:
                doc["backfill"] = backfill(rw, deadline=t0 + max(5.0, 0.8 * budget_s))
            finally:
                rw.close()
    else:
        doc["backfill"] = {"ran": False, "why": "measurement-only pass (--no-backfill)"}
    ro = _connect(path, write=False)
    if ro is None:
        doc["available"] = False
        doc["why"] = f"{A.UNMEASURED}: registry unopenable after backfill"
        return doc
    try:
        doc["after"] = {"candidates": measure(ro, "research_candidates"),
                        "discoveries": measure(ro, "discoveries")}
        doc["unique_cells_by_region"] = unique_cells_by_region(ro)
        doc["judged_cells_by_region"] = judged_by_region(ro)
        doc["producer_region"] = producer_region(ro)
        doc["certificates"] = certificates(ro)
    finally:
        ro.close()
    cells = (doc["unique_cells_by_region"] or {}).get("by_region") or {}
    judged = (doc["judged_cells_by_region"] or {}).get("by_region") or {}
    doc["unique_cells_by_region"]["spread"] = A.region_spread(cells)
    # THE RATCHET FOLLOWS THE REGISTRY IT MEASURED, NEVER THE PRODUCTION PATH BY DEFAULT. A pass
    # run against another database -- a test fixture, a restored backup, a second box's copy -- was
    # writing its counts into the desk's real high-water file, which is how a synthetic registry of
    # three rows reported every region as having fallen to zero (observed the hour this landed,
    # R0748's hazard in a new place). An off-registry run is now self-contained.
    rpath = RATCHET if path == REGISTRY else path.parent / RATCHET.name
    doc["ratchet"] = ratchet(dict(zip(MEASURES_ARE, (cells, judged), strict=True)), path=rpath)
    doc["available"] = True
    before = doc["before"]["candidates"]
    after = doc["after"]["candidates"]
    doc["delta"] = {
        "producer_coverage": [before.get("producer_coverage"), after.get("producer_coverage")],
        "region_coverage": [before.get("region_coverage"), after.get("region_coverage")],
        "attributed_candidates": [before.get("attributed"), after.get("attributed")],
        "unstamped_candidates": [before.get("unstamped"), after.get("unstamped")]}
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    return doc


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    out = path if path is not None else OUT
    _atomic(out, doc)
    try:
        from libs.ops import events
        events.emit("attribution_census", rows=doc.get("after", {}).get(
            "candidates", {}).get("rows"),
            producer_coverage=doc.get("after", {}).get("candidates", {}).get(
                "producer_coverage"))
    except Exception:                                        # pragma: no cover - optional organ
        pass
    return out


def render(doc: dict[str, Any]) -> list[str]:
    if not doc.get("available"):
        return [f"ATTRIBUTION CENSUS  {doc.get('why')}"]
    b, a = doc["before"]["candidates"], doc["after"]["candidates"]
    cert = doc.get("certificates") or {}
    lines = [f"ATTRIBUTION CENSUS  {doc['at']}",
             f"  candidates  {a.get('rows')} rows: producer {b.get('producer_coverage')} -> "
             f"{a.get('producer_coverage')}, region {b.get('region_coverage')} -> "
             f"{a.get('region_coverage')}",
             f"  declared    {a.get('unattributable_producer')} UNATTRIBUTABLE producer, "
             f"{a.get('unattributable_region')} UNATTRIBUTABLE region, "
             f"{a.get('not_regional')} NOT_REGIONAL",
             f"  backfill    {json.dumps(doc.get('backfill', {}).get('candidates'))} candidates, "
             f"{json.dumps(doc.get('backfill', {}).get('discoveries'))} discoveries"]
    if cert.get("available"):
        lines.append(f"  certs       {cert.get('attributed')}/{cert.get('n')} attributed "
                     f"(coverage {cert.get('coverage')})")
    cells = (doc.get("unique_cells_by_region") or {}).get("by_region") or {}
    top = ", ".join(f"{k}={v}" for k, v in list(cells.items())[:8])
    lines.append(f"  unique cells by region  {top}")
    for name in ("unique_cells_by_region", "judged_cells_by_region"):
        sp = (doc.get(name) or {}).get("spread") or {}
        if sp:
            lines.append(f"  spread {name.split('_')[0]:<6}  {sp.get('regions_holding')}/"
                         f"{sp.get('regions_named')} regions hold cells, min {sp.get('min')} "
                         f"median {sp.get('median')} max {sp.get('max')}, evenness "
                         f"{sp.get('evenness')}; empty: {', '.join(sp.get('regions_empty') or [])}")
    rat = doc.get("ratchet") or {}
    if rat:
        fell = {k: v.get("fell_to_zero") for k, v in (rat.get("measures") or {}).items()
                if v.get("fell_to_zero")}
        lines.append(f"  ratchet     {rat.get('status')}"
                     + (f" -- REGIONS FELL TO ZERO: {fell}" if fell else ""))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Attribution at birth: producer and region per cell")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--backfill", action="store_true",
                    help="recover attribution from existing lineage (the default on a clock)")
    ap.add_argument("--no-backfill", action="store_true", help="measure only")
    args = ap.parse_args(argv)
    doc = run(budget_s=float(args.budget_s), do_backfill=not args.no_backfill)
    write(doc)
    for line in render(doc):
        print(line)
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
