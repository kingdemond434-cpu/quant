"""R0133 paper book resolver -- the mark must be real, conservative, and refuse rather than guess.

An unmarked paper book is the purest form of the L1.28a defect: it accumulates confident rows,
reports no failure, and reads as though the sleeve works. These tests pin that the mark walks the
recorded ladder, resolves intrabar ambiguity AGAINST the desk, and never turns a missing price
series into a zero.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.resolve_paper_book import (KILL_AFTER_N, KILL_HIT_RATE, _benchmark,
                                        equity_curve, kill_check, mark_event_row,
                                        resolve_book, trade_cost, walk_ladder)
from scripts.run_conviction_trader import kelly_leverage, management_plan

_ENTRY, _INVAL = 100.0, 98.0                  # LONG, R = 2.0
_START = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)


def _row(direction="LONG", entry=_ENTRY, inval=_INVAL, hours=24):
    s = kelly_leverage(0.63, 4.0 / 2.0, 2.0)
    plan = management_plan(entry, inval, direction,
                           risk_fraction=s["risk_fraction"], leverage=s["leverage"])
    return {"action": "TRADE", "symbol": "BTCUSDT", "direction": direction, "probability": 0.63,
            "entry_ref": entry, "invalidation": inval, "expected_move_pct": 4.0,
            "horizon_hours": hours, "at": _START.isoformat(), "paper": True, "sizing": s,
            "management": plan,
            "resolve_by": (_START + timedelta(hours=hours)).isoformat()}


def _bars(path):
    """path = list of (high, low) in order; open/close filled in plausibly."""
    out, ts = [], int(_START.timestamp() * 1000)
    for hi, lo in path:
        out.append((ts, (hi + lo) / 2, hi, lo, (hi + lo) / 2))
        ts += 15 * 60 * 1000
    return out


def test_a_trade_stopped_at_its_invalidation_loses_exactly_one_R():
    res = walk_ladder(_row(), _bars([(100.5, 97.0)]))
    assert res["outcome"] == "STOPPED"
    assert abs(res["realised_R"] + 1.0) < 1e-9              # -1R, no more
    assert res["exit_price"] == _INVAL and res["stage_reached"] == 0
    # GROSS is exactly the risk the sizer budgeted, never more...
    assert abs(res["gross_return"] + _row()["sizing"]["risk_fraction"]) < 1e-9
    # ...and NET is that plus costs, because a stop is a real fill that a real venue charges for.
    assert res["equity_return"] < res["gross_return"]
    assert abs(res["equity_return"] - (res["gross_return"] - res["cost"]["total"])) < 1e-9
    assert res["cost"]["entry_side"] == "maker"          # resting order at the named level


def test_costs_are_deducted_so_a_marginal_edge_reads_as_marginal():
    # At 6.7x a round trip is ~24% of a full R: a gross mark shows a 30% hit rate as profitable
    # when it is a loser. This is the self-flattery the resolver exists to prevent.
    c = trade_cost(6.7, 1.5, 20.0)
    assert c["total"] > 0.005 and c["total"] < 0.02
    assert c["entry_fee"] < c["exit_fee"]                # maker in, taker out
    taker = trade_cost(6.7, 1.5, 20.0, entry_maker=False)
    assert taker["total"] > c["total"] * 1.3             # chasing the entry costs real money
    assert trade_cost(0.0, 0.0, 0.0)["total"] == 0.0     # no position, no cost


def test_intrabar_ambiguity_resolves_against_the_desk():
    # ADVERSE-FIRST: this bar contains both the +1R trigger (102) and the stop (98). Assuming the
    # trigger printed first would manufacture a winner out of an unknowable ordering.
    res = walk_ladder(_row(), _bars([(103.0, 97.5)]))
    assert res["outcome"] == "STOPPED" and res["realised_R"] < 0


def test_a_trend_that_runs_advances_the_ladder_and_pays_more_than_one_R():
    # "PUT TRADES UNTIL THE TREND AND SWING HITS": price grinds up, the ladder advances, the adds
    # go on, and the trail -- not a target -- takes it out.
    path = [(100.0 + i * 0.6, 99.0 + i * 0.6) for i in range(22)]      # up to ~113
    path += [(112.0, 106.0)]                                          # the swing that breaks
    res = walk_ladder(_row(), _bars(path))
    assert res["outcome"] == "TRAILED-OUT"
    assert res["stage_reached"] == res["max_stage"]         # the whole ladder was walked
    assert res["units_at_exit"] > 1.0                       # it really did pyramid
    assert res["realised_R"] > 1.5                          # and the winner is a multiple of 1R
    assert res["equity_return"] > 0


def test_the_winner_is_bigger_than_the_loser_on_the_same_R():
    # The asymmetry the whole design exists for, measured rather than asserted.
    loss = walk_ladder(_row(), _bars([(100.5, 97.0)]))["realised_R"]
    path = [(100.0 + i * 0.6, 99.0 + i * 0.6) for i in range(22)] + [(112.0, 106.0)]
    win = walk_ladder(_row(), _bars(path))["realised_R"]
    assert win > abs(loss) * 1.5


def test_a_short_is_the_mirror_image():
    row = _row(direction="SHORT", entry=100.0, inval=102.0)
    res = walk_ladder(row, _bars([(103.0, 99.5)]))          # stop above -> hit
    assert res["outcome"] == "STOPPED" and abs(res["realised_R"] + 1.0) < 1e-9
    path = [(101.0 - i * 0.6, 100.0 - i * 0.6) for i in range(22)] + [(94.0, 88.0)]
    res = walk_ladder(row, _bars(path))
    assert res["realised_R"] > 1.5 and res["units_at_exit"] > 1.0


def test_a_position_still_open_is_marked_open_not_won():
    path = [(100.4 + i * 0.05, 99.6 + i * 0.05) for i in range(6)]     # drifts, nothing triggers
    res = walk_ladder(_row(), _bars(path))
    assert res["outcome"] == "OPEN"


def test_no_bars_means_no_mark_never_a_zero():
    assert walk_ladder(_row(), [])["outcome"] == "UNRESOLVABLE"
    assert mark_event_row({"direction": "LONG"}, [])["outcome"] == "UNRESOLVABLE"
    assert _benchmark([]) is None


def test_an_unfetchable_window_never_becomes_evidence(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(json.dumps(_row()) + "\n")
    rep = resolve_book(tmp_path, now=_START + timedelta(days=2),
                       fetch=lambda *a: ([], "UNRESOLVABLE -- venue down"))
    assert rep["status"] == "UNMEASURED"
    assert rep["n_unresolvable"] == 1 and rep["n_resolved"] == 0
    assert rep["sleeve_return"] is None                     # not 0.0 -- absence, not flat
    assert "NO evidence" in rep["detail"]


def test_an_empty_book_reports_unmeasured_not_ok(tmp_path):
    (tmp_path / "data").mkdir()
    rep = resolve_book(tmp_path, now=_START)
    assert rep["status"] == "UNMEASURED" and rep["n_resolved"] == 0


def test_a_resolved_book_is_benchmarked_against_buy_and_hold(tmp_path):
    # L1.6: a levered sleeve that merely tracks buy-and-hold is taking risk for nothing.
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(json.dumps(_row()) + "\n")
    path = [(100.0 + i * 0.6, 99.0 + i * 0.6) for i in range(22)] + [(112.0, 106.0)]
    rep = resolve_book(tmp_path, now=_START + timedelta(days=2),
                       fetch=lambda *a: (_bars(path), "test"))
    assert rep["status"] == "MEASURED" and rep["n_resolved"] == 1
    assert rep["buy_and_hold_return"] is not None
    assert rep["beats_buy_and_hold"] is (rep["sleeve_return"] > rep["buy_and_hold_return"])
    assert rep["win_rate"] == 1.0


def test_a_torn_book_line_is_skipped_not_guessed_at(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(
        json.dumps(_row()) + "\n{ this is a torn write\n")
    rep = resolve_book(tmp_path, now=_START + timedelta(days=2),
                       fetch=lambda *a: ([], "down"))
    assert rep["n_rows"] == 1                               # the torn line contributed nothing


def test_conventions_are_published_with_every_report(tmp_path):
    # Each convention decides the answer; a mark that hides them is a number nobody can audit.
    (tmp_path / "data").mkdir()
    rep = resolve_book(tmp_path, now=_START)
    assert any("adverse-first" in c for c in rep["conventions"])
    assert any("slippage" in c for c in rep["conventions"])


# ----------------------------------------------- geometric growth is the objective, so measure it

def _closed(rets, hours=20):
    from datetime import timedelta
    return [{"equity_return": r, "outcome": "STOPPED", "closed": True, "profitable": r > 0,
             "exit_at": (_START + timedelta(hours=hours * (i + 1))).isoformat()}
            for i, r in enumerate(rets)]


def test_log_growth_per_trade_is_reported_not_just_total_return():
    # The objective is max E[log wealth]. Total return over a short window says almost nothing
    # about it; g per trade x trades per year is the quantity that compounds.
    c = equity_curve(_closed([0.18] * 7 + [-0.06] * 13))
    assert c["log_growth_per_trade"] > 0
    assert c["trades_per_year_at_this_pace"] > 0
    assert c["implied_cagr"] is not None


def test_a_losing_edge_names_EDGE_as_the_constraint_not_frequency():
    # THE POINT OF NAMING IT: if g <= 0, raising cadence multiplies a losing bet. Reporting a
    # growth number without saying which term is short invites exactly the wrong response.
    c = equity_curve(_closed([0.18] * 2 + [-0.06] * 18))
    assert c["log_growth_per_trade"] <= 0
    assert c["growth_constraint"].startswith("EDGE")
    assert "makes it worse" in c["growth_constraint"]


def test_a_winning_edge_at_low_pace_names_FREQUENCY():
    c = equity_curve(_closed([0.18] * 7 + [-0.06] * 13, hours=24 * 30))   # ~12 trades/yr
    assert c["log_growth_per_trade"] > 0
    assert c["growth_constraint"].startswith("FREQUENCY")


def test_no_closed_trades_is_unmeasured_never_zero_growth():
    c = equity_curve([])
    assert c["log_growth_per_trade"] is None
    assert c["growth_constraint"].startswith("UNMEASURED")


def test_the_kill_condition_is_pre_registered_and_gives_no_verdict_early():
    # An author who has built something finds reasons to extend a failing test. The threshold is
    # fixed before the data exists, and before the decision point there is NO verdict either way.
    r = kill_check(_closed([0.18] * 2 + [-0.06] * 8))
    assert r["state"] == "RUNNING" and r["n_closed"] < KILL_AFTER_N
    assert "no verdict either way" in r["why"]


def test_a_dead_sleeve_is_killed_with_no_extensions():
    r = kill_check(_closed([0.18] * 8 + [-0.06] * 42))        # 16% hit rate over 50
    assert r["state"] == "KILL" and r["hit_rate"] < KILL_HIT_RATE
    assert "NO EXTENSIONS" in r["why"] and "materially NEW mechanism" in r["why"]


def test_surviving_the_kill_check_is_not_a_promotion():
    # 30% clears the 25% kill floor and is still BELOW the 31.1% cost-adjusted breakeven.
    r = kill_check(_closed([0.18] * 15 + [-0.06] * 35))
    assert r["state"] == "SURVIVES-THIS-CHECK"
    assert "not a promotion" in r["why"] and "breakeven" in r["why"]


def test_the_kill_floor_sits_below_breakeven_not_at_it():
    # Killing at exactly breakeven would graveyard a real 33% edge about half the time.
    assert KILL_HIT_RATE < 0.311
