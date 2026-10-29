"""exit_news_tag: tagging correctness, the null case, coverage honesty, and the hourly wiring."""

from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import exit_news_tag as ent  # noqa: E402


def _cal(tmp: Path) -> dict:
    fomc = tmp / "event_calendar.json"
    fomc.write_text(json.dumps({"valid_through": "2026-12-31", "events": [
        {"utc": "2026-10-28T18:00:00Z", "name": "FOMC decision", "impact": "high"}]}))
    ff = tmp / "ff"
    ff.mkdir()
    rows = [{"title": "USD Non-Farm Employment Change", "symbols": ["USD"], "impact": "High",
             "event_date": "2026-10-02T08:30:00-04:00"},
            {"title": "USD Final Wholesale Inventories m/m", "symbols": ["USD"], "impact": "Low",
             "event_date": "2026-10-02T10:00:00-04:00"},
            {"title": "EUR ECB Press", "symbols": ["EUR"], "impact": "Low",
             "event_date": "2026-10-05T08:00:00-04:00"}]
    with gzip.open(ff / "rollup_x.jsonl.gz", "wt") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows))
    return ent.load_calendar(fomc, ff)


def test_tags_nearest_high_impact_release(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 10, 2, 12, 30, 25, tzinfo=UTC), cal)
    nw = t["news_window"]
    assert nw["name"] == "Non-Farm Employment Change" and nw["currency"] == "USD"
    assert nw["minutes_from_release"] == round(25 / 60, 2)
    assert t["calendar_coverage"] == "FULL" and t["in_window"] is True
    # before the release is negative
    assert ent.tag(datetime(2026, 10, 2, 12, 20, tzinfo=UTC), cal)["news_window"][
        "minutes_from_release"] == -10.0
    # FOMC file
    assert ent.tag(datetime(2026, 10, 28, 18, 5, tzinfo=UTC), cal)["news_window"][
        "name"] == "FOMC decision"


def test_null_case_and_low_impact_ignored(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 10, 2, 14, 0, tzinfo=UTC), cal)   # Low-impact 14:00Z only
    assert t["news_window"] is None and t["in_window"] is False
    t = ent.tag(datetime(2026, 10, 2, 12, 46, tzinfo=UTC), cal)  # 16 min after: outside +-15
    assert t["news_window"] is None


def test_null_without_full_coverage_is_unmeasured(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 11, 6, 13, 30, tzinfo=UTC), cal)
    assert t["news_window"] is None and t["calendar_coverage"] == "FOMC_ONLY"
    assert t["in_window"] is None and "NFP" in t["unmeasured_series"]
    t = ent.tag(datetime(2027, 6, 1, tzinfo=UTC), cal)
    assert t["calendar_coverage"] == "NONE" and t["in_window"] is None


def test_csv_enrich_writes_keyed_rows(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    p = tmp_path / "x.csv"
    p.write_text("account,symbol,side,exit_utc,slip_pts,basis\n"
                 "e8,XAUUSD,sell,2026-10-02T12:30:25Z,2300.0,exit_type=stop\n"
                 "e8,XAUUSD,buy,2026-10-02T15:00:00Z,3.0,exit_type=stop\n")
    rows = ent.enrich(ent.csv_exits(p), cal)
    out = tmp_path / "o.jsonl"
    ent.write(rows, out)
    got = [json.loads(x) for x in out.read_text().splitlines()]
    assert len({r["exit_id"] for r in got}) == 2
    s = ent.slip_split(rows)
    assert s["in_window"] == {"n": 1, "median": 2300.0, "max": 2300.0}
    assert s["out_of_window_measured"]["n"] == 1


def test_leg_is_wired() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"exit_news_tag", "research/exit_news_tag.py"' in src
    assert '"exit_news_tag": ent,' in src
    root = DESK.parents[1]
    sys.path.insert(0, str(root))
    from libs.research import layers
    assert layers.LEG_LAYER["exit_news_tag"] == "execution" if hasattr(
        layers, "LEG_LAYER") else '"exit_news_tag": "execution"' in (
        root / "libs" / "research" / "layers.py").read_text(encoding="utf-8")
    contracts = json.loads((root / "docs" / "research" / "experiment_contracts.json")
                           .read_text(encoding="utf-8"))
    assert "exit_news_tag" in contracts["legs"]
