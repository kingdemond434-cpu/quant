"""REGIONAL PARITY -- no region absent, every region at the same DEPTH, compute by coverage debt.

THE LAW (docs/LAWS.md 5n, principal 2026-09-19, permanent). Every world region receives the same
depth of civilization -- the ten source layers in the native language, own mechanics, own
calendars, own rule states, own transmission map -- and compute is NOT equal: it follows

    Priority = P(useful) x Orthogonality x InformationGain x CoverageDebt
               / (Compute + DataCost + TrialBurden)

where the coverage-debt bonus keeps neglected regions discovering and the expected-value terms
keep low-information areas from wasting resources. The parity fence turns the desk red when a
region the packs name has no resident, no discovery in its trailing window, or no candidate in
its lattice.

WHAT THIS MODULE IS. The PURE half of that law: it opens no socket, writes no file and imports
no desk organ. It reads four things and names what it cannot read:

  * the forest federation (`libs.research.forests`) -- WHICH regions exist and which packs and
    countries each one draws on;
  * the country packs through `libs.research.country_lab` -- how DEEP each region's packs are,
    measured by the framework's own layer inventory and row counts, never by a pack's claim;
  * the moat registry, through a connection the CALLER hands it -- whether a resident is alive
    (`workers`), whether anything was discovered in the trailing window (`sources`,
    `discoveries`) and whether any candidate reached the lattice (`discoveries` cell counters,
    `research_candidates`);
  * the forest reports directory -- a resident's last completed pass.

`desks/mt5/research/research_roi.py` folds `priority` into `forest_allocation.json` (two-sided,
scout floor kept) and `scripts/check_regional_parity.py` is the fence. Both are consumers; this
module decides nothing about compute on its own.

UNMEASURED IS A VALUE (L1.28a). A registry that cannot be opened, a pack that does not resolve,
a region whose ground is a LAYER of the world rather than a place (the five global forests) --
each reads UNMEASURED by name and holds the MIDDLE of every term it feeds, never zero and never
the best. A region is flagged only on a MEASURED absence.

DEPTH IS THE FRAMEWORK'S VERDICT, NOT THE PACK'S. `pack_depth` counts what
`country_lab.CountryPack` actually carries after coercion and what `layer_inventory` actually
tags. A pack whose sources reach the framework untagged reads as UNMAPPED here, and
`untagged_sources` says so -- that is work for the pack's author, and hiding it behind the pack's
own module-level tables would make the parity number a description of this module's charity
rather than of the country.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research import country_lab as CL
from libs.research import equivalence_ontology as EQ
from libs.research import forests as F

__all__ = [
    "DEBT_WEIGHTS",
    "DEPTH_TARGETS",
    "DISCOVERY_WINDOW_DAYS",
    "EQUIVALENCE_RULE",
    "FLAGS",
    "LATTICE_TARGET",
    "RESIDENT_STALE_HOURS",
    "RULE",
    "UNMEASURED",
    "PackDepth",
    "RegionDepth",
    "classes_declared",
    "clip",
    "coverage_debt",
    "depth_score",
    "equivalence_parity",
    "flags_for",
    "median",
    "pack_declarations",
    "pack_depth",
    "parity_report",
    "priority_of",
    "proof_index",
    "region_depth",
    "region_signals",
    "region_tokens",
    "regional_ids",
]

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: Where a forest resident writes `FOREST_<ID>.json` after every pass.
REPORTS_DIR: Path = DESK / "reports"

UNMEASURED = "UNMEASURED"
#: The trailing window of the discovery half of coverage -- the country lab's own constant.
DISCOVERY_WINDOW_DAYS = CL.DISCOVERY_WINDOW_DAYS
#: A resident that has neither heartbeated nor written a report inside this many hours is not
#: present. A forest pass is budgeted at 3000 s and heartbeats at start and end; three hours
#: catches a dead resident inside the fence's own cadence without flagging a long pass.
RESIDENT_STALE_HOURS = 3.0
#: Lattice candidates at which the lattice term of the debt reaches zero.
LATTICE_TARGET = 20
#: Two-sided clip on the factors derived here, symmetric about 1.0 (GROWTH_GOVERNANCE Rule 2).
FACTOR_CLIP = (0.5, 2.0)

#: THE STANDING DEPTH RULE, as targets. A pack at or above every one of them scores 1.0; the
#: score is the mean of the eight capped ratios so no single table can buy the rest.
DEPTH_TARGETS: dict[str, float] = {
    "actors": 12.0, "domains": 10.0, "edges": 8.0, "layers": 10.0, "terms": 40.0,
    "datasets": 8.0, "eras": 4.0, "instruments": 6.0,
}
#: How the four debt terms are weighed. Layers carry the most because they are the half of the
#: depth rule a scout cannot fake by typing; the resident carries the least because a resident
#: with nothing to read produces nothing anyway.
DEBT_WEIGHTS: dict[str, float] = {"layers": 0.35, "discovery": 0.25, "lattice": 0.25,
                                  "resident": 0.15}
#: The four things the fence turns red on, exactly as the law names them, plus the one the
#: portable half can measure with no state at all.
FLAGS: tuple[str, ...] = ("NO_PACK", "NO_RESIDENT", "NO_DISCOVERY", "NO_LATTICE_CANDIDATE",
                          "DEPTH_BELOW_HALF_MEDIAN")

RULE = ("no region absent, every region at the same depth; compute follows Priority = "
        "P(useful) x Orthogonality x InformationGain x CoverageDebt / (Compute + DataCost + "
        "TrialBurden); a region with no resident, no discovery in its trailing window or no "
        "candidate in its lattice is a defect, and UNMEASURED holds the middle, never zero")


# --------------------------------------------------------------------------- small helpers
def clip(x: float, lo: float = FACTOR_CLIP[0], hi: float = FACTOR_CLIP[1]) -> float:
    return max(lo, min(hi, float(x)))


def median(values: Iterable[float]) -> float | None:
    got = sorted(float(v) for v in values)
    if not got:
        return None
    n = len(got)
    mid = n // 2
    return got[mid] if n % 2 else 0.5 * (got[mid - 1] + got[mid])


def _mean(values: Iterable[float]) -> float | None:
    got = [float(v) for v in values]
    return (sum(got) / len(got)) if got else None


def _parse_stamp(text: Any) -> datetime | None:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        got = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo is not None else got.replace(tzinfo=UTC)


def _age_hours(stamp: Any, now: datetime) -> float | None:
    got = _parse_stamp(stamp)
    if got is None:
        return None
    return (now - got).total_seconds() / 3600.0


def regional_ids() -> tuple[str, ...]:
    """The regional forests, in registry order -- the regions the packs name."""
    return tuple(f.id for f in F.REGIONAL_FORESTS)


def region_tokens(forest_id: str) -> frozenset[str]:
    """Every lower-case token the registry may stamp on a row that belongs to this forest: the
    forest id, its ISO-2 countries, its pack directory codes and its deep-forest grounds."""
    f = F.forest(forest_id)
    toks = {f.id.lower(), f.name.lower()}
    toks |= {c.lower() for c in f.countries}
    toks |= {p.lower() for p in f.packs}
    toks |= {g.lower() for g in f.grounds}
    return frozenset(t for t in toks if t)


# --------------------------------------------------------------------------- depth
@dataclass(frozen=True)
class PackDepth:
    """One pack, measured by what the framework can read out of it."""

    code: str
    resolved: bool = False
    actors: int = 0
    domains: int = 0
    edges: int = 0
    terms: int = 0
    datasets: int = 0
    eras: int = 0
    instruments: int = 0
    languages: int = 0
    layers_mapped: int = 0            # MAPPED or ABSENT_DECLARED
    layers_unverified: int = 0        # declared, nothing fetched yet
    layers_unmapped: int = 0          # no source and no declared absence
    untagged_sources: int = 0
    pit_feasible_share: float | None = None
    fatal: tuple[str, ...] = ()
    score: float | None = None
    why: str = ""

    @property
    def layers_declared(self) -> int:
        return self.layers_mapped + self.layers_unverified

    def as_row(self) -> dict[str, Any]:
        return {"code": self.code, "resolved": self.resolved, "actors": self.actors,
                "domains": self.domains, "edges": self.edges, "terms": self.terms,
                "datasets": self.datasets, "eras": self.eras, "instruments": self.instruments,
                "languages": self.languages, "layers_mapped": self.layers_mapped,
                "layers_unverified": self.layers_unverified,
                "layers_unmapped": self.layers_unmapped,
                "layers_declared": self.layers_declared,
                "untagged_sources": self.untagged_sources,
                "pit_feasible_share": self.pit_feasible_share, "fatal": list(self.fatal),
                "score": self.score, "why": self.why}


def depth_score(d: PackDepth) -> float:
    """The mean of the eight capped ratios against `DEPTH_TARGETS`, in [0, 1]."""
    have = {"actors": d.actors, "domains": d.domains, "edges": d.edges,
            "layers": d.layers_declared, "terms": d.terms, "datasets": d.datasets,
            "eras": d.eras, "instruments": d.instruments}
    ratios = [min(1.0, float(have[k]) / t) for k, t in DEPTH_TARGETS.items() if t > 0]
    return round(sum(ratios) / len(ratios), 6) if ratios else 0.0


def pack_depth(pack: CL.CountryPack | None, code: str = "",
               reg: Mapping[str, Mapping[str, Any]] | None = None) -> PackDepth:
    """Measure one pack. A pack that does not resolve is UNMEASURED by name, never a zero row."""
    if pack is None:
        return PackDepth(code=code or "?", resolved=False,
                         why=f"{UNMEASURED}: no country pack resolves for {code!r}")
    inventory = CL.layer_inventory(pack.code, pack=pack)
    mapped = unverified = unmapped = 0
    for layer in CL.SOURCE_LAYERS:
        rows = inventory[layer]
        if any(r.get("absent_reason") for r in rows) or any(r.get("verified") for r in rows):
            mapped += 1
        elif rows:
            unverified += 1
        else:
            unmapped += 1
    terms = {t for words in dict(pack.terminology).values() for t in words}
    pit = [bool(ds.pit_feasible) for ds in pack.datasets]
    try:
        problems = CL.validate_pack(pack, reg)
    except Exception as exc:                    # a pack that breaks the validator is a defect
        problems = [f"pack row: FAILED validate_pack raised {type(exc).__name__}: {exc}"]
    fatal = tuple(CL.fatal_problems(problems))
    d = PackDepth(code=pack.code, resolved=True, actors=len(pack.actors),
                  domains=len(pack.domains), edges=len(pack.transmission_edges_seed),
                  terms=len(terms), datasets=len(pack.datasets), eras=len(pack.policy_eras),
                  instruments=len(pack.executable_instruments),
                  languages=len(pack.native_languages), layers_mapped=mapped,
                  layers_unverified=unverified, layers_unmapped=unmapped,
                  untagged_sources=len(inventory["UNTAGGED"]),
                  pit_feasible_share=(round(sum(pit) / len(pit), 4) if pit else None),
                  fatal=fatal)
    score = depth_score(d)
    why = (f"{score:.3f}: {mapped} mapped + {unverified} declared-unverified + {unmapped} "
           f"unmapped layers; {len(pack.actors)} actors, {len(pack.domains)} domains, "
           f"{len(pack.transmission_edges_seed)} edges, {len(terms)} terms")
    if inventory["UNTAGGED"]:
        why += (f"; {len(inventory['UNTAGGED'])} source(s) reach the framework UNTAGGED -- "
                f"work for the pack's author, not coverage")
    if fatal:
        why += f"; FATAL: {fatal[0]}"
    return PackDepth(**{**d.__dict__, "score": score, "why": why})


@dataclass(frozen=True)
class RegionDepth:
    """One forest's depth: its packs measured, its missing packs named."""

    forest: str
    kind: str = "regional"
    packs: tuple[PackDepth, ...] = ()
    missing: tuple[str, ...] = ()
    package: str = ""
    score_mean: float | None = None
    score_max: float | None = None
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.score_mean is not None

    def as_row(self) -> dict[str, Any]:
        return {"forest": self.forest, "kind": self.kind,
                "packs": [p.as_row() for p in self.packs], "missing": list(self.missing),
                "package": self.package, "score_mean": self.score_mean,
                "score_max": self.score_max, "why": self.why}


