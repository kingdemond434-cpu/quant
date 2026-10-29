"""exit_news_tag: tagging, the null case, broker-time conversion, write-time refusal, day-set
coverage, the falsifiable summary, and the hourly wiring."""

from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
sys.path.insert(0, str(DESK / "research"))

import exit_news_tag as ent  # noqa: E402

#: The desk's server anchor (prop.e8_guard): America/New_York + 7h.
ANCHOR = (ZoneInfo("America/New_York"), 17)


def _ff(d: Path, rows: list[dict]) -> None:
    d.mkdir(exist_ok=True)
    with gzip.open(d / "rollup_x.jsonl.gz", "wt") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows))


def _filler(day: str) -> dict:
    return {"title": "JPY Filler", "symbols": ["JPY"], "impact": "Low",
            "event_date": f"{day}T12:00:00+00:00"}


def _cal(tmp: Path, extra_days: tuple[str, ...] = ()) -> dict:
    fomc = tmp / "event_calendar.json"
    fomc.write_text(json.dumps({"valid_through": "2026-12-31", "events": [
        {"utc": "2026-09-16T18:00:00Z", "name": "FOMC decision", "impact": "high"},
        {"utc": "2026-10-28T18:00:00Z", "name": "FOMC decision", "impact": "high"}]}))
    rows = [{"title": "USD Non-Farm Employment Change", "symbols": ["USD"], "impact": "High",
             "event_date": "2026-10-02T08:30:00-04:00"},
            {"title": "USD Final Wholesale Inventories m/m", "symbols": ["USD"], "impact": "Low",
             "event_date": "2026-10-02T10:00:00-04:00"}]
    rows += [_filler(d) for d in extra_days]
    _ff(tmp / "ff", rows)
    return ent.load_calendar(fomc, tmp / "ff")


# -------- tagging correctness and the null case
def test_tags_nearest_high_impact_release(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 10, 2, 12, 30, 25, tzinfo=UTC), cal)
    nw = t["news_window"]
    assert nw["name"] == "Non-Farm Employment Change" and nw["currency"] == "USD"
    assert nw["minutes_from_release"] == round(25 / 60, 2)
    assert t["calendar_coverage"] == "FULL" and t["in_window"] is True
    assert ent.tag(datetime(2026, 10, 2, 12, 20, tzinfo=UTC), cal)["news_window"][
        "minutes_from_release"] == -10.0
    assert ent.tag(datetime(2026, 10, 28, 18, 5, tzinfo=UTC), cal)["news_window"][
        "name"] == "FOMC decision"


def test_null_case_and_low_impact_ignored(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 10, 2, 14, 0, tzinfo=UTC), cal)
    assert t["news_window"] is None and t["in_window"] is False
    assert ent.tag(datetime(2026, 10, 2, 12, 46, tzinfo=UTC), cal)["news_window"] is None


