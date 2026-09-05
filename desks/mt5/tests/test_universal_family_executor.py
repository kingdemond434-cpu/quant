"""Every certified family reaches capital by the path its own clock replayed.

THE STATE THIS REPLACES, measured 2026-09-05 against `UNIVERSAL_SURVIVORS.canon.json`:

    orthogonal   45 certificates   executor_gap -- population the gateway does not run
    families     20 certificates   executor_gap -- population the gateway does not run
    hunt16        1 certificate    EXECUTABLE

One tradeable certificate out of sixty-six. The gauntlet could certify a cell, the forward clock
could mature it, the promoter could read PROMOTION CANDIDATE -- and the row could never become
capital, because `run_family_sleeves` resolved its constructor through `run_hunt16.FAMILIES` alone
and called it `FAMILIES[fam](df, side)`. That call is right for a windowed hunt16 cell and wrong
for every other family on the desk: `mt5desk.families` and `families_orthogonal` take keyword
params and a keyword side, and most need runtime inputs the executor had no way to rebuild.

THE THREE THINGS THAT HAD TO BE TRUE, and what pins each here:

  ONE CALL SHAPE   `mt5desk.family_call` owns how a constructor is invoked, and `shadow_forward`
                   uses it, so the executor calls a family exactly as the clock that certified it
                   did. A second implementation in the gateway would show up only as a sleeve
                   trading differently live than it was certified -- and that difference IS the
                   strategy.
  ONE RECONSTRUCTION  runtime inputs come from `family_inputs.resolve`, the same call the gauntlet
                   and the clock make, and a cell whose inputs cannot be rebuilt is refused BY
                   NAME rather than run short of them (`family_carry` returns [] without its swap
                   terms, which reads as "never fires" instead of "never fed").
  HUNT16 UNCHANGED the one population that already worked must come through byte-identical, or
                   the certificate that IS executable today silently changes meaning.

And the boundary is widened, not deleted: a family no code answers to, and a chart the box has no
constant for, are still named `executor_gap`s that never become LIVE rows.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

fc = pytest.importorskip("mt5desk.family_call")
dc = pytest.importorskip("mt5desk.decision_core")
ex = pytest.importorskip("mt5desk.executables")

_LADDER = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
_MT5_ENUM = {"TIMEFRAME_M1": 1, "TIMEFRAME_M5": 5, "TIMEFRAME_M15": 15, "TIMEFRAME_M30": 30,
             "TIMEFRAME_H1": 16385, "TIMEFRAME_H4": 16388, "TIMEFRAME_D1": 16408}


@pytest.fixture
def gw(monkeypatch):
    """`mt5desk.gateway` with a stand-in MetaTrader5, so the money path is TESTED off the box."""
    stub = types.ModuleType("MetaTrader5")
    for name, value in _MT5_ENUM.items():
        setattr(stub, name, value)
    monkeypatch.setitem(sys.modules, "MetaTrader5", stub)
    return pytest.importorskip("mt5desk.gateway")


# ------------------------------------------------------------------- ONE CALL SHAPE, NOT TWO

class TestTheCallShapeIsTheClocksOwn:
    def test_a_long_call_omits_side_entirely(self) -> None:
        """LOAD-BEARING ASYMMETRY. Every clock running today was started by a call that did not
        pass `side` for a long cell. Passing it -- even the correct `side=1` -- would re-enter
        families whose `side` default is not 1, changing running clocks for no reason at all."""
        seen: list[dict] = []

        def fam(df, **kw):
            seen.append(dict(kw))
            return []

        fc.signals(fam, "BARS", side=1, params={"rr": 2.0})
        assert seen == [{"rr": 2.0}], "a long call must not pass `side`"

    def test_a_short_passes_side_explicitly_on_the_first_attempt(self) -> None:
        """Discovering the side through `TypeError` cannot tell "this family takes no side" from
        "something inside it raised TypeError", and under the second reading it silently re-runs
        a short certificate long."""
        seen: list[dict] = []

        def fam(df, **kw):
            seen.append(dict(kw))
            return []

        fc.signals(fam, "BARS", side=-1, params={"rr": 2.0})
        assert seen == [{"side": -1, "rr": 2.0}]

    def test_a_family_that_rejects_the_keyword_call_gets_the_positional_fallback(self) -> None:
        calls: list[tuple] = []

        def fam(df, side):
            calls.append((df, side))
            if not calls[:-1]:
                pass
            return []

        # `fam(df, rr=...)` raises TypeError; the fallback passes side explicitly.
        assert fc.signals(fam, "BARS", side=1, params={}) == []
        assert calls[-1] == ("BARS", 1)

    def test_the_hunt16_call_is_positional_and_unparameterised(self) -> None:
        """A DIFFERENT CONTRACT, not a variation: a hunt16 cell takes its parameterisation from
        `WINDOWS[selector]` at sweep time, and `qquant_shadow` replays it as `FAMILIES[fam](h1,
        side)`. Naming it separately is what stops the two shapes being confused at the call."""
        calls: list[tuple] = []
        fc.hunt16_signals(lambda df, side: calls.append((df, side)) or [], "BARS", -1)
        assert calls == [("BARS", -1)]

    def test_the_forward_clock_and_the_executor_ask_the_same_side_question(self) -> None:
        """`shadow_forward._accepts_side` is now an alias for this. Two answers to "does this
        family take a side" ends with a short cell running long on one machine and refused on the
        other."""
        sf = pytest.importorskip("shadow_forward")

        def with_side(df, side=1):
            return []

        def without_side(df, rr=2.0):
            return []

        def with_kwargs(df, **kw):
            return []

        for fn in (with_side, without_side, with_kwargs):
            assert sf._accepts_side(fn) is fc.accepts_side(fn)
        assert fc.accepts_side(with_side) is True
        assert fc.accepts_side(without_side) is False
        assert fc.accepts_side(with_kwargs) is True

    def test_an_unsignaturable_callable_is_refused_rather_than_assumed(self) -> None:
        """Absence is never permission: a callable whose signature cannot be read is treated as
        taking no side, so a SHORT certificate on it is refused instead of traded long."""
        assert fc.accepts_side(len) is False


# --------------------------------------------------------- THE DECISION CORE SELECTS THE REPLAY

def _bars(*stamps: str) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(s, tz="UTC") for s in stamps])
    return pd.DataFrame({"close": [1.0] * len(idx)}, index=idx)


class _Sig:
    def __init__(self, time, ttl_bars=12):
        self.time, self.ttl_bars = time, ttl_bars


class TestTheSignalStepPicksTheRightContract:
    def test_call_params_none_makes_the_hunt16_positional_call(self) -> None:
        """`None` is what every existing caller passes by omission, so the hunt16 path is
        byte-identical to what it was before the universal executor landed."""
        seen: list[tuple] = []
        frame = _bars("2026-09-04T09:00:00")
        bar = frame.index[-1]

        def fam(df, side):
            seen.append(("positional", side))
            return [_Sig(bar)]

        step = dc.family_signal_step(frame, bar, last_signal_bar=None, want_state=None, side=-1,
                                     family_fn=fam, day_states_fn=lambda df: {})
        assert seen == [("positional", -1)]
        assert step.signal is not None

    def test_a_dict_makes_the_parameterised_call(self) -> None:
        seen: list[dict] = []
        frame = _bars("2026-09-04T09:00:00")
        bar = frame.index[-1]

        def fam(df, **kw):
            seen.append(dict(kw))
            return [_Sig(bar)]

        dc.family_signal_step(frame, bar, last_signal_bar=None, want_state=None, side=1,
                              family_fn=fam, day_states_fn=lambda df: {},
                              call_params={"swap_long": 0.4})
        assert seen == [{"swap_long": 0.4}]

    def test_an_empty_dict_still_selects_the_parameterised_call(self) -> None:
        """A price-only orthogonal family needs nothing beyond bars. That is a valid answer, not a
        missing one, and it must not fall through to the hunt16 positional shape."""
        seen: list[str] = []
        frame = _bars("2026-09-04T09:00:00")
        bar = frame.index[-1]

        def fam(df, **kw):
            seen.append("keyword")
            return []

        dc.family_signal_step(frame, bar, last_signal_bar=None, want_state=None, side=1,
                              family_fn=fam, day_states_fn=lambda df: {}, call_params={})
        assert seen == ["keyword"]

    def test_only_a_signal_on_this_exact_bar_acts(self) -> None:
        """The executor considers the newest closed bar and acts only if the family put a signal
        ON it -- a stale signal from an earlier bar is not a live entry."""
        frame = _bars("2026-09-04T08:00:00", "2026-09-04T09:00:00")
        bar = frame.index[-1]
        stale = _Sig(frame.index[0])
        step = dc.family_signal_step(frame, bar, last_signal_bar=None, want_state=None, side=1,
                                     family_fn=lambda df, **kw: [stale],
                                     day_states_fn=lambda df: {}, call_params={})
        assert step.signal is None and step.mark is True

    def test_a_raising_family_is_named_and_not_marked(self) -> None:
        """NOT marked, so the next pass tries again: a transient input fault must not consume the
        sleeve's one decision for this bar."""
        frame = _bars("2026-09-04T09:00:00")

        def boom(df, **kw):
            raise RuntimeError("peer frame empty")

        step = dc.family_signal_step(frame, frame.index[-1], last_signal_bar=None, want_state=None,
                                     side=1, family_fn=boom, day_states_fn=lambda df: {},
                                     call_params={})
        assert step.mark is False and step.signal is None
        assert "peer frame empty" in (step.note or "")


