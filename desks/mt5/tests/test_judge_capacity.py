"""The judge-capacity report (ideas 630/632): the 7-day trend and the five-stage queue model."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from research import judge_capacity as jc

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
DAY = 86400


def _index(rows, *, updated=NOW, kept_days=8):
    return {"recent": [list(r) for r in rows], "updated_at": updated.isoformat(),
            "kept_since": int((NOW - timedelta(days=kept_days)).timestamp())}


def _ts(t: datetime) -> int:
    return int(t.timestamp())


def test_days_bucket_by_utc_day_and_count_first_terminal_separately():
    yday = NOW.replace(hour=0) - timedelta(days=1)
    rows = [(_ts(yday) + 10, 1), (_ts(yday) + 20, 0), (_ts(yday) + DAY - 1, 1),
            (_ts(NOW) - 60, 1)]
    doc = jc.build_trend(NOW, index=_index(rows))
    days = {d["day"]: d for d in doc["days"]}
    y = days[yday.date().isoformat()]
    assert (y["state"], y["verdict_events"], y["first_terminal"]) == ("COMPLETE", 3, 2)
    assert days[NOW.date().isoformat()]["state"] == "PARTIAL"
    assert len(doc["days"]) == jc.TREND_DAYS
    assert doc["status"] == "BELOW_FLOOR"
    assert doc["last_complete_day"] == yday.date().isoformat()
    assert doc["shortfall_per_day"] == jc.FLOOR_PER_DAY - 2


def test_a_day_at_the_floor_reads_at_floor():
    yday = _ts(NOW.replace(hour=0) - timedelta(days=1))
    rows = [(yday + (i % DAY), 1) for i in range(jc.FLOOR_PER_DAY)]
    assert jc.build_trend(NOW, index=_index(rows))["status"] == "AT_FLOOR"


def test_no_index_is_unmeasured_never_zero():
    doc = jc.build_trend(NOW, index=None)
    assert doc["status"] == jc.UNMEASURED
    assert doc["days"] == []


def test_a_stale_index_cannot_speak_for_days_after_it():
    doc = jc.build_trend(NOW, index=_index([], updated=NOW - timedelta(days=3)))
    states = [d["state"] for d in doc["days"]]
    assert states[-1] == "PARTIAL"
    assert states[-3:-1] == [jc.UNMEASURED, jc.UNMEASURED]
    assert doc.get("index_stale") is True


def test_a_day_the_index_dropped_is_unmeasured():
    doc = jc.build_trend(NOW, index=_index([], kept_days=3))
    assert doc["days"][0]["state"] == jc.UNMEASURED


def test_each_sweep_is_recorded_once_with_its_own_verdicts():
    end = NOW - timedelta(hours=1)
    resident = {"last_sweep_ended_utc": end.isoformat(), "last_sweep_s": 7200.0,
                "sweeps": 9, "last_rc": 0}
    rows = [(_ts(end) - 100, 1), (_ts(end) - 200, 0), (_ts(end) - 8000, 1)]
    doc = jc.build_trend(NOW, index=_index(rows), resident=resident)
    assert len(doc["sweeps"]) == 1
    s = doc["sweeps"][0]
    assert (s["verdict_events"], s["first_terminal"]) == (2, 1)
    assert s["first_terminal_per_sweep_hour"] == 0.5
    again = jc.build_trend(NOW, index=_index(rows), resident=resident, previous=doc)
    assert len(again["sweeps"]) == 1
    assert again["per_sweep"]["first_terminal_per_sweep"] == 1.0


def _sources(now, *, born=1000.0, first=300.0, depth=1_500_000):
    at = now.isoformat()
    return {"rate": {"at": at, "created": {"per_hour": {"24h": 700.0}},
                     "verdicts": {"first_terminal_per_hour": {"24h": first}}},
            "throughput": {"at": at, "queue": {"depth": depth}},
            "backpressure": {"at": at, "windows": {"24h": {"intake": {"per_hour": born}}},
                             "core": {"testing_24h": {"passed": 240}}},
            "cert": {"at": at, "counts": {"NO_CLOCK": 50},
                     "certificates": [{"certified_at": (now - timedelta(hours=2)).isoformat()}]},
            "clocks": {"at": at, "n_clocks": 100}}


def test_the_judge_stage_carries_rates_depth_and_wait():
    cap = jc.build_capacity(NOW, **_sources(NOW))
    j = cap["stages"]["judge"]
    assert (j["arrival_per_h"], j["service_per_h"], j["queue_depth"]) == (1000.0, 300.0, 1_500_000)
    assert j["implied_wait_h"] == 5000.0
    assert cap["binding_stage"] == "cert"     # 1 cert / 24h is the slowest measured service
    assert cap["order"] == list(jc.STAGES)


def test_alarm_needs_six_hours_of_arrival_over_service():
    prev = None
    for h in range(8, -1, -1):
        t = NOW - timedelta(hours=h)
        prev = jc.build_capacity(t, **_sources(t), previous=prev)
    assert prev is not None
    assert prev["stages"]["judge"]["alarm"]["status"] == "ALARM"
    assert "judge" in prev["alarms"]
    assert prev["stages"]["intake"]["alarm"]["status"] == "OK"


def test_one_sample_never_reads_a_clean_ok():
    cap = jc.build_capacity(NOW, **_sources(NOW))
    assert cap["stages"]["judge"]["alarm"]["status"] == jc.UNMEASURED
    assert cap["status"] == jc.UNMEASURED


def test_a_stale_source_is_unmeasured_not_zero():
    src = _sources(NOW)
    src["cert"]["at"] = (NOW - timedelta(days=4)).isoformat()
    cap = jc.build_capacity(NOW, **src)
    assert cap["stages"]["cert"]["service_per_h"] == jc.UNMEASURED
    assert cap["source_ages"]["CERTIFICATE_CLOCK_LAW.json"]["status"] == "STALE"


def test_clock_service_is_the_change_in_clocks_against_an_older_sample():
    t0 = NOW - timedelta(hours=4)
    prev = jc.build_capacity(t0, **_sources(t0))
    src = _sources(NOW)
    src["clocks"]["n_clocks"] = 108
    cap = jc.build_capacity(NOW, **src, previous=prev)
    assert cap["stages"]["clock"]["service_per_h"] == 2.0
    assert cap["stages"]["clock"]["implied_wait_h"] == 25.0


def test_run_writes_both_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(jc, "OUT", tmp_path / "JUDGING_RATE_TREND.json")
    monkeypatch.setattr(jc, "CAPACITY_OUT", tmp_path / "CAPACITY_MODEL.json")
    for name in ("LEDGER_INDEX", "RESIDENT", "RATE", "THROUGHPUT", "BACKPRESSURE",
                 "CERT_CLOCK", "CLOCK_LEDGER"):
        monkeypatch.setattr(jc, name, tmp_path / f"{name}.json")
    out = jc.run(NOW)
    assert (tmp_path / "JUDGING_RATE_TREND.json").exists()
    assert (tmp_path / "CAPACITY_MODEL.json").exists()
    assert out["trend"]["status"] == jc.UNMEASURED
