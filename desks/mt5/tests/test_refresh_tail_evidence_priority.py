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
