"""E8 gold bracket guard v5: the must-fixes of the audit HOLD on v4 (4effc032d302 + 72c1c091).

1. The floor fit is net of COMMITTED risk, which counts a break-even winner's open profit.
2. Evidence rows on the rail skip, the in-sizing budget deferral and the rails exception, and the
   lot-ceiling fit runs before any R_RISK_BUDGET deferral.
3. ROOM_MARGIN_USD comes off step 2's room.
4. A measured slip p95 of 0 (pooled or per window) reads the 24.13-point floor.
5. leg_risk is re-derived after a venue-minimum lift; a lift that does not fit is not sent.
6. Both legs filling and both slipping fits the room (until the cross-account OCO lands).
7. Stop-exit rows (and the evidence) carry the HMAC account_key, or nothing.

Plus the scrub leaks of the evidence v5 note (subacc_, acc., accountNumber=). Every account id
here is fake.

The fixture is test_e8_gold_guard_and_open_risk's: the afternoon window is due at 17:30 with a
33.5-point stop and a 67-point target on a 100 oz contract.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_e8_gold_bracket_guard as bg  # noqa: E402
import test_e8_gold_guard_and_open_risk as h  # noqa: E402
from prop import e8_evidence as ev  # noqa: E402
from prop import e8_gold as g  # noqa: E402

#: A fake TradeLocker account id. Never a real one.
_FAKE_ID = 4818273
_FAKE_KEY = "sha256:0123456789abcdef"


@pytest.fixture(autouse=True)
def _unbind_the_pass() -> Any:
    """A test that binds an account (or its stamp) by hand leaves nothing bound for the next."""
    yield
    ev.bind_account(ev.UNMEASURED)


def _decisions(doc: dict[str, Any], window: str = "afternoon") -> list[dict[str, Any]]:
    return [d for d in doc["decisions"] if d["window"] == window]


def _locked_short(qty: float) -> dict[str, Any]:
    """A short opened at 4330 whose stop is ratcheted to 4310: not AT RISK, but at the 4300.4
    mark it can give back 9.6 points plus 24.13 points of stop slip, 3,373 USD a lot (v5.2)."""
    return {"id": 501, "tradableInstrumentId": 6102, "side": "sell", "qty": qty,
            "avgPrice": 4330.0, "stopLoss": 4310.0, "stopLossId": 0}


def _bracket_need(lots: dict[str, float], stop: float = 33.5, contract: float = 100.0) -> float:
    """Both legs to their stops plus both legs' default slip, in USD."""
    return float(sum(lot * contract * (stop + g.DEFAULT_SLIP_POINTS) for lot in lots.values()))


# ------------------------------------------------------------- 1. committed risk


def test_the_floor_fit_subtracts_a_break_even_winners_give_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 0.22-lot short opened at 4330 with its stop ratcheted to 4310 is not AT RISK (the
    one-at-a-time rule lets the afternoon window place), but the mark is 4300.4: 9.6 points x
    0.22 x 100 oz = 211.2 USD of open profit can go back, and its stop fills 24.13 points through
    (v5.2): 530.86 more. Committed 742.06; on a day down 700 the room is 1,800 - 742.06 - 100 =
    957.94.

    Re-cut on live: the book's 1.2% is capped by the r7.1 code ceiling to 0.6% = 595.8 USD, so
    the agreeing sell leg is 0.17 lots and needs 595.8 + 0.17 x 100 x 24.13 = 1,006 > 957.94
    (and 1.25 x (742.06 + 595.8) = 1,672 <= 1,700 passes the concurrent budget first), so
    L = 957.94 / 5,763 = 0.166 -> 0.16.
    """
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(99_300.0))
    bg._cert_book(tmp_path, 0.012)
    venue = bg._Venue(equity=99_300.0)
    venue._positions = [
        {
            "id": 501,
            "tradableInstrumentId": 6102,
            "side": "sell",
            "qty": 0.22,
            "avgPrice": 4330.0,
            "stopLoss": 4310.0,
            "stopLossId": 0,
        }
    ]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    (pos,) = doc["committed_risk"]["positions"]
    assert pos["at_risk"] is False and pos["stop_risk_usd"] == pytest.approx(211.2)
    assert pos["slip_usd"] == pytest.approx(530.86)
    assert venue.sent == [("sell", 0.16, 4290.0)]
    (cut,) = bg._shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["committed_usd"] == pytest.approx(742.06)
    assert cut["room_to_floor"] == pytest.approx(1800.0 - 742.06 - g.ROOM_MARGIN_USD)
    assert 742.06 + _bracket_need({"sell_stop": 0.16}) <= 1800.0 - g.ROOM_MARGIN_USD


# ------------------------------------------------------------- v5.2: committed slip, account-wide


@pytest.mark.parametrize("frac", [0.005, 0.0095])
def test_the_auditors_break_even_long_on_a_91k_day_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frac: float
) -> None:
    """The audit's probe (HOLD on 8fe4edce): a 0.5-lot break-even long on a 91k day. Day start
    91,000, equity 91,900: 1,900 to the static floor. The long (entry and stop 4288, mark 4300)
    gives back 600 at its stop and 1,206.5 more when the stop slips 24.13 points. v5 counted only
    the 600, fitted a new buy leg to 1,200 and could lose ~2,555-2,995 against 1,900. v5.2
    counts 1,806.5, leaves no room, and sends nothing."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(91_900.0, day_start=91_000.0))
    monkeypatch.setattr(g, "RISK_FRAC", frac)
    venue = bg._Venue(equity=91_900.0)
    venue._positions = [
        {
            "id": 601,
            "tradableInstrumentId": 6102,
            "side": "buy",
            "qty": 0.5,
            "avgPrice": 4288.0,
            "stopLoss": 4288.0,
            "stopLossId": 0,
        }
    ]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    (pos,) = doc["committed_risk"]["positions"]
    assert pos["at_risk"] is False
    assert pos["stop_risk_usd"] == pytest.approx(600.0)
    assert pos["slip_usd"] == pytest.approx(1206.5)
    assert venue.sent == [] and doc["placed"] == []
    room = float(doc["guard_decision"]["room_to_static_floor"])
    assert room == pytest.approx(1900.0)
    # What v5 would have risked: a leg fitted to the room net of the 600 only.
    v5_room = room - 600.0 - g.ROOM_MARGIN_USD
    assert 600.0 + 1206.5 + min(v5_room, _bracket_need({"buy_stop": 0.13})) > room
    (row,) = _decisions(doc)
    assert row["outcome"] in ("SKIPPED", "DEFERRED") and row["taken"] is False


def test_every_resting_leg_counts_with_its_slip() -> None:
    journal = [
        {
            "status": "SENT",
            "order_id": 1,
            "window": "asia",
            "price": 4310.0,
            "sl": 4276.5,
            "lot": 0.2,
            "at": "2026-10-15T04:00:00+00:00",
        },
        {
            "status": "SENT",
            "order_id": 2,
            "window": "asia",
            "price": 4290.0,
            "sl": 4323.5,
            "lot": 0.2,
            "at": "2026-10-15T04:00:00+00:00",
        },
    ]
    resting = [{"id": 1, "stopPrice": 4310.0}, {"id": 2, "stopPrice": 4290.0}]
    total, _detail = g.committed_risk(
        [],
        resting,
        journal,
        {"date": "2026-10-15"},
        bid=4300.0,
        ask=4300.4,
        contract_size=100.0,
        slip_points=24.13,
    )
    assert total == pytest.approx(2 * (33.5 + 24.13) * 0.2 * 100)


def test_a_foreign_xau_entry_order_counts_and_one_without_a_stop_refuses() -> None:
    foreign = {
        "id": 77,
        "tradableInstrumentId": 6102,
        "qty": 0.1,
        "stopPrice": 4320.0,
        "stopLoss": 4300.0,
        "stopLossType": "absolute",
    }
    total, detail = g.committed_risk(
        [],
        [foreign],
        [],
        {},
        bid=4300.0,
        ask=4300.4,
        contract_size=100.0,
        slip_points=24.13,
        instrument_id=6102,
    )
    assert total == pytest.approx((20.0 + 24.13) * 0.1 * 100)
    assert detail["foreign"][0]["order_id"] == 77
    with pytest.raises(ValueError, match="unbounded"):
        g.committed_risk(
            [],
            [{**foreign, "stopLoss": None}],
            [],
            {},
            bid=4300.0,
            ask=4300.4,
            contract_size=100.0,
            slip_points=24.13,
            instrument_id=6102,
        )


