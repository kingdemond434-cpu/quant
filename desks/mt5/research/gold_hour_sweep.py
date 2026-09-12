"""RE-EARN THE GOLD ENTRY HOURS INSTEAD OF INHERITING THEM.

`decision_core.GOLD_WINDOWS` is a table of three hours -- asia 7, london_am 13, afternoon 17 --
and `ny_open` sits quarantined beside it with the measurement that killed it (exp +0.029R,
PF 1.05, maxDD -52.8R). That table is a real result, not a guess: session structure in gold is
driven by the London/NY liquidity handover, which is a calendar fact rather than a market-state
one, so a fixed hour is the right SHAPE of answer.

WHAT IS WRONG WITH IT IS THAT NOTHING RE-EARNS IT. The sweep that chose 7/13/17 ran once and no
organ re-runs it, so if the paying hour drifted the desk would go on firing at 7/13/17 forever
and never find out. That is the same "measured once, frozen" defect as every other one found on
2026-09-11: the number was right when it was taken and nothing checks whether it still is.

THE HOURS ARE DYNAMIC ACROSS WEEKS AND FIXED WITHIN A DAY, and the distinction is the whole
design. Choosing an entry hour from live chart state would be a free parameter selected after
seeing the data -- unfalsifiable, and precisely the overfit the ten gates exist to stop. So every
hour is emitted as a CANDIDATE CELL, judged by the same gauntlet as everything else, and an hour
that survives becomes a shadow clock that must earn promotion on its own forward record.

IT DOES NOT TOUCH THE LIVE BOOK, and that is deliberate rather than timid. The three armed
windows are the desk's only forward-evidenced book; a fresh backtest saying hour 9 beats hour 7
is a backtest competing against live forward evidence, and swapping directly would trade proven
evidence for unproven. The new hours enter where every other candidate enters.

THE TRIAL COST IS ZERO, which is why this is worth doing at all. `gate_policy` charges a FIXED
597 trials and a FIXED variance-of-Sharpes, so adding 48 cells raises no other candidate's bar
(test_the_trial_charge_is_fixed_and_never_taxes_breadth pins this). Under the old batch-scaled
charge this sweep would have made every other cell in the docket harder to certify.

    python desks/mt5/research/gold_hour_sweep.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(ROOT))

OUT = DESK / "data" / "hypotheses" / "external_survivors.json"

#: The instrument. Gold is where the armed windows live and where the question was asked.
SYMBOL = "XAUUSD"

#: The family that implements a session-range breakout, and the one GOLD_WINDOWS is expressed in.
FAMILY = "session_range_breakout"

#: Hours to sweep, in BROKER time, which is what `range_start`/`signal_at` are read in. Every
#: hour of the day: the point is to let the data say which pay, not to pre-select a shortlist and
#: call the result a discovery.
HOURS = tuple(range(24))

#: The range that FEEDS each signal hour. Three hours, matching the shape of the two windows that
#: declare one (london_am 10-13 -> signal 13, afternoon 14-17 -> signal 17). `asia` uses the
#: whole session before its hour and is emitted separately below so its shape is not lost.
RANGE_HOURS = 3

#: Two reward multiples, because rr is the parameter the armed windows differ on least and the
#: one most likely to interact with the hour: a thin hour may pay at 1.5R and not at 3R.
RR_VALUES = (1.5, 3.0)


def cells() -> list[dict]:
    """Every (hour x rr) gold breakout cell, plus the from-session-open variant per hour."""
    now = datetime.now(tz=UTC).isoformat()
    out: list[dict] = []
    for h in HOURS:
        for rr in RR_VALUES:
            start = (h - RANGE_HOURS) % 24
            out.append({
                "symbol": SYMBOL,
                "family": FAMILY,
                "params": {"range_start": start, "range_end": h, "signal_at": h,
                           "rr": rr, "ttl_bars": 12, "atr_n": 20},
                # NO PERFORMANCE IS CLAIMED. These fields carry a backtest's record when a row
                # arrives from external discovery; here there is no backtest yet and inventing
                # one would be a fabricated claim wearing a survivor's shape. The gauntlet builds
                # and judges the cell itself, which is the only number that will ever attach.
                "n": 0, "exp_r": None, "max_dd_r": None, "t_stat": None,
                "profit_factor": None, "win_rate": None,
                "source": f"gold_hour_sweep_h{h:02d}_rr{rr}",
                "url": None,
                "producer": "desks/mt5/research/gold_hour_sweep.py",
                # THE PIT STAMP, because the judge refuses an unstamped row the moment any
                # stamped row exists. A cell generated today became knowable today; claiming
                # otherwise would be the exact provenance lie the stamp exists to prevent.
                "first_seen": now,
                "pit_stamp": now,
                "why": ("re-earning the gold entry hour rather than inheriting GOLD_WINDOWS; "
                        "an hour that survives enters as a shadow clock, never as a live swap"),
            })
    return out


def apply(new: list[dict]) -> tuple[int, int]:
    """Merge into the docket, never replacing it. Returns (added, total).

    DEDUPED ON THE EXECUTABLE SPEC, not on the source string: re-running this must not grow the
    docket by 48 rows an hour. Two rows with the same symbol, family and params are the same
    test whatever produced them.
    """
    try:
        existing = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        existing = []
    if not isinstance(existing, list):
        raise SystemExit(f"{OUT} is not a list; refusing to overwrite a docket I cannot read")

    def key(r: dict) -> str:
        return json.dumps([r.get("symbol"), r.get("family"), r.get("params") or {}],
                          sort_keys=True, default=str)

    seen = {key(r) for r in existing if isinstance(r, dict)}
    added = [r for r in new if key(r) not in seen]
    if added:
        existing.extend(added)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing), encoding="utf-8")
        tmp.replace(OUT)
    return len(added), len(existing)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="merge into external_survivors.json")
    a = ap.parse_args(argv)
    new = cells()
    print(f"gold hour sweep: {len(new)} cell(s) across {len(HOURS)} hour(s) x {len(RR_VALUES)} rr")
    print("  armed today (GOLD_WINDOWS): asia 7, london_am 13, afternoon 17; ny_open quarantined")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    added, total = apply(new)
    print(f"  merged {added} new cell(s); docket now {total} row(s) -> {OUT}")
    if not added:
        print("  (all already present -- the sweep is idempotent on the executable spec)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
