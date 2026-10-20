"""The tick tape's freshness fence, its contract and the recorder's clock (2026-10-14).

MT5-TickRecorder returned 1 at 2026-10-12 19:56 box time and never ran again: boot/logon
triggers only, no organ contract, and a pull window that ended at UTC-now on a venue clock two or
three hours ahead. These pin: a symbol over 2 h old inside ITS OWN session is RED (one dead
symbol among live ones included, and a crypto CFD at the weekend), an absent, unstamped or future
stamp is UNMEASURED (and RED), a shut session is not RED, the contract reads the tape's own stamp,
the recorder stamps every symbol on the broker's clock, and the leg is wired, contracted and
published (per-symbol, per-session judgement: audit 2026-10-20).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
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


#: Sessions by registry class -- the fallback the fence uses when a symbol has no H1 bars.
SESS = {"EURUSD": fence.class_slots("Forex"), "XAUUSD": fence.class_slots("Metals"),
        "BTCUSD": fence.class_slots("Crypto")}


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


def _ages(tmp: Path, now: datetime, **age_h: float) -> Path:
    """Both tapes, each symbol's newest tick `age_h[sym]` hours before `now`."""
    ms = {sym: _broker_ms(now - timedelta(hours=a)) for sym, a in age_h.items()}
    return _desk(tmp, {"state": "RECORDING", "symbols_last_tick_ms": ms},
                 {sym: {"last_tick_ms": v} for sym, v in ms.items()})


def _build(desk: Path, now: datetime) -> dict:
    return fence.build(desk, now, sess=SESS)


def test_a_fresh_tape_is_green(tmp_path: Path) -> None:
    rep = _build(_ages(tmp_path, WED, EURUSD=0.2, XAUUSD=0.1, BTCUSD=0.0), WED)
    assert rep["status"] == "GREEN", rep
    assert {r["status"] for r in rep["tapes"]} == {"FRESH"}
    # The venue stamp was converted: a raw read would sit three hours in the future.
    assert abs(rep["tapes"][0]["symbols"]["EURUSD"]["age_h"] - 0.2) < 0.01


def test_over_two_hours_in_its_own_session_is_red(tmp_path: Path) -> None:
    rep = _build(_ages(tmp_path, WED, EURUSD=2.5, XAUUSD=2.5, BTCUSD=2.5), WED)
    assert rep["status"] == "RED" and set(rep["red"]) == {"bronze", "silver"}
    assert {r["status"] for r in rep["tapes"]} == {"STALE"}


def test_one_dead_symbol_among_live_ones_is_red_and_named(tmp_path: Path) -> None:
    """Audit: the newest tick over every symbol let one live symbol hide 244 dead ones."""
    rep = _build(_ages(tmp_path, WED, EURUSD=0.1, XAUUSD=5.0, BTCUSD=0.0), WED)
    assert rep["status"] == "RED"
    for row in rep["tapes"]:
        assert row["status"] == "STALE" and row["stale"] == ["XAUUSD"]
        assert row["counts"] == {"FRESH": 2, "STALE": 1}


def test_a_weekend_with_crypto_live_and_fx_shut(tmp_path: Path) -> None:
    """Audit: the FX calendar read GREEN all weekend while the crypto CFDs trade."""
    sat = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    fri_close = datetime(2026, 10, 16, 20, 59, tzinfo=UTC)
    fx = (sat - fri_close).total_seconds() / 3600
    live = _build(_ages(tmp_path / "a", sat, EURUSD=fx, XAUUSD=fx, BTCUSD=0.1), sat)
    assert live["status"] == "GREEN"
    row = live["tapes"][0]
    assert row["counts"] == {"CLOSED": 2, "FRESH": 1} and "EURUSD" not in row["symbols"]
    dead = _build(_ages(tmp_path / "b", sat, EURUSD=fx, XAUUSD=fx, BTCUSD=fx), sat)
    assert dead["status"] == "RED" and dead["tapes"][0]["stale"] == ["BTCUSD"]


