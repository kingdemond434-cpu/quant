"""One forward ledger per clock key; a legacy file several keys shared is a named gap.

Every test here fails on the pre-2026-10-14 code: the module did not exist, and the readers below
read a cell's shared `ledger_<sym>_<family>_<window>.json` as each variant's own series.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forward_ledger as fl  # noqa: E402

KEYS = ["XAUUSD.asia", "XAUUSD.asia#rr=1.5", "XAUUSD.asia#rr=2.5", "XAUUSD.asia@M5#rr=1.5",
        "XAUUSD.asia.SHORT", "CHFDKK.overnight_gap_decay.asia",
        "CHFNOK.carry.asia#input_symbol=CHFNOK", "CHFNOK.carry.asia#input_symbol=GBPJPY",
        "EURUSD.london"]


def _rows(r: float, n: int = 3) -> list[dict]:
    return [{"entry_time": f"2026-09-{10 + i} 01:00:00", "r_multiple": r, "phase": "forward"}
            for i in range(n)]


def test_every_key_gets_its_own_name_and_a_plain_key_keeps_its_legacy_name() -> None:
    names = [fl.per_key_name(k) for k in KEYS]
    assert len(set(names)) == len(KEYS), "two clock keys may never share a ledger name"
    assert fl.per_key_name("XAUUSD.asia") == "ledger_XAUUSD_asia.json"
    assert fl.per_key_name("CHFDKK.overnight_gap_decay.asia") == (
        "ledger_CHFDKK_overnight_gap_decay_asia.json")
    # the convention forward_reconcile / decay_monitor already resolve by
    assert fl.per_key_name("XAUUSD.asia#rr=1.5") == "ledger_XAUUSD_asia#rr=1_5.json"
    # the legacy name drops every variant tail -- the defect, measured
    assert {fl.legacy_name(k) for k in KEYS[:5]} == {"ledger_XAUUSD_asia.json"}


def test_long_keys_are_bounded_and_never_meet_on_truncation() -> None:
    a = "AUDNZD.cross_asset_residual.asia@M5#" + "x" * 300 + "_a"
    b = "AUDNZD.cross_asset_residual.asia@M5#" + "x" * 300 + "_b"
    na, nb = fl.per_key_name(a), fl.per_key_name(b)
    assert len(na) <= fl.NAME_MAX and len(nb) <= fl.NAME_MAX and na != nb
    assert fl.per_key_name(a) == na, "deterministic"


def test_collisions_and_the_registry_is_append_only(tmp_path: Path) -> None:
    groups = fl.collisions(KEYS)
    assert set(groups) == {"ledger_XAUUSD_asia.json", "ledger_CHFNOK_carry_asia.json"}
    assert len(groups["ledger_XAUUSD_asia.json"]) == 5
    fl.freeze_collisions(KEYS, tmp_path)
    # a later pass that no longer sees the variants must not unfreeze the file
    files = fl.freeze_collisions(["XAUUSD.asia"], tmp_path)
    assert "ledger_XAUUSD_asia.json" in files
    assert len(files["ledger_XAUUSD_asia.json"]["members"]) == 5
    files = fl.freeze_collisions(["XAUUSD.asia", "XAUUSD.asia#rr=9"], tmp_path)
    assert "XAUUSD.asia#rr=9" in files["ledger_XAUUSD_asia.json"]["members"]


def test_writer_never_targets_a_frozen_legacy_file(tmp_path: Path) -> None:
    shared = fl.freeze_collisions(KEYS, tmp_path)
    for k in KEYS:
        assert fl.writer_path(k, tmp_path).name not in shared
    assert fl.writer_path("XAUUSD.asia", tmp_path).name == "ledger_XAUUSD_asia#own.json"
    # a clock that never collided keeps its byte-identical name
    assert fl.writer_path("EURUSD.london", tmp_path).name == "ledger_EURUSD_london.json"
    assert fl.writer_path("CHFDKK.overnight_gap_decay.asia", tmp_path).name == (
        "ledger_CHFDKK_overnight_gap_decay_asia.json")


def test_reader_gets_its_own_file_or_a_named_gap_never_a_sibling(tmp_path: Path) -> None:
    (tmp_path / "ledger_XAUUSD_asia.json").write_text(json.dumps(_rows(9.0)), "utf-8")
    # no registry yet: a variant still refuses the cell's file
    rows, status, why = fl.read_rows("XAUUSD.asia#rr=1.5", (tmp_path,))
    assert rows is None and status == fl.UNMEASURED_SHARED_LEDGER and "shared" in why
    # once frozen, the base key refuses it too
    fl.freeze_collisions(KEYS, tmp_path)
    assert fl.read_rows("XAUUSD.asia", (tmp_path,))[1] == fl.UNMEASURED_SHARED_LEDGER
    # each clock's own file is its series
    (tmp_path / "ledger_XAUUSD_asia#rr=1_5.json").write_text(json.dumps(_rows(1.0)), "utf-8")
    (tmp_path / "ledger_XAUUSD_asia#own.json").write_text(json.dumps(_rows(2.0)), "utf-8")
    assert fl.read_rows("XAUUSD.asia#rr=1.5", (tmp_path,))[0][0]["r_multiple"] == 1.0
    assert fl.read_rows("XAUUSD.asia", (tmp_path,))[0][0]["r_multiple"] == 2.0
    assert fl.read_rows("XAUUSD.asia#rr=2.5", (tmp_path,))[1] == fl.UNMEASURED_SHARED_LEDGER
    assert fl.read_rows("GBPUSD.asia", (tmp_path,))[1] == fl.NO_LEDGER
    # the legacy file is left exactly as it was
    assert json.loads((tmp_path / "ledger_XAUUSD_asia.json").read_text("utf-8")) == _rows(9.0)


def test_a_caller_holding_every_key_refuses_before_any_registry_exists(tmp_path: Path) -> None:
    (tmp_path / "ledger_XAUUSD_asia.json").write_text(json.dumps(_rows(9.0)), "utf-8")
    assert fl.read_rows("XAUUSD.asia", (tmp_path,))[1] == fl.OWN
    assert fl.read_rows("XAUUSD.asia", (tmp_path,), fl.collisions(KEYS))[1] == (
        fl.UNMEASURED_SHARED_LEDGER)


# ------------------------------------------------------------------- the readers that resolve
def test_forward_reconcile_no_longer_reads_the_shared_file_as_a_series(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import forward_reconcile as fr
    (tmp_path / "ledger_XAUUSD_asia.json").write_text(json.dumps(_rows(9.0)), "utf-8")
    monkeypatch.setattr(fr, "SHADOW", tmp_path)
    r, basis = fr.forward_series("XAUUSD.asia#rr=1.5", {"n": 3}, live={})
    assert r == [] and basis == fl.UNMEASURED_SHARED_LEDGER
    (tmp_path / "ledger_XAUUSD_asia#rr=1_5.json").write_text(json.dumps(_rows(1.0)), "utf-8")
    assert fr.forward_series("XAUUSD.asia#rr=1.5", {"n": 3}, live={}) == (
        [1.0, 1.0, 1.0], "shadow_ledger_forward")


def test_decay_monitor_and_slot_ranker_refuse_a_frozen_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import decay_monitor as dm
    import forward_slot_ranker as fsr
    (tmp_path / "ledger_XAUUSD_asia.json").write_text(json.dumps(_rows(9.0)), "utf-8")
    monkeypatch.setattr(dm, "SHADOW_LEDGER_DIRS", (tmp_path,))
    monkeypatch.setattr(fsr, "SHADOW_DIR", tmp_path)
    assert dm._shadow_ledger_rows("XAUUSD.asia") != [], "not frozen yet: its own file"
    fl.freeze_collisions(KEYS, tmp_path)
    assert dm._shadow_ledger_rows("XAUUSD.asia") == []
    assert dm._shadow_ledger_rows("XAUUSD.asia#rr=1.5") == []
    assert fsr.forward_days("XAUUSD.asia") == {}


def test_shadow_forward_writes_through_the_per_key_writer() -> None:
    """The WRITER half: shadow_forward freezes collisions over every key it holds and writes each
    clock's ledger at `writer_path`, never at the symbol/family/window name."""
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert "_fl.freeze_collisions(" in src
    assert "_fl.writer_path(key, SHADOW_DIR, shared_ledgers)" in src
    assert 'f"ledger_{sym}_{win}.json"' not in src and 'f"ledger_{sym}_{fam}_{win}.json"' not in src


def test_forward_exploitation_and_hazard_index_skip_a_frozen_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import forward_exploitation as fx
    import hazard_engine as hz
    shared = fl.freeze_collisions(KEYS, tmp_path)
    (tmp_path / "ledger_XAUUSD_asia.json").write_text(json.dumps(_rows(1.0)), "utf-8")
    own = tmp_path / fl.writer_name("XAUUSD.asia#rr=1.5", shared)
    own.write_text(json.dumps(_rows(-1.0)), "utf-8")
    monkeypatch.setattr(fx, "SHADOW_DIR", tmp_path)
    assert fx.ledger_path("XAUUSD.asia#rr=1.5") == own
    base = fx.ledger_path("XAUUSD.asia")
    assert base.name == fl.own_name("XAUUSD.asia") and not base.exists()
    idx = hz._ledger_index(tmp_path)
    assert "ledger_xauusd_asia.json" not in idx and own.name.lower() in idx
