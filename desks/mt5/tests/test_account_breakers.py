"""THE ACCOUNT BREAKERS (mt5desk.account_breakers): one daily-loss latch and one disconnect breaker,
run by every live account's lanes, each threshold read from `account_profile`.

What is pinned here: the latch trips AT its threshold and not above it, holds for the rest of the
broker day and resets with the next one; the disconnect breaker refuses on a disconnected
terminal, trading switched off and a stale quote; an unreadable state fails CLOSED as UNMEASURED
and is billed; the Fusion rail answers exactly as it did before it was generalised; and every
lane calls the breakers, obeys them by refusing NEW orders only, and bills each refusal.
"""
from __future__ import annotations

import ast
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import account_breakers as ab  # noqa: E402
from mt5desk import account_profile as ap  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import fusion_rails  # noqa: E402

REAL_QUOTE_MAX_AGE_S = 1800.0
NOW = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)


@pytest.fixture
def real_limit(monkeypatch):
    """conftest lifts the quote-age limit for the lane harnesses; these tests put it back."""
    monkeypatch.setattr(ab, "QUOTE_MAX_AGE_S", REAL_QUOTE_MAX_AGE_S)


def _lines() -> list[dict]:
    p = Path(fusion_rails.LEDGER)
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


# ------------------------------------------------------------------ thresholds from the profile
def test_each_venue_threshold_comes_from_account_profile() -> None:
    assert ab.trip_frac("e8")[0] == pytest.approx(ap.E8_PRO.daily_circuit_breaker) == 0.015
    # AT the firm's 5% (audit HOLD f39234fbf MF1), the same 5% the lanes' loss_guard enforces.
    assert ab.trip_frac("ftmo")[0] == pytest.approx(0.05)
    assert ap.PROFILES["ftmo-2step"].daily_loss_limit == 0.05
    # Fusion has no venue limit: its own FUSION_DAILY_LOSS_FRAC stands, unchanged.
    assert ap.LIVE.daily_loss_limit is None and ap.LIVE.daily_circuit_breaker is None
    assert ab.trip_frac("fusion")[0] == dc.FUSION_DAILY_LOSS_FRAC == 0.05


def test_a_declared_tighter_daily_limit_tightens_and_a_looser_one_never_loosens() -> None:
    assert ab.trip_frac("ftmo", 0.03)[0] == pytest.approx(0.03)         # FTMO 1-Step
    assert ab.trip_frac("ftmo", 0.10)[0] == pytest.approx(0.05)
    for junk in (None, "x", float("nan"), -1.0, 0.0):
        assert ab.trip_frac("ftmo", junk)[0] == pytest.approx(0.05)


# ------------------------------------------------------------------ the daily-loss latch
def test_trips_at_the_threshold_and_latches_for_the_rest_of_the_day(tmp_path) -> None:
    p = tmp_path / "s.json"
    assert ab.account_latch("e8", 100_000.0, "2026-11-11", path=p).state == "OK"
    b = ab.account_latch("e8", 98_500.0, "2026-11-11", path=p)          # exactly -1.5%
    assert b.refuse and b.state == "TRIPPED" and "rest of 2026-11-11" in b.why
    # Latched: a bounce back does not re-open the day.
    b = ab.account_latch("e8", 101_000.0, "2026-11-11", path=p)
    assert b.refuse and b.state == "STOOD_DOWN"
    st = json.loads(p.read_text("utf-8"))["e8"]
    assert st["day_start_equity"] == {"date": "2026-11-11", "equity": 100_000.0}
    assert st["daily_loss_stood_down"] == "2026-11-11"


def test_no_trip_just_above_the_threshold(tmp_path) -> None:
    p = tmp_path / "s.json"
    ab.account_latch("ftmo", 100_000.0, "2026-11-11", path=p)
    b = ab.account_latch("ftmo", 95_000.01, "2026-11-11", path=p)       # floor 95,000
    assert not b.refuse and b.state == "OK"
    assert ab.account_latch("ftmo", 95_000.0, "2026-11-11", path=p).state == "TRIPPED"


def test_the_broker_day_resets_the_anchor_and_the_latch(tmp_path) -> None:
    p = tmp_path / "s.json"
    ab.account_latch("e8", 100_000.0, "2026-11-11", path=p)
    assert ab.account_latch("e8", 90_000.0, "2026-11-11", path=p).refuse
    b = ab.account_latch("e8", 90_000.0, "2026-11-12", path=p)
    assert not b.refuse and b.state == "OK"
    assert json.loads(p.read_text("utf-8"))["e8"]["day_start_equity"]["equity"] == 90_000.0


