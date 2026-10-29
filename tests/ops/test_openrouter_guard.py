"""NO OPENROUTER CREDIT CAN BE SPENT UNLESS THE PRINCIPAL SWITCHES PAID ON.

  * a request naming a model without `:free` is refused before it leaves, on every path that
    posts: the guard itself, `llm_seat`, and every file that builds a
    `/chat/completions` request (a fence, so a new caller cannot skip it);
  * a pinned paid id on an OpenRouter seat is replaced by the best free id, never sent;
  * QUANT_LLM_LAB_PAID=1 is the only way past, and other providers' hosts are untouched;
  * budgets read the account's own daily limit, so credit moves them from 50 to 1,000.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from libs.ops import llm_seat
from libs.ops import openrouter_guard as g

ROOT = Path(__file__).resolve().parents[2]
OR = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture(autouse=True)
def _free_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(g.PAID_ENV, raising=False)


@pytest.mark.parametrize("body", [
    {"model": "openai/gpt-6"},
    {"model": "openrouter/auto"},
    {"model": "deepseek/deepseek-r2-free"},
    {"model": "meta-llama/llama-4:free", "models": ["anthropic/claude-5"]},
    {},
    b"not json",
])
def test_paid_or_unprovable_ids_are_refused(body: Any) -> None:
    assert g.refusal(OR, body)
    with pytest.raises(g.PaidModelRefused):
        g.check(OR, body)


def test_free_ids_pass_and_reads_are_not_requests() -> None:
    assert g.refusal(OR, {"model": "qwen/qwen3-235b:free",
                          "models": ["meta-llama/llama-4:free"]}) is None
    assert g.refusal(OR, json.dumps({"model": "x/y:free"}).encode()) is None
    assert g.refusal("https://openrouter.ai/api/v1/key", None) is None
    assert g.refusal("https://api.groq.com/openai/v1/chat/completions",
                     {"model": "llama-3.3-70b"}) is None


def test_only_the_principals_switch_opens_paid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_FREE_TIER", "0")
    assert g.refusal(OR, {"model": "openai/gpt-6"})          # the old switch is not enough
    monkeypatch.setenv(g.PAID_ENV, "1")
    assert g.refusal(OR, {"model": "openai/gpt-6"}) is None


def test_check_request_reads_a_urllib_request() -> None:
    req = urllib.request.Request(OR, data=json.dumps({"model": "openai/gpt-6"}).encode(),
                                 method="POST")
    with pytest.raises(g.PaidModelRefused):
        g.check_request(req)


def _no_network(*a: Any, **k: Any) -> Any:
    raise AssertionError("a refused request reached the network")


def test_llm_seat_post_refuses_before_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    body, err = llm_seat._post(OR, "k", json.dumps({"model": "openai/gpt-6"}).encode(),
                               timeout=1)
    assert body == {} and err and "openrouter_guard" in err


def test_pinned_paid_seat_model_is_swapped_for_a_free_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    seat = llm_seat.Seat("openrouter", "https://openrouter.ai/api/v1", "k",
                         model="openai/gpt-6")
    listing = {"data": [{"id": "openai/gpt-6"}, {"id": "qwen/qwen3-235b:free"}]}
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: (listing, None))
    monkeypatch.setenv("QUANT_FREE_TIER", "0")                # even with spending "on"
    model, err = llm_seat.discover_model(seat)
    assert err is None and model.endswith(":free")


def test_no_free_listing_goes_dark_rather_than_paid(monkeypatch: pytest.MonkeyPatch) -> None:
    seat = llm_seat.Seat("openrouter", "https://openrouter.ai/api/v1", "k")
    monkeypatch.setattr(llm_seat, "_get",
                        lambda *a, **k: ({"data": [{"id": "openai/gpt-6"}]}, None))
    monkeypatch.setenv("QUANT_FREE_TIER", "0")
    model, err = llm_seat.discover_model(seat)
    assert model == "" and err and ":free" in err


def test_every_chat_completions_caller_goes_through_the_guard() -> None:
    """The fence: a file that builds a /chat/completions request must call the guard."""
    skip = {"libs/ops/openrouter_guard.py", "scripts/doctrine.py", "scripts/prove_future.py",
            "libs/llm/effort.py"}
    missing = []
    for path in list(ROOT.glob("libs/**/*.py")) + list(ROOT.glob("scripts/**/*.py")) + \
            list(ROOT.glob("desks/**/*.py")) + list(ROOT.glob("ops/**/*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if "/tests/" in f"/{rel}" or "/_retired/" in rel or rel in skip:
            continue
        try:
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        builds = re.search(r"chat/completions[\"']?\s*,|ENDPOINT\s*=\s*[\"']https://openrouter",
                           text)
        if builds and "openrouter_guard" not in text:
            missing.append(rel)
    assert not missing, f"posts to /chat/completions without openrouter_guard: {missing}"


def test_daily_limit_follows_the_account(monkeypatch: pytest.MonkeyPatch) -> None:
    free = g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": True,
                                                              "limit": 0}}, now=1000.0)
    assert free["daily_limit"] == 50 and free["credit_limit_usd"] == 0
    credited = g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": False}},
                          now=2000.0)
    assert credited["daily_limit"] == 1000
    assert g.daily_limit(cached_only=True, now=2100.0) == 1000
    published = g.key_info(refresh=True, now=3000.0, fetch=lambda u: {"data": {
        "is_free_tier": False,
        "free_model_daily_requests": {"limit": 1200, "used": 3, "remaining": 1197}}})
    assert published["daily_limit"] == 1200 and published["remaining"] == 1197


def test_unreachable_key_info_is_unmeasured_not_zero() -> None:
    def boom(u: str) -> Any:
        raise OSError("offline")
    assert g.key_info(refresh=True, fetch=boom) == {}
    assert g.daily_limit(cached_only=True) is None


def test_seat_budget_scales_with_the_measured_limit(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_FREE_DAILY_MAX", raising=False)
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    assert llm_seat.free_daily_max() == llm_seat.DEFAULT_FREE_DAILY_MAX   # UNMEASURED
    g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": True}})
    assert llm_seat.free_daily_max() < 50
    g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": False}})
    assert 900 < llm_seat.free_daily_max() < 1000
