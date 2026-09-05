"""The scheduler fence must know about every plane that runs jobs, not just cron.

THE DEFECT (measured 2026-08-29). `scripts/check_scheduler_manifest.py` compared
`ops/crontab.manifest` against `crontab -l` and nothing else. That was complete when it was
written and stopped being complete on 2026-08-20, when root `cron.service` was OOM-killed and the
desk moved its live jobs onto systemd USER timers and `scripts/run_manifest_dispatch.py`. From
that morning the fence emitted 232 identical `DRIFT manifest-only (box does not run it)` lines,
one of them for every row that was in fact running perfectly well under a timer.

That is not a cosmetic problem. A fence whose every line is noise cannot carry the one line that
matters, and the cron death itself hid inside this output for six days -- exactly the outcome
L1.43 predicts for a control that is red from day one. After the fix the same box reports 130
genuinely uncovered rows with 72 attributed to the dispatcher and 30 to installed units.

WHAT THESE TESTS PIN: a row covered by another plane is NOT drift; a row covered by nothing IS;
coverage is claimed from EVIDENCE THAT SOMETHING RAN (the dispatcher's recorded fire, a unit's
ExecStart) and never from the manifest's own say-so; and a dispatcher row that stopped firing
long ago stops counting as coverage -- a dead row with a memory is not an executor.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_ROW_A = "5 * * * * cd <ROOT> && .venv/bin/python scripts/alpha_one.py >> data/a.log 2>&1"
_ROW_B = "7 * * * * cd <ROOT> && .venv/bin/python scripts/beta_two.py >> data/b.log 2>&1"
_ROW_C = "9 * * * * cd <ROOT> && .venv/bin/python scripts/gamma_three.py >> data/c.log 2>&1"


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "check_scheduler_manifest", _ROOT / "scripts" / "check_scheduler_manifest.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the module defines @dataclass types, and dataclasses resolves
    # field annotations through sys.modules[cls.__module__], which is None for a module loaded
    # by spec alone. Without this every test in the file errors in dataclasses.py, not in the
    # code under test.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod() -> ModuleType:
    return _load()


def _write_state(root: Path, rows: dict[str, str]) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "manifest_dispatch_state.json").write_text(
        json.dumps({"rows": {t: {"last_fired": at} for t, at in rows.items()}}), "utf-8")


def test_row_covered_by_dispatcher_is_not_drift(mod: ModuleType, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_unit_scripts", set)
    _write_state(tmp_path, {"scripts/alpha_one.py": datetime.now(UTC).isoformat()})
    uncovered, absorbed = mod.split_by_plane(tmp_path, [_ROW_A, _ROW_B])
    assert uncovered == [_ROW_B]
    assert absorbed["manifest_dispatcher"] == 1


def test_row_covered_by_a_systemd_unit_is_not_drift(mod: ModuleType, tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_unit_scripts", lambda: {"beta_two.py"})
    _write_state(tmp_path, {})
    uncovered, absorbed = mod.split_by_plane(tmp_path, [_ROW_A, _ROW_B])
    assert uncovered == [_ROW_A]
    assert absorbed["systemd_unit"] == 1


def test_row_covered_by_nothing_is_the_real_drift(mod: ModuleType, tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_unit_scripts", lambda: {"beta_two.py"})
    _write_state(tmp_path, {"scripts/alpha_one.py": datetime.now(UTC).isoformat()})
    uncovered, absorbed = mod.split_by_plane(tmp_path, [_ROW_A, _ROW_B, _ROW_C])
    assert uncovered == [_ROW_C], "the only row no plane runs"
    assert absorbed == {"systemd_unit": 1, "manifest_dispatcher": 1}


def test_a_dispatcher_row_that_stopped_firing_stops_covering(mod: ModuleType, tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             ) -> None:
    """Coverage is a claim about NOW. A row that last fired a month ago is a dead row."""
    monkeypatch.setattr(mod, "_unit_scripts", set)
    stale = (datetime.now(UTC) - timedelta(hours=mod._DISPATCH_FRESH_H + 24)).isoformat()
    _write_state(tmp_path, {"scripts/alpha_one.py": stale})
    uncovered, absorbed = mod.split_by_plane(tmp_path, [_ROW_A])
    assert uncovered == [_ROW_A]
    assert absorbed["manifest_dispatcher"] == 0


def test_missing_dispatch_state_covers_nothing(mod: ModuleType, tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """No evidence file means no coverage claim -- absence must not read as covered."""
    monkeypatch.setattr(mod, "_unit_scripts", set)
    uncovered, absorbed = mod.split_by_plane(tmp_path, [_ROW_A, _ROW_B])
    assert uncovered == [_ROW_A, _ROW_B]
    assert absorbed == {"systemd_unit": 0, "manifest_dispatcher": 0}


def test_unparseable_fire_stamp_does_not_grant_coverage(mod: ModuleType, tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_unit_scripts", set)
    _write_state(tmp_path, {"scripts/alpha_one.py": "not-a-timestamp"})
    uncovered, _ = mod.split_by_plane(tmp_path, [_ROW_A])
    assert uncovered == [_ROW_A]
