"""scalp_markout_rerank: an unusable book and a thin sleeve stay UNMEASURED."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research import scalp_markout_rerank as smr  # noqa: E402

CERTS = {"xau_scalp_a": {"exp_r": 0.30}, "xau_scalp_b": {"exp_r": 0.20}}


def test_unusable_book_leaves_every_row_unmeasured():
    slips = {"xau_scalp_a": [0.05] * 10}
    rows = smr.rerank(CERTS, slips, usable=False)
    assert all(r["verdict"] == "UNMEASURED" and r["net_exp_r"] is None for r in rows)
    assert "unusable" in rows[0]["why"]


def test_a_single_fill_is_not_a_measurement():
    rows = {r["name"]: r for r in smr.rerank(CERTS, {"xau_scalp_a": [0.05]})}
    assert rows["xau_scalp_a"]["verdict"] == "UNMEASURED"
    assert rows["xau_scalp_a"]["n_fills"] == 1 and "MIN_FILLS" in rows["xau_scalp_a"]["why"]


def test_happy_path_nets_own_slip_and_reranks():
    slips = {"xau_scalp_a": [0.25] * smr.MIN_FILLS, "xau_scalp_b": [0.0] * smr.MIN_FILLS}
    rows = {r["name"]: r for r in smr.rerank(CERTS, slips)}
    a, b = rows["xau_scalp_a"], rows["xau_scalp_b"]
    assert a["verdict"] == b["verdict"] == "MEASURED"
    assert abs(a["net_exp_r"] - 0.05) < 1e-12 and abs(b["net_exp_r"] - 0.20) < 1e-12
    assert b["rank_net"] == 1 and a["rank_net"] == 2 and a["rank_gross"] == 1
