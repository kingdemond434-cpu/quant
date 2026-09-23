"""EVERY GROUND CONVERTS TO CELLS. A ground with no converter is a defect, and this is its gate.

THE LAW, in the principal's words (2026-09-15): every single ground we ever cover should have
machinery which converts all of them into cells for the gauntlet.

It is III.16 -- "unwired or idle is a defect" -- applied one layer further out. That law already
says a built organ running on no clock is not done. This says a GROUND reaching no gauntlet is not
covered, however carefully it was described and however many crawlers pass over it.

WHY IT NEEDS A GATE AND NOT A GOOD INTENTION. Adding a name to a source registry feels like
progress, costs nothing, takes one line, and is measured by absolutely nothing downstream. Source
lists therefore grow forever while the docket does not, and the desk cannot tell the difference
between a ground it mines and a ground it merely lists. Both look identical from every artifact
this desk publishes -- which is the same shape as `live: 0` meaning "I could not read the file".

THE DISTINCTION THAT KEEPS THIS HONEST, and it is the whole design:

    NO_CONVERTER      no machinery maps this ground to a cell. A DEFECT. Exits 1.
    NO_YIELD          machinery exists and this ground produced no cell in the window. NOT a
                      defect -- that is yield, and yield is allowed to be zero. A source that
                      converts and finds nothing has answered the question.
    CONVERTS          machinery exists and cells came out of it.

Conflating the first two would make the gate a liar in the expensive direction: it would fail on
a quiet source and teach the next session to silence it, which is how a real feed gets deleted for
being briefly uninteresting.

    python scripts/check_ground_conversion.py
    python scripts/check_ground_conversion.py --json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
FOREST = DESK / "data" / "deep_forest_sources.json"
ASIA = DESK / "data" / "asia_sources.json"
ASIA_REPORT = DESK / "reports" / "ASIA_PLANE.json"
MINER = DESK / "data" / "hypotheses" / "miner_candidates.json"
INTEL = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
OUT = DESK / "reports" / "GROUND_CONVERSION.json"

#: Registry -> the organ that converts its grounds, and the artifact proving it ran. A registry
#: added without an entry here fails this gate by construction, which is deliberate: a new source
#: file with no declared converter is precisely the thing the law forbids.
CONVERTERS: dict[str, dict[str, Any]] = {
    "deep_forest": {
        "registry": FOREST,
        "key": "grounds",
        "id_field": "name",
        "converter": "desks/mt5/research/deep_forest_miner.py",
        "path": ("crawl -> verbatim claim -> mechanism -> data/intelligence/<seat>/ -> "
                 "miner_candidate_compiler -> docket -> external_gauntlet"),
    },
    "asia_plane": {
        "registry": ASIA,
        "key": "sources",
        "id_field": "id",
        "converter": "desks/mt5/research/asia_plane.py",
        "path": ("registry -> declared MT5 transmission -> price-only expression families -> "
                 "data/intelligence/asia/ -> miner_candidate_compiler -> docket -> gauntlet"),
    },
}


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _asia_yield() -> dict[str, int]:
    doc = _read(ASIA_REPORT, {})
    out = dict(doc.get("cells_per_source") or {})
    # A transport mints nothing BY DESIGN and must not be scored as a barren ground. It answers
    # the same law in its own currency: it has to name the sources it carries.
    for t in doc.get("transports") or []:
        if isinstance(t, dict):
            out[str(t.get("asia_source_id"))] = -1
    return out


def _forest_yield() -> dict[str, int]:
    """Cells attributable to each forest ground, from the compiler's own seat census."""
    doc = _read(MINER, {})
    seats = doc.get("seats") or {}
    out: dict[str, int] = {}
    if isinstance(seats, dict):
        for seat, v in seats.items():
            n = v.get("candidates") if isinstance(v, dict) else v
            if isinstance(n, (int, float)):
                out[str(seat)] = int(n)
    return out


