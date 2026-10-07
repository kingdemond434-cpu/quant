"""WHO DIRECTLY MEASURES ACTIVITY, COUNTRY BY COUNTRY, DOWN TO THE FACILITY (DATA-10).

THE GAP. The country packs (`desks/mt5/research/countries/*/pack.py`) list each country's
national sources -- the central bank, the statistics office, the customs service -- and the
catalogue roster (`data/catalog_routes/roster.json`) already walks a few subnational portals
(data.nsw.gov.au, the Ontario and Alberta catalogues, the New York City and Chicago portals). But
no record said, for any country, WHO MEASURES ACTIVITY BELOW THE NATIONAL LEVEL -- the province's
energy regulator, the city portal, the port, the grid operator, the river basin authority, the
canal -- and no number said how much of that is mapped. A national aggregate arrives weeks after
the facility that produced it published; the subnational producer is where the lead is.

THE REGISTRY. One row per measurer, merged every pass from three places, none edited here:

    country packs     every SourceRow / DatasetRow in a measuring layer (official,
                      institutional, physical_economy, archive, or untagged), classified
    catalogue roster  every portal, with its own `producer_type` and `subnational` code
    data/measurer_registry.json   the producer-level rows neither of the above carries yet

Each row carries `level` (national / province / municipality / facility / basin / corridor) and
`producer_type` (statistics_office, central_bank, regulator, port, grid_operator, ...). A level
the text does not support is UNMEASURED, never defaulted to national.

THE METRIC, per country: measurers at each level, the SUBNATIONAL LEVELS COVERED out of five
(province, municipality, facility, basin, corridor), and how many rows are VERIFIED (a catalogue
portal that was visited, or a pack source marked verified). A country with no row at all is
UNMEASURED by name, never 0% covered. Nothing is fetched.

    python desks/mt5/research/measurer_registry.py   -> reports/MEASURER_REGISTRY.json + digest
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEED = DESK / "data" / "measurer_registry.json"
ROSTER = DESK / "data" / "catalog_routes" / "roster.json"
CATALOG_STATE = DESK / "data" / "catalog_routes" / "state.json"
COUNTRIES = DESK / "research" / "countries"
REPORT = DESK / "reports" / "MEASURER_REGISTRY.json"
DIGEST = DESK / "data" / "digests" / "measurer_registry_digest.json"

UNMEASURED = "UNMEASURED"
LEVELS: tuple[str, ...] = ("national", "province", "municipality", "facility", "basin",
                           "corridor")
SUBNATIONAL: tuple[str, ...] = LEVELS[1:]
#: Pack layers whose sources MEASURE something. Media, practitioners, retail chatter, apps,
#: academics and the citation graph report on activity; they do not measure it.
MEASURING_LAYERS = frozenset({"official", "institutional", "physical_economy", "archive", ""})

#: Words that place a measurer at a level, most specific first. Matched on word boundaries
#: against the source's label, notes and roots. No match leaves the level UNMEASURED.
_LEVEL_WORDS: tuple[tuple[str, str], ...] = (
    ("facility", r"port of|ports? authority|harbou?r|terminal|refiner(y|ies)|smelter|mine\b|"
                 r"mines\b|warehouse|power (plant|station)|storage hub|cushing|stockpile|"
                 r"\bfab\b|plant-level|pilbaraports|portof"),
    ("basin", r"basin|river authority|watershed|reservoir|catchment|aquifer"),
    ("corridor", r"canal|strait|pipeline|corridor|shipping route|rail freight|waterway|"
                 r"freight route|transit route|chokepoint"),
    ("municipality", r"municipal|city of|\bcity\b|metropolitan|county|prefectural capital|"
                     r"borough|mayor"),
    ("province", r"provinc|\bstate (government|budget|statistics|treasury)|prefecture|oblast|"
                 r"l[aä]nder|\bregional (government|statistics)|canton|governorate|emirate of|"
                 r"territory government|\bstate's\b"),
)
_TYPE_WORDS: tuple[tuple[str, str], ...] = (
    ("central_bank", r"central bank|reserve bank|banco central|bank of [a-z]+|bundesbank|"
                     r"banque de|norges bank|riksbank|monetary authority"),
    ("statistics_office", r"statistic|census|bureau of statistics|insee|istat|destatis|"
                          r"\bons\b|\bcbs\b|statcan|\bbps\b|\bine\b"),
    ("customs", r"customs|trade statistics office"),
    ("port", r"\bports?\b|harbou?r|maritime authority"),
    ("grid_operator", r"grid|system operator|\biso\b|transmission|electricity market operator"),
    ("utility", r"utility|utilities|water corporation|energy company"),
    ("exchange", r"exchange|bourse|b3\b|clearing"),
    ("regulator", r"regulator|commission|authority|supervis"),
    ("ministry", r"ministry|ministerio|department of|treasury|budget"),
    ("association", r"association|federation|chamber|institute|council"),
    ("agency", r"agency|administration|office|service|survey"),
)
_NATIONAL_TYPES = frozenset({"central_bank", "statistics_office", "customs", "ministry"})


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def classify(text: str) -> tuple[str, str]:
    """(level, producer_type) from a source's own words; UNMEASURED where they say nothing."""
    level, ptype, _basis = classify_with_basis(text)
    return level, ptype


