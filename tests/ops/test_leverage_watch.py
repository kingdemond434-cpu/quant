"""CRO K3: the account's leverage is kept from pass to pass and every change is named."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import leverage_watch as lw

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _obs(p: Path, lev: float | None, t: datetime, sent: list) -> dict:
    return lw.observe(p, lev, now=t, emit=lambda kind, **f: sent.append((kind, f)))


def test_first_reading_is_measured_and_a_cut_is_named(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, 500, T0, sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert _obs(p, 500, T0 + timedelta(hours=1), sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert sent == []
    doc = _obs(p, 100, T0 + timedelta(hours=2), sent)
    row = doc["venues"]["fusion"]
    assert row["verdict"] == "CHANGED" and row["leverage"] == 100.0
    assert row["changes"][-1] == {"at": (T0 + timedelta(hours=2)).isoformat(),
                                  "from": 500.0, "to": 100.0, "direction": "CUT"}
    assert sent == [("ACCOUNT_LEVERAGE_CHANGED", {"producer": "research/financing_lab.py",
                                                  "priority": 2, "venue": "fusion",
                                                  "from": 500.0, "to": 100.0,
                                                  "direction": "CUT"})]
    assert json.loads(p.read_text())["venues"]["fusion"]["leverage"] == 100.0


def test_an_unreadable_pass_is_never_a_change_and_ages_to_stale(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, None, T0, sent)["venues"]["fusion"]["verdict"] == "UNMEASURED"
    _obs(p, 500, T0, sent)
    for lev in (None, 0, -5):
        row = _obs(p, lev, T0 + timedelta(hours=2), sent)["venues"]["fusion"]
        assert row["leverage"] == 500.0 and row["verdict"] == "MEASURED"
    row = _obs(p, None, T0 + timedelta(hours=lw.STALE_AFTER_H + 1), sent)["venues"]["fusion"]
    assert row["verdict"] == "STALE" and sent == []


def test_the_published_file_names_no_account(tmp_path: Path) -> None:
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    lw.observe(p, 500, now=T0, emit=lambda *a, **k: None)
    text = p.read_text()
    for banned in ("login", "server", "account_number"):
        assert banned not in text


def test_the_lab_wires_it() -> None:
    # The kind is not in libs.ops.events.KINDS yet: events.py is money path the replay cannot
    # measure, so the vocabulary row rides on its own; emit() still writes it (unknown_kind).
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "financing_lab.py").read_text(encoding="utf-8")
    assert "from libs.ops.leverage_watch import assess, observe" in src
    assert "feasibility=(assess(acct" in src
    assert 'live = acct.get("source") == "live terminal"' in src
    assert "symbol_margins(" in src


class _MT5:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1

    def __init__(self, margin: float) -> None:
        self.margin = margin

    def symbol_info(self, sym: str) -> object | None:
        return None if sym == "NOPE" else type("I", (), {"trade_contract_size": 100.0})()

    def symbol_info_tick(self, sym: str) -> object:
        return type("T", (), {"ask": 4000.0, "bid": 3999.0})()

    def order_calc_margin(self, otype: int, sym: str, vol: float, px: float) -> float:
        return self.margin


def test_a_per_symbol_cut_is_named_without_an_account_change(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    rows = lw.symbol_margins(_MT5(2000.0), ["xauusd", "NOPE", "XAUUSD"])
    assert list(rows) == ["XAUUSD"] and rows["XAUUSD"]["effective_leverage"] == 200.0
    lw.observe(p, 500, now=T0, emit=lambda k, **f: sent.append(k), symbols=rows)
    small = lw.symbol_margins(_MT5(2200.0), ["XAUUSD"])         # +10%: not a change
    assert lw.observe(p, 500, now=T0 + timedelta(hours=1), emit=lambda k, **f: sent.append(k),
                      symbols=small)["venues"]["fusion"]["verdict"] == "MEASURED"
    cut = lw.symbol_margins(_MT5(4000.0), ["XAUUSD"])           # margin doubled: a CUT
    row = lw.observe(p, 500, now=T0 + timedelta(hours=2), emit=lambda k, **f: sent.append(k),
                     symbols=cut)["venues"]["fusion"]
    assert row["verdict"] == "CHANGED" and row["symbol_changes"][-1]["direction"] == "CUT"
    assert row["symbols"]["XAUUSD"]["effective_leverage"] == 100.0
    assert sent == ["SYMBOL_MARGIN_CHANGED"]


# ------------------------------------------------ ported from #1145: venues and feasibility
FRI_PM = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)       # inside the weekend window
TUE = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)           # outside it
EQUITY = 123457.0                                        # a figure that must never be published


class _Acc:
    leverage, equity, margin, margin_so_call, margin_so_mode = 100.0, EQUITY, 0.0, 100.0, 0


class _Term(_MT5):
    """A terminal with an account, one held position and Market Watch visibility per symbol."""

    def __init__(self, margin: float, hidden: tuple[str, ...] = (), acc: object = _Acc) -> None:
        super().__init__(margin)
        self.hidden, self.acc = hidden, acc
        self.selected: list[str] = []

    def account_info(self) -> object:
        return self.acc

    def positions_get(self) -> tuple:
        return ()

    def symbol_info(self, sym: str) -> object | None:
        return type("I", (), {"trade_contract_size": 100.0,
                              "visible": sym not in self.hidden})()

    def symbol_select(self, sym: str, on: bool) -> bool:
        self.selected.append(sym)
        return True


def _intents(p: Path, rows: list[tuple[str, str, float]], at: datetime) -> Path:
    p.write_text("".join(json.dumps({"sleeve": s, "symbol": y, "side": "buy", "lot": lot,
                                     "time": (at - timedelta(days=1)).isoformat()}) + "\n"
                         for s, y, lot in rows), encoding="utf-8")
    return p


def _acct(**kw: object) -> dict:
    return {"equity": 100_000.0, "margin": 0.0, "margin_so_call": 100.0, "margin_so_mode": 0,
            **kw}


def test_feasibility_today_green_and_half_leverage_flagged_only_in_the_window(
        tmp_path: Path) -> None:
    # capacity 100k / 1.0 x 0.5 = 50k; two 7-lot orders at 2k per lot = 28k today, 56k at x2.
    ip = _intents(tmp_path / "i.jsonl", [("a", "XAUUSD", 7.0), ("b", "XAGUSD", 7.0),
                                         ("a", "XAUUSD", 1.0)], TUE)
    margins = {s: {"margin_per_lot_buy": 2000.0} for s in ("XAUUSD", "XAGUSD")}
    cal = tmp_path / "cal"
    out = lw.assess(_acct(), margins, "ftmo", now=TUE, intents=ip, calendars=cal)
    assert out["verdict"] == "GREEN" and out["today"]["book_use_share"] == 0.56
    assert out["half_leverage"]["book_fits"] is False and out["stress_flagged"] is False
    out = lw.assess(_acct(), margins, "ftmo", now=FRI_PM, intents=_intents(
        ip, [("a", "XAUUSD", 7.0), ("b", "XAGUSD", 7.0)], FRI_PM), calendars=cal)
    assert out["verdict"] == "AT_RISK" and out["stress_flagged"] is True
    assert out["today"]["orders"] == 2


def test_an_order_that_does_not_fit_alone_is_at_risk(tmp_path: Path) -> None:
    ip = _intents(tmp_path / "i.jsonl", [("a", "XAUUSD", 30.0)], TUE)
    out = lw.assess(_acct(), {"XAUUSD": {"margin_per_lot_buy": 2000.0}}, "ftmo", now=TUE,
                    intents=ip, calendars=tmp_path)
    assert out["verdict"] == "AT_RISK" and out["today"]["orders_infeasible_alone"] == ["a:XAUUSD"]


def test_missing_margin_call_level_and_zero_intents_are_unmeasured(tmp_path: Path) -> None:
    ip = _intents(tmp_path / "i.jsonl", [("a", "XAUUSD", 1.0)], TUE)
    m = {"XAUUSD": {"margin_per_lot_buy": 2000.0}}
    for call in (None, 0.0):                         # SF b: never a default of 100
        out = lw.assess(_acct(margin_so_call=call), m, "ftmo", now=TUE, intents=ip,
                        calendars=tmp_path)
        assert out["verdict"] == "UNMEASURED" and "margin_so_call" in out["why"]
    empty = tmp_path / "none.jsonl"                  # SF c: no order is not GREEN
    out = lw.assess(_acct(), m, "ftmo", now=TUE, intents=empty, calendars=tmp_path)
    assert out["verdict"] == "UNMEASURED" and "no order sized" in out["why"]
    old = _intents(tmp_path / "old.jsonl", [("a", "XAUUSD", 1.0)], TUE - timedelta(days=40))
    assert lw.assess(_acct(), m, "ftmo", now=TUE, intents=old,
                     calendars=tmp_path)["verdict"] == "UNMEASURED"


def test_only_high_impact_calendar_rows_open_the_window(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    soon = (TUE + timedelta(hours=6)).isoformat()
    (cal / "low.json").write_text(json.dumps({"events": [{"time": soon, "impact": "Low"},
                                                         {"time": soon}]}), encoding="utf-8")
    assert lw.in_cut_window(TUE, cal)["now"] is False           # SF f
    (cal / "fomc.json").write_text(json.dumps([{"time": soon, "impact": "High"}]),
                                   encoding="utf-8")
    w = lw.in_cut_window(TUE, cal)
    assert w["now"] is True and "high-impact" in w["why"]
    assert lw.in_cut_window(FRI_PM, tmp_path / "absent")["now"] is True


def test_ftmo_hook_publishes_ratios_only_and_selects_only_hidden_symbols(
        tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    ip = _intents(tmp_path / "ftmo.jsonl", [("a", "XAUUSD", 1.0)], TUE)
    monkeypatch.setitem(lw.INTENT_FILES, "ftmo", ip)
    term = _Term(2000.0, hidden=("XAGUSD",))
    line = lw.observe_mt5(term, "ftmo", path=p, now=TUE, emit=lambda *a, **k: None)
    assert "GREEN" in line and term.selected == ["XAGUSD"]       # SF e
    doc = json.loads(p.read_text())
    row = doc["venues"]["ftmo"]
    assert row["leverage"] == 100.0 and row["feasibility"]["verdict"] == "GREEN"
    assert doc["feasibility_by_venue"] == {"e8": "UNMEASURED", "ftmo": "GREEN",
                                           "fusion": "UNMEASURED"}
    text = p.read_text()                                         # SF a
    for banned in ("equity", "123457", "margin_per_lot", "2000", "login", "server"):
        assert banned not in text, banned
    assert lw.observe_mt5(object(), "ftmo", path=p).startswith("ftmo: leverage read failed")


def test_a_price_move_alone_is_not_a_symbol_change(tmp_path: Path) -> None:
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    a = {"XAUUSD": {"margin_per_lot_buy": 2000.0, "effective_leverage": 200.0}}
    b = {"XAUUSD": {"margin_per_lot_buy": 2400.0, "effective_leverage": 200.0}}   # price +20%
    lw.observe(p, 100, now=TUE, emit=lambda *a, **k: None, symbols=a)
    row = lw.observe(p, 100, now=TUE + timedelta(hours=1), emit=lambda *a, **k: None,
                     symbols=b)["venues"]["fusion"]
    assert row["verdict"] == "MEASURED" and row["symbol_changes"] == []


class _TLApi:
    def __init__(self, hang: float = 0.0) -> None:
        self.hang = hang

    def get_account_state(self) -> dict:
        import time as _t
        _t.sleep(self.hang)
        return {"leverage": 30.0, "marginUsed": 5555.0, "projectedBalance": EQUITY}


class _TLVenue:
    def __init__(self, hang: float = 0.0) -> None:
        self._api, self._by_key = _TLApi(hang), {"XAUUSD": 1, "EURUSD": 2}

    def details(self, sym: str) -> dict:
        return {"leverage": 20.0, "marginRate": 0.05, "lotSize": 100.0, "name": sym}


def test_e8_reads_keys_by_name_on_the_held_session_within_its_budget(tmp_path: Path) -> None:
    import time as _t
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    line = lw.observe_tradelocker(_TLVenue(), budget_s=5, path=p, now=TUE,
                                  emit=lambda *a, **k: None)
    row = json.loads(p.read_text())["venues"]["e8"]
    assert "UNMEASURED" in line and row["leverage"] == 30.0
    assert row["tradelocker_fields"]["account"] == ["leverage", "marginUsed"]
    assert row["tradelocker_fields"]["symbol"]["XAUUSD"] == ["leverage", "lotSize", "marginRate"]
    assert row["feasibility"]["verdict"] == "UNMEASURED"
    text = p.read_text()
    assert "5555" not in text and "123457" not in text and "0.05" not in text
    t0 = _t.monotonic()                                          # SF d
    line = lw.observe_tradelocker(_TLVenue(hang=3.0), budget_s=0.3, path=p, now=TUE,
                                  emit=lambda *a, **k: None)
    assert _t.monotonic() - t0 < 2.0 and "budget" in line


def test_the_ftmo_reader_wires_it_and_e8_book_does_not_yet() -> None:
    """Governance 2026-11-18 18:52Z: e8_book's main() is money path the replay cannot reach, so
    the E8 read waits for a replay scenario that runs it."""
    prop = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "prop"
    ftmo = (prop / "ftmo_venue_reader.py").read_text(encoding="utf-8")
    assert "observe_mt5(mt5, 'ftmo')" in ftmo
    book = (prop / "e8_book.py").read_text(encoding="utf-8")
    assert "leverage_watch" not in book
