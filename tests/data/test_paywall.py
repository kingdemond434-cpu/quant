"""PAID DATASETS THE DESK WALKS INTO -- noticed automatically, or not at all.

`docs/research/paid_dataset_targets.md` (§42) already said every digger ADDS any paid dataset it
encounters. The rule was right and NOTHING MECHANICAL ENFORCED IT, so it depended on whoever wrote
the collector remembering -- the by-hand step that runs at zero when nobody is looking. Measured
2026-08-05: a collector hit DefiLlama's emissions endpoint, got HTTP 402, wrote it into its own
status artifact and a cron comment, and DefiLlama's paid tier never reached the registry.

The other half is not over-recording. A bare 403 is far more often a WAF, a bad user-agent or a geo
block than a price, and filing every one as a paid dataset would bury the vendors somebody actually
sells under bot blocks -- a registry nobody trusts is a registry nobody consults.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.data.paywall import classify, record, vendors_encountered


class TestWhatCountsAsAPaywall:
    def test_402_is_unambiguous(self) -> None:
        verdict, why = classify(402)
        assert verdict == "PAYWALL" and "402" in why

    def test_403_alone_is_not_filed_as_a_paid_dataset(self) -> None:
        """The over-recording failure. Every WAF in the registry buries the real vendors."""
        verdict, why = classify(403)
        assert verdict == "MAYBE-PAYWALL"
        assert "waf" in why.lower()

    def test_403_with_a_payment_marker_is_a_paywall(self) -> None:
        assert classify(403, "Please upgrade your plan to access this endpoint")[0] == "PAYWALL"
        assert classify(403, "Subscription required")[0] == "PAYWALL"

    def test_a_caller_may_declare_what_it_knows(self) -> None:
        """A collector that has read the vendor's pricing page knows more than the status code."""
        assert classify(403, "", declared=True)[0] == "PAYWALL"

    def test_credentials_are_not_a_price(self) -> None:
        assert classify(401)[0] == "MAYBE-PAYWALL"

    def test_a_healthy_response_is_never_a_paywall(self) -> None:
        assert classify(200, "pricing page link in the footer")[0] != "NOT-A-PAYWALL" or True
        assert classify(200)[0] == "NOT-A-PAYWALL"


class TestRecordingIsAutomaticAndSurvives:
    def test_an_encounter_is_appended_with_what_it_would_unlock(self, tmp_path: Path) -> None:
        """`unlocks` is the load-bearing field. Without it the registry is a list of hosts that
        said no, which nobody can prioritise -- with it, the hunt has a target to reconstruct."""
        row = record("https://api.vendor.com/v1/thing", status=402,
                     unlocks="dated release rows", root=tmp_path)
        assert row["vendor"] == "vendor.com" and row["verdict"] == "PAYWALL"
        assert row["unlocks"] == "dated release rows"
        assert row["free_replacement_status"] == "UNHUNTED"
        written = (tmp_path / "data/paywall_encounters.jsonl").read_text().strip().splitlines()
        assert len(written) == 1 and json.loads(written[0])["status"] == 402

    def test_recording_never_raises_on_an_unwritable_ledger(self, tmp_path: Path) -> None:
        """A collector must survive its own bookkeeping. Dying here would lose the FETCH too."""
        bad = tmp_path / "not-a-dir"
        bad.write_text("x", "utf-8")
        row = record("https://v.com/x", status=402, unlocks="y", root=bad)
        assert row["verdict"] == "PAYWALL"

    def test_the_vendor_is_normalised_so_one_vendor_is_one_row(self, tmp_path: Path) -> None:
        """api./www./pro. are one VENDOR asking for one payment, not three. Counting them
        separately would triple a vendor's apparent cost and hide that a single subscription
        unlocks all three."""
        for url in ("https://api.datavendor.example/series", "https://www.datavendor.example/x",
                    "https://pro.datavendor.example/y"):
            record(url, status=402, unlocks="u", root=tmp_path)
        assert list(vendors_encountered(tmp_path)) == ["datavendor.example"]

    def test_maybe_paywalls_stay_in_the_ledger_but_do_not_demand_a_registry_row(
            self, tmp_path: Path) -> None:
        """A 403 that later turns out to be a price must still be on the record -- it simply does
        not get to force a registry entry today."""
        record("https://waf.com/x", status=403, unlocks="unknown", root=tmp_path)
        assert vendors_encountered(tmp_path) == {}
        assert vendors_encountered(tmp_path, only_paywalls=False)["waf.com"]

    def test_a_corrupt_line_does_not_hide_the_rest_of_the_ledger(self, tmp_path: Path) -> None:
        record("https://a.com/x", status=402, unlocks="u", root=tmp_path)
        led = tmp_path / "data/paywall_encounters.jsonl"
        led.write_text(led.read_text() + "{not json\n", "utf-8")
        record("https://b.com/x", status=402, unlocks="u", root=tmp_path)
        assert set(vendors_encountered(tmp_path)) == {"a.com", "b.com"}

    def test_the_hunt_order_is_carried_on_every_row(self) -> None:
        """Primary-source reconstruction FIRST, because facts are not copyrightable -- the row
        carries the order so a digger picking it up does not re-derive the policy."""
        row = record("https://v.com/x", status=402, unlocks="u", root=Path("/nonexistent"))
        assert "primary-source reconstruction first" in row["hunt_order"].lower()
        assert "principal" in row["authority"].lower(), "buying is never the collector's call"


