"""The E8 scheduled-release fence (patch e8_news_fence/v1): default OFF, shadow-billed, RED-checked."""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import news_fence as nf  # noqa: E402

#: The 2026-10-02 london_am sell-stop fill, 5 min 8 s before the 12:30Z Employment Situation.
FILL_1002 = datetime(2026, 10, 2, 12, 24, 52, tzinfo=UTC)


def _flag(tmp_path: Path, body: object) -> Path:
    p = tmp_path / "E8_NEWS_FENCE.json"
    p.write_text(body if isinstance(body, str) else json.dumps(body), "utf-8")
    return p


def test_absent_flag_is_off_but_the_shadow_still_sees_the_1002_print(tmp_path) -> None:
    v = nf.verdict(FILL_1002, flag_path=tmp_path / "absent.json")
    assert not v.enabled and not v.blocks
    assert v.would_block and v.release == "2026-10-02 12:30Z NFP"


def test_enabled_flag_blocks_inside_the_window_and_not_outside(tmp_path) -> None:
    f = _flag(tmp_path, {"enabled": True, "pre_min": 15, "post_min": 15})
    assert nf.verdict(FILL_1002, flag_path=f).blocks
    assert not nf.verdict(datetime(2026, 10, 2, 12, 46, tzinfo=UTC), flag_path=f).blocks
    assert not nf.verdict(datetime(2026, 10, 2, 12, 14, tzinfo=UTC), flag_path=f).blocks
    # The windows are arguments: a 5-minute pre-window would NOT have caught the 10-02 fill.
    f5 = _flag(tmp_path, {"enabled": True, "pre_min": 5, "post_min": 15})
    assert not nf.verdict(FILL_1002, flag_path=f5).blocks


def test_only_a_literal_true_enables_and_a_bad_flag_reads_off(tmp_path) -> None:
    assert not nf.verdict(FILL_1002, flag_path=_flag(tmp_path, {"enabled": "yes"})).enabled
    v = nf.verdict(FILL_1002, flag_path=_flag(tmp_path, "{not json"))
    assert not v.enabled and "malformed" in v.why
    assert not nf.verdict(FILL_1002, flag_path=_flag(tmp_path, {"enabled": True,
                                                                 "pre_min": -1})).enabled


def test_a_calendar_gap_is_published_never_read_as_a_quiet_month() -> None:
    gaps = nf.uncovered_families(date(2026, 9, 1), date(2026, 10, 31))
    for fam in ("CPI", "PPI", "PCE", "GDP"):
        assert f"{fam}:2026-09" in gaps and f"{fam}:2026-10" in gaps
    assert "NFP:2026-10" not in gaps                      # rule-derived, first Friday
    v = nf.verdict(datetime(2026, 10, 14, 12, 30, tzinfo=UTC), flag_path=Path("/nonexistent"))
    assert not v.in_window and "UNMEASURED" in v.why and "CPI:2026-10" in v.uncovered


def test_an_enabled_fence_with_no_calendar_for_the_year_fails_open(tmp_path) -> None:
    f = _flag(tmp_path, {"enabled": True})
    v = nf.verdict(datetime(2027, 1, 8, 9, 0, tzinfo=UTC), flag_path=f)
    assert not v.calendar_ok and not v.blocks and v.uncovered == ("ALL:2027",)
    off = nf.verdict(datetime(2027, 1, 8, 9, 0, tzinfo=UTC), flag_path=tmp_path / "none")
    assert not off.blocks and "UNMEASURED" in off.why


def test_resting_entry_legs_skip_filled_windows_and_gone_orders() -> None:
    state = {"windows": {
        "london_am": {"orders": {"buy_stop": {"id": 11}, "sell_stop": {"id": 12}},
                      "position_id": None},
        "asia": {"orders": {"buy_stop": {"id": 21}}, "position_id": 900},
        "afternoon": {"orders": {"buy_stop": {"id": None}}, "position_id": None}}}
    got = nf.resting_entry_legs(state, open_ids={11, 12, 21}, filled={12: 77})
    assert got == [("london_am", "buy_stop", 11)]


def test_the_lane_is_wired_to_the_fence_on_placement_retry_and_resting_legs() -> None:
    src = (_DESK / "prop" / "e8_gold.py").read_text("utf-8")
    assert "from mt5desk import news_fence as _nf" in src
    assert "news = news_verdict(now)" in src and "_nf.verdict(now)" in src
    assert "news_why=(" in src                                 # the retry path
    assert "resting_entry_legs(state, open_ids, filled)" in src  # the resting-leg cancel
    assert src.count("else NEWS_SHADOW") >= 2                  # billed when OFF, both paths
    assert src.count("else NEWS_SHADOW") >= 3                  # ... and on re-sends


