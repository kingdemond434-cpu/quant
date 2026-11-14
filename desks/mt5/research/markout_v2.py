#!/usr/bin/env python3
"""Execution slip in R, in PRICE units on both sides of the ratio, per account. REPORT ONLY.

WHY A V2. `markout.json` (mt5desk/markout.py, slip over the stop distance since #1057) refuses a
ledger holding more than one account, and the desk trades E8, FTMO and Fusion at once, so the
headline it publishes on the multi-account box is MIXED. This module measures each account on
its own, joins the box-only E8 fills to their placing intents, labels a stale ledger STALE and
signs the result from a bootstrap CI rather than a raw mean. It does not edit markout.py.

    slip_r = (fill - intended) * direction / |intended - stop|        all PRICE units
             positive = worse than asked (the markout.py convention)

    `intended` and `stop` are the INTENT's (what was asked), never the venue's held levels, so the
    denominator is the risk the sizing decision priced, not the distance left after the fill.

WHAT IT REFUSES TO DO
    * A row with no intended price, no stop, no fill, no direction, or a stop distance below the
      floor (one point, or 1e-5 of price) is UNMEASURED and counted under its reason. Never 0.0.
    * ONE ACCOUNT AT A TIME (markout.py:278-287 ported). Deals are split by (account key, server, kind);
      a ledger holding more than one account is MIXED and publishes no figure. Deals that join no
      intent are counted (`n_unjoined_deals`), never dropped silently.
    * ONE ROW PER POSITION. Partial closes share one entry; their deals collapse onto the intent
      ticket with a volume-weighted entry fill, so n is positions, not close deals.
    * STALE IS NOT MEASURED. The newest deal (or E8 fill) must be within `max_age_days` of
      `as_of`; otherwise the account is STALE and its headline median and mean are null.
    * The sign is CI-aware: WORSE/BETTER only when the bootstrap 95% CI of the mean excludes 0,
      INDISTINGUISHABLE when it spans 0, INSUFFICIENT_N below `MIN_N` (no CI is published).
    * E8 and Fusion are never blended. E8 fills are box-only; `--e8-fills` takes a JSONL file
      (`order_id`, `fill_price`|`avgPrice`, `time`) or the CSV export (filled_at_utc, window, side,
      lot, entry, sl, tp, position_id). The export has NO requested price: each fill is joined to
      its placing SENT intent (by id, else the exact stop+target echo in the same window and
      direction), and a fill whose intent is absent is UNMEASURED (`no_intended_price`).
    * Point in time: only intents stamped at or before `as_of`, and only deals recorded at or
      before it, are read. A row with no readable stamp is excluded, not assumed early.
    * Unparseable input lines are counted per file (`inputs.*.garbage_lines`).

Nothing here places, sizes or gates an order. It reads ledgers and writes one JSON report.

CLOCK: a step of the markout leg, not a process of its own. `daily_cycle._markout` (run hourly
as hourly_cycle leg `fill_markout`) calls `main([])` after markout.json is written, so this
module inherits that leg's clock and attestation row. By hand: `main(["--as-of", ISO])`.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
_ROOT = DESK.parents[1]
for _p in (str(DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.markout import (  # noqa: E402
    _direction,
    _echo,
    _entry_fill,
    _join_ticket,
    echo_join,
    load_jsonl,
    position_direction,
)
from mt5desk.provenance import split_by_account  # noqa: E402

Row = dict[str, Any]
UNMEASURED = "UNMEASURED"
STALE = "STALE"
MIXED = "MIXED"
INSUFFICIENT_N = "INSUFFICIENT_N"
INDISTINGUISHABLE = "INDISTINGUISHABLE"
FUSION_INTENTS = DESK / "data" / "order_intents.jsonl"
FUSION_LEDGER = DESK / "data" / "live_ledger.jsonl"
E8_INTENT_FILES = (DESK / "data" / "e8_intents.jsonl", DESK / "data" / "e8_gold_intents.jsonl")
E8_FILLS = DESK / "data" / "e8_fills.jsonl"
LEGACY = DESK / "reports" / "markout.json"
OUT = DESK / "reports" / "MARKOUT_V2.json"
#: The per-trade join (tickets, deal ids, fill prices and times). BOX ONLY: `**/reports/*` keeps
#: it out of git and no sync path names it. The published report carries aggregates only.
ROWS_OUT = DESK / "reports" / "MARKOUT_V2_ROWS.json"
#: Keys that describe one trade. None of them may reach the published report (Auditor MF1,
#: 2026-11-14): the repository is public, and a trade-level record is the account's own.
TRADE_KEYS = frozenset({"rows", "latest_fill_at"})


def public_view(doc: Any) -> Any:
    """The report with every trade-level key removed, at any depth: aggregates only."""
    if isinstance(doc, dict):
        return {k: public_view(v) for k, v in doc.items() if k not in TRADE_KEYS}
    if isinstance(doc, list):
        return [public_view(v) for v in doc]
    return doc
BOOT_N = 2000
BOOT_SEED = 20261020
#: Fewer measured positions than this publish no CI and no directional sign.
MIN_N = 20
#: The newest fill must be this recent for an account to read MEASURED. 14 days: Fusion has been
#: flat since 2026-10-13 and its fills remain the latest evidence, but a ledger older than the
#: queue's own staleness horizon is no longer a current execution figure.
MAX_AGE_DAYS = 14.0
#: Stop-distance floor relative to the intended price (0.1 pip on a ~1.0 FX quote, 0.04 on gold
#: at 4000). Below it the R unit is numerically meaningless (1e-10 would read 99,999R).
STOP_FLOOR_REL = 1e-5


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _stamp(x: Any) -> datetime | None:
    if x is None:
        return None
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _first_stamp(row: Row, keys: Iterable[str]) -> datetime | None:
    for k in keys:
        t = _stamp(row.get(k))
        if t is not None:
            return t
    return None


def _visible(row: Row, keys: Iterable[str], as_of: datetime) -> bool:
    """True when the row's first readable stamp is at or before `as_of`. No stamp: not visible."""
    t = _first_stamp(row, keys)
    return t is not None and t <= as_of


