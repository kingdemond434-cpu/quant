"""THE ASIA DIRECTIVE'S COMPLETION AUDIT, ON FIXTURES.

The ladder is read from runtime artifacts: code lifts a row only to SCHEDULED, an absent artifact
is UNMEASURED, a blocked source is BLOCKED, a failed XLIV verification holds a row at RUNNING.
The three feedback-loop proofs (EVIG -> collection order, ROI -> forest budget, deep-forest
language rotation) are PROVEN only from a before/after decision record joined with what the
consumer actually did -- and the organs that write those records are tested to write them.
Every fixture lives in tmp_path; nothing here writes a tracked file."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_spec = importlib.util.spec_from_file_location("check_asia_directive",
                                               _ROOT / "scripts" / "check_asia_directive.py")
assert _spec and _spec.loader
CAD = importlib.util.module_from_spec(_spec)
sys.modules["check_asia_directive"] = CAD
_spec.loader.exec_module(CAD)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def _w(root: Path, rel: str, doc: Any) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return p


def _jl(root: Path, rel: str, rows: list[dict[str, Any]]) -> None:
    _w(root, rel, "".join(json.dumps(r) + "\n" for r in rows))


def _reqs(root: Path, rows: list[dict[str, Any]]) -> None:
    _w(root, CAD.REQS_REL, {"ladder": list(CAD.LADDER), "requirements": rows})


def _tree(root: Path) -> None:
    """A tiny repo: one hourly leg, one owner module."""
    _w(root, "desks/mt5/research/hourly_cycle.py",
       'alt = _costed("alt_proxies", lambda: 0)\nsev = _costed("research_roi", lambda: 0)\n')
    _w(root, "desks/mt5/research/alt_proxies.py", "# fixture owner\nPLACEBO = 'release_gain'\n")


def _row(**kw: Any) -> dict[str, Any]:
    base = {"id": "R06", "title": "NBS retail", "parts": ["I.C"], "region": "CN",
            "owner": ["desks/mt5/research/alt_proxies.py"], "scheduler": ["hourly:alt_proxies"],
            "probes": [{"kind": "alt_proxies", "artifact": "desks/mt5/reports/ALT_PROXIES.json",
                        "ids": ["cn_nbs_retail"]}]}
    base.update(kw)
    return base


def _item(root: Path) -> dict[str, Any]:
    return CAD.audit(root, NOW)["items"][0]


# ------------------------------------------------------------------------- the real data file
def test_the_requirement_file_covers_every_report_row_and_is_well_formed() -> None:
    rd = CAD.Reader(_ROOT)
    rows, errors = CAD.load_requirements(rd)
    assert errors == []
    assert len(rows) == 55
    assert sorted(r["report_row"] for r in rows) == list(range(1, 56))
    xliv = {r["id"] for r in rows if r.get("xliv")}
    # the directive's XLIV list: latent state, dislocation lab, SGE, SHFE ranks, SHFE warehouse,
    # SAFE, CFETS, ports, procurement, Tianyancha, Copernicus/FIRMS, Baidu, JQuants/BOJ/KRX/HKMA,
    # trader genome, EVIG, ROI, deep forest
    for rid in ("R38", "R37", "R08", "R11", "R12", "R01", "R03", "R18", "R24", "R23", "R25",
                "R26", "R27", "R29", "R30", "R31", "R33", "R35", "R43", "R44", "R45"):
        assert rid in xliv, rid
    for r in rows:
        assert r["probes"], f"{r['id']} names no evidence artifact"


# ------------------------------------------------------------------------------- the ladder
def test_no_artifact_is_unmeasured_never_a_pass(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    it = _item(tmp_path)
    assert it["static_rung"] == "SCHEDULED"
    assert it["state"] == "UNMEASURED"
    assert it["cells_emitted"] == "UNMEASURED" and it["observations"] == "UNMEASURED"


def test_missing_owner_or_marker_is_absent(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row(owner=["desks/mt5/research/nope.py"])])
    assert _item(tmp_path)["state"] == "ABSENT"
    _reqs(tmp_path, [_row(code_markers=[{"path": "desks/mt5/research/alt_proxies.py",
                                         "contains": "parse_s5p"}])])
    assert _item(tmp_path)["state"] == "ABSENT"


def test_unscheduled_code_is_coded_or_wired(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row(scheduler=["daily:book_forensics"])])
    assert _item(tmp_path)["state"] == "CODED"
    _w(tmp_path, "desks/mt5/research/other.py", "from research import alt_proxies\n")
    assert _item(tmp_path)["state"] == "WIRED"


def test_runtime_rungs_follow_the_artifact(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    ap = "desks/mt5/reports/ALT_PROXIES.json"
    _w(tmp_path, ap, {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 0}],
                      "gain_tests": {}})
    assert _item(tmp_path)["state"] == "RUNNING"
    _w(tmp_path, ap, {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}],
                      "gain_tests": {}})
    assert _item(tmp_path)["state"] == "PRODUCING_DATA"
    _w(tmp_path, ap, {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}],
                      "gain_tests": {"cn_nbs_retail|retail_yoy|USDCNH": {"verdict": UNM}}})
    it = _item(tmp_path)
    assert it["state"] == "PRODUCING_CELLS" and it["cells_emitted"] == 1
    _w(tmp_path, ap, {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}],
                      "gain_tests": {"cn_nbs_retail|retail_yoy|USDCNH": {"verdict": "PASS"},
                                     "cn_nbs_retail|retail_yoy|AUDUSD": {"verdict": "FAIL"},
                                     "other|x|EURUSD": {"verdict": "PASS"}}})
    it = _item(tmp_path)
    assert it["state"] == "JUDGED"
    assert (it["cells_emitted"], it["cells_judged"], it["survivors"]) == (2, 2, 1)


UNM = "UNMEASURED"


def test_a_keyless_source_is_blocked_not_running(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row(key_env=["FIRMS_MAP_KEY"])])
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "BLOCKED_ON_KEY:FIRMS_MAP_KEY",
                     "store_rows": 0}]})
    it = _item(tmp_path)
    assert it["state"] == "BLOCKED" and "BLOCKED_ON_KEY" in it["blocker"]
    assert it["blocker_measured"] is True
    assert set(it["keys_present"]) == {"FIRMS_MAP_KEY"}


def test_a_failed_xliv_verification_holds_the_row_at_running(tmp_path: Path) -> None:
    """'SGE must maintain actual daily history, not one day': one row is not history."""
    _tree(tmp_path)
    _reqs(tmp_path, [_row(verify={"kind": "min_rows", "min_rows": 20, "why": "not one day"})])
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 1}],
        "gain_tests": {"cn_nbs_retail|a|USDCNH": {"verdict": "PASS"}}})
    it = _item(tmp_path)
    assert it["state"] == "RUNNING"
    assert it["verify"]["ok"] is False and it["verify"]["have_rows"] == 1


def test_pack_chain_counts_and_a_proxy_flag(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row(proxy=True, probes=[{"kind": "pack_cells",
                                               "artifact": "desks/mt5/reports/PACK_CELLS.json",
                                               "ids": ["hkma_open_api"]}])])
    _w(tmp_path, "desks/mt5/reports/PACK_CELLS.json",
       {"rows": [{"id": "hkma_open_api", "stage": "cells_judged", "n_rows": 300,
                  "cells_emitted": 12, "cells_judged": 4}]})
    it = _item(tmp_path)
    assert it["state"] == "JUDGED" and it["proxy"] is True
    assert it["observations"] == 300 and it["cells_judged"] == 4


# ------------------------------------------------------------------------------- the proofs
def _evig_row() -> dict[str, Any]:
    return _row(id="R44", scheduler=["hourly:alt_proxies"],
                probes=[{"kind": "proof", "proof": "evig_order",
                         "artifact": "desks/mt5/data/evig_order_decisions.jsonl"}])


def test_evig_is_proven_only_when_it_changed_what_was_fetched(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_evig_row()])
    at = (NOW - timedelta(minutes=30)).isoformat()
    _jl(tmp_path, "desks/mt5/data/evig_order_decisions.jsonl",
        [{"at": at, "moved": 3, "before": ["a", "b", "c", "d"], "after": ["d", "c", "a", "b"]}])
    coll = {"generated_utc": (NOW - timedelta(minutes=20)).isoformat(),
            "rows": [{"id": "d", "status": "COLLECTED"}, {"id": "c", "status": "COLLECTED"},
                     {"id": "a", "status": "DEFERRED"}, {"id": "b", "status": "DEFERRED"}]}
    _w(tmp_path, CAD.COLLECTOR_REL, coll)
    it = _item(tmp_path)
    proof = it["proofs"][0]
    assert proof["verdict"] == "PROVEN"
    assert proof["measures"]["fetched_because_of_evig"] == ["c", "d"]
    assert proof["measures"]["deferred_because_of_evig"] == ["a", "b"]
    assert it["state"] == "PROVEN"
    # the budget never bound: positions moved, no fetch differed
    coll["rows"] = [{"id": i, "status": "COLLECTED"} for i in ("d", "c", "a", "b")]
    _w(tmp_path, CAD.COLLECTOR_REL, coll)
    it = _item(tmp_path)
    assert it["proofs"][0]["verdict"] == "NOT_PROVEN" and it["state"] != "PROVEN"


def test_evig_proof_without_decisions_is_unmeasured(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_evig_row()])
    assert _item(tmp_path)["state"] == "UNMEASURED"


def test_roi_is_proven_on_an_adequate_sample_the_forest_ran_on(tmp_path: Path) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row(id="R43", scheduler=["hourly:research_roi"],
                          probes=[{"kind": "proof", "proof": "roi_budget",
                                   "artifact": "desks/mt5/data/roi_budget_decisions.jsonl"}])])
    at = (NOW - timedelta(hours=2)).isoformat()
    moved = {"roi": 0.4, "trials": 80, "flat": {"workers": 4, "budget_s": 3000},
             "roi_only": {"workers": 6, "budget_s": 4500},
             "after": {"workers": 6, "budget_s": 4500}, "before": {"workers": 4, "budget_s": 3000}}
    thin = dict(moved, trials=3)
    _jl(tmp_path, "desks/mt5/data/roi_budget_decisions.jsonl",
        [{"at": at, "forests": {"china": moved, "korea": thin}}])
    _jl(tmp_path, CAD.FOREST_RUNS_REL,
        [{"at": (NOW - timedelta(hours=1)).isoformat(), "forest": "china",
          "allocation": {"workers": 6, "budget_s": 4500}}])
    proof = _item(tmp_path)["proofs"][0]
    assert proof["verdict"] == "PROVEN"
    assert proof["measures"]["forests_moved_with_adequate_sample"] == ["china"]
    # only the undersampled forest moved: not proven
    _jl(tmp_path, "desks/mt5/data/roi_budget_decisions.jsonl",
        [{"at": at, "forests": {"korea": thin}}])
    assert _item(tmp_path)["proofs"][0]["verdict"] == "NOT_PROVEN"


def test_rotation_needs_native_languages_and_moving_ground(tmp_path: Path) -> None:
    _tree(tmp_path)
    rot = "desks/mt5/data/deep_forest_rotation.jsonl"
    _reqs(tmp_path, [_row(id="R45", probes=[{"kind": "proof", "proof": "forest_rotation",
                                             "artifact": rot}])])
    t1, t2 = (NOW - timedelta(hours=3)).isoformat(), (NOW - timedelta(hours=1)).isoformat()
    _jl(tmp_path, "desks/mt5/data/deep_forest_rotation.jsonl", [
        {"at": t1, "attempts_by_language": {"en": 2, "zh": 2, "ja": 1, "ko": 1},
         "grounds": ["g1", "g2", "g3", "g4", "g5", "g6"]},
        {"at": t2, "attempts_by_language": {"en": 2, "zh": 1, "vi": 1, "ko": 1},
         "grounds": ["g7", "g8", "g9", "g10", "g11"]}])
    proof = _item(tmp_path)["proofs"][0]
    assert proof["verdict"] == "PROVEN", proof
    _jl(tmp_path, "desks/mt5/data/deep_forest_rotation.jsonl", [
        {"at": t1, "attempts_by_language": {"en": 9, "zh": 1}, "grounds": ["g1", "g2"]},
        {"at": t2, "attempts_by_language": {"en": 9, "zh": 1}, "grounds": ["g1", "g2"]}])
    proof = _item(tmp_path)["proofs"][0]
    assert proof["verdict"] == "NOT_PROVEN"
    assert "non-English share" in proof["why"] and "not rotating" in proof["why"]


def test_write_and_fence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                         capsys: pytest.CaptureFixture[str]) -> None:
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    doc = CAD.audit(tmp_path, NOW)
    out = CAD.write(doc, tmp_path)
    back = json.loads(out.read_text("utf-8"))
    assert back["census"]["UNMEASURED"] == 1 and back["summary"]
    monkeypatch.setattr(CAD, "ROOT", tmp_path)
    assert CAD.main(["--fence"]) == 0
    assert "ASIA DIRECTIVE COMPLETION AUDIT" in capsys.readouterr().out
    _w(tmp_path, CAD.REQS_REL, {"ladder": ["ABSENT"], "requirements": [{"id": "X"}]})
    assert CAD.main(["--fence"]) == 1


# --------------------------------------------------- the organs that write the decision records
def test_fetch_order_records_its_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import source_evig as se
    out = tmp_path / "SOURCE_EVIG.json"
    rows = [{"id": "c", "rank": 0}, {"id": "a", "rank": 1}]
    out.write_text(json.dumps({"at": "x", "rows": rows}), encoding="utf-8")
    monkeypatch.setattr(se, "OUT", out)
    monkeypatch.setattr(se, "DECISIONS", tmp_path / "evig_order_decisions.jsonl")
    assert se.fetch_order(["a", "b", "c"]) == ["c", "a", "b"]
    assert not (tmp_path / "evig_order_decisions.jsonl").exists(), "record is opt-in"
    se.fetch_order(["a", "b", "c"], record=True)
    rec = json.loads((tmp_path / "evig_order_decisions.jsonl").read_text("utf-8").splitlines()[0])
    assert rec["before"] == ["a", "b", "c"] and rec["after"] == ["c", "a", "b"]
    assert rec["moved"] == 3 and rec["evig_at"] == "x"


def test_an_unranked_order_records_nothing(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from research import source_evig as se
    monkeypatch.setattr(se, "OUT", tmp_path / "absent.json")
    monkeypatch.setattr(se, "DECISIONS", tmp_path / "evig_order_decisions.jsonl")
    assert se.fetch_order(["a", "b"], record=True) == ["a", "b"]
    assert not (tmp_path / "evig_order_decisions.jsonl").exists()


def test_roi_decision_ledger_follows_the_allocation_file(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from research import research_roi as rr
    monkeypatch.setattr(rr, "FOREST_OUT", tmp_path / "forest_allocation.json")
    assert rr.budget_decisions_path() == tmp_path / "roi_budget_decisions.jsonl"
    rr._append_budget_decision({"at": "t", "forests": {}})
    assert (tmp_path / "roi_budget_decisions.jsonl").read_text("utf-8").count("\n") == 1


def test_evig_terms_parsing_relevance_and_licence() -> None:
    from research import source_evig as se
    src = [{"id": "parsed", "targets": ["XAUUSD"], "cadence": "daily"},
           {"id": "unparsed", "targets": ["XAUUSD"], "cadence": "daily"},
           {"id": "offuniverse", "targets": ["CNYBOND"], "cadence": "daily"},
           {"id": "priced", "targets": ["XAUUSD"], "cadence": "daily", "access": "paid",
            "licence_cost_s": 100.0}]
    chain = {"parsed": {"collected": True, "stage_reached": "represented"},
             "unparsed": {"collected": True, "stage_reached": "collected"}}
    rows = {r["id"]: r for r in se.price(src, {}, {}, universe={"XAUUSD"}, chain=chain)}
    assert rows["parsed"]["p_parsed"] > rows["unparsed"]["p_parsed"]
    assert rows["parsed"]["evig"] > rows["unparsed"]["evig"]
    assert rows["offuniverse"]["mt5_relevance"] == 0.05
    assert rows["priced"]["licence_status"] == "DECLARED" and rows["priced"]["cost_s"] > 100
    off = {r["id"]: r for r in se.price(src, {}, {})}
    assert off["parsed"]["parse_status"] == "UNMEASURED" and off["parsed"]["p_parsed"] == 1.0


def test_roi_budget_decision_names_the_budget_roi_moved() -> None:
    from research import research_roi as rr
    by = {r: {"roi": None, "roi_status": "UNMEASURED", "trials": 0} for r in rr.REGIONS}
    by["china"] = {"roi": 2.0, "roi_status": "MEASURED", "trials": 50}
    by["korea"] = {"roi": 0.5, "roi_status": "MEASURED", "trials": 50}
    regions = {"by_region": by}
    roi_only = rr.forest_allocation(regions)
    rec = rr.budget_decision(regions, roi_only, roi_only, None)
    assert "china" in rec["moved_by_roi"] and "korea" in rec["moved_by_roi"]
    assert "japan" not in rec["moved_by_roi"], "an unpriced region keeps the flat default"
    assert rec["forests"]["china"]["trials"] == 50 and rec["forests"]["china"]["before"] is None


def test_deep_forest_rotation_record_counts_attempts_not_skips() -> None:
    from research import deep_forest_miner as dfm
    status = [{"ground": "a", "language": "zh", "status": "PRODUCTIVE"},
              {"ground": "b", "language": "ja", "status": "REACHED_NO_CLAIMS"},
              {"ground": "c", "language": "en", "status": "BUDGET_EXHAUSTED"},
              {"ground": "d", "language": "ko", "status": "BLOCKED"}]
    rec = dfm.rotation_record({"generated_utc": "t", "cursor_next": 7}, status,
                              [{"language": "zh"}, {"language": "en"}])
    assert rec["attempts_by_language"] == {"ja": 1, "ko": 1, "zh": 1}
    assert rec["grounds"] == ["a", "b", "d"] and rec["n_scheduled"] == 2
    assert rec["scheduled_by_language"] == {"en": 1, "zh": 1}


# ------------------------------------------------------------- the consumer: the dashboard
def test_dashboard_reads_the_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import desk_dashboard_state as DDS
    monkeypatch.setattr(DDS, "ROOT", tmp_path)
    sec = DDS._asia_intelligence()
    assert sec["status"] == "MISSING" and sec["census"]["value"] is None
    assert all(r["observations"] == "UNMEASURED" for r in sec["regions"])
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}]})
    CAD.write(CAD.audit(tmp_path, NOW), tmp_path)
    _w(tmp_path, "desks/mt5/data/axes/latent_cn_industrial.json",
       {"rows": [{"as_of": "2026-10-01", "level": 0.4, "surprise": -1.2, "acceleration": 0.1,
                  "uncertainty": 0.3, "contributions": {"pmi": 0.2}}]})
    sec = DDS._asia_intelligence()
    assert sec["status"] == "MEASURED"
    assert sec["census"]["value"]["PRODUCING_DATA"] == 1
    china = next(r for r in sec["regions"] if r["region"] == "China")
    assert china["observations"] == 40
    assert china["certificates"] == "UNMEASURED"
    ind = next(x for x in sec["latent_states"] if x["state"] == "industrial state")
    assert ind["surprise"]["value"] == -1.2
    fx = next(x for x in sec["latent_states"] if x["state"] == "FX-flow state")
    assert fx["level"]["status"] == "MISSING"
