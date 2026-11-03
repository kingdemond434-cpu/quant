#!/usr/bin/env python3
"""Does every live account run the same mechanisms? A read-only census, never a decision.

A LIBRARY, NOT AN EXECUTABLE: its one clock is MT5-BoxHeartbeat, which imports it. By hand:
    python -c "import sys; sys.path.insert(0, 'desks/mt5/scripts'); import account_parity as a; \
print(a.refresh(force=True)['verdict'])"

WHY (zuck, 2026-11-03). Every live account -- E8, FTMO, Fusion, and any future one -- must run
IDENTICAL mechanisms. Only the firm's caps may differ (loss limits, profit caps, lot caps), and a
mechanism missing on one account is a defect, not a configuration. Nothing measured that: each
lane has its own report, and a mechanism wired on one account and absent (or silently failing) on
another showed up only when somebody read three logs side by side.

THE GRID. Rows are accounts, columns are mechanisms (MECHANISMS). Each cell carries

    present     the mechanism is wired in that account's code or config (True / False), or None
                when the source cannot be read. Read as TEXT: nothing here imports a lane, so
                MetaTrader5 is never imported or initialised and no order is ever touched
    last_fired  the newest UTC instant the mechanism acted, from that lane's own log tail,
                intent journal, pass report or ledger -- carried forward from the previous
                report, so a fire older than the tail is not forgotten
    evidence    file:line for the wiring and the path the firing was read from

    RED         absent; or, for a per-trade mechanism (`compare_fire`), never fired inside
                LOOKBACK_DAYS while the same mechanism fired on another account in that window
    UNMEASURED  the wiring or the firing source cannot be read (missing log, torn JSON, the time
                budget ran out). NEVER GREEN (L1.28a): an unread cell is not a passing one
    GREEN       otherwise

CONDITIONAL RAILS ARE NOT FIRE-COMPARED. The equity-floor rail, the daily-loss breaker and the
opposite-side fence act only when their condition occurs; E8 tripping its daily breaker on a bad
day is no evidence that FTMO's should have tripped. Their last trip is reported, and they go RED
only when absent, UNMEASURED only when unreadable.

A MANUAL CLOSE IS AN EVENT, NOT A DEFECT (zuck, 2026-11-03). Each account's exits in the window
are read from its fills ledger and labelled: an exit with no request from our side (`closed_by` /
`exit_reason` "manual": a person's desktop, mobile or web close) is "manual". A trade a person
closed never gave the floor or the trail a chance to act, so when every exit an account had in
the window is manual, its silent exit-management cells (EXIT_MECHANISMS) are GREEN with that
named -- a manual exit never turns a cell RED. One desk- or venue-closed exit and the rule binds.

FIRM CAPS ARE LISTED, NOT JUDGED (`allowed_differences`): each account's loss limits, profit cap
and lot caps, read from the constants that enforce them, so a reader sees what is SUPPOSED to
differ next to what does.

BOUNDED. Only the last TAIL_BYTES of each log or journal is read, the whole pass has BUDGET_S,
and whatever the budget does not reach is UNMEASURED. `refresh` re-measures at most every
REMEASURE_MIN and never raises.

Writes `desks/mt5/reports/ACCOUNT_PARITY.json` (a state path; the box may write it), published to
LIVE every 15 minutes by `sync_shadow_to_git.ps1`. No account number is read or written.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent

OUT = BASE / "reports" / "ACCOUNT_PARITY.json"
#: The heartbeat runs every 5 minutes; the grid is re-measured at most this often.
REMEASURE_MIN = 15.0
#: The whole measurement rides a 5-minute task with a 2-minute limit, next to other checks.
BUDGET_S = 8.0
#: Bytes read from the end of each log or journal. Never the whole file.
TAIL_BYTES = 1_500_000
#: The window the per-trade fire comparison looks back over.
LOOKBACK_DAYS = 14

ACCOUNTS = ("e8", "ftmo", "fusion")
#: (key, label, compare_fire). compare_fire: a per-trade mechanism, judged against its peers.
MECHANISMS: tuple[tuple[str, str, bool], ...] = (
    ("entry", "entry", True),
    ("breakeven_floor", "break-even floor (+0.85R)", True),
    ("atr_trail", "ATR chandelier trail", True),
    ("stall_tighten", "trail stall tighten (k=4 -> k=1)", True),
    ("equity_floor_rail", "deadman / equity-floor rail", False),
    ("daily_loss_breaker", "daily-loss breaker", False),
    ("opposite_side_fence", "cross-account opposite-side fence", False),
    ("loss_learner", "loss-loop hook (loss_learner)", True),
    ("combiner", "combiner hook", True),
    ("sizing_source", "sizing source", False),
)

E8_GOLD = "desks/mt5/prop/e8_gold.py"
E8_GUARD = "desks/mt5/prop/e8_guard.py"
FTMO = "desks/mt5/prop/ftmo_follower.py"
GATEWAY = "desks/mt5/mt5desk/gateway.py"
PM = "desks/mt5/mt5desk/position_manager.py"
DCORE = "desks/mt5/mt5desk/decision_core.py"
DEADMAN = "desks/mt5/proposals/fusion_deadman.py"
LEARNER = "desks/mt5/research/loss_learner.py"
HOURLY = "desks/mt5/research/hourly_cycle.py"

E8_LOG = "desks/mt5/logs/e8_gold.log"
E8_INTENTS = "desks/mt5/data/e8_gold_intents.jsonl"
FTMO_LOG = "desks/mt5/logs/ftmo_follower.log"
FTMO_INTENTS = "desks/mt5/data/ftmo_follower_intents.jsonl"
FTMO_REPORT = "desks/mt5/reports/FTMO_FOLLOWER.json"
GW_LOG = "desks/mt5/logs/gateway.log"
FUSION_RAILS = "desks/mt5/data/fusion_book_rails.jsonl"
DEADMAN_LOGS = ("desks/mt5/logs/fusion_deadman.log", "desks/mt5/logs/MT5-FusionDeadmanLive.log")
LEARNER_REPORT = "desks/mt5/reports/LOSS_LEARNER.json"
CERT_BOOK = "desks/mt5/data/CERT_BOOK_LIVE.json"
MINLOT = "desks/mt5/data/MINLOT_OVERRIDE.json"

PROP_LEDGER = "desks/mt5/data/live_ledger_prop.jsonl"
FUSION_LEDGER = "desks/mt5/data/live_ledger.jsonl"
#: Where each account's closed trades are read from: (ledger, book filter or None).
EXIT_LEDGERS = {"e8": (PROP_LEDGER, "e8"), "ftmo": (PROP_LEDGER, "ftmo"),
                "fusion": (FUSION_LEDGER, None)}
#: The mechanisms that act on an open trade's exit, which a manual close pre-empts.
EXIT_MECHANISMS = ("breakeven_floor", "atr_trail", "stall_tighten")
#: Exits listed per account in the report.
EXITS_SHOWN = 12

FENCE_RAILS = ("cross_account_opposite", "gold_oco_direction_lock")
COMBINER_RX = r"weak_signal_book|combiner"
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)")
_OK_RC = r"retcode=1000[89]\b"
_E8_BE = r"\] RATCHET position .*break-even floor"
_E8_STALL = r"\] RATCHET position .*stalled: chandelier"
_E8_DAILY = r"guard (?:STOOD_DOWN|BREACHED: .*today's floor)"
_GW_BE = r"MODIFY \[BREAK-EVEN FLOOR\].*" + _OK_RC


class OutOfBudget(Exception):
    """The pass's time budget is spent: every cell not yet read is UNMEASURED."""


