"""R0104 capability ratchet -- the desk's own 0-10 score per aspect, and it may only rise.

These lock the properties that decide whether the artifact is worth trusting, plus its schema:

  A FALL IS FLAGGED WITH ITS CAUSE. A score that can drop quietly is not a standard, so a drop
  must name which component regressed, from what to what, out of which artifact -- including the
  DELETION case, where the measurement itself disappears.
  UNMEASURED IS NEITHER 0 NOR 10. The single most important property here: 0 manufactures a defect
  out of ignorance, 10 manufactures a capability out of it, and the second is how an all-green
  board hides an empty desk. Every aspect must REFUSE when its artifacts are gone.
  A TRUNCATED MUTATION RUN IS NOT A STRENGTH READING, and a truncated file is not COVERED either.
  Otherwise the desk buys points by running LESS, which is the denominator trick with a stopwatch.
  THE HIGH-WATER MARK NEVER DECREASES. Across any sequence of readings, good or bad.
  MEASURING MORE IS NOT REGRESSING. Widening an aspect's component set lowers its mean while
  nothing got worse; that is WIDENED, it keeps the old mark, and it is not a defect. It cannot
  launder a real fall, because component marks are held per component.
  THE DESK-WIDE BINDING CONSTRAINT IS THE TRUE MINIMUM over MEASURED components -- an unmeasured
  component has no score to be the minimum of, and letting it win would bury every real defect.
"""
from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from scripts.run_capability_ratchet import run

from libs.research.capability_ratchet import (
    ARTIFACT_PATH,
    ASPECT_KEYS,
    MEASURED,
    SCALE_MAX,
    UNMEASURED,
    binary_component,
    fraction_component,
    graveyard_kills,
    read_capability,
)

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]

#: Every aspect the standing order names. This tuple may GROW; an aspect leaving it is a
#: capability the desk stopped being graded on, which is the deletion loophole one level up.
#: The second block is the MINOR surface -- the pager, the tape, the credentials, the pins. None
#: of it is glamorous and all of it has taken desks down; "every aspect" means these too.
REQUIRED_ASPECTS = (
    "statistical_validation", "research_discipline", "risk_rails", "governance", "data_coverage",
    "execution_path", "self_improvement", "ops_autonomy", "alpha_output",
    "alerting_pager", "cost_model_fidelity", "forward_clock_hygiene", "recorder_tape",
    "llm_seat_coverage", "dependency_environment", "knowledge_currency", "backup_dr",
    "mutation_breadth", "scheduler_integrity", "secret_permission_hygiene", "engineering_standard",
    "capital_utilisation", "source_resilience", "blind_spot_coverage",
    "constitutional_aggression", "ambition_discipline",
)

#: The artifact's contract with its readers. Pinned because a ratchet whose schema drifts silently
#: takes every consumer of the record with it -- and a KEY DISAPPEARING is the same deletion
#: loophole the marks themselves are protected against.
TOP_KEYS = frozenset({
    "_", "law", "generated", "status", "scale_max", "stall_days", "n_aspects", "n_measured",
    "n_unmeasured", "measured_mean", "first_recorded", "last_raise_at", "days_since_raise",
    "n_raises", "binding_constraint", "high_water", "component_high_water", "aspects", "defects",
    "flatlined", "raised", "widened", "unmeasured", "unmeasured_components",
})
ASPECT_FIELDS = frozenset({"key", "state", "score", "high_water", "movement", "cause",
                           "binding_constraint", "ceiling", "artifacts", "components"})
COMPONENT_FIELDS = frozenset({"key", "state", "score", "artifact", "detail", "constraint"})

#: The whole product is "what is stopping this from being one point higher", so every constraint
#: must be one of these shapes: a quantified step in the metric's own units, a statement that the
#: work is now HOLDING a ceiling, or a named imperative for the cases where the next point is not
#: a number. Prose that is none of these is a constraint nobody can act on.
ACTIONABLE = ("buys the next point", "10/10", "AT CEILING", "the whole remaining gap",
              "RESTART IT", "WIRE IT", "MEASURE IT", "ARM A CHANNEL", "RUN THE RECORDER",
              "PROVISION THE CREDENTIAL", "RECORD A DATED PROMOTION HISTORY",
              "RESTORE FROM THE BACKUP", "EXTEND RETENTION", "FIX THE LOG DIRECTORY")

