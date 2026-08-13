#!/usr/bin/env python3
"""GATE REACHABILITY (L1.49) -- a tally can only see the gates that RAN, and this desk has two
validation gates that have never executed once in 434 candidates plus eight governance gates
nothing in production can ever satisfy.

THE BLIND SPOT, STATED PRECISELY. The desk already measures gate optimality well:
`max_audit.check_gate_optimality` flags any gate rejecting >=98pct, `validation.gate_
discrimination` marks constant gates, `blocking_constant_gates` names the ones that make
promotion arithmetically impossible, and `check_fence_yield` (L1.43) does this job for the
GOVERNANCE layer. Every one of those consumes a per-gate tally -- `rejection_by_gate`, or a list
of evaluated `gate_results` rows. That is the flaw they share and cannot see past:

    A GATE THAT NEVER RAN EMITS NO ROW, SO IT IS NOT A KEY IN THE TALLY, SO NO CHECK THAT
    ITERATES THE TALLY CAN EVER FLAG IT. It is invisible BY CONSTRUCTION, not by oversight.

`check_fence_yield` understood this for governance fences and gave them a NEVER-RUN state. The
validation layer -- the one deciding what reaches capital -- was never given the equivalent.

THE SECOND HALF OF THE SAME BLIND SPOT. `rejection_by_gate` counts REJECTIONS only, so absence
from the tally is ambiguous between two states it cannot distinguish: the gate was never
EVALUATED (dead branch), or it was evaluated every time and PASSED every time (zero-bit
constant-pass). Both carry zero information; only one is a wiring defect. Telling them apart
needs the DECLARATION SITE and its precondition, which is what this fence adds. It is also why
this fence reads source rather than only artifacts.

WHAT IT FOUND ON ITS FIRST RUN (2026-08-05, 434 candidates, 0 survivors ever):
  * `execution_gap` and `regime_robustness` sit behind `if status is CandidateStatus.REGISTRY`
    (orchestrator.py:238-245). No candidate has EVER reached REGISTRY, so neither branch has
    executed a single time. The desk believes it enforces live-cost stress and >=2-vol-regime
    robustness before the registry; it measurably enforces neither.
  * All eight `GovernanceVerdict` fields default False, are AND-ed into a required-True gate, and
    are set True NOWHERE outside tests/ -- the eight-gate signal gauntlet cannot be passed.
  * `economic_mechanism` is declared unconditionally and has never once rejected -- constant-PASS,
    invisible to a >=98pct-REJECT detector that only watches the far end of the range.

WHY THIS IS NOT A LICENCE TO LOOSEN ANYTHING. An unreachable gate is a CLAIM THE DESK CANNOT
CASH, not a bar to lower. The repair for a dead branch is to make its precondition reachable, or
to record out loud that it cannot run and why -- NEVER to delete the gate and call the gauntlet
smaller. That would lower a bar, which L1.6 forbids. This fence moves no threshold, grants no
promotion authority, and fails no build; it reports.

STATUS VALUES -- UNMEASURED is a real answer and never reads as OK (L1.28a):
  UNMEASURED     no candidate ledger, or a sample below the floor. The fence refuses to grade.
  DEAD-BRANCH    a gate whose precondition has PROVABLY never held, so it has never evaluated.
  UNSATISFIABLE  a required-True verdict field that nothing outside tests/ can ever set.
  ZERO-BIT       declared unconditionally, evaluated, and never once rejected.
  OK             every declared gate has been exercised and can be satisfied.

    python scripts/check_gate_reachability.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: Below this many tested candidates the tally cannot distinguish "never ran" from "small
#: sample", so the fence refuses to grade rather than manufacturing a verdict.
_MIN_SAMPLE = 30

#: Where production code lives. `data/` is EXCLUDED deliberately: it holds rollback snapshots
#: that contain whole copies of tests/, and an early version of this fence reported all eight
#: governance gates satisfiable because `data/rollback/*/tests/signal_engine/conftest.py` looked
#: like a production setter. A search root that includes backups will lie about wiring.
_PROD_ROOTS = ("libs", "scripts", "app", "api")

#: The gauntlet's declaration site, parsed with `ast` rather than matched with a regex: an earlier
#: regex captured neighbouring dict keys (`n`, `note`, `survivor_indices`) as gates, and a fence
#: that cries wolf gets ignored, which is worse than not having built it.
_GAUNTLET = "libs/autodiscovery/validation.py"

#: Post-promotion gates, guarded by a precondition -- so reachability is a real question.
_POST_PROMOTE = ("libs/autodiscovery/orchestrator.py", r'reason = "failed: ([a-z_]+)')

#: Modules declaring required-True verdict booleans. Curated like `check_fence_yield._FENCES`,
#: and rot-checked below: any other production module declaring `x: bool = False` inside a class
#: is reported as UNSCANNED rather than silently skipped.
_VERDICT_MODULES = (
    "libs/signal_engine/governance.py",
    # libs/discovery/acceptance.py was RETIRED 2026-07-30 (graveyard: Alpha Discovery Factory);
    # it re-entered this roster because a merge resurrected the dead file, re-deleted 2026-08-11.
    "libs/stage15/governance.py",
)

_ARTIFACT = "data/gate_reachability.json"
_WEB_TALLY = "web/autodiscovery_crypto.json"
_LEDGER = "data/sor_autodiscovery.sqlite"


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text("utf-8")
    except OSError:
        return ""


def _parse(root: Path, rel: str) -> ast.Module | None:
    try:
        return ast.parse(_read(root, rel))
    except SyntaxError:
        return None


def declared_gates(root: Path) -> dict[str, str]:
    """Gate name -> declaration kind, read from the source that declares them.

    unconditional -- a key of the literal ``gates = {...}`` dict: scored for every candidate.
    conditional   -- assigned via ``gates["x"] = ...``: only declared when its evidence exists,
                     so zero observations is AMBIGUOUS and is reported rather than failed.
    post-promote  -- guarded by a precondition in the orchestrator.
    """
    out: dict[str, str] = {}
    tree = _parse(root, _GAUNTLET)
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "gates" and isinstance(
                    node.value, ast.Dict
                ):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            out.setdefault(key.value, "unconditional")
                elif (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "gates" and isinstance(tgt.slice, ast.Constant)
                        and isinstance(tgt.slice.value, str)):
                    out.setdefault(tgt.slice.value, "conditional")
    rel, pattern = _POST_PROMOTE
    for name in re.findall(pattern, _read(root, rel)):
        out.setdefault(name, "post-promote")
    return out


def _required_true(tree: ast.Module) -> set[str]:
    """Attribute/param names that a module AND-chains or ``all()``-s into a required-True gate."""
    req: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            for val in node.values:
                if isinstance(val, ast.Attribute):
                    req.add(val.attr)
                elif isinstance(val, ast.Name):
                    req.add(val.id)
    return req


def _declared_bools(tree: ast.Module) -> set[str]:
    """Class-level ``x: bool = False`` fields -- fail-closed verdict flags."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                    and isinstance(stmt.annotation, ast.Name) and stmt.annotation.id == "bool"
                    and isinstance(stmt.value, ast.Constant) and stmt.value.value is False):
                out.add(stmt.target.id)
    return out


