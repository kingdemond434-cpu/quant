#!/usr/bin/env python3
"""DAILY P&L EXPLAIN: the book's realised P&L per day, split into what earned it.

    python research/pnl_explain.py [--days 90] [--out reports/PNL_EXPLAIN.json]

Clock: hourly leg `pnl_explain` (research/hourly_cycle.py, meta). Artifact:
desks/mt5/reports/PNL_EXPLAIN.json, published by sync_shadow_to_git.ps1's $reportPaths. Consumer:
the CRO pass, duty D22 (docs/cro/CRO_CYCLE.md), measured by scripts/check_cro_duties.py.

WHY (backlog finding K4, noon CRO pass 2026-11-13). The desk had no daily P&L explain. markout.json
gives book-level slippage only, and live_ledger.jsonl carries the raw fields (pl_quote,
commission, swap, the fill and the entry) with no decomposition, so a red day could not be told
apart as a bad signal, bad fills, fees or carry.

REPORT-ONLY. It reads data/live_ledger.jsonl and data/order_intents.jsonl and writes one report.
It imports nothing from the gateway, sizing, orders or the allocator, and nothing reads it to
place, size or veto a trade.

THE SPLIT, per closed position (the gateway's own arithmetic, mt5desk/gateway.py: `pl_quote` is
the broker's account-currency profit + commission + swap + fee + the entry deal's costs):

    commission  = commission + exit_fee + entry_cost_allocated      (account currency)
    swap        = swap
    gross       = pl_quote - commission - swap                      (the price P&L the broker paid)
    price move  = (exit - entry) * direction                        (quote currency, per unit)
    slippage    = -(entry - intended) * direction                   (negative = filled worse)
    signal      = (exit - intended) * direction = price move - slippage
    fx          = gross converted back to quote at the venue rate, minus the price move

The venue rate is `risk_quote / (|entry - sl| * volume * contract_size)`: risk_quote is the
account-currency value of the entry-to-stop distance from the venue's tick value, so it is the
account currency per quote unit the broker applied. `fx` is the conversion residual: what the
broker's account-currency P&L carries that the quote-currency price move at that rate does not.

NO MONEY AND NO ACCOUNT IS PUBLISHED (audit SF2, 2026-11-18). Every component is in basis points
of the position's entry notional, and a day's figure is the notional-weighted mean over its closed
positions; the day also carries its summed R (r_multiple, unitless) and each component's share of
the day's gross absolute movement. The PUBLISHED report is BOOK-LEVEL only: every account's
positions are pooled into one series per day, with no per-account row, label, login, key, server
or name. Per-account detail (labelled `<kind>-<n>` in order of first appearance, still never a
login, key or server) goes to reports/PNL_EXPLAIN_ACCOUNTS.local.json, which is gitignored and is
not in sync_shadow_to_git.ps1's $reportPaths: it stays on the box. No notional, price, ticket or
deal id leaves this file in either report.

UNMEASURED IS A REAL ANSWER (L1.28a). A position with no matched intent has no slippage or signal
split (its price move is reported unsplit and counted); one with no stop, no risk or no entry has
no venue rate and so no bps at all, and is counted under `unmeasured`. A day of nothing but such
rows reads UNMEASURED, never zero.

A ROW IS MEASURED ONLY WHEN EVERY COST AND THE RATE ARE MEASURED (audit MF2/SF1, 2026-11-18). Two
gaps keep a row's numbers but mark it PARTIAL, with the gap named in its `flags`, and so keep its
day and the report off MEASURED:

  * UNMEASURED_ENTRY_COST -- the gateway wrote `entry_cost_allocated: null` with
    `net_cost_status: "UNMEASURED_ENTRY_COST"` (or the row predates both fields). The entry
    deal's costs are then absent from `pl_quote` too, so `commission` and `net` are the KNOWN
    costs only, and the unknown entry cost is never summed in as a zero.
  * RATE_QUOTE_FALLBACK -- the venue rate is exactly 1. That is what
    `decision_core.closed_trade_r` produces when the venue's tick value or tick size was missing
    and it fell back to the quote-currency distance; it is also what an account whose currency
    is the quote currency produces, and the row cannot tell the two apart. Either way no
    conversion was measured, so `fx_conversion` on such a row is the residual of an assumed rate
    of 1, not a measured FX effect.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from libs.ops.win_write import write_text_resilient  # noqa: E402

DATA = BASE / "data"
LEDGER = DATA / "live_ledger.jsonl"
INTENTS = DATA / "order_intents.jsonl"
OUT = BASE / "reports" / "PNL_EXPLAIN.json"
#: Per-account detail, BOX-LOCAL: gitignored (`**/reports/*` plus its own line) and never in
#: sync_shadow_to_git.ps1's $reportPaths.
LOCAL_OUT = BASE / "reports" / "PNL_EXPLAIN_ACCOUNTS.local.json"
DAYS = 90
COMPONENTS = ("signal", "slippage", "commission", "swap", "fx_conversion")
#: The intent ticket can be any of these on a ledger row (markout's join keys).
JOIN_KEYS = ("entry_order", "position_id", "order")
#: A venue rate this close to 1 is indistinguishable from closed_trade_r's quote-currency
#: fallback (risk_quote is rounded to 6 dp on the ledger).
RATE_ONE_TOL = 1e-6
ENTRY_COST_GAP = "UNMEASURED_ENTRY_COST"
RATE_GAP = "RATE_QUOTE_FALLBACK"
_BUY = {0, 2, 4}
_SELL = {1, 3, 5}


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _load(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8-sig", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _dir_of(side: Any) -> int:
    if isinstance(side, str):
        s = side.lower()
        return 1 if s.startswith("buy") else -1 if s.startswith("sell") else 0
    if isinstance(side, int) and not isinstance(side, bool):
        return 1 if side in _BUY else -1 if side in _SELL else 0
    return 0


def direction(row: dict[str, Any], intent: dict[str, Any] | None) -> int:
    """The POSITION's direction: the intent's side, the entry deal's type, the stop geometry,
    then the closing deal inverted (the ledger's `side` is the closing deal's)."""
    d = _dir_of(intent.get("side")) if intent else 0
    if d:
        return d
    d = _dir_of(row.get("entry_side"))
    if d:
        return d
    entry, sl = _num(row.get("entry_price")), _num(row.get("sl"))
    if entry and sl and sl != entry:
        return 1 if sl < entry else -1
    return -_dir_of(row.get("side"))


def _day(row: dict[str, Any]) -> str | None:
    for key in ("exit_time", "time"):
        raw = row.get(key)
        if isinstance(raw, str) and raw:
            try:
                t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC).date().isoformat()
    return None


def explain_row(row: dict[str, Any], intent: dict[str, Any] | None) -> dict[str, Any]:
    """One closed position's split, in bps of entry notional, with its notional as weight.

    Returns {"status": MEASURED|PARTIAL|UNMEASURED, "why", and when not UNMEASURED: "bps": {...},
    "split": bool, "flags": [...], "weight": notional (quote currency, never published),
    "r": r_multiple}. PARTIAL carries the same numbers with each gap named in `flags`.
    """
    entry, exit_ = _num(row.get("entry_price")), _num(row.get("fill_price"))
    sl, vol = _num(row.get("sl")), _num(row.get("volume"))
    cs, risk = _num(row.get("contract_size")), _num(row.get("risk_quote"))
    net = _num(row.get("pl_quote"))
    if not (entry and exit_ and vol and cs and net is not None):
        return {"status": "UNMEASURED", "why": "no entry, exit, volume, contract size or P&L"}
    if not (sl and sl != entry and risk and risk > 0):
        return {"status": "UNMEASURED", "why": "no stop or risk, so no venue conversion rate"}
    dirn = direction(row, intent)
    if dirn == 0:
        return {"status": "UNMEASURED", "why": "no direction"}
    flags: list[str] = []
    notional = entry * vol * cs                      # quote currency
    quote_risk = abs(entry - sl) * vol * cs
    rate = risk / quote_risk                         # account currency per quote unit
    if abs(risk - quote_risk) <= RATE_ONE_TOL + 1e-9 * quote_risk:
        flags.append(RATE_GAP)
    to_bps = 1e4 / (notional * rate)                 # account currency -> bps of notional
    # The entry deal's cost is summed only when the gateway measured it; a null is a gap, never
    # a zero. pl_quote then carries no entry cost either, so the known costs stay consistent.
    entry_cost = _num(row.get("entry_cost_allocated"))
    if entry_cost is None or row.get("net_cost_status") == ENTRY_COST_GAP:
        flags.append(ENTRY_COST_GAP)
        entry_cost = None
    known = [_num(row.get(k)) for k in ("commission", "exit_fee")]
    if entry_cost is not None:
        known.append(entry_cost)
    commission = sum(v for v in known if v is not None)
    swap = _num(row.get("swap")) or 0.0
    gross = net - commission - swap
    move_bps = (exit_ - entry) * dirn / entry * 1e4
    bps: dict[str, float | None] = {
        "commission": commission * to_bps, "swap": swap * to_bps,
        "fx_conversion": gross * to_bps - move_bps, "net": net * to_bps,
    }
    want = _num(intent.get("intended")) if intent else None
    split = bool(want and want > 0)
    if split:
        assert want is not None
        bps["slippage"] = -(entry - want) * dirn / entry * 1e4
        bps["signal"] = (exit_ - want) * dirn / entry * 1e4
        bps["price_unsplit"] = 0.0
    else:
        bps["slippage"] = bps["signal"] = None
        bps["price_unsplit"] = move_bps
    return {"status": "PARTIAL" if flags else "MEASURED", "flags": flags, "bps": bps,
            "split": split, "weight": notional, "r": _num(row.get("r_multiple"))}


def _intent_index(intents: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    out: dict[Any, dict[str, Any]] = {}
    for i in intents:
        t = i.get("ticket")
        if t not in (None, 0, ""):
            out[t] = i
    return out


def _match(row: dict[str, Any], by_ticket: dict[Any, dict[str, Any]]) -> dict[str, Any] | None:
    for k in JOIN_KEYS:
        v = row.get(k)
        if v is not None and v in by_ticket:
            return by_ticket[v]
    return None


def _rnd(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def _day_entry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One day's pooled split over `rows` (any accounts); PARTIAL rows count with their flags."""
    meas = [r for r in rows if r["status"] != "UNMEASURED"]
    unmeas = len(rows) - len(meas)
    split = [r for r in meas if r["split"]]
    flags: dict[str, int] = defaultdict(int)
    for r in meas:
        for f in r["flags"]:
            flags[f] += 1
    entry: dict[str, Any] = {"closed": len(rows), "measured": len(meas),
                             "unmeasured": unmeas, "split": len(split),
                             "partial": sum(1 for r in meas if r["status"] == "PARTIAL"),
                             "flags": dict(sorted(flags.items()))}
    if not meas:
        entry.update(status="UNMEASURED", why="no closed position on this day could be split")
        return entry
    w = sum(r["weight"] for r in meas)
    ws = sum(r["weight"] for r in split)

    def wmean(key: str, pool: list[dict[str, Any]], wt: float) -> float | None:
        vals = [(r["bps"][key], r["weight"]) for r in pool if r["bps"].get(key) is not None]
        return (sum(v * x for v, x in vals) / wt) if vals and wt else None

    comp = {k: wmean(k, meas, w) for k in ("commission", "swap", "fx_conversion", "net")}
    # signal and slippage are means over the SPLIT rows, re-weighted onto the whole day so
    # the five components and the unsplit remainder sum to the day's net.
    for k in ("signal", "slippage"):
        m = wmean(k, split, ws)
        comp[k] = None if m is None else m * ws / w
    comp["price_unsplit"] = wmean("price_unsplit", meas, w)
    gross_abs = sum(abs(comp[k] or 0.0) for k in (*COMPONENTS, "price_unsplit"))
    rs = [r["r"] for r in meas if r["r"] is not None]
    clean = len(split) == len(meas) and not unmeas and not entry["partial"]
    entry.update(
        status="MEASURED" if clean else "PARTIAL",
        bps={k: _rnd(v) for k, v in comp.items()},
        share={k: (_rnd(abs(comp[k] or 0.0) / gross_abs, 4) if gross_abs else None)
               for k in (*COMPONENTS, "price_unsplit")},
        r_sum=_rnd(sum(rs), 4) if rs else None)
    return entry


