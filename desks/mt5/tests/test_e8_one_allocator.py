"""E8 joins the one allocator (one-pipe step 1): E8's own solve sizes its sleeves when fresh."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK.parent.parent), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import prop_challenge_allocator as pca  # noqa: E402
from prop import e8_book  # noqa: E402

NOW = datetime(2026, 11, 24, 21, 0, tzinfo=UTC)


def _solve(tmp: Path, **kw: object) -> Path:
    doc = {"venue": "e8", "deployable": True, "status": "OK",
           "generated_at": (NOW - timedelta(minutes=30)).isoformat(),
           "solved_columns": ["EURUSD_srb_london", "AUDCAD_carry_asia"],
           "executable": {"EURUSD_srb_london": 0.004}, **kw}
    p = tmp / "E8_ALLOCATOR.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_a_fresh_e8_solve_prices_every_solved_column(tmp_path):
    book, why = e8_book.e8_solved_book(_solve(tmp_path), NOW)
    assert book == {"EURUSD_srb_london": 0.004, "AUDCAD_carry_asia": 0.0}, why


def test_stale_foreign_or_undeployable_solves_change_nothing(tmp_path):
    for kw in ({"generated_at": (NOW - timedelta(hours=3)).isoformat()}, {"venue": "ftmo"},
               {"deployable": False}, {"generated_at": "x"}, {"solved_columns": None}):
        assert e8_book.e8_solved_book(_solve(tmp_path, **kw), NOW)[0] == {}
    assert e8_book.e8_solved_book(tmp_path / "absent.json", NOW)[0] == {}


def test_a_solve_fraction_above_the_e8_ceiling_is_clipped_to_it(tmp_path):
    from mt5desk.decision_core import E8_CERT_CEILING
    p = _solve(tmp_path, executable={"EURUSD_srb_london": 1.0})
    assert e8_book.e8_solved_book(p, NOW)[0]["EURUSD_srb_london"] == E8_CERT_CEILING


def test_the_solve_sizes_up_down_and_to_zero_and_leaves_unpriced_rows_alone():
    rows = [{"symbol": "EURUSD", "family": "srb", "selector": "london", "risk_frac": 0.001},
            {"symbol": "AUDCAD", "family": "carry", "selector": "asia", "risk_frac": 0.001},
            {"symbol": "NZDJPY", "family": "clock", "selector": "asia", "risk_frac": 0.001}]
    kept, zeroed = e8_book.apply_solved(rows, {"EURUSD_srb_london": 0.004,
                                               "AUDCAD_carry_asia": 0.0})
    assert [z["column"] for z in zeroed] == ["AUDCAD_carry_asia"]
    assert zeroed[0]["missed_growth_risk_frac"] == 0.001
    assert {r["symbol"]: r["risk_frac"] for r in kept} == {"EURUSD": 0.004, "NZDJPY": 0.001}
    assert kept[0]["risk_source"].startswith("one allocator")


def _guard(eq: float, start: float, verdict: str, at: datetime) -> dict:
    """prop/e8_guard.write_report's shape."""
    return {"generated_utc": at.isoformat(), "account": {"balance": 100000.0},
            "decision": {"verdict": verdict, "equity": eq, "day_start": start,
                         "room_to_daily_floor": eq - start * 0.975}}


def test_e8_state_reads_the_guard(tmp_path):
    g = tmp_path / "E8_GUARD.json"
    g.write_text(json.dumps(_guard(102000.0, 101000.0, "OK", NOW - timedelta(minutes=5))),
                 encoding="utf-8")
    st = pca.read_e8_state(g, now=NOW)
    assert st.measured and st.phase == "phase1"
    assert abs(st.equity - 1.02) < 1e-9 and abs(st.day_start - 1.01) < 1e-9


def test_e8_state_stale_breached_or_absent_is_not_deployable(tmp_path):
    g = tmp_path / "E8_GUARD.json"
    g.write_text(json.dumps(_guard(1.0e5, 1.0e5, "OK", NOW - timedelta(hours=5))),
                 encoding="utf-8")
    assert pca.read_e8_state(g, now=NOW).status == "STALE"
    g.write_text(json.dumps(_guard(8.9e4, 9e4, "BREACHED", NOW)), encoding="utf-8")
    assert pca.read_e8_state(g, now=NOW).status == "BREACHED"
    for eq, extra in ((0.0, {}), (1.0e5, {"equity_from_balance": 1.0})):
        doc = _guard(eq, 1.0e5, "OK", NOW)
        doc["decision"].update(extra)
        g.write_text(json.dumps(doc), encoding="utf-8")
        assert not pca.read_e8_state(g, now=NOW).measured
    assert not pca.read_e8_state(tmp_path / "none.json", now=NOW).measured


def test_main_solves_every_venue_into_its_own_file(monkeypatch, tmp_path):
    seen: list[tuple[str, Path]] = []
    monkeypatch.setattr(pca, "_run_venue",
                        lambda v, p, s, out: seen.append((v, out)) or 0)
    assert pca.main([]) == 0
    assert seen == [("ftmo", pca.OUT), ("e8", pca.E8_OUT)]


def test_one_venue_failing_does_not_cost_the_other(monkeypatch):
    seen: list[str] = []

    def run(v: str, p: int, s: int, out: Path) -> int:
        if v == "ftmo":
            raise RuntimeError("boom")
        seen.append(v)
        return 0
    monkeypatch.setattr(pca, "_run_venue", run)
    assert pca.main([]) == 1 and seen == ["e8"]


def test_a_doubted_row_is_capped_by_its_evidence_multiple_of_the_e8_ceiling():
    """Audit MF-2b: the cap is evidence_mult x E8_CERT_CEILING, so a doubted row stays below it."""
    from mt5desk.decision_core import E8_CERT_CEILING
    rows = [{"symbol": "EURUSD", "family": "srb", "selector": "london", "risk_frac": 0.0005,
             "evidence_mult": 0.25, "doubt_codes": ["placebo_alarm"]},
            {"symbol": "GBPUSD", "family": "srb", "selector": "london", "risk_frac": 0.0005,
             "evidence_mult": 1.0}]
    kept, _ = e8_book.apply_solved(rows, {"EURUSD_srb_london": E8_CERT_CEILING,
                                          "GBPUSD_srb_london": 0.01})
    by = {r["symbol"]: r for r in kept}
    assert by["EURUSD"]["risk_frac"] == round(0.25 * E8_CERT_CEILING, 6) < E8_CERT_CEILING
    assert by["EURUSD"]["evidence_capped_from"] == E8_CERT_CEILING
    assert by["GBPUSD"]["risk_frac"] == E8_CERT_CEILING


def test_a_principal_funded_row_keeps_its_size_and_journals_the_solve():
    """Audit MF-3: a solve zero never drops a principal-funded key."""
    rows = [{"symbol": "USDJPY", "family": "daily", "selector": "asia", "risk_frac": 0.004,
             "principal_funded": True}]
    kept, zeroed = e8_book.apply_solved(rows, {"USDJPY_daily_asia": 0.0})
    assert kept[0]["risk_frac"] == 0.004 and kept[0]["solve_risk_frac"] == 0.0
    assert zeroed == []