def test_accounts_keep_separate_anchors_in_one_file(tmp_path) -> None:
    p = tmp_path / "s.json"
    ab.account_latch("e8", 100_000.0, "2026-11-11", path=p)
    ab.account_latch("ftmo", 200_000.0, "2026-11-11", path=p)
    assert ab.account_latch("e8", 98_000.0, "2026-11-11", path=p).refuse
    assert not ab.account_latch("ftmo", 199_000.0, "2026-11-11", path=p).refuse


@pytest.mark.parametrize("equity", [None, "x", float("nan"), 0.0, -5.0])
def test_an_unreadable_equity_fails_closed_without_anchoring(tmp_path, equity) -> None:
    p = tmp_path / "s.json"
    b = ab.account_latch("e8", equity, "2026-11-11", path=p)
    assert b.refuse and b.state == "UNMEASURED" and "unreadable" in b.why
    assert not p.exists()


def test_an_unreadable_state_file_fails_closed_and_heals(tmp_path) -> None:
    p = tmp_path / "s.json"
    p.write_text("{torn", "utf-8")
    b = ab.account_latch("e8", 100_000.0, "2026-11-11", path=p)
    assert b.refuse and b.state == "UNMEASURED" and "unreadable" in b.why
    assert ab.account_latch("e8", 100_000.0, "2026-11-11", path=p).state == "OK"


# ------------------------------------------------------------------ Fusion unchanged
def _fusion_before(st: dict, equity: object, day_key: str) -> tuple[bool, str]:
    """`decision_core.fusion_daily_loss` as it stood on LIVE before the generalisation."""
    try:
        eq = float(equity)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        eq = float("nan")
    if not (math.isfinite(eq) and eq > 0.0):
        return True, "fusion daily-loss rail: equity unreadable; no new risk this pass"
    anchor = st.get("day_start_equity")
    if not (isinstance(anchor, dict) and anchor.get("date") == day_key
            and isinstance(anchor.get("equity"), (int, float))
            and not isinstance(anchor.get("equity"), bool) and float(anchor["equity"]) > 0.0):
        anchor = {"date": day_key, "equity": round(eq, 2)}
        st["day_start_equity"] = anchor
    start = float(anchor["equity"])
    floor = start * (1.0 - 0.05)
    if st.get("daily_loss_stood_down") == day_key:
        return True, (f"fusion daily-loss rail: stood down for {day_key} (start {start:.2f}, "
                      f"floor {floor:.2f}, equity {eq:.2f})")
    if eq <= floor:
        st["daily_loss_stood_down"] = day_key
        return True, (f"fusion daily-loss rail: equity {eq:.2f} reached {floor:.2f} "
                      f"(-{0.05:.0%} of the day's start {start:.2f}); no new "
                      f"risk for the rest of {day_key}")
    return False, (f"fusion daily-loss rail: equity {eq:.2f} above the {floor:.2f} floor "
                   f"(start {start:.2f})")


def test_the_fusion_rail_answers_exactly_as_before() -> None:
    path = [(500.0, "2026-10-20"), (476.0, "2026-10-20"), (475.0, "2026-10-20"),
            (520.0, "2026-10-20"), (None, "2026-10-20"), (430.0, "2026-10-21"),
            ("x", "2026-10-21"), (408.5, "2026-10-21"), (999.0, "2026-10-22")]
    new_st: dict = {}
    old_st: dict = {}
    for eq, day in path:
        assert dc.fusion_daily_loss(new_st, eq, day) == _fusion_before(old_st, eq, day)
        assert new_st == old_st


def test_the_fusion_gateway_keeps_its_one_cancel_and_the_breakers_add_none() -> None:
    gw = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    main = gw[gw.index("\ndef main() -> None:"):]
    i, j = main.index("fusion_daily_loss(st"), main.index("_ab.connection_breaker(")
    assert main[i:j].count("cancel_pending(") == 1          # the Fusion rail's own, unchanged
    block = main[j:main.index("A PRINCIPAL WITHDRAWAL IS NOT A LOSS")]
    assert "NEW_RISK_OK = False" in block and "_ab.bill(_ab.RAIL_DISCONNECT" in block
    for verb in ("cancel", "close", "order_send", "TRADE_ACTION"):
        assert verb not in block


