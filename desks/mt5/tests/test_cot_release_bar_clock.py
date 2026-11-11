"""The #238 HOLD repairs (2026-11-11): the COT label lives on the BAR clock, and a cell is charged once.

A. LOOK-AHEAD. `cot_frames._label_for` returned the release in true UTC while the bars a label is
   searched against are broker wall time (New York + 7 h) under a UTC tzinfo, so a delayed report
   was readable 1.5 h (summer) to 2.5 h (winter) before it was public. Every expected instant
   below is written out by hand from the CFTC's 15:30 New York release, never derived from the
   code under test.

B. CHARGE-ONCE. `cot_positioning_flow` charged `len(grid)` on every donating pass. A cell identity
   is charged exactly once; a pass with nothing new charges 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import cot_frames  # noqa: E402

from research import futures_state as fs  # noqa: E402

UTC = "UTC"
NY = "America/New_York"


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=UTC)


def _broker(ny_wall: str) -> pd.Timestamp:
    """A New York wall-clock time as the bar index stamps it (NY + 7 h, UTC-labelled). Written
    independently of `futures_state.to_bar_clock` so the tests do not grade the code with itself."""
    return (pd.Timestamp(ny_wall) + pd.Timedelta(hours=7)).tz_localize(UTC)


# ------------------------------------------------------------------ the one shared helper
def test_shared_helper_is_1530_new_york_in_both_dst_regimes():
    cal = fs.cftc_calendar()
    assert fs.cot_usable_from("2026-10-13", cal) == _ts("2026-10-16 19:30")     # EDT
    assert fs.cot_usable_from("2026-01-13", cal) == _ts("2026-01-16 20:30")     # EST
    # and the bar clock reads the SAME wall time in both: 15:30 + 7 h
    assert fs.to_bar_clock(_ts("2026-10-16 19:30")) == _ts("2026-10-16 22:30")
    assert fs.to_bar_clock(_ts("2026-01-16 20:30")) == _ts("2026-01-16 22:30")


def test_shared_helper_reads_the_registry_calendar_when_given_none():
    assert fs.cot_usable_from("2025-10-07") == fs.cot_usable_from("2025-10-07",
                                                                  fs.cftc_calendar())
    assert fs.cot_usable_from("2025-10-07") == _ts("2025-11-21 20:30")          # catch-up, EST


def test_to_bar_clock_reads_a_naive_instant_as_utc():
    assert fs.to_bar_clock("2026-06-22 19:30") == _ts("2026-06-22 22:30")


# --------------------------------------------- holiday weeks never label before release
#: (as-of day, the release in New York wall time, DST regime). Sources: the CFTC release schedule
#: (holiday weeks release the next business day) and the 2025 lapse catch-up table.
HOLIDAY_WEEKS = [
    ("2024-11-26", "2024-12-02 15:30", "EST"),    # Thanksgiving Thu Nov 28 2024
    ("2023-11-21", "2023-11-27 15:30", "EST"),    # Thanksgiving Thu Nov 23 2023
    ("2024-12-24", "2024-12-30 15:30", "EST"),    # Christmas Wed Dec 25 2024
    ("2023-12-19", "2023-12-26 15:30", "EST"),    # Christmas Mon Dec 25 2023 follows the Friday
    ("2026-06-16", "2026-06-22 15:30", "EDT"),    # Juneteenth Fri Jun 19 2026
    ("2024-06-18", "2024-06-24 15:30", "EDT"),    # Juneteenth Wed Jun 19 2024
    ("2026-06-30", "2026-07-06 15:30", "EDT"),    # Jul 3 2026 (Independence Day observed)
    ("2025-10-07", "2025-11-21 15:30", "EST"),    # 2025 shutdown catch-up
    ("2025-09-30", "2025-11-19 15:30", "EST"),    # 2025 shutdown catch-up, the first
]


def test_the_table_covers_both_dst_regimes():
    for asof, ny_wall, regime in HOLIDAY_WEEKS:
        off = pd.Timestamp(ny_wall).tz_localize(NY).utcoffset()
        assert off == pd.Timedelta(hours=-5 if regime == "EST" else -4), asof
    assert {r for _a, _n, r in HOLIDAY_WEEKS} == {"EST", "EDT"}


@pytest.mark.parametrize("asof,ny_wall,regime", HOLIDAY_WEEKS)
def test_holiday_week_is_never_labelled_before_release_on_the_broker_clock(asof, ny_wall, regime):
    release_bar = _broker(ny_wall)
    lab = cot_frames.release_label(_ts(asof))
    assert lab >= release_bar, (asof, lab, release_bar)
    # THE DEFECT, pinned: the same instant in true UTC is 2 h (EDT) or 3 h (EST) EARLIER than the
    # bar that carries it, and that is what the label used to be compared against.
    true_utc = pd.Timestamp(ny_wall).tz_localize(NY).tz_convert(UTC)
    assert release_bar - true_utc == pd.Timedelta(hours=3 if regime == "EST" else 2)
    assert lab > true_utc.ceil("h")


def test_plain_holiday_weeks_label_the_first_bar_hour_after_release():
    # 15:30 New York = 22:30 on the bar clock, so the first whole bar hour is 23:00 -- in summer
    # and in winter alike. Before the fix these read 20:00 (EDT) and 21:00 (EST).
    assert cot_frames.release_label(_ts("2026-06-16")) == _ts("2026-06-22 23:00")
    assert cot_frames.release_label(_ts("2024-11-26")) == _ts("2024-12-02 23:00")


def test_a_normal_week_keeps_its_monday_label():
    # Friday 15:30 New York is Friday 22:30 on the bar clock: before the nominal Monday 00:00.
    assert cot_frames.release_label(_ts("2026-08-11")) == _ts("2026-08-17")
    assert cot_frames.release_label(_ts("2026-01-13")) == _ts("2026-01-19")


def test_every_tuesday_2018_to_2026_is_labelled_at_or_after_its_release():
    cal = fs.cftc_calendar()
    hol = fs._us_holidays(tuple(str(c) for c in (cal.get("closures") or ())))
    tuesdays = pd.date_range("2018-01-02", "2026-12-29", freq="W-TUE")
    assert len(tuesdays) > 460
    prev = None
    for tue in tuesdays:
        lab = cot_frames.release_label(tue.tz_localize(UTC))
        # the desk's one rule, on the bar clock
        shared = fs.to_bar_clock(fs.cot_usable_from(tue, cal, hol))
        assert lab >= shared, (tue, lab, shared)
        # and, independently of every calendar: never before 15:30 New York on the Friday after
        friday = tue + pd.Timedelta(days=3)
        assert lab >= _broker(f"{friday.date()} 15:30"), (tue, lab)
        assert prev is None or lab > prev, (tue, lab, prev)
        prev = lab


def test_no_schedule_week_is_labelled_before_its_true_release():
    sched = cot_frames.release_schedule()
    early = [str(f.date()) for f, lab in sched.items()
             if lab < fs.to_bar_clock(cot_frames.true_release(f))]
    assert early == []


def test_the_own_tables_are_a_floor_never_a_lead():
    # Dec 23 2025: the registry tables Dec 29, this module's notice-based table Dec 31. The later
    # one stands.
    assert cot_frames.release_label(_ts("2025-12-23")) >= _broker("2025-12-31 15:30")


def test_the_gauntlet_cache_path_and_the_in_git_frame_share_the_corrected_clock():
    from research import orthogonal_sweep as osw
    fridays = pd.DatetimeIndex([_ts("2024-11-29"), _ts("2026-06-19"), _ts("2026-08-14")])
    labels = osw._release_labels(fridays)
    assert labels is not None
    assert list(labels) == [_ts("2024-12-02 23:00"), _ts("2026-06-22 23:00"), _ts("2026-08-17")]
    frame = cot_frames.frame("GBPUSD")
    assert frame is not None
    epoch = pd.Timestamp("1970-01-02", tz=UTC)
    for lab, wk in zip(frame.index, frame[cot_frames.REPORT_WEEK], strict=True):
        friday = epoch + pd.Timedelta(days=7 * int(wk))
        assert lab >= fs.to_bar_clock(cot_frames.true_release(friday)), (lab, friday)


def test_a_missing_shared_helper_fails_closed(monkeypatch):
    from research import orthogonal_sweep as osw

    def boom():
        raise RuntimeError("futures_state unavailable")
    monkeypatch.setattr(cot_frames, "_shared_release", boom)
    cot_frames.release_schedule.cache_clear()
    try:
        assert osw._release_labels(pd.DatetimeIndex([_ts("2026-06-19")])) is None
        assert "release_labels" in osw.COT_LABEL_REFUSALS
    finally:
        cot_frames.release_schedule.cache_clear()
        osw.COT_LABEL_REFUSALS.pop("release_labels", None)


# ------------------------------------------------------------------------- charge-once
class _Door:
    """Stands in for `proposer_common.donate`: records every charge, writes the contract file."""

    def __init__(self, seat: Path):
        self.seat, self.calls = seat, []

    def donate(self, source, rows, tests_run, *_a, **_k):
        self.calls.append({"rows": len(rows), "tests_run": int(tests_run)})
        self.seat.mkdir(parents=True, exist_ok=True)
        path = self.seat / f"discoveries_2026111{len(self.calls)}_0000.json"
        path.write_text(json.dumps({"source": source, "tests_run": tests_run,
                                    "generated_at": f"2026-11-1{len(self.calls)}T00:00:00+00:00",
                                    "discoveries": rows}), "utf-8")
        return path

    def counts(self):
        return {"donated": self.calls[-1]["rows"] if self.calls else 0}


@pytest.fixture
def organ(tmp_path, monkeypatch):
    from research import cot_positioning_flow as cpf
    from research import cross_sectional_breadth as csb
    from research import proposer_common as pc
    door = _Door(tmp_path / "seat")
    world = {"plan": [("XAUUSD", "mm_net", "fade"), ("XAUUSD", "mm_net", "follow"),
                      ("XAGUSD", "swap_net", "fade")],
             "days": {"fade": 100, "follow": 10}}      # follow cells sit under the seed floor

    def grid():
        return [(s, {**cpf.PARAMS, "cot_symbol": s, "series": c, "mode": m})
                for s, c, m in world["plan"]]

    monkeypatch.setattr(cpf, "SEAT", door.seat)
    monkeypatch.setattr(cpf, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(cpf, "grid", grid)
    monkeypatch.setattr(cpf, "_build", lambda sym, params, cache: (
        cache.setdefault(sym, object()), [params["mode"]])[1])
    monkeypatch.setattr(csb, "firing", lambda sigs, _d: {
        "signal_days": world["days"][sigs[0]], "trade_days_lb": world["days"][sigs[0]]})
    monkeypatch.setattr(pc, "donate", door.donate)
    monkeypatch.setattr(pc, "donation_counts", door.counts)
    return cpf, door, world, tmp_path


def _forget_today(tmp: Path) -> None:
    """Age every measurement by a day so the next pass measures again."""
    doc = json.loads((tmp / "state.json").read_text("utf-8"))
    for row in doc["cells"].values():
        if row.get("day"):
            row["day"] = "2000-01-01"
    (tmp / "state.json").write_text(json.dumps(doc), "utf-8")


def test_first_pass_charges_every_cell_it_looked_at_once(organ):
    cpf, door, _world, tmp = organ
    out = cpf.seed()
    # two cells clear the floor and are donated; the held-back one was LOOKED AT, so it is charged
    assert door.calls == [{"rows": 2, "tests_run": 3}]
    assert out["tests_run_this_pass"] == 3 and out["charged_total"] == 3
    assert out["charge_pending"] == 0
    state = json.loads((tmp / "state.json").read_text("utf-8"))
    assert len(state["charged"]) == 3


def test_second_pass_with_nothing_new_charges_zero(organ):
    cpf, door, _world, tmp = organ
    cpf.seed()
    out = cpf.seed()
    assert len(door.calls) == 1                         # no second contract, so no second charge
    assert out["tests_run_this_pass"] == 0 and out["charged_total"] == 3
    _forget_today(tmp)
    out = cpf.seed()                                    # re-measured, still nothing new
    assert len(door.calls) == 1
    assert out["tests_run_this_pass"] == 0 and out["charged_total"] == 3


def test_a_new_identity_is_the_only_thing_a_later_donation_charges(organ):
    cpf, door, world, _tmp = organ
    cpf.seed()
    world["plan"].append(("EURUSD", "lev_net", "fade"))
    out = cpf.seed()
    assert door.calls[-1] == {"rows": 1, "tests_run": 1}   # was len(grid) = 4 before the fix
    assert out["tests_run_this_pass"] == 1 and out["charged_total"] == 4
    assert sum(c["tests_run"] for c in door.calls) == 4    # one charge per identity, in total


def test_a_held_back_cell_that_later_clears_is_donated_on_a_charge_already_paid(organ):
    cpf, door, world, tmp = organ
    cpf.seed()
    world["days"]["follow"] = 100
    _forget_today(tmp)
    out = cpf.seed()
    assert door.calls[-1] == {"rows": 1, "tests_run": 0}
    assert out["donated_total"] == 3 and out["charged_total"] == 3
    assert sum(c["tests_run"] for c in door.calls) == 3


def test_looks_with_no_donation_are_pending_then_charged_once(organ):
    cpf, door, world, tmp = organ
    world["days"]["fade"] = 10                          # nothing clears: no contract to carry it
    out = cpf.seed()
    assert door.calls == [] and out["tests_run_this_pass"] == 0
    assert out["charge_pending"] == 3 and out["charged_total"] == 0
    world["days"]["fade"] = 100
    _forget_today(tmp)
    out = cpf.seed()
    assert door.calls == [{"rows": 2, "tests_run": 3}]
    assert out["charge_pending"] == 0 and out["charged_total"] == 3


def test_a_refused_donation_charges_nothing(organ, monkeypatch):
    cpf, door, _world, _tmp = organ
    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda *_a, **_k: None)
    out = cpf.seed()
    assert out["tests_run_this_pass"] == 0 and out["charged_total"] == 0
    assert out["donation"]["status"] == "REFUSED_AT_DOOR"
    monkeypatch.setattr(pc, "donate", door.donate)
    out = cpf.seed()                                    # the retry carries the charge, once
    assert door.calls == [{"rows": 2, "tests_run": 3}] and out["charged_total"] == 3


def test_a_dry_run_charges_nothing(organ):
    cpf, door, _world, tmp = organ
    out = cpf.seed(dry_run=True)
    assert door.calls == [] and out["tests_run_this_pass"] == 0
    assert not (tmp / "state.json").exists()


def test_the_seat_keeps_donated_cells_charged_when_the_state_file_is_lost(organ):
    cpf, door, _world, tmp = organ
    cpf.seed()
    (tmp / "state.json").unlink()
    state = cpf._load_state()
    assert len(state["charged"]) == 2                   # the two cells the seat file holds
    out = cpf.seed()
    # nothing is donated twice; only the held-back look, whose record went with the state file,
    # is pending again -- and it is not charged until a contract carries it
    assert len(door.calls) == 1 and out["tests_run_this_pass"] == 0
    assert out["donated_this_pass"] == 0
