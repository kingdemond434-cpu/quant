"""ROBOTS FAIL CLOSED on the Asia planes' new fetch paths until the desk's gate (#831) lands.

Audit hold on #251 (2026-11-11). `libs.data.robots_shim.robots_allows(url)` delegates to
`libs.data.robots_gate.RobotsGate.check` when that module is on the tree and answers False when it
is not. With NO gate, each path below makes ZERO network calls (robots.txt included), records
REFUSED_ROBOTS_UNREAD and writes one missed-growth line; with a stub gate that ALLOWS, the same
paths fetch.

  * alt_proxies: the six plane rows whose robots.txt was never read (MOF x3, HKMA x3);
  * asia_collector.collect_one: a keyed row, and a managed-token row;
  * research/keyed_sources.collect: every keyed request;
  * libs/ops/token_refresh: the mint.
"""
from __future__ import annotations

import json
import socket
import sys
import types
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import asia_collector as ac  # noqa: E402
import keyed_sources as K  # noqa: E402

from libs.data import keyed_sources as ks  # noqa: E402
from libs.data import robots_shim  # noqa: E402
from libs.ops import token_refresh as T  # noqa: E402
from research import alt_proxies as A  # noqa: E402

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
SIX = ("jp_mof_securities_weekly", "jp_mof_securities_investor_bonds", "jp_mof_fx_intervention",
       "hk_hkma_interbank_liquidity", "hk_hkma_hibor_fixing", "hk_hkma_monetary_base")


class _Net:
    """Every way out of this process, refused and counted."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[str] = []

        def boom(*a: Any, **k: Any) -> Any:
            self.calls.append(repr(a[:1])[:120])
            raise AssertionError(f"network call: {a[:1]!r}")
        monkeypatch.setattr(urllib.request, "urlopen", boom)
        monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
        monkeypatch.setattr(socket, "create_connection", boom)
        monkeypatch.setattr(T, "_http", boom)


@pytest.fixture
def no_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tree as it is today: libs.data.robots_gate is not importable."""
    monkeypatch.setattr(robots_shim, "_gate_module", lambda: None)
    monkeypatch.setattr(robots_shim, "_GATE", None)


@pytest.fixture
def _token_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_TOKEN_CACHE_DIR", str(tmp_path / "token_cache"))
    for p in T.PROVIDERS.values():
        monkeypatch.delenv(p.short_env, raising=False)
        for g in p.long_envs:
            for k in g:
                monkeypatch.delenv(k, raising=False)


def _ledger() -> list[dict[str, Any]]:
    p = robots_shim.MISSED_GROWTH
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


