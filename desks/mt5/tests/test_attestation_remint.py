"""An attestation change is re-JUDGED at the front of the next sweep, never re-stamped.

MEASURED 2026-09-30: sealed pass 1 changed gate_policy.ATTESTATION (lockbox v4). Both certificate
stores carried `...-v2-calibrated-inputs`, `authorized_runs()` returned 0 of 58, and the sealed
writer's only way out was to merge the old rows and stamp the new attestation over them.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.gate_policy import ATTESTATION, GATES  # noqa: E402

from research import attestation_remint as ar  # noqa: E402
from research import canon_publication as cp  # noqa: E402

T0 = datetime(2026, 9, 30, 12, 50, 41, tzinfo=UTC)          # the v4 commit
OLD = "2026-09-16T15:07:12+00:00"
NEW = "2026-09-30T15:00:00+00:00"
STALE_POLICY = {**ATTESTATION, "version": "mt5-original-universal-10-v2-calibrated-inputs",
                "lockbox_basis": "the v2 basis"}


def _gates() -> dict:
    return {g: {"passed": True} for g in GATES}


def _row(sym: str, gated_at: str, params: dict | None = None) -> dict:
    params = {"lookback": 20} if params is None else params
    from research.frontier_identity import cell_id
    return {"cell": cell_id({"sym": sym, "family": "carry", "params": params}), "sym": sym,
            "gates": _gates(), "gated_at": gated_at,
            "shadow_spec": {"symbol": sym, "family": "carry", "selector": "continuous",
                            "params": params}}


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "external_gauntlet.py").write_text("# unpatched\n", "utf-8")
    for name, rel in (("REPORT", "reports/UNIVERSAL_SURVIVORS.json"),
                      ("CANON", "data/UNIVERSAL_SURVIVORS.canon.json"),
                      ("DOCKET", "data/hypotheses/external_survivors.json"),
                      ("PRIORITY", "data/hypotheses/priority_remint.json"),
                      ("STATUS", "reports/REMINT_STATUS.json"),
                      ("JUDGING_RATE", "reports/JUDGING_RATE.json"),
                      ("GAUNTLET_ORDER", "reports/GAUNTLET_ORDER.json"),
                      ("GATES_OUTPUT", "reports/universal_gates_external.json"),
                      ("GAUNTLET_SRC", "scripts/external_gauntlet.py")):
        monkeypatch.setattr(ar, name, tmp_path / rel)
    monkeypatch.setattr(ar, "_authorized_runs", lambda: {"status": "MEASURED", "n": 0})
    (tmp_path / "data" / "hypotheses" / "external_survivors.json").write_text(
        json.dumps([{"symbol": "EURUSD", "family": "carry", "params": {}}], indent=1), "utf-8")
    return tmp_path


def _write(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), "utf-8")


def _stores(desk: Path, policy: dict, rows: dict) -> None:
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json",
           {"n": len(rows), "gate_policy": policy, "survivors": rows, "swept_at": OLD})
    _write(desk / "data" / "UNIVERSAL_SURVIVORS.canon.json",
           {"n": len(rows), "gate_policy": policy, "survivors": rows, "swept_at": OLD})


def test_the_measured_freeze_is_reported_and_every_certificate_queued(desk: Path) -> None:
    rows = {"external.A": _row("AUDUSD", OLD), "external.B": _row("NZDUSD", OLD),
            "external.NOPARAMS": {**_row("USDJPY", OLD), "shadow_spec": {
                "symbol": "USDJPY", "family": "carry", "params": None}},
            "scalp.X": {**_row("XAUUSD", OLD)}}
    _stores(desk, STALE_POLICY, rows)
    doc = ar.build(T0 + timedelta(hours=2), previous={}, git_time=T0, patched=False)

    assert doc["enrolment_frozen"] is True
    assert doc["match"] == {"report": False, "canon": False, "any": False}
    assert doc["report"]["version"] == STALE_POLICY["version"]
    assert "lockbox_basis" in doc["report"]["differs_in"]
    assert doc["certificates_pending_rejudge"] == 4
    assert {x["key"] for x in doc["_targets"]} == {"external.A", "external.B"}
    assert {x["key"] for x in doc["not_queueable"]} == {"external.NOPARAMS", "scalp.X"}
    assert doc["frozen_at"] == T0.isoformat(timespec="seconds")
    assert doc["oldest_pending_age_hours"] == 2.0
    assert doc["eta"]["status"] == "AWAITING_SEALED_PATCH"
    assert doc["breach"] is False                     # no sweep has completed since the freeze


def test_apply_appends_in_place_once_and_the_cells_are_stamped(desk: Path) -> None:
    _stores(desk, STALE_POLICY, {"external.A": _row("AUDUSD", OLD)})
    doc = ar.build(T0 + timedelta(hours=1), previous={}, git_time=T0, patched=False)
    first = ar.apply(doc, T0 + timedelta(hours=1))
    second = ar.apply(doc, T0 + timedelta(hours=2))

    assert first["queued"] == 1 and second == {**second, "queued": 0, "already_on_docket": 1}
    docket = json.loads((desk / "data" / "hypotheses" / "external_survivors.json").read_text())
    assert len(docket) == 2 and docket[0]["symbol"] == "EURUSD"      # nothing rewritten
    row = docket[1]
    assert row["params"] == {"lookback": 20} and row["mechanism_status"] == "NAMED"
    from libs.data.pit import is_stamped
    assert is_stamped(row)
    prio = json.loads((desk / "data" / "hypotheses" / "priority_remint.json").read_text())
    assert prio["attestation"] == ATTESTATION
    assert prio["cells"] == [doc["_targets"][0]["cell_id"]]


def test_a_restamped_row_is_a_breach_the_moment_it_appears(desk: Path) -> None:
    """The unpatched writer's failure: current header, evidence from before it."""
    _stores(desk, dict(ATTESTATION), {"external.A": _row("AUDUSD", OLD),
                                      "external.FRESH": _row("EURUSD", NEW)})
    doc = ar.build(T0 + timedelta(hours=3), previous={}, git_time=T0, patched=False)
    assert doc["enrolment_frozen"] is False
    assert doc["restamped_not_rejudged"] == ["external.A"]
    assert doc["breach"] is True and "re-stamped" in doc["breach_why"][0]
    assert [x["key"] for x in doc["_targets"]] == ["external.A"]


