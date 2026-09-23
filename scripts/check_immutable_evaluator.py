#!/usr/bin/env python3
"""IMMUTABLE EVALUATOR (portable fence) -- research agents may not modify the test they failed.

autoresearch-trading's split, made a law here: the files that JUDGE a hypothesis -- the
gauntlet, the multiplicity charge, the cost engine, the lockbox access, the promotion law, the
heat law and the growth governance fences -- are hashed into `data/IMMUTABLE_MANIFEST.json`.
Any change to one of them must arrive with a re-signed manifest (a human commit that runs
`--sign`), otherwise the gate is red. An organ that dislikes a verdict can change the
hypothesis; it cannot change the judge.

    python scripts/check_immutable_evaluator.py          # verify (rc=1 on drift)
    python scripts/check_immutable_evaluator.py --sign   # re-sign after a deliberate change

The MUTABLE side -- hypotheses, strategies, models, factors, proposers -- is everything else.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "desks" / "mt5" / "data" / "IMMUTABLE_MANIFEST.json"

IMMUTABLE: tuple[str, ...] = (
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/multiplicity.py",
    "desks/mt5/research/gate_policy.py",
    "desks/mt5/research/heat_policy.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py",
    "libs/portfolio/allocator_proof.py",
    "libs/portfolio/rails.py",
    "libs/portfolio/capital_modifiers.py",
    "libs/validation/redteam.py",
    "libs/validation/replay2.py",
    "libs/validation/calibration.py",
    "libs/regime/state_admission.py",
    "scripts/check_growth_governance.py",
    "scripts/check_heat_floor_wiring.py",
    "scripts/check_immutable_evaluator.py",
    "scripts/run_deadman_switch.py",
)

# ------------------------------------------------------------- the wall beyond frozen code
#: THE WALL IS NOT ONLY CODE (W19). The list above says the JUDGE may not be edited. The
#: constitution says more: the forward clocks' ledgers, the live ledger, the measured cost
#: surface and the research lineage chain are RECORDS, and a record that can be rewritten is
#: not evidence. They cannot be frozen like a source file -- they grow every hour, and hashing
#: them whole would make this fence permanently red for exactly the reason the CRLF bug did.
#: They are sealed by PREFIX instead: what was already written must still be there, byte for
#: byte, in the same order, and the only legal change is MORE records after it.
#:
#: (path-or-one-directory-glob, mode, why). `lines` = one record per line (jsonl); `rows` = a
#: JSON list, or a document with a "rows" list, whose elements are the records.
APPEND_ONLY: tuple[tuple[str, str, str], ...] = (
    ("desks/mt5/data/live_ledger.jsonl", "lines",
     "the live ledger -- the actual execution records every attribution is measured on"),
    ("desks/mt5/data/research_artifacts.jsonl", "lines",
     "the research lineage chain (libs/research/artifact_chain.py): hash-linked, append-only"),
    ("desks/mt5/reports/shadow/ledger_*.json", "rows",
     "the forward clocks' ledgers -- the preregistered evidence promotion reads"),
)

#: REBUILT, NEVER BACK-DATED. The cost surface is not append-only: it is re-measured, and a
#: fresher measurement is the whole point of it. What no self-improving organ may do is move it
#: BACKWARDS -- swap today's measured spread for an older, cheaper one and re-judge a cell that
#: failed net of cost. So the seal is the vintage stamp: it may advance, and a stamp that goes
#: backwards, or vanishes, is a breach. (path, stamp field, why)
VINTAGE: tuple[tuple[str, str, str], ...] = (
    ("desks/mt5/data/cost_surface.json", "built_at",
     "the measured cost surface -- the actual costs every net-of-cost verdict is charged"),
)


def _expand(rel: str) -> list[tuple[str, Path]]:
    """A path, or every file a one-directory glob matches, as (rel, absolute) pairs."""
    if "*" not in rel:
        return [(rel, ROOT / rel)]
    head, _, pattern = rel.rpartition("/")
    parent = ROOT / head
    if not parent.is_dir():
        return []
    return sorted((f"{head}/{p.name}", p) for p in parent.glob(pattern) if p.is_file())


def _records(path: Path, mode: str) -> list[str] | None:
    """The file's records as canonical strings, or None when it cannot be read as records."""
    try:
        raw = path.read_text("utf-8", errors="replace")
    except OSError:
        return None
    if mode == "lines":
        return [ln for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    rows = doc if isinstance(doc, list) else (doc.get("rows") if isinstance(doc, dict) else None)
    if not isinstance(rows, list):
        return None
    return [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows]


def _prefix_sha(records: Sequence[str], n: int) -> str:
    h = hashlib.sha256()
    for rec in records[:n]:
        h.update(rec.encode("utf-8", "replace"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def append_only_seal() -> dict[str, dict[str, Any]]:
    """{rel: {records, prefix_sha, mode}} for every append-only record file present HERE.

    A path this host does not have is simply not sealed: these are files the trading box writes
    and a clean clone legitimately lacks. `wall_rows` reports that as UNMEASURED with the reason
    named -- an absent record file must never read as a verified one (L1.28a).
    """
    out: dict[str, dict[str, Any]] = {}
    for rel, mode, _why in APPEND_ONLY:
        for name, path in _expand(rel):
            recs = _records(path, mode)
            if recs is None:
                continue
            half = len(recs) // 2
            out[name] = {"records": len(recs), "prefix_sha": _prefix_sha(recs, len(recs)),
                         "half": half, "half_sha": _prefix_sha(recs, half), "mode": mode}
    return out


def vintage_seal() -> dict[str, dict[str, Any]]:
    """{rel: {field, stamp}} for every rebuilt-but-never-back-dated artifact present here."""
    out: dict[str, dict[str, Any]] = {}
    for rel, field, _why in VINTAGE:
        path = ROOT / rel
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        stamp = doc.get(field) if isinstance(doc, dict) else None
        if not isinstance(stamp, str) or not stamp:
            continue
        out[rel] = {"field": field, "stamp": stamp}
    return out


def _append_only_rows(sealed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One row per append-only record file: verified, grew, behind, absent, unsealed or BREACH.

    THE OVERLAP IS WHAT IS JUDGED, and that choice is the difference between a fence that means
    something and a fence that is red on every clean checkout. The seal is taken on the box that
    WRITES these files; another host's copy is routinely shorter (an older pull, a clone that
    never had the untracked forward ledgers at all). So the prefix is recomputed at min(n_now,
    n_sealed):

        identical there, and longer   -> `grew`      the only change these files may make
        identical there, and equal    -> `verified`
        identical there, and shorter  -> `behind`    UNMEASURED, named, never a pass
        DIFFERENT there               -> BREACH      a record was rewritten, and that is the
                                                     one thing an append-only record cannot do
    """
    rows: list[dict[str, Any]] = []
    live = append_only_seal()
    for rel, mode, why in APPEND_ONLY:
        found = _expand(rel)
        if not found:
            rows.append({"path": rel, "kind": "append_only", "status": "absent", "why":
                         f"not on this host ({why}); UNMEASURED, not verified"})
            continue
        for name, path in found:
            rec = sealed.get(name)
            now = live.get(name)
            if not path.exists():
                rows.append({"path": name, "kind": "append_only", "status": "absent",
                             "why": f"not on this host ({why}); UNMEASURED, not verified"})
                continue
            if now is None:
                rows.append({"path": name, "kind": "append_only", "status": "unreadable",
                             "why": f"{path.name} could not be read as {mode} records"})
                continue
            if not isinstance(rec, Mapping):
                rows.append({"path": name, "kind": "append_only", "status": "unsealed",
                             "why": "not in the signed manifest; run --sign once",
                             "records": now["records"]})
                continue
            n_now, n_was = int(now["records"]), int(rec.get("records") or 0)
            n_half = int(rec.get("half") or 0)
            recs = _records(path, mode) or []
            # The checkpoint to judge at: the full seal when this host has at least that many
            # records, else the half seal, which is what makes a SHORTER copy checkable at all.
            if n_now >= n_was:
                at, want = n_was, str(rec.get("prefix_sha") or "")
            elif n_now >= n_half and n_half > 0:
                at, want = n_half, str(rec.get("half_sha") or "")
            else:
                rows.append({"path": name, "kind": "append_only", "status": "behind",
                             "why": f"{n_now} record(s) here against {n_was} sealed and no "
                                    "checkpoint below that: UNMEASURED, not verified",
                             "records": n_now})
                continue
            here = _prefix_sha(recs, at)
            if here != want:
                rows.append({"path": name, "kind": "append_only", "status": "breach",
                             "why": f"the sealed prefix of {at} record(s) changed "
                                    f"({want} -> {here}): a record was rewritten"})
            elif n_now < n_was:
                rows.append({"path": name, "kind": "append_only", "status": "behind",
                             "why": f"{n_now} record(s) here against {n_was} sealed; the first "
                                    f"{at} are unchanged, the rest is UNMEASURED on this host",
                             "records": n_now})
            else:
                rows.append({"path": name, "kind": "append_only",
                             "status": "verified" if n_now == n_was else "grew",
                             "why": f"{n_was} sealed record(s) unchanged; {n_now - n_was} "
                                    "appended since", "records": n_now})
    return rows


def _vintage_rows(sealed: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    live = vintage_seal()
    for rel, field, why in VINTAGE:
        now = live.get(rel)
        rec = sealed.get(rel)
        if now is None:
            rows.append({"path": rel, "kind": "vintage", "status": "absent",
                         "why": f"no readable {field} here ({why}); UNMEASURED, not verified"})
            continue
        if not isinstance(rec, Mapping):
            rows.append({"path": rel, "kind": "vintage", "status": "unsealed",
                         "why": "not in the signed manifest; run --sign once"})
            continue
        was, stamp = str(rec.get("stamp") or ""), str(now["stamp"])
        if stamp < was:
            rows.append({"path": rel, "kind": "vintage", "status": "breach",
                         "why": f"{field} moved BACKWARDS ({was} -> {stamp}): a measured cost "
                                "surface may be rebuilt, never back-dated"})
        else:
            rows.append({"path": rel, "kind": "vintage",
                         "status": "verified" if stamp == was else "rebuilt",
                         "why": f"{field} {was} -> {stamp}"})
    return rows


# ------------------------------------------------------------- generator isolation (W19)
#: "SEALED DATA NEVER REACHES A GENERATOR." The frozen list guards the judge; this guards the
#: other direction. A proposer that can read the holdout is not proposing, it is fitting -- and
#: the damage is invisible afterwards, because the candidate that comes out looks exactly like
#: one that was found honestly. The only moment this is cheap to catch is the day the line is
#: written, so the check is SOURCE INSPECTION over every organ that can mint a hypothesis.
#:
#: WHAT IS BANNED IS THE READ, NOT THE SPLIT. `expression_factory` constructs a `LockedHoldout`
#: precisely so the tail of each world is sealed away from its own search, and calls
#: `.research()` and never `open_lockbox()`. Banning the import would have banned the correct
#: behaviour and taught the next author to seal nothing.
GENERATOR_ROOTS: tuple[str, ...] = ("desks/mt5/research", "desks/mt5/scripts", "libs/research")
#: A file is a generator if it imports the donation door. Cheap prefilter, AST-confirmed.
GENERATOR_MARKER = "proposer_common"
#: Generators that do not donate through that door and must still be scanned.
EXTRA_GENERATORS: tuple[str, ...] = (
    "libs/research/generators.py",        # the alpha-grammar generators (GFlowNet, symbolic)
    "desks/mt5/research/qd_frontier.py",  # the quality-diversity worker
    "libs/research/adapters/pyribs.py",   # the QD archive adapter
    "desks/mt5/research/representation_forge.py",  # the representation forge
)
#: Organs that JUDGE rather than propose. They are allowed to reach sealed evidence -- that is
#: their function -- and the frozen list above is what guards them instead.
JUDGES: frozenset[str] = frozenset({
    "desks/mt5/scripts/external_gauntlet.py", "desks/mt5/research/promoter.py",
    "desks/mt5/research/blind_reviewer.py", "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/evidence_vault.py", "desks/mt5/research/certificate_truth.py",
})
#: Module whose import by a generator is itself the violation: it IS the sealed-tier vault.
SEALED_MODULES: frozenset[str] = frozenset({"evidence_vault"})
#: Names that read the sealed side. `LockedHoldout` is absent on purpose (see above).
SEALED_NAMES: frozenset[str] = frozenset({"open_lockbox", "LockboxService", "_seal_holdouts"})
#: Path literals that name sealed data. Matched only inside a string that LOOKS like a path, and
#: never inside a docstring, so prose about the holdout is not a finding.
SEALED_PATHS: tuple[str, ...] = ("evidence_vault.json", "data/lockbox", "holdout")


def _docstrings(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) \
                and isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            out.add(id(body[0].value))
    return out


def _is_donor(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            # BOTH SPELLINGS. `from research import proposer_common as pc` is an ImportFrom whose
            # MODULE is "research" and whose NAME is the door -- the spelling `expression_factory`
            # actually uses, and reading only the module missed the largest generator in the desk.
            names = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            if any(n.split(".")[-1] == GENERATOR_MARKER for n in names):
                return True
    return False


def _sealed_reads(rel: str, tree: ast.AST) -> list[dict[str, str]]:
    skip = _docstrings(tree)
    out: list[dict[str, str]] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import | ast.ImportFrom):
            mods = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
            for mod in mods:
                if SEALED_MODULES & set(mod.split(".")):
                    out.append({"file": rel, "line": str(line),
                                "what": f"imports the sealed vault: {mod}"})
        elif isinstance(node, ast.Attribute) and node.attr in SEALED_NAMES:
            out.append({"file": rel, "line": str(line),
                        "what": f"reaches for {node.attr} -- that opens sealed evidence"})
        elif isinstance(node, ast.Name) and node.id in SEALED_NAMES:
            out.append({"file": rel, "line": str(line),
                        "what": f"names {node.id} -- that opens sealed evidence"})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip and len(node.value) < 200 \
                and ("/" in node.value or node.value.endswith(".json")):
            for tok in SEALED_PATHS:
                if tok in node.value:
                    out.append({"file": rel, "line": str(line),
                                "what": f"names a sealed path: {node.value!r}"})
                    break
    seen: set[tuple[str, str]] = set()
    unique = []
    for row in out:
        key = (row["line"], row["what"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def generator_isolation() -> dict[str, Any]:
    """Every proposer in the desk, and what it was found reaching for.

    Reports WHAT IT SCANNED as well as what it found: a wall that fires on nothing because it
    enumerated nothing is the failure mode this desk has paid for before (L1.49 -- a gate that
    never ran is a claim it cannot cash).
    """
    candidates: dict[str, Path] = {}
    for root in GENERATOR_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or "__pycache__" in rel or rel in JUDGES:
                continue
            try:
                if GENERATOR_MARKER not in path.read_text("utf-8", errors="replace"):
                    continue
            except OSError:
                continue
            candidates[rel] = path
    for rel in EXTRA_GENERATORS:
        path = ROOT / rel
        if path.is_file() and rel not in JUDGES:
            candidates[rel] = path

    scanned: list[str] = []
    unparsed: list[str] = []
    findings: list[dict[str, str]] = []
    for rel, path in sorted(candidates.items()):
        try:
            tree = ast.parse(path.read_text("utf-8", errors="replace"), filename=rel)
        except (OSError, SyntaxError, ValueError):
            unparsed.append(rel)
            continue
        if rel not in EXTRA_GENERATORS and not _is_donor(tree):
            continue
        scanned.append(rel)
        findings.extend(_sealed_reads(rel, tree))
    return {"scanned": scanned, "n_scanned": len(scanned), "unparsed": unparsed,
            "judges_skipped": sorted(JUDGES), "findings": findings,
            "rule": "sealed data never reaches a generator; a generator may SEAL its own tail "
                    "(LockedHoldout.research) but may never open one"}


def _hashes() -> dict[str, str]:
    """SHA-256 of each guarded file, over LINE-ENDING-NORMALISED bytes.

    WHY NORMALISED, measured 2026-09-12 on the Windows trading box. A signature is a claim about
    CONTENT. Hashing raw bytes made it a claim about content AND about how the checkout happened
    to write newlines, and those two came apart:

        working tree  desks/mt5/research/promoter.py  ->  766a1119abcd663a   (CRLF)
        HEAD blob     desks/mt5/research/promoter.py  ->  8e1f39e3f4a6905f   (LF)

    Identical code, byte-different files. `run_law_gate` judges HEAD in a DETACHED WORKTREE
    whenever the tree is dirty -- and this box's tree is permanently dirty, because live state
    files (gateway_state.json and friends) are tracked and rewritten every pass. So the fence
    always hashed the LF checkout while `--sign` always hashed the CRLF working copy, and the two
    could never agree. The fence reported a BREACH on a file nobody had touched, on every run, and
    since a failing law fence refuses the push, the trading box could not reach origin at all.

    That is the worst shape a constitutional fence can take: permanently red, red about nothing,
    and blocking. A fence that cannot be satisfied by correct code stops being read as evidence
    and starts being read as an obstacle -- and then the day it fires on a REAL tamper, it looks
    exactly like the eleven days it fired on newlines.

    Normalising CRLF -> LF makes the hash mean what it always claimed to mean. It does not weaken
    the guard: any change to a byte that is not a carriage return still changes the digest, so
    every tamper this caught before it still catches.
    """
    out = {}
    for rel in IMMUTABLE:
        p = ROOT / rel
        if not p.exists():
            out[rel] = "<absent>"
            continue
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()[:16]
    return out


def sign(by: str) -> dict[str, object]:
    doc: dict[str, object] = {"signed_utc": datetime.now(tz=UTC).isoformat(), "signed_by": by,
           "files": _hashes(),
           "append_only": append_only_seal(),
           "vintage": vintage_seal(),
           "rule": ("these files judge hypotheses; a change must arrive with a re-signed "
                    "manifest -- research organs may change the hypothesis, never the judge"),
           "record_rule": ("the ledgers, the live fills, the cost surface and the lineage chain "
                           "are RECORDS: the sealed prefix may never change, only grow, and a "
                           "measured cost surface may be rebuilt but never back-dated")}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def wall_rows() -> list[dict[str, Any]]:
    """Every non-frozen guarded path with its verdict, absent ones included and named.

    Absence is a verdict here, never a pass: a host without the forward ledgers reports them
    UNMEASURED, and `--json` carries the row so a caller can tell "nothing to check" from
    "checked and clean" (L1.28a / WS-005).
    """
    try:
        doc = json.loads(MANIFEST.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    sealed_a = doc.get("append_only") if isinstance(doc, dict) else None
    sealed_v = doc.get("vintage") if isinstance(doc, dict) else None
    return _append_only_rows(sealed_a if isinstance(sealed_a, Mapping) else {}) + \
        _vintage_rows(sealed_v if isinstance(sealed_v, Mapping) else {})


def check() -> list[dict[str, str]]:
    try:
        rec = json.loads(MANIFEST.read_text("utf-8")).get("files") or {}
    except (OSError, ValueError):
        return [{"file": str(MANIFEST), "why": "no IMMUTABLE_MANIFEST.json; run --sign once"}]
    now = _hashes()
    out = []
    for rel, h in now.items():
        if rel not in rec:
            out.append({"file": rel, "why": "immutable file not in the signed manifest"})
        elif rec[rel] != h:
            out.append({"file": rel, "why": f"changed since signing ({rec[rel]} -> {h})"})
    for rel in rec:
        if rel not in now:
            out.append({"file": rel, "why": "in the manifest but no longer declared immutable"})
    for row in wall_rows():
        if row["status"] == "breach":
            out.append({"file": str(row["path"]), "why": str(row["why"])})
    for hit in generator_isolation()["findings"]:
        out.append({"file": f"{hit['file']}:{hit['line']}",
                    "why": f"GENERATOR READS SEALED DATA -- {hit['what']}"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sign", action="store_true")
    # SEAL THE RECORDS WITHOUT BLESSING THE CODE. `--sign` re-signs everything, so on a box whose
    # frozen files have already drifted it would launder those drifts in the same act -- the one
    # thing this fence exists to prevent. This flag writes ONLY the record seals and leaves the
    # `files` section exactly as it was, so a stale judge hash stays red while the ledgers,
    # forward clocks and cost surface start being watched today.
    ap.add_argument("--seal-records", action="store_true")
    ap.add_argument("--by", default="principal")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.sign:
        d = sign(a.by)
        print(f"immutable manifest signed by {a.by}: {len(d['files'])} files")  # type: ignore[arg-type]
        return 0
    if a.seal_records:
        try:
            doc = json.loads(MANIFEST.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        seal_a, seal_v = append_only_seal(), vintage_seal()
        doc["append_only"] = seal_a
        doc["vintage"] = seal_v
        doc["records_sealed_utc"] = datetime.now(tz=UTC).isoformat()
        doc["records_sealed_by"] = a.by
        doc["record_rule"] = ("the ledgers, the live fills, the cost surface and the lineage "
                              "chain are RECORDS: the sealed prefix may never change, only "
                              "grow, and a measured cost surface may be rebuilt, never "
                              "back-dated")
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
        print(f"record wall sealed by {a.by}: {len(seal_a)} append-only, {len(seal_v)} vintage "
              "(the frozen-file section was NOT re-signed)")
        return 0
    findings = check()
    rows = wall_rows()
    gen = generator_isolation()
    tally: dict[str, int] = {}
    for row in rows:
        tally[str(row["status"])] = tally.get(str(row["status"]), 0) + 1
    if a.json:
        print(json.dumps({"ok": not findings, "findings": findings, "wall": rows,
                          "generator_isolation": gen}, indent=1))
    else:
        print(f"immutable evaluator: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        print(f"  frozen files {len(IMMUTABLE)}  records {len(rows)} "
              f"({', '.join(f'{k}={v}' for k, v in sorted(tally.items())) or 'none'})  "
              f"generators scanned {gen['n_scanned']}")
        for f in findings:
            print(f"  BREACH {f['file']}: {f['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
