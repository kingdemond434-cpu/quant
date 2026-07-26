"""§39(5)(d): the parity guard must actually catch the failure that caused §39 in the first place.

The original defect was five copies of one policy that drifted apart, so the guard checks the
SHAPE OF THE DEPENDENCY (does this scorer import the shared policy?) rather than the value of any
threshold -- otherwise it would fire on every legitimate re-tune and be acknowledged into silence.
These lock that it fires on a re-inlined constant and on a dropped import, and stays quiet on the
real tree."""

from __future__ import annotations

import scripts.max_audit as m


def _defects(monkeypatch, root) -> list[tuple[str, str]]:
    monkeypatch.setattr(m, "ROOT", root)
    out: list[tuple[str, str]] = []
    m.check_capacity_single_source(out)
    return out


class TestGuard:
    def test_the_real_tree_is_clean(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_capacity_single_source(out)
        assert out == [], f"§39 parity guard is firing on the live tree: {out}"

    def test_a_reinlined_fund_constant_is_caught(self, tmp_path, monkeypatch) -> None:
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n", "utf-8")
        bad = tmp_path / m._CAPACITY_CONSUMERS[0]
        bad.write_text("from libs.research.capacity_policy import capacity_fit\n"
                       "capacity_pass = capacity_usd >= 1e5\n", "utf-8")
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-constant-reinlined" in ids

    def test_dropping_the_shared_import_is_caught(self, tmp_path, monkeypatch) -> None:
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n", "utf-8")
        (tmp_path / m._CAPACITY_CONSUMERS[1]).write_text("x = 1\n", "utf-8")
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-policy-not-imported" in ids

    def test_a_consumer_that_vanished_is_reported_not_skipped(self, tmp_path, monkeypatch) -> None:
        # a moved file must not silently make the guard blind to wherever the logic went
        ids = [d[0] for d in _defects(monkeypatch, tmp_path)]
        assert "capacity-consumer-missing" in ids

    def test_a_comment_mentioning_the_old_floor_is_not_a_defect(
        self, tmp_path, monkeypatch
    ) -> None:
        # the modules DOCUMENT the bug they fixed; the guard must not punish that
        for rel in m._CAPACITY_CONSUMERS:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("from libs.research.capacity_policy import capacity_fit\n"
                         "# capacity was a flat 1e5 floor until 2026-07-26\n", "utf-8")
        assert _defects(monkeypatch, tmp_path) == []
