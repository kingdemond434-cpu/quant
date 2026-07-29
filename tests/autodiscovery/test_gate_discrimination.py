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

from libs.autodiscovery.validation import blocking_constant_gates, gate_discrimination


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
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "scripts/run_discovery.py").read_text("utf-8")
    assert "gate_discrimination" in src and "blocking_constant_gates" in src
    assert "PRINCIPAL ruling" in src, (
        "the output must say who owns the decision; silently relaxing the bar is forbidden")
