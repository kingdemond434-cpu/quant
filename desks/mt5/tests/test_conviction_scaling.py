"""Conviction scaling (Build C row 143): two-sided, SHADOW byte-identical, promoted by code."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import conviction as cm  # noqa: E402
from libs.portfolio.capital_modifiers import REGISTRY  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, optimise  # noqa: E402


def _ev() -> list[SleeveEvidence]:
    rng = np.random.default_rng(7)
    n = 600
    common = rng.normal(0, 1, n)
    out = [
        # strong, long, corroborated by two independent mechanisms on EURUSD
        SleeveEvidence("EURUSD.breakout", rng.normal(0.25, 1.0, n), family="breakout",
                       symbol="EURUSD", n_trials=5),
        SleeveEvidence("EURUSD.carry", rng.normal(0.08, 1.0, n), family="carry",
                       symbol="EURUSD", n_trials=5),
        SleeveEvidence("EURUSD.gap", rng.normal(0.08, 1.0, n), family="gap", symbol="EURUSD",
                       n_trials=5),
        # lone, modest sleeves on their own instruments: the book's typical corroboration is 0
        SleeveEvidence("GBPUSD.x", rng.normal(0.05, 1.0, n), family="x", symbol="GBPUSD"),
        SleeveEvidence("AUDUSD.y", rng.normal(0.05, 1.0, n), family="y", symbol="AUDUSD"),
        # weak, selected from many trials, alone on its instrument
        SleeveEvidence("XAUUSD.fade", rng.normal(0.005, 1.0, n), family="fade",
                       symbol="XAUUSD", n_trials=2000),
        # a correlated copy: same instrument, another family, NOT independent
        SleeveEvidence("USDJPY.a", common + rng.normal(0.05, 0.2, n), family="a",
                       symbol="USDJPY", n_trials=50),
        SleeveEvidence("USDJPY.b", common + rng.normal(0.05, 0.2, n), family="b",
                       symbol="USDJPY", n_trials=50),
    ]
    return out


def test_two_sided_and_able_to_raise_capital() -> None:
    m = cm.MODIFIER
    # the growth fence's G4 rule, asserted on the row the sealed REGISTRY will carry
    assert m.kind == "two_sided" and m.lo < 1.0 < m.hi and m.hi >= 2.0
    assert m.name not in {x.name for x in REGISTRY} or m in REGISTRY


def test_strong_corroborated_sleeve_is_raised_and_weak_lone_one_cut() -> None:
    f = cm.conviction_factors(_ev())
    assert f["EURUSD.breakout"]["factor"] > 1.4
    assert f["EURUSD.breakout"]["agreement"] > 1.0
    assert f["EURUSD.breakout"]["agreeing"] == 2
    assert f["XAUUSD.fade"]["factor"] < 1.0
    # correlated same-instrument sleeves are not independent: they do not corroborate each other
    assert f["USDJPY.a"]["agreeing"] == 0
    assert all(cm.CONV_LO <= v["factor"] <= cm.CONV_HI for v in f.values())


def test_apply_conviction_never_touches_its_input() -> None:
    ev = _ev()
    before = [e.daily_r.tobytes() for e in ev]
    out = cm.apply_conviction(ev, cm.conviction_factors(ev))
    assert [e.daily_r.tobytes() for e in ev] == before
    assert out[0].daily_r.mean() > ev[0].daily_r.mean()


def _book(ev: list[SleeveEvidence]) -> bytes:
    cfg = WorldConfig(seed=0, n_worlds=32, n_rows=64)
    r = optimise(ev, hard_cap=0.2, target=0.2, cfg=cfg, max_per_sleeve=0.1, iterations=60)
    return json.dumps(r.heat, sort_keys=True).encode()


def test_shadow_leaves_live_fractions_byte_identical(tmp_path, monkeypatch) -> None:
    import pf_allocator as pa
    monkeypatch.setattr(cm, "CONVICTION_SWITCH", tmp_path / "CONVICTION_SCALING.json")
    pristine = _ev()
    ev = _ev()
    ids = [id(e) for e in ev]
    meta, base = pa.apply_conviction_scaling(ev)
    assert meta["mode"] == "SHADOW"
    assert [id(e) for e in ev] == ids and [id(e) for e in base] == ids
    assert [e.daily_r.tobytes() for e in ev] == [e.daily_r.tobytes() for e in pristine]
    assert _book(ev) == _book(pristine)
    # an unreadable or non-LIVE switch is SHADOW too
    (tmp_path / "CONVICTION_SCALING.json").write_text('{"mode": "live?"}', "utf-8")
    assert pa.apply_conviction_scaling(ev)[0]["mode"] == "SHADOW"


def test_live_switch_tilts_the_evidence(tmp_path, monkeypatch) -> None:
    import pf_allocator as pa
    sw = tmp_path / "CONVICTION_SCALING.json"
    sw.write_text(json.dumps({"mode": "LIVE"}), "utf-8")
    monkeypatch.setattr(cm, "CONVICTION_SWITCH", sw)
    monkeypatch.setattr(cm, "registered", lambda: True)
    ev = _ev()
    meta, base = pa.apply_conviction_scaling(ev)
    assert meta["status"] == "APPLIED" and meta["n_up"] >= 1 and meta["n_down"] >= 1
    assert ev[0].daily_r.mean() > base[0].daily_r.mean()


def test_promotion_rule_flips_both_ways_without_a_human() -> None:
    n = cm.CONV_PROMOTE_N
    assert cm.conviction_promotion([1e-4] * (n - 1), "SHADOW")["verdict"] == "UNMEASURED"
    up = cm.conviction_promotion([1e-4 + 1e-5 * (i % 3) for i in range(n)], "SHADOW")
    assert up["mode"] == "LIVE" and up["changed"]
    down = cm.conviction_promotion([-1e-4 - 1e-5 * (i % 3) for i in range(n)], "LIVE")
    assert down["mode"] == "SHADOW" and down["changed"]
    noisy = cm.conviction_promotion([(-1) ** i * 1e-3 for i in range(n)], "SHADOW")
    assert noisy["mode"] == "SHADOW" and not noisy["changed"]


def test_shadow_leg_writes_both_books_and_scores_forward(tmp_path, monkeypatch) -> None:
    import conviction_shadow as cs
    import pf_allocator as pa
    inputs = tmp_path / "conviction_inputs.npz"
    monkeypatch.setattr(pa, "CONVICTION_INPUTS", inputs)
    monkeypatch.setattr(cs, "INPUTS", inputs)
    monkeypatch.setattr(cs, "OUT", tmp_path / "CONVICTION_SHADOW.json")
    monkeypatch.setattr(cs, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(cm, "CONVICTION_SWITCH", tmp_path / "CONVICTION_SCALING.json")
    from dataclasses import replace
    # R per day at a scale a 20% book survives in every sampled world
    ev = [replace(e, daily_r=e.daily_r * 0.1) for e in _ev()]
    book = {"EURUSD.breakout": 0.08, "XAUUSD.fade": 0.07, "USDJPY.a": 0.05}
    assert "NOT written" not in pa.write_conviction_inputs(ev, book, {"generated_utc": "x"})
    monkeypatch.setattr(cs, "realised_by_day", lambda: {})
    doc = cs.run(budget_s=60)
    sh = doc["shadow"]
    assert sh["status"] == "MEASURED"
    assert abs(sum(sh["base_book"].values()) - 0.2) < 1e-3
    assert abs(sum(sh["conviction_book"].values()) - 0.2) < 1e-3
    assert sh["ex_ante"]["delta_mean_log_per_day"] <= 1e-9
    assert (tmp_path / "CONVICTION_SHADOW.json").exists()
    rows = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    # a second pass the same day does not ledger again
    cs.run(budget_s=60)
    assert len((tmp_path / "ledger.jsonl").read_text().splitlines()) == 1
    rec = {"day": "2026-01-01", "base_book": {"A": 0.1, "B": 0.1},
           "conviction_book": {"A": 0.15, "B": 0.05}, "factors": {"A": 1.5, "B": 0.5}}
    s = cs.score_record(rec, {"A": {"2026-01-02": 1.0}, "B": {"2026-01-02": -1.0}})
    assert s is not None and s["delta_logw"] > 0 and s["down_half_logw"] > 0
    assert cs.score_record(rec, {"A": {"2025-12-31": 1.0}}) is None
    assert not (tmp_path / "CONVICTION_SCALING.json").exists()


def test_missed_growth_bills_the_down_half_only_when_live(tmp_path, monkeypatch) -> None:
    from research import missed_growth as mg
    p = tmp_path / "CONVICTION_SHADOW.json"
    monkeypatch.setattr(mg, "CONVICTION", p)
    assert mg.published_conviction_lines()["verdict"] == mg.UNMEASURED
    p.write_text(json.dumps({"mode": "SHADOW", "down_half": {"value_logw_per_day": -1e-4}}))
    assert mg.published_conviction_lines()["verdict"] == mg.NOT_BINDING
    from datetime import UTC, datetime
    today = datetime.now(tz=UTC).date().isoformat()
    p.write_text(json.dumps({"mode": "LIVE", "down_half": {"value_logw_per_day": -1e-4,
                                                           "realised_day": today}}))
    got = mg.published_conviction_lines()
    assert got["sample"] is True and got["value_logw_per_day"] == pytest.approx(-1e-4)


def test_weekend_records_scored_on_one_monday_count_once() -> None:
    import conviction_shadow as cs
    book = {"base_book": {"A": 0.1}, "conviction_book": {"A": 0.2}, "factors": {"A": 1.5}}
    realised = {"A": {"2026-01-01": 0.5, "2026-01-05": 1.0}}       # Thu, then Monday
    recs = [{"day": d, **book} for d in ("2026-01-01", "2026-01-02", "2026-01-03",
                                         "2026-01-04")]            # Thu, Fri, Sat, Sun
    scored = [cs.score_record(r, realised) for r in recs]
    assert scored[0] is not None and scored[0]["realised_day"] == "2026-01-05"
    mondays = [s for s in scored if s and s["realised_day"] == "2026-01-05"]
    assert len(mondays) == 3                                       # Fri, Sat, Sun -> Monday
    kept = cs.distinct_realised(s for s in scored if s and s["status"] == "MEASURED")
    assert [k["realised_day"] for k in kept].count("2026-01-05") == 1
    assert next(k for k in kept if k["realised_day"] == "2026-01-05")["day"] == "2026-01-04"


def test_a_name_with_no_series_at_or_after_the_day_is_unmeasured_not_flat() -> None:
    import conviction_shadow as cs
    rec = {"day": "2026-01-01", "base_book": {"A": 0.1, "B": 0.1},
           "conviction_book": {"A": 0.2, "B": 0.0}, "factors": {"A": 1.5, "B": 0.5}}
    # B stopped being recorded before Jan 2: unmeasured, never a flat zero
    got = cs.score_record(rec, {"A": {"2026-01-02": 1.0}, "B": {"2025-12-31": -1.0}})
    assert got is not None and got["status"] == "UNMEASURED" and got["unmeasured"] == ["B"]
    assert "delta_logw" not in got
    # B still recorded (a later date) but flat on Jan 2: that IS a zero
    got = cs.score_record(rec, {"A": {"2026-01-02": 1.0}, "B": {"2026-01-03": -1.0}})
    assert got is not None and got["status"] == "MEASURED"
    assert got["delta_logw"] == pytest.approx(np.log1p(0.2) - np.log1p(0.1))


def test_live_switch_is_inert_until_the_sealed_registry_carries_the_row(tmp_path,
                                                                        monkeypatch) -> None:
    from libs.portfolio import capital_modifiers
    sw = tmp_path / "CONVICTION_SCALING.json"
    sw.write_text(json.dumps({"mode": "LIVE"}), "utf-8")
    monkeypatch.setattr(cm, "CONVICTION_SWITCH", sw)
    monkeypatch.setattr(capital_modifiers, "REGISTRY",
                        tuple(m for m in capital_modifiers.REGISTRY if m.name != "conviction"))
    assert cm.switch_mode() == "LIVE"            # the clock still reads the file
    assert not cm.registered() and cm.conviction_mode() == "SHADOW"
    monkeypatch.setattr(capital_modifiers, "REGISTRY",
                        (*capital_modifiers.REGISTRY, cm.MODIFIER))
    assert cm.registered() and cm.conviction_mode() == "LIVE"


def test_promotion_needs_two_standard_errors_and_records_its_bar() -> None:
    n = cm.CONV_PROMOTE_N
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, n)
    x = (x - x.mean()) / x.std(ddof=1)               # mean 0, sd 1 -> se = 1/sqrt(n)
    se = 1 / np.sqrt(n)
    one_se = list(x + 1.5 * se)                      # mean - 1 se > 0, mean - 2 se < 0
    got = cm.conviction_promotion(one_se, "SHADOW")
    assert got["mode"] == "SHADOW" and not got["changed"]
    assert got["bar"]["promote"] == "mean - 2 x se > 0"
    assert got["bar"]["promote_one_sided_level"] == pytest.approx(0.9772, abs=1e-4)
    assert cm.conviction_promotion(list(x + 2.5 * se), "SHADOW")["mode"] == "LIVE"
    # demotion keeps the 1 se bar (hysteresis)
    assert cm.conviction_promotion(list(x - 1.5 * se), "LIVE")["mode"] == "SHADOW"