class _AccountVenue(bg._Venue):
    """The E8 account also holds EURUSD: catalogue, details and a quote for it."""

    _by_key: ClassVar[dict[str, int]] = {"XAUUSD": 6102, "EURUSD": 7001}

    def details(self, symbol: str) -> dict[str, Any]:
        if symbol == "EURUSD":
            return {"contractSize": 100_000.0, "currency": "USD", "lotStep": 0.01}
        return {"contractSize": 100.0, "currency": "USD", "lotStep": 0.01}

    def quote(self, symbol: str) -> tuple[float, float]:
        return (1.1000, 1.1002) if symbol == "EURUSD" else (4300.0, 4300.4)


def _eurusd(stop: float | None) -> dict[str, Any]:
    return {
        "id": 801,
        "tradableInstrumentId": 7001,
        "side": "buy",
        "qty": 0.5,
        "avgPrice": 1.1000,
        "stopLoss": stop,
        "stopLossId": 0,
    }


def test_a_non_xau_position_counts_at_its_stop_plus_slip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """EURUSD long 0.5 lot, stop 20 pips under: 0.0020 x 50,000 = 100 USD to its stop, plus the
    gold slip carried as a share of price (24.13 / 4,300.2 of 1.1001) on 50,000 units."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = _AccountVenue()
    venue._positions = [_eurusd(1.0980)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    (row,) = doc["committed_risk"]["foreign"]
    slip_usd = 24.13 / 4300.2 * 1.1001 * 0.5 * 100_000
    assert row["kind"] == "position"
    assert row["risk_usd"] == pytest.approx(0.0020 * 50_000 + slip_usd, rel=1e-3)
    assert doc["committed_risk"]["total_usd"] == pytest.approx(row["risk_usd"], abs=0.02)


def test_a_non_xau_position_with_no_stop_sends_nothing_with_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = _AccountVenue()
    venue._positions = [_eurusd(None)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == []
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("DEFERRED", ev.R_RISK_UNMEASURABLE)
    assert "whole room" in row["why"]


def test_a_position_on_an_instrument_the_catalogue_cannot_name_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = bg._Venue()  # no catalogue: the EURUSD row cannot be priced
    venue._positions = [_eurusd(1.0980)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == []
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("DEFERRED", ev.R_RISK_UNMEASURABLE)


# ------------------------------------------------------------- v5.2: equity or nothing


@pytest.mark.parametrize(
    "acct",
    [
        {"balance": 100_000.0},
        {"balance": 100_000.0, "equity": None},
        {"equity": float("nan"), "balance": 100_000.0},
        {"equity": 100_000.0, "balance": 100_000.0, "equity_from_balance": 1.0},
        "raise",
    ],
)
def test_missing_equity_sends_nothing_and_bills_missed_growth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, acct: Any
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = bg._Venue()

    def account() -> dict[str, Any]:
        if acct == "raise":
            raise ConnectionError("account state endpoint returned HTML")
        return dict(acct)

    monkeypatch.setattr(venue, "account", account)
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    # v5.3: a refused equity is published null / UNMEASURED, never 0.0
    assert venue.sent == [] and doc["equity"] is None
    assert doc["equity_status"] == "UNMEASURED" and doc["risk_usd"] is None
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("DEFERRED", ev.R_EQUITY_UNREADABLE)
    (bill,) = [r for r in bg._journal(tmp_path) if r.get("rail") == g.EQUITY_UNREADABLE_RAIL]
    assert bill["status"] == "RAIL_BLOCKED" and bill["missed_growth_risk_usd"] is None
    g.run(venue, bg._FlatMT5(), armed=True)
    assert (
        len([r for r in bg._journal(tmp_path) if r.get("rail") == g.EQUITY_UNREADABLE_RAIL]) == 1
    ), "billed once per window per day"
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg

    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    (line,) = [
        x for x in mg.published_e8_gold_lines()["lines"] if x["rail"] == g.EQUITY_UNREADABLE_RAIL
    ]
    assert line["n_blocked"] == 1 and line["saving"]["verdict"] == mg.UNMEASURED


def test_the_venue_flags_an_equity_derived_from_balance_alone() -> None:
    from prop.tradelocker_venue import TradeLockerVenue

    class _Api:
        def __init__(self, st: dict[str, Any]) -> None:
            self.st = st

        def get_account_state(self) -> dict[str, Any]:
            return self.st

    alone = TradeLockerVenue(api=_Api({"balance": 100_000.0})).account()
    assert alone.get("equity_from_balance") == 1.0
    floating = TradeLockerVenue(api=_Api({"balance": 100_000.0, "openNetPnL": -400.0})).account()
    assert floating["equity"] == 99_600.0 and "equity_from_balance" not in floating


# ------------------------------------------------------------- 2. evidence and its ordering


def test_the_ceiling_fit_runs_before_any_risk_budget_deferral(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """3% at a 10 oz contract: 8.95 lots, whose unshrunk 3,000 USD x 1.25 fails the concurrent
    budget. The ceiling caps it to 0.75 and fits that to the budget FIRST, so the window is sent
    and no exempt `risk_budget` deferral is ever written for it."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.03)
    venue = bg._Venue()
    monkeypatch.setattr(
        venue, "details", lambda symbol: {"contractSize": 10.0, "currency": "USD", "lotStep": 0.01}
    )
    assert not g.risk_budget_allows(0.0, 3000.0, 2500.0)[0]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)]
    rows = _decisions(doc)
    assert [r["reason"] for r in rows] == ["placed"]
    assert rows[0]["outcome"] == "PLACED" and "lot_ceiling" in rows[0]["why"]
    assert not [r for r in doc["decisions"] if r["reason"] == ev.R_RISK_BUDGET]


