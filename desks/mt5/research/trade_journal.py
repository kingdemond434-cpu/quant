#!/usr/bin/env python3
"""TRADE JOURNAL: one row per closed trade, carrying what a trader writes in the book after the
exit (trader-brain row #7).

The live ledger records what a trade MADE. It does not say why the trade was taken, what the
world looked like when it was, how far it went for and against the position before the exit, or
how it ended. `loss_learner` and the dashboard need exactly those to tell a bad idea from a bad
fill from a bad day, so this organ joins what the desk already holds into one row per closed
trade, keyed by the venue's closing deal ticket and written once.

WHAT EACH ROW CARRIES (`data/TRADE_JOURNAL.jsonl`, one row per closing `deal`, rebuilt
every pass from the ledger so a field measured late fills in; see `merge`):

  * thesis -- `sleeve`, `symbol`, `family` and `certificate` from the live roster and the intent;
  * regime -- `regime` from `data/state_vector.json` (the symbol's own fit, else the global one)
    when the vector was written within REGIME_FRESH_H of the exit, else UNLABELLED; and
    `state_vector_id`, the id stamped on the ENTRY intent, from which the exact world at entry
    can be reconstructed later;
  * spread at entry -- `spread_at_entry_pts`, the intent's `spread_at_decision` in points, and
    `spread_ratio`, that over the symbol's median at the entry's server hour
    (`reports/SPREAD_STATE.json`), the number the spread gate (#6) acts on;
  * excursion -- `mfe_r` / `mae_r`, the best and worst price the position saw between entry and
    exit, in units of its entry risk, from the finest bars this box holds for the symbol; the
    timeframe used rides on the row as `excursion_tf` because a coarse bar's high and low can
    include minutes outside the trade, so an H1 excursion is an upper bound and is labelled so;
  * the exit -- `exit_kind` (sl | tp | stop_out | desk), from the gateway's own stamp when the
    ledger row carries one, else INFERRED from where the fill landed against the stop and target
    (`exit_kind_basis` says which); `r` is the ledger's net R;
  * event exposure -- `event_exposed`, whether a calendar event touching one of the symbol's
    currencies fell inside the holding period or the -30/+60 min window around its entry, and
    the event's name (#2).

NO MONEY ON THE ROW. Results are in R; the account key, P&L in currency and the broker server
are left in the ledger. A field that cannot be measured is null with its reason, never a guess.

    python desks/mt5/research/trade_journal.py [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEDGER = DESK / "data" / "live_ledger.jsonl"
INTENTS = DESK / "data" / "order_intents.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
STATE_VECTOR = DESK / "data" / "state_vector.json"
SPREAD_STATE = DESK / "reports" / "SPREAD_STATE.json"
UNIVERSE = DESK / "data" / "universe"
CALENDAR = ROOT / "data" / "event_calendar.json"
OUT = DESK / "data" / "TRADE_JOURNAL.jsonl"
SUMMARY = DESK / "reports" / "TRADE_JOURNAL_SUMMARY.json"

#: Finest first. M1 is where a stop fills; H1 is the floor every symbol on this box carries.
TIMEFRAMES = ("M1", "M5", "M15", "H1")
#: The state vector is rewritten hourly by the hourly cycle; a vector older than two cadences at
#: the exit describes another market, so the regime is UNLABELLED rather than borrowed.
REGIME_FRESH_H = 2.0
#: A fill within this share of the entry risk of the stop (or target) is read as that exit when
#: the gateway did not stamp one: a tenth of R is wider than the slippage measured on any stop
#: fill in the ledger and narrower than any target or desk exit sits from the stop.
EXIT_TOL_R = 0.1
#: The event window the gate (#2) and its policy organ judge, minutes before and after release.
EVENT_BEFORE_MIN, EVENT_AFTER_MIN = 30, 60
UNLABELLED = "UNLABELLED"


def _jsonl(p: Path) -> list[dict[str, Any]]:
    try:
        lines = p.read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _json(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _ts(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def roster() -> dict[str, dict[str, Any]]:
    doc: Any
    try:
        doc = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, ValueError):
        doc = []
    rows = (doc if isinstance(doc, list)
            else doc.get("sleeves", doc) if isinstance(doc, dict) else [])
    rows = rows if isinstance(rows, list) else list(rows.values()) if isinstance(rows, dict) else []
    return {str(r["name"]): r for r in rows if isinstance(r, dict) and r.get("name")}


def exit_kind(row: dict[str, Any]) -> tuple[str | None, str]:
    """(kind, basis). The gateway's stamp when present, else where the fill landed."""
    stamped = row.get("exit_kind")
    if stamped:
        return str(stamped), "gateway"
    fill, entry, sl, tp = (_f(row.get(k)) for k in ("fill_price", "entry_price", "sl", "tp"))
    if not fill or not entry or not sl:
        return None, "unreconstructible: no fill, entry or stop"
    risk = abs(entry - sl)
    if risk <= 0:
        return None, "unreconstructible: zero stop distance"
    if abs(fill - sl) <= EXIT_TOL_R * risk:
        return "sl", "inferred"
    if tp and abs(fill - tp) <= EXIT_TOL_R * risk:
        return "tp", "inferred"
    return "desk", "inferred"


