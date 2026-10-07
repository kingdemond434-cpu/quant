"""The universal sensor contract: one shape for text and non-text, PIT clocks kept apart,
revisions appended, no authority, and throughput measured rather than assumed."""
from __future__ import annotations

import json
import multiprocessing
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.data import pit
from libs.research import sensor_contract as sc

T0 = datetime(2026, 10, 2, 12, 30, tzinfo=UTC)


def _payrolls(value: float, *, received: datetime, consensus: float = 50.0,
              knowable: datetime | None = None) -> sc.SensorObservation:
    return sc.make(sensor_id="macro:alfred", source_id="alfred", metric="PAYEMS_change",
                   entity="US", kind="state", value=value, unit="k", consensus=consensus,
                   event_time="2026-09-30", scheduled_time=T0, publication_time=T0,
                   knowable_at=knowable or T0, knowable_basis="calendar", received_at=received,
                   parse_complete_at=received + timedelta(seconds=2), licence="public domain")


def test_every_field_the_header_names_is_on_the_contract() -> None:
    names = set(sc.SensorObservation.__dataclass_fields__)
    header = {"sensor_id", "source_id", "dataset_id", "observation_id", "entity", "geography",
              "asset_domain", "metric", "value", "unit", "event_time", "scheduled_time",
              "publication_time", "knowable_at", "received_at", "parse_complete_at",
              "expected_value", "consensus", "seasonal_expected", "raw_surprise", "surprise_z",
              "percentile", "delta", "acceleration", "revision_of", "revision_delta",
              "source_confidence", "measurement_uncertainty", "commercial_rights", "licence",
              "provenance_hash", "raw_pointer"}
    assert header <= names


def test_clocks_stay_apart_and_absence_is_unmeasured() -> None:
    obs = sc.make(sensor_id="weather:noaa", metric="hdd_anomaly", value=3.0,
                  event_time="2026-10-01T00:00:00Z", received_at=T0)
    assert obs.event_time == "2026-10-01T00:00:00+00:00"
    assert obs.knowable_at == sc.UNMEASURED      # never copied from a neighbouring clock
    assert obs.publication_time == sc.UNMEASURED
    # an unmeasured world clock is never permission, whatever the desk clock says
    assert not sc.usable_at(obs, T0 + timedelta(days=1))
    assert sc.defects(obs) == []


def test_raw_surprise_is_actual_minus_consensus_and_no_authority_exists() -> None:
    obs = _payrolls(120.0, received=T0 + timedelta(seconds=40))
    assert obs.raw_surprise == pytest.approx(70.0)
    assert obs.authority == sc.AUTHORITY == "NONE"
    assert sc.make(authority="FULL", sensor_id="x", metric="m", value=1.0).authority == "NONE"
    assert sc.route(obs)["route"] == "state"
    shock = sc.make(**{**obs.__dict__, "surprise_z": 3.1, "observation_id": ""})
    assert sc.route(shock)["route"] == "event"
    assert sc.route(shock)["authority"] == "NONE"


def test_usable_at_world_versus_desk_basis() -> None:
    obs = _payrolls(120.0, received=T0 + timedelta(minutes=5))
    assert sc.usable_at(obs, T0 + timedelta(minutes=1), basis="world")
    assert not sc.usable_at(obs, T0 + timedelta(minutes=1))          # the desk had not got it
    assert sc.usable_at(obs, T0 + timedelta(minutes=6))
    # and a pit.py joiner reads the row through its own stamp names
    row = obs.to_row()
    assert pit.usable_at(row, T0 + timedelta(minutes=1)) is True
    assert pit.usable_at(row, T0 - timedelta(minutes=1)) is False


def test_receipt_before_knowable_is_a_lookahead_defect() -> None:
    bad = _payrolls(120.0, received=T0 - timedelta(hours=1))
    assert any("look-ahead" in d for d in sc.defects(bad))
    with pytest.raises(ValueError):
        sc.SensorLedger().stamp_downstream(["x"], "not_a_clock", T0, "test")


