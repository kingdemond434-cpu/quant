"""Signed release artifacts: a box runs code some authority SEALED, not code that appeared.

BLUEPRINT ITEM 1, the part that is mechanically enforceable. "Live boxes should accept only
signed release artifacts; no healer, sync process or agent should be able to overwrite
money-path files directly."

WHAT THIS IS FOR, measured rather than imagined. On 2026-09-11 the money path on the trading
box was overwritten repeatedly by `sftp-server.exe` arriving over an authorised key -- Windows
file auditing caught it writing `desks/mt5/mt5desk/families.py` four seconds before a checksum
watch saw the revert. The SSH gate now refuses that, but a gate is a perimeter and perimeters
are the wrong place to put the last line of defence. The same day a *correct* fix was reverted
by `Adopt-Release` because origin did not yet carry it, and a `RELEASE.json` copied between two
boxes pointed one of them at a commit that did not exist in its own clone and stopped it taking
new risk. Three different writers, one property missing: nothing checked that the release the
box was about to trade had been sealed BY THIS DESK over THESE bytes.

WHAT IT SIGNS, and why those three. The signature covers `code_sha`, `money_path_hash` and
`immutable_hash` and nothing else:

  * `code_sha` pins WHICH commit,
  * `money_path_hash` pins the CONTENT of the files that decide orders, so a commit whose money
    path was edited on disk after sealing no longer verifies,
  * `immutable_hash` pins the sealed doctrine core.

Timestamps, `dirty` counts and the sealer's name are deliberately OUTSIDE the signature: they
are provenance, they change for honest reasons, and including them would make every re-read a
re-sign, which is how signatures become noise that people learn to skip.

HMAC AND NOT A PUBLIC-KEY SIGNATURE, on purpose. The threat here is an unattended process
writing a file, not a forger with the desk's secret. An HMAC over a key that lives only in
`data/secrets/` -- which never leaves the box and is never printed -- refuses every writer that
does not hold it, which is all of them. Upgrading to asymmetric signing later changes this
module and nothing that calls it.

FAILS CLOSED, AND SAYS WHICH. An absent key, an absent signature and a WRONG signature are three
different facts and each returns its own reason; none of them returns True.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

#: The signing key. Lives beside the other secrets, is never printed, and never leaves the box.
KEY_REL = "data/secrets/release_signing.key"

#: The fields the signature covers. Order is fixed because the digest is order-dependent.
SIGNED_FIELDS = ("code_sha", "money_path_hash", "immutable_hash")

SIG_FIELD = "signature"
SIG_ALGO_FIELD = "signature_algo"
ALGO = "hmac-sha256-v1"


def _root(root: Path | None = None) -> Path:
    return root or Path(__file__).resolve().parents[2]


def key_path(root: Path | None = None) -> Path:
    return _root(root) / KEY_REL


def load_key(root: Path | None = None) -> bytes | None:
    """The signing key, or None when this box has not been given one.

    NO SILENT GENERATION. A module that mints a key when it cannot find one signs everything it
    sees and proves nothing -- every box would trust its own invention. Creating the key is a
    deliberate act (`ensure_key`), taken once, by someone who meant to.
    """
    env = os.environ.get("QUANT_RELEASE_SIGNING_KEY")
    if env:
        return env.encode("utf-8")
    p = key_path(root)
    try:
        raw = p.read_bytes().strip()
    except OSError:
        return None
    return raw or None


def ensure_key(root: Path | None = None) -> tuple[bool, str]:
    """Create the signing key if absent. Returns (created, message). Never overwrites."""
    p = key_path(root)
    if p.exists() and p.read_bytes().strip():
        return False, f"key already present at {p.name}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(os.urandom(48).hex().encode("ascii"))
    return True, f"created {p.name} (48 random bytes, hex); it never leaves this box"


def payload(record: dict[str, Any]) -> bytes:
    """The exact bytes the signature covers: the signed fields, in order, canonically encoded."""
    items = [(f, "" if record.get(f) is None else str(record.get(f))) for f in SIGNED_FIELDS]
    return json.dumps(items, separators=(",", ":"), sort_keys=False).encode("utf-8")


def sign(record: dict[str, Any], root: Path | None = None) -> tuple[str | None, str]:
    """Return (signature, reason). None when this box holds no key."""
    key = load_key(root)
    if key is None:
        return None, f"no signing key at {KEY_REL} and QUANT_RELEASE_SIGNING_KEY unset"
    mac = hmac.new(key, payload(record), hashlib.sha256).hexdigest()
    return mac, "signed"


def verify(record: dict[str, Any], root: Path | None = None) -> tuple[bool, str]:
    """Is this release record signed by THIS desk over THESE bytes? (ok, reason).

    Returns False with a distinct reason for: no key, no signature, wrong algorithm, bad
    signature. "I cannot check" and "it is forged" are different facts and a caller that
    conflates them is the reason this returns a reason at all.
    """
    got = str(record.get(SIG_FIELD) or "")
    if not got:
        return False, "release record carries no signature"
    algo = str(record.get(SIG_ALGO_FIELD) or "")
    if algo != ALGO:
        return False, f"unknown signature algorithm {algo!r} (this desk writes {ALGO})"
    key = load_key(root)
    if key is None:
        return False, f"no signing key at {KEY_REL}; cannot verify (this is not a pass)"
    want = hmac.new(key, payload(record), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, got):
        return False, ("signature does not match this release's code_sha / money_path_hash / "
                       "immutable_hash -- the record was edited or signed elsewhere")
    return True, "signature valid"


def stamp(record: dict[str, Any], root: Path | None = None) -> tuple[dict[str, Any], str]:
    """Return a copy of `record` carrying a valid signature, plus the reason."""
    out = dict(record)
    out.pop(SIG_FIELD, None)
    out.pop(SIG_ALGO_FIELD, None)
    mac, why = sign(out, root)
    if mac is None:
        return out, why
    out[SIG_ALGO_FIELD] = ALGO
    out[SIG_FIELD] = mac
    return out, why
