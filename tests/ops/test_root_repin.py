"""THE ROOT RE-PIN SERVICE (repin.py, SEALED): it re-pins only the released, adopted tree after
a ROOT-path merge it re-verifies, logs both digests, alerts, and clears ROOT_INFLIGHT; anything
else pins nothing and keeps the ROOT path off. Run against a real throwaway git repository."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "ops/release/authority"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rp_mod = _load("repin_t", AUTH / "repin.py")
T_MERGE = datetime(2026, 11, 15, 12, tzinfo=UTC)


def _git(repo: Path, *args: str, when: datetime | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
    if when is not None:
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = when.isoformat()
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True, env=env).stdout.strip()  # fmt: skip


def _put(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class Box:
    """A live tree with LIVE history: base -> ROOT PR merged by the gate -> release seal."""

    def __init__(
        self,
        tmp: Path,
        change: str = ".github/scripts/audit_gate.py",
        title: str = "Merge #41 (registry CLEAR 1111, ROOT path, from the box)",
    ) -> None:
        self.live = tmp / "live"
        self.reg = tmp / "registry"
        self.reg.mkdir()
        r = self.live
        r.mkdir()
        _git(r, "init", "-q", "-b", "live")
        for rel in ("ops/release/authority/policy.py", "ops/release/authority/ROOT_POLICY.json",
                    "ops/release/authority/root_path.py"):  # fmt: skip
            _put(r, rel, (ROOT / rel).read_text("utf-8"))
        _put(r, ".github/scripts/audit_gate.py", "REGISTRY_HOLD_H = 24.0\nX = 1\n")
        _put(r, "scripts/check_immutable_evaluator.py", "pass\n")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", "base", when=T_MERGE - timedelta(days=5))
        self.base = _git(r, "rev-parse", "HEAD")
        _git(r, "checkout", "-q", "-b", "pr")
        old = (r / change).read_text("utf-8") if (r / change).exists() else ""
        _put(r, change, old + "# changed\n")
        _git(r, "commit", "-qam", "pr change", when=T_MERGE - timedelta(days=4))
        self.head = _git(r, "rev-parse", "HEAD")
        _git(r, "checkout", "-q", "live")
        _git(r, "merge", "-q", "--no-ff", "-m", title, "pr", when=T_MERGE)
        self.merge = _git(r, "rev-parse", "HEAD")
        self.release(self.merge)
        self.pin = self.reg / "ROOT_PIN.json"
        self.pin.write_text(json.dumps({"digest": rp_mod.tree_digest(rp_mod.Repo(r), self.base)}))
        (self.reg / "ROOT_INFLIGHT.json").write_text(json.dumps({"pr": 41, "head": self.head}))
        self.notice(T_MERGE - timedelta(hours=73))
        self.alerts: list[str] = []

    def release(self, sha: str) -> None:
        _put(self.live, "desks/mt5/data/RELEASE.json", json.dumps({"code_sha": sha}))

    def notice(self, at: datetime, head: str | None = None, receipt: str = "delivered 1") -> None:
        rec = {"head": head or self.head, "at": at.isoformat(), "receipt": receipt}
        (self.reg / "root_window.json").write_text(json.dumps({"41": rec}))

    def run(self) -> int:
        return int(rp_mod.run(self.reg, self.live, self.pin, None, T_MERGE + timedelta(hours=1)))

    def log(self) -> list[dict[str, Any]]:
        p = self.reg / "repin.log.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


@pytest.fixture(autouse=True)
def _need_git() -> None:
    if shutil.which("git") is None:
        pytest.skip("git not installed")


def test_a_root_path_merge_that_was_released_and_adopted_is_re_pinned(tmp_path: Path) -> None:
    b = Box(tmp_path)
    old = json.loads(b.pin.read_text())["digest"]
    assert b.run() == 0
    pin = json.loads(b.pin.read_text())
    want = rp_mod.tree_digest(rp_mod.Repo(b.live), b.merge)
    assert pin["digest"] == want != old and pin["commit"] == b.merge and pin["by"] == "repin"
    assert pin["previous_digest"] == old and pin["merge"] == b.merge
    assert not (b.reg / "ROOT_INFLIGHT.json").exists()
    line = b.log()[-1]
    assert line["action"] == "PIN" and line["old"] == old and line["new"] == want


def test_the_digest_is_the_one_the_authority_computes(tmp_path: Path) -> None:
    b = Box(tmp_path)
    pol = _load("pol_t", AUTH / "policy.py")
    repo = rp_mod.Repo(b.live)
    names = repo.out("ls-tree", "-r", "--name-only", b.merge).splitlines()
    want = pol.root_digest(lambda n: repo.show(b.merge, n), names, pol.load_policy())
    assert rp_mod.tree_digest(repo, b.merge) == want


def _refused(b: Box, words: str) -> None:
    before = b.pin.read_text()
    assert b.run() == 2
    assert b.pin.read_text() == before and (b.reg / "ROOT_INFLIGHT.json").exists()
    assert b.log()[-1]["action"] == "REFUSE" and words in b.log()[-1]["why"]


def test_a_merge_inside_the_72h_window_is_refused(tmp_path: Path) -> None:
    b = Box(tmp_path)
    b.notice(T_MERGE - timedelta(hours=71))
    _refused(b, "72 h")


@pytest.mark.parametrize("receipt,head", [("", None), ("delivered 1", "9" * 40)])
def test_no_delivered_notice_for_that_head_is_refused(
    tmp_path: Path, receipt: str, head: str | None
) -> None:
    b = Box(tmp_path)
    b.notice(T_MERGE - timedelta(hours=80), head=head, receipt=receipt)
    _refused(b, "delivered ROOT notice")


def test_a_sealed_core_merge_is_refused(tmp_path: Path) -> None:
    b = Box(tmp_path, change="scripts/check_immutable_evaluator.py")
    _refused(b, "SEALED CORE")


def test_a_merge_not_titled_by_the_root_path_is_refused(tmp_path: Path) -> None:
    b = Box(tmp_path, title="Merge #41 (merge): audit CLEAR 1111")
    _refused(b, "no ROOT-path merge")


def test_another_root_change_after_the_merge_is_refused(tmp_path: Path) -> None:
    b = Box(tmp_path)
    _put(
        b.live,
        ".github/scripts/audit_gate.py",
        (b.live / ".github/scripts/audit_gate.py").read_text() + "# later\n",
    )
    _git(b.live, "commit", "-qam", "later root change", when=T_MERGE + timedelta(minutes=5))
    b.release(_git(b.live, "rev-parse", "HEAD"))
    _refused(b, "another root change")


def test_nothing_is_pinned_before_the_box_adopts_the_release(tmp_path: Path) -> None:
    b = Box(tmp_path)
    b.release(b.base)  # the release still names the tree before the merge
    before = b.pin.read_text()
    assert b.run() == 0 and b.pin.read_text() == before
    assert (b.reg / "ROOT_INFLIGHT.json").exists() and b.log()[-1]["action"] == "WAIT"
    b.release("f" * 40)  # a release the live tree does not contain
    assert b.run() == 0 and b.pin.read_text() == before and b.log()[-1]["action"] == "WAIT"


def test_no_root_merge_in_flight_changes_nothing(tmp_path: Path) -> None:
    b = Box(tmp_path)
    (b.reg / "ROOT_INFLIGHT.json").unlink()
    before = b.pin.read_text()
    assert b.run() == 0 and b.pin.read_text() == before and b.log() == []


def test_an_unreadable_inflight_record_pins_nothing(tmp_path: Path) -> None:
    b = Box(tmp_path)
    (b.reg / "ROOT_INFLIGHT.json").write_text("{not json")
    before = b.pin.read_text()
    assert b.run() == 2 and b.pin.read_text() == before


def test_the_plan_is_pure_and_fails_closed() -> None:
    rp = _load("rp_plan_t", AUTH / "root_path.py")
    base = {"inflight": {"pr": 41, "head": "h" * 40}, "release_sha": "c" * 40,
            "adopted": (True, ""), "contains_merge": True,
            "merge": ("m" * 40, int(T_MERGE.timestamp())),
            "window_rec": {"head": "h" * 40, "at": (T_MERGE - timedelta(hours=72)).isoformat(),
                           "receipt": "delivered 1"},
            "sealed": [], "digest_m": "d1", "digest_c": "d1", "old_digest": "d0"}  # fmt: skip
    assert rp_mod.plan(base, rp)[0] == "PIN"
    assert rp_mod.plan({**base, "digest_c": None}, rp)[0] == "REFUSE"
    assert rp_mod.plan({**base, "old_digest": "d1"}, rp)[0] == "CLEAR"
    assert rp_mod.plan({**base, "adopted": (False, "x")}, rp)[0] == "WAIT"
    assert rp_mod.plan({**base, "contains_merge": False, "merge": None}, rp)[0] == "WAIT"
    rec = {**base["window_rec"], "at": "2026-11-12T12:00:00"}
    assert rp_mod.plan({**base, "window_rec": rec}, rp)[0] == "REFUSE"


def test_the_installer_seals_the_copy_and_runs_it_as_system() -> None:
    ps = (AUTH / "install_repin.ps1").read_text("utf-8")
    assert '"repin.py", "root_path.py"' in ps
    assert '"Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Users:(OI)(CI)RX"' in ps
    assert 'New-ScheduledTaskPrincipal -UserId "SYSTEM"' in ps and "Quant-RootRepin" in ps
    assert "the task was NOT registered" in ps  # a dry run must pass before the task exists
    rp = _load("rp_seal_t", AUTH / "root_path.py")
    for f in ("ops/release/authority/repin.py", "ops/release/authority/install_repin.ps1"):
        assert rp.sealed_touch([f], lambda n: None, lambda n: None), f
