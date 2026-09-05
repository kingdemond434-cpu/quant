"""The decision dataset: every minute the desk decided anything, as ONE versioned row.

    D_t = (WorldState, CandidateActions, ChosenAction, Outcome, CounterfactualOutcomes)

WHY ONE ROW. The desk already writes eleven append-only ledgers about its own behaviour, and
no two of them share a key. The gateway records the bracket it considered (`decision_ledger`,
keyed sleeve/side/time), the order it sent (`order_intents`, keyed ticket), the deal that closed
(`live_ledger`, keyed deal, joined to the intent only through the deal's order number), the
position each sleeve wanted (`theoretical_positions`, keyed sleeve/symbol/at) and what the
market algorithm expected against what it got (`execution_algo_outcomes`, keyed symbol/side/
lots/at). The allocator logs the book it expected (`pf_forecast_log`, one line per pass) and the
capital-modifier category it claimed (`capital_modifier_ledger`, per sleeve per pass). Three
feedback engines price closed trades after the fact, each keyed its own way. Every one of them
answers one question about one moment; none of them can answer "what was the desk looking at,
what could it have done, what did it do, and what happened" for the same minute, because that
row was never assembled. This module assembles it, once, and keeps it.

THE JOIN RULES, one per ledger -- the contract this module keeps, stated where a reader of the
dataset can find it (`JOIN_RULES` carries the same text at runtime):

    decision_ledger          PRIMARY. One dataset row per (sleeve, symbol, side, minute). A row
                             recorded with no side and a bracket in `detail` (the release
                             identity refusing new risk) becomes one row per leg.
    order_intents            PRIMARY for the family and scalp lanes, which record an intent and
                             never a decision: an intent with no decision row at its (sleeve,
                             symbol, minute, side) is itself the decision, taken when the venue
                             accepted it (retcode 10008/10009). SECONDARY for brackets: joined
                             on the same key, it adds the quote, the spread, the policy
                             competition and the ticket.
    live_ledger              OUTCOME. Joined on the deal's `order` == the intent's `ticket`;
                             when no ticket matches, the first unclaimed deal of the same sleeve
                             and symbol after the minute (join_key "sleeve_time", counted so the
                             report can say how many were fuzzy). A taken row with no deal yet
                             is PENDING and re-joined on the next run.
    theoretical_positions    WORLD STATE. The sleeve's last asserted target on the symbol at or
                             before the minute: the position the decision was made inside.
    execution_algo_outcomes  OUTCOME. Expected against realised cost, joined on (symbol, side,
                             lots) at the nearest `at` within JOIN_TOLERANCE_S of the minute.
                             Only the `market` plan is ever recorded, which is why the
                             counterfactual world prices the others.
    broker_clock             WORLD STATE. A singleton: the terminal's UTC offset, so the
                             broker hour can be reconstructed from the minute.
    pf_forecast_log          WORLD STATE. The last allocator pass at or before the minute: the
                             book (the sleeve's fraction h), total heat, the binding constraint,
                             the regime probabilities.
    capital_modifier_ledger  WORLD STATE / CHOSEN SIZE. The sleeve's last category at or before
                             the minute; its multiplier is the size the desk chose against the
                             allocator's 1.0x unless the row itself carries `size_mult`.
    counterfactuals          OUTCOME (prior). `counterfactual_markout`'s replay of a not-taken
                             bracket, joined on (sleeve, side, time) verbatim -- kept as a
                             cross-check against this dataset's own pricing.
    action_counterfactuals   OUTCOME (prior). Hold alternatives of a taken trade, joined on
                             (sleeve, minute of entry_time).
    excursions               OUTCOME. MFE / MAE of a taken trade, joined the same way.

The state vector is not a ledger: its id is stamped on the decision and intent rows at write
time and is carried as `world_state_id`; `data/state_vector.json` is only ever the CURRENT one.

VERSIONING AND THE WATERMARK. `data/decision_dataset.jsonl` is append-only. A row is identified
by `row_id` (symbol, sleeve, side, minute); its `version` starts at 1 and rises by one each
time its outcome or counterfactual content changes -- a deal that closes days after the intent,
bars that arrive and let the counterfactual be priced. The last line per row_id is the truth
and `latest()` collapses to it. `append()` refuses a line whose (row_id, fingerprint) is already
the last one on file, so a re-run over the same ledgers writes nothing, whatever the watermark
says. The watermark (`decision_dataset_watermark.json`) records how many lines of each ledger
the last run consumed and which rows were still unresolved; `join()` builds rows only for
primary lines past the watermark and for the unresolved ids, so a run costs the new work, not
the whole history. `read()` yields rows by schema version so a consumer can pin the shape it
was written against.

Assembles and records. Prices nothing (that is `counterfactual_world`), decides nothing.
"""
from __future__ import annotations

