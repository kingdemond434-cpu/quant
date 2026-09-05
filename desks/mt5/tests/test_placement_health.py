"""The gateway ran four days with every order refused and said nothing useful.

From data/gateway_state.json, 2026-08-14: all four sleeves, both sides, 10015
and 10017. `place_bracket` logged each retcode and returned; nothing counted
them, nothing escalated, nothing stopped. Total failure and a quiet market
produced the same silence, because nothing ever checked for SUCCESS.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as _dc  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_CORE_SRC = (_DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")


def _load(tmp_paused: Path):
    """`diagnose`, `entry_is_legal` and the placement verdict come from the decision core, by
    import. `note_placement` stays in the gateway -- it writes the pause file -- and is exec'd
    out of the gateway's source over that same core, with the pause path, clock and log faked."""
    logged: list = []
    tree = ast.parse(_SRC)
    ns = {k: v for k, v in vars(_dc).items() if not k.startswith("__")}
    ns.update({"PAUSED": tmp_paused, "now": lambda: "2026-08-18T00:00:00+00:00",
               "log": logged.append})
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "note_placement"]
    assert keep, "note_placement is no longer defined in gateway.py"
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    ns["_logged"] = logged
    return ns


@pytest.fixture()
def gw(tmp_path):
    return _load(tmp_path / "GATEWAY_PAUSED")


def _rej(code=10017):
    return [{"side": "buy_stop", "retcode": code, "comment": "Trade disabled"},
            {"side": "sell_stop", "retcode": code, "comment": "Trade disabled"}]


def _ok():
    return [{"side": "buy_stop", "retcode": 10009, "comment": "Done"},
            {"side": "sell_stop", "retcode": 10009, "comment": "Done"}]


# ------------------------------------------------------------- diagnosis

def test_a_retcode_becomes_something_an_operator_can_act_on():
    """A bare number in a state file is not a diagnosis."""
    d = _load(Path("/tmp/x"))["diagnose"](10017)
    assert "Trade disabled" in d
    assert "Allow algorithmic trading" in d


def test_the_10015_diagnosis_names_the_actual_cause(gw):
    """It is the ENTRY price inside the freeze band, not the stops."""
    d = gw["diagnose"](10015)
    assert "PENDING ORDER PRICE" in d and "stops_level points ABOVE" in d


def test_a_success_diagnoses_to_nothing(gw):
    assert gw["diagnose"](10009) == "" and gw["diagnose"](10008) == ""


def test_a_lost_connection_is_distinguished_from_a_rejection(gw):
    assert "terminal connection is gone" in gw["diagnose"](None)


def test_an_unknown_retcode_says_so_rather_than_inventing_a_cause(gw):
    assert "not a retcode this desk has seen" in gw["diagnose"](99999)


# ---------------------------------------------------- the escalation

def test_one_bad_pass_does_not_pause_the_desk(gw):
    """One can be a bad minute at the open."""
    st = {}
    assert gw["note_placement"](st, "asia", _rej()) is True
    assert not gw["PAUSED"].exists()


def test_repeated_total_rejection_pauses_the_desk(gw):
    """THE WHOLE POINT. Four days of this happened and nothing stopped."""
    st = {}
    gw["note_placement"](st, "asia", _rej())
    assert gw["note_placement"](st, "asia", _rej()) is False
    assert gw["PAUSED"].exists()


def test_the_pause_file_says_why_and_how_to_clear_it(gw):
    st = {}
    for _ in range(gw["MAX_TOTAL_REJECTIONS"]):
        gw["note_placement"](st, "asia", _rej(10017))
    text = gw["PAUSED"].read_text()
    assert "ZERO accepted" in text
    assert "Trade disabled" in text
    assert "delete this file to re-arm" in text


def test_a_single_accepted_order_resets_the_counter(gw):
    st = {}
    gw["note_placement"](st, "asia", _rej())
    gw["note_placement"](st, "asia", [_ok()[0], _rej()[1]])
    assert st["placement_health"]["consecutive_total_rejections"] == 0
    assert not gw["PAUSED"].exists()


def test_success_is_timestamped_so_staleness_is_visible(gw):
    st = {}
    gw["note_placement"](st, "asia", _ok())
    assert st["placement_health"]["last_ok"]


def test_the_last_error_is_kept_with_its_diagnosis(gw):
    st = {}
    gw["note_placement"](st, "asia", _rej(10015))
    err = st["placement_health"]["last_error"]
    assert err["sleeve"] == "asia"
    assert any("Invalid price" in d for d in err["diagnoses"])


def test_the_desk_pauses_the_same_file_the_operator_uses(gw):
    """A second, private kill switch is one the operator does not know about."""
    assert "PAUSED = BASE / \"data\" / \"GATEWAY_PAUSED\"" in _SRC


# --------------------------------------------- unavailable is not rejected

def test_an_unavailable_bracket_does_not_count_toward_the_pause(gw):
    """A desk that paused because price sat on the range edge would stop working
    on exactly the days its strategy correctly stands aside."""
    st = {}
    una = [{"side": "buy_stop", "retcode": None, "unavailable": True},
           {"side": "sell_stop", "retcode": None, "unavailable": True}]
    for _ in range(5):
        assert gw["note_placement"](st, "asia", una) is True
    assert not gw["PAUSED"].exists()


def test_a_mixed_pass_still_counts_the_real_rejection(gw):
    st = {}
    mixed = [{"side": "buy_stop", "retcode": None, "unavailable": True},
             {"side": "sell_stop", "retcode": 10017, "comment": "Trade disabled"}]
    gw["note_placement"](st, "asia", mixed)
    assert st["placement_health"]["consecutive_total_rejections"] == 1


# ------------------------------------------------- the 10015 cause itself

def test_a_buy_stop_too_close_to_the_ask_is_refused_before_sending(gw):
    ok, why = gw["entry_is_legal"](4360.50, "buy_stop", 4360.0, 4360.30,
                                   point=0.01, stops_level=50)
    assert not ok and "NOT AVAILABLE" in why


def test_a_buy_stop_clear_of_the_band_is_legal(gw):
    ok, why = gw["entry_is_legal"](4365.0, "buy_stop", 4360.0, 4360.30,
                                   point=0.01, stops_level=50)
    assert ok and why == ""


def test_a_sell_stop_too_close_to_the_bid_is_refused(gw):
    ok, why = gw["entry_is_legal"](4359.90, "sell_stop", 4360.0, 4360.30,
                                   point=0.01, stops_level=50)
    assert not ok and "NOT AVAILABLE" in why


def test_the_entry_is_never_pushed_out_to_a_legal_level(gw):
    """Moving it would silently trade a different strategy: the edge was
    measured at the range boundary, not the boundary plus the broker's freeze
    distance."""
    assert "NOT AVAILABLE today rather" in _CORE_SRC
    assert "silently trade a different strategy" in _CORE_SRC


def test_a_zero_stops_level_never_blocks_a_bracket(gw):
    ok, _ = gw["entry_is_legal"](4360.001, "buy_stop", 4360.0, 4360.0,
                                 point=0.01, stops_level=0)
    assert ok


# --------------------------------------------------------- it is wired

def test_place_bracket_actually_calls_the_success_check():
    """The check is only real if the placement path runs it."""
    assert "note_placement(st, sleeve, sent)" in _SRC


def test_place_bracket_checks_legality_before_sending():
    assert "entry_is_legal(" in _SRC
    assert "NOT AVAILABLE [" in _SRC
