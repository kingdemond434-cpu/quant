"""R0526: the backlog's delay bill, and the three ways a row refuses to be priced."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.ops.delay_cost import ORDINAL_BPS, measure

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


def _row(rid: str, *, roi_bps: object = 40.0, due_days_ago: float | None = None,
         raised_days_ago: float | None = None, status: str = "scheduled") -> dict:
    r: dict = {"id": rid, "status": status, "summary": f"row {rid}"}
    if roi_bps is not None:
        r["roi_bps"] = roi_bps
    if due_days_ago is not None:
        r["due"] = (NOW - timedelta(days=due_days_ago)).isoformat()
    if raised_days_ago is not None:
        r["raised"] = (NOW - timedelta(days=raised_days_ago)).isoformat()
    return r


class TestPricing:
    def test_cost_is_roi_times_age(self) -> None:
        d = measure([_row("R1", roi_bps=40.0, due_days_ago=10)], now=NOW)
        assert d.total_bps_days == 400.0
        assert d.priced[0].days_overdue == 10.0

    def test_a_longer_delay_on_the_same_row_costs_strictly_more(self) -> None:
        short = measure([_row("R1", due_days_ago=2)], now=NOW).total_bps_days
        long_ = measure([_row("R1", due_days_ago=20)], now=NOW).total_bps_days
        assert long_ > short

    def test_a_more_valuable_row_at_equal_age_costs_strictly_more(self) -> None:
        cheap = measure([_row("R1", roi_bps=2.0, due_days_ago=10)], now=NOW).total_bps_days
        rich = measure([_row("R2", roi_bps=400.0, due_days_ago=10)], now=NOW).total_bps_days
        assert rich > cheap

    def test_top_orders_the_queue(self) -> None:
        d = measure([_row("SMALL", roi_bps=5.0, due_days_ago=3),
                     _row("BIG", roi_bps=300.0, due_days_ago=9)], now=NOW)
        assert [p.rid for p in d.top()] == ["BIG", "SMALL"]


class TestTheTwoClocks:
    """The ledger has two, and collapsing them would invent a number for rows that have none."""

    def test_an_untriaged_open_row_is_late_from_raised_plus_grace(self) -> None:
        d = measure([_row("R1", raised_days_ago=3.0, status="open")], now=NOW, grace_h=24.0)
        assert d.priced[0].days_overdue == 2.0          # 3 days old, 1 day of grace

    def test_due_in_the_future_is_not_overdue(self) -> None:
        d = measure([_row("R1", due_days_ago=-5)], now=NOW)
        assert d.priced == () and d.n_no_clock == 1

    def test_a_row_with_no_dates_is_no_clock_not_zero_days(self) -> None:
        """A chronic re-snoozed row is owed regardless of date but has no overdue span."""
        d = measure([_row("R1", roi_bps=400.0)], now=NOW)
        assert d.priced == () and d.n_no_clock == 1 and d.total_bps_days == 0.0


class TestContamination:
    """R0477's rank-ordinals are the reason this is a split rather than a sum."""

    def test_a_rank_ordinal_is_quarantined_never_multiplied(self) -> None:
        """Measured: 4 legacy ordinal rows carried 38.6% of a naive total, top one 14h late."""
        d = measure([_row("R0240", roi_bps=6500.0, due_days_ago=0.6)], now=NOW)
        assert d.priced == () and d.n_ordinal == 1
        assert d.total_bps_days == 0.0

    def test_the_ordinal_bound_matches_the_cli_tripwire(self) -> None:
        assert ORDINAL_BPS == 1000.0
        assert measure([_row("R1", roi_bps=999.0, due_days_ago=1)], now=NOW).n_ordinal == 0
        assert measure([_row("R1", roi_bps=1000.0, due_days_ago=1)], now=NOW).n_ordinal == 1

    def test_a_missing_estimate_is_unpriced_never_a_free_row(self) -> None:
        """L1.28a: 'costs nothing to delay' and 'nobody estimated it' are different claims."""
        d = measure([_row("R1", roi_bps=None, due_days_ago=10)], now=NOW)
        assert d.priced == () and d.n_unpriced == 1

    def test_a_literal_zero_is_unpriced_too(self) -> None:
        d = measure([_row("R1", roi_bps=0.0, due_days_ago=10)], now=NOW)
        assert d.n_unpriced == 1

    def test_a_bool_is_not_a_price(self) -> None:
        d = measure([_row("R1", roi_bps=True, due_days_ago=10)], now=NOW)
        assert d.n_unpriced == 1


class TestTheDenominatorTravelsWithTheTotal:
    """L1.57: a total whose denominator is hidden is an opinion."""

    def test_every_row_lands_in_exactly_one_bucket(self) -> None:
        rows = [_row("A", due_days_ago=5), _row("B", roi_bps=9999.0, due_days_ago=5),
                _row("C", roi_bps=None, due_days_ago=5), _row("D", roi_bps=40.0)]
        d = measure(rows, now=NOW)
        assert d.n_rows == len(rows) == 4
        assert (len(d.priced), d.n_ordinal, d.n_unpriced, d.n_no_clock) == (1, 1, 1, 1)
        assert d.coverage == 0.25

    def test_nothing_priceable_publishes_unmeasured_not_zero(self) -> None:
        d = measure([_row("R1", roi_bps=None, due_days_ago=5)], now=NOW)
        pub = d.as_dict()
        assert pub["delay_cost_status"] == "UNMEASURED"
        assert pub["delay_cost_bps_days"] is None

    def test_an_empty_queue_is_distinct_from_an_unpriceable_one(self) -> None:
        assert measure([], now=NOW).as_dict()["delay_cost_status"] == "EMPTY-QUEUE"

    def test_the_published_unit_refuses_a_dollar_reading(self) -> None:
        pub = measure([_row("R1", due_days_ago=1)], now=NOW).as_dict()
        assert "never a dollar claim" in pub["delay_cost_unit"]
        assert not any("usd" in k.lower() for k in pub)
