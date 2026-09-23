"""The allocator's liveness organ and its fence.

Every test here builds a sandbox of artifacts with tmp_path + monkeypatch; nothing reads or
writes the desk's real state.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import allocator_liveness as AL  # noqa: E402
from scripts import check_allocator_liveness as FENCE  # noqa: E402


def _write(p: Path, doc: object) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, default=str), encoding="utf-8")
    return p


def _allocation(**heat: object) -> dict:
    h = {"resolved": 0.225, "total": 0.225, "filled": True, "certified": True,
         "binding": "ceiling", "state": "session=LONDON_MID"}
    h.update(heat)
    return {
        "generated_utc": "2026-09-23T09:11:00+00:00",
        "heat": h,
        "book": {"gold_afternoon": 0.05, "CHFNOK_carry_asia": 0.175},
        "book_fallback": {"name": "static_incumbent", "book": {"gold_afternoon": 0.05}},
        "allocator_evidence": {"evidence": "allocator_evidence.json read: 19 sleeve(s), 4 min old",
                               "roi": "roi read: 69 mechanism(s)",
                               "net_of_cost": "NET_EDGE.json prices 12 sleeve net-of-cost edges",
                               "forward_posterior": "posterior read: 14",
                               "marginal_breadth": "breadth read: 14",
                               "factor_tier": "exposure read: 14"},
        "state_vector": {"status": "MEASURED", "why": "admitted dims applied"},
        "regime": {"status": "MEASURED", "why": "regime probabilities applied"},
        "macro_regime": {"status": "MEASURED", "why": "macro labels applied"},
        "drift_overlay": {"status": "MEASURED", "why": "crisis share applied"},
        "evidence": {"sleeves": 19},
    }


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A sandbox laid out exactly like the desk, with every input fresh."""
    root = tmp_path
    reports, data = root / "desks" / "mt5" / "reports", root / "desks" / "mt5" / "data"
    monkeypatch.setattr(AL, "ROOT", root)
    monkeypatch.setattr(AL, "DESK", root / "desks" / "mt5")
    monkeypatch.setattr(AL, "REPORTS", reports)
    monkeypatch.setattr(AL, "DATA", data)
    monkeypatch.setattr(AL, "ALLOCATION", reports / "pf_allocation.json")
    monkeypatch.setattr(AL, "OUT", reports / "ALLOCATOR_LIVENESS.json")
    monkeypatch.setattr(AL, "STANDDOWN", reports / "ALLOCATOR_STANDDOWN.json")
    monkeypatch.setattr(AL, "PROOF_PATHS",
                        (root / "reports" / "ALLOCATOR_PROOF.json",
                         reports / "ALLOCATOR_PROOF.json"))
    _write(reports / "pf_allocation.json", _allocation())
    _write(root / "reports" / "ALLOCATOR_PROOF.json", {"passed": True, "at": "2026-09-23"})
    (reports / "DONE_pf_allocation").write_text("2026-09-23", encoding="utf-8")
    (data).mkdir(parents=True, exist_ok=True)
    (data / "pf_forecast_log.jsonl").write_text("{}\n", encoding="utf-8")
    for spec in AL.inputs():
        rel = spec.path.relative_to(AL.DESK)
        _write(root / "desks" / "mt5" / rel, {"at": "2026-09-23T09:00:00+00:00"})
    _write(data / "sleeves.json", {"sleeves": [
        {"name": "gold_afternoon", "symbol": "XAUUSD", "status": "LIVE", "risk_frac": 0.03}]})
    return root


def test_healthy_desk_is_live_with_no_breaches(desk: Path) -> None:
    rep = AL.measure()
    assert rep["verdict"] == "LIVE"
    assert rep["breaches"] == [], rep["breaches"]
    assert rep["ok"] is True


def test_every_output_names_a_consumer(desk: Path) -> None:
    """An artifact nothing reads is dead architecture; the report must name the reader."""
    rep = AL.measure()
    assert {r["key"] for r in rep["outputs"]} == {"allocation", "proof", "done_marker",
                                                  "forecast_log"}
    for row in rep["outputs"]:
        assert row["consumers"], row["key"]


