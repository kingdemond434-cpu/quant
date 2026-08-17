"""A trade's evidence is only as good as the account it happened on.

The desk switches brokers by editing one file -- `data/terminal_path.txt`. The moment that points
at a Fusion DEMO terminal, demo fills append to `data/live_ledger.jsonl`: the same file the
promoter reads to RETIRE live sleeves, the same file `armed_forward_exp` reads to judge gold
challengers, the same file markout calls execution evidence. Nothing in the record said which
account produced it, so demo and live were indistinguishable forever after -- and when the live
account is funded, its sleeves would be judged partly on demo history.

Demo fills are not merely different, they are OPTIMISTIC: demo servers typically fill stop orders
at the requested price with no slippage, which is precisely the assumption markout exists to test.
Treating them as execution evidence would confirm the thing being questioned.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.markout import compute  # noqa: E402
from mt5desk.provenance import (  # noqa: E402
    DEMO, LIVE, UNKNOWN, account_kind, current_account, same_account, split_by_account)

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


class _Acc:
    def __init__(self, login, server, trade_mode):
        self.login, self.server, self.trade_mode = login, server, trade_mode


# ------------------------------------------------------------------ classification

def test_the_three_mt5_account_modes_are_classified():
    assert account_kind(0) == DEMO          # ACCOUNT_TRADE_MODE_DEMO
    assert account_kind(1) == DEMO          # CONTEST -- not real money either
    assert account_kind(2) == LIVE          # ACCOUNT_TRADE_MODE_REAL


def test_an_unrecognised_mode_is_UNKNOWN_not_assumed_demo():
    """FAILS CLOSED. Guessing 'demo' would let an unclassifiable real account be treated as
    practice; guessing 'live' would let demo results retire a live sleeve. Neither is safe, so
    the desk refuses to classify and the caller must decide."""
    assert account_kind(99) == UNKNOWN
    assert account_kind(None) == UNKNOWN
    assert account_kind("real") == UNKNOWN


def test_current_account_reads_login_server_and_mode():
    got = current_account(_Acc(5551234, "FusionMarkets-Demo", 0))
    assert got == {"login": 5551234, "server": "FusionMarkets-Demo", "kind": DEMO}


def test_no_terminal_is_an_unknown_account_not_an_absent_one():
    assert current_account(None) == {"login": None, "server": None, "kind": UNKNOWN}


# ---------------------------------------------------------------------- matching

def _row(login=1, server="S", kind=LIVE, **kw):
    return {"account": login, "server": server, "account_kind": kind, **kw}


def test_trades_from_the_same_account_match():
    acc = {"login": 1, "server": "S", "kind": LIVE}
    assert same_account(_row(), acc)


def test_a_different_login_on_the_same_server_does_not_match():
    """Fusion demo and Fusion live share a broker name. The login is what separates them."""
    assert not same_account(_row(login=2), {"login": 1, "server": "S", "kind": LIVE})


def test_a_demo_row_never_matches_a_live_account_even_on_the_same_login():
    """THE DEFECT THIS PREVENTS. A funded live account judged on demo fills."""
    assert not same_account(_row(kind=DEMO), {"login": 1, "server": "S", "kind": LIVE})


def test_a_legacy_row_with_no_account_field_does_not_match_anything():
    """Rows written before provenance existed. They are real trades on SOME account, and the desk
    cannot say which -- so they are never counted as evidence for the account in hand."""
    legacy = {"sleeve": "gold_asia", "r_multiple": 0.4}
    assert not same_account(legacy, {"login": 1, "server": "S", "kind": LIVE})
    assert not same_account(legacy, {"login": None, "server": None, "kind": UNKNOWN})


def test_split_by_account_separates_rather_than_discards():
    """A demo run is valuable evidence about ORDER CONSTRUCTION. It is segregated, not deleted."""
    rows = [_row(login=1, kind=LIVE), _row(login=2, kind=DEMO), _row(login=2, kind=DEMO),
            {"sleeve": "x"}]
    got = split_by_account(rows)
    assert len(got[(1, "S", LIVE)]) == 1
    assert len(got[(2, "S", DEMO)]) == 2
    assert len(got[(None, None, UNKNOWN)]) == 1


# ------------------------------------------------------------------------ wiring

def test_the_gateway_stamps_every_ledger_row():
    """A field nothing writes is not provenance. Checks the wiring rather than literal key names,
    because the stamp is merged from one helper so the field set cannot drift between writers."""
    assert "from mt5desk import provenance" in _GW, "the gateway cannot stamp what it cannot import"
    assert "_prov.stamp(_prov.current_account(mt5.account_info()))" in _GW, (
        "ledger rows are written without account provenance")
    i_stamp = _GW.index("_prov.stamp(")
    i_write = _GW.index("f.write(json.dumps(rec)")
    assert i_stamp < i_write, "the stamp is applied after the row is written"


def test_the_stamp_covers_exactly_what_same_account_compares():
    """The writer and the matcher must agree on the field set, or every row silently fails to
    match and the promoter sees an empty ledger forever."""
    from mt5desk.provenance import stamp
    written = stamp({"login": 1, "server": "S", "kind": LIVE})
    assert same_account(written, {"login": 1, "server": "S", "kind": LIVE})


def test_the_promoter_only_counts_trades_from_the_account_in_hand():
    src = (_DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert "same_account" in src, (
        "promoter reads the ledger without filtering by account -- demo fills can retire a live "
        "sleeve, and demo history can judge a newly funded live one")


# ----------------------------------------------------------------------- markout

def test_markout_reports_the_account_kind_it_measured():
    m = compute([{"ticket": 1, "intended": 2000.0, "side": "buy_stop"}],
                [{"order": 1, "fill_price": 2000.5, "side": 0, "risk_quote": 19.1,
                  "account": 7, "server": "FusionMarkets-Demo", "account_kind": DEMO}])
    assert m.account_kind == DEMO
    assert m.mean_slip_quote == pytest.approx(0.5)


def test_a_demo_markout_says_it_is_not_evidence_of_live_execution():
    """Demo servers fill stops at the requested price. A clean demo markout is the null result you
    would get from a server that never slips -- reporting it as 'tolerable' execution would
    confirm exactly the assumption the module exists to question."""
    from mt5desk.markout import render
    m = compute([{"ticket": 1, "intended": 2000.0, "side": "buy_stop"}],
                [{"order": 1, "fill_price": 2000.0, "side": 0, "risk_quote": 19.1,
                  "account": 7, "server": "FusionMarkets-Demo", "account_kind": DEMO}])
    out = render(m)
    assert "DEMO" in out
    assert "not evidence of live execution" in out


def test_a_mixed_ledger_is_refused_rather_than_averaged():
    """Averaging a demo fill and a live fill produces a number describing neither."""
    m = compute([{"ticket": 1, "intended": 2000.0, "side": "buy_stop"},
                 {"ticket": 2, "intended": 2000.0, "side": "buy_stop"}],
                [{"order": 1, "fill_price": 2000.5, "side": 0, "risk_quote": 19.1,
                  "account": 7, "server": "S", "account_kind": DEMO},
                 {"order": 2, "fill_price": 2001.0, "side": 0, "risk_quote": 19.1,
                  "account": 8, "server": "S", "account_kind": LIVE}])
    assert not m.usable
    assert "MIXED" in m.why
