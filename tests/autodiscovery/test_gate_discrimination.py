"""GAP #71 -- telling "nothing was good enough" apart from "a gate vetoed everything".

`pbo` and `reality_check` are computed ONCE per campaign -- they are properties of the returns
matrix, not of any candidate -- and then applied as PER-CANDIDATE gates. When campaign PBO comes
in at 0.6159 against a 0.50 bar, that gate reads False for all 420 candidates regardless of
individual merit. The desk's own measurement: 420 tested, ZERO survivors, while the genuinely
per-candidate gates discriminated normally (walk_forward 58.1%, fragility 47.9%).

Zero survivors reads two ways, and they demand opposite responses -- generate better candidates,
or fix the gate. This instrumentation makes the difference visible.

IT DELIBERATELY DOES NOT FIX THE GATE. Converting a campaign veto into a rank lowers a
statistical bar, the register marks that as needing a principal ruling, and the standing research
directive is explicit: "Never reduce statistical standards. Only improve efficiency." Measuring
the mechanism is the part that can be done without a ruling.
"""

from __future__ import annotations

from libs.autodiscovery.validation import (
    blocking_constant_gates,
    counterfactual_survivors,
    gate_discrimination,
)


def _rows(n: int, **gates) -> list[dict[str, bool]]:
    """n candidates; each kwarg is a list of per-candidate outcomes or a constant."""
    return [{g: (v[i] if isinstance(v, list) else v) for g, v in gates.items()}
            for i in range(n)]


def test_a_gate_that_fails_everyone_is_flagged_constant() -> None:
    rows = _rows(20, pbo=False, walk_forward=[i % 2 == 0 for i in range(20)])
    d = gate_discrimination(rows)
    assert d["pbo"]["discriminates"] is False
    assert d["pbo"]["passed"] == 0
    assert "campaign-level verdict" in d["pbo"]["note"]
    assert d["walk_forward"]["discriminates"] is True


def test_the_real_shape_is_identified_end_to_end() -> None:
    """The desk's measured campaign: two constant vetoes beside gates that work fine."""
    n = 420
    rows = _rows(
        n,
        pbo=False,                                            # campaign PBO 0.6159 > 0.50
        reality_check=False,                                  # campaign RC p 0.4220
        walk_forward=[i < int(n * 0.581) for i in range(n)],   # 58.1% -- discriminates
        fragility=[i < int(n * 0.479) for i in range(n)],      # 47.9% -- discriminates
    )
    blocking = blocking_constant_gates(rows)
    assert set(blocking) == {"pbo", "reality_check"}
    d = gate_discrimination(rows)
    assert d["walk_forward"]["pass_rate"] == 0.581
    assert d["fragility"]["discriminates"] is True


def test_a_gate_that_passes_everyone_is_also_flagged() -> None:
    """The mirror failure: a gate wired to nothing looks identical to a gate nothing trips."""
    d = gate_discrimination(_rows(10, capacity=True))
    assert d["capacity"]["discriminates"] is False
    assert "not filtering" in d["capacity"]["note"]
    assert blocking_constant_gates(_rows(10, capacity=True)) == [], (
        "passing everything is a warning; only FAILING everything blocks promotion")


def test_healthy_campaign_reports_nothing_blocking() -> None:
    rows = _rows(50, dsr=[i % 3 == 0 for i in range(50)],
                 cpcv=[i % 5 != 0 for i in range(50)])
    assert blocking_constant_gates(rows) == []
    assert all(v["discriminates"] for v in gate_discrimination(rows).values())


def test_empty_input_is_not_a_finding() -> None:
    """No candidates means nothing measured -- it must not fabricate a blocking gate."""
    assert gate_discrimination([]) == {}
    assert blocking_constant_gates([]) == []


def test_single_candidate_is_honestly_uninformative() -> None:
    """With n=1 every gate is trivially constant, and the note must not overclaim."""
    d = gate_discrimination(_rows(1, pbo=False))
    assert d["pbo"]["n"] == 1
    assert d["pbo"]["discriminates"] is False


