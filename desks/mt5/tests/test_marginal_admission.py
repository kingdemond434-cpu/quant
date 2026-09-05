"""dE[log W] is the admission criterion, size is an output, and the two directions are asymmetric.

    "Don't rank candidates primarily by Sharpe. Rank by dE[log W] after adding the candidate to
     the existing portfolio. A Sharpe-1.2 strategy at correlation -0.2 to the book can be vastly
     more valuable than a Sharpe-2.5 strategy at correlation +0.9. Your repo's doctrine already
     has this exact insight. Now make that principle the actual automatic admission criterion."

    "Never have 'this strategy is allocated 3% forever'. Have 'this strategy currently earns 7.4%
     portfolio risk because its posterior edge, uncertainty, conditional state and covariance make
     that the current robust log-optimal allocation.' Five minutes/hour/session later, it can
     be 0%."

    "promotion slow / demotion immediate, evidence-based allocation, and fractional Kelly rather
     than blindly betting full Kelly."                              -- the principal, 2026-09-05

WHAT WAS ACTUALLY MISSING BEFORE THIS FILE. `libs.portfolio.robust_elog.marginal_delta_elog` has
computed this comparison since the module was written and `libs/research/alpha_fitness.py` calls
it -- inside the EVOLUTIONARY SEARCH, to breed alphas. Nothing on the capital path used it. The
allocation artifact's `marginal_delta_elog` field is `AllocationResult.marginal`, the per-sleeve
GRADIENT at the solved optimum: the right ranking for the heat cap to trim a book it already
holds by, and NOT the value of admitting something it does not hold. So the desk's promoter
admitted on a forward clock with no reference to the book at all, and wrote a CONSTANT 3% risk
fraction onto every row it admitted.

The worked example below is the principal's own, measured on this desk's real solver: against a
book of four sleeves at Sharpe 2.3 correlated 0.97 to each other, a Sharpe-1.2 candidate at
correlation -0.19 is ADMITTED (+0.00024/day) and a Sharpe-2.5 candidate at correlation +0.93 is
REFUSED, earning exactly zero heat. Sharpe ranks them one way; dE[log W] ranks them the other,
and dE[log W] is what decides.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    sample_worlds,
)

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")
promoter = pytest.importorskip("promoter", reason="the promoter ships with the desk")
from mt5desk import decision_core as dc  # noqa: E402


# --------------------------------------------------------------------------- the world it lives in
def _sleeve(name: str, sharpe: float, rho: float, core: np.ndarray,
            rng: np.random.Generator, family: str, vol: float = 0.35) -> SleeveEvidence:
    """A sleeve with a CHOSEN annual Sharpe and a chosen correlation to the book's common factor.

    Synthetic on purpose: the point is to control the two numbers the principal's claim is about
    and let the desk's own solver answer. Nothing here is a forecast.
    """
    idio = rng.normal(0.0, 1.0, core.size)
    z = rho * core + np.sqrt(max(1.0 - rho * rho, 0.0)) * idio
    z = (z - z.mean()) / z.std()
    return SleeveEvidence(name=name, daily_r=z * vol + sharpe / np.sqrt(252.0) * vol,
                          family=family, symbol=name.split("_")[0], n_trials=50,
                          forward_days=40, live_days=0, cost_r=0.02)


def _book_and_two_candidates(seed: int = 7, n: int = 600):
    """Four correlated held sleeves, one diversifying low-Sharpe candidate, one correlated star."""
    rng = np.random.default_rng(seed)
    core = rng.normal(0.0, 1.0, n)
    held = [_sleeve(f"HELD_{i}", 2.3, 0.97, core, rng, "core") for i in range(4)]
    diversifier = _sleeve("EURJPY_carry_asia", 1.2, -0.20, core, rng, "carry")
    correlated_star = _sleeve("XAUUSD_trend_ny", 2.5, 0.95, core, rng, "core")
    return held, diversifier, correlated_star


def _scan(held, *candidates, total_heat: float = 0.20, bound: float = 0.20, **kw):
    ev = [*held, *candidates]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    worlds = sample_worlds(ev, cfg)
    return pa.marginal_admission(ev, worlds, cfg,
                                 incumbent={e.name: 0.05 for e in held},
                                 bounds={e.name: bound for e in ev},
                                 total_heat=total_heat, **kw)


# ----------------------------------------------------------------- the principal's worked example
def test_a_low_sharpe_diversifier_beats_a_high_sharpe_copy_of_the_book() -> None:
    """THE INSTRUCTION, measured. Sharpe orders these two one way; dE[log W] orders them the
    other, and the criterion follows dE[log W]."""
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star)
    assert doc["status"] == "MEASURED"
    lo = doc["candidates"]["EURJPY_carry_asia"]
    hi = doc["candidates"]["XAUUSD_trend_ny"]

    # The premise: the refused one really is the higher-Sharpe, higher-correlation sleeve.
    assert hi["sharpe_standalone_annual"] > lo["sharpe_standalone_annual"] + 1.0
    assert hi["corr_to_book"] > 0.8 and lo["corr_to_book"] < 0.0

    # The verdict is the opposite of the Sharpe ordering.
    assert lo["admit"] is True, "a diversifying candidate that raises growth must be admitted"
    assert hi["admit"] is False, "a correlated copy of the book must not be admitted on Sharpe"
    assert lo["delta_elogw_per_day"] > hi["delta_elogw_per_day"]
    assert hi["heat_earned"] == pytest.approx(0.0, abs=1e-5), \
        "the book does not want the correlated star at any size"
    assert doc["admitted"] == ["EURJPY_carry_asia"]
    assert "XAUUSD_trend_ny" in doc["refused"]


def test_every_candidate_carries_the_reason_it_was_admitted_or_refused() -> None:
    """A score with no sentence beside it is a number nobody can audit. Both rows must name the
    delta, the heat, the Sharpe and the correlation -- so a reader can see the disagreement."""
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star)
    for name, row in doc["candidates"].items():
        why = row["why"]
        assert "Sharpe" in why and "correlation" in why, f"{name}: {why}"
        assert ("admitted" in why) == bool(row["admit"]), f"{name}: {why}"
        for field in ("delta_elogw_per_day", "delta_elogw_per_year", "heat_earned",
                      "corr_to_book", "sharpe_standalone_annual", "displaced"):
            assert field in row, f"{name} is missing {field}"


def test_the_contest_is_at_equal_total_heat_so_exposure_cannot_buy_the_win() -> None:
    """A candidate that simply adds risk beats every incumbent on raw growth while being worse per
    unit of it. Both books are therefore solved at the SAME total heat -- the same equalisation
    `allocator_proof.contest` applies -- and what a candidate earns, something else pays for."""
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star, total_heat=0.20)
    assert doc["basis"] == "equal_heat"
    assert doc["total_heat"] == pytest.approx(0.20)
    admitted = doc["candidates"]["EURJPY_carry_asia"]
    assert admitted["heat_earned"] > 0
    paid = sum(v for v in admitted["displaced"].values())
    assert paid < 0, "heat given to a candidate must be taken from what the book already held"


def test_the_margin_is_not_zero_so_a_hairs_breadth_win_is_not_a_win() -> None:
    """A sampled-world estimate has noise, and admitting on a difference inside it is admitting on
    luck. The bar is a fraction of the incumbent's OWN growth -- the same fraction the proof
    certificate demands of the allocator itself, so there is one margin and not two."""
    held, diversifier, _ = _book_and_two_candidates()
    doc = _scan(held, diversifier)
    assert doc["margin_frac"] == pa.ADMISSION_MARGIN_FRAC
    assert doc["margin_per_day"] == pytest.approx(
        abs(doc["incumbent_elogw_per_day"]) * pa.ADMISSION_MARGIN_FRAC, rel=1e-6)
    assert doc["margin_per_day"] > 0


def test_a_candidate_the_budget_did_not_reach_is_named_and_refused() -> None:
    """ABSENCE IS NEVER PERMISSION. A widening library must degrade the scan honestly: the
    candidates the clock did not reach are listed with the reason and are NOT admitted."""
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star, budget_s=-1.0)
    assert doc["candidates"] == {}
    assert set(doc["unscored"]) == {"EURJPY_carry_asia", "XAUUSD_trend_ny"}
    assert doc["admitted"] == []
    for why in doc["unscored"].values():
        assert "not admitted" in why.lower()


def test_the_unreached_tail_goes_first_next_pass_so_coverage_is_eventually_complete() -> None:
    """A pass whose budget runs out would otherwise leave the SAME tail unmeasured every hour --
    a candidate below the cut could never be admitted, and a compute limit would harden into a
    verdict. Whatever the last scan could not reach is measured first on the next one."""
    held, diversifier, star = _book_and_two_candidates()
    ev = [*held, diversifier, star]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    worlds = sample_worlds(ev, cfg)
    common = {"incumbent": {e.name: 0.05 for e in held},
              "bounds": {e.name: 0.20 for e in ev}, "total_heat": 0.20}
    # Rank the correlated star first, then declare the diversifier unreached: it must now lead.
    doc = pa.marginal_admission(ev, worlds, cfg, order={"XAUUSD_trend_ny": 9.0},
                                prefer={"EURJPY_carry_asia"}, **common)
    assert list(doc["candidates"])[0] == "EURJPY_carry_asia"
    assert doc["n_carried_from_last_unreached"] == 1
    assert "unreached" in doc["order"]
    # With nothing carried, the ranking alone decides the order.
    plain = pa.marginal_admission(ev, worlds, cfg, order={"XAUUSD_trend_ny": 9.0}, **common)
    assert list(plain["candidates"])[0] == "XAUUSD_trend_ny"


def test_an_empty_book_is_scored_on_the_free_basis_and_says_so() -> None:
    """With nothing held there is nothing to displace, so the equal-heat contest has no meaning.
    The scan says `free` rather than quietly answering a different question."""
    held, diversifier, _ = _book_and_two_candidates()
    ev = [*held, diversifier]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    doc = pa.marginal_admission(ev, sample_worlds(ev, cfg), cfg, incumbent={},
                                bounds={e.name: 0.20 for e in ev}, total_heat=0.20)
    assert doc["basis"] == "free"
    assert doc["incumbent_elogw_per_day"] == 0.0


def test_the_gradient_field_and_the_admission_field_are_kept_apart() -> None:
    """The artifact's legacy `marginal_delta_elog` is the GRADIENT at the solved book, which the
    heat cap trims by. Conflating it with the admission marginal is how the desk came to believe
    it had an admission criterion, so the artifact says which is which in its own text."""
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert '"marginal_delta_elog_basis"' in src
    assert "admission.candidates[*]" in src


# ------------------------------------------------------------------- size is an output, not 3%
def test_the_promoter_no_longer_writes_a_constant_risk_fraction() -> None:
    """`PROMOTED_RISK_FRAC` was written verbatim onto every promoted row -- "allocated 3% forever".
    It survives only as the CEILING on what this module may write, and the number itself comes
    from the allocator's own solve for that sleeve."""
    frac, why = promoter.promoted_risk_frac({"heat_earned": 0.0174})
    assert frac == pytest.approx(0.0174) and "allocator" in why
    frac, why = promoter.promoted_risk_frac({"heat_earned": 0.0})
    assert frac == 0.0 and "no heat" in why
    frac, _ = promoter.promoted_risk_frac(None)
    assert frac == 0.0, "an unmeasured sleeve is sized at zero, never at a default"