# ------------------------------------------------------------------ THE HOLD IS IN THIS CHART'S BARS

class TestTheTimeExitCountsBarsNotHours:
    def test_h1_is_byte_identical(self) -> None:
        """`bar_minutes` defaults to 60, so every caller written before the ladder resolves to the
        exact timestamp it always did -- including the `+1` for the entry bar."""
        bar = pd.Timestamp("2026-09-04T09:00:00", tz="UTC")
        assert dc.family_ttl_until(bar, 12) == dc.family_ttl_until(bar, 12, 60)
        assert dc.family_ttl_until(bar, 12) == (bar + pd.Timedelta(hours=13)).isoformat()

    @pytest.mark.parametrize(("tf", "minutes"), [("M1", 1), ("M5", 5), ("M15", 15), ("M30", 30),
                                                 ("H1", 60), ("H4", 240), ("D1", 1440)])
    def test_every_chart_holds_for_its_own_bars(self, tf: str, minutes: int) -> None:
        """THE DEFECT, directly: `engine.py` counts `ttl_bars` in INDEX POSITIONS, so a 12-bar TTL
        is twelve hours on H1, one hour on M5 and twelve DAYS on D1. Converting bars to hours held
        an M5 sleeve twelve times too long and closed a D1 sleeve twenty-four times too early --
        a different strategy under the certified one's name, both ways."""
        bar = pd.Timestamp("2026-09-04T09:00:00", tz="UTC")
        got = pd.Timestamp(dc.family_ttl_until(bar, 12, minutes))
        assert got - bar == pd.Timedelta(minutes=13 * minutes), tf

    def test_a_fast_chart_is_no_longer_held_for_hours(self) -> None:
        bar = pd.Timestamp("2026-09-04T09:00:00", tz="UTC")
        m5 = pd.Timestamp(dc.family_ttl_until(bar, 12, 5))
        assert m5 - bar == pd.Timedelta(minutes=65)
        assert m5 - bar < pd.Timedelta(hours=13), "the old conversion held M5 for 13 hours"


