"""The principal-drop ingestion path: the one route into sources the desk cannot reach itself.

WHY THIS ORGAN EXISTS, and the number is the argument. libs.research.conversion_max reports
`mined_research` total 14 -- FOURTEEN mined items have ever been read, against a miner surfacing
60-115 rows per run six times a day across Bilibili, Juejin and WeChat. The chain is

    mine -> rank -> [ NOBODY READS ] -> hypothesis -> screen -> survivor

and it breaks at the read step, which is the whole answer to why the Chinese miner has produced no
screens and no survivors while working perfectly. Reading is blocked differently per source and the
difference decides what to build: video is genuinely unreadable here (0 of 14 expose captions
unauthenticated), Juejin bodies need browser rendering (a COST -- Chromium is present), and closed
groups need a membership, which is a person rather than a credential. This organ covers the third.

WHAT THESE TESTS GUARD. Not the parsing -- that is simple. They guard PROVENANCE, because the
failure mode is silent and permanent: a row that loses its principal_drop tag becomes
indistinguishable from something the desk's own organs found, and a later audit will hunt for a
collector that does not exist. And they guard the BAR, because hand-supplied material is exactly
the kind that acquires an exemption ("the principal vouched for it") -- it must not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.ingest_principal_drop as D

# FULLWIDTH PUNCTUATION IS DELIBERATE and RUF001 is silenced rather than obeyed: these are
# realistic Chinese chat messages, and fullwidth comma is the CORRECT character in them.
# "Correcting" them to ASCII would make the fixture unrepresentative of every real drop this
# organ will ever see, which is the one property a fixture has to have.
_SUBSTANTIVE = (
    "老王: 今天聊聊我们做的期现套利回测，样本外只剩三分之一的收益，"  # noqa: RUF001
    "主要是资金费率的结算时间没对齐"
)
_CHATTER = "随便聊聊天气今天真不错啊，大家周末有什么安排吗，我打算去爬山看看风景"  # noqa: RUF001


def _drop(tmp_path: Path, name: str, body: str) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(body, "utf-8")
    return inbox


class TestProvenanceSurvivesEverything:
    def test_every_row_is_tagged_principal_drop(self, tmp_path: Path) -> None:
        """source is ALWAYS principal_drop, never the channel. The channel says WHERE it came
        from; the source says the DESK DID NOT OBTAIN IT, and that is the fact a later reader
        must not be able to lose."""
        inbox = _drop(tmp_path, "wechat-group-2026-08-05.txt", _SUBSTANTIVE)
        rep = D.ingest(inbox, move=False)
        assert rep["n_rows"] >= 1
        assert all(r["source"] == "principal_drop" for r in rep["rows"])

    def test_the_channel_is_read_from_the_filename(self, tmp_path: Path) -> None:
        inbox = _drop(tmp_path, "telegram-alpha-chat.txt", _SUBSTANTIVE)
        assert D.ingest(inbox, move=False)["rows"][0]["channel"] == "telegram"

    def test_an_unnameable_channel_is_unspecified_not_guessed(self, tmp_path: Path) -> None:
        """A WRONG channel tag is worse than none: it claims a provenance the desk cannot check,
        and provenance the desk cannot check is the thing this whole organ exists to preserve."""
        inbox = _drop(tmp_path, "notes.txt", _SUBSTANTIVE)
        assert D.ingest(inbox, move=False)["rows"][0]["channel"] == "unspecified"

    def test_the_originating_file_is_recorded(self, tmp_path: Path) -> None:
        """A membership can lapse. Rows carrying their file and channel let the desk see later
        which lanes went quiet -- what unproven_sources does for probed sources."""
        inbox = _drop(tmp_path, "wechat-groupname.txt", _SUBSTANTIVE)
        assert D.ingest(inbox, move=False)["rows"][0]["file"] == "wechat-groupname.txt"

    def test_the_artifact_says_why_the_organ_exists(self, tmp_path: Path) -> None:
        """The measurement that justifies a hand-fed intake path must travel WITH it. Strip it and
        the next reader sees a manual step and deletes it as unautomated."""
        rep = D.ingest(_drop(tmp_path, "x.txt", _SUBSTANTIVE), move=False)
        assert "14" in rep["why_this_organ_exists"]
        assert "principal_drop" in rep["provenance_note"]
        assert "ZERO promotion authority" in rep["provenance_note"]


class TestHandSuppliedMaterialGetsNoExemption:
    def test_it_is_scored_by_the_same_ranker_as_miner_output(self, tmp_path: Path) -> None:
        """The exemption this must never acquire is 'the principal vouched for it'. Same ranker,
        same threshold, or the desk has two bars and the softer one is fed by hand."""
        from libs.research.video_triage import score_title
        inbox = _drop(tmp_path, "wechat-g.txt", _SUBSTANTIVE)
        row = D.ingest(inbox, move=False)["rows"][0]
        assert row["score"] == pytest.approx(round(score_title(_SUBSTANTIVE)[0], 1))

    def test_chatter_below_threshold_is_dropped(self, tmp_path: Path) -> None:
        inbox = _drop(tmp_path, "wechat-g.txt", _CHATTER)
        assert D.ingest(inbox, move=False)["n_rows"] == 0

    def test_the_threshold_is_not_secretly_lower_than_the_miners(self, tmp_path: Path) -> None:
        rep = D.ingest(_drop(tmp_path, "x.txt", _SUBSTANTIVE), move=False)
        assert rep["threshold"] == 3.0, "the miner's threshold; a softer one here is a second bar"

    def test_a_long_document_is_split_rather_than_scored_whole(self, tmp_path: Path) -> None:
        """Scoring a 40KB export as ONE unit lets a single strong phrase carry the whole file --
        the exact shape in which junk enters a ranked queue."""
        body = f"{_CHATTER}\n\n{_SUBSTANTIVE}\n\n{_CHATTER}"
        rep = D.ingest(_drop(tmp_path, "wechat-g.txt", body), move=False)
        assert rep["n_rows"] == 1, "only the substantive block should survive"


class TestItSurvivesRealDropsRatherThanTidyOnes:
    def test_html_is_stripped_then_unescaped_in_that_order(self, tmp_path: Path) -> None:
        """Same order rule as the CN parsers: decode first and an encoded `&lt;p&gt;` becomes a
        real tag the stripper eats, deleting text that was never markup."""
        inbox = _drop(tmp_path, "wechat-g.html", f"<div><p>{_SUBSTANTIVE}</p></div>")
        rows = D.ingest(inbox, move=False)["rows"]
        assert rows and "<p>" not in rows[0]["text"]

    def test_a_json_chat_export_is_flattened_to_its_strings(self, tmp_path: Path) -> None:
        """There is no standard shape for chat exports and never will be, so the reader walks to
        the string leaves instead of assuming a schema it would then be wrong about."""
        doc = {"messages": [{"from": "老王", "body": _SUBSTANTIVE}, {"from": "x", "body": "hi"}]}
        inbox = _drop(tmp_path, "wechat-g.json", json.dumps(doc, ensure_ascii=False))
        assert D.ingest(inbox, move=False)["n_rows"] >= 1

    def test_malformed_json_falls_back_to_raw_text(self, tmp_path: Path) -> None:
        inbox = _drop(tmp_path, "wechat-g.json", "{broken " + _SUBSTANTIVE)
        assert D.ingest(inbox, move=False)["n_rows"] >= 1

    def test_an_empty_inbox_is_not_an_error(self, tmp_path: Path) -> None:
        """A scheduled organ that hard-fails on an empty input gets switched off, and a
        switched-off organ ingests nothing forever."""
        rep = D.ingest(tmp_path / "inbox", move=False)
        assert rep["n_files"] == 0 and rep["n_rows"] == 0

    def test_processed_files_move_so_a_rerun_is_idempotent(self, tmp_path: Path) -> None:
        inbox = _drop(tmp_path, "wechat-g.txt", _SUBSTANTIVE)
        assert D.ingest(inbox, move=True)["n_rows"] >= 1
        assert D.ingest(inbox, move=True)["n_rows"] == 0, "a second run must not re-score"
        assert (inbox / ".done" / "wechat-g.txt").exists(), "the original must be kept, not lost"

    def test_duplicate_blocks_within_one_drop_are_collapsed(self, tmp_path: Path) -> None:
        body = f"{_SUBSTANTIVE}\n\n{_SUBSTANTIVE}"
        assert D.ingest(_drop(tmp_path, "x.txt", body), move=False)["n_rows"] == 1


def test_private_material_can_never_be_committed() -> None:
    """THE ONE IRREVERSIBLE FAILURE. This inbox holds closed-group content; a push cannot be
    undone by a later commit. `data/*` already covers it, so this asserts the EXPLICIT entries
    are also present -- a future `!data/<artifact>` exception added in good faith would otherwise
    widen the hole silently, and nobody would be looking."""
    ignore = Path(".gitignore").read_text("utf-8")
    assert "data/inbox/" in ignore
    assert "reports/principal_drop.json" in ignore, (
        "the scored output quotes up to 600 chars of source material verbatim")
