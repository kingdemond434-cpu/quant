"""The 24/7 LLM research lab (libs/ops/deepseek_lab.py): queue, scoring and the cycle end to end.

Every test runs in a temporary root; nothing here writes the repository's own state."""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import deepseek_cycle as ds
from libs.ops import deepseek_lab as lab
from libs.ops import llm_lab_core as core

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def families() -> dict[str, list[str]]:
    fams = core.family_specs(REPO)
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
    monkeypatch.setattr(core, "family_specs", lambda _root: families)
    return tmp_path


def _ctx(root: Path) -> dict[str, Any]:
    return core.context(root)


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
    q = core.load_queue(root)
    assert core.enqueue(q, "A", "cadence:1h:1") is not None
    assert core.enqueue(q, "A", "cadence:1h:1") is None
    core.save_queue(root, q)
    q2 = core.load_queue(root)                   # a restart reads the same jobs
    assert len(q2["jobs"]) == 1
    assert next(iter(q2["jobs"].values()))["status"] == "PENDING"


def test_provider_failure_keeps_the_job_with_backoff_then_parks_and_rearms() -> None:
    q: dict[str, Any] = {"jobs": {}}
    jid = core.enqueue(q, "B", "x", now=NOW)
    job = q["jobs"][jid]
    core.fail_job(job, "429", now=NOW)
    assert job["status"] == "PENDING" and job["attempts"] == 1
    assert core.due_jobs(q, now=NOW) == []
    assert core.due_jobs(q, now=NOW + timedelta(minutes=16)) == [job]
    for _ in range(core.MAX_ATTEMPTS):
        core.fail_job(job, "429", now=NOW)
    assert job["status"] == "PARKED"            # visible, never deleted
    assert core.rearm_parked(q) == 1 and job["status"] == "PENDING"


def test_cadence_makes_one_job_per_lab_per_bucket() -> None:
    q: dict[str, Any] = {"jobs": {}}
    first = core.ensure_cadence(q, now=NOW)
    assert len(first) == len(core.LABS)
    assert core.ensure_cadence(q, now=NOW + timedelta(minutes=5)) == []
    nxt = core.ensure_cadence(q, now=NOW + timedelta(hours=1, minutes=1))
    hourly = {k for k, v in core.LABS.items() if v["period_h"] == 1}
    assert {q["jobs"][j]["lab"] for j in nxt} == hourly


def test_events_fire_on_content_change_not_on_first_sight() -> None:
    q: dict[str, Any] = {"jobs": {}}
    marks: dict[str, Any] = {}
    assert core.scan_events(q, _packet(), marks) == []
    assert core.scan_events(q, _packet(), marks) == []
    made = core.scan_events(q, _packet(data_and_features={"dirs": 2}), marks)
    assert {q["jobs"][j]["lab"] for j in made} == set(core.SECTION_EVENTS["data_and_features"])


# ------------------------------------------------------------------------ scoring (26)

def test_selection_holds_a_cold_floor_and_one_job_per_lab() -> None:
    q: dict[str, Any] = {"jobs": {}}
    for lb in ("B", "B2", "L", "A", "M"):
        core.enqueue(q, lb if lb in core.LABS else "B", f"t:{lb}", now=NOW)
    for lb in ("L", "M"):
        core.enqueue(q, lb, f"event:x:{lb}", now=NOW)
    attrib = {"by_lab": {"A": {"calls": 50}, "L": {"calls": 5, "compiled": 20}}}
    picked = lab.select(core.due_jobs(q, now=NOW), attrib, 3, now=NOW)
    labs = [j["lab"] for j in picked]
    assert "A" in labs                           # cold floor beats a measured-poor score
    assert len(labs) == len(set(labs)) == 3


def test_a_lab_earns_work_only_through_measured_yield() -> None:
    assert lab.lab_rate({}, "Q") == (1.0, "PROBATION")
    good = lab.lab_rate({"by_lab": {"B": {"calls": 10, "compiled": 9}}}, "B")[0]
    bad = lab.lab_rate({"by_lab": {"B": {"calls": 10}}}, "B")[0]
    assert good > bad



REG = {"data": [
    {"id": "deepseek/deepseek-chat-v4:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 2, "supported_parameters": ["response_format"]},
    {"id": "deepseek/deepseek-r2:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 3, "supported_parameters": ["reasoning"]},
    {"id": "qwen/qwen3:free", "pricing": {"prompt": "0", "completion": "0"}, "created": 9},
]}



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
    attrib = json.loads((root / core.ATTRIBUTION).read_text("utf-8"))
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
    _cycle(root, chat, k=len(core.LABS), packet=pk)
    blob = " ".join(c["user"] for c in calls)
    assert calls and "lockbox_sharpe" not in blob and "gauntlet_verdicts" not in blob
    assert "claude_opinion" not in blob


def test_an_outage_preserves_the_queue_and_the_cycle_completes(root: Path) -> None:
    def down(user: str, system: str, tier: str) -> dict[str, Any]:
        return {"text": "", "error": "503 provider down"}
    out = _cycle(root, down, k=3)
    assert [r["status"] for r in out["runs"]] == ["CALL_FAILED"] * 3
    q = core.load_queue(root)
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
    assert out["metrics"]["queue"]["pending"] == len(core.LABS)


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
    assert core.validate(ok, _ctx(root))["object"]["disposition"] == "TESTABLE_NOW"
    miss = {**ok, "params": {**ok["params"], "source": "lme_copper_stocks"},
            "data_inputs": []}
    rec = core.validate(miss, _ctx(root))
    assert rec["object"]["disposition"] == "NEEDS_DATA"
    assert rec["data_requests"][0]["variable"] == "lme_copper_stocks"
