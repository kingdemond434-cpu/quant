"""Order-sensitive decay verdicts: pre-registered splits, UNMEASURED by name, report-only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decay_verdicts as dv  # noqa: E402

from libs.research import order_sensitive_decay as osd  # noqa: E402

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
T0 = datetime(2026, 9, 1, tzinfo=UTC)


def _ledger_rows(rs: list[float], phase: str | None = "forward",
                 start: datetime = T0) -> list[dict]:
    rows = [{"entry_time": str(start + timedelta(days=i)),
             "exit_time": str(start + timedelta(days=i)), "r_multiple": r}
            for i, r in enumerate(rs)]
    if phase is not None:
        for r in rows:
            r["phase"] = phase
    return rows


def _decaying(n: int = 40) -> list[float]:
    half = n // 2
    return [1.0 + 0.1 * (i % 3) for i in range(half)] + [-1.0 - 0.1 * (i % 3)
                                                         for i in range(n - half)]


def test_split_rule_is_equal_count_by_trade_index_and_frozen() -> None:
    assert dv.SUB_PERIODS == 4 and dv.MIN_TRADES == 20
    assert dv.splits(20) == [(0, 5), (5, 10), (10, 15), (15, 20)]
    cuts = dv.splits(23)
    assert cuts[0][0] == 0 and cuts[-1][1] == 23
    assert all(b > a for a, b in cuts) and max(b - a for a, b in cuts) - min(
        b - a for a, b in cuts) <= 1
    # the split is a function of n alone: the same n gives the same cuts whatever the values
    assert dv.verdict_for(_decaying(40))["splits"] == dv.verdict_for([0.1] * 40)["splits"]


def test_too_few_trades_is_unmeasured_by_name() -> None:
    v = dv.verdict_for([1.0] * 19)
    assert v["verdict"] == dv.UNMEASURED_TOO_FEW
    assert v["p_values"] is None and v["n"] == 19 and "20" in v["why"]


def test_decaying_record_is_called_and_flat_record_is_not() -> None:
    v = dv.verdict_for(_decaying(40))
    assert v["verdict"] == osd.DECAYING
    assert len(v["p_values"]) == 4 and all(0.0 <= p <= 1.0 for p in v["p_values"])
    assert v["error_rate_late"] > v["error_rate_early"]
    rev = dv.verdict_for(list(reversed(_decaying(40))))
    assert rev["verdict"] == osd.STRENGTHENING, "order is the whole point: reversed flips it"
    flat = dv.verdict_for([0.5, -0.4, 0.6, -0.3] * 10)
    assert flat["verdict"] == osd.STABLE


def test_one_sided_p_is_a_probability_and_handles_zero_variance() -> None:
    assert dv.one_sided_p([1.0, 1.0, 1.0]) == 0.0
    assert dv.one_sided_p([-1.0, -1.0]) == 1.0
    assert dv.one_sided_p([0.0, 0.0]) == 0.5
    assert 0.0 < dv.one_sided_p([0.5, -0.2, 0.3, 0.1]) < 0.5


def _tree(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "EURUSD.asia": {"status": "ACTIVE", "n": 40, "sleeve_id": "a",
                        "forward_start": T0.isoformat(), "broker_offset_h": 0.0},
        "GBPUSD.asia": {"status": "ACTIVE", "n": 5, "forward_start": T0.isoformat()},
        "USDJPY.asia#rr=1.5": {"status": "ACTIVE", "n": 30},
        "AUDUSD.asia": {"status": "KILL", "n": 30},
    }), "utf-8")
    hist = _ledger_rows([5.0] * 30, phase="historical", start=T0 - timedelta(days=60))
    (shadow / "ledger_EURUSD_asia.json").write_text(
        json.dumps(hist + _ledger_rows(_decaying(40))), "utf-8")
    (shadow / "ledger_GBPUSD_asia.json").write_text(json.dumps(_ledger_rows([1.0] * 5)), "utf-8")
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "eurusd_live_sleeve", "status": "LIVE"},
        {"name": "old_one", "status": "RETIRED"}]}), "utf-8")
    live = tmp_path / "live_ledger.jsonl"
    rows = [{"sleeve": "eurusd_live_sleeve", "r_multiple": r,
             "time": (T0 + timedelta(hours=i)).isoformat()} for i, r in enumerate(_decaying(24))]
    rows.append({"sleeve": "eurusd_live_sleeve", "r_multiple": 0.0, "r_unreconstructible": True,
                 "time": T0.isoformat()})
    live.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return shadow, sleeves, live, tmp_path / "out.json"


def test_build_judges_live_and_forward_clocks_and_names_every_gap(tmp_path: Path) -> None:
    shadow, sleeves, live, out = _tree(tmp_path)
    doc = dv.build(now=NOW, shadow=shadow, sleeves_file=sleeves, live_ledger=live,
                   ledger_dirs=(shadow,))
    rows = doc["sleeves"]
    assert doc["generated_utc"] == NOW.isoformat(timespec="seconds")
    # forward-phase only: the 30 historical +5R rows never enter the decay record
    eur = rows["clock:EURUSD.asia"]
    assert eur["basis"] == "shadow_forward" and eur["n"] == 40 and eur["verdict"] == osd.DECAYING
    assert eur["splits"] == [[0, 10], [10, 20], [20, 30], [30, 40]]
    assert rows["clock:GBPUSD.asia"]["verdict"] == dv.UNMEASURED_TOO_FEW
    var = rows["clock:USDJPY.asia#rr=1.5"]
    assert var["verdict"] == dv.UNMEASURED_NO_LEDGER
    assert "clock:AUDUSD.asia" not in rows and doc["sources"]["forward_clocks"][
        "dead_clocks_skipped"] == 1
    lv = rows["live:eurusd_live_sleeve"]
    assert lv["basis"] == "live_ledger" and lv["n"] == 24, "unreconstructible R is skipped"
    assert lv["verdict"] == osd.DECAYING
    assert "live:old_one" not in rows
    assert doc["sizing_hook"]["status"] == "NOT_WIRED"
    assert doc["sizing_hook"]["owner"] == "Max-growth thread"
    assert set(doc["companions"]) == {"decline_detector", "capacity_frontier"}
    dv.write(doc, out)
    got = dv.decay_input("EURUSD.asia", out)
    assert got["demote_input"] is True and got["strengthen_input"] is False
    assert dv.decay_input("eurusd_live_sleeve", out)["basis"] == "live_ledger"
    assert dv.decay_input("GBPUSD.asia", out)["demote_input"] is False


def test_absent_sources_are_unmeasured_never_empty(tmp_path: Path) -> None:
    doc = dv.build(now=NOW, shadow=tmp_path / "nope", sleeves_file=tmp_path / "nope.json",
                   ledger_dirs=(tmp_path,))
    assert doc["sources"]["roster"]["status"] == "UNMEASURED"
    assert len(doc["sources"]["forward_clocks"]["lanes_absent"]) == len(dv.LANE_FILES)
    assert dv.decay_input("anything", tmp_path / "absent.json")["verdict"] == "UNMEASURED"


def test_unreadable_live_ledger_is_named_per_sleeve(tmp_path: Path) -> None:
    shadow, sleeves, _live, _out = _tree(tmp_path)
    doc = dv.build(now=NOW, shadow=shadow, sleeves_file=sleeves,
                   live_ledger=tmp_path / "missing.jsonl", ledger_dirs=(shadow,))
    assert doc["sleeves"]["live:eurusd_live_sleeve"]["verdict"] == dv.UNMEASURED_NO_SOURCE
    assert doc["sources"]["live_ledger"]["status"] == "UNMEASURED"


def test_the_leg_is_registered_everywhere_legs_are_declared() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("decay_verdicts"' in src and '"research/decay_verdicts.py"' in src
    from libs.ops import capability_graph as cg
    from libs.research import layers
    assert layers.LEG_LAYER["decay_verdicts"] == "portfolio"
    assert any(n.name == "decay_verdicts" for n in cg.NODES)


def test_a_shared_legacy_ledger_is_a_named_gap_and_each_clock_reads_its_own(
        tmp_path: Path) -> None:
    """Fails on the symbol/family/window resolution: XAUUSD.asia read the shared file."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "XAUUSD.asia": {"status": "ACTIVE", "forward_start": T0.isoformat()},
        "XAUUSD.asia#rr=1.5": {"status": "ACTIVE", "forward_start": T0.isoformat()},
        "XAUUSD.asia#rr=2.5": {"status": "KILL"}}), "utf-8")
    (shadow / "ledger_XAUUSD_asia.json").write_text(json.dumps(_ledger_rows(_decaying(40))),
                                                    "utf-8")
    (shadow / "ledger_XAUUSD_asia#rr=1_5.json").write_text(
        json.dumps(_ledger_rows([0.5, -0.4, 0.6, -0.3] * 10)), "utf-8")
    doc = dv.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "none.json",
                   ledger_dirs=(shadow,))
    base = doc["sleeves"]["clock:XAUUSD.asia"]
    assert base["verdict"] == dv.UNMEASURED_SHARED_LEDGER and base["n"] is None
    assert "shared" in base["why"]
    own = doc["sleeves"]["clock:XAUUSD.asia#rr=1.5"]
    assert own["verdict"] == osd.STABLE and own["n"] == 40
    assert own["ledger"].endswith("ledger_XAUUSD_asia#rr=1_5.json")
    assert doc["sources"]["forward_clocks"]["shared_legacy_ledgers"] == 1
    # the base clock's own file, once written, is its series
    (shadow / "ledger_XAUUSD_asia#own.json").write_text(
        json.dumps(_ledger_rows(_decaying(40))), "utf-8")
    doc = dv.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "none.json",
                   ledger_dirs=(shadow,))
    assert doc["sleeves"]["clock:XAUUSD.asia"]["verdict"] == osd.DECAYING


