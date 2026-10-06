"""The box writes the broker_swaps panel itself from the terminal's swap fields, and a freshness
report names a stopped capture by its age (2026-10-06: the panel's last file was 2026-09-12)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "side_channels"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import tape  # noqa: E402

T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _terms(at: datetime, eur_long: float = -7.1) -> dict[str, Any]:
    rec = [{"observed_at": at.isoformat(timespec="seconds"), "symbol": s, "swap_long": lo,
            "swap_short": sh, "swap_mode": 1, "swap_rollover3days": 3}
           for s, lo, sh in (("EURUSD", eur_long, 2.3), ("XAUUSD", -40.0, 18.5))]
    return {"observed_at": at.isoformat(timespec="seconds"), "rows": 2, "failures": {},
            "records": rec}


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tape, "SWAP_PANEL", tmp_path / "broker_swaps")
    monkeypatch.setattr(tape, "SWAP_FRESHNESS", tmp_path / "BROKER_SWAPS_FRESHNESS.json")
    return tmp_path


def test_rows_carry_the_terminal_instant_in_the_panel_schema(box: Path) -> None:
    doc = tape.publish_swap_panel(_terms(T0), now=T0)
    files = list((box / "broker_swaps").glob("discoveries_*.json"))
    assert len(files) == 1 and doc["status"] == "FRESH" and doc["n_symbols"] == 2
    rows = json.loads(files[0].read_text())
    assert {r["kind"] for r in rows} == {"swap_table"}
    assert all(r["found_at"] == T0.isoformat(timespec="seconds") for r in rows)
    eur = next(r for r in rows if r["symbols"] == ["EURUSD"])
    assert eur["swap_long"] == -7.1 and eur["swap_mode"] == 1


def test_unchanged_swaps_write_no_panel_until_the_heartbeat(box: Path) -> None:
    tape.publish_swap_panel(_terms(T0), now=T0)
    t1 = T0 + timedelta(hours=1)
    tape.publish_swap_panel(_terms(t1), now=t1)
    assert len(list((box / "broker_swaps").iterdir())) == 1
    t2 = T0 + timedelta(hours=2)
    tape.publish_swap_panel(_terms(t2, eur_long=-6.9), now=t2)       # a reprice writes at once
    t3 = t2 + timedelta(hours=tape.SWAP_HEARTBEAT_H)
    doc = tape.publish_swap_panel(_terms(t3, eur_long=-6.9), now=t3)  # heartbeat
    assert len(list((box / "broker_swaps").iterdir())) == 3
    assert doc["last_capture_at"] == t3.isoformat(timespec="seconds")


def test_a_capture_that_returns_nothing_ages_to_stale_by_name(box: Path) -> None:
    tape.publish_swap_panel(_terms(T0), now=T0)
    later = T0 + timedelta(hours=tape.SWAP_STALE_H + 1)
    doc = tape.publish_swap_panel({"observed_at": later.isoformat(), "records": [],
                                   "failures": {"EURUSD": "symbol_info unavailable"}}, now=later)
    assert doc["status"] == "STALE" and doc["last_capture_at"] == T0.isoformat(timespec="seconds")
    assert doc["n_failures"] == 1


def test_no_capture_ever_is_unmeasured_not_fresh(box: Path) -> None:
    doc = tape.publish_swap_panel({"records": [], "failures": {}}, now=T0)
    assert doc["status"] == "UNMEASURED" and doc["capture_age_h"] is None


def test_the_seed_miner_stamps_the_registry_reading_time(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({
        "EURUSD": {"swap_long": -7.1, "swap_short": 2.3, "updated_at": "2026-09-03T04:40:20+00:00"},
        "GBPUSD": {"swap_long": -5.0, "swap_short": 1.0}}))
    monkeypatch.setattr(seed_miners, "__file__", str(tmp_path / "side_channels" / "seed_miners.py"))
    rows = {r["symbols"][0]: r for r in seed_miners.mine_broker_swaps()}
    assert rows["EURUSD"]["found_at"] == "2026-09-03T04:40:20+00:00"
    assert rows["EURUSD"]["observed_at"] == "2026-09-03T04:40:20+00:00"
    assert "observed_at" not in rows["GBPUSD"]               # unstamped: keeps the copy time