def _bars(sym: str, t0: datetime, t1: datetime) -> tuple[Any, str | None]:
    import pandas as pd
    for tf in TIMEFRAMES:
        f = UNIVERSE / f"{sym}_{tf}.parquet"
        if not f.exists():
            continue
        try:
            df = pd.read_parquet(f, columns=["high", "low"])
        except (OSError, ValueError, KeyError):
            continue
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        df.index = idx
        # The bar that CONTAINS the entry opens before it, so a bar's span is read back one bar.
        span = df.loc[(df.index > pd.Timestamp(t0) - pd.Timedelta(tf_minutes(tf), "min"))
                      & (df.index <= pd.Timestamp(t1))]
        if not span.empty and df.index[0] <= pd.Timestamp(t0) and df.index[-1] >= pd.Timestamp(t1):
            return span, tf
    return None, None


def tf_minutes(tf: str) -> int:
    return {"M1": 1, "M5": 5, "M15": 15, "H1": 60}[tf]


def excursion(row: dict[str, Any]) -> dict[str, Any]:
    """MFE/MAE in R. Ledger stamps and the bar tape share the broker's server clock, so no offset
    is applied between them."""
    entry, sl = _f(row.get("entry_price")), _f(row.get("sl"))
    t0, t1 = _ts(row.get("entry_time")), _ts(row.get("exit_time"))
    side = row.get("entry_side")
    if not entry or not sl or t0 is None or t1 is None or side not in (0, 1) or t1 < t0:
        return {"mfe_r": None, "mae_r": None, "excursion_tf": None,
                "excursion_why": "no entry, stop, side or holding period on the ledger row"}
    risk = abs(entry - sl)
    if risk <= 0:
        return {"mfe_r": None, "mae_r": None, "excursion_tf": None,
                "excursion_why": "zero stop distance"}
    span, tf = _bars(str(row.get("symbol") or ""), t0, t1)
    if span is None:
        return {"mfe_r": None, "mae_r": None, "excursion_tf": None,
                "excursion_why": "no bars on this box cover the holding period"}
    hi, lo = float(span["high"].max()), float(span["low"].min())
    fav, adv = ((hi - entry), (entry - lo)) if side == 0 else ((entry - lo), (hi - entry))
    return {"mfe_r": round(max(fav, 0.0) / risk, 4), "mae_r": round(max(adv, 0.0) / risk, 4),
            "excursion_tf": tf,
            "excursion_why": None if tf == "M1" else
            f"{tf} bars: an upper bound, a bar's range can include minutes outside the trade"}


def _to_utc(d: datetime) -> datetime | None:
    try:
        import pandas as pd
        from mt5desk.broker_clock import broker_to_utc
        u = broker_to_utc(pd.Timestamp(d).tz_convert("UTC").tz_localize(None))
        out: datetime = u.tz_convert("UTC").to_pydatetime()
        return out
    except Exception:
        return None