def _one_clock(tmp_path: Path, state: dict, ledgers: dict[str, list[dict]]) -> dict:
    shadow = tmp_path / "shadow"
    shadow.mkdir(exist_ok=True)
    (shadow / "shadow_state.json").write_text(json.dumps(state), "utf-8")
    for name, rows in ledgers.items():
        (shadow / name).write_text(json.dumps(rows), "utf-8")
    return dv.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "none.json",
                    live_ledger=tmp_path / "none.jsonl", ledger_dirs=(shadow,))["sleeves"]


FS = datetime(2026, 10, 1, tzinfo=UTC)


def test_audit_probe_a_variants_forward_rows_never_judge_the_base(tmp_path: Path) -> None:
    """The audit's probe: base XAUUSD.asia (forward_start 10-01) was judged DECAYING n=40 on its
    variant's 40 'forward' rows, all of which predate the base's own forward_start."""
    variant_rows = _ledger_rows(_decaying(40), start=FS - timedelta(days=45))
    rows = _one_clock(tmp_path, {
        "XAUUSD.asia": {"status": "ACTIVE", "forward_start": FS.isoformat(),
                        "broker_offset_h": 3.0},
        "XAUUSD.asia#rr=2.0": {"status": "ACTIVE",
                               "forward_start": (FS - timedelta(days=50)).isoformat()},
    }, {"ledger_XAUUSD_asia.json": variant_rows})
    base = rows["clock:XAUUSD.asia"]
    assert base["verdict"] == dv.UNMEASURED_SHARED_LEDGER and base["n"] is None
    assert "XAUUSD.asia#rr=2.0" in base["why"]
    # the variant has no own file yet, and the cell's legacy file is not its series either
    assert rows["clock:XAUUSD.asia#rr=2.0"]["verdict"] == dv.UNMEASURED_SHARED_LEDGER


