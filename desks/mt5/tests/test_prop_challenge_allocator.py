"""The FTMO allocator's barrier, objective, phase logic, cost reprice and deploy gate.

`research/prop_challenge_allocator.py` sizes the FTMO book by expected funded days (pass-speed x
pass-probability) from the account's live phase; `prop/ftmo_venue_reader.py` reads the phase off
the account. These pin the rules the solve rests on, with no terminal and no world file.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prop_challenge_allocator as pca  # noqa: E402
from prop import ftmo_venue_reader as fvr  # noqa: E402

R = pca.FTMO_2STEP


def _paths(rows: list[list[float]]) -> np.ndarray:
    """(paths=1, days, sleeves=1) from one path's daily R."""
    return np.asarray(rows, dtype=float)[None]


# ------------------------------------------------------------------ the barrier

def test_a_steady_winner_passes_phase1_only_after_the_minimum_days() -> None:
    r = _paths([[1.0]] * 10)                       # +1R a day
    sim = pca.simulate_phase(r, np.array([0.05]), R, "phase1", pca.AccountState())
    # +5% a day reaches +10% on day 2, then FTMO's 4 minimum trading days still have to be done.
    assert sim["state"][0] == 1 and sim["days"][0] == 4


def test_the_daily_limit_is_measured_on_the_days_low_not_its_close() -> None:
    # Two sleeves: one loses 3R, the other wins 3R the same day -> flat close, 6% low at 2%/R.
    r = np.array([[[-3.0, 3.0]]])
    sim = pca.simulate_phase(r, np.array([0.02, 0.02]), R, "phase1", pca.AccountState())
    assert sim["state"][0] == 2                    # losers first: -6% breaches the 5% daily limit


def test_the_daily_limit_hangs_off_the_days_starting_balance() -> None:
    # Up 4% on day 1, then a 4.5% loss on day 2: the day-2 limit is 104% - 5% = 99%, not breached.
    r = _paths([[2.0], [-2.25]])
    sim = pca.simulate_phase(r, np.array([0.02]), R, "phase1", pca.AccountState())
    assert sim["state"][0] == 0


def test_the_max_loss_is_static_from_the_initial_balance() -> None:
    r = _paths([[-1.0]] * 6)                       # -2.4% a day, under the daily limit
    sim = pca.simulate_phase(r, np.array([0.024]), R, "phase1", pca.AccountState())
    assert sim["state"][0] == 3 and sim["days"][0] == 5     # 1 - 5 x 0.024 = 0.88 <= 0.90


def test_the_e8_profit_cap_strips_the_excess_at_rollover() -> None:
    r = _paths([[5.0]] * 3)                        # +5% a day, capped to +2%
    sim = pca.simulate_phase(r, np.array([0.01]), pca.E8_PRO, "phase1", pca.AccountState())
    assert sim["state"][0] == 0                    # 3 days x 2% = 6% < the 10% target


def test_the_phase_is_solved_from_where_the_account_stands() -> None:
    # One trading day short of the minimum, already at target: one more day passes it.
    st = pca.AccountState(phase="phase1", balance=1.101, equity=1.101, day_start=1.101,
                          days_traded=3, status="MEASURED")
    sim = pca.simulate_phase(_paths([[0.0]] * 5), np.array([0.0]), R, "phase1", st)
    assert sim["state"][0] == 1 and sim["days"][0] == 2


def test_an_account_near_its_daily_limit_breaches_on_a_smaller_loss() -> None:
    st = pca.AccountState(phase="phase1", balance=1.0, equity=0.96, day_start=1.0,
                          status="MEASURED")
    sim = pca.simulate_phase(_paths([[-1.0]]), np.array([0.011]), R, "phase1", st)
    assert sim["state"][0] == 2


# ------------------------------------------------------------------ the objective

