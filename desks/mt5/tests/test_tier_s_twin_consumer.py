"""Tier S S28 -> S30: the shadow desk's verdicts (reports/TWIN.json) have a consumer.

A LOSS marks the challenger REJECTED in the registry (its replay slot goes to the next open
challenger, and the twin's adoption stays REJECTED); a WIN on a money-path component is a
proposal for the principal, never an adoption; the self-model reads the report as a deficiency.

Every test runs in tmp_path; none reads or writes the desk's live data.
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import self_model  # noqa: E402


def _row(name: str, component: str = "config", **kw: Any) -> dict[str, Any]:
    return {"component": component, "name": name, "registered_at": "2026-09-01T00:00:00+00:00",
            "genome_hash": "h" + name, "genome": {"config": {"eur": {"k": 2}}}, "fitness": None,
            **kw}


def _run(name: str, verdict: str, component: str = "config", **kw: Any) -> dict[str, Any]:
    return {"name": name, "component": component, "status": "MEASURED",
            "decision_agreement": 0.8, "sandbox": {"terminal_touches": []},
            "verdict": {"verdict": verdict, "n": 34, "mean_improvement": -0.4 if verdict ==
                        "REJECT" else 0.3, "t": -3.1 if verdict == "REJECT" else 2.6,
                        "money_path": True, "terminal_touches": 0}, **kw}


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: Any) -> Path:
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "TWIN_REPORT", tmp_path / "TWIN.json")
    # the twin also drives the regression stop: keep its RELEASE_STOP.json out of the checkout
    monkeypatch.setattr(ts.regression_stop, "_root", lambda root=None: root or tmp_path)
    monkeypatch.setattr(ts, "_release_history", lambda: [{"sha": "a" * 40, "sealed": True},
                                                         {"sha": "c" * 40, "sealed": True}])
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "challengers.json").write_text(json.dumps({"challengers": [
        _row("cfg_lose"), _row("cfg_win"), _row("cfg_open"),
        _row(f"code_{'b' * 12}", "code", genome={"sha": "b" * 40}),
        _row("validator_x", "validator")]}), "utf-8")
    return tmp_path


def _write_twin(root: Path, runs: list[dict[str, Any]]) -> None:
    (root / "TWIN.json").write_text(json.dumps({
        "generated_utc": ts.NOW.isoformat(), "incumbent": "c" * 40, "status": "MEASURED",
        "runs": runs}), "utf-8")


def _registry(root: Path) -> dict[str, dict[str, Any]]:
    doc = json.loads((root / "state" / "challengers.json").read_text("utf-8"))
    return {r["name"]: r for r in doc["challengers"]}


def test_a_shadow_loss_rejects_and_a_win_is_a_principal_proposal(world: Path) -> None:
    _write_twin(world, [_run("self_consistency", "CONTINUE", "code"),
                        _run("cfg_lose", "REJECT"), _run("cfg_win", "PROPOSE"),
                        _run("cfg_open", "CONTINUE")])
    out = ts._consume_shadow_verdicts()
    assert out["rejected"] == ["cfg_lose"] and out["proposed"] == ["cfg_win"]
    reg = _registry(world)
    assert reg["cfg_lose"]["status"] == "REJECTED"
    assert reg["cfg_lose"]["rejected_by"] == "shadow_desk"
    assert reg["cfg_lose"]["shadow"]["n"] == 34 and reg["cfg_lose"]["shadow"]["t"] == -3.1
    assert reg["cfg_win"]["status"] == "PROPOSED_TO_PRINCIPAL"
    assert "status" not in reg["cfg_open"], "an undecided pair is not a verdict"
    assert "self_consistency" not in reg, "the desk replaying itself is not a challenger"
    assert len(reg) == 5, "nothing is dropped from the registry"
    props = json.loads((world / "state" / "twin_proposals.json").read_text("utf-8"))
    (p,) = props["proposals"]
    assert p["name"] == "cfg_win" and p["state"] == "AWAITING_PRINCIPAL"
    assert p["genome"] == {"config": {"eur": {"k": 2}}}
    assert p["rollback"]["target"] == "a" * 40 and "--rollback-to" in p["rollback"]["command"]
    # re-reading the same report changes nothing and keeps the proposal's first date
    since = p["proposed_since"]
    again = ts._consume_shadow_verdicts()
    assert again["rejected"] == [] and again["open_proposals"] == 1
    props2 = json.loads((world / "state" / "twin_proposals.json").read_text("utf-8"))
    assert props2["proposals"][0]["proposed_since"] == since


def test_a_later_loss_withdraws_the_proposal(world: Path) -> None:
    _write_twin(world, [_run("cfg_win", "PROPOSE")])
    ts._consume_shadow_verdicts()
    _write_twin(world, [_run("cfg_win", "REJECT")])
    out = ts._consume_shadow_verdicts()
    assert out["withdrawn"] == ["cfg_win"] and out["open_proposals"] == 0
    assert _registry(world)["cfg_win"]["status"] == "REJECTED"


def test_no_report_is_unmeasured_and_touches_nothing(world: Path) -> None:
    before = (world / "state" / "challengers.json").read_text("utf-8")
    out = ts._consume_shadow_verdicts()
    assert out["status"] == "UNMEASURED" and out["rejected"] == []
    assert (world / "state" / "challengers.json").read_text("utf-8") == before


def test_a_rejected_config_is_not_replayed_and_its_adoption_stays_rejected(
        world: Path, monkeypatch: Any) -> None:
    """The consequence on the hourly clock: organ_twin runs the shadow desk, consumes the
    report it wrote, and the NEXT pass gives the rejected challenger's slot away."""
    monkeypatch.setattr(ts, "_git_out", lambda *a: "c" * 40 if "c" * 40 in a[-1] else None)
    monkeypatch.setattr(ts, "_shadow_candidate_ref", lambda: "c" * 40)   # no new code
    monkeypatch.setattr(ts, "_shadow_sleeves", lambda: [{"name": "eur"}])
    monkeypatch.setattr(ts.authority, "suspended", lambda k: False)
    monkeypatch.setattr(ts, "live_rows", list)
    monkeypatch.setattr(ts, "_jsonl", lambda *a, **k: [])
    monkeypatch.setattr(ts, "names", lambda: None)
    monkeypatch.setattr(ts, "_judge_validators", lambda *a: {"status": "IDLE"})
    monkeypatch.setattr(ts.self_model, "adoption", lambda c, v, m, b: "SHADOW")
    replayed: list[list[str]] = []
    verdict_of = {"cfg_lose": "REJECT", "cfg_win": "PROPOSE", "cfg_open": "CONTINUE"}

    def fake_shadow(ch: Any, ref: str, inc: str, sleeves: Any, **kw: Any) -> dict[str, Any]:
        replayed[-1].append(ch.name)
        run = _run(ch.name, verdict_of.get(ch.name, "CONTINUE"), ch.component)
        return {k: v for k, v in run.items() if k not in ("name", "component")} | {
            "sleeves": [{"name": "eur", "status": "MEASURED"}], "pairs": []}

    monkeypatch.setattr(ts.twin, "shadow", fake_shadow)
    monkeypatch.setattr(ts, "SHADOW_MAX_CONFIG", 2)
    replayed.append([])
    first = ts.organ_twin({})
    # registry order cfg_lose, cfg_win, cfg_open: the last two configs are replayed first
    assert replayed[0] == ["self_consistency", "cfg_win", "cfg_open"]
    assert first["shadow_consumer"]["proposed"] == ["cfg_win"]
    # an hour later cfg_open's own replay has lost ...
    _write_twin(world, [_run("cfg_open", "REJECT")])
    ts._consume_shadow_verdicts()
    replayed.append([])
    second = ts.organ_twin({})
    # ... and the rejected challenger's slot goes to the next open one
    assert replayed[1] == ["self_consistency", "cfg_lose", "cfg_win"]
    assert second["shadow_consumer"]["rejected"] == ["cfg_lose"]
    adoption = {r["name"]: r["adoption"] for r in second["challengers"]}
    assert adoption["cfg_open"] == "REJECTED", "a rejected challenger never reads SHADOW"
    assert adoption["cfg_lose"] == "REJECTED"
    assert second["metric"]["shadow_rejected"] == 1
    assert second["metric"]["principal_proposals"] == 1


