"""The Asia sensor adapter: stored Asia observations land in the ONE sensor ledger as contract
observations -- PIT-honest, idempotent, licensed -- and a downstream reader of that ledger sees
them."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import pit  # noqa: E402
from libs.research import sensor_contract as sc  # noqa: E402
from research import asia_sensor_adapter as ad  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _desk(tmp: Path) -> Path:
    desk = tmp / "desk"
    # alt_proxies vintage store: a KR export print published on its page, later revised; and a
    # second period whose publication is the release calendar only
    _write(desk / "data" / "alt_proxies" / "obs" / "kr_exports_early.json", {
        "exports|2026-09-10": {
            "series": "exports", "period": "2026-09-10", "value_first": 150.0,
            "value_last": 152.5, "first_seen_at": "2026-09-11T02:00:00+00:00",
            "last_seen_at": "2026-09-20T02:00:00+00:00",
            "published_time": "2026-09-11T00:00:00+00:00", "published_basis": "page",
            "revision_time": "2026-09-20T02:00:00+00:00", "n_revisions": 1},
        "exports|2026-09-20": {
            "series": "exports", "period": "2026-09-20", "value_first": 160.0,
            "value_last": 160.0, "first_seen_at": "2026-09-21T09:00:00+00:00",
            "last_seen_at": "2026-09-21T09:00:00+00:00",
            "published_time": "2026-09-22T00:00:00+00:00", "published_basis": "release_rule",
            "revision_time": None, "n_revisions": 0}})
    # a refused-terms Asian source: its store is never read
    _write(desk / "data" / "alt_proxies" / "obs" / "jp_jnto_arrivals.json", {
        "arrivals|2026-08-31": {"series": "arrivals", "period": "2026-08-31",
                                "value_first": 3.1, "value_last": 3.1,
                                "first_seen_at": "2026-09-18T00:00:00+00:00",
                                "published_time": "2026-09-17T07:00:00+00:00",
                                "published_basis": "page", "n_revisions": 0}})
    # asia_parser: one Asian and one non-Asian registry row, each with a stamped frame
    _write(desk / "data" / "asia_sources.json", {"sources": [
        {"id": "cn_test_stat", "country": "cn", "plane": "cn_hard", "access": "public",
         "cadence": "monthly", "url": "https://example.invalid/cn"},
        {"id": "us_test_stat", "country": "us", "plane": "macro", "access": "public",
         "cadence": "monthly", "url": "https://example.invalid/us"}]})
    series = desk / "data" / "lake" / "series"
    series.mkdir(parents=True, exist_ok=True)
    head = ("region,level,event_time,available_time,ingested_time,published_time,"
            "retrieval_time,revision_time,source_id,vintage_id\n")
    (series / "cn_test_stat.csv").write_text(
        head + "north,10.5,2026-07-31,2026-08-20 00:00:00+00:00,2026-09-01T00:00:00+00:00,"
               "2026-08-20,2026-09-01T00:00:00+00:00,,cn_test_stat,v1\n"
               "south,11.0,2026-08-31,2026-09-20 00:00:00+00:00,2026-09-21T00:00:00+00:00,"
               "2026-09-20,2026-09-21T00:00:00+00:00,,cn_test_stat,v1\n", encoding="utf-8")
    (series / "us_test_stat.csv").write_text(
        head + "x,1.0,2026-07-31,2026-08-20,2026-09-01T00:00:00+00:00,2026-08-20,"
               "2026-09-01T00:00:00+00:00,,us_test_stat,v1\n", encoding="utf-8")
    # free_stack_cnx rows as free_stack_hunter.merge_obs writes them (s2.5 names carried)
    base = {"source_id": "cnx_shfe", "dataset_id": "shfe.warrants", "entity": "SHFE:cu",
            "geography": "CN", "asset_domain": "futures", "metric": "wr", "unit": "t",
            "event_time": "2026-09-30", "publication_time": "2026-09-30T12:00:00+00:00",
            "licence": "free_stack_sources:cnx_shfe", "commercial_rights": "to_confirm",
            "provenance_hash": "abc", "raw_pointer": "raw/cnx_shfe/2026-10-01.jsonl#shfe"}
    rows = [{**base, "key": "cu_wr", "period_end": "2026-09-30", "value": 5000.0,
             "available_time": "2026-09-30T12:00:00+00:00", "vintage": "archive",
             "observation_id": "p1", "knowable_at": "2026-09-30T12:00:00+00:00",
             "received_at": "2026-10-01T01:00:00+00:00"},
            {**base, "key": "cu_wr", "period_end": "2026-09-30", "value": 5100.0,
             "available_time": "2026-10-02T01:00:00+00:00", "vintage": "revision",
             "observation_id": "p2", "revision_of": "p1",
             "knowable_at": "2026-10-02T01:00:00+00:00",
             "received_at": "2026-10-02T01:00:00+00:00"}]
    obs = desk / "data" / "free_stack" / "obs"
    obs.mkdir(parents=True, exist_ok=True)
    (obs / "cnx_shfe.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                        encoding="utf-8")
    # a pre-contract free-stack store (no s2.5 names) is left alone
    (obs / "old_source.jsonl").write_text(json.dumps(
        {"key": "x", "period_end": "2026-09-01", "value": 1.0,
         "available_time": "2026-09-02T00:00:00+00:00"}) + "\n", encoding="utf-8")
    return desk


def _all_rows(root: Path) -> list[dict[str, Any]]:
    led = sc.SensorLedger(root)
    out: list[dict[str, Any]] = []
    for shard in sorted((root / "observations").glob("*.jsonl")):
        out.extend(led.rows(shard.stem))
    return out


def test_alt_proxies_row_keeps_publication_and_receipt_apart() -> None:
    src = {"id": "jp_tokyo_cpi", "region": "JP", "licence": "e-Stat", "terms": "confirmed"}
    row = {"series": "core", "period": "2026-09-30", "value_first": 2.1, "value_last": 2.1,
           "first_seen_at": "2026-10-01T01:00:00+00:00",
           "published_time": "2026-10-02T00:00:00+00:00", "published_basis": "release_rule",
           "n_revisions": 0}
    (obs,) = ad.map_alt_proxies_row(src, row)
    # a release calendar is a schedule, not a printed publication stamp
    assert obs.publication_time == sc.UNMEASURED
    assert obs.scheduled_time == "2026-10-02T00:00:00+00:00"
    # the desk held it before the (late-biased) calendar instant: the world knew it by then
    assert obs.knowable_at == "2026-10-01T01:00:00+00:00"
    assert obs.received_at == "2026-10-01T01:00:00+00:00"
    assert obs.knowable_basis == "bounded_by_receipt" and obs.knowable_at == obs.received_at
    assert "knowable_basis" not in obs.attributes
    assert obs.geography == "JP" and obs.licence == "e-Stat"
    assert obs.commercial_rights.startswith("terms=confirmed")
    assert obs.authority == "NONE" and sc.defects(obs) == []


def test_pass_maps_every_asia_store_and_a_downstream_reader_sees_it(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    doc = ad.run(desk, ledger_root=root, report=rep, now=NOW)
    t = doc["totals"]
    # alt 2 periods + 1 revision; frame 2 rows x 1 numeric col; cnx 1 + 1 revision
    assert t["appended"] == 7, doc["stores"]
    assert t["revisions"] == 2 and t["refused"] == 0
    assert "alt_proxies:jp_jnto_arrivals" not in doc["stores"]     # refused terms: never read
    assert "asia_parser_frames:us_test_stat" not in doc["stores"]  # not an Asian geography
    assert doc["hooks"]["asia_parser_frames"]["status"] == "READING"
    assert doc["hooks"]["cn_exchange"]["status"] == "READING"
    assert doc["stores"]["cn_exchange:old_source"]["mapped"] == 0  # pre-contract store
    assert doc["hooks"]["latent"]["status"].startswith("ABSENT")

    rows = _all_rows(root)
    # THE DOWNSTREAM READER: the contract's own intake meter over the ledger shards
    m = sc.intake_metrics(rows)
    assert m["rows"] == 7
    assert set(m["regions"]) == {"KR", "CN"}
    assert m["sensor_classes"] == {ad.SENSOR_CLASS: 7}
    assert m["pit_completeness"]["knowable_at"] == 1.0
    assert all(r["authority"] == "NONE" and r["licence"] != sc.UNMEASURED for r in rows)

    # a PIT joiner reads the rows through libs.data.pit with no edit
    kr = [r for r in rows if r["source_id"] == "kr_exports_early"
          and r["event_time"].startswith("2026-09-10")]
    first = next(r for r in kr if not r["revision_of"])
    rev = next(r for r in kr if r["revision_of"])
    assert first["knowable_at"] == "2026-09-11T00:00:00+00:00"       # the printed stamp
    assert first["received_at"] == "2026-09-11T02:00:00+00:00"       # first sight, not now
    assert rev["revision_of"] == first["observation_id"] and rev["revision_delta"] == 2.5
    assert pit.usable_at(first, datetime(2026, 9, 10, 23, tzinfo=UTC)) is False
    assert pit.usable_at(first, datetime(2026, 9, 11, 1, tzinfo=UTC)) is True
    assert pit.usable_at(rev, datetime(2026, 9, 19, tzinfo=UTC)) is False
    # the first print is never edited by its revision
    assert first["value"] == 150.0

    cnx = [r for r in rows if r["source_id"] == "cnx_shfe"]
    assert {r["metric"] for r in cnx} == {"wr"} and len(cnx) == 2
    assert all(r["attributes"].get("producer_observation_id") in ("p1", "p2") for r in cnx)
    assert next(r for r in cnx if r["value"] == 5000.0)["knowable_at"] == \
        "2026-09-30T12:00:00+00:00"

    frame = [r for r in rows if r["source_id"] == "cn_test_stat"]
    assert {r["entity"] for r in frame} == {"north", "south"}
    south = next(r for r in frame if r["entity"] == "south")
    # declared lag says the DATE 2026-09-20: knowable at the end of that Shanghai day, whenever
    # the desk read it (2026-09-21 00:00Z here, within 24h, so not backfill)
    assert south["knowable_at"] == "2026-09-20T15:59:59+00:00"
    assert south["knowable_basis"] == "declared_lag"
    assert south["received_at"] == "2026-09-21T00:00:00+00:00"
    assert "pit_quality" not in south["attributes"]


def test_rerun_appends_nothing_even_without_the_cursor(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    ad.run(desk, ledger_root=root, report=rep, now=NOW)
    n = len(_all_rows(root))
    again = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=1))
    assert again["totals"].get("appended", 0) == 0
    rep.unlink()                       # the stores_seen cursor is gone: only the index guards
    third = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=2))
    # the CONTRACT keeps it idempotent: replayed first prints (older than the revisions the
    # ledger holds) are duplicates, never new revisions back to the first print
    assert third["totals"]["appended"] == 0 and third["totals"]["revisions"] == 0
    assert third["totals"]["duplicates"] == third["totals"]["mapped"] == n
    assert not hasattr(ad, "pending") and not hasattr(ad, "_index")
    assert len(_all_rows(root)) == n


def test_alt_proxies_leg_runs_the_adapter(tmp_path: Path) -> None:
    from research import alt_proxies as A
    desk = _desk(tmp_path)
    out = A.sensor_adapter_pass(A.Paths(desk), ledger_root=tmp_path / "sensors")
    assert out["appended"] == 7
    assert (desk / "reports" / ad.REPORT_NAME).exists()


def test_each_knowable_basis_is_set_from_how_knowable_at_was_derived(tmp_path: Path) -> None:
    src = {"id": "kr_exports_early", "region": "KR", "licence": "x", "terms": "confirmed"}
    base = {"series": "exports", "period": "2026-09-10", "value_first": 1.0, "value_last": 1.0,
            "first_seen_at": "2026-09-11T02:00:00+00:00", "n_revisions": 0}
    # printed_stamp: the page's own stamp, earlier than first sight
    (o,) = ad.map_alt_proxies_row(src, {**base, "published_time": "2026-09-11T00:00:00+00:00",
                                        "published_basis": "page"})
    assert (o.knowable_basis, o.knowable_at) == ("printed_stamp", "2026-09-11T00:00:00+00:00")
    # calendar: the release rule's instant, earlier than first sight
    (o,) = ad.map_alt_proxies_row(src, {**base, "published_time": "2026-09-11T01:00:00+00:00",
                                        "published_basis": "release_rule"})
    assert (o.knowable_basis, o.scheduled_time) == ("calendar", "2026-09-11T01:00:00+00:00")
    assert o.knowable_at == "2026-09-11T01:00:00+00:00"
    # bounded_by_receipt: no publication instant at all -> knowable_at IS received_at
    (o,) = ad.map_alt_proxies_row(src, {**base, "published_time": None})
    assert o.knowable_basis == "bounded_by_receipt" and o.knowable_at == o.received_at
    # declared_lag: a registry frame's modelled available_time is a DATE, so knowable_at is the
    # end of that local day (no receipt instant later than it)
    reg = {"id": "cn_test_stat", "country": "cn"}
    rec = {"event_time": "2026-07-31", "available_time": "2026-08-20T00:00:00+00:00",
           "level": 10.5}
    (o,) = ad.map_asia_frame_row(reg, rec, ["level"])
    assert (o.knowable_basis, o.knowable_at) == ("declared_lag", "2026-08-20T15:59:59+00:00")
    # read 11 days after the local day ended: still the end of that day, marked backfill
    (o,) = ad.map_asia_frame_row(reg, {**rec, "ingested_time": "2026-09-01T00:00:00+00:00"},
                                 ["level"])
    assert (o.knowable_basis, o.knowable_at) == ("declared_lag", "2026-08-20T15:59:59+00:00")
    assert o.received_at == "2026-09-01T00:00:00+00:00"
    assert o.attributes["pit_quality"] == "backfill" and sc.defects(o) == []
    # s2.5 producer rows: the contract word is kept, free text is read into the vocabulary
    # (and kept as producer_knowable_basis), and with no word the matching clock decides
    row = {"source_id": "cnx_shfe", "metric": "wr", "value": 1.0, "geography": "CN",
           "event_time": "2026-09-30", "publication_time": "2026-09-30T12:00:00+00:00",
           "knowable_at": "2026-09-30T12:00:00+00:00", "received_at": "2026-10-01T01:00:00+00:00"}
    assert ad.map_cn_exchange_record(row).knowable_basis == "printed_stamp"
    o = ad.map_cn_exchange_record({**row, "knowable_basis": "release calendar hour"})
    assert o.knowable_basis == "calendar"
    assert o.attributes["producer_knowable_basis"] == "release calendar hour"
    assert ad.map_cn_exchange_record({**row, "knowable_basis": "declared_lag"}
                                     ).knowable_basis == "declared_lag"
    lag = {k: v for k, v in row.items() if k not in ("knowable_at", "publication_time")}
    o = ad.map_cn_exchange_record({**lag, "available_time": "2026-09-30T15:00:00+00:00"})
    assert (o.knowable_basis, o.knowable_at) == ("declared_lag", "2026-09-30T15:00:00+00:00")
    assert sc.defects(ad.map_cn_exchange_record(row)) == []

    # every row the pass lands carries a contract basis, as a field and never an attribute
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    doc = ad.run(desk, ledger_root=root, report=tmp_path / "rep.json", now=NOW)
    assert doc["totals"]["refused"] == 0 and doc["contract_gaps"] == []
    rows = _all_rows(root)
    assert {r["knowable_basis"] for r in rows} == {
        "printed_stamp", "declared_lag", "bounded_by_receipt"}
    assert all(r["knowable_basis"] in sc.KNOWABLE_BASES for r in rows)
    assert not any("knowable_basis" in (r["attributes"] or {}) for r in rows)
    assert all(r["knowable_at"] == r["received_at"] for r in rows
               if r["knowable_basis"] == "bounded_by_receipt")


def test_adapter_rows_show_up_in_the_hourly_sensor_ledger_digest(
        tmp_path: Path, monkeypatch: Any) -> None:
    """#208's `sensor_ledger` leg (research/sensor_ledger_digest.py -> reports/SENSOR_LEDGER.json)
    is the ledger's clock and artifact: the adapter's observations are counted there."""
    from research import sensor_ledger_digest as dg
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    ad.run(desk, ledger_root=root, report=tmp_path / "rep.json", now=NOW)
    held = sc.SensorLedger(root).latest_index()
    monkeypatch.setenv("QUANT_SENSOR_LEDGER", str(root))
    out = tmp_path / "SENSOR_LEDGER.json"
    assert dg.main(["--out", str(out), "--days", "400"]) == 0
    digest = json.loads(out.read_text(encoding="utf-8"))
    assert digest["status"] == "MEASURED" and digest["root"] == str(root)
    assert digest["index_keys"] == len(held) and digest["revised_keys"] == 2
    days = [d for d in digest["days"].values() if d.get("rows")]
    assert sum(d["rows"] for d in days) == 7
    classes: dict[str, int] = {}
    for d in days:
        for k, v in d["sensor_classes"].items():
            classes[k] = classes.get(k, 0) + v
    assert classes == {ad.SENSOR_CLASS: 7}
    assert ad.LEDGER_DIGEST == "desks/mt5/reports/SENSOR_LEDGER.json" == \
        str(dg.REPORT.relative_to(ROOT)).replace("\\", "/")


# ============================================================== the date-only look-ahead (#225)
def _close(country: str, received: str | None) -> sc.SensorObservation:
    rec: dict[str, Any] = {"event_time": "2026-09-01",
                           "available_time": "2026-09-01T00:00:00+00:00", "close": 3.5}
    if received:
        rec["ingested_time"] = received
    (o,) = ad.map_asia_frame_row({"id": f"{country}_close", "country": country}, rec, ["close"])
    return o


def test_cn_close_dated_0901_is_not_knowable_before_the_shanghai_day_ends() -> None:
    """A lag-0 CN close dated 09-01 was knowable at 00:00Z and usable at 03:00Z, before the
    15:00 CST (07:00Z) close. Now knowable_at = max(end of the Shanghai day, received_at)."""
    o = _close("cn", "2026-09-01T02:00:00+00:00")          # fetched 10:00 CST, intraday
    k = sc.parse_time(o.knowable_at)
    assert k is not None and k >= datetime(2026, 9, 1, 7, 0, tzinfo=UTC)   # after the close
    assert o.knowable_at == "2026-09-01T15:59:59+00:00"     # 23:59:59 Asia/Shanghai
    assert o.knowable_basis == "declared_lag"
    assert sc.usable_at(o, "2026-09-01T03:00:00Z") is False
    assert sc.usable_at(o, "2026-09-01T03:00:00Z", basis="world") is False
    # an intraday read of a date-stamped close is refused by the contract, not admitted early
    assert any("received_at precedes knowable_at" in d for d in sc.defects(o))
    # read after the day ended: still knowable at the end of the day, received_at as recorded
    late = _close("cn", "2026-09-01T20:00:00+00:00")
    assert (late.knowable_at, late.knowable_basis) == ("2026-09-01T15:59:59+00:00",
                                                      "declared_lag")
    assert late.received_at == "2026-09-01T20:00:00+00:00"
    assert sc.defects(late) == [] and "pit_quality" not in late.attributes
    assert sc.usable_at(late, "2026-09-01T15:59:58Z", basis="world") is False
    assert sc.usable_at(late, "2026-09-01T15:59:59Z", basis="world") is True
    # backfill: read a week later, the release instant is kept and the row is marked
    old = _close("cn", "2026-09-08T00:00:00+00:00")
    assert old.knowable_at == "2026-09-01T15:59:59+00:00"
    assert old.attributes["pit_quality"] == "backfill"


@pytest.mark.parametrize(("country", "eod"), [
    ("jp", "2026-09-01T14:59:59+00:00"),     # Asia/Tokyo, UTC+9
    ("kr", "2026-09-01T14:59:59+00:00"),     # Asia/Seoul, UTC+9
    ("hk", "2026-09-01T15:59:59+00:00"),
    ("in", "2026-09-01T18:29:59+00:00"),     # Asia/Kolkata, UTC+5:30
    ("xx", "2026-09-02T11:59:59+00:00"),     # unknown: UTC-12, the LATEST end of day
])
def test_each_country_ends_its_day_in_its_own_zone(country: str, eod: str) -> None:
    o = _close(country, None)
    assert (o.knowable_at, o.knowable_basis) == (eod, "declared_lag")
    assert sc.usable_at(o, "2026-09-01T03:00:00Z", basis="world") is False
    assert sc.defects(o) == []


def test_alt_proxies_revision_correction_and_rerun_make_no_vintage_conflict(
        tmp_path: Path) -> None:
    """The ledger keys vintages by knowable_at: a value re-sent under a held knowable_at with a
    different value is a refused conflict. A revision, a correction in place and a re-run must
    each produce 0 conflicts."""
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    first = ad.run(desk, ledger_root=root, report=rep, now=NOW)
    assert first["totals"]["conflicts"] == 0 and first["totals"]["revisions"] == 2
    again = ad.run(desk, ledger_root=root, report=tmp_path / "rep2.json", now=NOW)
    assert again["totals"]["conflicts"] == 0 and again["totals"]["appended"] == 0
    # the store corrects the 09-20 print IN PLACE, keeping its first_seen stamp
    path = desk / "data" / "alt_proxies" / "obs" / "kr_exports_early.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    store["exports|2026-09-20"]["value_first"] = 161.0
    store["exports|2026-09-20"]["value_last"] = 161.0
    _write(path, store)
    fix = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=1))
    t = fix["totals"]
    assert t["conflicts"] == 0 and t["corrections_restamped"] == 1 and t["revisions"] == 1
    led = sc.SensorLedger(root)
    held = led.latest("asia.alt_proxies:kr_exports_early", "KR", "exports", "2026-09-20")
    assert held is not None and held["value"] == 161.0
    assert held["knowable_at"] > "2026-09-21T09:00:00+00:00"   # strictly later than corrected
    # the old vintage still answers for the instant before the correction was seen
    before = led.as_of("asia.alt_proxies:kr_exports_early", "KR", "exports", "2026-09-20",
                       "2026-09-22T00:00:00Z", basis="world")
    assert before is not None and before["value"] == 160.0
    rerun = ad.run(desk, ledger_root=root, report=tmp_path / "rep3.json",
                   now=NOW + timedelta(hours=2))
    assert rerun["totals"]["conflicts"] == 0 and rerun["totals"]["appended"] == 0


def test_a_corrupt_index_is_counted_and_never_reset(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    ad.run(desk, ledger_root=root, report=rep, now=NOW)
    shards = {p.name: p.read_bytes() for p in (root / "observations").glob("*.jsonl")}
    index = root / "latest_numeric.json"
    index.write_text("{not json", encoding="utf-8")
    rep.unlink()                                   # force every store to be re-sent
    doc = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=1))
    # the pass COMPLETES and reports it: nothing appended, nothing marked seen
    assert doc["ledger_status"].startswith("INDEX_CORRUPT")
    assert doc["totals"]["index_corrupt"] >= 3 and doc["totals"].get("appended", 0) == 0
    assert all(v["status"] == "INDEX_CORRUPT" for v in doc["stores"].values()
               if v.get("status") not in ("ERROR",))
    assert doc["stores_seen"] == {}                                    # re-sent next pass
    assert rep.exists()
    assert index.read_text(encoding="utf-8") == "{not json"          # never reset
    assert {p.name: p.read_bytes() for p in (root / "observations").glob("*.jsonl")} == shards


def test_a_failed_write_is_counted_and_the_store_is_resent(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"

    def failed(self: Any, observations: Any, now: Any = None) -> dict[str, Any]:
        return {"status": "WRITE_FAILED", "why": "OSError: disk full", "appended": 0,
                "duplicates": 0, "revisions": 0, "conflicts": 0, "refused": 0,
                "refusals": [], "shards": []}
    monkeypatch.setattr(sc.SensorLedger, "append", failed)
    doc = ad.run(desk, ledger_root=root, report=rep, now=NOW)
    carried = [k for k, v in doc["stores"].items() if v.get("mapped")]
    assert doc["totals"]["write_failed"] == len(carried) >= 3
    assert all(doc["stores"][k]["status"] == "WRITE_FAILED" for k in carried)
    assert not any(k in doc["stores_seen"] for k in carried)
    monkeypatch.undo()
    again = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=1))
    assert again["totals"]["appended"] == 7


def test_as_of_on_adapter_rows_answers_nothing_before_knowable_at(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    ad.run(desk, ledger_root=root, report=tmp_path / "rep.json", now=NOW)
    led = sc.SensorLedger(root)
    rows = [r for r in _all_rows(root) if r["source_id"] == "cn_test_stat"]
    assert rows
    for r in rows:
        k = sc.parse_time(r["knowable_at"])
        assert k is not None
        rx = sc.parse_time(r["received_at"])
        assert rx is not None
        args = (r["sensor_id"], r["entity"], r["metric"], r["event_time"])
        # world basis: invisible before knowable_at, visible at it
        assert led.as_of(*args, k - timedelta(seconds=1), basis="world") is None
        got = led.as_of(*args, k, basis="world")
        assert got is not None and got["value"] == r["value"]
        assert got["knowable_at"] == r["knowable_at"]
        # desk basis (the default): invisible until the desk ALSO held it
        held = max(k, rx)
        assert led.as_of(*args, held - timedelta(seconds=1)) is None
        desk_got = led.as_of(*args, held)
        assert desk_got is not None and desk_got["value"] == r["value"]
        assert desk_got["received_at"] == r["received_at"]
        latest = led.latest(*args)
        assert latest is not None and latest["knowable_at"] == r["knowable_at"]
        assert sc.usable_at(r, k - timedelta(seconds=1)) is False


def test_an_intraday_read_is_held_until_a_refetch_after_the_local_close(tmp_path: Path) -> None:
    """A date-only CN close fetched at 02:00Z (10:00 CST) may be provisional: it is held, not
    sent, and the cursor does not advance. A later pass WITHOUT a re-fetch still holds it (the
    run clock never stands in for a fetch). A re-fetch at 19:00Z is admitted with received_at
    19:00Z and knowable_at 15:59:59Z, the 02:00Z read kept as first_read_at."""
    desk = tmp_path / "desk"
    _write(desk / "data" / "asia_sources.json", {"sources": [
        {"id": "cn_close", "country": "cn", "plane": "cn_markets", "access": "public",
         "cadence": "daily"}]})
    frame = desk / "data" / "lake" / "series" / "cn_close.csv"
    frame.parent.mkdir(parents=True, exist_ok=True)
    head = "close,event_time,available_time,ingested_time,source_id,vintage_id\n"
    frame.write_text(head + "3.5,2026-09-01,2026-09-01 00:00:00+00:00,"
                            "2026-09-01T02:00:00+00:00,cn_close,v1\n", encoding="utf-8")
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    name = "asia_parser_frames:cn_close"
    early = ad.run(desk, ledger_root=root, report=rep,
                   now=datetime(2026, 9, 1, 2, 30, tzinfo=UTC))
    st = early["stores"][name]
    assert st["intraday_held_until_local_close"] == 1 and st["appended"] == 0
    assert name not in early["stores_seen"] and len(early["intraday_held"]) == 1
    assert _all_rows(root) == []
    # 20:00Z, the store NOT re-fetched: the 02:00Z value is not the close, so still held
    stale = ad.run(desk, ledger_root=root, report=rep,
                   now=datetime(2026, 9, 1, 20, 0, tzinfo=UTC))
    st = stale["stores"][name]
    assert st["intraday_held_until_local_close"] == 1 and st["appended"] == 0
    assert name not in stale["stores_seen"] and _all_rows(root) == []
    # the store re-fetches at 19:00Z (after the 15:59:59Z Shanghai end of day)
    frame.write_text(head + "3.6,2026-09-01,2026-09-01 00:00:00+00:00,"
                            "2026-09-01T19:00:00+00:00,cn_close,v2\n", encoding="utf-8")
    late = ad.run(desk, ledger_root=root, report=rep,
                  now=datetime(2026, 9, 1, 20, 30, tzinfo=UTC))
    st = late["stores"][name]
    assert st["appended"] == 1 and st["intraday_settled"] == 1
    assert st["intraday_held_until_local_close"] == 0
    assert name in late["stores_seen"] and late["intraday_held"] == {}
    (row,) = _all_rows(root)
    assert row["value"] == 3.6
    assert row["knowable_at"] == "2026-09-01T15:59:59+00:00"
    assert row["knowable_basis"] == "declared_lag"
    assert row["received_at"] == "2026-09-01T19:00:00+00:00"          # the re-fetch, not now
    assert row["attributes"]["first_read_at"] == "2026-09-01T02:00:00+00:00"
    led = sc.SensorLedger(root)
    args = (row["sensor_id"], row["entity"], row["metric"], row["event_time"])
    # world basis: the CN close is invisible before the Shanghai day ends
    assert led.as_of(*args, "2026-09-01T03:00:00Z", basis="world") is None
    assert led.as_of(*args, "2026-09-01T15:59:58Z", basis="world") is None
    got = led.as_of(*args, "2026-09-01T15:59:59Z", basis="world")
    assert got is not None and got["value"] == 3.6
    # desk basis: invisible until its received_at (the 19:00Z re-fetch)
    assert led.as_of(*args, "2026-09-01T15:59:59Z") is None
    assert led.as_of(*args, "2026-09-01T18:59:59Z") is None
    got = led.as_of(*args, "2026-09-01T19:00:00Z")
    assert got is not None and got["value"] == 3.6
    again = ad.run(desk, ledger_root=root, report=tmp_path / "rep2.json",
                   now=datetime(2026, 9, 2, 1, 0, tzinfo=UTC))
    assert again["totals"].get("appended", 0) == 0 and again["totals"]["conflicts"] == 0


def test_a_missing_index_keeps_the_cursor_and_refeeds_nothing(tmp_path: Path) -> None:
    desk = _desk(tmp_path)
    root = tmp_path / "sensors"
    rep = tmp_path / "rep.json"
    first = ad.run(desk, ledger_root=root, report=rep, now=NOW)
    assert first["ledger_status"] == "EMPTY" and first["totals"]["appended"] == 7
    n = len(_all_rows(root))
    (root / "latest_numeric.json").unlink()
    doc = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=1))
    assert doc["ledger_status"].startswith("INDEX_MISSING")
    # the cursor is kept: no store is re-fed because the index went missing
    assert all(v["status"] == "UNCHANGED" for k, v in doc["stores"].items()
               if k in first["stores_seen"])
    assert doc["totals"].get("appended", 0) == 0
    rep.unlink()           # and with no cursor either, the append dedupes every re-sent row
    bare = ad.run(desk, ledger_root=root, report=rep, now=NOW + timedelta(hours=2))
    # the contract rebuilt the index on the previous pass, so it is present again
    assert bare["ledger_status"] == "OK"
    assert bare["totals"]["appended"] == 0 and bare["totals"]["conflicts"] == 0
    assert len(_all_rows(root)) == n
