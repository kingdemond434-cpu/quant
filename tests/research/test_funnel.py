"""SURVIVOR THROUGHPUT -- the tests are about not misdiagnosing zero.

Zero survivors has eight candidate explanations implying opposite actions, and "generate more" is
the default failure: cheapest to do, always feels productive, and exactly wrong when the blockage
is downstream. This desk owns the archetypal case -- ~900k enumerated candidates, 20,052
pre-registered trials, ZERO executed -- where the correct answer is EXECUTION and the comfortable
answer is a bigger generator.
"""

from __future__ import annotations

from libs.research.funnel import STAGES, Funnel, diagnose, render, throughput


def _f(**counts: int | None) -> Funnel:
    return Funnel(counts=dict(counts))


def _full(**over: int | None) -> Funnel:
    base: dict[str, int | None] = {
        "mined": 500, "hypotheses": 300, "novel_families": 120, "tested": 100,
        "net_positive": 20, "deflated": 6, "out_of_sample": 3, "independent": 2,
        "portfolio_positive": 1,
    }
    base.update(over)
    return Funnel(counts=base)


# ------------------------------------------------------------------ the desk's own case


def test_A_HUGE_QUEUE_WITH_ZERO_EXECUTED_DIAGNOSES_EXECUTION_NOT_HYPOTHESIS_QUALITY() -> None:
    """The desk's real state, and the diagnosis that decides the next month of work. Generating
    more is the cheapest action and grows the queue that IS the bottleneck."""
    d = diagnose(_f(mined=5000, hypotheses=898_560, novel_families=14_040, tested=0))
    assert d.blocked_at == "tested"
    assert d.blockage == "EXECUTION"
    assert "wrong one" in d.action and "queue backlogged" in d.action


def test_THE_STARVED_STAGES_ARE_NAMED_SO_THEIR_ZEROS_ARE_NOT_READ_AS_FINDINGS() -> None:
    """With nothing executed, the desk knows NOTHING about overfitting, costs or validation --
    inventing a verdict for them is a gate that never ran (L1.49)."""
    d = diagnose(_f(mined=5000, hypotheses=20_052, novel_families=900, tested=0))
    assert set(d.unmeasured_downstream) == set(STAGES[STAGES.index("tested") + 1:])
    assert any("starved by construction" in w for w in d.warnings)


def test_ZERO_OVER_ZERO_IS_UNDEFINED_NOT_A_ZERO_PERCENT_SURVIVOR_RATE() -> None:
    """An idle month and a failing method call for opposite responses, and 0% conflates them."""
    rate, per_month = throughput(_f(tested=0, independent=0))
    assert rate is None
    assert "UNMEASURED (no completed experiments)" in render(_f(tested=0, independent=0))
    assert per_month == 0.0, "with a real period, 0 survivors IS 0 per month -- that part is known"


# ---------------------------------------------------------------- earliest blockage wins


def test_THE_EARLIEST_EMPTY_STAGE_IS_THE_BINDING_ONE() -> None:
    """Later stages are starved by construction, so blaming one of them is blaming a symptom."""
    d = diagnose(_f(mined=0, hypotheses=0, novel_families=0, tested=0))
    assert d.blocked_at == "mined" and d.blockage == "INFORMATION"


def test_EACH_STAGE_BLAMES_ITSELF_WITH_AN_ACTION_THAT_DIFFERS_FROM_ITS_NEIGHBOURS() -> None:
    """The whole point is that the eight diagnoses imply DIFFERENT work. Identical advice would
    make the diagnostic decorative."""
    actions = {}
    for i, stage in enumerate(STAGES):
        counts = {s: (10 if j < i else 0) for j, s in enumerate(STAGES)}
        d = diagnose(Funnel(counts=counts))
        assert d.blocked_at == stage, f"expected {stage}, got {d.blocked_at}"
        actions[stage] = d.action
    assert len(set(actions.values())) == len(STAGES), "two stages give the same advice"


def test_A_FULLY_FLOWING_FUNNEL_REPORTS_NO_BLOCKAGE() -> None:
    d = diagnose(_full())
    assert d.blocked_at is None
    assert d.survivor_rate == 0.02
    assert d.survivors_per_month == 2.0


def test_COST_BLOCKAGE_SENDS_THE_DESK_TO_LIQUIDITY_AND_HORIZON_FIRST() -> None:
    """WS-006: an edge that survives only in the tightest names is a liquidity finding, and
    chasing signal quality there spends a cycle on the wrong hypothesis."""
    d = diagnose(_full(net_positive=0, deflated=0, out_of_sample=0, independent=0,
                       portfolio_positive=0))
    assert d.blocked_at == "net_positive" and d.blockage == "COSTS"
    assert "WS-006" in d.action and "turnover" in d.action


def test_REDUNDANCY_IS_DISTINGUISHED_FROM_HAVING_NO_SURVIVORS() -> None:
    """Survivors that collapse to one mechanism are inventory, not discovery -- a different
    problem from having none, and it wants orthogonality rather than volume."""
    d = diagnose(_full(independent=0, portfolio_positive=0))
    assert d.blocked_at == "independent" and d.blockage == "REDUNDANCY"
    assert "inventory, not discovery" in d.action


# ----------------------------------------------------------------------- honesty guards


def test_AN_UNCOUNTED_STAGE_IS_UNMEASURED_AND_IS_NOT_TREATED_AS_A_BLOCKAGE() -> None:
    """A stage nobody instrumented cannot be diagnosed, and silently treating None as 0 would
    blame whichever stage the desk simply forgot to count."""
    d = diagnose(_f(mined=100, hypotheses=None, novel_families=50, tested=10,
                    net_positive=5, deflated=2, out_of_sample=1, independent=1,
                    portfolio_positive=1))
    assert d.blocked_at is None
    assert any("never counted" in w and "not zero" in w for w in d.warnings)


def test_A_FUNNEL_THAT_WIDENS_DOWNSTREAM_IS_REPORTED_AS_A_COUNTING_BUG() -> None:
    """Counting bugs in this direction manufacture throughput, so they are surfaced rather than
    clipped."""
    f = _full(deflated=999)
    assert any("cannot widen downstream" in w for w in f.inconsistencies)
    assert any("cannot widen downstream" in w for w in diagnose(f).warnings)


def test_THE_RENDER_STATES_THAT_THE_TARGET_ONLY_MEANS_ANYTHING_AT_FIXED_GATES() -> None:
    """A survivor count is trivially maximised by weakening a threshold. The sentence has to sit
    beside the number, because that is where the temptation is."""
    text = render(_full())
    assert "FIXED GATES" in text
    assert "trivially maximised by weakening" in text


def test_NOTHING_IN_THE_MODULE_REFERENCES_A_THRESHOLD() -> None:
    """Structural. The target is throughput SUBJECT TO fixed gates; a throughput optimiser that
    could see a threshold would eventually be pointed at it."""
    import inspect

    import libs.research.funnel as F

    src = inspect.getsource(F)
    for token in ("sr0", "alpha=", "p_value", "pvalue", "threshold =", "0.05"):
        assert token not in src, f"the funnel module references a gate parameter: {token!r}"
