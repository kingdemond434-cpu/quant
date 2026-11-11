"""The CFTC fetchers on the hourly leg send our honest UA, and fetch nothing robots.txt has not
allowed (#238 audit HOLD, 2026-11-11).

`fetch_tff`, `fetch_cot` and `fetch_cot_disagg` sent "Mozilla/5.0" with no robots check, and
`fetch_cot_latest` put all three on the hourly leg. They now open through
`futures_state.gated_urlopen`: `futures_state.UA`, and only after `futures_state.robots_verdict`
(a thin wrap of `robots_allow`) says ALLOWED. 401/403/429/451 on robots.txt is REFUSED; a 5xx, a
network error or a challenge page is UNMEASURED; 404/410 means no rules. No network is used here.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import fetch_cot, fetch_cot_disagg, fetch_cot_latest, fetch_tff  # noqa: E402

from research import futures_state as fs  # noqa: E402

URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=5000"


def _raises(exc: Exception):
    def get(_u: str) -> str:
        raise exc
    return get


# ------------------------------------------------------------------- the verdict, by case
@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_hard_stop_on_robots_txt_is_refused(code):
    got, why = fs.robots_verdict(URL, _raises(fs.HardStop(code, "robots")))
    assert got == fs.ROBOTS_REFUSED and str(code) in why


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_hard_stop_raised_as_an_http_error_is_refused_too(code):
    err = urllib.error.HTTPError("https://x/robots.txt", code, "no", {}, None)  # type: ignore[arg-type]
    assert fs.robots_verdict(URL, _raises(err))[0] == fs.ROBOTS_REFUSED


@pytest.mark.parametrize("exc", [fs.FetchError(503, "r", "HTTP 503"),
                                 fs.FetchError(500, "r", "HTTP 500"),
                                 fs.FetchError(None, "r", "timed out"),
                                 OSError("network unreachable")])
def test_a_5xx_or_a_network_error_is_unmeasured(exc):
    assert fs.robots_verdict(URL, _raises(exc))[0] == fs.ROBOTS_UNMEASURED


@pytest.mark.parametrize("body", [
    "<!DOCTYPE html><html><title>Just a moment...</title></html>",
    "<html><body>Please complete the captcha</body></html>"])
def test_a_challenge_page_in_place_of_rules_is_unmeasured(body):
    assert fs.robots_verdict(URL, lambda _u: body)[0] == fs.ROBOTS_UNMEASURED


@pytest.mark.parametrize("code", [404, 410])
def test_a_missing_robots_txt_means_no_rules(code):
    assert fs.robots_verdict(URL, _raises(fs.FetchError(code, "r", "gone")))[0] == \
        fs.ROBOTS_ALLOWED


def test_the_files_own_rules_decide_otherwise():
    assert fs.robots_verdict(URL, lambda _u: "User-agent: *\nDisallow: /resource/\n")[0] == \
        fs.ROBOTS_DISALLOWED
    assert fs.robots_verdict(URL, lambda _u: "User-agent: *\nDisallow: /private/\n")[0] == \
        fs.ROBOTS_ALLOWED


# --------------------------------------------- refusal means no request; the UA is honest
@pytest.fixture
def wire(monkeypatch):
    sent: list = []

    class _Resp:
        def __init__(self, body: bytes):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def urlopen(req, timeout=None, context=None):
        sent.append(req)
        return _Resp(b"[]")
    monkeypatch.setattr(fs.urllib.request, "urlopen", urlopen)
    return sent


@pytest.mark.parametrize("verdict", [fs.ROBOTS_REFUSED, fs.ROBOTS_UNMEASURED,
                                     fs.ROBOTS_DISALLOWED])
def test_gated_urlopen_makes_no_request_unless_allowed(wire, monkeypatch, verdict):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (verdict, "test"))
    with pytest.raises(fs.RobotsRefused) as got:
        fs.gated_urlopen(URL, 5)
    assert got.value.verdict == verdict
    assert wire == []


def test_gated_urlopen_sends_the_desks_honest_ua(wire, monkeypatch):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_ALLOWED, "test"))
    with fs.gated_urlopen(URL, 5) as resp:
        assert resp.read() == b"[]"
    assert len(wire) == 1
    ua = wire[0].get_header("User-agent")
    assert ua == fs.UA and "Mozilla" not in ua and "quant-research" in ua


@pytest.mark.parametrize("mod", [fetch_cot, fetch_cot_disagg])
def test_the_socrata_fetchers_refused_by_robots_make_no_request(wire, monkeypatch, mod):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_REFUSED, "403"))
    with pytest.raises(fs.RobotsRefused):
        mod.fetch_contract("GOLD")
    assert wire == []


@pytest.mark.parametrize("mod", [fetch_cot, fetch_cot_disagg])
def test_the_socrata_fetchers_send_the_honest_ua(wire, monkeypatch, mod):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_ALLOWED, "ok"))
    assert mod.fetch_contract("GOLD") is None          # the stub answers no rows
    assert wire and all(r.get_header("User-agent") == fs.UA for r in wire)


def test_the_tff_fetcher_refused_by_robots_makes_no_request(wire, monkeypatch):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_UNMEASURED, "503"))
    assert fetch_tff.load_year(2026) is None
    assert wire == []


def test_the_tff_fetcher_sends_the_honest_ua(wire, monkeypatch):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_ALLOWED, "ok"))
    assert fetch_tff.load_year(2026) is None           # the stub body is not a zip
    assert len(wire) == 1 and wire[0].get_header("User-agent") == fs.UA


def test_the_hourly_refetch_records_a_robots_refusal_as_no_fetch(wire, monkeypatch, tmp_path):
    monkeypatch.setattr(fs, "robots_verdict", lambda _u: (fs.ROBOTS_REFUSED, "403"))
    out = fetch_cot_latest._socrata("legacy", tmp_path, deadline=1e18, plan={"slugs": ["gold"]})
    assert out == {"gold": "NOT_FETCHED_ROBOTS_REFUSED"}
    assert wire == []


def test_no_fetcher_spoofs_a_browser():
    for mod in (fetch_tff, fetch_cot, fetch_cot_disagg, fetch_cot_latest):
        assert "Mozilla" not in Path(str(mod.__file__)).read_text("utf-8"), mod.__name__
