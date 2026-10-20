"""E8 GOLD PLACEMENT EVIDENCE -- which host ran the pass, and what each due window decided.

WHY THIS EXISTS (measured on the trading box 2026-10-20). `scripts/check_placement_interlock.py`
reads `desks/mt5/data/decision_ledger.jsonl`, and only the Fusion gateway writes that file (its
last row was 10-16). `prop/e8_gold.py` wrote its state and its pass report and nothing else, so
an E8 window that stopped placing was invisible to the one fence built to see a silent halt, and
no record anywhere said WHICH machine had sent the E8 gold orders -- the question CLAUDE.md's
two-box history keeps making expensive.

TWO FILES, BOTH OWNED BY THIS LANE AND NEVER BY THE GATEWAY:

  `data/e8_gold_heartbeat.json`   rewritten on EVERY pass, flat or not, failed or not: the
                                  `libs/ops/host_identity` verdict, hostname, machine id, the pass
                                  time, its status and the account. One small file, so its age is
                                  the lane's age.
  `data/e8_decision_ledger.jsonl` one row per DECISION, never per pass: a due window's outcome
                                  (PLACED / WOULD_PLACE / DEFERRED / SKIPPED), a stable reason
                                  code, the prose why, its window, lot and risk_usd, attributed to
                                  `lane: e8_gold` and the venue account so no reader can mix it
                                  with Fusion's rows. Separate from the gateway's ledger because
                                  two processes appending to one file is a second writer to a
                                  record the gateway owns.

WHY ROWS ONLY AT DECISION POINTS. The pass runs every five minutes, and the interlock's breach (a)
counts consecutive not-taken rows sharing one reason. A per-pass row would turn a legitimate
one-gold-at-a-time deferral -- which can hold a window for hours while an earlier trade's stop is
short of break-even -- into thirty identical rows, i.e. a false halt. So a row is written when a
window's (outcome, reason) for the server day CHANGES (`state["evidence"]`, emptied by the
rollover), and a pass with no window due writes nothing at all. The fence then judges this lane
in decisions per server day, not rows per minute (see `E8_*` in the fence).

FAIL SAFE. Nothing here may block or alter a placement: every public function returns None (or
an empty list) instead of raising, logs what it could not write, and the placement code calls it
only after the orders have been decided. A failed ledger write leaves the dedupe mark unset, so
the next pass writes the row again -- a duplicate is harmless to the fence, a loss is not.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LANE = "e8_gold"
DECISIONS_NAME = "e8_decision_ledger.jsonl"
HEARTBEAT_NAME = "e8_gold_heartbeat.json"
#: Tests redirect both files here, exactly as MT5_ORDER_DOOR_DIR redirects the order door's.
DIR_ENV = "E8_EVIDENCE_DIR"
UNMEASURED = "UNMEASURED"

# OUTCOMES. Only PLACED put an order at the venue; the fence reads `taken` from it.
PLACED = "PLACED"
WOULD_PLACE = "WOULD_PLACE"
DEFERRED = "DEFERRED"
SKIPPED = "SKIPPED"

# REASON CODES -- stable, short, never prose, because the fence's run is "consecutive rows sharing
# one reason" and a reason carrying position ids or dollar figures would never repeat. The prose
# rides beside it in `why`. `scripts/check_placement_interlock.py` classifies every code (pinned
# by tests/governance/test_placement_interlock_fence.py).
R_PLACED = "placed"
R_SHADOW = "shadow_unarmed"
R_VENUE_REJECTED = "venue_rejected"
R_LEGS_UNAVAILABLE = "legs_unavailable"
R_UNSIZEABLE = "unsizeable"
R_KELLY_ZERO = "kelly_zero"
R_ONE_AT_RISK = "one_at_risk"
R_RISK_BUDGET = "risk_budget"
R_SIDE_UNREADABLE = "side_unreadable"
R_RISK_UNMEASURABLE = "risk_unmeasurable"
R_EQUITY_UNREADABLE = "equity_unreadable"
R_GUARD_UNREADABLE = "guard_unreadable"
R_POSITIONS_UNREADABLE = "positions_unreadable"
#: The guard's own verdicts, as `guard_<verdict>` (e8_guard.Verdict, lower-cased).
GUARD_PREFIX = "guard_"


def _dir() -> Path:
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else DESK / "data"


def decisions_path() -> Path:
    return _dir() / DECISIONS_NAME


def heartbeat_path() -> Path:
    return _dir() / HEARTBEAT_NAME


def _say(log: Callable[[str], None] | None, msg: str) -> None:
    if log is None:
        return
    with contextlib.suppress(Exception):
        log(msg)


def host_block() -> dict[str, Any]:
    """This machine through `libs/ops/host_identity`, the helper every fence shares. Never raises:
    an identity that cannot be read is recorded as UNMEASURED, never guessed from a label."""
    try:
        from libs.ops import host_identity
        ident = host_identity.identify()
        return {"verdict": ident.verdict, "hostname": ident.hostname,
                "machine_id": ident.machine_id,
                "recorded_machine_id": ident.recorded_machine_id,
                "may_be_trading": ident.may_be_trading, "why": ident.why}
    except Exception as exc:
        return {"verdict": UNMEASURED, "hostname": UNMEASURED, "machine_id": UNMEASURED,
                "why": f"host_identity unavailable ({type(exc).__name__})"}


def account_label(venue: Any) -> str:
    """The venue account this lane trades, as `tradelocker:<id>`, or UNMEASURED. Read from the SDK
    handle's own attributes; never a credential, never a call that could raise into the pass."""
    try:
        api = venue._api
    except Exception:
        return UNMEASURED
    for attr in ("account_id", "acc_num"):
        try:
            value = getattr(api, attr, None)
        except Exception:
            continue
        if isinstance(value, (int, str)) and str(value).strip() not in ("", "0"):
            return f"tradelocker:{str(value).strip()}"
    return UNMEASURED


