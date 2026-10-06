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


def _row(lb: float, wf: float, at: str, **extra: Any) -> dict[str, Any]:
    return {"gated_at": at, "gates": {"lockbox": {"passed": lb > 0, "lockbox_sharpe": lb},
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
    assert st == {"a": "REMINTED", "b": "REMINTED", "c": "RETIRED", "d": "PENDING",
                  "e": "RESTAMPED", "f": "ABSENT"}
    a = doc["certificates"]["a"]
    assert a["before"]["lockbox_equals_wf"] and not a["after"]["lockbox_equals_wf"]
    assert a["after"]["lockbox_sharpe"] == 0.11
    assert doc["certificates"]["c"]["after"]["rejudged_under_v4"] is True
    assert doc["before_lockbox_equals_wf"] == 6
    assert doc["after_lockbox_equals_wf"] == 1          # b2 still equal
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
