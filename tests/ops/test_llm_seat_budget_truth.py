"""The seat must tell the truth about what it spent and what the provider allows.

Every test here pins a defect MEASURED on the trading box on 2026-09-24, and each one was
invisible before it was measured rather than merely unfixed:

  * a free call booked phantom dollars against the $20 cap ($234.26 of them that month), which
    would have taken every organ dark the instant the principal enabled the paid tier;
  * the day's "ceiling" was recorded in COMPLETIONS while the provider refuses in REQUESTS, and
    the smaller number then propagated into four docstrings as the desk's research capacity;
  * nothing recorded WHICH organ spent the one shared allowance, so it could not be allocated;
  * an empty completion was indistinguishable downstream from a refusal, so a truncated reasoning
    reply and a model that would not answer produced the same report.
"""
from __future__ import annotations

import json

import pytest

from libs.ops import llm_seat


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    p = tmp_path / "llm_spend.jsonl"
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", p)
    return p


def _seat() -> llm_seat.Seat:
    return llm_seat.Seat(name="openrouter", base_url="https://example.invalid/v1",
                         key="not-a-real-key", model="", source="test")


def _body(tokens: int = 100, *, content: str = "ok", finish: str = "stop") -> dict:
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": {"total_tokens": tokens, "prompt_tokens": 40, "completion_tokens": 60,
                      "completion_tokens_details": {"reasoning_tokens": 55}}}


def _rows(p):
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


# --------------------------------------------------------------------- a free call costs nothing

def test_free_model_books_zero_usd(ledger):
    """The whole paid lane hangs on this: a free call must not accrue estimated spend."""
    llm_seat._record_spend(_seat(), "nvidia/nemotron-3-ultra-550b-a55b:free", _body(500_000))
    row = _rows(ledger)[0]
    assert row["usd"] == 0.0
    assert row["free"] is True
    assert row["tokens"] == 500_000, "tokens are still recorded -- only the CHARGE is zero"


def test_metered_model_still_books_spend(ledger):
    """The cap must keep working for calls that genuinely cost money."""
    llm_seat._record_spend(_seat(), "openai/gpt-5", _body(10_000))
    row = _rows(ledger)[0]
    assert row["usd"] > 0.0
    assert row["free"] is False


def test_month_rollup_ignores_free_rows_already_written(ledger, monkeypatch):
    """The ledger is append-only, so the ROLLUP is where the historic phantom spend is corrected.

    Without this the cap stays tripped by its own past for the rest of the month -- and the cap is
    exactly what gates the paid tier the principal would be buying.
    """
    ledger.write_text(
        json.dumps({"utc": "2026-09-01T00:00:00+00:00", "model": "x/y:free", "usd": 234.26})
        + "\n"
        + json.dumps({"utc": "2026-09-01T00:00:00+00:00", "model": "openai/gpt-5", "usd": 1.5})
        + "\n", encoding="utf-8")
    import datetime as _dt
    got = llm_seat.month_spend_usd(_dt.datetime(2026, 9, 15, tzinfo=_dt.UTC))
    assert got == pytest.approx(1.5), "a `:free` row charges nothing, retroactively included"


@pytest.mark.parametrize("model,free", [
    ("nvidia/nemotron-3-ultra-550b-a55b:free", True),
    ("meta/llama-4-405b-free", True),
    ("openai/gpt-5", False),
    ("", False),
])
def test_is_free_model(model, free):
    assert llm_seat.is_free_model(model) is free


# ----------------------------------------------------- the ceiling is recorded in a labelled unit

def test_limit_hit_records_provider_unit_beside_our_own(tmp_path, monkeypatch, ledger):
    """`ceiling` (ours, completions) and `provider_limit` (theirs, requests) must both be named.

    The 2026-09-23 reading was 460 and 1000. The desk quoted 458 as its capacity for a day.
    """
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    ledger.write_text("".join(
        json.dumps({"utc": "2026-09-24T01:00:00+00:00", "model": "x:free", "usd": 0.0}) + "\n"
        for _ in range(460)), encoding="utf-8")
    import datetime as _dt
    now = _dt.datetime(2026, 9, 24, 12, tzinfo=_dt.UTC)
    llm_seat.note_free_limit_hit(
        'HTTP 429: {"error":{"message":"Rate limit exceeded: free-models-per-day-high-balance.",'
        '"metadata":{"headers":{"X-RateLimit-Limit":"1000","X-RateLimit-Remaining":"0"}}}}', now)
    doc = json.loads((tmp_path / "ceiling.json").read_text("utf-8"))
    assert doc["ceiling"] == 460
    assert doc["provider_limit"] == 1000
    assert doc["invisible_requests"] == 540
    assert "completions" in doc["ceiling_unit"]
    assert "REQUESTS" in doc["provider_limit_unit"]


