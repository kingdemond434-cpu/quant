"""The stablecoin-supply collector must refuse an implausible vendor read (found closing R0230).

WHAT HAPPENED. On 2026-07-27 scripts/collect_stablecoin_supply.py stored supply_usd=122.37bn
between two ~306bn days -- a 60% collapse in AGGREGATE stablecoin supply with a full recovery the
next morning -- and wrote z20=-239.803 into data/stablecoin_supply.jsonl. DefiLlama's own history
now serves 307.96bn for that date, so the vendor has since corrected what was a transient bad
read. Between the API and the artifact there was no plausibility check of any kind.

WHY IT MATTERS MORE THAN IT LOOKS. That artifact is the live input to a Holm-corrected forward
slot (run_axis_shadows.py:94) -- the pre-registered forward evidence the two-stage discovery law
says is the ONLY thing that may ever promote capital. The damage this time was zero, but only
because the consumer takes np.sign(z), so -239.803 and the true -0.950 give the same short. A bad
read in the other direction flips the sign and books that day's forward return inverted. "The
corruption happened to be sign-preserving" is luck, not a control, and luck is not repeatable.

MIGRATED (R0390): the hand-picked `_MAX_DAILY_MOVE = 0.10` these tests originally pinned has been
replaced by libs.research.axis_integrity.move_bar, which MEASURES the bar from the series' own
history. Every original assertion is preserved below against the new implementation. The one
deliberate behaviour change is documented in `test_the_bar_tightened_and_why`: the measured bar on
the live series is 3.15%, so the old bar's 8.5% allowance is now refused. That is a TIGHTENING,
the safe direction, and it is loud (SystemExit) rather than silent.
"""

from __future__ import annotations

import importlib
import json
import random

import pytest

from libs.research.axis_integrity import check_move, move_bar

cs = importlib.import_module("scripts.collect_stablecoin_supply")


def _live_like(start: float = 300e9) -> list[float]:
    """A series REPRODUCING THE MEASURED MOVE DISTRIBUTION of DefiLlama's real last 900 days.

    Not a hand-drawn ramp. The first attempt at this fixture used a regular +0.1%/-0.05% zigzag,
    whose MAD is near zero, and it derived a 0.15% bar -- 20x tighter than reality -- which would
    have "proved" the gate worked while testing a bar the live series never sees. Desk lesson
    L0134: build the fixture from the real on-disk shape.

    Measured on DefiLlama 2026-08-12 over the last 900 days: median |move| 0.129%, MAD 0.090%,
    max 2.10% -> bar 3.15%. Seed 0 at sigma 0.0020 reproduces median 0.131%, MAD 0.078%, and the
    planted 2.10% extreme, deriving the same 3.15%.
    """
    rng = random.Random(0)
    moves = [abs(rng.gauss(0.0, 0.0020)) for _ in range(899)]
    moves[400] = 0.0210                      # the real 900-day extreme
    out = [start]
    for i, m in enumerate(moves):
        out.append(out[-1] * (1.0 + (m if i % 2 else -m)))
    return out


