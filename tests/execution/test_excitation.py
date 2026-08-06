"""BOUNDED, PRE-REGISTERED RANDOMISATION OF THE DESK'S OWN ORDER KNOBS -- 147 statements, untested.

THE ABSORBING CYCLE THIS EXISTS TO BREAK, every file individually correct:

    run_recorder._universe()   records only benchmark + book + RECENTLY TRADED symbols
    run_cost_model             walks data/moat/{spot,fut}/SYM -- only RECORDED symbols measurable
    executor._rt_bps           unmeasured -> 39.5 bps (p90, fail-closed)
    executor._entry_gate       funding * 1e4 * periods > _rt_bps(sym)

    => never traded => never recorded => never measured => expensive => never traded. FOREVER.

The fail-closed default is GOOD engineering. Its COMPOSITION with a traded-set universe is what
welds the gate, and no single-file review can see that -- which is exactly why the module needs
tests that assert the SAFETY BOUNDARY rather than the arithmetic.

THE BOUNDARY IS THE WHOLE ARGUMENT, and it is one sentence: **it varies HOW, never HOW MUCH.**
`maker_wait_s` and nothing else. This module has no vocabulary for size. So the tests spend most of
their effort on the five refusal paths and on the structural claim that no arm can touch size --
because a module that could would be a second, unreviewed, risk policy.

CLOSES ARE NEVER EXCITED. Structural, not config: a close is a CERTAINTY problem, not a fee
problem (incident #6 -- post-only closes bought a short through). Asserted first.

The other property worth more than coverage: an unreadable design degrades to TODAY'S BEHAVIOUR
rather than to random behaviour, and records WHY, so `check_excitation` reports NO-EXCITATION
rather than OK. An inert experiment that looks like a running one is the built-never-wired failure
wearing an experiment's costume.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.execution import excitation as EX

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _design(**over) -> EX.Design:
    base = {"arms": {EX.BASELINE_ARM: 240.0, "fast": 30.0, "slow": 600.0},
            "epsilon": 1.0, "daily_notional_cap_usd": 100_000.0}
    base.update(over)
    return EX.Design(**base)


# ============================================================ the safety boundary

def test_the_module_has_NO_VOCABULARY_FOR_SIZE() -> None:
    """THE ENTIRE SAFETY ARGUMENT, asserted structurally because it is a claim about what the code
    is CAPABLE of rather than what it happens to do. Position size, leverage, the entry gate, the
    bleed denylist and every rail are untouched BY CONSTRUCTION -- and the moment a size word
    appears here, that sentence stops being true."""
    # Tokenised rather than grepped, because the module DISCUSSES size at length in its own prose
    # -- "position size, leverage, the entry gate ... are untouched by construction" is the safety
    # argument itself. A plain substring search fires on the sentence that states the guarantee,
    # which would be the most annoying possible false positive: the fence tripping on its own
    # rationale. Comments and string literals are dropped; what remains is what the module can DO.
    import io
    import tokenize
    src = Path(EX.__file__).read_text("utf-8")
    code = " ".join(
        tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline)
        if tok.type not in (tokenize.COMMENT, tokenize.STRING))
    for banned in ("leverage", "quantity", "position_size", "place_order", "set_leverage",
                   "notional_usd_target"):
        assert banned not in code, f"{banned!r} appeared in a module that may only vary HOW"


def test_an_arm_can_only_carry_a_WAIT() -> None:
    """The Arm dataclass is the whole interface to the executor. If it ever gained a size field,
    every refusal path below would be guarding the wrong quantity."""
    from dataclasses import fields
    assert {f.name for f in fields(EX.Arm)} == {
        "name", "maker_wait_s", "cell", "seed", "baseline", "reason"}


def test_A_CLOSE_IS_NEVER_EXCITED() -> None:
    """Structural, not a config knob. A close is a CERTAINTY problem, not a fee problem -- incident
    #6 was post-only closes buying a short through. No design, no epsilon and no budget can
    re-enable it."""
    arm = EX.assign("BTCUSDT", "SELL", 100.0, design=_design(), now=_NOW)
    assert arm.baseline is True
    assert "close side" in arm.reason
    assert arm.name == EX.BASELINE_ARM


def test_the_close_refusal_survives_a_maximally_permissive_design() -> None:
    permissive = _design(epsilon=1.0, daily_notional_cap_usd=1e12)
    for side in ("SELL", "sell", "Sell"):
        assert EX.assign("BTCUSDT", side, 1.0, design=permissive, now=_NOW).baseline is True


# ============================================================ the five refusals

def test_an_UNREADABLE_design_degrades_to_todays_behaviour_not_to_random(tmp_path: Path) -> None:
    """epsilon=0 means every assignment returns baseline. Degrading to RANDOM behaviour on an
    unreadable artifact would be the opposite of fail-closed on the one path that touches orders.
    """
    p = tmp_path / "design.json"
    p.write_text("{not json", "utf-8")
    d = EX.load_design(p)
    assert d.loaded is False and d.epsilon == 0.0 and d.daily_notional_cap_usd == 0.0
    arm = EX.assign("BTCUSDT", "BUY", 100.0, design=d, now=_NOW)
    assert arm.baseline is True and "design not loaded" in arm.reason


def test_a_MISSING_design_artifact_is_the_same(tmp_path: Path) -> None:
    d = EX.load_design(tmp_path / "absent.json")
    assert d.loaded is False and "absent" in d.note


def test_a_design_with_NO_BASELINE_ARM_refuses_to_excite(tmp_path: Path) -> None:
    """Without a control arm the design cannot identify anything. Running a treatment-only
    experiment produces an effect with nothing to measure it against -- which reads as a result."""
    p = tmp_path / "design.json"
    p.write_text(json.dumps({"arms": {"fast": 30.0}, "epsilon": 0.25}), "utf-8")
    d = EX.load_design(p)
    assert d.loaded is False and "no baseline arm" in d.note


@pytest.mark.parametrize("eps", [-0.1, 1.5, 2.0])
def test_an_out_of_range_epsilon_refuses_to_excite(tmp_path: Path, eps: float) -> None:
    p = tmp_path / "design.json"
    p.write_text(json.dumps({"arms": {EX.BASELINE_ARM: 240.0, "fast": 30.0},
                             "epsilon": eps}), "utf-8")
    d = EX.load_design(p)
    assert d.loaded is False and "outside [0,1]" in d.note


def test_a_MALFORMED_arms_map_refuses_to_excite(tmp_path: Path) -> None:
    p = tmp_path / "design.json"
    p.write_text(json.dumps({"arms": {"baseline": "soon"}, "epsilon": 0.25}), "utf-8")
    assert EX.load_design(p).loaded is False


def test_EPSILON_ZERO_is_reported_as_disabled_rather_than_as_healthy() -> None:
    """`check_excitation` reads the reason and reports NO-EXCITATION rather than OK. An inert
    experiment indistinguishable from a running one is the built-never-wired failure."""
    arm = EX.assign("BTCUSDT", "BUY", 100.0, design=_design(epsilon=0.0), now=_NOW)
    assert arm.baseline is True and "epsilon=0" in arm.reason


def test_the_DAILY_CAP_is_a_real_ceiling_and_names_the_spend() -> None:
    """A declared, capped, reported budget. The cap is not a risk limit -- an arm cannot change
    size -- it caps the notional EXPOSED TO A DIFFERENT WAIT, the only thing an arm influences."""
    d = _design(daily_notional_cap_usd=1_000.0)
    arm = EX.assign("BTCUSDT", "BUY", 500.0, design=d, spent_today_usd=900.0, now=_NOW)
    assert arm.baseline is True
    assert "budget spent" in arm.reason and "900" in arm.reason and "1000" in arm.reason


def test_an_order_that_exactly_fills_the_cap_is_still_allowed() -> None:
    d = _design(daily_notional_cap_usd=1_000.0)
    assert EX.assign("BTCUSDT", "BUY", 100.0, design=d, spent_today_usd=900.0,
                     now=_NOW).baseline is False


def test_a_design_with_NO_TREATMENT_ARMS_falls_back_to_baseline() -> None:
    d = EX.Design(arms={EX.BASELINE_ARM: 240.0}, epsilon=1.0, daily_notional_cap_usd=1e9)
    arm = EX.assign("BTCUSDT", "BUY", 10.0, design=d, now=_NOW)
    assert arm.baseline is True and "no treatment arms" in arm.reason


def test_EVERY_refusal_carries_a_REASON_onto_the_tape() -> None:
    """"Why did this order not vary" must always be answerable from the tape. A silent
    non-assignment makes an inert experiment look like a running one."""
    cases = [
        EX.assign("BTCUSDT", "SELL", 10.0, design=_design(), now=_NOW),
        EX.assign("BTCUSDT", "BUY", 10.0, design=_design(epsilon=0.0), now=_NOW),
        EX.assign("BTCUSDT", "BUY", 10.0, design=_design(daily_notional_cap_usd=0.0), now=_NOW),
        EX.assign("BTCUSDT", "BUY", 10.0, design=EX._fallback_design("x"), now=_NOW),
    ]
    for arm in cases:
        assert arm.reason and arm.baseline is True


# ============================================================ assignment

def test_the_BASELINE_ARM_reproduces_todays_wait_exactly() -> None:
    """Excitation is a bounded perturbation of a working controller, never a replacement. If the
    baseline wait ever drifted from the executor's, the CONTROL arm would be a treatment."""
    arm = EX.assign("BTCUSDT", "BUY", 10.0, design=_design(epsilon=0.0), now=_NOW)
    assert arm.maker_wait_s == 240.0


