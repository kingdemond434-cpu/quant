"""GATE-0's LIVE-KEY CHECK -- it was green on empty files, on the last gate before real capital.

MEASURED 2026-08-07 on the live box. `_keys_present` globbed `data/secrets/*`, filtered names
containing "binance" or "api", and reported "4 live-venue credential file(s)" as READY. In the same
session `check_credentials.py` -- which OPENS them -- reported binance_live.json INCOMPLETE
(missing api_key, api_secret), both testnets the same, and binance_live_spot.json ABSENT.

So the gate that sits immediately before live trading would have signed off on a key set that
cannot place an order. That is WS-005 (absence resolving to the clean verdict) on the most
consequential check the desk owns, and it is the same shape as mistaking a file EXISTING for a
file WORKING. A credential is a capability; the only evidence of a capability is its contents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.check_gate0_ready as G


@pytest.fixture()
def secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data" / "secrets"
    d.mkdir(parents=True)
    monkeypatch.setattr(G, "_ROOT", tmp_path)
    return d


def _write(d: Path, name: str, doc: object) -> None:
    (d / name).write_text(json.dumps(doc), "utf-8")


def test_AN_EMPTY_CREDENTIAL_FILE_IS_NOT_READY(secrets: Path) -> None:
    """THE EXACT LIVE FAILURE. Both files exist, both are empty, and the old check called this
    READY because it only ever looked at filenames."""
    _write(secrets, "binance_live.json", {})
    _write(secrets, "binance_live_spot.json", {})
    row = G._keys_present()
    assert row["status"] != "READY"
    assert "missing or empty" in row["detail"]


def test_A_FILE_WITH_BLANK_VALUES_IS_NOT_READY(secrets: Path) -> None:
    """The keys are present as JSON fields and empty as strings -- which is what a half-finished
    paste leaves behind, and it reads as configured to anything that does not check the value."""
    _write(secrets, "binance_live.json", {"api_key": "", "api_secret": ""})
    _write(secrets, "binance_live_spot.json", {"api_key": "k", "api_secret": "s"})
    assert G._keys_present()["status"] != "READY"


def test_UNREADABLE_JSON_IS_NOT_READY(secrets: Path) -> None:
    """A truncated paste leaves a file that exists, parses as nothing, and is treated as absent by
    every reader while LOOKING configured."""
    (secrets / "binance_live.json").write_text("{not json", "utf-8")
    _write(secrets, "binance_live_spot.json", {"api_key": "k", "api_secret": "s"})
    row = G._keys_present()
    assert row["status"] != "READY" and "not valid JSON" in row["detail"]


def test_THE_FUTURES_LEG_ALONE_IS_NOT_READY(secrets: Path) -> None:
    """The futures leg without the spot leg is not half a cash-and-carry, it is an UNHEDGED
    DIRECTIONAL POSITION -- which is precisely what GAP #90 was opened for. A gate that accepted
    one leg would greenlight the failure the desk already paid to find."""
    _write(secrets, "binance_live.json", {"api_key": "k", "api_secret": "s"})
    row = G._keys_present()
    assert row["status"] != "READY"
    assert "binance_live_spot.json" in row["detail"]


def test_BOTH_LEGS_WITH_REAL_VALUES_IS_READY(secrets: Path) -> None:
    _write(secrets, "binance_live.json", {"api_key": "k", "api_secret": "s"})
    _write(secrets, "binance_live_spot.json", {"api_key": "k2", "api_secret": "s2"})
    row = G._keys_present()
    assert row["status"] == "READY"
    assert "both live legs" in row["detail"]


def test_UNRELATED_FILES_CANNOT_SATISFY_THE_GATE(secrets: Path) -> None:
    """The old check matched any filename containing "binance" or "api", so a README or a stale
    backup counted toward readiness. Only the two named files with usable fields do."""
    _write(secrets, "binance_notes_api.json", {"api_key": "k", "api_secret": "s"})
    _write(secrets, "binance_testnet.json", {"api_key": "k", "api_secret": "s"})
    assert G._keys_present()["status"] != "READY", "a non-live file satisfied a LIVE gate"


def test_THE_CHECK_ACTUALLY_OPENS_THE_FILES() -> None:
    """Structural: a filename-only check is the defect. If `glob` returns and nothing is parsed,
    the gate is green on existence again."""
    import inspect

    src = inspect.getsource(G._keys_present)
    assert "json.loads" in src, "the gate no longer reads credential CONTENTS"
    assert "read_text" in src