def test_j_is_speed_times_probability() -> None:
    sim = {"state": np.array([1, 1, 2, 0], dtype=np.int8), "days": np.array([0, 126, 5, 252])}
    out = pca.phase_outcome(sim, None, horizon=252)
    assert out["J"] == pytest.approx((1.0 + 0.5) / 4)
    assert out["p_pass"] == 0.5 and out["p_fail"] == 0.25


def test_a_later_phase_adds_its_own_days_and_its_own_failures() -> None:
    sim = {"state": np.array([1, 1], dtype=np.int8), "days": np.array([10, 10])}
    cont = np.array([20.0, np.inf])
    out = pca.phase_outcome(sim, cont, horizon=252)
    t = 10 + pca.HANDOFF_DAYS + 20
    assert out["J"] == pytest.approx((252 - t) / 252 / 2)


def test_the_solve_sizes_a_positive_edge_and_holds_survival() -> None:
    rng = np.random.default_rng(1)
    worlds = rng.normal(0.25, 1.0, (8, 256, 1))
    solve_w, _ = pca.make_worlds(worlds, 300, 160, 0)
    h, v = pca.search(solve_w, R, "phase2", pca.AccountState(phase="phase2"), None, 0.05,
                      np.random.default_rng(0), 0.04)
    assert h[0] > 0 and v > 0
    ev = pca.evaluate(solve_w, h, R, "phase2", pca.AccountState(phase="phase2"), None)
    assert ev["risk"] <= 0.04


def test_a_negative_edge_is_never_funded() -> None:
    rng = np.random.default_rng(2)
    worlds = rng.normal(-0.2, 1.0, (8, 256, 1))
    solve_w, _ = pca.make_worlds(worlds, 200, 120, 0)
    h, _ = pca.search(solve_w, R, "phase1", pca.AccountState(), None, 0.05,
                      np.random.default_rng(0), 0.04)
    assert h[0] == 0.0


# ------------------------------------------------------------------ the venue cost

def _surface(hours: dict[int, float], **kw) -> dict:
    return {"symbols": {"AUDNZD": {"hours": {str(h): {"status": "MEASURED", "p50": v}
                                             for h, v in hours.items()}, **kw}}}


def test_the_ftmo_spread_at_the_fill_hour_is_charged_and_never_credited() -> None:
    listing = {"AUDNZD": {"point": 1e-5, "spread": 10}}
    fusion = _surface({1: 20.0, 10: 10.0})
    reg = {"AUDNZD": {"point": 1e-5, "median_spread_pts": 12.0}}
    dear = pca.venue_cost_bias("AUDNZD_overnight_gap_decay_asia", "asia", listing,
                               _surface({1: 60.0}), fusion, reg)
    assert dear["status"] == "PRICED" and dear["ratio_raw"] == pytest.approx(5.0)
    assert dear["bias_r_per_trade"] == pytest.approx(0.05 * 4)
    cheap = pca.venue_cost_bias("AUDNZD_overnight_gap_decay_asia", "asia", listing,
                                _surface({1: 5.0}), fusion, reg)
    assert cheap["bias_r_per_trade"] == 0.0


def test_a_non_positive_measured_stop_is_refused_never_a_credit() -> None:
    listing = {"XAUUSD": {"point": 0.01, "spread": 41, "trade_contract_size": 100.0}}
    reg = {"XAUUSD": {"median_spread_pts": 14.5, "tick_size": 0.01}}
    fusion = {"symbols": {"XAUUSD": {"hours": {"7": {"status": "MEASURED", "p50": 16.0}}}}}
    for rpl in (0.0, -3000.0):
        out = pca.venue_cost_bias("gold_asia", "asia", listing, None, fusion, reg,
                                  risk_per_lot=rpl)
        assert out["status"] == "UNPRICED"


def test_a_sleeve_the_venue_cannot_price_is_refused() -> None:
    out = pca.venue_cost_bias("AUDNZD_overnight_gap_decay_asia", "asia", {}, None, None, None)
    assert out["status"] == "UNPRICED"


