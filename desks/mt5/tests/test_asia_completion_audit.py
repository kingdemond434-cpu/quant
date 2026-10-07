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
    """A tiny repo: one hourly leg that imports its owner module (so the owner is REACHED)."""
    _w(root, "desks/mt5/research/hourly_cycle.py",
       'import alt_proxies\n'
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
def test_the_requirement_file_is_the_project_audits_asia_rows() -> None:
    rd = CAD.Reader(_ROOT)
    rows, errors = CAD.load_requirements(rd)
    assert errors == []
    ids = [r["id"] for r in rows]
    # no parallel requirement list: the 1,944 ASIA-xxxx rows of the project completion audit
    assert len(ids) == 1944 and len(set(ids)) == 1944
    assert all(i.startswith(CAD.AUDIT_ID_PREFIX) for i in ids)
    assert all(r["audit_state"] in CAD.LADDER for r in rows)
    doc = rd.json(CAD.REQS_REL)
    keys = {o["key"] for o in doc["overlays"]}
    # the diff report's XLIV evidence specs are all attached as overlays: latent state,
    # dislocation lab, SGE, SHFE ranks, SHFE warehouse, SAFE, CFETS, ports, procurement,
    # Tianyancha, Copernicus/FIRMS, Baidu, JQuants/BOJ/KRX/HKMA, trader genome, EVIG, ROI, forest
    for k in ("R38", "R37", "R08", "R11", "R12", "R01", "R03", "R18", "R24", "R23", "R25",
              "R26", "R27", "R29", "R30", "R31", "R33", "R35", "R43", "R44", "R45", "R49", "R50"):
        assert k in keys, k
    used = {k for r in rows for k in r.get("overlays") or []}
    assert {"R43", "R44", "R45", "R49", "R50"} <= used
    by_id = {r["id"]: r for r in rows}
    # PART XXXVII's audit row and PART XXXIX's dashboard rows are lifted only by a code marker
    assert "R49" in by_id["ASIA-0931"]["overlays"] and not by_id["ASIA-0931"].get("hold_absent")
    assert "R50" in by_id["ASIA-0958"]["overlays"]


def _audit_row(**kw: Any) -> dict[str, Any]:
    base = {"id": "ASIA-0007", "source": "DIRECTIVE.md PART I A 3",
            "requirement": "Collect NBS retail sales for China with release history.",
            "state": "SCHEDULED", "owner_thread": "data",
            "module": ["desks/mt5/research/alt_proxies.py:12"],
            "scheduler": "hourly leg alt_proxies (L5174)",
            "input_artifacts": [], "output_artifacts": ["desks/mt5/reports/ALT_PROXIES.json",
                                                        "desks/mt5/data/lake/series/<source>.parquet"],
            "blocker": "", "next_repair": "", "evidence": "x"}
    base.update(kw)
    return base


def test_import_maps_an_audit_row_and_attaches_its_overlay() -> None:
    overlay = {"key": "R06", "match": r"retail sales", "match_parts": ["I"], "xliv": False,
               "region": "CN", "package": "P3", "report_row": 6,
               "owner": ["desks/mt5/research/pack_cells.py"], "scheduler": ["hourly:pack_cells"],
               "probes": [{"kind": "alt_proxies", "artifact": "desks/mt5/reports/ALT_PROXIES.json",
                           "ids": ["cn_nbs_retail"]}],
               "verify": {"kind": "min_rows", "min_rows": 12}}
    other = {"key": "R99", "match": r"retail sales", "match_parts": ["IX"], "probes": []}
    audit_doc = {"generated_at": "2026-10-06T00:00:00Z", "requirements": [
        _audit_row(), _audit_row(id="MT5-0001"),
        _audit_row(id="ASIA-0008", state="ABSENT", requirement="Build a JGB curve state.",
                   source="DIRECTIVE.md PART IX", scheduler="NONE", module=[]),
        _audit_row(id="ASIA-0009", requirement="Daily Korean flow", scheduler="MT5-Gauntlet task")]}
    hourly = 'a = _costed("alt_proxies", f)\nb = _costed("pack_cells", g)\n'
    doc = CAD.import_audit(audit_doc, {"ladder": list(CAD.LADDER), "overlays": [overlay, other]},
                           hourly)
    rows = {r["id"]: r for r in doc["requirements"]}
    assert set(rows) == {"ASIA-0007", "ASIA-0008", "ASIA-0009"}          # ASIA rows only
    r = rows["ASIA-0007"]
    assert r["audit_state"] == "SCHEDULED" and r["part"] == "I" and r["region"] == "CN"
    assert r["overlays"] == ["R06"]                                       # PART gates R99 out
    assert r["owner"] == ["desks/mt5/research/alt_proxies.py", "desks/mt5/research/pack_cells.py"]
    assert r["scheduler"] == ["hourly:alt_proxies", "hourly:pack_cells"]
    kinds = [(p["kind"], p["artifact"]) for p in r["probes"]]
    # the overlay's probe wins over the bare artifact probe; a templated path is not a probe
    assert kinds == [("alt_proxies", "desks/mt5/reports/ALT_PROXIES.json")]
    assert r["verify"]["min_rows"] == 12 and r["package"] == "P3"
    a = rows["ASIA-0008"]
    assert a["hold_absent"] and a["scheduler"] == [] and a["region"] == "JP"
    assert rows["ASIA-0009"]["scheduler"] == ["audit:MT5-Gauntlet task"]
    assert rows["ASIA-0009"]["region"] == "KR"
    assert doc["audit_source"]["rows"] == 3


def test_the_delta_against_the_audit(tmp_path: Path) -> None:
    _tree(tmp_path)
    _w(tmp_path, "desks/mt5/research/user.py", "import alt_proxies\n")
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "COLLECTED", "store_rows": 40}]})
    _reqs(tmp_path, [
        _row(id="ASIA-0001", audit_state="RUNNING"),                       # measured higher
        _row(id="ASIA-0002", audit_state="PRODUCING_DATA"),                # same
        _row(id="ASIA-0003", audit_state="SCHEDULED", hold_absent=True),   # held ABSENT: down
        _row(id="ASIA-0004", audit_state="LIVE", probes=[], scheduler=[]),  # code only: unconfirmed
        _row(id="ASIA-0005", audit_state="PROVEN", owner=[], probes=[], scheduler=[]),
        _row(id="ASIA-0006", audit_state="JUDGED",
             probes=[{"kind": "artifact", "artifact": "desks/mt5/reports/NOPE.json"}]),
    ])
    doc = CAD.audit(tmp_path, NOW)
    got = {i["id"]: (i["state"], i["delta"]) for i in doc["items"]}
    assert got["ASIA-0001"] == ("PRODUCING_DATA", "up")
    assert got["ASIA-0002"] == ("PRODUCING_DATA", "same")
    assert got["ASIA-0003"] == ("ABSENT", "down")
    assert got["ASIA-0004"] == ("WIRED", "unconfirmed")
    assert got["ASIA-0005"] == ("UNMEASURED", "unconfirmed")               # never ABSENT
    assert got["ASIA-0006"] == ("UNMEASURED", "unconfirmed")
    assert doc["delta_census"]["unconfirmed"] == 3
    assert doc["audit_census"]["PROVEN"] == 1
    assert any("against the project audit" in line for line in doc["summary"])


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


