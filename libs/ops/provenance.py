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

NOTHING ON THE ORDER PATH TOUCHES THE NETWORK (v5f). `account_key` runs between order_send and
the next bracket leg, so it only APPENDS a row to an outbox (`_enqueue`); `deliver_pending`, run
by MT5-BoxHeartbeat every 5 minutes and MT5-ProcessHealth hourly (or `python -m
libs.ops.provenance --deliver-alerts`), writes the AlertLedger and pages, under one OS lock.

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
import subprocess
import sys
import threading
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
#: An undelivered page is retried at most this often by one deliverer process.
RETRY_UNDELIVERED_S = 300.0
Sender = Callable[[str, str], dict[str, Any]]
#: THE ORDER PATH'S IN-PROCESS DEDUPE (v5f): (outbox, alert id, status|sig) -> monotonic time it
#: was last enqueued. It EXPIRES after REPAGE_H, so a process that lives for days
#: (gateway_resident) re-enqueues a standing incident every 6h and the deliverer repages it --
#: a set that never expired made a long-lived process page an incident once, then never again.
_ENQUEUED: dict[tuple[str, str, str], float] = {}
#: outbox -> monotonic time of the last FAILED append (v5f: the retry time is recorded in the
#: except branch too, so a full disk or a denied outbox costs one attempt per window, never one
#: per row on the money path).
_ENQUEUE_FAILED: dict[str, float] = {}
#: (page state, alert id, status|sig) -> monotonic time of the deliverer's last failed send.
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


def _outbox_path() -> Path:
    """The alert OUTBOX beside the page state: one JSON line per enqueued alert row."""
    return _page_state_path().with_name("account_key_outbox.jsonl")


def _default_sender() -> Sender:
    """alert_channels.send_all against the channels config beside the alert state: the box's
    data/secrets/alert_channels.json; under a key override, one in the override's directory (so
    a test's temp key can never reach the real channels)."""
    base = _data_dir()

    def send(title: str, body: str) -> dict[str, Any]:
        from libs.ops import alert_channels
        # DESK: an unnamed account FAILS CLOSED (its legs are refused) and restoring the box-held
        # key is a thread's step; no position is left needing the owner's hand.
        return alert_channels.send_all(title, body,
                                       config=base / "secrets" / "alert_channels.json",
                                       ledger=base / "alert_delivery.jsonl", audience="desk")
    return send


#: Tests (and only tests) replace this; None means `_default_sender()`.
SENDER: Sender | None = None


#: A well-formed outbox row (v5f.1): an alert id is a short token, never a dict's repr or an
#: empty string, and a row with no title is never paged (it used to page with an empty one).
_AID = re.compile(r"[A-Za-z0-9_.:@-]{1,80}")


def _row_problem(r: Any) -> str | None:
    """Why `r` is not a deliverable outbox row, or None."""
    if not isinstance(r, dict):
        return "not an object"
    if not isinstance(r.get("aid"), str) or not _AID.fullmatch(r["aid"]):
        return "aid is not a short token"
    if r.get("status") not in ("OPEN", "OK"):
        return "status is not OPEN or OK"
    for k in ("sig", "title", "body", "at"):
        if not isinstance(r.get(k), str):
            return f"{k} is not a string"
    if not r["title"].strip():
        return "empty title"
    try:
        datetime.fromisoformat(r["at"])
    except ValueError:
        return "at is not a timestamp"
    if not isinstance(r.get("needs_human", ""), str) or not isinstance(r.get("ledger", False),
                                                                        bool):
        return "needs_human / ledger mistyped"
    return None


