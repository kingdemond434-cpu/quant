"""THE FTMO SLEEVE EXECUTOR (prop/ftmo_executor.py): the allocator's non-gold sleeves, sent.

A stubbed MT5 terminal and a stub family; the doors (replication, Tier S, the cross-account books)
are replaced by stubs so each test moves one of them.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import ftmo_executor as fx  # noqa: E402
from prop.e8_guard import server_offset_hours  # noqa: E402

NOW = datetime(2026, 10, 29, 2, 3, tzinfo=UTC)
SERVER = NOW + timedelta(hours=server_offset_hours(NOW))   # the broker clock, NY+7
BAR = pd.Timestamp(SERVER.replace(minute=0) - timedelta(hours=1)).tz_convert(UTC)
KEY = "AUDNZD_overnight_gap_decay_asia"
SPEC = {"key": "external.AUDNZD.overnight_gap_decay.p=1", "symbol": "AUDNZD",
        "family": "overnight_gap_decay", "selector": "asia", "fingerprint": "fp",
        "params": {"timeframe": "H1"}}


class _MT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    ORDER_TIME_GTC, ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 0, 1, 2
    TIMEFRAME_H1 = 16385

    def __init__(self) -> None:
        self.acc = SimpleNamespace(equity=100_000.0, balance=100_000.0)
        self.positions: list[SimpleNamespace] = []
        self.orders: list[SimpleNamespace] = []
        self.sent: list[dict] = []
        self.tick_epoch = SERVER.timestamp()
        self.retcode = 10009
        self.rates_shift_h = 0
        self.point = 0.00001

    def account_info(self) -> SimpleNamespace:
        return self.acc

    def symbol_select(self, sym: str, on: bool) -> bool:
        return True

    def symbol_info_tick(self, sym: str) -> SimpleNamespace:
        return SimpleNamespace(time=self.tick_epoch, bid=1.1000, ask=1.1001)

    def symbol_info(self, sym: str) -> SimpleNamespace:
        return SimpleNamespace(volume_min=0.01, volume_step=0.01, volume_max=50.0,
                               trade_contract_size=100_000.0, point=self.point, filling_mode=2)

    def order_calc_profit(self, typ: int, sym: str, vol: float, a: float, b: float) -> float:
        return (b - a if typ == 0 else a - b) * 100_000.0 * vol * 0.6   # NZD -> USD

    def positions_get(self, symbol: str | None = None) -> list:
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def orders_get(self, symbol: str | None = None) -> list:
        return [o for o in self.orders if symbol is None or o.symbol == symbol]

    def history_orders_get(self, a: datetime, b: datetime) -> list:
        return []

    def history_deals_get(self, a: datetime, b: datetime) -> list:
        return []

    def copy_rates_from_pos(self, sym: str, tf: int, start: int, n: int) -> list:
        t0 = int(SERVER.replace(minute=0).timestamp()) - (200 + self.rates_shift_h) * 3600
        return [{"time": t0 + 3600 * i, "open": 1.1, "high": 1.101, "low": 1.099,
                 "close": 1.1, "tick_volume": 1} for i in range(201)]

    def order_send(self, req: dict) -> SimpleNamespace:
        self.sent.append(req)
        if req.get("position") is None:
            self.positions.append(SimpleNamespace(
                ticket=7000 + len(self.sent), symbol=req["symbol"], type=req["type"],
                magic=req["magic"], volume=req["volume"], price_open=req["price"],
                sl=req["sl"], comment=req["comment"], time=int(self.tick_epoch)))
        else:
            self.positions = [p for p in self.positions if p.ticket != req["position"]]
        return SimpleNamespace(retcode=self.retcode, order=7000 + len(self.sent))


def _sig(side: int = 1) -> SimpleNamespace:
    return SimpleNamespace(time=BAR, side=side, stop=1.0950 if side > 0 else 1.1050,
                           target=1.1100 if side > 0 else 1.0900, ttl_bars=6)


@pytest.fixture
def world(monkeypatch, tmp_path) -> SimpleNamespace:
    import admission_integrity
    from mt5desk import cross_account as xa
    from mt5desk import decision_core, families, family_call, kelly_sizing, order_door
    from prop import e8_executor

    from libs.ops import new_risk_hold
    from libs.tiers import promotion_authority
    for name in ("STATE", "OUT", "INTENTS", "LOG", "ARMED_MARKER", "ALLOCATOR"):
        monkeypatch.setattr(fx, name, tmp_path / name.lower())
    cert = tmp_path / "CERT_BOOK_LIVE.json"
    cert.write_text(json.dumps({"enabled": True, "excluded": {},
                                "ftmo": {"gold_asia": 0.002, KEY: 0.003}}))
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", cert)
    fx.ALLOCATOR.write_text(json.dumps({"generated_at": NOW.isoformat(), "deployable": True,
                                        "status": "OK", "specs": {KEY: SPEC},
                                        "executable": {"gold_asia": 0.002, KEY: 0.003}}))
    fx.ARMED_MARKER.write_text("")
    monkeypatch.setattr(fx._fw, "bound_account", lambda mt5: (
        "sha256:" + "a" * 16, {"initial_balance": 100_000.0, "daily_loss_frac": 0.05}, "ok"))
    monkeypatch.setattr(fx._fw, "day_start_balance", lambda mt5, b, s, n, **k: 100_000.0)
    monkeypatch.setattr(fx._fw, "near_market_close", lambda now: False)
    monkeypatch.setattr(order_door, "guard", lambda mt5, caller="", log=None: mt5)
    monkeypatch.setattr(new_risk_hold, "reason", lambda root=None: None)
    gate = SimpleNamespace(alarm={}, replication=lambda k, f: ("REPLICATED", "ok"))
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load", classmethod(lambda c: gate))
    monkeypatch.setattr(admission_integrity, "REPLICATED", "REPLICATED")
    monkeypatch.setattr(promotion_authority, "block", lambda k: None)
    sigs = {"list": [_sig()]}
    monkeypatch.setattr(families, "get_family_func", lambda f: (lambda d, **k: sigs["list"]))
    monkeypatch.setattr(family_call, "certified_session_filter", lambda s, sl: s)
    monkeypatch.setattr(family_call, "signal_reference_price", lambda f, b, g: None)
    monkeypatch.setattr(decision_core, "family_bracket", lambda g, s, b, a, c: (
        a, g.stop, g.target, abs(a - g.stop), "certified", 0.0, "certified"))
    monkeypatch.setattr(e8_executor, "_call_params", lambda s, sym, bars: {})
    books: dict[str, Any] = {"fusion": ({}, "ok"), "e8": ({}, "ok")}
    monkeypatch.setattr(xa, "read_book", lambda a, now=None, **k: books[a])
    return SimpleNamespace(mt5=_MT5(), books=books, sigs=sigs, cert=cert)


def _rows() -> list[dict]:
    return [json.loads(x) for x in fx.INTENTS.read_text().splitlines()]


def test_a_funded_sleeve_with_a_signal_is_sent_with_its_stop_and_target(world) -> None:
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert doc["status"] == "OK", doc
    (req,) = world.mt5.sent
    assert req["symbol"] == "AUDNZD" and req["magic"] == fx.MAGIC
    assert req["sl"] == 1.0950 and req["tp"] == 1.1100
    # 0.003 x 100k = $300 at the 51-pip stop from the ask ($306/lot), floored -> 0.98 lot
    assert req["volume"] == pytest.approx(0.98)
    assert _rows()[-1]["status"] == "SENT"


def test_the_same_bar_is_never_sent_twice(world) -> None:
    fx.run(world.mt5, armed=True, now=NOW)
    world.mt5.positions.clear()                                  # even after the position closed
    doc = fx.run(world.mt5, armed=True, now=NOW + timedelta(minutes=5))
    assert len(world.mt5.sent) == 1
    assert doc["sleeves"][0]["status"] == "ALREADY_TRADED"


def test_standby_sends_nothing_and_says_what_it_would(world) -> None:
    doc = fx.run(world.mt5, armed=False, now=NOW)
    assert world.mt5.sent == []
    assert doc["sleeves"][0]["status"] == "WOULD_SEND"


def test_an_opposite_side_on_e8_blocks_the_order_and_bills_it(world) -> None:
    world.books["e8"] = ({"AUDNZD": {"long": False, "short": True}}, "ok")
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == []
    row = doc["sleeves"][0]
    assert row["status"] == "RAIL_BLOCKED" and row["rail"] == "cross_account_opposite"
    assert row["missed_growth_risk_usd"] == pytest.approx(0.98 * 306.0)


def test_an_unreadable_fusion_book_fails_closed(world) -> None:
    world.books["fusion"] = (None, "absent")
    fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == []
    assert _rows()[-1]["rail"] == "cross_account_opposite"


def test_the_daily_loss_rail_counts_the_whole_book(world) -> None:
    # $4,800 already lost today against a $5,000 daily limit: a $300 trade would cross it
    world.mt5.acc = SimpleNamespace(equity=95_200.0, balance=95_200.0)
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == []
    assert doc["sleeves"][0]["rail"] == "ftmo_loss_guard"


def test_a_position_without_a_stop_refuses_new_risk(world) -> None:
    world.mt5.positions.append(SimpleNamespace(ticket=1, symbol="EURUSD", type=0, magic=0,
                                               volume=1.0, price_open=1.1, sl=0.0))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == []
    assert doc["sleeves"][0]["rail"] == "ftmo_loss_guard"


@pytest.mark.parametrize("change", ["stale", "undeployable", "no_spec", "void_block"])
def test_no_fresh_deployable_book_trades_nothing(world, change: str) -> None:
    alloc = json.loads(fx.ALLOCATOR.read_text())
    if change == "stale":
        alloc["generated_at"] = (NOW - timedelta(hours=4)).isoformat()
    elif change == "undeployable":
        alloc["deployable"] = False
    elif change == "no_spec":
        alloc["specs"] = {}
    fx.ALLOCATOR.write_text(json.dumps(alloc))
    if change == "void_block":
        world.cert.write_text(json.dumps({"enabled": True, "ftmo": {KEY: "x"}}))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == [] and doc["status"] == "NO_BOOK"


def test_gold_is_never_this_lanes(world) -> None:
    spec = dict(SPEC, symbol="XAUUSD")
    sleeves, _ = fx.book_sleeves({"generated_at": NOW.isoformat(), "deployable": True,
                                  "specs": {"XAUUSD_x_asia": spec}},
                                 {"XAUUSD_x_asia": 0.003}, NOW)
    assert sleeves == []


def test_a_server_off_the_broker_clock_reads_no_signal(world) -> None:
    world.mt5.tick_epoch = NOW.timestamp()                     # a UTC server
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert doc["status"] == "CLOCK_MISMATCH" and world.mt5.sent == []


def test_a_sleeve_below_the_minimum_lot_is_billed_not_lifted(world) -> None:
    world.cert.write_text(json.dumps({"enabled": True, "excluded": {}, "ftmo": {KEY: 0.00001}}))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    row = doc["sleeves"][0]
    assert world.mt5.sent == [] and row["rail"] == "venue_min_lot"
    assert row["missed_growth_risk_usd"] == pytest.approx(1.0)


def test_an_open_position_is_closed_when_another_account_takes_the_other_side(world) -> None:
    fx.run(world.mt5, armed=True, now=NOW)
    world.books["fusion"] = ({"AUDNZD": {"long": False, "short": True}}, "ok")
    doc = fx.run(world.mt5, armed=True, now=NOW + timedelta(minutes=5))
    closes = [a for a in doc["actions"] if a["act"] == "close"]
    assert closes and closes[0]["ok"] and world.mt5.positions == []
    assert doc["alerts"]


def test_the_certified_time_exit_closes_the_position(world) -> None:
    fx.run(world.mt5, armed=True, now=NOW)
    world.mt5.tick_epoch = SERVER.timestamp() + 8 * 3600       # past bar + (6 + 1) hours
    doc = fx.run(world.mt5, armed=True, now=NOW + timedelta(hours=8))
    assert any(a["act"] == "close" and "time exit" in a["why"] for a in doc["actions"])


def test_the_allocator_lays_non_gold_sleeves_into_the_ftmo_block_and_zeroes_dropped_ones(
        tmp_path: Path) -> None:
    import prop_challenge_allocator as pca
    armed = tmp_path / "ARMED"
    armed.touch()
    principal = tmp_path / "P.json"
    principal.write_text(json.dumps({"gold_asia": 0.009}))
    book = tmp_path / "CERT_BOOK_LIVE.json"
    book.write_text(json.dumps({"enabled": True, "ftmo": {"gold_asia": 0.002,
                                                          "OLD_x_asia": 0.004}}))
    doc = {"deployable": True, "executable": {"gold_asia": 0.002, KEY: 0.003},
           "generated_at": "t", "account": {"phase": "phase1", "status": "MEASURED"}}
    assert pca.apply_book(doc, book, armed, principal)["applied"] is True
    assert json.loads(book.read_text())["ftmo"] == {"gold_asia": 0.002, KEY: 0.003,
                                                    "OLD_x_asia": 0.0}


def test_the_allocator_marks_a_non_gold_spec_executable_and_gold_windows_not() -> None:
    import prop_challenge_allocator as pca
    specs = {KEY: SPEC, "XAUUSD_x_london": dict(SPEC, symbol="XAUUSD")}
    assert pca.executor_runs(KEY, specs)
    assert pca.executor_runs("gold_asia", specs)
    assert not pca.executor_runs("XAUUSD_x_london", specs)
    assert not pca.executor_runs("EURUSD_y_asia", specs)


def test_every_executor_refusal_reaches_the_missed_growth_bill(world, monkeypatch) -> None:
    import missed_growth as mg
    world.books["e8"] = ({"AUDNZD": {"long": False, "short": True}}, "ok")
    fx.run(world.mt5, armed=True, now=NOW)
    monkeypatch.setattr(mg, "FTMO_EXEC_INTENTS", Path(fx.INTENTS))
    line = mg.published_ftmo_executor_lines()["rails"]["cross_account_opposite"]
    assert line["n"] == 1 and line["undeployed_risk_usd"] == pytest.approx(0.98 * 306.0)
    assert line["sleeves"] == [KEY]


# ============================================================== the audit's fixes (2026-10-29)

def _alloc(**kw: Any) -> None:
    alloc = json.loads(fx.ALLOCATOR.read_text())
    alloc.update(kw)
    fx.ALLOCATOR.write_text(json.dumps(alloc))


def test_the_smaller_of_the_block_and_this_passs_solve_is_traded(world) -> None:
    """MF1: a block an unarmed or refused apply left behind never outsizes this pass's solve."""
    _alloc(executable={"gold_asia": 0.002, KEY: 0.001})
    fx.run(world.mt5, armed=True, now=NOW)
    (req,) = world.mt5.sent
    assert req["volume"] == pytest.approx(0.32)              # $100 at $306/lot


