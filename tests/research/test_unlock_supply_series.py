"""Tests for the gap-#3 schedule-as-SERIES screen.

Four behaviours are pinned, because they are the four ways this screen could lie:
  1. alignment is strictly causal -- an unlock at instant t never informs a bar containing t,
     and a schedule row not yet public never informs any bar before it was public;
  2. a synthetic signal that genuinely LEADS is detected;
  3. a signal that merely COINCIDES is killed as an artifact, not promoted;
  4. missing data REFUSES to screen rather than silently substituting a snapshot denominator --
     which is defect_1 of the screen this module replaces.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from libs.research.unlock_supply_series import (
    CONSTRUCTIONS,
    NEW_CELLS,
    PRIOR_PARAMETERISATIONS,
    TOTAL_TRIALS,
    UnlockRelease,
    build_series,
    circulating_at,
    declared_cells,
    forward_unlock_tokens,
    load_circulating_supply,
    load_unlock_schedule,
    locked_tokens_at,
    run_screen,
    screen_cell,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _closes(n: int) -> tuple[datetime, ...]:
    return tuple(_T0 + timedelta(days=i) for i in range(n))


def _supply(n: int, value: float = 1_000_000.0) -> tuple[tuple[datetime, float], ...]:
    return tuple((_T0 + timedelta(days=i), value) for i in range(n))


# --------------------------------------------------------------------- 1. causal alignment


def test_release_inside_the_bar_never_informs_that_bar():
    """An unlock at instant t must not appear in the signal stamped on a bar containing t.

    Bar d ends at close_d.  A release landing between close_{d-1} and close_d is INSIDE bar d,
    so it may inform the signal at d-1 (the schedule was public then) but never the signal at d,
    where it is already in the past and cannot be forward supply.
    """
    closes = _closes(5)
    inside_bar_3 = closes[2] + timedelta(hours=6)      # after close_2, before close_3
    rel = (UnlockRelease("X", inside_bar_3, 1_000.0),)

    assert forward_unlock_tokens(rel, closes[2], 7) == 1_000.0    # visible looking forward
    assert forward_unlock_tokens(rel, closes[3], 7) == 0.0        # gone once the bar contains it
    assert forward_unlock_tokens(rel, closes[4], 7) == 0.0


def test_release_exactly_at_the_close_is_excluded_strictly():
    """The `>` in the window is strict.  A release stamped exactly at close_d belongs to the
    bar that just ended, not to the forward window opening at that instant."""
    closes = _closes(4)
    rel = (UnlockRelease("X", closes[2], 500.0),)
    assert forward_unlock_tokens(rel, closes[2], 30) == 0.0
    assert forward_unlock_tokens(rel, closes[1], 30) == 500.0


def test_release_beyond_the_window_is_excluded():
    closes = _closes(3)
    far = closes[0] + timedelta(days=40)
    rel = (UnlockRelease("X", far, 900.0),)
    assert forward_unlock_tokens(rel, closes[0], 7) == 0.0
    assert forward_unlock_tokens(rel, closes[0], 60) == 900.0


def test_schedule_not_yet_public_never_informs_an_earlier_bar():
    """`known_from` is the second causality rail: a contractually certain release the market has
    not been told about is not tradeable information."""
    closes = _closes(10)
    rel = (
        UnlockRelease("X", closes[8], 1_000.0, known_from=closes[5]),
    )
    assert forward_unlock_tokens(rel, closes[4], 30) == 0.0     # not yet announced
    assert forward_unlock_tokens(rel, closes[5], 30) == 1_000.0  # announced at close_5
    assert locked_tokens_at(rel, closes[4]) == 0.0
    assert locked_tokens_at(rel, closes[5]) == 1_000.0


def test_denominator_never_reads_the_future():
    """circulating_at returns the last observation AT OR BEFORE the bar close, never a later
    one.  A None before the series starts is the honest answer -- borrowing a later float is
    exactly defect_1 of the screen this module replaces."""
    series = ((_T0 + timedelta(days=5), 100.0), (_T0 + timedelta(days=10), 200.0))
    assert circulating_at(series, _T0) is None
    assert circulating_at(series, _T0 + timedelta(days=5)) == 100.0
    assert circulating_at(series, _T0 + timedelta(days=9, hours=23)) == 100.0
    assert circulating_at(series, _T0 + timedelta(days=10)) == 200.0
    assert circulating_at(series, _T0 + timedelta(days=999)) == 200.0


def test_no_dated_float_yields_nan_not_a_snapshot_fallback():
    """The construction must produce NaN where no dated denominator exists, so the row is
    dropped.  A fallback to a current-day snapshot would rebuild defect_1."""
    closes = _closes(6)
    late = ((closes[3], 1_000.0),)
    rel = (UnlockRelease("X", closes[5], 10.0),)
    out = build_series(rel, late, closes, construction="C1_forward_fraction", window_days=7)
    assert np.isnan(out[0]) and np.isnan(out[2])
    assert np.isfinite(out[3])


def test_undeclared_construction_is_refused():
    with pytest.raises(ValueError, match="undeclared construction"):
        build_series((), _supply(3), _closes(3), construction="C9_after_the_fact", window_days=7)


# --------------------------------------------------------------------- 2/3. lead vs coincide


def _panel(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    sig = rng.normal(size=n)
    noise = rng.normal(0.0, 0.02, size=n)
    return sig, noise


#: A genuine forward effect that DECAYS over several bars.  Deliberately not a knife-edge
#: one-period effect: an effect concentrated entirely on t+1 is, in the (signal, return) arrays
#: alone, ARITHMETICALLY INDISTINGUISHABLE from a one-period lookahead -- lagging the signal
#: turns its forward skill into contemporaneous skill in both cases -- so the harness's
#: `shift_translates` rail correctly reads it as SUSPECT-LOOKAHEAD.  Verified while building this
#: screen.  What separates a real lead from a leak is the TIMESTAMP ALIGNMENT, which is why the
#: alignment tests above are the load-bearing ones and this is only a detection-sensitivity test.
_DECAY = (1.0, 0.7, 0.5, 0.3)


def test_a_genuinely_leading_signal_is_detected():
    """signal[t] drives returns from t+1 onward, decaying.  The harness must find it and must
    not mistake it for an artifact -- otherwise the screen cannot detect its own mechanism."""
    n = 8000
    sig, noise = _panel(n, seed=7)
    ret = noise.copy()
    for j, w in enumerate(_DECAY):
        ret[j + 1:] += 0.002 * w * sig[: -(j + 1)]   # STRICTLY forward: never touches ret[t]
    out = screen_cell(sig, ret, name="synthetic_lead", horizon_days=1)
    assert out["verdict"] == "SCREEN-INTERESTING", out
    assert out["decontam_passed"] is True
    assert out["shift_translates"] is False
    assert out["powered"] is True                       # the harness's own detection floor
    assert out["power"]["min_detectable_effect"] is not None


def test_the_27_prior_parameterisations_push_the_floor_above_the_reference_effect():
    """A MEASURED CONSEQUENCE OF THE MULTIPLICITY CHARGE, NOT AN INCONVENIENCE.

    Charging the 27 parameterisations already spent on this class raises the critical value, and
    at ~8k symbol-days the smallest IC detectable at 80% power becomes 0.0375 -- ABOVE the
    desk's 0.03 reference effect.  So even a well-sized sample cannot claim a reference-size
    edge on this class after multiplicity, and any future null here is UNDERPOWERED at the
    reference rather than graveyard-grade.  Pinned so it is reported, not discovered late."""
    n = 8000
    sig, noise = _panel(n, seed=7)
    out = screen_cell(sig, noise, name="floor_probe", horizon_days=1)
    power = out["power"]
    assert power["n_tests"] == TOTAL_TRIALS == 63
    assert power["min_detectable_effect"] > power["reference_effect"]
    assert power["label"] == "UNDERPOWERED"
    assert power["alpha"] == 0.05                        # the bar moved, never the alpha


def test_a_knife_edge_one_period_effect_is_refused_as_indistinguishable():
    """AN HONEST LIMIT OF THE INSTRUMENT, PINNED SO IT IS NOT REDISCOVERED AS A BUG.

    When the entire effect lands on exactly t+1 and nothing after, a true lead and a one-period
    lookahead produce the SAME numbers.  The harness refuses rather than guessing, and this test
    asserts the refusal: a screen that resolved this case would be claiming information the
    arrays do not contain."""
    n = 8000
    sig, noise = _panel(n, seed=7)
    ret = noise.copy()
    ret[1:] += 0.010 * sig[:-1]                      # ALL of it on t+1, nothing on t+2
    out = screen_cell(sig, ret, name="knife_edge", horizon_days=1)
    assert out["verdict"] == "SUSPECT-LOOKAHEAD"
    assert out["shift_translates"] is True


def test_a_merely_coincident_signal_is_killed_as_an_artifact():
    """signal[t] moves WITH return[t] and has no forward content.  This is the coinbase/turkey
    failure mode; it must never reach SCREEN-INTERESTING."""
    n = 6000
    sig, noise = _panel(n, seed=11)
    ret = 0.020 * sig + noise                        # same-period, zero lead
    out = screen_cell(sig, ret, name="synthetic_coincident", horizon_days=1)
    assert out["verdict"] in {"TIMING-ARTIFACT", "SCREEN-WEAK", "SCREEN-UNDERPOWERED"}
    assert out["verdict"] != "SCREEN-INTERESTING"


def test_a_strong_coincident_signal_trips_the_decontamination_gate():
    """With enough same-period correlation the verdict must be the artifact label specifically,
    not merely 'weak' -- the gate has to fire, not just fail to fire the other way."""
    n = 6000
    sig, noise = _panel(n, seed=13)
    ret = 0.020 * sig + noise
    ret[1:] += 0.004 * sig[:-1]                      # a little real lead, swamped by contamination
    out = screen_cell(sig, ret, name="synthetic_contaminated", horizon_days=1)
    assert abs(out["same_period_corr"]) > 0.20
    assert out["verdict"] == "TIMING-ARTIFACT"


# --------------------------------------------------------------------- 4. refuse, never fake


def test_missing_schedule_is_reported_not_invented(tmp_path):
    load = load_unlock_schedule(tmp_path / "nope.json")
    assert not load.readable
    assert load.releases == ()
    assert any("absent from this checkout" in m for m in load.missing)


def test_missing_supply_history_is_reported_not_invented(tmp_path):
    load = load_circulating_supply(tmp_path / "nope.jsonl")
    assert not load.readable
    assert load.series == {}
    assert any("absent from this checkout" in m for m in load.missing)


def test_run_screen_refuses_and_names_every_missing_input(tmp_path):
    """Absent data => NOT-READABLE-HERE with the addresses, an INDETERMINATE power label, and
    ZERO cells run.  It must not return a number, and must not record a refutation."""
    report = run_screen(
        schedule_path=tmp_path / "unlock_events.json",
        supply_path=tmp_path / "circulating_supply.jsonl",
        bars=None,
    )
    assert report["status"] == "NOT-READABLE-HERE"
    assert report["verdict"] == "NOT-READABLE-HERE"
    assert report["cells_run"] == 0
    assert report["power"]["label"] == "INDETERMINATE"
    assert report["graveyard"] == []
    blob = " ".join(report["missing_inputs"])
    assert "unlock_events.json" in blob
    assert "circulating_supply.jsonl" in blob
    assert "price panel" in blob
    assert "reentry_condition" in report


# ------------------------------------------------- 4b. the REAL on-disk schema, not a friendly one
#
# These two fixtures are written from the field names the COLLECTORS actually emit, sampled from
# `data/unlock_events.json` and `data/circulating_supply.jsonl`.  That is the whole point of them.
# Every fixture above builds rows out of the field names the loader already understood, so the
# suite was structurally incapable of noticing that neither loader read the real files: the
# schedule chain omitted `ts` and the supply chain omitted `observed_utc`, and BOTH files parsed
# to exactly zero rows for weeks while the weekly cron exited 0.  A fixture that only contains the
# covered fields cannot reveal what its loader is blind to (desk lesson, R0289 class).


def test_schedule_loader_reads_the_real_collector_schema(tmp_path):
    """`ts` + naive `date` is what data/unlock_events.json actually carries.

    `date` alone is naive and is CORRECTLY rejected -- the fix is that `ts` must be consulted,
    not that naive stamps become acceptable.
    """
    p = tmp_path / "unlock_events.json"
    p.write_text(
        json.dumps(
            [
                {
                    "symbol": "GLMUSDT",
                    "protocol": "Golem Network",
                    "ts": 1478822400,
                    "date": "2016-11-11",
                    "tokens": 820000000,
                    "pct_max": 82.0,
                    "category": "publicSale",
                }
            ]
        ),
        encoding="utf-8",
    )
    load = load_unlock_schedule(p)
    assert load.releases, "the real schedule schema must parse; `ts` is the only field dating it"
    assert load.releases[0].symbol == "GLMUSDT"
    assert load.releases[0].instant == datetime(2016, 11, 11, tzinfo=UTC)
    assert not any("dropped" in d for d in load.defects)


def test_supply_loader_reads_the_real_collector_schema(tmp_path):
    """`observed_utc` is what collect_circulating_supply.py writes on every row."""
    p = tmp_path / "circulating_supply.jsonl"
    p.write_text(
        json.dumps(
            {
                "observed_utc": "2026-08-06T05:10:05+00:00",
                "coin_id": "aptos",
                "symbol": "APT",
                "circulating_supply": 845695519.4167547,
                "source": "coingecko/coins",
                "known_from": "2026-08-06T05:10:05+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    load = load_circulating_supply(p)
    assert load.series, "the real supply schema must parse; `observed_utc` is the observation stamp"
    assert load.series["APT"][0][0] == datetime(2026, 8, 6, 5, 10, 5, tzinfo=UTC)
    assert not any("dropped" in d for d in load.defects)


def test_a_naive_only_stamp_is_still_refused(tmp_path):
    """The repair added field names; it did NOT loosen the timezone rail.

    A row datable ONLY by a naive string must still drop, because guessing the zone of a vesting
    cliff is the whole-day misalignment `_as_utc` exists to refuse.
    """
    p = tmp_path / "unlock_events.json"
    p.write_text(
        json.dumps([{"symbol": "XUSDT", "date": "2016-11-11", "tokens": 1.0}]), encoding="utf-8"
    )
    load = load_unlock_schedule(p)
    assert load.releases == ()
    assert any("dropped" in d for d in load.defects)


def test_a_thin_cell_is_underpowered_not_refuted():
    """Too few usable rows must read 'could not tell', never 'dead'.  The graveyard is
    permanent, so an unpowered null must never enter it as a kill."""
    out = screen_cell(np.arange(10.0), np.arange(10.0) * 0.001, name="thin", horizon_days=1)
    assert out["verdict"] == "SCREEN-UNDERPOWERED"
    assert out["n_usable_rows"] == 10
    assert "not refuted" in out["why"]


def test_nan_rows_are_dropped_jointly_and_never_filled():
    """A NaN denominator must shrink n, not be imputed.  Both legs drop the same rows."""
    sig = np.array([1.0, np.nan, 3.0, 4.0, np.nan])
    ret = np.array([0.1, 0.2, 0.3, np.nan, 0.5])
    out = screen_cell(sig, ret, name="gappy", horizon_days=1)
    assert out["n_usable_rows"] == 2          # rows 0 and 2 survive both masks


# --------------------------------------------------------------------- multiplicity is honest


def test_prior_parameterisations_are_charged_not_forgotten():
    """27 parameterisations were already spent on this class.  They must be in the charge, or
    the 28th look is priced as if it were the first."""
    assert PRIOR_PARAMETERISATIONS == 27
    assert NEW_CELLS == len(CONSTRUCTIONS) * 3 * 3 == 36
    assert TOTAL_TRIALS == 63
    assert len(declared_cells()) == NEW_CELLS


def test_every_declared_cell_is_logged_not_just_the_winner():
    """The declared grid is emitted in full even when nothing runs, so a reader can see the
    denominator of the garden of forking paths."""
    report = run_screen(schedule_path=None, supply_path=None, bars=None)
    assert len(report["cells_declared"]) == NEW_CELLS
    names = {(c["construction"], c["window_days"], c["horizon_days"]) for c in
             report["cells_declared"]}
    assert len(names) == NEW_CELLS


def test_power_is_reported_beside_every_verdict():
    """A negative without its detection floor is not a finding.  Every return path carries one."""
    thin = screen_cell(np.arange(5.0), np.arange(5.0), name="t", horizon_days=1)
    assert "power" in thin and thin["power"]["label"] in {"INDETERMINATE", "UNDERPOWERED"}
    sig, noise = _panel(6000, seed=3)
    fat = screen_cell(sig, noise, name="f", horizon_days=1)
    assert fat["power"]["min_detectable_effect"] is not None
    assert fat["power"]["alpha"] == 0.05
    assert fat["power"]["n_tests"] == TOTAL_TRIALS
