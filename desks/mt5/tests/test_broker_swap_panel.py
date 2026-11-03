"""The box writes the broker_swaps panel itself from the terminal's swap fields -- only on live
terminal evidence -- and a freshness report names a stopped capture by its age (2026-10-06: the
panel's last file was 2026-09-12)."""
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


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _terms(at: datetime, eur_long: float = -7.1, connected: bool = True,
           quote: datetime | None = None, n_requested: int = 2) -> dict[str, Any]:
    q = _iso(quote or at - timedelta(minutes=1))
    rec = [{"observed_at": _iso(at), "symbol": s, "swap_long": lo, "swap_short": sh,
            "swap_mode": 1, "swap_rollover3days": 3, "quote_time_utc": q}
           for s, lo, sh in (("EURUSD", eur_long, 2.3), ("XAUUSD", -40.0, 18.5))]
    return {"observed_at": _iso(at), "rows": 2, "failures": {}, "records": rec,
            "connected": connected, "n_requested": n_requested}


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tape, "SWAP_PANEL", tmp_path / "broker_swaps")
    monkeypatch.setattr(tape, "SWAP_FRESHNESS", tmp_path / "BROKER_SWAPS_FRESHNESS.json")
    monkeypatch.setattr(tape, "SWAP_STATE", tmp_path / "swap_panel_state.json")
    return tmp_path


def _panels(box: Path) -> list[list[dict]]:
    return [json.loads(f.read_text()) for f in sorted((box / "broker_swaps").glob("*.json"))]


def test_rows_carry_value_since_and_terminal_evidence(box: Path) -> None:
    doc = tape.publish_swap_panel(_terms(T0), now=T0)
    (rows,) = _panels(box)
    assert doc["status"] == "FRESH" and doc["n_symbols"] == 2
    assert {r["kind"] for r in rows} == {"swap_table"}
    eur = next(r for r in rows if r["symbols"] == ["EURUSD"])
    assert eur["found_at"] == eur["value_since"] == _iso(T0)
    assert eur["last_evidence_at"] == _iso(T0 - timedelta(minutes=1))
    assert eur["swap_long"] == -7.1 and eur["swap_mode"] == 1


def test_a_heartbeat_keeps_found_at_and_a_reprice_moves_it(box: Path) -> None:
    tape.publish_swap_panel(_terms(T0), now=T0)
    t1 = T0 + timedelta(hours=1)
    tape.publish_swap_panel(_terms(t1), now=t1)                     # unchanged: no new panel
    assert len(_panels(box)) == 1
    t2 = T0 + timedelta(hours=tape.SWAP_HEARTBEAT_H + 1)
    tape.publish_swap_panel(_terms(t2), now=t2)                     # heartbeat
    hb = {r["symbols"][0]: r for r in _panels(box)[-1]}
    assert hb["EURUSD"]["found_at"] == _iso(T0)                     # never a new knowledge time
    assert hb["EURUSD"]["last_evidence_at"] == _iso(t2 - timedelta(minutes=1))
    t3 = t2 + timedelta(hours=1)
    tape.publish_swap_panel(_terms(t3, eur_long=-6.9), now=t3)      # reprice writes at once
    rp = {r["symbols"][0]: r for r in _panels(box)[-1]}
    assert len(_panels(box)) == 3
    assert rp["EURUSD"]["found_at"] == _iso(t3) and rp["XAUUSD"]["found_at"] == _iso(T0)


@pytest.mark.parametrize("terms", [
    _terms(T0, connected=False),                                    # cached values
    _terms(T0, quote=T0 - timedelta(hours=tape.SWAP_QUOTE_MAX_AGE_H + 1)),   # dead quotes
    {**_terms(T0), "records": [{**r, "quote_time_utc": None} for r in _terms(T0)["records"]]},
])
def test_no_live_evidence_writes_no_panel_and_never_reads_fresh(box: Path,
                                                                terms: dict) -> None:
    doc = tape.publish_swap_panel(terms, now=T0)
    assert not (box / "broker_swaps").exists()
    assert doc["status"] == "UNMEASURED" and doc["this_run"]["why_no_capture"]


def test_a_dead_feed_ages_to_stale_by_name(box: Path) -> None:
    tape.publish_swap_panel(_terms(T0), now=T0)
    later = T0 + timedelta(hours=tape.SWAP_STALE_H + 1)
    doc = tape.publish_swap_panel(_terms(later, connected=False), now=later)
    assert doc["status"] == "STALE" and doc["last_capture_at"] == _iso(T0)


def test_a_partial_capture_reads_partial(box: Path) -> None:
    doc = tape.publish_swap_panel(_terms(T0, n_requested=248), now=T0)
    assert doc["status"] == "PARTIAL" and doc["n_expected"] == 248


