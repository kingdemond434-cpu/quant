"""Tests for the evaluator lab -- the Red Queen mechanism (principal, 2026-09-16).

THE LOAD-BEARING PAIR IN THIS FILE is `test_the_planted_edge_passes_the_standing_battery` against
`test_the_standing_roster_has_no_cost_adversary_and_the_lab_finds_one`. A lab whose controls do
not behave is not measuring discriminating power, it is measuring its own tape; and the second
test pins the finding the lab exists to produce -- a mechanism that is real in the sequence, real
in both halves, real in every year and worth less per trade than a round trip walks through all
four wrapped hostile tests untouched, because not one of them charges a cost.

Everything else here prosecutes the RULE rather than the arithmetic: keep needs power AND marginal
value, retire needs two strikes, the protected roster is exempt, disagreement survives into the
report, and no function in the module can be handed a sealed input.
"""
from __future__ import annotations

import inspect
import json
from typing import Any

import numpy as np
import pandas as pd
import pytest

from libs.validation import evaluator_lab as lab
from libs.validation.evaluator_lab import Attack, Control, Verdict
from libs.validation.hostile import BLOCK, REPORT

#: A parameter whose name contains any of these would be a hole in the immutable wall.
BANNED = ("lockbox", "forward", "fill", "live", "real_cost", "holdout", "oos", "broker")


@pytest.fixture(scope="module")
def bundle() -> tuple[Control, ...]:
    """The lab's own controls, seed 0. Deterministic: this is the immutable reality anchor."""
    return lab.controls_for(0)


@pytest.fixture(scope="module")
def roster() -> list[Attack]:
    return lab.battery(lab.seed_state())


def _stub(passes: set[str]) -> lab.AttackFn:
    """An attack that passes exactly the named controls, fails the rest, and is UNMEASURED when it
    is handed no control at all -- the three states a real verdict has."""
    def fn(evaluate: Any, bars: Any, *, marker: str = "", **_: Any) -> Verdict:
        if not marker:
            return Verdict(name="stub", passed=None, statistic=None, threshold=None, why="blind")
        return Verdict(name="stub", passed=marker in passes, statistic=1.0, threshold=0.5,
                       why="stub")
    return fn


_STUB_BARS = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})


def _stub_bundle() -> tuple[Control, ...]:
    def nil(_frame: pd.DataFrame) -> Any:
        raise AssertionError("a stub attack must never replay")
    return tuple(Control(n, k, nil, _STUB_BARS, {"marker": n}) for n, k in
                 (("planted_edge", lab.POSITIVE), ("neg_a", lab.NEGATIVE), ("neg_b", lab.NEGATIVE)))


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Control, ...]]:
    """Two seeds of a three-control stub world, plus the two stub families that see it."""
    monkeypatch.setitem(lab.FAMILIES, "sharp_stub", _stub({"planted_edge"}))
    monkeypatch.setitem(lab.FAMILIES, "blunt_stub", _stub({"planted_edge", "neg_a", "neg_b"}))
    monkeypatch.setitem(lab.FAMILIES, "half_stub", _stub({"planted_edge", "neg_a"}))
    monkeypatch.setitem(lab.GRID, "sharp_stub", {})
    return [_stub_bundle(), _stub_bundle()]


# ------------------------------------------------------------------------------ the sealed wall


def test_sealed_names_the_four_things_out_of_reach() -> None:
    assert lab.SEALED == ("lockbox", "forward_clock", "live_fills", "real_costs")


def test_no_function_in_the_module_accepts_a_sealed_argument() -> None:
    """The wall is enforced by the interface: there is no parameter to hand a sealed input to."""
    checked = 0
    members = [f for _n, f in inspect.getmembers(lab, inspect.isfunction)
               if getattr(f, "__module__", "") == lab.__name__]
    members += [lab.Attack.run, lab.Measurement.to_dict]
    for fn in members:
        checked += 1
        for param in inspect.signature(fn).parameters:
            low = param.lower()
            assert not any(b in low for b in BANNED), f"{fn.__qualname__} takes {param!r}"
    assert checked > 20, "the sweep must actually reach the module's functions"


# --------------------------------------------------------------------------- the controls behave


def test_every_control_looks_like_a_certificate(bundle: tuple[Control, ...]) -> None:
    """Ground truth: all six score positive expectancy on their own trade series. That is the
    whole difficulty -- an artefact nobody would believe is not a control."""
    assert [c.kind for c in bundle] == [lab.POSITIVE] + [lab.NEGATIVE] * 5
    for ctl in bundle:
        st = ctl.evaluate(ctl.bars)
        assert st.n >= 100 and st.expectancy > 0.0 and st.t_stat > 1.0, ctl.name


