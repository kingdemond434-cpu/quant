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

import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research import country_lab as CL
from libs.research import forests as F

__all__ = [
    "DEBT_WEIGHTS",
    "DEPTH_TARGETS",
    "DISCOVERY_WINDOW_DAYS",
    "FLAGS",
    "LATTICE_TARGET",
    "RESIDENT_STALE_HOURS",
    "RULE",
    "UNMEASURED",
    "PackDepth",
    "RegionDepth",
    "clip",
    "coverage_debt",
    "depth_score",
    "flags_for",
    "median",
    "pack_depth",
    "parity_report",
    "priority_of",
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


def region_signals(forest_id: str, conn: Any = None, *, now: datetime | None = None,
                   window_days: int = DISCOVERY_WINDOW_DAYS,
                   reports_dir: Path | None = None,
                   stale_hours: float = RESIDENT_STALE_HOURS) -> dict[str, Any]:
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
    # ---- the lattice: discoveries that produced cells, plus candidates the forest generated ---
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
    signals = {fid: region_signals(fid, conn, now=at, window_days=window_days,
                                   reports_dir=reports_dir, stale_hours=stale_hours)
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
