"""E8 gold: a stand-down reaches resting legs, and a bracket must fit the floor and the cap.

1. On a pass where `e8_guard.assess(...).may_open` is False (STOOD_DOWN, CAPPED, BREACHED,
   PASSED) this lane cancels its own journalled entry orders still resting, so a twin placed
   before the verdict cannot fill after it. Filled positions, their stops and orders the lane did
   not send are never touched; a failed cancel is logged, never raised, and retried next pass.
2. Both legs' risk to their stops plus ONE leg's slip in POINTS at the lot sent (measured p95 once
   20 stop exits exist, else 24.13) must fit the nearer of today's and the static floor; a bracket
   that does not is SHRUNK to fit, and skipped (with a row) only under the venue minimum.
3. A target past the daily profit cap headroom is shrunk to fit it, never refused whole.

The fixture is test_e8_gold_guard_and_open_risk's: the afternoon window is due at 17:30 with a
33.5-point stop and a 67-point target, 500 USD of risk -> 0.14 lots at a 100 oz contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_e8_gold_guard_and_open_risk as h  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402

#: The journal row of a placed leg, exactly as it was before these rails existed.
_SENT_KEYS = {
    "at",
    "window",
    "side",
    "price",
    "sl",
    "tp",
    "lot",
    "stop_dist",
    "risk_usd",
    "sizing",
    "risk_frac",
    "risk_source",
    "armed",
    "status",
    "order_id",
}


class _Venue(h._Venue):
    """The shared fake, with resting orders the lane can cancel and an armed send."""

    def __init__(
        self,
        *,
        equity: float = 100_000.0,
        resting: list[int] | None = None,
        cancel_fails: int = 0,
        cancel_raises: bool = False,
    ) -> None:
        super().__init__(equity=equity)
        self.sent: list[tuple[str, float, float]] = []
        self.resting = list(resting or [])
        self.cancelled: list[int] = []
        self._fails = cancel_fails
        self._cancel_raises = cancel_raises

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [{"id": oid, "stopPrice": 4250.0} for oid in self.resting]

    def place_stop(
        self, symbol: str, side: str, lot: float, *, price: float, stop: float, take_profit: float
    ) -> int:
        self.sent.append((side, float(lot), float(price)))
        return 7000 + len(self.sent)

    def cancel(self, order_id: int) -> bool:
        if self._fails > 0:
            self._fails -= 1
            if self._cancel_raises:
                raise ConnectionError("venue answered with an HTML page")
            return False
        self.cancelled.append(int(order_id))
        self.resting.remove(int(order_id))
        return True


def _guard(
    equity: float = 100_000.0, *, day_start: float = 100_000.0, stood_down: bool = False
) -> dict[str, Any]:
    return {
        "day": e8_guard.server_day(),
        "day_start": day_start,
        "peak_equity": max(equity, day_start),
        "stood_down": stood_down,
    }


def _sandbox(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    guard: dict[str, Any] | None = None,
    slip: Any = None,
) -> Path:
    h._sandbox(monkeypatch, tmp_path, guard=guard)
    monkeypatch.setattr(g, "GOLD_MAX_LOT_FILE", tmp_path / "E8_GOLD_MAX_LOT.json")
    p = tmp_path / "E8_GOLD_SLIP.json"
    if slip is not None:
        p.write_text(slip if isinstance(slip, str) else json.dumps(slip), encoding="utf-8")
    monkeypatch.setattr(g, "BRACKET_SLIP_FILE", p)
    monkeypatch.setattr(g, "STOP_EXITS", tmp_path / "e8_gold_stop_exits.jsonl")
    return p


def _journal(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "intents.json"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _rail_skips(doc: dict[str, Any], rail: str) -> list[dict[str, Any]]:
    return [s for s in doc["skipped"] if s.get("rail") == rail]


# ------------------------------------------------------------- unchanged when nothing binds


def test_placement_is_unchanged_when_no_rail_binds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 2 x 500 + 24.13 x 0.14 x 100 = 1,338 <= 2,500; the 938 USD target is inside the 2,000 cap.
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert sorted(venue.sent) == [("buy", 0.14, 4310.0), ("sell", 0.14, 4290.0)]
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    assert "shrunk" not in doc and not [s for s in doc["skipped"] if s.get("rail")]
    assert not [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert venue.cancelled == []
    assert doc["bracket_slip"]["slip_points"] == g.DEFAULT_SLIP_POINTS
    rows = _journal(tmp_path)
    assert [r["status"] for r in rows] == ["SENT", "SENT"]
    assert all(set(r) == _SENT_KEYS for r in rows), [sorted(r) for r in rows]


# ------------------------------------------------------------- rule 2: the floor, in points


def _shrinks(doc: dict[str, Any], rail: str) -> list[dict[str, Any]]:
    return [x for x in doc.get("shrunk") or [] if x["rail"] == rail]


def test_slip_is_one_legs_points_at_the_lot_sent_not_r() -> None:
    risk = {"buy_stop": 950.0, "sell_stop": 950.0}
    lots = {"buy_stop": 0.28, "sell_stop": 0.28}
    assert g.bracket_floor_need(risk, lots, 24.13, 100.0) == pytest.approx(1900 + 24.13 * 28)
    # The same 24.13 points weighs the same dollars at a 13-point or a 110-point stop.
    assert g.bracket_floor_need(
        {"buy_stop": 0.0}, {"buy_stop": 0.5}, 24.13, 100.0
    ) == pytest.approx(24.13 * 50)


def test_max_asia_risk_on_a_fresh_day_is_shrunk_a_step_to_fit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 0.95%: 2 x 950 + 24.13 x 28 = 2,576 > 2,500 -> one lot L = 2,500 / (100 x (67 + 24.13))
    # = 0.274 -> 0.27 on both legs. The 1,809 USD target fits the cap.
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.27, 4310.0), ("sell", 0.27, 4290.0)]
    (cut,) = _shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["unshrunk_lots"] == {"buy_stop": 0.28, "sell_stop": 0.28}
    assert cut["room_to_floor"] == pytest.approx(2500.0)
    assert not _shrinks(doc, g.PROFIT_CAP_RAIL)


def test_a_down_day_shrinks_both_legs_to_fit_and_bills_the_cut(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Down 100: 2,400 of room. 2 x 949.05 + 24.13 x 28 = 2,574 -> L = 2,400 / 9,113 = 0.263 ->
    # 0.26 on both legs, 871 USD a leg; 2 x 871 + 24.13 x 26 = 2,369 <= 2,400.
    _sandbox(monkeypatch, tmp_path, guard=_guard(99_900.0))
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert sorted(venue.sent) == [("buy", 0.26, 4310.0), ("sell", 0.26, 4290.0)]
    (cut,) = _shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["reason"] == g.DAILY_FLOOR_REASON
    assert cut["slip_points"] == g.DEFAULT_SLIP_POINTS
    assert cut["room_to_floor"] == pytest.approx(2400.0)
    assert cut["risk_usd"] == pytest.approx(871.0)
    assert cut["missed_growth_risk_usd"] == pytest.approx(938.0 - 871.0)
    assert 2 * 871.0 + 24.13 * 26 <= 2400.0
    rows = _journal(tmp_path)
    (billed,) = [r for r in rows if r.get("rail") == g.DAILY_FLOOR_RAIL]
    assert billed["status"] == "RAIL_SHRUNK" and billed.get("order_id") is None
    sent = [r for r in rows if r["status"] == "SENT"]
    assert all(
        r["risk_usd"] == 871.0
        and r["shrunk"] == {"unshrunk_lot": 0.28, "by": [g.DAILY_FLOOR_REASON]}
        for r in sent
    )
    assert "MISSED GROWTH" in (tmp_path / "log.json").read_text(encoding="utf-8")
    again = g.run(venue, h._MT5(), armed=True)
    assert len(venue.sent) == 2 and "shrunk" not in again
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg

    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    (line,) = mg.published_e8_gold_lines()["lines"]
    assert line["rail"] == g.DAILY_FLOOR_RAIL and line["n_shrunk"] == 1
    assert line["cost"]["risk_withheld_usd"] == pytest.approx(67.0)
    assert line["saving"]["verdict"] == mg.UNMEASURED


def test_the_floor_fit_respects_the_static_floor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Day started 91,000, equity 90,900: 2,175 to today's floor but only 900 to the static
    # 90,000. 2 x 454.5 + 24.13 x 13 = 1,223 > 900 -> L = 900 / 9,113 = 0.099 -> 0.09.
    _sandbox(monkeypatch, tmp_path, guard=_guard(90_900.0, day_start=91_000.0))
    venue = _Venue(equity=90_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert sorted(venue.sent) == [("buy", 0.09, 4310.0), ("sell", 0.09, 4290.0)]
    (cut,) = _shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert cut["room_to_floor"] == pytest.approx(900.0)


def test_a_bracket_that_cannot_fit_above_the_venue_minimum_is_skipped_with_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(
        monkeypatch,
        tmp_path,
        guard=_guard(99_900.0),
        slip={"status": "MEASURED", "slip_points": 100_000.0, "n": 25},
    )
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["bracket_slip"]["slip_points"] == 100_000.0
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = _rail_skips(doc, g.DAILY_FLOOR_RAIL)
    assert "venue minimum" in skip["why"] and skip["reason"] == g.DAILY_FLOOR_REASON
    assert skip["missed_growth_risk_usd"] == pytest.approx(949.05)
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.DAILY_FLOOR_RAIL]
    assert row["status"] == "RAIL_BLOCKED"
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["windows"]["afternoon"]["skipped"] == g.DAILY_FLOOR_RAIL
    again = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and not _rail_skips(again, g.DAILY_FLOOR_RAIL)


def test_floor_fit_lots_is_pure() -> None:
    q = lambda x: float(int(x * 100 + 1e-9)) / 100  # noqa: E731 -- floor to a 0.01 step
    both = {"buy_stop": 33.5, "sell_stop": 33.5}
    fit, why = g.floor_fit_lots(
        {"buy_stop": 0.28, "sell_stop": 0.28},
        both,
        slip_points=24.13,
        room=2400.0,
        contract_size=100.0,
        min_lot=0.01,
        quantise=q,
    )
    assert why is None and fit == {"buy_stop": 0.26, "sell_stop": 0.26}
    fit, why = g.floor_fit_lots(
        {"buy_stop": 0.10},
        {"buy_stop": 33.5},
        slip_points=24.13,
        room=2400.0,
        contract_size=100.0,
        min_lot=0.01,
        quantise=q,
    )
    assert fit == {"buy_stop": 0.10}, "a leg is never made bigger"
    fit, why = g.floor_fit_lots(
        {"buy_stop": 0.28},
        {"buy_stop": 33.5},
        slip_points=24.13,
        room=40.0,
        contract_size=100.0,
        min_lot=0.01,
        quantise=q,
    )
    assert fit is None and "venue minimum" in str(why)


def test_a_shrunk_leg_is_budgeted_against_the_floor_at_its_shrunk_risk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 949 USD at a 10 oz contract needs 2.83 lots; the ceiling sends 0.75 (251.25 USD a leg):
    # 2 x 251.25 + 24.13 x 7.5 = 683.5 fits the 2,400.
    _sandbox(monkeypatch, tmp_path, guard=_guard(99_900.0))
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    monkeypatch.setattr(
        venue, "details", lambda symbol: {"contractSize": 10.0, "currency": "USD", "lotStep": 0.01}
    )
    doc = g.run(venue, h._MT5(), armed=True)
    assert not _shrinks(doc, g.DAILY_FLOOR_RAIL)
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)]
    assert _shrinks(doc, g.LOT_CEILING_RAIL)[0]["risk_usd"] == pytest.approx(251.25)


# ------------------------------------------------------------- the slip: points, measured


def test_the_lanes_measured_slip_replaces_the_default_at_20_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(
        monkeypatch,
        tmp_path,
        guard=_guard(99_900.0),
        slip={"status": "MEASURED", "slip_points": 0.0, "n": 20},
    )
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["bracket_slip"]["slip_points"] == 0.0
    assert doc["bracket_slip"]["source"] == "E8_GOLD_SLIP.json (p95 of 20 stop exits)"
    assert not _shrinks(doc, g.DAILY_FLOOR_RAIL)  # 2 x 949 = 1,898 <= 2,400
    assert len(venue.sent) == 2


@pytest.mark.parametrize(
    "doc",
    [
        {"status": "MEASURED", "slip_points": 3.0, "n": 19},
        {"status": "UNMEASURED", "n": 0, "slip_points": 0.01},
        {"status": "MEASURED", "slip_points": -1.0, "n": 30},
        {"status": "MEASURED", "slip_points": "3", "n": 30},
        {"status": "MEASURED", "slip_points": True, "n": 30},
        {"status": "MEASURED", "slip": 0.3, "n": 30},
        {"status": "MEASURED", "slip_points": 3.0, "n": True},
        [1.0],
        "NaN",
        '{"status": "MEASURED", "slip_points": Infinity, "n": 30}',
        "{ not json",
    ],
)
def test_an_unusable_slip_file_keeps_the_points_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, doc: Any
) -> None:
    _sandbox(monkeypatch, tmp_path, slip=doc)
    slip, src = g.bracket_slip()
    assert slip == g.DEFAULT_SLIP_POINTS and src.startswith("default DEFAULT_SLIP_POINTS")


def test_the_committed_slip_file_is_unmeasured_in_points_and_says_what_is_missing() -> None:
    doc = json.loads((_DESK / "data" / "E8_GOLD_SLIP.json").read_text(encoding="utf-8"))
    assert doc["status"] == "UNMEASURED" and doc["n"] == 0 and doc["unit"] == "points"
    assert "slip_points" not in doc and "slip" not in doc
    assert doc["measured_at"] == "2026-10-20" and doc["sources"] and doc["missing"]
    assert g.bracket_slip(_DESK / "data" / "E8_GOLD_SLIP.json")[0] == g.DEFAULT_SLIP_POINTS


def test_the_slip_is_the_p95_of_stop_exit_fill_through_in_points() -> None:
    from prop import e8_gold_slip as es

    assert es.exit_slip_points({"side": "sell", "stop": 4100.0, "fill": 4100.0}) == 0.0
    # 2026-09-24: a short's protective BUY stop at 4259.78 filled at 4283.91 -> 24.13 points.
    assert es.exit_slip_points({"side": "buy", "stop": 4259.78, "fill": 4283.91}) == pytest.approx(
        24.13
    )
    assert es.exit_slip_points({"side": "sell", "stop": 4100.0, "fill": 4097.5}) == pytest.approx(
        2.5
    )
    # An entry that filled 2 points through its trigger adds its own fill-through.
    assert es.exit_slip_points(
        {
            "side": "sell",
            "stop": 4100.0,
            "fill": 4100.0,
            "entry_side": "buy",
            "trigger": 4130.0,
            "entry": 4132.0,
        }
    ) == pytest.approx(2.0)
    assert es.exit_slip_points({"side": "sell", "stop": 4100.0}) is None
    rows = [{"side": "sell", "stop": 4100.0, "fill": 4100.0 - 0.5 * k} for k in range(20)]
    doc = es.measure(rows, sources=["test"], measured_at="2026-10-20")
    assert doc["status"] == "MEASURED" and doc["n"] == 20 and doc["unit"] == "points"
    assert doc["slip_points"] == pytest.approx(
        es.quantile([0.5 * k for k in range(20)], 0.95), abs=1e-4
    )
    few = es.measure(rows[:19], sources=["test"], measured_at="2026-10-20")
    assert few["status"] == "UNMEASURED" and "slip_points" not in few
    assert few["provisional_p95_points"] > 0 and few["missing"]


def test_a_measured_slip_file_is_read(tmp_path: Path) -> None:
    from prop import e8_gold_slip as es

    rows = [{"side": "buy", "stop": 4000.0, "fill": 4000.0 + k} for k in range(25)]
    path = tmp_path / "E8_GOLD_SLIP.json"
    es.write(es.measure(rows, sources=["t"], measured_at="2026-10-20"), path)
    slip, src = g.bracket_slip(path)
    assert slip == pytest.approx(es.quantile([float(k) for k in range(25)], 0.95), abs=1e-4)
    assert src == "E8_GOLD_SLIP.json (p95 of 25 stop exits)"


def test_the_pass_journals_our_stop_exits_and_remeasures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from prop import e8_gold_slip as es

    monkeypatch.setattr(g, "STOP_EXITS", tmp_path / "exits.jsonl")
    monkeypatch.setattr(g, "BRACKET_SLIP_FILE", tmp_path / "E8_GOLD_SLIP.json")
    own = {9001: {"window": "asia", "side": "sell_stop"}}
    hist = [
        {
            "id": 9001,
            "status": "Filled",
            "positionId": 77,
            "side": "sell",
            "stopPrice": 4290.0,
            "avgPrice": 4290.0,
        },  # our entry
        {
            "id": 9100,
            "status": "Filled",
            "positionId": 77,
            "side": "buy",
            "stopPrice": 4259.78,
            "avgPrice": 4283.91,
        },  # its stop exit
        {
            "id": 9101,
            "status": "Filled",
            "positionId": 77,
            "side": "buy",
            "price": 4200.0,
            "avgPrice": 4200.0,
        },  # a target: no stop
        {
            "id": 9200,
            "status": "Filled",
            "positionId": 88,
            "side": "buy",
            "stopPrice": 4300.0,
            "avgPrice": 4310.0,
        },
    ]  # not our position
    exits = g.stop_exits_from_history(hist, {9001: 77, 9200: 88}, own)
    assert [(e["order_id"], e["side"], e["stop"], e["fill"]) for e in exits] == [
        (9100, "buy", 4259.78, 4283.91)
    ]
    now = e8_guard.datetime.now(e8_guard.UTC)
    assert g._record_stop_exits(exits, now=now) == 1
    assert g._record_stop_exits(exits, now=now) == 0, "an exit is journalled once"
    pub = g.publish_slip(now=now)
    doc = json.loads((tmp_path / "E8_GOLD_SLIP.json").read_text(encoding="utf-8"))
    assert doc["status"] == "UNMEASURED" and doc["n"] == 1
    assert doc["provisional_p95_points"] == pytest.approx(24.13)
    assert doc["windows"]["asia"]["status"] == "UNMEASURED"
    assert doc["windows"]["asia"]["n"] == 1
    assert doc["windows"]["asia"]["max_points"] == pytest.approx(24.13)
    assert pub["status"] == "UNMEASURED" and pub["windows"] == doc["windows"]
    assert pub["guard_slip_points"] == g.DEFAULT_SLIP_POINTS
    assert es.read_stop_exits(tmp_path / "exits.jsonl")[0]["order_id"] == 9100


def test_an_entrys_fill_through_past_its_trigger_is_carried_with_the_exit() -> None:
    own = {9001: {"window": "asia", "side": "sell_stop", "price": 4290.0}}
    hist = [
        {
            "id": 9001,
            "status": "Filled",
            "positionId": 77,
            "side": "sell",
            "stopPrice": 4290.0,
            "avgPrice": 4288.0,
        },  # entry 2 pts through
        {
            "id": 9100,
            "status": "Filled",
            "positionId": 77,
            "side": "buy",
            "stopPrice": 4320.0,
            "avgPrice": 4321.5,
        },
    ]  # stop 1.5 through
    (row,) = g.stop_exits_from_history(hist, {9001: 77}, own)
    assert (row["window"], row["entry_side"], row["trigger"], row["entry"]) == (
        "asia",
        "sell",
        4290.0,
        4288.0,
    )
    from prop import e8_gold_slip as es

    assert es.exit_slip_points(row) == pytest.approx(3.5)


def test_every_pass_publishes_the_slip_per_window_in_points(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    doc = g.run(_Venue(), h._MT5(), armed=True)
    pub = doc["slip"]
    assert pub["status"] == "UNMEASURED" and pub["n"] == 0 and pub["unit"] == "points"
    assert pub["guard_slip_points"] == g.DEFAULT_SLIP_POINTS == 24.13
    assert {"measured_at", "sources", "windows"} <= set(pub)
    written = json.loads((tmp_path / "E8_GOLD_SLIP.json").read_text(encoding="utf-8"))
    assert written["status"] == "UNMEASURED" and written["windows"] == pub["windows"]
    on_disk = json.loads(g.OUT.read_text(encoding="utf-8"))
    assert on_disk["slip"]["status"] == "UNMEASURED"


def test_a_failing_slip_publication_never_blocks_placement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from prop import e8_gold_slip as es

    def boom(**_: Any) -> dict[str, Any]:
        raise OSError("disk full")

    monkeypatch.setattr(es, "refresh", boom)
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.14, 4310.0), ("sell", 0.14, 4290.0)]
    assert doc["slip"]["status"] == "UNMEASURED" and "disk full" in doc["slip"]["error"]
    assert doc["slip"]["guard_slip_points"] == g.DEFAULT_SLIP_POINTS


def test_a_windows_own_measured_slip_is_used_for_that_window_only(tmp_path: Path) -> None:
    from prop import e8_gold_slip as es

    rows = [
        {"side": "buy", "stop": 4000.0, "fill": 4001.0, "window": "asia"} for _ in range(20)
    ] + [{"side": "buy", "stop": 4000.0, "fill": 4030.0, "window": "afternoon"}]
    path = tmp_path / "E8_GOLD_SLIP.json"
    es.write(es.measure(rows, sources=["t"], measured_at="2026-10-20"), path)
    assert g.bracket_slip(path, window="asia")[0] == pytest.approx(1.0)
    pooled = g.bracket_slip(path, window="afternoon")[0]
    assert pooled == g.bracket_slip(path)[0]


# ------------------------------------------------------------- rule 3: the daily profit cap


def test_a_target_past_the_profit_cap_headroom_is_shrunk_to_fit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Up 1,500 today: 500 of counted profit left. 0.15 lots x 67 points x 100 oz = 1,005 USD;
    # the lot is cut to 500 / 6,700 = 0.0746 -> 0.07, a 469 USD target.
    _sandbox(monkeypatch, tmp_path, guard=_guard(101_500.0))
    venue = _Venue(equity=101_500.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert sorted(venue.sent) == [("buy", 0.07, 4310.0), ("sell", 0.07, 4290.0)]
    (cut,) = _shrinks(doc, g.PROFIT_CAP_RAIL)
    cap = e8_guard.START_BALANCE * e8_guard.DAILY_PROFIT_CAP
    assert cut["profit_cap_headroom_usd"] == pytest.approx(cap - 1500.0)
    assert cut["reason"] == g.PROFIT_CAP_REASON and "daily profit cap" in cut["why"]
    assert cut["missed_growth_risk_usd"] == pytest.approx(33.5 * 100 * (0.15 - 0.07))
    assert g.leg_target_profit(h._MT5 and {"price": 4310.0, "tp": 4377.0}, 0.07, 100.0) <= 500.0
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.PROFIT_CAP_RAIL]
    assert row["status"] == "RAIL_SHRUNK"


def test_a_headroom_too_small_for_the_minimum_lot_skips_with_a_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Up 1,995: 5 USD left, which 0.01 lots (67 USD of target) cannot fit.
    _sandbox(monkeypatch, tmp_path, guard=_guard(101_995.0))
    venue = _Venue(equity=101_995.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = _rail_skips(doc, g.PROFIT_CAP_RAIL)
    assert skip["reason"] == g.PROFIT_CAP_REASON and "venue minimum" in skip["why"]
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.PROFIT_CAP_RAIL]
    assert row["status"] == "RAIL_BLOCKED"


def test_the_headroom_is_the_guards_cap_less_todays_profit() -> None:
    cap = e8_guard.START_BALANCE * e8_guard.DAILY_PROFIT_CAP
    up = e8_guard.assess(101_200.0, state=_guard(101_200.0), persist=False)
    down = e8_guard.assess(99_500.0, state=_guard(99_500.0), persist=False)
    assert up.profit_cap_headroom == pytest.approx(cap - 1200.0)
    assert down.profit_cap_headroom == pytest.approx(cap), "a losing day leaves the whole cap"
    caps = g.profit_fit_caps(
        {"buy_stop": {"price": 4310.0, "tp": 4377.0}}, ["buy_stop"], 800.0, 100.0
    )
    assert caps["buy_stop"] == pytest.approx(800.0 / 6700.0)


def test_an_unmeasurable_rail_defers_and_never_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())

    def boom(*a: Any, **k: Any) -> Any:
        raise ArithmeticError("no figures")

    monkeypatch.setattr(g, "bracket_floor_need", boom)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and "bracket rails unmeasurable" in " ".join(
        str(s.get("why")) for s in doc["skipped"]
    )
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "afternoon" not in saved["windows"], "a deferral is not a spent window"


# ------------------------------------------------------------- rule 1: stand-down cancels

_OWN = (9001, 9002)
_PROTECTIVE, _HUMAN = 555, 777


def _resting_bracket(tmp_path: Path) -> None:
    """The afternoon bracket placed at 17:00 and still resting, journalled as this lane's."""
    legs = {
        "buy_stop": {"id": _OWN[0], "price": 4310.0, "sl": 4276.5, "tp": 4377.0, "lot": 0.14},
        "sell_stop": {"id": _OWN[1], "price": 4290.0, "sl": 4323.5, "tp": 4223.0, "lot": 0.14},
    }
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    state["windows"]["afternoon"] = {
        "placed_hour": 17.0,
        "orders": legs,
        "position_id": None,
        "shadow": False,
    }
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with (tmp_path / "intents.json").open("a", encoding="utf-8") as fh:
        for side, leg in legs.items():
            fh.write(
                json.dumps(
                    {
                        "at": "2026-10-15T17:00:00+00:00",
                        "window": "afternoon",
                        "side": side,
                        "status": "SENT",
                        "order_id": leg["id"],
                        "risk_usd": 500.0,
                        **{k: leg[k] for k in ("price", "sl", "tp", "lot")},
                    }
                )
                + "\n"
            )