def test_a_killed_co_tenant_still_makes_the_file_shared(tmp_path: Path) -> None:
    rows = _one_clock(tmp_path, {
        "EURUSD.asia": {"status": "ACTIVE", "forward_start": T0.isoformat()},
        "EURUSD.asia@M5": {"status": "KILL"},
    }, {"ledger_EURUSD_asia.json": _ledger_rows(_decaying(40))})
    assert rows["clock:EURUSD.asia"]["verdict"] == dv.UNMEASURED_SHARED_LEDGER
    assert "clock:EURUSD.asia@M5" not in rows


def test_rows_tagged_forward_before_the_clocks_own_start_are_dropped(tmp_path: Path) -> None:
    """Even an unshared file: the phase tag is never trusted over the clock's own boundary."""
    early = _ledger_rows(_decaying(40), start=FS - timedelta(days=45))
    rows = _one_clock(tmp_path, {"XAUUSD.asia": {"status": "ACTIVE",
                                                 "forward_start": FS.isoformat()}},
                      {"ledger_XAUUSD_asia.json": early})
    r = rows["clock:XAUUSD.asia"]
    assert r["verdict"] == dv.UNMEASURED_TOO_FEW and r["n"] == 0
    assert r["row_filter"]["before_own_forward_start"] == 40


def test_unphased_ledger_is_cut_at_the_boundary_never_judged_whole(tmp_path: Path) -> None:
    old = _ledger_rows([5.0] * 30, phase=None, start=FS - timedelta(days=40))
    new = _ledger_rows(_decaying(40), phase=None, start=FS)
    rows = _one_clock(tmp_path, {"XAUUSD.asia": {"status": "ACTIVE",
                                                 "forward_start": FS.isoformat()}},
                      {"ledger_XAUUSD_asia.json": old + new})
    r = rows["clock:XAUUSD.asia"]
    assert r["basis"] == "shadow_unphased" and r["n"] == 40 and r["verdict"] == osd.DECAYING
    assert r["row_filter"]["before_own_forward_start"] == 30


