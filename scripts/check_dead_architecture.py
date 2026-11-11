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

#: RATCHET: organs that hold a clock and whose artifact no other production file reads. It may
#: FALL, never rise. This is the ONE population the census may fence on, because the clock half is
#: exact -- UNREACHED and NO_CLOCK rest on a consumer heuristic that under-reports and fencing on
#: them would licence deleting working organs. BURNING is different in kind: the desk is paying
#: compute every hour for bytes nobody opens, which is an orphan by the principal's own definition
#: (2026-09-23) even when the organ runs perfectly.
#:
#: THE NUMBER JUMPED WHEN THE CENSUS STOPPED BEING BLIND, and that is the honest direction. Before
#: the constant-binding and one-hop-alias fixes above, the census could see 146 organs and called 5
#: of them BURNING. After, it sees 656 -- the other 510 wrote through a module constant and were
#: SKIPPED ENTIRELY by `if not arts: continue`, so they were never judged at all -- and 49 are
#: BURNING. 50 is therefore not a regression from 5; 5 was a number measured over a quarter of the
#: desk. The ratchet is set at the measured count, NOT above it: a new BURNING organ must fail this
#: fence on the day it arrives, which is the whole point of ratcheting rather than sweeping.
#:
#: NOTHING HERE THROTTLES OR DISABLES ANYTHING. The two repairs are to name a consumer or to
#: retire the organ with a reason in `docs/research/retirements.jsonl`. Lowering a budget or
#: masking a timer is never the remedy (growth governance: a reduction needs its own E[log W]
#: proof, and a census has none to offer).
MAX_BURNING = 50

#: RATCHET: filenames written by two or more organs -- the "two builders of one identity" failure
#: the desk has already paid for twice. It may FALL, never rise. 66 on 2026-09-23, measured by the
#: widened census above (19 before it, on the quarter of the desk that census could see). Held as a
#: ratchet rather than an absolute `--strict` failure because wedging the law gate on a 66-row
#: backlog would get the fence switched off within a day, and a fence nobody runs finds nothing.
MAX_CONTESTED = 66


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


#: THE HOUSE STYLE BINDS THE NAME AT THE TOP AND WRITES IT FOUR HUNDRED LINES DOWN:
#: `OUT = DESK / "reports" / "PLUMBING_WATCHDOG.json"` then `OUT.write_text(...)` in main().
#: An eight-line window around the write call can never see that literal, so the census read the
#: watchdog's writes as `X.json` -- a name that only ever appears in its DOCSTRING -- and then
#: reported the organ BURNING while `scripts/check_plumbing_watchdog.py`, a law-gate fence, reads
#: its real artifact every run. Two of the five BURNING rows of 2026-09-23 were this bug, not a
#: dead organ, and a census that manufactures its own actionable population is worse than none.
#: `libs/ops/control_plane`'s sibling check already solved this: when a literal is bound to a
#: constant, search the WHOLE module for a write through that constant.
_CONST_BIND = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=")
_WRITE_LINE = re.compile(r"write_text|write_bytes|json\.dump\(|open\([^)]*['\"][wa]|mkstemp|"
                         r"fh\.write\(|write_report|stamp_sidecar|os\.replace|to_parquet\(")
_WRITE_WORDS = ("write", "dump", "open(", "mkstemp", "stamp_sidecar", "replace", "to_parquet")


#: ONE HOP OF ALIASING, because the desk's own organs take an override argument:
#: `clock_liveness.py:1193` is `r, m = report or REPORT, markdown or DOC` and then writes through
#: `r`, so a search for writes through `REPORT` alone finds nothing and the organ is reported
#: BURNING while three fences read its artifact. One hop is deliberate: it covers the override
#: idiom this repository actually uses without becoming a dataflow analysis that would start
#: claiming writes nobody performs.
_ALIAS = r"^([^=\n<>!+\-*/]+?)\s*=\s*([^=\n].*)$"
_ALIAS_RE = re.compile(_ALIAS)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _alias_lines(src: str) -> list[tuple[str, str]]:
    """(target, value) of every assignment-shaped line, computed ONCE per module.

    SPEED, NOT SCOPE (Desk health 2026-11-06: this fence ran past its 600 s clock on the box).
    `_writes_through` re-split and re-matched the whole module for every constant it was asked
    about; the lines are the same each time, so they are matched once here."""
    out = []
    for line in src.splitlines():
        m = _ALIAS_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


#: The three write shapes `_writes_through` asks about, as ONE pass over the module that
#: collects every name each shape writes through. Asking "does NAME appear in a write?" of that
#: set is the same question the per-name search asked of the whole source, without rescanning
#: the module once per name (Desk health 2026-11-06: that rescan was most of this fence's time).
#:   NAME.write_text / .write_bytes / .open('w|a|x') / .parent.mkdir
_SITE_ATTR = re.compile(
    r"\b(\w+)(?=\s*\.\s*(?:write_text|write_bytes|open\(\s*['\"][wax]|parent\.mkdir))")
#:   write_report(...NAME...) and friends: every word inside the call's first parenthesis run
_SITE_CALL = re.compile(r"(?:write_report|stamp_sidecar|_atomic_write|os\.replace|json\.dump)"
                        r"\(([^)]*)")
#:   .to_json(NAME / .to_csv(NAME / .to_parquet(NAME
_SITE_TO = re.compile(r"\bto_(?:json|csv|parquet)\(\s*(\w+)")
_WORD = re.compile(r"\w+")


def _write_sites(src: str) -> frozenset[str]:
    """Every name the module writes through, in any of the three shapes."""
    names = set(_SITE_ATTR.findall(src)) | set(_SITE_TO.findall(src))
    for run in _SITE_CALL.findall(src):
        names.update(_WORD.findall(run))
    return frozenset(names)


