"""The carry re-judge queue holds every certificate in force until a REAL ten-gate verdict.

Audit PR269 (2026-10-07): the first version listed the carry keys as `stale_certificate_keys`.
A stale key leaves the survivor set on the first sweep -- taking the LIVE CHFNOK forward clock
with it (`clock_certificate.retire_unbacked`) -- and retires on ANY verdict carrying stages,
including an UNMEASURED "too short" one. These pin the repair: the keys are verdict-bound, the
judge's existing re-mint path never retires them, and (with the sealed `carry_pit` patch) only a
real, fully measured ten-gate FAIL can.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts"), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402
from research.gate_policy import ATTESTATION, GATES  # noqa: E402

_spec = importlib.util.spec_from_file_location("queue_carry_rejudge",
                                               DESK / "scripts" / "queue_carry_rejudge.py")
assert _spec and _spec.loader
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)

KEY = "external.CHFNOK.carry.p=98d776f3e210d3e2"
CELL = "CHFNOK.carry.p=98d776f3e210d3e2"
CUTOFF = "2026-10-08T00:00:00+00:00"
PATCHED = hasattr(eg, "verdict_bound_partition")
VERSION = str(ATTESTATION.get("version") or "")
NOW = "2026-10-09T00:00:00+00:00"


def _ten(passed: bool = True) -> dict:
    return {g: {"passed": passed} for g in GATES}


def _cert_row(gated: str = "2026-09-02T23:37:32+00:00") -> dict:
    return {"cell": CELL, "sym": "CHFNOK", "gated_at": gated, "days": 1120, "gates": _ten(),
            "shadow_spec": {"symbol": "CHFNOK", "selector": "asia", "family": "carry",
                            "params": {"input_symbol": "CHFNOK"}}}


def _files(tmp_path: Path, extra: dict | None = None) -> tuple[tuple[Path, ...], Path]:
    surv = tmp_path / "UNIVERSAL_SURVIVORS.json"
    rows = {KEY: _cert_row(),
            "external.CHFNOK.carry.p=new": {**_cert_row("2026-10-08T01:00:00+00:00"),
                                            "cell": "CHFNOK.carry.p=new"},
            "external.EURUSD.session_range_breakout.p=b": {
                "cell": "EURUSD.session_range_breakout.p=b",
                "gated_at": "2026-09-01T00:00:00+00:00",
                "shadow_spec": {"symbol": "EURUSD", "family": "session_range_breakout"}}}
    rows.update(extra or {})
    surv.write_text(json.dumps({"gate_policy": ATTESTATION, "survivors": rows}))
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "chfnok_carry_asia_p_98d776f3e210d3e2", "symbol": "CHFNOK", "family": "carry",
         "status": "LIVE", "certificate": {"cell": KEY, "gated_at": "2026-09-02T23:37:32+00:00"}},
        {"name": "CHFNOK.carry.asia#input_symbol=CHFNOK", "symbol": "CHFNOK", "family": "carry",
         "status": "LIVE", "params": {"input_symbol": "CHFNOK"},
         "certificate": "CHFNOK.carry.asia#input_symbol=CHFNOK"},
    ]}))
    return (surv,), sleeves


def _queue(tmp_path: Path) -> tuple[Path, dict]:
    files, sleeves = _files(tmp_path)
    certs = q.carry_certificates(CUTOFF, files, sleeves)
    doc, why = q.build_queue(certs, None, ATTESTATION)
    assert why == "ok" and doc is not None
    p = tmp_path / "priority_remint.json"
    p.write_text(json.dumps(doc, default=str))
    return p, doc


def _sweep(tmp_path: Path, verdicts: list, fresh: set | None = None) -> tuple[dict, dict]:
    """The survivor block's two partitions, exactly as the judge runs them."""
    path, _ = _queue(tmp_path)
    survivors = {KEY: _cert_row()}
    old = {"gate_policy": ATTESTATION, "survivors": dict(survivors)}
    _cells, stale = eg.remint_cells(path)
    from gate_policy import is_exact_policy
    rm = eg.remint_partition(old, survivors, verdicts, fresh or set(), stale, is_exact_policy,
                             VERSION, NOW)
    retired = dict(rm["retired"])
    if PATCHED:
        b = eg.verdict_bound_partition(survivors, verdicts, fresh or set(),
                                       eg.verdict_bound_keys(path), VERSION, NOW)
        retired.update(b["retired"])
    return survivors, retired


def _unmeasured_too_short() -> dict:
    return {"cell": CELL, "sym": "CHFNOK", "family": "carry", "days": 29, "passed": False,
            "unmeasured": True, "unknown_reason": "short_history_after_cut",
            "failed_gates": ["observations"],
            "stages": {"observations": {"passed": False, "days": 29, "required": 60}}}


def _pending_history() -> dict:
    return {"cell": CELL, "sym": "CHFNOK", "family": "carry", "days": 0, "passed": None,
            "stages": {}, "downstream_status": "PENDING_HISTORY",
            "why": "PENDING_HISTORY: CHFNOK carry holds 29 honest swap weekday(s)"}


# ------------------------------------------------------------------------------ the queue
def test_carry_certificates_gated_before_adoption_and_both_live_sleeves_are_queued(
        tmp_path) -> None:
    files, sleeves = _files(tmp_path)
    certs = q.carry_certificates(CUTOFF, files, sleeves)
    assert set(certs) == {KEY}
    assert sorted(certs[KEY]["sleeves"]) == ["CHFNOK.carry.asia#input_symbol=CHFNOK",
                                             "chfnok_carry_asia_p_98d776f3e210d3e2"]
    assert "stays in force until a real ten-gate verdict" in certs[KEY]["reason"]


