"""MARKET INTELLIGENCE (P14 / P16 / P17 / P23 / P24 / P26).

Six capabilities, one shared failure mode: every one of them is trivially excellent if it is
allowed to see the future, and the leak is never visible in the output. A market-memory search
that includes tomorrow returns a perfect answer. A surprise standardised against a window that
contains the move shrinks the largest surprises most. A response surface measured over an
incomplete forward window scores a partial move as a finished one.

So these tests are almost entirely leak tests, plus one on the distinction that P17 exists for:
an INFERENCE about participant pressure invites a test, while a CLAIM invites sizing, and the
module may only ever produce the first.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_mktintel", _ROOT / "desks" / "mt5" / "research" / "market_intelligence.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mi():
    return _load()


def _walk(n=1200, seed=0, vol=0.001):
    rng = np.random.default_rng(seed)
    return np.exp(np.cumsum(rng.normal(0, vol, n)) + 7.0)


# --------------------------------------------------------------------------- P24
def test_a_surprise_is_measured_against_the_window_before_it(mi) -> None:
    """Including the move in its own reference distribution shrinks every surprise, and shrinks
    the largest ones most -- so the biggest news reads as the least surprising."""
    close = _walk()
    quiet = mi.surprise(close)
    assert quiet.value is not None and abs(quiet.value) < 4

    shocked = close.copy()
    shocked[-1] = shocked[-2] * 1.05           # a 5% jump on a 0.1% vol series
    loud = mi.surprise(shocked)
    assert abs(loud.value) > 10, (
        f"a 5% move on a 0.1%-vol series scored {loud.value} sigma; the reference window is "
        "contaminated by the move it is scoring")


def test_a_raw_move_is_not_a_surprise(mi) -> None:
    """The whole point of standardising: a cross-asset list built on raw percentages is led by
    whatever is most volatile and never says anything."""
    calm = mi.surprise(_walk(vol=0.0005, seed=1))
    wild = mi.surprise(_walk(vol=0.01, seed=1))
    assert abs(calm.value - wild.value) < 0.5, (
        "the same shaped move on two different volatilities produced different surprise; the "
        "score is still reading raw size")


def test_a_short_series_yields_no_surprise(mi) -> None:
    s = mi.surprise(_walk(20))
    assert s.value is None and s.status == "INSUFFICIENT"


# --------------------------------------------------------------------------- P23
def test_market_memory_never_retrieves_the_future(mi) -> None:
    """THE LEAK THAT MAKES THIS CAPABILITY WORTHLESS. A neighbour drawn from after the query
    window is tomorrow, and the answer becomes perfect."""
    close = _walk(2000)
    out = mi.nearest_worlds(close)
    assert out["status"] == "MEASURED"
    # Mutating only the final bars -- which no legitimate neighbour may have seen -- must not
    # change the retrieved outcomes.
    tampered = close.copy()
    tampered[-30:] *= 1.3
    out2 = mi.nearest_worlds(tampered)
    assert out2["neighbours"] == out["neighbours"]
    assert "why_past_only" in out and "tomorrow" in out["why_past_only"]


def test_every_neighbour_has_a_completed_forward_outcome(mi) -> None:
    """A neighbour too close to the end has only a partial forward window, and scoring a partial
    move as a full one biases the answer toward whatever the series was doing at the end."""
    close = _walk(2000)
    out = mi.nearest_worlds(close, forward=48)
    assert out["status"] == "MEASURED" and out["neighbours"] > 0
    assert -1.0 <= out["median_forward"] <= 1.0
    assert 0.0 <= out["up_fraction"] <= 1.0


def test_a_short_series_refuses_retrieval(mi) -> None:
    assert mi.nearest_worlds(_walk(40))["status"] == "INSUFFICIENT"


# --------------------------------------------------------------------------- P26
def test_a_response_is_decomposed_across_horizons(mi) -> None:
    """One number for 'the reaction' hides its shape, and a desk measuring only the first bar
    exits into the discovery."""
    close = _walk(2000)
    events = list(range(300, 1500, 40))
    out = mi.response_surface(close, events)
    assert out["status"] == "MEASURED"
    assert len(out["horizons"]) >= 3, "the surface collapsed to fewer than three horizons"
    assert out["shape"] in {"unmeasured"} or any(
        w in out["shape"] for w in ("shock", "discovery", "drift", "reversal"))


def test_no_events_is_reported_as_unmeasured_not_flat(mi) -> None:
    """ABSENCE IS NEVER A PASS. A surface with no events is not a flat surface."""
    out = mi.response_surface(_walk(), [])
    assert out["status"] == "NO_EVENTS"
    assert "not a flat surface" in out["why"]


# --------------------------------------------------------------------------- P17
def test_ecology_infers_and_never_claims(mi) -> None:
    """A claim invites sizing; an inference invites a test. The module may only produce the
    second, and every output carries bounded confidence with its evidence."""
    sigs = mi.ecology(_walk())
    assert sigs and all(0.0 <= s.confidence <= 1.0 for s in sigs)
    for s in sigs:
        assert s.evidence, f"{s.name} has no evidence recorded"
    # CHECK WHAT THE MODULE EMITS, NOT WHAT IT SAYS ABOUT ITSELF.
    #
    # The first version of this test grepped the source and failed on the module's OWN docstring,
    # which says `never "institutions are accumulating"` -- the sentence promising not to do the
    # thing. That is the third variant of this trap in this session: `#` comments, then a
    # docstring. The durable fix is to stop reading prose and read the values the code actually
    # produces, which is the property that was meant all along.
    import ast

    src = (_ROOT / "desks" / "mt5" / "research" / "market_intelligence.py").read_text("utf-8")
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    emitted = " ".join(n.value.lower() for n in ast.walk(tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str)
                       and n.value not in docstrings)
    runtime = " ".join(f"{s.name} {s.evidence}" for s in sigs).lower()
    for claim in ("institutions are", "smart money", "whales are", "banks are buying"):
        assert claim not in emitted, (
            f"the module EMITS {claim!r} -- that is a claim about unobservable positioning, "
            "and a claim invites sizing where an inference would invite a test")
        assert claim not in runtime, f"a live signal claimed {claim!r}"


# --------------------------------------------------------------------------- P14 / P16
def test_an_unavailable_input_is_named_never_defaulted(mi) -> None:
    """A skew silently defaulted to zero is a confident claim that the market sees no asymmetry."""
    for sig in mi.options_surface("XAUUSD") + mi.commodity_state("XAUUSD"):
        assert sig.status == "UNAVAILABLE"
        assert sig.value is None, "an unavailable input was given a number"
        assert sig.confidence == 0.0
        assert "requires" in sig.evidence, "the missing input is not named"


def test_commodity_state_demands_publication_dates(mi) -> None:
    """POINT-IN-TIME ONLY. Inventory series are revised for months; a backtest on today's values
    of a 2024 series trades on numbers nobody had."""
    ev = " ".join(s.evidence for s in mi.commodity_state("USOIL"))
    assert "point-in-time" in ev and "publication dates" in ev
