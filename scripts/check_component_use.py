#!/usr/bin/env python3
"""EVERY SCHEDULED COMPONENT USED, NOT A MUSEUM: a justified role, a consumer, and tests on both.

    python scripts/check_component_use.py             # hourly leg `component_use`
    python scripts/check_component_use.py --ratchet   # law-gate fence: the gap count may only fall

WHY (ARCH-33, principal 2026-10-07: "every component in the quant is maximally used, not a museum:
each has a justified role and a tested consumer; zero weight allowed if redundant").
`check_dead_architecture.py` answers half of it every hour: which organs hold a clock, which
write an artifact, and whether anything reads it. It never asked whether the component is TESTED,
whether the thing that reads it is tested, or what role the component claims -- so an organ with
an untested reader read LIVE, and a consumer that silently stopped parsing the artifact would look
identical to one that uses it.

WHAT IT JOINS, for every organ the census sees on a clock (cycle leg or box task):

    ROLE              a cycle leg's declared layer (`libs/research/layers.LEG_LAYER`) or the box
                      task's manifest line (`desks/mt5/ops/box_tasks.manifest`)
    TESTED            a test file imports the module or names its file
    CONSUMER          the census's readers and importers (its own heuristic, over-reporting)
    TESTED_CONSUMER   at least one of those consumers is itself tested

USED needs all four. Anything else carries its named gaps (NO_ROLE, UNTESTED, NO_CONSUMER,
CONSUMER_UNTESTED). ZERO_WEIGHT is the principal's escape for a redundant component: an entry in
`docs/research/zero_weight_components.json` (path, reason, redundant_with) keeps it scheduled at
zero weight without counting as a gap -- a declared decision, never silence.

THE TEST JOIN IS A HEURISTIC AND IT OVER-REPORTS (a test that only names a file counts), so
UNTESTED is a floor on the debt, never an overstatement. REPORT, PLUS ONE RATCHET: `--ratchet`
exits 1 when the number of clocked organs that are neither USED nor ZERO_WEIGHT rises above
`MAX_GAPPED`. It removes nothing, masks no timer and deletes no source.

Writes desks/mt5/reports/COMPONENT_USE.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = ROOT / "desks" / "mt5" / "reports" / "COMPONENT_USE.json"
ZERO_WEIGHT = ROOT / "docs" / "research" / "zero_weight_components.json"
TEST_ROOTS = ("tests", "desks/mt5/tests", "libs", "scripts")

USED, ZERO, GAPPED = "USED", "ZERO_WEIGHT", "GAPPED"
NO_ROLE, UNTESTED, NO_CONSUMER, CONSUMER_UNTESTED = (
    "NO_ROLE", "UNTESTED", "NO_CONSUMER", "CONSUMER_UNTESTED")

#: RATCHET: clocked organs that are neither USED nor ZERO_WEIGHT. It may FALL, never rise.
#: Measured 2026-11-10 on 105c594a33 when the fence was built.
MAX_GAPPED = 90

_LEG = re.compile(r"_costed\('([\w-]+)'\)")
_TASK = re.compile(r"^([\w.-]+)\s")


def _test_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for r in TEST_ROOTS:
        base = root / r
        if base.is_dir():
            out.extend(p for p in base.rglob("test_*.py") if "__pycache__" not in p.parts)
    return sorted(set(out))


_PYFILE = re.compile(r"\b(\w+)\.py\b")
_IMPORT_LINE = re.compile(r"^\s*(?:from\s+[\w.]+\s+import\s+[^\n]*|import\s+[^\n]*)$", re.M)
_IMPORT_MOD = re.compile(r"import_module\(\s*['\"]([\w.]+)['\"]")
_WORDS = re.compile(r"\w+")


def test_tokens(text: str) -> set[str]:
    """Module stems a test file reaches: every word on an import line (dotted parts split), every
    `<stem>.py` it names, and every `importlib.import_module("...")` target."""
    out = set(_PYFILE.findall(text))
    for line in _IMPORT_LINE.findall(text):
        out.update(_WORDS.findall(line))
    for mod in _IMPORT_MOD.findall(text):
        out.update(mod.split("."))
    return out


def tested_modules(modules: set[str], root: Path) -> set[str]:
    """The subset of repo-relative module paths some test file imports or names."""
    tokens: set[str] = set()
    for p in _test_files(root):
        try:
            tokens |= test_tokens(p.read_text("utf-8", errors="replace"))
        except OSError:
            continue
    return {m for m in modules if Path(m).stem != "__init__" and Path(m).stem in tokens}


def roles(root: Path) -> dict[str, str]:
    """repo-relative script -> its declared role (a leg's layer, or a box task's name)."""
    try:
        from check_scheduler_manifest import parse_manifest, schedule_rows

        from libs.research.layers import LEG_LAYER
        man = parse_manifest(root / "desks" / "mt5" / "ops" / "box_tasks.manifest")
        rows, _ = schedule_rows(root, man)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for r in rows:
        script = str(getattr(r, "script", ""))
        rel = script.split(":", 1)[1] if script.startswith("hourly_cycle:") else script
        rel = rel.lstrip("./")
        path = next((c for c in (rel, f"desks/mt5/{rel}", f"scripts/{rel}")
                     if (root / c).is_file()), None)
        if path is None:
            continue
        where = str(getattr(r, "where", ""))
        if r.plane == "hourly_leg":
            m = _LEG.search(where)
            layer = LEG_LAYER.get(m.group(1)) if m else None
            if layer:
                out.setdefault(path, f"layer:{layer} (leg {m.group(1) if m else '?'})")
        elif r.plane == "box_task":
            m = _TASK.match(where)
            if m:
                out.setdefault(path, f"box_task:{m.group(1)}")
    return out


def zero_weight(path: Path = ZERO_WEIGHT) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("components") if isinstance(doc, dict) else None
    return {str(r["path"]): r for r in rows or [] if isinstance(r, dict) and r.get("path")
            and r.get("reason") and r.get("redundant_with")}


def build(root: Path = ROOT, census: dict[str, Any] | None = None) -> dict[str, Any]:
    if census is None:
        from check_dead_architecture import census as _census
        census = _census(root)
    organs: dict[str, dict[str, Any]] = census.get("organs") or {}
    clocked = {k: v for k, v in organs.items() if v.get("planes")}
    # consumers are capped at 12 names in the census rows; that is enough to find a tested one
    every = set(clocked) | {c for v in clocked.values() for c in v.get("consumers") or []}
    tested = tested_modules(every, root)
    role_of = roles(root)
    zw = zero_weight()
    rows: dict[str, dict[str, Any]] = {}
    for name, o in sorted(clocked.items()):
        cons = list(o.get("consumers") or [])
        gaps = []
        if name not in role_of:
            gaps.append(NO_ROLE)
        if name not in tested:
            gaps.append(UNTESTED)
        if not cons:
            gaps.append(NO_CONSUMER)
        elif not any(c in tested for c in cons):
            gaps.append(CONSUMER_UNTESTED)
        verdict = ZERO if name in zw else USED if not gaps else GAPPED
        rows[name] = {"verdict": verdict, "gaps": gaps, "role": role_of.get(name),
                      "planes": o.get("planes"), "artifacts": o.get("artifacts"),
                      "consumers": cons, "tested_consumers": [c for c in cons if c in tested],
                      **({"zero_weight": zw[name]} if name in zw else {})}
    counts = {v: sum(r["verdict"] == v for r in rows.values()) for v in (USED, ZERO, GAPPED)}
    by_gap = {g: sum(g in r["gaps"] for r in rows.values() if r["verdict"] == GAPPED)
              for g in (NO_ROLE, UNTESTED, NO_CONSUMER, CONSUMER_UNTESTED)}
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "status": "MEASURED", "n_clocked": len(rows), "counts": counts, "gaps": by_gap,
            "gapped_ratchet": MAX_GAPPED, "ratchet_ok": counts[GAPPED] <= MAX_GAPPED,
            "used_share": round(counts[USED] / len(rows), 4) if rows else None,
            "gapped": sorted(k for k, r in rows.items() if r["verdict"] == GAPPED),
            "organs": rows,
            "basis": "clock and consumer from check_dead_architecture.census; role from "
                     "layers.LEG_LAYER and box_tasks.manifest; tested = a test file imports or "
                     "names the module (over-reports, so UNTESTED is a floor on the debt)",
            "rule": "USED needs a role, a test, a consumer and a tested consumer; ZERO_WEIGHT "
                    "needs a declared redundancy in docs/research/zero_weight_components.json; "
                    "GAPPED may only fall (MAX_GAPPED)"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--ratchet", action="store_true",
                    help="exit 1 when GAPPED rose above MAX_GAPPED")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.no_write:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    n = doc["counts"][GAPPED]
    print(f"component use: {doc['n_clocked']} clocked organs; {doc['counts']}; gaps "
          f"{doc['gaps']}; GAPPED {n} (ratchet {MAX_GAPPED})")
    if a.ratchet:
        if n > MAX_GAPPED:
            new = doc["gapped"][:20]
            print(f"FAIL: clocked organs without a role, a test, a consumer or a tested consumer "
                  f"rose to {n} (ratchet {MAX_GAPPED}). Give the new organ a layer, a test and a "
                  f"reader with a test, or declare it ZERO_WEIGHT in "
                  f"docs/research/zero_weight_components.json with what it is redundant with. "
                  f"Gapped (first 20): {new}")
            return 1
        if n < MAX_GAPPED:
            print(f"NOTE: GAPPED fell to {n}; lower MAX_GAPPED in this file to {n} so the "
                  f"ground that was won is kept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
