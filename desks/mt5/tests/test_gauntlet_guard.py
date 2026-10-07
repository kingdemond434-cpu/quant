"""The judge's environment monitor, and the atomic universe write that stopped killing it.

These are the two unsealed halves of "the judge reaches its epilogue": a writer that never hands
the sealed reader a torn frame, and a reader of the judge's own log that can say how many passes
reached the end without anyone's impression of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gauntlet_guard as gg  # noqa: E402
from mt5desk.universe_registry import publish_frame  # noqa: E402


# --------------------------------------------------------------- the torn-frame fault
def test_publish_frame_never_leaves_a_torn_destination(tmp_path):
    """A universe frame is published whole or not at all -- the fault that killed 19 sweeps.

    `to_parquet` onto the destination truncates it first, so a concurrent `pd.read_parquet`
    can see 0 bytes. The published file must always carry both PAR1 sentinels.
    """
    dest = tmp_path / "EURUSD_H1.parquet"
    frame = pd.DataFrame({"close": [1.0, 2.0, 3.0]},
                         index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"],
                                              utc=True))
    assert publish_frame(frame, dest) is True
    raw = dest.read_bytes()
    assert raw[:4] == b"PAR1" and raw[-4:] == b"PAR1"
    assert pd.read_parquet(dest).shape == (3, 1)
    # no temp litter left beside the destination
    assert [p.name for p in tmp_path.iterdir()] == ["EURUSD_H1.parquet"]


def test_publish_frame_replaces_in_place_and_keeps_the_old_frame_readable(tmp_path):
    """A republish over an existing frame leaves ONE valid file, never a half-written one."""
    dest = tmp_path / "XAUUSD_M15.parquet"
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True)
    publish_frame(pd.DataFrame({"close": [1.0, 2.0]}, index=idx), dest)
    publish_frame(pd.DataFrame({"close": [9.0, 8.0]}, index=idx), dest)
    assert list(pd.read_parquet(dest)["close"]) == [9.0, 8.0]
    assert dest.read_bytes()[:4] == b"PAR1"


# --------------------------------------------------------------- the integrity fence
def test_frame_integrity_names_the_torn_frames_and_counts_the_whole_directory(tmp_path):
    good = tmp_path / "AUDUSD_H1.parquet"
    publish_frame(pd.DataFrame({"close": [1.0]},
                               index=pd.to_datetime(["2026-01-01"], utc=True)), good)
    (tmp_path / "EMPTY_H1.parquet").write_bytes(b"")
    (tmp_path / "HALF_M5.parquet").write_bytes(b"PAR1" + b"\x00" * 40)

    out = gg.frame_integrity(tmp_path)
    assert out["status"] == "MEASURED"
    assert out["checked"] == 3
    assert out["n_torn"] == 2
    assert any(n.startswith("EMPTY_H1") for n in out["torn"])
    assert "HALF_M5.parquet" in out["torn"]


def test_frame_integrity_on_an_absent_directory_is_unmeasured_not_clean(tmp_path):
    """An absent directory is UNMEASURED (L1.28a) -- never a zero that reads as 'all fine'."""
    out = gg.frame_integrity(tmp_path / "nope")
    assert out["status"] == "UNMEASURED" and "torn" not in out


# --------------------------------------------------------------- the pass reader
@pytest.mark.parametrize(("line", "phase"), [
    ("PRE-WARM: 15 worker(s) warmed 2399 cell(s) in 1288s", "prewarm"),
    ("Cell cache: 58502/140090 loaded (same data-day), 81588 to compute", "cache"),
    ("  seen-cells: +55318 first-judged this sweep (171696 known)", "seen"),
    ("Saved to C:\\opt\\quant\\desks\\mt5\\reports\\universal_gates_external.json", "saved_report"),
    ("Updated UNIVERSAL_SURVIVORS.json: 119 total (+91)", "survivors"),
    ("SURVIVORS_LEDGER.json: 177 claim(s)", "ledger"),
    ("Traceback (most recent call last):", "traceback"),
    ("  FAIL GBPZAR@M5.overnight_drift n=350", None),
])
def test_classify_reads_the_judges_own_phase_prints(line, phase):
    assert gg.classify(line) == phase


def _ev(*phases):
    return [{"phase": p, "text": p} for p in phases]


def test_a_pass_that_reaches_the_ledger_is_recorded_as_reaching_the_epilogue():
    passes = gg.fold(_ev("prewarm", "cache", "seen", "saved_report", "survivors", "ledger"),
                     [], "T0")
    assert len(passes) == 1
    assert passes[0]["outcome"] == "REACHED_EPILOGUE"


def test_a_pass_that_dies_between_the_gates_and_the_survivor_write_is_recorded_as_died():
    """The exact shape that discarded 65 passing cells: judged, saved, then killed."""
    passes = gg.fold(_ev("prewarm", "cache", "seen", "saved_report", "traceback"), [], "T0")
    assert passes[0]["outcome"] == "DIED_BEFORE_EPILOGUE"
    assert "survivors" not in passes[0]["phases"]


def test_a_new_prewarm_closes_the_previous_pass_as_died():
    """A pass killed by the task window prints no traceback at all -- the next PRE-WARM is the
    only evidence it ended, and a reader that waited for a traceback would count it as open
    for ever."""
    passes = gg.fold(_ev("prewarm", "cache", "seen", "prewarm", "cache"), [], "T0")
    assert len(passes) == 2
    assert passes[0]["outcome"] == "DIED_BEFORE_EPILOGUE"
    assert passes[1]["outcome"] == "OPEN"


def test_fold_keeps_a_bounded_history_so_the_report_cannot_grow_without_end():
    passes: list[dict] = []
    for _ in range(gg.KEEP_PASSES + 12):
        passes = gg.fold(_ev("prewarm", "ledger"), passes, "T")
    assert len(passes) == gg.KEEP_PASSES


def test_commit_info_is_measured_or_says_why_and_never_reports_a_false_ceiling():
    """A zero headroom must never be manufactured by a failed probe: the ceiling is the
    diagnosis for a broken worker pool, so a wrong one would misdirect the next session."""
    out = gg.commit_info()
    assert out["status"] in {"MEASURED", "UNMEASURED"}
    if out["status"] == "MEASURED":
        assert out["commit_limit_gb"] > 0
        assert out["headroom_gb"] == pytest.approx(
            out["commit_limit_gb"] - out["commit_total_gb"], abs=0.02)
        assert isinstance(out["peak_touched_ceiling"], bool)
    else:
        assert out["why"]


def test_the_guard_never_writes_to_or_stops_the_sealed_judge():
    """The seal, pinned by a test. This organ may MEASURE the judge; it may never write to it,
    start it or stop it -- and the only file it writes is its own report."""
    src = Path(gg.__file__).read_text(encoding="utf-8")
    assert "SEALED" in src
    for forbidden in (".terminate(", ".kill(", "taskkill", "Popen("):
        assert forbidden not in src, f"gauntlet_guard must never {forbidden}"
    assert 'OUT = REPORTS / "GAUNTLET_PASSES.json"' in src
    assert src.count("os.replace(") == 1, "the guard writes exactly one file: its own report"


# --------------------------------------------------------------- the consumer
def test_judging_throughput_reads_the_guard_and_absence_is_unmeasured(tmp_path, monkeypatch):
    """The guard's report has a reader: `judging_throughput` carries it into the judge's sizing
    evidence, REPORT ONLY. An absent report is UNMEASURED (L1.28a), never a clean environment."""
    root = DESK.parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from research import judging_throughput as jt

    monkeypatch.setattr(jt, "GAUNTLET_PASSES", tmp_path / "GAUNTLET_PASSES.json")
    assert jt._judge_environment()["judge_env_status"] == jt.UNMEASURED

    (tmp_path / "GAUNTLET_PASSES.json").write_text(
        '{"reach_rate": 0.55, "passes_closed": 20, '
        '"commit": {"headroom_gb": 3.2, "peak_touched_ceiling": true}, '
        '"frame_integrity": {"n_torn": 0}}', encoding="utf-8")
    env = jt._judge_environment()
    assert env["judge_env_status"] == "MEASURED"
    assert env["judge_env_reach_rate"] == 0.55
    assert env["judge_env_commit_ceiling_touched"] is True
    assert env["judge_env_torn_frames"] == 0
