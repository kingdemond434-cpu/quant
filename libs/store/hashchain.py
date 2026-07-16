"""Hash-chain primitives for tamper-evident, append-only tables.

Each row hashes its own content together with the previous row's hash, forming a chain:
any retroactive edit to a row (or a reordering) breaks every hash after it, which
:func:`libs.store.audit.verify_audit_chain` and friends detect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

# The chain's anchor: the predecessor hash of the very first row.
GENESIS_PREV_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` to canonical JSON (sorted keys, compact, ``str`` fallback)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_chain_hash(fields: Mapping[str, Any]) -> str:
    """Compute a row hash from its content fields (which must include ``prev_hash``)."""
    return sha256_hex(canonical_json(dict(fields)))


def verify_chain(
    rows: Sequence[Mapping[str, Any]],
    build_fields: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> tuple[bool, int | None, str]:
    """Verify a hash chain given rows ordered by ``seq``.

    Checks contiguous sequence numbers (from 1), correct ``prev_hash`` linkage, and that each
    stored ``row_hash`` matches a recomputation of its content — so any edit, deletion, or
    reordering is detected.

    Returns ``(ok, broken_seq, message)``.
    """
    prev = GENESIS_PREV_HASH
    expected_seq = 1
    for row in rows:
        seq = int(row["seq"])
        if seq != expected_seq:
            return False, seq, f"non-contiguous sequence: expected {expected_seq}, got {seq}"
        if row["prev_hash"] != prev:
            return False, seq, f"prev_hash mismatch at seq {seq}"
        recomputed = compute_chain_hash(build_fields(row))
        if recomputed != row["row_hash"]:
            return False, seq, f"row_hash mismatch at seq {seq} (tampered)"
        prev = str(row["row_hash"])
        expected_seq += 1
    return True, None, "chain intact"
