"""THE RUNTIME ATTESTATION pins the four honest states and the one-host rule.

Every test here builds its own tree under tmp_path. None of them touches the committed
`docs/research/runtime_state.json`: a test that regenerated the attestation would make the fence
unable to catch a stopped clock, which is the only thing the fence is for.
"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runtime_attestation as ra  # noqa: E402

from scripts import check_runtime_attestation as fence  # noqa: E402


def test_state_never_returns_a_blank_and_names_every_case() -> None:
    assert ra._state(False, None, 3600, ran=False)[0] == "NEVER"
    assert ra._state(False, None, 3600, ran=True)[0] == "MISSING"
    assert ra._state(True, 9999.0, 3600, ran=True)[0] == "STALE"
    assert ra._state(True, 60.0, 3600, ran=True)[0] == "LIVE"
    # no declared cadence: nothing here may call it late
    assert ra._state(True, 9e9, None, ran=True)[0] == ra.UNMEASURED
    for exists in (True, False):
        for cad in (3600, None):
            state, why = ra._state(exists, 10.0 if exists else None, cad, ran=True)
            assert state in ra.STATES and why.strip()


def test_summary_takes_only_declared_scalars_and_never_a_body(tmp_path: Path) -> None:
    art = tmp_path / "A.json"
    art.write_text(json.dumps({
        "rows": 12, "status": "ok", "nested": {"a": [1, 2, 3]}, "secret_key": "x" * 500,
        "count": 3, "total": 4, "passed": 5, "failed": 6, "refused": 7, "defects": 8,
        "verdict": "y" * 200,
    }), encoding="utf-8")
    out = ra._summary(art, art.stat().st_size)
    assert "nested" not in out and "secret_key" not in out
    assert len(out) <= ra.MAX_SUMMARY_KEYS
    assert all(isinstance(v, (int, float, bool, str)) for v in out.values())
    assert all(len(v) <= ra.MAX_SUMMARY_CHARS for v in out.values() if isinstance(v, str))


def test_oversized_artifact_is_named_unmeasured_not_skipped(tmp_path: Path) -> None:
    art = tmp_path / "big.json"
    art.write_text("{}", encoding="utf-8")
    out = ra._summary(art, ra.MAX_PARSE_BYTES + 1)
    assert ra.UNMEASURED in str(out["_"])


def test_attest_names_one_host_and_holds_its_size(tmp_path: Path) -> None:
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    doc = ra.attest(ra.Paths.at(tmp_path), budget_s=30.0)
    assert doc["attests_to_host"] == doc["host"]["hostname"] == socket.gethostname()
    assert doc["host"]["role_evidence"].strip()
    assert len(json.dumps(doc, default=str)) <= ra.MAX_JSON_BYTES
    assert set(doc["census"]) == set(ra.STATES)
    assert all(r["state"] in ra.STATES for r in doc["organs"])
    text = ra.render(doc)
    assert doc["host"]["hostname"] in text and "describes no other machine" in text


def _write(tmp_path: Path, doc: dict) -> None:
    p = ra.Paths.at(tmp_path)
    p.out_json.parent.mkdir(parents=True, exist_ok=True)
    p.out_json.write_text(json.dumps(doc, default=str), encoding="utf-8")


def _doc(**over: object) -> dict:
    here = socket.gethostname()
    base = {
        "schema": "runtime_attestation/1",
        "generated_at": ra._iso(time.time()),
        "attests_to_host": here,
        "host": {"hostname": here, "role": "non_trading_host", "role_evidence": "measured"},
        "census": dict.fromkeys(ra.STATES, 0),
        "organs": [],
    }
    base.update(over)
    return base


def test_fence_fails_on_host_drift_everywhere(tmp_path: Path) -> None:
    _write(tmp_path, _doc(attests_to_host="some-other-box"))
    v = fence.measure(tmp_path)
    assert any("host drift" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 2


def test_fence_fails_when_the_role_is_asserted_not_measured(tmp_path: Path) -> None:
    here = socket.gethostname()
    _write(tmp_path, _doc(host={"hostname": here, "role": "box", "role_evidence": ""}))
    assert any("role is asserted" in f for f in fence.measure(tmp_path)["failures"])


def _box_host() -> dict:
    return {"hostname": socket.gethostname(), "role": "trading_host",
            "role_evidence": "gateway_state.json is 0.1h old (fresh)"}


def test_fence_fails_on_staleness_on_the_trading_box(tmp_path: Path) -> None:
    # the box that owns the organs, reading its own stale attestation: red, as always
    _write(tmp_path, _doc(host=_box_host(),
                          generated_at=ra._iso(time.time() - ra.MAX_SILENCE_S - 600)))
    v = fence.measure(tmp_path)
    assert v["on_attesting_host"] and v["age_judged"]
    assert v["staleness"].startswith("STALE")
    assert any("stale on its own host" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 2


def test_off_box_staleness_is_unmeasured_loudly_never_judged(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # a cloud container (every one is hostname `vm`) that attested itself as non_trading_host:
    # its age is not the box's hourly leg, so it reads UNMEASURED with the age and the host
    _write(tmp_path, _doc(generated_at=ra._iso(time.time() - 10 * ra.MAX_SILENCE_S)))
    v = fence.measure(tmp_path)
    assert v["on_attesting_host"] and not v["age_judged"]
    assert v["staleness"].startswith(ra.UNMEASURED)
    assert socket.gethostname() in v["staleness"] and "20.0h" in v["staleness"]
    assert not v["failures"]
    assert fence.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "staleness: UNMEASURED" in out and "20.0h ago on host" in out


def test_structural_failures_stay_red_off_box_even_when_stale(tmp_path: Path) -> None:
    old = ra._iso(time.time() - 10 * ra.MAX_SILENCE_S)
    here = socket.gethostname()
    for doc, needle in (
            (_doc(generated_at=old, attests_to_host="some-other-box"), "host drift"),
            (_doc(generated_at=old, host={"hostname": here, "role": "non_trading_host",
                                          "role_evidence": ""}), "role is asserted"),
            (_doc(generated_at="not-a-time"), "not a timestamp")):
        _write(tmp_path, doc)
        v = fence.measure(tmp_path)
        assert not v["age_judged"]
        assert any(needle in f for f in v["failures"]), needle
        assert not any("stale" in f for f in v["failures"])
        assert fence.main(["--root", str(tmp_path)]) == 2


def test_fence_passes_elsewhere_and_absence_is_unmeasured(tmp_path: Path) -> None:
    # a stale document ABOUT another host is that host's business, not this reader's
    _write(tmp_path, _doc(attests_to_host="other-box",
                          host={"hostname": "other-box", "role": "box",
                                "role_evidence": "measured"},
                          generated_at=ra._iso(time.time() - 10 * ra.MAX_SILENCE_S)))
    v = fence.measure(tmp_path)
    assert not v["on_attesting_host"]
    assert not any("stale" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 0
    assert fence.main(["--root", str(tmp_path), "--require-state"]) == 2
    (tmp_path / "docs" / "research" / "runtime_state.json").unlink()
    assert fence.main(["--root", str(tmp_path)]) == 0
    assert fence.main(["--root", str(tmp_path), "--require-state"]) == 2


def test_the_leg_the_layer_and_the_committed_artifact_are_wired() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["runtime_attestation"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("runtime_attestation"' in src
    assert '"runtime_attestation": rta' in src
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert gate.count("check_runtime_attestation.py") == 2
    # THE WHOLE POINT: both files must be committable, or a reader on GitHub sees nothing.
    from libs.ops.release import is_state_path
    for rel in ("docs/research/runtime_state.json", "docs/research/RUNTIME_STATE.md"):
        assert is_state_path(rel), f"{rel} must be a state path the box owns and pushes"


# ------------------------------------------------------- the declaration, parsed and resolved
def test_a_prose_artifact_declaration_yields_every_path_in_it() -> None:
    """35 organs on the trading box read MISSING because their declaration had a word after the
    path. The declaration was never wrong; it was never parsed."""
    from desks.mt5.ops.components import artifact_paths
    assert artifact_paths("desks/mt5/reports/ADVERSARY.json gate_detail") == (
        "desks/mt5/reports/ADVERSARY.json",)
    assert artifact_paths("a/A.json; b/B.jsonl + c/C.md") == ("a/A.json", "b/B.jsonl", "c/C.md")
    assert artifact_paths("a/A.json (see a/A.json)") == ("a/A.json",)          # de-duplicated
    # a bare filename is a word in a sentence, not a repo path -- but the declaration still
    # COUNTS, because an organ that vanishes from the census is a hole in the ratchet
    assert artifact_paths("registry rows") == ("registry rows",)
    assert artifact_paths("") == ()


def test_resolve_prefers_the_freshest_declared_output_then_names_the_relocation(
        tmp_path: Path) -> None:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    old = tmp_path / "desks" / "mt5" / "reports" / "A.json"
    new = tmp_path / "desks" / "mt5" / "reports" / "B.json"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")
    import os
    os.utime(old, (time.time() - 9000, time.time() - 9000))
    rel, how, age, size = ra.resolve_artifact(
        tmp_path, ("desks/mt5/reports/A.json", "desks/mt5/reports/B.json"))
    assert rel == "desks/mt5/reports/B.json" and how == "declared" and age is not None
    assert size > 0
    # nothing declared exists, but the same basename does: a DECLARATION defect, named as one
    (tmp_path / "desks" / "mt5" / "data" / "C.json").write_text("{}", encoding="utf-8")
    rel, how, age, _ = ra.resolve_artifact(tmp_path, ("desks/mt5/reports/C.json",))
    assert rel == "desks/mt5/data/C.json" and how.startswith("relocated") and age is not None
    # and when it exists nowhere, the row stays absent rather than being invented
    rel, how, age, _ = ra.resolve_artifact(tmp_path, ("desks/mt5/reports/NOPE.json",))
    assert how == "absent" and age is None and rel == "desks/mt5/reports/NOPE.json"


# ------------------------------------------------------------------------------ the ratchet
def test_the_ratchet_only_ever_falls_and_is_per_host(tmp_path: Path) -> None:
    paths = ra.Paths.at(tmp_path)
    ra.ratchet_update(paths, "box-a", {"STALE": 10, "MISSING": 5, "NEVER": 3})
    ra.ratchet_update(paths, "box-a", {"STALE": 4, "MISSING": 5, "NEVER": 9})
    doc = json.loads(paths.ratchet.read_text(encoding="utf-8"))
    floor = doc["hosts"]["box-a"]
    assert (floor["STALE"], floor["MISSING"], floor["NEVER"]) == (4, 5, 3)
    ra.ratchet_update(paths, "box-b", {"STALE": 99, "MISSING": 99, "NEVER": 99})
    doc = json.loads(paths.ratchet.read_text(encoding="utf-8"))
    assert doc["hosts"]["box-a"]["STALE"] == 4 and doc["hosts"]["box-b"]["STALE"] == 99


def test_the_fence_fails_when_a_count_rises_above_its_floor(tmp_path: Path) -> None:
    here = socket.gethostname()
    census = dict.fromkeys(ra.STATES, 0)
    census.update({"LIVE": 300, "STALE": 5, "MISSING": 2, "NEVER": 1})
    _write(tmp_path, _doc(census=census))
    ra.ratchet_update(ra.Paths.at(tmp_path), here, census)
    assert fence.main(["--root", str(tmp_path)]) == 0           # at the floor: held
    worse = dict(census)
    worse["MISSING"] = 4
    _write(tmp_path, _doc(census=worse))
    v = fence.measure(tmp_path)
    assert v["ratchet_regressions"] == ["MISSING rose 2 -> 4"]
    assert any("RATCHET BROKEN" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 2
    better = dict(census)
    better["STALE"] = 0
    _write(tmp_path, _doc(census=better))
    assert fence.main(["--root", str(tmp_path)]) == 0           # below the floor: fine


def test_a_leg_with_a_producer_is_repaired_by_running_the_leg(tmp_path: Path) -> None:
    """A department restart cannot relight a leg that has never fired inside a healthy
    department. The leg's own repair is the leg, proved by its artifact moving."""
    from desks.mt5.ops import components as comp

    from libs.ops.control_plane import reconciler as rec
    legs = [s for s in comp.hourly_leg_specs() if s.restart_action.startswith("run_once:")]
    assert legs, "no leg carries a run_once repair: the plane cannot relight a dark leg"
    a = rec._actuator_for(legs[0])
    assert a is not None and a.name.startswith("run_once:leg:")
    assert a.argv[0] and a.argv[-1]
    assert a.postconditions == (rec.act.PRODUCTION_RESUMED,)