class Decisions:
    """What each due window decided on this pass, collected while the pass runs.

    `note` never raises: it is called from inside the placement block, and a bookkeeping error
    there must cost a row, never an order. `risk_of(window)` supplies the window's planned risk in
    USD for a row that never reached sizing (a deferral)."""

    def __init__(self, risk_of: Callable[[str], float | None] | None = None) -> None:
        self.rows: list[dict[str, Any]] = []
        self._risk_of = risk_of

    def note(self, window: str, outcome: str, reason: str, why: str = "", *,
             lot: float | None = None, risk_usd: float | None = None) -> None:
        try:
            risk = risk_usd
            if risk is None and self._risk_of is not None:
                risk = self._risk_of(window)
            self.rows.append({
                "window": str(window), "outcome": str(outcome), "reason": str(reason),
                "taken": outcome == PLACED, "why": str(why or "")[:300],
                "lot": float(lot) if lot is not None else None,
                "risk_usd": round(float(risk), 2) if risk is not None else None,
            })
        except Exception:
            pass

    def windows(self) -> set[str]:
        return {r["window"] for r in self.rows}


def stand_down_reason(equity: float, guard_decision: Any, doc: dict[str, Any]) -> str:
    """Why `run` placed nothing this pass, as a reason code, derived after the fact from what the
    pass already recorded -- the guard block itself is not touched. First cause wins: an equity
    the venue would not state, a guard that raised, the guard's verdict, the position book."""
    try:
        if not equity > 0:
            return R_EQUITY_UNREADABLE
        if guard_decision is None:
            return R_GUARD_UNREADABLE
        if not guard_decision.may_open:
            return GUARD_PREFIX + str(guard_decision.verdict.value).lower()
        if doc.get("positions_unreadable"):
            return R_POSITIONS_UNREADABLE
    except Exception:
        pass
    return R_GUARD_UNREADABLE


