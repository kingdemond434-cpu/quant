"""The invariance test itself, and the one place a causal label changes anything (Tier-1 B16).

Two halves, and the second is the one the ledger's gap was about: a statistic nothing consumes is
a report. The wiring assertions are therefore as load-bearing as the maths.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import causal_invariance as ci  # type: ignore[import-not-found]  # noqa: E402


def _labels(n_per: int, names: tuple[str, ...]) -> list[str]:
    return [nm for nm in names for _ in range(n_per)]


def test_a_stable_effect_reads_invariant() -> None:
    """The same effect in every environment, plus symmetric noise: the dispersion is exactly what
    relabelling produces, so the permutation null cannot reject it."""
    names = ("asia", "london", "ny")
    labels = _labels(40, names)
    # A deterministic zig-zag rather than a random draw: the test must give the same verdict on
    # every machine and every run, and a seeded RNG here would hide a real regression behind a
    # lucky seed.
    eff = [0.001 + (0.0004 if i % 2 else -0.0004) for i in range(len(labels))]
    r = ci.invariance(eff, labels, seed=1, n_perm=200)
    assert r["status"] == "OK"
    assert r["invariant"] is True, r["why"]
    assert r["sign_stability"] == pytest.approx(1.0)
    assert r["n_env"] == 3


def test_an_environment_specific_fit_reads_non_invariant() -> None:
    """The whole edge lives in one environment and the other two are flat. That is exactly the
    shape a curve fitted to the dominant regime has, and the permutation null rejects it."""
    names = ("asia", "london", "ny")
    labels = _labels(40, names)
    eff = [(0.01 if lab == "london" else 0.0) + (0.0002 if i % 2 else -0.0002)
           for i, lab in enumerate(labels)]
    r = ci.invariance(eff, labels, seed=1, n_perm=400)
    assert r["status"] == "OK"
    assert r["invariant"] is False, r["why"]
    assert r["p_excess"] < ci.ALPHA


def test_a_sign_flip_is_non_invariant_on_its_own() -> None:
    """A magnitude that wanders is a sizing problem; a SIGN that flips is a different strategy in
    each environment, and it binds separately from the permutation test."""
    names = ("2022", "2023", "2024", "2025")
    labels = _labels(40, names)
    eff = [(0.004 if lab in ("2022", "2023") else -0.004) for lab in labels]
    r = ci.invariance(eff, labels, seed=1, n_perm=200)
    assert r["sign_stability"] == pytest.approx(0.5)
    assert r["sign_stability"] < ci.SIGN_MIN
    assert r["invariant"] is False


def test_too_few_environments_is_unmeasured_never_a_pass() -> None:
    """L1.28a: absence never resolves to a clean verdict."""
    r = ci.invariance([0.001] * 20, ["asia"] * 20, seed=1, n_perm=20)
    assert r["status"] == "UNMEASURED" and "environments" in r["why"]
    assert "invariant" not in r, "an unmeasured axis must not publish a verdict"


def test_a_cell_with_no_signals_is_unmeasured(monkeypatch: Any) -> None:
    monkeypatch.setattr(ci, "_effects", lambda *_a, **_k: ([], [], "family fired no signal"),
                        raising=True)
    out = ci.judge_cell("XAUUSD", "nothing", {}, 1)
    assert out["verdict"] == "UNMEASURED" and out["n_signals"] == 0


def test_the_pair_index_takes_the_worst_verdict(tmp_path: Path, monkeypatch: Any) -> None:
    """A mechanism that is environment-specific on ONE of its instruments is environment-specific.
    Letting the best cell speak for the pair would turn the test into a search for the environment
    that agrees with it."""
    cells = [("EURUSD", "fam", {"a": 1}, 1), ("EURUSD", "fam", {"a": 2}, 1)]
    verdicts = {1: "INVARIANT", 2: "NON_INVARIANT"}
    monkeypatch.setattr(ci, "_cells", lambda: cells, raising=True)
    monkeypatch.setattr(ci, "judge_cell",
                        lambda s, f, p, side, **kw: {
                            "cell": ci.cell_key(s, f, p), "symbol": s, "family": f,
                            "verdict": verdicts[p["a"]], "broken_axes": ["year"], "why": "x"},
                        raising=True)
    doc = ci.build(budget_s=30)
    assert doc["by_pair"]["EURUSD|fam"]["verdict"] == "NON_INVARIANT"
    assert doc["counts"] == {"INVARIANT": 1, "NON_INVARIANT": 1}


def test_verdict_for_reads_the_artifact_and_absence_changes_nothing(
        tmp_path: Path, monkeypatch: Any) -> None:
    out = tmp_path / "CAUSAL_INVARIANCE.json"
    monkeypatch.setattr(ci, "OUT", out, raising=True)
    assert ci.verdict_for("EURUSD", "fam") is None
    out.write_text(json.dumps({"by_pair": {"EURUSD|fam": {"verdict": "NON_INVARIANT",
                                                          "broken_axes": ["year"], "why": "w"}}}),
                   encoding="utf-8")
    got = ci.verdict_for("EURUSD", "fam")
    assert got is not None and got["verdict"] == "NON_INVARIANT"
    assert ci.verdict_for("EURUSD", "other") is None


# ------------------------------------------------------------------------------ the wiring

def test_the_compiler_deprioritises_but_never_drops(monkeypatch: Any) -> None:
    """THE GAP THE LEDGER NAMED: a causal label must change something on the path a candidate
    travels. It changes ORDER and nothing else -- the same cells come out, one priority step
    later, carrying the verdict."""
    import miner_candidate_compiler as mcc  # type: ignore[import-not-found]

    monkeypatch.setattr(mcc, "_charts_with_bars", lambda _s: ["M15"], raising=True)
    cand = [{"symbol": "EURUSD", "family": "fam", "params": {}}]

    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: None, raising=True)
    clean = mcc.expand_axes(list(cand))

    monkeypatch.setattr(mcc, "_invariance",
                        lambda _s, _f: {"verdict": "NON_INVARIANT", "broken_axes": ["year"],
                                        "why": "the effect changes with year"}, raising=True)
    demoted = mcc.expand_axes(list(cand))

    assert len(demoted) == len(clean), "the gate dropped candidates; it may only reorder them"
    for a, b in zip(clean, demoted, strict=True):
        assert b["priority"] == a["priority"] + 1
        assert b["causal_invariance"]["verdict"] == "NON_INVARIANT"
        assert b["causal_invariance"]["broken_axes"] == ["year"]
    # An INVARIANT mechanism is not demoted: the gate is two-sided in the only currency it has.
    monkeypatch.setattr(mcc, "_invariance", lambda _s, _f: {"verdict": "INVARIANT"}, raising=True)
    kept = mcc.expand_axes(list(cand))
    for a, b in zip(clean, kept, strict=True):
        assert b["priority"] == a["priority"]


def test_the_refusal_carries_a_missed_growth_line() -> None:
    """GROWTH_GOVERNANCE: no new gate, veto, cap or shrink without its missed-growth ledger line.
    A deprioritisation is a refusal measured in hours, so it is registered and billed like any
    other rail."""
    import missed_growth as mg  # type: ignore[import-not-found]

    from libs.portfolio.rails import RAILS

    rail = next((r for r in RAILS if r.name == "causal_invariance"), None)
    assert rail is not None, "the invariance gate is not registered in libs/portfolio/rails.py"
    assert rail.measure in mg.MEASURES, f"{rail.measure} is not a measurement in missed_growth"
    out = mg.MEASURES[rail.measure](rail, {}, {})
    assert out["verdict"] in (mg.UNMEASURED, mg.NOT_BINDING, mg.EARNS, mg.COSTS, "SAMPLE")


def test_the_forward_lab_publishes_the_verdict_beside_the_certificate() -> None:
    """The second consumer: the field rides the forward row, where a reader comparing a
    certificate against its forward evidence will see it."""
    src = (_DESK / "research" / "forward_reconcile.py").read_text("utf-8")
    assert '"causal_invariance": _invariance_rows()' in src
    assert "def _invariance_rows(" in src


def test_the_sealed_judge_is_not_touched() -> None:
    """The four sealed files must not import, mention or be modified by this organ. An invariance
    gate that reached the gauntlet would be a bar inserted outside the policy (L1.60)."""
    src = (_DESK / "research" / "causal_invariance.py").read_text("utf-8")
    for sealed in ("external_gauntlet", "promoter", "allocator_proof", "state_admission"):
        assert f"import {sealed}" not in src, f"the organ imports the sealed {sealed}"
    for sealed_path in (_DESK / "scripts" / "external_gauntlet.py",
                        _DESK / "research" / "promoter.py",
                        _ROOT / "libs" / "portfolio" / "allocator_proof.py",
                        _ROOT / "libs" / "regime" / "state_admission.py"):
        assert sealed_path.exists(), f"{sealed_path} is not on this tree"
        text = sealed_path.read_text("utf-8")
        assert "causal_invariance" not in text, (
            f"{sealed_path.name} was modified to read the gate")


def test_the_organ_is_on_a_clock_with_a_layer() -> None:
    """LAWS 7, UNWIRED OR IDLE IS A DEFECT: a leg, a layer, an artifact."""
    from libs.research.layers import LEG_LAYER
    hc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("causal_invariance"' in hc
    assert '"causal_invariance": civ' in hc
    assert LEG_LAYER.get("causal_invariance") == "prediction"
