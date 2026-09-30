"""No implicit stash, in any scope: the fence for the half of R0423 nothing could grep."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _by_path(name: str, path: Path) -> ModuleType:
    """Load BY PATH, never by `from scripts import ...`.

    `tests/scripts/__init__.py` makes `scripts` a real package, which shadows the repo-root
    namespace package of the same name without a word -- the identical trap
    `plumbing_watchdog._load_by_path` exists for.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ca = _by_path("check_autostash_under_test", ROOT / "scripts" / "check_autostash.py")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo with the ambient global/system config neutralised.

    GIT_CONFIG_GLOBAL / GIT_CONFIG_SYSTEM point git at files of our choosing, so the test never
    reads -- or depends on -- whatever the developer or the box has configured.
    """
    (tmp_path / "empty_global").write_text("", "utf-8")
    (tmp_path / "empty_system").write_text("", "utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty_global"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "empty_system"))
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q")
    _git(work, "config", "user.email", "fence@example.invalid")
    _git(work, "config", "user.name", "fence")
    (work / "a.txt").write_text("one\n", "utf-8")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-q", "-m", "first")
    return work


def test_unset_passes_and_says_it_is_unpinned(repo: Path) -> None:
    doc = ca.scan(repo)
    assert doc["ok"], doc["problems"]
    assert doc["measured"] is True
    assert doc["effective"]["merge.autoStash"] is None
    assert doc["effective"]["rebase.autoStash"] is None
    # git's own default is false, so this is safe -- but it must be SAID, because the measured
    # history of this class is that config drifts back and nobody notices an absent line.
    assert any("UNPINNED" in n for n in doc["notes"])
    assert any("--pin" in n for n in doc["notes"])


@pytest.mark.parametrize("key", ["merge.autoStash", "rebase.autoStash"])
def test_true_in_local_scope_fails_and_names_the_file(repo: Path, key: str) -> None:
    _git(repo, "config", "--local", key, "true")
    doc = ca.scan(repo)
    assert not doc["ok"]
    assert any(key in p and "TRUE" in p for p in doc["problems"]), doc["problems"]
    # The verdict is unactionable until it names the scope AND the file to edit.
    assert any(r["true"] and r["scope"] == "local" and r["origin"] for r in doc["scopes"])
    assert any("git config --local" in p for p in doc["problems"])


def test_a_true_a_narrower_scope_overrides_still_fails(repo: Path, tmp_path: Path) -> None:
    """THE PROPERTY THE EFFECTIVE VALUE CANNOT SEE.

    global says true, local says false, so git's effective answer is false and a fence that read
    only the effective value would pass. It is one fresh clone, one `git -C` elsewhere, or one
    deleted local line away from stashing 21,884 live paths -- so a true in ANY scope fails.
    """
    (tmp_path / "empty_global").write_text("[merge]\n\tautostash = true\n", "utf-8")
    _git(repo, "config", "--local", "merge.autoStash", "false")

    doc = ca.scan(repo)
    assert doc["effective"]["merge.autoStash"] == "false", "the effective value is genuinely false"
    assert not doc["ok"], "a true in a wider scope is still a reachable implicit stash"
    assert any(r["true"] and r["scope"] == "global" for r in doc["scopes"]), doc["scopes"]


def test_a_valueless_key_counts_as_true(repo: Path, tmp_path: Path) -> None:
    """`[merge]\\n autostash` with no value is TRUE to git, and must be TRUE to the fence."""
    (tmp_path / "empty_global").write_text("[merge]\n\tautostash\n", "utf-8")
    doc = ca.scan(repo)
    assert not doc["ok"], doc["scopes"]
    assert any(r["true"] for r in doc["scopes"])


def test_a_stash_entry_fails_and_is_never_dropped(repo: Path) -> None:
    (repo / "a.txt").write_text("two\n", "utf-8")
    _git(repo, "stash", "push", "-q", "-m", "wreckage")
    doc = ca.scan(repo)
    assert not doc["ok"]
    assert doc["stash"]["n"] == 1
    assert any("stash entry" in p for p in doc["problems"]), doc["problems"]
    # THE FENCE REPORTS, IT DOES NOT REPAIR BY REMOVING. Dropping a stash is exactly the
    # "acting on an absence" LAWS 7 refuses -- the parked state may be the only copy.
    after = subprocess.run(["git", "stash", "list"], cwd=repo, capture_output=True, text=True)
    assert after.stdout.strip(), "the fence must not drop the stash it reports"


def test_pin_sets_both_false_and_the_rescan_is_clean(repo: Path) -> None:
    _git(repo, "config", "--local", "merge.autoStash", "true")
    assert not ca.scan(repo)["ok"]
    done = ca.pin(repo)
    assert len(done) == 2 and all("set" in d for d in done), done
    doc = ca.scan(repo)
    assert doc["ok"], doc["problems"]
    assert doc["effective"]["merge.autoStash"] == "false"
    assert doc["effective"]["rebase.autoStash"] == "false"


def test_an_unmeasurable_host_fails_rather_than_passing(repo: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """A fence that cannot prove the law holds must not claim it does (L1.28a / L1.37)."""
    monkeypatch.setattr(ca, "_git", lambda *a, **k: (-1, ""))
    doc = ca.scan(repo)
    assert not doc["ok"]
    assert doc["measured"] is False
    assert any("UNMEASURED" in p for p in doc["problems"])


def test_the_fence_is_registered_in_the_law_gate_battery() -> None:
    """UNWIRED IS A DEFECT (III.16). A fence nothing runs protects nothing."""
    run_law_gate = _by_path("run_law_gate_under_test", ROOT / "scripts" / "run_law_gate.py")

    names = {n for n, _a in (*run_law_gate._LAW_FENCES, *run_law_gate._STATE_FENCES)}
    assert "check_autostash.py" in names
    # Portable half: it reads git's own config, so it must gate the COMMIT and the PUSH, where a
    # drifted config is already dangerous -- not only an hourly clock.
    assert "check_autostash.py" in {n for n, _a in run_law_gate._LAW_FENCES}
