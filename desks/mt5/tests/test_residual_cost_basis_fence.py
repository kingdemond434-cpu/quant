"""A residual cell must not be proposed on a spread the desk already knows is wrong.

`factor_residual_engine._cost_frac` prices every expectancy from the universe registry's
`median_spread_pts`. `repair_universe_spreads` re-derives that number hourly from each symbol's
own H1 spread column and publishes the difference. Measured 2026-09-14, of the sixteen cells the
engine proposed, the five whose targets had been re-measured were understated WITHOUT EXCEPTION:

    CHFHUF     224 ->  16,990   75.8x   (also flagged SUSPECT)
    CHFPLN      16 ->     174   10.9x
    CHFSEK      33 ->     339   10.3x
    AUDHUF   1,616 ->  11,400    7.1x
    CHFDKK      24 ->      45    1.9x

CHFHUF was proposed with cost_frac 5.4e-05 against gross 1.9e-03; at 75.8x the cost its net is
NEGATIVE. `_candidate` mints these into the docket with "no new wiring" to the gauntlet and the
forward engine, and automatic promotion is a standing order -- so the path from a bad spread to
live capital had nothing in it.

THIS IS NOT A RISK REDUCTION AND MUST NOT BE READ AS ONE (GROWTH_GOVERNANCE Rule 1). It suppresses
a claim whose expectancy is negative once its own cost is priced correctly, which RAISES robust
forward E[log W]. It is repaired by fixing the spreads, not by lowering the bar, and the refusals
are published in `refused_on_cost_basis` so the missed growth is named rather than silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
fre = pytest.importorskip("research.factor_residual_engine")


def _provenance(tmp_path: Path, monkeypatch, doc: dict) -> None:
    p = tmp_path / "SPREAD_PROVENANCE.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(fre, "SPREAD_PROVENANCE", p)


def test_a_materially_understated_spread_is_named_with_its_ratio(tmp_path, monkeypatch):
    _provenance(tmp_path, monkeypatch, {
        "corrected": [{"symbol": "CHFHUF", "old": 224.0, "new": 16990.0}],
        "suspect": [{"symbol": "CHFHUF", "old": 224.0, "new": 16990.0}]})
    b = fre._cost_basis()["CHFHUF"]
    assert b["basis"] == "REMEASURED"
    assert b["ratio"] == pytest.approx(75.85, abs=0.05)
    assert b["suspect"] is True
    assert b["ratio"] >= fre.MAX_SPREAD_UNDERSTATEMENT


def test_a_realized_fill_beats_an_inference(tmp_path, monkeypatch):
    """An execution is evidence; a re-derivation from bars is not, and must not override it."""
    _provenance(tmp_path, monkeypatch, {
        "kept_realized_fills": [{"symbol": "EURUSD"}],
        "corrected": [{"symbol": "EURUSD", "old": 1.0, "new": 900.0}]})
    b = fre._cost_basis()["EURUSD"]
    assert b["basis"] == "REALIZED_FILLS"
    assert b["ratio"] == 1.0


def test_a_symbol_never_re_measured_is_UNMEASURED_not_clean(tmp_path, monkeypatch):
    """Absence is a verdict (L1.28a). It must not silently read as a verified cost."""
    _provenance(tmp_path, monkeypatch, {"corrected": [{"symbol": "OTHER", "old": 1.0, "new": 2.0}]})
    assert "ZARJPY" not in fre._cost_basis()


def test_a_mildly_wider_spread_does_not_trip_the_fence(tmp_path, monkeypatch):
    """CHFDKK measures 1.88x and is KEPT -- the fence is for fiction, not for every correction."""
    _provenance(tmp_path, monkeypatch,
                {"corrected": [{"symbol": "CHFDKK", "old": 24.0, "new": 45.0}]})
    b = fre._cost_basis()["CHFDKK"]
    assert b["ratio"] < fre.MAX_SPREAD_UNDERSTATEMENT


def test_an_unreadable_provenance_report_does_not_block_everything(tmp_path, monkeypatch):
    """A missing report must degrade to UNMEASURED, never refuse the whole engine's output."""
    monkeypatch.setattr(fre, "SPREAD_PROVENANCE", tmp_path / "nope.json")
    assert fre._cost_basis() == {}


def test_the_complete_map_is_preferred_over_the_readers_sample(tmp_path, monkeypatch):
    """`corrected` is published as 60 rows of 191. Reading the sample invents UNMEASURED verdicts.

    Measured 2026-09-14: eleven of the sixteen proposal targets sat in the 131 rows the truncation
    dropped, so the fence read every one as never-measured and let them through. A sampled
    artifact does not report a smaller answer -- it reports a DIFFERENT one, and silently.
    """
    _provenance(tmp_path, monkeypatch, {
        "n_corrected": 191,
        "corrected": [{"symbol": "INSAMPLE", "old": 10.0, "new": 200.0}],
        "by_symbol": {"INSAMPLE": {"old": 10.0, "new": 200.0},
                      "TRUNCATED": {"old": 5.0, "new": 400.0}}})
    b = fre._cost_basis()
    assert "TRUNCATED" in b, "a symbol outside the published sample must still be seen"
    assert b["TRUNCATED"]["ratio"] == pytest.approx(80.0)
    assert b["TRUNCATED"]["ratio"] >= fre.MAX_SPREAD_UNDERSTATEMENT
    assert b["INSAMPLE"]["ratio"] == pytest.approx(20.0)


def test_a_realized_fill_still_wins_against_the_complete_map(tmp_path, monkeypatch):
    _provenance(tmp_path, monkeypatch, {
        "kept_realized_fills": [{"symbol": "EURUSD"}],
        "by_symbol": {"EURUSD": {"old": 1.0, "new": 900.0}}})
    assert fre._cost_basis()["EURUSD"]["basis"] == "REALIZED_FILLS"