def test_a_key_this_pass_did_not_solve_is_not_traded(world) -> None:
    _alloc(executable={"gold_asia": 0.002})
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == [] and doc["status"] == "NO_BOOK"


def test_a_feed_that_stopped_reads_no_signal_and_is_billed(world) -> None:
    """MF2: the last closed bar must be the one before the bar forming on the server's clock."""
    world.mt5.rates_shift_h = 2
    world.sigs["list"] = [SimpleNamespace(**dict(vars(_sig()), time=BAR - pd.Timedelta(hours=2)))]
    doc = fx.run(world.mt5, armed=True, now=NOW)
    row = doc["sleeves"][0]
    assert world.mt5.sent == [] and row["status"] == "STALE_BARS"
    assert row["rail"] == "ftmo_stale_bars"


def test_a_partial_fill_is_a_live_position(world) -> None:
    """MF3: 10010 is a partial fill: counted SENT, so the bar is spent and the position managed."""
    world.mt5.retcode = 10010
    fx.run(world.mt5, armed=True, now=NOW)
    assert _rows()[-1]["status"] == "SENT"


def test_the_time_exit_is_read_off_the_position_and_survives_a_lost_state(world) -> None:
    """MF3: the hold rides in the order comment; the state file holds nothing the exit needs."""
    fx.run(world.mt5, armed=True, now=NOW)
    (pos,) = world.mt5.positions
    assert pos.comment.startswith("FX6H1|")
    assert fx.exit_epoch(pos) == pytest.approx(pos.time + 6 * 3600)
    fx.STATE.unlink()
    world.mt5.tick_epoch = SERVER.timestamp() + 8 * 3600
    doc = fx.run(world.mt5, armed=True, now=NOW + timedelta(hours=8))
    assert any(a["act"] == "close" and "time exit" in a["why"] for a in doc["actions"])
    assert world.mt5.positions == []


