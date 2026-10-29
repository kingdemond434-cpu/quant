"""BACKUP_STATE.json: is the desk's state backed up, and was a restore ever rehearsed? (v5f)

ONE PUBLISHED ANSWER, SCHEME ONLY. The facts already exist on the box, spread over four writers:

    MT5-OffsiteBackup   desks/mt5/scripts/offsite_backup.py -> reports/OFFSITE_BACKUP.json
                        (restic, encrypted off-site; its own restore drill, the 8-day rule)
    ops_redundancy      desks/mt5/research/ops_redundancy.py -> reports/OPS_REDUNDANCY.json
                        (off-box restore drill of the box stores from the origin ref)
    MT5-RebootDrill     ops/reboot_drill.ps1 -> reports/REBOOT_DRILL.json
    moat backup         scripts/run_moat_backup.py -> data/backup_status.json and
                        scripts/run_restore_drill.py -> reports/restore_drill.json (VPS side)

plus the box-local account-key backup (libs/ops/provenance.key_backup_state). None of those
reports crossed the wire, and two of them cannot: OFFSITE_BACKUP.json carries restic's stderr in
its `why` (which can name the repository), and the moat manifest carries paths and sha256 digests.
So this file is BUILT FROM AN ALLOW-LIST -- timestamps re-serialised from a parsed datetime,
enumerated states matched against a token pattern, booleans and counts -- and nothing free-form
from a source is ever copied. No path, no repository, no password, no restic key, no hash, no
account. The key backup stays where it is: this reads present / size / matches and moves nothing.

THE RESTORE-DRILL INVARIANT. A restore that has not been rehearsed in 8 days (the same 8 days
offsite_backup.verdict uses) is a hope, not a backup. Older than that, FAILED, or ABSENT pages
through alert_channels.send_all, deduplicated (login_fence.page's idiom: a new incident pages,
the same one again every REPAGE_H, recovery once). ABSENT reads UNMEASURED and PAGES; it never
reads OK.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: Where the CODE lives (the offsite job's own verdict is imported from here), as distinct from
#: ROOT, the tree whose state is read -- a test moves ROOT and keeps the code.
_CODE = Path(__file__).resolve().parent.parent

#: The restore drill's age limit, in days: offsite_backup.verdict's own rule.
DRILL_MAX_AGE_DAYS = 8.0
REPAGE_H = 6.0
RETRY_UNDELIVERED_S = 300.0
ALERT_ID = "restore_drill_overdue"

#: A source's state string is published only if it is a short upper-case token (PASS, NOT_ARMED,
#: DRILL-FAILED ...). Anything else -- a sentence, a path, a URL -- is replaced, never copied.
_TOKEN = re.compile(r"[A-Z][A-Z0-9_-]{0,31}")

Sender = Callable[[str, str], dict[str, Any]]
#: Tests set this; None means alert_channels.send_all against the box's channel config.
SENDER: Sender | None = None
_PAGED: set[tuple[str, str]] = set()
_LAST_TRY: dict[tuple[str, str], float] = {}


def out_path() -> Path:
    return ROOT / "desks" / "mt5" / "reports" / "BACKUP_STATE.json"


def _page_state_path() -> Path:
    return ROOT / "desks" / "mt5" / "logs" / "backup_state_page.json"


def _sources() -> dict[str, Path]:
    reports = ROOT / "desks" / "mt5" / "reports"
    return {
        "offsite": reports / "OFFSITE_BACKUP.json",
        "ops_redundancy": reports / "OPS_REDUNDANCY.json",
        "reboot_drill": reports / "REBOOT_DRILL.json",
        "moat_backup": ROOT / "data" / "backup_status.json",
        "moat_restore_drill": reports / "restore_drill.json",
    }


def _load(p: Path) -> dict[str, Any] | None:
    """The source document, or None when it is absent or unreadable (both are UNMEASURED)."""
    try:
        # PowerShell's Set-Content -Encoding UTF8 writes a BOM; utf-8-sig reads both.
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        t = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(raw: Any) -> str | None:
    """A timestamp RE-SERIALISED from its parse, so only a datetime ever reaches the file."""
    t = _ts(raw)
    return None if t is None else t.astimezone(UTC).isoformat(timespec="seconds")


def _state(raw: Any) -> str:
    if raw is None or raw == "":
        return "UNMEASURED"
    s = str(raw).strip()
    return s if _TOKEN.fullmatch(s) else "UNRECOGNISED"


def _bool(raw: Any) -> bool | None:
    return raw if isinstance(raw, bool) else None


def _count(raw: Any) -> int | None:
    return len(raw) if isinstance(raw, list | dict) else None


def _offsite(doc: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    if doc is None:
        return {"job": "MT5-OffsiteBackup", "state": "UNMEASURED",
                "why": "no OFFSITE_BACKUP.json on this host: the job has not run here"}
    verdict = "UNMEASURED"
    with contextlib.suppress(Exception):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "offsite_backup_for_state", _CODE / "desks" / "mt5" / "scripts" / "offsite_backup.py")
        if spec is not None and spec.loader is not None:
            ob = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ob)
            verdict = _state(ob.verdict(doc, now)[0])   # the STATE only; its `why` is not copied
    return {
        "job": "MT5-OffsiteBackup",
        "state": _state(doc.get("status")),
        "verdict": verdict,
        "at": _iso(doc.get("at")),
        "last_success_at": _iso(doc.get("last_success_at")),
        "last_check_at": _iso(doc.get("last_check_at")),
        "last_check_ok": _bool(doc.get("last_check_ok")),
        "last_prune_at": _iso(doc.get("last_prune_at")),
        "encrypted": bool(doc.get("encryption")),
        "key_escrowed_off_box": _bool(doc.get("key_escrowed_off_box")),
        "n_included": _count(doc.get("included")),
        "n_missing": _count(doc.get("missing")),
    }


def _key_backup() -> dict[str, Any]:
    """present / size / matches from provenance.key_backup_state -- never its path or a hash."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import provenance
        st = dict(provenance.key_backup_state())
    except Exception as exc:
        return {"state": "UNMEASURED", "why": f"key_backup_state unreadable: {type(exc).__name__}"}
    size = st.get("size_bytes")
    return {"state": _state(str(st.get("state") or "").upper() or None),
            "present": _bool(st.get("present")),
            "size_bytes": size if isinstance(size, int) and not isinstance(size, bool) else None,
            "matches": _bool(st.get("matches")),
            "box_local": True}