def test_the_planted_edge_passes_the_standing_battery(bundle: tuple[Control, ...],
                                                      roster: list[Attack]) -> None:
    ctl = bundle[0]
    assert ctl.name == "planted_edge"
    for attack in roster:
        v = attack.run(ctl.evaluate, ctl.bars, **ctl.context)
        assert v.passed is True, f"{attack.key} rejected the known-good edge: {v.why}"


def test_every_artefact_fails_at_least_one_attack_in_the_lab(bundle: tuple[Control, ...],
                                                             roster: list[Attack]) -> None:
    full = [*roster, Attack("cost_multiplier", {"cost_r": 0.05, "mult": 3.0})]
    for ctl in bundle[1:]:
        found = [a.key for a in full if a.run(ctl.evaluate, ctl.bars, **ctl.context).passed is
                 False]
        assert found, f"nothing in the lab catches {ctl.name}"


def test_the_standing_roster_has_no_cost_adversary_and_the_lab_finds_one(
        bundle: tuple[Control, ...], roster: list[Attack]) -> None:
    """The finding this module exists to produce, pinned so it cannot be lost by accident."""
    ctl = next(c for c in bundle if c.name == "uneconomic_edge")
    for attack in roster:
        v = attack.run(ctl.evaluate, ctl.bars, **ctl.context)
        assert v.passed is not False, f"{attack.key} was expected to let {ctl.name} through"
    cost = Attack("cost_multiplier", {"cost_r": 0.05, "mult": 3.0})
    assert cost.run(ctl.evaluate, ctl.bars, **ctl.context).passed is False


def test_an_attack_that_raises_is_unmeasured_and_never_a_pass() -> None:
    def boom(_ev: Any, _bars: Any, **_: Any) -> Verdict:
        raise RuntimeError("the tape was not quotable")
    lab.FAMILIES["boom_stub"] = boom
    try:
        v = Attack("boom_stub").run(lambda f: lab.stats_from_r([]), _STUB_BARS)
    finally:
        del lab.FAMILIES["boom_stub"]
    assert v.passed is None and "RuntimeError" in v.why


# ----------------------------------------------------------------------------------- the scoring


def test_power_is_the_gap_between_the_positive_and_negative_pass_rates(
        stubs: list[tuple[Control, ...]]) -> None:
    sharp = lab.measure(Attack("sharp_stub"), stubs)
    assert sharp.positive_rate == 1.0 and sharp.negative_rate == 0.0
    assert sharp.power == pytest.approx(1.0)
    assert sharp.caught == ("neg_a", "neg_b")
    blunt = lab.measure(Attack("blunt_stub"), stubs)
    assert blunt.power == pytest.approx(0.0) and blunt.caught == ()
    half = lab.measure(Attack("half_stub"), stubs)
    assert half.power == pytest.approx(0.5) and half.caught == ("neg_b",)


def test_power_is_none_when_the_attack_never_measures(
        stubs: list[tuple[Control, ...]]) -> None:
    """UNMEASURED leaves the denominator; it never becomes a pass, a fail or a zero (L1.28a)."""
    m = lab.measure(Attack("no_such_family"), stubs)
    assert m.power is None and m.positive_rate is None and m.caught == ()
    assert m.draws == 6, "it was asked six times and answered none of them"
    ok, why = lab.keep_decision(m, {"neg_a"})
    assert ok is False and "UNMEASURED" in why


def test_keep_needs_both_power_and_marginal_value(stubs: list[tuple[Control, ...]]) -> None:
    sharp = lab.measure(Attack("sharp_stub"), stubs)
    ok, why = lab.keep_decision(sharp, {"neg_b"})
    assert ok is True and "neg_b" in why
    ok, why = lab.keep_decision(sharp, set())
    assert ok is False and "no marginal value" in why
    half = lab.measure(Attack("half_stub"), stubs)
    assert lab.keep_decision(half, {"neg_b"}) == (False, "power 0.50 below the 0.60 keep floor")


# ------------------------------------------------------------------- the rule over two evaluations


def _blunt_row() -> dict[str, Any]:
    return {**lab._row(Attack("blunt_stub"), 0), "power_history": []}


