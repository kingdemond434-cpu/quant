"""Tests for INTERNAL CLAIM RECONCILIATION (L1.61).

The positive control is the point (the desk's own ``certify_gauntlet`` lesson: a gauntlet never
shown to PASS a known-good input has not been validated, only its rejections have been observed).
Every test here plants a KNOWN state and asserts the fence reaches the verdict that state
deserves -- including the verdicts that must NOT fire.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops.claim_registry import (
    AGREED,
    CLAIMS,
    CONTRADICTED,
    UNRESOLVED,
    Claim,
    Publisher,
    _gate0_criterion,
    _guard_criterion,
    _plain_key,
    reconcile,
)


def _write(root: Path, rel: str, doc: Any) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))


def _board(**criteria: str) -> dict[str, Any]:
    return {"rows": [{"criterion": k, "status": v, "detail": f"{k} detail"}
                     for k, v in criteria.items()]}


def _guard(why: str, *, measured: bool = True, stage: str = "S0") -> dict[str, Any]:
    return {"stage": stage, "stage_gate": {"why": why, "measured": measured, "provenance": []}}


def _one_claim(*, from_absent: bool = False) -> tuple[Claim, ...]:
    return (Claim(
        name="gate0.keys_present",
        question="q",
        publishers=(
            Publisher("check_gate0_ready", "data/gate0_readiness.json",
                      _gate0_criterion("keys_present"), measures="files on disk"),
            Publisher("run_live_guard", "data/live_guard.json",
                      _guard_criterion("keys_present", from_absent_input=from_absent),
                      measures="connector constructed"),
        ),
    ),)


class TestPositiveControl:
    """A planted contradiction must be caught, and a planted agreement must NOT be."""

    def test_planted_contradiction_is_caught(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["status"] == "CONTRADICTED"
        assert rep["n_contradicted"] == 1
        assert rep["rows"][0]["status"] == CONTRADICTED

    def test_planted_agreement_does_not_fire(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=True"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["status"] == "OK"
        assert rep["rows"][0]["status"] == AGREED
        assert rep["n_compared"] == 1

    def test_agreement_on_false_is_still_agreement(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="NOT-READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["status"] == "OK"


class TestRefusalPath:
    """UNMEASURED must never read as agreement (L1.28a)."""

    def test_no_artifacts_at_all_is_unmeasured_not_ok(self, tmp_path: Path) -> None:
        rep = reconcile(tmp_path, _one_claim())
        assert rep["status"] == "UNMEASURED"
        assert rep["n_compared"] == 0

    def test_one_side_missing_is_unresolved_not_agreed(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["rows"][0]["status"] == UNRESOLVED
        assert rep["status"] == "UNMEASURED"

    def test_board_refusal_status_is_not_a_verdict(self, tmp_path: Path) -> None:
        """BLOCKED-UNKNOWN is the board's own refusal and must never be compared as False."""
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="BLOCKED-UNKNOWN"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["rows"][0]["status"] == UNRESOLVED

    def test_unreadable_artifact_is_counted_as_attrition(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data/gate0_readiness.json").write_text("{not json")
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False"))
        rep = reconcile(tmp_path, _one_claim())
        assert "data/gate0_readiness.json" in rep["unreadable_artifacts"]
        assert rep["rows"][0]["status"] == UNRESOLVED

    def test_partial_when_some_resolve_and_none_contradict(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json",
               _board(keys_present="READY", connector_verified="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=True"))
        claims = (*_one_claim(), Claim(
            name="gate0.connector_verified", question="q",
            publishers=(
                Publisher("check_gate0_ready", "data/gate0_readiness.json",
                          _gate0_criterion("connector_verified")),
                Publisher("run_live_guard", "data/live_guard.json",
                          _guard_criterion("connector_verified")),
            )))
        rep = reconcile(tmp_path, claims)
        assert rep["status"] == "PARTIAL"
        assert rep["n_compared"] == 1 and rep["n_unresolved"] == 1


class TestRepairAttribution:
    """The repair class is what makes a finding actionable rather than a puzzle."""

    def test_absent_input_side_is_labelled_fabricated(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False", measured=False))
        rep = reconcile(tmp_path, _one_claim(from_absent=True))
        assert rep["rows"][0]["kind"] == "FABRICATED-SIDE"
        assert "REPAIR THE INPUT" in rep["rows"][0]["repair"]

    def test_block_measured_flag_alone_does_not_taint_a_real_measurement(
            self, tmp_path: Path) -> None:
        """The regression that the first run of this fence actually had.

        ``measured: False`` is BLOCK-level. A criterion computed after -- and overriding -- the
        absent input is a genuine measurement, and labelling it FABRICATED sends the reader to
        repair an input that this value never read.
        """
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False", measured=False))
        rep = reconcile(tmp_path, _one_claim(from_absent=False))
        assert rep["rows"][0]["kind"] == "SAME-NAME-DIFFERENT-QUESTION"
        assert not any(s["fabricated"] for s in rep["rows"][0]["sides"])

    def test_same_name_different_question_is_distinguished(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/gate0_readiness.json", _board(keys_present="READY"))
        _write(tmp_path, "data/live_guard.json", _guard("keys_present=False"))
        rep = reconcile(tmp_path, _one_claim())
        assert rep["rows"][0]["kind"] == "SAME-NAME-DIFFERENT-QUESTION"
        assert "CONTRACT is the defect" in rep["rows"][0]["repair"]


class TestComparison:
    def test_bool_vs_non_bool_never_reads_as_agreement(self, tmp_path: Path) -> None:
        """The `ready` collision: a bool in one artifact and a count in another."""
        _write(tmp_path, "data/a.json", {"ready": True})
        _write(tmp_path, "data/b.json", {"ready": 11})
        claims = (Claim(name="ready", question="q", publishers=(
            Publisher("a", "data/a.json", _plain_key("ready")),
            Publisher("b", "data/b.json", _plain_key("ready")),
        )),)
        assert reconcile(tmp_path, claims)["status"] == "CONTRADICTED"

    def test_number_tolerance_is_honoured(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/a.json", {"x": 1.000})
        _write(tmp_path, "data/b.json", {"x": 1.004})
        mk = lambda tol: (Claim(  # noqa: E731
            name="x", question="q", kind="number", tolerance=tol, publishers=(
                Publisher("a", "data/a.json", _plain_key("x")),
                Publisher("b", "data/b.json", _plain_key("x")),
            )),)
        assert reconcile(tmp_path, mk(0.01))["status"] == "OK"
        assert reconcile(tmp_path, mk(0.001))["status"] == "CONTRADICTED"

    def test_container_value_is_not_a_scalar_verdict(self, tmp_path: Path) -> None:
        _write(tmp_path, "data/a.json", {"x": [1, 2]})
        _write(tmp_path, "data/b.json", {"x": 1})
        claims = (Claim(name="x", question="q", publishers=(
            Publisher("a", "data/a.json", _plain_key("x")),
            Publisher("b", "data/b.json", _plain_key("x")),
        )),)
        assert reconcile(tmp_path, claims)["rows"][0]["status"] == UNRESOLVED

    def test_substring_criterion_names_do_not_cross_match(self, tmp_path: Path) -> None:
        """`symbol_count` must not match inside `symbol_count_4_5`."""
        _write(tmp_path, "data/live_guard.json", _guard("symbol_count_4_5=False"))
        doc = json.loads((tmp_path / "data/live_guard.json").read_text())
        assert _guard_criterion("symbol_count")(doc).resolved is False
        assert _guard_criterion("symbol_count_4_5")(doc).value is False


class TestRegistryIsReal:
    """A registry entry that cannot resolve against the real repo is a decorative claim."""

    def test_every_registered_claim_names_at_least_two_publishers(self) -> None:
        assert CLAIMS, "the registry must not be empty -- an empty scope reads UNMEASURED"
        for c in CLAIMS:
            assert len(c.publishers) >= 2, f"{c.name} has fewer than two publishers"

    def test_scanned_counts_the_run_not_the_registry(self, tmp_path: Path) -> None:
        """L1.57: the denominator must count what the RUN found, never len(CLAIMS)."""
        rep = reconcile(tmp_path, CLAIMS)
        assert rep["n_claims_registered"] == len(CLAIMS)
        assert rep["n_compared"] == 0, "nothing on disk in tmp_path -- nothing can be compared"
        assert rep["status"] == "UNMEASURED"


class TestFenceWiring:
    """Tests that fail if the wiring is removed."""

    def test_fence_script_exists_and_declares_its_denominator(self) -> None:
        src = Path(__file__).resolve().parents[2] / "scripts/check_claim_consistency.py"
        assert src.exists()
        body = src.read_text()
        assert "fence_exit(" in body, "the fence must exit through fence_exit (L1.41)"
        assert "scanned=report[\"n_compared\"]" in body, "denominator must be the measured count"
        assert "_law_guard()" in body, "every entry point passes the laws (L1.42)"

    @pytest.mark.parametrize("path", ["scripts/check_claim_consistency.py",
                                      "libs/ops/claim_registry.py"])
    def test_law_is_mapped_in_the_enforcement_matrix(self, path: str) -> None:
        root = Path(__file__).resolve().parents[2]
        body = (root / "scripts/build_enforcement_matrix.py").read_text()
        assert path in body, f"{path} must be mapped to L1.61 in the enforcement matrix"

    def test_fence_is_scheduled(self) -> None:
        root = Path(__file__).resolve().parents[2]
        manifest = (root / "ops/crontab.manifest").read_text()
        assert "check_claim_consistency.py" in manifest, "an unscheduled fence never runs (L1.28c)"
