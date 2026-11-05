"""Each account's sizing is charged its own venue's quoted spread (Judge, 2026-11-05)."""
from __future__ import annotations

import json
from pathlib import Path

from libs.portfolio import venue_cost as vc
from libs.portfolio.execution_cost import cost_ratio


def _quotes(path: Path, venue: str, at: str, point: float, readings: list[float]) -> None:
    path.write_text(json.dumps({
        "at": at, "venue": venue,
        "symbols": {"EURUSD": {"point": point, "live_spread_pts": 10}},
        "spread_by_hour_utc": {"EURUSD": {"07": [[at, px] for px in readings]}}}), "utf-8")


def test_each_account_reads_its_own_venue_file_never_the_max(tmp_path: Path) -> None:
    _quotes(tmp_path / "cost_truth_quotes.fusion_markets_pty_ltd.json", "fusion_markets_pty_ltd",
            "2026-11-05T06:00:00+00:00", 0.00001, [0.00008, 0.00010, 0.00012])
    _quotes(tmp_path / "cost_truth_quotes.ftmo_s_r_o.json", "ftmo_s_r_o",
            "2026-11-05T06:00:00+00:00", 0.00001, [0.00020, 0.00022, 0.00024])
    _quotes(tmp_path / "cost_truth_quotes.max.json", "max", "2026-11-05T06:00:00+00:00",
            0.00001, [0.0009] * 3)
    fus, _ = vc.venue_quotes(tmp_path, "fusion")
    ftmo, _ = vc.venue_quotes(tmp_path, "ftmo")
    assert fus["venue"].startswith("fusion") and ftmo["venue"].startswith("ftmo")
    assert vc.venue_quotes(tmp_path, "e8") == (None, None)
    assert abs(vc.hour_spreads_pts(fus)["EURUSD"]["7"]["p50"] - 10.0) < 1e-9     # 0.0001 / 1e-5
    assert abs(vc.hour_spreads_pts(ftmo)["EURUSD"]["7"]["p50"] - 22.0) < 1e-9


def test_the_overlay_prices_the_fill_hour_at_the_venues_own_median(tmp_path: Path) -> None:
    surface = {"symbols": {"EURUSD": {"pooled_median_spread_pts": 8.0, "hours": {
        "7": {"status": "MEASURED", "p50": 9.0}, "8": {"status": "MEASURED", "p50": 9.5}}}}}
    _quotes(tmp_path / "cost_truth_quotes.fusion_markets.json", "fusion_markets",
            "2026-11-05T06:00:00+00:00", 0.00001, [0.00011, 0.00012, 0.00013])
    s = vc.account_surface(tmp_path, "fusion", surface)
    assert abs(s["symbols"]["EURUSD"]["hours"]["7"]["p50"] - 12.0) < 1e-9     # the quotes
    assert s["symbols"]["EURUSD"]["hours"]["8"]["p50"] == 9.5                  # untouched
    assert s["venue_quotes"]["cells_overlaid"] == 1
    assert surface["symbols"]["EURUSD"]["hours"]["7"]["p50"] == 9.0            # input not mutated
    r, _why, _d = cost_ratio(s, "EURUSD", 7, None)
    assert r is not None and abs(r - 12.0 / 8.0) < 1e-6


def test_too_few_readings_or_no_file_change_nothing(tmp_path: Path) -> None:
    surface = {"symbols": {"EURUSD": {"hours": {"7": {"status": "MEASURED", "p50": 9.0}}}}}
    _quotes(tmp_path / "cost_truth_quotes.fusion_x.json", "fusion_x",
            "2026-11-05T06:00:00+00:00", 0.00001, [0.0005, 0.0006])          # 2 < 3
    s = vc.account_surface(tmp_path, "fusion", surface)
    assert s["symbols"]["EURUSD"]["hours"]["7"]["p50"] == 9.0
    assert vc.account_surface(tmp_path / "none", "fusion", surface)["symbols"] == surface["symbols"]
    assert vc.account_surface(tmp_path / "none", "fusion", None) is None


def test_both_allocators_size_on_their_own_venue() -> None:
    root = Path(__file__).resolve().parents[2]
    pf = (root / "desks/mt5/research/pf_allocator.py").read_text(encoding="utf-8")
    pca = (root / "desks/mt5/research/prop_challenge_allocator.py").read_text(encoding="utf-8")
    assert 'account_surface(BASE / "data", "fusion", surface)' in pf
    assert 'account_surface(BASE / "data", "ftmo", _read_json(FTMO_SURFACE))' in pca