# ---------------------------------------------------------------- --only-missing (merge resolution)
def _row(organ: str, state: str = "NEVER") -> dict:
    return {"organ": organ, "kind": "leg", "code": [f"desks/mt5/research/{organ}.py"],
            "clock": f"hourly_cycle:{organ}", "state": state, "why": "fixture",
            "artifact": "x.json", "artifact_sha256": ra.UNMEASURED, "summary": {},
            "last_run_at": ra.UNMEASURED, "last_run_outcome": ra.UNMEASURED,
            "artifact_age_s": None, "artifact_bytes": 0}


def _as_host(monkeypatch, name: str = "vmi3571445", mid: str = "box-machine-id") -> None:
    monkeypatch.setattr(ra.socket, "gethostname", lambda: name)
    monkeypatch.setattr(ra, "_machine_id", lambda: mid)


def _committed(tmp_path: Path, machine_id: str | None = None) -> Path:
    here = socket.gethostname()
    census = dict.fromkeys(ra.STATES, 0)
    census.update({"LIVE": 1, "STALE": 1})
    doc = _doc(host={"hostname": here, "role": "box", "role_evidence": "measured",
                     "measured_at": "2026-09-30T00:00:00+00:00", "platform": "x",
                     "git_sha": "a" * 40, "git_branch": "live",
                     "release_seal": {"ok": True, "running_sha": "b" * 40,
                                      "release_sha": "b" * 40}},
               census=census, cadence_s=ra.CADENCE_S, max_silence_s=ra.MAX_SILENCE_S,
               states=dict.fromkeys(ra.STATES, "m"),
               scope={"attested": 2, "excluded": 0, "excluded_reason": "r",
                      "registry_components": 2, "hash_skipped_over_budget": 0, "wall_s": 0.1},
               organs=[_row("old_a", "LIVE"), _row("old_b", "STALE")])
    if machine_id is not None:
        doc["host"]["machine_id"] = machine_id
    p = ra.Paths.at(tmp_path)
    p.out_json.parent.mkdir(parents=True, exist_ok=True)
    p.out_json.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return p.out_json


