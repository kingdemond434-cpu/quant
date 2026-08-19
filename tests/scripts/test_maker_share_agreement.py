"""Two organs, one tape, one number -- and no fabricated zero (R0324 + R0064).

`run_cashcarry_executor` stamps `spot_mode`/`fut_mode` on every trade row: ONE mode per LEG, so a
pair that rests maker on spot and crosses taker on futures is two observations, not one. Two organs
read those strings -- scripts/fill_quality_monitor (the weekly "is the maker fix working?" loop) and
scripts/run_trade_forensics (the daily integrity flag against the 0.60 target). Before this pair of
rows they disagreed in opposite directions:

  R0324  the monitor could not read the schema at all and refused to measure it (an honest guard,
         but the tape stayed unmeasured);
  R0064  the forensics counted EVERY truthy mode, so `already-flat` legs -- the venue saying the
         leg was ALREADY flat, no order placed, no fill, no fee -- scored non-maker and pushed
         maker_share below target on arithmetic alone: a false integrity flag.

These tests pin the two properties that make the numbers trustworthy: the organs agree EXACTLY on
the same trades, and an all-`already-flat` set reports UNMEASURED rather than a measured 0.0.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.fill_quality_monitor import measure, verdict  # noqa: E402
from scripts.run_trade_forensics import _leg_share  # noqa: E402

from libs.execution import leg_modes  # noqa: E402

#: A known trade set: one maker leg, one taker leg, one already-flat leg, plus a taker_fallback.
#: Measurable legs = maker, taker, taker_fallback, taker -> 1/4 = 0.25. `already-flat` is not in
#: the denominator; if it were, the same set would read 1/5 = 0.20 -- the R0064 deflation.
_TRADES: list[dict[str, Any]] = [
    {"symbol": "BNBUSDT", "spot_mode": "maker", "fut_mode": "taker", "notional": 100.0,
     "fee": 0.05},
    {"symbol": "FILUSDT", "spot_mode": "taker_fallback", "fut_mode": "already-flat",
     "notional": 100.0, "fee": 0.05},
    {"symbol": "OPUSDT", "spot_mode": "taker", "notional": 100.0, "fee": 0.05},
]
_EXPECTED_SHARE = 0.25

#: Every leg already flat: nothing was quoted, so there is no denominator to divide by.
_FLAT_ONLY: list[dict[str, Any]] = [
    {"symbol": "FILUSDT", "spot_mode": "already-flat", "fut_mode": "already-flat",
     "notional": 10.0},
    {"symbol": "OPUSDT", "spot_mode": "already-flat", "fut_mode": "already-flat",
     "notional": 10.0},
]


def _forensics_share(trades: list[dict[str, Any]]) -> float | None:
    """The whole-book maker share exactly as run_trade_forensics computes it for `maker_share`."""
    legs = [m for x in trades for m in (x.get("spot_mode"), x.get("fut_mode"))
            if leg_modes.placed_order(m)]
    return round(sum(leg_modes.is_maker(m) for m in legs) / len(legs), 3) if legs else None


class TestBothOrgansAgree:
    def test_same_trades_yield_the_same_maker_share(self) -> None:
        monitor = measure(_TRADES)["maker_rate"]
        forensics = _forensics_share(_TRADES)
        assert monitor == _EXPECTED_SHARE
        assert forensics == _EXPECTED_SHARE
        assert monitor == forensics, "one tape must not produce two maker shares"

    def test_already_flat_is_out_of_the_denominator(self) -> None:
        """Dropping the no-order leg, not scoring it taker, is the whole of R0064."""
        m = measure(_TRADES)
        assert m["measured_legs"] == 4, "5 mode strings, 4 of them placed an order"
        assert m["fills"] == len(_TRADES), "row count is unchanged; only the denominator moved"
        deflated = round(1 / 5, 4)
        assert m["maker_rate"] > deflated, "counting already-flat would deflate the share"

    def test_per_leg_parsing_beats_one_verdict_per_row(self) -> None:
        """A row whose legs disagree contributes BOTH observations, not one rounded verdict."""
        mixed = [{"spot_mode": "maker", "fut_mode": "taker", "notional": 10.0}]
        assert measure(mixed)["maker_rate"] == 0.5
        assert _forensics_share(mixed) == 0.5

    def test_leg_share_agrees_per_leg_too(self) -> None:
        assert _leg_share(_TRADES, "spot_mode") == round(1 / 3, 3)   # maker, taker_fallback, taker
        assert _leg_share(_TRADES, "fut_mode") == 0.0                # taker; already-flat dropped


class TestAlreadyFlatOnlyIsUnmeasured:
    def test_monitor_reports_unmeasured_never_zero(self) -> None:
        m = measure(_FLAT_ONLY)
        assert m["maker_rate"] is None, "0.0 here would be a rate built from legs that never traded"
        assert m["no_order_legs_only"] is True
        assert m["measured_legs"] == 0
        assert m["fills"] == len(_FLAT_ONLY), "it saw the rows; there is just nothing to judge"

    def test_forensics_reports_no_denominator(self) -> None:
        assert _forensics_share(_FLAT_ONLY) is None
        assert _leg_share(_FLAT_ONLY, "spot_mode") is None
        assert _leg_share(_FLAT_ONLY, "fut_mode") is None

    def test_neither_organ_can_be_read_as_a_measured_zero(self) -> None:
        assert measure(_FLAT_ONLY)["maker_rate"] == _forensics_share(_FLAT_ONLY) is None

    def test_the_unmeasured_set_never_pages_as_a_finding(self) -> None:
        """UNMEASURED must route to NO DATA, not to the STALLED defect line."""
        v, why = verdict(measure(_FLAT_ONLY), {"maker_rate": 0.242})
        assert v == "NO DATA"
        assert "DEFECT" not in why


class TestVocabularyIsShared:
    """One vocabulary or the organs drift apart again -- that drift IS the defect these rows fix."""

    def test_every_executor_mode_is_classified(self) -> None:
        stamped = {"maker", "maker_pending", "taker", "taker_fallback", "limit_only_unfilled",
                   "already-flat", "mkt", "limit"}
        assert stamped <= leg_modes.KNOWN_MODES


#: THE WIDEST REAL SCHEMA, not the narrowest. Every fixture above stamps a leg mode on every row,
#: which is why they all passed while the live tape was being mis-measured by 16.9x: the real
#: `data/cashcarry_trades.json` carries `spot_mode`/`fut_mode` on 25 of 500 rows and NOTHING
#: liquidity-shaped on the other 475. A fixture that cannot express the unpriced, unstamped row is
#: structurally incapable of revealing what the reader does with it.
_MIXED_TAPE: list[dict[str, Any]] = [
    {"symbol": "BNBUSDT", "spot_mode": "maker", "fut_mode": "maker", "notional": 100.0},
    {"symbol": "OPUSDT", "spot_mode": "taker", "notional": 100.0},
    # ...and the rows the executor wrote before the patient-maker path existed:
    *({"symbol": "OLDUSDT", "event": "close", "qty": 1.0, "notional": 100.0} for _ in range(50)),
]


class TestUnstampedRowsLeaveTheDenominator:
    """A row that records no liquidity is UNMEASURABLE -- never a taker (measured 2026-08-05).

    The live tape read 18/505 = 3.6% because 475 rows with no liquidity field at all were each
    scored a taker fill, while the 30 legs that actually recorded a mode read 18/30 = 60.0% and
    `run_trade_forensics` -- same tape, same vocabulary -- published 0.60.
    """

    def test_bare_rows_are_not_counted_as_takers(self) -> None:
        m = measure(_MIXED_TAPE)
        assert m["measured_legs"] == 3, "2 maker legs + 1 taker leg; the 50 bare rows are silent"
        assert m["unmeasurable_rows"] == 50
        assert m["maker_rate"] == round(2 / 3, 4)

    def test_the_organs_still_agree_on_a_tape_that_is_mostly_unstamped(self) -> None:
        # Compared at the COARSER organ's precision: the monitor rounds to 4dp and forensics to
        # 3dp, so an exact `==` only holds for shares that terminate at 3dp. `_EXPECTED_SHARE`
        # (0.25) does; 2/3 does not. That is a fixture artifact, not a disagreement -- but it is
        # why the agreement assertion above never had to survive a repeating decimal.
        assert round(measure(_MIXED_TAPE)["maker_rate"], 3) == _forensics_share(_MIXED_TAPE)

    def test_coverage_travels_with_the_rate(self) -> None:
        """A rate over 4% of the tape must never be readable as a rate for the tape."""
        m = measure(_MIXED_TAPE)
        assert m["coverage"] == round(2 / 52, 4)
        assert m["fills"] == 52, "row count unchanged; only the denominator moved"

    def test_a_liquidity_field_still_fails_closed(self) -> None:
        """The narrowing must not reach rows that DO record liquidity -- those still score taker."""
        assert measure([{"maker": False, "notional": 10.0}])["maker_rate"] == 0.0
        assert measure([{"role": "taker", "notional": 10.0}])["maker_rate"] == 0.0


class TestUnpricedTapeReportsUnmeasuredCost:
    """0 of 500 live rows carry a fee field, so the tape cannot price a round trip at all."""

    def test_bps_per_rt_is_none_not_zero(self) -> None:
        m = measure(_MIXED_TAPE)
        assert m["bps_per_rt"] is None, "0.0 bps on a book paying $1750.88 commission is fabricated"
        assert m["fees_usd"] is None
        assert m["fee_concentration"] is None
        assert m["priced_rows"] == 0
        assert "UNMEASURED" in m["fee_note"]

    def test_a_priced_tape_still_reports_a_cost(self) -> None:
        """The refusal must be about ABSENT fee fields, never about a genuinely free fill."""
        m = measure([{"spot_mode": "taker", "notional": 1000.0, "fee": 0.5}])
        assert m["priced_rows"] == 1
        assert m["bps_per_rt"] == 10.0          # 0.5/1000 = 5bps one-way, x2 for the round trip


class TestVerdictRespectsSampleSize:
    """PASS sizes real confidence and STALLED calls a shipped fix defective -- neither on n=30."""

    def test_point_estimate_on_the_bar_is_underpowered_not_pass(self) -> None:
        v, why = verdict({"maker_rate": 0.6, "maker_fills": 18, "measured_legs": 30,
                          "coverage": 0.05}, None)
        assert v == "UNDERPOWERED"
        assert "42" in why and "75" in why, "the interval must be shown, not just asserted"

    def test_a_genuinely_powered_pass_still_passes(self) -> None:
        v, _ = verdict({"maker_rate": 0.8, "maker_fills": 800, "measured_legs": 1000,
                        "coverage": 1.0}, None)
        assert v == "PASS"

    def test_a_powered_failure_still_stalls(self) -> None:
        v, why = verdict({"maker_rate": 0.1, "maker_fills": 100, "measured_legs": 1000,
                          "coverage": 1.0}, {"maker_rate": 0.1})
        assert v == "STALLED"
        assert "DEFECT" in why

    def test_only_already_flat_leaves_the_denominator(self) -> None:
        for mode in leg_modes.KNOWN_MODES:
            expected = mode not in ("already-flat", "")
            assert leg_modes.placed_order(mode) is expected

    def test_maker_is_confirmed_only(self) -> None:
        assert leg_modes.is_maker("maker") is True
        for mode in ("maker_pending", "taker", "taker_fallback", "limit_only_unfilled", "limit"):
            assert leg_modes.is_maker(mode) is False, f"{mode} is not a confirmed maker fill"

    def test_unknown_mode_fails_closed_and_never_lifts_the_share(self) -> None:
        """An unrecognised mode may push a measured share DOWN, never up over the target."""
        assert leg_modes.is_known("teleported") is False
        assert leg_modes.is_maker("teleported") is False
        assert leg_modes.placed_order("teleported") is True
        rows = [{"spot_mode": "maker", "fut_mode": "teleported", "notional": 10.0}]
        assert _forensics_share(rows) == 0.5


class TestGuardStillGuards:
    """The repair narrows what is unmeasured; it must not widen what is assumed-understood."""

    def test_unknown_leg_schema_still_refuses(self) -> None:
        m = measure([{"spot_mode": "teleported", "fut_mode": "teleported", "notional": 10.0}])
        assert m["maker_rate"] is None
        assert m["unreadable_schema"] is True

    def test_rows_with_no_liquidity_signal_at_all_still_refuse(self) -> None:
        m = measure([{"symbol": "BNBUSDT", "notional": 10.0, "fee": 0.01}])
        assert m["maker_rate"] is None
        assert m["unreadable_schema"] is True

    def test_row_per_fill_schema_is_untouched(self) -> None:
        rows = [{"maker": True, "notional": 100.0, "fee": 0.01},
                {"maker": False, "notional": 100.0, "fee": 0.05}]
        m = measure(rows)
        assert m["maker_rate"] == 0.5
        assert m["fee_concentration"] == round(0.05 / 0.06, 4), "taker still owns its fee bill"


class TestPatientPathPolicing:
    """R0481 power piece: the bar is tested on the legs the fix claims -- entries.

    "Patient on OPENS, fast on CLOSES" CROSSES close legs by design, so a pooled bar penalises
    the design on arithmetic alone: at steady state every open pairs with a close, and the pooled
    rate can straddle (or fail) the target forever while every patient order rests maker. That is
    the R0064 false-integrity-flag one level up -- an order was placed, but it was never meant to
    rest. Closes stay in the pooled `maker_rate` (two-reader agreement, trend store) and in
    `per_leg`; only the POLICED metric excludes them.
    """

    _TAPE: list[dict[str, Any]] = (
        [{"event": "open", "spot_mode": "maker", "fut_mode": "maker", "notional": 10.0}] * 6
        + [{"event": "open", "spot_mode": "taker_fallback", "fut_mode": "maker",
            "notional": 10.0}] * 6
        + [{"event": "close", "spot_mode": "taker", "fut_mode": "maker", "notional": 10.0}] * 9
    )

    def test_per_leg_decomposition_is_published(self) -> None:
        pl = measure(self._TAPE)["per_leg"]
        assert (pl["spot_entry"]["legs"], pl["spot_entry"]["maker"]) == (12, 6)
        assert (pl["spot_close"]["legs"], pl["spot_close"]["maker"]) == (9, 0)
        assert (pl["fut_entry"]["legs"], pl["fut_entry"]["maker"]) == (12, 12)
        assert (pl["fut_close"]["legs"], pl["fut_close"]["maker"]) == (9, 9)
        assert pl["spot_entry"]["ci95"][0] < 0.6 < pl["spot_entry"]["ci95"][1]

    def test_pooled_rate_is_unchanged_by_the_decomposition(self) -> None:
        """The two-reader agreement must survive: pooled counts every placed leg, closes too."""
        m = measure(self._TAPE)
        assert m["maker_rate"] == round(27 / 42, 4)
        assert m["maker_rate"] == _forensics_share(self._TAPE) or (
            round(m["maker_rate"], 3) == _forensics_share(self._TAPE))
        assert m["patient_path"] == {"legs": 24, "maker": 18, "rate": 0.75}

    def test_verdict_polices_the_patient_path_and_names_the_routing_gate(self) -> None:
        v, why = verdict(measure(self._TAPE), None)
        assert v == "UNDERPOWERED", "18/24 straddles 60% -- decomposition must not manufacture PASS"
        assert "patient-path" in why
        assert "spot-entry 6/12" in why, "the routing gate must be visible in the verdict"

    def test_design_conforming_closes_cannot_fail_the_policed_bar(self) -> None:
        """All-maker entries + all-taker closes is the DESIGN WORKING: policed PASS, not STALLED."""
        tape = ([{"event": "open", "spot_mode": "maker", "fut_mode": "maker",
                  "notional": 10.0}] * 100
                + [{"event": "close", "spot_mode": "taker", "fut_mode": "taker",
                    "notional": 10.0}] * 100)
        m = measure(tape)
        assert m["maker_rate"] == 0.5, "pooled tells the blended truth"
        v, why = verdict(m, None)
        assert v == "PASS", "200/200 patient legs maker: the fix did exactly what it claimed"
        assert "patient-path" in why

    def test_pre_decomposition_dict_shape_keeps_its_old_verdict(self) -> None:
        """A dict without patient_path (old artifact, old fixtures) polices pooled, bit-for-bit."""
        v, why = verdict({"maker_rate": 0.6, "maker_fills": 18, "measured_legs": 30,
                          "coverage": 0.05}, None)
        assert v == "UNDERPOWERED"
        assert "measured leg(s)" in why and "patient-path" not in why

    def test_unknown_event_fails_closed_into_the_policed_denominator(self) -> None:
        """A leg whose intent is unrecorded can only push the policed share DOWN, never leave."""
        tape = [{"spot_mode": "taker", "fut_mode": "taker", "notional": 10.0}] * 40
        m = measure(tape)
        assert m["patient_path"]["legs"] == 80, "no event field -> policed, not excused"
        v, _ = verdict(m, {"maker_rate": 0.242})
        assert v == "STALLED", "0/80 policed legs is a determinate failure, not a straddle"