class Ctx:
    """One pass's reads: a root, a deadline and a cache, so each file is read at most once."""

    def __init__(self, root: Path, deadline: float) -> None:
        self.root, self.deadline = root, deadline
        self._text: dict[str, str | None] = {}
        self._tail: dict[str, list[str] | None] = {}

    def _tick(self) -> None:
        if time.monotonic() > self.deadline:
            raise OutOfBudget

    def text(self, rel: str) -> str | None:
        """A source file, whole (code and config are small). None when unreadable."""
        if rel not in self._text:
            self._tick()
            try:
                self._text[rel] = (self.root / rel).read_text("utf-8", errors="replace")
            except OSError:
                self._text[rel] = None
        return self._text[rel]

    def tail(self, rel: str) -> list[str] | None:
        """The last TAIL_BYTES of a log or journal, as whole lines. None when unreadable."""
        if rel not in self._tail:
            self._tick()
            p = self.root / rel
            try:
                with p.open("rb") as fh:
                    size = fh.seek(0, os.SEEK_END)
                    start = max(0, size - TAIL_BYTES)
                    fh.seek(start)
                    raw = fh.read(TAIL_BYTES)
                lines = raw.decode("utf-8", errors="replace").splitlines()
                self._tail[rel] = lines[1:] if start > 0 else lines
            except OSError:
                self._tail[rel] = None
        return self._tail[rel]

    def json(self, rel: str) -> Any:
        txt = self.text(rel)
        if txt is None:
            return None
        try:
            return json.loads(txt)
        except ValueError:
            return None


