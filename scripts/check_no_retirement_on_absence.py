#!/usr/bin/env python
"""NOTHING IS RETIRED ON AN ABSENCE (LAWS 7) -- the fence for every pass that removes.

WHAT IT PROVES, and why each half is needed.

1. EVERY DECLARED DESTRUCTIVE PATH STILL EXISTS. A row in
   `libs/ops/reference_freshness.DESTRUCTIVE_PATHS` that names a module or a function this tree no
   longer has is a lie the inventory is telling, and an inventory that lies is worse than none --
   it reads GREEN for an act nobody is watching any more.

2. EVERY `guarded` ROW ACTUALLY CALLS THE GUARD. Proved from the AST, not from an import line and
   not from a comment: the guard call (`require_live_reference` / `assess_reference` /
   `reference_is_live`) must appear inside the declared `guard_site` function. "It imports the
   module" is the shape of every dead safety rail this desk has ever found.

3. EVERY GUARDED ROW'S REFERENCE HAS A LEASE OR A DERIVED CADENCE. A reference whose staleness
   nobody has decided cannot be judged stale, so a guard over it is a guard that can never fire.
   `lease_for()` resolves envelope -> registry `max_silence_s` -> cadence x 2 (recorded as
   derived) -> nothing; the last case fails here.

4. THE UNGUARDED COUNT RATCHETS DOWN. `UNGUARDED_CEILING` may only fall. The fence also refuses a
   count above the PREVIOUS artifact's, so the ratchet holds between ceiling edits too.

5. THE TREE IS RE-SCANNED, so a destructive act added tomorrow is not invisible because nobody
   remembered to add a row. The scan is deliberately two-condition (a removal VOCABULARY name AND
   a real removal ACT in the body) because a one-condition scan returns hundreds of rows, gets
   ignored, and then the fence is decoration -- L1.43: a gate that cries wolf gets switched off.
   Undeclared candidates are published and ratcheted, not failed on sight, because the honest
   first state of a new scanner is a backlog and a backlog that fails the gate gets the scanner
   deleted rather than the backlog drained.

6. THE INVENTORY IS NOT STALE. The artifact this fence writes carries the fingerprint of the
   destructive surface it described. If the previous artifact is older than its lease AND the live
   fingerprint has moved, the fence has not run since the surface changed -- the artifact was
   describing a tree that no longer exists, which is exactly the "a gate that never ran is a claim
   the desk cannot cash" case (L1.49). Stale WITHOUT drift is reported, not failed: an old
   description of an unchanged surface is still true, and failing on it would be timidity.

PORTABLE. It reads the tree and one tracked module, so it means the same in CI, in a fresh clone
and on the box. No desk state is required; a missing previous artifact is UNMEASURED (this run
writes it), never a failure.

Artifact: `desks/mt5/reports/DESTRUCTIVE_PATHS.json`.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import reference_freshness as rf  # noqa: E402

ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "DESTRUCTIVE_PATHS.json"

#: THE RATCHET. Declared destructive paths that still remove without proving their reference.
#: This number may only FALL. 2026-09-23: 2 -- both inside certificate_truth.apply (the row-retire
#: branch and the survivor-ledger branch), owned by another builder in the same session (it is
#: restoring the 837 rows the empty canon retired). One require_live_reference at the top of
#: apply() closes both; it lands in that builder's edit rather than in a second one racing it in
#: the same file.
UNGUARDED_CEILING = 2

#: Undeclared candidates the tree scan finds. Also ratchets down: each one is either given a row
#: (and a status) or shown to be a false positive of the two-condition rule. 2026-09-23: 6 --
#: certificate_truth.repair and promoter.reconcile_capital/main (owned by other builders or
#: sealed), coverage_tensor.observe_world and check_job_manifest.main (in-memory dict pops), and
#: make_probe_worktree.remove (scratch teardown).
UNDECLARED_CEILING = 6

#: How long the inventory stays believable. The law gate runs at least daily, so a day plus the
#: desk's standard two-hour slack.
INVENTORY_LEASE_S = 26 * 3600.0

#: Where a destructive act can live. Everything else in the tree is out of this fence's scope and
#: the artifact says so, rather than implying the scan covered it.
SCAN_DIRS = (
    "desks/mt5/research",
    "desks/mt5/scripts",
    "libs",
    "scripts",
)

#: IMMUTABLE (the sealed four). A destructive path found in one of these is REPORTED FOR THE
#: PRINCIPAL and never edited by a session.
SEALED = frozenset({
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/research/promoter.py",
    # The seal names `desks/mt5/research/allocator_proof.py`; the file in this tree is
    # `libs/portfolio/allocator_proof.py`. BOTH are listed so a move cannot quietly unseal it and
    # so the discrepancy is on the record rather than resolved by one session's guess.
    "desks/mt5/research/allocator_proof.py",
    "libs/portfolio/allocator_proof.py",
    "libs/regime/state_admission.py",
})

#: Condition A of the scan: the act NAMES itself as a removal.
REMOVAL_WORDS = (
    "retire", "purge", "demote", "delete", "prune", "evict", "revoke", "drop",
    "remove", "expire", "void", "quarantine", "reap", "cull", "unenrol", "unenroll",
)

#: Condition A, second form: the act does not NAME itself a removal but RECORDS one. `apply()` in
#: certificate_truth.py is called `apply`; what gives it away is that it writes `retired_reason`.
#: Searched in string constants only, so a function that merely mentions the word in a comment or
#: reads a field is not dragged in.
REMOVAL_STATE_TOKENS = (
    "retired_reason", "retired_at", "retired_by", "retired_certificates", "RETIRED",
    "purged", "evicted", "revoked", "demoted", "deleted_at", "removed_at", "voided",
    "no longer backed", "not backed", "unenrolled",
)

#: Condition B of the scan: the body CONTAINS a removal act. Attribute calls, builtins and the one
#: SQL verb that removes.
REMOVAL_CALLS = frozenset({
    "unlink", "rmtree", "remove", "rmdir", "pop", "discard", "clear", "popitem", "truncate",
})
REMOVAL_SQL = ("DELETE FROM", "DROP TABLE", "DROP INDEX")


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


# --------------------------------------------------------------------------- AST helpers

def _parse(p: Path) -> ast.Module | None:
    return _parse_with_source(p)[0]


def _parse_with_source(p: Path) -> tuple[ast.Module | None, str]:
    try:
        src = p.read_text(encoding="utf-8-sig")
        return ast.parse(src, filename=str(p)), src
    except (OSError, SyntaxError, ValueError):
        return None, ""


def _functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function in the module by name, including methods (a method keeps its bare name so a
    declared row may name `_apply` without knowing whether it is a method today)."""
    out: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, node)
    return out


