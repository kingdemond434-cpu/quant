"""The organ that closes the allocator's own bottleneck, tested against artifacts that EXIST.

WHY THIS SUITE IS NOT OPTIONAL. In a fresh checkout data/ is empty, so this organ honestly reports
every subsystem as NEVER_EXECUTED -- and a derivation that crashes, returns nonsense, or silently
reports absence when data IS present would look identical. The desk has shipped that exact shape
before: an organ green in the container, dark in production, for six weeks. So every derivation is
exercised against a synthetic artifact with known contents and the arithmetic is checked, not just
the absence of an exception.

THE SECOND CLAIM UNDER TEST is the refusal. Absence must stay VISIBLE and COSTED without ever
becoming actionable, and a made-up basis must never enter the ranking with the standing of a
measurement.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.estimate_contributions as C

from libs.doctrine.contribution import Contribution


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A synthetic desk root with a real sqlite metrics db, wired into the organ's paths."""
    (tmp_path / "data").mkdir()
    (tmp_path / "docs").mkdir()
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "METRICS", tmp_path / "data/desk_metrics.db")
    monkeypatch.setattr(C, "REPORT", tmp_path / "data/contributions.json")
    monkeypatch.setattr(C, "HISTORY", tmp_path / "data/contributions_history.jsonl")
    return tmp_path


def _jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _table(db: Path, table: str, n: int) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as c:
        c.execute(f"create table if not exists {table} (i integer)")
        c.executemany(f"insert into {table} values (?)",  # noqa: S608 -- test fixture
                      [(i,) for i in range(n)])


# ------------------------------------------------------------------ the map must not drift


def test_the_source_map_agrees_with_the_allocator_that_consumes_it() -> None:
    """Two maps naming different artifacts for the same subsystem is a silent contradiction: the
    allocator reports a gap the organ believes it has filled, forever. Held as a test rather than
    an import because this organ must be able to say 'the allocator expects a number here and I
    could not compute one', which requires its own opinion about where the number lives."""
    import scripts.run_allocator as A
    theirs = {k: v[0] for k, v in A._INSTRUMENTS.items()}
    assert theirs == C.SOURCES, {
        k: (C.SOURCES.get(k), theirs.get(k))
        for k in set(C.SOURCES) | set(theirs) if C.SOURCES.get(k) != theirs.get(k)}


def test_every_subsystem_the_allocator_tracks_gets_a_contribution(desk) -> None:
    """A subsystem with no entry is invisible to P4's argmax -- not ranked low, ABSENT, which is
    the one state the ranking cannot report on."""
    import scripts.run_allocator as A
    cs = C.build()
    assert {c.subsystem for c in cs} == set(A.SUBSYSTEM_DERIVATIVES)


# ------------------------------------------------------------------ derivations that compute


def test_generation_measures_the_funnel_pass_rate(desk) -> None:
    """The one term the desk HAS observed: what fraction of candidates reach L4. BACKTEST because
    no candidate has ever traded, so the pass rate is real and its conversion to growth is not."""
    _jsonl(desk / "data/hypothesis_queue.jsonl",
           [{"stage": "L4"}] * 3 + [{"stage": "L2"}] * 7)
    c = C._research_generation()
    assert c.provenance == "BACKTEST" and c.n == 10
    assert c.value == pytest.approx(0.3 * C.LOGW_PER_LIVE_ALPHA_CYCLE)
    assert "3/10" in c.basis


def test_screening_is_scored_on_power_MINUS_false_positives(desk) -> None:
    """A screen judged on power alone is a screen that admits everything -- it would score
    perfectly by never rejecting. Both terms, or the metric rewards the failure mode."""
    (desk / "data/gauntlet_calibration.json").write_text(
        json.dumps({"power": 0.9, "false_positive_rate": 0.3, "n": 400}), "utf-8")
    c = C._research_screening()
    assert c.value == pytest.approx((0.9 - 0.3) * C.LOGW_PER_LIVE_ALPHA_CYCLE)

    # The same screen with NO false positives must score strictly higher. Asserted as a
    # comparison rather than a magnitude, because that is the property that stops the metric
    # rewarding a screen which admits everything.
    (desk / "data/gauntlet_calibration.json").write_text(
        json.dumps({"power": 0.9, "false_positive_rate": 0.0, "n": 400}), "utf-8")
    assert C._research_screening().value > c.value


def test_mining_uses_the_measured_closure_rate_not_the_level(desk) -> None:
    """P18: the LEVEL is a status line, the RATE is what compounds. Coverage sitting at 40% tells
    you nothing about whether resource spent on the miner buys anything."""
    (desk / "data/moat_mine.json").write_text(json.dumps({
        "cumulative_coverage": {"coverage_pct": 41.0},
        "closure": {"pct_per_run": {"rate": 0.5, "se": 0.05, "n": 12}}}), "utf-8")
    c = C._research_mining()
    assert c.n == 12
    assert c.value == pytest.approx(0.5 * C.LOGW_PER_LIVE_ALPHA_CYCLE)
    assert "pp/run" in c.basis


def test_mining_refuses_a_rate_from_too_few_observations(desk) -> None:
    """A slope through two points is not evidence, and this organ must not launder one into a
    contribution just because the field was present."""
    (desk / "data/moat_mine.json").write_text(json.dumps({
        "cumulative_coverage": {"coverage_pct": 41.0},
        "closure": {"pct_per_run": {"rate": 9.9, "se": 0.0, "n": 2}}}), "utf-8")
    c = C._research_mining()
    assert c.provenance == "NEVER_EXECUTED"
    assert "at least 3" in c.basis