def test_only_missing_appends_new_organs_and_leaves_existing_rows_byte_identical(
        tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch)
    path = _committed(tmp_path, machine_id="box-machine-id")
    before = json.loads(path.read_text(encoding="utf-8"))
    raw_before = [json.dumps(r, indent=1) for r in before["organs"]]
    # the live pass would FLIP both existing rows; --only-missing must not let it
    fresh = [_row("old_a", "NEVER"), _row("old_b", "MISSING"), _row("new_c", "NEVER"),
             _row("new_d", "LIVE")]
    monkeypatch.setattr(ra, "organ_rows", lambda paths, budget_s: ([dict(r) for r in fresh], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))
    assert [json.dumps(r, indent=1) for r in after["organs"][:2]] == raw_before
    assert [r["organ"] for r in after["organs"][2:]] == ["new_c", "new_d"]
    assert after["census"]["LIVE"] == 2 and after["census"]["NEVER"] == 1
    assert after["census"]["STALE"] == 1 and after["census"]["MISSING"] == 0
    assert after["scope"]["attested"] == 4
    for k in ("generated_at", "attests_to_host", "host"):
        assert after[k] == before[k]
    assert not ra.Paths.at(tmp_path).ratchet.exists()          # the ratchet is not touched
    md = ra.Paths.at(tmp_path).out_md.read_text(encoding="utf-8")
    assert "new_c" in md and "new_d" in md
    # each existing row's serialized text is still in the file, unchanged
    text_after = path.read_text(encoding="utf-8")
    for r in before["organs"]:
        block = json.dumps(r, indent=1, default=str).replace("\n", "\n  ")
        assert block in text_after

