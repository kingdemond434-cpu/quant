"""HOW LONG A CANDIDATE REALLY TAKES TO REACH CAPITAL -- 82 statements, zero tests until now.

Two things in this module are worth more than the arithmetic around them.

THE QUEUE WAIT IS THE TERM EVERYBODY FORGETS. The forward cohort is capped so the Holm bar stays
fixed; when the cap is full, a new candidate accrues ZERO evidence while its capacity decays
against a growing book. Every per-candidate view shows it as "in progress" when it is parked. If
this term ever silently reads 0 on a full cohort, the whole pipeline-latency figure understates
itself by a design clock and nothing else in the desk would notice.

THE ACCELERANT'S VALUE IS ITS REFUSAL. Granting a diffusive process a speed-up for finer sampling
would loosen the confirmation bar while looking like an optimisation -- the exact shape of
self-deception that L1.6 and the two-stage law exist to prevent, and the shape a desk under time
pressure is most likely to talk itself into. So the tests spend most of their effort on the paths
that say NO, and on the one path that says yes saying it for a stated reason.

PROVENANCE IS ASSERTED EVERYWHERE. MEASURED, DESIGN and ESTIMATED are different claims about how
much to believe a number, and a module that labelled an estimate MEASURED would be worse than one
that reported nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import promotion_latency as PL

# ------------------------------------------------------------------ the queue wait


def test_a_free_slot_means_a_clock_starts_TODAY(monkeypatch) -> None:
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (3, 12, ["a", "b", "c"]))
    c = PL.queue_wait_days()
    assert c.days == 0.0 and c.provenance == "MEASURED"
    assert "9/12 forward slots free" in c.detail


def test_a_FULL_cohort_is_real_latency_and_is_never_reported_as_zero(monkeypatch) -> None:
    """THE TERM EVERYBODY FORGETS. A parked candidate accrues no evidence while its capacity
    decays against a growing book, and every per-candidate view calls that 'in progress'."""
    names = [f"slot{i}" for i in range(12)]
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (12, 12, names))
    c = PL.queue_wait_days()
    assert c.days == PL.DESIGN_CLOCK_DAYS
    assert c.provenance == "ESTIMATED", "an upper bound must not be dressed as a measurement"
    assert "cohort FULL" in c.detail


def test_an_overfull_cohort_still_reports_a_wait(monkeypatch) -> None:
    """`free = cap - occupied` goes negative if the cap is ever lowered under a live cohort, and a
    naive `if free > 0` would be the only thing standing between that and a zero wait."""
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (15, 12, ["x"] * 15))
    assert PL.queue_wait_days().days == PL.DESIGN_CLOCK_DAYS


def test_a_missing_slot_registry_does_not_crash_the_queue(monkeypatch) -> None:
    """Import-guarded on purpose: a latency estimate is not worth taking the caller down for."""
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "libs.research.slot_registry":
            raise ImportError("simulated")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    occupied, cap, names = PL._slot_occupancy()
    assert (occupied, cap, names) == (0, 12, [])


# ------------------------------------------------------------------ the clock

def test_the_design_clock_is_reported_as_DESIGN_not_as_measured() -> None:
    c = PL.clock_days()
    assert c.days == PL.DESIGN_CLOCK_DAYS
    assert c.provenance == "DESIGN"
    assert "Holm correction" in c.detail


def test_the_fast_track_is_a_SMALLER_FAMILY_not_a_shorter_bar() -> None:
    """The distinction is the whole justification for the exemption. A pre-registered PRIMARY
    registered before any cohort carries no Holm correction because there is no family to correct
    over -- not because its evidence bar was lowered."""
    c = PL.clock_days(fast_track_eligible=True)
    assert c.days == 40.0 and c.provenance == "MEASURED"
    assert "smaller family" in c.detail
    assert "not a shorter bar" in c.detail


def test_this_module_never_SHORTENS_the_pre_registered_window() -> None:
    """It reports. A latency module that could move the forward window would be a latency module
    that could promote something early."""
    assert PL.clock_days().days == PL.DESIGN_CLOCK_DAYS
    assert PL.clock_days(fast_track_eligible=True).days <= PL.DESIGN_CLOCK_DAYS


# ------------------------------------------------------------------ decision lag

def _ledger(tmp_path: Path, rows, monkeypatch, *, wrap: bool = False) -> None:
    root = tmp_path
    (root / "data").mkdir(parents=True, exist_ok=True)
    payload = {"decisions": rows} if wrap else rows
    (root / "data/decision_ledger.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(PL, "_ROOT", root)


def test_the_lag_is_MEASURED_from_the_ledger_once_it_has_three_closed_rows(
        tmp_path: Path, monkeypatch) -> None:
    rows = [{"raised": "2026-08-01T00:00:00+00:00", "closed": "2026-08-03T00:00:00+00:00"},
            {"raised": "2026-08-01T00:00:00+00:00", "closed": "2026-08-05T00:00:00+00:00"},
            {"raised": "2026-08-01T00:00:00+00:00", "closed": "2026-08-09T00:00:00+00:00"}]
    _ledger(tmp_path, rows, monkeypatch)
    c = PL.decision_lag_days()
    assert c.provenance == "MEASURED"
    # The MEDIAN, not the mean -- one stalled row is not the norm and must not become it.
    assert c.days == pytest.approx(4.0)


def test_fewer_than_three_rows_is_ESTIMATED_and_floored_at_the_daily_cycle(
        tmp_path: Path, monkeypatch) -> None:
    """A median of two is not a median. The floor is the cycle cadence, because one day is the
    least a decision can physically take here."""
    _ledger(tmp_path, [{"raised": "2026-08-01T00:00:00+00:00",
                        "closed": "2026-08-02T00:00:00+00:00"}], monkeypatch)
    c = PL.decision_lag_days()
    assert c.provenance == "ESTIMATED" and c.days == 1.0
    assert "re-measures automatically" in c.detail


def test_both_field_spellings_are_accepted(tmp_path: Path, monkeypatch) -> None:
    """`raised`/`closed` and `opened`/`decided` are both in the ledger's history. Reading only one
    would silently fall back to the estimate on the machine with the longest record."""
    rows = [{"opened": "2026-08-01T00:00:00+00:00", "decided": "2026-08-03T00:00:00+00:00"}] * 3
    _ledger(tmp_path, rows, monkeypatch)
    assert PL.decision_lag_days().provenance == "MEASURED"


def test_a_dict_wrapped_ledger_is_unwrapped(tmp_path: Path, monkeypatch) -> None:
    rows = [{"raised": "2026-08-01T00:00:00+00:00", "closed": "2026-08-03T00:00:00+00:00"}] * 3
    _ledger(tmp_path, rows, monkeypatch, wrap=True)
    assert PL.decision_lag_days().provenance == "MEASURED"


def test_incomplete_and_unparseable_rows_are_skipped_not_counted_as_zero(
        tmp_path: Path, monkeypatch) -> None:
    """A row counted as a zero-day lag would drag the median toward zero and report the pipeline
    as faster than it is -- an error in the flattering direction."""
    rows = [{"raised": "2026-08-01T00:00:00+00:00"},                       # never closed
            {"closed": "2026-08-03T00:00:00+00:00"},                       # never raised
            {"raised": "not-a-date", "closed": "2026-08-03T00:00:00+00:00"},
            {"raised": "2026-08-01T00:00:00+00:00", "closed": "2026-08-03T00:00:00+00:00"}]
    _ledger(tmp_path, rows, monkeypatch)
    c = PL.decision_lag_days()
    assert c.provenance == "ESTIMATED", "only ONE row was usable"


def test_a_missing_or_corrupt_ledger_falls_back_rather_than_crashing(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(PL, "_ROOT", tmp_path)
    assert PL.decision_lag_days().provenance == "ESTIMATED"
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/decision_ledger.json").write_text("{not json", "utf-8")
    assert PL.decision_lag_days().provenance == "ESTIMATED"


def test_a_negative_lag_is_floored_at_zero(tmp_path: Path, monkeypatch) -> None:
    """Closed before raised is a clock error, not a negative latency, and a negative component
    would subtract from the pipeline total."""
    rows = [{"raised": "2026-08-05T00:00:00+00:00", "closed": "2026-08-01T00:00:00+00:00"}] * 3
    _ledger(tmp_path, rows, monkeypatch)
    assert PL.decision_lag_days().days >= 0.0


# ------------------------------------------------------------------ the whole pipeline

def test_the_total_is_the_sum_and_the_components_are_kept(monkeypatch) -> None:
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (2, 12, ["a", "b"]))
    p = PL.measure()
    assert p.total_days == pytest.approx(
        p.clock.days + p.queue_wait.days + p.decision.days)
    d = p.as_dict()
    assert set(d["components"]) == {"clock", "queue_wait", "decision"}
    json.dumps(d)


def test_fully_measured_is_False_whenever_any_component_is_only_estimated(monkeypatch) -> None:
    """A single ESTIMATED term makes the total an estimate. Reporting the sum as measured because
    two of three parts were is how a design constant becomes a fact."""
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (12, 12, ["x"] * 12))
    assert PL.measure(fast_track_eligible=True).fully_measured is False


def test_a_full_cohort_adds_a_design_clock_to_the_total(monkeypatch) -> None:
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (12, 12, ["x"] * 12))
    full = PL.measure().total_days
    monkeypatch.setattr(PL, "_slot_occupancy", lambda: (0, 12, []))
    empty = PL.measure().total_days
    assert full - empty == pytest.approx(PL.DESIGN_CLOCK_DAYS)


# ------------------------------------------------------------------ the accelerant

def test_a_DIFFUSIVE_pnl_is_REFUSED_however_fast_it_is_sampled() -> None:
    """THE REFUSAL IS THE ENTIRE VALUE. Drift estimation depends on the HORIZON, not the sampling
    frequency: finer sampling of the same window adds rows and zero information about the mean.
    Granting a speed-up here manufactures a t-stat out of oversampling."""
    out = PL.frequency_accelerant("hourly", pnl_is_event_driven=False, event_rate_rises=True)
    assert out["granted"] is False and out["divisor"] == 1.0
    assert "DIFFUSIVE" in out["reason"]


def test_event_driven_pnl_whose_EVENT_RATE_does_not_rise_is_REFUSED() -> None:
    """Sampling between events resamples the same cash flows. This is the subtler half and the one
    a plausible argument would get past a looser gate."""
    out = PL.frequency_accelerant("hourly", pnl_is_event_driven=True, event_rate_rises=False)
    assert out["granted"] is False
    assert "EVENT RATE does not rise" in out["reason"]


def test_a_cadence_no_faster_than_daily_earns_nothing() -> None:
    out = PL.frequency_accelerant("daily", pnl_is_event_driven=True, event_rate_rises=True)
    assert out["granted"] is False and out["divisor"] == 1.0


def test_an_UNDECLARED_cadence_earns_nothing_rather_than_a_default() -> None:
    """Refusal is the default. An unknown rate silently treated as some rate is a speed-up granted
    on a fact nobody stated."""
    out = PL.frequency_accelerant("every-so-often", pnl_is_event_driven=True,
                                  event_rate_rises=True)
    assert out["granted"] is False and "unknown cadence" in out["reason"]


def test_a_genuine_event_driven_speed_up_is_GRANTED_with_its_arithmetic_shown() -> None:
    """The one yes. 8h funding at vif 1.008 is near-independent, so three observations a day are
    worth nearly three -- and the BAR IS UNCHANGED; only the calendar moves."""
    out = PL.frequency_accelerant("8h", pnl_is_event_driven=True, event_rate_rises=True)
    assert out["granted"] is True
    assert out["divisor"] == pytest.approx(3.0 / PL.FUNDING_8H_VIF)
    assert "The bar is unchanged" in out["reason"]


def test_a_higher_VIF_earns_a_smaller_speed_up() -> None:
    """Variance inflation is the price of dependence between observations. If it did not reduce
    the multiplier, correlated samples would be counted as independent ones."""
    indep = PL.frequency_accelerant("hourly", pnl_is_event_driven=True, event_rate_rises=True,
                                    vif=1.0)["divisor"]
    dep = PL.frequency_accelerant("hourly", pnl_is_event_driven=True, event_rate_rises=True,
                                  vif=4.0)["divisor"]
    assert dep < indep
    assert dep == pytest.approx(24.0 / 4.0)


def test_every_refusal_carries_a_reason() -> None:
    """A gate that says no without saying why gets argued with rather than obeyed."""
    for kwargs in ({"pnl_is_event_driven": False, "event_rate_rises": True},
                   {"pnl_is_event_driven": True, "event_rate_rises": False}):
        out = PL.frequency_accelerant("hourly", **kwargs)
        assert out["reason"] and not out["granted"]
