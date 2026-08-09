"""The yield instrument -- the number every mining CADENCE is read off, and it had no test.

WHY THIS FILE EXISTS. `data/miner_yield.jsonl` answers the only question that decides how often a
miner should run: of what it fetched, how much was NEW and above threshold? A source can look busy
on `fetched` and be worth nothing, which is exactly Juejin's shape (80 fetched, 0 new) and exactly
what a fetch-count-only report hides. The standing rule is that cadence is READ OFF this ratio
rather than argued -- so a wrong number here does not produce a wrong report, it produces a wrong
schedule, and the wrongness compounds every day nobody re-derives it.

It had zero coverage, and the defect that got in is the one that shape invites:

    prefixes = ("juejin", "wechat") if src == "cn" else (src,)

`cn` is a GROUP, not a producer -- its rows carry `juejin:`/`wechat:` channels -- so it was
special-cased. When `foreign` was added as a second group (qiita/zenn/hatena/dcinside/habr) the
special case was not extended, and its `new_above_threshold` became structurally ZERO: the first
foreign sweep logged 1,601 fetched, 0 new, yield 0.0 on a run that had just surfaced three rows.
A producing lane reporting nothing forever is an argument to cut the one sweep worth keeping.
"""
from __future__ import annotations

import scripts.mine_research_queue as M


def _doc(**kw: object) -> dict:
    base = {"threshold": 3.0, "queue": []}
    base.update(kw)
    return base


class TestAGroupIsNotAProducer:
    def test_foreign_rows_are_attributed_to_foreign(self) -> None:
        """THE REGRESSION. Foreign queue channels are qiita:/zenn:/hatena:/dcinside:/habr:, and
        the string "foreign" never appears in one -- so a prefix match on the group name counts
        none of them."""
        doc = _doc(foreign_discovered={"qiita:a": 20, "habr:b": 10},
                   queue=[{"channel": "qiita:a"}, {"channel": "habr:b"}, {"channel": "habr:c"}])
        per = M._yield_row(doc, seen=set(), only=["foreign"])["per_source"]["foreign"]
        assert per == {"fetched": 30, "new_above_threshold": 3, "yield": 0.1}

    def test_cn_rows_are_still_attributed_to_cn(self) -> None:
        """The case that WAS handled must not break while fixing the case that was not."""
        doc = _doc(cn_article_discovered={"juejin:a": 20, "wechat:b": 10},
                   queue=[{"channel": "juejin:a"}, {"channel": "wechat:b"}])
        per = M._yield_row(doc, seen=set(), only=["cn"])["per_source"]["cn"]
        assert per["new_above_threshold"] == 2

    def test_every_multi_producer_group_declares_its_producers(self) -> None:
        """A group added without an entry here silently reports zero yield forever. The check is
        structural rather than a list of known names, so the NEXT group is covered too."""
        for group, producers in M._GROUP_PRODUCERS.items():
            assert group in M._FETCH_KEYS, f"{group} is not a known source group"
            assert producers, f"{group} declares no producers"
            assert group not in producers, (
                f"{group} lists itself as a producer -- if that were true it would not need "
                "an entry, and the entry would be masking the bug rather than fixing it")

    def test_single_producer_groups_still_fall_back_to_their_own_name(self) -> None:
        doc = _doc(bilibili_discovered={"q1": 100},
                   queue=[{"channel": "bilibili:q1"}, {"channel": "bilibili:q2"}])
        per = M._yield_row(doc, seen=set(), only=["bilibili"])["per_source"]["bilibili"]
        assert per["new_above_threshold"] == 2


class TestTheRatioMeansWhatCadenceAssumesItMeans:
    def test_a_busy_source_with_no_new_rows_reports_zero_yield_not_absence(self) -> None:
        """Juejin's shape: 80 fetched, 0 new. That is a MEASURED zero and the whole reason the
        instrument exists -- reporting it as absent would hide the finding."""
        doc = _doc(cn_article_discovered={"juejin:a": 80}, queue=[])
        per = M._yield_row(doc, seen=set(), only=["cn"])["per_source"]["cn"]
        assert per["fetched"] == 80
        assert per["new_above_threshold"] == 0
        assert per["yield"] == 0.0, "a measured zero, not None"

    def test_a_source_that_did_not_run_is_absent_rather_than_zero(self) -> None:
        """L1.41: 'did not run' and 'ran and found nothing' are different facts, and a schedule
        derived from the second when the first is true cuts a lane that was never given a chance."""
        doc = _doc(bilibili_discovered={"q": 50}, queue=[{"channel": "bilibili:q"}])
        per = M._yield_row(doc, seen=set(), only=["bilibili"])["per_source"]
        assert "cn" not in per and "academic" not in per

    def test_zero_fetched_yields_none_rather_than_a_division(self) -> None:
        doc = _doc(bilibili_discovered={}, queue=[])
        per = M._yield_row(doc, seen=set(), only=["bilibili"])["per_source"]["bilibili"]
        assert per["yield"] is None, "0/0 is unmeasured, never 0.0"

    def test_the_row_carries_the_threshold_it_was_measured_at(self) -> None:
        """A yield is meaningless without the bar it was measured against -- comparing runs at
        different thresholds is exactly how a cadence argument gets won by moving the bar."""
        row = M._yield_row(_doc(bilibili_discovered={"q": 10}), seen=set(), only=["bilibili"])
        assert row["threshold"] == 3.0
        assert "ts" in row and "seen_ledger_size" in row
