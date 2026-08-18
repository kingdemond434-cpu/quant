"""Compiling a stranger's code into hypotheses has two ways to go badly: running
it, and misreading it. Most of these tests are about those.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.compiler import (  # noqa: E402
    MIN_COVERAGE, Family, ParseError, Strategy, ablate, census,
    compile_and_ablate, compile_source, detect_language, parse_python,
    parse_source)

MQL = """
#property copyright "someone"
#include <Trade/Trade.mqh>
input int FastEMA = 20;
input int SlowEMA = 50;

int OnInit() { return INIT_SUCCEEDED; }

void OnTick() {
   double fast = iMA(_Symbol, PERIOD_H1, FastEMA, 0, MODE_EMA, PRICE_CLOSE, 0);
   double slow = iMA(_Symbol, PERIOD_H1, SlowEMA, 0, MODE_EMA, PRICE_CLOSE, 0);
   double atr  = iATR(_Symbol, PERIOD_H1, 14, 0);
   if (fast > slow && LiquiditySweepDetected())
      OrderSend(_Symbol, OP_BUY, 0.01, Ask, 3, Ask - atr, Ask + 2*atr);
   if (fast < slow)
      OrderSend(_Symbol, OP_SELL, 0.01, Bid, 3, Bid + atr, Bid - 2*atr);
   Comment("fast=", fast);
   ObjectCreate(0, "line", OBJ_HLINE, 0, 0, fast);
}
"""

PINE = """
//@version=5
strategy("EMA cross", overlay=true)
fast = ta.ema(close, 20)
slow = ta.ema(close, 50)
rsiv = ta.rsi(close, 14)
plot(fast, color=color.blue)
plot(slow)
if ta.crossover(fast, slow) and rsiv < 70
    strategy.entry("long", strategy.long)
if ta.crossunder(fast, slow)
    strategy.entry("short", strategy.short)
"""

PY = """
import pandas as pd

def signals(df):
    ema_fast = df.close.ewm(span=20).mean()
    ema_slow = df.close.ewm(span=50).mean()
    atr = true_range(df).rolling(14).mean()
    out = []
    for i in range(len(df)):
        if ema_fast[i] > ema_slow[i]:
            out.append(("buy", atr[i]))
        elif ema_fast[i] < ema_slow[i]:
            out.append(("sell", atr[i]))
    return out
"""

PLOT_ONLY = """
//@version=5
indicator("just a chart", overlay=true)
plot(ta.ema(close, 20))
plot(ta.ema(close, 50))
label.new(bar_index, high, "hi")
"""


# ---------------------------------------------------- it never runs the input

def test_the_compiler_cannot_execute_what_it_reads():
    """Downloading a stranger's trading code and running it is arbitrary code
    execution with extra steps, and "it's just a strategy" is not a security
    model."""
    src = (_DESK / "mt5desk" / "compiler.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # Bare builtins only — `re.compile` is a regex, not an execution path, and a
    # check that cannot tell them apart is one that gets suppressed.
    bare = {"exec", "eval", "compile", "__import__"}
    # Attribute calls that DO execute, whatever they are called on.
    attrs = {"system", "popen", "check_output", "Popen", "call", "spawn",
             "load_module", "exec_module", "import_module"}
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id in bare:
            hits.append(f"{n.lineno}:{f.id}")
        elif isinstance(f, ast.Attribute) and f.attr in attrs:
            hits.append(f"{n.lineno}:{f.attr}")
    assert not hits, f"compiler can execute input: {hits}"


def test_python_is_parsed_by_ast_not_imported():
    src = (_DESK / "mt5desk" / "compiler.py").read_text(encoding="utf-8")
    assert "ast.parse(src)" in src
    assert "import subprocess" not in src


# ------------------------------------------------------------ the front end

def test_languages_are_detected():
    assert detect_language(MQL) == "mql"
    assert detect_language(PINE) == "pinescript"
    assert detect_language(PY) == "python"


def test_an_mql_expert_yields_its_mechanisms():
    s = compile_source(MQL, "ema_sweep")
    inds = {t.indicator for t in s.terms}
    assert "ema" in inds and "atr" in inds and "sweep" in inds


def test_pine_yields_its_mechanisms():
    s = compile_source(PINE, "pine_cross")
    inds = {t.indicator for t in s.terms}
    assert "ema" in inds and "rsi" in inds


def test_python_is_read_through_the_ast():
    s = parse_python(PY, "py_cross")
    assert s.language == "python"
    assert {"ema", "atr"} & {t.indicator for t in s.terms}


def test_invalid_python_is_refused_rather_than_regex_guessed():
    """Guessing would produce a rule set nobody wrote."""
    with pytest.raises(ParseError, match="not valid Python"):
        parse_python("def broken(:\n  pass", "bad")


def test_plotting_and_comments_do_not_count_as_trading_lines():
    """A file that is three hundred lines of plotting is not a strategy the
    parser failed at."""
    s = compile_source(MQL, "x")
    assert s.lines_trading < s.lines_total


def test_a_repeated_rule_is_one_term_not_eight():
    """A rule referenced on eight lines counted eight times makes the ablation
    family eight times larger, and the trial count with it."""
    s = compile_source(MQL, "x")
    inds = [t.indicator for t in s.terms]
    assert len(inds) == len(set(inds))


def test_direction_is_read_where_it_is_unambiguous():
    s = compile_source(MQL, "x")
    assert any(t.direction in ("long", "short") for t in s.terms)


def test_mql_side_constants_are_recognised():
    """`\\b` does not work here: underscore is a word character, so `\\bbuy\\b`
    never matches OP_BUY, ORDER_TYPE_BUY or POSITION_TYPE_BUY — which is every
    way MQL spells a direction. Every term came back directionless and the
    inversion ablation had nothing to invert."""
    from mt5desk.compiler import _direction
    for s in ("OrderSend(_Symbol, OP_BUY, 0.01)", "type=ORDER_TYPE_BUY",
              "POSITION_TYPE_BUY"):
        assert _direction(s) == "long", s
    for s in ("OrderSend(_Symbol, OP_SELL, 0.01)", "ORDER_TYPE_SELL"):
        assert _direction(s) == "short", s


def test_a_word_merely_containing_buy_is_not_a_direction():
    """Otherwise `overbought` and `buyer` would flip a strategy's side."""
    from mt5desk.compiler import _direction
    assert _direction("if rsi > overbought_level") == "any"
    assert _direction("buyer_count += 1") == "any"


