"""CERTIFIED XAUUSD SLEEVES ON E8 (prop/e8_executor.GOLD_SLEEVES, 2026-11-25).

Every XAUUSD sleeve used to be refused as OWNED_BY_GOLD_LANE, so the certified gold sleeves that
FTMO trades (#1323) had no E8 route. A sleeve leg is now placed only under the cross-account gold
direction lock, never while this account rests a gold entry on the other side, and fails closed
on anything unreadable. Stub venue; the OCO's own behaviour is pinned in test_gold_oco.py.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import gold_oco as oco  # noqa: E402
from prop import e8_executor as ex  # noqa: E402
from prop import e8_guard  # noqa: E402

NOW = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)
IID = 4242


class Venue:
    def __init__(self, orders: list[dict[str, Any]] | None = None) -> None:
        self._orders = orders or []

    def positions(self) -> list[dict[str, Any]]:
        return []

    def orders(self) -> list[dict[str, Any]]:
        return list(self._orders)

    def instrument_id(self, sym: str) -> int:
        return IID


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {"gate": []}
    monkeypatch.setattr(oco, "tradelocker_oco_key", lambda venue: "tl:key")

    def sync_lane(lane: str, key: str, rows: Any, *, date: str, holder: str) -> dict[str, Any]:
        seen["sync"] = (lane, key, date, holder)
        rows()
        return {"published": True, "claims": []}

    def gate(lane: str, side: str, *, key: str, date: str) -> Any:
        seen["gate"].append((lane, side, key, date))
        return SimpleNamespace(allowed=seen.get("allow", True), why="gold OCO: refused")

    monkeypatch.setattr(oco, "sync_lane", sync_lane)
    monkeypatch.setattr(oco, "gate", gate)
    return seen


def test_the_flag_is_on_and_the_revert_is_the_old_refusal() -> None:
    assert ex.GOLD_SLEEVES is True
    src = Path(ex.__file__).read_text(encoding="utf-8")
    assert 'if str(sym).upper() == "XAUUSD" and not GOLD_SLEEVES:' in src
    assert '"OWNED_BY_GOLD_LANE"' in src


def test_a_clean_account_is_judged_by_the_direction_lock_on_the_e8_day(
        wired: dict[str, Any]) -> None:
    why, ctx = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="e8_executor:s")
    assert why is None
    assert ctx == ("tl:key", e8_guard.server_day(NOW))
    assert wired["sync"][0] == "e8" and wired["sync"][2] == e8_guard.server_day(NOW)
    assert wired["gate"] == [("e8", "buy", "tl:key", e8_guard.server_day(NOW))]


def test_the_direction_lock_refusal_is_returned(wired: dict[str, Any]) -> None:
    wired["allow"] = False
    why, _ = ex._gold_sleeve_refusal(Venue(), "sell", now=NOW, holder="h")
    assert why == "gold OCO: refused"


@pytest.mark.parametrize("sides", [("buy", "sell"), ("buy",), ("sell",)])
def test_any_resting_gold_entry_keeps_the_window_slot(wired: dict[str, Any],
                                                      sides: tuple[str, ...]) -> None:
    """Audit SF1: an opposite leg would fill against the sleeve, a same-side one stack beside it."""
    legs = [{"id": 10 + k, "side": sd, "type": "stop", "tradableInstrumentId": IID}
            for k, sd in enumerate(sides)]
    why, _ = ex._gold_sleeve_refusal(Venue(legs), "buy", now=NOW, holder="h")
    assert why is not None and "rests a gold entry" in why
    assert wired["gate"] == []


def test_an_xau_position_in_the_locked_reading_refuses(wired: dict[str, Any]) -> None:
    """Audit MF2: an E8-Gold fill or another sleeve's send since the pass-start snapshot."""
    class Held(Venue):
        def positions(self) -> list[dict[str, Any]]:
            return [{"id": 99, "side": "buy", "tradableInstrumentId": IID}]
    why, _ = ex._gold_sleeve_refusal(Held(), "buy", now=NOW, holder="h")
    assert why is not None and "already holds XAU" in why and "99" in why
    assert wired["gate"] == []


def test_a_send_marks_the_instrument_open_for_the_rest_of_the_pass() -> None:
    """Audit MF2: the next sleeve on the instrument in the same pass reads ALREADY_OPEN."""
    src = Path(ex.__file__).read_text(encoding="utf-8")
    sent = src.index('row["status"] = "SENT"')
    assert "open_keys.add((int(iid), side))" in src[sent:sent + 900]
    assert "if any(k[0] == int(iid) for k in open_keys):" in src


def test_an_unnamed_account_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(venue: Any) -> str:
        raise oco.IdentityUnavailable("no keyed identity")
    monkeypatch.setattr(oco, "tradelocker_oco_key", boom)
    why, ctx = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="h")
    assert why is not None and "fail closed" in why and ctx is None


