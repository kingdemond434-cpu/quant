"""A principal withdrawal is not a loss: sizing and the equity floor see it, loss rails don't."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from mt5desk import fusion_equity_reference as fer

_DM = Path(__file__).resolve().parents[1] / "proposals" / "fusion_deadman.py"


def _ref(tmp_path: Path, **doc: object) -> Path:
    p = tmp_path / "ref.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_sizing_acts_as_if_the_withdrawal_had_not_happened(tmp_path: Path) -> None:
    p = _ref(tmp_path, reference_equity=460, withdrawn=200)
    assert fer.sizing_equity(266.0, p) == 460.0          # capped at the reference
    assert fer.sizing_equity(200.0, p) == 400.0          # a later loss still shrinks the book
    assert fer.sizing_equity(500.0, p) == 500.0          # fades once real equity is back
    assert fer.active_offset(266.0, p) == 200.0
    assert fer.active_offset(470.0, p) == 0.0


def test_no_valid_reference_means_no_uplift(tmp_path: Path) -> None:
    assert fer.sizing_equity(266.0, tmp_path / "missing.json") == 266.0
    for doc in ({"reference_equity": 460}, {"reference_equity": 99999, "withdrawn": 200},
                {"reference_equity": 460, "withdrawn": 500}, {"reference_equity": 460,
                                                              "withdrawn": -1}):
        p = _ref(tmp_path, **doc)
        assert fer.sizing_equity(266.0, p) == 266.0 and fer.active_offset(266.0, p) == 0.0
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert fer.sizing_equity(266.0, bad) == 266.0


def _deadman():
    spec = importlib.util.spec_from_file_location("fusion_deadman_t", _DM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_equity_floor_counts_the_withdrawal_and_still_trips_on_a_real_loss() -> None:
    dm = _deadman()
    codes = lambda acct: [c for c, _ in dm.evaluate(acct, [], [], 568.77)]  # noqa: E731
    assert "EQUITY_FLOOR" in codes({"equity": 266.0})
    assert "EQUITY_FLOOR" not in codes({"equity": 266.0, "withdrawn_offset": 200.0})
    assert "EQUITY_FLOOR" in codes({"equity": 90.0, "withdrawn_offset": 200.0})


def test_a_locked_breach_log_never_kills_the_rail(tmp_path: Path, monkeypatch, capsys) -> None:
    dm = _deadman()
    locked = tmp_path / "logs"
    locked.mkdir()
    target = locked / "fusion_deadman.log"
    target.mkdir()                                       # opening a directory for append fails
    monkeypatch.setattr(dm, "BREACH_LOG", target)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    dm.log("BREACH test")
    out = capsys.readouterr().out
    assert "BREACH test" in out and "not appended" in out