def test_the_breaker_module_makes_no_venue_call_and_changes_no_order() -> None:
    tree = ast.parse((_DESK / "mt5desk" / "account_breakers.py").read_text("utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imports = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in n.names}
    assert "mt5" not in names and "MetaTrader5" not in imports
    assert not ({"order_send", "cancel", "close", "close_all", "modify_stop", "place"} & attrs)


# ------------------------------------------------------------------ the disconnect breaker
def test_a_disconnected_terminal_refuses(real_limit) -> None:
    b = ab.connection_breaker(tick_age=1.0, terminal=SimpleNamespace(connected=False,
                                                                     trade_allowed=True))
    assert b.refuse and b.state == "DISCONNECTED"


def test_trading_switched_off_refuses(real_limit) -> None:
    b = ab.connection_breaker(tick_age=1.0, terminal=SimpleNamespace(connected=True,
                                                                     trade_allowed=False))
    assert b.refuse and b.state == "TRADE_DISABLED"
    b = ab.connection_breaker(tick_age=1.0, account=SimpleNamespace(trade_allowed=False))
    assert b.refuse and b.state == "TRADE_DISABLED"


def test_a_stale_quote_refuses_and_a_fresh_one_passes(real_limit) -> None:
    live = SimpleNamespace(connected=True, trade_allowed=True)
    assert not ab.connection_breaker(tick_age=1799.0, terminal=live, account=SimpleNamespace(
        trade_allowed=True)).refuse
    b = ab.connection_breaker(tick_age=1801.0, terminal=live)
    assert b.refuse and b.state == "STALE_QUOTE" and "1801s old" in b.why


@pytest.mark.parametrize("kw", [
    {"tick_age": None},
    {"tick_age": float("nan")},
    {"tick_age": -3600.0},                                   # stamped an hour in the future
    {"tick_age": 1.0, "terminal": None},                     # the terminal did not answer
    {"tick_age": 1.0, "account": None},                      # the account did not answer
])
def test_an_unreadable_connection_state_fails_closed(real_limit, kw) -> None:
    b = ab.connection_breaker(**kw)
    assert b.refuse and b.state == "UNMEASURED"


def test_tick_age_reads_the_broker_clock() -> None:
    from mt5desk.broker_clock import broker_epoch_to_utc
    stamp = int(datetime(2026, 11, 11, 5, 0, tzinfo=UTC).timestamp())      # broker 05:00
    at = broker_epoch_to_utc(stamp).to_pydatetime()                         # = 22:00Z prev day
    assert ab.tick_age_s(stamp, at + timedelta(seconds=30)) == pytest.approx(30.0)
    assert ab.tick_age_s(None, NOW) is None and ab.tick_age_s(0, NOW) is None


# ------------------------------------------------------------------ the ledger
def test_a_trip_and_a_refusal_each_write_one_named_line() -> None:
    trip = ab.Breaker(True, "TRIPPED", "e8 latch tripped")
    down = ab.Breaker(True, "STOOD_DOWN", "e8 latch stood down")
    for lane in ("e8_gold", "e8_executor"):
        ab.bill(ab.RAIL_DAILY_LOSS, trip, account="e8", lane=lane, day="2026-11-11")
    for _ in range(3):
        ab.bill(ab.RAIL_DAILY_LOSS, down, account="e8", lane="e8_gold", day="2026-11-11")
    assert not ab.bill(ab.RAIL_DAILY_LOSS, ab.Breaker(False, "OK", "fine"), account="e8",
                       lane="e8_gold", day="2026-11-11")
    rows = _lines()
    assert [(r["rail"], r["state"]) for r in rows] == [
        ("account_daily_loss", "TRIPPED"), ("account_daily_loss", "STOOD_DOWN")]
    assert rows[0]["account"] == "e8" and rows[0]["why"] == "e8 latch tripped"


def test_a_disconnect_is_billed_per_lane_state_and_hour() -> None:
    b = ab.Breaker(True, "STALE_QUOTE", "stale")
    for at in (NOW, NOW + timedelta(minutes=5), NOW + timedelta(hours=1)):
        ab.bill(ab.RAIL_DISCONNECT, b, account="ftmo", lane="ftmo_executor", day="d", now=at)
    assert len([r for r in _lines() if r["rail"] == "account_disconnect"]) == 2


def test_both_rails_are_registered_and_published() -> None:
    from research import missed_growth as mg
    for rail in (ab.RAIL_DAILY_LOSS, ab.RAIL_DISCONNECT):
        assert rail in fusion_rails.RAILS and rail in mg.FUSION_RAIL_NAMES


# ------------------------------------------------------------------ every lane runs both
_LANES = {
    "fusion": ("mt5desk/gateway.py", "fusion_daily_loss(st", "_ab.connection_breaker("),
    "e8 gold": ("prop/e8_gold.py", "_ab.account_latch(\"e8\"", "_ab.connection_breaker("),
    "e8 executor": ("prop/e8_executor.py", "_ab.account_latch(\"e8\"", None),
    "ftmo executor": ("prop/ftmo_executor.py", "_ab.account_latch(", "_ab.connection_breaker("),
    "ftmo follower": ("prop/ftmo_follower.py", "_ab.account_latch(", "_ab.connection_breaker("),
}


@pytest.mark.parametrize("lane", sorted(_LANES))
def test_every_lane_runs_the_breakers_and_bills_them(lane) -> None:
    rel, latch, conn = _LANES[lane]
    src = (_DESK / rel).read_text("utf-8")
    assert latch in src
    if conn:
        assert conn in src
    assert "_ab.bill(" in src or '_rails.line("fusion_daily_loss"' in src


# ------------------------------------------------------------------ a lane, end to end
from test_ftmo_executor import NOW as FX_NOW  # noqa: E402
from test_ftmo_executor import fx, world  # noqa: E402,F401


def test_ftmo_executor_refuses_a_stale_quote_and_bills_it(world, monkeypatch) -> None:  # noqa: F811
    # The real 1800 s bar sits past the executor's own 300 s clock skew check, so the lane is
    # driven into the breaker with a bar inside it: 200 s without a tick, past a 120 s bar.
    monkeypatch.setattr(ab, "QUOTE_MAX_AGE_S", 120.0)
    world.mt5.tick_epoch -= 200
    doc = fx.run(world.mt5, armed=True, now=FX_NOW)
    assert doc["status"] == "ACCOUNT_DISCONNECT" and world.mt5.sent == []
    assert [r["state"] for r in _lines() if r["rail"] == "account_disconnect"] == ["STALE_QUOTE"]


def test_ftmo_executor_trips_the_latch_sends_nothing_new_and_touches_nothing_open(
        world, real_limit) -> None:  # noqa: F811
    fx.run(world.mt5, armed=False, now=FX_NOW)                     # anchors the CET day
    world.mt5.acc = SimpleNamespace(equity=94_900.0, balance=100_000.0)   # -5.1% floating
    resting = SimpleNamespace(ticket=1, symbol="EURUSD", type=2, magic=0, sl=1.0, price_open=1.1,
                              volume_current=0.1, volume_initial=0.1, tp=0.0)
    world.mt5.orders.append(resting)
    doc = fx.run(world.mt5, armed=True, now=FX_NOW + timedelta(minutes=5))
    assert doc["status"] == "ACCOUNT_DAILY_LOSS", doc
    assert world.mt5.sent == [] and world.mt5.orders == [resting]
    rows = [r for r in _lines() if r["rail"] == "account_daily_loss"]
    assert [r["state"] for r in rows] == ["TRIPPED"] and rows[0]["account"] == "ftmo"


# ------------------------------------------------------------------ audit HOLD f39234fbf
def test_the_venue_anchor_wins_over_a_first_read_taken_after_a_loss(tmp_path) -> None:
    path = tmp_path / "s.json"
    # First read of the day is already 4% down; FTMO's midnight balance was 100k.
    late = ab.account_latch("ftmo", 96_000.0, "2026-11-11", path=path)
    assert not late.refuse
    b = ab.account_latch("ftmo", 94_900.0, "2026-11-11", path=path, anchor=100_000.0)
    assert b.state == "TRIPPED", b
    # Without the venue anchor the first read (96k) would have held the floor at 91.2k.
    assert json.loads(path.read_text())["ftmo"]["day_start_equity"]["source"] == "venue"


def test_a_terminal_with_no_connected_flag_is_unmeasured() -> None:
    b = ab.connection_breaker(tick_age=1.0, terminal=True)
    assert b.refuse and b.state == "UNMEASURED"
    b = ab.connection_breaker(tick_age=1.0, terminal=SimpleNamespace(trade_allowed=True))
    assert b.refuse and b.state == "UNMEASURED"
    ok = ab.connection_breaker(tick_age=1.0, terminal=SimpleNamespace(connected=True,
                                                                       trade_allowed=True))
    assert not ok.refuse


def test_every_line_is_priced_for_missed_growth() -> None:
    trip = ab.Breaker(True, "TRIPPED", "t")
    assert ab.bill(ab.RAIL_DAILY_LOSS, trip, account="ftmo", lane="ftmo_executor", day="d1")
    cb = ab.Breaker(True, "STALE_QUOTE", "s")
    assert ab.bill(ab.RAIL_DISCONNECT, cb, account="e8", lane="e8_gold", day="d1",
                   risk_frac=0.004, lot=0.2)
    rows = {r["rail"]: r for r in _lines()}
    dl, dc_ = rows["account_daily_loss"], rows["account_disconnect"]
    assert dl["risk_frac"] == pytest.approx(ap.PROFILES["ftmo-2step"].risk_frac)
    assert dl["forgone_basis"] == "one_entry_at_profile_risk_frac" and dl["lot"] is None
    assert dc_["risk_frac"] == 0.004 and dc_["lot"] == 0.2
    assert dc_["forgone_basis"] == "sized_order"
