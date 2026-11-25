"""The hourly pass on the box (principal 2026-11-25 03:11Z): board, I1-I8, prevention, diff,
hourly lens + red team, one PASS_FINDINGS.json -- read-only, local files, no LLM."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

import box_pass as bp

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)


def _root(tmp: Path, procs, *, invariants=None) -> Path:
    (tmp / "ops/pass").mkdir(parents=True)
    shutil.copy(REPO / bp.PREVENTION, tmp / bp.PREVENTION)
    for rel, doc in ((bp.BOARD, {"at": NOW.isoformat(), "processes": procs}),
                     (bp.SELF_HEAL, {"invariants": invariants or [], "repairs": []})):
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text(json.dumps(doc))
    return tmp


def _p(name, verdict, code=0, age=None, limit=None, why="w"):
    return {"name": name, "verdict": verdict, "last_result_code": code, "why": why,
            "artifact_age_min": age, "contract_max_age_min": limit, "last_run": "x"}


def test_findings_classify_diff_and_escalate(tmp_path):
    root = _root(tmp_path, [_p("MT5-Judge", "OK", age=5, limit=60),
                            _p("MT5-Dept-Macro", "UNCONTRACTED", code=2147946720),
                            _p("MT5-Disky", "FAILING", why="disk free_gb low"),
                            _p("MT5-CycleNoon", "DISABLED")],
                 invariants=[{"invariant": "I6", "holds": False, "detail": "97% used"},
                             {"invariant": "I3", "holds": True, "detail": "holds"}])
    d = bp.run(root, NOW)
    pub = json.loads((root / bp.OUT).read_text())
    assert pub["board"]["counts"] == {"LIVE": 1, "BROKEN": 2, "OFF_BY_DESIGN": 1}
    assert set(pub["board"]["new"]) == {"MT5-Dept-Macro", "MT5-Disky"}
    assert pub["invariants"]["I3"]["ok"] and not pub["invariants"]["I6"]["ok"]
    assert pub["invariants"]["I8"]["unmeasured"]                  # not reported yet: never OK
    rows = {r["name"]: r for r in bp.board_rows(root)}
    bp.classify(list(rows.values()), bp.load_prevention(root))
    assert rows["MT5-Dept-Macro"]["prevention"] == "TASK_REFUSED"
    assert rows["MT5-Disky"]["prevention"] in ("DISK_HEADROOM", "TASK_FAILING")
    assert d["ledger"]["state"] == "OFF_BOX" and len(d["redteam"]) == 3
    assert any("invariant I6" in n for n in d["needs_claude"])
    for k in range(1, 3):
        d = bp.run(root, NOW + timedelta(minutes=15 * k))
    assert set(d["board"]["escalate"]) == {"MT5-Dept-Macro", "MT5-Disky"}
    assert d["board"]["new"] == []


def test_lens_and_redteam_run_hourly_only_and_rotate(tmp_path):
    root = _root(tmp_path, [_p(f"MT5-T{i}", "OK", age=1, limit=60) for i in range(7)])
    first = bp.run(root, NOW)
    q = bp.run(root, NOW + timedelta(minutes=15))
    assert q["redteam"] == first["redteam"] and q["lens_at"] == first["lens_at"]
    nxt = bp.run(root, NOW + timedelta(minutes=60))
    seen = {f["component"] for f in first["redteam"]} | {f["component"] for f in nxt["redteam"]}
    assert len(seen) == 6                                         # least recently inspected first
    assert all(f["verdict"] == "PASS" for f in nxt["redteam"])
    assert first["lens"]["Q1_live_share"] == 1.0


def test_probes_catch_a_green_task_with_stale_output():
    r = {"name": "MT5-X", "status": "LIVE", "code": 0, "age_min": 500, "limit_min": 60,
         "owner": "Autonomy"}
    f = bp.probe(r)
    assert f["verdict"] == "FAIL" and "artifact_fresh" in f["finding"]


def test_an_empty_box_is_not_a_clean_pass(tmp_path):
    d = bp.run(tmp_path, NOW)
    assert d["measured"] is False and all(not v["ok"] for v in d["invariants"].values())