def test_null_without_full_coverage_is_unmeasured(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    t = ent.tag(datetime(2026, 11, 6, 13, 30, tzinfo=UTC), cal)
    assert t["calendar_coverage"] == "FOMC_ONLY" and t["in_window"] is None
    assert "NFP" in t["unmeasured_series"]
    assert ent.tag(datetime(2027, 6, 1, tzinfo=UTC), cal)["calendar_coverage"] == "NONE"


# -------- MUST 1: broker wall time is converted, never read as UTC
def test_broker_wall_exit_converted_then_tagged(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    # 12:31Z true UTC on 2026-10-02 (EDT) is 15:31 broker wall, stamped "+00:00" by the gateway
    row = {"exit_time": "2026-10-02T15:31:00+00:00", "timestamp_basis": "broker_deal_epoch",
           "position_id": 7, "deal": 9}
    [x] = ent.ledger_rows("live_ledger", [row], ANCHOR)
    assert x["exit_utc"] == datetime(2026, 10, 2, 12, 31, tzinfo=UTC)
    [r] = ent.enrich([x], cal)
    assert r["in_window"] is True and r["news_window"]["minutes_from_release"] == 1.0
    assert r["exit_id"] == "live_ledger:7:9"
    # read naively as UTC the same stamp sits 3h away and misses the release
    assert ent.tag(datetime(2026, 10, 2, 15, 31, tzinfo=UTC), cal)["in_window"] is False


def test_no_anchor_is_unmeasured(monkeypatch) -> None:
    class _NoAnchor:
        @staticmethod
        def broker_to_utc(wall, anchor=None):
            return None
    monkeypatch.setattr(ent, "_broker_anchor", lambda: _NoAnchor)
    u, why = ent.exit_true_utc("2026-10-02T15:31:00+00:00", "broker_deal_epoch")
    assert u is None and why.startswith("UNMEASURED")
    u, why = ent.exit_true_utc("2026-10-02T15:31:00+00:00", "something_else")
    assert u is None and "unknown timestamp_basis" in why


# -------- MUST 2: a row with no exit_time is never tagged from `time`
def test_missing_exit_time_is_unmeasured_not_write_time(tmp_path: Path) -> None:
    cal = _cal(tmp_path)
    row = {"time": "2026-10-02T12:30:00+00:00", "timestamp_basis": "broker_deal_epoch",
           "deal": 1}
    [r] = ent.enrich(ent.ledger_rows("live_ledger", [row], ANCHOR), cal)
    assert r["exit_utc"] is None and r["in_window"] is None and r["news_window"] is None
    assert r["calendar_coverage"] == "UNMEASURED"


# -------- MUST 3: coverage is the captured day set; the whole window must sit inside it
def test_gap_week_is_not_covered(tmp_path: Path) -> None:
    week1 = tuple(f"2026-09-{d:02d}" for d in range(1, 8))
    week3 = tuple(f"2026-09-{d:02d}" for d in range(15, 22))
    cal = _cal(tmp_path, week1 + week3)
    assert ent.tag(datetime(2026, 9, 3, 12, tzinfo=UTC), cal)["calendar_coverage"] == "FULL"
    gap = ent.tag(datetime(2026, 9, 10, 12, 30, tzinfo=UTC), cal)   # week 2: never captured
    assert gap["calendar_coverage"] != "FULL" and gap["in_window"] is None


def test_window_crossing_last_covered_day_is_not_full(tmp_path: Path) -> None:
    cal = _cal(tmp_path, ("2026-09-01", "2026-09-02"))
    assert ent.tag(datetime(2026, 9, 2, 23, 40, tzinfo=UTC), cal)["calendar_coverage"] == "FULL"
    t = ent.tag(datetime(2026, 9, 2, 23, 55, tzinfo=UTC), cal)
    assert t["calendar_coverage"] != "FULL" and t["in_window"] is None


# -------- MUST 4: the summary is one JSON object the falsifier can read
def test_summary_is_falsifiable(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from libs.tiers import contracts, experiment_contract
    cal = _cal(tmp_path)
    p = tmp_path / "x.csv"
    p.write_text("account,symbol,side,exit_utc,slip_pts,basis\n"
                 "e8,XAUUSD,sell,2026-10-02T12:30:25Z,2300.0,exit_type=stop\n"
                 "e8,XAUUSD,buy,2026-10-02T15:00:00Z,3.0,exit_type=stop\n"
                 "e8,XAUUSD,buy,2026-11-06T15:00:00Z,7.0,exit_type=stop\n")
    rows = ent.enrich(ent.csv_exits(p), cal)
    summ = ent.summary(rows, cal)
    out, sp = tmp_path / "EXIT_NEWS_TAGS.jsonl", tmp_path / "EXIT_NEWS_TAGS_SUMMARY.json"
    ent.write(rows, out, summ, sp)
    assert len({json.loads(x)["exit_id"] for x in out.read_text().splitlines()}) == 3
    assert (summ["n_in_window"], summ["n_out_of_window"], summ["n_unmeasured"]) == (1, 1, 1)
    assert summ["median_slip_in_window"] == 2300.0 and summ["n_measured"] == 2
    c = json.loads((ROOT / "docs/research/experiment_contracts.json").read_text())[
        "legs"]["exit_news_tag"]
    doc, how = experiment_contract.report_for(c, tmp_path)
    assert how == "read"
    assert contracts.read_metric(doc, c["falsifier"]["metric"]) == 2.0
    assert experiment_contract.judge_falsifier(c, doc)["verdict"] == experiment_contract.HOLDS
    sp.write_text(json.dumps({**summ, "n_measured": 0}))
    doc, _ = experiment_contract.report_for(c, tmp_path)
    assert experiment_contract.judge_falsifier(c, doc)["verdict"] == experiment_contract.FALSIFIED


# -------- wiring (III.16)
def test_leg_is_wired() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"exit_news_tag", "research/exit_news_tag.py"' in src
    assert '"exit_news_tag": ent,' in src
    assert '"exit_news_tag": "execution"' in (ROOT / "libs/research/layers.py").read_text()
    rs = json.loads((ROOT / "docs/research/runtime_state.json").read_text())
    assert any(o["organ"] == "leg:exit_news_tag" for o in rs["organs"])
    ps1 = (DESK / "scripts/sync_shadow_to_git.ps1").read_text(encoding="utf-8")
    assert "desks/mt5/reports/EXIT_NEWS_TAGS_SUMMARY.json" in ps1
