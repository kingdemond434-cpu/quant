from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gate_policy import ATTESTATION, GATES  # noqa: E402
from survivor_publication import publish_qquant_survivors  # noqa: E402
from universal_gate import retained_exact_survivors  # noqa: E402


def _stages(passed: bool = True) -> dict:
    return {name: {"passed": passed} for name in GATES}


def test_qquant_pass_is_atomically_merged_with_shadow_identity(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({
        "survivors": {"other.hunt": {"cell": "kept"}},
        "gate_policy": ATTESTATION,
    }), encoding="utf-8")
    report = {
        "gate_policy": ATTESTATION,
        "swept_at": "2026-08-23T13:51:10+00:00",
        "verdicts": [{
            "id": "AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY",
            "hunt": "hunt16.json",
            "days": 179,
            "passed": True,
            "stages": _stages(),
            # THE SWEEP ALWAYS EMITS THIS. `full_pipeline` writes `"params": c["params"]` onto
            # every verdict row, and this fixture omitted it only because the publisher used to
            # throw it away -- which is exactly the defect that produced six unrunnable
            # certificates in the sealed canon.
            "params": {"lookback": 20, "adx_min": 25},
        }],
    }
    result = publish_qquant_survivors(report, reports)
    assert result["survivor_count"] == 2
    payload = json.loads((reports / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    row = payload["survivors"][result["published"][0]]
    assert row["shadow_spec"] == {
        "symbol": "AUDNZD", "family": "dav_range_filter_adx", "side": "SHORT",
        "selector": "afternoon", "condition": "NORMAL_DAY", "is_universe": True,
        "hunt": "hunt16.json", "params": {"lookback": 20, "adx_min": 25},
    }
    ledger = json.loads((reports / "SURVIVORS_LEDGER.json").read_text("utf-8"))
    assert ledger["n"] == 1


def test_failed_or_partial_rows_never_publish(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    report = {
        "gate_policy": ATTESTATION,
        "verdicts": [
            {"id": "A f LONG w s", "hunt": "h", "passed": False, "stages": _stages()},
            {"id": "B f LONG w s", "hunt": "h", "passed": True,
             "stages": {k: v for k, v in _stages().items() if k != "pbo"}},
        ],
    }
    assert publish_qquant_survivors(report, reports)["survivor_count"] == 0


def test_incremental_universal_sweep_retains_only_exact_prior_passes(tmp_path: Path) -> None:
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps({
        "gate_policy": ATTESTATION,
        "survivors": {
            "qquant.kept": {"gates": _stages(), "shadow_spec": {"symbol": "AUDNZD"}},
            "partial.rejected": {"gates": {"economic_prior": {"passed": True}}},
        },
    }), encoding="utf-8")
    assert retained_exact_survivors(path) == {
        "qquant.kept": {"gates": _stages(), "shadow_spec": {"symbol": "AUDNZD"}},
    }


def test_a_certificate_with_no_parameterization_is_refused_not_sealed(tmp_path: Path) -> None:
    """A ten-gate pass whose sweep recorded no `params` is a ZOMBIE and must never be sealed.

    It would be counted in every survivor total, inflate the certified library, and reach no
    capital for ever: enrolment cannot run it without inventing the parameterization that passed,
    and inventing one runs a different strategy than the one that was certified. Measured
    2026-09-05: 6 of 66 certificates in the sealed canon are in exactly this state, and
    `session_range_breakout` -- 15 certificates with parameters and 5 without, same family --
    proves the missing ones are a lost parameterization rather than a parameterless strategy.

    `{}` IS NOT `None`. A family that genuinely takes no parameters publishes an empty mapping and
    enrols normally, which is why `overnight_gap_decay` funds while these do not.
    """
    reports = tmp_path / "reports"
    reports.mkdir()
    base = {"gate_policy": ATTESTATION, "swept_at": "2026-09-05T00:00:00+00:00"}
    row = {"id": "AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY",
           "hunt": "hunt16.json", "days": 179, "passed": True, "stages": _stages()}

    refused = publish_qquant_survivors({**base, "verdicts": [dict(row)]}, reports)
    assert refused["published"] == [], "an unrunnable certificate was sealed into the canon"

    kept = publish_qquant_survivors({**base, "verdicts": [{**row, "params": {}}]}, reports)
    assert len(kept["published"]) == 1, (
        "a family that takes NO parameters publishes `{}` and must still be sealed -- refusing it "
        "too would turn a defect fence into a capability cut")
