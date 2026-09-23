#!/usr/bin/env python3
"""THE TIER-5 AUDIT CANNOT CLAIM WHAT THE REPOSITORY DOES NOT HOLD.

`docs/research/tier5_audit.json` lists every section of the principal's two blueprints (the
COMPLETE TIER-5 AUTONOMOUS QUANT INSTITUTION BLUEPRINT, I-CII, and the FINAL MAXIMUM-AGGRESSIVE
mandate, 1-170) with a status from a fixed vocabulary. This fence reads it and exits 1 on a lie:

  * status must be one of STATUSES;
  * every row that is not MISSING must cite at least one file that EXISTS in this tree (paths
    are checked; `path:line` must be inside the file);
  * every EXISTS+WIRED+LIVE row must name a clock the repo knows -- an hourly_cycle/daily_cycle
    leg (`hourly_cycle:<leg>` / `daily_cycle:<name>`), a box task (`MT5-*` / `E8-*` from
    desks/mt5/ops/box_tasks.manifest), a VPS timer (`quant-*.timer` under ops/) or a resident
    (`resident:<name>` named in the manifest) -- and a non-empty artifact;
  * DORMANT rows must name the file and say why it has no clock; PARTIAL rows must say what is
    missing (`gap`); REFUSED_CONSERVATIVE rows must carry the sentence saying why (`why`), and it
    must name aggressiveness, the floor, the rail or the principal's order;
  * DUPLICATIVE rows must name the canonical organ they duplicate (`canonical`).

`--render` writes docs/research/TIER5_AUDIT.md (derived, never hand-edited). Registered in
scripts/run_law_gate.py as a portable fence: it reads only tracked files.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "research" / "tier5_audit.json"
RENDERED = ROOT / "docs" / "research" / "TIER5_AUDIT.md"

STATUSES = ("EXISTS+WIRED+LIVE", "DORMANT", "PARTIAL", "MISSING", "DUPLICATIVE",
            "REFUSED_CONSERVATIVE")
_PATH_RE = re.compile(
    r"(?<![\w/])((?:[\w.&-]+/)*[\w.&-]+\.(?:py|ps1|sh|cmd|md|timer|service|manifest|toml|"
    r"yaml|yml|json|jsonl|sqlite))(?::(\d+))?")
_REFUSAL_WORDS = ("aggress", "floor", "rail", "principal", "conservative", "timid", "reduce")


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text("utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def clocks(root: Path) -> dict[str, set[str]]:
    """Every clock the repo knows: legs, daily names, box tasks, timers, residents."""
    legs: set[str] = set()
    daily: set[str] = set()
    hc = root / "desks" / "mt5" / "research" / "hourly_cycle.py"
    dc = root / "desks" / "mt5" / "research" / "daily_cycle.py"
    if hc.exists():
        src = hc.read_text("utf-8", errors="replace")
        legs |= set(re.findall(r'_costed\("([^"]+)"', src))
        legs |= set(re.findall(r"^def (\w+)\(", src, re.M))
    if dc.exists():
        src = dc.read_text("utf-8", errors="replace")
        daily |= set(re.findall(r'"([a-z][a-z0-9_]+)"', src))
        daily |= set(re.findall(r"^def (\w+)\(", src, re.M))
    tasks: set[str] = set()
    residents: set[str] = set()
    manifest = root / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    if manifest.exists():
        text = manifest.read_text("utf-8", errors="replace")
        tasks = set(re.findall(r'TASK name="([^"]+)"', text))
        residents = {t for t in tasks if "resident" in text.split(f'name="{t}"', 1)[1][:400]}
    timers = {p.name for p in (root / "ops").glob("*.timer")}
    return {"leg": legs, "daily": daily, "task": tasks, "resident": residents, "timer": timers}


def clock_known(spec: str, known: dict[str, set[str]]) -> bool:
    ok = False
    for token in (t.strip() for t in str(spec).split(",") if t.strip()):
        if token.endswith(".timer"):
            ok |= token in known["timer"]
        elif token.startswith(("MT5-", "E8-")):
            ok |= token in known["task"]
        elif token.startswith("hourly_cycle:"):
            ok |= token.split(":", 1)[1] in known["leg"]
        elif token.startswith("daily_cycle:"):
            ok |= token.split(":", 1)[1] in known["daily"]
        elif token.startswith("resident:"):
            ok |= token.split(":", 1)[1] in known["task"]
        elif token.startswith("law_gate:"):
            ok |= (root_law_gate_names().__contains__(token.split(":", 1)[1]))
        else:
            return False
    return ok


def root_law_gate_names(root: Path = ROOT) -> set[str]:
    p = root / "scripts" / "run_law_gate.py"
    if not p.exists():
        return set()
    return set(re.findall(r'\("(check_\w+\.py)"', p.read_text("utf-8", errors="replace")))


def check(ledger: dict[str, Any], root: Path) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    known = clocks(root)
    counts: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = {}
    rows = ledger.get("sections") or []
    seen: set[str] = set()
    for it in rows:
        sid = f"{it.get('source')}:{it.get('id')}"
        if sid in seen:
            problems.append(f"{sid}: duplicated id")
        seen.add(sid)
        status = str(it.get("status"))
        if status not in STATUSES:
            problems.append(f"{sid}: status {status!r} not in {STATUSES}")
            continue
        counts[status] += 1
        by_source.setdefault(str(it.get("source")), Counter())[status] += 1
        if not it.get("title"):
            problems.append(f"{sid}: no title")
        files = [str(f) for f in (it.get("files") or [])]
        if status != "MISSING":
            if not files:
                problems.append(f"{sid}: {status} cites no file")
            for f in files:
                m = _PATH_RE.match(f)
                path, line = (m.group(1), m.group(2)) if m else (f, None)
                target = root / path
                if not target.exists():
                    problems.append(f"{sid}: cites {path} which does not exist")
                elif line and target.is_file() and int(line) > _line_count(target):
                    problems.append(f"{sid}: cites {path}:{line} beyond its "
                                    f"{_line_count(target)} lines")
        if status == "EXISTS+WIRED+LIVE":
            if not clock_known(str(it.get("clock") or ""), known):
                problems.append(f"{sid}: LIVE but clock={it.get('clock')!r} is not a known "
                                f"leg/task/timer/resident")
            if not it.get("artifact"):
                problems.append(f"{sid}: LIVE with no artifact")
        if status == "DORMANT" and not it.get("why"):
            problems.append(f"{sid}: DORMANT must say why it has no clock")
        if status == "PARTIAL" and not it.get("gap"):
            problems.append(f"{sid}: PARTIAL must name the missing part (gap)")
        if status == "REFUSED_CONSERVATIVE":
            why = str(it.get("why") or "")
            if not why or not any(w in why.lower() for w in _REFUSAL_WORDS):
                problems.append(f"{sid}: REFUSED_CONSERVATIVE must say why in terms of "
                                f"aggressiveness/floor/rail/principal")
        if status == "DUPLICATIVE" and not it.get("canonical"):
            problems.append(f"{sid}: DUPLICATIVE must name the canonical organ")
    expected = ledger.get("expected_counts") or {}
    for source, n in expected.items():
        have = sum(by_source.get(source, Counter()).values())
        if have != int(n):
            problems.append(f"{source}: {have} sections listed, {n} expected")
    return problems, {"total": dict(counts), "by_source": {k: dict(v) for k, v in
                                                            sorted(by_source.items())},
                      "n_sections": len(rows)}


def render(ledger: dict[str, Any], census: dict[str, Any]) -> str:
    out = ["# Tier-5 institution audit (derived -- edit docs/research/tier5_audit.json)", "",
           f"Updated {ledger.get('updated')}. {census['n_sections']} sections; "
           + "; ".join(f"{k} {v}" for k, v in sorted(census["total"].items())) + ".", "",
           "Status vocabulary: EXISTS+WIRED+LIVE = code on a named clock with an artifact; "
           "DORMANT = code with no clock; PARTIAL = an arrow of the chain is missing (named in "
           "`gap`); MISSING = nothing in the tree; DUPLICATIVE = a second copy of a canonical "
           "organ; REFUSED_CONSERVATIVE = refused because it would reduce aggressiveness, with "
           "the sentence why. Verified by scripts/check_tier5_audit.py at every law-gate run.", ""]
    for source in sorted({str(s.get("source")) for s in ledger.get("sections") or []}):
        out += [f"## {source}", "", "| id | section | status | files | clock | artifact | note |",
                "|---|---|---|---|---|---|---|"]
        for it in ledger.get("sections") or []:
            if str(it.get("source")) != source:
                continue
            note = it.get("why") or it.get("gap") or it.get("canonical") or it.get("note") or ""
            files = ", ".join(f"`{f}`" for f in (it.get("files") or [])[:3])
            out.append(f"| {it.get('id')} | {it.get('title')} | {it.get('status')} | {files} | "
                       f"{it.get('clock') or ''} | {it.get('artifact') or ''} | "
                       f"{str(note).replace('|', '/')} |")
        out.append("")
    return "\n".join(out)


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
        print(f"tier-5 audit unreadable: {exc}")
        return 2
    problems, census = check(ledger, args.root)
    print(f"tier-5 audit: {census['n_sections']} sections; "
          + "; ".join(f"{k} {v}" for k, v in sorted(census["total"].items())))
    for source, c in census["by_source"].items():
        print(f"  {source}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    for p in problems:
        print(f"  LIE: {p}")
    if args.render:
        args.out.write_text(render(ledger, census), "utf-8")
        print(f"rendered {args.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
