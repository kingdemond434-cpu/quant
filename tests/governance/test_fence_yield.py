"""L1.43 -- governance measured like everything else: has each fence ever caught anything?"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.check_fence_yield import _FENCES, _SEEDED, build_report


def test_report_runs_and_classifies_every_fence():
    rep = build_report(record=False)
    assert set(rep["fences"]) >= set(_FENCES)
    assert rep["n_fired"] + rep["n_quiet"] + rep["n_never_run"] == rep["n_fences"]


def test_seeded_firings_carry_their_evidence():
    # Seeding is only honest if each entry cites where the catch is recorded.
    for name, (verdict, why) in _SEEDED.items():
        assert name in _FENCES
        assert verdict in _FENCES[name][2], f"{name}: seeded verdict is not a firing value"
        assert len(why) > 60 and "2026-" in why


def test_a_fence_that_only_ever_says_ok_reads_quiet(tmp_path):
    (tmp_path / "data").mkdir(parents=True)
    for _n, (rel, key, _f, _k) in _FENCES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(json.dumps({key: "OK"}), "utf-8")
    rep = build_report(tmp_path, record=False)
    # the un-seeded fences must read QUIET; seeded ones keep their proven firing
    assert rep["fences"]["conversion"]["state"] == "QUIET"
    assert rep["fences"]["law_families"]["state"] == "FIRED"


def test_missing_artifact_is_never_run_not_ok(tmp_path):
    rep = build_report(tmp_path, record=False)
    assert rep["fences"]["conversion"]["state"] == "NEVER-RUN"


def test_rails_and_detectors_are_distinguished():
    # A quiet RAIL is what you are paying for (L1.23); a quiet DETECTOR is ambiguous.
    kinds = {k: v[3] for k, v in _FENCES.items()}
    assert kinds["law_gate"] == "RAIL" and kinds["moat_backup"] == "RAIL"
    assert kinds["conversion"] == "DETECTOR"
    rep = build_report(record=False)
    assert all(f["kind"] in ("RAIL", "DETECTOR") for f in rep["fences"].values())


def test_it_proposes_no_retirements_and_fails_no_build():
    src = Path("scripts/check_fence_yield.py").read_text("utf-8")
    assert "NEVER auto-retire" in src
    assert "return 0" in src.split("def main(")[1]     # evidence organ, never a gate
    assert "proposes no retirements" in src