def test_an_unshrunk_window_over_the_budget_is_deferred_with_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Re-cut on live: the book's 2% is capped by the r7.1 code ceiling to 0.6% = 600 USD (0.17
    lots, under the lot ceiling), which alone fits the budget, so the account carries a locked
    0.4-lot short (not at risk; 1,349.2 USD it can still give back): (1,349.2 + 600) x 1.25 =
    2,436.5 > 2,500 - 100 -> DEFERRED, risk_budget, with the evidence row v4 never wrote, and
    the window is not spent."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    bg._cert_book(tmp_path, 0.02)
    venue = bg._Venue()
    venue._positions = [_locked_short(0.4)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == []
    assert doc["committed_risk"]["total_usd"] == pytest.approx(1349.2)
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("DEFERRED", ev.R_RISK_BUDGET)
    assert row["risk_usd"] == pytest.approx(600.0)
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "afternoon" not in saved["windows"]


def test_the_evidence_ledger_holds_the_rail_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(
        monkeypatch,
        tmp_path,
        guard=bg._guard(99_900.0),
        slip=bg._scoped({"status": "MEASURED", "slip_points": 100_000.0, "n": 25}),
    )
    bg._cert_book(tmp_path, 0.0095)
    g.run(bg._Venue(equity=99_900.0), bg._FlatMT5(), armed=True)
    lines = ev.decisions_path().read_text(encoding="utf-8").splitlines()
    (row,) = [json.loads(x) for x in lines if '"afternoon"' in x]
    assert (row["outcome"], row["reason"], row["taken"]) == (
        "SKIPPED",
        g.DAILY_FLOOR_REASON,
        False,
    )


# ------------------------------------------------------------- 3. the margin


def test_step_two_keeps_room_margin_usd_clear_of_the_floor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Re-cut on live: the book's 0.71% is capped by the r7.1 code ceiling to 0.6%, so the same
    geometry is set on a day down 460: 0.6% of 99,540 = 597.24 USD, 0.17 lots, need
    2 x 597.24 + 2 x 24.13 x 17 = 2,014.9, which is under the 2,040 to today's floor but inside
    its last ROOM_MARGIN_USD. v4 sent it with 25 USD to spare; v5 cuts the bracket until it
    clears the margin: L = 1,940 / 11,526 = 0.168 -> 0.16."""
    assert g.ROOM_MARGIN_USD == 100.0
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(99_540.0))
    bg._cert_book(tmp_path, 0.0071)
    venue = bg._Venue(equity=99_540.0)
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    room = min(
        float(doc["guard_decision"]["room_to_daily_floor"]),
        float(doc["guard_decision"]["room_to_static_floor"]),
    )
    need0 = 2 * 0.006 * 99_540.0 + 2 * 24.13 * 17
    assert need0 <= room < need0 + g.ROOM_MARGIN_USD, (need0, room)
    (cut,) = bg._shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["unshrunk_lots"] == {"buy_stop": 0.17, "sell_stop": 0.17}
    sent = {side: lot for side, lot, _px in venue.sent}
    assert sent == {"buy": 0.16, "sell": 0.16}
    assert _bracket_need(sent) <= room - g.ROOM_MARGIN_USD


# ------------------------------------------------------------- 4. a zero p95


@pytest.mark.parametrize("raw", [0.0, 0, -0.0, None, "nan", float("inf")])
def test_a_measured_slip_that_is_zero_or_unusable_reads_the_floor(tmp_path: Path, raw: Any) -> None:
    p = tmp_path / "E8_GOLD_SLIP.json"
    val = float("nan") if raw == "nan" else raw
    p.write_text(json.dumps({"status": "MEASURED", "slip_points": val, "n": 40}), encoding="utf-8")
    assert g.bracket_slip(p)[0] == g.DEFAULT_SLIP_POINTS
    doc = {
        "status": "MEASURED",
        "slip_points": 5.0,
        "n": 40,
        "windows": {"asia": {"status": "MEASURED", "slip_points": val, "n": 40}},
    }
    p.write_text(json.dumps(doc), encoding="utf-8")
    # A window whose own p95 is zero falls to the pooled 5.0, never to zero.
    assert g.bracket_slip(p, window="asia")[0] == 5.0
    doc["slip_points"] = 0.0
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert g.bracket_slip(p, window="asia")[0] == g.DEFAULT_SLIP_POINTS


# ------------------------------------------------------------- 5. the venue-minimum lift


class _TenthLotVenue(bg._Venue):
    """A venue whose minimum and step are 0.1 lots."""

    def min_lot(self, symbol: str) -> float:
        return 0.1

    def details(self, symbol: str) -> dict[str, Any]:
        return {"contractSize": 100.0, "currency": "USD", "lotStep": 0.1}


def test_a_lift_to_the_venue_minimum_is_judged_at_the_lifted_risk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """0.2% of 100k is 200 USD -> 0.06 lots, lifted to the 0.1 minimum: 335 USD a leg, not 200.
    It fits 2,400 (2 x 335 + 2 x 24.13 x 10 = 1,152.6), so it is sent, and the journal bills the
    risk the leg really carries."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    bg._cert_book(tmp_path, 0.002)
    venue = _TenthLotVenue()
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.1, 4310.0), ("sell", 0.1, 4290.0)]
    sent = [r for r in bg._journal(tmp_path) if r["status"] == "SENT"]
    assert all(r["risk_usd"] == pytest.approx(335.0) for r in sent)
    assert "shrunk" not in doc


def test_a_lift_that_does_not_fit_is_never_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Equity 91,100 on a 91,100 day: 1,100 to the static floor, 1,000 after the margin. At 0.2%
    the certified 182.2 USD a leg would 'fit' (2 x 182.2 + 482.6 = 847), but the 0.1 lot the venue
    forces risks 335 a leg: 1,152.6 > 1,000, and 0.1 cannot be cut. RAIL_BLOCKED, with a row."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(91_100.0, day_start=91_100.0))
    bg._cert_book(tmp_path, 0.002)
    venue = _TenthLotVenue(equity=91_100.0)
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = bg._rail_skips(doc, g.DAILY_FLOOR_RAIL)
    assert skip["need_usd"] == pytest.approx(2 * 335.0 + 2 * 24.13 * 10)
    assert skip["room_to_floor"] == pytest.approx(1000.0)
    assert "venue minimum" in skip["why"]
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("SKIPPED", g.DAILY_FLOOR_REASON)
    (blocked,) = [r for r in bg._journal(tmp_path) if r["status"] == "RAIL_BLOCKED"]
    assert blocked["missed_growth_risk_usd"] == pytest.approx(182.2)


# ------------------------------------------------------------- 6. both legs slip


@pytest.mark.parametrize(
    "equity,day_start",
    [
        (100_000.0, 100_000.0),
        (99_900.0, 100_000.0),
        (101_500.0, 100_000.0),
        (105_500.0, 105_500.0),
        (90_900.0, 91_000.0),
        (90_150.0, 90_150.0),
    ],
)
@pytest.mark.parametrize("frac", [0.006, 0.0095, 0.03])
def test_both_legs_filled_and_slipped_fit_the_room(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, equity: float, day_start: float, frac: float
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(equity, day_start=day_start))
    monkeypatch.setattr(g, "RISK_FRAC", frac)
    venue = bg._Venue(equity=equity)
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    gd = doc.get("guard_decision") or {}
    if not venue.sent:
        assert not gd.get("may_open", False) or doc["skipped"], "a no-send leaves a row"
        return
    room = min(float(gd["room_to_daily_floor"]), float(gd["room_to_static_floor"]))
    lots = {side: lot for side, lot, _px in venue.sent}
    assert len(lots) == 2
    assert _bracket_need(lots) <= room - g.ROOM_MARGIN_USD + 1e-6, (lots, room)
    assert all(lot <= g.GOLD_MAX_LOT for lot in lots.values())


# ------------------------------------------------------------- 7. the account stamp


class _StampApi(h._Api):
    """The TLAPI 0.56.2 shape: an int `account_id` and a `_credentials` dict with the server.
    `server` is deliberately None, as on TLAPI (it has no such attribute of its own)."""

    account_id = _FAKE_ID
    acc_num = 1
    server = None
    _credentials: ClassVar[dict[str, Any]] = {
        "username": "nobody@example.invalid",
        "password": "x",
        "server": "FAKE-DEMO",
    }


class _NoServerApi(h._Api):
    account_id = _FAKE_ID
    server = "NOT-THIS-ONE"  # never read: only `_credentials` names the server
    _credentials: ClassVar[dict[str, Any]] = {
        "username": "nobody@example.invalid",
        "password": "x",
        "server": None,
    }


class _StampedVenue(bg._Venue):
    """A venue whose SDK handle carries a FAKE account id and the server in `_credentials`."""

    _api = _StampApi()
    # A venue-side server must not be read either: the key's server is TLAPI's own.
    _creds = types.SimpleNamespace(server="NOT-THIS-ONE-EITHER")


class _NoServerVenue(bg._Venue):
    _api = _NoServerApi()


def _fake_provenance(monkeypatch: pytest.MonkeyPatch, result: Any = _FAKE_KEY) -> list[Any]:
    calls: list[Any] = []

    def account_key(login: object, server: object, *, create: bool = False) -> Any:
        calls.append((login, server, create))
        return result

    mod = types.ModuleType("libs.ops.provenance")
    mod.account_key = account_key  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", mod)
    return calls


def _hist() -> list[dict[str, Any]]:
    return [
        {
            "id": 9001,
            "status": "Filled",
            "positionId": 77,
            "side": "sell",
            "stopPrice": 4290.0,
            "avgPrice": 4290.0,
        },
        {
            "id": 9100,
            "status": "Filled",
            "positionId": 77,
            "side": "buy",
            "stopPrice": 4259.78,
            "avgPrice": 4283.91,
        },
    ]


