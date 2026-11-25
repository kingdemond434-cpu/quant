"""The math_proposer job and the `math:llm_proposer` tradition: a free model's proposal is held to
the lab's grammar (look-ahead, unknown primitives, invented series and duplicates are dropped and
counted by reason), an accepted one is charged as a trial and judged like any other object,
donated rows carry lane=math_proposer, and the job is a registered, re-weighted free-model job."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import grammar as G  # noqa: E402
from research.mathlab import llm_proposer as MP  # noqa: E402
from research.mathlab import scientists as S  # noqa: E402
from research.mathlab.objects import Panel, Variable  # noqa: E402

from research import conversion_lanes as cl  # noqa: E402
from research import math_lab as ML  # noqa: E402

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
VOCAB = list(G.BAR_VARIABLES)
N = 2600


# ------------------------------------------------------------------------------ the grammar --
def test_the_lab_string_form_parses_back_to_the_same_tree():
    for tree in (["z", ["diff", "close", 3], 24], ["add", "ret", ["rstd", "range", 48]],
                 ["gt", ["z", "flow", 12], 1.5], ["div", ["curv", "close", 8], "atr"]):
        assert MP.parse_expr(G.to_str(G.simplify(tree))) == G.simplify(tree)


@pytest.mark.parametrize("expr,why", [
    ("lead(close, 3)", "look_ahead"),
    ("lag(close, -2)", "look_ahead"),
    ("z(fwd_ret, 24)", "look_ahead"),
    ("sub(close, center_mean(close, 24))", "look_ahead"),
    ("normalize_full(close)", "look_ahead"),
    (["rmean", "epsilon", 24], "look_ahead"),
    ("rsi(close, 14)", "unknown_operator"),
    ("z(vix_close, 24)", "unknown_variable"),
    ("z(alt:made_up:z, 24)", "alt_not_offered"),
    ("z(alt:cot_gold:z, 24)", "alt_not_on_panel"),
    ("z(close, 7)", "invalid_structure"),
    ("z(close, 24", "unparseable"),
    ("add(1, 2)", "no_variable"),
])
def test_screen_drops_by_reason(expr, why):
    tree, reason = MP.screen(expr, VOCAB, offered_alt=["alt:cot_gold:z:gt:0"])
    assert tree is None and reason == why


def test_validate_drops_duplicates_over_k_and_missing_mechanisms():
    existing = {G.to_str(G.simplify(["z", ["diff", "close", 3], 24]))}
    props = [
        {"expr": "z(diff(close, 3), 24)", "mechanism": "already in the lab"},
        {"expr": "(ret + flow)", "mechanism": "order flow adds to the bar's own return"},
        {"expr": "(flow + ret)", "mechanism": "the same law written the other way round"},
        {"expr": "z(flow, 24)", "mechanism": ""},
        {"expr": "rstd(ret, 48)", "mechanism": "volatility clustering", "kind": "representation",
         "side": "fade"},
        {"expr": "z(range, 12)", "mechanism": "past k"},
    ]
    kept, dropped = MP.validate(props, vocabulary=VOCAB, existing=existing, k=5)
    assert [k["canonical"] for k in kept] == ["(flow + ret)", "rstd(ret, 48)"]
    assert kept[1]["kind"] == "representation" and kept[1]["side_mode"] == "fade"
    assert dropped == {"duplicate_existing": 1, "duplicate_batch": 1, "no_mechanism": 1,
                       "over_k": 1}


# -------------------------------------------------------------------------------- the job ----
REPLY = json.dumps({"proposals": [
    {"expr": "z(diff(close, 3), 24)", "kind": "relationship", "side": "fade",
     "mechanism": "short-horizon overshoot by liquidity takers reverts"},
    {"expr": "mul(sign(diff(close, 8)), z(range, 48))", "side": "follow",
     "mechanism": "trend persistence is stronger when the range state is wide"},
    {"expr": "lead(close, 1)", "mechanism": "peeks"},
    {"expr": "z(vix_close, 24)", "mechanism": "invents a series"}]})


def _ask(seen: list[tuple[str, str]]):
    def ask(system: str, user: str) -> tuple[str, str, str | None]:
        seen.append((system, user))
        return REPLY, "stub/free-model", None
    return ask


def test_run_job_queues_only_validated_proposals_and_never_rerolls(tmp_path):
    q = tmp_path / "math_proposals.jsonl"
    seen: list[tuple[str, str]] = []
    report = {"panel": {"targets": ["EURUSD"], "panel_sources": {"EURUSD": "bar_baseline"},
                        "columns": [*G.BAR_VARIABLES, "cot_net_z"]},
              "per_tradition": {"spectral": {"proposed": 4, "donated": 2, "share": 0.03}},
              "objects": {"top": [{"canonical": "z(close, 240)",
                                   "evidence": {"ic_held_out": 0.123456}}]}}
    out = MP.run_job(ask=_ask(seen), calls=1, deadline=float("inf"), now=NOW, queue=q,
                     report=report, cat=None, existing=set())
    assert out["accepted"] == 2 and out["proposed"] == 4
    assert out["dropped"]["look_ahead"] == 1 and out["dropped"]["unknown_variable"] == 1
    rows = MP.read_queue(q)
    assert {r["lane"] for r in rows} == {"math_proposer"} and rows[0]["model"] == "stub/free-model"
    system, user = seen[0]
    assert "cot_net_z" in user and "spectral" in user and "z(close, 240)" in user
    assert "0.123456" not in user, "a held-out number reached the model"
    from libs.ops import cn_ensemble as cn
    cn.assert_public(system, user)               # a relay may receive this prompt
    again = MP.run_job(ask=_ask([]), calls=1, deadline=float("inf"), now=NOW, queue=q,
                       report=report, cat=None, existing=set())
    assert again["accepted"] == 0 and again["dropped"]["duplicate_existing"] == 2
    skipped = MP.run_job(ask=None, calls=3, deadline=float("inf"), queue=tmp_path / "none.jsonl")
    assert skipped["status"].startswith("SKIPPED") and not (tmp_path / "none.jsonl").exists()


def test_the_registry_validates_the_job_and_by_lane_weights_it(tmp_path):
    jobs, refused = cl.load_jobs(cl.JOBS)
    assert refused == []
    job = next(j for j in jobs if j["name"] == "math_proposer")
    assert (job["kind"], job["template"], job["status"]) == ("math_proposer",
                                                             "math_proposer_v1", "ACTIVE")
    assert "math_proposer" in cl.call_shares(jobs)
    # a file that omits it still gets it (a standing lane is never lost)
    assert "math_proposer" in [j["name"] for j in cl.load_jobs(tmp_path / "absent.json")[0]]
    rows = [{"lane": "math_proposer", "family": "formula", "symbol": "EURUSD",
             "params": {"expr": ["zscore", ["delta", "close", 3], 24], "norm": 240,
                        "entry_z": 1.5, "side_mode": "fade", "hold_bars": 8}}]
    out = cl.by_lane(rows, seen={"c1"}, certified=set(), live=None, jobs=jobs,
                     ledger={"lanes": {"math_proposer": {"inputs": 2, "outputs": 1}}},
                     cell_of=lambda r: "c1")
    mp = out["math_proposer"]
    assert isinstance(mp["weight"], float) and (mp["inputs"], mp["outputs"]) == (2, 1)
    assert mp["testable"] == 1 and mp["judged"] == 1
    rescored = {j["name"]: j for j in cl.rescore(jobs, {"math_proposer": mp}, NOW)}
    assert isinstance(rescored["math_proposer"]["weight"], float)


def test_conversion_lanes_pass_runs_the_job(tmp_path):
    rep = cl.run_pass(now=NOW, ask=_ask([]), jobs_path=tmp_path / "jobs.json",
                      compiler=tmp_path / "none.json", roster=tmp_path / "none.json",
                      funnel=tmp_path / "f.json", intel_root=tmp_path / "intel",
                      ledger_path=tmp_path / "cl" / "led.json", report_path=tmp_path / "rep.json",
                      feedback_path=tmp_path / "fb.json", cat={"status": "READ", "series": []},
                      registry_db=tmp_path / "none.sqlite")
    mp = rep["lanes"]["math_proposer"]
    assert mp["accepted"] == 2 and rep["ledger"]["math_proposer"]["outputs"] == 2
    assert len(MP.read_queue(tmp_path / "cl" / "math_proposals.jsonl")) == 2


# -------------------------------------------------------------------------------- the lab ----
def _panel(target: str, seed: int) -> Panel:
    rng = np.random.default_rng(seed)
    ret = 0.0008 * np.sin(2 * np.pi * np.arange(N) / 24) + 0.0006 * rng.normal(0, 1, N)
    close = 100.0 * np.exp(np.cumsum(ret))
    columns = {"close": close, "open": close, "high": close * 1.0004, "low": close * 0.9996,
               "ret": ret, "range": np.abs(ret) * 2 + 1e-6, "body": ret,
               "activity": 100 + 8 * np.abs(rng.normal(0, 1, N)), "spread": np.full(N, 1e-4),
               "atr": np.abs(ret) * 3 + 1e-6, "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, N)),
               "flow": rng.normal(0, 1, N)}
    epsilon = rng.normal(0, 1, N)
    return Panel(target=target, times=np.arange(N, dtype=np.int64) * 3600 + 1_600_000_000,
                 epsilon=epsilon, columns=columns,
                 meta={k: Variable(k, f"bars:{target}", "bars") for k in columns},
                 regime=np.asarray(["mid"] * N), session=np.asarray(["ny"] * N), horizon="4",
                 source="test_store", residual_discovery_id=f"disc_{target}")


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(ML, "OUT", tmp_path / "reports" / "MATH_LAB.json")
    monkeypatch.setattr(ML, "ALLOCATION", tmp_path / "data" / "math_allocation.json")
    monkeypatch.setattr(ML, "DONATED", tmp_path / "data" / "mathlab_donated.json")
    monkeypatch.setattr(ML, "MATHLAB_REPRESENTATIONS", tmp_path / "data" / "representations")
    monkeypatch.setattr(MP, "QUEUE", tmp_path / "cl" / "math_proposals.jsonl")
    monkeypatch.setattr(MP, "CONSUMED", tmp_path / "cl" / "math_proposals_consumed.json")
    panels = [_panel("EURUSD", 1)]
    monkeypatch.setattr(ML, "build_panels", lambda max_targets=4: (
        panels, {"unmeasured": [], "targets": ["EURUSD"],
                 "panel_sources": {"EURUSD": "test_store"}}))
    donated: list[dict[str, Any]] = []
    from research import proposer_common as PC

    def fake_donate(source: str, candidates: list[dict], tests_run: int) -> Path:
        donated.extend(candidates)
        return tmp_path / "intel" / source / "discoveries_test.json"

    monkeypatch.setattr(PC, "donate", fake_donate)
    monkeypatch.setattr(PC, "donation_counts", lambda: {"donated": len(donated)})
    MP.run_job(ask=_ask([]), calls=1, deadline=float("inf"), now=NOW, queue=MP.QUEUE,
               report={}, cat=None, existing=set())
    yield {"donated": donated, "registry": R}
    R.set_path(None)


def test_the_lab_charges_judges_and_donates_llm_proposals_like_any_tradition(lab):
    assert "llm_proposer" in ML.all_traditions() and "llm_proposer" not in S.TRADITIONS
    assert ML.department_of("llm_proposer") == "mathematics"
    report = ML.run(budget_s=30.0, traditions=["llm_proposer", "spectral"], permutations=20)
    per = report["per_tradition"]["llm_proposer"]
    assert per["status"] == "OK" and per["proposed"] == 2 and per["distinct"] == 2
    assert per["effective_trials"] >= 2
    share = report["allocation"]["traditions"]["llm_proposer"]
    assert share["share"] >= ML.FLOOR_SHARE and share["department"] == "mathematics"
    R = lab["registry"]
    conn = R.connect()
    try:
        trials = [dict(r) for r in conn.execute(
            "SELECT hypothesis_id, method FROM trials_ledger").fetchall()]
    finally:
        conn.close()
    assert {"hypothesis_id": "mathlab:llm_proposer", "method": "mathlab:llm_proposer"} in trials
    assert R.verify_trial_chain()[0]
    generators = {str(r.get("generator")) for r in R.discoveries(limit=500)}
    assert "math:llm_proposer" in generators
    assert "math:llm_proposer" in {str(r["generator"]) for r in R.generator_yields()}
    mine = [r for r in lab["donated"] if r["evidence"]["tradition"] == "llm_proposer"]
    assert mine and all(r["lane"] == "math_proposer" for r in mine)
    assert all(r.get("lane") != "math_proposer" for r in lab["donated"]
               if r["evidence"]["tradition"] != "llm_proposer")
    # consumed once: the next pass has nothing to re-roll
    again = ML.run(budget_s=20.0, traditions=["llm_proposer"], permutations=20)
    assert again["per_tradition"]["llm_proposer"]["proposed"] == 0


def test_a_dry_run_reads_the_queue_without_consuming_it(lab):
    first = ML.run(budget_s=20.0, dry_run=True, traditions=["llm_proposer"], permutations=20)
    assert first["per_tradition"]["llm_proposer"]["proposed"] == 2
    assert not MP.CONSUMED.exists()
    MP.CONSUME = True
