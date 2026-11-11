"""Idea 611: the modelled E[log W] cost of sizing on a stale allocator fraction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research import fraction_staleness_cost as fsc  # noqa: E402

WORLDS = ({"a": 1.0, "b": 1.0}, {"a": 0.2, "b": 0.2})


def _snaps(step: float) -> list[tuple[float, dict[str, float]]]:
    return [(i * 900.0, {"a": 0.01 + step * (i % 2), "b": 0.01}) for i in range(40)]


def test_zero_lag_costs_nothing() -> None:
    doc = fsc.measure(_snaps(0.005), WORLDS)
    assert doc["basis"] == "MODELLED"
    assert doc["by_lag"]["0"]["delta_elogw_per_day"] == 0.0


def test_cost_increases_with_drift() -> None:
    lo = fsc.measure(_snaps(0.002), WORLDS)["by_lag"]["15"]["delta_elogw_per_day"]
    hi = fsc.measure(_snaps(0.008), WORLDS)["by_lag"]["15"]["delta_elogw_per_day"]
    assert hi < lo < 0.0


def test_no_drift_recommends_the_longest_lag() -> None:
    doc = fsc.measure(_snaps(0.0), WORLDS)
    assert doc["recommended_max_age_min"] == 180


def test_missing_input_is_unmeasured() -> None:
    assert fsc.measure([], WORLDS)["status"] == "UNMEASURED"
    doc = fsc.measure(_snaps(0.01), None)
    assert doc["status"] == "UNMEASURED"
    assert doc["recommended_max_age_min"] == "UNMEASURED"
    assert fsc.load_variances(Path("/nonexistent/worlds.npz")) is None


def test_write_is_atomic(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "FRACTION_STALENESS_COST.json"
    seen: list[tuple[str, str]] = []
    real = fsc.os.replace

    def spy(a, b):  # type: ignore[no-untyped-def]
        seen.append((str(a), str(b)))
        real(a, b)

    monkeypatch.setattr(fsc.os, "replace", spy)
    fsc.write_atomic({"report_only": True, "consumer": None}, out)
    assert seen == [(str(out) + ".tmp", str(out))]
    assert json.loads(out.read_text())["report_only"] is True
    assert not (tmp_path / "FRACTION_STALENESS_COST.json.tmp").exists()
