"""The Asia sensor adapter: stored Asia observations land in the ONE sensor ledger as contract
observations -- PIT-honest, idempotent, licensed -- and a downstream reader of that ledger sees
them."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
               "south,11.0,2026-08-31,2026-09-20 00:00:00+00:00,2026-09-01T00:00:00+00:00,"
               "2026-09-20,2026-09-01T00:00:00+00:00,,cn_test_stat,v1\n", encoding="utf-8")
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
    # declared lag says 2026-09-20 but the desk held it on 2026-09-01: knowable is bounded
    assert south["knowable_at"] == "2026-09-01T00:00:00+00:00"


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
    # declared_lag: a registry frame's modelled available_time, earlier than the fetch
    reg = {"id": "cn_test_stat", "country": "cn"}
    rec = {"event_time": "2026-07-31", "available_time": "2026-08-20T00:00:00+00:00",
           "ingested_time": "2026-09-01T00:00:00+00:00", "level": 10.5}
    (o,) = ad.map_asia_frame_row(reg, rec, ["level"])
    assert (o.knowable_basis, o.knowable_at) == ("declared_lag", "2026-08-20T00:00:00+00:00")
    (o,) = ad.map_asia_frame_row(reg, {**rec, "available_time": "2026-09-20T00:00:00+00:00"},
                                 ["level"])
    assert o.knowable_basis == "bounded_by_receipt" and o.knowable_at == o.received_at
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
