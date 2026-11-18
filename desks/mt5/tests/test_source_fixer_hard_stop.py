"""source_fixer: 401/403/429/WAF is a hard stop; how long it is held depends on which no.

No variant, no scheme/www swap and no Wayback lookup follows a refusal. 401/403/WAF is access
control: a site-wide hold no timer lapses, released only by a person. 429 is a rate refusal: a
hold on that one source alone, lapsing on its own after HARD_STOP_H (24 h), retried once under
the same honest client name. All network is faked; every request the module would make is
counted.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

import source_fixer

URL = "https://data.example.org/api/series.json"


class _Resp:
    def __init__(self, status: int, body: bytes, ctype: str) -> None:
        self.status = status
        self.headers = {"Content-Type": ctype}
        self._b = io.BytesIO(body)

    def read(self, n: int = -1) -> bytes:
        return self._b.read(n)

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name, rel in (("REGISTRY", "asia_sources.json"), ("COLLECTOR_REPORT", "AC.json"),
                      ("COLLECTOR_STATE", "cs.json"), ("OUT", "SOURCE_FIXER.json"),
                      ("STATE", "sfs.json")):
        monkeypatch.setattr(source_fixer, name, tmp_path / rel)
    monkeypatch.setattr(source_fixer, "VARIANT_GAP_S", 0.0)
    (tmp_path / "asia_sources.json").write_text(json.dumps(
        {"sources": [{"id": "s1", "url": URL, "expect": "json"}]}))
    calls: list[str] = []
    agents: list[str | None] = []
    answers: dict[str, Any] = {}

    def fake_urlopen(req, timeout=None, **_k):
        url = req if isinstance(req, str) else req.full_url
        calls.append(url)
        agents.append(None if isinstance(req, str) else req.get_header("User-agent"))
        ans = answers.get(url, 404)
        if isinstance(ans, _Resp):
            return ans
        raise urllib.error.HTTPError(url, ans, "x", {}, io.BytesIO(b""))  # type: ignore[arg-type]

    monkeypatch.setattr(source_fixer.urllib.request, "urlopen", fake_urlopen)

    def verdict(**row: Any) -> None:
        (tmp_path / "AC.json").write_text(json.dumps({"rows": [{"id": "s1", **row}]}))

    return {"calls": calls, "agents": agents, "answers": answers, "verdict": verdict,
            "tmp": tmp_path}


def _state(env) -> dict[str, Any]:
    return json.loads((env["tmp"] / "sfs.json").read_text())


@pytest.mark.parametrize("code", [401, 403])
def test_collector_refusal_makes_zero_requests_and_holds_for_a_person(env, code) -> None:
    env["verdict"](status="HTTP_ERROR", http=code)
    doc = source_fixer.run()
    assert env["calls"] == []  # no variant, no www/bare, no http/https, no Wayback
    (row,) = doc["results"]
    assert row["outcome"] == "HELD"
    hold = _state(env)["_holds"]["site:data.example.org"]
    assert hold["released_by"] is None and hold["released_at"] is None
    assert hold["status"] == code and hold["host"] == "data.example.org"
    assert hold["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert "recheck_after_ts" not in hold and doc["n_held"] == 1


def test_waf_verdict_is_a_hard_stop(env) -> None:
    env["verdict"](status="ROUTE_CHANGED", http=200, why="Cloudflare challenge page")
    doc = source_fixer.run()
    assert env["calls"] == [] and doc["results"][0]["outcome"] == "HELD"


@pytest.mark.parametrize("code", [403, 429])
def test_variant_refusal_stops_every_further_request_including_wayback(env, code) -> None:
    env["verdict"](status="ROUTE_CHANGED", http=200)
    first = source_fixer.candidate_urls(URL)[0]
    env["answers"][first] = code
    doc = source_fixer.run()
    assert env["calls"] == [first]
    assert not any("archive.org" in c for c in env["calls"])
    assert doc["results"][0]["outcome"] == "HELD"
    host = source_fixer._host(first)
    holds = _state(env)["_holds"]
    if code == 429:  # rate refusal: this source alone, on a timer
        assert f"site:{host}" not in holds
        assert holds["source:s1"]["release"] == "timer"
    else:
        assert holds[f"site:{host}"]["released_by"] is None


def test_collector_429_holds_only_that_source_for_hard_stop_h(env: dict[str, Any]) -> None:
    env["verdict"](status="HTTP_ERROR", http=429)
    doc = source_fixer.run()
    assert env["calls"] == []  # no variant, no www/bare, no http/https, no Wayback
    (row,) = doc["results"]
    assert row["outcome"] == "HELD"
    holds = _state(env)["_holds"]
    assert not any(k.startswith("site:") for k in holds)  # never the whole site
    hold = holds["source:s1"]
    assert hold["release"] == "timer" and hold["status"] == 429
    assert hold["recheck_after_ts"] == pytest.approx(
        hold["held_at"] + source_fixer.HARD_STOP_H * 3600)
    assert source_fixer.HARD_STOP_H == 24.0
    assert hold["missed_growth"]["delta_elogw"] == "UNMEASURED" and doc["n_held"] == 1


def test_a_429_on_one_source_never_blocks_another_on_the_same_host(
        env: dict[str, Any]) -> None:
    other = "https://data.example.org/api/other.json"
    (env["tmp"] / "asia_sources.json").write_text(json.dumps({"sources": [
        {"id": "s1", "url": URL, "expect": "json"},
        {"id": "s2", "url": other, "expect": "json"}]}))
    (env["tmp"] / "AC.json").write_text(json.dumps({"rows": [
        {"id": "s1", "status": "HTTP_ERROR", "http": 429},
        {"id": "s2", "status": "ROUTE_CHANGED", "http": 200}]}))
    fix = source_fixer.candidate_urls(other)[0]
    env["answers"][fix] = _Resp(200, b'{"ok": 1}', "application/json")
    doc = source_fixer.run()
    out = {r["id"]: r for r in doc["results"]}
    assert out["s1"]["outcome"] == "HELD"
    assert out["s2"]["outcome"] == "REPAIRED" and env["calls"] == [fix]


def test_429_hold_lapses_alone_and_retries_once_under_the_same_honest_ua(
        env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    env["verdict"](status="HTTP_ERROR", http=429)
    source_fixer.run()
    real = source_fixer.time.time
    # 23 h on: the hold stands and no request is made.
    monkeypatch.setattr(source_fixer.time, "time", lambda: real() + 23 * 3600)
    assert source_fixer.run()["results"][0]["outcome"] == "HELD"
    assert env["calls"] == []
    # 25 h on, no person involved: one retry of the registered URL, same honest client name.
    monkeypatch.setattr(source_fixer.time, "time", lambda: real() + 25 * 3600)
    env["answers"][URL] = 429
    doc = source_fixer.run()
    assert env["calls"] == [URL]
    assert env["agents"] == [source_fixer.USER_AGENT]
    assert doc["results"][0]["outcome"] == "HELD"  # a second 429: a fresh 24 h hold
    hold = _state(env)["_holds"]["source:s1"]
    assert hold["released_by"] is None
    assert hold["recheck_after_ts"] == pytest.approx(real() + 49 * 3600, abs=60)
    # Another 25 h on, the host answers: the source recovered with no person and no override.
    monkeypatch.setattr(source_fixer.time, "time", lambda: real() + 50 * 3600)
    env["answers"][URL] = _Resp(200, b'{"ok": 1}', "application/json")
    doc = source_fixer.run()
    assert doc["results"][0]["outcome"] == "RECOVERED" and doc["n_held"] == 0
    assert env["calls"] == [URL, URL]
    assert set(env["agents"]) == {source_fixer.USER_AGENT}
    reg = json.loads((env["tmp"] / "asia_sources.json").read_text())
    assert "url_override" not in reg["sources"][0]


def test_waf_body_on_a_variant_is_a_hard_stop(env) -> None:
    env["verdict"](status="UNREACHABLE")
    first = source_fixer.candidate_urls(URL)[0]
    env["answers"][first] = _Resp(200, b"<html><title>Just a moment...</title>cf-chl", "text/html")
    doc = source_fixer.run()
    assert env["calls"] == [first] and doc["results"][0]["outcome"] == "HELD"


def test_access_hold_never_lapses_and_only_a_person_releases_it(env, monkeypatch) -> None:
    env["verdict"](status="HTTP_ERROR", http=403)
    source_fixer.run()
    # 400 days on, whatever any clock says, the hold stands.
    real = source_fixer.time.time
    monkeypatch.setattr(source_fixer.time, "time", lambda: real() + 400 * 86400)
    # A later pass -- whatever the clock says -- with a now-harmless verdict makes no request.
    env["verdict"](status="ROUTE_CHANGED", http=200)
    for _ in range(3):
        doc = source_fixer.run()
        assert doc["results"][0]["outcome"] == "HELD"
    assert env["calls"] == []
    with pytest.raises(ValueError):
        source_fixer.release("site:data.example.org", " ")
    assert source_fixer.main(["--release", "site:data.example.org", "--by", "principal"]) == 0
    row = _state(env)["_holds"]["site:data.example.org"]
    assert row["released_by"] == "principal" and row["released_at"]
    source_fixer.run()
    assert env["calls"]  # released by a person: the repair resumes


def test_200_path_is_unchanged(env) -> None:
    env["verdict"](status="ROUTE_CHANGED", http=200)
    cands = source_fixer.candidate_urls(URL)
    env["answers"][cands[1]] = _Resp(200, b'{"ok": 1}', "application/json")
    doc = source_fixer.run()
    assert env["calls"] == cands[:2]
    (row,) = doc["results"]
    assert row["outcome"] == "REPAIRED" and row["to"] == cands[1]
    assert doc["n_held"] == 0
    reg = json.loads((env["tmp"] / "asia_sources.json").read_text())
    assert reg["sources"][0]["url_override"] == cands[1]


def test_404_everywhere_tries_every_variant_and_never_asks_the_archive(env) -> None:
    """A 404 is a route problem, not a refusal: every variant is tried and no hold is made.
    The Archive is refused on terms on LIVE (2026-11-14), so the last request is a variant."""
    env["verdict"](status="HTTP_ERROR", http=404)
    doc = source_fixer.run()
    assert env["calls"] == source_fixer.candidate_urls(URL)
    assert not any("archive.org" in c for c in env["calls"])
    (row,) = doc["results"]
    assert row["outcome"] == "STILL_DEAD" and row["wayback"] == source_fixer.WAYBACK_TERMS
    assert doc["n_held"] == 0


def test_legacy_row_with_recheck_after_ts_is_still_active(env) -> None:
    (env["tmp"] / "sfs.json").write_text(json.dumps({"_holds": {"site:data.example.org": {
        "key": "site:data.example.org", "released_by": None, "recheck_after_ts": 1.0}}}))
    env["verdict"](status="ROUTE_CHANGED", http=200)
    doc = source_fixer.run()
    assert env["calls"] == [] and doc["results"][0]["outcome"] == "HELD"


def test_a_held_twin_host_blocks_the_www_variant(env) -> None:
    (env["tmp"] / "sfs.json").write_text(json.dumps({"_holds": {
        "site:www.data.example.org": {"key": "site:www.data.example.org", "released_by": None}}}))
    env["verdict"](status="ROUTE_CHANGED", http=200)
    doc = source_fixer.run()
    assert env["calls"] == [] and doc["results"][0]["outcome"] == "HELD"