def _parse_ts(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------ presence (code / config)

def wired(ctx: Ctx, *needs: tuple[str, str]) -> tuple[bool | None, list[str]]:
    """Every (file, regex) must match. (True, [file:line...]); (False, [what is missing]); or
    (None, [unreadable file]) -- unreadable is not absent."""
    where: list[str] = []
    for rel, rx in needs:
        txt = ctx.text(rel)
        if txt is None:
            return None, [f"{rel} unreadable"]
        m = re.search(rx, txt, re.M)
        if m is None:
            return False, [f"{rel}: no match for /{rx}/"]
        where.append(f"{rel}:{txt.count(chr(10), 0, m.start()) + 1}")
    return True, where


# ------------------------------------------------------------------ firing (logs / ledgers)

Fire = tuple[str, datetime | None, str]   # (MEASURED | UNMEASURED, newest fire, source)


def log_fire(ctx: Ctx, rels: str | tuple[str, ...], rx: str) -> Fire:
    """Newest line in any of `rels` matching `rx`, by its own leading ISO stamp."""
    rels = (rels,) if isinstance(rels, str) else rels
    pat = re.compile(rx)
    best: datetime | None = None
    read: list[str] = []
    for rel in rels:
        lines = ctx.tail(rel)
        if lines is None:
            continue
        read.append(rel)
        for ln in reversed(lines):
            if pat.search(ln):
                m = _TS.match(ln)
                t = _parse_ts(m.group(1)) if m else None
                if t is not None:
                    best = t if best is None or t > best else best
                    break
    if not read:
        return "UNMEASURED", None, f"{' / '.join(rels)} unreadable"
    return "MEASURED", best, " / ".join(read)


def jsonl_fire(ctx: Ctx, rel: str, pred: Callable[[dict[str, Any]], bool]) -> Fire:
    """Newest row of a journal satisfying `pred`, by its `at` stamp."""
    lines = ctx.tail(rel)
    if lines is None:
        return "UNMEASURED", None, f"{rel} unreadable"
    best: datetime | None = None
    for ln in lines:
        with contextlib.suppress(ValueError, TypeError):
            row = json.loads(ln)
            if isinstance(row, dict) and pred(row):
                t = _parse_ts(row.get("at"))
                if t is not None and (best is None or t > best):
                    best = t
    return "MEASURED", best, rel


def report_action_fire(ctx: Ctx, rel: str, pred: Callable[[dict[str, Any]], bool]) -> Fire:
    """A pass report's `actions`: the report's own `at` when any action satisfies `pred`. Only
    the latest pass is on disk; the carried `last_fired` keeps older ones."""
    doc = ctx.json(rel)
    if not isinstance(doc, dict):
        return "UNMEASURED", None, f"{rel} absent or unreadable"
    hit = any(isinstance(a, dict) and pred(a) for a in doc.get("actions") or [])
    return "MEASURED", _parse_ts(doc.get("at")) if hit else None, f"{rel} actions"


def learner_fire(ctx: Ctx, book: str) -> Fire:
    """loss_learner measured this book's ledger in its last report."""
    doc = ctx.json(LEARNER_REPORT)
    if not isinstance(doc, dict):
        return "UNMEASURED", None, f"{LEARNER_REPORT} absent or unreadable"
    state = str((doc.get("books") or {}).get(book) or "")
    t = _parse_ts(doc.get("generated_at")) if state.startswith("MEASURED") else None
    return "MEASURED", t, f"{LEARNER_REPORT} books.{book}: {state[:120] or 'not named'}"


def no_fire(_ctx: Ctx) -> Fire:
    return "MEASURED", None, "no firing source: nothing wired to fire"


# ------------------------------------------------------------------ the probes

def _ftmo_ratchet(a: dict[str, Any]) -> bool:
    return a.get("act") == "ratchet_stop" and a.get("ok") is True and not a.get("shadow")


def _rail_row(rails: tuple[str, ...]) -> Callable[[dict[str, Any]], bool]:
    return lambda r: str(r.get("rail") or "") in rails


def _ftmo_guard(prefix: str) -> Callable[[dict[str, Any]], bool]:
    return lambda r: r.get("reason") == "loss_guard" and str(r.get("why") or "").startswith(prefix)


Probe = tuple[tuple[tuple[str, str], ...], Callable[[Ctx], Fire]]

PROBES: dict[str, dict[str, Probe]] = {
    "e8": {
        "entry": (((E8_GOLD, r"\] PLACED \{side\}"),),
                  lambda c: log_fire(c, E8_LOG, r"\] (?:RE-)?PLACED ")),
        "breakeven_floor": (((E8_GOLD, r"cost_per_unit=E8_ROUND_TRIP_PER_PRICE_UNIT"),
                             (E8_GOLD, r"_pm\.ratchet\(")),
                            lambda c: log_fire(c, E8_LOG, _E8_BE)),
        "atr_trail": (((E8_GOLD, r"_pm\.ratchet\("),),
                      lambda c: log_fire(c, E8_LOG, r"\] RATCHET position .*chandelier k=")),
        "stall_tighten": (((E8_GOLD, r"_pm\.extreme_and_stall\("),),
                          lambda c: log_fire(c, E8_LOG, _E8_STALL)),
        "equity_floor_rail": (((E8_GOLD, r"e8_guard\.assess\("), (E8_GUARD, r"STATIC floor")),
                              lambda c: log_fire(c, E8_LOG, r"guard BREACHED: .*STATIC floor")),
        "daily_loss_breaker": (((E8_GOLD, r"e8_guard\.assess\("),
                                (E8_GUARD, r"^DAILY_DRAWDOWN = ")),
                               lambda c: log_fire(c, E8_LOG,
                                                  _E8_DAILY)),
        "opposite_side_fence": (((E8_GOLD, r"_xa\.opposite_block\("),),
                                lambda c: jsonl_fire(c, E8_INTENTS, _rail_row(FENCE_RAILS))),
        "loss_learner": (((LEARNER, r'"e8": "E8 book'), (HOURLY, r'"research/loss_learner\.py"')),
                         lambda c: learner_fire(c, "e8")),
        "combiner": (((E8_GOLD, COMBINER_RX),), no_fire),
        "sizing_source": (((E8_GOLD, r'load_cert_book\(CERT_BOOK_FILE, "e8"\)'),), no_fire),
    },
    "ftmo": {
        "entry": (((FTMO, r"def _place_locked\("),),
                  lambda c: log_fire(c, FTMO_LOG, r"\] SENT ")),
        # FTMO computes no stop of its own: it mirrors the stop E8 acknowledged (`mirrored_stop`)
        # through TRADE_ACTION_SLTP, so its floor, trail and stall are E8's, copied when they land.
        "breakeven_floor": (((FTMO, r"mirrored_stop\("), (FTMO, r"TRADE_ACTION_SLTP")),
                            lambda c: report_action_fire(c, FTMO_REPORT, _ftmo_ratchet)),
        "atr_trail": (((FTMO, r"mirrored_stop\("), (FTMO, r"TRADE_ACTION_SLTP")),
                      lambda c: report_action_fire(c, FTMO_REPORT, _ftmo_ratchet)),
        "stall_tighten": (((FTMO, r"mirrored_stop\("), (FTMO, r"TRADE_ACTION_SLTP")),
                          lambda c: report_action_fire(c, FTMO_REPORT, _ftmo_ratchet)),
        "equity_floor_rail": (((FTMO, r"^MAX_LOSS_FRAC = "), (FTMO, r"def loss_guard\(")),
                              lambda c: jsonl_fire(c, FTMO_INTENTS, _ftmo_guard("max loss"))),
        "daily_loss_breaker": (((FTMO, r"^ACCOUNT_TYPES = "), (FTMO, r"loss_guard\(float")),
                               lambda c: jsonl_fire(c, FTMO_INTENTS, _ftmo_guard("daily loss"))),
        "opposite_side_fence": (((FTMO, r"_oco\.gate\("),),
                                lambda c: jsonl_fire(c, FTMO_INTENTS,
                                                     lambda r: r.get("reason") == "gold_oco"
                                                     or str(r.get("rail") or "") in FENCE_RAILS)),
        "loss_learner": (((LEARNER, r'"ftmo": "FTMO allocator'),
                          (HOURLY, r'"research/loss_learner\.py"')),
                         lambda c: learner_fire(c, "ftmo")),
        "combiner": (((FTMO, COMBINER_RX),), no_fire),
        "sizing_source": (((FTMO, r'load_cert_book\(CERT_BOOK_FILE, "ftmo"\)'),), no_fire),
    },
    "fusion": {
        "entry": (((GATEWAY, r"def place_bracket\("), (GATEWAY, r"mt5\.order_send\(req\)")),
                  lambda c: log_fire(c, GW_LOG, r"ORDER \[[^\]]+\] \S+ -> " + _OK_RC)),
        "breakeven_floor": (((GATEWAY, r"cost_per_unit=cost_unit"), (GATEWAY, r"_pm\.ratchet\(")),
                            lambda c: log_fire(c, GW_LOG, _GW_BE)),
        "atr_trail": (((GATEWAY, r"_pm\.ratchet\("),),
                      lambda c: log_fire(c, GW_LOG, r"MODIFY sl .*" + _OK_RC + r".*chandelier k=")),
        "stall_tighten": (((GATEWAY, r"_pm\.extreme_and_stall\("),),
                          lambda c: log_fire(c, GW_LOG,
                                             r"MODIFY sl .*" + _OK_RC + r".*stalled: chandelier")),
        "equity_floor_rail": (((GATEWAY, r"fusion_deadman_armed\(\)"),
                               (DEADMAN, r"^EQUITY_FLOOR_EUR = ")),
                              lambda c: log_fire(c, DEADMAN_LOGS, r"HALT FILE WRITTEN")),
        "daily_loss_breaker": (((GATEWAY, r"fusion_daily_loss\(st"),),
                               lambda c: jsonl_fire(c, FUSION_RAILS,
                                                    _rail_row(("fusion_daily_loss",)))),
        "opposite_side_fence": (((GATEWAY, r"_xa\.opposite_block\("),),
                                lambda c: jsonl_fire(c, FUSION_RAILS, _rail_row(FENCE_RAILS))),
        "loss_learner": (((LEARNER, r'"fusion": "Fusion allocator'),
                          (HOURLY, r'"research/loss_learner\.py"')),
                         lambda c: learner_fire(c, "fusion")),
        "combiner": (((GATEWAY, COMBINER_RX),), no_fire),
        "sizing_source": (((GATEWAY, r'load_cert_book\(CERT_BOOK_FILE, "fusion"\)'),
                           (GATEWAY, r"MINLOT_OVERRIDE_FILE")), no_fire),
    },
}


def sizing_config(ctx: Ctx, account: str) -> tuple[bool | None, str]:
    """The sizing file each account's code reads: CERT_BOOK_LIVE.json's block for it (Fusion's
    gold window also through MINLOT_OVERRIDE.json). (present, source) -- None when unreadable."""
    book = ctx.json(CERT_BOOK)
    if not isinstance(book, dict):
        return None, f"{CERT_BOOK} absent or unreadable"
    if book.get("enabled") is not True:
        return False, f"{CERT_BOOK} enabled is not true"
    block = book.get(account)
    if not isinstance(block, dict):
        return False, f"{CERT_BOOK} has no {account} block"
    funded = {k: v for k, v in block.items() if isinstance(v, int | float) and v > 0}
    src = f"{CERT_BOOK} {account} block (funded: {funded or 'none'})"
    if account == "fusion":
        ml = ctx.json(MINLOT)
        if isinstance(ml, dict) and ml.get("enabled") is True:
            src += (f" + {MINLOT} (sleeves {ml.get('sleeves')}, target_risk "
                    f"{ml.get('target_risk')}, lot floor {ml.get('lot')})")
    return True, src


# ------------------------------------------------------------------ caps (allowed differences)

_CAPS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "e8": ((E8_GUARD, "DAILY_DRAWDOWN", "daily loss limit (fraction of start balance)"),
           (E8_GUARD, "STATIC_DRAWDOWN", "static max-loss floor"),
           (E8_GUARD, "DAILY_PROFIT_CAP", "daily profit cap"),
           (E8_GUARD, "STAND_DOWN", "voluntary stand-down inside the daily limit"),
           (DCORE, "E8_CERT_CEILING", "per-window risk ceiling")),
    "ftmo": ((FTMO, "ACCOUNT_TYPES", "daily loss limit by account type"),
             (FTMO, "MAX_LOSS_FRAC", "max loss"),
             (FTMO, "MAX_NOTIONAL_X", "lot cap (notional x equity)"),
             (FTMO, "REQUEST_BUDGET", "daily server-request budget"),
             (FTMO, "GAP_GUARD_H", "no entry this close to the market close (h)")),
    "fusion": ((DCORE, "FUSION_DAILY_LOSS_FRAC", "daily loss limit"),
               (DEADMAN, "DAILY_LOSS_PCT", "ruin rail daily loss"),
               (DEADMAN, "EQUITY_FLOOR_EUR", "ruin rail equity floor"),
               (DEADMAN, "MAX_OPEN_POSITIONS", "ruin rail max open positions")),
}


