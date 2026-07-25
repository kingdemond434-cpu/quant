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
    # isolate from the real repo's artifacts AND its snapshot ledger -- the conversion check now
    # reads history, so an un-isolated fixture inherits the live desk's vanished-item state
    monkeypatch.setattr(m, "_conversion_artifacts", lambda: [])
    monkeypatch.setattr(m, "MINE_LEDGER", tmp / "data/ledger.jsonl")


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
            "### 1. Tardis [§33: killed -> docs/graveyard.md]\n"
            "### 2. Upbit [§33: deferred(2099-01-01)]\n")
        # a kill is only credited with its graveyard entry -- named EXACTLY, so the cheap exit
        # stays closed and the credit cannot drift on a rename
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

    def test_exact_artifact_claim_is_credited(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. Upbit [§33: wired -> data/upbit_1m.jsonl]\n")
        (tmp_path / "data/upbit_1m.jsonl").write_text('{"t":1}\n')
        _point_at(monkeypatch, tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        assert defects == []   # exact path, exists, non-empty -> no fuzzy nudge either

    def test_fuzzy_claim_is_credited_but_nudged(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. Upbit [§33: wired]\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "MINING_SUSPENDED", tmp_path / "data/mining_suspended")
        monkeypatch.setattr(m, "_conversion_artifacts", lambda: ["upbit_krw_btc_1m"])
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        # credited (no backlog, no unbacked) but the weaker standard is surfaced, not silent
        assert [d[0] for d in defects] == ["mine-conversion-fuzzy"]

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


class TestMineGate:
    def test_missing_gate_script_fires(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "scripts").mkdir(parents=True)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_gate(defects)
        assert defects and defects[0][0] == "mine-gate-missing"

    def test_shell_that_skips_the_gate_is_flagged(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts/mine_gate.py").write_text("print('[§33] AUTHORISED -- ok')\n")
        (tmp_path / "ops").mkdir()
        (tmp_path / "ops/run_rogue_dig.sh").write_text("#!/bin/bash\nclaude -p dig\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_gate(defects)
        assert "mine-gate-bypassed" in [d[0] for d in defects]

    def test_gate_that_fails_open_is_surfaced(self, tmp_path: Path, monkeypatch) -> None:
        # failing open is deliberate; this defect is the ONLY thing that makes it visible
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts/mine_gate.py").write_text(
            "print('[§33] GATE-ERROR ValueError: boom -- failing OPEN')\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_gate(defects)
        assert "mine-gate-broken" in [d[0] for d in defects]
        assert "UNGATED" in dict(defects)["mine-gate-broken"]

    def test_healthy_gate_is_silent(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts/mine_gate.py").write_text("print('[§33] AUTHORISED -- clear')\n")
        (tmp_path / "ops").mkdir()
        (tmp_path / "ops/run_x_dig.sh").write_text("python3 scripts/mine_gate.py || exit 0\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_gate(defects)
        assert defects == []


class TestGateScript:
    def test_real_gate_suspends_on_the_real_backlog(self) -> None:
        import subprocess
        import sys
        r = subprocess.run([sys.executable, "scripts/mine_gate.py"],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode in (0, 1)              # never crashes
        assert "[§33]" in r.stdout
        assert "GATE-ERROR" not in r.stdout        # and never fails open in a healthy tree

    def test_explain_never_blocks(self) -> None:
        import subprocess
        import sys
        r = subprocess.run([sys.executable, "scripts/mine_gate.py", "--explain"],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0


class TestTamperChecks:
    def test_vanished_card_fires(self, tmp_path: Path, monkeypatch) -> None:
        from libs.research.mine_conversion import MinedItem, append_snapshot
        w = _mk(tmp_path)
        lg = tmp_path / "data/l.jsonl"
        append_snapshot(lg, [MinedItem(source="docs/research/data_axis_watchlist.md",
                                       name="Tardis fence"),
                             MinedItem(source="docs/research/data_axis_watchlist.md",
                                       name="Upbit")])
        w.write_text("### 2. Upbit\n")   # the Tardis card is simply edited away
        _point_at(monkeypatch, tmp_path)
        monkeypatch.setattr(m, "MINE_LEDGER", lg)
        defects: list[tuple[str, str]] = []
        m.check_mine_conversion(defects)
        d = dict(defects)
        assert "mine-item-vanished" in d
        assert "Tardis fence" in d["mine-item-vanished"]

    def test_ratchet_record_lives_in_a_tracked_path(self) -> None:
        # under data/* it was one `rm` from a fresh, easier bar; in docs/ a reset shows in git
        assert "docs/research" in str(m.MINE_RATCHET)
        assert "data/" not in str(m.MINE_RATCHET)

    def test_truncated_ledger_fires(self, tmp_path: Path, monkeypatch) -> None:
        from datetime import datetime

        from libs.research.mine_conversion import MinedItem, Ratchet, append_snapshot
        _mk(tmp_path)
        lg = tmp_path / "data/l.jsonl"
        base = datetime(2026, 7, 1, tzinfo=UTC)
        append_snapshot(lg, [MinedItem(source="s", name="A")], now=base)
        append_snapshot(lg, [MinedItem(source="s", name="A")],
                        now=datetime.fromtimestamp(base.timestamp() + 86400, UTC))
        rec = tmp_path / "docs/research/conversion_record.json"
        rec.write_text(Ratchet(n_snapshots=9, earliest_ts=1.0).model_dump_json())
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "MINE_LEDGER", lg)
        monkeypatch.setattr(m, "MINE_RATCHET", rec)
        monkeypatch.setattr(m, "MINE_PRIORS", tmp_path / "data/p.json")
        defects: list[tuple[str, str]] = []
        m.check_mine_flow(defects)
        assert "mine-ledger-truncated" in [d[0] for d in defects]


class TestMineScope:
    def test_rogue_card_bearing_doc_is_flagged(self, tmp_path: Path, monkeypatch) -> None:
        # writing finds to an unscanned file is the ONE bypass needing no code change
        _mk(tmp_path)
        (tmp_path / "docs/research/secret_finds.md").write_text("### 1. A\n### 2. B\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_scope(defects)
        assert defects and defects[0][0] == "mine-scope-unmonitored"
        assert "secret_finds.md(2 cards)" in defects[0][1]

    def test_scanned_doc_is_not_flagged(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path).write_text("### 1. A\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_scope(defects)
        assert defects == []

    def test_explicitly_excluded_doc_is_not_flagged(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "docs/research/panel_inbox.md").write_text("### 1. A\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_scope(defects)
        assert defects == []   # consciously excluded, with a reason on record

    def test_doc_without_cards_is_ignored(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "docs/research/prose.md").write_text("# notes\nsome prose\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_mine_scope(defects)
        assert defects == []
