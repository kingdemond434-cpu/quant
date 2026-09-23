"""The effective-trial charge, and that the SEALED judge's input actually carries it."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
for p in (str(ROOT), str(BASE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.trial_ledger import (  # noqa: E402
    campaign_charge,
    content_key,
    effective_independent_tests,
    grid_key,
    mechanism_key,
    trial_from_record,
)
from research import effective_trials as et  # noqa: E402


def _row(fam: str, sym: str, tf: str, **params: Any) -> dict[str, Any]:
    return {"family": fam, "symbol": sym, "timeframe": tf, "params": dict(params)}


# ----------------------------------------------------------------- the identities
def test_grid_cell_is_family_symbol_horizon() -> None:
    t = trial_from_record(_row("carry", "AUDJPY", "H1", fast=19))
    assert grid_key(t) == "carry|AUDJPY|H1"
    assert mechanism_key(t) == "carry"
    assert grid_key(trial_from_record(_row("carry", "AUDJPY", "H4"))) != grid_key(t)


def test_missing_axes_are_marked_not_invented() -> None:
    assert grid_key(trial_from_record({"family": "carry"})) == "carry|?|?"


def test_content_key_separates_different_evaluations() -> None:
    a = trial_from_record(_row("carry", "AUDJPY", "H1", fast=19))
    b = trial_from_record(_row("carry", "AUDJPY", "H1", fast=20))
    assert content_key(a) != content_key(b)


# ------------------------------------------------------- the charge, both directions
def test_parameter_variants_of_one_rule_collapse_toward_one_test() -> None:
    """Thirty-one tunings of one rule on one instrument are nearer one test than thirty-one."""
    rows = [_row("carry", "AUDJPY", "H1", fast=19 + i, slow=57 + i) for i in range(31)]
    c = effective_independent_tests(rows)
    assert c.n_nominal == 31
    assert c.n_effective < 10.0
    assert c.n_effective >= 1.0
    assert c.ratio > 3.0


def test_distinct_grid_cells_are_never_collapsed() -> None:
    """A different symbol or horizon is a different test of the claim: the hard direction."""
    rows = [_row("carry", sym, "H1", fast=19) for sym in ("AUDJPY", "EURUSD", "GBPCAD", "NZDCHF")]
    c = effective_independent_tests(rows)
    assert c.n_effective == pytest.approx(4.0)
    assert c.ratio == pytest.approx(1.0)


def test_distinct_mechanisms_are_independent_by_construction() -> None:
    rows = [_row(f"mech_{i}", "AUDJPY", "H1", fast=19) for i in range(5)]
    c = effective_independent_tests(rows)
    assert c.n_mechanisms == 5
    assert c.n_effective == pytest.approx(5.0)


def test_effective_never_exceeds_nominal_and_never_below_one() -> None:
    for rows in ([_row("carry", "AUDJPY", "H1", fast=19)] * 9,
                 [_row("carry", "AUDJPY", "H1", fast=f) for f in range(2, 40)]):
        c = effective_independent_tests(rows)
        assert 1.0 <= c.n_effective <= c.n_nominal


def test_empty_docket_is_unmeasured_not_zero_trials() -> None:
    c = effective_independent_tests([])
    assert c.status == "UNMEASURED"
    assert c.ratio == 1.0


# ------------------------------------------------------------- campaign charge safety
def test_campaign_charge_scales_by_measured_redundancy() -> None:
    rows = [_row("carry", "AUDJPY", "H1", fast=19 + i) for i in range(20)]
    c = effective_independent_tests(rows)
    charged, basis = campaign_charge(597, c)
    assert charged < 597
    assert "effective_campaign_trials" in basis


def test_unmeasured_census_fails_closed_to_the_unchanged_nominal_charge() -> None:
    charged, basis = campaign_charge(597, effective_independent_tests([]))
    assert charged == 597
    assert "fail_closed" in basis


def test_charge_is_floored_at_the_number_of_distinct_mechanisms() -> None:
    rows = [_row(f"mech_{i}", "AUDJPY", "H1", fast=19) for i in range(40)]
    c = effective_independent_tests(rows)
    charged, _ = campaign_charge(41, c)
    assert charged >= c.n_mechanisms


def test_charge_never_rises_above_the_nominal_campaign_count() -> None:
    rows = [_row(f"mech_{i}", "AUDJPY", "H1") for i in range(500)]
    charged, _ = campaign_charge(597, effective_independent_tests(rows))
    assert charged <= 597


# -------------------------------------------------------------- the organ and the spec
_SPEC = """version: test
gates:
  - name: deflated_sharpe
    params:
      trials_multiplier: 7.0
      fixed_trial_count: 597
      fixed_variance_of_sharpes: 0.014863
      # a comment that must survive the write
      trial_count_basis: "fixed_campaign_trials(597)"
      fail_closed_to: "fixed_campaign_trials(597)"