def test_inside_epsilon_a_TREATMENT_arm_is_assigned_with_its_own_wait() -> None:
    """The positive control. A module that only ever returned baseline would pass every refusal
    test above and buy no identifying variation at all."""
    arm = EX.assign("BTCUSDT", "BUY", 10.0, design=_design(epsilon=1.0), now=_NOW)
    assert arm.baseline is False
    assert arm.name in {"fast", "slow"}
    assert arm.maker_wait_s in {30.0, 600.0}


def test_the_assignment_is_DETERMINISTIC_and_therefore_REPLAYABLE() -> None:
    """A pre-registered experiment must be replayable: given the tape's recorded seed, an auditor
    can recompute the exact assignment and verify the desk did not choose arms after seeing
    outcomes. `random.Random()` seeded from entropy is unrecoverable, which is precisely why the
    executor's existing jitter -- genuine exogenous variation since day one -- is worthless as
    evidence."""
    kw = {"design": _design(), "now": _NOW, "sequence": 7}
    a = EX.assign("BTCUSDT", "BUY", 10.0, **kw)
    b = EX.assign("BTCUSDT", "BUY", 10.0, **kw)
    assert (a.name, a.maker_wait_s, a.seed) == (b.name, b.maker_wait_s, b.seed)
    assert EX._draw(a.seed) == EX._draw(a.seed)