def slip_r(fill: Any, intended: Any, stop: Any, direction: int,
           point: Any = None) -> tuple[float | None, str]:
    """(slip in R, reason). The value is None, with the reason, whenever any input is missing."""
    f, w, s = _num(fill), _num(intended), _num(stop)
    if w is None or w <= 0:
        return None, "no_intended_price"
    if s is None or s <= 0:
        return None, "no_stop"
    if f is None or f <= 0:
        return None, "no_fill"
    if direction not in (1, -1):
        return None, "no_direction"
    dist = abs(w - s)
    if dist <= 0:
        return None, "zero_stop_distance"
    floor = max(_num(point) or 0.0, STOP_FLOOR_REL * w)
    if dist < floor:
        return None, "stop_below_floor"
    return (f - w) * direction / dist + 0.0, "measured"


def sign_label(x: float | None) -> str:
    """The raw sign of one number (used for the median). Not a significance claim."""
    if x is None:
        return UNMEASURED
    if x > 0:
        return "WORSE_THAN_ASKED"
    if x < 0:
        return "BETTER_THAN_ASKED"
    return "AT_ASKED"


def ci_sign(ci: list[float] | None, n: int) -> str:
    """Directional only when the 95% CI of the mean excludes 0."""
    if n == 0:
        return UNMEASURED
    if n < MIN_N or ci is None:
        return INSUFFICIENT_N
    lo, hi = ci
    if lo > 0:
        return "WORSE_THAN_ASKED"
    if hi < 0:
        return "BETTER_THAN_ASKED"
    return INDISTINGUISHABLE


def _boot_ci(xs: list[float]) -> list[float] | None:
    if len(xs) < MIN_N:
        return None
    rng = random.Random(BOOT_SEED)  # noqa: S311 -- bootstrap resampling, never a secret
    n = len(xs)
    means = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(BOOT_N))
    return [round(means[int(0.025 * BOOT_N)], 6) + 0.0,
            round(means[int(0.975 * BOOT_N) - 1], 6) + 0.0]


def freshness(latest: datetime | None, as_of: datetime,
              max_age_days: float = MAX_AGE_DAYS) -> dict[str, Any]:
    if latest is None:
        return {"latest_fill_at": None, "age_days": None, "max_age_days": max_age_days,
                "fresh": False}
    age = (as_of - latest).total_seconds() / 86400.0
    return {"latest_fill_at": latest.isoformat(timespec="seconds"), "age_days": round(age, 3),
            "max_age_days": max_age_days, "fresh": age <= max_age_days}