def _drill(off: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """The off-site RESTORE drill: when it last ran, its verdict, and whether that is in date."""
    rd = (off or {}).get("restore_drill")
    rd = rd if isinstance(rd, dict) else {}
    at = _ts(rd.get("at"))
    verdict = _state(rd.get("verdict"))
    if at is None:
        state, why = "UNMEASURED", ("no restore drill on record: a backup never restored is a "
                                    "hope, not a backup")
        age = None
    else:
        age = round((now - at).total_seconds() / 86400, 2)
        if age > DRILL_MAX_AGE_DAYS:
            state, why = "STALE", (f"last restore drill {age:.1f} days old "
                                   f"(limit {DRILL_MAX_AGE_DAYS:g})")
        elif verdict != "PASS":
            state, why = "FAILED", f"last restore drill verdict {verdict}"
        else:
            state, why = "OK", f"restore drill passed {age:.1f} days ago"
    return {"state": state, "why": why, "at": None if at is None else _iso(rd.get("at")),
            "verdict": verdict if at is not None else "UNMEASURED",
            "age_days": age, "max_age_days": DRILL_MAX_AGE_DAYS}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    src = {k: _load(p) for k, p in _sources().items()}
    off = src["offsite"]
    drill = _drill(off, now)
    red = src["ops_redundancy"]
    red_drill = (red or {}).get("offbox_restore_drill")
    reboot = src["reboot_drill"]
    moat = src["moat_backup"]
    moat_drill = src["moat_restore_drill"]
    key = _key_backup()
    import socket
    doc: dict[str, Any] = {
        "schema": "backup_state/1",
        "at": now.isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "last_backup_at": _iso((off or {}).get("last_success_at")),
        "last_restore_drill_at": drill["at"],
        "restore_drill": drill,
        "offsite": _offsite(off, now),
        "ops_redundancy": ({"state": "UNMEASURED", "why": "no OPS_REDUNDANCY.json on this host"}
                           if red is None else
                           {"state": _state(red.get("status")),
                            "at": _iso(red.get("generated_utc")),
                            "offbox_restore_drill": _state(
                                (red_drill or {}).get("status")
                                if isinstance(red_drill, dict) else None)}),
        "reboot_drill": ({"state": "UNMEASURED", "why": "no REBOOT_DRILL.json on this host"}
                         if reboot is None else
                         {"state": _state(reboot.get("verdict") or reboot.get("status")),
                          "at": _iso(reboot.get("checked_at") or reboot.get("at")
                                     or reboot.get("generated_utc")),
                          "n_failures": _count(reboot.get("failures"))}),
        "moat": {
            "backup": ({"state": "UNMEASURED", "why": "no moat backup manifest on this host"}
                       if moat is None else
                       {"state": _state(moat.get("status")), "at": _iso(moat.get("generated")),
                        "restore_drill_passed": _bool(moat.get("restore_drill_passed")),
                        "n_stores": _count(moat.get("stores")),
                        "n_absent": _count(moat.get("absent_stores"))}),
            "restore_drill": ({"state": "UNMEASURED", "why": "no moat restore drill on this host"}
                              if moat_drill is None else
                              {"state": _state(moat_drill.get("status")),
                               "at": _iso(moat_drill.get("drilled_at"))}),
        },
        "key_backup": key,
    }
    doc["status"] = ("ATTENTION" if drill["state"] in ("STALE", "FAILED")
                     else "UNMEASURED" if drill["state"] == "UNMEASURED" else "OK")
    return doc


def _default_sender() -> Sender:
    def send(title: str, body: str) -> dict[str, Any]:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops import alert_channels
        # DESK: a stale or failed restore drill is re-run by a thread.
        return alert_channels.send_all(title, body,
                                       config=ROOT / "data" / "secrets" / "alert_channels.json",
                                       ledger=ROOT / "data" / "alert_delivery.jsonl",
                                       audience="desk")
    return send


def page(doc: dict[str, Any]) -> dict[str, Any]:
    """THE INVARIANT: a restore drill STALE, FAILED or ABSENT pages; a recovery pages once.

    Deduplicated by (state, last drill at) in a state file, re-paged every REPAGE_H while it
    stands. A send with `delivered` 0 is NOT a page: nothing is recorded and a later pass re-sends
    (throttled to one try per RETRY_UNDELIVERED_S in a process). NEVER RAISES.
    """
    try:
        drill = doc["restore_drill"]
        open_ = drill["state"] != "OK"
        status = "OPEN" if open_ else "OK"
        sig = f"{drill['state']}|{drill.get('at')}"
        path = _page_state_path()
        memo = (str(path), f"{status}|{sig}")
        if memo in _PAGED:
            return {"sent": False, "reason": "deduplicated (this process)"}
        last_try = _LAST_TRY.get(memo)
        if last_try is not None and time.monotonic() - last_try < RETRY_UNDELIVERED_S:
            return {"sent": False, "reason": "undelivered, retry throttled"}
        try:
            state = json.loads(path.read_text("utf-8"))
            state = state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            state = {}
        got = state.get(ALERT_ID)
        prev: dict[str, Any] = got if isinstance(got, dict) else {}
        now = datetime.now(UTC)
        last = _ts(prev.get("paged_at"))
        if open_:
            if prev.get("status") == "OPEN" and prev.get("sig") == sig and last is not None \
                    and (now - last).total_seconds() / 3600 < REPAGE_H:
                _PAGED.add(memo)
                return {"sent": False, "reason": "deduplicated"}
        elif prev.get("status") != "OPEN":
            _PAGED.add(memo)
            return {"sent": False, "reason": "OK: nothing to page"}
        host = doc.get("host") or "this box"
        if open_:
            title = f"Restore drill {drill['state']} on {host}"
            body = (f"{drill['why']}. A restore not rehearsed in {DRILL_MAX_AGE_DAYS:g} days is "
                    "a hope, not a backup. Run MT5-OffsiteBackup's restore drill "
                    "(desks/mt5/scripts/offsite_backup.py) and read BACKUP_STATE.json.")
        else:
            title = f"Restore drill recovered on {host}"
            body = drill["why"]
        res = (SENDER or _default_sender())(title, body[:1500])
        res = res if isinstance(res, dict) else {}
        if not res.get("delivered"):
            _LAST_TRY[memo] = time.monotonic()
            return {"sent": False, "reason": "undelivered, re-sent later",
                    "armed": res.get("armed"), "delivered": res.get("delivered")}
        state[ALERT_ID] = {"status": status, "sig": sig,
                           "paged_at": now.isoformat(timespec="seconds")}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, indent=1), "utf-8")
        os.replace(tmp, path)
        _PAGED.add(memo)
        _LAST_TRY.pop(memo, None)
        return {"sent": True, "armed": res.get("armed"), "delivered": res.get("delivered")}
    except Exception as exc:
        return {"sent": False, "reason": f"page failed ({type(exc).__name__})"}


def write(now: datetime | None = None) -> dict[str, Any]:
    """Build, page on the invariant, and publish. The page result rides in the document."""
    doc = build(now)
    doc["page"] = {k: v for k, v in page(doc).items() if k in ("sent", "reason", "delivered")}
    out = out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, out)
            break
        except PermissionError:
            if attempt == 9:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.2)
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = write()
    print(f"backup state: {doc['status']} (restore drill {doc['restore_drill']['state']}) "
          f"-> {out_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
