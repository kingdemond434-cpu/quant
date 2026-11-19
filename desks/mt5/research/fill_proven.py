#!/usr/bin/env python3
"""FILL-PROVEN SLEEVES -- forward R after the real spread, outside the rollover hours.

WHY THIS EXISTS (2026-11-19). Every forward clock is replayed on BID bars. In the broker's
rollover hours (00:00-01:59 on the venue clock) the spread runs 10-1000x normal, so a clock
that enters there books a fill no live order gets. 36 "promotable" candidates and the claim
that "own-price families hold 95-100%" turned out to enter in exactly those hours. A box read
of 168 spread-adjustable sleeves found 11 positive after the spread outside 00:00-01:59 with
n>=10, 80 negative, and the rest too thin to judge.

WHAT IT WRITES. `reports/FILL_PROVEN.json`, each pass:

    sleeves  -- the admitted list, [{sleeve, n_out, adjR_out, lcb95_out, p_out}]: n_out >= MIN_N,
                adjR_out > 0 AND the sleeve survives Benjamini-Hochberg at FDR_Q across every
                sleeve tested (a positive mean out of ~168 tries is not evidence on its own)
    table    -- every sleeve read, with n/adjR for all trades, outside rollover and inside it,
                and how many trades had no measured spread (UNMEASURED, never charged zero)

The one-pipe roster diff admits a sleeve beyond the existing book ONLY when it is in `sleeves`.
An absent or empty file admits nothing extra, so this organ fails closed.

THE METHOD (the same one as the 11-19 box read).
  * Trades: the clocks' own forward-phase rows in `reports/shadow/ledger_*.json`, walked through
    `forward_ledger.iter_ledgers`, so a frozen shared legacy file is never read as one clock's series.
  * Spread: the median (ask - bid) / mid per symbol and per hour from the box's own tick tape
    (`data/tape/ticks/<SYM>/<day>.parquet`) over the last TAPE_DAYS day files. Tape `ts` comes
    from `time_msc`, which is the VENUE clock, and the ledgers' `entry_time` is the bar stamp,
    also on the venue clock. Both hours therefore sit on one clock, and nothing is shifted.
  * adjR = R - spread_frac * entry / stop_distance, charged once per round trip at the entry
    hour. The stop distance is |entry - stop|, or |exit - entry| / |R| when there is no stop.
    The charge slightly flatters a trade that exits in a wider hour, and the artifact says so.

WHAT IT IS NOT. A per-hour slice of a sleeve is a HYPOTHESIS: post-hoc hour selection is
selection. This organ admits at sleeve level only, using every non-rollover trade. An hour
filter needs its own preregistered forward test.

Reads only. No MetaTrader import, no terminal attach, no network, no LLM.

    python desks/mt5/research/fill_proven.py --once
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent
SHADOW = DESK / "reports" / "shadow"
TICKS = DESK / "data" / "tape" / "ticks"
OUT = DESK / "reports" / "FILL_PROVEN.json"

SCHEMA = "fill-proven/1"
#: Venue-clock hours treated as rollover. The 11-19 read found the 00 and 01 slices deeply
#: negative across sleeves.
ROLLOVER_HOURS = frozenset({0, 1})
#: Minimum number of trades outside rollover before a sleeve can be admitted.
MIN_N = 10
#: Most recent tape day files read per symbol for the spread table.
TAPE_DAYS = 30
#: False-discovery rate across every sleeve with n_out >= MIN_N (Audit 11-19: 11 positives out of
#: 168 is about what noise alone gives, so a positive mean is not enough on its own).
FDR_Q = 0.10
#: A quote whose spread is above this fraction of mid is a broken print and is dropped.
MAX_SANE_SPREAD_FRAC = 0.2


def _num(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return None
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _hour(stamp: object) -> int | None:
    """The hour as written. Ledger stamps are bar stamps on the venue clock, with or without an
    offset suffix, and the wall-clock hour is the one that matters, so no conversion is done."""
    s = str(stamp or "").strip()
    if len(s) < 13:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).hour
    except ValueError:
        return None


def symbol_of(row: dict[str, Any], label: str) -> str:
    sym = str(row.get("symbol") or "").strip().upper()
    return sym or label.split("_", 1)[0].upper()


def stop_distance(row: dict[str, Any]) -> float | None:
    entry, stop = _num(row.get("entry")), _num(row.get("stop"))
    if entry and stop and abs(entry - stop) > 0:
        return abs(entry - stop)
    exit_, r = _num(row.get("exit")), _num(row.get("r_multiple"))
    if r is None:
        r = _num(row.get("r"))
    if entry and exit_ and r and abs(r) > 1e-9 and abs(exit_ - entry) > 0:
        return abs(exit_ - entry) / abs(r)
    return None


def tape_files(symbol: str, root: Path = TICKS) -> list[tuple[str, Path]]:
    """(ISO day, path) oldest first. Both naming conventions; when a day exists in both, the
    larger file wins (`feed_clock_lab.tape_days` / `moat_series.tape_index`'s rule)."""
    d = root / symbol
    days: dict[str, Path] = {}
    if not d.is_dir():
        return []
    for p in d.glob("*.parquet"):
        stem = p.stem
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            key = stem
        elif len(stem) == 8 and stem.isdigit():
            key = f"{stem[:4]}-{stem[4:6]}-{stem[6:]}"
        else:
            continue
        try:
            if key in days and p.stat().st_size <= days[key].stat().st_size:
                continue
        except OSError:
            continue
        days[key] = p
    return sorted(days.items())


def _venue_hours(path: Path):
    """(hours, bid, ask) from one tape day file, or None. The recorder writes `ts` (from
    time_msc); the moat's compact files carry only `time_msc`. Both are the venue clock."""
    import pandas as pd
    import pyarrow.parquet as pq
    try:
        names = set(pq.read_schema(path).names)
    except Exception:
        return None
    stamp = "ts" if "ts" in names else ("time_msc" if "time_msc" in names else None)
    if stamp is None or not {"bid", "ask"} <= names:
        return None
    try:
        df = pd.read_parquet(path, columns=[stamp, "bid", "ask"]).dropna()
    except Exception:
        return None
    if stamp == "time_msc":
        when = pd.to_datetime(df[stamp].astype("int64"), unit="ms", utc=True)
    else:
        when = pd.to_datetime(df[stamp], utc=True)
    return when.dt.hour, df["bid"], df["ask"]


def spread_by_hour(symbol: str, root: Path = TICKS,
                   days: int = TAPE_DAYS) -> tuple[dict[int, float], int]:
    """({venue hour: median (ask-bid)/mid}, day files actually read) from the last `days`
    tape files. A file that cannot be read is not counted, so `days_read` says what was used."""
    import pandas as pd
    by_hour: dict[int, list[float]] = defaultdict(list)
    used = 0
    for _day, path in tape_files(symbol, root)[-days:]:
        got = _venue_hours(path)
        if got is None:
            continue
        hours, bid, ask = got
        ok = (bid > 0) & (ask > bid)
        if not ok.any():
            continue
        mid = (ask[ok] + bid[ok]) / 2.0
        frame = pd.DataFrame({"h": hours[ok].to_numpy(),
                              "f": ((ask[ok] - bid[ok]) / mid).to_numpy()})
        frame = frame[frame["f"] <= MAX_SANE_SPREAD_FRAC]
        if frame.empty:
            continue
        used += 1
        for h, med in frame.groupby("h")["f"].median().items():
            by_hour[int(h)].append(float(med))
    # The median of the daily medians, so one wild day cannot set the hour.
    return {h: statistics.median(v) for h, v in by_hour.items() if v}, used


def adjusted_trades(rows: list[dict[str, Any]], label: str,
                    spreads: dict[int, float]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("phase") or "") != "forward":
            continue
        r = _num(row.get("r_multiple"))
        if r is None:
            r = _num(row.get("r"))
        hour = _hour(row.get("entry_time") or row.get("opened_at"))
        if r is None or hour is None:
            continue
        entry, dist = _num(row.get("entry")), stop_distance(row)
        frac = spreads.get(hour)
        if frac is None or not entry or not dist:
            out.append({"hour": hour, "r": r, "adj": None})
            continue
        out.append({"hour": hour, "r": r, "adj": r - frac * entry / dist})
    return out


def _cut(trades: list[dict[str, Any]]) -> tuple[int, float | None]:
    adj = [t["adj"] for t in trades if t["adj"] is not None]
    return len(adj), (round(statistics.fmean(adj), 4) if adj else None)


def one_sided_p(values: list[float]) -> tuple[float | None, float | None]:
    """(p for mean <= 0, 95% one-sided lower bound of the mean) by Student t; None under 2."""
    n = len(values)
    if n < 2:
        return None, None
    from scipy import stats
    mean, sd = statistics.fmean(values), statistics.stdev(values)
    if sd <= 0:
        return (0.0 if mean > 0 else 1.0), mean
    se = sd / math.sqrt(n)
    p = float(stats.t.sf(mean / se, n - 1))
    lcb = mean - float(stats.t.ppf(0.95, n - 1)) * se
    return p, lcb


def bh_pass(pvals: dict[str, float], q: float) -> set[str]:
    """Benjamini-Hochberg at `q` over every sleeve that was eligible to be tested."""
    ranked = sorted(pvals.items(), key=lambda kv: kv[1])
    m, cut = len(ranked), 0
    for i, (_k, p) in enumerate(ranked, 1):
        if p <= q * i / m:
            cut = i
    return {k for k, _p in ranked[:cut]}


def sleeve_row(label: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    out_t = [t for t in trades if t["hour"] not in ROLLOVER_HOURS]
    roll_t = [t for t in trades if t["hour"] in ROLLOVER_HOURS]
    n_all, a_all = _cut(trades)
    n_out, a_out = _cut(out_t)
    n_roll, a_roll = _cut(roll_t)
    p_out, lcb_out = one_sided_p([t["adj"] for t in out_t if t["adj"] is not None])
    return {"p_out": None if p_out is None else round(p_out, 5),
            "lcb95_out": None if lcb_out is None else round(lcb_out, 4),"sleeve": label, "n_all": n_all, "adjR_all": a_all, "n_out": n_out,
            "adjR_out": a_out, "n_rollover": n_roll, "adjR_rollover": a_roll,
            "n_unmeasured": sum(1 for t in trades if t["adj"] is None)}


def eligible(row: dict[str, Any]) -> bool:
    a = row.get("adjR_out")
    return int(row.get("n_out") or 0) >= MIN_N and isinstance(a, float) and a > 0


def admitted(row: dict[str, Any]) -> bool:
    return eligible(row) and bool(row.get("fdr_pass"))


def build(shadow: Path = SHADOW, ticks: Path = TICKS,
          now: datetime | None = None) -> dict[str, Any]:
    from libs.research import forward_ledger as fl
    now = now or datetime.now(UTC)
    spread_cache: dict[str, dict[int, float]] = {}
    days_read: dict[str, int] = {}
    table: list[dict[str, Any]] = []
    unread: list[str] = []
    for path in fl.iter_ledgers(shadow):
        label = fl.label_of(path)
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unread.append(label)
            continue
        if not isinstance(rows, list) or not rows:
            continue
        sym = symbol_of(rows[0] if isinstance(rows[0], dict) else {}, label)
        if sym not in spread_cache:
            spread_cache[sym], days_read[sym] = spread_by_hour(sym, ticks)
        trades = adjusted_trades(rows, label, spread_cache[sym])
        if trades:
            row = sleeve_row(label, trades)
            row["symbol"] = sym
            table.append(row)
    tested = {r["sleeve"]: r["p_out"] for r in table
              if int(r["n_out"] or 0) >= MIN_N and r["p_out"] is not None}
    passed = bh_pass(tested, FDR_Q)
    for r in table:
        r["fdr_pass"] = r["sleeve"] in passed
    table.sort(key=lambda r: (not admitted(r), not eligible(r), -(r["adjR_out"] or -9e9)))
    sleeves = [{"sleeve": r["sleeve"], "n_out": r["n_out"], "adjR_out": r["adjR_out"],
                "lcb95_out": r["lcb95_out"], "p_out": r["p_out"]}
               for r in table if admitted(r)]
    return {
        "schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
        "rule": {"rollover_hours_venue": sorted(ROLLOVER_HOURS), "min_n_out": MIN_N,
                 "adjR_out": "> 0", "tape_days": TAPE_DAYS,
                 "fdr": f"Benjamini-Hochberg q={FDR_Q} on one-sided t over n_out >= {MIN_N}",
                 "n_tested": len(tested)},
        "method": ("forward-phase ledger R minus the median tape (ask-bid)/mid at the entry hour "
                   "x entry / stop distance, once per round trip; hours on the venue clock"),
        "limitations": [
            "one spread charged at the entry hour; a trade exiting in a wider hour is flattered",
            "per-hour slices are hypotheses; admission is at sleeve level only",
            "a trade with no measured spread for its hour is UNMEASURED and not counted",
        ],
        "n_sleeves_read": len(table), "n_admitted": len(sleeves),
        "n_positive_failing_fdr": sum(1 for r in table if eligible(r) and not admitted(r)),
        "tape_days_read": dict(sorted(days_read.items())),
        "symbols_without_tape": sorted(s for s, v in spread_cache.items() if not v),
        "unreadable_ledgers": unread,
        "sleeves": sleeves, "table": table,
    }


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="build and write the artifact once")
    args = ap.parse_args(argv)
    if not args.once:
        ap.print_help()
        return 0
    doc = build()
    write(doc)
    print(f"fill_proven: {doc['n_admitted']} admitted of {doc['n_sleeves_read']} sleeves read; "
          f"{len(doc['symbols_without_tape'])} symbols without tape")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