#: THE FAST PATH (v5f.1). The heartbeat drains the outbox every 5 minutes, so a KEY_MISMATCH or
#: UNDECLARED incident paged up to 5 minutes late while trading sat failed-closed. Each successful
#: enqueue now also KICKS one deliverer: a daemon thread starts a detached, below-normal
#: `python -m libs.ops.provenance --deliver-alerts` child and the caller returns at once. Best
#: effort -- the heartbeat still delivers whatever the kick did not -- and throttled to one kick
#: per IMMEDIATE_DRAIN_MIN_S per process. `QUANT_ALERT_IMMEDIATE_DRAIN=0` turns it off.
IMMEDIATE_DRAIN_ENV = "QUANT_ALERT_IMMEDIATE_DRAIN"
IMMEDIATE_DRAIN_MIN_S = 30.0
_DRAIN_CHILD_ENV = "QUANT_ALERT_DRAIN_CHILD"
#: Tests replace this; None means `_spawn_drain_child`, which a pytest process never runs.
DRAIN_SPAWNER: Callable[[], Any] | None = None
_LAST_KICK: list[float] = []


def _spawn_drain_child() -> subprocess.Popen[bytes]:
    """The detached deliverer, below normal priority; it lowers itself again on start."""
    cmd = [sys.executable, "-m", "libs.ops.provenance", "--deliver-alerts"]
    common: dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL, "close_fds": True, "cwd": str(_REPO),
                              "env": {**os.environ, _DRAIN_CHILD_ENV: "1"}}
    if sys.platform == "win32":
        base = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000))
        try:
            return subprocess.Popen(cmd, creationflags=base | 0x01000000, **common)
        except OSError:
            return subprocess.Popen(cmd, creationflags=base, **common)
    return subprocess.Popen(cmd, start_new_session=True, **common)


def _run_kick(spawner: Callable[[], Any]) -> None:
    with contextlib.suppress(Exception):
        proc = spawner()
        wait = getattr(proc, "wait", None)
        if callable(wait):          # reap it (POSIX zombie); never kill it
            with contextlib.suppress(Exception):
                wait(timeout=600)


def _kick_drain() -> bool:
    """Start the immediate deliverer without waiting for it. NEVER RAISES, NEVER BLOCKS: the
    caller pays for one thread start."""
    try:
        if os.environ.get(IMMEDIATE_DRAIN_ENV, "1") == "0" or os.environ.get(_DRAIN_CHILD_ENV):
            return False
        now = time.monotonic()
        if _LAST_KICK and now - _LAST_KICK[0] < IMMEDIATE_DRAIN_MIN_S:
            return False
        spawner = DRAIN_SPAWNER
        if spawner is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                return False        # a test never starts a real deliverer unless it asks to
            spawner = _spawn_drain_child
        _LAST_KICK[:] = [now]
        threading.Thread(target=_run_kick, args=(spawner,), daemon=True,
                         name="account-key-alert-drain").start()
        return True
    except Exception:
        return False


def _enqueue(aid: str, status: str, sig: str, title: str, body: str,
             needs_human: str = "", *, ledger: bool = False) -> bool:
    """THE ONLY ALERT WORK ON THE ORDER PATH (v5f): append one line to the outbox. No network,
    no lock, no ledger read -- `account_key` runs between order_send and the next bracket leg,
    and a send there (12 s per channel, repeated when the page state could not be written or the
    sender raised) delayed the protective leg. Delivery is `deliver_pending`, run by
    MT5-BoxHeartbeat every 5 minutes and by MT5-ProcessHealth hourly. NEVER RAISES."""
    doc = {"at": datetime.now(UTC).isoformat(timespec="microseconds"), "pid": os.getpid(),
           "aid": aid, "status": status, "sig": sig, "title": title,
           "body": body[:1500] if isinstance(body, str) else body,
           "needs_human": needs_human[:600] if isinstance(needs_human, str) else needs_human,
           "ledger": ledger}
    if _row_problem(doc) is not None:
        return False                # never write a row the deliverer would quarantine
    path = _outbox_path()
    memo = (str(path), aid, f"{status}|{sig}")
    now = time.monotonic()
    last = _ENQUEUED.get(memo)
    if last is not None and now - last < REPAGE_H * 3600:
        return False
    failed = _ENQUEUE_FAILED.get(str(path))
    if failed is not None and now - failed < RETRY_UNDELIVERED_S:
        return False
    try:
        row = json.dumps(doc) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, row.encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        _ENQUEUE_FAILED[str(path)] = now
        return False
    _ENQUEUE_FAILED.pop(str(path), None)
    # a new state for this alert supersedes the other one's memo (an incident after a recovery,
    # or a recovery after an incident, is enqueued at once)
    for m in [m for m in _ENQUEUED if m[0] == memo[0] and m[1] == aid and m != memo]:
        _ENQUEUED.pop(m, None)
    _ENQUEUED[memo] = now
    _kick_drain()
    return True


