"""Boot r19: a replay-shadow or risk-invariants red keeps its whole output (#127, 11-26 21:35Z).

The forge status holds a 160-character tail; #127's was cut mid-JSON and its report was deleted, so
the reason could not be recovered on the box.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_loop as L  # noqa: E402


def _cfg(tmp: Path) -> L.Config:
    return L.Config(forge_url="https://127.0.0.1", bare=tmp / "bare", work=tmp / "work",
                    tokens=tmp / "tok", ca=tmp / "ca", state=tmp / "ci" / "state.json")


def test_a_replay_red_keeps_its_output_and_report(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    cfg.work.mkdir(parents=True)

    @contextlib.contextmanager
    def wt(c: L.Config, sha: str):
        d = tmp_path / sha
        d.mkdir(exist_ok=True)
        yield d

    def run(c: L.Config, argv, **k):
        Path(argv[argv.index("--report") + 1]).write_text('{"divergences": ["sleeves"]}')
        return 1, "x" * 5000 + "\nFAIL: undeclared divergence in sleeves"

    monkeypatch.setattr(L, "worktree", wt)
    monkeypatch.setattr(L, "_run_untrusted", run)
    head = "79af9260ed8a9d8f8a67a09cd06afd62363748eb"
    ok, why = L.replay_job(cfg, "a" * 40, head, ["desks/mt5/x.py"])
    assert not ok and "ci_logs/replay-79af9260ed8a.log" in why
    log = (tmp_path / "ci" / "ci_logs" / "replay-79af9260ed8a.log").read_text()
    assert "x" * 5000 in log and '"divergences": ["sleeves"]' in log
    assert not (cfg.work / f"replay_{head[:12]}.json").exists()   # scratch report still removed


def test_a_log_that_cannot_be_written_never_changes_the_verdict(tmp_path: Path,
                                                                monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    cfg.work.mkdir(parents=True)

    @contextlib.contextmanager
    def wt(c: L.Config, sha: str):
        yield tmp_path

    monkeypatch.setattr(L, "worktree", wt)
    monkeypatch.setattr(L, "_run_untrusted", lambda c, argv, **k: (0, "replay ok"))
    monkeypatch.setattr(L, "keep_log", lambda *a: None)
    ok, why = L.replay_job(cfg, "a" * 40, "b" * 40, [])
    assert ok and why == "replay-shadow rc=0: replay ok"
