"""R0017's remaining half: the certifier could not run at all, so 0/420 stayed uninterpretable."""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts import certify_gauntlet as cg


def test_it_imports_as_a_script_not_only_as_a_module():
    """It had no sys.path bootstrap, so `python scripts/certify_gauntlet.py` -- exactly how its
    manifest line invokes it -- died on ModuleNotFoundError. The BLOCKED artifact it was
    carefully written to emit was therefore never written either: the daily organ produced a
    bare traceback and the gap stayed invisible."""
    src = (cg.Path(__file__).resolve().parent.parent.parent
           / "scripts/certify_gauntlet.py").read_text("utf-8")
    assert "sys.path.insert" in src
    assert src.index("sys.path.insert") < src.index("from libs.autodiscovery")


def test_synthetic_fallback_builds_at_the_recorded_campaign_shape(tmp_path, monkeypatch):
    """The resolution the script named for itself. The shape is committed in gate_histogram.json,
    so the stand-in cohort has the campaign's real dimensions rather than invented ones."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cg, "_PREPARED", cg.Path("nope.pkl"))
    hist = tmp_path / "reports/gate_histogram.json"
    hist.parent.mkdir(parents=True)
    hist.write_text(json.dumps({"matrix_shape": [40, 12]}), "utf-8")
    monkeypatch.setattr(cg, "_HIST", hist)
    matrix, sharpes, n_obs, provenance = cg._load_campaign()
    assert provenance == "SYNTHETIC"
    assert matrix.shape == (40, 12) and n_obs == 40 and len(sharpes) == 12


def test_synthetic_peers_are_identical_across_runs():
    """The peers must not move between runs or the certification drifts for reasons that have
    nothing to do with the gate -- while the INJECTED controls still vary their seed, which is
    the defect R0017 actually closed on (a reused seed=7 across all 13 rows)."""
    a = cg.null_cohort(6, 30, rng=np.random.default_rng(cg._SYNTH_SEED))
    b = cg.null_cohort(6, 30, rng=np.random.default_rng(cg._SYNTH_SEED))
    assert np.array_equal(a, b)


def test_a_synthetic_run_is_a_different_status_never_plain_complete(tmp_path, monkeypatch):
    """A reader scanning for COMPLETE must not pick up a manufactured-peer run and conclude the
    real 0/420 campaign was vindicated. The numbers look identical; the questions are not."""
    src = (cg.Path(__file__).resolve().parent.parent.parent
           / "scripts/certify_gauntlet.py").read_text("utf-8")
    assert '"COMPLETE" if provenance == "CAMPAIGN" else "COMPLETE-SYNTHETIC"' in src
    assert "ONLY: can the gate stack pass a genuinely good candidate" in src


def test_it_still_refuses_when_even_the_shape_is_gone(tmp_path, monkeypatch):
    """Unknown must block: with no pickle AND no recorded shape there is nothing honest to build."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cg, "_PREPARED", cg.Path("nope.pkl"))
    monkeypatch.setattr(cg, "_HIST", cg.Path("also-nope.json"))
    with pytest.raises(cg.CampaignUnavailable):
        cg._load_campaign()
