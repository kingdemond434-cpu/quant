"""The bar clock, measured from broker server time against UTC (`research/bar_clock_probe.py`).

The producer reads what the terminal says (newest tick's time_msc and the current H1 bar's open)
against the box's UTC clock at capture, publishes dated spans, and writes UNMEASURED -- never a
guess -- when it has no fresh evidence. These tests pin that, the DST handling (the EU and US
autumn rules disagree on 2026-10-26..10-30, and only a reading settles which one the broker
follows), the second opinions' power to refuse a span, and that `family_event_reaction` fires
again from the measured clock: 12, 9 and 11 fire days on XAUUSD, EURUSD and USDJPY.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bar_clock as bc  # noqa: E402
from research import bar_clock_probe as bp  # noqa: E402

H = 3_600_000
_SYMS = ("EURUSD", "USDJPY", "XAUUSD")


def _ms(when: datetime) -> int:
    return int(when.timestamp() * 1000)


def _row(when: datetime, offset_h: int, sym: str = "EURUSD", *, age_s: float = 2.0,
         bar: bool = True) -> dict:
    local = _ms(when)
    server = local + offset_h * H - int(age_s * 1000)
    srv_hour = (local + offset_h * H) // H * H
    return {"source": "terminal", "symbol": sym, "local_ms": local, "server_ms": server,
            "bar_open_ms": srv_hour if bar else None}


def _ledger(root: Path, rows: list[dict]) -> None:
    assert bp.append_ledger(root, rows) is None


def _hourly(start: datetime, end: datetime, offset_of) -> list[dict]:
    """Hourly captures on three symbols; weekend ticks are stale, as a closed market's are."""
    rows, t = [], start
    while t < end:
        closed = t.weekday() == 5 or (t.weekday() == 4 and t.hour >= 21) \
            or (t.weekday() == 6 and t.hour < 21)
        for s in _SYMS:
            rows.append(_row(t, offset_of(t), s, age_s=(36 * 3600 if closed else 2.0)))
        t += timedelta(hours=1)
    return rows


def _build(root: Path, monkeypatch, *, release=None, now=None) -> dict:
    monkeypatch.setattr(bp, "release_opinion", lambda _r: release or {"per_season": {}})
    doc = bp.build(root, tape_clock=root / "no_tape", now=now)
    bp.write(root, doc)
    return doc


# ------------------------------------------------------------------------- one reading --
def test_a_fresh_tick_and_its_bar_read_the_offset():
    t = datetime(2026, 7, 1, 12, 20, tzinfo=UTC)
    assert bp.read_probe(_row(t, 3)) == (3, "FRESH_TICK_AND_BAR")
    assert bp.read_probe(_row(t, 2, bar=False)) == (2, "FRESH_TICK")


def test_a_stale_tick_is_rejected_never_rounded():
    """A weekend tick 36h old lands between hours; rounding it would invent an offset."""
    t = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    assert bp.read_probe(_row(t, 3, age_s=36 * 3600 + 1800)) == (None, "STALE")
    assert bp.read_probe(_row(t, 3, age_s=600)) == (None, "STALE")


def test_a_bar_on_another_clock_refuses_the_reading():
    t = datetime(2026, 7, 1, 12, 20, tzinfo=UTC)
    row = _row(t, 3)
    row["bar_open_ms"] -= 2 * H
    assert bp.read_probe(row) == (None, "BAR_DISAGREES")
    row = _row(t, 3)
    row["server_ms"] = row["local_ms"] + 20 * H
    assert bp.read_probe(row)[1] == "IMPLAUSIBLE"


def test_symbols_that_disagree_at_one_instant_measure_nothing(tmp_path):
    t = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    points, verdicts = bp.instants([_row(t, 3, "EURUSD"), _row(t, 2, "USDJPY")])
    assert points == [] and verdicts["SYMBOLS_DISAGREE"] == 1


