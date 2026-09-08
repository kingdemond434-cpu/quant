"""The Tier-1 programme ledger, checked against the repository it describes.

    python scripts/check_tier1_program.py            # verify, print the status census, exit 1 on a lie
    python scripts/check_tier1_program.py --render   # also rewrite docs/research/TIER1_PROGRAM.md

WHY A CHECKER AND NOT A DOCUMENT. The principal was handed two external blueprints (2026-09-08)
totalling ~120 architecture items plus five acceptance properties, and asked for all of them.
The desk's own history is that "built" and "runs" diverge silently: organs exist and produce
nothing, a merge aborts 960 times unrecorded, a seat writes where no reader looks. A ledger that
merely LISTS the items would repeat that failure at the programme level -- the first stale
EXISTS-LIT entry makes every other entry worthless. So the ledger is data
(docs/research/tier1_program.json) and this script is its gate:

  * every `file:line` cited as evidence must exist, and the line must be inside the file;
  * an item whose status is EXISTS-LIT must name a scheduler that exists -- a VPS timer under
    ops/, a box task in desks/mt5/ops/box_tasks.manifest, or a leg of hourly_cycle.py -- and an
    artifact path; "runs" is a claim about a clock, not about code;
  * an item marked MISSING or EXISTS-DARK may cite nothing; PARTIAL must say which part.

The exit code is the verdict. A wrong ledger fails the suite; a correct one is the programme's
coverage number, the same way the discovery frontier's coverage is a number and not a feeling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "research" / "tier1_program.json"
RENDERED = ROOT / "docs" / "research" / "TIER1_PROGRAM.md"

STATUSES = ("EXISTS-LIT", "EXISTS-DARK", "PARTIAL", "MISSING", "LANDED")
GATES = ("none", "hardware", "capital", "principal", "data", "time", "box-paste")
#: CODE and DOCUMENT paths are verified against the tree. Artifact paths (.json/.jsonl) are
#: claims about a box's state -- most live only on the trading box or the VPS and are gitignored
#: here -- so they are carried as evidence but never checked for existence.
_PATH_RE = re.compile(
    r"(?<![\w/])((?:[\w.-]+/)*[\w.-]+\.(?:py|ps1|sh|cmd|md|timer|service|manifest|"
    r"toml|yaml|yml))(?::(\d+))?")


def _line_count(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


_BASENAMES: dict[Path, dict[str, list[Path]]] = {}


def _basenames(root: Path) -> dict[str, list[Path]]:
    """basename -> every file in the tree with that name. A sweep that cites `gate_spec.yaml`
    or `quant-deepseek.timer` by name alone is citing a real file; the ledger resolves the name
    instead of calling a short citation a lie. Ambiguous names (two `orchestrator.py`) exist
    but cannot be line-checked."""
    if root not in _BASENAMES:
        idx: dict[str, list[Path]] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
            for name in filenames:
                idx.setdefault(name, []).append(Path(dirpath, name))
        _BASENAMES[root] = idx
    return _BASENAMES[root]


def _resolve(root: Path, path: str) -> Path | None:
    """The file a citation names, or None. A path with a directory is taken literally; a bare
    name resolves through the tree and returns None when nothing carries it, or a directory-less
    sentinel when several do (exists, but no single line count)."""
    if "/" in path:
        target = root / path
        return target if target.exists() else None
    hits = _basenames(root).get(path) or []
    if not hits:
        return None
    return hits[0] if len(hits) == 1 else AMBIGUOUS


AMBIGUOUS = Path("<ambiguous>")


def _schedulers(root: Path) -> dict[str, set[str]]:
    """Every clock the repo knows: VPS timers, box tasks, hourly/daily legs."""
    timers = {p.name for p in (root / "ops").glob("*.timer")}
    tasks: set[str] = set()
    manifest = root / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    if manifest.exists():
        tasks = set(re.findall(r'TASK name="([^"]+)"', manifest.read_text("utf-8")))
    legs: set[str] = set()
    for name in ("hourly_cycle.py", "daily_cycle.py"):
        src = root / "desks" / "mt5" / "research" / name
        if src.exists():
            legs |= set(re.findall(r'_costed\("([^"]+)"', src.read_text("utf-8")))
            legs |= set(re.findall(r"^def (\w+)\(", src.read_text("utf-8"), re.M))
    return {"timer": timers, "task": tasks, "leg": legs}


def _scheduler_known(spec: str, clocks: dict[str, set[str]]) -> bool:
    """`quant-x.timer` | `MT5-Name` | `hourly_cycle:leg` | `daily_cycle:leg`; comma-separated."""
    ok = False
    for token in (t.strip() for t in spec.split(",") if t.strip()):
        if token.endswith(".timer"):
            ok |= token in clocks["timer"]
        elif token.startswith("MT5-"):
            ok |= token in clocks["task"]
        elif ":" in token:
            ok |= token.split(":", 1)[1] in clocks["leg"]
        else:
            return False
    return ok


def check(ledger: dict, root: Path) -> tuple[list[str], dict]:
    """Return (problems, census). A problem is a lie the ledger tells about the repo."""
    problems: list[str] = []
    warnings: list[str] = []
    clocks = _schedulers(root)
    by_phase: dict[str, Counter] = defaultdict(Counter)
    for it in ledger.get("items", []):
        iid = str(it.get("id"))
        status = it.get("status")
        if status not in STATUSES:
            problems.append(f"{iid}: status {status!r} is not one of {STATUSES}")
            continue
        if it.get("gate", "none") not in GATES:
            problems.append(f"{iid}: gate {it.get('gate')!r} is not one of {GATES}")
        by_phase[str(it.get("phase", "?"))][status] += 1
        # A claim that something RUNS or has LANDED must be verifiable to the line; a PARTIAL,
        # DARK or MISSING entry's citations are evidence of absence and are checked as warnings
        # (a sweep may cite a file by its short name), never as the gate.
        sink = problems if status in ("EXISTS-LIT", "LANDED") else warnings
        for ev in it.get("evidence") or []:
            for path, line in _PATH_RE.findall(str(ev)):
                target = _resolve(root, path)
                if target is None:
                    sink.append(f"{iid}: cites {path} which does not exist")
                elif target is AMBIGUOUS:
                    warnings.append(f"{iid}: cites {path} by name alone and the tree holds "
                                    f"several; line not checked")
                elif line and int(line) > _line_count(target):
                    sink.append(f"{iid}: cites {path}:{line} beyond its {_line_count(target)} lines")
        if status in ("EXISTS-LIT", "LANDED"):
            if not (it.get("evidence") or []):
                problems.append(f"{iid}: {status} with no evidence")
            sched = str(it.get("scheduled_by") or "")
            if status == "EXISTS-LIT" and not _scheduler_known(sched, clocks):
                problems.append(f"{iid}: EXISTS-LIT but scheduled_by={sched!r} names no known "
                                f"timer/task/leg")
            if status == "EXISTS-LIT" and not it.get("artifact"):
                problems.append(f"{iid}: EXISTS-LIT with no artifact")
        if status == "PARTIAL" and not it.get("gap"):
            problems.append(f"{iid}: PARTIAL must say which part is missing")
    for ap in ledger.get("acceptance_properties", []):
        if ap.get("status") not in ("MET", "PARTIAL", "MISSING"):
            problems.append(f"{ap.get('id')}: acceptance status must be MET/PARTIAL/MISSING")
    total = Counter()
    for c in by_phase.values():
        total.update(c)
    return problems, {"by_phase": {k: dict(v) for k, v in sorted(by_phase.items())},
                      "total": dict(total), "n_items": len(ledger.get("items", [])),
                      "warnings": warnings}


def render(ledger: dict, census: dict) -> str:
    out = ["# Tier-1 programme ledger", "",
           f"Updated {ledger.get('updated')} · {census['n_items']} items · generated by "
           "`scripts/check_tier1_program.py --render` (do not edit by hand; edit the JSON).", "",
           "Status vocabulary: EXISTS-LIT = code runs on a named clock and its artifact has a "
           "consumer; EXISTS-DARK = code exists, no clock or no consumer; PARTIAL = part exists "
           "(gap named); MISSING = nothing; LANDED = built in this programme, with commit.", "",
           "## Acceptance properties", ""]
    for ap in ledger.get("acceptance_properties", []):
        out.append(f"- **{ap['id']} {ap['name']}** — {ap['status']}. Measure: {ap['measure']}")
        for ev in ap.get("evidence") or []:
            out.append(f"  - {ev}")
    out += ["", "## Census", "", "| phase | " + " | ".join(STATUSES) + " |",
            "|---|" + "---|" * len(STATUSES)]
    for phase, counts in census["by_phase"].items():
        name = ledger.get("phases", {}).get(phase, "")
        out.append(f"| {phase} {name} | " + " | ".join(str(counts.get(s, 0)) for s in STATUSES)
                   + " |")
    out.append("| **all** | " + " | ".join(str(census["total"].get(s, 0)) for s in STATUSES)
               + " |")
    out += ["", "## Items", ""]
    for phase in sorted(census["by_phase"]):
        out.append(f"### Phase {phase} — {ledger.get('phases', {}).get(phase, '')}")
        out.append("")
        for it in ledger.get("items", []):
            if str(it.get("phase")) != phase:
                continue
            gate = f" · gate: {it['gate']}" if it.get("gate", "none") != "none" else ""
            out.append(f"- **{it['id']} {it['item']}** — {it['status']}{gate}")
            if it.get("gap"):
                out.append(f"  - gap: {it['gap']}")
            for ev in (it.get("evidence") or [])[:4]:
                out.append(f"  - {ev}")
            if it.get("scheduled_by"):
                out.append(f"  - clock: {it['scheduled_by']} · artifact: {it.get('artifact') or 'NONE'}"
                           f" · consumer: {it.get('consumer') or 'NONE'}")
            if it.get("next_step"):
                out.append(f"  - next: {it['next_step']}")
            if it.get("landed"):
                out.append(f"  - landed: {', '.join(it['landed'])}")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--out", type=Path, default=RENDERED)
    args = ap.parse_args(argv)
    try:
        ledger = json.loads(args.ledger.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ledger unreadable: {exc}")
        return 2
    problems, census = check(ledger, args.root)
    print(f"tier-1 programme: {census['n_items']} items; "
          + "; ".join(f"{k} {v}" for k, v in sorted(census["total"].items())))
    for phase, counts in census["by_phase"].items():
        print(f"  phase {phase}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for p in problems:
        print(f"  LIE: {p}")
    if census["warnings"]:
        print(f"  {len(census['warnings'])} unresolved citation(s) on non-lit entries "
              f"(warnings, not lies); first: {census['warnings'][0]}")
    if args.render:
        args.out.write_text(render(ledger, census), "utf-8")
        print(f"rendered {args.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
