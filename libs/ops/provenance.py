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
NEVER overwritten (that would orphan every row hashed under it). A 0-byte or short file reads as
NO key.

A LOST KEY IS NEVER SILENTLY REGENERATED (v5e, coordinator ruling). `create=True` no longer
creates anything: a writer that finds no key gets None, fails closed and PAGES. The ONE way to
make a key is `create_account_key_first_time(operator_present=True)` (CLI: `python -m
libs.ops.provenance --create-first-time --at-the-laptop`), which refuses when any ledger already
holds a hashed row, when desks/mt5/data/E8_ACCOUNT.json exists, or without the explicit flag.
It writes a temp file beside the key, fsyncs it and hard-links it into place (create-if-absent;
with no hard links, an exclusive create) -- never a replace, so an existing key is never touched.

FAIL-CLOSED IS NEVER SILENT (v5d/v5e). A short, unreadable or (for a writer) absent key opens one
NEEDS_HUMAN alert per incident in the desk's AlertLedger AND pages through
`alert_channels.send_all` (login_fence's idiom: deduplicated, repaged every 6h while it stands,
one page on recovery, and a send that `delivered` 0 is not a page). A valid read closes it, from
any process. The restore step is RESTORE_STEP; process_health reports the key's and the backup's
state (never contents, never a hash).

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
import json
import operator
import os
import re
import secrets
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["ALERT_KEY", "ALERT_USERNAME", "BACKUP_DEFAULT", "BACKUP_ENV", "KEY_ENV", "KEY_REL",
           "RESTORE_STEP", "account_key", "create_account_key_first_time", "is_key",
           "key_backup_state", "key_path", "key_state", "norm_login"]

KEY_ENV = "QUANT_ACCOUNT_KEY_FILE"
KEY_REL = "data/secrets/account_key.hmac"
_REPO = Path(__file__).resolve().parents[2]
_KEY_SHAPE = re.compile(r"sha256:[0-9a-f]{16}")
_MIN_KEY_BYTES = 32
#: path -> ((inode, size, mtime_ns), key). Keyed on all three (v5c) so a key REPLACED in place --
#: same mtime granularity, new inode or size -- is re-read rather than served from the cache.
_KEY_CACHE: dict[str, tuple[tuple[int, int, int], bytes]] = {}


#: THE ALERTS (v5d, paging v5e). A short, unreadable or (for a writer) absent key, or a login
#: that is a username, makes `account_key` fail closed -- and fail-closed must never be silent.
#: Each opens ONE alert per incident in the desk's AlertLedger, marked NEEDS_HUMAN, and PAGES
#: (`_page`). A valid key read closes the key alert (FIXED) and pages the recovery once. Never the
#: key's bytes, never a hash of it, never the login: only the state, the size and the restore step.
ALERT_KEY = "account_key_unusable"
ALERT_USERNAME = "account_key_non_numeric_login"
RESTORE_STEP = ("restore data/secrets/account_key.hmac from the box-local backup in "
                "C:\\ProgramData\\quant-keys\\ (ACL'd to the box user) or from zuck's own copy; "
                "NEVER regenerate it -- if the key is lost, every account_key changes and "
                "E8_ACCOUNT.json must be re-declared")
REPAGE_H = 6.0
#: An undelivered page is retried at most this often by one process (the money path calls
#: account_key per row; a dead channel must not cost a network attempt per row).
RETRY_UNDELIVERED_S = 300.0
Sender = Callable[[str, str], dict[str, Any]]
#: (ledger, alert id, detail) whose LEDGER entry this process already wrote.
_ALERTED: set[tuple[str, str, str]] = set()
#: (page state, alert id, sig) this process already saw DELIVERED; and last undelivered attempt.
_PAGED: set[tuple[str, str, str]] = set()
_LAST_TRY: dict[tuple[str, str, str], float] = {}


def _data_dir() -> Path:
    """Where the alert state lives. The box key's own `data/` (data/secrets/.. -> data/), or, when
    QUANT_ACCOUNT_KEY_FILE overrides the key, the directory HOLDING that key (v5e: it used to be
    the key's grandparent, so an override in /dev/shm wrote /dev/alert_ledger.json)."""
    return key_path().parent if os.environ.get(KEY_ENV) else _REPO / "data"


def _alert_ledger_path() -> Path:
    return _data_dir() / "alert_ledger.json"


def _page_state_path() -> Path:
    """Page dedup state: gitignored desks/mt5/logs/ on the box (beside login_fence's)."""
    if os.environ.get(KEY_ENV):
        return _data_dir() / "account_key_page.json"
    return _REPO / "desks" / "mt5" / "logs" / "account_key_page.json"