#: EVERY ARTIFACT AN ASPECT READS, so "delete them all and it must refuse" is a table rather than
#: twenty-six near-identical tests. An aspect missing from this map is an aspect nobody proved
#: refuses, which is the failure mode the whole module exists to prevent.
ASPECT_SOURCES: dict[str, tuple[str, ...]] = {
    "statistical_validation": ("data/mutation_score.json", "data/calibration_status.json"),
    "research_discipline": ("docs/research/test_suite_record.json", "docs/graveyard.md",
                            "data/strategy_coverage.json", "data/mechanism_census.json",
                            "data/strategy_breadth.json"),
    "risk_rails": ("data/mutation_score.json", "data/gate0_readiness.json",
                   "data/sizing_derivation.json", "data/drill_report.json",
                   "data/organ_liveness.json"),
    "governance": ("data/law_gate.json", "data/max_audit_report.json",
                   "data/enforcement_matrix.json", "data/law_families.json",
                   "data/fence_yield.json"),
    "data_coverage": ("data/data_assets.json", "data/exploration_status.json",
                      "docs/research/data_provenance.json", "data/announcement_collector.json"),
    "execution_path": ("data/gate0_readiness.json", "docs/research/COVERAGE_RATCHET.json",
                       "data/mutation_score.json",
                       "docs/research/trade_forensics_latest.json"),
    "self_improvement": ("docs/research/recommendation_ledger.json", "data/conversion_status.json",
                         "data/instrumentation_coverage.jsonl", "data/instrumentation_chase.json"),
    "ops_autonomy": ("data/organ_liveness.json", "data/organ_readiness.json", "data/organ_er.json",
                     "data/kernel_log_status.json"),
    "alpha_output": ("data/promotion_queue.json", "data/promotion_gate.json"),
    "alerting_pager": ("data/alert_delivery.jsonl", "data/alert_canary_state.json"),
    "cost_model_fidelity": ("data/cost_hunt.json", "data/execution_economics.json",
                            "data/organ_liveness.json"),
    "forward_clock_hygiene": ("data/promotion_queue.json", "data/replacement_rate.json"),
    "recorder_tape": ("data/clock_provenance_status.json", "data/backup_status.json",
                      "docs/research/trade_forensics_latest.json"),
    "llm_seat_coverage": ("data/miner_runway.json",),
    "dependency_environment": ("data/max_audit_report.json", "data/utilisation.json"),
    "knowledge_currency": ("data/knowledge_engine.json", "data/trading_playbook.json",
                           "docs/desk_lessons.jsonl"),
    "backup_dr": ("data/backup_status.json", "data/organ_liveness.json"),
    "mutation_breadth": ("data/mutation_score.json", "docs/research/COVERAGE_RATCHET.json"),
    "scheduler_integrity": ("data/scheduler_manifest_report.json",),
    "secret_permission_hygiene": ("data/organ_readiness.json", "data/miner_runway.json",
                                  "data/max_audit_report.json"),
    "engineering_standard": ("data/build_standard.json", "data/mypy_ratchet.json",
                             "data/wiring_agent.json", "data/max_audit_report.json"),
    "capital_utilisation": ("data/utilisation.json",),
    "source_resilience": ("data/source_alternatives_report.json", "data/source_health.jsonl"),
    "blind_spot_coverage": ("data/blindspot_max.json",),
    "constitutional_aggression": ("docs/research/CONSTITUTION_RATCHET.json",
                                  "docs/research/LAW_COVERAGE.json"),
    "ambition_discipline": ("data/timidity_audit.json", "data/return_targeting.json"),
}


