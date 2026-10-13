"""Portfolio controller phase 1: the online edge monitor.

Pins: the posterior moves both ways, forward evidence is de-duplicated against live fills, the
fraction rises when evidence improves (two-sided), the decay alarm fires on a run of losses and
not on a single one, the replay is causal, decisions are logged only on change, the hooks report
UNMEASURED rather than a zero, and the allocator reads the hazard (stale -> nothing).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import portfolio_controller as pc  # noqa: E402

SIG = 1.0


def test_posterior_moves_both_ways():
    base = pc.posterior(0.1, 0, 0.0, [], SIG)
    up = pc.posterior(0.1, 0, 0.0, [0.5] * 20, SIG)
    down = pc.posterior(0.1, 0, 0.0, [-0.5] * 20, SIG)
    assert down["mean_r"] < base["mean_r"] < up["mean_r"]
    assert up["sd_r"] < base["sd_r"]
    assert down["p_edge_le_0"] > 0.5 > up["p_edge_le_0"]


def test_forward_is_deduplicated_against_live():
    p = pc.posterior(0.1, 10, -0.5, [0.2, 0.3], SIG)
    assert p["n_forward_used"] == 8 and p["n_live"] == 2
    q = pc.posterior(0.1, 2, -0.5, [0.2, 0.3, 0.1], SIG)
    assert q["n_forward_used"] == 0


def test_fraction_is_two_sided_and_capped():
    lo = pc.posterior(0.05, 0, 0.0, [0.0] * 5, SIG)
    hi = pc.posterior(0.05, 0, 0.0, [0.4] * 40, SIG)
    f_lo = pc.kelly_fraction(lo["mean_r"], lo["sd_r"], SIG, 0.10)
    f_hi = pc.kelly_fraction(hi["mean_r"], hi["sd_r"], SIG, 0.10)
    assert f_hi > f_lo > 0
    assert pc.kelly_fraction(5.0, 0.01, SIG, 0.10) == 0.10
    assert pc.kelly_fraction(-0.1, 0.1, SIG, 0.10) == 0.0


def test_alarm_needs_a_run_not_one_loss():
    assert pc.decay_alarm(0.1, [-1.0], SIG)["state"] in ("OK", "WATCH")
    assert pc.decay_alarm(0.1, [-1.0] * 8, SIG)["state"] == "ALARM"
    assert pc.decay_alarm(0.1, [], SIG)["state"] == "UNMEASURED"


def test_replay_is_causal_and_counts_both_signs():
    seq = [("2026-10-01T00:00:00+00:00", -1.0)] * 12 + [("2026-10-02T00:00:00+00:00", 1.0)]
    fwd = {"n": 0, "mean": 0.0, "first": "", "last": ""}
    rep = pc.replay(0.1, fwd, seq, SIG, 0.10, 0.10)
    assert rep["trades"][0]["fraction"] == pytest.approx(
        pc.kelly_fraction(0.1, pc.PRIOR_SD_R, SIG, 0.10), abs=1e-4)
    assert rep["trades"][-1]["fraction"] < rep["trades"][0]["fraction"]
    assert rep["value_add"] == pytest.approx(rep["controller_equity_r"] - rep["static_equity_r"])


def test_forward_prorating_bounds():
    fwd = {"n": 10, "first": "2026-09-01 00:00:00+00:00", "last": "2026-09-11 00:00:00+00:00"}
    assert pc.forward_n_by(fwd, "2026-08-01T00:00:00+00:00") == 0.0
    assert pc.forward_n_by(fwd, "2026-10-01T00:00:00+00:00") == 10
    assert 1 <= pc.forward_n_by(fwd, "2026-09-06T00:00:00+00:00") <= 10


def test_names_join_book_clock_and_ledger():
    assert pc.norm("AUDCHF.overnight_gap_decay.asia#session=asia") == \
        "audchf_overnight_gap_decay_asia"
    assert pc.stem("AUDCHF_overnight_gap_decay_asia") == "audchf_overnight_gap_decay_"


def test_decisions_logged_only_on_change(tmp_path):
    st, lg = tmp_path / "s.json", tmp_path / "d.jsonl"
    doc = {"sleeves": {"x": {"fraction": 0.05, "alarm": {"state": "OK", "cusum": 0.0},
                             "static_fraction": 0.1, "override_pinned": False,
                             "posterior": {"mean_r": 0.1, "sd_r": 0.2, "p_edge_le_0": 0.3,
                                           "n_live": 1, "n_forward_used": 0}}}}
    now = datetime.now(tz=UTC)
    assert pc.log_decisions(doc, now, st, lg) == 1
    assert pc.log_decisions(doc, now, st, lg) == 0
    doc["sleeves"]["x"]["fraction"] = 0.0
    assert pc.log_decisions(doc, now, st, lg) == 1
    rows = [json.loads(x) for x in lg.read_text().splitlines()]
    assert len(rows) == 2 and "posterior mean" in rows[-1]["reason"]


def test_hooks_never_report_a_zero():
    for h in pc.hooks():
        assert h["status"] in ("UNMEASURED", "READ_NOT_ACTED")
        assert h["why"]


def test_override_allowlist_absent_is_unmeasured(tmp_path):
    names, why = pc.override_allowlist(tmp_path / "none.json")
    assert names == set() and why.startswith("UNMEASURED")


def test_hazard_for_reads_fresh_and_refuses_stale(tmp_path):
    p = tmp_path / "EDGE_MONITOR.json"
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "hazard_by_sleeve": {"audchf_overnight_gap_decay_asia": 0.9}}
    p.write_text(json.dumps(doc))
    assert pc.hazard_for(["AUDCHF_overnight_gap_decay_asia_p_44136fa355b3678a"], p) == \
        {"AUDCHF_overnight_gap_decay_asia_p_44136fa355b3678a": 0.9}
    doc["generated_utc"] = (datetime.now(tz=UTC) - timedelta(hours=5)).isoformat()
    p.write_text(json.dumps(doc))
    assert pc.hazard_for(["AUDCHF_overnight_gap_decay_asia"], p) == {}


def test_allocator_reads_the_monitor():
    src = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
    assert "_haz.update(edge_monitor_hazard(" in src
    hc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert hc.index('_costed("portfolio_controller"') < hc.index('_costed("pf_allocator"')


def test_run_end_to_end_without_writing():
    doc = pc.run(write=False)
    assert "value_add_vs_static" in doc and "hazard_by_sleeve" in doc
    for s in doc["sleeves"].values():
        f = s["fraction"]
        assert f is None or 0.0 <= f <= pc.DEFAULT_MAX_RISK_FRAC + 1e-9 or s["override_pinned"]
