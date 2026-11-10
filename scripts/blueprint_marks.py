#!/usr/bin/env python3
"""THE EVIDENCE HALF OF THE BLUEPRINT RE-SCORE: how ONE row's marks are measured on this host.

scripts/check_blueprint_score.py is the fence, the hourly leg and the aggregator; this module is
what it measures a row with (the host's clocks, tests, artifacts and branch; the seven marks; the
E[log W] routing weight). Split out so neither file is one diff hunk too large for the
independent reviewer to read whole -- the behaviour is the checker's, unchanged.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "docs" / "research" / "blueprint_ledger"
TIER5 = ROOT / "docs" / "research" / "tier5_audit.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "BLUEPRINT_SCORE.json"
LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
UNMEASURED = "UNMEASURED"
MARKS = ("I", "W", "A", "T", "R", "D", "C")
RECORDED_MARKS = ("A", "C")
ORDER = {"OPEN": 0, UNMEASURED: 1, "PARTIAL": 2, "DONE": 3}
STATES = ("DONE", "PARTIAL", "OPEN", UNMEASURED, "EXCLUDED")
#: An artifact older than this is not evidence that the organ still runs.
ARTIFACT_MAX_AGE_H = 72.0
#: The state half of the fence: the hourly leg must have written the score within this window.
STATE_MAX_AGE_H = 3.0
#: Where a bare artifact name (`COST_SURFACES.json`) is looked for -- a short list, never a tree
#: walk, so the hourly leg stays cheap on the box whose data tree is gigabytes.
ARTIFACT_DIRS = ("desks/mt5/reports", "desks/mt5/reports/tier_s", "desks/mt5/reports/shadow",
                 "desks/mt5/data", "desks/mt5/data/hypotheses", "desks/mt5/data/tier_s",
                 "data", "data/tier_s", "docs/research", "desks/mt5/policy", "")
#: The files that put a module on a clock.
CLOCK_SOURCES = ("desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py",
                 "desks/mt5/ops/box_tasks.manifest", "scripts/run_law_gate.py")
_STAMP_KEYS = ("generated_at", "at", "measured_at", "written_at", "updated_at", "ts", "asof")
_STAMP_READ_MAX = 5_000_000

#: E[log W] WEIGHT, BY WHAT THE ROW TOUCHES. A routing heuristic, stated as data so it can be
#: argued with: a row on the capital path (sizing, costs, fills, the live book) moves E[log W]
#: directly; a row on the validation path decides which edges reach capital at all; discovery
#: rows feed that; plumbing and hygiene rows move it last. First matching tier wins.
WEIGHTS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (5, ("allocat", "sizing", "margin", "cost", "swap", "slippage", "fill", "execution", "order",
         "exposure", "ruin", "survival", "sleeve", "capital", "heat", "kelly", "position",
         "drawdown", "e[log", "elog", "optimizer", "markout", "impact", "latency")),
    (4, ("lockbox", "certif", "gauntlet", "dsr", "deflat", "trial", "replicat", "forward",
         "validat", "admission", "promot", "breadth", "independen", "override", "fdr",
         "selection", "evaluator", "multiplicity")),
    (3, ("data", "pit", "research", "discover", "mechanism", "hypothes", "judg", "backlog",
         "world", "regime", "signal", "search", "frontier", "alpha")),
    (1, ("ci", "lint", "ruff", "mypy", "branch", "doc", "dashboard", "naming")),
)
MONEY_PATH = ("gateway", "decision_core", "sizing", "pf_allocator", "promoter")


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: ONE VERIFIER, NOT A SECOND: the Tier-1 checker verifies the blueprint ledger's citations,
#: statuses and gaps; the Tier-5 checker verifies its own ledger and owns the clock table.
tier1 = _load("repo_check_tier1_program", "scripts/check_tier1_program.py")
tier5 = _load("repo_check_tier5_audit", "scripts/check_tier5_audit.py")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None

def _text(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="replace")
    except OSError:
        return ""


def _stamp(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


class Host:
    """What this host can show: its clock sources, its tests, its artifacts, its branch."""

    def __init__(self, root: Path, now: datetime, branch: str | None = None) -> None:
        self.root = root
        self.now = now
        corpus = [_text(root / rel) for rel in CLOCK_SOURCES]
        ops = root / "ops"
        if ops.is_dir():
            for pat in ("*.timer", "*.service", "*.sh"):
                corpus += [_text(p) for p in sorted(ops.glob(pat))]
        self.clock_words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", "\n".join(corpus)))
        words: set[str] = set()
        self.test_files: set[str] = set()
        for area in ("tests", "desks/mt5/tests"):
            d = root / area
            if not d.is_dir():
                continue
            for p in d.rglob("test_*.py"):
                self.test_files.add(p.relative_to(root).as_posix())
                words |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", _text(p)))
        self.test_words = words
        self.branch = branch if branch is not None else self._branch()
        self.t5_clocks = tier5.clocks(root)

    def _branch(self) -> str:
        try:
            out = subprocess.run(["git", "branch", "--show-current"], cwd=self.root,
                                 capture_output=True, text=True, timeout=10, check=False)
            return out.stdout.strip() or UNMEASURED
        except (OSError, subprocess.SubprocessError):
            return UNMEASURED

    def artifact(self, name: str) -> Path | None:
        name = name.strip().strip("`")
        cands = [self.root / name] if "/" in name else []
        cands += [self.root / d / Path(name).name for d in ARTIFACT_DIRS]
        if "/" in name:
            cands += [self.root / "desks" / "mt5" / name]
        return next((c for c in cands if c.is_file()), None)

    def age_h(self, path: Path) -> float | None:
        """The artifact's own stamp when it carries one (a git checkout's mtime is the checkout's,
        not the run's), else its mtime."""
        stamp = None
        try:
            if path.suffix == ".json" and path.stat().st_size <= _STAMP_READ_MAX:
                doc = _read_json(path)
                if isinstance(doc, dict):
                    stamp = next((s for s in (_stamp(doc.get(k)) for k in _STAMP_KEYS) if s), None)
            if stamp is None:
                stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            return None
        return round((self.now - stamp).total_seconds() / 3600.0, 2)

    def fresh_artifact(self, names: list[str]) -> tuple[bool | None, str]:
        """True: a named artifact is here and young. False: here but stale. None: none is here."""
        if not names:
            return None, "the row names no artifact"
        stale = None
        for n in names:
            p = self.artifact(n)
            if p is None:
                continue
            age = self.age_h(p)
            if age is not None and age <= ARTIFACT_MAX_AGE_H:
                return True, f"{p.relative_to(self.root).as_posix()} {age} h old"
            stale = f"{p.relative_to(self.root).as_posix()} {age} h old (> {ARTIFACT_MAX_AGE_H})"
        if stale:
            return False, stale
        return None, "no named artifact on this host: " + ", ".join(names[:4])


