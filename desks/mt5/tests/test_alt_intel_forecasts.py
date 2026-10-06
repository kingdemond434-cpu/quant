"""The alt-data allocation intel has a proven reader: scoreable beliefs, graded on the bars."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import alt_intel_forecasts as F  # noqa: E402

from libs.data import dataset_use as U  # noqa: E402


def _intel(tilt: float, as_of: str) -> dict:
    return {"instruments": {"AUDUSD": {"tilt": tilt, "as_of": as_of, "components": [
        {"source": "kr_exports", "series": "exports", "available_time": "2026-10-01T00:00:00+00:00"}]}}}


def test_one_belief_per_tilt_date_and_bounded_probability(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "USE_DIR", tmp_path / "use")
    reg = tmp_path / "register.jsonl"
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    doc = F.run(tmp_path, _intel(9.0, "2026-10-01"), lambda s: None, now=now, register=reg)
    assert doc["published_this_pass"] == {"accepted": 1, "refused": 0}
    row = json.loads(reg.read_text().splitlines()[0])
    assert row["value"] == 0.6 and row["kind"] == "PROBABILITY"
    again = F.run(tmp_path, _intel(9.0, "2026-10-01"), lambda s: None,
                  now=now + timedelta(hours=1), register=reg)
    assert again["published_this_pass"]["accepted"] == 0
    assert "alt_proxies:kr_exports:exports" in U.census()
    assert again["skill"]["status"] == "UNMEASURED"


def test_matured_beliefs_are_graded_against_the_bars(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "USE_DIR", tmp_path / "use")
    reg = tmp_path / "register.jsonl"
    t0 = datetime(2026, 10, 1, 12, tzinfo=UTC)
    F.run(tmp_path, _intel(3.0, "2026-10-01"), lambda s: None, now=t0, register=reg)
    idx = pd.date_range(t0 - timedelta(days=1), periods=24 * 10, freq="h", tz="UTC")
    close = pd.Series([1.0 + i * 1e-3 for i in range(len(idx))], index=idx)    # rises
    doc = F.run(tmp_path, {"instruments": {}}, lambda s: close,
                now=t0 + timedelta(days=6), register=reg)
    assert doc["resolved_this_pass"] == 1
    assert doc["skill"]["status"] == "MEASURED"
    assert doc["skill"]["brier"] == round((0.6 - 1.0) ** 2, 6)
    assert doc["skill"]["skill_vs_climatology"] > 0
