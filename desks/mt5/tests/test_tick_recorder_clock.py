"""The tick recorders against the broker's clock: the auditor's scenarios (audit 2026-10-20).

The 2026-10-14 fix ended every pull at box-UTC plus the calendar's venue lead. The audit
reproduced two silent losses from that: on the New York fall-back the venue clock drops an hour
below the cursor and the repeated hour was never queried (3,533 of 13,981 ticks on a 24/7
symbol), and a box clock more than 7 s ahead of the broker put the window end past ticks the
broker had not stamped yet (20% lost at +20 s). It also found a hung recorder holds its task slot
forever. Each scenario is replayed here against a deterministic broker that stamps one tick per
second of TRUE time on its own clock and only ever returns ticks it has already stamped.
"""
from __future__ import annotations

import sys
import threading
import types
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders.tick_recorder import (  # noqa: E402
    EXIT_HUNG,
    EXIT_STALLED,
    STATE_CURSORS,
    CycleReport,
    RecorderConfig,
    TickRecorder,
)
from recorders.tick_source import TICK_DTYPE, FakeTickSource  # noqa: E402

H = 3_600_000
#: New York leaves daylight time at 06:00 UTC on Sunday 2025-11-02: venue 09:00 becomes 08:00.
FALL_BACK = int(pd.Timestamp("2025-11-02 06:00", tz="UTC").timestamp() * 1000)
BASE = 1.0
PT = 1e-5


class Broker(FakeTickSource):
    """One tick per second of true time, stamped on the venue clock `stamp(true)`; a query
    returns only ticks already stamped, exactly as `copy_ticks_range` does."""

    def __init__(self, sym: str, t0: int, t1: int, lead) -> None:
        super().__init__([sym])
        self.true = np.arange(t0, t1, 1000, dtype=np.int64)
        self.stamp = np.array([t + lead(int(t)) for t in self.true], dtype=np.int64)
        self.now_true = t0

    def _arr(self, mask: np.ndarray) -> np.ndarray:
        idx = np.nonzero(mask)[0]
        out = np.zeros(idx.size, dtype=TICK_DTYPE)
        out["time_msc"] = self.stamp[idx]
        out["time"] = self.stamp[idx] // 1000
        out["bid"] = np.round(BASE + idx * PT, 5)          # the tick's identity
        out["ask"] = out["bid"] + 10 * PT
        out["flags"] = 6
        return out

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
        seen = self.true <= self.now_true
        return self._arr(seen & (self.stamp >= start_ms) & (self.stamp <= end_ms))

    def server_now_ms(self, symbols: list[str]) -> int | None:
        seen = self.stamp[self.true <= self.now_true]
        return int(seen[-1]) if seen.size else None


def _recorded(rec: TickRecorder, sym: str) -> set[int]:
    got: set[int] = set()
    for day in rec.store.days(sym):
        df = rec.store.read_day(sym, day)
        got |= {round(float((b - BASE) / PT)) for b in df["bid"].to_numpy()}
    return got


def _replay(tmp: Path, lead, t0: int, t1: int, skew_ms: int = 0,
            step_ms: int = 60_000) -> tuple[TickRecorder, Broker, list[CycleReport]]:
    src = Broker("BTCUSD", t0, t1, lead)
    rec = TickRecorder(src, RecorderConfig(tape_root=tmp, cold_start_days=0,
                                           disk_floor_bytes=0, measure_broker_clock=True,
                                           seal_after_hours=48))
    reps = []
    for t in range(t0 + 5_000, t1, step_ms):
        src.now_true = t
        reps.append(rec.run_once(now_ms=t + skew_ms))
    return rec, src, reps


def _expected(src: Broker, from_true: int, to_true: int) -> set[int]:
    return {i for i, t in enumerate(src.true) if from_true <= t <= to_true}