def test_the_promoter_can_only_lower_what_it_used_to_write_never_raise_it() -> None:
    """Rules that override everything: never raise leverage or size by fiat. The clamp is
    one-sided, so this change can only ever reduce the fraction the promoter writes."""
    high, _ = promoter.promoted_risk_frac({"heat_earned": 0.40})
    assert high == pytest.approx(promoter.PROMOTED_RISK_FRAC)
    assert high <= promoter.PROMOTED_RISK_FRAC
    # And when the clamp bites, BOTH numbers are on the verdict: the gateway sizes a funded sleeve
    # from the book, so a row showing 3% beside a 7.4% solve must not read as the constant back.
    view = {"fresh": True, "at": datetime.now(tz=UTC).isoformat(), "book": {}, "zeroed": {},
            "candidates": {"x": _row(admit=True, heat=0.074)}}
    cap = promoter.capital_verdict(view, "x")
    assert cap["status"] == "LIVE"
    assert cap["risk_frac"] == pytest.approx(promoter.PROMOTED_RISK_FRAC)
    assert cap["allocator_heat"] == pytest.approx(0.074)
    assert cap["written_at_promoter_ceiling"] is True


def test_a_zeroed_sleeve_is_sized_at_zero_instead_of_the_three_percent_floor() -> None:
    """THE HOLE THE PRINCIPAL'S "five minutes later it can be 0%" FELL THROUGH. The allocation
    artifact's book is filtered to heat > 1e-5, so a zeroed sleeve VANISHED from it; the gateway
    then read `from_book = False` and fell back to `clamp_risk_frac`, which FLOORS at 3%. The
    allocator could say "small" and could not say "none". `book_zeroed` closes it, and the zero
    can only reduce a size -- it changes neither the sum nor the empty-book refusal."""
    book, why = dc.book_from_allocation(0.2, {"a": 0.12, "b": 0.08}, None, certified=True,
                                        why="proof 1h old", zeroed={"c": "no heat this pass"})
    assert book == {"a": 0.12, "b": 0.08, "c": 0.0}
    assert "held at zero" in why
    assert sum(book.values()) == pytest.approx(0.2), "zeros must not disturb the drift check"
    # `promoted_lot` on the book path returns no lot at all for a zero fraction, which is the
    # gateway's own "allocator gave this sleeve no heat; skipped" path.
    assert dc.promoted_lot(10_000.0, 0, 5.0, "EURUSD", None, 0.0, None, from_book=True) == 0.0
    # And absence changes nothing: the old answer, byte for byte.
    same, why2 = dc.book_from_allocation(0.2, {"a": 0.12, "b": 0.08}, None, certified=True,
                                         why="proof 1h old")
    assert same == {"a": 0.12, "b": 0.08}
    assert why2 == "allocator book authoritative (2 sleeve(s)); proof 1h old"


