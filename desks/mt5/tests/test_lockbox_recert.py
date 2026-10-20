"""The lockbox v4 re-certification ledger (pass-2 P0): before/after lockbox Sharpe per certificate.

Pins: the committed baseline covers all 52 canon certificates with lockbox == WF on every one;
each after-state (re-minted, re-minted under a superseding key, retired, pending, re-stamped) is
read correctly; the pass is idempotent and the BEFORE side is write-once; DONE requires 0 of the
re-minted rows to show lockbox == WF; the artifact is on the box's sync list; the leg is wired.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import lockbox_recert as lr  # noqa: E402

from libs.ops import release  # noqa: E402

OLD = "v2-old"
NEW = "v3-reserved-lockbox"
NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


BASIS = "reserved_final_calendar_fraction (test)"


def _row(lb: float, wf: float, at: str, *, carved: bool = True, **extra: Any) -> dict[str, Any]:
    lock: dict[str, Any] = {"passed": lb > 0, "lockbox_sharpe": lb}
    if carved:                                     # what a v4 judge stamps after lockbox_stage
        lock.update(cut="2024-12-19", basis=BASIS)
    return {"gated_at": at, "gates": {"lockbox": lock,
                                      "walk_forward": {"passed": True, "oos_sharpe": wf}},
            **extra}


def _write(p: Path, doc: Any) -> Path:
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _baseline(tmp: Path, keys: list[str]) -> Path:
    return _write(tmp / "baseline.json", {"source_commit": "abc", "certificates": {
        k: {**lr.sharpes(_row(0.2, 0.2, "2026-08-26T00:00:00+00:00")),
            "gated_at": "2026-08-26T00:00:00+00:00", "attestation": OLD} for k in keys}})


def _build(tmp: Path, canon: dict, report: dict | None = None,
           previous: Any = None) -> dict[str, Any]:
    return lr.build(canon=_write(tmp / "canon.json", canon),
                    report=_write(tmp / "report.json", report or {}),
                    baseline=tmp / "baseline.json", previous=previous, current=NEW, now=NOW)


def test_the_committed_baseline_is_the_52_with_lockbox_equal_to_wf() -> None:
    seed = json.loads(lr.BASELINE.read_text("utf-8"))
    certs = seed["certificates"]
    assert len(certs) == 52
    assert sum(1 for c in certs.values() if c["lockbox_equals_wf"]) == 52
    canon = json.loads((DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json").read_text("utf-8"))
    assert set(certs) <= set(canon["survivors"]) | set(canon.get("pending_rejudge") or {}) \
        | set(canon.get("retired_certificates") or {}), "a baseline key left every canon block"


def test_every_after_state_is_read(tmp_path: Path) -> None:
    keys = ["a", "b", "c", "d", "e", "f"]
    _baseline(tmp_path, keys)
    canon = {"gate_policy": {"version": NEW},
             "survivors": {"a": _row(0.11, 0.19, "2026-10-01T01:00:00+00:00"),
                           "b2": _row(0.15, 0.15, "2026-10-01T01:00:00+00:00"),
                           "e": _row(0.2, 0.2, "2026-08-26T00:00:00+00:00")},
             "reattestation": {"superseded": {"b": "b2"}},
             "retired_certificates": {"c": {**_row(-0.1, 0.3, "2026-10-01T01:00:00+00:00"),
                                            "gates_superseded": {}}},
             "pending_rejudge": {"d": {}}}
    doc = _build(tmp_path, canon)
    st = {k: v["after"]["state"] for k, v in doc["certificates"].items()}
    # b2 is re-gated but its lockbox equals its WF Sharpe: not a held-out reading
    assert st == {"a": "REMINTED", "b": lr.NOT_INDEPENDENT, "c": "RETIRED", "d": "PENDING",
                  "e": "RESTAMPED", "f": "ABSENT"}
    a = doc["certificates"]["a"]
    assert a["before"]["lockbox_equals_wf"] and not a["after"]["lockbox_equals_wf"]
    assert a["after"]["lockbox_sharpe"] == 0.11
    assert doc["certificates"]["c"]["after"]["rejudged_under_v4"] is True
    assert doc["before_lockbox_equals_wf"] == 6
    assert doc["after_lockbox_equals_wf"] == 1          # b2 still equal
    assert doc["rejudge_required"] == ["b", "d", "e"]
    assert doc["restamped"] == 1 and not doc["done"]
    assert doc["status"].startswith("BREACH")


def test_a_stale_store_is_pending_not_restamped(tmp_path: Path) -> None:
    _baseline(tmp_path, ["a"])
    canon = {"gate_policy": {"version": OLD},
             "survivors": {"a": _row(0.2, 0.2, "2026-08-26T00:00:00+00:00")}}
    doc = _build(tmp_path, canon)
    assert doc["certificates"]["a"]["after"]["state"] == "PENDING"
    assert doc["status"] == "IN_PROGRESS" and not doc["done"]


def test_done_only_when_all_resolved_and_none_equal(tmp_path: Path) -> None:
    _baseline(tmp_path, ["a", "c"])
    canon = {"gate_policy": {"version": NEW},
             "survivors": {"a": _row(0.11, 0.19, "2026-10-01T01:00:00+00:00")},
             "retired_certificates": {"c": _row(-0.1, 0.3, "2026-10-01T01:00:00+00:00")}}
    doc = _build(tmp_path, canon)
    assert doc["done"] and doc["status"] == "DONE"
    assert doc["counts"]["REMINTED"] == 1 and doc["counts"]["RETIRED"] == 1


def test_idempotent_and_the_before_side_is_write_once(tmp_path: Path) -> None:
    _baseline(tmp_path, ["a"])
    canon = {"gate_policy": {"version": OLD},
             "survivors": {"a": _row(0.2, 0.2, "2026-08-26T00:00:00+00:00"),
                           "boxonly": _row(0.3, 0.3, "2026-08-27T00:00:00+00:00")}}
    first = _build(tmp_path, canon)
    assert first["certificates"]["boxonly"]["before"]["source"] == "box_canon"
    again = _build(tmp_path, canon, previous=first)
    assert again["certificates"] == first["certificates"], "a re-run changed the ledger"
    # After the re-mint the box-only row is re-judged: its BEFORE must not be rewritten.
    reminted = {"gate_policy": {"version": NEW},
                "survivors": {"boxonly": _row(0.05, 0.3, "2026-10-01T01:00:00+00:00")},
                "pending_rejudge": {"a": {}}}
    after = _build(tmp_path, reminted, previous=again)
    box = after["certificates"]["boxonly"]
    assert box["before"]["lockbox_sharpe"] == 0.3 and box["before"]["attestation"] == OLD
    assert box["after"]["state"] == "REMINTED" and box["after"]["lockbox_sharpe"] == 0.05


def test_write_is_atomic_and_leaves_no_temp(tmp_path: Path) -> None:
    out = tmp_path / "LOCKBOX_RECERT.json"
    lr.write({"k": 1}, out)
    lr.write({"k": 2}, out)
    assert json.loads(out.read_text("utf-8")) == {"k": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["LOCKBOX_RECERT.json"]


def test_the_box_publishes_it() -> None:
    rel = "desks/mt5/reports/LOCKBOX_RECERT.json"
    ps = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert f'"{rel}"' in ps.split("$relPaths = @(", 1)[1].split("\n)", 1)[0]
    assert rel in release.NON_CODE
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text((ROOT / ".gitignore").read_text("utf-8"), "utf-8")
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text("{}", "utf-8")
        assert subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=root,
                              check=False).returncode == 1, f"{rel} is gitignored"


def test_the_leg_is_wired_after_the_seal() -> None:
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer(\n        "lockbox_recert", "research/lockbox_recert.py")' in cycle
    assert cycle.index('_costed("canon_publication"') < cycle.index('_costed("lockbox_recert"')


# ------------------------------------------- the lockbox must be held out (2026-10-20)


def test_independence_needs_a_carve_a_basis_and_a_number_unlike_wf() -> None:
    at = "2026-10-01T01:00:00+00:00"
    assert lr.lockbox_independence(_row(0.11, 0.19, at)["gates"], BASIS)["verdict"] \
        == lr.INDEPENDENT
    for gates, needle in (
            (_row(0.19, 0.19, at)["gates"], "restates gate 7"),
            (_row(0.11, 0.19, at, carved=False)["gates"], "never reserved"),
            ({"lockbox": {"passed": False, "lockbox_sharpe": None, "cut": "x", "basis": BASIS},
              "walk_forward": {"oos_sharpe": 0.2}}, "no numeric lockbox"),
            (_row(0.11, 0.19, at)["gates"], "differs")):
        got = lr.lockbox_independence(gates, BASIS if needle != "differs" else "other basis")
        assert got["verdict"] == lr.NOT_INDEPENDENT
        assert any(needle in w for w in got["why"]), (needle, got["why"])
    assert lr.lockbox_independence({}, None)["verdict"] == lr.NOT_INDEPENDENT


def test_a_regated_row_whose_lockbox_was_never_carved_is_not_reminted(tmp_path: Path) -> None:
    """The 7 of 2026-10-20: gated after the baseline, before v3 landed, lockbox == WF."""
    _baseline(tmp_path, ["a", "b"])
    canon = {"gate_policy": {"version": NEW},
             "survivors": {"a": _row(0.6088, 0.6088, "2026-09-29T20:48:07+00:00",
                                     carved=False),
                           "b": _row(0.30, 0.41, "2026-09-27T02:15:47+00:00", carved=False)}}
    doc = _build(tmp_path, canon)
    st = {k: v["after"]["state"] for k, v in doc["certificates"].items()}
    assert st == {"a": lr.NOT_INDEPENDENT, "b": lr.NOT_INDEPENDENT}
    assert doc["certificates"]["a"]["after"]["lockbox"] == lr.UNMEASURED
    assert doc["after_lockbox_equals_wf"] == 1 and not doc["done"]
    assert doc["status"] == f"BREACH: {lr.NOT_INDEPENDENT}" and doc["breach"] == 2


def test_the_sleeves_holding_an_affected_certificate_are_named(tmp_path: Path) -> None:
    reg = _write(tmp_path / "sleeves.json", {"sleeves": [
        {"name": "s1", "status": "STANDBY", "risk_frac": 0.0,
         "certificate": {"cell": "e", "source": "UNIVERSAL_SURVIVORS"}},
        {"name": "s2", "status": "LIVE", "certificate": "e"},
        {"name": "s3", "status": "RETIRED", "certificate": {"cell": "e"}},
        {"name": "s4", "status": "LIVE", "certificate": {"cell": "zz"}}]})
    got = lr.sleeve_holders({"e"}, reg)
    assert [h["sleeve"] for h in got["sleeves"]] == ["s1", "s2"]
    assert got["n_live"] == 1 and got["n_standby"] == 1
    assert lr.sleeve_holders({"e"}, tmp_path / "absent.json")["status"] == lr.UNMEASURED


def test_the_holdback_publishes_an_unmeasured_missed_growth_line(tmp_path: Path) -> None:
    _baseline(tmp_path, ["e"])
    reg = _write(tmp_path / "sleeves.json", {"sleeves": [
        {"name": "s1", "status": "STANDBY", "risk_frac": 0.0, "certificate": {"cell": "e"}}]})
    doc = lr.build(canon=_write(tmp_path / "canon.json", {
        "gate_policy": {"version": NEW},
        "survivors": {"e": _row(0.2, 0.2, "2026-08-26T00:00:00+00:00")}}),
        report=_write(tmp_path / "report.json", {}), baseline=tmp_path / "baseline.json",
        current=NEW, now=NOW, sleeves=reg)
    (line,) = doc["missed_growth"]
    assert line["value"] is None and line["value_status"] == lr.UNMEASURED
    assert line["n_certificates"] == 1 and line["n_sleeves"] == 1
    assert line["risk_frac_withheld"] == 0.0


def test_an_unread_registry_withholds_unmeasured_risk_not_zero(tmp_path: Path) -> None:
    """Audit 2026-10-20 v2 delta: an UNMEASURED sleeve registry never publishes 0 withheld."""
    now = datetime(2026, 10, 20, tzinfo=UTC)
    (line,) = lr.missed_growth_lines(["e"], {"status": lr.UNMEASURED, "why": "absent"}, now)
    assert line["risk_frac_withheld"] is None and line["risk_frac_status"] == lr.UNMEASURED
    assert line["n_sleeves"] is None and line["n_live_sleeves"] is None
    (ok,) = lr.missed_growth_lines(["e"], {"status": "MEASURED", "n_live": 0, "sleeves": [
        {"sleeve": "s", "status": "STANDBY", "risk_frac": 0.0}]}, now)
    assert ok["risk_frac_withheld"] == 0.0 and ok["risk_frac_status"] == "MEASURED"


def test_missed_growth_reads_an_unmeasured_recert_as_unmeasured(tmp_path: Path,
                                                               monkeypatch) -> None:
    import missed_growth as mg

    path = _write(tmp_path / "LOCKBOX_RECERT.json", {"status": lr.UNMEASURED,
                                                      "missed_growth": []})
    monkeypatch.setattr(mg, "LOCKBOX_RECERT", path)
    assert mg.lockbox_holdback_lines()["verdict"] == mg.UNMEASURED
    _write(path, {"status": "DONE", "missed_growth": []})
    assert mg.lockbox_holdback_lines()["verdict"] == mg.NOT_BINDING