def test_the_fall_back_hour_on_a_24_7_symbol_loses_nothing(tmp_path: Path) -> None:
    def lead(t: int) -> int:
        return 3 * H if t < FALL_BACK else 2 * H

    t0, t1 = FALL_BACK - 30 * 60_000, FALL_BACK + 90 * 60_000
    rec, src, reps = _replay(tmp_path, lead, t0, t1)
    # The step was seen, and seen once.
    steps = [r.clock_stepped_back_ms for r in reps if r.clock_stepped_back_ms]
    assert len(steps) == 1 and 3_500_000 < steps[0] <= 3_600_000
    assert {r.clock_source for r in reps} == {"broker"}
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    missing = want - _recorded(rec, "BTCUSD")
    assert not missing, f"{len(missing)} of {len(want)} ticks lost across the fall-back"
    state = rec.store.read_state("recorder")
    assert state["last_clock_step"]["from_ms"] > state["last_clock_step"]["to_ms"]


def test_a_box_clock_twenty_seconds_ahead_loses_nothing(tmp_path: Path) -> None:
    t0 = int(pd.Timestamp("2026-10-14 06:00", tz="UTC").timestamp() * 1000)
    t1 = t0 + 30 * 60_000
    rec, src, reps = _replay(tmp_path, lambda t: 3 * H, t0, t1, skew_ms=20_000)
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    assert not (want - _recorded(rec, "BTCUSD"))
    # The window ended at the broker's own now, never the box's (which is 20 s past it).
    assert reps[-1].window_ms[1] == src.server_now_ms(["BTCUSD"]) - rec.config.settle_ms
    assert all(r.clock_source == "broker" for r in reps)


def test_an_unmeasurable_broker_falls_back_to_the_late_lossless_bound(tmp_path: Path) -> None:
    src = FakeTickSource(["EURUSD"], ticks_per_day=20_000)
    rec = TickRecorder(src, RecorderConfig(tape_root=tmp_path, cold_start_days=0,
                                           disk_floor_bytes=0, measure_broker_clock=True))
    t0 = 1_780_000_000_000
    rep = rec.run_once(now_ms=t0)
    assert rep.clock_source == "utc" and rep.window_ms[1] == t0 - rec.config.settle_ms
    src.server_clock_ms = t0 + 3 * H
    rep = rec.run_once(now_ms=t0 + 60_000)
    assert rep.clock_source == "broker" and rep.window_ms[1] == t0 + 3 * H - 2_000
    # A broker stamp implausibly far ahead is bounded by the calendar lead plus slack.
    src.server_clock_ms = t0 + 30 * H
    rep = rec.run_once(now_ms=t0 + 120_000)
    assert rep.window_ms[1] <= t0 + 120_000 + 3 * H + 120_000


class _Scripted(TickRecorder):
    """run_once replaced: each call sets the newest tick to the next scripted value."""

    def __init__(self, tmp: Path, newest: list[int], block: threading.Event | None = None):
        super().__init__(FakeTickSource(["X"]), RecorderConfig(tape_root=tmp, cycle_s=0))
        self.newest = list(newest)
        self.block = block

    def run_once(self, now_ms: int | None = None) -> CycleReport:
        if self.block is not None:
            self.block.wait(5)
        v = self.newest.pop(0) if self.newest else 0
        self.store.write_state(STATE_CURSORS, {"X": {"last_tick_ms": v, "active": True}})
        return CycleReport(cycle_id="t", at="", window_ms=(0, 0), symbols_seen=1,
                           symbols_pulled=0)


def test_a_hung_recorder_exits_five_so_the_scheduler_can_restart_it(tmp_path: Path) -> None:
    release = threading.Event()
    rec = _Scripted(tmp_path, [1], block=release)
    codes: list[int] = []

    def fake_exit(code: int) -> None:
        codes.append(code)
        release.set()

    t = threading.Thread(target=rec.run_forever,
                         kwargs={"max_cycles": 1, "sleep": lambda s: None, "hang_s": 0.2,
                                 "exit_fn": fake_exit})
    t.start()
    t.join(10)
    assert codes == [EXIT_HUNG]


