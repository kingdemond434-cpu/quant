"""A host that refuses the honest name is recorded as a refusal, never as a dead or empty source.

The auditor's finding on PR #1320 (2026-11-18): once every fetcher sends
``libs/data/honest_ua.HONEST_UA``, some hosts answer 401/403/429/451 or serve a challenge page.
Each must come out as a HARD_STOP (a refusing status) or BLOCKED_ON_TERMS (a wall) row carrying
the host, the status, the UA sent, a missed_growth line, ``retry: never`` and ``bypass: refused``
-- and no fetcher may answer it by trying another User-Agent.
"""

from __future__ import annotations

import io
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "desks" / "mt5"),
           str(_ROOT / "desks" / "mt5" / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import venue_http  # noqa: E402
from libs.data.honest_ua import (  # noqa: E402
    BLOCKED_ON_TERMS,
    HARD_STOP,
    HONEST_UA,
    REFUSAL_MISSED_GROWTH,
    refusal_row,
)
from libs.research import source_health as sh  # noqa: E402

CHALLENGE = ("<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
             "<script>window._cf_chl_opt={cvId:'3'}</script></body></html>")
_T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)


def _assert_refused_row(row: dict[str, Any] | None, status: str, host: str) -> None:
    assert row is not None
    assert row["status"] == status
    assert row["host"] == host
    assert row["user_agent"] == HONEST_UA
    assert row["missed_growth"] == REFUSAL_MISSED_GROWTH
    assert "lawful route" in str(row["missed_growth"])
    assert row["retry"] == "never" and row["bypass"] == "refused"


class _Recorder:
    """A fake transport that records the User-Agent of every request it is handed."""

    def __init__(self, answers: list[Any]) -> None:
        self.answers = answers
        self.uas: list[str] = []

    def __call__(self, req: Any, *a: Any, **k: Any) -> Any:
        self.uas.append(req.get_header("User-agent") or "")
        ans = self.answers[min(len(self.uas), len(self.answers)) - 1]
        if isinstance(ans, BaseException):
            raise ans
        return ans


class _Body:
    def __init__(self, text: str, url: str) -> None:
        self._raw, self.url, self.status = text.encode(), url, 200
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def read(self, *a: Any) -> bytes:
        return self._raw


def _http_error(url: str, code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "refused", Message(), io.BytesIO(body.encode()))


# ------------------------------------------------------------------------------- polite_fetch
@pytest.mark.parametrize("code", [401, 403, 451])
def test_a_refusing_status_is_a_hard_stop_and_is_asked_once(code: int) -> None:
    url = "https://ground.example/forum"
    t = _Recorder([_http_error(url, code)])
    r = pf.get(url, opener=t, gate=None, retries=3, sleep=lambda s: None)
    _assert_refused_row(r.refusal, HARD_STOP, "ground.example")
    assert r.refusal is not None and r.refusal["http_status"] == code
    assert not r.ok and r.error.startswith(HARD_STOP)
    assert t.uas == [HONEST_UA]                  # one request, the honest name, never another


def test_a_429_is_paced_under_the_same_name_then_a_hard_stop() -> None:
    url = "https://ground.example/api"
    t = _Recorder([_http_error(url, 429)])
    r = pf.get(url, opener=t, gate=None, retries=2, sleep=lambda s: None)
    _assert_refused_row(r.refusal, HARD_STOP, "ground.example")
    assert len(t.uas) == 3 and set(t.uas) == {HONEST_UA}   # no rotation, ever


def test_a_challenge_page_served_as_200_is_blocked_on_terms_not_data() -> None:
    url = "https://walled.example/p"
    t = _Recorder([_Body(CHALLENGE, url)])
    r = pf.get(url, opener=t, gate=None, retries=3, sleep=lambda s: None)
    _assert_refused_row(r.refusal, BLOCKED_ON_TERMS, "walled.example")
    assert not r.ok
    assert t.uas == [HONEST_UA]


def test_a_503_interstitial_is_a_wall_and_is_not_retried() -> None:
    url = "https://walled.example/p"
    t = _Recorder([_http_error(url, 503, CHALLENGE)])
    r = pf.get(url, opener=t, gate=None, retries=3, sleep=lambda s: None)
    _assert_refused_row(r.refusal, BLOCKED_ON_TERMS, "walled.example")
    assert t.uas == [HONEST_UA]


