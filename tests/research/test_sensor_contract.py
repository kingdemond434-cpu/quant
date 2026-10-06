"""The universal sensor contract: one shape for text and non-text, PIT clocks kept apart,
revisions appended, no authority, and throughput measured rather than assumed."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    revised = _payrolls(95.0, received=T0 + timedelta(days=30))
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
    led.append([_payrolls(95.0, received=T0 + timedelta(days=30))])
    again = led.append([first])
    assert again == {**again, "appended": 0, "duplicates": 1, "revisions": 0}
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
    led.append([_payrolls(95.0, received=T0 + timedelta(seconds=90))])
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
