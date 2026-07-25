"""Regression guards for the §33 MINED-TO-WIRED checks. The gate file is the enforcement -- a
reported backlog that stops nothing is a wish, so these lock BOTH the defect and the side effect."""

from __future__ import annotations

import subprocess
from datetime import UTC
from pathlib import Path

import scripts.max_audit as m


def _mk(tmp: Path) -> Path:
    (tmp / "docs/research").mkdir(parents=True)
    (tmp / "data").mkdir(parents=True)
    return tmp / "docs/research/data_axis_watchlist.md"


def _point_at(monkeypatch, tmp: Path) -> None:
    monkeypatch.setattr(m, "ROOT", tmp)
    monkeypatch.setattr(m, "MINING_SUSPENDED", tmp / "data/mining_suspended")
    # isolate from the real repo's artifacts so credit comes only from the fixture
    monkeypatch.setattr(m, "_conversion_artifacts", lambda: [])


class TestMineConversion:
    def test_backlog_fires_and_writes_the_gate_file(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. Tardis 88 free L2 days\n### 2. Upbit +5.7y\n")
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert "mine-conversion-backlog" in [d[0] for d in defects]
        assert (tmp_path / "data/mining_suspended").exists()  # the teeth, not just the report
        assert "MINING IS SUSPENDED" in dict(defects)["mine-conversion-backlog"]

    def test_full_disposition_clears_gate_file(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text(
            "### 1. Tardis [§33: killed]\n### 2. Upbit [§33: deferred(2099-01-01)]\n")
        # a kill is only credited with its graveyard entry -- the cheap exit stays closed
        (tmp_path / "docs/graveyard.md").write_text(
            "- Tardis -- mechanism: vendor withdrew the free tier\n")
        _point_at(monkeypatch, tmp_path)
        (tmp_path / "data/mining_suspended").write_text("stale")  # left from a previous cycle
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert defects == []
        assert not (tmp_path / "data/mining_suspended").exists()  # resumes the instant it clears

    def test_unbacked_claim_fires_and_suspends(self, tmp_path: Path, monkeypatch) -> None:
        # typing "wired" must never be the cheapest way to clear a backlog
        _mk(tmp_path).write_text("### 1. Upbit KRW-BTC backfill [§33: wired]\n")
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert "mine-conversion-unbacked" in [d[0] for d in defects]
        assert (tmp_path / "data/mining_suspended").exists()

    def test_backed_claim_is_credited(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. Upbit [§33: wired]\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "MINING_SUSPENDED", tmp_path / "data/mining_suspended")
        monkeypatch.setattr(m, "_conversion_artifacts", lambda: ["upbit_krw_btc_1m"])
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert defects == []

    def test_mass_kill_without_graveyard_does_not_clear(self, tmp_path: Path, monkeypatch) -> None:
        # killing everything must cost MORE than converting it, not less
        _mk(tmp_path).write_text("".join(
            f"### {i}. find{i} [§33: killed]\n" for i in range(1, 6)))
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert "mine-conversion-unbacked" in [d[0] for d in defects]
        assert (tmp_path / "data/mining_suspended").exists()

    def test_priority_inversion_fires(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text(
            "### 1. diff-verify fence ground truth\n### 2. search operator [§33: killed]\n")
        (tmp_path / "docs/graveyard.md").write_text("- search operator -- mechanism: no signal\n")
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert "mine-conversion-inversion" in [d[0] for d in defects]

    def test_illegal_undated_deferral_fires(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. Quantopian archive [§33: deferred]\n")
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        ids = [d[0] for d in defects]
        assert "mine-conversion-illegal" in ids and "mine-conversion-backlog" in ids

    def test_no_docs_no_op(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "docs/research").mkdir(parents=True)
        (tmp_path / "data").mkdir(parents=True)
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert defects == []  # a fresh clone owes nothing

    def test_readonly_checkout_still_reports(self, tmp_path: Path, monkeypatch) -> None:
        # the gate file may be unwritable; the DEFECT must still surface
        _mk(tmp_path).write_text("### 1. Tardis\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "MINING_SUSPENDED", tmp_path / "nodir/sub/mining_suspended")
        monkeypatch.setattr(m, "_conversion_artifacts", lambda: [])
        monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError()))
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert "mine-conversion-backlog" in [d[0] for d in defects]


class TestDigUncommitted:
    def _repo(self, tmp: Path) -> Path:
        f = _mk(tmp)
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
        f.write_text("### 1. A [§33: killed]\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-qm", "x"], cwd=tmp, check=True)
        return f

    def test_committed_output_is_silent(self, tmp_path: Path, monkeypatch) -> None:
        self._repo(tmp_path)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_dig_uncommitted(defects)
        assert defects == []

    def test_edited_after_commit_fires(self, tmp_path: Path, monkeypatch) -> None:
        import os
        import time
        f = self._repo(tmp_path)
        f.write_text("### 1. A [§33: killed]\n### 2. NEW UNCOMMITTED FIND\n")
        future = time.time() + 7200  # well past the 1h skew slack
        os.utime(f, (future, future))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_dig_uncommitted(defects)
        assert defects and defects[0][0] == "dig-output-uncommitted"
        assert "DID NOT HAPPEN" in defects[0][1]

    def test_no_git_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. A\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)  # not a git repo
        defects: list[tuple[str, str]] = []
        m.check_dig_uncommitted(defects)
        assert defects == []


class TestMineFlow:
    def test_no_history_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        monkeypatch.setattr(m, "MINE_LEDGER", tmp_path / "data/led.jsonl")
        defects: list[tuple[str, str]] = []
        m.check_mine_flow(defects)
        assert defects == []  # one snapshot cannot measure flow

    def test_rotting_item_fires_and_priors_are_published(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from datetime import datetime

        from libs.research.mine_conversion import MinedItem, append_snapshot
        _mk(tmp_path)
        lg = tmp_path / "data/led.jsonl"
        old = datetime(2026, 1, 1, tzinfo=UTC)
        items = [MinedItem(source="w.md", name=f"rot{i}") for i in range(3)]
        items += [MinedItem(source="ok.md", name=f"done{i}", disposition="wired")
                  for i in range(3)]
        append_snapshot(lg, items, now=old)
        append_snapshot(lg, items)
        monkeypatch.setattr(m, "MINE_LEDGER", lg)
        monkeypatch.setattr(m, "MINE_RATCHET", tmp_path / "data/r.json")
        monkeypatch.setattr(m, "MINE_PRIORS", tmp_path / "data/p.json")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_flow(defects)
        assert "mine-flow-rotting" in [d[0] for d in defects]
        # the closed loop must actually emit its artifact, not just compute it
        assert (tmp_path / "data/p.json").exists()
        assert (tmp_path / "data/r.json").exists()   # ratchet persisted
