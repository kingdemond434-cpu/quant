#!/usr/bin/env python3
"""Measure the venue's UTC offset from this desk's own H1 bars and write it down.

    python research/measure_broker_clock.py
    python research/measure_broker_clock.py --days 90 --json

WHY THIS ORGAN EXISTS. `state_admission` reports one gap and it is the desk's most important
state dimension:

    "session": "no labeller: this dimension cannot be reconstructed from a timestamp alone, or
                its input (e.g. the broker clock) is unavailable here"

`session_phase.broker_utc_offset_h()` tries a live MetaTrader5 terminal, then
`data/broker_clock.json`, then returns None. There is no terminal off the box, and that file has
NEVER BEEN WRITTEN despite naming the gateway as its only writer. So the session dimension has
never been judged, and state-conditioned allocation is left running on `weekday` ("no measurable
improvement; kept only by the shrinkage") and `event` ("only 1 bucket ever had 15 training
trades") -- which is to say, not running at all, on a desk whose whole mechanism vocabulary is
asia / london_am / afternoon.

The offset does not need a terminal. It is in the bars: see `libs/regime/broker_clock.py` for the
two anchors and the three refusals. This organ is the I/O around that measurement.

IT WRITES A SEPARATE FILE, AND THAT IS THE POINT. `data/broker_clock.json` belongs to the
gateway's live-terminal measurement, which is a strictly better answer and must never be raced or
overwritten by an inference from bars. This writes `data/broker_clock_measured.json`, and
`session_phase` reads it only as the THIRD tier -- live terminal, then the recorded terminal
reading, then this. A measurement from bars is what a host with no terminal deserves; it is not
what a host with one should use.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime.broker_clock import (  # noqa: E402
    MIN_BARS,
    estimate_offset,
    hour_profile,
)

UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "data" / "broker_clock_measured.json"

#: THE SYMBOLS THE ANCHORS ARE DEFINED FOR. The rollover trough and the London/New York overlap
#: are facts about the FOREIGN EXCHANGE session, so the estimate is taken on liquid FX and not on
#: an index or a share CFD, whose volume profile is their own exchange's opening hours and would
#: measure that exchange rather than the venue's stamp clock.
ANCHOR_SYMBOLS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP",
)

#: Trailing days the profile is built from. Long enough that a quiet week cannot move the argmin,
#: short enough that the answer is the offset IN FORCE rather than its average since 2018 -- the
#: venue moves its clock with DST twice a year, and an eight-year median straddles the switch.
DEFAULT_DAYS = 90


def run(days: int = DEFAULT_DAYS, write: bool = True,
        symbols: tuple[str, ...] = ANCHOR_SYMBOLS) -> dict:
    try:
        import pandas as pd
    except ImportError:
        return {"status": "UNMEASURED", "why": "pandas is not importable on this host"}
    profiles: dict[str, list[float]] = {}
    skipped: dict[str, str] = {}
    for sym in symbols:
        f = UNIVERSE / f"{sym}_H1.parquet"
        if not f.exists():
            skipped[sym] = "no local H1 bars"
            continue
        try:
            df = pd.read_parquet(f, columns=["tick_volume"])
        except (OSError, ValueError, KeyError) as exc:
            skipped[sym] = f"unreadable: {type(exc).__name__}"
            continue
        idx = pd.DatetimeIndex(df.index)
        keep = idx >= (idx.max() - pd.Timedelta(days=int(days)))
        prof = hour_profile(idx[keep].hour.to_numpy(), df["tick_volume"].to_numpy()[keep])
        if prof is None:
            skipped[sym] = f"fewer than {MIN_BARS} usable bars in the trailing {days}d"
            continue
        profiles[sym] = [float(x) for x in prof]
    doc = estimate_offset(profiles)
    doc.update({"measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "window_days": int(days), "skipped": skipped,
                "source": "measured_from_bars"})
    if doc.get("status") == "MEASURED":
        doc["utc_offset_hours"] = int(doc["utc_offset_hours"])
        # THE RESIDUAL AMBIGUITY, STATED. The trough anchor is the winter rollover (22:00 UTC)
        # and the summer one is 21:00, so a window inside British Summer Time reads one hour low
        # against it -- which is exactly the +2 trough / +3 peak split this desk's own bars show.
        # The phase buckets are 2-3 hours wide, so a one-hour error moves a minority of trades
        # across a boundary. That is a real cost and a bounded one, and it is not a reason to
        # leave the dimension dark; it IS a reason to say so in the artifact rather than publish
        # a single number as though it were exact.
        peaks = sorted({int(v["offset_by_peak"]) for v in doc["per_symbol"].values()
                        if isinstance(v, dict) and "offset_by_peak" in v})
        doc["dst_ambiguity"] = {
            "offset_by_trough": doc["utc_offset_hours"], "offset_by_peak": peaks,
            "why": ("the rollover anchor is the WINTER cutoff (22:00 UTC); inside summer time it "
                    "reads one hour low. Both anchors are published so a reader can see the "
                    "ambiguity rather than inherit it."),
        }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--json", action="store_true", help="print the whole document")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = run(days=a.days, write=not a.no_write)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"broker clock: {doc.get('status')} offset="
              f"{doc.get('utc_offset_hours')} from {doc.get('n_symbols', 0)} symbol(s)")
        print(f"  {doc.get('why', '')}")
        if doc.get("skipped"):
            print(f"  skipped: {len(doc['skipped'])} symbol(s)")
    # A measurement that could not be taken must not report success: the session dimension stays
    # dark and something has to say so in an exit code.
    return 0 if doc.get("status") == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
