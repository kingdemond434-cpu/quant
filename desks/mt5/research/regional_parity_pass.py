"""REGIONAL PARITY, BY EQUIVALENCE -- every country x information class, disposed, each pass.

    python desks/mt5/research/regional_parity_pass.py --once
    python desks/mt5/research/regional_parity_pass.py --once --dry-run

THE GAP IT CLOSES (completion audit 2026-10-06, rank 11; ASIA-1068..1072, ASIA-1207..1292,
ASIA-1294..1315, ASIA-1759). The global directive's core law -- "for every country identify the
LOCAL EQUIVALENT of every useful information class" (China's SHFE member ranks ~ the US COT,
Korea's 10-day customs exports ~ Japan's 上中旬 trade print) -- had no machine object, and
regional_parity.json was never committed. This organ is that object's hourly projection:

  * the frozen ontology `libs/research/equivalence_ontology.py` (PART II's 12 classes / 86
    sub-classes and PART III's functions, named per-country equivalents, transnational datasets,
    national publishers, the rules under which a class genuinely has no local equivalent);
  * the country packs (`country_lab.resolve_pack`) -- what each country DECLARES;
  * `reports/COVERAGE_TENSOR.json` -- the tensor's own per-country source-layer verdicts;
  * `reports/INGESTION_EXPLOITATION.json` and the tail of `data/ingestion_ledger.jsonl` -- the
    only evidence that lifts a cell to COVERED (a unit past AWAITING_EXPERIMENT).

`libs.research.regional_parity.equivalence_parity` does the projection; this file only reads,
writes and wires. It writes FIVE things, ALL of them the box's measured state and ALL
gitignored (a digest measured on a build VM and committed is a fact about the wrong machine):

  reports/REGIONAL_PARITY.json            the whole table, metrics per class and region, the
                                          ranked work queue, the candidate classes
  data/digests/regional_parity_digest.json  the small digest
  data/intelligence/world/discoveries_parity_<YYYYMMDD>.json
                                          the known-but-undeclared equivalents as discovery rows
                                          (marked `lane: regional_parity`); acquire_datasets gives
                                          them their own additive lane. Only endpoints whose
                                          publisher's terms PERMIT the use are listed; the rest
                                          ride as `held_endpoints` and are never fetched
  data/equivalence_candidates.json        every pack declaration NO class matches, persisted and
                                          never dropped (promote one through
                                          data/equivalence_ontology_ext.json)
  data/parity_hunt_targets.json           the UNMEASURED cells by class, for the dataset hunter's
                                          parity lane (world_dataset_hunter._fetch_order)

It decides nothing about capital and caps no compute; it names work.

UNMEASURED IS A VALUE (L1.28a). No tensor, no ingestion ledger, a pack that does not resolve --
each is named in `unmeasured`, and no cell is COVERED without the ledger's proof.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import equivalence_ontology as EQ  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

#: Module globals, not frozen constants: the tests point the whole organ at a tmp desk.
DATA = BASE / "data"
REPORTS = BASE / "reports"
COUNTRIES_DIR = BASE / "research" / "countries"
TENSOR = REPORTS / "COVERAGE_TENSOR.json"
INGESTION = REPORTS / "INGESTION_EXPLOITATION.json"
INGESTION_LEDGER = DATA / "ingestion_ledger.jsonl"
DEPTH_REPORT = REPORTS / "regional_parity.json"
WORLD = DATA / "intelligence" / "world"
DIGEST = DATA / "digests" / "regional_parity_digest.json"
CANDIDATES = DATA / "equivalence_candidates.json"
HUNT_TARGETS = DATA / "parity_hunt_targets.json"
OUT = REPORTS / "REGIONAL_PARITY.json"

UNMEASURED = EQ.UNMEASURED
#: Lines read from the END of the ingestion ledger (it is append-only and grows every hour).
LEDGER_TAIL_BYTES = 24 * 1024 * 1024
MAX_DISCOVERIES = 200
#: The marker on every parity discovery row; acquire_datasets gives rows carrying it their own lane.
PARITY_LANE = "regional_parity"
DIGEST_QUEUE = 40
DIGEST_LIST = 60
#: Packs that are not a country: the global and institutional grounds answer no jurisdiction.
NOT_COUNTRIES = frozenset({"global", "institutional"})


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def _ledger_tail(path: Path, max_bytes: int = LEDGER_TAIL_BYTES) -> list[dict[str, Any]]:
    """The newest rows of the append-only ingestion ledger, bounded by bytes, never whole."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()                      # drop the partial first line
            raw = fh.read()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(ValueError):
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
    return out


