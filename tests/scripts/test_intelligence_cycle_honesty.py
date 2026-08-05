"""R0095 (E-6/E-13): the intelligence cycle must report what actually happened.

Two honesty defects fixed here, both of the crash-reported-as-data-gap class:
  * _subprocess_cap labelled ANY nonzero exit NO-INPUT -- the label factory crashed daily
    for weeks and the cycle reported it as an absent-input condition.
  * _research_priority ranked HARDCODED constants while reporting ACTIVE ("ranked N
    categories by decay pressure"), indistinguishable from a measured ranking.
"""

from __future__ import annotations

from unittest import mock

import scripts.run_intelligence_cycle as ic


class TestSubprocessCapStatus:
    def test_nonzero_exit_is_error_not_no_input(self) -> None:
        fake = mock.Mock(returncode=3, stdout="Traceback ...\nValueError: boom", stderr="")
        with mock.patch.object(ic.subprocess, "run", return_value=fake):
            out = ic._subprocess_cap("x", "scripts/build_labels.py", timeout_s=5)
        assert out["status"] == "ERROR", "a crash is a crash, not an absent input"
        assert "exit=3" in out["detail"]

    def test_zero_exit_is_active(self) -> None:
        fake = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(ic.subprocess, "run", return_value=fake):
            out = ic._subprocess_cap("x", "scripts/build_labels.py", timeout_s=5)
        assert out["status"] == "ACTIVE"


class TestResearchPriorityWiring:
    def test_ranks_from_mechanism_board_when_kpis_lack_families(self) -> None:
        def reader(rel: str):
            if rel == "data/mechanism_board.json":
                return {"verdicts": {"M_PRICE_PATTERN": "FAMILY KILL",
                                     "M_FORCED_DELEVERAGE": "ALIVE",
                                     "M_LIQUIDITY_WITHDRAWAL": "UNTESTED"}}
            return {}
        with mock.patch.object(ic, "_read", side_effect=reader):
            out = ic._research_priority()
        assert out["status"] == "ACTIVE"
        assert "mechanism_board" in out["detail"], "the source must be named, not implied"
        top = {t["category"]: t["score"] for t in out["top"]}
        assert top["M_PRICE_PATTERN"] > top["M_FORCED_DELEVERAGE"], (
            "a killed family carries more decay pressure than a live one"
        )

    def test_no_measured_record_is_data_free_not_active(self) -> None:
        with mock.patch.object(ic, "_read", return_value=None):
            out = ic._research_priority()
        assert out["status"] == "NO-INPUT"
        assert "DATA-FREE" in out["detail"], "constants must never masquerade as a ranking"