def test_a_stalled_recorder_exits_six_and_a_moving_one_does_not(tmp_path: Path) -> None:
    import time
    frozen = _Scripted(tmp_path / "a", [5] * 50)
    code = frozen.run_forever(max_cycles=50, sleep=lambda s: time.sleep(0.02), stall_s=0.1,
                              exit_fn=lambda c: None)
    assert code == EXIT_STALLED
    moving = _Scripted(tmp_path / "b", list(range(1, 21)))
    assert moving.run_forever(max_cycles=20, sleep=lambda s: time.sleep(0.02), stall_s=0.1,
                              exit_fn=lambda c: None) == 0


# ----------------------------------------------------------------- the silver tape (tape.py) --
def test_the_silver_tape_keeps_the_repeated_fall_back_hour(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import tape

    def lead(t: int) -> int:
        return 3 * H if t < FALL_BACK else 2 * H

    t0, t1 = FALL_BACK - 60 * 60_000, FALL_BACK + 90 * 60_000
    src = Broker("BTCUSD", t0, t1, lead)

    fake = types.ModuleType("MetaTrader5")
    fake.COPY_TICKS_ALL = 1

    def copy_ticks_range(sym, start, end, flags):
        s = int(start.timestamp() * 1000)
        e = int(end.timestamp() * 1000)
        return src.ticks(sym, s, e)

    def symbol_info_tick(sym):
        return types.SimpleNamespace(time_msc=src.server_now_ms([sym]))

    fake.copy_ticks_range = copy_ticks_range
    fake.symbol_info_tick = symbol_info_tick
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(tape, "TAPE", tmp_path)
    monkeypatch.setattr(tape, "TICKS", tmp_path / "ticks")
    monkeypatch.setattr(tape, "STATE", tmp_path / "tape_state.json")
    monkeypatch.setattr(tape, "_venue_lead_h",
                        lambda now: lead(src.now_true) // H)
    first = int(src.stamp[0])
    (tmp_path / "tape_state.json").write_text(
        f'{{"BTCUSD": {{"last_tick_ms": {first - 1}, "lead_h": 3}}}}', "utf-8")
    for t in range(t0 + 600_000, t1, 600_000):          # every ten minutes
        src.now_true = t
        tape.record_ticks(["BTCUSD"])
    got: set[int] = set()
    for f in (tmp_path / "ticks" / "BTCUSD").glob("*.parquet"):
        got |= {round(float((b - BASE) / PT)) for b in pd.read_parquet(f)["bid"].to_numpy()}
    want = _expected(src, t0, src.now_true)
    missing = want - got
    assert not missing, f"{len(missing)} of {len(want)} ticks lost across the fall-back"


def test_the_fall_back_instant_is_where_the_calendar_says() -> None:
    from libs.regime.session_clock import utc_offset_h
    before = datetime.fromtimestamp((FALL_BACK - 1000) / 1000, tz=UTC)
    after = datetime.fromtimestamp((FALL_BACK + 1000) / 1000, tz=UTC)
    assert utc_offset_h(before) == 3 and utc_offset_h(after) == 2


# ------------------------------------------------- audit 2026-10-29 (HOLD on 288c77417) --
WED = int(pd.Timestamp("2026-10-14 06:00", tz="UTC").timestamp() * 1000)


class _Glitchy(Broker):
    """The auditor's broker: can drop the terminal, and can misreport its clock for a cycle."""

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.clock_bias: dict[int, int] = {}     # now_true -> ms added to the clock reading
        self.frozen_at: int | None = None

    def server_now_ms(self, symbols: list[str]) -> int | None:
        if not self.is_alive:
            return None
        v = super().server_now_ms(symbols)
        if v is None:
            return None
        if self.frozen_at is not None:
            v = min(v, self.frozen_at)
        return v + self.clock_bias.get(self.now_true, 0)


def _rec(tmp: Path, src: Broker) -> TickRecorder:
    return TickRecorder(src, RecorderConfig(tape_root=tmp, cold_start_days=0,
                                            disk_floor_bytes=0, measure_broker_clock=True,
                                            seal_after_hours=48))


def _gap_rows(rec: TickRecorder, sym: str) -> list[dict]:
    import json
    seen: dict[tuple, dict] = {}
    for f in sorted((rec.store.gaps_dir / sym).glob("*.jsonl")):
        for line in f.read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen[(r["from_ms"], r["to_ms"], r["reason"], r.get("cycle_id"))] = r
    return list(seen.values())


def _run(rec: TickRecorder, src: Broker, t0: int, t1: int, down=None, skip=None,
         step_ms: int = 60_000) -> list[CycleReport]:
    reps = []
    for t in range(t0 + 5_000, t1, step_ms):
        src.now_true = t
        src.is_alive = not (down and down[0] <= t < down[1])
        if skip and skip[0] <= t < skip[1]:
            continue                                    # the recorder is not running at all
        reps.append(rec.run_once(now_ms=t))
    return reps


def test_mf1_a_terminal_outage_is_accounted_on_the_broker_clock(tmp_path: Path) -> None:
    """MF1: v2 wrote 2 of 2 SOURCE_UNAVAILABLE rows reversed (-179/-164 min) and no closing
    row for a 30-minute outage, because the fallback clock was UTC, 3 h behind the broker."""
    t0, t1 = WED, WED + 90 * 60_000
    down = (WED + 30 * 60_000, WED + 60 * 60_000)
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H)
    rec = _rec(tmp_path, src)
    marks = []
    for t in range(t0 + 5_000, t1, 60_000):
        src.now_true = t
        src.is_alive = not (down[0] <= t < down[1])
        rec.run_once(now_ms=t)
        marks.append(rec.store.read_state("recorder")["last_cycle_end_ms"])
    rows = _gap_rows(rec, "BTCUSD")
    assert all(r["to_ms"] >= r["from_ms"] for r in rows), "a reversed gap row"
    su = [r for r in rows if r["reason"] == "SOURCE_UNAVAILABLE"]
    assert su and all(r["to_ms"] > r["from_ms"] for r in su)
    # The closing row is the episode in full, on the broker clock (venue = UTC + 3 h).
    full = max(su, key=lambda r: r["to_ms"] - r["from_ms"])
    assert full["from_ms"] <= down[0] + 3 * H and full["to_ms"] >= down[1] + 3 * H - 62_000
    assert not [r for r in rows if r["reason"] == "RECORDER_DOWN"], "spurious RECORDER_DOWN"
    assert marks == sorted(marks), "last_cycle_end_ms moved backwards"
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    assert not (want - _recorded(rec, "BTCUSD"))


@pytest.mark.parametrize("a_min,b_min", [(-30, 60), (-20, 70)])
def test_mf2_an_outage_across_the_fall_back_loses_nothing_and_is_named(
        tmp_path: Path, a_min: int, b_min: int) -> None:
    """MF2: v2 saw the step only when the clock fell below its last reading, so an hour-long
    outage across the fall-back hid it: 1,738 (-30..+60) and 2,338 (-20..+70) ticks lost, and
    the RECORDER_DOWN row named 08:30-09:00 while the lost ticks were the repeated 08:00-08:30."""
    def lead(t: int) -> int:
        return 3 * H if t < FALL_BACK else 2 * H

    t0, t1 = FALL_BACK - 90 * 60_000, FALL_BACK + 150 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lead)
    rec = _rec(tmp_path, src)
    skip = (FALL_BACK + a_min * 60_000, FALL_BACK + b_min * 60_000)
    reps = _run(rec, src, t0, t1, skip=skip)
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    missing = want - _recorded(rec, "BTCUSD")
    assert not missing, f"{len(missing)} of {len(want)} ticks lost"
    assert len([r for r in reps if r.clock_stepped_back_ms]) == 1
    # The outage row covers the repeated stretch on the new clock and was backfilled.
    rep_lo = FALL_BACK + 2 * H                              # first new-clock stamp
    rep_hi = skip[0] + 3 * H                                # last old-clock stamp recorded
    rows = _gap_rows(rec, "BTCUSD")
    down = [r for r in rows if r["reason"] == "RECORDER_DOWN"]
    assert any(r["from_ms"] <= rep_lo and r["to_ms"] >= rep_hi for r in down), down
    resolved = {(r["from_ms"], r["to_ms"]) for r in rows if r["reason"] == "RESOLVED"}
    assert all((r["from_ms"], r["to_ms"]) in resolved for r in down)


