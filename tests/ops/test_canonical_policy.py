"""Canonical policy resolution -- the PRE-DEEPSEEK mandate's II-B/II-D as behavior, not prose.

The load-bearing case is the STALE-POLICY SIMULATION (gate item 4 of XXVI): edit the policy file
without regenerating the state record and the resolver must say HASH_MISMATCH, visibly, rather
than pass on the stale record or die. A resolver that raises reads as silence in a cron log, and
silence is the exact failure II-D names.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.ops.canonical_policy import POLICY_STATE, policy_duty, resolve

_REPO = Path(__file__).resolve().parents[2]


def _seed(tmp: Path, body: str = "THE POLICY\n") -> Path:
    """A miniature repo: policy file + state record whose hash genuinely matches."""
    import hashlib
    pol = tmp / "docs/policy/MANDATE.md"
    pol.parent.mkdir(parents=True)
    pol.write_text(body, "utf-8")
    (tmp / POLICY_STATE).write_text(json.dumps({
        "canonical_policy_version": "test.1",
        "canonical_policy_hash": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
        "policy_file": "docs/policy/MANDATE.md",
    }), "utf-8")
    return pol


def test_matching_hash_resolves(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = resolve(tmp_path)
    assert r["verdict"] == "RESOLVED"
    assert r["canonical_policy_version"] == "test.1"


def test_stale_policy_fails_visible(tmp_path: Path) -> None:
    """Gate item 4. An edit without a regenerated state record is the mandate's HASH_MISMATCH."""
    pol = _seed(tmp_path)
    pol.write_text("THE POLICY\nedited without regenerating the state record\n", "utf-8")
    r = resolve(tmp_path)
    assert r["verdict"] == "HASH_MISMATCH"
    assert "FAIL VISIBLE" in r["why"]


def test_missing_state_record_is_unknown_never_a_pass(tmp_path: Path) -> None:
    r = resolve(tmp_path)
    assert r["verdict"] == "MISSING_POLICY" and "unreadable" in r["why"]


def test_missing_policy_file_is_unknown_never_a_pass(tmp_path: Path) -> None:
    pol = _seed(tmp_path)
    pol.unlink()
    r = resolve(tmp_path)
    assert r["verdict"] == "MISSING_POLICY"


def test_resolver_never_raises_on_garbage_state(tmp_path: Path) -> None:
    (tmp_path / POLICY_STATE).parent.mkdir(parents=True)
    (tmp_path / POLICY_STATE).write_text("{not json", "utf-8")
    assert resolve(tmp_path)["verdict"] == "MISSING_POLICY"


# --------------------------------------------------------------------- R0438: policy_duty()
def test_policy_duty_empty_when_resolved(tmp_path: Path) -> None:
    """STEADY: no text at all when policy is verified -- matches libs.ops.repair_mode's own
    convention, and ops/brain_env.sh only injects a non-empty block."""
    _seed(tmp_path)
    assert policy_duty(tmp_path) == ""


def test_policy_duty_names_the_mismatched_file(tmp_path: Path) -> None:
    pol = _seed(tmp_path)
    pol.write_text("THE POLICY\nedited without regenerating the state record\n", "utf-8")
    text = policy_duty(tmp_path)
    assert "[II-D]" in text and "HASH MISMATCH" in text
    assert "docs/policy/MANDATE.md" in text


def test_policy_duty_reports_missing_policy(tmp_path: Path) -> None:
    text = policy_duty(tmp_path)
    assert "[II-B]" in text and "UNRESOLVED" in text


def test_policy_duty_adds_work_and_removes_none(tmp_path: Path) -> None:
    """Same banned-verb discipline libs.ops.repair_mode._BANNED_VERBS asserts, and the same test
    shape tests/governance/test_repair_actuator.py uses -- checks the EMITTED TEXT, never the
    docstring (which legitimately discusses "stop"/"cut" while explaining why the function does
    not emit them). A duty producer must never teach an organ to do less."""
    from libs.ops.repair_mode import _BANNED_VERBS
    pol = _seed(tmp_path)
    pol.write_text("edited\n", "utf-8")
    mismatch_text = policy_duty(tmp_path)
    missing_text = policy_duty(tmp_path.parent / "nonexistent")
    for verb in _BANNED_VERBS:
        assert verb not in mismatch_text.lower(), f"HASH_MISMATCH text contains {verb!r}"
        assert verb not in missing_text.lower(), f"MISSING_POLICY text contains {verb!r}"


def test_main_calls_the_lawful_guard() -> None:
    src = Path("libs/ops/canonical_policy.py").read_text("utf-8")
    assert "from libs.ops.lawful import guard as _law_guard" in src
    assert "_law_guard()" in src


def test_the_real_repo_policy_resolves() -> None:
    """The committed state record must match the committed mandate byte-for-byte -- this is the
    'fresh Claude resolves latest canonical policy hash/version' proof (gate item 1), and it
    turns every future edit-without-rehash into a red test instead of a silent divergence."""
    r = resolve(_REPO)
    assert r["verdict"] == "RESOLVED", r.get("why")
    assert r["canonical_policy_version"] == "2026-08-11.1"
    # Both mandates must verify -- the DeepSeek flywheel landed as a second canonical file and
    # the verdict is the conjunction, so a stale edit to EITHER file turns this test red.
    assert len(r["policies"]) == 2
    assert all(row["verdict"] == "RESOLVED" for row in r["policies"])
