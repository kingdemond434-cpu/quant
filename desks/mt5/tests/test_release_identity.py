"""The box-side identity verdict, the smoke test, and the live-manifest attestation.

The properties that carry money: the sealed commit and its pure seal commit are a licence; a
diverged SHA, a file edited on the box, or a re-signed judge are not; an identity that cannot be
measured is not a licence either; staleness is reported and refuses only when told to; the SHA
is still known when the git binary is not; the smoke test skips the gateway import off Windows
and says why; and the live manifest carries all of it in a chain that still verifies.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import release_identity as ri  # noqa: E402
from research import live_manifest  # noqa: E402

from libs.ops import release  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required")

SIZING = "desks/mt5/mt5desk/sizing.py"
SMOKE = _DESK / "scripts" / "smoke_release.py"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _commit(cwd: Path, rel: str, text: str | None, msg: str) -> str:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        p.write_text(text, "utf-8")
    _git(cwd, "add", "--", rel)
    _git(cwd, "commit", "-qm", msg)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    for rel in (*release.MONEY_PATH, *release.CONFIG_FILES, release.SURVIVORS):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", "utf-8")
    (r / release.IMMUTABLE_MANIFEST).write_text(json.dumps(
        {"signed_utc": "2026-09-05T00:00:00+00:00", "signed_by": "t", "files": {}}), "utf-8")
    (r / release.PYPROJECT).write_text('[project]\nname = "x"\ndependencies = []\n', "utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "code")
    return r


@pytest.fixture
def sealed(repo: Path) -> Path:
    release.seal(root=repo, by="t", tested=True)
    _commit(repo, release.RELEASE_REL, None, "seal release")
    return repo


# ------------------------------------------------------------------------------ verdict
def test_the_sealed_commit_and_the_pure_seal_commit_are_a_licence(repo: Path) -> None:
    doc = release.seal(root=repo)
    v = ri.verdict(repo)
    assert v.ok and v.measured and v.allows_new_risk() and v.source == "git"
    assert v.running_sha == v.release_sha == doc["code_sha"] and v.release_id == doc["release_id"]
    written = json.loads((repo / ri.VERDICT_REL).read_text("utf-8"))
    assert written["verdict"] == "OK" and written["allows_new_risk"] is True
    s = _commit(repo, release.RELEASE_REL, None, "seal release")
    v = ri.verdict(repo)
    assert v.ok and v.allows_new_risk() and v.running_sha == s and "seal/state" in v.reason
    _commit(repo, "desks/mt5/data/gateway_state.json", "{}\n", "mt5 shadow sync")
    assert ri.verdict(repo).allows_new_risk()


def test_a_diverged_sha_is_refused_and_named(sealed: Path) -> None:
    c = _commit(sealed, SIZING, "# new sizing\n", "code")
    v = ri.verdict(sealed)
    assert not v.ok and v.measured and not v.allows_new_risk()
    assert v.running_sha == c and v.changed_paths == (SIZING,) and "never named" in v.reason
    assert json.loads((sealed / ri.VERDICT_REL).read_text("utf-8"))["verdict"] == "REFUSED"


def test_a_money_path_file_edited_on_the_box_is_refused_by_name(sealed: Path) -> None:
    (sealed / SIZING).write_text("# hot patch on the box\n", "utf-8")
    v = ri.verdict(sealed)
    assert not v.ok and v.drift == (SIZING,) and "drifted on disk" in v.reason
    assert v.changed_paths == ()                 # git still agrees; the disk does not


def test_a_crlf_checkout_is_not_drift(sealed: Path) -> None:
    p = sealed / SIZING
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert ri.verdict(sealed).allows_new_risk()


def test_a_resigned_judge_manifest_is_refused(sealed: Path) -> None:
    p = sealed / release.IMMUTABLE_MANIFEST
    p.write_text(json.dumps({"signed_utc": "2026-09-06T00:00:00+00:00", "signed_by": "someone",
                             "files": {}}), "utf-8")
    v = ri.verdict(sealed)
    assert not v.ok and "judge manifest" in v.reason


def test_a_moved_canon_is_reported_not_refused(sealed: Path) -> None:
    (sealed / release.SURVIVORS).write_text("{}\n", "utf-8")
    v = ri.verdict(sealed)
    assert v.allows_new_risk() and any("canon" in r for r in v.report)


def test_unmeasured_is_not_a_licence(repo: Path, tmp_path: Path) -> None:
    v = ri.verdict(repo)                                   # git, but no RELEASE.json
    assert not v.ok and not v.measured and not v.allows_new_risk()
    assert "UNMEASURED" in v.reason and v.running_sha is not None and v.release_sha is None
    assert json.loads((repo / ri.VERDICT_REL).read_text("utf-8"))["verdict"] == "UNMEASURED"
    bare = tmp_path / "bare"
    bare.mkdir()
    v = ri.verdict(bare, write=False)                      # no git, no RELEASE.json
    assert not v.allows_new_risk() and v.running_sha is None and v.source == "none"
    release.seal(root=repo)
    rec = json.loads((repo / release.RELEASE_REL).read_text("utf-8"))
    rec["code_sha"] = rec["live_sha"] = "unknown"
    (repo / release.RELEASE_REL).write_text(json.dumps(rec), "utf-8")
    v = ri.verdict(repo, write=False)
    assert not v.measured and "no code_sha" in v.reason


def test_stale_is_reported_and_refuses_only_when_configured(
        sealed: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ri.ENV_STALE_REFUSES, raising=False)
    monkeypatch.delenv(ri.ENV_MAX_AGE_H, raising=False)
    rec = json.loads((sealed / release.RELEASE_REL).read_text("utf-8"))
    sealed_at = datetime.fromisoformat(rec["sealed_at"])
    fresh = ri.verdict(sealed, now=sealed_at + timedelta(hours=1), write=False)
    assert not fresh.stale and fresh.age_h == pytest.approx(1.0, abs=0.01)
    late = ri.verdict(sealed, now=sealed_at + timedelta(days=8), write=False)
    assert late.ok and late.stale and late.allows_new_risk()
    assert any("old" in r for r in late.report)
    assert not ri.verdict(sealed, now=sealed_at + timedelta(days=8), stale_refuses=True,
                          write=False).allows_new_risk()
    monkeypatch.setenv(ri.ENV_STALE_REFUSES, "1")
    v = ri.verdict(sealed, now=sealed_at + timedelta(days=8), write=False)
    assert v.stale_refuses and not v.allows_new_risk()
    monkeypatch.setenv(ri.ENV_MAX_AGE_H, str(30 * 24))
    assert ri.verdict(sealed, now=sealed_at + timedelta(days=8), write=False).allows_new_risk()
    assert ri.verdict(sealed, now=sealed_at + timedelta(days=8), max_age_h=24 * 9,
                      write=False).allows_new_risk()
    # A seal of unknown age is stale (unknown is not fresh) and, by default, still reported only.
    monkeypatch.delenv(ri.ENV_STALE_REFUSES)
    rec.pop("sealed_at")
    rec.pop("generated_utc")
    (sealed / release.RELEASE_REL).write_text(json.dumps(rec), "utf-8")
    v = ri.verdict(sealed, write=False)
    assert v.stale and v.age_h is None and v.allows_new_risk()
    assert not ri.verdict(sealed, stale_refuses=True, write=False).allows_new_risk()


# ---------------------------------------------------------------------- without git
def test_head_is_resolved_from_refs_loose_packed_worktree_and_detached(
        repo: Path, tmp_path: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    assert ri.head_from_refs(repo) == head                         # loose ref
    _git(repo, "pack-refs", "--all")
    assert not (repo / ".git" / "refs" / "heads" / "main").exists()
    assert ri.head_from_refs(repo) == head                         # packed-refs
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(wt))
    assert (wt / ".git").is_file()                                 # gitdir: file + commondir
    assert ri.head_from_refs(wt) == _git(wt, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "--detach")
    assert ri.head_from_refs(repo) == head                         # raw sha in HEAD
    assert ri.head_from_refs(tmp_path / "nowhere") is None


def test_without_the_git_binary_equality_is_the_only_yes(
        sealed: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ri, "_git", lambda *a, **k: None)
    v = ri.verdict(sealed, write=False)                            # at the seal commit
    assert v.source == "refs" and v.measured and not v.ok
    assert "cannot be taken" in v.reason and not v.allows_new_risk()
    # Back on the sealed commit itself, manifest on disk (the operator's own checkout): equality
    # needs no diff, so refs alone are enough for a yes.
    record = (sealed / release.RELEASE_REL).read_text("utf-8")
    _git(sealed, "checkout", "-q", "HEAD^")
    (sealed / release.RELEASE_REL).write_text(record, "utf-8")
    v = ri.verdict(sealed, write=False)
    assert v.source == "refs" and v.ok and v.allows_new_risk()


def test_the_cli_exit_code_is_the_verdict(sealed: Path) -> None:
    r = subprocess.run([sys.executable, str(_DESK / "mt5desk" / "release_identity.py"),
                        "--root", str(sealed), "--no-write"], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)["verdict"] == "OK"
    _commit(sealed, SIZING, "# new\n", "code")
    r = subprocess.run([sys.executable, str(_DESK / "mt5desk" / "release_identity.py"),
                        "--root", str(sealed), "--no-write"], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 1 and json.loads(r.stdout)["verdict"] == "REFUSED"


# -------------------------------------------------------------------------- the smoke
def _smoke(root: Path, out: Path) -> tuple[int, dict]:
    r = subprocess.run([sys.executable, str(SMOKE), "--root", str(root), "--out", str(out),
                        "--json"], capture_output=True, text=True, timeout=180)
    assert r.stdout, r.stderr
    return r.returncode, json.loads(r.stdout)


def test_smoke_release_on_this_tree_imports_everything_and_skips_the_gateway_with_a_reason(
        tmp_path: Path) -> None:
    rc, rep = _smoke(_ROOT, tmp_path / "smoke.json")
    assert (tmp_path / "smoke.json").exists()

    # PINNED AS AN INVARIANT, NOT A MAGIC NUMBER. This read `n == 15` and went red the moment
    # `mt5desk.execution_registry` joined the money path -- a true statement about a stale
    # constant, costing a hand edit for every legitimate module the desk grows. The count is
    # derived from the smoke's own MODULES tuple instead.
    #
    # Deriving it would ordinarily WEAKEN the test, because a module silently dropped from
    # MODULES would no longer be noticed. So the names that must never leave are asserted
    # explicitly below. Together the two catch both directions: a module that stops compiling,
    # and a money-path module quietly removed from the list that proves it compiles.
    sys.path.insert(0, str(_ROOT / "desks" / "mt5" / "scripts"))
    import smoke_release
    declared = [name for name, _rel in smoke_release.MODULES]
    n = len(declared)
    assert rep["checks"]["compile"] == {"ok": True, "n": n}
    for never_drop in ("mt5desk.gateway", "mt5desk.decision_core", "mt5desk.sizing",
                       "mt5desk.scalp_exec", "mt5desk.execution_policy", "mt5desk.netting",
                       "research.promoter", "research.shadow_forward", "research.pf_allocator"):
        assert never_drop in declared, f"{never_drop} left the release smoke's module list"

    assert rep["checks"]["imports"]["ok"], rep["failures"]
    if importlib.util.find_spec("MetaTrader5") is None:
        assert rep["checks"]["imports"]["n"] == n - 1 and len(rep["skipped"]) == 1
        assert rep["skipped"][0]["module"] == "mt5desk.gateway"
        assert "MetaTrader5" in rep["skipped"][0]["why"]
    else:
        assert rep["checks"]["imports"]["n"] == n and rep["skipped"] == []
    assert rep["checks"]["identity"]["verdict"] in ("OK", "REFUSED", "UNMEASURED")
    assert "ok" in rep["checks"]["immutable"] and "crlf_only" in rep["checks"]["immutable"]
    assert rep["elapsed_s"] < 20 and rep["at"]
    # ok and the exit code agree, and both are decided by the failures list alone.
    assert rep["ok"] == (rc == 0) == (not rep["failures"])
    for f in rep["failures"]:
        assert f["check"] in ("identity", "immutable"), f     # never imports or compile here


def test_smoke_release_passes_on_a_sealed_signed_tree(sealed: Path, tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "cie_under_test", _ROOT / "scripts" / "check_immutable_evaluator.py")
    assert spec is not None and spec.loader is not None
    cie = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cie)
    cie.ROOT = sealed
    cie.MANIFEST = sealed / release.IMMUTABLE_MANIFEST
    cie.sign("t")
    _git(sealed, "add", "-A")
    _git(sealed, "commit", "-qm", "sign")
    release.seal(root=sealed)
    _commit(sealed, release.RELEASE_REL, None, "seal release")
    rc, rep = _smoke(sealed, tmp_path / "smoke.json")
    assert rc == 0 and rep["ok"] and rep["failures"] == [], rep["failures"]
    assert rep["checks"]["identity"]["verdict"] == "OK" and rep["checks"]["immutable"]["ok"]
    assert rep["sha"] == _git(sealed, "rev-parse", "HEAD")
    # A hot patch on the box: the identity refuses, the smoke test fails, the exit code says so.
    (sealed / SIZING).write_text("# patched\n", "utf-8")
    rc, rep = _smoke(sealed, tmp_path / "smoke2.json")
    assert rc == 1 and not rep["ok"] and rep["failures"][0]["check"] == "identity"
    # A CRLF checkout of the signed judge files is reported, never failed.
    _git(sealed, "checkout", "--", SIZING)
    judge = sealed / "desks/mt5/research/promoter.py"
    judge.write_bytes(judge.read_bytes().replace(b"\n", b"\r\n"))
    rc, rep = _smoke(sealed, tmp_path / "smoke3.json")
    assert rc == 0 and rep["checks"]["immutable"]["crlf_only"] == ["desks/mt5/research/promoter.py"]


# ------------------------------------------------------------------- the live manifest
def test_the_manifest_row_carries_the_attestation_and_the_chain_still_verifies(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_manifest, "CHAIN", tmp_path / "m.jsonl")
    e1 = live_manifest.write()
    e2 = live_manifest.write()
    assert live_manifest.verify()["ok"] and e2["prev"] == e1["hash"]
    assert e2["release"]["verdict"] in ("OK", "REFUSED", "UNMEASURED")
    assert isinstance(e2["release"]["allows_new_risk"], bool)
    assert e2["release"]["running_sha"] == e2["code"]
    assert len(e2["data_schema"]["hash"]) == 16 and e2["data_schema"]["universe_fields"] > 0
    assert "identity_schemas" in e2["data_schema"]
    assert set(e2["allocator_certificate"]) == {"hash", "passed", "at"}
    assert "status" in e2["health"]
    # The attestation is inside the hash: editing it after the fact breaks the chain.
    lines = (tmp_path / "m.jsonl").read_text("utf-8").splitlines()
    row = json.loads(lines[0])
    row["release"]["allows_new_risk"] = True
    row["release"]["verdict"] = "OK"
    lines[0] = json.dumps(row)
    (tmp_path / "m.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    v = live_manifest.verify()
    assert not v["ok"] and v["broken_at"] == 0


def test_the_data_schema_hash_moves_with_field_names_not_values(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uni, reg = tmp_path / "universe.json", tmp_path / "sleeve_registry.json"
    monkeypatch.setitem(live_manifest.TRACKED, "cost_fields", uni)
    monkeypatch.setitem(live_manifest.TRACKED, "sleeve_registry", reg)
    reg.write_text(json.dumps({"sleeves": {"a": {"identity": {"family": "f"}, "status": "LIVE",
                                                 "identity_schema": "venue-2026-08-26"}}}), "utf-8")
    uni.write_text(json.dumps({"XAUUSD": {"spread": 1.0, "swap_long": -2.0}}), "utf-8")
    a = live_manifest._data_schema()
    uni.write_text(json.dumps({"XAUUSD": {"spread": 9.0, "swap_long": 5.0}}), "utf-8")
    assert live_manifest._data_schema()["hash"] == a["hash"]           # values moved
    uni.write_text(json.dumps({"XAUUSD": {"spread": 9.0, "swap_long": 5.0, "new": 1}}), "utf-8")
    assert live_manifest._data_schema()["hash"] != a["hash"]           # a field appeared
    assert a["identity_schemas"] == ["venue-2026-08-26"] and a["sleeve_fields"] == 3


def test_health_summary_reads_the_shadow_cycle_shape(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    h = tmp_path / "shadow_health.json"
    monkeypatch.setattr(live_manifest, "HEALTH", h)
    assert live_manifest._health() == {"status": None}
    h.write_text(json.dumps({"status": "OPERATING", "configured_sleeves": 9, "errors": ["x"],
                             "evidence_blocked_sleeves": 2, "gateway_armed": True}), "utf-8")
    s = live_manifest._health()
    assert s["status"] == "OPERATING" and s["n_errors"] == 1 and s["gateway_armed"] is True


# ---------------------------------------------------------------------------- parity
def test_hash_and_allowlist_mirror_the_seal(tmp_path: Path) -> None:
    assert ri.NON_CODE == release.NON_CODE
    (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
    (tmp_path / "b.py").write_bytes(b"y = 2\n")
    paths = ("a.py", "b.py", "absent.py")
    assert ri.hash_paths(paths, tmp_path) == release.hash_paths(paths, tmp_path)
    h = hashlib.sha256()
    for rel, body in (("a.py", b"x = 1\n"), ("absent.py", b"<absent>"), ("b.py", b"y = 2\n")):
        h.update(rel.encode())
        h.update(body)
    assert ri.hash_paths(paths, tmp_path) == h.hexdigest()[:16]


def test_verdict_uses_utc_now_by_default(sealed: Path) -> None:
    v = ri.verdict(sealed, write=False)
    assert datetime.fromisoformat(v.at).tzinfo is not None
    assert v.age_h is not None and 0 <= v.age_h < 1
    assert datetime.now(tz=UTC) >= datetime.fromisoformat(v.at)
