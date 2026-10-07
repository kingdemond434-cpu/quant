"""Preregistration: a cell's contract is sealed with a SHA before anything evaluates it.

    seal(contract)      -> writes preregistrations/<cell_id>.json {contract, sha}, read-only
    load(cell_id)       -> the contract, after re-hashing it; any change raises
    verify(cell_id, spec) -> does the spec the evaluator judged equal the sealed one?
    amend(cell_id, ...) -> a NEW cell_id (parent_cell_id = old, same trial family)

Sealing the same cell_id twice with the same content is a no-op; with different content it
raises `PreregMutationError`. A contract file edited on disk after sealing fails `load` for the
same reason. So a change after evaluation start can only exist as a new cell with its own id,
which is what keeps the multiplicity count honest: the evaluator never judges a contract that
moved under it.

TRIAL LINEAGE. Every contract carries `trial_family_id` and `parent_cell_id`. A descendant (an
amendment, a symbol transfer, a regime child of the same rule) inherits its parent's family.
This is LINEAGE: `experiment_ledger` reads it (via the mining digest) as the lineage view of
trials it already counts, and the multiple-testing charge stays the gauntlet's own
deflated-Sharpe trial count per registered family.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Fields that define WHAT is tested. `verify` compares these against the judged spec.
SPEC_FIELDS: tuple[str, ...] = ("sym", "family", "params", "timeframe")


class PreregMutationError(RuntimeError):
    """A sealed contract was changed (on disk, or by re-sealing different content)."""


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def sha_of(contract: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(dict(contract)).encode("utf-8")).hexdigest()


def trial_family_id(mechanism_family: str, mechanism_subtype: str, family: str) -> str:
    """The family a trial is charged to: one mechanism expressed by one registered family."""
    key = f"{mechanism_family}|{mechanism_subtype}|{family}"
    return "tf_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def spec_of(contract: Mapping[str, Any]) -> dict[str, Any]:
    spec = contract.get("spec") or {}
    return {k: (spec.get(k) if k != "params" else dict(spec.get("params") or {}))
            for k in SPEC_FIELDS} if isinstance(spec, Mapping) else {}


class PreregStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, cell_id: str) -> Path:
        safe = "".join(ch for ch in cell_id if ch.isalnum() or ch in "-_.")
        if not safe:
            raise ValueError("empty cell id")
        return self.root / f"{safe}.json"

    def seal(self, contract: Mapping[str, Any], *, now: datetime | None = None) -> str:
        """Seal and return the SHA. Required keys: cell_id, spec, falsifier, trial_family_id."""
        body = dict(contract)
        for k in ("cell_id", "spec", "falsifier", "trial_family_id"):
            if not body.get(k):
                raise ValueError(f"contract missing {k!r}")
        body.setdefault("parent_cell_id", "")
        body.setdefault("sealed_at", (now or datetime.now(tz=UTC)).isoformat())
        p = self.path(str(body["cell_id"]))
        if p.exists():
            existing = self.load(str(body["cell_id"]))
            mine = {k: v for k, v in body.items() if k != "sealed_at"}
            theirs = {k: v for k, v in existing.items() if k != "sealed_at"}
            if canonical(mine) != canonical(theirs):
                raise PreregMutationError(
                    f"{body['cell_id']}: already sealed with different content; an amendment "
                    "must be a new cell (use amend)")
            return sha_of(existing)
        sha = sha_of(body)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"contract": body, "sha256": sha}, ensure_ascii=False,
                                  indent=1, sort_keys=True, default=str), "utf-8")
        os.replace(tmp, p)
        # Read-only on disk: an accidental write fails loudly; a deliberate one fails `load`.
        os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        return sha

    def load(self, cell_id: str) -> dict[str, Any]:
        p = self.path(cell_id)
        doc = json.loads(p.read_text("utf-8"))
        contract = doc.get("contract") if isinstance(doc, dict) else None
        if not isinstance(contract, dict):
            raise PreregMutationError(f"{cell_id}: contract file malformed")
        if sha_of(contract) != doc.get("sha256"):
            raise PreregMutationError(f"{cell_id}: contract changed after sealing "
                                      f"(sha {doc.get('sha256')} no longer matches)")
        return contract

    def sha(self, cell_id: str) -> str:
        return sha_of(self.load(cell_id))

    def exists(self, cell_id: str) -> bool:
        return self.path(cell_id).exists()

    def verify(self, cell_id: str, judged_spec: Mapping[str, Any]) -> tuple[bool, str]:
        """Did the evaluator judge exactly the sealed spec? (ok, why-not)."""
        try:
            sealed = spec_of(self.load(cell_id))
        except (OSError, ValueError, PreregMutationError) as exc:
            return False, f"contract unreadable or mutated: {exc}"
        judged = {k: (judged_spec.get(k) if k != "params" else
                      dict(judged_spec.get("params") or {})) for k in SPEC_FIELDS}
        for k in SPEC_FIELDS:
            if k == "timeframe" and not judged.get(k):
                continue          # the verdict row may omit the chart; the id carries it
            if canonical(sealed.get(k)) != canonical(judged.get(k)):
                return False, f"{k}: sealed {sealed.get(k)!r} != judged {judged.get(k)!r}"
        return True, ""

    def amend(self, cell_id: str, changes: Mapping[str, Any], *, new_cell_id: str,
              now: datetime | None = None) -> tuple[str, str]:
        """A changed contract is a NEW cell in the SAME trial family. Returns (cell_id, sha)."""
        parent = self.load(cell_id)
        if new_cell_id == cell_id:
            raise PreregMutationError("an amendment needs a new cell id")
        child = {k: v for k, v in parent.items() if k != "sealed_at"}
        child.update(dict(changes))
        child["cell_id"] = new_cell_id
        child["parent_cell_id"] = cell_id
        child["trial_family_id"] = parent["trial_family_id"]
        return new_cell_id, self.seal(child, now=now)
