"""The Chinese-model ensemble: fail-closed seats, public-only prompts, diversity, donation."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.ops import cn_ensemble as cn
from libs.ops import llm_seat

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
OR, HC, AR, YJ = cn.PROVIDERS


@pytest.fixture(autouse=True)
def _relays_ruled_allowed(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Most tests exercise relay plumbing, so they assume Governance has ruled ALLOWED."""
    if "shipped_rulings" not in request.node.name:
        monkeypatch.setattr(cn, "relay_ruling", lambda name: "ALLOWED")


def test_shipped_rulings_keep_every_relay_dark_with_a_key() -> None:
    for p in (HC, AR, YJ):
        s = cn.seat_for(p, {p.key_env: "k"}, lambda b, k: ["deepseek-chat"])
        assert not s.lit and "Governance" in s.why and s.key == ""


def _no_list(base: str, key: str) -> list[str]:
    raise RuntimeError("offline")


def test_every_provider_is_dark_without_its_key() -> None:
    for p in (HC, AR, YJ):
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
    assert len({c[2] for c in calls}) == 8 and {c[3] for c in calls} == {"propose"}
    assert cn.plan([a], {"openrouter": 0}, 0) == []


def _finding(title: str) -> str:
    return json.dumps({"findings": [{"title": title, "mechanism": "forced hedging",
                                     "testable_claim": "long X after Y beats flat",
                                     "symbols": ["xauusd"], "horizon": "1d",
                                     "source": "public"}]})


def test_run_dedupes_across_models_and_donates(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cn, "_donate", lambda rows, rec, now, base: _fake_donate(rows, base))
    env = {"OPENROUTER_API_KEY": "k", "HCNSEC": "h", "CN_ENSEMBLE_WORKERS": "3"}

    def lister(base: str, key: str) -> list[str]:
        if "hcnsec" in base:
            return ["deepseek-ai/DeepSeek-R1-0528"]
        return ["deepseek/deepseek-r1:free", "qwen/qwen3-235b-a22b:free"]

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        assert seat.key and ("RESEARCH LENS" in user or "RULES:" in user)
        if "qwen" in model:
            return "", "HTTP 429"
        return _finding("Gold fix flow" if "R1" in model.upper() else "Other idea"), None

    rep = cn.run(NOW, root=tmp_path, env={**env, "CN_SWARM_CRITIC_CALLS": "0"}, chat=chat,
                 list_models=lister, quotas={"openrouter": 4, "hcnsec": 2})
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


# ------------------------------------------------------------------------------ the swarm
from libs.ops import cn_swarm  # noqa: E402


def test_catalog_is_price_only_registered_families() -> None:
    cat = cn_swarm.catalog()
    assert "mean_reversion_rsi" in cat and cat["mean_reversion_rsi"]["rsi_n"] == 14
    assert not any(k.startswith("cot_") for k in cat)          # needs a second input


def test_validate_recipe_admits_only_runnable_specs() -> None:
    cat = {"mean_reversion_rsi": {"rsi_n": 14, "oversold": 30, "rr": 1.8}}
    ok = cn_swarm.validate_recipe({"family": "mean_reversion_rsi", "symbols": ["xau/usd"],
                                   "params": {"rsi_n": 7, "oversold": 30}}, cat)
    assert ok == {"family": "mean_reversion_rsi", "params": {"rsi_n": 7}, "symbols": ["XAUUSD"]}
    bad = [{"family": "nope", "symbols": ["EURUSD"]},
           {"family": "mean_reversion_rsi", "symbols": ["EURUSD"], "params": {"zzz": 1}},
           {"family": "mean_reversion_rsi", "symbols": ["EURUSD"], "params": {"rsi_n": 9999}},
           {"family": "mean_reversion_rsi", "symbols": [], "params": {}}]
    assert all(cn_swarm.validate_recipe(b, cat) is None for b in bad)


def test_genome_id_matches_the_graph() -> None:
    from libs.research.hypothesis_graph import node_id
    assert cn_swarm.genome_id("xauusd", "f", {"a": 1}) == node_id("XAUUSD", "f", {"a": 1})


def test_power_only_gates_match_the_judge() -> None:
    src = (Path(__file__).resolve().parents[2] / "desks/mt5/scripts/external_gauntlet.py"
           ).read_text("utf-8")
    for g in cn_swarm.POWER_ONLY_GATES:
        assert f'"{g}"' in src.split("POWER_ONLY_GATES = frozenset(")[1].split(")")[0]


def test_every_lens_prompt_is_public() -> None:
    cat = cn_swarm.catalog()
    for lid, _lg, _b in cn_swarm.LENSES:
        cn.assert_public(cn_swarm.propose_system(cat), cn_swarm.lens_prompt(lid))
    cn.assert_public(cn_swarm.CRITIC_SYSTEM, cn_swarm.MUTATE_SYSTEM)


