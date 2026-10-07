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
import urllib.parse
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


@pytest.fixture
def myfx_unfenced(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the Myfxbook code path as it would run AFTER its terms were confirmed, so the
    secrecy of that path is pinned now, while the shipped fence keeps it closed."""
    monkeypatch.setitem(T.TERMS, "myfxbook", ("confirmed", "test-only"))


@pytest.fixture
def jq_unfenced(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the J-Quants code path as it would run AFTER its terms were confirmed (they are
    to_confirm: art. 8 limits use to the registered individual's private use)."""
    monkeypatch.setitem(T.TERMS, "jquants", ("confirmed", "test-only"))


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


def test_missing_credential_is_blocked_on_key(monkeypatch: pytest.MonkeyPatch,
                                              myfx_unfenced: None, jq_unfenced: None) -> None:
    f = _fake(monkeypatch, [])
    for env in T.MANAGED:
        r = T.get_token(env, environ={}, now=NOW)
        assert r.status == T.BLOCKED_ON_KEY and not r.ok and r.token is None
    assert f.calls == []


def test_http_401_is_refresh_failed_and_secret_free(monkeypatch: pytest.MonkeyPatch,
                                                    caplog: pytest.LogCaptureFixture,
                                                    capsys: pytest.CaptureFixture[str],
                                                    myfx_unfenced: None) -> None:
    caplog.set_level(logging.DEBUG)
    _fake(monkeypatch, [(401, None)])
    env = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}
    r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
    assert r.status == T.REFRESH_FAILED and r.http == 401
    blob = repr(r) + r.detail + caplog.text + "".join(capsys.readouterr())
    blob += json.dumps(T.status_report(env))
    assert PASSWORD not in blob


def test_myfxbook_error_true_on_200(monkeypatch: pytest.MonkeyPatch,
                                    myfx_unfenced: None) -> None:
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


def test_token_never_in_repr(monkeypatch: pytest.MonkeyPatch, myfx_unfenced: None) -> None:
    _fake(monkeypatch, [(200, {"error": False, "session": "SESS%2Bsecret123"})])
    env = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}
    r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
    assert r.ok and r.token == "SESS+secret123"
    assert "secret123" not in repr(r)
    url, _ = T.apply_to_request(r, "https://www.myfxbook.com/api/get-community-outlook.json", {})
    assert url.endswith("session=SESS%2Bsecret123")


def test_jquants_v1_mint_and_v2_api_key(monkeypatch: pytest.MonkeyPatch,
                                        jq_unfenced: None) -> None:
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


def test_pasted_env_wins_and_expired_jwt_falls_through(monkeypatch: pytest.MonkeyPatch,
                                                       myfx_unfenced: None) -> None:
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


def test_collector_uses_helper(monkeypatch: pytest.MonkeyPatch, myfx_unfenced: None) -> None:
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

    def fake_open(self: Any, req: Any, data: Any = None, timeout: float = 0) -> Any:
        sent.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, None)  # type: ignore[arg-type]
    # a keyed request goes through the credential-safe opener (#201's keyed_opener)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    monkeypatch.setattr(T, "invalidate", lambda env: None)
    rec = C.collect_one(src)
    assert sent and "session=SESSIONSECRET" in sent[0]
    assert rec["status"] == "HTTP_ERROR" and "SESSIONSECRET" not in json.dumps(rec)


# ---------------------------------------------------------------------------------------------
# security audit of #218 (2026-10-06)
# ---------------------------------------------------------------------------------------------

MYFX_ENV = {"MYFXBOOK_EMAIL": "me@example.org", "MYFXBOOK_PASSWORD": PASSWORD}


def _collector() -> Any:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import asia_collector as C
    return C


