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
from typing import Any

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


def _bracket_need(lots: dict[str, float], stop: float = 33.5, contract: float = 100.0) -> float:
    """Both legs to their stops plus both legs' default slip, in USD."""
    return float(sum(lot * contract * (stop + g.DEFAULT_SLIP_POINTS) for lot in lots.values()))


# ------------------------------------------------------------- 1. committed risk


def test_the_floor_fit_subtracts_a_break_even_winners_give_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A short opened at 4330 with its stop ratcheted to 4310 is not AT RISK (the one-at-a-time
    rule lets the afternoon window place), but the mark is 4300.4, so 9.6 points x 1 lot x 100 oz
    = 960 USD of open profit can still go back to today's floor. v4 fitted the new bracket to the
    whole 2,500 of room; v5 fits it to 2,500 - 960 - 100 = 1,440.

    The book is short, so only the agreeing sell leg is sized: 950 USD -> 0.28 lots needs
    950 + 24.13 x 28 = 1,626 > 1,440, so L = 1,440 / (100 x (33.5 + 24.13)) = 0.249 -> 0.24.
    """
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = bg._Venue()
    venue._positions = [
        {
            "id": 501,
            "tradableInstrumentId": 6102,
            "side": "sell",
            "qty": 1.0,
            "avgPrice": 4330.0,
            "stopLoss": 4310.0,
            "stopLossId": 0,
        }
    ]
    doc = g.run(venue, h._MT5(), armed=True)
    (pos,) = doc["committed_risk"]["positions"]
    assert pos["at_risk"] is False and pos["risk_usd"] == pytest.approx(960.0)
    assert venue.sent == [("sell", 0.24, 4290.0)]
    (cut,) = bg._shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["committed_usd"] == pytest.approx(960.0)
    assert cut["room_to_floor"] == pytest.approx(2500.0 - 960.0 - g.ROOM_MARGIN_USD)
    # What the account can now lose today: the give-back plus the new leg slipped.
    assert 960.0 + _bracket_need({"sell_stop": 0.24}) <= 2500.0 - g.ROOM_MARGIN_USD


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
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)]
    rows = _decisions(doc)
    assert [r["reason"] for r in rows] == ["placed"]
    assert rows[0]["outcome"] == "PLACED" and "lot_ceiling" in rows[0]["why"]
    assert not [r for r in doc["decisions"] if r["reason"] == ev.R_RISK_BUDGET]


def test_an_unshrunk_window_over_the_budget_is_deferred_with_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """2% at 100 oz: 0.59 lots, under the ceiling; 2,000 x 1.25 > 2,400 -> DEFERRED, risk_budget,
    with the evidence row v4 never wrote, and the window is not spent."""
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.02)
    venue = bg._Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == []
    (row,) = _decisions(doc)
    assert (row["outcome"], row["reason"]) == ("DEFERRED", ev.R_RISK_BUDGET)
    assert row["risk_usd"] == pytest.approx(2000.0)
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "afternoon" not in saved["windows"]


def test_the_evidence_ledger_holds_the_rail_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bg._sandbox(
        monkeypatch,
        tmp_path,
        guard=bg._guard(99_900.0),
        slip={"status": "MEASURED", "slip_points": 100_000.0, "n": 25},
    )
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    g.run(bg._Venue(equity=99_900.0), h._MT5(), armed=True)
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
    """At 0.71% of a fresh 100k day: 0.21 lots, need 2 x 710 + 2 x 24.13 x 21 = 2,433.5, which
    is under the 2,500 to today's floor but inside its last ROOM_MARGIN_USD. v4 sent it with 67
    USD to spare; v5 cuts the bracket until it clears the margin."""
    assert g.ROOM_MARGIN_USD == 100.0
    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.0071)
    venue = bg._Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    room = min(
        float(doc["guard_decision"]["room_to_daily_floor"]),
        float(doc["guard_decision"]["room_to_static_floor"]),
    )
    need0 = 2 * 710.0 + 2 * 24.13 * 21
    assert need0 <= room < need0 + g.ROOM_MARGIN_USD, (need0, room)
    (cut,) = bg._shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["unshrunk_lots"] == {"buy_stop": 0.21, "sell_stop": 0.21}
    sent = {side: lot for side, lot, _px in venue.sent}
    assert sent == {"buy": 0.20, "sell": 0.20}
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
    monkeypatch.setattr(g, "RISK_FRAC", 0.002)
    venue = _TenthLotVenue()
    doc = g.run(venue, h._MT5(), armed=True)
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
    monkeypatch.setattr(g, "RISK_FRAC", 0.002)
    venue = _TenthLotVenue(equity=91_100.0)
    doc = g.run(venue, h._MT5(), armed=True)
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
    doc = g.run(venue, h._MT5(), armed=True)
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


class _StampedVenue(bg._Venue):
    """An SDK handle carrying a FAKE account id as a string, and a server on its credentials."""

    class _StampApi(h._Api):
        acc_id = str(_FAKE_ID)

    _api = _StampApi()
    _creds = types.SimpleNamespace(server="FAKE-DEMO", username="nobody@example.invalid")


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
    assert ev.tradelocker_identity(venue) == (_FAKE_ID, "FAKE-DEMO")
    assert ev.account_key(venue) == _FAKE_KEY
    assert calls == [(_FAKE_ID, "FAKE-DEMO", False)], "int login, create=False"
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
    g.run(venue, h._MT5(), armed=True)
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
        (str(_FAKE_ID), _FAKE_ID),
        (_FAKE_ID, _FAKE_ID),
        (float(_FAKE_ID), _FAKE_ID),
        ("4818273x", None),
        (True, None),
        ("", None),
        (0, None),
    ],
)
def test_the_login_is_normalised_to_int(raw: Any, login: int | None) -> None:
    class _V:
        _api = types.SimpleNamespace(acc_id=raw)

    ident = ev.tradelocker_identity(_V())
    assert (ident[0] if ident else None) == login
    if ident:
        assert ident[1] == "tradelocker"


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