def weight(text: str) -> int:
    """The first tier any of whose keys starts a word of `text` (so `ci` is CI, not decision)."""
    low = re.sub(r"[_/.-]", " ", text.lower())
    for w, keys in WEIGHTS:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(k), low) for k in keys):
            return w
    return 2


def _fresh_record(row: dict[str, Any], ttl_days: float, now: datetime) -> bool:
    at = _stamp(row.get("reviewed_at"))
    return at is not None and (now - at).total_seconds() <= ttl_days * 86400


def _level(marks: dict[str, bool | None]) -> str:
    if marks["I"] is False:
        return "OPEN"
    held = sum(1 for m in MARKS if marks[m] is True)
    if held == len(MARKS):
        return "DONE"
    return "PARTIAL" if held else UNMEASURED


def score_blueprint_row(row: dict[str, Any], host: Host, ttl_days: float,
                        root: Path) -> dict[str, Any]:
    rec = dict(row.get("marks") or {})
    fresh = _fresh_record(row, ttl_days, host.now)
    code = [str(c) for c in row.get("code") or []]
    stems = {Path(c).stem for c in code}
    marks: dict[str, bool | None] = {}
    why: dict[str, str] = {}
    lies: list[str] = []
    if code:
        absent = [c for c in code if not (root / c).exists()]
        marks["I"] = not absent
        why["I"] = ("absent: " + ", ".join(absent)) if absent else f"{len(code)} cited module(s) exist"
    else:
        marks["I"], why["I"] = None, "the row cites no module this tree can resolve"
    wired = sorted(s for s in stems if s in host.clock_words)
    marks["W"] = True if wired else None
    why["W"] = (f"named by a clock source: {', '.join(wired)}" if wired
                else "no clock source names its modules (a library reached by import reads "
                     "UNMEASURED, not false)")
    tests = [str(t) for t in row.get("tests") or []]
    tested = sorted(s for s in stems if s in host.test_words)
    if (tests and all(t in host.test_files for t in tests)) or tested:
        marks["T"] = True
        why["T"] = "test(s) exist: " + ", ".join((tests or tested)[:3])
    elif code:
        marks["T"], why["T"] = False, "no test file names any cited module"
    else:
        marks["T"], why["T"] = None, "no module to look a test up by"
    marks["R"], why["R"] = host.fresh_artifact([str(a) for a in row.get("artifacts") or []])
    if marks["I"] is True and host.branch == LIVE_BRANCH:
        marks["D"], why["D"] = True, f"this checkout is {LIVE_BRANCH}"
    elif marks["I"] is False:
        marks["D"], why["D"] = False, "the cited code is absent"
    else:
        marks["D"], why["D"] = None, f"this checkout is {host.branch}, not LIVE"
    evidence = dict(row.get("mark_evidence") or {})
    for m in RECORDED_MARKS:
        v = rec.get(m)
        # Only a mark that COUNTS must show its evidence: a stale one reads UNMEASURED anyway.
        if v is True and fresh:
            cite = str(evidence.get(m) or "")
            paths = [p for p, _ in tier1._PATH_RE.findall(cite)]
            if not paths or any(tier1._resolve(root, p) is None for p in paths):
                lies.append(f"{row.get('id')}: recorded {m}=✓ without mark_evidence[{m}] citing "
                            f"a file that exists")
        if not fresh:
            marks[m] = None
            why[m] = f"recorded {row.get('reviewed_at')} is older than {ttl_days:g} days"
        else:
            marks[m] = v if v is not None else None
            why[m] = f"recorded {row.get('reviewed_at')}"
    claim = str(row.get("claim") or "PARTIAL")
    if claim == "EXCLUDED":
        state = "EXCLUDED"
    else:
        ev = _level(marks)
        state = min((claim if claim in ORDER else "PARTIAL"), ev, key=lambda s: ORDER[s])
        if claim == "DONE" and ev != "DONE":
            lies.append(f"{row.get('id')}: claims DONE but the evidence reads {ev} "
                        f"(not held: {', '.join(m for m in MARKS if marks[m] is not True)})")
    text = " ".join([str(row.get("item")), str(row.get("gap")), " ".join(sorted(stems))])
    held = sum(1 for m in MARKS if marks[m] is True)
    return {"ledger": "blueprint", "id": row.get("id"), "phase": row.get("phase"),
            "item": row.get("item"), "claim": claim, "state": state,
            "marks": "".join("✓" if marks[m] is True else "✗" if marks[m] is False else "?"
                             for m in MARKS),
            "held": held, "why": why, "gap": row.get("gap"), "owner": row.get("owner"),
            "weight": int(row.get("elogw") or weight(text)),
            "money_path": any(k in c for c in code for k in MONEY_PATH),
            "promotable": claim != "DONE" and _level(marks) == "DONE",
            "lies": lies}


