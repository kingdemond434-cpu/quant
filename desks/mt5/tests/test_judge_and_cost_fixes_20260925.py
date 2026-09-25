"""The certification judge and cost-model defects fixed 2026-09-25, each pinned.

1. `all_ten_pass` refused every verdict carrying the eleventh stage `swap_cost`; the trial-basis
   admissibility refused the gauntlet's own short-form stamp of the CURRENT charge.
2. The deflated-Sharpe charge is owed on the LIFETIME of judged cells, in effective tests.
3. The 3x stress arm and the forward clock are priced on the certificate's fill-hour spread.
4. Commission constants read the measured single source (2.00), never 3.50 / 2.25.
5. Swap: per side and signed, interest-mode symbols in annual percent, the broker's own triple
   day, no weekend stamps, and the rollover at 00:00 on the bar label's (broker) clock.
6. A lapsed certificate never funds a NEW sleeve.
7. CPCV carries purge/embargo, the lockbox is strict (> 0), PBO/SPA rows are calendar dates.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Costs, rollovers_between, swap_terms_from_meta  # noqa: E402

from research import gate_policy as gp  # noqa: E402


# ------------------------------------------------------------------ 1. the ten + supplementary
def _ten(**extra: dict) -> dict:
    stages = {name: {"passed": True} for name in gp.GATES}
    stages.update(extra)
    return stages


def test_the_ten_alone_still_pass() -> None:
    assert gp.all_ten_pass(_ten())


def test_a_passed_swap_cost_stage_does_not_refuse_the_verdict() -> None:
    assert gp.all_ten_pass(_ten(swap_cost={"passed": True, "measured": True}))


def test_an_unmeasured_swap_cost_is_not_a_failure() -> None:
    assert gp.all_ten_pass(_ten(swap_cost={"passed": True, "measured": False}))
    assert gp.all_ten_pass(_ten(swap_cost={"measured": False, "why": "UNMEASURED"}))


def test_a_measured_failing_swap_cost_refuses() -> None:
    assert not gp.all_ten_pass(_ten(swap_cost={"passed": False, "measured": True}))
    assert not gp.all_ten_pass(_ten(swap_cost={"passed": False, "measured": False}))


def test_an_unknown_extra_stage_still_refuses_even_when_it_says_passed() -> None:
    assert not gp.all_ten_pass(_ten(self_certified={"passed": True}))


def test_a_missing_or_failed_canonical_gate_refuses() -> None:
    stages = _ten()
    stages.pop(gp.GATES[0])
    assert not gp.all_ten_pass(stages)
    assert not gp.all_ten_pass(_ten(**{gp.GATES[1]: {"passed": False}}))
    assert not gp.all_ten_pass(None)


def test_the_gauntlets_own_short_stamp_of_the_current_charge_is_admissible() -> None:
    current = gp._SPEC_FIXED_TRIALS
    assert isinstance(current, int)
    assert gp.is_admissible_trial_count_basis(f"fixed_campaign_trials({current})")
    assert gp.is_admissible_trial_count_basis(gp.TRIAL_COUNT_BASIS)


def test_a_harder_charge_is_admissible_and_a_softer_one_is_not() -> None:
    current = gp._SPEC_FIXED_TRIALS
    assert gp.is_admissible_trial_count_basis(f"fixed_campaign_trials({current * 10})")
    assert not gp.is_admissible_trial_count_basis(f"fixed_campaign_trials({max(2, current // 2)})")
    var = gp.FIXED_VARIANCE_OF_SHARPES
    assert gp.is_admissible_trial_count_basis(
        f"effective_campaign_trials({current}) + fixed_variance_of_sharpes({var}): x")
    # A different dispersion is a different hurdle and is not provably harder.
    assert not gp.is_admissible_trial_count_basis(
        f"effective_campaign_trials({current}) + fixed_variance_of_sharpes(0.0001): x")


def test_the_fail_closed_stamp_is_judged_by_the_count_it_charged() -> None:
    current = gp._SPEC_FIXED_TRIALS
    stamp = "raw_cells_x7_fail_closed (ValueError)"
    assert gp.is_admissible_trial_count_basis(stamp, current)
    assert not gp.is_admissible_trial_count_basis(stamp, max(2, current - 1))
    assert not gp.is_admissible_trial_count_basis(stamp, None)
    assert not gp.is_admissible_trial_count_basis("anything else", 10 ** 9)


# ------------------------------------------------------------------ 2. lifetime effective trials
_SPEC = """version: test
gates:
  - name: deflated_sharpe
    params:
      trials_multiplier: 7.0
      fixed_trial_count: 109
      fixed_variance_of_sharpes: 0.014863
      trial_count_basis: "effective_campaign_trials(109) + fixed_variance_of_sharpes(0.014863): x"
      fail_closed_to: "fixed_campaign_trials(597)"
