"""Tests for the §33 MINED-TO-WIRED law. These lock the anti-gaming rules: an undated deferral is
illegal, a deferral expires, and a conversion CLAIM without a backing artifact never counts."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from libs.research.mine_conversion import (
    FlowStats,
    MinedItem,
    Ratchet,
    append_snapshot,
    backing_reason,
    backlog,
    class_priors,
    conversion_report,
    feedback_applied,
    first_seen_map,
    flow_stats,
    fuzzy_credited,
    infer_tier,
    is_disposed,
    law_effectiveness,
    ledger_regressed,
    load_ledger,
    parse_dispositions,
    priors_payload,
    stable_key,
    tier_calibration,
    unbacked,
    unbacked_reasons,
    update_ratchet,
    vanished,
)

_TODAY = date(2026, 7, 25)
_BACKING = {"wired": ["upbit"], "screened": ["barrier-rent"], "killed": ["kaiko"]}

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
        assert unbacked(items, backing={}) == tuple(items)

    def test_substring_match_in_either_direction_counts(self) -> None:
        items = [MinedItem(source="d", name="Tardis", disposition="wired")]
        assert unbacked(items, backing={"wired": ["tardis_l2_backfill.json"]}) == ()
        items2 = [MinedItem(source="d", name="Upbit KRW-BTC 1m backfill", disposition="screened")]
        assert unbacked(items2, backing={"screened": ["upbit"]}) == ()

    def test_killed_IS_artifact_checked_closing_the_cheap_exit(self) -> None:
        # mass-killing must cost MORE than converting, not less: a kill needs its graveyard entry
        killed = MinedItem(source="d", name="X", disposition="killed")
        assert unbacked([killed], backing={}) == (killed,)
        assert unbacked([killed], backing={"killed": ["x -- mechanism: no counterparty"]}) == ()

    def test_an_anchor_names_which_entry_and_is_verified_not_ignored(self, tmp_path) -> None:
        """CITING MORE PRECISELY MUST NOT SCORE WORSE. `-> docs/graveyard.md `some_entry`` used to
        parse as one 40-character filename that could never exist, so the claim read as unbacked
        permanently and doing the work could not clear it. The anchor is now a SECOND assertion:
        the file must exist AND actually contain the named entry -- a 388-line graveyard is
        non-empty whatever you failed to write in it."""
        (tmp_path / "docs").mkdir()
        g = tmp_path / "docs" / "graveyard.md"
        g.write_text("## `jp_bitflyer_direct_recording`\nmechanism: licence forbids it\n", "utf-8")
        it = MinedItem(source="d", name="bitFlyer", disposition="killed",
                       artifact="docs/graveyard.md `jp_bitflyer_direct_recording`")
        assert unbacked([it], backing={}, root=tmp_path) == (), "named entry present -> backed"

        missing = MinedItem(source="d", name="other", disposition="killed",
                            artifact="docs/graveyard.md `never_written`")
        assert unbacked([missing], backing={}, root=tmp_path) == (missing,), (
            "the file exists and is non-empty, but the entry it points at was never written -- "
            "that must NOT be credited, or the anchor is decoration")

    def test_a_bare_path_still_behaves_exactly_as_before(self, tmp_path) -> None:
        (tmp_path / "a.json").write_text("{}", "utf-8")
        ok = MinedItem(source="d", name="X", disposition="wired", artifact="a.json")
        assert unbacked([ok], backing={}, root=tmp_path) == ()
        gone = MinedItem(source="d", name="Y", disposition="wired", artifact="nope.json")
        assert unbacked([gone], backing={}, root=tmp_path) == (gone,)

    def test_deferred_is_never_artifact_checked(self) -> None:
        items = [MinedItem(source="d", name="Y", disposition="deferred",
                           deferred_until="2026-09-01")]
        assert unbacked(items, backing={}) == ()


class TestBareAnchorIsParsedNotSwallowed:
    """The backtick fix taught ONE precise form; every other attempt at precision scored worse.

    Measured 2026-08-05: three JP/BR cards wrote the anchor BARE --
    `docs/research/prospector_coverage.md JP-s1` -- which matched neither branch, so the whole
    string became a path that can never exist and the claims read as unbacked permanently. Same
    defect as the backtick case, one costume later.
    """

    def test_a_bare_anchor_is_checked_against_the_file(self, tmp_path) -> None:
        (tmp_path / "cov.md").write_text("...JP-s1 section...\n", "utf-8")
        it = MinedItem(source="d", name="X", disposition="screened", artifact="cov.md JP-s1")
        assert unbacked([it], backing={}, root=tmp_path) == (), "anchor present -> backed"

    def test_a_bare_anchor_that_is_absent_is_still_refused(self, tmp_path) -> None:
        """The whole point: parsing it must not CREDIT it. It must CHECK it."""
        (tmp_path / "cov.md").write_text("nothing relevant here\n", "utf-8")
        it = MinedItem(source="d", name="X", disposition="screened", artifact="cov.md JP-s1")
        assert unbacked([it], backing={}, root=tmp_path) == (it,)

    def test_a_real_path_containing_a_space_is_not_reinterpreted(self, tmp_path) -> None:
        """The bare reading is tried ONLY when the literal string is not itself a file."""
        (tmp_path / "my report.md").write_text("x\n", "utf-8")
        it = MinedItem(source="d", name="X", disposition="wired", artifact="my report.md")
        assert unbacked([it], backing={}, root=tmp_path) == (), "the literal path wins"


class TestBackingReasonSeparatesTypoFromFabrication:
    """A count is not a diagnosis, and these two need OPPOSITE actions.

    A mis-typed citation is fixed by correcting a string; an untrue claim must NEVER be fixed by
    correcting a string. Reported as one number they are indistinguishable to whoever picks them up.
    """

    def test_missing_path_says_so_and_teaches_the_anchor_form(self, tmp_path) -> None:
        it = MinedItem(source="d", name="X", disposition="wired", artifact="nope.json")
        why = backing_reason(it, backing={}, root=tmp_path)
        assert why.startswith("path-not-found")
        assert "path `anchor`" in why, "the message must name the form that would have worked"

    def test_absent_anchor_is_a_different_reason_from_a_missing_file(self, tmp_path) -> None:
        (tmp_path / "g.md").write_text("some other entry\n", "utf-8")
        it = MinedItem(source="d", name="X", disposition="killed", artifact="g.md `never_written`")
        assert backing_reason(it, backing={}, root=tmp_path).startswith("anchor-absent")

    def test_empty_file_is_its_own_reason(self, tmp_path) -> None:
        (tmp_path / "e.json").write_text("", "utf-8")
        it = MinedItem(source="d", name="X", disposition="wired", artifact="e.json")
        assert backing_reason(it, backing={}, root=tmp_path).startswith("path-empty")

    def test_stale_evidence_is_named_as_stale(self, tmp_path) -> None:
        p = tmp_path / "old.json"
        p.write_text("{}", "utf-8")
        os.utime(p, (1000, 1000))
        it = MinedItem(source="d", name="X", disposition="wired", artifact="old.json")
        why = backing_reason(it, backing={}, root=tmp_path, first_seen={"X": 2_000_000.0})
        assert why.startswith("stale-evidence")

    def test_a_backed_claim_has_no_reason(self, tmp_path) -> None:
        (tmp_path / "a.json").write_text("{}", "utf-8")
        it = MinedItem(source="d", name="X", disposition="wired", artifact="a.json")
        assert backing_reason(it, backing={}, root=tmp_path) == ""

    def test_reasons_and_the_tally_never_disagree(self, tmp_path) -> None:
        """One source of truth: `unbacked` is now derived from the reasons, not computed twice."""
        (tmp_path / "a.json").write_text("{}", "utf-8")
        items = [MinedItem(source="d", name="A", disposition="wired", artifact="a.json"),
                 MinedItem(source="d", name="B", disposition="wired", artifact="gone.json"),
                 MinedItem(source="d", name="C", disposition="screened", artifact="also-gone.md")]
        flagged = unbacked(items, backing={}, root=tmp_path)
        reasons = unbacked_reasons(items, backing={}, root=tmp_path)
        assert tuple(i for i, _ in reasons) == flagged
        assert len(flagged) == 2
        assert all(w for _, w in reasons)


class TestReport:
    def test_backlog_demands_conversion_first_but_never_throttles_mining(self) -> None:
        """AMENDED 2026-07-25 (principal directive): a backlog must NEVER stop, pause, or reduce
        mining -- unprocessed data is unrealized option value and living-web sources decay, so a
        suspended miner permanently loses that day's information. The backlog preempts the dig's
        PRIORITY (convert first, highest tier first) and the dig then keeps mining in the SAME
        run. `suspend_mining` survives only as a reporting signal for the max_audit defects; the
        verdict text must instruct conversion-then-continue, never 'catalogue nothing new'."""
        rep = conversion_report(parse_dispositions(_DOC, source="d"), as_of=_TODAY,
                                backing=_BACKING)
        assert rep.suspend_mining is True          # reporting signal only -- see mine_gate exit 0
        assert rep.n_backlog == 4
        assert "CONVERSION FIRST" in rep.verdict
        assert "CONTINUE MINING" in rep.verdict
        assert "never throttled" in rep.verdict
        assert "catalogue nothing new" not in rep.verdict

    def test_unbacked_claim_alone_suspends_mining(self) -> None:
        # the cheapest way to clear a backlog must NOT be typing the word "wired"
        items = [MinedItem(source="d", name="Upbit", disposition="wired")]
        rep = conversion_report(items, as_of=_TODAY, backing={})
        assert rep.suspend_mining is True and rep.n_unbacked == 1

    def test_fully_disposed_and_backed_authorises_mining(self) -> None:
        items = [MinedItem(source="d", name="Upbit", disposition="wired"),
                 MinedItem(source="d", name="Kaiko", disposition="killed")]
        rep = conversion_report(items, as_of=_TODAY,
                                backing={"wired": ["upbit_1m.jsonl"], "killed": ["kaiko index"]})
        assert rep.suspend_mining is False
        assert "backlog clear" in rep.verdict and rep.n_wired == 1 and rep.n_killed == 1

    def test_empty_owes_nothing(self) -> None:
        rep = conversion_report([], as_of=_TODAY)
        assert rep.suspend_mining is False and "nothing owed" in rep.verdict

    def test_counts_are_reported(self) -> None:
        rep = conversion_report(parse_dispositions(_DOC, source="d"), as_of=_TODAY,
                                backing=_BACKING)
        assert (rep.n_wired, rep.n_screened, rep.n_killed, rep.n_deferred) == (1, 1, 1, 1)
        assert rep.n_illegal == 2  # undated deferral + unknown verb


class TestTierWeighting:
    def test_defect_closer_is_tier1(self) -> None:
        assert infer_tier("Tardis ground truth for the diff-verify fence") == 1
        assert infer_tier("Upbit 1m backfill to 2017") == 1

    def test_prior_on_ingested_axis_is_tier2(self) -> None:
        assert infer_tier("premium-as-barrier-rent prior") == 2
        assert infer_tier("Naver attention thing", ingested_axes=["naver"]) == 2

    def test_operator_is_tier4(self) -> None:
        assert infer_tier("SMF printpage search operator") == 4

    def test_explicit_tag_overrides_the_heuristic(self) -> None:
        items = parse_dispositions("### 1. some operator [§33: deferred(2099-01-01) tier:1]\n",
                                   source="d")
        assert items[0].tier == 1  # heuristic would have said 4

    def test_weighted_backlog_prices_the_expensive_item(self) -> None:
        cheap = [MinedItem(source="d", name=f"op{i}", tier=4) for i in range(4)]
        one_t1 = [MinedItem(source="d", name="fence", tier=1)]
        assert conversion_report(one_t1, as_of=_TODAY).weighted_backlog > \
            conversion_report(cheap, as_of=_TODAY).weighted_backlog

    def test_priority_inversion_detected(self) -> None:
        items = [MinedItem(source="d", name="fence", tier=1),  # owes
                 MinedItem(source="d", name="op", tier=4, disposition="killed")]
        rep = conversion_report(items, as_of=_TODAY, backing={"killed": ["op"]})
        assert rep.priority_inversion is True and rep.top_tier_owing == 1


class TestKillQuality:
    def test_kill_spike_is_measured(self) -> None:
        items = [MinedItem(source="d", name=f"k{i}", disposition="killed") for i in range(4)]
        items.append(MinedItem(source="d", name="w", disposition="wired"))
        rep = conversion_report(items, as_of=_TODAY,
                                backing={"killed": [f"k{i}" for i in range(4)], "wired": ["w"]})
        assert rep.kill_share == 0.8  # 4 of 5 terminal


class TestFlowAndRatchet:
    def _ledger(self, tmp: Path) -> Path:
        lg = tmp / "led.jsonl"
        day = 86400.0
        base = datetime(2026, 7, 1, tzinfo=UTC)
        append_snapshot(lg, [MinedItem(source="w.md", name="A"),
                             MinedItem(source="w.md", name="B")], now=base)
        append_snapshot(lg, [MinedItem(source="w.md", name="A", disposition="wired"),
                             MinedItem(source="w.md", name="B")],
                        now=datetime.fromtimestamp(base.timestamp() + 2 * day, UTC))
        return lg

    def test_latency_derived_from_snapshots(self, tmp_path: Path) -> None:
        f = flow_stats(load_ledger(self._ledger(tmp_path)),
                       now=datetime(2026, 7, 10, tzinfo=UTC))
        assert f.n_converted == 1 and f.median_latency_days == 2.0

    def test_oldest_owing_is_tracked(self, tmp_path: Path) -> None:
        f = flow_stats(load_ledger(self._ledger(tmp_path)),
                       now=datetime(2026, 7, 10, tzinfo=UTC))
        assert f.oldest_owing_name == "B" and f.oldest_owing_days == 9.0

    def test_corrupt_line_does_not_lose_history(self, tmp_path: Path) -> None:
        lg = self._ledger(tmp_path)
        lg.write_text(lg.read_text("utf-8") + "{not json\n")
        assert len(load_ledger(lg)) == 2

    def test_ratchet_sets_a_record_then_tightens(self, tmp_path: Path) -> None:
        f = flow_stats(load_ledger(self._ledger(tmp_path)),
                       now=datetime(2026, 7, 10, tzinfo=UTC))
        r, v = update_ratchet(Ratchet(), f, conversion_rate=0.5)
        assert v.improved and r.best_median_latency_days == 2.0 and r.n_records == 1
        assert "RECORD" in v.verdict

    def test_ratchet_never_loosens_on_a_worse_cycle(self, tmp_path: Path) -> None:
        good = Ratchet(best_median_latency_days=2.0, best_conversion_rate=0.9)
        slow = FlowStats(n_snapshots=3, median_latency_days=20.0, p90_latency_days=20.0,
                         oldest_owing_days=0.0, oldest_owing_name="", n_converted=3,
                         latency_worsening=False)
        r, v = update_ratchet(good, slow, conversion_rate=0.1)
        assert v.regressed is True
        assert r.best_median_latency_days == 2.0   # record untouched by a bad cycle
        assert r.best_conversion_rate == 0.9

    def test_regression_measured_against_record_not_last_cycle(self, tmp_path: Path) -> None:
        # a slow drift downhill must not read as "fine" at every step
        best = Ratchet(best_median_latency_days=2.0)
        mid = FlowStats(n_snapshots=3, median_latency_days=3.5, p90_latency_days=4.0,
                        oldest_owing_days=0.0, oldest_owing_name="", n_converted=3,
                        latency_worsening=False)
        _, v = update_ratchet(best, mid, conversion_rate=0.0, regress_mult=1.5)
        assert v.regressed is True  # 3.5 > 2.0 * 1.5


class TestClosedLoop:
    def _mixed(self, tmp: Path) -> Path:
        lg = tmp / "l.jsonl"
        base = datetime(2026, 7, 1, tzinfo=UTC)
        good = [MinedItem(source="good.md", name=f"g{i}", disposition="wired") for i in range(4)]
        bad = [MinedItem(source="bad.md", name=f"b{i}") for i in range(4)]
        append_snapshot(lg, good + bad, now=base)
        append_snapshot(lg, good + bad,
                        now=datetime.fromtimestamp(base.timestamp() + 86400, UTC))
        return lg

    def test_priors_rank_by_measured_conversion(self, tmp_path: Path) -> None:
        priors = class_priors(load_ledger(self._mixed(tmp_path)))
        assert priors[0].source == "good.md" and priors[0].conversion_rate == 1.0
        assert priors[-1].source == "bad.md" and priors[-1].conversion_rate == 0.0

    def test_thin_class_is_omitted_not_shown_at_a_noisy_rate(self, tmp_path: Path) -> None:
        lg = tmp_path / "t.jsonl"
        append_snapshot(lg, [MinedItem(source="thin.md", name="x", disposition="wired")])
        assert class_priors(load_ledger(lg), min_seen=3) == ()

    def test_payload_names_what_to_favour_and_starve(self, tmp_path: Path) -> None:
        pay = priors_payload(class_priors(load_ledger(self._mixed(tmp_path))))
        assert "good.md" in pay["favour"] and "bad.md" in pay["starve"]

    def test_ignoring_the_priors_is_a_defect(self, tmp_path: Path) -> None:
        lg = self._mixed(tmp_path)
        priors = class_priors(load_ledger(lg))
        # next cycle piles MORE finds into the starved class
        append_snapshot(lg, [MinedItem(source="bad.md", name=f"new{i}") for i in range(5)],
                        now=datetime(2026, 8, 1, tzinfo=UTC))
        ok, why = feedback_applied(load_ledger(lg), priors, lookback=1)
        assert ok is False and "IGNORED" in why

    def test_following_the_priors_passes(self, tmp_path: Path) -> None:
        lg = self._mixed(tmp_path)
        priors = class_priors(load_ledger(lg))
        append_snapshot(lg, [MinedItem(source="good.md", name=f"new{i}") for i in range(5)],
                        now=datetime(2026, 8, 1, tzinfo=UTC))
        ok, _ = feedback_applied(load_ledger(lg), priors, lookback=1)
        assert ok is True


class TestExactArtifactCredit:
    def test_arrow_syntax_parses_the_path(self) -> None:
        i = parse_dispositions("### 1. Upbit [§33: wired -> data/upbit_1m.jsonl]\n", source="d")
        assert i[0].artifact == "data/upbit_1m.jsonl" and i[0].disposition == "wired"

    def test_at_syntax_also_parses(self) -> None:
        i = parse_dispositions("### 1. X [§33: screened @ reports/x.json]\n", source="d")
        assert i[0].artifact == "reports/x.json"

    def test_arrow_combines_with_tier(self) -> None:
        i = parse_dispositions("### 1. X [§33: wired tier:1 -> a/b.json]\n", source="d")
        assert i[0].tier == 1 and i[0].artifact == "a/b.json"

    def test_existing_nonempty_file_is_credited(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}")
        i = parse_dispositions("### 1. X [§33: wired -> a.json]\n", source="d")
        assert unbacked(i, backing={}, root=tmp_path) == ()

    def test_missing_file_is_unbacked_even_with_a_perfect_name_match(self, tmp_path: Path) -> None:
        # the exact path is AUTHORITATIVE -- naming a file that isn't there cannot be laundered
        # by a fuzzy name hit
        i = parse_dispositions("### 1. X [§33: wired -> gone.json]\n", source="d")
        assert unbacked(i, backing={"wired": ["x"]}, root=tmp_path) == tuple(i)

    def test_empty_stub_file_is_unbacked(self, tmp_path: Path) -> None:
        (tmp_path / "stub.json").write_text("")
        i = parse_dispositions("### 1. X [§33: wired -> stub.json]\n", source="d")
        assert unbacked(i, backing={}, root=tmp_path) == tuple(i)

    def test_directory_is_not_an_artifact(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        i = parse_dispositions("### 1. X [§33: wired -> d]\n", source="d")
        assert unbacked(i, backing={}, root=tmp_path) == tuple(i)

    def test_fuzzy_claims_are_counted_so_the_standard_can_ratchet(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}")
        i = parse_dispositions(
            "### 1. Exact [§33: wired -> a.json]\n### 2. Loose [§33: wired]\n", source="d")
        assert [x.name for x in fuzzy_credited(i)] == ["Loose"]
        rep = conversion_report(i, as_of=_TODAY, backing={"wired": ["loose"]}, root=tmp_path)
        assert rep.n_fuzzy_credited == 1 and rep.n_unbacked == 0


class TestTamperResistance:
    """Every remaining §33 bypass was the same shape: state that could be deleted or forged."""

    def _led(self, tmp: Path, names: list[str], *, disposed: tuple[str, ...] = ()) -> Path:
        lg = tmp / "l.jsonl"
        append_snapshot(lg, [
            MinedItem(source="d", name=n, disposition="wired" if n in disposed else "")
            for n in names], now=datetime(2026, 7, 1, tzinfo=UTC))
        return lg

    def test_deleting_the_card_does_not_delete_the_obligation(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["Tardis fence", "Upbit"])
        after = parse_dispositions("### 2. Upbit\n", source="d")   # card 1 edited away
        assert vanished(after, load_ledger(lg), as_of=_TODAY) == ("Tardis fence",)

    def test_disposing_an_item_is_not_an_erasure(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["Tardis"])
        done = parse_dispositions("### 1. Tardis [§33: killed]\n", source="d")
        assert vanished(done, load_ledger(lg), as_of=_TODAY) == ()

    def test_already_disposed_items_are_not_reported_as_vanished(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["A"], disposed=("A",))
        assert vanished([], load_ledger(lg), as_of=_TODAY) == ()

    def test_no_ledger_means_no_vanish_claims(self) -> None:
        assert vanished([], [], as_of=_TODAY) == ()

    def test_preexisting_file_cannot_receipt_a_new_find(self, tmp_path: Path) -> None:
        # `-> pyproject.toml` used to be credited: any old non-empty file was a valid receipt
        old = tmp_path / "old.json"
        old.write_text("{}")
        past = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        os.utime(old, (past, past))
        i = parse_dispositions("### 1. Tardis [§33: wired -> old.json]\n", source="d")
        fs = {"Tardis": datetime(2026, 7, 1, tzinfo=UTC).timestamp()}
        assert unbacked(i, backing={}, root=tmp_path, first_seen=fs) == tuple(i)

    def test_artifact_written_after_the_find_is_credited(self, tmp_path: Path) -> None:
        new = tmp_path / "new.json"
        new.write_text("{}")
        fs = {"Tardis": datetime(2026, 1, 1, tzinfo=UTC).timestamp()}
        i = parse_dispositions("### 1. Tardis [§33: wired -> new.json]\n", source="d")
        assert unbacked(i, backing={}, root=tmp_path, first_seen=fs) == ()

    def test_recency_is_skipped_when_the_find_has_no_history(self, tmp_path: Path) -> None:
        old = tmp_path / "old.json"
        old.write_text("{}")
        past = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        os.utime(old, (past, past))
        i = parse_dispositions("### 1. New [§33: wired -> old.json]\n", source="d")
        assert unbacked(i, backing={}, root=tmp_path, first_seen={}) == ()

    def test_truncated_ledger_is_detected(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["A"])
        r = Ratchet(n_snapshots=5, earliest_ts=1000.0)
        bad, why = ledger_regressed(r, load_ledger(lg))
        assert bad and "truncated" in why

    def test_rewritten_history_is_detected(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["A"])   # ts = 2026-07-01
        r = Ratchet(n_snapshots=1, earliest_ts=1.0)   # record says history began long ago
        bad, why = ledger_regressed(r, load_ledger(lg))
        assert bad and "rewritten" in why

    def test_intact_ledger_passes(self, tmp_path: Path) -> None:
        lg = self._led(tmp_path, ["A"])
        led = load_ledger(lg)
        r = Ratchet(n_snapshots=1, earliest_ts=float(led[0]["ts"]))
        assert ledger_regressed(r, led)[0] is False

    def test_first_record_has_nothing_to_compare(self, tmp_path: Path) -> None:
        assert ledger_regressed(Ratchet(), load_ledger(self._led(tmp_path, ["A"])))[0] is False

    def test_ratchet_captures_ledger_high_water_marks(self, tmp_path: Path) -> None:
        led = load_ledger(self._led(tmp_path, ["A"]))
        flow = flow_stats(led)
        r, _ = update_ratchet(Ratchet(), flow, conversion_rate=0.0, ledger=led)
        assert r.n_snapshots == 1 and r.earliest_ts == float(led[0]["ts"])


class TestLawSelfAudit:
    def _ledger(self, tmp: Path, rows: list[list[tuple[str, int, bool]]]) -> Path:
        lg = tmp / "sa.jsonl"
        base = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        for k, row in enumerate(rows):
            append_snapshot(lg, [
                MinedItem(source="d", name=n, tier=t,
                          disposition="wired" if done else "")
                for n, t, done in row],
                now=datetime.fromtimestamp(base + k * 86400, UTC))
        return lg

    def test_inverted_tier_weights_are_detected(self, tmp_path: Path) -> None:
        # T1 items never finish while T4 items all do -> the weighting misdirects effort
        row = ([(f"t1_{i}", 1, False) for i in range(4)]
               + [(f"t4_{i}", 4, True) for i in range(4)])
        cal = tier_calibration(load_ledger(self._ledger(tmp_path, [row, row])))
        assert cal.inverted is True and "INVERTED" in cal.verdict

    def test_healthy_tiers_pass(self, tmp_path: Path) -> None:
        row = ([(f"t1_{i}", 1, True) for i in range(4)]
               + [(f"t4_{i}", 4, False) for i in range(4)])
        cal = tier_calibration(load_ledger(self._ledger(tmp_path, [row, row])))
        assert cal.inverted is False

    def test_thin_history_is_not_a_defect(self, tmp_path: Path) -> None:
        cal = tier_calibration(load_ledger(self._ledger(tmp_path, [[("a", 1, False)]])))
        assert cal.inverted is False and "insufficient" in cal.verdict

    def test_law_is_not_judged_too_early(self, tmp_path: Path) -> None:
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, [[("a", 3, False)]])))
        assert eff.conclusive is False and "too early" in eff.verdict

    def test_flat_conversion_indicts_the_law(self, tmp_path: Path) -> None:
        """Nothing ever converts. Widened from 3 to 6 items per window when the sample-size gate
        landed -- the CLAIM is unchanged, it just now has enough evidence behind it to be made."""
        rows = [[(f"x{i}", 3, False) for i in range(6)] for _ in range(12)]
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, rows)))
        assert eff.conclusive and eff.improving is False
        assert "ceremony with good telemetry" in eff.verdict

    def test_a_zero_rate_is_convicted_on_its_LEVEL_without_needing_a_trend(
            self, tmp_path: Path
    ) -> None:
        """A law under which nothing converts is failing whether or not the rate moved. Judging
        only the derivative would exonerate the worst possible state for being CONSISTENTLY the
        worst -- 0% to 0% is flat, and flatness is the least interesting thing about it."""
        rows = [[(f"x{i}", 3, False) for i in range(6)] for _ in range(12)]
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, rows)))
        assert eff.late_rate == 0.0
        assert eff.conclusive is True, "zero conversions must never report as inconclusive"
        assert "no trend argument can rescue a rate of zero" in eff.verdict

    def test_rising_conversion_clears_the_law(self, tmp_path: Path) -> None:
        early = [[(f"e{i}", 3, False) for i in range(6)] for _ in range(6)]
        late = [[(f"l{i}", 3, True) for i in range(6)] for _ in range(6)]
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, early + late)))
        assert eff.conclusive and eff.improving is True
        assert "the law is working" in eff.verdict

    def test_a_rate_built_on_two_items_cannot_convict_the_law(self, tmp_path: Path) -> None:
        """THE LIVE BUG. min_snapshots gates how often the ledger was WRITTEN; the rate rests on
        how many distinct ITEMS were seen, and the production ledger had 62 of the former and 2 of
        the latter. It reported 40% -> 40% and called §33 "ceremony with good telemetry" from a
        sample where one item flipping moves the rate fifty points -- committed by the organ that
        enforces the evidence standard on everything else."""
        early = [[("e1", 3, False), ("e2", 3, True)] for _ in range(6)]
        late = [[("l1", 3, False), ("l2", 3, True)] for _ in range(6)]
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, early + late)))
        assert eff.conclusive is False
        assert eff.n_early_items < 5 and eff.n_late_items < 5
        assert "distinct items per window" in eff.verdict
        assert "never how much evidence it holds" in eff.verdict

    def test_a_one_point_move_is_not_a_trend(self, tmp_path: Path) -> None:
        """Two proportions differing slightly are not evidence of improvement. Comparing raw point
        estimates is exactly what libs/doctrine/estimate.py exists to stop the rest of the desk
        doing, and this function was doing it with `>`."""
        early = [[(f"e{i}", 3, i < 3) for i in range(8)] for _ in range(6)]
        late = [[(f"l{i}", 3, i < 4) for i in range(8)] for _ in range(6)]
        eff = law_effectiveness(load_ledger(self._ledger(tmp_path, early + late)))
        assert eff.late_rate > eff.early_rate, "the point estimate really did rise -- the trap"
        assert eff.improving is False, "a 12pp move on n=8 is noise, not a working law"


class TestAmbiguousRewriteSignal:
    """A fresh clone and a rewritten history are STRUCTURALLY IDENTICAL, and the check says so.

    data/ is gitignored, so any fresh checkout starts an empty ledger and fills it one row per
    audit invocation. Every row then postdates the recorded earliest at an unchanged or higher
    count -- the same signature as a rewrite that replaced old rows with new ones.

    A carve-out exempting "disjoint history" was written and REVERTED: `n >= n_snapshots` holds for
    both cases, so exempting it converted a false positive into a false NEGATIVE on the only
    detector of the desk's evidence base being erased. Between those two errors this one is the
    cheap one -- an accusation can be checked, a silent deletion cannot be noticed. So the verdict
    stands and the ambiguity moves into the message.
    """

    @staticmethod
    def _rat(n, earliest):
        return Ratchet(n_snapshots=n, earliest_ts=earliest)

    def test_the_signal_still_fires_because_it_cannot_safely_be_suppressed(self) -> None:
        led = [{"ts": 2000.0 + i, "items": []} for i in range(90)]
        bad, _ = ledger_regressed(self._rat(89, 1000.0), led)
        assert bad is True

    def test_the_message_names_the_environment_explanation(self) -> None:
        """What stops a reader -- this one, on 2026-08-02 -- filing a container artifact as a desk
        defect. The check cannot resolve the ambiguity; it can refuse to hide it."""
        led = [{"ts": 2000.0 + i, "items": []} for i in range(90)]
        _, why = ledger_regressed(self._rat(89, 1000.0), led)
        assert "CHECK THE ENVIRONMENT BEFORE THE CONCLUSION" in why
        assert "gitignored" in why and "having deleted nothing" in why

    def test_the_message_carries_the_numbers_needed_to_decide(self) -> None:
        led = [{"ts": 2000.0 + i, "items": []} for i in range(90)]
        _, why = ledger_regressed(self._rat(89, 1000.0), led)
        assert "2000" in why and "1000" in why and "90 rows" in why

    def test_a_genuinely_truncated_history_is_STILL_caught(self) -> None:
        led = [{"ts": 1000.0 + i, "items": []} for i in range(10)]
        bad, why = ledger_regressed(self._rat(89, 1000.0), led)
        assert bad is True and "truncated or deleted" in why

    def test_an_intact_ledger_still_reads_intact(self) -> None:
        led = [{"ts": 1000.0 + i, "items": []} for i in range(120)]
        bad, why = ledger_regressed(self._rat(89, 1000.0), led)
        assert bad is False and why == "ledger intact"


class TestSnapshotCountIsMachineLocal:
    """THE AUDITOR WAS MANUFACTURING ITS OWN DEFECT, ONCE PER RUN, FOREVER.

    `append_snapshot` adds one ledger row per max_audit invocation, so `n_snapshots` advanced on
    every sweep. The ratchet -- a GIT-TRACKED file -- was rewritten unconditionally, so the working
    tree was dirty after every run and the next check duly reported `dig-output-uncommitted`. The
    only way to keep it green was to commit after every audit. A defect that can only be cleared by
    ceremony is noise, and it was crowding out the defects that matter.

    The count is also the wrong thing to commit on its own terms: data/ is gitignored, so a clone's
    ledger starts empty and its count has nothing to do with the count the VPS reached. Comparing
    the two reports truncation on a machine that has deleted nothing.
    """

    def _led(self, tmp_path, names, ts=1000.0):
        p = tmp_path / "led.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for i, n in enumerate(names):
                fh.write(json.dumps({"ts": ts + i, "items": [{"n": n, "s": "x", "d": "owing",
                                                              "t": 1}]}) + "\n")
        return p

    def test_a_clone_is_not_accused_of_truncating_the_vps_ledger(self, tmp_path) -> None:
        """The committed ratchet says 113 snapshots; this machine's ledger holds 2. Judged against
        the committed figure that is 'the ledger was truncated'. Judged against THIS machine's own
        previous count -- which is what the sweep now passes -- it is a clone doing its second run.
        """
        led = load_ledger(self._led(tmp_path, ["A", "B"]))
        committed = Ratchet(n_snapshots=113, earliest_ts=1000.0)
        assert ledger_regressed(committed, led)[0] is True          # the old, cross-machine test
        assert ledger_regressed(committed, led, local_n_prior=1)[0] is False

    def test_a_genuine_local_truncation_still_fires(self, tmp_path) -> None:
        """The false positive is removed WITHOUT removing the detector. This machine recorded 5
        snapshots and now holds 2: rows were deleted here, and that must still be seen."""
        led = load_ledger(self._led(tmp_path, ["A", "B"]))
        r = Ratchet(n_snapshots=113, earliest_ts=1000.0)
        bad, why = ledger_regressed(r, led, local_n_prior=5)
        assert bad is True
        assert "5 -> 2" in why

    def test_omitting_local_state_preserves_the_original_behaviour(self, tmp_path) -> None:
        """Callers with no machine-local state must be unaffected -- the parameter is additive."""
        led = load_ledger(self._led(tmp_path, ["A", "B"]))
        r = Ratchet(n_snapshots=5, earliest_ts=1000.0)
        assert ledger_regressed(r, led) == ledger_regressed(r, led, local_n_prior=None)


class TestStableIdentityAcrossRegrades:
    """A re-graded card is the same find under a new assessment, never a rename (2026-08-11:
    one re-graded T3 card reported vanished and six same-run conversions reported unbacked)."""

    def test_a_regrade_is_not_a_vanish(self, tmp_path: Path) -> None:
        lg = tmp_path / "led.jsonl"
        append_snapshot(lg, [MinedItem(
            source="d", name="Foreign AI-quant systems — grade: UNVERIFIED", disposition="")],
            now=datetime(2026, 7, 1, tzinfo=UTC))
        after = parse_dispositions(
            "### 1. Foreign AI-quant systems — grade: verified + MINED [§33: wired -> x.md]\n",
            source="d")
        assert vanished(after, load_ledger(lg), as_of=_TODAY) == ()

    def test_a_regrade_does_not_reset_first_seen(self, tmp_path: Path) -> None:
        lg = tmp_path / "led.jsonl"
        append_snapshot(lg, [MinedItem(
            source="d", name="Grouping map — grade: UNVERIFIED", disposition="")],
            now=datetime(2026, 7, 1, tzinfo=UTC))
        append_snapshot(lg, [MinedItem(
            source="d", name="Grouping map — grade: BUILT 2026-08-11", disposition="wired")],
            now=datetime(2026, 8, 11, tzinfo=UTC))
        fs = first_seen_map(load_ledger(lg))
        assert fs[stable_key("Grouping map — grade: anything at all")] == \
            datetime(2026, 7, 1, tzinfo=UTC).timestamp()

    def test_evidence_between_carding_and_regrade_is_credited(self, tmp_path: Path) -> None:
        art = tmp_path / "map.json"
        art.write_text("{}")
        mid = datetime(2026, 8, 1, tzinfo=UTC).timestamp()
        os.utime(art, (mid, mid))
        i = parse_dispositions(
            "### 1. Grouping map — grade: BUILT [§33: wired -> map.json]\n", source="d")
        fs = {stable_key("Grouping map — grade: UNVERIFIED"):
              datetime(2026, 7, 1, tzinfo=UTC).timestamp()}
        assert unbacked(i, backing={}, root=tmp_path, first_seen=fs) == ()

    def test_a_genuinely_preexisting_file_still_fails_after_the_fix(self, tmp_path: Path) -> None:
        art = tmp_path / "old.json"
        art.write_text("{}")
        past = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        os.utime(art, (past, past))
        i = parse_dispositions(
            "### 1. Grouping map — grade: BUILT [§33: wired -> old.json]\n", source="d")
        fs = {stable_key("Grouping map — grade: UNVERIFIED"):
              datetime(2026, 7, 1, tzinfo=UTC).timestamp()}
        assert unbacked(i, backing={}, root=tmp_path, first_seen=fs) == tuple(i)


class TestDeferredOwingClock:
    """A DATED, UNEXPIRED deferral is a disposition (§33): it must silence the owing clock
    without resetting it. The Upbit false positive: mine-flow-rotting fired at 17d on a card
    carrying a legal deferred(2026-08-15) because append_snapshot dropped the date and
    flow_stats counted every non-terminal item as owing."""

    def _ledger(self, tmp: Path) -> Path:
        lg = tmp / "led.jsonl"
        base = datetime(2026, 7, 1, tzinfo=UTC)
        append_snapshot(lg, [MinedItem(source="w.md", name="D"),
                             MinedItem(source="w.md", name="B")], now=base)
        append_snapshot(
            lg, [MinedItem(source="w.md", name="D", disposition="deferred",
                           deferred_until="2026-08-15"),
                 MinedItem(source="w.md", name="B")],
            now=datetime(2026, 7, 3, tzinfo=UTC))
        return lg

    def test_snapshot_retains_the_deferral_date(self, tmp_path: Path) -> None:
        rows = load_ledger(self._ledger(tmp_path))
        d_item = next(i for i in rows[-1]["items"] if i["n"] == "D")
        assert d_item["u"] == "2026-08-15"

    def test_unexpired_deferral_is_not_owing(self, tmp_path: Path) -> None:
        f = flow_stats(load_ledger(self._ledger(tmp_path)),
                       now=datetime(2026, 7, 20, tzinfo=UTC))
        assert f.oldest_owing_name == "B", "the dated, unexpired deferral must not age as owing"

    def test_expired_deferral_resumes_at_original_age_not_zero(self, tmp_path: Path) -> None:
        f = flow_stats(load_ledger(self._ledger(tmp_path)),
                       now=datetime(2026, 8, 20, tzinfo=UTC))
        assert f.oldest_owing_name in ("D", "B")
        assert f.oldest_owing_days == 50.0, "deferral buys silence, not youth: age is first_seen"

    def test_undated_deferral_still_ages_as_owing(self, tmp_path: Path) -> None:
        lg = tmp_path / "old.jsonl"
        base = datetime(2026, 7, 1, tzinfo=UTC)
        append_snapshot(lg, [MinedItem(source="w.md", name="OLD", disposition="deferred")],
                        now=base)
        f = flow_stats(load_ledger(lg), now=datetime(2026, 7, 20, tzinfo=UTC))
        assert f.oldest_owing_name == "OLD", "old-format rows (no date) stay conservative"