def test_an_unmeasurable_lot_cap_refuses_and_is_billed(world) -> None:
    """MF5: the notional cap is never skipped because it cannot be read."""
    world.mt5.point = 0.0
    doc = fx.run(world.mt5, armed=True, now=NOW)
    row = doc["sleeves"][0]
    assert world.mt5.sent == [] and row["status"] == "RAIL_BLOCKED"
    assert row["rail"] == fx._fw.LOT_CAP_RAIL


def test_a_bracket_that_cannot_be_measured_is_billed_not_raised(world, monkeypatch) -> None:
    """S1: one sleeve's bracket error never ends the pass for the others."""
    from mt5desk import decision_core

    def boom(*a: Any) -> None:
        raise ValueError("no ATR")
    monkeypatch.setattr(decision_core, "family_bracket", boom)
    doc = fx.run(world.mt5, armed=True, now=NOW)
    row = doc["sleeves"][0]
    assert world.mt5.sent == [] and row["status"] == "UNMEASURED_BRACKET"


def test_the_same_side_on_another_firm_is_copied_by_zucks_override(world, monkeypatch) -> None:
    """zuck 2026-10-29 15:27Z, "extend copy override to all": a same-side holding on E8 is sent;
    the switch off restores the refusal; the opposite side is refused either way."""
    world.books["e8"] = ({"AUDNZD": {"long": True, "short": False}}, "ok")
    assert fx.ALLOW_CROSS_FIRM_COPY is True
    fx.run(world.mt5, armed=True, now=NOW)
    assert len(world.mt5.sent) == 1
    world.mt5.sent.clear()
    world.mt5.positions.clear()
    fx.STATE.unlink()
    monkeypatch.setattr(fx, "ALLOW_CROSS_FIRM_COPY", False)
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == [] and doc["sleeves"][0]["rail"] == "cross_firm_copy"


