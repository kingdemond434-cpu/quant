"""The two stop-geometry constants are solved on kelly_survival's objective, never chosen.

`research/stop_geometry_derivation.py` sets gateway.MIN_STOP_SPREAD_MULT and
decision_core.ENTRY_DRIFT_TOL_FRAC by maximising ruin-counted E[log W] subject to
P(losing 80% within 60 days) <= 5%. These tests pin the trade model, the solve's refusal to move
a money-path number on noise, the aggressiveness flag, and that an absent input reads UNMEASURED.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stop_geometry_derivation as sgd  # noqa: E402


def test_a_stop_the_widened_quote_reaches_is_lost_whatever_the_edge() -> None:
    # x = 2 spreads: the quote alone takes it once the spread widens 3x (W >= 2x - 1).
    x = np.array([2.0, 2.0])
    r = sgd.trade_r(x, np.full(2, 1.5), np.full(2, 50.0), np.array([3.0, 2.9]),
                    np.array([0.0, 0.0]))
    assert r[0] == pytest.approx(-1.0 - 0.5)            # taken: -1R less the spread in R
    assert r[1] == pytest.approx(1.5 - 0.5)             # not taken: the certain win, less spread


def test_the_price_edge_dilutes_as_the_bracket_widens() -> None:
    """A fixed-hold edge worth `e*x + 1` spreads at geometry x is worth (e*x + 1)/x' R gross at
    x', less 1/x' of spread: the trade-off the solve prices."""
    rng = np.random.default_rng(0)
    n = 200_000
    u = rng.random(n)
    edge = np.full(n, 0.2 * 10 + 1.0)                   # e = 0.2R at x = 10 spreads
    no_widen = np.ones(n)
    at_10 = sgd.trade_r(np.full(n, 10.0), np.full(n, 1.5), edge, no_widen, u).mean()
    at_20 = sgd.trade_r(np.full(n, 20.0), np.full(n, 1.5), edge, no_widen, u).mean()
    assert at_10 == pytest.approx(0.2, abs=0.01)        # the certificate's own net R
    assert at_20 == pytest.approx((3.0 - 1.0) / 20.0, abs=0.01)


def _active(n: int = 400, days: int = 60, slots: int = 3) -> np.ndarray:
    return np.ones((n, days, slots), dtype=bool)


def test_a_flat_objective_never_moves_todays_number() -> None:
    act = _active()
    base = np.random.default_rng(1).normal(0.05, 1.0, act.shape)
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: base, act, 0.005, 3.0, "lower")
    assert res["status"] == "TODAY_OPTIMAL_WITHIN_NOISE"
    assert res["derived"] == 3.0 and res["less_aggressive_than_today"] is False
    assert res["tie_rule_value"] == 1.0                 # named, not taken


def test_a_clear_optimum_moves_and_says_which_way() -> None:
    act = _active()
    noise = np.random.default_rng(2).normal(0.0, 0.5, act.shape)
    # E[R] peaks at 2.0: the more aggressive side of today's 3.0 for "lower".
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: noise + 0.3 - 0.2 * abs(v - 2.0),
                     act, 0.005, 3.0, "lower")
    assert res["status"] == "OK" and res["derived"] == 2.0
    assert res["less_aggressive_than_today"] is False
    assert res["vs_today"]["delta_elog_per_day"] > 0
    # The same peak read on a "higher is more aggressive" constant below today is flagged.
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: noise + 0.3 - 0.2 * abs(v - 2.0),
                     act, 0.005, 3.0, "higher")
    assert res["derived"] == 2.0 and res["less_aggressive_than_today"] is True


def test_every_value_dead_is_stated_and_today_stands() -> None:
    act = _active()
    res = sgd._solve((1.0, 2.0), lambda v: np.full(act.shape, -1.0), act, 0.05, 1.0, "lower")
    assert res["status"].startswith("NO_SURVIVING_VALUE") and res["derived"] is None


def test_a_price_distance_in_the_risk_field_is_not_an_r() -> None:
    # 2026-09-16 family rows: risk_quote is a signed price distance and r_multiple 0.0.
    assert sgd.ledger_r({"r_multiple": 0.0, "pl_quote": -3.24, "risk_quote": -0.00026}) is None
    # A positive MONEY risk is a real denominator: P/L over it is the R.
    assert sgd.ledger_r({"r_multiple": 0.0, "pl_quote": 1.0, "risk_quote": 2.0}) == \
        pytest.approx(0.5)
    assert sgd.ledger_r({"r_multiple": -1.0966, "pl_quote": -6.2, "risk_quote": 5.67}) == \
        pytest.approx(-1.0966)


def test_a_truncated_order_comment_names_its_sleeve() -> None:
    names = {"eurgbp_discovered_asia_p_8e61ea22743f15b7"}
    assert sgd._sleeve_of({"sleeve": "eurgbp_discovered_asia_p_8e"}, names)
    assert not sgd._sleeve_of({"sleeve": "eurgbp"}, names)     # too short to name one sleeve
    assert not sgd._sleeve_of({"sleeve": "audusd_discovered_asia_p_8e"}, names)


def test_spread_geometry_reads_stop_in_spreads_and_widening() -> None:
    n = 40
    df = pd.DataFrame({"high": np.full(n, 101.0), "low": np.full(n, 99.0),
                       "close": np.full(n, 100.0), "spread": np.full(n, 10)})
    df.loc[25, "spread"] = 50
    x, w = sgd.spread_geometry(df, 0.01, 1.0, 14, 3)
    assert x[0] == pytest.approx(2.0 / 0.1)             # ATR 2.0 over a 0.10 spread
    assert w.max() == pytest.approx(5.0) and np.median(w) == pytest.approx(1.0)


def test_absent_inputs_read_unmeasured_never_a_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sgd, "SLEEVES", tmp_path / "absent.json")
    monkeypatch.setattr(sgd, "LEDGER", tmp_path / "absent.jsonl")
    doc = sgd.derive()
    assert doc["status"] == "UNMEASURED"
    for k in ("MIN_STOP_SPREAD_MULT", "ENTRY_DRIFT_TOL_FRAC"):
        assert doc[k]["status"].startswith("UNMEASURED")
        assert doc[k].get("derived") is None


def test_the_solve_is_kelly_survivals() -> None:
    import kelly_survival as ks
    assert (sgd.DEATH_LINE, sgd.EPS_DEATH, sgd.HORIZON) == (ks.DEATH_LINE, ks.EPS_DEATH,
                                                             ks.HORIZON)
    assert pytest.approx(0.20) == sgd.DEATH_LINE and pytest.approx(0.05) == sgd.EPS_DEATH
    assert sgd.HORIZON == 60


def test_a_value_kept_on_the_evidence_is_a_solved_constant(monkeypatch) -> None:
    ok = {"status": "OK", "derived": 0.05}
    kept = {"status": "TODAY_OPTIMAL_WITHIN_NOISE", "derived": 3.0}
    monkeypatch.setattr(sgd, "derive_min_stop_spread_mult", lambda deals, **k: dict(kept))
    monkeypatch.setattr(sgd, "derive_entry_drift_tol_frac", lambda deals, **k: dict(ok))
    assert sgd.derive()["status"] == "OK"


# --------------------------------------------------------------------- the robustness gate
def _solved(derived: float, today: float, *, n: int, mean: float | None, sd: float | None,
            prior_r: float = 0.29, delta: float = 1.7e-4) -> dict:
    return {"status": "OK", "derived": derived, "today": today,
            "vs_today": {"delta_elog_per_day": delta},
            "inputs": {"edge": {"prior_r": prior_r, "live_n": n, "live_mean_r": mean,
                                "live_sd_r": sd}}}


@pytest.mark.parametrize(("derived", "prior_value"), [(0.05, 0.9), (0.9, 0.05)],
                         ids=["thin_move_down", "thin_move_up"])
def test_ten_trades_cannot_move_a_money_path_number_either_way(derived: float,
                                                               prior_value: float) -> None:
    """The 2026-10-06 dry run: 10 live trades took ENTRY_DRIFT_TOL_FRAC to 0.05 against a
    prior-only 0.9. That move is held -- and so is its mirror image toward more aggression."""
    res = _solved(derived, 0.25, n=10, mean=-0.33467, sd=1.1)
    out = sgd.robustness_gate(res, prior_value, 0.25)
    assert out["adopt"] is False
    assert out["adopted_value"] == 0.25                 # the current value stays
    assert out["gate"]["verdict"] == "THIN_EVIDENCE" and out["gate"]["held"] is True
    mg = out["gate"]["missed_growth"]
    assert mg["held_value"] == 0.25 and mg["refused_value"] == derived
    assert mg["direction"] == ("down" if derived < 0.25 else "up")
    assert mg["claimed_delta_elog_per_day"] == pytest.approx(1.7e-4)


@pytest.mark.parametrize(("derived", "prior_value", "mean"),
                         [(0.05, 0.9, -0.40), (0.9, 0.05, 0.98)],
                         ids=["ample_move_down", "ample_move_up"])
def test_ample_evidence_adopts_in_either_direction(derived: float, prior_value: float,
                                                   mean: float) -> None:
    res = _solved(derived, 0.25, n=200, mean=mean, sd=1.0)    # ~9.8 SEs from the 0.29R prior
    out = sgd.robustness_gate(res, prior_value, 0.25)
    assert out["adopt"] is True and out["adopted_value"] == derived
    assert out["gate"]["verdict"] == "ADOPT" and out["gate"]["held"] is False
    assert "missed_growth" not in out["gate"]


@pytest.mark.parametrize(("derived", "prior_value", "mean"),
                         [(0.05, 0.9, 0.29 - 0.1), (0.9, 0.05, 0.29 + 0.1)],
                         ids=["noisy_move_down", "noisy_move_up"])
def test_a_move_inside_the_samples_noise_is_held_either_way(derived: float,
                                                            prior_value: float,
                                                            mean: float) -> None:
    # 40 trades clear the floor, but a 0.1R gap at sd 1.0 is 0.63 SEs: not a refutation.
    out = sgd.robustness_gate(_solved(derived, 0.25, n=40, mean=mean, sd=1.0), prior_value, 0.25)
    assert out["adopt"] is False and out["adopted_value"] == 0.25
    assert out["gate"]["verdict"] == "WITHIN_SAMPLING_UNCERTAINTY"
    assert out["gate"]["z"] == pytest.approx(0.1 / (1.0 / 40 ** 0.5), abs=1e-3)


def test_the_gate_holds_only_moves_the_live_ledger_made() -> None:
    # No move: nothing to hold. The certified prior's own answer: adopted, live n irrelevant.
    out = sgd.robustness_gate(_solved(0.25, 0.25, n=0, mean=None, sd=None), 0.9, 0.25)
    assert out["adopt"] is True and out["gate"]["verdict"] == "NO_MOVE"
    out = sgd.robustness_gate(_solved(0.9, 0.25, n=3, mean=0.1, sd=None), 0.9, 0.25)
    assert out["adopt"] is True and out["adopted_value"] == 0.9
    assert out["gate"]["verdict"] == "PRIOR_ANSWER"
    # Nothing solved: today stands and nothing is billed (there is no refused value).
    out = sgd.robustness_gate({"status": "UNMEASURED: x"}, None, 3.0)
    assert out["adopt"] is False and out["adopted_value"] == 3.0
    assert out["gate"]["held"] is False


def test_the_thresholds_are_the_desks_two_se_bar_and_a_thirty_trade_floor() -> None:
    assert sgd.MIN_LIVE_N == 30
    assert sgd.Z_ADOPT == sgd.TIE_SE == 2.0


def test_derive_reports_the_dry_runs_case_as_held(monkeypatch) -> None:
    """End to end through derive(): the live-moved 0.05 is reported adopt:false, 0.25 stands."""
    def drift(deals, prior_only=False, **_k):
        return (_solved(0.9, 0.25, n=0, mean=None, sd=None) if prior_only
                else _solved(0.05, 0.25, n=10, mean=-0.33467, sd=1.1))
    kept = {"status": "TODAY_OPTIMAL_WITHIN_NOISE", "derived": 3.0, "today": 3.0}
    monkeypatch.setattr(sgd, "derive_min_stop_spread_mult", lambda deals, **k: dict(kept))
    monkeypatch.setattr(sgd, "derive_entry_drift_tol_frac", drift)
    doc = sgd.derive()
    assert doc["ENTRY_DRIFT_TOL_FRAC"]["derived"] == 0.05        # the solve's answer, published
    assert doc["ENTRY_DRIFT_TOL_FRAC"]["adopt"] is False
    assert doc["adopted"] == {"MIN_STOP_SPREAD_MULT": 3.0, "ENTRY_DRIFT_TOL_FRAC": 0.25}
    assert doc["held"] == ["ENTRY_DRIFT_TOL_FRAC"]
    # ONE missed-growth line per constant, every pass: the hold billed, the non-hold a zero.
    lines = {x["constant"]: x for x in doc["missed_growth"]}
    assert lines["ENTRY_DRIFT_TOL_FRAC"]["verdict"] == "COSTS_GROWTH"
    assert lines["ENTRY_DRIFT_TOL_FRAC"]["value"] == pytest.approx(-1.7e-4)
    assert lines["ENTRY_DRIFT_TOL_FRAC"]["direction"] == "down"
    assert lines["MIN_STOP_SPREAD_MULT"]["verdict"] == "NOT_BINDING"
    assert lines["MIN_STOP_SPREAD_MULT"]["value"] == 0.0


def test_missed_growth_carries_every_held_move(tmp_path, monkeypatch) -> None:
    """The report's consumer: the daily missed-growth organ reads the gate's published lines."""
    import json
    from datetime import UTC, datetime

    import missed_growth as mg

    path = tmp_path / "STOP_GEOMETRY_DERIVATION.json"
    monkeypatch.setattr(mg, "STOP_GEOMETRY", path)
    assert mg.published_gate_lines()["verdict"] == mg.UNMEASURED      # absent: never a zero
    at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    held = sgd.robustness_gate(_solved(0.9, 0.25, n=10, mean=0.9, sd=1.1, delta=2e-4),
                               0.05, 0.25)                             # the upward thin move
    kept = sgd.robustness_gate(_solved(3.0, 3.0, n=0, mean=None, sd=None), 3.0, 3.0)
    doc = {"generated_at": at, "missed_growth": [
        sgd.gate_missed_growth_line("ENTRY_DRIFT_TOL_FRAC", held["gate"], at),
        sgd.gate_missed_growth_line("MIN_STOP_SPREAD_MULT", kept["gate"], at)]}
    path.write_text(json.dumps(doc), "utf-8")
    m = mg.published_gate_lines()
    assert m["verdict"] == mg.COSTS and m["n_held"] == 1
    assert m["value_logw_per_day"] == pytest.approx(-2e-4)
    assert m["by_direction"] == {"up": 1, "down": 0}
    doc["missed_growth"] = [sgd.gate_missed_growth_line("ENTRY_DRIFT_TOL_FRAC", kept["gate"], at)]
    path.write_text(json.dumps(doc), "utf-8")
    assert mg.published_gate_lines()["verdict"] == mg.NOT_BINDING
    doc["generated_at"] = "2026-01-01T00:00:00+00:00"           # stale: the gate's state unknown
    path.write_text(json.dumps(doc), "utf-8")
    assert mg.published_gate_lines()["verdict"] == mg.UNMEASURED


def test_the_daily_missed_growth_run_publishes_the_gate(tmp_path, monkeypatch) -> None:
    import missed_growth as mg
    monkeypatch.setattr(mg, "STOP_GEOMETRY", tmp_path / "absent.json")
    doc = mg.run(write=False)
    assert "stop_geometry_robustness_gate" in doc["published_gate_lines"]
