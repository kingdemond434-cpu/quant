#!/usr/bin/env python3
"""EVENT WINDOWS, PER SLEEVE: stand aside where the event costs growth, trade through where the
edge IS the event (trader-brain row #2, idea 695).

THE QUESTION. `libs/execution/event_guard.py` defers new entries around scheduled high-impact
releases (FOMC, CPI, NFP, central-bank decisions). Deferring every sleeve is wrong both ways: a
carry or range sleeve whose stop gaps through on the print should stand aside, and a sleeve whose
mechanism is the repricing itself (a breakout that fires on the release) would be switched off on
exactly the hours it earns. So the decision is made per sleeve, from the sleeve's own trades.

THE COUNTERFACTUAL. For each sleeve (live trades by sleeve name) and each replayed shadow cell
(`reports/shadow/ledger_<SYM>_<family>_<window>.json`, keyed `SYM|family|window`):
  * every trade is a log-return `log(1 + f * R)` at the per-trade risk fraction `f`;
  * WITH = every trade; WITHOUT = the trades whose ENTRY falls in an event window removed (a
    deferred entry is counted as not taken -- the conservative reading of a deferral);
  * the two daily log-wealth series are PAIRED BY DAY over the days that held at least one
    in-window entry (on every other day the two books are identical);
  * the paired mean difference, its t statistic and a one-sample two-sided p-value, Holm-adjusted
    across every key tested this pass, decide the verdict; E[log W] and CVaR5 of the daily series
    are reported both ways.

VERDICTS. DEFER: removing the windows raises E[log W], Holm-significant. TRADE_THROUGH: removing
them lowers it, Holm-significant -- the edge is the event. NO_EVIDENCE: too few paired days, or
no significant difference. The gateway defers on DEFER and on NO_EVIDENCE (the guard's standing
law, R0276: entries are deferred inside a window unless the evidence says otherwise), trades
through on TRADE_THROUGH, and bills every deferral on the rails ledger (Rule 1).

Times: both ledgers stamp the BROKER's wall clock under a UTC label; every entry is converted with
`mt5desk.broker_clock.broker_to_utc` before it is compared with the calendar's true UTC.

    python desks/mt5/research/event_window_policy.py [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CALENDAR = ROOT / "data" / "event_calendar.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
SHADOW = DESK / "reports" / "shadow"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "EVENT_WINDOW_POLICY.json"

#: The window tested and then enforced: 30 minutes before a release (positioning ahead of a binary
#: print) to 60 after (the first prints, where spreads blow out and stops fill far from their
#: level) -- idea 695's window, wider after than the guard's default 15 because a deferral that
#: re-enters into the second leg of the repricing has deferred nothing.
BEFORE_MIN = 30
AFTER_MIN = 60
#: Per-trade risk fraction when the sleeve row carries none: the prop plan's 0.50% per trade
#: (docs/PROP_FIRM_E8.md). Only the SIGN and ranking of the paired difference decide a verdict;
#: f scales both books alike.
DEFAULT_F = 0.005
#: Paired days needed before a difference is judged at all: below this a t statistic on daily
#: differences is not worth computing (a two-day "test" is two anecdotes).
MIN_DAYS = 5
#: Family-wise error rate for the Holm step-down across every key tested in one pass.
ALPHA = 0.05


def _parse(ts: Any) -> datetime | None:
    if ts in (None, ""):
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _to_utc(ts: Any) -> datetime | None:
    """A broker-wall-clock stamp (labelled UTC or naive) as its true UTC instant."""
    d = _parse(ts)
    if d is None:
        return None
    try:
        from mt5desk.broker_clock import broker_to_utc
        out: datetime = broker_to_utc(d).to_pydatetime()
        return out
    except Exception:
        return None


def load_calendar(path: Path = CALENDAR) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """High-impact events with a parsed UTC instant, and a summary of the calendar read."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [], {"state": "UNREADABLE", "why": type(exc).__name__}
    out = []
    for ev in doc.get("events") or []:
        when = _parse(ev.get("utc"))
        if when is not None and str(ev.get("impact", "high")).lower() == "high":
            out.append({**ev, "_when": when})
    out.sort(key=lambda e: e["_when"])
    names = sorted({str(e.get("name")) for e in out})
    return out, {"state": "READ" if out else "EMPTY", "n_events": len(out),
                 "first": out[0]["_when"].isoformat() if out else None,
                 "last": out[-1]["_when"].isoformat() if out else None,
                 "series": names, "valid_through": doc.get("valid_through")}


