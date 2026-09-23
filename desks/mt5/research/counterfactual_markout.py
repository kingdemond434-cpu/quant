"""What every veto cost or saved: the P&L of the trades the desk chose not to take.

    FilterValue(reason) = sum of R the desk avoided by not taking those trades
                        = -(sum of counterfactual R of the vetoed brackets)

A regime filter that vetoed forty trades which would have lost 17R earned +17R. An event veto
that blocked eleven trades which would have made 11R cost -11R. Until this existed every filter on
this desk was assumed to be worth having because it sounded prudent, which is the same error as
assuming a state dimension conditions capital because it sounds economic. Now each one has a
ledger line, and a filter with a negative line is a candidate for deletion.

THE JOIN. `gateway._record_decision` writes every considered bracket -- taken or not -- with its
price, stop, target and reason. This replays each NOT-taken bracket with `replay2` (the second,
contract-written engine, so the counterfactual is not produced by the same code that decided) on
the bars that followed, exactly as a pending stop would have filled: if price reached the bracket
level within the day, the trade is on from there with its stated stop and target.

A BRACKET THAT WOULD NOT HAVE FILLED IS NOT A ZERO. It is NOT_TRIGGERED and excluded from the
filter's value, because a veto of a trade the market never offered has no P&L in either
direction. Counting it as +0 would drag every filter toward "harmless".

APPEND-ONLY, keyed on (sleeve, side, time). Each decision is replayed once, when enough bars
have arrived to cover its holding period; until then it is PENDING.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

DECISIONS = BASE / "data" / "decision_ledger.jsonl"
OUT = BASE / "data" / "counterfactuals.jsonl"
REPORT = BASE / "reports" / "FILTER_VALUE.json"
#: Hours a pending stop is live before the desk's own housekeeping would have cancelled it.
BRACKET_LIVE_H = 12
#: Bars the counterfactual trade may run before a time exit, mirroring the families' TTLs.
HOLD_BARS = 24
NOT_TRIGGERED, PENDING = "NOT_TRIGGERED", "PENDING"


def _rows(path: Path) -> list[dict]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def counterfactual(bars: pd.DataFrame, when: pd.Timestamp, side: str, price: float,
                   sl: float | None, tp: float | None) -> dict:
    """Would the bracket have filled, and what would it have made? In R, from the bars after."""
    seg = bars[bars.index > when]
    if seg.empty:
        return {"status": PENDING}
    window = seg.iloc[:BRACKET_LIVE_H]
    long = side == "buy_stop"
    hit = window[(window["high"] >= price)] if long else window[(window["low"] <= price)]
    if hit.empty:
        if len(seg) < BRACKET_LIVE_H:
            return {"status": PENDING}
        return {"status": NOT_TRIGGERED}
    fill_time = hit.index[0]
    if sl is None or not np.isfinite(float(sl)) or float(sl) == price:
        return {"status": "UNPRICED", "why": "no stop on the decision row"}
    from mt5desk.engine import Signal

    from libs.validation.replay2 import replay
    # The signal bar is the one BEFORE the fill bar, so replay2 fills at the fill bar's open --
    # a pending stop fills at its level, so the entry is overridden to `price` below.
    i = bars.index.get_loc(fill_time)
    if i == 0 or i + HOLD_BARS + 1 >= len(bars):
        return {"status": PENDING}
    sig = Signal(time=bars.index[i - 1], side=(1 if long else -1), stop=float(sl),
                 target=(float(tp) if tp is not None and np.isfinite(float(tp)) else
                         (price + (price - float(sl)) * 1.5)), ttl_bars=HOLD_BARS, tag="cf",
                 trigger=None, wait_bars=1)
    trades = replay(bars, [sig])
    if not trades:
        return {"status": PENDING}
    t = trades[0]
    risk = abs(price - float(sl))
    # Re-anchor to the bracket level rather than the bar open replay2 used.
    r = ((t.exit - price) * t.side) / risk if risk > 0 else float("nan")
    return {"status": "REPLAYED", "fill_time": str(fill_time), "exit_reason": t.reason,
            "r": round(float(r), 4)}


def run() -> dict:
    from research import proposer_common as pc

    decisions = _rows(DECISIONS)
    done = {f"{r.get('sleeve')}|{r.get('side')}|{r.get('time')}" for r in _rows(OUT)
            if r.get("status") != PENDING}
    cache: dict[str, pd.DataFrame | None] = {}
    new: list[dict] = []
    for d in decisions:
        if d.get("taken"):
            continue
        key = f"{d.get('sleeve')}|{d.get('side')}|{d.get('time')}"
        if key in done:
            continue
        sym = str(d.get("symbol") or "")
        if sym not in cache:
            cache[sym] = pc.bars(sym)
        bars = cache[sym]
        try:
            when = pd.Timestamp(d["time"])
            if when.tzinfo is None:
                when = when.tz_localize("UTC")
            price = float(d.get("price"))
        except (KeyError, TypeError, ValueError):
            continue
        if bars is None or not np.isfinite(price):
            continue
        cf = counterfactual(bars, when, str(d.get("side")), price,
                            d.get("sl"), d.get("tp"))
        if cf.get("status") == PENDING:
            continue
        new.append({"sleeve": d.get("sleeve"), "symbol": sym, "side": d.get("side"),
                    "time": d.get("time"), "reason": d.get("reason"),
                    "state_vector_id": d.get("state_vector_id"), **cf})
    if new:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r) + "\n")

    allrows = [r for r in _rows(OUT) if r.get("status") == "REPLAYED"]
    by_reason: dict[str, list[float]] = defaultdict(list)
    by_reason_state: dict[str, list[float]] = defaultdict(list)
    for r in allrows:
        by_reason[str(r.get("reason"))].append(float(r["r"]))
        by_reason_state[f"{r.get('reason')}|{r.get('state_vector_id') or '?'}"].append(float(r["r"]))
    filters = {}
    for reason, rs in by_reason.items():
        arr = np.asarray(rs)
        avoided = -float(arr.sum())
        se = float(arr.std(ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else float("nan")
        filters[reason] = {"n_vetoed_and_triggered": int(arr.size),
                           "filter_value_r": round(avoided, 3),
                           "mean_avoided_r": round(-float(arr.mean()), 4),
                           "t": (round(-float(arr.mean()) / se, 2) if se and se > 0 else None),
                           "verdict": ("EARNS_ITS_PLACE" if arr.size >= 20 and avoided > 0 and
                                       se > 0 and -float(arr.mean()) / se > 2.0 else
                                       ("COSTS_EDGE" if arr.size >= 20 and avoided < 0 and
                                        se > 0 and float(arr.mean()) / se > 2.0 else
                                        "UNDETERMINED"))}
    n_not = sum(1 for r in _rows(OUT) if r.get("status") == NOT_TRIGGERED)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "decisions": len(decisions),
           "not_taken": sum(1 for d in decisions if not d.get("taken")),
           "replayed_new": len(new), "replayed_total": len(allrows),
           "not_triggered_total": n_not, "filters": filters,
           "rule": ("filter_value_r = -(sum of counterfactual R of vetoed, triggered brackets); "
                    "NOT_TRIGGERED brackets are excluded, never counted as zero")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"FILTER VALUE  {d['decisions']} decisions, {d['not_taken']} not taken, "
          f"{d['replayed_total']} replayed, {d['not_triggered_total']} never triggered")
    for reason, f in sorted(d["filters"].items(), key=lambda kv: -kv[1]["filter_value_r"]):
        print(f"  {reason:28s} n={f['n_vetoed_and_triggered']:4d} value={f['filter_value_r']:+8.2f}R "
              f"t={f['t']}  {f['verdict']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
