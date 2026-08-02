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
    monkeypatch.setattr(M, "HISTORY", tmp_path / "moat_coverage_history.jsonl")
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


# ------------------------------------------------------------------ the RATE, not the level
#
# P26 says under-exploration is a breach and that the breach is the gap NOT CLOSING. Those two
# states are identical in any snapshot -- 1.2% is a triumph the day after 0.5% and a scandal after
# a week at 1.2% -- so the miner has to trend its own coverage or the law is undecidable. These
# tests are written against the four verdicts separately because each one has a DIFFERENT fix, and
# collapsing them is how the desk would end up chasing neglect while the real problem was
# throughput.


def _history(monkeypatch, tmp_path, pcts, cells, *, step_s: int = 600, tape=None):
    from datetime import UTC, datetime, timedelta
    h = tmp_path / "hist.jsonl"
    t0 = datetime(2026, 8, 1, tzinfo=UTC)
    # Default: the tape grows, which is the normal world. Tests that care pass `tape` explicitly.
    tape = tape if tape is not None else [10**9 * (i + 1) for i in range(len(pcts))]
    with h.open("w", encoding="utf-8") as fh:
        for i, (p, c) in enumerate(zip(pcts, cells, strict=True)):
            fh.write(json.dumps({"ts": (t0 + timedelta(seconds=step_s * i)).isoformat(),
                                 "run": i, "coverage_pct": p, "cells_filled": c,
                                 "cells_total": 1000, "holes": 1000 - c,
                                 "tape_bytes": tape[i], "tape_files": 100 * (i + 1)}) + "\n")
    monkeypatch.setattr(M, "HISTORY", h)
    # closure() appends its OWN row and measures the tape itself, so the fixture has to control
    # that reading too -- otherwise the appended row reports this container's empty data/moat and
    # the synthetic history is contradicted by its own last point.
    monkeypatch.setattr(M, "tape_bytes", lambda _root: (tape[-1], 100 * len(tape)))
    return h


def _rep(pct: float, cells: int, total: int = 1000) -> dict:
    return {"coverage_pct": pct, "cells_filled": cells, "cells_total": total,
            "holes": total - cells}


def test_a_rising_coverage_is_closing_and_carries_an_eta(monkeypatch, tmp_path) -> None:
    """A gap being closed is NOT a breach, and firing on it would train everyone to ignore the
    alarm that matters. The ETA is the deliverable: 'when do we reach 100%' has to be an answer
    the desk computes, not one a human reconstructs from two numbers they wrote down."""
    _history(monkeypatch, tmp_path, [0.5, 0.9, 1.3, 1.7, 2.1], [5, 9, 13, 17, 21])
    c = M.closure(_rep(2.5, 25), run=6)
    assert c["state"] == "CLOSING"
    assert c["runs_to_100"] and c["runs_to_100"] > 0
    assert c["hours_to_100"] and c["hours_to_100"] > 0


def test_a_flat_coverage_is_the_breach_in_its_pure_form(monkeypatch, tmp_path) -> None:
    """Edge the desk has already PAID to record and is declining to collect. This is the state
    the check has to be able to reach, and before the closure field existed it could not: the
    defect fired identically whether the miner was converging in hours or had been dead a week."""
    _history(monkeypatch, tmp_path, [1.2] * 6, [12] * 6)
    c = M.closure(_rep(1.2, 12), run=7)
    assert c["state"] == "STANDING-STILL"
    assert c["runs_to_100"] is None, "a flat series must not be extrapolated to a finish date"


def test_cells_rising_while_the_percentage_stalls_is_a_throughput_finding(
        monkeypatch, tmp_path) -> None:
    """THE SUBTLE ONE. The grid GROWS every second the recorders run, so a miner working flat out
    can hold the percentage still. Reporting that as neglect sends the desk chasing a motivation
    problem it has not got -- the fix is more miner, and the verdict has to say so."""
    _history(monkeypatch, tmp_path, [1.2] * 6, [12, 24, 36, 48, 60, 72])
    c = M.closure(_rep(1.2, 84, total=7000), run=7)
    assert c["state"] == "OUTPACED-BY-RECORDING"
    assert "more miner" in c["why"]


def test_too_few_observations_is_unknown_rather_than_a_verdict(monkeypatch, tmp_path) -> None:
    """A slope through two points is not evidence. Guessing here in either direction is worse than
    admitting the rate is not yet measurable."""
    _history(monkeypatch, tmp_path, [0.5], [5])
    c = M.closure(_rep(0.9, 9), run=2)
    assert c["state"] == "UNKNOWN"
    assert c["runs_to_100"] is None


