"""The meta-controller CONSUMES the science controller (U19): the QD archive's empty
high-value cells become ranked new-hypothesis actions, an anytime-valid DISCOVERY becomes a
deepen action and a FUTILE campaign with queued launches becomes freed compute. An absent
report contributes nothing -- guarded, never a crash."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import meta_controller as MC  # noqa: E402

SCIENCE_DOC = {
    "empty_high_value_cells": [
        {"cell": "carry|fx|EU-US|EURUSD|london|calm|sub_4h|limit", "value": 0.42,
         "neighbours": 3},
        {"cell": "bad", "value": 0.1, "neighbours": 1},
        "not a row",
    ],
    "families": {"top": [
        {"family_id": "fam_a", "queued": 3, "judged": 12, "passes_at_gate": 9,
         "continuation": {"decision": "STOP_DISCOVERED", "anytime_p": 0.01,
                          "why": "e=120 vs 1/alpha=20"}},
        {"family_id": "fam_b", "queued": 4, "judged": 60, "passes_at_gate": 0,
         "continuation": {"decision": "STOP_FUTILE", "anytime_p": 1.0,
                          "why": "excess pass rate CS below zero"}},
        {"family_id": "fam_c", "queued": 0, "judged": 5, "passes_at_gate": 0,
         "continuation": {"decision": "STOP_FUTILE", "why": "nothing queued"}},
        {"family_id": "fam_d", "queued": 2, "judged": 1, "passes_at_gate": 0,
         "continuation": {"decision": "CONTINUE", "why": "undecided"}},
    ]},
}


def test_science_actions_read_the_archive_and_the_decisions() -> None:
    acts = MC._science_actions(SCIENCE_DOC)
    kinds = {(a["kind"], a["target"]) for a in acts}
    assert ("new_hypothesis", "archive:carry|fx|EU-US|EURUSD|london|calm|sub_4h|limit") in kinds
    assert ("new_hypothesis", "archive:bad") in kinds
    assert ("deepen_existing", "family:fam_a") in kinds
    assert ("abandon_region", "family:fam_b") in kinds
    assert not any(a["target"] in ("family:fam_c", "family:fam_d") for a in acts)
    deepen = next(a for a in acts if a["target"] == "family:fam_a")
    assert deepen["p_success"] == pytest.approx(0.99) and deepen["info_gain_nats"] > 0.0
    futile = next(a for a in acts if a["target"] == "family:fam_b")
    assert futile["frees_cells"] == 4.0 and futile["info_gain_nats"] == 0.0
    assert all(a["source"] == "science_controller" for a in acts)
    assert all(a["kind"] in MC.COSTS for a in acts)


def test_an_absent_or_malformed_report_contributes_nothing(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    assert MC._science_actions({}) == []
    assert MC._science_actions({"families": "nope", "empty_high_value_cells": None}) == []
    monkeypatch.setattr(MC, "SCIENCE", tmp_path / "absent.json")
    assert MC._read(MC.SCIENCE) == {}
    path = tmp_path / "SCIENCE_CONTROLLER.json"
    path.write_text(json.dumps(SCIENCE_DOC), encoding="utf-8")
    monkeypatch.setattr(MC, "SCIENCE", path)
    assert len(MC._science_actions(MC._read(MC.SCIENCE))) == 4