def test_weights_keep_an_exploration_floor() -> None:
    import random
    board = {"a": {"judged": 100, "passed": 30, "near": 20}, "b": {"judged": 100}}
    w = cn_swarm.weights(["a", "b", "c"], board, random.Random(1))
    assert abs(sum(w.values()) - 1) < 1e-9 and min(w.values()) > 0.05 and w["a"] > w["b"]


def _recipe(fam: str, sym: str, **params: object) -> str:
    return json.dumps({"findings": [{"title": f"{fam} {sym}", "mechanism": "forced flow",
                                     "testable_claim": "x", "symbols": [sym], "family": fam,
                                     "params": params}]})


def test_swarm_runs_critic_mutation_and_lineage(tmp_path: Path) -> None:
    # A near miss on the judge's ledger, resolvable through the graph.
    (tmp_path / "desks/mt5/data/hypotheses").mkdir(parents=True)
    (tmp_path / cn_swarm.GRAPH).write_text(json.dumps({
        "id": "g1", "symbol": "EURUSD", "family": "mean_reversion_rsi",
        "params": {"rsi_n": 10, "timeframe": "M15"}, "source": "miner:other"}) + "\n")
    (tmp_path / cn_swarm.GATE_LEDGER).write_text(json.dumps({
        "at": "2026-11-17T00:00:00", "graph_id": "g1", "passed": False,
        "terminal_gate": "deflated_sharpe"}) + "\n")
    env = {"OPENROUTER_API_KEY": "k", "HCNSEC": "h", "CN_SWARM_CRITIC_CALLS": "1",
           "CN_SWARM_MUTATIONS": "1"}

    def lister(base: str, key: str) -> list[str]:
        return ["deepseek-ai/DeepSeek-R1"] if "hcnsec" in base else ["qwen/qwen3:free",
                                                                      "z-ai/glm-4.5-air:free"]
    sent: list[tuple[str, str]] = []

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        sent.append((seat.provider.name, system[:20]))
        if system == cn_swarm.CRITIC_SYSTEM:
            return json.dumps({"scores": [{"i": 0, "score": 9}, {"i": 1, "score": 1}]}), None
        if system == cn_swarm.MUTATE_SYSTEM:
            assert seat.provider.name == "openrouter"          # never a relay
            return _recipe("mean_reversion_rsi", "EURUSD", rsi_n=8), None
        if "glm" in model:
            return _recipe("trend_ma_cross", "XAUUSD", fast_ema=20), None
        return _recipe("mean_reversion_rsi", "GBPUSD", rsi_n=21), None

    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat, list_models=lister,
                 quotas={"openrouter": 6, "hcnsec": 4})
    assert rep["near_misses_seen"] == 1 and rep["mutation_calls"] == 1
    assert rep["runnable_recipes"] >= 2 and rep["critic"]["scored"] >= 2
    assert rep["critic"]["killed"] >= 1
    assert rep["scoreboard"]["status"] == "MEASURED"
    doc = json.loads((tmp_path / rep["donated"]).read_text("utf-8"))
    rows = [d for d in doc["discoveries"] if d.get("family")]
    assert rows and all(isinstance(d["params"], dict) and d["symbols"] for d in rows)
    lin = (tmp_path / cn_swarm.LINEAGE).read_text("utf-8").splitlines()
    assert len(lin) >= len(rows)
    # A second hour does not resend what the first already donated.
    rep2 = cn.run(NOW, root=tmp_path, env=env, chat=chat, list_models=lister,
                  quotas={"openrouter": 6, "hcnsec": 4})
    assert rep2["recipes_skipped_already_sent"] >= 1


def test_scoreboard_joins_verdicts_back_to_model_and_lens(tmp_path: Path) -> None:
    (tmp_path / "desks/mt5/data/hypotheses").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / cn_swarm.LINEAGE).write_text(json.dumps({
        "at": "2026-11-17T00:00:00", "gid": "x", "symbol": "EURUSD", "family": "f",
        "params": {"a": 1}, "provider": "openrouter", "model": "m", "lens": "l"}) + "\n")
    (tmp_path / cn_swarm.GRAPH).write_text(json.dumps({
        "id": "g", "symbol": "EURUSD", "family": "f", "params": {"a": 1, "timeframe": "M5"},
        "source": cn_swarm.DONOR_SOURCE}) + "\n")
    (tmp_path / cn_swarm.GATE_LEDGER).write_text(json.dumps({
        "graph_id": "g", "passed": True, "terminal_gate": "PASSED"}) + "\n")
    b = cn_swarm.scoreboard(tmp_path)
    assert b["by_model"]["openrouter:m"] == {"donated": 1, "judged": 1, "passed": 1, "near": 0}
    assert b["by_lens"]["l"]["passed"] == 1
    assert cn_swarm.scoreboard(tmp_path / "nowhere")["status"] == "UNMEASURED"
