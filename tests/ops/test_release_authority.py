"""The release authority (ops/release/authority/): signed attestations replace pasted registry
rows, and every way around them fails closed. Each case runs the REAL authority and the REAL box
gate against the sandbox's fake GitHub, temp key and simulated clock."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "authority_sandbox", ROOT / "ops/release/authority/sandbox.py"
)
assert _spec is not None and _spec.loader is not None
sb_mod = importlib.util.module_from_spec(_spec)
sys.modules["authority_sandbox"] = sb_mod
_spec.loader.exec_module(sb_mod)
H1, H2 = sb_mod.H1, sb_mod.H2


@pytest.fixture
def sb(tmp_path: Path) -> Any:
    return sb_mod.Sandbox(tmp_path)


def _through_window(sb: Any) -> None:
    sb.gate()  # notice
    sb.clock.advance(hours=24, minutes=1)
    sb.gate()


# ------------------------------------------------------------------- the happy path


def test_a_protected_pr_merges_only_after_the_authority_signs_and_24h_pass(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    assert len(sb.notices) == 1 and sb.gh.merges() == []
    sb.clock.advance(hours=23, minutes=59)
    sb.gate()
    assert sb.gh.merges() == []
    sb.clock.advance(minutes=2)
    sb.gate()
    (m,) = sb.gh.merges()
    assert m["sha"] == H1  # pinned: GitHub refuses it if the head moved
    assert "registry CLEAR" in m["commit_title"]  # auto_revert() recognises it


# ------------------------------------------------------------------- spoofing


def test_an_unsigned_registry_row_merges_nothing_once_the_authority_is_on(sb: Any) -> None:
    row = {"pr": 41, "sha": H1, "verdict": "CLEAR", "at": "2026-11-04T11:00:00+00:00"}
    sb.registry.write_text(json.dumps(row) + "\n", encoding="utf-8")
    _through_window(sb)
    assert sb.gh.merges() == [] and sb.notices == []


def _forge(sb: Any, **change: Any) -> dict[str, Any]:
    """A CLEAR signed by the real authority, then optionally altered after signing."""
    assert sb.authority()[0] == "CLEAR"
    (f,) = sorted(sb.folder.glob("pr41-*.json"))
    env = json.loads(f.read_text())
    f.unlink()
    return env


def test_a_clear_signed_by_any_other_key_is_refused(sb: Any) -> None:
    from cryptography.hazmat.primitives.asymmetric import ed25519

    env = _forge(sb)
    st = json.loads(env["statement"])
    other = ed25519.Ed25519PrivateKey.generate()
    # same key id claimed, other key's signature
    sig = base64.b64encode(other.sign(env["statement"].encode())).decode()
    env2 = {"statement": env["statement"], "key_id": st["key_id"], "sig": sig}
    (sb.folder / "pr41-forged.json").write_text(json.dumps(env2))
    _through_window(sb)
    assert sb.gh.merges() == []


def test_an_edited_statement_no_longer_verifies(sb: Any) -> None:
    env = _forge(sb)
    st = json.loads(env["statement"])
    st["head_sha"] = H2  # carry the CLEAR to another head
    env["statement"] = json.dumps(st, sort_keys=True, separators=(",", ":"))
    (sb.folder / "pr41-edited.json").write_text(json.dumps(env))
    sb.gh.pr["head"]["sha"] = H2
    _through_window(sb)
    assert sb.gh.merges() == []


def test_a_pr_author_cannot_self_approve_with_a_comment(sb: Any) -> None:
    sb.gh.comments.append({"body": f"AUDIT CLEAR {H1}", "created_at": "2026-11-04T11:00:00Z",
                           "updated_at": "2026-11-04T11:00:00Z", "author_association": "OWNER",
                           "performed_via_github_app": {"slug": "claude"}})  # fmt: skip
    _through_window(sb)
    assert sb.gh.merges() == []  # no attestation: a comment is not one


# ------------------------------------------------------------------- stale, failed, missing


def test_a_new_push_makes_the_clear_stale(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    sb.gh.pr["head"]["sha"] = H2
    sb.clock.advance(hours=30)
    sb.gate()
    assert sb.gh.merges() == []


def test_failed_ci_is_never_signed_and_a_later_failure_blocks_a_signed_clear(sb: Any) -> None:
    sb.gh.conclusion["replay-shadow"] = "failure"
    assert sb.authority()[0] == "FAIL" and list(sb.folder.iterdir()) == []
    sb.gh.conclusion["replay-shadow"] = "success"
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    sb.gh.conclusion["mt5-money-path"] = "failure"  # a re-run went red mid-window
    sb.clock.advance(hours=25)
    sb.gate()
    assert sb.gh.merges() == []


def test_a_failed_independent_review_is_never_turned_into_a_clear(sb: Any) -> None:
    sb.gh.conclusion["independent-review"] = "failure"
    v, why = sb.authority()
    assert v == "FAIL" and "independent-review" in " ".join(why)


def test_a_check_changing_pr_needs_the_base_run_trusted_eval(sb: Any) -> None:
    sb.gh.trusted_eval = None
    assert sb.authority()[0] == "WAIT"
    sb.gh.trusted_eval = "failure"
    assert sb.authority()[0] == "FAIL"
    sb.gh.trusted_eval = "success"
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    sb.gh.trusted_eval = "failure"  # the gate re-reads it too
    sb.clock.advance(hours=25)
    sb.gate()
    assert sb.gh.merges() == []


def test_an_expired_attestation_is_refused(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    sb.clock.advance(hours=49)
    sb.gate()
    assert sb.gh.merges() == []


# ------------------------------------------------------------------- policy-changing PRs


@pytest.mark.parametrize("path", [
    ".github/scripts/audit_gate.py",
    "ops/release/authority/ROOT_POLICY.json",
    "ops/release/authority/attestation.py",
    ".github/workflows/trusted-eval.yml",
    "ops/box/workflow_gate.ps1",
])  # fmt: skip
def test_a_pr_that_changes_the_authority_or_the_merger_is_root_and_held(
    tmp_path: Path, path: str
) -> None:
    sb = sb_mod.Sandbox(tmp_path, files=(path,))
    v, why = sb.authority()
    assert v == "HOLD" and "ROOT" in why[0]
    _through_window(sb)
    assert sb.gh.merges() == []


def test_a_grow_only_list_may_grow_but_never_shrink(tmp_path: Path) -> None:
    p = "ops/release/protected_paths.txt"
    sb = sb_mod.Sandbox(tmp_path, files=(p,))
    sb.base_text[p] = "a/*\nb/*\n"
    sb.head_text[p] = "a/*\nb/*\nc/*\n"
    assert sb.authority()[0] == "CLEAR"
    (tmp_path / "2").mkdir()
    sb2 = sb_mod.Sandbox(tmp_path / "2", files=(p,))
    sb2.base_text[p] = "a/*\nb/*\n"
    sb2.head_text[p] = "a/*\n"
    assert sb2.authority()[0] == "HOLD"


def test_the_root_pin_must_match_live_or_nothing_merges(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.pin.write_text(json.dumps({"digest": "0" * 64}))
    _through_window(sb)
    assert sb.gh.merges() == []


def test_the_root_digest_moves_with_any_root_file_and_only_root_files() -> None:
    pol = sb_mod._load("p", ROOT / "ops/release/authority/policy.py")
    policy = pol.load_policy()
    files = {"ops/release/authority/policy.py": b"x", "scripts/x.py": b"y"}
    d0 = pol.root_digest(files.get, files, policy)
    assert pol.root_digest({**files, "scripts/x.py": b"z"}.get, files, policy) == d0
    assert pol.root_digest({**files, "ops/release/authority/policy.py": b"q"}.get, files,
                           policy) != d0  # fmt: skip
    assert pol.root_digest(lambda n: None, files, policy) != d0  # a deleted root file


# ------------------------------------------------------------------- the sizing envelope


def _ceil(**mx: float) -> dict[str, Any]:
    return {"max": {"desks/mt5/mt5desk/sizing.py": {"MAX_RISK_FRAC": mx.get("m", 0.08),
                                                    "BASE_RISK_FRAC": 0.03},
                    "desks/mt5/prop/ftmo_follower.py": {"DAILY_LOSS_FRAC": mx.get("d", 0.05),
                                                        "MAX_LOSS_FRAC": 0.1}},
            "equal": {"a.py": {"K": 1}}, "superset": {"r.py": "RAILS"}}  # fmt: skip


@pytest.fixture
def env() -> dict[str, Any]:
    pol = sb_mod._load("p2", ROOT / "ops/release/authority/policy.py")
    return {"pol": pol, "env": pol.load_policy()["envelope"]}


def test_a_raise_inside_the_envelope_is_delegated(env: Any) -> None:
    assert env["pol"].envelope_check(_ceil(m=0.08), _ceil(m=0.1), env["env"]) == []


def test_a_raise_past_the_hard_max_or_more_than_one_step_is_root(env: Any) -> None:
    bad = env["pol"].envelope_check(_ceil(m=0.08), _ceil(m=0.12), env["env"])
    assert any("hard max" in b for b in bad)
    bad = env["pol"].envelope_check(_ceil(m=0.05), _ceil(m=0.08), env["env"])
    assert any("one step" in b for b in bad)


def test_a_firm_rule_is_never_raised(env: Any) -> None:
    bad = env["pol"].envelope_check(_ceil(d=0.05), _ceil(d=0.06), env["env"])
    assert any("firm rule" in b for b in bad)


def test_a_lowered_ceiling_is_not_delegated_either(env: Any) -> None:
    """#637 audit MF2: NEVER REDUCE AGGRESSIVENESS -- a cap lowered by fiat is zuck's call."""
    bad = env["pol"].envelope_check(_ceil(m=0.08), _ceil(m=0.06), env["env"])
    assert any("lowered" in b for b in bad)
    assert env["pol"].envelope_check(_ceil(m=0.08), _ceil(m=0.08), env["env"]) == []


