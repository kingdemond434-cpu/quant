"""NO OPENROUTER CREDIT CAN BE SPENT UNLESS THE PRINCIPAL SWITCHES PAID ON.

  * a request naming a model without `:free` is refused before it leaves, on every path that
    posts: the guard itself, `llm_seat`, `free_chain`, and every file that builds a
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

from libs.ops import free_chain as fc
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


def test_free_chain_request_refuses_before_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    body, err = fc._request(OR, "k", {"model": "openai/gpt-6"}, 1)
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


def test_budgets_scale_with_the_measured_limit(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_FREE_DAILY_MAX", raising=False)
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    monkeypatch.setattr(fc, "CONFIG", tmp_path / "providers.json")
    assert llm_seat.free_daily_max() == llm_seat.DEFAULT_FREE_DAILY_MAX   # UNMEASURED
    g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": True}})
    assert llm_seat.free_daily_max() < 50
    assert next(p for p in fc.providers() if p.name == "openrouter_free").daily_cap == 50
    g.key_info(refresh=True, fetch=lambda u: {"data": {"is_free_tier": False}})
    assert 900 < llm_seat.free_daily_max() < 1000
    assert next(p for p in fc.providers() if p.name == "openrouter_free").daily_cap == 1000


def test_a_model_hint_cannot_skip_the_free_filter(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit must-fix 3: a hinted model is tried only if the free catalogue lists it."""
    monkeypatch.setattr(fc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(fc, "CONFIG", tmp_path / "providers.json")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("QUANT_LOCAL_LLM_URLS", "")
    sent: list[str] = []

    def fake(url: str, key: str, payload: Any, timeout: float) -> tuple[dict, str | None]:
        if url.endswith("/models"):
            return {"data": [{"id": "openai/gpt-6", "pricing": {"prompt": "1",
                                                                "completion": "1"}},
                             {"id": "qwen/qwen3:free"}]}, None
        sent.append(str(payload.get("model")))
        return {"choices": [{"message": {"content": "ok"}}]}, None

    monkeypatch.setattr(fc, "_request", fake)
    monkeypatch.setattr(fc, "providers", lambda: [p for p in fc.DEFAULTS
                                                  if p.name == "openrouter_free"])
    reply = fc.chat("s", "u", model_hint="openrouter_free:openai/gpt-6", timeout=5)
    assert "openai/gpt-6" not in sent and reply.model == "qwen/qwen3:free"


def test_default_deny_covers_every_openrouter_post() -> None:
    """Follow-up to #353's audit: not only /completions -- any OpenRouter request with a body."""
    assert g.refusal("https://openrouter.ai/api/v1/images/generations",
                     {"model": "openai/gpt-image-2"})
    assert g.refusal("https://openrouter.ai/api/v1/auth/keys", {"name": "new"})
    assert g.refusal("https://openrouter.ai/api/v1/models", b"{}"), "a body is never a read"
    # A billable path is never a read, even bodiless and even under /models/ (audit MF3 on
    # #332: .../models/x/chat/completions passed here and was refused on live).
    assert g.refusal("https://openrouter.ai/api/v1/models/x/chat/completions", None)
    assert g.refusal("https://openrouter.ai/api/v1/chat/completions", None)
    for read in ("/models", "/key", "/credits", "/models/qwen/qwen3:free/endpoints"):
        assert g.refusal("https://openrouter.ai/api/v1" + read, None) is None


def test_the_wire_backstop_catches_a_url_built_in_pieces(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller the source fence cannot see is still stopped at urlopen itself."""
    reached: list[str] = []
    monkeypatch.setattr(g, "_ORIG_URLOPEN", lambda *a, **k: reached.append("sent"))
    monkeypatch.setattr(urllib.request, "urlopen", g._guarded_urlopen)
    host = "".join(["open", "router", ".ai"])
    req = urllib.request.Request(f"https://{host}/api/v1/chat/" + "completions",
                                 data=json.dumps({"model": "openai/gpt-6"}).encode())
    with pytest.raises(g.PaidModelRefused):
        urllib.request.urlopen(req, timeout=1)
    with pytest.raises(g.PaidModelRefused):
        urllib.request.urlopen(f"https://{host}/api/v1/chat/completions",
                               json.dumps({"model": "x/y"}).encode())
    urllib.request.urlopen(f"https://{host}/api/v1/models")
    assert reached == ["sent"]


def test_importing_the_guard_installs_the_backstop() -> None:
    import importlib
    importlib.reload(g)
    assert getattr(urllib.request.urlopen, "_openrouter_guard", False)
    # A reload must keep the function it wraps (CI 2026-10-13: it became None and every later
    # urlopen in the worker raised "'NoneType' object is not callable").
    assert callable(g._ORIG_URLOPEN) and not getattr(g._ORIG_URLOPEN, "_openrouter_guard", False)


def test_the_account_file_never_reaches_the_public_repo() -> None:
    assert "desks/mt5/data/llm_lab/openrouter_key.json" in (ROOT / ".gitignore").read_text()
