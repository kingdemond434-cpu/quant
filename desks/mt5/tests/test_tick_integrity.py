"""The integrity checker, tested by handing it tapes with known defects.

A checker is only worth what it CATCHES, so every test here plants a specific defect and asserts
the verdict names it. The two that matter most are the pair at the bottom: a hole with no gap row
must FAIL, and the identical hole WITH a gap row must not -- because that distinction is the
entire difference between "the market was quiet" and "our recorder was down".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders import tape_store as ts  # noqa: E402
from recorders import tick_integrity as ti  # noqa: E402
from recorders.tick_source import TICK_DTYPE  # noqa: E402

POINT = 1e-5
#: A Wednesday, so the weekday-session machinery is exercised on an ordinary trading day.
BASE_DAY = "2026-05-06"


def _day_ms(day: str) -> int:
    return int(np.datetime64(f"{day}T00:00", "ms").astype("int64"))


def _synth(day: str, minutes: range, per_minute: int = 30) -> np.ndarray:
    """A tick every two seconds across `minutes` of `day`, with a walking mid."""
    stamps: list[int] = []
    d0 = _day_ms(day)
    for m in minutes:
        base = d0 + m * 60_000
        stamps.extend(base + int(60_000 * k / per_minute) for k in range(per_minute))
    t = np.array(sorted(stamps), dtype=np.int64)
    out = np.empty(t.size, dtype=TICK_DTYPE)
    out["time_msc"] = t
    out["time"] = t // 1000
    rng = np.random.default_rng(abs(hash(day)) % 2**32)
    bid_pts = 100_000 + np.cumsum(rng.choice([-1, 0, 1], size=t.size))
    out["bid"] = np.round(bid_pts * POINT, 5)
    out["ask"] = np.round((bid_pts + 12) * POINT, 5)
    out["last"] = 0.0
    out["volume"] = 0
    out["flags"] = 6
    out["volume_real"] = 0.0
    return out


def _write_days(store: ts.TapeStore, sym: str, days: list[str],
                minutes: range = range(0, 1440)) -> None:
    for d in days:
        store.write_segment(sym, d, _synth(d, minutes), POINT, 5)
        store.seal_day(sym, d)


def _weeks(n_weeks: int, weekday_start: str = "2026-04-01") -> list[str]:
    """`n_weeks` occurrences of every weekday, so per-weekday sessions become establishable."""
    import pandas as pd
    start = pd.Timestamp(weekday_start)
    return [(start + pd.Timedelta(days=i)).date().isoformat() for i in range(7 * n_weeks)]


@pytest.fixture
def store(tmp_path: Path) -> ts.TapeStore:
    return ts.TapeStore(tmp_path / "tape")


# ------------------------------------------------------------------ the basics --
def test_a_clean_tape_reads_ok_and_publishes_measured_bytes_per_symbol_day(
        store: ts.TapeStore) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days)
    rep = ti.run(store, ["EURUSD"], days_back=0)
    assert rep["verdict"] == ti.OK, rep["failures"][:1]
    t = rep["totals"]
    assert t["unexplained_minutes"] == 0
    # THE NUMBER THE RETENTION POLICY IS DEFENDED WITH -- measured, not estimated.
    assert t["bytes_per_symbol_day"] > 0 and t["bytes_per_tick"] > 0
    assert rep["by_symbol"]["EURUSD"]["bytes_per_day"] > 0


def test_no_tape_at_all_is_the_loudest_finding_and_not_a_clean_pass(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The desk believes it is recording and there is nothing on disk."""
    rc = ti.main(["--root", str(tmp_path / "nothing"), "--out", str(tmp_path / "o.json")])
    assert rc == 2
    assert "NO TAPE" in capsys.readouterr().out


def test_too_little_history_is_unmeasured_and_never_ok(store: ts.TapeStore) -> None:
    """A session inferred from two days would call a bank holiday a market closure."""
    _write_days(store, "EURUSD", ["2026-05-06", "2026-05-07"])
    rep = ti.run(store, ["EURUSD"], days_back=0)
    assert set(rep["verdicts"]) == {ti.UNMEASURED}
    assert rep["verdict"] == ti.UNMEASURED
    assert "not establishable" in rep["days"][0]["reasons"][0]


# --------------------------------------------------- the distinction that matters --
def test_a_hole_with_no_gap_row_fails_because_a_feature_would_read_it_as_calm(
        store: ts.TapeStore) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days[:-1])
    hole_day = days[-1]
    # Four hours missing out of the middle of an otherwise full day, and NOTHING says why.
    _write_days(store, "EURUSD", [hole_day], minutes=range(0, 600))
    store.write_segment("EURUSD", hole_day, _synth(hole_day, range(840, 1440)), POINT, 5)
    store.seal_day("EURUSD", hole_day)

    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == hole_day)
    assert row["verdict"] == ti.FAIL
    assert row["unexplained_minutes"] >= ti.UNEXPLAINED_FAIL_MIN
    assert any("NO gap row" in r for r in row["reasons"])
    assert rep["verdict"] == ti.FAIL