@pytest.mark.parametrize(
    ("guard", "equity", "verdict"),
    [
        (_guard(stood_down=True), 100_000.0, "STOOD_DOWN"),
        (_guard(102_050.0), 102_050.0, "CAPPED"),
        (_guard(97_400.0), 97_400.0, "BREACHED"),
    ],
)
def test_a_refusing_verdict_cancels_our_resting_legs_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    guard: dict[str, Any],
    equity: float,
    verdict: str,
) -> None:
    _sandbox(monkeypatch, tmp_path, guard=guard)
    _resting_bracket(tmp_path)
    venue = _Venue(equity=equity, resting=[*_OWN, _PROTECTIVE, _HUMAN])
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == verdict
    assert sorted(venue.cancelled) == list(_OWN)
    assert venue.resting == [_PROTECTIVE, _HUMAN], "a stop or a human's order is never touched"
    acts = [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert sorted(a["order_id"] for a in acts) == list(_OWN)
    assert all(a["ok"] and a["verdict"] == verdict for a in acts)
    # Management on the same pass does not try the same ids again.
    assert not [
        a
        for a in doc["actions"]
        if a["act"] in ("oco_cancel", "ttl_cancel", "eod_cancel", "stale_cancel")
    ]
    assert venue.sent == []


def test_an_ok_verdict_leaves_the_resting_bracket_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    _resting_bracket(tmp_path)
    venue = _Venue(resting=[*_OWN, _PROTECTIVE, _HUMAN])
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert venue.cancelled == []
    assert not [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]


@pytest.mark.parametrize("raises", [True, False])
def test_a_failed_cancel_is_logged_never_raised_and_retried_next_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raises: bool
) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard(stood_down=True))
    _resting_bracket(tmp_path)
    venue = _Venue(resting=[*_OWN], cancel_fails=2, cancel_raises=raises)
    doc = g.run(venue, h._MT5(), armed=True)
    acts = [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert len(acts) == 2 and not any(a["ok"] for a in acts)
    assert all("tried again next pass" in a["why"] for a in acts)
    assert venue.resting == list(_OWN)
    assert f"{g.STAND_DOWN_CANCEL} FAILED" in (tmp_path / "log.json").read_text(encoding="utf-8")
    again = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.cancelled) == list(_OWN) and venue.resting == []
    assert all(a["ok"] for a in again["actions"] if a["act"] == g.STAND_DOWN_CANCEL)


def test_a_filled_entry_is_not_a_resting_leg() -> None:
    own = {9001: {"window": "afternoon"}, 9002: {"window": "afternoon"}}
    assert g.stand_down_cancels({9001, 9002, 555}, {9001: 42}, own) == [9002]
    assert g.stand_down_cancels({555, 777}, {}, own) == []