def window_outcome(legs: dict[str, dict[str, Any]], failed: dict[str, dict[str, Any]], *,
                   armed: bool, unsizeable: bool) -> tuple[str, str, str, float | None]:
    """(outcome, reason, why, lot) for a window that reached the leg loop. Pure.

    PLACED when an armed pass sent at least one leg; WOULD_PLACE for the same in shadow; DEFERRED
    when every leg the venue was sent failed (`_retry_failed_legs` re-sends it while the window
    holds); otherwise SKIPPED -- a leg the sizer could not size, or no leg available at all (the
    level is already through the price, or the one legal leg would trade against the book).
    Called inside the placement loop, so a malformed leg reads as an unknown lot, never a raise."""
    try:
        lots = [float(v.get("lot") or 0.0) for v in (*legs.values(), *failed.values())]
        lot: float | None = max(lots) if lots else None
    except Exception:
        lot = None
    if legs and armed:
        return PLACED, R_PLACED, f"sent {', '.join(sorted(legs))}", lot
    if legs:
        return WOULD_PLACE, R_SHADOW, f"shadow: would send {', '.join(sorted(legs))}", lot
    if failed:
        first = next(iter(failed.values()), {})
        why = first.get("why") if isinstance(first, dict) else None
        return DEFERRED, R_VENUE_REJECTED, str(why or "venue refused"), lot
    if unsizeable:
        return SKIPPED, R_UNSIZEABLE, "the sizer returned no lot for this window's risk", 0.0
    return SKIPPED, R_LEGS_UNAVAILABLE, "no leg of the bracket was available to send", None


def pending_rows(decided: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    """The decisions that are NEW for today: a window's (outcome, reason) that differs from the
    last one recorded for it on this server day. Pure. `state["evidence"]` is window ->
    "OUTCOME:reason"; the rollover builds a fresh state, so a new day starts with none."""
    raw = state.get("evidence")
    seen: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out: list[dict[str, Any]] = []
    for row in decided:
        key = f"{row.get('outcome')}:{row.get('reason')}"
        if seen.get(str(row.get("window"))) == key:
            continue
        out.append(row)
    return out


def record_decisions(decided: Decisions | list[dict[str, Any]], state: dict[str, Any], *,
                     now: datetime, server_date: str, account: str, armed: bool,
                     host: dict[str, Any], symbol: str = "XAUUSD",
                     log: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    """Append this pass's NEW decisions to the lane's ledger and mark them in `state`. Returns the
    rows written ([] when none were new or the write failed). Never raises."""
    try:
        rows = decided.rows if isinstance(decided, Decisions) else list(decided)
        new = pending_rows(rows, state)
        if not new:
            return []
        stamp = now.isoformat(timespec="seconds")
        lines: list[dict[str, Any]] = []
        for row in new:
            sleeve = f"{LANE}:{row['window']}"
            lines.append({
                "decided_at": stamp, "lane": LANE, "account": account,
                "sleeve": sleeve, "strategy_id": sleeve, "symbol": symbol,
                "server_date": server_date, "armed": bool(armed),
                "host": host.get("hostname"), "machine_id": host.get("machine_id"),
                "host_verdict": host.get("verdict"), **row,
            })
        path = decisions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r, default=str) + "\n" for r in lines))
    except Exception as exc:
        _say(log, f"E8 DECISION EVIDENCE WRITE FAILED ({type(exc).__name__}: {exc}); "
                  "placement unaffected, the rows are re-tried next pass")
        return []
    try:
        marks = state.setdefault("evidence", {})
        for row in new:
            marks[row["window"]] = f"{row['outcome']}:{row['reason']}"
    except Exception:
        pass
    return lines


def write_heartbeat(status: str, *, at: datetime, armed: bool, account: str = UNMEASURED,
                    host: dict[str, Any] | None = None, extra: dict[str, Any] | None = None,
                    log: Callable[[str], None] | None = None) -> dict[str, Any] | None:
    """Rewrite the lane's heartbeat: this pass happened, on this host, with this result. Written
    on every pass, including a flat one and one whose connection failed. Never raises."""
    try:
        doc: dict[str, Any] = {
            "at": at.isoformat(timespec="seconds"), "lane": LANE, "status": str(status),
            "armed": bool(armed), "account": account,
            "host": host if host is not None else host_block(),
        }
        doc.update(extra or {})
        path = heartbeat_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
        return doc
    except Exception as exc:
        _say(log, f"E8 heartbeat write failed ({type(exc).__name__}: {exc}); pass unaffected")
        return None