def region_depth(forest_id: str, *,
                 resolver: Callable[[str], CL.CountryPack | None] | None = None,
                 reg: Mapping[str, Mapping[str, Any]] | None = None) -> RegionDepth:
    """Depth of one forest = its resolvable packs measured; the ones that do not resolve named.

    A forest with a dedicated region PACKAGE and no packs (Japan) is UNMEASURED here rather than
    zero: the package is a department the country lab does not read, and pricing it at zero
    would defund the deepest civilization on the desk for the crime of predating the packs.
    """
    f = F.forest(forest_id)
    resolve = resolver or CL.resolve_pack
    rows: list[PackDepth] = []
    missing: list[str] = []
    for code in f.packs:
        try:
            got = resolve(code)
        except Exception:
            got = None
        d = pack_depth(got, code, reg)
        if d.resolved:
            rows.append(d)
        else:
            missing.append(code)
    scores = [p.score for p in rows if p.score is not None]
    if f.kind != "regional":
        why = f"{UNMEASURED}: a global forest's ground is a layer of the world, not a place"
        return RegionDepth(forest=f.id, kind=f.kind, package=f.package, why=why)
    if not rows:
        why = (f"{UNMEASURED}: no country pack resolves for {f.id}"
               + (f" (declared but absent: {missing})" if missing else "")
               + (f"; the region runs as the package {f.package}" if f.package else
                  "; NO PACK AND NO PACKAGE"))
        return RegionDepth(forest=f.id, kind=f.kind, missing=tuple(missing),
                           package=f.package, why=why)
    mean = _mean(scores)
    why = (f"{len(rows)} pack(s) measured, mean depth {mean:.3f}, max {max(scores):.3f}"
           + (f"; declared but absent: {missing}" if missing else ""))
    return RegionDepth(forest=f.id, kind=f.kind, packs=tuple(rows), missing=tuple(missing),
                       package=f.package, score_mean=round(float(mean or 0.0), 6),
                       score_max=round(max(scores), 6), why=why)