def test_the_queue_is_verdict_bound_and_never_names_a_stale_key(tmp_path) -> None:
    _, doc = _queue(tmp_path)
    assert doc["verdict_bound_keys"] == [KEY] and doc["cells"] == [CELL]
    assert KEY not in (doc.get("stale_certificate_keys") or [])


def test_the_queue_keeps_other_writers_cells_and_drains_its_own(tmp_path) -> None:
    existing = {"attestation": ATTESTATION, "cells": ["X.y.p=1", "OLD.carry.p=gone"],
                "carry_pit_cells": ["OLD.carry.p=gone"],
                "stale_certificate_keys": ["external.X.y.p=1"]}
    files, sleeves = _files(tmp_path)
    doc, why = q.build_queue(q.carry_certificates(CUTOFF, files, sleeves), existing, ATTESTATION)
    assert why == "ok" and doc is not None
    assert doc["cells"] == [CELL, "X.y.p=1"]
    assert doc["stale_certificate_keys"] == ["external.X.y.p=1"]


def test_a_queue_for_another_attestation_is_never_replaced(tmp_path) -> None:
    files, sleeves = _files(tmp_path)
    doc, why = q.build_queue(q.carry_certificates(CUTOFF, files, sleeves),
                             {"attestation": {"version": "other"}, "cells": ["a"]}, ATTESTATION)
    assert doc is None and "ANOTHER attestation" in why


def test_the_cutoff_is_stamped_once_at_adoption(tmp_path) -> None:
    p = tmp_path / "carry_pit_adoption.json"
    assert q.adoption_cutoff(p) is None
    first = q.adoption_cutoff(p, stamp=True)
    assert first and q.adoption_cutoff(p, stamp=True) == first


def test_the_write_is_atomic_and_a_refused_replace_leaves_the_file_whole(
        tmp_path, monkeypatch) -> None:
    p = tmp_path / "priority_remint.json"
    p.write_text('{"cells": ["kept"]}')
    real_replace = os.replace

    def refuse(src, dst):  # what Windows does onto a read-only destination (WinError 5)
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(q.os, "replace", refuse)
    with pytest.raises(PermissionError):
        q.atomic_write(p, '{"cells": ["new"]}')
    assert json.loads(p.read_text()) == {"cells": ["kept"]}
    assert [f.name for f in tmp_path.iterdir()] == ["priority_remint.json"]
    monkeypatch.setattr(q.os, "replace", real_replace)
    q.atomic_write(p, '{"cells": ["new"]}')
    assert json.loads(p.read_text()) == {"cells": ["new"]}


# ------------------------------------------------------------- the judge never wrongly retires
@pytest.mark.parametrize("verdict", [_unmeasured_too_short(), _pending_history(), None])
def test_a_short_or_unmeasured_history_never_retires_the_certificate(tmp_path, verdict) -> None:
    survivors, retired = _sweep(tmp_path, [verdict] if verdict else [])
    assert KEY in survivors and survivors[KEY]["gates"] == _ten()
    assert retired == {}


def test_the_forward_clock_survives_a_pending_history_sweep(tmp_path) -> None:
    """After the sweep the certificate is still one `shadow_admission.authorized_runs` hands the
    forward engine -- the door `clock_certificate` reads backing through -- so the clock stays
    BACKED and `retire_unbacked` has nothing to take."""
    from shadow_admission import authorized_runs
    survivors, _ = _sweep(tmp_path, [_pending_history()])
    base = tmp_path / "base"
    (base / "reports").mkdir(parents=True)
    (base / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"gate_policy": ATTESTATION, "survivors": survivors}))
    runs = authorized_runs(base, lanes=("h1",))
    assert KEY in {r["certificate"] for r in runs}


@pytest.mark.skipif(not PATCHED, reason="PARKED: arms when carry_pit.patch lands in the sealed "
                                        "external_gauntlet.py (verdict_bound_partition)")
def test_with_the_patch_a_real_measured_fail_retires_and_a_pass_replaces(tmp_path) -> None:
    failed = _ten()
    failed["deflated_sharpe"] = {"passed": False, "dsr": 0.4}
    real = {"cell": CELL, "sym": "CHFNOK", "passed": False, "stages": failed,
            "terminal_gate": "deflated_sharpe"}
    survivors, retired = _sweep(tmp_path, [real])
    assert KEY not in survivors and KEY in retired
    assert "deflated_sharpe" in retired[KEY]["retired_reason"]
    survivors, retired = _sweep(tmp_path, [{**real, "passed": True, "stages": _ten()}],
                                fresh={KEY})
    assert KEY in survivors and retired == {}


@pytest.mark.skipif(not PATCHED, reason="PARKED: arms when carry_pit.patch lands")
def test_with_the_patch_a_lockbox_with_no_evidence_is_not_a_real_fail(tmp_path) -> None:
    st = _ten()
    st["lockbox"] = {"passed": False, "lockbox_sharpe": None, "n_days": 12,
                     "why": "held-out window is 12 days, under the 40-day floor"}
    survivors, retired = _sweep(tmp_path, [{"cell": CELL, "passed": False, "stages": st}])
    assert KEY in survivors and retired == {}


def test_the_queue_runs_on_the_hourly_clock_and_reaches_the_judge() -> None:
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("carry_rejudge", "scripts/queue_carry_rejudge.py", "--write")' in cycle
    assert '"carry_rejudge": crj' in cycle and '"carry_rejudge": 120' in cycle
    judge = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert '"priority_remint.json"' in judge and "def remint_partition" in judge