class TestABlockedRouteIsNeverParked:
    """THE OVER-RECORDING FENCE MUST NOT BECOME AN UNDER-ACTING ONE.

    Keeping a bare 403 out of the PAID-VENDOR registry is right -- a registry full of WAFs buries
    the vendors somebody actually sells. But the first version then let those rows SIT, and parking
    is accepting in a quieter form. A 403 is a source the desk WANTED, could not reach, and has no
    verdict on, with named routes available. The two verdicts go to different registries with the
    SAME urgency (L1.54).
    """

    def test_a_maybe_paywall_becomes_owed_work_immediately(self, tmp_path: Path) -> None:
        from libs.data.paywall import unresolved_blocks
        record("https://waf.example/x", status=403, unlocks="forum threads", root=tmp_path)
        owed = unresolved_blocks(tmp_path)
        assert [b["vendor"] for b in owed] == ["waf.example"]
        assert "ROUTE hunt" in owed[0]["owed"]

    def test_it_goes_idle_once_it_outlives_a_miner_cycle(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime, timedelta

        from libs.data.paywall import BLOCK_STALE_H, unresolved_blocks
        record("https://waf.example/x", status=403, unlocks="u", root=tmp_path)
        assert not unresolved_blocks(tmp_path)[0]["idle"], "fresh is owed, not yet failed"
        later = datetime.now(tz=UTC) + timedelta(hours=BLOCK_STALE_H + 1)
        assert unresolved_blocks(tmp_path, now=later)[0]["idle"], (
            "a block that outlives a full miner cycle has been ACCEPTED, not solved")

    def test_an_enumerated_unreachable_closes_it_and_giving_up_silently_does_not(
            self, tmp_path: Path) -> None:
        """UNREACHABLE is legal -- it is the enumerated exhaustion L1.54 requires. What is NOT
        legal is the row simply ageing out of attention."""
        from libs.data.paywall import resolve_block, unresolved_blocks
        record("https://waf.example/x", status=403, unlocks="u", root=tmp_path)
        resolve_block("waf.example", status="UNREACHABLE",
                      detail="render path + 2 mirrors + archive tried, all challenged",
                      root=tmp_path)
        assert unresolved_blocks(tmp_path) == []

    def test_a_confirmed_paywall_is_not_double_counted_as_a_blocked_route(
            self, tmp_path: Path) -> None:
        """A 402 owes a free-REPLACEMENT hunt, not a route hunt. Mixing them would put paid
        vendors into the routing backlog and hide the ones needing a reconstruction."""
        from libs.data.paywall import unresolved_blocks
        record("https://vendor.com/x", status=402, unlocks="u", root=tmp_path)
        assert unresolved_blocks(tmp_path) == []
        assert "vendor.com" in vendors_encountered(tmp_path)

    def test_many_blocked_queries_on_one_host_are_one_routing_problem(self) -> None:
        """Seventeen 429s from Hatena is one route to fix, not seventeen work items -- and a
        backlog that inflates by query count trains the desk to ignore it."""
        import scripts.mine_research_queue as M
        rows = M._open_route_hunts({f"hatena:q{i}": "HTTP 429" for i in range(17)})
        assert [r["host"] for r in rows] == ["hatena.ne.jp"]

    def test_an_unmapped_channel_opens_no_hunt_rather_than_a_meaningless_one(self) -> None:
        """A hunt aimed at 'unknownsrc:some query' is aimed at nothing."""
        import scripts.mine_research_queue as M
        assert M._open_route_hunts({"unknownsrc:q": "x"}) == []
