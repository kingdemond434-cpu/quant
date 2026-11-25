"""DID EVERY ACCOUNT TRADE ON THE LAST MARKET DAY? And if one did not, why.

WHY (principal 2026-11-19, standing rule: E8, FTMO and Fusion trade every market day). On
2026-11-19 FTMO had traded nothing for days while every organ read healthy: the box ran 11-10
code, from before the FTMO Tier S bar drop (#769), so the executor refused 356 of its 357
strategies, one refusal row at a time, into a journal nobody read. A coordinator found it by
hand. This module is that check, run by the box itself on the plumbing watchdog's clock.

WHAT IT MEASURES. For the last COMPLETED market day (UTC Monday..Friday; Saturday and Sunday are
never judged, a Monday pass judges Friday) it counts, per account, the rows that put an order at
the venue, read from the journals each lane already writes:

  fusion  data/decision_ledger.jsonl          `taken` true (the placement interlock's own rule)
  e8      data/e8_intents.jsonl               status SENT  (certified sleeves, E8-Executor)
          data/e8_gold_intents.jsonl          status SENT  (gold windows, E8-Gold)
          data/e8_decision_ledger.jsonl       outcome PLACED
  ftmo    data/ftmo_exec_intents.jsonl        status SENT  (sleeves, MT5-FTMO-Executor)
          data/ftmo_follower_intents.jsonl    status SENT  (gold copy, MT5-FTMO-Follower)

AND DIAGNOSES A MISS. An account with zero placements gets the evidence a person would gather:
how many decisions its lanes wrote that day and the commonest refusal statuses (so "356 of 357
NOT_LISTED" is on the page, not in a journal), its lanes' last pass status, and whether the box
is running behind the shipped branch (the 11-19 cause). The KNOWN FIX for the code-behind cause
is the adoption task, which the plumbing watchdog already re-runs on an adoption_lag defect; no
other fix is applied from here, deliberately: arming, sizing, the allocator and the prop rails
are not things a watchdog may touch, and a lane that wrote nothing at all is a defect to name,
not a trade to force.

IT NEVER TRADES, SIZES, ARMS OR EDITS A RAIL. Read-only: it opens journals and reports.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

#: How much of each journal's END is read. A day of one-row-a-minute Fusion decisions is well
#: under this; reading whole multi-GB journals every 15 minutes is how a watchdog stalls.
TAIL_BYTES = 24 * 1024 * 1024

_TS_FIELDS = ("decided_at", "ts", "at", "time")

#: account -> ((relative journal, placed-row predicate name), ...), and the lane reports whose
#: `status` is quoted in a diagnosis.
SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "fusion": (("data/decision_ledger.jsonl", "taken"),),
    "e8": (("data/e8_intents.jsonl", "sent"),
           ("data/e8_gold_intents.jsonl", "sent"),
           ("data/e8_decision_ledger.jsonl", "placed")),
    "ftmo": (("data/ftmo_exec_intents.jsonl", "sent"),
             ("data/ftmo_follower_intents.jsonl", "sent")),
}
LANE_REPORTS: dict[str, tuple[str, ...]] = {
    "fusion": ("data/gateway_state.json",),
    "e8": ("reports/E8_EXEC.json", "reports/E8_GOLD.json"),
    "ftmo": ("reports/FTMO_EXEC.json", "reports/FTMO_FOLLOWER.json"),
}


def _parse(text: Any) -> datetime | None:
    if not text:
        return None
    try:
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def row_time(row: Mapping[str, Any]) -> datetime | None:
    for k in _TS_FIELDS:
        t = _parse(row.get(k))
        if t is not None:
            return t
    return None


def _placed(kind: str, row: Mapping[str, Any]) -> bool:
    if kind == "taken":
        if isinstance(row.get("taken"), bool):
            return bool(row["taken"])
        if str(row.get("reason") or "") == "placed":
            return True
        return str(row.get("outcome") or "").upper() in ("EXECUTED", "PLACED", "FILLED")
    if kind == "placed":
        return str(row.get("outcome") or "").upper() == "PLACED"
    return str(row.get("status") or "").upper() == "SENT"


def _why(kind: str, row: Mapping[str, Any]) -> str:
    if kind == "taken":
        return str(row.get("reason") or row.get("outcome") or "?")[:60]
    if kind == "placed":
        return f"{row.get('outcome') or '?'}:{row.get('reason') or ''}"[:60]
    return str(row.get("status") or "?")[:60]


def read_tail(path: Path, limit: int = TAIL_BYTES) -> list[dict[str, Any]]:
    """The journal's last `limit` bytes as rows; a torn first line is dropped, never raised."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > limit:
                fh.seek(size - limit)
                fh.readline()
            raw = fh.read()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for ln in raw.decode("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            doc = json.loads(ln)
        except ValueError:
            continue
        if isinstance(doc, dict):
            rows.append(doc)
    return rows


def last_market_day(now: datetime) -> date:
    """The most recent COMPLETED UTC weekday before `now`'s date."""
    d = now.astimezone(UTC).date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _lane_status(desk: Path, rels: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rel in rels:
        try:
            doc = json.loads((desk / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out[rel] = "ABSENT"
            continue
        if not isinstance(doc, dict):
            out[rel] = "UNREADABLE"
            continue
        out[rel] = {k: doc.get(k) for k in ("status", "why", "at", "state", "last_reconcile",
                                            "paused", "mode") if doc.get(k) is not None}
    return out


def measure(desk: Path | None = None, now: datetime | None = None,
            reader: Callable[[Path], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Per account: placements, decisions and the top refusal statuses on the last market day."""
    d = desk or DESK
    t = now or datetime.now(UTC)
    day = last_market_day(t)
    read = reader or read_tail
    accounts: dict[str, Any] = {}
    for acct, sources in SOURCES.items():
        placed = decisions = 0
        newest: datetime | None = None
        whys: Counter[str] = Counter()
        present: list[str] = []
        for rel, kind in sources:
            p = d / rel
            if not p.exists():
                continue
            present.append(rel)
            for row in read(p):
                rt = row_time(row)
                if rt is None:
                    continue
                newest = rt if newest is None or rt > newest else newest
                if rt.astimezone(UTC).date() != day:
                    continue
                decisions += 1
                if _placed(kind, row):
                    placed += 1
                else:
                    whys[_why(kind, row)] += 1
        accounts[acct] = {
            "journals": present,
            "placed": placed,
            "decisions": decisions,
            "top_refusals": [{"why": w, "n": n} for w, n in whys.most_common(5)],
            "newest_row_at": newest.isoformat(timespec="seconds") if newest else None,
            "lanes": _lane_status(d, LANE_REPORTS.get(acct, ())),
        }
    return {"market_day": day.isoformat(), "accounts": accounts}


def diagnose(acct: str, facts: Mapping[str, Any],
             adoption: Mapping[str, Any] | None = None) -> str:
    """One paragraph a person could act on, built only from what was measured."""
    parts: list[str] = []
    if not facts.get("journals"):
        parts.append("none of its lane journals exist on this box, so the lane never ran here")
    elif not facts.get("decisions"):
        parts.append(f"its lanes wrote no decision at all that day (newest row "
                     f"{facts.get('newest_row_at') or 'never'}): the lane did not run")
    else:
        tops = ", ".join(f"{r['why']} x{r['n']}" for r in facts.get("top_refusals") or [])
        parts.append(f"{facts['decisions']} decisions, none placed; commonest: {tops}")
    behind = (adoption or {}).get("commits_behind")
    if isinstance(behind, int) and behind > 0:
        parts.append(f"the box is {behind} commit(s) behind the shipped branch (HEAD "
                     f"{(adoption or {}).get('head')}), the 2026-11-19 cause: the adoption "
                     f"task is re-run by the adoption_lag repair")
    lanes = facts.get("lanes") or {}
    if lanes:
        parts.append("lanes: " + "; ".join(f"{k} {v}" for k, v in lanes.items())[:300])
    return f"{acct}: " + ". ".join(parts)