def test_wired_is_reachability_from_a_scheduler_not_any_importer(tmp_path: Path) -> None:
    """Item 3: an importer that no clock runs does not wire a module; a partial clock is not
    SCHEDULED; an audit-named clock is never taken on the audit's word."""
    _w(tmp_path, "desks/mt5/research/hourly_cycle.py", 'x = _costed("other_leg", f)\n')
    _w(tmp_path, "desks/mt5/research/alt_proxies.py", "PLACEBO = 1\n")
    _w(tmp_path, "desks/mt5/research/other.py", "from research import alt_proxies\n")
    _reqs(tmp_path, [_row(scheduler=["daily:book_forensics"])])
    it = _item(tmp_path)
    assert it["state"] == "CODED", it["why"]                  # imported, but by nothing on a clock
    assert "not reachable from any scheduler root" in " ".join(it["why"])
    # the importer becomes reachable from hourly_cycle: now the owner is WIRED, not SCHEDULED
    _w(tmp_path, "desks/mt5/research/hourly_cycle.py", 'import other\nx = _costed("o", f)\n')
    assert _item(tmp_path)["state"] == "WIRED"
    # a box task that runs the owner is a scheduler root too
    _w(tmp_path, "desks/mt5/research/hourly_cycle.py", 'x = _costed("o", f)\n')
    _w(tmp_path, CAD.BOX_TASKS_REL,
       'TASK name="MT5-Alt" trigger="hourly" runs="desks/mt5/research/alt_proxies.py"\n')
    assert _item(tmp_path)["static_rung"] == "WIRED"
    # a partial clock (one of two declared clocks confirmed) is WIRED, never SCHEDULED
    _w(tmp_path, "desks/mt5/research/hourly_cycle.py",
       'import alt_proxies\nx = _costed("alt_proxies", f)\n')
    _reqs(tmp_path, [_row(scheduler=["hourly:alt_proxies", "hourly:missing_leg"])])
    it = _item(tmp_path)
    assert it["static_rung"] == "WIRED" and "PARTIAL clock" in " ".join(it["why"])
    # an audit clock that names nothing this tree confirms is not a clock ...
    _reqs(tmp_path, [_row(scheduler=["audit:hourly_cycle legs / department residents"])])
    assert _item(tmp_path)["static_rung"] == "WIRED"
    # ... and one that names a box task the manifest holds is
    _reqs(tmp_path, [_row(scheduler=["audit:MT5-Alt task"])])
    assert _item(tmp_path)["static_rung"] == "SCHEDULED"


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
    # Item 2: the proof holds, but the row has no cells, judgements or forward/live
    # lineage of its own -- a proof never lifts a row past the rungs below it.
    assert it["state"] == "PRODUCING_DATA" and it["rungs_held"]["PROVEN"] is True
    assert "every lower rung must hold" in " ".join(it["why"])
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