def test_every_session_shut_is_market_closed_not_red(tmp_path: Path) -> None:
    sat = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    rep = fence.build(_ages(tmp_path, sat, EURUSD=15.0), sat, sess={"EURUSD": SESS["EURUSD"]})
    assert rep["status"] == "GREEN"
    assert {r["status"] for r in rep["tapes"]} == {"MARKET_CLOSED"}


def test_sunday_open_is_measured_from_the_open_not_friday(tmp_path: Path) -> None:
    fri_close = datetime(2026, 10, 16, 20, 59, tzinfo=UTC)
    sun = datetime(2026, 10, 18, 22, 0, tzinfo=UTC)          # one hour after the FX open
    ms = _broker_ms(fri_close)
    desk = _desk(tmp_path, {"symbols_last_tick_ms": {"EURUSD": ms}},
                 {"EURUSD": {"last_tick_ms": ms}})
    one = {"EURUSD": SESS["EURUSD"]}
    assert fence.build(desk, sun, sess=one)["status"] == "GREEN"
    assert fence.build(desk, sun + timedelta(hours=1, minutes=30), sess=one)["status"] == "RED"


@pytest.mark.parametrize("now,open_", [
    (datetime(2026, 10, 16, 20, 59, tzinfo=UTC), True),      # NY Fri 16:59 (daylight time)
    (datetime(2026, 10, 16, 21, 0, tzinfo=UTC), False),
    (datetime(2026, 10, 18, 20, 59, tzinfo=UTC), False),
    (datetime(2026, 10, 18, 21, 0, tzinfo=UTC), True),       # NY Sun 17:00
    (datetime(2026, 11, 13, 21, 59, tzinfo=UTC), True),      # winter: NY Fri 16:59
    (datetime(2026, 11, 13, 22, 0, tzinfo=UTC), False),
])
def test_the_fx_class_week_is_new_york_sunday_17_to_friday_17(now: datetime, open_: bool) -> None:
    v_now = now.replace(tzinfo=None) + fence.venue_lead(now)
    assert (fence.session_open(fence.class_slots("Forex"), v_now) is not None) is open_


def test_a_symbols_session_is_read_from_its_own_bars(tmp_path: Path) -> None:
    """No hard-coded list: the slots come from the symbol's own H1 bars, else its class."""
    idx = pd.date_range("2026-08-17", "2026-10-16 23:00", freq="h")
    idx = idx[(idx.weekday < 5) & (idx.hour >= 1) & (idx.hour < 23)]     # a 01-23 venue index
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    pd.DataFrame({"close": 1.0}, index=idx).to_parquet(uni / "US500_H1.parquet")
    (uni / "universe.json").write_text(json.dumps(
        {"US500": {"asset_class": "Indices"}, "ETHUSD": {"asset_class": "Crypto"}}), "utf-8")
    sess = fence.sessions(tmp_path, WED)
    assert 0 not in sess["US500"] and 1 in sess["US500"] and 23 not in sess["US500"]
    assert 5 * 24 + 1 not in sess["US500"]                    # Saturday
    assert sess["ETHUSD"] == set(range(168))
    assert json.loads((tmp_path / fence.SESSION_CACHE).read_text("utf-8"))["symbols"]["US500"]
    # Enrolment is the tape's: a registry symbol the tape never carried is counted, not RED.
    rep = fence.build(_ages(tmp_path, WED, ETHUSD=0.1), WED)
    assert rep["status"] == "GREEN" and rep["tapes"][0]["not_enrolled"] == ["US500"]


def test_an_absent_tape_is_unmeasured_and_red(tmp_path: Path) -> None:
    ms = _broker_ms(WED - timedelta(minutes=10))
    rep = _build(_desk(tmp_path, {"symbols_last_tick_ms": {"EURUSD": ms}}, None), WED)
    row = {r["tape"]: r for r in rep["tapes"]}["silver"]
    assert row["status"] == "UNMEASURED" and rep["status"] == "RED"
    assert rep["n_unmeasured"] == 1


