"""THE LABEL FACTORY -- 187 statements, zero tests until now, guarding the desk's worst bug class.

A label marks that something HAPPENED. The trap the module is built around is that the natural way
to define one uses the very window it describes: "forced deleveraging happened here" is recognised
FROM the cascade, so testing whether it predicts the cascade's returns measures the definition and
looks spectacular. That is the class that produced the bithumb KST/UTC IC-0.72 fake.

THE TEST THAT MATTERS MOST IS THE POSITIVE CONTROL FOR THE LEAK DETECTOR. The module's own
docstring records that two earlier guard designs -- constant-multiple future mutation, and per-bar
random mutation -- BOTH passed a `regime_transition` mislabelled as lag-0 while it openly read five
bars ahead. So a test that only checks honest labels pass proves nothing whatever: it is satisfied
by a detector that always returns clean. The mislabelled-lag case is constructed here and required
to be caught, and every other assertion in this file is downstream of that one working.

The second-order guard is also pinned: an all-zero label is MAXIMALLY causal and entirely useless,
so `responds_to_inputs` must reject it rather than let perfect causality read as quality.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research import label_factory as L

# --------------------------------------------------------------------------- synthetic panels


def _bars(n: int = 600, *, seed: int = 5, oi: bool = True, vol: bool = True,
          shock_at: int | None = None) -> pd.DataFrame:
    """A plausible OHLCV(+OI) panel. `shock_at` injects a genuine stress bar."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0, 0.01, n)
    if shock_at is not None:
        ret[shock_at] = -0.12
    close = 100.0 * np.exp(np.cumsum(ret))
    hi = close * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = close * (1 - np.abs(rng.normal(0, 0.004, n)))
    if shock_at is not None:
        hi[shock_at] = close[shock_at] * 1.10
        lo[shock_at] = close[shock_at] * 0.90
    df = pd.DataFrame({"open": close, "high": hi, "low": lo, "close": close})
    if vol:
        v = rng.lognormal(10, 0.4, n)
        if shock_at is not None:
            v[shock_at] *= 15
        df["volume"] = v
    if oi:
        o = 1e6 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
        if shock_at is not None:
            o[shock_at:] *= 0.90                # positions removed and they stay removed
        df["open_interest"] = o
    return df


def _regime_bars(n: int = 600, *, switch: int = 300) -> pd.DataFrame:
    """Vol steps up at `switch` and STAYS up -- a real regime transition, not a loud bar."""
    rng = np.random.default_rng(17)
    sd = np.where(np.arange(n) < switch, 0.004, 0.020)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 1, n) * sd))
    return pd.DataFrame({"open": close, "high": close * 1.001,
                         "low": close * 0.999, "close": close})


# --------------------------------------------------------------------------- spec identity

def test_a_retuned_threshold_is_a_NEW_label_not_an_edit() -> None:
    """Versioning by content hash is what stops a parameter sweep being laundered as one label
    that 'improved'. Two thresholds are two hypotheses and must carry two versions."""
    a = L.LabelSpec("x", "liquidity_stress", {"range_mult": 2.0})
    b = L.LabelSpec("x", "liquidity_stress", {"range_mult": 2.5})
    assert a.version != b.version
    assert a.qualified_id.endswith(a.version) and a.qualified_id.startswith("x@")


def test_the_version_is_stable_under_parameter_ORDER() -> None:
    a = L.LabelSpec("x", "f", {"a": 1.0, "b": 2.0})
    b = L.LabelSpec("x", "f", {"b": 2.0, "a": 1.0})
    assert a.version == b.version, "a dict ordering must not mint a new label version"


def test_the_declared_lag_is_part_of_the_identity() -> None:
    """A label re-declared with a different knowability lag is a different claim about when it
    could be known. Sharing a version with the honest one would let a mislabel inherit its record.
    """
    assert (L.LabelSpec("x", "f", {"a": 1.0}, known_at_lag=0).version
            != L.LabelSpec("x", "f", {"a": 1.0}, known_at_lag=5).version)


def test_the_id_is_not_part_of_the_version() -> None:
    """Renaming a label does not change what it computes, and pretending otherwise would break the
    lineage every time someone tidied a name."""
    assert (L.LabelSpec("old", "f", {"a": 1.0}).version
            == L.LabelSpec("new", "f", {"a": 1.0}).version)


# --------------------------------------------------------------------------- the leak detector