# --------------------------------------------------------------------------- live signals
def _worker_ids(forest_id: str) -> tuple[str, ...]:
    """The heartbeat ids a resident for this forest may write under: its own forest id, and the
    department id of the task it rides (`RIDES`), read from the task name rather than typed."""
    fid = F.forest(forest_id).id
    task = F.resident_task(fid)
    suffix = task.rsplit("-", 1)[-1].lower()
    ids = [f"forest:{fid}", f"dept:{fid}", f"dept:{suffix}"]
    return tuple(dict.fromkeys(ids))


def _count(conn: Any, sql: str, params: Sequence[Any]) -> int | None:
    try:
        row = conn.execute(sql, tuple(params)).fetchone()
    except Exception:
        return None
    if row is None:
        return 0
    try:
        return int(row[0] or 0)
    except (TypeError, ValueError, IndexError):
        return None


@contextmanager
def _regional_census(conn: Any, cutoff: str) -> Iterator[dict[str, str] | None]:
    """One exact SQL census per report, rather than rescanning millions of rows per forest.

    Native SQLite LIKE/IN semantics and missing-table/column UNMEASURED results
    are retained. Temporary tables live inside a private rolled-back savepoint.
    """
    if not isinstance(conn, sqlite3.Connection):
        yield None
        return
    name = "region_census_" + uuid.uuid4().hex
    conn.execute(f"SAVEPOINT {name}")
    tables: dict[str, str] = {}
    try:
        queries = {
            "sources": ("SELECT lower(COALESCE(country,'')) country, COUNT(*) n "
                        "FROM sources WHERE first_seen>=? "
                        "GROUP BY lower(COALESCE(country,''))", (cutoff,)),
            "discoveries_total": ("SELECT generator, COUNT(*) n FROM discoveries "
                                  "GROUP BY generator", ()),
            "discoveries_window": ("SELECT generator, COUNT(*) n FROM discoveries "
                                   "WHERE created_at>=? GROUP BY generator", (cutoff,)),
            "cells": ("SELECT generator, COUNT(*) n FROM discoveries WHERE "
                      "COALESCE(generated_cells,0)+COALESCE(compiled_cells,0)+"
                      "COALESCE(queued_cells,0)+COALESCE(tested_cells,0)>0 "
                      "GROUP BY generator", ()),
            "candidates": ("SELECT generator, COUNT(*) n FROM research_candidates "
                           "GROUP BY generator", ()),
        }
        # Three discovery metrics share the same grouping population. Scan it
        # once while keeping absent columns independently UNMEASURED.
        try:
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(discoveries)")}
            expressions = {"discoveries_total": "COUNT(*)"}
            parameters: list[Any] = []
            if "created_at" in columns:
                expressions["discoveries_window"] = (
                    "SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END)")
                parameters.append(cutoff)
            if {"generated_cells", "compiled_cells", "queued_cells", "tested_cells"} <= columns:
                expressions["cells"] = (
                    "SUM(CASE WHEN COALESCE(generated_cells,0)+COALESCE(compiled_cells,0)+"
                    "COALESCE(queued_cells,0)+COALESCE(tested_cells,0)>0 THEN 1 ELSE 0 END)")
            grouped = name + "_discovery_grouped"
            selection = ", ".join(f"{expression} AS {metric}"
                                  for metric, expression in expressions.items())
            # UUID table names and the expression dictionary above are internal constants.
            conn.execute(f"CREATE TEMP TABLE {grouped} AS SELECT generator, {selection} "  # noqa: S608
                         "FROM discoveries GROUP BY generator", parameters)
            for metric in ("discoveries_total", "discoveries_window", "cells"):
                queries.pop(metric)
                if metric in expressions:
                    table = name + "_" + metric
                    conn.execute(f"CREATE TEMP VIEW {table} AS "  # noqa: S608
                                 f"SELECT generator, {metric} AS n FROM {grouped}")
                    tables[metric] = table
        except sqlite3.Error:
            # Preserve independent query failures on incomplete older schemas.
            pass
        for metric, (query, params) in queries.items():
            table = name + "_" + metric
            try:
                conn.execute(f"CREATE TEMP TABLE {table} AS {query}", params)
            except sqlite3.Error:
                continue
            tables[metric] = table
        yield tables
    finally:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")


def _census_count(conn: Any, census: Mapping[str, str], metric: str,
                  patterns: Sequence[str], column: str = "n") -> int | None:
    table = census.get(metric)
    if table is None:
        return None
    if metric == "sources":
        clause = "country IN (" + ",".join("?" for _ in patterns) + ")"
    else:
        clause = " OR ".join("generator LIKE ?" for _ in patterns)
    return _count(conn,  # identifiers are private UUID tables and fixed metric columns
                  f"SELECT COALESCE(SUM({column}),0) FROM {table} WHERE ({clause})",  # noqa: S608
                  patterns)