# --------------------------------------------------------------------------- the shim itself
def test_the_shim_is_closed_without_the_gate_and_reads_nothing(
        no_gate: None, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _Net(monkeypatch)
    assert robots_shim.robots_allows("https://www.mof.go.jp/x.csv") is False
    out = robots_shim.refuse("organ", "https://www.mof.go.jp/x.csv", "src", NOW)
    robots_shim.refuse("organ", "https://www.mof.go.jp/y.csv", "src", NOW)   # same host, day
    assert out["status"] == "REFUSED_ROBOTS_UNREAD" and out["requests"] == 0
    (line,) = _ledger()
    assert line["rail"] == "robots_unread" and line["host"] == "www.mof.go.jp"
    assert line["value"] is None and line["measured"] is False and "UNMEASURED" in line["why"]
    assert net.calls == []


def test_the_shim_delegates_to_the_gate_and_only_allowed_passes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    verdicts = {"https://a.example/p": "ALLOWED", "https://b.example/p": "DISALLOWED",
                "https://c.example/p": "UNREAD"}

    class Gate:
        def __init__(self, get: Any, agent: str = "") -> None:
            pass

        def check(self, url: str) -> str:
            return verdicts[url]
    stub = types.SimpleNamespace(RobotsGate=Gate, ALLOWED="ALLOWED")
    monkeypatch.setattr(robots_shim, "_gate_module", lambda: stub)
    monkeypatch.setattr(robots_shim, "_GATE", None)
    assert [robots_shim.robots_allows(u) for u in verdicts] == [True, False, False]


def test_the_real_gate_api_is_what_the_shim_calls() -> None:
    """When #831 is on the tree, its RobotsGate(get, agent).check(url) is the call (pinned so a
    renamed API fails here, not silently closed on the box)."""
    mod = robots_shim._gate_module()
    if mod is None:
        pytest.skip("libs.data.robots_gate (#831) is not on this tree: the shim fails closed")
    gate = mod.RobotsGate(lambda u: (404, ""), agent=robots_shim.AGENT)
    assert gate.check("https://example.org/x") == mod.ALLOWED


# --------------------------------------------------------------------------- alt_proxies rows
def test_the_six_plane_rows_are_exactly_the_robots_unread_set() -> None:
    assert set(SIX) == set(A.ROBOTS_UNREAD_SOURCES)


@pytest.mark.parametrize("sid", SIX)
def test_an_unread_robots_row_makes_no_request_without_the_gate(
        sid: str, no_gate: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    net = _Net(monkeypatch)
    got: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        got.append(url)
        raise AssertionError(f"fetched {url}")
    src = A.BY_ID[sid]
    assert src.terms == "confirmed" and A.requests_for(src, NOW, {})
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=getter)
    assert rec["status"] == "REFUSED_ROBOTS_UNREAD" and rec["requests"] == 0, rec
    assert got == [] and net.calls == []
    assert [x["source"] for x in _ledger()] == [sid]


@pytest.mark.parametrize("sid", SIX)
def test_an_unread_robots_row_fetches_once_the_gate_allows(
        sid: str, robots_allowed: None, tmp_path: Path) -> None:
    got: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        got.append(url)
        raise OSError("offline in tests")
    rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID[sid], {}, NOW, fetch=True,
                    fixtures=None, deadline=1e18, getter=getter)
    assert got and rec["status"] != "REFUSED_ROBOTS_UNREAD"
    assert _ledger() == []


def test_fixtures_never_ask_robots(no_gate: None, tmp_path: Path) -> None:
    fix = ROOT / "tests" / "fixtures" / "alt_proxies"
    rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID["jp_mof_fx_intervention"], {}, NOW,
                    fetch=True, fixtures=fix, deadline=1e18)
    assert rec["status"] != "REFUSED_ROBOTS_UNREAD" and _ledger() == []


