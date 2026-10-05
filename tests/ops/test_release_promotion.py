"""Development -> green release -> production -> master, and the box's release gate.

Real git, real bare remote, in tmp_path: the promotion is a sequence of pushes whose safety is
"never force, never publish untested code", and only a real remote rejects a non-fast-forward.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from libs.ops import release_promotion as rp

ROOT = Path(__file__).resolve().parents[2]
LIVE = rp.LIVE_BRANCH


def _cli() -> ModuleType:
    """The CLI loaded by FILE: `scripts` is a namespace package that another test's sys.path
    insertion (desks/mt5) can shadow, so `from scripts import ...` is order-dependent."""
    spec = importlib.util.spec_from_file_location("_release_promotion_cli",
                                                  ROOT / "scripts" / "release_promotion.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k, v in (("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@example.com"),
                 ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@example.com")):
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(rp.OVERRIDE_ENV, raising=False)
    (tmp_path / "gitconfig").write_text("[init]\n\tdefaultBranch = master\n", encoding="utf-8")


def _g(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        _g(repo, "add", rel)
    _g(repo, "commit", "-q", "-m", msg)
    return _g(repo, "rev-parse", "HEAD")


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    """A bare `origin` with master (old, divergent history) and the live branch."""
    origin = tmp_path / "origin.git"
    _g(tmp_path, "init", "-q", "--bare", str(origin))
    dev = tmp_path / "dev"
    _g(tmp_path, "clone", "-q", str(origin), str(dev))
    _commit(dev, {"README": "master-only history\n"}, "old master")
    _g(dev, "push", "-q", "origin", "HEAD:refs/heads/master")
    _g(dev, "checkout", "-q", "--orphan", LIVE)
    _g(dev, "rm", "-q", "-rf", "--cached", ".")
    (dev / "README").unlink()
    _commit(dev, {"libs/a.py": "A = 1\n", "desks/mt5/data/state.json": "{}\n"}, "live root")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    return {"origin": origin, "dev": dev}


def _ev(sha: str) -> rp.Evidence:
    return rp.Evidence(tested_sha=sha, run_id="123", run_attempt="1",
                       run_url="https://example.invalid/run/123",
                       law_gate="LAW GATE -- 38 fences: PASS",
                       quality_suite="10 passed, 0 failed, 0 errors, 1 skipped (11 collected)",
                       mt5_suite="20 passed, 0 failed, 0 errors, 0 skipped (20 collected)")


def _remote(origin: Path, ref: str) -> str | None:
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=origin,
                       capture_output=True, text=True)
    return r.stdout.strip() or None


# ------------------------------------------------------------------------------ pure rules
def test_tag_names_sort_by_time_and_round_trip() -> None:
    sha = "6c8a71a40d7ddc267f890c86686bc5d8330983b7"
    t = rp.tag_name(sha, datetime(2026, 9, 30, 10, 17, 36, tzinfo=UTC))
    assert t == "release/20260930T101736Z-6c8a71a40d7d"
    assert rp.parse_tag(t) == (datetime(2026, 9, 30, 10, 17, 36, tzinfo=UTC), sha[:12])
    older = rp.tag_name(sha, datetime(2026, 9, 29, tzinfo=UTC))
    assert rp.newest_release_tag([older, t, "release/garbage", "v1"]) == t
    assert rp.newest_release_tag(["nope"]) is None
    with pytest.raises(ValueError):
        rp.tag_name("xyz", datetime.now(UTC))


def test_code_paths_use_the_gateways_own_rule() -> None:
    assert rp.code_paths(["libs/a.py", "desks/mt5/data/RELEASE.json", "desks/mt5/data/x.json",
                          "docs/y.md", "desks/mt5/gateway_state.json",
                          "desks/mt5/mt5desk/gateway.py"]) == ["desks/mt5/mt5desk/gateway.py",
                                                               "libs/a.py"]


def test_junit_counts_and_the_counts_command(tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    xml = tmp_path / "j.xml"
    xml.write_text('<testsuites><testsuite tests="12" failures="1" errors="0" skipped="2"/>'
                   '<testsuite tests="3" failures="0" errors="1" skipped="0"/></testsuites>',
                   encoding="utf-8")
    c = rp.junit_counts(xml)
    assert c == {"tests": 15, "failures": 1, "errors": 1, "skipped": 2, "passed": 11}
    law = tmp_path / "law.txt"
    law.write_text("noise\nLAW GATE -- 38 fences: PASS\n  judged: cwd==HEAD\n", encoding="utf-8")
    cli = _cli()
    assert cli.main(["counts", "--junit", str(xml), "--law-log", str(law)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["suite=11 passed, 1 failed, 1 errors, 2 skipped (15 collected)",
                   "law_gate=LAW GATE -- 38 fences: PASS"]
    assert cli.main(["counts", "--junit", str(tmp_path / "absent.xml")]) == 0
    assert capsys.readouterr().out.startswith("suite=UNMEASURED")


# --------------------------------------------------------------------------- CI promotion
def test_first_promotion_tags_creates_production_and_tree_takes_master(
        world: dict[str, Path]) -> None:
    dev, origin = world["dev"], world["origin"]
    tested = _g(dev, "rev-parse", "HEAD")
    master_before = _remote(origin, "refs/heads/master")
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    res = rp.promote(dev, tested, _ev(tested), now=now)

    tag = rp.tag_name(tested, now)
    assert res.tag == tag and res.tag_created
    assert _remote(origin, f"refs/tags/{tag}^{{commit}}") == tested
    # annotated, and it carries the evidence
    assert _g(origin, "cat-file", "-t", f"refs/tags/{tag}") == "tag"
    body = _g(origin, "cat-file", "-p", f"refs/tags/{tag}")
    for needle in ("tested_sha: " + tested, "ci_run: 123 attempt 1", "LAW GATE -- 38 fences: PASS",
                   "quality_suite: 10 passed", "mt5_money_path_suite: 20 passed",
                   "previous_production: none"):
        assert needle in body, needle
    assert _remote(origin, "refs/heads/production") == tested

    master = _remote(origin, "refs/heads/master")
    assert master is not None and master != master_before
    parents = _g(origin, "rev-list", "--parents", "-n", "1", master).split()[1:]
    assert parents == [master_before, tested]          # first parent = old master
    assert _g(origin, "rev-parse", f"{master}^{{tree}}") == _g(origin, "rev-parse",
                                                                 f"{tested}^{{tree}}")


def test_second_promotion_fast_forwards_and_is_idempotent(world: dict[str, Path]) -> None:
    dev, origin = world["dev"], world["origin"]
    first = _g(dev, "rev-parse", "HEAD")
    rp.promote(dev, first, _ev(first), now=datetime(2026, 9, 30, 12, tzinfo=UTC))
    second = _commit(dev, {"libs/a.py": "A = 2\n"}, "code change")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    res = rp.promote(dev, second, _ev(second), now=datetime(2026, 9, 30, 13, tzinfo=UTC))
    assert res.production_before == first and res.production_after == second
    body = _g(origin, "cat-file", "-p", f"refs/tags/{res.tag}")
    assert f"previous_production: {first} (1 code path(s) changed since)" in body
    master = _remote(origin, "refs/heads/master")
    # a rerun of the same run: no second tag, nothing moves
    again = rp.promote(dev, second, _ev(second), now=datetime(2026, 9, 30, 14, tzinfo=UTC))
    assert not again.tag_created and again.tag == res.tag
    assert _remote(origin, "refs/heads/master") == master
    assert len(_g(origin, "tag", "--list", "release/*").split()) == 2


def test_the_seal_commit_is_released_when_it_only_adds_the_manifest(
        world: dict[str, Path]) -> None:
    dev, origin = world["dev"], world["origin"]
    tested = _g(dev, "rev-parse", "HEAD")
    seal = _commit(dev, {"desks/mt5/data/RELEASE.json": "{}\n"}, "seal release")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    res = rp.promote(dev, seal, _ev(tested))
    assert _remote(origin, "refs/heads/production") == seal and res.tag


def test_promotion_refuses_untested_code_and_off_branch_targets(world: dict[str, Path]) -> None:
    dev = world["dev"]
    tested = _g(dev, "rev-parse", "HEAD")
    untested = _commit(dev, {"libs/b.py": "B = 1\n"}, "untested code")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    with pytest.raises(ValueError, match="code path"):
        rp.promote(dev, untested, _ev(tested))
    _g(dev, "checkout", "-q", "-b", "side", tested)
    stray = _commit(dev, {"desks/mt5/data/state.json": "{\"x\": 1}\n"}, "never pushed")
    with pytest.raises(ValueError, match="not on origin"):
        rp.promote(dev, stray, _ev(tested))


def test_production_is_never_forced_or_moved_backwards(world: dict[str, Path]) -> None:
    dev, origin = world["dev"], world["origin"]
    first = _g(dev, "rev-parse", "HEAD")
    second = _commit(dev, {"libs/a.py": "A = 3\n"}, "newer")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    rp.promote(dev, second, _ev(second))
    older = rp.promote(dev, first, _ev(first))          # an older run finishing late
    assert _remote(origin, "refs/heads/production") == second
    assert older.production_after == second
    # production moved off the live history by hand: refuse, do not force
    _g(dev, "checkout", "-q", "--orphan", "elsewhere")
    stray = _commit(dev, {"x": "1\n"}, "stray")
    _g(dev, "push", "-q", "-f", "origin", f"{stray}:refs/heads/production")
    _g(dev, "checkout", "-q", LIVE)
    third = _commit(dev, {"libs/a.py": "A = 4\n"}, "third")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    with pytest.raises(ValueError, match="not an ancestor"):
        rp.promote(dev, third, _ev(third))
    assert _remote(origin, "refs/heads/production") == stray


def test_master_sync_retries_when_master_moves(world: dict[str, Path],
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    dev, origin = world["dev"], world["origin"]
    tested = _g(dev, "rev-parse", "HEAD")
    real_run = rp.Git.run
    moved = {"done": False}

    def racing(self: rp.Git, *args: str, check: bool = True,
               env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("push",) and args[-1].endswith(":refs/heads/master") and not moved["done"]:
            moved["done"] = True
            other = world["origin"].parent / "other"
            _g(origin.parent, "clone", "-q", "-b", "master", str(origin), str(other))
            _commit(other, {"README": "someone else\n"}, "concurrent master commit")
            _g(other, "push", "-q", "origin", "HEAD:refs/heads/master")
        return real_run(self, *args, check=check, env=env)

    monkeypatch.setattr(rp.Git, "run", racing)
    res = rp.promote(dev, tested, _ev(tested))
    assert any("rejected (attempt 1)" in n for n in res.notes)
    master = _remote(origin, "refs/heads/master")
    assert master == res.master_after
    assert _g(origin, "rev-parse", f"{master}^{{tree}}") == _g(origin, "rev-parse",
                                                                 f"{tested}^{{tree}}")


def test_promote_cli_reports_refusal_as_json(world: dict[str, Path],
                                             capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    dev = world["dev"]
    tested = _g(dev, "rev-parse", "HEAD")
    untested = _commit(dev, {"libs/c.py": "C = 1\n"}, "untested")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    rc = cli.main(["promote", "--root", str(dev), "--target", untested, "--tested", tested])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    rc = cli.main(["promote", "--root", str(dev), "--target", tested, "--tested", tested,
                   "--run-id", "9"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["production_after"] == tested


# ------------------------------------------------------------------------- the box's gate
@pytest.fixture
def box(world: dict[str, Path]) -> Path:
    box = world["origin"].parent / "box"
    _g(world["origin"].parent, "clone", "-q", "-b", LIVE, str(world["origin"]), str(box))
    return box


def test_gate_without_any_release_holds_untested_code(world: dict[str, Path],
                                                         box: Path) -> None:
    d = rp.gate(box)
    assert d.decision == "HOLD" and d.target is None
    assert "no production pointer" in d.reason


def test_unverifiable_release_diff_never_adopts_the_tip() -> None:
    class BrokenDiff:
        def changed(self, before: str, after: str) -> list[str]:
            raise rp.GitError("object unavailable")

    d = rp.adoption_decision(BrokenDiff(), tip="b" * 40, release_sha="a" * 40,
                             release_ref="production", head="c" * 40)  # type: ignore[arg-type]
    assert d.decision == "HOLD" and d.target is None
    assert "unverified" in d.reason


def test_gate_adopts_a_tip_that_is_the_release_plus_state(world: dict[str, Path],
                                                          box: Path) -> None:
    dev = world["dev"]
    rel = _g(dev, "rev-parse", "HEAD")
    rp.promote(dev, rel, _ev(rel))
    tip = _commit(dev, {"desks/mt5/data/state.json": "{\"n\": 2}\n",
                        "desks/mt5/data/RELEASE.json": "{}\n"}, "box state + seal")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    d = rp.gate(box)
    assert (d.decision, d.target, d.release_ref) == ("ADOPT_TIP", tip, "production")


def test_gate_adopts_the_release_not_an_untested_tip(world: dict[str, Path], box: Path) -> None:
    dev = world["dev"]
    rel = _commit(dev, {"libs/a.py": "A = 5\n"}, "released code")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    rp.promote(dev, rel, _ev(rel))
    tip = _commit(dev, {"libs/a.py": "A = 6\n"}, "not yet green")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    d = rp.gate(box)                                     # box HEAD is the live root
    assert (d.decision, d.target) == ("ADOPT_RELEASE", rel)
    assert d.unreleased_code == ["libs/a.py"] and d.tip == tip
    _g(box, "merge", "-q", "--ff-only", rel)             # the box took the release
    held = rp.gate(box)
    assert (held.decision, held.target) == ("HOLD", None) and "waiting for CI" in held.reason
    # the escape hatch, by file and by flag
    flag = box / rp.OVERRIDE_FLAG_REL
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("principal: CI is down, land the fix\n", encoding="utf-8")
    over = rp.gate(box)
    assert (over.decision, over.target) == ("OVERRIDE_TIP", tip)
    flag.unlink()
    assert rp.gate(box, allow_unreleased=True).decision == "OVERRIDE_TIP"


def test_gate_falls_back_to_the_newest_release_tag(world: dict[str, Path], box: Path) -> None:
    dev, origin = world["dev"], world["origin"]
    rel = _g(dev, "rev-parse", "HEAD")
    rp.promote(dev, rel, _ev(rel))
    _g(origin, "update-ref", "-d", "refs/heads/production")
    _commit(dev, {"libs/a.py": "A = 7\n"}, "untested")
    _g(dev, "push", "-q", "origin", f"HEAD:refs/heads/{LIVE}")
    d = rp.gate(box)                                     # box already runs `rel`
    assert d.release_ref is not None and d.release_ref.startswith("release/")
    assert (d.release_sha, d.decision) == (rel, "HOLD")


def test_gate_cli_emits_json_and_exits_3_when_it_cannot_decide(
        box: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
    assert cli.main(["gate", "--root", str(box)]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "HOLD"
    report = box / "desks" / "mt5" / "reports" / "RELEASE_GATE.json"
    assert json.loads(report.read_text(encoding="utf-8"))["decision"] == "HOLD"
    assert cli.main(["gate", "--root", str(box), "--remote", "nowhere"]) == 3
    doc = json.loads(capsys.readouterr().out)
    assert doc["decision"] == "ERROR" and doc["adopts"] is False
    assert json.loads(report.read_text(encoding="utf-8"))["decision"] == "ERROR"


# ---------------------------------------------------------------------------- the wiring
def _job(text: str, name: str) -> str:
    start = text.index(f"\n  {name}:\n")
    m = re.search(r"\n  [a-z0-9-]+:\n", text[start + 3:])
    return text[start:start + 3 + m.start()] if m else text[start:]


def test_ci_promotes_only_green_live_pushes_and_never_forces() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    promote = _job(ci, "promote")
    assert "needs: [quality, mt5-money-path, coverage-floor, seal]" in promote
    assert "github.event_name == 'push'" in promote
    assert f"github.ref == 'refs/heads/{LIVE}'" in promote
    assert "python scripts/release_promotion.py promote" in promote
    assert "needs.seal.outputs.release_commit" in promote
    assert "needs.quality.outputs.law_gate" in promote
    assert "needs.quality.outputs.suite" in promote
    assert "needs.mt5-money-path.outputs.suite" in promote
    assert "--force" not in promote and " -f " not in promote
    seal = _job(ci, "seal")
    assert "needs: [quality, mt5-money-path, coverage-floor]" in seal
    # the seal step is reused, not duplicated, and it now says which commit it released
    assert ci.count("release_manifest.py --seal") == 2           # first seal + retry re-seal
    assert "release_commit=" in seal
    assert "release_manifest.py" not in promote
    for job in ("quality", "mt5-money-path"):
        body = _job(ci, job)
        assert "--junitxml=" in body and "release_promotion.py counts" in body, job


def test_shared_coverage_uses_both_complete_suites_without_lowering_floors() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    quality, desk = _job(ci, "quality"), _job(ci, "mt5-money-path")
    combined = _job(ci, "coverage-floor")
    assert "--cov=libs" in quality and "--cov=libs" in desk
    for body in (quality, desk):
        assert "--cov-branch" in body
        assert "include-hidden-files: true" in body
        assert "if-no-files-found: error" in body
    assert "needs: [quality, mt5-money-path]" in combined
    assert "root-coverage-${{ github.sha }}" in combined
    assert "desk-coverage-${{ github.sha }}" in combined
    assert ("coverage combine coverage-input/root/.coverage "
            "coverage-input/desk/.coverage") in combined
    assert "coverage json --include='libs/*'" in combined
    assert "check_coverage_floors.py --report coverage.json" in combined
    assert "--update" not in combined
    assert "check_mt5_coverage_floor.py --report mt5cov.json" in desk


def test_raw_branch_coverage_artifacts_combine_by_executed_arcs(tmp_path: Path) -> None:
    from coverage import Coverage, CoverageData

    source = str(ROOT / "libs/ops/release_promotion.py")
    inputs = []
    for suite, arcs in (("root", [(-1, 1), (1, 2)]), ("desk", [(-1, 1), (1, 3)])):
        directory = tmp_path / suite
        directory.mkdir()
        path = directory / ".coverage"
        raw = CoverageData(basename=str(path))
        raw.add_arcs({source: arcs})
        raw.write()
        inputs.append(str(path))
    combined = Coverage(data_file=str(tmp_path / ".coverage"), config_file=False, branch=True)
    combined.combine(data_paths=inputs, strict=True)
    assert combined.get_data().has_arcs()
    assert set(combined.get_data().arcs(source) or []) == {(-1, 1), (1, 2), (1, 3)}


def test_the_box_adopts_only_through_the_release_gate() -> None:
    s = (ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1").read_text(encoding="utf-8")
    gate_at = s.index("release_promotion.py")
    adopt_at = s.index("@adoptArgs 2>&1")
    assert gate_at < adopt_at
    assert '"gate"' in s and "--allow-unreleased" in s
    assert "-Target" in s and "-NoFetch" in s
    assert "held-awaiting-release" in s


def test_windows_launcher_never_converts_gate_failure_to_tip_authority() -> None:
    s = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text("utf-8")
    for failure in ("release-gate-error", "release-gate-absent", "release-gate-invalid"):
        assert f'Done 8 "{failure}"' in s
    assert '$adoptArgs += @("-Target", $gateTarget, "-NoFetch")' in s
    assert "falling back to adopting the branch tip" not in s
    assert '"ADOPT_TIP", "ADOPT_RELEASE", "OVERRIDE_TIP"' in s
    r = (ROOT / "desks" / "mt5" / "scripts" / "Adopt-Release.ps1").read_text(encoding="utf-8")
    assert "[string] $Target" in r
