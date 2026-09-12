"""Free tier is the DEFAULT, and it must never be the reason a seat goes dark.

The principal's instruction, 2026-09-12: "make everything free tier on openrouter... all the paid
run things js run on free tiers instead... make all as frequent as possible without hitting limits
or going dark on the free tiers".

The trap this file pins is subtle and was caught only by running it: `:free` and `-free` are
entries in `_DOWNGRADE_TOKENS`, so `flagship_rank` refuses every free id BY DESIGN -- that is what
stops a `gpt-6:free` outranking a paid `gpt-6` when both are on the table. Narrow `ids` to the free
ones without accounting for that and discovery returns "no flagship model found", every organ goes
dark, and the error reads like a provider outage rather than like a policy change we made.
"""
from __future__ import annotations

import json

import pytest

from libs.ops import llm_seat


class _Seat:
    model = ""
    base_url = "https://example/v1"
    key = "k"
    name = "openrouter"


def _listing(monkeypatch, ids: list[str]) -> None:
    monkeypatch.setattr(llm_seat, "_get",
                        lambda url, key, *, timeout: ({"data": [{"id": i} for i in ids]}, None))


def test_free_tier_is_on_by_default(monkeypatch) -> None:
    """The safe state is the automatic one: spending requires an explicit opt-out."""
    monkeypatch.delenv("QUANT_FREE_TIER", raising=False)
    assert llm_seat.free_tier_only() is True
    monkeypatch.setenv("QUANT_FREE_TIER", "0")
    assert llm_seat.free_tier_only() is False


def test_the_best_free_model_wins_not_merely_a_free_one(monkeypatch) -> None:
    """Auto-upgrade is preserved INSIDE the free tier -- the version still decides."""
    monkeypatch.setenv("QUANT_FREE_TIER", "1")
    _listing(monkeypatch, ["openai/gpt-5:free", "openai/gpt-6:free", "openai/gpt-6"])
    assert llm_seat.discover_model(_Seat())[0] == "openai/gpt-6:free"


def test_paid_flagship_still_wins_when_spending_is_re_enabled(monkeypatch) -> None:
    monkeypatch.setenv("QUANT_FREE_TIER", "0")
    _listing(monkeypatch, ["openai/gpt-5:free", "openai/gpt-6:free", "openai/gpt-6"])
    assert llm_seat.discover_model(_Seat())[0] == "openai/gpt-6"


def test_a_provider_with_no_free_models_does_not_go_dark(monkeypatch) -> None:
    """Free-first is a PREFERENCE. A provider serving nothing free must still answer, because a
    dark seat answers nothing and that is strictly worse than a call we did not plan."""
    monkeypatch.setenv("QUANT_FREE_TIER", "1")
    _listing(monkeypatch, ["openai/gpt-6"])
    model, err = llm_seat.discover_model(_Seat())
    assert err is None and model == "openai/gpt-6"


def test_unrankable_free_models_still_answer(monkeypatch) -> None:
    """A free id carrying no parseable version is weaker evidence, never unusable."""
    monkeypatch.setenv("QUANT_FREE_TIER", "1")
    _listing(monkeypatch, ["vendor/mystery:free"])
    model, err = llm_seat.discover_model(_Seat())
    assert err is None and model == "vendor/mystery:free"


def test_the_dollar_cap_cannot_silence_a_free_run(monkeypatch, tmp_path) -> None:
    """The ledger books an ESTIMATED cost, so a month of free calls would accrue phantom spend and
    then refuse free calls for the rest of the month -- dark over money never spent."""
    monkeypatch.setenv("QUANT_FREE_TIER", "1")
    monkeypatch.setattr(llm_seat, "month_spend_usd", lambda *a, **k: 999.0)
    monkeypatch.setattr(llm_seat, "monthly_cap_usd", lambda: 20.0)
    monkeypatch.setattr(llm_seat, "primary_seat", lambda: _Seat())
    _listing(monkeypatch, ["vendor/m:free"])
    monkeypatch.setattr(llm_seat, "_post_with_degrade",
                        lambda *a, **k: ({"choices": [{"message": {"content": "ok"}}]}, None))
    monkeypatch.setattr(llm_seat, "_record_spend", lambda *a, **k: None)
    text, err = llm_seat.chat("hi")
    assert err is None and text == "ok"


def test_the_daily_request_budget_skips_rather_than_burning_the_account(
        monkeypatch, tmp_path) -> None:
    """The free tier's real limit is requests per day. Stopping one call short is the difference
    between an organ skipping a cycle and the ACCOUNT being rate-limited dark for the day -- which
    takes every other organ with it, not just the one that spent the last request."""
    ledger = tmp_path / "llm_spend.jsonl"
    now = llm_seat.datetime.now(llm_seat.UTC).isoformat(timespec="seconds")
    ledger.write_text("\n".join(json.dumps({"utc": now, "usd": 0.0}) for _ in range(5)),
                      encoding="utf-8")
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", ledger)
    monkeypatch.setenv("QUANT_FREE_TIER", "1")
    monkeypatch.setenv("QUANT_FREE_DAILY_MAX", "5")
    assert llm_seat.calls_today() == 5
    assert llm_seat.free_budget_left() == 0

    monkeypatch.setattr(llm_seat, "primary_seat", lambda: _Seat())
    text, err = llm_seat.chat("hi")
    assert text == ""
    assert err is not None and "daily request budget exhausted" in err
    assert "SKIP, not a failure" in err


@pytest.mark.parametrize("raw,expected", [("", 900), ("not-a-number", 900), ("40", 40), ("0", 1)])
def test_the_daily_ceiling_is_configurable_and_never_zero(monkeypatch, raw, expected) -> None:
    """An account that has never purchased credit is capped at 50/day, not 1000 -- so the number
    has to be settable. A ceiling of zero would be a permanently dark desk, so it floors at one."""
    if raw:
        monkeypatch.setenv("QUANT_FREE_DAILY_MAX", raw)
    else:
        monkeypatch.delenv("QUANT_FREE_DAILY_MAX", raising=False)
    assert llm_seat.free_daily_max() == expected
