"""A conditioned sleeve must stay conditioned from shadow to live, or not trade at all.

The chain was state-blind end to end: shadow_forward keyed on (symbol, window), promoter wrote no
state field, and gateway.sleeve_set rebuilt every sleeve from `window` alone. Promoting
"CADJPY asia FAILED_BREAK" would have traded CADJPY asia on EVERY day -- carrying the name and
risk budget of a strategy measured at +0.276R while running the unconditioned one at +0.163R,
with nothing anywhere reporting the substitution.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_SF = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
_PR = (_DESK / "research" / "promoter.py").read_text(encoding="utf-8")


def _state_allows():
    tree = ast.parse(_GW)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "state_allows")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gw>", "exec"), ns)
    return ns["state_allows"]


ALLOWS = _state_allows()
_H1 = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]},
                   index=pd.to_datetime(["2026-08-17 07:00"], utc=True))


def test_an_unconditioned_sleeve_always_trades():
    ok, why = ALLOWS({"name": "gold_asia"}, _H1, None)
    assert ok and why == ""


def test_a_conditioned_sleeve_refuses_when_the_state_cannot_be_computed():
    """FAILS CLOSED. The alternative is trading the unconditioned strategy under a conditioned
    sleeve's name and risk budget -- absence of a state is not permission."""
    ok, why = ALLOWS({"name": "x", "state": "FAILED_BREAK"}, None, None)
    assert not ok
    assert "UNCOMPUTABLE" in why or "unknown" in why


def test_a_conditioned_sleeve_refuses_on_a_state_mismatch(monkeypatch):
    import research.run_hunt12 as h12
    monkeypatch.setattr(h12, "day_states", lambda h1: {"D": "NORMAL_DAY"})
    ok, why = ALLOWS({"name": "x", "state": "FAILED_BREAK"}, _H1, "D")
    assert not ok and "NORMAL_DAY" in why


def test_a_conditioned_sleeve_trades_on_a_match(monkeypatch):
    import research.run_hunt12 as h12
    monkeypatch.setattr(h12, "day_states", lambda h1: {"D": "FAILED_BREAK"})
    ok, why = ALLOWS({"name": "x", "state": "FAILED_BREAK"}, _H1, "D")
    assert ok and why == ""


def test_shadow_carries_state_for_hunt12_and_macro_candidates():
    from shadow_forward import SLEEVES
    assert all(len(t) == 3 for t in SLEEVES), "SLEEVES rows must be (sym, window, state)"
    conditioned = [t for t in SLEEVES if t[2]]
    assert len(conditioned) == 14, (
        f"expected 9 hunt12 plus 5 macro-conditioned candidates, found {len(conditioned)}"
    )
    assert ("CADJPY", "asia", "FAILED_BREAK") in SLEEVES
    assert len([t for t in SLEEVES if t[2] == "MACRO_FAV"]) == 5
    # the hunt6 ten must survive unchanged
    assert ("XAUUSD", "asia", None) in SLEEVES
    assert len([t for t in SLEEVES if t[2] is None]) == 10


def test_the_promoter_parses_a_three_part_key():
    """`split(".", 1)` put "asia.FAILED_BREAK" into `win`, which then fails the gateway's window
    whitelist and drops the sleeve silently -- a conditioned candidate would meet every promotion
    criterion forever and never promote, with no error raised anywhere."""
    assert 'key.split(".", 1)' not in _PR, "the two-part split is back"
    assert 'parts = key.split(".")' in _PR
    key = "CADJPY.asia.FAILED_BREAK"
    parts = key.split(".")
    assert (parts[0], parts[1], parts[2]) == ("CADJPY", "asia", "FAILED_BREAK")
    assert len(["CADJPY", "asia"]) == 2, "unconditioned keys must still parse"


def test_every_link_in_the_chain_carries_the_state():
    """A gate applied at only one layer is not a gate."""
    assert '"state": cond' in _PR, "promoter does not write the state"
    assert '"state": s.get("state")' in _GW, "gateway does not read the state"
    assert "state_allows(s, df" in _GW, "the state gate is never applied in the trading path"
    assert "day_states(h1)" in _SF, "shadow does not condition its replay"


def test_the_state_gate_runs_before_a_bracket_is_computed():
    """Ordering matters: computing a bracket for a sleeve that must not trade wastes nothing but
    invites a later edit to place it."""
    i_gate = _GW.index("state_allows(s, df")
    i_range = _GW.index("rng2 = day_range(df")
    assert i_gate < i_range


# --------------------------------------------------------- the verdict needs evidence

def test_no_terminal_verdict_below_the_evidence_floor():
    """THE 14-DAY CLOCK WAS EXECUTING SLOW SLEEVES AT RANDOM. A cell firing ~80x/yr produces
    about 3 trades in 14 days, and at n=3 a genuinely good +0.276R edge is KILLED 36% of the
    time -- permanently, in both directions. The clock still runs; it just cannot decide on a
    sample that is more likely to be wrong than right."""
    from shadow_forward import MIN_VERDICT_TRADES, VERDICT_MIN_DAYS
    assert MIN_VERDICT_TRADES >= 20, "the evidence floor is too low to beat a coin flip"
    assert VERDICT_MIN_DAYS == 14, "the clock itself should be unchanged"
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert 'if st["n"] < MIN_VERDICT_TRADES:' in src
    i_defer = src.index('st["n"] < MIN_VERDICT_TRADES')
    i_kill = src.index('st["status"] = "KILL"')
    i_prom = src.index('st["status"] = "PROMOTION CANDIDATE"')
    assert i_defer < i_prom < i_kill, (
        "the evidence floor must be checked BEFORE either terminal branch")


def test_deferral_keeps_the_sleeve_active_rather_than_killing_it():
    """A slow edge must never be stuck AND never executed: it stays ACTIVE, keeps accruing, and
    promotes the moment it has evidence. Shadow uses no capital, so waiting is free."""
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    block = src[src.index('if st["n"] < MIN_VERDICT_TRADES:'):src.index('elif st["exp_r"]')]
    assert '"KILL"' not in block, "the deferral branch kills the sleeve"
    assert 'st["status"]' not in block, "the deferral branch changes status; it must not"
    assert "DEFERRED" in block
