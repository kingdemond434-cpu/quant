"""The search burden: a beautiful nonsense formula with a perfect in-sample fit is refused by the
held-out evidence and the permutation null, every search is charged its effective trials into
the hash-chained ledger, and an interpretation is optional but always recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mathlab import burden as B  # noqa: E402
from mathlab import grammar as G  # noqa: E402
from mathlab.objects import MathObject, Panel, Variable  # noqa: E402

N = 4000


def _bars(rng: np.random.Generator, n: int = N) -> dict[str, np.ndarray]:
    ret = rng.normal(0.0, 0.001, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    return {"close": close, "open": close, "high": close * 1.0005, "low": close * 0.9995,
            "ret": ret, "range": np.abs(ret) * 2 + 1e-6, "body": ret,
            "activity": 100 + 10 * np.abs(rng.normal(0, 1, n)), "spread": np.full(n, 1e-4),
            "atr": np.abs(ret) * 3 + 1e-6, "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, n)),
            "flow": rng.normal(0, 1, n)}


def _panel(columns: dict[str, np.ndarray], epsilon: np.ndarray, target: str = "EURUSD") -> Panel:
    return Panel(target=target, times=np.arange(epsilon.size, dtype=np.int64) * 3600,
                 epsilon=epsilon, columns=columns,
                 meta={k: Variable(k, f"bars:{target}", "bars") for k in columns}, horizon="4")


@pytest.fixture
def real() -> tuple[Panel, MathObject]:
    """A residual that genuinely responds to the curvature of price, everywhere in the sample."""
    rng = np.random.default_rng(3)
    columns = _bars(rng)
    signal = G.evaluate(["z", ["curv", "close", 12], 240], columns, N)
    epsilon = 0.5 * np.nan_to_num(signal) + rng.normal(0.0, 1.0, N)
    obj = MathObject(kind="relationship", tradition="symbolic_regression",
                     expression=["curv", "close", 12], target="EURUSD", horizon="4")
    return _panel(columns, epsilon), obj


@pytest.fixture
def nonsense() -> tuple[Panel, MathObject]:
    """A column that equals the residual on the first 60% of the sample and noise after it, wrapped
    in a ten-node formula: in-sample it is perfect, out of sample it is nothing."""
    rng = np.random.default_rng(4)
    columns = _bars(rng)
    epsilon = rng.normal(0.0, 1.0, N)
    junk = np.where(np.arange(N) < int(N * 0.6), epsilon * 3 + rng.normal(0, 0.01, N),
                    rng.normal(0, 1, N))
    columns["junk"] = junk
    obj = MathObject(kind="relationship", tradition="symbolic_regression",
                     expression=["div", ["mul", ["rmean", ["abs", ["curv", "junk", 3]], 5],
                                         ["z", "junk", 8]], ["rstd", "junk", 12]],
                     target="EURUSD", horizon="4")
    return _panel(columns, epsilon), obj


def test_beautiful_nonsense_fails_held_out_and_permutation(nonsense):
    panel, obj = nonsense
    verdict = B.judge(obj, panel, distinct_forms=5000, lifetime_trials=1000,
                      rng=np.random.default_rng(1), permutations=60)
    assert obj.evidence.ic_in_sample > 0.6, "the trap was not planted"
    assert abs(obj.evidence.ic_held_out) < 0.1
    assert verdict.value < 0
    assert not verdict.passed and not obj.passed
    assert verdict.gates["value_positive"] is False
    assert verdict.gates["held_out_sign_agrees"] is False or \
        verdict.gates["permutation"] is False
    assert verdict.effective_trials == 6000
    assert obj.complexity["nodes"] == 10 and obj.complexity["parameters"] == 4


def test_a_real_relation_passes_with_its_evidence_recorded(real):
    panel, obj = real
    verdict = B.judge(obj, panel, distinct_forms=500, rng=np.random.default_rng(1),
                      permutations=60)
    assert verdict.passed and obj.passed
    assert obj.evidence.ic_held_out > 0.3
    assert obj.evidence.permutation_p is not None and obj.evidence.permutation_p <= B.P_MAX
    assert obj.evidence.era_stability is not None and obj.evidence.era_stability >= 0.6
    assert obj.evidence.perturbation_min_t is not None and obj.evidence.perturbation_min_t > 0
    assert obj.burden["rule"].startswith("value = held-out t")
    row = obj.to_row()
    assert row["evidence"]["n_test"] >= B.MIN_TEST_ROWS
    assert row["burden"]["effective_trials"] == 500


def test_the_three_terms_are_exactly_the_specification(real):
    panel, obj = real
    verdict = B.judge(obj, panel, distinct_forms=200, lifetime_trials=100,
                      rng=np.random.default_rng(1), permutations=20)
    expected = (verdict.evidence_t - B.complexity_penalty(obj) - B.trials_penalty(300)
                + verdict.prior_shift)
    assert verdict.value == pytest.approx(expected)
    assert B.trials_penalty(2) < B.trials_penalty(20) < B.trials_penalty(2000)
    assert B.effective_trials(10, 5) == 15 and B.effective_trials(0) == 1


def test_complexity_penalty_prefers_the_simpler_of_two_equal_fits():
    simple = MathObject(kind="relationship", tradition="t", expression=["z", "close", 24],
                        target="X")
    ornate = MathObject(kind="relationship", tradition="t",
                        expression=["add", ["z", "close", 24], ["mul", 0.0001,
                                                                 ["sqrt", ["abs", "ret"]]]],
                        target="X")
    assert B.complexity_penalty(ornate) > B.complexity_penalty(simple)
    assert ornate.complexity["mdl_bits"] > simple.complexity["mdl_bits"]


def test_formal_simplification_makes_equivalent_formulas_one_trial():
    a = MathObject(kind="law", tradition="t", expression=["add", ["z", "close", 24], 0.0],
                   target="X")
    b = MathObject(kind="law", tradition="t", expression=["add", 0.0, ["z", "close", 24]],
                   target="X")
    c = MathObject(kind="law", tradition="t", expression=["mul", 1.0, ["z", "close", 24]],
                   target="X")
    assert a.object_id == b.object_id == c.object_id
    assert a.canonical == "z(close, 24)"
    assert G.simplify(["neg", ["neg", "ret"]]) == "ret"
    assert G.simplify(["sub", "ret", "ret"]) == 0.0
    assert G.to_str(G.simplify(["mul", "ret", "close"])) == G.to_str(
        G.simplify(["mul", "close", "ret"]))
    assert G.simplify(["add", 2.0, 3.0]) == 5.0


def test_effective_trials_are_charged_to_the_hash_chained_ledger(tmp_path, monkeypatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        first = B.record_trials("spectral", distinct_forms=17, evaluated=40, target="EURUSD",
                                passed=2)
        second = B.record_trials("spectral", distinct_forms=5, evaluated=9, target="EURUSD",
                                 passed=0)
        assert first["status"] == "RECORDED" and second["status"] == "RECORDED"
        assert first["row_hash"] != second["row_hash"]
        ok, n = R.verify_trial_chain()
        assert ok and n == 2
        conn = R.connect()
        rows = conn.execute("SELECT method, params_json, symbol FROM trials_ledger").fetchall()
        conn.close()
        methods = {str(r["method"]) for r in rows}
        assert methods == {"mathlab:spectral"}
        params = json.loads(str(rows[0]["params_json"]))
        assert params["distinct_canonical_forms"] == 17
        assert params["expressions_evaluated"] == 40
    finally:
        R.set_path(None)


def test_interpretation_is_optional_but_always_recorded(real):
    panel, obj = real
    B.judge(obj, panel, distinct_forms=10, rng=np.random.default_rng(1), permutations=10)
    assert obj.interpretation.status in ("interpreted", "uninterpreted")
    assert obj.interpretation.rationale and obj.interpretation.falsifier
    assert obj.to_row()["interpretation"]["prior"] in (B.INTERPRETED_PRIOR,
                                                       B.UNINTERPRETED_PRIOR)
    named = MathObject(kind="mechanism", tradition="game_theory_ecology",
                       expression=["neg", ["z", "activity", 240]], target="EURUSD", horizon="4",
                       statement="month end rebalancing flow at the london close: hedging demand")
    reading = B.interpret(named, panel)
    if reading.status == "interpreted":
        assert reading.mechanism_id and reading.actor and reading.matched_on
        assert reading.prior == B.INTERPRETED_PRIOR
    else:
        assert "UNINTERPRETED" in reading.rationale and reading.prior == B.UNINTERPRETED_PRIOR
    blank = MathObject(kind="law", tradition="topology", expression=["curv", "close", 24],
                       target="EURUSD", horizon="4", statement="")
    plain = B.interpret(blank, panel)
    assert plain.status == "uninterpreted" and plain.prior == B.UNINTERPRETED_PRIOR


def test_cost_stress_reads_the_surface_and_names_what_it_cannot(tmp_path, real):
    panel, obj = real
    surface = tmp_path / "cost_surface.json"
    surface.write_text(json.dumps({
        "built_at": "2026-09-01", "symbols": {
            "EURUSD": {"tick_size": 1e-5,
                       "hours": {str(h): {"p50": 12.0} for h in range(24)}}}}), "utf-8")
    measured = B.cost_stress(obj, panel, 0.4, surface)
    # THE SURFACE IS IN POINTS: 12 points at a 1e-5 tick is 0.00012 in price, a fraction of the
    # panel's own median close, and a 0.4 IC on a unit-sd residual clears that round trip.
    assert measured["status"] == "MEASURED"
    assert measured["one_way_cost_price"] == pytest.approx(0.00012)
    assert measured["one_way_cost_frac"] == pytest.approx(0.00012 / measured["price"], rel=1e-3)
    assert measured["survives"] is True
    untickable = tmp_path / "no_tick.json"
    untickable.write_text(json.dumps({"symbols": {"EURUSD": {"hours": {"1": {"p50": 12.0}}}}}),
                          "utf-8")
    assert B.cost_fraction("EURUSD", untickable)[1].startswith("UNMEASURED")
    absent = B.cost_stress(obj, _panel(panel.columns, panel.epsilon, "XAUUSD"), 0.4, surface)
    assert absent["status"] == "UNMEASURED" and "XAUUSD" in absent["why"]
    missing = B.cost_fraction("EURUSD", tmp_path / "nowhere.json")
    assert missing[0] is None and missing[1].startswith("UNMEASURED")


def test_translation_to_the_trade_grammar_is_exact_or_refused():
    assert G.to_alpha_grammar(["curv", "close", 12]) == [
        "sub", ["delta", "close", 12], ["delay", ["delta", "close", 12], 12]]
    assert G.to_alpha_grammar(["z", "ret", 24]) == ["zscore", "ret", 24]
    assert G.to_alpha_grammar(["gt", "ret", 0.5]) is None
    assert G.to_alpha_grammar(["log", "close"]) is None
    assert G.to_alpha_grammar(["mul", 2.0, "ret"]) is None
    assert G.to_alpha_grammar("macro_driver") is None
    expr, why = G.tradeable(["gt", ["z", "ret", 24], 1.0])
    assert expr is None and "gt" in why
    expr, why = G.tradeable(["mul", ["sign", ["diff", "close", 8]], ["z", "range", 120]])
    assert expr is not None and why == ""


def test_evaluation_is_causal_and_nan_on_warm_up():
    rng = np.random.default_rng(0)
    columns = _bars(rng, 600)
    lagged = G.evaluate(["lag", "close", 5], columns, 600)
    assert np.isnan(lagged[:5]).all()
    assert np.allclose(lagged[5:], columns["close"][:-5])
    curvature = G.evaluate(["curv", "close", 2], columns, 600)
    close = columns["close"]
    assert np.allclose(curvature[4:], close[4:] - 2 * close[2:-2] + close[:-4])
    absent = G.evaluate(["z", "not_a_column", 24], columns, 600)
    assert np.isnan(absent).all()