def classify_with_basis(text: str) -> tuple[str, str, str]:
    """(level, producer_type, the words that decided the level) -- auditable per row."""
    low = text.lower()
    level, basis = "", ""
    for lv, rx in _LEVEL_WORDS:
        m = re.search(rx, low)
        if m:
            level, basis = lv, f"keyword {m.group(0)!r}"
            break
    ptype = next((t for t, rx in _TYPE_WORDS if re.search(rx, low)), UNMEASURED)
    if not level:
        level, basis = (("national", f"producer type {ptype}") if ptype in _NATIONAL_TYPES
                        else (UNMEASURED, "no level word in the source's own text"))
    return level, ptype, basis


def _level_of_subnational(code: Any) -> str:
    text = str(code or "")
    if not text:
        return "national"
    return "municipality" if "/" in text else "province"


def _unpack_label(row: Any) -> dict[str, Any]:
    """A pack source declared as a repr()'d mapping (some packs did) read back as data. Literal
    evaluation only: a label is data, never code."""
    label = str(getattr(row, "label", "") or getattr(row, "id", "") or "")
    if label.startswith("{"):
        try:
            got = ast.literal_eval(label)
        except (ValueError, SyntaxError):
            got = None
        if isinstance(got, dict):
            return got
    return {"id": getattr(row, "id", ""), "label": label, "layer": getattr(row, "layer", ""),
            "roots": list(getattr(row, "roots", ()) or ()), "notes": getattr(row, "notes", ""),
            "verified": bool(getattr(row, "verified", False))}


def _pack_country(code: str, sid: str) -> str:
    if len(code) == 2:
        return code.upper()
    parts = sid.split("_")
    if len(parts) > 1 and len(parts[1]) == 2 and parts[1].isalpha():
        return parts[1].upper()
    return f"REGION:{code}"


def from_packs(countries: Path = COUNTRIES) -> tuple[list[dict[str, Any]], list[str]]:
    """Every measuring source every country pack declares, classified. (rows, unresolved packs)"""
    try:
        from libs.research import country_lab
    except Exception as exc:
        return [], [f"country_lab unimportable: {type(exc).__name__}"]
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for pack_py in sorted(countries.glob("*/pack.py")):
        code = pack_py.parent.name
        if code.startswith("_"):
            continue
        try:
            pack = country_lab.resolve_pack(code)
        except Exception:
            pack = None
        if pack is None:
            unresolved.append(code)
            continue
        for src in country_lab.source_rows(pack):
            d = _unpack_label(src)
            layer = str(d.get("layer") or getattr(src, "layer", "") or "")
            if layer not in MEASURING_LAYERS or str(d.get("id", "")).startswith("absent:"):
                continue
            roots = [str(r) for r in (d.get("roots") or ())]
            text = " ".join([str(d.get("label") or ""), str(d.get("notes") or ""), *roots])
            level, ptype, basis = classify_with_basis(text)
            sid = str(d.get("id") or "")[:80]
            rows.append({"id": f"pack:{code}:{sid}", "country": _pack_country(code, sid),
                         "level": level, "producer_type": ptype,
                         "producer": str(d.get("label") or sid)[:160], "roots": roots[:4],
                         "origin": f"countries/{code}/pack.py", "layer": layer or "UNTAGGED",
                         "level_basis": basis, "verified": bool(d.get("verified"))})
        for ds in pack.datasets:
            text = " ".join([ds.name, ds.source, ds.how_to_fetch, ds.coverage])
            level, ptype, basis = classify_with_basis(text)
            rows.append({"id": f"pack:{code}:dataset:{ds.name[:60]}",
                         "country": _pack_country(code, ""), "level": level,
                         "producer_type": ptype, "producer": (ds.source or ds.name)[:160],
                         "roots": [ds.how_to_fetch] if ds.how_to_fetch.startswith("http") else [],
                         "origin": f"countries/{code}/pack.py (dataset)", "layer": "dataset",
                         "level_basis": basis, "verified": False})
    return rows, unresolved