def summarise(rows: list[Row], fresh: dict[str, Any] | None = None) -> dict[str, Any]:
    """Median, mean, CI and sign over MEASURED rows; UNMEASURED rows are counted by reason only.

    `fresh` is the account's freshness block. Not fresh -> status STALE and null headline figures
    (the figures that would have been published are kept under `stale_*` for the record).
    """
    vals = [r["slip_r"] for r in rows if r.get("slip_r") is not None]
    reasons: dict[str, int] = {}
    for r in rows:
        if r.get("slip_r") is None:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    out: dict[str, Any] = {"n_rows": len(rows), "n_measured": len(vals),
                           "median_slip_r": None, "mean_slip_r": None, "mean_ci95": None,
                           "sign": UNMEASURED, "median_sign": UNMEASURED,
                           "unmeasured_by_reason": reasons, "status": UNMEASURED}
    if not vals:
        return out
    med = round(statistics.median(vals), 6) + 0.0
    mean = round(sum(vals) / len(vals), 6) + 0.0
    ci = _boot_ci(vals)
    if fresh is not None and not fresh.get("fresh"):
        out.update({"status": STALE, "sign": STALE, "median_sign": STALE,
                    "stale_median_slip_r": med, "stale_mean_slip_r": mean})
        return out
    out.update({"median_slip_r": med, "mean_slip_r": mean, "mean_ci95": ci,
                "sign": ci_sign(ci, len(vals)), "median_sign": sign_label(med),
                "status": "MEASURED" if len(vals) >= MIN_N else INSUFFICIENT_N})
    return out


def _group(rows: list[Row], key: str, fresh: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, list[Row]] = {}
    for r in rows:
        out.setdefault(str(r.get(key) or "UNKNOWN"), []).append(r)
    return {k: summarise(v, fresh) for k, v in sorted(out.items())}


def _order_type(intent: Row) -> str:
    """`market` or `pending`, from the intent's order_type, else its side string."""
    raw = str(intent.get("order_type") or "").lower()
    side = str(intent.get("side") or "").lower()
    if "pending" in raw or "stop" in side or "limit" in side:
        return "pending"
    return "market"


def _vwap(pairs: list[tuple[Any, Any]]) -> float | None:
    """Volume-weighted price of (price, volume) pairs; equal weights when volumes are missing."""
    pts = [(_num(p), _num(v)) for p, v in pairs]
    good = [(p, v) for p, v in pts if p is not None and p > 0]
    if not good:
        return None
    if all(v is not None and v > 0 for _, v in good):
        tot = sum(v for _, v in good if v is not None)
        return sum(p * v for p, v in good if v is not None) / tot
    return sum(p for p, _ in good) / len(good)


def fusion_rows(intents: list[Row], deals: list[Row],
                as_of: datetime) -> tuple[list[Row], int]:
    """(one row per POSITION that joins an intent, number of deals that joined none).

    `deals` must already be one account's. Partial closes collapse onto the intent ticket.
    """
    intents = [i for i in intents if _visible(i, ("time", "sent_at"), as_of)]
    by_ticket = {i["ticket"]: i for i in intents if i.get("ticket") is not None}
    keyed: set[int] = set()
    for d in deals:
        kt = _join_ticket(d, by_ticket)
        if kt is not None and d.get("entry_order") is not None:
            keyed.add(id(by_ticket[kt]))
    echoed = {id(d): it for it, d in echo_join(intents, deals, keyed, set())}
    positions: dict[Any, tuple[Row, list[Row]]] = {}
    unjoined = 0
    for d in deals:
        t = _join_ticket(d, by_ticket)
        intent = by_ticket.get(t) if t is not None else echoed.get(id(d))
        if intent is None:
            unjoined += 1
            continue
        positions.setdefault(intent.get("ticket"), (intent, []))[1].append(d)
    rows: list[Row] = []
    for ticket, (intent, ds) in positions.items():
        fill = _vwap([(_entry_fill(d), d.get("volume")) for d in ds])
        dirn = _direction(intent.get("side")) or position_direction(ds[0])
        val, why = slip_r(fill, intent.get("intended"), intent.get("sl"), dirn,
                          intent.get("point"))
        rows.append({"ticket": ticket, "deals": [d.get("deal") for d in ds],
                     "n_close_deals": len(ds),
                     "symbol": ds[0].get("symbol") or intent.get("symbol"),
                     "sleeve": ds[0].get("sleeve") or intent.get("sleeve"),
                     "order_type": _order_type(intent),
                     "slip_r": None if val is None else round(val, 6) + 0.0, "reason": why})
    return rows, unjoined


