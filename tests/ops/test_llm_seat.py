"""The seat: key resolution, model discovery, and the spend cap.

test_the_cap_is_checked_before_spending is the one that protects real money. The desk has already
been burned the other way round -- run_external_panel discovered credit exhaustion mid-run, after
the last of the balance had been spent on a panel that returned nothing.
"""
from __future__ import annotations

import json

import pytest

from libs.ops import llm_seat


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """No test may read the real environment's keys or write the real spend ledger."""
    for var, _, _ in llm_seat.KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("LLM_MONTHLY_CAP_USD", raising=False)
    monkeypatch.setattr(llm_seat, "SECRETS", tmp_path / "llm_panel.json")
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", tmp_path / "spend.jsonl")


# ------------------------------------------------------------------------------ key resolution

def test_a_dark_desk_reports_the_blocker_rather_than_raising() -> None:
    """A missing credential is a known state of the world. An organ that raises on it gets
    removed from the cadence, and a removed organ recommends nothing."""
    assert llm_seat.primary_seat() is None
    st = llm_seat.status()
    assert st["n_seats"] == 0 and "DARK" in st["blocker"]


def test_the_environment_is_read_first(monkeypatch) -> None:
    """THE WHOLE POINT. The secrets file lives on a box that gets reclaimed; an exported variable
    is set once and survives every container the desk is ever given."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    seat = llm_seat.primary_seat()
    assert seat is not None
    assert seat.name == "openai" and seat.source == "env:OPENAI_API_KEY"
    assert seat.base_url == "https://api.openai.com/v1"


def test_openai_outranks_the_others(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_seat.primary_seat().name == "openai"


def test_the_secrets_file_still_works(monkeypatch) -> None:
    llm_seat.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SECRETS.write_text(json.dumps(
        {"providers": [{"name": "panel", "key": "k", "model": "m"}]}), "utf-8")
    seats = llm_seat.seats()
    assert len(seats) == 1 and seats[0].source == "file:llm_panel.json"


def test_a_corrupt_secrets_file_does_not_take_down_the_organ() -> None:
    llm_seat.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SECRETS.write_text("{not json", "utf-8")
    assert llm_seat.seats() == []


def test_an_empty_key_is_not_a_seat(monkeypatch) -> None:
    """An exported-but-blank variable is the most common way a credential looks present and is
    not; treating it as a seat produces a 401 that reads like a provider outage."""
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert llm_seat.primary_seat() is None


def test_a_key_never_appears_in_full_in_a_report(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-do-not-log")
    seat = llm_seat.primary_seat()
    assert "secret-value" not in seat.redacted
    assert "sk-secret-value-do-not-log" not in json.dumps(llm_seat.status())


# ---------------------------------------------------------------------------- model discovery

def test_an_explicit_model_wins_over_discovery(monkeypatch) -> None:
    """Discovery is the default, not an override of the principal's choice."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-pinned")
    seat = llm_seat.primary_seat()
    model, err = llm_seat.discover_model(seat)
    assert model == "gpt-pinned" and err is None


def test_discovery_picks_by_preference_and_prefers_the_bare_alias(monkeypatch) -> None:
    """The bare name is the provider's stable alias; the decorated ones are snapshots that get
    retired, so a pinned snapshot is a time bomb with a later fuse."""
    listed = ["babbage-002", "gpt-4o-mini", "gpt-5-chat-latest-preview", "gpt-5", "gpt-4.1"]
    monkeypatch.setattr(llm_seat, "_get",
                        lambda *a, **k: ({"data": [{"id": i} for i in listed]}, None))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model, err = llm_seat.discover_model(llm_seat.primary_seat())
    assert model == "gpt-5" and err is None


def test_no_preferred_model_names_what_was_actually_offered(monkeypatch) -> None:
    """'None of the models matched' is unactionable; the list is what lets a human fix it."""
    monkeypatch.setattr(llm_seat, "_get",
                        lambda *a, **k: ({"data": [{"id": "llama-2-7b"}]}, None))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model, err = llm_seat.discover_model(llm_seat.primary_seat())
    assert not model and "llama-2-7b" in err


# --------------------------------------------------------------------------------- the cap

def test_the_cap_is_checked_before_spending(monkeypatch) -> None:
    """THE TEST THAT PROTECTS REAL MONEY. Checking after the call is how the desk's external panel
    discovered exhaustion mid-run with nothing to show for the spend."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MONTHLY_CAP_USD", "1.0")
    llm_seat.SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SPEND_LEDGER.write_text(json.dumps(
        {"utc": llm_seat.datetime.now(llm_seat.UTC).isoformat(), "usd": 5.0}) + "\n", "utf-8")

    called: list[str] = []
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: called.append("spent") or ({}, None))
    text, err = llm_seat.chat("hello")
    assert not text and "monthly cap reached" in err
    assert called == [], "a call was made after the cap was already breached"


def test_spend_from_other_months_does_not_count(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_seat.SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SPEND_LEDGER.write_text(json.dumps({"utc": "1999-01-01T00:00:00+00:00",
                                                 "usd": 999.0}) + "\n", "utf-8")
    assert llm_seat.month_spend_usd() == 0.0


def test_a_malformed_spend_row_does_not_take_down_the_audit() -> None:
    llm_seat.SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SPEND_LEDGER.write_text("{bad\n", "utf-8")
    assert llm_seat.month_spend_usd() == 0.0


def test_a_nonsense_cap_falls_back_to_the_default(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MONTHLY_CAP_USD", "lots")
    assert llm_seat.monthly_cap_usd() == llm_seat.DEFAULT_MONTHLY_CAP_USD


# ------------------------------------------------------------------------------ transport

def test_chat_without_a_seat_says_exactly_what_to_export() -> None:
    text, err = llm_seat.chat("hi")
    assert not text and "OPENAI_API_KEY" in err


def test_an_http_error_carries_its_body(monkeypatch) -> None:
    """A bare '400 Bad Request' from a model API is unactionable; the body names the parameter."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post",
                        lambda *a, **k: ({}, "HTTP 400: unsupported parameter temperature"))
    _, err = llm_seat.chat("hi")
    assert "temperature" in err


def test_an_unparseable_response_is_reported_not_raised(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: ({"unexpected": 1}, None))
    text, err = llm_seat.chat("hi")
    assert not text and "unparseable" in err


def test_a_successful_call_records_its_spend(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post", lambda *a, **k: (
        {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 5000}}, None))
    text, err = llm_seat.chat("hi")
    assert text == "ok" and err is None
    assert llm_seat.month_spend_usd() == pytest.approx(0.1)