import bisect
import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CANDIDATE_MENU",
    "JOIN_RULES",
    "JOIN_TOLERANCE_S",
    "LEDGER_FILES",
    "LEDGER_NAMES",
    "OK_RETCODES",
    "PRIMARY",
    "RETRY_STATUSES",
    "SCHEMA_VERSION",
    "DatasetRow",
    "Watermark",
    "append",
    "join",
    "latest",
    "ledger_counts",
    "load_ledgers",
    "minute_of",
    "pending_ids",
    "read",
    "read_ledger",
    "row_id",
]

Row = dict[str, Any]
Ledger = list[tuple[int, Row]]

SCHEMA_VERSION: int = 1

LEDGER_NAMES: tuple[str, ...] = (
    "decision_ledger", "order_intents", "live_ledger", "theoretical_positions",
    "execution_algo_outcomes", "broker_clock", "pf_forecast_log", "capital_modifier_ledger",
    "counterfactuals", "action_counterfactuals", "excursions",
)
#: Where each ledger lives, relative to the desk root (`desks/mt5`).
LEDGER_FILES: Mapping[str, str] = {
    "decision_ledger": "data/decision_ledger.jsonl",
    "order_intents": "data/order_intents.jsonl",
    "live_ledger": "data/live_ledger.jsonl",
    "theoretical_positions": "data/theoretical_positions.jsonl",
    "execution_algo_outcomes": "data/execution_algo_outcomes.jsonl",
    "broker_clock": "data/broker_clock.json",
    "pf_forecast_log": "data/pf_forecast_log.jsonl",
    "capital_modifier_ledger": "data/capital_modifier_ledger.jsonl",
    "counterfactuals": "data/counterfactuals.jsonl",
    "action_counterfactuals": "data/action_counterfactuals.jsonl",
    "excursions": "data/excursions.jsonl",
}
PRIMARY: tuple[str, ...] = ("decision_ledger", "order_intents")
#: The join rule per ledger, as prose, carried on the report so the dataset explains itself.
JOIN_RULES: Mapping[str, str] = {
    "decision_ledger": "PRIMARY: one row per (sleeve, symbol, side, minute); a side-less row "
                       "with a bracket in `detail` becomes one row per leg",
    "order_intents": "PRIMARY for family/scalp intents with no decision row at (sleeve, symbol, "
                     "minute, side), taken iff retcode in 10008/10009; SECONDARY for brackets: "
                     "quote, spread, policy competition, ticket",
    "live_ledger": "OUTCOME: deal.order == intent.ticket, else first unclaimed deal of the "
                   "sleeve+symbol after the minute (join_key sleeve_time); no deal -> PENDING",
    "theoretical_positions": "WORLD STATE: last target of (sleeve, symbol) at or before the "
                             "minute",
    "execution_algo_outcomes": "OUTCOME: (symbol, side, lots) nearest `at` within "
                               f"{60} s of the minute; market plan only",
    "broker_clock": "WORLD STATE: singleton utc_offset_hours -> broker hour",
    "pf_forecast_log": "WORLD STATE: last pass at or before the minute -> h, heat, binding, regime",
    "capital_modifier_ledger": "WORLD STATE / CHOSEN SIZE: sleeve's last category at or before "
                               "the minute -> size_mult unless the row carries one",
    "counterfactuals": "OUTCOME (prior): (sleeve, side, time) verbatim",
    "action_counterfactuals": "OUTCOME (prior): (sleeve, minute of entry_time)",
    "excursions": "OUTCOME: (sleeve, minute of entry_time) -> mfe_r, mae_r",
}
JOIN_TOLERANCE_S: float = 60.0
#: MT5 TRADE_RETCODE_PLACED / TRADE_RETCODE_DONE: the venue accepted the order.
OK_RETCODES: frozenset[int] = frozenset({10008, 10009})
#: Statuses a later run must revisit: the outcome has not closed, or the counterfactual could
#: not be priced yet (bars not arrived, or none on this host).
RETRY_STATUSES: frozenset[str] = frozenset({"PENDING", "UNPRICED", "NO_BARS"})
#: The alternatives every row is priced against -- the CandidateActions menu.
CANDIDATE_MENU: Mapping[str, tuple[Any, ...]] = {
    "sizes": (0.5, 1.0, 1.5),
    "executions": ("market", "limit", "delayed"),
    "exits": ("fixed_tp", "trail", "hold", "partial"),
}