# ------------------------------------------------------------------------- no evidence --
def test_no_evidence_publishes_unmeasured_with_its_stamp_and_n(tmp_path, monkeypatch):
    doc = _build(tmp_path, monkeypatch)
    assert doc["status"] == bp.UNMEASURED
    assert doc["measured_at"] and doc["evidence"]["n_probe_rows"] == 0
    assert doc["spans"] == [] and all(v["offset_h"] is None for v in doc["per_season"].values())
    got, status, _ = bc.to_bar_time(datetime(2026, 7, 1, 12, 0, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED


def test_stale_rows_alone_stay_unmeasured(tmp_path, monkeypatch):
    t = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    _ledger(tmp_path, [_row(t + timedelta(hours=i), 3, age_s=40_000) for i in range(10)])
    doc = _build(tmp_path, monkeypatch)
    assert doc["status"] == bp.UNMEASURED and doc["evidence"]["verdicts"]["STALE"] == 10


def test_main_on_a_host_without_a_terminal_writes_unmeasured(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)    # import fails, as off the box
    monkeypatch.setattr(bp, "tape_clock_dir", lambda: tmp_path / "no_tape")
    monkeypatch.setattr(bp, "release_opinion", lambda _r: {"per_season": {}})
    assert bp.main(["--root", str(tmp_path)]) == 0
    doc = json.loads((tmp_path / Path(*bp.CLOCK_REL.split("/"))).read_text("utf-8"))
    assert doc["status"] == bp.UNMEASURED
    assert doc["evidence"]["capture"].startswith("NO_TERMINAL")


def test_too_few_captures_make_no_span(tmp_path, monkeypatch):
    t = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    _ledger(tmp_path, [_row(t + timedelta(hours=i), 3) for i in range(bp.MIN_SPAN_PROBES - 1)])
    doc = _build(tmp_path, monkeypatch)
    assert doc["status"] == bp.UNMEASURED and len(doc["short_runs"]) == 1


# ---------------------------------------------------------------------------------- DST --
def _us_rule(t: datetime) -> int:
    return 3 if t < datetime(2026, 11, 1, 6, 0, tzinfo=UTC) else 2


def _eu_rule(t: datetime) -> int:
    return 3 if t < datetime(2026, 10, 25, 1, 0, tzinfo=UTC) else 2


def test_the_autumn_changeover_is_read_and_the_rule_named(tmp_path, monkeypatch):
    """Broker on the New York rule: still +3 on 10-26..10-30, +2 from 11-01."""
    _ledger(tmp_path, _hourly(datetime(2026, 10, 19, tzinfo=UTC),
                              datetime(2026, 11, 7, tzinfo=UTC), _us_rule))
    doc = _build(tmp_path, monkeypatch, now=datetime(2026, 11, 7, tzinfo=UTC))
    assert [s["offset_h"] for s in doc["spans"]] == [3, 2]
    tr = [t for t in doc["transitions"] if t["from_h"] == 3 and t["to_h"] == 2]
    assert len(tr) == 1 and "us_autumn" in tr[0]["rule_match"]
    assert "eu_autumn" not in tr[0]["rule_match"]
    assert doc["dst_watch"]["broker_follows"] == "us"
    assert doc["varies_with_dst"] is True
    # A shoulder-month instant converts, because there the offset was read, not inferred.
    got, status, why = bc.to_bar_time(datetime(2026, 10, 28, 14, 30, tzinfo=UTC), tmp_path)
    assert status == bc.OK and got.hour == 17 and "span" in why
    got, status, _ = bc.to_bar_time(datetime(2026, 11, 3, 14, 30, tzinfo=UTC), tmp_path)
    assert status == bc.OK and got.hour == 16
    # Inside the measured changeover (the weekend it fell in) nothing is knowable.
    got, status, why = bc.to_bar_time(datetime(2026, 11, 1, 12, 0, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED and "changeover" in why
    # And beyond the evidence nothing converts.
    got, status, why = bc.to_bar_time(datetime(2026, 11, 20, 12, 0, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED and "covers this instant" in why


def test_a_broker_on_the_eu_rule_reads_plus_two_in_the_gap_week(tmp_path, monkeypatch):
    _ledger(tmp_path, _hourly(datetime(2026, 10, 19, tzinfo=UTC),
                              datetime(2026, 11, 7, tzinfo=UTC), _eu_rule))
    doc = _build(tmp_path, monkeypatch, now=datetime(2026, 11, 7, tzinfo=UTC))
    assert doc["dst_watch"]["broker_follows"] == "eu"
    got, status, _ = bc.to_bar_time(datetime(2026, 10, 28, 14, 30, tzinfo=UTC), tmp_path)
    assert status == bc.OK and got.hour == 16


def test_before_the_gap_week_is_read_the_rule_is_unmeasured(tmp_path, monkeypatch):
    _ledger(tmp_path, _hourly(datetime(2026, 10, 12, tzinfo=UTC),
                              datetime(2026, 10, 21, tzinfo=UTC), _us_rule))
    doc = _build(tmp_path, monkeypatch, now=datetime(2026, 10, 21, tzinfo=UTC))
    assert doc["status"] == bp.MEASURED
    assert doc["dst_watch"]["broker_follows"] == bp.UNMEASURED


# ---------------------------------------------------------------------- second opinions --
def _summer_ledger(root: Path) -> None:
    _ledger(root, _hourly(datetime(2026, 8, 20, tzinfo=UTC),
                          datetime(2026, 9, 16, tzinfo=UTC), lambda _t: 3))


def test_a_resolved_release_reading_that_disagrees_refuses_the_span(tmp_path, monkeypatch):
    _summer_ledger(tmp_path)
    release = {"per_season": {"summer": {"offset_h": 2, "window": {
        "first": "2026-08-26T12:30:00+00:00", "last": "2026-09-11T12:30:00+00:00"},
        "readings": {}}}}
    doc = _build(tmp_path, monkeypatch, release=release)
    assert {s["status"] for s in doc["spans"]} == {bp.CONFLICT}
    assert doc["status"] == bp.UNMEASURED
    got, status, _ = bc.to_bar_time(datetime(2026, 9, 2, 12, 30, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED


def test_instrument_votes_that_all_disagree_refuse_the_span(tmp_path, monkeypatch):
    _summer_ledger(tmp_path)
    votes = {s: {"offset_h": 1, "releases": ["2026-09-04T12:30:00+00:00"]}
             for s in ("EURUSD", "GBPUSD", "USDJPY")}
    doc = _build(tmp_path, monkeypatch,
                 release={"per_season": {"summer": {"offset_h": None, "readings": votes}}})
    assert {s["status"] for s in doc["spans"]} == {bp.CONFLICT}


def test_agreeing_votes_corroborate_the_span(tmp_path, monkeypatch):
    _summer_ledger(tmp_path)
    votes = {"XAUUSD": {"offset_h": 3, "releases": ["2026-09-04T12:30:00+00:00"]}}
    doc = _build(tmp_path, monkeypatch,
                 release={"per_season": {"summer": {"offset_h": None, "readings": votes}}})
    assert {s["second_opinion"]["verdict"] for s in doc["spans"]} == {"AGREES"}
    assert doc["status"] == bp.MEASURED


def _futures(root: Path, summer: int, winter: int) -> None:
    p = root / Path(*bp.FUTURES_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": "2026-10-21T00:00:00+00:00", "clock": {"per_season": {
        "summer": {"offset_h": summer, "agrees_across_pairs": True},
        "winter": {"offset_h": winter, "agrees_across_pairs": True}}}}), encoding="utf-8")


def test_only_the_cross_venue_reading_publishes_a_season_wide_offset(tmp_path, monkeypatch):
    _summer_ledger(tmp_path)
    doc = _build(tmp_path, monkeypatch)
    assert doc["per_season"]["summer"]["offset_h"] is None      # spans alone: dated only
    got, status, _ = bc.to_bar_time(datetime(2025, 7, 1, 12, 0, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED              # 2026 says nothing about 2025
    _futures(tmp_path, 3, 2)
    doc = _build(tmp_path, monkeypatch)
    assert doc["per_season"]["summer"]["offset_h"] == 3
    assert doc["per_season"]["winter"]["offset_h"] == 2
    got, status, _ = bc.to_bar_time(datetime(2025, 7, 1, 12, 0, tzinfo=UTC), tmp_path)
    assert status == bc.OK and got.hour == 15


def test_a_span_that_contradicts_the_cross_venue_season_withholds_it(tmp_path, monkeypatch):
    _summer_ledger(tmp_path)
    _futures(tmp_path, 2, 2)
    doc = _build(tmp_path, monkeypatch)
    assert doc["per_season"]["summer"]["offset_h"] is None
    assert bp.CONFLICT in doc["per_season"]["summer"]["why"]


def test_the_tick_recorders_clock_rows_are_read_too(tmp_path, monkeypatch):
    clock = tmp_path / "tape" / "clock"
    clock.mkdir(parents=True)
    t0 = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    lines = []
    for i in range(5):
        r = _row(t0 + timedelta(hours=i), 3, bar=False)
        lines.append(json.dumps({"at": "x", "symbol": r["symbol"], "local_ms": r["local_ms"],
                                 "server_ms": r["server_ms"],
                                 "skew_ms": r["server_ms"] - r["local_ms"]}))
    (clock / "2026-07-01.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(bp, "release_opinion", lambda _r: {"per_season": {}})
    doc = bp.build(tmp_path, tape_clock=clock)
    assert doc["evidence"]["tape_rows"] == 5
    assert doc["spans"][0]["sources"] == ["tape_clock_probe"]


# ------------------------------------------------------------------------------ wiring --
def test_it_is_an_hourly_leg_after_futures_lead_lag_and_the_one_writer():
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert src.index('_costed("futures_lead_lag"') < src.index('_costed("bar_clock_probe"')
    assert '_producer("bar_clock_probe", "research/bar_clock_probe.py")' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["bar_clock_probe"] == "information"
    fll = (_DESK / "research" / "futures_lead_lag.py").read_text(encoding="utf-8")
    assert "(CLOCK_REL, {" not in fll


def test_zero_authority():
    src = (_DESK / "research" / "bar_clock_probe.py").read_text(encoding="utf-8")
    for forbidden in ("order_send", "sleeves.json", "universe.json", "def promote",
                      "subprocess", "positions_get"):
        assert forbidden not in src, forbidden


# -------------------------------------------------------- event_reaction fires again --
_CAL = _DESK / "data" / "intelligence" / "ff_calendar_vintage"
_UNI = _DESK / "data" / "universe"


@pytest.mark.skipif(not (_CAL.is_dir() and (_UNI / "XAUUSD_H1.parquet").exists()),
                    reason="needs the desk's calendar vintages and H1 bars")
def test_event_reaction_fires_again_from_the_measured_clock(tmp_path, monkeypatch):
    """FIXTURE: terminal captures at +3 across 2026-08-20..09-16 (the summer the calendar's
    high-impact history covers), run through the producer, read by the family. With no
    BAR_CLOCK.json the same cells place nothing (NEEDS_DATA(bar_clock), 0 fire days)."""
    import external_gauntlet as G

    from libs.research import bar_clock_release

    _summer_ledger(tmp_path)
    monkeypatch.setattr(bp, "release_opinion", lambda _r: bar_clock_release.reading(_ROOT))
    doc = bp.build(tmp_path, tape_clock=tmp_path / "no_tape")
    bp.write(tmp_path, doc)
    assert doc["status"] == bp.MEASURED
    assert {s["second_opinion"]["verdict"] for s in doc["spans"]} <= {"AGREES",
                                                                      "UNCORROBORATED"}
    monkeypatch.setattr(bc, "_ROOT", tmp_path)

    meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    days = {}
    for sym in ("XAUUSD", "EURUSD", "USDJPY"):
        obj = G.build_cell(sym, "event_reaction", {"input_source": "ff_calendar_vintage"}, meta)
        assert obj, G.LAST_BUILD_FAILURE
        sigs = obj["sigs"] or []
        days[sym] = len(G.daily_series(obj["df"], sigs, obj["costs"])) if sigs else 0
    assert days == {"XAUUSD": 12, "EURUSD": 9, "USDJPY": 11}