def caps(ctx: Ctx) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for acct, rows in _CAPS.items():
        out[acct] = []
        for rel, name, what in rows:
            txt = ctx.text(rel)
            m = re.search(rf"^{name} = (.+)$", txt or "", re.M)
            line = (txt or "").count("\n", 0, m.start()) + 1 if m else None
            out[acct].append({"cap": name, "what": what,
                              "value": m.group(1).split("#")[0].strip()[:120] if m else None,
                              "evidence": f"{rel}:{line}" if m else f"{rel}: not found"})
    return out


def shared_constants(ctx: Ctx) -> dict[str, Any]:
    """The position manager every account's stop goes through (FTMO by mirroring E8)."""
    txt = ctx.text(PM) or ""
    got = {}
    for name in ("BREAKEVEN_TRIGGER_R", "K_TREND", "K_STALLED", "STALL_BARS"):
        m = re.search(rf"^{name} = (\S+)", txt, re.M)
        got[name] = m.group(1) if m else None
    got["evidence"] = PM if txt else f"{PM} unreadable"
    return got


# ------------------------------------------------------------------ exits (manual is an event)

def exit_label(row: dict[str, Any]) -> str:
    """"manual" for an exit nobody on the desk requested; else the ledger's own label."""
    by = str(row.get("closed_by") or "").lower()
    why = str(row.get("exit_reason") or "").lower()
    if "manual" in (by, why):
        return "manual"
    return why or by or "unlabelled"


