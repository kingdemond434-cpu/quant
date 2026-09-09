"""One SOURCE -> P&L path with counts, conversions and named breaks (Tier-1 item I6)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import build_zentech_state as bz  # noqa: E402


def _payload() -> dict:
    return {"pipeline": {"docket_candidates": 200, "gauntlet_last_judged": 100, "certified": 10,
                         "forward_clocks": 8, "promotion_ready": 2, "live": 1},
            "execution": {"deals": 6, "attributed_deals": 3},
            "account": {"today_pnl": -1.5}}


def test_the_path_is_twelve_stages_in_funnel_order_with_conversions() -> None:
    g = bz._observability_graph(_payload(), {"fractions": {"a": 0.3, "b": 0.0}},
                                {"rows_accounted": 5000, "executable_candidates": 400})
    ids = [n["id"] for n in g["nodes"]]
    assert ids == list(bz._STAGES) and ids[0] == "SOURCE" and ids[-1] == "PNL"
    by = {(e["from"], e["to"]): e for e in g["edges"]}
    assert by[("SOURCE", "COMPILER")]["conversion"] == 0.08
    assert by[("DOCKET", "GAUNTLET")]["conversion"] == 0.5
    assert by[("CERTIFIED", "FORWARD")]["conversion"] == 0.8
    assert by[("PROMOTER", "ALLOCATOR")]["conversion"] == 0.5, "one funded of two ready"
    assert by[("BROKER", "ATTRIBUTED")]["conversion"] == 0.5
    assert by[("ATTRIBUTED", "PNL")]["conversion"] is None, "P&L is money, not a count"
    assert g["breaks"] == [] and g["observed"] == 12 and g["of"] == 12


def test_an_unobserved_stage_is_a_named_break_not_a_zero() -> None:
    p = _payload()
    p["execution"] = {}
    g = bz._observability_graph(p, {}, {})
    assert "BROKER" in g["breaks"] and "ATTRIBUTED" in g["breaks"] and "SOURCE" in g["breaks"]
    edge = next(e for e in g["edges"] if e["to"] == "BROKER")
    assert edge["conversion"] is None and "unobserved" in edge["break"]
    assert g["observed"] == 12 - len(g["breaks"])
    for n in g["nodes"]:
        assert n["from"], "every count names the artifact it came from"


def test_funded_reads_whatever_the_allocator_calls_its_map() -> None:
    assert bz._funded({"allocations": {"a": {"fraction": 0.2}, "b": {"fraction": 0}}}) == 1
    assert bz._funded({"weights": {"a": 0.1, "b": 0.1}}) == 2
    assert bz._funded({}) is None