def test_failed_refresh_is_blocked_auth_not_unconfigured(monkeypatch: pytest.MonkeyPatch,
                                                         jq_unfenced: None) -> None:
    _fake(monkeypatch, [(401, None)])
    r = T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW)
    assert r.status == T.REFRESH_FAILED and T.collector_status(r) == T.BLOCKED_AUTH
    rep = {row["env"]: row for row in T.status_report(CDSE_ENV)}["CDSE_TOKEN"]
    assert rep["status"] == T.BLOCKED_AUTH
    # a truly absent credential, and only that, is UNCONFIGURED
    absent = T.get_token("JQUANTS_TOKEN", environ={}, now=NOW)
    assert T.collector_status(absent) == T.UNCONFIGURED
    assert {row["env"]: row for row in T.status_report({})}["JQUANTS_TOKEN"]["status"] \
        == T.UNCONFIGURED

    C = _collector()
    monkeypatch.setattr(T, "get_token", lambda env, **k: T.TokenResult(
        T.REFRESH_FAILED, env, http=401, detail="CDSE token endpoint answered HTTP 401"))
    rec = C.collect_one({"id": "copernicus_s5p", "access": "key", "key_env": "CDSE_TOKEN",
                         "url": "https://catalogue.dataspace.copernicus.eu/stac",
                         "expect": "json"})
    assert rec["status"] == "BLOCKED_AUTH" and rec["token_http"] == 401


def test_myfxbook_is_fenced_on_terms_and_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fake(monkeypatch, [])
    for env in (MYFX_ENV, {"MYFXBOOK_SESSION": "pasted-session"}):
        r = T.get_token("MYFXBOOK_SESSION", environ=env, now=NOW)
        assert r.status == T.BLOCKED_ON_TERMS and r.token is None
    assert f.calls == []
    assert T.TERMS["myfxbook"][0] != "confirmed"
    rep = {row["env"]: row for row in T.status_report(MYFX_ENV)}["MYFXBOOK_SESSION"]
    assert rep["status"] == T.BLOCKED_ON_TERMS

    C = _collector()
    opened: list[Any] = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: opened.append(a))
    monkeypatch.setattr(urllib.request.OpenerDirector, "open",
                        lambda *a, **k: opened.append(a))
    rec = C.collect_one({"id": "myfxbook_outlook", "access": "key",
                         "key_env": "MYFXBOOK_SESSION", "expect": "json",
                         "url": "https://www.myfxbook.com/api/get-community-outlook.json"})
    assert rec["status"] == "BLOCKED_ON_TERMS" and not opened


def test_terms_evidence_is_recorded_for_every_fenced_provider() -> None:
    for name, (verdict, _note) in T.TERMS.items():
        ev = T.TERMS_EVIDENCE[name]
        assert ev["terms_url"].startswith("https://") and len(ev["terms_quote"]) > 20
        assert ev["checked_at"]
        assert T.terms_ok(T.PROVIDERS[{"cdse": "CDSE_TOKEN", "jquants": "JQUANTS_TOKEN",
                                       "myfxbook": "MYFXBOOK_SESSION"}[name]]) == (
            verdict in T.PERMITTED_VERDICTS)
    assert T.TERMS["cdse"][0] == "confirmed"
    # the clause that scopes the portal's non-commercial sentence away from Sentinel data
    cdse = T.TERMS_EVIDENCE["cdse"]
    assert cdse["scope_url"].startswith("https://dataspace.copernicus.eu/")
    assert cdse["scope_quote"].startswith("Any other contents of the Copernicus Data Space")


def test_every_managed_provider_is_terms_listed() -> None:
    """No managed provider is unfenced by omission."""
    assert {p.name for p in T.PROVIDERS.values()} <= set(T.TERMS)


