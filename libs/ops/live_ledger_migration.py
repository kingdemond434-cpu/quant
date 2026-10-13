"""Lossless adoption handoff for previously corrected broker ledger metadata."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from libs.ops.live_ledger_view import FIELDS, LedgerViewError, effective_text
from libs.ops.release_promotion import AdoptionDecision, Git, code_paths


def authorized_handoff(decision: AdoptionDecision, target: str, git: Git | None = None) -> bool:
    """Accept the released gate choice, including its already-adopted production commit.

    After adoption the gate can HOLD an unreleased development tip. The exact
    production commit already at HEAD remains eligible for its state handoff.
    The caller also verifies that target's immutable release seal before writing.
    """
    if decision.decision in {"ADOPT_TIP", "ADOPT_RELEASE"}:
        return decision.target == target
    if (decision.decision != "HOLD" or not decision.unreleased_code
            or decision.release_sha != target or not decision.head):
        return False
    if decision.head == target:
        return True
    # The existing adopter records a merge retaining box state. Prove that
    # descendant contains the exact released code rather than requiring equal IDs.
    return (git is not None and git.is_ancestor(target, decision.head)
            and not code_paths(git.changed(target, decision.head)))


def migration_bytes(baseline: bytes, current: bytes, corrections: bytes,
                    manifest: dict[str, Any]) -> bytes:
    """Return sealed original prefix plus every newer broker record, or refuse.

    The effective output must reproduce the box's current consumer rows exactly.
    No profit, account, deal identity or newly recorded trade may change.
    """
    header = json.loads(corrections.splitlines()[0])
    count = header["raw_prefix_records"]
    if type(count) is not int or count < 1:
        raise LedgerViewError("Invalid migration prefix count")
    prefix = b"".join(baseline.replace(b"\r\n", b"\n").splitlines(keepends=True)[:count])
    if hashlib.sha256(prefix).hexdigest() != header["raw_prefix_sha256"]:
        raise LedgerViewError("Migration baseline is not the original sealed broker prefix")
    old = [json.loads(line) for line in prefix.splitlines() if line.strip()]
    now = [json.loads(line) for line in current.splitlines() if line.strip()]
    by_id = {row["deal"]: row for row in now}
    if len(by_id) != len(now):
        raise LedgerViewError("Current ledger duplicates a broker deal")
    for original in old:
        revised = by_id.get(original["deal"])
        if revised is None or not set(original) <= set(revised):
            raise LedgerViewError("Migration would lose an original broker record or field")
        changed = {key for key in revised if original.get(key) != revised[key]}
        if changed - FIELDS:
            raise LedgerViewError("Migration changes financial facts or account identity")
    old_ids = {row["deal"] for row in old}
    following = [line for line in current.splitlines(keepends=True)
                 if line.strip() and json.loads(line)["deal"] not in old_ids]
    result = prefix + b"".join(following)
    already_migrated = hashlib.sha256(
        b"".join(current.replace(b"\r\n", b"\n").splitlines(keepends=True)[:count])
    ).hexdigest() == header["raw_prefix_sha256"]
    # Exercise the actual consumer, including the amendment seal, before any live write.
    with tempfile.TemporaryDirectory(prefix="quant-ledger-plan-") as directory:
        path = Path(directory) / "live_ledger.jsonl"
        path.with_name("live_ledger_corrections.jsonl").write_bytes(corrections)
        path.with_name("IMMUTABLE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        projected = effective_text(path, (current if already_migrated else result).decode("utf-8"))
    if not already_migrated and [json.loads(line) for line in projected.splitlines()] != now:
        raise LedgerViewError("Migration does not preserve the current effective ledger")
    return current if already_migrated else result
