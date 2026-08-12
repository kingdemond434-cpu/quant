"""A clock could clear its pre-registered bar and nothing would happen.

MEASURED 2026-08-12. `run_paper_sleeve_forward` computes, per sleeve, the forward IC, the rows
added, the Holm bar it must clear and how many rows that needs -- then writes it to a file and
stops. A grep for anything CONSUMING a cleared bar found `publish_pipeline`, which counts resolved
sleeves for the dashboard, and nothing else. The desk could run a clock ninety days, watch it clear
the bar it was pre-registered against, and the sleeve would keep accruing while the survivor sat in
a JSON field until a person noticed.

These tests pin the two properties that make the resolver safe to run unattended: it cannot mint a
survivor cheaply, and it cannot mistake "could not measure" for "measured nothing".
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def res():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_forward_resolution", _REPO / "scripts/run_forward_resolution.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _desk(tmp_path: Path, sleeves: dict) -> Path:
    (tmp_path / "web").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "web/paper_sleeve_forward.json").write_text(
        json.dumps({"sleeves": sleeves}), "utf-8")
    return tmp_path


def _sleeve(*, ic: float, rows: float, needed: float = 100.0) -> dict:
    return {"ic_forward_estimate": ic, "rows_added": rows,
            "n_needed_for_forward_rejection": needed, "evidence": "ACCRUING"}


# ------------------------------------------------------------------ it must be hard to survive
def test_a_handful_of_rows_can_never_mint_a_survivor(res, tmp_path: Path) -> None:
    """THE ERROR THAT MATTERS HERE IS THE FALSE POSITIVE. A |t| computed on a few rows is a coin
    flip with a decimal point, and one lucky week must not be able to produce the desk's first
    survivor -- the number everything downstream would then be built on."""
    root = _desk(tmp_path, {"a": _sleeve(ic=0.9, rows=5)})
    d = res.resolve(root=root)
    assert d["n_survived"] == 0
    assert d["clocks"][0]["verdict"] == "ACCRUING"
    assert "coin flip" in d["clocks"][0]["why"]


def test_the_minimum_row_bar_is_not_trivially_small(res) -> None:
    assert res.MIN_FORWARD_ROWS >= 30.0


def test_a_real_effect_with_real_evidence_does_survive(res, tmp_path: Path) -> None:
    """The other half. A resolver that never resolves is the stall it was built to remove."""
    root = _desk(tmp_path, {"a": _sleeve(ic=0.5, rows=400)})
    d = res.resolve(root=root)
    assert d["n_survived"] == 1 and d["status"] == "SURVIVOR"
    c = d["clocks"][0]
    assert c["verdict"] == "SURVIVED" and c["t"] >= c["bar_z"]


def test_the_survivor_is_ledgered_the_moment_it_happens(res, tmp_path: Path) -> None:
    """The desk has never produced one. The first must not depend on anybody noticing a field."""
    root = _desk(tmp_path, {"a": _sleeve(ic=0.5, rows=400)})
    res.resolve(root=root)
    rows = [json.loads(x) for x in
            (root / res.LEDGER).read_text("utf-8").splitlines() if x.strip()]
    assert len(rows) == 1 and rows[0]["name"] == "a"
    assert rows[0]["resolved_utc"] and rows[0]["m_effective"] >= 1


# ------------------------------------------------------------------ Holm step-down
def test_the_descent_stops_at_the_first_failure(res, tmp_path: Path) -> None:
    """THE STOPPING RULE IS THE PROCEDURE. Holm tests the strongest at alpha/m and descends only
    while each rejects; carrying on past a failure would turn step-down into a licence and break
    the family-wise error rate the whole cohort is corrected for."""
    root = _desk(tmp_path, {
        "strong": _sleeve(ic=0.6, rows=400),
        "middling": _sleeve(ic=0.02, rows=400),
        "weak": _sleeve(ic=0.015, rows=400),
    })
    d = res.resolve(root=root)
    by = {c["name"]: c for c in d["clocks"]}
    assert by["strong"]["verdict"] == "SURVIVED"
    assert by["middling"]["verdict"] in ("ACCRUING", "UNDERPOWERED")
    assert by["weak"]["verdict"] == "ACCRUING"
    assert "step-down stops here" in by["weak"]["why"]


def test_ranks_are_assigned_strongest_first(res, tmp_path: Path) -> None:
    root = _desk(tmp_path, {"lo": _sleeve(ic=0.10, rows=400),
                            "hi": _sleeve(ic=0.60, rows=400)})
    d = res.resolve(root=root)
    by = {c["name"]: c for c in d["clocks"]}
    assert by["hi"]["holm_rank"] == 1 and by["lo"]["holm_rank"] == 2
    assert by["hi"]["bar_z"] >= by["lo"]["bar_z"], "rank 1 carries the strictest bar"


def test_the_rank_one_bar_is_never_looser_than_bonferroni(res, tmp_path: Path) -> None:
    """WHAT STEP-DOWN IS AND IS NOT. It buys nothing for the FIRST clock -- alpha/m either way --
    so it is not a shortcut to a survivor. It only means the SECOND real effect is not held to a
    bar built for the possibility that it was the only one."""
    from libs.validation.forward_stats import holm_bar
    root = _desk(tmp_path, {"a": _sleeve(ic=0.6, rows=400)})
    d = res.resolve(root=root)
    m = d["m_effective"]
    assert d["clocks"][0]["bar_z"] == pytest.approx(float(holm_bar(m, 1)))


# ------------------------------------------------------------------ unknown is never a negative
def test_underpowered_is_never_recorded_as_a_refutation(res, tmp_path: Path) -> None:
    """L1.49. A source that cannot supply the rows this bar needs has not shown the effect is
    absent -- it has shown the desk cannot see. Filing that as a negative poisons the graveyard
    with hypotheses nobody actually tested."""
    root = _desk(tmp_path, {"a": _sleeve(ic=0.01, rows=100, needed=50_000)})
    d = res.resolve(root=root)
    c = d["clocks"][0]
    assert c["verdict"] == "UNDERPOWERED"
    assert "not a refutation" in c["why"]
    assert "REFUTED" not in json.dumps(d["by_verdict"])
    assert "not evidence of absence" in d["unresolved_is_not_refuted"]


def test_a_sleeve_with_no_forward_ic_is_accruing_not_judged(res, tmp_path: Path) -> None:
    root = _desk(tmp_path, {"a": {"rows_added": 500, "evidence": "NO-EVIDENCE"}})
    d = res.resolve(root=root)
    assert d["clocks"][0]["verdict"] == "ACCRUING" and d["clocks"][0]["t"] is None


def test_an_absent_feed_is_no_survivor_not_a_crash(res, tmp_path: Path) -> None:
    d = res.resolve(root=tmp_path)
    assert d["status"] == "NO-SURVIVOR" and d["n_clocks"] == 0
    assert d["source"] == "ABSENT"


def test_no_survivor_is_reported_as_the_desks_state_not_an_organ_failure(res, tmp_path) -> None:
    root = _desk(tmp_path, {"a": _sleeve(ic=0.001, rows=400)})
    d = res.resolve(root=root)
    assert "honest state, not a failure of this organ" in d["why"]


# ------------------------------------------------------------------ what it may not do
def test_it_cannot_promote_anything_to_capital(res) -> None:
    """A SURVIVED verdict STARTS the live ladder; it does not bypass it. The promotion gate still
    applies every criterion it applies today."""
    src = (_REPO / "scripts/run_forward_resolution.py").read_text("utf-8")
    body = src.split('"""', 2)[2]
    for forbidden in ("live_authority", "book_fraction", "create_order", "MAX_FORWARD_SLOTS"):
        assert forbidden not in body, forbidden