def exits(ctx: Ctx, account: str, now: datetime) -> dict[str, Any]:
    """The account's exits inside LOOKBACK_DAYS, newest first, labelled. Time, price and label
    only: no account, login or ticket is copied out of a ledger."""
    rel, book = EXIT_LEDGERS[account]
    lines = ctx.tail(rel)
    if lines is None:
        return {"read": "UNMEASURED", "source": f"{rel} unreadable", "rows": []}
    since = now - timedelta(days=LOOKBACK_DAYS)
    rows: list[dict[str, Any]] = []
    for ln in lines:
        with contextlib.suppress(ValueError, TypeError):
            r = json.loads(ln)
            if not isinstance(r, dict) or (book is not None and r.get("book") != book):
                continue
            t = _parse_ts(r.get("exit_time") or r.get("time"))
            if t is None or t < since or t > now + timedelta(minutes=5):
                continue
            rows.append({"at": _iso(t), "price": r.get("fill_price"), "label": exit_label(r)})
    rows.sort(key=lambda x: str(x["at"]), reverse=True)
    labels = [x["label"] for x in rows]
    return {"read": "MEASURED", "source": rel + (f" book={book}" if book else ""),
            "n": len(rows), "manual": labels.count("manual"),
            "all_manual": bool(rows) and all(lb == "manual" for lb in labels),
            "rows": rows[:EXITS_SHOWN]}


