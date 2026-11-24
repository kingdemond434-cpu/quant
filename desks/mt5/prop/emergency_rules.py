"""EMERGENCY KILL RULES: box-native, risk-reducing only (zuck 2026-11-24 23:15Z).

zuck lifted "a manual close of a live position needs his own words" ("u can do 4 bro trust in
emergency cases cuz i wont always be here 24 7"). The coordinator scoped it: closes and size cuts
only, never an open or an add, and the common cases built as AUTOMATIC rules on the box so nothing
waits on a Claude being awake. Every close is logged with its reason (`LOG`).

THE RULES (pure; `assess` returns what to close and why, the caller sends):
  NEAR_DAILY_LIMIT  equity is within EMERGENCY_ROOM_FRAC of the firm's daily-loss floor
                    (room <= 20% of the daily limit): flatten every desk position on the account
                    and stand down new risk for the firm's day. A daily breach loses the account;
                    E8's own stand-down measured that a floor inside the firm's takes breaches to
                    zero and costs nothing in time (prop/e8_guard.py, research/prop_barrier.py).
  NEAR_MAX_LOSS     the same against the firm's static maximum-loss floor.
  DUPLICATE         two or more desk positions with the same symbol, side, magic and comment (one
                    sleeve, one bar): every one but the oldest is closed. A duplicate is a runaway
                    send, never a sized decision.
  UNPROTECTED       a desk position with no broker-side stop older than UNPROTECTED_GRACE_S (the
                    entry attaches one and stop management never removes it): closed, because its
                    risk is unbounded and the book's risk is unmeasurable while it stands.

WHAT IT NEVER DOES: open, add, widen a stop, or touch a position that is not the desk's (its magic
is not in the caller's `desk_magics`). Missing inputs (no equity, no day start) skip the limit
rules and are reported; they never flatten on a guess.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LOG = DESK / "data" / "emergency_closes.jsonl"

#: Flatten when the room left to a firm floor is at or below this share of that limit.
EMERGENCY_ROOM_FRAC = 0.20
#: A position with no stop is given this long for the entry's stop to land before it is closed.
UNPROTECTED_GRACE_S = 120.0

NEAR_DAILY_LIMIT, NEAR_MAX_LOSS = "NEAR_DAILY_LIMIT", "NEAR_MAX_LOSS"
DUPLICATE, UNPROTECTED = "DUPLICATE", "UNPROTECTED"


@dataclass
class Assessment:
    flatten: bool = False
    stand_down: bool = False
    rule: str | None = None
    why: str = ""
    #: [(ticket, rule, why)] positions to close; on a flatten, every desk position.
    closes: list[tuple[int, str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"flatten": self.flatten, "stand_down": self.stand_down, "rule": self.rule,
                "why": self.why, "closes": [{"ticket": t, "rule": r, "why": w}
                                            for t, r, w in self.closes],
                "notes": self.notes}


def _side(p: Any) -> str:
    return "buy" if int(getattr(p, "type", -1)) == 0 else "sell"


def limit_rule(*, equity: float | None, day_start: float | None, initial: float,
               daily_frac: float, max_frac: float,
               room_frac: float = EMERGENCY_ROOM_FRAC) -> tuple[str | None, str]:
    """(rule, why) when equity is within `room_frac` of a firm floor, else (None, why)."""
    if equity is None or not initial > 0:
        return None, "equity or initial balance unreadable: limit rules skipped"
    static_floor = initial * (1.0 - max_frac)
    if equity - static_floor <= room_frac * max_frac * initial:
        return NEAR_MAX_LOSS, (f"equity {equity:,.2f} is {equity - static_floor:,.2f} above the "
                               f"max-loss floor {static_floor:,.2f} (<= {room_frac:.0%} of the "
                               f"{max_frac:.0%} limit)")
    if day_start is None:
        return None, "today's start balance unreadable: daily rule skipped"
    daily_limit = daily_frac * initial
    daily_floor = day_start - daily_limit
    if equity - daily_floor <= room_frac * daily_limit:
        return NEAR_DAILY_LIMIT, (f"equity {equity:,.2f} is {equity - daily_floor:,.2f} above "
                                  f"today's floor {daily_floor:,.2f} (<= {room_frac:.0%} of the "
                                  f"{daily_frac:.1%} daily limit)")
    return None, "within limits"


def assess(positions: Iterable[Any], *, desk_magics: Sequence[int], now_epoch: float,
           equity: float | None, day_start: float | None, initial: float,
           daily_frac: float, max_frac: float) -> Assessment:
    """What the emergency rules close this pass. Pure: reads position-like objects
    (ticket, symbol, type, magic, comment, sl, time) and numbers; sends nothing."""
    desk = [p for p in positions if int(getattr(p, "magic", 0) or 0) in set(desk_magics)]
    out = Assessment()
    rule, why = limit_rule(equity=equity, day_start=day_start, initial=initial,
                           daily_frac=daily_frac, max_frac=max_frac)
    if rule is None and why != "within limits":
        out.notes.append(why)
    if rule is not None:
        out.flatten = out.stand_down = True
        out.rule, out.why = rule, why
        out.closes = [(int(p.ticket), rule, why) for p in desk]
        return out
    groups: dict[tuple[str, str, int, str], list[Any]] = {}
    for p in desk:
        key = (str(p.symbol), _side(p), int(getattr(p, "magic", 0) or 0),
               str(getattr(p, "comment", "") or ""))
        groups.setdefault(key, []).append(p)
    closing: set[int] = set()
    for (sym, side, magic, comment), ps in groups.items():
        if len(ps) < 2:
            continue
        ps = sorted(ps, key=lambda q: (float(getattr(q, "time", 0) or 0), int(q.ticket)))
        for p in ps[1:]:
            w = (f"duplicate of #{int(ps[0].ticket)} ({sym} {side}, magic {magic}, "
                 f"comment {comment!r}): a runaway send")
            out.closes.append((int(p.ticket), DUPLICATE, w))
            closing.add(int(p.ticket))
    for p in desk:
        if int(p.ticket) in closing or float(getattr(p, "sl", 0.0) or 0.0) > 0:
            continue
        opened = float(getattr(p, "time", 0) or 0)
        if opened > 0 and now_epoch - opened < UNPROTECTED_GRACE_S:
            continue
        out.closes.append((int(p.ticket), UNPROTECTED,
                           f"{p.symbol} #{int(p.ticket)} has no broker-side stop "
                           f"({now_epoch - opened:.0f}s after entry): unbounded risk"))
    if out.closes:
        out.rule = ",".join(sorted({r for _, r, _ in out.closes}))
        out.why = f"{len(out.closes)} position(s) closed by the emergency rules"
    return out


def log_close(*, account: str, ticket: int, symbol: str, rule: str, why: str, ok: bool,
              armed: bool, now: datetime | None = None, path: Path | None = None,
              **extra: Any) -> None:
    """One line per emergency close, sent or shadow. Never raises into the pass."""
    row = {"at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
           "account": account, "ticket": int(ticket), "symbol": symbol, "rule": rule,
           "why": why, "ok": bool(ok), "armed": bool(armed), **extra}
    try:
        target = path or LOG
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError:
        pass
