"""asia_collector: paid sources are refused by rule, and a declared key reaches the request
without ever reaching the recorded row (audit of #201, 2026-10-06)."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "desks" / "mt5" / "research"), str(ROOT / "desks" / "mt5")]

import asia_collector as ac  # noqa: E402


def test_paid_source_is_refused_even_with_its_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIANYANCHA_TOKEN", "set-on-the-box")
    called: list[Any] = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: called.append(a))
    rec = ac.collect_one({"id": "tianyancha_supply", "access": "paid",
                          "key_env": "TIANYANCHA_TOKEN", "url": "https://open.tianyancha.com/"})
    assert rec["status"] == "BLOCKED_PAID"
    assert not called


def test_login_cookie_source_reads_unconfigured_even_when_set(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAIDU_INDEX_COOKIE", "cookie")
    rec = ac.collect_one({"id": "baidu_index", "access": "key",
                          "key_env": "BAIDU_INDEX_COOKIE", "url": "https://index.baidu.com/"})
    assert rec["status"] == "UNCONFIGURED"


@pytest.mark.parametrize(("place", "check"), [
    ("query:api_key", lambda url, h: "api_key=SECRET123" in url),
    ("header:Bmx-Token", lambda url, h: h.get("Bmx-Token") == "SECRET123"),
    ("bearer", lambda url, h: h.get("Authorization") == "Bearer SECRET123"),
])
def test_declared_key_placement(monkeypatch: pytest.MonkeyPatch, place: str, check: Any) -> None:
    monkeypatch.setenv("QK_ASIA_KEY", "SECRET123")
    url, headers, key = ac._apply_key({"key_env": "QK_ASIA_KEY", "key_in": place},
                                      "https://api.example/v1/data", {})
    assert check(url, headers)
    assert key == "SECRET123"


def test_no_declaration_sends_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_ASIA_KEY", "SECRET123")
    url, headers, key = ac._apply_key({"key_env": "QK_ASIA_KEY"}, "https://x/", {})
    assert (url, headers, key) == ("https://x/", {}, "")


def test_key_never_lands_in_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_ASIA_KEY", "SECRET123")
    monkeypatch.setattr(ac, "_robots_allows", lambda url, agent="": (True, "ok"))
    seen: list[str] = []

    def boom(req: Any, timeout: float = 0, context: Any = None) -> Any:
        seen.append(req.full_url)
        raise OSError(f"refused {req.full_url}")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    rec = ac.collect_one({"id": "eia_energy", "access": "key", "key_env": "QK_ASIA_KEY",
                          "key_in": "query:api_key", "url": "https://api.eia.gov/v2/x/data/",
                          "expect": "json"})
    assert "SECRET123" in seen[0]
    assert "SECRET123" not in str(rec)
