"""libs.ops.token_refresh: short-lived tokens minted from long-lived env credentials.

Every HTTP call is mocked; nothing here touches the network.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import token_refresh as T  # noqa: E402

NOW = 1_800_000_000.0
PASSWORD = "hunter2-very-secret-pw"
CLIENT_SECRET = "cdse-client-secret-xyz"


def _jwt(exp: float) -> str:
    def b(d: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b({'exp': exp})}.sig"


class FakeHTTP:
    def __init__(self, responses: list[tuple[int, dict[str, Any] | None]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, bytes | None]] = []

    def __call__(self, method: str, url: str, data: bytes | None, headers: dict[str, str],
                 timeout: float) -> tuple[int, bytes]:
        self.calls.append((method, url, data))
        code, doc = self.responses.pop(0)
        return code, (json.dumps(doc).encode() if doc is not None else b"")


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "token_cache"
    monkeypatch.setenv("QUANT_TOKEN_CACHE_DIR", str(d))
    for p in T.PROVIDERS.values():
        monkeypatch.delenv(p.short_env, raising=False)
        for g in p.long_envs:
            for k in g:
                monkeypatch.delenv(k, raising=False)
    return d


def _fake(monkeypatch: pytest.MonkeyPatch, responses: list[tuple[int, dict[str, Any] | None]]
          ) -> FakeHTTP:
    f = FakeHTTP(responses)
    monkeypatch.setattr(T, "_http", f)
    return f


CDSE_ENV = {"CDSE_USERNAME": "me@example.org", "CDSE_PASSWORD": PASSWORD}


def test_fresh_mint_cdse_password_grant(monkeypatch: pytest.MonkeyPatch, _cache: Path) -> None:
    tok = _jwt(NOW + 600)
    f = _fake(monkeypatch, [(200, {"access_token": tok, "expires_in": 600})])
    r = T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW)
    assert r.ok and r.source == "minted" and r.token == tok
    assert r.expires_at == NOW + 600
    method, url, data = f.calls[0]
    assert method == "POST" and url == T.CDSE_ENDPOINT
    assert data is not None and b"grant_type=password" in data and b"client_id=cdse-public" in data
    if os.name == "posix":
        mode = stat.S_IMODE((_cache / "cdse.json").stat().st_mode)
        assert mode == 0o600
    rep = {row["env"]: row for row in T.status_report(CDSE_ENV)}["CDSE_TOKEN"]
    assert rep["long_lived_present"] and rep["last_status"] == "OK"
    assert rep["cached_expires_at"] == NOW + 600


def test_cdse_client_credentials_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [(200, {"access_token": "abc.def", "expires_in": 600})])
    env = {"CDSE_CLIENT_ID": "cid", "CDSE_CLIENT_SECRET": CLIENT_SECRET, **CDSE_ENV}
    assert T.get_token("CDSE_TOKEN", environ=env, now=NOW).ok
    assert f.calls[0][2] is not None and b"grant_type=client_credentials" in f.calls[0][2]


def test_cache_hit_makes_no_call(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [(200, {"access_token": "t1.x.y", "expires_in": 600})])
    assert T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW).source == "minted"
    r = T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW + 300)
    assert r.ok and r.source == "cache" and r.token == "t1.x.y"
    assert len(f.calls) == 1


def test_expiry_remints(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [(200, {"access_token": "t1.x.y", "expires_in": 600}),
                            (200, {"access_token": "t2.x.y", "expires_in": 600})])
    T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW)
    # inside the safety margin counts as expired
    r = T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW + 600 - T.SAFETY_S + 1)
    assert r.ok and r.source == "minted" and r.token == "t2.x.y"
    assert len(f.calls) == 2


def test_missing_credential_is_blocked_on_key(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [])
    for env in T.MANAGED:
        r = T.get_token(env, environ={}, now=NOW)
        assert r.status == T.BLOCKED_ON_KEY and not r.ok and r.token is None
    assert f.calls == []


def test_http_401_is_refresh_failed_and_secret_free(monkeypatch: pytest.MonkeyPatch,
                                                    caplog: pytest.LogCaptureFixture,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    caplog.set_level(logging.DEBUG)
    _fake(monkeypatch, [(401, None)])
    env = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}
    r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
    assert r.status == T.REFRESH_FAILED and r.http == 401
    blob = repr(r) + r.detail + caplog.text + "".join(capsys.readouterr())
    blob += json.dumps(T.status_report(env))
    assert PASSWORD not in blob


def test_myfxbook_error_true_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [(200, {"error": True, "message": "Invalid login", "session": ""})])
    env = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}
    r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
    assert r.status == T.REFRESH_FAILED and r.http == 200


def test_network_exception_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> tuple[int, bytes]:
        raise OSError(f"connect failed for password={PASSWORD}")
    monkeypatch.setattr(T, "_http", boom)
    r = T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW)
    assert r.status == T.REFRESH_FAILED and PASSWORD not in r.detail


def test_token_never_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [(200, {"error": False, "session": "SESS%2Bsecret123"})])
    env = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}
    r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
    assert r.ok and r.token == "SESS+secret123"
    assert "secret123" not in repr(r)
    url, _ = T.apply_to_request(r, "https://www.myfxbook.com/api/get-community-outlook.json", {})
    assert url.endswith("session=SESS%2Bsecret123")


def test_jquants_v1_mint_and_v2_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    idt = _jwt(NOW + 86400)
    f = _fake(monkeypatch, [(200, {"refreshToken": "rt-abc"}), (200, {"idToken": idt})])
    env = {"JQUANTS_MAILADDRESS": "me@example.org", "JQUANTS_PASSWORD": PASSWORD}
    r = T.get_token("JQUANTS_TOKEN", environ=env, now=NOW)
    assert r.ok and r.token == idt and r.expires_at == NOW + 86400
    assert f.calls[0][1].endswith("/v1/token/auth_user")
    assert "/v1/token/auth_refresh?refreshtoken=" in f.calls[1][1]
    _, hdr = T.apply_to_request(r, "https://api.jquants.com/v1/markets/trades_spec", {})
    assert hdr["Authorization"] == f"Bearer {idt}"
    # V2: a non-expiring API key needs no call and goes in x-api-key
    k = T.get_token("JQUANTS_TOKEN", environ={"JQUANTS_API_KEY": "k-123456"}, now=NOW)
    assert k.ok and k.source == "api_key"
    _, hdr = T.apply_to_request(k, "https://api.jquants.com/v2/equities/bars/daily", {})
    assert hdr == {"x-api-key": "k-123456"}


def test_pasted_env_wins_and_expired_jwt_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [(200, {"access_token": "new.x.y", "expires_in": 600})])
    live = _jwt(NOW + 600)
    r = T.get_token("CDSE_TOKEN", environ={"CDSE_TOKEN": live}, now=NOW)
    assert r.ok and r.source == "env" and r.token == live and f.calls == []
    dead = _jwt(NOW - 10)
    r = T.get_token("CDSE_TOKEN", environ={"CDSE_TOKEN": dead}, now=NOW)
    assert r.status == T.BLOCKED_ON_KEY
    r = T.get_token("CDSE_TOKEN", environ={"CDSE_TOKEN": dead, **CDSE_ENV}, now=NOW)
    assert r.ok and r.source == "minted"
    # an opaque pasted value (no JWT exp) is used as-is, as before
    r = T.get_token("MYFXBOOK_SESSION", environ={"MYFXBOOK_SESSION": "opaque"}, now=NOW)
    assert r.ok and r.source == "env"


def test_token_only_sent_to_provider_hosts() -> None:
    r = T.TokenResult(T.OK, "JQUANTS_TOKEN", token="tok", source="env", apply="bearer")
    url, hdr = T.apply_to_request(r, "https://jpx-jquants.com/", {"A": "b"})
    assert url == "https://jpx-jquants.com/" and hdr == {"A": "b"}


def test_invalidate_drops_cached_token(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [(200, {"access_token": "t1.x.y", "expires_in": 600}),
                            (200, {"access_token": "t2.x.y", "expires_in": 600})])
    T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW)
    T.invalidate("CDSE_TOKEN")
    assert T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW + 1).source == "minted"
    assert len(f.calls) == 2


def test_collector_uses_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """asia_collector.collect_one reads the helper, never the env var, for managed keys, and
    never records the session in the row's url."""
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import asia_collector as C

    src = {"id": "myfxbook_outlook", "access": "key", "key_env": "MYFXBOOK_SESSION",
           "url": "https://www.myfxbook.com/api/get-community-outlook.json", "expect": "json"}
    rec = C.collect_one(src)
    assert rec["status"] == "UNCONFIGURED" and rec["token_status"] == T.BLOCKED_ON_KEY

    monkeypatch.setattr(T, "get_token", lambda env, **k: T.TokenResult(
        T.OK, env, token="SESSIONSECRET", source="cache", apply="query:session"))
    monkeypatch.setattr(C, "_robots_allows", lambda url, agent="": (True, "stub"))
    sent: list[str] = []

    def fake_open(req: Any, timeout: float = 0, context: Any = None) -> Any:
        sent.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(T, "invalidate", lambda env: None)
    rec = C.collect_one(src)
    assert sent and "session=SESSIONSECRET" in sent[0]
    assert rec["status"] == "HTTP_ERROR" and "SESSIONSECRET" not in json.dumps(rec)
