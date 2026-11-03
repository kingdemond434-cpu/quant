"""SIGNED RELEASE ATTESTATIONS -- the one proof the box gate accepts in place of a pasted row.

WHY (zuck 2026-11-03 19:11Z, "Eliminate manual protected-PR registry approvals"). The registry
path (#591) reads `{"pr","sha","verdict","at"}` rows from C:\\opt\\audit_registry\\registry.jsonl.
An unsigned row is only as good as whoever can write the file, so a Claude session writing one
was rightly refused, and zuck pasted them by hand. This module replaces "who wrote the line" with
"who holds the key": the release AUTHORITY (ops/release/authority/authority.py) signs a
statement with an Ed25519 key that only its own Windows account can read, and the gate verifies
it against a public key pinned OUTSIDE the repo (QUANT_AUTHORITY_PUBKEY, a box file zuck writes
once). No PR, no Claude session and no Codex run holds the private key, so none can issue one.

THE STATEMENT binds everything a CLEAR depends on, so a CLEAR for one thing is never a CLEAR for
another: the repo, PR, exact head sha, the base sha it was judged against, the byte patch-id of
the change, the tier, the ROOT POLICY DIGEST (ops/release/authority/ROOT_POLICY.json + the gate's
root symbols; a policy change invalidates every older attestation), the evidence (each required
check's run id and conclusion), the reasons, the authority's key id, issue time and expiry.

Canonical JSON (sorted keys, no spaces, UTF-8) is what is signed; the envelope carries it as a
string so no re-serialisation can change the signed bytes. Any parse error, unknown type, wrong
key id, bad signature, expiry or missing field is a REJECT with a reason: fail closed.

Needs the `cryptography` package; without it nothing verifies, so nothing merges by this path.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

TYPE = "quant.release.attestation/v1"
VERDICTS = ("CLEAR", "HOLD")
#: Every statement field the gate relies on; a statement missing any is rejected.
REQUIRED = (
    "type", "repo", "pr", "head_sha", "base_sha", "patch_id", "tier", "verdict",
    "policy_digest", "evidence", "reasons", "key_id", "issued_at", "expires_at",
)  # fmt: skip
#: An attestation is good for at most this long; the authority re-issues while a PR is open.
MAX_TTL = timedelta(hours=72)
#: Allowance for the authority's clock running ahead of the gate's.
SKEW = timedelta(minutes=5)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _crypto() -> Any:
    from cryptography.hazmat.primitives.asymmetric import ed25519

    return ed25519


def key_id(public_raw: bytes) -> str:
    """The key's identity: sha256 of its 32 raw public bytes, hex, first 16."""
    return hashlib.sha256(public_raw).hexdigest()[:16]


def load_public(path: str | Path) -> tuple[Any, str]:
    """(Ed25519PublicKey, key id) from a file holding the raw key as base64 (one line) or PEM."""
    from cryptography.hazmat.primitives import serialization

    data = Path(path).read_bytes().strip()
    if data.startswith(b"-----BEGIN"):
        pub = serialization.load_pem_public_key(data)
        if not isinstance(pub, _crypto().Ed25519PublicKey):
            raise ValueError("not an Ed25519 public key")
    else:
        pub = _crypto().Ed25519PublicKey.from_public_bytes(base64.b64decode(data, validate=True))
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pub, key_id(raw)


def load_private(path: str | Path) -> tuple[Any, str]:
    """(Ed25519PrivateKey, key id) from an unencrypted PKCS8 PEM (the authority's own file)."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, _crypto().Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, key_id(raw)


def sign(statement: Mapping[str, Any], private: Any, kid: str) -> dict[str, str]:
    """The envelope for `statement` (which must already carry `key_id` == kid)."""
    if statement.get("key_id") != kid:
        raise ValueError("the statement's key_id is not the signing key's")
    body = canonical(dict(statement)).decode()
    sig = private.sign(body.encode())
    return {"statement": body, "sig": base64.b64encode(sig).decode(), "key_id": kid}


def verify(
    env: Any,
    public: Any,
    kid: str,
    now: datetime,
    *,
    policy_digest: str,
    repo: str,
) -> tuple[dict[str, Any] | None, str]:
    """(the verified statement, or None; why). Checks, in order: shape, key id, signature, type,
    every required field, repo, verdict, policy digest, issue/expiry window."""
    if not isinstance(env, Mapping) or not all(
        isinstance(env.get(k), str) for k in ("statement", "sig", "key_id")
    ):
        return None, "not an attestation envelope"
    if env["key_id"] != kid:
        return None, f"signed by key {env['key_id'][:16]}, not the pinned authority key"
    try:
        sig = base64.b64decode(env["sig"], validate=True)
        public.verify(sig, env["statement"].encode())
    except Exception:  # InvalidSignature, binascii.Error, ...: all a reject
        return None, "the signature does not verify"
    try:
        st = json.loads(env["statement"])
    except ValueError:
        return None, "the signed statement is not JSON"
    if not isinstance(st, dict) or st.get("type") != TYPE:
        return None, "not a v1 release attestation"
    missing = [k for k in REQUIRED if k not in st]
    if missing:
        return None, f"the statement lacks {', '.join(missing)}"
    if st["key_id"] != kid:
        return None, "the statement names another key"
    if st["repo"] != repo:
        return None, f"the attestation is for {st['repo']}, not {repo}"
    if st["verdict"] not in VERDICTS:
        return None, f"unknown verdict {st['verdict']!r}"
    if st["policy_digest"] != policy_digest:
        return None, "issued under another root policy (the policy changed): stale"
    try:
        issued = datetime.fromisoformat(str(st["issued_at"]))
        expires = datetime.fromisoformat(str(st["expires_at"]))
    except ValueError:
        return None, "unreadable issue or expiry time"
    if issued.tzinfo is None or expires.tzinfo is None:
        return None, "a time without a zone"
    if issued - now > SKEW:
        return None, "issued in the future"
    if expires <= now:
        return None, "expired"
    if expires - issued > MAX_TTL:
        return None, "valid for longer than the authority may grant"
    if not isinstance(st["pr"], int) or not isinstance(st["head_sha"], str):
        return None, "bad pr or head"
    return st, "verified"


def statement(
    *,
    repo: str,
    pr: int,
    head_sha: str,
    base_sha: str,
    patch_id: str | None,
    tier: str,
    verdict: str,
    policy_digest: str,
    evidence: Mapping[str, Any],
    reasons: list[str],
    kid: str,
    now: datetime | None = None,
    ttl: timedelta = timedelta(hours=48),
    authority_version: str = "",
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    return {
        "type": TYPE,
        "repo": repo,
        "pr": pr,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "patch_id": patch_id or "",
        "tier": tier,
        "verdict": verdict,
        "policy_digest": policy_digest,
        "evidence": dict(evidence),
        "reasons": list(reasons),
        "key_id": kid,
        "authority_version": authority_version,
        "issued_at": now.isoformat(),
        "expires_at": (now + min(ttl, MAX_TTL)).isoformat(),
    }
