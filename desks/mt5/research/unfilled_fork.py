"""For every order that never filled: did price ever TOUCH the level?

THE BINDING CONSTRAINT IS ONE NUMBER HIDING TWO DEFECTS. `fill_attribution` measures order -> fill
at 1.9% -- 52 orders, 34 unfilled, 10 rejected, 1 filled -- and 34 UNFILLED is pooled. It is
actually two completely different failures with completely different fixes:

    TOUCHED      price reached the entry and no fill arrived.
                 A fill the desk SHOULD have had. Queue position, latency, broker stop-distance
                 rules, or an expiry that fired before the trigger. An execution defect.

    NEVER_REACHED  price never got there before the bracket expired.
                 The order was never viable. The range did not break, or the level was chosen
                 too far away. A STRATEGY defect, in price selection -- and no amount of
                 execution work fixes it.

Pooled, they average into "1.9% fill rate" and point nowhere. Split, each names its own remedy.
This is the cheapest split available on the whole desk: the bars are already on disk and the
orders are already recorded.

WHAT MAKES THE ANSWER TRUSTWORTHY IS THE WINDOW. An order is only asked about between the moment
it was ACCEPTED and the moment it expired. Scanning all of history would find almost every level
"touched" eventually and report a fill rate problem where none exists -- the classic look-ahead
dressed as diagnosis. Where the window cannot be established the verdict is UNMEASURED, never a
default to either side.

AND IT USES THE HIGH/LOW, not the close. A stop triggers intrabar. Asking whether any close
exceeded the level would miss every wick that filled and every wick that did not.

    python desks/mt5/research/unfilled_fork.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
FILLS = BASE / "data" / "fill_corpus.jsonl"
INTENTS = BASE / "data" / "order_intents.jsonl"
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "reports" / "UNFILLED_FORK.json"

#: How long a bracket rests before it expires, when the record does not say. The gateway places
#: session brackets with a broker-side expiry; where that is absent this is the honest default
#: and it is REPORTED, so a reader can see the verdict rests on an assumption.
DEFAULT_TTL_HOURS = 12.0

#: Charts to look for, finest first. A stop triggers intrabar, so the finer the bar the less the
#: answer depends on the bar boundary -- M1 resolves a wick that H1 would smear into a range.
_CHARTS = ("M1", "M5", "M15", "M30", "H1")


def _rows(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _bars(symbol: str):
    """The finest chart on disk for this symbol, as a DataFrame, or None."""
    try:
        import pandas as pd
    except ImportError:
        return None
    for tf in _CHARTS:
        f = UNIVERSE / f"{symbol}_{tf}.parquet"
        if f.exists():
            try:
                df = pd.read_parquet(f)
            except Exception:
                continue
            if len(df):
                df.attrs["chart"] = tf
                return df
    return None


def _touched(df, level: float, side: str, start, end) -> bool | None:
    """Did price reach `level` on the correct side between start and end? None when unknowable."""
    if df is None or level is None or start is None or end is None:
        return None
    try:
        win = df.loc[(df.index >= start) & (df.index <= end)]
    except Exception:
        return None
    if not len(win):
        return None
    # HIGH/LOW, NOT CLOSE. A stop triggers intrabar; a close test misses every wick.
    if "buy" in side:
        return bool((win["high"] >= level).any())
    return bool((win["low"] <= level).any())


def fork() -> dict[str, Any]:
    fills = _rows(FILLS)
    intents = _rows(INTENTS)
    by_ticket = {str(i.get("ticket")): i for i in intents
                 if i.get("ticket") and str(i.get("ticket")) != "0"}

    unfilled = [f for f in fills if str(f.get("status") or "").upper() == "UNFILLED"]
    results: list[dict[str, Any]] = []
    cache: dict[str, Any] = {}

    for f in unfilled:
        sym = str(f.get("symbol") or "").upper()
        intent = by_ticket.get(str(f.get("ticket") or "")) or {}
        sym = sym or str(intent.get("symbol") or "").upper()
        level = f.get("intended") or intent.get("intended")
        side = str(f.get("side") or intent.get("side") or "")
        rec: dict[str, Any] = {"symbol": sym, "side": side, "level": level,
                               "sleeve": f.get("sleeve") or intent.get("sleeve")}
        ack = f.get("ack_at") or f.get("decided_at") or intent.get("ack_at")
        try:
            start = datetime.fromisoformat(str(ack).replace("Z", "+00:00")) if ack else None
        except ValueError:
            start = None
        if start is None or level is None or not sym or not side:
            rec.update({"verdict": "UNMEASURED",
                        "why": "no accepted-at timestamp, level, symbol or side on the record"})
            results.append(rec)
            continue
        end = start + timedelta(hours=DEFAULT_TTL_HOURS)
        rec["window"] = [start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")]
        if sym not in cache:
            cache[sym] = _bars(sym)
        df = cache[sym]
        rec["chart"] = (df.attrs.get("chart") if df is not None else None)
        hit = _touched(df, float(level), side, start, end)
        if hit is None:
            rec.update({"verdict": "UNMEASURED",
                        "why": f"no bars on disk covering the window for {sym}"})
        elif hit:
            rec.update({"verdict": "TOUCHED",
                        "why": ("price reached the entry and no fill arrived: queue position, "
                                "latency, broker stop-distance, or an expiry that fired before "
                                "the trigger. An EXECUTION defect.")})
        else:
            rec.update({"verdict": "NEVER_REACHED",
                        "why": ("price never reached the entry before expiry: the range did not "
                                "break or the level was too far. A STRATEGY defect in price "
                                "selection -- execution work cannot fix it.")})
        results.append(rec)

    census = Counter(str(r["verdict"]) for r in results)
    n = len(results) or 1
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("an order is asked about ONLY between acceptance and expiry. Scanning all of "
                 "history would find almost every level touched eventually -- look-ahead dressed "
                 "as diagnosis. High/low is used, never close: a stop triggers intrabar."),
        "assumed_ttl_hours": DEFAULT_TTL_HOURS,
        "n_unfilled": len(results),
        "census": dict(census),
        "share_touched": round(census.get("TOUCHED", 0) / n, 4),
        "share_never_reached": round(census.get("NEVER_REACHED", 0) / n, 4),
        "share_unmeasured": round(census.get("UNMEASURED", 0) / n, 4),
        "records": results,
    }


def main() -> int:
    doc = fork()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"unfilled fork: {doc['n_unfilled']} unfilled order(s)")
    for k, v in doc["census"].items():
        print(f"  {k:16} {v}")
    print(f"  touched {doc['share_touched']:.0%} | never reached "
          f"{doc['share_never_reached']:.0%} | unmeasured {doc['share_unmeasured']:.0%}")
    if doc["census"].get("TOUCHED"):
        print("  TOUCHED means fills the desk should have had -- an execution defect.")
    if doc["census"].get("NEVER_REACHED"):
        print("  NEVER_REACHED means the level was never viable -- a strategy defect.")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