def _calls_in(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _records_removal(node: ast.AST) -> bool:
    """Condition A's second form: the body WRITES the vocabulary of removal into a store, even
    though the function is called something neutral like `apply`."""
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                and any(tok in sub.value for tok in REMOVAL_STATE_TOKENS)):
            return True
    return False


def _removal_act(node: ast.AST) -> str:
    """The first concrete removal act inside this function, or "" if there is none."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Delete):
            return "del"
        if isinstance(sub, ast.Call):
            fn = sub.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if name in REMOVAL_CALLS:
                return f"{name}()"
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            upper = sub.value.upper()
            for verb in REMOVAL_SQL:
                if verb in upper:
                    return verb
    return ""


# --------------------------------------------------------------------------- the tree scan

def scan_tree(root: Path | None = None) -> list[dict[str, Any]]:
    """Candidate destructive paths: functions that both NAME a removal and PERFORM one.

    Returns rows sorted by module then function, each naming the act found, so a reader can tell a
    real deletion from a `pop()` used as a dict default.
    """
    base = root or ROOT
    rows: list[dict[str, Any]] = []
    for rel_dir in SCAN_DIRS:
        d = base / rel_dir
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            parts = set(p.parts)
            if "__pycache__" in parts or "_retired" in parts or "tests" in parts:
                continue
            tree, src = _parse_with_source(p)
            if tree is None:
                continue
            module = _rel(p)
            # CHEAP PRE-FILTER. Walking every function of every file in libs/ and scripts/ looking
            # for a string constant costs minutes; one substring scan of the raw source says
            # whether the expensive walk can possibly find anything.
            may_record = any(tok in src for tok in REMOVAL_STATE_TOKENS)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                lowered = node.name.lower()
                named = any(w in lowered for w in REMOVAL_WORDS)
                records = may_record and _records_removal(node)
                if not (named or records):
                    continue
                act = _removal_act(node)
                if not act:
                    continue
                rows.append({
                    "module": module, "function": node.name,
                    "lines": [node.lineno, getattr(node, "end_lineno", node.lineno)],
                    "act": act, "named": named, "records_removal": records,
                    "sealed": module in SEALED,
                    "guarded_call": bool(_calls_in(node) & set(rf.guard_call_names())),
                })
    rows.sort(key=lambda r: (r["module"], r["function"]))
    return rows


def fingerprint(rows: list[dict[str, Any]]) -> str:
    """A stable hash of the destructive SURFACE (module + function + act), so a stale inventory can
    be told from an inventory that is merely old."""
    payload = "\n".join(f"{r['module']}::{r['function']}::{r['act']}" for r in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- the checks

def audit(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    problems: list[str] = []
    notes: list[str] = []
    declared: list[dict[str, Any]] = []

    scanned = scan_tree(base)
    scanned_index = {(r["module"], r["function"]): r for r in scanned}

    for spec in rf.DESTRUCTIVE_PATHS:
        row = spec.as_dict()
        module_path = base / spec.module
        tree = _parse(module_path) if module_path.exists() else None
        row["module_exists"] = module_path.exists()
        row["sealed_file"] = spec.module in SEALED
        funcs = _functions(tree) if tree is not None else {}
        row["function_found"] = spec.function in funcs
        site = spec.guard_site or spec.function
        row["guard_site"] = site
        site_node = funcs.get(site)
        row["guard_call_found"] = bool(
            site_node is not None and (_calls_in(site_node) & set(rf.guard_call_names())))
        if site_node is not None:
            row["guard_site_lines"] = [site_node.lineno,
                                       getattr(site_node, "end_lineno", site_node.lineno)]

        # The reference's lease. A `positive` row judges live evidence rather than a stored file,
        # so it is exempt by construction -- there is no file whose absence could authorise it.
        lease_s: float | None = None
        lease_source = rf.UNMEASURED
        writer = rf.UNMEASURED
        ref_path = base / spec.reference
        row["reference_is_file"] = ref_path.exists() or spec.reference.endswith(".json")
        if row["reference_is_file"]:
            lease_s, lease_source, writer = rf.lease_for(ref_path)
            state = rf.assess_reference(ref_path)
            row["reference_verdict"] = state.verdict
            row["reference_rows"] = state.rows
            row["reference_age_s"] = state.age_s
        row["lease_s"] = lease_s
        row["lease_source"] = lease_source
        row["reference_writer"] = writer

        if not row["module_exists"]:
            problems.append(f"{spec.path_id}: declared module {spec.module} does not exist -- an "
                            f"inventory that names a file this tree lost reads GREEN for an act "
                            f"nobody is watching")
        elif not row["function_found"]:
            problems.append(f"{spec.path_id}: {spec.module} has no function {spec.function!r} -- "
                            f"the inventory is describing code that moved")
        if spec.status == "guarded":
            if not row["guard_call_found"]:
                problems.append(
                    f"{spec.path_id}: declared guarded but {spec.module}:{site} calls none of "
                    f"{rf.guard_call_names()} -- an import is not a guard")
            if row["reference_is_file"] and lease_s is None:
                problems.append(
                    f"{spec.path_id}: reference {spec.reference} has NO lease and no cadence to "
                    f"derive one from (writer {writer}) -- a reference whose staleness nobody has "
                    f"decided can never be judged stale, so the guard over it can never fire")
        if spec.status == "unguarded":
            notes.append(f"{spec.path_id}: UNGUARDED -- {spec.note or 'no reason recorded'}")
        if spec.status == "sealed" or row["sealed_file"]:
            notes.append(f"{spec.path_id}: inside a SEALED file ({spec.module}) -- "
                         f"for the principal, never edited by a session")
        row["scanner_saw_it"] = (spec.module, spec.function) in scanned_index
        declared.append(row)

    declared_keys = {(s.module, s.function) for s in rf.DESTRUCTIVE_PATHS}
    undeclared = [r for r in scanned if (r["module"], r["function"]) not in declared_keys]
    n_unguarded = sum(1 for s in rf.DESTRUCTIVE_PATHS if s.status == "unguarded")
    n_guarded = sum(1 for s in rf.DESTRUCTIVE_PATHS if s.status == "guarded")
    n_positive = sum(1 for s in rf.DESTRUCTIVE_PATHS if s.status == "positive")
    n_sealed = sum(1 for s in rf.DESTRUCTIVE_PATHS if s.status == "sealed" or s.module in SEALED)

    previous = _previous()
    prev_unguarded = previous.get("unguarded") if isinstance(previous, dict) else None
    prev_undeclared = previous.get("undeclared_count") if isinstance(previous, dict) else None
    fp = fingerprint(scanned)
    stale = _inventory_staleness(previous, fp)

    if n_unguarded > UNGUARDED_CEILING:
        problems.append(f"unguarded destructive paths {n_unguarded} > ceiling "
                        f"{UNGUARDED_CEILING}: the ratchet only falls (L1.50)")
    if isinstance(prev_unguarded, int) and n_unguarded > prev_unguarded:
        problems.append(f"unguarded destructive paths rose {prev_unguarded} -> {n_unguarded}: "
                        f"the ratchet only falls (L1.50)")
    if len(undeclared) > UNDECLARED_CEILING:
        problems.append(f"undeclared destructive candidates {len(undeclared)} > ceiling "
                        f"{UNDECLARED_CEILING}: every candidate is given a row or shown to be a "
                        f"false positive; the ratchet only falls (L1.50)")
    if isinstance(prev_undeclared, int) and len(undeclared) > prev_undeclared:
        problems.append(f"undeclared destructive candidates rose {prev_undeclared} -> "
                        f"{len(undeclared)}: the ratchet only falls (L1.50)")
    if stale["fatal"]:
        problems.append(stale["why"])
    elif stale["why"]:
        notes.append(stale["why"])

    recent = rf.stand_downs(limit=25)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "law": "LAWS 7: NOTHING IS RETIRED ON AN ABSENCE",
        "guard": "libs/ops/reference_freshness.py",
        "fence": "scripts/check_no_retirement_on_absence.py",
        "scan_dirs": list(SCAN_DIRS),
        "sealed_files": sorted(SEALED),
        "declared": declared,
        "counts": {
            "declared": len(declared), "guarded": n_guarded, "positive": n_positive,
            "sealed": n_sealed, "unguarded": n_unguarded, "undeclared": len(undeclared),
            "scanned_candidates": len(scanned),
        },
        "unguarded": n_unguarded,
        "unguarded_ceiling": UNGUARDED_CEILING,
        "undeclared_count": len(undeclared),
        "undeclared_ceiling": UNDECLARED_CEILING,
        "undeclared": undeclared,
        "surface_fingerprint": fp,
        "inventory_staleness": stale,
        "stand_downs_recent": recent,
        "stand_downs_recorded": len(recent),
        "for_the_principal": [r for r in declared if r.get("sealed_file")],
        "notes": notes,
        "problems": problems,
        "ok": not problems,
    }


def _previous() -> dict[str, Any]:
    try:
        doc = json.loads(ARTIFACT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _inventory_staleness(previous: dict[str, Any], live_fp: str) -> dict[str, Any]:
    """Was the inventory still describing this tree?

    MISSING is UNMEASURED, never a failure -- a fresh clone has not run this fence yet and this run
    writes it. Old-but-accurate is reported. Old AND describing a surface that has since moved is
    fatal: the fence had stopped running while the destructive surface changed under it.
    """
    if not previous:
        return {"verdict": rf.UNMEASURED, "fatal": False, "age_s": None, "drift": None,
                "why": "no previous DESTRUCTIVE_PATHS.json: UNMEASURED, written by this run"}
    stamp = previous.get("generated_at")
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        age = max(0.0, (datetime.now(tz=UTC) - t).total_seconds())
    except (TypeError, ValueError):
        return {"verdict": rf.UNREADABLE, "fatal": False, "age_s": None, "drift": None,
                "why": "previous DESTRUCTIVE_PATHS.json has no readable generated_at: UNMEASURED"}
    drift = str(previous.get("surface_fingerprint") or "") != live_fp
    if age <= INVENTORY_LEASE_S:
        return {"verdict": rf.FRESH, "fatal": False, "age_s": age, "drift": drift, "why": ""}
    if not drift:
        return {"verdict": rf.STALE, "fatal": False, "age_s": age, "drift": False,
                "why": (f"inventory is {age / 3600.0:.1f}h old (lease "
                        f"{INVENTORY_LEASE_S / 3600.0:.0f}h) but the destructive surface has not "
                        f"moved, so its description is still true -- reported, not failed")}
    return {"verdict": rf.STALE, "fatal": True, "age_s": age, "drift": True,
            "why": (f"inventory is {age / 3600.0:.1f}h old (lease "
                    f"{INVENTORY_LEASE_S / 3600.0:.0f}h) AND the destructive surface moved "
                    f"({previous.get('surface_fingerprint')} -> {live_fp}): this fence stopped "
                    f"running while removals changed under it, so the inventory was describing a "
                    f"tree that no longer exists (L1.49)")}


def write_artifact(doc: dict[str, Any], path: Path | None = None) -> Path:
    target = path or ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact and exit 0")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    ap.add_argument("--list-undeclared", action="store_true",
                    help="print the tree scan's undeclared candidates")
    args = ap.parse_args(argv)

    doc = audit()
    if not args.no_write:
        write_artifact(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0

    c = doc["counts"]
    print(f"destructive paths: declared={c['declared']} guarded={c['guarded']} "
          f"positive={c['positive']} sealed={c['sealed']} unguarded={c['unguarded']} "
          f"(ceiling {UNGUARDED_CEILING})")
    print(f"tree scan: {c['scanned_candidates']} candidates, {c['undeclared']} undeclared "
          f"(ceiling {UNDECLARED_CEILING}); surface {doc['surface_fingerprint']}")
    print(f"inventory: {doc['inventory_staleness']['verdict']} | "
          f"stand-downs recorded: {doc['stand_downs_recorded']}")
    if args.list_undeclared:
        for r in doc["undeclared"]:
            print(f"  - {r['module']}:{r['function']} [{r['act']}] "
                  f"{'GUARD-CALL' if r['guarded_call'] else ''}")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"]:
        print("check_no_retirement_on_absence: OK")
        return 0
    print("check_no_retirement_on_absence: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