def test_an_unpublished_gold_state_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oco, "tradelocker_oco_key", lambda venue: "tl:key")
    monkeypatch.setattr(oco, "sync_lane",
                        lambda *a, **k: {"published": False, "why": "lock held"})
    monkeypatch.setattr(oco, "gate", lambda *a, **k: pytest.fail("gate read without a publish"))
    why, _ = ex._gold_sleeve_refusal(Venue(), "buy", now=NOW, holder="h")
    assert why is not None and "not republished" in why and "fail closed" in why


def test_the_republish_after_a_send_reports_what_happened(wired: dict[str, Any]) -> None:
    out = ex._gold_republish(Venue(), ("tl:key", "2026-11-25"), holder="h")
    assert out["published"] is True and wired["sync"][:3] == ("e8", "tl:key", "2026-11-25")


def test_a_banned_xau_sleeve_closes_nothing_by_instrument(monkeypatch: pytest.MonkeyPatch,
                                                         tmp_path: Path) -> None:
    """Audit MF1: E8-Gold's positions share XAUUSD; a banned gold sleeve writes an alert row."""
    import json

    class Decision:
        flatten, may_open = False, True
        verdict = SimpleNamespace(value="OK")
        why = "ok"

        def as_dict(self) -> dict[str, Any]:
            return {"equity": 100_000.0}

    class Live:
        def __init__(self) -> None:
            self._by_key = {"XAUUSD": IID}
            self.closes: list[int] = []

        def account(self) -> dict[str, float]:
            return {"equity": 100_000.0}

        def positions(self) -> list[dict[str, Any]]:
            return [{"id": 5, "side": "buy", "tradableInstrumentId": IID}]

        def orders(self) -> list[dict[str, Any]]:
            return []

        def close(self, pid: int) -> bool:
            self.closes.append(int(pid))
            return True

    book = tmp_path / "E8_BOOK.json"
    book.write_text(json.dumps({"generated_utc": NOW.isoformat(), "risk_frac": 0.0015,
                                "sleeves": [{"symbol": "XAUUSD", "family": "discovered"}]}),
                    encoding="utf-8")
    import real_edge
    from mt5desk import cross_account as xa
    from mt5desk import order_door
    monkeypatch.setattr(ex, "BOOK", book)
    monkeypatch.setattr(e8_guard, "assess", lambda equity, now=None: Decision())
    monkeypatch.setattr(ex, "manage_breakeven", lambda *a, **k: [])
    monkeypatch.setattr(ex, "_family_banned", lambda fam: True)
    monkeypatch.setattr(ex, "_record", lambda *a, **k: None)
    monkeypatch.setattr(ex, "outstanding_stop_risk", lambda *a, **k: (0.0, ""))
    monkeypatch.setattr(real_edge, "load", lambda *a, **k: ({}, "ok"))
    monkeypatch.setattr(xa, "publish_under_lock", lambda *a, **k: None)
    monkeypatch.setattr(order_door, "guard_venue", lambda venue, **k: venue)
    venue = Live()
    doc = ex.run(venue, armed=True, now=NOW, entry_enabled=True)
    rows = [r for r in doc["sleeves"] if r.get("symbol") == "XAUUSD"]
    assert rows and rows[0]["status"] == "BANNED_FAMILY"
    assert rows[0]["closed_positions"] == [] and "alert" in rows[0]
    assert venue.closes == []


