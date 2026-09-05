"""R0520: run_fee_attribution is the CONSUMER of the executor's unconfirmed-order tape.

The recorder without a reader would be an unwired capability (III.16), and these pin the one
distinction that makes the reading honest: a tape that does not exist yet says NOTHING about the
$3.26M of notional already missing, because the recorder postdates it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from libs.ops.input_provenance import Inputs

_SPEC = importlib.util.spec_from_file_location(
    "run_fee_attribution", Path(__file__).resolve().parents[2] / "scripts/run_fee_attribution.py")
assert _SPEC is not None and _SPEC.loader is not None
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _run(tmp_path: Path, monkeypatch, lines: list[str] | None) -> dict:
    monkeypatch.setattr(_MOD, "_ROOT", tmp_path)
    if lines is not None:
        p = tmp_path / _MOD._FAILURES
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", "utf-8")
    return _MOD._failure_tape(Inputs(caller="test"))


def test_absent_tape_is_not_yet_produced_never_zero(tmp_path: Path, monkeypatch) -> None:
    """L1.28a. The gap predates the recorder, so an empty tape is not evidence of no failures."""
    out = _run(tmp_path, monkeypatch, None)
    assert out["status"] == "NOT-YET-PRODUCED"
    assert out["rows"] == 0
    assert "never zero" in out["why"]


def test_attempts_are_summed_per_symbol(tmp_path: Path, monkeypatch) -> None:
    out = _run(tmp_path, monkeypatch, [
        json.dumps({"event": "open_fail", "symbol": "COOKIEUSDT", "attempted_notional": 887.01,
                    "at": "2026-08-19T14:00:00+00:00"}),
        json.dumps({"event": "close_fail", "symbol": "MOVEUSDT", "attempted_notional": 1200.5,
                    "at": "2026-08-19T14:05:00+00:00"}),
        json.dumps({"event": "topup_fail", "symbol": "COOKIEUSDT", "attempted_notional": 100.0,
                    "at": "2026-08-19T14:09:00+00:00"}),
    ])
    assert out["status"] == "MEASURED"
    assert out["rows"] == 3
    assert out["attempted_notional_usd"] == 2187.51
    # ranked by attempted notional, biggest first: MOVE 1200.50 > COOKIE 887.01 + 100.00
    assert list(out["by_symbol"]) == ["MOVEUSDT", "COOKIEUSDT"]
    assert out["by_symbol"]["COOKIEUSDT"] == 987.01
    assert out["since"] == "2026-08-19T14:00:00+00:00"


def test_unparseable_rows_are_counted_never_dropped(tmp_path: Path, monkeypatch) -> None:
    """L1.60: a denominator that loses members in silence is a claim the desk cannot cash."""
    out = _run(tmp_path, monkeypatch, [
        json.dumps({"event": "open_fail", "symbol": "AAAUSDT", "attempted_notional": 10.0}),
        "{not json",
        json.dumps(["a list, not an object"]),
    ])
    assert out["rows"] == 1
    assert out["unparseable"] == 2


def test_a_row_without_a_notional_still_counts_as_an_attempt(tmp_path: Path, monkeypatch) -> None:
    """An unpriceable attempt is still an attempt -- it must not vanish from the row count."""
    out = _run(tmp_path, monkeypatch, [
        json.dumps({"event": "open_fail", "symbol": "AAAUSDT"}),
    ])
    assert out["rows"] == 1
    assert out["attempted_notional_usd"] == 0.0
    assert out["by_symbol"] == {}
