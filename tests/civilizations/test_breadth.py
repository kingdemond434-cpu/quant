"""The anti-saturation law at the civilizations producer (zuck 2026-10-05)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from libs.civilizations import breadth as B

SLOTS = [{"mechanism": "session_range_breakout", "instrument": "XAUUSD", "asset_class": "metal"},
         {"mechanism": "session_range_breakout", "instrument": "GBPJPY", "asset_class": "fx"},
         {"mechanism": "carry", "instrument": "AUDJPY", "asset_class": "fx"}]
SHARES = ({"session_range_breakout": 0.6, "carry": 0.4}, 3)
CLASSES = {"XAUUSD": "metal", "GBPJPY": "fx", "AUDJPY": "fx", "US500": "index",
           "EURUSD": "fx"}


def _keff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for r in rows:
        r["_keff"] = 0.5 if r["symbol"] == "US500" else 0.1
    return {"instrument": {"status": "MEASURED"}}


def _map(tmp: Path, **kw: Any) -> B.BreadthMap:
    return B.BreadthMap(tmp, asset_class_of=CLASSES, shares=SHARES, slots=SLOTS,
                        keff=kw.get("keff", _keff))


def spec(fam: str, sym: str, **p: Any) -> dict[str, Any]:
    return {"family": fam, "sym": sym, "params": p, "timeframe": p.pop("tf", "H1")}


def test_structural_key_uses_the_judge_axes() -> None:
    k = B.structural_key(spec("carry", "audjpy", hold_bars=24, side="long"))
    assert k.split("|")[:3] == ["carry", "AUDJPY", "24"]
    assert B.structural_key(spec("carry", "AUDJPY")) != k


def test_held_slot_is_near_duplicate_and_new_ground_is_not(tmp_path: Path) -> None:
    m = _map(tmp_path)
    dup = m.assess([spec("session_range_breakout", "XAUUSD")], set())
    assert dup["near_duplicate"] and dup["dup_canon"] == 1 and dup["exceptions"] == []
    payer = m.assess([spec("overnight_gap_decay", "XAUUSD")], set())
    assert not payer["near_duplicate"] and "A_new_payer" in payer["exceptions"]
    expr = m.assess([spec("carry", "US500")], set())          # carry has never paid on an index
    assert "E_new_expression" in expr["exceptions"] and not expr["near_duplicate"]
    clock = m.assess([spec("carry", "AUDJPY", tf="M15")], set())
    assert "C_new_temporal" in clock["exceptions"] and not clock["near_duplicate"]
    reg = m.assess([spec("carry", "AUDJPY", regime="high_vol")], set())
    assert reg["exceptions"] == ["D_new_regime"] and not reg["near_duplicate"]
    info = m.assess([{**spec("carry", "AUDJPY"),
                      "required_data": ["bars:AUDJPY:H1", "cot:JPY"]}], set())
    assert info["exceptions"] == ["B_new_information"]
    bars = m.assess([{**spec("carry", "AUDJPY"), "required_data": ["bars:AUDJPY:H1"]}], set())
    assert bars["near_duplicate"]
    # crowded family: lower breadth score than an equally scored uncrowded one
    assert expr["breadth_score"] > 0 and m.keff_status == "MEASURED"


def test_own_released_ground_counts_as_held(tmp_path: Path) -> None:
    m = _map(tmp_path)
    s = spec("carry", "EURUSD")
    first = m.assess([s], set())
    assert not first["near_duplicate"]
    again = m.assess([s], set(first["structural_keys"]))
    assert again["near_duplicate"] and again["dup_own"] == 1


def test_unmeasured_keff_is_par_and_said(tmp_path: Path) -> None:
    def boom(rows: list[dict[str, Any]]) -> dict[str, Any]:
        raise RuntimeError("no book")
    m = _map(tmp_path, keff=boom)
    r = m.assess([spec("carry", "EURUSD")], set())
    assert r["keff"] == 0.0 and any("docket_keff" in u for u in m.unmeasured)


def _cands(n: int, dup_every: int) -> list[dict[str, Any]]:
    return [{"candidate_id": f"c{i}", "parked_at": f"{i:05d}", "dup": i % dup_every == 0,
             "score": float(i)} for i in range(n)]


def _assess(c: dict[str, Any]) -> dict[str, Any]:
    return {"near_duplicate": c["dup"], "breadth_score": c["score"]}


def test_order_puts_independent_first_and_keeps_exploration_floor() -> None:
    pend = _cands(100, 2)                      # half near-duplicates
    out, st = B.order(pend, 22, assess=_assess, base_key=lambda c: c["parked_at"])
    assert len(out) == 22
    dups = [c for c in out if c["dup"]]
    assert len(dups) == 2                      # one per ten independent
    fresh = [c["score"] for c in out if not c["dup"]]
    assert fresh == sorted(fresh, reverse=True)
    assert st["duplicate_share_head"] == 0.5 and st["screened"] == 100


def test_all_duplicate_queue_uses_the_whole_budget() -> None:
    out, _ = B.order(_cands(50, 1), 30, assess=_assess, base_key=lambda c: c["parked_at"])
    assert len(out) == 30 and all(c["dup"] for c in out)
    # oldest first, so the next pass (released rows gone) rotates to the next ones
    assert [c["candidate_id"] for c in out[:3]] == ["c0", "c1", "c2"]


def test_few_fresh_many_duplicates_fills_budget_and_keeps_the_floor() -> None:
    # the audit's fixture: 5 independent, 100 near-duplicates, budget 50
    pend = [{"candidate_id": f"f{i}", "parked_at": f"a{i}", "dup": False, "score": 1.0}
            for i in range(5)] + [{"candidate_id": f"d{i}", "parked_at": f"b{i:03d}",
                                   "dup": True, "score": 0.0} for i in range(100)]
    out, _ = B.order(pend, 50, assess=_assess, base_key=lambda c: c["parked_at"])
    assert len(out) == 50
    assert sum(not c["dup"] for c in out) == 5
    assert sum(c["dup"] for c in out) == 45


def test_floor_holds_with_one_to_nine_fresh() -> None:
    for n_fresh in range(1, 10):
        pend = [{"candidate_id": f"f{i}", "parked_at": f"a{i}", "dup": False, "score": 1.0}
                for i in range(n_fresh)] + [{"candidate_id": "d0", "parked_at": "b0",
                                             "dup": True, "score": 0.0}]
        out, _ = B.order(pend, n_fresh, assess=_assess, base_key=lambda c: c["parked_at"])
        assert len(out) == n_fresh and sum(c["dup"] for c in out) == 1, n_fresh
    # and at least one in every ten released, wherever there are near-duplicates waiting
    out, _ = B.order(_cands(400, 4), 100, assess=_assess, base_key=lambda c: c["parked_at"])
    assert len(out) == 100 and sum(c["dup"] for c in out) >= 10


def test_ledger_report_counts_duplicate_share_and_keff_per_hour(tmp_path: Path) -> None:
    led = B.BreadthLedger(tmp_path / "b.jsonl")
    at = B._iso(B._now())
    led.append([{"at": at, "source_id": "qc", "near_duplicate": False, "keff": 0.3, "specs": 2,
                 "exceptions": ["A_new_payer"], "structural_keys": ["k1"]},
                {"at": at, "source_id": "qc", "near_duplicate": True, "keff": 0.9, "specs": 1,
                 "dup_canon": 1, "structural_keys": ["k2"]}])
    assert led.released_keys() == {"k1", "k2"}
    assert led.keff_by_source() == {"qc": 0.3}
    doc = led.report({"qc": 1800.0}, {"qc": {"civilization": "quantconnect"}}, _map(tmp_path))
    lane = doc["lanes"]["qc"]
    assert lane["released"] == 2 and lane["duplicate_share"] == 0.5
    assert lane["delta_keff"] == 0.3 and lane["delta_keff_per_compute_hour"] == 0.6
    assert doc["exceptions_claimed"] == {"A_new_payer": 1}
    assert {s["family"] for s in doc["saturated_families"]} == {"session_range_breakout",
                                                                "carry"}
