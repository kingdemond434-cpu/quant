"""Culture-gap producers: the gap's own clock, converted honestly, minted at the one door."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import session_clock as SC  # noqa: E402
from libs.research import cell_culture as CC  # noqa: E402
from research import culture_gap_cells as G  # noqa: E402

_REC = G.recipes()
_ROSTER = G.roster()


def _fix(at: str, tz: str, **kw: object) -> dict:
    return {"id": "t", "family": "fx_fixing_reversal", "symbols": ["USDCNH"],
            "windows": [{"param": "fix_hour", "tz": tz, "at": at, "align": "contains"}],
            "grid": {}, "charts": ["H1"], **kw}


def test_the_pboc_fix_is_two_broker_hours_a_year_and_both_round_trip() -> None:
    kept, dropped = G.variants(_fix("09:15", "Asia/Shanghai"), 2026)
    hours = {v["params"]["fix_hour"]: v["share"] for v in kept}
    # 09:15 Beijing = 01:15 UTC: New York + 7 h is 04:15 on US daylight time, 03:15 otherwise
    assert set(hours) == {3, 4} and not dropped
    assert hours[4] > hours[3] and abs(sum(hours.values()) - 1.0) < 1e-6
    stamp = pd.DatetimeIndex(["2026-07-15 04:15"], tz="UTC")
    assert SC.server_to_utc(stamp)[0] == pd.Timestamp("2026-07-15 01:15", tz="UTC")


def test_a_dst_mismatch_week_is_published_not_minted() -> None:
    kept, dropped = G.variants(_fix("14:10", "Europe/Berlin"), 2026)
    assert [v["params"]["fix_hour"] for v in kept] == [15]
    assert dropped and dropped[0]["share"] < G.MIN_VARIANT_SHARE and "DST" in dropped[0]["why"]


def test_start_alignment_takes_the_first_full_hour_and_spans_wrap() -> None:
    days = G.weekdays(2026)[150:151]                            # a summer day
    w = {"param": "hours", "tz": "Asia/Kolkata", "at": "10:00", "align": "start", "span": 2}
    # 10:00 IST = 04:30 UTC -> 00:30 EDT + 7 = 07:30 stamp; the first full bar is 08
    assert G.window_hours(w, days) == [(8, 9)]
    late = {"param": "hours", "tz": "America/New_York", "at": "16:30", "align": "start",
            "span": 2}
    assert G.window_hours(late, days) == [(0, 1)]


def test_a_handoff_whose_trade_hour_precedes_its_source_is_refused() -> None:
    rec = {"id": "t", "family": "session_handoff", "fixed": {"source_bars": 1},
           "windows": [{"param": "source_start_hour", "tz": "Europe/London", "at": "08:00",
                        "align": "start"},
                       {"param": "trade_hour", "tz": "Asia/Tokyo", "at": "09:00",
                        "align": "start"}]}
    kept, dropped = G.variants(rec, 2026)
    assert not kept and dropped and all("same day" in d["why"] for d in dropped)


def test_every_recipe_is_executable_honest_and_mt5_only() -> None:
    from mt5desk.families import live_family_names
    fams = set(live_family_names())
    uni = G.universe()
    asia = {str(r.get("id")) for r in json.loads(
        (_DESK / "data" / "asia_sources.json").read_text("utf-8"))["sources"]}
    ground_names = {g["name"] for g in json.loads(
        (_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))["grounds"]}
    assert len(_REC) >= 40 and len({r["id"] for r in _REC}) == len(_REC)
    for r in _REC:
        assert r["family"] in fams and r["family"] not in G.BANNED_FAMILIES, r["id"]
        assert all(s.upper() in uni for s in r["symbols"]), r["id"]
        assert not any(s.upper().endswith(("USDT", "PERP")) for s in r["symbols"])
        assert r["participant_structure"] in CC.PARTICIPANT_STRUCTURES, r["id"]
        assert CC.CULTURE_RE.match(r["source_culture"]), r["id"]
        assert CC.jurisdiction_of(r["source_culture"]) == r["gap"]["jurisdiction"], r["id"]
        src = str(r["source_id"])
        assert src in _ROSTER or src in asia or src in ground_names, (r["id"], src)
        for w in r.get("windows") or []:
            assert w["align"] in ("contains", "start") and w["tz"] and ":" in w["at"]


def test_the_roster_is_keyless_and_every_row_is_a_forest_ground() -> None:
    from libs.research import mechanism_claims as mc
    grounds = {g.get("url") for g in json.loads(
        (_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))["grounds"]}
    for sid, row in _ROSTER.items():
        assert row["auth"] == "none" and row["url"].startswith("https://"), sid
        assert row["fetcher"] == "owned" and row["consumer"].endswith("culture_gap_cells.py")
        assert mc.forbidden_venue(row["url"]) is None, sid
        assert row["url"] in grounds, sid
        assert row["verified"] in ("page", "secondary", "url_only", CC.UNMEASURED), sid


def test_a_conditioner_without_its_pack_series_is_unmeasured(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    monkeypatch.setattr(G, "SERIES_DIR", tmp_path / "series")
    rec = next(r for r in _REC if r["family"] == "exogenous_conditioner")
    cells, note = G.cells_for(rec, 2026, G.universe())
    assert cells == [] and str(note["unmeasured"]).startswith(CC.UNMEASURED)


def test_cells_reach_the_registry_with_declared_culture_once(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    monkeypatch.setattr(G, "SERIES_DIR", tmp_path / "series")
    recs = [r for r in _REC if r["id"] in ("cn_pboc_fix", "jp_tax_calendar_jpn225")]
    rp = tmp_path / "recipes.json"
    rp.write_text(json.dumps({"recipes": recs}), encoding="utf-8")
    summary = tmp_path / "CELL_CULTURE.json"
    summary.write_text(json.dumps({"gaps": [
        {"asset_class": "index", "culture": "JP/ja", "participant_structure": "tax_driven",
         "state": "ZERO"}]}), encoding="utf-8")
    cur = tmp_path / "cursor.json"
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        doc = G.run(60, year=2026, recipes_path=rp, summary=summary, cursor_path=cur)
        assert doc["recipes"][0]["id"] == "jp_tax_calendar_jpn225"   # ZERO first
        assert doc["recipes"][1]["gap_state"] == "COVERED"
        n = doc["totals"]["emitted_this_pass"]
        assert n == doc["totals"]["created_this_pass"] == 18 + 8
        conn = R.connect()
        rows = conn.execute("select family, symbol, params_json, source_culture, "
                            "participant_structure, culture_derivation, origin "
                            "from research_candidates").fetchall()
        conn.close()
        assert len(rows) == n
        for r in rows:
            assert r["origin"] == G.ORIGIN and r["family"] != "discovered"
            how = json.loads(r["culture_derivation"])
            assert how["source_culture"] == how["participant_structure"] == CC.DECLARED
            assert CC.is_source_derived(how)
        fix = [r for r in rows if r["family"] == "fx_fixing_reversal"]
        assert {json.loads(r["params_json"])["fix_hour"] for r in fix} == {3, 4}
        assert {r["source_culture"] for r in fix} == {"CN/zh"}
        again = G.run(60, year=2026, recipes_path=rp, summary=summary, cursor_path=cur)
        assert again["totals"]["emitted_this_pass"] == 0                # never searched twice
    finally:
        R.set_path(None)


def test_no_summary_is_unmeasured_and_reorders_nothing(tmp_path: Path) -> None:
    doc = G.run(30, dry_run=True, year=2026, summary=tmp_path / "absent.json")
    assert str(doc["gap_list"]).startswith(CC.UNMEASURED)
    assert {r["gap_state"] for r in doc["recipes"]} == {CC.UNMEASURED}
    assert doc["totals"]["cells_total"] >= 1000