def fusion_block(intents: list[Row], deals: list[Row], as_of: datetime,
                 max_age_days: float = MAX_AGE_DAYS) -> tuple[dict[str, Any], list[Row]]:
    """The live-ledger account's summary, refusing a ledger that holds more than one account."""
    visible = [d for d in deals if _visible(d, ("time", "exit_time"), as_of)]
    accounts = split_by_account(visible) if visible else {}
    # PUBLISHED TO A PUBLIC REPOSITORY: an account is named by its kind and deal count only. The
    # broker server label and the keyed account id stay on the box (Auditor MF2, 2026-11-14).
    listed = [{"kind": k[2], "n_deals": len(v)}
              for k, v in sorted(accounts.items(), key=str)]
    if len(accounts) > 1:
        # The headline refuses to blend; each account is then measured on its own deals, so a
        # multi-account ledger still yields one figure per account instead of none at all.
        by_account = []
        for k, v in sorted(accounts.items(), key=str):
            sub, _ = fusion_block(intents, v, as_of, max_age_days)
            by_account.append(sub)
        return ({"status": MIXED, "sign": MIXED, "median_slip_r": None, "mean_slip_r": None,
                 "mean_ci95": None, "n_rows": 0, "n_measured": 0, "accounts_in_ledger": listed,
                 "by_account": by_account,
                 "why": (f"MIXED ledger: fills from {len(accounts)} accounts. No blended "
                         "headline; see by_account for each one measured alone.")},
                [])
    rows, unjoined = fusion_rows(intents, visible, as_of)
    latest = max((t for t in (_first_stamp(d, ("time", "exit_time")) for d in visible)
                  if t is not None), default=None)
    fresh = freshness(latest, as_of, max_age_days)
    block = summarise(rows, fresh)
    block.update({"freshness": fresh, "account": listed[0] if listed else None,
                  "n_deals": len(visible), "n_unjoined_deals": unjoined,
                  "n_positions": len(rows),
                  "by_symbol": _group(rows, "symbol", fresh),
                  "by_order_type": _group(rows, "order_type", fresh)})
    if not visible:
        block["why"] = "no live-ledger deal at or before as_of"
    return block, rows


def _e8_status(row: Row) -> str:
    """fill_recorder.py:545: status compared stripped and upper-cased."""
    return str(row.get("status") or "").strip().upper()


def _side_dir(side: Any) -> int:
    """`_direction` plus the export's long/short words."""
    s = str(side or "").strip().lower()
    if s in ("long", "l"):
        return 1
    if s in ("short", "s"):
        return -1
    return _direction(side)


def e8_fill_from_csv(row: dict[str, str]) -> Row:
    """One row of the E8 fills export (filled_at_utc, window, side, lot, entry, sl, tp,
    position_id) in this module's fill shape. The export carries NO requested price: the intended
    price must come from the E8 intent that placed the bracket, or the row is UNMEASURED."""
    at = str(row.get("filled_at_utc") or "").strip()
    if at and _stamp(at) is None and _stamp(at + "+00:00") is not None:
        at += "+00:00"  # the column is named UTC; a bare stamp is read as UTC, never local
    return {"time": at or None, "window": (row.get("window") or "").strip() or None,
            "side": row.get("side"), "volume": _num(row.get("lot")),
            "fill_price": _num(row.get("entry")), "sl": _num(row.get("sl")),
            "tp": _num(row.get("tp")), "position_id": (row.get("position_id") or "").strip()
            or None, "order_id": (row.get("order_id") or "").strip() or None}


def _e8_intent_for(fill: Row, t_fill: datetime, by_id: dict[str, Row],
                   sent: list[Row], used: set[int]) -> Row | None:
    """The SENT intent that placed this fill's bracket: by order/position id first, else the
    exact stop AND target echo (markout's `_echo`, half a point) in the same window and position
    direction, sent no later than the fill. Each intent is used once; latest qualifying wins."""
    for key in ("order_id", "position_id"):
        v = fill.get(key)
        if v is not None and str(v) in by_id and id(by_id[str(v)]) not in used:
            return by_id[str(v)]
    dirn = _side_dir(fill.get("side"))
    best: Row | None = None
    best_t: datetime | None = None
    for it in sent:
        if id(it) in used:
            continue
        if fill.get("window") and it.get("window") and it.get("window") != fill.get("window"):
            continue
        if dirn and _side_dir(it.get("side")) != dirn:
            continue
        sl = it.get("sl") if it.get("sl") is not None else it.get("stop")
        tp = it.get("tp") if it.get("tp") is not None else it.get("target")
        if not (_echo(sl, fill.get("sl")) and _echo(tp, fill.get("tp"))):
            continue
        ti = _first_stamp(it, ("at", "sent_at"))
        if ti is None or ti > t_fill:
            continue
        if best_t is None or ti > best_t:
            best, best_t = it, ti
    return best


