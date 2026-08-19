"""Pins R0483: the print-impact pair cost is a LABELLED THIRD BASIS in `_rt_bps`, folded in
through the same tighten-only max() as the realised-fills floor.

The row was deferred once on the fear that the print basis -- which reads CHEAPER than the book
walk on exactly the thin books that produced COOKIEUSDT 130bps (CELR 0.40x, ZEN 0.43x,
TST 0.44x) -- could loosen the entry gate. These tests pin the property that makes the wiring
safe: under max() a cheaper print reading NEVER binds, an absent/unmeasured one changes nothing,
and only a print cost ABOVE the other bases can move the gate -- and that movement is a refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.run_cashcarry_executor as ex

_BUCKETS = {"500": {"pair_roundtrip_bps": 10.0}}


def _install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             pairs: list[dict] | None) -> None:
    cost = tmp_path / "cost_model.json"
    cost.write_text(json.dumps({"symbols": {"PBTUSDT": {"pair": dict(_BUCKETS)}}}), "utf-8")
    monkeypatch.setattr(ex, "_COST_MODEL", cost)
    # No realised-fill floor: the print basis is under the microscope.
    monkeypatch.setattr(ex, "_TRADES", tmp_path / "no_trades.json")
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": []}), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    pi = tmp_path / "print_impact.json"
    if pairs is not None:
        pi.write_text(json.dumps({"generated": "2026-08-18T00:00:00+00:00",
                                  "pairs": pairs}), "utf-8")
    monkeypatch.setattr(ex, "_PRINT_IMPACT", pi)


def test_cheaper_print_basis_never_loosens(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    # Print pair open 2.0bps -> RT 4.0bps, well under the 10.0 book walk: the exact thin-book
    # direction (ratio < 1) that deferred R0483. The gate must stay at the book walk.
    _install(tmp_path, monkeypatch,
             [{"symbol": "PBTUSDT", "print_pair_open_bps": 2.0}])
    assert ex._rt_bps("PBTUSDT") == 10.0


def test_expensive_print_basis_tightens(tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    # Print pair open 9.0bps -> RT 18.0bps > 10.0 book walk: realised third-party execution
    # says the book walk under-prices this name; the gate takes the tighter number.
    _install(tmp_path, monkeypatch,
             [{"symbol": "PBTUSDT", "print_pair_open_bps": 9.0}])
    assert ex._rt_bps("PBTUSDT") == 18.0


def test_absent_or_unmeasured_print_changes_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    # No artifact at all (fitter never ran) -- fail-closed to the two existing bases.
    _install(tmp_path, monkeypatch, None)
    assert ex._rt_bps("PBTUSDT") == 10.0
    # Artifact present but the symbol's pair is unpriced (one leg unmeasured -> None), or the
    # symbol is absent from the table entirely: both are the today-state (pairs == []).
    _install(tmp_path, monkeypatch, [{"symbol": "PBTUSDT", "print_pair_open_bps": None}])
    assert ex._rt_bps("PBTUSDT") == 10.0
    _install(tmp_path, monkeypatch, [])
    assert ex._rt_bps("PBTUSDT") == 10.0


def test_print_basis_stacks_with_realised_floor(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    # All three bases present: the gate takes the MAX of the three, whichever it is.
    _install(tmp_path, monkeypatch,
             [{"symbol": "PBTUSDT", "print_pair_open_bps": 6.0}])   # RT 12.0
    trades = tmp_path / "trades.json"
    trades.write_text(json.dumps([
        {"symbol": "PBTUSDT", "spot_slip_bps": 7.0, "fut_slip_bps": 7.0},
        {"symbol": "PBTUSDT", "spot_slip_bps": 7.5, "fut_slip_bps": 7.5},
        {"symbol": "PBTUSDT", "spot_slip_bps": 8.0, "fut_slip_bps": 8.0},
    ]), "utf-8")                                                    # realised median 15.0
    monkeypatch.setattr(ex, "_TRADES", trades)
    assert ex._rt_bps("PBTUSDT") == 15.0                            # realised binds
    trades.write_text(json.dumps([
        {"symbol": "PBTUSDT", "spot_slip_bps": 2.0, "fut_slip_bps": 2.0},
        {"symbol": "PBTUSDT", "spot_slip_bps": 2.5, "fut_slip_bps": 2.5},
        {"symbol": "PBTUSDT", "spot_slip_bps": 3.0, "fut_slip_bps": 3.0},
    ]), "utf-8")                                                    # realised median 5.0
    assert ex._rt_bps("PBTUSDT") == 12.0                            # print binds