# ----------------------------------------------------------------- EVERY CERTIFICATE IS EXECUTABLE

_CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"


class TestTheCanonReachesCapital:
    def _specs(self) -> list[dict]:
        if not _CANON.exists():
            pytest.skip("no canon on this host")
        doc = json.loads(_CANON.read_text("utf-8"))
        return [r.get("shadow_spec") or {} for r in (doc.get("survivors") or {}).values()]

    def test_no_certificate_is_held_out_by_its_population(self) -> None:
        """The measurement this whole change is about. Before it: 65 of 66 refused."""
        gaps = []
        for sp in self._specs():
            fam = str(sp.get("family") or "")
            tf = str((sp.get("params") or {}).get("timeframe") or "H1")
            gap = ex.executor_gap(fam, tf)
            if gap:
                gaps.append(f"{sp.get('symbol')}.{fam}@{tf}: {gap}")
        assert not gaps, f"{len(gaps)} certificate(s) still unexecutable:\n" + "\n".join(gaps[:10])

    def test_every_population_the_canon_uses_is_declared_executable(self) -> None:
        pops = {ex.population_of(str((sp.get("family") or ""))) for sp in self._specs()}
        pops.discard(None)
        assert pops <= set(ex.GATEWAY_FAMILY_POPULATIONS), f"undeclared populations: {pops}"


