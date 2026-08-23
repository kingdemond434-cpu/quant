#!/usr/bin/env python3
"""ENFORCEMENT EXECUTION (L1.43 / L2.0) -- the enforcement matrix proves a fence EXISTS and maps
to a law. Nothing ever proved the fence RUNS.

THE DEFECT THIS WAS BUILT FOR, found by the capability hunt 2026-08-01 and confirmed by hand
before a line was written: `data/enforcement_matrix.json` reports ENFORCED on 62 of 65 principles.
Two of those -- L1.19 (information decay) and L2.10 (reality gap) -- name `libs/research/dist_shift.py`
as their enforcement. That module's only importer in the entire repo is its own unit test. The
producer was built, unit-tested green, cited as evidence that two laws were enforced, and never
called by anything. The matrix could not see it, because the matrix asks "does the file exist and
does it map to a principle?" -- both yes -- and never asks "does anything execute it?".

That is L1.43's welded-gate logic one level up. L1.43 classifies a fence by whether it has ever
FIRED; this asks the prior question, the one a never-run fence cannot answer for itself: is there
a path by which it could fire at all? A citation nothing executes is a law enforced by a
docstring.

WHY THE EXISTING CHECKS DO NOT COVER THIS, verified rather than assumed:
  * `build_enforcement_matrix.py` checks existence + mapping. Never execution.
  * `max_audit.check_orphan_code` walks the import graph but at PACKAGE granularity, and skips any
    package with fewer than 3 modules. `libs/research` is reached by dozens of scripts, so every
    orphaned MODULE inside it is invisible. dist_shift.py sat there unseen.
  * `check_fence_yield.py` (L1.43) measures fences that produce ARTIFACTS. A library module with no
    artifact of its own is outside its scope entirely.
The blind spot was module-granular, and all three checks were green across it.

IMPORTABLE IS NOT EXECUTED, and this distinction is the whole fence. `libs/validation/__init__.py`
re-exports `RevalidationController`, so `revalidation.py` is reachable from any script importing
`libs.validation` -- static reachability would call it live. It is not: nothing constructs that
controller outside tests. So a module counts as EXECUTED only when one of its own public symbols
is REFERENCED from non-test code that is itself reachable -- never merely because an `__init__`
re-exports it.

STATUSES, per citation:
  EXECUTED   a real path to execution exists: a cron line, a subprocess invocation, an import that
             is used, or a max_audit fence that is registered.
  STANDING   a non-executable artifact (docs/, data/, ops/ -- a lock file, the doctrine, the
             graveyard). Enforcement by content, not by running. Checked for EXISTENCE only.
  TEST       a tests/ path: executed by pytest in CI. Checked for existence.
  DECORATIVE the file exists and nothing executes it. The law it is cited for is enforced by
             nothing. FAILS.
  MISSING    the cited path does not exist at all. FAILS.

Run status: OK / DECORATIVE / MISSING / UNMEASURED. UNMEASURED when the citation map cannot be
read -- zero citations is UNMEASURED, never OK (L1.28a: an unmeasured thing must never report
fine, which is the exact bug that let this defect live).

DELIBERATELY CONSERVATIVE. A gate that cries wolf gets acknowledged into silence, and that is how
enforcement actually dies (L1.41). Every ambiguous case resolves to EXECUTED: a symbol referenced
anywhere in non-test production code counts, subprocess invocation by string counts, and a
parenthetical or `:symbol` suffix is stripped rather than treated as a path. The fence reports what
it can PROVE is unexecuted, and says so.

    python scripts/check_enforcement_execution.py [--report-only] [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ acts, so it passes the law boundary like every other. guard() is
# TTL-cached (~0ms after the first call in a window) and pages rather than blocks -- a governance
# fault must never silently stop a detector.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data/enforcement_execution.json"
_MANIFEST = _ROOT / "ops/crontab.manifest"
_AUDIT = _ROOT / "scripts/max_audit.py"

#: Citations that are deliberately HUMAN-INVOKED, with the reason. Same convention as
#: check_build_standard's _SCHEDULE_EXEMPT: "no cron line" must be a DECISION on the record, never
#: a default. A tool taking file arguments cannot have a cadence -- but the exemption is narrow and
#: still printed, because an unrun manual tool is a real obligation, just one a DIFFERENT fence
#: owns (Gate-0 readiness), not this one. This fence asks only: can it execute at all?
_MANUAL: dict[str, str] = {
    "scripts/deep_review.py": "13-seat second-model-family panel, ONE file per pass, invoked with "
    "explicit file arguments (LIVE_CONNECTOR_SPEC section-7). Cold "
    "independence is the point -- it is deliberately not self-served by "
    "the desk on a timer. Its Gate-0 obligation is tracked separately.",
    # THE THREE BELOW WERE AUTO-PASSED AS EXECUTED off a string in the citation registry, so
    # nobody ever had to make this call on the record. Each is genuinely human-invoked -- but
    # "no cron line must be a DECISION on the record, never a default" (check_build_standard's
    # own convention), and a substring matcher was making that decision silently for all three.
    "scripts/read_xls.py": "a TOOL, not an organ, and already exempted on those grounds in "
    "check_build_standard._SCHEDULE_EXEMPT: it reads a .xls a seat hands "
    "it, so there is no state for a cadence to sample. Built for the "
    "research-frozen digger seats, which cannot write to scripts/ and so "
    "need a reachable surface rather than a library (R0317).",
    "scripts/screen_oi_ls_axes.py": "a Stage-A screen over a PRE-DECLARED trial grid. It is run "
    "once per campaign against a named panel, and a cadence would "
    "re-run the same pre-registered cells against unchanged data "
    "-- multiplicity budget spent for no new evidence, which is "
    "the garden-of-forking-paths failure the grid exists to stop.",
    "scripts/falsify_funding_state_axis.py": "a ONE-SHOT falsifier, run BEFORE the L1.63 build it "
    "tests (capability hunt 2026-08-13 s0). Its whole "
    "purpose is to execute once against a standing claim; "
    "re-running it on a timer would re-answer a question "
    "already answered and recorded in the law's own text.",
}

#: Verdicts that mean the cited enforcement cannot be cashed. MENTIONED and DECORATIVE are both
#: failures and are deliberately NOT merged: "someone wrote this path down in a registry" and
#: "nothing in the repo names this at all" demand opposite repairs -- wire the caller vs decide
#: whether the artifact should exist -- and a desk that cannot tell them apart debugs the wrong
#: organ (L1.55, on ABSENT vs UNREADABLE).
_BROKEN = ("DECORATIVE", "MISSING", "MENTIONED")
_PASSING = frozenset({"OK"})

#: Non-executable artifact roots: these enforce by CONTENT (a sealed lock, the doctrine text, the
#: graveyard record), so "does it run" is the wrong question and existence is the right one.
_STANDING_ROOTS = ("docs/", "data/", "ops/")
_STANDING_SUFFIXES = (".md", ".txt", ".lock", ".json", ".jsonl", ".yaml", ".yml")


def _strip_citation(raw: str) -> str:
    """A citation carries prose: 'run_deadman_switch.py (Tier-3)', 'libs/x.py:capacity_status'."""
    s = re.sub(r"\s*\(.*?\)\s*$", "", raw.strip())
    if ".py:" in s:  # 'libs/autodiscovery/validation.py:capacity_status'
        s = s.split(".py:")[0] + ".py"
    return s.strip()


def _module_or_script(s: str, p: Path) -> str:
    """'module' (checked by import/reference evidence) or 'script' (checked by process
    evidence) -- and the split used to be a bare `libs/` prefix, which is a directory-naming
    guess, not a structural fact. It produced a false DECORATIVE verdict on
    desks/mt5/mt5desk/risk_units.py (L1.67): that file is a genuine library module -- imported
    and called from gateway.py, never run standalone -- but it lives under desks/, not libs/,
    so it was classified 'script' and then judged by `invoked()`, which asks "does anything run
    this as a process". A pure library module can never produce that evidence even when it is
    working exactly as designed; demanding it is a category error, not a wiring gap.

    THE STRUCTURAL SIGNAL: `if __name__ == "__main__":`. A file with one is DESIGNED to run as a
    process (gateway.py has one; it is genuinely `python gateway.py`-able). A file with neither
    that guard nor a `libs/` path is a library module by construction, wherever it happens to
    live, and belongs on the import-evidence path instead.
    """
    if s.startswith("libs/"):
        return "module"
    try:
        text = p.read_text("utf-8", errors="ignore")
    except OSError:
        return "script"
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "script"
    has_main_guard = any(
        isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__"
        for n in ast.walk(tree)
    )
    return "script" if has_main_guard else "module"


def _resolve(cite: str) -> tuple[str, Path | None]:
    """-> (kind, path). kind in {standing, test, script, module, fence, unknown}."""
    s = _strip_citation(cite)
    if not s:
        return "unknown", None
    if s.startswith("tests/"):
        return "test", _ROOT / s
    if s.startswith(_STANDING_ROOTS) or (s.endswith(_STANDING_SUFFIXES) and "/" in s):
        return "standing", _ROOT / s
    if s.endswith(".py"):
        p = _ROOT / s
        if p.exists():
            return (_module_or_script(s, p)), p
        alt = _ROOT / "scripts" / s  # bare 'revalidate_clocks.py'
        if alt.exists():
            return "script", alt
        return (_module_or_script(s, p)), p
    if "/" not in s and "." not in s:
        return "fence", _AUDIT  # a max_audit fence function name
    return "unknown", _ROOT / s


def _py_files(*rel: str) -> list[Path]:
    out: list[Path] = []
    for r in rel:
        d = _ROOT / r
        if d.exists():
            out.extend(sorted(d.rglob("*.py")))
    return out


def _public_symbols(path: Path) -> set[str]:
    """Top-level public defs/classes of a module -- the names a caller would actually use."""
    try:
        tree = ast.parse(path.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id.isupper():
                    out.add(t.id)
        elif isinstance(node, ast.AnnAssign):
            # ANNOTATED module constants are public surface too, and were invisible here.
            # `BASES: tuple[str, ...] = (...)` in libs/research/capital_basis.py is the whole
            # point of that module -- ONE vocabulary for the denominator -- and a consumer
            # importing only BASES would not have counted as a reference to it.
            tgt = node.target
            if isinstance(tgt, ast.Name) and not tgt.id.startswith("_") and tgt.id.isupper():
                out.add(tgt.id)
    return out


#: Modules whose presence proves a file can start another process or resolve one dynamically.
#: Deliberately a LOW bar, and the direction of that choice is the point: this set decides
#: whether a citer is CAPABLE of invoking, and a false "incapable" would manufacture a
#: DECORATIVE verdict against a script that really does run. Over-admitting costs a missed
#: detection; under-admitting cries wolf, and a gate that cries wolf gets acknowledged into
#: silence (L1.41). So anything that imports a process/import primitive counts as capable.
_EXEC_IMPORTS = frozenset({"subprocess", "runpy", "importlib", "multiprocessing", "pty", "shlex"})
#: os.system / os.exec* / os.spawn* -- os is imported almost everywhere, so the ATTRIBUTE is
#: what proves the capability, never the bare import.
_EXEC_ATTRS = ("system", "execv", "execvp", "execl", "spawnl", "spawnv", "popen", "import_module")


def _code_index(text: str) -> tuple[set[str], bool] | None:
    """-> (names loaded in CODE, can-this-file-execute-something). None when unparsable.

    THE WHOLE FIX LIVES HERE. The previous matcher asked whether a name appeared anywhere in a
    file's TEXT, so a docstring, a comment or -- the case that produced this row -- a path string
    sitting in a citation registry all read as use. Names are collected from the AST, where a
    string literal is a Constant and is never a Name, so prose cannot be laundered into evidence.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    names: set[str] = set()
    can_exec = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
            if n.attr in _EXEC_ATTRS:
                can_exec = True
        elif isinstance(n, ast.alias):
            root = n.name.split(".")[0]
            names.add((n.asname or n.name).split(".")[-1])
            if root in _EXEC_IMPORTS:
                can_exec = True
    return names, can_exec