def _liveness_organs() -> list[dict[str, Any]]:
    """The per-organ roster. The cadence and tolerance live HERE, in check_organ_liveness's own
    artifact, because that is the organ that owns them -- the ratchet reads the verdict."""
    return [
        {"script": "scripts/run_drills.py", "state": "FRESH", "age_h": 2.0, "tolerance_h": 72.0,
         "artifacts": ["data/drill_report.json"]},
        {"script": "scripts/run_cost_hunt.py", "state": "STALE", "age_h": 113.1,
         "tolerance_h": 3.0, "artifacts": ["data/cost_hunt.json"]},
        {"script": "scripts/run_cost_identification.py", "state": "NEVER-PRODUCED", "age_h": None,
         "tolerance_h": 3.0, "artifacts": ["data/cost_surface.json"]},
        {"script": "scripts/run_moat_backup.py", "state": "FRESH", "age_h": 1.0,
         "tolerance_h": 72.0, "artifacts": ["data/backup_status.json"]},
    ]


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
        "data/calibration_status.json": {"n_forecasts": 10, "n_resolved": 4, "n_overdue": 0,
                                         "brier": 0.2, "status": "OK", "detail": "4/10 resolved"},
        "docs/research/test_suite_record.json": {"max_collected": 440, "at": "2026-08-05"},
        "docs/graveyard.md": "## banner\n\n## `a_thing` -- KILLED\n\n### b_thing -- KILLED\n",
        "data/strategy_coverage.json": {"n_hunted": 7, "n_families": 14, "n_thin": 6,
                                        "n_unhunted": 1},
        "data/mechanism_census.json": {
            "diversity": {"n_classes_occupied": 15, "n_classes_in_taxonomy": 20,
                          "n_candidates": 82, "diversity": 0.4232, "hhi": 0.1734,
                          "effective_classes": 8.463, "top_class": "price_continuation",
                          "top_class_share": 0.2927},
            "campaign_diversity": {"diversity": 0.1394}},
        "data/strategy_breadth.json": {"n_surfaces": 14, "unwidened_surfaces": [], "status": "OK",
                                       "breadth": {"state": "NOT-RUN"}},
        "data/gate0_readiness.json": {
            "n_ready": 3, "n_criteria": 6, "desk_owes": [], "principal_owes": [],
            "rows": [{"criterion": "ruin_rail_clear", "status": "READY", "detail": "clear",
                      "action": ""}]},
        "data/sizing_derivation.json": {"n_modules": 3, "n_unjustified": 0, "status": "OK",
                                        "detail": "43 constants, 0 underived"},
        "data/drill_report.json": {"at": "2026-08-05", "n_drills": 3, "passed": 3,
                                   "critical_drill_failures": 0},
        "data/law_gate.json": {"n_fences": 10, "n_failed": 0, "failures": []},
        # 46 live defects clears the 32 rung of DEFECT_LADDER -> 4.0, so governance is NOT at
        # ceiling in the baseline: a fixture that starts at 10 cannot show a fall. One of them is
        # a dependency defect and one a phantom-path defect, so the prefix-scoped counts (which
        # dependency_environment and secret_permission_hygiene read) are exercised too.
        "data/max_audit_report.json": {
            "ran": "2026-08-05", "by_scope": {"REPO": 46},
            "live": ([{"id": "dependency-absent", "msg": "psutil"},
                      {"id": "phantom-paths", "msg": "61 paths"}]
                     + [{"id": f"other-{i}", "msg": "x"} for i in range(44)])},
        "data/enforcement_matrix.json": {"counts": {"ENFORCED": 65, "STANDING": 2},
                                         "n_principles": 68, "n_fences": 93, "unenforced": []},
        "data/law_families.json": {"n_families": 6, "failing": [], "status": "OK",
                                   "n_laws_governed": 35, "detail": "6/6 enforced"},
        "data/fence_yield.json": {"n_fences": 10, "n_fired": 8, "n_quiet": 2, "n_never_run": 0,
                                  "status": "ALL-EARNING", "detail": "8/10 caught something"},
        "data/data_assets.json": {"counts": {"measured": 2, "assets": 46, "absent": 43},
                                  "deep": False},
        "data/exploration_status.json": {"n_fresh": 2, "n_organs": 6, "n_stale": 1, "n_dark": 3,
                                         "status": "DARK"},
        "docs/research/data_provenance.json": {
            "datasets": {f"d{i}.jsonl": {"source": "desk"} for i in range(8)}},
        "data/announcement_collector.json": {"source_errors": {"a": "HTTP 400", "b": "blocked"},
                                             "status": "DEGRADED", "detail": "2 sources failed",
                                             "median_latency_minutes": 1681.98},
        "docs/research/COVERAGE_RATCHET.json": {
            "measured": {"money_path_pct": 60.0, "money_path_statements": 740,
                         "repo_pct": 89.0},
            "money_path_files": ["libs/execution/binance_live.py",
                                 "libs/execution/binance_testnet.py",
                                 "libs/execution/binance_spot_live.py",
                                 "libs/execution/binance_spot_testnet.py",
                                 "libs/execution/staging.py"]},
        "docs/research/trade_forensics_latest.json": {
            "updated": "2026-08-05T03:20:08Z",
            "maker_fill": {"n_legs": 42, "maker_share": 0.429, "spot": 0.238, "fut": 0.619,
                           "target": 0.6},
            "fee_attribution": {"venue_commission": 1581.78, "attributed": 1570.28,
                                "unattributed": 11.5, "n_events": 9110, "scope": "futures only"},
            "execution_tape": {"taped": 531, "tape_days": 2404.91, "buffer_days": 25.06,
                               "window_margin_days": 11.06, "buffer_squeezing_window": False}},
        "docs/research/recommendation_ledger.json": {"recommendations": [
            {"id": "R1", "status": "implemented"}, {"id": "R2", "status": "open"}]},
        "data/conversion_status.json": {"arrivals_7d": 10, "dispositions_7d": 5, "status": "OK",
                                        "backlog": 3, "oldest_backlog_age_days": 1.0},
        "data/instrumentation_coverage.jsonl":
            '{"ts":"2026-08-05T13:15:25Z","coverage_pct":10.0,"instrumented":2,"owed":18}\n',
        "data/instrumentation_chase.json": {"updated": "2026-08-05T13:15:25Z",
                                            "cycles_owed": {f"g{i}": i for i in range(18)}},
        "data/organ_liveness.json": {"n_fresh": 19, "n_checked": 42, "status": "DARK",
                                     "never_produced": [], "stale": [],
                                     "organs": _liveness_organs()},
        "data/organ_readiness.json": {"ready": 11, "not_ready": 0, "ts": "2026-08-05",
                                      "gate_ok": True, "log_dir_writable": True,
                                      "doctrine_bytes": 59846},
        "data/organ_er.json": {"n_organs": 6, "n_healthy": 2, "n_sick": 4, "n_coma": 2,
                               "untreated_comas": ["a", "b"], "coma_hours": 24.0,
                               "treatments": [], "status": "COMA-UNTREATED", "detail": "2/6"},
        "data/kernel_log_status.json": {"verdict": "READABLE", "detail": "dmesg readable",
                                        "readable_channels": ["dmesg"],
                                        "channels": [{"channel": "dmesg"},
                                                     {"channel": "journalctl-k"}]},
        "data/promotion_queue.json": {
            "slots": {"occupied": 2, "cap": 12}, "n_candidates": 0, "latency_is_measured": False,
            "latency": {"total_days": 91.0, "fully_measured": False, "components": {
                "clock": {"days": 90.0, "provenance": "DESIGN"},
                "queue_wait": {"days": 0.0, "provenance": "MEASURED"},
                "decision": {"days": 1.0, "provenance": "ESTIMATED"}}}},
        "data/promotion_gate.json": {"granted_rung": 1, "granted": "PAPER", "blocked_at_rung": 2,
                                     "n_closed": 0,
                                     "ladder": [{"rung": 1}, {"rung": 2}, {"rung": 3},
                                                {"rung": 4}]},
        "data/alert_delivery.jsonl": (
            '{"ts":"2026-08-05T02:00:00+00:00","channel":"ntfy","ok":true,"detail":"202"}\n'
            '{"ts":"2026-08-05T03:00:00+00:00","channel":"none","ok":false,"detail":"NOT-ARMED"}\n'
        ),
        "data/alert_canary_state.json": {"last_canary": "2026-08-05T02:00:00+00:00"},
        "data/cost_hunt.json": {"n_measured": 17, "n_symbols": 18, "status": "PARTIAL",
                                "detail": "17/18 funding rates measured"},
        "data/execution_economics.json": {
            "status": "UNMEASURED",
            "inputs": {"trades": "ok", "live_book": "ok", "forensics": "NOT-READABLE-HERE",
                       "cost_model": "NOT-READABLE-HERE"},
            "thresholds_read_not_declared": {"sources": {"cost bands": "run_reality_gap.py"}}},
        "data/replacement_rate.json": {"births_measured": True, "births": 2, "deaths": 1,
                                       "replacement_rate": 0.5, "window_days": 90,
                                       "live_forward_clocks": 2, "status": "OK",
                                       "detail": "2 births vs 1 death"},
        "data/clock_provenance_status.json": {
            "status": "OK", "detail": "all streams declare their clock", "rows_sampled": 1000,
            "files_read": 12, "streams": {"a": {}, "b": {}, "c": {}, "d": {}},
            "mixed_clock_streams": ["a"], "unknown_streams": []},
        "data/backup_status.json": {
            "generated": "2026-08-05T12:00:00Z", "status": "DISK-FUSE",
            "stores": {"execution_tape": {"status": "REPLICATED", "path": "data/moat/tape"},
                       "graveyard": {"status": "REPLICATED", "path": "docs/graveyard.md"},
                       "cost_model": {"status": "ABSENT", "path": "data/cost_model.json",
                                      "note": "missing on this host"}},
            "restore_drill_passed": True, "disk_free_pct": 11.41, "fuse_pct": 15.0,
            "not_covered_note": "bulk lake needs a principal decision"},
        "data/miner_runway.json": {
            "checked": "2026-08-05T10:00:00Z", "observable": True, "creds_present": True,
            "by_status": {"ok": ["a"]}, "blockers": [],
            "seats": {"a": {"prompt": True, "runner": True, "unit": True, "creds": True,
                            "status": "ok"},
                      "b": {"prompt": True, "runner": True, "unit": True, "creds": True,
                            "status": "stale"},
                      "c": {"prompt": True, "runner": False, "unit": True, "creds": False,
                            "status": "stale"},
                      "d": {"prompt": True, "runner": True, "unit": True, "creds": False,
                            "status": "stale"}}},
        "data/utilisation.json": {
            "expect_fraction": 0.9, "mean_utilisation": 0.463, "idle_unexplained": [],
            "unmeasured": ["scheduler_cadence"],
            "ceilings": [
                {"name": "deployed_capital", "measured": True, "utilisation": 1.0,
                 "limit": 100.0, "used": 100.0, "status": "SATURATED", "binding_constraint": ""},
                {"name": "forward_confirmation_slots", "measured": True, "utilisation": 0.167,
                 "limit": 12.0, "used": 2.0, "status": "IDLE", "binding_constraint": "supply"},
                {"name": "optional_test_deps", "measured": True, "utilisation": 0.0,
                 "limit": 3.0, "used": 0.0, "status": "IDLE",
                 "binding_constraint": "missing ['arch', 'backtrader', 'vectorbt']"},
                {"name": "scheduler_cadence", "measured": False, "utilisation": 0.0,
                 "limit": 1.0, "used": 0.0, "status": "UNMEASURED",
                 "binding_constraint": "log directory absent"}]},
        "data/knowledge_engine.json": {"corpus_size": 40, "updated": "2026-08-05",
                                       "causal_edges": [{"cause": "x"}],
                                       "blind_validation_consistent": True},
        "data/trading_playbook.json": {"lessons": [1, 2, 3, 4], "reviewed_keys": 0,
                                       "updated": "2026-08-05"},
        "docs/desk_lessons.jsonl": "".join(
            f'{{"id":"L{i:04d}","learned":"2026-08-05","cost":"blind"}}\n' for i in range(12)),
        "data/scheduler_manifest_report.json": {
            "generated_utc": "2026-08-05T12:13:54Z", "cron_entries": 152, "systemd_entries": 16,
            "checks": {"scripts_exist": {"ok": True, "missing": []},
                       "committed_timers": {"ok": True, "problems": []},
                       "lock_coherence": {"ok": False, "problems": ["x"]},
                       "parse": {"ok": True, "problems": []},
                       "live_crontab": {"readable": True, "missing_in_live": ["a"],
                                        "extra_in_live": [], "duplicated_in_live": []}}},
        "data/build_standard.json": {"n_governed": 48, "n_failing": 0, "status": "OK",
                                     "failing": [], "unreadable_inputs": []},
        "data/mypy_ratchet.json": {"generated": "2026-07-30", "total_errors": 1116,
                                   "clean_fraction": 0.4068,
                                   "per_file": {f"s{i}.py": i % 2 for i in range(10)}},
        "data/wiring_agent.json": {"counts": {"PROPOSE": 34}, "n_scripts_scanned": 299},
        "data/source_alternatives_report.json": {
            "generated_utc": "2026-08-05T13:13:39Z", "vantage": "container",
            "vantage_note": "a probe here is a fact about THIS box", "mode": "all-registered",
            "dead_sources": [], "dead_without_registered_alternatives": [],
            "registry": {"a": {}, "b": {}}},
        "data/source_health.jsonl": (
            '{"day":"2026-08-04","source":"arxiv","verdict":"DEGRADED"}\n'
            '{"day":"2026-08-05","source":"arxiv","verdict":"HEALTHY"}\n'
            '{"day":"2026-08-05","source":"zhihu","verdict":"DEGRADED"}\n'
        ),
        "data/blindspot_max.json": {
            "updated": "2026-08-05", "unread_fields": 5, "unmodelled_entities": [],
            "uncrossed_pairs": [], "total": 5,
            "slices": [{"slice": "hour_of_day", "conditioned": True},
                       {"slice": "day_of_week", "conditioned": True},
                       {"slice": "regime", "conditioned": True},
                       {"slice": "session", "conditioned": False}]},
        "docs/research/CONSTITUTION_RATCHET.json": {
            "updated": "2026-08-04", "high_water": {"P0": 10, "P1": 9, "P2": 8, "P3": 10}},
        "docs/research/LAW_COVERAGE.json": {
            "updated": "2026-08-04",
            "live": {"principles": 27, "both": 27, "unenforced": 0, "mechanical_pct": 100.0,
                     "interactional_pct": 100.0, "full_pct": 100.0}},
        "data/timidity_audit.json": {
            "counts": {"CLASSIFIED": 26, "NO-RESTRAINT": 28}, "unclassified": [],
            "doctrine_injected": True, "prompt_surfaces_scanned": 18, "prompt_timid_hits": [],
            "rows": [{"row": i} for i in range(68)]},
        "data/return_targeting.json": {"n_scoped": 11, "n_flagged": 0, "status": "OK",
                                       "unreadable": [], "detail": "no return number bound"},
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


