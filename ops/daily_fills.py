"""DID EACH ACCOUNT FILL TODAY -- one verdict per account per market day, read off the box's files.

WHY (principal, 2026-11-18). Fusion, E8 and FTMO are built to trade EVERY market day. Nothing
said so when one of them ended a day with no fill at all: a day lost to a stale release seal, a
rail that refused every window or a lane whose task stopped looked exactly like a quiet day, and
was noticed only when a Claude session happened to look. This runs on the box with no session.

WHAT IT WRITES. `desks/mt5/reports/DAILY_FILLS.json`, carried off the box by the state sync:

  today     the UTC day in progress (or just closed): per account the fills (ENTRIES) so far,
            the verdict, the newest skip reasons the account's own ledgers recorded, the time of
            the last fill, and which sources were readable. `final` is false until the session
            close (SESSION_CLOSE_UTC); an in-progress day never alarms.
  judged    the most recent CLOSED market day (Mon-Fri UTC, past SESSION_CLOSE_UTC), recomputed
            every pass and unioned with what earlier passes saw that day.
  alarms    one row per account whose judged day reads ZERO_FILLS or UNMEASURED. Each row has
            the fault-queue shape (key / kind / task / verdict / last_error), so a reader needs
            no knowledge of this file to queue it. The key carries no date: a run of zero days is
            ONE open fault whose first_queued_at says when the run began. The alarm stands until
            the next market day is judged, so a Friday alarm stays visible all weekend.

VERDICTS. FILLED (at least one entry that day, from any source), ZERO_FILLS (every source the
account needs was readable and none shows an entry), UNMEASURED (no entry seen and at least one
needed source was unreadable or stale -- never resolved to a clean zero).

WHAT IS A FILL, PER ACCOUNT (an entry, never a placement: a resting stop that never triggers is
not a fill):

  fusion  `data/live_ledger.jsonl` closed trades by `entry_time`, plus the open positions in
          `data/account_positions.json` by `opened_at` (ops/publish_account_state.py). Both are
          stamped on the broker's deal clock; a day is assigned by that stamp's date.
  e8      gold: a window in `data/e8_gold_state.json` whose leg FILLED (`position_id` recorded by
          the lane's `record_position` / `readopt` management, prop/e8_gold.py) while the state's
          server day is this day -- the intents journal records SENDS only, the state is where a
          fill lands. The state rolls over at the server's midnight, so every pass remembers what
          it saw in this report and unions it (`fill_refs`). FX: `data/e8_intents.jsonl` rows
          SENT by prop/e8_executor.py, which sends MARKET orders (TradeLockerVenue.place) -- a
          SENT row is an entry. Gold protective-stop exits (`data/e8_gold_stop_exits.jsonl`) on
          the day are a fill's evidence too.
  ftmo    `data/live_ledger_prop.jsonl` closed positions (book "ftmo") by `entry_time`;
          `data/ftmo_exec_intents.jsonl` SENT rows (prop/ftmo_executor.py sends TRADE_ACTION_DEAL
          only); `data/ftmo_follower_intents.jsonl` SENT rows whose `kind` is a market kind (a
          pending kind rests until the venue triggers it, and reaches the prop ledger on close).

SKIP REASONS are reason CODES only (`reason` / `rail` / `status`), never the free `why` text: the
report is published, and a why-line can carry prices, sizes and account figures.

READ ONLY. No MetaTrader, no venue, no broker call; nothing here can change what any lane trades.
It runs from ops/run_process_health.cmd (MT5-ProcessHealth, every half hour): no new task.

    python ops/daily_fills.py           write the report
    python ops/daily_fills.py --print   also print it
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REL_OUT = "desks/mt5/reports/DAILY_FILLS.json"
SCHEMA = 1

#: The book's day ends here: CLOSE_HOUR (19:30 UTC) flattens gold, and nothing new opens after.
#: A verdict before this time is a day IN PROGRESS and never alarms.
SESSION_CLOSE_UTC = time(20, 30)
#: Mon-Fri, UTC.
MARKET_WEEKDAYS = frozenset(range(5))
#: Skip reasons kept per account: the newest distinct codes.
MAX_REASONS = 5
#: A JSONL source is read from its tail: a day's rows are at the end, and a ledger a writer
#: forgot to bound must not cost this pass its memory.
TAIL_BYTES = 16 * 1024 * 1024
#: An open-position snapshot older than this cannot vouch for "no position opened today".
POSITIONS_MAX_AGE = timedelta(hours=3)

#: The task each account's fills come from, named on its alarm so a reader knows where to look.
TASKS = {"fusion": "MT5-GatewayResident", "e8": "E8-Gold", "ftmo": "MT5-FTMO-Follower"}
ACCOUNTS = ("fusion", "e8", "ftmo")

DATA = "desks/mt5/data"
SRC = {
    "live_ledger": f"{DATA}/live_ledger.jsonl",
    "account_positions": f"{DATA}/account_positions.json",
    "decision_ledger": f"{DATA}/decision_ledger.jsonl",
    "order_intents": f"{DATA}/order_intents.jsonl",
    "e8_gold_state": f"{DATA}/e8_gold_state.json",
    "e8_gold_intents": f"{DATA}/e8_gold_intents.jsonl",
    "e8_intents": f"{DATA}/e8_intents.jsonl",
    "e8_gold_stop_exits": f"{DATA}/e8_gold_stop_exits.jsonl",
    "e8_decision_ledger": f"{DATA}/e8_decision_ledger.jsonl",
    "live_ledger_prop": f"{DATA}/live_ledger_prop.jsonl",
    "ftmo_follower_intents": f"{DATA}/ftmo_follower_intents.jsonl",
    "ftmo_exec_intents": f"{DATA}/ftmo_exec_intents.jsonl",
}
#: Sources an account cannot be judged ZERO without. Any other source is read when present.
REQUIRED = {
    "fusion": ("live_ledger", "account_positions"),
    "e8": ("e8_gold_state", "e8_gold_intents"),
    "ftmo": ("ftmo_follower_intents", "ftmo_exec_intents"),
}

#: Statuses / outcomes that are not a skip (an entry, a send, a management act, or a shadow pass).
NOT_A_SKIP = frozenset({
    "SENT", "SENDING", "PLACED", "EXECUTED", "FILLED", "OK", "CLOSE", "CLOSED", "WOULD_SEND",
    "WOULD_PLACE", "CAPPED", "RAIL_SHRUNK", "ADOPTED", "MODIFIED"})
#: e8_executor statuses written every five minutes for every certified sleeve that simply had no
#: signal: they are the absence of a trade, not a reason one was refused.
QUIET = frozenset({"NO_SIGNAL", "ALREADY_OPEN", "OWNED_BY_GOLD_LANE", "NOT_LISTED",
                   "STANDS_ASIDE"})


# ---------------------------------------------------------------------------- readers

def _parse_at(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=UTC)
        at = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        return None
    return at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)


def _row_at(row: dict[str, Any], *keys: str) -> datetime | None:
    for k in keys:
        at = _parse_at(row.get(k))
        if at is not None:
            return at
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """The file's rows (its last TAIL_BYTES), or None when it is absent or unreadable. A torn or
    non-object line is skipped, never fatal."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()                      # drop the partial first line
            raw = fh.read()
    except OSError:
        return None
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _ref(kind: str, value: Any) -> str:
    """A stable, non-reversible handle for one fill, so passes can union what they saw without
    the report carrying a venue's position or order number."""
    return f"{kind}:" + hashlib.sha256(f"{kind}|{value}".encode()).hexdigest()[:12]


