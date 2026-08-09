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
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    seat = llm_seat.primary_seat()
    assert seat is not None
    assert seat.name == "openrouter" and seat.source == "env:OPENROUTER_API_KEY"
    assert seat.base_url == "https://openrouter.ai/api/v1"


def test_openrouter_outranks_the_others(monkeypatch) -> None:
    """A DIRECT vendor key bounds auto-upgrade to one catalogue: OpenAI upgrades gpt-5 -> gpt-6
    forever and can never reach a better model from anyone else. OpenRouter lists the whole
    landscape, so the same version parser upgrades across the MARKET rather than within a
    supplier -- which is what a standing 'always run the best available' order actually requires."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    seat = llm_seat.primary_seat()
    assert seat.name == "openrouter"
    assert seat.base_url == "https://openrouter.ai/api/v1"


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
    assert not text and "OPENROUTER_API_KEY" in err


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


# --------------------------------------------------- flagship selection that upgrades itself

def test_the_highest_version_wins_so_upgrades_are_automatic(monkeypatch) -> None:
    """THE POINT OF PARSING RATHER THAN LISTING. A hardcoded preference list containing `gpt-5`
    keeps choosing it forever after `gpt-6` ships -- silently, while every status line reads
    healthy. Same bomb as a pinned model string, with a longer fuse."""
    today = ["gpt-4o", "gpt-5", "gpt-5-mini", "o3", "babbage-002"]
    tomorrow = [*today, "gpt-6", "gpt-6-mini", "o5"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for listing, expect in ((today, "gpt-5"), (tomorrow, "gpt-6")):
        monkeypatch.setattr(llm_seat, "_get",
                            lambda *a, _l=listing, **k: ({"data": [{"id": i} for i in _l]}, None))
        model, err = llm_seat.discover_model(llm_seat.primary_seat())
        assert (model, err) == (expect, None)


def test_cheaper_variants_are_refused_not_merely_ranked_low() -> None:
    """`mini` and `nano` sort adjacent to the flagship and often carry the SAME version number, so
    ranking alone would let a gpt-6-mini beat a gpt-5 and quietly shrink the brain."""
    for bad in ("gpt-5-mini", "gpt-6-nano", "o4-mini", "gpt-4-turbo",
                "deepseek/deepseek-r1:free", "meta-llama/llama-3-8b-instruct"):
        assert llm_seat.flagship_rank(bad) is None, bad
    for good in ("gpt-5", "gpt-6", "openai/gpt-5", "o5", "x-ai/grok-4"):
        assert llm_seat.flagship_rank(good) is not None, good


def test_a_flagship_beats_a_higher_versioned_downgrade(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("gpt-5", "gpt-9-mini", "gpt-9-nano")]}, None))
    assert llm_seat.discover_model(llm_seat.primary_seat())[0] == "gpt-5"


def test_openrouter_prefixed_ids_are_understood(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: ({"data": [{"id": i} for i in (
        "openai/gpt-5", "openai/gpt-5-mini", "anthropic/claude-opus-4",
        "deepseek/deepseek-r1:free")]}, None))
    assert llm_seat.discover_model(llm_seat.primary_seat())[0] == "openai/gpt-5"


def test_the_bare_alias_beats_a_dated_snapshot(monkeypatch) -> None:
    """The bare name is the provider's stable pointer; decorated ids are snapshots that get
    retired under you."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("gpt-5-2026-04-01", "gpt-5")]}, None))
    assert llm_seat.discover_model(llm_seat.primary_seat())[0] == "gpt-5"


def test_no_flagship_names_what_was_offered(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "_get",
                        lambda *a, **k: ({"data": [{"id": "text-embedding-3-large"}]}, None))
    model, err = llm_seat.discover_model(llm_seat.primary_seat())
    assert not model and "text-embedding-3-large" in err


# ------------------------------------------------------------------- max effort, degraded safely

def test_max_effort_is_requested_by_default(monkeypatch) -> None:
    seen: list[dict] = []
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post", lambda u, k, payload, **kw: (
        seen.append(json.loads(payload)) or
        ({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 10}}, None)))
    llm_seat.chat("hi")
    assert seen[0]["reasoning_effort"] == llm_seat.DEFAULT_EFFORT == "high"


def test_a_provider_that_refuses_effort_still_gets_an_answer(monkeypatch) -> None:
    """A seat going dark because it asked for too much thinking would be a self-inflicted outage."""
    calls: list[dict] = []

    def post(u, k, payload, **kw):
        body = json.loads(payload)
        calls.append(body)
        if "reasoning_effort" in body:
            return {}, "HTTP 400: Unsupported parameter: 'reasoning_effort'"
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 10}}, None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post", post)
    text, err = llm_seat.chat("hi")
    assert (text, err) == ("ok", None)
    assert len(calls) == 2 and "reasoning_effort" not in calls[-1]


