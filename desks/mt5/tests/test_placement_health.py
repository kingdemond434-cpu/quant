"""The gateway ran four days with every order refused and said nothing useful.

From data/gateway_state.json, 2026-08-14: all four sleeves, both sides, 10015
and 10017. `place_bracket` logged each retcode and returned; nothing counted
them, nothing escalated, nothing stopped. Total failure and a quiet market
produced the same silence, because nothing ever checked for SUCCESS.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
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
            if isinstance(n, ast.FunctionDef)
            and n.name in ("note_placement", "_rejection_streak_expired")]
    assert len(keep) == 2, "note_placement / _rejection_streak_expired missing from gateway.py"
    ns.setdefault("datetime", datetime)
    ns.setdefault("UTC", UTC)
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


# ------------------------------------------------ a streak is consecutive in time, not count

def _stale_streak(n: int = 2, at: str = "2026-08-04T04:00:03+00:00") -> dict:
    """The box's own shape on 2026-09-08: a streak of two whose last rejection was two weeks old,
    standing because release identity refused every order in between and no pass ever ran."""
    return {"placement_health": {"consecutive_total_rejections": n, "last_ok": None,
                                 "last_error": {"time": at, "sleeve": "gold_asia",
                                                "diagnoses": ["10027"]}}}


def test_a_two_week_old_streak_is_not_evidence_about_today(gw):
    """The harness clock is 2026-08-18; the streak's last rejection is 2026-08-04. The first
    modern rejection counts from zero: no pause, streak 1, and the reason is logged."""
    st = _stale_streak()
    assert gw["note_placement"](st, "asia", _rej()) is True
    assert st["placement_health"]["consecutive_total_rejections"] == 1
    assert not gw["PAUSED"].exists()
    assert any("older than 24h" in x for x in gw["_logged"])


def test_a_streak_inside_the_window_still_pauses(gw):
    """Two rejections inside a day pause exactly as before -- the law is unchanged."""
    st = _stale_streak(n=1, at="2026-08-17T23:00:00+00:00")     # one hour before the clock
    assert gw["note_placement"](st, "asia", _rej()) is False
    assert gw["PAUSED"].exists()


def test_a_streak_the_desk_cannot_date_is_kept(gw):
    """Absence is not a reason to forget a refusal: no timestamp, or an unreadable one, keeps the
    streak."""
    st = _stale_streak(n=1, at="not a time")
    assert gw["note_placement"](st, "asia", _rej()) is False
    st = {"placement_health": {"consecutive_total_rejections": 1, "last_ok": None,
                               "last_error": None}}
    assert gw["note_placement"](st, "asia", _rej()) is False


def test_the_window_is_a_day_and_lives_in_the_core(gw):
    assert "REJECTION_STREAK_WINDOW_H = 24.0" in _CORE_SRC
    expired = gw["_rejection_streak_expired"]
    assert expired("2026-08-04T04:00:03+00:00", "2026-08-18T00:00:00+00:00")
    assert not expired("2026-08-17T23:00:00+00:00", "2026-08-18T00:00:00+00:00")
    assert not expired("", "2026-08-18T00:00:00+00:00")
    assert not expired("not a time", "2026-08-18T00:00:00+00:00")


# ------------------------------------------------ the streak counts passes, not sleeves

def test_two_sleeves_refused_in_one_pass_are_one_pass(gw):
    """MEASURED 2026-09-08: a gateway armed at 22:40 broker computed both london_am and
    afternoon and sent them in one minute; on a terminal with AutoTrading off that was two total
    rejections in ONE pass -> MAX_TOTAL_REJECTIONS -> GATEWAY_PAUSED on one bad minute, the case
    the number two was chosen to tolerate. The pass stamp `main` writes makes them one."""
    st = {"placement_pass": "2026-08-18T00:00:00+00:00"}
    assert gw["note_placement"](st, "gold_london_am", _rej()) is True
    assert gw["note_placement"](st, "gold_afternoon", _rej()) is True
    assert st["placement_health"]["consecutive_total_rejections"] == 1
    assert st["placement_health"]["last_error"]["sleeve"] == "gold_afternoon"
    assert not gw["PAUSED"].exists()
    assert any("not counted twice" in x for x in gw["_logged"])
    # the NEXT pass, refused again: that is the second consecutive pass, and it pauses
    st["placement_pass"] = "2026-08-18T00:01:00+00:00"
    assert gw["note_placement"](st, "gold_london_am", _rej()) is False
    assert gw["PAUSED"].exists()


def test_without_a_pass_stamp_the_old_per_call_count_stands(gw):
    """A state file from before the stamp existed keeps the stricter behaviour."""
    st = {}
    gw["note_placement"](st, "a", _rej())
    assert gw["note_placement"](st, "b", _rej()) is False
