"""The DeepSeek third-brain laboratory (libs/ops/deepseek_lab.py), addendum sections 6-13, 21-27,
32, 38-40. Every test runs in a temporary root; nothing here writes the repository's own state."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import deepseek_cycle as ds
from libs.ops import deepseek_lab as lab

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def families() -> dict[str, list[str]]:
    fams = lab.family_specs(REPO)
    assert "formula" in fams, "the registered formula family is the exact-candidate IR"
    return fams


@pytest.fixture
def root(tmp_path: Path, families, monkeypatch) -> Path:
    uni = tmp_path / "desks/mt5/data/universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "GBPUSD": {"asset_class": "Forex"},
        "USDJPY": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
    }), "utf-8")
    (tmp_path / "desks/mt5/data/data_registry.json").write_text(
        json.dumps({"datasets": {"cot_tff": {}}}), "utf-8")
    monkeypatch.setattr(lab, "family_specs", lambda _root: families)
    return tmp_path


def _ctx(root: Path) -> dict[str, Any]:
    return lab.context(root)


EXACT = {
    "object_type": "EXACT_CANDIDATE", "title": "USD driver impulse fades on EURUSD in NY",
    "symbols": ["eurusd"], "family": "formula",
    "params": {"expr": "mul(sign(delta(usd, 5)), ts_rank(vol, 48))", "norm": 240,
               "entry_z": 1.5, "side_mode": "fade", "hold_bars": 8, "stop_atr": 2.0, "rr": 1.5},
    "timeframe": "H1", "session": "ny", "direction": "both",
    "entry_rule": "enter at next open when |z| of expr over 240 bars >= 1.5, against its sign",
    "exit_rule": "exit after 8 bars or at target/stop", "stop_rule": "2.0 ATR(20)",
    "target_rule": "1.5 R", "holding_horizon": "8 H1 bars",
    "falsifier": "fade return <= 0 net of costs over the dev sample",
    "economic_mechanism": "dealers hedge USD index moves late in NY and over-shoot EURUSD",
    "forced_actor": "USD index hedgers", "mechanism_class": "inventory_hedging",
    "data_inputs": [{"series_id": "usd", "source": "desk driver"}],
}


def _packet(**sections: Any) -> dict[str, Any]:
    base = {"universe": {"symbols": 4}, "data_and_features": {"dirs": 1},
            "research_frontier": {"docket_rows": 1}, "conversion_inventory": {"queue": 1},
            "empirical_memory": {"rows": 1}, "portfolio_opportunity_state": {"sleeves": 1},
            "point_in_time_metadata": {"a": 1}, "resource_state": {"cpu": 4}}
    base.update(sections)
    return {"status": "MEASURED", "packet_hash": "p" * 64, "sections": base}


# ------------------------------------------------------------------------- queue (32, 39)

def test_enqueue_is_idempotent_and_survives_restart(root: Path) -> None:
    q = lab.load_queue(root)
    assert lab.enqueue(q, "A", "cadence:1h:1") is not None
    assert lab.enqueue(q, "A", "cadence:1h:1") is None
    lab.save_queue(root, q)
    q2 = lab.load_queue(root)                   # a restart reads the same jobs
    assert len(q2["jobs"]) == 1
    assert next(iter(q2["jobs"].values()))["status"] == "PENDING"


def test_provider_failure_keeps_the_job_with_backoff_then_parks_and_rearms() -> None:
    q: dict[str, Any] = {"jobs": {}}
    jid = lab.enqueue(q, "B", "x", now=NOW)
    job = q["jobs"][jid]
    lab.fail_job(job, "429", now=NOW)
    assert job["status"] == "PENDING" and job["attempts"] == 1
    assert lab.due_jobs(q, now=NOW) == []
    assert lab.due_jobs(q, now=NOW + timedelta(minutes=16)) == [job]
    for _ in range(lab.MAX_ATTEMPTS):
        lab.fail_job(job, "429", now=NOW)
    assert job["status"] == "PARKED"            # visible, never deleted
    assert lab.rearm_parked(q) == 1 and job["status"] == "PENDING"


def test_cadence_makes_one_job_per_lab_per_bucket() -> None:
    q: dict[str, Any] = {"jobs": {}}
    first = lab.ensure_cadence(q, now=NOW)
    assert len(first) == len(lab.LABS)
    assert lab.ensure_cadence(q, now=NOW + timedelta(minutes=5)) == []
    nxt = lab.ensure_cadence(q, now=NOW + timedelta(hours=1, minutes=1))
    hourly = {k for k, v in lab.LABS.items() if v["period_h"] == 1}
    assert {q["jobs"][j]["lab"] for j in nxt} == hourly


def test_events_fire_on_content_change_not_on_first_sight() -> None:
    q: dict[str, Any] = {"jobs": {}}
    marks: dict[str, Any] = {}
    assert lab.scan_events(q, _packet(), marks) == []
    assert lab.scan_events(q, _packet(), marks) == []
    made = lab.scan_events(q, _packet(data_and_features={"dirs": 2}), marks)
    assert {q["jobs"][j]["lab"] for j in made} == set(lab.SECTION_EVENTS["data_and_features"])


# ------------------------------------------------------------------------ scoring (26)

def test_selection_holds_a_cold_floor_and_one_job_per_lab() -> None:
    q: dict[str, Any] = {"jobs": {}}
    for lb in ("B", "B2", "L", "A", "M"):
        lab.enqueue(q, lb if lb in lab.LABS else "B", f"t:{lb}", now=NOW)
    for lb in ("L", "M"):
        lab.enqueue(q, lb, f"event:x:{lb}", now=NOW)
    attrib = {"by_lab": {"A": {"calls": 50}, "L": {"calls": 5, "compiled": 20}}}
    picked = lab.select(lab.due_jobs(q, now=NOW), attrib, 3, now=NOW)
    labs = [j["lab"] for j in picked]
    assert "A" in labs                           # cold floor beats a measured-poor score
    assert len(labs) == len(set(labs)) == 3


def test_a_lab_earns_work_only_through_measured_yield() -> None:
    assert lab.lab_rate({}, "Q") == (1.0, "PROBATION")
    good = lab.lab_rate({"by_lab": {"B": {"calls": 10, "compiled": 9}}}, "B")[0]
    bad = lab.lab_rate({"by_lab": {"B": {"calls": 10}}}, "B")[0]
    assert good > bad


# ------------------------------------------------------------------- contract (10, 16)

def test_an_exact_formula_candidate_is_testable_now(root: Path) -> None:
    rec = lab.validate(dict(EXACT), _ctx(root))
    o = rec["object"]
    assert o["disposition"] == "TESTABLE_NOW", o["reasons"]
    assert o["symbols"] == ["EURUSD"]            # registry spelling
    assert o["schema_version"] == lab.SCHEMA_VERSION


def test_vague_rules_are_refused_not_repaired(root: Path) -> None:
    o = lab.validate({**EXACT, "entry_rule": "enter on a strong trend"}, _ctx(root))["object"]
    assert o["disposition"] == "NEEDS_RULE_EXTRACTION"
    assert o["object_type"] == "MECHANISM_HYPOTHESIS"
    assert any(r.startswith("VAGUE_RULE") for r in o["reasons"])


def test_an_unknown_series_becomes_a_data_request(root: Path) -> None:
    rec = lab.validate({**EXACT, "data_inputs": [{"series_id": "lme_cancelled_warrants"}]},
                       _ctx(root))
    assert rec["object"]["disposition"] == "NEEDS_DATA"
    assert rec["data_requests"][0]["variable"] == "lme_cancelled_warrants"


def test_an_invalid_expression_or_unregistered_family_is_named(root: Path) -> None:
    bad = lab.validate({**EXACT, "params": {**EXACT["params"], "expr": "mean(close, 20)"}},
                       _ctx(root))["object"]
    assert bad["disposition"] == "NEEDS_RULE_EXTRACTION"
    assert any("EXPR" in r for r in bad["reasons"])
    new = lab.validate({**EXACT, "family": "gamma_flip_sniper"}, _ctx(root))["object"]
    assert new["disposition"] == "NEEDS_NEW_EXECUTABLE_FAMILY"


def test_banal_indicator_rules_are_not_discoveries(root: Path) -> None:
    o = lab.validate({**EXACT, "title": "RSI 30 oversold bounce",
                      "data_inputs": [{"series_id": "close"}]}, _ctx(root))["object"]
    assert o["disposition"] == "INVALID" and "BANAL_INDICATOR_VARIANT" in o["reasons"]


def test_simple_but_new_is_accepted(root: Path) -> None:
    o = lab.validate({**EXACT, "params": {"expr": "sign(delta(oil, 24))", "side_mode": "follow"},
                      "title": "oil 24-bar impulse leads CAD-free USD"}, _ctx(root))["object"]
    assert o["disposition"] == "TESTABLE_NOW", o["reasons"]


def test_unparseable_reply_is_schema_invalid_not_a_crash() -> None:
    assert lab.parse_objects("I think gold goes up") == ([], "SCHEMA_INVALID")
    objs, st = lab.parse_objects('Sure:\n```json\n{"objects": [{"title": "x"}]}\n```')
    assert st == "OK" and objs == [{"title": "x"}]


# ------------------------------------------------------------- novelty / genealogy (15)

def test_duplicates_collapse_and_neighbours_share_a_trial_family(root: Path) -> None:
    ctx = _ctx(root)
    o = lab.validate(dict(EXACT), ctx)["object"]
    n1 = lab.novelty(o, [])
    assert n1["class"] == "GENUINELY_NOVEL"
    f = lab.freeze(root, o, n1, {"model": "m"})
    assert f["status"] == "FROZEN_PRE_EVALUATION"
    mem = lab.load_memory(root)
    assert lab.novelty(o, mem)["class"] == "EXACT_DUPLICATE"
    p2 = lab.validate({**EXACT, "params": {**EXACT["params"], "entry_z": 2.0}}, ctx)["object"]
    n2 = lab.novelty(p2, mem)
    assert n2["class"] == "PARAMETER_NEIGHBOUR"
    assert n2["trial_family_id"] == f["trial_family_id"]
    x = lab.validate({**EXACT, "symbols": ["GBPUSD"]}, ctx)["object"]
    assert lab.novelty(x, mem)["class"] == "CROSS_ASSET_TRANSLATION"


def test_a_frozen_id_changes_when_any_rule_changes(root: Path) -> None:
    ctx = _ctx(root)
    a = lab.validate(dict(EXACT), ctx)["object"]
    b = lab.validate({**EXACT, "stop_rule": "2.5 ATR(20)"}, ctx)["object"]
    fa = lab.freeze(root, a, lab.novelty(a, []), {})
    fb = lab.freeze(root, b, lab.novelty(b, []), {})
    assert fa["hypothesis_id"] != fb["hypothesis_id"]


# --------------------------------------------------------------------- routing (21)

def _route(root: Path, objs: list[dict[str, Any]]) -> dict[str, Any]:
    ctx = _ctx(root)
    recs = [lab.validate(o, ctx) for o in objs]
    return lab.route(root, recs, lab="B", prov={"model": "deepseek/x"}, ctx=ctx,
                     memory=ctx["memory"])


def test_exact_candidates_reach_the_compiler_as_exact_recipes(root: Path) -> None:
    out = _route(root, [dict(EXACT)])
    assert out["counts"]["exact"] == 1
    doc = json.loads(Path(out["donated_to"]).read_text("utf-8"))
    row = doc["discoveries"][0]
    assert row["params"]["expr"] == EXACT["params"]["expr"]
    assert row["params"]["session"] == "ny"
    assert row["url"].startswith("deepseek://B/dsh_")
    # The SAME compiler door every miner uses: EXACT_RECIPE, no DeepSeek lane.
    sys.path.insert(0, str(REPO / "desks/mt5/research"))
    sys.path.insert(0, str(REPO / "desks/mt5"))
    import miner_candidate_compiler as mcc
    cands, why = mcc.compile_row("deepseek", row, {"EURUSD", "GBPUSD"})
    assert why == "EXACT_RECIPE"
    assert cands[0]["family"] == "formula" and cands[0]["source_url"] == row["url"]


def test_duplicate_output_is_collapsed_not_donated_twice(root: Path) -> None:
    _route(root, [dict(EXACT)])
    out = _route(root, [dict(EXACT)])
    assert out["counts"] == {"duplicate": 1} and out["donated_to"] is None


def test_incomplete_output_enters_deepening_and_invalid_is_named(root: Path) -> None:
    out = _route(root, [{"object_type": "MECHANISM_HYPOTHESIS", "title": "pension rebalancing",
                         "mechanism": "month-end rebalancing sells winners"},
                        {"object_type": "NEGATIVE_KNOWLEDGE", "title": "x"}])
    assert out["counts"].get("deepening") == 1
    row = json.loads(Path(out["donated_to"]).read_text("utf-8"))["discoveries"][0]
    assert row["kind"] == "hypothesis" and "params" not in row
    assert any(r["route"] == "NEGATIVE_MEMORY" for r in out["receipts"])


def test_data_request_lifecycle_reaches_the_frontier_and_resumes(root: Path) -> None:
    _route(root, [{**EXACT, "data_inputs": [{"series_id": "lme_warrants"}]}])
    reqs = json.loads((root / lab.REQUESTS).read_text("utf-8"))
    (rid, r), = reqs["open"].items()
    assert r["object_type"] == "DATA_REQUEST" and r["parent_hypothesis"].startswith("dsh_")
    frontier = json.loads((root / lab.FRONTIER).read_text("utf-8"))
    assert frontier["vectors"]["deepseek data request: lme_warrants"]["outcome"] == "NAMED_ONLY"
    q: dict[str, Any] = {"jobs": {}}
    assert lab.recheck_requests(root, {"eurusd"}, q) == []
    assert lab.recheck_requests(root, {"lme_warrants"}, q) == [rid]
    (job,) = q["jobs"].values()
    assert job["lab"] == "CONV" and job["trigger"].startswith("resume:dsh_")


def test_representation_with_a_valid_expr_becomes_a_formula_candidate(root: Path) -> None:
    out = _route(root, [{"object_type": "REPRESENTATION_REQUEST", "title": "usd persistence",
                         "symbols": ["USDJPY"], "expr": "ts_rank(usd, 48)"}])
    assert out["counts"].get("exact") == 1


def test_coverage_debt_waits_for_the_parent_verdict_then_drains_by_cursor(root: Path) -> None:
    out = _route(root, [dict(EXACT)])
    hid = out["receipts"][0]["hypothesis_id"]
    d0 = lab.drain_debt(root, 10)
    assert d0["donated"] == 0 and d0["awaiting_parent_verdict"] == 2   # owed, not dropped
    (root / lab.ATTRIBUTION).write_text(json.dumps(
        {"gauntlet": {"verdicts": {hid: {"judged": 1, "passed": 0}}}}), "utf-8")
    d1 = lab.drain_debt(root, 1)
    assert d1["donated"] == 1 and d1["owed"] == 1      # GBPUSD, USDJPY: one now, one owed
    d2 = lab.drain_debt(root, 10)
    assert d2["donated"] == 1 and d2["owed"] == 0
    assert lab.drain_debt(root, 10)["donated"] == 0


# ------------------------------------------------------------------- models (27, 28)

REG = {"data": [
    {"id": "deepseek/deepseek-chat-v4:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 2, "supported_parameters": ["response_format"]},
    {"id": "deepseek/deepseek-r2:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 3, "supported_parameters": ["reasoning"]},
    {"id": "qwen/qwen3:free", "pricing": {"prompt": "0", "completion": "0"}, "created": 9},
]}


def test_registry_seats_every_free_model_of_every_family_and_never_a_paid_one(root: Path) -> None:
    paid = {"id": "openai/gpt-9", "pricing": {"prompt": "0.01", "completion": "0.02"}}
    reg = lab.refresh_models(root, fetch=lambda _u: {"data": [*REG["data"], paid]}, now=NOW)
    assert reg["status"] == "MEASURED"
    assert {m["id"] for m in reg["models"]} == {"deepseek/deepseek-chat-v4:free",
                                                "deepseek/deepseek-r2:free", "qwen/qwen3:free"}
    assert reg["families"] == ["deepseek", "qwen"]


def test_coverage_slot_goes_to_the_least_called_seat_then_yield_ranks(root: Path) -> None:
    reg = lab.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    attrib = {"by_model": {
        "deepseek/deepseek-chat-v4:free": {"calls": 10, "compiled": 9, "passed": 2},
        "deepseek/deepseek-r2:free": {"calls": 10, "compiled": 0},
        "qwen/qwen3:free": {"calls": 0}}}
    cov = lab.plan_seats("bulk", reg, attrib, coverage=True)
    assert cov["seats"][0] == "qwen/qwen3:free" and "coverage" in cov["why"]
    best = lab.plan_seats("bulk", reg, attrib)
    assert best["seats"][0] == "deepseek/deepseek-chat-v4:free"       # the producing seat leads
    spread = lab.plan_seats("bulk", reg, attrib, used={"deepseek/deepseek-chat-v4:free"})
    assert spread["seats"][-1] == "deepseek/deepseek-chat-v4:free"     # used seats drop behind
    assert lab.model_rate(attrib, "qwen/qwen3:free") == (1.0, "PROBATION")


def test_the_job_is_credited_to_the_seat_that_answered(root: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    reg = lab.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    tried: list[str] = []

    def fake_chat(_u: str, **kw: Any) -> tuple[str, str | None]:
        tried.append(kw["seat"].model)
        return ("", "429 rate limited") if len(tried) == 1 else ('{"objects": []}', None)

    monkeypatch.setattr(llm_seat, "chat", fake_chat)
    chat = lab.make_chat({"OPENROUTER_API_KEY": "k"}, reg, {})
    out = chat("u", "s", "bulk")
    assert out["model"] == tried[1] != tried[0]
    assert out["attempts"] == [{"provider": "openrouter", "model": tried[0],
                                "error": "429 rate limited"}]
    assert out["family"] == lab.model_family(tried[1])


def test_a_seat_swapped_inside_llm_seat_is_credited_to_the_model_that_answered(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    reg = lab.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    monkeypatch.setattr(llm_seat, "chat", lambda _u, **_k: ('{"objects": []}', None))
    monkeypatch.setattr(llm_seat, "last_resolved", lambda _s: "qwen/qwen3-next:free",
                        raising=False)
    out = lab.make_chat({"OPENROUTER_API_KEY": "k"}, reg, {})("u", "s", "bulk")
    assert out["model"] == "qwen/qwen3-next:free" and out["family"] == "qwen"
    assert out["attempts"][0]["swapped_to"] == "qwen/qwen3-next:free"


def test_no_free_seat_listed_is_model_unavailable_not_a_paid_route(root: Path) -> None:
    reg = lab.refresh_models(root, fetch=lambda _u: {"data": [
        {"id": "openai/gpt-9", "pricing": {"prompt": "0.01"}}]}, now=NOW)
    assert lab.plan_seats("bulk", reg, {}, pin="openai/gpt-9")["seats"] == []
    dark = {"status": "UNMEASURED"}
    assert lab.plan_seats("bulk", dark, {}, pin="openai/gpt-9")["seats"] == []


def test_an_unreachable_registry_is_unmeasured_and_keeps_the_pin(root: Path) -> None:
    def boom(_u: str) -> Any:
        raise OSError("403")
    reg = lab.refresh_models(root, fetch=boom, now=NOW)
    assert reg["status"] == "UNMEASURED"
    assert lab.plan_seats("bulk", reg, {}, pin="deepseek/x:free")["seats"] == ["deepseek/x:free"]


def test_the_local_seat_takes_any_open_weight_family() -> None:
    assert lab.local_seat({"LLM_LAB_LOCAL_BASE_URL": "http://127.0.0.1:11434/v1",
                           "LLM_LAB_LOCAL_MODEL": "qwen3:14b"}) == (
        "http://127.0.0.1:11434/v1", "qwen3:14b")
    old = {"DEEPSEEK_LOCAL_BASE_URL": "u", "DEEPSEEK_LOCAL_MODEL": "m"}
    assert lab.local_seat(old) == ("u", "m")


def test_the_local_rung_refuses_anything_but_loopback() -> None:
    text, err = lab._local_chat("u", "s", "deepseek-r1:14b", "http://10.0.0.5:11434/v1")
    assert text == "" and err and err.startswith("LOCAL_REFUSED")


# ------------------------------------------------- the cycle, end to end (39) + fences

def _stub_chat(reply: str):
    calls: list[dict[str, str]] = []

    def chat(user: str, system: str, tier: str) -> dict[str, Any]:
        calls.append({"user": user, "system": system, "tier": tier})
        return {"text": reply, "provider": "stub", "model": "deepseek/stub:free"}
    return chat, calls


def _cycle(root: Path, chat, k: int = 2, packet: dict[str, Any] | None = None):
    return lab.cycle(root, packet=packet or _packet(), policy_hash="h" * 64, env={},
                     chat=chat, k=k, fetch=lambda _u: REG, now=NOW)


def test_smoke_job_to_donation_to_compiler_to_attribution(root: Path) -> None:
    chat, _calls = _stub_chat(json.dumps({"objects": [EXACT]}))
    out = _cycle(root, chat, k=1)
    run = out["runs"][0]
    assert run["status"] == "OK" and run["seal"] == "SEALED"
    assert run["counts"]["exact"] == 1
    attrib = json.loads((root / lab.ATTRIBUTION).read_text("utf-8"))
    assert attrib["calls"][0]["model"] == "deepseek/stub:free"
    assert attrib["by_lab"][run["lab"]]["exact"] == 1
    assert attrib["by_family"]["deepseek"]["calls"] == 1
    m = out["metrics"]
    assert m["production_24h"]["exact"] == 1
    assert m["pipeline"]["gauntlet"]["status"].startswith("UNMEASURED")   # never zero-as-healthy
    assert ds.inheritance_check(root)["ok"] is True                        # no parallel registry


def test_cold_generation_never_sees_held_out_outcomes(root: Path) -> None:
    chat, calls = _stub_chat('{"objects": []}')
    pk = _packet(research_frontier={"docket_rows": 3, "lockbox_sharpe": 9.9,
                                    "gauntlet_verdicts": ["PASS"], "claude_opinion": "buy"})
    _cycle(root, chat, k=len(lab.LABS), packet=pk)
    blob = " ".join(c["user"] for c in calls)
    assert calls and "lockbox_sharpe" not in blob and "gauntlet_verdicts" not in blob
    assert "claude_opinion" not in blob


def test_an_outage_preserves_the_queue_and_the_cycle_completes(root: Path) -> None:
    def down(user: str, system: str, tier: str) -> dict[str, Any]:
        return {"text": "", "error": "503 provider down"}
    out = _cycle(root, down, k=3)
    assert [r["status"] for r in out["runs"]] == ["CALL_FAILED"] * 3
    q = lab.load_queue(root)
    failed = [j for j in q["jobs"].values() if j.get("attempts")]
    assert len(failed) == 3 and all(j["status"] == "PENDING" for j in failed)
    assert out["metrics"]["liveness"]["last_successful_call_utc"].startswith("UNMEASURED")


def test_a_crashing_job_costs_the_job_not_the_cycle(root: Path) -> None:
    def crash(user: str, system: str, tier: str) -> dict[str, Any]:
        raise RuntimeError("boom")
    out = _cycle(root, crash, k=2)
    assert {r["status"] for r in out["runs"]} == {"JOB_ERROR"}


def test_the_lab_writes_nothing_on_the_money_path(root: Path) -> None:
    chat, _ = _stub_chat(json.dumps({"objects": [
        EXACT, {"object_type": "DATA_REQUEST", "variable": "cftc_options", "title": "opts"},
        {"object_type": "VALIDATION_ATTACK", "title": "lockbox reuse", "attack": "reuse"},
        {"object_type": "EXACT_CANDIDATE", "title": "promote_survivor now and allocate_capital",
         "symbols": ["XAUUSD"]}]}))
    _cycle(root, chat, k=3)
    written = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    allowed = ("data/deepseek_lab/", "data/intelligence/deepseek/", "data/deepseek_seals/",
               "data/deepseek_evidence.jsonl", "desks/mt5/data/deep_forest_frontier.json",
               "desks/mt5/data/universe/", "desks/mt5/data/data_registry.json",
               "docs/research/capability_challengers.jsonl")
    assert all(w.startswith(allowed) for w in written), sorted(written)
    for money in ("sleeves.json", "PF_ALLOCATOR_ARMED", "pf_allocator", "LIVE_MANIFEST"):
        assert not any(money in w for w in written)
    assert ds.fence("promote_survivor")["allowed"] is False


def test_a_maintenance_pass_runs_with_zero_calls(root: Path) -> None:
    chat, calls = _stub_chat("{}")
    out = _cycle(root, chat, k=0)
    assert calls == [] and out["runs"] == []
    assert out["metrics"]["queue"]["pending"] == len(lab.LABS)


def test_the_runner_reports_the_lab_and_never_fails_the_scheduler(tmp_path, monkeypatch) -> None:
    import scripts.run_deepseek_cycle as runner
    monkeypatch.setattr(runner, "_REPORT", tmp_path / "DEEPSEEK_RESEARCH.json")
    monkeypatch.setattr(runner, "_ROOT", tmp_path)
    shutil.copytree(REPO / "desks/mt5/data/universe", tmp_path / "desks/mt5/data/universe",
                    ignore=shutil.ignore_patterns("*.parquet"))
    monkeypatch.setattr(runner.ds, "policy_gate", lambda: {"ok": True, "verdict": "RESOLVED",
                                                           "policy_hash": "h", "version": "v"})
    monkeypatch.setattr(runner.ds, "budget_gate", lambda: {"ok": False, "why": "spent"})
    monkeypatch.setattr(runner.lab, "refresh_models", lambda *_a, **_k: {"status": "UNMEASURED"})
    assert runner.main([]) == 0
    rep = json.loads((tmp_path / "DEEPSEEK_RESEARCH.json").read_text("utf-8"))
    assert rep["result"] == "BUDGET_EXHAUSTED"
    assert rep["lab"]["result"] in ("MAINTENANCE_ONLY", "LAB_ERROR")


def test_futures_series_are_a_data_axis_for_exogenous_conditioners(root: Path) -> None:
    fut = root / "desks/mt5/data/intelligence/futures_state"
    fut.mkdir(parents=True)
    (fut / "lab_inputs.json").write_text(json.dumps({"generated_utc": "x", "rows": [
        {"series": "cftc_gold_mm", "kind": "positioning", "targets": ["XAUUSD"],
         "columns": ["net_oi", "net_oi_pct"], "extreme_percentiles": {"net_oi_pct": 0.95}}]}))
    from libs.ops import deepseek_packet as pk
    sec = pk._futures_state(root)
    assert sec["n_series"] == 1 and sec["series"][0]["targets"] == ["XAUUSD"]
    ok = {**EXACT, "symbols": ["XAUUSD"], "family": "exogenous_conditioner",
          "params": {"source": "cftc_gold_mm", "signal": "net_oi", "transform": "level_z",
                     "threshold": 1.5, "side_when_high": -1},
          "data_inputs": [{"series_id": "cftc_gold_mm"}]}
    assert lab.validate(ok, _ctx(root))["object"]["disposition"] == "TESTABLE_NOW"
    miss = {**ok, "params": {**ok["params"], "source": "lme_copper_stocks"},
            "data_inputs": []}
    rec = lab.validate(miss, _ctx(root))
    assert rec["object"]["disposition"] == "NEEDS_DATA"
    assert rec["data_requests"][0]["variable"] == "lme_copper_stocks"