def test_unknown_provider_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider absent from TERMS is BLOCKED_ON_TERMS, never a silent pass."""
    p = T.Provider(name="newcomer", short_env="NEWCOMER_TOKEN", long_envs=(("NEWCOMER_KEY",),),
                   apply="bearer", hosts=("api.example.org",), docs="https://example.org")
    assert "newcomer" not in T.TERMS and not T.terms_ok(p)
    monkeypatch.setitem(T.PROVIDERS, "NEWCOMER_TOKEN", p)
    f = _fake(monkeypatch, [])
    r = T.get_token("NEWCOMER_TOKEN", environ={"NEWCOMER_TOKEN": "tok-abc",
                                               "NEWCOMER_KEY": "k"}, now=NOW)
    assert r.status == T.BLOCKED_ON_TERMS and r.token is None and not f.calls
    row = {x["env"]: x for x in T.status_report({"NEWCOMER_KEY": "k"})}["NEWCOMER_TOKEN"]
    assert row["status"] == T.BLOCKED_ON_TERMS and row["terms"] == "unlisted"
    # confirmed WITHOUT recorded evidence is still not ok
    monkeypatch.setitem(T.TERMS, "newcomer", ("confirmed", "no evidence"))
    assert not T.terms_ok(p)


def test_jquants_is_permitted_for_private_use_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The principal answered the art. 8 question on 2026-10-06 (private use by the registered
    individual): J-Quants is permitted, and only under its recorded private-use condition."""
    assert T.TERMS["jquants"][0] == T.PRIVATE_USE
    ev = T.TERMS_EVIDENCE["jquants"]
    assert ev["terms_url"] == "https://jpx-jquants.com/termsofservice"
    assert "私的使用の目的に限ります" in ev["terms_quote"]
    assert ev["principal_message_id"].startswith("cmsg_")
    assert ev["principal_answered_at"] == "2026-10-06T21:11:56Z"
    assert "no redistribution" in ev["condition"] and "no sharing" in ev["condition"]
    r = T.get_token("JQUANTS_TOKEN", environ={"JQUANTS_API_KEY": "k-123456"}, now=NOW)
    assert r.ok and r.private_use and r.apply == "x-api-key"
    row = {x["env"]: x for x in T.status_report({})}["JQUANTS_TOKEN"]
    assert row["private_use"] is True and row["terms"] == T.PRIVATE_USE
    # a private-use verdict without its recorded condition is not a permission
    monkeypatch.setitem(T.TERMS_EVIDENCE, "jquants", {k: v for k, v in ev.items()
                                                      if k != "condition"})
    assert not T.terms_ok(T.PROVIDERS["JQUANTS_TOKEN"])
    # and no other provider is private-use by accident
    assert not T.get_token("CDSE_TOKEN", environ={}, now=NOW).private_use