def test_limit_hit_without_a_header_still_records_our_count(tmp_path, monkeypatch, ledger):
    """A refusal that names no limit must not lose the observation it DOES carry."""
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    ledger.write_text("", encoding="utf-8")
    llm_seat.note_free_limit_hit("HTTP 429: slow down")
    doc = json.loads((tmp_path / "ceiling.json").read_text("utf-8"))
    assert doc["ceiling"] == 0
    assert "provider_limit" not in doc, "absence is UNMEASURED, never a guessed number"


def test_free_daily_max_never_rises_above_the_configured_ceiling(tmp_path, monkeypatch):
    """A measured refusal may only LOWER the day's belief, never raise it."""
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    monkeypatch.delenv("QUANT_FREE_DAILY_MAX", raising=False)
    import datetime as _dt
    today = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d")
    (tmp_path / "ceiling.json").write_text(
        json.dumps({"date": today, "ceiling": 99999}), encoding="utf-8")
    assert llm_seat.free_daily_max() == llm_seat.DEFAULT_FREE_DAILY_MAX


# ------------------------------------------------------------------- the budget carries a name

def test_spend_row_names_the_calling_organ(ledger, monkeypatch):
    monkeypatch.setenv("QUANT_LLM_ORGAN", "deepening_worker")
    llm_seat._record_spend(_seat(), "x/y:free", _body())
    assert _rows(ledger)[0]["organ"] == "deepening_worker"


def test_organ_defaults_to_something_rather_than_nothing(ledger, monkeypatch):
    """An unattributed call is still labelled, so the census can report the share it cannot name."""
    monkeypatch.delenv("QUANT_LLM_ORGAN", raising=False)
    llm_seat._record_spend(_seat(), "x/y:free", _body())
    assert _rows(ledger)[0]["organ"]


# ------------------------------------------- truncation and refusal must not look the same

def test_empty_completion_is_recorded_as_such(ledger):
    """`finish_reason=length` with empty content IS truncation, and downstream cannot see it.

    Every caller reports this as "reply was not a JSON object" -- 456 times on the day measured,
    58% of that day's completed calls -- which reads like a model that would not answer.
    """
    llm_seat._record_spend(_seat(), "x/y:free", _body(content="", finish="length"))
    row = _rows(ledger)[0]
    assert row["empty_content"] is True
    assert row["finish_reason"] == "length"
    assert row["reasoning_tokens"] == 55
    assert row["completion_tokens"] == 60


def test_non_empty_completion_is_not_flagged(ledger):
    llm_seat._record_spend(_seat(), "x/y:free", _body(content='{"a":1}'))
    assert _rows(ledger)[0]["empty_content"] is False


def test_record_spend_survives_a_body_with_no_usage_or_choices(ledger):
    """A ledger write must never take down the organ, whatever the provider returned."""
    llm_seat._record_spend(_seat(), "x/y:free", {})
    row = _rows(ledger)[0]
    assert row["tokens"] == 0
    assert "finish_reason" not in row


# --------------------------------------------------------------- the JSON contract is expressible

def test_response_format_degrades_rather_than_failing():
    """A free model with no structured-output support must not cost the caller its request."""
    assert "response_format" in llm_seat._DEGRADABLE
    assert (llm_seat._DEGRADABLE.index("response_format")
            < llm_seat._DEGRADABLE.index("reasoning_effort")), \
        "effort is the principal's explicit ask and is surrendered last"
    assert llm_seat.JSON_OBJECT == {"type": "json_object"}


def test_provider_free_quota_is_unmeasured_when_dark(monkeypatch):
    """No seat means UNMEASURED, never a zero budget -- absence is not exhaustion (L1.28a)."""
    monkeypatch.setattr(llm_seat, "primary_seat", lambda: None)
    assert llm_seat.provider_free_quota() == {}