def test_the_seed_records_everything_needed_to_recompute_it() -> None:
    arm = EX.assign("ETHUSDT", "BUY", 10.0, design=_design(), now=_NOW, sequence=3)
    assert arm.seed == "2026-08-06|ETHUSDT|BUY|3"


def test_different_orders_get_INDEPENDENT_draws() -> None:
    """A design that assigned every order in a day the same arm would have one observation, not
    many, and the standard error computed from it would be wrong by the count."""
    names = {EX.assign("BTCUSDT", "BUY", 10.0, design=_design(epsilon=0.5), now=_NOW,
                       sequence=i).name for i in range(40)}
    assert len(names) > 1, "every order in the day drew the same arm"


def test_the_draw_is_uniform_enough_that_epsilon_means_what_it_says() -> None:
    """epsilon is the FRACTION excited. If the hash were biased, the pre-registered budget and the
    realised one would differ and the cap would bind at the wrong point."""
    d = _design(epsilon=0.25)
    excited = sum(not EX.assign("BTCUSDT", "BUY", 1.0, design=d, now=_NOW, sequence=i).baseline
                  for i in range(2_000))
    assert 0.20 < excited / 2_000 < 0.30


def test_the_arm_draw_is_INDEPENDENT_of_the_epsilon_draw() -> None:
    """Reusing one draw for both decisions correlates "was it excited" with "which arm", so one
    arm would systematically get the marginal orders."""
    d = _design(epsilon=1.0)
    picks = [EX.assign("BTCUSDT", "BUY", 1.0, design=d, now=_NOW, sequence=i).name
             for i in range(400)]
    assert 0.35 < picks.count("fast") / len(picks) < 0.65