def test_scheduler_is_the_one_LIVE_estimate_available_today(desk) -> None:
    """Its own throughput needs no counterfactual -- steps that ran over steps scheduled is
    directly observed. Worth having exactly because everything else on this desk needs one."""
    (desk / "data/cadence_state.json").write_text(
        json.dumps({"steps_run": 18, "steps_total": 20}), "utf-8")
    c = C._scheduler()
    assert c.provenance == "LIVE"
    assert c.value == pytest.approx(0.9 * C.LOGW_PER_LIVE_ALPHA_CYCLE)


def test_memory_is_valued_at_the_cost_of_a_cycle_not_the_value_of_an_alpha(desk) -> None:
    """Memory saves WORK; it does not create edge. Valuing avoided duplication at the price of a
    validated alpha would make the research-memory table the highest-contributing subsystem on
    the desk by a wide margin, which is obviously wrong and would misroute every marginal hour."""
    _table(desk / "data/desk_metrics.db", "research_memory", 50)
    c = C._memory()
    assert c.provenance == "PRIOR"
    assert c.value < 0.1 * C.LOGW_PER_LIVE_ALPHA_CYCLE
    assert "saves work, it does not create edge" in c.basis


def test_panel_novelty_is_SHADOW_because_nothing_downstream_validated_it(desk) -> None:
    """Self-assessed novelty is a real observation of the panel and NOT an observation of edge.
    Grading it LIVE would let the panel certify its own usefulness."""
    _jsonl(desk / "data/external_panel_log.jsonl",
           [{"novel": True}] * 2 + [{"novel": False}] * 6)
    c = C._llm_panel()
    assert c.provenance == "SHADOW"
    assert c.value == pytest.approx(0.25 * C.LOGW_PER_LIVE_ALPHA_CYCLE)
    assert "self-assessed" in c.basis


# ------------------------------------------------------------------ the refusals


def test_a_desk_that_has_never_traded_reports_absence_not_zero(desk) -> None:
    """THE ONE THAT MATTERS MOST. costs, execution and portfolio have no observations because
    nothing has ever traded. Reporting them as zero would route the marginal resource away from
    them forever on no evidence; reporting absence keeps them ranked and costed."""
    for c in (C._fills_backed("costs", "d", "x"), C._portfolio()):
        assert c.provenance == "NEVER_EXECUTED"
        assert c.n == 0
        assert c.actionable() is False
        # The invariant is that the basis SAYS WHY there is nothing, not that it uses any
        # particular word -- and that it refuses the zero reading explicitly.
        assert "No observation exists" in c.basis
        assert "silently assigning it zero" in c.basis


def test_an_absent_artifact_is_still_ranked_never_dropped(desk) -> None:
    """A subsystem excluded from the ranking is assigned zero, and zero is a far stronger claim
    than unmeasured. Twenty-five cycles of invisibility came from exactly this."""
    cs = C.build()
    assert len(cs) == len(C.SOURCES)
    assert all(c.basis.strip() for c in cs), "every contribution must carry an auditable basis"


def test_data_present_but_no_derivation_is_distinguished_from_no_data(desk) -> None:
    """Two different problems with two different fixes: one needs an organ to produce data, the
    other needs somebody to write the derivation. Collapsing them hides the cheaper of the two."""
    (desk / "docs/GAP_REGISTER.md").write_text("# gaps\n| a | b |\n", "utf-8")
    owed = C._generic("engineering")
    assert "derivation-owed" in owed.tags
    assert "EXISTS and holds data" in owed.basis
    missing = C._generic("capacity")
    assert "absent" in missing.tags


def test_no_derivation_ever_invents_a_plausible_number(desk) -> None:
    """An estimate with a made-up basis enters the ranking with the standing of a measurement and
    nothing downstream can tell them apart. Every zero-evidence contribution must be value 0.0
    with NEVER_EXECUTED, never a confident-looking guess."""
    for c in C.build():
        if c.provenance == "NEVER_EXECUTED":
            assert c.value == 0.0 and c.n == 0, c.subsystem


# ------------------------------------------------------------------ the artifact


def test_the_run_writes_an_artifact_that_names_the_residual_bottleneck(desk) -> None:
    """Read by the allocator, so a missing field is a law that cannot be enforced. The bottleneck
    string is what tells the desk whether the work is FILLING the table or narrowing it."""
    (desk / "data/cadence_state.json").write_text(
        json.dumps({"steps_run": 18, "steps_total": 20}), "utf-8")
    assert C.main() == 0
    rep = json.loads((desk / "data/contributions.json").read_text("utf-8"))
    assert rep["subsystems"] == len(C.SOURCES)
    assert rep["measured"] >= 1, "the scheduler estimate should compute from the state written"
    assert rep["bottleneck"]
    assert rep["ranked"][0]["rank"] == 1
    assert "never clear an action threshold" in rep["note"]


def test_history_is_append_only(desk) -> None:
    """The measured-count is a ratchet like every other coverage number here; a file rewritten
    each run has no trend, and a trend is the only thing that distinguishes progress from a
    standing gap."""
    C.main()
    n1 = len((desk / "data/contributions_history.jsonl").read_text("utf-8").strip().splitlines())
    C.main()
    n2 = len((desk / "data/contributions_history.jsonl").read_text("utf-8").strip().splitlines())
    assert n2 > n1


def test_a_corrupt_artifact_degrades_to_absence_rather_than_crashing(desk) -> None:
    """This organ runs in the cadence. A JSONDecodeError here takes down the cycle and every
    downstream step, to report one subsystem it could not read -- the blast radius has to match
    the failure."""
    (desk / "data/moat_mine.json").write_text("{not json at all", "utf-8")
    (desk / "data/gauntlet_calibration.json").write_text("\x00\x01", "utf-8")
    cs = C.build()
    assert len(cs) == len(C.SOURCES)
    assert isinstance(cs[0], Contribution)
