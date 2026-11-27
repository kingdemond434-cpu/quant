"""The task failure digest: every red task listed with its age, rc and products; expected
disabled tasks marked; shared causes grouped; an absent or broken health file is UNMEASURED.

EVERY INPUT IS A FIXTURE in `tmp_path`: a process_health.json in the schema
`ops/process_health.py` writes, a two-row box_tasks.manifest, one run script and one installer.
"""

from __future__ import annotations

import json
import sys as _sys
from datetime import UTC, datetime
from pathlib import Path
from pathlib import Path as _Path

_DESK = _Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from research import task_failure_digest as tfd  # noqa: E402

NOW = datetime(2026, 10, 21, 3, 30, tzinfo=UTC)


def _proc(name, verdict, *, last_run="", rc=None, why="", artifact=None, age=None, state="Ready"):
    return {
        "name": name,
        "verdict": verdict,
        "why": why,
        "state": state,
        "last_run": last_run,
        "next_run": "",
        "last_result_code": rc,
        "last_result": why,
        "artifact": artifact,
        "artifact_age_min": age,
        "contract_max_age_min": 60 if age is not None else None,
        "purpose": None,
    }


GENERIC = "generic failure (the script itself returned 1)"


def _root(tmp_path: Path, processes=None, *, health_text: str | None = None) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports").mkdir(parents=True)
    (desk / "ops").mkdir()
    (desk / "research").mkdir()
    (desk / "scripts").mkdir()
    (desk / "research" / "alpha.py").write_text(
        'OUT = DESK / "reports" / "ALPHA.json"\nIN_BARS = DESK / "data" / "bars.json"\n',
        encoding="utf-8",
    )
    (desk / "scripts" / "install_beta_task.ps1").write_text(
        "$TaskName = 'MT5-Beta'\n# writes desks/mt5/reports/BETA.json\n", encoding="utf-8"
    )
    (desk / "ops" / "box_tasks.manifest").write_text(
        "# comment\n"
        'TASK name="MT5-Alpha" trigger="hourly" runs="desks/mt5/research/alpha.py" '
        'installer="NONE" lane="research"\n'
        'TASK name="MT5-AdoptRelease" trigger="every 1 hour" runs="x.ps1" installer="NONE" '
        'lane="ops"\n',
        encoding="utf-8",
    )
    hp = desk / "reports" / "process_health.json"
    if health_text is not None:
        hp.write_text(health_text, encoding="utf-8")
    elif processes is not None:
        hp.write_text(
            json.dumps(
                {"at": "2026-10-21T03:00:00+00:00", "host": "fixture", "processes": processes}
            ),
            encoding="utf-8",
        )
    return tmp_path


def _build(root: Path):
    desk = root / "desks" / "mt5"
    return tfd.build(
        desk / "reports" / "process_health.json", desk / "ops" / "box_tasks.manifest", root, now=NOW
    )


def _task(doc, name):
    return next(t for t in doc["tasks"] if t["name"] == name)


def test_missing_health_is_unmeasured_never_ok(tmp_path):
    doc = _build(_root(tmp_path))
    assert doc["status"] == "UNMEASURED"
    assert doc["tasks"] == "UNMEASURED" and doc["counts"] == "UNMEASURED"
    assert "absent" in doc["why"]


def test_unparseable_health_is_unmeasured(tmp_path):
    doc = _build(_root(tmp_path, health_text="{not json"))
    assert doc["status"] == "UNMEASURED" and "unparseable" in doc["why"]


def test_health_without_processes_is_unmeasured(tmp_path):
    doc = _build(_root(tmp_path, health_text=json.dumps({"at": "x"})))
    assert doc["status"] == "UNMEASURED"


def test_lists_only_the_four_red_verdicts_with_age_rc_and_products(tmp_path):
    procs = [
        _proc("MT5-Alpha", "FAILING", last_run="10/21/2026 05:00:01", rc=1, why=GENERIC),
        _proc(
            "MT5-Beta",
            "STALE",
            last_run="10/21/2026 04:00:01",
            rc=0,
            why="old",
            artifact="desks/mt5/reports/BETA.json",
            age=120.0,
        ),
        _proc("MT5-Ok", "OK", last_run="10/21/2026 05:10:01", rc=0),
        _proc("MT5-Gone", "NOT_SCHEDULED", state="ABSENT"),
        _proc("MT5-Unc", "UNCONTRACTED", last_run="10/21/2026 05:00:01", rc=0),
    ]
    doc = _build(_root(tmp_path, procs))
    assert doc["status"] == "ATTENTION"
    assert doc["counts"] == {"FAILING": 1, "STALE": 1, "NOT_SCHEDULED": 1}
    alpha = _task(doc, "MT5-Alpha")
    assert alpha["last_rc"] == 1
    assert alpha["age"]["snapshot_age_min"] == 30.0
    # newest start in the snapshot is MT5-Ok at 05:10:01, same box clock
    assert alpha["age"]["last_run_lag_min"] == 10.0
    assert alpha["age"]["artifact_age_min"] == "UNMEASURED"
    assert alpha["produces"]["artifacts"] == ["desks/mt5/reports/ALPHA.json"]
    assert "desks/mt5/data/bars.json" in alpha["produces"]["referenced_paths"]
    beta = _task(doc, "MT5-Beta")
    assert beta["produces"]["manifest"] == "NOT_IN_MANIFEST"
    assert beta["produces"]["installers_naming_it"] == ["desks/mt5/scripts/install_beta_task.ps1"]
    assert beta["produces"]["artifacts"] == ["desks/mt5/reports/BETA.json"]
    assert beta["age"]["artifact_age_min"] == 120.0
    gone = _task(doc, "MT5-Gone")
    assert gone["last_rc"] == "UNMEASURED"
    assert gone["age"]["last_run_lag_min"] == "UNMEASURED"
    assert gone["produces"]["artifacts"] == "UNMEASURED"