def _component(rep: dict[str, Any], aspect: str, key: str) -> dict[str, Any]:
    return next(c for c in _aspect(rep, aspect)["components"] if c["key"] == key)


class TestFallsAreFlaggedWithACause:
    def test_regression_names_the_component_the_artifact_and_both_numbers(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        assert _aspect(first, "governance")["score"] == 8.3

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
        # and it is NOT scored as zero: the surviving components still carry the aspect
        assert gov["score"] == 7.9

    def test_whole_aspect_going_dark_is_a_defect_carrying_its_last_mark(self, tmp_path):
        tree = _desk()
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        assert _aspect(first, "data_coverage")["state"] == MEASURED

        for rel in ASPECT_SOURCES["data_coverage"]:
            (tmp_path / rel).unlink()
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        dc = _aspect(second, "data_coverage")
        assert second["status"] == "REGRESSED"
        assert dc["movement"] == "WENT-DARK"
        assert dc["state"] == UNMEASURED
        assert dc["score"] is None                  # NOT zero, even while failing
        assert dc["high_water"] == 4.2              # the record it went dark from
        assert "data/data_assets.json" in dc["cause"]

    def test_a_flatline_names_the_binding_constraint_rather_than_saying_nothing(self, tmp_path):
        _build(tmp_path, _desk())
        _cycle(tmp_path, NOW)
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        assert second["status"] == "FLATLINE"
        assert len(second["flatlined"]) == len(ASPECT_KEYS)
        for row in second["flatlined"]:
            # "what is stopping this from being one point higher" -- either quantified in the
            # metric's own units, or a named imperative when the next point is not a number
            # (an organ that is STALE does not need +0.3 of anything, it needs restarting).
            assert any(marker in row["binding_constraint"] for marker in ACTIONABLE), \
                f"{row['aspect']} flatlined without an actionable constraint: " \
                f"{row['binding_constraint']}"

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


class TestEveryAspectIsScoredAndEveryAspectRefuses:
    """The two halves of the honesty rule, applied to EVERY aspect rather than the headline ones.

    A taxonomy is only worth widening if each new aspect actually reads its artifact AND actually
    refuses without it. An aspect that scores from a fixture but quietly reports 0 (or 10) when
    the file is gone is worse than no aspect: it puts a number on the board that means nothing.
    """

    @pytest.mark.parametrize("key", REQUIRED_ASPECTS)
    def test_the_aspect_scores_from_the_fixture_and_cites_its_sources(self, tmp_path, key):
        _build(tmp_path, _desk())
        aspect = _aspect(_cycle(tmp_path, NOW), key)

        assert aspect["state"] == MEASURED, f"{key} did not score from a complete fixture"
        assert aspect["score"] is not None
        assert 0.0 <= aspect["score"] <= SCALE_MAX
        assert aspect["ceiling"], f"{key} states no ceiling -- a score with no stated 10/10 drifts"
        assert aspect["binding_constraint"]
        assert aspect["components"], f"{key} has no components"
        for c in aspect["components"]:
            # A SCORE WITH NO SOURCE IS NOT ADMISSIBLE. Every component names the file it read.
            assert c["artifact"], f"{key}.{c['key']} cites no artifact"
            assert c["detail"] and c["constraint"]

    @pytest.mark.parametrize("key", REQUIRED_ASPECTS)
    def test_the_aspect_refuses_when_its_artifacts_are_gone(self, tmp_path, key):
        tree = _desk()
        _build(tmp_path, tree)
        for rel in ASPECT_SOURCES[key]:
            path = tmp_path / rel
            if path.exists():
                path.unlink()
        aspect = _aspect(_cycle(tmp_path, NOW), key)

        assert aspect["state"] == UNMEASURED, f"{key} scored something with no artifact to read"
        assert aspect["score"] is None                      # never 0.0, never 10.0
        for c in aspect["components"]:
            assert c["state"] == UNMEASURED
            assert c["score"] is None
            # the reason must name what would settle it, not merely that something is missing
            assert c["artifact"] in c["constraint"] or "MEASURE IT" in c["constraint"]

    def test_every_aspect_in_the_module_is_covered_by_this_table(self):
        # An aspect added without a refusal test is an aspect nobody proved honest.
        assert set(ASPECT_KEYS) == set(ASPECT_SOURCES) == set(REQUIRED_ASPECTS)


class TestTheDeskWideBindingConstraint:
    """One instruction, not thirty. A weekly sweep works the desk-wide minimum first."""

    def test_it_names_the_true_minimum_component_with_its_artifact(self, tmp_path):
        _build(tmp_path, _desk())
        rep = _cycle(tmp_path, NOW)

        scored = [(c["score"], a["key"], c["key"], c["artifact"])
                  for a in rep["aspects"] for c in a["components"]
                  if c["state"] == MEASURED and c["score"] is not None]
        want = min(scored)
        bind = rep["binding_constraint"]

        assert bind["state"] == MEASURED
        assert (bind["score"], bind["aspect"], bind["component"], bind["artifact"]) == want
        assert bind["constraint"]

    def test_it_moves_when_a_new_true_minimum_appears(self, tmp_path):
        # Lift the fixture's own zeroes first, so the move is unambiguous rather than a tie-break.
        tree = _desk()
        tree["data/organ_liveness.json"] = dict(
            tree["data/organ_liveness.json"],
            organs=[dict(o, state="FRESH", age_h=1.0) for o in _liveness_organs()])
        tree["data/utilisation.json"] = dict(
            tree["data/utilisation.json"],
            ceilings=[dict(c, used=3.0, utilisation=1.0) if c["name"] == "optional_test_deps"
                      else c for c in tree["data/utilisation.json"]["ceilings"]])
        _build(tmp_path, tree)
        before = _cycle(tmp_path, NOW)["binding_constraint"]
        assert before["score"] > 0.0
        assert (before["aspect"], before["component"]) == ("data_coverage",
                                                           "assets_with_measured_span")

        # drive one component to a hard zero; it must become the desk-wide constraint
        tree["data/law_gate.json"] = {"n_fences": 10, "n_failed": 10, "failures": ["x"] * 10}
        _build(tmp_path, tree)
        after = _cycle(tmp_path, NOW + timedelta(days=1))["binding_constraint"]

        assert (after["aspect"], after["component"]) == ("governance", "law_fences_passing")
        assert after["score"] == 0.0
        assert after["artifact"] == "data/law_gate.json"

    def test_an_unmeasured_component_never_becomes_the_binding_constraint(self, tmp_path):
        # An absent measurement has NO score. Letting it win here would make "the thing nobody
        # measured" permanently the top priority and bury every real defect beneath it.
        tree = _desk()
        del tree["data/clock_provenance_status.json"]
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)

        bind = rep["binding_constraint"]
        assert (bind["aspect"], bind["component"]) != ("recorder_tape", "tape_clock_declared")
        assert bind["n_unmeasured_components"] >= 1
        # but it is still visible, in its own list, with the artifact that would settle it
        assert any(u["component"] == "tape_clock_declared"
                   and u["artifact"] == "data/clock_provenance_status.json"
                   for u in rep["unmeasured_components"])

    def test_an_empty_desk_says_the_constraint_is_the_measurement_itself(self, tmp_path):
        bind = _cycle(tmp_path, NOW)["binding_constraint"]
        assert bind["state"] == UNMEASURED
        assert bind["score"] is None
        assert bind["aspect"] is None
        assert "NOTHING IS MEASURED" in bind["constraint"]


