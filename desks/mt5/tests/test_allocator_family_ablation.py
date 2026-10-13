"""ALLOC-25: the data-family ablation of the allocator's world sampler, on fixtures only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import allocator_family_ablation as afa  # noqa: E402

NAMES = ("XAUUSD_session_range_breakout_asia", "EURJPY_session_range_breakout_asia",
         "CHFNOK_carry_asia", "EURUSD_macro_conditional_asia", "mystery_sleeve")


def _worlds(path: Path, *, carry_mu: float = 0.08, seed: int = 3) -> Path:
    rng = np.random.default_rng(seed)
    w, t, n = 64, 96, len(NAMES)
    r = rng.normal(0.0, 0.6, size=(w, t, n)).astype(np.float32)
    mu = np.array([0.02, 0.01, carry_mu, 0.015, 0.0])
    r += mu[None, None, :].astype(np.float32)
    np.savez_compressed(path, r=r, names=np.array(NAMES), crisis=rng.random(w) < 0.1,
                        mu=np.tile(mu, (w, 1)))
    return path


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(afa, "SLEEVES", tmp_path / "absent_sleeves.json")
    monkeypatch.setattr(afa, "REGISTRY", tmp_path / "absent_registry.json")
    monkeypatch.setattr(afa, "_scalp_candidates", lambda: {})
    return tmp_path


def test_mapping_reads_the_desks_own_tables_and_unknown_is_unmeasured():
    m = afa.map_sleeves([*NAMES, "gold_asia", "CADJPY_asia_FAILED_BREAK"],
                        sleeves_doc={"sleeves": [{"name": "mystery_sleeve", "family": ""}]},
                        registry_doc={"sleeves": {"CHFNOK.carry.asia#input_symbol=CHFNOK": {
                            "identity": {"family": "carry"}}}}, scalp={})
    assert m["XAUUSD_session_range_breakout_asia"]["data_family"] == "price_only"
    assert m["CHFNOK_carry_asia"]["data_family"] == "carry"
    assert m["CHFNOK_carry_asia"]["mapped_from"] == "data/sleeve_registry.json"
    assert m["EURUSD_macro_conditional_asia"]["data_family"] == "macro"
    # The two producer lanes whose names are not family names resolve through the cited alias.
    assert m["gold_asia"]["data_family"] == "price_only"
    assert m["CADJPY_asia_FAILED_BREAK"]["data_family"] == "price_only"
    # Unknown is UNMEASURED, never folded into price only.
    assert m["mystery_sleeve"]["data_family"] == afa.UNMEASURED


def test_ablation_on_the_same_worlds_reports_paired_deltas(iso):
    wp = _worlds(iso / "worlds.npz", carry_mu=0.10)
    doc = afa.build(worlds_path=wp, daily_path=iso / "no_daily.parquet")
    fams = doc["sleeves"]["families"]
    assert doc["trials_charged"] == 0 and doc["report_only"] is True
    carry = fams["carry"]
    assert carry["status"] == "MEASURED" and carry["sleeves"] == ["CHFNOK_carry_asia"]
    d = carry["drop"]["delta_elog_per_world"]
    assert d["n_worlds"] == 64
    assert d["p05"] <= d["p25"] <= d["p50"] <= d["p75"] <= d["p95"]
    # The richest sleeve's family removed: the book is worse in the median world.
    assert d["p50"] < 0
    assert "delta_breach_p" in carry["drop"] and "fractions_l1_shift" in carry["drop"]
    assert carry["drop"]["top_fraction_movers"][0]["sleeve"] == "CHFNOK_carry_asia"
    # Reverse case: carry alone added to the price-only sleeves.
    add = carry["add_to_price_only"]["delta_elog_per_world"]
    assert add["p50"] > 0
    # Absent families are NOT_IN_POPULATION, never a zero delta.
    assert fams["positioning"]["status"] == afa.NOT_IN_POPULATION
    assert "drop" not in fams["positioning"]
    # Unknown sleeves form their own UNMEASURED group.
    assert fams[afa.UNMEASURED]["family_status"] == afa.UNMEASURED
    assert doc["mapping_unmeasured"] == ["mystery_sleeve"]
    assert fams["price_only"]["add_to_price_only"]["status"] == "IS_BASELINE"
    # States cannot be removed from a baked tensor: UNMEASURED with the missing input named.
    assert doc["states"]["macro_kernel"]["status"] == afa.UNMEASURED
    assert "daily_r" in doc["states"]["macro_kernel"]["why"] or "no_daily" in \
        doc["states"]["macro_kernel"]["why"]
    rows = {r["family"]: r for r in doc["table"]}
    assert rows["carry"]["drop_delta_elog_median"] == d["p50"]


def test_drop_and_add_are_mirror_images_when_the_family_completes_the_book(iso):
    names = NAMES[:3]
    rng = np.random.default_rng(1)
    r = (rng.normal(0, 0.5, size=(48, 64, 3)) + np.array([0.02, 0.01, 0.06])).astype(np.float32)
    w = afa.Worlds(r=r, names=names, crisis=np.zeros(48, bool), mu_draws=np.zeros((48, 3)))
    mp = afa.map_sleeves(names, sleeves_doc=None, registry_doc=None, scalp={})
    out = afa.sleeve_ablation(w, mp, cfg=afa.WorldConfig(seed=0), law=afa._heat_law(),
                              families=["carry"])
    drop = out["families"]["carry"]["drop"]["delta_elog_per_world"]
    add = out["families"]["carry"]["add_to_price_only"]["delta_elog_per_world"]
    assert drop["p50"] == pytest.approx(-add["p50"], abs=1e-7)


def test_missing_population_is_unmeasured_not_zero(iso):
    doc = afa.build(worlds_path=iso / "absent.npz", daily_path=iso / "absent.parquet")
    assert doc["status"] == afa.UNMEASURED
    assert doc["sleeves"]["status"] == afa.UNMEASURED
    assert doc["table"] == []


def test_report_writes_only_its_own_artifact(iso):
    wp = _worlds(iso / "worlds.npz")
    before = wp.read_bytes()
    out = iso / "reports" / "ALLOCATOR_FAMILY_ABLATION.json"
    rc = afa.main(["--worlds", str(wp), "--daily", str(iso / "none.parquet"),
                   "--out", str(out)])
    assert rc == 0
    assert wp.read_bytes() == before                     # the allocator's cache is untouched
    created = sorted(p.relative_to(iso).as_posix() for p in iso.rglob("*") if p.is_file())
    assert created == ["reports/ALLOCATOR_FAMILY_ABLATION.json", "worlds.npz"]
    doc = json.loads(out.read_text("utf-8"))
    assert doc["requirement"] == "ALLOC-25" and doc["writes"] == [
        "desks/mt5/reports/ALLOCATOR_FAMILY_ABLATION.json"]
    assert "g_w" not in json.dumps(doc)


def test_state_ablation_redraws_with_the_same_seed_when_evidence_exists(iso):
    rng = np.random.default_rng(5)
    days = pd.date_range("2025-01-01", periods=240, freq="D").strftime("%Y-%m-%d")
    daily = pd.DataFrame(rng.normal(0.03, 0.5, size=(240, 3)), index=days,
                         columns=list(NAMES[:3]))
    p = iso / "daily_r.parquet"
    daily.to_parquet(p)
    labels = tuple(["calm"] * 120 + ["stress"] * 120)
    out = afa.state_ablation(
        p, afa.map_sleeves(NAMES[:3], scalp={}), law=afa._heat_law(), seed=0,
        macro_weights=lambda dates: (np.linspace(0.0, 1.0, len(dates)), {}),
        regime=lambda _d: (labels, (("calm", 0.7), ("stress", 0.3)), {}))
    for key in ("macro_kernel", "regime_labels"):
        assert out[key]["status"] == afa.MEASURED, out[key]
        assert out[key]["drop"]["delta_elog_per_world"]["n_worlds"] > 0
    assert out["macro_kernel"]["family"] == "macro"
    assert out["regime_labels"]["family"] == "price_only"

