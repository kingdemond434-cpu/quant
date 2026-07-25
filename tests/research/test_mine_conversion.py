"""Tests for the §33 MINED-TO-WIRED law. These lock the anti-gaming rules: an undated deferral is
illegal, a deferral expires, and a conversion CLAIM without a backing artifact never counts."""

from __future__ import annotations

from datetime import date

from libs.research.mine_conversion import (
    MinedItem,
    backlog,
    conversion_report,
    is_disposed,
    parse_dispositions,
    unbacked,
)

_TODAY = date(2026, 7, 25)

_DOC = """# Dig output 2026-07-25

### 1. Upbit 1m candles to 2017-10-24 [§33: wired]
### 2. Tardis free full-depth L2, 88 days
### 3. Kaiko index methodology is public [§33: killed]
### 4. bitFlyer 31-day wall [§33: deferred(2026-09-01)]
### 5. Quantopian archive [§33: deferred]
### 6. premium-as-barrier-rent prior [§33: screened]
### 7. SMF printpage operator [§33: maybe-later]
### 8. HN tree-walk operator [§33: deferred(2026-01-01)]
- **Provenance**: a metadata field, NOT a carded find
- **Queries used**: also not a find
"""


class TestParse:
    def test_extracts_numbered_cards_only(self) -> None:
        items = parse_dispositions(_DOC, source="dig")
        assert len(items) == 8  # the "### N." cards, bold bullets excluded

    def test_bold_bullets_are_not_finds(self) -> None:
        # source cards carry "- **Provenance**:" / "- **Queries used**:" metadata fields; treating
        # those as carded finds made the first real run fire 92/92, and a check that flags
        # everything is ignored. Only the id-numbered card is a "thing that was found".
        items = {i.name for i in parse_dispositions(_DOC, source="dig")}
        assert "Provenance" not in items and "Queries used" not in items

    def test_card_number_is_not_part_of_the_name(self) -> None:
        # "1. Upbit" would match no artifact in either direction -> a real conversion reported
        # as unbacked. The id is parsed and dropped from the name.
        items = parse_dispositions("### 7. Upbit KRW-BTC\n", source="d")
        assert items[0].name == "Upbit KRW-BTC"

    def test_tag_stripped_from_name(self) -> None:
        items = {i.name for i in parse_dispositions(_DOC, source="dig")}
        assert "Kaiko index methodology is public" in items  # no trailing [§33: killed]

    def test_untagged_item_is_undisposed(self) -> None:
        by = {i.name: i for i in parse_dispositions(_DOC, source="dig")}
        tardis = by["Tardis free full-depth L2, 88 days"]
        assert tardis.disposition == "" and not is_disposed(tardis, as_of=_TODAY)

    def test_undated_deferral_is_illegal(self) -> None:
        by = {i.name: i for i in parse_dispositions(_DOC, source="dig")}
        q = by["Quantopian archive"]
        assert q.illegal_reason == "deferred with NO date"
        assert not is_disposed(q, as_of=_TODAY)  # the hiding place stays in the backlog

    def test_unknown_verb_is_illegal(self) -> None:
        by = {i.name: i for i in parse_dispositions(_DOC, source="dig")}
        assert "unknown disposition" in by["SMF printpage operator"].illegal_reason

    def test_ascii_tag_variant_accepted(self) -> None:
        items = parse_dispositions("### 1. X [S33: wired]\n", source="d")
        assert items[0].disposition == "wired"

    def test_blanket_tag_on_its_own_line_launders_nothing(self) -> None:
        # a header tag must NOT dispose the items beneath it
        doc = "[§33: wired]\n### 1. A\n### 2. B\n"
        items = parse_dispositions(doc, source="d")
        assert [i.disposition for i in items] == ["", ""]


class TestDisposition:
    def test_terminal_verbs_dispose(self) -> None:
        for verb in ("wired", "screened", "killed"):
            it = MinedItem(source="d", name="x", disposition=verb)
            assert is_disposed(it, as_of=_TODAY)

    def test_future_deferral_disposes(self) -> None:
        it = MinedItem(source="d", name="x", disposition="deferred",
                       deferred_until="2026-09-01")
        assert is_disposed(it, as_of=_TODAY)

    def test_expired_deferral_returns_to_backlog(self) -> None:
        it = MinedItem(source="d", name="x", disposition="deferred",
                       deferred_until="2026-01-01")
        assert not is_disposed(it, as_of=_TODAY)  # a promise with a clock, not a filing cabinet

    def test_backlog_collects_every_owing_item(self) -> None:
        bl = {i.name for i in backlog(parse_dispositions(_DOC, source="d"), as_of=_TODAY)}
        assert bl == {
            "Tardis free full-depth L2, 88 days",  # untagged
            "Quantopian archive",                  # undated deferral
            "SMF printpage operator",              # unknown verb
            "HN tree-walk operator",               # expired deferral
        }


class TestUnbacked:
    def test_claim_without_artifact_is_unbacked(self) -> None:
        items = [MinedItem(source="d", name="Upbit 1m candles", disposition="wired")]
        assert unbacked(items, artifact_backed=[]) == tuple(items)

    def test_substring_match_in_either_direction_counts(self) -> None:
        items = [MinedItem(source="d", name="Tardis", disposition="wired")]
        assert unbacked(items, artifact_backed=["tardis_l2_backfill.json"]) == ()
        items2 = [MinedItem(source="d", name="Upbit KRW-BTC 1m backfill", disposition="screened")]
        assert unbacked(items2, artifact_backed=["upbit"]) == ()

    def test_killed_and_deferred_are_never_artifact_checked(self) -> None:
        items = [MinedItem(source="d", name="X", disposition="killed"),
                 MinedItem(source="d", name="Y", disposition="deferred",
                           deferred_until="2026-09-01")]
        assert unbacked(items, artifact_backed=[]) == ()


class TestReport:
    def test_backlog_suspends_mining(self) -> None:
        rep = conversion_report(parse_dispositions(_DOC, source="d"), as_of=_TODAY,
                                artifact_backed=["upbit", "barrier-rent"])
        assert rep.suspend_mining is True
        assert rep.n_backlog == 4
        assert "MINING SUSPENDED" in rep.verdict

    def test_unbacked_claim_alone_suspends_mining(self) -> None:
        # the cheapest way to clear a backlog must NOT be typing the word "wired"
        items = [MinedItem(source="d", name="Upbit", disposition="wired")]
        rep = conversion_report(items, as_of=_TODAY, artifact_backed=[])
        assert rep.suspend_mining is True and rep.n_unbacked == 1

    def test_fully_disposed_and_backed_authorises_mining(self) -> None:
        items = [MinedItem(source="d", name="Upbit", disposition="wired"),
                 MinedItem(source="d", name="Kaiko", disposition="killed")]
        rep = conversion_report(items, as_of=_TODAY, artifact_backed=["upbit_1m.jsonl"])
        assert rep.suspend_mining is False
        assert "backlog clear" in rep.verdict and rep.n_wired == 1 and rep.n_killed == 1

    def test_empty_owes_nothing(self) -> None:
        rep = conversion_report([], as_of=_TODAY)
        assert rep.suspend_mining is False and "nothing owed" in rep.verdict

    def test_counts_are_reported(self) -> None:
        rep = conversion_report(parse_dispositions(_DOC, source="d"), as_of=_TODAY,
                                artifact_backed=["upbit", "barrier-rent"])
        assert (rep.n_wired, rep.n_screened, rep.n_killed, rep.n_deferred) == (1, 1, 1, 1)
        assert rep.n_illegal == 2  # undated deferral + unknown verb