class Day:
    """What one account's sources say about one UTC day."""

    def __init__(self) -> None:
        self.fills: dict[str, str | None] = {}     # ref -> entry time (None: time not recorded)
        self.reasons: dict[tuple[str, str], dict[str, Any]] = {}
        self.sources: dict[str, str] = {}

    def fill(self, ref: str, at: datetime | None) -> None:
        stamp = at.isoformat(timespec="seconds") if at is not None else None
        if ref not in self.fills or (self.fills[ref] is None and stamp is not None):
            self.fills[ref] = stamp

    def skip(self, source: str, code: Any, at: datetime | None) -> None:
        code = str(code or "").strip()
        if not code:
            return
        key = (source, code[:80])
        row = self.reasons.setdefault(key, {"source": source, "code": key[1], "n": 0,
                                            "last_at": None})
        row["n"] += 1
        stamp = at.isoformat(timespec="seconds") if at is not None else None
        if stamp and (row["last_at"] is None or stamp > row["last_at"]):
            row["last_at"] = stamp


def _rows_on(rows: Iterable[dict[str, Any]], day: date, *keys: str
             ) -> Iterable[tuple[dict[str, Any], datetime]]:
    for row in rows:
        at = _row_at(row, *keys)
        if at is not None and at.date() == day:
            yield row, at


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "").strip().upper()