# ------------------------------------------------------------------ the self-model's reading

def _doc(**code: Any) -> dict[str, Any]:
    run = {"name": "code_x", "component": "code", "status": "MEASURED",
           "sandbox": {"terminal_touches": []}, "decision_agreement": 0.9,
           "verdict": {"verdict": "CONTINUE", "n": 3}}
    run.update(code)
    return {"status": "MEASURED", "runs": [run]}


def test_shadow_desk_gap_reads_the_candidate_code() -> None:
    gap = self_model.shadow_desk_gap
    assert gap(None)[0] is None
    assert gap({"status": "UNMEASURED", "why": "no bars"}) == (
        None, "shadow desk UNMEASURED: no bars")
    lose = _doc(verdict={"verdict": "REJECT", "n": 31, "mean_improvement": -0.2, "t": -2.4})
    g, why = gap(lose)
    assert g == 1.0 and "LOSES" in why and "31 pairs" in why
    assert gap(_doc(verdict={"verdict": "PROPOSE", "n": 40}))[0] == 0.0
    assert gap(_doc())[0] is None, "undecided is half weight, never clean"
    touched = _doc(sandbox={"terminal_touches": ["initialize", "order_send"]})
    assert gap(touched)[0] == 1.0
    same = _doc(same_code=True, decision_agreement=0.75)
    g, why = gap(same)
    assert g == pytest.approx(0.25) and "75.0%" in why
    assert gap(_doc(same_code=True, decision_agreement=1.0))[0] == 0.0
    assert gap(_doc(status="UNMEASURED", why="materialise failed"))[0] is None