def test_a_zeroed_leg_costs_no_heat_in_the_cap_and_is_not_dropped_from_the_roster() -> None:
    """A leg the solve zeroed places nothing, so billing it at its measured stop cost would
    reserve budget nothing will use and could defer a leg the book actually wanted. It must not
    be dropped from the roster either -- that would orphan any bracket it still has open.

    Before `book_zeroed` existed `q_charge` could not BE zero (`clamp_risk_frac` floors at the
    base fraction), so the previously-unreachable value is the only behaviour that changed."""
    def leg(name, **kw):
        return {"name": name, "symbol": "EURUSD", **kw}

    budget = (0.05, "solved")           # + HEAT_SLIDE: room for exactly one 5% leg, not two
    kept, note = dc.cap_by_heat([leg("live", q_charge=0.05), leg("zeroed", q_charge=0.0)],
                                10_000.0, allocation=budget)
    assert [s["name"] for s in kept] == ["live", "zeroed"], "a zeroed leg keeps its roster row"
    assert note is None, f"the zeroed leg must not consume budget: {note}"
    # A POSITIVE q_charge still bills exactly itself and is still deferred when it does not fit.
    # The zero is the only value whose meaning changed, and it could not occur before.
    kept2, note2 = dc.cap_by_heat([leg("a", q_charge=0.05), leg("b", q_charge=0.05)],
                                  10_000.0, allocation=budget)
    assert [s["name"] for s in kept2] == ["a"]
    assert note2 is not None and "'b'" in note2