# --------------------------------------------------------------------------- reading ledgers
def read_ledger(path: Path | str) -> Ledger:
    """(offset, row) for every readable JSON object in a file. A `.jsonl` gives one per line
    (a torn final line is skipped, never fatal); a `.json` singleton gives [(0, obj)]. The
    offset is the physical 0-based line number, which an append-only ledger never moves."""
    p = Path(path)
    try:
        text = p.read_text("utf-8")
    except OSError:
        return []
    if p.suffix == ".json":
        try:
            obj = json.loads(text)
        except ValueError:
            return []
        return [(0, obj)] if isinstance(obj, dict) else []
    out: Ledger = []
    for i, ln in enumerate(text.splitlines()):
        s = ln.strip()
        if not s:
            continue
        try:
            r = json.loads(s)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append((i, r))
    return out


def load_ledgers(base: Path | str) -> dict[str, Ledger]:
    """Every ledger under a desk root, by name; a missing file is an empty ledger."""
    b = Path(base)
    return {name: read_ledger(b / rel) for name, rel in LEDGER_FILES.items()}


# --------------------------------------------------------------------------- time and keys
def _ts(v: Any) -> datetime | None:
    """A UTC-aware datetime from the ledgers' stamps (ISO with offset, 'Z', or naive = UTC)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo is not None else v.replace(tzinfo=UTC)
    s = str(v).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d.astimezone(UTC) if d.tzinfo is not None else d.replace(tzinfo=UTC)


def minute_of(v: Any) -> str | None:
    """The decision minute: the stamp floored to the minute, UTC, ISO."""
    d = _ts(v)
    return d.replace(second=0, microsecond=0).isoformat() if d is not None else None


def row_id(symbol: str, sleeve: str, side: str, minute: str) -> str:
    """The row's identity: what was decided, where, when. Stable across versions."""
    key = f"{symbol}|{sleeve}|{side}|{minute}"
    # sha1 is an ADDRESS here, not a secret: short, stable, and never authenticating anything.
    return hashlib.sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def _int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _dict(v: Any) -> dict[str, Any]:
    """A nested object as a dict; anything else (absent, a string, a list) is empty. The ledgers
    are hand-written JSON and a field that should carry an object sometimes does not."""
    return {str(k): val for k, val in v.items()} if isinstance(v, dict) else {}


# --------------------------------------------------------------------------- the row
@dataclass
class DatasetRow:
    """One decision minute. `to_row()` is the JSON line; the field order is the schema."""

    row_id: str
    minute: str
    symbol: str
    sleeve: str
    side: str
    world_state_id: str
    world_state: dict[str, Any]
    candidate_actions: list[dict[str, Any]]
    chosen_action: dict[str, Any]
    outcome: dict[str, Any]
    counterfactual_outcomes: dict[str, Any] = field(default_factory=lambda: {"status": "UNPRICED"})
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    version: int = 1
    written_utc: str = ""

    def fingerprint(self) -> str:
        """What a new version is FOR: the outcome and the counterfactuals. World state and the
        chosen action are facts of the minute and never change after it."""
        blob = json.dumps({"o": self.outcome, "c": self.counterfactual_outcomes}, sort_keys=True,
                          default=str)
        return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]

    def to_row(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "row_id": self.row_id,
                "version": self.version, "minute": self.minute, "symbol": self.symbol,
                "sleeve": self.sleeve, "side": self.side, "world_state_id": self.world_state_id,
                "world_state": self.world_state, "candidate_actions": self.candidate_actions,
                "chosen_action": self.chosen_action, "outcome": self.outcome,
                "counterfactual_outcomes": self.counterfactual_outcomes,
                "provenance": self.provenance, "fingerprint": self.fingerprint(),
                "written_utc": self.written_utc}

    @classmethod
    def from_row(cls, r: Mapping[str, Any]) -> DatasetRow:
        return cls(row_id=str(r.get("row_id") or ""), minute=str(r.get("minute") or ""),
                   symbol=str(r.get("symbol") or ""), sleeve=str(r.get("sleeve") or ""),
                   side=str(r.get("side") or ""),
                   world_state_id=str(r.get("world_state_id") or ""),
                   world_state=dict(r.get("world_state") or {}),
                   candidate_actions=list(r.get("candidate_actions") or []),
                   chosen_action=dict(r.get("chosen_action") or {}),
                   outcome=dict(r.get("outcome") or {}),
                   counterfactual_outcomes=dict(r.get("counterfactual_outcomes")
                                                or {"status": "UNPRICED"}),
                   provenance=dict(r.get("provenance") or {}),
                   schema_version=int(r.get("schema_version") or SCHEMA_VERSION),
                   version=int(r.get("version") or 1),
                   written_utc=str(r.get("written_utc") or ""))


