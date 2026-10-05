"""Route variants at batch cost while preserving instrument/family policy decisions."""
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import merge_hypotheses as merge  # noqa: E402


def test_variants_share_routing_lookup_but_different_families_do_not():
    calls = []

    def refusal(symbol, family):
        calls.append((symbol, family))
        return "event" if family == "formula" else ""

    rows = [{"symbol": "AAPL", "family": family, "params": {"n": n}}
            for family in ("formula", "cross_asset_residual") for n in range(1000)]
    admitted, event, counts, _ = merge.split_by_lane(rows, refusal, "now")
    assert len(admitted) == len(event) == 1000
    assert {row["family"] for row in admitted} == {"cross_asset_residual"}
    assert counts == {"event": 1000}
    assert calls == [("AAPL", "formula"), ("AAPL", "cross_asset_residual")]


def test_next_batch_rechecks_changed_policy():
    policy = ["event"]
    def rows():
        return [{"symbol": "AAPL", "family": "formula"}]

    def refused(symbol, family):
        return policy[0]
    assert len(merge.split_by_lane(rows(), refused, "first")[1]) == 1
    policy[0] = ""
    assert len(merge.split_by_lane(rows(), refused, "next")[0]) == 1