def test_a_rail_journalled_under_its_own_status_is_billed_too(world, monkeypatch) -> None:
    """S2: STALE_BARS, UNSIZEABLE at the venue minimum, ... are refusals by a rail as well."""
    import missed_growth as mg
    world.cert.write_text(json.dumps({"enabled": True, "excluded": {}, "ftmo": {KEY: 0.00001}}))
    _alloc(executable={KEY: 0.00001})
    fx.run(world.mt5, armed=True, now=NOW)
    monkeypatch.setattr(mg, "FTMO_EXEC_INTENTS", Path(fx.INTENTS))
    line = mg.published_ftmo_executor_lines()["rails"]["venue_min_lot"]
    assert line["n"] == 1 and line["statuses"] == ["UNSIZEABLE"]


def test_the_ftmo_book_is_published_for_the_other_lanes_fence(world, monkeypatch) -> None:
    """zuck 2026-10-29: no account goes opposite another. The pass publishes the FTMO book every
    pass, and the send holds its symbol in flight on it, so the gateway and the E8 executor
    (`cross_account.ftmo_block`) see it before the send returns."""
    from mt5desk import cross_account as xa
    seen: dict[str, Any] = {"published": [], "inflight": []}
    monkeypatch.setattr(xa, "publish_mt5", lambda mt5, *, source, account="fusion":
                        seen["published"].append(account))
    real_mark = xa.mark_inflight
    monkeypatch.setattr(xa, "mark_inflight", lambda account, symbol, **k: (
        seen["inflight"].append((account, symbol)), real_mark(account, symbol, **k))[1])
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert doc["book_published"] == "ok" and len(world.mt5.sent) == 1
    assert seen["published"] == ["ftmo", "ftmo"]               # the pass, then after the send
    assert seen["inflight"] == [("ftmo", "AUDNZD")]
    fx.ALLOCATOR.unlink()
    assert fx.run(world.mt5, armed=True, now=NOW)["status"] == "NO_BOOK"
    assert seen["published"][-1] == "ftmo"                     # published with nothing to trade


