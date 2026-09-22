#!/usr/bin/env python3
"""THE EVOLVABLE / IMMUTABLE BOUNDARY (LAWS 5m), FENCED -- an evolvable organ's change set may
not touch an immutable rail.

WHAT THIS ADDS TO THE EVALUATOR, AND WHAT IT DELIBERATELY DOES NOT. `check_immutable_evaluator`
hashes the judge files into a signed manifest; this fence RE-USES that mechanism (it imports the
evaluator by path and calls its `check()`, so there is one seal and one manifest) and adds the
question the seal cannot answer: which ORGAN made a change. The meta-evolution layer
(`desks/mt5/research/research_evolution.py`) records every mutation it applies with the paths and
symbols it touched; this fence reads those records and refuses, by name, any that reached a rail
in `libs/research/immutable_rails.py`. A commit stamped by the evolution organ (trailer
`Evolved-By: research_evolution`) is held to the same rule over its git change set.

FOUR CHECKS, all repo-only except (c), which reads a box-written ledger when it is present:

  (a) THE BOUNDARY IS WELL-FORMED: every non-state rail names a file that exists (a rail that
      guards nothing is a wish), every evolvable path exists, no evolvable path is a whole-file
      rail, and the evaluator's sealed tuple is a subset of the rails (so the two lists cannot
      disagree about what is immutable).
  (b) THE SEAL'S STATE, read through `check_immutable_evaluator.check()` -- the same call the
      law gate makes -- and REPORTED beside the rails verdict, never counted twice: the seal's
      verdict belongs to the evaluator fence, which sits in the same battery, and a second red
      for one drift would teach the desk to read this fence as an echo. A rails verdict is
      still never issued silently over a broken seal: `checks.seal` says BROKEN and names why.
  (c) THE EVOLUTION ORGAN'S RECORDED CHANGE SETS touch no rail: every `applied: true` row in
      `desks/mt5/data/research_evolution/lineage.jsonl` passes `check_change_set`. Absent
      ledger = UNMEASURED on this axis, reported by name, not a pass and not a failure.
  (d) THE HEAD COMMIT, when it carries the evolution organ's trailer, changed no rail path.
      No git = UNMEASURED, reported.

Exit 1 on any breach; 0 clean.

    python scripts/check_immutable_rails.py [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import immutable_rails as IR  # noqa: E402

LINEAGE = ROOT / "desks" / "mt5" / "data" / "research_evolution" / "lineage.jsonl"
TRAILER = "Evolved-By: research_evolution"
UNMEASURED = "UNMEASURED"


def _evaluator() -> Any:
    spec = importlib.util.spec_from_file_location("_rails_fence_evaluator", IR.EVALUATOR_SCRIPT)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_boundary() -> list[dict[str, str]]:
    """(a): the boundary is well-formed."""
    out: list[dict[str, str]] = []
    rails = IR.immutable_rails()
    sealed = IR.evaluator_immutable()
    if not sealed:
        out.append({"what": "evaluator", "why": "check_immutable_evaluator.IMMUTABLE could not "
                                                "be loaded; the sealed set is unknown"})
    rail_paths = {IR.norm(r.path) for r in rails}
    for rel in sealed:
        if IR.norm(rel) not in rail_paths:
            out.append({"what": rel, "why": "sealed by the evaluator but absent from the rails"})
    for r in rails:
        if r.state or r.path.endswith("/") or any(ch in r.path for ch in "*?["):
            continue
        if not (ROOT / r.path).exists():
            out.append({"what": r.path, "why": f"rail ({r.category}) names a path that does not "
                                                f"exist; a rail guarding nothing is a wish"})
    whole = {IR.norm(r.path) for r in rails if not r.symbols}
    for cat, paths in IR.EVOLVABLE.items():
        for p in paths:
            if IR.norm(p) in whole:
                out.append({"what": p, "why": f"listed evolvable ({cat}) AND a whole-file rail"})
            if not (ROOT / p).exists():
                out.append({"what": p, "why": f"evolvable path ({cat}) does not exist"})
    return out


def check_seal() -> list[dict[str, str]]:
    """(b): the evaluator's own verdict, re-used rather than re-implemented."""
    mod = _evaluator()
    if mod is None:
        return [{"what": "evaluator", "why": "scripts/check_immutable_evaluator.py unloadable"}]
    try:
        findings = mod.check()
    except Exception as exc:
        return [{"what": "evaluator", "why": f"check() raised {type(exc).__name__}: {exc}"}]
    return [{"what": str(f.get("file")), "why": f"seal: {f.get('why')}"} for f in findings]


def check_lineage(path: Path = LINEAGE) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """(c): every applied mutation the evolution organ recorded passes the rails."""
    if not path.exists():
        return [], {"status": UNMEASURED, "why": f"no lineage ledger at {path}; the evolution "
                                                  f"organ has applied nothing on this checkout"}
    breaches: list[dict[str, str]] = []
    n_rows = n_applied = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [{"what": str(path), "why": f"unreadable: {exc}"}], {"status": UNMEASURED}
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            breaches.append({"what": str(path), "why": "unparseable lineage row"})
            continue
        n_rows += 1
        if not row.get("applied"):
            continue
        n_applied += 1
        v = IR.check_change_set(row.get("touches") or [])
        for r in v.refused:
            breaches.append({"what": f"{row.get('id')} -> {r.path}"
                                     + (f"::{r.symbol}" if r.symbol else ""),
                             "why": f"applied mutation touched a rail: {r.why}"})
    return breaches, {"status": "MEASURED", "rows": n_rows, "applied": n_applied}


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(ROOT),
                           timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def check_head_commit() -> tuple[list[dict[str, str]], dict[str, Any]]:
    """(d): a commit the evolution organ stamped changed no rail."""
    body = _git("log", "-1", "--format=%B")
    if body is None:
        return [], {"status": UNMEASURED, "why": "git unavailable; HEAD's change set unread"}
    if TRAILER not in body:
        return [], {"status": "MEASURED", "evolved_commit": False}
    names = _git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") or ""
    touched = [ln.strip() for ln in names.splitlines() if ln.strip()]
    v = IR.check_change_set(touched)
    return ([{"what": r.path, "why": f"HEAD is an evolved commit and it {r.why}"}
             for r in v.refused],
            {"status": "MEASURED", "evolved_commit": True, "n_paths": len(touched)})


def run() -> dict[str, Any]:
    boundary = check_boundary()
    seal = check_seal()
    lineage, lineage_meta = check_lineage()
    head, head_meta = check_head_commit()
    breaches = boundary + lineage + head
    rep = IR.rails_report()
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "ok": not breaches,
        "n_breaches": len(breaches),
        "breaches": breaches,
        "checks": {"boundary": len(boundary),
                   "seal": {"status": "HELD" if not seal else "BROKEN",
                            "findings": seal,
                            "owner": "scripts/check_immutable_evaluator.py (same battery)"},
                   "lineage": lineage_meta, "head_commit": head_meta},
        "n_immutable_rails": rep["n_immutable"], "n_evolvable_paths": rep["n_evolvable"],
        "law": rep["law"], "rule": rep["rule"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = run()
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"immutable rails: {'OK' if doc['ok'] else str(doc['n_breaches']) + ' breach(es)'}"
              f" -- {doc['n_immutable_rails']} rails, {doc['n_evolvable_paths']} evolvable "
              f"paths; seal {doc['checks']['seal']['status']}, lineage "
              f"{doc['checks']['lineage'].get('status')}, head "
              f"{doc['checks']['head_commit'].get('status')}")
        for b in doc["breaches"]:
            print(f"  BREACH {b['what']}: {b['why']}")
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
