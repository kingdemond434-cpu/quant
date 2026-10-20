"""source_fixer: 401/403/429/WAF is a hard stop held until a person releases it.

No variant, no scheme/www swap and no Wayback lookup follows a refusal, and no timer lapses the
hold. All network is faked; every request the module would make is counted.
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
    robots: list[str] = []
    answers: dict[str, Any] = {}

    def fake_urlopen(req, timeout=None, **_k):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/robots.txt"):       # robots.txt: 404 = allow all (RFC 9309)
            robots.append(url)
            raise urllib.error.HTTPError(url, 404, "x", {}, io.BytesIO(b""))  # type: ignore[arg-type]
        calls.append(url)
        if url.startswith(source_fixer.WAYBACK):
            return _Resp(200, b'{"archived_snapshots": {}}', "application/json")
        ans = answers.get(url, 404)
        if isinstance(ans, _Resp):
            return ans
        hdrs: dict[str, str] = {}
        if isinstance(ans, tuple):            # (30x, Location)
            ans, hdrs = ans[0], {"Location": ans[1]}
        raise urllib.error.HTTPError(url, ans, "x", hdrs, io.BytesIO(b""))  # type: ignore[arg-type]

    # The polite no-redirect opener (variants, robots.txt) and the fetch door (Wayback): every
    # request the module can make lands here.
    monkeypatch.setattr(source_fixer._pf, "open_no_redirect", fake_urlopen)
    monkeypatch.setattr(source_fixer, "fenced_urlopen", fake_urlopen)

    def verdict(**row: Any) -> None:
        (tmp_path / "AC.json").write_text(json.dumps({"rows": [{"id": "s1", **row}]}))

    return {"calls": calls, "answers": answers, "verdict": verdict, "tmp": tmp_path,
            "robots": robots}


def _state(env) -> dict[str, Any]:
    return json.loads((env["tmp"] / "sfs.json").read_text())


@pytest.mark.parametrize("code", [401, 403, 429])
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
    assert not any(c.startswith(source_fixer.WAYBACK) for c in env["calls"])
    assert doc["results"][0]["outcome"] == "HELD"
    host = source_fixer._host(first)
    assert _state(env)["_holds"][f"site:{host}"]["released_by"] is None


def test_waf_body_on_a_variant_is_a_hard_stop(env) -> None:
    env["verdict"](status="UNREACHABLE")
    first = source_fixer.candidate_urls(URL)[0]
    env["answers"][first] = _Resp(200, b"<html><title>Just a moment...</title>cf-chl", "text/html")
    doc = source_fixer.run()
    assert env["calls"] == [first] and doc["results"][0]["outcome"] == "HELD"


def test_hold_never_lapses_and_only_a_person_releases_it(env, monkeypatch) -> None:
    env["verdict"](status="HTTP_ERROR", http=429)
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


def test_404_everywhere_still_reaches_wayback(env) -> None:
    env["verdict"](status="HTTP_ERROR", http=404)
    doc = source_fixer.run()
    assert env["calls"][-1].startswith(source_fixer.WAYBACK)
    assert doc["results"][0]["outcome"] == "STILL_DEAD"


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


# ---------------------------------------------------------------- audit 31618ff54 should-fixes
def test_a_redirecting_variant_is_never_followed_to_its_target(env) -> None:
    """(1) The no-redirect opener: a variant answering 30x to another host is recorded, and the
    target is never requested by the fixer."""
    env["verdict"](status="ROUTE_CHANGED", http=200)
    cands = source_fixer.candidate_urls(URL)
    env["answers"][cands[0]] = (302, "https://elsewhere.example.net/landing")
    doc = source_fixer.run()
    assert "https://elsewhere.example.net/landing" not in env["calls"]
    assert not any("elsewhere.example.net" in r for r in env["robots"])
    (row,) = doc["results"]
    assert row["tried"][0]["why"] == "redirect:https://elsewhere.example.net/landing"
    assert row["outcome"] == "STILL_DEAD"


def test_a_refusal_holds_the_host_that_refused_in_both_records(env) -> None:
    """(1) The refusing variant's own host is held here AND in the shared access record."""
    from libs.data import polite_fetch as pf
    env["verdict"](status="ROUTE_CHANGED", http=200)
    cands = source_fixer.candidate_urls(URL)
    env["answers"][cands[0]] = 429
    source_fixer.run()
    host = source_fixer._host(cands[0])
    assert _state(env)["_holds"][f"site:{host}"]["status"] == 429
    assert pf.person_hold(cands[0]) == "METHOD_BLOCKED"


def test_a_site_held_in_the_shared_record_is_never_probed(env) -> None:
    from libs.data import polite_fetch as pf
    pf.hold_site("https://example.org/x", 403)
    env["verdict"](status="ROUTE_CHANGED", http=200)
    doc = source_fixer.run()
    assert env["calls"] == [] and env["robots"] == []
    assert doc["results"][0]["outcome"] == "HELD"


def test_releasing_one_key_releases_its_www_twin(env) -> None:
    """(2) site:x and site:www.x are one site: a release of either releases both stored keys."""
    (env["tmp"] / "sfs.json").write_text(json.dumps({"_holds": {
        "site:data.example.org": {"key": "site:data.example.org", "released_by": None},
        "site:www.data.example.org": {"key": "site:www.data.example.org", "released_by": None},
    }}))
    source_fixer.release("site:data.example.org", "principal")
    holds = _state(env)["_holds"]
    assert all(h["released_by"] == "principal" and h["released_at"] for h in holds.values())
    env["verdict"](status="ROUTE_CHANGED", http=200)
    assert source_fixer.run()["n_held"] == 0


def test_holds_listed_by_a_dry_run_are_labelled_dry_run(env) -> None:
    """(3) A dry run persists nothing, so the holds it lists say so."""
    env["verdict"](status="HTTP_ERROR", http=429)
    doc = source_fixer.run(dry_run=True)
    assert doc["holds_persisted"] is False
    assert doc["holds"] and all(h["dry_run"] is True for h in doc["holds"])
    assert doc["results"][0]["hold"]["dry_run"] is True
    assert not (env["tmp"] / "sfs.json").exists()
    real = source_fixer.run()
    assert real["holds_persisted"] is True and "dry_run" not in real["holds"][0]
