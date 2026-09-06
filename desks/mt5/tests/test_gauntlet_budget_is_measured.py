"""The sweep's throttle and its admission ask must be ONE measured number, not two typed ones.

`external_gauntlet` declares `need_mb` at admission and separately throttles itself at
`MEMORY_BUDGET_MB`, and the module's own comment says they are "the SAME number". They were not:
both were the literal 1200 while the sweep's measured working set is 1619MB and 1615MB across the
runs on record.

THE COST OF THE STALE COPY WAS THROUGHPUT, EVERY HOUR. The budget makes the sweep DEFER cells once
its RSS passes the cap, so a cap 400MB below the true working set is reached on every single run:
the sweep stopped early, every time, and judged a fraction of the docket it was given. Measured off
the live dashboard 2026-09-05 -- 8,804 judged and 2,108 unmeasured against a docket of 19,632.
Roughly eight thousand candidates were not reached, by a constant.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_eg", _ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


@pytest.fixture
def peaks(tmp_path, monkeypatch):
    """Write a peak history the module will read when it computes its budget."""
    locks = _ROOT / "desks" / "mt5" / "data" / ".job_locks"
    locks.mkdir(parents=True, exist_ok=True)
    path = locks / "external_gauntlet.peaks.json"
    existing = path.read_text("utf-8") if path.exists() else None

    def write(history: list[int]):
        path.write_text(json.dumps(history), "utf-8")
        return _load()
    yield write
    if existing is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(existing, "utf-8")


def test_the_budget_tracks_the_measured_working_set(peaks) -> None:
    """THE LIVE DEFECT. A sweep that really uses ~1619MB must not throttle itself at 1200."""
    m = peaks([1619, 1615, 1622, 1610, 1600])
    assert m.MEMORY_BUDGET_MB > m.DECLARED_NEED_MB, (
        f"budget {m.MEMORY_BUDGET_MB} is still the declaration {m.DECLARED_NEED_MB} despite a "
        "measured history well above it -- the sweep defers cells on every run for nothing")
    assert 1600 <= m.MEMORY_BUDGET_MB <= 1700


def test_the_declaration_remains_the_floor(peaks) -> None:
    """A LIGHT history may never lower the throttle below what the job declared.

    Downward correction would let one thin docket talk the cap under the working set of a full
    one, and the next full docket then defers everything. The correction is upward-only; only the
    STATISTIC behind it is measured.
    """
    m = peaks([300, 280, 310])
    assert m.MEMORY_BUDGET_MB == float(m.DECLARED_NEED_MB)


def test_an_unmeasurable_box_falls_back_to_the_declaration_never_to_unlimited(monkeypatch) -> None:
    """If the measurement cannot be read, the throttle must still bind.

    The failure mode this forbids is the one the derivation itself nearly introduced: a bad import
    inside the helper was swallowed and silently pinned the budget to the declaration. Silent is
    survivable here only because the fallback is STRICTER than the truth, never looser -- an
    unmeasurable box must not have its throttle removed.
    """
    m = _load()
    monkeypatch.setattr(m, "DECLARED_NEED_MB", 1200)
    monkeypatch.setitem(sys.modules, "research.job_lock", None)
    assert m._measured_budget_mb() >= 1200


def test_the_env_override_still_wins(monkeypatch, peaks) -> None:
    """An operator on a box with different memory must be able to say so, and be believed."""
    monkeypatch.setenv("GAUNTLET_MEMORY_BUDGET_MB", "900")
    m = peaks([4000, 4100, 4200])
    assert m.MEMORY_BUDGET_MB == 900.0


def test_the_admission_ask_uses_the_same_declaration(peaks) -> None:
    """Two literals is how one of them goes stale, which is the whole defect. The ask and the
    throttle must both descend from one constant."""
    src = (_ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "_need = 300 if _REPRO is not None else DECLARED_NEED_MB" in src, (
        "the admission ask has its own literal again")
