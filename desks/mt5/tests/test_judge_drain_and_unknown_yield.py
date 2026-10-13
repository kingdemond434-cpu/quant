"""The drain meter reads the judge's sustained rate, and never-firing cells stop eating the judge."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def test_sustained_rate_is_the_average_not_the_burst_hour(tmp_path: Path) -> None:
    """One sweep stamps 5,000 verdicts in one hour; the day holds 5,000, so 208/h, not 5,000/h."""
    at = (NOW - timedelta(hours=2)).isoformat()
    rows = [{"at": at, "cell": f"c{i}", "family": "f", "terminal_gate": "cpcv"}
            for i in range(5_000)]
    rows += [{"at": at, "cell": f"n{i}", "family": "f", "downstream_status": "NOT_RUN_X"}
             for i in range(900)]
    r = jc.sustained_rate(_ledger(tmp_path, rows), now=NOW)
    assert r["counts"]["24h"] == 5_000, "a NOT_RUN deferral is not a verdict"
    assert abs(r["per_hour_24h"] - 5_000 / 24.0) < 0.01
    assert jc.measured_capacity({}, _ledger(tmp_path, rows), now=NOW) >= 5_000


def test_drain_reports_growing_when_backlog_rises() -> None:
    d = jc.drain(1_398_253, 220.0, prior_backlog=1_395_253,
                 prior_at=NOW - timedelta(hours=24), now=NOW)
    assert d["status"] == "GROWING" and d["hours"] is None
    assert d["net_per_day"] == 3000.0
    assert d["hours_at_zero_creation"] == round(1_398_253 / 220.0, 1)


def test_drain_eta_uses_net_fall() -> None:
    d = jc.drain(1_000, 100.0, prior_backlog=1_100, prior_at=NOW - timedelta(hours=1), now=NOW)
    assert d["status"] == "DRAINING" and d["hours"] == 10.0


def test_drain_unmeasured_without_verdicts() -> None:
    d = jc.drain(10, 0.0, prior_backlog=None, prior_at=None, now=NOW)
    assert d["status"] == "UNMEASURED"


def test_readmission_needs_real_history_growth(tmp_path: Path, monkeypatch) -> None:
    """One more hour of bars must not re-admit a spec that never fired on the whole history."""
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_010_000)
    parked = (NOW - timedelta(days=1)).isoformat()
    never = {"sym": "EURUSD", "days": 0, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(never, now=NOW)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_260_000)
    assert jc.readmit_due(never, now=NOW)
    rare = {"sym": "EURUSD", "days": 30, "bar_bytes": 1_000_000, "parked_at": parked}
    assert not jc.readmit_due(rare, now=NOW), "30 days needs the history doubled to reach 60"
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 2_000_000)
    assert jc.readmit_due(rare, now=NOW)


def test_readmission_after_max_wait(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000_000)
    old = {"sym": "X", "days": 0, "bar_bytes": 1_000_000,
           "parked_at": (NOW - timedelta(days=jc.READMIT_MAX_DAYS + 1)).isoformat()}
    assert jc.readmit_due(old, now=NOW)


def test_never_fire_pairs_need_volume_and_no_fired_sibling() -> None:
    bank = {f"c{i}": {"reason": "never_fires", "family": "f", "sym": "A"}
            for i in range(jc.SIBLING_NEVER_FIRES_MIN)}
    bank.update({f"d{i}": {"reason": "never_fires", "family": "f", "sym": "B"}
                 for i in range(jc.SIBLING_NEVER_FIRES_MIN)})
    bank.update({f"e{i}": {"reason": "never_fires", "family": "f", "sym": "C"} for i in range(3)})
    dead = jc.never_fire_pairs(bank, fired={("f", "B")})
    assert dead == {("f", "A")}


def test_fired_pairs_skip_unknown(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [
        {"family": "f", "sym": "A", "terminal_gate": "UNKNOWN"},
        {"family": "f", "sym": "B", "terminal_gate": "in_sample_screen"}])
    assert jc.fired_pairs(p) == {("f", "B")}


def test_not_run_cells_are_named_and_parked(tmp_path: Path, monkeypatch) -> None:
    """A cell that could not be BUILT stops coming back at the head of every sweep."""
    report = tmp_path / "gates.json"
    report.write_text(json.dumps({"verdicts": [
        {"cell": "a", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_DATA_MISSING",
         "why": "point-in-time M5 parquet is missing or empty"},
        {"cell": "b", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_BUILD_FAILED", "why": "boom"},
        {"cell": "c", "sym": "EURUSD", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}]}), "utf-8")
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if tf == "M5" else 5_000)
    named = jc.name_not_run(report)
    assert set(named) == {"a", "b"}, "a budget deferral is work not yet done, never parked"
    assert named["a"]["reason"] == "data_missing" and named["a"]["tf"] == "M5"
    assert named["b"]["reason"] == "build_failed"
    bank = tmp_path / "bank.json"
    res = jc.update_unrunnable_bank(named, at=NOW.isoformat(), path=bank)
    assert res["bank_size"] == 2


def test_data_missing_readmits_when_its_own_chart_appears(monkeypatch) -> None:
    row = {"sym": "EURUSD", "tf": "M5", "reason": "data_missing", "bar_bytes": 0,
           "parked_at": NOW.isoformat()}
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if tf == "M5" else 9_999)
    assert not jc.readmit_due(row, now=NOW), "H1 bars growing says nothing about the M5 chart"
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 100)
    assert jc.readmit_due(row, now=NOW)


def test_build_failed_retries_after_a_week(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000)
    row = {"sym": "X", "tf": "H1", "reason": "build_failed", "bar_bytes": 1_000,
           "parked_at": (NOW - timedelta(days=2)).isoformat()}
    assert not jc.readmit_due(row, now=NOW)
    row["parked_at"] = (NOW - timedelta(days=jc.BUILD_FAILED_RETRY_DAYS + 0.1)).isoformat()
    assert jc.readmit_due(row, now=NOW)


def test_prewarm_share_counts_build_and_data_failures(tmp_path: Path) -> None:
    report = tmp_path / "gates.json"
    report.write_text(json.dumps({"prewarm": {"submitted": 100, "failures": {
        "NOT_RUN_DATA_MISSING": 40, "NOT_RUN_BUILD_FAILED": 29, "ERROR": 1}}}), "utf-8")
    assert jc._prewarm_share(report) == 0.7


def _fence_report(tmp_path: Path, totals: dict) -> Path:
    p = tmp_path / "JUDGE_COVERAGE.json"
    fams = {"f": {"unjudged": 0, "queued": 0, "judged_window": 1}}
    p.write_text(json.dumps({"at": NOW.isoformat(), "families": fams, "totals": totals,
                             "ranking": []}), "utf-8")
    return p


def test_fence_fails_when_the_backlog_grows_twice(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_judge_coverage as fence

    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"drain_status": "GROWING",
                                               "prior_drain_status": "GROWING"}))
    checks = {c["metric"]: c for c in doc["checks"]}
    assert checks["judge_keeps_pace"]["state"] == "FAIL"
    assert "never throttle" in checks["judge_keeps_pace"]["why"]
    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"drain_status": "GROWING",
                                               "prior_drain_status": "DRAINING"}))
    assert {c["metric"]: c for c in doc["checks"]}["judge_keeps_pace"]["state"] == "WARN"


def test_fence_ratchets_prewarm_failures(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_judge_coverage as fence

    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"prewarm_fail_share": 0.5,
                                               "prior_prewarm_fail_share": 0.3}))
    assert {c["metric"]: c for c in doc["checks"]}["prewarm_fail_ratchet"]["state"] == "FAIL"
    doc = fence.judge(now=NOW, report=_fence_report(tmp_path, {"prewarm_fail_share": 0.2,
                                               "prior_prewarm_fail_share": 0.3}))
    assert {c["metric"]: c for c in doc["checks"]}["prewarm_fail_ratchet"]["state"] == "OK"


def test_refresh_bars_asks_for_the_charts_the_judge_wanted(tmp_path: Path) -> None:
    from research import hourly_cycle as hc

    rep = tmp_path / "JUDGE_COVERAGE.json"
    rep.write_text(json.dumps({"bars_wanted": {"EURUSD_M5": 3, "EURUSD_M1": 4,
                                               "GBPJPY_M15": 5, "USDMXN_H1": 1}}), "utf-8")
    assert hc.bars_wanted_symbols(rep) == ["EURUSD", "GBPJPY", "USDMXN"]
    assert hc.bars_wanted_symbols(tmp_path / "absent.json") == []


# ---------------------------------------------------------------- the sticky prior (audit 10-13)
def _sticky_fence(tmp_path: Path, totals: dict, now: datetime = NOW) -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_judge_coverage as fence
    doc = fence.judge(now=now, report=_fence_report(tmp_path, totals))
    return {c["metric"]: c for c in doc["checks"]}


def _owned(opened: datetime = NOW) -> dict:
    return {"row": "214", "opened_utc": opened.isoformat(), "opened_share": 0.556}


def test_a_rise_with_no_open_row_fails(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.556, "prior_prewarm_fail_share": 0.556,
                                 "prewarm_fail_best": 0.163, "prewarm_fail_baseline": None,
                                 "prewarm_fail_defect": None})
    assert c["prewarm_fail_ratchet"]["state"] == "OK"          # the last-reading check alone
    assert c["prewarm_fail_unowned"]["state"] == "FAIL"        # ... cannot launder it


def test_an_owned_regression_repeated_is_warn_never_ok(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.556, "prior_prewarm_fail_share": 0.556,
                                 "prewarm_fail_best": 0.163, "prewarm_fail_baseline": 0.556,
                                 "prewarm_fail_defect": _owned()})
    assert c["prewarm_fail_sticky"]["state"] == "WARN" and "#214" in c["prewarm_fail_sticky"]["why"]
    assert "prewarm_fail_unowned" not in c and "prewarm_fail_baseline" not in c


def test_a_further_rise_over_the_baseline_fails(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.60, "prior_prewarm_fail_share": 0.59,
                                 "prewarm_fail_best": 0.163, "prewarm_fail_baseline": 0.556,
                                 "prewarm_fail_defect": _owned()})
    assert c["prewarm_fail_baseline"]["state"] == "FAIL"


def test_a_defect_open_14_days_without_falling_fails(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.556, "prior_prewarm_fail_share": 0.556,
                                 "prewarm_fail_best": 0.163, "prewarm_fail_baseline": 0.556,
                                 "prewarm_fail_defect": _owned(NOW - timedelta(days=15))})
    assert c["prewarm_fail_defect_aged"]["state"] == "FAIL"


def test_recovery_closes_the_defect_and_a_row_alone_never_does() -> None:
    at = NOW.isoformat()
    prior = {"prewarm_fail_share": 0.556, "prewarm_fail_best": 0.163}
    opened = jc.prewarm_sticky(prior, 0.556, "214", at)
    assert opened["prewarm_fail_defect"]["row"] == "214"
    # row 214 opens at its anchored opening, whatever the ratchet carried
    assert opened["prewarm_fail_defect"]["opened_share"] == 0.555807
    assert opened["prewarm_fail_baseline"] == 0.555807 and opened["prewarm_fail_best"] == 0.163
    # The row disappears from the register: the defect stays open (only a reading closes it).
    held = jc.prewarm_sticky({**prior, **opened}, 0.50, None, at)
    assert held["prewarm_fail_defect"]["row"] == "214" and held["prewarm_fail_baseline"] == 0.50
    closed = jc.prewarm_sticky({**prior, **held, "prewarm_fail_share": 0.50}, 0.17, None, at)
    assert closed["prewarm_fail_defect"] is None and closed["prewarm_fail_baseline"] is None


def test_best_never_rises_whatever_the_order() -> None:
    import itertools
    for seq in itertools.permutations([0.30, 0.10, 0.556, 0.20]):
        st: dict = {}
        best_seen = []
        for v in seq:
            st = {**st, **jc.prewarm_sticky(st, v, None, NOW.isoformat(), sample=10_000),
                  "prewarm_fail_share": v, "prewarm_submitted": 10_000}
            best_seen.append(st["prewarm_fail_best"])
        assert all(b2 <= b1 for b1, b2 in itertools.pairwise(best_seen))
        assert best_seen[-1] == min(0.10, jc.PREWARM_FAIL_BEST_SEED)


def test_the_register_row_is_found_by_its_marker(tmp_path: Path) -> None:
    reg = tmp_path / "GAP_REGISTER.md"
    reg.write_text("| 9 | **x** (metric:prewarm_fail_share) | e | f | o | 10-13 | closed |\n"
                   "| 214 | **y** (metric:prewarm_fail_share) | e | f | o | 10-13 | open |\n",
                   "utf-8")
    assert jc.open_defect_row(reg) == "214"
    assert jc.open_defect_row(tmp_path / "absent.md") is None


# ------------------------------------------------ audit of #372: nothing launders the regression
def test_a_wiped_ratchet_reopens_row_214_at_its_anchor_not_today() -> None:
    later = (NOW + timedelta(days=13)).isoformat()
    st = jc.prewarm_sticky({}, 0.62, "214", later, sample=10_000)
    assert st["prewarm_fail_defect"]["opened_utc"] == jc.PREWARM_DEFECT_ANCHORS["214"]["opened_utc"]
    assert st["prewarm_fail_baseline"] == 0.555807            # 0.62 is a rise over it


def test_a_wiped_ratchet_reading_a_rise_still_fails(tmp_path: Path) -> None:
    st = jc.prewarm_sticky({}, 0.62, "214", NOW.isoformat(), sample=10_000)
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.62, "prior_prewarm_fail_share": None,
                                 **st})
    assert c["prewarm_fail_baseline"]["state"] == "FAIL"


def test_an_empty_reading_carries_the_sticky_values_forward(tmp_path: Path) -> None:
    rt, rep = tmp_path / "ratchet.json", tmp_path / "JC.json"
    sticky = {"prewarm_fail_best": 0.10, "prewarm_fail_baseline": 0.5559,
              "prewarm_fail_defect": {"row": "214", "opened_utc": "x", "opened_share": 0.555807}}
    rt.write_text(json.dumps(sticky), "utf-8")
    jc.write({"families": {}, "totals": {}}, report=rep, ratchet=rt)
    kept = json.loads(rt.read_text("utf-8"))
    assert {k: kept[k] for k in sticky} == sticky
    assert not list(tmp_path.glob("*.tmp"))


def test_a_future_or_unreadable_opening_time_is_aged(tmp_path: Path) -> None:
    for stamp in ("2027-01-01T00:00:00+00:00", "bogus"):
        c = _sticky_fence(tmp_path, {
            "prewarm_fail_share": 0.556, "prior_prewarm_fail_share": 0.556,
            "prewarm_fail_best": 0.163, "prewarm_fail_baseline": 0.556,
            "prewarm_fail_defect": {"row": "214", "opened_utc": stamp, "opened_share": 0.556}},
            now=NOW + timedelta(days=30))
        assert c["prewarm_fail_defect_aged"]["state"] == "FAIL", stamp


def test_a_token_fall_after_14_days_is_still_the_regression(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.5559, "prior_prewarm_fail_share": 0.556,
                                 "prewarm_fail_best": 0.163, "prewarm_fail_baseline": 0.5559,
                                 "prewarm_fail_defect": _owned(NOW - timedelta(days=60))})
    assert c["prewarm_fail_defect_aged"]["state"] == "FAIL"


def test_a_non_finite_best_fails(tmp_path: Path) -> None:
    c = _sticky_fence(tmp_path, {"prewarm_fail_share": 0.30, "prior_prewarm_fail_share": 0.30,
                                 "prewarm_fail_best": float("nan"),
                                 "prewarm_fail_baseline": None, "prewarm_fail_defect": None})
    assert c["prewarm_fail_sticky"]["state"] == "FAIL"


def test_a_tiny_sweep_cannot_pin_best() -> None:
    st = jc.prewarm_sticky({"prewarm_fail_best": 0.163}, 0.0, None, NOW.isoformat(), sample=12)
    assert st["prewarm_fail_best"] == 0.163
    st = jc.prewarm_sticky({"prewarm_fail_best": 0.163}, 0.05, None, NOW.isoformat(),
                           sample=jc.PREWARM_MIN_SAMPLE)
    assert st["prewarm_fail_best"] == 0.05
