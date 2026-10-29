"""near_miss_farm: every near-miss on the one forward engine, its own ledger, no authority."""
from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import near_miss_farm as nmf  # noqa: E402


def _row(sym: str, fam: str, params: dict) -> dict:
    return {"cell": f"{sym}.{fam}", "validity_pass": True, "promotion_authority": False,
            "failed_power_gates": ["deflated_sharpe"],
            "shadow_spec": {"symbol": sym, "selector": "continuous", "family": fam,
                            "params": params}}


def test_a_short_cell_keeps_its_side_and_carries_no_authority() -> None:
    rows, refused = nmf.farm_rows({
        "external.a": _row("EURUSD", "forced_flow", {"side": -1, "event_kind": "fixing"}),
        "external.b": _row("EURUSD", "forced_flow", {"event_kind": "fixing"}),
        "external.c": {"cell": "c"}})
    assert [r[4] for r in rows] == ["SHORT", "LONG"]
    assert all("side" not in r[2] for r in rows)
    assert all(r[5] == nmf.ADMISSION and r[7] is False for r in rows)
    assert [x["cell"] for x in refused] == ["external.c"]


def test_the_ledger_sits_outside_every_clock_store_glob() -> None:
    assert "/" in nmf.LEDGER_REL                               # a subdirectory: no glob reaches it
    name = Path(nmf.LEDGER_REL).name
    assert not name.endswith("_state.json") and not name.endswith("shadow_state.json")
    from research import retired_clocks
    assert not any(nmf.LEDGER_REL in s for s in retired_clocks.CLOCK_STORES)


def test_cure_thresholds_are_the_gate_specs() -> None:
    assert nmf.cure_thresholds() == {k: float(v) for k, v in nmf.FALLBACK_CURE.items()}


def test_absent_roster_is_unmeasured_not_empty(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nmf, "ROSTER", tmp_path / "none.json")
    monkeypatch.setattr(nmf, "SNAPSHOT", tmp_path / "none2.json")
    monkeypatch.setattr(nmf, "clockless_cert_rows", lambda: ([], [], "none"))
    doc = nmf.run(out=tmp_path / "out.json")
    assert doc["source"].startswith(nmf.UNMEASURED)
    assert json.loads((tmp_path / "out.json").read_text())["roster_rows"] == 0


def test_a_farm_pass_writes_its_own_ledger_with_authority_withheld(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not (DESK / "data" / "universe" / "EURUSD_H1.parquet").exists():
        pytest.skip("no EURUSD H1 bars on this tree")
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"rows": {"external.a": _row("EURUSD", "turn_of_month", {})}}))
    monkeypatch.setattr(nmf, "ROSTER", roster)
    monkeypatch.setattr(nmf, "clockless_cert_rows", lambda: ([], [], "none"))
    from research import shadow_forward as sf
    monkeypatch.setattr(sf, "SHADOW_DIR", tmp_path / "shadow")
    marks: list[str] = []
    monkeypatch.setattr(nmf, "_farm_watermark", lambda n, ledger: marks.append(ledger))
    doc = nmf.run(out=tmp_path / "out.json")
    ledger = tmp_path / "shadow" / nmf.LEDGER_REL
    assert ledger.exists() and marks == [nmf.LEDGER_NAME]
    # Per-trade ledgers land beside the farm state, never beside the certified lane's.
    assert not list((tmp_path / "shadow").glob("ledger_*.json"))
    assert tmp_path / "shadow" == sf.SHADOW_DIR                # restored after the run
    state = json.loads(ledger.read_text())
    rows = [v for v in state.values() if isinstance(v, dict) and "n" in v]
    assert rows and not any(v.get("promotion_authority") for v in rows)
    assert doc["authority_leaks"] == 0 and doc["cells_farmed"] == 1
    assert not (tmp_path / "shadow" / "shadow_state.json").exists()