def test_missed_growth_publishes_both_sides_of_the_bill(tmp_path, monkeypatch) -> None:
    from research import missed_growth as mg
    j = tmp_path / "e8_gold_intents.jsonl"
    monkeypatch.setattr(mg, "E8_INTENTS", j)
    rep = tmp_path / "E8_GOLD.json"
    monkeypatch.setattr(mg, "E8_GOLD_REPORT", rep)
    assert mg.published_news_fence_lines()["verdict"] == mg.UNMEASURED      # absent journal
    j.write_text("", "utf-8")
    rep.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(),
                               "news_fence": {"calendar_ok": True, "error": None}}), "utf-8")
    assert mg.published_news_fence_lines()["verdict"] == mg.NOT_BINDING
    rows = [{"rail": "e8_news_fence", "status": "SHADOW_FENCE", "missed_growth_risk_usd": 250.0,
             "release": "2026-10-02 12:30Z NFP", "at": "2026-10-02T12:25:00+00:00"},
            {"rail": "e8_news_fence", "status": "RAIL_BLOCKED", "missed_growth_risk_usd": 300.0},
            {"rail": "e8_news_fence", "status": "RAIL_BLOCKED"},
            {"rail": "cross_account_opposite", "status": "RAIL_BLOCKED"}]
    j.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    out = mg.published_news_fence_lines()
    assert out["verdict"] == mg.UNMEASURED
    assert out["shadow"]["n"] == 1 and out["shadow"]["risk_usd"] == 250.0
    assert out["held"]["n"] == 2 and out["held"]["risk_usd"] == 300.0
    assert out["held"]["n_unpriced"] == 1
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"e8_news_fence": published_news_fence_lines()' in src