def test_a_variant_is_kept_then_a_blunt_one_retired_over_two_generations(
        stubs: list[tuple[Control, ...]], monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any) -> None:
    """Generation 1 promotes the discriminating variant; generation 2 retires the blunt one on its
    second consecutive strike. The state travels through the persistence path, not a variable."""
    monkeypatch.setattr(lab, "STATE_PATH", tmp_path / "evaluator_lab.json")
    monkeypatch.setattr(lab, "REPORT_PATH", tmp_path / "EVALUATOR_LAB.json")
    lab._atomic(lab.STATE_PATH, {"at": "seed", "generation": 0, "battery": [_blunt_row()],
                                 "retired": []})

    s1, r1 = lab.run_generation(bundles=stubs, candidates=[Attack("sharp_stub")])
    assert r1["generation"] == 1
    assert r1["uncaught_negatives"] == ["neg_a", "neg_b"], "the blunt battery catches nothing"
    assert r1["kept_this_run"] == ["sharp_stub"] and r1["retired_this_run"] == []
    assert r1["candidates_evaluated"] == 1
    lab._atomic(lab.STATE_PATH, s1)
    assert {r["key"] for r in lab.load_state()["battery"]} == {"blunt_stub", "sharp_stub"}

    s2, r2 = lab.run_generation(bundles=stubs, candidates=[])
    assert r2["retired_this_run"] == ["blunt_stub"], "two strikes under 0.30 must retire it"
    assert [r["key"] for r in s2["battery"]] == ["sharp_stub"]
    assert r2["n_retired"] == 1 and r2["uncaught_negatives"] == []
    assert s2["retired"][0]["retired_generation"] == 2


def test_the_protected_roster_is_never_retired(stubs: list[tuple[Control, ...]]) -> None:
    """`delayed_entry` scores 0.25 by this metric and is the test that caught fifteen t-units."""
    row = {**lab._row(Attack("blunt_stub", {}, BLOCK, protected=True), 0),
           "power_history": [0.0, 0.0, 0.0]}
    state = {"generation": 4, "battery": [row], "retired": []}
    _s, rep = lab.run_generation(state=state, bundles=stubs, candidates=[])
    assert rep["retired_this_run"] == []
    assert rep["battery"][0]["power"] == 0.0, "its power is published, it is simply not acted on"


def test_retirement_needs_two_consecutive_strikes() -> None:
    assert lab._retire_decision([0.1, 0.1]) is True
    assert lab._retire_decision([0.9, 0.1]) is False
    assert lab._retire_decision([0.1]) is False
    assert lab._retire_decision([None, 0.1]) is False, "UNMEASURED is not a strike"


# ------------------------------------------------------------------------------------- the judge


def _const(passed: bool | None, severity: str = REPORT) -> lab.AttackFn:
    def fn(evaluate: Any, bars: Any, **_: Any) -> Verdict:
        return Verdict(name="const", passed=passed, statistic=1.0, threshold=0.5, why="const",
                       severity=severity)
    return fn


@pytest.fixture
def judges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(lab.FAMILIES, "yes_stub", _const(True))
    monkeypatch.setitem(lab.FAMILIES, "no_stub", _const(False, BLOCK))
    monkeypatch.setitem(lab.FAMILIES, "mute_stub", _const(None))


@pytest.mark.usefixtures("judges")
def test_judge_keeps_both_sides_of_a_disagreement() -> None:
    out = lab.judge(lambda f: lab.stats_from_r([]), _STUB_BARS,
                    attacks=[Attack("yes_stub"), Attack("no_stub"), Attack("mute_stub")])
    assert (out["n_passed"], out["n_failed"], out["n_unmeasured"]) == (1, 1, 1)
    assert {v["name"]: v["status"] for v in out["verdicts"]} == {
        "yes_stub": "PASS", "no_stub": "FAIL", "mute_stub": "UNMEASURED"}
    assert out["disagreements"] == [{"passed": "yes_stub", "failed": "no_stub"}]
    assert "disagreeing pair" in out["why"] and out["sealed"] == list(lab.SEALED)


@pytest.mark.usefixtures("judges")
def test_only_the_protected_roster_can_block() -> None:
    """An attack this lab evolved reports; only an inherited hostile severity withdraws a cell."""
    ev, bars = (lambda f: lab.stats_from_r([])), _STUB_BARS
    evolved = lab.judge(ev, bars, attacks=[Attack("no_stub", {}, BLOCK, protected=False)])
    assert evolved["blocking"] is False and evolved["n_failed"] == 1
    inherited = lab.judge(ev, bars, attacks=[Attack("no_stub", {}, BLOCK, protected=True)])
    assert inherited["blocking"] is True and inherited["blocked_by"] == ["no_stub"]