# --------------------------------------------------------------------------- the watermark
@dataclass
class Watermark:
    """How far the last run read each ledger, and which rows it left unresolved."""

    ledger_lines: dict[str, int] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    rows_written: int = 0
    runs: int = 0
    last_run_utc: str = ""
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path | str) -> Watermark:
        try:
            d = json.loads(Path(path).read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(d, dict):
            return cls()
        lines = _dict(d.get("ledger_lines"))
        return cls(ledger_lines={str(k): int(v) for k, v in lines.items()},
                   pending=[str(x) for x in (d.get("pending") or [])],
                   rows_written=int(d.get("rows_written") or 0), runs=int(d.get("runs") or 0),
                   last_run_utc=str(d.get("last_run_utc") or ""),
                   schema_version=int(d.get("schema_version") or SCHEMA_VERSION))

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"schema_version": self.schema_version,
                                 "ledger_lines": self.ledger_lines, "pending": self.pending,
                                 "rows_written": self.rows_written, "runs": self.runs,
                                 "last_run_utc": self.last_run_utc}, indent=1), "utf-8")

    def unchanged(self, counts: Mapping[str, int]) -> bool:
        """Nothing grew and nothing is pending: a run would find no work."""
        return (not self.pending and bool(self.ledger_lines)
                and all(int(counts.get(k, 0)) <= int(self.ledger_lines.get(k, 0))
                        for k in LEDGER_NAMES))


def ledger_counts(ledgers: Mapping[str, Ledger]) -> dict[str, int]:
    """Lines consumed per ledger = the last offset + 1 (a torn tail is not counted as read)."""
    return {name: (rows[-1][0] + 1 if rows else 0) for name, rows in ledgers.items()}


# --------------------------------------------------------------------------- indexes
class _Timeline:
    """Rows of one key sorted by time, for 'last at or before t' and 'first after t'."""

    def __init__(self) -> None:
        self.times: list[datetime] = []
        self.items: list[tuple[int, Row]] = []

    def add(self, t: datetime, off: int, row: Row) -> None:
        i = bisect.bisect_right(self.times, t)
        self.times.insert(i, t)
        self.items.insert(i, (off, row))

    def last_at_or_before(self, t: datetime) -> tuple[int, Row] | None:
        i = bisect.bisect_right(self.times, t)
        return self.items[i - 1] if i > 0 else None

    def nearest(self, t: datetime, tol_s: float) -> tuple[int, Row] | None:
        i = bisect.bisect_left(self.times, t)
        best: tuple[int, Row] | None = None
        best_d = tol_s
        for j in (i - 1, i):
            if 0 <= j < len(self.times):
                d = abs((self.times[j] - t).total_seconds())
                if d <= best_d:
                    best, best_d = self.items[j], d
        return best

    def after(self, t: datetime) -> list[tuple[int, Row]]:
        return self.items[bisect.bisect_right(self.times, t):]


def _side_of_deal(v: Any) -> str:
    s = str(v).lower()
    if s in ("0", "0.0", "buy", "long"):
        return "buy"
    if s in ("1", "1.0", "sell", "short"):
        return "sell"
    return ""


def _base_side(side: str) -> str:
    return "buy" if side.startswith("buy") else ("sell" if side.startswith("sell") else "")


