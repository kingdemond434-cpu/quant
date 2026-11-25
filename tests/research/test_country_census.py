"""The country census: every ISO 3166-1 entry is classed, and MISSING may only fall."""
from __future__ import annotations

import json
from pathlib import Path

from libs.research import country_census as cc

ROOT = Path(__file__).resolve().parents[2]


def _iso(*rows: dict) -> dict:
    return {"countries": list(rows)}


def test_the_iso_table_is_the_whole_of_iso_3166_1() -> None:
    doc = json.loads((ROOT / "desks/mt5/data/iso3166_countries.json").read_text(encoding="utf-8"))
    codes = [c["alpha2"] for c in doc["countries"]]
    assert len(codes) == 249 and len(set(codes)) == 249
    assert {"US", "CN", "JP", "DE", "GB", "SA", "AX", "BV", "AQ"} <= set(codes)


def test_statuses_follow_the_rule() -> None:
    grounds = {"grounds": [
        {"region": "us", "kind": "macro"}, {"region": "us", "kind": "forum"},
        {"region": "us", "kind": "blog"}, {"region": "fr", "kind": "forum"},
        {"region": "fr", "kind": "forum"}, {"region": "fr", "kind": "forum"},
        {"region": "no", "kind": "official"}]}
    iso = _iso({"alpha2": "US"}, {"alpha2": "FR"}, {"alpha2": "NO"},
               {"alpha2": "SJ", "served_by": "NO", "served_by_why": "no own statistics body"},
               {"alpha2": "BV", "served_by": "XX"}, {"alpha2": "ZZ"})
    out = cc.census(iso, grounds)
    by = {r["alpha2"]: r["status"] for r in out["rows"]}
    assert by == {"US": "COVERED", "FR": "PARTIAL", "NO": "PARTIAL", "SJ": "SERVED_BY_PARENT",
                  "BV": "MISSING", "ZZ": "MISSING"}
    assert out["missing"] == 2 and out["missing_list"] == ["BV", "ZZ"]


def test_absent_files_are_unmeasured_never_zero() -> None:
    assert cc.census(None, {"grounds": []})["status"] == "UNMEASURED"


def test_missing_may_only_fall() -> None:
    before = {"status": "MEASURED", "missing": 10}
    assert cc.check_ratchet({"status": "MEASURED", "missing": 9}, before) is None
    assert "rose" in (cc.check_ratchet({"status": "MEASURED", "missing": 11}, before) or "")
    assert cc.check_ratchet({"status": "UNMEASURED"}, before)


def test_the_live_census_measures() -> None:
    out = cc.current()
    assert out["status"] == "MEASURED" and out["total"] == 249
