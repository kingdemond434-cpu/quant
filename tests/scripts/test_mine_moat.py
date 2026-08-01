"""The dedicated moat miner, end to end over a synthetic mine.

THE CLAIM UNDER TEST is not "it extracts numbers" -- moat_mine's own suite covers that. It is the
scheduling claim, which is the entire reason this organ exists: repeated budgeted runs must
CONVERGE ON 100% coverage rather than re-grinding whichever symbol happens to sort first. A miner
without hole-first ordering plateaus at the width of a single run and looks busy forever, which is
indistinguishable from progress in any log.

The second claim is the honest-empty one. data/ is not in git, so a fresh checkout has no mine.
Reporting 0.0% with the reason named is the correct output; exiting 0 in silence is how a dark
organ passes for a working one for six weeks -- a failure mode this desk has already lived.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.mine_moat as M


def _write_day(root: Path, venue: str, sym: str, day: str, *, hours: int = 2,
               kind: str = "d") -> None:
    d = root / venue / sym
    d.mkdir(parents=True, exist_ok=True)
    for h in range(hours):
        rows = []
        for i in range(40):
            size = 10.0 - (i % 5)          # varies, so nothing is degenerate
            rows.append({"t": i, "k": kind,
                         "b": [[f"{100 - j * 0.01:.4f}", f"{size:.4f}"] for j in range(20)],
                         "a": [[f"{100.1 + j * 0.01:.4f}", f"{size:.4f}"] for j in range(20)]})
            rows.append({"t": i, "k": "t", "p": "100.05", "q": "1"})   # the 8:1 trade noise
        with gzip.open(d / f"{day}_{h:02d}.jsonl.gz", "wt", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")


@pytest.fixture
def mine(tmp_path, monkeypatch):
    """A small synthetic mine wired into the miner's module-level paths."""
    moat = tmp_path / "moat"
    monkeypatch.setattr(M, "MOAT", moat)
    monkeypatch.setattr(M, "COVERAGE", tmp_path / "moat_coverage.json")
    monkeypatch.setattr(M, "REPORT", tmp_path / "moat_mine.json")
    monkeypatch.setattr(M, "SERIES", tmp_path / "moat_series.jsonl")
    monkeypatch.setattr(M, "ONTOLOGY_STATE", tmp_path / "ontology_state.json")
    return moat


def _report(tmp_path) -> dict:
    return json.loads((tmp_path / "moat_mine.json").read_text("utf-8"))


# ------------------------------------------------------------------ honest empty

def test_an_empty_mine_reports_zero_coverage_and_names_the_blocker(mine, tmp_path) -> None:
    """0.0% is a MEASUREMENT here, not a failure of the run -- and the recorders, not the miner,
    are named as what has to change. Silence would let a dark organ read as a working one."""
    assert M.main() == 0
    r = _report(tmp_path)
    assert r["coverage_pct"] == 0.0
    assert r["state"] == "NO MINE ON DISK"
    assert "recorders have written nothing" in r["reason"]


# ------------------------------------------------------------------ convergence

def test_repeated_budgeted_runs_converge_on_full_coverage(mine, tmp_path, monkeypatch) -> None:
    """THE LOAD-BEARING TEST. Coverage must be CUMULATIVE across runs and strictly increasing
    until it saturates. A miner whose coverage oscillates is re-grinding, not exploring."""
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for day in ("20260730", "20260731"):
            _write_day(mine, "fut", sym, day)
    monkeypatch.setattr(M, "FILE_BUDGET", 2)      # 2 files/run vs 12 on disk: forced multi-run

    seen = []
    for _ in range(8):
        M.main()
        seen.append(_report(tmp_path)["cumulative_coverage"]["coverage_pct"])

    assert seen == sorted(seen), f"coverage went backwards: {seen}"
    assert seen[-1] == 100.0, f"never reached full exploration: {seen}"
    assert seen[0] < 100.0, "budget was not actually binding -- the test proves nothing"