#: Non-.py places a script can genuinely be invoked from. THESE WERE NOT SCANNED, and the
#: omission was half of this fence's error: it matched a BARE filename against the cron manifest
#: but demanded a FULL PATH from everything else, so a runner holding bare filenames was
#: invisible while a registry holding full paths was authoritative.
_RUNNER_GLOBS = (
    "ops/**/*.sh", "ops/*.sh", "ops/**/*.service", "ops/**/*.timer",
    "deploy/**/*.sh", "deploy/*.sh", ".github/workflows/*.yml", ".github/workflows/*.yaml",
)


class _Corpus:
    """Non-test production code, indexed once by AST rather than by text."""

    def __init__(self) -> None:
        self.files: dict[Path, str] = {}
        self.code: dict[Path, set[str]] = {}
        self.can_exec: dict[Path, bool] = {}
        # L1.60 ATTRITION: a file this fence could not read or parse is NOT the same as a file
        # that contained nothing, and dropping it invisibly would inflate every "nothing
        # references this" verdict below. Counted, published, never swallowed.
        self.unreadable = 0
        self.unparsable: list[str] = []
        # EXCLUDE THIS FENCE'S OWN SOURCE. Found on the second run, and it is precisely the defect
        # class this fence hunts: the _MANUAL registry below contains the literal string
        # "scripts/deep_review.py", so scanning scripts/ found the fence's own exemption entry and
        # reported the tool as INVOKED. A checker that cites itself as evidence launders any
        # mention -- a docstring, a registry key -- into proof of execution.
        _self = Path(__file__).resolve()
        # "desks" WAS MISSING, AND IT IS WHERE EVERY DESK'S OWN CODE ACTUALLY LIVES. A caller
        # inside desks/mt5/mt5desk/gateway.py referencing a symbol in desks/mt5/mt5desk/
        # risk_units.py was invisible to this scan by construction -- not a lazy-import edge
        # case, a directory this corpus never read at all. That produced a false DECORATIVE
        # verdict on risk_units.py (L1.67) the moment the real caller and the real callee both
        # happened to live in the one tree this fence never looked at.
        for f in _py_files("scripts", "libs", "desks"):
            if f.resolve() == _self:
                continue
            try:
                text = f.read_text("utf-8", errors="ignore")
            except OSError:
                self.unreadable += 1
                continue
            self.files[f] = text
            idx = _code_index(text)
            if idx is None:
                # Unparsable: fall back to TEXT matching for this one file only. That is the old
                # (over-admitting) behaviour, which is the safe direction -- it can only produce
                # a spurious EXECUTED, never a spurious DECORATIVE -- and it is counted.
                self.unparsable.append(f.relative_to(_ROOT).as_posix())
                continue
            self.code[f], self.can_exec[f] = idx
        self.manifest = _MANIFEST.read_text("utf-8", errors="ignore") if _MANIFEST.exists() else ""
        self.runners: dict[Path, str] = {}
        for glob in _RUNNER_GLOBS:
            for f in sorted(_ROOT.glob(glob)):
                try:
                    self.runners[f] = f.read_text("utf-8", errors="ignore")
                except OSError:
                    self.unreadable += 1

    def scanned(self) -> int:
        """Files this fence actually examined -- its L1.57 denominator, counted not asserted."""
        return len(self.files) + len(self.runners)

    def references(
        self, symbols: set[str], *, exclude: Path, package_init: Path | None
    ) -> tuple[str, str] | None:
        """Is any symbol used from real CODE? -> (file, symbol), or None.

        `package_init` is excluded: a re-export in `__init__.py` proves the module is IMPORTABLE,
        never that anything calls it. Counting it is exactly how an orphan reads as wired.
        """
        for path, names in self.code.items():
            if path in (exclude, package_init):
                continue
            hit = symbols & names
            if hit:
                return path.relative_to(_ROOT).as_posix(), sorted(hit)[0]
        for path in self.unparsable:  # text fallback, over-admitting by design
            p = _ROOT / path
            if p in (exclude, package_init):
                continue
            for sym in symbols:
                if re.search(rf"\b{re.escape(sym)}\b", self.files.get(p, "")):
                    return path, sym
        return None

    def _patterns(self, script: Path) -> list[re.Pattern[str]]:
        """A script is named three ways in the wild, and all three are legitimate."""
        return [
            re.compile(rf"\b{re.escape(f'scripts/{script.name}')}"),   # 'scripts/foo.py'
            re.compile(rf"(?<![\w/.]){re.escape(script.name)}\b"),      # bare 'foo.py'
            re.compile(rf"\bscripts\.{re.escape(script.stem)}\b"),      # 'scripts.foo'
        ]

    def invoked(self, script: Path) -> tuple[str, str] | None:
        """A PROVEN path to execution -> (where, how). Mention alone is never proof."""
        pats = self._patterns(script)
        if any(p.search(self.manifest) for p in pats):
            return "ops/crontab.manifest", "cron line"
        for path, text in self.runners.items():
            if any(p.search(text) for p in pats):
                return path.relative_to(_ROOT).as_posix(), "shell/CI runner"
        for path, text in self.files.items():
            if path == script or not any(p.search(text) for p in pats):
                continue
            # THE LOAD-BEARING CONDITION. A file that imports no process or import primitive
            # cannot start anything, so naming a script there is a citation, not a call.
            # scripts/build_enforcement_matrix.py is exactly this: a dict of law -> citation
            # paths, no subprocess anywhere, and it was this fence's evidence for 185 verdicts.
            if self.can_exec.get(path, True):
                return path.relative_to(_ROOT).as_posix(), "invoked by"
        return None

    def mentioned_by(self, script: Path) -> list[str]:
        """Who names it WITHOUT being able to run it -- the debugging half of a MENTIONED row."""
        pats = self._patterns(script)
        return [
            p.relative_to(_ROOT).as_posix()
            for p, text in self.files.items()
            if p != script and any(pat.search(text) for pat in pats)
        ]

    def symbol_in_text(
        self, symbols: set[str], *, exclude: Path, package_init: Path | None
    ) -> tuple[str, str] | None:
        """Where a symbol appears in PROSE only -- separates MENTIONED from DECORATIVE.

        `libs/research/capital_basis.py` is the worked example: scripts/check_capital_basis.py
        tells its reader twice, in a docstring and in the artifact's own `law` string, to
        "declare via libs.research.capital_basis.declare()" -- and never imports it. Naming the
        helper is not calling it, and the two demand opposite repairs (wire the caller vs delete
        the module), so collapsing them sends the reader to the wrong organ (the L1.55 shape).
        """
        for path, text in self.files.items():
            if path in (exclude, package_init):
                continue
            for sym in symbols:
                if re.search(rf"\b{re.escape(sym)}\b", text):
                    return path.relative_to(_ROOT).as_posix(), sym
        return None


