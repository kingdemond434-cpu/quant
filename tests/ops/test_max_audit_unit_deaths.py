"""AN OOM-KILLED SEAT MUST LEAVE A DEFECT, NOT A 58-BYTE LOG (gap-fixer 2026-08-26).

Three gap-wirer seats were OOM-killed in one night; each log held only the attempt header,
byte-identical to an auth failure. The death-visibility drop-in writes unit_deaths.jsonl on
every non-success stop; ``check_unit_deaths`` turns those lines into defects. These tests pin:

  * the drop-in going missing is ITSELF a defect (the fence must not be silently uninstallable),
  * a death inside 24h fires with the unit named,
  * old deaths and the scratch positive-control unit do not fire,
  * no log file with the drop-in installed is genuinely clean (deaths, unlike data, have a
    correct absence).
"""

from __future__ import annotations

import json
import time

from scripts import max_audit


def _setup(monkeypatch, tmp_path, *, dropin: bool, lines: list[dict] | None) -> list:
    dropin_path = tmp_path / "10-death-visibility.conf"
    if dropin:
        dropin_path.write_text("[Service]\n", "utf-8")
    logs = tmp_path / "cro_ai_logs"
    logs.mkdir()
    if lines is not None:
        (logs / "unit_deaths.jsonl").write_text(
            "\n".join(json.dumps(row) for row in lines) + "\n", "utf-8")
    monkeypatch.setattr(max_audit, "_DEATH_DROPIN", dropin_path)
    monkeypatch.setattr(max_audit, "LOGS", logs)
    defects: list = []
    max_audit.check_unit_deaths(defects)
    return defects


def _ts(age_s: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max_audit.NOW - age_s))


def test_missing_dropin_is_a_defect(monkeypatch, tmp_path):
    defects = _setup(monkeypatch, tmp_path, dropin=False, lines=None)
    assert [d[0] for d in defects] == ["unit-deaths-fence-missing"]


def test_recent_death_fires_with_unit_named(monkeypatch, tmp_path):
    row = {"ts": _ts(3600), "unit": "quant-gap-wirer.service",
           "result": "oom-kill", "exit_code": "killed", "exit_status": "15"}
    defects = _setup(monkeypatch, tmp_path, dropin=True, lines=[row])
    assert [d[0] for d in defects] == ["unit-deaths"]
    assert "quant-gap-wirer.service(oom-kill/15)" in defects[0][1]


def test_old_death_and_scratch_unit_are_quiet(monkeypatch, tmp_path):
    rows = [
        {"ts": _ts(48 * 3600), "unit": "quant-gap-wirer.service",
         "result": "oom-kill", "exit_code": "killed", "exit_status": "15"},
        {"ts": _ts(60), "unit": "test-death-visibility.service",
         "result": "exit-code", "exit_code": "exited", "exit_status": "7"},
    ]
    assert _setup(monkeypatch, tmp_path, dropin=True, lines=rows) == []


def test_no_log_with_dropin_installed_is_clean(monkeypatch, tmp_path):
    assert _setup(monkeypatch, tmp_path, dropin=True, lines=None) == []
