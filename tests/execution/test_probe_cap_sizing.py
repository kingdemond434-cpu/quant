"""An authorised re-entry probe must be SIZED at its cap, not merely refused above it.

MEASURED DEFECT (2026-08-18). Every one of the 7 recorded re-entry rows (cap $100, windows open
since 08-15, budgets unspent) was REFUSED by `_probe_within_cap` because the intended notional
arrived as the funding-weighted share of free capital -- hundreds of dollars -- from an `_alloc`
that never learned the cap existed. The refusing half of the protocol shipped 2026-08-13; the
sizing half did not exist, so the door L1.16a/L1.45 require was welded shut: the only path back
for a blocked symbol could not fire at any free capital above ~cap x n_cands.

These tests pin the sizing half: `_probe_caps` names exactly the authorised probes, the clamp
grants the probe at min(share, cap), and everything else -- unknown sizes, over-cap sizes,
exhausted budgets, capless rows -- stays refused exactly as before (tighten-only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.run_cashcarry_executor as ex

_ROW: dict[str, object] = {
    "named_change": "synthetic fixture -- mechanism of death addressed",
    "original_verdict": {"n": 5, "bps": -74.6, "net_usd": -43.32},
    "probe_after": "2020-01-01T00:00:00+00:00",     # window long open
    "max_probes": 3,
    "max_notional_usd": 100.0,
}


def _wire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reentry: dict[str, object],
          tape: list[dict[str, object]] | None = None) -> None:
    """Empty rolling window + a recorded re-entry ledger + a controlled tape."""
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": []}), "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps(reentry), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    monkeypatch.setattr(ex.execution_tape, "read", lambda: list(tape or []))


def test_authorised_probe_appears_in_cap_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": dict(_ROW)})
    assert ex._probe_caps() == {"ZZZPROBEUSDT": 100.0}


def test_clamped_share_is_granted_where_raw_share_was_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE REGRESSION. At the $500 share _alloc chose, the probe was refused (welded door);
    at min(share, cap) -- what both consumers now pass -- the door opens."""
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": dict(_ROW)})
    assert ex._structurally_bleeding("ZZZPROBEUSDT", 500.0) is True
    caps = ex._probe_caps()
    clamped = min(500.0, caps.get("ZZZPROBEUSDT", float("inf")))
    assert clamped == 100.0
    assert ex._structurally_bleeding("ZZZPROBEUSDT", clamped) is False


def test_exhausted_budget_never_enters_the_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spent probe budget is a standing verdict: no cap entry, still denied at any size."""
    tape: list[dict[str, object]] = [
        {"event": "open", "symbol": "ZZZPROBEUSDT", "opened": f"2026-08-1{d}T01:00:00+00:00"}
        for d in (5, 6, 7)
    ]
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": dict(_ROW)}, tape=tape)
    assert ex._probe_caps() == {}
    assert ex._structurally_bleeding("ZZZPROBEUSDT", 100.0) is True


def test_capless_row_never_enters_the_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No declared cap => no bounded probe exists (unchanged from the refusing half)."""
    row = {k: v for k, v in _ROW.items() if k != "max_notional_usd"}
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": row})
    assert ex._probe_caps() == {}
    assert ex._structurally_bleeding("ZZZPROBEUSDT", 50.0) is True


def test_unknown_size_stays_refused_and_says_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """max_audit's dormancy probe declares no notional: refused fail-closed, and the refusal
    must be labelled a diagnostic read -- an unknown size and an over-cap size are different
    claims (L1.55), and only the second means the clamp failed."""
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": dict(_ROW)})
    assert ex._structurally_bleeding("ZZZPROBEUSDT") is True
    out = capsys.readouterr().out
    assert "diagnostic read at unknown size" in out
    assert "fail-closed" in out


def test_unrecorded_symbols_are_never_clamped_or_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tighten-only: symbols in neither source are allowed exactly as before, and the cap map
    carries no entry that could shrink their opens."""
    _wire(tmp_path, monkeypatch, {"ZZZPROBEUSDT": dict(_ROW)})
    caps = ex._probe_caps()
    for sym in ("BTCUSDT", "ETHUSDT"):
        assert sym not in caps
        assert ex._structurally_bleeding(sym, 500.0) is False