def test_no_helper_means_no_stamp_never_the_login(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)  # import raises
    assert ev.account_key(_StampedVenue()) is None
    monkeypatch.setattr(g, "STOP_EXITS", tmp_path / "exits.jsonl")
    ev.bind_account(f"tradelocker:{_FAKE_ID}")
    ev.bind_account_key(ev.account_key(_StampedVenue()))
    exits = g.stop_exits_from_history(_hist(), {9001: 77}, {9001: {"window": "asia"}})
    assert g._record_stop_exits(exits, now=h._NOW.to_pydatetime()) == 1
    text = (tmp_path / "exits.jsonl").read_text(encoding="utf-8")
    assert "account_key" not in text and str(_FAKE_ID) not in text


def test_the_helper_stamps_stop_exits_and_evidence_with_an_int_login(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _fake_provenance(monkeypatch)
    venue = _StampedVenue()
    assert ev.tradelocker_login(venue) == _FAKE_ID
    assert ev.tradelocker_server(venue) == "FAKE-DEMO"
    assert ev.account_key_status(venue) == (_FAKE_KEY, ev.AK_OK)
    assert calls == [(_FAKE_ID, "FAKE-DEMO", False)], "the SDK's int login, create=False"
    assert isinstance(calls[0][0], int)
    monkeypatch.setattr(g, "STOP_EXITS", tmp_path / "exits.jsonl")
    ev.bind_account(f"tradelocker:{_FAKE_ID}")
    ev.bind_account_key(ev.account_key(venue))
    exits = g.stop_exits_from_history(_hist(), {9001: 77}, {9001: {"window": "asia"}})
    assert g._record_stop_exits(exits, now=h._NOW.to_pydatetime()) == 1
    (row,) = [json.loads(x) for x in (tmp_path / "exits.jsonl").read_text("utf-8").splitlines()]
    assert row["account_key"] == _FAKE_KEY
    assert str(_FAKE_ID) not in json.dumps(row)


def test_a_full_pass_stamps_the_ledger_and_heartbeat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_provenance(monkeypatch)
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = _StampedVenue()
    g.run(venue, bg._FlatMT5(), armed=True)
    beat = json.loads(ev.heartbeat_path().read_text("utf-8"))
    assert beat["account_key"] == _FAKE_KEY
    rows = [json.loads(x) for x in ev.decisions_path().read_text("utf-8").splitlines()]
    assert rows and all(r["account_key"] == _FAKE_KEY for r in rows)
    for path in (ev.heartbeat_path(), ev.decisions_path()):
        assert str(_FAKE_ID) not in path.read_text("utf-8")


@pytest.mark.parametrize(
    "bad", ["sha256:" + "0" * 15, f"{_FAKE_ID}", None, 12345, "sha256:0123456789ABCDEF"]
)
def test_a_helper_answer_that_is_not_an_hmac_key_is_no_stamp(
    monkeypatch: pytest.MonkeyPatch, bad: Any
) -> None:
    _fake_provenance(monkeypatch, result=bad)
    assert ev.account_key(_StampedVenue()) is None


@pytest.mark.parametrize(
    "raw,login",
    [
        (_FAKE_ID, _FAKE_ID),
        (str(_FAKE_ID), str(_FAKE_ID)),
        (True, None),
        ("", None),
        (0, None),
        (None, None),
    ],
)
def test_the_login_is_passed_through_for_provenance_to_normalise(raw: Any, login: Any) -> None:
    """v5.1: no local int(): provenance.account_key normalises the login itself. A missing,
    zero or bool id is no login. `acc_num` (the account's index, 1, 2, ...) is never the id."""

    class _V:
        _api = types.SimpleNamespace(account_id=raw, acc_num=1)

    assert ev.tradelocker_login(_V()) == login


# ------------------------------------------------------------- v5.1: the server is TLAPI's own


def test_the_server_is_read_from_tlapi_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_provenance(monkeypatch)
    assert ev.tradelocker_server(_StampedVenue()) == "FAKE-DEMO"
    assert ev.account_key(_StampedVenue()) == _FAKE_KEY
    assert calls[-1][1] == "FAKE-DEMO"


def test_api_server_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """TLAPI's `server` is None; a fake one on the handle or on the venue's creds is ignored."""
    calls = _fake_provenance(monkeypatch)
    assert ev.tradelocker_server(_NoServerVenue()) is None

    class _Bare:
        _api = types.SimpleNamespace(account_id=_FAKE_ID, server="SOMETHING")

    assert ev.tradelocker_server(_Bare()) is None
    assert ev.account_key_status(_Bare()) == (None, ev.AK_SERVER_UNREADABLE)
    assert calls == [], "the helper is never called without TLAPI's server"


def test_a_missing_server_fails_closed_and_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_provenance(monkeypatch)
    ledger_path = tmp_path / "alert_ledger.json"
    monkeypatch.setenv(ev.ALERT_LEDGER_ENV, str(ledger_path))
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    doc = g.run(_NoServerVenue(), bg._FlatMT5(), armed=True)
    assert doc["account_key_status"] == ev.AK_SERVER_UNREADABLE
    assert any("account_key not stamped" in a for a in doc.get("alerts") or [])
    beat = json.loads(ev.heartbeat_path().read_text("utf-8"))
    assert beat["account_key"] is None and beat["account_key_status"] == ev.AK_SERVER_UNREADABLE
    rows = [json.loads(x) for x in ev.decisions_path().read_text("utf-8").splitlines()]
    assert rows and all(r["account_key"] is None for r in rows)
    alerts = json.loads(ledger_path.read_text("utf-8"))
    assert ev.AK_ALERT_ID in json.dumps(alerts)
    # Re-cut on live: with no server the venue's own key is unresolvable, so r7.1's account rail
    # refuses new E8 gold risk (fail closed), and the refusal is a REFUSED decision row (ruling
    # (c)) rather than an absent one. The report stamps no key, never the raw login (ruling (e)).
    assert doc["placed"] == []
    (row,) = [r for r in rows if r["window"] == "afternoon"]
    assert (row["outcome"], row["reason"], row["taken"]) == (
        ev.REFUSED, ev.R_ACCOUNT_UNDECLARED, False)
    assert doc["account_key"] is None and doc["account_key_status"] == ev.AK_SERVER_UNREADABLE
    assert "account" not in doc
    # The next pass that stamps again closes the page.
    assert ev.page_account_key(ev.AK_OK) == "FIXED"


def test_a_dormant_helper_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """v5.2: HELPER_ABSENT pages too -- once OCO v2 reads the key, a silent None is a join that
    fails without anyone knowing."""
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", None)
    ledger_path = tmp_path / "alert_ledger.json"
    monkeypatch.setenv(ev.ALERT_LEDGER_ENV, str(ledger_path))
    doc: dict[str, Any] = {}
    assert ev.bind_pass_account_key(_StampedVenue(), doc) == ev.AK_HELPER_ABSENT
    assert any("HELPER_ABSENT" in a for a in doc["alerts"])
    assert ev.AK_ALERT_ID in ledger_path.read_text("utf-8")


@pytest.mark.parametrize("answer", [None, "sha256:short"])
def test_a_keyless_answer_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: Any
) -> None:
    """No box key (the helper answers None) or a login of -5 (no key) is KEY_UNAVAILABLE and
    pages (v5.2)."""
    _fake_provenance(monkeypatch, result=answer)
    ledger_path = tmp_path / "alert_ledger.json"
    monkeypatch.setenv(ev.ALERT_LEDGER_ENV, str(ledger_path))
    doc: dict[str, Any] = {}
    assert ev.bind_pass_account_key(_StampedVenue(), doc) == ev.AK_KEY_UNAVAILABLE
    assert {ev.AK_KEY_UNAVAILABLE, ev.AK_HELPER_ABSENT} <= ev.AK_PAGE
    assert ev.AK_ALERT_ID in ledger_path.read_text("utf-8")


#: The auditor's reference derivation (v5c provenance.account_key): "sha256:" + the first 16 hex
#: of HMAC-SHA256(box key, f"{norm_login}@{server.strip()}"). A fixed vector, computed once, with
#: a throwaway key, a FAKE login and a server whose case and padding must survive to the helper.
_VECTOR_KEY = b"a" * 64
_VECTOR_SERVER = " FAKE-Demo-Server "
_VECTOR = "sha256:3e29c239439974ee"


