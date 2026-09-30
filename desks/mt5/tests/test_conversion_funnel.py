"""The conversion funnel: every stage counted, every loss named, nothing absent read as zero."""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conversion_funnel as cf  # noqa: E402

from libs.moat import registry as R  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _row(cell: str, *, at: datetime, passed: bool = False, gate: str = "UNKNOWN",
         ds: str | None = None, family: str = "carry") -> dict:
    return {"at": at.isoformat(), "cell": cell, "sym": cell.split(".")[0], "family": family,
            "passed": passed, "terminal_gate": "PASSED" if passed else gate,
            "downstream_status": ds}


@pytest.fixture
def desk(tmp_path: Path) -> cf.Paths:
    paths = cf.Paths.at(tmp_path)
    old = NOW - timedelta(days=2)
    _ledger(paths.ledger, [
        _row("EURUSD.carry.p=a", at=old - timedelta(days=20), gate="cpcv"),
        _row("EURUSD.carry.p=a", at=old, passed=True),            # latest wins: PASS
        _row("GBPUSD.carry.p=b", at=old, passed=True),            # certified
        _row("USDJPY.carry.p=c", at=old, passed=True),            # retired
        _row("AUDUSD.carry.p=d", at=NOW, passed=True),            # after the last sweep
        _row("NZDUSD.discovered.p=e", at=old, passed=True, family="discovered"),
        _row("XAUUSD.carry.p=f", at=old, gate="deflated_sharpe"),
        _row("XAGUSD.carry.p=g", at=old, gate="economic_prior"),
        _row("USDCAD.carry.p=h", at=old, ds="NOT_RUN_BUILD_FAILED"),
        _row("USDCHF.carry.p=i", at=old, ds="NOT_RUN_DATA_MISSING"),
        _row("EURGBP.carry.p=j", at=old, ds="NOT_RUN_BUILD_BUDGET_DEFERRED"),
        _row("EURJPY.carry.p=k", at=old),                          # <60 observations
    ])
    paths.report.parent.mkdir(parents=True, exist_ok=True)
    paths.seal.parent.mkdir(parents=True, exist_ok=True)
    paths.report.write_text(json.dumps({
        "swept_at": (NOW - timedelta(days=1)).isoformat(),
        "survivors": {"external.GBPUSD.carry.p=b": {}}}), encoding="utf-8")
    paths.seal.write_text(json.dumps({
        "swept_at": (NOW - timedelta(days=1)).isoformat(),
        "survivors": {"external.GBPUSD.carry.p=b": {}},
        "retired_certificates": {"external.USDJPY.carry.p=c": {"reason": "x"}}}),
        encoding="utf-8")
    paths.enrolment.write_text(json.dumps({
        "at": NOW.isoformat(), "n_certificates": 1, "n_enrolled": 1, "n_missing": 0,
        "n_accruing": 0, "n_blocked": 1, "blocked_by_status": {"BLOCKED_NO_BARS": 1},
        "missing": []}), encoding="utf-8")
    return paths


def test_every_verdict_class_and_every_unknown_cause_is_named(desk) -> None:
    doc = cf.build(desk, None, budget_s=30, now=NOW, banned={"discovered"})
    v = doc["verdicts"]
    assert v["cells_judged"] == 11
    assert v["by_class"] == {"PASS": 5, "UNKNOWN": 4, "FAIL_AT_GATE": 1, "REFUSED_PRE_GATE": 1}
    assert v["by_subclass"]["UNKNOWN"] == {"BUILD_FAILED": 1, "DATA_MISSING": 1,
                                           "BUDGET_DEFERRED": 1, "NO_STATUS": 1}
    assert v["unknown_build_or_data"] == 2 and v["unknown_build_or_data_share"] == 0.5
    assert v["by_subclass"]["FAIL_AT_GATE"] == {"deflated_sharpe": 1}
    for cause in v["by_subclass"]["UNKNOWN"]:
        assert v["owners"][cause], f"{cause} must name the organ that owns it"


def test_the_latest_verdict_is_the_standing_one(desk) -> None:
    doc = cf.build(desk, None, budget_s=30, now=NOW, banned=set())
    assert doc["verdicts"]["by_subclass"]["PASS"]["PASSED"] == 5
    assert "cpcv" not in doc["verdicts"]["by_subclass"].get("FAIL_AT_GATE", {})