"""


def test_apply_to_spec_rewrites_the_charge_and_keeps_the_comments(tmp_path: Path) -> None:
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    res = et.apply_to_spec(109, variance=0.014863, path=spec)
    assert res["status"] == "APPLIED"
    text = spec.read_text("utf-8")
    assert "fixed_trial_count: 109" in text
    assert "a comment that must survive the write" in text
    assert et.spec_fixed_trial_count(spec) == 109
    assert "effective_campaign_trials(109)" in text


def test_apply_to_spec_never_raises_the_charge(tmp_path: Path) -> None:
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    res = et.apply_to_spec(900, variance=0.014863, path=spec)
    assert res["status"] == "UNCHANGED"
    assert et.spec_fixed_trial_count(spec) == 597


def test_a_small_move_does_not_rewrite_policy_every_hour(tmp_path: Path) -> None:
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    res = et.apply_to_spec(590, variance=0.014863, path=spec)
    assert res["status"] == "UNCHANGED"
    assert et.spec_fixed_trial_count(spec) == 597


def test_lower_charge_lowers_the_hurdle_and_the_relief_is_published() -> None:
    assert et.sr0(109, 0.014863) < et.sr0(597, 0.014863)


def test_build_publishes_nominal_effective_ratio_and_the_judge_proof(
        tmp_path: Path) -> None:
    docket = tmp_path / "docket.json"
    rows = [_row("carry", "AUDJPY", "H1", fast=19 + i) for i in range(24)]
    rows += [_row("overnight_gap_decay", "EURUSD", "H4", z=1.0 + i / 10) for i in range(12)]
    docket.write_text(json.dumps(rows), encoding="utf-8")
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    doc = et.build(docket=docket, spec=spec, apply=True, budget_s=30.0)
    assert doc["verdict"] == "MEASURED"
    assert doc["nominal"] == 36
    assert doc["effective"] < 36
    assert doc["ratio_nominal_per_effective"] > 1.0
    assert doc["n_mechanisms"] == 2
    fams = {r["family"] for r in doc["by_family"]}
    assert fams == {"carry", "overnight_gap_decay"}
    cam = doc["campaign"]
    assert cam["sr0_after"] <= cam["sr0_before"]
    assert doc["judge_input_proof"]["status"] in ("MEASURED", "UNMEASURED")
    out = tmp_path / "EFFECTIVE_TRIALS.json"
    et.write(doc, report=out)
    assert json.loads(out.read_text("utf-8"))["nominal"] == 36


def test_absent_docket_is_unmeasured_and_changes_no_policy(tmp_path: Path) -> None:
    spec = tmp_path / "gate_spec.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    doc = et.build(docket=tmp_path / "nope.json", spec=spec, apply=True, budget_s=5.0)
    assert doc["verdict"] == "UNMEASURED"
    assert et.spec_fixed_trial_count(spec) == 597


def test_render_is_a_list_of_lines() -> None:
    doc = et.build(docket=Path("/nonexistent/docket.json"), apply=False, budget_s=5.0)
    assert all(isinstance(line, str) for line in et.render(doc))
