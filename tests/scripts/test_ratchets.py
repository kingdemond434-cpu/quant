"""RATCHET FENCE (constitution L1.0/L2.0) -- the fence that makes 'every metric toward 100%' law
rather than prose.

The load-bearing property is asymmetry: a floor may only RISE. A fence that could lower a floor to
match a regression would launder exactly the failure it exists to catch (the same denominator trick
§34 forbids for coverage). These tests pin that, plus the three defect states -- because a metric
that is unmeasured, unfloored or regressed must never read as a pass.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parents[2] / "scripts/check_ratchets.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_ratchets_probe", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    mod = _load()
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_FLOORS", tmp_path / "data/ratchet_floors.json")
    monkeypatch.setattr(mod, "_OUT", tmp_path / "data/ratchet_report.json")
    # One synthetic metric so the tests do not depend on the real desk's numbers.
    monkeypatch.setattr(mod, "_METRICS", {
        "demo": ("data/demo.json", lambda d: (float(d["v"]) if isinstance(d, dict) else None),
                 None, "python -c pass")})
    monkeypatch.setattr(mod, "_FILE_METRICS", {})
    (tmp_path / "data").mkdir()
    return mod


def _set(tmp_path: Path, v: Any) -> None:
    (tmp_path / "data/demo.json").write_text(json.dumps({"v": v}), "utf-8")


def _floors(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "data/ratchet_floors.json").read_text("utf-8"))


def test_new_metric_without_a_floor_is_a_defect(fence: ModuleType, tmp_path: Path) -> None:
    _set(tmp_path, 0.8)
    rep = fence.evaluate()
    assert rep["rows"][0]["status"] == "NO-FLOOR"      # a number with no floor is a defect
    assert rep["n_bad"] == 1


def test_missing_artifact_is_unmeasured_not_ok(fence: ModuleType) -> None:
    rep = fence.evaluate()
    assert rep["rows"][0]["status"] == "UNMEASURED"    # never a silent pass
    assert rep["n_bad"] == 1


def test_floor_rises_on_improvement(fence: ModuleType, tmp_path: Path) -> None:
    _set(tmp_path, 0.55)
    fence.ratchet_up(fence.evaluate())
    assert _floors(tmp_path)["demo"]["value"] == pytest.approx(0.55)
    _set(tmp_path, 0.90)                              # the 55% -> 90% move, in miniature
    fence.ratchet_up(fence.evaluate())
    assert _floors(tmp_path)["demo"]["value"] == pytest.approx(0.90)


def test_floor_NEVER_lowers_even_when_asked(fence: ModuleType, tmp_path: Path) -> None:
    """THE LOAD-BEARING TEST. A regression must not be laundered into a lower floor."""
    _set(tmp_path, 0.90)
    fence.ratchet_up(fence.evaluate())
    _set(tmp_path, 0.40)                              # a real regression
    rep = fence.evaluate()
    assert rep["rows"][0]["status"] == "REGRESSION"
    fence.ratchet_up(rep)                             # explicitly ask it to record 0.40
    assert _floors(tmp_path)["demo"]["value"] == pytest.approx(0.90)   # floor held


def test_regression_fails_the_check(fence: ModuleType, tmp_path: Path,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    _set(tmp_path, 0.9)
    fence.ratchet_up(fence.evaluate())
    _set(tmp_path, 0.5)
    monkeypatch.setattr("sys.argv", ["check_ratchets.py"])
    assert fence.main() == 1                          # cron-visible
    monkeypatch.setattr("sys.argv", ["check_ratchets.py", "--report-only"])
    assert fence.main() == 0


def test_at_100_is_reported_and_passes(fence: ModuleType, tmp_path: Path) -> None:
    _set(tmp_path, 1.0)
    fence.ratchet_up(fence.evaluate())
    rep = fence.evaluate()
    assert rep["rows"][0]["status"] == "AT-100"
    assert rep["rows"][0]["distance_to_100"] == pytest.approx(0.0)
    assert rep["work_queue"] == []                    # nothing to queue at 100%


def test_work_queue_is_ranked_by_distance_from_100(fence: ModuleType, tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence, "_METRICS", {
        "near": ("data/near.json", lambda d: 0.95 if d else None, None, "cmd"),
        "far": ("data/far.json", lambda d: 0.20 if d else None, None, "cmd"),
    })
    (tmp_path / "data/near.json").write_text('{"v": 1}', "utf-8")   # non-empty: {} is falsy
    (tmp_path / "data/far.json").write_text('{"v": 1}', "utf-8")
    rep = fence.evaluate()
    assert [q["metric"] for q in rep["work_queue"]] == ["far", "near"]


def test_every_row_carries_its_proving_command(fence: ModuleType, tmp_path: Path) -> None:
    # L2.4: a claim without the command that proves it is not a measurement.
    _set(tmp_path, 0.7)
    for row in fence.evaluate()["rows"]:
        assert row["proving_command"]


def test_real_desk_metrics_are_all_declared_with_commands() -> None:
    """Against the REAL fence: every declared metric names an artifact and a proving command."""
    mod = _load()
    declared = {**mod._METRICS, **mod._FILE_METRICS}
    assert len(declared) >= 4
    for name, entry in declared.items():
        artifact, _fn, _max_age, cmd = entry
        assert artifact and cmd, f"{name} missing artifact or proving command"


# --------------------------------------------------------------------- R0104: capability ratchet


def test_capability_wired_reads_the_utilisation_ceiling() -> None:
    """R0104: the engine's own strength is a floored, fenced metric like everything else."""
    from scripts.check_ratchets import _capability_wired
    doc = {"ceilings": [{"name": "deployed_capital", "measured": True, "utilisation": 1.0},
                        {"name": "capability_wired", "measured": True, "utilisation": 0.804}]}
    assert _capability_wired(doc) == 0.804


def test_capability_wired_refuses_an_unmeasured_ceiling() -> None:
    """UNMEASURED must not install a ZERO floor -- a zero floor is a ratchet that permits anything.

    This is the trap the whole registration turns on. L1.28a says unmeasured counts as zero, and
    check_utilisation reports it that way; but feeding that zero to --ratchet would record a floor
    of 0.0, after which capability could collapse to nothing and the fence would still read OK.
    'No reading' and 'a reading of zero' must stay different claims here.
    """
    from scripts.check_ratchets import _capability_wired
    doc = {"ceilings": [{"name": "capability_wired", "measured": False, "utilisation": 0.0}]}
    assert _capability_wired(doc) is None


def test_capability_wired_is_none_when_absent_or_malformed() -> None:
    from scripts.check_ratchets import _capability_wired
    assert _capability_wired({"ceilings": []}) is None
    assert _capability_wired({"ceilings": [{"name": "other", "measured": True}]}) is None
    assert _capability_wired("not a dict") is None
    assert _capability_wired({"ceilings": [{"name": "capability_wired", "measured": True,
                                           "utilisation": "eighty"}]}) is None


def test_capability_wired_is_registered_and_carries_a_staleness_bound() -> None:
    """A metric whose producer died must read STALE, never green on a frozen artifact (L1.44)."""
    from scripts.check_ratchets import _METRICS
    assert "capability_wired" in _METRICS
    artifact, _fn, max_age, cmd = _METRICS["capability_wired"]
    assert artifact == "data/utilisation.json"
    assert max_age is not None and max_age > 0
    assert "check_utilisation" in cmd
