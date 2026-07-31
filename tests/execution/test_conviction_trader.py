"""R0125 conviction sleeve -- aggression uncapped, ruin capped, and paper-only.

The structural-stop tests below are the principal's instruction expressed as arithmetic:
*"use calculated SL to prevent it and put trades until the trend and swing hits, minimising
downside and maximising upside."* Downside minimised = open risk falls at every stage of the
ladder and the trail never widens it. Upside maximised = exposure rises and there is no target.
"""
from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.run_conviction_trader import (
    _BRIEF,
    _LENSES,
    ENSEMBLE_N,
    INSTRUMENTS,
    MAX_GROSS_HEAT,
    MAX_LEVERAGE,
    MAX_PEAK_STRESS_LOSS,
    MAX_PORTFOLIO_HEAT,
    MAX_RISK_PER_TRADE,
    MAX_STRESS_LOSS,
    MIN_STOP_PCT,
    RISK_CAP_CEILING,
    RISK_CAP_FLOOR,
    SLIP_STRESS_PCT,
    _chart_brief,
    adverse_excursion,
    calibrated_p,
    derive_stop_pct,
    effective_heat,
    ensemble_consensus,
    kelly_leverage,
    management_plan,
    measured_risk_cap,
    noise_floor,
    portfolio_heat,
    record,
    size_into_headroom,
    sleeve_drawdown,
    slip_leverage_cap,
    validate,
)

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
    # downside at every stage of it. (At a 6% budget no ceiling binds inside the legal stop range,
    # so this is checked by forcing the leverage cap directly.)
    s = kelly_leverage(0.63, 4.0 / 0.5, 0.5)
    assert abs(s["risk_fraction"] - s["leverage"] * 0.005) < 1e-6      # always the realised number
    assert abs(s["risk_fraction"] - s["kelly_risk_fraction"]) < 1e-6   # nothing binding -> agree
    tiny = kelly_leverage(0.63, 4.0 / 0.05, 0.05)                      # sub-legal stop: caps bite
    assert tiny["risk_fraction"] < tiny["kelly_risk_fraction"]
    assert tiny["capped_by"] not in ("", "kelly")


def test_no_size_is_left_on_the_table_at_any_stop_distance():
    # ANTI-TIMIDITY PIN (L1.28). Size must always sit exactly ON the binding constraint -- never
    # below it, and the constraint must be one that has a reason. A flat 10x cap failed this: at a
    # 0.9% stop it deployed 9% of a 20% budget for no reason beyond the roundness of the number.
    for stop in (0.5, 0.9, 1.5, 2.0, 4.0, 10.0):
        s = kelly_leverage(0.63, 4.0 / stop, stop)
        binding = min(MAX_RISK_PER_TRADE / (stop / 100.0),   # kelly / per-trade risk budget
                      slip_leverage_cap(stop),               # gap stress
                      MAX_LEVERAGE,                          # absolute notional
                      kelly_leverage(0.63, 4.0 / stop, stop)["kelly_risk_fraction"]
                      / (stop / 100.0))
        assert abs(s["leverage"] - round(binding, 2)) < 0.02, f"size left unused at {stop}%"
        assert s["capped_by"] != ""


def test_a_tight_structural_stop_deploys_the_whole_budget():
    # REGRESSION PIN for the original defect: a flat 10x cap made a 0.9% structural stop deploy
    # only 9% of a 20% budget, penalising the exact behaviour the calculated stop exists to
    # produce. No ceiling may quietly keep the budget from a tight honest level.
    for stop in (0.5, 0.9, 1.5):
        s = kelly_leverage(0.63, 4.0 / stop, stop)
        assert abs(s["risk_fraction"] - s["kelly_risk_fraction"]) < 1e-9, \
            f"budget stolen at {stop}%"
    assert kelly_leverage(0.63, 4.0 / 0.9, 0.9)["leverage"] > 5.0      # still real leverage


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
        assert risks[1] < risks[0]                       # strictly falls once the first add is on


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


# -------------------------------------------------------- the measured, per-instrument noise floor

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
    for a, b in itertools.pairwise(st):
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


# ------------------------------------------------- breadth is the aggression: portfolio heat rail

def _book_row(symbol, risk, hours_left=6):
    from datetime import UTC, datetime, timedelta
    return json.dumps({"action": "TRADE", "symbol": symbol, "direction": "LONG",
                       "sizing": {"risk_fraction": risk},
                       "resolve_by": (datetime.now(tz=UTC)
                                      + timedelta(hours=hours_left)).isoformat()})