def test_every_input_is_published_with_its_age(desk: Path) -> None:
    rep = AL.measure()
    keys = {r["key"] for r in rep["inputs"]}
    assert {"state_vector", "net_edge", "allocator_evidence", "regime_state"} <= keys
    for row in rep["inputs"]:
        assert row["age_h"] is not None and row["verdict"] == "FRESH"
        assert row["how_used"]


def test_stale_input_the_pass_claims_it_used_is_a_breach(desk: Path) -> None:
    """The 18.7h state_vector: conditioning on yesterday's world while reporting today's."""
    sv = AL.DATA / "state_vector.json"
    old = time.time() - 19 * 3600
    import os
    os.utime(sv, (old, old))
    rep = AL.measure()
    checks = [b["check"] for b in rep["breaches"]]
    assert "INPUT_STATE_VECTOR" in checks
    row = next(r for r in rep["inputs"] if r["key"] == "state_vector")
    assert row["verdict"] == "STALE" and row["degraded_honestly"] is False


def test_stale_input_the_pass_declared_unmeasured_is_not_a_breach(desk: Path) -> None:
    """Degrading honestly is legal; hiding the degrade is not."""
    doc = _allocation()
    doc["state_vector"] = {"status": "UNMEASURED",
                           "why": "state_vector.json is 19.0h old: every dimension neutral"}
    _write(AL.ALLOCATION, doc)
    import os
    old = time.time() - 19 * 3600
    os.utime(AL.DATA / "state_vector.json", (old, old))
    rep = AL.measure()
    assert "INPUT_STATE_VECTOR" not in [b["check"] for b in rep["breaches"]]
    row = next(r for r in rep["inputs"] if r["key"] == "state_vector")
    assert row["used"] is False and row["degraded_honestly"] is True


def test_missing_allocation_with_no_stand_down_is_SILENT(desk: Path) -> None:
    AL.ALLOCATION.unlink()
    rep = AL.measure()
    checks = [b["check"] for b in rep["breaches"]]
    assert "ALLOCATION" in checks and "SILENT" in checks
    assert rep["verdict"] == "ABSENT"


def test_named_stand_down_covers_the_gap(desk: Path) -> None:
    """Absence must be impossible to confuse with a decision -- a named stand-down IS one."""
    AL.ALLOCATION.unlink()
    _write(AL.STANDDOWN, {"status": "STOOD_DOWN", "mode": "fast", "reason": "MEMORY",
                          "why": "needs ~350MB, box has 210MB free"})
    rep = AL.measure()
    checks = [b["check"] for b in rep["breaches"]]
    assert "SILENT" not in checks
    assert rep["verdict"] == "STOOD_DOWN"
    assert rep["stand_down"]["reason"] == "MEMORY"


def test_stale_allocation_and_stale_proof_both_breach(desk: Path) -> None:
    import os
    old = time.time() - 40 * 3600
    os.utime(AL.ALLOCATION, (old, old))
    os.utime(AL.PROOF_PATHS[0], (old, old))
    rep = AL.measure()
    checks = [b["check"] for b in rep["breaches"]]
    assert "ALLOCATION_STALE" in checks and "PROOF_STALE" in checks


def test_heat_is_published_against_the_floor(desk: Path) -> None:
    rep = AL.measure()
    heat = rep["heat"]
    assert heat["status"] == "MEASURED"
    assert heat["resolved"] == 0.225
    assert heat["book_sum"] == pytest.approx(0.225)
    # The floor is read from the desk's own constant, never chosen here.
    assert heat["floor"] == pytest.approx(0.20)
    assert heat["at_or_above_floor"] is True


def test_run_writes_the_artifact(desk: Path) -> None:
    rep = AL.run(budget_s=30.0)
    assert AL.OUT.exists()
    on_disk = json.loads(AL.OUT.read_text(encoding="utf-8"))
    assert on_disk["verdict"] == rep["verdict"] == "LIVE"