def test_the_key_matches_the_auditors_reference_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import hmac

    seen: list[Any] = []

    def account_key(login: object, server: object, *, create: bool = False) -> str | None:
        seen.append((login, server, create))
        canon = str(int(login)) if isinstance(login, int) else None  # type: ignore[call-overload]
        if canon is None:
            return None
        srv = str(server).strip()
        mac = hmac.new(_VECTOR_KEY, f"{canon}@{srv}".encode(), hashlib.sha256).hexdigest()
        return "sha256:" + mac[:16]

    mod = types.ModuleType("libs.ops.provenance")
    mod.account_key = account_key  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "libs.ops.provenance", mod)

    class _Api(h._Api):
        account_id = _FAKE_ID
        _credentials: ClassVar[dict[str, Any]] = {"server": _VECTOR_SERVER}

    class _V:
        _api = _Api()

    assert ev.account_key(_V()) == _VECTOR
    # The server reached the helper RAW: unstripped and with its case.
    assert seen == [(_FAKE_ID, _VECTOR_SERVER, False)]


# ------------------------------------------------------------- the scrub leaks (evidence v5 note)


@pytest.mark.parametrize(
    "text",
    [
        f"subacc_{_FAKE_ID} refused",
        f"SubAcc-{_FAKE_ID}",
        f"/trade/acc.{_FAKE_ID}/orders",
        f"accountNumber={_FAKE_ID}",
        f"account_number: {_FAKE_ID}",
    ],
)
def test_the_scrub_catches_subacc_acc_dot_and_account_number(text: str) -> None:
    out = ev.scrub(text)  # no account bound: the word pattern alone must catch it
    assert str(_FAKE_ID) not in out and ev.REDACTED in out


@pytest.mark.parametrize(
    "text", ["accuracy 95", "accepted 4300.25", "price 4300.25 lot 0.27", "subtotal 4300"]
)
def test_the_scrub_leaves_prices_and_ordinary_words(text: str) -> None:
    assert ev.scrub(text) == text


# ------------------------------------------------------------- v5.3 (audit HOLD on 0a19b657)


class _StopIdVenue(_AccountVenue):
    """EURUSD long whose stop exists ONLY as a resting order named by stopLossId."""

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [
            {
                "id": 5551,
                "tradableInstrumentId": 7001,
                "side": "sell",
                "qty": 0.5,
                "stopPrice": 1.0980,
                "positionId": 801,
            }
        ]


def _eurusd_stop_by_id() -> dict[str, Any]:
    return {**_eurusd(None), "stopLossId": 5551}


def test_mf1_an_fx_stop_held_only_as_stop_loss_id_is_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MF1: before v5.3 the non-XAU stop was read from row["stopLoss"] only, so this position
    read as stopless and froze every gold window. It now prices exactly as the stopLoss case."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    venue = _StopIdVenue()
    venue._positions = [_eurusd_stop_by_id()]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    (row,) = doc["committed_risk"]["foreign"]
    slip_usd = 24.13 / 4300.2 * 1.1001 * 0.5 * 100_000
    assert row["kind"] == "position" and row["stop"] == pytest.approx(1.0980)
    assert row["risk_usd"] == pytest.approx(0.0020 * 50_000 + slip_usd, rel=1e-3)
    assert row["slip_source"].startswith("unmeasured EURUSD")
    assert not [d for d in doc["decisions"] if d["reason"] == ev.R_RISK_UNMEASURABLE]
    assert venue.sent, "the gold window is no longer frozen by the FX position"


