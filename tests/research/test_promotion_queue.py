"""The promotion queue's two load-bearing decisions: EXPIRY ORDER, and what never gets a slot.

The failure this guards is subtle because it looks like fairness. Filling forward slots in ARRIVAL
order is the worst available policy when capacity decays: a long-runway edge loses nothing by
waiting a month, a short-runway one loses everything, so arrival order systematically sacrifices
exactly the edges that cannot afford to wait. These pin the ordering, the exclusions, and the
refusal to grant a statistical speed-up where none exists.
"""

from __future__ import annotations

import pytest

from libs.research.promotion_latency import (
    FUNDING_8H_VIF,
    frequency_accelerant,
    measure,
    queue_wait_days,
)
from scripts import run_promotion_queue as q


@pytest.fixture
def synthetic(monkeypatch):
    """A candidate set spanning the whole lifecycle, since this box carries no research db."""
    monkeypatch.setattr(q, "_candidates", lambda: [
        {"id": "c-huge", "family": "carry", "symbol": "A", "capacity_usd": 5_000_000.0,
         "status": "SURVIVED"},
        {"id": "c-mid", "family": "basis", "symbol": "B", "capacity_usd": 40_000.0,
         "status": "SURVIVED"},
        {"id": "c-small", "family": "flow", "symbol": "C", "capacity_usd": 3_000.0,
         "status": "SURVIVED"},
        {"id": "c-dust", "family": "micro", "symbol": "D", "capacity_usd": 50.0,
         "status": "SURVIVED"},
    ])


def test_queue_is_ordered_by_expiry_shortest_first(synthetic):
    """THE POLICY. Slots go to what expires soonest, not to what arrived first."""
    rep = q.build(equity_usd=1_000.0, growth=1.0)
    runways = [r["runway_days"] for r in rep["queue"]]
    assert runways == sorted(runways), f"queue not expiry-ordered: {runways}"
    assert rep["queue"][0]["capacity_usd"] < rep["queue"][-1]["capacity_usd"], (
        "smallest capacity expires first at a fixed growth rate, so it must be served first")


def test_sub_viable_never_takes_a_slot(synthetic):
    """A $50 edge fails execution physics at ANY equity, so a slot spent on it buys nothing at any
    point in the future -- it is excluded, not merely sorted to the back."""
    rep = q.build(equity_usd=1_000.0)
    assert all(r["id"] != "c-dust" for r in rep["queue"])
    assert any(r["id"] == "c-dust" and r["admission"] == "SUB-VIABLE" for r in rep["excluded"])


def test_outgrown_edges_leave_the_queue_as_the_book_grows(synthetic):
    """The lifecycle: the same $3k edge is queued at seed scale and gone at scale -- retirement by
    OUTGROWTH, which is success, not failure."""
    small = q.build(equity_usd=1_000.0)
    large = q.build(equity_usd=5_000_000.0)
    assert any(r["id"] == "c-small" for r in small["queue"])
    assert all(r["id"] != "c-small" for r in large["queue"])
    assert any(r["id"] == "c-small" and r["admission"] == "OUTGROWN" for r in large["excluded"])


def test_only_free_slots_are_admitted_now(synthetic, monkeypatch):
    """The cap is what keeps the Holm bar fixed, so the queue may never over-admit."""
    import libs.research.slot_registry as sr
    monkeypatch.setattr(sr, "derive_slots",
                        lambda: {"slots": [{"name": f"s{i}"} for i in range(11)]})
    rep = q.build(equity_usd=1_000.0)
    assert rep["slots"]["free"] == 1
    admitted = [r for r in rep["queue"] if r["slot_action"] == "ADMIT-NOW"]
    assert len(admitted) <= 1
    if len(rep["queue"]) > 1:
        assert rep["queue"][1]["slot_action"].startswith("WAIT")


def test_faster_growth_shortens_every_runway(synthetic):
    """The race the principal named: the faster capital compounds, the sooner an edge expires."""
    slow = q.build(equity_usd=1_000.0, growth=1.0)
    fast = q.build(equity_usd=1_000.0, growth=4.6)      # ~100x/yr
    by_id = {r["id"]: r["runway_days"] for r in slow["queue"]}
    for r in fast["queue"]:
        assert r["runway_days"] < by_id[r["id"]], r["id"]


class TestQueueWaitIsRealLatency:
    """The term a per-candidate view can never show: a full cohort means a new candidate accrues
    NOTHING while its capacity decays, and it looks 'in progress' the whole time."""

    def test_free_slots_mean_no_wait(self, monkeypatch):
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "derive_slots", lambda: {"slots": [{"name": "a"}]})
        assert queue_wait_days().days == 0.0

    def test_full_cohort_is_charged_as_latency(self, monkeypatch):
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "derive_slots",
                            lambda: {"slots": [{"name": f"s{i}"} for i in range(12)]})
        w = queue_wait_days()
        assert w.days > 0, "a full cohort must cost the race something"
        assert "FULL" in w.detail

    def test_latency_reports_its_own_provenance(self):
        """An unmeasured component quoted as measured is the reality gap L2.10 exists to catch."""
        lat = measure()
        assert lat.total_days > 0
        provs = {c.provenance for c in (lat.clock, lat.queue_wait, lat.decision)}
        assert provs <= {"MEASURED", "DESIGN", "ESTIMATED"}
        assert lat.fully_measured == (provs == {"MEASURED"})


class TestFrequencyAccelerantRefusesWhereItIsFalse:
    """The trap inside the only real accelerant, and the reason it is a function rather than a
    multiplier someone applies by hand."""

    def test_event_driven_faster_settlement_is_granted(self):
        """Perp funding settles 3x daily: three REAL cash flows per day, vif ~1.008, so effective
        N genuinely triples and the same bar is reached in ~1/3 the wall clock."""
        a = frequency_accelerant("8h", pnl_is_event_driven=True, event_rate_rises=True)
        assert a["granted"]
        assert a["divisor"] == pytest.approx(3.0 / FUNDING_8H_VIF, rel=1e-6)

    def test_diffusive_pnl_is_refused(self):
        """Drift estimation depends on the HORIZON, not the sampling rate. Granting this would
        manufacture a t-stat out of oversampling while looking like an optimisation -- the exact
        self-deception L1.6 and the two-stage law exist to prevent."""
        a = frequency_accelerant("hourly", pnl_is_event_driven=False, event_rate_rises=True)
        assert not a["granted"]
        assert a["divisor"] == 1.0
        assert "HORIZON" in a["reason"]

    def test_event_driven_but_static_event_rate_is_refused(self):
        """Sampling between events just resamples the same cash flows."""
        a = frequency_accelerant("8h", pnl_is_event_driven=True, event_rate_rises=False)
        assert not a["granted"]

    def test_unknown_cadence_defaults_to_refusal(self):
        a = frequency_accelerant("every-so-often", pnl_is_event_driven=True, event_rate_rises=True)
        assert not a["granted"]

    def test_daily_is_not_an_acceleration(self):
        assert not frequency_accelerant(
            "daily", pnl_is_event_driven=True, event_rate_rises=True)["granted"]
