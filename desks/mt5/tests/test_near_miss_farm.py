"""near_miss_farm: every near-miss on the one forward engine, its own ledger, no authority."""
from __future__ import annotations

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
        "external.a": _row("EURUSD", "turn_of_month", {"side": -1}),
        "external.b": _row("EURUSD", "turn_of_month", {}),
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
    from research import shadow_forward as sf
    monkeypatch.setattr(sf, "SHADOW_DIR", tmp_path / "shadow")
    marks: list[str] = []
    monkeypatch.setattr(nmf, "_farm_watermark", lambda n, ledger: marks.append(ledger))
    doc = nmf.run(out=tmp_path / "out.json")
    ledger = tmp_path / "shadow" / nmf.LEDGER_REL
    assert ledger.exists() and marks == [nmf.LEDGER_REL]
    state = json.loads(ledger.read_text())
    rows = [v for v in state.values() if isinstance(v, dict) and "n" in v]
    assert rows and not any(v.get("promotion_authority") for v in rows)
    assert doc["authority_leaks"] == 0 and doc["cells_farmed"] == 1
    assert not (tmp_path / "shadow" / "shadow_state.json").exists()