# ============================================================ the tape record

def test_BASELINE_ORDERS_ARE_RECORDED_TOO() -> None:
    """An experiment whose control arm is not recorded HAS NO CONTROL. `exc_baseline` is what lets
    the fit separate the assigned condition from the ambient one."""
    arm = EX.assign("BTCUSDT", "SELL", 10.0, design=_design(), now=_NOW)
    f = arm.as_tape_fields()
    assert set(f) == {"exc_arm", "exc_wait_s", "exc_cell", "exc_seed", "exc_baseline"}
    assert f["exc_baseline"] is True
    json.dumps(f)


def test_the_tape_fields_carry_the_CELL_so_the_fit_can_separate_the_populations() -> None:
    d = _design(cells={"_measured_symbols": {"BTCUSDT": 1}})
    measured = EX.assign("BTCUSDT", "BUY", 100.0, design=d, now=_NOW)
    unmeasured = EX.assign("NEWCOINUSDT", "BUY", 100.0, design=d, now=_NOW)
    assert measured.cell.startswith("measured:")
    assert unmeasured.cell.startswith("unmeasured:")


# ============================================================ cells

@pytest.mark.parametrize(("notional", "bucket"), [
    (10.0, "xs"), (249.0, "xs"), (250.0, "s"), (999.0, "s"),
    (1_000.0, "m"), (4_999.0, "m"), (5_000.0, "l"), (1e9, "l"),
])
def test_size_buckets_split_at_the_declared_boundaries(notional, bucket) -> None:
    assert EX.cell_of("BTCUSDT", notional, _design()).endswith(f":{bucket}")


def test_the_TIER_is_the_axis_the_absorbing_cycle_runs_along() -> None:
    """Keeping the measured/unmeasured tier in the cell means the fit reports separately on the two
    populations instead of averaging the cheap measured names over the expensive unmeasured ones --
    which would hide the very asymmetry the module exists to break."""
    d = _design(cells={"_measured_symbols": {"BTCUSDT": 1, "ETHUSDT": 1}})
    assert EX.cell_of("BTCUSDT", 100.0, d) == "measured:xs"
    assert EX.cell_of("DOGEUSDT", 100.0, d) == "unmeasured:xs"


def test_METADATA_KEYS_ARE_NOT_COUNTED_AS_CELLS() -> None:
    """`_measured_symbols` and `_measured_note` live inside `cells` so the tiering data travels
    with the grid it tiers. Treating them as cells crashed this property on its first run -- and
    that was the BENIGN direction. The dangerous one is counting a note as an observed cell and
    reporting a design better identified than it is."""
    d = _design(cells={"_measured_symbols": {"BTCUSDT": 1}, "_measured_note": "a string",
                       "measured:xs": {"n_observed": 12},
                       "unmeasured:l": {"n_observed": 0}})
    assert set(d.real_cells) == {"measured:xs", "unmeasured:l"}
    assert d.unidentified_cells == ["unmeasured:l"]