# ============================================================ the audit of 67121b8f7 (2026-10-29)

def test_a_rewritten_comment_falls_back_to_the_hold_kept_at_the_send(world) -> None:
    """MUST-FIX 1: the broker rewrote the comment; the exit kept by ticket still closes it."""
    fx.run(world.mt5, armed=True, now=NOW)
    (pos,) = world.mt5.positions
    pos.comment = "[tp 1.11]"
    assert fx.exit_epoch(pos) is None
    world.mt5.tick_epoch = SERVER.timestamp() + 8 * 3600
    doc = fx.run(world.mt5, armed=True, now=NOW + timedelta(hours=8))
    assert any(a["act"] == "close" and "time exit" in a["why"] for a in doc["actions"])


def test_a_position_with_no_readable_exit_is_never_silent(world) -> None:
    world.mt5.positions.append(SimpleNamespace(
        ticket=55, symbol="AUDNZD", type=0, magic=fx.MAGIC, volume=0.5, price_open=1.1,
        sl=1.09, comment="FX6H", time=int(SERVER.timestamp())))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert any("#55" in m for m in doc["manage_unmeasured"])
    assert any("#55" in a and "unmanaged" in a for a in doc["alerts"])


def test_the_forming_bar_is_read_off_the_frame(world) -> None:
    """SF1: after a gap (a weekend, a Monday D1) the last closed bar is not one bar before the
    forming one; the forming bar the feed carries decides, so the signal is not lost."""
    real = world.mt5.copy_rates_from_pos

    def gapped(sym: str, tf: int, start: int, n: int) -> list:
        rows = real(sym, tf, start, n)
        for r in rows[:-1]:
            r["time"] -= 48 * 3600                   # every closed bar two days earlier
        return rows
    world.mt5.copy_rates_from_pos = gapped
    world.sigs["list"] = [SimpleNamespace(**dict(vars(_sig()), time=BAR - pd.Timedelta(hours=48)))]
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert doc["sleeves"][0]["status"] == "SENT"


