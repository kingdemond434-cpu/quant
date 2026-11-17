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


def test_no_clear_a_hold_a_moved_head_or_a_young_window_waits(monkeypatch):
    monkeypatch.setattr(mg.ag, "REGISTRY_HOLD_H", 24.0)  # the window, whatever LIVE sets
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


def test_paper_only_paths_pass_only_while_they_stay_paper_only():
    """Governance 2026-11-17: a name-caught file that cannot reach a key, the box's state or a
    remote endpoint is not on the fence; the moment a changed line reaches one, it is again."""
    health = "deploy/windows/memecoin-health.ps1"
    scoring = "src/strategies/wallet_intelligence.py"
    # read-only reporting of the switch, a loopback GET, a stderr drop: paper-only
    for line in (
        "+ $h=[ordered]@{ok=$true;dry_run=$j.dry_run;live_locked=$j.live_submission_locked}",
        "+ $raw=& curl.exe -s --noproxy '*' -m 10 (\"http://127.0.0.1:$port/health\") 2>$null",
        "+ $t=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue",
    ):
        assert _decide(files=_files((health, line)))[0] == "merge", line
    assert (
        _decide(files=_files((scoring, "+        rate = prior.shrink(hits, trials)")))[0] == "merge"
    )
    # ...and fenced the moment it writes, starts, sets, signs, reads a key or leaves loopback
    for line in (
        "+[IO.File]::WriteAllText($p,$json)",
        "+$json > C:\\opt\\memecoin\\config.json",
        "+Set-Content -Path x -Value y",
        "+Start-ScheduledTask -TaskName MemecoinShadowCodex",
        "+Stop-Process -Id 1",
        "+$env:ALLOW_LIVE_TRADING='1'",
        "+setx /M ALLOW_LIVE_TRADING 1",
        "+iex $payload",
        "+curl.exe https://api.mainnet-beta.solana.com",
        "+$k = Get-Content id.json",
    ):
        assert _decide(files=_files((health, line)))[0] == "zuck", line
    for line in (
        "+    dry_run = False",  # LIVE_WORDS still binds a .py on the list
        "+    kp = Keypair.from_base58_string(raw)",
        "+    key = load_private_key()",
        "+    sig = signer.sign(msg)",
        "+    r = requests.post(url)",
        "+    os.environ['X'] = '1'",
        "+    RPC_URL = 'https://x'",
    ):
        assert _decide(files=_files((scoring, line)))[0] == "zuck", line


def test_the_exception_is_by_exact_name_and_in_place_only():
    # a real wallet or keypair file, a sibling deploy script, a near-miss name: still fenced
    for path in (
        "src/wallet.py",
        "data/wallet.json",
        "src/strategies/wallet_signer.py",
        "deploy/windows/start-cpu-bounded.ps1",
        "deploy/windows/memecoin-health2.ps1",
    ):
        assert _decide(files=_files((path, "+x = 1")))[0] == "zuck", path
    # renaming a fenced file ONTO an exempt name, or away from it, is fenced
    onto = [
        {
            "filename": "src/strategies/wallet_intelligence.py",
            "previous_filename": "src/execution/signer.py",
            "patch": "",
            "changes": 0,
            "status": "renamed",
        }
    ]
    away = [
        {
            "filename": "src/x.py",
            "previous_filename": "deploy/windows/memecoin-health.ps1",
            "patch": "",
            "changes": 0,
            "status": "renamed",
        }
    ]
    assert _decide(files=onto)[0] == "zuck"
    assert _decide(files=away)[0] == "zuck"
    # a removed exempt file is read as the path it is
    gone = [
        {
            "filename": "deploy/windows/memecoin-health.ps1",
            "patch": "-x",
            "changes": 1,
            "status": "removed",
        }
    ]
    assert _decide(files=gone)[0] == "zuck"


def test_docs_may_name_the_switch_but_code_and_fenced_docs_may_not():
    line = "+| 1 | promotion bar | PRESENT | `src/research/promotion_gate.py` |"
    assert _decide(files=_files(("docs/QUANT_PORT_LEDGER.md", line)))[0] == "merge"
    assert _decide(files=_files(("README.md", line)))[0] == "zuck"
    assert _decide(files=_files(("docs/tool.py", line)))[0] == "zuck"
    assert _decide(files=_files(("src/notes.md", "+dry_run = False")))[0] == "zuck"
