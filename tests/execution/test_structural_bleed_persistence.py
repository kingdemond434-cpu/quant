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
    have been had the rolling window still carried the symbol. Granted AT OR BELOW the recorded
    cap: the row authorises a $100 probe, so $100 is the probe it authorises.
    """
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    _rows(tmp_path, monkeypatch, opened)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", 100.0) is False
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", 25.0) is False


# --------------------------------------------------------------------------------------------
# THE PROBE CAP HAD NO READER (found 2026-08-13, two days before the first probe window opened).
# `max_notional_usd` appeared NOWHERE in the repo outside the JSON that declares it, so an armed
# probe un-blocked the symbol and the open then proceeded at ordinary size -- while the protocol
# promised "a bounded number of MINIMUM-SIZE probes" and the rows documented a $100 cap. The
# denylist exists to prevent exactly the event an uncapped probe would cause: NOMUSDT took $4,297
# into a thin book on 2026-07-13 and cost 40.9% of venue equity in five minutes.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("notional", [100.01, 500.0, 4297.0])
def test_an_oversized_probe_is_refused_however_open_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notional: float
) -> None:
    """THE REGRESSION. Window open, budget unspent, size over the recorded cap -> still denied."""
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    _rows(tmp_path, monkeypatch, opened)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", notional) is True


def test_an_undeclared_size_cannot_be_certified_as_within_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UNMEASURED IS NOT WITHIN-CAP (L1.28a). A caller that does not say how big its open is has
    not shown the probe is bounded, so the verdict stands -- the fail-closed direction.
    """
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    _rows(tmp_path, monkeypatch, opened)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT") is True
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", None) is True
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", 0.0) is True


def test_a_row_without_a_declared_cap_authorises_no_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cap the row never declares is not a cap, so there is no bounded probe to grant."""
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    del opened["ZZZBLEEDUSDT"]["max_notional_usd"]                       # type: ignore[union-attr]
    _rows(tmp_path, monkeypatch, opened)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT", 1.0) is True


def test_the_entry_gate_passes_its_intended_notional_to_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PINS THE PLUMBING, which is where this defect actually lived.

    `_entry_gate` already knew the intended per-leg notional (R0247) and simply never handed it
    to the denylist. A gate that computes the right number and drops it before the check is
    indistinguishable from one that never had it.
    """
    opened = json.loads(json.dumps(_BLOCKED))
    opened["ZZZBLEEDUSDT"]["probe_after"] = "2000-01-01T00:00:00+00:00"  # type: ignore[index]
    _rows(tmp_path, monkeypatch, opened)
    monkeypatch.setattr(ex, "_rt_bps", lambda _s, _n=None: 1.0)   # cheap book: isolate the veto
    assert ex._entry_gate("ZZZBLEEDUSDT", 0.001, notional=50.0) is True     # within cap
    assert ex._entry_gate("ZZZBLEEDUSDT", 0.001, notional=5000.0) is False  # over cap
    assert ex._entry_gate("ZZZBLEEDUSDT", 0.001) is False                   # size undeclared


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


# --------------------------------------------------------------------------------------------
# R0158. The repair above (2026-08-05) put the persistent graveyard BELOW an early return that
# fires whenever `worst_symbols` will not parse. So on a corrupt or absent forensics artifact --
# the one input the graveyard exists to survive -- the newest denial layer was unreachable and
# the gate allowed the open. These pin the fix in both directions: the deny path must reach the
# graveyard and the cached window, and an innocent symbol must still be allowed.
# --------------------------------------------------------------------------------------------