def test_every_certificate_without_a_lane_clock_is_farmed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import admission_integrity, shadow_admission
    from research import shadow_forward as sf
    runs = [{"certificate": "c1", "symbol": "EURUSD", "selector": "asia",
             "family": "overnight_gap_decay", "side": "LONG", "params": {"gap_atr": 0.5}},
            {"certificate": "c2", "symbol": "GBPUSD", "selector": "asia",
             "family": "overnight_gap_decay", "side": "LONG", "params": {"gap_atr": 0.5}},
            {"certificate": "scalp.x", "symbol": "XAUUSD", "selector": "asia",
             "family": "scalp", "side": "LONG", "params": {}}]
    clocked = sf.sleeve_key("GBPUSD", "asia", {"gap_atr": 0.5}, "overnight_gap_decay", "LONG")
    monkeypatch.setattr(shadow_admission, "authorized_runs", lambda base: runs)
    monkeypatch.setattr(admission_integrity, "lane_clock_keys", lambda d: {clocked})
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls, **kw: cls(alarm={}, verdicts={})))
    rows, refused, why = nmf.clockless_cert_rows()
    assert [r[0] for r in rows] == ["EURUSD"] and not refused
    assert rows[0][5] == nmf.CERT_ADMISSION and rows[0][7] is False
    assert "3 certificates" in why


def test_hourly_leg_is_wired() -> None:
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("near_miss_farm"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["near_miss_farm"] == "timing"


def _bytes(p: Path) -> bytes | None:
    return p.read_bytes() if p.exists() else None


def test_a_farm_pass_never_touches_the_global_registry_or_clock_ledger(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit HOLD on #487: a farm pass wrote a LIVE row into the tracked sleeve registry and a
    clock into the global forward clock ledger, and a later main-lane pass inherited the farm's
    start with promotion authority. Every import path the engine uses is driven here, because a
    module imported under two names is two module objects."""
    import importlib

    from research import shadow_forward as sf
    real_reg = importlib.import_module("sleeve_registry").REGISTRY
    real_ledger = importlib.import_module("clock_ledger").LEDGER
    before = (_bytes(real_reg), _bytes(real_ledger))
    monkeypatch.setattr(sf, "SHADOW_DIR", tmp_path / "shadow")

    def engine(rows: list, ledger: str) -> None:
        import clock_ledger
        import sleeve_registry
        from research.clock_ledger import stamp
        stamp("FARM.K", "id", "2026-10-01T00:00:00+00:00")
        clock_ledger.stamp("FARM.K2", "id", "2026-10-01T00:00:00+00:00")
        sleeve_registry.freeze("FARM.K", {"params": {}},
                               forward_start="2026-10-01T00:00:00+00:00")
        for name in nmf.REGISTRY_MODULES[1:]:
            with contextlib.suppress(ImportError):
                importlib.import_module(name).freeze("FARM.K3", {"params": {}})

    monkeypatch.setattr(sf, "main", engine)
    nmf.evaluate([])
    assert (_bytes(real_reg), _bytes(real_ledger)) == before, "a global store was written"
    farm = tmp_path / "shadow" / nmf.FARM_SUBDIR
    assert "FARM.K" in json.loads((farm / nmf.FARM_REGISTRY).read_text())["sleeves"]
    clocks = json.loads((farm / nmf.FARM_CLOCK_LEDGER).read_text())["clocks"]
    assert {r["key"] for r in clocks.values()} >= {"FARM.K", "FARM.K2"}
    assert real_reg == importlib.import_module("sleeve_registry").REGISTRY, "restored"
    assert real_ledger == importlib.import_module("clock_ledger").LEDGER, "restored"

    # A promoting lane that later clocks the same key starts FRESH: nothing the farm did is
    # visible to the lane's ledger.
    from research.clock_ledger import stamp
    lane = tmp_path / "lane_clock_ledger.json"
    later = "2026-10-29T00:00:00+00:00"
    assert stamp("FARM.K", "id", later, path=lane)["start"] == later


def test_a_replication_mismatch_is_quarantined_never_farmed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit on #487: a MISMATCH means the desk's implementation disagrees with the written spec,
    so its forward evidence is evidence about the wrong strategy."""
    from research import admission_integrity, shadow_admission
    run = {"certificate": "c1", "symbol": "EURUSD", "selector": "asia",
           "family": "overnight_gap_decay", "side": "LONG", "params": {"gap_atr": 0.5}}
    fp = admission_integrity.spec_fingerprint("EURUSD", "overnight_gap_decay", "asia", "LONG",
                                              {"gap_atr": 0.5})
    monkeypatch.setattr(shadow_admission, "authorized_runs", lambda base: [run])
    monkeypatch.setattr(admission_integrity, "lane_clock_keys", lambda d: set())
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load", classmethod(
        lambda cls, **kw: cls(alarm={}, verdicts={"c1": {"fp": fp, "verdict": "MISMATCH"}})))
    rows, refused, _ = nmf.clockless_cert_rows()
    assert rows == [] and refused[0]["why"].startswith(admission_integrity.HELD_MISMATCH)
