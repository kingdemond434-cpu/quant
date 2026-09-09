"""Duplicate organs across the four scheduler planes (Tier-1 I1): reported, never disabled.

Check (d) already fails a script on two CRON lines under two locks. Nothing saw the same organ
scheduled on two PLANES -- a cron line and a systemd unit, a box task and an hourly leg. Pinned:
rows from all four planes group by the executed file, a group is SERIALISED only when one flock
path covers every line or the script holds its own job lock, everything else is UNSERIALISED,
the verdict never touches the exit code, and the report is written where the reader looks.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.check_scheduler_manifest as c

ROOT = Path(__file__).resolve().parents[2]


def _tree(tmp_path: Path, manifest: str, *, box: str = "", hourly: str = "",
          scripts: dict[str, str] | None = None) -> Path:
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(manifest, "utf-8")
    for rel, body in (scripts or {}).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
    if box:
        p = tmp_path / c._BOX_TASKS_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(box, "utf-8")
    if hourly:
        p = tmp_path / c._HOURLY_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(hourly, "utf-8")
    return tmp_path


_MANIFEST = """# fixture
QUANT_ROOT=/srv/desk
*/5 * * * * cd "$QUANT_ROOT" && flock -n /tmp/a.lock .venv/bin/python scripts/a.py
0 3 * * * cd "$QUANT_ROOT" && flock -n data/.b.lock .venv/bin/python scripts/b.py
0 9 * * * cd "$QUANT_ROOT" && flock -n data/.b.lock .venv/bin/python scripts/b.py
0 1 * * * cd "$QUANT_ROOT" && .venv/bin/python scripts/solo.py
0 6 * * * cd "$QUANT_ROOT" && ops/run_wrap.sh
SYSTEMD unit="quant-a.timer" on="*-*-* 04:00:00" exec="scripts/a.py"
SYSTEMD unit="quant-wrap.timer" on="*-*-* 05:00:00" exec="ops/run_wrap.sh"
"""
_BOX = """# box tasks
TASK name="MT5-Gauntlet" trigger="UNDECLARED" runs="desks/mt5/scripts/gauntlet.py" lane="research"
TASK name="MT5-Hourly" trigger="loop" runs="desks/mt5/research/hourly_cycle.py" lane="research"
TASK name="MT5-Fence" trigger="UNDECLARED" runs="UNKNOWN" installer="NONE" lane="data"
"""
_HOURLY = '''
def deep_forest():
    """The leg's name is not the file's name: resolution reads the callee's body."""
    return _producer("deep_forest_miner", "research/deep_forest_miner.py")


def main():
    _costed("gauntlet", gauntlet)
    _costed("deep_forest", deep_forest)
    _costed("zentech", lambda: _producer("build_zentech_state", "scripts/zentech.py"))
    _costed("wrap", wrap)
    _costed("in_process_only", fn)
    _costed("gauntlet", gauntlet)   # a second call site is the same leg