def _run_to_the_fence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sym: str,
                      fusion_why: str | None, gold_why: str | None = None
                      ) -> tuple[list[dict[str, Any]], list[Any]]:
    """e8_executor.run driven to the placement lock with one certified sleeve on `sym`.
    Everything before the fence is stubbed to pass; the venue records any send."""
    import contextlib
    import json

    import pandas as pd
    import real_edge
    from mt5desk import cross_account as xa
    from mt5desk import families, kelly_sizing, order_door

    from libs.ops import new_risk_hold
    from prop import e8_book

    class Decision:
        flatten, may_open = False, True
        verdict = SimpleNamespace(value="OK")
        why = "ok"
        room_to_daily_floor = 2_500.0

        def as_dict(self) -> dict[str, Any]:
            return {"equity": 100_000.0}

    class Live:
        def __init__(self) -> None:
            self._by_key = {sym: IID}
            self._raw_api = object()
            self.sent: list[Any] = []

        def account(self) -> dict[str, float]:
            return {"equity": 100_000.0}

        def positions(self) -> list[dict[str, Any]]:
            return []

        def orders(self) -> list[dict[str, Any]]:
            return []

        def instrument_id(self, s: str) -> int:
            return IID

        def quote(self, s: str) -> tuple[float, float]:
            return 1.0000, 1.0001

        def place(self, *a: Any, **k: Any) -> int:
            self.sent.append(a)
            return 1

    idx = pd.date_range(end=NOW, periods=80, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    sig = SimpleNamespace(time=idx[-2], side=1, stop=0.99, target=1.02)
    book = tmp_path / "E8_BOOK.json"
    book.write_text(json.dumps({"generated_utc": NOW.isoformat(), "risk_frac": 0.0015,
                                "sleeves": [{"symbol": sym, "family": "fam", "key": "k",
                                             "risk_frac": 0.0015}]}), encoding="utf-8")
    cert_book = tmp_path / "CERT_BOOK_LIVE.json"
    cert_book.write_text(json.dumps({"excluded": {}}), encoding="utf-8")
    rows: list[dict[str, Any]] = []
    import admission_integrity
    monkeypatch.setattr(ex, "BOOK", book)
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", cert_book)
    monkeypatch.setattr(kelly_sizing, "load_cert_book", lambda *a, **k: {})
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls, *a, **k: None))
    monkeypatch.setattr(e8_guard, "assess", lambda equity, now=None: Decision())
    monkeypatch.setattr(ex, "manage_breakeven", lambda *a, **k: [])
    monkeypatch.setattr(ex, "_record", lambda row, *a, **k: rows.append(dict(row)))
    monkeypatch.setattr(ex, "outstanding_stop_risk", lambda *a, **k: (0.0, ""))
    monkeypatch.setattr(ex, "entry_doors", lambda *a, **k: ("", "", [], 1.0))
    monkeypatch.setattr(ex, "_frame", lambda *a, **k: frame)
    monkeypatch.setattr(ex, "_call_params", lambda *a, **k: {})
    from mt5desk import family_call
    monkeypatch.setattr(family_call, "certified_session_filter", lambda sigs, s: sigs)
    monkeypatch.setattr(family_call, "signal_reference_price",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stub")))
    monkeypatch.setattr(ex, "size_certified_entry",
                        lambda *a, **k: (0.1, "test", 150.0, None))
    monkeypatch.setattr(e8_book, "rollover_block", lambda *a, **k: None)
    monkeypatch.setattr(new_risk_hold, "reason", lambda *a, **k: None)
    monkeypatch.setattr(families, "get_family_func", lambda fam: (lambda f, **k: [sig]))
    monkeypatch.setattr(real_edge, "load", lambda *a, **k: ({}, "ok"))
    monkeypatch.setattr(real_edge, "doubt", lambda *a, **k: None)
    monkeypatch.setattr(order_door, "guard_venue", lambda venue, **k: venue)
    monkeypatch.setattr(xa, "publish_under_lock", lambda *a, **k: None)
    monkeypatch.setattr(xa, "publish_tradelocker", lambda *a, **k: None)
    monkeypatch.setattr(xa, "placement_lock",
                        lambda *a, **k: contextlib.nullcontext(True))
    monkeypatch.setattr(xa, "read_book", lambda acct, **k: ({}, None))
    monkeypatch.setattr(xa, "opposite_block", lambda *a, **k: fusion_why)
    monkeypatch.setattr(xa, "ftmo_block", lambda *a, **k: None)
    monkeypatch.setattr(ex, "_gold_sleeve_refusal",
                        lambda *a, **k: (gold_why, ("tl:key", "2026-11-25")))
    monkeypatch.setattr(ex, "_gold_republish", lambda *a, **k: {"published": True})
    venue = Live()
    doc = ex.run(venue, armed=True, now=NOW, entry_enabled=True)
    return [r for r in doc["sleeves"] if r.get("symbol") == sym], venue.sent


def test_a_non_gold_fenced_row_carries_the_cross_account_rail(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Audit r3: the non-gold fence row is RAIL_BLOCKED on cross_account_opposite, nothing sent."""
    rows, sent = _run_to_the_fence(monkeypatch, tmp_path, "EURUSD",
                                   "fusion holds the opposite side of EURUSD")
    assert rows and rows[0]["status"] == "RAIL_BLOCKED", rows
    assert rows[0]["rail"] == "cross_account_opposite"
    assert rows[0]["missed_growth_risk_usd"] > 0 and sent == []


def test_a_gold_lock_refusal_carries_the_gold_rail(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows, sent = _run_to_the_fence(monkeypatch, tmp_path, "XAUUSD", None,
                                   gold_why="gold OCO: refused")
    assert rows and rows[0]["status"] == "RAIL_BLOCKED", rows
    assert rows[0]["rail"] == oco.RAIL and sent == []


def test_an_unfenced_gold_sleeve_is_sent_and_marks_the_instrument_open(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows, sent = _run_to_the_fence(monkeypatch, tmp_path, "XAUUSD", None)
    assert rows and rows[0]["status"] == "SENT", rows
    assert len(sent) == 1 and rows[0]["gold_oco_republish"] == {"published": True}
