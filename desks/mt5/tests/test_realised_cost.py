"""Realised execution cost, per fill, per account: what Fusion, E8 and FTMO actually paid, and the
allocator's cost input reading it -- both ways, never pooled, and never a zero for no fills."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import fill_corpus as fc  # noqa: E402
from libs.portfolio import execution_cost as ec  # noqa: E402
from research import fill_recorder as fr  # noqa: E402
from research import health_board as hb  # noqa: E402
from research import realised_cost as rc  # noqa: E402

_FUSION_INTENT: dict[str, Any] = {
    "time": "2026-09-16T09:00:00+00:00", "intent_id": "i1", "sleeve": "s", "symbol": "EURGBP",
    "side": "buy", "lot": 0.1, "intended": 0.85613, "sl": 0.85513, "tp": 0.85813,
    "ticket": 111, "retcode": 10009, "latency_ms": 12.5, "latency_send_to_ack_ms": 12.5,
    "decision_bid": 0.85610, "decision_ask": 0.85614, "spread_at_decision": 0.00004,
    "point": 0.00001,
}
_FUSION_DEAL: dict[str, Any] = {
    "time": "2026-09-16T09:30:00+00:00", "symbol": "EURGBP", "side": 1, "deal": 900,
    "entry_order": 111, "position_id": 111, "entry_price": 0.85627, "sl": 0.85513,
    "fill_price": 0.85700, "volume": 0.1, "contract_size": 100000.0, "commission": -0.5,
    "account_kind": "live", "entry_side": 0,
}
#: E8's order carries THE SAME NUMBER (111) as the Fusion ticket: a pooled join could cross them.
_E8_INTENT = {"at": "2026-10-30T04:00:00+00:00", "tag": "gold_asia", "symbol": "XAUUSD",
              "side": "buy", "lot": 0.1, "entry_ref": 2000.0, "stop": 1990.0, "target": 2020.0,
              "order_id": 111, "status": "SENT", "spread": 0.3}
_FTMO_FOLLOW = {"at": "2026-10-30T04:00:05+00:00", "window": "asia", "lane": "ftmo",
                "side": "buy", "kind": "buy_stop", "price": 4000.0, "sl": 3990.0, "tp": 4020.0,
                "lot": 0.1, "status": "SENT", "retcode": 10009, "order_id": 5001}
_FTMO_EXEC = {"at": "2026-10-30T05:00:00+00:00", "lane": "ftmo", "sleeve": "EURUSD_sess",
              "symbol": "EURUSD", "side": "sell", "entry_ref": 1.1000, "stop": 1.1050,
              "target": 1.0900, "spread": 0.00008, "lot": 0.2, "status": "SENT",
              "order_id": 7001, "latency_send_to_ack_ms": 40.0}
_FTMO_SKIPPED = {**_FTMO_EXEC, "status": "RAIL_BLOCKED", "order_id": None, "sleeve": "x"}


def _prop_row(book: str, pid: int, entry: float, sl: float, vol: float, contract: float,
              comm: float, symbol: str = "XAUUSD") -> dict[str, Any]:
    return {"schema": "prop-fills-v1", "book": book, "symbol": symbol, "position_id": pid,
            "entry_order": pid, "entry_price": entry, "sl": sl, "tp": entry + 20,
            "volume": vol, "fill_price": entry + 5, "entry_side": 0, "side": 1,
            "risk_quote": abs(entry - sl) * vol * contract, "commission": comm, "swap": 0.0,
            "fees": 0.0, "pl_quote": 50.0, "time": "2026-10-30T09:00:00+00:00",
            "entry_time": "2026-10-30T04:00:10+00:00", "account_kind": "prop",
            "account_key": "k" * 16}


def _point_recorder(monkeypatch: Any, tmp: Path) -> None:
    for name in ("INTENTS", "E8_INTENTS", "E8_GOLD_INTENTS", "FTMO_EXEC_INTENTS",
                 "FTMO_FOLLOWER_INTENTS",
                 "LEDGER", "PROP_LEDGER", "DECISIONS", "CORPUS"):
        monkeypatch.setattr(fr, name, tmp / f"{name.lower()}.jsonl")


def _jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


# --------------------------------------------------------------------------- ingestion
def test_ftmo_and_e8_fills_are_ingested_with_their_own_account(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.INTENTS, [_FUSION_INTENT])
    _jsonl(fr.LEDGER, [_FUSION_DEAL])
    _jsonl(fr.E8_INTENTS, [_E8_INTENT])
    _jsonl(fr.FTMO_FOLLOWER_INTENTS, [_FTMO_FOLLOW])
    _jsonl(fr.FTMO_EXEC_INTENTS, [_FTMO_EXEC, _FTMO_SKIPPED])
    _jsonl(fr.PROP_LEDGER, [_prop_row("e8", 111, 2000.2, 1990.0, 0.1, 100.0, -0.6),
                            _prop_row("ftmo", 5001, 4000.5, 3990.0, 0.1, 100.0, -0.7)])
    doc = fr.build()
    assert doc["by_book"]["fusion"]["matched_fills"] == 1
    assert doc["by_book"]["e8"]["matched_fills"] == 1
    assert doc["by_book"]["ftmo"]["matched_fills"] == 1
    # only the SENT executor row reached the venue; the refused sleeve is not an execution
    assert doc["by_book"]["ftmo"]["n_intents"] == 2
    rows = {r["record_id"]: r for r in fc.read_rows(fr.CORPUS)}
    filled = [r for r in rows.values() if r["status"] == "FILLED"]
    by_book = {r["book"]: r for r in filled}
    assert set(by_book) == {"fusion", "e8", "ftmo"}
    # each book's fill is its own venue's: E8's 111 joined E8's position, not Fusion's deal 900
    assert by_book["fusion"]["symbol"] == "EURGBP" and by_book["fusion"]["deal"] == 900
    assert by_book["e8"]["symbol"] == "XAUUSD" and by_book["e8"]["fill_price"] == 2000.2
    assert by_book["ftmo"]["fill_price"] == 4000.5
    # FTMO's pending stop filled 0.5 above the trigger: worse than asked is positive slippage
    # R is the position's own |entry - stop| = 10.5, the contract recovered from risk_quote
    assert by_book["ftmo"]["slip_r"] == pytest.approx(0.5 / 10.5)
    assert by_book["ftmo"]["commission_r"] == pytest.approx(-0.7 / (10.5 * 0.1 * 100.0))
    assert by_book["e8"]["record_id"].startswith("e8|")
    assert by_book["ftmo"]["record_id"].startswith("ftmo|")
    assert "live_ledger_prop.jsonl" in by_book["ftmo"]["sources"]
    # the FTMO executor's EURUSD order has no closed position yet: UNRESOLVED, never a 0 slip
    exec_row = [r for r in rows.values() if r.get("book") == "ftmo" and r["symbol"] == "EURUSD"]
    assert exec_row and exec_row[0]["status"] == "UNRESOLVED"


def test_e8_deals_join_only_e8_intents(tmp_path: Path, monkeypatch: Any) -> None:
    """A Fusion deal whose entry_order equals an E8 order id is never claimed by the E8 intent."""
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.LEDGER, [_FUSION_DEAL])
    _jsonl(fr.E8_INTENTS, [_E8_INTENT])
    doc = fr.build()
    assert doc["by_book"]["e8"]["matched_fills"] == 0
    assert doc["by_book"]["fusion"]["n_unmatched_deals"] == 1


# --------------------------------------------------------------------------- aggregation
def _fill(book: str, symbol: str, slip_r: float, spread_frac: float, stop_frac: float,
          comm_r: float, rid: str, decided: str = "2026-11-01T04:00:00+00:00"
          ) -> dict[str, Any]:
    return {"record_id": rid, "intent_id": rid, "book": book, "symbol": symbol,
            "status": "FILLED", "slip_r": slip_r, "slip_frac": slip_r * stop_frac,
            "spread_frac_at_decision": spread_frac, "stop_frac": stop_frac,
            "commission_r": comm_r, "decided_at": decided,
            "latency_decision_to_send_ms": 10.0, "latency_send_to_ack_ms": 30.0,
            "join_keys": {"basis": "entry_order"}}


def test_accounts_are_never_mixed_in_an_aggregate() -> None:
    rows = [_fill("fusion", "XAUUSD", 0.01, 0.0001, 0.005, -0.01, "a"),
            _fill("ftmo", "XAUUSD", 0.20, 0.0004, 0.005, -0.05, "b")]
    doc = rc.build(rows, fill_report={"realised_fills": 2})
    fus = doc["accounts"]["fusion"]["symbols"]["XAUUSD"]
    ftm = doc["accounts"]["ftmo"]["symbols"]["XAUUSD"]
    assert fus["n_fills"] == 1 and ftm["n_fills"] == 1
    # fusion: 0.01 + 0.0001/0.005 + 0.01 = 0.04R ; ftmo: 0.20 + 0.08 + 0.05 = 0.33R
    assert fus["total_cost_r"]["mean"] == pytest.approx(0.04)
    assert ftm["total_cost_r"]["mean"] == pytest.approx(0.33)
    assert fus["commission_frac"]["mean"] == pytest.approx(0.01 * 0.005)
    assert doc["accounts"]["e8"]["status"] == "UNMEASURED"
    assert doc["status"] == "MEASURED" and doc["n_cells_measured"] == 2


def test_unattributed_and_duplicate_rows_never_enter_a_cell() -> None:
    twin = {**_fill("fusion", "XAUUSD", 9.0, 0.1, 0.005, -1.0, "t"), "book": None,
            "intent_id": "", "sources": ["execution_twin_cases"]}
    open_fill = {**_fill("fusion", "XAUUSD", 0.5, 0.0001, 0.005, -0.01, "i9|open"),
                 "intent_id": "i9", "join_keys": {"basis": "intent_fill"}}
    joined = {**_fill("fusion", "XAUUSD", 0.02, 0.0001, 0.005, -0.01, "i9|closed"),
              "intent_id": "i9"}
    doc = rc.build([twin, open_fill, joined], fill_report={"realised_fills": 1})
    cell = doc["accounts"]["fusion"]["symbols"]["XAUUSD"]
    assert cell["n_fills"] == 1
    assert cell["slip_r"]["mean"] == pytest.approx(0.02)
    assert doc["corpus_census"]["unattributed"] == 1
    assert doc["corpus_census"]["duplicates_collapsed"] == 1


#: the real pricer, captured before the autouse fixture swaps it out
_REAL_PRICER = rc.gauntlet_pricer


def _charge(r: float | None) -> Any:
    """A replay pricer that charged every fill `r` R (None: the replay could not price it)."""
    def price(_row: dict[str, Any]) -> tuple[float | None, str]:
        return r, ("test charge" if r is not None else "UNMEASURED: test unpriced")
    return price


@pytest.fixture(autouse=True)
def _no_gauntlet_import(monkeypatch: Any) -> None:
    """`build` defaults to the gauntlet's own pricer; these tests price with a declared charge
    unless they import the gauntlet on purpose."""
    monkeypatch.setattr(rc, "gauntlet_pricer", lambda *a, **k: _charge(0.0))


def test_the_shrinkage_is_n_over_n_plus_k_toward_the_model() -> None:
    assert rc.SHRINK_K == ec.REALISED_K == 20.0
    assert rc.MIN_DIFF_N == ec.REALISED_MIN_N == 5
    val, w = rc.shrink(0.25, 20, 0.05)
    assert w == pytest.approx(0.5) and val == pytest.approx(0.15)
    val, w = rc.shrink(0.25, 180, 0.05)
    assert w == pytest.approx(0.9) and val == pytest.approx(0.9 * 0.25 + 0.1 * 0.05)
    assert rc.shrink(None, 0, 0.05) == (None, 0.0)
    rows = [_fill("fusion", "EURUSD", 0.1, 0.0, 0.01, 0.0, f"r{i}") for i in range(5)]
    sh = rc.build(rows, fill_report=None)["accounts"]["fusion"]["symbols"]["EURUSD"]["shrink"]
    assert sh["weight"] == pytest.approx(5 / 25)
    # NO BLEND AGAINST ANY SCALAR here: the allocator shrinks vs_replay toward its modelled bias
    assert "shrunk_cost_r" not in sh and "prior_cost_r" not in sh


def test_one_extreme_slip_barely_moves_the_difference() -> None:
    """A single 4,138-point fill (here a 50R slip among 0.05R fills) is clipped at the cell's own
    quantiles before the shrinkage; the raw mean still publishes it."""
    calm = [_fill("fusion", "XAUUSD", 0.05, 0.0, 0.01, 0.0, f"c{i}") for i in range(24)]
    spike = _fill("fusion", "XAUUSD", 50.0, 0.0, 0.01, 0.0, "spike")
    for n_calm, method in ((24, "p5/p95"), (9, "p10/p90")):
        base = rc.build(calm[:n_calm], pricer=_charge(0.05))[
            "accounts"]["fusion"]["symbols"]["XAUUSD"]
        hit = rc.build([*calm[:n_calm], spike], pricer=_charge(0.05))[
            "accounts"]["fusion"]["symbols"]["XAUUSD"]
        sh, vr = hit["shrink"], hit["vs_replay"]
        assert method in sh["mean_method"] and method in vr["diff_method"]
        assert sh["raw_mean_cost_r"] > 1.0 and vr["raw_diff_mean_r"] > 1.0
        assert sh["realised_mean_cost_r"] == pytest.approx(0.05)
        assert vr["diff_mean_r"] == pytest.approx(0.0, abs=1e-9)
        assert abs(vr["diff_mean_r"] - base["vs_replay"]["diff_mean_r"]) < 0.002
    # the allocator reads the winsorized difference, not the raw one
    doc = rc.build([*calm, spike], pricer=_charge(0.05))
    surface, registry = _surface("XAUUSD", {1: 5.0}, pooled=5.0)
    model = ec.costs_for([{"name": "XAUUSD_asia_brk", "symbol": "XAUUSD"}], surface,
                         registry=registry)
    row = ec.apply_realised(model, doc, symbols={"XAUUSD_asia_brk": "XAUUSD"})["sleeves"][
        "XAUUSD_asia_brk"]
    assert row["realised"]["diff_mean_r"] == pytest.approx(0.0, abs=1e-9)
    assert row["cost_bias_r"] == pytest.approx(0.0, abs=1e-6)


def test_each_fill_records_the_replay_charge_and_the_difference() -> None:
    rows = [_fill("fusion", "EURUSD", 0.01, 0.0001, 0.01, -0.01, f"r{i}") for i in range(5)]
    vr = rc.build(rows, pricer=_charge(0.02))["accounts"]["fusion"]["symbols"]["EURUSD"][
        "vs_replay"]
    # realised 0.01 + 0.0001/0.01 + 0.01 = 0.03R against a 0.02R charge
    assert vr["status"] == "MEASURED" and vr["n"] == 5
    assert vr["charged_mean_r"] == pytest.approx(0.02)
    assert vr["realised_mean_r"] == pytest.approx(0.03)
    assert vr["diff_mean_r"] == pytest.approx(0.01)
    assert all(f["replay_charged_cost_r"] == pytest.approx(0.02)
               and f["diff_r"] == pytest.approx(0.01) for f in vr["fills"])


def test_the_replay_charge_is_the_gauntlets_pooled_cost_over_the_trades_own_stop() -> None:
    """Imported, never copied: external_gauntlet.costs_for on today's registry row. XAUUSD at
    14.5 pts x 0.01 x 100 = 14.50 per lot of spread, plus 2 x 2.00 commission carried by
    quote_per_account (100 x 0.01 / tick_value 1.0 = 1.0) -> 18.50 / 100 = 0.185 in price, over a
    10.0 stop -> 0.0185R. The fill's stop distance is stop_frac x fill_price."""
    meta = {"XAUUSD": {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
                       "median_spread_pts": 14.5}}
    price = _REAL_PRICER(meta)
    got, basis = price({"symbol": "XAUUSD", "fill_price": 2000.0, "stop_frac": 10.0 / 2000.0})
    assert got == pytest.approx(0.0185) and "costs_for" in basis
    # a symbol the registry does not price, and a fill with no stop geometry, are UNMEASURED
    assert price({"symbol": "NOPE", "fill_price": 1.0, "stop_frac": 0.01})[0] is None
    assert price({"symbol": "XAUUSD", "fill_price": 2000.0, "stop_frac": None})[0] is None


