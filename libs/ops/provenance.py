"""The account key: a keyed, box-held HMAC of an MT5 account, never the login.

ONE PUBLIC FUNCTION, STABLE NAME AND SIGNATURE (2026-10-20, publish_sync_schtasks audit v5):

    account_key(login: object, server: object, *, create: bool = False) -> str | None

returns "sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16 lowercase hex] -- the shape
Fusion r5's book check validates -- or None, THE FAIL-CLOSED SENTINEL, when the login is
unreadable or no box key is held. It NEVER falls back to a bare sha256: the v4 key was an
unsalted truncated sha256 of "<login>@<server>" with the server published in clear on the same
row, and one core inverts an 8-digit login from that in about a minute. Every consumer (the
desk's mt5desk.provenance, the gateway's intent stamp, the cross-account OCO lock) calls THIS,
and it normalises internally (v5c, `norm_login` + a stripped server), so no caller has to.

THE KEY. `data/secrets/account_key.hmac` under the repository (gitignored with all of
data/secrets/, never printed, never logged, never leaves the box), or the file named by
`QUANT_ACCOUNT_KEY_FILE`. At least 32 bytes after stripping; a shorter file is unusable and is
NEVER overwritten (that would orphan every row hashed under it). Only an ABSENT file is created,
only when `create=True` -- which is for WRITERS on the box: the key is written to a temp file in
the same directory, fsynced, and hard-linked into place (create-if-absent, so two processes cannot
race two keys and a crash cannot leave a torn one; v5b); with no hard links, an exclusive create
of the key path itself (v5c) -- never a replace, so an existing key is never overwritten. A
0-byte or short file reads as NO key. A reader never creates one: with none, it gets None.

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
import operator
import os
import re
import secrets
from pathlib import Path

__all__ = ["ALERT_KEY", "ALERT_USERNAME", "KEY_ENV", "KEY_REL", "RESTORE_STEP", "account_key",
           "is_key", "key_path", "key_state", "norm_login"]

KEY_ENV = "QUANT_ACCOUNT_KEY_FILE"
KEY_REL = "data/secrets/account_key.hmac"
_REPO = Path(__file__).resolve().parents[2]
_KEY_SHAPE = re.compile(r"sha256:[0-9a-f]{16}")
_MIN_KEY_BYTES = 32
#: path -> ((inode, size, mtime_ns), key). Keyed on all three (v5c) so a key REPLACED in place --
#: same mtime granularity, new inode or size -- is re-read rather than served from the cache.
_KEY_CACHE: dict[str, tuple[tuple[int, int, int], bytes]] = {}


#: THE ALERTS (v5d). A short or unreadable key, or a login that is a username, makes
#: `account_key` fail closed -- and fail-closed must never be silent. Each opens ONE alert per
#: incident in the desk's AlertLedger (`data/alert_ledger.json`, the path the placement interlock
#: uses), marked NEEDS_HUMAN because no command can repair it; a valid read closes the key alert
#: (FIXED), so the next incident opens again (REGRESSED). Never the key's bytes, never the login:
#: only the state, the size and the restore step.
ALERT_KEY = "account_key_unusable"
ALERT_USERNAME = "account_key_non_numeric_login"
RESTORE_STEP = ("restore data/secrets/account_key.hmac from the laptop backup and NEVER "
                "regenerate it (a new key orphans every row hashed under the old one)")
#: (ledger, alert id, detail) already recorded by THIS process: once per incident, not per row.
_ALERTED: set[tuple[str, str, str]] = set()


def _alert_ledger_path() -> Path:
    """The ledger beside the key's secrets directory: <repo>/data/alert_ledger.json for the box
    key, and inside the temp tree for a test's key -- so a test never touches the repo's copy."""
    return key_path().parent.parent / "alert_ledger.json"


def _alert(aid: str, detail: str, message: str) -> None:
    """Open `aid` once per incident. NEVER RAISES: an alert that fails must not turn a fail-closed
    None into an exception on the money path."""
    ledger_path = _alert_ledger_path()
    memo = (str(ledger_path), aid, detail)
    if memo in _ALERTED:
        return
    try:
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(ledger_path)
        known = ledger.alerts.get(aid)
        if known is None or not known.open or known.message != message:
            ledger.observe(aid, message[:600], scope="RUNTIME")
            ledger.needs_human(aid, RESTORE_STEP if aid == ALERT_KEY else
                               "fix the caller to pass the numeric MT5 login, never a username")
            ledger.save()
        _ALERTED.add(memo)
    except Exception:
        return


def _alert_clear() -> None:
    """A usable key read after an incident closes the key alert (verified by this very read)."""
    ledger_path = _alert_ledger_path()
    if not any(m[0] == str(ledger_path) and m[1] == ALERT_KEY for m in _ALERTED):
        return
    try:
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(ledger_path)
        known = ledger.alerts.get(ALERT_KEY)
        if known is not None and known.open:
            ledger.verify(ALERT_KEY, still_firing=False)
            ledger.save()
    except Exception:
        return
    finally:
        _ALERTED.difference_update({m for m in _ALERTED
                                    if m[0] == str(ledger_path) and m[1] == ALERT_KEY})


def key_state() -> dict[str, object]:
    """The key file's STATE for health organs: present / short / unreadable / absent, and its size
    in bytes. NEVER its contents. `path` is the repo-relative default or the env override's name."""
    path = key_path()
    where = KEY_REL if not os.environ.get(KEY_ENV) else f"${KEY_ENV}"
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return {"path": where, "state": "absent", "size_bytes": None,
                "min_bytes": _MIN_KEY_BYTES}
    except OSError as exc:
        return {"path": where, "state": "unreadable", "size_bytes": None,
                "min_bytes": _MIN_KEY_BYTES, "why": type(exc).__name__}
    try:
        n = len(path.read_bytes().strip())
    except OSError as exc:
        return {"path": where, "state": "unreadable", "size_bytes": size,
                "min_bytes": _MIN_KEY_BYTES, "why": type(exc).__name__}
    return {"path": where, "state": "present" if n >= _MIN_KEY_BYTES else "short",
            "size_bytes": size, "min_bytes": _MIN_KEY_BYTES}


