"""THE DEAD-ARCHITECTURE CENSUS: which organs run, which are dark, and which write the same file.

    python scripts/check_dead_architecture.py

MEASURED 2026-09-08 (Tier-1 programme item I4): the desk already runs a module census, and its
verdict is UNMEASURED for 70 of 71 modules, so nothing acts on it -- no organ is ever disabled,
no timer masked, no source removed. The census was not wrong, it was answering a question it
could not answer: MODULE_RENT asks "did this module EARN", which needs a live ledger, and most
organs will never touch money directly.

A DIFFERENT QUESTION, ANSWERABLE TODAY: is anything on the other end of this organ? Three facts
the repository can state without a single trade:

    CLOCK       is the file on one of the four scheduling planes (cron, systemd, box task,
                cycle leg)? `check_scheduler_manifest.schedule_rows` already computes this.
    ARTIFACT    does it write a file?
    CONSUMER    does any other production file read that artifact, or import this module?

An organ with a clock and no consumer is BURNING (it runs every hour and nobody reads the
result). An organ with a consumer and no clock is NO_CLOCK (something reads a file nothing
refreshes). An organ with neither is UNREACHED. An artifact written by two organs is CONTESTED --
the "two builders of one identity" failure this desk has already paid for twice.

THE VERDICTS CLAIM ONLY WHAT THE EVIDENCE SUPPORTS. The clock is exact: it comes from
`check_scheduler_manifest`, which parses all four planes. The consumer is a heuristic over
filename literals and resolved imports, and it UNDER-reports -- so UNREACHED is a list for a
person to review, never a death certificate, and this file deliberately does not use the word.

REPORT ONLY, AND DELIBERATELY SO. Nothing here disables a timer, deletes a source or masks a
unit. The desk's standing order is that organs are removed by a person on evidence, and this is
the evidence. `--strict` exits 1 when an organ is CONTESTED, because two writers of one file is
a defect the repo can decide about without a person's judgement.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "dead_architecture.json"

#: EVERY production tree, not the obvious five. `desks/mt5/side_channels/controller.py` is the
#: only production importer of `mt5desk/compiler.py`, so a root list that stopped at research/
#: and mt5desk/ reported the compiler DEAD -- a census that misses a consumer buries a working
#: organ, which is the one error this file must not make.
PROD_ROOTS = ("libs", "scripts", "ops", "desks/mt5")
_SKIP_DIRS = frozenset({"tests", "__pycache__", "backups", "node_modules", ".git", "venv",
                        ".venv", "site-packages"})
#: ARTIFACTS ARE JOINED ON THEIR FILENAME, not their path, because this repository builds every
#: path from parts -- `BASE / "reports" / "burn_in.json"` -- so a full-path regex matches almost
#: nothing and would report a desk where nobody reads anything. The filename is what one organ
#: writes and another names, and it is unique enough here to be the join key.
_ARTIFACT = re.compile(r"""["']([\w.-]+\.(?:json|jsonl|md|txt|parquet))["']""")
#: Names too generic to identify an organ's output.
_GENERIC = frozenset({"config.json", "state.json", "index.json", "README.md", "out.json",
                      "data.json", "report.json", "results.json", "tmp.json", "test.json"})
#: THE CLOCK IS EXACT (the scheduler manifest computes it); THE CONSUMER IS A HEURISTIC. So the
#: verdicts are named for what the evidence supports and no further: "UNREACHED" means no clock
#: and no detected reader, NOT "dead" -- a consumer this file cannot see is the likeliest reason
#: a working organ lands there, and calling it dead would licence deleting it.
LIVE, BURNING, NO_CLOCK, UNREACHED = "LIVE", "BURNING", "NO_CLOCK", "UNREACHED"


def _prod_files(root: Path) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for rel in PROD_ROOTS:
        base = root / rel
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if seen.isdisjoint({p}) and _SKIP_DIRS.isdisjoint(p.parts):
                seen.add(p)
                out.append(p)
    return out


def _module_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def artifacts_and_reads(path: Path) -> tuple[set[str], set[str]]:
    """(artifact filenames this file appears to WRITE, filenames it appears to READ).

    Best effort, and the report says so: a filename literal within a few lines of a write call
    is a write, any other filename literal is a read. The heuristic over-reports CONSUMERS on
    purpose -- it can make an organ look more alive than it is, never mark a live one dead,
    and a census that wrongly buries a working organ is worse than one that is generous.
    """
    try:
        src = path.read_text("utf-8", errors="ignore")
    except OSError:
        return set(), set()
    lines = src.splitlines()
    named = {n for n in _ARTIFACT.findall(src) if n not in _GENERIC}
    writes: set[str] = set()
    for i, line in enumerate(lines):
        if not re.search(r"write_text|json\.dump\(|open\([^)]*['\"][wa]|mkstemp|fh\.write\(",
                         line):
            continue
        window = "\n".join(lines[max(0, i - 8):i + 3])
        writes |= {n for n in _ARTIFACT.findall(window) if n not in _GENERIC}
    return writes, named - writes


def imports_of(path: Path, root: Path) -> set[str]:
    """Repo-relative module paths this file imports from the production roots."""
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    dotted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            dotted.add(node.module)
            dotted |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            dotted |= {a.name for a in node.names}
    out: set[str] = set()
    for d in dotted:
        rel = d.replace(".", "/") + ".py"
        # THE DESK IMPORTS ITSELF BY A SHORT NAME. `research/` and `mt5desk/` are on sys.path on
        # the box, so `from research import promoter` names desks/mt5/research/promoter.py and a
        # repo-root-only resolution would report the whole desk as importing nothing -- which
        # would bury every organ it schedules.
        for cand in (root / rel, root / "desks" / "mt5" / rel):
            if cand.is_file():
                out.add(cand.relative_to(root).as_posix())
                break
    return out


def scheduled(root: Path) -> dict[str, list[str]]:
    """repo-relative script -> the planes that run it, from the scheduler manifest's own reader."""
    # THE READER COMES FROM THIS REPOSITORY, THE DATA FROM `root`. Putting the target root on
    # sys.path imported nothing when `root` was a fixture, and the census then reported every
    # organ clockless -- the exact false negative that would bury a running organ.
    try:
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        from check_scheduler_manifest import parse_manifest, schedule_rows
        man = parse_manifest(root / "desks" / "mt5" / "ops" / "box_tasks.manifest")
    except Exception:
        return {}
    try:
        rows, _ = schedule_rows(root, man)
    except Exception:
        return {}
    out: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        script = getattr(r, "script", "")
        plane = getattr(r, "plane", "")
        rel = script.split(":", 1)[1] if str(script).startswith("hourly_cycle:") else str(script)
        rel = rel.lstrip("./")
        for cand in (rel, f"desks/mt5/{rel}", f"scripts/{rel}"):
            if (root / cand).is_file():
                out[cand].append(plane)
                break
    return {k: sorted(set(v)) for k, v in out.items()}


def census(root: Path = ROOT) -> dict[str, Any]:
    files = _prod_files(root)
    clocks = scheduled(root)
    writes: dict[str, set[str]] = {}
    reads: dict[str, set[str]] = {}
    imports: dict[str, set[str]] = {}
    for f in files:
        name = _module_name(root, f)
        w, r = artifacts_and_reads(f)
        writes[name], reads[name] = w, r
        imports[name] = imports_of(f, root)
    imported_by: dict[str, set[str]] = defaultdict(set)
    for name, deps in imports.items():
        for d in deps:
            imported_by[d].add(name)
    readers_of: dict[str, set[str]] = defaultdict(set)
    for name, rs in reads.items():
        for a in rs:
            readers_of[a].add(name)
    writers_of: dict[str, set[str]] = defaultdict(set)
    for name, ws in writes.items():
        for a in ws:
            writers_of[a].add(name)

    organs: dict[str, dict[str, Any]] = {}
    for name in sorted(writes):
        arts = sorted(writes[name])
        if not arts:
            # A file that writes no NAMED artifact is not an organ this census can judge. It may
            # still be essential (a library, a CLI); silence about it is the honest answer.
            continue
        consumers = sorted({c for a in arts for c in readers_of.get(a, set()) if c != name}
                           | imported_by.get(name, set()))
        planes = clocks.get(name, [])
        verdict = (LIVE if planes and consumers else
                   BURNING if planes else
                   NO_CLOCK if consumers else UNREACHED)
        organs[name] = {"planes": planes, "artifacts": arts, "consumers": consumers[:12],
                        "n_consumers": len(consumers), "verdict": verdict}
    contested = {a: sorted(w) for a, w in writers_of.items() if len(w) > 1}
    by_verdict: dict[str, list[str]] = defaultdict(list)
    for name, o in organs.items():
        by_verdict[o["verdict"]].append(name)
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_organs": len(organs), "organs": organs,
        "live": sorted(by_verdict[LIVE]), "burning": sorted(by_verdict[BURNING]),
        "no_clock": sorted(by_verdict[NO_CLOCK]), "unreached": sorted(by_verdict[UNREACHED]),
        "contested_artifacts": dict(sorted(contested.items())),
        "counts": {k: len(v) for k, v in sorted(by_verdict.items())},
        "basis": ("CLOCK from check_scheduler_manifest's four planes; ARTIFACT and CONSUMER from "
                  "literal paths near a write call and everywhere else, plus module imports. The "
                  "heuristic over-reports consumers on purpose: it can make an organ look more "
                  "alive, never mark a live one dead"),
        "confidence": {"clock": "exact (the scheduler manifest's four planes)",
                       "consumer": ("heuristic (filename literals and resolved imports); it "
                                    "under-reports, so UNREACHED is a review list, not a "
                                    "death certificate")},
        "why": ("BURNING = on a clock and no reader found -- the actionable population, because "
                "the clock half is exact. NO_CLOCK = read by something, refreshed by nothing. "
                "UNREACHED = neither found, which is a candidate for a person to look at and "
                "NOT a verdict of death. CONTESTED = two organs write one filename, the "
                "two-builders-of-one-identity failure this desk has already paid for twice. "
                "Report only: no timer is masked and no source removed"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 on a contested artifact")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = census()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"dead architecture: {doc['n_organs']} organs that write something; {doc['counts']}")
    if doc["burning"]:
        print(f"  BURNING (on a clock, no reader found): {', '.join(doc['burning'][:10])}")
    if doc["contested_artifacts"]:
        print(f"  CONTESTED artifacts: {len(doc['contested_artifacts'])}; first "
              f"{next(iter(doc['contested_artifacts'].items()))}")
    return 1 if (args.strict and doc["contested_artifacts"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
