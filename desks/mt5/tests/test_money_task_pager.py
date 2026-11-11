"""The money-task time-limit pager and the disk-floor guard (desks/mt5/scripts/money_task_pager.py).

Pins: one kill does not page, two consecutive kills page, a finished run resets the streak, a
re-read of the same run is not a new strike, the page is deduplicated, and the disk floor pages
naming the largest .git pack dirs while deleting nothing.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("money_task_pager", SCRIPTS / "money_task_pager.py")
assert _spec and _spec.loader
mtp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mtp)

import disk_census  # noqa: E402

T0 = datetime(2026, 11, 11, 1, 0, tzinfo=UTC)
KILL, OK = mtp.TIME_LIMIT_KILL, 0


class Pager:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def __call__(self, title: str, body: str) -> dict[str, Any]:
        self.sent.append((title, body))
        return {"armed": 1, "delivered": 1}


def _pass(root: Path, pager: Pager, minute: int, result: int, *, task: str = "E8-Gold",
          free_gb: float = 50.0, now: datetime | None = None) -> dict[str, Any]:
    run_at = (T0 + timedelta(minutes=minute)).isoformat()
    return mtp.run(root, facts={task: {"last_run": run_at, "result": result}}, free_gb=free_gb,
                   packs=lambda: [], sender=pager, now=now or T0 + timedelta(minutes=minute + 4))


def test_one_kill_does_not_page(tmp_path: Path) -> None:
    p = Pager()
    out = _pass(tmp_path, p, 10, KILL)
    assert p.sent == [] and out["streaks"] == {"E8-Gold": 1}


def test_two_consecutive_kills_page(tmp_path: Path) -> None:
    p = Pager()
    _pass(tmp_path, p, 10, KILL)
    out = _pass(tmp_path, p, 15, KILL)
    assert out["killed"] == ["E8-Gold"]
    assert len(p.sent) == 1 and "E8-Gold" in p.sent[0][0] and "267014" in p.sent[0][1]


def test_a_success_resets_the_count(tmp_path: Path) -> None:
    p = Pager()
    _pass(tmp_path, p, 10, KILL)
    _pass(tmp_path, p, 15, OK)
    out = _pass(tmp_path, p, 20, KILL)
    assert p.sent == [] and out["streaks"] == {"E8-Gold": 1}


def test_reading_the_same_run_twice_is_one_strike(tmp_path: Path) -> None:
    p = Pager()
    _pass(tmp_path, p, 50, KILL, task="MT5-FTMO-Allocator")
    out = _pass(tmp_path, p, 50, KILL, task="MT5-FTMO-Allocator", now=T0 + timedelta(minutes=64))
    assert p.sent == [] and out["streaks"] == {"MT5-FTMO-Allocator": 1}


def test_a_running_task_is_not_a_verdict(tmp_path: Path) -> None:
    p = Pager()
    _pass(tmp_path, p, 10, KILL)
    out = _pass(tmp_path, p, 15, mtp.STILL_RUNNING)
    assert p.sent == [] and out["streaks"] == {"E8-Gold": 1}
    _pass(tmp_path, p, 15, KILL)          # that same run, once it ended killed
    assert len(p.sent) == 1


def test_dedup_holds_until_the_repage_window(tmp_path: Path) -> None:
    p = Pager()
    for m in (10, 15, 20, 25):              # four kills in a row: one page
        _pass(tmp_path, p, m, KILL)
    assert len(p.sent) == 1
    _pass(tmp_path, p, 30 + int(mtp.REPAGE_H * 60), KILL)
    assert len(p.sent) == 2


def test_the_money_list_is_one_constant_and_declared_on_the_box(tmp_path: Path) -> None:
    manifest = (SCRIPTS.parent / "ops" / "box_tasks.manifest").read_text("utf-8")
    declared = set(re.findall(r'^TASK name="([^"]+)"', manifest, re.M))
    for must in ("E8-Gold", "MT5-TerminalBoot", "MT5-FTMO-Executor", "MT5-FTMO-Follower",
                 "MT5-FTMO-Allocator", "MT5-AllocatorPulse"):
        assert must in mtp.MONEY_TASKS
    # MT5-Gateway has no manifest row (the resident carries it); every other name is declared.
    assert set(mtp.MONEY_TASKS) - declared <= {"MT5-Gateway"}


# ------------------------------------------------------------------------------- disk floor
def _clone(root: Path, name: str, packs: int, size: int) -> Path:
    pack = root / name / ".git" / "objects" / "pack"
    pack.mkdir(parents=True)
    (root / name / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    for i in range(packs):
        (pack / f"pack-{i}.pack").write_bytes(b"x" * size)
    return pack


def test_pack_dirs_names_the_largest_clone_first_and_deletes_nothing(tmp_path: Path) -> None:
    big = _clone(tmp_path, "gate-repo", 5, 4000)
    _clone(tmp_path / "nested", "quant", 1, 100)
    before = sorted(p.name for p in big.iterdir())
    rows = disk_census.pack_dirs([tmp_path])
    assert [r["path"] for r in rows][0] == str(big)
    assert rows[0]["packs"] == 5 and rows[0]["bytes"] == 20000 and len(rows) == 2
    assert sorted(p.name for p in big.iterdir()) == before


def test_disk_floor_pages_once_with_the_pack_dirs(tmp_path: Path) -> None:
    p = Pager()
    rows = [{"path": r"C:\ProgramData\QuantBox\gate-repo\.git\objects\pack", "gb": 25.0,
             "packs": 52, "bytes": 25 * 1024 ** 3}]
    out = mtp.run(tmp_path, facts={}, free_gb=1.9, packs=lambda: rows, sender=p, now=T0)
    assert len(p.sent) == 1 and "DISK FLOOR" in p.sent[0][0]
    assert "gate-repo" in p.sent[0][1] and "52 packs" in p.sent[0][1]
    assert out["pack_dirs"] == rows
    mtp.run(tmp_path, facts={}, free_gb=1.8, packs=lambda: rows, sender=p,
            now=T0 + timedelta(minutes=10))
    assert len(p.sent) == 1                         # deduplicated inside the repage window


def test_disk_above_floor_is_silent_and_clears(tmp_path: Path) -> None:
    p = Pager()
    mtp.run(tmp_path, facts={}, free_gb=1.9, packs=lambda: [], sender=p, now=T0)
    mtp.run(tmp_path, facts={}, free_gb=mtp.DISK_FLOOR_GB + 1, packs=lambda: [], sender=p,
            now=T0 + timedelta(minutes=10))
    mtp.run(tmp_path, facts={}, free_gb=1.9, packs=lambda: [], sender=p,
            now=T0 + timedelta(minutes=20))
    assert len(p.sent) == 2                         # recovery then a fresh breach pages again


def test_disk_floor_matches_the_ladder_floor() -> None:
    src = (SCRIPTS / "stall_watch.ps1").read_text("utf-8")
    assert f"$DiskFloorGB = {mtp.DISK_FLOOR_GB:g}" in src


def test_a_sender_that_raises_never_breaks_the_pass(tmp_path: Path) -> None:
    def boom(title: str, body: str) -> dict[str, Any]:
        raise RuntimeError("down")
    out = mtp.run(tmp_path, facts={}, free_gb=1.0, packs=lambda: [], sender=boom, now=T0)
    assert out["pages"][0]["delivered"] == 0 and out["pages"][0]["error"] == "RuntimeError"