def test_jquants_permitting_clause_and_conditions_are_recorded(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit of #218 (2026-10-07): the clause that PERMITS the use is recorded verbatim with its
    URL, its conditions are structured fields, the stale BLOCKED_ON_TERMS note is gone, and the
    principal's approval is stored with the question it answered."""
    ev = T.TERMS_EVIDENCE["jquants"]
    assert ev["permitting_url"] == "https://jpx-jquants.com/en/help/usage"
    assert "own investment analysis, portfolio management" in ev["permitting_quote"]
    assert ev["permitting_quote_source"] in ("fetched_2026-10-07", "quoted_via_audit")
    assert "scope_note" not in ev and "BLOCKED_ON_TERMS" not in json.dumps(ev)
    assert "private use by the registered individual" in ev["principal_question"]
    assert ev["principal_answer"].endswith("yes fr j quants")
    assert ev["principal_answered_by"] == "zuck"
    c = T.TERMS_CONDITIONS["jquants"]
    assert c["corporate_use_permitted"] is False
    assert any("not reused for training" in x for x in c["ai_use"]["permitted_only_if"])
    assert any("not distributed or published" in x for x in c["ai_use"]["permitted_only_if"])
    assert c["repeated_publishing_is_personal_use"] is False
    assert c["delete_on_cancellation"] is True and "copies" in c["delete_on_cancellation_quote"]
    assert c["lineage"] == T.PRIVATE_LINEAGE and c["e8_eligible"] is False
    # the structured conditions are part of the permission: without them it is not one
    monkeypatch.delitem(T.TERMS_CONDITIONS, "jquants")
    assert not T.terms_ok(T.PROVIDERS["JQUANTS_TOKEN"])


def test_private_lineage_is_seen_at_any_depth() -> None:
    cell = T.mark_private_lineage({"family": "x"})
    assert cell["lineage"] == T.PRIVATE_LINEAGE and cell[T.E8_INELIGIBLE] is True
    assert T.has_private_lineage({"spec": {"parents": [cell]}})
    assert T.has_private_lineage({"lineages": [T.PRIVATE_LINEAGE]})
    assert not T.has_private_lineage({"spec": {"family": "carry", "private_use": False}})


def test_cdse_attribution_duty_rides_on_every_record(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    """The Sentinel Data Legal Notice requires the source notice on anything communicated or
    distributed; the desk adapts the data, so the 'Contains modified' form is carried."""
    ev = T.TERMS_EVIDENCE["cdse"]
    assert ev["attribution"] == "Contains modified Copernicus Sentinel data {year}"
    assert ev["attribution_unmodified"] == "Copernicus Sentinel data {year}"
    assert "Contains modified Copernicus Sentinel data [Year]" in ev["attribution_quote"]
    assert ev["attribution_url"].startswith("https://sentinels.copernicus.eu/")
    assert T.attribution("CDSE_TOKEN", 2026) == "Contains modified Copernicus Sentinel data 2026"
    assert T.attribution("cdse", 2025).endswith(" 2025")
    assert T.attribution("JQUANTS_TOKEN") == "" and T.attribution("MYFXBOOK_SESSION") == ""

    year = __import__("time").gmtime(NOW).tm_year
    want = f"Contains modified Copernicus Sentinel data {year}"
    # every TokenResult on the CDSE path carries it -- minted, blocked or failed alike
    _fake(monkeypatch, [(200, {"access_token": _jwt(NOW + 600), "expires_in": 600})])
    assert T.get_token("CDSE_TOKEN", environ=CDSE_ENV, now=NOW).attribution == want
    assert T.get_token("CDSE_TOKEN", environ={}, now=NOW).attribution == want
    assert T.get_token("JQUANTS_TOKEN", environ={}, now=NOW).attribution == ""
    assert {x["env"]: x for x in T.status_report({})}["CDSE_TOKEN"]["attribution"]

    # the collector's row and its vault meta carry it on a collected CDSE source
    C = _collector()
    monkeypatch.setattr(C, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(C, "SERIES", tmp_path / "series")
    monkeypatch.setattr(T, "get_token", lambda e, **k: T.TokenResult(
        T.OK, e, token="cdse-bearer-abc", source="cache", attribution=want))
    monkeypatch.setattr(C, "_robots_allows", lambda u, agent="": (True, "stub"))
    monkeypatch.setattr(urllib.request.OpenerDirector, "open",
                        lambda self, req, data=None, timeout=0: _Resp(b'{"type": "Catalog"}'))
    rec = C.collect_one({"id": "copernicus_s5p", "access": "key", "key_env": "CDSE_TOKEN",
                         "url": "https://catalogue.dataspace.copernicus.eu/stac",
                         "expect": "json"})
    assert rec["status"] == "COLLECTED" and rec["attribution"] == want
    meta = json.loads(next((tmp_path / "vault" / "copernicus_s5p").glob("*.meta.json"))
                      .read_text(encoding="utf-8"))
    assert meta["attribution"] == want
    assert C.report_doc([rec], 1, __import__("collections").Counter())["rows"][0][
        "attribution"] == want


class _Resp:
    """A minimal urllib response for the collector's fake transport."""

    def __init__(self, body: bytes, ctype: str = "application/json") -> None:
        self.status = 200
        self.headers = {"Content-Type": ctype}
        self._body = body

    def read(self, n: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


def test_credentials_come_from_read_key_not_os_environ(monkeypatch: pytest.MonkeyPatch,
                                                       jq_unfenced: None) -> None:
    """The default credential source is read_key (#201): a value only the machine registry
    holds (setx /M after the task started) is seen, and os.environ is never consulted."""
    from libs.ops import env_secret
    machine = {"CDSE_USERNAME": "me@example.org", "CDSE_PASSWORD": PASSWORD}
    monkeypatch.setattr(env_secret, "_registry",
                        lambda hive, name: machine.get(name) if hive == "machine" else None)
    monkeypatch.setattr(os, "environ", {"QUANT_TOKEN_CACHE_DIR":
                                        os.environ["QUANT_TOKEN_CACHE_DIR"]})
    f = _fake(monkeypatch, [(200, {"access_token": "m.x.y", "expires_in": 600})])
    r = T.get_token("CDSE_TOKEN", now=NOW)
    assert r.ok and r.source == "minted"
    assert f.calls[0][2] is not None and b"me%40example.org" in f.calls[0][2]
    assert PASSWORD not in T.scrub(f"echo {PASSWORD}")

    # a fake key source through the read_key seam
    fake = {"JQUANTS_API_KEY": "fake-v2-key"}
    monkeypatch.setattr(T, "_read_key", lambda name: fake.get(name, ""))
    k = T.get_token("JQUANTS_TOKEN", now=NOW)
    assert k.ok and k.source == "api_key" and k.apply == "x-api-key"


def test_collector_non_managed_key_uses_read_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import env_keys
    C = _collector()
    monkeypatch.delenv("QK_FAKE_KEY", raising=False)
    monkeypatch.setattr(env_keys, "read_key", lambda name, default="", **k:
                        "v" if name == "QK_FAKE_KEY" else default)
    assert C._key_present({"key_env": "QK_FAKE_KEY"})
    assert not C._key_present({"key_env": "QK_OTHER"})


@pytest.mark.parametrize("url", [
    "https://www.myfxbook.com/api/login.json?email=me%40example.org&password=" + PASSWORD,
    "https://u:" + PASSWORD + "@host.example/x?a=1",
    "https://api.example/x?session=" + PASSWORD + "&symbol=EURUSD",
    "https://api.example/x?refreshtoken=" + PASSWORD,
])
def test_recorded_urls_carry_no_query_credential(url: str) -> None:
    out = T.strip_url_credentials(url)
    assert PASSWORD not in out and "me%40example.org" not in out
    assert T.scrub(f"ValueError: unknown url type: {url!r}", env={}).count(PASSWORD) == 0


def test_myfxbook_login_url_never_reaches_a_record(monkeypatch: pytest.MonkeyPatch,
                                                   myfx_unfenced: None, _cache: Path,
                                                   caplog: pytest.LogCaptureFixture) -> None:
    """Even unfenced, the GET login URL (password in its query) never reaches a detail, the
    cache or a log, whatever the transport raises."""
    caplog.set_level(logging.DEBUG)
    for exc in (OSError, ValueError, urllib.error.URLError):
        def boom(method: str, url: str, *a: Any, _e: Any = exc) -> tuple[int, bytes]:
            raise _e(f"failed {url}")
        monkeypatch.setattr(T, "_http", boom)
        r = T.get_token("MYFXBOOK_SESSION", environ=MYFX_ENV, now=NOW)
        assert r.status == T.REFRESH_FAILED
        blob = r.detail + repr(r) + caplog.text
        blob += "".join(p.read_text() for p in _cache.glob("*.json"))
        assert PASSWORD not in blob and "password=" not in blob


def _managed_fetch(monkeypatch: pytest.MonkeyPatch, token: str, fail: Any,
                   env: str = "JQUANTS_TOKEN", apply: str = "x-api-key",
                   url: str = "https://api.jquants.com/v2/equities/investor-types"
                   ) -> tuple[dict[str, Any], list[Any]]:
    C = _collector()
    monkeypatch.setattr(T, "get_token", lambda e, **k: T.TokenResult(
        T.OK, e, token=token, source="api_key", apply=apply))
    monkeypatch.setattr(C, "_robots_allows", lambda u, agent="": (True, "stub"))
    seen: list[Any] = []

    def opened(self: Any, req: Any, data: Any = None, timeout: float = 0) -> Any:
        seen.append(req)
        raise fail(req)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", opened)
    rec = C.collect_one({"id": "jpx_jquants", "access": "key", "key_env": env,
                         "url": url, "expect": "json"})
    return rec, seen


TOKEN40 = "TKN" + "abcdefghijklmnopqrstuvwxyz0123456789Q"


@pytest.mark.parametrize("pad", [0, 30, 60, 70, 75, 80, 85, 88, 89, 90, 95, 120])
@pytest.mark.parametrize("kind", [OSError, TimeoutError, RuntimeError, ValueError])
def test_token_at_any_position_never_survives_the_cut(monkeypatch: pytest.MonkeyPatch,
                                                      pad: int, kind: Any) -> None:
    """Scrub first, truncate after: a token at any offset, including one straddling char 90,
    leaves no fragment in the row (UNREACHABLE and UNMEASURED branches alike)."""
    rec, _ = _managed_fetch(monkeypatch, TOKEN40, lambda req: kind("x" * pad + TOKEN40 + " tail"))
    why = rec["why"]
    assert rec["status"] in ("UNREACHABLE", "UNMEASURED")
    assert len(why) <= 90
    for i in range(len(TOKEN40) - 5):
        assert TOKEN40[i:i + 6] not in why, (pad, why)
    assert TOKEN40 not in json.dumps(rec)


def test_session_in_a_raised_url_never_reaches_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    rec, seen = _managed_fetch(
        monkeypatch, "SESSIONSECRET", lambda req: ValueError(f"unknown url type: {req.full_url}"),
        env="MYFXBOOK_SESSION", apply="query:session",
        url="https://www.myfxbook.com/api/get-community-outlook.json")
    assert "session=SESSIONSECRET" in seen[0].full_url
    assert "SESSIONSECRET" not in json.dumps(rec)


def test_jquants_v2_key_attaches_to_the_real_api_call(monkeypatch: pytest.MonkeyPatch,
                                                      jq_unfenced: None) -> None:
    """The registry row points at the V2 API (not the landing page), and the API key read from a
    fake key source rides as `x-api-key` on that call -- never in the url or the row."""
    rows = json.loads((ROOT / "desks/mt5/data/asia_sources.json").read_text(encoding="utf-8"))
    row = next(r for r in rows["sources"] if r.get("id") == "jpx_jquants")
    assert row["url"].startswith("https://api.jquants.com/v2/")
    fake = {"JQUANTS_API_KEY": "fake-v2-key-123456"}
    monkeypatch.setattr(T, "_read_key", lambda name: fake.get(name, ""))
    C = _collector()
    monkeypatch.setattr(C, "_robots_allows", lambda u, agent="": (True, "stub"))
    seen: list[Any] = []

    def opened(self: Any, req: Any, data: Any = None, timeout: float = 0) -> Any:
        seen.append(req)
        raise urllib.error.HTTPError(req.full_url, 503, "busy", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", opened)
    rec = C.collect_one(dict(row))
    assert seen, "no request was sent"
    req = seen[0]
    assert urllib.parse.urlsplit(req.full_url).hostname == "api.jquants.com"
    assert req.get_header("X-api-key") == "fake-v2-key-123456"
    assert "fake-v2-key" not in req.full_url and "fake-v2-key" not in json.dumps(rec)
    assert rec["status"] == "HTTP_ERROR" and rec["http"] == 503
    # a pasted JQUANTS_TOKEN that is not a JWT is a V2 key too
    k = T.get_token("JQUANTS_TOKEN", environ={"JQUANTS_TOKEN": "opaque-key"}, now=NOW)
    assert k.ok and k.apply == "x-api-key"