class _Index:
    """Every secondary ledger indexed the way its join rule reads it."""

    def __init__(self, ledgers: Mapping[str, Ledger]) -> None:
        self.intents_by_key: dict[tuple[str, str, str, str], list[tuple[int, Row]]] = {}
        self.intents_by_ticket: dict[int, tuple[int, Row]] = {}
        for off, r in ledgers.get("order_intents", []):
            m = minute_of(r.get("time"))
            if m is None:
                continue
            self.intents_by_key.setdefault(
                (str(r.get("sleeve") or ""), str(r.get("symbol") or ""), m,
                 str(r.get("side") or "")), []).append((off, r))
            tk = _int(r.get("ticket"))
            if tk is not None:
                self.intents_by_ticket[tk] = (off, r)
        self.deals_by_order: dict[int, tuple[int, Row]] = {}
        self.deals_by_sleeve: dict[tuple[str, str], _Timeline] = {}
        for off, r in ledgers.get("live_ledger", []):
            o = _int(r.get("order"))
            if o is not None and o not in self.deals_by_order:
                self.deals_by_order[o] = (off, r)
            dt = _ts(r.get("time"))
            if dt is not None:
                self.deals_by_sleeve.setdefault(
                    (str(r.get("sleeve") or ""), str(r.get("symbol") or "")),
                    _Timeline()).add(dt, off, r)
        self.positions: dict[tuple[str, str], _Timeline] = {}
        for off, r in ledgers.get("theoretical_positions", []):
            if r.get("kind") != "target":
                continue
            pt = _ts(r.get("at"))
            if pt is None:
                continue
            self.positions.setdefault(
                (str(r.get("sleeve") or ""), str(r.get("symbol") or "")),
                _Timeline()).add(pt, off, r)
        self.algo: dict[tuple[str, str, float], _Timeline] = {}
        for off, r in ledgers.get("execution_algo_outcomes", []):
            at = _ts(r.get("at"))
            lots = _num(r.get("lots"))
            if at is None or lots is None:
                continue
            self.algo.setdefault(
                (str(r.get("symbol") or ""), _base_side(str(r.get("side") or "")),
                 round(lots, 8)), _Timeline()).add(at, off, r)
        clock = ledgers.get("broker_clock", [])
        self.clock: tuple[int, Row] | None = clock[0] if clock else None
        self.forecasts = _Timeline()
        for off, r in ledgers.get("pf_forecast_log", []):
            ft = _ts(r.get("t"))
            if ft is not None:
                self.forecasts.add(ft, off, r)
        self.capmod: dict[str, _Timeline] = {}
        for off, r in ledgers.get("capital_modifier_ledger", []):
            ct = _ts(r.get("t"))
            if ct is not None:
                self.capmod.setdefault(str(r.get("sleeve") or ""), _Timeline()).add(ct, off, r)
        self.cf: dict[tuple[str, str, str], tuple[int, Row]] = {}
        for off, r in ledgers.get("counterfactuals", []):
            self.cf.setdefault((str(r.get("sleeve") or ""), str(r.get("side") or ""),
                                str(r.get("time") or "")), (off, r))
        self.ac: dict[tuple[str, str], tuple[int, Row]] = {}
        for off, r in ledgers.get("action_counterfactuals", []):
            m = minute_of(r.get("entry_time"))
            if m is not None:
                self.ac.setdefault((str(r.get("sleeve") or ""), m), (off, r))
        self.exc: dict[tuple[str, str], tuple[int, Row]] = {}
        for off, r in ledgers.get("excursions", []):
            m = minute_of(r.get("entry_time"))
            if m is not None:
                self.exc.setdefault((str(r.get("sleeve") or ""), m), (off, r))
        self.claimed_deals: set[int] = set()


# --------------------------------------------------------------------------- assembling
def _world_state(ix: _Index, sleeve: str, symbol: str, t: datetime, intent: Row | None,
                 prov: dict[str, list[int]], base: Row) -> dict[str, Any]:
    ws: dict[str, Any] = {
        "release_id": str(base.get("release_id") or (intent or {}).get("release_id") or ""),
        "hour_utc": t.hour, "weekday": t.weekday(),
    }
    if ix.clock is not None:
        off, c = ix.clock
        offh = _num(c.get("utc_offset_hours"))
        ws["broker_utc_offset_hours"] = offh
        ws["broker_hour"] = (int((t.hour + offh) % 24) if offh is not None else None)
        prov.setdefault("broker_clock", []).append(off)
    if intent is not None:
        bid, ask = _num(intent.get("decision_bid")), _num(intent.get("decision_ask"))
        spread = _num(intent.get("spread_at_decision"))
        ref = _num(intent.get("intended"))
        if spread is None and bid is not None and ask is not None:
            spread = ask - bid
        ws["quote"] = {"bid": bid, "ask": ask, "intended": ref, "spread": spread,
                       "spread_frac": (spread / ref if spread is not None and ref
                                       else None),
                       "point": _num(intent.get("point")),
                       "stops_level": _int(intent.get("stops_level"))}
    fc = ix.forecasts.last_at_or_before(t)
    if fc is not None:
        off, f = fc
        book = _dict(f.get("book"))
        h = _num(book.get(sleeve))
        ws["allocator"] = {"t": f.get("t"), "mode": f.get("mode"),
                           "total_heat": _num(f.get("total_heat")), "binding": f.get("binding"),
                           "expected_log_per_day": _num(f.get("expected_log_per_day")),
                           "h": h, "h_source": ("pf_forecast_log book" if h else "unfunded"),
                           "regime": _dict(f.get("regime")), "n_book": len(book)}
        prov.setdefault("pf_forecast_log", []).append(off)
    cm = ix.capmod.get(sleeve)
    last = cm.last_at_or_before(t) if cm is not None else None
    if last is not None:
        off, c = last
        ws["capital_modifier"] = {"t": c.get("t"), "category": c.get("category"),
                                  "multiplier": _num(c.get("multiplier")),
                                  "state": c.get("state"), "n_state": _int(c.get("n_state"))}
        prov.setdefault("capital_modifier_ledger", []).append(off)
    pos = ix.positions.get((sleeve, symbol))
    lastp = pos.last_at_or_before(t) if pos is not None else None
    if lastp is not None:
        off, p = lastp
        ws["position"] = {"lots": _num(p.get("lots")), "reason": p.get("reason"),
                          "at": p.get("at"), "price": _num(p.get("price"))}
        prov.setdefault("theoretical_positions", []).append(off)
    # the symbol's whole theoretical book at the minute: every sleeve's last target
    book_lots = 0.0
    n_sleeves = 0
    for (sl, sym), tl in ix.positions.items():
        if sym != symbol:
            continue
        lp = tl.last_at_or_before(t)
        if lp is not None:
            v = _num(lp[1].get("lots"))
            if v:
                book_lots += v
                n_sleeves += 1 if sl != sleeve else 0
    if n_sleeves or lastp is not None:
        ws["symbol_book"] = {"net_lots": round(book_lots, 8), "other_sleeves": n_sleeves}
    return ws