def test_the_eta_is_derived_from_the_percentage_not_the_cell_count(monkeypatch, tmp_path) -> None:
    """An ETA from cells-per-run assumes a frozen archive and promises a date that recording pushes
    back every day. The percentage slope already nets grid growth out, which is the only reason it
    can be quoted to a human at all."""
    # cells climb 10/run, but the grid climbs with them so the percentage barely moves
    _history(monkeypatch, tmp_path, [1.0, 1.02, 1.04, 1.06, 1.08], [10, 20, 30, 40, 50])
    c = M.closure(_rep(1.10, 60, total=5455), run=6)
    naive = (100.0 - 1.10) / 10.0        # what a cell-slope ETA would have claimed
    assert c["runs_to_100"] is None or c["runs_to_100"] > naive * 10
    assert "nets out grid growth" in c["eta_note"]


def test_coverage_history_is_append_only(mine, tmp_path, monkeypatch) -> None:
    """The trend IS the enforcement mechanism, so a file that gets overwritten each run destroys
    the only evidence P26 can be decided on."""
    for sym in ("AAAUSDT", "BBBUSDT"):
        _write_day(mine, "fut", sym, "20260731", hours=1)
    monkeypatch.setattr(M, "FILE_BUDGET", 1)
    assert M.main() == 0
    n1 = len((tmp_path / "moat_coverage_history.jsonl").read_text("utf-8").strip().splitlines())
    assert M.main() == 0
    n2 = len((tmp_path / "moat_coverage_history.jsonl").read_text("utf-8").strip().splitlines())
    assert n2 > n1


# ------------------------------------------------------------------ the false win
#
# THE FAILURE THESE GUARD, STATED ONCE. Coverage is filled/total, and total only grows while the
# recorders write. Disk exhaustion pauses them, the grid freezes, and the miner closes the last
# holes in a frozen denominator all the way to 100%. That produces a GREEN number for the exact
# event that ends the desk's only unreplicable asset -- worse than a red alarm, because it retires
# the chase. Every test below exists because a rising percentage is not, by itself, good news.


def test_a_frozen_tape_refuses_the_coverage_verdict_even_while_coverage_rises(
        monkeypatch, tmp_path) -> None:
    """THE LOAD-BEARING ONE. Coverage climbing 41 -> 62 with the tape byte-identical is the
    miner grinding out a frozen grid. Reporting CLOSING here would be true of the ratio and a lie
    about the asset."""
    _history(monkeypatch, tmp_path, [41.0, 47.0, 53.0, 59.0], [410, 470, 530, 590],
             tape=[8_200_000_000] * 4)
    c = M.closure(_rep(62.0, 620), run=5)
    assert c["state"] == "RECORDING-STOPPED"
    assert c["coverage_is_meaningful"] is False
    assert c["runs_to_100"] is None, "a frozen grid must not be given a finish date"
    assert "frozen grid" in c["why"] or "FROZEN grid" in c["why"]


def test_a_growing_tape_leaves_the_normal_verdicts_alone(monkeypatch, tmp_path) -> None:
    """The guard must not fire on the healthy world -- an alarm that also rings when nothing is
    wrong is the one everybody disables."""
    _history(monkeypatch, tmp_path, [0.5, 0.9, 1.3, 1.7], [5, 9, 13, 17])
    c = M.closure(_rep(2.1, 21), run=5)
    assert c["state"] == "CLOSING"
    assert c["coverage_is_meaningful"] is True


def test_a_short_history_does_not_call_a_quiet_run_a_stopped_recorder(
        monkeypatch, tmp_path) -> None:
    """The recorders flush on their own schedule, so one pass seeing no new bytes is normal. Four
    observations is the bar -- below it, silence is not evidence of death."""
    _history(monkeypatch, tmp_path, [1.0, 1.2], [10, 12], tape=[5_000_000_000] * 2)
    c = M.closure(_rep(1.4, 14), run=3)
    assert c["state"] != "RECORDING-STOPPED"


def test_the_disk_deadline_travels_with_the_coverage_number(monkeypatch, tmp_path) -> None:
    """The miner reads the archive every pass, which makes it the cheapest place on the desk to
    notice the archive has a deadline. Carried in the artifact so the audit reads it rather than
    re-deriving it."""
    _history(monkeypatch, tmp_path, [0.5, 0.9, 1.3, 1.7], [5, 9, 13, 17])
    c = M.closure(_rep(2.1, 21), run=5)
    assert "disk" in c
    assert c["disk"]["state"] in ("OK", "URGENT", "PAUSED", "UNKNOWN")
    assert "used_frac" in c["disk"]


def test_a_real_run_ships_the_closure_verdict_in_its_artifact(mine, tmp_path) -> None:
    """Read by check_under_exploration, so a missing field is a law that cannot be decided. The
    check reads the ARTIFACT rather than re-deriving the trend, which means this field existing is
    what makes the enforcement real."""
    _write_day(mine, "fut", "AAAUSDT", "20260731", hours=1)
    assert M.main() == 0
    c = _report(tmp_path)["closure"]
    assert c["state"] in ("CLOSING", "STANDING-STILL", "OUTPACED-BY-RECORDING", "UNKNOWN",
                          "COMPLETE-FOR-THIS-GRID")
    assert c["why"]