def from_roster(roster: Mapping[str, Any] | None, state: Mapping[str, Any] | None
                ) -> list[dict[str, Any]]:
    visited = (state or {}).get("portals") or {}
    out = []
    for p in (roster or {}).get("portals") or []:
        if not isinstance(p, Mapping):
            continue
        ptype = str(p.get("producer_type") or UNMEASURED)
        level = _level_of_subnational(p.get("subnational"))
        if level == "national":
            lv, _ = classify(" ".join(str(p.get(k) or "") for k in ("producer", "note")))
            level = lv if lv in SUBNATIONAL else "national"
        st = visited.get(str(p.get("id"))) or {}
        out.append({"id": f"roster:{p.get('id')}", "country": str(p.get("country") or UNMEASURED),
                    "level": level, "producer_type": ptype,
                    "producer": str(p.get("producer") or p.get("id")),
                    "subdivision": p.get("subnational"), "roots": [str(p.get("base") or "")],
                    "origin": "data/catalog_routes/roster.json", "layer": "catalogue",
                    "level_basis": ("roster subnational code" if p.get("subnational")
                                    else "roster portal"),
                    "verified": bool(st.get("last_visit_at")) and not str(
                        st.get("status") or "").startswith(("ERROR", "TERMS", "BLOCKED"))})
    return out


def from_seed(seed: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for m in (seed or {}).get("measurers") or []:
        if not isinstance(m, Mapping) or not m.get("id"):
            continue
        level = str(m.get("level") or UNMEASURED)
        out.append({"id": f"seed:{m['id']}", "country": str(m.get("country") or UNMEASURED),
                    "level": level if level in LEVELS else UNMEASURED,
                    "producer_type": str(m.get("producer_type") or UNMEASURED),
                    "producer": str(m.get("producer") or m["id"]),
                    "subdivision": m.get("subdivision"), "roots": [str(m.get("root") or "")],
                    "measures": list(m.get("measures") or []),
                    "origin": "data/measurer_registry.json", "layer": "seed",
                    "level_basis": "declared in the seed",
                    "verified": False})
    return out


def coverage(rows: Iterable[Mapping[str, Any]], countries: Iterable[str] = ()
             ) -> dict[str, dict[str, Any]]:
    """Per country: measurers by level, subnational levels covered of five, verified rows."""
    by: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r["country"]), []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for c in sorted(set(by) | set(countries)):
        rs = by.get(c) or []
        if not rs:
            out[c] = {"status": UNMEASURED, "why": "no measurer row names this country"}
            continue
        levels = {lv: sum(1 for r in rs if r["level"] == lv) for lv in (*LEVELS, UNMEASURED)}
        covered = [lv for lv in SUBNATIONAL if levels[lv] > 0]
        out[c] = {"status": "MEASURED", "measurers": len(rs), "by_level": levels,
                  "subnational_levels_covered": covered,
                  "subnational_coverage": round(len(covered) / len(SUBNATIONAL), 4),
                  "subnational_measurers": sum(levels[lv] for lv in SUBNATIONAL),
                  "level_unmeasured": levels[UNMEASURED],
                  "verified": sum(1 for r in rs if r.get("verified")),
                  "missing_levels": [lv for lv in SUBNATIONAL if levels[lv] == 0]}
    return out


def build(now: datetime | None = None, *, seed_path: Path = SEED, roster_path: Path = ROSTER,
          state_path: Path = CATALOG_STATE, countries: Path = COUNTRIES) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    pack_rows, unresolved = from_packs(countries)
    rows = [*pack_rows, *from_roster(_read(roster_path, None), _read(state_path, None)),
            *from_seed(_read(seed_path, None))]
    cov = coverage(rows)
    measured = {c: v for c, v in cov.items() if v["status"] == "MEASURED"}
    level_totals = {lv: sum(1 for r in rows if r["level"] == lv) for lv in (*LEVELS, UNMEASURED)}
    return {
        "measured_at": now.isoformat(timespec="seconds"),
        "row": "DATA-10: producer-level measurers per country, national to facility",
        "levels": list(LEVELS), "subnational_levels": list(SUBNATIONAL),
        "n_measurers": len(rows), "n_countries": len(measured),
        "by_level": level_totals,
        "by_origin": {o: sum(1 for r in rows if r["origin"].startswith(o))
                      for o in ("countries/", "data/catalog_routes", "data/measurer_registry")},
        "countries_with_any_subnational": sorted(c for c, v in measured.items()
                                                 if v["subnational_measurers"] > 0),
        "mean_subnational_coverage": (round(sum(v["subnational_coverage"]
                                                for v in measured.values()) / len(measured), 4)
                                      if measured else UNMEASURED),
        "packs_unresolved": unresolved,
        "rule": ("a level the source's own words do not support is UNMEASURED, never national; "
                 "a country with no row is UNMEASURED, never 0%; nothing here is fetched"),
        "coverage": cov,
        "measurers": rows,
    }


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main() -> int:
    doc = build()
    _atomic(REPORT, doc)
    _atomic(DIGEST, {k: v for k, v in doc.items() if k != "measurers"}
            | {"report": "desks/mt5/reports/MEASURER_REGISTRY.json"})
    print(f"measurer registry: {doc['n_measurers']} measurer(s) in {doc['n_countries']} "
          f"country(ies); by level {doc['by_level']}; "
          f"{len(doc['countries_with_any_subnational'])} country(ies) with any subnational "
          f"measurer; mean subnational coverage {doc['mean_subnational_coverage']} -> {REPORT}")
    print("YIELD " + json.dumps({"targets": doc["n_measurers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