def test_the_identical_hole_with_a_gap_row_is_explained_and_does_not_fail(
        store: ts.TapeStore) -> None:
    """The same absence, with the desk having recorded WHY. This pair is the whole point of the
    gap ledger: an outage the desk owns up to is data quality, an outage it hides is a lie."""
    days = _weeks(4)
    _write_days(store, "EURUSD", days[:-1])
    hole_day = days[-1]
    _write_days(store, "EURUSD", [hole_day], minutes=range(0, 600))
    store.write_segment("EURUSD", hole_day, _synth(hole_day, range(840, 1440)), POINT, 5)
    d0 = _day_ms(hole_day)
    store.record_gap(ts.GapRecord("EURUSD", d0 + 600 * 60_000, d0 + 840 * 60_000,
                                  ts.GAP_RECORDER_DOWN, "the box rebooted for updates"))
    store.seal_day("EURUSD", hole_day)

    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == hole_day)
    assert row["unexplained_minutes"] == 0, "a recorded gap must account for its own minutes"
    assert row["explained_minutes"] > 200
    assert row["verdict"] != ti.FAIL
    assert row["gap_reasons"].get(ts.GAP_RECORDER_DOWN) == 1


# ------------------------------------------------------- the weekday session bug --
def test_a_short_session_day_is_judged_against_its_own_weekday_not_the_pooled_one(
        store: ts.TapeStore) -> None:
    """REGRESSION. Pooling every day into one session mask made the desk's own Sunday FAIL at
    12.5% coverage, because Sunday quotes from 21:00 and was being judged against a
    Monday-to-Friday session. A checker that reds every weekend is a checker nobody reads."""
    import pandas as pd
    days = _weeks(5)
    for d in days:
        wd = pd.Timestamp(d).weekday()
        if wd == 5:                                   # Saturday: genuinely closed
            continue
        minutes = range(1260, 1440) if wd == 6 else range(0, 1440)   # Sunday opens 21:00
        _write_days(store, "EURUSD", [d], minutes=minutes)

    rep = ti.run(store, ["EURUSD"], days_back=0)
    sundays = [r for r in rep["days"] if pd.Timestamp(r["day"]).weekday() == 6]
    assert sundays, "the fixture must contain Sundays"
    judged = [r for r in sundays if r["session_basis"] == "weekday"]
    assert judged, "Sunday must eventually be judged on Sunday's own history"
    for r in judged:
        assert r["verdict"] == ti.OK, (
            f"Sunday {r['day']} judged {r['verdict']} at coverage {r['coverage_frac']} against a "
            f"{r['session_minutes']}-minute session -- the session is not per weekday")
        assert r["session_minutes"] < 400, "Sunday's denominator must be Sunday's own session"


def test_a_provisional_pooled_session_may_degrade_but_never_fail(store: ts.TapeStore) -> None:
    """A stand-in denominator that can red the gate is a stand-in that will red it every Friday
    close. It reports, it degrades, it does not fail."""
    import pandas as pd
    # One week only: weekdays have 1 observation each, so the pooled fallback is used.
    days = [d for d in _weeks(1) if pd.Timestamp(d).weekday() <= 4]
    _write_days(store, "EURUSD", days[:-1])
    short = days[-1]
    _write_days(store, "EURUSD", [short], minutes=range(0, 300))    # 5h of a 24h session

    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == short)
    assert row["session_basis"] == "pooled"
    assert row["verdict"] != ti.FAIL
    assert any("held at DEGRADED" in r for r in row["reasons"])


def test_the_cold_start_day_is_not_billed_for_hours_before_capture_began(
        store: ts.TapeStore) -> None:
    """The desk never claimed those minutes. Counting them as missing coverage would make the
    first day of every new symbol a permanent FAIL."""
    days = _weeks(4)
    _write_days(store, "EURUSD", days[:-1])
    first = days[-1]
    # Capture begins at 18:00 on this day, and the recorder said so.
    _write_days(store, "EURUSD", [first], minutes=range(1080, 1440))
    store.record_gap(ts.GapRecord("EURUSD", _day_ms(first) + 1080 * 60_000,
                                  _day_ms(first) + 1080 * 60_000, ts.GAP_COLD_START,
                                  "capture begins here"))
    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == first)
    assert row["claimed_minutes"] == 360
    assert row["session_minutes"] <= 360
    assert row["unexplained_minutes"] == 0
    assert row["verdict"] == ti.OK