def _outcome(ix: _Index, sleeve: str, symbol: str, side: str, t: datetime, minute: str,
             time_verbatim: str, taken: bool, ticket: int | None, intent: Row | None,
             lot: float | None, prov: dict[str, list[int]]) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "NOT_APPLICABLE" if not taken else "PENDING",
                           "join_key": None}
    deal: tuple[int, Row] | None = None
    if taken:
        if ticket is not None and ticket in ix.deals_by_order:
            deal = ix.deals_by_order[ticket]
            out["join_key"] = "ticket"
        else:
            tl = ix.deals_by_sleeve.get((sleeve, symbol))
            if tl is not None:
                for off, d in tl.after(t):
                    if off in ix.claimed_deals:
                        continue
                    deal = (off, d)
                    out["join_key"] = "sleeve_time"
                    break
    if deal is not None:
        off, d = deal
        ix.claimed_deals.add(off)
        prov.setdefault("live_ledger", []).append(off)
        entry, fill = _num(d.get("entry_price")), _num(d.get("fill_price"))
        ref = _num((intent or {}).get("intended"))
        dirn = 1.0 if _base_side(side) == "buy" else -1.0
        out.update({"status": "RESOLVED", "r_multiple": _num(d.get("r_multiple")),
                    "pl_quote": _num(d.get("pl_quote")), "entry_price": entry,
                    "fill_price": fill, "exit_time": d.get("time"), "deal": d.get("deal"),
                    "commission": _num(d.get("commission")), "swap": _num(d.get("swap")),
                    "volume": _num(d.get("volume")),
                    "r_unreconstructible": bool(d.get("r_unreconstructible")),
                    "deal_side": _side_of_deal(d.get("side")),
                    "slippage_frac": (round((entry - ref) * dirn / ref, 8)
                                      if entry is not None and ref else None)})
    if intent is not None:
        out["retcode"] = _int(intent.get("retcode"))
        out["latency_ms"] = _num(intent.get("latency_ms"))
        if lot is None:
            lot = _num(intent.get("lot"))
    if lot is not None:
        tl = ix.algo.get((symbol, _base_side(side), round(lot, 8)))
        near = tl.nearest(t, JOIN_TOLERANCE_S) if tl is not None else None
        if near is not None:
            off, a = near
            out["execution"] = {"algo": a.get("algo"),
                                "expected_cost_frac": _num(a.get("expected_cost")),
                                "realised_cost_frac": _num(a.get("realised_cost")),
                                "filled_frac": _num(a.get("filled_frac")),
                                "expected_p_fill": _num(a.get("expected_p_fill"))}
            prov.setdefault("execution_algo_outcomes", []).append(off)
    cf = ix.cf.get((sleeve, side, time_verbatim))
    if cf is not None:
        off, c = cf
        out["prior_counterfactual"] = {"status": c.get("status"), "r": _num(c.get("r")),
                                       "exit_reason": c.get("exit_reason"),
                                       "engine": "counterfactual_markout"}
        prov.setdefault("counterfactuals", []).append(off)
    ac = ix.ac.get((sleeve, minute))
    if ac is not None:
        off, a = ac
        out["prior_hold"] = {"hold": a.get("hold"), "bars_held": a.get("bars_held"),
                             "opposite_r": _num(a.get("opposite_r")),
                             "engine": "action_counterfactuals"}
        prov.setdefault("action_counterfactuals", []).append(off)
    ex = ix.exc.get((sleeve, minute))
    if ex is not None:
        off, e = ex
        out["mfe_r"] = _num(e.get("mfe_r"))
        out["mae_r"] = _num(e.get("mae_r"))
        prov.setdefault("excursions", []).append(off)
    return out


def _candidates(intent: Row | None) -> list[dict[str, Any]]:
    advice = _dict((intent or {}).get("policy_advice"))
    alts = _dict(advice.get("alternatives"))
    return [{"kind": "enter", "sizes": list(CANDIDATE_MENU["sizes"]),
             "executions": list(CANDIDATE_MENU["executions"]),
             "exits": list(CANDIDATE_MENU["exits"]),
             "policy_alternatives": {str(k): _num(v) for k, v in alts.items()}},
            {"kind": "skip"}]