def event_exposure(row: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    from libs.execution.event_guard import event_currencies, symbol_currencies
    t0, t1 = _ts(row.get("entry_time")), _ts(row.get("exit_time"))
    if t0 is None or t1 is None:
        return {"event_exposed": None, "event": None}
    u0, u1 = _to_utc(t0), _to_utc(t1)
    if u0 is None or u1 is None:
        return {"event_exposed": None, "event": None}
    ccy = symbol_currencies(str(row.get("symbol") or ""))
    lo, hi = u0 - timedelta(minutes=EVENT_AFTER_MIN), u1 + timedelta(minutes=EVENT_BEFORE_MIN)
    for ev in events:
        at = _ts(ev.get("utc"))
        if at is None or not lo <= at <= hi:
            continue
        evc = event_currencies(ev)
        if evc is None or evc & ccy:
            return {"event_exposed": True, "event": str(ev.get("name") or "")[:60]}
    return {"event_exposed": False, "event": None}


def _regime(sym: str, exit_t: datetime | None, sv: dict[str, Any]) -> str:
    gen = _ts(sv.get("at") or sv.get("generated_utc") or sv.get("generated_at"))
    if exit_t is None or gen is None:
        return UNLABELLED
    u = _to_utc(exit_t) or exit_t
    if abs((gen - u).total_seconds()) > REGIME_FRESH_H * 3600:
        return UNLABELLED
    from research.alpha_evolution import regime_label
    return regime_label(sym, sv)


def journal_row(row: dict[str, Any], intent: dict[str, Any] | None,
                sleeve: dict[str, Any] | None, spread_doc: dict[str, Any],
                sv: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    sym = str(row.get("symbol") or "")
    intent = intent or {}
    sleeve = sleeve or {}
    kind, basis = exit_kind(row)
    spread = _f(intent.get("spread_at_decision"))
    point = _f(intent.get("point"))
    spread_pts = round(spread / point, 2) if spread is not None and point else None
    ratio = None
    t_int = _ts(intent.get("time"))
    if spread_pts is not None and t_int is not None:
        from research.spread_state import _server_hour
        hour = _server_hour(intent.get("time"))
        p50 = _f(((spread_doc.get("hour_p50_pts") or {}).get(sym) or {}).get(str(hour)))
        ratio = round(spread_pts / p50, 3) if p50 else None
    out = {"deal": row.get("deal"), "position_id": row.get("position_id"),
           "sleeve": row.get("sleeve"), "symbol": sym,
           "family": sleeve.get("family") or sleeve.get("exec"),
           "certificate": intent.get("certificate"),
           "side": {0: "long", 1: "short"}.get(row.get("entry_side")),  # type: ignore[arg-type]
           "entry_time": row.get("entry_time"), "exit_time": row.get("exit_time"),
           "clock": "broker server wall clock, as the ledger stamps it",
           "regime": _regime(sym, _ts(row.get("exit_time")), sv),
           "state_vector_id": intent.get("state_vector_id") or None,
           "spread_at_entry_pts": spread_pts, "spread_ratio": ratio,
           "exit_kind": kind, "exit_kind_basis": basis,
           "r": _f(row.get("r_multiple")),
           "r_unreconstructible": bool(row.get("r_unreconstructible")),
           "account_kind": row.get("account_kind"),
           "release_id": intent.get("release_id")}
    out.update(excursion(row))
    out.update(event_exposure(row, events))
    return out


#: Fields measured once, at the time they describe, and never re-derivable later: a regime read
#: off a state vector that has since moved on, or an excursion from bars since pruned.
_STICKY = ("regime", "mfe_r", "mae_r", "excursion_tf", "excursion_why")


def merge(prior: dict[str, Any] | None, fresh: dict[str, Any]) -> dict[str, Any]:
    """REBUILT EVERY PASS, NOT APPENDED ONCE. A row written before its bars arrived would carry a
    null excursion forever; rebuilding fills it when the tape catches up. What can only be read
    at the time (the regime) is carried from the earlier row when this pass cannot read it."""
    if not prior:
        return fresh
    out = dict(fresh)
    if out.get("regime") == UNLABELLED and prior.get("regime") not in (None, UNLABELLED):
        out["regime"] = prior["regime"]
    if out.get("mfe_r") is None and prior.get("mfe_r") is not None:
        for k in _STICKY[1:]:
            out[k] = prior.get(k)
    return out


def build(now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = now or datetime.now(tz=UTC)
    prior = {r.get("deal"): r for r in _jsonl(OUT)}
    ledger = [r for r in _jsonl(LEDGER) if r.get("deal") is not None]
    intents = {r["ticket"]: r for r in _jsonl(INTENTS) if r.get("ticket") is not None}
    sleeves = roster()
    spread_doc = _json(SPREAD_STATE)
    sv = _json(STATE_VECTOR)
    events = [e for e in (_json(CALENDAR).get("events") or []) if isinstance(e, dict)]
    rows, seen = [], set()
    for r in ledger:
        if r["deal"] in seen:
            continue
        seen.add(r["deal"])
        rows.append(merge(prior.get(r["deal"]),
                          journal_row(r, intents.get(r.get("entry_order")),
                                      sleeves.get(str(r.get("sleeve"))), spread_doc, sv, events)))
    n = len(rows)

    def share(key: str) -> float | None:
        return round(sum(1 for r in rows if r.get(key) is not None) / n, 4) if n else None

    summary = {"generated_utc": now.isoformat(timespec="seconds"),
               "status": "MEASURED" if n else "UNMEASURED",
               "path": "desks/mt5/data/TRADE_JOURNAL.jsonl",
               "n_rows": n, "n_new": sum(1 for r in rows if r["deal"] not in prior),
               "coverage": {k: share(k) for k in ("mfe_r", "spread_ratio", "exit_kind",
                                                  "event_exposed", "state_vector_id")},
               "regime_labelled_share": (round(sum(1 for r in rows
                                                   if r.get("regime") != UNLABELLED) / n, 4)
                                         if n else None),
               "exit_kinds": {k: sum(1 for r in rows if r.get("exit_kind") == k)
                              for k in ("sl", "tp", "stop_out", "desk")},
               "valid_until": (now + timedelta(hours=26)).isoformat(timespec="seconds")}
    return rows, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rows, summary = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp_j = OUT.with_suffix(".tmp")
        tmp_j.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), "utf-8")
        tmp_j.replace(OUT)
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        tmp = SUMMARY.with_suffix(".tmp")
        tmp.write_text(json.dumps(summary, indent=1, default=str), "utf-8")
        tmp.replace(SUMMARY)
    if a.json:
        print(json.dumps(summary, default=str))
    else:
        print(f"trade_journal: {summary['status']} {summary['n_new']} new, "
              f"{summary['n_rows']} rows, coverage {summary['coverage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