"""


def test_the_lifetime_charge_counts_every_judged_cell() -> None:
    from research import effective_trials as et
    seen = {f"SYM{i}.fam{i % 5}.p={i:016x}": "2026-09-01T00:00:00+00:00" for i in range(400)}
    life = et.lifetime_charge([], seen)
    assert life["status"] == "MEASURED"
    assert life["n_nominal"] == 400
    assert life["charged"] >= life["n_mechanisms"] == 5
    assert life["charged"] >= 2


def test_an_empty_lifetime_is_unmeasured_not_small() -> None:
    from research import effective_trials as et
    assert et.lifetime_charge([], {})["status"] == "UNMEASURED"


def test_an_authorised_act_may_raise_the_wall_and_an_unauthorised_pass_may_not(
        tmp_path: Path) -> None:
    from research import effective_trials as et
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    res = et.apply_to_spec(3200, variance=0.014863, path=spec)
    assert res["status"] == "REFUSED_UNAUTHORISED"
    assert et.spec_fixed_trial_count(spec) == 109
    res = et.apply_to_spec(3200, variance=0.014863, path=spec, authorised=True)
    assert res["status"] == "APPLIED"
    assert et.spec_fixed_trial_count(spec) == 3200
    text = spec.read_text("utf-8")
    assert "effective_campaign_trials(3200)" in text
    # Fail-closed never points at a softer wall than the one in force.
    assert "fail_closed_to: \"fixed_campaign_trials(3200)" in text


def test_the_build_proposes_the_lifetime_charge(tmp_path: Path) -> None:
    from research import effective_trials as et
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps({f"S{i}.carry.p={i:016x}": "t" for i in range(300)}), "utf-8")
    doc = et.build(docket=tmp_path / "none.json", spec=spec, seen=seen, apply=True)
    cam = doc["campaign"]
    assert cam["lifetime"]["status"] == "MEASURED"
    assert cam["charged"] == cam["lifetime"]["charged"]
    assert et.spec_fixed_trial_count(spec) == 109          # the hourly pass never writes


def test_an_unmeasurable_lifetime_proposes_the_harder_standing_wall(tmp_path: Path) -> None:
    from research import effective_trials as et
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    doc = et.build(docket=tmp_path / "none.json", spec=spec, seen=tmp_path / "absent.json",
                   apply=False)
    assert doc["campaign"]["charged"] == max(et.NOMINAL_CAMPAIGN_TRIALS, 109)


# ------------------------------------------------------------------ 3. one fill-hour constructor
def _meta() -> dict:
    return {"EURZAR": {"contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 0.05,
                       "median_spread_pts": 310.0}}


def test_the_stress_arm_is_three_times_the_same_fill_hour_spread() -> None:
    from scripts import external_gauntlet as eg
    cell = {"sym": "EURZAR", "_spread_pts": 1918.0, "_fill_hour": 1}
    base = Costs.from_symbol(_meta()["EURZAR"], spread_pts=1918.0)
    x3 = eg.stress_costs_for(cell, _meta(), mult=3.0)
    assert x3.spread_per_lot == pytest.approx(base.spread_per_lot * 3.0)
    assert x3.spread_per_lot > base.spread_per_lot
    # No measured fill hour: both arms on the pooled median, alike.
    pooled = eg.stress_costs_for({"sym": "EURZAR", "_spread_pts": None}, _meta(), mult=3.0)
    assert pooled.spread_per_lot == pytest.approx(
        Costs.from_symbol(_meta()["EURZAR"], mult=3.0).spread_per_lot)


def test_the_forward_clock_prices_at_the_certificates_fill_hour(monkeypatch) -> None:
    from mt5desk.engine import Signal

    from research import cell_costs, shadow_forward
    surface = {"symbols": {"EURZAR": {"hours": {"1": {"status": "MEASURED", "p50": 1918.0}}}}}
    monkeypatch.setattr(cell_costs, "load_surface", lambda *a, **k: surface)
    sigs = [Signal(time=pd.Timestamp("2026-09-01 00:00"), side=1, stop=1.0, target=2.0,
                   ttl_bars=5, tag="t", wait_bars=1)]
    fwd = shadow_forward.per_symbol_costs(_meta(), "EURZAR", sigs=sigs, timeframe="H1")
    cert, basis, spread = cell_costs.fill_hour_costs(_meta()["EURZAR"], "EURZAR", hour=1,
                                                     surface=surface)
    assert basis == "fill_hour_01_spread" and spread == 1918.0
    assert fwd == cert
    assert fwd.commission_per_lot == pytest.approx(2.00)


def test_a_frozen_commission_never_overrides_the_measured_one(monkeypatch) -> None:
    import sleeve_registry

    from research import shadow_forward
    monkeypatch.setattr(sleeve_registry, "frozen_cost_fields", lambda _k: {
        "spread_per_lot": 912.0, "commission_per_lot": 3.5, "contract_oz": 100000.0,
        "quote_per_account": 18.5})
    cost = shadow_forward.frozen_costs("EURZAR.overnight_gap_decay.asia")
    assert cost is not None and cost.commission_per_lot == pytest.approx(2.00)
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert "frozen_cost_fields(key)\n                if _ff:" not in src


# ------------------------------------------------------------------ 4. commission single source
_COMMISSION_FILES = (
    "research/mech_split.py", "research/fragility.py", "research/placebo_test.py",
    "research/trade_path.py", "research/rv_triangle.py", "research/validate_fusion.py",
    "research/swap_exposure.py", "research/run_hunt7.py", "research/run_hunt8.py",
    "research/run_hunt13.py", "research/run_hunt21.py", "side_channels/ug_remote.py",
    "side_channels/sharpe.py", "side_channels/combined.py",
)


@pytest.mark.parametrize("rel", _COMMISSION_FILES)
def test_no_stale_commission_literal_is_charged(rel: str) -> None:
    tree = ast.parse((DESK / rel).read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "commission_per_lot":
            assert not isinstance(node.value, ast.Constant), f"{rel}: literal commission"
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and node.value.value in (3.5, 2.25):
            names = [getattr(t, "id", "") for t in node.targets]
            assert not any("COMMISSION" in n for n in names), f"{rel}: {names}"


def test_the_counterfactual_world_charges_the_measured_commission() -> None:
    from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE
    from libs.research import counterfactual_world as cw
    assert cw.COMMISSION_PER_LOT == pytest.approx(COMMISSION_PER_LOT_PER_SIDE) == 2.00


# ------------------------------------------------------------------ 5. swap
def test_points_mode_credits_the_positive_side_and_charges_the_negative() -> None:
    meta = {"contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 1.0,
            "swap_long": -324.72, "swap_short": 39.11, "asset_class": "Forex Exotics"}
    c = Costs.from_symbol(meta)
    assert c.swap_mode == 1
    assert c.night_cost(+1, 20.0) == pytest.approx(324.72 * 0.00001 * 100000.0)
    assert c.night_cost(-1, 20.0) == pytest.approx(-39.11 * 0.00001 * 100000.0)   # a CREDIT
    # The legacy side-blind field is unchanged for its readers.
    assert c.swap_per_lot_per_night == pytest.approx(324.72)


def test_interest_mode_is_annual_percent_of_notional_on_a_360_day_year() -> None:
    meta = {"contract_size": 1.0, "tick_size": 0.01, "tick_value": 0.0086,
            "swap_long": -5.92, "swap_short": 1.56, "asset_class": "Indices"}
    c = Costs.from_symbol(meta)
    assert c.swap_mode == 5
    price = 5000.0
    assert c.night_cost(+1, price) == pytest.approx(5.92 / 100 / 360 * price * 1.0)
    assert c.night_cost(-1, price) == pytest.approx(-1.56 / 100 / 360 * price * 1.0)


def test_an_explicit_swap_mode_wins_over_the_asset_class() -> None:
    terms = swap_terms_from_meta({"swap_mode": 1, "asset_class": "Equities", "swap_long": -2.0,
                                  "swap_short": 1.0, "tick_size": 0.01, "contract_size": 1.0})
    assert terms["swap_mode"] == 1 and "swap_long_pct" not in terms


def test_an_unclassified_row_keeps_the_legacy_worse_side_charge() -> None:
    meta = {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
            "median_spread_pts": 29.0, "swap_long": -61.76, "swap_short": 29.45}
    c = Costs.from_symbol(meta)
    assert c.swap_mode is None
    assert c.night_cost(-1, 3300.0) == pytest.approx(61.76)          # no credit is guessed


def test_disabled_swap_charges_nothing() -> None:
    c = Costs.from_symbol({"swap_mode": 0, "swap_long": -9.0, "swap_short": -9.0,
                           "tick_size": 0.01, "contract_size": 1.0})
    assert not c.charges_financing()


def test_the_rollover_is_midnight_on_the_bar_labels_clock() -> None:
    # Bars are labelled in broker server time; the broker rolls at 00:00 on that clock.
    assert rollovers_between(pd.Timestamp("2026-09-14 21:30"),
                             pd.Timestamp("2026-09-14 23:30")) == 0.0
    assert rollovers_between(pd.Timestamp("2026-09-14 23:00"),
                             pd.Timestamp("2026-09-15 01:00")) == 1.0
    # Half-open: a midnight exactly at entry is not charged, exactly at exit is.
    assert rollovers_between(pd.Timestamp("2026-09-15 00:00"),
                             pd.Timestamp("2026-09-15 20:00")) == 0.0
    assert rollovers_between(pd.Timestamp("2026-09-14 20:00"),
                             pd.Timestamp("2026-09-15 00:00")) == 1.0
    # A tz-aware label is read on its own wall clock, not converted.
    aware = pd.Timestamp("2026-09-14 23:00", tz="Etc/GMT-3")
    assert rollovers_between(aware, aware + pd.Timedelta(hours=2)) == 1.0


def test_a_week_is_seven_nights_and_the_weekend_stamps_are_not_charged() -> None:
    mon = pd.Timestamp("2026-09-14 10:00")
    assert mon.weekday() == 0
    assert rollovers_between(mon, mon + pd.Timedelta(days=7)) == 7.0
    # Friday afternoon to Monday morning crosses only the Friday night.
    assert rollovers_between(pd.Timestamp("2026-09-18 15:00"),
                             pd.Timestamp("2026-09-21 09:00")) == 1.0


def test_the_symbols_own_triple_day_is_used() -> None:
    wed_night = (pd.Timestamp("2026-09-16 23:00"), pd.Timestamp("2026-09-17 01:00"))
    fri_night = (pd.Timestamp("2026-09-18 23:00"), pd.Timestamp("2026-09-19 01:00"))
    assert rollovers_between(*wed_night) == 3.0
    assert rollovers_between(*fri_night) == 1.0
    assert rollovers_between(*wed_night, triple_weekday=4) == 1.0
    assert rollovers_between(*fri_night, triple_weekday=4) == 3.0
    # MT5's swap_rollover3days is Sunday-based: 5 = Friday.
    assert swap_terms_from_meta({"swap_rollover3days": 5})["swap_triple_weekday"] == 4


def test_financing_for_uses_side_price_and_triple_day() -> None:
    meta = {"contract_size": 1.0, "tick_size": 0.01, "swap_long": -3.6, "swap_short": 3.6,
            "asset_class": "Equities", "swap_rollover3days": 5}
    c = Costs.from_symbol(meta)
    t0, t1 = pd.Timestamp("2026-09-18 15:00"), pd.Timestamp("2026-09-19 01:00")   # Fri night
    per_night = 3.6 / 100 / 360 * 100.0
    assert c.financing_for(+1, 100.0, t0, t1) == pytest.approx(3 * per_night)
    assert c.financing_for(-1, 100.0, t0, t1) == pytest.approx(-3 * per_night)


def test_the_registry_writers_record_the_swap_unit() -> None:
    for rel in ("research/expand_universe.py", "research/fetch_universe.py"):
        src = (DESK / rel).read_text("utf-8")
        assert "swap_mode" in src and "swap_rollover3days" in src, rel


# ------------------------------------------------------------------ 6. lapsed certificates
def test_a_lapsed_certificate_is_detected_and_the_universe_flag_is_not_compared() -> None:
    from research import promoter
    auth = {("EURUSD", "asia", None, "carry", True)}
    assert not promoter.certificate_lapsed(("EURUSD", "asia", None, "carry", False), auth)
    assert promoter.certificate_lapsed(("EURUSD", "london", None, "carry", False), auth)
    assert promoter.certificate_lapsed(("EURUSD", "asia", None, "carry", False), set())


def test_a_lapsed_certificate_holds_a_generic_candidate(monkeypatch) -> None:
    from research import promoter
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {"K": {
        "symbol": "EURUSD", "selector": "asia", "family": "carry", "is_universe": True}})
    monkeypatch.setattr(promoter, "regrade_block", lambda *_a: None)
    monkeypatch.setattr(promoter, "blind_review_veto", lambda *_a: None)
    sleeves: list[dict] = []
    q = {"K": {"status": "PROMOTION_CANDIDATE", "exp_r": 0.2, "n": 60}}
    promoter.promote_generic(sleeves, q, set(), {("GBPUSD", "asia", None, "carry", True)},
                             regrade={}, view={})
    assert sleeves == []
    assert q["K"]["status"] == "PROMOTION_CANDIDATE"          # held, not re-statused
    assert "certificate_lapsed_reason" in q["K"]


# ------------------------------------------------------------------ 7. CPCV / lockbox / calendar
def test_cpcv_carries_purge_and_embargo_and_the_lockbox_is_strict() -> None:
    from scripts import external_gauntlet as eg
    assert eg.CPCV_PURGE_DAYS >= 1 and eg.CPCV_EMBARGO > 0
    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "purge=CPCV_PURGE_DAYS, embargo=CPCV_EMBARGO" in src
    assert '"passed": bool(wf_oos > 0.0)' in src
    assert "bool(wf_oos >= 0.0)" not in src


def test_program_level_rows_are_calendar_dates_not_positions() -> None:
    from scripts import external_gauntlet as eg
    days = pd.bdate_range("2025-01-01", periods=120)
    a = pd.Series(1.0, index=days)                                   # trades every day
    b = pd.Series(2.0, index=days[::2])                              # every other day
    m = eg.calendar_matrix([a, b])
    # The window every cell was live in: b's last trade is day 118, so 119 common dates.
    assert m.shape == (119, 2)
    # The same row is the same date: b is 0 on the days it did not trade.
    assert np.allclose(m[:, 0], 1.0)
    assert np.allclose(m[::2, 1], 2.0) and np.allclose(m[1::2, 1], 0.0)


def test_a_short_overlap_widens_to_the_union_still_date_aligned() -> None:
    from scripts import external_gauntlet as eg
    a = pd.Series(1.0, index=pd.bdate_range("2024-01-01", periods=100))
    b = pd.Series(1.0, index=pd.bdate_range("2024-05-01", periods=100))
    m = eg.calendar_matrix([a, b])
    assert m.shape[0] == len(a.index.union(b.index))