def _jurisdictions(code: str) -> tuple[str, ...]:
    """The ISO-2 countries a pack answers for -- the parity fence's own reading."""
    try:
        from scripts.check_regional_parity import jurisdictions_of
        return tuple(jurisdictions_of(code)[0])
    except Exception:
        return (code.lower(),)


def load_packs() -> tuple[dict[str, Any], dict[str, tuple[str, ...]], list[str]]:
    """Every country pack on this tree, resolved, with the jurisdictions it answers for."""
    notes: list[str] = []
    packs: dict[str, Any] = {}
    juris: dict[str, tuple[str, ...]] = {}
    try:
        from libs.research import country_lab as CL
    except Exception as exc:
        return {}, {}, [f"country_lab not importable: {type(exc).__name__}: {exc}"]
    if not COUNTRIES_DIR.exists():
        return {}, {}, [f"{COUNTRIES_DIR} is absent: no pack declarations are readable"]
    for pack_py in sorted(COUNTRIES_DIR.glob("*/pack.py")):
        code = pack_py.parent.name
        if code.startswith(("_", ".")) or code in NOT_COUNTRIES:
            continue
        try:
            packs[code] = CL.resolve_pack(code)
        except Exception as exc:
            packs[code] = None
            notes.append(f"pack {code}: {type(exc).__name__}: {exc}")
        juris[code] = _jurisdictions(code)
    return packs, juris, notes


def roster() -> list[str]:
    """Every country the forest federation names -- the countries the directive is about."""
    return sorted({c.lower() for f in F.REGIONAL_FORESTS for c in f.countries})


# ------------------------------------------------------------------------------- discoveries
def discovery_rows(doc: Mapping[str, Any], at: str) -> list[dict[str, Any]]:
    """One row per known-but-undeclared equivalent, in the world crawler's discovery shape.

    Grouped by source id, so a transnational file (BIS, ECB) is ONE row naming every country it
    answers rather than forty copies of the same url. Role-inferred equivalents are left out: a
    statistics office's home page is a place to look, not a dataset. Ranked endpoint-first, then
    by how many cells the row would close."""
    groups: dict[str, dict[str, Any]] = {}
    for c in doc.get("cells") or ():
        if c.get("disposition") != "ABSENT_KNOWN_EQUIVALENT":
            continue
        eq = c.get("equivalent") or {}
        if str(eq.get("tier") or "") not in ("named", "transnational"):
            continue
        sid = str(eq.get("source_id") or "")
        g = groups.setdefault(sid, {"eq": eq, "countries": set(), "classes": set(),
                                    "endpoints": set(), "held": set(), "regions": set()})
        g["countries"].add(str(c["country"]))
        g["classes"].add(str(c["class"]))
        g["regions"].add(str(c.get("region") or UNMEASURED))
        # Only endpoints whose publisher's own terms PERMIT the use reach the acquirer; the rest
        # ride along as `held_endpoints` and are never fetched (fail closed).
        g["endpoints"].update(str(u) for u in eq.get("endpoints") or ())
        g["held"].update(str(h.get("url")) for h in eq.get("held_endpoints") or ())
    rows: list[dict[str, Any]] = []
    for sid, g in groups.items():
        eq = g["eq"]
        url = str(eq.get("url") or "")
        endpoints = sorted(g["endpoints"])
        countries = sorted(g["countries"])
        rows.append({
            "source": "regional_parity", "kind": "dataset",
            "title": f"{eq.get('series')} -- {eq.get('publisher')}",
            "url": url, "published": at, "symbols": [], "timeframes": [], "patterns": [],
            "confidence": 0.7 if endpoints else 0.5, "lang": "en",
            "endpoints": endpoints, "n_endpoints": len(endpoints),
            "host": urllib.parse.urlparse(url).netloc,
            "ground": str(eq.get("publisher") or ""),
            "region": countries[0] if len(countries) == 1 else "multi",
            "cluster": sorted(g["regions"])[0] if len(g["regions"]) == 1 else "multi",
            "dataset_class": sorted(g["classes"])[0],
            "available_time": at, "ingested_time": at,
            "source_hash": hashlib.sha1(sid.encode("utf-8")).hexdigest()[:20],
            "claims": [], "n_claims": 0,
            # THE PRIORITY-LANE MARKER `acquire_datasets._parity_lane` keys on.
            "lane": PARITY_LANE,
            "held_endpoints": sorted(g["held"]),
            "parity": {"source_id": sid, "tier": eq.get("tier"), "cadence": eq.get("cadence"),
                       "access": eq.get("access"), "terms": list(eq.get("terms") or []),
                       "classes": sorted(g["classes"]),
                       "countries": countries,
                       "why": "a public functional equivalent no country pack declares "
                              "(directive CORE LAW / PART III)"},
        })
    rows.sort(key=lambda r: (-int(r["n_endpoints"] > 0), -len(r["parity"]["countries"])
                             * len(r["parity"]["classes"]), r["parity"]["source_id"]))
    return rows[:MAX_DISCOVERIES]


