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
    for name in ("INTENTS", "E8_INTENTS", "FTMO_EXEC_INTENTS", "FTMO_FOLLOWER_INTENTS",
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
    assert by_book["ftmo"]["slip_r"] == pytest.approx(0.5 / 10.0)
    assert by_book["ftmo"]["commission_r"] == pytest.approx(-0.7 / (10.0 * 0.1 * 100.0))
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


def test_the_shrinkage_is_n_over_n_plus_k_toward_the_model() -> None:
    assert rc.SHRINK_K == ec.REALISED_K == 20.0
    val, w = rc.shrink(0.25, 20, 0.05)
    assert w == pytest.approx(0.5) and val == pytest.approx(0.15)
    val, w = rc.shrink(0.25, 180, 0.05)
    assert w == pytest.approx(0.9) and val == pytest.approx(0.9 * 0.25 + 0.1 * 0.05)
    assert rc.shrink(None, 0, 0.05) == (None, 0.0)
    rows = [_fill("fusion", "EURUSD", 0.1, 0.0, 0.01, 0.0, f"r{i}") for i in range(5)]
    sh = rc.build(rows, fill_report=None)["accounts"]["fusion"]["symbols"]["EURUSD"]["shrink"]
    assert sh["weight"] == pytest.approx(5 / 25)
    assert sh["shrunk_cost_r"] == pytest.approx(0.2 * 0.1 + 0.8 * rc.PRIOR_COST_R)


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
    assert cell["shrink"]["shrunk_cost_r"] is None and "commission_r" in cell["why"]


def test_the_shrinkage_withheld_share_is_a_two_sided_missed_growth_line() -> None:
    rows = [_fill("fusion", "XAUUSD", 0.30, 0.0, 0.01, 0.0, "up"),
            _fill("ftmo", "EURUSD", -0.04, 0.0, 0.01, 0.0, "down")]
    lines = {(x["account"], x["symbol"]): x for x in rc.build(rows)["missed_growth"]}
    assert lines[("fusion", "XAUUSD")]["direction"] == "cost_up"
    assert lines[("ftmo", "EURUSD")]["direction"] == "cost_down"
    assert all(x["verdict"] == "UNMEASURED" for x in lines.values())


# --------------------------------------------------------------------------- the allocator
def _realised(mean: float, n: int, account: str = "fusion", symbol: str = "EURUSD",
              age_h: float = 1.0) -> dict[str, Any]:
    at = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    return {"measured_at": at, "status": "MEASURED",
            "accounts": {account: {"symbols": {symbol: {
                "status": "MEASURED", "shrink": {"n": n, "realised_mean_cost_r": mean}}}}}}


def _modelled() -> dict[str, Any]:
    return ec.costs_for([{"name": "EURUSD_asia_brk", "symbol": "EURUSD"},
                         {"name": "GBPUSD_asia_brk", "symbol": "GBPUSD"}], None)


_SYMS = {"EURUSD_asia_brk": "EURUSD", "GBPUSD_asia_brk": "GBPUSD"}


def test_a_fresh_realised_cost_replaces_the_model_and_is_two_sided() -> None:
    base = _modelled()
    assert base["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == 0.0
    cheap = ec.apply_realised(base, _realised(0.01, 20), symbols=_SYMS)
    row = cheap["sleeves"]["EURUSD_asia_brk"]
    # w = 0.5: 0.5 x 0.01 + 0.5 x 0.05 = 0.03R, so the bias is -0.02R -- a CREDIT
    assert row["source"] == "REALISED"
    assert row["cost_bias_r"] == pytest.approx(0.03 - ec.BASE_COST_R)
    assert row["cost_bias_r"] < 0.0
    dear = ec.apply_realised(base, _realised(0.25, 20), symbols=_SYMS)
    assert dear["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == pytest.approx(0.15 - 0.05)
    # the sleeve with no measured cell keeps its modelled entry untouched
    assert cheap["sleeves"]["GBPUSD_asia_brk"] == base["sleeves"]["GBPUSD_asia_brk"]
    blk = cheap["summary"]["realised"]
    assert blk["usable"] and blk["n_realised"] == 1 and blk["n_cheaper"] == 1
    assert dear["summary"]["realised"]["n_dearer"] == 1


def test_a_stale_or_absent_realised_cost_falls_back_to_the_model_and_says_so() -> None:
    base = _modelled()
    stale = ec.apply_realised(base, _realised(0.01, 500, age_h=49.0), symbols=_SYMS)
    assert stale["sleeves"] == base["sleeves"]
    assert stale["summary"]["realised"]["fallback"] == "MODELLED"
    assert "STALE" in stale["summary"]["realised"]["why"]
    absent = ec.apply_realised(base, None, symbols=_SYMS)
    assert absent["sleeves"] == base["sleeves"] and not absent["summary"]["realised"]["usable"]
    unmeasured = ec.apply_realised(base, {**_realised(0.01, 5), "status": "UNMEASURED"},
                                   symbols=_SYMS)
    assert unmeasured["sleeves"] == base["sleeves"]


def test_the_allocator_reads_only_its_own_account() -> None:
    base = _modelled()
    other = ec.apply_realised(base, _realised(0.01, 100, account="ftmo"), symbols=_SYMS)
    assert other["sleeves"] == base["sleeves"]
    mine = ec.apply_realised(base, _realised(0.01, 100, account="ftmo"), symbols=_SYMS,
                             account="ftmo")
    assert mine["sleeves"]["EURUSD_asia_brk"]["source"] == "REALISED"


def test_pf_allocator_cost_input_uses_the_realised_report(tmp_path: Path,
                                                          monkeypatch: Any) -> None:
    from research import pf_allocator as pa
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(pa, "BASE", tmp_path)
    (tmp_path / "reports" / "REALISED_COST.json").write_text(
        json.dumps(_realised(0.01, 20)), "utf-8")
    doc = pa._execution_costs(["EURUSD_asia_brk"])     # no cost surface on this tmp host
    assert doc["sleeves"]["EURUSD_asia_brk"]["source"] == "REALISED"
    assert doc["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] < 0.0
    assert pa._EXEC_COST_META["usable"] is True
    (tmp_path / "reports" / "REALISED_COST.json").write_text(
        json.dumps(_realised(0.01, 20, age_h=72.0)), "utf-8")
    doc = pa._execution_costs(["EURUSD_asia_brk"])
    assert doc["sleeves"]["EURUSD_asia_brk"]["cost_bias_r"] == 0.0
    assert pa._EXEC_COST_META["fallback"] == "MODELLED"


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