def test_only_missing_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    path = _committed(tmp_path)
    fresh = [_row("old_a"), _row("new_c")]
    monkeypatch.setattr(ra, "organ_rows", lambda paths, budget_s: ([dict(r) for r in fresh], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    once = path.read_bytes()
    md_once = ra.Paths.at(tmp_path).out_md.read_bytes()
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    assert path.read_bytes() == once
    assert ra.Paths.at(tmp_path).out_md.read_bytes() == md_once


def test_only_missing_refuses_without_a_committed_attestation(tmp_path: Path) -> None:
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 1
    assert not ra.Paths.at(tmp_path).out_json.exists()


def test_only_missing_stamps_rows_and_off_host_never_trusts_local_mtimes(
        tmp_path: Path, monkeypatch) -> None:
    path = _committed(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["host"]["hostname"] = doc["attests_to_host"] = "the-box"
    path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    fresh = [_row("new_live", "LIVE"), _row("new_stale", "STALE"),
             _row("new_missing", "MISSING"), _row("new_never", "NEVER")]
    monkeypatch.setattr(ra, "organ_rows", lambda paths, budget_s: ([dict(r) for r in fresh], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))
    new = {r["organ"]: r for r in after["organs"][2:]}
    assert {k: r["state"] for k, r in new.items()} == {
        "new_live": ra.UNMEASURED, "new_stale": ra.UNMEASURED,
        "new_missing": ra.UNMEASURED, "new_never": "NEVER"}
    assert all(r["measured_on"] == socket.gethostname() and r["measured_at"]
               for r in new.values())
    assert after["census"][ra.UNMEASURED] == 3 and after["census"]["NEVER"] == 1
    assert after["census"]["LIVE"] == 1 and after["census"]["STALE"] == 1  # untouched
    assert after["scope"]["only_missing_appended"][-1]["on_attesting_host"] is False
    # the fence still reads it as a report about the box, with no host drift
    assert not any("host drift" in f for f in fence.measure(tmp_path)["failures"])


def test_only_missing_on_the_attesting_host_keeps_its_measured_state(
        tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch)                                   # the box, by name AND machine id
    path = _committed(tmp_path, machine_id="box-machine-id")
    monkeypatch.setattr(ra, "organ_rows",
                        lambda paths, budget_s: ([_row("new_live", "LIVE")], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    row = json.loads(path.read_text(encoding="utf-8"))["organs"][-1]
    assert row["state"] == "LIVE" and row["measured_on"] == socket.gethostname()


def test_only_missing_trims_only_the_appended_rows(tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch)
    path = _committed(tmp_path, machine_id="box-machine-id")
    doc = json.loads(path.read_text(encoding="utf-8"))
    for r in doc["organs"]:
        r["summary"] = {"status": "keep-me"}
    doc["scope"]["summaries_trimmed"] = 2
    path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    raw_before = [json.dumps(r, indent=1) for r in doc["organs"]]
    base = len(json.dumps(doc, default=str))
    monkeypatch.setattr(ra, "MAX_JSON_BYTES", base + 600)
    fresh = []
    for i in range(6):
        r = _row(f"new_{i}", "LIVE")
        r["summary"] = {"status": "x" * 40, "rows": 10 ** 9 + i, "verdict": "y" * 40}
        fresh.append(r)
    monkeypatch.setattr(ra, "organ_rows", lambda paths, budget_s: ([dict(r) for r in fresh], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))
    assert [json.dumps(r, indent=1) for r in after["organs"][:2]] == raw_before
    trimmed = [r for r in after["organs"][2:] if "trimmed" in str(r["summary"].get("_", ""))]
    assert trimmed and after["scope"]["summaries_trimmed"] == 2 + len(trimmed)


def test_a_cloud_vm_is_off_host_even_when_name_and_machine_id_match(
        tmp_path: Path, monkeypatch) -> None:
    # cloud containers are all "vm" and may share an image-baked machine id: neither makes one
    # the desk's attesting host, because "vm" is not a declared desk host
    _as_host(monkeypatch, name="vm", mid="image-baked-id")
    path = _committed(tmp_path, machine_id="image-baked-id")
    ok, why = ra.attesting_identity(json.loads(path.read_text(encoding="utf-8")))
    assert not ok and "not a declared desk host" in why
    monkeypatch.setattr(ra, "organ_rows",
                        lambda paths, budget_s: ([_row("new_live", "LIVE")], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    row = json.loads(path.read_text(encoding="utf-8"))["organs"][-1]
    assert row["state"] == ra.UNMEASURED and row["measured_on"] == "vm"


def test_the_box_is_on_host_and_another_machine_id_is_not(tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch)
    doc = json.loads(_committed(tmp_path, machine_id="box-machine-id").read_text(
        encoding="utf-8"))
    assert ra.attesting_identity(doc)[0] is True
    _as_host(monkeypatch, mid="someone-elses-id")         # same name, different machine
    ok, why = ra.attesting_identity(doc)
    assert not ok and why.startswith("off-host")


def test_an_old_format_stamp_is_unverifiable_not_breakage(tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch, name="vm", mid="whatever")
    path = _committed(tmp_path)                             # no machine_id: LIVE's current file
    before = json.loads(path.read_text(encoding="utf-8"))
    ok, why = ra.attesting_identity(before)
    assert not ok and why.startswith("UNVERIFIABLE")
    monkeypatch.setattr(ra, "organ_rows",
                        lambda paths, budget_s: ([_row("new_never", "NEVER")], {}))
    assert ra.main(["--root", str(tmp_path), "--only-missing"]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["organs"][:2] == before["organs"] and after["host"] == before["host"]
    assert after["organs"][-1]["state"] == "NEVER"
    assert not any("host drift" in f or "role" in f for f in fence.measure(tmp_path)["failures"])


def test_the_host_stamp_records_the_machine_identity(tmp_path: Path, monkeypatch) -> None:
    _as_host(monkeypatch)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    h = ra.host_identity(ra.Paths.at(tmp_path))
    assert h["hostname"] == "vmi3571445" and h["machine_id"] == "box-machine-id"
    assert h["desk_host"] is True