# ------------------------------------------------------- PR #232 audit HOLD: no rung rounds up
CLAIMS = "desks/mt5/data/deep_forest_claims.jsonl"


def _lang_row(rid: str, lang: str, **kw: Any) -> dict[str, Any]:
    return _row(id=rid, region="GLOBAL", owner=["desks/mt5/research/alt_proxies.py"],
                title=f"Native-language practitioner-forest search in {lang}.",
                scheduler=["hourly:alt_proxies"],
                inputs=["desks/mt5/data/deep_forest_sources.json"],
                outputs=[CLAIMS], probes=[{"kind": "artifact", "artifact": CLAIMS}], **kw)


def test_a_shared_artifact_credits_each_requirement_only_its_own_rows(tmp_path: Path) -> None:
    """Item 1, the ASIA-1639 / ASIA-1643 case: one claims ledger, named by the German and the
    Dutch requirement, used to give BOTH its whole row count with zero de/nl rows in it."""
    _tree(tmp_path)
    _reqs(tmp_path, [_lang_row("ASIA-1639", "German"), _lang_row("ASIA-1643", "Dutch"),
                     _row(id="ASIA-1700", region="GLOBAL", title="Practitioner claims, any ground.",
                          probes=[{"kind": "artifact", "artifact": CLAIMS}])])
    _jl(tmp_path, CLAIMS, [{"language": "zh", "claim": "a"}, {"lang": "ja", "claim": "b"},
                           {"language": "en", "claim": "c"}])
    items = {i["id"]: i for i in CAD.audit(tmp_path, NOW)["items"]}
    for rid in ("ASIA-1639", "ASIA-1643"):
        assert items[rid]["state"] == "RUNNING", items[rid]       # ran; zero rows in its language
        assert items[rid]["observations"] == 0
        assert items[rid]["state"] != "PRODUCING_DATA"
    # a requirement no filter can be built for proves nothing from a shared artifact
    assert items["ASIA-1700"]["state"] == "UNMEASURED"
    _jl(tmp_path, CLAIMS, [{"language": "de", "claim": "a"}, {"language": "de-CH", "claim": "b"},
                           {"language": "zh", "claim": "c"}])
    items = {i["id"]: i for i in CAD.audit(tmp_path, NOW)["items"]}
    assert (items["ASIA-1639"]["state"], items["ASIA-1639"]["observations"]) == \
        ("PRODUCING_DATA", 2)
    assert items["ASIA-1643"]["state"] == "RUNNING"
    # rows carrying no language field cannot be attributed: UNMEASURED, never the whole count
    _jl(tmp_path, CLAIMS, [{"claim": "a"}, {"claim": "b"}])
    items = {i["id"]: i for i in CAD.audit(tmp_path, NOW)["items"]}
    assert items["ASIA-1639"]["state"] == "UNMEASURED"