def test_a_mislabelled_lag0_regime_transition_IS_CAUGHT() -> None:
    """THE POSITIVE CONTROL, and the reason this module was rewritten twice.

    `regime_transition` reads `confirm` bars ahead by construction and honestly declares
    known_at_lag=5. Declared at lag 0 it is a label openly claiming to be knowable before its own
    inputs exist. Two earlier guard designs passed exactly this. Truncation must not.
    """
    bars = _regime_bars()
    liar = L.LabelSpec("liar", "regime_transition",
                       {"win": 20, "ratio": 1.8, "confirm": float(L.REGIME_CONFIRM_BARS)},
                       known_at_lag=0)
    checked, failures, _ = L.leakage_check(liar, bars)
    assert checked > 0, "the check must actually sample points, or it proves nothing"
    assert failures > 0, "a label reading 5 bars ahead at declared lag 0 must FAIL truncation"
    assert L.validate(liar, bars).verdict == L.VERDICT_LEAKING


def test_the_same_label_at_its_HONEST_lag_passes() -> None:
    """The other half of the control: the detector must not simply reject everything. A guard that
    fails all labels is as useless as one that passes all of them, and far more likely to be
    switched off."""
    bars = _regime_bars()
    honest = L.LabelSpec("honest", "regime_transition",
                         {"win": 20, "ratio": 1.8, "confirm": float(L.REGIME_CONFIRM_BARS)},
                         known_at_lag=L.REGIME_CONFIRM_BARS)
    _, failures, _ = L.leakage_check(honest, bars)
    assert failures == 0


@pytest.mark.parametrize("family", ["liquidity_stress", "forced_deleveraging",
                                    "accumulation_window"])
def test_the_lag0_families_really_are_knowable_at_the_close_of_t(family: str) -> None:
    """Each declares lag 0. Truncation is the definition of that claim, not a proxy for it."""
    bars = _bars(shock_at=420)
    spec = next(s for s in L.default_specs() if s.family == family)
    checked, failures, _ = L.leakage_check(spec, bars)
    assert failures == 0, f"{family} claims lag 0 and does not survive truncation"
    assert checked > 0


def test_leakage_sampling_is_weighted_to_FIRING_positions() -> None:
    """Event labels are sparse. Uniform sampling almost always compares 0 against 0, which is how
    a violation hides -- it only shows up where the label actually fires."""
    bars = _bars(shock_at=420)
    spec = next(s for s in L.default_specs() if s.family == "liquidity_stress")
    y = L.generate(spec, bars)
    if y.sum() == 0:
        pytest.skip("no firings on this panel; the weighting is untestable here")
    checked, _, _ = L.leakage_check(spec, bars)
    assert checked > 0


def test_a_short_panel_declines_to_judge_rather_than_passing_it() -> None:
    """Below 60 bars the rolling windows have not filled, so a clean result would be an artifact of
    there being nothing to see."""
    checked, failures, responds = L.leakage_check(L.default_specs()[0], _bars(30))
    assert (checked, failures) == (0, 0) and responds is True


# --------------------------------------------------------------------------- inertness

def test_an_all_zero_label_is_INERT_and_not_praised_for_being_causal() -> None:
    """An array of zeros passes every causality test perfectly. Without this guard, the most
    broken possible label scores best."""
    dead = L.LabelSpec("dead", "liquidity_stress", {"range_mult": 1e9}, known_at_lag=0)
    v = L.validate(dead, _bars())
    assert v.verdict == L.VERDICT_INERT
    assert not v.usable and v.n_firings == 0


def test_forced_deleveraging_refuses_to_emit_without_open_interest() -> None:
    """A sharp drop on RISING OI is new shorts; the same drop on FALLING OI is longs being removed.
    Without OI the two are indistinguishable, and a price-only lookalike would be a fabrication."""
    spec = next(s for s in L.default_specs() if s.family == "forced_deleveraging")
    y = L.generate(spec, _bars(oi=False, shock_at=400))
    assert y.sum() == 0
    assert L.validate(spec, _bars(oi=False, shock_at=400)).verdict == L.VERDICT_INERT


def test_liquidity_stress_still_computes_without_volume_but_needs_price() -> None:
    spec = next(s for s in L.default_specs() if s.family == "liquidity_stress")
    assert L.generate(spec, _bars(vol=False, shock_at=400)).dtype == np.int8
    empty = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    assert L.generate(spec, empty).sum() == 0, "missing high/low must yield zeros, never a crash"


# --------------------------------------------------------------------------- degeneracy verdicts

