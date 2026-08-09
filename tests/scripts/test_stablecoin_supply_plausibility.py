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
"""

from __future__ import annotations

import importlib
import json

import pytest

cs = importlib.import_module("scripts.collect_stablecoin_supply")


class TestImplausibleMoveDetection:
    def test_the_actual_2026_07_27_read_is_refused(self) -> None:
        """The measured incident, replayed: 307.96bn -> 122.37bn must not be storable."""
        why = cs._implausible(122.37e9, 307.96e9)
        assert why, "a 60% one-day collapse in aggregate stablecoin supply must be refused"
        assert "-60" in why and "%" in why, f"the reason must quantify the move, got: {why}"

    def test_a_high_side_bad_read_is_refused_too(self) -> None:
        """The direction that would actually have flipped the forward clock's sign."""
        assert cs._implausible(612.0e9, 306.0e9), "a doubling is as implausible as a halving"

    @pytest.mark.parametrize("latest,prev", [
        (306.05e9, 305.86e9),   # a real consecutive pair from the live series
        (309.02e9, 307.70e9),
        (280.0e9, 306.0e9),     # -8.5%: large, below the bar, and must still pass
    ])
    def test_real_daily_moves_are_accepted(self, latest: float, prev: float) -> None:
        """The gate must not cost real data. Over DefiLlama's full 3,172-day history the last
        |move| above 10% was 2020-04-03, when the entire float was ~$7bn."""
        assert not cs._implausible(latest, prev), (
            "a plausible move was refused -- this gate would silently starve the axis"
        )

    def test_no_previous_value_never_blocks(self) -> None:
        """First observation has nothing to compare against; refusing it would deadlock the
        collector on an empty series."""
        assert not cs._implausible(306.0e9, 0.0)
        assert not cs._implausible(306.0e9, -1.0)

    def test_the_bar_is_not_quietly_loose(self) -> None:
        """A plausibility bar wide enough to admit the incident is decoration. Pins the constant
        so a future edit that would re-admit the 2026-07-27 read has to argue for it here."""
        assert cs._MAX_DAILY_MOVE <= 0.10, (
            "at ~$306bn a 10% day is a $30bn mint or burn; a looser bar readmits the bad read "
            "this test exists for"
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
