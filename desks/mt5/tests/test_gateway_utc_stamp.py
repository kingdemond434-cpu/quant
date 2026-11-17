"""L3 AT THE SOURCE: the gateway's pass stamp is real UTC and its stale-tick guard sees real age.

MetaTrader's `tick.time` is the BROKER wall clock counted in seconds (New York + 7 h: +3 while New
York is on daylight time, +2 otherwise). `gateway.main` built `tnow` from it under a UTC label,
wrote that as `placement_pass` (2-3 h in the future) and measured the stale-tick guard -- "never
trade a closed market" -- against it, so a dead terminal mid-week read 2-3 h younger than it was.

These drive the REAL `gateway.main` against a stub terminal in a subprocess, with the host
timezone set to one that is neither UTC nor the venue's, and with the wall clock frozen once in
New York daylight time (+3) and once in standard time (+2).
"""
from __future__ import annotations

import calendar
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops import gateway_clock as gc  # noqa: E402
from mt5desk.broker_clock import broker_epoch_to_utc  # noqa: E402

DST_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)      # NY daylight time: venue = UTC+3
STD_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)      # NY standard time: venue = UTC+2


def broker_epoch(utc: datetime) -> int:
    """What MetaTrader puts in `tick.time` for a real UTC instant: NY wall clock + 7 h, as
    seconds read as if that wall clock were UTC."""
    wall = utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None) + timedelta(hours=7)
    return calendar.timegm(wall.timetuple())


@pytest.mark.parametrize(("utc", "offset_h"), [(DST_NOW, 3), (STD_NOW, 2)])
def test_a_broker_tick_converts_to_its_true_utc_instant(utc: datetime, offset_h: int) -> None:
    epoch = broker_epoch(utc)
    assert epoch - int(utc.timestamp()) == offset_h * 3600
    at = broker_epoch_to_utc(epoch)
    assert at == utc
    assert at is not None and (utc + timedelta(minutes=40) - at).total_seconds() == 2400.0


_CHILD = r"""
import json, sys, time, types
from datetime import UTC, datetime
from types import SimpleNamespace as NS
from unittest import mock
root, desk, frozen_iso, tick_epoch = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
time.tzset()
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)
stub.symbol_info_tick = lambda sym: NS(bid=2400.0, ask=2400.3, time=tick_epoch)
stub.account_info = lambda: NS(equity=1000.0, balance=1000.0)
stub.shutdown = lambda: None
stub.positions_get = lambda *a, **k: ()
sys.modules["MetaTrader5"] = stub
sys.path[:0] = [root, desk]
import mt5desk.gateway as gw
FROZEN = datetime.fromisoformat(frozen_iso)
class Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN if tz is not None else FROZEN.replace(tzinfo=None)
gw.datetime = Frozen
saved, logs = [], []
class PastTheGuard(Exception):
    pass
def sleeve_set():
    raise PastTheGuard()
gw.gateway_paused = lambda: False
gw.connect = lambda: True
gw.load_state = lambda: {"armed": False, "last_bracket_date": "never", "brackets": {}}
gw.reconcile = lambda st: st
gw.save_state = lambda st: saved.append(json.loads(json.dumps(st, default=str)))
gw.log = logs.append
gw.sleeve_set = sleeve_set
past = False
try:
    gw.main()
except PastTheGuard:
    past = True
print("RESULT " + json.dumps({"past_guard": past, "state": saved[-1] if saved else None,
                              "logs": logs}))
"""


def _drive(tmp_path: Path, now: datetime, tick_utc: datetime) -> dict:
    env = {**os.environ, "MT5_DESK_ROOT": str(tmp_path), "TZ": "Asia/Kolkata",
           "PYTHONPATH": os.pathsep.join([str(_ROOT), str(_DESK)])}
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD, str(_ROOT), str(_DESK), now.isoformat(),
         str(broker_epoch(tick_utc))],
        capture_output=True, text=True, timeout=300, cwd=str(_ROOT), env=env)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line is not None, f"gateway.main did not finish:\n{proc.stderr[-4000:]}"
    out: dict = json.loads(line[len("RESULT "):])
    return out