def _chosen(base: Row, intent: Row | None, taken: bool, side: str, ws: dict[str, Any],
            lot: float | None) -> dict[str, Any]:
    advice = _dict((intent or {}).get("policy_advice"))
    policy = str(advice.get("policy")) if advice.get("policy") else None
    execution = str(base.get("execution") or (intent or {}).get("order_type") or
                    ("pending_stop" if side.endswith("_stop") else "market"))
    sm = _num(base.get("size_mult"))
    if sm is None:
        sm = _num(_dict(ws.get("capital_modifier")).get("multiplier"))
    return {"kind": "enter" if taken else "skip", "side": side,
            "price": _num(base.get("price") if base.get("price") is not None
                          else (intent or {}).get("intended")),
            "sl": _num(base.get("sl") if base.get("sl") is not None else (intent or {}).get("sl")),
            "tp": _num(base.get("tp") if base.get("tp") is not None else (intent or {}).get("tp")),
            "lot": lot, "size_mult": sm if sm is not None else 1.0,
            "size_mult_source": ("row" if _num(base.get("size_mult")) is not None else
                                 ("capital_modifier_ledger" if sm is not None else "default 1.0")),
            "execution": execution, "policy": policy,
            "policy_utility": _num(advice.get("utility")),
            "exit_rule": str(base.get("exit_rule") or "fixed_tp"),
            "veto_reason": ("" if taken else str(base.get("veto_reason") or base.get("reason")
                                                 or "")),
            "reason": str(base.get("reason") or ""),
            "detail": (str(base.get("detail"))[:200] if isinstance(base.get("detail"), str)
                       else None),
            "ticket": _int(base.get("ticket") if base.get("ticket") is not None
                           else (intent or {}).get("ticket")),
            "retcode": _int((intent or {}).get("retcode") if intent else base.get("retcode"))}


def _legs(d: Row) -> list[Row]:
    """A decision row per leg. A side-less refusal with the bracket spec in `detail` is the
    release identity refusing new risk: both legs it refused become rows."""
    if str(d.get("side") or ""):
        return [d]
    spec = d.get("detail")
    if not isinstance(spec, dict):
        return [d]
    out: list[Row] = []
    for leg in ("buy_stop", "sell_stop"):
        lg = spec.get(leg)
        if isinstance(lg, dict):
            out.append({**d, "side": leg, "price": lg.get("price"), "sl": lg.get("sl"),
                        "tp": lg.get("tp"), "detail": "release_identity_refused bracket"})
    return out or [d]


