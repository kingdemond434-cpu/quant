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


def _keyed_fetch(monkeypatch: pytest.MonkeyPatch, key: str, fail: Any) -> tuple[dict, list]:
    monkeypatch.setenv("QK_ASIA_KEY", key)
    monkeypatch.setattr(ac, "_robots_allows", lambda url, agent="": (True, "ok"))
    seen: list[str] = []

    def opened(self: Any, req: Any, data: Any = None, timeout: float = 0) -> Any:
        seen.append(req.full_url)
        raise fail(req.full_url)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", opened)
    rec = ac.collect_one({"id": "eia_energy", "access": "key", "key_env": "QK_ASIA_KEY",
                          "key_in": "query:api_key", "url": "https://api.eia.gov/v2/x/data/",
                          "expect": "json"})
    return rec, seen


def test_key_never_lands_in_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    rec, seen = _keyed_fetch(monkeypatch, "SECRET123", lambda u: OSError(f"refused {u}"))
    assert "SECRET123" in seen[0]
    assert "SECRET123" not in str(rec)


@pytest.mark.parametrize("fail", [lambda u: OSError(f"refused {u}"),
                                  lambda u: ValueError(f"unknown url type: {u!r}")])
def test_a_key_straddling_the_cut_leaves_no_prefix(monkeypatch: pytest.MonkeyPatch,
                                                   fail: Any) -> None:
    """Re-audit of #201: truncating to 90 chars BEFORE redacting kept 31 of 40 key chars."""
    key = "K" * 8 + "abcdefghijklmnopqrstuvwxyz012345"   # 40 chars, crosses char 90
    rec, _ = _keyed_fetch(monkeypatch, key, fail)
    why = rec["why"]
    assert key[:12] not in why and "KKKKKKKK" not in why


def test_an_encoded_key_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key with + / = travels url-encoded; scrubbing only the raw form left it whole."""
    key = "ab+cd/ef==gh"
    rec, seen = _keyed_fetch(monkeypatch, key, lambda u: OSError(f"refused {u}"))
    assert "ab%2Bcd%2Fef%3D%3Dgh" in seen[0]
    assert "ab%2Bcd" not in str(rec) and key not in str(rec)