def test_the_self_model_ranks_a_losing_candidate_as_a_deficiency() -> None:
    lose = _doc(verdict={"verdict": "REJECT", "n": 31, "mean_improvement": -0.2, "t": -2.4})
    rows = {r["area"]: r for r in self_model.inventory({"shadow_desk": lose})}
    assert rows["twin.shadow_desk"]["gap"] == 1.0
    assert rows["twin.shadow_desk"]["gain"] == "OPERATIONAL_RISK"
    assert "twin.shadow_desk" not in {r["area"] for r in self_model.inventory({})}, \
        "counted only when the caller passes the report"
    ranked = {r["area"]: r for r in self_model.rank(self_model.inventory({"shadow_desk": lose}))}
    # gap 1 x OPERATIONAL_RISK 0.6 x p_fix 0.6 / cost 1
    assert ranked["twin.shadow_desk"]["expected_improvement"] == pytest.approx(0.36)


def test_the_self_model_reads_twin_json_and_refuses_a_stale_one(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "TWIN_REPORT", tmp_path / "TWIN.json")
    assert ts._shadow_doc_for_self_model()["status"] == "UNMEASURED"
    doc = {**_doc(verdict={"verdict": "REJECT", "n": 30}), "generated_utc": ts.NOW.isoformat()}
    (tmp_path / "TWIN.json").write_text(json.dumps(doc), "utf-8")
    assert ts._shadow_doc_for_self_model()["runs"][0]["name"] == "code_x"
    old = ts.NOW - timedelta(hours=ts.TWIN_MAX_AGE_H + 1)
    (tmp_path / "TWIN.json").write_text(json.dumps({**doc, "generated_utc": old.isoformat()}),
                                        "utf-8")
    stale = ts._shadow_doc_for_self_model()
    assert stale["status"] == "UNMEASURED" and "older than" in stale["why"]


def test_organ_self_model_carries_the_shadow_deficiency_to_its_docket(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "TWIN_REPORT", tmp_path / "TWIN.json")
    monkeypatch.setattr(ts, "_operational_self_facts", lambda: {
        "queue_status": {}, "oldest_waiting_h": None, "verdicts_per_h": None,
        "compute": [{"run": "x", "outcome": "ok"}],
        "allocation": {"heat": {"binding": "", "free_optimum": 1.0, "total": 1.0}}})
    doc = {**_doc(verdict={"verdict": "REJECT", "n": 30, "mean_improvement": -0.5, "t": -4}),
           "generated_utc": ts.NOW.isoformat()}
    (tmp_path / "TWIN.json").write_text(json.dumps(doc), "utf-8")
    reports: dict[str, Any] = {}
    out = ts.organ_self_model(reports)
    areas = {d["area"]: d for d in out["deficiencies"]}
    assert areas["twin.shadow_desk"]["gap"] == 1.0
    assert "shadow_desk" not in reports, "the caller's reports are not mutated"
    docket = json.loads((tmp_path / "state" / "SELF_MODEL_DOCKET.json").read_text("utf-8"))
    assert any(t["task"] == "Tier S deficiency: twin.shadow_desk" for t in docket["tasks"])
