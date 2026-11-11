"""One marker every live lane reads before it opens a position: the unattended adopter's hold.

WHY NOT GATEWAY_PAUSED (audit HOLD on the adopter v1, 2026-10-28). The adopter's last resort was
to write GATEWAY_PAUSED when a bad release could not be rolled back. That file makes the gateway
return before it even connects, so open positions lost the close-hour flatten, the OCO cancel
and the time exits, while a resting bracket leg could still fill; and the E8 and FTMO lanes never
read it at all, so they went on trading the failed code. A hold for a failed release must stop
NEW entries only -- management, cancels and flattens keep running -- and it must reach every lane
that can open a position.

    gateway      ANDs it into NEW_RISK_OK, the gate every placement path already obeys, after
                 the management block has run
    E8 executor  skips a sleeve's new order (closes and breakeven moves still run)
    E8 gold      skips a window's bracket placement
    FTMO follow  skips the follow order (management of an open follow still runs)

ONE FILE PER WRITER. `place(by=...)` writes desks/mt5/data/new_risk_holds/<by>.json and never
overwrites it; `lift(by=...)` removes only that writer's file. A person's hold and the guard's
therefore stand side by side: lifting one never lifts the other, and the guard holds even while a
person's hold is already up (adopter v2 audit, probe 13d). desks/mt5/data/ADOPT_NEW_RISK_HOLD.json
is also honoured as a hold a person may write by hand; no code here removes it. An unreadable
file, or a hold folder that cannot be listed, holds: a marker nobody can read is still a marker,
and so does ANY file in the folder, whatever its name (adopter v3 audit: a non-.json file was
skipped).

WHOSE RUN PLACED IT (adopter v3 audit MF1). `place(run=...)` records the run that wrote the hold,
and `lift(run=...)` removes it only when that same run wrote it. A run that found the guard's hold
already standing -- left by a rollback that failed -- therefore never lifts it on a "nothing was
adopted" exit; only a passing health check (`lift` with no run) may.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOLD_REL = "desks/mt5/data/ADOPT_NEW_RISK_HOLD.json"
HOLD_DIR_REL = "desks/mt5/data/new_risk_holds"


def _root(root: Path | None) -> Path:
    return ROOT if root is None else Path(root)


def hold_file(by: str, root: Path | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", by) or by.startswith("."):
        raise ValueError(f"hold writer {by!r} is not a plain name")
    return _root(root) / HOLD_DIR_REL / f"{by}.json"


def _describe(f: Path, default_by: str) -> str:
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        why = str(doc.get("why") or "no reason recorded")
        by = str(doc.get("by") or default_by)
    except (OSError, ValueError, AttributeError):
        return f"ADOPT HOLD: {f.name} is unreadable -- no new risk until it is removed"
    return f"ADOPT HOLD by {by}: {why} -- no new risk until it is lifted"


def reason(root: Path | None = None) -> str | None:
    """Why new risk is held, or None. Never raises: a lane must be able to ask every pass."""
    base = _root(root)
    found: list[str] = []
    try:
        legacy = base / HOLD_REL
        if legacy.exists():
            found.append(_describe(legacy, "unknown"))
        d = base / HOLD_DIR_REL
        if d.exists():
            for f in sorted(d.iterdir()):
                if not f.is_dir():
                    found.append(_describe(f, f.stem))
    except OSError:
        return "ADOPT HOLD: the hold markers could not be examined -- no new risk"
    return " | ".join(found) if found else None


def place(why: str, *, by: str, root: Path | None = None, run: str | None = None) -> bool:
    """Write `by`'s hold unless it already stands. True when it stands afterwards (whoever
    wrote it: `run` is recorded only when this call wrote the file)."""
    f = hold_file(by, root)
    doc: dict[str, str] = {"by": by, "at": datetime.now(UTC).isoformat(), "why": why}
    if run:
        doc["run"] = run
    body = json.dumps(doc)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(f), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return True
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        h.write(body)
    return True


def since(*, by: str, root: Path | None = None) -> datetime | None:
    """When `by`'s hold went up, or None when it has none (an unreadable one dates from 1970)."""
    f = hold_file(by, root)
    if not f.exists():
        return None
    try:
        t = datetime.fromisoformat(str(json.loads(f.read_text(encoding="utf-8")).get("at")))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except (OSError, ValueError, AttributeError):
        return datetime.fromtimestamp(0, UTC)


def lift(*, by: str, root: Path | None = None, run: str | None = None) -> bool:
    """Remove `by`'s own hold; with `run`, only when that run wrote it. True when removed."""
    f = hold_file(by, root)
    if run is not None:
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("run") != run:
                return False
        except (OSError, ValueError, AttributeError):
            return False
    try:
        f.unlink()
        return True
    except OSError:
        return False
