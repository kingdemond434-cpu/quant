"""R0104 capability ratchet -- the desk's own 0-10 score per aspect, and it may only rise.

These lock the four properties that decide whether the artifact is worth trusting, plus its
schema:

  A FALL IS FLAGGED WITH ITS CAUSE. A score that can drop quietly is not a standard, so a drop
  must name which component regressed, from what to what, out of which artifact -- including the
  DELETION case, where the measurement itself disappears.
  UNMEASURED IS NEITHER 0 NOR 10. The single most important property here: 0 manufactures a defect
  out of ignorance, 10 manufactures a capability out of it, and the second is how an all-green
  board hides an empty desk.
  A TRUNCATED MUTATION RUN IS NOT A STRENGTH READING. Otherwise the desk buys points by running
  LESS, which is the denominator trick with a stopwatch.
  THE HIGH-WATER MARK NEVER DECREASES. Across any sequence of readings, good or bad.
"""
from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.run_capability_ratchet import run

from libs.research.capability_ratchet import (
    ARTIFACT_PATH,
    ASPECT_KEYS,
    MEASURED,
    SCALE_MAX,
    UNMEASURED,
    fraction_component,
    graveyard_kills,
    read_capability,
)

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]

#: Every aspect the standing order names. This tuple may GROW; an aspect leaving it is a
#: capability the desk stopped being graded on, which is the deletion loophole one level up.
REQUIRED_ASPECTS = (
    "statistical_validation", "research_discipline", "risk_rails", "governance", "data_coverage",
    "execution_path", "self_improvement", "ops_autonomy", "alpha_output",
)

#: The artifact's contract with its readers. Pinned because a ratchet whose schema drifts silently
#: takes every consumer of the record with it -- and a KEY DISAPPEARING is the same deletion
#: loophole the marks themselves are protected against.
TOP_KEYS = frozenset({
    "_", "law", "generated", "status", "scale_max", "stall_days", "n_aspects", "n_measured",
    "n_unmeasured", "measured_mean", "first_recorded", "last_raise_at", "days_since_raise",
    "n_raises", "high_water", "component_high_water", "aspects", "defects", "flatlined",
    "raised", "unmeasured", "unmeasured_components",
})
ASPECT_FIELDS = frozenset({"key", "state", "score", "high_water", "movement", "cause",
                           "binding_constraint", "ceiling", "artifacts", "components"})
COMPONENT_FIELDS = frozenset({"key", "state", "score", "artifact", "detail", "constraint"})


def _desk() -> dict[str, Any]:
    """A synthetic desk with every artifact present and readable -- the all-measured baseline."""
    return {
        "data/mutation_score.json": {
            "bar": 0.9, "measured": "2026-08-01T00:00:00Z",
            "targets": [
                {"target": "libs/validation/stepwise.py", "kill_rate": 0.9, "total": 40},
                {"target": "libs/risk/gate.py", "kill_rate": 1.0, "total": 51},
                {"target": "libs/execution/staging.py", "kill_rate": 0.8, "total": 42},
            ]},
        "docs/research/test_suite_record.json": {"max_collected": 440, "at": "2026-08-05"},
        "docs/graveyard.md": "## banner\n\n## `a_thing` -- KILLED\n\n### b_thing -- KILLED\n",
        "data/strategy_coverage.json": {"n_hunted": 7, "n_families": 14, "n_thin": 6,
                                        "n_unhunted": 1},
        "data/gate0_readiness.json": {
            "n_ready": 3, "n_criteria": 6, "desk_owes": [], "principal_owes": [],
            "rows": [{"criterion": "ruin_rail_clear", "status": "READY", "detail": "clear",
                      "action": ""}]},
        "data/law_gate.json": {"n_fences": 10, "n_failed": 0, "failures": []},
        # 46 live defects clears the 32 rung of DEFECT_LADDER -> 4.0, so governance is NOT at
        # ceiling in the baseline: a fixture that starts at 10 cannot show a fall.
        "data/max_audit_report.json": {"ran": "2026-08-05", "live": ["d"] * 46, "by_scope": {}},
        "data/data_assets.json": {"counts": {"measured": 2, "assets": 46, "absent": 43},
                                  "deep": False},
        "data/exploration_status.json": {"n_fresh": 2, "n_organs": 6, "n_stale": 1, "n_dark": 3,
                                         "status": "DARK"},
        "docs/research/COVERAGE_RATCHET.json": {
            "measured": {"money_path_pct": 60.0, "money_path_statements": 740,
                         "repo_pct": 89.0}},
        "docs/research/recommendation_ledger.json": {"recommendations": [
            {"id": "R1", "status": "implemented"}, {"id": "R2", "status": "open"}]},
        "data/conversion_status.json": {"arrivals_7d": 10, "dispositions_7d": 5, "status": "OK",
                                        "backlog": 3, "oldest_backlog_age_days": 1.0},
        "data/organ_liveness.json": {"n_fresh": 19, "n_checked": 42, "status": "DARK",
                                     "never_produced": [], "stale": []},
        "data/organ_readiness.json": {"ready": 11, "not_ready": 0, "ts": "2026-08-05",
                                      "gate_ok": True},
        "data/promotion_queue.json": {"slots": {"occupied": 2, "cap": 12}, "n_candidates": 0},
        "data/promotion_gate.json": {"granted_rung": 1, "granted": "PAPER", "blocked_at_rung": 2,
                                     "n_closed": 0,
                                     "ladder": [{"rung": 1}, {"rung": 2}, {"rung": 3},
                                                {"rung": 4}]},
    }