def test_broker_epoch_converts_on_the_new_york_plus_seven_clock() -> None:
    summer = datetime(2026, 7, 15, 12, 0)            # broker wall time; NY is UTC-4 in July
    sec = int(summer.replace(tzinfo=UTC).timestamp())
    assert tape.broker_epoch_to_utc(sec) == "2026-07-15T09:00:00+00:00"
    winter = int(datetime(2026, 1, 15, 12, 0, tzinfo=UTC).timestamp())
    assert tape.broker_epoch_to_utc(winter) == "2026-01-15T10:00:00+00:00"
    assert tape.broker_epoch_to_utc(0) is None and tape.broker_epoch_to_utc(None) is None


def test_the_seed_miner_stamps_the_registry_reading_time(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({
        "EURUSD": {"swap_long": -7.1, "swap_short": 2.3, "updated_at": "2026-09-03T04:40:20+00:00"},
        "GBPUSD": {"swap_long": -5.0, "swap_short": 1.0}}))
    monkeypatch.setattr(seed_miners, "__file__", str(tmp_path / "side_channels" / "seed_miners.py"))
    rows = {(r["symbols"][0], r["kind"]): r for r in seed_miners.mine_broker_swaps()}
    eur = rows[("EURUSD", "swap_table")]
    assert eur["found_at"] == eur["observed_at"] == "2026-09-03T04:40:20+00:00"
    assert ("GBPUSD", "swap_table") not in rows                 # no reading time: UNMEASURED
    assert ("GBPUSD", "unmeasured") in rows


def test_corrupt_freshness_or_state_files_self_heal_and_never_read_fresher(box: Path) -> None:
    (box / "BROKER_SWAPS_FRESHNESS.json").write_text("[]")
    (box / "swap_panel_state.json").write_text('{"EURUSD": 7}')
    doc = tape.publish_swap_panel(_terms(T0), now=T0)
    assert doc["status"] == "FRESH" and len(_panels(box)) == 1
    later = T0 + timedelta(hours=tape.SWAP_STALE_H + 1)
    (box / "BROKER_SWAPS_FRESHNESS.json").write_text('"garbage"')
    doc = tape.publish_swap_panel(_terms(later, connected=False), now=later)
    assert doc["status"] == "UNMEASURED"              # no trusted previous capture: fails closed


def test_the_broker_clock_converts_without_a_tz_database(monkeypatch: pytest.MonkeyPatch) -> None:
    import zoneinfo

    def missing(key: str) -> None:
        raise zoneinfo.ZoneInfoNotFoundError(key)
    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    for wall, utc in ((datetime(2026, 7, 15, 12, 0), "2026-07-15T09:00:00+00:00"),
                      (datetime(2026, 1, 15, 12, 0), "2026-01-15T10:00:00+00:00"),
                      (datetime(2026, 3, 8, 10, 30), "2026-03-08T07:30:00+00:00"),  # 03:30 EDT
                      (datetime(2026, 3, 8, 8, 30), "2026-03-08T06:30:00+00:00")):  # 01:30 EST
        sec = int(wall.replace(tzinfo=UTC).timestamp())
        assert tape.broker_epoch_to_utc(sec) == utc, wall


def test_a_spring_gap_quote_takes_the_earlier_instant() -> None:
    # 2026-03-08 02:30 New York does not exist; broker wall 09:30 epoch. Fold 0 reads 07:30 UTC
    # (an hour fresher), fold 1 reads 06:30 UTC: the earlier reading can only age the quote.
    sec = int(datetime(2026, 3, 8, 9, 30, tzinfo=UTC).timestamp())
    assert tape.broker_epoch_to_utc(sec) == "2026-03-08T06:30:00+00:00"


def test_the_broker_clock_is_measured_from_the_newest_live_quote(
        monkeypatch: pytest.MonkeyPatch) -> None:
    summer = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    live = summer.timestamp() + 3 * 3600 - 20          # broker = UTC+3, quote 20 s old
    got = tape.broker_clock([live, live - 900, None], summer)
    assert got["verdict"] == "MATCH" and got["observed_offset_h"] == 3
    assert tape.broker_clock([live - 3600], summer)["verdict"] == "MISMATCH"
    weekend = tape.broker_clock([summer.timestamp() - 40 * 3600], summer)
    assert weekend["verdict"] == "UNMEASURED" and weekend["expected_offset_h"] == 3
    assert tape.broker_clock([], summer)["verdict"] == "UNMEASURED"
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    want = tape.broker_clock([winter.timestamp() + 2 * 3600], winter)
    assert want["verdict"] == "MATCH"

    import builtins
    real = builtins.__import__

    def no_tz(name: str, *a: Any, **k: Any) -> Any:
        if name == "zoneinfo":
            raise KeyError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_tz)
    assert tape.broker_clock([winter.timestamp() + 2 * 3600], winter) == want
    assert tape.broker_clock([live], summer)["verdict"] == "MATCH"