def test_heat_is_read_from_the_open_book_not_assumed(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(
        "\n".join([_book_row("BTCUSDT", 0.06), _book_row("ETHUSDT", 0.06),
                   _book_row("SOLUSDT", 0.06, hours_left=-5)]) + "\n")    # third has expired
    h = portfolio_heat(tmp_path)
    assert h["n_open"] == 2 and abs(h["heat"] - 0.12) < 1e-9
    assert h["state"] == "OPEN" and h["headroom"] > 0
    assert set(h["symbols"]) == {"BTCUSDT", "ETHUSDT"}


def test_a_full_book_refuses_the_next_trade_rather_than_stacking(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(
        "\n".join(_book_row(s, 0.06) for s in
                  ("BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "LINKUSDT")) + "\n")
    h = portfolio_heat(tmp_path)
    assert h["state"] == "FULL" and h["heat"] >= MAX_PORTFOLIO_HEAT
    # with no per-symbol headroom measured, a FULL book still refuses...
    ok, why = validate(_t(), heat=h)
    assert not ok and "UNMEASURED" in why
    # ...and once headroom IS measured, refusal is by fillable size, not by "the book is busy".
    ok, why = validate(_t(), heat={**h, "fits_risk": 0.0})
    assert not ok and "Breadth is the aggression" in why


def test_doubling_the_same_instrument_is_refused(tmp_path):
    # Eight positions all in one name is one position wearing eight names -- exactly what the
    # spread-the-heat simulation says destroys the advantage.
    h = {"state": "OPEN", "heat": 0.06, "symbols": ["PAXGUSDT"]}
    ok, why = validate(_t(symbol="PAXGUSDT"), heat=h)
    assert not ok and "already live" in why
    assert validate(_t(symbol="BTCUSDT"), heat=h)[0]


def test_an_empty_book_leaves_full_heat_available(tmp_path):
    h = portfolio_heat(tmp_path)
    assert h["state"] == "OPEN" and h["heat"] == 0.0 and h["n_open"] == 0


def test_the_universe_is_wide_enough_for_the_heat_cap():
    # Breadth only works if there ARE enough instruments to spread across: the cap allows
    # MAX_PORTFOLIO_HEAT / MAX_RISK_PER_TRADE concurrent positions, and the universe must exceed
    # that or the design silently degrades back to concentration.
    slots = MAX_PORTFOLIO_HEAT / MAX_RISK_PER_TRADE
    assert len(INSTRUMENTS) > slots * 2
    assert len(set(INSTRUMENTS)) == len(INSTRUMENTS)
    assert "PAXGUSDT" in INSTRUMENTS               # the one non-crypto-beta name


def test_blind_on_charts_is_stated_not_hidden(tmp_path):
    # A trader reasoning over structure it cannot see is worse than one that knows it is blind.
    txt = _chart_brief(tmp_path)
    assert "UNAVAILABLE" in txt and "BLIND" in txt


def test_stale_charts_are_flagged(tmp_path):
    from datetime import UTC, datetime, timedelta
    (tmp_path / "data").mkdir()
    old = (datetime.now(tz=UTC) - timedelta(hours=9)).isoformat()
    (tmp_path / "data/chart_context.json").write_text(json.dumps(
        {"generated": old, "status": "OK", "detail": "1/1",
         "charts": {"BTCUSDT": {"state": "OK"}}}))
    txt = _chart_brief(tmp_path)
    assert "STALE" in txt


def test_charts_for_instruments_already_held_are_not_spent_on(tmp_path):
    from datetime import UTC, datetime
    (tmp_path / "data").mkdir()
    (tmp_path / "data/chart_context.json").write_text(json.dumps(
        {"generated": datetime.now(tz=UTC).isoformat(), "status": "OK", "detail": "2/2",
         "charts": {"BTCUSDT": {"state": "OK"}, "ETHUSDT": {"state": "OK"}}}))
    txt = _chart_brief(tmp_path, {"symbols": ["BTCUSDT"]})
    assert "ETHUSDT" in txt and "BTCUSDT" not in txt.split("\n", 1)[1]


# ---------------------------------- correlation-weighted heat: real diversification, real room

def _cc(tmp_path, corr):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/chart_context.json").write_text(json.dumps({"correlations": corr}))


def _pos(sym, r=0.06):
    return {"symbol": sym, "sizing": {"risk_fraction": r}}


def test_identical_bets_get_no_diversification_credit(tmp_path):
    # Five copies of the same trade is one trade. The naive sum is right here and must stay right.
    _cc(tmp_path, {s: dict.fromkeys("ABCDE", 1.0) for s in "ABCDE"})
    eff, _ = effective_heat(tmp_path, [_pos(s) for s in "ABCDE"])
    assert abs(eff - 0.30) < 1e-6


def test_genuinely_uncorrelated_bets_buy_real_capacity(tmp_path):
    _cc(tmp_path, {s: {t: (1.0 if s == t else 0.0) for t in "ABCDE"} for s in "ABCDE"})
    eff, _ = effective_heat(tmp_path, [_pos(s) for s in "ABCDE"])
    assert eff < 0.30                                   # less portfolio risk than the naive sum...
    assert eff > 0.06 * 5 / 5                           # ...but never less than a single position


def test_correlations_are_stressed_toward_one_never_toward_zero(tmp_path):
    # Correlations rise in exactly the cascade that hurts. A rail trusting calm-market numbers
    # fails when it matters, so diversification is credited only partly.
    _cc(tmp_path, {s: {t: (1.0 if s == t else 0.0) for t in "AB"} for s in "AB"})
    eff, basis = effective_heat(tmp_path, [_pos("A"), _pos("B")])
    independent = (0.06 ** 2 + 0.06 ** 2) ** 0.5
    assert eff > independent                            # strictly less credit than the raw estimate
    assert "stressed" in basis


def test_unmeasured_correlation_falls_back_to_the_naive_sum(tmp_path):
    # Never to an optimistic default: a blind book must not believe it is diversified.
    eff, basis = effective_heat(tmp_path, [_pos("A"), _pos("B")])
    assert abs(eff - 0.12) < 1e-9 and "UNMEASURED" in basis
    _cc(tmp_path, {"A": {"A": 1.0}})                    # B missing from the matrix
    eff, basis = effective_heat(tmp_path, [_pos("A"), _pos("B")])
    assert abs(eff - 0.12) < 1e-9 and "no measured correlation" in basis


def test_the_gross_cap_still_binds_however_diversified_the_book_looks(tmp_path):
    # Correlation estimates can be wrong; the nominal cap bounds how wrong they may make the book.
    _cc(tmp_path, {f"S{i}": {f"S{j}": (1.0 if i == j else 0.0) for j in range(9)}
                   for i in range(9)})
    (tmp_path / "data/conviction_book.jsonl").write_text("\n".join(
        json.dumps({**_pos(f"S{i}"), "action": "TRADE", "direction": "LONG",
                    "hard_exit_by": (datetime.now(tz=UTC) + timedelta(hours=9)).isoformat()})
        for i in range(9)) + "\n")
    h = portfolio_heat(tmp_path)
    assert h["gross_heat"] >= MAX_GROSS_HEAT and h["state"] == "FULL"


# --------------------------------------- the position clock is not the forecast clock

def test_a_trade_gets_far_longer_than_its_forecast_horizon(tmp_path, monkeypatch):
    # Measured: the same gold short reads +0.07R at a 12h horizon and +0.63R at 30h. An arbitrary
    # clock was setting the P&L instead of the structure.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    row = record(tmp_path, _t(horizon_hours=12))
    assert row["max_hold_hours"] == 48.0                # 4x the forecast horizon
    assert row["hard_exit_by"] > row["resolve_by"]      # position outlives its scoring clock
    assert "POST_ONLY_LIMIT" in row["entry_order_type"]


def test_heat_is_released_once_the_resolver_marks_a_trade_closed(tmp_path):
    # A stopped position must stop occupying heat immediately -- blocking new trades with capital
    # returned hours ago is idle capacity dressed as prudence.
    (tmp_path / "data").mkdir()
    key = datetime.now(tz=UTC).isoformat()
    (tmp_path / "data/conviction_book.jsonl").write_text(json.dumps(
        {"action": "TRADE", "symbol": "BTCUSDT", "direction": "LONG", "at": key,
         "sizing": {"risk_fraction": 0.06},
         "hard_exit_by": (datetime.now(tz=UTC) + timedelta(hours=40)).isoformat()}) + "\n")
    assert portfolio_heat(tmp_path)["n_open"] == 1
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps(
        {"marks": [{"key": key, "outcome": "STOPPED"}]}))
    assert portfolio_heat(tmp_path)["n_open"] == 0      # capital back, slot free


# ------------------------------------------------- geometric growth: the three levers, measured

def test_size_follows_measured_accuracy_in_both_directions(monkeypatch):
    # THE GROWTH TERM, not a safety feature: if the sleeve claims 0.63 and truly hits 0.45, sizing
    # on 0.63 bets ~2x Kelly, where E[log wealth] is NEGATIVE. And the upward direction matters
    # just as much -- a desk measured UNDER-confident gets its size handed back automatically.
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "calibrated_confidence",
                        lambda p: {"raw": p, "adjusted": p - 0.12, "applied": True, "bias": 0.12})
    over = calibrated_p(0.63)
    assert over["used"] < over["raw"] and "over-confident" in over["direction"]
    monkeypatch.setattr(fc, "calibrated_confidence",
                        lambda p: {"raw": p, "adjusted": p + 0.09, "applied": True, "bias": -0.09})
    under = calibrated_p(0.63)
    assert under["used"] > under["raw"] and "earned size returned" in under["direction"]
    # ...and a smaller probability is strictly less Kelly, which is the whole mechanism. Asserted
    # on full_kelly because the 6% per-trade cap masks the difference at these probabilities --
    # the growth term is what moves, and the cap is downstream of it.
    assert (kelly_leverage(over["used"], 2.0, 2.0)["full_kelly"]
            < kelly_leverage(under["used"], 2.0, 2.0)["full_kelly"])


def test_unmeasured_calibration_sizes_on_the_raw_claim_and_says_so(monkeypatch):
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "calibrated_confidence",
                        lambda p: (_ for _ in ()).throw(OSError("log unreadable")))
    c = calibrated_p(0.63)
    assert c["used"] == 0.63 and c["applied"] is False and "UNMEASURED" in c["why"]


def test_the_raw_claim_is_what_gets_scored_not_the_size_taken(tmp_path, monkeypatch):
    # Grading the adjusted number would launder the model's error through the desk's own
    # correction, and the bias would never become measurable again.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    monkeypatch.setattr(fc, "calibrated_confidence",
                        lambda p: {"raw": p, "adjusted": 0.55, "applied": True, "bias": 0.08})
    row = record(tmp_path, _t())
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert any(abs(f["p"] - 0.63) < 1e-9 for f in logged.values())    # RAW is scored
    assert row["sizing"]["calibration"]["used"] == 0.55               # ADJUSTED is sized


def test_an_uncorrelated_trade_gets_more_room_than_a_duplicate(tmp_path):
    # The multivariate-Kelly intuition made operational: allocate to the bet that adds the most
    # growth per unit of PORTFOLIO risk, not per unit of its own risk.
    _cc(tmp_path, {"A": {"A": 1.0, "B": 1.0, "Z": 0.0},
                   "B": {"A": 1.0, "B": 1.0, "Z": 0.0},
                   "Z": {"A": 0.0, "B": 0.0, "Z": 1.0}})
    book = [_pos("A", 0.14), _pos("B", 0.14)]
    dup = size_into_headroom(tmp_path, "A", 0.06, book)["risk"]
    div = size_into_headroom(tmp_path, "Z", 0.06, book)["risk"]
    assert div > dup


def test_a_busy_book_trims_the_trade_instead_of_refusing_it(tmp_path):
    # An unbooked setup contributes exactly zero to geometric growth; a small one does not.
    _cc(tmp_path, {s: {t: (1.0 if s == t else 0.9) for t in "ABCDEFG"} for s in "ABCDEFG"})
    book = [_pos(s) for s in "ABCDE"]
    fit = size_into_headroom(tmp_path, "F", 0.06, book)
    assert 0.0 < fit["risk"] < 0.06 and fit["bound"] == "effective_heat"
    ok, _ = validate(_t(), heat={"heat": 0.28, "fits_risk": fit["risk"], "symbols": []})
    assert ok                                            # taken small, not thrown away


def test_nothing_fillable_is_still_refused(tmp_path):
    ok, why = validate(_t(), heat={"heat": 0.30, "fits_risk": 0.0001, "symbols": []})
    assert not ok and "no fillable size" in why


# --------------------------------------- the per-trade cap is DERIVED, and it can go UP

def test_the_cap_rises_with_a_measured_hit_rate(monkeypatch):
    # The flat 6% was wrong in the TIMID direction and the principal caught it: at a real 35% hit
    # rate full Kelly is 13.3%, so 6% is 0.45x Kelly and leaves growth on the table (L1.28).
    import libs.self_improvement.forecast_calibration as fc
    caps = []
    for p in (0.30, 0.35, 0.42):
        monkeypatch.setattr(fc, "report",
                            lambda p=p: {"n_resolved": 60, "hit_rate_posterior": p})
        caps.append(measured_risk_cap(Path("."))["cap"])
    assert caps == sorted(caps) and caps[-1] > caps[0]
    assert caps[-1] > RISK_CAP_FLOOR                  # a proven forecaster earns MORE size
    assert caps[-1] <= RISK_CAP_CEILING


def test_an_unmeasured_hit_rate_holds_the_floor_and_says_why(monkeypatch):
    # Not timidity: a cap derived from an unobserved rate is a guess wearing a formula, and this
    # is the same rule that treats an unmeasured correlation as a duplicate.
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "report", lambda: {"n_resolved": 4, "hit_rate_posterior": 0.5})
    c = measured_risk_cap(Path("."))
    assert c["cap"] == RISK_CAP_FLOOR and c["state"] == "UNMEASURED"
    assert "guess wearing a formula" in c["why"]


