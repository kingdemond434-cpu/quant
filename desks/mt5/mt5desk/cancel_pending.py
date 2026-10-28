"""A supported way to withdraw a lane's resting orders without a person deleting a ticket by hand.

THE GAP (2026-10-28, Desk health). A resting FTMO follower order (ticket 111616773) had to go, and
no executor had a lever for it: zuck was asked to delete the ticket in the terminal himself. Each
executor already cancels its own orders for its own reasons (session over, against direction,
OCO); none would cancel one because the desk decided to.

THE REQUEST. desks/mt5/data/CANCEL_PENDING.json (gitignored, box-local; written by Desk health on
the box, or applied by the unattended adopter from desks/mt5/data/box_state_desired/ after an
auditor CLEAR):

    {"requests": [
        {"id": "ftmo-111616773", "lane": "ftmo", "tickets": [111616773],
         "expires_at": "2026-10-28T12:00:00+00:00", "why": "stale follow leg"},
        {"id": "e8-all-1028", "lane": "e8", "all": true,
         "placed_before": "2026-10-28T07:30:00+00:00",
         "expires_at": "2026-10-28T09:00:00+00:00", "why": "..."}]}

WHAT EACH EXECUTOR DOES, on its next pass (FTMO follower: lane ftmo; E8 gold: e8; the gateway's
gold and FX book: fusion):

    * only ITS OWN resting orders are ever candidates (the executor passes the tickets it owns:
      MAGIC on MT5, its own journalled entries and legs on TradeLocker). A requested ticket that
      is not one of them is reported as "not ours" and never touched.
    * `tickets`: exactly those. `all`: every own order PLACED BEFORE the request's
      `placed_before` (and before the lane first saw it), by the order's own setup time. Orders
      placed afterwards are never cancelled by it (that would be a hold, and the new-risk hold
      already exists for that), and the bound is in the request itself, so a lost or garbled
      acknowledgement file cannot widen it (v7 audit MF6). An order whose setup time cannot be
      read is never cancelled by `all`; it is reported, and a `tickets` request names it.
    * a request past `expires_at`, or one more than 48 h long, is ignored: a forgotten file never
      becomes a standing veto.
    * cancels only when the lane is armed, and records each ticket's outcome in
      desks/mt5/data/cancel_pending_acks/<lane>.json, so a cancelled ticket is not re-sent and
      Desk health can read what happened. An acknowledgement file that cannot be read cancels
      nothing for that lane until a person looks (fail closed).
    * every cancel the lane makes is billed as a refusal (Rule 1): a RAIL_BLOCKED line at the
      order's own risk, in the lane's own missed-growth ledger.

It only ever REMOVES resting orders: it opens nothing and closes no position. A file that cannot
be read cancels nothing and says so (an unreadable request is not a reason to touch orders).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_DESK = Path(__file__).resolve().parent.parent
REQUEST_FILE = _DESK / "data" / "CANCEL_PENDING.json"
ACK_DIR = _DESK / "data" / "cancel_pending_acks"
LANES = ("e8", "fusion", "ftmo")
#: The longest a request may live: long enough for one trading day, never a standing rule.
MAX_LIFE = timedelta(hours=48)
#: The rail every requested cancel is billed under (fusion_rails, E8 intents, FTMO reason).
RAIL = "cancel_requested"


class AcksUnreadable(Exception):
    """The lane's acknowledgement file exists but cannot be read."""


def server_time_utc(server_epoch: object) -> datetime | None:
    """A broker-clock stamp (MT5 `time_setup`, TradeLocker order times: seconds on the trade
    server's clock, New York + 7 h) as UTC. Of the two offsets a DST change can leave in doubt
    the smaller is used, so the time read is never EARLIER than the real one: an order is never
    taken for older than it is."""
    if isinstance(server_epoch, bool) or not isinstance(server_epoch, (int, float)):
        return None
    s = float(server_epoch)
    if s <= 0:
        return None
    ny = ZoneInfo("America/New_York")
    offs = []
    for back in (0, 3 * 3600):
        t = datetime.fromtimestamp(s - back, UTC).astimezone(ny)
        offs.append((t.utcoffset() or timedelta(0)) + timedelta(hours=7))
    return datetime.fromtimestamp(s, UTC) - min(offs)


