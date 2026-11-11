"""Idea 619: the families step asks for memory before it grows, and every step logs its peak.

Measured on the box 2026-11-11: MT5-MergeDocket (pid 36280) stalled inside the families step at
16.7 GB of commit against ~15.8 GB admitted at entry, held the docket writer lane ~31 h, and froze
the Judge's intake. The run was admitted once and never asked again.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import job_lock
from research import merge_hypotheses as merger


def _box(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, free: int | None,
         peaks: list[int] | None = None) -> None:
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(job_lock, "free_mb", lambda: free)
    for p in peaks or []:
        job_lock.record_peak(merger.FAMILIES_STEP, p)


def test_the_step_is_refused_when_free_memory_cannot_cover_its_growth(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _box(monkeypatch, tmp_path, free=1500)
    ok, why = merger.families_admission()
    assert ok is False and "1500MB free" in why and "3000MB" in why


def test_measured_growth_raises_the_bar_above_the_declaration(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _box(monkeypatch, tmp_path, free=4000, peaks=[2900, 4500, 4600, 4700])
    ok, why = merger.families_admission()
    assert ok is False and "p75" in why            # 4000 free < ~4700 measured growth


def test_enough_memory_admits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _box(monkeypatch, tmp_path, free=20000)
    ok, why = merger.families_admission()
    assert ok is True and "20000MB free" in why


def test_an_unreadable_counter_changes_nothing(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    _box(monkeypatch, tmp_path, free=None)
    ok, why = merger.families_admission()
    assert ok is True and "UNMEASURED" in why


def test_each_step_logs_its_peak_free_and_time(monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(job_lock, "peak_rss_mb", lambda: 1234)
    monkeypatch.setattr(job_lock, "free_mb", lambda: 5678)
    row = merger._mem_line("before families", 0.0)
    out = capsys.readouterr().out
    assert row["peak_mb"] == 1234 and row["free_mb"] == 5678
    assert "mem[before families]: peak 1234MB, free 5678MB" in out


def test_a_refusal_costs_the_census_never_a_row() -> None:
    """The refusal rides the step's existing fault path, which keeps rows_out unchanged."""
    src = inspect.getsource(merger.main)
    refuse = src.index("families step refused by its memory admission")
    apply = src.index("_hf.apply(")
    fault = src.index('families census unavailable')
    assert refuse < apply < fault
    assert "record_peak(FAMILIES_STEP" in src           # the step's growth is measured each run


def test_each_run_writes_its_own_log_so_an_orphan_cannot_block_the_next(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os
    from datetime import UTC, datetime
    real_out, real_err = sys.stdout, sys.stderr
    opened = []
    try:
        with open(tmp_path / f"{merger.LOG_STEM}.log", "a", encoding="utf-8"):  # the orphan
            first = merger._per_run_log(tmp_path, datetime(2026, 11, 11, 10, 0, tzinfo=UTC))
            opened.append(sys.stdout)
            print("run one")
            second = merger._per_run_log(tmp_path, datetime(2026, 11, 11, 11, 0, tzinfo=UTC))
            opened.append(sys.stdout)
            print("run two")
    finally:
        sys.stdout, sys.stderr = real_out, real_err
        for fh in opened:
            fh.close()
    assert first and second and first != second
    assert str(os.getpid()) in second.name
    assert "run one" in first.read_text("utf-8") and "run two" in second.read_text("utf-8")
    assert (tmp_path / f"{merger.LOG_STEM}.latest.txt").read_text("utf-8").strip() == second.name


def test_old_run_logs_are_pruned(tmp_path: Path) -> None:
    import os
    from datetime import UTC, datetime
    old = tmp_path / f"{merger.LOG_STEM}-20260101T000000Z-1.log"
    old.write_text("x", "utf-8")
    os.utime(old, (0, 0))
    real_out, real_err = sys.stdout, sys.stderr
    try:
        merger._per_run_log(tmp_path, datetime(2026, 11, 11, tzinfo=UTC))
        mine = sys.stdout
    finally:
        sys.stdout, sys.stderr = real_out, real_err
    mine.close()
    assert not old.exists()


def test_the_flag_is_read_before_admission() -> None:
    src = inspect.getsource(merger.run_cli)
    assert src.index('"--log-dir"') < src.index("exclusive_job(")


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_mergedocket_task.ps1"


def test_the_task_runs_python_directly_with_a_per_run_log() -> None:
    """A stop must end the process doing the work, and no run may share another run's log file.

    The 11-11 box read: the cmd.exe wrapper's `>>` redirect onto one shared log failed with
    0x80070001 on every trigger while an orphaned python child held that log open.
    """
    text = INSTALLER.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "cmd.exe" not in code and ">>" not in code
    assert "--log-dir" in code and "-WorkingDirectory" in code
    assert "merge_hypotheses.py" in code


def test_the_time_limit_is_a_backstop_above_a_healthy_run() -> None:
    """Healthy runs measure about 27 h; the limit must never end one, only beat the 72 h default."""
    import re

    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r"-ExecutionTimeLimit \(New-TimeSpan -Hours (\d+)\)", text)
    assert m, "the installer must set an ExecutionTimeLimit"
    assert 27 < int(m.group(1)) < 72


def test_the_manifest_declares_the_task_with_its_installer() -> None:
    manifest = (Path(__file__).resolve().parents[1] / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    line = next(ln for ln in manifest.splitlines() if 'name="MT5-MergeDocket"' in ln)
    assert 'installer="desks/mt5/scripts/install_mergedocket_task.ps1"' in line
    assert 'trigger="every 30 minutes"' in line
