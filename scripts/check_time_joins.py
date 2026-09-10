#!/usr/bin/env python3
"""EVERY PLACE AN EXTERNAL TIMESTAMP MEETS A BAR INDEX, and whether it declares which clock it is on.

WHY THIS IS A CENSUS AND NOT A FIX. One bug of this class was found and fixed on 2026-09-10:
`family_event_reaction` compared a genuinely-UTC filing time against a bar index that is BROKER
time carrying a UTC tzinfo (+2 winter, +3 summer, measured by `research/futures_lead_lag` at 0.978
correlation against 0.10 at zero). The lane entered two to three hours BEFORE the news, on bars
that opened while the information was still private -- a look-ahead, not lateness, and largest
exactly where the lane was supposed to work.

A defect of that shape is rarely alone, and it is invisible at every site: the code reads
correctly, the types line up, the tzinfo says UTC, and the join is off by an hour or three. So
this enumerates the sites rather than guessing at them, and reports for each whether the frame is
DECLARED. It fixes nothing: which frame a given source is on is a fact about that source, and
guessing it is the original error repeated at scale.

THE THREE STATES A SITE CAN BE IN:

    DECLARED       the call site says which clock its stamps are on (`clock=`, or a call through
                   `libs.research.bar_clock`), so a reader can check it against the source
    INTERNAL       both sides come from the bar index itself -- a rolling window, an ATR reindex,
                   a peer symbol's bars. No external clock is involved and nothing is at risk.
    UNDECLARED     an external series is joined to bars and nothing says which frame it is on.
                   NOT a bug by itself; a site that needs reading, with the arithmetic attached.

AND ONE KNOWN GAP THIS CANNOT MEASURE HERE. `family_cot_positioning` joins a weekly COT series
resampled to `W-FRI` -- a Friday 00:00 label -- while the CFTC publishes the report Friday 15:30
ET (20:30 UTC). If the cached series is not already lagged to its release, that is a ~20 hour
look-ahead which dwarfs the clock offset and is a different defect. The cache
(`data/cot_zcache.parquet`) is not in a research checkout, so this reports the question rather
than an answer: it must be checked on a machine that holds the file.

    python scripts/check_time_joins.py
    python scripts/check_time_joins.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]

#: Trees whose modules can reach a bar index.
TREES = ("desks/mt5/mt5desk", "desks/mt5/research", "libs/research")

#: Calls that align one time series onto another. `reindex` and `searchsorted` are the two that
#: silently succeed with a wrong clock; `merge_asof` and `asof` are the tolerant versions, which
#: are worse, because a tolerance absorbs the offset and returns a plausible answer.
JOINS = ("searchsorted", "reindex", "asof", "merge_asof", "tz_localize", "get_indexer")

#: Parameter and variable names that mark a series as coming from OUTSIDE the bar tape.
EXTERNAL = ("events", "event", "macro", "cot", "calendar", "filing", "announcement", "news",
            "release", "fred", "futures", "reference")

#: How a site declares its frame.
DECLARERS = ("clock=", "bar_clock", "to_bar_time", "CLOCKS")

OUT_REL = "desks/mt5/reports/TIME_JOINS.json"
DECLARED, INTERNAL, UNDECLARED = "DECLARED", "INTERNAL", "UNDECLARED"


@dataclass(frozen=True)
class Site:
    module: str
    line: int
    call: str
    func: str
    state: str
    why: str

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


def _enclosing(tree: ast.Module) -> dict[int, str]:
    """Line -> the function it sits in, so a finding names something a person can open."""
    out: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                out[ln] = node.name
    return out


def scan_module(path: Path, root: Path) -> list[Site]:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return []
    lines = text.splitlines()
    where = _enclosing(tree)
    _params: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = fn.args
            _params[fn.name] = {p.arg for p in (*a.args, *a.posonlyargs, *a.kwonlyargs)}
    rel = str(path.relative_to(root))
    out: list[Site] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name not in JOINS:
            continue
        func = where.get(node.lineno, "<module>")
        # THE CALL'S OWN EXPRESSION, plus the enclosing function's PARAMETERS. A wider window
        # flags any join in a module that merely mentions the word "macro" somewhere -- the first
        # version of this scan reported 75 sites including `encode_quantile` and
        # `realized_variation`, both purely internal. A census that cries wolf is not read.
        seg = (ast.get_source_segment(text, node) or "").lower()
        params = _params.get(func, set())
        touched = {k for k in EXTERNAL if k in seg} | (params & set(EXTERNAL))
        # An external NAME must actually appear in the join itself, not merely be in scope: a
        # function that takes `events` and separately reindexes an ATR is not joining events.
        if not (touched & {k for k in EXTERNAL if k in seg}):
            out.append(Site(rel, node.lineno, name, func, INTERNAL,
                            "the join's own operands come from the bar tape; no external clock"))
            continue
        external = sorted(touched)
        window = "\n".join(lines[max(0, node.lineno - 30):node.lineno + 3])
        if any(d in window or d in f"def {func}" for d in DECLARERS):
            out.append(Site(rel, node.lineno, name, func, DECLARED,
                            "the call site declares which clock its stamps are on"))
            continue
        out.append(Site(rel, node.lineno, name, func, UNDECLARED,
                        f"joins {'/'.join(sorted(set(external))[:3])} to a bar index and nothing "
                        "says which frame those stamps are on. The bar index is BROKER time "
                        "under a UTC tzinfo, so a genuinely-UTC stamp lands 2-3 hours early"))
    return out


def census(root: Path | None = None) -> dict[str, Any]:
    root = Path(root or _ROOT)
    sites: list[Site] = []
    for tree in TREES:
        base = root / Path(*tree.split("/"))
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if path.name.startswith("test_"):
                continue
            sites.extend(scan_module(path, root))
    by = {s: [x for x in sites if x.state == s] for s in (DECLARED, INTERNAL, UNDECLARED)}
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "n_sites": len(sites),
        "by_state": {k: len(v) for k, v in by.items()},
        "undeclared": [s.to_dict() for s in by[UNDECLARED]],
        "declared": [s.to_dict() for s in by[DECLARED]],
        "known_gap_cot": (
            "family_cot_positioning joins a W-FRI weekly series (a Friday 00:00 label) while the "
            "CFTC publishes Friday 15:30 ET = 20:30 UTC. If the cached series is not already "
            "lagged to its release that is a ~20 hour look-ahead, which dwarfs the clock offset "
            "and is a different defect. data/cot_zcache.parquet is absent from a research "
            "checkout, so this is a QUESTION and not an answer: check it where the file lives"),
        "rule": (
            "UNDECLARED is not a bug. It is a site where the frame is a fact about the SOURCE and "
            "nothing records it, so nobody reading the code can tell a correct join from one that "
            "is three hours early. Declaring it is cheap; guessing it is the original error "
            "repeated at scale, which is why this census fixes nothing"),
    }


def render(doc: dict[str, Any]) -> str:
    b = doc["by_state"]
    lines = [f"TIME JOINS  {doc['n_sites']} sites: {b[DECLARED]} declared, {b[INTERNAL]} internal, "
             f"{b[UNDECLARED]} undeclared"]
    for s in doc["undeclared"]:
        lines.append(f"  {s['module']}:{s['line']}  {s['func']}() via .{s['call']}()")
    if doc["undeclared"]:
        lines.append("  (undeclared is a site to read, not a bug: see `rule`)")
    lines.append(f"  KNOWN GAP: {doc['known_gap_cot'][:110]}...")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="where an external timestamp meets a bar index")
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = census(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
