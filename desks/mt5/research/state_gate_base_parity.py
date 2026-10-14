"""How many H1 bars each state-gate BASE needs behind its earliest ranked signal for its own
signals to be the same on a live read as on the full history -- measured on real bars.

A state gate ranks its state at a base signal against the states at the base's earlier signals in
the trailing `family_state_gates.RANK_SPAN_DAYS`. So the gate the gateway computes equals the one
that was certified only if the BASE's signals inside that span are the same on the bars the
gateway reads as on the whole file. A base with a long indicator warm-up or a path-dependent entry
chain (audit of #403, must-fix 1: `multi_speed_trend` kept 16 signals on the full frame and 0 on a
400-bar read) needs more bars than the 400 every H1 family has always been read with.

The read is MEASURED, never declared: for every base `state_gate_proposer` can wrap (at the
default params it mints), on each reference symbol and at several frame ends, the base's signals
in the final span are compared between the whole history and a read holding `n` bars behind the
span, for `n` up a ladder. The base's read is the smallest rung that matches everywhere; a base
that matches at no rung is NOT live-reproducible and `family_state_gates.live_refusal` names it,
so its certificates are never written LIVE.

    python research/state_gate_base_parity.py           # print the measurement
    python research/state_gate_base_parity.py --write   # record it in mt5desk/state_gate_base_reads.json

The recorded file is code (it changes what the gateway reads), so it is re-measured and committed
when a base family's code changes; `test_state_gates_live_parity` re-measures it and fails if it
has drifted.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_state_gates as fsg  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
OUT = DESK / "mt5desk" / "state_gate_base_reads.json"
#: An FX major, gold and a seven-day crypto CFD: the three session shapes the desk trades.
SYMBOLS: tuple[str, ...] = ("EURUSD", "XAUUSD", "BTCUSD")
#: Frame ends, in days before the file's last bar.
END_OFFSETS_DAYS: tuple[int, ...] = (0, 120, 240)
#: Bars behind the span a read may hold; the first is the read every H1 family has always had.
LADDER: tuple[int, ...] = (400, 1000, 2000, 4000, 8000)


def _bases() -> list[str]:
    import state_gate_proposer as sgp
    return sorted({b for w in fsg.STATE_GATE_FAMILIES for b in sgp.bases_for(w)})


def _frame(symbol: str) -> pd.DataFrame | None:
    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    d = pd.read_parquet(path)
    if not isinstance(d.index, pd.DatetimeIndex):
        d = d.set_index(pd.to_datetime(d["time"], utc=True))
    return d.sort_index()


def _span_signals(base: str, frame: pd.DataFrame, start: pd.Timestamp) -> set[tuple[int, int]]:
    _d, sigs = fsg.base_signals(frame, base, {})
    return {(int(pd.Timestamp(s.time).value), int(s.side)) for s in sigs
            if pd.Timestamp(s.time) >= start}


def measure_base(base: str, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """{"read": smallest matching rung or None, "checks": n, "first_mismatch": ...}."""
    span = pd.Timedelta(days=fsg.RANK_SPAN_DAYS)
    checks = 0
    worst = 0
    for sym, full in frames.items():
        for off in END_OFFSETS_DAYS:
            end = full.index[-1] - pd.Timedelta(days=off)
            upto = full.loc[:end]
            start = end - span
            in_span = int((upto.index >= start).sum())
            want = _span_signals(base, upto, start)
            found = None
            for n in LADDER:
                got = _span_signals(base, upto.iloc[-(in_span + n):], start)
                if got == want:
                    found = n
                    break
            checks += 1
            if found is None:
                return {"read": None, "checks": checks,
                        "first_mismatch": f"{sym} end-{off}d: no rung up to {LADDER[-1]} matches "
                                          f"({len(want)} signals in the span)"}
            worst = max(worst, found)
    return {"read": worst, "checks": checks, "first_mismatch": None}


def measure() -> dict[str, Any]:
    frames = {s: f for s in SYMBOLS if (f := _frame(s)) is not None}
    if len(frames) < len(SYMBOLS):
        return {"status": "UNMEASURED",
                "why": f"bar store lacks {sorted(set(SYMBOLS) - set(frames))}"}
    return {"status": "MEASURED", "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "symbols": list(SYMBOLS), "end_offsets_days": list(END_OFFSETS_DAYS),
            "ladder": list(LADDER), "rank_span_days": fsg.RANK_SPAN_DAYS,
            "base_params": {}, "bases": {b: measure_base(b, frames) for b in _bases()}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help=f"record the measurement in {OUT.name}")
    args = ap.parse_args(argv)
    doc = measure()
    print(json.dumps(doc, indent=1))
    if doc.get("status") != "MEASURED":
        return 2
    if args.write:
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