# ------------------------------------------------------------------------------- candidates
def merge_candidates(previous: Any, rows: Sequence[Mapping[str, Any]], at: str
                     ) -> dict[str, Any]:
    """The persisted candidate-class ledger: every unmatched declaration ever seen, keyed by id.

    NOTHING LEAVES IT. A row the packs no longer declare stays with `present: false` and its
    `last_seen`; a row now matched by a class (after an extension) is still kept, so promoting a
    candidate is visible in the ledger rather than a silent disappearance."""
    old = previous.get("rows") if isinstance(previous, Mapping) else None
    book: dict[str, dict[str, Any]] = {str(k): dict(v) for k, v in dict(old or {}).items()
                                       if isinstance(v, Mapping)}
    for kept in book.values():
        kept["present"] = False
    for r in rows:
        cid = str(r["candidate_id"])
        prior = book.get(cid) or {"first_seen": at}
        book[cid] = {**prior, **dict(r), "last_seen": at, "present": True}
    return {"at": at, "organ": "regional_parity", "n": len(book),
            "n_present": sum(1 for r in book.values() if r.get("present")),
            "promote_by": "desks/mt5/data/equivalence_ontology_ext.json",
            "rows": dict(sorted(book.items()))}


# ------------------------------------------------------------------------------- the hunter
def hunt_targets(doc: Mapping[str, Any], at: str) -> dict[str, Any]:
    """UNMEASURED cells, grouped by class, for `world_dataset_hunter`'s parity lane.

    An UNMEASURED cell has no known equivalent and no endpoint, so the acquirer can do nothing
    with it; the dataset hunter's catalogue (DBnomics: ~80 providers, national offices and central
    banks among them) is where an unknown equivalent is found. Each class carries its own match
    terms and the names of the countries still unmeasured on it, so the hunter can recognise a
    catalogue dataset that answers it without importing the ontology."""
    per: dict[str, set[str]] = {}
    for c in doc.get("cells") or ():
        if c.get("disposition") == UNMEASURED:
            per.setdefault(str(c["class"]), set()).add(str(c["country"]))
    classes: dict[str, Any] = {}
    for key, ccs in sorted(per.items()):
        dc = EQ.class_of(key)
        if dc is None:
            continue
        classes[key] = {"terms": dc.terms, "n_unmeasured": len(ccs),
                        "countries": sorted(ccs),
                        "country_names": sorted({n.lower() for cc in ccs
                                                 for n in EQ.COUNTRY_NAMES.get(cc, ())
                                                 if len(n) >= 4})}
    return {"at": at, "organ": "regional_parity", "lane": PARITY_LANE,
            "n_cells": sum(len(v) for v in per.values()), "classes": classes}


# ------------------------------------------------------------------------------- digest
def digest(doc: Mapping[str, Any], *, discoveries_file: str, n_discoveries: int) -> dict[str, Any]:
    """The small digest: counts, parity per class group and region, the queue head. Written on the
    box and gitignored: it is the box's measured state, never a committed fact."""
    groups: dict[str, dict[str, int]] = {}
    for _key, row in (doc.get("by_class") or {}).items():
        g = groups.setdefault(str(row.get("group")), dict.fromkeys(EQ.DISPOSITIONS, 0))
        for d, n in dict(row.get("counts") or {}).items():
            g[d] = g.get(d, 0) + int(n)
    return {
        "at": doc.get("at"), "organ": "regional_parity",
        "artifact": "desks/mt5/reports/REGIONAL_PARITY.json",
        "rule": doc.get("rule"), "class_source": doc.get("class_source"),
        "n_countries": doc.get("n_countries"), "n_classes": doc.get("n_classes"),
        "n_cells": doc.get("n_cells"), "totals": doc.get("totals"),
        "by_group": dict(sorted(groups.items())),
        "by_region": {r: {"n_countries": v.get("n_countries"), "parity": v.get("parity"),
                          "measured": v.get("measured"), "unmeasured": v.get("unmeasured"),
                          "counts": v.get("counts")}
                      for r, v in sorted((doc.get("by_region") or {}).items())},
        "parity_definition": doc.get("parity_definition"),
        "parity_spread": doc.get("parity_spread"),
        "n_candidate_classes": doc.get("n_candidate_classes"),
        "ontology_extension": doc.get("ontology_extension"),
        "work_queue_total": doc.get("work_queue_total"),
        "work_queue_head": [{k: q.get(k) for k in ("country", "class", "disposition",
                                                   "source_id", "score")}
                            for q in list(doc.get("work_queue") or [])[:DIGEST_QUEUE]],
        "discoveries_file": discoveries_file, "discoveries": n_discoveries,
        "proof": doc.get("proof"),
        "unattributed_declarations": doc.get("unattributed_declarations"),
        "unmeasured": sorted(str(x) for x in doc.get("unmeasured") or ())[:DIGEST_LIST],
    }