def test_every_pass_is_a_certificate_or_carries_a_named_reason(desk) -> None:
    c = cf.build(desk, None, budget_s=30, now=NOW, banned={"discovered"})["certificates"]
    assert c["passes"] == 5 and c["certified"] == 1
    assert c["lost"] == {"RETIRED_AFTER_CERTIFICATION": 1, "AWAITING_REPUBLICATION": 1,
                         "BANNED_FAMILY": 1, "UNEXPLAINED": 1}
    assert c["lost_samples"]["UNEXPLAINED"] == ["external.EURUSD.carry.p=a"]
    assert sum(c["lost"].values()) + c["certified"] == c["passes"], "no PASS goes uncounted"


def test_certificate_to_clock_names_what_is_not_accruing(desk) -> None:
    k = cf.build(desk, None, budget_s=30, now=NOW, banned=set())["clocks"]
    assert k["on_clock"] == 1 and k["accruing"] == 0
    assert k["lost"] == {"CLOCKLESS": 0, "NOT_ACCRUING": 1}
    assert k["not_accruing_by_status"] == {"BLOCKED_NO_BARS": 1}


def test_an_absent_input_is_unmeasured_never_zero(tmp_path) -> None:
    doc = cf.build(cf.Paths.at(tmp_path), None, budget_s=30, now=NOW, banned=set())
    assert doc["registry"]["status"] == cf.UNMEASURED
    assert doc["verdicts"]["status"] == cf.UNMEASURED
    assert doc["certificates"]["status"] == cf.UNMEASURED
    assert doc["clocks"]["status"] == cf.UNMEASURED
    assert doc["near_miss"]["status"] == cf.UNMEASURED


def test_a_stream_the_budget_cuts_is_published_partial(desk) -> None:
    out = cf.stream_ledger(desk.ledger, deadline=time.monotonic() - 1.0)
    assert out["partial"] is True
    assert out["rows"] == 0 and out["bytes_read"] < out["bytes_total"]


def test_the_registry_stage_counts_losses_before_a_cell(tmp_path) -> None:
    R.set_path(tmp_path / "reg.sqlite")
    try:
        conn = R.connect()
        for i, st in enumerate(("queued", "judged", "donated", "retired", "retired")):
            R.enqueue_candidate(family="carry", symbol="EURUSD", params={"i": i}, origin="T",
                                mechanism="m", status=st, candidate_id=f"c{i}", conn=conn)
        conn.execute("UPDATE research_candidates SET failure_class='OFF_UNIVERSE' "
                     "WHERE status='retired'")
        conn.commit()
        reg = cf.registry_stage(conn)
        conn.close()
    finally:
        R.set_path(None)
    assert reg["mined"] == 5 and reg["testable_cells"] == 2 and reg["awaiting_judge"] == 1
    assert reg["lost_before_cell"] == {"donated": 1, "retired": 2}
    assert reg["lost_before_cell_by_class"]["retired"] == {"OFF_UNIVERSE": 2}


def test_main_checkpoints_then_writes_the_artifact(desk, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(R, "connect", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    assert cf.main(["--once", "--budget-s", "30", "--desk", str(tmp_path)]) == 0
    doc = json.loads(desk.out.read_text(encoding="utf-8"))
    assert doc["pass_status"] == cf.STAGE_COMPLETE
    assert [s["stage"] for s in doc["funnel"]] == [
        "mined", "testable_cell", "judged", "verdict", "pass", "certificate", "forward_clock"]


def test_the_budget_never_outlives_the_cycle_cap() -> None:
    assert cf.effective_budget_s(240, {}) == 240
    assert cf.effective_budget_s(240, {"QUANT_LEG_BUDGET_S": "300"}) == 240
    assert cf.effective_budget_s(240, {"QUANT_LEG_BUDGET_S": "200"}) == 140


def test_the_leg_is_wired_on_the_hourly_clock() -> None:
    src = " ".join((_DESK / "research" / "hourly_cycle.py").read_text("utf-8").split())
    assert '"conversion_funnel", "research/conversion_funnel.py", "--once", "--budget-s"' in src
    from research import hourly_cycle as hc
    assert "conversion_funnel" in hc.LEG_BUDGET_SEC
    from libs.research.layers import LEG_LAYER
    assert "conversion_funnel" in LEG_LAYER
