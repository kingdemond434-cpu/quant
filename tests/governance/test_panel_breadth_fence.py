"""L1.62 fence -- a power figure whose denominator was assumed is not a measurement.

These tests fail if the fence's wiring is removed. The two that matter most pin the REFUSAL:
an empty scan set must never read OK (L1.28a / WS-005), and an over-claimed cell must fail even
though it looks like every other passing cell from the outside.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SRC = ROOT / "scripts/check_panel_breadth.py"


def _load(monkeypatch: pytest.MonkeyPatch, root: Path) -> Any:
    """Import the fence with its ROOT pointed at a temporary tree."""
    spec = importlib.util.spec_from_file_location("check_panel_breadth_under_test", _SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "_OUT", root / "data/panel_breadth_coverage.json")
    return mod


def _cell(**kw: Any) -> dict[str, Any]:
    base = {"name": "axis::c::h1d", "verdict": "SCREEN-UNDERPOWERED", "panel_width": 139,
            "powered": False, "n_eff": 1000.0, "min_detectable_ic": 0.062,
            "breadth_basis": "MEASURED", "xs_neff": 93.0}
    base.update(kw)
    return base


def _write(root: Path, rel: str, doc: Any) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def test_an_empty_scan_set_is_unmeasured_never_ok(monkeypatch, tmp_path):
    """THE REFUSAL. Zero panel cells means the fence verified nothing, and must say so.

    This is WS-005, the desk's most-repeated defect class: absence resolving to a clean verdict.
    A fence that returns OK here would report "every panel is measured" from a run that looked
    at no panels at all.
    """
    (tmp_path / "data").mkdir()
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "UNMEASURED"
    assert rep["n_panel_cells"] == 0
    assert rep["coverage"] is None
    assert "UNMEASURED" not in mod._PASSING
    assert mod.fence_exit(rep["status"], mod._PASSING, scanned=rep["n_examined"] or 1,
                          of="t", fence="t") != 0


def test_a_powered_claim_on_an_unmeasured_basis_fails(monkeypatch, tmp_path):
    """THE FAILURE: a refutation banked against a sample size nobody measured."""
    _write(tmp_path, "data/s.json", [_cell(breadth_basis="UNMEASURED", powered=True,
                                           verdict="SCREEN-WEAK")])
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "OVERCLAIMED"
    assert rep["n_overclaimed"] == 1
    assert rep["overclaimed"][0]["breadth_basis"] == "UNMEASURED"
    assert mod.fence_exit(rep["status"], mod._PASSING, scanned=rep["n_examined"],
                          of="t", fence="t") != 0


def test_screen_weak_on_an_absent_basis_also_fails(monkeypatch, tmp_path):
    """A legacy cell with NO breadth key that banked a graveyard-grade refutation.

    `powered` may be absent or false in the artifact while the verdict already spent the claim,
    so the verdict is checked independently of the flag.
    """
    legacy = _cell(verdict="SCREEN-WEAK", powered=False)
    legacy.pop("breadth_basis")
    legacy.pop("xs_neff")
    _write(tmp_path, "data/legacy.json", {"trials": [legacy]})
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "OVERCLAIMED"
    assert rep["overclaimed"][0]["breadth_basis"] == "<absent>"


def test_assumed_but_conservative_cells_are_partial_not_failing(monkeypatch, tmp_path):
    """COVERAGE IS A RATCHET, NOT A CLIFF (L1.0/L1.43).

    An unmeasured cell that claims nothing is a work-queue item, not a breach. A fence that went
    red on every legacy artifact the day it shipped would be switched off.
    """
    _write(tmp_path, "data/s.json", [_cell(breadth_basis="UNMEASURED", powered=False,
                                           verdict="SCREEN-UNDERPOWERED")])
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "PARTIAL"
    assert rep["n_overclaimed"] == 0
    assert rep["coverage"] == 0.0
    assert mod.fence_exit(rep["status"], mod._PASSING, scanned=rep["n_examined"],
                          of="t", fence="t") == 0


def test_fully_measured_reads_ok(monkeypatch, tmp_path):
    _write(tmp_path, "data/s.json", [_cell(), _cell(name="b", panel_width=80, xs_neff=40.0)])
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["status"] == "OK"
    assert rep["coverage"] == 1.0
    assert rep["n_panel_cells"] == 2


def test_single_series_cells_are_not_counted_as_panels(monkeypatch, tmp_path):
    """panel_width=1 has no cross-section to measure and must not dilute the coverage ratio."""
    _write(tmp_path, "data/s.json", [_cell(panel_width=1, breadth_basis="SINGLE-SERIES"),
                                     _cell()])
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["n_single_series"] == 1
    assert rep["n_panel_cells"] == 1
    assert rep["status"] == "OK"


def test_every_artifact_is_counted_once(monkeypatch, tmp_path):
    """L1.60: the denominator must not double-count, which this fence's own first run did.

    `reports/axis_screens` was listed alongside `reports`, so rglob walked every axis-screen
    artifact twice and 48 real cells were reported as 90.
    """
    _write(tmp_path, "reports/axis_screens/s.json", [_cell()])
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "_SCAN", ("reports/axis_screens", "reports"))
    rep = mod.build()
    assert rep["n_examined"] == 1                  # not 2
    assert rep["n_panel_cells"] == 1               # not 2


def test_unreadable_artifacts_stay_in_the_denominator(monkeypatch, tmp_path):
    """L1.60: a file the fence could not read is COUNTED, never silently skipped."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/broken.json").write_text("{not json", "utf-8")
    _write(tmp_path, "data/ok.json", [_cell()])
    mod = _load(monkeypatch, tmp_path)
    rep = mod.build()
    assert rep["n_examined"] == 2
    assert rep["n_unreadable"] == 1


def test_the_fence_declares_a_denominator_at_its_exit_site():
    """L1.57: the exit site is the only place holding both the status and what was scanned."""
    src = _SRC.read_text("utf-8")
    assert "fence_exit(" in src
    assert "scanned=rep[" in src
    assert 'of="' in src