def test_judge_reads_the_battery_from_the_state_file(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Any) -> None:
    monkeypatch.setattr(lab, "STATE_PATH", tmp_path / "evaluator_lab.json")
    assert [a.key for a in lab.battery()] == [a.key for a in lab.battery(lab.seed_state())]
    lab._atomic(lab.STATE_PATH, {"generation": 9, "battery": [lab._row(Attack("permutation",
                                                                              {"block": 6}), 9)]})
    assert [a.key for a in lab.battery()] == ["permutation[block=6]"]


# ------------------------------------------------------------------------------- determinism / IO


def test_the_reality_anchor_is_deterministic_in_its_seed() -> None:
    a, basket_a = lab.synthetic_bars(seed=3, years=0.2)
    b, basket_b = lab.synthetic_bars(seed=3, years=0.2)
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_series_equal(basket_a, basket_b)
    other, _ = lab.synthetic_bars(seed=4, years=0.2)
    assert not np.allclose(a["close"].to_numpy(), other["close"].to_numpy())


def test_a_generation_is_reproducible_under_the_same_state_and_seeds(
        stubs: list[tuple[Control, ...]]) -> None:
    state = {"generation": 0, "battery": [_blunt_row()], "retired": []}
    when = pd.Timestamp("2026-09-16T12:00:00Z").to_pydatetime()
    first = lab.run_generation(state=state, bundles=stubs, now=when)
    second = lab.run_generation(state=state, bundles=stubs, now=when)
    assert json.dumps(first, default=str) == json.dumps(second, default=str)
    rng = np.random.default_rng
    assert ([a.key for a in lab.propose([_blunt_row()], set(), rng(7))]
            == [a.key for a in lab.propose([_blunt_row()], set(), rng(7))])


def test_propose_never_repeats_a_standing_or_retired_variant() -> None:
    rows = [lab._row(a, 0) for a in lab.battery(lab.seed_state())]
    out = lab.propose(rows, {"permutation[block=6]"}, np.random.default_rng(2))
    keys = [a.key for a in out]
    assert len(keys) == len(set(keys))
    assert "permutation[block=6]" not in keys
    assert not ({r["key"] for r in rows} & set(keys))
    assert all(a.family in lab.FAMILIES for a in out)


def test_cli_dry_run_prints_and_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    state, report = tmp_path / "state.json", tmp_path / "report.json"
    monkeypatch.setattr(lab, "STATE_PATH", state)
    monkeypatch.setattr(lab, "REPORT_PATH", report)
    monkeypatch.setattr(lab, "controls_for", lambda seed: _stub_bundle())
    monkeypatch.setitem(lab.FAMILIES, "blunt_stub", _stub({"planted_edge", "neg_a", "neg_b"}))
    monkeypatch.setattr(lab, "load_state", lambda path=None: {
        "generation": 0, "battery": [_blunt_row()], "retired": []})
    assert lab.main(["--dry-run", "--seeds", "2"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "generation 1" in out
    printed = json.loads(out.rsplit("\n", 2)[0])
    assert printed["rule"]["seeds"] == 2 and printed["generation"] == 1
    assert not state.exists() and not report.exists()


def test_cli_writes_both_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    state, report = tmp_path / "state.json", tmp_path / "EVALUATOR_LAB.json"
    monkeypatch.setattr(lab, "STATE_PATH", state)
    monkeypatch.setattr(lab, "REPORT_PATH", report)
    monkeypatch.setattr(lab, "controls_for", lambda seed: _stub_bundle())
    monkeypatch.setitem(lab.FAMILIES, "blunt_stub", _stub({"planted_edge", "neg_a", "neg_b"}))
    monkeypatch.setattr(lab, "load_state", lambda path=None: {
        "generation": 2, "battery": [_blunt_row()], "retired": []})
    assert lab.main(["--seeds", "2"]) == 0
    doc = json.loads(report.read_text("utf-8"))
    assert doc["generation"] == 3 and doc["n_battery"] >= 1
    assert set(doc) >= {"at", "generation", "n_battery", "n_retired", "candidates_evaluated",
                        "kept_this_run", "retired_this_run", "controls", "battery", "rule"}
    assert doc["controls"]["positive"]["planted_edge"]["pass_rate"] == 1.0
    assert doc["rule"]["sealed"] == list(lab.SEALED)
    assert json.loads(state.read_text("utf-8"))["generation"] == 3
    assert not list(tmp_path.glob("*.tmp*")), "the temp file must be renamed away"