def _build(root: Path, tree: dict[str, Any]) -> None:
    for rel, obj in tree.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj), "utf-8")


def _cycle(root: Path, at: datetime) -> dict[str, Any]:
    """One full organ run, persisted exactly as the script persists it."""
    rep = run(root, at)
    out = root / ARTIFACT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep), "utf-8")
    return dict(rep)


def _aspect(rep: dict[str, Any], key: str) -> dict[str, Any]:
    return next(a for a in rep["aspects"] if a["key"] == key)


class TestFallsAreFlaggedWithACause:
    def test_regression_names_the_component_the_artifact_and_both_numbers(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        assert _aspect(first, "governance")["score"] == 7.0

        tree["data/law_gate.json"] = {"n_fences": 10, "n_failed": 4, "failures": ["a"]}
        _build(tmp_path, tree)
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        assert second["status"] == "REGRESSED"
        gov = _aspect(second, "governance")
        assert gov["movement"] == "FELL"
        # the cause must be actionable on its own: component, both numbers, and the source file
        assert "law_fences_passing" in gov["cause"]
        assert "10.0 -> 6.0" in gov["cause"]
        assert "data/law_gate.json" in gov["cause"]
        assert [d["aspect"] for d in second["defects"]] == ["governance"]

    def test_a_measurement_that_disappears_is_scored_as_a_fall_not_as_neutral(self, tmp_path):
        # DELETION IS WEAKENING (libs/doctrine/ratchet.py): deleting the evidence would otherwise
        # be the trivial way around the whole mechanism.
        tree = _desk()
        _build(tmp_path, tree)
        _cycle(tmp_path, NOW)

        (tmp_path / "data/law_gate.json").unlink()
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        gov = _aspect(second, "governance")
        assert second["status"] == "REGRESSED"
        assert gov["movement"] == "FELL"
        assert "law_fences_passing" in gov["cause"]
        assert "UNMEASURED" in gov["cause"] or "WENT DARK" in gov["cause"]
        # and it is NOT scored as zero: the surviving component still carries the aspect
        assert gov["score"] == 4.0

    def test_whole_aspect_going_dark_is_a_defect_carrying_its_last_mark(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        assert _aspect(first, "data_coverage")["state"] == MEASURED

        (tmp_path / "data/data_assets.json").unlink()
        (tmp_path / "data/exploration_status.json").unlink()
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        dc = _aspect(second, "data_coverage")
        assert second["status"] == "REGRESSED"
        assert dc["movement"] == "WENT-DARK"
        assert dc["state"] == UNMEASURED
        assert dc["score"] is None                  # NOT zero, even while failing
        assert dc["high_water"] == 1.8              # the record it went dark from
        assert "data/data_assets.json" in dc["cause"]

    def test_a_flatline_names_the_binding_constraint_rather_than_saying_nothing(self, tmp_path):
        _build(tmp_path, _desk())
        _cycle(tmp_path, NOW)
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        assert second["status"] == "FLATLINE"
        assert len(second["flatlined"]) == len(ASPECT_KEYS)
        for row in second["flatlined"]:
            # "what is stopping this from being one point higher" -- quantified, in real units
            assert "buys the next point" in row["binding_constraint"] or "10/10" in \
                row["binding_constraint"]

    def test_no_raise_for_a_week_is_itself_a_defect(self, tmp_path):
        _build(tmp_path, _desk())
        _cycle(tmp_path, NOW)
        assert _cycle(tmp_path, NOW + timedelta(days=3))["status"] == "FLATLINE"
        stalled = _cycle(tmp_path, NOW + timedelta(days=8))
        assert stalled["status"] == "STALLED"
        assert stalled["days_since_raise"] == 8.0


class TestUnmeasuredIsNeitherZeroNorTen:
    def test_an_empty_desk_scores_nothing_at_all(self, tmp_path):
        rep = _cycle(tmp_path, NOW)          # no artifacts written whatsoever

        assert rep["n_measured"] == 0
        assert rep["n_unmeasured"] == len(ASPECT_KEYS)
        assert rep["measured_mean"] is None          # never 0.0, never 10.0
        assert rep["high_water"] == {}               # ignorance sets no record
        for a in rep["aspects"]:
            assert a["state"] == UNMEASURED
            assert a["score"] is None
            assert a["movement"] == UNMEASURED
            for c in a["components"]:
                assert c["state"] == UNMEASURED
                assert c["score"] is None

    def test_absent_artifacts_never_reach_the_defect_list_either(self, tmp_path):
        rep = _cycle(tmp_path, NOW)
        # unmeasured is not a fall: there is nothing to have fallen FROM on a first reading
        assert rep["defects"] == []
        assert len(rep["unmeasured"]) == len(ASPECT_KEYS)
        assert all(u["why"] for u in rep["unmeasured"])          # the reason is always carried

    def test_zero_over_zero_is_unmeasured_not_full_marks(self):
        # "0 of 0 organs are stale" is an empty desk, not a healthy one -- the shape in which
        # unmeasured most often tries to pass itself off as perfect.
        c = fraction_component("x", "data/x.json", 0.0, 0.0, unit="organs", detail="")
        assert c.state == UNMEASURED
        assert c.score is None

    def test_an_idle_finder_does_not_read_as_a_perfect_fixer(self, tmp_path):
        tree = _desk()
        tree["data/conversion_status.json"] = {"arrivals_7d": 0, "dispositions_7d": 0,
                                               "status": "OK"}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        flow = next(c for c in _aspect(rep, "self_improvement")["components"]
                    if c["key"] == "conversion_flow_7d")
        assert flow["state"] == UNMEASURED
        assert flow["score"] is None

    def test_a_measured_zero_is_still_allowed(self, tmp_path):
        # the honesty rule cuts both ways: the desk really has promoted nothing, and 0.0 is the
        # honest reading of that -- it must NOT be laundered into UNMEASURED.
        tree = _desk()
        tree["data/promotion_gate.json"] = {"granted_rung": 0, "ladder": [{"rung": 1},
                                                                         {"rung": 4}]}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        rung = next(c for c in _aspect(rep, "alpha_output")["components"]
                    if c["key"] == "promotion_rung")
        assert rung["state"] == MEASURED
        assert rung["score"] == 0.0


class TestTruncatedMutationIsNotStrength:
    def test_a_truncated_target_is_excluded_from_the_score_and_named_unmeasured(self, tmp_path):
        tree = _desk()
        tree["data/mutation_score.json"] = {"bar": 0.9, "targets": [
            {"target": "libs/risk/sizing.py", "kill_rate": 0.5, "total": 29},
            {"target": "libs/risk/gate.py", "kill_rate": 1.0, "total": 4, "n_sites": 137,
             "budget_truncated": True},
        ]}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)

        comps = {c["key"]: c for c in _aspect(rep, "risk_rails")["components"]}
        # 5.0 from the complete run alone -- never 7.5 (averaged in) and never 10.0
        assert comps["mutation_kill_risk_stack"]["score"] == 5.0
        truncated = comps["mutation_kill_risk_stack::gate.py"]
        assert truncated["state"] == UNMEASURED
        assert truncated["score"] is None
        assert "BUDGET-TRUNCATED" in truncated["detail"]

    def test_all_targets_truncated_leaves_the_component_unmeasured(self, tmp_path):
        tree = _desk()
        tree["data/mutation_score.json"] = {"bar": 0.9, "targets": [
            {"target": "libs/risk/gate.py", "kill_rate": 1.0, "budget_truncated": True},
        ]}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)

        comps = {c["key"]: c for c in _aspect(rep, "risk_rails")["components"]}
        stack = comps["mutation_kill_risk_stack"]
        assert stack["state"] == UNMEASURED
        assert stack["score"] is None

    def test_the_equivalence_adjusted_rate_wins_where_the_register_applies(self, tmp_path):
        # same reading rule as scripts/check_ratchets.py:82 -- two organs on one artifact must not
        # disagree about what its numbers mean
        tree = _desk()
        tree["data/mutation_score.json"] = {"bar": 0.9, "targets": [
            {"target": "libs/risk/gate.py", "kill_rate": 0.8, "adjusted_kill_rate": 1.0,
             "equivalent_mutants": 7, "total": 42},
        ]}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        comps = {c["key"]: c for c in _aspect(rep, "risk_rails")["components"]}
        assert comps["mutation_kill_risk_stack"]["score"] == 10.0


