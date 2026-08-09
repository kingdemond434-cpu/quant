"""The structural-bleed denylist must not forget itself while the book is paused.

MEASURED DEFECT (2026-08-05). `_structurally_bleeding` read only `worst_symbols`, which
`run_trade_forensics.py` computes over a 14-DAY ROLLING window of this book's own closes. The
book paused 2026-08-01 on a -17.6% drawdown, the window emptied, and on a freshly regenerated
artifact (not a stale one) `worst_symbols == []` -- so the gate returned False for COOKIEUSDT and
1000CATUSDT, the two incident-#6 symbols the executor's own comment calls "currently-blocked".

The failure is self-reinforcing: a pause is CAUSED by losses, so the denylist is guaranteed to be
wiped exactly when it is most needed, and a re-arm re-opens the proven losers at FULL size -- ten
days before the 2026-08-15 / $100 / 3-probe ceiling their `data/execution_reentry.json` rows exist
to impose. That protocol was unreachable code, consulted only for symbols the rolling window still
happened to carry.

This compounds: R0057 DELETED the absolute per-8h funding floor on 2026-07-31 on the reasoning
that "the per-symbol cost gate plus the structural-bleed denylist carry all of its protection"
(tests/execution/test_entry_gate.py). One of those two had silently become a no-op.

These tests pin all three directions: the persistent denial, the tighten-only guarantee, and the
door that must still open -- an exclusion with no way back is the L1.16a/L1.45 defect this
denylist's own re-entry ledger exists to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.run_cashcarry_executor as ex


def _rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reentry: dict[str, object]) -> None:
    """An EMPTY rolling window plus a recorded re-entry ledger -- the exact measured state."""
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": []}), "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps(reentry), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)


_BLOCKED = {
    "_default": "DENY",
    "ZZZBLEEDUSDT": {
        "named_change": "synthetic fixture -- mechanism of death addressed",
        "original_verdict": {"n": 5, "bps": -74.6, "net_usd": -43.32},
        "probe_after": "2099-01-01T00:00:00+00:00",
        "max_probes": 3,
        "max_notional_usd": 100.0,
    },
}


def test_recorded_bleeder_stays_denied_when_the_rolling_window_has_emptied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE REGRESSION. Empty `worst_symbols` must not un-deny a recorded bleeder."""
    _rows(tmp_path, monkeypatch, _BLOCKED)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT") is True


def test_symbols_absent_from_both_sources_are_unaffected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TIGHTEN-ONLY. The persistent branch may add denials, never invent them."""
    _rows(tmp_path, monkeypatch, _BLOCKED)
    for sym in ("BTCUSDT", "ETHUSDT", "GTCUSDT"):
        assert ex._structurally_bleeding(sym) is False


def test_metadata_keys_are_never_treated_as_symbols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ledger carries `_law`/`_purpose`/`_default` prose beside real rows."""
    _rows(tmp_path, monkeypatch, _BLOCKED)
    assert ex._structurally_bleeding("_default") is False


def test_the_door_still_opens_so_the_exclusion_is_not_absorbing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L1.16a/L1.45: a persistent denial with no path back is a worse defect than the leak.

    Same row, probe window already open -> the bounded probe is granted, exactly as it would
    have been had the rolling window still carried the symbol.
    """
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    _rows(tmp_path, monkeypatch, opened)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT") is False


def test_unreadable_ledger_does_not_become_a_licence_to_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt ledger degrades to the PRE-FIX behaviour, never looser than it."""
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": [
        {"symbol": "ZZZBLEEDUSDT", "n": 5, "bps": -74.6}]}), "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text("{not json", "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    # windowed row + unreadable ledger => no recorded probe condition => denied, as before
    assert ex._structurally_bleeding("ZZZBLEEDUSDT") is True