def test_an_ordinary_page_with_a_captcha_form_is_content() -> None:
    url = "https://forum.example/t/1"
    page = ("<html><title>Thread</title><p>" + "x" * 500 + "</p><div class='g-recaptcha'></div>"
            "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script></html>")
    r = pf.get(url, opener=_Recorder([_Body(page, url)]), gate=None)
    assert r.ok and r.refusal is None


def test_a_404_is_not_a_refusal() -> None:
    url = "https://ground.example/moved"
    r = pf.get(url, opener=_Recorder([_http_error(url, 404)]), gate=None, sleep=lambda s: None)
    assert r.refusal is None and r.error == "HTTP 404"


# ------------------------------------------------------------------------------- venue_http
def test_venue_http_raises_the_refused_row_after_one_request(monkeypatch) -> None:
    url = "https://data.example/v1/series"
    t = _Recorder([_http_error(url, 403)])
    monkeypatch.setattr(venue_http.urllib.request, "urlopen", t)
    monkeypatch.setattr(venue_http.time, "sleep", lambda s: None)
    with pytest.raises(venue_http.HostRefused) as info:
        venue_http.get_json(url, tries=4)
    _assert_refused_row(info.value.row, HARD_STOP, "data.example")
    assert isinstance(info.value, RuntimeError)
    assert t.uas == [HONEST_UA]


# ------------------------------------------------------------------------------- source_health
@pytest.mark.parametrize("error, state", [
    ("HARD_STOP: HTTP 403 to quant-desk-research (https://zhihu.example/api)", HARD_STOP),
    ("HTTPError: HTTP Error 451: Unavailable For Legal Reasons", HARD_STOP),
    ("served <title>Attention Required! | Cloudflare</title>", BLOCKED_ON_TERMS),
])
def test_a_refused_source_is_never_marched_to_dead(tmp_path: Path, error: str, state: str) -> None:
    p = tmp_path / "h.jsonl"
    for i in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES + 2):
        touched = sh.record_run([sh.Observation(source="zhihu", ok=False, error=error,
                                                vantage=sh.VANTAGE_DIRECT)],
                                path=p, now=_T0 + timedelta(days=i))
    st = touched["zhihu"]
    assert st.verdict == state and st.verdict != sh.VERDICT_DEAD
    assert st.consecutive_failed_runs == 0
    assert sh.dead_sources(p, now=_T0 + timedelta(days=9)) == []
    _assert_refused_row(sh.state_of("zhihu", p, now=_T0 + timedelta(days=9)).refusal, state,
                        "zhihu.example" if "zhihu.example" in error else "zhihu")
    assert "missed_growth" in st.claim()


def test_a_transport_failure_still_reaches_dead(tmp_path: Path) -> None:
    p = tmp_path / "h.jsonl"
    for i in range(sh.DEAD_AFTER_CONSECUTIVE_FAILURES):
        sh.record_run([sh.Observation(source="csdn", ok=False, error="ReadTimeout",
                                      vantage=sh.VANTAGE_DIRECT)], path=p,
                      now=_T0 + timedelta(days=i))
    assert [s.source for s in sh.dead_sources(p, now=_T0 + timedelta(days=5))] == ["csdn"]


# ------------------------------------------------------------------------------- run_all_miners
def test_a_miner_failing_on_a_refusal_is_a_hard_stop_not_failed() -> None:
    import run_all_miners as ram

    row = ram.miner_outcome("ground", "err", "HostRefused: HARD_STOP: HTTP 403 to "
                            "quant-desk-research -- the host refused the desk "
                            "(https://ground.example/a)")
    assert row["status"] == HARD_STOP and row["count"] == 0
    _assert_refused_row(row["refusal"], HARD_STOP, "ground.example")
    assert row["retry"] == "never" and row["bypass"] == "refused"
    wall = ram.miner_outcome("ground", "err", "RuntimeError: <title>Just a moment...</title>")
    assert wall["status"] == BLOCKED_ON_TERMS
    plain = ram.miner_outcome("ground", "err", "ValueError: bad json")
    assert "status" not in plain and "refusal" not in plain


def test_the_classifier_ignores_non_refusals() -> None:
    assert refusal_row("https://a.example", status=404) is None
    assert refusal_row("https://a.example", status=500, body="<html>oops</html>") is None
    assert refusal_row(error="ConnectionResetError") is None
