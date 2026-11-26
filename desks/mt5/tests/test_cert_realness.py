"""CERTIFICATE REALNESS -- the ranking score, its fallbacks, its falsifier, what it never writes.

  * MONOTONE: more in-sample Sharpe, or more days at the same Sharpe, is never less real;
  * (1 - pi0) FALLS BACK AND SAYS SO: a family x timeframe under MIN_MATURED clocks borrows a
    named level, down to the DECLARED prior;
  * THE ORDER MOVES THE WAY THE PROBE SAYS IT SHOULD: an M5 certificate in a family whose
    matured clocks lose ranks below an H1 one, though the old desk-wide decay ranked it first;
  * THE CALIBRATION BLOCK'S MATHS, and that it only reports;
  * NO GATE OR CERTIFICATE FILE IS WRITTEN, and a stale certified population is FLAGGED.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import cert_realness as cr  # noqa: E402
from research import forward_slot_ranker as fsr  # noqa: E402
from research import replication_civilization as rc  # noqa: E402

NOW = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)


def _ctx(xs: dict | None = None, clocks: dict | None = None) -> cr.Context:
    xs = xs or {"status": cr.UNMEASURED, "pooled": {}, "by_family": {}, "why": "none here"}
    return cr.Context(xs, cr.pi0_table({"shadow": clocks or {}}), (109, "floor"),
                      {"status": cr.UNMEASURED, "by_family": {}})


def _clock(t: float, exp_r: float, n: int, status: str = "KILL", cum: float | None = None) -> dict:
    return {"status": status, "forward_t": t, "exp_r": exp_r, "n": n,
            "cum_r": cum if cum is not None else exp_r * n}


def _losing_m5(fam: str = "carry", k: int = 12) -> dict:
    return {f"S{i}.{fam}.asia@M5": _clock(-2.5, -0.2, 20 + i) for i in range(k)}


def _winning_h1(fam: str = "formula", k: int = 12) -> dict:
    return {f"W{i}.{fam}.asia": _clock(3.0, 0.3, 30 + i, "PROMOTION CANDIDATE")
            for i in range(k)}


# ------------------------------------------------------------------------------- monotone
def test_score_is_monotone_in_sharpe_and_in_days():
    ctx = _ctx()
    by_sr = [cr.score(sr, 500, "fam", "H1", ctx) for sr in (0.05, 0.1, 0.2, 0.4)]
    assert [s["z"] for s in by_sr] == sorted(s["z"] for s in by_sr)
    assert len({s["z"] for s in by_sr}) == 4
    by_t = [cr.score(0.15, t, "fam", "H1", ctx) for t in (100, 300, 1000, 3000)]
    assert [s["z"] for s in by_t] == sorted(s["z"] for s in by_t)
    assert all(s["p_real"] <= 1.0 for s in by_sr + by_t)
    # The noise floor is the basis when nothing measures V_null, and it says so.
    assert by_t[0]["v_star"] == pytest.approx(1 / 99, rel=1e-6)
    assert "noise floor" in by_t[0]["basis"] and "UNMEASURED" in by_t[0]["basis"]


def test_a_measured_v_null_raises_sr0_and_is_named():
    xs = {"status": cr.MEASURED, "source": "gauntlet_report", "pooled": {},
          "by_family": {"fam": {"status": cr.MEASURED, "n": 50, "v_null": 0.01}}}
    floor = cr.score(0.3, 1000, "fam", "H1", _ctx())
    fam = cr.score(0.3, 1000, "fam", "H1", _ctx(xs))
    assert fam["v_star"] == 0.01 and fam["sr0"] > floor["sr0"]
    assert fam["z"] < floor["z"]
    assert "family fam robust V net of noise" in fam["basis"]


def test_a_certificate_without_sharpe_or_days_is_unmeasured_never_guessed():
    sc = cr.score(None, 400, "fam", "H1", _ctx())
    assert sc["status"] == cr.UNMEASURED and sc["p_real"] is None
    assert cr.rank_key(sc) == -math.inf


def test_log10_phi_stays_finite_and_ordered_deep_in_the_tail():
    vals = [cr.log10_phi(z) for z in (-80.0, -40.0, -31.0, -29.0, -5.0, 0.0)]
    assert all(math.isfinite(v) for v in vals)
    assert vals == sorted(vals)
    assert cr.log10_phi(0.0) == pytest.approx(math.log10(0.5))


# ------------------------------------------------------------------------- pi0 and fallbacks
def test_pi0_falls_back_to_the_declared_prior_and_says_so():
    table = cr.pi0_table({"shadow": {"A.fam.asia": _clock(1.0, 0.1, 12)}})
    pi0, basis = cr.pi0_for(table, "fam", "H1")
    assert pi0 == cr.PRIOR_PI0
    assert "DECLARED PRIOR" in basis and "fallback" in basis
    pi0, basis = cr.pi0_for(table, "unseen", "M5")
    assert pi0 == cr.PRIOR_PI0 and "DECLARED PRIOR" in basis


def test_pi0_is_measured_per_family_timeframe_and_thin_cells_borrow_the_timeframe():
    clocks = {**_losing_m5("carry"), **_winning_h1("formula"),
              "X.carry.asia": _clock(2.0, 0.2, 99, "PROMOTION CANDIDATE")}
    table = cr.pi0_table({"shadow": clocks})
    assert table["cells"]["carry|M5"]["pi0"] == 1.0
    assert table["cells"]["carry|M5"]["basis"].startswith("measured")
    assert table["cells"]["formula|H1"]["pi0"] == 0.0
    thin = table["cells"]["carry|H1"]          # one clock: borrows the H1 timeframe's level
    assert thin["basis"].startswith("fallback (1 < 10): timeframe H1")
    assert thin["pi0"] == table["by_timeframe"]["H1"]["pi0"]


def test_aliases_count_once():
    same = {f"A.fam.asia#p={i}": _clock(2.0, 0.2, 30, cum=6.0) for i in range(5)}
    assert len(cr.matured_distinct({"shadow": same})) == 1


# ---------------------------------------------------------------------------- calibration
def test_calibration_bins_by_decile_and_the_trigger_needs_100_clocks():
    rows = [(0.9, 0) for _ in range(30)] + [(0.1, 0) for _ in range(70)]
    rank = [r[0] for r in rows]
    cal = cr.calibration(rows, rank=rank)
    assert sum(b["n"] for b in cal["bins"]) == 100 and len(cal["bins"]) == 10
    top = cal["top_deciles"]
    assert top["n"] == 30 and top["predicted_keep"] == pytest.approx(0.9)
    assert top["measured_keep"] == 0.0
    assert top["se"] == pytest.approx(math.sqrt(0.9 * 0.1 / 30), rel=1e-4)
    assert top["gap_in_se"] < -2
    assert cal["trigger_met"] is True and cal["acts"] is False
    assert cal["trigger_line"] == cr.TRIGGER_LINE
    assert "at least 100 matured clocks" in cal["trigger_line"]
    small = cr.calibration(rows[:99], rank=rank[:99])
    assert small["trigger_met"] is False and small["reading"].startswith("INSUFFICIENT")


def test_calibration_within_two_se_does_not_trigger():
    rows = [(0.5, i % 2) for i in range(200)]
    cal = cr.calibration(rows)
    assert cal["trigger_met"] is False
    assert abs(cal["top_deciles"]["gap_in_se"]) <= 2


# ------------------------------------------------------------------ cross-section from a sweep
def _verdict(cell: str, fam: str, sr: float, days: int, dsr_pass: bool = True,
             other_fail: bool = False) -> dict:
    return {"cell": cell, "family": fam, "sym": cell.split()[0], "days": days,
            "stages": {"in_sample_screen": {"passed": True, "sharpe": sr},
                       "deflated_sharpe": {"passed": dsr_pass, "dsr": 0.5, "sr0": 0.9,
                                           "n_trials": 400000},
                       "pbo": {"passed": not other_fail}}}


def test_cross_section_streams_the_sweep_report_caches_and_lists_dsr_only_kills(tmp_path):
    verdicts = [_verdict(f"S{i} fam x", "fam", 0.01 * ((i % 7) - 3), 400) for i in range(60)]
    verdicts += [_verdict("BIG fam x", "fam", 0.4, 2000, dsr_pass=False),
                 _verdict("BAD fam x", "fam", 0.4, 2000, dsr_pass=False, other_fail=True)]
    (tmp_path / "universal_gates_external.json").write_text(json.dumps(
        {"hunt": "h", "swept_at": "2026-11-25T00:00:00+00:00", "verdicts": verdicts}), "utf-8")
    paths = cr.paths_for(tmp_path)
    xs = cr.cross_section(paths)
    assert xs["status"] == cr.MEASURED and xs["source"] == "gauntlet_report"
    fam = xs["by_family"]["fam"]
    assert fam["n"] == 62 and fam["status"] == cr.MEASURED
    assert fam["v_null"] <= fam["v_null_raw"]          # the robust scale ignores the two tails
    assert [k["cell"] for k in xs["dsr_only_kills"]] == ["BIG fam x"]
    assert cr.cross_section(paths)["cache"] == "hit"
    listing = cr.dsr_only_kills(cr.Context(xs, cr.pi0_table({}), (109, "f"), {"by_family": {}}))
    assert listing["n_dsr_only_kills"] == 1
    assert [r["cell"] for r in listing["would_pass_at_v_star"]] == ["BIG fam x"]
    assert "read-only" in listing["boundary"]


# ------------------------------------------------------------- the ranker, wired end to end
@pytest.fixture
def desk(tmp_path, monkeypatch):
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    for name, path in (("SHADOW_DIR", shadow),
                       ("SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json"),
                       ("GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl"),
                       ("ALLOCATION", tmp_path / "pf_allocation.json"),
                       ("EXPOSURE", tmp_path / "EXPOSURE_DECOMPOSITION.json"),
                       ("CAPACITY_FILE", tmp_path / "forward_capacity.json"),
                       ("OUT", tmp_path / "FORWARD_SLOT_RANKER.json")):
        monkeypatch.setattr(fsr, name, path)
    return tmp_path


def _cell(symbol: str, family: str, selector: str, ev: float, sharpe: float) -> dict:
    return {"cell": f"{symbol} {family} {selector}", "sym": symbol, "days": 600,
            "gates": {"expected_value": {"passed": True, "ev": ev},
                      "in_sample_screen": {"passed": True, "sharpe": sharpe},
                      "cpcv": {"passed": True, "mean_oos_sharpe": sharpe}},
            "shadow_spec": {"symbol": symbol, "family": family, "selector": selector}}


def _write(desk_dir: Path, clocks: dict, cells: dict, swept_at: str) -> None:
    (desk_dir / "shadow" / "shadow_state.json").write_text(
        json.dumps({"updated_at": NOW.isoformat(), **clocks}), "utf-8")
    (desk_dir / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"n": len(cells), "swept_at": swept_at, "survivors": cells}), "utf-8")


def test_the_order_changes_the_way_the_forward_evidence_says(desk):
    """The M5 cell has the higher in-sample EV, so a desk-wide decay scalar ranks it first. Its
    family's matured M5 clocks lose, so the realness score puts the H1 cell first."""
    cells = {"c.m5": _cell("AUDCAD", "carry", "asia@M5", ev=0.8, sharpe=0.3),
             "c.h1": _cell("EURNOK", "formula", "asia", ev=0.4, sharpe=0.3)}
    _write(desk, {**_losing_m5("carry"), **_winning_h1("formula")}, cells,
           NOW.isoformat())
    payload = fsr.run(write=False, now=NOW)
    order = [e["cell"] for e in payload["waiting"]]
    assert order == ["c.h1", "c.m5"]
    by = {e["cell"]: e for e in payload["waiting"]}
    assert by["c.m5"]["p_real"] == 0.0 and by["c.h1"]["p_real"] > 0.9
    assert by["c.m5"]["timeframe"] == "M5" and by["c.h1"]["days"] == 600
    assert "p_real" in by["c.h1"]["p_certify_basis"]
    # The old scalar: the same raw term times one decay for both, so EV decides.
    th = fsr.maturity_thresholds()
    rows = {r.key: r for r in fsr.waiting_rows({}, cells, [])}
    old = {k: fsr.p_certify_waiting(r, th, 0.5)[0] for k, r in rows.items()}
    assert old["c.m5"] > old["c.h1"]
    assert payload["replication_priority"]["certificates"][0] == "c.h1"
    fcs = payload["false_certificate_share"]["by_family_timeframe"]
    assert fcs["carry|M5"]["pi0"] == 1.0 and fcs["formula|H1"]["pi0"] == 0.0


