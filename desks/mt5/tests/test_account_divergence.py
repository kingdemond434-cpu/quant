"""Cross-account divergence: one signal on several accounts, compared on realised R and cut."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mt5desk import account_divergence as ad


def test_the_measured_ftmo_gap_cuts_to_about_a_third() -> None:
    mult, why = ad.multiplier([-0.073] * 8, [0.164] * 30)
    assert mult == pytest.approx((8 * -0.073 + 10 * 0.164) / 18 / 0.164)
    assert 0.35 < mult < 0.37 and "x0.36" in why


def test_a_matching_copy_keeps_its_whole_fraction_and_never_gains() -> None:
    assert ad.multiplier([0.2] * 20, [0.164] * 30)[0] == 1.0
    assert ad.multiplier([0.164] * 20, [0.164] * 30)[0] == pytest.approx(1.0)


def test_too_few_fills_or_a_non_positive_reference_cut_nothing() -> None:
    assert ad.multiplier([-1.0] * 2, [0.2] * 30)[0] == 1.0
    assert ad.multiplier([-1.0] * 8, [0.2] * 5)[0] == 1.0
    assert ad.multiplier([-1.0] * 8, [-0.1] * 30)[0] == 1.0


def test_a_disastrous_copy_goes_to_zero_not_below() -> None:
    assert ad.multiplier([-1.0] * 50, [0.1] * 30)[0] == 0.0


def test_the_report_flags_every_diverged_account(tmp_path, monkeypatch) -> None:
    rows = ([{"book": "ftmo", "sleeve": "gold_asia", "r_multiple": -0.5}] * 6
            + [{"book": "e8", "sleeve": "gold_asia", "r_multiple": 0.3}] * 12
            + [{"book": "fusion", "sleeve": "eurusd_x", "r": 0.1}] * 4
            + [{"book": "ftmo", "sleeve": "only_here", "r_multiple": 1.0}] * 4
            + ["not json", {"book": "e8", "sleeve": "gold_asia", "r_multiple": None}])
    led = tmp_path / "l.jsonl"
    led.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows), "utf-8")
    monkeypatch.setattr(ad, "LEDGERS", (led, tmp_path / "missing.jsonl"))
    doc = ad.report(tmp_path / "out.json")
    (row,) = doc["rows"]
    assert (row["account"], row["reference"], row["n"], row["n_ref"]) == ("ftmo", "e8", 6, 12)
    assert row["diverged"] and doc["diverged"] == ["ftmo/gold_asia"]
    assert ad.copy_multiplier(account="ftmo", sleeve="gold_asia")[0] < 1.0
    assert ad.copy_multiplier(account="ftmo", sleeve="none")[0] == 1.0


def test_a_row_named_only_by_its_lane_or_provenance_still_maps_to_its_account() -> None:
    assert ad._account({"server": "GooeyTrade-Live", "lane": "e8_gold"}) == "e8"
    assert ad._account({"server": "Fusion-Live"}) == "fusion-live"
    assert ad._account({"lane": "e8_gold", "sleeve": "gold_asia"}) == "e8"
    assert ad._account({"provenance": "e8_gold:tradelocker"}) == "e8"
    assert ad._account({"lane": "gateway"}) is None