def test_a_trimmed_order_that_is_sent_is_billed(world, monkeypatch) -> None:
    """SF2: the part the lot cap trimmed is missed growth even though the order went."""
    import missed_growth as mg
    monkeypatch.setattr(fx._fw, "lot_cap", lambda *a, **k: (0.5, "declared max_lot 0.5"))
    fx.run(world.mt5, armed=True, now=NOW)
    (req,) = world.mt5.sent
    assert req["volume"] == pytest.approx(0.5)
    monkeypatch.setattr(mg, "FTMO_EXEC_INTENTS", Path(fx.INTENTS))
    line = mg.published_ftmo_executor_lines()["rails"][fx._fw.LOT_CAP_RAIL]
    assert line["statuses"] == ["SENT"] and line["undeployed_risk_usd"] == pytest.approx(
        0.48 * 306.0)


def test_a_vetoed_pass_leaves_a_row(world) -> None:
    """SF3: a pass vetoed as a whole still leaves Rule 1 a line."""
    world.mt5.tick_epoch = NOW.timestamp()                      # CLOCK_MISMATCH
    fx.run(world.mt5, armed=True, now=NOW)
    (row,) = [r for r in _rows() if r.get("rail") == fx.PASS_RAIL]
    assert row["status"] == "CLOCK_MISMATCH" and row["sleeve"] == KEY


def test_an_empty_block_is_not_billed_as_a_veto(world) -> None:
    world.cert.write_text(json.dumps({"enabled": True, "excluded": {},
                                      "ftmo": {"gold_asia": 0.002}}))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert doc["status"] == "NO_BOOK"
    assert not fx.INTENTS.exists() or not [r for r in _rows() if r.get("rail") == fx.PASS_RAIL]


def test_a_nan_solve_never_reads_as_no_limit(world) -> None:
    """SF5: min(block, nan) is the block; a NaN solve trades nothing."""
    fx.ALLOCATOR.write_text(fx.ALLOCATOR.read_text().replace(
        '"' + KEY + '": 0.003}', '"' + KEY + '": NaN}'))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert world.mt5.sent == [] and doc["status"] == "NO_BOOK"


def test_a_position_certified_with_no_time_exit_is_not_paged(world) -> None:
    """FX0: a hold of zero bars means stop and target only, by its certificate; not an alarm."""
    world.mt5.positions.append(SimpleNamespace(
        ticket=56, symbol="AUDNZD", type=0, magic=fx.MAGIC, volume=0.5, price_open=1.1,
        sl=1.09, comment="FX0H1|" + KEY, time=int(SERVER.timestamp())))
    doc = fx.run(world.mt5, armed=True, now=NOW)
    assert not [a for a in doc["alerts"] if "#56" in a]
    assert doc["manage_stop_target_only"] == ["AUDNZD #56"]
