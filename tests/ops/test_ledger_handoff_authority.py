from libs.ops import live_ledger_migration as module
from libs.ops.release_promotion import AdoptionDecision


def test_released_gate_target_is_accepted():
    assert module.authorized_handoff(AdoptionDecision("ADOPT_RELEASE", "signed", ""), "signed")
    assert not module.authorized_handoff(AdoptionDecision("ADOPT_RELEASE", "signed", ""), "other")


def test_post_adoption_hold_accepts_only_exact_current_production():
    decision = AdoptionDecision(
        "HOLD", None, "", release_sha="signed", head="signed", unreleased_code=["untested.py"]
    )
    assert module.authorized_handoff(decision, "signed")
    assert not module.authorized_handoff(decision, "untested")


def test_unverified_diff_or_absent_release_remains_refused():
    assert not module.authorized_handoff(
        AdoptionDecision("HOLD", None, "", release_sha="signed", head="signed"), "signed"
    )
    assert not module.authorized_handoff(
        AdoptionDecision("HOLD", None, "", head="signed", unreleased_code=["code.py"]), "signed"
    )


def test_override_and_different_head_remain_refused():
    assert not module.authorized_handoff(
        AdoptionDecision(
            "OVERRIDE_TIP",
            "signed",
            "",
            release_sha="signed",
            head="signed",
            unreleased_code=["code.py"],
        ),
        "signed",
    )
    assert not module.authorized_handoff(
        AdoptionDecision(
            "HOLD", None, "", release_sha="signed", head="other", unreleased_code=["code.py"]
        ),
        "signed",
    )


def test_state_preserving_adopter_merge_requires_proven_release_ancestry_and_code():
    from types import SimpleNamespace

    decision = AdoptionDecision(
        "HOLD", None, "", release_sha="signed", head="box-merge", unreleased_code=["untested.py"]
    )
    state_only = SimpleNamespace(
        is_ancestor=lambda *_: True, changed=lambda *_: ["desks/mt5/data/account_state.json"]
    )
    assert module.authorized_handoff(decision, "signed", state_only)
    changed_code = SimpleNamespace(
        is_ancestor=lambda *_: True, changed=lambda *_: ["libs/execution/sizing.py"]
    )
    assert not module.authorized_handoff(decision, "signed", changed_code)
    unrelated = SimpleNamespace(is_ancestor=lambda *_: False, changed=lambda *_: [])
    assert not module.authorized_handoff(decision, "signed", unrelated)


def test_windows_exclusive_adoption_preserves_rows_and_repeats_without_rewrite(
    tmp_path, monkeypatch
):
    import hashlib
    import importlib.util
    import json
    import os
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    import pytest

    from libs.ops.live_ledger_view import effective_text, record_digest

    if os.name != "nt":
        pytest.skip("Native Windows exclusive-handle contract")
    prepared = Path(__file__).parent / "migrate_live_ledger_view_source.py"
    if not prepared.exists():
        prepared = Path(__file__).resolve().parents[2] / "scripts/migrate_live_ledger_view.py"
    spec = importlib.util.spec_from_file_location("native_handoff_fixture", prepared)
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "libs.ops.live_ledger_migration", module)
    spec.loader.exec_module(runner)
    original = {"deal": 123, "profit": 10, "time": "original"}
    revised = dict(original, time="corrected")
    following = {"deal": 456, "profit": -2}
    baseline = (json.dumps(original) + "\n").encode()
    current = (json.dumps(revised) + "\n" + json.dumps(following) + "\n").encode()
    events = [
        {
            "schema_version": 1,
            "raw_prefix_records": 1,
            "raw_prefix_sha256": hashlib.sha256(baseline).hexdigest(),
            "projection_order": [123],
        },
        {
            "deal": 123,
            "before_sha256": record_digest(original),
            "after_sha256": record_digest(revised),
            "set": {"time": "corrected"},
        },
    ]
    corrections = ("".join(json.dumps(row) + "\n" for row in events)).encode()
    previous = {"append_only": {"live_ledger.jsonl": {"records": 1}}, "vintage": {"fixture": True}}
    target_manifest = dict(
        previous,
        append_only=dict(
            previous["append_only"],
            **{
                runner.SIDECAR: {
                    "records": 2,
                    "prefix_sha": hashlib.sha256(corrections).hexdigest()[:16],
                }
            },
        ),
    )
    for rel, body in [(runner.LEDGER, current), (runner.MANIFEST, json.dumps(previous).encode())]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (tmp_path / "desks/mt5/reports").mkdir(parents=True)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        runner,
        "gate",
        lambda *_args, **_kwargs: AdoptionDecision(
            "ADOPT_RELEASE", "signed-fixture", "synthetic fixture"
        ),
    )
    monkeypatch.setattr(
        runner,
        "show",
        lambda target, rel: (
            baseline
            if target == runner.BASELINE
            else corrections
            if rel == runner.SIDECAR
            else json.dumps(target_manifest).encode()
        ),
    )
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(sys, "argv", ["fixture", "--target", "signed-fixture", "--apply"])
    late = {"deal": 789, "profit": 5}
    plan = runner.migration_bytes
    plans = []

    def append_between_snapshot_and_lock(*args):
        planned = plan(*args)
        if not plans:
            with (tmp_path / runner.LEDGER).open("ab") as handle:
                handle.write((json.dumps(late) + "\n").encode())
        plans.append(True)
        return planned

    monkeypatch.setattr(runner, "migration_bytes", append_between_snapshot_and_lock)
    atomic = runner.atomic
    locked = []

    def assert_locked_then_atomic(path, body):
        if path.name == "live_ledger_corrections.jsonl":
            with pytest.raises(PermissionError):
                (tmp_path / runner.LEDGER).read_bytes()
            locked.append(True)
        atomic(path, body)

    monkeypatch.setattr(runner, "atomic", assert_locked_then_atomic)
    assert runner.main() == 0
    assert locked == [True]
    ledger = tmp_path / runner.LEDGER
    assert (
        ledger.read_bytes()
        == baseline + (json.dumps(following) + "\n" + json.dumps(late) + "\n").encode()
    )
    assert [json.loads(row) for row in effective_text(ledger, ledger.read_text()).splitlines()] == [
        revised,
        following,
        late,
    ]
    assert runner.main() == 0
    receipt = json.loads((tmp_path / "desks/mt5/reports/LEDGER_VIEW_ADOPTION.json").read_bytes())
    assert receipt["state"] == "ALREADY_VERIFIED"
    assert receipt["rows"] == 3
    assert len(list((tmp_path / "data/secrets/ledger-migration-backups").iterdir())) == 1


def test_adoption_handoff_has_an_executable_repair_actuator_and_published_receipt():
    from pathlib import Path

    from desks.mt5.ops.components import explicit_specs

    from libs.ops.control_plane.reconciler import _actuator_for
    from libs.ops.release import is_state_path

    spec = next(
        item
        for item in explicit_specs()
        if item.component_id == "executable:scripts/migrate_live_ledger_view.py"
    )
    assert spec.restart_action == "restart:task:MT5-AdoptRelease"
    assert _actuator_for(spec) is not None
    receipt = "desks/mt5/reports/LEDGER_VIEW_ADOPTION.json"
    assert receipt in spec.outputs
    assert is_state_path(receipt)
    root = Path(__file__).resolve().parents[2]
    publisher = root / "desks/mt5/scripts/sync_shadow_to_git.ps1"
    assert '"' + receipt + '"' in publisher.read_text(encoding="utf-8")
