"""The Chinese-model ensemble: fail-closed seats, public-only prompts, diversity, donation."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.ops import cn_ensemble as cn
from libs.ops import llm_seat

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
OR, HC, AR = cn.PROVIDERS


def _no_list(base: str, key: str) -> list[str]:
    raise RuntimeError("offline")


def test_every_provider_is_dark_without_its_key() -> None:
    for p in (HC, AR):
        s = cn.seat_for(p, {}, _no_list)
        assert not s.lit and s.key == "" and p.key_env in s.why


def test_relay_needs_https_and_a_chinese_model() -> None:
    env = {"HCNSEC": "k", "HCNSEC_BASE_URL": "http://api.hcnsec.cn/v1"}
    assert "https" in cn.seat_for(HC, env, _no_list).why
    env = {"HCNSEC": "k"}
    assert not cn.seat_for(HC, env, lambda b, k: ["gpt-4o", "claude-x"]).lit
    s = cn.seat_for(HC, env, lambda b, k: ["gpt-4o", "deepseek-ai/DeepSeek-R1-0528"])
    assert s.lit and s.models == ("deepseek-ai/DeepSeek-R1-0528",)


def test_openrouter_takes_only_free_chinese_ids() -> None:
    env = {"OPENROUTER_API_KEY": "k"}
    listed = ["qwen/qwen3-235b-a22b:free", "qwen/qwen3-max", "openai/gpt-oss:free",
              "z-ai/glm-4.5-air:free"]
    s = cn.seat_for(OR, env, lambda b, k: listed)
    assert s.models == ("qwen/qwen3-235b-a22b:free", "z-ai/glm-4.5-air:free")
    fallback = cn.seat_for(OR, env, _no_list)
    assert fallback.lit and all(m.endswith(":free") for m in fallback.models)
    paid = cn.seat_for(OR, {**env, "CN_ENSEMBLE_OPENROUTER_MODELS": "qwen/qwen3-max"}, _no_list)
    assert not paid.lit


@pytest.mark.parametrize("leak", ["OPENROUTER_API_KEY=sk-or-v1-abc", "our FTMO account",
                                  "C:\\opt\\quant\\data", "survivors from the gauntlet"])
def test_assert_public_refuses_desk_text(leak: str) -> None:
    with pytest.raises(ValueError):
        cn.assert_public(cn.SYSTEM, leak)


def test_the_shipped_prompts_are_public() -> None:
    for role, brief in cn.ROLES:
        cn.assert_public(cn.SYSTEM, f"RESEARCH QUESTION ({role}): {brief}.")


def test_plan_spreads_over_models_and_respects_quotas() -> None:
    a = cn.seat_for(OR, {"OPENROUTER_API_KEY": "k"}, lambda b, k: [
        "deepseek/deepseek-r1:free", "qwen/qwen3-235b-a22b:free", "moonshotai/kimi-k2:free"])
    b = cn.seat_for(HC, {"HCNSEC": "k"}, lambda b, k: ["deepseek-ai/DeepSeek-R1-0528"])
    calls = cn.plan([a, b], {"openrouter": 6, "hcnsec": 2}, start=0)
    assert len(calls) == 8
    assert sum(c[0].provider.name == "hcnsec" for c in calls) == 2
    assert len({c[1] for c in calls}) == 4
    assert len({c[2] for c in calls}) >= 6
    assert cn.plan([a], {"openrouter": 0}, 0) == []


def _finding(title: str) -> str:
    return json.dumps({"findings": [{"title": title, "mechanism": "forced hedging",
                                     "testable_claim": "long X after Y beats flat",
                                     "symbols": ["xauusd"], "horizon": "1d",
                                     "source": "public"}]})


def test_run_dedupes_across_models_and_donates(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cn, "_donate", lambda rows, now, base: _fake_donate(rows, base))
    env = {"OPENROUTER_API_KEY": "k", "HCNSEC": "h", "CN_ENSEMBLE_WORKERS": "3"}

    def lister(base: str, key: str) -> list[str]:
        if "hcnsec" in base:
            return ["deepseek-ai/DeepSeek-R1-0528"]
        return ["deepseek/deepseek-r1:free", "qwen/qwen3-235b-a22b:free"]

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        assert seat.key and "RESEARCH QUESTION" in user
        if "qwen" in model:
            return "", "HTTP 429"
        return _finding("Gold fix flow" if "R1" in model.upper() else "Other idea"), None

    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat, list_models=lister,
                 quotas={"openrouter": 4, "hcnsec": 2})
    assert rep["calls"] == 6
    assert rep["providers"]["agentrouter"]["lit"] is False
    assert any(o["status"] == "CALL_FAILED" for o in rep["outcomes"])
    assert rep["distinct_ideas"] >= 1 and rep["multi_model_ideas"] >= 1
    assert "PROPOSE ONLY" in rep["authority"]
    assert (tmp_path / cn.REPORT).exists()
    relay_rows = (tmp_path / cn.RELAY_LEDGER).read_text("utf-8").splitlines()
    assert len(relay_rows) == 2 and all('"hcnsec"' in r for r in relay_rows)


def _fake_donate(rows: list[dict], base: Path) -> Path:
    p = base / cn.DONATE_DIR / "discoveries_test.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows), "utf-8")
    return p


def test_run_with_no_keys_sends_nothing(tmp_path: Path) -> None:
    def chat(*a: object) -> tuple[str, str | None]:
        raise AssertionError("a dark ensemble must not call anyone")

    rep = cn.run(NOW, root=tmp_path, env={"OPENROUTER_API_KEY": ""}, chat=chat,
                 list_models=_no_list)
    assert rep["calls"] == 0 and rep["donated"] is None


def test_relay_calls_stay_out_of_openrouter_budget(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "llm_spend.jsonl"
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", ledger)
    stamp = NOW.isoformat(timespec="seconds")
    ledger.write_text("\n".join([
        json.dumps({"utc": stamp, "seat": "cn_openrouter", "free": True}),
        json.dumps({"utc": stamp, "seat": "cn_hcnsec", "free": True,
                    "provider": llm_seat.FREE_RELAY}),
    ]) + "\n", "utf-8")
    assert llm_seat.calls_today(NOW) == 1