def _alert(aid: str, detail: str, message: str) -> None:
    """Enqueue `aid` OPEN. The deliverer writes the AlertLedger (NEEDS_HUMAN) and pages."""
    title = ("ACCOUNT KEY UNUSABLE: ledger stamps fail closed" if aid == ALERT_KEY
             else "ACCOUNT KEY: a non-numeric login was keyed None")
    why = (RESTORE_STEP if aid == ALERT_KEY else
           "fix the caller to pass the numeric MT5 login, never a username")
    _enqueue(aid, "OPEN", detail, title, message, needs_human=why, ledger=True)


def _alert_clear() -> None:
    """A usable key was read (on a key-cache miss only): enqueue the recovery. The deliverer
    closes the alert (verified by this read) and pages the recovery ONCE across every process.
    Only when there is an incident to close -- one queued, or one the page state holds open --
    so a box that never had one writes nothing. Two small local reads, never a lock or a send."""
    try:
        open_incident = _outbox_path().exists()
        if not open_incident:
            st = _read_state(_page_state_path())
            w = (st or {}).get(ALERT_KEY)
            open_incident = st is None or (isinstance(w, dict) and (
                w.get("want") == "OPEN"
                or (isinstance(w.get("paged"), dict) and w["paged"].get("status") == "OPEN")))
        if not open_incident and _alert_ledger_path().exists():
            from libs.ops.alert_ledger import AlertLedger
            known = AlertLedger(_alert_ledger_path()).alerts.get(ALERT_KEY)
            open_incident = known is not None and known.open
    except Exception:
        open_incident = True     # unsure: enqueue, the deliverer decides
    if not open_incident:
        return
    _enqueue(ALERT_KEY, "OK", "recovered", "ACCOUNT KEY OK again",
             "the account key reads as a usable key again; ledger stamps carry account_key",
             ledger=True)


