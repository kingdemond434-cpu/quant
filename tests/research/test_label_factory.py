"""RANK 6 label factory. The one property worth more than all the others: the leakage guard must
FIRE on a label that reads the future, and must NOT fire on one that legitimately uses its declared
confirmation lag. The rest is about refusing to call a state an event.

This is the bug class that produced the bithumb KST/UTC IC-0.72 fake and the kimchi
construction error -- arithmetic that looked fine and was aligned wrong. Two earlier versions of
the guard passed a label that openly read 5 bars ahead, so the negative controls ARE the test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import libs.research.label_factory as lf
from libs.research.label_factory import (
    VERDICT_BLOB,
    VERDICT_COMMON,
    VERDICT_INERT,
    VERDICT_LEAKING,
    VERDICT_VALID,
    LabelSpec,
    build_catalogue,
    default_specs,
    generate,
    validate,
)


@pytest.fixture
def bars() -> pd.DataFrame:
    """A panel with a real vol-regime step at 500 and a liquidation cascade at 300."""
    rng = np.random.default_rng(7)
    n = 900
    vol = np.where(np.arange(n) < 500, 0.008, 0.025)
    ret = rng.normal(0, vol)
    ret[300:305] = -0.09
    close = 100 * np.exp(np.cumsum(ret))
    oi = 1e6 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    oi[300:305] *= 0.90                       # OI COLLAPSES in the cascade: positions closing
    df = pd.DataFrame(
        {"close": close,
         "high": close * (1 + abs(rng.normal(0, 0.004, n))),
         "low": close * (1 - abs(rng.normal(0, 0.004, n))),
         "volume": rng.lognormal(10, 0.6, n),
         "open_interest": oi},
        index=pd.date_range("2024-01-01", periods=n, freq="D"))
    df.loc[df.index[300:305], "volume"] *= 8
    return df


class TestTheLeakageGuardActuallyFires:
    """A 'leak=0' report is worthless unless the test can detect a leak at all."""

    def test_a_label_that_reads_tomorrow_is_caught(self, bars: pd.DataFrame) -> None:
        def cheater(b: pd.DataFrame, **_: float) -> np.ndarray:
            fut = b["close"].shift(-1) / b["close"] - 1.0
            return (fut < -0.02).fillna(False).to_numpy(dtype=np.int8)

        lf.FAMILIES["_cheater"] = (cheater, 0)
        try:
            v = validate(LabelSpec("_cheater", "_cheater"), bars)
            assert v.verdict == VERDICT_LEAKING
            assert v.leak_failures > 0 and not v.usable
        finally:
            lf.FAMILIES.pop("_cheater")

    def test_leakage_outranks_a_base_rate_complaint(self, bars: pd.DataFrame) -> None:
        """A leaking label that ALSO fires too often must report LEAKING -- the fatal one."""
        def leaky_and_common(b: pd.DataFrame, **_: float) -> np.ndarray:
            return (b["close"].shift(-1) > b["close"]).fillna(False).to_numpy(dtype=np.int8)

        lf.FAMILIES["_lc"] = (leaky_and_common, 0)
        try:
            assert validate(LabelSpec("_lc", "_lc"), bars).verdict == VERDICT_LEAKING
        finally:
            lf.FAMILIES.pop("_lc")

    def test_an_inert_label_is_caught_not_praised(self, bars: pd.DataFrame) -> None:
        """All-zeros is maximally causal and completely useless -- the opposite failure."""
        lf.FAMILIES["_inert"] = (lambda b, **_: np.zeros(len(b), dtype=np.int8), 0)
        try:
            v = validate(LabelSpec("_inert", "_inert"), bars)
            assert v.verdict == VERDICT_INERT and not v.responds_to_inputs
        finally:
            lf.FAMILIES.pop("_inert")

    def test_the_four_shipped_families_do_not_leak(self, bars: pd.DataFrame) -> None:
        for spec in default_specs():
            v = validate(spec, bars)
            assert v.leak_failures == 0, f"{spec.id} leaks at lag {spec.known_at_lag}"

    def test_the_lagged_family_is_allowed_its_declared_lag(self, bars: pd.DataFrame) -> None:
        """regime_transition legitimately needs future bars; at lag 0 it WOULD look like a leak."""
        spec = next(s for s in default_specs() if s.family == "regime_transition")
        assert spec.known_at_lag > 0, "a confirmed regime turn cannot be knowable same-bar"
        assert validate(spec, bars).leak_failures == 0
        # the same label declared as lag-0 must be REJECTED -- proving the lag is load-bearing
        mis = LabelSpec("regime_mislabelled", "regime_transition", spec.params, (), 0)
        assert validate(mis, bars).verdict == VERDICT_LEAKING


class TestAStateIsNotAnEvent:
    def test_a_label_firing_most_bars_is_rejected(self, bars: pd.DataFrame) -> None:
        lf.FAMILIES["_always"] = (lambda b, **_: np.ones(len(b), dtype=np.int8), 0)
        try:
            assert validate(LabelSpec("_always", "_always"), bars).verdict == VERDICT_COMMON
        finally:
            lf.FAMILIES.pop("_always")

    def test_one_contiguous_blob_is_a_period_flag_not_an_event(self, bars: pd.DataFrame) -> None:
        def blob(b: pd.DataFrame, **_: float) -> np.ndarray:
            y = np.zeros(len(b), dtype=np.int8)
            y[100:190] = 1                     # one long run == "that stretch of 2024"
            return y

        lf.FAMILIES["_blob"] = (blob, 0)
        try:
            v = validate(LabelSpec("_blob", "_blob"), bars)
            assert v.verdict == VERDICT_BLOB
            assert v.n_events == 1, "90 firings in one run is ONE event, not 90"
        finally:
            lf.FAMILIES.pop("_blob")

    def test_a_vanishingly_rare_label_is_flagged_untestable(self, bars: pd.DataFrame) -> None:
        def rare(b: pd.DataFrame, **_: float) -> np.ndarray:
            # length-safe: the causality check recomputes on TRUNCATED frames, so a generator
            # that assumes the full panel length would IndexError inside validation
            y = np.zeros(len(b), dtype=np.int8)
            if len(b) > 400:
                y[400] = 1
            return y

        lf.FAMILIES["_rare"] = (rare, 0)
        try:
            assert validate(LabelSpec("_rare", "_rare"), bars).verdict != VERDICT_VALID
        finally:
            lf.FAMILIES.pop("_rare")

    def test_the_shipped_families_are_events_on_a_realistic_panel(self, bars: pd.DataFrame) -> None:
        """THREE of the four ship as valid events. `regime_transition` does NOT, and that is a
        real finding rather than a test defect -- see the dedicated test below.

        It was invisible until 2026-07-30 because this whole module failed on a pandas
        FutureWarning first (filterwarnings=error), so eight tests went red for a version reason
        and the one genuine verdict underneath was never read. A suite that fails for the wrong
        reason does not merely waste time; it HIDES the right reason.
        """
        for spec in default_specs():
            if spec.family == "regime_transition":
                continue
            v = validate(spec, bars)
            assert v.verdict == VERDICT_VALID, f"{spec.id}: {v.verdict} {v.notes}"

    def test_regime_transition_is_DEGENERATE_RARE_at_its_shipped_parameters(
            self, bars: pd.DataFrame) -> None:
        """The finding, pinned so it cannot be lost again.

        At win=20, ratio=1.8, confirm=5 the family fires on 0.33% of bars -- below its own 0.5%
        viability floor, i.e. too rare to carry statistical power at any horizon. The label is
        mechanically CORRECT (a vol regime turn that persists really is rare); it is the
        PARAMETERISATION that makes it untestable on a panel this size.

        DELIBERATELY NOT FIXED BY LOOSENING THE FLOOR. The 0.5% bar is the thing that tells the
        desk a label cannot be validated; moving it to make a label pass is the bar-loosening
        failure L1.6 and the L2.8a immutable core forbid, and it would silently re-admit every
        other under-powered family too. Recalibrating `ratio`/`confirm` is a research decision
        with its own evidence requirement, so it is recorded here rather than guessed at.

        strict=True: the day this family becomes viable, THIS TEST FAILS and the finding is
        closed deliberately instead of decaying into a stale xfail nobody rechecks.
        """
        spec = next(s for s in default_specs() if s.family == "regime_transition")
        v = validate(spec, bars)
        assert v.verdict != VERDICT_VALID
        assert any("too rare" in n for n in v.notes), v.notes


class TestMechanismIsLoadBearing:
    def test_deleveraging_refuses_to_emit_without_open_interest(self,
                                                               bars: pd.DataFrame) -> None:
        """Falling price on RISING OI is new shorts; on FALLING OI it is longs being removed.
        Without OI the two are indistinguishable, so emitting anything would be a guess."""
        spec = next(s for s in default_specs() if s.family == "forced_deleveraging")
        assert generate(spec, bars.drop(columns=["open_interest"])).sum() == 0

    def test_deleveraging_ignores_a_crash_where_oi_is_rising(self, bars: pd.DataFrame) -> None:
        spec = next(s for s in default_specs() if s.family == "forced_deleveraging")
        rising = bars.copy()
        rising["open_interest"] = np.linspace(1e6, 3e6, len(rising))   # OI only ever grows
        assert generate(spec, rising).sum() == 0, "a crash on rising OI is not deleveraging"

    def test_deleveraging_fires_on_the_cascade_where_oi_collapses(self,
                                                                 bars: pd.DataFrame) -> None:
        spec = next(s for s in default_specs() if s.family == "forced_deleveraging")
        y = generate(spec, bars)
        assert y[298:308].sum() > 0, "the seeded cascade (OI -10%) must be detected"

    def test_liquidity_stress_needs_volume_confirmation(self, bars: pd.DataFrame) -> None:
        """A big move on NORMAL volume is a clean repricing, not thin depth."""
        spec = next(s for s in default_specs() if s.family == "liquidity_stress")
        flat_vol = bars.copy()
        flat_vol["volume"] = 1000.0            # no volume ever looks unusual
        assert generate(spec, flat_vol).sum() < generate(spec, bars).sum()

    def test_labels_are_binary(self, bars: pd.DataFrame) -> None:
        for spec in default_specs():
            assert set(np.unique(generate(spec, bars))) <= {0, 1}

    def test_length_is_preserved(self, bars: pd.DataFrame) -> None:
        for spec in default_specs():
            assert len(generate(spec, bars)) == len(bars)


class TestVersioningIsByContent:
    def test_retuning_a_parameter_changes_the_version(self) -> None:
        a = LabelSpec("x", "liquidity_stress", {"range_mult": 2.0})
        b = LabelSpec("x", "liquidity_stress", {"range_mult": 2.5})
        assert a.version != b.version, "a redefined label must not reuse its old validation record"

    def test_the_same_definition_hashes_identically(self) -> None:
        p = {"range_mult": 2.0, "atr_win": 20}
        assert (LabelSpec("x", "liquidity_stress", p).version
                == LabelSpec("x", "liquidity_stress", dict(reversed(list(p.items())))).version)

    def test_int_and_float_params_agree(self) -> None:
        """Params are stored as floats for stable hashing; 20 and 20.0 are the same label."""
        assert (LabelSpec("x", "f", {"win": 20}).version
                == LabelSpec("x", "f", {"win": 20.0}).version)

    def test_changing_the_declared_lag_changes_the_version(self) -> None:
        # the lag is part of the DEFINITION -- silently changing it must not keep the old identity
        assert (LabelSpec("x", "f", {}, (), 0).version != LabelSpec("x", "f", {}, (), 5).version)

    def test_lineage_is_carried(self) -> None:
        s = default_specs(inputs=("lake_crypto",))[0]
        assert s.inputs == ("lake_crypto",), "a label must name the panel it was built from"


class TestTheCatalogue:
    def test_it_records_every_family_with_a_verdict(self, bars: pd.DataFrame) -> None:
        recs = build_catalogue(bars, inputs=("lake_crypto",))
        assert len(recs) == len(lf.FAMILIES)
        for r in recs:
            assert r["validation"]["verdict"] and "qualified_id" in r

    def test_a_short_panel_does_not_crash(self) -> None:
        tiny = pd.DataFrame({"close": [1.0, 2.0, 3.0], "high": [1, 2, 3.0],
                             "low": [1, 2, 3.0], "volume": [1, 1, 1.0],
                             "open_interest": [1, 1, 1.0]})
        for r in build_catalogue(tiny):
            assert r["validation"]["verdict"]      # a verdict, not an exception

    def test_every_record_is_json_serialisable(self, bars: pd.DataFrame) -> None:
        import json
        json.dumps(build_catalogue(bars))
