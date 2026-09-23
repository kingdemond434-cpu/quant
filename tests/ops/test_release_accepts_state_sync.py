"""The release fence accepts an hourly state-sync commit and still refuses code drift.

MEASURED 2026-09-08 in the gateway log, once a minute, for the whole day:

    RELEASE IDENTITY refuses NEW risk: running 92480baa4c66 carries 83 path(s) the sealed
    release ca12b75a8a7f never named: ['desks/mt5/data/cross_asset_anchors.pkl',
    'desks/mt5/data/decay_live.json', 'desks/mt5/data/forward_reconcile.json', ...]

Every named path is evidence under desks/mt5/data/, committed by the hourly sync BY DESIGN.
`accepts()` treated anything outside its short enumerated allowlist as code, so a seal could
not survive the next sync. The fence's own docstring promised the opposite: "a seal commit or a
state-sync commit on top of the sealed code is the same release".

The governed files under those directories -- canon, immutable manifest, sleeve registry,
RELEASE.json -- are each held to their own hash in `verify()`, so the SHA check may classify
the DIRECTORY as state without losing anything. These tests pin both halves.
"""
from __future__ import annotations

import pytest

from libs.ops import release

SEALED = "ca12b75a8a7f" + "0" * 28
RUNNING = "92480baa4c66" + "0" * 28
REC = {"code_sha": SEALED}


def _diff(monkeypatch, paths: list[str]) -> None:
    monkeypatch.setattr(release, "_git", lambda args, root: "\n".join(paths))


# ------------------------------------------------------------- the day's refusal, now accepted
def test_the_measured_refusal_is_now_an_acceptance(monkeypatch) -> None:
    _diff(monkeypatch, [
        "desks/mt5/data/cross_asset_anchors.pkl",
        "desks/mt5/data/decay_live.json",
        "desks/mt5/data/forward_reconcile.json",
        "desks/mt5/data/hypotheses/coverage_search_results.json",
        "desks/mt5/data/hypotheses/edge_search_results.json",
        "desks/mt5/data/hypotheses/gauntlet_build_cursor.json",
    ])
    ok, why, code = release.accepts(RUNNING, REC)
    assert ok, why
    assert code == []
    assert "only by 6 seal/state path(s)" in why


def test_eighty_three_state_paths_are_summarised_not_dumped(monkeypatch) -> None:
    _diff(monkeypatch, [f"desks/mt5/data/hypotheses/f{i}.json" for i in range(83)])
    ok, why, _ = release.accepts(RUNNING, REC)
    assert ok
    assert "83 seal/state path(s)" in why and why.endswith("...")


@pytest.mark.parametrize("path", [
    "desks/mt5/reports/pf_allocation.json",
    "desks/mt5/logs/gateway_20260908.log",
    "web/desk_state.json",
    "docs/BOOK_E8_MEASURED.md",
    "data/miner_conversion.json",
    "reports/shadow_health.json",
])
def test_each_state_directory_is_state(path: str, monkeypatch) -> None:
    _diff(monkeypatch, [path])
    ok, _, code = release.accepts(RUNNING, REC)
    assert ok and code == [], path


def test_windows_separators_and_dot_slash_are_normalised() -> None:
    assert release.is_state_path("desks\\mt5\\data\\decay_live.json")
    assert release.is_state_path("./desks/mt5/data/decay_live.json")


# ---------------------------------------------------------------- code drift is STILL refused
@pytest.mark.parametrize("path", [
    "desks/mt5/mt5desk/gateway.py",
    "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/research/sleeve_registry.py",
    "libs/portfolio/allocator_proof.py",
    "desks/mt5/scripts/external_gauntlet.py",
])
def test_a_money_or_research_module_still_refuses(path: str, monkeypatch) -> None:
    _diff(monkeypatch, ["desks/mt5/data/decay_live.json", path])
    ok, why, code = release.accepts(RUNNING, REC)
    assert not ok
    assert code == [path]
    assert "never named" in why


def test_a_state_looking_name_outside_a_state_directory_is_code() -> None:
    """The prefix is the classification, not the extension: a .json at the repo root that is
    not under data/ or reports/ is not waved through."""
    assert not release.is_state_path("desk_manifest.yaml")
    assert not release.is_state_path("alpha_pipeline.json")
    assert not release.is_state_path("desks/mt5/mt5desk/config.json")


# ------------------------------------------------- the governed state files keep their own hash
def test_the_governed_files_under_data_are_still_hashed_by_verify() -> None:
    """Classifying desks/mt5/data/ as state for the SHA check is only safe because these are
    caught elsewhere. If one leaves the hashed set, this fails and the classification must be
    revisited."""
    assert release.SURVIVORS.startswith("desks/mt5/data/")
    assert release.IMMUTABLE_MANIFEST.startswith("desks/mt5/data/")
    assert release.RELEASE_REL.startswith("desks/mt5/data/")
    from pathlib import Path
    src = Path(release.__file__).read_text(encoding="utf-8")
    assert '"survivor_registry_hash"' in src
    assert '"immutable_manifest"' in src


def test_the_exact_equality_and_unknown_cases_are_unchanged(monkeypatch) -> None:
    ok, why, _ = release.accepts(SEALED, REC)
    assert ok and "running the sealed commit" in why
    ok, why, _ = release.accepts("unknown", REC)
    assert not ok and "unmeasured" in why
    ok, why, _ = release.accepts(RUNNING, {})
    assert not ok and "names no code_sha" in why


# ----------------------------------------------------- a seal on the box, between two syncs
def _repo(tmp_path):
    import subprocess

    repo = tmp_path / "box"
    repo.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@t"),
                 ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    (repo / "libs").mkdir()
    (repo / "libs" / "x.py").write_text("code = 1\n")
    (repo / "desks" / "mt5" / "data").mkdir(parents=True)
    (repo / "desks" / "mt5" / "data" / "ledger.json").write_text("[1]\n")
    subprocess.run(["git", "-C", str(repo), "add", "--", "libs/x.py",
                    "desks/mt5/data/ledger.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "base"], check=True)
    return repo


def test_dirty_paths_can_leave_state_out(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "data" / "ledger.json").write_text("[1, 2]\n")
    (repo / "libs" / "x.py").write_text("code = 2\n")
    assert release.dirty_paths(repo) == ["desks/mt5/data/ledger.json", "libs/x.py"]
    assert release.dirty_paths(repo, code_only=True) == ["libs/x.py"]


def test_a_seal_is_not_refused_by_the_ledger_an_organ_rewrote_a_minute_ago(tmp_path) -> None:
    """On the box every organ rewrites its artifact between syncs, so a tracked state path is
    dirty for most of every hour by design. The unattended seal never succeeded once because of
    it. The seal hashes HEAD's blobs; the dirt is recorded, never hidden."""
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "data" / "ledger.json").write_text("[1, 2]\n")
    doc = release.seal(root=repo, by="test", write=False)
    assert doc["sealed"] is True
    assert doc["worktree_dirty"] == ["desks/mt5/data/ledger.json"]


def test_a_seal_still_refuses_a_dirty_code_path(tmp_path) -> None:
    repo = _repo(tmp_path)
    (repo / "libs" / "x.py").write_text("code = 2\n")
    with pytest.raises(RuntimeError, match=r"1 tracked code path\(s\)"):
        release.seal(root=repo, by="test", write=False)
    doc = release.seal(root=repo, by="test", write=False, allow_dirty=True)
    assert doc["worktree_dirty"] == ["libs/x.py"]
