"""DATA-13: six separate discovery buckets and cohort arrivals/completion/backlog age, from
fixtures with no network."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import dataset_use as U  # noqa: E402
from research import discovery_audit as A  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _world(tmp_path: Path) -> list[dict]:
    world = tmp_path / "world"
    world.mkdir()
    rows = [
        {"source": "catalog_routes", "route": "ckan", "country": "AU", "region": "Asia-Pacific",
         "lang": "en", "producer_type": "subnational_portal", "access": "OPEN",
         "endpoints": ["https://nsw.test/a.csv"],
         "first_discovered_at": "2026-10-05T12:00:00+00:00"},
        {"source": "catalog_routes", "route": "ckan", "country": "AU", "region": "Asia-Pacific",
         "lang": "en", "producer_type": "subnational_portal", "access": "OPEN",
         "endpoints": ["https://nsw.test/b.csv"],
         "first_discovered_at": "2026-10-06T12:00:00+00:00"},
        {"source": "catalog_routes", "route": "sdmx", "country": "JP", "region": "Asia-Pacific",
         "lang": "ja", "producer_type": "statistics_office", "access": "NEEDS_KEY",
         "endpoints": [], "keyed_endpoints": ["https://estat.test/k"],
         "first_discovered_at": "2026-09-28T12:00:00+00:00"},
        {"source": "catalog_routes", "route": "ckan", "country": "AU", "region": "Asia-Pacific",
         "lang": "en", "producer_type": "subnational_portal", "access": "OPEN",
         "endpoints": ["https://nsw.test/c.csv"], "mirror_of": "x",
         "first_discovered_at": "2026-10-06T12:00:00+00:00"},
    ]
    (world / "discoveries_catalog_20261006.json").write_text(json.dumps(rows))
    return A.load_discoveries(world)


def test_six_buckets_are_published_separately(tmp_path):
    rows = _world(tmp_path)
    registry = {"by_url": {"https://nsw.test/a.csv": {"status": "SUCCESS"}},
                "access": {"https://estat.test/k": {"state": "BLOCKED_ON_KEY:ESTAT_APP_ID"}}}
    state = {"portals": {"au_nsw": {"last_visit_at": "2026-10-06", "status": "OK",
                                    "total": 200, "remainder": 50},
                         "jp_estat": {"status": "TERMS_UNVERIFIED", "remainder": "UNMEASURED"}}}
    roster = {"portals": [{"id": "au_nsw", "country": "AU", "region": "Asia-Pacific"},
                          {"id": "jp_estat", "country": "JP", "region": "Asia-Pacific"},
                          {"id": "br_x", "country": "BR", "region": "Americas"}]}
    U.record_reads("world_model", {"acquired:a": "v"}, use="nowcast", root=tmp_path / "use",
                   now=NOW)
    audit = {"verdict": "OK", "recall": 0.4, "full_benchmark_recall": 0.35, "measured": 10}
    bk = A.buckets(rows, registry, audit, NOW, catalog_state=state, roster=roster,
                   frontier={"n_cold_cells": 7}, use_dir=tmp_path / "use")
    for key in ("known_catalog_coverage", "benchmark_recall", "unexplored_regions",
                "access_blocked", "acquisition_backlog", "verified_consumption"):
        assert key in bk and bk[key]["status"] in ("MEASURED", "UNMEASURED", "CONTAMINATED")
    cat = bk["known_catalog_coverage"]
    assert cat["enumerated"] == 150 and cat["declared_total"] == 200
    assert cat["portals_unmeasured"] == 1                        # remainder not an int: named
    assert bk["benchmark_recall"]["recall"] == 0.4
    un = bk["unexplored_regions"]
    assert un["roster_countries_without_a_row"] == ["BR"]
    assert un["portals_never_visited"] == ["br_x"]
    assert un["frontier_cold_cells"] == 7
    ab = bk["access_blocked"]
    assert ab["discovery_rows_by_access"] == {"NEEDS_KEY": 1}
    assert ab["portals"] == [{"portal": "jp_estat", "status": "TERMS_UNVERIFIED"}]
    assert ab["acquirer_keyed"] == {"BLOCKED_ON_KEY": 1}
    assert bk["acquisition_backlog"]["open_endpoint_rows"] == 1   # b.csv; the mirror is not counted
    assert bk["acquisition_backlog"]["oldest_age_h"] == 24.0
    assert bk["verified_consumption"]["datasets_read_in_window"] == 1
    assert bk["flow"] == {**bk["flow"], "arrivals": 2, "completed": 1, "backlog": 1}


def test_cohorts_carry_arrivals_completion_and_backlog_age(tmp_path):
    rows = _world(tmp_path)
    bk = A.buckets(rows, {"by_url": {"https://nsw.test/a.csv": {"status": "SUCCESS"}}},
                   {"verdict": "UNMEASURED", "why": "salt absent"}, NOW,
                   use_dir=tmp_path / "use")
    week = bk["cohorts"]["week"]["2026-W41"]
    assert week["arrivals"] == 2 and week["completed"] == 1 and week["completion"] == 0.5
    assert week["backlog_age_h_max"] == 24.0
    assert bk["cohorts"]["language"]["en"]["arrivals"] == 2
    assert bk["cohorts"]["type"]["subnational_portal"]["backlog"] == 1
    assert bk["benchmark_recall"]["status"] == "UNMEASURED"
    assert bk["known_catalog_coverage"]["status"] == "UNMEASURED"
    assert bk["verified_consumption"]["status"] == "UNMEASURED"     # no reads: never zero


def test_no_registry_reads_backlog_unmeasured(tmp_path):
    bk = A.buckets(_world(tmp_path), None, {"verdict": "OK"}, NOW, use_dir=tmp_path / "use")
    assert bk["acquisition_backlog"]["status"] == "UNMEASURED"
