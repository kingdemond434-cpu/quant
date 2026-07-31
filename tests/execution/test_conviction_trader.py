"""R0125 conviction sleeve -- aggression uncapped, ruin capped, and paper-only.

The structural-stop tests below are the principal's instruction expressed as arithmetic:
*"use calculated SL to prevent it and put trades until the trend and swing hits, minimising
downside and maximising upside."* Downside minimised = open risk falls at every stage of the
ladder and the trail never widens it. Upside maximised = exposure rises and there is no target.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_conviction_trader import (_BRIEF, MAX_LEVERAGE, MAX_PEAK_STRESS_LOSS,
                                           MAX_RISK_PER_TRADE, MAX_STOP_PCT, MAX_STRESS_LOSS,
                                           MIN_STOP_PCT, SLIP_STRESS_PCT, adverse_excursion,
                                           derive_stop_pct, kelly_leverage, management_plan,
                                           noise_floor, record, sleeve_drawdown,
                                           slip_leverage_cap, validate)

_ENTRY = 4107.4                                   # the screenshot's XAUUSD short, as PAXGUSDT


def _t(**kw):
    base = {"action": "TRADE", "symbol": "PAXGUSDT", "direction": "SHORT", "probability": 0.63,
            "entry_ref": _ENTRY, "invalidation": _ENTRY * 1.02,     # 2% structural stop
            "structure": "the prior-session swing high that capped the last two attempts",
            "expected_move_pct": 4.0, "horizon_hours": 12,
            "driver": "DXY strength and overbought gold into a known resistance shelf",
            "falsifier": "gold breaks and holds above the shelf on rising volume"}
    base.update(kw)
    return base


def test_a_real_edge_produces_real_leverage():
    # The whole point: an honest 60%+ call with a tight stop is meant to be BIG (the screenshot's
    # ~8x), not shrunk to nothing.
    s = kelly_leverage(0.63, 4.0 / 2.0, 2.0)
    assert s["leverage"] > 2.0                     # genuinely aggressive
    assert s["capped_by"] in ("kelly", "max_leverage", "max_risk")


def test_leverage_is_hard_capped():
    # Aggression uncapped, RUIN capped -- a wildly confident call cannot exceed the ceiling.
    s = kelly_leverage(0.90, 10.0 / 0.5, 0.5)
    assert s["leverage"] <= MAX_LEVERAGE
    assert s["risk_fraction"] <= MAX_RISK_PER_TRADE


def test_no_edge_means_no_size():
    s = kelly_leverage(0.50, 1.0, 2.0)             # coin flip, no edge
    assert s["leverage"] == 0.0 and s["capped_by"] == "no-edge"


def test_reported_risk_is_what_the_stop_actually_costs_not_what_kelly_asked_for():
    # When a ceiling binds, Kelly's REQUEST and the position's actual exposure diverge. The
    # management ladder is denominated in this number, so publishing the request would overstate
    # downside at every stage of it.
    s = kelly_leverage(0.63, 4.0 / 0.5, 0.5)
    assert s["kelly_risk_fraction"] == MAX_RISK_PER_TRADE
    assert s["risk_fraction"] < s["kelly_risk_fraction"]
    assert abs(s["risk_fraction"] - s["leverage"] * 0.005) < 1e-6
    # ...and when nothing binds, request and realisation agree.
    s = kelly_leverage(0.63, 4.0 / 4.0, 4.0)
    assert abs(s["risk_fraction"] - s["kelly_risk_fraction"]) < 1e-6


def test_no_size_is_left_on_the_table_at_any_stop_distance():
    # ANTI-TIMIDITY PIN (L1.28). Size must always sit exactly ON the binding constraint -- never
    # below it, and the constraint must be one that has a reason. A flat 10x cap failed this: at a
    # 0.9% stop it deployed 9% of a 20% budget for no reason beyond the roundness of the number.
    for stop in (0.5, 0.9, 1.5, 2.0, 4.0, 10.0):
        s = kelly_leverage(0.63, 4.0 / stop, stop)
        binding = min(MAX_RISK_PER_TRADE / (stop / 100.0),   # kelly / per-trade risk budget
                      slip_leverage_cap(stop),               # gap stress
                      MAX_LEVERAGE,                          # absolute notional
                      kelly_leverage(0.63, 4.0 / stop, stop)["kelly_risk_fraction"] / (stop / 100.0))
        assert abs(s["leverage"] - round(binding, 2)) < 0.02, f"size left unused at {stop}%"
        assert s["capped_by"] != ""


def test_the_tight_structural_stop_beats_the_old_flat_ceiling():
    # REGRESSION PIN for the actual defect: under the old flat 10x cap a 0.9% structural stop
    # deployed 9% of the risk budget while a lazy 2% stop deployed the full 20%. The gap-stress
    # bound is a real constraint at that distance -- but it must bind at a level well above where
    # the arbitrary one did.
    tight = kelly_leverage(0.63, 4.0 / 0.9, 0.9)
    assert "gap_stress" in tight["capped_by"]       # bound by a reason, not a round number
    assert tight["risk_fraction"] > 10.0 * 0.009 * 1.5     # comfortably beats the old 9%
    assert tight["leverage"] > 10.0


def test_the_only_notional_ceiling_is_the_gap_stress():
    # The stop being hit is priced. A cascade printing THROUGH it is not, and that loss scales
    # with notional rather than stop distance -- so it, not a round number, sets the ceiling.
    for stop in (0.5, 0.9, 2.0, 4.0):
        cap = slip_leverage_cap(stop)
        assert abs(cap * (stop + SLIP_STRESS_PCT) / 100.0 - MAX_STRESS_LOSS) < 1e-9
        s = kelly_leverage(0.63, 4.0 / stop, stop)
        assert s["leverage"] <= cap + 1e-9 and s["leverage"] <= MAX_LEVERAGE


def test_the_stop_can_never_sit_past_liquidation():
    # leverage * stop == risk_fraction <= 20% by construction, while liquidation is ~1/leverage:
    # the stop is therefore never more than a fifth of the way to liquidation, at any input.
    for prob in (0.55, 0.63, 0.75, 0.90):
        for stop in (0.5, 1.0, 2.0, 5.0, 15.0):
            s = kelly_leverage(prob, 4.0 / stop, stop)
            assert s["leverage"] * (stop / 100.0) <= MAX_RISK_PER_TRADE + 1e-9


# --------------------------------------------------------------------- calculated stop (the ask)

def test_tighter_structural_stop_buys_more_size_at_the_same_edge():
    # WHY THE LEVEL MATTERS: same conviction, same risk budget -- the stop placement alone decides
    # how big the trade is. A lazy 4% stop throws away 4x the size a real 1% swing would carry.
    lazy = kelly_leverage(0.63, 4.0 / 4.0, 4.0)["leverage"]
    tight = kelly_leverage(0.63, 4.0 / 1.0, 1.0)["leverage"]
    assert tight > lazy * 2                        # not marginal -- multiples


def test_stop_distance_is_derived_from_the_level_not_asserted():
    pct, why = derive_stop_pct(100.0, 98.0, "LONG")
    assert why == "" and abs(pct - 2.0) < 1e-9
    pct, why = derive_stop_pct(100.0, 102.0, "SHORT")
    assert why == "" and abs(pct - 2.0) < 1e-9


def test_invalidation_on_the_wrong_side_is_refused():
    # A level above entry on a LONG is a target wearing a stop's name.
    ok, why = validate(_t(direction="LONG", invalidation=_ENTRY * 1.02))
    assert not ok and "target, not a stop" in why
    ok, why = validate(_t(direction="SHORT", invalidation=_ENTRY * 0.98))
    assert not ok and "target, not a stop" in why


def test_an_arbitrary_stop_with_no_named_structure_is_refused():
    ok, why = validate(_t(structure="2 percent, feels about right"))
    assert not ok and "NAMED market structure" in why


def test_a_decorated_stop_pct_that_contradicts_the_level_is_refused():
    # Model names a 2% swing then writes stop_pct 5 -> it did not reason about the level.
    ok, why = validate(_t(stop_pct=5.0))
    assert not ok and "decorated, not calculated" in why
    assert validate(_t(stop_pct=2.0))[0]           # a consistent restatement is fine


def test_a_stop_so_wide_it_is_not_a_stop_is_refused():
    # The rail the manual account lacked (L1.23).
    ok, why = validate(_t(invalidation=_ENTRY * 2.0))
    assert not ok and "structural stop" in why


def test_negative_ev_reward_risk_refused():
    ok, why = validate(_t(expected_move_pct=1.0))  # risking 2 to make 1
    assert not ok and "reward:risk" in why


def test_overconfidence_bound():
    ok, why = validate(_t(probability=0.97))
    assert not ok and "probability" in why


# ------------------------------------------- ride the trend: downside falls while upside compounds

def _plan(direction="SHORT"):
    inval = _ENTRY * (1.02 if direction == "SHORT" else 0.98)
    s = kelly_leverage(0.63, 2.0, 2.0)
    return management_plan(_ENTRY, inval, direction,
                           risk_fraction=s["risk_fraction"], leverage=s["leverage"])


def test_open_risk_never_widens_and_falls_at_every_stage():
    # "MINIMISING DOWNSIDE": the trail can only ever reduce what is at risk, never restore it.
    for d in ("LONG", "SHORT"):
        risks = [s["open_risk_frac"] for s in _plan(d)["stages"]]
        assert risks == sorted(risks, reverse=True)          # monotonically non-increasing
        assert risks[0] == max(risks)                        # initial budget is the ceiling
        assert risks[-1] == 0.0                              # fully de-risked once it runs
        assert risks[1] < risks[0]                           # strictly falls once the first add is on


def test_exposure_rises_while_risk_falls():
    # "MAXIMISING UPSIDE": the pyramid grows the position exactly as the position stops being able
    # to hurt. That asymmetry is the entire instruction.
    for d in ("LONG", "SHORT"):
        st = _plan(d)["stages"]
        units = [s["units"] for s in st]
        assert units == sorted(units) and units[-1] > units[0]      # it really does add
        assert st[-1]["locked_profit_frac"] > 0 and st[-1]["open_risk_frac"] == 0.0
        locked = [s["locked_profit_frac"] for s in st]
        assert locked == sorted(locked)                      # non-decreasing


def test_the_trail_only_ever_moves_in_the_trades_favour():
    stops = [s["stop"] for s in _plan("LONG")["stages"]]
    assert stops == sorted(stops)                            # a long's stop only ratchets up
    stops = [s["stop"] for s in _plan("SHORT")["stages"]]
    assert stops == sorted(stops, reverse=True)              # a short's only ratchets down


def test_there_is_no_take_profit_anywhere_in_the_plan():
    # "UNTIL THE TREND AND SWING HITS" -- the exit is a structure break, not a number. Capping the
    # winner while the losers run their full R is how a real edge still loses money.
    plan = _plan()
    assert "structure break" in plan["exit_rule"]
    for stage in plan["stages"]:
        assert "target" not in stage and "take_profit" not in stage
        assert "close" not in stage["action"].lower() or "closes back through" in stage["action"]


def test_the_pyramid_shrinks_the_adds_rather_than_breaching_the_stress_bound():
    # If the full ladder would breach the bound, the ADDS give way -- never the rail.
    for stop_frac in (0.005, 0.009, 0.02, 0.04):
        s = kelly_leverage(0.63, 4.0 / (stop_frac * 100), stop_frac * 100)
        plan = management_plan(100.0, 100.0 * (1 - stop_frac), "LONG",
                               risk_fraction=s["risk_fraction"], leverage=s["leverage"])
        assert plan["peak_leverage"] <= MAX_LEVERAGE + 1e-9
        assert plan["peak_stress_loss"] <= MAX_PEAK_STRESS_LOSS + 1e-9
        assert 0.0 <= plan["add_scale"] <= 1.0
        assert plan["status"] in ("OK", "PYRAMID-SCALED")


def test_good_trade_accepted_and_sized_and_scored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    row = record(tmp_path, _t())
    assert row["paper"] is True and row["sizing"]["leverage"] > 0
    assert abs(row["stop_pct"] - 2.0) < 0.01 and "DERIVED" in row["stop_source"]
    assert row["management"]["stages"][0]["open_risk_frac"] == row["sizing"]["risk_fraction"]
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert any(k.startswith("conviction:") for k in logged)     # scored like everything else


def test_pass_must_justify():
    assert not validate({"action": "PASS"})[0]
    assert validate({"action": "PASS", "pass_reason": "no directional edge, chop"})[0]


def test_places_no_orders():
    src = Path("scripts/run_conviction_trader.py").read_text("utf-8")
    for banned in ("binance_live", "place_order", "place_market", "place_post_only"):
        assert banned not in src
    assert "PAPER ONLY" in src


# ------------------------------------------------------------------ sleeve-level drawdown rail

def test_the_drawdown_rail_is_blind_not_ok_when_the_book_is_unmarked(tmp_path):
    # L1.28a: an unmarked book means the rail has no data. That must read as BLIND, never as a
    # clean slate -- "no evidence of a drawdown" and "no drawdown" are not the same statement.
    d = sleeve_drawdown(tmp_path)
    assert d["state"] == "NO-HISTORY" and d["halted"] is False and "BLIND" in d["why"]
    (tmp_path / "data").mkdir()
    (tmp_path / "data/paper_book_pnl.json").write_text(
        json.dumps({"status": "UNMEASURED", "equity": {"n": 0}}))
    assert sleeve_drawdown(tmp_path)["state"] == "NO-HISTORY"


def test_a_losing_run_halts_the_sleeve(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps(
        {"status": "MEASURED", "equity": {"n": 9, "current_drawdown": 0.42, "max_drawdown": 0.42}}))
    d = sleeve_drawdown(tmp_path)
    assert d["state"] == "HALTED" and d["halted"] is True
    # ...and a sleeve inside the rail keeps trading, aggressively.
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps(
        {"status": "MEASURED", "equity": {"n": 9, "current_drawdown": 0.10, "max_drawdown": 0.30}}))
    assert sleeve_drawdown(tmp_path)["halted"] is False


# ---------------------------------------------------------- the measured, per-instrument noise floor

def _flat_bars(n=600, start=100.0, wiggle=0.004):
    """Bars that oscillate by a known amount and go nowhere -- pure noise, no trend."""
    out, ts = [], 1_780_000_000_000
    for i in range(n):
        mid = start * (1 + (wiggle if i % 2 else -wiggle))
        out.append((ts, mid, mid * 1.001, mid * 0.999, mid))
        ts += 15 * 60 * 1000
    return out


def test_adverse_excursion_measures_the_wiggle_it_is_given():
    med = adverse_excursion(_flat_bars(wiggle=0.01), 8.0, "LONG")
    assert med is not None and 1.0 < med < 3.0          # ~2% peak-to-trough oscillation
    quiet = adverse_excursion(_flat_bars(wiggle=0.001), 8.0, "LONG")
    assert quiet < med                                   # a quieter instrument gets a tighter floor


def test_too_few_bars_is_unmeasured_never_zero_noise():
    # Reporting "no noise" from missing data would let every stop through -- the exact inversion.
    assert adverse_excursion(_flat_bars(4), 24.0, "LONG") is None
    nf = noise_floor("BTCUSDT", 24.0, "LONG", fetch=lambda *a: ([], "venue down"))
    assert nf["state"] == "UNMEASURED" and "did NOT pass, it did not run" in nf["why"]
    assert nf["floor_pct"] == MIN_STOP_PCT                # falls back, and says so


def test_a_stop_inside_the_noise_is_refused():
    # REGRESSION PIN from the first live resolver run: a PAXGUSDT short with a 1.04% structural
    # stop over 30h was marked -0.13R -- the thesis was RIGHT (gold fell) and ordinary retrace
    # took it out. Measured floor for that instrument/horizon/direction is ~1.18%.
    noise = {"state": "MEASURED", "floor_pct": 1.18, "median_adverse_pct": 1.18}
    ok, why = validate(_t(invalidation=_ENTRY * 1.0104, horizon_hours=30), noise=noise)
    assert not ok and "INSIDE the noise" in why
    # ...and a level outside the noise on the same trade is fine.
    assert validate(_t(invalidation=_ENTRY * 1.02, horizon_hours=30), noise=noise)[0]


def test_an_unmeasured_noise_floor_does_not_block_the_trade_but_is_recorded():
    # UNMEASURED must not become a silent refusal either: a dead price feed would otherwise halt
    # the sleeve entirely, which is the timid failure of the same coin (L1.28).
    noise = {"state": "UNMEASURED", "floor_pct": MIN_STOP_PCT, "why": "venue down"}
    assert validate(_t(invalidation=_ENTRY * 1.006), noise=noise)[0]


def test_the_constraint_is_published_but_the_reward_is_not():
    # The model is TOLD the noise floor (a constraint it must satisfy) and never told where the
    # sizing optimum sits (a reward it would chase by naming levels that maximise its own size).
    assert "{noise}" in _BRIEF
    low = _BRIEF.lower()
    for leak in ("kelly", "max_risk_per_tra", "slip_stress", "sizing optimum", "1.3-2"):
        assert leak not in low.replace("fractional-kelly against your probability", "")


def test_the_trail_clears_the_noise_too_not_just_the_entry_stop():
    # Consistency: a stop moved to breakeven at +1R sits one R from price, and the entry stop is
    # allowed to sit AT the noise floor -- so the trailed stop has to pass the same test.
    s = kelly_leverage(0.63, 2.0, 2.0)
    tight = management_plan(100.0, 98.0, "LONG", risk_fraction=s["risk_fraction"],
                            leverage=s["leverage"], noise_pct=2.5)      # noise > 1R
    assert tight["trail_R"] > 1.0 and tight["trail_source"] == "noise-widened"
    # each rung's stop lands exactly where the previous rung triggered
    st = tight["stages"]
    for a, b in zip(st, st[1:]):
        assert abs(b["stop"] - a["trigger"]) < 1e-6


def test_a_quiet_instrument_reduces_exactly_to_the_old_one_R_ladder():
    # The change is a GENERALISATION, not a different design: when noise is not binding, nothing
    # about the ladder moves.
    s = kelly_leverage(0.63, 2.0, 2.0)
    base = management_plan(100.0, 98.0, "LONG", risk_fraction=s["risk_fraction"],
                           leverage=s["leverage"])
    quiet = management_plan(100.0, 98.0, "LONG", risk_fraction=s["risk_fraction"],
                            leverage=s["leverage"], noise_pct=0.4)      # 1.5*0.4% < 2% stop
    assert quiet["trail_source"].startswith("1R")
    assert [x["stop"] for x in base["stages"]] == [x["stop"] for x in quiet["stages"]]
    assert [x["trigger"] for x in base["stages"]] == [x["trigger"] for x in quiet["stages"]]


def test_the_widened_trail_keeps_every_downside_invariant():
    # Giving the trade room must not quietly give back the asymmetry it was built for.
    s = kelly_leverage(0.63, 2.0, 2.0)
    for noise in (None, 2.5, 4.0):
        st = management_plan(100.0, 98.0, "LONG", risk_fraction=s["risk_fraction"],
                             leverage=s["leverage"], noise_pct=noise)["stages"]
        risks = [x["open_risk_frac"] for x in st]
        assert risks == sorted(risks, reverse=True) and risks[0] == max(risks)
        assert risks[-1] == 0.0
        assert [x["stop"] for x in st] == sorted(x["stop"] for x in st)
        assert [x["units"] for x in st] == sorted(x["units"] for x in st)
