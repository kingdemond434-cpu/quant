"""TIER-1 W8 / C12 -- THE EXECUTION INTELLIGENCE COMMAND.

Cost(asset, time, size, state, order) and NetAlpha = RawAlpha - ExpectedExecutionCost. What is
pinned here is the arithmetic that makes the surface trustworthy rather than merely present: a
planted size-dependent cost is RECOVERED by the size dimension; a thin cell is SHRUNK toward its
parent and says by how much (n_eff); a cell the desk has never traded reads UNMEASURED and falls
back to the MODELLED spread and never to zero; and a candidate whose raw edge is smaller than its
own cell's cost appears in the sign-flip list, which is the whole point of the organ.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cost_surface as CS  # noqa: E402

#: The registry the R denominator is built from. `risk_quote` is no longer the divisor:
#: it holds a price distance on some ledger rows and a money amount on others (measured
#: 2026-09-23, reports/COST_TRUTH.json), which billed EURCHF 45R of commission. The
#: denominator is the deal's OWN stop distance carried into account currency.
_META: dict[str, Any] = {"EURUSD": {"tick_size": 1e-5, "tick_value": 1.0},
                         "GBPUSD": {"tick_size": 1e-5, "tick_value": 1.0}}


def _deal(symbol: str, hour: int, volume: float, commission: float, *, risk: float = 100.0,
          sleeve: str = "s1", swap: float = 0.0) -> dict[str, Any]:
    # a stop distance that carries EXACTLY `risk` of account currency at this lot size
    entry = 1.20000
    stop_px = risk * _META[symbol]["tick_size"] / volume
    return {"time": f"2026-09-0{1 + hour % 9}T{hour:02d}:30:00+00:00", "symbol": symbol,
            "sleeve": sleeve, "volume": volume, "commission": -commission, "swap": swap,
            "entry_price": entry, "sl": round(entry - stop_px, 8),
            "risk_quote": -risk}


def _spread_surface(symbol: str = "EURUSD") -> dict[str, Any]:
    hours = {str(h): {"status": "MEASURED", "p50": 10.0 + h, "p75": 12.0 + h, "p90": 14.0 + h,
                      "n_bars": 500, "n_nonzero": 500, "zero_frac": 0.0} for h in range(24)}
    return {"symbols": {symbol: {"hours": hours, "dearest_hour": 23, "cheapest_hour": 0}}}


def test_a_planted_size_dependent_cost_is_recovered_by_the_size_dimension() -> None:
    # cost scales with the lot: 0.01 -> 0.1R, 0.10 -> 1.0R, 1.00 -> 10.0R of the same risk
    deals = ([_deal("EURUSD", 3, 0.01, 10.0) for _ in range(12)]
             + [_deal("EURUSD", 3, 0.10, 100.0) for _ in range(12)]
             + [_deal("EURUSD", 3, 1.00, 1000.0) for _ in range(12)])
    rows, notes = CS.deal_costs(deals, _META)
    assert len(rows) == 36 and not any("cannot be expressed in R" in n for n in notes)
    assert {r["size"] for r in rows} == {"small", "medium", "large"}
    cells = CS.cells(rows)
    small = cells["EURUSD|asia|small"]["cost_r_measured"]
    large = cells["EURUSD|asia|large"]["cost_r_measured"]
    assert large > 50 * small                       # the size dimension carries the structure
    assert cells["EURUSD|asia|small"]["status"] == "MEASURED"


def test_a_size_independent_cost_is_not_invented_by_the_size_dimension() -> None:
    deals = ([_deal("EURUSD", 3, 0.01, 10.0) for _ in range(12)]
             + [_deal("EURUSD", 3, 0.10, 10.0) for _ in range(12)]
             + [_deal("EURUSD", 3, 1.00, 10.0) for _ in range(12)])
    cells = CS.cells(CS.deal_costs(deals, _META)[0])
    per_size = [cells[f"EURUSD|asia|{b}"]["cost_r_measured"] for b in ("small", "medium", "large")]
    assert max(per_size) - min(per_size) < 1e-9     # flat in, flat out


def test_a_thin_cell_is_shrunk_toward_its_parent_and_states_its_n_eff() -> None:
    fat = [_deal("EURUSD", 3, 0.01, 10.0, sleeve="fat") for _ in range(40)]
    thin = [_deal("EURUSD", 3, 0.01, 1000.0, sleeve="thin")]
    rows, _ = CS.deal_costs(fat + thin, _META)
    for r in rows:
        r["order"] = "market" if r["sleeve"] == "fat" else "limit"
    cells = CS.cells(rows)
    thin_row = next(r for r in rows if r["order"] == "limit")
    cell = cells["|".join(str(thin_row[d]) for d in CS.DIMENSIONS)]
    assert cell["n"] == 1
    assert cell["n_eff"] == 1 + CS.K_SHRINK
    assert cell["parent_cost_r"] is not None
    # the one wild observation is pulled most of the way back to its parent margin
    assert cell["cost_r_shrunk"] < cell["cost_r_measured"] / 2
    assert cell["status"] == "THIN"


def test_an_untraded_cell_is_UNMEASURED_and_falls_back_to_the_modelled_cost_not_zero() -> None:
    surf = {"cells": CS.cells(CS.deal_costs([_deal("EURUSD", 3, 0.01, 10.0)] * 4, _META)[0])}
    hit = CS.lookup(surf, asset="XAUUSD", time="ny", size="large", state="dear", order="market")
    assert hit["status"] == "UNMEASURED" and hit["cost_r"] is None and hit["why"]
    spread = _spread_surface("XAUUSD")
    modelled = CS.modelled_cost_r(spread, "XAUUSD", 12, stop_pts=500.0)
    assert modelled is not None and modelled > 0.0      # never 0.0, never a silent guess
    assert CS.modelled_cost_r(spread, "XAUUSD", 12, stop_pts=None) is None
    assert CS.modelled_cost_r(spread, "NOTHING", 12, stop_pts=500.0) is None


def test_the_hierarchy_answers_from_the_deepest_level_that_has_evidence() -> None:
    rows, _ = CS.deal_costs([_deal("EURUSD", 3, 0.01, 10.0) for _ in range(6)], _META)
    surf = {"cells": CS.cells(rows)}
    deep = CS.lookup(surf, asset="EURUSD", time="asia", size="UNMEASURED",
                     state="UNMEASURED", order="UNMEASURED")
    assert deep["resolved_at"] == "asset|time|size|state|order" and deep["status"] == "MEASURED"
    shallow = CS.lookup(surf, asset="EURUSD", time="asia", size="large",
                        state="dear", order="market")
    assert shallow["status"] == "SHRUNK_TO_PARENT"
    assert shallow["resolved_at"] == "asset|time"       # the deepest level with evidence
    none = CS.lookup(surf, asset="NEVER_TRADED", time="ny", size="large", state="dear",
                     order="market")
    assert none["status"] == "UNMEASURED" and none["cost_r"] is None


def test_the_state_dimension_is_the_symbols_own_spread_regime() -> None:
    spread = _spread_surface("EURUSD")
    assert CS.state_of(spread, "EURUSD", 0) == "cheap"
    assert CS.state_of(spread, "EURUSD", 23) == "dear"
    assert CS.state_of(spread, "EURUSD", 12) == "normal"
    assert CS.state_of(spread, "EURUSD", -1) == "UNMEASURED"
    assert CS.state_of(spread, "ABSENT", 3) == "UNMEASURED"


def test_a_candidate_whose_edge_is_smaller_than_its_cost_lands_in_the_sign_flip_list() -> None:
    rows, _ = CS.deal_costs([_deal("EURUSD", 23, 0.01, 50.0) for _ in range(6)], _META)
    surf = {"cells": CS.cells(rows)}
    spread = _spread_surface("EURUSD")
    raws = [{"id": "rich", "asset": "EURUSD", "family": "f", "selector": "",
             "raw_alpha": 2.0, "unit": "R_per_trade", "source": "test"},
            {"id": "thin", "asset": "EURUSD", "family": "f", "selector": "",
             "raw_alpha": 0.05, "unit": "R_per_trade", "source": "test"}]
    table, flips = CS.net_alpha(raws, surf, spread)
    by_id = {r["id"]: r for r in table}
    assert by_id["rich"]["net_alpha"] > 0 and by_id["thin"]["net_alpha"] < 0
    assert [f["id"] for f in flips] == ["thin"]
    assert by_id["thin"]["cost_basis"] in ("MEASURED", "SHRUNK_TO_PARENT")


def test_a_deal_with_no_recorded_risk_is_counted_and_never_assumed_free() -> None:
    bad = [{"time": "2026-09-01T03:00:00+00:00", "symbol": "EURUSD", "volume": 0.01,
            "commission": -10.0, "swap": 0.0}]
    rows, notes = CS.deal_costs(bad, _META)
    assert rows == [] and any("cannot be" in n and "never assumed free" in n
                              for n in notes)


def test_the_report_is_written_with_a_verdict_per_input_even_with_nothing_on_the_host(
        tmp_path: Path) -> None:
    doc = CS.build_execution_surface(_spread_surface(), ledger=tmp_path / "nope.jsonl",
                                     corpus=tmp_path / "also-nope.jsonl")
    assert doc["schema"] == "execution-cost-surface-1"
    assert list(doc["dimensions"]) == list(CS.DIMENSIONS)
    assert doc["inputs"]["nope.jsonl"] == "absent"
    assert doc["n_deals_priced"] == 0
    assert any("UNMEASURED" in n for n in doc["unmeasured"])
    assert "vetoes nothing" in doc["rule"]


def test_a_swap_credit_lowers_the_cost_rather_than_raising_it() -> None:
    debit = CS.deal_costs([_deal("EURUSD", 3, 0.01, 10.0, swap=-5.0)], _META)[0][0]["cost_r"]
    credit = CS.deal_costs([_deal("EURUSD", 3, 0.01, 10.0, swap=+5.0)], _META)[0][0]["cost_r"]
    assert credit < debit
