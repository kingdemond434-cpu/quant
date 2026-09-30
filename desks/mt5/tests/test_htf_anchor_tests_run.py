"""htf_anchor_proposer charges distinct hypotheses tested, never accumulated census rows.

Audit of #137 (2026-09-30): `tests_run=len(census["rows"])` charged every pass the census's
whole accumulated history and nothing for the cells actually minted. The claim-selection trials
(#169) are charged once elsewhere and must not ride on tests_run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

BASE = Path(__file__).resolve().parents[1]
for p in (str(BASE.parents[1]), str(BASE), str(BASE / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import htf_anchor_proposer as hap  # noqa: E402


def _cell(sym: str, mult: float) -> dict[str, Any]:
    return hap._row(sym, "htf_anchor_trend", {"timeframe": "H1", "anchor_mult": mult,
                                              "expansion_mult": 0.0,
                                              "exit_on_anchor_flip": False}, "t")


def test_distinct_minted_plus_census_this_pass_never_accumulated_rows() -> None:
    cands = [_cell("EURUSD", 4), _cell("EURUSD", 4), _cell("GBPUSD", 4), _cell("EURUSD", 8)]
    census = {"rows": [{}] * 500, "cells_measured_this_pass": 12}
    got = hap.hypotheses_tested(cands, census)
    # the wrap repeat is one hypothesis; 500 historical readings are not re-charged
    assert got == {"minted": 3, "census_screened": 12, "total": 15}


def test_census_without_per_pass_count_is_charged_whole_never_zero() -> None:
    got = hap.hypotheses_tested([_cell("EURUSD", 4)], {"rows": [{}] * 7})
    assert got["census_screened"] == 7 and got["total"] == 8
    assert hap.hypotheses_tested([], {})["total"] == 0


def test_claim_selection_trials_are_not_charged_per_pass() -> None:
    row = {**_cell("EURUSD", 4), "claim_selection_trials": 200}
    assert hap.hypotheses_tested([row], {"cells_measured_this_pass": 0})["total"] == 1


def test_main_donates_the_distinct_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import proposer_common as pc
    grid = [_cell("EURUSD", m) for m in (2, 4)]           # smaller than the slice: ring wraps
    monkeypatch.setattr(hap, "CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(hap, "MINT", tmp_path / "mint.json")
    monkeypatch.setattr(hap, "_legal_symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(hap, "bind_census",
                        lambda budget_s=0.0: {"rows": [{}] * 900, "binding": [],
                                              "cells_measured_this_pass": 5})
    monkeypatch.setattr(hap, "build_candidates", lambda census, symbols: list(grid))
    seen: dict[str, Any] = {}

    def fake_donate(source: str, candidates: list[dict], tests_run: int) -> None:
        seen.update(n=len(candidates), tests_run=tests_run)

    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {})
    assert hap.main([]) == 0
    assert seen["n"] == 4                                      # 2 cells, wrapped once
    assert seen["tests_run"] == 2 + 5                          # distinct cells + census this pass
    assert json.loads((tmp_path / "mint.json").read_text())["tests_run"]["total"] == 7