class TestTheMarkNeverDecreases:
    def test_high_water_is_monotone_across_a_degrading_sequence(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        seen: list[dict[str, float]] = [dict(_cycle(tmp_path, NOW)["high_water"])]

        for day, ready in enumerate([5, 2, 6, 1, 4], start=1):
            tree["data/gate0_readiness.json"] = {
                "n_ready": ready, "n_criteria": 6,
                "rows": [{"criterion": "ruin_rail_clear", "status": "READY", "detail": "clear"}]}
            _build(tmp_path, tree)
            seen.append(dict(_cycle(tmp_path, NOW + timedelta(days=day))["high_water"]))

        for prev, cur in itertools.pairwise(seen):
            for key, mark in prev.items():
                assert cur[key] >= mark, f"{key} mark fell {mark} -> {cur[key]}"
        # and the mark holds the best ever seen: 6/6 ready was reached on day 3
        gate0 = seen[-1]["execution_path"]
        assert gate0 >= seen[3]["execution_path"]

    def test_a_component_mark_holds_even_when_the_aspect_mean_rises(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        assert first["component_high_water"]["governance.law_fences_passing"] == 10.0

        # governance trades a collapsed fence set for a clean audit: the MEAN could rise while a
        # component regressed, and the ratchet must still call that a fall.
        tree["data/law_gate.json"] = {"n_fences": 10, "n_failed": 5}
        tree["data/max_audit_report.json"] = {"live": [], "ran": "x"}      # 0 defects -> 10.0
        _build(tmp_path, tree)
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        assert second["component_high_water"]["governance.law_fences_passing"] == 10.0
        assert _aspect(second, "governance")["movement"] == "FELL"

    def test_deleting_the_record_is_visible_rather_than_silent(self, tmp_path):
        _build(tmp_path, _desk())
        first = _cycle(tmp_path, NOW)
        (tmp_path / ARTIFACT_PATH).unlink()
        second = _cycle(tmp_path, NOW + timedelta(days=1))
        # the marks are gone -- the honest signal is first_recorded restarting, and the script
        # prints NO PRIOR RECORD FOUND on exactly this branch
        assert second["first_recorded"] != first["first_recorded"]
        assert second["n_raises"] == 1


class TestSchemaIsStable:
    def test_top_level_keys_are_exactly_these(self, tmp_path):
        _build(tmp_path, _desk())
        rep = _cycle(tmp_path, NOW)
        assert set(rep) == TOP_KEYS

    def test_every_aspect_and_component_carries_the_same_fields(self, tmp_path):
        _build(tmp_path, _desk())
        rep = _cycle(tmp_path, NOW)
        assert [a["key"] for a in rep["aspects"]] == list(ASPECT_KEYS)
        for a in rep["aspects"]:
            assert set(a) == ASPECT_FIELDS
            assert a["artifacts"], f"{a['key']} cites no artifact"
            for c in a["components"]:
                assert set(c) == COMPONENT_FIELDS
                assert c["artifact"] and c["constraint"]

    def test_the_aspect_list_covers_every_named_aspect(self):
        assert set(REQUIRED_ASPECTS) <= set(ASPECT_KEYS)

    def test_an_empty_desk_keeps_the_same_schema(self, tmp_path):
        rep = _cycle(tmp_path, NOW)          # the UNMEASURED path must not change the shape
        assert set(rep) == TOP_KEYS
        for a in rep["aspects"]:
            assert set(a) == ASPECT_FIELDS

    def test_graveyard_entries_are_counted_and_banners_are_not(self):
        text = ("## SECTION BANNER (with prose)\n"
                "## `libs/x/` Thing -- RETIRED\n"
                "### some_hypothesis -- KILLED\n"
                "## CROSS-ERA SYNTHESIS -- the barrier migrates\n")
        assert graveyard_kills(text) == 2


class TestAgainstTheRealDesk:
    def test_the_live_tree_scores_without_crashing_and_stays_in_scale(self):
        # the artifacts this reads are written by other organs and change daily; a shape change
        # that broke the scorer would otherwise surface as a red cron at 06:20 rather than here
        aspects = read_capability(REPO)
        assert [a.key for a in aspects] == list(ASPECT_KEYS)
        for a in aspects:
            if a.state == MEASURED:
                assert a.score is not None
                assert 0.0 <= a.score <= SCALE_MAX
                assert a.binding_constraint
            else:
                assert a.score is None
            for c in a.components:
                assert (c.score is None) == (c.state == UNMEASURED)