class TestTheBoundaryIsWidenedNotDeleted:
    def test_a_family_no_code_answers_to_is_still_refused(self) -> None:
        """A certificate for a family with no constructor is an ORPHAN, not a sleeve. Promoting it
        would put a LIVE row in the book the allocator funds and the gateway cannot trade."""
        gap = ex.executor_gap("a_family_that_does_not_exist_anywhere")
        assert gap is not None and "no constructor" in gap

    def test_a_chart_outside_the_sweep_is_still_refused(self) -> None:
        gap = ex.executor_gap("session_range_breakout", "W1")
        assert gap is not None and "W1" in gap

    def test_the_three_populations_are_exactly_what_the_resolver_can_answer(self) -> None:
        """If `population_of` ever learns a fourth name, this fails until someone shows the
        executor runs it -- which is the entire point of keeping the tuple."""
        assert set(ex.GATEWAY_FAMILY_POPULATIONS) == {"hunt16", "families", "orthogonal"}

    def test_all_seven_charts_and_all_three_populations_cross_cleanly(self) -> None:
        cases = [("session_range_breakout", "families"), ("carry", "orthogonal")]
        for fam, want_pop in cases:
            if ex.population_of(fam) != want_pop:
                pytest.skip(f"{fam} is not in the {want_pop} population on this tree")
            for tf in _LADDER:
                assert ex.executor_gap(fam, tf) is None, f"{fam}@{tf}"


# --------------------------------------------------------------- THE EXECUTOR FAILS CLOSED BY NAME

class TestTheGatewayRefusesRatherThanGuesses:
    def test_an_unresolvable_family_yields_no_constructor(self, gw) -> None:
        fn, pop = gw._family_constructor("a_family_that_does_not_exist_anywhere")
        assert fn is None and pop is None

    def test_a_real_family_resolves_with_its_population(self, gw) -> None:
        fn, pop = gw._family_constructor("session_range_breakout")
        assert callable(fn) and pop in ("families", "hunt16", "orthogonal")

    def test_missing_runtime_inputs_refuse_the_row_and_say_why(self, gw, monkeypatch) -> None:
        """FAIL CLOSED. Running a family short of its inputs is worse than not running it: the
        empty result reads as "this mechanism never fires" rather than "nobody fed it"."""
        import mt5desk.family_inputs as fi
        monkeypatch.setattr(fi, "resolve", lambda *a, **k: (None, "no swap terms for EURNOK"))
        params, why = gw._family_call_params({"symbol": "EURNOK", "params": {}}, "carry", None)
        assert params is None
        assert "no swap terms" in why

    def test_a_price_only_family_gets_an_empty_dict_not_a_refusal(self, gw, monkeypatch) -> None:
        import mt5desk.family_inputs as fi
        monkeypatch.setattr(fi, "resolve", lambda *a, **k: ({}, ""))
        params, why = gw._family_call_params({"symbol": "EURUSD", "params": {}},
                                             "session_range_breakout", None)
        assert params == {} and why == ""

    def test_a_raising_reconstruction_is_caught_and_named(self, gw, monkeypatch) -> None:
        """The gateway pass must survive one bad row. An exception escaping here would take every
        other certified sleeve's decision with it."""
        import mt5desk.family_inputs as fi

        def boom(*a, **k):
            raise ValueError("peer parquet truncated")

        monkeypatch.setattr(fi, "resolve", boom)
        params, why = gw._family_call_params({"symbol": "EURUSD", "params": {}}, "carry", None)
        assert params is None and "peer parquet truncated" in why

    def test_the_side_question_is_family_calls_answer(self, gw) -> None:
        assert gw._family_takes_side(lambda df, side=1: []) is True
        assert gw._family_takes_side(lambda df, rr=2.0: []) is False