def test_the_real_language_rows_filter_by_their_own_language() -> None:
    rows = {r["id"]: r for r in CAD.load_requirements(CAD.Reader(_ROOT))[0]}
    assert CAD.requirement_filter(rows["ASIA-1639"])["values"] == ["de"]
    assert CAD.requirement_filter(rows["ASIA-1643"])["values"] == ["nl"]
    claims = CAD.claimants_by_probe(list(rows.values()))
    key = CAD._probe_key({"kind": "artifact", "artifact": CLAIMS})
    assert {"row:ASIA-1639", "row:ASIA-1643"} <= claims[key]


def test_proven_needs_every_lower_rung(tmp_path: Path) -> None:
    """Item 2: data, cells, judgements and a PROVEN proof still stop at JUDGED while no
    per-requirement FORWARD / LIVE lineage is published."""
    _tree(tmp_path)
    _reqs(tmp_path, [_row(probes=[
        {"kind": "alt_proxies", "artifact": "desks/mt5/reports/ALT_PROXIES.json",
         "ids": ["cn_nbs_retail"]},
        {"kind": "proof", "proof": "evig_order",
         "artifact": "desks/mt5/data/evig_order_decisions.jsonl"}])])
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}],
        "gain_tests": {"cn_nbs_retail|a|USDCNH": {"verdict": "PASS"}}})
    _jl(tmp_path, "desks/mt5/data/evig_order_decisions.jsonl",
        [{"at": (NOW - timedelta(minutes=30)).isoformat(), "moved": 2,
          "before": ["a", "b"], "after": ["b", "a"]}])
    _w(tmp_path, CAD.COLLECTOR_REL, {"generated_utc": NOW.isoformat(),
                                     "rows": [{"id": "b", "status": "COLLECTED"},
                                              {"id": "a", "status": "DEFERRED"}]})
    it = _item(tmp_path)
    assert it["proofs"][0]["verdict"] == "PROVEN"
    assert it["state"] == "JUDGED" and it["rungs_held"]["FORWARD"] is False