def test_revisions_append_and_never_overwrite(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    first = _payrolls(120.0, received=T0 + timedelta(seconds=30))
    out1 = led.append([first])
    assert out1["appended"] == 1
    assert led.append([first])["duplicates"] == 1                  # same print twice: one row
    revised = _payrolls(95.0, received=T0 + timedelta(days=30),
                        knowable=T0 + timedelta(days=30))
    out2 = led.append([revised])
    assert out2["revisions"] == 1
    rows = led.rows(first.received_at[:10]) + led.rows(revised.received_at[:10])
    assert [r["value"] for r in rows] == [120.0, 95.0]             # the first print survives
    rev = rows[1]
    assert rev["revision_of"] == first.observation_id
    assert rev["revision_delta"] == pytest.approx(-25.0)
    assert rev["revision_n"] == 1


def test_defective_rows_are_refused_not_repaired(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    out = led.append([sc.make(sensor_id="", metric="m", value=1.0, received_at=T0),
                      sc.make(sensor_id="s", metric="m", kind="state", received_at=T0)])
    assert out["appended"] == 0 and out["refused"] == 2


def test_intake_metrics_measure_compression_coverage_and_latency(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    docs = []
    for i, (src, lang) in enumerate((("reuters", "en"), ("xinhua", "zh"), ("tass", "ru"))):
        docs.append(sc.make(sensor_id="news:x", source_id=src, metric="document",
                            kind="document", text="Iran strikes tanker", language=lang,
                            geography="IR", knowable_at=T0,
                            knowable_basis="printed_stamp", received_at=T0 + timedelta(
                                seconds=10 * (i + 1)),
                            parse_complete_at=T0 + timedelta(seconds=10 * (i + 1) + 1),
                            provenance_hash="same-headline",
                            attributes={"story_id": "ev_1",
                                        "event_id": "ev_1:a" if i == 0 else None,
                                        "novelty": 1.0, "event_kind": "war_escalation"}))
    led.append(docs)
    m = sc.intake_metrics(led.rows(T0.date().isoformat()))
    assert m["raw_observations"] == 3
    assert m["unique_documents"] == 1
    assert m["duplicate_compression_ratio"] == 3.0
    assert m["unique_stories"] == 1 and m["novel_events"] == 1
    assert m["economically_relevant_events"] == 1
    assert set(m["languages"]) == {"en", "zh", "ru"}
    lat = m["latency_s"]["publication_to_receipt"]
    assert lat["n"] == 3 and lat["p50"] == 20.0
    assert m["latency_s"]["receipt_to_classification"]["p99"] == pytest.approx(1.0)
    empty = sc.intake_metrics([])
    assert empty["unique_documents"] == sc.UNMEASURED                # never a clean zero
    assert empty["latency_s"]["publication_to_receipt"]["p50"] == sc.UNMEASURED


def test_downstream_clocks_join_on_observation_id(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    obs = _payrolls(120.0, received=T0 + timedelta(seconds=30))
    led.append([obs])
    led.stamp_downstream([obs.observation_id], "allocator_at", T0 + timedelta(seconds=75),
                         "pf_allocator")
    day = T0.date().isoformat()
    m = sc.intake_metrics(led.rows(day), led.clock_rows(day))
    assert m["latency_s"]["receipt_to_allocator_at"]["p50"] == 45.0


def test_bitemporal_handoff_keeps_valid_and_knowledge_time_apart() -> None:
    d = _payrolls(120.0, received=T0 + timedelta(seconds=30)).to_datum()
    assert d.valid_time == "2026-09-30T00:00:00+00:00"
    assert d.knowledge_time == T0.isoformat(timespec="seconds")
    assert d.latency_s == 30.0


def test_a_resent_first_print_after_its_revision_is_a_duplicate(tmp_path) -> None:
    """Asia's adapter replays its cache: the first print arrives AGAIN after the revision. It
    must not become a third row 'revising' 95 back to 120."""
    led = sc.SensorLedger(tmp_path)
    first = _payrolls(120.0, received=T0 + timedelta(seconds=30))
    led.append([first])
    led.append([_payrolls(95.0, received=T0 + timedelta(days=30),
                          knowable=T0 + timedelta(days=30))])
    again = led.append([first])
    assert again["appended"] == 0 and again["duplicates"] == 1 and again["revisions"] == 0
    # a fresh ledger object (the index re-read from disk) agrees
    again2 = sc.SensorLedger(tmp_path).append([first])
    assert again2["duplicates"] == 1 and again2["revisions"] == 0
    latest = sc.SensorLedger(tmp_path).latest("macro:alfred", "US", "PAYEMS_change",
                                              "2026-09-30")
    assert latest is not None and latest["value"] == 95.0 and latest["revision_n"] == 1
    assert first.observation_id in latest["known_ids"]
    assert sc.SensorLedger(tmp_path).latest("macro:alfred", "US", "nope", "2026-09-30") is None
    idx = led.latest_index()
    assert list(idx.values()) == [{"observation_id": latest["observation_id"], "value": 95.0,
                                   "revision_n": 1}]


def test_knowable_basis_is_first_class_and_required_with_a_world_clock() -> None:
    assert "knowable_basis" in sc.SensorObservation.__dataclass_fields__
    base = {"sensor_id": "s", "metric": "m", "value": 1.0, "knowable_at": T0,
            "received_at": T0 + timedelta(seconds=5)}
    assert any("knowable_basis" in d for d in sc.defects(sc.make(**base)))
    assert any("not one of" in d for d in sc.defects(sc.make(**base, knowable_basis="guess")))
    assert sc.defects(sc.make(**base, knowable_basis="declared_lag")) == []
    bounded = sc.make(**base, knowable_basis="bounded_by_receipt")
    assert any("bounded_by_receipt" in d for d in sc.defects(bounded))
    ok = sc.make(sensor_id="s", metric="m", value=1.0, knowable_at=T0, received_at=T0,
                 knowable_basis="bounded_by_receipt")
    assert sc.defects(ok) == []
    # no world clock at all needs no basis (it is UNMEASURED, and usable_at refuses it anyway)
    assert sc.defects(sc.make(sensor_id="s", metric="m", value=1.0)) == []
    assert sc.make(**base, knowable_basis="calendar").to_row()["knowable_basis"] == "calendar"


def test_the_digest_is_unmeasured_on_an_empty_ledger_and_measures_a_full_one(tmp_path) -> None:
    empty = sc.digest(sc.SensorLedger(tmp_path / "none"), now=T0)
    assert empty["status"] == sc.UNMEASURED and empty["shards"] == 0
    assert all(d["status"] == sc.UNMEASURED for d in empty["days"].values())
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    led.append([_payrolls(95.0, received=T0 + timedelta(seconds=90),
                          knowable=T0 + timedelta(seconds=60))])
    got = sc.digest(led, now=T0 + timedelta(hours=1))
    assert got["status"] == "MEASURED" and got["shards"] == 1
    assert got["index_keys"] == 1 and got["revised_keys"] == 1
    assert got["days"][T0.date().isoformat()]["rows"] == 2


def test_the_ledger_has_a_clock_an_artifact_and_stays_out_of_git() -> None:
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    cycle = (root / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    assert '_producer("sensor_ledger", "research/sensor_ledger_digest.py")' in cycle
    assert '_costed("sensor_ledger", sensor_ledger)' in cycle
    digest = (root / "desks/mt5/research/sensor_ledger_digest.py").read_text("utf-8")
    assert 'REPORT = DESK / "reports" / "SENSOR_LEDGER.json"' in digest
    assert "desks/mt5/data/sensors/" in (root / ".gitignore").read_text("utf-8")


def _vintages(day: int) -> list[sc.SensorObservation]:
    """What release_vintages sends EVERY pass: the first print and every revision so far."""
    rx = T0 + timedelta(days=day, hours=1)
    rows = [_payrolls(120.0, received=rx)]
    if day >= 30:
        rows.append(_payrolls(95.0, received=rx, knowable=T0 + timedelta(days=30)))
    if day >= 60:
        rows.append(_payrolls(101.0, received=rx, knowable=T0 + timedelta(days=60)))
    return rows


def test_daily_resends_of_every_vintage_append_nothing_new(tmp_path) -> None:
    """Audit HOLD #204/#208 item 1: each new day re-appended the first print as revision 6, 9."""
    led = sc.SensorLedger(tmp_path)
    totals = []
    for day in (0, 1, 2, 30, 31, 60, 61, 62):
        out = sc.SensorLedger(tmp_path).append(_vintages(day))
        totals.append((day, out["appended"], out["revisions"]))
    assert totals == [(0, 1, 0), (1, 0, 0), (2, 0, 0), (30, 1, 1), (31, 0, 0), (60, 1, 1),
                      (61, 0, 0), (62, 0, 0)]
    latest = led.latest("macro:alfred", "US", "PAYEMS_change", "2026-09-30")
    assert latest is not None and latest["value"] == 101.0 and latest["revision_n"] == 2
    # same-day rerun: nothing appended AND no revisions reported
    again = sc.SensorLedger(tmp_path).append(_vintages(62))
    assert (again["appended"], again["revisions"], again["duplicates"]) == (0, 0, 3)


def test_as_of_reads_what_the_ledger_held_at_an_instant(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append(_vintages(60))
    key = ("macro:alfred", "US", "PAYEMS_change", "2026-09-30")
    w = {"basis": "world"}
    assert led.as_of(*key, T0 - timedelta(seconds=1), **w) is None
    assert led.as_of(*key, T0 + timedelta(days=10), **w)["value"] == 120.0
    assert led.as_of(*key, T0 + timedelta(days=45), **w)["value"] == 95.0
    assert led.as_of(*key, T0 + timedelta(days=90), **w)["value"] == 101.0
    # audit #208 (2): all three were BACKFILLED on day 60 -- the desk held none of them on day
    # 10, so the default (desk) basis returns nothing until the receipt, then the newest
    assert led.as_of(*key, T0 + timedelta(days=10)) is None
    assert led.as_of(*key, T0 + timedelta(days=60, hours=1))["value"] == 101.0


def test_a_deleted_index_is_rebuilt_from_the_shards_not_read_as_empty(tmp_path) -> None:
    """Audit #208 must-fix 1: a deleted index re-appended the history (4 rows, not 2)."""
    sc.SensorLedger(tmp_path).append(_vintages(30))
    led = sc.SensorLedger(tmp_path)
    led.index_path.unlink()
    out = sc.SensorLedger(tmp_path).append(_vintages(31))
    assert out["appended"] == 0 and out["duplicates"] == 2
    n = sum(len(led.rows(p.stem)) for p in led.obs_dir.glob("*.jsonl"))
    assert n == 2
    latest = sc.SensorLedger(tmp_path).latest("macro:alfred", "US", "PAYEMS_change",
                                              "2026-09-30")
    assert latest is not None and latest["value"] == 95.0


def test_a_crash_between_shard_and_index_is_reconciled_on_load(tmp_path) -> None:
    """Audit #208 must-fix 2: rows on disk that the index never recorded duplicated when the
    producer re-sent them on a later receipt day."""
    led = sc.SensorLedger(tmp_path)
    led.append(_vintages(0))
    stale = led.index_path.read_text(encoding="utf-8")
    sc.SensorLedger(tmp_path).append(_vintages(30))           # writes the day-30 vintage
    led.index_path.write_text(stale, encoding="utf-8")         # ...but the index write was lost
    out = sc.SensorLedger(tmp_path).append(_vintages(45))      # resent on a later receipt day
    assert out["appended"] == 0 and out["duplicates"] == 2
    assert sum(len(led.rows(p.stem)) for p in led.obs_dir.glob("*.jsonl")) == 2


def test_a_torn_last_line_is_quarantined_and_its_observation_admitted(tmp_path) -> None:
    """Audit #208 should-fix: the fragment's id was taken as held, losing the observation."""
    led = sc.SensorLedger(tmp_path)
    obs = _payrolls(120.0, received=T0 + timedelta(seconds=30))
    shard = led.obs_dir / f"{T0.date().isoformat()}.jsonl"
    shard.parent.mkdir(parents=True)
    whole = json.dumps(obs.to_row(), default=str)
    shard.write_text(whole[: len(whole) // 2], encoding="utf-8")   # a crash mid-write
    out = sc.SensorLedger(tmp_path).append([obs])
    assert out["appended"] == 1
    rows = led.rows(T0.date().isoformat())
    assert [r["observation_id"] for r in rows] == [obs.observation_id]
    assert (led.torn_dir / shard.name).read_text(encoding="utf-8").startswith(whole[:20])


def test_the_digest_status_reads_index_corrupt(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    led.index_path.write_text("{not json", encoding="utf-8")
    assert sc.digest(sc.SensorLedger(tmp_path), now=T0)["status"] == "INDEX_CORRUPT"


def _series(entity: str, value: float, rx: datetime) -> sc.SensorObservation:
    return sc.make(sensor_id="macro:alfred", source_id="alfred", metric="PAYEMS_change",
                   entity=entity, kind="state", value=value, unit="k", event_time="2026-09-30",
                   scheduled_time=T0, publication_time=T0, knowable_at=T0,
                   knowable_basis="calendar", received_at=rx,
                   parse_complete_at=rx + timedelta(seconds=2), licence="public domain")


def _writer(root: str, prefix: str, n: int) -> None:
    led = sc.SensorLedger(Path(root))             # one long-lived instance, as a producer holds
    for i in range(n):
        out = led.append([_series(f"{prefix}{i}", float(i), T0 + timedelta(seconds=30))])
        assert out["status"] == "OK", out


def test_a_stale_writer_never_drops_another_writers_rows(tmp_path) -> None:
    """Audit #208 round 2 must-fix: A loaded, B appended, A appended -- A's index lacked B's row
    while its watermark covered B's bytes, so B's row was never replayed and a resend landed."""
    a, b = sc.SensorLedger(tmp_path), sc.SensorLedger(tmp_path)
    a.latest_index()                                          # A has its index in memory
    b.append([_series("B", 1.0, T0 + timedelta(seconds=30))])
    a.append([_series("A", 2.0, T0 + timedelta(seconds=30))])
    raw = json.loads(a.index_path.read_text(encoding="utf-8"))
    assert {k.split("|")[1] for k in raw if k != sc.META} == {"A", "B"}
    out = sc.SensorLedger(tmp_path).append([_series("B", 1.0, T0 + timedelta(days=1))])
    assert out["appended"] == 0 and out["duplicates"] == 1


def test_two_processes_appending_at_once_lose_nothing(tmp_path) -> None:
    ctx = multiprocessing.get_context("fork" if sys.platform != "win32" else "spawn")
    procs = [ctx.Process(target=_writer, args=(str(tmp_path), p, 25)) for p in ("P", "Q")]
    for pr in procs:
        pr.start()
    for pr in procs:
        pr.join(120)
        assert pr.exitcode == 0
    raw = json.loads((tmp_path / "latest_numeric.json").read_text(encoding="utf-8"))
    assert len([k for k in raw if k != sc.META]) == 50
    led = sc.SensorLedger(tmp_path)
    assert sum(len(led.rows(p.stem)) for p in led.obs_dir.glob("*.jsonl")) == 50
    resend = [_series(f"{p}{i}", float(i), T0 + timedelta(days=1)) for p in "PQ"
              for i in range(25)]
    assert sc.SensorLedger(tmp_path).append(resend)["appended"] == 0
    assert not list(tmp_path.glob("*.tmp"))


def test_a_shard_cut_below_its_watermark_prunes_the_cut_rows_from_the_index(tmp_path) -> None:
    """Audit #208 round 2 should-fix: the cut row's index entry survived, so its resend was
    refused as a duplicate of a row that no longer exists."""
    led = sc.SensorLedger(tmp_path)
    led.append([_series("A", 1.0, T0 + timedelta(seconds=30))])
    led.append([_series("B", 2.0, T0 + timedelta(seconds=40))])
    shard = led.obs_dir / f"{T0.date().isoformat()}.jsonl"
    first = shard.read_text(encoding="utf-8").splitlines(keepends=True)[0]
    shard.write_text(first, encoding="utf-8")                 # B's row is gone from the truth
    out = sc.SensorLedger(tmp_path).append([_series("B", 2.0, T0 + timedelta(days=1))])
    assert out["appended"] == 1
    again = sc.SensorLedger(tmp_path).append([_series("A", 1.0, T0 + timedelta(days=1))])
    assert again["appended"] == 0


@pytest.mark.parametrize("meta", ["abc", {"shards": {"2026-10-02": "abc"}}, {"shards": []}])
def test_a_malformed_watermark_is_index_corrupt_not_a_crash(tmp_path, meta) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_series("A", 1.0, T0 + timedelta(seconds=30))])
    doc = json.loads(led.index_path.read_text(encoding="utf-8"))
    doc[sc.META] = meta
    led.index_path.write_text(json.dumps(doc), encoding="utf-8")
    out = sc.SensorLedger(tmp_path).append([_series("B", 2.0, T0 + timedelta(seconds=40))])
    assert out["status"] == "INDEX_CORRUPT" and out["appended"] == 0
    assert sc.digest(sc.SensorLedger(tmp_path), now=T0)["status"] == "INDEX_CORRUPT"


def test_a_same_vintage_with_a_different_value_is_a_refused_conflict(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    out = led.append([_payrolls(121.0, received=T0 + timedelta(seconds=40))])
    assert out["conflicts"] == 1 and out["appended"] == 0
    assert "vintage conflict" in out["refusals"][0]["defects"][0]


def test_a_late_older_vintage_is_history_not_a_revision_of_the_newer(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(95.0, received=T0 + timedelta(days=31),
                          knowable=T0 + timedelta(days=30))])
    out = led.append([_payrolls(120.0, received=T0 + timedelta(days=32))])
    assert out["appended"] == 1 and out["revisions"] == 0
    rows = led.rows((T0 + timedelta(days=32)).date().isoformat())
    assert rows[-1]["attributes"]["late_vintage"] is True and not rows[-1]["revision_of"]
    assert led.latest("macro:alfred", "US", "PAYEMS_change", "2026-09-30")["value"] == 95.0


def test_a_corrupt_index_fails_closed_and_is_never_reset(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    led.index_path.write_text("{not json", encoding="utf-8")
    fresh = sc.SensorLedger(tmp_path)
    out = fresh.append([_payrolls(95.0, received=T0 + timedelta(days=30),
                                  knowable=T0 + timedelta(days=30))])
    assert out["status"] == "INDEX_CORRUPT" and out["appended"] == 0
    assert led.index_path.read_text(encoding="utf-8") == "{not json"
    with pytest.raises(sc.LedgerIndexCorrupt):
        fresh.latest("macro:alfred", "US", "PAYEMS_change", "2026-09-30")
    assert sc.digest(sc.SensorLedger(tmp_path))["index_status"].startswith("INDEX_CORRUPT")


def test_the_index_moves_only_after_the_rows_are_written(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    before = led.index_path.read_text(encoding="utf-8")
    day = (T0 + timedelta(days=30)).date().isoformat()
    (led.obs_dir / f"{day}.jsonl").mkdir(parents=True)       # the shard cannot be opened
    out = sc.SensorLedger(tmp_path).append([_payrolls(95.0, received=T0 + timedelta(days=30),
                                                      knowable=T0 + timedelta(days=30))])
    assert out["status"] == "WRITE_FAILED" and out["appended"] == 0
    assert led.index_path.read_text(encoding="utf-8") == before


def test_the_pre_vintage_index_form_is_still_read(tmp_path) -> None:
    import json
    led = sc.SensorLedger(tmp_path)
    led.index_path.parent.mkdir(parents=True, exist_ok=True)
    first = _payrolls(120.0, received=T0 + timedelta(seconds=30))
    key = sc.SensorLedger.revision_key(first)
    led.index_path.write_text(json.dumps({key: [first.observation_id, 120.0, 0,
                                                [first.observation_id]]}), encoding="utf-8")
    assert sc.SensorLedger(tmp_path).append([first])["duplicates"] == 1


def test_rows_since_streams_only_new_whole_lines(tmp_path) -> None:
    led = sc.SensorLedger(tmp_path)
    led.append([_payrolls(120.0, received=T0 + timedelta(seconds=30))])
    day = T0.date().isoformat()
    rows, off = led.rows_since(day)
    assert len(rows) == 1 and off > 0
    assert led.rows_since(day, off) == ([], off)
    led.append([_payrolls(95.0, received=T0 + timedelta(seconds=90),
                          knowable=T0 + timedelta(seconds=60))])
    with led._shard(day).open("a", encoding="utf-8") as fh:
        fh.write('{"partial": ')                          # a row still being written
    more, off2 = led.rows_since(day, off)
    assert [r["value"] for r in more] == [95.0] and off2 > off
    assert led.rows_since(day, 10 ** 9)[0][0]["value"] == 120.0   # rotated: restart


@pytest.mark.skipif(sys.platform == "win32", reason="holds the lock with flock")
def test_a_hung_lock_holder_times_out_and_appends_nothing(tmp_path, monkeypatch) -> None:
    import fcntl
    monkeypatch.setattr(sc, "LOCK_DEADLINE_S", 0.3)
    led = sc.SensorLedger(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    with led.lock_path.open("a+b") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)          # a hung writer
        out = led.append([_series("A", 1.0, T0 + timedelta(seconds=30))])
        assert out["status"] == "LOCK_TIMEOUT" and out["appended"] == 0
        assert not led.obs_dir.exists()
        assert sc.digest(sc.SensorLedger(tmp_path), now=T0)["status"] == "LOCK_TIMEOUT"
    assert sc.SensorLedger(tmp_path).append(
        [_series("A", 1.0, T0 + timedelta(seconds=30))])["appended"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="patches flock")
def test_a_permanent_lock_error_is_raised_not_retried_forever(tmp_path, monkeypatch) -> None:
    import errno
    import fcntl
    calls = []

    def bad(fd: int, op: int) -> None:
        calls.append(op)
        raise OSError(errno.EBADF, "bad file descriptor")

    monkeypatch.setattr(fcntl, "flock", bad)
    with pytest.raises(OSError):
        sc.SensorLedger(tmp_path).append([_series("A", 1.0, T0 + timedelta(seconds=30))])
    assert len(calls) == 1