def e8_rows(intents: list[Row], fills: list[Row], as_of: datetime) -> tuple[list[Row], Any]:
    """(one row per E8 POSITION filled at or before as_of, newest fill stamp).

    The intended price and stop are the placing intent's (`price`/`entry_ref`, `sl`/`stop`). A fill
    whose intent is not in the repository is UNMEASURED with reason `no_intended_price`, never 0.
    Partial fills of one position collapse to one row, volume-weighted.
    """
    sent = [i for i in intents if _e8_status(i) == "SENT" and i.get("order_id") is not None
            and _visible(i, ("at", "sent_at"), as_of)]
    by_id: dict[str, Row] = {}
    for i in sent:
        for key in ("order_id", "position_id"):
            if i.get(key) is not None:
                by_id[str(i[key])] = i  # the latest SENT row for an id wins
    groups: dict[str, list[tuple[Row, datetime]]] = {}
    latest: datetime | None = None
    for n, f in enumerate(fills):
        t = _first_stamp(f, ("time", "filled_at", "at"))
        if t is None or t > as_of:
            continue
        key = str(f.get("position_id") or f.get("order_id") or f"row{n}")
        groups.setdefault(key, []).append((f, t))
        latest = t if latest is None or t > latest else latest
    used: set[int] = set()
    rows: list[Row] = []
    for key, fs in sorted(groups.items(), key=lambda kv: min(t for _, t in kv[1])):
        first, t0 = min(fs, key=lambda ft: ft[1])
        fill = _vwap([(f.get("fill_price") if f.get("fill_price") is not None
                       else f.get("avgPrice"), f.get("qty", f.get("volume"))) for f, _ in fs])
        intent = _e8_intent_for(first, t0, by_id, sent, used)
        if intent is None:
            val, why = None, "no_intended_price"
        else:
            used.add(id(intent))
            intended = (intent.get("price") if intent.get("price") is not None
                        else intent.get("entry_ref"))
            stop = intent.get("sl") if intent.get("sl") is not None else intent.get("stop")
            dirn = _side_dir(intent.get("side")) or _side_dir(first.get("side"))
            val, why = slip_r(fill, intended, stop, dirn, intent.get("point"))
        rows.append({"position": key, "filled_at": t0.isoformat(timespec="seconds"),
                     "window": first.get("window"), "side": first.get("side"),
                     "fill": fill, "intent_order_id": intent.get("order_id") if intent else None,
                     "slip_r": None if val is None else round(val, 6) + 0.0, "reason": why})
    return rows, latest


def read_e8_fills(path: Path) -> tuple[list[Row], int]:
    """(fills, garbage rows) from a .csv export or a JSONL file."""
    if path.suffix.lower() != ".csv":
        return read_jsonl(path)
    import csv

    out: list[Row] = []
    bad = 0
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            row = e8_fill_from_csv(raw)
            if row["time"] is None or _stamp(row["time"]) is None or row["fill_price"] is None:
                bad += 1
                continue
            out.append(row)
    return out, bad


def _legacy(path: Path) -> Row:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mean_slip_r": UNMEASURED, "why": f"{path.name} absent or unreadable"}
    return {"mean_slip_r": doc.get("mean_slip_r"), "n_matched": doc.get("n_matched"),
            "label": "ARTIFACT",
            "why": ("markout.json: one account at a time or MIXED; reference only, never a "
                    "slip input here")}


def _headroom(block: dict[str, Any]) -> Any:
    """Only a fresh, MEASURED account (n >= MIN_N) hands a number to e8_headroom."""
    med = block.get("median_slip_r")
    return med if block.get("status") == "MEASURED" and med is not None else UNMEASURED


