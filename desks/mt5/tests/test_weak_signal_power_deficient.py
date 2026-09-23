"""`power_deficient` must read the schema the gauntlet actually writes, and carry real params.

THE BUG THIS PINS RETURNED ZERO SILENTLY. The gauntlet writes each verdict's per-gate detail under
`stages`; this function asked for `gates`. `.get("gates") or {}` is an empty dict, not an error, so
`failed` was empty for every row and `if not failed: continue` discarded the entire docket. The
compiler printed "0 symbols with members, 0 combinations, 0 proposed" and looked like a lane with
nothing to do. Measured on the trading box 2026-09-14: 7,831 verdicts, 0 carrying `gates`, 7,831
carrying `stages`, 560 cells failing only power gates across 67 eligible symbols.

AND A MEMBER WITHOUT ITS PARAMS IS A DIFFERENT STRATEGY. The verdict names a cell as
`SYM.family.p=<sha256[:16]>` -- a one-way digest -- so params can only come from the docket row
that minted it. A member silently built with `{}` would be combined under a name it does not have.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
wsc = pytest.importorskip("research.weak_signal_compiler")
from research.frontier_identity import cell_id  # noqa: E402


def _write(tmp_path: Path, monkeypatch, verdicts: list[dict], docket: list[dict]) -> None:
    g = tmp_path / "universal_gates_external.json"
    d = tmp_path / "external_survivors.json"
    g.write_text(json.dumps({"verdicts": verdicts}), encoding="utf-8")
    d.write_text(json.dumps(docket), encoding="utf-8")
    monkeypatch.setattr(wsc, "GATES", g)
    monkeypatch.setattr(wsc, "DOCKET", d)


def _row(sym: str, fam: str, params: dict) -> dict:
    return {"symbol": sym, "family": fam, "params": params}


def test_stages_schema_is_read_and_gates_schema_still_works(tmp_path, monkeypatch):
    """The live schema (`stages`) must be honoured; the legacy name stays a fallback."""
    params = {"rr": 1.5, "mode": "spike_reversion"}
    row = _row("EURUSD", "pca_residual", params)
    cid = cell_id({**row, "sym": "EURUSD"})
    power_fail = {"deflated_sharpe": {"passed": False},
                  "in_sample_screen": {"passed": True, "sharpe": 0.31},
                  "pbo": {"passed": True}}
    for field in ("stages", "gates"):
        _write(tmp_path, monkeypatch,
               [{"cell": cid, "sym": "EURUSD", "family": "pca_residual", field: power_fail}],
               [row])
        out = wsc.power_deficient()
        assert "EURUSD" in out, f"{field!r} schema was not read"
        assert out["EURUSD"][0]["params"] == params, "params must come from the docket row"
        assert out["EURUSD"][0]["sharpe"] == pytest.approx(0.31)


def test_a_cell_failing_a_validity_gate_is_not_a_member(tmp_path, monkeypatch):
    """Only a POWER deficit qualifies. A cell that failed pbo is refuted, not under-powered."""
    row = _row("GBPUSD", "carry", {"rr": 2.0})
    cid = cell_id({**row, "sym": "GBPUSD"})
    _write(tmp_path, monkeypatch,
           [{"cell": cid, "sym": "GBPUSD", "family": "carry",
             "stages": {"deflated_sharpe": {"passed": False}, "pbo": {"passed": False}}}],
           [row])
    assert wsc.power_deficient() == {}


def test_a_cell_with_no_docket_row_is_dropped_not_defaulted(tmp_path, monkeypatch):
    """An unjoinable cell must vanish rather than be built with empty params under its name."""
    _write(tmp_path, monkeypatch,
           [{"cell": "NOSUCH.carry.p=deadbeefdeadbeef", "sym": "NOSUCH", "family": "carry",
             "stages": {"expected_value": {"passed": False}}}],
           [_row("OTHER", "carry", {"rr": 1.0})])
    assert wsc.power_deficient() == {}


def test_a_verdict_with_no_stage_detail_is_not_a_member(tmp_path, monkeypatch):
    """A cell the sweep never judged is UNMEASURED, and absence is never a qualification."""
    row = _row("USDJPY", "carry", {"rr": 1.0})
    cid = cell_id({**row, "sym": "USDJPY"})
    _write(tmp_path, monkeypatch,
           [{"cell": cid, "sym": "USDJPY", "family": "carry", "stages": {}}], [row])
    assert wsc.power_deficient() == {}
