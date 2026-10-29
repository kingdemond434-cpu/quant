"""THE FREE CHAIN: free cloud, then another free provider, then a local model -- and never a bill.

  * a rate-limited provider cools and the chain moves on to the next rung, ending on local;
  * configuration can add a free endpoint and can never add a paid one;
  * a model_free provider sends only ids its catalogue marks free;
  * the whole call is bounded by its timeout, however many rungs are left;
  * status reports keys as present/absent and never prints one;
  * the proposer seat reaches the chain after the free panel and before the paid seat.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops import free_chain as fc
from libs.research import proposer_seat as ps


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(fc, "CONFIG", tmp_path / "providers.json")
    for p in fc.DEFAULTS:
        if p.key_env:
            monkeypatch.delenv(p.key_env, raising=False)
    monkeypatch.setenv("QUANT_LOCAL_LLM_URLS", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("QUANT_LOCAL_LLM_GUARD", "0")
    # The chain's behaviour across rungs is what these tests pin; account-tier rungs are opened
    # here, and test_account_tier_rungs_are_closed_by_default pins the real default.
    monkeypatch.setenv("QUANT_FREE_ONLY_ACCOUNTS", "all")
    return tmp_path


def _fake(responses: dict[str, Any], seen: list[str]):
    def request(url: str, key: str, payload: Any, timeout: float):
        seen.append(url)
        for frag, out in responses.items():
            if frag in url:
                return out
        return {}, "URLError"
    return request


def test_a_rate_limit_falls_through_to_the_local_rung(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test-not-real")
    seen: list[str] = []
    monkeypatch.setattr(fc, "_request", _fake({
        "groq.com/openai/v1/models": ({"data": [{"id": "llama-test"}]}, None),
        "groq.com/openai/v1/chat": ({}, "HTTP 429"),
        "11434/v1/models": ({"data": [{"id": "qwen-local"}]}, None),
        "11434/v1/chat": ({"choices": [{"message": {"content": "{\"a\": 1}"}}]}, None),
    }, seen))
    r = fc.chat("sys", "user", timeout=30)
    assert (r.provider, r.model, r.tier) == ("local0", "qwen-local", "local")
    assert any("groq" in u and "chat" in u for u in seen), "the free cloud rung was tried first"
    st = json.loads(fc.STATE.read_text())
    assert any(k.startswith("groq:") for k in st["cooldown"]), "the 429 cooled that model"


def test_config_can_add_a_free_endpoint_and_never_a_paid_one(_isolated: Path) -> None:
    fc.CONFIG.write_text(json.dumps({"providers": [
        {"name": "paid_flagship", "base_url": "https://api.example.com/v1", "tier": "paid"},
        {"name": "lmstudio", "base_url": "http://127.0.0.1:1234/v1", "tier": "local"},
        {"name": "gemini", "disabled": True}]}))
    names = [p.name for p in fc.providers()]
    assert "paid_flagship" not in names and "lmstudio" in names and "gemini" not in names


def test_a_model_free_provider_sends_only_free_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    monkeypatch.setattr(fc, "_request", _fake({"openrouter.ai/api/v1/models": ({"data": [
        {"id": "vendor/flagship", "pricing": {"prompt": "0.000003", "completion": "0.00001"}},
        {"id": "vendor/small:free"},
        {"id": "vendor/zero", "pricing": {"prompt": "0", "completion": "0"}}]}, None)}, []))
    p = next(p for p in fc.providers() if p.name == "openrouter_free")
    models, err = fc.list_models(p)
    assert err is None and set(models) == {"vendor/small:free", "vendor/zero"}


def test_the_call_is_bounded_by_its_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(fc, "_now", lambda: clock[0])

    def slow(url: str, key: str, payload: Any, timeout: float):
        clock[0] += 25.0
        if url.endswith("/models"):
            return {"data": [{"id": f"m{i}"} for i in range(4)]}, None
        return {}, "HTTP 500"
    monkeypatch.setattr(fc, "_request", slow)
    with pytest.raises(fc.ChainExhausted, match="deadline"):
        fc.chat("s", "u", timeout=60)


def test_status_never_prints_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "gsk-THIS-MUST-NOT-APPEAR"
    monkeypatch.setenv("GROQ_API_KEY", secret)
    doc = fc.status()
    assert secret not in json.dumps(doc)
    row = next(r for r in doc["providers"] if r["name"] == "groq")
    assert row["key_present"] is True and doc["verdict"] == "RAN"


def test_the_seat_reaches_the_chain_after_the_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ps, "_panel_module", lambda: None)
    monkeypatch.setattr(ps, "_seat_module", lambda: None)
    monkeypatch.setattr(fc, "chat", lambda *a, **k: fc.Reply("{\"x\": 1}", "local0", "q", "local"))
    text, model, err = ps._ask("generation", "prompt", timeout=10)
    assert err is None and model == "local0:q" and text


def test_a_hint_is_tried_first_and_an_exhausted_hint_falls_through(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def chat(*a: Any, model_hint: str = "", **k: Any) -> fc.Reply:
        calls.append(model_hint)
        raise fc.ChainExhausted("nothing")
    monkeypatch.setattr(fc, "chat", chat)
    monkeypatch.setattr(ps, "_panel_module", lambda: None)
    monkeypatch.setattr(ps, "_seat_module", lambda: None)
    text, _, err = ps._ask("generation", "prompt", timeout=10, model_hint="local0:q")
    assert calls == ["local0:q"] and not text and err


def test_a_declared_local_server_turns_the_seat_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "1")
    monkeypatch.setenv("QUANT_LOCAL_LLM_URLS", "http://127.0.0.1:11434/v1")
    assert ps.enabled()
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")
    assert not ps.enabled()


# --------------------------------------------------------------- open-weight breadth (2026-10-13)
def test_the_open_weight_hosted_tiers_are_all_on_the_chain() -> None:
    names = {p.name for p in fc.DEFAULTS}
    assert {"groq", "cerebras", "cloudflare_ai", "huggingface", "openrouter_free",
            "mistral_free", "github_models", "gemini"} <= names
    assert [p.name for p in fc.DEFAULTS if not p.open_weights] == ["gemini"]
    assert all(p.terms_url for p in fc.DEFAULTS), "every rung names its own published terms"


def test_a_missing_url_variable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-test-not-real")
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    cf = next(p for p in fc.providers() if p.name == "cloudflare_ai")
    assert not cf.usable() and cf.url() == ""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    cf = next(p for p in fc.providers() if p.name == "cloudflare_ai")
    assert cf.usable() and "/accounts/acct123/ai/v1" in cf.url()


def test_the_terms_gate_holds_a_rung_shut_until_confirmed(monkeypatch: pytest.MonkeyPatch,
                                                          _isolated: Path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp-test-not-real")
    gh = next(p for p in fc.providers() if p.name == "github_models")
    assert gh.terms == "to_confirm" and not gh.usable(), "a token alone is not consent"
    fc.CONFIG.write_text(json.dumps({"providers": [{"name": "github_models",
                                                    "terms": "confirmed"}]}))
    gh = next(p for p in fc.providers() if p.name == "github_models")
    assert gh.usable() and gh.base_url == "https://models.github.ai/inference"
    fc.CONFIG.write_text(json.dumps({"providers": [{"name": "new_cloud", "tier": "account_free",
                                                    "base_url": "https://x.example/v1",
                                                    "key_env": "GROQ_API_KEY"}]}))
    monkeypatch.setenv("GROQ_API_KEY", "k")
    new = next(p for p in fc.providers() if p.name == "new_cloud")
    assert new.terms == "to_confirm" and not new.usable(), "a new cloud row starts closed"


def test_the_rotation_spreads_load_and_keeps_local_last() -> None:
    st = fc._State({})
    a = fc.Provider("a", "https://a/v1", "K", "account_free", daily_cap=100)
    b = fc.Provider("b", "https://b/v1", "K", "account_free", daily_cap=100)
    loc = fc.Provider("local0", "http://127.0.0.1:11434/v1")
    for _ in range(90):
        st.count("a", "m", True, 1.0)
    order = [p.name for p in fc.rank(st, [loc, a, b])]
    assert order == ["b", "a", "local0"], "a nearly-drained quota yields to a fresh one"
    for _ in range(30):
        st.count("b", "m", False)
    st.doc["calls"] = {}
    assert fc.rank(st, [loc, a, b])[0].name == "a", "answer rate is benchmarked"


def test_local_fit_is_measured_on_this_machine() -> None:
    doc = fc.local_fit()
    assert doc.get("verdict") == fc.UNMEASURED or {"total_gb", "fit"} <= set(doc)


def test_with_only_openrouter_the_rest_are_skipped_not_failed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    doc = fc.status()
    assert doc["verdict"] == "RAN" and doc["cloud_usable"] == 1
    assert "openrouter_free" not in doc["skipped_no_key"]
    assert {"groq", "cerebras", "huggingface", "gemini"} <= set(doc["skipped_no_key"])


class _Proc:
    def __init__(self, cmd: list[str], name: str = "python") -> None:
        self.info = {"cmdline": cmd, "name": name}
        self.pid = id(self)
        self.niced: Any = None

    def nice(self, v: Any) -> None:
        self.niced = v


class _PS:
    def __init__(self, cpu: float, procs: list[_Proc]) -> None:
        self.cpu, self.procs = cpu, procs

    def cpu_percent(self, interval: float = 0.0) -> float:
        return self.cpu

    def process_iter(self, attrs: Any = None) -> list[_Proc]:
        return self.procs


def test_the_local_rung_runs_on_spare_cpu_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_LOCAL_LLM_GUARD", "1")
    server = _Proc([], name="ollama.exe")
    judge = _Proc(["python", "desks/mt5/scripts/external_gauntlet.py"])
    monkeypatch.setattr(fc, "_psutil", lambda: _PS(80.0, [judge, server]))
    why = fc.local_blocked()
    assert "busy" in why and "external_gauntlet" in why, "a loaded box blocks and names who"
    # The judge runs 24/7: its PRESENCE on a box with spare cores must not block the rung.
    monkeypatch.setattr(fc, "_psutil", lambda: _PS(5.0, [judge, server]))
    fc._DEMOTED.clear()
    assert fc.local_blocked() == "" and server.niced is not None
    monkeypatch.setattr(fc, "_psutil", lambda: _PS(5.0, [server]))
    fc._DEMOTED.clear()
    assert fc.local_blocked() == "" and server.niced is not None, "server dropped to idle"
    monkeypatch.setattr(fc, "_psutil", lambda: None)
    assert fc.local_blocked(), "no way to prove idleness keeps the local rung off"


def test_a_busy_box_skips_the_local_rung_in_the_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_LOCAL_LLM_GUARD", "1")
    monkeypatch.setattr(fc, "_psutil", lambda: _PS(95.0, []))
    seen: list[str] = []
    monkeypatch.setattr(fc, "_request", _fake({}, seen))
    with pytest.raises(fc.ChainExhausted, match="busy"):
        fc.chat("s", "u", timeout=10)
    assert not seen, "no request reached the local server"


def test_account_tier_rungs_are_closed_by_default(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit must-fix 6: an account-tier rung is free only if that ACCOUNT is, which no code can
    see, so it stays closed until the principal names it."""
    monkeypatch.delenv("QUANT_FREE_ONLY_ACCOUNTS", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    groq = next(p for p in fc.providers() if p.name == "groq")
    assert groq.tier == "account_free" and not groq.usable()
    assert "groq" in fc.status()["account_closed"]
    monkeypatch.setenv("QUANT_FREE_ONLY_ACCOUNTS", "groq")
    assert next(p for p in fc.providers() if p.name == "groq").usable()
    monkeypatch.delenv("QUANT_FREE_ONLY_ACCOUNTS")
    fc.CONFIG.write_text(json.dumps({"providers": [{"name": "groq",
                                                    "free_only_account": True}]}))
    assert next(p for p in fc.providers() if p.name == "groq").usable()