def test_freshness_is_the_in_file_stamp_never_mtime(tmp_path: Path) -> None:
    """Item 4: a file touched a second ago with no stamp is UNMEASURED; an old generated_at is
    STALE however new the file's mtime."""
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    ap = "desks/mt5/reports/ALT_PROXIES.json"
    _w(tmp_path, ap, {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 4}]})
    it = _item(tmp_path)
    assert it["freshness"]["status"] == "UNMEASURED"
    assert it["last_successful_run"] == "UNMEASURED"
    _w(tmp_path, ap, {"generated_at": (NOW - timedelta(days=5)).isoformat(),
                      "sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 4}]})
    assert _item(tmp_path)["freshness"]["status"] == "STALE"
    _w(tmp_path, ap, {"generated_at": (NOW - timedelta(minutes=10)).isoformat(),
                      "sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 4}]})
    assert _item(tmp_path)["freshness"]["status"] == "FRESH"


def test_underpowered_is_emitted_not_judged(tmp_path: Path) -> None:
    """Item 6a."""
    _tree(tmp_path)
    _reqs(tmp_path, [_row()])
    _w(tmp_path, "desks/mt5/reports/ALT_PROXIES.json",
       {"sources": [{"id": "cn_nbs_retail", "status": "OK", "store_rows": 40}],
        "gain_tests": {"cn_nbs_retail|a|USDCNH": {"verdict": "UNDERPOWERED"},
                       "cn_nbs_retail|b|AUDUSD": {"verdict": "UNDERPOWERED"}}})
    it = _item(tmp_path)
    assert it["state"] == "PRODUCING_CELLS"
    assert (it["cells_emitted"], it["cells_judged"]) == (2, 0)


def test_an_input_artifact_is_not_evidence(tmp_path: Path) -> None:
    """Item 6b: the organ's INPUT existing says nothing about the organ having run."""
    _tree(tmp_path)
    src = "desks/mt5/data/deep_forest_sources.json"
    _w(tmp_path, src, [{"id": "g1", "language": "de"}])
    _reqs(tmp_path, [_row(inputs=[src], outputs=[],
                          probes=[{"kind": "artifact", "artifact": src}])])
    assert _item(tmp_path)["state"] == "UNMEASURED"
    audit_doc = {"requirements": [_audit_row(output_artifacts=[], input_artifacts=[src])]}
    doc = CAD.import_audit(audit_doc, {"ladder": list(CAD.LADDER), "overlays": []},
                           'a = _costed("alt_proxies", f)\n')
    assert doc["requirements"][0]["probes"] == []


def test_ledgers_rotate_whole_and_proofs_read_the_archives(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 5: past the bound a decision ledger moves whole to <stem>.<stamp>.jsonl; no row is
    discarded and a proof whose rows sit in the archive still reads them."""
    from libs.ops import ledger_rotation as lr
    from research import source_evig as se
    led = tmp_path / "desks/mt5/data/evig_order_decisions.jsonl"
    led.parent.mkdir(parents=True)
    monkeypatch.setattr(se, "DECISIONS", led)
    monkeypatch.setattr(se, "DECISIONS_ROTATE_BYTES", 200)
    recs = [{"at": (NOW - timedelta(minutes=30)).isoformat(), "moved": 2, "n": i,
             "before": ["a", "b"], "after": ["b", "a"]} for i in range(6)]
    for r in recs:
        se._record_decision(r)
    files = lr.ledger_files(led)
    assert len(lr.archives(led)) >= 1
    assert all(a.name.startswith("evig_order_decisions.2") for a in lr.archives(led))
    kept = [json.loads(line)["n"] for f in files for line in f.read_text("utf-8").splitlines()]
    assert kept == list(range(6)), "a rotation never discards a row"
    # everything in archives, nothing live: the proof still reads it
    if led.exists():
        lr.rotate_if_over(led, 0)
    assert not led.exists()
    _tree(tmp_path)
    _reqs(tmp_path, [_evig_row()])
    _w(tmp_path, CAD.COLLECTOR_REL, {"generated_utc": NOW.isoformat(),
                                     "rows": [{"id": "b", "status": "COLLECTED"},
                                              {"id": "a", "status": "DEFERRED"}]})
    proof = _item(tmp_path)["proofs"][0]
    assert proof["verdict"] == "PROVEN", proof
    assert proof["ledger_read"]["complete"] is True
    # the other two organs rotate the same way
    from research import deep_forest_miner as dfm
    from research import research_roi as rr
    assert dfm.ROTATION_ROTATE_BYTES == rr.BUDGET_DECISIONS_ROTATE_BYTES == 2 * 1024 * 1024
    monkeypatch.setattr(rr, "FOREST_OUT", tmp_path / "forest_allocation.json")
    monkeypatch.setattr(rr, "BUDGET_DECISIONS_ROTATE_BYTES", 10)
    rr._append_budget_decision({"at": "t1"})
    rr._append_budget_decision({"at": "t2"})
    bpath = rr.budget_decisions_path()
    got = [json.loads(line)["at"] for f in lr.ledger_files(bpath)
           for line in f.read_text("utf-8").splitlines()]
    assert got == ["t1", "t2"]


# ------------------------------------------------------------------- attribution by ground
GROUNDS_REG = {"grounds": [
    {"name": "七禾网 期货人物专访", "region": "cn", "language": "zh", "kind": "interview"},
    {"name": "聚宽 JoinQuant 社区", "region": "cn", "language": "zh", "kind": "community"},
    {"name": "雪球 港股", "region": "hk", "language": "zh", "kind": "social"}]}
ROT = "desks/mt5/data/deep_forest_rotation.jsonl"


def _ground_row(rid: str, ground: str, **kw: Any) -> dict[str, Any]:
    kw.setdefault("probes", [{"kind": "artifact", "artifact": CLAIMS}])
    return _row(id=rid, region="CN", title=f"Explore Chinese practitioner ground: {ground}.",
                **kw)


def test_a_ground_is_credited_only_with_its_own_rows(tmp_path: Path) -> None:
    """THE PR #232 HOLD: two grounds share a country, only one has claims, and only that one
    reaches PRODUCING_DATA. Country (or language) attribution used to credit both with every CN
    claim."""
    _tree(tmp_path)
    _w(tmp_path, CAD.FOREST_GROUNDS_REL, GROUNDS_REG)
    _reqs(tmp_path, [_ground_row("G1", "七禾网"), _ground_row("G2", "聚宽"),
                     _ground_row("G3", "defunct quant forums via Wayback")])
    _jl(tmp_path, CLAIMS, [
        {"ground": "七禾网 期货人物专访", "region": "cn", "language": "zh", "claim": "a"},
        {"ground": "七禾网 期货人物专访", "region": "cn", "language": "zh", "claim": "b"},
        {"ground": "雪球 港股", "region": "cn", "language": "zh", "claim": "c"}])
    items = {i["id"]: i for i in CAD.audit(tmp_path, NOW)["items"]}
    assert (items["G1"]["state"], items["G1"]["observations"]) == ("PRODUCING_DATA", 2)
    # same country, same language, zero rows of its own ground: below PRODUCING_DATA
    assert (items["G2"]["state"], items["G2"]["observations"]) == ("RUNNING", 0)
    # a ground the registry does not hold matches nothing
    assert (items["G3"]["state"], items["G3"]["observations"]) == ("RUNNING", 0)
    att = next(e for e in items["G2"]["evidence"] if e.get("attribution"))["attribution"]
    assert att["dimension"] == "ground" and att["values"] == ["聚宽 JoinQuant 社区"]
    # rows that carry no ground field are never credited: UNMEASURED
    _jl(tmp_path, CLAIMS, [{"region": "cn", "language": "zh", "claim": "a"}])
    items = {i["id"]: i for i in CAD.audit(tmp_path, NOW)["items"]}
    assert items["G1"]["state"] == "UNMEASURED" and items["G2"]["state"] == "UNMEASURED"


def test_a_ground_status_row_counts_its_claims_not_itself() -> None:
    flt = {"dimension": "ground", "values": ["a"], "basis": "t"}
    assert CAD._matches({"ground": "a", "claims": 0}, flt)
    assert not CAD._matches({"region": "cn"}, flt)


def test_the_real_ground_rows_resolve_to_their_own_grounds() -> None:
    rd = CAD.Reader(_ROOT)
    rows = {r["id"]: r for r in CAD.load_requirements(rd)[0]}
    reg = rd.json(CAD.FOREST_GROUNDS_REL)["grounds"]

    def vals(rid: str) -> list[str]:
        return CAD.requirement_filter(rows[rid], reg)["values"]
    assert vals("ASIA-0382") == ["七禾网 期货人物专访"]
    assert vals("ASIA-0396") == ["微信公众号 via 搜狗"]
    assert vals("ASIA-0391") == ["雪球"]                 # the CN ground, never HK's 雪球 港股
    assert vals("ASIA-0449") == ["Qiita systemtrade"]
    assert vals("ASIA-0456") == []                       # J-STAGE is not a registered ground
    assert CAD.requirement_filter(rows["ASIA-0382"])["dimension"] != "ground"  # no registry


def test_the_rotation_proof_is_per_ground(tmp_path: Path) -> None:
    _tree(tmp_path)
    _w(tmp_path, CAD.FOREST_GROUNDS_REL, GROUNDS_REG)
    proof = {"kind": "proof", "proof": "forest_rotation", "artifact": ROT}
    _reqs(tmp_path, [_ground_row("G1", "七禾网", probes=[proof]),
                     _ground_row("G2", "聚宽", probes=[proof]),
                     _ground_row("G3", "university repositories", probes=[proof])])
    t1, t2 = (NOW - timedelta(hours=3)).isoformat(), (NOW - timedelta(hours=1)).isoformat()
    _jl(tmp_path, ROT, [
        {"at": t1, "attempts_by_language": {"en": 2, "zh": 2, "ja": 1, "ko": 1},
         "grounds": ["七禾网 期货人物专访", "g2", "g3"]},
        {"at": t2, "attempts_by_language": {"en": 2, "zh": 1, "vi": 1, "ko": 1},
         "grounds": ["g4", "g5", "g6", "g7"]}])
    doc = CAD.audit(tmp_path, NOW)
    assert doc["proofs"]["forest_rotation"]["verdict"] == "PROVEN"     # the global loop moved
    items = {i["id"]: i for i in doc["items"]}
    assert items["G1"]["proofs"][0]["verdict"] == "PROVEN"
    assert items["G1"]["proofs"][0]["measures"]["runs_reaching_ground"] == 1
    assert items["G2"]["proofs"][0]["verdict"] == "NOT_PROVEN"       # never reached
    assert items["G3"]["proofs"][0]["verdict"] == "NOT_PROVEN"       # no registered ground
    # the decision ledger's rows are nobody's observations
    assert items["G1"]["observations"] == "UNMEASURED"


def test_row_count_reads_the_archives_after_a_rotation(tmp_path: Path) -> None:
    from libs.ops import ledger_rotation as lr
    rel = "desks/mt5/data/roi_budget_decisions.jsonl"
    _jl(tmp_path, rel, [{"at": "t1"}, {"at": "t2"}, {"at": "t3"}])
    rd = CAD.Reader(tmp_path)
    assert CAD._rows_in(rd, rel) == 3
    lr.rotate_if_over(tmp_path / rel, 0)
    assert not (tmp_path / rel).exists()
    assert CAD._rows_in(rd, rel) == 3, "the live file is gone; the archive still holds 3 rows"
    _jl(tmp_path, rel, [{"at": "t4"}])
    assert CAD._rows_in(rd, rel) == 4
    assert CAD._rows_in(rd, "desks/mt5/data/never_written.jsonl") is None


def test_free_stack_seat_cells_count_once(tmp_path: Path) -> None:
    """The proposer publishes ONE minted count for its seat; 60 rows naming free-stack sources
    each used to add it again (twice for a row with two sources)."""
    _tree(tmp_path)
    fs = "desks/mt5/reports/FREE_STACK_YIELD.json"

    def fsrow(rid: str, *ids: str) -> dict[str, Any]:
        return _row(id=rid, probes=[{"kind": "free_stack", "artifact": fs, "ids": [i]}
                                    for i in ids])
    _reqs(tmp_path, [fsrow("F1", "akshare", "shfe_daily"), fsrow("F2", "akshare"),
                     fsrow("F3", "shfe_daily")])
    _w(tmp_path, fs, {"per_source": {
        "akshare": {"status": "OK", "obs_total": 10, "columns": 2},
        "shfe_daily": {"status": "OK", "obs_total": 5, "columns": 1}}})
    _w(tmp_path, "desks/mt5/reports/FREE_STACK_PROPOSER.json",
       {"built_at": "2026-10-06T11:00:00Z", "minted": 40, "cursor_from": 0, "cursor_to": 40})
    doc = CAD.audit(tmp_path, NOW)
    items = {i["id"]: i for i in doc["items"]}
    assert items["F1"]["cells_emitted"] == 40           # two probes, one seat credit
    assert items["F2"]["cells_emitted"] == items["F3"]["cells_emitted"] == 40
    assert doc["by_region"]["CN"]["cells_emitted"] == 40  # three rows, one seat count
    assert items["F1"]["observations"] == 15


def test_rotated_ledger_archives_are_gitignored() -> None:
    """The three rotating ledgers' archives never reach a commit; the live ledgers are untouched."""
    import fnmatch

    from libs.ops import ledger_rotation as lr
    pats = [ln.strip() for ln in (_ROOT / ".gitignore").read_text("utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")]
    data = _ROOT / "desks/mt5/data"
    for stem in ("evig_order_decisions", "roi_budget_decisions", "deep_forest_rotation"):
        live = data / f"{stem}.jsonl"
        arch = lr.archive_path(live, NOW).relative_to(_ROOT).as_posix()
        assert any(fnmatch.fnmatchcase(arch, p) for p in pats), arch
        assert any(fnmatch.fnmatchcase(arch.replace(".jsonl", "_1.jsonl"), p) for p in pats)
        assert not any(fnmatch.fnmatchcase(live.relative_to(_ROOT).as_posix(), p)
                       for p in pats if "T[0-9]" in p)