def test_a_cell_with_no_observations_is_UNIDENTIFIED_and_never_yields_a_coefficient() -> None:
    d = _design(cells={"a:xs": {"n_observed": 0}, "b:xs": {"n_observed": 5},
                       "c:xs": {}, "d:xs": {"n_observed": None}})
    assert d.unidentified_cells == ["a:xs", "c:xs", "d:xs"]


# ============================================================ the re-entry door

def _reentry(**over) -> dict:
    row = {"named_change": "cost model now walks unmeasured symbols",
           "probe_after": "2026-08-01T00:00:00+00:00", "max_probes": 2}
    row.update(over)
    return {"DOGEUSDT": row}


def test_NO_NAMED_CHANGE_MEANS_NO_RE_ENTRY() -> None:
    """L1.16a: re-opening requires a NAMED ENABLING CHANGE addressing the ORIGINAL MECHANISM OF
    DEATH. This is not a general amnesty for losers, and the absence of a change is the most
    likely way one would be attempted."""
    ok, why = EX.reentry_allowed("DOGEUSDT", _reentry(named_change="  "), [], now=_NOW)
    assert ok is False and "named enabling change" in why


def test_an_UNRECORDED_symbol_stays_absorbing() -> None:
    ok, why = EX.reentry_allowed("DOGEUSDT", {}, [], now=_NOW)
    assert ok is False and "still absorbing" in why


def test_the_probe_WINDOW_binds() -> None:
    future = (_NOW + timedelta(days=5)).isoformat()
    ok, why = EX.reentry_allowed("DOGEUSDT", _reentry(probe_after=future), [], now=_NOW)
    assert ok is False and "window opens" in why


@pytest.mark.parametrize("bad", [{"probe_after": "not-a-date"}, {"probe_after": None},
                                 {"max_probes": "two"}])
def test_an_UNPARSEABLE_re_entry_row_DENIES(bad) -> None:
    """Default is deny. An unreadable row must be exactly as absorbing as no row at all -- the
    fail-closed direction, exactly as before this function existed."""
    ok, _ = EX.reentry_allowed("DOGEUSDT", _reentry(**bad), [], now=_NOW)
    assert ok is False


def test_a_row_with_max_probes_zero_is_RECORDED_BUT_NOT_ARMED() -> None:
    """A distinct state worth naming: someone wrote the re-entry condition and deliberately did not
    arm it. Reporting that as 'no condition' would send them to write it again."""
    ok, why = EX.reentry_allowed("DOGEUSDT", _reentry(max_probes=0), [], now=_NOW)
    assert ok is False and "not armed" in why


def test_a_fully_specified_row_GRANTS_a_bounded_probe() -> None:
    ok, why = EX.reentry_allowed("DOGEUSDT", _reentry(), [], now=_NOW)
    assert ok is True
    assert "probe 1/2" in why and "cost model" in why


def test_the_probe_budget_EXHAUSTS_and_the_verdict_stands() -> None:
    tape = [{"event": "open", "symbol": "DOGEUSDT", "opened": "2026-08-02T00:00:00+00:00"},
            {"event": "open", "symbol": "DOGEUSDT", "opened": "2026-08-03T00:00:00+00:00"}]
    ok, why = EX.reentry_allowed("DOGEUSDT", _reentry(), tape, now=_NOW)
    assert ok is False and "budget exhausted (2/2)" in why


def test_the_probe_count_is_DERIVED_FROM_THE_TAPE_never_stored() -> None:
    """A counter in a state file diverges the first time a write is lost or a restart lands
    mid-open, and it diverges SILENTLY IN THE PERMISSIVE DIRECTION -- a forgotten count re-grants
    probes forever. The tape is the record of what actually happened."""
    since = datetime(2026, 8, 1, tzinfo=UTC)
    tape = [
        {"event": "open", "symbol": "DOGEUSDT", "opened": "2026-08-02T00:00:00+00:00"},
        {"event": "close", "symbol": "DOGEUSDT", "opened": "2026-08-02T00:00:00+00:00"},
        {"event": "open", "symbol": "BTCUSDT", "opened": "2026-08-02T00:00:00+00:00"},
        {"event": "open", "symbol": "DOGEUSDT", "opened": "2026-07-20T00:00:00+00:00"},
    ]
    assert EX.probes_used("DOGEUSDT", tape, since) == 1