def test_it_sets_no_threshold_of_its_own(res) -> None:
    """alpha and the bar come from libs.validation.forward_stats; m comes from
    forward_multiplicity. An organ that could pick its own bar is not a test."""
    src = (_REPO / "scripts/run_forward_resolution.py").read_text("utf-8")
    assert "holm_bar" in src and "alpha=" not in src.split('"""', 2)[2]


def test_the_t_statistic_is_not_inflated_by_a_sign(res) -> None:
    """|IC| is used, so a negative effect of the same magnitude is judged identically -- and a
    one-sided read of a two-sided family would be a hidden loosening."""
    assert res._t_stat(-0.5, 400) == res._t_stat(0.5, 400)
    assert res._t_stat(0.0, 400) == 0.0
    assert res._t_stat(float("nan"), 400) == 0.0
    assert not math.isnan(res._t_stat(0.5, 0))


# ------------------------------------------------------------------ wiring
def test_it_runs_before_the_actuator_in_the_same_cycle() -> None:
    """THE PRINCIPAL'S ACTUAL ASK: live immediately after shadow is done. If resolution ran after
    the actuator, a clock that survived would wait a full cycle for the gate to notice."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_pipeline_cycle", _REPO / "scripts/run_pipeline_cycle.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    order = [s[0] for s in m.STAGES]
    assert "run_forward_resolution.py" in order, "resolution runs nowhere"
    assert order.index("run_forward_resolution.py") < order.index("run_promotion_actuator.py")
    assert order.index("run_paper_sleeve_forward.py") < order.index("run_forward_resolution.py")


def test_a_survivor_pages_a_person(res) -> None:
    """The desk has never produced one. Nobody should find out from a dashboard refresh."""
    src = (_REPO / "scripts/run_forward_resolution.py").read_text("utf-8")
    assert "send_all" in src and "SURVIVOR" in src
