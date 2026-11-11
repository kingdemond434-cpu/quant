"""The memecoin auto-merge path: CLEAR + green + window merges; the live switch never does."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "memecoin_gate", ROOT / ".github" / "scripts" / "memecoin_gate.py"
)
assert _spec and _spec.loader
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
HEAD = "a" * 40


def _pr(**kw):
    return {"number": 143, "draft": False, "base": {"ref": "main"}, "head": {"sha": HEAD}, **kw}


def _files(*items):
    return [{"filename": f, "patch": p, "changes": 1} for f, p in items]


GREEN = [
    {"name": j, "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"}}
    for j in mg.REQUIRED_JOBS
]
ROW = [{"pr": 143, "sha": HEAD, "verdict": "CLEAR", "at": (NOW - timedelta(hours=30)).isoformat()}]


def _old_window():
    return NOW - timedelta(hours=25), ""


def _decide(files=None, runs=GREEN, behind=0, rows=ROW, window=_old_window, pr=None):
    return mg.decide(
        pr or _pr(), files or _files(("ops/health.py", "+x = 1")), runs, behind, rows, window, NOW
    )


def test_a_cleared_green_current_change_past_its_window_merges():
    assert _decide()[0] == "merge"


def test_the_live_switch_is_zucks_by_path_and_by_word():
    for path in (
        "config/chains.yaml",
        ".github/workflows/ci.yml",
        "src/execution/signer.py",
        "deploy/systemd/memecoin-health.service",
        "src/research/promotion_gate.py",
    ):
        assert _decide(files=_files((path, "+x = 1")))[0] == "zuck", path
    for line in (
        "+    dry_run = False",
        "-ALLOW_LIVE_TRADING=1",
        "+stage = Stage.CANARY",
        "+from src.execution import signer",
    ):
        assert _decide(files=_files(("src/main.py", line)))[0] == "zuck", line
    # a rename OUT of a fenced path is fenced too
    moved = [
        {
            "filename": "src/x.py",
            "previous_filename": "src/execution/jupiter_jito.py",
            "patch": "",
            "changes": 0,
        }
    ]
    assert _decide(files=moved)[0] == "zuck"


def test_the_audited_bypasses_are_all_zucks():
    for line in (
        '+    mode.add_argument("--live", action="store_true", default=True)',
        '+os.environ["ALLOW_"+"LIVE_TRADING"]="yes-"+"i-understand"',
        '+os.environ.setdefault("X", "1")',
        "+    dry_override = False",
        "+    if champion_challenger.is_live:",
        "+        tx.sign(&[&kp], blockhash)?;",
    ):
        assert _decide(files=_files(("src/main.py", line)))[0] == "zuck", line
    for path in (
        "native/solana_fastpath/src/transaction.rs",
        "native/solana_fastpath/Cargo.toml",
        "Cargo.lock",
        "pyproject.toml",
        "requirements-dev.txt",
        "setup.py",
        "dashboard/web/package.json",
        "native/solana_fastpath/pyproject.toml",
    ):
        assert _decide(files=_files((path, "+x = 1")))[0] == "zuck", path


def test_a_binary_file_without_a_patch_fails_closed_but_a_pure_rename_passes():
    assert (
        _decide(
            files=[{"filename": "assets/x.bin", "patch": None, "changes": 0, "status": "modified"}]
        )[0]
        == "zuck"
    )
    rename = [
        {
            "filename": "docs/b.md",
            "previous_filename": "docs/a.md",
            "patch": None,
            "changes": 0,
            "status": "renamed",
        }
    ]
    assert _decide(files=rename)[0] == "merge"


def test_a_check_named_like_a_required_job_from_another_app_does_not_count():
    forged = [{**r, "app": {"slug": "some-app"}} for r in GREEN]
    assert _decide(runs=forged)[0] == "wait"


def test_an_unreadable_patch_or_empty_list_fails_closed():
    assert _decide(files=[{"filename": "src/big.py", "patch": None, "changes": 9}])[0] == "zuck"
    assert mg.fenced([]) is not None


def test_no_clear_a_hold_a_moved_head_or_a_young_window_waits():
    assert _decide(rows=[])[0] == "wait"
    hold = [*ROW, {"pr": 143, "sha": HEAD, "verdict": "HOLD", "at": NOW.isoformat()}]
    assert _decide(rows=hold)[0] == "wait"
    assert _decide(rows=[{**ROW[0], "sha": "b" * 40}])[0] == "wait"
    assert _decide(window=lambda: (NOW - timedelta(hours=2), ""))[0] == "wait"
    assert _decide(window=lambda: (None, "notice not delivered"))[0] == "wait"


def test_red_running_or_missing_ci_waits():
    red = [*GREEN[:2], {"name": "rust", "status": "completed", "conclusion": "failure"}]
    assert _decide(runs=red)[0] == "wait"
    running = [*GREEN, {"name": "extra", "status": "in_progress", "conclusion": None}]
    assert _decide(runs=running)[0] == "wait"
    assert _decide(runs=GREEN[:2])[0] == "wait"


def test_behind_is_brought_up_and_unknown_waits_and_drafts_wait():
    assert _decide(behind=3)[0] == "bring_up"
    assert _decide(behind=None)[0] == "wait"
    assert _decide(pr=_pr(draft=True))[0] == "wait"
    assert _decide(pr=_pr(base={"ref": "dev"}))[0] == "wait"


def test_its_merge_title_is_one_auto_revert_recognises():
    import audit_gate as ag

    assert ag.is_registry_merge(f"Merge #143: {ag.REGISTRY_TITLE} {HEAD[:9]}")


def test_off_the_box_or_without_a_registry_it_does_nothing(monkeypatch):
    monkeypatch.delenv(mg.MEMECOIN_REGISTRY_ENV, raising=False)
    assert mg.main(["--box"]) == 0
    monkeypatch.setenv(mg.MEMECOIN_REGISTRY_ENV, "x")
    assert mg.main([]) == 0