def test_hour_buckets_publish_only_when_they_hold_enough_fills() -> None:
    rows = [_fill("fusion", "EURUSD", 0.1, 0.0, 0.01, 0.0, f"r{i}") for i in range(5)]
    rows.append(_fill("fusion", "EURUSD", 0.1, 0.0, 0.01, 0.0, "late",
                      decided="2026-11-01T13:00:00+00:00"))
    hours = rc.build(rows)["accounts"]["fusion"]["symbols"]["EURUSD"]["hours_utc"]
    assert list(hours) == ["04"] and hours["04"]["n"] == 5


def test_no_fills_is_unmeasured_never_a_zero_cost() -> None:
    doc = rc.build([], fill_report=None)
    assert doc["status"] == "UNMEASURED" and doc["n_cells"] == 0
    for book in ("fusion", "e8", "ftmo"):
        assert doc["accounts"][book]["status"] == "UNMEASURED"
        assert doc["accounts"][book]["n_fills"] == 0
    # a fill missing its commission has no whole round-trip cost: UNMEASURED, not cheaper
    partial = {**_fill("e8", "XAUUSD", 0.1, 0.001, 0.005, 0.0, "p"), "commission_r": None}
    cell = rc.build([partial])["accounts"]["e8"]["symbols"]["XAUUSD"]
    assert cell["status"] == "UNMEASURED" and cell["total_cost_r"]["mean"] is None
    assert cell["shrink"]["weight"] == 0.0 and "commission_r" in cell["why"]


