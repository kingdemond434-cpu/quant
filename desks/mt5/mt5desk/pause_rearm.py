"""Lift the gateway's OWN placement auto-pause once the terminal is measurably answering again.

WHY (principal, 2026-11-17: "box 'go' replies for routine recovery must be removed"). When every
order of two consecutive placement passes is refused, `gateway.placement_guard` writes
data/GATEWAY_PAUSED with a body that starts "AUTO-PAUSED" and the words "delete this file to
re-arm". Nothing ever deleted it but a person. After the 11-16 reboot a hung terminal refuses
every order, the pause lands, TerminalBoot restarts the terminal -- and the desk then stays flat
until somebody notices the file. That wait is the thing removed here.

THE PAUSE IS LIFTED ONLY WHEN ALL OF THESE HOLD, and every lift is journalled to the gateway log
and the event log (GATEWAY_AUTO_REARMED):
  1. the pause is the gateway's own placement pause: the body starts "AUTO-PAUSED". A pause a
     person wrote, the Fusion ruin rail's halt (fusion_deadman re-arms its own, on its own clear
     condition), or anything else is never touched;
  2. the read-only terminal probe has PASSED since the pause was written: TerminalBoot's
     data/terminal_boot_ok.json carries an `at` later than the pause file's mtime and no older
     than BOOT_OK_MAX_AGE_MIN. "Orders refused" is a terminal or venue state; a terminal that
     answers again after the pause is the measured change, not hope;
  3. a backoff has elapsed since the pause was written: REARM_BASE_MIN doubled per auto re-arm in
     the last 24h, capped at REARM_CAP_MIN. If the venue still refuses, the gateway re-pauses in
     two passes on its own rule and the next lift waits twice as long -- refused orders cost
     nothing, a flat desk on a working venue costs the day.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PAUSE_TAG = "AUTO-PAUSED"
BOOT_OK_MAX_AGE_MIN = 90.0
REARM_BASE_MIN = 30.0
REARM_CAP_MIN = 480.0


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read_json(p: Path) -> dict[str, Any]:
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def decide(paused: Path, boot_ok: Path, history: Path, now: datetime) -> dict[str, Any]:
    """The verdict, with no side effects. `rearm` is True only when all three conditions hold."""
    out: dict[str, Any] = {"rearm": False, "at": now.isoformat(timespec="seconds")}
    try:
        body = paused.read_text(encoding="utf-8")
        paused_at = datetime.fromtimestamp(paused.stat().st_mtime, tz=UTC)
    except OSError:
        out["why"] = "no pause file"
        return out
    if not body.lstrip().startswith(PAUSE_TAG):
        out["why"] = "pause is not the gateway's own placement pause; never touched"
        return out
    out["paused_at"] = paused_at.isoformat(timespec="seconds")
    ok_at = _parse(_read_json(boot_ok).get("at"))
    if ok_at is None:
        out["why"] = "no passed terminal probe on record (UNMEASURED); held"
        return out
    out["probe_passed_at"] = ok_at.isoformat(timespec="seconds")
    if ok_at <= paused_at:
        out["why"] = "the terminal probe has not passed since the pause; held"
        return out
    if (now - ok_at).total_seconds() / 60.0 > BOOT_OK_MAX_AGE_MIN:
        out["why"] = f"last passed probe is older than {BOOT_OK_MAX_AGE_MIN:.0f} min; held"
        return out
    recent = [t for t in (_parse(x) for x in _read_json(history).get("rearms", []))
              if t is not None and t > now - timedelta(days=1)]
    wait = min(REARM_BASE_MIN * (2 ** len(recent)), REARM_CAP_MIN)
    waited = (now - paused_at).total_seconds() / 60.0
    out.update(backoff_min=wait, waited_min=round(waited, 1), rearms_24h=len(recent))
    if waited < wait:
        out["why"] = f"backoff {waited:.0f}/{wait:.0f} min (auto re-arm #{len(recent) + 1} in 24h)"
        return out
    out["rearm"] = True
    out["why"] = (f"own placement pause; terminal probe passed at {out['probe_passed_at']} after "
                  f"the pause; backoff {wait:.0f} min elapsed")
    out["first_line"] = body.strip().splitlines()[0][:300] if body.strip() else ""
    return out


def maybe_rearm(paused: Path, boot_ok: Path, history: Path,
                now: datetime | None = None) -> dict[str, Any]:
    """Lift the pause when `decide` says so; record the lift. Returns the verdict either way."""
    now = now or datetime.now(tz=UTC)
    v = decide(paused, boot_ok, history, now)
    if not v["rearm"]:
        return v
    # Re-read the body immediately before the unlink: a person who wrote over the auto-pause in
    # the meantime owns the file now.
    try:
        if not paused.read_text(encoding="utf-8").lstrip().startswith(PAUSE_TAG):
            v.update(rearm=False, why="pause body changed before the lift; never touched")
            return v
        paused.unlink()
    except OSError as exc:
        v.update(rearm=False, why=f"lift failed: {type(exc).__name__}")
        return v
    h = _read_json(history)
    keep = [x for x in h.get("rearms", [])
            if (t := _parse(x)) is not None and t > now - timedelta(days=1)]
    keep.append(now.isoformat(timespec="seconds"))
    h["rearms"] = keep
    h["last"] = v
    try:
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text(json.dumps(h, indent=1), encoding="utf-8")
    except OSError:
        pass
    return v
