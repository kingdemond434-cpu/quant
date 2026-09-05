"""Coverage map, resurrection, prospector, productivity, feature admission, VOI ordering.

What is pinned: an uncovered state becomes a machine-readable research task naming the families
never tried there; a hibernated sleeve is only resurrected when its habitat is present AND shadow
confirms; the prospector ranks a named gap an engine asked for above a catalogue entry nobody
asked for, and never a crypto-exchange source; a feature joins the regime model only by improving
out-of-sample likelihood; the deepening queue works high-VOI tasks first.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import Trade  # noqa: E402
from research import data_prospector, deepening_worker, regime_coverage, resurrection  # noqa: E402


def _trades() -> list[Trade]:
    rng = np.random.default_rng(0)
    out = []
    for i in range(600):
        state = "A" if i % 2 == 0 else "B"
        sleeve = f"XAUUSD_fam{i % 3}_asia"
        # fam0 pays in A only; nothing pays in B.
        r = (0.3 if (state == "A" and i % 3 == 0) else -0.1) + rng.normal(scale=0.3)
        out.append(Trade(sleeve=sleeve, when=f"2026-0{1 + i % 8}-{1 + i % 27:02d}T10:00:00+00:00",
                         r=r, buckets={"global": state}))
    return out


def test_coverage_names_the_covered_and_uncovered_states():
    cov = regime_coverage.coverage(_trades(), ("global",))
    assert cov["global=A"]["n_covering"] >= 1
    assert cov["global=B"]["n_covering"] == 0
    assert cov["global=A"]["best"]["family"] == "fam0"


def test_an_uncovered_state_becomes_a_research_task_naming_untried_families():
    cov = regime_coverage.coverage(_trades(), ("global",))
    tasks = regime_coverage.instructions(cov)
    assert [t["state"] for t in tasks] == ["global=B"]
    t = tasks[0]
    assert t["source"] == "regime_coverage" and t["kind"] == "coverage_gap"
    assert "fam0" in t["description"] and "families_never_tried_here" in t


def test_coverage_is_shrunk_so_six_lucky_trades_do_not_cover():
    rng = np.random.default_rng(1)
    trades = [Trade("S_fam_x", f"2026-01-{1 + i % 27:02d}T00:00:00+00:00",
                    r=(2.0 if i < 8 else -0.2) + rng.normal(scale=0.1),
                    buckets={"global": "lucky" if i < 8 else "rest"}) for i in range(300)]
    cov = regime_coverage.coverage(trades, ("global",))
    assert cov["global=lucky"]["sleeves"][0]["raw_r"] > 1.5
    assert cov["global=lucky"]["sleeves"][0]["shrunk_r"] < 0.5, "eight trades cannot own the bucket"


def test_only_admitted_dimensions_build_the_map():
    src = inspect.getsource(regime_coverage.run)
    assert "_admitted()" in src and "if d in admitted" in src


# ------------------------------------------------------------------------------------------
# Resurrection
# ------------------------------------------------------------------------------------------

def test_resurrection_needs_habitat_and_confirmation():
    hab = {"global=A": {"n": 30, "shrunk_r": 0.2}}
    good = [0.2] * 30
    bad = [-0.2] * 30
    assert resurrection.judge("s", hab, "global=A", good, 0.0, 3)["verdict"] == "RESURRECT"
    assert resurrection.judge("s", hab, "global=A", bad, 0.0, 3)["verdict"] == "WATCH"
    assert resurrection.judge("s", hab, "global=B", good, 0.0, 3)["verdict"] == "DORMANT"
    assert resurrection.judge("s", hab, "global=A", bad, 0.0, 90)["verdict"] == "DEAD"
    assert resurrection.judge("s", {}, "global=A", good, 0.0, 3)["verdict"] == "DORMANT"


def test_habitats_are_the_buckets_a_sleeve_paid_in():
    hab = resurrection.habitats(_trades(), ("global",))
    assert "global=A" in hab["XAUUSD_fam0_asia"]
    assert "global=B" not in hab.get("XAUUSD_fam0_asia", {})


# ------------------------------------------------------------------------------------------
# Prospector
# ------------------------------------------------------------------------------------------

def test_a_named_gap_an_engine_asked_for_outranks_the_catalogue(monkeypatch):
    monkeypatch.setattr(data_prospector, "_named_gaps",
                        lambda: {"surprise": "no actual on the calendar"})
    monkeypatch.setattr(data_prospector, "_coverage_gaps", lambda: (["s1"], {"event_reaction": 1}))
    monkeypatch.setattr(data_prospector, "_barren", lambda: {})
    doc = data_prospector.rank()
    assert doc["queue"][0]["asked_by"] == "surprise"


def test_the_prospector_never_ranks_a_crypto_exchange_source():
    doc = data_prospector.rank()
    for it in doc["queue"]:
        low = json.dumps(it).lower()
        for banned in ("binance", "bybit", "okx", "hyperliquid", "funding_rates", "funding rate"):
            assert banned not in low, it


# ------------------------------------------------------------------------------------------
# Feature admission
# ------------------------------------------------------------------------------------------

def test_candidate_features_are_causal():
    from libs.regime.feature_admission import FEATURES
    rng = np.random.default_rng(2)
    c = pd.Series(np.exp(np.cumsum(rng.normal(scale=0.01, size=600))))
    cut = 450
    tampered = c.copy()
    tampered.iloc[cut:] *= 3.0
    for name, fn in FEATURES.items():
        a, b = fn(c).to_numpy(), fn(tampered).to_numpy()
        assert np.allclose(a[:cut], b[:cut], equal_nan=True), f"{name} reads the future"


def test_a_feature_that_carries_nothing_is_not_admitted():
    from libs.regime import feature_admission as fa
    rng = np.random.default_rng(3)
    c = pd.Series(np.exp(np.cumsum(rng.normal(scale=0.01, size=1200))),
                  index=pd.date_range("2020-01-01", periods=1200, freq="D"))
    fa.FEATURES["noise"] = lambda s: pd.Series(rng.normal(size=len(s)), index=s.index)
    try:
        v = fa.judge(c, "noise", candidates_tried=3)
    finally:
        fa.FEATURES.pop("noise", None)
    assert v.verdict != "ADMIT", v


# ------------------------------------------------------------------------------------------
# VOI ordering and roles
# ------------------------------------------------------------------------------------------

def test_coverage_gap_tasks_are_worked_before_plain_crawler_rows():
    tasks = [{"source": "world_crawler", "title": "a", "url": "u1"},
             {"source": "regime_coverage", "kind": "coverage_gap", "title": "b", "url": "u2"},
             {"source": "fund_playbook", "evidence_grade": "A", "title": "c", "url": "u3"}]
    ordered = deepening_worker.voi_order(tasks)
    assert ordered[0]["source"] == "regime_coverage"
    assert ordered[1]["source"] == "fund_playbook"


def test_voi_ordering_is_deterministic():
    tasks = [{"source": "world_crawler", "title": f"t{i}", "url": f"u{i}"} for i in range(6)]
    assert deepening_worker.voi_order(tasks) == deepening_worker.voi_order(list(reversed(tasks)))


def test_specialist_roles_exist_for_each_task_kind():
    for kind in ("coverage_gap", "fund_claim", "data_source"):
        assert kind in deepening_worker._SYSTEM_BY_KIND
    src = inspect.getsource(deepening_worker.extract)
    assert "_SYSTEM_BY_KIND.get" in src


def test_the_daily_cycle_runs_the_proposers_and_the_feedback_loop():
    from research import daily_cycle
    names = [n for n, _ in daily_cycle.STEPS]
    assert "proposers" in names and "state_research_feedback" in names
    assert names.index("proposers") < names.index("shadow")
    assert names.index("state_research_feedback") > names.index("promoter")
