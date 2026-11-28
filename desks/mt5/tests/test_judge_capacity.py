"""The judge-capacity report (ideas 630/632): the 7-day trend and the five-stage queue model."""
from __future__ import annotations

import json
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
    for name in ("VERDICT_CKPT", "GATE_LEDGER", "RESIDENT", "RATE", "THROUGHPUT",
                 "BACKPRESSURE", "CERT_CLOCK", "CLOCK_LEDGER"):
        monkeypatch.setattr(jc, name, tmp_path / f"{name}.json")
    out = jc.run(NOW)
    assert (tmp_path / "JUDGING_RATE_TREND.json").exists()
    assert (tmp_path / "CAPACITY_MODEL.json").exists()
    assert out["trend"]["status"] == jc.UNMEASURED


# THE TREND READS A FILE THAT IS ACTUALLY WRITTEN (Auditor HOLD on #1037, 2026-11-18). The first
# version read data/judging_rate_ledger_index.json, which nothing wrote, so idea 630 read
# UNMEASURED every hour. The source is now judging_throughput's own resume checkpoint; these
# tests drive the real writer and read its output, so a writer that stops writing fails here.

def _writer_rows(now: datetime) -> tuple[list[str], dict[str, tuple[int, int]]]:
    """Ledger lines in the gauntlet's own layout, and the expected (events, first) per day."""
    lines, want = [], {}
    for k, (n_new, n_again) in enumerate(((3, 1), (5, 0), (2, 4))):
        day = (now - timedelta(days=k + 1)).replace(hour=6, minute=0, second=0, microsecond=0)
        at = day.isoformat(timespec="seconds")
        for i in range(n_new):
            lines.append(json.dumps({"at": at, "cell": f"d{k}|c{i}", "graph_id": "",
                                     "sym": "EURUSD", "family": "carry", "passed": False,
                                     "terminal_gate": "dsr", "downstream_status": None}))
        later = (day + timedelta(hours=1)).isoformat(timespec="seconds")
        for i in range(n_again):
            lines.append(json.dumps({"at": later, "cell": f"d{k}|c{i}", "graph_id": "",
                                     "sym": "EURUSD", "family": "carry", "passed": False,
                                     "terminal_gate": "oos", "downstream_status": None}))
        # A repeat beyond the day's new cells names a cell never ruled before: its first ruling.
        want[day.date().isoformat()] = (n_new + n_again, n_new + max(0, n_again - n_new))
    return lines, want


def test_the_trend_reads_the_checkpoint_the_verdict_stream_writes(tmp_path):
    import json as _json

    from research import judging_throughput as jt
    now = datetime.now(UTC).replace(microsecond=0)
    lines, want = _writer_rows(now)
    lines.sort(key=lambda s: _json.loads(s)["at"])
    led = tmp_path / "gate_verdict_ledger.jsonl"
    led.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ck = tmp_path / jt.VERDICT_CKPT_NAME
    jt._verdict_counts(now, led, checkpoint=ck)
    assert ck.exists(), "the verdict stream wrote no checkpoint: the trend has no source"
    idx = jc.index_from_checkpoint(_json.loads(ck.read_text("utf-8")), now=now,
                                   ckpt_mtime=now, ledger_size=led.stat().st_size)
    assert idx is not None and idx["caught_up"] is True
    doc = jc.build_trend(now, index=idx)
    got = {d["day"]: (d["verdict_events"], d["first_terminal"]) for d in doc["days"]
           if d["day"] in want}
    assert got == want
    assert doc["status"] in ("BELOW_FLOOR", "AT_FLOOR")


def test_a_checkpoint_short_of_the_ledger_speaks_only_to_its_newest_stamp():
    last = NOW - timedelta(days=2, hours=3)
    ck = {"raw": {last.isoformat(timespec="seconds"): 4},
          "first": {last.isoformat(timespec="seconds"): 1},
          "offset": 10, "last": last.isoformat(timespec="seconds")}
    idx = jc.index_from_checkpoint(ck, now=NOW, ckpt_mtime=NOW, ledger_size=99)
    assert idx["caught_up"] is False
    doc = jc.build_trend(NOW, index=idx)
    states = {d["day"]: d["state"] for d in doc["days"]}
    assert states[(NOW - timedelta(days=3)).date().isoformat()] == "COMPLETE"
    assert states[(NOW - timedelta(days=1)).date().isoformat()] == jc.UNMEASURED


def test_no_checkpoint_is_unmeasured():
    assert jc.index_from_checkpoint(None, now=NOW, ckpt_mtime=None, ledger_size=None) is None
    assert jc.build_trend(NOW, index=None)["status"] == jc.UNMEASURED


def test_no_parseable_certificate_stamp_is_unmeasured_not_zero():
    assert jc._certs_last_24h({"certificates": [{"certified_at": "?"}]}, NOW) is None
    assert jc._certs_last_24h({"certificates": []}, NOW) is None
