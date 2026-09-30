#!/usr/bin/env python3
"""KNOWN-BY-DATE LINT: every research reader that joins an external dataset by the date it
DESCRIBES, without routing through that dataset's publication lag, is named.

    python scripts/check_known_by_date.py            # the fence: exit 1 on a NEW offender
    python scripts/check_known_by_date.py --json     # the census as JSON
    python scripts/check_known_by_date.py --update   # drop healed names from the floor (never adds)

THE DEFECT CLASS. A daily macro state computed from the day's close, joined to a 03:00 bar by
`s.time.date() in fav_dates`; a CFTC report as-of Tuesday labelled Friday 00:00 and joined on the
label; a monthly print joined on the month it describes. Each reads correctly, types line up, and
each conditions a bar on a number nobody had yet. The desk found and fixed three of these one at
a time (`run_edges_macro_fusion_sweep`, `orthogonal_sweep.COT_RELEASE_LAG_DAYS`,
`orthogonal_sweep.DAILY_MACRO_SERIES`). This names the whole class instead.

WHAT IS A READER. A module under the research trees whose source carries one of a registered
source's `readers` tokens (`libs/tiers/data_os.PUBLICATION_LAGS`), so the dataset list and the
lag list are ONE declaration: adding a source with its readers makes every reader of it subject
to this fence the hour it lands.

WHAT IS A VALID-DATE JOIN. An aligning call (`reindex`, `merge`, `merge_asof`, `join`, `asof`,
`searchsorted`, `get_indexer`) or a membership test on a `.date()` -- the two shapes every
look-ahead of this kind has taken here.

WHAT DECLARES THE LAG. Any of: a read through the bitemporal store (`latest_known`, `as_of(`),
`data_os` (`store_from_series`, `knowledge_time`, `declared_lag`), a knowledge-time column
(`available_time`, `knowledge_time`, `usable_at`), a vintage read, or a named lag constant
(`PUBLICATION_LAG`, `RELEASE_LAG`, `KNOWABLE`). The census is module-grained on purpose: it cannot
prove a lag is applied to the right join, only that a reader that joins has SOMETHING that says
when its data was known -- an undeclared one has nothing, which is the finding.

A RATCHET THAT ONLY TIGHTENS. Today's offenders are the committed floor
(`docs/research/known_by_date_floor.json`); only an ARRIVAL fails, a healed module drops out
(`--update` rewrites the floor to the smaller set and refuses to add a name). Fetchers
(`fetch_*.py`) write datasets and join nothing to bars; they are out of scope by name.

Artifact: `desks/mt5/reports/KNOWN_BY_DATE.json`.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.tiers.data_os import PUBLICATION_LAGS  # noqa: E402

TREES = ("desks/mt5/research", "desks/mt5/mt5desk", "libs/research")
JOINS = ("reindex", "merge", "merge_asof", "join", "asof", "searchsorted", "get_indexer")
LAG_TOKENS = ("latest_known", ".as_of(", "store_from_series", "knowledge_time", "declared_lag",
              "available_time", "usable_at", "vintage", "PUBLICATION_LAG", "publication_lag",
              "RELEASE_LAG", "KNOWABLE", "data_os.")
FLOOR = ROOT / "docs" / "research" / "known_by_date_floor.json"
OUT = ROOT / "desks" / "mt5" / "reports" / "KNOWN_BY_DATE.json"


def _joins(tree: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in JOINS:
            # `"sep".join(...)` and `os.path.join` are string/path joins, not data joins
            if node.func.attr == "join" and isinstance(node.func.value, (ast.Constant,
                                                                         ast.Attribute)):
                continue
            out.append((node.lineno, node.func.attr))
        elif isinstance(node, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn))
                                                   for o in node.ops):
            left = node.left
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute) \
                    and left.func.attr == "date":
                out.append((node.lineno, ".date() in"))
    return sorted(out)


def scan(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    readers_of = {s: tuple(e.get("readers") or ()) for s, e in PUBLICATION_LAGS.items()}
    offenders: dict[str, dict[str, Any]] = {}
    routed: dict[str, list[str]] = {}
    n_readers = 0
    for tree_rel in TREES:
        base = root / tree_rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if p.name.startswith(("test_", "fetch_")) or "__pycache__" in p.parts \
                    or "/tests/" in p.as_posix():
                continue
            try:
                text = p.read_text("utf-8")
                tree = ast.parse(text)
            except (OSError, SyntaxError, ValueError):
                continue
            sources = sorted(s for s, toks in readers_of.items() if any(t in text for t in toks))
            if not sources:
                continue
            n_readers += 1
            rel = p.relative_to(root).as_posix()
            joins = _joins(tree)
            if not joins:
                continue
            if any(t in text for t in LAG_TOKENS):
                routed[rel] = sources
                continue
            offenders[rel] = {"sources": sources,
                              "joins": [f"{ln}:{kind}" for ln, kind in joins[:8]],
                              "why": (f"reads {', '.join(sources)} and joins by date "
                                      f"({joins[0][1]} at line {joins[0][0]}) with no declared "
                                      "publication lag, store read or knowledge-time column")}
    return {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "trees": list(TREES), "sources": sorted(readers_of),
            "readers": n_readers, "routed": routed, "offenders": offenders}


def read_floor(path: Path | None = None) -> set[str] | None:
    try:
        doc = json.loads((path or FLOOR).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    names = doc.get("offenders") if isinstance(doc, dict) else None
    return set(names) if isinstance(names, list) else None


def write_floor(names: set[str], path: Path | None = None) -> None:
    (path or FLOOR).write_text(json.dumps({
        "_": ("KNOWN-BY-DATE FLOOR: research readers that joined an external dataset by valid "
              "date without a declared lag when the fence was built. Only SHRINKS: a module that "
              "routes through data_os / the bitemporal store drops out; a new offender fails "
              "scripts/check_known_by_date.py and is never added here."),
        "offenders": sorted(names)}, indent=1) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="rewrite the floor to the healed (smaller) set; never adds a name")
    ap.add_argument("--init", action="store_true",
                    help="seal the floor from today's census; refuses if one exists")
    a = ap.parse_args(argv)
    doc = scan()
    now = set(doc["offenders"])
    floor = read_floor()
    if a.init:
        if floor is not None:
            print(f"REFUSING --init: {FLOOR.relative_to(ROOT)} exists; it only shrinks")
            return 1
        write_floor(now)
        print(f"sealed {FLOOR.relative_to(ROOT)} with {len(now)} offender(s)")
        return 0
    if floor is None:
        print(f"NO FLOOR: {FLOOR.relative_to(ROOT)} is absent or unreadable. A ratchet with "
              "nothing to ratchet against is not a ratchet: seal it with --init and commit it.")
        return 1
    arrived = sorted(now - floor)
    healed = sorted(floor - now)
    doc.update({"floor": sorted(floor), "arrived": arrived, "healed": healed,
                "verdict": "FAIL" if arrived else "OK"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"known-by-date: {doc['readers']} reader(s) of {len(doc['sources'])} declared "
              f"source(s); {len(doc['routed'])} routed through a lag, {len(now)} offender(s) "
              f"(floor {len(floor)}), {len(healed)} healed")
        for rel in arrived:
            print(f"  NEW OFFENDER {rel}: {doc['offenders'][rel]['why']}")
        for rel in healed:
            print(f"  healed: {rel}")
    if a.update and healed and not arrived:
        write_floor(floor & now)
        print(f"  floor shrunk {len(floor)} -> {len(floor & now)} (commit it)")
    return 1 if arrived else 0


if __name__ == "__main__":
    raise SystemExit(main())