def test_expected_disabled_is_marked_and_others_are_flagged(tmp_path):
    procs = [
        _proc(
            "MT5-AdoptRelease",
            "DISABLED",
            last_run="10/20/2026 18:20:16",
            rc=0,
            state="Disabled",
            why="the scheduler will never start this",
        ),
        _proc(
            "MT5-GatewayResident",
            "DISABLED",
            last_run="10/14/2026 09:22:01",
            rc=0,
            state="Disabled",
            why="the scheduler will never start this",
        ),
    ]
    doc = _build(_root(tmp_path, procs))
    assert _task(doc, "MT5-AdoptRelease")["expected_disabled"] is True
    assert _task(doc, "MT5-GatewayResident")["expected_disabled"] is False
    assert doc["expected_disabled"] == ["MT5-AdoptRelease"]
    assert doc["unexpected_disabled"] == ["MT5-GatewayResident"]


def test_shared_cause_same_error_and_same_start_minute(tmp_path):
    procs = [
        _proc("MT5-Alpha", "FAILING", last_run="10/21/2026 05:00:01", rc=1, why=GENERIC),
        _proc("MT5-Beta", "FAILING", last_run="10/21/2026 05:00:40", rc=1, why=GENERIC),
        _proc(
            "MT5-Gamma",
            "FAILING",
            last_run="10/21/2026 04:12:00",
            rc=2,
            why="ModuleNotFoundError: libs.x",
        ),
        _proc(
            "MT5-Delta",
            "FAILING",
            last_run="10/21/2026 04:47:00",
            rc=2,
            why="ModuleNotFoundError: libs.x",
        ),
    ]
    doc = _build(_root(tmp_path, procs))
    kinds = {(c["kind"], tuple(c["tasks"])): c for c in doc["shared_causes"]}
    weak = kinds[("same_error_text", ("MT5-Alpha", "MT5-Beta"))]
    assert weak["strength"].startswith("WEAK")
    strong = kinds[("same_error_text", ("MT5-Delta", "MT5-Gamma"))]
    assert strong["strength"].startswith("STRONG")
    start = kinds[("same_start_minute_box_clock", ("MT5-Alpha", "MT5-Beta"))]
    assert start["key"] == "2026-10-21 05:00"


def test_no_red_rows_is_ok_with_empty_lists(tmp_path):
    doc = _build(_root(tmp_path, [_proc("MT5-Ok", "OK", last_run="10/21/2026 05:10:01", rc=0)]))
    assert doc["status"] == "OK" and doc["tasks"] == [] and doc["shared_causes"] == []


def test_main_writes_the_report(tmp_path):
    root = _root(
        tmp_path, [_proc("MT5-Alpha", "FAILING", last_run="10/21/2026 05:00:01", rc=1, why=GENERIC)]
    )
    out = tmp_path / "out" / "TASK_FAILURE_DIGEST.json"
    desk = root / "desks" / "mt5"
    rc = tfd.main(
        [
            "--health",
            str(desk / "reports" / "process_health.json"),
            "--manifest",
            str(desk / "ops" / "box_tasks.manifest"),
            "--root",
            str(root),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["schema"] == tfd.SCHEMA and doc["tasks"][0]["name"] == "MT5-Alpha"


def test_error_text_is_a_type_like_head_never_the_verbatim_last_result(tmp_path):
    raw = ("Traceback: ModuleNotFoundError: No module named 'libs.x' in "
           "C:\\opt\\quant\\desks\\mt5\\research\\hourly_cycle.py line 12")
    procs = [
        _proc("MT5-Exc", "FAILING", rc=2, why=raw),
        _proc("MT5-Generic", "FAILING", rc=1, why=GENERIC),
        _proc("MT5-Path", "FAILING", rc=7, why="file not found: /home/quant/x/y.json"),
        _proc("MT5-NoRc", "FAILING", rc=None, why="some prose with no class or code"),
    ]
    doc = _build(_root(tmp_path, procs))
    assert _task(doc, "MT5-Exc")["error_text"] == "ModuleNotFoundError"
    assert _task(doc, "MT5-Generic")["error_text"] == "rc=1"
    assert _task(doc, "MT5-Path")["error_text"] == "rc=7"
    assert _task(doc, "MT5-NoRc")["error_text"] == ""
    text = json.dumps(doc)
    for leak in ("C:\\\\opt", "/home/quant", "No module named", "Traceback"):
        assert leak not in text, leak


def test_error_head_is_capped_at_sixty_characters():
    long_name = "A" * 80 + "Error"
    assert len(tfd.error_head(long_name, 3)) == tfd.ERROR_HEAD_MAX == 60
    assert tfd.error_head("", "5") == "rc=5"
    assert tfd.error_head(None, True) == ""


def test_the_host_name_is_withheld(tmp_path):
    doc = _build(_root(tmp_path, [_proc("MT5-Alpha", "FAILING", rc=1, why=GENERIC)]))
    assert doc["health_host"] in (tfd.HOST_WITHHELD, tfd.UNMEASURED)