def test_the_shrinkage_withheld_share_is_a_two_sided_missed_growth_line() -> None:
    """The lines are the ALLOCATOR's, measured against each sleeve's MODELLED bias (0.05R for
    EURUSD here), and the realised-cost report publishes none of its own."""
    rows = [_fill("fusion", "EURUSD", 0.30, 0.0, 0.01, 0.0, "up")]
    assert "missed_growth" not in rc.build(rows)
    up = ec.apply_realised(_modelled(), _realised(0.30, 20), symbols=_SYMS)
    down = ec.apply_realised(_modelled(), _realised(-0.03, 20), symbols=_SYMS)
    (lu,) = up["summary"]["realised"]["missed_growth"]
    (ld,) = down["summary"]["realised"]["missed_growth"]
    assert lu["direction"] == "cost_up" and lu["modelled_bias_r"] == pytest.approx(0.05)
    assert lu["gap_r"] == pytest.approx(0.25) and lu["withheld_r"] == pytest.approx(0.125)
    assert ld["direction"] == "cost_down" and ld["gap_r"] == pytest.approx(-0.08)
    assert ld["withheld_r"] == pytest.approx(-0.04)
    assert all(x["verdict"] == "UNMEASURED" for x in (lu, ld))
    # missed_growth reads them off the allocator's artifact, never off REALISED_COST.json
    from research import missed_growth as mg
    got = mg.realised_cost_lines({"execution_cost_realised": up["summary"]["realised"]})
    assert got["verdict"] == "UNMEASURED" and got["lines"] == [lu]
    assert "pf_allocation.json" in got["source"]
    assert mg.realised_cost_lines({})["verdict"] == "UNMEASURED"
    none = ec.apply_realised(_modelled(), _realised(0.30, 4, status="UNMEASURED"),
                             symbols=_SYMS)
    nb = mg.realised_cost_lines({"execution_cost_realised": none["summary"]["realised"]})
    assert nb["verdict"] == "UNMEASURED" and "realised-minus-replay" in nb["why"]