def test_the_token_cap_is_renamed_rather_than_dropped(monkeypatch) -> None:
    """Losing the cap entirely would let one call run away against a metered API."""
    calls: list[dict] = []

    def post(u, k, payload, **kw):
        body = json.loads(payload)
        calls.append(body)
        if "max_completion_tokens" in body:
            return {}, "HTTP 400: Unsupported parameter: 'max_completion_tokens', use 'max_tokens'"
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 10}}, None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post", post)
    assert llm_seat.chat("hi", max_tokens=1234)[0] == "ok"
    assert calls[-1]["max_tokens"] == 1234


def test_a_400_that_dropping_cannot_fix_is_surfaced(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "discover_model", lambda *a, **k: ("gpt-5", None))
    monkeypatch.setattr(llm_seat, "_post",
                        lambda *a, **k: ({}, "HTTP 400: model not available in your region"))
    _, err = llm_seat.chat("hi")
    assert "region" in err


def test_a_dated_snapshot_never_outranks_its_own_stable_alias() -> None:
    """`gpt-5-2026-04-01` parsed as minor version 2026 and beat `gpt-5`. Snapshots get retired
    under you; the bare alias does not, so a hyphen-plus-digits is a DATE and only a dot
    introduces a minor version."""
    assert llm_seat.flagship_rank("gpt-5")[:2] >= llm_seat.flagship_rank("gpt-5-2026-04-01")[:2]
    assert llm_seat.flagship_rank("gpt-5.1")[:2] > llm_seat.flagship_rank("gpt-5")[:2]


def test_there_is_no_version_ceiling(monkeypatch) -> None:
    """"Not just to gpt6 then never." The version is parsed, so there is no upper bound to reach."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for listing, expect in ((["gpt-5", "gpt-7"], "gpt-7"),
                            (["gpt-7", "gpt-12"], "gpt-12"),
                            (["gpt-12", "gpt-40"], "gpt-40")):
        monkeypatch.setattr(llm_seat, "_get",
                            lambda *a, _l=listing, **k: ({"data": [{"id": i} for i in _l]}, None))
        assert llm_seat.discover_model(llm_seat.primary_seat())[0] == expect


def test_a_brand_new_family_is_still_discovered(monkeypatch) -> None:
    """The version has no ceiling, but the FAMILY list is still a list -- and a new family under a
    new name would match nothing and be invisible forever. That is the same 'then never' failure
    one level up, and it is the one that bites when the landscape actually moves."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("titan-3", "titan-3-mini", "titan-2")]}, None))
    assert llm_seat.discover_model(llm_seat.primary_seat())[0] == "titan-3"


def test_a_known_family_still_wins_over_an_unknown_one(monkeypatch) -> None:
    """An unrecognised name is weaker evidence than a recognised one -- but 'unrecognised' must
    not mean 'unusable'."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("titan-9", "gpt-5")]}, None))
    assert llm_seat.discover_model(llm_seat.primary_seat())[0] == "gpt-5"


# ------------------------------------------------------- pinned models elsewhere on the desk

def test_a_pin_below_the_flagship_is_reported(monkeypatch) -> None:
    """THE COVERAGE THIS MODULE DOES NOT OTHERWISE HAVE. Discovery keeps THIS seat current, but
    eleven other organs read llm_panel.json where every provider carries a hardcoded model. A pin
    is invisible by construction: the organ runs, returns text, reports success, and quietly
    executes something superseded -- for years, if nobody looks."""
    llm_seat.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SECRETS.write_text(json.dumps(
        {"providers": [{"name": "panel", "key": "k", "model": "gpt-4o"}]}), "utf-8")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("gpt-4o", "gpt-5")]}, None))
    pins = llm_seat.stale_pins()
    assert len(pins) == 1
    assert pins[0]["stale"] is True and pins[0]["flagship"] == "gpt-5"
    assert "PINNED BELOW FLAGSHIP" in pins[0]["note"]


def test_a_pin_at_the_flagship_is_not_flagged(monkeypatch) -> None:
    llm_seat.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SECRETS.write_text(json.dumps(
        {"providers": [{"name": "panel", "key": "k", "model": "gpt-5"}]}), "utf-8")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("gpt-4o", "gpt-5")]}, None))
    assert llm_seat.stale_pins()[0]["stale"] is False


def test_an_unpinned_seat_needs_no_check(monkeypatch) -> None:
    """Discovery already keeps it current; probing it would spend a request to learn nothing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_seat.stale_pins() == []


def test_stale_pins_reach_status(monkeypatch) -> None:
    """So it lands in front of the CRO and the doctor without anyone remembering to ask."""
    llm_seat.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    llm_seat.SECRETS.write_text(json.dumps(
        {"providers": [{"name": "panel", "key": "k", "model": "gpt-4o"}]}), "utf-8")
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (
        {"data": [{"id": i} for i in ("gpt-4o", "gpt-5")]}, None))
    st = llm_seat.status()
    assert st["stale_pins"][0]["pinned"] == "gpt-4o"
    assert st["effort"] == "high"
