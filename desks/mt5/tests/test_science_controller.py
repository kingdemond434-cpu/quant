"""The science controller organ on a temporary registry: genomes and families are stamped,
the trial stream is priced at N_effective, an exhausted lineage's queued launches are BLOCKED
with the reason, a dry run writes nothing anywhere, and absent inputs read UNMEASURED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import science_controller as sc  # noqa: E402

from libs.moat import registry as R  # noqa: E402

EXHAUSTED_LAUNCHES = 60


def _enqueue(family: str, symbol: str, mechanism: str, i: int, **fields: str) -> str:
    cid, _ = R.enqueue_candidate(
        family=family, symbol=symbol, params={"lookback": 20 + i}, origin="DESK",
        mechanism=mechanism, asset_class="forex", chart="H1", session="all",
        horizon="sub_4h", regime="unconditional", information="price_only",
        transformation="compiled", pit_status="PIT_BAR_CLOSE", **fields)
    return cid


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    report = tmp_path / "universal_gates_external.json"
    out = tmp_path / "SCIENCE_CONTROLLER.json"
    monkeypatch.setattr(sc, "GATE_LEDGER", ledger)
    monkeypatch.setattr(sc, "GATES_REPORT", report)
    monkeypatch.setattr(sc, "OUT_REPORT", out)
    ids = {"clone": [_enqueue("clone_fam", "EURUSD", "trend_persistence", i) for i in range(4)],
           "healthy": [_enqueue("healthy_fam", "USDJPY", "carry_rollover", i) for i in range(2)]}
    rows = [{"at": f"2026-09-01T{i // 60:02d}:{i % 60:02d}:00+00:00",
             "cell": f"EURUSD.clone_fam.p={i}", "sym": "EURUSD", "family": "clone_fam",
             "passed": False, "terminal_gate": "in_sample_screen"}
            for i in range(EXHAUSTED_LAUNCHES)]
    rows += [{"at": "2026-09-02T00:00:00+00:00", "cell": "USDJPY.healthy_fam.p=1",
              "sym": "USDJPY", "family": "healthy_fam", "passed": True,
              "terminal_gate": "PASSED"},
             {"at": "2026-09-02T01:00:00+00:00", "cell": "USDJPY.healthy_fam.p=2",
              "sym": "USDJPY", "family": "healthy_fam", "passed": "False",
              "terminal_gate": "deflated_sharpe"}]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    report.write_text(json.dumps({"verdicts": [
        {"cell": "USDJPY.healthy_fam.p=1", "passed": True,
         "stages": {"deflated_sharpe": {"dsr": 0.999}}}]}), encoding="utf-8")
    assert len(ids["clone"]) == 4 and len(ids["healthy"]) == 2
    yield {"ledger": ledger, "report": report, "out": out}
    R.set_path(None)


def test_stamps_prices_and_blocks_an_exhausted_lineage(desk: dict[str, Path]) -> None:
    rep = sc.build(budget_s=30.0)
    fams = {r["families"][0]: r for r in rep["families"]["top"]}
    assert set(fams) == {"clone_fam", "healthy_fam"}
    clone, healthy = fams["clone_fam"], fams["healthy_fam"]
    assert clone["state"] == "EXHAUSTED" and clone["launches"] == EXHAUSTED_LAUNCHES
    assert clone["discoveries"] == 0 and clone["queued"] == 4 and clone["members"] == 4
    assert healthy["state"] == "OPEN" and healthy["passes_at_gate"] == 1
    assert healthy["dsr_measured"] == 1 and healthy["e_value"] == 10.0
    assert healthy["verdict"] == "UNDECIDED"
    stream = rep["trials"]["stream"]
    assert stream["raw"] == EXHAUSTED_LAUNCHES + 2 and stream["effective"] < 10.0
    assert rep["trials"]["queue"]["raw"] == 6 and rep["trials"]["queue"]["effective"] < 6
    assert rep["blocked"]["count"] == 4 and rep["blocked"]["families"] == 1
    assert all(b["family"] == "clone_fam" and "EXHAUSTED" in b["reason"]
               for b in rep["blocked"]["rows"])
    assert rep["wealth"]["exhausted"] == 1 and rep["wealth"]["blocked"] >= 1
    assert rep["archive"]["cells_filled"] == 2 and rep["archive"]["evidence_states"] == {
        "MEASURED_FAIL": 4, "CERTIFIED": 2}
    assert rep["inputs"]["cells_with_dsr"] == 1
    assert rep["inputs"]["gate_level_affordable_by_a_fresh_lineage"] is False
    assert rep["inputs"]["unmeasured"] == {"trials_ledger": "registry trials_ledger holds no "
                                                            "rows"}
    assert isinstance(rep["empty_high_value_cells"], list)
    assert len(rep["_stamps"]) == 6 and rep["stamped"]["written"] is False


def test_dry_run_writes_nothing_and_a_real_pass_stamps_the_registry(
        desk: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert sc.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not desk["out"].exists()
    conn = R.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM research_candidates WHERE family_id IS NOT "
                            "NULL").fetchone()[0] == 0
    finally:
        conn.close()
    assert sc.main(["--once", "--budget-s", "30"]) == 0
    out = capsys.readouterr().out
    assert "BLOCKED 4 queued launches in 1 families" in out
    doc = json.loads(desk["out"].read_text(encoding="utf-8"))
    assert doc["stamped"]["written"] is True and "_stamps" not in doc
    conn = R.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT family, family_id, science_state, genome_json FROM research_candidates")]
    finally:
        conn.close()
    assert all(r["family_id"] and r["genome_json"] for r in rows)
    assert {r["science_state"][:7] for r in rows if r["family"] == "clone_fam"} == {"BLOCKED"}
    assert {r["science_state"] for r in rows if r["family"] == "healthy_fam"} == {"OPEN"}
    g = json.loads(rows[0]["genome_json"])
    assert g["mechanism"] == "trend_persistence" and g["geography"] == "EU-US"
    assert len({r["family_id"] for r in rows}) == 2


def test_absent_inputs_are_unmeasured_not_zero(desk: dict[str, Path]) -> None:
    desk["ledger"].unlink()
    desk["report"].unlink()
    rep = sc.build(budget_s=30.0)
    note = rep["inputs"]["unmeasured"]
    assert note["gate_ledger"].startswith("absent") and note["gates_report"].startswith("absent")
    assert rep["inputs"]["gate_ledger_rows"] == 0 and rep["inputs"]["cells_with_dsr"] == 0
    assert rep["trials"]["stream"]["raw"] == 0 and rep["blocked"]["count"] == 0
    assert rep["families"]["count"] == 2 and rep["families"]["exhausted"] == 0
    assert all(r["verdict"] == "UNMEASURED" for r in rep["families"]["top"])



def test_campaign_continuation_is_anytime_valid_and_a_report_only(desk: dict[str, Path]) -> None:
    """Every family carries a continuation decision read off two Bernoulli mixture e-processes
    (discovery above the sealed level, futility below it). The clone family's sixty fails push
    the futility process and never the discovery one; the healthy family CONTINUES; the block
    is a report; and a decision, once reached, is the same whenever the stream is read."""
    rep = sc.build(budget_s=30.0)
    fams = {r["families"][0]: r for r in rep["families"]["top"]}
    clone, healthy = fams["clone_fam"]["continuation"], fams["healthy_fam"]["continuation"]
    assert clone["n"] == EXHAUSTED_LAUNCHES and clone["passes"] == 0
    assert clone["futility_e"] > 1.0 > clone["discovery_e"]
    assert clone["decision"] in (sc.CONTINUE, sc.STOP_FUTILE)
    assert clone["excess_pass_rate_cs"][0] < 0.0 and clone["wealth_state"] == "EXHAUSTED"
    assert healthy["decision"] == sc.CONTINUE and healthy["n"] == 2 and healthy["passes"] == 1
    camp = rep["campaigns"]
    assert sum(camp["decisions"].values()) == 2 and camp["judged_families"] == 2
    assert camp["decisions"][sc.STOP_DISCOVERED] == 0
    assert "never a brake" in camp["rule"] and "report" in camp["boundary"]
    level = float(rep["parameters"]["gate_level"])
    # futility: a long run of fails crosses 1/alpha; the crossing index is a stopping time and
    # the decision is fixed there, whatever arrives afterwards (optional stopping legal)
    fails = [False] * 400
    fut = sc.continuation_of(fails, level, 0.05)
    assert fut["decision"] == sc.STOP_FUTILE and fut["futility_max_e"] >= 20.0
    at = int(fut["decided_at"])
    assert sc.continuation_of(fails[:at], level, 0.05)["decision"] == sc.STOP_FUTILE
    assert sc.continuation_of(fails[:at - 1], level, 0.05)["decision"] == sc.CONTINUE
    later = sc.continuation_of(fails + [True] * 40, level, 0.05)
    assert later["decision"] == sc.STOP_FUTILE and later["decided_at"] == at
    # discovery: passes at many times the sealed level cross the other boundary
    won = sc.continuation_of([True] * 6, level, 0.05)
    assert won["decision"] == sc.STOP_DISCOVERED and won["discovery_e"] >= 20.0
    assert won["anytime_p_discovery"] <= 0.05
    # the Ville bound is a real bound: under the null, most fail-runs never cross by n=25
    assert sc.continuation_of([False] * 25, level, 0.05)["futility_e"] < 20.0
    empty = sc.continuation_of([], level, 0.05)
    assert empty["decision"] == sc.CONTINUE and empty["n"] == 0 and "UNMEASURED" in empty["why"]
