from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from scripts import derive_walcl_clock as walcl


def _rows(n: int, *, flat: bool = False) -> list[tuple[str, float]]:
    start = date(2025, 1, 1)
    return [
        ((start + timedelta(days=7 * i)).isoformat(), 100.0 if flat else 100.0 + i * i)
        for i in range(n)
    ]


def test_signal_respects_release_lag_history_and_degenerate_refusal() -> None:
    rows = _rows(walcl._MIN_OBS + 2)
    before_last_release = (date.fromisoformat(rows[-1][0]) + timedelta(days=1)).isoformat()
    after_last_release = (date.fromisoformat(rows[-1][0]) + timedelta(days=2)).isoformat()

    assert walcl.signal_for("2025-01-02", rows) is None
    assert walcl.signal_for(before_last_release, rows) is not None
    signal = walcl.signal_for(after_last_release, rows)
    assert signal is not None
    assert signal["date"] == after_last_release
    assert signal["asof"] == rows[-1][0]
    assert walcl.signal_for(after_last_release, _rows(walcl._MIN_OBS + 2, flat=True)) is None


def test_series_is_fail_closed_and_filters_invalid_rows(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "fred.json"
    monkeypatch.setattr(walcl, "_ARCHIVE", archive)
    assert walcl._series() == []

    archive.write_text("{", encoding="utf-8")
    assert walcl._series() == []

    archive.write_text(
        json.dumps(
            {
                "series": {
                    "WALCL": [
                        ["2025-01-08", "102"],
                        ["2025-01-01", 100],
                        ["bad"],
                        ["2025-01-15", "not-a-number"],
                        ["2025-01-22", -2],
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    assert walcl._series() == [("2025-01-01", 100.0), ("2025-01-08", 102.0)]