# --------------------------------------------------------------------------- the token paths
def test_a_mint_sends_no_credential_without_the_gate(
        no_gate: None, _token_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _Net(monkeypatch)
    env = {"JQUANTS_MAILADDRESS": "me@example.org", "JQUANTS_PASSWORD": "pw-SECRET",
           "CDSE_CLIENT_ID": "cid", "CDSE_CLIENT_SECRET": "cs-SECRET"}
    for short in ("JQUANTS_TOKEN", "CDSE_TOKEN"):
        res = T.get_token(short, environ=env)
        assert res.status == T.REFUSED_ROBOTS_UNREAD and not res.ok, (short, res)
        assert T.collector_status(res) == "REFUSED_ROBOTS_UNREAD"
        assert "SECRET" not in res.detail
    assert net.calls == []
    assert {x["source"] for x in _ledger()} == {"jquants", "cdse"}


def test_a_mint_runs_once_the_gate_allows(robots_allowed: None, _token_env: None,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def http(method: str, url: str, data: Any, headers: Any, timeout: float
             ) -> tuple[int, bytes]:
        calls.append(url)
        return 200, json.dumps({"access_token": "tok", "expires_in": 600}).encode()
    monkeypatch.setattr(T, "_http", http)
    res = T.get_token("CDSE_TOKEN", environ={"CDSE_CLIENT_ID": "c", "CDSE_CLIENT_SECRET": "s"})
    assert res.ok and calls == [T.CDSE_ENDPOINT]


def _keyed_row() -> dict[str, Any]:
    return {"id": "eia_energy", "access": "key", "key_env": "QK_ASIA_KEY",
            "key_in": "query:api_key", "url": "https://api.eia.gov/v2/x/data/",
            "terms_ref": "asia_eia_energy", "expect": "json"}


def test_a_keyed_collector_row_sends_nothing_without_the_gate(
        no_gate: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_ASIA_KEY", "SECRET123")
    net = _Net(monkeypatch)
    rec = ac.collect_one(_keyed_row())
    assert rec["status"] == "REFUSED_ROBOTS_UNREAD" and rec["requests"] == 0, rec
    assert net.calls == [] and "SECRET123" not in json.dumps(rec)
    assert [x["organ"] for x in _ledger()] == ["asia_collector"]


def test_a_keyed_collector_row_fetches_once_the_gate_allows(
        robots_allowed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QK_ASIA_KEY", "SECRET123")
    monkeypatch.setattr(ac, "_robots_allows", lambda url, agent="": (True, "ok"))
    seen: list[str] = []

    def opened(self: Any, req: Any, data: Any = None, timeout: float = 0) -> Any:
        seen.append(req.full_url)
        raise OSError("offline in tests")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", opened)
    rec = ac.collect_one(_keyed_row())
    assert seen and rec["status"] == "UNREACHABLE"


def test_a_token_collector_row_names_the_refusal_without_the_gate(
        no_gate: None, _token_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDSE_CLIENT_ID", "cid")
    monkeypatch.setenv("CDSE_CLIENT_SECRET", "cs-SECRET")
    # the row's own terms decision is not what is under test here: the robots door is
    monkeypatch.setattr(ac, "_terms_state", lambda src, url: ("confirmed", ""))
    net = _Net(monkeypatch)
    rec = ac.collect_one({"id": "cdse_catalogue", "access": "key", "key_env": "CDSE_TOKEN",
                          "url": "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
                          "expect": "json"})
    assert rec["status"] == "REFUSED_ROBOTS_UNREAD" and rec["requests"] == 0, rec
    assert net.calls == [] and "cs-SECRET" not in json.dumps(rec)


def test_a_token_detail_is_scrubbed_in_the_collector_record(
        _token_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """tok.detail reaches a tracked report: whatever a minter put in it, no credential lands."""
    monkeypatch.setenv("CDSE_CLIENT_ID", "cid")
    monkeypatch.setenv("CDSE_CLIENT_SECRET", "cs-SECRET-VALUE")
    leaky = T.TokenResult(T.REFRESH_FAILED, "CDSE_TOKEN",
                          detail="token endpoint said https://u:cs-SECRET-VALUE@h/?password=pw1 "
                                 "client_secret=cs-SECRET-VALUE")
    monkeypatch.setattr(ac._token_refresh, "get_token", lambda env, **k: leaky)
    monkeypatch.setattr(ac, "_terms_state", lambda src, url: ("confirmed", ""))
    rec = ac.collect_one({"id": "cdse_catalogue", "access": "key", "key_env": "CDSE_TOKEN",
                          "url": "https://catalogue.dataspace.copernicus.eu/x", "expect": "json"})
    text = json.dumps(rec)
    assert rec["status"] == "BLOCKED_AUTH" and rec["token_detail"]
    assert "cs-SECRET-VALUE" not in text and "pw1" not in text, text


# --------------------------------------------------------------------------- keyed_sources leg
def _ks_row() -> dict[str, Any]:
    doc = json.loads((DESK / "data" / "source_rosters" / "keyed_sources.json")
                     .read_text("utf-8"))
    return next(r for r in doc["sources"] if r["id"] == "eia_petroleum_weekly")


def test_a_keyed_source_request_is_never_sent_without_the_gate(
        no_gate: None, monkeypatch: pytest.MonkeyPatch) -> None:
    net = _Net(monkeypatch)
    got: list[str] = []

    def get(req: ks.Request) -> bytes:
        got.append(req.url)
        raise AssertionError("fetched")
    with pytest.raises(K.Blocked, match="^REFUSED_ROBOTS_UNREAD$"):
        K.collect(_ks_row(), get=get, now=NOW, paths=K.Paths(), start=None,
                  environ={"EIA_API_KEY": "SECRET-EIA"})
    assert got == [] and net.calls == []
    (line,) = _ledger()
    assert line["organ"] == "keyed_sources" and "SECRET-EIA" not in json.dumps(line)


def test_a_keyed_source_request_is_sent_once_the_gate_allows(robots_allowed: None) -> None:
    got: list[str] = []

    def get(req: ks.Request) -> bytes:
        got.append(req.url)
        raise OSError("offline in tests")
    with pytest.raises(RuntimeError):
        K.collect(_ks_row(), get=get, now=NOW, paths=K.Paths(), start=None,
                  environ={"EIA_API_KEY": "SECRET-EIA"})
    assert got