def test_liveness_check_goes_red_when_unwired_or_blind_and_is_in_the_law_gate(tmp_path) -> None:
    from scripts import check_news_fence_liveness as chk
    lane = tmp_path / "e8_gold.py"
    lane.write_text("# no fence here\n", "utf-8")
    out = chk.assess(today=date(2026, 10, 2), lane=lane, report=tmp_path / "none.json",
                     flag=tmp_path / "none")
    assert out["verdict"] == "RED" and any("UNWIRED" in r for r in out["red"])
    on = _flag(tmp_path, {"enabled": True})
    out = chk.assess(today=date(2026, 10, 2), report=tmp_path / "none.json", flag=on)
    assert out["verdict"] == "RED" and any(r.startswith("BLIND") for r in out["red"])
    off = chk.assess(today=date(2026, 10, 2), report=tmp_path / "none.json",
                     flag=tmp_path / "none")
    assert off["verdict"] == "UNMEASURED" and not off["red"]
    rep = tmp_path / "E8_GOLD.json"
    rep.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(), "status": "OK"}), "utf-8")
    out = chk.assess(today=date(2026, 10, 2), report=rep, flag=tmp_path / "none")
    assert any(r.startswith("SILENT") for r in out["red"])
    gate = (_ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_news_fence_liveness.py", ())' in gate


def test_gaps_cover_the_whole_month_and_nfp_holiday_moves() -> None:
    assert nf.uncovered_families(date(2026, 10, 1), date(2026, 10, 1)) == \
        nf.uncovered_families(date(2026, 10, 31), date(2026, 10, 31))
    from mt5desk.calendar_us import releases
    nfp = [r.when.date() for r in releases(date(2026, 7, 1), date(2026, 7, 31))
           if r.family == "NFP"]
    assert nfp == [date(2026, 7, 2)]                     # 07-03 is the observed holiday


def test_the_flag_reads_with_a_bom_and_bounds_the_windows(tmp_path) -> None:
    p = tmp_path / "f.json"
    p.write_bytes(b"\xef\xbb\xbf" + b'{"enabled": true, "pre_min": 20}')
    assert nf.read_flag(p)[:3] == (True, 20, 15)
    for bad in ('{"pre_min": 1e999}', '{"post_min": 1000000000000}', '{"pre_min": true}'):
        p.write_text(bad, "utf-8")
        assert nf.read_flag(p)[0] is False and "malformed" in nf.read_flag(p)[3]


def test_liveness_is_not_silent_red_on_a_no_bars_pass_but_is_red_on_an_error(tmp_path) -> None:
    from scripts import check_news_fence_liveness as chk
    rep = tmp_path / "E8_GOLD.json"
    now = datetime.now(tz=UTC).isoformat()
    rep.write_text(json.dumps({"at": now, "status": "NO_BARS"}), "utf-8")
    assert not chk.assess(report=rep, flag=tmp_path / "none")["red"]
    rep.write_text(json.dumps({"at": now, "status": "OK",
                               "news_fence": {"error": "boom"}}), "utf-8")
    assert any("FAILED OPEN" in r for r in chk.assess(report=rep, flag=tmp_path / "none")["red"])


def test_no_rows_from_a_blind_fence_is_unmeasured_and_named(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit v2 MUST (L1.28a): a blind or failed fence fails open and journals NOTHING, so a
    readable journal with no fence rows must not read NOT_BINDING."""
    from research import missed_growth as mg
    j = tmp_path / "e8_gold_intents.jsonl"
    rep = tmp_path / "E8_GOLD.json"
    monkeypatch.setattr(mg, "E8_INTENTS", j)
    monkeypatch.setattr(mg, "E8_GOLD_REPORT", rep)
    j.write_text("", "utf-8")
    rep.write_text(json.dumps({"news_fence": {"calendar_ok": False,
                                              "uncovered": ["CPI:2026-10"]}}), "utf-8")
    out = mg.published_news_fence_lines()
    assert out["verdict"] == mg.UNMEASURED and out["uncovered_last_pass"] == ["CPI:2026-10"]
    rep.write_text(json.dumps({"news_fence": {"calendar_ok": True, "error": "boom"}}), "utf-8")
    out = mg.published_news_fence_lines()
    assert out["verdict"] == mg.UNMEASURED and out["error"] == "boom"
    # A clean last pass, but the journal spans months the calendar cannot see.
    rep.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(),
                               "news_fence": {"calendar_ok": True}}), "utf-8")
    j.write_text(json.dumps({"rail": "cross_account_opposite", "status": "RAIL_BLOCKED",
                             "at": "2026-10-02T12:25:00+00:00"}), "utf-8")
    out = mg.published_news_fence_lines()
    assert out["verdict"] == mg.UNMEASURED and "CPI:2026-10" in out["uncovered_journal_span"]


def _retry_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, on: bool,
                legs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    sys.path.insert(0, str(_DESK / "tests"))
    import test_e8_gold_guard_and_open_risk as h
    from prop import e8_gold as g
    tmp_path.mkdir(parents=True, exist_ok=True)
    h._sandbox(monkeypatch, tmp_path)
    (tmp_path / "intents.json").write_text("", "utf-8")
    st = json.loads(g.STATE.read_text("utf-8"))
    st["windows"]["afternoon"] = {"placed_hour": 17.0, "position_id": None, "shadow": False,
                                  "orders": {}, "failed": legs}
    sent: list[str] = []

    class V(h._Venue):
        def place_stop(self, *a: object, **k: object) -> int:
            sent.append(str(a[1]))
            return 9000 + len(sent)
    doc: dict[str, object] = {"actions": []}
    why = "inside -15/+15 min of 2026-10-15 17:30Z NFP"
    g._retry_failed_legs(V(), st, doc, hour=17.5, now=datetime(2026, 10, 15, 14, 30, tzinfo=UTC),
                         open_orders=[], orders_ok=True, filled={}, xau_positions=[],
                         positions_ok=True, stood_down=False, armed=True, hist_rows=[],
                         history_ok=True, instrument_id=6102, mt5=h._MT5(),
                         news_why=f"the news fence holds ({why})" if on else None,
                         news_shadow_why=None if on else why)
    rows = [json.loads(x) for x in (tmp_path / "intents.json").read_text("utf-8").splitlines()
            if x.strip()]
    return [r for r in rows if r.get("rail") == "e8_news_fence"] + [{"sent": sent}]


_LEG = {"price": 4310.0, "sl": 4295.0, "tp": 4340.0, "lot": 0.5, "risk_usd": 750.0,
        "attempts": 1, "first_at": "2026-10-15T14:20:00+00:00", "why": "timeout"}
_LATE = {**_LEG, "price": 4290.0}                   # a buy stop already through: abandoned


def test_on_and_off_bill_the_same_re_sent_legs(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavioural (v4): ON holds and bills, OFF sends and shadow-bills -- the SAME leg set, a
    leg retry_decisions abandons (price through) is billed by neither."""
    legs = {"buy_stop": dict(_LEG), "sell_stop": {**_LATE, "price": 4310.0}}
    on = _retry_pass(tmp_path / "on", monkeypatch, on=True, legs={"buy_stop": dict(_LEG)})
    off = _retry_pass(tmp_path / "off", monkeypatch, on=False, legs={"buy_stop": dict(_LEG)})
    assert [r["status"] for r in on[:-1]] == ["RAIL_BLOCKED"]
    assert [r["status"] for r in off[:-1]] == ["SHADOW_FENCE"]
    assert on[-1]["sent"] == []                                   # held
    assert [(r["window"], r["side"]) for r in on[:-1]] == \
        [(r["window"], r["side"]) for r in off[:-1]]
    gone = _retry_pass(tmp_path / "gone", monkeypatch, on=False, legs=legs)
    assert [r["side"] for r in gone[:-1]] == ["buy_stop"]         # the through leg: no bill


def _clean_report(rep: Path, **over: object) -> None:
    body: dict[str, object] = {"at": datetime.now(tz=UTC).isoformat(),
                               "news_fence": {"calendar_ok": True, "error": None}}
    body.update(over)
    rep.write_text(json.dumps(body), "utf-8")


@pytest.mark.parametrize("case", ["undated_rows", "empty_verdict", "stale_verdict",
                                  "undated_report"])
def test_v3_blind_states_read_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                         case: str) -> None:
    """Audit v3 MUST: three (four) blind states that read NOT_BINDING now read UNMEASURED."""
    from research import missed_growth as mg
    j = tmp_path / "e8_gold_intents.jsonl"
    rep = tmp_path / "E8_GOLD.json"
    monkeypatch.setattr(mg, "E8_INTENTS", j)
    monkeypatch.setattr(mg, "E8_GOLD_REPORT", rep)
    j.write_text("", "utf-8")
    _clean_report(rep)
    assert mg.published_news_fence_lines()["verdict"] == mg.NOT_BINDING      # the clean case
    if case == "undated_rows":
        j.write_text("\n".join(json.dumps(r) for r in (
            {"rail": "cross_account_opposite", "status": "RAIL_BLOCKED"},
            {"rail": "x", "at": "2026-10"})), "utf-8")
        assert mg.published_news_fence_lines()["undated_rows"] == 2
    elif case == "empty_verdict":
        _clean_report(rep, news_fence={})
        assert mg.published_news_fence_lines()["calendar_ok"] is None
    elif case == "stale_verdict":
        _clean_report(rep, at="2025-10-02T12:00:00+00:00")
        assert mg.published_news_fence_lines()["stale_verdict_age_h"] > 24
    else:
        rep.write_text(json.dumps({"news_fence": {"calendar_ok": True}}), "utf-8")
        assert mg.published_news_fence_lines()["stale_verdict_age_h"] is None
    assert mg.published_news_fence_lines()["verdict"] == mg.UNMEASURED


def test_a_leg_held_by_the_fence_is_not_billed_again_when_its_window_expires(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    held = _retry_pass(tmp_path / "held", monkeypatch, on=True, legs={"buy_stop": dict(_LEG)})
    assert [r["status"] for r in held[:-1]] == ["RAIL_BLOCKED"]
    import test_e8_gold_guard_and_open_risk as h
    from prop import e8_gold as g
    st = json.loads(g.STATE.read_text("utf-8")) if g.STATE.exists() else {}
    leg = {**_LEG, "news_held": "2026-10-15T14:30:00+00:00"}
    st.setdefault("windows", {})["afternoon"] = {"placed_hour": 17.0, "position_id": None,
                                                 "shadow": False, "orders": {},
                                                 "failed": {"buy_stop": leg}}
    doc: dict[str, object] = {"actions": []}
    # Past the cancel hour: retry_decisions abandons the leg.
    g._retry_failed_legs(h._Venue(), st, doc, hour=23.0,
                         now=datetime(2026, 10, 15, 20, 0, tzinfo=UTC), open_orders=[],
                         orders_ok=True, filled={}, xau_positions=[], positions_ok=True,
                         stood_down=False, armed=True, hist_rows=[], history_ok=True,
                         instrument_id=6102, mt5=h._MT5())
    rows = [json.loads(x) for x in (tmp_path / "held" / "intents.json").read_text(
        "utf-8").splitlines() if x.strip()]
    assert not [r for r in rows if r.get("rail") in ("gold_retry_abandoned", "gold_late_send")]
    assert "buy_stop" in st["windows"]["afternoon"]["abandoned"]


def test_a_report_that_is_not_an_object_is_no_verdict(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from research import missed_growth as mg
    j = tmp_path / "e8_gold_intents.jsonl"
    rep = tmp_path / "E8_GOLD.json"
    monkeypatch.setattr(mg, "E8_INTENTS", j)
    monkeypatch.setattr(mg, "E8_GOLD_REPORT", rep)
    j.write_text("", "utf-8")
    rep.write_text("[1, 2, 3]", "utf-8")
    out = mg.published_news_fence_lines()
    assert out["verdict"] == mg.UNMEASURED and "why_verdict" in out
