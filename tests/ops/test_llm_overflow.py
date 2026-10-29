"""The GitHub free overflow: used only after OpenRouter's day is gone, closed per model on a
daily 429, closed for the day on 401/403, and kept out of OpenRouter's request count."""
from __future__ import annotations

import json

import pytest

from libs.ops import llm_overflow as ov
from libs.ops import llm_seat

CAT = [{"id": "openai/gpt-4.1-mini", "rate_limit_tier": "low",
        "supported_output_modalities": ["text"]},
       {"id": "openai/gpt-4.1", "rate_limit_tier": "high"},
       {"id": "cohere/embed", "rate_limit_tier": "embeddings"}]


@pytest.fixture
def gh(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp-test")
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (CAT, None))  # type: ignore[arg-type]
    return tmp_path


def _ok(text: str = "{}"):
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 5}}, None


def test_no_token_is_zero_budget_not_an_error() -> None:
    assert ov.seat() is None and ov.budget_left() == 0
    assert "no overflow seat" in (ov.chat("x")[1] or "")


def test_catalog_unread_is_unmeasured_then_sized_by_tier(gh, monkeypatch) -> None:
    assert ov.budget_left() == -1
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: _ok())
    assert ov.chat("x") == ("{}", None)
    assert ov.budget_left() == 150 + 50 - 1, "embeddings counted, or the call was not"


def test_a_daily_429_closes_that_model_and_moves_on(gh, monkeypatch) -> None:
    sent: list[str] = []

    def post(u, k, payload, **kw):
        mid = json.loads(payload)["model"]
        sent.append(mid)
        if mid == "openai/gpt-4.1-mini":
            return {}, "HTTP 429: Rate limit of 150 per 86400s exceeded for UserByModelByDay"
        return _ok("hi")

    monkeypatch.setattr(llm_seat, "_post", post)
    assert ov.chat("x") == ("hi", None)
    assert ov.chat("y") == ("hi", None)
    assert sent == ["openai/gpt-4.1-mini", "openai/gpt-4.1", "openai/gpt-4.1"]


def test_an_unauthorised_token_closes_the_day(gh, monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: ({}, "HTTP 401: Bad credentials"))
    _, err = ov.chat("x")
    assert err and "per-day" in err and ov.budget_left() == 0


def test_overflow_rows_do_not_spend_openrouters_day(gh, monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: _ok())
    ov.chat("x")
    row = json.loads((gh / "spend.jsonl").read_text().splitlines()[-1])
    assert row["seat"] == "github_models" and row["usd"] == 0.0 and row["free"] is True
    assert llm_seat.calls_today() == 0


def test_overflow_is_only_used_after_openrouters_day(gh, monkeypatch) -> None:
    used: list[str] = []
    monkeypatch.setattr(ov, "chat", lambda *a, **k: used.append("gh") or ("ok", None))
    monkeypatch.setattr(llm_seat, "chat", lambda *a, **k: ("primary", None))
    assert ov.chat_with_overflow("x") == ("primary", None) and not used
    monkeypatch.setattr(llm_seat, "chat", lambda *a, **k: (
        "", "free-tier daily request budget exhausted: 519 call(s) today"))
    assert ov.chat_with_overflow("x") == ("ok", None) and used == ["gh"]
    monkeypatch.setattr(llm_seat, "chat", lambda *a, **k: ("", "HTTP 429: slow down"))
    assert ov.chat_with_overflow("x")[1] == "HTTP 429: slow down", "a burst is not the day"
