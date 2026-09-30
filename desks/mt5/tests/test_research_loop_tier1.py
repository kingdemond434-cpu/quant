"""Tier-1 #9-#12 (2026-09-29): the north star, the factory contracts, the champion, the wall, the
source quality fields -- and the wiring that makes each one run on the hour.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_rank as ar  # type: ignore[import-not-found]  # noqa: E402
import factory_contracts as fc  # type: ignore[import-not-found]  # noqa: E402
import meta_rnd  # type: ignore[import-not-found]  # noqa: E402
import research_os_archive as roa  # type: ignore[import-not-found]  # noqa: E402

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #9 the north star
def _cert(sym: str, fam: str, sel: str = "asia", hunt: str = "hunt_a") -> dict[str, Any]:
    return {"sym": sym, "hunt": hunt, "cell": f"{sym}.{fam}",
            "shadow_spec": {"symbol": sym, "family": fam, "selector": sel, "hunt": hunt}}


def _point_rank(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                survivors: dict[str, Any] | None) -> None:
    for name in ("SURVIVORS", "CANON", "UNIVERSE_JSON", "LIVE_BREADTH", "OUT", "HISTORY"):
        monkeypatch.setattr(ar, name, tmp_path / name / f"{name}.json")
    if survivors is not None:
        ar.SURVIVORS.parent.mkdir(parents=True)
        ar.SURVIVORS.write_text(json.dumps({"survivors": survivors}), encoding="utf-8")
    monkeypatch.setattr(ar, "_realised", lambda edges: ({}, {}))


def test_alpha_rank_is_unmeasured_without_certificates(monkeypatch, tmp_path) -> None:
    _point_rank(monkeypatch, tmp_path, None)
    doc = ar.build()
    assert doc["status"] == "UNMEASURED" and doc["north_star"] is None
    assert doc["schema_version"] == ar.SCHEMA_VERSION


def test_alpha_rank_publishes_the_north_star_and_producer_credit(monkeypatch, tmp_path) -> None:
    import numpy as np
    rng = np.random.default_rng(5)
    panel = {"EURCHF": list(rng.standard_normal(400)), "XAUUSD": list(rng.standard_normal(400))}
    monkeypatch.setattr(ar, "_proxy", lambda syms: (panel, {}, []))
    _point_rank(monkeypatch, tmp_path, {
        "e1": _cert("EURCHF", "session_range_breakout", hunt="dup_hunt"),
        "e2": _cert("EURCHF", "session_range_breakout", hunt="dup_hunt"),
        "g1": _cert("XAUUSD", "carry", sel="ny", hunt="new_hunt"),
    })
    assert ar.main([]) == 0
    doc = json.loads(ar.OUT.read_text(encoding="utf-8"))
    ns = doc["north_star"]
    assert doc["status"] == "MEASURED" and ns["n_certified"] == 3
    assert 1.0 <= ns["effective_independent_alpha_rank"] < 3.0
    assert set(doc["channels"]) == set(ar.ig.CHANNELS)
    assert doc["producer_independent_alpha"]["new_hunt"] > \
        doc["producer_independent_alpha"]["dup_hunt"]
    hist = ar.HISTORY.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(hist[-1])["effective_independent_alpha_rank"] == \
        ns["effective_independent_alpha_rank"]


# -------------------------------------------------------------------------- #11 the contracts
def _census_row(key: str, raw: float, uniq: float, judged: float, surv: float, certs: float,
                hours: float, clock: str | None = None) -> dict[str, Any]:
    return {"producer": key, "key": key, "clock": clock, "compute_hours": hours,
            "funnel": {"raw_cells": raw, "unique_cells": uniq, "cells_judged": judged,
                       "cheap_survivors": surv, "certificates": certs}}


def test_a_contract_has_seven_terms_and_the_arithmetic_is_pinned() -> None:
    c = fc.contract(_census_row("p", 100, 40, 20, 5, 2, 4.0), {"credited_delta_elogw": 0.8},
                    0.5, "")
    t = c["contract"]
    assert set(t) == set(fc.TERMS)
    assert t["candidates_produced"] == 100 and t["novelty_rate"] == 0.4
    assert t["falsification_rate"] == 0.75 and t["survivor_yield"] == 0.1
    assert t["independent_alpha_yield"] == 0.5 and t["incremental_elogw"] == 0.8
    assert c["complete"] is True
    assert c["rates"]["unique_cells_per_hour"] == 10.0
    assert c["rates"]["elogw_per_hour"] == 0.2


def test_an_unmeasured_term_is_named_never_zero() -> None:
    c = fc.contract(_census_row("q", 10, 10, 0, 0, 0, 0.0), None, None, "no certificate")
    t = c["contract"]
    for term in ("falsification_rate", "survivor_yield", "independent_alpha_yield",
                 "incremental_elogw"):
        assert t[term]["verdict"] == "UNMEASURED" and t[term]["why"]
    assert c["complete"] is False and all(v is None for v in c["rates"].values())


def test_contracts_price_the_legs_that_run_their_producers(monkeypatch, tmp_path) -> None:
    stamp = datetime.now(tz=UTC).isoformat()
    for name in ("CENSUS", "ROI", "ALPHA_RANK", "OUT"):
        monkeypatch.setattr(fc, name, tmp_path / f"{name}.json")
    fc.CENSUS.write_text(json.dumps({"at": stamp, "producers": [
        _census_row("alpha_evolution", 100, 50, 40, 10, 3, 2.0),
        _census_row("deepen", 100, 5, 40, 1, 0, 10.0),
        _census_row("offline_thing", 10, 1, 0, 0, 0, 1.0),
    ]}), encoding="utf-8")
    fc.ROI.write_text(json.dumps({"at": stamp, "scientist_roi": {
        "alpha_evolution": {"credited_delta_elogw": 0.4}}}), encoding="utf-8")
    fc.ALPHA_RANK.write_text(json.dumps({"at": stamp, "status": "MEASURED",
                                         "producer_independent_alpha": {"alpha_evolution": 1.2}}),
                             encoding="utf-8")
    monkeypatch.setattr(fc, "_legs", lambda: {"alpha_evolution", "deepen"})
    assert fc.main([]) == 0
    doc = json.loads(fc.OUT.read_text(encoding="utf-8"))
    assert doc["schema_version"] == fc.SCHEMA_VERSION and doc["status"] == "MEASURED"
    assert doc["n_producers"] == 3 and doc["n_complete_contracts"] == 1
    ly, why = fc.leg_yield(fc.OUT)
    assert why == "" and ly["alpha_evolution"] > ly["deepen"]
    assert "offline_thing" not in ly


def test_contracts_are_unmeasured_on_a_stale_census(monkeypatch, tmp_path) -> None:
    old = (datetime.now(tz=UTC) - timedelta(days=5)).isoformat()
    for name in ("CENSUS", "ROI", "ALPHA_RANK", "OUT"):
        monkeypatch.setattr(fc, name, tmp_path / f"{name}.json")
    fc.CENSUS.write_text(json.dumps({"at": old, "producers": [
        _census_row("x", 1, 1, 1, 1, 1, 1.0)]}), encoding="utf-8")
    doc = fc.build()
    assert doc["status"] == "UNMEASURED" and doc["leg_yield"] == {}


# ------------------------------------------------------------------ #12 the wall and the crown
def test_the_meta_rnd_wall_is_restored() -> None:
    """research_os_archive imports both tables; losing them emptied one refusal list silently."""
    assert roa.forbidden_knobs(), "meta_rnd.FORBIDDEN_KNOBS must be reachable"
    assert set(roa.meta_knob_specs()) == set(meta_rnd.META_KNOBS)
    assert "any gate threshold" in meta_rnd.FORBIDDEN_KNOBS
    for spec in meta_rnd.META_KNOBS.values():
        assert spec["lo"] < spec["hi"]


def test_the_sealed_suite_fails_when_an_arena_is_dark(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(meta_rnd, "QUANTBENCH", tmp_path / "qb.json")
    monkeypatch.setattr(meta_rnd, "ADVERSARY", tmp_path / "adv.json")
    assert meta_rnd.sealed_benchmark()["passed"] is False
    (tmp_path / "qb.json").write_text(json.dumps({"status": "OK", "n_cases": 11}), "utf-8")
    assert meta_rnd.sealed_benchmark()["passed"] is False           # adversary still dark
    (tmp_path / "adv.json").write_text(json.dumps({"n_breach": 0}), "utf-8")
    assert meta_rnd.sealed_benchmark()["passed"] is True
    (tmp_path / "adv.json").write_text(json.dumps({"n_breach": 2}), "utf-8")
    assert meta_rnd.sealed_benchmark()["passed"] is False


def _win(hours_ago: float, comp: float, sealed: bool) -> dict[str, Any]:
    fr = (NOW - timedelta(hours=hours_ago + 6)).isoformat(timespec="seconds")
    to = (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    return {"from": fr, "to": to, "hours": 6.0, "composite": comp, "n_measured": 6,
            "sealed": sealed}


def _arch(challenger_windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"variants": [
        {"variant_id": "incumbent", "policy": {}, "active_windows": [_win(40, 0.1, True),
                                                                     _win(30, 0.1, False)]},
        {"variant_id": "ch", "policy": {}, "active_windows": challenger_windows}],
        "active": "incumbent", "champion": "incumbent",
        "champion_since": (NOW - timedelta(hours=48)).isoformat(timespec="seconds"),
        "history": []}


def test_a_challenger_is_crowned_only_on_sealed_windows_fresh_episode_and_suite() -> None:
    passing = {"passed": True}
    good = [_win(20, 0.9, True), _win(12, 0.9, True), _win(2, 0.8, False)]
    arch = _arch(good)
    d = roa.champion_decision(arch, NOW, passing)
    assert d["promoted"] == "ch" and arch["champion"] == "ch"
    assert arch["history"][-1]["event"] == "CHAMPION"
    # the same record with the suite dark: the champion holds
    arch2 = _arch(good)
    d2 = roa.champion_decision(arch2, NOW, {"passed": False})
    assert d2["promoted"] is None and arch2["champion"] == "incumbent"
    # great UNSEALED windows alone never crown -- that is selection on the scored windows
    arch3 = _arch([_win(20, 0.9, False), _win(12, 0.9, False), _win(2, 0.9, False)])
    d3 = roa.champion_decision(arch3, NOW, passing)
    assert d3["promoted"] is None
    why = next(r for r in d3["challengers"] if r["variant_id"] == "ch")["why_not"]
    assert any("sealed window" in w for w in why)
    # a stale challenger (nothing since the champion was seated) never crowns
    arch4 = _arch([_win(80, 0.9, True), _win(70, 0.9, True)])
    assert roa.champion_decision(arch4, NOW, passing)["promoted"] is None


def test_sealed_windows_are_held_out_of_the_ucb_board() -> None:
    v = {"variant_id": "x", "active_windows": [_win(10, 5.0, True), _win(4, 0.2, False)]}
    comp, _n = roa.variant_composite(v)
    assert comp == 0.2
    assert roa.sealed_record(v) == (5.0, 1)


def test_the_seal_is_a_coin_decided_before_the_fitness() -> None:
    flips = [roa.is_sealed("v", f"2026-09-{d:02d}T00:00:00+00:00") for d in range(1, 29)]
    assert any(flips) and not all(flips)
    assert roa.is_sealed("v", "2026-09-01T00:00:00+00:00") == flips[0]     # reproducible


# ------------------------------------------------------- #10b closed-loop discovery quality
def test_every_source_row_carries_the_quality_fields() -> None:
    import source_registry as sr  # type: ignore[import-not-found]
    rows = {"g": {"source_id": "g", "region": "cn", "language": "zh", "kind": "forum",
                  "data_class": "interview", "licence_note": "WEB-PUBLIC", "n_leads": 3,
                  "first_seen": "2026-09-01T00:00:00+00:00",
                  "last_seen": "2026-09-01T02:00:00+00:00", "intel_roi": None,
                  "roi_basis": "UNMEASURED: thin"},
            "empty": {"source_id": "empty", "region": "br", "language": "pt",
                      "licence_note": "UNDECLARED -- declare", "n_leads": 0}}
    counts = {"g": {"_quality": {"lineage": 3, "claims": {"a", "b"}, "families": {"carry"},
                                 "url_versions": {"u": {"t1": {"a"}, "t2": {"b"}},
                                                  "v": {"t1": {"a"}}}}}}
    cube = sr.quality(rows, counts, now=datetime(2026, 9, 1, 12, tzinfo=UTC))
    q = rows["g"]["source_quality"]
    assert q["freshness_h"] == 10.0 and q["cadence_h"] == 1.0
    assert q["lineage_share"] == 1.0 and q["revision_rate"] == 1.0
    assert q["access"] == "DECLARED" and q["coverage"]["transmission_path"] == ["risk_premium"]
    e = rows["empty"]["source_quality"]
    assert e["access"] == "UNDECLARED"
    assert e["cadence_h"]["verdict"] == "UNMEASURED"
    assert e["revision_rate"]["verdict"] == "UNMEASURED"
    assert cube["reached"]["jurisdiction"] == 1 and cube["listed"]["jurisdiction"] == 2


# ---------------------------------------------------------------------------------- wiring
def test_the_new_legs_run_on_the_hour() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    import hourly_cycle as hc  # type: ignore[import-not-found]
    from libs.research.layers import LEG_LAYER
    for leg in ("alpha_rank", "factory_contracts"):
        assert f'_costed("{leg}"' in src
        assert leg in hc.CORE_LEGS and hc.LEG_DEPARTMENT.get(leg) == "meta"
        assert LEG_LAYER.get(leg) == "meta"
        assert hc.LEG_BUDGET_SEC.get(leg, 0) > 0
