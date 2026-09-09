"""The daily execution-intelligence organ's alpha-capture half.

Pinned here:

  * with no fill corpus the organ reports UNMEASURED WITH THE REASON and writes no history point.
    A capture ratio of zero would read as an execution catastrophe when in fact nothing traded,
    and a trend line fitted through absences would describe the desk's trading frequency;
  * with a corpus it computes the ratio, splits it by sleeve, session and symbol, and appends
    exactly ONE history point per measured pass -- which is what makes the ratio trendable;
  * an append-only corpus is read LAST-ROW-PER-KEY, so a fill whose exit resolved on a later pass
    is counted once, at its resolved value;
  * the blocked models' sample requirements are in the daily report too, so "not yet" always
    arrives with a number the desk can plan against.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_intelligence as ei  # noqa: E402

from libs.execution import fill_corpus as fc  # noqa: E402


@pytest.fixture
def organ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every path under tmp_path. The box's real corpus is never read and never appended to."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    monkeypatch.setattr(ei, "CORPUS", data / "fill_corpus.jsonl")
    monkeypatch.setattr(ei, "HISTORY", data / "alpha_capture_history.jsonl")
    monkeypatch.setattr(ei, "CAPTURE_REPORT", reports / "ALPHA_CAPTURE.json")
    monkeypatch.setattr(ei, "SHADOW_TAPE", reports / "execution_quality.json")
    monkeypatch.setattr(ei, "SHADOW_LEDGERS", reports / "shadow")
    return tmp_path


# ------------------------------------------------- the shadow tape, when no fill has ever printed

def _tape(root: Path, cells: dict[str, dict]) -> None:
    p = root / "reports" / "execution_quality.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"measured_at": "2026-09-08T00:00:00+00:00", "filled": 40,
                             "unfilled": 3, "by_symbol_session": cells}), "utf-8")


def _cell(fills: int, slip_mean: float | None, spread_mean: float | None,
          n_slip: int | None = None) -> dict:
    n = fills if n_slip is None else n_slip
    return {"fills": fills,
            "slippage_R": {"n": n if slip_mean is not None else 0, "mean": slip_mean},
            "spread_at_fill": {"n": fills, "mean": spread_mean}}


def _ledger(root: Path, symbol: str, session: str, n: int, *, entry: float = 2000.0,
            exit_: float = 2010.0, r: float = 0.5) -> None:
    p = root / "reports" / "shadow" / f"ledger_{symbol}_{session}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{"entry_time": "2026-09-01T01:00:00", "side": "BUY",
                              "entry": entry, "exit": exit_, "r_multiple": r}
                             for _ in range(n)]), "utf-8")


def test_no_corpus_and_no_tape_is_unmeasured_on_both_bases(organ) -> None:
    d = ei.alpha_capture_report(write=True)
    assert d["status"] == "UNMEASURED"
    st = d["shadow_tape"]
    assert st["basis"] == "shadow_tape" and st["status"] == "UNMEASURED"
    assert "execution_quality.json absent" in st["why"]
    assert not ei.HISTORY.exists()


def test_the_shadow_tape_gives_a_ratio_labelled_shadow_tape_and_live_stays_unmeasured(
        organ) -> None:
    """BY HAND: bracket R 0.5 on a 20-point risk (2000 -> 2010 at 0.5R); slippage 0.05R; spread
    0.2 points at fill -> half of it over the risk = 0.005R. realised = 0.445, ratio = 0.89."""
    _tape(organ, {"XAUUSD.asia": _cell(40, 0.05, 0.2)})
    _ledger(organ, "XAUUSD", "asia", 40)
    d = ei.alpha_capture_report(write=True)
    assert d["status"] == "UNMEASURED", "live capture is still UNMEASURED: no fill has printed"
    assert "no fill corpus" in d["why"]
    st = d["shadow_tape"]
    assert st["basis"] == "shadow_tape" and st["status"] == "MEASURED"
    assert st["alpha_capture_ratio"] == pytest.approx(0.89, abs=1e-6)
    cell = st["by_symbol_session"]["XAUUSD.asia"]
    assert cell["predicted_bracket_r"] == pytest.approx(0.5)
    assert cell["realised_shadow_r"] == pytest.approx(0.445)
    assert cell["leakage"]["slippage"] == pytest.approx(0.05)
    assert cell["leakage"]["spread_exit_half"] == pytest.approx(0.005)
    assert "SIMULATED" in st["why_basis"] and "never a live capture ratio" in st["why_basis"]
    assert not ei.HISTORY.exists(), "a simulated ratio never enters the live history"
    written = json.loads(ei.CAPTURE_REPORT.read_text("utf-8"))
    assert written["shadow_tape"]["alpha_capture_ratio"] == pytest.approx(0.89, abs=1e-6)


def test_a_cell_without_a_ledger_has_no_denominator_and_says_so(organ) -> None:
    _tape(organ, {"XAUUSD.asia": _cell(40, 0.05, 0.2), "EURUSD.london": _cell(40, 0.02, 0.0001)})
    _ledger(organ, "XAUUSD", "asia", 40)
    st = ei.alpha_capture_report(write=False)["shadow_tape"]
    assert st["status"] == "MEASURED" and st["n_cells_measured"] == 1
    eur = st["by_symbol_session"]["EURUSD.london"]
    assert eur["status"] == "UNMEASURED" and "frictionless denominator" in eur["why"]
    assert st["n_fills"] == 40


def test_below_min_n_and_below_the_denominator_floor_are_unmeasured(organ) -> None:
    from libs.execution import alpha_capture as ac
    _tape(organ, {"XAUUSD.asia": _cell(40, 0.05, 0.2, n_slip=ac.MIN_N - 1),
                  "GBPUSD.london": _cell(40, 0.01, 0.0001)})
    _ledger(organ, "XAUUSD", "asia", 40)
    _ledger(organ, "GBPUSD", "london", 40, entry=1.3, exit_=1.3001, r=0.001)
    st = ei.alpha_capture_report(write=False)["shadow_tape"]
    assert st["status"] == "UNMEASURED" and st["alpha_capture_ratio"] is None
    assert f"needs {ac.MIN_N}" in st["by_symbol_session"]["XAUUSD.asia"]["why"]
    assert "below the" in st["by_symbol_session"]["GBPUSD.london"]["why"]


def test_a_corpus_row_takes_precedence_and_the_shadow_tape_is_not_consulted(organ) -> None:
    fc.append_rows(ei.CORPUS, [_row(i) for i in range(40)])
    _tape(organ, {"XAUUSD.asia": _cell(40, 0.05, 0.2)})
    d = ei.alpha_capture_report(write=False)
    assert d["status"] == "MEASURED" and "shadow_tape" not in d


def test_run_reports_the_shadow_basis_beside_the_live_status(organ, monkeypatch) -> None:
    _tape(organ, {"XAUUSD.asia": _cell(40, 0.05, 0.2)})
    _ledger(organ, "XAUUSD", "asia", 40)
    monkeypatch.setattr(ei.fill_surface, "run", lambda write=True: {"note": "n/a", "n_fills": 0})
    monkeypatch.setattr(ei.netting, "savings_report",
                        lambda *a, **k: {"verdict": "UNMEASURED", "opposing_share": None})
    d = ei.run()
    assert d["alpha_capture"] == "UNMEASURED"
    assert d["alpha_capture_shadow_tape"] == "MEASURED"
    assert d["alpha_capture_shadow_tape_basis"] == "shadow_tape"
    assert d["alpha_capture_ratio_shadow_tape"] == pytest.approx(0.89, abs=1e-6)


def _row(i: int, *, realized: float = 0.17, predicted: float = 0.25,
         key_suffix: str = "", **over) -> dict:
    rec = fc.FillRecord(
        record_id=f"r{i}{key_suffix}", intent_id=f"i{i}", symbol="XAUUSD", sleeve="gold",
        session="asia", status="FILLED", account_kind="live", realized_r=realized,
        posterior_edge_r=predicted, stop_frac=0.01, slip_r=0.03,
        spread_frac_at_decision=0.0001, commission_r=0.01, algo="market", direction=1,
        **over)
    return rec.to_row()


def test_no_corpus_is_unmeasured_with_the_reason_and_writes_no_history_point(organ) -> None:
    d = ei.alpha_capture_report(write=True)
    assert d["status"] == "UNMEASURED"
    assert "no fill corpus" in d["why"] and "NOT a capture ratio of zero" in d["why"]
    assert d["corpus"]["unique_executions"] == 0
    assert not ei.HISTORY.exists()
    # the report is still written, and it still carries what the blocked models need
    written = json.loads(ei.CAPTURE_REPORT.read_text("utf-8"))
    assert written["requirements"]["meta_label"]["n_total_labelled_outcomes"] > 0
    assert written["requirements"]["execution_choice"]["tiers"]["full"]["n_cells"] == 180


def test_a_corpus_gives_a_ratio_split_three_ways_and_exactly_one_history_point(organ) -> None:
    fc.append_rows(ei.CORPUS, [_row(i) for i in range(40)])
    d = ei.alpha_capture_report(write=True)
    assert d["status"] == "MEASURED"
    assert d["alpha_capture_ratio"] == pytest.approx(0.17 / 0.25, abs=1e-6)
    cap = d["capture"]
    assert cap["by_sleeve"]["gold"]["status"] == "MEASURED"
    assert cap["by_session"]["asia"]["n"] == 40 and cap["by_symbol"]["XAUUSD"]["n"] == 40
    points = fc.read_rows(ei.HISTORY)
    assert len(points) == 1 and points[0]["ratio"] == pytest.approx(0.68, abs=1e-6)
    assert points[0]["leakage"]["residual"] == pytest.approx(0.03, abs=1e-6)
    # a second pass appends a second point, and the trend then has something to fit
    ei.alpha_capture_report(write=True)
    assert len(fc.read_rows(ei.HISTORY)) == 2


def test_the_last_row_per_key_is_the_truth_so_a_late_exit_is_counted_once(organ) -> None:
    """The corpus is append-only: a fill written UNRESOLVED and re-written when its deal arrived
    appears twice on disk and must count once, at its RESOLVED value."""
    fc.append_rows(ei.CORPUS, [_row(i, realized=0.05) for i in range(40)])
    fc.append_rows(ei.CORPUS, [_row(i, realized=0.17) for i in range(40)])
    d = ei.alpha_capture_report(write=False)
    assert d["corpus"]["rows"] == 80 and d["corpus"]["unique_executions"] == 40
    assert d["alpha_capture_ratio"] == pytest.approx(0.17 / 0.25, abs=1e-6)


def test_run_never_lets_the_capture_half_take_the_daily_organ_down(organ, monkeypatch) -> None:
    """The daily cycle catches per-organ failures, but a capture-ratio fault must not cost the
    fill surface and the netting report that run beside it."""
    def boom(*_a, **_k):
        raise RuntimeError("corpus unreadable")

    monkeypatch.setattr(ei, "alpha_capture_report", boom)
    monkeypatch.setattr(ei.fill_surface, "run", lambda write=True: {"note": "n/a", "n_fills": 0})
    monkeypatch.setattr(ei.netting, "savings_report",
                        lambda *a, **k: {"verdict": "UNMEASURED", "opposing_share": None})
    d = ei.run()
    assert d["alpha_capture"] == "UNMEASURED" and "corpus unreadable" in d["alpha_capture_why"]
    assert d["fill_surface"] == "n/a"
