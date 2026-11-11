"""WHEN EACH ACCOUNT LAST TRADED: a report-only publisher of fills, intents and balances.

Before this, nothing published when FTMO or E8 last traded. A box read on 2026-11-11 found FTMO's
newest journaled fill on 11-03 (data/live_ledger_prop.jsonl), E8's exit-fill journal
(data/e8_gold_exit_fills.csv) stale since 10-20, and "last fill" had to be pieced together from
equity steps and the intent journals by hand. This module does that join once an hour and writes
it down: `desks/mt5/reports/ACCOUNT_ACTIVITY.json`, one block per account (fusion, e8, ftmo).

REPORT ONLY. It imports nothing but the standard library: no broker or MetaTrader module and
nothing from the money path. It calls no venue, and the only file it writes is its own report
(a temporary sibling, then `os.replace`).

THE ROW SHAPES ARE THE WRITERS', read from their code, never guessed:

  data/live_ledger.jsonl           mt5desk/gateway.py record_closed_trades: exit_time, time,
                                   symbol, entry_side (0 buy / 1 sell), volume, server
  data/live_ledger_prop.jsonl      prop/ftmo_follower.py compose_fills (prop-fills-v1): book,
                                   exit_time, time, symbol, entry_side, volume
  data/order_intents.jsonl         mt5desk/gateway.py _record_intent: time, retcode, status
  data/ftmo_follower_intents.jsonl prop/ftmo_follower.py _record: at, status, reason, why
  data/e8_gold_intents.jsonl       prop/e8_gold.py _record: at, status, why, rail
  data/e8_intents.jsonl            prop/e8_executor.py _record: at, status, why
  data/order_door_ledger.jsonl     mt5desk/order_door.py venue_act / append_ledger: at, venue,
                                   action, outcome (the E8 lanes' TradeLocker writes)
  reports/FTMO_ACCOUNT_STATE.json  prop/ftmo_venue_reader.py: generated_at, balance, equity,
                                   day_start_balance (FTMO's 00:00 CE(S)T anchor)
  reports/E8_GOLD.json             prop/e8_gold.py: at, equity (no balance is written)
  data/e8_guard_state.json         prop/e8_guard.py: day, day_start, peak_equity
  data/account_state.json          ops/publish_account_state.py: updated_at, server, balance,
                                   equity, today_closed_pnl (since 00:00 UTC)
  web/equity_history.jsonl         scripts/build_zentech_state.py _equity_history: at, equity
                                   (the main terminal's equity, sampled; carries no account)

  data/e8_gold_exit_fills.csv has NO WRITER IN THIS REPOSITORY, so its row schema is unknown and
  no field name is assumed: its newest row is bounded by the file's mtime (a row cannot be newer
  than the file's last write), which is enough to call it stale, and it never supplies a fill.

INFERRED IS WRITTEN AS INFERRED. A balance or equity history exists only for the main terminal
(web/equity_history.jsonl, used for fusion); FTMO and E8 have none, and the block says so. Without
one, the account-state report's balance against its day-start anchor says whether a fill closed
since that anchor; the fill is then `source: "inferred:equity_step"`, with the window it fell in
and the symbol, side and lots of the newest SENT intent before it, labelled as taken from that
intent.

NEVER QUIET ON A MISSING FILE. Every block lists each source and whether it was read. A missing
fill journal makes `fills_24h` null, not 0, and `facts` reads PARTIAL (some sources missing or
the last fill unknown) or UNMEASURED (nothing readable), never MEASURED.

    python desks/mt5/research/account_activity.py            # write the report
    python desks/mt5/research/account_activity.py --print    # also print it
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
OUT_REL = "reports/ACCOUNT_ACTIVITY.json"
SCHEMA = "account-activity-v1"
WINDOW_H = 24
#: MT5 retcodes that mean the order was accepted (placed / done / done partial).
SENT_RETCODES = (10008, 10009, 10010)
#: An equity step bigger than this share of the prior sample is a terminal switched to another
#: account (the history carries no account key), never a fill.
SWITCH_FRAC = 0.5
#: FTMO's trading day starts at midnight Prague time (prop/ftmo_follower.DAY_TZ).
FTMO_DAY_TZ = "Europe/Prague"


# ------------------------------------------------------------------ reading

def _ts(v: Any) -> datetime | None:
    """An aware UTC datetime from an ISO string or epoch seconds; None for anything else."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=UTC) if v > 0 else None
        except (OverflowError, OSError, ValueError):
            return None
    try:
        t = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(UTC) if t.tzinfo is not None else None