def join(ledgers: Mapping[str, Ledger], *, since: Mapping[str, int] | None = None,
         pending: Iterable[str] = (), now: datetime | None = None) -> list[DatasetRow]:
    """Assemble dataset rows from the ledgers by the rules above.

    `since` is the watermark's consumed line count per PRIMARY ledger: a primary line below it
    is re-joined only when its row_id is in `pending`. Secondary ledgers are always read in
    full (they are indexed, and a join is a lookup). Rows come back sorted by minute so the
    fuzzy deal join claims deals in decision order.
    """
    since = dict(since or {})
    pend = set(pending)
    ix = _Index(ledgers)
    stamp = (now or datetime.now(tz=UTC)).isoformat()
    work: list[tuple[datetime, str, int, Row, Row | None, int | None]] = []
    claimed_intents: set[int] = set()

    for off, d0 in ledgers.get("decision_ledger", []):
        for d in _legs(d0):
            m = minute_of(d.get("time") or d.get("decided_at"))
            t = _ts(d.get("time") or d.get("decided_at"))
            if m is None or t is None:
                continue
            sleeve, symbol = str(d.get("sleeve") or ""), str(d.get("symbol") or "")
            side = str(d.get("side") or "")
            rid = row_id(symbol, sleeve, side, m)
            # the intent this decision produced, claimed so it is not a second row
            cands = ix.intents_by_key.get((sleeve, symbol, m, side), [])
            tk = _int(d.get("ticket"))
            picked: tuple[int, Row] | None = None
            for cand_off, it in cands:
                if cand_off in claimed_intents:
                    continue
                if tk is None or _int(it.get("ticket")) == tk:
                    picked = (cand_off, it)
                    break
            if picked is None and tk is not None and tk in ix.intents_by_ticket:
                picked = ix.intents_by_ticket[tk]
            if picked is not None:
                claimed_intents.add(picked[0])
            if off < since.get("decision_ledger", 0) and rid not in pend:
                continue
            work.append((t, "decision_ledger", off, d, picked[1] if picked else None,
                         picked[0] if picked else None))

    for off, it in ledgers.get("order_intents", []):
        if off in claimed_intents:
            continue
        m = minute_of(it.get("time"))
        t = _ts(it.get("time"))
        if m is None or t is None:
            continue
        sleeve, symbol = str(it.get("sleeve") or ""), str(it.get("symbol") or "")
        side = str(it.get("side") or "")
        rid = row_id(symbol, sleeve, side, m)
        if off < since.get("order_intents", 0) and rid not in pend:
            continue
        rc = _int(it.get("retcode"))
        taken = rc in OK_RETCODES
        synth: Row = {"sleeve": sleeve, "symbol": symbol, "side": side, "time": it.get("time"),
                      "lot": it.get("lot"), "price": it.get("intended"), "sl": it.get("sl"),
                      "tp": it.get("tp"), "taken": taken,
                      "reason": "placed" if taken else "broker_rejected",
                      "veto_reason": "" if taken else "broker_rejected",
                      "ticket": it.get("ticket"), "retcode": rc,
                      "state_vector_id": it.get("state_vector_id"),
                      "release_id": it.get("release_id")}
        work.append((t, "order_intents", off, synth, it, off))

    work.sort(key=lambda w: (w[0], w[1], w[2]))
    rows: list[DatasetRow] = []
    for t, source, off, base, intent, ioff in work:
        m = minute_of(t)
        if m is None:
            continue
        sleeve, symbol = str(base.get("sleeve") or ""), str(base.get("symbol") or "")
        side = str(base.get("side") or "")
        taken = bool(base.get("taken"))
        prov: dict[str, list[int]] = {}
        prov.setdefault(source, []).append(off)
        if intent is not None and ioff is not None and source != "order_intents":
            prov.setdefault("order_intents", []).append(ioff)
        ws = _world_state(ix, sleeve, symbol, t, intent, prov, base)
        lot = _num(base.get("lot"))
        if lot is None and intent is not None:
            lot = _num(intent.get("lot"))
        chosen = _chosen(base, intent, taken, side, ws, lot)
        outcome = _outcome(ix, sleeve, symbol, side, t, m, str(base.get("time") or ""), taken,
                           chosen.get("ticket"), intent, lot, prov)
        wsid = str(base.get("world_state_id") or base.get("state_vector_id")
                   or (intent or {}).get("state_vector_id") or "")
        rows.append(DatasetRow(row_id=row_id(symbol, sleeve, side, m), minute=m, symbol=symbol,
                               sleeve=sleeve, side=side, world_state_id=wsid, world_state=ws,
                               candidate_actions=_candidates(intent), chosen_action=chosen,
                               outcome=outcome, provenance={"source": source, **prov},
                               written_utc=stamp))
    return rows


# --------------------------------------------------------------------------- the file
def read(path: Path | str, schema_version: int | None = None) -> Iterator[dict[str, Any]]:
    """Every line, in file order, optionally only one schema version. A torn line is skipped."""
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            for ln in fh:
                s = ln.strip()
                if not s:
                    continue
                try:
                    r = json.loads(s)
                except ValueError:
                    continue
                if not isinstance(r, dict):
                    continue
                if (schema_version is not None
                        and int(r.get("schema_version") or 0) != schema_version):
                    continue
                yield r
    except OSError:
        return


def latest(path: Path | str) -> dict[str, dict[str, Any]]:
    """The last version per row_id -- the truth of the dataset."""
    out: dict[str, dict[str, Any]] = {}
    for r in read(path):
        rid = str(r.get("row_id") or "")
        if rid:
            out[rid] = r
    return out


def _last_fingerprints(path: Path | str) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    for r in read(path):
        rid = str(r.get("row_id") or "")
        if rid:
            out[rid] = (int(r.get("version") or 1), str(r.get("fingerprint") or ""))
    return out


def append(rows: Sequence[DatasetRow], path: Path | str) -> int:
    """Append the rows whose content is new: a fresh row_id at version 1, a changed outcome or
    counterfactual at the next version. Anything already on file as the last version is
    skipped, so a re-run over unchanged ledgers writes zero lines. Returns lines written."""
    p = Path(path)
    last = _last_fingerprints(p)
    written = 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fp = row.fingerprint()
            prev = last.get(row.row_id)
            if prev is not None and prev[1] == fp:
                continue
            row.version = (prev[0] + 1) if prev is not None else 1
            fh.write(json.dumps(row.to_row(), default=str) + "\n")
            last[row.row_id] = (row.version, fp)
            written += 1
    return written


def pending_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Row ids a later run must revisit: an outcome not closed, a counterfactual not priced."""
    out: list[str] = []
    for r in rows:
        o = _dict(r.get("outcome"))
        c = _dict(r.get("counterfactual_outcomes"))
        if str(o.get("status")) in RETRY_STATUSES or str(c.get("status")) in RETRY_STATUSES:
            rid = str(r.get("row_id") or "")
            if rid:
                out.append(rid)
    return sorted(set(out))
