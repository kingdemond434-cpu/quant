"""coverage-risk-stale root cause (2026-08-12): :free panel seats fail with TRANSIENT
400/429/choices-null during pool saturation -- the identical seat flipped 400 at 03:36 and
answered at 07:30 -- so quorum sat at 1/4 since 08-04 and the risk-file audit stamps froze.
_ask retries free seats through the transient class and NEVER retries paid seats (a retried
bad request re-bills the ~40k-char context for nothing).
"""
from __future__ import annotations

import urllib.error

import pytest

from scripts import run_external_panel as panel


class _Flaky:
    """Fails `fail_n` times with `exc`, then answers."""

    def __init__(self, fail_n: int, exc: Exception):
        self.fail_n, self.exc, self.calls = fail_n, exc, 0

    def __call__(self, base_url, key, model, messages, timeout=360.0):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise self.exc
        return "substantive answer"


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "msg", hdrs=None, fp=None)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(panel._time, "sleep", lambda s: None)


def test_free_seat_retries_through_transient_400(monkeypatch):
    flaky = _Flaky(2, _http(400))
    monkeypatch.setattr(panel, "_ask_once", flaky)
    assert panel._ask("https://x", "k", "poolside/laguna-s-2.1:free", []) == \
        "substantive answer"
    assert flaky.calls == 3                              # 1 + _FREE_RETRIES


def test_free_seat_retries_choices_null_envelope(monkeypatch):
    flaky = _Flaky(1, TypeError("'NoneType' object is not subscriptable"))
    monkeypatch.setattr(panel, "_ask_once", flaky)
    assert panel._ask("https://x", "k", "openai/gpt-oss-20b:free", []) == "substantive answer"


def test_free_seat_gives_up_after_bounded_retries(monkeypatch):
    flaky = _Flaky(99, _http(429))
    monkeypatch.setattr(panel, "_ask_once", flaky)
    with pytest.raises(urllib.error.HTTPError):
        panel._ask("https://x", "k", "m:free", [])
    assert flaky.calls == 1 + panel._FREE_RETRIES        # bounded, never a hot loop


def test_paid_seat_is_never_retried(monkeypatch):
    flaky = _Flaky(1, _http(400))
    monkeypatch.setattr(panel, "_ask_once", flaky)
    with pytest.raises(urllib.error.HTTPError):
        panel._ask("https://x", "k", "anthropic/claude-fable-5", [])
    assert flaky.calls == 1                              # a paid bad request re-bills nothing


def test_non_transient_code_raises_immediately(monkeypatch):
    flaky = _Flaky(1, _http(401))                        # auth is NOT pool saturation
    monkeypatch.setattr(panel, "_ask_once", flaky)
    with pytest.raises(urllib.error.HTTPError):
        panel._ask("https://x", "k", "m:free", [])
    assert flaky.calls == 1