def _iso(t: datetime | None) -> str | None:
    return t.isoformat(timespec="seconds") if t is not None else None


def _mtime(p: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return None


class Source:
    """One input file: whether it was read, how many rows, and why not."""

    def __init__(self, base: Path, rel: str, role: str) -> None:
        self.rel, self.role, self.path = rel, role, base / rel
        self.present = self.path.is_file()
        self.rows: list[dict[str, Any]] = []
        self.doc: dict[str, Any] | None = None
        self.why: str | None = None if self.present else "missing"
        self.torn = 0

    def jsonl(self) -> Source:
        if self.present:
            try:
                text = self.path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError as exc:
                self.present, self.why = False, f"unreadable ({type(exc).__name__})"
                return self
            for ln in text.splitlines():
                if not ln.strip():
                    continue
                try:
                    d = json.loads(ln)
                except ValueError:
                    self.torn += 1
                    continue
                if isinstance(d, dict):
                    self.rows.append(d)
        return self

    def json(self) -> Source:
        if self.present:
            try:
                d = json.loads(self.path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                self.present, self.why = False, f"unreadable ({type(exc).__name__})"
                return self
            if isinstance(d, dict):
                self.doc = d
            else:
                self.present, self.why = False, "not a JSON object"
        return self

    def csv_rows(self) -> int | None:
        """Data rows in a CSV whose schema is unknown (header excluded); None if unreadable."""
        if not self.present:
            return None
        try:
            with self.path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
                n = sum(1 for _ in csv.reader(fh))
        except (OSError, csv.Error) as exc:
            self.present, self.why = False, f"unreadable ({type(exc).__name__})"
            return None
        return max(n - 1, 0)

    def card(self, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {"file": self.rel, "role": self.role, "present": self.present}
        if self.why:
            out["why"] = self.why
        if self.rows:
            out["rows"] = len(self.rows)
        if self.torn:
            out["torn_lines"] = self.torn
        out.update(extra)
        return out


# ------------------------------------------------------------------ fills and intents

def _side(entry_side: Any) -> str | None:
    """The position's direction from a ledger row's `entry_side` (0 buy, 1 sell)."""
    return {0: "long", 1: "short"}.get(entry_side) if isinstance(entry_side, int) else None


def ledger_fills(src: Source, *, book: str | None = None,
                 exclude_server: str | None = None) -> list[dict[str, Any]]:
    """Closed-trade rows (gateway or prop-fills-v1) as fills, oldest first. A row's time is its
    exit deal's (`exit_time`), else the row's own `time`."""
    out: list[dict[str, Any]] = []
    for r in src.rows:
        if book is not None and r.get("book") not in (None, book):
            continue
        if exclude_server and exclude_server.lower() in str(r.get("server") or "").lower():
            continue
        t = _ts(r.get("exit_time")) or _ts(r.get("time"))
        if t is None:
            continue
        out.append({"ts": t, "symbol": r.get("symbol"), "side": _side(r.get("entry_side")),
                    "lots": r.get("volume"), "source": f"journal:{Path(src.rel).name}"})
    out.sort(key=lambda f: f["ts"])
    return out


def _outcome(r: dict[str, Any]) -> str | None:
    s = r.get("status")
    if isinstance(s, str) and s.strip():
        return s.strip().upper()
    code = r.get("retcode")
    if isinstance(code, int) and not isinstance(code, bool):
        return "SENT" if code in SENT_RETCODES else "REJECTED"
    return None


def intents(src: Source, *, time_key: str,
            exclude_server: str | None = None) -> list[dict[str, Any]]:
    """Intent rows as {ts, outcome, reason, ...}, oldest first. `reason` is the row's own
    `reason`, else `why`, else the `rail` that refused it."""
    out: list[dict[str, Any]] = []
    for r in src.rows:
        if exclude_server and exclude_server.lower() in str(r.get("server") or "").lower():
            continue
        t = _ts(r.get(time_key))
        oc = _outcome(r)
        if t is None or oc is None:
            continue
        reason = r.get("reason") or r.get("why") or r.get("rail")
        out.append({"ts": t, "outcome": oc,
                    "reason": str(reason)[:300] if reason is not None else None,
                    "symbol": r.get("symbol"), "side": r.get("side"), "lots": r.get("lot"),
                    "kind": r.get("kind"), "window": r.get("window"),
                    "source": Path(src.rel).name})
    out.sort(key=lambda i: i["ts"])
    return out


def _fill_card(f: dict[str, Any] | None) -> dict[str, Any] | None:
    if f is None:
        return None
    return {**{k: v for k, v in f.items() if k != "ts"}, "ts": _iso(f["ts"])}


def _intent_card(i: dict[str, Any] | None) -> dict[str, Any] | None:
    if i is None:
        return None
    out: dict[str, Any] = {"ts": _iso(i["ts"]), "outcome": i["outcome"], "reason": i["reason"]}
    for k in ("symbol", "side", "lots", "kind", "window", "source"):
        if i.get(k) is not None:
            out[k] = i[k]
    return out


def _since(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    lo = now - timedelta(hours=WINDOW_H)
    return [r for r in rows if lo <= r["ts"] <= now]


# ------------------------------------------------------------------ equity steps

def history_step(src: Source) -> dict[str, Any]:
    """The newest equity step in a sampled history: when equity last changed, and since when it
    has not. A jump over SWITCH_FRAC is a terminal moved to another account, never a fill."""
    pts = sorted(((t, float(r["equity"])) for r in src.rows
                  if (t := _ts(r.get("at"))) is not None
                  and isinstance(r.get("equity"), (int, float))
                  and not isinstance(r.get("equity"), bool)), key=lambda p: p[0])
    if not pts:
        return {"status": "UNMEASURED", "why": f"{src.rel}: no samples"}
    out: dict[str, Any] = {"status": "MEASURED", "samples": len(pts),
                           "first_at": _iso(pts[0][0]), "last_at": _iso(pts[-1][0]),
                           "last_equity": pts[-1][1]}
    for (t0, e0), (t1, e1) in zip(reversed(pts[:-1]), reversed(pts[1:]), strict=True):
        if e1 == e0:
            continue
        if e0 and abs(e1 - e0) / abs(e0) > SWITCH_FRAC:
            out.update({"step": None, "unchanged_since": _iso(t1),
                        "why": (f"equity jumped {e0:,.2f} -> {e1:,.2f} at {_iso(t1)}: a terminal "
                                "switched account, not a fill; nothing before it is read")})
            return out
        out.update({"step": {"after": _iso(t0), "by": _iso(t1), "from": e0, "to": e1},
                    "unchanged_since": _iso(t1)})
        return out
    out.update({"step": None, "unchanged_since": _iso(pts[0][0]),
                "why": "equity never changed across the history"})
    return out


def _sent_before(sent: list[dict[str, Any]], t: datetime) -> dict[str, Any] | None:
    prior = [i for i in sent if i["ts"] <= t]
    return prior[-1] if prior else None


def inferred_fill(after: datetime | None, by: datetime, basis: str,
                  sent: list[dict[str, Any]]) -> dict[str, Any]:
    """A fill known only from a balance or equity step inside (after, by]. Symbol, side and lots
    are the newest SENT intent's before `by`, and say so."""
    i = _sent_before(sent, by)
    return {"ts": by, "ts_is_upper_bound": True, "ts_window": [_iso(after), _iso(by)],
            "symbol": i.get("symbol") if i else None, "side": i.get("side") if i else None,
            "lots": i.get("lots") if i else None, "source": "inferred:equity_step",
            "basis": basis,
            "detail_from_intent": (f"{i['source']} SENT at {_iso(i['ts'])}" if i
                                   else "no SENT intent before the step: detail unknown")}


def _day_start(now: datetime, tz: str) -> datetime | None:
    try:
        from zoneinfo import ZoneInfo
        local = now.astimezone(ZoneInfo(tz))
    except Exception:
        return None
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


# ------------------------------------------------------------------ one block

def block(*, fills: list[dict[str, Any]], fill_sources: list[Source],
          intent_rows: list[dict[str, Any]], sources: list[Source], now: datetime,
          balance: Any, equity: Any, unchanged: dict[str, Any] | None,
          inferred: dict[str, Any] | None, extra_stale: list[dict[str, Any]] | None = None,
          notes: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    """Assemble one account's block from what was read. The newest of the journaled fill and
    the inferred one is `last_fill`, and the inferred one only when no journaled fill falls in or
    after its window (the journal then explains the step)."""
    journal_last = fills[-1] if fills else None
    last = journal_last
    if inferred is not None:
        lo = _ts(inferred["ts_window"][0])
        explained = journal_last is not None and (lo is None or journal_last["ts"] > lo)
        if not explained:
            last = inferred
    sent = [i for i in intent_rows if i["outcome"] == "SENT"]
    newest_sent = sent[-1] if sent else None
    stale: list[dict[str, Any]] = []
    for s in fill_sources:
        if not s.present:
            continue
        mine = [f for f in fills if f["source"] == f"journal:{Path(s.rel).name}"]
        newest = mine[-1]["ts"] if mine else None
        if newest_sent is not None and (newest is None or newest < newest_sent["ts"]):
            stale.append(_stale_card(s.rel, newest, "row time", newest_sent, inferred))
    stale += extra_stale or []
    journals_ok = bool(fill_sources) and all(s.present for s in fill_sources)
    fills_24h = len(_since(fills, now)) if journals_ok else None
    intent_srcs = [s for s in sources if s.role == "intents"]
    intents_ok = bool(intent_srcs) and all(s.present for s in intent_srcs)
    by_outcome = (dict(sorted(Counter(i["outcome"] for i in _since(intent_rows, now)).items()))
                  if intent_srcs and any(s.present for s in intent_srcs) else None)
    missing = [s.rel for s in sources if not s.present]
    readable = [s for s in sources if s.present]
    if not readable:
        facts = "UNMEASURED"
    elif missing or last is None or balance is None or equity is None or not intents_ok:
        facts = "PARTIAL"
    else:
        facts = "MEASURED"
    out: dict[str, Any] = {
        "facts": facts,
        "last_fill": _fill_card(last),
        "last_journaled_fill": _fill_card(journal_last),
        "last_intent": _intent_card(intent_rows[-1] if intent_rows else None),
        "last_sent": _intent_card(newest_sent),
        "fills_24h": fills_24h,
        "fills_24h_basis": ("journaled fills only; a stale journal makes this a lower bound"
                            if fills_24h is not None else
                            "UNMEASURED: a fill journal is missing or none is known"),
        "intents_24h_by_outcome": by_outcome,
        "intents_24h_partial": bool(by_outcome is not None and not intents_ok),
        "balance": balance, "equity": equity,
        "balance_unchanged_since": unchanged,
        "journal_stale": stale,
        "missing": missing,
        "sources": [s.card() for s in sources],
    }
    out.update(extra)
    if notes:
        out["notes"] = notes
    return out


def _stale_card(rel: str, newest: datetime | None, basis: str,
                sent: dict[str, Any], inferred: dict[str, Any] | None) -> dict[str, Any]:
    confirmed = False
    if inferred is not None:
        by = _ts(inferred["ts_window"][1])
        confirmed = by is not None and (newest is None or by > newest)
    return {"file": rel, "newest_row": _iso(newest), "newest_row_basis": basis,
            "newer_sent": _iso(sent["ts"]), "newer_sent_source": sent["source"],
            "confirmed_by_equity_step": confirmed}


# ------------------------------------------------------------------ the accounts

def ftmo(desk: Path, now: datetime) -> dict[str, Any]:
    led = Source(desk, "data/live_ledger_prop.jsonl", "fills").jsonl()
    its = Source(desk, "data/ftmo_follower_intents.jsonl", "intents").jsonl()
    st = Source(desk, "reports/FTMO_ACCOUNT_STATE.json", "account_state").json()
    fills = ledger_fills(led, book="ftmo")
    rows = intents(its, time_key="at")
    sent = [i for i in rows if i["outcome"] == "SENT"]
    doc = st.doc or {}
    bal, eq, d0 = doc.get("balance"), doc.get("equity"), doc.get("day_start_balance")
    at = _ts(doc.get("generated_at"))
    notes = ["no balance or equity history exists for FTMO: the equity step is read from "
             "FTMO_ACCOUNT_STATE.json's balance against its day_start_balance"]
    inferred, unchanged = None, None
    if not isinstance(bal, (int, float)) or not isinstance(d0, (int, float)) or at is None:
        unchanged = None
        notes.append("FTMO_ACCOUNT_STATE.json carries no balance, day_start_balance or "
                     f"generated_at (status {doc.get('status')!r}): no step is measurable")
    else:
        start = _day_start(at, FTMO_DAY_TZ)
        if round(float(bal), 2) != round(float(d0), 2):
            inferred = inferred_fill(start, at, (f"balance {float(bal):,.2f} != day_start_balance "
                                                 f"{float(d0):,.2f}: a fill closed since FTMO's "
                                                 "00:00 CE(S)T"), sent)
        else:
            unchanged = {"at_least_since": _iso(start), "as_of": _iso(at),
                         "basis": "balance == day_start_balance (FTMO's 00:00 CE(S)T anchor); "
                                  "earlier is unmeasured: there is no balance history"}
    return block(fills=fills, fill_sources=[led], intent_rows=rows, sources=[led, its, st],
                 now=now, balance=bal, equity=eq, unchanged=unchanged, inferred=inferred,
                 notes=notes, account_state_at=_iso(at), open_positions=doc.get("open_positions"))


def e8(desk: Path, now: datetime) -> dict[str, Any]:
    gold = Source(desk, "data/e8_gold_intents.jsonl", "intents").jsonl()
    exe = Source(desk, "data/e8_intents.jsonl", "intents").jsonl()
    door = Source(desk, "data/order_door_ledger.jsonl", "venue_writes").jsonl()
    csvf = Source(desk, "data/e8_gold_exit_fills.csv", "fills")
    rep = Source(desk, "reports/E8_GOLD.json", "account_state").json()
    guard = Source(desk, "data/e8_guard_state.json", "account_state").json()
    csv_n = csvf.csv_rows()
    rows = sorted(intents(gold, time_key="at") + intents(exe, time_key="at"),
                  key=lambda i: i["ts"])
    sent = [i for i in rows if i["outcome"] == "SENT"]
    eq = (rep.doc or {}).get("equity")
    at = _ts((rep.doc or {}).get("at"))
    g = guard.doc or {}
    d0 = g.get("day_start")
    notes = ["no balance or equity history exists for E8, and E8_GOLD.json writes no balance: "
             "the step is read from E8_GOLD.json's equity against e8_guard_state.json's "
             "day_start (the server day's anchor)",
             "data/e8_gold_exit_fills.csv has no writer in this repository: its schema is "
             "unknown, so it supplies no fill and its newest row is bounded by the file's mtime"]
    inferred, unchanged = None, None
    if isinstance(eq, (int, float)) and isinstance(d0, (int, float)) and at is not None:
        if round(float(eq), 2) != round(float(d0), 2):
            inferred = inferred_fill(None, at, (f"equity {float(eq):,.2f} != the guard's day_start "
                                                f"{float(d0):,.2f} (server day {g.get('day')}): "
                                                "a fill since the day's anchor, or a position "
                                                "still open"), sent)
        else:
            unchanged = {"at_least_since": f"server day {g.get('day')} start", "as_of": _iso(at),
                         "basis": "equity == e8_guard_state day_start; earlier is unmeasured: "
                                  "there is no equity history",
                         "peak_equity": g.get("peak_equity")}
    else:
        notes.append("E8_GOLD.json equity or the guard's day_start is unreadable: no step is "
                     "measurable")
    extra_stale = []
    newest_sent = sent[-1] if sent else None
    csv_m = _mtime(csvf.path) if csvf.present else None
    if newest_sent is not None and csv_m is not None and csv_m < newest_sent["ts"]:
        extra_stale.append(_stale_card(csvf.rel, csv_m, "file mtime (an upper bound on its "
                                       "newest row)", newest_sent, inferred))
    door_rows = [r for r in door.rows if str(r.get("venue") or "") == "tradelocker"
                 and _ts(r.get("at")) is not None]
    door_rows.sort(key=lambda r: _ts(r.get("at")) or now)
    last_door = door_rows[-1] if door_rows else None
    out = block(fills=[], fill_sources=[], intent_rows=rows,
                sources=[gold, exe, door, csvf, rep, guard], now=now, balance=None, equity=eq,
                unchanged=unchanged, inferred=inferred, extra_stale=extra_stale, notes=notes,
                account_state_at=_iso(at),
                exit_fills_csv={"rows": csv_n, "mtime": _iso(csv_m)},
                last_venue_write=(None if last_door is None else
                                  {"ts": _iso(_ts(last_door.get("at"))),
                                   "action": last_door.get("action"),
                                   "outcome": last_door.get("outcome"),
                                   "caller": last_door.get("caller")}))
    # E8's only fill journal has no known schema, so fills are never countable here.
    out["fills_24h"] = None
    out["fills_24h_basis"] = ("UNMEASURED: E8's only fill journal (e8_gold_exit_fills.csv) has "
                              "no writer in this repository and no known schema")
    out["balance_why"] = "E8_GOLD.json writes equity only; no E8 report carries a balance"
    if out["facts"] == "MEASURED":
        out["facts"] = "PARTIAL"
    return out


def fusion(desk: Path, repo: Path, now: datetime) -> dict[str, Any]:
    names = sorted(p.name for p in (desk / "data").glob("live_ledger*.jsonl")
                   if p.name not in ("live_ledger_prop.jsonl", "live_ledger_corrections.jsonl"))
    leds = [Source(desk, f"data/{n}", "fills").jsonl() for n in names or ["live_ledger.jsonl"]]
    its = Source(desk, "data/order_intents.jsonl", "intents").jsonl()
    st = Source(desk, "data/account_state.json", "account_state").json()
    hist = Source(repo, "web/equity_history.jsonl", "equity_history").jsonl()
    fills = sorted((f for s in leds for f in ledger_fills(s, exclude_server="ftmo")),
                   key=lambda f: f["ts"])
    rows = intents(its, time_key="time", exclude_server="ftmo")
    sent = [i for i in rows if i["outcome"] == "SENT"]
    doc = st.doc or {}
    server = str(doc.get("server") or "")
    notes = ["live_ledger_prop.jsonl (FTMO's book) and live_ledger_corrections.jsonl (the "
             "audited sidecar, not fills) are not fusion fill journals"]
    bal = eq = None
    other_account = bool(server) and "fusion" not in server.lower()
    if st.doc is not None and not other_account:
        bal, eq = doc.get("balance"), doc.get("equity")
    elif other_account:
        notes.append(f"data/account_state.json names server {server!r}, not Fusion: the main "
                     "terminal is on another account, so no Fusion balance or equity is read "
                     "and the equity history is not trusted past the switch")
    inferred, unchanged = None, None
    step: dict[str, Any] = (history_step(hist) if hist.present else
                            {"status": "UNMEASURED", "why": "web/equity_history.jsonl missing"})
    if step.get("step"):
        s: dict[str, Any] = step["step"]
        inferred = inferred_fill(_ts(s["after"]), _ts(s["by"]) or now,
                                 (f"web/equity_history.jsonl: equity {s['from']:,.2f} -> "
                                  f"{s['to']:,.2f} between two samples"), sent)
    if step.get("unchanged_since") and not other_account:
        unchanged = {"at_least_since": step["unchanged_since"], "as_of": step.get("last_at"),
                     "basis": "equity unchanged in web/equity_history.jsonl (equity, not "
                              "balance: the history samples equity only)"}
    at = _ts(doc.get("updated_at"))
    pnl = doc.get("today_closed_pnl")
    if not other_account and at is not None and isinstance(pnl, (int, float)):
        day0 = at.replace(hour=0, minute=0, second=0, microsecond=0)
        hist_last = _ts(step.get("last_at"))
        if pnl != 0 and (inferred is None or (_ts(inferred["ts_window"][1]) or at) < day0):
            inferred = inferred_fill(day0, at, f"account_state.json today_closed_pnl {pnl:,.2f} "
                                               "!= 0: a fill closed since 00:00 UTC", sent)
        elif pnl == 0 and (unchanged is None or (hist_last is not None and hist_last < day0)):
            # the history ends before today: today's publisher is the newer reading
            unchanged = {"at_least_since": _iso(day0), "as_of": _iso(at),
                         "basis": "account_state.json today_closed_pnl == 0 since 00:00 UTC"}
    return block(fills=fills, fill_sources=leds, intent_rows=rows, sources=[*leds, its, st, hist],
                 now=now, balance=bal, equity=eq, unchanged=unchanged, inferred=inferred,
                 notes=notes, account_state_at=_iso(at), account_state_server=server or None,
                 equity_history=step)


def build(desk: Path = DESK, repo: Path = REPO, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    return {"schema": SCHEMA, "generated_at": _iso(now), "window_h": WINDOW_H,
            "report_only": True,
            "basis": ("read from the desk's own journals and reports; no venue is called. "
                      "An inferred fill is labelled inferred:equity_step."),
            "accounts": {"fusion": fusion(desk, repo, now), "e8": e8(desk, now),
                         "ftmo": ftmo(desk, now)}}


def write(doc: dict[str, Any], path: Path) -> Path:
    """Write `doc` whole: a temporary sibling, then `os.replace`, so no reader sees half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desk", type=Path, default=DESK)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args(argv)
    doc = build(a.desk, a.repo)
    out = write(doc, a.desk / OUT_REL)
    if a.show:
        print(json.dumps(doc, indent=1, default=str))
    for name, b in doc["accounts"].items():
        lf = b.get("last_fill") or {}
        print(f"account_activity {name}: facts={b['facts']} last_fill={lf.get('ts')} "
              f"({lf.get('source')}) stale={[s['file'] for s in b['journal_stale']]} "
              f"missing={b['missing']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