def build(as_of: datetime, *, fusion_intents: list[Row], fusion_deals: list[Row],
          e8_intents: list[Row], e8_fills: list[Row] | None,
          legacy: Row | None = None, inputs: Row | None = None,
          max_age_days: float = MAX_AGE_DAYS) -> dict[str, Any]:
    fusion, fr = fusion_block(fusion_intents, fusion_deals, as_of, max_age_days)
    er, e8_latest = e8_rows(e8_intents, e8_fills or [], as_of)
    e8_fresh = freshness(e8_latest, as_of, max_age_days)
    e8 = summarise(er, e8_fresh if e8_fills else None)
    e8["freshness"] = e8_fresh
    e8["n_sent_intents"] = sum(1 for i in e8_intents if _e8_status(i) == "SENT")
    if e8_fills is None:
        e8["why"] = ("no E8 fill record in the repository: E8 intents carry order_id, but the "
                     "venue fill price is box-only. Supply --e8-fills to measure")
    elif not er:
        e8["why"] = "no E8 fill at or before as_of"
    elif not e8["n_measured"]:
        e8["why"] = ("every E8 fill lacks its placing intent in the repository, so its intended "
                     "price is unknown (e8_intents.jsonl / e8_gold_intents.jsonl are box-only)")
    return {
        "schema": "markout_v2/3", "report_only": True,
        "as_of": as_of.isoformat(timespec="seconds"),
        "unit": "R = |intended - intent stop| in PRICE units; positive = worse than asked",
        "rules": {"min_n": MIN_N, "max_age_days": max_age_days,
                  "stop_floor": f"max(point, {STOP_FLOOR_REL} * intended)",
                  "sign": "from the bootstrap 95% CI of the mean; median_sign is raw"},
        "accounts": {"fusion": fusion, "e8": e8},
        "e8_headroom_input": {"e8_slip_r": _headroom(e8), "fusion_slip_r": _headroom(fusion),
                              "statistic": "median"},
        "legacy_markout": legacy if legacy is not None else {},
        "inputs": inputs if inputs is not None else {},
        "rows": {"fusion": fr, "e8": er},
    }


def read_jsonl(path: Path) -> tuple[list[Row], int]:
    """(dict rows, garbage lines). Blank lines are not garbage; anything else unparsed is."""
    out: list[Row] = []
    bad = 0
    if not path.exists():
        return out, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(row, dict):
            out.append(row)
        else:
            bad += 1
    return out, bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=None, help="ISO time with zone; default now (UTC)")
    ap.add_argument("--e8-fills", default=str(E8_FILLS),
                    help="E8 fills: JSONL (order_id, fill_price|avgPrice, time) or the CSV "
                         "export (filled_at_utc, window, side, lot, entry, sl, tp, position_id)")
    ap.add_argument("--max-age-days", type=float, default=MAX_AGE_DAYS)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    as_of = _stamp(a.as_of) if a.as_of else datetime.now(tz=UTC)
    if as_of is None:
        ap.error("--as-of must be an ISO time with a zone")
    inputs: Row = {}
    fusion_intents, inputs["order_intents"] = read_jsonl(FUSION_INTENTS)
    _, raw_bad = read_jsonl(FUSION_LEDGER)
    deals = load_jsonl(FUSION_LEDGER)
    e8_intents: list[Row] = []
    for p in E8_INTENT_FILES:
        rows, inputs[p.stem] = read_jsonl(p)
        e8_intents.extend(rows)
    fills_path = Path(a.e8_fills)
    fills: list[Row] | None = None
    if fills_path.exists():
        fills, inputs["e8_fills"] = read_e8_fills(fills_path)
    inputs = {"garbage_lines": inputs, "live_ledger_raw_garbage_lines": raw_bad,
              "live_ledger_rows": len(deals),
              "e8_fills_path": fills_path.name if fills is not None else None,
              "e8_intent_files_present": [p.name for p in E8_INTENT_FILES if p.exists()]}
    doc = build(as_of, fusion_intents=fusion_intents, fusion_deals=deals,
                e8_intents=e8_intents, e8_fills=fills, legacy=_legacy(LEGACY), inputs=inputs,
                max_age_days=a.max_age_days)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(public_view(doc), indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    rows_out = out.with_name(ROWS_OUT.name)
    rows_out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    f, e = doc["accounts"]["fusion"], doc["accounts"]["e8"]
    print(f"fusion {f['status']} median {f['median_slip_r']} sign {f['sign']} "
          f"n={f['n_measured']}/{f['n_rows']} positions, unjoined {f.get('n_unjoined_deals')}, "
          f"mean {f['mean_slip_r']} ci {f['mean_ci95']}; e8 {e['status']} -> {out}")
    return 0