# ------------------------------------------------------------------------------- the pass
def build(*, dry_run: bool = False, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    when = now or _now()
    at = when.isoformat(timespec="seconds")
    packs, juris, notes = load_packs()
    tensor = _read_json(TENSOR)
    ingestion = _read_json(INGESTION)
    ledger = _ledger_tail(INGESTION_LEDGER)
    doc = RP.equivalence_parity(packs=packs, jurisdictions=juris,
                                tensor=tensor if isinstance(tensor, Mapping) else None,
                                ingestion=ingestion if isinstance(ingestion, Mapping) else None,
                                ledger_rows=ledger, countries=roster(), now=when)
    doc["unmeasured"] = list(doc["unmeasured"]) + notes
    depth = _read_json(DEPTH_REPORT)
    doc["depth"] = ({fid: {"depth_score": r.get("depth_score"), "flags": r.get("flags")}
                     for fid, r in (depth.get("regions") or {}).items()}
                    if isinstance(depth, Mapping) else
                    f"{UNMEASURED}: {DEPTH_REPORT.name} absent (scripts/check_regional_parity.py)")
    doc["inputs"] = {"coverage_tensor": TENSOR.name if isinstance(tensor, Mapping) else UNMEASURED,
                     "ingestion_exploitation": (INGESTION.name if isinstance(ingestion, Mapping)
                                                else UNMEASURED),
                     "ingestion_ledger_rows": len(ledger), "packs": len(packs),
                     "packs_resolved": sum(1 for p in packs.values() if p is not None)}
    disc = discovery_rows(doc, at)
    disc_path = WORLD / f"discoveries_parity_{when:%Y%m%d}.json"
    doc["discoveries"] = {"file": str(disc_path.relative_to(BASE)) if disc else None,
                          "rows": len(disc),
                          "with_endpoints": sum(1 for r in disc if r["n_endpoints"]),
                          "held_endpoints": sorted({u for r in disc
                                                    for u in r["held_endpoints"]})}
    cand = merge_candidates(_read_json(CANDIDATES), doc["candidate_classes"], at)
    targets = hunt_targets(doc, at)
    doc["candidate_ledger"] = {"file": str(CANDIDATES.relative_to(BASE)), "n": cand["n"],
                               "n_present": cand["n_present"]}
    doc["hunt_targets"] = {"file": str(HUNT_TARGETS.relative_to(BASE)),
                           "classes": len(targets["classes"]), "cells": targets["n_cells"]}
    doc["elapsed_s"] = round(time.monotonic() - t0, 2)
    doc["dry_run"] = bool(dry_run)
    if not dry_run:
        _write_atomic(OUT, doc)
        _write_atomic(CANDIDATES, cand)
        _write_atomic(HUNT_TARGETS, targets)
        if disc:
            _write_atomic(disc_path, disc)
        _write_atomic(DIGEST, digest(doc, discoveries_file=disc_path.name if disc else "",
                                     n_discoveries=len(disc)))
    return doc


def summary(doc: Mapping[str, Any]) -> str:
    t = doc.get("totals") or {}
    spread = doc.get("parity_spread") or {}
    lines = [f"regional parity @ {doc.get('at')}: {doc.get('n_countries')} countries x "
             f"{doc.get('n_classes')} classes = {doc.get('n_cells')} cells; "
             f"parity {t.get('parity')} = fed {t.get('fed')} / measured {t.get('measured')} "
             f"(unmeasured {t.get('unmeasured')}; median region {spread.get('median')})",
             "  " + ", ".join(f"{k}={v}" for k, v in dict(t.get("counts") or {}).items()),
             f"  work queue {doc.get('work_queue_total')}; discoveries "
             f"{(doc.get('discoveries') or {}).get('rows')}; candidate classes "
             f"{doc.get('n_candidate_classes')}; hunt-target cells "
             f"{(doc.get('hunt_targets') or {}).get('cells')}"]
    for note in list(doc.get("unmeasured") or [])[:6]:
        lines.append(f"  UNMEASURED: {note}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's call)")
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing")
    ap.add_argument("--budget-s", type=float, default=300.0, help="accepted for the leg runner")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = build(dry_run=args.dry_run)
    if args.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "cells"}, indent=1, default=str))
    else:
        print(summary(doc))
    return 0


if __name__ == "__main__":                                                # pragma: no cover
    raise SystemExit(main())