@pytest.mark.skipif(not hasattr(__import__("time"), "tzset"), reason="needs time.tzset (POSIX)")
@pytest.mark.parametrize(("now", "offset_h"), [(DST_NOW, 3), (STD_NOW, 2)])
def test_a_tick_forty_minutes_old_by_true_utc_trips_the_stale_guard(
        tmp_path: Path, now: datetime, offset_h: int) -> None:
    out = _drive(tmp_path, now, now - timedelta(minutes=40))
    assert out["past_guard"] is False, out["logs"]
    assert any("idle: tick stale 40 min" in str(m) for m in out["logs"]), out["logs"]
    st = out["state"]
    assert st["placement_pass_clock"] == gc.UTC_MARK
    assert datetime.fromisoformat(st["placement_pass"]) == now
    assert st["placement_tick_utc"] == (now - timedelta(minutes=40)).isoformat()
    assert st["broker_utc_offset_h"] == offset_h
    broker_wall = (now - timedelta(minutes=40) + timedelta(hours=offset_h)).replace(tzinfo=None)
    assert st["placement_tick_broker"] == broker_wall.isoformat()
    assert gc.placement_pass_utc(st) == now
    assert gc.clock_verdict(st, now)["verdict"] == "OK"


@pytest.mark.skipif(not hasattr(__import__("time"), "tzset"), reason="needs time.tzset (POSIX)")
@pytest.mark.parametrize("now", [DST_NOW, STD_NOW])
def test_a_fresh_tick_passes_the_guard(tmp_path: Path, now: datetime) -> None:
    """Five minutes old by true UTC: the pass goes on (before the fix it would have too, but a
    guard that also refuses fresh quotes would be a reduction nobody proved)."""
    out = _drive(tmp_path, now, now - timedelta(minutes=5))
    assert out["past_guard"] is True, out["logs"]


def test_clock_verdict_reds_on_a_missing_mark_or_a_future_stamp() -> None:
    now = DST_NOW
    marked = {"placement_pass": now.isoformat(), "placement_pass_clock": "utc",
              "placement_tick_broker": "2026-07-15T15:00:00"}
    assert gc.clock_verdict(marked, now)["verdict"] == "OK"
    unmarked = {k: v for k, v in marked.items() if k != "placement_pass_clock"}
    assert gc.clock_verdict(unmarked, now)["verdict"] == "RED"
    ahead = {**marked, "placement_pass": (now + timedelta(minutes=6)).isoformat()}
    assert gc.clock_verdict(ahead, now)["verdict"] == "RED"
    skew = {**marked, "placement_pass": (now + timedelta(minutes=4)).isoformat()}
    assert gc.clock_verdict(skew, now)["verdict"] == "OK"
    # the regression itself: a broker stamp (+3 h) wearing the utc mark
    broker = {**marked, "placement_pass": (now + timedelta(hours=3)).isoformat()}
    assert gc.clock_verdict(broker, now)["verdict"] == "RED"
    # a pre-fix gateway's file is converted and reported, not failed
    legacy = {"placement_pass": (now + timedelta(hours=3)).isoformat()}
    assert gc.clock_verdict(legacy, now)["verdict"] == "LEGACY"
    assert gc.clock_verdict({}, now)["verdict"] == "UNMEASURED"


def test_the_placement_interlock_fence_goes_red_on_a_mislabelled_clock(tmp_path: Path) -> None:
    sys.path.insert(0, str(_ROOT / "scripts"))
    import check_placement_interlock as cpi
    now = DST_NOW
    gs = tmp_path / "desks" / "mt5" / "data" / "gateway_state.json"
    gs.parent.mkdir(parents=True)
    base_doc = {"ok": True, "verdict": "OK", "problems": [], "notes": []}

    gs.write_text(json.dumps({"placement_pass": (now + timedelta(hours=3)).isoformat(),
                              "placement_pass_clock": "utc"}), "utf-8")
    doc = cpi.apply_clock_check(dict(base_doc, problems=[], notes=[]), tmp_path, now)
    assert doc["ok"] is False and doc["verdict"] == "GATEWAY_CLOCK_RED"

    gs.write_text(json.dumps({"placement_pass": now.isoformat(),
                              "placement_tick_broker": "2026-07-15T15:00:00"}), "utf-8")
    doc = cpi.apply_clock_check(dict(base_doc, problems=[], notes=[]), tmp_path, now)
    assert doc["ok"] is False and doc["gateway_clock"]["verdict"] == "RED"

    gs.write_text(json.dumps({"placement_pass": now.isoformat(), "placement_pass_clock": "utc",
                              "placement_tick_broker": "2026-07-15T15:00:00"}), "utf-8")
    doc = cpi.apply_clock_check(dict(base_doc, problems=[], notes=[]), tmp_path, now)
    assert doc["ok"] is True and doc["verdict"] == "OK"
    assert doc["gateway_clock"]["verdict"] == "OK"