def test_a_measured_stop_prices_the_spread_exactly() -> None:
    listing = {"XAUUSD": {"point": 0.01, "spread": 41, "trade_contract_size": 100.0}}
    fusion = {"symbols": {"XAUUSD": {"hours": {"7": {"status": "MEASURED", "p50": 16.0}},
                                     "tick_size": 0.01}}}
    reg = {"XAUUSD": {"median_spread_pts": 14.5, "tick_size": 0.01, "contract_size": 100.0}}
    out = pca.venue_cost_bias("gold_asia", "asia", listing,
                              {"symbols": {"XAUUSD": {"hours": {"7": {"status": "MEASURED",
                                                                       "p50": 41.0}}}}},
                              fusion, reg, risk_per_lot=3000.0, ftmo_commission=2.84)
    want = (2 * (0.41 - 0.145) * 100 + 2 * (2.84 - 2.0)) / 3000.0
    assert out["bias_r_per_trade"] == pytest.approx(want, abs=1e-4)


# ------------------------------------------------------------------ the phase chain

def test_the_phase_advances_only_after_a_pass() -> None:
    chain: dict = {}
    p, _, chain = fvr.infer_phase(chain, "k1", balance=100_000, initial=100_000,
                                  declared="phase1", first_balance_at="2026-10-21", rules=R)
    assert p == "phase1" and chain["accounts"]["k1"]["established"]
    chain = fvr.mark_passed(chain, "k1", balance=110_500, initial=100_000, days_traded=4,
                            flat=True, rules=R)
    p, why, chain = fvr.infer_phase(chain, "k2", balance=100_000, initial=100_000, declared=None,
                                    first_balance_at="2026-12-01", rules=R)
    assert p == "phase2" and "seen to PASS" in why and chain["accounts"]["k2"]["established"]
    p, _, chain = fvr.infer_phase(chain, "k3", balance=100_000, initial=100_000, declared=None,
                                  first_balance_at="2027-01-10", rules=R)
    assert p == "phase2"                           # phase 2 never passed: a retry ...
    assert not chain["accounts"]["k3"]["established"]   # ... which is not established


def test_a_first_seen_account_is_not_an_established_phase() -> None:
    p, why, chain = fvr.infer_phase({}, "k1", balance=1, initial=1, declared=None,
                                    first_balance_at=None, rules=R)
    assert p == "phase1" and not chain["accounts"]["k1"]["established"]
    assert "NOT established" in why


def test_a_missed_pass_is_never_read_as_the_next_phase() -> None:
    chain = fvr.infer_phase({}, "k1", balance=1, initial=1, declared="phase1",
                            first_balance_at=None, rules=R)[2]
    # The reader never saw k1 at its target: k2 is NOT phase2, and NOT established either.
    p, _, chain = fvr.infer_phase(chain, "k2", balance=1, initial=1, declared=None,
                                  first_balance_at=None, rules=R)
    assert p == "phase1" and not chain["accounts"]["k2"]["established"]


def test_an_unestablished_state_is_solved_but_never_deployable(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"status": "UNMEASURED", "phase": "phase1",
                             "initial_balance": 100_000, "balance": 104_000, "equity": 104_000,
                             "day_start_balance": 104_000, "days_traded": 3,
                             "generated_at": datetime.now(tz=UTC).isoformat()}))
    st = pca.read_account_state(p)
    assert st.balance == pytest.approx(1.04) and st.status == "UNESTABLISHED"
    assert not st.measured


def test_a_pass_needs_the_minimum_days_and_a_flat_book() -> None:
    chain = fvr.infer_phase({}, "k1", balance=1, initial=1, declared=None,
                            first_balance_at="a", rules=R)[2]
    assert not fvr.mark_passed(json.loads(json.dumps(chain)), "k1", balance=111_000,
                               initial=100_000, days_traded=3, flat=True,
                               rules=R)["accounts"]["k1"]["passed"]
    assert not fvr.mark_passed(json.loads(json.dumps(chain)), "k1", balance=111_000,
                               initial=100_000, days_traded=5, flat=False,
                               rules=R)["accounts"]["k1"]["passed"]