def key_path() -> Path:
    """Where the box key lives (the env override, else data/secrets/ under the repo)."""
    return Path(os.environ.get(KEY_ENV) or (_REPO / KEY_REL))


def _read_key(path: Path) -> bytes | None:
    """The key file's bytes if it is a usable key, else None. A 0-byte, short or torn file is
    NO KEY (never a weaker one): every caller then fails closed."""
    st = path.stat()
    ident = (st.st_ino, st.st_size, st.st_mtime_ns)
    hit = _KEY_CACHE.get(str(path))
    if hit is not None and hit[0] == ident and st.st_size >= _MIN_KEY_BYTES:
        return hit[1]
    raw = path.read_bytes().strip()
    if len(raw) < _MIN_KEY_BYTES:
        _KEY_CACHE.pop(str(path), None)
        return None
    _KEY_CACHE[str(path)] = (ident, raw)
    return raw


def _create_key(path: Path) -> None:
    """Write a fresh key to a temp file beside `path`, fsync it, then hard-link it into place.

    os.link is create-if-absent on POSIX and Windows alike (FileExistsError if a key is there),
    so a crash can never leave a torn key at `path` and an existing key -- even a short one, or a
    read-only one, where os.replace raises WinError 5 -- is never overwritten.

    NO HARD LINKS (v5c): the fallback is an EXCLUSIVE CREATE of `path` itself (O_CREAT|O_EXCL),
    the key written into it directly, flushed and fsynced. There is no replace at all, so no
    race can overwrite a key that already exists: a second writer gets FileExistsError and
    re-reads. The cost is that a crash mid-write can leave a short file there; it reads as NO
    key (fail closed) and is never overwritten, so a human restores the key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = secrets.token_hex(32).encode()
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # another writer won the race; the caller re-reads theirs
        except OSError:
            _create_in_place(path, body)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _create_in_place(path: Path, body: bytes) -> None:
    """The no-hard-link fallback: create `path` exclusively and write `body` into it. An existing
    key -- any key, any size, read-only or not -- is left exactly as it is."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "wb") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())


