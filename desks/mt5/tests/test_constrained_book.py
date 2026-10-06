"""Tier-1 audit #6: risk as hard constraints inside the E[log W] solve, published as a shadow.

Pins: every MEASURED clause constrains, an UNMEASURED clause is never reported as slack, the
concentration clause redistributes rather than drops heat, the shadow is two-sided (it may carry
MORE heat than the traded book), and the fiat switch is OFF: only the hourly proof switch,
re-contested by the allocator, feeds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import constrained_book as cb  # noqa: E402

from libs.portfolio import constrained_elog as ce  # noqa: E402
from libs.portfolio.posterior_growth import sample_paths  # noqa: E402
from libs.portfolio.robust_elog import Worlds  # noqa: E402

NAMES = ("xau_a", "xau_b", "xau_c", "EURUSD_x")
SYM = {"xau_a": "XAUUSD", "xau_b": "XAUUSD", "xau_c": "XAUUSD", "EURUSD_x": "EURUSD"}
CLS = {k: ("metal" if v == "XAUUSD" else "fx") for k, v in SYM.items()}


def _worlds(mu=(0.15, 0.12, 0.10, 0.05), sd=0.5, seed=0) -> Worlds:
    rng = np.random.default_rng(seed)
    m = np.asarray(mu)
    r = (m + sd * rng.standard_normal((64, 120, len(m)))).astype("float32")
    return Worlds(r=r, names=NAMES, crisis=np.zeros(64, bool), mu_draws=np.tile(m, (64, 1)))


def _paths(**kw):
    return sample_paths(None, n_paths=300, horizon=5, worlds=_worlds(**kw), seed=1)


def test_the_fiat_switch_is_off_and_only_the_proof_switch_reaches_the_allocator():
    assert ce.FEEDS_LIVE is False
    # the gateway, the decision core and the promoter never read the shadow directly
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/decision_core.py",
                "desks/mt5/research/promoter.py"):
        text = (ROOT / rel).read_text("utf-8")
        assert "constrained_elog" not in text and "CONSTRAINED_BOOK" not in text, rel
    # the allocator reads ONLY the proof switch, and adopts ONLY through the re-contest
    alloc = (ROOT / "desks/mt5/research/pf_allocator.py").read_text("utf-8")
    assert "CONSTRAINED_BOOK_SWITCH.json" in alloc and "adopt_if_proven" in alloc
    assert "_ce.FEEDS_LIVE" not in alloc.replace("`constrained_elog.FEEDS_LIVE`", "")


def _doc(beats: bool, *, total: float = 0.25, status: str = "MEASURED", stale: bool = False,
         ruin_a: float = 0.0, ruin_b: float = 0.0) -> dict:
    return {"status": status, "worlds_stale": stale, "spec": {"floor": 0.20},
            "constrained": {"total_heat": total, "book": {"xau_a": total}},
            "contest_constrained_vs_current": {
                "beats": beats, "delta_elogw_per_day": 0.001 if beats else -0.001,
                "ci_lo": 0.0005 if beats else -0.002, "ci_hi": 0.002,
                "p_ruin_a": ruin_a, "p_ruin_b": ruin_b}}


def test_the_switch_turns_on_only_when_robust_elog_beats_the_live_book():
    now = "2026-09-30T12:00:00+00:00"
    on = ce.decide(_doc(True), now_iso=now)
    assert on["feeds_live"] is True and on["book"] == {"xau_a": 0.25}
    for doc, why in ((_doc(False), "does not beat"),
                     (_doc(True, stale=True), "stale"),
                     (_doc(True, status="UNMEASURED"), "UNMEASURED"),
                     (_doc(True, ruin_a=0.02, ruin_b=0.0), "ruinous"),
                     (_doc(True, total=0.15), "below the 0.20 floor")):
        off = ce.decide(doc, now_iso=now)
        assert off["feeds_live"] is False and off["book"] == {} and why in off["why"], why
    # the allocator's reading: OFF, stale-ON and fresh-ON
    assert ce.read_switch(None, now_iso=now)["feeds"] is False
    assert ce.read_switch(ce.decide(_doc(False), now_iso=now), now_iso=now)["feeds"] is False
    assert ce.read_switch(on, now_iso="2026-09-30T15:00:00+00:00")["feeds"] is False
    assert ce.read_switch(on, now_iso="2026-09-30T12:30:00+00:00")["feeds"] is True


def test_the_allocator_adopts_only_after_its_own_re_contest():
    paths = _paths(mu=(0.15, 0.12, 0.10, 0.05))
    good = {"feeds": True, "book": {"xau_a": 0.10, "xau_b": 0.08, "EURUSD_x": 0.04}}
    weak = {"EURUSD_x": 0.20}                      # the lowest-drift sleeve alone
    book, rec = ce.adopt_if_proven(good, weak, paths, floor=0.20, score=lambda b: 1.0)
    assert book is not None and rec["adopted"] and rec["vs_incumbent"]["beats"]
    # the incumbent is better: it stands, whatever the hourly switch said
    book2, rec2 = ce.adopt_if_proven({"feeds": True, "book": weak}, good["book"], paths,
                                     floor=0.20, score=lambda b: 1.0)
    assert book2 is None and not rec2["adopted"]
    # a book the allocator scores ruinous is never published
    book3, rec3 = ce.adopt_if_proven(good, weak, paths, floor=0.20,
                                     score=lambda b: float("-inf"))
    assert book3 is None and "ruinous" in rec3["why"]
    # switch OFF: nothing is contested at all
    book4, rec4 = ce.adopt_if_proven({"feeds": False, "why": "off"}, weak, paths, floor=0.20,
                                     score=lambda b: 1.0)
    assert book4 is None and "vs_incumbent" not in rec4


def test_unmeasured_clauses_are_never_reported_as_slack():
    ev = ce.evaluate(_paths(), {"xau_a": 0.1, "EURUSD_x": 0.1}, ce.ConstraintSpec(),
                     symbol_of=SYM, class_of=CLS)
    for k in ("broker_stop_out", "margin_use", "liquidity", "execution_feasibility"):
        assert ev["clauses"][k]["status"] == "UNMEASURED", k
    assert ev["n_unmeasured"] >= 4


def test_concentration_binds_and_the_freed_heat_is_replaced_not_dropped():
    spec = ce.ConstraintSpec(max_symbol_share=0.5, max_class_share=0.9, tail_max_loss=0.99)
    res = ce.solve_constrained(_paths(), spec, symbol_of=SYM, class_of=CLS)
    book = res["book"]
    total = sum(book.values())
    gold = sum(v for k, v in book.items() if SYM[k] == "XAUUSD")
    assert gold / total <= 0.5 + 1e-3
    assert any(b.startswith("concentration_symbol") for b in res["binding"])
    assert total >= spec.floor - 1e-6            # the heat law's floor is filled, never short


def test_margin_clause_is_measured_when_the_inputs_exist():
    spec = ce.ConstraintSpec(margin_per_heat=4.0, stop_out_level=0.5, max_margin_use=0.5)
    ev = ce.evaluate(_paths(), {"xau_a": 0.2, "EURUSD_x": 0.1}, spec, symbol_of=SYM,
                     class_of=CLS)
    assert ev["clauses"]["margin_use"]["status"] == "VIOLATED"      # 4.0 x 0.3 = 1.2 > 0.5
    assert ev["clauses"]["broker_stop_out"]["status"] in ("SATISFIED", "VIOLATED")
    res = ce.solve_constrained(_paths(), spec, symbol_of=SYM, class_of=CLS)
    assert any("margin use caps" in n for n in res["notes"])


def test_the_shadow_is_two_sided(tmp_path, monkeypatch):
    w = _worlds(sd=0.3)
    np.savez_compressed(tmp_path / "worlds.npz", r=w.r, names=np.array(w.names),
                        crisis=w.crisis, mu=w.mu_draws)
    art = {"book": {"xau_a": 0.02, "EURUSD_x": 0.02},
           "heat": {"hard_ceiling": 0.30, "target": 0.20}}
    (tmp_path / "pf_allocation.json").write_text(json.dumps(art), "utf-8")
    monkeypatch.setattr(cb, "WORLDS", tmp_path / "worlds.npz")
    monkeypatch.setattr(cb, "ALLOCATION", tmp_path / "pf_allocation.json")
    monkeypatch.setattr(cb, "CAPACITY", tmp_path / "absent.json")
    monkeypatch.setattr(cb, "SLEEVES", tmp_path / "absent.json")
    monkeypatch.setattr(cb, "ACCOUNT", tmp_path / "absent.json")
    monkeypatch.setattr(cb, "ROOT", tmp_path)
    monkeypatch.setattr(cb, "_terminal_account",
                        lambda: ({"margin": None, "equity": None, "stop_out_level": None}, "x"))
    doc = cb.build()
    assert doc["status"] == "MEASURED"
    assert doc["feeds_live"] is doc["switch"]["feeds_live"]       # the decision, on the artifact
    assert doc["fiat_switch"] is False
    assert doc["constrained"]["total_heat"] > 0.04          # MORE heat than the traded book
    assert doc["direction"].startswith("MORE")
    assert "contest_constrained_vs_current" in doc


def test_absent_inputs_read_unmeasured(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "ALLOCATION", tmp_path / "none.json")
    monkeypatch.setattr(cb, "ROOT", tmp_path)
    monkeypatch.setattr(cb, "WORLDS", tmp_path / "none.npz")
    assert cb.build()["status"] == "UNMEASURED"


def test_execution_feasibility_counts_heat_below_one_minimum_lot():
    f = cb.feasibility({"a": 0.001, "b": 0.05}, {"a": 0.004, "b": 0.004})
    assert f["status"] == "MEASURED" and f["n_below_min_lot"] == 1 and "a" in f["below_min_lot"]
    assert cb.feasibility({"a": 0.01}, {})["status"] == "UNMEASURED"