@pytest.mark.parametrize("glitch_s", [10, 30, 59, 90])
def test_s1_a_forward_glitched_stamp_loses_nothing(tmp_path: Path, glitch_s: int) -> None:
    """S1: v2 took the stamp as the window end; +10/+30/+59/+90 s lost 2/22/51/82 of 3,461."""
    t0, t1 = WED, WED + 60 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H)
    src.clock_bias = {t0 + 5_000 + 20 * 60_000: glitch_s * 1000}
    rec = _rec(tmp_path, src)
    _run(rec, src, t0, t1)
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    missing = want - _recorded(rec, "BTCUSD")
    assert not missing, f"{len(missing)} of {len(want)} ticks lost to a +{glitch_s}s stamp"


def test_s1_a_persistent_rise_is_believed_on_the_second_cycle(tmp_path: Path) -> None:
    """The glitch hold must not pin the clock: a lead that RISES and stays (spring-forward) is
    taken on the second cycle, so the window is late by one cycle at most."""
    t0, t1 = WED, WED + 20 * 60_000
    jump = t0 + 5_000 + 10 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 2 * H if t < jump else 3 * H)
    rec = _rec(tmp_path, src)
    reps = _run(rec, src, t0, t1)
    assert reps[-1].window_ms[1] == src.server_now_ms(["BTCUSD"]) - rec.config.settle_ms