def _skip_code(row: dict[str, Any]) -> str:
    return str(row.get("reason") or row.get("rail") or row.get("status") or "")


def _load(root: Path, d: Day, name: str) -> list[dict[str, Any]] | None:
    rows = read_jsonl(root / SRC[name])
    d.sources[name] = "READ" if rows is not None else "UNREADABLE"
    return rows


# ---------------------------------------------------------------------------- per account

def fusion_day(root: Path, day: date, now: datetime) -> Day:
    d = Day()
    for row, at in _rows_on(_load(root, d, "live_ledger") or [], day, "entry_time"):
        d.fill(_ref("fusion", row.get("position_id") or row.get("entry_order")
                    or row.get("deal") or at.isoformat()), at)
    book = read_json(root / SRC["account_positions"])
    if book is None:
        d.sources["account_positions"] = "UNREADABLE"
    else:
        updated = _parse_at(book.get("updated_at"))
        # A snapshot can vouch for the day only when it is fresh, or was taken after the day's
        # close (it then still lists every position that opened that day and is still open).
        close = datetime.combine(day, SESSION_CLOSE_UTC, tzinfo=UTC)
        stale = updated is None or (now - updated > POSITIONS_MAX_AGE and updated < close)
        d.sources["account_positions"] = "STALE" if stale else "READ"
        for p in book.get("positions") or []:
            if not isinstance(p, dict):
                continue
            opened = _parse_at(p.get("opened_at"))
            if opened is not None and opened.date() == day:
                d.fill(_ref("fusion", p.get("ticket") or opened.isoformat()), opened)
    for row, at in _rows_on(_load(root, d, "order_intents") or [], day, "time", "at"):
        status = _status(row)
        if status and status not in NOT_A_SKIP:
            d.skip("order_intents", _skip_code(row), at)
    for row, at in _rows_on(_load(root, d, "decision_ledger") or [], day,
                            "decided_at", "time"):
        outcome = str(row.get("outcome") or "").upper()
        if outcome and outcome not in NOT_A_SKIP:
            d.skip("decision_ledger", row.get("reason") or row.get("veto_reason") or outcome, at)
    return d