def test_an_unstamped_tape_is_unmeasured(tmp_path: Path) -> None:
    rep = _build(_desk(tmp_path, {"state": "RECORDING", "last_tick_ms": None},
                       {"EURUSD": {"last_run": "2026-10-14T05:00:00+00:00"}}), WED)
    assert [r["status"] for r in rep["tapes"]] == ["UNMEASURED", "UNMEASURED"]
    assert rep["status"] == "RED"


def test_a_bronze_status_without_per_symbol_stamps_is_unmeasured(tmp_path: Path) -> None:
    """The pre-audit bronze shape carried one newest stamp; it cannot be judged per symbol."""
    ms = _broker_ms(WED - timedelta(minutes=5))
    rep = _build(_desk(tmp_path, {"state": "RECORDING", "last_tick_ms": ms},
                       {"EURUSD": {"last_tick_ms": ms}}), WED)
    assert [r["status"] for r in rep["tapes"]] == ["UNMEASURED", "FRESH"]


def test_a_future_stamp_is_unmeasured_never_fresh(tmp_path: Path) -> None:
    rep = _build(_ages(tmp_path, WED, EURUSD=-1.0), WED)
    assert {r["status"] for r in rep["tapes"]} == {"STALE"}
    assert rep["tapes"][0]["unmeasured"] == ["EURUSD"]
    assert rep["status"] == "RED"


def test_a_red_tape_names_the_terminal_link_as_its_cause(tmp_path: Path) -> None:
    desk = _ages(tmp_path, WED, EURUSD=30.0)
    rep = _build(desk, WED)
    assert rep["terminal_link"]["status"] == "UNMEASURED" and "IPC probe" in rep["cause"]
    ok = desk / "data" / "terminal_boot_ok.json"
    ok.write_text("\ufeff" + json.dumps({"at": (WED - timedelta(hours=50)).isoformat()}), "utf-8")
    rep = _build(desk, WED)
    assert rep["status"] == "RED" and rep["terminal_link"]["status"] == "DOWN"
    assert "MT5 Python link is down" in rep["cause"]
    ok.write_text(json.dumps({"at": (WED - timedelta(minutes=5)).isoformat()}), "utf-8")
    (desk / "reports" / "TAPE_RECORDER.json").write_text(json.dumps(
        {"symbols_last_tick_ms": {"EURUSD": _broker_ms(WED - timedelta(hours=30))},
         "paused_reason": "source not connected"}), "utf-8")
    assert "PAUSED: source not connected" in _build(desk, WED)["cause"]
    assert _build(_ages(tmp_path / "f", WED, EURUSD=0.1), WED)["cause"] == ""


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


def test_the_recorder_stamps_every_symbols_newest_tick(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from recorders import tick_recorder
    from recorders.tick_recorder import RecorderConfig, TickRecorder, _newest_tick
    from recorders.tick_source import FakeTickSource
    status = tmp_path / "TAPE_RECORDER.json"
    monkeypatch.setattr(tick_recorder, "STATUS", status)
    t0 = 1_780_000_000_000
    src = FakeTickSource(["EURUSD", "GBPUSD"], ticks_per_day=20_000)
    src.server_clock_ms = t0 + 3 * 3_600_000
    rec = TickRecorder(src, RecorderConfig(tape_root=tmp_path / "tape", cold_start_days=1,
                                           disk_floor_bytes=0, measure_broker_clock=True))
    rep = rec.run_once(now_ms=t0)
    assert rep.ticks > 0 and rep.clock_source == "broker"
    state = rec.store.read_state("recorder")
    # Windows end at the BROKER's measured now; liveness stays on the wall clock.
    assert state["last_cycle_end_ms"] == t0 + 3 * 3_600_000 - rec.config.settle_ms
    assert state["last_cycle_finished_ms"] < t0 + 3_600_000
    doc = json.loads(status.read_text("utf-8"))
    assert set(doc["symbols_last_tick_ms"]) == {"EURUSD", "GBPUSD"}
    assert all(v > 0 for v in doc["symbols_last_tick_ms"].values())
    assert doc["clock_source"] == "broker"
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