def _page(aid: str, status: str, sig: str, title: str, body: str) -> dict[str, Any]:
    """THE v5e ENTRY POINT, KEPT (v5f): same signature, same "never raises, returns a dict with
    `sent`", now ENQUEUE-ONLY -- so a caller written against v5e (Fusion r7.2's cross_account
    page_key / clear_key_alert) goes off the order path with no change. Its rules are v5e's:
    "OPEN" pages a new `sig` and again every REPAGE_H while it stands; "OK" pages once, only
    after a delivered OPEN; `delivered` 0 is not a page. The page itself is sent by
    `deliver_pending`, so `sent` is always False here and `queued` says whether a row was
    written; like v5e's `_page`, it never writes the AlertLedger."""
    try:
        if status not in ("OPEN", "OK"):
            return {"sent": False, "queued": False, "reason": f"unknown status {status!r}"}
        queued = _enqueue(aid, status, sig, title, body)   # validated: a dict aid is refused
        return {"sent": False, "queued": queued,
                "reason": ("queued: delivered off the order path by deliver_pending" if queued
                           else "deduplicated or enqueue throttled (this process)")}
    except Exception as exc:
        return {"sent": False, "queued": False, "reason": f"page failed ({type(exc).__name__})"}


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, indent=1))
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _drain(outbox: Path) -> list[tuple[Path, list[dict[str, Any]]]]:
    """Move the outbox aside (appenders open it per row, so a rename takes every finished row and
    later rows start a new file) and read it with any earlier drain a crash left behind."""
    with contextlib.suppress(FileNotFoundError, PermissionError):
        os.replace(outbox, outbox.with_name(
            f"{outbox.name}.{os.getpid()}.{time.time_ns()}.draining"))
    out: list[tuple[Path, list[dict[str, Any]]]] = []
    for f in sorted(outbox.parent.glob(outbox.name + ".*.draining")):
        rows: list[dict[str, Any]] = []
        bad: list[str] = []
        with contextlib.suppress(OSError):
            for line in f.read_text("utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    r = None
                why = "not JSON" if r is None else _row_problem(r)
                if why is None:
                    rows.append(r)
                else:
                    bad.append(json.dumps({"why": why, "line": line[:4000]}))
        if bad:
            _quarantine(outbox, bad)
        out.append((f, rows))
    return out


def _quarantine(outbox: Path, lines: list[str]) -> None:
    """Malformed outbox rows are KEPT, never paged and never silently dropped (v5f.1)."""
    with contextlib.suppress(OSError):
        q = outbox.with_name("account_key_outbox.quarantine.jsonl")
        with open(q, "a", encoding="utf-8") as fh:
            fh.write("".join(x + "\n" for x in lines))


def _to_ledger(applied: dict[str, dict[str, Any]]) -> str:
    """Write each alert's newest state to the AlertLedger, in ONE locked transaction."""
    if not applied:
        return "nothing to write"
    try:
        from libs.ops.alert_ledger import AlertLedger
        with AlertLedger.transaction(_alert_ledger_path()) as ledger:
            for aid, w in applied.items():
                known = ledger.alerts.get(aid)
                if w["want"] == "OPEN":
                    if known is None or not known.open or known.message != w["body"][:600]:
                        ledger.observe(aid, w["body"][:600], scope="RUNTIME")
                        ledger.needs_human(aid, w.get("needs_human") or "see the alert")
                elif known is not None and known.open:
                    ledger.verify(aid, still_firing=False)
        return "written"
    except Exception as exc:
        return f"not written ({type(exc).__name__})"


def deliver_pending() -> dict[str, Any]:
    """DELIVER THE OUTBOX, OFF THE ORDER PATH (v5f). One deliverer at a time, under an OS lock.

    Each alert's newest enqueued row becomes its WANTED state in the page-state file; then:
    OPEN pages on a new incident (or a new detail), and again when the incident was re-observed
    and REPAGE_H has passed since the last page; OK pages once, only if the last delivered page
    was OPEN. The page state is read, decided on, sent and written UNDER THE LOCK, so the
    recovery fires exactly once across processes. A send that raises or `delivered` 0 is not a
    page: the wanted state stays and the next pass sends it. A page state that cannot be read
    stops the pass before the outbox is drained, so no row is lost. NEVER RAISES."""
    out: dict[str, Any] = {"rows": 0, "sent": [], "ledger": None}
    try:
        from libs.ops.alert_ledger import os_lock
        state_path = _page_state_path()
        with os_lock(state_path.with_name(state_path.name + ".flock"), timeout_s=30):
            state = _read_state(state_path)
            if state is None:
                out["error"] = "page state unreadable: nothing drained"
                return out
            drained = _drain(_outbox_path())
            for _f, rows in drained:
                for r in rows:
                    out["rows"] += 1
                    aid = str(r["aid"])
                    got = state.get(aid)
                    w: dict[str, Any] = got if isinstance(got, dict) else {}
                    if str(r.get("at") or "") < str(w.get("want_at") or ""):
                        continue
                    w = {**w, "want": r["status"], "sig": str(r.get("sig") or ""),
                         "ledger": bool(r.get("ledger")),
                         "ledger_pending": bool(r.get("ledger")) or bool(w.get("ledger_pending")),
                         "want_at": str(r.get("at") or ""), "title": str(r.get("title") or ""),
                         "body": str(r.get("body") or ""),
                         "needs_human": str(r.get("needs_human") or "")}
                    state[aid] = w
            if drained:
                _write_json(state_path, state)          # the rows are now held in the state
                for f, _rows in drained:
                    with contextlib.suppress(OSError):
                        f.unlink()
            # THE LEDGER WRITE IS RETRIED, NEVER DROPPED (v5f.1). A row's NEEDS_HUMAN entry is
            # held as `ledger_pending` in the page state (which has absorbed the outbox row) until
            # a transaction lands; a Busy or Unreadable ledger leaves it pending for the next pass.
            applied = {aid: w for aid, w in state.items()
                       if isinstance(w, dict) and w.get("ledger_pending")}
            out["ledger"] = _to_ledger(applied)
            if applied and out["ledger"] == "written":
                for w in applied.values():
                    w["ledger_pending"] = False
                _write_json(state_path, state)
            elif applied:
                out["ledger_pending"] = sorted(applied)
            now = datetime.now(UTC)
            for aid, w in list(state.items()):
                if not isinstance(w, dict) or w.get("want") not in ("OPEN", "OK") \
                        or not _AID.fullmatch(str(aid)) or not str(w.get("title") or "").strip():
                    continue
                got_p = w.get("paged")
                paged: dict[str, Any] = got_p if isinstance(got_p, dict) else {}
                last = None
                with contextlib.suppress(TypeError, ValueError):
                    last = datetime.fromisoformat(str(paged.get("at")))
                if w["want"] == "OPEN":
                    due = (paged.get("status") != "OPEN" or paged.get("sig") != w.get("sig")
                           or (last is not None and str(w.get("want_at")) > str(paged.get("at"))
                               and (now - last).total_seconds() / 3600 >= REPAGE_H))
                else:
                    due = paged.get("status") == "OPEN"
                if not due:
                    continue
                memo = (str(state_path), aid, f"{w['want']}|{w.get('sig')}")
                tried = _LAST_TRY.get(memo)
                if tried is not None and time.monotonic() - tried < RETRY_UNDELIVERED_S:
                    continue
                try:
                    res = (SENDER or _default_sender())(str(w.get("title")),
                                                        str(w.get("body"))[:1500])
                except Exception as exc:
                    _LAST_TRY[memo] = time.monotonic()     # v5f: recorded on a raise too
                    out["sent"].append({"aid": aid, "sent": False,
                                        "reason": f"sender raised ({type(exc).__name__})"})
                    continue
                res = res if isinstance(res, dict) else {}
                if not res.get("delivered"):
                    _LAST_TRY[memo] = time.monotonic()
                    out["sent"].append({"aid": aid, "sent": False, "reason": "undelivered"})
                    continue
                w["paged"] = {"status": w["want"], "sig": w.get("sig"),
                              "at": now.isoformat(timespec="microseconds")}
                _write_json(state_path, state)
                _LAST_TRY.pop(memo, None)
                out["sent"].append({"aid": aid, "sent": True, "status": w["want"]})
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}"
    return out


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