# -------------------------------------------- a bad parse must not look simple

def test_an_unrecognised_file_is_PARTIAL_not_a_simple_strategy():
    """THE QUIET FAILURE. The parser understands three lines of four hundred,
    emits a two-term rule set, and the ablations decompose something nobody
    wrote."""
    s = compile_source("void OnTick(){ ZorbleFlux(); OrderSend(1,2,3); }", "odd")
    assert s.partial
    assert "mostly invented" in s.why


def test_a_file_that_does_not_trade_says_so():
    s = compile_source(PLOT_ONLY, "chart")
    assert s.coverage == 0.0
    assert "does not trade" in s.why


def test_a_partial_parse_refuses_to_ablate():
    """Twelve descendants of an invented rule set spends twelve trials of
    multiplicity budget on a decomposition of nothing."""
    s = compile_source("OrderSend(); ZorbleFlux(); Wibble();", "odd")
    with pytest.raises(ParseError, match="PARTIAL"):
        ablate(s)


def test_an_empty_term_set_refuses_to_ablate():
    s = Strategy("x", "mql", (), coverage=1.0)
    with pytest.raises(ParseError, match="nothing to ablate"):
        ablate(s)


def test_unparsed_lines_are_kept_so_the_gap_is_inspectable():
    s = compile_source("OrderSend(); ZorbleFlux(1,2);", "odd")
    assert s.unparsed


# ---------------------------------------------------------------- ablations

def test_the_family_contains_the_219_3_mutations():
    f = compile_and_ablate(MQL, "ema_sweep")
    muts = {d.mutation for d in f.descendants}
    assert "original" in muts
    assert any(m.startswith("without ") for m in muts)
    assert any(m.endswith(" only") for m in muts)
    assert "opposite direction" in muts
    assert "delayed entry" in muts
    assert "failed-signal reversal" in muts
    assert {"asia session only", "london session only", "ny session only"} <= muts


def test_dropping_a_term_actually_drops_it():
    f = compile_and_ablate(MQL, "x")
    d = next(d for d in f.descendants if d.mutation == "without ema")
    assert "ema" not in {t.indicator for t in d.terms}


def test_isolating_a_term_keeps_only_it():
    f = compile_and_ablate(MQL, "x")
    d = next(d for d in f.descendants if d.mutation == "ema only")
    assert [t.indicator for t in d.terms] == ["ema"]


def test_inversion_flips_every_direction():
    """A system whose INVERSE is profitable has found a real relationship and
    got the sign wrong, which is a better discovery than the original working."""
    f = compile_and_ablate(MQL, "x")
    orig = next(d for d in f.descendants if d.mutation == "original")
    inv = next(d for d in f.descendants if d.mutation == "opposite direction")
    for a, b in zip(orig.terms, inv.terms):
        if a.direction == "long":
            assert b.direction == "short"
        elif a.direction == "short":
            assert b.direction == "long"


def test_every_descendant_carries_its_parent_and_mutation():
    f = compile_and_ablate(MQL, "ema_sweep")
    assert all(d.parent == "ema_sweep" and d.mutation for d in f.descendants)


# ------------------------------------------------- the family IS the trial count

def test_a_family_of_twelve_is_twelve_trials():
    """219.5, and the constitution names this the largest single source of trial
    inflation."""
    f = compile_and_ablate(MQL, "x")
    assert f.n_trials == len(f.descendants)
    assert f.n_trials > 8


def test_the_render_refuses_the_robustness_check_framing():
    f = compile_and_ablate(MQL, "x")
    txt = f.render()
    assert "TRIALS, not one result with" in txt


def test_the_census_counts_trials_across_a_batch():
    fams = [compile_and_ablate(MQL, "a"), compile_and_ablate(PINE, "b")]
    c = census(fams)
    assert c["systems"] == 2
    assert c["trials"] == sum(f.n_trials for f in fams)


def test_the_same_mechanism_twice_is_one_donation():
    """A public corpus is full of the same few ideas rewritten, and counting
    them as distinct doubles the apparent breadth of the search."""
    fams = [compile_and_ablate(MQL, "a"), compile_and_ablate(MQL, "b")]
    c = census(fams)
    assert c["distinct_mechanisms"] == 1 and c["duplicate_donations"] == 1


def test_parameters_do_not_change_the_mechanism_fingerprint():
    """EMA(20)/EMA(50) and EMA(21)/EMA(55) are one hypothesis sampled twice."""
    a = compile_source(MQL, "a")
    b = compile_source(MQL.replace("20", "21").replace("50", "55"), "b")
    assert a.fingerprint() == b.fingerprint()


def test_a_different_mechanism_fingerprints_differently():
    a = compile_source(MQL, "a")
    b = compile_source(PINE, "b")
    assert a.fingerprint() != b.fingerprint()


def test_the_census_points_at_the_deduplication_that_follows():
    c = census([compile_and_ablate(MQL, "a")])
    assert "canonical" in c["note"] and "report both" in c["note"]