def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the last-good cache at a tmp file so tests never touch the live one."""
    cache = tmp_path / "structural_bleed_last_good.json"
    monkeypatch.setattr(ex, "_BLEED_CACHE", cache)
    return cache


@pytest.mark.parametrize("payload", ["{not json", '{"worst_symbols": "not-a-list"}', None])
def test_unparseable_forensics_still_reaches_the_persistent_graveyard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str | None
) -> None:
    """THE REGRESSION. Corrupt, malformed, or absent forensics must not un-deny a bleeder."""
    forensics = tmp_path / "trade_forensics.json"
    if payload is not None:  # None => the file never exists at all
        forensics.write_text(payload, "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps(_BLOCKED), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    _cache(tmp_path, monkeypatch)
    assert ex._structurally_bleeding("ZZZBLEEDUSDT") is True


def test_unparseable_forensics_leaves_innocent_symbols_openable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TIGHTEN-ONLY. The repair may add denials, never invent them for unrecorded names."""
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text("{not json", "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps(_BLOCKED), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    _cache(tmp_path, monkeypatch)
    for sym in ("BTCUSDT", "ETHUSDT"):
        assert ex._structurally_bleeding(sym) is False


def test_last_good_window_denies_a_bleeder_the_graveyard_never_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symbol proven bleeding by forensics ALONE survives the file going corrupt.

    `data/execution_reentry.json` is written by hand after an incident, so a freshly-measured
    bleeder is in the rolling window and nowhere else. Without the cache, one corrupt read
    re-opens it at full size.
    """
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": [
        {"symbol": "ZZZFRESHUSDT", "n": 6, "bps": -80.0}]}), "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps({"_default": "DENY"}), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    cache = _cache(tmp_path, monkeypatch)

    assert ex._structurally_bleeding("ZZZFRESHUSDT") is True   # live read populates the cache
    assert cache.exists()
    forensics.write_text("{truncated", "utf-8")                # producer dies mid-write
    assert ex._structurally_bleeding("ZZZFRESHUSDT") is True   # cache carries the denial
    assert ex._structurally_bleeding("BTCUSDT") is False       # and only that denial


def test_an_emptied_rolling_window_never_erases_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The forgetting defect, one layer down.

    `worst_symbols` empties whenever the book pauses -- the ordinary state during a drawdown.
    If an empty read were written through, the cache would be wiped in exactly the same
    self-reinforcing way the 2026-08-05 defect wiped the denylist.
    """
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({"worst_symbols": [
        {"symbol": "ZZZFRESHUSDT", "n": 6, "bps": -80.0}]}), "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps({"_default": "DENY"}), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    _cache(tmp_path, monkeypatch)

    assert ex._structurally_bleeding("ZZZFRESHUSDT") is True
    forensics.write_text(json.dumps({"worst_symbols": []}), "utf-8")  # book pauses
    assert ex._structurally_bleeding("ZZZFRESHUSDT") is False         # live empty read governs
    forensics.write_text("{truncated", "utf-8")                       # now it also corrupts
    assert ex._structurally_bleeding("ZZZFRESHUSDT") is True          # cache was NOT wiped


def test_a_cache_written_under_the_old_key_still_fences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The payload key was renamed `worst_symbols` -> `rows` when the fence moved to the all-time
    list. A cache file written before that rename must still deny: dropping it would discard
    recorded denials at exactly the moment the live artifact is unreadable, which is the one
    direction this cache exists to prevent.
    """
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text("{not json", "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps({"_default": "DENY"}), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    cache = _cache(tmp_path, monkeypatch)
    cache.write_text(json.dumps({"worst_symbols": [
        {"symbol": "ZZZOLDKEYUSDT", "n": 5, "bps": -80.0}], "cached": "2026-08-13"}), "utf-8")
    assert ex._structurally_bleeding("ZZZOLDKEYUSDT") is True
    assert ex._structurally_bleeding("BTCUSDT") is False


def test_a_missing_cache_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No cache + unreadable forensics + no graveyard row => allowed, exactly as pre-fix."""
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text("{not json", "utf-8")
    ledger = tmp_path / "execution_reentry.json"
    ledger.write_text(json.dumps({"_default": "DENY"}), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)
    monkeypatch.setattr(ex, "_REENTRY", ledger)
    _cache(tmp_path, monkeypatch)
    assert ex._last_good_bleed_window() == []
    assert ex._structurally_bleeding("BTCUSDT") is False