def _totals(days: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ds = days.values()
    return {"closed": sum(d["closed"] for d in ds), "measured": sum(d["measured"] for d in ds),
            "split": sum(d["split"] for d in ds), "partial": sum(d["partial"] for d in ds),
            "days_measured": sum(1 for d in ds if d["status"] != "UNMEASURED")}


def _status(t: dict[str, Any]) -> tuple[str, str]:
    if not t["measured"]:
        return "UNMEASURED", "no closed position in the window could be split"
    clean = t["measured"] - t["partial"]
    why = (f"{t['measured']} of {t['closed']} closed positions split in bps of entry notional"
           f" ({clean} fully measured, {t['partial']} partial)")
    full = t["partial"] == 0 and t["measured"] == t["closed"] and t["split"] == t["measured"]
    return ("MEASURED" if full else "PARTIAL"), why


def build_all(ledger: list[dict[str, Any]], intents: list[dict[str, Any]], now: datetime,
              days: int = DAYS) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the PUBLISHED book-level report, the BOX-LOCAL per-account detail)."""
    by_ticket = _intent_index(intents)
    since = (now - timedelta(days=days)).date().isoformat()
    labels: dict[tuple[Any, Any, Any], str] = {}
    kinds_seen: dict[str, int] = defaultdict(int)
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_acct: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    undated = 0
    for row in ledger:
        acct = (row.get("account_key") or row.get("account"), row.get("server"),
                row.get("account_kind") or "unknown")
        if acct not in labels:
            kind = str(acct[2])
            kinds_seen[kind] += 1
            labels[acct] = f"{kind}-{kinds_seen[kind]}"
        day = _day(row)
        if day is None:
            undated += 1
            continue
        if day < since:
            continue
        ex = explain_row(row, _match(row, by_ticket))
        by_day[day].append(ex)
        by_acct[(labels[acct], day)].append(ex)

    book_days = {day: _day_entry(rows) for day, rows in sorted(by_day.items())}
    book = _totals(book_days)
    status, why = _status(book)
    common = {
        "generated_utc": now.isoformat(), "window_days": days,
        "units": "bps of entry notional, notional-weighted per day; r_sum is unitless R",
        "components": [*COMPONENTS, "price_unsplit"],
        "identity": "net = signal + slippage + commission + swap + fx_conversion + price_unsplit",
        "sign": "positive adds to P&L; slippage is negative when the fill was worse than asked",
        "flags_meaning": {
            ENTRY_COST_GAP: "entry deal cost unmeasured by the gateway; commission and net "
                            "carry the known costs only",
            RATE_GAP: "venue rate exactly 1 (tick value missing, or account currency is the "
                      "quote currency); fx_conversion is not a measured conversion"},
        "undated_rows": undated, "report_only": True,
        "sources": ["desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/order_intents.jsonl"],
    }
    published = {**common, "status": status, "why": why,
                 "scope": "book: every account pooled; no per-account row or identifier",
                 "book": {**book, "days": book_days}}

    accounts: dict[str, dict[str, Any]] = {}
    for (label, day), rows in sorted(by_acct.items()):
        accounts.setdefault(label, {"days": {}})["days"][day] = _day_entry(rows)
    for acc in accounts.values():
        acc.update(_totals(acc["days"]))
    local = {**common, "status": status, "why": why,
             "scope": "per account, BOX-LOCAL (gitignored, never published)",
             "accounts": accounts}
    return published, local


def build(ledger: list[dict[str, Any]], intents: list[dict[str, Any]], now: datetime,
          days: int = DAYS) -> dict[str, Any]:
    """The published, book-level report."""
    return build_all(ledger, intents, now, days)[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--intents", type=Path, default=INTENTS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--local-out", type=Path, default=LOCAL_OUT)
    ap.add_argument("--days", type=int, default=DAYS)
    a = ap.parse_args(argv)
    doc, local = build_all(_load(a.ledger), _load(a.intents), datetime.now(UTC), a.days)
    for path, body in ((a.out, doc), (a.local_out, local)):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_resilient(path, json.dumps(body, indent=1) + "\n")
    print(json.dumps({"status": doc["status"], "why": doc["why"],
                      "accounts": len(local["accounts"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
