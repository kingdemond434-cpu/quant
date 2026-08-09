"""Tests for the VENUE SUBSIDY / REBATE RENT Stage-A screen (census gap #4).

WHAT THESE TESTS ARE FOR. This class has one way to go badly wrong and the desk has already paid
for it in cash: report a GROSS rebate as though it were income, when the trades that earned it
would not otherwise have happened. That is the 2026-07 fee fire's own arithmetic ($1,750 of
commission against ~$126 of logged round-trips). So the properties pinned here are refusals:

  NO GROSS-ONLY       when the round-trip cost of the trades required to earn the rebate is not
                      measured, the capture must REFUSE -- and the gross figure must be SUPPRESSED
                      from the artifact entirely, not printed beside a caveat. A number in an
                      artifact gets quoted without its caveat.
  EFFECTIVE DATES     a tier may value a fill only where its published effective window covers the
                      fill's own timestamp. An undated sheet prices history at today's rates and
                      the error is invisible in the output, so it must disqualify rather than
                      default.
  R0143               a rebate tier the desk does not already reach on its OWN observed volume is
                      a KILL (NOT-EARNABLE-AT-CURRENT-SIZE) and must never become an argument for
                      more size or leverage.
  UNREACHABLE VENUES  a venue that will not serve its schedule yields a status artifact naming the
                      status code, not a silent omission and not an assumed rate.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from scripts.screen_venue_subsidy import (
    build_report,
    load_fills,
    load_schedules,
    pre_registration,
    probe_venues,
)

from libs.research.venue_subsidy import (
    MIN_TIER_DAYS,
    NOT_READABLE,
    REFUSED,
    FeeSchedule,
    FeeTier,
    Fill,
    attributed_counterfactual,
    daily_grid,
    net_execution_bps_series,
    net_rebate_capture,
    tier_reachability,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _tier(*, maker_bps: float = -0.5, min_vol: float = 1_000.0,
          dated: bool = True, tier: str = "vip3") -> FeeTier:
    return FeeTier(
        venue="testvenue", tier=tier, maker_bps=maker_bps, taker_bps=4.0,
        min_30d_volume_usd=min_vol,
        effective_from=(T0 - timedelta(days=365)) if dated else None,
        source_url="https://example.test/fees", retrieved_utc=T0.isoformat())


def _fills(days: int = 40, notional: float = 500.0, *, fee: float | None = -0.02,
           counterfactual: str = "UNATTRIBUTED") -> list[Fill]:
    return [Fill(ts=T0 + timedelta(days=i), venue="testvenue", symbol="BTCUSDT",
                 notional_usd=notional, is_maker=True, fee_usd=fee,
                 counterfactual=counterfactual, slip_bps=0.5)
            for i in range(days)]


# --------------------------------------------------------------------------- the core refusal


def test_capture_refuses_when_the_roundtrip_cost_is_unmeasured() -> None:
    """THE HEADLINE PROPERTY. A rebate without its cost side is not a partial answer."""
    sched = FeeSchedule("testvenue", (_tier(),))
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=sched,
                             roundtrip_cost_usd=None)
    assert cap.net_usd is None
    assert cap.as_dict()["verdict"] == REFUSED
    assert REFUSED in cap.headline()
    assert "round-trip cost" in " ".join(cap.missing)


def test_a_refused_capture_suppresses_the_gross_figure_entirely() -> None:
    """Not "gross, with a caveat" -- gross MUST NOT appear. A number outlives its caveat."""
    sched = FeeSchedule("testvenue", (_tier(),))
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=sched,
                             roundtrip_cost_usd=None)
    blob = cap.as_dict()
    assert blob["gross_rebate_usd"] == (
        "SUPPRESSED -- a gross rebate is not reported without its cost side")
    assert not isinstance(blob["gross_rebate_usd"], (int, float))
    # ...and no gross number leaks through the headline either.
    assert "$" not in cap.headline().split(REFUSED)[-1].split("missing")[0]


def test_screen_report_never_claims_a_gross_number() -> None:
    report = build_report(
        captures=[net_rebate_capture(venue="testvenue", fills=_fills(),
                                     schedule=FeeSchedule("testvenue", (_tier(),)),
                                     roundtrip_cost_usd=None).as_dict()],
        rows=[], probes=[], missing=[], provenance={})
    assert report["gross_reported"] is False
    assert report["net_testable"] is False
    assert report["status"] == REFUSED
    assert report["survivors"] == [] and report["graveyard"] == []
    assert "NOTHING is graveyarded" in report["power_headline"]
    blob = json.dumps(report)
    assert "SUPPRESSED" in blob


def test_net_is_measured_only_when_both_sides_are() -> None:
    sched = FeeSchedule("testvenue", (_tier(),))
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=sched,
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is not None
    blob = cap.as_dict()
    assert blob["verdict"] == "NET-MEASURED"
    assert isinstance(blob["gross_rebate_usd"], float)
    # 40 maker fills x $500 x 0.5 bps = $1.00 gross, minus the $1.00 round-trip cost.
    assert cap.gross_rebate_usd == pytest.approx(1.0)
    assert cap.net_usd == pytest.approx(0.0, abs=1e-9)


def test_incumbent_counterfactual_is_never_inferred_from_an_unattributed_tape() -> None:
    """One unattributed fill drags the whole set to REBATE_SEEKING -- the conservative branch."""
    mixed = (_fills(days=5, counterfactual="INCUMBENT")
             + _fills(days=1, counterfactual="UNATTRIBUTED"))
    assert attributed_counterfactual(mixed) == "REBATE_SEEKING"
    assert attributed_counterfactual(_fills(days=5, counterfactual="INCUMBENT")) == "INCUMBENT"


def test_incumbent_flow_pays_zero_incremental_cost_and_is_measurable_without_one() -> None:
    """The one branch where a net exists with no cost supplied -- because the cost is zero BY the
    counterfactual, not by omission. It requires every fill to be individually attributed."""
    sched = FeeSchedule("testvenue", (_tier(),))
    cap = net_rebate_capture(venue="testvenue",
                             fills=_fills(counterfactual="INCUMBENT"), schedule=sched,
                             roundtrip_cost_usd=None)
    assert cap.counterfactual == "INCUMBENT"
    assert cap.incremental_roundtrip_cost_usd == 0.0
    assert cap.net_usd == pytest.approx(cap.gross_rebate_usd)


# --------------------------------------------------------------------------- effective dates


def test_an_undated_schedule_cannot_value_a_historical_fill() -> None:
    undated = FeeTier(venue="testvenue", tier="vip3", maker_bps=-0.5, taker_bps=4.0,
                      min_30d_volume_usd=1_000.0, effective_from=None,
                      source_url="https://example.test/fees", retrieved_utc=T0.isoformat())
    sched = FeeSchedule("testvenue", (undated,))
    assert sched.dated_fraction() == 0.0
    assert sched.tier_at(1e9, T0) is None
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=sched,
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is None
    assert any("EFFECTIVE DATES" in m for m in cap.missing)


def test_tier_outside_its_effective_window_does_not_apply() -> None:
    t = FeeTier(venue="v", tier="vip3", maker_bps=-0.5, taker_bps=4.0, min_30d_volume_usd=0.0,
                effective_from=T0, effective_to=T0 + timedelta(days=10),
                source_url="u", retrieved_utc="r")
    assert t.covers(T0 + timedelta(days=5))
    assert not t.covers(T0 - timedelta(days=1))
    assert not t.covers(T0 + timedelta(days=10))          # half-open: effective_to is exclusive
    with pytest.raises(ValueError, match="timezone-aware"):
        t.covers(datetime(2026, 1, 5))


def test_naive_effective_dates_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FeeTier(venue="v", tier="t", maker_bps=-1.0, taker_bps=4.0, min_30d_volume_usd=0.0,
                effective_from=datetime(2026, 1, 1))


# --------------------------------------------------------------------------- R0143


def test_an_unreachable_tier_is_a_kill_and_not_a_size_argument() -> None:
    sched = FeeSchedule("testvenue", (_tier(min_vol=1e12),))
    reach = tier_reachability(sched, _fills())
    assert reach.verdict == "NOT-EARNABLE-AT-CURRENT-SIZE"
    assert reach.days_at_or_above == 0
    blob = reach.as_dict()
    assert "KILL" in blob["r0143"]
    assert "never a reason to add size" in blob["r0143"]
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=sched,
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is None
    assert any("R0143" in m for m in cap.missing)


def test_a_tier_reached_for_only_a_few_days_is_not_reached() -> None:
    """A spike above a 30-day-volume threshold is not a tier; the rebate accrues while it holds."""
    sched = FeeSchedule("testvenue", (_tier(min_vol=2_000.0),))
    short = _fills(days=MIN_TIER_DAYS - 1, notional=5_000.0)
    assert tier_reachability(sched, short).verdict == "NOT-EARNABLE-AT-CURRENT-SIZE"
    long = _fills(days=MIN_TIER_DAYS + 5, notional=5_000.0)
    assert tier_reachability(sched, long).verdict == "REACHED"


def test_a_venue_that_charges_the_maker_has_no_rent_to_capture() -> None:
    charging = FeeSchedule("testvenue", (_tier(maker_bps=1.5),))
    assert charging.best_rebate_tier() is None
    assert tier_reachability(charging, _fills()).verdict == "NO-REBATE-TIER"
    cap = net_rebate_capture(venue="testvenue", fills=_fills(), schedule=charging,
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is None
    assert any("no maker-REBATE tier" in m or "REBATE tier" in m for m in cap.missing)


def test_the_preregistration_carries_the_hazard_and_the_rail() -> None:
    pre = pre_registration()
    assert "WOULD HAVE TRADED ANYWAY" in pre["honest_hazard"]
    assert "never gross" in pre["honest_hazard"]
    assert "SIZE lever" in pre["r0143"]
    assert pre["order_of_operations"].startswith("the NET ACCOUNTING GATE runs FIRST")
    assert pre["alignment"]["excludes_current_period"] is True


# --------------------------------------------------------------------------- missing fee data


def test_a_fee_that_was_not_recorded_is_not_a_fee_of_zero() -> None:
    sched = FeeSchedule("testvenue", (_tier(),))
    cap = net_rebate_capture(venue="testvenue", fills=_fills(fee=None), schedule=sched,
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is None
    assert any("venue-charged fee" in m for m in cap.missing)


def test_net_execution_series_is_nan_not_zero_where_the_fee_is_unreadable() -> None:
    fills = _fills(days=3, fee=None)
    days = daily_grid(fills)
    out = net_execution_bps_series(fills, days)
    assert np.isnan(out).all()
    priced = _fills(days=3, fee=0.05)
    out2 = net_execution_bps_series(priced, daily_grid(priced))
    assert np.isfinite(out2).all()
    # POSITIVE means the desk was PAID: a paid rebate is a negative fee under the executor's
    # "positive bps means we paid" convention, so the sign flips exactly once.
    rebated = _fills(days=3, fee=-0.05)
    out3 = net_execution_bps_series(rebated, daily_grid(rebated))
    assert (out3 > out2).all()


def test_no_fills_refuses_and_names_the_missing_evidence() -> None:
    cap = net_rebate_capture(venue="testvenue", fills=None,
                             schedule=FeeSchedule("testvenue", (_tier(),)),
                             roundtrip_cost_usd=1.0)
    assert cap.net_usd is None
    assert any("own fill records" in m for m in cap.missing)
    assert cap.as_dict()["net_usd"] == NOT_READABLE


# --------------------------------------------------------------------------- unreachable venues


def test_unprobed_venues_are_recorded_rather_than_omitted() -> None:
    probes = probe_venues(enabled=False)
    assert probes and all(p["status"] == "NOT-PROBED" for p in probes)
    assert {p["venue"] for p in probes} >= {"deribit", "binance", "bybit"}


def test_unreachable_venues_yield_a_status_artifact_naming_the_status_code() -> None:
    probes = [
        {"venue": "binance", "url": "https://api.binance.com/...", "status": "HTTP-451",
         "publishes_maker_commission": False},
        {"venue": "bybit", "url": "https://api.bybit.com/...", "status": "HTTP-403",
         "publishes_maker_commission": False},
    ]
    report = build_report(captures=[], rows=[], probes=probes,
                          missing=["data/venue_fee_schedules.json absent"], provenance={})
    assert report["status"] == "NOT-READABLE-HERE"
    assert report["net_testable"] is False
    assert [p["status"] for p in report["venue_probes"]] == ["HTTP-451", "HTTP-403"]
    assert report["missing_inputs"] == ["data/venue_fee_schedules.json absent"]
    assert report["survivors"] == [] and report["graveyard"] == []
    json.dumps(report)                                   # must be serialisable as an artifact


def test_absent_schedule_file_is_a_named_problem_not_an_empty_success(tmp_path) -> None:
    sched, problems = load_schedules(tmp_path / "nope.json")
    assert sched == {}
    assert problems and "effective dates" in problems[0]


def test_a_schedule_row_without_provenance_is_rejected(tmp_path) -> None:
    p = tmp_path / "fees.json"
    p.write_text(json.dumps({"venueA": [
        {"tier": "vip3", "maker_bps": -0.5, "taker_bps": 4.0, "min_30d_volume_usd": 1000,
         "effective_from": T0.isoformat()},
    ]}), "utf-8")
    sched, problems = load_schedules(p)
    assert sched == {}
    assert any("provenance" in x for x in problems)


def test_absent_fill_tape_names_both_paths(tmp_path, monkeypatch) -> None:
    import scripts.screen_venue_subsidy as mod
    monkeypatch.setattr(mod, "TAPE", tmp_path / "tape.jsonl")
    monkeypatch.setattr(mod, "ROLLING", tmp_path / "rolling.json")
    fills, problems, prov = load_fills(venue_default="binance", attribute_incumbent=False)
    assert fills == []
    assert any("tape.jsonl" in x for x in problems)
    assert any("rolling.json" in x for x in problems)
    assert prov["tape_rows"] == 0


def test_fills_are_read_per_leg_and_default_to_unattributed(tmp_path, monkeypatch) -> None:
    """A cash-carry pair can rest maker on one leg and cross taker on the other; collapsing the
    pair would let the maker leg launder the taker one."""
    import scripts.screen_venue_subsidy as mod
    tape = tmp_path / "tape.jsonl"
    tape.write_text(json.dumps({
        "event": "open", "symbol": "BTCUSDT", "notional": 1000.0,
        "opened": T0.isoformat(), "modes": {"spot": "maker", "fut": "taker"},
        "spot_slip_bps": 0.4, "fut_slip_bps": 2.0}) + "\n", "utf-8")
    monkeypatch.setattr(mod, "TAPE", tape)
    monkeypatch.setattr(mod, "ROLLING", tmp_path / "rolling.json")
    fills, problems, _ = load_fills(venue_default="binance", attribute_incumbent=False)
    assert len(fills) == 2
    assert {f.is_maker for f in fills} == {True, False}
    assert all(f.counterfactual == "UNATTRIBUTED" for f in fills)
    assert all(f.fee_usd is None for f in fills)
    assert any("venue-charged fee" in x for x in problems)
    assert any("--venue default" in x or "venue field" in x for x in problems)
