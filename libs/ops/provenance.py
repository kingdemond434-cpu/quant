"""The account key: a keyed, box-held HMAC of an MT5 account, never the login.

ONE PUBLIC FUNCTION, STABLE NAME AND SIGNATURE (2026-10-20, publish_sync_schtasks audit v5):

    account_key(login: object, server: object, *, create: bool = False) -> str | None

returns "sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16 lowercase hex] -- the shape
Fusion r5's book check validates -- or None, THE FAIL-CLOSED SENTINEL, when the login is
unreadable or no box key is held. It NEVER falls back to a bare sha256: the v4 key was an
unsalted truncated sha256 of "<login>@<server>" with the server published in clear on the same
row, and one core inverts an 8-digit login from that in about a minute. Every consumer (the
desk's mt5desk.provenance, the gateway's intent stamp, the cross-account OCO lock) calls THIS.

THE KEY. `data/secrets/account_key.hmac` under the repository (gitignored with all of
data/secrets/, never printed, never logged, never leaves the box), or the file named by
`QUANT_ACCOUNT_KEY_FILE`. At least 32 bytes after stripping; a shorter file is unusable and is
NEVER overwritten (that would orphan every row hashed under it). Only an ABSENT file is created,
only when `create=True` -- which is for WRITERS on the box: the key is written to a temp file in
the same directory, fsynced, and hard-linked into place (create-if-absent, so two processes cannot
race two keys and a crash cannot leave a torn one; v5b). A 0-byte or short file reads as NO key.
A reader never creates one: with none, it gets None.

LOSING THE KEY ORPHANS EVERY HASHED ROW (they read as no provenance, never as another account).
Back it up with the box's other secrets. Off the box, with no key, a hashed row can be grouped by
its key string but never recomputed from a login.

THE VALUE CHANGED, THE FORMAT DID NOT. Keys written by r4/r5-era code (bare sha256) and keys
from this function share a shape but never a value; anything that recomputes a key must call
this function with the box key.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path

__all__ = ["KEY_ENV", "KEY_REL", "account_key", "is_key", "key_path"]

KEY_ENV = "QUANT_ACCOUNT_KEY_FILE"
KEY_REL = "data/secrets/account_key.hmac"
_REPO = Path(__file__).resolve().parents[2]
_KEY_SHAPE = re.compile(r"sha256:[0-9a-f]{16}")
_MIN_KEY_BYTES = 32
_KEY_CACHE: dict[str, tuple[int, bytes]] = {}


def key_path() -> Path:
    """Where the box key lives (the env override, else data/secrets/ under the repo)."""
    return Path(os.environ.get(KEY_ENV) or (_REPO / KEY_REL))


def _read_key(path: Path) -> bytes | None:
    """The key file's bytes if it is a usable key, else None. A 0-byte, short or torn file is
    NO KEY (never a weaker one): every caller then fails closed."""
    st = path.stat()
    hit = _KEY_CACHE.get(str(path))
    if hit is not None and hit[0] == st.st_mtime_ns and st.st_size >= _MIN_KEY_BYTES:
        return hit[1]
    raw = path.read_bytes().strip()
    if len(raw) < _MIN_KEY_BYTES:
        _KEY_CACHE.pop(str(path), None)
        return None
    _KEY_CACHE[str(path)] = (st.st_mtime_ns, raw)
    return raw


def _create_key(path: Path) -> None:
    """Write a fresh key to a temp file beside `path`, fsync it, then hard-link it into place.

    os.link is create-if-absent on POSIX and Windows alike (FileExistsError if a key is there),
    so a crash can never leave a torn key at `path` and an existing key -- even a short one, or a
    read-only one, where os.replace raises WinError 5 -- is never overwritten. On a filesystem
    with no hard links the fallback is os.replace, taken ONLY while `path` is still absent; the
    race window that leaves is closed by the re-read, which keeps whichever key landed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(secrets.token_hex(32).encode())
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # another writer won the race; the caller re-reads theirs
        except OSError:
            # No hard links on this filesystem. Replace only onto an ABSENT key, never over one.
            if not path.exists():
                os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _box_key(create: bool = False) -> bytes | None:
    """The HMAC key's bytes, or None (no usable key: callers fail closed). Never printed."""
    path = key_path()
    for _ in range(2):
        try:
            return _read_key(path)
        except FileNotFoundError:
            if not create:
                return None
            try:
                _create_key(path)
            except OSError:
                return None
        except OSError:
            return None
    return None


def _canon_login(login: object) -> str | None:
    """The login as hash input. An integral float reads as its int (N.0 == N, as the raw
    comparison always had it); a string is tagged so "123" stays distinct from 123."""
    if login is None or isinstance(login, bool):
        return None
    if isinstance(login, float):
        if not login.is_integer():
            return f"f:{login!r}"
        login = int(login)
    if isinstance(login, int):
        return str(login)
    text = str(login)
    return ("s:" + text) if text else None


def is_key(value: object) -> bool:
    """Is `value` an account key's shape ("sha256:" + 16 lowercase hex)?"""
    return isinstance(value, str) and _KEY_SHAPE.fullmatch(value) is not None


def account_key(login: object, server: object, *, create: bool = False) -> str | None:
    """"sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16], or None (fail closed) when the
    login is unreadable or no box key is held. `create=True` is for writers on the box only."""
    canon = _canon_login(login)
    if canon is None:
        return None
    key = _box_key(create=create)
    if key is None:
        return None
    srv = "\x00none" if server is None else str(server)
    mac = hmac.new(key, f"{canon}@{srv}".encode(), hashlib.sha256).hexdigest()
    return "sha256:" + mac[:16]
