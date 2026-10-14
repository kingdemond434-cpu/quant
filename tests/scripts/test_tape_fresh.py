"""The tick tape's freshness fence, its contract and the recorder's clock (2026-10-14).

MT5-TickRecorder returned 1 at 2026-10-12 19:56 box time and never ran again: boot/logon
triggers only, no organ contract, and a pull window that ended at UTC-now on a venue clock two or
three hours ahead. These pin: a tape over 2 h old in FX hours is RED, an absent, unstamped or
future tape is UNMEASURED (and RED), the weekend is not RED, the contract reads the tape's own
stamp, the recorder pulls to the venue's now, and the leg is wired, contracted and published.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fence = _load("check_tape_fresh", "scripts/check_tape_fresh.py")
contract = _load("organ_contract_t", "ops/organ_contract.py")

WED = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)       # US daylight time: venue = UTC + 3 h


def _broker_ms(utc: datetime) -> int:
    """The venue's `time_msc` for a true UTC instant (New York wall time + 7 h)."""
    from libs.regime.session_clock import utc_offset_h
    return int((utc + timedelta(hours=utc_offset_h(utc))).timestamp() * 1000)


def _desk(tmp: Path, bronze: dict | None, silver: dict | None) -> Path:
    if bronze is not None:
        p = tmp / "reports" / "TAPE_RECORDER.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(bronze), "utf-8")
    if silver is not None:
        p = tmp / "data" / "tape" / "tape_state.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(silver), "utf-8")
    return tmp


def _both(tmp: Path, age_h: float, now: datetime = WED) -> Path:
    ms = _broker_ms(now - timedelta(hours=age_h))
    return _desk(tmp, {"last_tick_ms": ms},
                 {"EURUSD": {"last_tick_ms": ms - 5_000}, "XAUUSD": {"last_tick_ms": ms}})


def test_a_fresh_tape_is_green(tmp_path: Path) -> None:
    rep = fence.build(_both(tmp_path, 0.2), WED)
    assert rep["status"] == "GREEN", rep
    assert {r["status"] for r in rep["tapes"]} == {"FRESH"}
    # The venue stamp was converted: a raw read would sit three hours in the future.
    assert abs(rep["tapes"][0]["age_h"] - 0.2) < 0.01


def test_over_two_hours_in_fx_hours_is_red(tmp_path: Path) -> None:
    rep = fence.build(_both(tmp_path, 2.5), WED)
    assert rep["status"] == "RED" and set(rep["red"]) == {"bronze", "silver"}
    assert {r["status"] for r in rep["tapes"]} == {"STALE"}


def test_an_absent_tape_is_unmeasured_and_red(tmp_path: Path) -> None:
    ms = _broker_ms(WED - timedelta(minutes=10))
    rep = fence.build(_desk(tmp_path, {"last_tick_ms": ms}, None), WED)
    row = {r["tape"]: r for r in rep["tapes"]}["silver"]
    assert row["status"] == "UNMEASURED" and rep["status"] == "RED"
    assert rep["n_unmeasured"] == 1


def test_an_unstamped_tape_is_unmeasured(tmp_path: Path) -> None:
    rep = fence.build(_desk(tmp_path, {"state": "RECORDING", "last_tick_ms": None},
                            {"EURUSD": {"last_run": "2026-10-14T05:00:00+00:00"}}), WED)
    assert [r["status"] for r in rep["tapes"]] == ["UNMEASURED", "UNMEASURED"]
    assert rep["status"] == "RED"


def test_a_future_stamp_is_unmeasured_never_fresh(tmp_path: Path) -> None:
    rep = fence.build(_both(tmp_path, -1.0), WED)
    assert {r["status"] for r in rep["tapes"]} == {"UNMEASURED"}
    assert rep["status"] == "RED"


def test_the_weekend_is_market_closed_not_red(tmp_path: Path) -> None:
    sat = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    rep = fence.build(_both(tmp_path, 15.0, sat), sat)
    assert rep["fx_open"] is False and rep["status"] == "GREEN"
    assert {r["status"] for r in rep["tapes"]} == {"MARKET_CLOSED"}


def test_sunday_open_is_measured_from_the_open_not_friday(tmp_path: Path) -> None:
    fri_close = datetime(2026, 10, 16, 21, 0, tzinfo=UTC)
    sun = datetime(2026, 10, 18, 23, 0, tzinfo=UTC)          # one hour after the open
    ms = _broker_ms(fri_close)
    desk = _desk(tmp_path, {"last_tick_ms": ms}, {"EURUSD": {"last_tick_ms": ms}})
    assert fence.build(desk, sun)["status"] == "GREEN"
    assert fence.build(desk, sun + timedelta(hours=1, minutes=30))["status"] == "RED"


@pytest.mark.parametrize("now,open_", [
    (datetime(2026, 10, 16, 21, 59, tzinfo=UTC), True),
    (datetime(2026, 10, 16, 22, 0, tzinfo=UTC), False),
    (datetime(2026, 10, 18, 21, 59, tzinfo=UTC), False),
    (datetime(2026, 10, 18, 22, 0, tzinfo=UTC), True),
])
def test_fx_hours_are_sunday_2200_to_friday_2200(now: datetime, open_: bool) -> None:
    assert fence.fx_open(now) is open_