def _when(v: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def problem(doc: object, *, now: datetime | None = None) -> str | None:
    """None when `doc` is a request file every executor reads as written."""
    now = now or datetime.now(UTC)
    if not isinstance(doc, dict) or set(doc) - {"requests", "note"}:
        return "the file must be an object with only 'requests' (and an optional 'note')"
    reqs = doc.get("requests")
    if not isinstance(reqs, list):
        return "requests must be a list"
    seen: set[str] = set()
    for r in reqs:
        if not isinstance(r, dict) or set(r) - {
            "id",
            "lane",
            "tickets",
            "all",
            "placed_before",
            "expires_at",
            "why",
        }:
            return f"request {r!r} has unknown keys"
        rid = r.get("id")
        if not isinstance(rid, str) or not rid or rid in seen:
            return f"request id {rid!r} is missing or repeated"
        seen.add(rid)
        if r.get("lane") not in LANES:
            return f"request {rid}: lane must be one of {LANES}"
        tickets, every = r.get("tickets"), r.get("all")
        if (tickets is None) == (every is None):
            return f"request {rid}: give exactly one of tickets or all"
        if every is not None and every is not True:
            return f"request {rid}: all must be true"
        before = r.get("placed_before")
        if every is True and _when(before) is None:
            return f"request {rid}: all needs placed_before (an ISO time) to bound it"
        if every is None and before is not None:
            return f"request {rid}: placed_before goes only with all"
        if tickets is not None and (
            not isinstance(tickets, list)
            or not tickets
            or any(not isinstance(t, int) or isinstance(t, bool) or t <= 0 for t in tickets)
        ):
            return f"request {rid}: tickets must be a non-empty list of positive integers"
        exp = _when(r.get("expires_at"))
        if exp is None:
            return f"request {rid}: expires_at must be an ISO time"
        if exp - now > MAX_LIFE:
            return f"request {rid}: expires more than {MAX_LIFE} from now"
    return None


def _requests(lane: str, now: datetime, path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return [], None
    except (OSError, ValueError) as exc:
        return [], f"{path.name} unreadable ({type(exc).__name__}); nothing cancelled"
    if not isinstance(doc, dict) or not isinstance(doc.get("requests"), list):
        return [], f"{path.name} is not a request file; nothing cancelled"
    live = []
    for r in doc["requests"]:
        if not isinstance(r, dict) or r.get("lane") != lane or not isinstance(r.get("id"), str):
            continue
        exp = _when(r.get("expires_at"))
        if exp is None or exp <= now or exp - now > MAX_LIFE:
            continue
        live.append(r)
    return live, None


def _ack_path(lane: str, ack_dir: Path) -> Path:
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}")
    return ack_dir / f"{lane}.json"


def _load_acks(lane: str, ack_dir: Path) -> dict[str, Any]:
    """{} when there is no file yet; AcksUnreadable when one exists and cannot be read (v7
    audit MF6: read as empty, it would re-send and re-snapshot)."""
    f = _ack_path(lane, ack_dir)
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise AcksUnreadable(f"{f.name} unreadable ({type(exc).__name__})") from exc
    if not isinstance(doc, dict):
        raise AcksUnreadable(f"{f.name} is not an object")
    return doc


def _save_acks(lane: str, acks: dict[str, Any], ack_dir: Path) -> None:
    f = _ack_path(lane, ack_dir)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(acks, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, f)


def due(
    lane: str,
    own_tickets: Mapping[int, datetime | None] | list[int],
    *,
    now: datetime | None = None,
    path: Path | None = None,
    ack_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """([{ticket, request, why}] to cancel now, notes). `own_tickets` maps each of the lane's
    own resting orders to its setup time in UTC (None, or a bare list, when unreadable: such an
    order is never cancelled by `all`). Never raises: a lane pass must not die on a request
    file."""
    now = now or datetime.now(UTC)
    path = path or REQUEST_FILE
    ack_dir = ack_dir or ACK_DIR
    notes: list[str] = []
    try:
        reqs, bad = _requests(lane, now, path)
        if bad:
            return [], [bad]
        if not reqs:
            return [], []
        setup: dict[int, datetime | None] = (
            {int(t): v for t, v in own_tickets.items()}
            if isinstance(own_tickets, Mapping)
            else {int(t): None for t in own_tickets}
        )
        own = set(setup)
        try:
            acks = _load_acks(lane, ack_dir)
        except AcksUnreadable as exc:
            return [], [f"{exc}; nothing cancelled until a person looks at it"]
        out: list[dict[str, Any]] = []
        changed = False
        for r in reqs:
            a = acks.setdefault(r["id"], {"done": []})
            if r.get("all") is True:
                if "seen_at" not in a:
                    a["seen_at"] = now.isoformat()
                    changed = True
                bound = _when(r.get("placed_before"))
                seen = _when(a.get("seen_at"))
                if bound is None:
                    notes.append(f"request {r['id']}: all without placed_before; nothing cancelled")
                    continue
                cutoff = min(bound, seen) if seen is not None else bound
                wanted = []
                for t in sorted(own):
                    at = setup[t]
                    if at is None:
                        notes.append(
                            f"request {r['id']}: order {t} has no readable setup time; all "
                            "leaves it (name it in tickets)"
                        )
                    elif at <= cutoff:
                        wanted.append(t)
            else:
                wanted = [int(t) for t in r.get("tickets") or []]
            for t in wanted:
                if t in a["done"]:
                    continue
                if t not in own:
                    note = f"request {r['id']}: ticket {t} is not a resting order of this lane"
                    if note not in a.get("notes", []):
                        a.setdefault("notes", []).append(note)
                        changed = True
                    notes.append(note)
                    continue
                out.append(
                    {
                        "ticket": t,
                        "request": r["id"],
                        "why": f"cancel requested ({r['id']}): {r.get('why') or 'no reason'}",
                    }
                )
        if changed:
            _save_acks(lane, acks, ack_dir)
        return out, notes
    except Exception as exc:  # never take the pass down
        return [], [f"cancel requests not read ({type(exc).__name__}: {exc})"]


def record(
    lane: str,
    request: str,
    ticket: int,
    ok: bool,
    *,
    ack_dir: Path | None = None,
    now: datetime | None = None,
) -> None:
    """Remember a ticket this lane cancelled (it is not re-sent) or failed to (it is retried)."""
    ack_dir = ack_dir or ACK_DIR
    try:
        acks = _load_acks(lane, ack_dir)
        a = acks.setdefault(request, {"done": []})
        if ok and int(ticket) not in a["done"]:
            a["done"].append(int(ticket))
        a.setdefault("log", []).append(
            {"ticket": int(ticket), "ok": bool(ok), "at": (now or datetime.now(UTC)).isoformat()}
        )
        a["log"] = a["log"][-50:]
        _save_acks(lane, acks, ack_dir)
    except Exception:
        pass