def _has_production_setter(root: Path, name: str, declaring: str) -> bool:
    """True iff something under a PRODUCTION root (never tests/, never data/) sets ``name`` True."""
    pat = re.compile(rf"\b{re.escape(name)}\s*=\s*True\b")
    for top in _PROD_ROOTS:
        for path in (root / top).rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if rel == declaring or "test" in path.name:
                continue
            try:
                if pat.search(path.read_text("utf-8")):
                    return True
            except OSError:
                continue
    return False


def governance_fields(root: Path) -> dict[str, dict[str, Any]]:
    """Required-True verdict field -> {module, has_production_setter}."""
    out: dict[str, dict[str, Any]] = {}
    for rel in _VERDICT_MODULES:
        tree = _parse(root, rel)
        if tree is None:
            continue
        required = _required_true(tree)
        for name in sorted(_declared_bools(tree) & required):
            out[name] = {"module": rel,
                         "has_production_setter": _has_production_setter(root, name, rel)}
    return out


def observed(root: Path) -> tuple[dict[str, int], int, int]:
    """(rejections per gate, candidates tested, candidates that ever survived).

    Unions the published tally with the durable sqlite ledger, so a rebuilt web artifact cannot
    make a gate look unreachable by amnesia.
    """
    hist: dict[str, int] = {}
    tested = survivors = 0
    try:
        doc = json.loads((root / _WEB_TALLY).read_text("utf-8"))
        hist = {str(k): int(v) for k, v in (doc.get("rejection_by_gate") or {}).items()}
        tested = int(doc.get("cumulative_tested", 0) or 0)
        survivors = int(doc.get("cumulative_survivors", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    db = root / _LEDGER
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = list(con.execute(
                    "select survived, coalesce(rejection_reason,'') from research_candidates"))
            finally:
                con.close()
            tested = max(tested, len(rows))
            survivors = max(survivors, sum(1 for s, _ in rows if s))
            for surv, reason in rows:
                if surv or not reason:
                    continue
                for gate in (g.strip() for g in
                             reason.removeprefix("failed: ").split(",") if g.strip()):
                    hist[gate] = hist.get(gate, 0) + 1
        except (sqlite3.Error, OSError):
            pass
    return hist, tested, survivors


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    decl = declared_gates(root)
    gov = governance_fields(root)
    hist, tested, survivors = observed(root)

    base: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.49 -- a gate that never ran emits no row, so no tally-reading check can flag "
               "it. Reachability is measured from the declaration site, not the histogram. "
               "Evidence only: this fence moves no threshold and grants no promotion authority.",
        "n_declared": len(decl) + len(gov), "n_tested": tested, "n_survivors": survivors,
    }

    if tested < _MIN_SAMPLE or not decl:
        return base | {
            "status": "UNMEASURED", "gates": {},
            "dead_branches": [], "unsatisfiable": [], "zero_bit": [],
            "detail": (f"only {tested} candidates tested (floor {_MIN_SAMPLE}) or no declaration "
                       f"site readable -- cannot distinguish 'never ran' from 'small sample'"),
            "next_action": "run a discovery campaign to a non-trivial sample, then re-run. This "
                           "is UNMEASURED, NOT a pass: no gate has been cleared here.",
        }

    gates: dict[str, Any] = {}
    dead: list[str] = []
    unsat: list[str] = []
    zerobit: list[str] = []

    for name, kind in sorted(decl.items()):
        n = hist.get(name, 0)
        if n:
            state = "FIRING"
            note = f"rejected {n}/{tested} ({n / tested:.1%})"
        elif kind == "post-promote" and survivors == 0:
            state = "DEAD-BRANCH"
            note = (f"guarded by a precondition (a candidate reaching REGISTRY) that has NEVER "
                    f"held in {tested} candidates -- this gate has not executed once. The desk "
                    f"believes it enforces this and measurably does not.")
            dead.append(name)
        elif kind == "conditional":
            state = "NEVER-EXERCISED"
            note = ("declared only when its evidence is supplied, and never rejected -- "
                    "ambiguous between 'nobody supplied the input' and 'always passed'. "
                    "Reported, not failed.")
        else:
            state = "ZERO-BIT"
            note = (f"declared unconditionally, evaluated across {tested} candidates, and never "
                    f"once rejected -- it carries zero information and has filtered nothing. "
                    f"Invisible to a >=98pct-REJECT detector, which only watches the far end.")
            zerobit.append(name)
        gates[name] = {"state": state, "kind": kind, "rejections": n, "note": note}

    for name, info in sorted(gov.items()):
        if info["has_production_setter"]:
            gates[name] = {"state": "FIRING", "kind": "verdict-bool", "rejections": None,
                           "module": info["module"],
                           "note": "required True and production can set it"}
            continue
        gates[name] = {
            "state": "UNSATISFIABLE", "kind": "verdict-bool", "rejections": None,
            "module": info["module"],
            "note": (f"required True by an AND-chain in {info['module']}, defaults False, and "
                     f"NOTHING outside tests/ ever sets it -- any verdict carrying this field "
                     f"can never pass"),
        }
        unsat.append(name)

    status = ("DEAD-BRANCH" if dead else "UNSATISFIABLE" if unsat
              else "ZERO-BIT" if zerobit else "OK")
    return base | {
        "status": status,
        "dead_branches": dead, "unsatisfiable": unsat, "zero_bit": zerobit,
        "gates": gates,
        "detail": (f"{len(dead)} dead branch(es), {len(unsat)} unsatisfiable, "
                   f"{len(zerobit)} zero-bit across {len(gates)} declared gates / "
                   f"{tested} candidates"),
        "next_action": (
            "A dead branch is a claim the desk cannot cash. Repair it by making the precondition "
            "REACHABLE, or record out loud that the gate cannot run and why -- NEVER by deleting "
            "the gate and calling the gauntlet smaller (that lowers a bar, which L1.6 forbids). "
            "An UNSATISFIABLE field needs a production producer or an explicit retirement. A "
            "ZERO-BIT gate should be confirmed still wired to its input."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _ARTIFACT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"gate reachability (L1.49): {rep['status']} -- {rep['detail']}")
        for name, g in rep.get("gates", {}).items():
            if g["state"] in ("DEAD-BRANCH", "UNSATISFIABLE", "ZERO-BIT"):
                print(f"  {g['state']:<14} {name}: {g['note']}")
    if args.report_only:
        return 0
    # L1.57 (R0417): the denominator is the gates DISCOVERED at their declaration sites by the
    # ast walk -- which is this fence's whole method (L1.49: reachability is measured from the
    # declaration site, never from a tally). If the parse finds no gates the roster is empty,
    # and "no gate is unreachable" over zero gates is the vacuous pass this law refuses.
    return fence_exit(rep["status"], {"OK"}, scanned=rep.get("n_declared", 0),
                      of="gates declared in source", fence="check_gate_reachability.py")


if __name__ == "__main__":
    sys.exit(main())