def test_main_never_exits_nonzero_even_on_breaches(desk: Path) -> None:
    """The leg publishes; the FENCE fails. A measurement organ that exited 1 would take the
    remaining legs of the hourly cycle with it."""
    AL.ALLOCATION.unlink()
    assert AL.main(["--once", "--budget-s", "5"]) == 0


# ------------------------------------------------------------------------------------- fence


def test_fence_passes_on_a_healthy_desk(desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    AL.run(budget_s=30.0)
    monkeypatch.setattr(FENCE, "LIVENESS", AL.OUT)
    monkeypatch.setattr(FENCE, "_EVIDENCE_OF_AN_ALLOCATOR", (AL.ALLOCATION,))
    assert FENCE.check()["status"] == "OK"


def test_fence_fails_when_the_allocation_is_silent(desk: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    AL.run(budget_s=30.0)
    monkeypatch.setattr(FENCE, "LIVENESS", AL.OUT)
    monkeypatch.setattr(FENCE, "_EVIDENCE_OF_AN_ALLOCATOR", (AL.OUT,))
    AL.ALLOCATION.unlink()
    res = FENCE.check()
    assert res["status"] == "FAIL"
    assert "SILENT" in [f["check"] for f in res["findings"]]


def test_fence_fails_when_its_own_report_stops(desk: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """A fence whose measurement stopped publishing is a claim the desk cannot cash (L1.49)."""
    monkeypatch.setattr(FENCE, "LIVENESS", AL.OUT)
    monkeypatch.setattr(FENCE, "_EVIDENCE_OF_AN_ALLOCATOR", (AL.ALLOCATION,))
    res = FENCE.check()
    assert res["status"] == "FAIL"
    assert "REPORT_ABSENT" in [f["check"] for f in res["findings"]]


def test_fence_is_unmeasured_on_a_host_with_no_allocator(monkeypatch: pytest.MonkeyPatch,
                                                         tmp_path: Path) -> None:
    monkeypatch.setattr(FENCE, "_EVIDENCE_OF_AN_ALLOCATOR", (tmp_path / "nothing.json",))
    assert FENCE.check()["status"] == "UNMEASURED"
    assert FENCE.check(require_state=True)["status"] == "FAIL"


def test_fence_is_registered_in_the_law_gate() -> None:
    """LAWS 7: unwired is a defect. A fence nothing runs blocks nothing."""
    text = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_allocator_liveness.py", ())' in text


# ------------------------------------------------------- the net-edge door into the allocator


def test_net_of_cost_reaches_the_allocator_through_consumed_inputs() -> None:
    """DOOR (c): the spine's net-of-cost tilt must arrive where pf_allocator reads it.

    It was in TERM_SPECS and in CONSUMED_TILT_TERMS, `financing_lab` wrote it onto every row
    from NET_EDGE.json every hour -- and `consumed_inputs`, the ONLY function pf_allocator reads
    the pack through, returned lineage and financing alone. The term reached the artifact and
    stopped there.
    """
    from datetime import UTC, datetime

    from libs.portfolio.allocator_evidence import CONSUMED_TILT_TERMS, consumed_inputs
    assert "net_of_cost" in CONSUMED_TILT_TERMS
    doc = {"kind": "evidence", "at": datetime.now(tz=UTC).isoformat(),
           "sleeves": {"gold_asia": {"lineage_factor": 1.0,
                                     "terms": {"net_of_cost": {"factor": 1.4}}},
                       "chf_carry": {"lineage_factor": 1.0,
                                     "terms": {"net_of_cost": {"factor": 0.6}}},
                       "no_term": {"lineage_factor": 1.0}}}
    rows, why = consumed_inputs(doc)
    assert rows["gold_asia"]["net_of_cost_factor"] == pytest.approx(1.4)
    assert rows["chf_carry"]["net_of_cost_factor"] == pytest.approx(0.6)
    # A sleeve the spine could not price reads exactly neutral -- never a silent 0.
    assert rows["no_term"]["net_of_cost_factor"] == pytest.approx(1.0)
    assert why


def test_net_of_cost_is_multiplied_into_the_allocator_tilt() -> None:
    """The tilt pf_allocator applies must include the net-of-cost factor, two-sided."""
    src = (DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert 'nf = float(row.get("net_of_cost_factor", 1.0))' in src
    assert "lf * rf * pf * bf * tf * nf" in src


def test_pf_allocator_records_a_named_stand_down_on_every_silent_path() -> None:
    """A pass that ends without an allocation must say why, by name (L1.28a)."""
    src = (DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert src.count("_record_stand_down(") == 4        # 3 call sites + the definition
    for reason in ('"MEMORY"', '"LOCK"', '"FAILED"'):
        assert reason in src
    assert "_clear_stand_down(args.mode)" in src


# ---------------------------------------------------- the join: the book must reach the rows


def _gateway_book_key():
    """`gateway._book_key` lifted out of the module, so the test needs no MetaTrader5 package.

    The fence keeps a COPY of this function on purpose (it must run on a box with no MT5), and a
    copy that drifts is exactly the defect the fence exists to catch -- so the two are compared
    here rather than trusted.
    """
    import re as _re
    import textwrap
    src = (DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    start = src.index("def _book_key(")
    end = src.index("\ndef ", start + 1)
    ns: dict = {"re": _re}
    exec(textwrap.dedent(src[start:end]), ns)
    return ns["_book_key"]


@pytest.mark.parametrize("row,book,expect", [
    # the version suffix: the live rows carry it, the allocator prices the window
    ({"name": "gold_afternoon_v3"}, {"gold_afternoon": 0.02}, "gold_afternoon"),
    ({"name": "gold_london_am_v2"}, {"gold_london_am": 0.03}, "gold_london_am"),
    # an exact name still wins, so a book that carries its own version is untouched
    ({"name": "gold_afternoon_v3"}, {"gold_afternoon_v3": 0.02, "gold_afternoon": 0.01},
     "gold_afternoon_v3"),
    # a genuine miss stays a miss: m5 and m15 are different sleeves, not a suffix apart
    ({"name": "xau_m5_anti_breakout_overlap"}, {"xau_m15_anti_breakout": 0.03}, None),
    # the derived SYMBOL_family_selector key still works
    ({"name": "chfnok_carry_asia_p_98d7", "symbol": "chfnok", "family": "carry",
      "selector": "asia"}, {"CHFNOK_carry_asia": 0.02}, "CHFNOK_carry_asia"),
    ({"name": "x"}, {}, None),
])
def test_book_key_joins_versioned_rows_and_the_two_copies_agree(row, book, expect) -> None:
    from scripts.check_allocator_join import _book_key as fence_key
    gw_key = _gateway_book_key()
    assert fence_key(row, book) == expect
    assert gw_key(row, book) == expect


def test_the_join_fix_can_only_raise_a_live_row_never_lower_it() -> None:
    """NEVER REDUCE AGGRESSIVENESS (principal, standing order).

    `clamp_risk_frac` FLOORS at BASE_RISK_FRAC, so a row that newly joins a book fraction BELOW
    the base is sized exactly as it was, and one that joins a fraction above it goes UP. The
    join can therefore only raise the live book. Measured on the box 2026-09-23: 0/7 rows joined
    at sum_risk_frac 0.2100 became 6/7 at 0.2272.
    """
    from mt5desk.sizing import BASE_RISK_FRAC, clamp_risk_frac
    from scripts.check_allocator_join import _book_key
    row = {"name": "gold_afternoon_v3", "risk_frac": BASE_RISK_FRAC}
    for book_frac in (0.0001, 0.005, BASE_RISK_FRAC, 0.0357, 0.09):
        key = _book_key(row, {"gold_afternoon": book_frac})
        assert key == "gold_afternoon"
        assert clamp_risk_frac(book_frac) >= clamp_risk_frac(row["risk_frac"]) - 1e-12 or \
            clamp_risk_frac(book_frac) == BASE_RISK_FRAC
