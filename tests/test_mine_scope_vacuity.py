"""R0269: §33 scope must be COUNTED, not merely listed, and the feed inbox must be counted at all.

Both guards are tested for FIRING as well as passing -- a check that can only pass is not a check.
The specific thing under test is the distinction that keeps `check_mine_scope_vacuous` honest: an
EMPTY doc is healthy and must read clean, because a fence that punished a drained queue would push
the desk to keep entries around. Vacuity is content the parser cannot SEE, never merely no cards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import scripts.max_audit as m


def _run(monkeypatch, tmp_path, fn) -> list[tuple[str, str]]:
    monkeypatch.setattr(m, "ROOT", tmp_path)
    out: list[tuple[str, str]] = []
    fn(out)
    return out


def _doc(tmp_path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")


_CARD = "### 1. A real find — grade: verified [§33: killed -> docs/graveyard.md thing]\n- x\n"


class TestScopeVacuity:
    def test_fires_on_a_doc_in_scope_the_parser_cannot_see(self, tmp_path, monkeypatch) -> None:
        """THE MEASURED DEFECT: feed_inbox.md sat in _DIG_DOCS with 27 '##' entries and parsed to
        zero items, so §33 reported a clean backlog computed over an empty set."""
        _doc(tmp_path, "docs/research/queue.md", "# Q\n\n## Entry one\n- a\n\n## Entry two\n- b\n")
        monkeypatch.setattr(m, "_DIG_DOCS", ("docs/research/queue.md",))
        out = _run(monkeypatch, tmp_path, m.check_mine_scope_vacuous)
        assert "mine-scope-vacuous" in [d[0] for d in out]
        assert "0 cards" in out[0][1]

    def test_empty_doc_is_healthy_and_reads_clean(self, tmp_path, monkeypatch) -> None:
        """A DRAINED QUEUE MUST NOT FIRE. This is the whole design: reward draining, never punish
        it, or the fence teaches the desk to keep a backlog."""
        _doc(tmp_path, "docs/research/queue.md", "# Q\n\nnothing outstanding.\n")
        monkeypatch.setattr(m, "_DIG_DOCS", ("docs/research/queue.md",))
        assert _run(monkeypatch, tmp_path, m.check_mine_scope_vacuous) == []

    def test_doc_with_real_cards_passes(self, tmp_path, monkeypatch) -> None:
        _doc(tmp_path, "docs/research/w.md", "# W\n\n" + _CARD)
        monkeypatch.setattr(m, "_DIG_DOCS", ("docs/research/w.md",))
        assert _run(monkeypatch, tmp_path, m.check_mine_scope_vacuous) == []

    def test_absent_path_is_a_phantom_not_a_silent_skip(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(m, "_DIG_DOCS", ("docs/research/never_existed.md",))
        out = _run(monkeypatch, tmp_path, m.check_mine_scope_vacuous)
        assert "mine-scope-phantom" in [d[0] for d in out]

    def test_live_scope_is_clean(self) -> None:
        """The live tree, after the 2026-08-06 re-derivation. Guards the regression directly."""
        out: list[tuple[str, str]] = []
        m.check_mine_scope_vacuous(out)
        assert out == [], out


class TestFeedInboxBacklog:
    def _inbox(self, tmp_path, entries: list[tuple[str, str]]) -> None:
        body = "# Research feed inbox (auto-fetched; CRO processes then DELETES entries)\n"
        for title, day in entries:
            body += f"\n## {title}\n- {day} · http://arxiv.org/abs/1234.5678v1\n- abstract\n"
        _doc(tmp_path, "docs/research/feed_inbox.md", body)

    def test_fires_on_a_stale_queue(self, tmp_path, monkeypatch) -> None:
        old = (datetime.now(tz=UTC) - timedelta(days=30)).date().isoformat()
        self._inbox(tmp_path, [("A paper", old)])
        out = _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog)
        assert "feed-inbox-backlog" in [d[0] for d in out]
        assert "1 live entr" in out[0][1]

    def test_fires_on_depth_even_when_fresh(self, tmp_path, monkeypatch) -> None:
        today = datetime.now(tz=UTC).date().isoformat()
        self._inbox(tmp_path, [(f"Paper {i}", today) for i in range(m._FEED_INBOX_MAX_OPEN + 1)])
        out = _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog)
        assert "feed-inbox-backlog" in [d[0] for d in out]

    def test_fresh_shallow_queue_passes(self, tmp_path, monkeypatch) -> None:
        today = datetime.now(tz=UTC).date().isoformat()
        self._inbox(tmp_path, [("A paper", today)])
        assert _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog) == []

    def test_drained_inbox_passes(self, tmp_path, monkeypatch) -> None:
        self._inbox(tmp_path, [])
        assert _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog) == []

    def test_triage_comment_blocks_are_not_counted_as_backlog(self, tmp_path, monkeypatch) -> None:
        """The record of DRAINING must never read as the backlog itself."""
        _doc(tmp_path, "docs/research/feed_inbox.md",
             "# Research feed inbox\n\n<!-- 2026-08-06: 27 entries triaged and cleared.\n"
             "## this heading is inside a comment\n-->\n")
        out = _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog)
        assert out == [], out

    def test_absent_inbox_does_not_fire(self, tmp_path, monkeypatch) -> None:
        assert _run(monkeypatch, tmp_path, m.check_feed_inbox_backlog) == []

    def test_live_inbox_is_drained(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_feed_inbox_backlog(out)
        assert out == [], out


@pytest.mark.parametrize("check", [m.check_mine_scope_vacuous, m.check_feed_inbox_backlog])
def test_new_checks_are_registered_in_the_sweep(check) -> None:
    """A check the sweep never calls is the orphan problem one level up."""
    assert check in [fn for _, fn in m.CHECKS], \
        f"{check.__name__} is defined but is not in CHECKS, so the sweep never runs it"