# --------------------------------------------------------------------------- the allocator
def _realised(diff: float, n: int, account: str = "fusion", symbol: str = "EURUSD",
              age_h: float = 1.0, status: str = "MEASURED",
              charged: float = 0.02) -> dict[str, Any]:
    at = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    return {"measured_at": at, "status": "MEASURED",
            "accounts": {account: {"symbols": {symbol: {
                "status": "MEASURED", "shrink": {"n": n, "realised_mean_cost_r": charged + diff},
                "vs_replay": {"status": status, "n": n, "diff_mean_r": diff,
                              "charged_mean_r": charged, "realised_mean_r": charged + diff,
                              "why": "" if status == "MEASURED" else "UNMEASURED: test"}}}}}}


def _surface(symbol: str, hours: dict[int, float], pooled: float
             ) -> tuple[dict[str, Any], dict[str, Any]]:
    """(cost surface, registry) with MEASURED broker-hour cells for one symbol and a registry
    spread that carries provenance, so `costs_for` prices the sleeve from the surface."""
    surface = {"symbols": {symbol: {"pooled_median_spread_pts": pooled, "hours": {
        str(h): {"status": "MEASURED", "p50": v} for h, v in hours.items()}}}}
    registry = {symbol: {"median_spread_pts": pooled,
                         "_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}
    return surface, registry


def _modelled(hours: dict[int, float] | None = None, pooled: float = 10.0) -> dict[str, Any]:
    """EURUSD priced off a MEASURED surface cell at its asia fill hour (01): p50 20 against the
    pooled 10 -> modelled bias 0.05 x (2 - 1) = 0.05R. GBPUSD is unpriced: modelled bias 0."""
    surface, registry = _surface("EURUSD", hours or {1: 20.0, 2: 5.0}, pooled)
    return {**ec.costs_for([{"name": "EURUSD_asia_brk", "symbol": "EURUSD"},
                            {"name": "GBPUSD_asia_brk", "symbol": "GBPUSD"}],
                           surface, registry=registry)}


_SYMS = {"EURUSD_asia_brk": "EURUSD", "GBPUSD_asia_brk": "GBPUSD"}


def test_replay_charged_002_realised_003_is_dearer_never_a_credit() -> None:
    """THE AUDITOR'S CASE. A sleeve whose replay already netted 0.02R and whose real fills cost
    0.03R is DEARER than modelled, wherever the surface's 0.05 x ratio sits. Measured against the
    scalar it read 0.03 - 0.05, a credit; against the replay's own charge it is +0.01R."""
    rows = [_fill("fusion", "EURUSD", 0.01, 0.0001, 0.01, -0.01, f"r{i}") for i in range(5)]
    doc = rc.build(rows, pricer=_charge(0.02))
    flat = _modelled({1: 10.0, 2: 10.0})                 # ratio 1: 0.05R surface cost, bias 0
    assert flat["sleeves"]["EURUSD_asia_brk"]["cost_r"] == pytest.approx(ec.BASE_COST_R)
    row = ec.apply_realised(flat, doc, symbols=_SYMS)["sleeves"]["EURUSD_asia_brk"]
    assert row["source"] == "REALISED"
    assert row["cost_bias_r"] > 0
    assert row["cost_bias_r"] == pytest.approx(5 / 25 * 0.01)
    # and on a sleeve the surface prices dearer still (0.05 x 2), never below its modelled bias
    dear = ec.apply_realised(_modelled(), doc, symbols=_SYMS)["sleeves"]["EURUSD_asia_brk"]
    assert dear["cost_bias_r"] > 0
    assert dear["cost_bias_r"] == pytest.approx(0.2 * 0.01 + 0.8 * 0.05)


def test_replay_charged_005_realised_003_over_five_fills_is_a_credit() -> None:
    rows = [_fill("fusion", "GBPUSD", 0.01, 0.0001, 0.01, -0.01, f"r{i}") for i in range(5)]
    doc = rc.build(rows, pricer=_charge(0.05))
    out = ec.apply_realised(_modelled(), doc, symbols=_SYMS)
    row = out["sleeves"]["GBPUSD_asia_brk"]
    # modelled bias 0 (unpriced); w = 5/25; diff -0.02 -> -0.004R, a CREDIT
    assert row["source"] == "REALISED" and row["cost_bias_r"] == pytest.approx(-0.004)
    assert out["summary"]["realised"]["n_cheaper"] == 1


def test_four_fills_move_nothing() -> None:
    rows = [_fill("fusion", "GBPUSD", 0.01, 0.0001, 0.01, -0.01, f"r{i}") for i in range(4)]
    doc = rc.build(rows, pricer=_charge(0.05))
    vr = doc["accounts"]["fusion"]["symbols"]["GBPUSD"]["vs_replay"]
    assert vr["status"] == "UNMEASURED" and "5-fill floor" in vr["why"]
    base = _modelled()
    out = ec.apply_realised(base, doc, symbols=_SYMS)
    assert out["sleeves"] == base["sleeves"]
    assert out["summary"]["realised"]["no_baseline"]["GBPUSD_asia_brk"]["verdict"] == \
        ec.NO_BASELINE
    # and the allocator holds the floor itself, whatever a report claims
    lying = _realised(-0.5, 4, symbol="GBPUSD")
    assert ec.apply_realised(base, lying, symbols=_SYMS)["sleeves"] == base["sleeves"]


def test_one_unpriced_term_keeps_the_modelled_bias() -> None:
    rows = [_fill("fusion", "EURUSD", 0.01, 0.0001, 0.01, -0.01, f"r{i}") for i in range(6)]
    charges = iter([0.05, 0.05, 0.05, 0.05, 0.05, None])

    def price(_row: dict[str, Any]) -> tuple[float | None, str]:
        c = next(charges)
        return c, ("test" if c is not None else "UNMEASURED: not in the registry")
    doc = rc.build(rows, pricer=price)
    vr = doc["accounts"]["fusion"]["symbols"]["EURUSD"]["vs_replay"]
    assert vr["status"] == "UNMEASURED" and vr["n_unpriced_by_replay"] == 1
    assert "1 of 6" in vr["why"]
    base = _modelled()
    out = ec.apply_realised(base, doc, symbols=_SYMS)
    assert out["sleeves"]["EURUSD_asia_brk"] == base["sleeves"]["EURUSD_asia_brk"]
    assert out["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(0.05)
    # a realised term missing (no commission) is never counted and never becomes a zero
    partial = [{**r, "commission_r": None} for r in rows]
    vr = rc.build(partial, pricer=_charge(0.05))["accounts"]["fusion"]["symbols"]["EURUSD"][
        "vs_replay"]
    assert vr["status"] == "UNMEASURED" and vr["n"] == 0


def test_a_fresh_realised_cost_corrects_the_model_and_is_two_sided() -> None:
    base = _modelled()
    cheap = ec.apply_realised(base, _realised(-0.03, 20), symbols=_SYMS)
    row = cheap["sleeves"]["EURUSD_asia_brk"]
    # w = 0.5: 0.5 x -0.03 + 0.5 x 0.05 = 0.01R, below the 0.05R modelled bias
    assert row["source"] == "REALISED"
    assert row["cost_bias_r"] == pytest.approx(0.01)
    assert row["realised"]["modelled_cost_bias_r"] == pytest.approx(0.05)
    dear = ec.apply_realised(base, _realised(0.30, 20), symbols=_SYMS)
    assert dear["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(0.175)
    # the sleeve with no realised cell keeps its modelled entry untouched
    assert cheap["sleeves"]["GBPUSD_asia_brk"] == base["sleeves"]["GBPUSD_asia_brk"]
    blk = cheap["summary"]["realised"]
    assert blk["usable"] and blk["n_realised"] == 1 and blk["n_cheaper"] == 1
    assert dear["summary"]["realised"]["n_dearer"] == 1
    assert "BASE_COST_R" not in json.dumps(blk)


def test_a_stale_or_absent_realised_cost_falls_back_to_the_model_and_says_so() -> None:
    base = _modelled()
    stale = ec.apply_realised(base, _realised(-0.01, 500, age_h=49.0), symbols=_SYMS)
    assert stale["sleeves"] == base["sleeves"]
    assert stale["summary"]["realised"]["fallback"] == "MODELLED"
    assert "STALE" in stale["summary"]["realised"]["why"]
    absent = ec.apply_realised(base, None, symbols=_SYMS)
    assert absent["sleeves"] == base["sleeves"] and not absent["summary"]["realised"]["usable"]
    unmeasured = ec.apply_realised(base, {**_realised(-0.01, 5), "status": "UNMEASURED"},
                                   symbols=_SYMS)
    assert unmeasured["sleeves"] == base["sleeves"]


def test_no_surface_still_corrects_where_the_difference_is_measured() -> None:
    """The surface is the MODEL, not the anchor: with none, every modelled bias is 0 and the
    measured realised-minus-replay difference corrects it; an unmeasured one moves nothing."""
    blank = ec.costs_for([{"name": "EURUSD_asia_brk", "symbol": "EURUSD"}], None)
    out = ec.apply_realised(blank, _realised(-0.02, 20), symbols=_SYMS)
    assert out["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(-0.01)
    none = ec.apply_realised(blank, _realised(-0.02, 20, status="UNMEASURED"), symbols=_SYMS)
    assert none["sleeves"] == blank["sleeves"]
    assert none["summary"]["realised"]["verdict"] == ec.NO_BASELINE
    assert none["summary"]["realised"]["missed_growth"] == []


def test_the_allocator_reads_only_its_own_account() -> None:
    base = _modelled()
    other = ec.apply_realised(base, _realised(-0.01, 100, account="ftmo"), symbols=_SYMS)
    assert other["sleeves"] == base["sleeves"]
    mine = ec.apply_realised(base, _realised(-0.01, 100, account="ftmo"), symbols=_SYMS,
                             account="ftmo")
    assert mine["sleeves"]["EURUSD_asia_brk"]["source"] == "REALISED"
    # per sleeve: a sleeve mapped to its own book reads that book alone
    per = ec.apply_realised(base, _realised(-0.01, 100, account="ftmo"), symbols=_SYMS,
                            accounts={"EURUSD_asia_brk": "ftmo"})
    assert per["sleeves"]["EURUSD_asia_brk"]["realised"]["account"] == "ftmo"
    assert per["summary"]["realised"]["accounts"] == ["ftmo", "fusion"]


def test_pf_allocator_cost_input_uses_the_realised_report(tmp_path: Path,
                                                          monkeypatch: Any) -> None:
    from research import pf_allocator as pa
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(pa, "BASE", tmp_path)
    (tmp_path / "reports" / "REALISED_COST.json").write_text(
        json.dumps(_realised(-0.03, 20)), "utf-8")
    # NO COST SURFACE: modelled bias 0, corrected by the measured difference alone
    doc = pa._execution_costs(["EURUSD_asia_brk"])
    assert doc["sleeves"]["EURUSD_asia_brk"]["source"] == "REALISED"
    assert doc["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(-0.015)
    surface, registry = _surface("EURUSD", {1: 20.0, 2: 5.0}, 10.0)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "cost_surface.json").write_text(json.dumps(surface), "utf-8")
    (tmp_path / "data" / "universe" / "universe.json").write_text(
        json.dumps({"symbols": registry}), "utf-8")
    doc = pa._execution_costs(["EURUSD_asia_brk"])
    assert doc["sleeves"]["EURUSD_asia_brk"]["source"] == "REALISED"
    assert doc["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(0.01)
    assert pa._EXEC_COST_META["usable"] is True
    assert pa._EXEC_COST_META["missed_growth"][0]["modelled_bias_r"] == pytest.approx(0.05)
    (tmp_path / "reports" / "REALISED_COST.json").write_text(
        json.dumps(_realised(-0.03, 20, age_h=72.0)), "utf-8")
    doc = pa._execution_costs(["EURUSD_asia_brk"])
    # stale: the modelled surface entry stands (its own 0.05R under-charge), unblended
    assert doc["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(0.05)
    assert doc["sleeves"]["EURUSD_asia_brk"]["source"] == "MEASURED"
    assert pa._EXEC_COST_META["fallback"] == "MODELLED"


def test_a_broken_execution_cost_import_degrades_to_unpriced(tmp_path: Path,
                                                             monkeypatch: Any) -> None:
    from research import pf_allocator as pa
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setitem(sys.modules, "libs.portfolio.execution_cost", None)
    doc = pa._execution_costs(["EURUSD_asia_brk"])
    assert doc["sleeves"] == {}
    assert "execution cost unimportable" in doc["summary"]["verdict"]


def test_a_negative_cost_bias_raises_the_sleeves_worlds() -> None:
    """Two-sided to the last step: robust_elog must not clip a realised credit back to zero."""
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds
    r = np.random.default_rng(0).normal(0.05, 1.0, size=600)
    cfg = WorldConfig(n_worlds=64, n_rows=250, seed=1)
    flat = sample_worlds([SleeveEvidence(name="a", daily_r=r, cost_r=0.05)], cfg)
    cheap = sample_worlds([SleeveEvidence(name="a", daily_r=r, cost_r=0.05,
                                          cost_bias_r=-0.05)], cfg)
    assert cheap.r[:, :, 0].mean() > flat.r[:, :, 0].mean()


# --------------------------------------------------------------------------- wiring + liveness
def test_realised_cost_is_a_registered_hourly_leg_with_a_contract_and_a_layer() -> None:
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc
    assert "realised_cost" in hc.CORE_LEGS
    assert hc.LEG_DEPARTMENT["realised_cost"] == "execution"
    assert LEG_LAYER["realised_cost"] == "execution"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("realised_cost"' in src and '"realised_cost": rlc' in src
    contracts = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))
    assert contracts["legs"]["realised_cost"]["metric"]["organ"] == "report:REALISED_COST.json"
    from libs.portfolio.capital_modifiers import REGISTRY
    mod = {m.name: m for m in REGISTRY}["realised_execution_cost"]
    assert mod.kind == "two_sided" and mod.hi > 1.0


def test_liveness_is_red_when_stale_or_empty_while_fills_flow() -> None:
    flowing = {"realised_fills": 30}
    fresh = rc.build([_fill("fusion", "XAUUSD", 0.01, 0.0001, 0.005, -0.01, "a")])
    assert hb.realised_cost_liveness(fresh, flowing)["verdict"] == hb.GREEN
    stale = {**fresh, "measured_at": (datetime.now(tz=UTC) - timedelta(hours=5)).isoformat()}
    assert hb.realised_cost_liveness(stale, flowing)["verdict"] == hb.RED
    empty = rc.build([])
    assert hb.realised_cost_liveness(empty, flowing)["verdict"] == hb.RED
    assert hb.realised_cost_liveness(None, flowing)["verdict"] == hb.RED
    assert hb.realised_cost_liveness(None, None)["verdict"] == hb.UNMEASURED
    assert hb.realised_cost_liveness(empty, {"realised_fills": 0})["verdict"] == hb.GREEN


def test_health_board_carries_the_liveness_row(tmp_path: Path) -> None:
    rep, up = tmp_path / "REALISED_COST.json", tmp_path / "FILL_RECORDER.json"
    up.write_text(json.dumps({"realised_fills": 3}), "utf-8")
    doc = hb.build(runtime=tmp_path / "a", events=tmp_path / "b", acceptance=tmp_path / "c",
                   stall=tmp_path / "d", readers={}, liveness={"realised_cost": (rep, up)})
    row = next(o for o in doc["organs"] if o["organ"] == "liveness:realised_cost")
    assert row["verdict"] == hb.RED and doc["desk_verdict"] == hb.RED


# --------------------------------------------------------------------------- prop ledger rows
def _e8_ledger_row(pid: int, entry_order: int, *, book: str = "e8", entry: float = 4000.6,
                   intended: float = 4000.0, sl: float = 3990.0, direction: int = 1,
                   r_multiple: float | None = 1.4) -> dict[str, Any]:
    """A closed position in `prop/e8_fills.compose_fills`' exact prop-fills-v1 shape (#589)."""
    return {
        "schema": "prop-fills-v1", "book": book, "venue": "tradelocker", "lane": f"{book}_gold",
        "provenance": "e8_fills:tradelocker_order_history",
        "recorded_at": "2026-11-02T10:00:00+00:00", "time": "2026-11-02T09:00:00.000+00:00",
        "sleeve": "gold_asia", "window": "asia", "symbol": "XAUUSD",
        "entry_side": 0 if direction == 1 else 1, "side": 1 if direction == 1 else 0,
        "direction": direction, "signal_hour_utc": "2026-11-02T04:00:00+00:00",
        "signal_hour_basis": "server_offset",
        "entry_time": "2026-11-02T05:10:00.000+00:00",
        "exit_time": "2026-11-02T09:00:00.000+00:00",
        "timestamp_basis": "tradelocker_order_ms_utc (lastModified of the filled order)",
        "venue_clock_skew_ms": 120, "entry_time_box_utc": "2026-11-02T04:00:02+00:00",
        "entry_price": entry, "intended_entry": intended, "sl": sl, "tp": intended + 20.0,
        "volume": 0.1, "fill_price": entry + 14.0, "exit_reason": "tp", "closed_by": "venue",
        "exit_magic": None, "exit_order_type": "limit", "r_multiple": r_multiple,
        "r_basis": "price: side x (exit - entry) / |entry - sent stop|, gross of fees",
        "r_unreconstructible": False, "risk_quote": round(abs(entry - sl) * 0.1 * 100.0, 6),
        "pl_quote": 140.0, "quote_ccy": "USD", "pl_basis": "price",
        "commission": None, "swap": None, "fees": None, "fees_status": "UNMEASURED",
        "fees_measured": [], "fees_basis": "the TradeLocker order history (no fee fields)",
        "pl_net_quote": None, "position_id": pid, "entry_order": entry_order,
        "close_order": entry_order + 1, "n_exit_orders": 1, "server": "E8",
        "account_kind": "prop", "account_key": "k" * 16,
        "account_key_status": "keyed (gold_oco.tradelocker_oco_key)"}


#: `prop/e8_gold.py`'s SENT journal row (`_record`), identical on LIVE and on #589.
_E8_GOLD_SENT = {"at": "2026-11-02T04:00:02+00:00", "window": "asia", "side": "buy_stop",
                 "price": 4000.0, "sl": 3990.0, "tp": 4020.0, "lot": 0.1, "stop_dist": 10.0,
                 "risk_usd": 100.0, "sizing": "risk", "risk_frac": 0.005,
                 "risk_source": "allocator", "armed": True, "status": "SENT",
                 "order_id": 7300001}


def _filled_by_book(book: str) -> list[dict[str, Any]]:
    last: dict[str, dict[str, Any]] = {}
    for r in fc.read_rows(fr.CORPUS):
        last[fc.record_from_row(r).key] = r
    return [r for r in last.values() if r.get("book") == book and r["status"] == "FILLED"]


def test_e8_gold_ledger_row_joins_its_gold_intent_on_entry_order(tmp_path: Path,
                                                                 monkeypatch: Any) -> None:
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.E8_GOLD_INTENTS, [_E8_GOLD_SENT, {**_E8_GOLD_SENT, "adopted": True},
                                {**_E8_GOLD_SENT, "status": "RAIL_BLOCKED", "order_id": None}])
    _jsonl(fr.PROP_LEDGER, [_e8_ledger_row(88, 7300001)])
    doc = fr.build()
    e8 = doc["by_book"]["e8"]
    assert e8["n_intents"] == 1                       # one SENT order id, adoption deduped
    assert e8["matched_fills"] == 1 and e8["join_census"]["entry_order"] == 1
    assert e8["join_census"]["ledger_row"] == 0
    rows = _filled_by_book("e8")
    assert len(rows) == 1
    r = rows[0]
    assert r["join_keys"]["basis"] == "entry_order"
    assert r["intent_id"].startswith("e8|gold|asia|buy_stop")
    assert r["requested_price"] == 4000.0 and r["fill_price"] == 4000.6
    assert r["slip_r"] == pytest.approx(0.6 / 10.6)   # stop geometry of the filled position
    assert r["realized_r"] == pytest.approx(1.4)
    # no quote on the gold intent, and E8 fees are unread: neither is a zero
    assert r["spread_frac_at_decision"] is None and r["commission_r"] is None


@pytest.mark.parametrize("book", ["e8", "ftmo"])
def test_a_ledger_row_with_its_asked_price_is_self_sufficient(tmp_path: Path, monkeypatch: Any,
                                                              book: str) -> None:
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.PROP_LEDGER, [_e8_ledger_row(91, 555, book=book, entry=3989.5, intended=3990.0,
                                           sl=4000.0, direction=-1, r_multiple=-0.3)])
    doc = fr.build()
    blk = doc["by_book"][book]
    assert blk["matched_fills"] == 0
    assert blk["join_census"]["ledger_row"] == 1 and blk["join_census"]["deal_only"] == 0
    rows = _filled_by_book(book)
    assert len(rows) == 1
    r = rows[0]
    assert r["join"] == "ledger_row" and r["join_keys"]["basis"] == "ledger_row"
    # a short that filled 0.5 BELOW its sell stop got a worse price: slip is positive
    assert r["slip_frac"] == pytest.approx(0.5 / 3990.0)
    assert r["slip_r"] == pytest.approx(0.5 / 10.0)   # |intended_entry - sl|
    assert r["realized_r"] == pytest.approx(-0.3)
    assert r["decided_at"] == "2026-11-02T04:00:02+00:00"
    assert r["spread_frac_at_decision"] is None and r["spread_status"] == "UNMEASURED"
    assert r["record_id"].startswith(f"{book}|deal:91|")


def test_a_joined_position_is_never_also_written_from_its_ledger_row(tmp_path: Path,
                                                                     monkeypatch: Any) -> None:
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.E8_GOLD_INTENTS, [_E8_GOLD_SENT])
    # the same closed position recorded twice, plus one position no intent reaches
    _jsonl(fr.PROP_LEDGER, [_e8_ledger_row(88, 7300001), _e8_ledger_row(88, 7300001),
                            _e8_ledger_row(89, 999)])
    doc = fr.build()
    e8 = doc["by_book"]["e8"]
    assert e8["n_deals"] == 2
    assert e8["join_census"]["entry_order"] == 1 and e8["join_census"]["ledger_row"] == 1
    rows = _filled_by_book("e8")
    assert sorted(str(r["join_keys"]["position_id"]) for r in rows) == ["88", "89"]
    # a later pass that joins position 89 supersedes its earlier ledger_row key
    _jsonl(fr.E8_GOLD_INTENTS, [_E8_GOLD_SENT, {**_E8_GOLD_SENT, "order_id": 999}])
    fr.build()
    rows = _filled_by_book("e8")
    assert sorted(str(r["join_keys"]["position_id"]) for r in rows) == ["88", "89"]
    assert {r["join_keys"]["basis"] for r in rows} == {"entry_order"}
    fills, _census = rc.latest_fills(fc.read_rows(fr.CORPUS))
    assert len([f for f in fills if f["_book"] == "e8"]) == 2


def test_a_spreadless_prop_fill_leaves_total_cost_unmeasured(tmp_path: Path,
                                                             monkeypatch: Any) -> None:
    _point_recorder(monkeypatch, tmp_path)
    _jsonl(fr.PROP_LEDGER, [_e8_ledger_row(91, 555), _e8_ledger_row(92, 556, book="ftmo")])
    fr.build()
    doc = rc.build(fc.read_rows(fr.CORPUS), fill_report={})
    for book in ("e8", "ftmo"):
        acct = doc["accounts"][book]
        assert acct["n_fills"] == 1
        c = acct["symbols"]["XAUUSD"]
        assert c["slip_r"]["n"] == 1                  # the slippage IS measured
        assert c["total_cost_r"]["status"] == rc.UNMEASURED
        assert c["status"] == rc.UNMEASURED and c["shrink"]["weight"] == 0.0
        assert acct["status"] == rc.UNMEASURED
    assert doc["status"] == rc.UNMEASURED and doc["n_cells_measured"] == 0