def in_window(entry: datetime, symbol: str, events: list[dict[str, Any]], *,
              before_min: int = BEFORE_MIN, after_min: int = AFTER_MIN) -> str | None:
    """The name of the event whose window holds this entry and reprices this symbol, else None."""
    from libs.execution.event_guard import event_currencies, symbol_currencies
    mine = symbol_currencies(symbol)
    for ev in events:
        w = ev["_when"]
        if w - timedelta(minutes=before_min) <= entry <= w + timedelta(minutes=after_min):
            reach = event_currencies(ev)
            if reach is None or reach & mine:
                return str(ev.get("name") or "event")
    return None


def _jsonl(p: Path) -> list[dict[str, Any]]:
    try:
        rows = []
        for line in p.read_text("utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        return rows
    except OSError:
        return []


def _sleeve_rows() -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc if isinstance(doc, list) else doc.get("sleeves", doc)
    rows = rows if isinstance(rows, list) else list(rows.values()) if isinstance(rows, dict) else []
    return {str(r.get("name")): r for r in rows if isinstance(r, dict) and r.get("name")}


def cell_key(symbol: str, family: str, window: str) -> str:
    return f"{symbol}|{family}|{window}"


def _shadow_key(p: Path) -> tuple[str, str, str] | None:
    """`ledger_<SYM>_<family>_<window>.json` -> (SYM, family, window); `ledger_<SYM>_<window>`
    is the session_range_breakout family, as shadow_forward names it."""
    parts = p.stem.split("_")[1:]
    if len(parts) == 2:
        return parts[0], "session_range_breakout", parts[1]
    if len(parts) >= 3:
        return parts[0], "_".join(parts[1:-1]), parts[-1]
    return None


def trades(shadow_dir: Path = SHADOW, live: Path = LIVE_LEDGER) -> dict[str, dict[str, Any]]:
    """{key: {"symbol", "source", "f", "trades": [(entry_utc, R)]}} from both ledgers."""
    rows = _sleeve_rows()
    out: dict[str, dict[str, Any]] = {}
    for r in _jsonl(live):
        name, sym = str(r.get("sleeve") or ""), str(r.get("symbol") or "")
        rr, at = r.get("r_multiple"), _to_utc(r.get("entry_time") or r.get("time"))
        if not name or not sym or at is None or not isinstance(rr, (int, float)) \
                or r.get("r_unreconstructible") or not math.isfinite(float(rr)):
            continue
        f = float((rows.get(name) or {}).get("risk_frac") or 0) or DEFAULT_F
        out.setdefault(name, {"symbol": sym, "source": "live", "f": min(f, 0.05),
                              "trades": []})["trades"].append((at, float(rr)))
    for p in sorted(shadow_dir.glob("ledger_*.json")):
        k = _shadow_key(p)
        if k is None:
            continue
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rowset = doc if isinstance(doc, list) else (doc.get("trades") or [])
        bucket = out.setdefault(cell_key(*k), {"symbol": k[0], "source": "shadow",
                                               "f": DEFAULT_F, "trades": []})
        for t in rowset:
            at, rr = _to_utc(t.get("entry_time")), t.get("r_multiple")
            if at is not None and isinstance(rr, (int, float)) and math.isfinite(float(rr)):
                bucket["trades"].append((at, float(rr)))
    return out


def _cvar5(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = max(1, math.ceil(0.05 * len(s)))
    return sum(s[:k]) / k


def _p_two_sided(t: float, dof: int) -> float:
    """Student-t two-sided p-value (regularised incomplete beta), no scipy needed."""
    if dof <= 0 or not math.isfinite(t):
        return 1.0
    x = dof / (dof + t * t)
    try:
        from scipy.special import betainc  # type: ignore[import-untyped,unused-ignore]
        return float(betainc(dof / 2.0, 0.5, x))
    except Exception:
        # normal approximation: adequate for the dof this runs at, and conservative enough
        return math.erfc(abs(t) / math.sqrt(2.0))


def judge(info: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    f = float(info["f"])
    sym = str(info["symbol"])
    day_with: dict[str, float] = defaultdict(float)
    day_without: dict[str, float] = defaultdict(float)
    hit_days: set[str] = set()
    n_in = 0
    names: dict[str, int] = defaultdict(int)
    for at, r in info["trades"]:
        lr = math.log(max(1e-9, 1.0 + f * r))
        d = at.date().isoformat()
        day_with[d] += lr
        ev = in_window(at, sym, events)
        if ev:
            n_in += 1
            names[ev] += 1
            hit_days.add(d)
        else:
            day_without[d] += lr
    days = sorted(day_with)
    w = [day_with[d] for d in days]
    wo = [day_without.get(d, 0.0) for d in days]
    row: dict[str, Any] = {
        "symbol": sym, "source": info["source"], "f": f, "n_trades": len(info["trades"]),
        "n_in_window": n_in, "events_hit": dict(names), "n_days": len(days),
        "paired_days": len(hit_days),
        "elogw_with": (sum(w) / len(w)) if w else None,
        "elogw_without": (sum(wo) / len(wo)) if wo else None,
        "cvar5_with": _cvar5(w), "cvar5_without": _cvar5(wo)}
    diffs = [day_without.get(d, 0.0) - day_with[d] for d in sorted(hit_days)]
    if len(diffs) < MIN_DAYS:
        row.update(p=None, t=None, mean_gain_from_deferring=(sum(diffs) / len(diffs)
                                                             if diffs else None))
        return row
    m = sum(diffs) / len(diffs)
    var = sum((x - m) ** 2 for x in diffs) / (len(diffs) - 1)
    t = (m / math.sqrt(var / len(diffs))) if var > 0 else (math.inf if m else 0.0)
    row.update(mean_gain_from_deferring=m, t=t,
               p=_p_two_sided(t, len(diffs) - 1) if math.isfinite(t) else (0.0 if m else 1.0))
    return row


def holm(rows: dict[str, dict[str, Any]], alpha: float = ALPHA) -> None:
    """Holm step-down over every key that has a p-value; sets each row's verdict in place."""
    tested = sorted((r["p"], k) for k, r in rows.items() if r.get("p") is not None)
    m = len(tested)
    rejecting = True
    for i, (p, k) in enumerate(tested):
        thr = alpha / (m - i)
        rows[k]["holm_threshold"] = thr
        rejecting = rejecting and p <= thr
        gain = rows[k].get("mean_gain_from_deferring") or 0.0
        rows[k]["verdict"] = ("NO_EVIDENCE" if not rejecting else
                              "DEFER" if gain > 0 else "TRADE_THROUGH")
    for r in rows.values():
        r.setdefault("verdict", "NO_EVIDENCE")
        r.setdefault("why", (
            f"{r['paired_days']} paired day(s) < {MIN_DAYS}" if r.get("p") is None else
            f"paired gain from deferring {r['mean_gain_from_deferring']:+.5f} log/day, "
            f"t={r['t']:.2f}, p={r['p']:.4f} vs Holm {r.get('holm_threshold', 0):.4f}"))


def calendar_health(cal: dict[str, Any], now: datetime) -> dict[str, Any]:
    """RED when the calendar cannot be read, holds no high-impact event, or has run past its
    `valid_through`. The gateway's event gate is OFF in every one of those states (a data gap
    must not stand the book aside), so this is where the gap is made loud instead."""
    state = cal.get("state")
    vt = str(cal.get("valid_through") or "")
    if state != "READ":
        return {"state": "RED", "why": f"calendar {state}: {cal.get('why') or 'no events'}; "
                                       "the gateway's event gate is off"}
    if not vt:
        return {"state": "RED", "why": "valid_through is empty (a core publisher went unread); "
                                       "the gateway's event gate is off"}
    if vt < now.date().isoformat():
        return {"state": "RED", "why": f"calendar ran out on {vt}; the event gate is off"}
    return {"state": "GREEN", "why": f"{cal.get('n_events')} events through {vt}"}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    events, cal = load_calendar()
    rows = {k: judge(v, events) for k, v in trades().items() if v["trades"]} if events else {}
    holm(rows)
    counts: dict[str, int] = {"DEFER": 0, "TRADE_THROUGH": 0, "NO_EVIDENCE": 0}
    for r in rows.values():
        counts[r["verdict"]] += 1
    return {"generated_utc": now.isoformat(timespec="seconds"),
            "status": "MEASURED" if rows else "UNMEASURED",
            "why": None if rows else ("no event calendar read" if not events
                                      else "no trades in either ledger"),
            "window": {"before_min": BEFORE_MIN, "after_min": AFTER_MIN},
            "calendar": cal, "calendar_health": calendar_health(cal, now),
            "alpha": ALPHA, "min_days": MIN_DAYS,
            "counts": dict(counts), "policy": rows,
            "rule": "DEFER and NO_EVIDENCE defer new entries inside a window (R0276); "
                    "TRADE_THROUGH trades through; every deferral is billed (Rule 1)",
            "valid_until": (now + timedelta(hours=26)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(OUT)
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"event_window_policy: {doc['status']} {doc['counts']} "
              f"(calendar {doc['calendar'].get('n_events')} events, "
              f"{doc['calendar_health']['state']}: {doc['calendar_health']['why']})")
    # A RED calendar is a failed leg, so the hourly cycle's organ health shows it.
    return 2 if doc["calendar_health"]["state"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