def test_a_poor_measured_hit_rate_never_pushes_the_cap_below_the_floor(monkeypatch):
    # Sizing DOWN is calibrated_p's job (it shrinks the probability). The cap floor stays put so a
    # bad patch cannot ratchet the sleeve into irrelevance before the kill condition decides.
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "report", lambda: {"n_resolved": 60, "hit_rate_posterior": 0.26})
    assert measured_risk_cap(Path("."))["cap"] == RISK_CAP_FLOOR


def test_the_sizer_actually_consumes_the_higher_cap():
    lo = kelly_leverage(0.63, 4.0 / 2.0, 2.0, risk_cap=0.06)["risk_fraction"]
    hi = kelly_leverage(0.63, 4.0 / 2.0, 2.0, risk_cap=0.11)["risk_fraction"]
    assert hi > lo                                    # the cap is a real input, not decoration


# ------------------------------------------- the ensemble: precision bought with frequency

def _read(sym, direction, p, action="TRADE"):
    return {"action": action, "symbol": sym, "direction": direction, "probability": p}


def test_a_split_ensemble_stands_aside():
    # Near a 31.1% breakeven, +3pp of hit rate multiplies g by 3.5x while halving the trade count
    # costs a factor of 2. Standing aside on disagreement is the good side of that trade.
    call, d = ensemble_consensus([_read("BTCUSDT", "LONG", 0.62),
                                  _read("ETHUSDT", "SHORT", 0.60),
                                  _read("SOLUSDT", "LONG", 0.55)])
    assert d["state"] == "SPLIT" and call["action"] == "PASS"
    assert "precision is worth more than frequency" in call["pass_reason"] + d["why"]