def test_a_running_clock_prior_mean_is_the_shrunk_in_sample_ev(desk):
    cells = {"c.h1": _cell("EURNOK", "formula", "asia", ev=0.4, sharpe=0.3)}
    clocks = {**_winning_h1("formula"),
              "EURNOK.formula.asia#p=1": {"status": "ACTIVE", "n": 0, "exp_r": 0.0,
                                          "days_active": 2, "forward_t": 0.0, "max_dd_r": 0.0,
                                          "forward_start": "2026-11-23T00:00:00+00:00"}}
    _write(desk, clocks, cells, NOW.isoformat())
    payload = fsr.run(write=False, now=NOW)
    young = next(e for e in payload["running"] if e["clock"].startswith("EURNOK"))
    assert isinstance(young["p_real"], float)
    assert "prior mean" in young["p_certify_basis"] and "p_real" in young["p_certify_basis"]
    th = fsr.maturity_thresholds()
    bare, _ = fsr.p_certify_running(fsr.Row("running", "k", "shadow", "S", "f", n=0.0), th)
    assert young["p_certify"] > bare


def test_a_stale_certified_population_is_flagged_with_its_age(desk):
    _write(desk, {}, {"c": _cell("EURNOK", "formula", "asia", 0.4, 0.3)},
           "2026-09-16T15:07:26+00:00")
    (desk / "REPLICATION.json").write_text(json.dumps({"population": {"certificates": 13452}}),
                                           "utf-8")
    payload = fsr.run(write=False, now=NOW)
    pop = payload["certified_population"]
    assert pop["status"] == "STALE" and pop["age_h"] > 24 * 60
    assert pop["population_gap"] == 13451
    assert any("STALE certified population" in n for n in payload["unmeasured"])
    _write(desk, {}, {"c": _cell("EURNOK", "formula", "asia", 0.4, 0.3)}, NOW.isoformat())
    assert fsr.run(write=False, now=NOW)["certified_population"]["status"] == "FRESH"