def e8_day(root: Path, day: date, now: datetime) -> Day:
    d = Day()
    state = read_json(root / SRC["e8_gold_state"])
    d.sources["e8_gold_state"] = "READ" if state is not None else "UNREADABLE"
    if state is not None and str(state.get("date") or "") == day.isoformat():
        for name, w in (state.get("windows") or {}).items():
            if str(name).startswith("carried:") or not isinstance(w, dict):
                continue                           # a position that entered on an earlier day
            if w.get("position_id") is not None:
                d.fill(_ref("e8", w["position_id"]), None)
    for row, _at in _rows_on(_load(root, d, "e8_gold_stop_exits") or [], day, "at"):
        if row.get("position_id") is not None:
            d.fill(_ref("e8", row["position_id"]), None)
    for row, at in _rows_on(_load(root, d, "e8_intents") or [], day, "acked_at", "at"):
        status = _status(row)
        if status == "SENT":
            d.fill(_ref("e8fx", row.get("order_id") or at.isoformat()), at)
        elif status and status not in NOT_A_SKIP and status not in QUIET:
            d.skip("e8_intents", _skip_code(row), at)
    for row, at in _rows_on(_load(root, d, "e8_gold_intents") or [], day, "at"):
        status = _status(row)
        if status and status not in NOT_A_SKIP:
            d.skip("e8_gold_intents", _skip_code(row), at)
    for row, at in _rows_on(_load(root, d, "e8_decision_ledger") or [], day, "decided_at"):
        outcome = str(row.get("outcome") or "").upper()
        if outcome and outcome not in NOT_A_SKIP:
            d.skip("e8_decision_ledger", row.get("reason") or outcome, at)
    return d


def ftmo_day(root: Path, day: date, now: datetime) -> Day:
    d = Day()
    prop = _load(root, d, "live_ledger_prop")
    if prop is None and not (root / SRC["live_ledger_prop"]).exists():
        d.sources["live_ledger_prop"] = "ABSENT"   # no FTMO position has closed yet: not a fault
    for row, at in _rows_on(prop or [], day, "entry_time"):
        if str(row.get("book") or "ftmo") == "ftmo":
            d.fill(_ref("ftmo", row.get("entry_order") or row.get("position_id")
                        or at.isoformat()), at)
    for row, at in _rows_on(_load(root, d, "ftmo_exec_intents") or [], day, "at"):
        status = _status(row)
        if status == "SENT":
            d.fill(_ref("ftmo", row.get("order_id") or at.isoformat()), at)
        elif status and status not in NOT_A_SKIP:
            d.skip("ftmo_exec_intents", _skip_code(row), at)
    for row, at in _rows_on(_load(root, d, "ftmo_follower_intents") or [], day, "at"):
        status = _status(row)
        if status == "SENT" and str(row.get("kind") or "").endswith("_market"):
            d.fill(_ref("ftmo", row.get("order_id") or at.isoformat()), at)
        elif status and status not in NOT_A_SKIP:
            d.skip("ftmo_follower_intents", _skip_code(row), at)
    return d


READERS = {"fusion": fusion_day, "e8": e8_day, "ftmo": ftmo_day}


# ---------------------------------------------------------------------------- the day

def is_market_day(day: date) -> bool:
    return day.weekday() in MARKET_WEEKDAYS


def is_closed(day: date, now: datetime) -> bool:
    return now >= datetime.combine(day, SESSION_CLOSE_UTC, tzinfo=UTC)


def last_closed_market_day(now: datetime) -> date:
    day = now.date()
    while not (is_market_day(day) and is_closed(day, now)):
        day -= timedelta(days=1)
    return day


def account_block(name: str, d: Day, day: date, prior: dict[str, Any] | None) -> dict[str, Any]:
    fills = dict(d.fills)
    # What earlier passes saw this day stands: the E8 state forgets a day at its rollover.
    for ref, at in ((prior or {}).get("fill_refs") or {}).items():
        if ref not in fills or (fills[ref] is None and at):
            fills[str(ref)] = at
    unreadable = sorted(k for k in REQUIRED[name] if d.sources.get(k) in ("UNREADABLE", "STALE"))
    if fills:
        verdict = "FILLED"
    elif unreadable:
        verdict = "UNMEASURED"
    else:
        verdict = "ZERO_FILLS"
    stamps = [a for a in fills.values() if a]
    reasons = sorted(d.reasons.values(), key=lambda r: str(r["last_at"] or ""), reverse=True)
    return {"date": day.isoformat(), "fills": len(fills), "verdict": verdict,
            "last_fill_at": max(stamps) if stamps else None,
            "skip_reasons": reasons[:MAX_REASONS],
            "unreadable": unreadable, "sources": dict(sorted(d.sources.items())),
            "fill_refs": dict(sorted(fills.items()))}