# ------------------------------------------------------------- structural defects --
def test_a_corrupt_segment_fails_the_day(store: ts.TapeStore) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days)
    bad = days[-1]
    seg = next((store.day_dir("EURUSD", bad)).glob("*.parquet"))
    raw = bytearray(seg.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    seg.write_bytes(bytes(raw))

    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == bad)
    assert row["verdict"] == ti.FAIL
    assert row["corrupt_segments"] == 1


def test_duplicates_crossed_quotes_and_staleness_are_all_measured(store: ts.TapeStore) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days[:-1])
    d = days[-1]
    t = _synth(d, range(0, 1440))
    t["ask"][:50] = t["bid"][:50] - 12 * POINT       # crossed
    t["bid"][100:5000] = t["bid"][100]               # a long stale run
    t["ask"][100:5000] = t["ask"][100]
    store.write_segment("EURUSD", d, t, POINT, 5)
    store.write_segment("EURUSD", d, t[:2000], POINT, 5)   # a deliberate duplicate segment
    store.seal_day("EURUSD", d)

    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == d)
    assert row["crossed"] == 50 and row["crossed_rate"] > 0
    assert row["dup_rows"] == 2000, "the overlap policy's cost must be measured, not assumed"
    assert row["longest_stale_s"] > ti.STALE_RUN_S
    assert row["stale_runs"] >= 1


def test_an_orphan_recovered_at_check_time_is_reported_rather_than_hidden(
        store: ts.TapeStore) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days)
    d = days[-1]
    store.manifest_path("EURUSD", d).unlink()               # crash between rename and manifest
    rep = ti.run(store, ["EURUSD"], days_back=0)
    row = next(r for r in rep["days"] if r["day"] == d)
    assert row["orphans_recovered"] == 1
    assert row["n_ticks"] > 0, "the orphan must be readable after reconciliation"
    assert any("re-registered" in r for r in row["reasons"])


# ------------------------------------------------------------------- the reporting --
def test_the_recorder_status_is_paired_with_the_tape_so_the_two_can_disagree(
        store: ts.TapeStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A recorder claiming RECORDING while the tape has holes is a much worse finding than one
    that says it paused on a disk floor. Reading only the tape cannot tell them apart."""
    _write_days(store, "EURUSD", _weeks(4))
    status = tmp_path / "TAPE_RECORDER.json"
    # Point at an absent file explicitly: the test must assert on the checker, never on whatever
    # a real recorder happens to have left in this checkout's reports directory.
    monkeypatch.setattr(ti, "RECORDER_STATUS", status)
    rep = ti.run(store, ["EURUSD"], days_back=0)
    assert rep["recorder"]["state"] == "NEVER_RAN"
    assert "schedule" in rep["recorder"]["why"], (
        "an empty tape with no recorder is an alarm about the SCHEDULE, not about the tape")

    status.write_text(json.dumps({"at": "2026-05-06T00:00:00+00:00", "state": "PAUSED",
                                  "paused_reason": "disk floor", "symbols_enrolled": 1}))
    monkeypatch.setattr(ti, "RECORDER_STATUS", status)
    rep = ti.run(store, ["EURUSD"], days_back=0)
    assert rep["recorder"]["state"] == "PAUSED"
    assert rep["recorder"]["paused_reason"] == "disk floor"
    assert rep["recorder"]["age_s"] is not None


def test_main_exits_nonzero_on_fail_because_a_report_nobody_reads_is_not_an_alarm(
        store: ts.TapeStore, tmp_path: Path) -> None:
    days = _weeks(4)
    _write_days(store, "EURUSD", days[:-1])
    _write_days(store, "EURUSD", [days[-1]], minutes=range(0, 200))
    out = tmp_path / "TICK_INTEGRITY.json"
    rc = ti.main(["--root", str(store.root), "--out", str(out)])
    assert rc == 2
    doc = json.loads(out.read_text("utf-8"))
    assert doc["schema"] == ti.SCHEMA and doc["verdict"] == ti.FAIL
    # The thresholds travel with the verdict so a later reader knows which line applied.
    assert doc["thresholds"]["coverage_fail"] == ti.COVERAGE_FAIL


def test_thresholds_are_a_ratchet_and_this_test_is_the_ratchet() -> None:
    """These may be tightened and never loosened. A gate that can be relaxed to go green is not
    a gate, and this desk's laws forbid it explicitly."""
    assert ti.COVERAGE_FAIL >= 0.80
    assert ti.COVERAGE_DEGRADED >= 0.95
    assert ti.UNEXPLAINED_DEGRADED_MIN <= 1, "ANY unexplained minute must be at least DEGRADED"
    assert ti.UNEXPLAINED_FAIL_MIN <= 30
    assert ti.SESSION_QUORUM >= 0.5 and ti.MIN_WEEKDAY_OBS >= 3