'''
_SCRIPTS = {
    "scripts/a.py": "print('a')\n",
    "scripts/b.py": "print('b')\n",
    "scripts/solo.py": "print('solo')\n",
    "ops/run_wrap.sh": "#!/bin/bash\nexec flock -n /tmp/wrap.lock python scripts/wrap.py\n",
    "scripts/wrap.py": "print('wrap')\n",
    "desks/mt5/scripts/gauntlet.py": "from research.job_lock import exclusive_job\n"
                                     "with exclusive_job(need_mb=1):\n    pass\n",
    "desks/mt5/research/deep_forest_miner.py": "print('df')\n",
    "scripts/zentech.py": "print('z')\n",
}


def test_rows_come_from_all_four_planes(tmp_path: Path) -> None:
    root = _tree(tmp_path, _MANIFEST, box=_BOX, hourly=_HOURLY, scripts=_SCRIPTS)
    man = c.parse_manifest(root / "ops/crontab.manifest")
    rows, planes = c.schedule_rows(root, man)
    by_plane = {}
    for r in rows:
        by_plane.setdefault(r.plane, []).append(r.script)
    assert sorted(by_plane["cron"]) == ["ops/run_wrap.sh", "scripts/a.py", "scripts/b.py",
                                        "scripts/b.py", "scripts/solo.py"]
    assert sorted(by_plane["systemd"]) == ["ops/run_wrap.sh", "scripts/a.py"]
    assert by_plane["box_task"] == ["desks/mt5/scripts/gauntlet.py",
                                    "desks/mt5/research/hourly_cycle.py"], "UNKNOWN is skipped"
    # a leg resolves to the _producer script in its callee's body or on its own line, to a
    # same-named file, or stays an in-process leg
    assert sorted(by_plane["hourly_leg"]) == ["desks/mt5/research/deep_forest_miner.py",
                                              "desks/mt5/scripts/gauntlet.py",
                                              "hourly_cycle:in_process_only",
                                              "scripts/wrap.py", "scripts/zentech.py"]
    assert [r.lock for r in rows if r.script == "scripts/a.py"] == ["/tmp/a.lock", None]
    assert planes["hourly_cycle"].endswith("5 _costed leg(s)")


def test_verdicts_name_one_lock_or_a_self_lock_and_nothing_else(tmp_path: Path) -> None:
    root = _tree(tmp_path, _MANIFEST, box=_BOX, hourly=_HOURLY, scripts=_SCRIPTS)
    man = c.parse_manifest(root / "ops/crontab.manifest")
    dup = c.check_duplicate_organs(root, man)
    g = dup["groups"]
    assert set(g) == {"a", "b", "gauntlet", "run_wrap"} and "solo" not in g
    assert g["a"]["verdict"] == c.UNSERIALISED and g["a"]["planes"] == ["cron", "systemd"]
    assert "1 distinct flock path(s) across 2 schedules" in g["a"]["why"]
    assert g["b"]["verdict"] == c.SERIALISED and g["b"]["locks"] == ["data/.b.lock"]
    assert g["gauntlet"]["verdict"] == c.SERIALISED
    assert g["gauntlet"]["planes"] == ["box_task", "hourly_leg"]
    assert g["gauntlet"]["self_lock"] == "desks/mt5/scripts/gauntlet.py: job_lock"
    assert g["run_wrap"]["verdict"] == c.SERIALISED and "flock" in g["run_wrap"]["self_lock"]
    assert g["run_wrap"]["planes"] == ["cron", "systemd"] and g["run_wrap"]["locks"] == []
    assert dup["unserialised"] == ["a"] and dup["serialised"] == ["b", "gauntlet", "run_wrap"]
    assert dup["n_duplicated"] == 4 and dup["by_plane"]["hourly_leg"] == 5
    assert "REPORT ONLY" in dup["note"]


def test_two_schedules_and_no_lock_anywhere_is_unserialised(tmp_path: Path) -> None:
    man_text = ('0 1 * * * cd "$QUANT_ROOT" && python scripts/x.py\n'
                'SYSTEMD unit="quant-x.timer" on="*-*-* 02:00:00" exec="scripts/x.py"\n')
    root = _tree(tmp_path, man_text, scripts={"scripts/x.py": "print(1)\n"})
    dup = c.check_duplicate_organs(root, c.parse_manifest(root / "ops/crontab.manifest"))
    assert dup["groups"]["x"]["verdict"] == c.UNSERIALISED
    assert dup["groups"]["x"]["why"].startswith("2 schedules, no flock on any line")
    assert "absent" in dup["planes_read"]["box_tasks"]
    assert "absent" in dup["planes_read"]["hourly_cycle"]


def test_the_verdict_never_touches_the_exit_code_and_the_report_is_written(tmp_path: Path,
                                                                           capsys) -> None:
    man_text = ('0 1 * * * cd "$QUANT_ROOT" && python scripts/x.py\n'
                'SYSTEMD unit="quant-x.timer" on="*-*-* 02:00:00" exec="scripts/x.py"\n')
    root = _tree(tmp_path, man_text, scripts={"scripts/x.py": "print(1)\n"})
    assert c.main(["--root", str(root), "--json"]) == 0
    out = capsys.readouterr().out
    assert "DUPLICATE x: 2 live schedules on cron+systemd -- UNSERIALISED" in out
    assert "reported, never disabled" in out
    written = json.loads((root / c._DUP_REPORT_REL).read_text("utf-8"))
    assert written["unserialised"] == ["x"] and written["generated_utc"]
    report = json.loads((root / "data/scheduler_manifest_report.json").read_text("utf-8"))
    assert report["checks"]["duplicate_organs"] == {
        "ok": False, "n_duplicated": 1, "unserialised": ["x"], "serialised": [],
        "report": c._DUP_REPORT_REL}
    assert report["exit_code"] == 0


def test_the_real_repo_reports_its_known_cross_plane_duplicates() -> None:
    man = c.parse_manifest(ROOT / "ops/crontab.manifest")
    dup = c.check_duplicate_organs(ROOT, man)
    assert dup["by_plane"]["box_task"] >= 20 and dup["by_plane"]["hourly_leg"] >= 50
    g = dup["groups"]
    # external_gauntlet: box task MT5-Gauntlet plus the hourly leg, deliberate, and serialised
    # by its own job lock (Install-QuantWindows.ps1:194-196 says exactly this)
    assert g["external_gauntlet"]["planes"] == ["box_task", "hourly_leg"]
    assert g["external_gauntlet"]["verdict"] == c.SERIALISED
    assert "job_lock" in g["external_gauntlet"]["self_lock"]
    # run_frontier_rotation: four schedules on two planes
    assert g["run_frontier_rotation"]["n_schedules"] >= 4
    assert set(g["run_frontier_rotation"]["planes"]) == {"cron", "systemd"}