def test_frozen_past_one_completed_sweep_is_a_breach(desk: Path) -> None:
    _stores(desk, STALE_POLICY, {"external.A": _row("AUDUSD", OLD)})
    started = T0 + timedelta(minutes=30)
    _write(desk / "reports" / "GAUNTLET_ORDER.json", {"at": started.isoformat()})
    gates = desk / "reports" / "universal_gates_external.json"
    gates.write_text("{}", "utf-8")
    import os
    os.utime(gates, (started.timestamp() - 60, started.timestamp() - 60))   # still running
    doc = ar.build(T0 + timedelta(hours=1), previous={}, git_time=T0, patched=True)
    assert doc["first_sweep_started_after_freeze"] and doc["breach"] is False

    os.utime(gates, (started.timestamp() + 600, started.timestamp() + 600))  # that sweep done
    doc = ar.build(T0 + timedelta(hours=2), previous=dict(doc),
                   patched=True)
    assert doc["breach"] is True
    assert "still frozen after the sweep" in doc["breach_why"][0]


def test_the_re_mint_is_timed_and_ends_the_freeze(desk: Path) -> None:
    _stores(desk, STALE_POLICY, {"external.A": _row("AUDUSD", OLD)})
    frozen = ar.build(T0 + timedelta(hours=1), previous={}, git_time=T0, patched=True)
    _stores(desk, dict(ATTESTATION), {"external.A": _row("AUDUSD", NEW)})
    done = ar.build(T0 + timedelta(hours=3), previous=frozen, patched=True)
    assert done["enrolment_frozen"] is False and done["certificates_pending_rejudge"] == 0
    assert done["reminted_at"] == (T0 + timedelta(hours=3)).isoformat(timespec="seconds")
    assert done["frozen_hours"] == 3.0 and done["breach"] is False


def test_eta_comes_from_the_measured_judge_rate(desk: Path) -> None:
    _stores(desk, STALE_POLICY, {"external.A": _row("AUDUSD", OLD),
                                 "external.B": _row("NZDUSD", OLD)})
    _write(desk / "reports" / "JUDGING_RATE.json", {"at": NEW, "verdicts_per_hour": 400.0})
    doc = ar.build(T0 + timedelta(hours=1), previous={}, git_time=T0, patched=True)
    assert doc["eta"]["status"] == "FRONT_OF_DOCKET" and doc["eta"]["hours"] == 0.01
    (desk / "reports" / "JUDGING_RATE.json").unlink()
    doc = ar.build(T0 + timedelta(hours=1), previous={}, git_time=T0, patched=True)
    assert doc["eta"]["status"] == "UNMEASURED" and doc["eta"]["hours"] is None


def test_a_trial_basis_only_change_does_not_restart_the_clock() -> None:
    """is_exact_policy accepts a superseded HARDER trial charge; so does the dating."""
    assert ar.fingerprint(ATTESTATION) == ar.fingerprint(
        {**ATTESTATION, "trial_count_basis": "something older"})
    assert ar.fingerprint(ATTESTATION) != ar.fingerprint(STALE_POLICY)