def test_the_declaration_overrides_the_inference() -> None:
    p, why, _ = fvr.infer_phase({}, "k1", balance=1, initial=1, declared="funded",
                                first_balance_at=None, rules=R)
    assert p == "funded" and "declared" in why


# ------------------------------------------------------------------ the state and the deploy gate

def test_no_state_is_solved_fresh_and_never_deployable(tmp_path: Path) -> None:
    st = pca.read_account_state(tmp_path / "absent.json")
    assert st.phase == "phase1" and not st.measured


def test_a_stale_state_is_not_deployable(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"status": "OK", "phase": "phase2", "initial_balance": 100_000,
                             "balance": 103_000, "equity": 102_500,
                             "day_start_balance": 103_000, "days_traded": 2,
                             "generated_at": (datetime.now(tz=UTC) - timedelta(hours=5))
                             .isoformat()}))
    st = pca.read_account_state(p)
    assert st.phase == "phase2" and st.status == "STALE"
    assert st.balance == pytest.approx(1.03) and st.equity == pytest.approx(1.025)


def _book(tmp_path: Path) -> Path:
    p = tmp_path / "CERT_BOOK_LIVE.json"
    p.write_text(json.dumps({"enabled": True, "ftmo": {"gold_asia": 0.009}, "e8": {}}))
    return p


def test_the_book_moves_only_when_armed_and_deployable(tmp_path: Path) -> None:
    book, armed = _book(tmp_path), tmp_path / "ARMED"
    doc = {"deployable": True, "executable": {"gold_asia": 0.004},
           "generated_at": "t", "account": {"phase": "phase1", "status": "MEASURED"}}
    ceiling = _principal(tmp_path, 0.009)
    assert pca.apply_book(doc, book, armed, ceiling)["applied"] is False   # not armed
    armed.touch()
    assert pca.apply_book({**doc, "deployable": False}, book, armed, ceiling)["applied"] is False
    assert pca.apply_book(doc, book, armed, ceiling)["applied"] is True
    assert json.loads(book.read_text())["ftmo"]["gold_asia"] == 0.004


def test_only_executable_keys_are_ever_written(tmp_path: Path) -> None:
    book, armed = _book(tmp_path), tmp_path / "ARMED"
    armed.touch()
    doc = {"deployable": True, "executable": {"gold_asia": 0.003},
           "sized_no_executor": {"AUDNZD_overnight_gap_decay_asia": 0.01},
           "generated_at": "t", "account": {"phase": "phase1", "status": "MEASURED"}}
    pca.apply_book(doc, book, armed, _principal(tmp_path, 0.009))
    assert set(json.loads(book.read_text())["ftmo"]) == {"gold_asia"}