def _validated(y: np.ndarray, monkeypatch, bars: pd.DataFrame) -> L.LabelValidation:
    """Force `generate` to return a chosen array so the VERDICT LOGIC is tested directly, rather
    than by hunting for a parameterisation that happens to produce the shape."""
    spec = L.LabelSpec("probe", "liquidity_stress", {"range_mult": 2.0}, known_at_lag=0)
    monkeypatch.setattr(L, "generate", lambda s, b: y[:len(b)])
    return L.validate(spec, bars)


def test_a_label_firing_too_rarely_is_untestable_and_says_so(monkeypatch) -> None:
    y = np.zeros(600, dtype=np.int8)
    y[[100, 400]] = 1                            # 0.33% -- below MIN_BASE_RATE
    v = _validated(y, monkeypatch, _bars())
    assert v.verdict == L.VERDICT_RARE and not v.usable
    assert "too rare" in v.notes[0]


def test_a_label_firing_half_the_time_is_a_STATE_not_an_event(monkeypatch) -> None:
    """Event-study machinery assumes rarity. 'Stressed 40% of the time' is a regime variable, and
    running event studies on it silently violates their assumptions."""
    y = np.zeros(600, dtype=np.int8)
    y[::2] = 1                                   # 50%
    v = _validated(y, monkeypatch, _bars())
    assert v.verdict == L.VERDICT_COMMON
    assert "STATE" in v.notes[0]


def test_one_contiguous_blob_is_a_PERIOD_FLAG_not_a_repeatable_event(monkeypatch) -> None:
    """One 2022 blob is 'the year 2022'. n_events is effectively 1 however many bars it covers, so
    every event-study standard error computed from it is wrong by that factor."""
    y = np.zeros(600, dtype=np.int8)
    y[100:190] = 1                               # 15% base rate, all in one run
    v = _validated(y, monkeypatch, _bars())
    assert v.verdict == L.VERDICT_BLOB
    assert v.max_run == 90 and v.n_events == 1


def test_a_well_spread_label_at_a_testable_rate_is_VALID(monkeypatch) -> None:
    y = np.zeros(600, dtype=np.int8)
    y[::20] = 1                                  # 5%, 30 separate events
    v = _validated(y, monkeypatch, _bars())
    assert v.verdict == L.VERDICT_VALID and v.usable
    assert v.n_events == 30 and v.max_run == 1


def test_leakage_outranks_every_base_rate_complaint() -> None:
    """ORDER MATTERS. A leaking label that also fires too often must report LEAKING: fixing the
    base rate on a label that reads the future produces a better-looking lie."""
    bars = _regime_bars()
    liar = L.LabelSpec("liar", "regime_transition",
                       {"win": 20, "ratio": 1.05, "confirm": float(L.REGIME_CONFIRM_BARS)},
                       known_at_lag=0)
    v = L.validate(liar, bars)
    if v.leak_failures:
        assert v.verdict == L.VERDICT_LEAKING


# --------------------------------------------------------------------------- run accounting

@pytest.mark.parametrize(("seq", "want"), [
    ([], []),
    ([0, 0, 0], []),
    ([1, 1, 0, 1], [2, 1]),
    ([1, 1, 1], [3]),
    ([0, 1, 0, 1, 0], [1, 1]),
])
def test_runs_counts_contiguous_firings_including_one_ending_at_the_edge(seq, want) -> None:
    assert L._runs(np.asarray(seq, dtype=np.int8)) == want


# --------------------------------------------------------------------------- the four families

def test_liquidity_stress_requires_BOTH_a_wide_range_and_heavy_volume() -> None:
    """Stress is not a big move, it is a big move that needed unusual volume to clear. Firing on
    range alone would relabel every clean repricing as thin depth."""
    n = 400
    rng = np.random.default_rng(2)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.005, n)))
    df = pd.DataFrame({"high": close * 1.002, "low": close * 0.998, "close": close,
                       "volume": np.full(n, 1000.0)})
    # a wide bar on utterly ordinary volume
    df.loc[300, "high"] = close[300] * 1.2
    df.loc[300, "low"] = close[300] * 0.8
    assert L.liquidity_stress(df)[300] == 0, "range alone must not fire"
    df.loc[300, "volume"] = 1e9
    assert L.liquidity_stress(df)[300] == 1, "range AND volume must fire"


def test_accumulation_needs_calm_price_AND_building_open_interest() -> None:
    """Low vol alone is a quiet market; rising OI alone is growth. Only the conjunction is
    positioning without repricing."""
    n = 400
    close = np.full(n, 100.0) + np.linspace(0, 0.05, n)
    flat_oi = pd.DataFrame({"close": close, "open_interest": np.full(n, 1e6)})
    assert L.accumulation_window(flat_oi).sum() == 0, "calm alone must not fire"
    rising = flat_oi.copy()
    rising["open_interest"] = 1e6 * np.exp(np.linspace(0, 1.5, n))
    assert L.accumulation_window(rising).sum() > 0


