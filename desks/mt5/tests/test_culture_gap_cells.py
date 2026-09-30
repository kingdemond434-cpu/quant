"""Culture-gap producers: the gap's own clock, converted honestly, minted at the one door."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
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


def _stamps(start: str, end: str) -> pd.DatetimeIndex:
    """Broker-stamped H1 bars (New York + 7 h wearing a UTC label), weekdays only."""
    idx = pd.date_range(start, end, freq="h", tz="UTC")
    return idx[idx.dayofweek < 5]


def test_the_pboc_fix_is_one_local_cell_on_the_right_bar_every_date() -> None:
    """ONE cell, not a 65%/35% pair: 09:15 Beijing is the 04:00 stamp on US daylight time and
    the 03:00 stamp otherwise, and the family finds whichever it is on each date."""
    from mt5desk import local_clock as LC
    kept, dropped = G.variants(_fix("09:15", "Asia/Shanghai"), 2026)
    assert not dropped and len(kept) == 1 and kept[0]["share"] == 1.0
    p = kept[0]["params"]
    assert p == {"fix_tz": "Asia/Shanghai", "fix_at": "09:15", "fix_align": "contains"}
    idx = _stamps("2026-01-05", "2026-12-31")
    mask = LC.window_mask(idx, p["fix_tz"], p["fix_at"], p["fix_align"])
    assert mask is not None
    hit = idx[mask]
    by_day = pd.Series(hit.hour, index=hit.normalize())
    assert (by_day.groupby(level=0).size() == 1).all()          # exactly one bar a date
    assert by_day[pd.Timestamp("2026-07-15", tz="UTC")] == 4
    assert by_day[pd.Timestamp("2026-01-14", tz="UTC")] == 3
    assert SC.server_to_utc(pd.DatetimeIndex(["2026-07-15 04:15"], tz="UTC"))[0] == (
        pd.Timestamp("2026-07-15 01:15", tz="UTC"))


def test_the_london_fix_follows_both_dst_calendars_including_the_mismatch_weeks() -> None:
    """16:00 London is the 18:00 stamp most of the year and 19:00 in the weeks the US has
    changed its clocks and the UK has not -- the weeks a broker-hour cell got wrong."""
    from mt5desk import local_clock as LC
    idx = _stamps("2026-03-02", "2026-04-10")
    mask = LC.window_mask(idx, "Europe/London", "16:00", "contains")
    assert mask is not None
    hit = pd.Series(idx[mask].hour, index=idx[mask].normalize())
    assert hit[pd.Timestamp("2026-03-04", tz="UTC")] == 18      # both on winter time
    assert hit[pd.Timestamp("2026-03-18", tz="UTC")] == 19      # US on DST, UK not yet
    assert hit[pd.Timestamp("2026-04-08", tz="UTC")] == 18      # both on summer time


def test_a_half_hour_zone_is_matched_in_minutes() -> None:
    from mt5desk import local_clock as LC
    idx = _stamps("2026-07-13", "2026-07-17")
    mask = LC.window_mask(idx, "Asia/Kolkata", "12:00", "contains")
    assert mask is not None
    local = SC.server_to_utc(idx[mask]).tz_convert("Asia/Kolkata")
    assert set(zip(local.hour, local.minute, strict=True)) == {(11, 30)}   # 11:30-12:30 bar


def test_start_alignment_takes_the_first_full_hour_and_spans_wrap() -> None:
    days = G.weekdays(2026)[150:151]                            # a summer day
    w = {"param": "hours", "tz": "Asia/Kolkata", "at": "10:00", "align": "start", "span": 2}
    # 10:00 IST = 04:30 UTC -> 00:30 EDT + 7 = 07:30 stamp; the first full bar is 08
    assert G.window_hours(w, days) == [(8, 9)]
    late = {"param": "hours", "tz": "America/New_York", "at": "16:30", "align": "start",
            "span": 2}
    assert G.window_hours(late, days) == [(0, 1)]


def _bars(idx: pd.DatetimeIndex, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.6, len(idx)))
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": op, "high": np.maximum(op, close) + 0.3,
                         "low": np.minimum(op, close) - 0.3, "close": close}, index=idx)


def test_a_local_handoff_only_ever_trades_after_its_source_closed() -> None:
    """The broker-hour handoff grouped by broker day and could read a later bar of that day; the
    local one pairs each source window with the FIRST trade window after it, within 24 h."""
    from mt5desk import local_clock as LC
    from mt5desk.families_edge_queue import family_session_handoff
    idx = _stamps("2026-01-05", "2026-06-30")
    df = _bars(idx)
    kw = {"source_tz": "Europe/London", "source_at": "08:00", "source_align": "start",
          "trade_tz": "Asia/Tokyo", "trade_at": "09:00", "trade_align": "start"}
    sigs = family_session_handoff(df, source_bars=2, min_info_atr=0.1, **kw)
    assert sigs
    src = idx[LC.window_mask(idx, "Europe/London", "08:00", "start")]
    trd = set(idx[LC.window_mask(idx, "Asia/Tokyo", "09:00", "start")])
    for g in sigs:
        assert g.time in trd
        before = src[src < g.time]
        gap = g.time - (before[-1] + pd.Timedelta(hours=1))
        assert pd.Timedelta(0) <= gap <= pd.Timedelta(hours=24)


def test_the_boc_cell_fires_only_on_announcement_days_in_the_0945_bar() -> None:
    from mt5desk import local_clock as LC
    from mt5desk.families_edge_queue import family_fx_fixing_reversal
    rec = next(r for r in _REC if r["id"] == "ca_boc_announcement_hour")
    kept, _ = G.variants(rec, 2026)
    assert kept[0]["params"] == {"calendar": "boc_policy_rate", "fix_align": "contains"}
    cal = LC.calendar("boc_policy_rate")
    assert cal is not None and cal[0] == "America/Toronto" and len(cal[1]) >= 8
    idx = _stamps("2025-01-01", "2026-09-30")
    sigs = family_fx_fixing_reversal(_bars(idx, 3), pre_window_bars=1, min_displacement_atr=0.0,
                                     **kept[0]["params"])
    assert sigs
    local = SC.server_to_utc(pd.DatetimeIndex([g.time for g in sigs])).tz_convert(
        "America/Toronto")
    days = {int(f"{t.year}{t.month:02d}{t.day:02d}") for t in local}
    assert days <= set(cal[1]) and len(days) >= 12              # announcement days only
    assert set(local.hour) == {9}                               # the bar holding 09:45
    # without the calendar the same fix fires on every weekday -- which is what it replaced
    daily = family_fx_fixing_reversal(_bars(idx, 3), pre_window_bars=1, min_displacement_atr=0.0,
                                      fix_tz="America/Toronto", fix_at="09:45")
    assert len(daily) > 10 * len(sigs)


def test_a_local_close_is_the_venue_close_on_every_date() -> None:
    from mt5desk.families_edge_queue import family_hedging_demand_close
    idx = _stamps("2026-01-05", "2026-06-30")
    sigs = family_hedging_demand_close(
        _bars(idx, 5), min_displacement_atr=0.0, require_elevated_vol=False,
        close_tz="Europe/Berlin", close_at="17:30", close_align="contains",
        rod_start_tz="Europe/Berlin", rod_start_at="09:00", rod_start_align="start")
    assert sigs
    local = SC.server_to_utc(pd.DatetimeIndex([g.time for g in sigs])).tz_convert(
        "Europe/Berlin")
    assert set(local.hour) == {17}


def test_a_symbol_the_broker_will_not_trade_is_gated_and_named() -> None:
    rows = G.universe_rows()
    rub = G.tradability("USDRUB", rows, None)
    assert not rub["ok"] and "median spread" in rub["why"]
    assert rub["trade_mode"] == CC.UNMEASURED                    # never read as a pass or a 0
    eur = G.tradability("EURRUB", rows, None)                  # 1.4M-point snapshot, 250 median
    assert eur["ok"] and eur["snapshot_spread_cost"] > 0.05 > eur["median_spread_cost"]
    assert G.tradability("USDMXN", rows, None)["ok"]
    closing = G.tradability("USDMXN", rows, {"USDMXN": 3})
    assert not closing["ok"] and "CLOSE_ONLY" in closing["why"]
    rec = next(r for r in _REC if r["id"] == "ru_retail_moex_open")
    cells, note = G.cells_for(rec, 2026, G.universe(), rows=rows, modes=None)
    assert {g["symbol"] for g in note["gated"]} == {"USDRUB"}      # the USDRUB gate stays
    assert cells and {c["symbol"] for c in cells} == {"EURRUB"}


def test_one_bad_snapshot_never_gates_the_median_and_trade_mode_do() -> None:
    """EURRUB was gated on ONE 10.33% print against a 0.0018% median: the snapshot is reported,
    only the median (or the box's trade_mode) vetoes."""
    rows = {"EURUSD": {"tick_value": 1.0, "tick_size": 1e-5, "contract_size": 100000.0},
            "USDXXX": {"median_spread_pts": 2.0, "spread_pts_at_collection": 5e6,
                       "tick_value": 1.0, "tick_size": 1e-5, "contract_size": 100000.0}}
    t = G.tradability("USDXXX", rows, None)
    assert t["ok"] and t["snapshot_spread_cost"] > 0.01
    rows["USDXXX"]["median_spread_pts"] = 5e3
    assert "median spread" in G.tradability("USDXXX", rows, None)["why"]
    rows["USDXXX"]["median_spread_pts"] = 2.0
    assert "DISABLED" in G.tradability("USDXXX", rows, {"USDXXX": 0})["why"]
    rows["USDXXX"]["median_spread_pts"] = None                  # UNMEASURED never gates
    assert G.tradability("USDXXX", rows, None)["ok"]


def test_every_gate_writes_its_missed_growth_line_once_a_day(tmp_path: Path) -> None:
    """Rule 1: a veto bills what it withheld. One row per (day, recipe:symbol), value UNMEASURED
    (never 0), in the ledger's own shape; an hourly leg never appends the same day twice."""
    gated = [{"recipe": "ru_retail_moex_open", "symbol": "USDRUB", "cells_not_minted": 12,
              "why": "median spread 0.179% of notional > 0.10%", "trade_mode": CC.UNMEASURED,
              "median_spread_cost": 0.0018, "snapshot_spread_cost": 0.015}]
    led = tmp_path / "missed_growth.jsonl"
    lines = G.missed_growth_lines(gated, "2026-09-30")
    assert G.append_missed_growth(lines, led) == 1
    assert G.append_missed_growth(G.missed_growth_lines(gated, "2026-09-30"), led) == 0
    assert G.append_missed_growth(G.missed_growth_lines(gated, "2026-10-01"), led) == 1
    rows = [json.loads(x) for x in led.read_text().splitlines()]
    assert len(rows) == 2 and {r["rail"] for r in rows} == {G.GATE_RAIL}
    for r in rows:
        assert set(r) >= {"day", "rail", "value", "at"} and r["value"] is None
        assert r["value_status"].startswith(CC.UNMEASURED) and r["cells_not_minted"] == 12
    from libs.portfolio.rails import RAILS  # sealed register: not a rail there
    assert G.GATE_RAIL not in {x.name for x in RAILS}


def test_crowding_reads_the_english_evidence_the_run_was_given(tmp_path: Path) -> None:
    rec = next(r for r in _REC if r["id"] == "cn_pboc_fix")
    cell = {"symbol": "USDCNH", "params": {}, "chart": "H1"}
    none = G._culture(rec, cell, {}, None if False else frozenset({"fx_fixing_reversal"}))
    assert none["crowding_prior"] == CC.UNMEASURED              # covered in English: no rule
    low = G._culture(rec, cell, {}, frozenset({"carry"}))
    assert low["crowding_prior"] == "low"
    assert low[CC.DERIVATION_FIELD]["crowding_prior"].startswith("inferred")
    summary = tmp_path / "CELL_CULTURE.json"
    summary.write_text(json.dumps({"english_covered_families": ["carry"]}), encoding="utf-8")
    assert G.english_families(summary) == frozenset({"carry"})
    assert G.english_families(tmp_path / "absent.json") is None


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


def _isolate_door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the donation door (intake dir, pre-registration ledger, registry backup) at tmp."""
    from libs.moat import registry as R
    from libs.ops import throughput as TP
    from libs.research import preregistration as PR
    from research import proposer_common as PC
    intel = tmp_path / "intel"
    monkeypatch.setattr(PC, "INTEL", intel)
    monkeypatch.setattr(PR, "LEDGER", tmp_path / "prereg.jsonl")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    monkeypatch.setattr(TP, "SAMPLES", tmp_path / "throughput_samples.jsonl")
    monkeypatch.setattr(G, "SERIES_DIR", tmp_path / "series")
    monkeypatch.setattr(G, "MISSED", tmp_path / "missed_growth.jsonl")
    return intel


def test_cells_reach_the_registry_with_declared_culture_once(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    from libs.moat import registry as R
    _isolate_door(tmp_path, monkeypatch)
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
        assert n == doc["totals"]["created_this_pass"] == 9 + 8   # one local cell per grid pt
        conn = R.connect()
        rows = conn.execute("select family, symbol, params_json, source_culture, "
                            "participant_structure, culture_derivation, origin "
                            "from research_candidates where origin = ?",
                            (G.ORIGIN,)).fetchall()
        conn.close()
        assert len(rows) == n                                         # the lineage rows
        assert doc["donation"]["donated"] == n == doc["donation"]["tests_run"]
        for r in rows:
            assert r["origin"] == G.ORIGIN and r["family"] != "discovered"
            how = json.loads(r["culture_derivation"])
            assert how["source_culture"] == how["participant_structure"] == CC.DECLARED
            assert CC.is_source_derived(how)
        fix = [r for r in rows if r["family"] == "fx_fixing_reversal"]
        assert {json.loads(r["params_json"])["fix_tz"] for r in fix} == {"Asia/Shanghai"}
        assert {r["source_culture"] for r in fix} == {"CN/zh"}
        again = G.run(60, year=2026, recipes_path=rp, summary=summary, cursor_path=cur)
        assert again["totals"]["emitted_this_pass"] == 0                # never searched twice
    finally:
        R.set_path(None)


def test_recipe_to_donation_to_compiler_to_a_docket_row_with_all_four_fields(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """END TO END (2026-09-30): the registry door alone is never judged, so a gap cell must
    reach the COMPILER's intake. Recipe -> `run` donates through proposer_common.donate into
    data/intelligence/culture_gap/ -> the compiler reads that file with its own reader and
    compiles each row EXACT_RECIPE -> the docket candidate carries all four culture fields,
    the two the recipe knows as declared and the other two inferred by the one rule."""
    from libs.moat import registry as R
    from research import miner_candidate_compiler as MC
    intel = _isolate_door(tmp_path, monkeypatch)
    recs = [r for r in _REC if r["id"] == "cn_pboc_fix"]
    rp = tmp_path / "recipes.json"
    rp.write_text(json.dumps({"recipes": recs}), encoding="utf-8")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        doc = G.run(60, year=2026, recipes_path=rp, summary=tmp_path / "absent.json",
                    cursor_path=tmp_path / "cursor.json")
    finally:
        R.set_path(None)
    n = doc["totals"]["emitted_this_pass"]
    assert n > 0 and doc["donation"]["donated"] == n
    files = sorted((intel / G.SEAT).glob("discoveries_*.json"))
    assert len(files) == 1
    contract = json.loads(files[0].read_text(encoding="utf-8"))
    assert contract["tests_run"] == n                          # every trial charged
    universe = {s for r in recs for s in r["symbols"]}
    docket: list[dict] = []
    for row in MC._iter_file_rows(files[0]):
        assert row["available_time"] and row["payload_hash"]   # the PIT door stamped it
        produced, disposition = MC.compile_row(str(row["source"]), row, universe)
        assert disposition == "EXACT_RECIPE"
        docket.extend(MC.expand_axes(produced))
    assert len(docket) == n            # one fixed hour is never re-sliced by the session axis
    for cand in docket:
        assert cand["family"] == "fx_fixing_reversal" != "discovered"
        assert cand["params"]["session"] == "all"
        assert cand["mechanism_status"] == "NAMED" and len(cand["mechanism_note"]) >= 12
        how = cand[CC.DERIVATION_FIELD]
        for f in CC.FIELDS:                     # all four ride; none is laundered to a value
            assert cand[f], f
            assert (how[f] == CC.UNMEASURED) == (cand[f] == CC.UNMEASURED), f
        assert cand["failure_mode_hypothesis"] != CC.UNMEASURED
        assert cand["crowding_prior"] in CC.CROWDING_PRIORS
        assert cand["source_culture"] == "CN/zh"
        assert how["source_culture"] == how["participant_structure"] == CC.DECLARED
        assert how["failure_mode_hypothesis"] != CC.DECLARED     # inferred, not laundered
        assert CC.is_source_derived(how)
    assert {c["params"]["fix_tz"] for c in docket} == {"Asia/Shanghai"}


def test_each_rule_has_one_identity_and_one_charge_from_registry_to_docket(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE AUDIT'S DUPLICATE (2026-09-30): the donation added `session` to params the registry
    row did not carry, and the door wrote a second registry row, so each rule reached the docket
    twice (18 cells -> 36 docket identities), each judged and charged. Now: one registry
    candidate per cell, the docket feed's row and the compiler's cell have the SAME merge
    identity, and `tests_run` equals the number of cells."""
    from libs.moat import docket_feed as DF
    from libs.moat import registry as R
    from research import merge_hypotheses as MH
    from research import miner_candidate_compiler as MC
    intel = _isolate_door(tmp_path, monkeypatch)
    recs = [r for r in _REC if r["id"] in ("cn_pboc_fix", "ae_gold_dubai_to_london")]
    rp = tmp_path / "recipes.json"
    rp.write_text(json.dumps({"recipes": recs}), encoding="utf-8")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        doc = G.run(60, year=2026, recipes_path=rp, summary=tmp_path / "absent.json",
                    cursor_path=tmp_path / "cursor.json")
        conn = R.connect()
        reg = [dict(r) for r in conn.execute("select * from research_candidates")]
        conn.close()
    finally:
        R.set_path(None)
    n = doc["totals"]["emitted_this_pass"]
    assert n > 0 and len(reg) == n                         # no second row from the door
    assert {r["origin"] for r in reg} == {G.ORIGIN}
    fed = {MH._identity(DF._row(r) or {}) for r in reg}
    contract = json.loads(sorted((intel / G.SEAT).glob("discoveries_*.json"))[0].read_text())
    assert contract["tests_run"] == n                      # charged once, per cell
    universe = {s for r in recs for s in r["symbols"]}
    compiled = [c for row in contract["discoveries"]
                for c in MC.expand_axes(MC.compile_row(G.SEAT, row, universe)[0])]
    ids = {MH._identity(c) for c in compiled}
    assert len(compiled) == len(ids) == n
    assert ids == fed                                      # one identity, both doors


def test_no_summary_is_unmeasured_and_reorders_nothing(tmp_path: Path) -> None:
    doc = G.run(30, dry_run=True, year=2026, summary=tmp_path / "absent.json")
    assert str(doc["gap_list"]).startswith(CC.UNMEASURED)
    assert {r["gap_state"] for r in doc["recipes"]} == {CC.UNMEASURED}
    assert doc["totals"]["cells_total"] >= 1000


def test_bar_length_is_read_in_the_index_own_unit() -> None:
    """A us-resolution chart once read as 2-minute bars across a weekend and matched nothing."""
    from mt5desk import local_clock as LC
    idx = _stamps("2026-01-05", "2026-02-27")
    for unit in ("s", "ms", "us", "ns"):
        assert LC.bar_minutes(idx.as_unit(unit)) == 60


def test_a_lost_cursor_never_re_donates_or_re_charges(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """The cursor is gitignored state; the dedup that charges is by cell identity against the
    seat's own contract files. Delete the cursor: nothing is enqueued, donated or charged again."""
    from libs.moat import registry as R
    intel = _isolate_door(tmp_path, monkeypatch)
    recs = [r for r in _REC if r["id"] in ("cn_pboc_fix", "jp_tax_calendar_jpn225")]
    rp = tmp_path / "recipes.json"
    rp.write_text(json.dumps({"recipes": recs}), encoding="utf-8")
    cur = tmp_path / "cursor.json"
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        first = G.run(60, year=2026, recipes_path=rp, summary=tmp_path / "absent.json",
                      cursor_path=cur)
        n = first["totals"]["emitted_this_pass"]
        assert n > 0 and first["donation"]["tests_run"] == n
        assert first["donation"]["identities_on_file_before"] == 0
        cur.unlink()                                             # the cursor is gone
        again = G.run(60, year=2026, recipes_path=rp, summary=tmp_path / "absent.json",
                      cursor_path=cur)
    finally:
        R.set_path(None)
    assert again["donation"]["identities_on_file_before"] == n
    assert again["totals"]["emitted_this_pass"] == 0
    assert again["totals"]["already_donated_this_pass"] == n
    assert again["donation"]["donated"] == 0 and again["donation"]["path"] is None
    files = sorted((intel / G.SEAT).glob("discoveries_*.json"))
    assert len(files) == 1                                       # no second contract file
    charged = sum(json.loads(f.read_text())["tests_run"] for f in files)
    assert charged == n                                          # charged once, per cell
    # the rebuilt cursor marks them done, so a third pass is a no-op on the fast path too
    assert json.loads(cur.read_text())
    assert len(G.donated_identities(intel / G.SEAT)) == n


def test_the_donated_identity_is_the_identity_the_judge_stamps(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    """The ledger charges each identity once (experiment_ledger.lifetime): that only holds if
    the donated row's node_id is the node_id the compiled, judged cell carries."""
    from libs.moat import registry as R
    from libs.research.hypothesis_graph import node_id_for_spec
    from research import miner_candidate_compiler as MC
    intel = _isolate_door(tmp_path, monkeypatch)
    recs = [r for r in _REC if r["id"] in ("cn_pboc_fix", "ae_gold_dubai_to_london")]
    rp = tmp_path / "recipes.json"
    rp.write_text(json.dumps({"recipes": recs}), encoding="utf-8")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        G.run(60, year=2026, recipes_path=rp, summary=tmp_path / "absent.json",
              cursor_path=tmp_path / "cursor.json")
    finally:
        R.set_path(None)
    contract = json.loads(sorted((intel / G.SEAT).glob("discoveries_*.json"))[0].read_text())
    universe = {s for r in recs for s in r["symbols"]}
    compiled = {node_id_for_spec(c) for row in contract["discoveries"]
                for c in MC.expand_axes(MC.compile_row(G.SEAT, row, universe)[0])}
    assert compiled == G.donated_identities(intel / G.SEAT)


def test_a_local_handoff_reads_a_microsecond_index_as_hours() -> None:
    """`_local_handoff` read `asi8` in nanoseconds: on a datetime64[us] index a contiguous source
    span looked 1000x too short and no window ever paired. Same bars, any unit, same signals."""
    from mt5desk.families_edge_queue import _local_handoff
    idx = _stamps("2026-01-05", "2026-04-30")
    base = _bars(idx)
    args = ("Europe/London", "08:00", "start", 2, "Asia/Tokyo", "09:00", "start",
            0.1, 20, 1.0, 1.2, 6, 1)
    want = _local_handoff(base, *args)
    assert want
    for unit in ("us", "ms", "s"):
        df = base.copy()
        df.index = df.index.as_unit(unit)
        got = _local_handoff(df, *args)
        assert [(g.time, g.side, round(g.stop, 9)) for g in got] == \
            [(g.time, g.side, round(g.stop, 9)) for g in want], unit