class TestTheMinorAspectsReadTheRightThing:
    """Aspect-specific traps, each one a way a minor aspect could report a comfortable lie."""

    def test_an_unrun_canary_does_not_read_as_a_live_pager(self, tmp_path):
        # The absence of the silence flag proves nothing if the canary never ran: an unrun canary
        # and a healthy pager leave the same empty directory.
        tree = _desk()
        del tree["data/alert_canary_state.json"]
        _build(tmp_path, tree)
        comp = _component(_cycle(tmp_path, NOW), "alerting_pager", "alert_channels_not_silent")
        assert comp["state"] == UNMEASURED
        assert comp["score"] is None

    def test_the_silence_flag_is_a_measured_zero_not_a_refusal(self, tmp_path):
        _build(tmp_path, _desk())
        (tmp_path / "data/ALERT_CHANNELS_SILENT").write_text("no delivery in 24h\n", "utf-8")
        comp = _component(_cycle(tmp_path, NOW), "alerting_pager", "alert_channels_not_silent")
        assert comp["state"] == MEASURED
        assert comp["score"] == 0.0
        assert "SILENCE FLAG PRESENT" in comp["detail"]

    def test_unobservable_seats_are_refused_rather_than_scored_zero(self, tmp_path):
        # miner_runway states its own observability. 0 productive of 11 would be a FABRICATED
        # defect when the log directory simply cannot be read from this box.
        tree = _desk()
        tree["data/miner_runway.json"] = dict(tree["data/miner_runway.json"], observable=False,
                                              blockers=[{"blocker": "log directory absent"}])
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        assert _component(rep, "llm_seat_coverage", "seats_productive")["score"] is None
        # but credentials and wiring ARE directly observable and stay measured
        assert _component(rep, "llm_seat_coverage", "seats_credentialled")["state"] == MEASURED

    def test_an_unreadable_live_crontab_is_unmeasured_not_zero_drift(self, tmp_path):
        # A manifest that agrees with ITSELF is not evidence the box runs what it says.
        tree = _desk()
        checks = dict(tree["data/scheduler_manifest_report.json"]["checks"])
        checks["live_crontab"] = {"readable": False, "note": "no live crontab readable",
                                 "missing_in_live": [], "extra_in_live": []}
        tree["data/scheduler_manifest_report.json"] = dict(
            tree["data/scheduler_manifest_report.json"], checks=checks)
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        drift = _component(rep, "scheduler_integrity", "live_crontab_matches_manifest")
        assert drift["state"] == UNMEASURED
        assert drift["score"] is None
        # the checks that DID run still score -- a refusal on one component is not a blackout
        assert _component(rep, "scheduler_integrity", "manifest_checks_passing")["score"] == 7.5

    def test_a_clock_fence_refusal_is_not_a_tape_defect(self, tmp_path):
        # NO-DATA means the fence had nothing to look at. Scoring it zero would invent a defect
        # out of an absent corpus; scoring it ten is the failure the fence itself forbids.
        tree = _desk()
        tree["data/clock_provenance_status.json"] = {"status": "NO-DATA",
                                                     "detail": "no tape to check"}
        _build(tmp_path, tree)
        comp = _component(_cycle(tmp_path, NOW), "recorder_tape", "tape_clock_declared")
        assert comp["state"] == UNMEASURED
        assert comp["score"] is None

    def test_an_unmeasured_ceiling_is_excluded_from_utilisation_not_folded_in_as_zero(self,
                                                                                     tmp_path):
        _build(tmp_path, _desk())
        rep = _cycle(tmp_path, NOW)
        assert _component(rep, "capital_utilisation",
                          "ceiling::scheduler_cadence")["state"] == UNMEASURED
        # the aggregate is the mean over the three MEASURED ceilings (1.0, 0.167, 0.0) against
        # the organ's own 0.9 expectation -- NOT the four-ceiling mean the fence publishes
        assert _component(rep, "capital_utilisation", "ceiling_utilisation")["score"] == 4.3

    def test_a_null_replacement_rate_is_refused_while_births_stays_a_measured_flag(self, tmp_path):
        tree = _desk()
        tree["data/replacement_rate.json"] = {"births_measured": False, "births": None,
                                              "deaths": 1, "replacement_rate": None,
                                              "status": "UNMEASURED-BIRTHS", "detail": "x",
                                              "window_days": 90}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)
        assert _component(rep, "forward_clock_hygiene", "replacement_rate")["score"] is None
        births = _component(rep, "forward_clock_hygiene", "births_countable")
        assert births["state"] == MEASURED and births["score"] == 0.0

    def test_a_missing_flag_is_unmeasured_while_false_is_a_measured_zero(self):
        # The distinction binary_component exists for: `None` is "the artifact never said", which
        # is not the same fact as "the artifact said no".
        assert binary_component("k", "a.json", None, detail="absent", fix="f").score is None
        assert binary_component("k", "a.json", False, detail="no", fix="f").score == 0.0
        assert binary_component("k", "a.json", True, detail="yes", fix="f").score == SCALE_MAX


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

    def test_a_truncated_target_does_not_count_as_BREADTH_either(self, tmp_path):
        # BREADTH is the other place the stopwatch trick works: a budget-truncated run scores an
        # arbitrary PREFIX of the file, so counting the file as "mutation-tested" would let the
        # desk buy coverage by running LESS -- the same defect one level up from the kill rate.
        tree = _desk()
        tree["data/mutation_score.json"] = {"bar": 0.9, "measured": "x", "targets": [
            {"target": "libs/execution/staging.py", "kill_rate": 1.0, "total": 4, "n_sites": 137,
             "budget_truncated": True},
            {"target": "libs/risk/gate.py", "kill_rate": 1.0, "total": 51},
        ]}
        _build(tmp_path, tree)
        rep = _cycle(tmp_path, NOW)

        # staging.py is one of the five money-path files; truncated, it counts for none of them
        money = _component(rep, "mutation_breadth", "money_path_files_mutated")
        assert money["score"] == 0.0
        assert "libs/execution/staging.py" in money["detail"]
        # and the truncated target is named as UNMEASURED rather than averaged away
        truncated = _component(rep, "mutation_breadth",
                               "mutation_targets_complete::staging.py")
        assert truncated["state"] == UNMEASURED
        assert "BUDGET-TRUNCATED" in truncated["detail"]
        # one complete target remains, so breadth is a real (low) reading, not a refusal
        assert _component(rep, "mutation_breadth", "mutation_targets_complete")["score"] == 1.0

    def test_the_breadth_denominator_comes_from_the_organ_that_owns_the_money_path(self, tmp_path):
        # Inventing the money-path file list here would let the breadth score be raised by
        # editing this module. With no declared list there is no honest denominator.
        tree = _desk()
        tree["docs/research/COVERAGE_RATCHET.json"] = {
            "measured": {"money_path_pct": 60.0, "money_path_statements": 740, "repo_pct": 89.0}}
        _build(tmp_path, tree)
        money = _component(_cycle(tmp_path, NOW), "mutation_breadth", "money_path_files_mutated")
        assert money["state"] == UNMEASURED
        assert money["artifact"] == "docs/research/COVERAGE_RATCHET.json"

    def test_the_at_bar_share_uses_the_artifacts_own_bar(self, tmp_path):
        # A scorer that owns its own bar is a scorer that can lower it. The bar is read from
        # data/mutation_score.json, which is where check_ratchets reads it too.
        tree = _desk()
        tree["data/mutation_score.json"] = {"bar": 0.99, "measured": "x", "targets": [
            {"target": "libs/risk/gate.py", "kill_rate": 0.95, "total": 51},
            {"target": "libs/risk/sizing.py", "kill_rate": 1.0, "total": 29},
        ]}
        _build(tmp_path, tree)
        at_bar = _component(_cycle(tmp_path, NOW), "mutation_breadth", "mutation_targets_at_bar")
        assert at_bar["score"] == 5.0                      # 1 of 2 clears 0.99, not 0.90
        assert "0.99" in at_bar["detail"]

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

        gov = _aspect(second, "governance")
        assert second["component_high_water"]["governance.law_fences_passing"] == 10.0
        assert gov["score"] > _aspect(first, "governance")["score"]
        assert gov["movement"] == "FELL"

    def test_widening_an_aspect_is_not_a_fall_and_keeps_the_old_mark(self, tmp_path):
        # THE LESSON check_ratchets.py ALREADY LEARNED: a single aggregate across targets meant
        # MEASURING A NEW FILE looked like a regression, and a fence that fires when the desk
        # measures MORE gets ignored. Here: llm_seat_coverage cannot see seat productivity, then
        # the log directory becomes readable and a weak third component appears.
        tree = _desk()
        tree["data/miner_runway.json"] = dict(tree["data/miner_runway.json"], observable=False,
                                              blockers=[{"blocker": "log dir absent"}])
        _build(tmp_path, tree)
        first = _cycle(tmp_path, NOW)
        seats = _aspect(first, "llm_seat_coverage")
        assert seats["score"] == 6.2                      # 2 measured components, 1 refused
        assert [c["state"] for c in seats["components"] if c["key"] == "seats_productive"] == [
            UNMEASURED]

        _build(tmp_path, _desk())                          # observable again, and only 1 of 4 ok
        second = _cycle(tmp_path, NOW + timedelta(days=1))
        seats = _aspect(second, "llm_seat_coverage")

        assert seats["score"] == 5.0 < 6.2
        assert seats["movement"] == "WIDENED"
        assert seats["high_water"] == 6.2                  # the mark is KEPT, never lowered
        assert "seats_productive" in seats["cause"]
        assert "NO component that already had a mark is below it" in seats["cause"]
        # and it is NOT a defect: nothing that was already graded got worse
        assert [d["aspect"] for d in second["defects"]] == []
        assert [w["aspect"] for w in second["widened"]] == ["llm_seat_coverage"]
        assert second["status"] != "REGRESSED"

    def test_widening_can_never_launder_a_real_fall(self, tmp_path):
        # The loophole this closes: add a fresh 10/10 component beside a collapsing one and hope
        # the aspect reads WIDENED. Component marks are held per component, so it cannot.
        tree = _desk()
        tree["data/miner_runway.json"] = dict(tree["data/miner_runway.json"], observable=False)
        _build(tmp_path, tree)
        _cycle(tmp_path, NOW)

        # seats_productive appears (new) AND seats_wired collapses in the same run
        seatmap = dict(_desk()["data/miner_runway.json"])
        seatmap["seats"] = {k: dict(v, runner=False) for k, v in seatmap["seats"].items()}
        tree["data/miner_runway.json"] = seatmap
        _build(tmp_path, tree)
        second = _cycle(tmp_path, NOW + timedelta(days=1))

        seats = _aspect(second, "llm_seat_coverage")
        assert seats["movement"] == "FELL"                 # never WIDENED
        assert "seats_wired" in seats["cause"]
        assert second["status"] == "REGRESSED"

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