_DECLARED = re.compile(r"(?<![\w/])((?:[\w.-]+/)+[\w.-]+\.jsonl?)")


def _cited_path(cite: str) -> str:
    """`path:line` -> path, as the Tier-5 checker reads a citation."""
    m = tier5._PATH_RE.match(cite)
    return m.group(1) if m else cite


def score_tier5_row(row: dict[str, Any], host: Host, root: Path) -> dict[str, Any]:
    status = str(row.get("status"))
    claim = {"EXISTS+WIRED+LIVE": "DONE", "PARTIAL": "PARTIAL", "MISSING": "OPEN",
             "DORMANT": "OPEN"}.get(status, "EXCLUDED")
    files = [str(f) for f in row.get("files") or []]
    present = [f for f in files if (root / _cited_path(f)).exists()]
    i_ok: bool | None = (len(present) == len(files)) if files else None
    w_ok = bool(row.get("clock")) and tier5.clock_known(str(row.get("clock")), host.t5_clocks)
    declared = [str(row["artifact"])] if row.get("artifact") else _DECLARED.findall(
        str(row.get("gap") or ""))
    r_ok, r_why = host.fresh_artifact(declared)
    if claim == "EXCLUDED":
        state = "EXCLUDED"
        ev = "EXCLUDED"
    else:
        if i_ok is False or i_ok is None:
            ev = "OPEN"
        elif w_ok and r_ok is True:
            ev = "DONE"
        elif r_ok is None and declared:
            ev = UNMEASURED
        else:
            ev = "PARTIAL"
        state = min(claim, ev, key=lambda s: ORDER[s])
    text = " ".join([str(row.get("title")), str(row.get("gap") or ""),
                     " ".join(Path(_cited_path(f)).stem for f in files)])
    return {"ledger": "tier5", "id": f"{row.get('source')}:{row.get('id')}",
            "item": row.get("title"), "claim": status, "state": state,
            "marks": ("✓" if i_ok else "✗" if i_ok is False else "?")
            + ("✓" if w_ok else "✗") + ("✓" if r_ok else "✗" if r_ok is False else "?"),
            "held": int(bool(i_ok)) + int(w_ok) + int(bool(r_ok)),
            "why": {"I": f"{len(present)}/{len(files)} cited file(s) exist",
                    "W": f"clock {row.get('clock')!r} {'known' if w_ok else 'unknown or absent'}",
                    "R": r_why},
            "gap": row.get("gap") or row.get("why") or "", "weight": weight(text),
            "money_path": any(k in f for f in files for k in MONEY_PATH),
            "promotable": status == "PARTIAL" and ev == "DONE", "lies": []}

