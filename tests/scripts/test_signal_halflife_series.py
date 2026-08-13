"""R0314: the decay series must hold one row per (date, signal), and a retraction is permanent.

The writer appended once per RUN while the row's only time key is the DATE, and the daily cycle
fires more than once a day -- so by 2026-08-12 the live file carried 2-3 byte-identical copies of
32 of its 34 keys. Nothing reads it yet, which is exactly why this had to be closed rather than
deferred: the file exists to BE the time series a future decay fit runs on, and duplicated dates
would have weighted those days 2-3x in that fit, silently, long after anyone remembered the
writer's per-run append semantics. Observation count is not sample size.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "signal_halflife", Path(__file__).resolve().parents[2] / "scripts/signal_halflife.py")
assert _SPEC and _SPEC.loader
signal_halflife = importlib.util.module_from_spec(_SPEC)
sys.modules["signal_halflife"] = signal_halflife
_SPEC.loader.exec_module(signal_halflife)
merge_series = signal_halflife.merge_series


def _row(date: str, signal: str = "kimchi_premium", **kw) -> dict:
    return {"date": date, "signal": signal, "ic_early": 0.1, **kw}


class TestMergeSeries:
    def test_same_day_rerun_replaces_rather_than_appends(self) -> None:
        """The live instance: three runs on one date produced three rows."""
        existing = [_row("2026-08-02"), _row("2026-08-02")]
        merged = merge_series(existing, [_row("2026-08-02", ic_early=0.9)])
        assert len(merged) == 1
        assert merged[0]["ic_early"] == 0.9  # last write wins

    def test_distinct_signals_on_one_date_both_survive(self) -> None:
        """The key is (date, signal) -- deduping on date alone would delete a whole signal."""
        merged = merge_series([], [_row("2026-08-02", "kimchi_premium"),
                                   _row("2026-08-02", "stablecoin_supply")])
        assert len(merged) == 2
        assert {r["signal"] for r in merged} == {"kimchi_premium", "stablecoin_supply"}

    def test_distinct_dates_are_never_collapsed(self) -> None:
        """It is a TIME SERIES: collapsing dates would be the opposite defect."""
        merged = merge_series([_row("2026-08-01")], [_row("2026-08-02")])
        assert [r["date"] for r in merged] == ["2026-08-01", "2026-08-02"]

    def test_output_is_ordered_by_date(self) -> None:
        merged = merge_series([_row("2026-08-09"), _row("2026-08-03")], [_row("2026-08-06")])
        assert [r["date"] for r in merged] == ["2026-08-03", "2026-08-06", "2026-08-09"]

    def test_a_retraction_is_not_silently_dropped_by_a_rerun(self) -> None:
        """A retraction is a judgement about a contaminated observation; the value may be
        recomputed but the judgement must not vanish because a later run said nothing about it."""
        existing = [_row("2026-08-01", retracted_lookahead=True, retraction="R0314: leaky join")]
        merged = merge_series(existing, [_row("2026-08-01", ic_early=0.5)])
        assert len(merged) == 1
        assert merged[0]["ic_early"] == 0.5
        assert merged[0]["retracted_lookahead"] is True
        assert "R0314" in merged[0]["retraction"]

    def test_idempotent(self) -> None:
        """Re-merging an already-clean series must not change it."""
        clean = merge_series([], [_row("2026-08-01"), _row("2026-08-02")])
        assert merge_series(clean, []) == clean


class TestLiveFileShape:
    def test_the_repaired_live_series_has_no_duplicate_keys(self) -> None:
        """Guards the data repair itself: the box-local artifact, if present, stays deduped."""
        import json
        p = Path(__file__).resolve().parents[2] / "data/signal_halflife.jsonl"
        if not p.exists():
            # SKIP, never a silent pass. data/ is gitignored, so in CI this guard examines zero
            # rows -- and a green assertion over an empty set is the vacuous denominator L1.57
            # exists to refuse. On the box, where the series lives, it really runs.
            pytest.skip("data/signal_halflife.jsonl is box-local and absent in this clone")
        rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        keys = [(r.get("date"), r.get("signal")) for r in rows]
        assert len(keys) == len(set(keys)), "duplicate (date, signal) rows are back"


#: Date `status` was retired from the writer (R0467). Rows dated on or before this may carry both
#: verdicts -- they are what was published at the time and are left alone.
_RETIRED_ON = "2026-08-13"


class TestOneVerdictPerRow:
    """R0467: the row published TWO verdicts on one question and they disagreed on live data.

    `status` (AGEING/STABLE/STRENGTHENING off a bare +/-0.03 two-window IC difference, no null
    behind it) sat beside the order-sensitive `decay`. On 2026-08-12 and 08-13 stablecoin_supply
    read STABLE by one and STRENGTHENING then DECAYING by the other. Whichever suits an argument
    is always available, so two labels are worse than either alone.
    """

    def test_the_writer_no_longer_emits_the_untested_status_label(self) -> None:
        import ast
        producer = Path(__file__).resolve().parents[2] / "scripts/signal_halflife.py"
        tree = ast.parse(producer.read_text("utf-8"))
        emitted = {k.value for node in ast.walk(tree) if isinstance(node, ast.Dict)
                   for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        assert "decay" in emitted, "the surviving verdict must still be published"
        assert "status" not in emitted, "the retired verdict is being written again"
        # The MEASUREMENT under the retired label stays: retiring a verdict is not a reason to
        # stop publishing the number it was thresholding.
        assert {"trend", "ic_early", "ic_recent"} <= emitted

    def test_the_live_series_carries_at_most_one_verdict_going_forward(self) -> None:
        import json
        p = Path(__file__).resolve().parents[2] / "data/signal_halflife.jsonl"
        if not p.exists():
            pytest.skip("data/signal_halflife.jsonl is box-local and absent in this clone")
        rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        # THE PAST IS NOT REWRITTEN. Four rows (2026-08-12/13, kimchi_premium and
        # stablecoin_supply) were written in the window where da53431 had added `decay` and
        # `status` had not yet been retired; they carry both, and they are the record of what the
        # desk actually published on those days. Deleting a field from them to make a fence green
        # would edit the evidence rather than the producer -- the failure this desk has paid for
        # (the moat-tape contamination fix went at the WRITE chokepoint, not at the rows).
        # The property with teeth is forward-looking: nothing written after the retirement may
        # carry two verdicts.
        both = [r for r in rows
                if "decay" in r and "status" in r and str(r.get("date", "")) > _RETIRED_ON]
        assert not both, (
            f"{len(both)} row(s) written after {_RETIRED_ON} publish two verdicts on one "
            f"question: {[(r.get('date'), r.get('signal')) for r in both[:5]]}")
