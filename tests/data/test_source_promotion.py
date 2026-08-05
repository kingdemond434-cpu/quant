"""REPLACEMENT, not cataloguing -- the third of the three halves the desk was missing.

`source_alternatives` holds candidates. `paywall` records paid datasets and demands a hunt. Neither
could SWAP anything, so a genuinely better free route could be found, verified, written into a
registry row, and the desk would keep calling the old one forever. Hunting without replacing is
cataloguing.

The two directions that matter, both tested here. A bar too LOOSE silently degrades every
downstream number by adopting a source nobody measured. A bar too TIGHT means the hunt never pays
and the desk keeps its incumbents out of inertia.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.data.source_promotion import (
    INSUFFICIENT,
    KEEP,
    PROMOTE,
    REFUSED,
    RouteEvidence,
    active_route,
    evaluate,
    promote,
)


def _good(**kw) -> RouteEvidence:
    base = {"name": "cand", "information_class": "unlock_calendar", "usable_rows": 500,
            "licence": "MIT", "is_paid": False, "stamps_known_from": True}
    base.update(kw)
    return RouteEvidence(**base)


class TestGenuineMeansMeasured:
    def test_an_unprobed_candidate_is_never_promoted_on_optimism(self) -> None:
        v = evaluate(_good(usable_rows=None), None)
        assert v.verdict == INSUFFICIENT
        assert any("usable_rows" in m for m in v.missing)

    def test_an_unread_licence_blocks_promotion(self) -> None:
        """UNKNOWN blocks deliberately: adopting a source whose terms nobody read is how a desk
        acquires an obligation it cannot see."""
        v = evaluate(_good(licence="UNKNOWN"), None)
        assert v.verdict == INSUFFICIENT
        assert any("licence" in m for m in v.missing)

    def test_the_missing_field_is_named_so_the_next_hunt_knows_what_to_measure(self) -> None:
        v = evaluate(RouteEvidence("c", "x"), None)
        assert v.verdict == INSUFFICIENT and len(v.missing) == 3

    def test_a_probed_but_empty_source_is_refused_not_merely_unmeasured(self) -> None:
        """200-with-an-empty-list and 200-with-an-anti-bot-page are not working sources."""
        assert evaluate(_good(usable_rows=0), None).verdict == REFUSED

    def test_a_non_permissive_licence_is_refused_however_good_the_data(self) -> None:
        """Coin Metrics was excluded on exactly this ground with perfect data."""
        v = evaluate(_good(licence="CC-BY-NC"), None)
        assert v.verdict == REFUSED and "licence" in v.why.lower()

    def test_a_route_that_cannot_stamp_known_from_is_refused_on_the_hard_axis(self) -> None:
        """A point-in-time series with no knowability stamp silently reintroduces look-ahead,
        which no downstream statistic would reveal -- so it never trades off against price."""
        v = evaluate(_good(stamps_known_from=False, is_paid=False), None)
        assert v.verdict == REFUSED and "look-ahead" in v.why


class TestReplacementActuallyHappens:
    def test_a_verified_candidate_replaces_nothing_with_something(self) -> None:
        v = evaluate(_good(), None)
        assert v.verdict == PROMOTE and "exists" in v.better_on

    def test_free_beats_paid_on_the_same_class(self) -> None:
        """THE CASE THE PRINCIPAL ASKED FOR: hunt a genuine alternative, then REPLACE."""
        incumbent = _good(name="paid_vendor", is_paid=True, licence="PRIMARY-SOURCE",
                          usable_rows=500)
        v = evaluate(_good(name="free_route"), incumbent)
        assert v.verdict == PROMOTE and "free vs paid" in v.better_on

    def test_a_dead_incumbent_is_replaced_by_anything_that_works(self) -> None:
        dead = _good(name="incumbent", usable_rows=0)
        v = evaluate(_good(name="alive"), dead)
        assert v.verdict == PROMOTE
        assert any("died" in b for b in v.better_on)

    def test_wider_coverage_is_a_promotion_reason(self) -> None:
        v = evaluate(_good(usable_rows=5000), _good(name="old", usable_rows=500))
        assert v.verdict == PROMOTE
        assert any("more rows" in b for b in v.better_on)

    def test_future_better_alternatives_keep_replacing_the_current_one(self) -> None:
        """A route is never permanent because it was first. The GENERAL case the principal
        asked for, not only the paywall one: better turns up, better replaces."""
        first = _good(name="v1", usable_rows=100)
        second = _good(name="v2", usable_rows=900)
        assert evaluate(second, first).verdict == PROMOTE
        third = _good(name="v3", usable_rows=9000)
        assert evaluate(third, second).verdict == PROMOTE


class TestChurnAndBuyingAreBothRefused:
    def test_an_equal_candidate_is_kept_as_a_standby_not_swapped_in(self) -> None:
        """Churn costs the desk its comparability. A working alternative that beats the incumbent
        on nothing is a standby, not an upgrade."""
        v = evaluate(_good(name="equal"), _good(name="incumbent"))
        assert v.verdict == KEEP and not v.better_on

    def test_a_paid_candidate_never_displaces_a_free_incumbent(self) -> None:
        """Buying is the principal's decision, never a promotion rule."""
        v = evaluate(_good(name="paid", is_paid=True, usable_rows=99999),
                     _good(name="free", is_paid=False, usable_rows=10))
        assert v.verdict == REFUSED and "principal" in v.why

    def test_a_substitute_that_changes_the_question_is_not_a_replacement(self) -> None:
        v = evaluate(_good(information_class="something_else"),
                     _good(information_class="unlock_calendar"))
        assert v.verdict == REFUSED and "different dataset" in v.why


class TestTheSwapIsLedgeredAndReversible:
    def test_promoting_writes_the_live_route_and_the_history(self, tmp_path: Path) -> None:
        out = promote(_good(name="free_route"), root=tmp_path)
        assert out["verdict"] == PROMOTE and out.get("swapped")
        live = active_route("unlock_calendar", tmp_path)
        assert live and live.name == "free_route"
        ledger = (tmp_path / "data/route_swaps.jsonl").read_text().strip().splitlines()
        assert len(ledger) == 1 and json.loads(ledger[0])["verdict"] == PROMOTE

    def test_the_displaced_route_stays_named_so_a_rollback_knows_where_to_go(
            self, tmp_path: Path) -> None:
        promote(_good(name="v1"), root=tmp_path)
        out = promote(_good(name="v2", usable_rows=9000), root=tmp_path)
        assert out["incumbent"]["name"] == "v1"
        doc = json.loads((tmp_path / "data/active_routes.json").read_text())
        assert doc["unlock_calendar"]["replaced"] == "v1"

    def test_a_refused_candidate_changes_nothing(self, tmp_path: Path) -> None:
        promote(_good(name="incumbent"), root=tmp_path)
        out = promote(_good(name="unlicensed", licence="CC-BY-NC"), root=tmp_path)
        assert out["verdict"] == REFUSED and not out.get("swapped")
        live = active_route("unlock_calendar", tmp_path)
        assert live and live.name == "incumbent", "a refusal must not swap anything"

    def test_an_override_is_recorded_as_an_override(self, tmp_path: Path) -> None:
        """force= exists for a human decision the rules cannot express. It must never be
        indistinguishable from a clean promotion in the record."""
        out = promote(_good(usable_rows=0), root=tmp_path, force=True)
        assert out.get("swapped") and "forced" in out
