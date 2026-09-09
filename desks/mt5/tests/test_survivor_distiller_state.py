"""Motifs by state (Tier-1 A11): "X works primarily when state = Y", induced from certificates.

The distiller's priors were per-family PARAMETER priors; no module produced a state-conditioned
rule. Pinned: a family's survivors are grouped by the state their shadow_spec names, a RULE is
written only where they concentrate (MIN_STATE_N stated, STATE_SHARE of them in one state), a
certificate outside that state gets itself-conditioned-on-it as a neighbour, UNSTATED is unknown
and never an origin or a destination, and the neighbour reaches the queue as a task -- never a
bar screen, which cannot see a state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.hypothesis_graph import node_id  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import survivor_distiller as sd  # noqa: E402


def _c(sym: str, fam: str, params: dict, selector=None, condition=None) -> dict:
    return {"key": f"external.{sym}.{fam}.{selector}", "id": node_id(sym, fam, params),
            "symbol": sym, "family": fam, "params": params, "gated_at": "",
            "selector": selector, "condition": condition, "mechanism": f"{fam} on {sym}: toy"}


def test_state_of_names_what_the_certificate_names() -> None:
    assert sd.state_of(_c("X", "f", {}, "asia")) == "selector=asia"
    assert sd.state_of(_c("X", "f", {}, "afternoon", "NORMAL_DAY")) == \
        "selector=afternoon|condition=NORMAL_DAY"
    assert sd.state_of(_c("X", "f", {}, None, "NORMAL_DAY")) == "condition=NORMAL_DAY"
    assert sd.state_of(_c("X", "f", {})) == sd.UNSTATED_STATE
    assert sd._state_fields("selector=afternoon|condition=NORMAL_DAY") == \
        {"selector": "afternoon", "condition": "NORMAL_DAY"}


def _certified() -> list[dict]:
    return [_c("A", "srb", {"rr": 1}, "asia"), _c("B", "srb", {"rr": 1}, "asia"),
            _c("C", "srb", {"rr": 1}, "asia"), _c("D", "srb", {"rr": 1}, "london"),
            _c("E", "srb", {"rr": 1}),                       # graph-only: unstated
            _c("F", "carry", {"k": 2}, "ny"),                # one stated survivor: no rule
            _c("G", "dav", {"k": 1}, "afternoon", "NORMAL_DAY"),
            _c("H", "dav", {"k": 1}, "asia", "NORMAL_DAY")]   # split 1/1: no concentration


def test_a_rule_is_written_only_where_survivors_concentrate() -> None:
    m = sd.motifs_by_state(_certified())
    srb = m["srb"]
    assert (srb["n"], srb["n_stated"], srb["n_unstated"]) == (5, 4, 1)
    assert srb["states"] == {"selector=asia": 3, "selector=london": 1}
    assert srb["dominant"] == "selector=asia" and srb["share"] == 0.75 and srb["concentrated"]
    assert srb["rule"] == "srb survivors concentrate in selector=asia: 3 of 4 stated certificate(s)"
    assert m["carry"]["concentrated"] is False and m["carry"]["rule"] is None
    assert m["carry"]["why_no_rule"] == "1 stated certificate(s) < 2"
    assert m["dav"]["concentrated"] is False and "50%" in m["dav"]["why_no_rule"]
    assert "strict majority" in m["dav"]["why_no_rule"]
    assert sd.motifs_by_state([]) == {}


def test_only_a_certificate_outside_the_dominant_state_is_conditioned_and_only_once() -> None:
    certs = _certified()
    m = sd.motifs_by_state(certs)
    existing: set[str] = set()
    ns = sd.state_neighbours(certs, m, existing)
    assert [n["symbol"] for n in ns] == ["D"], "the london cell alone steps toward asia"
    n = ns[0]
    assert n["operator"] == sd.STATE_OP and n["state"] == {"selector": "asia"}
    assert n["from_state"] == "selector=london" and n["to_state"] == "selector=asia"
    assert n["params"] == {"rr": 1} and n["id"] != node_id("D", "srb", {"rr": 1})
    assert n["id"] in existing and n["score"] == 0.75
    assert "concentrate in selector=asia" in n["mechanism"]
    assert sd.state_neighbours(certs, m, existing) == [], "the graph refuses a repeat"


def test_the_state_task_says_it_was_not_bar_screened() -> None:
    certs = _certified()
    n = sd.state_neighbours(certs, sd.motifs_by_state(certs), set())[0]
    t = sd._task(n, sd._STATE_WHY)
    assert t["kind"] == "mutation" and t["operator"] == sd.STATE_OP
    assert t["state"] == {"selector": "asia"} and t["from_state"] == "selector=london"
    assert t["symbols"] == ["D"] and t["params"] == {"rr": 1} and t["parent"] == n["parent"]
    assert "shadow harness" in t["description"] and "selector=asia" in t["title"]
    plain = sd._task({**n, "operator": "step_rr_up"}, "no bars")
    assert "state" not in plain and plain["title"].startswith("Mutate D.srb")


def test_run_reports_the_motifs_and_queues_the_conditioned_neighbour(tmp_path, monkeypatch):
    data = tmp_path / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    fam = "srb"
    survivors = {}
    for sym, sel in (("AAAUSD", "asia"), ("BBBUSD", "asia"), ("CCCUSD", "london")):
        survivors[f"external.{sym}.{fam}"] = {
            "sym": sym, "gated_at": "2026-08-25T22:00:42+00:00",
            "shadow_spec": {"symbol": sym, "family": fam, "selector": sel, "condition": None,
                            "params": {"rr": 1.5}}}
    canon = data / "canon.json"
    canon.write_text(json.dumps({"n": 3, "survivors": survivors}), "utf-8")
    monkeypatch.setattr(sd, "CANON", canon)
    monkeypatch.setattr(sd, "GRAPH", data / "graph.jsonl")
    monkeypatch.setattr(sd, "WEIGHTS", data / "weights.json")
    monkeypatch.setattr(sd, "REPORT", tmp_path / "SURVIVOR_DISTILLER.json")
    monkeypatch.setattr(pc, "UNI", tmp_path / "universe")       # no bars: nothing is screened
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    queued: list[dict] = []
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": queued.extend(tasks))
    rep = sd.run(budget_s=5.0)
    assert rep["motifs_by_state"][fam]["rule"].endswith("2 of 3 stated certificate(s)")
    assert rep["state_neighbours"] == 1 and rep["tests_run"] == 0
    mine = [t for t in queued if t["operator"] == sd.STATE_OP]
    assert len(mine) == 1 and mine[0]["symbols"] == ["CCCUSD"]
    assert mine[0]["state"] == {"selector": "asia"} and mine[0]["source"] == sd.SOURCE
    assert rep["n_tasks"] == len(queued) and rep["n_tasks"] > 1   # param neighbours queue too
    assert json.loads(sd.REPORT.read_text("utf-8"))["state_neighbours"] == 1