def _writes_through(src: str, const: str,
                    aliases: list[tuple[str, str]] | None = None,
                    sites: frozenset[str] | None = None) -> bool:
    """Does the module ever write through the constant `const`, or a one-hop alias of it?"""
    names = {const}
    word = re.compile(rf"\b{re.escape(const)}\b")
    for target, value in (_alias_lines(src) if aliases is None else aliases):
        if const in value and word.search(value):  # substring first: the regex only confirms
            names |= set(_IDENT.findall(target))
    return not names.isdisjoint(_write_sites(src) if sites is None else sites)


def artifacts_and_reads(path: Path) -> tuple[set[str], set[str]]:
    """(artifact filenames this file appears to WRITE, filenames it appears to READ).

    Best effort, and the report says so: a filename literal within a few lines of a write call
    is a write, a literal BOUND TO A CONSTANT the module later writes through is a write, and any
    other filename literal is a read. The heuristic over-reports CONSUMERS on purpose -- it can
    make an organ look more alive than it is, never mark a live one dead, and a census that
    wrongly buries a working organ is worse than one that is generous.
    """
    try:
        src = path.read_text("utf-8", errors="ignore")
    except OSError:
        return set(), set()
    lines = src.splitlines()
    named = {n for n in _ARTIFACT.findall(src) if n not in _GENERIC}
    writes: set[str] = set()
    for i, line in enumerate(lines):
        # Every _WRITE_LINE alternative contains one of these words, so a line without any of
        # them cannot match: the cheap substring test spares the regex on most lines.
        if not any(k in line for k in _WRITE_WORDS) or not _WRITE_LINE.search(line):
            continue
        window = "\n".join(lines[max(0, i - 8):i + 3])
        writes |= {n for n in _ARTIFACT.findall(window) if n not in _GENERIC}
    aliases: list[tuple[str, str]] | None = None
    sites: frozenset[str] | None = None
    through: dict[str, bool] = {}  # one answer per constant per module
    for m in _ARTIFACT.finditer(src):
        name = m.group(1)
        if name in _GENERIC or name in writes:
            continue
        head = src[src.rfind("\n", 0, m.start()) + 1: m.start()]
        bind = _CONST_BIND.match(head)
        if not bind:
            continue
        const = bind.group(1)
        if const not in through:
            if aliases is None:
                aliases = _alias_lines(src)
            if sites is None:
                sites = _write_sites(src)
            through[const] = _writes_through(src, const, aliases, sites)
        if through[const]:
            writes.add(name)
    return writes, named - writes


_BLOCKS = (ast.stmt, ast.excepthandler, ast.match_case)


def _statements(tree: ast.AST) -> list[ast.AST]:
    """Every statement in the module, at any depth, without walking expressions.

    An import is a statement, and statements only ever sit in the statement lists of other
    statements (bodies, else/finally blocks, except handlers, match cases), so this finds every
    import `ast.walk` finds while skipping the expression trees that are most of a module's nodes
    (Desk health 2026-11-06: ast.walk was half this fence's time)."""
    out: list[ast.AST] = []
    todo: list[ast.AST] = [tree]
    while todo:
        node = todo.pop()
        out.append(node)
        for value in vars(node).values():
            if isinstance(value, list):
                todo.extend(v for v in value if isinstance(v, _BLOCKS))
    return out


def imports_of(path: Path, root: Path) -> set[str]:
    """Repo-relative module paths this file imports from the production roots."""
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    dotted: set[str] = set()
    for node in _statements(tree):
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
        "burning_ratchet": MAX_BURNING,
        "burning_ratchet_ok": len(by_verdict[BURNING]) <= MAX_BURNING,
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
    ap.add_argument("--strict", action="store_true", help="exit 1 on any contested artifact")
    ap.add_argument("--ratchet", action="store_true",
                    help="exit 1 when BURNING or CONTESTED rose above its ratchet (the law-gate "
                         "clause: the backlog may only fall)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = census()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    n_burn, n_cont = len(doc["burning"]), len(doc["contested_artifacts"])
    print(f"dead architecture: {doc['n_organs']} organs that write something; {doc['counts']}; "
          f"BURNING {n_burn} (ratchet {MAX_BURNING}); CONTESTED {n_cont} "
          f"(ratchet {MAX_CONTESTED})")
    if doc["burning"]:
        print(f"  BURNING (on a clock, no reader found): {', '.join(doc['burning'][:10])}")
    if doc["contested_artifacts"]:
        print(f"  CONTESTED artifacts: {n_cont}; first "
              f"{next(iter(doc['contested_artifacts'].items()))}")
    if args.ratchet:
        bad = False
        if n_burn > MAX_BURNING:
            bad = True
            print(f"FAIL: organs on a clock with no reader rose to {n_burn} (ratchet "
                  f"{MAX_BURNING}). Each is an orphan the desk pays compute for every hour: give "
                  f"its artifact a named consumer, or retire the organ with a reason in "
                  f"docs/research/retirements.jsonl and lower MAX_BURNING. Never mask its timer.")
        if n_cont > MAX_CONTESTED:
            bad = True
            print(f"FAIL: artifacts with two writers rose to {n_cont} (ratchet {MAX_CONTESTED}). "
                  f"Two builders of one identity is a defect this desk has already paid for "
                  f"twice: give the second writer its own filename, or delete it.")
        for label, n, cap in (("BURNING", n_burn, MAX_BURNING),
                              ("CONTESTED", n_cont, MAX_CONTESTED)):
            if n < cap:
                print(f"NOTE: {label} fell to {n}; lower its ratchet in this file to {n} so the "
                      f"ground that was won is kept.")
        if bad:
            return 1
    return 1 if (args.strict and doc["contested_artifacts"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