def _lower_own_priority() -> None:
    """The immediate deliverer runs below normal: it must never compete with the order path.
    Only this process is touched."""
    with contextlib.suppress(Exception):
        import psutil  # type: ignore[import-untyped,unused-ignore]
        me = psutil.Process()
        if sys.platform == "win32":
            me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            me.nice(max(me.nice(), 10))


def main(argv: list[str] | None = None) -> int:
    """`--create-first-time --at-the-laptop`: the one key-creating entry point. Prints the
    verdict only, never the key. rc 0 created, 1 refused."""
    import argparse
    ap = argparse.ArgumentParser(description="the account key's one creating entry point")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create-first-time", action="store_true")
    mode.add_argument("--deliver-alerts", action="store_true",
                      help="deliver the alert outbox (off the order path; v5f)")
    ap.add_argument("--at-the-laptop", action="store_true",
                    help="the principal is present; without it nothing is created")
    args = ap.parse_args(argv)
    if args.deliver_alerts:
        if os.environ.get(_DRAIN_CHILD_ENV):
            _lower_own_priority()
        res = deliver_pending()
        print(json.dumps({k: res.get(k) for k in ("rows", "sent", "ledger", "error")}))
        return 0
    ok, why = create_account_key_first_time(operator_present=bool(args.at_the_laptop))
    print(why)
    return 0 if ok else 1


if __name__ == "__main__":
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    raise SystemExit(main())
