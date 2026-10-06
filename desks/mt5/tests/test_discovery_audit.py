"""Discovery audit: contamination is caught, recall is computed honestly, the rotation is weekly.

The audit is driven from its inputs (`audit(...)` takes the benchmark, discovery rows, registry
and seed texts), so nothing here touches the network or the desk's own artifacts -- except the
one test that pins the REAL benchmark as uncontaminated by the REAL seeds.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import discovery_audit as da  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _item(i: str, url: str, did: str, typ: str, region: str, **kw: Any) -> dict[str, Any]:
    return {"id": i, "url": url, "dataset_id": did, "type": typ, "region": region,
            "language": "en", "benchmark_since": "2026-10-01", **kw}


BENCH: dict[str, Any] = {"weekly_share": 1.0, "items": [
    _item("eu_ports", "https://ec.example.eu/sdmx/data/MAR_GO_QM?format=SDMX-CSV", "MAR_GO_QM",
          "shipping_ports", "Europe", columns=1),
    _item("rba_cards", "https://www.rba.example.au/tables/csv/c1-data.csv", "c1-data",
          "payments_retail", "Asia-Pacific", columns=4),
    _item("dol_claims", "https://oui.example.gov/csv/ar539.csv", "ar539", "labour", "Americas"),
]}


def _rows(tmp: Path) -> list[dict[str, Any]]:
    world = tmp / "world"
    world.mkdir()
    (world / "discoveries_catalog_20261003.json").write_text(json.dumps([
        {"route": "sdmx", "dataset_id": "MAR_GO_QM", "host": "ec.example.eu",
         "first_discovered_at": "2026-10-03T00:00:00+00:00",
         "endpoints": ["https://ec.example.eu/sdmx/data/MAR_GO_QM?format=SDMX-CSV&x=1"]}]))
    (world / "discoveries_20260901_1200.json").write_text(json.dumps([
        {"source": "world_crawler", "url": "https://www.rba.example.au/tables/",
         "endpoints": ["https://www.rba.example.au/tables/csv/c1-data.csv"]},
        {"source": "world_crawler", "url": "https://oui.example.gov/csv/ar5390.html",
         "endpoints": []}]))
    return da.load_discoveries(world)


REGISTRY = {"by_url": {"https://www.rba.example.au/tables/csv/c1-data.csv": {
    "series": ["rba_c1_a", "rba_c1_b"], "status": "SUCCESS"}}, "series": {}}


def test_contamination_by_url_or_exact_dataset_id() -> None:
    clean = {"roster": "https://ec.example.eu/sdmx/dataflow/all\nar5390 is another id"}
    assert da.contamination(BENCH["items"], clean) == []
    by_url = {"roster": "seed: HTTPS://WWW.RBA.EXAMPLE.AU/tables/csv/c1-data.csv/"}
    assert [(h["id"], h["by"]) for h in da.contamination(BENCH["items"], by_url)] == [
        ("rba_cards", "url")]
    by_id = {"pack": "https://other.example/x?flow=mar_go_qm"}
    assert [(h["id"], h["by"]) for h in da.contamination(BENCH["items"], by_id)] == [
        ("eu_ports", "dataset_id")]


def test_a_contaminated_benchmark_publishes_no_recall(tmp_path: Path) -> None:
    rep = da.audit(BENCH, now=NOW, rows=_rows(tmp_path), registry=REGISTRY,
                   sources={"data/catalog_routes/roster.json": "MAR_GO_QM"},
                   missing_sources=[], use_dir=tmp_path / "none")
    assert rep["verdict"] == "CONTAMINATED" and rep["recall"] is None
    assert rep["label"] == "benchmark coverage, not world coverage"


def test_recall_by_route_region_type_and_the_missed_list(tmp_path: Path) -> None:
    rep = da.audit(BENCH, now=NOW, rows=_rows(tmp_path), registry=REGISTRY,
                   sources={"roster": ""}, missing_sources=[], use_dir=tmp_path / "none")
    assert rep["verdict"] == "OK" and rep["label"] == da.LABEL
    assert rep["measured"] == 3 and rep["discovered"] == 2 and rep["recall"] == pytest.approx(
        0.667, abs=1e-3)
    assert rep["missed"] == [{"id": "dol_claims", "type": "labour", "region": "Americas"}]
    by = {m["id"]: m for m in rep["items"]}
    ports, cards = by["eu_ports"], by["rba_cards"]
    assert ports["first_route"] == "sdmx" and ports["matched_by"] == ["dataset_id"]
    assert ports["endpoint_resolved"] is True and ports["ingested"] is False
    assert ports["field_coverage"] == 0.0
    assert ports["first_discovery_delay_h"] == 48.0
    assert ports["discovered_before_benchmark_entry"] is False
    assert cards["first_route"] == "world_crawler" and cards["matched_by"] == ["url"]
    assert cards["ingested"] is True and cards["series"] == ["rba_c1_a", "rba_c1_b"]
    assert cards["field_coverage"] == 0.5
    assert cards["first_discovery_delay_h"] == 0.0               # found before it was listed
    assert cards["discovered_before_benchmark_entry"] is True
    assert cards["downstream_use"] == da.UNMEASURED            # no ledger is not a zero
    assert by["dol_claims"]["field_coverage"] == da.UNMEASURED  # no declared columns
    assert rep["recall_by_route"]["sdmx"]["discovered"] == 1
    assert rep["recall_by_route"]["MISSED"]["items"] == 1
    assert rep["recall_by_type"]["labour"]["recall"] == 0.0
    assert rep["recall_by_region"]["Europe"]["recall"] == 1.0


def test_downstream_use_is_read_when_a_ledger_exists(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta

    from libs.data import dataset_use as U
    use = tmp_path / "dataset_use"
    U.record_reads("world_model", {"acquired:rba_c1_b": "v1"}, use="regime_state", root=use,
                   now=datetime.now(UTC) - timedelta(days=9))
    rows = _rows(tmp_path)
    m = da.measure_item(BENCH["items"][1], rows, REGISTRY, use)
    assert m["downstream_use"] is False                          # a stale read is not use
    U.record_reads("anomaly_miner", {"acquired:rba_c1_b": "v2"}, use="new_hypotheses", root=use)
    m = da.measure_item(BENCH["items"][1], rows, REGISTRY, use)
    assert m["downstream_use"] is True


def test_no_registry_reads_unmeasured_ingestion(tmp_path: Path) -> None:
    m = da.measure_item(BENCH["items"][1], _rows(tmp_path), None, tmp_path / "none")
    assert m["discovered"] is True and m["ingested"] == da.UNMEASURED
    assert m["field_coverage"] == da.UNMEASURED


def test_registry_only_discovery_is_attributed_to_the_acquirer(tmp_path: Path) -> None:
    reg = {"by_url": {"https://oui.example.gov/csv/ar539.csv": {"series": ["claims"]}}}
    m = da.measure_item(BENCH["items"][2], [], reg, tmp_path / "none")
    assert m["discovered"] and m["routes"] == ["acquire_registry"] and m["ingested"] is True


def test_weekly_rotation_is_deterministic_by_iso_week() -> None:
    items = [{"id": f"i{n}"} for n in range(60)]
    a = da.weekly_subset(items, NOW, 0.34)
    assert len(a) == 20
    assert da.iso_week(NOW) == da.iso_week(NOW + timedelta(days=1))
    assert a == da.weekly_subset(items, NOW + timedelta(days=1), 0.34)
    later = da.weekly_subset(items, NOW + timedelta(days=7), 0.34)
    assert later != a and len(later) == 20


def test_the_real_benchmark_is_well_formed_and_withheld_from_every_seed() -> None:
    bench = json.loads(da.BENCHMARK.read_text("utf-8"))
    items = bench["items"]
    assert bench["label"] == da.LABEL
    assert 55 <= len(items) <= 80
    assert len({i["id"] for i in items}) == len(items)
    types = {i["type"] for i in items}
    assert {"weather_climate", "shipping_ports", "energy_electricity", "agriculture", "labour",
            "prices", "trade_customs", "satellite_numeric", "payments_retail",
            "procurement"} <= types
    assert len({i["region"] for i in items}) >= 5
    assert len({i["language"] for i in items}) >= 8
    for i in items:                       # sealed: hashes only, nothing a reader could copy
        assert i["url_h"] and i["id_h"] and "url" not in i and "dataset_id" not in i, i["id"]
        assert "title" not in i and "producer" not in i
    assert bench["sealed"] is True and bench["salt"]
    assert "http" not in da.BENCHMARK.read_text("utf-8")
    sources, _missing = da.seed_sources()
    assert "acquire_datasets._SEED_ENDPOINTS" in sources and "country packs" in sources
    assert da.contamination(items, sources, bench["salt"]) == [], \
        "a seed can read the withheld benchmark"


def test_a_sealed_benchmark_measures_exactly_what_the_plaintext_does(tmp_path: Path) -> None:
    rows = _rows(tmp_path)
    plain = da.audit(BENCH, now=NOW, rows=rows, registry=REGISTRY, sources={},
                     missing_sources=[], use_dir=tmp_path / "none")
    sealed = da.audit(da.seal(BENCH, "s4lt"), now=NOW, rows=rows, registry=REGISTRY,
                      sources={}, missing_sources=[], use_dir=tmp_path / "none")
    assert sealed["recall"] == plain["recall"] and sealed["discovered"] == plain["discovered"]
    assert sealed["ingested"] == plain["ingested"]
    leak = {"seed.json": "https://www.rba.example.au/tables/csv/c1-data.csv"}
    hit = da.audit(da.seal(BENCH, "s4lt"), now=NOW, rows=rows, registry=REGISTRY, sources=leak,
                   missing_sources=[], use_dir=tmp_path / "none")
    assert hit["verdict"] == "CONTAMINATED"