def _default_sender() -> Sender:
    """alert_channels.send_all against the channels config beside the alert state: the box's
    data/secrets/alert_channels.json; under a key override, one in the override's directory (so
    a test's temp key can never reach the real channels)."""
    base = _data_dir()

    def send(title: str, body: str) -> dict[str, Any]:
        from libs.ops import alert_channels
        return alert_channels.send_all(title, body,
                                       config=base / "secrets" / "alert_channels.json",
                                       ledger=base / "alert_delivery.jsonl")
    return send


#: Tests (and only tests) replace this; None means `_default_sender()`.
SENDER: Sender | None = None


def _page(aid: str, status: str, sig: str, title: str, body: str) -> dict[str, Any]:
    """Page `aid` (login_fence.page's idiom). status "OPEN" pages on a new `sig`, again every
    REPAGE_H while it stands; "OK" pages once on recovery. A send whose `delivered` is 0, absent
    or falsy is NOT a page: nothing is recorded and a later call re-sends. NEVER RAISES."""
    try:
        path = _page_state_path()
        memo = (str(path), aid, f"{status}|{sig}")
        if memo in _PAGED:
            return {"sent": False, "reason": "deduplicated (this process)"}
        last_try = _LAST_TRY.get(memo)
        if last_try is not None and time.monotonic() - last_try < RETRY_UNDELIVERED_S:
            return {"sent": False, "reason": "undelivered, retry throttled"}
        try:
            doc = json.loads(path.read_text("utf-8"))
            doc = doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            doc = {}
        got = doc.get(aid)
        prev: dict[str, Any] = got if isinstance(got, dict) else {}
        now = datetime.now(UTC)
        last = None
        with contextlib.suppress(TypeError, ValueError):
            last = datetime.fromisoformat(str(prev.get("paged_at")))
        if status == "OPEN":
            if prev.get("status") == "OPEN" and prev.get("sig") == sig and last is not None \
                    and (now - last).total_seconds() / 3600 < REPAGE_H:
                _PAGED.add(memo)
                return {"sent": False, "reason": "deduplicated"}
        elif prev.get("status") != "OPEN":
            _PAGED.add(memo)
            return {"sent": False, "reason": "OK: nothing to page"}
        res = (SENDER or _default_sender())(title, body[:1500])
        res = res if isinstance(res, dict) else {}
        if not res.get("delivered"):
            _LAST_TRY[memo] = time.monotonic()
            return {"sent": False, "reason": "undelivered, re-sent later",
                    "armed": res.get("armed"), "delivered": res.get("delivered")}
        doc[aid] = {"status": status, "sig": sig, "paged_at": now.isoformat(timespec="seconds")}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        os.replace(tmp, path)
        _PAGED.add(memo)
        _LAST_TRY.pop(memo, None)
        return {"sent": True, "armed": res.get("armed"), "delivered": res.get("delivered")}
    except Exception as exc:
        return {"sent": False, "reason": f"page failed ({type(exc).__name__})"}


def _alert(aid: str, detail: str, message: str) -> None:
    """Open `aid` once per incident in the AlertLedger, and page it. NEVER RAISES: an alert that
    fails must not turn a fail-closed None into an exception on the money path."""
    ledger_path = _alert_ledger_path()
    memo = (str(ledger_path), aid, detail)
    if memo not in _ALERTED:
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
            pass
    title = ("ACCOUNT KEY UNUSABLE: ledger stamps fail closed" if aid == ALERT_KEY
             else "ACCOUNT KEY: a non-numeric login was keyed None")
    _page(aid, "OPEN", detail, title, message)


def _alert_clear() -> None:
    """A usable key, read after any incident -- by this process or another -- closes the key
    alert (verified by this very read) and pages the recovery once. Called on a key-cache miss
    only, so a process pays one ledger read per key it loads, not one per row."""
    try:
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(_alert_ledger_path())
        known = ledger.alerts.get(ALERT_KEY)
        if known is not None and known.open:
            ledger.verify(ALERT_KEY, still_firing=False)
            ledger.save()
    except Exception:
        pass
    _ALERTED.difference_update({m for m in _ALERTED if m[1] == ALERT_KEY})
    _PAGED.difference_update({m for m in _PAGED if m[1] == ALERT_KEY})
    _page(ALERT_KEY, "OK", "recovered", "ACCOUNT KEY OK again",
          "the account key reads as a usable key again; ledger stamps carry account_key")


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


#: The box-local key backup (v5e): ACL'd to the box user, outside the repository. The env var
#: overrides it (tests; never needed on the box).
BACKUP_DEFAULT = r"C:\ProgramData\quant-keys\account_key.hmac"
BACKUP_ENV = "QUANT_ACCOUNT_KEY_BACKUP"


