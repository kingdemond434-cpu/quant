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
}

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
            return ("module" if s.startswith("libs/") else "script"), p
        alt = _ROOT / "scripts" / s  # bare 'revalidate_clocks.py'
        if alt.exists():
            return "script", alt
        return ("module" if s.startswith("libs/") else "script"), p
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
    return out


class _Corpus:
    """Non-test production text, indexed once. Built lazily so --json stays cheap."""

    def __init__(self) -> None:
        self.files: dict[Path, str] = {}
        # EXCLUDE THIS FENCE'S OWN SOURCE. Found on the second run, and it is precisely the defect
        # class this fence hunts: the _MANUAL registry below contains the literal string
        # "scripts/deep_review.py", so scanning scripts/ found the fence's own exemption entry and
        # reported the tool as INVOKED. A checker that cites itself as evidence launders any
        # mention -- a docstring, a registry key -- into proof of execution.
        _self = Path(__file__).resolve()
        for f in _py_files("scripts", "libs"):
            if f.resolve() == _self:
                continue
            try:
                self.files[f] = f.read_text("utf-8", errors="ignore")
            except OSError:
                continue
        self.manifest = _MANIFEST.read_text("utf-8", errors="ignore") if _MANIFEST.exists() else ""

    def references(
        self, symbols: set[str], *, exclude: Path, package_init: Path | None
    ) -> str | None:
        """Is any symbol used from real code? Returns the referencing file, or None.

        `package_init` is excluded: a re-export in `__init__.py` proves the module is IMPORTABLE,
        never that anything calls it. Counting it is exactly how an orphan reads as wired.
        """
        for path, text in self.files.items():
            if path in (exclude, package_init):
                continue
            for sym in symbols:
                if re.search(rf"\b{re.escape(sym)}\b", text):
                    return path.relative_to(_ROOT).as_posix()
        return None

    def invoked(self, script: Path) -> str | None:
        """Cron line, subprocess-by-string, or import by another module."""
        name = script.name
        rel = f"scripts/{name}"
        if re.search(rf"\b{re.escape(name)}\b", self.manifest):
            return "ops/crontab.manifest"
        stem = script.stem
        for path, text in self.files.items():
            if path == script:
                continue
            if rel in text or re.search(rf"\bscripts\.{re.escape(stem)}\b", text):
                return path.relative_to(_ROOT).as_posix()
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
                where = corpus.invoked(path)
                if where:
                    row |= {"verdict": "EXECUTED", "evidence": f"invoked by {where}"}
                elif rel in _MANUAL:
                    row |= {"verdict": "MANUAL", "evidence": _MANUAL[rel]}
                else:
                    row |= {
                        "verdict": "DECORATIVE",
                        "evidence": "no cron line, no subprocess call, no importer",
                    }
            elif kind == "module":
                syms = _public_symbols(path)
                init = path.parent / "__init__.py"
                where = corpus.references(
                    syms, exclude=path, package_init=init if init.exists() else None
                )
                if not syms:
                    row |= {
                        "verdict": "EXECUTED",
                        "evidence": "no public symbols to trace (conservative pass)",
                    }
                else:
                    row |= {
                        "verdict": "EXECUTED" if where else "DECORATIVE",
                        "evidence": f"symbol used by {where}"
                        if where
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
    broken = [r for r in rows if r["verdict"] in ("DECORATIVE", "MISSING")]

    # A law is enforced by NOTHING only when EVERY one of its citations is broken. The first draft
    # of this fence flagged L1.7 as unenforced because one of its three citations was, while
    # check_rubberstamp_detector and check_rubberstamp_enforcement both execute -- an over-claim,
    # and an over-claiming gate is one nobody believes the second time.
    per_law: dict[str, list[str]] = {}
    for r in rows:
        for law in r["laws"]:
            per_law.setdefault(law, []).append(r["verdict"])
    unenforced = sorted(
        law for law, vs in per_law.items() if vs and all(v in ("DECORATIVE", "MISSING") for v in vs)
    )
    weakened = sorted(
        law
        for law, vs in per_law.items()
        if law not in unenforced and any(v in ("DECORATIVE", "MISSING") for v in vs)
    )

    if not rows:
        status = "UNMEASURED"
    elif any(r["verdict"] == "MISSING" for r in broken):
        status = "MISSING"
    elif broken:
        status = "DECORATIVE"
    else:
        status = "OK"
    return {
        "status": status,
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
