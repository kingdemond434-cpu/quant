"""REGION YIELD -- what every region in the source registries produced, hourly, ranked by gap.

    python desks/mt5/research/region_yield.py            # write reports/REGION_YIELD.json
    python desks/mt5/research/region_yield.py --json

THE QUESTION THE DESK COULD NOT ANSWER (row 75, 2026-11-03). Argentina, Brazil, Chile and the
Middle East have grounds in `deep_forest_sources.json` (ar 5, br 21, cl 4, sa 8, ae 5, il 6, ...)
and MT5-Forest-Latam / MT5-Forest-Mena run every ten minutes. Nothing said what any region YIELDS.
`ALT_DATA_YIELD.json` is per platform and per vector; `FOREST_ATTEMPTS.json` counts attempts by
region but not output; `CELL_CULTURE.json` counts cells by culture but not sources. Each answers
one link of the chain and none answers the region.

WHAT THIS DOES. A COMPOSER, not a second miner: per region it joins

    sources        deep_forest_sources.json grounds + reading_list, source_rosters/
                   culture_gap_sources.json, asia_sources.json, and the country pack directory
                   (research/countries/<region>) -- every registry LIVE holds
    rows           deep_forest_vector_stats.json `rows` + `datasets` per ground (the miner's own
                   checkpoint counters), and deep_forest_datasets.jsonl lines
    claims         deep_forest_claims.jsonl lines, streamed (never loaded whole)
    cells minted   CELL_CULTURE.json `by_culture` (cells whose culture jurisdiction is the region)
    cells judged   CELL_CULTURE.json `judged_by_culture`
    certificates   CELL_CULTURE.json `headline.certificates.by_culture`

and the forest roll-up through `libs.research.forests.forest_of_country`, with each forest's own
last pass (`reports/DEEP_FOREST_<forest>.json` totals). Regions are RANKED BY GAP: the funnel
stage where the region's output dies first, then by how many sources feed that dead stage.

RED, by name: a region with sources > 0 whose MEASURED output (rows, datasets, claims, cells) is
all zero. A region whose counters are absent on this host is UNMEASURED, never zero (L1.28a):
`CELL_CULTURE.json` and the vector stats are box-written, so a cloud checkout reads UNMEASURED.
The culture attribution in CELL_CULTURE includes symbol-home derivation (a USDJPY cell is JP), so
its cell counts are an upper bound on what the region's SOURCES minted; the basis is published.

Hourly leg `region_yield` (core plan); its artifact is contracted in
`scripts/check_leg_artifact_liveness.py`, which turns RED when it stops moving.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
REPORTS = DESK / "reports"
SOURCES = DATA / "deep_forest_sources.json"
CULTURE_GAP = DATA / "source_rosters" / "culture_gap_sources.json"
ASIA = DATA / "asia_sources.json"
COUNTRIES = DESK / "research" / "countries"
VECTOR_STATS = DATA / "deep_forest_vector_stats.json"
FRONTIER = DATA / "deep_forest_frontier.json"
CLAIMS = DATA / "deep_forest_claims.jsonl"
DATASETS = DATA / "deep_forest_datasets.jsonl"
CELL_CULTURE = REPORTS / "CELL_CULTURE.json"
OUT = REPORTS / "REGION_YIELD.json"
UNMEASURED = "UNMEASURED"

#: The funnel, in order. A region's gap is the first stage that reads zero.
STAGES: tuple[str, ...] = ("sources", "rows", "claims", "cells_minted", "cells_judged",
                           "certificates")
#: A ledger larger than this is counted over its last MAX_LEDGER_BYTES and the count says so.
MAX_LEDGER_BYTES = 512 * 1024 * 1024


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _region(v: Any) -> str:
    return str(v or "").strip().lower()


def _count_jsonl(p: Path, key: str = "region") -> tuple[Counter[str] | None, str]:
    """Lines per region of an append-only ledger, streamed; None when the file is absent."""
    if not p.exists():
        return None, f"{p.name} absent on this host"
    out: Counter[str] = Counter()
    lines = 0
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            partial = size > MAX_LEDGER_BYTES
            if partial:
                fh.seek(size - MAX_LEDGER_BYTES)
                fh.readline()
            for raw in fh:
                with contextlib.suppress(ValueError):
                    row = json.loads(raw.decode("utf-8", errors="replace"))
                    if isinstance(row, dict):
                        out[_region(row.get(key))] += 1
                        lines += 1
    except OSError as exc:
        return None, f"{p.name} unreadable: {exc}"
    basis = f"{lines} line(s) of {p.name}" + (" (last 512 MB only)" if partial else "")
    return out, basis


def _sources() -> tuple[dict[str, Counter[str]], dict[str, str], dict[str, str]]:
    """region -> Counter(registry -> n sources); ground name -> region; notes."""
    by: dict[str, Counter[str]] = {}
    ground_region: dict[str, str] = {}
    notes: dict[str, str] = {}

    def add(region: str, registry: str, n: int = 1) -> None:
        if region:
            by.setdefault(region, Counter())[registry] += n

    doc = _json(SOURCES)
    if isinstance(doc, dict):
        for g in (doc.get("grounds") or []) + (doc.get("reading_list") or []):
            if isinstance(g, dict):
                r = _region(g.get("region"))
                add(r, "deep_forest_sources")
                if g.get("name"):
                    ground_region[str(g["name"])] = r
        for r in (doc.get("regions") or {}):
            by.setdefault(_region(r), Counter())
    else:
        notes["deep_forest_sources"] = f"{SOURCES} unreadable"
    cg = _json(CULTURE_GAP)
    if isinstance(cg, dict):
        for s in cg.get("sources") or []:
            if isinstance(s, dict):
                add(_region(s.get("region") or s.get("jurisdiction")), "culture_gap_sources")
    else:
        notes["culture_gap_sources"] = f"{CULTURE_GAP} unreadable"
    asia = _json(ASIA)
    if isinstance(asia, dict):
        planes = asia.get("planes") or {}
        for s in asia.get("sources") or []:
            if isinstance(s, dict):
                plane = planes.get(s.get("plane")) if isinstance(planes, dict) else None
                r = _region(s.get("country") or (plane or {}).get("region"))
                add(r, "asia_sources")
    else:
        notes["asia_sources"] = f"{ASIA} unreadable"
    try:
        for d in sorted(COUNTRIES.iterdir()):
            if d.is_dir() and not d.name.startswith(("_", ".")) and any(d.glob("*.py")):
                add(_region(d.name), "country_pack")
    except OSError:
        notes["country_packs"] = f"{COUNTRIES} unreadable"
    return by, ground_region, notes


def _vector_rows(ground_region: dict[str, str]) -> tuple[dict[str, dict[str, int]] | None, str]:
    st = _json(VECTOR_STATS)
    vec = st.get("vectors") if isinstance(st, dict) else None
    if not isinstance(vec, dict):
        return None, f"{VECTOR_STATS.name} absent or unreadable on this host"
    fr = _json(FRONTIER)
    fvec = fr.get("vectors") if isinstance(fr, dict) else {}
    out: dict[str, dict[str, int]] = {}
    for name, s in vec.items():
        if not isinstance(s, dict):
            continue
        r = ground_region.get(str(name)) or _region(((fvec or {}).get(name) or {}).get("region"))
        b = out.setdefault(r or "?", {"rows": 0, "datasets": 0, "attempts": 0, "successes": 0})
        for k in b:
            with contextlib.suppress(TypeError, ValueError):
                b[k] += int(s.get(k) or 0)
    return out, f"{len(vec)} ground counter(s) in {VECTOR_STATS.name}"


def _culture_counts() -> tuple[dict[str, dict[str, int]] | None, str]:
    """region -> {cells_minted, cells_judged, certificates} from CELL_CULTURE.json."""
    doc = _json(CELL_CULTURE)
    if not isinstance(doc, dict):
        return None, f"{CELL_CULTURE.name} absent on this host (written by cell_culture_index)"
    certs = (((doc.get("headline") or {}).get("certificates") or {}).get("by_culture") or {})
    fields = {"cells_minted": doc.get("by_culture") or {},
              "cells_judged": doc.get("judged_by_culture") or {}, "certificates": certs}
    out: dict[str, dict[str, int]] = {}
    for field, table in fields.items():
        items = table.items() if isinstance(table, dict) else (
            (r[0], r[1]) for r in table if isinstance(r, (list, tuple)) and len(r) >= 2)
        for culture, n in items:
            c = str(culture or "")
            juris = c.split("/", 1)[0].lower() if "/" in c else c.lower()
            if not juris or juris in ("unmeasured",):
                continue
            with contextlib.suppress(TypeError, ValueError):
                out.setdefault(juris, {}).setdefault(field, 0)
                out[juris][field] += int(n)
    return out, (f"CELL_CULTURE.json at {doc.get('generated_at')}: culture jurisdiction, "
                 "source-declared OR symbol-home (an upper bound on source-minted cells)")


def _forest_of(region: str) -> str:
    try:
        from libs.research import forests as F
        return str(F.forest_of_country(region.upper()) or "")
    except Exception:
        return ""


def _forest_passes() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(REPORTS.glob("DEEP_FOREST_*.json")):
        doc = _json(p)
        if isinstance(doc, dict) and doc.get("forest"):
            out[str(doc["forest"])] = {"at": doc.get("at"), "totals": doc.get("totals"),
                                       "n_roles_ran": doc.get("n_roles_ran")}
    return out


def _gap_stage(row: dict[str, Any]) -> tuple[int, str]:
    """(index, name) of the first funnel stage that is measured zero; len(STAGES) if none."""
    for i, st in enumerate(STAGES):
        v = row.get(st)
        if isinstance(v, int) and v == 0:
            return i, st
    return len(STAGES), "none"


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    by_src, ground_region, notes = _sources()
    vrows, v_basis = _vector_rows(ground_region)
    claims, c_basis = _count_jsonl(CLAIMS)
    dsets, d_basis = _count_jsonl(DATASETS)
    culture, cu_basis = _culture_counts()
    passes = _forest_passes()
    regions = sorted((set(by_src) | set(vrows or {}) | set(claims or {})) - {"", "?"})
    rows: list[dict[str, Any]] = []
    for r in regions:
        if not r or r == "?":
            continue
        src = by_src.get(r, Counter())
        v = (vrows or {}).get(r, {})
        cc = (culture or {}).get(r, {})
        row: dict[str, Any] = {
            "region": r, "forest": _forest_of(r),
            "sources": int(sum(src.values())), "sources_by_registry": dict(src),
            "rows": (int(v.get("rows", 0)) + int(v.get("datasets", 0))) if vrows is not None
            else UNMEASURED,
            "datasets_ledger": int((dsets or {}).get(r, 0)) if dsets is not None else UNMEASURED,
            "attempts": int(v.get("attempts", 0)) if vrows is not None else UNMEASURED,
            "claims": int((claims or {}).get(r, 0)) if claims is not None else UNMEASURED,
            "cells_minted": int(cc.get("cells_minted", 0)) if culture is not None else UNMEASURED,
            "cells_judged": int(cc.get("cells_judged", 0)) if culture is not None else UNMEASURED,
            "certificates": int(cc.get("certificates", 0)) if culture is not None else UNMEASURED,
        }
        outputs = [row[k] for k in ("rows", "datasets_ledger", "claims", "cells_minted")]
        measured = [x for x in outputs if isinstance(x, int)]
        forest_measured = isinstance(row["rows"], int) or isinstance(row["claims"], int)
        if row["sources"] > 0 and forest_measured and measured and sum(measured) == 0:
            verdict, why = "RED", (f"{row['sources']} source(s) registered and ZERO measured "
                                   f"output (rows, datasets, claims, cells): the region is "
                                   f"scheduled and yields nothing")
        elif measured and sum(measured) > 0:
            verdict, why = "YIELDING", "measured output > 0"
        elif row["sources"] == 0:
            verdict, why = "NO_SOURCES", "output seen with no registered source (orphan)"
        else:
            verdict, why = UNMEASURED, "no output counter is readable on this host"
        gi, gname = _gap_stage(row)
        row.update({"verdict": verdict, "why": why, "gap_stage": gname, "_gi": gi})
        rows.append(row)
    rows.sort(key=lambda x: (x["verdict"] != "RED", x["_gi"], -x["sources"], x["region"]))
    for i, row in enumerate(rows, 1):
        row["gap_rank"] = i
        row.pop("_gi", None)
    by_forest: dict[str, dict[str, Any]] = {}
    for row in rows:
        f = row["forest"] or "unassigned"
        b = by_forest.setdefault(f, {"regions": 0, "red": 0, **dict.fromkeys(STAGES, 0),
                                     "last_pass": passes.get(f)})
        b["regions"] += 1
        b["red"] += int(row["verdict"] == "RED")
        for st in STAGES:
            if isinstance(row.get(st), int):
                b[st] += row[st]
            elif st != "sources":
                b[st] = UNMEASURED
    red = [r["region"] for r in rows if r["verdict"] == "RED"]
    census = Counter(r["verdict"] for r in rows)
    status = "RED" if red else (UNMEASURED if census.get(UNMEASURED) == len(rows) else "GREEN")
    return {
        "generated_utc": now.isoformat(timespec="seconds"), "leg": "region_yield",
        "status": status, "n_regions": len(rows), "census": dict(census), "red": red,
        "stages": list(STAGES),
        "basis": {"sources": "deep_forest_sources (grounds + reading_list), culture_gap_sources, "
                             "asia_sources, research/countries/<region> packs",
                  "rows": v_basis, "claims": c_basis, "datasets_ledger": d_basis,
                  "cells": cu_basis, "notes": notes},
        "rule": ("RED = sources > 0 and every MEASURED output (rows, datasets, claims, cells) is "
                 "zero; UNMEASURED when no counter is readable here, never zero (L1.28a); ranked "
                 "RED first, then by the first funnel stage that reads zero, then by sources"),
        "by_forest": dict(sorted(by_forest.items())),
        "regions": rows,
    }


def write(doc: dict[str, Any], out: Path | None = None) -> None:
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
        return 0
    print(f"region yield: {doc['n_regions']} region(s) -> {doc['census']} status {doc['status']}")
    for r in doc["regions"][:25]:
        print(f"  #{r['gap_rank']:<3} {r['verdict']:10} {r['region']:14} src {r['sources']:3} "
              f"rows {r['rows']!s:>8} claims {r['claims']!s:>6} cells {r['cells_minted']!s:>8} "
              f"judged {r['cells_judged']!s:>7} certs {r['certificates']!s:>5}  "
              f"gap@{r['gap_stage']}")
    print(f"  -> {OUT}")
    # The RED regions are a WORKLIST in the artifact, not a failure of this leg: the leg exits 0
    # whenever it wrote, so `completion` and `check_silent_organs` read its health from whether
    # the artifact moved (check_leg_artifact_liveness), and its findings from `red`.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