def key_backup_state() -> dict[str, object]:
    """The backup's state: present, size, and whether it MATCHES the live key. The match is a
    constant-time compare of two in-process digests that are never returned, printed or stored.
    `not_applicable` when there is no usable live key to compare, or off the trading box (no
    override and not Windows)."""
    override = os.environ.get(BACKUP_ENV)
    where = f"${BACKUP_ENV}" if override else BACKUP_DEFAULT
    if not override and os.name != "nt":
        return {"path": where, "state": "not_applicable", "why": "not the trading box"}
    try:
        live = _read_key(key_path())
    except OSError:
        live = None
    if live is None:
        return {"path": where, "state": "not_applicable", "why": "no usable live key"}
    bpath = Path(override or BACKUP_DEFAULT)
    try:
        size = bpath.stat().st_size
        raw = bpath.read_bytes().strip()
    except FileNotFoundError:
        return {"path": where, "state": "missing", "present": False, "size_bytes": None,
                "matches": None}
    except OSError as exc:
        return {"path": where, "state": "unreadable", "present": True, "size_bytes": None,
                "matches": None, "why": type(exc).__name__}
    same = hmac.compare_digest(hashlib.sha256(raw).digest(), hashlib.sha256(live).digest())
    return {"path": where, "state": "ok" if same else "mismatch", "present": True,
            "size_bytes": size, "matches": same}


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
    if hit is None or hit[0] != ident:
        _alert_clear()                      # a fresh load: close any open incident (v5e)
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
    """The HMAC key's bytes, or None (no usable key: callers fail closed). Never printed.

    A short or unreadable key pages (ALERT_KEY). An ABSENT key pages only for a WRITER
    (`create=True`): off the box a reader with no key is the design, not an incident. Nothing here
    ever creates a key (v5e): see `create_account_key_first_time`."""
    path = key_path()
    try:
        got = _read_key(path)
    except FileNotFoundError:
        if create:
            _alert(ALERT_KEY, "absent",
                   "account key ABSENT on a writer: it is never regenerated by a writer (that "
                   "would orphan every hashed row), so every stamp fails closed (account_key "
                   f"None). {RESTORE_STEP}")
        return None
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
    return got


#: The ledgers that carry hashed rows; any one of them holding an account_key means a key EXISTED.
HASHED_LEDGERS = ("desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/order_intents.jsonl")
E8_DECLARATION_REL = "desks/mt5/data/E8_ACCOUNT.json"
_HASHED_ROW = re.compile(rb'"account_key"\s*:\s*"sha256:[0-9a-f]{16}"')


def create_account_key_first_time(*, operator_present: bool = False,
                                  root: Path | None = None) -> tuple[bool, str]:
    """THE ONLY WAY A KEY IS MADE (v5e). (created, why); never prints or returns the key.

    Refuses unless `operator_present` (the principal is at the laptop, by an explicit flag);
    refuses if any key file is there at all (present, short or unreadable: it is restored, never
    replaced); refuses if a ledger already holds a hashed row (a key existed and was lost --
    regenerating would orphan those rows) or if E8_ACCOUNT.json exists (a declaration keyed under
    the old key)."""
    base = Path(root or _REPO)
    path = key_path()
    if not operator_present:
        return False, "refused: --at-the-laptop / operator_present=True not given"
    if path.exists() or path.is_symlink():
        return False, f"refused: a key file already exists; {RESTORE_STEP}"
    if (base / E8_DECLARATION_REL).exists():
        return False, (f"refused: {E8_DECLARATION_REL} exists, so a key existed and was lost; "
                       f"{RESTORE_STEP}")
    for rel in HASHED_LEDGERS:
        try:
            body = (base / rel).read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            return False, f"refused: {rel} unreadable ({type(exc).__name__}); cannot prove no key"
        if _HASHED_ROW.search(body):
            return False, (f"refused: {rel} already holds hashed rows, so a key existed and was "
                           f"lost; {RESTORE_STEP}")
    try:
        _create_key(path)
    except OSError as exc:
        return False, f"refused: the key could not be written ({type(exc).__name__})"
    ok = _box_key() is not None
    return ok, ("created; back it up to the box-local backup now" if ok else
                "written but does not read back as a usable key")


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
    login is unreadable or no box key is held. `create=True` marks a WRITER on the box: it never
    creates a key (v5e); with none it gets None, fails closed and pages.

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


def main(argv: list[str] | None = None) -> int:
    """`--create-first-time --at-the-laptop`: the one key-creating entry point. Prints the
    verdict only, never the key. rc 0 created, 1 refused."""
    import argparse
    ap = argparse.ArgumentParser(description="the account key's one creating entry point")
    ap.add_argument("--create-first-time", action="store_true", required=True)
    ap.add_argument("--at-the-laptop", action="store_true",
                    help="the principal is present; without it nothing is created")
    args = ap.parse_args(argv)
    ok, why = create_account_key_first_time(operator_present=bool(args.at_the_laptop))
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    raise SystemExit(main())
