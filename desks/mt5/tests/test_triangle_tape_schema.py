"""A tick parquet's time axis may be a column or an index, and neither may crash the hourly cycle.

MEASURED on the box 2026-09-06: `tick tape FAILED: KeyError: "['ts'] not in index"`, every hour.
`tape.py` writes ticks with ``index=False`` and an explicit `ts` column, but the tape on that box
has been written by more than one generation of this code, and a frame that went through an
index-carrying writer reads back with `ts` as the INDEX and no such column. ``frame[["ts", "bid",
"ask"]]`` then raises.

The failure was quiet in the way that matters. `record_tape` runs `tape.main` first and it kept
succeeding -- 359,107 ticks on the run that produced this trace -- so the desk went on collecting
its irreplaceable broker-native tape while the triangle evidence stopped being produced entirely,
and the only symptom was one line in an hourly log that had said the same thing for two days.
"""
from __future__ import annotations

import pathlib

import pandas as pd
import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
SRC = (DESK / "mt5desk" / "triangle_tape.py").read_text("utf-8")


def _module() -> dict:
    """Load the module's own source WITHOUT importing `mt5desk.tape`.

    `triangle_tape` imports TICKS from the tape module, which reaches for MT5 paths that do not
    exist off the box. The functions under test are pure pandas, so the import is stubbed rather
    than the test being skipped -- a schema guard that only runs on the one machine that already
    has the bug is no guard at all.
    """
    src = SRC.replace("from mt5desk.tape import TICKS",
                      "import pathlib as _pl; TICKS = _pl.Path('/nonexistent')")
    namespace: dict = {}
    exec(compile(src, "triangle_tape.py", "exec"), namespace)  # noqa: S102 -- own source, no input
    return namespace


TS = pd.to_datetime(["2026-09-06T12:00:00Z", "2026-09-06T12:00:01Z"])
QUOTES = pd.DataFrame({"ts": TS, "bid": [1.0, 1.1], "ask": [1.2, 1.3]})


@pytest.mark.parametrize("shape", ["column", "named_index", "unnamed_index"])
def test_ts_is_recovered_whatever_shape_the_parquet_was_written_in(shape: str) -> None:
    ns = _module()
    frame = QUOTES.copy()
    if shape != "column":
        frame = frame.set_index("ts")
        if shape == "unnamed_index":
            frame.index.name = None
    out = ns["normalise"](frame)
    assert ns["QUOTE_COLUMNS"] <= set(out.columns), f"{shape}: ts was not recovered"
    assert len(out) == len(QUOTES), f"{shape}: normalising changed the row count"


def test_a_frame_with_no_time_axis_stays_unusable() -> None:
    """Recovery must not become invention. A frame carrying no time at all has to remain
    unusable so `build()` reports it as UNMEASURED against its own symbol -- absence is not a
    pass, and a manufactured `ts` would align quotes that were never simultaneous."""
    ns = _module()
    out = ns["normalise"](pd.DataFrame({"bid": [1.0], "ask": [1.2]}))
    assert not ns["QUOTE_COLUMNS"] <= set(out.columns)


def test_a_bad_leg_is_reported_against_its_symbol_and_does_not_raise() -> None:
    """The whole point of the change: one malformed leg must not take the hourly cycle down, and
    the report must name WHICH leg and what it actually carried."""
    ns = _module()
    good = QUOTES.copy()
    bad = pd.DataFrame({"bid": [1.0], "ask": [1.2]})
    ns["TRIANGLES"] = (("EURGBP", "EURUSD", "GBPUSD"),)
    ns["_latest"] = lambda symbol: bad if symbol == "GBPUSD" else good

    report = ns["build"]()

    (row,) = report["rows"]
    assert row["status"] == "UNMEASURED"
    assert "GBPUSD" in row["why"], "the report does not name the leg that was unusable"
    assert "ts" in row["why"], "the report does not say what was missing"


def test_an_absent_leg_is_named_too() -> None:
    ns = _module()
    ns["TRIANGLES"] = (("EURGBP", "EURUSD", "GBPUSD"),)
    ns["_latest"] = lambda symbol: None if symbol == "EURUSD" else QUOTES.copy()

    (row,) = ns["build"]()["rows"]

    assert row["status"] == "UNMEASURED"
    assert "EURUSD" in row["why"], "'one or more legs' sends the reader to three directories"
