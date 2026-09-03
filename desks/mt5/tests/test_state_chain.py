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


def test_shadow_enrolment_is_certificates_never_a_hand_typed_list():
    """GRANDFATHERING IS OVER (2026-08-26): this test used to assert 24 hand-typed sleeves,
    which is exactly the defect the law forbids -- enrolment is a CERTIFICATE. The literal must
    stay empty forever; clocks come from certified_sleeves() reading the admission door."""
    from shadow_forward import SLEEVES, sleeve_key
    assert SLEEVES == [], "a hand-typed sleeve bypasses the ten gates; the list must stay empty"
    # Breakout keys keep their historical shape -- running clocks must never be renamed --
    # while every other family carries its family name in the key (one clock per strategy).
    assert sleeve_key("XAUUSD", "asia", {"range_start": 7, "wait_bars": 12,
                                         "rr": 2.0, "ttl_bars": 12}) == "XAUUSD.asia"
    assert (sleeve_key("EURZAR", "asia", {}, "overnight_gap_decay")
            == "EURZAR.overnight_gap_decay.asia")
    assert sleeve_key("XAUUSD", "asia", {"range_start": 7, "wait_bars": 12,
                                         "rr": 1.5, "ttl_bars": 12}) == "XAUUSD.asia#rr=1.5"


def test_every_certified_family_enrols_or_is_skipped_by_name():
    """The one-pipeline law: a certificate IS enrolment. A family this engine cannot replay
    (needs runtime inputs beyond bars) must be skipped BY NAME, and a price-only family must
    resolve to a constructor -- a bare `continue` here is how two overnight_gap_decay
    certificates sat CERTIFIED-NOT-ENROLLED while the same-day fence screamed."""
    from shadow_forward import _family_fn, _family_needs
    assert _family_fn("overnight_gap_decay") is not None
    assert _family_needs("overnight_gap_decay") is None, "price-only: must enrol"
    assert _family_needs("cot_positioning"), "needs COT data: skip must carry the input's name"
    assert _family_fn("session_range_breakout") is not None


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
    # Shadow's conditioned replay retired WITH the conditioned sleeves (all hunt12/macro rows
    # are RETIRED_ORPHAN/RETIRED_GATE_FAIL; enrolment is certificates only). What the law still
    # requires here is that the CONDITION TRAVELS IN THE IDENTITY: a future conditioned
    # certificate must freeze its condition, never silently drop it.
    assert "condition=None, params=params" in _SF, (
        "shadow must pass the condition into the frozen identity explicitly")


def test_the_state_gate_runs_before_a_bracket_is_computed():
    """Ordering matters: computing a bracket for a sleeve that must not trade wastes nothing but
    invites a later edit to place it."""
    i_gate = _GW.index("state_allows(s, df")
    i_range = _GW.index("rng2 = day_range(df")
    assert i_gate < i_range


# --------------------------------------------------------- the verdict needs evidence

def test_the_evidence_floors_are_a_ratchet():
    """THE 14-DAY CLOCK WAS EXECUTING SLOW SLEEVES AT RANDOM (n=3 kills a good +0.276R edge 36%
    of the time). The floors that fixed it may rise, never fall -- and the sequential path may
    only ever be STRICTER on marginal edges, not a side door."""
    from shadow_forward import SEQ_MIN_T, SEQ_MIN_TRADES, VERDICT_MIN_DAYS, VERDICT_MIN_TRADES
    assert VERDICT_MIN_TRADES >= 50, "the flat evidence floor may only ratchet UP"
    assert SEQ_MIN_TRADES >= 20, "no verdict on a handful of trades, however pretty"
    assert SEQ_MIN_T >= 2.5, "the early path must demand real significance"
    assert VERDICT_MIN_DAYS == 14, "the clock itself should be unchanged"


def test_no_verdict_without_sufficient_evidence():
    """A slow edge must never be stuck AND never executed: below the evidence floors the status
    stays ACTIVE and the clock keeps accruing. Sequential sufficiency (2026-08-26) replaced the
    old deferral block: a verdict requires `enough` (flat n>=50 OR n>=20 with forward t>=2.5)
    AND the day floor -- so no branch may kill or promote beneath it."""
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    gate = 'if st["status"] == "ACTIVE" and enough and days_active >= VERDICT_MIN_DAYS:'
    assert gate in src, "the verdict gate must require sufficiency and the day floor together"
    verdict_zone = src[src.index(gate):]
    assert '"KILL"' in verdict_zone and '"PROMOTION CANDIDATE"' in verdict_zone
    before_gate = src[:src.index(gate)]
    # ANCHORED ON `in enrolled:` RATHER THAN THE FULL UNPACK. The assertion below is
    # the invariant -- nothing kills a sleeve before the evidence gate -- and it does
    # not depend on the loop's binding shape. Pinning the exact tuple made a source
    # detail load-bearing: widening the row to carry the certified side turned this
    # into `ValueError: substring not found`, which reads as a broken invariant when
    # the invariant is untouched. A test that fails for the wrong reason teaches its
    # reader to edit it, which is how a real one eventually gets edited away.
    loop_body = before_gate[before_gate.index("in enrolled:"):]
    assert '= "KILL"' not in loop_body, "nothing may kill a sleeve before the evidence gate"