def test_discovery_surfaces_this_rather_than_reporting_a_bare_zero() -> None:
    """The runner that reports a zero-survivor campaign must say WHY, and say who may rule on it.

    2026-09-05: `scripts/run_discovery.py` went with the crypto desk. The claim is not withdrawn --
    it is about whatever runner reports a campaign result -- so this SKIPS rather than passing
    silently, and names the file the MT5 runner must satisfy when it takes over.
    """
    from pathlib import Path

    import pytest
    src_path = Path(__file__).resolve().parents[2] / "scripts/run_discovery.py"
    if not src_path.is_file():
        pytest.skip(
            "scripts/run_discovery.py is absent (deleted with the crypto desk). The MT5 campaign "
            "runner must still surface gate_discrimination + blocking_constant_gates and name the "
            "PRINCIPAL as the owner of any relaxation; re-point this fence at it.")
    src = src_path.read_text("utf-8")
    assert "gate_discrimination" in src and "blocking_constant_gates" in src
    assert "PRINCIPAL ruling" in src, (
        "the output must say who owns the decision; silently relaxing the bar is forbidden")


# ------------------------------------------------- gap #71: "do we get survivors if we lower it?"


def test_waiving_the_campaign_veto_promotes_nobody_on_the_real_shape() -> None:
    """THE ANSWER TO THE QUESTION, MECHANISED.

    The desk's measured campaign: pbo and reality_check reject 420/420 as campaign-level
    statistics applied per-candidate, while the genuinely per-candidate gates discriminate
    (walk_forward 58.1%, fragility 47.9%, cpcv 43.3%, capacity 43.3%, expected_value 40.2%) and
    SOLE-CAUSE FAILURES ARE EMPTY -- i.e. every candidate also fails something that does
    discriminate. Waiving the veto therefore promotes nobody; it only changes which failure gets
    reported first.
    """
    import random
    rates = {"walk_forward": 0.581, "fragility": 0.479, "cpcv": 0.433,
             "capacity": 0.433, "expected_value": 0.402}
    rng = random.Random(7)
    rows = []
    for _ in range(420):
        gs = list(rates)
        doomed = gs[rng.randrange(len(gs))]      # every candidate has at least one real weakness
        rows.append({**{g: (False if g == doomed else rng.random() < rates[g] / 0.85)
                        for g in gs},
                     "pbo": False, "reality_check": False})

    cf = counterfactual_survivors(rows, ["pbo", "reality_check"])
    assert cf["survivors"] == 0, "waiving a campaign veto must not conjure survivors"
    assert "promotes NOBODY" in cf["note"]
    assert cf["independent_estimate"] > cf["survivors"], (
        "observed BELOW the independent estimate is the signature of gates that measure "
        "genuinely different failure modes")


def test_a_real_survivor_is_reported_and_escalated_not_swallowed() -> None:
    """If waiving WOULD promote someone, that is a promotion-bar change and must say so."""
    rows = [{"pbo": False, "reality_check": False, "walk_forward": True, "cpcv": True}
            for _ in range(10)]
    cf = counterfactual_survivors(rows, ["pbo", "reality_check"])
    assert cf["survivors"] == 10
    assert "belongs to the principal" in cf["note"]


def test_positive_association_would_exceed_the_independent_estimate() -> None:
    """Pins the direction, because it is easy to state backwards -- and I did, first time.

    One latent quality driving every gate means the good candidates sweep all of them, so
    survivors EXCEED the independent estimate. That would mean the battery is largely one gate
    wearing five hats. The desk's real campaign shows the opposite.
    """
    import random
    rates = {"a": 0.581, "b": 0.479, "c": 0.433, "d": 0.433, "e": 0.402}
    rng = random.Random(7)
    rows = [{**{g: q < r for g, r in rates.items()}, "pbo": False}
            for q in (rng.random() for _ in range(420))]
    cf = counterfactual_survivors(rows, ["pbo"])
    assert cf["survivors"] > cf["independent_estimate"] * 5


def test_waiving_nothing_matches_the_true_survivor_count() -> None:
    rows = [{"a": True, "b": True}, {"a": True, "b": False}]
    assert counterfactual_survivors(rows, [])["survivors"] == 1


def test_empty_campaign_counterfactual_is_honest() -> None:
    cf = counterfactual_survivors([], ["pbo"])
    assert cf["survivors"] == 0 and "nothing to counterfact" in cf["note"]
