"""CANONICAL POLICY RESOLUTION -- the mandate's own II-B/II-D, made mechanical.

WHY THIS EXISTS. The PRE-DEEPSEEK master mandate (docs/policy/PRE_DEEPSEEK_MASTER_MANDATE.md)
rules that a policy is NOT authoritative until persisted, hashed and version-controlled, and that
every agent resolves the same (version, hash) or the mismatch FAILS VISIBLE. Persisting the file
satisfies none of that on its own -- II-H: markdown alone is not implementation. This module is
the LOAD half: one function every agent calls, one verdict shape, and a hash comparison that
cannot be satisfied by a stale copy.

WHAT IT DELIBERATELY IS NOT. Not a second policy authority (the mandate forbids one): it holds no
policy content, only the mechanics of reading the state record and checking the bytes on disk
against it. Not a prompt injector: II-F rules the mandate is never pasted into inference calls,
so `resolve()` returns metadata -- version, hash, verdict -- and the caller loads sections of the
file on demand if it needs the text.

THE FAIL-VISIBLE CONTRACT. Three verdicts, and only one is a pass:
    RESOLVED       -- state record read, policy file present, hash matches byte-for-byte.
    HASH_MISMATCH  -- the file was edited without regenerating the state record (II-D names this
                      exact class). The policy on disk is UNVERIFIED and consequential work must
                      not proceed on it.
    MISSING_POLICY -- state record or policy file absent/unreadable. UNKNOWN, never a pass.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["POLICY_STATE", "resolve"]

_ROOT = Path(__file__).resolve().parents[2]
POLICY_STATE = "docs/policy/POLICY_STATE.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root: Path | None = None) -> dict[str, Any]:
    """Resolve canonical policy state. Never raises -- a resolver that dies reads as silence, and
    silence is the failure mode II-D exists to prevent. The verdict carries the failure instead."""
    base = root or _ROOT
    out: dict[str, Any] = {
        "resolved_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "verdict": "MISSING_POLICY",
    }
    try:
        state = json.loads((base / POLICY_STATE).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        out["why"] = f"policy state unreadable: {type(exc).__name__}: {str(exc)[:120]}"
        return out

    out["canonical_policy_version"] = state.get("canonical_policy_version")
    declared = str(state.get("canonical_policy_hash", "")).removeprefix("sha256:")
    rel = str(state.get("policy_file", ""))
    out["policy_file"] = rel
    try:
        actual = _sha256(base / rel)
    except OSError as exc:
        out["why"] = f"policy file unreadable: {type(exc).__name__}: {str(exc)[:120]}"
        return out

    out["canonical_policy_hash"] = f"sha256:{actual}"
    if actual == declared and declared:
        out["verdict"] = "RESOLVED"
    else:
        out["verdict"] = "HASH_MISMATCH"
        out["why"] = (
            "the policy file on disk does not match the recorded hash -- it was edited without "
            "regenerating POLICY_STATE.json in the same commit, or the state record is stale. "
            f"declared={declared[:16]}... actual={actual[:16]}... The policy is UNVERIFIED and "
            "consequential work must not proceed on it (mandate II-D: FAIL VISIBLE)")
    return out


if __name__ == "__main__":
    print(json.dumps(resolve(), indent=1))