def test_e8_symbols_keep_own_sleeves_out(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "b.json"
    p.write_text(json.dumps({"enabled": True, "e8": {"gold_asia": 0.006, "AUDCHF_x_asia": 0.0}}))
    monkeypatch.setattr(pca, "CERT_BOOK", p)
    assert pca.e8_symbols() == {"XAUUSD"}


def _principal(tmp_path: Path, v: float) -> Path:
    p = tmp_path / "FTMO_COPY_PRINCIPAL.json"
    p.write_text(json.dumps({"gold_asia": v, "by": "test"}))
    return p


def test_the_copy_is_never_reopened_or_raised_by_the_solve(tmp_path: Path) -> None:
    armed = tmp_path / "ARMED"
    armed.touch()
    book = _book(tmp_path)
    doc = {"deployable": True, "executable": {"gold_asia": 0.004},
           "generated_at": "t", "account": {"phase": "phase1", "status": "MEASURED"}}
    paused = _principal(tmp_path, 0.0)
    assert pca.apply_book(doc, book, armed, paused)["applied"] is False   # a pause stays a pause
    assert pca.apply_book(doc, book, armed, tmp_path / "absent.json")["applied"] is False
    low = _principal(tmp_path, 0.003)
    assert pca.apply_book(doc, book, armed, low)["applied"] is False      # never above the cap


def test_the_ceiling_never_ratchets_on_the_allocators_own_writes(tmp_path: Path,
                                                                 monkeypatch) -> None:
    import mt5desk.gold_oco as oco
    monkeypatch.setattr(oco, "declared_lanes", lambda doc=None: ("e8", "fusion", "ftmo"))
    armed, book = tmp_path / "ARMED", _book(tmp_path)
    armed.touch()
    ceiling = _principal(tmp_path, 0.009)

    def doc(v: float) -> dict:
        return {"deployable": True, "executable": {"gold_asia": v}, "generated_at": "t",
                "account": {"phase": "phase1", "status": "MEASURED"}}

    assert pca.apply_book(doc(0.0025), book, armed, ceiling)["applied"] is True
    assert pca.apply_book(doc(0.0), book, armed, ceiling)["applied"] is True     # an allocator 0
    assert pca.copy_switch(ceiling)["gold_asia"][:2] == (True, 0.009)            # ... no pause
    assert pca.apply_book(doc(0.009), book, armed, ceiling)["applied"] is True   # back up to it
    assert json.loads(book.read_text())["ftmo"]["gold_asia"] == 0.009


def test_the_copy_column_needs_the_principals_switch(tmp_path: Path, monkeypatch) -> None:
    import mt5desk.gold_oco as oco
    p = _principal(tmp_path, 0.009)
    monkeypatch.setattr(oco, "declared_lanes", lambda doc=None: ("e8", "fusion"))
    assert pca.copy_switch(p)["gold_asia"][0] is False                    # lane off
    monkeypatch.setattr(oco, "declared_lanes", lambda doc=None: ("e8", "fusion", "ftmo"))
    assert pca.copy_switch(p)["gold_asia"][:2] == (True, 0.009)
    assert pca.copy_switch(_principal(tmp_path, 0.0))["gold_asia"][0] is False   # paused
    assert pca.copy_switch(tmp_path / "absent.json")["gold_asia"][0] is False


def test_gap_requests_name_one_symbol_per_row(tmp_path: Path) -> None:
    uni = {"listing": {"EURUSD": {}, "GBPUSD": {}, "AUDCAD": {}, "Apple": {}},
           "tier_s": {}, "screen": [{"family": "overnight_gap_decay"}]}
    out = pca.write_gap_requests(uni, datetime.now(tz=UTC), tmp_path / "g.jsonl")
    rows = [json.loads(x) for x in (tmp_path / "g.jsonl").read_text().splitlines()]
    assert out["rows"] == 3 and all(len(r["symbols"]) == 1 for r in rows)


# ------------------------------------------------------------------ the empty book (2026-10-29)

def _slow_world(mu: float = 0.25) -> tuple[pca.World, dict[str, np.ndarray]]:
    """A positive edge, and a later phase that never funds inside the horizon: J is 0 at every
    size, as it was at 15:33Z when phase 1 was too slow for the chain to fund within H."""
    rng = np.random.default_rng(3)
    solve_w, _ = pca.make_worlds(rng.normal(mu, 1.0, (8, 256, 1)), 300, 160, 0)
    never = {"est": np.full(300, np.inf), "halved": np.full(300, np.inf)}
    return solve_w, never


def test_a_flat_zero_j_still_sizes_the_largest_survivable_book() -> None:
    """The 15:33Z defect: J exactly 0 everywhere feasible left the search on the zero book, and
    the zero deployed over an admitted sleeve. Progress to the target breaks the tie."""
    solve_w, never = _slow_world()
    st = pca.AccountState()
    h, v = pca.search(solve_w, R, "phase1", st, never, 0.05, np.random.default_rng(0), 0.04)
    assert v == 0.0 and h[0] > 0
    assert pca.evaluate(solve_w, h, R, "phase1", st, never)["risk"] <= 0.04


def test_the_tie_break_never_sizes_a_negative_edge() -> None:
    solve_w, never = _slow_world(mu=-0.2)
    h, _ = pca.search(solve_w, R, "phase1", pca.AccountState(), never, 0.05,
                      np.random.default_rng(0), 0.04)
    assert h[0] == 0.0


def test_an_empty_book_with_a_feasible_size_is_a_search_defect_not_a_zero() -> None:
    solve_w, never = _slow_world()
    hit = pca.empty_book_probe(solve_w, np.array([0.009]), R, "phase1", pca.AccountState(),
                               never, 0.05, 0.04)
    assert hit is not None and hit["risk"] <= 0.04 and hit["progress"] > 0
    neg, never = _slow_world(mu=-0.2)
    assert pca.empty_book_probe(neg, np.array([0.009]), R, "phase1", pca.AccountState(),
                                never, 0.05, 0.04) is None


def test_a_search_defect_never_deploys(tmp_path: Path, monkeypatch) -> None:
    """The guard behind the fix: a phase block flagged EMPTY_BOOK_SEARCH_DEFECT is not deployable,
    so apply_book leaves the principal's block as it stands, and it is RED from the first pass."""
    monkeypatch.setattr(pca, "search", lambda w, rules, phase, st, cont, cap, rng, margin: (
        (np.zeros(1), 0.0) if margin is not None else (np.array([0.009]), 0.13)))
    monkeypatch.setattr(pca, "build_universe", lambda seed: {
        "status": "OK", "cols": ["gold_asia"], "r": np.random.default_rng(3).normal(
            0.25, 1.0, (8, 256, 1)), "caps": {"gold_asia": 0.009}, "columns": {}})
    monkeypatch.setattr(pca, "write_gap_requests", lambda uni, now: {})
    st = pca.AccountState(phase="phase2", status="MEASURED")
    doc = pca.solve("ftmo", n_paths=300, state=st)
    assert doc["status"].startswith("EMPTY_BOOK_SEARCH_DEFECT") and doc["deployable"] is False
    assert doc["book_deployed"] is False and "RED" in doc["red"]
    armed = tmp_path / "ARMED"
    armed.touch()
    book = tmp_path / "CERT_BOOK_LIVE.json"
    book.write_text(json.dumps({"enabled": True, "ftmo": {"gold_asia": 0.009}}))
    assert pca.apply_book(doc, book, armed)["applied"] is False
    assert json.loads(book.read_text())["ftmo"] == {"gold_asia": 0.009}


def test_a_standing_defect_is_red_with_its_age(tmp_path: Path, monkeypatch) -> None:
    """Rule 23: a defect that persists keeps the old block deployed, so it is RED every pass
    and carries when it began; a sound pass clears it."""
    out = tmp_path / "FTMO_ALLOCATOR.json"
    doc = {"status": "EMPTY_BOOK_SEARCH_DEFECT: x", "generated_at": "2026-10-29T16:00:00+00:00"}
    pca.mark_defect(doc, {"status": "EMPTY_BOOK_SEARCH_DEFECT: x",
                          "defect_since": "2026-10-29T15:00:00+00:00"})
    assert doc["defect_since"] == "2026-10-29T15:00:00+00:00" and "since" in doc["red"]
    fresh = {"status": "EMPTY_BOOK_SEARCH_DEFECT: x", "generated_at": "t1"}
    pca.mark_defect(fresh, {"status": "OK"})
    assert fresh["defect_since"] == "t1"
    ok = {"status": "OK", "generated_at": "t2"}
    pca.mark_defect(ok, {"status": "EMPTY_BOOK_SEARCH_DEFECT: x", "defect_since": "t0"})
    assert "red" not in ok and "defect_since" not in ok
    assert not out.exists()