class TestImplausibleMoveDetection:
    def test_the_actual_2026_07_27_read_is_refused(self) -> None:
        """The measured incident, replayed: 307.96bn -> 122.37bn must not be storable."""
        v = check_move(122.37e9, 307.96e9, move_bar(_live_like()))
        assert not v.ok, "a 60% one-day collapse in aggregate stablecoin supply must be refused"
        assert "-60" in v.reason and "%" in v.reason, (
            f"the reason must quantify the move, got: {v.reason}"
        )

    def test_a_high_side_bad_read_is_refused_too(self) -> None:
        """The direction that would actually have flipped the forward clock's sign."""
        assert not check_move(612.0e9, 306.0e9, move_bar(_live_like())).ok, (
            "a doubling is as implausible as a halving"
        )

    @pytest.mark.parametrize("latest,prev", [
        (306.05e9, 305.86e9),   # a real consecutive pair from the live series
        (309.02e9, 307.70e9),
    ])
    def test_real_daily_moves_are_accepted(self, latest: float, prev: float) -> None:
        """The gate must not cost real data. Measured against DefiLlama's real last-900-day
        history, the derived bar refuses ZERO of those 900 days."""
        assert check_move(latest, prev, move_bar(_live_like())).ok, (
            "a plausible move was refused -- this gate would silently starve the axis"
        )

    def test_no_previous_value_never_blocks(self) -> None:
        """First observation has nothing to compare against; refusing it would deadlock the
        collector on an empty series."""
        bar = move_bar(_live_like())
        assert check_move(306.0e9, 0.0, bar).ok
        assert check_move(306.0e9, -1.0, bar).ok

    def test_the_bar_is_not_quietly_loose(self) -> None:
        """A plausibility bar wide enough to admit the incident is decoration. The original pinned
        `_MAX_DAILY_MOVE <= 0.10`; the measured bar must be at least as tight."""
        bar = move_bar(_live_like())
        assert bar.value is not None
        assert bar.value <= 0.10, (
            "at ~$306bn a 10% day is a $30bn mint or burn; a looser bar readmits the bad read "
            f"this test exists for -- got {bar.value:.2%}"
        )

    def test_the_bar_tightened_and_why(self) -> None:
        """THE ONE DELIBERATE BEHAVIOUR CHANGE, pinned so it cannot drift back silently.

        The old hand-picked 10% bar admitted a -8.5% day. The measured bar is ~3.15%, which is
        still 1.5x the largest move in the series' last 900 days (2.10%), so a -8.5% day is 4x
        anything observed in 2.5 years. It is now REFUSED -- loudly, via SystemExit, which a human
        sees and can act on -- rather than stored. False refusal costs one day of data and a
        visible failure; false acceptance costs a forward slot, silently. Measured false-refusal
        rate on 900 real days: ZERO.
        """
        bar = move_bar(_live_like())
        assert bar.value is not None
        assert 0.02 < bar.value < 0.05, f"bar drifted off its measured basis: {bar.value:.2%}"
        assert not check_move(280.0e9, 306.0e9, bar).ok, "-8.5% is 4x the 900-day max"

    def test_the_collector_still_holds_a_refusal_path(self) -> None:
        """The helper is only a control if the collector actually calls it. Guards against the
        migration having left the import in place and the check behind it deleted (L1.49)."""
        import inspect
        body = inspect.getsource(cs.main)
        assert "check_move" in body and "REFUSED" in body, (
            "collect_stablecoin_supply.main no longer refuses an implausible read"
        )
        assert "raise SystemExit" in body, "the refusal must exit non-zero, not just print"


class TestVendorRevisionIsRecorded:
    def test_the_collector_records_the_revision_delta(self) -> None:
        """R0389: the screen recomputes on the vendor's REVISED history every run, so the as-of
        values must be captured rather than discarded -- via R0316's existing vintage store, not a
        second implementation of it (L2.9 upgrade-before-build)."""
        import inspect
        body = inspect.getsource(cs.main)
        assert "vintage.record" in body and "vintage.summarise" in body, (
            "the vendor-revision vintage store is not wired into the collector"
        )
        assert "revision_report" not in body, (
            "R0389 must reuse libs/research/vintage.py (R0316), not a second implementation"
        )


class TestStoredSeriesContract:
    def test_live_series_rows_carry_the_fields_the_forward_clock_reads(self) -> None:
        """run_axis_shadows.py:94 reads the `z20` field of every row. A row missing it would be
        skipped or crash the clock; this asserts the contract the collector writes to."""
        from pathlib import Path
        p = Path("data/stablecoin_supply.jsonl")
        if not p.exists():                       # gitignored runtime artifact; absent in CI
            pytest.skip("point-in-time series not present on this box")
        rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]
        assert rows, "series file exists but is empty"
        for r in rows:
            assert {"date", "supply_usd", "z20"} <= set(r), f"row missing clock fields: {r}"
