"""A robots "no" STOPS shadow_institutional's automated fetch (Auditor ruling 2026-11-18, #1335).

Disallowed, UNREAD (HTML served 200, 5xx) and hard stop (401/403/429/451) each leave the data URL
unrequested and record the reason in `Guard.robots_refused`; a real allow still fetches. Every
reply is a fake; nothing touches the network.
"""
from __future__ import annotations

import io
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_institutional as si  # type: ignore[import-not-found]  # noqa: E402

DATA_URL = "https://h.example/data/series"
REAL_ALLOW = "User-agent: *\nDisallow: /private/\n"
REAL_DENY = "User-agent: *\nDisallow: /data/\n"


class _Resp:
    def __init__(self, body: str, status: int = 200, ctype: str = "text/plain") -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = ctype
        self._b = body.encode("utf-8")

    def read(self, n: int = -1) -> bytes:
        return self._b if n < 0 else self._b[:n]

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_a: Any) -> None:
        return None


def _wire(monkeypatch: pytest.MonkeyPatch, *, body: str = "", status: int = 200,
          ctype: str = "text/plain") -> list[str]:
    """Fake urlopen: robots.txt answers as told, the data URL answers JSON. Returns the log."""
    opened: list[str] = []

    def _open(req: Any, *_a: Any, **_k: Any) -> Any:
        url = str(getattr(req, "full_url", req))
        opened.append(url)
        if url.endswith("/robots.txt"):
            if status >= 400:
                raise urllib.error.HTTPError(url, status, "x", Message(), io.BytesIO(b""))
            return _Resp(body, status, ctype)
        return _Resp('[{"d": "2026-11-17", "v": 1.0}]', 200, "application/json")

    monkeypatch.setattr(si.urllib.request, "urlopen", _open)
    return opened


@pytest.fixture(autouse=True)
def _robots_ledger_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stopped fetch is billed by the desk's robots gate; no test writes the real ledger."""
    from research import robots_gate as RG
    monkeypatch.setattr(RG, "LEDGER", tmp_path / "robots_set_aside.jsonl")
    monkeypatch.setattr(RG, "REPORT", tmp_path / "ROBOTS_SET_ASIDE.json")


def _sensor() -> Any:
    return si.Sensor(sensor_id="checked_sensor", latent="global_risk_appetite", what="x",
                     fetch_class="public_endpoint", source="x", cadence="daily",
                     pit_lag_days=0.0, machine_use_allowed=True, licence="", sign=1,
                     consumers=("US500",), url=DATA_URL, robots="checked")


@pytest.mark.parametrize("case", [
    {"body": REAL_DENY},                                              # disallowed
    {"body": "<!DOCTYPE html><html>challenge</html>"},                 # HTML served 200
    {"body": "x", "ctype": "text/html"},                               # HTML content type
    {"status": 403}, {"status": 429}, {"status": 401}, {"status": 451},  # hard stop
    {"status": 503},                                                   # unread
], ids=["disallowed", "html_body", "html_ctype", "403", "429", "401", "451", "503"])
def test_a_robots_no_sends_no_data_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                           case: dict[str, Any]) -> None:
    opened = _wire(monkeypatch, **case)
    guard = si.Guard(budget_s=5.0, no_fetch=False, fixtures=tmp_path)
    payload, why = guard.get(_sensor())
    assert payload is None and why.startswith("refused by robots")
    assert DATA_URL not in opened, "a robots 'no' must stop the data request"
    assert opened == ["https://h.example/robots.txt"]
    assert guard.robots_refused == [{"sensor": "checked_sensor", "why": why}]
    assert guard.refused == []
    (row,) = guard.set_aside
    assert row["status"] == "SET_ASIDE" and row["billed"] is True and row["reopen"]


def test_a_transport_failure_on_robots_is_unread_and_stops(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    opened: list[str] = []

    def _open(req: Any, *_a: Any, **_k: Any) -> Any:
        opened.append(str(getattr(req, "full_url", req)))
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(si.urllib.request, "urlopen", _open)
    payload, why = si.Guard(budget_s=5.0, no_fetch=False, fixtures=tmp_path).get(_sensor())
    assert payload is None and why.startswith("refused by robots")
    assert opened == ["https://h.example/robots.txt"]


@pytest.mark.parametrize("case", [{"body": REAL_ALLOW}, {"status": 404}],
                         ids=["real_allow", "no_file_404"])
def test_a_real_allow_still_fetches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                    case: dict[str, Any]) -> None:
    opened = _wire(monkeypatch, **case)
    guard = si.Guard(budget_s=5.0, no_fetch=False, fixtures=tmp_path)
    payload, why = guard.get(_sensor())
    assert opened == ["https://h.example/robots.txt", DATA_URL]
    assert payload == [{"d": "2026-11-17", "v": 1.0}] and why.startswith("fetched")
    assert guard.robots_refused == []


def test_a_sensor_with_robots_unset_still_obeys_a_disallow(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`robots` left at its "api" default is no exemption: every wire fetch reads robots."""
    opened = _wire(monkeypatch, body=REAL_DENY)
    sensor = si.Sensor(sensor_id="api_sensor", latent="global_risk_appetite", what="x",
                       fetch_class="public_endpoint", source="x", cadence="daily",
                       pit_lag_days=0.0, machine_use_allowed=True, licence="", sign=1,
                       consumers=("US500",), url=DATA_URL)
    assert sensor.robots == "api"
    guard = si.Guard(budget_s=5.0, no_fetch=False, fixtures=tmp_path)
    payload, why = guard.get(sensor)
    assert payload is None and why.startswith("refused by robots")
    assert opened == ["https://h.example/robots.txt"], "no data request past a Disallow"
    assert guard.robots_refused == [{"sensor": "api_sensor", "why": why}]


def test_the_fixture_path_reads_no_robots(monkeypatch: pytest.MonkeyPatch,
                                          tmp_path: Path) -> None:
    opened = _wire(monkeypatch, body=REAL_DENY)
    payload, why = si.Guard(no_fetch=True, fixtures=tmp_path).get(_sensor())
    assert payload is None and "no fixture" in why and opened == []