def test_the_contract_reads_the_tapes_own_stamp(tmp_path: Path) -> None:
    rel = "desks/mt5/reports/TAPE_RECORDER.json"
    assert contract.CONTRACTS["MT5-TickRecorder"][0] == rel
    assert contract.INTERNAL_STAMPS[rel] == "last_tick_utc"
    p = tmp_path / rel
    p.parent.mkdir(parents=True)
    now = datetime.now(UTC)
    # Rewritten this instant (fresh mtime) but carrying a three-hour-old tick: STALE by stamp.
    p.write_text(json.dumps({"at": now.isoformat(),
                             "last_tick_utc": (now - timedelta(hours=3)).isoformat()}), "utf-8")
    age = contract.artifact_age_min(rel, now, root=tmp_path)
    assert age is not None and age > contract.CONTRACTS["MT5-TickRecorder"][1]
    p.write_text(json.dumps({"at": now.isoformat(), "last_tick_utc": None}), "utf-8")
    assert contract.artifact_age_min(rel, now, root=tmp_path) is None     # -> NO_ARTIFACT
    p.write_text(json.dumps({"last_tick_utc": (now + timedelta(hours=3)).isoformat()}), "utf-8")
    assert contract.artifact_age_min(rel, now, root=tmp_path) is None     # future: no artifact


def test_the_recorder_pulls_to_the_venue_clock_and_stamps_its_newest_tick(
        tmp_path: Path) -> None:
    from recorders.tick_recorder import RecorderConfig, TickRecorder, _newest_tick
    from recorders.tick_source import FakeTickSource
    t0 = 1_780_000_000_000
    src = FakeTickSource(["EURUSD"], ticks_per_day=20_000)
    rec = TickRecorder(src, RecorderConfig(tape_root=tmp_path, cold_start_days=0,
                                           server_offset_ms=3 * 3_600_000))
    rec.run_once(now_ms=t0)
    rep = rec.run_once(now_ms=t0 + 60_000)
    state = rec.store.read_state("recorder")
    # Windows end at the VENUE's now; liveness stays on the wall clock.
    assert state["last_cycle_end_ms"] == t0 + 60_000 + 3 * 3_600_000 - rec.config.settle_ms
    assert state["last_cycle_finished_ms"] < t0 + 3_600_000
    assert rep.ticks > 0
    newest = _newest_tick([{"last_tick_ms": 1_788_566_339_990}, {"last_tick_ms": 0}])
    # Friday 2026-09-04 broker 23:58:59.99 is 20:58:59.99 UTC (New York + 7 h, daylight time).
    assert newest["last_tick_utc"].startswith("2026-09-04T20:58:59")
    assert _newest_tick([{"last_tick_ms": 0}])["last_tick_utc"] is None


def test_a_session_zero_recorder_exits_four_and_a_down_terminal_stays_resident(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from recorders import tick_recorder, tick_source

    from research import mt5_session

    class Dead(tick_source.Mt5TickSource):
        def initialize(self) -> bool:
            return False

    monkeypatch.setattr(tick_source, "Mt5TickSource", Dead)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda pid=None: 0)
    assert tick_recorder.main(["--root", str(tmp_path)]) == tick_recorder.EXIT_SESSION_ZERO
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda pid=None: 1)
    ran: list[int] = []
    monkeypatch.setattr(tick_recorder.TickRecorder, "run_forever",
                        lambda self, *a, **k: ran.append(1) or 0)
    assert tick_recorder.main(["--root", str(tmp_path)]) == 0 and ran == [1]


def test_the_runner_returns_the_recorders_exit_and_logs() -> None:
    cmd = (ROOT / "ops" / "run_tick_recorder.cmd").read_text("utf-8")
    code = [ln.strip() for ln in cmd.splitlines()
            if ln.strip() and not ln.lstrip().lower().startswith("rem")]
    assert code[-1] == "exit /b %RC%" and "exit /b 0" not in code
    assert "MT5-TickRecorder.log" in cmd and "recorders.tick_recorder" in cmd
    inst = (ROOT / "desks" / "mt5" / "recorders" / "install_tape_tasks.ps1").read_text("utf-8")
    assert "run_tick_recorder.cmd" in inst and "LogonType Interactive" in inst
    assert "RepetitionInterval (New-TimeSpan -Minutes 10)" in inst


def test_the_tape_module_entry_point_is_last() -> None:
    src = (ROOT / "desks" / "mt5" / "mt5desk" / "tape.py").read_text("utf-8")
    assert src.rstrip().endswith("raise SystemExit(main())")
    assert src.index("def _explain") < src.index('if __name__ == "__main__":')


def test_the_leg_is_wired_contracted_and_published() -> None:
    from libs.research import layers
    assert layers.LEG_LAYER["tape_fresh"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"tape_fresh"' in src and 'scripts/check_tape_fresh.py' in src
    assert '_costed("tape_fresh", tape_fresh)' in src
    contracts = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))["legs"]
    assert contracts["tape_fresh"]["metric"]["organ"] == "report:TAPE_FRESHNESS.json"
    rel = "desks/mt5/reports/TAPE_FRESHNESS.json"
    assert rel in (ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert f"!{rel}" in (ROOT / ".gitignore").read_text("utf-8")
    from libs.ops import release
    assert rel in release.NON_CODE
