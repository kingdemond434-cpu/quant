"""L1.53 applied to the desk's own strength gauge: running LESS must never read as killing more.

THE TRAP, AND WHY IT LIVED IN THE ONE PLACE IT SHOULD NOT HAVE. check_utilisation._mutation()
aggregates mutation results into `test_kill_rate`, the number that stands for how much of the
money path the suite can actually see. It summed `killed` and `total` across every target and
divided. run_mutation.py walks mutation sites in SOURCE ORDER, so a budget-truncated target has
tested a PREFIX of a file rather than a sample of it -- and both its kills and its mutants entered
the sums together. Truncating a hard file therefore did not lower the score; it shrank the
denominator and raised it.

The harness had recorded `budget_truncated` per target the whole time. This consumer never read
it. That is exactly the failure L1.53 names -- a gauge improvable by doing less of the thing it
exists to encourage -- sitting inside the desk's own test-strength measurement.

TWO MORE DEFECTS IN THE SAME EIGHT LINES, both of the same family the desk kept finding on
2026-08-05 (unknown reading as fine, and its inverse):

  * `else float(d.get("kill_rate", 0.0))` -- a fallback on a top-level key the artifact NEVER
    writes, so "no mutants ran" silently became a confident 0.0.
  * `measured = score > 0` -- which then relabelled that 0.0 as UNMEASURED. So a suite that kills
    NOTHING, the single worst real result this gauge can produce, was indistinguishable from a run
    that never happened. Those are opposite facts: one is a catastrophe, the other is a chore.

These tests are behavioural and use synthetic artifacts, because the live artifact currently has
zero truncated targets -- the protection must be provable before the day it is needed, not after.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.check_utilisation as U


def _artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, targets: list[dict]) -> None:
    monkeypatch.setattr(U, "_ROOT", tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/mutation_score.json").write_text(
        json.dumps({"measured": True, "targets": targets}), "utf-8")


def _t(killed: int, total: int, *, truncated: bool = False, n_sites: int | None = None) -> dict:
    """One target. `total` is what RAN; `n_sites` is what EXISTS (they differ only if truncated)."""
    return {"target": f"libs/x{killed}_{total}.py", "killed": killed, "total": total,
            "n_sites": total if n_sites is None else n_sites,
            "budget_truncated": truncated, "kill_rate": (killed / total if total else 0.0)}


class TestATruncatedTargetIsNotACheapMeasurement:
    def test_unrun_sites_are_charged_to_the_denominator_as_unkilled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The whole point. A truncated target ran 20 of its 200 sites and killed all 20; the
        other 180 were never injected and must count as un-killed, not as absent."""
        _artifact(tmp_path, monkeypatch, [
            _t(50, 100),                                    # honest: 50/100
            _t(20, 20, truncated=True, n_sites=200),        # a flattering prefix of a hard file
        ])
        c = U._mutation()
        assert c.used == pytest.approx(70.0 / 300.0), (
            "expected 70 kills over 300 SITES; naive summing would read 70/120 = 0.583 and "
            "dropping the target entirely would read 0.500 -- both reward truncation")
        assert c.measured is True

    def test_running_less_of_a_hard_file_cannot_raise_the_score(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The adversarial framing, executed: take a file the suite is bad at and run less of it.
        The score must not improve. This is the exact incentive L1.53 forbids."""
        honest = [_t(50, 100), _t(10, 100)]                       # 60/200 = 0.30
        _artifact(tmp_path, monkeypatch, honest)
        before = U._mutation().used
        # same hard file, but only its first 10 sites run -- and they happen to be the easy ones
        gamed = [_t(50, 100), _t(9, 10, truncated=True, n_sites=100)]
        _artifact(tmp_path, monkeypatch, gamed)
        after = U._mutation().used
        assert after <= before, (
            f"truncating the hard target raised the score {before:.3f} -> {after:.3f}; "
            "the denominator is buyable")

    def test_the_truncation_is_stated_rather_than_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Silent truncation reads as full coverage. The count of dropped targets must reach the
        operator, or the honest number looks identical to the flattering one."""
        _artifact(tmp_path, monkeypatch,
                  [_t(50, 100), _t(20, 20, truncated=True, n_sites=200)])
        c = U._mutation()
        assert "1 truncated" in c.unit
        assert "prefix is not a sample" in c.unit

    def test_a_wholly_truncated_target_scores_against_all_its_sites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Even alone, a truncated target is scored against what EXISTS, so a 9-of-10-run file
        with 1000 sites reads ~0.009 rather than 0.9. It is measured -- and damning."""
        _artifact(tmp_path, monkeypatch, [_t(9, 10, truncated=True, n_sites=1000)])
        c = U._mutation()
        assert c.measured is True
        assert c.used == pytest.approx(9.0 / 1000.0)


class TestMeasuredMeansItHappenedNotThatItWentWell:
    def test_a_genuine_zero_kill_rate_is_MEASURED(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The worst real result this gauge can produce -- the suite kills nothing -- was
        reported as UNMEASURED by `measured = score > 0`, i.e. as though nobody had looked."""
        _artifact(tmp_path, monkeypatch, [_t(0, 120)])
        c = U._mutation()
        assert c.used == 0.0
        assert c.measured is True, (
            "a suite that kills 0 of 120 mutants has been MEASURED, and catastrophically so; "
            "reporting it as unmeasured hides the single most alarming reading available")

    def test_an_empty_target_list_is_unmeasured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _artifact(tmp_path, monkeypatch, [])
        assert U._mutation().measured is False

    def test_a_missing_artifact_is_unmeasured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(U, "_ROOT", tmp_path)
        assert U._mutation().measured is False

    def test_the_dead_toplevel_fallback_is_gone(self) -> None:
        """`d.get("kill_rate")` read a key the artifact never writes, turning "nothing ran" into
        a confident 0.0 that the next line then relabelled UNMEASURED. Pinned at source because
        re-adding it looks like defensive programming and restores both bugs at once."""
        # Comment lines are stripped first: the repair's own comment QUOTES the removed code to
        # explain why it went, and a naive substring search reads that explanation as the bug.
        code = [ln for ln in Path("scripts/check_utilisation.py").read_text("utf-8").splitlines()
                if not ln.lstrip().startswith("#")]
        assert not [ln for ln in code if 'd.get("kill_rate"' in ln]


def test_the_live_artifact_still_scores_the_same(tmp_path: Path) -> None:
    """NON-REGRESSION. Every target in the live artifact is untruncated today, so this repair
    must not move the number -- it adds a rail, it does not restate the measurement. If this
    fails, the fix changed a reading it had no business changing."""
    raw = json.loads(Path("data/mutation_score.json").read_text("utf-8"))
    targets = [t for t in raw.get("targets") or [] if isinstance(t, dict)]
    if not targets or any(t.get("budget_truncated") for t in targets):
        pytest.skip("live artifact has truncated targets -- the identity no longer applies")
    naive = (sum(float(t["killed"]) for t in targets)
             / sum(float(t["total"]) for t in targets))
    assert U._mutation().used == pytest.approx(naive)
