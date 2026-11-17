"""FRED/ALFRED are terms-refused (2026-11-13 ruling): these doors never contact stlouisfed.org."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
pytest.importorskip("requests")


def _no_request(*a: Any, **k: Any) -> None:
    raise AssertionError("a FRED request was made")


def _no_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_alfred no longer imports requests; the HTTP layers it could reach fail the test."""
    import urllib.request

    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", _no_request)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _no_request)


def test_fetch_alfred_main_is_blocked_and_never_requests(monkeypatch: pytest.MonkeyPatch,
                                                        tmp_path: Path) -> None:
    from research import fetch_alfred as fa
    assert not hasattr(fa, "requests"), "the dead network body and its import are gone"
    _no_transport(monkeypatch)
    monkeypatch.setattr(fa, "REPORTS", tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "dummy-not-a-key")
    assert fa.main(["DGS10"]) == 2
    import json
    rep = json.loads((tmp_path / "alfred_vintages.json").read_text(encoding="utf-8"))
    assert rep["status"] == "BLOCKED_ON_TERMS"
    assert rep["missed_growth"]["mechanism"] == "fred_terms_refusal"


def test_fetch_vintages_never_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import fetch_alfred as fa
    _no_transport(monkeypatch)
    assert fa.fetch_vintages("DGS10", "dummy-not-a-key") is None


def test_data_axis_miner_never_probes_the_fred_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import data_axis_miner as dam
    probed: list[str] = []

    def _probe(url: str) -> dict:
        probed.append(url)
        return {"reachable": True}

    monkeypatch.setattr(dam, "probe", _probe)
    dam.build(True)
    assert not [u for u in probed if "stlouisfed.org" in u]