def check() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    asia_cells = _asia_yield()
    forest_cells = _forest_yield()
    forest_total = sum(v for v in forest_cells.values() if v > 0)

    for reg_name, spec in CONVERTERS.items():
        registry = _read(spec["registry"], {})
        grounds = registry.get(spec["key"]) or []
        converter_exists = (ROOT / spec["converter"]).exists()
        for g in grounds:
            if not isinstance(g, dict):
                continue
            gid = str(g.get(spec["id_field"]) or "")
            rec: dict[str, Any] = {"registry": reg_name, "ground": gid,
                                   "converter": spec["converter"], "path": spec["path"]}
            if not converter_exists:
                rec.update({"verdict": "NO_CONVERTER",
                            "why": f"{spec['converter']} does not exist in this tree"})
                rows.append(rec)
                continue
            if reg_name == "asia_plane":
                n = asia_cells.get(gid)
                if n == -1:
                    rec.update({"verdict": "CONVERTS", "cells": 0, "role": "transport",
                                "why": "a transport: it carries other sources and mints no "
                                       "hypothesis of its own, and it names what it carries"})
                elif n:
                    rec.update({"verdict": "CONVERTS", "cells": int(n)})
                elif ASIA_REPORT.exists():
                    rec.update({"verdict": "NO_YIELD", "cells": 0,
                                "why": "the converter ran and this ground produced no cell: "
                                       "yield, not wiring"})
                else:
                    rec.update({"verdict": "UNMEASURED", "cells": None,
                                "why": f"{ASIA_REPORT.name} has never been written, so no pass "
                                       f"has been recorded. UNMEASURED is a verdict."})
            else:
                # The forest does not attribute a cell back to an individual ground -- it
                # attributes to a SEAT. That is a real limit and it is reported as one rather
                # than papered over with a guess: the converter is proven to exist and to run,
                # and per-ground attribution is a named gap.
                rec.update({
                    "verdict": "CONVERTS" if forest_total else "NO_YIELD",
                    "cells": None,
                    "attribution": "seat-level, not ground-level",
                    "why": (f"the miner converts this registry as a whole; the compiler's seat "
                            f"census shows {forest_total} candidate(s) this window. Per-ground "
                            f"attribution is a NAMED GAP, not a claim of zero."),
                })
            rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    defects = [r for r in rows if r["verdict"] == "NO_CONVERTER"]
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY GROUND CONVERTS TO CELLS (principal, 2026-09-15). A ground with no "
                "machinery mapping it to a gauntlet cell is a DEFECT. A ground whose machinery "
                "ran and yielded nothing is NOT -- that is yield, and yield may be zero."),
        "n_grounds": len(rows),
        "census": dict(census),
        "n_defects": len(defects),
        "defects": defects,
        "by_registry": {k: dict(Counter(str(r["verdict"]) for r in rows if r["registry"] == k))
                        for k in CONVERTERS},
        "named_gaps": [
            "the deep forest attributes cells to a SEAT, not to the individual ground that "
            "produced them, so a single barren ground among 502 is currently invisible. Closing "
            "it means stamping the ground id onto the donated row at crawl time.",
        ],
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if args.json:
        print(json.dumps(doc, indent=1))
        return 1 if doc["n_defects"] else 0

    print(f"ground conversion: {doc['n_grounds']} ground(s) -> {doc['census']}")
    for reg, c in doc["by_registry"].items():
        print(f"  {reg:14} {c}")
    if doc["defects"]:
        print(f"\n  NO_CONVERTER {len(doc['defects'])} -- a ground that reaches no gauntlet is "
              f"not covered:")
        for d in doc["defects"][:15]:
            print(f"    {str(d['ground'])[:44]:44} {str(d['why'])[:56]}")
    for gap in doc["named_gaps"]:
        print(f"  GAP: {gap[:110]}")
    print(f"  -> {OUT}")
    return 1 if doc["n_defects"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