def test_holes_are_mined_before_anything_is_re_measured(mine, tmp_path, monkeypatch) -> None:
    """Without hole-first ordering the miner spends every run on the same alphabetically-first
    cell and the grid plateaus at the width of one run."""
    for sym in ("AAA", "BBB", "CCC", "DDD"):
        _write_day(mine, "fut", sym, "20260731", hours=1)
    monkeypatch.setattr(M, "FILE_BUDGET", 1)
    touched = []
    for _ in range(4):
        M.main()
        touched.append(_report(tmp_path)["results"][0]["symbol"])
    assert len(set(touched)) == 4, f"re-ground the same cell: {touched}"


# ------------------------------------------------------------------ both schemas

def test_the_bybit_schema_is_mined_alongside_the_binance_one(mine, tmp_path) -> None:
    """Two recorders, two `k` discriminators, one mine. Reading only one returns a clean and
    completely empty result over the other's files."""
    _write_day(mine, "fut", "BTCUSDT", "20260731", kind="d")
    _write_day(mine, "bybit", "BTCUSDT", "20260731", kind="depth")
    M.main()
    r = _report(tmp_path)
    venues = {row["symbol"].split("/")[0] for row in r["results"]}
    assert venues == {"fut", "bybit"}
    for row in r["results"]:
        assert row["mechanisms"]["imbalance"]["n"] > 0, row["symbol"]


# ------------------------------------------------------------------ what coverage means

def test_a_cell_that_measured_nothing_stays_open(mine, tmp_path) -> None:
    """ZERO OBSERVATIONS IS NOT COVERAGE. A file of pure trade rows contains no book; marking it
    covered would retire that day from the frontier on a measurement never taken."""
    d = mine / "fut" / "BTCUSDT"
    d.mkdir(parents=True)
    with gzip.open(d / "20260731_00.jsonl.gz", "wt", encoding="utf-8") as fh:
        for i in range(50):
            fh.write(json.dumps({"t": i, "k": "t", "p": "100", "q": "1"}) + "\n")
    M.main()
    assert _report(tmp_path)["cumulative_coverage"]["coverage_pct"] == 0.0


def test_a_constant_series_is_recorded_as_barren_not_as_a_finding(mine, tmp_path) -> None:
    """A series with zero dispersion cannot separate two states of the world however many
    observations back it. Recording it as a survivor would let a constant become a mechanism."""
    d = mine / "fut" / "BTCUSDT"
    d.mkdir(parents=True)
    with gzip.open(d / "20260731_00.jsonl.gz", "wt", encoding="utf-8") as fh:
        for i in range(60):
            fh.write(json.dumps({"t": i, "k": "d",
                                 "b": [["100.0000", "10.0000"]],
                                 "a": [["100.1000", "10.0000"]]}) + "\n")
    M.main()
    r = _report(tmp_path)
    assert any("imbalance" in x for x in r["degenerate_series"]), r["degenerate_series"]
    state = json.loads((tmp_path / "ontology_state.json").read_text("utf-8"))["questions"]
    assert state["STRUCT.1"]["attempts"] > 0
    assert state["STRUCT.1"]["survivors"] == 0, "a constant must never count as a survivor"


def test_the_series_file_is_append_only(mine, tmp_path) -> None:
    """The moat's entire value is that it ACCUMULATES. A results file rewritten each run has no
    history to accumulate, which would throw away the one property that makes it a moat."""
    _write_day(mine, "fut", "BTCUSDT", "20260731", hours=1)
    M.main()
    n1 = len((tmp_path / "moat_series.jsonl").read_text("utf-8").strip().splitlines())
    M.main()
    n2 = len((tmp_path / "moat_series.jsonl").read_text("utf-8").strip().splitlines())
    assert n2 > n1


def test_every_mechanism_is_wired_to_an_ontology_question(mine) -> None:
    """A measurement that updates no frontier region is a number in a file. This is what makes
    mining move the search space rather than just fill a log."""
    from libs.hypmax.moat_mine import MECHANISMS
    assert set(M._QUESTION) == set(MECHANISMS)
