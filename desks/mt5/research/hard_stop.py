"""THE HARD STOP: one implementation of the standing rule for a 401, 403 or 429.

A producer that receives one stops the pass on the spot, marks itself METHOD_BLOCKED (403/429) or
NEEDS_KEY (401) with the reason, persists a backoff (the response's Retry-After when it names one,
else 1h doubling per consecutive block, capped at 7 days) that makes its later passes request
nothing until it expires, and records the block in the desk's one register of sources that stopped
yielding, `data/intelligence/blocked_sources.json`. It never retries around the block, rotates
identity or User-Agent, or takes another host or route to the same gated content.

Used by `research/form4_lane.py` and `side_channels/google_trends_miner.py`.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

HARD_STOP: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}
#: Backoff when the response names no Retry-After: 1h, doubling per consecutive block, capped.
BACKOFF_BASE_S = 3600.0
BACKOFF_MAX_S = 7 * 86400.0
#: The desk's one register of sources that stopped yielding (written by the regional survivor
#: hunters too); a block is recorded there, never in a register of its own.
BLOCKED_REGISTER = DESK / "data" / "intelligence" / "blocked_sources.json"


def _parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def retry_after_s(value: str | None, now: datetime) -> float | None:
    """Retry-After as seconds from `now`: delta-seconds or an HTTP-date; None when absent/bad."""
    if not value:
        return None
    v = str(value).strip()
    if v.isdigit():
        return float(v)
    try:
        from email.utils import parsedate_to_datetime
        at = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return max(0.0, (at - now).total_seconds())


def block_marker(status: int, url_class: str, headers: dict[str, str], now: datetime,
                 prior: dict[str, Any] | None) -> dict[str, Any]:
    """The persisted marker: who refused, which URL class, when, and until when."""
    hdr = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    consecutive = int((prior or {}).get("consecutive") or 0) + 1
    ra = retry_after_s(hdr.get("retry-after"), now)
    wait = ra if ra is not None else min(BACKOFF_MAX_S,
                                         BACKOFF_BASE_S * 2 ** (consecutive - 1))
    return {"status": HARD_STOP[status], "http_status": status, "url_class": url_class,
            "at": now.isoformat(timespec="seconds"),
            "until": (now + timedelta(seconds=wait)).isoformat(timespec="seconds"),
            "backoff_s": wait, "backoff_source": "retry_after" if ra is not None else
            "exponential", "consecutive": consecutive}


def active(marker: Any, now: datetime) -> bool:
    """Is this persisted marker still in force at `now`?"""
    if not isinstance(marker, dict):
        return False
    until = _parse_time(marker.get("until"))
    return until is not None and now < until


def record_block(marker: dict[str, Any], register: Path, *, key: str, host: str,
                 region: str = "global") -> None:
    """Add or update `key` in the existing blocked-sources register (same schema as the regional
    survivor hunters' entries); every other entry is kept."""
    reg = _read_json(register, None)
    if not isinstance(reg, dict):
        reg = {"note": "sources that returned no survivor records -- a WORK QUEUE, never a "
                       "discovery.", "sources": {}}
    e = reg.setdefault("sources", {}).setdefault(key, {"first_seen": marker["at"],
                                                       "region": region})
    e.update({"last_seen": marker["at"], "url": f"{host} {marker['url_class']}",
              "diagnosis": marker["status"],
              "fix_hint": (f"HARD STOP: HTTP {marker['http_status']} -- backed off until "
                           f"{marker['until']}; no retry around the block, no identity or "
                           "User-Agent rotation, no other host or route to the same content"
                           + ("; a key/credential is needed" if marker["status"] == "NEEDS_KEY"
                              else "")),
              "error": f"HTTP {marker['http_status']} on {marker['url_class']}",
              "blocked_until": marker["until"],
              "attempts": int(e.get("attempts", 0)) + 1})
    _write_json(register, reg)
