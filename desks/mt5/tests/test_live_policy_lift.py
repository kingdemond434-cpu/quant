"""The 2026-11-13 lift of the live symbol whitelist (principal zuck, decision card 19:17:59Z and
19:18Z "All the promoted ones can we put them all on live accounts now I didn't mean to white
list"): every symbol admitted, named quarantines kept, and rows the policy alone retired come back
through the promotion doors."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import live_policy as lp  # noqa: E402

TRACKED = DESK / "data" / "live_sleeve_policy.json"


def test_the_tracked_policy_admits_every_symbol_and_keeps_the_named_quarantines() -> None:
    pol = lp.policy(TRACKED)
    assert "*" in pol.live_symbols
    assert lp.refuse({"symbol": "CHFNOK", "name": "CHFNOK.formula.asia", "family": "formula"},
                     pol) is None
    assert lp.refuse({"symbol": "AUDSGD", "name": "AUDSGD.carry.asia", "family": "carry"},
                     pol) is None
    for name in ("chfnok_carry_asia_p_98d776f3e210d3e2", "USDJPY.asia#rr=2.5",
                 "audchf_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007"):
        assert "quarantined" in (lp.refuse({"symbol": "X", "name": name}, pol) or "")
    # what stands
    assert lp.refuse({"symbol": "XAUUSD", "name": "g", "timeframe": "M15"}, pol)
    assert lp.refuse({"symbol": "EURUSD", "name": "d", "family": "discovered"}, pol)
    assert lp.refuse({"symbol": "XAUUSD", "name": "s", "exec": "scalp_market"}, pol)


def test_a_policy_file_without_quarantines_reads_an_empty_set(tmp_path) -> None:
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"live_symbols": ["XAUUSD"]}))
    assert lp.policy(f).quarantined_sleeves == frozenset()
    assert lp.policy(tmp_path / "absent.json").live_symbols == lp.DEFAULT_LIVE_SYMBOLS


def test_only_policy_retired_rows_with_a_live_candidate_clock_reopen(monkeypatch) -> None:
    import promoter as pr
    pol = lp.Policy(live_symbols=frozenset({"*"}),
                    quarantined_sleeves=frozenset({"Q.carry.asia"}))
    monkeypatch.setattr(lp, "policy", lambda path=None: pol)
    sleeves = [
        {"name": "A.carry.asia", "symbol": "A", "status": "RETIRED", "retired_by": "live_policy"},
        {"name": "B.carry.asia", "symbol": "B", "status": "RETIRED",
         "retire_reason": "roll20 exp -0.1R <= 0"},                       # own evidence
        {"name": "C.carry.asia", "symbol": "C", "status": "RETIRED", "retired_by": "live_policy"},
        {"name": "Q.carry.asia", "symbol": "Q", "status": "RETIRED", "retired_by": "live_policy"},
        {"name": "s1", "symbol": "XAUUSD", "status": "RETIRED", "retired_by": "live_policy"},
    ]
    shadow = {"A.carry.asia": {"status": "PROMOTION CANDIDATE"},
              "B.carry.asia": {"status": "PROMOTION CANDIDATE"},
              "C.carry.asia": {"status": "KILL"},
              "Q.carry.asia": {"status": "PROMOTION CANDIDATE"}}
    scalp = {"sleeves": {"s1": {"status": "PROMOTION_CANDIDATE"}}}
    got = pr.reopen_policy_retirements(sleeves, [shadow, {}, scalp])
    assert got == {"A.carry.asia", "s1"}
    status = {r["name"]: r["status"] for r in sleeves}
    assert status["A.carry.asia"] == pr.POLICY_REOPENED
    assert status["B.carry.asia"] == "RETIRED"          # one-way door on its own evidence
    assert status["C.carry.asia"] == "RETIRED"          # clock no longer a candidate
    assert status["Q.carry.asia"] == "RETIRED"          # still quarantined by name
