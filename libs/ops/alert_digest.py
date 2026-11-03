"""OPT-IN DAILY DIGEST for repeating measurement-gap pages (2026-11-03).

The principal: "I got tons of ntfy things". The box's 41 pages in 48h were 26 six-hourly
repeats of measurement-gap reminders (restore drill / backup UNMEASURED, login fence
UNMEASURED, state meter silent/flowing, judge coverage) -- none needing his click, none live
money. A caller that OPTS IN by calling `send()` with a `digest_class` pages at most once per
DIGEST_COOLDOWN_H for that class; repeats inside the window go to the digest file and the next
page carries the held count.

WHY A SEPARATE MODULE. `libs/ops/alert_channels.py` is in the money-path import closure
(ops/money_closure.txt) and stays byte-identical: every live-money pager keeps calling
`alert_channels.send_all` directly and can never be held by this, by construction. Only the
four noisy callers import this module, and none of them is in the money closure.

Never classify by title substring here (audit HOLD e5110a958): the class is caller-declared.
Fails OPEN: any state error lets the page through.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import alert_channels

DIGEST_COOLDOWN_H = 24.0


def _paths(ledger: Path) -> tuple[Path, Path]:
    return ledger.parent / "alert_digest_state.json", ledger.parent / "alert_digest.jsonl"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)


def _gate(cls: str | None, title: str, ledger: Path, now: datetime) -> tuple[bool, int]:
    """(hold, repeats_owed)."""
    if not cls:
        return False, 0
    state_p, digest_p = _paths(ledger)
    try:
        state = json.loads(state_p.read_text("utf-8")) if state_p.exists() else {}
        row = state.get(cls) or {}
        last = datetime.fromisoformat(row["last_paged"]) if row.get("last_paged") else None
        if last is not None and (now - last).total_seconds() < DIGEST_COOLDOWN_H * 3600.0:
            row["held"] = int(row.get("held", 0)) + 1
            state[cls] = row
            _write_atomic(state_p, json.dumps(state, indent=1))
            entry = {"ts": now.isoformat(), "class": cls, "title": title[:80]}
            with digest_p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
            return True, 0
        held = int(row.get("held", 0))
        state[cls] = {"last_paged": now.isoformat(), "held": 0}
        _write_atomic(state_p, json.dumps(state, indent=1))
        return False, held
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return False, 0


def send(title: str, body: str, *, config: Path, ledger: Path,
         digest_class: str | None) -> dict[str, Any]:
    """`alert_channels.send_all`, unless this class already paged inside the cooldown.

    A held page returns `delivered` 1 (the digest took it) so callers whose contract is
    "delivered 0 means re-send next pass" do not retry every tick; it is ledgered as a `digest`
    row with ok=False so `alert_channels.all_silent_since()` stays honest.
    """
    hold, held = _gate(digest_class, title, ledger, datetime.now(tz=UTC))
    if hold:
        alert_channels._log("digest", False, f"HELD: {digest_class} paged within "
                            f"{DIGEST_COOLDOWN_H:g}h; counted in the next page", title, ledger)
        return {"armed": None, "delivered": 1, "suppressed": True,
                "results": [{"channel": "digest", "ok": True, "detail": "held"}]}
    if held:
        note = f"(+{held} repeat(s) of this notice held in the last {DIGEST_COOLDOWN_H:g}h)"
        body = note + "\n" + body
    return alert_channels.send_all(title, body, config=config, ledger=ledger)
