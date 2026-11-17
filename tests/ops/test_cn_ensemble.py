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


def _no_list(base: str, key: str) -> list[str]:
    raise RuntimeError("offline")


@pytest.fixture(autouse=True)
def _relays_ruled_allowed(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Most tests exercise relay plumbing, so they assume Governance has ruled ALLOWED."""
    if "shipped_rulings" not in request.node.name:
        monkeypatch.setattr(cn, "relay_ruling", lambda name: "ALLOWED")


def test_shipped_rulings_allow_the_relays_on_the_principals_override() -> None:
    for p in (HC, AR, YJ):
        assert cn.relay_ruling(p.name) == "ALLOWED"
        s = cn.seat_for(p, {}, _no_list)
        assert not s.lit and p.key_env in s.why          # still dark until the key exists
        lit = cn.seat_for(p, {p.key_env: "k"}, lambda b, k: ["deepseek-chat"])
        assert lit.lit and lit.models == ("deepseek-chat",)


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
        "id": "g1", "symbol": "EURUSD", "family": "overnight_drift",
        "params": {"hold_bars": 10, "timeframe": "M15"}, "source": "miner:other"}) + "\n")
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
            return _recipe("overnight_drift", "EURUSD", hold_bars=6), None
        if "glm" in model:
            return _recipe("momentum_volgate", "XAUUSD", mom_n=12), None
        return _recipe("overnight_drift", "GBPUSD", hold_bars=16), None

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


# ------------------------------------------- the relay ruling and its four conditions
def test_relay_ruling_is_allowed_on_its_four_conditions(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    rulings = json.loads((root / "ops/relay_terms_rulings.json").read_text("utf-8"))
    for name in ("hcnsec", "agentrouter", "yjs"):
        row = rulings[name]
        assert row["ruling"] == "ALLOWED" and row["keys"] == "principal"
        assert "governance/llm-relays-terms-ruling-2026-11-17.md" in row["ref"]
    # 4. the keys are the principal's: catalogued, read by the ensemble only, never shipped.
    from libs.ops import env_keys
    for p in (HC, AR, YJ):
        row = next(r for r in env_keys.catalog() if r["name"] == p.key_env)
        assert row["readers"] == ["libs/ops/cn_ensemble.py"] and "principal" in row["owner"]
        assert not env_keys.refused(p.key_env)
    # 1. public prompts only: every prompt a relay can receive passes assert_public.
    from libs.ops import cn_swarm as sw
    cat = sw.catalog()
    for lid, _lg, _b in sw.LENSES:
        cn.assert_public(sw.propose_system(cat), sw.lens_prompt(lid))
    cn.assert_public(sw.CRITIC_SYSTEM, sw.SCOUT_SYSTEM)
    # 3. propose-only, never on a money path.
    closure = (root / "ops/money_closure.txt").read_text("utf-8")
    for mod in ("cn_ensemble", "cn_swarm", "run_cn_ensemble"):
        assert mod not in closure
    rep_src = (root / "libs/ops/cn_ensemble.py").read_text("utf-8")
    assert "PROPOSE ONLY" in rep_src
    assert "AUTHORITY: NONE" in (sw.__doc__ or "") and "AUTHORITY: NONE" in (cn.__doc__ or "")


def test_near_misses_never_reach_a_relay(tmp_path: Path) -> None:
    """2. no desk-private or near-miss content to relays: with OpenRouter dark, the swarm makes
    no mutation call at all rather than hand a near miss to a relay."""
    from libs.ops import cn_swarm as sw
    (tmp_path / "desks/mt5/data/hypotheses").mkdir(parents=True)
    (tmp_path / sw.GRAPH).write_text(json.dumps({
        "id": "g1", "symbol": "EURUSD", "family": "overnight_drift",
        "params": {"hold_bars": 10}, "source": "miner:other"}) + "\n")
    (tmp_path / sw.GATE_LEDGER).write_text(json.dumps({
        "at": "2026-11-17T00:00:00", "graph_id": "g1", "passed": False,
        "terminal_gate": "deflated_sharpe"}) + "\n")

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        assert seat.provider.relay
        assert system != sw.MUTATE_SYSTEM and "RULES:\n{\"symbol\"" not in user
        return json.dumps({"findings": []}), None

    rep = cn.run(NOW, root=tmp_path, env={"HCNSEC": "h", "CN_SWARM_CRITIC_CALLS": "0"},
                 chat=chat, list_models=lambda b, k: ["deepseek-chat"],
                 quotas={"hcnsec": 5})
    assert rep["mutation_calls"] == 0 and rep["calls"] == 5


def test_worldwide_lenses_cover_every_region_in_its_own_language() -> None:
    from libs.ops import cn_swarm as sw
    langs = {lg for _l, lg, _b in sw.LENSES}
    assert {"zh", "ja", "ko", "es", "pt", "ar", "ru", "pl", "tr", "hi", "id", "th", "fr",
            "de"} <= langs
    assert all(lg in sw._LANG_ASK for lg in langs)
    assert sw.SCOUT_LENS in sw.LENS_BRIEF


def test_source_scouts_feed_the_ledger_and_the_next_hour(tmp_path: Path) -> None:
    from libs.ops import cn_swarm as sw
    env = {"OPENROUTER_API_KEY": "k", "CN_SWARM_CRITIC_CALLS": "0"}

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        if system == sw.SCOUT_SYSTEM:
            return json.dumps({"sources": [
                {"name": "Bank of Ghana bulletin", "url": "https://www.bog.gov.gh/stats",
                 "country": "GH", "language": "en", "publishes": "monthly", "why": "gold"},
                {"name": "bad", "url": "http://insecure.example"},
                {"name": "exchange", "url": "https://www.binance.com/x"}]}), None
        assert sw.DISCOVERED_LENS not in user or "Bank of Ghana" in user
        return json.dumps({"findings": []}), None

    lens_all = [lid for lid, _lg, _b in sw.LENSES]
    calls = len(lens_all)
    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat,
                 list_models=lambda b, k: ["qwen/qwen3:free"], quotas={"openrouter": calls})
    assert rep["sources_discovered"] == 1
    assert rep["sources_registration"]["status"] == "SKIPPED"
    rows = (tmp_path / sw.SOURCES_LEDGER).read_text("utf-8").splitlines()
    assert len(rows) == 1 and "bog.gov.gh" in rows[0]
    rep2 = cn.run(NOW, root=tmp_path, env=env, chat=chat,
                  list_models=lambda b, k: ["qwen/qwen3:free"], quotas={"openrouter": calls + 1})
    assert rep2["sources_discovered"] == 0 and rep2["lenses"] == calls + 1


def test_mutation_derived_recipes_never_reach_a_relay_critic(tmp_path: Path) -> None:
    """Auditor MF1: a recipe descended from a desk near miss is scored on OpenRouter or not at
    all; the relay critic only ever sees recipes from public lenses."""
    from libs.ops import cn_swarm as sw
    (tmp_path / "desks/mt5/data/hypotheses").mkdir(parents=True)
    (tmp_path / sw.GRAPH).write_text(json.dumps({
        "id": "g1", "symbol": "EURUSD", "family": "overnight_drift",
        "params": {"hold_bars": 10}, "source": "miner:other"}) + "\n")
    (tmp_path / sw.GATE_LEDGER).write_text(json.dumps({
        "at": "2026-11-17T00:00:00", "graph_id": "g1", "passed": False,
        "terminal_gate": "deflated_sharpe"}) + "\n")
    env = {"OPENROUTER_API_KEY": "k", "HCNSEC": "h", "CN_SWARM_CRITIC_CALLS": "2",
           "CN_SWARM_MUTATIONS": "1"}
    critics: list[tuple[str, str]] = []

    def lister(base: str, key: str) -> list[str]:
        return ["deepseek-chat"] if "hcnsec" in base else ["qwen/qwen3:free"]

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        if system == sw.CRITIC_SYSTEM:
            critics.append((seat.provider.name, user))
            n = user.count('"i":')
            return json.dumps({"scores": [{"i": i, "score": 8} for i in range(n)]}), None
        if system == sw.MUTATE_SYSTEM:
            assert not seat.provider.relay
            return _recipe("overnight_drift", "USDCHF", hold_bars=6), None
        return _recipe("momentum_volgate", "XAUUSD", mom_n=12), None

    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat, list_models=lister,
                 quotas={"openrouter": 9, "hcnsec": 6})
    assert rep["mutation_calls"] == 1
    relay_seen = " ".join(u for who, u in critics if who == "hcnsec")
    or_seen = " ".join(u for who, u in critics if who == "openrouter")
    assert "XAUUSD" in relay_seen and "USDCHF" not in relay_seen
    assert "USDCHF" in or_seen


def test_steering_prunes_dead_families_and_ranks_by_realised_yield(tmp_path: Path) -> None:
    from libs.ops import cn_swarm as sw
    cat = {"ict_fvg": {"a": 1}, "overnight_gap_decay": {"a": 1}, "dow_effect": {"a": 1},
           "brand_new": {"a": 1}}
    yld = {"ict_fvg": {"judged": 14818, "passed": 0, "mean": 0.0001, "hi": 0.0002},
           "overnight_gap_decay": {"judged": 7523, "passed": 436, "mean": 0.058, "hi": 0.063},
           "dow_effect": {"judged": 1744, "passed": 0, "mean": 0.0005, "hi": 0.0017}}
    live, dead = sw.steer_catalog(cat, yld)
    assert dead == ["dow_effect", "ict_fvg"]
    assert list(live) == ["overnight_gap_decay", "brand_new"]
    # Off the box (no coverage report) the fallback list still prunes the retail-TA set.
    live2, dead2 = sw.steer_catalog({"ict_fvg": {}, "overnight_drift": {}}, {})
    assert dead2 == ["ict_fvg"] and list(live2) == ["overnight_drift"]
    # The report is read from the judge's own field.
    (tmp_path / "desks/mt5/reports").mkdir(parents=True)
    (tmp_path / sw.COVERAGE).write_text(json.dumps({"realised_pass_rate": [
        {"family": "clock_transition", "judged": 13103, "passed": 934,
         "posterior_mean": 0.071, "posterior_hi": 0.076}]}))
    assert sw.family_yield(tmp_path)["clock_transition"]["passed"] == 934
    cn.assert_public(sw.MECHANISM_STEER)


def test_dead_family_findings_are_not_donated(tmp_path: Path) -> None:
    env = {"OPENROUTER_API_KEY": "k", "CN_SWARM_CRITIC_CALLS": "0"}

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        return _recipe("ict_fvg", "EURUSD", ema_fast=5), None

    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat,
                 list_models=lambda b, k: ["qwen/qwen3:free"], quotas={"openrouter": 3})
    assert rep["runnable_recipes"] == 0
    assert rep["steering_by_yield"]["findings_dropped_dead_family"] >= 1
    assert "ict_fvg" in rep["steering_by_yield"]["pruned_families"]


def test_yjs_key_saved_as_yjss_lights_the_seat() -> None:
    s = cn.seat_for(YJ, {"YJSS": "k"}, lambda b, k: ["deepseek-chat"])
    assert s.lit and s.key == "k"
    from libs.ops import env_keys
    row = next(r for r in env_keys.catalog() if r["name"] == "YJSS")
    assert row["readers"] == ["libs/ops/cn_ensemble.py"] and not env_keys.refused("YJSS")


SCI_EXPR = "zscore(sub(mean(flow, 12), mean(flow, 48)), 120)"


def test_validate_formula_admits_only_bar_only_grammar() -> None:
    from libs.ops import cn_swarm as sw
    ok = sw.validate_formula({"expr": SCI_EXPR, "symbols": ["eurusd", "XAU/USD"],
                              "side_mode": "fade", "hold_bars": 12}, "science_sir_contagion")
    assert ok is not None and ok["family"] == "formula"
    assert ok["symbols"] == ["EURUSD", "XAUUSD"]
    assert ok["params"]["population"] == "llm_science_sir_contagion"
    assert ok["params"]["side_mode"] == "fade" and ok["params"]["hold_bars"] == 12
    for bad in ("ts_zscore(close, 20)", "zscore(close, 7)", "add(std(close, 24), std(ret, 24))",
                "zscore(dxy, 24)", "", "not a formula ((("):
        assert sw.validate_formula({"expr": bad, "symbols": ["EURUSD"]}, "science_x") is None
    assert sw.validate_formula({"expr": SCI_EXPR, "symbols": []}, "science_x") is None
    assert sw.validate_formula({"expr": SCI_EXPR, "symbols": ["EURUSD"], "hold_bars": 999},
                               "science_x") is None


def test_science_lenses_are_public_and_cover_the_four_asked_analogs() -> None:
    from libs.ops import cn_swarm as sw
    ids = {lid for lid, _lg, _b in sw.LENSES if lid.startswith(sw.SCIENCE_PREFIX)}
    assert {"science_predator_prey", "science_sir_contagion", "science_queueing_refill",
            "science_critical_slowing"} <= ids
    for lid in ids:
        cn.assert_public(sw.formula_system(), sw.lens_prompt(lid))
    from libs.research import alpha_grammar as g
    assert g.is_valid(g.from_str(SCI_EXPR), terminals=g.BAR_TERMINALS)  # the prompt's example


def test_science_lens_donates_a_formula_recipe(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import cn_swarm as sw
    donated: list[dict] = []
    monkeypatch.setattr(cn, "_donate", lambda rows, rec, now, base: (donated.extend(rec),
                                                                     _fake_donate(rows, base))[1])
    monkeypatch.setattr(sw, "steer_catalog", lambda cat, yld: (dict(cat), ["formula"]))
    env = {"OPENROUTER_API_KEY": "k", "CN_SWARM_CRITIC_CALLS": "0"}

    def chat(seat: cn.Seat, model: str, system: str, user: str) -> tuple[str, str | None]:
        if system == sw.formula_system():
            return json.dumps({"findings": [{"title": "contagion", "analog": "SIR",
                                             "mechanism": "m", "testable_claim": "c",
                                             "expr": SCI_EXPR, "symbols": ["EURUSD"]}]}), None
        return json.dumps({"findings": []}), None

    calls = len(sw.LENSES)
    rep = cn.run(NOW, root=tmp_path, env=env, chat=chat,
                 list_models=lambda b, k: ["qwen/qwen3:free"], quotas={"openrouter": calls})
    assert rep["runnable_recipes"] >= 1
    pops = {r["params"]["population"] for r in donated if r.get("family") == "formula"}
    assert pops and all(p.startswith("llm_science_") for p in pops)
