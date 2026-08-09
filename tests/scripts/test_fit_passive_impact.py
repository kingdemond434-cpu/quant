"""R0267 `fit_passive_impact` organ: does it read a tape, refuse honestly, and honour its root?

The estimators themselves are controlled in tests/execution/test_passive_impact.py. What is tested
here is the ORGAN -- that an empty tree refuses rather than publishing a number, and that a `root`
argument reaches every read rather than half of them.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "fit_passive_impact", _ROOT / "scripts/fit_passive_impact.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fit_passive_impact"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def _write_hour(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


class TestRefusal:
    def test_empty_tree_is_no_data_not_a_number(self, mod, tmp_path):
        """An organ with nothing to read must refuse. A fitted coefficient from an empty tree is
        the L1.55 failure: well-formed, young, and built from an input that was never measured."""
        rep = mod.build_report(root=tmp_path)
        assert rep["status"] == "NO-DATA"
        assert rep["n_files_read"] == 0
        assert rep["counterfactual"]["decay"]["status"] in ("NO-DATA", "UNDERPOWERED")
        assert rep["counterfactual"]["curve"]["impact_bps"] == []

    def test_thin_tape_refuses_rather_than_fitting(self, mod, tmp_path):
        rows = [
            {"t": 1000, "k": "d", "b": [[100.0, 5.0], [99.9, 5.0]], "a": [[100.1, 5.0]]},
            {"t": 1100, "k": "t", "p": 99.9, "q": 1.0, "m": True},
        ]
        _write_hour(tmp_path / "data/moat/fut/BTCUSDT/20260806_00.jsonl.gz", rows)
        rep = mod.build_report(root=tmp_path)
        assert rep["status"] != "OK"
        assert rep["counterfactual"]["curve"]["impact_bps"] == []


class TestUntouchedLevelsCount:
    def test_levels_the_price_never_reached_are_zeros_not_dropped(self, mod):
        """REGRESSION, and it is the bug the first live run caught.

        Deep levels were skipped when no volume traded through them, so a deep bucket was only
        ever measured on the rare windows where price walked down to it -- conditioning on the
        outcome. The fitted slope came back POSITIVE (fill probability apparently RISING with
        distance). An untouched level has fill probability zero and must count as one.
        """
        # Levels chosen to sit INSIDE the module's distance cap, so anything missing from the
        # output is missing because it was dropped, not because it was out of range.
        rows = [
            {"t": 0, "k": "d",
             "b": [[100.0, 1.0], [99.9, 1.0], [99.8, 1.0], [99.7, 1.0]],
             "a": [[100.5, 1.0]]},
            # One small sell that only reaches the TOP bid. The three deeper levels are untouched.
            {"t": 100, "k": "t", "p": 100.0, "q": 5.0, "m": True},
        ]
        obs = mod._decay_observations(rows)
        assert len(obs) == 4, f"expected one row per bid level, got {obs}"
        deep = [pf for dist, pf in obs if dist > 30.0]
        assert len(deep) == 3, f"deeper levels were dropped -- the selection bug is back: {obs}"
        assert all(pf == 0.0 for pf in deep), deep
        touched = [pf for dist, pf in obs if dist <= 30.0]
        assert touched and max(touched) > 0.0


class TestRootIsHonoured:
    def test_own_fill_verdict_comes_from_the_given_root_not_the_live_tape(self, mod, tmp_path):
        """THE REGRESSION THIS EXISTS FOR: `build_report(root=...)` originally read the execution
        tape from the LIVE tree while reading the book from `root`, so the report was part fixture
        and part production and the mixture was invisible in the output."""
        tape = tmp_path / "data/moat/execution_tape/cashcarry_trades.jsonl"
        tape.parent.mkdir(parents=True, exist_ok=True)
        # A tape that DOES carry a varying placement offset -- impossible on the live tree, so if
        # the verdict comes back OK we know the fixture root was actually used.
        tape.write_text("".join(
            json.dumps({"event": "open", "quote_offset_bps": float(i % 7)}) + "\n"
            for i in range(50)), "utf-8")
        rep = mod.build_report(root=tmp_path)
        assert rep["own_fills"]["status"] == "OK", rep["own_fills"]
        assert rep["own_fills"]["n_rows"] == 50

    def test_absent_tape_under_root_reports_no_data(self, mod, tmp_path):
        rep = mod.build_report(root=tmp_path)
        assert rep["own_fills"]["status"] == "NO-DATA"


class TestReportShape:
    def test_carries_the_fields_a_reader_needs(self, mod, tmp_path):
        rep = mod.build_report(root=tmp_path)
        for key in ("generated", "law", "row", "status", "why", "n_files_read",
                    "n_distance_buckets", "counterfactual", "own_fills"):
            assert key in rep, key
        assert rep["row"] == "R0267"
        # The two bases must stay distinguishable in the artifact itself.
        assert rep["counterfactual"]["decay"]["basis"] == "counterfactual"
        assert "UPPER BOUND" in rep["counterfactual"]["caveat"]
        assert "OFFSET ARM" in rep["own_fills"]["note"]