def test_zeroing_a_book_of_nothing_is_still_a_refusal_to_allocate() -> None:
    """An empty book is "the allocator declined", not "size everything at zero", and the zeros
    must never turn one into the other."""
    book, why = dc.book_from_allocation(0.2, {}, None, certified=True, why="proof",
                                        zeroed={"a": "none"})
    assert book is None and "empty" in why


# ------------------------------------------------ promotion slow, demotion immediate, both named
@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A promoter pointed entirely at tmp_path, with the allocator's answer under test control."""
    shadow_dir = tmp_path / "reports" / "shadow"
    shadow_dir.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "logs").mkdir()
    alloc = tmp_path / "reports" / "pf_allocation.json"
    monkeypatch.setattr(promoter, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(promoter, "LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")
    monkeypatch.setattr(promoter, "GOLD_RETIRED_FILE", tmp_path / "data" / "GOLD_RETIRED.json")
    monkeypatch.setattr(promoter, "ALLOCATION", alloc)
    monkeypatch.setattr(promoter, "clock_identities", lambda: {})
    monkeypatch.setattr(promoter, "regrade_failures", lambda now=None: {})
    monkeypatch.setattr(promoter, "load_ledger", lambda: [])
    monkeypatch.setattr(promoter, "authorized_specs", lambda base=None: set())

    class Desk:
        def shadow(self, blob: dict) -> None:
            (shadow_dir / "shadow_state.json").write_text(json.dumps(blob), encoding="utf-8")

        def read_shadow(self) -> dict:
            return json.loads((shadow_dir / "shadow_state.json").read_text(encoding="utf-8"))

        def allocate(self, rows: dict, *, at=None, heat_total: float = 0.20,
                     book: dict | None = None, zeroed: dict | None = None) -> None:
            stamp = (at or datetime.now(tz=UTC)).isoformat()
            alloc.write_text(json.dumps({
                "generated_utc": stamp, "heat": {"total": heat_total},
                "book": book or {}, "book_zeroed": zeroed or {},
                "admission": {"status": "MEASURED", "measured_utc": stamp, "universe": {},
                              "candidates": rows}}), encoding="utf-8")

        def no_allocation(self) -> None:
            if alloc.exists():
                alloc.unlink()

        def sleeves(self) -> list[dict]:
            p = tmp_path / "data" / "sleeves.json"
            return json.loads(p.read_text("utf-8"))["sleeves"] if p.exists() else []

        def write_sleeves(self, rows: list[dict]) -> None:
            (tmp_path / "data" / "sleeves.json").write_text(
                json.dumps({"sleeves": rows}), encoding="utf-8")

    return Desk()


def _row(*, admit: bool, heat: float = 0.03, delta: float = 0.0004) -> dict:
    return {"symbol": "", "family": "", "selector": "",
            "delta_elogw_per_day": delta if admit else -abs(delta),
            "heat_earned": heat if admit else 0.0, "admit": admit,
            "why": "fixture"}


_CAND = {"status": "PROMOTION CANDIDATE", "exp_r": 0.276, "n": 40, "max_dd_r": -8.0}


def test_capital_requires_a_measured_marginal_and_absence_is_standby_not_capital(desk) -> None:
    """A matured candidate with no measured dE[log W] joins the ROSTER and holds NO CAPITAL. It is
    not retired and its clock is untouched -- the next allocator pass decides."""
    desk.no_allocation()
    desk.shadow({"CADJPY.asia": dict(_CAND)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY" and s["risk_frac"] == 0.0
    assert "no fresh dE[log W]" in s["admission"]["why"]
    assert "retired_at" not in s, "standby is not retirement"
    assert desk.read_shadow()["CADJPY.asia"]["status"] == "PROMOTION CANDIDATE"


def test_a_candidate_the_book_does_not_want_is_refused_however_matured_its_clock(desk) -> None:
    """The forward clock says the sleeve is real. The allocator says adding it to the book the
    desk holds does not raise growth. Capital follows the allocator."""
    desk.shadow({"CADJPY.asia": dict(_CAND)})
    desk.allocate({"CADJPY.asia": _row(admit=False)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY" and s["risk_frac"] == 0.0
    assert s["admission"]["delta_elogw_per_day"] < 0


def test_an_admitted_candidate_takes_exactly_the_heat_the_solve_gave_it(desk) -> None:
    """Not 3%. Not a default. The number the allocator solved for, on the row, with its source."""
    desk.shadow({"CADJPY.asia": dict(_CAND)})
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.0174)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"
    assert s["risk_frac"] == pytest.approx(0.0174)
    assert s["risk_frac_source"] == "allocator_marginal"


def test_demotion_needs_one_reading_and_restoration_needs_several(desk) -> None:
    """THE ASYMMETRY, END TO END. One reading removes the risk. Restoring it takes
    PROMOTE_ADMIT_STREAK consecutive readings, and the sleeve is never retired in between."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "LIVE",
                         "risk_frac": 0.03, "window": "asia", "lot": "auto_ramp",
                         "promoted_at": (old - timedelta(hours=2)).isoformat(timespec="seconds")}])
    desk.shadow({})

    # ONE reading is enough to take the risk away.
    desk.allocate({"CADJPY.asia": _row(admit=False)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY" and s["risk_frac"] == 0.0
    assert s["demoted_at"] and "standby on the current reading" in s["demote_reason"]
    assert "retired_at" not in s and s.get("retire_reason") is None

    # The FIRST positive reading is not enough to give it back.
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.02)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY", "one reading must not restore what one reading removed"
    assert s["admit_streak"] == 1
    assert f"1/{promoter.PROMOTE_ADMIT_STREAK}" in s["admission"]["why"]

    # The second consecutive one is.
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.02)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["risk_frac"] == pytest.approx(0.02)
    assert s["admit_streak"] == promoter.PROMOTE_ADMIT_STREAK
    assert "demoted_at" not in s and s["restore_reason"]


def test_a_single_negative_reading_resets_the_streak(desk) -> None:
    """Accumulated evidence for ADDING risk is consecutive by construction: one bad reading in the
    middle sends the count back to zero, because the question is whether the marginal is
    reliably positive and not whether it was ever positive."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "STANDBY",
                         "risk_frac": 0.0, "window": "asia", "admit_streak": 1,
                         "demoted_at": old.isoformat(timespec="seconds"),
                         "promoted_at": (old - timedelta(hours=2)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({"CADJPY.asia": _row(admit=False)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["admit_streak"] == 0 and s["status"] == "STANDBY"


def test_a_live_sleeve_is_resized_by_the_current_solve_not_by_its_promotion_day(desk) -> None:
    """"This strategy currently earns 7.4% portfolio risk" -- and the number moves when the solve
    moves, without the sleeve being promoted or retired to make it move."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "LIVE",
                         "risk_frac": 0.03, "window": "asia",
                         "promoted_at": (old - timedelta(hours=2)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.0074)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["risk_frac"] == pytest.approx(0.0074)
    assert s["risk_frac_source"] == "allocator_marginal"


def test_a_sleeve_promoted_after_the_allocation_is_not_judged_by_it(desk) -> None:
    """Demoting a sleeve on a measurement taken before it existed is reading absence as evidence.
    The row stands and the next solve judges it."""
    desk.shadow({"CADJPY.asia": dict(_CAND)})
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.02)},
                  at=datetime.now(tz=UTC) - timedelta(seconds=1))
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"
    promoter.main()                                     # a second pass, same stale allocation
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"
    assert "predates the sleeve" in s["admission"]["why"]


def test_a_stale_allocation_removes_nothing_and_adds_nothing(desk) -> None:
    """An allocation older than the freshness bar describes a book that no longer exists. It may
    not add risk, and it may not remove it either -- acting on a stale reading in EITHER direction
    is acting on a measurement nobody took."""
    old = datetime.now(tz=UTC) - timedelta(hours=promoter.ADMISSION_MAX_AGE_H + 2)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "LIVE",
                         "risk_frac": 0.03, "window": "asia",
                         "promoted_at": (old - timedelta(days=2)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({"CADJPY.asia": _row(admit=False)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["risk_frac"] == pytest.approx(0.03)
    view = promoter.allocation_view()
    assert view["fresh"] is False and "old" in view["why"]


def test_a_carried_forward_scan_is_aged_by_its_own_measurement_not_by_the_file(desk) -> None:
    """THE SCAN AND THE FILE ARE NOT THE SAME AGE. `pf_allocator` measures the admission scan on
    its HEAVY clock and its short clocks carry the answer into a freshly written artifact, so a
    day-old scan can sit inside a minute-old file. Reading the file's timestamp alone would read
    a stale measurement as fresh -- what the carry-forward stamp exists to make visible."""
    fresh_file = datetime.now(tz=UTC)
    stale_scan = fresh_file - timedelta(hours=promoter.ADMISSION_MAX_AGE_H + 5)
    desk.allocate({"CADJPY.asia": _row(admit=True)}, at=fresh_file)
    path = Path(promoter.ALLOCATION)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["admission"]["measured_utc"] = stale_scan.isoformat()
    doc["admission"]["carried_from"] = stale_scan.isoformat()
    path.write_text(json.dumps(doc), encoding="utf-8")
    view = promoter.allocation_view()
    assert view["fresh"] is False
    assert "admission scan" in view["why"]
    assert view["scan_age_h"] > promoter.ADMISSION_MAX_AGE_H


def test_retirement_is_still_the_one_way_door_and_standby_is_not(desk) -> None:
    """Standby is reversible and writes no KILL; retirement is not and does. Conflating them is
    what the demotion rule exists to stop, so the two must stay visibly different."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "RETIRED",
                         "risk_frac": 0.0, "window": "asia", "retired_at": old.isoformat(),
                         "promoted_at": (old - timedelta(days=1)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({"CADJPY.asia": _row(admit=True, heat=0.03)}, at=old)
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "RETIRED", "a fresh positive marginal must not resurrect a retirement"
    assert promoter.EVIDENCE_TO_ADD_RISK != promoter.EVIDENCE_TO_REMOVE_RISK
    assert len(promoter.EVIDENCE_TO_REMOVE_RISK) == 1
    assert len(promoter.EVIDENCE_TO_ADD_RISK) > len(promoter.EVIDENCE_TO_REMOVE_RISK)


def test_a_sleeve_the_scan_never_reached_keeps_its_risk_and_says_why(desk) -> None:
    """"NOBODY LOOKED" IS NOT "THE ANSWER IS NO". A candidate the admission budget did not reach,
    or one outside the priced universe, has no reading -- and removing risk on a compute limit is
    an outage wearing a risk decision. The row stands with the gap named on it."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "LIVE",
                         "risk_frac": 0.03, "window": "asia",
                         "promoted_at": (old - timedelta(days=1)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({"SOMETHING_ELSE": _row(admit=True)}, at=old)     # this sleeve was not scored
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["risk_frac"] == pytest.approx(0.03)
    assert s["admission"]["status"] == "UNMEASURED"
    assert "not been measured" in s["admission"]["why"]


def test_a_sleeve_the_solve_explicitly_zeroed_loses_its_risk_at_once(desk) -> None:
    """A zeroed sleeve IS a reading -- the solve looked and gave it nothing -- so one of them is
    enough. It is the `book_zeroed` half of the same artifact the gateway sizes zero from."""
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    desk.write_sleeves([{"name": "CADJPY.asia", "symbol": "CADJPY", "status": "LIVE",
                         "risk_frac": 0.03, "window": "asia",
                         "promoted_at": (old - timedelta(days=1)).isoformat(timespec="seconds")}])
    desk.shadow({})
    desk.allocate({}, at=old, zeroed={"CADJPY.asia": "no heat in this state"})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "STANDBY" and s["risk_frac"] == 0.0
    assert "no heat in this state" in s["demote_reason"]
    assert "retired_at" not in s


def test_the_two_sides_name_the_same_sleeve_differently_and_still_join(desk) -> None:
    """THE JOIN IS THE RISKIEST PART ON THE REAL BOX. `pf_allocator` prices a sleeve as
    `SYM_family_selector`; the forward clocks key it `SYM.selector[.STATE]`. A join that matched
    nothing would refuse every candidate and read exactly like a verdict, so the allocator
    publishes each priced sleeve's PARTS and the promoter recognises them on those."""
    desk.shadow({"CADJPY.asia": dict(_CAND)})
    desk.allocate({"CADJPY_session_range_breakout_asia":
                   {**_row(admit=True, heat=0.019), "symbol": "CADJPY",
                    "family": "session_range_breakout", "selector": "asia"}})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["risk_frac"] == pytest.approx(0.019)
    assert "cadjpy|session_range_breakout|asia" in s["admission"]["joined"]


def test_an_ambiguous_join_is_dropped_rather_than_guessed(desk) -> None:
    """Two sleeves on the same symbol and selector but different mechanisms both answer to
    `sym|selector`. Funding one on the other's measurement is worse than funding neither."""
    idx = promoter._index({
        "EURUSD_carry_asia": {"symbol": "EURUSD", "family": "carry", "selector": "asia",
                              "admit": True},
        "EURUSD_breakout_asia": {"symbol": "EURUSD", "family": "breakout", "selector": "asia",
                                 "admit": False},
    })
    assert "eurusd|asia" not in idx
    assert idx["eurusd|carry|asia"]["admit"] is True
    assert idx["eurusd|breakout|asia"]["admit"] is False


# ---------------------------------------------------------------------------- fractional Kelly
def test_the_kelly_fraction_is_a_reported_number_with_a_ladder_behind_it() -> None:
    """"fractional Kelly rather than blindly betting full Kelly" -- and the fraction has to be a
    NUMBER, not an emergent property nobody can name. It is measured against the book a bettor
    who believed his own backtest would hold, and every shrinkage layer is priced separately."""
    held, diversifier, star = _book_and_two_candidates()
    ev = [*held, diversifier, star]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    doc = pa.kelly_fraction(ev, cfg, deployed=0.20,
                            bounds={e.name: 0.08 for e in ev}, seed=1)
    assert doc["status"] in ("MEASURED", "BOUND")
    assert doc["full_kelly_heat"] > doc["deployed_heat"], \
        "the deployed book must be a FRACTION of full Kelly, not a multiple of it"
    assert 0.0 < doc["kelly_fraction"] < 1.0
    assert doc["kelly_fraction"] == pytest.approx(0.20 / doc["full_kelly_heat"], rel=1e-3)
    for rung in ("winners_curse_deflation", "crisis_worlds", "edge_decay", "cost_uncertainty",
                 "cvar_blend", "redundancy_charge"):
        assert rung in doc["ladder"], f"{rung} is shrinkage nobody priced"
    assert "do not sum" in doc["ladder_note"]


def test_a_pinned_kelly_reference_is_reported_as_a_bound_not_as_a_measurement() -> None:
    """Full Kelly on believed-at-face-value evidence is enormous, so the reference solve is
    capped. When it sits ON that cap the true reference is LARGER and the true fraction SMALLER,
    and reporting the pinned ratio as measured would be a defect wearing a plausible answer --
    the exact failure this module's own plausibility fence exists to refuse."""
    held, diversifier, star = _book_and_two_candidates()
    ev = [*held, diversifier, star]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    doc = pa.kelly_fraction(ev, cfg, deployed=0.20, bounds={}, seed=1)
    assert doc["reference_cap"] == pa.REFERENCE_CAP
    assert doc["reference_pinned"] is (doc["status"] == "BOUND")
    if doc["reference_pinned"]:
        assert "upper bound" in doc["bound_note"]
        assert doc["full_kelly_heat"] == pytest.approx(pa.REFERENCE_CAP)
    for rung in doc["ladder"].values():
        if isinstance(rung, dict) and rung.get("pinned") and doc["reference_pinned"]:
            assert "UNMEASURED, not costless" in rung["why"]


# ------------------------------------------------------------------------------- the rent line
def test_the_criterion_carries_its_own_rent_line() -> None:
    """AGENTS.md: every component earns `E[logW] with - E[logW] without`, measured forward. What
    this criterion is worth IS the growth its admitted set adds, and it says so in its own units
    rather than claiming a joint number it did not measure."""
    held, diversifier, star = _book_and_two_candidates()
    doc = _scan(held, diversifier, star)
    rent = doc["rent"]
    assert rent["unit"] == "log-wealth per day"
    assert rent["sum_admitted_delta_elogw_per_day"] == pytest.approx(
        sum(doc["candidates"][n]["delta_elogw_per_day"] for n in doc["admitted"]))
    assert "joint delta" in rent["note"]