def test_two_of_three_is_enough_to_trade():
    call, d = ensemble_consensus([_read("BTCUSDT", "LONG", 0.62),
                                  _read("ETHUSDT", "SHORT", 0.60),
                                  _read("BTCUSDT", "LONG", 0.55)])
    assert d["state"] == "CONSENSUS" and call["action"] == "TRADE"
    assert call["symbol"] == "BTCUSDT" and d["n_agreeing"] == 2


def test_the_consensus_takes_the_most_conservative_probability():
    # Averaging lets one over-confident read pull the size up, and Kelly is CONVEX in p -- so the
    # error from an inflated probability is not symmetric with the error from a cautious one.
    call, d = ensemble_consensus([_read("BTCUSDT", "LONG", 0.88),
                                  _read("BTCUSDT", "LONG", 0.54)])
    assert call["probability"] == 0.54
    assert "convex" in d["probability_rule"]


def test_the_rejected_minority_is_kept_not_discarded():
    # Whether this filter HELPS is itself measurable, and imposing it without keeping what it
    # rejected makes that unanswerable.
    _c, d = ensemble_consensus([_read("BTCUSDT", "LONG", 0.62),
                                _read("ETHUSDT", "SHORT", 0.60),
                                _read("BTCUSDT", "LONG", 0.55)])
    assert d["minority"] and d["minority"][0]["symbol"] == "ETHUSDT"


def test_a_consensus_to_pass_is_a_pass():
    call, d = ensemble_consensus([{"action": "PASS", "pass_reason": "chop, no edge"},
                                  {"action": "PASS", "pass_reason": "nothing set up"},
                                  _read("BTCUSDT", "LONG", 0.62)])
    assert call["action"] == "PASS" and d["state"] == "CONSENSUS"


def test_no_readable_reads_is_not_a_trade():
    call, d = ensemble_consensus([None, None, None])
    assert call is None and d["state"] == "NO-READS"


def test_the_lenses_are_actually_different():
    # Three samples of one framing correlate heavily and their agreement means almost nothing.
    assert len(set(_LENSES)) == len(_LENSES) == ENSEMBLE_N
    assert any("OPPOSITE" in x for x in _LENSES)
    assert any("already in" in x for x in _LENSES)