def test_check_mode_exits_one_on_a_recorded_breach(tmp_path: Path) -> None:
    status = tmp_path / "s.json"
    status.write_text(json.dumps({"breach": True, "breach_why": ["x"]}), "utf-8")
    assert ar.check(status) == 1
    status.write_text(json.dumps({"breach": False, "eta": {}}), "utf-8")
    assert ar.check(status) == 0
    assert ar.check(tmp_path / "absent.json") == 1                  # UNMEASURED is not clean


# ------------------------------------------------------------------------ the canon's half

def _canon_desk(tmp_path: Path, floor: datetime | None) -> tuple[Path, Path, Path]:
    (tmp_path / "reports").mkdir(exist_ok=True)
    (tmp_path / "data").mkdir(exist_ok=True)
    status = tmp_path / "reports" / "REMINT_STATUS.json"
    if floor is not None:
        status.write_text(json.dumps({"attestation_fingerprint": ar.fingerprint(ATTESTATION),
                                      "in_force_since": floor.isoformat()}), "utf-8")
    return tmp_path / "reports" / "u.json", tmp_path / "data" / "canon.json", status


def test_the_canon_parks_what_predates_the_attestation_and_seals_what_was_re_judged(
        tmp_path: Path) -> None:
    report, seal, _ = _canon_desk(tmp_path, T0)
    _write(report, {"n": 2, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.A": _row("AUDUSD", NEW),
                                  "external.RESTAMPED": _row("GBPUSD", OLD)}})
    _write(seal, {"n": 2, "gate_policy": STALE_POLICY, "swept_at": OLD,
                  "survivors": {"external.A": _row("AUDUSD", OLD),
                                "external.OLD": _row("EURUSD", OLD)}})

    rec = cp.publish(report, seal)

    doc = json.loads(seal.read_text("utf-8"))
    assert rec["status"] == "SEALED"
    assert set(doc["survivors"]) == {"external.A"}
    assert doc["survivors"]["external.A"]["gated_at"] == NEW
    assert set(doc["pending_rejudge"]) == {"external.OLD", "external.RESTAMPED"}
    assert doc["revocation"]["kind"] == "pending_rejudge_under_attestation_in_force"
    assert rec["refused_rows"]["predates_attestation"] == 1


