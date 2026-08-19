"""The ranker's guarantees, with the leak test first because it matters most.

A cross-sectional ranker fed one forward-looking field posts a spectacular IC
and loses real money, and the brief is where that would happen -- it is the only
place market data is turned into text. So the brief is corrupted-future tested
exactly like the signal families are.

Everything else here is about refusing to be fooled by our own machinery: a
hallucinated symbol taints the whole read rather than being dropped, an
unparseable answer is an error rather than "no opinion", and the model is
required to have a free deterministic opponent so that beating nothing cannot
be mistaken for a result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.analyst_rank import (BaselineRanker, ClaudeCodeRanker, Pick,   # noqa: E402
                                  RankError, RankRead, build_brief)


def frame(close, wick=0.4):
    close = np.asarray(close, float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) + wick,
         "low": np.minimum(open_, close) - wick, "close": close},
        index=pd.date_range("2024-01-01", periods=len(close), freq="1h"))


def universe(n=400, seed=1):
    rng = np.random.default_rng(seed)
    out = {}
    specs = {"XAUUSD": (2000.0, 0.9, 1.5), "EURUSD": (1.08, 0.0, 0.0006),
             "USDJPY": (150.0, -0.05, 0.12), "BTCUSD": (60000.0, 25.0, 400.0)}
    for sym, (base, drift, vol) in specs.items():
        c = base + np.cumsum(rng.normal(drift, vol, n))
        out[sym] = frame(c, wick=vol * 0.3)
    return out


# ------------------------------------------------------------- the leak test

def test_the_brief_cannot_see_past_its_own_bar():
    """Corrupt everything after i; the brief built at i must be identical."""
    u = universe()
    i = 300
    clean = build_brief(u, i)
    rng = np.random.default_rng(7)
    dirty = {}
    for sym, df in u.items():
        d = df.copy()
        tail = d["close"].iloc[i] + np.cumsum(
            rng.normal(0, float(d["close"].std()) * 0.5, len(d) - i - 1))
        for col, v in (("open", tail), ("close", tail),
                       ("high", tail * 1.001), ("low", tail * 0.999)):
            d.iloc[i + 1:, d.columns.get_loc(col)] = v
        dirty[sym] = d
    assert build_brief(dirty, i).render() == clean.render(), \
        "the brief changed when only LATER bars changed: it reads the future"


def test_the_brief_carries_no_prices():
    """Gold at 4,500 and EURUSD at 1.08 must be comparable in one list."""
    txt = build_brief(universe(), 300).render()
    assert "2000" not in txt and "60000" not in txt and "1.08000" not in txt


def test_the_brief_is_scale_free():
    u = universe()
    scaled = {k: v * 7.0 for k, v in u.items()}
    assert build_brief(scaled, 300).render() == build_brief(u, 300).render()


# ----------------------------------------------------------- the free opponent

def test_the_baseline_ranks_and_costs_nothing():
    r = BaselineRanker().rank(build_brief(universe(), 300))
    assert r.ranker == "baseline"
    assert all(p.side in (1, -1) and 1 <= p.conviction <= 5 for p in r.picks)
    assert len(r.picks) <= 5


def test_the_baseline_skips_dying_trends():
    b = build_brief(universe(), 300)
    dying = {r.symbol for r in b.rows if r.dying}
    picked = {p.symbol for p in BaselineRanker().rank(b).picks}
    assert not (picked & dying)


def test_a_flat_cross_section_yields_no_picks():
    flat = {s: frame(np.full(400, v)) for s, v in
            (("A", 100.0), ("B", 200.0), ("C", 300.0))}
    assert BaselineRanker().rank(build_brief(flat, 300)).picks == ()


# ------------------------------------------------------------------ weights

def test_weights_are_unit_gross_not_unit_net():
    """A market-neutral spread must not be silently levered up."""
    r = RankRead(picks=(Pick("A", 1, 3), Pick("B", -1, 3)), ranker="t", model="t")
    w = r.as_weights(["A", "B", "C"])
    assert np.abs(w).sum() == pytest.approx(1.0)
    assert w.sum() == pytest.approx(0.0)
    assert w[2] == 0.0


def test_no_picks_means_no_exposure():
    w = RankRead(picks=(), ranker="t", model="t").as_weights(["A", "B"])
    assert np.abs(w).sum() == 0.0


# ------------------------------------------------------------ model refusals

def envelope(result, **over):
    e = {"is_error": False, "subtype": "success", "permission_denials": [],
         "result": result, "total_cost_usd": 0.05,
         "usage": {"input_tokens": 900, "cache_creation_input_tokens": 26488,
                   "cache_read_input_tokens": 0, "output_tokens": 400}}
    e.update(over)
    return e


def fake(result, seen=None):
    def run(argv, prompt):
        if seen is not None:
            seen.append((argv, prompt))
        return envelope(result) if isinstance(result, str) else result
    return run


def good_json():
    return json.dumps({"picks": [{"symbol": "XAUUSD", "side": "LONG",
                                  "conviction": 4},
                                 {"symbol": "USDJPY", "side": "SHORT",
                                  "conviction": 2}], "note": "gold leads"})


def test_a_valid_read_parses():
    b = build_brief(universe(), 300)
    r = ClaudeCodeRanker(runner=fake(good_json())).rank(b)
    assert [(p.symbol, p.side, p.conviction) for p in r.picks] == \
        [("XAUUSD", 1, 4), ("USDJPY", -1, 2)]
    assert r.usage["in"] == 900 + 26488


def test_a_fenced_answer_parses_because_the_cli_really_does_that():
    b = build_brief(universe(), 300)
    r = ClaudeCodeRanker(runner=fake("```json\n" + good_json() + "\n```")).rank(b)
    assert len(r.picks) == 2


def test_a_hallucinated_symbol_taints_the_whole_read():
    """Dropping it would keep picks produced by the same ungrounded pass."""
    bad = json.dumps({"picks": [{"symbol": "XAUUSD", "side": "LONG", "conviction": 3},
                                {"symbol": "DOGEUSD", "side": "LONG", "conviction": 5}]})
    with pytest.raises(RankError, match="not in the brief"):
        ClaudeCodeRanker(runner=fake(bad)).rank(build_brief(universe(), 300))


def test_a_duplicated_symbol_is_refused():
    bad = json.dumps({"picks": [{"symbol": "XAUUSD", "side": "LONG", "conviction": 3},
                                {"symbol": "XAUUSD", "side": "SHORT", "conviction": 3}]})
    with pytest.raises(RankError, match="twice"):
        ClaudeCodeRanker(runner=fake(bad)).rank(build_brief(universe(), 300))


@pytest.mark.parametrize("body,msg", [
    (json.dumps({"picks": [{"symbol": "XAUUSD", "side": "MAYBE", "conviction": 3}]}), "bad side"),
    (json.dumps({"picks": [{"symbol": "XAUUSD", "side": "LONG", "conviction": 9}]}), "bad conviction"),
    (json.dumps({"picks": [{"symbol": "XAUUSD", "side": "LONG", "conviction": "high"}]}), "bad conviction"),
    ("gold looks strong today", "not JSON"),
])
def test_malformed_reads_raise_rather_than_defaulting(body, msg):
    with pytest.raises(RankError, match=msg):
        ClaudeCodeRanker(runner=fake(body)).rank(build_brief(universe(), 300))


def test_an_empty_pick_list_is_allowed_because_flat_is_an_answer():
    r = ClaudeCodeRanker(runner=fake(json.dumps({"picks": [], "note": "chop"}))
                         ).rank(build_brief(universe(), 300))
    assert r.picks == () and r.note == "chop"


def test_too_many_picks_is_refused():
    many = json.dumps({"picks": [{"symbol": s, "side": "LONG", "conviction": 1}
                                 for s in ("XAUUSD", "EURUSD", "USDJPY", "BTCUSD")]})
    b = build_brief(universe(), 300, top_n=2)
    with pytest.raises(RankError, match="asked for at most"):
        ClaudeCodeRanker(runner=fake(many)).rank(b)


def test_subscription_mode_strips_the_key_and_reports_zero(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leftover")
    rk = ClaudeCodeRanker(billed=False, runner=fake(good_json()))
    assert "ANTHROPIC_API_KEY" not in rk._env()
    assert rk.rank(build_brief(universe(), 300)).usage["cost_usd"] == 0.0


def test_the_prompt_carries_the_cross_section_and_the_schema():
    seen = []
    ClaudeCodeRanker(runner=fake(good_json(), seen)).rank(build_brief(universe(), 300))
    argv, prompt = seen[0]
    assert argv[argv.index("--allowed-tools") + 1] == ""
    assert "XAUUSD" in prompt and "conviction" in prompt and "dimensionless" in prompt