def test_s2_a_dip_every_ten_cycles_never_rewinds(tmp_path: Path) -> None:
    """S2: v2 rewound on every dip, unbounded -- 120 rewinds and 82x the disk."""
    t0, t1 = WED, WED + 200 * 60_000
    base = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H)
    rec0 = _rec(tmp_path / "base", base)
    _run(rec0, base, t0, t1)
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H)
    src.clock_bias = {t0 + 5_000 + k * 60_000: -2 * H for k in range(9, 190, 10)}
    rec = _rec(tmp_path / "dip", src)
    reps = _run(rec, src, t0, t1)
    assert sum(1 for r in reps if r.clock_stepped_back_ms) == 0
    b0 = sum(f.stat().st_size for f in (tmp_path / "base").rglob("*") if f.is_file())
    b1 = sum(f.stat().st_size for f in (tmp_path / "dip").rglob("*") if f.is_file())
    assert b1 <= 1.25 * b0, f"{b1 / b0:.1f}x the disk"
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    assert not (want - _recorded(rec, "BTCUSD"))


def test_s2_a_quiet_frozen_clock_never_rewinds(tmp_path: Path) -> None:
    t0, t1 = WED, WED + 40 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H)
    rec = _rec(tmp_path, src)
    reps = []
    for t in range(t0 + 5_000, t1, 60_000):
        src.now_true = t
        quiet = t0 + 10 * 60_000 <= t < t0 + 25 * 60_000
        src.frozen_at = int(src.stamp[(t0 + 10 * 60_000 - t0) // 1000]) if quiet else None
        reps.append(rec.run_once(now_ms=t))
    assert sum(1 for r in reps if r.clock_stepped_back_ms) == 0


def test_s2_a_sustained_large_step_rewinds_at_most_the_cap(tmp_path: Path) -> None:
    t0, t1 = WED, WED + 30 * 60_000
    jump = t0 + 5_000 + 10 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lambda t: 3 * H if t < jump else 0)
    rec = _rec(tmp_path, src)
    reps = _run(rec, src, t0, t1)
    steps = [r.clock_stepped_back_ms for r in reps if r.clock_stepped_back_ms]
    assert steps == [rec.config.clock_rewind_cap_ms]
    st = rec.store.read_state("recorder")["last_clock_step"]
    assert st["from_ms"] - st["cursors_rewound_to_ms"] <= rec.config.clock_rewind_cap_ms + 2_000


def test_s3_the_recorder_follows_a_late_broker_flip(tmp_path: Path) -> None:
    """The measured clock, not the calendar: a broker that flips 30 min after New York does."""
    flip = FALL_BACK + 30 * 60_000

    def lead(t: int) -> int:
        return 3 * H if t < flip else 2 * H

    t0, t1 = FALL_BACK - 30 * 60_000, FALL_BACK + 150 * 60_000
    src = _Glitchy("BTCUSD", t0, t1, lead)
    rec = _rec(tmp_path, src)
    _run(rec, src, t0, t1)
    want = _expected(src, t0 + 70_000, t1 - 70_000)
    assert not (want - _recorded(rec, "BTCUSD"))


def test_s3_the_silver_tape_follows_an_early_broker_flip(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S3: v2's silver rewind followed the calendar; a broker flipping 30 h early lost 3,001 of
    126,000 ticks. The measured offset now drives it."""
    from mt5desk import tape

    flip = FALL_BACK - 30 * H

    def lead(t: int) -> int:
        return 3 * H if t < flip else 2 * H

    t0, t1 = FALL_BACK - 32 * H, FALL_BACK + 3 * H
    src = Broker("BTCUSD", t0, t1, lead)
    fake = types.ModuleType("MetaTrader5")
    fake.COPY_TICKS_ALL = 1
    fake.copy_ticks_range = lambda sym, s, e, f: src.ticks(
        sym, int(s.timestamp() * 1000), int(e.timestamp() * 1000))
    fake.symbol_info_tick = lambda sym: types.SimpleNamespace(
        time_msc=src.server_now_ms([sym]))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(tape, "TAPE", tmp_path)
    monkeypatch.setattr(tape, "TICKS", tmp_path / "ticks")
    monkeypatch.setattr(tape, "STATE", tmp_path / "tape_state.json")
    # The CALENDAR: New York flips at FALL_BACK, 30 h after this broker did.
    monkeypatch.setattr(tape, "_venue_lead_h",
                        lambda now: 3 if now.timestamp() * 1000 < FALL_BACK else 2)
    monkeypatch.setattr(tape, "_utcnow",
                        lambda: datetime.fromtimestamp(src.now_true / 1000, tz=UTC))
    (tmp_path / "tape_state.json").write_text(
        f'{{"BTCUSD": {{"last_tick_ms": {int(src.stamp[0]) - 1}, "lead_h": 3}}}}', "utf-8")
    for t in range(t0 + 600_000, t1, 600_000):
        src.now_true = t
        tape.record_ticks(["BTCUSD"])
    got: set[int] = set()
    for f in (tmp_path / "ticks" / "BTCUSD").glob("*.parquet"):
        got |= {round(float((b - BASE) / PT)) for b in pd.read_parquet(f)["bid"].to_numpy()}
    want = _expected(src, t0, src.now_true)
    missing = want - got
    assert not missing, f"{len(missing)} of {len(want)} ticks lost to an early broker flip"


def test_s1_the_mt5_source_reads_a_robust_clock() -> None:
    """One symbol's forward-glitched `symbol_info_tick` cannot set the clock: second-newest."""
    from recorders import tick_source
    stamps = {"A": 1_000_000, "B": 1_000_500, "C": 1_090_000}        # C is +90 s
    fake = types.SimpleNamespace(
        symbol_info_tick=lambda s: types.SimpleNamespace(time_msc=stamps[s]))
    assert tick_source._robust_clock([stamps[s] for s in stamps]) == 1_000_500
    src = tick_source.Mt5TickSource.__new__(tick_source.Mt5TickSource)
    src._mt5 = lambda: fake                                         # type: ignore[method-assign]
    assert src.server_now_ms(list(stamps)) == 1_000_500
    assert tick_source._robust_clock([5]) == 5 and tick_source._robust_clock([]) is None