def test_mf2_a_risk_budget_deferral_is_billed_once_per_window_per_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MF2: the unshrunk risk_budget deferral bills its withheld risk, once per window per day.
    Re-cut on live: the budget binds at the 0.006 code ceiling beside a locked 0.4-lot short (as
    in test_an_unshrunk_window_over_the_budget_is_deferred_with_a_row): 600 USD withheld."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    bg._cert_book(tmp_path, 0.02)
    venue = bg._Venue()
    venue._positions = [_locked_short(0.4)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == []
    (bill,) = [r for r in bg._journal(tmp_path) if r.get("rail") == g.RISK_BUDGET_RAIL]
    assert bill["status"] == "RAIL_BLOCKED" and bill["reason"] == ev.R_RISK_BUDGET
    assert bill["window"] == "afternoon"
    assert bill["missed_growth_risk_usd"] == pytest.approx(600.0)
    assert bill["committed_risk_usd"] == pytest.approx(doc["committed_risk"]["total_usd"])
    g.run(venue, bg._FlatMT5(), armed=True)
    assert len([r for r in bg._journal(tmp_path) if r.get("rail") == g.RISK_BUDGET_RAIL]) == 1
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg

    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    (line,) = [x for x in mg.published_e8_gold_lines()["lines"] if x["rail"] == g.RISK_BUDGET_RAIL]
    assert line["n_blocked"] == 1 and line["risk_withheld_usd"] == pytest.approx(600.0)


def _fx_hist_row(oid: int, side: str, stop: float, fill: float, **kw: Any) -> dict[str, Any]:
    return {
        "id": oid,
        "status": "Filled",
        "tradableInstrumentId": 7001,
        "positionId": 801,
        "side": side,
        "stopPrice": stop,
        "avgPrice": fill,
        "isOpen": "false",
        **kw,
    }


def test_fx_stop_exits_are_closing_fills_with_adverse_slip_only() -> None:
    names = {6102: "XAUUSD", 7001: "EURUSD"}
    rows = [
        _fx_hist_row(1, "sell", 1.1000, 1.0989),  # long stopped 11 points through
        _fx_hist_row(2, "buy", 1.1000, 1.0995, positionId=802),  # good side: 0
        _fx_hist_row(3, "buy", 1.1000, 1.1010, isOpen="true"),  # an FX ENTRY stop, never
        _fx_hist_row(4, "sell", 1.1000, 1.0990, isOpen=None),  # unknown flag, never
        _fx_hist_row(5, "sell", 4300.0, 4290.0, tradableInstrumentId=6102),  # gold, never
        _fx_hist_row(6, "sell", 1.1000, 1.0990, tradableInstrumentId=9999),  # uncatalogued
        _fx_hist_row(7, "sell", 1.1000, 1.0990, status="Cancelled"),
    ]
    out = g.fx_stop_exits_from_history(
        rows, names, xau_instrument_id=6102, seen_open={"801": "buy", "802": "sell"}
    )
    assert [r["order_id"] for r in out] == [1, 2]
    # row 3 is a filled buy OPENING 801, so row 1 also joins through the history
    assert [r["joined_by"] for r in out] == ["history", "position_book"]
    assert out[0]["slip_frac"] == pytest.approx(0.0011 / 1.1, rel=1e-6)
    assert out[1]["slip_frac"] == 0.0
    assert {r["symbol"] for r in out} == {"EURUSD"}


def test_fx_slip_is_measured_per_symbol_only_from_twenty_exits(tmp_path: Path) -> None:
    path = tmp_path / "fx.jsonl"
    rows = [{"order_id": i, "symbol": "EURUSD", "slip_frac": 0.0001} for i in range(20)]
    rows += [{"order_id": 100 + i, "symbol": "EURCHF", "slip_frac": 0.0002} for i in range(19)]
    rows += [{"order_id": 200 + i, "symbol": "GBPUSD", "slip_frac": 0.0} for i in range(25)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    got = g.fx_slip_fractions(path)
    assert got["EURUSD"] == {"n": 20, "slip_frac": pytest.approx(0.0001), "status": "MEASURED"}
    assert got["EURCHF"]["status"] == "UNMEASURED" and got["EURCHF"]["slip_frac"] is None
    assert got["GBPUSD"]["status"] == "P95_ZERO", "a zero p95 is not no slip"
    assert g.fx_slip_fractions(tmp_path / "absent.jsonl") == {}


def test_a_measured_fx_slip_prices_the_fx_stop_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    fx = tmp_path / "fx.jsonl"
    fx.write_text(
        "".join(
            # Stamped with the pass's account_key: a keyed pass reads only its own rows (v5.5).
            json.dumps({"order_id": i, "symbol": "EURUSD", "slip_frac": 0.0001,
                        "account_key": bg._pass_key()}) + "\n"
            for i in range(20)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(g, "FX_STOP_EXITS", fx)
    venue = _AccountVenue()
    venue._positions = [_eurusd(1.0980)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    (row,) = doc["committed_risk"]["foreign"]
    assert row["risk_usd"] == pytest.approx(0.0020 * 50_000 + 0.0001 * 1.1001 * 50_000, rel=1e-3)
    assert row["slip_source"].startswith("measured:") and row["slip_fraction"] == 0.0001


def test_a_full_pass_journals_the_fx_lanes_stop_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    fx = tmp_path / "fx.jsonl"
    monkeypatch.setattr(g, "FX_STOP_EXITS", fx)

    class _HistApi(h._Api):
        @staticmethod
        def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
            return [_fx_hist_row(31, "sell", 1.1000, 1.0995)]

    venue = _AccountVenue()
    venue._api = _HistApi()  # type: ignore[assignment]
    venue._positions = [_eurusd(1.0980)]  # the lane sees long 801 open, so its stop joins
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert doc["fx_stop_exits_recorded"] == 1
    g.run(venue, bg._FlatMT5(), armed=True)
    (row,) = [json.loads(x) for x in fx.read_text("utf-8").splitlines()]
    assert row["symbol"] == "EURUSD" and row["slip_frac"] == pytest.approx(0.0005 / 1.1, abs=1e-8)


def test_committed_slip_is_the_larger_of_pooled_and_every_windows_p95(tmp_path: Path) -> None:
    path = tmp_path / "slip.json"
    path.write_text(
        json.dumps(
            {
                "status": "MEASURED",
                "n": 40,
                "slip_points": 20.0,
                "windows": {
                    "asia": {"status": "MEASURED", "n": 20, "slip_points": 31.5},
                    "afternoon": {"status": "MEASURED", "n": 20, "slip_points": 12.0},
                },
            }
        ),
        encoding="utf-8",
    )
    pts, src = g.committed_slip_points(path)
    assert pts == 31.5 and "asia" in src
    assert g.committed_slip_points(tmp_path / "none.json")[0] == g.DEFAULT_SLIP_POINTS


def test_the_pass_charges_committed_risk_at_the_worst_window_slip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    slip = {
        "status": "MEASURED",
        "n": 40,
        "slip_points": 20.0,
        "windows": {"asia": {"status": "MEASURED", "n": 20, "slip_points": 31.5}},
    }
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard(), slip=bg._scoped(slip))
    venue = _AccountVenue()
    venue._positions = [_eurusd(1.0980)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert doc["committed_risk"]["slip_points"] == 31.5
    assert "asia" in doc["committed_risk"]["slip_source"]


# ------------------------------------------------------------- v5.5 (follow-up to CLEAR v5.4)

_KEY_A = "sha256:aaaaaaaaaaaaaaaa"
_KEY_B = "sha256:bbbbbbbbbbbbbbbb"


def test_v55_an_fx_entry_stop_is_never_counted() -> None:
    """A filled buy STOP marked isOpen=false (wrongly) on the position it opened: the position is
    long, so a buy is on its own side and never joins -- neither by the book nor by history."""
    names = {7001: "EURUSD"}
    entry = _fx_hist_row(41, "buy", 1.1000, 1.1000, positionId=900)
    assert g.fx_stop_exits_from_history([entry], names, xau_instrument_id=6102) == []
    assert (
        g.fx_stop_exits_from_history(
            [entry], names, xau_instrument_id=6102, seen_open={"900": "buy"}
        )
        == []
    )


def test_v55_an_unjoined_closing_order_is_never_counted() -> None:
    names = {7001: "EURUSD"}
    orphan = _fx_hist_row(42, "sell", 1.1000, 1.0990, positionId=901)
    assert g.fx_stop_exits_from_history([orphan], names, xau_instrument_id=6102) == []
    other = {"999": "buy"}  # the lane saw a different position open
    assert (
        g.fx_stop_exits_from_history([orphan], names, xau_instrument_id=6102, seen_open=other) == []
    )


def test_v55_a_closing_stop_joins_through_a_different_opening_fill() -> None:
    names = {7001: "EURUSD"}
    opener = _fx_hist_row(50, "buy", 0.0, 1.1005, positionId=902, isOpen="true")
    close = _fx_hist_row(51, "sell", 1.0980, 1.0978, positionId=902)
    (row,) = g.fx_stop_exits_from_history([opener, close], names, xau_instrument_id=6102)
    assert row["order_id"] == 51 and row["joined_by"] == "history"


def _fx_rows(path: Path, key: Any, n: int, frac: float, start: int) -> list[dict[str, Any]]:
    rows = [{"order_id": start + i, "symbol": "EURUSD", "slip_frac": frac} for i in range(n)]
    if key is not None:
        for r in rows:
            r["account_key"] = key
    return rows


def test_v55_fx_slip_is_read_only_from_the_accounts_own_rows(tmp_path: Path) -> None:
    path = tmp_path / "fx.jsonl"
    rows = _fx_rows(path, _KEY_A, 20, 0.0003, 0)
    rows += _fx_rows(path, _KEY_B, 25, 0.0009, 100)
    rows += _fx_rows(path, None, 25, 0.0007, 200)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    a = g.fx_slip_fractions(path, account_key=_KEY_A)["EURUSD"]
    assert a["n"] == 20 and a["slip_frac"] == pytest.approx(0.0003)
    assert g.fx_slip_fractions(path, account_key=None)["EURUSD"]["n"] == 25
    assert "EURUSD" not in g.fx_slip_fractions(path, account_key="sha256:cccccccccccccccc")
    ev.bind_account_key(_KEY_B)
    try:
        assert g.fx_slip_fractions(path)["EURUSD"]["slip_frac"] == pytest.approx(0.0009)
    finally:
        ev.bind_account_key(None)


def test_v55_the_gold_slip_file_is_scoped_to_its_account(tmp_path: Path) -> None:
    from prop import e8_gold_slip

    exits, out = tmp_path / "exits.jsonl", tmp_path / "slip.json"
    rows = [
        {"order_id": i, "side": "sell", "stop": 4300.0, "fill": 4290.0, "account_key": _KEY_B}
        for i in range(25)
    ]
    rows += [
        {"order_id": 100 + i, "side": "sell", "stop": 4300.0, "fill": 4299.0} for i in range(25)
    ]
    exits.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    doc = e8_gold_slip.refresh(exits=exits, out=out, measured_at="2026-10-21", account_key=_KEY_A)
    assert doc["n"] == 0 and doc["account_scoped"] and doc["account_key"] == _KEY_A
    doc = e8_gold_slip.refresh(exits=exits, out=out, measured_at="2026-10-21", account_key=_KEY_B)
    assert doc["n"] == 25 and doc["status"] == "MEASURED"
    ev.bind_account_key(_KEY_B)
    try:
        assert g.bracket_slip(out)[0] == pytest.approx(10.0)
        ev.bind_account_key(_KEY_A)  # a new account never inherits B's slip
        pts, src = g.bracket_slip(out)
        assert pts == g.DEFAULT_SLIP_POINTS and "not measured for this account" in src
    finally:
        ev.bind_account_key(None)
    assert g.bracket_slip(out)[0] == g.DEFAULT_SLIP_POINTS, "an unkeyed pass ignores B's file"
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"status": "MEASURED", "n": 30, "slip_points": 9.0}), "utf-8")
    assert g.bracket_slip(legacy)[0] == 9.0
    ev.bind_account_key(_KEY_A)
    try:
        assert g.bracket_slip(legacy)[0] == g.DEFAULT_SLIP_POINTS, "unscoped rows never count"
    finally:
        ev.bind_account_key(None)


def test_v55_a_zero_p95_reads_as_the_floor_not_measured(tmp_path: Path) -> None:
    p = tmp_path / "slip.json"
    p.write_text(json.dumps({"status": "MEASURED", "n": 30, "slip_points": 0.0}), "utf-8")
    pts, src = g.bracket_slip(p)
    assert pts == g.DEFAULT_SLIP_POINTS and src.startswith("floor (p95_zero)")
    fx = tmp_path / "fx.jsonl"
    fx.write_text(
        "".join(
            json.dumps({"order_id": i, "symbol": "EURUSD", "slip_frac": 0.0}) + "\n"
            for i in range(30)
        ),
        encoding="utf-8",
    )
    got = g.fx_slip_fractions(fx, account_key=None)["EURUSD"]
    assert got["status"] == "P95_ZERO" and got["slip_frac"] is None
    price = g.foreign_pricer(_AccountVenue(), slip_fraction=0.0056, fx_slip={"EURUSD": got})
    _, meta = price(_eurusd(1.0980), "position")
    assert meta["slip_source"].startswith("floor (p95_zero)") and meta["slip_fraction"] == 0.0056


def _capture_pages(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sends: list[tuple[str, str]] = []

    def send(title: str, body: str) -> dict[str, Any]:
        sends.append((title, body))
        return {"armed": 1, "delivered": 1}

    monkeypatch.setattr(ev, "SENDER", send)
    # These tests pin the DIRECT fallback pager; the v5f outbox path is tested below.
    monkeypatch.setattr(ev, "_PAGE", ev._page_direct)
    return sends


def test_v55_risk_unmeasurable_is_billed_once_and_paged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import os

    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    sends = _capture_pages(monkeypatch)
    ledger_path = Path(os.environ[ev.ALERT_LEDGER_ENV])
    venue = _AccountVenue()
    venue._positions = [_eurusd(None)]  # no stop: the account's risk cannot be bounded
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == [] and doc["risk_unmeasurable_page"] == "QUEUED"
    assert ev.drain_pages(5.0) == 0
    assert len(sends) == 1 and "unmeasurable" in sends[0][1], "v5.6: it is a page"
    (bill,) = [r for r in bg._journal(tmp_path) if r.get("rail") == g.RISK_UNMEASURABLE_RAIL]
    assert bill["status"] == "RAIL_BLOCKED" and bill["reason"] == ev.R_RISK_UNMEASURABLE
    assert isinstance(bill["missed_growth_risk_usd"], float) and bill["missed_growth_risk_usd"] > 0
    alert = json.loads(ledger_path.read_text("utf-8"))["alerts"][g.RISK_UNMEASURABLE_ALERT_ID]
    assert alert["state"] == "OPEN"
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert "risk_unmeasurable_page" not in doc, "paged once, not every pass"
    assert ev.drain_pages(5.0) == 0 and len(sends) == 1
    assert len([r for r in bg._journal(tmp_path) if r.get("rail") == g.RISK_UNMEASURABLE_RAIL]) == 1
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg

    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    (line,) = [
        x for x in mg.published_e8_gold_lines()["lines"] if x["rail"] == g.RISK_UNMEASURABLE_RAIL
    ]
    assert line["n_blocked"] == 1 and line["risk_withheld_usd"] > 0
    venue._positions = [_eurusd(1.0980)]  # the stop is readable again: the page closes
    g.run(venue, bg._FlatMT5(), armed=True)
    assert ev.drain_pages(5.0) == 0 and len(sends) == 1, "a close is not a page"
    alert = json.loads(ledger_path.read_text("utf-8"))["alerts"][g.RISK_UNMEASURABLE_ALERT_ID]
    assert alert["state"] == "FIXED"


# ------------------------------------------------------------- v5.6 (audit HOLD on 04e58c70)


@pytest.fixture
def _ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "alerts" / "alert_ledger.json"
    monkeypatch.setenv(ev.ALERT_LEDGER_ENV, str(path))
    yield path
    ev.drain_pages(5.0)


def test_v56_a_page_is_sent_only_when_the_alert_opens(
    monkeypatch: pytest.MonkeyPatch, _ledger: Path
) -> None:
    sends = _capture_pages(monkeypatch)
    for _ in range(3):
        assert ev.page_alert("e8_probe", "firing", firing=True) == "QUEUED"
        ev.drain_pages(5.0)
    assert len(sends) == 1, "a standing alert re-observed is not a new page"
    ev.page_alert("e8_probe", "", firing=False)
    ev.drain_pages(5.0)
    assert len(sends) == 1, "a close is not a page"
    assert json.loads(_ledger.read_text("utf-8"))["alerts"]["e8_probe"]["state"] == "FIXED"
    ev.page_alert("e8_probe", "again", firing=True)  # FIXED -> REGRESSED re-opens: a page
    ev.drain_pages(5.0)
    assert len(sends) == 2


def test_v56_the_caller_never_waits_on_a_slow_send_or_a_held_lock(
    monkeypatch: pytest.MonkeyPatch, _ledger: Path
) -> None:
    import threading
    import time

    gate = threading.Event()

    def slow(title: str, body: str) -> dict[str, Any]:
        gate.wait(5.0)
        return {"armed": 1, "delivered": 1}

    monkeypatch.setattr(ev, "SENDER", slow)
    monkeypatch.setattr(ev, "_PAGE", ev._page_direct)
    t0 = time.monotonic()
    assert ev.page_alert("e8_slow", "firing", firing=True) == "QUEUED"
    assert time.monotonic() - t0 < 0.5, "page_alert returned without waiting on the send"
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with ev._os_lock(_ledger.with_name(_ledger.name + ".flock"), 1.0):
            held.set()
            release.wait(5.0)

    gate.set()
    ev.drain_pages(5.0)
    th = threading.Thread(target=hold, daemon=True)
    th.start()
    held.wait(2.0)
    t0 = time.monotonic()
    assert ev.page_alert("e8_slow", "", firing=False) == "QUEUED"
    assert time.monotonic() - t0 < 0.5, "page_alert returned without waiting on the lock"
    release.set()
    th.join(2.0)


def test_v56_a_sender_that_raises_is_swallowed_and_logged(
    monkeypatch: pytest.MonkeyPatch, _ledger: Path
) -> None:
    said: list[str] = []

    def boom(title: str, body: str) -> dict[str, Any]:
        raise ConnectionError("ntfy unreachable")

    monkeypatch.setattr(ev, "SENDER", boom)
    monkeypatch.setattr(ev, "_PAGE", ev._page_direct)
    ev.page_alert("e8_boom", "firing", firing=True, log=said.append)
    assert ev.drain_pages(5.0) == 0
    assert any("sender raised ConnectionError" in x for x in said)


def test_v56_a_raising_alert_path_never_defers_a_window_or_escapes_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def raises(*a: Any, **k: Any) -> str:
        raise RuntimeError("alert path broken")

    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    monkeypatch.setattr(ev, "page_alert", raises)
    venue = _AccountVenue()
    venue._positions = [_eurusd(1.0980)]  # measurable: the close call runs and raises
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent, "the close call's raise did not defer the window"
    assert not [d for d in doc["decisions"] if d["reason"] == ev.R_RISK_UNMEASURABLE]
    venue = _AccountVenue()
    venue._positions = [_eurusd(None)]  # unmeasurable: the open call runs and raises
    doc = g.run(venue, bg._FlatMT5(), armed=True)  # never escapes run()
    assert venue.sent == []


def test_v56_an_unreadable_ledger_is_never_saved_over(_ledger: Path) -> None:
    _ledger.mkdir(parents=True)  # a directory: it exists and cannot be read as a file
    with pytest.raises(ev.AlertLedgerUnreadable), ev._ledger_txn(_ledger, 1.0) as txn:
        txn.dirty = True
    assert _ledger.is_dir()


def test_v56_an_unparseable_ledger_is_set_aside_not_lost(_ledger: Path) -> None:
    _ledger.parent.mkdir(parents=True)
    _ledger.write_text("{torn", "utf-8")
    with ev._ledger_txn(_ledger, 1.0) as txn:
        txn.ledger.observe("e8_x", "m", scope="RUNTIME")
        txn.dirty = True
    assert "e8_x" in json.loads(_ledger.read_text("utf-8"))["alerts"]
    (aside,) = list(_ledger.parent.glob("alert_ledger.json.unparseable-*"))
    assert aside.read_text("utf-8") == "{torn"


def test_v56_a_held_lock_is_never_shared_the_waiter_gives_up(
    monkeypatch: pytest.MonkeyPatch, _ledger: Path
) -> None:
    lock = _ledger.with_name(_ledger.name + ".flock")
    monkeypatch.setattr(ev, "AK_LOCK_WAIT_S", 0.1)
    with ev._os_lock(lock, 1.0):
        with pytest.raises(ev.AlertLedgerBusy), ev._ledger_txn(_ledger, 0.1):
            pass
        assert ev.page_account_key(ev.AK_HELPER_ABSENT) is None, "busy: nothing written"
    assert not _ledger.exists()
    assert lock.exists(), "the sidecar is never deleted"
    assert ev.page_account_key(ev.AK_HELPER_ABSENT) == "OPEN"
    assert ev.AK_ALERT_ID in json.loads(_ledger.read_text("utf-8"))["alerts"]


def test_v56_concurrent_writers_lose_no_alert(_ledger: Path) -> None:
    import threading

    def write(i: int) -> None:
        with ev._ledger_txn(_ledger, 10.0) as txn:
            txn.ledger.observe(f"e8_c{i}", "m", scope="RUNTIME")
            txn.dirty = True

    ts = [threading.Thread(target=write, args=(i,)) for i in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(15.0)
    alerts = json.loads(_ledger.read_text("utf-8"))["alerts"]
    assert {f"e8_c{i}" for i in range(12)} <= set(alerts)


# ------------------------------------------------------------- v5.6 on publish_sync v5f: the outbox


@pytest.fixture
def _outbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """v5f's provenance outbox in tmp, a fresh in-process dedupe, a recording fake sender."""
    from libs.ops import provenance as pv

    key = tmp_path / "data" / "secrets" / "account_key.hmac"
    key.parent.mkdir(parents=True)
    monkeypatch.setenv(pv.KEY_ENV, str(key))
    monkeypatch.setenv(ev.ALERT_LEDGER_ENV, str(tmp_path / "data" / "alert_ledger.json"))
    monkeypatch.setattr(pv, "_ENQUEUED", {})
    monkeypatch.setattr(pv, "_ENQUEUE_FAILED", {})
    monkeypatch.setattr(pv, "_LAST_TRY", {})
    sent: list[tuple[str, str]] = []

    def record(title: str, body: str) -> dict[str, Any]:
        sent.append((title, body))
        return {"armed": 1, "delivered": 1}

    monkeypatch.setattr(pv, "SENDER", record)
    monkeypatch.setattr(pv, "_default_sender", lambda: pytest.fail("the real sender was reached"))
    pv.sent_log = sent  # type: ignore[attr-defined]
    yield pv
    ev.drain_pages(5.0)


def _rows(pv: Any, aid: str) -> list[dict[str, Any]]:
    path = pv._outbox_path()
    if not path.exists():
        return []
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("aid") == aid]


def test_v56f_the_pager_is_provenances_enqueue_only_page(_outbox: Any) -> None:
    assert ev._PAGE is _outbox._page and ev._enqueue_only()


def test_v56f_a_hanging_sender_never_blocks_either_alert_path(
    _outbox: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    calls: list[str] = []

    def hangs(title: str, body: str) -> dict[str, Any]:
        calls.append(title)
        time.sleep(30)
        return {"delivered": 1}

    monkeypatch.setattr(_outbox, "SENDER", hangs)
    t0 = time.monotonic()
    assert ev.page_alert("e8_hang", "firing", firing=True) == "QUEUED"
    assert time.monotonic() - t0 < 0.5
    t0 = time.monotonic()
    assert ev.page_account_key(ev.AK_HELPER_ABSENT) == "OPEN"
    assert time.monotonic() - t0 < 0.5
    assert ev.drain_pages(5.0) == 0
    assert calls == [], "nothing on either path called the sender"
    assert _rows(_outbox, "e8_hang") and _rows(_outbox, ev.AK_ALERT_ID)


def test_v56f_an_open_writes_one_outbox_row_that_deliver_pending_sends(_outbox: Any) -> None:
    for _ in range(3):
        ev.page_alert("e8_open", "committed risk unmeasurable", firing=True)
        ev.drain_pages(5.0)
    (row,) = _rows(_outbox, "e8_open")
    assert row["status"] == "OPEN" and "unmeasurable" in row["body"]
    res = _outbox.deliver_pending()
    assert [x for x in res["sent"] if x["aid"] == "e8_open"] == [
        {"aid": "e8_open", "sent": True, "status": "OPEN"}
    ]
    assert len(_outbox.sent_log) == 1
    assert _outbox.deliver_pending()["sent"] == [], "a delivered OPEN is not re-sent"


def test_v56f_a_close_writes_ok_and_the_recovery_is_paged_once(_outbox: Any) -> None:
    ev.page_alert("e8_close", "firing", firing=True)
    ev.drain_pages(5.0)
    _outbox.deliver_pending()
    ev.page_alert("e8_close", "", firing=False)
    ev.drain_pages(5.0)
    assert [r["status"] for r in _rows(_outbox, "e8_close")] == ["OK"]
    res = _outbox.deliver_pending()
    assert {"aid": "e8_close", "sent": True, "status": "OK"} in res["sent"]
    assert len(_outbox.sent_log) == 2
    assert _outbox.deliver_pending()["sent"] == []


def test_v56f_page_account_key_enqueues_open_and_ok(_outbox: Any) -> None:
    assert ev.page_account_key(ev.AK_SERVER_UNREADABLE) == "OPEN"
    (row,) = _rows(_outbox, ev.AK_ALERT_ID)
    assert row["status"] == "OPEN" and row["sig"] == ev.AK_SERVER_UNREADABLE
    _outbox.deliver_pending()
    assert ev.page_account_key(ev.AK_OK) == "FIXED"
    assert [r["status"] for r in _rows(_outbox, ev.AK_ALERT_ID)] == ["OK"]
    res = _outbox.deliver_pending()
    assert {"aid": ev.AK_ALERT_ID, "sent": True, "status": "OK"} in res["sent"]
    assert ev.page_account_key(ev.AK_OK) is None, "nothing open: no OK row"
    assert _rows(_outbox, ev.AK_ALERT_ID) == []


# ------------------------------------------------------------- re-cut on live: rulings (c), (e)


def test_recut_an_account_refusal_is_a_refused_decision_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ruling (c): when r7.1's account rail refuses new E8 gold risk (here: E8_ACCOUNT.json
    absent), the window is still a decision row -- REFUSED, e8_account_undeclared, not taken,
    with its reason -- beside the billed RAIL_BLOCKED intents row. Nothing is sent."""
    from mt5desk import cross_account as xa

    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    xa.E8_ACCOUNT_FILE.unlink()
    venue = bg._Venue()
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert venue.sent == [] and doc["placed"] == []
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"], row["taken"]) == (
        ev.REFUSED, ev.R_ACCOUNT_UNDECLARED, False)
    assert "undeclared" in row["why"] and row["risk_usd"] == pytest.approx(500.0)
    (led,) = [json.loads(x) for x in ev.decisions_path().read_text("utf-8").splitlines()
              if '"afternoon"' in x]
    assert (led["outcome"], led["reason"]) == (ev.REFUSED, ev.R_ACCOUNT_UNDECLARED)
    (bill,) = [r for r in bg._journal(tmp_path) if r.get("rail") == "e8_account_undeclared"]
    assert bill["status"] == "RAIL_BLOCKED" and bill["missed_growth_risk_usd"] == 500.0


def test_recut_the_pass_report_stamps_the_account_key_never_the_login(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ruling (e): E8_GOLD.json carries the pass's HMAC account_key (provenance.account_key, the
    stamp the heartbeat and decision rows carry) and its status, never `tradelocker:<login>`."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    doc = g.run(bg._Venue(), bg._FlatMT5(), armed=True)
    assert "account" not in doc
    assert doc["account_key"] == bg._pass_key() and doc["account_key_status"] == ev.AK_OK
    assert ev.ACCOUNT_KEY_SHAPE.match(doc["account_key"])
    text = Path(g.OUT).read_text("utf-8")
    assert '"account_key": "' + bg._pass_key() + '"' in text
    # The heartbeat block carries only the keyed pseudonym (`account_ref`), never the label.
    assert "tradelocker:31337" not in text and '"account":' not in text
