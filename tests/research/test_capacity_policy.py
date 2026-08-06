"""THE ONE DEFINITION OF WHAT CAPACITY IS WORTH -- 114 statements, zero tests until now.

Five copies of this policy existed and they disagreed. Fixing the survival gate in isolation on
2026-07-26 left the other four intact, so a categorical exclusion simply moved to where it was
harder to see: a $50k-capacity dislocation could PASS the gate and still lose every ranking to a
fund-shaped idea it beat on every dimension that pays. Being allowed into the niche while being
scored out of it is not parity.

So the property under test is not "the arithmetic runs" -- it is the SHAPE of the score:

    ramp to sufficiency  ->  FLAT (parity)  ->  bounded, currently-neutral crowding term

The flat region IS the parity. A test suite that only checked the ramp would pass on a scorer that
was monotone in size, which is precisely the bug this module was written to delete. So the flatness
is asserted directly, across four orders of magnitude.

The second theme is FAILURE DIRECTION. Every degraded path here must fail in the direction that
demands MORE headroom, never less: a missing store falls back to the documented constant, a stale
NAV ledger means UNKNOWN rather than "anything goes", and an unreadable file must never become the
loosest possible gate. Those are asserted one by one, because each is a one-line change away from
inverting.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import capacity_policy as C

# ------------------------------------------------------------------ the shape of the score


def test_capacity_is_judged_as_SUFFICIENCY_not_magnitude() -> None:
    """The headline rule. A $200k edge and a $200M edge are identical to a $50k book, because
    additional capacity buys nothing the desk can spend."""
    book, sleeves = 50_000.0, 8
    required = C.capacity_required(book, sleeves)
    assert C.capacity_fit(required * 2, book, sleeves) == 1.0
    assert C.capacity_fit(required * 2_000, book, sleeves) == 1.0


def test_the_score_is_FLAT_above_the_requirement_across_orders_of_magnitude() -> None:
    """THE PARITY TEST, and the one a monotone-in-size scorer fails. Four scorers used to reward
    bigger capacity monotonically; if any of that leaks back in, this is where it shows."""
    book, sleeves = 50_000.0, 8
    req = C.capacity_required(book, sleeves)
    scores = [C.capacity_fit(req * m, book, sleeves) for m in (1, 10, 100, 1_000, 10_000)]
    assert scores == [1.0] * 5, f"size became a tiebreaker again: {scores}"


def test_below_the_requirement_the_score_ramps_rather_than_hard_rejecting() -> None:
    """The 2026-07-26 fix. A flat $100k floor hard-rejected sub-$100k edges; capacity is a RATIO to
    deployed equity, so an edge you would be half of is worth roughly half as much -- not zero."""
    book, sleeves = 50_000.0, 8
    req = C.capacity_required(book, sleeves)
    half = C.capacity_fit(req * 0.5, book, sleeves)
    quarter = C.capacity_fit(req * 0.25, book, sleeves)
    assert 0.0 < quarter < half < 1.0
    assert half == pytest.approx(0.5, abs=0.01)


def test_the_score_is_bounded_to_0_1_at_both_extremes() -> None:
    assert C.capacity_fit(0.0) == 0.0
    assert C.capacity_fit(-1_000.0) == 0.0, "negative capacity is not a negative score"
    assert 0.0 <= C.capacity_fit(1e15) <= 1.0


def test_the_crowding_term_defaults_to_NO_discount() -> None:
    """Principal 2026-07-26. The objective is the maximum number of simultaneous uncorrelated
    alphas -- a sleeve declined for its size is compounding foregone -- and crowding is already
    priced by `crowded_known`, DSR, PBO and persistence, so charging it here double-counts."""
    assert C._CROWD_FLOOR == 1.0
    assert C.capacity_fit(1e11, 50_000.0, 8) == 1.0


def test_the_crowding_mechanism_still_works_if_evidence_ever_reintroduces_it(monkeypatch) -> None:
    """The knob survives, defaulted to neutral and bounded, so MEASURED decay-versus-capacity
    evidence could revive it. A knob that had been deleted could not be revived by evidence, and a
    knob that silently did nothing would be worse -- so its mechanism is exercised here."""
    monkeypatch.setattr(C, "_tunable", lambda name, fb: 0.5 if name == "capacity_crowd_floor"
                        else fb)
    at_start = C.capacity_fit(C._CROWD_START_USD, 50_000.0, 8)
    two_decades = C.capacity_fit(C._CROWD_START_USD * 100, 50_000.0, 8)
    assert at_start == 1.0, "the discount must begin AT fund scale, not below it"
    assert two_decades == pytest.approx(0.5), "and must bottom out at the floor, not below"
    assert C.capacity_fit(C._CROWD_START_USD * 1e6, 50_000.0, 8) == pytest.approx(0.5)


# ------------------------------------------------------------------ sleeves and allocation

def test_no_single_edge_is_judged_against_the_WHOLE_book() -> None:
    """Judging every candidate against the full $50k assumes an all-in one-strategy desk -- the
    opposite of how this one runs -- and inflates the requirement by the sleeve count, pushing
    genuinely tradeable small edges back into 'unfillable'. That is the flat-floor bug in
    miniature."""
    assert C.sleeve_equity(50_000.0, 8) == pytest.approx(6_250.0)
    assert C.capacity_required(50_000.0, 8) < C.capacity_required(50_000.0, 1)


def test_sleeve_equity_never_divides_by_zero_or_goes_negative() -> None:
    assert C.sleeve_equity(50_000.0, 0) == 50_000.0
    assert C.sleeve_equity(-5.0, 4) == 0.0


def test_a_declared_allocation_admits_the_small_edge_equal_weight_excluded() -> None:
    """THE GAP THAT SILENTLY EXCLUDED THE EDGES SECTION 42 EXISTS TO KEEP. A $5k edge funded with
    $1k is 5x headroom and perfectly safe; equal weight on a $14.8k book reads $1,477 into it and
    fails."""
    book, sleeves = 14_800.0, 10
    assert C.capacity_fit(5_000.0, book, sleeves) < 1.0
    assert C.capacity_fit(5_000.0, book, sleeves, allocation_usd=1_000.0) == 1.0


def test_the_band_never_contradicts_the_score() -> None:
    """If the score says an edge is fillable at a declared allocation, the band must not
    simultaneously call it UNFILLABLE -- two answers to one question is how a gate gets argued
    with rather than obeyed."""
    book, sleeves, alloc = 14_800.0, 10, 1_000.0
    assert C.capacity_fit(5_000.0, book, sleeves, allocation_usd=alloc) == 1.0
    assert C.capacity_band(5_000.0, book, sleeves, allocation_usd=alloc) != "UNFILLABLE"


def test_a_zero_allocation_does_not_pass_everything() -> None:
    """A declared allocation of 0 collapses the requirement to the absolute floor. The floor is
    what stops that becoming a free pass -- 'I will fund it with nothing' must not be a way to
    clear any capacity gate."""
    assert C.capacity_required(0.0, 1) == pytest.approx(
        C._tunable("capacity_abs_floor_usd", C._CAPACITY_FALLBACK_FLOOR))
    assert C.capacity_fit(1.0, 50_000.0, 8, allocation_usd=0.0) < 1.0


def test_declared_allocation_is_None_for_an_unnamed_sleeve() -> None:
    """None is the SAFE direction: no declaration means the caller falls back to equal weight,
    which is the stricter assumption."""
    assert C.declared_allocation(None) is None
    assert C.declared_allocation("") is None
    assert C.declared_allocation("a-sleeve-that-does-not-exist") is None


# ------------------------------------------------------------------ the requirement, inverted

def test_max_allocation_is_a_QUARTER_of_capacity_not_all_of_it() -> None:
    """You never fill an edge to its stated capacity: capacity is where impact has already eaten
    the edge, so trading up to it means arriving exactly when there is nothing left to collect."""
    assert C.max_allocation(100_000.0) == pytest.approx(25_000.0)
    assert C.max_allocation(0.0) == 0.0
    assert C.max_allocation(-10.0) == 0.0


def test_max_allocation_and_capacity_required_are_exact_inverses() -> None:
    """They are two readings of ONE rule, and a separate function only because the sizer needs the
    second form -- re-deriving it there is precisely how five disagreeing copies appeared."""
    for cap in (10_000.0, 250_000.0, 9_000_000.0):
        alloc = C.max_allocation(cap)
        assert C.capacity_required(alloc, 1) == pytest.approx(max(
            C._tunable("capacity_abs_floor_usd", C._CAPACITY_FALLBACK_FLOOR), cap))


def test_outgrown_at_names_the_expiry_in_dollars() -> None:
    """Section 42(3): the decay of a small edge as the desk grows into it is DEFINITIONAL, not a
    risk to mitigate. It only compounds if the desk can SEE the expiry coming."""
    cap = 100_000.0
    assert C.outgrown_at(cap, 8) == pytest.approx(cap * 8 / 4.0)
    assert C.outgrown_at(cap, 8) > C.outgrown_at(cap, 1), "more sleeves means a longer life"
    assert C.outgrown_at(0.0) == 0.0


def test_growth_runway_below_one_means_already_outgrown() -> None:
    cap = 100_000.0
    expiry = C.outgrown_at(cap, 8)
    assert C.growth_runway(cap, expiry * 0.5, 8) > 1.0
    assert C.growth_runway(cap, expiry * 2.0, 8) < 1.0
    assert C.growth_runway(cap, expiry, 8) == pytest.approx(1.0)


def test_growth_runway_on_a_zero_book_is_infinite_rather_than_a_crash() -> None:
    assert C.growth_runway(1_000.0, 0.0, 4) == float("inf")


# ------------------------------------------------------------------ bands

@pytest.mark.parametrize(("cap", "want"), [
    (1.0, "UNFILLABLE"),
    (1_000_000.0, "NICHE"),
    (50_000_000.0, "SCALABLE"),
    (5_000_000_000.0, "FUND-SCALE"),
])
def test_bands_split_at_the_declared_boundaries(cap, want) -> None:
    assert C.capacity_band(cap, 50_000.0, 8) == want


def test_the_NICHE_band_is_the_desks_structural_advantage_and_is_reachable() -> None:
    """If nothing could ever land in NICHE the §42 hunt measurement would read 0 forever and look
    like a failed hunt rather than a broken band."""
    caps = [50_000.0, 500_000.0, 5_000_000.0, 5e10]
    share = C.niche_share(caps, 50_000.0, 8)
    assert 0.0 < share < 1.0


def test_niche_share_ignores_non_positive_capacities_and_survives_an_empty_funnel() -> None:
    assert C.niche_share([]) == 0.0
    assert C.niche_share([0.0, -1.0]) == 0.0
    assert C.niche_share([1_000_000.0, 0.0]) == 1.0, "a zero is not a candidate, not a failure"


# ------------------------------------------------------------------ live book: failure direction

def _nav(tmp_path: Path, *, equity: float, age_days: float = 0.0, sleeves: int = 3,
         field: str = "molded_curve_usd") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "nav.jsonl"
    ts = (datetime.now(tz=UTC) - timedelta(days=age_days)).isoformat()
    p.write_text(json.dumps({"ts": ts, field: equity, "n_carries": sleeves}) + "\n", "utf-8")
    return p


def test_the_live_book_is_read_from_the_ledger_rather_than_pinned_to_a_constant(
        tmp_path: Path) -> None:
    """'Capacity is a ratio' and 'the ratio is evaluated against a hardcoded literal' are the same
    bug one step apart: pinned, the desk would still be sizing edges for $50k at $500k."""
    assert C.live_book_usd(ledger=_nav(tmp_path, equity=123_456.0)) == pytest.approx(123_456.0)


def test_a_stale_ledger_means_UNKNOWN_and_UNKNOWN_is_not_anything_goes(tmp_path: Path) -> None:
    fresh = _nav(tmp_path / "a", equity=900_000.0)
    stale = _nav(tmp_path / "b", equity=900_000.0, age_days=C._NAV_STALE_DAYS + 1)
    assert C.live_book_usd(ledger=fresh) == pytest.approx(900_000.0)
    assert C.live_book_usd(fallback=50_000.0, ledger=stale) == 50_000.0


@pytest.mark.parametrize("broken", ["", "not json\n", '{"ts": "2026-01-01T00:00:00+00:00"}\n'])
def test_an_unreadable_ledger_falls_back_and_never_to_zero(tmp_path: Path, broken: str) -> None:
    """Returning 0.0 would collapse the requirement to the absolute floor and quietly pass
    everything. An unreadable file must never be the loosest possible gate."""
    p = tmp_path / "bad.jsonl"
    p.write_text(broken, "utf-8")
    assert C.live_book_usd(fallback=50_000.0, ledger=p) == 50_000.0


def test_a_missing_ledger_falls_back(tmp_path: Path) -> None:
    assert C.live_book_usd(fallback=7_000.0, ledger=tmp_path / "nope.jsonl") == 7_000.0


def test_a_non_positive_equity_falls_back_rather_than_loosening_every_gate(
        tmp_path: Path) -> None:
    assert C.live_book_usd(fallback=50_000.0, ledger=_nav(tmp_path, equity=0.0)) == 50_000.0


def test_the_legacy_field_name_is_still_accepted(tmp_path: Path) -> None:
    """The chain is APPEND-ONLY, so rows written before the rename are still in it. Failing to read
    them would silently fall back to the constant on the machine with the longest history."""
    p = _nav(tmp_path, equity=88_000.0, field="equity_marked")
    assert C.live_book_usd(ledger=p) == pytest.approx(88_000.0)


def test_live_sleeves_is_FLOORED_at_the_planned_count(tmp_path: Path) -> None:
    """Running one sleeve today does not mean one edge may swallow the whole book -- it means the
    desk has not diversified YET. Taking the live number literally would hand 100% of equity to one
    edge and call it sized."""
    p = _nav(tmp_path, equity=50_000.0, sleeves=1)
    assert C.live_sleeves(fallback=8, ledger=p) == 8
    more = _nav(tmp_path / "c", equity=50_000.0, sleeves=20)
    assert C.live_sleeves(fallback=8, ledger=more) == 20, "but a real increase is honoured"


def test_live_sleeves_is_never_below_one(tmp_path: Path) -> None:
    assert C.live_sleeves(fallback=0, ledger=tmp_path / "missing.jsonl") == 1


# ------------------------------------------------------------------ venue truth

def test_venue_truth_is_absent_rather_than_guessed_when_the_rail_has_not_run(
        monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(C, "_DEADMAN_STATE", tmp_path / "nope.json")
    assert C.venue_book_usd() is None


def test_venue_truth_reads_the_high_water_mark(monkeypatch, tmp_path: Path) -> None:
    """A high-water mark OVERSTATES the book during a drawdown, and overstating is the safe
    direction for a capacity requirement: it demands MORE headroom, never less."""
    p = tmp_path / "deadman.json"
    p.write_text(json.dumps({"high_water": 412_000.0}), "utf-8")
    monkeypatch.setattr(C, "_DEADMAN_STATE", p)
    assert C.venue_book_usd() == pytest.approx(412_000.0)


def test_venue_truth_rejects_a_non_positive_high_water(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "deadman.json"
    p.write_text(json.dumps({"high_water": 0.0}), "utf-8")
    monkeypatch.setattr(C, "_DEADMAN_STATE", p)
    assert C.venue_book_usd() is None


def test_venue_truth_is_read_only(monkeypatch, tmp_path: Path) -> None:
    """Two writers on the dead-man rail caused the 07-11 false fire. It is TIER-3 NEVER-TOUCH."""
    p = tmp_path / "deadman.json"
    p.write_text(json.dumps({"high_water": 1_000.0}), "utf-8")
    monkeypatch.setattr(C, "_DEADMAN_STATE", p)
    before = p.stat().st_mtime_ns
    C.venue_book_usd()
    assert p.stat().st_mtime_ns == before


# ------------------------------------------------------------------ the leaf constraint

def test_a_broken_threshold_store_degrades_to_the_documented_constant(monkeypatch) -> None:
    """This module must stay importable from anywhere in the dependency graph. A broken store must
    degrade to the default rather than taking the capacity policy -- and every gate reading it --
    down with it."""
    monkeypatch.setattr(C, "_STORE", Path("/nonexistent/nowhere.json"))
    assert C._tunable("capacity_headroom_mult", C._CAPACITY_FALLBACK_MULT) == \
        C._CAPACITY_FALLBACK_MULT
    assert C.capacity_required(50_000.0, 8) > 0.0


def test_the_module_imports_nothing_from_libs_at_module_scope() -> None:
    """THE LEAF CONSTRAINT IS LOAD-BEARING, NOT STYLISTIC. Five copies of this policy existed
    because callers found it 'too circular to import the real policy' and re-inlined their own.
    Every libs import here is lazy and exception-guarded so that excuse can never return."""
    src = Path(C.__file__).read_text("utf-8")
    top_level = [ln for ln in src.splitlines()
                 if ln.startswith(("import libs", "from libs"))]
    assert top_level == [], f"module-scope libs import breaks the leaf constraint: {top_level}"