# ------------------------------------------------------------------ the grid

def _cell(ctx: Ctx, account: str, mech: str, prev: dict[str, Any]) -> dict[str, Any]:
    needs, fire = PROBES[account][mech]
    present, where = wired(ctx, *needs)
    cell: dict[str, Any] = {"present": present, "evidence": {"code": where}}
    if mech == "sizing_source" and present:
        present, src = sizing_config(ctx, account)
        cell["present"] = present
        cell["source"] = src
    status, t, source = fire(ctx)
    cell["evidence"]["fired_from"] = source
    carried = _parse_ts(prev.get("last_fired"))
    best = max((x for x in (t, carried) if x is not None), default=None)
    cell["last_fired"] = _iso(best)
    cell["carried"] = best is not None and best == carried and t != carried
    cell["fire_read"] = status
    return cell


def judge(grid: dict[str, dict[str, dict[str, Any]]], now: datetime,
          exits_by: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Set each cell's verdict in place; return the RED cells with their reasons. A silent
    exit-management cell on an account whose every exit in the window was manual is GREEN."""
    exits_by = exits_by or {}
    since = now - timedelta(days=LOOKBACK_DAYS)
    reds: list[dict[str, Any]] = []
    for mech, _label, compare in MECHANISMS:
        fired_peers = {}
        for acct, row in grid.items():
            c = row.get(mech) or {}
            t = _parse_ts(c.get("last_fired"))
            if c.get("present") is True and t is not None and t >= since:
                fired_peers[acct] = c["last_fired"]
        for acct, row in grid.items():
            c = row[mech]
            if c.get("verdict") == "UNMEASURED":
                continue
            if c.get("present") is False:
                c["verdict"], c["why"] = "RED", "absent: " + "; ".join(
                    c["evidence"].get("code") or []) + (
                    f"; {c['source']}" if c.get("source") else "")
            elif c.get("present") is None or c.get("fire_read") != "MEASURED":
                c["verdict"] = "UNMEASURED"
                parts = list(c["evidence"].get("code") or []) if c.get("present") is None else []
                if c.get("fire_read") != "MEASURED":
                    parts.append(str(c["evidence"].get("fired_from")))
                c["why"] = "unreadable: " + "; ".join(parts)
            elif compare and acct not in fired_peers and set(fired_peers) - {acct}:
                ex = exits_by.get(acct) or {}
                if mech in EXIT_MECHANISMS and ex.get("all_manual"):
                    c["verdict"] = "GREEN"
                    c["why"] = (f"silent in {LOOKBACK_DAYS}d, but all {ex.get('n')} exit(s) in "
                                "the window were manual closes: an event, not a defect")
                    c["manual_exit"] = True
                    continue
                c["verdict"] = "RED"
                c["why"] = (f"never fired in {LOOKBACK_DAYS}d while it fired on "
                            + ", ".join(f"{a} at {t}" for a, t in sorted(fired_peers.items())))
            else:
                c["verdict"], c["why"] = "GREEN", None
            if c["verdict"] == "RED":
                reds.append({"account": acct, "mechanism": mech, "why": c["why"]})
    return reds


def measure(now: float | None = None, *, root: Path = ROOT, prev: dict[str, Any] | None = None,
            budget_s: float = BUDGET_S) -> dict[str, Any]:
    t = time.time() if now is None else now
    dt = datetime.fromtimestamp(t, tz=UTC)
    prev_grid = (prev or {}).get("grid") if isinstance((prev or {}).get("grid"), dict) else {}
    ctx = Ctx(root, time.monotonic() + budget_s)
    grid: dict[str, dict[str, dict[str, Any]]] = {}
    out_of_budget = False
    for acct in ACCOUNTS:
        grid[acct] = {}
        for mech, _label, _cmp in MECHANISMS:
            p = ((prev_grid.get(acct) or {}).get(mech) or {}) if isinstance(prev_grid, dict) else {}
            if out_of_budget:
                grid[acct][mech] = {"present": None, "last_fired": p.get("last_fired"),
                                    "evidence": {}, "verdict": "UNMEASURED",
                                    "why": f"time budget {budget_s:g}s spent before this cell"}
                continue
            try:
                grid[acct][mech] = _cell(ctx, acct, mech, p)
            except OutOfBudget:
                out_of_budget = True
                grid[acct][mech] = {"present": None, "last_fired": p.get("last_fired"),
                                    "evidence": {}, "verdict": "UNMEASURED",
                                    "why": f"time budget {budget_s:g}s spent on this cell"}
    exits_by: dict[str, dict[str, Any]] = {}
    for acct in ACCOUNTS:
        try:
            exits_by[acct] = exits(ctx, acct, dt)
        except OutOfBudget:
            exits_by[acct] = {"read": "UNMEASURED", "source": "time budget spent", "rows": []}
    reds = judge(grid, dt, exits_by)
    try:
        allowed = caps(ctx)
        shared = shared_constants(ctx)
    except OutOfBudget:
        allowed, shared = {}, {"evidence": "time budget spent"}
    verdicts = [c["verdict"] for row in grid.values() for c in row.values()]
    verdict = ("RED" if "RED" in verdicts else
               "UNMEASURED" if "UNMEASURED" in verdicts or not verdicts else "GREEN")
    return {"measured_at": _iso(dt), "verdict": verdict,
            "counts": {v: verdicts.count(v) for v in ("GREEN", "RED", "UNMEASURED")},
            "red": reds,
            "unmeasured": [{"account": a, "mechanism": m, "why": c.get("why")}
                           for a, row in grid.items() for m, c in row.items()
                           if c["verdict"] == "UNMEASURED"],
            "accounts": list(ACCOUNTS),
            "mechanisms": {m: {"label": lab, "fire_compared": cmp} for m, lab, cmp in MECHANISMS},
            "lookback_days": LOOKBACK_DAYS, "grid": grid, "exits": exits_by,
            "allowed_differences": allowed, "shared_position_manager": shared,
            "budget": {"budget_s": budget_s, "tail_bytes": TAIL_BYTES,
                       "spent": out_of_budget},
            "rule": ("every live account runs identical mechanisms; only firm caps differ. RED: "
                     "absent, or a per-trade mechanism silent while it fired on another account "
                     "in the lookback. UNMEASURED is never GREEN. Read-only: no lane is imported "
                     "and no order is touched")}


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.name}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(out)


def refresh(now: float | None = None, *, out: Path = OUT, root: Path = ROOT,
            force: bool = False) -> dict[str, Any]:
    """Re-measure when the report is older than REMEASURE_MIN, write it. NEVER RAISES: a crash is
    an UNMEASURED report, never a missing one that reads as nothing wrong."""
    t = time.time() if now is None else now
    prev: dict[str, Any] = {}
    with contextlib.suppress(OSError, ValueError):
        loaded = json.loads(out.read_text("utf-8"))
        prev = loaded if isinstance(loaded, dict) else {}
    at = _parse_ts(prev.get("measured_at"))
    if not force and at is not None and 0 <= (t - at.timestamp()) / 60.0 < REMEASURE_MIN:
        return prev
    try:
        doc = measure(t, root=root, prev=prev)
    except Exception as exc:
        doc = {"measured_at": _iso(datetime.fromtimestamp(t, tz=UTC)), "verdict": "UNMEASURED",
               "problems": [f"measurement crashed: {type(exc).__name__}: {str(exc)[:200]}"],
               "grid": prev.get("grid") or {}}
    with contextlib.suppress(OSError):
        write(doc, out)
    return doc