def test_pins_and_rail_lists_cannot_move_through_the_envelope(env: Any) -> None:
    head = _ceil()
    head["equal"]["a.py"]["K"] = 2
    head["superset"] = {}
    bad = env["pol"].envelope_check(_ceil(), head, env["env"])
    assert any("equal pin" in b for b in bad) and any("superset" in b for b in bad)


def test_an_unknown_knob_raise_is_root(env: Any) -> None:
    base, head = _ceil(), _ceil()
    base["max"]["x.py"] = {"K": 1.0}
    head["max"]["x.py"] = {"K": 1.1}
    assert env["pol"].envelope_check(base, head, env["env"])


# ------------------------------------------------------------------- notification and vetoes


def test_no_delivered_notice_no_window_no_merge(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.deliver = False
    for _ in range(3):
        sb.gate()
        sb.clock.advance(hours=12)
    assert sb.gh.merges() == []
    sb.deliver = True
    sb.authority()  # still within its TTL? re-signed if needed
    sb.gate()  # the window starts only now
    sb.clock.advance(hours=1)
    sb.gate()
    assert sb.gh.merges() == []


@pytest.mark.parametrize("veto", ["comment", "row", "kill_file", "deactivate"])
def test_a_mid_window_veto_stops_the_merge(sb: Any, veto: str) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    sb.clock.advance(hours=12)
    if veto == "comment":
        sb.gh.comments.append({"body": f"AUDIT HOLD {H1}", "created_at": "2026-11-05T00:00:00Z",
                               "updated_at": "2026-11-05T00:00:00Z",
                               "author_association": "OWNER"})  # fmt: skip
    elif veto == "row":
        sb.registry.write_text(json.dumps({"pr": 41, "sha": H1, "verdict": "HOLD",
                                           "at": "2026-11-05T00:00:00+00:00"}) + "\n")  # fmt: skip
    elif veto == "kill_file":
        (sb.folder / "DEACTIVATE").write_text("stop")
    else:
        sb.gh.board.append({"body": sb.ag.DEACTIVATE, "created_at": "2026-11-05T00:00:00Z",
                            "updated_at": "2026-11-05T00:00:00Z",
                            "author_association": "OWNER"})  # fmt: skip
    sb.clock.advance(hours=13)
    sb.gate()
    assert sb.gh.merges() == []


def test_conflicting_authority_verdicts_hold(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    key, kid = sb.att.load_private(sb.key_pem)
    f = {"pr": 41, "head": H1, "base_sha": "b" * 40, "patch_id": "patch-of-1111",
         "cls": "CONTROLLER"}  # fmt: skip
    env = sb.auth.issue(f, "HOLD", ["test"], repo="o/r", digest=sb.digest, key=key, kid=kid,
                        ttl_h=48, now=sb.clock.t)  # fmt: skip
    sb.auth.write(sb.folder, env, 41, H1, "HOLD", sb.digest)
    _through_window(sb)
    assert sb.gh.merges() == []


def test_a_clear_for_the_wrong_class_is_refused(sb: Any) -> None:
    key, kid = sb.att.load_private(sb.key_pem)
    f = {"pr": 41, "head": H1, "base_sha": "b" * 40, "patch_id": "patch-of-1111", "cls": "AUTO"}
    env = sb.auth.issue(f, "CLEAR", ["test"], repo="o/r", digest=sb.digest, key=key, kid=kid,
                        ttl_h=48, now=sb.clock.t)  # fmt: skip
    sb.auth.write(sb.folder, env, 41, H1, "CLEAR", sb.digest)
    _through_window(sb)  # the gate reads PROTECTED: only a CONTROLLER CLEAR covers it
    assert sb.gh.merges() == []


def test_the_authority_signs_nothing_without_the_pin_or_with_the_kill_file(
    sb: Any, tmp_path: Path
) -> None:
    sb.pin.write_text(json.dumps({"digest": "0" * 64}))
    args = ["--repo", "o/r", "--out", str(sb.folder), "--key", str(sb.key_pem),
            "--root-pin", str(sb.pin), "--pr", "41"]  # fmt: skip
    assert sb.auth.main(args) == 2
    sb.pin.write_text(json.dumps({"digest": sb.digest}))
    (sb.folder / "DEACTIVATE").write_text("stop")
    assert sb.auth.main(args) == 2
    assert [p.name for p in sb.folder.iterdir()] == ["DEACTIVATE"]


# ------------------------------------------------------------------- the decision itself


@pytest.mark.parametrize("facts,want", [
    ({"cls": "ROOT", "cls_reasons": ["x"]}, "HOLD"),
    ({"cls": "REFUSED", "cls_reasons": ["x"]}, "HOLD"),
    ({"cls": "MYSTERY"}, "HOLD"),
    ({"hold": "AUDIT HOLD abc"}, "HOLD"),
    ({"deactivated": True}, "WAIT"),
    ({"patch_id": None}, "WAIT"),
    ({"checks": ("pending", "running")}, "WAIT"),
    ({"checks": ("fail", "independent-review"), "review_queued": True}, "WAIT"),
    ({"checks": ("fail", "x")}, "FAIL"),
    ({"fresh": False, "fresh_why": "behind"}, "WAIT"),
    ({"open": False}, "WAIT"),
    ({}, "CLEAR"),
])  # fmt: skip
def test_decide_fails_closed(facts: dict[str, Any], want: str) -> None:
    pol = sb_mod._load("p3", ROOT / "ops/release/authority/policy.py")
    base = {"open": True, "same_repo": True, "base_ok": True, "cls": "AUTO", "patch_id": "p",
            "checks": ("pass", "ok"), "fresh": True}  # fmt: skip
    assert pol.decide({**base, **facts})[0] == want


@pytest.mark.parametrize("path", [
    ".github/scripts/audit_gate.py",
    "ops/release/authority/ROOT_POLICY.json",
    "ops/release/authority/authority.py",
    ".github/workflows/trusted-eval.yml",
    "ops/box/workflow_gate.ps1",
])  # fmt: skip
def test_every_root_file_is_protected_so_no_no_comment_path_can_merge_it(
    sb: Any, path: str
) -> None:
    """A root file on the AUTO path would merge with no authority at all once AUTO is active."""
    files = [{"filename": path, "status": "modified", "additions": 1, "deletions": 0}]
    assert sb.ag.tier(files, 1, lambda n: False)[0] == "PROTECTED"
    assert sb.auth.pol._match(path, sb.policy["root_files"])


# ---- Level 2: the commit status the LIVE ruleset requires -------------------------------------


def _auth() -> Any:
    return sb_mod._load("authority_service_l2", ROOT / "ops/release/authority/authority.py")


def test_status_auto_clear_is_success() -> None:
    a = _auth()
    assert a.status_for({"cls": "AUTO"}, "CLEAR", [], since=None, veto_h=24)[0] == "success"


def test_status_controller_waits_out_the_veto() -> None:
    from datetime import UTC, datetime, timedelta

    a = _auth()
    now = datetime(2026, 11, 4, tzinfo=UTC)
    f = {"cls": "CONTROLLER"}
    assert a.status_for(f, "CLEAR", [], since=None, veto_h=24, now=now)[0] == "pending"
    early = a.status_for(f, "CLEAR", [], since=now - timedelta(hours=23), veto_h=24, now=now)
    assert early[0] == "pending" and "1.0 h left" in early[1]
    late = a.status_for(f, "CLEAR", [], since=now - timedelta(hours=24), veto_h=24, now=now)
    assert late[0] == "success"


@pytest.mark.parametrize("verdict,state", [("HOLD", "failure"), ("FAIL", "failure"),
                                           ("WAIT", "pending")])  # fmt: skip
def test_status_never_success_without_clear(verdict: str, state: str) -> None:
    a = _auth()
    got = a.status_for({"cls": "CONTROLLER"}, verdict, ["why"], since=None, veto_h=24)
    assert got[0] == state


def test_first_signed_reads_the_earliest_statement(tmp_path: Path) -> None:
    a = _auth()
    head = "a" * 40
    for i, t in enumerate(["2026-11-03T10:00:00+00:00", "2026-11-03T08:00:00+00:00"]):
        (tmp_path / f"pr7-{head[:12]}-CLEAR-deadbeef-{i}.json").write_text(
            json.dumps({"statement": {"head_sha": head, "issued_at": t}}), encoding="utf-8"
        )
    (tmp_path / f"pr7-{head[:12]}-CLEAR-deadbeef-x.json").write_text(
        json.dumps({"statement": {"head_sha": "b" * 40, "issued_at": "2026-11-01T00:00:00+00:00"}}),
        encoding="utf-8",
    )
    from datetime import UTC, datetime

    now = datetime(2026, 11, 4, tzinfo=UTC)
    got = a.first_signed(tmp_path, 7, head, "deadbeef" + "0" * 56, now=now)
    assert got is not None and got.hour == 8 and got.day == 3
    # a HOLD at 09:00 restarts the window: only the 10:00 CLEAR counts
    (tmp_path / f"pr7-{head[:12]}-HOLD-deadbeef-h.json").write_text(
        json.dumps({"statement": {"head_sha": head, "issued_at": "2026-11-03T09:00:00+00:00",
                                  "verdict": "HOLD"}}), encoding="utf-8")  # fmt: skip
    got = a.first_signed(tmp_path, 7, head, "deadbeef" + "0" * 56, now=now)
    assert got is not None and got.hour == 10
    # a future-dated CLEAR is ignored
    (tmp_path / f"pr7-{head[:12]}-CLEAR-deadbeef-f.json").write_text(
        json.dumps({"statement": {"head_sha": head, "issued_at": "2026-11-09T00:00:00+00:00"}}),
        encoding="utf-8",
    )
    got = a.first_signed(tmp_path, 7, head, "deadbeef" + "0" * 56, now=now)
    assert got is not None and got.hour == 10


def test_status_is_failure_outside_the_delegated_classes_even_on_clear() -> None:
    a = _auth()
    for cls in ("ROOT", "REFUSED", None):
        assert a.status_for({"cls": cls}, "CLEAR", [], since=None, veto_h=24)[0] == "failure"


def _check_ruleset() -> Any:
    return sb_mod._load("check_ruleset", ROOT / "ops/release/authority/check_ruleset.py")


def test_prepared_ruleset_is_refused_until_the_state_app_is_named() -> None:
    cr = _check_ruleset()
    rs = json.loads((ROOT / "ops/release/authority/ruleset_live.json").read_text(encoding="utf-8"))
    assert cr.problems(rs) == [
        "bypass actor Integration has a placeholder id: fill in the state App's id"
    ]
    for b in rs["bypass_actors"]:
        if b["actor_id"] == 0:
            b["actor_id"] = 7777777
    assert cr.problems(rs) == []


@pytest.mark.parametrize("bad", [
    {"actor_type": "Integration", "actor_id": 15368, "bypass_mode": "always"},
    {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
    {"actor_type": "DeployKey", "actor_id": 1, "bypass_mode": "always"},
])  # fmt: skip
def test_ruleset_check_refuses_unsafe_bypass(bad: dict[str, Any]) -> None:
    cr = _check_ruleset()
    rs = json.loads((ROOT / "ops/release/authority/ruleset_live.json").read_text(encoding="utf-8"))
    rs["bypass_actors"] = [b for b in rs["bypass_actors"] if b["actor_id"] != 0]
    rs["bypass_actors"] += [{"actor_type": "Integration", "actor_id": 7777777,
                             "bypass_mode": "always"}, bad]  # fmt: skip
    assert cr.problems(rs)