def test_a_seal_of_another_attestation_is_parked_even_without_a_floor(tmp_path: Path) -> None:
    report, seal, _ = _canon_desk(tmp_path, None)
    _write(report, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.A": _row("AUDUSD", NEW)}})
    _write(seal, {"n": 1, "gate_policy": STALE_POLICY, "swept_at": OLD,
                  "survivors": {"external.OLD": _row("EURUSD", OLD)}})
    cp.publish(report, seal)
    doc = json.loads(seal.read_text("utf-8"))
    assert set(doc["survivors"]) == {"external.A"} and set(doc["pending_rejudge"]) == {
        "external.OLD"}


def test_a_parked_row_returns_when_re_judged(tmp_path: Path) -> None:
    report, seal, _ = _canon_desk(tmp_path, T0)
    _write(report, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.OLD": _row("EURUSD", NEW)}})
    _write(seal, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                  "survivors": {"external.B": _row("NZDUSD", NEW)},
                  "pending_rejudge": {"external.OLD": _row("EURUSD", OLD)}})
    cp.publish(report, seal)
    doc = json.loads(seal.read_text("utf-8"))
    assert set(doc["survivors"]) == {"external.B", "external.OLD"}
    assert "pending_rejudge" not in doc


def test_the_leg_runs_before_the_judge_on_the_core_clock() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["attestation_remint"] == "prediction"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"attestation_remint", "research/attestation_remint.py", "--apply"' in src
    assert src.index('_costed("attestation_remint"') < src.index('_costed("external_gauntlet"')
    assert '"attestation_remint": arm' in src
    from research import hourly_cycle as hc
    assert "attestation_remint" in hc.CORE_LEGS
    assert hc.LEG_BUDGET_SEC["attestation_remint"] >= 120


# ------------------------------------------------------------ the #126 audit's must-fixes

def test_an_undated_row_is_unmeasured_never_parked_or_queued(tmp_path: Path) -> None:
    """MF2: no gate date is absence of evidence, and absence never retires a certificate."""
    report, seal, _ = _canon_desk(tmp_path, T0)
    undated = _row("USDJPY", OLD)
    undated.pop("gated_at")
    _write(report, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.A": _row("AUDUSD", NEW)}})
    _write(seal, {"n": 2, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                  "survivors": {"external.A": _row("AUDUSD", NEW), "external.U": undated}})
    rec = cp.publish(report, seal)
    doc = json.loads(seal.read_text("utf-8"))
    assert "external.U" in doc["survivors"] and "pending_rejudge" not in doc
    assert rec["undated_unmeasured"] == ["external.U"]
    assert ar.stale_keys(doc, T0) == [] and ar.undated_keys(doc) == ["external.U"]


def test_no_git_date_gives_no_floor_never_now() -> None:
    """MF3: an attestation this organ cannot date dates no row stale."""
    since, basis = ar.in_force_since("fp", {}, T0, git_time=None)
    assert since is None and basis.startswith("UNMEASURED")
    assert ar.stale_keys({"survivors": {"k": _row("EURUSD", OLD)}}, None) == []


def test_no_floor_build_parks_and_queues_nothing_on_an_exact_store(desk: Path) -> None:
    _stores(desk, dict(ATTESTATION), {"external.A": _row("AUDUSD", OLD)})
    doc = ar.build(T0, previous={}, git_time=None, patched=True)
    assert doc["in_force_since"] is None
    assert doc["certificates_pending_rejudge"] == 0 and doc["restamped_not_rejudged"] == []
    assert doc["breach"] is False


def test_the_breach_exit_is_a_named_failure() -> None:
    """MF4: exit 3 is classified, never an anonymous exit_code."""
    from research import hourly_cycle as hc
    assert hc._exit_outcome("attestation_remint", ar.EXIT_BREACH) == "exit_code=3:REMINT_BREACH"
    assert ar.EXIT_BREACH not in hc.VERDICT_EXITS.get("attestation_remint", ())


def test_parking_publishes_a_two_sided_missed_growth_line(tmp_path: Path) -> None:
    """MF5 (Rule 1): a parking pass bills its cost and its gain; a pass that parks nothing bills
    nothing, which missed_growth reads as NOT_BINDING."""
    report, seal, _ = _canon_desk(tmp_path, T0)
    _write(report, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.A": _row("AUDUSD", NEW)}})
    _write(seal, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                  "survivors": {"external.OLD": _row("EURUSD", OLD)}})
    rec = cp.publish(report, seal)
    sides = sorted(x["side"] for x in rec["missed_growth"])
    assert sides == ["cost", "gain"]
    assert all(x["verdict"] == "UNMEASURED" and x["value"] is None for x in rec["missed_growth"])
    from research import missed_growth as mg
    out = tmp_path / "CANON_PUBLICATION.json"
    out.write_text(json.dumps(rec, default=str), "utf-8")
    assert mg.organ_published_lines(out)["verdict"] == "UNMEASURED"
    # MF2 (v2): the rail binds for as long as a row waits, not only on the pass that parked it.
    rec2 = cp.publish(report, seal)
    assert rec2["parked_this_pass"] == 0
    assert [x["withheld"] for x in rec2["missed_growth"]] == [1, 1]
    # Re-judged and re-admitted: nothing waits, so nothing is billed.
    _write(report, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.OLD": _row("EURUSD", NEW)}})
    rec3 = cp.publish(report, seal)
    assert rec3["pending_rejudge"] == 0 and rec3["missed_growth"] == []


def test_a_parked_row_that_fails_its_re_judge_leaves_the_park(tmp_path: Path) -> None:
    """MF1 (v2): a failed re-judge is a rejection, so the row stops waiting and its clock can
    retire through the normal path. A stale row under the current header is not a re-judge."""
    report, seal, _ = _canon_desk(tmp_path, T0)
    failed = _row("EURUSD", NEW)
    failed["gates"]["deflated_sharpe"] = {"passed": False}
    stale_fail = _row("USDCAD", OLD)
    stale_fail["gates"]["deflated_sharpe"] = {"passed": False}
    _write(report, {"n": 2, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                    "survivors": {"external.OLD": failed, "external.STALE": stale_fail}})
    _write(seal, {"n": 1, "gate_policy": dict(ATTESTATION), "swept_at": NEW,
                  "survivors": {"external.B": _row("NZDUSD", NEW)},
                  "pending_rejudge": {"external.OLD": _row("EURUSD", OLD),
                                      "external.STALE": _row("USDCAD", OLD)}})
    rec = cp.publish(report, seal)
    doc = json.loads(seal.read_text("utf-8"))
    assert rec["rejected_on_rejudge"] == ["external.OLD"]
    assert set(doc["pending_rejudge"]) == {"external.STALE"}
    assert "external.OLD" not in doc["survivors"]


def test_the_docket_append_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SF: a failure mid-append leaves the old docket whole."""
    docket = tmp_path / "d.json"
    docket.write_text(json.dumps([{"a": 1}], indent=1), "utf-8")
    before = docket.read_bytes()

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(ar.os, "replace", boom)
    res = ar.append_to_docket(docket, [{"b": 2}])
    assert res["appended"] == 0 and docket.read_bytes() == before
    assert not list(tmp_path.glob(".d.json.*"))
    monkeypatch.undo()
    assert ar.append_to_docket(docket, [{"b": 2}])["appended"] == 1
    assert json.loads(docket.read_text("utf-8")) == [{"a": 1}, {"b": 2}]