def test_no_gate_or_certificate_file_is_written(desk):
    _write(desk, {**_losing_m5("carry")}, {"c": _cell("EURNOK", "formula", "asia", 0.4, 0.3)},
           NOW.isoformat())
    (desk / "policy").mkdir()
    (desk / "policy" / "gate_spec.yaml").write_text(
        "deflated_sharpe:\n  fixed_trial_count: 109\n  fixed_variance_of_sharpes: 0.0002\n",
        "utf-8")
    before = {p: p.read_bytes() for p in desk.rglob("*") if p.is_file()}
    payload = fsr.run(write=True, now=NOW)
    after = {p for p in desk.rglob("*") if p.is_file()}
    assert after - set(before) == {desk / "FORWARD_SLOT_RANKER.json"}
    assert all(p.read_bytes() == b for p, b in before.items())
    assert payload["realness"]["campaign_floor"] == 109
    assert payload["calibration"]["acts"] is False


# ------------------------------------------------------------- replication takes the priority
def _cert(name: str, fam: str = "carry") -> dict[str, Any]:
    return {"certificate": name, "shadow_spec": {"symbol": "EURNOK", "family": fam,
                                                 "selector": "asia", "side": "LONG"}}


def test_replication_reads_the_rankers_priority_filters_judged_and_caps(tmp_path):
    names = [f"c{i}" for i in range(10)]
    certs = [_cert(n) for n in names]
    path = tmp_path / "FORWARD_SLOT_RANKER.json"
    path.write_text(json.dumps({"replication_priority": {
        "at": NOW.isoformat(), "certificates": ["ghost", *names]}}), "utf-8")
    judged = {"c0": {"fp": rc.certificate_fp(certs[0]),
                     "sharpe_metric_version": rc.SHARPE_METRIC_VERSION,
                     "rule_fp": rc.rule_fingerprint("carry")}}
    chosen, block = rc.ranker_priority(path, certs, judged, now=NOW)
    assert chosen == names[1:1 + rc.RANKER_PRIORITY_PER_PASS]
    assert block["skipped_already_judged"] == 1 and block["skipped_not_in_population"] == 1
    stale, why = rc.ranker_priority(path, certs, judged,
                                    now=datetime(2026, 11, 27, tzinfo=UTC))
    assert stale == [] and "not used" in why["why"]
    missing, why = rc.ranker_priority(tmp_path / "absent.json", certs, {}, now=NOW)
    assert missing == [] and why["used"] is False