def test_the_boundary_adds_the_broker_offset(tmp_path: Path) -> None:
    """Bar stamps are on the broker clock; forward_start is UTC. A row 2h after forward_start
    on the bar clock is still BEFORE the boundary at a +3h broker."""
    hourly = [{"entry_time": str(FS + timedelta(hours=h)), "r_multiple": 1.0,
               "phase": "forward"} for h in range(24)]
    rows = _one_clock(tmp_path, {"XAUUSD.asia": {"status": "ACTIVE",
                                                 "forward_start": FS.isoformat(),
                                                 "broker_offset_h": 3.0}},
                      {"ledger_XAUUSD_asia.json": hourly})
    r = rows["clock:XAUUSD.asia"]
    assert r["n"] == 21 and r["row_filter"]["before_own_forward_start"] == 3


def test_no_forward_start_is_unmeasured_by_name(tmp_path: Path) -> None:
    rows = _one_clock(tmp_path, {"XAUUSD.asia": {"status": "ACTIVE"}},
                      {"ledger_XAUUSD_asia.json": _ledger_rows(_decaying(40))})
    assert rows["clock:XAUUSD.asia"]["verdict"] == dv.UNMEASURED_NO_FORWARD_START


def test_ledger_name_is_shadow_forwards_legacy_naming() -> None:
    assert dv.ledger_name("XAUUSD.asia") == "ledger_XAUUSD_asia.json"
    assert dv.ledger_name("XAUUSD.asia@M5#rr=2.0.SHORT") == "ledger_XAUUSD_asia.json"
    assert dv.ledger_name("EURZAR.overnight_gap_decay.ny#k=1") == \
        "ledger_EURZAR_overnight_gap_decay_ny.json"
    assert dv.ledger_name("XAUUSD.session_range_breakout.asia") == "ledger_XAUUSD_asia.json"
    assert dv.ledger_name("garbage") is None


def test_scalp_rows_stamped_opened_at_are_judged_not_dropped(tmp_path: Path) -> None:
    """Re-audit of 9dd343f69: scalp ledgers stamp `opened_at`; every LIVE scalp clock read n=0."""
    rows = [{"opened_at": str(FS + timedelta(hours=i)), "r": 0.0, "r_multiple": r,
             "phase": "forward"} for i, r in enumerate(_decaying(40))]
    early = [{"opened_at": str(FS - timedelta(days=3, hours=i)), "r_multiple": 5.0}
             for i in range(10)]
    got = _one_clock(tmp_path, {"XAUUSD.scalp_vwap.asia": {
        "status": "PROMOTION_CANDIDATE", "forward_start": FS.isoformat()}},
        {"ledger_XAUUSD_scalp_vwap_asia.json": early + rows})
    r = got["clock:XAUUSD.scalp_vwap.asia"]
    assert r["n"] == 40 and r["verdict"] == osd.DECAYING
    assert r["row_filter"]["before_own_forward_start"] == 10


def test_rows_with_no_entry_stamp_at_all_are_named(tmp_path: Path) -> None:
    rows = [{"exit_time": str(FS + timedelta(days=i)), "r_multiple": 1.0} for i in range(30)]
    got = _one_clock(tmp_path, {"XAUUSD.asia": {"status": "ACTIVE",
                                                "forward_start": FS.isoformat()}},
                     {"ledger_XAUUSD_asia.json": rows})
    assert got["clock:XAUUSD.asia"]["verdict"] == dv.UNMEASURED_NO_ENTRY_TIME


def test_retired_clock_tombstones_are_co_tenants(tmp_path: Path) -> None:
    """An evacuated clock's key survives only as a tombstone; its pass still wrote the file."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "EURUSD.asia": {"status": "ACTIVE", "forward_start": T0.isoformat()},
        "retired_clocks": {"EURUSD.asia#rr=3.0": {"retired_at": "2026-09-30"}}}), "utf-8")
    (shadow / "ledger_EURUSD_asia.json").write_text(json.dumps(_ledger_rows(_decaying(40))),
                                                    "utf-8")
    assert "EURUSD.asia#rr=3.0" in dv.all_clock_keys(shadow)
    doc = dv.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "none.json",
                   live_ledger=tmp_path / "none.jsonl", ledger_dirs=(shadow,))
    assert doc["sleeves"]["clock:EURUSD.asia"]["verdict"] == dv.UNMEASURED_SHARED_LEDGER
