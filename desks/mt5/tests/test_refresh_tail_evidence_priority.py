from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "scripts"))

import refresh_tail as rt  # noqa: E402


def test_blocked_forward_symbols_refresh_first(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "reports" / "shadow" / "shadow_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "XAUEUR.cross_asset.asia@M5": {"status": "BLOCKED_NO_BARS"},
                "XTIUSD.breakout.asia@H1": {"status": "IDENTITY_BROKEN"},
                "EURUSD.trend.asia@H1": {"status": "ACTIVE"},
                "updated_at": "2026-09-30T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rt, "desk_root", lambda: tmp_path)

    ordered = rt.refresh_order(
        [Path("EURUSD_H1.parquet"), Path("XTIUSD_H1.parquet"), Path("XAUEUR_M5.parquet")]
    )

    assert [p.name for p in ordered[:2]] == ["XAUEUR_M5.parquet", "XTIUSD_H1.parquet"]
    assert ordered[-1].name == "EURUSD_H1.parquet"


def test_atomic_parquet_leaves_no_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "TEST_H1.parquet"
    frame = pd.DataFrame(
        {"close": [1.0, 2.0]},
        index=pd.to_datetime(["2026-09-29T00:00:00Z", "2026-09-29T01:00:00Z"]),
    )

    rt._atomic_parquet(frame, destination)

    assert pd.read_parquet(destination).equals(frame)
    assert not list(tmp_path.glob("*.refreshing"))


def _bars(stamps_h: list[int]) -> pd.DataFrame:
    idx = pd.to_datetime([h * 3600 for h in stamps_h], unit="s", utc=True)
    return pd.DataFrame({"close": range(len(stamps_h))}, index=idx)


def test_a_closed_market_keeps_its_final_bar() -> None:
    # The market closed after the 90h bar; the round-the-clock frontier is forming at 99h.
    kept = rt.drop_forming(_bars([88, 89, 90]), 99 * 3600)
    assert [int(t.timestamp()) // 3600 for t in kept.index] == [88, 89, 90]


def test_an_open_market_drops_only_its_forming_bar() -> None:
    kept = rt.drop_forming(_bars([97, 98, 99]), 99 * 3600)
    assert [int(t.timestamp()) // 3600 for t in kept.index] == [97, 98]


def test_without_a_frontier_the_newest_row_is_dropped_as_before() -> None:
    kept = rt.drop_forming(_bars([88, 89, 90]), None)
    assert [int(t.timestamp()) // 3600 for t in kept.index] == [88, 89]