def test_a_naive_tape_timestamp_is_read_as_UTC_rather_than_dropped() -> None:
    """Older tape rows carry naive stamps. Dropping them would under-count probes, which is the
    permissive direction."""
    since = datetime(2026, 8, 1, tzinfo=UTC)
    tape = [{"event": "open", "symbol": "DOGEUSDT", "opened": "2026-08-02T00:00:00"}]
    assert EX.probes_used("DOGEUSDT", tape, since) == 1


def test_an_unparseable_tape_timestamp_is_skipped_not_fatal() -> None:
    since = datetime(2026, 8, 1, tzinfo=UTC)
    tape = [{"event": "open", "symbol": "DOGEUSDT", "opened": "soon"},
            {"event": "open", "symbol": "DOGEUSDT", "_taped": "2026-08-02T00:00:00+00:00"}]
    assert EX.probes_used("DOGEUSDT", tape, since) == 1


# ============================================================ the daily spend

def test_the_spend_is_read_from_the_TAPE_so_it_survives_a_restart() -> None:
    """An executor that forgets its spend on every restart has no cap at all -- and a crash-loop
    would re-grant the whole budget every few seconds."""
    tape = [{"exc_baseline": False, "opened": "2026-08-06T01:00:00+00:00", "notional": 500.0},
            {"exc_baseline": False, "opened": "2026-08-06T02:00:00+00:00", "notional": -300.0},
            {"exc_baseline": True, "opened": "2026-08-06T03:00:00+00:00", "notional": 9_999.0},
            {"exc_baseline": False, "opened": "2026-08-05T23:00:00+00:00", "notional": 7_777.0}]
    assert EX.spent_today(tape, now=_NOW) == pytest.approx(800.0)


def test_BASELINE_notional_does_not_consume_the_excitation_budget() -> None:
    """The cap is on notional exposed to a DIFFERENT WAIT. Charging baseline orders against it
    would exhaust it on ordinary trading and silently disable the experiment."""
    tape = [{"exc_baseline": True, "opened": "2026-08-06T01:00:00+00:00", "notional": 1e6}]
    assert EX.spent_today(tape, now=_NOW) == 0.0


def test_a_row_with_no_exc_baseline_field_is_not_counted() -> None:
    """Pre-excitation tape rows have no such field. Counting them would charge historical trading
    against today's experimental budget."""
    tape = [{"opened": "2026-08-06T01:00:00+00:00", "notional": 5_000.0}]
    assert EX.spent_today(tape, now=_NOW) == 0.0


def test_an_unparseable_notional_is_skipped_rather_than_zeroing_the_spend() -> None:
    tape = [{"exc_baseline": False, "opened": "2026-08-06T01:00:00+00:00", "notional": "lots"},
            {"exc_baseline": False, "opened": "2026-08-06T02:00:00+00:00", "notional": 100.0}]
    assert EX.spent_today(tape, now=_NOW) == pytest.approx(100.0)


def test_the_spend_and_the_cap_compose_into_a_binding_ceiling() -> None:
    """End to end: yesterday's spend must not bind today, and today's must."""
    d = _design(daily_notional_cap_usd=1_000.0)
    tape = [{"exc_baseline": False, "opened": "2026-08-06T01:00:00+00:00", "notional": 950.0}]
    spent = EX.spent_today(tape, now=_NOW)
    assert EX.assign("BTCUSDT", "BUY", 100.0, design=d, spent_today_usd=spent,
                     now=_NOW).baseline is True
    assert EX.assign("BTCUSDT", "BUY", 10.0, design=d, spent_today_usd=spent,
                     now=_NOW).baseline is False
