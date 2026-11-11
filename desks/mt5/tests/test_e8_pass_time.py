"""E8 pass-time optimiser: caps enforced intraday, UNMEASURED on missing input, halved edge
is slower. Report only."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import e8_pass_time as ept  # noqa: E402
from prop import e8_guard  # noqa: E402


def test_caps_come_from_the_guard() -> None:
    assert ept.DAILY_DRAWDOWN == e8_guard.DAILY_DRAWDOWN
    assert ept.DAILY_PROFIT_CAP == e8_guard.DAILY_PROFIT_CAP
    assert ept.STAND_DOWN == e8_guard.STAND_DOWN
    assert ept.PROFIT_TARGET == e8_guard.PROFIT_TARGET


def test_daily_loss_is_judged_at_the_intraday_low_losses_first() -> None:
    # one day: a -2R leg then +5R; closes positive but the low is -2R * 1.5% = -3% <= -2.5%
    paths = np.array([[[-2.0, 5.0]]])
    out = ept.simulate(paths, np.array([0.015, 0.015]))
    assert out["p_daily"] == 1.0 and out["p_pass"] == 0.0


def test_stand_down_stops_later_legs() -> None:
    # first leg -1R at 1% hits the 0.75% stand-down; the +1R leg is not taken, so the day closes
    # at -1% and 12 such days reach the static floor (-10%) without a daily breach
    paths = np.tile(np.array([[[-1.0, 1.0]]]), (1, 12, 1))
    out = ept.simulate(paths, np.array([0.01, 0.01]))
    assert out["p_static"] == 1.0 and out["p_daily"] == 0.0


def test_profit_cap_strips_but_does_not_breach() -> None:
    # +10R a day at 1% = +10%/day, capped at +2%: passes on day 5, not day 1
    paths = np.full((1, 20, 1), 10.0)
    out = ept.simulate(paths, np.array([0.01]))
    assert out["p_pass"] == 1.0 and out["median_days"] == 5.0


def test_bracket_loss_is_clipped_at_two_gapped_stops() -> None:
    paths = np.array([[[-9.0]]])
    out = ept.simulate(paths, np.array([0.006]))
    assert out["p_daily"] == 0.0           # -3R * 0.6% = -1.8%, inside 2.5%


def test_halved_edge_raises_median_days() -> None:
    rng = np.random.default_rng(1)
    w = rng.normal(0.3, 1.0, (8, 256, 1))
    mu = w.mean(axis=(0, 1))
    from prop_challenge_allocator import draw_paths
    a = ept.optimise(draw_paths(w, 400, 300, 0), np.array([0.005]))
    b = ept.optimise(draw_paths(w - 0.5 * np.maximum(mu, 0), 400, 300, 0), np.array([0.005]))
    assert b["current"]["median_days"] > a["current"]["median_days"]


def test_unmeasured_on_missing_input(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ept, "CERT_BOOK", tmp_path / "absent.json")
    doc = ept.build(n_paths=10)
    assert doc["status"].startswith("UNMEASURED")
    assert doc["report_only"] is True and doc["consumer"] is None
    import kelly_survival as ks
    (tmp_path / "book.json").write_text('{"e8": {"gold_asia": 0.006}}')
    monkeypatch.setattr(ept, "CERT_BOOK", tmp_path / "book.json")
    monkeypatch.setattr(ks, "WORLDS", tmp_path / "no_worlds.npz")
    assert ept.build(n_paths=10)["status"].startswith("UNMEASURED")