def _fence_registered(name: str, audit_text: str) -> bool:
    """A max_audit fence is executed when it is DEFINED and referenced elsewhere in the file
    (a registry entry or a call) -- a defined-but-never-registered fence never runs."""
    if not re.search(rf"^def {re.escape(name)}\b", audit_text, re.M):
        return False
    hits = len(re.findall(rf"\b{re.escape(name)}\b", audit_text))
    return hits > 1


def evaluate() -> dict[str, Any]:
    try:
        from scripts.build_enforcement_matrix import _MAP
    except Exception as exc:
        return {
            "status": "UNMEASURED",
            "reason": f"citation map unreadable ({type(exc).__name__}: {exc}); "
            "cannot prove any law is enforced, so nothing is claimed",
            "citations": [],
            "counts": {},
        }
    if not _MAP:
        return {
            "status": "UNMEASURED",
            "reason": "citation map is empty",
            "citations": [],
            "counts": {},
        }

    corpus = _Corpus()
    audit_text = _AUDIT.read_text("utf-8", errors="ignore") if _AUDIT.exists() else ""
    rows: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    for law, cites in sorted(_MAP.items()):
        for cite in cites:
            kind, path = _resolve(cite)
            key = f"{kind}:{path}"
            if key in seen:  # same artifact cited by several laws
                seen[key]["laws"].append(law)
                continue
            row: dict[str, Any] = {
                "laws": [law],
                "citation": cite,
                "kind": kind,
                "path": path.relative_to(_ROOT).as_posix() if path else None,
            }
            if path is None or (kind != "fence" and not path.exists()):
                row |= {"verdict": "MISSING", "evidence": "path does not exist"}
            elif kind in ("standing", "test"):
                row |= {
                    "verdict": "STANDING" if kind == "standing" else "TEST",
                    "evidence": "non-executable artifact (content is the enforcement)"
                    if kind == "standing"
                    else "executed by pytest",
                }
            elif kind == "fence":
                name = _strip_citation(cite)
                ok = _fence_registered(name, audit_text)
                row |= {
                    "verdict": "EXECUTED" if ok else "DECORATIVE",
                    "evidence": "registered in max_audit.py"
                    if ok
                    else "no `def` in max_audit.py, or defined and never referenced",
                }
            elif kind == "script":
                rel = path.relative_to(_ROOT).as_posix() if path.exists() else ""
                hit = corpus.invoked(path)
                if hit:
                    where, how = hit
                    row |= {"verdict": "EXECUTED", "evidence": f"{how} {where}"}
                elif rel in _MANUAL:
                    row |= {"verdict": "MANUAL", "evidence": _MANUAL[rel]}
                else:
                    citers = corpus.mentioned_by(path)
                    row |= {
                        "verdict": "MENTIONED" if citers else "DECORATIVE",
                        "evidence": (
                            f"named by {citers[:3]}, none of which imports a process or import "
                            "primitive, so none of them can run it"
                        )
                        if citers
                        else "no cron line, no runner, no subprocess call, no importer",
                    }
            elif kind == "module":
                syms = _public_symbols(path)
                init = path.parent / "__init__.py"
                pkg = init if init.exists() else None
                used = corpus.references(syms, exclude=path, package_init=pkg)
                if not syms:
                    row |= {
                        "verdict": "EXECUTED",
                        "evidence": "no public symbols to trace (conservative pass)",
                    }
                elif used:
                    row |= {"verdict": "EXECUTED", "evidence": f"{used[1]} used by {used[0]}"}
                else:
                    prose = corpus.symbol_in_text(syms, exclude=path, package_init=pkg)
                    row |= {
                        "verdict": "MENTIONED" if prose else "DECORATIVE",
                        "evidence": (
                            f"{prose[1]!r} appears in {prose[0]} only as text -- a docstring, a "
                            "comment or a string literal, never a call"
                        )
                        if prose
                        else f"none of {sorted(syms)[:4]} referenced outside "
                        "its own module, its package __init__, or tests",
                    }
            else:
                row |= {
                    "verdict": "EXECUTED",
                    "evidence": "unrecognised citation form (conservative pass)",
                }
            seen[key] = row
            rows.append(row)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    broken = [r for r in rows if r["verdict"] in _BROKEN]

    # A law is enforced by NOTHING only when EVERY one of its citations is broken. The first draft
    # of this fence flagged L1.7 as unenforced because one of its three citations was, while
    # check_rubberstamp_detector and check_rubberstamp_enforcement both execute -- an over-claim,
    # and an over-claiming gate is one nobody believes the second time.
    per_law: dict[str, list[str]] = {}
    for r in rows:
        for law in r["laws"]:
            per_law.setdefault(law, []).append(r["verdict"])
    unenforced = sorted(
        law for law, vs in per_law.items() if vs and all(v in _BROKEN for v in vs)
    )
    weakened = sorted(
        law
        for law, vs in per_law.items()
        if law not in unenforced and any(v in _BROKEN for v in vs)
    )

    if not rows:
        status = "UNMEASURED"
    elif any(r["verdict"] == "MISSING" for r in broken):
        status = "MISSING"
    elif any(r["verdict"] == "DECORATIVE" for r in broken):
        status = "DECORATIVE"
    elif broken:
        status = "MENTIONED"
    else:
        status = "OK"
    return {
        "status": status,
        "scanned": corpus.scanned(),
        "attrition": {
            "unreadable": corpus.unreadable,
            "unparsable": corpus.unparsable,
            "note": "unparsable files fall back to TEXT matching, which can only over-admit "
                    "EXECUTED -- never manufacture a DECORATIVE",
        },
        "citations": rows,
        "counts": counts,
        "broken": [
            {
                "laws": r["laws"],
                "path": r["path"],
                "verdict": r["verdict"],
                "evidence": r["evidence"],
            }
            for r in broken
        ],
        "laws_unenforced": unenforced,
        "laws_weakened": weakened,
        "manual": [
            {"path": r["path"], "laws": r["laws"], "reason": r["evidence"]}
            for r in rows
            if r["verdict"] == "MANUAL"
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--report-only", action="store_true", help="print and always exit 0 (for dashboards)"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    _law_guard()
    res = evaluate()
    res["generated"] = datetime.now(UTC).isoformat()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(res, indent=1) + "\n", "utf-8")

    if args.json:
        print(json.dumps(res, indent=1))
    else:
        c = res.get("counts", {})
        print(
            f"enforcement execution (L1.43): {res['status']} -- "
            + ", ".join(f"{k}={v}" for k, v in sorted(c.items()))
            or "no citations"
        )
        if res.get("reason"):
            print(f"  {res['reason']}")
        for r in res.get("broken", []):
            print(f"  {r['verdict']:10s} {r['path']}  [{', '.join(r['laws'])}]")
            print(f"             {r['evidence']}")
        for m in res.get("manual", []):
            print(f"  MANUAL     {m['path']}  [{', '.join(m['laws'])}] -- human-invoked by design")
        if res.get("laws_unenforced"):
            print(f"  LAWS ENFORCED BY NOTHING: {', '.join(res['laws_unenforced'])}")
        if res.get("laws_weakened"):
            print(
                f"  laws with a broken citation (others still execute): "
                f"{', '.join(res['laws_weakened'])}"
            )
        print(f"-> {_OUT.relative_to(_ROOT)}")

    if args.report_only:
        return 0
    return 0 if res["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