def region_signals(forest_id: str, conn: Any = None, *, now: datetime | None = None,
                   window_days: int = DISCOVERY_WINDOW_DAYS,
                   reports_dir: Path | None = None,
                   stale_hours: float = RESIDENT_STALE_HOURS,
                   _census: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Resident present? Discovery in the trailing window? Candidates in the lattice?

    Every answer is an int or bool when the instrument could be read and None (UNMEASURED) with
    a reason when it could not. A readable table that holds nothing is a MEASURED zero.
    """
    fid = F.forest(forest_id).id
    at = now or datetime.now(tz=UTC)
    cutoff = (at - timedelta(days=int(window_days))).isoformat()
    toks = sorted(region_tokens(fid))
    out: dict[str, Any] = {"forest": fid, "window_days": int(window_days), "tokens": toks,
                           "resident": None, "resident_why": "", "heartbeat_age_h": None,
                           "report_age_h": None, "sources_window": None,
                           "discoveries_window": None, "discoveries_total": None,
                           "lattice_candidates": None, "unmeasured": []}
    # ---- the resident: a heartbeat in the registry, or a fresh report on disk ----------------
    rdir = reports_dir if reports_dir is not None else REPORTS_DIR
    report = rdir / F.forest(fid).report_name
    report_age: float | None = None
    report_readable = False
    try:
        doc = json.loads(report.read_text(encoding="utf-8-sig"))
        report_readable = True
        report_age = _age_hours(doc.get("at") if isinstance(doc, Mapping) else None, at)
    except (OSError, ValueError):
        report_readable = False
    out["report_age_h"] = None if report_age is None else round(report_age, 2)
    hb_age: float | None = None
    hb_readable = False
    if conn is not None:
        ids = _worker_ids(fid)
        marks = ",".join("?" for _ in ids)
        try:                     # only the "?" placeholder list is interpolated, never a value
            rows = conn.execute(f"SELECT worker_id, status, last_seen FROM workers WHERE "  # noqa: S608
                                f"worker_id IN ({marks})", ids).fetchall()
            hb_readable = True
        except Exception:
            rows = []
        for r in rows:
            try:
                status, seen = str(r["status"]), r["last_seen"]
            except (TypeError, KeyError, IndexError):
                status, seen = str(r[1]), r[2]
            age = _age_hours(seen, at)
            if age is not None and status == "running" and (hb_age is None or age < hb_age):
                hb_age = age
    out["heartbeat_age_h"] = None if hb_age is None else round(hb_age, 2)
    fresh_hb = hb_age is not None and hb_age <= float(stale_hours)
    fresh_report = report_age is not None and report_age <= float(stale_hours)
    if fresh_hb or fresh_report:
        out["resident"] = True
        out["resident_why"] = ("heartbeat" if fresh_hb else "report") + " inside the window"
    elif hb_readable or rdir.exists():
        out["resident"] = False
        out["resident_why"] = (
            f"no running heartbeat under {list(_worker_ids(fid))} "
            f"{'' if hb_readable else '(workers table unreadable) '}and "
            + (f"{report.name} is {report_age:.1f}h old" if report_age is not None else
               (f"{report.name} carries no readable stamp" if report_readable else
                f"{report.name} is absent")))
    else:
        out["resident_why"] = (f"{UNMEASURED}: neither the registry nor {rdir} is readable")
        out["unmeasured"].append("resident")
    # ---- discovery: scouts adding sources, and forest-generated discoveries -----------------
    if conn is None:
        out["unmeasured"].extend(["discovery", "lattice"])
        out["why"] = f"{UNMEASURED}: no registry connection; discovery and lattice unread"
        return out
    # Only "?" placeholder lists and the OR-joined `generator LIKE ?` clause are interpolated
    # below; every value travels as a bound parameter, which is what S608 cannot see.
    marks = ",".join("?" for _ in toks)
    pats = [f"{fid}:%", f"%:{fid}:%", f"%:{fid}"]
    if _census is not None:
        out["sources_window"] = _census_count(conn, _census, "sources", toks)
        out["discoveries_window"] = _census_count(
            conn, _census, "discoveries_window", pats)
        out["discoveries_total"] = _census_count(conn, _census, "discoveries_total", pats)
        cells = _census_count(conn, _census, "cells", pats)
        cands = _census_count(conn, _census, "candidates", pats)
    else:
        out["sources_window"] = _count(
            conn, f"SELECT COUNT(*) FROM sources WHERE lower(COALESCE(country,'')) IN ({marks}) "  # noqa: S608
                  f"AND first_seen >= ?", [*toks, cutoff])
        pats = [f"{fid}:%", f"%:{fid}:%", f"%:{fid}"]
        gen = " OR ".join("generator LIKE ?" for _ in pats)
        out["discoveries_window"] = _count(
            conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen}) AND created_at >= ?",  # noqa: S608
            [*pats, cutoff])
        out["discoveries_total"] = _count(
            conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen})", pats)  # noqa: S608
        # Lattice: discoveries that produced cells plus candidates the forest generated.
        cells = _count(
            conn, f"SELECT COUNT(*) FROM discoveries WHERE ({gen}) AND (COALESCE(generated_cells,0)"  # noqa: S608
                  f" + COALESCE(compiled_cells,0) + COALESCE(queued_cells,0) + "
                  f"COALESCE(tested_cells,0)) > 0", pats)
        cands = _count(conn, f"SELECT COUNT(*) FROM research_candidates WHERE ({gen})", pats)  # noqa: S608
    if cells is None and cands is None:
        out["unmeasured"].append("lattice")
    else:
        out["lattice_candidates"] = int(cells or 0) + int(cands or 0)
    if out["sources_window"] is None and out["discoveries_window"] is None:
        out["unmeasured"].append("discovery")
    return out


# --------------------------------------------------------------------------- the debt
def _term_or_middle(value: float | None, name: str, unmeasured: list[str]) -> float:
    if value is None:
        unmeasured.append(name)
        return 0.5
    return max(0.0, min(1.0, float(value)))


def coverage_debt(region: str, *, depth: RegionDepth | None = None,
                  signals: Mapping[str, Any] | None = None, conn: Any = None,
                  now: datetime | None = None, window_days: int = DISCOVERY_WINDOW_DAYS,
                  resolver: Callable[[str], CL.CountryPack | None] | None = None,
                  reports_dir: Path | None = None) -> dict[str, Any]:
    """How much of the standing depth rule this region still owes, in [0, 1], term by term.

    `layers` rises with every UNMAPPED layer (a declared-but-unverified layer counts half);
    `discovery` is 1 when nothing was added in the trailing window and falls with the rate;
    `lattice` is 1 when no candidate reached the lattice and falls toward `LATTICE_TARGET`;
    `resident` is 1 when nobody is running the forest. An UNMEASURED term holds 0.5 by name.
    """
    fid = F.forest(region).id
    d = depth if depth is not None else region_depth(fid, resolver=resolver)
    s = dict(signals) if signals is not None else region_signals(
        fid, conn, now=now, window_days=window_days, reports_dir=reports_dir)
    unmeasured: list[str] = []
    layers_term: float | None
    if d.packs:
        per = [1.0 - (p.layers_mapped + 0.5 * p.layers_unverified) / len(CL.SOURCE_LAYERS)
               for p in d.packs]
        layers_term = sum(per) / len(per)
    elif d.kind == "regional" and not d.package:
        layers_term = 1.0                      # nothing mapped because nothing exists
    else:
        layers_term = None
    n_disc = None
    if s.get("sources_window") is not None or s.get("discoveries_window") is not None:
        n_disc = int(s.get("sources_window") or 0) + int(s.get("discoveries_window") or 0)
    disc_term = None if n_disc is None else (
        1.0 if n_disc == 0 else max(0.0, 1.0 - (n_disc / max(1, int(window_days)))))
    lattice = s.get("lattice_candidates")
    lattice_term = None if lattice is None else (
        1.0 if int(lattice) == 0 else max(0.0, 1.0 - int(lattice) / float(LATTICE_TARGET)))
    resident = s.get("resident")
    resident_term = None if resident is None else (0.0 if resident else 1.0)
    terms = {"layers": _term_or_middle(layers_term, "layers", unmeasured),
             "discovery": _term_or_middle(disc_term, "discovery", unmeasured),
             "lattice": _term_or_middle(lattice_term, "lattice", unmeasured),
             "resident": _term_or_middle(resident_term, "resident", unmeasured)}
    debt = sum(DEBT_WEIGHTS[k] * v for k, v in terms.items())
    return {"region": fid, "debt": round(debt, 6), "terms": {k: round(v, 6) for k, v in
                                                            terms.items()},
            "weights": dict(DEBT_WEIGHTS), "unmeasured": unmeasured,
            "why": (f"debt {debt:.3f} = " + " + ".join(f"{DEBT_WEIGHTS[k]:.2f}x{v:.2f} {k}"
                                                        for k, v in terms.items())
                    + (f"; UNMEASURED held at the middle: {unmeasured}" if unmeasured else ""))}


# --------------------------------------------------------------------------- the priority
def priority_of(*, p_useful: float, orthogonality: float, information_gain: float,
                coverage_debt: float, compute: float = 0.0, data_cost: float = 0.0,
                trial_burden: float = 0.0) -> float:
    """The law's formula, with the debt entering as a BONUS (1 + debt) and every cost entering
    against a unit floor so an unpriced region is neither infinite nor zero."""
    num = (max(0.0, p_useful) * max(0.0, orthogonality) * max(0.0, information_gain)
           * (1.0 + max(0.0, coverage_debt)))
    den = 1.0 + max(0.0, compute) + max(0.0, data_cost) + max(0.0, trial_burden)
    return round(num / den, 6)


def _norm(value: float | None, mean: float | None) -> float | None:
    if value is None:
        return None
    if mean is None or mean <= 0:
        return 0.0
    return float(value) / float(mean)


def flags_for(row: Mapping[str, Any], median_depth: float | None) -> list[str]:
    """The law's four red conditions plus NO_PACK, on MEASURED absences only."""
    out: list[str] = []
    if row.get("kind") != "regional":
        return out
    depth = row.get("depth") or {}
    sig = row.get("signals") or {}
    if not depth.get("packs") and not depth.get("package"):
        out.append("NO_PACK")
    if sig.get("resident") is False:
        out.append("NO_RESIDENT")
    n_disc = None
    if sig.get("sources_window") is not None or sig.get("discoveries_window") is not None:
        n_disc = int(sig.get("sources_window") or 0) + int(sig.get("discoveries_window") or 0)
    if n_disc == 0:
        out.append("NO_DISCOVERY")
    if sig.get("lattice_candidates") == 0:
        out.append("NO_LATTICE_CANDIDATE")
    score = depth.get("score_mean")
    if score is not None and median_depth is not None and float(score) < 0.5 * median_depth:
        out.append("DEPTH_BELOW_HALF_MEDIAN")
    return out


@dataclass(frozen=True)
class _Costs:
    compute: float | None = None
    api: float | None = None
    trials: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _costs_of(costs: Mapping[str, Mapping[str, Any]] | None, fid: str) -> _Costs:
    row = (costs or {}).get(fid)
    if not isinstance(row, Mapping):
        return _Costs()

    def num(key: str) -> float | None:
        v = row.get(key)
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    return _Costs(compute=num("compute_hours"), api=num("api_calls"), trials=num("trials"))


def parity_report(regions: Sequence[str] | None = None, *, conn: Any = None,
                  now: datetime | None = None, window_days: int = DISCOVERY_WINDOW_DAYS,
                  region_roi: Mapping[str, float | None] | None = None,
                  costs: Mapping[str, Mapping[str, Any]] | None = None,
                  resolver: Callable[[str], CL.CountryPack | None] | None = None,
                  reports_dir: Path | None = None,
                  reg: Mapping[str, Mapping[str, Any]] | None = None,
                  stale_hours: float = RESIDENT_STALE_HOURS) -> dict[str, Any]:
    """For every FOREST region: resident present? discovery in the window? candidates in the
    lattice? layers mapped? depth vs the median region? -- and the priority each earns.

    `region_roi` and `costs` are the research-ROI organ's own per-region numbers when it is the
    caller (P(useful) and the denominator); absent, both hold the middle by name. The report is
    a plain mapping so the allocator can fold it into its file and the fence can write it.
    """
    at = now or datetime.now(tz=UTC)
    ids = tuple(F.forest(r).id for r in regions) if regions else tuple(F.FORESTS)
    depths = {fid: region_depth(fid, resolver=resolver, reg=reg) for fid in ids}
    cutoff = (at - timedelta(days=int(window_days))).isoformat()
    with _regional_census(conn, cutoff) as census:
        signals = {fid: region_signals(fid, conn, now=at, window_days=window_days,
                                       reports_dir=reports_dir, stale_hours=stale_hours,
                                       _census=census)
                   for fid in ids}
    debts = {fid: coverage_debt(fid, depth=depths[fid], signals=signals[fid]) for fid in ids}
    med = median(d.score_mean for d in depths.values()
                 if d.kind == "regional" and d.score_mean is not None)
    # P(useful): the measured ROI against the mean of the measured ROIs, halved into [0.25, 1].
    rois = {fid: (region_roi or {}).get(fid) for fid in ids}
    measured_roi = [float(v) for v in rois.values() if isinstance(v, (int, float))]
    mean_roi = _mean(measured_roi)
    totals_disc = sum(int(s["discoveries_total"] or 0) for s in signals.values()
                      if s.get("discoveries_total") is not None)
    cost_rows = {fid: _costs_of(costs, fid) for fid in ids}
    mean_compute = _mean(c.compute for c in cost_rows.values() if c.compute is not None)
    mean_trials = _mean(c.trials for c in cost_rows.values() if c.trials is not None)
    rows: dict[str, dict[str, Any]] = {}
    for fid in ids:
        d, s, debt, c = depths[fid], signals[fid], debts[fid], cost_rows[fid]
        unmeasured: list[str] = list(debt["unmeasured"])
        roi = rois[fid]
        if isinstance(roi, (int, float)) and mean_roi is not None and mean_roi > 0:
            p_useful = clip(float(roi) / mean_roi) / 2.0
        else:
            p_useful = 0.5
            unmeasured.append("p_useful")
        n_total = s.get("discoveries_total")
        if n_total is None:
            orth, ig = 1.0, 1.0
            unmeasured.append("orthogonality")
        else:
            share = (int(n_total) / totals_disc) if totals_disc > 0 else 0.0
            orth = 1.0 - min(0.9, share)
            lat = s.get("lattice_candidates")
            ig = 1.0 / (1.0 + math.log1p(int(lat))) if lat is not None else 1.0
        compute_n = _norm(c.compute, mean_compute)
        trials_n = _norm(c.trials, mean_trials)
        pit = [p.pit_feasible_share for p in d.packs if p.pit_feasible_share is not None]
        data_cost = (1.0 - sum(pit) / len(pit)) if pit else None
        if compute_n is None:
            unmeasured.append("compute")
        if trials_n is None:
            unmeasured.append("trial_burden")
        if data_cost is None:
            unmeasured.append("data_cost")
        terms = {"p_useful": round(p_useful, 6), "orthogonality": round(orth, 6),
                 "information_gain": round(ig, 6), "coverage_debt": debt["debt"],
                 "compute": round(compute_n if compute_n is not None else 0.0, 6),
                 "data_cost": round(data_cost if data_cost is not None else 0.5, 6),
                 "trial_burden": round(trials_n if trials_n is not None else 0.0, 6)}
        prio = priority_of(**terms)
        row: dict[str, Any] = {
            "forest": fid, "kind": d.kind, "depth": d.as_row(), "signals": s,
            "coverage_debt": debt, "priority": prio, "priority_terms": terms,
            "layers_mapped": (sum(p.layers_mapped for p in d.packs) / len(d.packs)
                              if d.packs else None),
            "layers_declared": (sum(p.layers_declared for p in d.packs) / len(d.packs)
                                if d.packs else None),
            "depth_score": d.score_mean, "depth_vs_median": (
                None if d.score_mean is None or not med else round(d.score_mean / med, 6)),
            "unmeasured": sorted(set(unmeasured)),
        }
        row["flags"] = flags_for(row, med)
        rows[fid] = row
    prios = [r["priority"] for r in rows.values()]
    mean_p = _mean(prios)
    for r in rows.values():
        r["priority_factor"] = (round(clip(r["priority"] / mean_p), 6)
                                if mean_p and mean_p > 0 else 1.0)
    counts = {flag: sum(1 for r in rows.values() if flag in r["flags"]) for flag in FLAGS}
    return {"at": at.isoformat(timespec="seconds"), "window_days": int(window_days),
            "median_depth": med, "n_regions": len(rows),
            "n_regional": sum(1 for r in rows.values() if r["kind"] == "regional"),
            "regions": rows, "flag_counts": counts,
            "flagged": sorted(fid for fid, r in rows.items() if r["flags"]),
            "mean_priority": (round(mean_p, 6) if mean_p is not None else None),
            "law": "docs/LAWS.md 5n", "rule": RULE}


# =========================================================================== EQUIVALENCE PARITY
# THE GLOBAL HALF'S CORE LAW, PROJECTED (ASIA_CHINA_FIRST_DIRECTIVE 2026-10-05, CORE LAW + PARTS
# II, III and XXXIII; completion audit 2026-10-06 rank 11). Depth above counts what a region's
# packs carry; this half asks the directive's question of EVERY country: for each information
# class, is the local functional equivalent COVERED, DECLARED, a known public equivalent nobody
# declared, genuinely absent, or never looked at? The ontology is frozen data in
# `libs/research/equivalence_ontology.py`; this projection is pure (it reads what it is handed)
# and `desks/mt5/research/regional_parity_pass.py` is the hourly organ that hands it the packs,
# the coverage tensor and the ingestion ledger and writes REGIONAL_PARITY.json.

#: A declaration a pack writes as a GAP rather than as a source ("NOT AVAILABLE. Declared as a
#: GAP by name", "cftc_cot_absent :: ... NO KRW CONTRACT EXISTS") is never a declaration.
_GAP_RE = re.compile(r"NOT AVAILABLE|declared as a gap|_absent\b|\bNO \w+ (CONTRACT )?EXISTS|"
                     r"LARGELY SUSPENDED", re.IGNORECASE)
#: Work-queue weights. Disposition first (a known equivalent nobody declared is the cheapest
#: parity a country can gain), then how good the equivalent is, then how fast it prints.
_QUEUE_DISPOSITION: dict[str, float] = {"ABSENT_KNOWN_EQUIVALENT": 3.0, "DECLARED": 2.0,
                                        UNMEASURED: 1.0}
_QUEUE_TIER: dict[str, float] = {"named": 0.3, "transnational": 0.2, "role": 0.1}
_QUEUE_CADENCE: dict[str, float] = {"daily": 0.15, "weekly": 0.1, "event": 0.08, "monthly": 0.05}
_NEXT_MOVE: dict[str, str] = {
    "ABSENT_KNOWN_EQUIVALENT": "declare the known equivalent in the country pack and hand its "
                               "endpoint to acquire_datasets (discoveries_parity_*.json)",
    "DECLARED": "feed it: fetch the declared source and carry one unit to a measured downstream "
                "state in the ingestion ledger",
    UNMEASURED: "hunt the local functional equivalent (directive PART III) or declare its "
                "absence with a reason",
}
EQUIVALENCE_RULE = ("for every country and every information class, name the LOCAL functional "
                    "equivalent; COVERED only with proof of source -> measured outcome, never by "
                    "default, and UNMEASURED is a verdict, never zero")


def _txt(*parts: Any) -> str:
    return " | ".join(str(p) for p in parts if str(p or "").strip())


def pack_declarations(code: str, pack: Any) -> list[dict[str, Any]]:
    """Every row a pack declares that could answer an information class, as plain mappings.

    Read from the typed pack (`country_lab.CountryPack`): release classes, datasets, positioning
    and institutional-flow sources, the series map, fixing conventions, the central bank's policy
    series and the CFTC currency. The ten source-layer ROOTS are not read: they name where to look
    ("the ministries"), not a data class, and matching them would credit classes by prose.
    """
    rows: list[dict[str, Any]] = []

    def add(kind: str, rid: Any, text: str, keys: Sequence[Any], forced: Sequence[str] = (),
            gap_text: str = "") -> None:
        ident = str(rid or "").strip()
        if not ident or _GAP_RE.search(f"{ident} {gap_text} {text}"):
            return
        rows.append({"pack": code, "kind": kind, "id": ident[:120], "text": text[:400],
                     "keys": sorted({str(k).strip().lower() for k in keys
                                     if len(str(k or "").strip()) >= 4}),
                     "forced": list(forced)})

    for r in getattr(pack, "release_classes", ()) or ():
        add("release", r.name, _txt(r.name, r.actual_series, r.source), (r.name, r.actual_series))
    for d in getattr(pack, "datasets", ()) or ():
        add("dataset", d.name, _txt(d.name, d.source, d.frequency), (d.name,),
            gap_text=str(d.how_to_fetch or ""))
    for s in tuple(getattr(pack, "positioning_sources", ()) or ()) + tuple(
            getattr(pack, "institutional_flow_sources", ()) or ()):
        parts = [p.strip() for p in str(s).split("::")]
        add("positioning", parts[0], _txt(*parts[:2]), (parts[0],), gap_text=str(s))
    for k, v in dict(getattr(pack, "series", {}) or {}).items():
        add("series", k, _txt(k, v), (k, v))
    for f in getattr(pack, "fixing_conventions", ()) or ():
        add("fixing", f.name, str(f.name), (f.name,))
    cb = getattr(pack, "central_bank", None)
    series = str(getattr(cb, "policy_rate_series", "") or "").strip() if cb is not None else ""
    if series and "no_policy_rate" not in series:
        add("central_bank", series, _txt(getattr(cb, "name", ""), "policy rate"), (series,),
            forced=("Monetary / rates:policy rates",))
    ccy = str(getattr(pack, "cot_currency", "") or "").strip()
    if ccy:
        add("cot_currency", f"cftc_cot:{ccy}", f"CFTC currency positioning {ccy}",
            ("cftc_tff_currency",), forced=("Part III:FX positioning",))
    return rows


def classes_declared(rows: Iterable[Mapping[str, Any]], code: str,
                     jurisdictions: Sequence[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """country -> class -> [declaration], with multi-country attribution made honestly.

    A single-jurisdiction pack credits its one country. A multi-jurisdiction pack credits a row to
    the country it NAMES (`equivalence_ontology.names_country`), or -- for a class that is that
    pack's shared competence, the ECB's operations for the euro members -- to every member. A row
    that names nobody is UNATTRIBUTED and reported, never spread over the pack.
    """
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    shared = EQ.SHARED_COMPETENCE.get(code, frozenset())
    single = len(jurisdictions) == 1
    for row in rows:
        text = str(row.get("text") or "").replace("_", " ")
        forced = list(row.get("forced") or ())
        # A FORCED row says exactly what it is (the central bank's policy series, the CFTC
        # currency); matching its prose too would credit the FOMC's name to open-market ops.
        keys = forced or list(EQ.match_classes(text))
        for key in keys:
            if single or key in shared:
                targets = list(jurisdictions)
            else:
                raw = f"{row.get('id')} {row.get('text')}"
                targets = [cc for cc in jurisdictions if EQ.names_country(raw, cc)]
            for cc in targets:
                out.setdefault(cc, {}).setdefault(key, []).append(dict(row))
    return out


def proof_index(ingestion: Mapping[str, Any] | None,
                ledger_rows: Iterable[Mapping[str, Any]] = ()) -> dict[str, dict[str, str]]:
    """token -> {state, unit}: every ingestion unit or dataset that reached a MEASURED outcome.

    The ingestion ledger is the same evidence the coverage tensor reads for its INGESTED rung; a
    unit counts as proof only past AWAITING_EXPERIMENT (`equivalence_ontology.
    MEASURED_OUTCOME_STATES`). Tokens are the unit id, the dataset name, the path stem and each
    `:`-separated part of them, lower-cased.
    """
    idx: dict[str, dict[str, str]] = {}

    def put(names: Iterable[Any], state: str, unit: str) -> None:
        for raw in names:
            s = str(raw or "").strip().lower()
            if not s:
                continue
            toks = {s, s.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]}
            toks |= {p for p in s.split(":") if p}
            for t in toks:
                if len(t) >= 4:
                    idx.setdefault(t, {"state": state, "unit": unit})

    datasets = ingestion.get("datasets") if isinstance(ingestion, Mapping) else None
    if isinstance(datasets, Mapping):
        for name, block in datasets.items():
            states = block.get("downstream_states") if isinstance(block, Mapping) else None
            hit = sorted(str(s) for s, n in dict(states or {}).items()
                         if s in EQ.MEASURED_OUTCOME_STATES and int(n or 0) > 0)
            if hit:
                put((name,), hit[0], str(name))
    for r in ledger_rows:
        state = str(r.get("downstream_state") or "")
        if state in EQ.MEASURED_OUTCOME_STATES:
            put((r.get("unit_id"), r.get("dataset"), r.get("path")), state,
                f"{r.get('kind')}:{r.get('unit_id')}")
    return idx


def _find_proof(idx: Mapping[str, Mapping[str, str]], keys: Iterable[str]) -> dict[str, str] | None:
    for k in keys:
        got = idx.get(str(k).lower())
        if got:
            return {"key": str(k), **dict(got)}
    return None


def _tensor_layers(tensor: Mapping[str, Any] | None) -> dict[str, dict[str, str]]:
    """pack code -> layer -> state, from COVERAGE_TENSOR.json's own country verdicts."""
    if not isinstance(tensor, Mapping):
        return {}
    cov = tensor.get("coverage")
    per = cov.get("by_country") if isinstance(cov, Mapping) else None
    out: dict[str, dict[str, str]] = {}
    for code, row in dict(per or {}).items():
        layers = row.get("layers") if isinstance(row, Mapping) else None
        if isinstance(layers, Mapping):
            out[str(code).lower()] = {
                str(k): str(v.get("state") or UNMEASURED) if isinstance(v, Mapping)
                else UNMEASURED for k, v in layers.items()}
    return out


#: The dispositions whose FED question a readable ledger answers. UNMEASURED never is (nobody
#: looked), NO_EQUIVALENT is out of scope, and any cell whose proof_state is UNMEASURED (no ledger
#: was readable) is unmeasured whatever its disposition.
_FED_MEASURABLE = frozenset({"COVERED", "DECLARED", "ABSENT_KNOWN_EQUIVALENT"})


def _fed_measured(cell: Mapping[str, Any]) -> bool:
    return (str(cell["disposition"]) in _FED_MEASURABLE
            and str(cell.get("proof_state") or UNMEASURED) != UNMEASURED)


def _counts(cells: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts and THE HEADLINE. Parity = fed / measured, where FED means EVALUATED -- a ledger
    verdict past AWAITING_EXPERIMENT (COVERED) -- and never merely declared; and MEASURED excludes
    every cell whose fed state nobody measured, which is published as its own count instead of
    sitting in the denominator as a zero. Nothing measured -> the headline is UNMEASURED."""
    c = dict.fromkeys(EQ.DISPOSITIONS, 0)
    n = measured = 0
    for cell in cells:
        c[str(cell["disposition"])] += 1
        n += 1
        measured += _fed_measured(cell)
    in_scope = n - c["NO_EQUIVALENT"]
    unmeasured = in_scope - measured
    return {"n": n, "counts": c,
            "parity": (round(c["COVERED"] / measured, 6) if measured > 0 else UNMEASURED),
            "fed": c["COVERED"], "measured": measured, "unmeasured": unmeasured,
            "declared_share": (round((c["COVERED"] + c["DECLARED"]) / in_scope, 6)
                               if in_scope > 0 else None),
            "known_gap": c["ABSENT_KNOWN_EQUIVALENT"],
            "unmeasured_share": (round(unmeasured / in_scope, 6) if in_scope > 0 else None)}


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def candidate_class_rows(rows: Iterable[Mapping[str, Any]], code: str,
                         jurisdictions: Sequence[str]) -> list[dict[str, Any]]:
    """Every declaration NO class matches, as a CANDIDATE CLASS row -- never dropped.

    The ontology is the directive's floor, not its ceiling: a source a pack declares that answers
    none of the classes is either a class the ontology lacks or a class whose terms are too
    narrow. Either way it is work, so it is reported and persisted; promoting one means adding
    it to `desks/mt5/data/equivalence_ontology_ext.json`."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("forced") or EQ.match_classes(str(row.get("text") or "").replace("_", " ")):
            continue
        raw = f"{row.get('id')} {row.get('text')}"
        named = [cc for cc in jurisdictions if EQ.names_country(raw, cc)]
        ident = f"{code}|{row.get('kind')}|{row.get('id')}"
        out.append({"candidate_id": hashlib.sha1(ident.encode("utf-8")).hexdigest()[:16],
                    "pack": code, "kind": row.get("kind"), "id": row.get("id"),
                    "text": row.get("text"),
                    "countries": (list(jurisdictions) if len(jurisdictions) == 1 else named),
                    "status": "CANDIDATE_CLASS",
                    "next_move": "add a class (or widen an existing class's terms) in "
                                 "desks/mt5/data/equivalence_ontology_ext.json, or record why "
                                 "this declaration is not an information class"})
    return out


def _queue_row(c: Mapping[str, Any], below: Sequence[str]) -> dict[str, Any] | None:
    d = str(c["disposition"])
    if d not in _QUEUE_DISPOSITION:
        return None
    eq = c.get("equivalent") or {}
    dc = EQ.class_of(str(c["class"]))
    score = (_QUEUE_DISPOSITION[d] + _QUEUE_TIER.get(str(eq.get("tier") or ""), 0.0)
             + (0.2 if eq.get("endpoints") else 0.0)
             + _QUEUE_CADENCE.get(dc.cadence if dc is not None else "", 0.0)
             + (0.1 if c["region"] in below else 0.0))
    return {"country": c["country"], "region": c["region"], "class": c["class"],
            "disposition": d, "score": round(score, 4), "source_id": eq.get("source_id"),
            "publisher": eq.get("publisher"), "url": eq.get("url"),
            "endpoints": list(eq.get("endpoints") or []),
            "held_endpoints": [h.get("url") for h in eq.get("held_endpoints") or []],
            "tier": eq.get("tier"),
            "next_move": _NEXT_MOVE[d]}


def equivalence_parity(*, packs: Mapping[str, Any], jurisdictions: Mapping[str, Sequence[str]],
                       tensor: Mapping[str, Any] | None = None,
                       ingestion: Mapping[str, Any] | None = None,
                       ledger_rows: Sequence[Mapping[str, Any]] = (),
                       countries: Sequence[str] | None = None,
                       now: datetime | None = None, queue_cap: int = 600) -> dict[str, Any]:
    """The per-country x information-class disposition table, its parity metrics and the work
    queue. PURE: everything it reads is an argument, and an argument that is None is named in
    `unmeasured` rather than read as empty ground."""
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    unmeasured: list[str] = []
    declared: dict[str, dict[str, list[dict[str, Any]]]] = {}
    unattributed: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    pack_of: dict[str, list[str]] = {}
    for code, pack in sorted(packs.items()):
        juris = [str(c).lower() for c in (jurisdictions.get(code) or (code,))]
        for cc in juris:
            pack_of.setdefault(cc, []).append(code)
        if pack is None:
            unmeasured.append(f"pack {code}: did not resolve, its declarations are UNMEASURED")
            continue
        rows = pack_declarations(code, pack)
        got = classes_declared(rows, code, juris)
        candidates.extend(candidate_class_rows(rows, code, juris))
        if len(juris) > 1:
            hit_ids = {d["id"] for per in got.values() for ds in per.values() for d in ds}
            missed = sum(1 for r in rows
                         if EQ.match_classes(str(r["text"]).replace("_", " "))
                         and r["id"] not in hit_ids)
            if missed:
                unattributed[code] = missed
        for cc, per in got.items():
            for key, ds in per.items():
                declared.setdefault(cc, {}).setdefault(key, []).extend(ds)
    roster = sorted({str(c).lower() for c in (countries or ())} | set(pack_of))
    readable = isinstance(ingestion, Mapping) or bool(ledger_rows)
    if not readable:
        unmeasured.append("ingestion ledger: neither INGESTION_EXPLOITATION.json nor "
                          "ingestion_ledger.jsonl was readable -- no cell can be COVERED and "
                          "every DECLARED cell carries proof_state UNMEASURED")
    idx = proof_index(ingestion, ledger_rows) if readable else {}
    layers = _tensor_layers(tensor)
    if not layers:
        unmeasured.append("COVERAGE_TENSOR.json: absent or carries no coverage.by_country -- the "
                          "per-country source-layer states are UNMEASURED")

    cells: list[dict[str, Any]] = []
    by_country: dict[str, dict[str, Any]] = {}
    for cc in roster:
        region = F.forest_of_country(cc) or "UNASSIGNED"
        per_cells: list[dict[str, Any]] = []
        for dc in EQ.CLASSES:
            decl = declared.get(cc, {}).get(dc.key, [])
            eqs = EQ.equivalents_for(cc, dc.key)
            keys = [str(k) for d in decl for k in d.get("keys") or ()]
            keys += [e.source_id for e in eqs if e.tier != "role"]
            proof = _find_proof(idx, keys) if idx else None
            cell = EQ.dispose(cc, dc.key, declared=decl, proof=proof, proof_readable=readable,
                              equivalents=eqs).to_json()
            cell["region"] = region
            cell["layer"] = dc.layer
            per_cells.append(cell)
        cells.extend(per_cells)
        tl: dict[str, str] = {}
        for code in pack_of.get(cc, []):
            for layer, state in layers.get(code, {}).items():
                tl.setdefault(layer, state)
        by_country[cc] = {"region": region, "name": EQ.COUNTRY_NAMES.get(cc, (cc,))[0],
                          "packs": sorted(pack_of.get(cc, [])),
                          "tensor_layers": tl or UNMEASURED, **_counts(per_cells)}

    groups = list(dict.fromkeys(dc.group for dc in EQ.CLASSES))
    by_class = {dc.key: {"group": dc.group, "part": dc.part, "mandate_id": dc.mandate_id,
                         "layer": dc.layer,
                         **_counts(c for c in cells if c["class"] == dc.key)}
                for dc in EQ.CLASSES}
    by_region: dict[str, dict[str, Any]] = {}
    for r in sorted({str(c["region"]) for c in cells}):
        mine = [c for c in cells if c["region"] == r]
        ctry = sorted(cc for cc, row in by_country.items() if row["region"] == r)
        by_region[r] = {"countries": ctry, "n_countries": len(ctry), **_counts(mine),
                        "parity_by_group": {
                            g: _counts(c for c in mine
                                       if str(c["class"]).startswith(g + ":"))["parity"]
                            for g in groups}}
    # THE HEADLINE SPREAD: only regions whose parity was MEASURED; an UNMEASURED region is named,
    # never read as zero and never as the median.
    measured_parity = {k: p for k, v in by_region.items()
                       if k != "UNASSIGNED" and (p := _num(v["parity"])) is not None}
    med = median(measured_parity.values())
    below = sorted(k for k, p in measured_parity.items() if med is not None and p < med)
    # The QUEUE's region boost reads declaration coverage, a different and explicitly named
    # quantity: it orders work toward thin regions even while no ledger is readable, and it is
    # never published as parity.
    declared_by_region = {k: float(v["declared_share"]) for k, v in by_region.items()
                          if k != "UNASSIGNED" and v["declared_share"] is not None}
    dmed = median(declared_by_region.values())
    thin = sorted(k for k, p in declared_by_region.items() if dmed is not None and p < dmed)
    queue = [q for q in (_queue_row(c, thin) for c in cells) if q is not None]
    queue.sort(key=lambda q: (-float(q["score"]), str(q["country"]), str(q["class"])))
    core: dict[str, dict[str, str]] = {}
    for anchor, key in EQ.CORE_LAW_ANCHORS.items():
        core[anchor] = {str(c["country"]): str(c["disposition"]) for c in cells
                        if c["class"] == key}
    return {
        "at": at, "rule": EQUIVALENCE_RULE, "class_source": EQ.CLASS_SOURCE,
        "dispositions": list(EQ.DISPOSITIONS),
        "classes": [{"key": dc.key, "group": dc.group, "name": dc.name, "part": dc.part,
                     "layer": dc.layer, "mandate_id": dc.mandate_id} for dc in EQ.CLASSES],
        "functions": {k: list(v) for k, v in EQ.FUNCTIONS.items()},
        "core_law_anchors": dict(EQ.CORE_LAW_ANCHORS),
        "n_countries": len(roster), "n_classes": len(EQ.CLASSES), "n_cells": len(cells),
        "totals": _counts(cells),
        "by_class": by_class, "by_region": by_region, "by_country": by_country,
        "parity_definition": ("fed / measured: FED = COVERED (an ingestion-ledger verdict past "
                              "AWAITING_EXPERIMENT), never DECLARED; MEASURED = in-scope cells "
                              "whose fed state a readable ledger answered; UNMEASURED cells are "
                              "excluded from the denominator and counted in `unmeasured`; with "
                              "nothing measured the headline is UNMEASURED"),
        "parity_spread": {"median": (round(med, 6) if med is not None else UNMEASURED),
                          "min": min(measured_parity.values()) if measured_parity else UNMEASURED,
                          "max": max(measured_parity.values()) if measured_parity else UNMEASURED,
                          "regions_measured": sorted(measured_parity),
                          "regions_unmeasured": sorted(k for k in by_region
                                                       if k != "UNASSIGNED"
                                                       and k not in measured_parity),
                          "regions_below_median": below},
        "declaration_spread": {"median": (round(dmed, 6) if dmed is not None else None),
                               "regions_below_median": thin,
                               "note": "declared_share orders the work queue; it is NOT parity"},
        "core_law": core,
        "work_queue": queue[:queue_cap], "work_queue_total": len(queue),
        "unattributed_declarations": dict(sorted(unattributed.items())),
        "candidate_classes": candidates, "n_candidate_classes": len(candidates),
        "ontology_extension": dict(EQ.EXT_REPORT),
        "proof": {"readable": readable, "measured_tokens": len(idx),
                  "states": sorted(EQ.MEASURED_OUTCOME_STATES)},
        "cells": cells,
        "unmeasured": unmeasured,
    }
