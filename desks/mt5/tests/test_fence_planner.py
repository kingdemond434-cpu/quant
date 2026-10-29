"""The fence-aware planner, the fence's counterfactual bill, and their hourly wiring (v2).

THE CASE (2026-10-29 04:24Z): E8 held or rested a gold short, the fence refused Fusion's gold_asia
buy_stop and let its sell_stop place, so Fusion carried half a bracket nobody chose.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import bars_state as bs  # noqa: E402
from research import fence_missed_trades as fmt  # noqa: E402
from research import fence_planner as fp  # noqa: E402
from research import missed_growth as mg  # noqa: E402

DAY = "2026-10-29"
WHY = ("cross-account fence: e8 holds or rests a short on XAUUSD; a long on XAUUSD here would "
       "hedge the other account")
BUY = {"time": "2026-10-29T04:24:28+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
       "side": "buy_stop", "price": 4069.31, "sl": 4035.92, "tp": 4135.69, "lot": 0.01,
       "execution": "pending_stop", "taken": False, "reason": "cross_account_opposite",
       "outcome": "VALIDATION_REJECTED", "detail": WHY}
SELL = {"time": "2026-10-29T04:24:44+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
        "side": "sell_stop", "price": 4036.12, "sl": 4069.51, "tp": 3969.74, "lot": 0.01,
        "execution": "pending_stop", "taken": True, "outcome": "EXECUTED", "reason": "placed"}
OK = "book 10s old"
BOOKS = {"e8": ({"XAUUSD": {"long": False, "short": True}}, OK),
         "fusion": ({"XAUUSD": {"long": False, "short": True}}, OK),
         "ftmo": ({}, OK)}
EMPTY_BOOKS = {"e8": ({}, OK), "fusion": ({}, OK), "ftmo": ({}, OK)}


def _ledger(n_long: int, n_short: int, r: float = 0.4) -> list[dict]:
    rows = [{"sleeve": "gold_asia", "entry_price": 100.0, "sl": 99.0, "pl_quote": r * 10,
             "risk_quote": -10.0} for _ in range(n_long)]
    rows += [{"sleeve": "gold_asia_v2", "entry_price": 100.0, "sl": 101.0, "pl_quote": r * 10,
              "risk_quote": -10.0} for _ in range(n_short)]
    return rows


def _build(ledger: list[dict], books: dict | None = BOOKS, cert: dict | None = None,
           ftmo: list[dict] | None = None) -> dict:
    return fp.build(DAY, decisions=[BUY, SELL], e8=[], ftmo=ftmo or [],
                    cert=cert if cert is not None else {"fusion": {"gold_asia": 0.006}},
                    sleeves=[], ledger=ledger, books=books, today=DAY)


# ------------------------------------------------------------------------------- the planner
def test_e8_short_resting_fusion_never_long_or_whole_and_unmeasured_is_no_divergence():
    doc = _build(_ledger(0, 0))
    p = doc["plans"]["XAUUSD|2026-10-29"]
    for a in [p["plan"], *p["alternatives"]]:
        assert a["assignment"]["fusion:gold_asia"] in ("short", "none")
    assert p["verdict"] == "UNMEASURED"
    assert doc["divergent_measured_symbol_days"] == 0
    assert any("fusion:gold_asia" in h for h in doc["half_brackets_actual"])


def test_measured_short_edge_plans_short_only_matching_what_fusion_carried():
    doc = _build(_ledger(12, 12))
    p = doc["plans"]["XAUUSD|2026-10-29"]
    assert p["verdict"] == "PLANNED"
    assert p["plan"]["assignment"]["fusion:gold_asia"] == "short"
    assert p["plan"]["delta_elogw"] > 0
    assert doc["divergent_measured_symbol_days"] == 0


def test_all_edges_missing_is_unmeasured_not_planned_none():
    doc = _build([])
    assert doc["verdict"] == "UNMEASURED"
    assert doc["plans"]["XAUUSD|2026-10-29"]["verdict"] == "UNMEASURED"


def test_no_books_is_unmeasured():
    doc = _build(_ledger(12, 12), books={})
    assert doc["verdict"] == "UNMEASURED"
    assert {"book:e8: not read", "book:fusion: not read"} <= set(doc["missing_inputs"])
    stale = _build(_ledger(12, 12), books={**BOOKS, "e8": (None, "the e8 book is 2000s old")})
    assert stale["plans"]["XAUUSD|2026-10-29"]["verdict"] == "UNMEASURED"


def test_whole_bracket_when_no_account_holds_a_side():
    doc = _build(_ledger(12, 12), books=EMPTY_BOOKS)
    p = doc["plans"]["XAUUSD|2026-10-29"]
    assert p["verdict"] == "PLANNED"
    assert p["plan"]["assignment"]["fusion:gold_asia"] == "both"


def test_ftmo_only_follows_e8_direction():
    ft = [{"at": "2026-10-29T04:30:00+00:00", "window": "gold_asia", "side": "buy_stop"}]
    doc = _build(_ledger(12, 12), ftmo=ft, cert={"fusion": {"gold_asia": 0.006},
                                                   "ftmo": {"gold_asia": 0.009}})
    p = doc["plans"]["XAUUSD|2026-10-29"]
    for a in [p["plan"], *p["alternatives"]]:
        assert a["assignment"]["ftmo:gold_asia"] == "none"   # E8 is short; FTMO never long


def test_history_keeps_one_row_per_day(tmp_path):
    h = tmp_path / "h.jsonl"
    doc = _build(_ledger(12, 12))
    fp.upsert_history(doc, h)
    fp.upsert_history(doc, h)
    fp.upsert_history({**doc, "day": "2026-10-30"}, h)
    assert [json.loads(x)["day"] for x in h.read_text().splitlines()] == [DAY, "2026-10-30"]


# ------------------------------------------------------------------------ the counterfactual
def _bars(spikes: dict[str, tuple[float, float]], *, start: str = "2026-10-29 04:55",
          end: str = "2026-10-29 22:29", level: float = 4050.0) -> pd.DataFrame:
    """Broker-wall M1 bars, flat at `level`, with {wall: (high, low)} spikes."""
    idx = pd.date_range(start, end, freq="1min")
    hi = [spikes.get(t.strftime("%H:%M"), (level + 1, level - 1))[0] for t in idx]
    lo = [spikes.get(t.strftime("%H:%M"), (level + 1, level - 1))[1] for t in idx]
    return pd.DataFrame({"open": level, "high": hi, "low": lo, "close": level,
                         "spread": 0}, index=idx)


def _ev(row: dict = BUY, sibling: dict | None = None) -> dict:
    decisions = [row] + ([sibling] if sibling else [])
    return fmt.events(decisions=decisions, e8=[], ftmo=[])[0]


needs_anchor = pytest.mark.skipif(bs.ANCHOR is None, reason="no server anchor importable")


@needs_anchor
def test_a_0500_stamped_bar_is_before_the_0424z_refusal():
    # 04:24Z on 10-29 is 07:24 broker (UTC+3). A bar stamped 05:00 broker that fills and hits
    # the target is BEFORE the refusal; read as UTC it would have been after it.
    bars = _bars({"05:00": (4140.0, 4060.0)})
    cf = fmt.counterfactual(_ev(), bars, point=0.01, clock=bs, directions={})
    assert cf["exit"] == "never_filled" and cf["r"] == 0.0


@needs_anchor
def test_fill_then_target_and_the_time_exit_bar():
    bars = _bars({"08:00": (4070.0, 4060.0), "09:00": (4140.0, 4068.0)})
    cf = fmt.counterfactual(_ev(), bars, point=0.01, clock=bs, directions={})
    assert cf["exit"] == "tp"
    assert abs(cf["r"] - (4135.69 - 4069.31) / (4069.31 - 4035.92)) < 1e-6
    # the spread is the ask: a bid high 1.0 short of the stop fills at a 120-point spread
    near = _bars({"08:00": (4068.31, 4060.0)})
    near.loc[pd.Timestamp("2026-10-29 08:00"), "spread"] = 120
    assert fmt.counterfactual(_ev(), near, point=0.01, clock=bs, directions={})["filled"]
    # bars that stop before 22:29 broker (19:30Z) leave the row pending
    short = _bars({}, end="2026-10-29 20:00")
    assert fmt.counterfactual(_ev(), short, point=0.01, clock=bs, directions={})["status"] \
        == "PENDING"


@needs_anchor
def test_sibling_fills_first_cancelled_by_oco():
    bars = _bars({"07:40": (4051.0, 4030.0), "08:00": (4140.0, 4060.0)})
    ev = _ev(BUY, SELL)
    assert ev["sibling"]["side"] == "sell_stop"
    cf = fmt.counterfactual(ev, bars, point=0.01, clock=bs, directions={})
    assert cf["exit"] == "cancelled_by_oco" and cf["r"] == 0.0 and cf["cancelled_by"] == "sibling"


@needs_anchor
def test_another_accounts_first_fill_cancels_and_unreadable_oco_is_unmeasured():
    bars = _bars({"08:00": (4140.0, 4060.0)})
    days = {DAY: {"direction": "short", "first_fill_at": "2026-10-29T04:10:00+00:00",
                  "first_fill_lane": "e8"}}
    cf = fmt.counterfactual(_ev(), bars, point=0.01, clock=bs, directions=days)
    assert cf["exit"] == "cancelled_by_oco" and cf["r"] == 0.0
    assert fmt.counterfactual(_ev(), bars, point=0.01, clock=bs,
                              directions=None)["status"] == "UNMEASURED_OCO"
    assert fmt.counterfactual(_ev(), bars, point=0.01, clock=None,
                              directions={})["status"] == "UNMEASURED_NO_ANCHOR"


def test_one_pending_event_is_unmeasured(tmp_path):
    class Clock:
        @staticmethod
        def utc_to_broker(t: datetime) -> datetime:
            return t.replace(tzinfo=None) + timedelta(hours=3)

        @staticmethod
        def broker_to_utc(t: datetime) -> datetime:
            return t - timedelta(hours=3)
    doc = fmt.run(evs=[_ev()], bars_for=lambda s: _bars({}, end="2026-10-29 09:00"),
                  out=tmp_path / "m.jsonl", summary=tmp_path / "s.json", clock=Clock,
                  directions={}, cert={})
    assert doc["verdict"] == "UNMEASURED" and doc["pending_count"] == 1
    assert doc["priced_rows"] == 0


def test_fail_closed_split_and_ftmo_unknown_side():
    assert fmt.kind_of(WHY) == "fence_block"
    assert fmt.kind_of("cross-account fence: the placement lock is held by the other "
                       "account's lane; fail closed") == "fail_closed"
    assert fmt.kind_of("cross-account fence: the e8 book is 2000s old (limit 900s); the e8 "
                       "account's positions are unknown now; fail closed") == "fail_closed"
    ev = fmt.events(decisions=[], e8=[], ftmo=[{"at": "2026-10-29T04:30:00+00:00",
                                               "window": "gold_asia",
                                               "reason": "opposite_exposure"}])[0]
    assert ev["kind"] == "ftmo_follow_rule" and ev["side"] == "?"
    assert fmt.counterfactual(ev, None)["status"] == "UNMEASURED_SIDE_UNKNOWN"


def test_missed_growth_line_needs_n_and_is_never_summed_with_rails(tmp_path):
    p = tmp_path / "m.jsonl"
    row = {"kind": "fence_block", "status": "MEASURED", "r": 2.0, "risk_frac": 0.006,
           "missed_usd": 66.0}
    p.write_text("\n".join(json.dumps(row) for _ in range(3)) + "\n")
    rails = tmp_path / "rails.jsonl"
    rails.write_text(json.dumps({"rail": "cross_account_opposite"}) + "\n")
    few = mg.cross_account_fence_line(p, rails=rails)
    assert few["verdict"] == mg.UNMEASURED and few["n"] == 3
    assert few["fusion_book_rails_cross_account_opposite_lines"] == 1
    p.write_text("\n".join(json.dumps(row) for _ in range(10)) + "\n")
    line = mg.cross_account_fence_line(p, rails=rails)
    assert line["verdict"] == mg.COSTS and line["n"] == 10
    assert abs(line["value_logw"] - 10 * (0.006 * 2 - 0.5 * 0.006 ** 2 * 4)) < 1e-12
    assert mg.cross_account_fence_line(tmp_path / "absent.jsonl")["verdict"] == mg.UNMEASURED


def test_legs_are_wired_hourly_and_contracted_on_numeric_metrics():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("fence_planner", "fence_missed_trades"):
        assert f'_producer(\n        "{leg}", "research/{leg}.py")' in src
    from research import hourly_cycle as hc
    assert {"fence_planner", "fence_missed_trades"} <= hc.CORE_LEGS
    contracts = json.loads((DESK.parent.parent / "docs" / "research" /
                            "experiment_contracts.json").read_text("utf-8"))["legs"]
    assert contracts["fence_planner"]["falsifier"]["metric"] == "divergent_measured_symbol_days"
    assert contracts["fence_missed_trades"]["falsifier"]["metric"] == "priced_rows"
    assert isinstance(_build(_ledger(12, 12))["divergent_measured_symbol_days"], int)
    mg_src = (DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"cross_account_fence": cross_account_fence_line()' in mg_src