def judge_day(root: Path, day: date, now: datetime,
              priors: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Every account's block for `day`, unioned with any earlier block for the same day."""
    same = [p for p in priors if isinstance(p, dict) and p.get("date") == day.isoformat()]
    accounts = {}
    for name in ACCOUNTS:
        prior_refs: dict[str, Any] = {}
        for p in same:
            prior_refs.update(((p.get("accounts") or {}).get(name) or {}).get("fill_refs") or {})
        try:
            d = READERS[name](root, day, now)
        except Exception as exc:                    # a reader defect is UNMEASURED, never ZERO
            d = Day()
            d.sources = dict.fromkeys(REQUIRED[name], "UNREADABLE")
            d.sources["reader_error"] = type(exc).__name__
        accounts[name] = account_block(name, d, day, {"fill_refs": prior_refs})
    return {"date": day.isoformat(), "market_day": is_market_day(day),
            "final": is_closed(day, now), "accounts": accounts}


def alarms_for(judged: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not judged.get("market_day") or not judged.get("final"):
        return out
    for name in ACCOUNTS:
        acc = (judged.get("accounts") or {}).get(name) or {}
        verdict = acc.get("verdict")
        if verdict not in ("ZERO_FILLS", "UNMEASURED"):
            continue
        if verdict == "ZERO_FILLS":
            codes = ", ".join(f"{r['source']}:{r['code']}" for r in acc.get("skip_reasons") or [])
            why = (f"{name}: no entry on market day {judged['date']}; newest skip reasons: "
                   f"{codes or 'none recorded'}")
        else:
            why = (f"{name}: fills on market day {judged['date']} unmeasured; unreadable: "
                   f"{', '.join(acc.get('unreadable') or []) or 'unknown'}")
        out.append({"key": f"daily_fills:{name}",
                    "kind": "zero_fills" if verdict == "ZERO_FILLS" else "fills_unmeasured",
                    "task": TASKS[name], "verdict": verdict, "date": judged["date"],
                    "last_fill_at": acc.get("last_fill_at"), "last_error": why[:300]})
    return out


def build(now: datetime | None = None, root: Path = ROOT,
          previous: dict[str, Any] | None = None) -> dict[str, Any]:
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    if previous is None:
        previous = read_json(root / REL_OUT) or {}
    priors = [previous.get("today") or {}, previous.get("judged") or {}]
    today = judge_day(root, now.date(), now, priors)
    jday = last_closed_market_day(now)
    judged = today if jday == now.date() else judge_day(root, jday, now, priors)
    alarms = alarms_for(judged)
    return {
        "schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
        "source": "ops/daily_fills.py",
        "session_close_utc": SESSION_CLOSE_UTC.strftime("%H:%M"),
        "status": ("ALARM" if alarms else "OK"),
        "alarms": alarms,
        "today": today,
        "judged": judged,
        "rule": ("every account trades every market day (Mon-Fri UTC); a closed market day with "
                 "no entry is ZERO_FILLS, and one whose needed sources were unreadable is "
                 "UNMEASURED -- both alarm until the next market day is judged"),
    }


def write(doc: dict[str, Any], root: Path = ROOT) -> Path:
    out = root / REL_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--print", action="store_true", help="print the report too")
    args = ap.parse_args(argv)
    doc = build()
    write(doc)
    line = ", ".join(f"{n} {a['verdict']} ({a['fills']})"
                     for n, a in doc["today"]["accounts"].items())
    print(f"DAILY FILLS {doc['status']} today {doc['today']['date']}: {line}; "
          f"judged {doc['judged']['date']}: {len(doc['alarms'])} alarm(s)")
    if args.print:
        print(json.dumps(doc, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