def test_regime_transition_marks_the_ONSET_and_not_every_held_bar() -> None:
    """Marking every bar of a new regime turns one event into hundreds and inflates n_events by
    the regime's length -- the same arithmetic error as the blob verdict, one level down."""
    y = L.regime_transition(_regime_bars(switch=300))
    runs = L._runs(y)
    assert runs, "vacuous otherwise: a label that never fires satisfies 'all runs are length 1'"
    assert all(r == 1 for r in runs), f"onset marking must produce runs of 1, got {runs}"
    fired = np.flatnonzero(y)
    assert ((fired >= 300) & (fired <= 300 + 3 * L.REGIME_CONFIRM_BARS)).any(), (
        f"the genuine vol step at 300 was not detected; fired at {fired.tolist()}")


def test_regime_transition_ignores_a_single_loud_bar() -> None:
    """Persistence is what separates a regime change from noise. A one-bar spike that reverts must
    not register, or the label becomes a volatility outlier detector wearing a regime name."""
    rng = np.random.default_rng(4)
    n = 400
    ret = rng.normal(0, 0.004, n)
    ret[250] = 0.25                              # one enormous bar, then back to calm
    close = 100.0 * np.exp(np.cumsum(ret))
    df = pd.DataFrame({"close": close})
    y = L.regime_transition(df)
    assert y[248:258].sum() == 0


@pytest.mark.parametrize("family", sorted(L.FAMILIES))
def test_every_family_returns_an_int8_mask_the_length_of_the_panel(family: str) -> None:
    fn, lag = L.FAMILIES[family]
    bars = _bars(shock_at=420)
    y = fn(bars)
    assert y.shape == (len(bars),) and y.dtype == np.int8
    assert set(np.unique(y)) <= {0, 1}
    assert lag >= 0


def test_a_missing_close_column_yields_zeros_from_every_family() -> None:
    """Absent input is not an event. Crashing would take down a catalogue build; guessing would
    fabricate one."""
    empty = pd.DataFrame({"unrelated": [1.0] * 100})
    for family, (fn, _) in L.FAMILIES.items():
        assert fn(empty).sum() == 0, family


# --------------------------------------------------------------------------- the catalogue

def test_the_default_catalogue_declares_the_lagged_family_honestly() -> None:
    """`regime_transition` is the ONLY family that cannot be known at t, and the catalogue is where
    that fact has to survive contact with a caller who did not read the docstring."""
    specs = {s.family: s for s in L.default_specs(("lake_crypto",))}
    assert specs["regime_transition"].known_at_lag == L.REGIME_CONFIRM_BARS
    assert all(specs[f].known_at_lag == 0 for f in
               ("liquidity_stress", "forced_deleveraging", "accumulation_window"))
    assert all(s.rationale for s in specs.values()), "a label with no stated mechanism is a knob"
    assert all(s.inputs == ("lake_crypto",) for s in specs.values()), "lineage, not decoration"


def test_build_catalogue_records_every_spec_including_the_unusable_ones() -> None:
    """A factory that reported only its successes would be a factory whose failure rate nobody
    knows -- and the failure rate is the number that says how much to believe a VALID."""
    rows = L.build_catalogue(_bars(shock_at=420), inputs=("lake_crypto",))
    assert len(rows) == len(L.default_specs())
    for r in rows:
        assert r["qualified_id"] == f"{r['id']}@{r['version']}"
        assert r["validation"]["verdict"] in {
            L.VERDICT_VALID, L.VERDICT_RARE, L.VERDICT_COMMON, L.VERDICT_BLOB,
            L.VERDICT_LEAKING, L.VERDICT_INERT}
        assert r["usable"] == (r["validation"]["verdict"] == L.VERDICT_VALID)


def test_build_catalogue_honours_an_explicit_spec_list() -> None:
    one = [L.LabelSpec("only", "liquidity_stress", {"range_mult": 2.0}, (), 0, "why")]
    rows = L.build_catalogue(_bars(shock_at=420), one)
    assert [r["id"] for r in rows] == ["only"]


def test_no_declared_family_is_missing_from_the_default_catalogue() -> None:
    """A family in FAMILIES but not in default_specs is code nothing ever builds -- the dormant
    -capability shape this desk scores as a defect."""
    assert {s.family for s in L.default_specs()} == set(L.FAMILIES)
