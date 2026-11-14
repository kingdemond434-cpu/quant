"""markout_v2: slip in R with PRICE units on both sides, one account and one row per position,
stale inputs never MEASURED, UNMEASURED never 0."""
from __future__ import annotations

import json

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import markout_v2 as m  # noqa: E402

AS_OF = datetime(2026, 10, 20, 18, tzinfo=UTC)
T = "2026-10-13T04:00:13+00:00"
LIVE = {"account": 1000001, "server": "Venue-Live", "account_kind": "live"}


def _intent(ticket: int, intended: float, sl: float, side: str = "buy",
            time: str | None = T, **kw: Any) -> dict[str, Any]:
    return {"ticket": ticket, "intended": intended, "sl": sl, "side": side, "time": time,
            "symbol": "XAUUSD", "sleeve": "gold_asia", **kw}


def _deal(ticket: int, entry: float, *, time: str = T, deal: int | None = None,
          volume: float = 0.01, **kw: Any) -> dict[str, Any]:
    return {"entry_order": ticket, "position_id": ticket, "entry_price": entry, "time": time,
            "symbol": "XAUUSD", "sleeve": "gold_asia", "deal": deal or ticket * 10,
            "volume": volume, "risk_quote": 0.087, **LIVE, **kw}


def _book(n: int, fill: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return ([_intent(i, 2000.0, 1990.0) for i in range(1, n + 1)],
            [_deal(i, fill) for i in range(1, n + 1)])


def test_slip_is_price_over_price_not_price_over_money() -> None:
    # The deal-200308589 shape: a 3.84 price slip, tiny risk_quote. markout.py read ~44R.
    rows, _ = m.fusion_rows([_intent(1, 2000.0, 1996.0, side="sell")], [_deal(1, 1996.16)],
                           AS_OF)
    assert rows[0]["slip_r"] == pytest.approx(0.96)


def test_direction_sign_convention() -> None:
    assert m.slip_r(2000.5, 2000.0, 1990.0, 1)[0] == pytest.approx(0.05)
    assert m.slip_r(1999.5, 2000.0, 2010.0, -1)[0] == pytest.approx(0.05)
    assert m.slip_r(1999.5, 2000.0, 1990.0, 1)[0] == pytest.approx(-0.05)


@pytest.mark.parametrize("fill,want,stop,d,why", [
    (2000.0, None, 1990.0, 1, "no_intended_price"),
    (2000.0, 2000.0, None, 1, "no_stop"),
    (None, 2000.0, 1990.0, 1, "no_fill"),
    (2000.0, 2000.0, 1990.0, 0, "no_direction"),
    (2000.0, 2000.0, 2000.0, 1, "zero_stop_distance"),
    (2000.0, 2000.0, 2000.0 - 1e-10, 1, "stop_below_floor"),
])
def test_missing_inputs_are_unmeasured_not_zero(fill: float | None, want: float | None,
                                                stop: float | None, d: int, why: str) -> None:
    assert m.slip_r(fill, want, stop, d) == (None, why)


def test_stop_floor_uses_the_intent_point() -> None:
    assert m.slip_r(1.0, 1.0, 0.99995, 1, point=0.0001) == (None, "stop_below_floor")
    assert m.slip_r(1.0, 1.0, 0.9998, 1, point=0.0001)[1] == "measured"


def test_mixed_ledger_is_refused() -> None:
    demo: dict[str, Any] = {"account": 1000002, "server": "Venue-Demo", "account_kind": "demo"}
    doc = m.build(AS_OF, fusion_intents=[_intent(1, 2000.0, 1990.0), _intent(2, 2000.0, 1990.0)],
                  fusion_deals=[_deal(1, 2000.5), _deal(2, 2000.5, **demo)],
                  e8_intents=[], e8_fills=None)
    f = doc["accounts"]["fusion"]
    assert f["status"] == m.MIXED and f["median_slip_r"] is None
    assert doc["e8_headroom_input"]["fusion_slip_r"] == m.UNMEASURED
    split = f["by_account"]
    assert len(split) == 2 and all(b["status"] != m.MIXED for b in split)
    assert sum(b["n_deals"] for b in split) == 2
    published = json.dumps(doc)
    for field in ('"login"', '"server"', '"account_key"', "Venue-Live", "Venue-Demo", "1000001"):
        assert field not in published, field
    assert {a["kind"] for a in f["accounts_in_ledger"]} == {"live", "demo"}


def test_unjoined_deals_are_counted() -> None:
    block, rows = m.fusion_block([_intent(1, 2000.0, 1990.0)],
                                 [_deal(1, 2000.5), _deal(99, 2000.5)], AS_OF)
    assert block["n_unjoined_deals"] == 1 and len(rows) == 1 and block["n_deals"] == 2


def test_partial_closes_are_one_position_with_volume_weighted_entry() -> None:
    deals = [_deal(7, 2000.0, deal=1, volume=0.03), _deal(7, 2001.0, deal=2, volume=0.01)]
    rows, unjoined = m.fusion_rows([_intent(7, 2000.0, 1990.0)], deals, AS_OF)
    assert unjoined == 0 and len(rows) == 1 and rows[0]["n_close_deals"] == 2
    assert rows[0]["slip_r"] == pytest.approx(0.025)


def test_stale_ledger_is_never_measured() -> None:
    old = "2020-01-01T00:00:00+00:00"
    doc = m.build(AS_OF, fusion_intents=[_intent(i, 2000.0, 1990.0, time=old)
                                         for i in range(1, 31)],
                  fusion_deals=[_deal(i, 2000.5, time=old) for i in range(1, 31)],
                  e8_intents=[], e8_fills=None)
    f = doc["accounts"]["fusion"]
    assert f["status"] == m.STALE and f["median_slip_r"] is None
    assert f["freshness"]["fresh"] is False
    assert doc["e8_headroom_input"]["fusion_slip_r"] == m.UNMEASURED


def test_small_n_has_no_ci_and_no_directional_sign() -> None:
    i, d = _book(2, 2000.0)
    doc = m.build(AS_OF, fusion_intents=i, fusion_deals=d, e8_intents=[], e8_fills=None)
    f = doc["accounts"]["fusion"]
    assert f["mean_ci95"] is None and f["sign"] == m.INSUFFICIENT_N
    assert f["status"] == m.INSUFFICIENT_N
    assert doc["e8_headroom_input"]["fusion_slip_r"] == m.UNMEASURED


def test_sign_is_ci_aware() -> None:
    assert m.ci_sign([-0.01, 0.02], 30) == m.INDISTINGUISHABLE
    assert m.ci_sign([0.001, 0.02], 30) == "WORSE_THAN_ASKED"
    assert m.ci_sign([-0.02, -0.001], 30) == "BETTER_THAN_ASKED"
    assert m.ci_sign(None, 0) == m.UNMEASURED
    i, d = _book(25, 2000.5)
    doc = m.build(AS_OF, fusion_intents=i, fusion_deals=d, e8_intents=[], e8_fills=None)
    f = doc["accounts"]["fusion"]
    assert f["status"] == "MEASURED" and f["sign"] == "WORSE_THAN_ASKED"
    assert doc["e8_headroom_input"]["fusion_slip_r"] == pytest.approx(0.05)


def test_unmeasured_rows_never_enter_the_median() -> None:
    rows: list[dict[str, Any]] = [{"slip_r": None, "reason": "no_stop"},
                                  {"slip_r": 0.1, "reason": "measured"}]
    s = m.summarise(rows)
    assert s["n_measured"] == 1 and s["median_slip_r"] == pytest.approx(0.1)
    assert s["unmeasured_by_reason"] == {"no_stop": 1}
    empty = m.summarise([{"slip_r": None, "reason": "no_stop"}])
    assert empty["median_slip_r"] is None and empty["sign"] == m.UNMEASURED


def test_point_in_time_excludes_future_and_unstamped_rows() -> None:
    late = "2026-10-21T00:00:00+00:00"
    rows, _ = m.fusion_rows([_intent(1, 2000.0, 1990.0), _intent(2, 2000.0, 1990.0, time=late),
                             _intent(3, 2000.0, 1990.0, time=None)],
                            [_deal(1, 2000.1), _deal(3, 2000.1)], AS_OF)
    assert [r["ticket"] for r in rows] == [1]
    block, _ = m.fusion_block([_intent(1, 2000.0, 1990.0)],
                              [_deal(1, 2000.1), _deal(2, 2000.1, time=late)], AS_OF)
    assert block["n_deals"] == 1


def test_e8_without_fills_is_unmeasured_and_kept_apart_from_fusion() -> None:
    e8 = [{"at": T, "status": "SENT", "order_id": 9, "side": "buy", "price": 2000.0,
           "sl": 1990.0, "window": "asia"}]
    i, d = _book(25, 2000.5)
    doc = m.build(AS_OF, fusion_intents=i, fusion_deals=d, e8_intents=e8, e8_fills=None)
    assert doc["accounts"]["e8"]["median_slip_r"] is None
    assert doc["accounts"]["e8"]["sign"] == m.UNMEASURED
    assert doc["e8_headroom_input"]["e8_slip_r"] == m.UNMEASURED
    assert doc["e8_headroom_input"]["fusion_slip_r"] == pytest.approx(0.05)


def test_e8_with_fills_lowercase_status_and_dedupe() -> None:
    e8 = [{"at": T, "status": " sent", "order_id": 9, "side": "sell", "entry_ref": 2000.0,
           "stop": 2010.0}, {"at": T, "status": "SENT", "order_id": 9, "side": "sell",
                             "entry_ref": 2000.0, "stop": 2010.0},
          {"at": T, "status": "REJECTED", "order_id": 8}]
    fills = [{"order_id": "9", "avgPrice": 1999.0, "time": T}]
    doc = m.build(AS_OF, fusion_intents=[], fusion_deals=[], e8_intents=e8, e8_fills=fills)
    e = doc["accounts"]["e8"]
    assert e["n_rows"] == 1 and e["median_slip_r"] == pytest.approx(0.1)
    assert e["status"] == m.INSUFFICIENT_N
    assert doc["accounts"]["fusion"]["status"] == m.UNMEASURED


def test_stale_e8_fills_are_stale() -> None:
    old = "2020-01-01T00:00:00+00:00"
    e8 = [{"at": old, "status": "SENT", "order_id": 9, "side": "buy", "price": 2000.0,
           "sl": 1990.0}]
    doc = m.build(AS_OF, fusion_intents=[], fusion_deals=[], e8_intents=e8,
                  e8_fills=[{"order_id": 9, "fill_price": 2000.1, "time": old}])
    assert doc["accounts"]["e8"]["status"] == m.STALE


def test_garbage_lines_are_counted(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\nnot json\n\n[1, 2]\n', encoding="utf-8")
    rows, bad = m.read_jsonl(p)
    assert rows == [{"a": 1}] and bad == 2


CSV = ("filled_at_utc,window,side,lot,entry,sl,tp,position_id\n"
       "2026-10-14T07:12:22,asia,long,0.08,4318.13,4257.49,4439.41,111\n"
       "2026-10-14T10:07:20,london_am,short,0.16,4305.16,4335.37,4244.74,222\n"
       "bad,row,,,,,,\n")


def test_e8_csv_export_without_intents_is_no_intended_price(tmp_path: Path) -> None:
    p = tmp_path / "e8_fills.csv"
    p.write_text(CSV, encoding="utf-8")
    fills, bad = m.read_e8_fills(p)
    assert len(fills) == 2 and bad == 1
    assert fills[0]["time"] == "2026-10-14T07:12:22+00:00"
    doc = m.build(AS_OF, fusion_intents=[], fusion_deals=[], e8_intents=[], e8_fills=fills)
    e = doc["accounts"]["e8"]
    assert e["n_rows"] == 2 and e["n_measured"] == 0
    assert e["unmeasured_by_reason"] == {"no_intended_price": 2}
    assert e["median_slip_r"] is None and doc["e8_headroom_input"]["e8_slip_r"] == m.UNMEASURED


def test_e8_csv_fill_joins_its_bracket_intent_on_the_stop_target_echo(tmp_path: Path) -> None:
    p = tmp_path / "e8_fills.csv"
    p.write_text(CSV, encoding="utf-8")
    fills, _ = m.read_e8_fills(p)
    intents = [{"at": "2026-10-14T04:00:00+00:00", "status": "SENT", "order_id": 5,
                "window": "asia", "side": "buy_stop", "price": 4318.0, "sl": 4257.49,
                "tp": 4439.41},
               # same echo, wrong window: must not join the london_am fill
               {"at": "2026-10-14T04:00:00+00:00", "status": "SENT", "order_id": 6,
                "window": "asia", "side": "sell_stop", "price": 4305.0, "sl": 4335.37,
                "tp": 4244.74}]
    rows, _ = m.e8_rows(intents, fills, AS_OF)
    by_win = {r["window"]: r for r in rows}
    assert by_win["asia"]["slip_r"] == pytest.approx(0.13 / (4318.0 - 4257.49), abs=1e-6)
    assert by_win["asia"]["intent_order_id"] == 5
    assert by_win["london_am"]["reason"] == "no_intended_price"


def test_the_published_report_carries_no_trade_level_record(tmp_path: Path) -> None:
    out = tmp_path / "MARKOUT_V2.json"
    assert m.main(["--as-of", AS_OF.isoformat(), "--out", str(out),
                   "--e8-fills", str(tmp_path / "absent.jsonl")]) == 0
    published = out.read_text("utf-8")
    for key in ('"rows"', '"ticket"', '"deals"', '"deal"', '"intent_order_id"', '"order_id"',
                '"filled_at"', '"latest_fill_at"', '"fill"', '"position"', '"entry_price"'):
        assert key not in published, key
    doc = {"accounts": {"fusion": {"n_rows": 3, "freshness": {"latest_fill_at": T,
                                                               "age_days": 1.0}}},
           "rows": {"fusion": [{"ticket": 1, "deals": [10], "fill": 2000.5}]}}
    view = m.public_view(doc)
    assert "rows" not in view and "latest_fill_at" not in json.dumps(view)
    assert view["accounts"]["fusion"]["freshness"]["age_days"] == 1.0
    assert (tmp_path / m.ROWS_OUT.name).exists()