def _box_key(create: bool = False) -> bytes | None:
    """The HMAC key's bytes, or None (no usable key: callers fail closed). Never printed. A short
    or unreadable key (or one that cannot be created) also opens ALERT_KEY, once per incident."""
    path = key_path()
    for _ in range(2):
        try:
            got = _read_key(path)
        except FileNotFoundError:
            if not create:
                return None
            try:
                _create_key(path)
            except OSError as exc:
                _alert(ALERT_KEY, f"uncreatable:{type(exc).__name__}",
                       f"account key could not be created ({type(exc).__name__}); every stamp "
                       f"fails closed (account_key None). {RESTORE_STEP}")
                return None
            continue
        except OSError as exc:
            _alert(ALERT_KEY, f"unreadable:{type(exc).__name__}",
                   f"account key unreadable ({type(exc).__name__}); every stamp fails closed "
                   f"(account_key None). {RESTORE_STEP}")
            return None
        if got is None:
            size = None
            with contextlib.suppress(OSError):
                size = path.stat().st_size
            _alert(ALERT_KEY, f"short:{size}",
                   f"account key short ({size} bytes, need {_MIN_KEY_BYTES}); every stamp fails "
                   f"closed (account_key None). {RESTORE_STEP}")
            return None
        _alert_clear()
        return got
    return None


_DIGITS = re.compile(r"[0-9]+")


def norm_login(login: object) -> int | None:
    """The ONE canonical form of an MT5 login: a positive int, or None (fail closed, never a
    guess). v5c: `7000001`, `7000001.0`, `"7000001"` and `" 7000001 "` are all 7000001. A bool,
    a non-integral or non-finite float, a string that is not ASCII digits after stripping,
    zero, a negative, or any other type is None -- the gateway's `login or 0` for an unreadable
    account must not key as account 0."""
    if login is None or isinstance(login, bool):
        return None
    if isinstance(login, float):     # np.float64 is a float
        if not login.is_integer():   # NaN and inf are not integral
            return None
        value = int(login)
    elif isinstance(login, str):
        text = login.strip()
        if not _DIGITS.fullmatch(text):
            return None
        value = int(text)
    elif isinstance(login, (bytes, bytearray, memoryview)):
        return None
    else:
        # int and every integer-like type -- np.int64, np.uint32, ... -- by `__index__`, so numpy
        # is never imported here (v5d). np.bool_ and Decimal have no `__index__`: None.
        try:
            value = operator.index(login)  # type: ignore[arg-type]
        except TypeError:
            return None
    return value if value > 0 else None


def is_key(value: object) -> bool:
    """Is `value` an account key's shape ("sha256:" + 16 lowercase hex)?"""
    return isinstance(value, str) and _KEY_SHAPE.fullmatch(value) is not None


def account_key(login: object, server: object, *, create: bool = False) -> str | None:
    """"sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16], or None (fail closed) when the
    login is unreadable or no box key is held. `create=True` is for writers on the box only.

    NORMALISES INTERNALLY (v5c): the login goes through `norm_login` (int, integral float and
    digit string -- whitespace allowed -- are one account; anything else is None) and the server
    is `.strip()`ped (None stays distinct from ""). An int login with a clean server hashes
    exactly as before, so every key already stamped from the terminal's int login still holds."""
    canon = norm_login(login)
    if canon is None:
        if isinstance(login, str) and login.strip() and not _DIGITS.fullmatch(login.strip()):
            # A USERNAME (v5d): keyed None, and never silently. The name itself is never written.
            _alert(ALERT_USERNAME, "username",
                   "account_key was handed a non-numeric login string (a username?); it keyed "
                   "None and the row carries no account. Pass the numeric MT5 login.")
        return None
    key = _box_key(create=create)
    if key is None:
        return None
    srv = "\x00none" if server is None else str(server).strip()
    mac = hmac.new(key, f"{canon}@{srv}".encode(), hashlib.sha256).hexdigest()
    return "sha256:" + mac[:16]
