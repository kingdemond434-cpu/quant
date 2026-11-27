"""Per-producer funnel status and floors; the conversion fixes of the 2026-11-25 producer triage.

  * producer_floors: OK / BELOW_FLOOR / STALE / DEAD on every funnel producer row; breadth,
    depth and conversion floors ratchet UP only and no writer can lower one.
  * family_spec: a REQUIRED keyword is an argument (calendar_month, mass_screen_*), and a recipe
    that omits one is a named refusal, never a testable cell that would TypeError.
  * miner_candidate_compiler: a bars-file stem (`EURUSD_H1`) resolves to its symbol; the
    seasonality seat's own bullish/bearish are the two directions.
  * check_producer_yield: a proposer's seat is read from its module's SOURCE constant.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_spec as FS  # noqa: E402
from research import funnel as fn  # noqa: E402
from research import producer_floors as PF  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def _row(name: str, *, raw=100, testable=40, breadth=20, depth=4.0, conv=0.4) -> dict:
    return {"producer": name,
            "stages": {"RAW": raw, "ROWS": 100, "TESTABLE": testable},
            "transitions": [{"transition": "ROWS->TESTABLE", "rate": conv}],
            "depth": {"testable_cells_per_family": depth,
                      "breadth_units": {"TESTABLE": breadth}}}


def test_status_is_one_of_four_and_floors_ratchet_up_only() -> None:
    rows = [_row("alpha"), _row("beta", raw=0, testable=0, breadth=0, depth=fn.UNMEASURED,
                                conv=fn.UNMEASURED)]
    floors = PF.annotate(rows, {}, {}, NOW, ratchet=fn.ratchet_one)
    a, b = rows
    assert a["status"] == PF.OK and b["status"] == PF.DEAD
    assert floors["alpha"]["breadth"]["floor"] == 18          # 0.9 x 20, integer
    assert floors["alpha"]["conversion"]["floor"] == 0.36
    # next pass: alpha collapses -> BELOW_FLOOR on every metric, floors unchanged
    rows2 = [_row("alpha", breadth=5, depth=1.0, conv=0.05)]
    floors2 = PF.annotate(rows2, floors, {}, NOW, ratchet=fn.ratchet_one)
    assert rows2[0]["status"] == PF.BELOW_FLOOR
    assert rows2[0]["violated"] == ["breadth", "conversion", "depth"]
    assert floors2["alpha"]["breadth"]["floor"] == 18
    assert floors2["beta"] == floors["beta"]                   # absent producer keeps its floors
    # and a better pass lifts them, no ceiling
    rows3 = [_row("alpha", breadth=1000, depth=40.0, conv=0.9)]
    floors3 = PF.annotate(rows3, floors2, {}, NOW, ratchet=fn.ratchet_one)
    assert floors3["alpha"]["breadth"]["floor"] == 900 and rows3[0]["status"] == PF.OK


def test_the_heartbeat_decides_stale_and_dead() -> None:
    rows = [_row("alpha"), _row("gamma")]
    PF.annotate(rows, {}, {"alpha": {"status": "TIMEOUT", "why": "cap"},
                           "gamma": {"status": "DEAD", "why": "no run"}}, NOW,
                ratchet=fn.ratchet_one)
    assert rows[0]["status"] == PF.STALE and "TIMEOUT" in rows[0]["status_why"]
    assert rows[1]["status"] == PF.DEAD


def test_merge_up_never_lowers_a_producer_floor() -> None:
    disk = {"alpha": {"breadth": {"floor": 50, "raised_at": "x"}}}
    new = {"alpha": {"breadth": {"floor": 10, "raised_at": "y"},
                     "depth": {"floor": 2.0, "raised_at": "y"}}}
    got = PF.merge_up(disk, new)
    assert got["alpha"]["breadth"]["floor"] == 50 and got["alpha"]["depth"]["floor"] == 2.0
    merged = fn.merge_up({"stages": {}, "transitions": {}, "producers": disk},
                         {"stages": {}, "transitions": {}, "producers": new})
    assert merged["producers"]["alpha"]["breadth"]["floor"] == 50


def test_read_heartbeat_keeps_legs_and_seats(tmp_path: Path) -> None:
    p = tmp_path / "PRODUCER_HEARTBEAT.json"
    p.write_text(json.dumps({"producers": [
        {"producer": "a", "kind": "leg", "status": "OK"},
        {"producer": "b", "kind": "seat", "status": "STALE"},
        {"producer": "MT5-X", "kind": "box_task", "status": "DEAD"}]}), encoding="utf-8")
    got = PF.read_heartbeat(p)
    assert set(got) == {"a", "b"}
    assert PF.read_heartbeat(tmp_path / "absent.json") == {}


def test_the_funnel_wires_the_producer_floors() -> None:
    src = (_DESK / "research" / "funnel.py").read_text("utf-8")
    assert 'floors_new["producers"] = PF.annotate(' in src
    assert '"producer_status": PF.summary(rows_p)' in src


# ------------------------------------------------------------------------- family_spec
def test_a_required_keyword_is_an_argument() -> None:
    sig = FS.signature("calendar_month")
    if sig is None:                       # the families cannot import on this host
        return
    assert "active_month" in sig and "side_bias" in sig
    got = FS.to_executable("calendar_month", {"active_month": 9, "side_bias": -1})
    assert FS.is_testable(got["status"]), got
    assert got["params"] == {"active_month": 9, "side_bias": -1}


def test_a_recipe_missing_a_required_keyword_is_a_named_refusal() -> None:
    if FS.signature("calendar_month") is None:
        return
    got = FS.to_executable("calendar_month", {"active_month": 9})
    assert got["status"] == FS.DEFAULTS_ONLY and "requires ['side_bias']" in got["reason"]
    # a session variant alone used to read testable and would TypeError at the call
    got = FS.to_executable("calendar_month", {"session": "asia"})
    assert not FS.is_testable(got["status"])


def test_the_replay_supplies_symbol() -> None:
    sig = FS.signature("cross_sectional_class_ltr")
    if sig is None:
        return
    assert "symbol" not in sig


# ------------------------------------------------------------------------- the compiler
def test_a_bars_file_stem_resolves_and_bearish_is_a_direction() -> None:
    import miner_candidate_compiler as M
    uni = {"EURUSD", "3M"}
    assert M.resolve_symbols({"symbols": ["EURUSD_H1"]}, uni) == ["EURUSD"]
    assert M.resolve_symbols({"symbol": "3m_h1"}, uni) == ["3M"]
    assert M.resolve_symbols({"symbols": ["EURUSD"]}, uni) == ["EURUSD"]
    row = {"source": "seasonality", "type": "historical_pattern", "symbol": "EURUSD_H1",
           "month": 9, "direction": "bearish", "symbols": ["EURUSD_H1"]}
    cands, why = M.compile_row("seasonality", row, uni)
    assert why == "STRUCTURED_CALENDAR"
    assert cands and cands[0]["family"] == "calendar_month"
    assert cands[0]["params"] == {"active_month": 9, "side_bias": -1}
    up = dict(row, direction="bullish")
    assert M.compile_row("seasonality", up, uni)[0][0]["params"]["side_bias"] == 1


# ------------------------------------------------------------------------- the census
def test_a_proposer_seat_is_read_from_its_source_constant(tmp_path: Path) -> None:
    import check_producer_yield as cpy
    (tmp_path / "plumbing_miner.py").write_text('SOURCE = "plumbing"\n', encoding="utf-8")
    (tmp_path / "same.py").write_text('SOURCE = "same"\n', encoding="utf-8")
    (tmp_path / "none.py").write_text("x = 1\n", encoding="utf-8")
    got = cpy.declared_seats(["plumbing_miner", "same", "none", "absent"], research=tmp_path)
    assert got == {"plumbing_miner": "plumbing"}
    live = cpy.declared_seats(["plumbing_miner", "microstructure_miner", "style_premia_sweep",
                               "tail_alpha_search", "weak_signal_compiler"])
    assert live == {"plumbing_miner": "plumbing", "microstructure_miner": "microstructure",
                    "style_premia_sweep": "style_premia", "tail_alpha_search": "tail_alpha",
                    "weak_signal_compiler": "weak_signal_ensemble"}


# ------------------------------------------------------------------------- the soft deadline
def test_a_ledger_read_stops_at_the_soft_deadline(tmp_path: Path, monkeypatch) -> None:
    import time

    from research import axis_registry as ar
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text("".join(json.dumps({"cell": f"x{i}"}) + "\n" for i in range(12_000)),
                 encoding="utf-8")
    note: dict[str, str] = {}
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    monkeypatch.delenv("QUANT_LEG_DEADLINE_TS", raising=False)
    assert len(ar._read_jsonl(p, note)) == 12_000 and note[p.name] == "READ"
    monkeypatch.setenv("QUANT_LEG_DEADLINE_TS", str(time.time() + 10))   # inside the margin
    note = {}
    rows = ar._read_jsonl(p, note)
    assert len(rows) == 5_000 and note[p.name] == "DEADLINE_TRUNCATED(5000)"


def test_a_producer_sharing_a_seat_is_counted_by_its_own_files(tmp_path: Path,
                                                               monkeypatch) -> None:
    import check_producer_yield as cpy
    world = tmp_path / "desks" / "mt5" / "data" / "intelligence" / "world"
    world.mkdir(parents=True)
    (world / "discoveries_deepforest_1.json").write_text("[\n{}\n]\n", encoding="utf-8")
    (world / "discoveries_crawler_1.json").write_text("[\n{}\n{}\n{}\n]\n", encoding="utf-8")
    monkeypatch.setattr(cpy, "DESK", tmp_path / "desks" / "mt5")
    monkeypatch.setattr(cpy, "ROOT", tmp_path)
    assert cpy._prefixed_output(3.0, "world", "discoveries_deepforest_") == 3
    assert cpy._prefixed_output(3.0, "world", "discoveries_nothing_") is None
    assert cpy.SHARED_SEAT_PREFIXES["deep_forest_miner"] == ("world", "discoveries_deepforest_")


def test_local_convert_output_rides_the_box_state_sync() -> None:
    sync = (_DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/data/hypotheses/local_candidates.json"' in sync
