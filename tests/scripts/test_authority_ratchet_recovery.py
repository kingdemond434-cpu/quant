from __future__ import annotations

import json

from scripts import check_authority_ratchet as ratchet


def _doc(n: int, *, params: bool = True, revoked: bool = False) -> dict:
    rows = {}
    for i in range(n):
        row = {"cell": f"cell-{i}"}
        if params:
            row["shadow_spec"] = {"params": {"lookback": i + 1}}
        rows[f"survivor-{i}"] = row
    doc = {"n": n, "survivors": rows, "gate_policy": {"policy": "test"}}
    if revoked:
        doc["revoked"] = ["survivor-old"]
    return doc


def test_smaller_authority_is_atomically_restored_from_canon(monkeypatch, tmp_path) -> None:
    auth = tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json"
    canon = tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json"
    auth.parent.mkdir()
    canon.parent.mkdir()
    auth.write_text(json.dumps(_doc(0)), "utf-8")
    canon.write_text(json.dumps(_doc(2)), "utf-8")
    monkeypatch.setattr(ratchet, "AUTHORITY_FILE", auth)
    monkeypatch.setattr(ratchet, "CANON_FILE", canon)
    monkeypatch.setattr(ratchet, "hold", lambda *_a, **_kw: _NullLease())

    message = ratchet.restore_authority()

    assert "authority restored" in message
    assert json.loads(auth.read_text("utf-8"))["survivors"] == _doc(2)["survivors"]


def test_explicit_revocation_is_not_undone(monkeypatch, tmp_path) -> None:
    auth = tmp_path / "authority.json"
    canon = tmp_path / "canon.json"
    auth.write_text(json.dumps(_doc(0, revoked=True)), "utf-8")
    canon.write_text(json.dumps(_doc(2)), "utf-8")
    monkeypatch.setattr(ratchet, "AUTHORITY_FILE", auth)
    monkeypatch.setattr(ratchet, "CANON_FILE", canon)

    assert ratchet.restore_authority() is None
    assert json.loads(auth.read_text("utf-8"))["revoked"] == ["survivor-old"]


def test_better_authority_heals_canon_under_the_same_lease(monkeypatch, tmp_path) -> None:
    auth = tmp_path / "authority.json"
    canon = tmp_path / "canon.json"
    auth.write_text(json.dumps(_doc(2)), "utf-8")
    canon.write_text(json.dumps(_doc(1)), "utf-8")
    monkeypatch.setattr(ratchet, "AUTHORITY_FILE", auth)
    monkeypatch.setattr(ratchet, "CANON_FILE", canon)
    monkeypatch.setattr(ratchet, "hold", lambda *_a, **_kw: _NullLease())

    message = ratchet.heal_canon()

    assert "canon healed" in message
    assert json.loads(canon.read_text("utf-8"))["survivors"] == _doc(2)["survivors"]


def test_cohort_loss_merges_latest_sufficient_git_snapshot(monkeypatch, tmp_path) -> None:
    cohort = tmp_path / "cohort_registry.json"
    cohort.write_text(json.dumps({"current": {"observations": 2}}), "utf-8")
    monkeypatch.setattr(ratchet, "COHORT_FILE", cohort)
    monkeypatch.setattr(ratchet, "ROOT", tmp_path)
    monkeypatch.setattr(ratchet, "hold", lambda *_a, **_kw: _NullLease())

    class Result:
        def __init__(self, stdout: str, returncode: int = 0) -> None:
            self.stdout, self.returncode = stdout, returncode

    def fake_run(command, **_kwargs):
        if command[1] == "rev-list":
            return Result("known-good\n")
        return Result(json.dumps({"old": {"observations": 0}, "current": {"observations": 1}}))

    monkeypatch.setattr(ratchet.subprocess, "run", fake_run)
    message = ratchet.restore_cohorts_from_git(2)

    assert "1 -> 2" in message
    assert json.loads(cohort.read_text("utf-8"))["current"]["observations"] == 2


class _NullLease:
    def __enter__(self):
        return "test-token"

    def __exit__(self, *_exc):
        return False
