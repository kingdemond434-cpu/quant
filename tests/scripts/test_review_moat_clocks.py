"""READING THE FORWARD CLOCK -- the only out-of-sample evidence the moat pipeline produces.

mine -> screen -> register -> promote buys a forward clock, and until this organ existed nothing
read one. That is the same failure as a survivor registry nobody adjudicates, one stage later and
more expensive: the desk would have been paying days into a waiting room with no door.

The tests that carry the most weight are the two about CONTAMINATION, because both failures are
invisible in the output -- the number they produce looks exactly like a real one:

  a cell from the registration day itself must NOT count as forward, and
  nothing may be re-selected: one candidate, one specification, one number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.review_moat_clocks as R  # noqa: E402
import scripts.screen_moat as SM  # noqa: E402
from tests.scripts.test_screen_moat import _tape  # noqa: E402

# ------------------------------------------------------------------ the cutoff

def test_a_cell_from_the_registration_day_is_not_forward_tape() -> None:
    """THE MOST FLATTERING POSSIBLE BUG. Part of the registration day predates the clock and there
    is no way to tell which part, so counting it re-uses the very evidence that earned the clock
    -- turning an out-of-sample check into a slightly noisier in-sample one."""
    cutoff = "2026-01-04T12:00:00+00:00"
    assert R._day_after("20260105", cutoff) is True
    assert R._day_after("20260104", cutoff) is False, "the registration day is contaminated"
    assert R._day_after("20260103", cutoff) is False
    assert R._day_after("20260104_00", cutoff) is False   # the real cell-key shape


def test_an_unparseable_day_is_excluded_rather_than_assumed_forward() -> None:
    """A cell whose date cannot be read must not be counted as evidence FOR the candidate. The
    permissive default is the one that manufactures a result."""
    assert R._day_after("not-a-date", "2026-01-04T00:00:00+00:00") is False
    assert R._day_after("20260105", "garbage") is False


# ----------------------------------------------------------------- the verdicts

def _fwd(ic: float, cells: int = 5) -> dict:
    return {"state": "MEASURED", "cells": cells, "forward_cells": cells,
            "forward_ic_mean": ic, "forward_ic_median": ic, "forward_sign_stability": 1.0,
            "forward_n_total": 500, "days": [f"2026010{i}" for i in range(cells)]}


def test_an_edge_that_holds_its_sign_and_half_its_size_is_HOLDING() -> None:
    """Half deliberately: in-sample magnitude is biased upward by the selection that produced it,
    so demanding the full number would refute every real edge along with every false one."""
    v, why = R.verdict(0.10, _fwd(0.06))
    assert v == "HOLDING" and "never seen" in why


def test_an_edge_that_inverts_is_a_refutation_not_decay() -> None:
    v, why = R.verdict(0.10, _fwd(-0.08))
    assert v == "INVERTED"
    assert "was never there" in why


def test_an_edge_that_shrinks_below_half_is_DECAYED_not_dead() -> None:
    """Decay is not failure -- an edge that half-lives can still be tradeable at the right size --
    but it is not the edge that was pre-registered, and collapsing the two loses that."""
    v, _ = R.verdict(0.10, _fwd(0.03))
    assert v == "DECAYED"


def test_a_forward_ic_below_the_floor_is_DEAD_whatever_its_sign() -> None:
    v, _ = R.verdict(0.10, _fwd(0.005))
    assert v == "DEAD"


def test_one_forward_cell_is_a_reading_not_evidence() -> None:
    v, why = R.verdict(0.10, _fwd(0.09, cells=1))
    assert v == "TOO-EARLY" and "not evidence" in why


def test_no_forward_tape_is_reported_not_scored() -> None:
    v, _ = R.verdict(0.10, {"state": "NO-FORWARD-TAPE", "cells": 0})
    assert v == "NO-FORWARD-DATA"


def test_a_missing_baseline_cannot_be_invented() -> None:
    """Without an in-sample number there is nothing to compare against, and defaulting it would
    make every forward reading look like whatever the default implied."""
    assert R.verdict(None, _fwd(0.09))[0] == "NO-BASELINE"
    assert R.verdict(0.0, _fwd(0.09))[0] == "NO-BASELINE"


# ------------------------------------------------------------ real forward tape

def test_forward_ic_reads_only_post_registration_cells(tmp_path, monkeypatch) -> None:
    """END TO END ON REAL TAPE. Nine days exist; the clock starts after day four; only the later
    cells may contribute, and the organ must say how many it used."""
    root = tmp_path / "moat"
    stage = tmp_path / "stage"
    for day in [f"2026010{i}_00" for i in range(1, 10)]:
        _tape(stage, predictive=True, n=400, seed=abs(hash(day)) % 9999, day=day)
        src = stage / "binance" / "BTCUSDT" / f"{day}.jsonl.gz"
        d = root / "binance" / "BTCUSDT"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{day}.jsonl.gz").write_bytes(src.read_bytes())
        src.unlink()

    monkeypatch.setattr(SM, "MOAT", root)
    out = R.forward_ic("binance:BTCUSDT", "imbalance", 60,
                       "2026-01-04T00:00:00+00:00", budget=12)
    assert out["state"] == "MEASURED"
    # Days 5..9 are forward; 1..4 are not. The cell count is the cutoff working.
    assert out["cells"] == 5, f"cutoff admitted the wrong cells: {out}"
    assert set(out["days"]) == {f"2026010{i}" for i in range(5, 10)}


def test_it_reuses_the_screens_alignment_rather_than_re_deriving_it() -> None:
    """The screen's alignment took FIVE corrections -- entry priced before the signal, a
    double-shifted target, a daily-calibrated Sharpe rail, horizons that were not strides, a
    stepdown fed constants. A second implementation here would be a sixth waiting to happen."""
    import inspect
    src = inspect.getsource(R.forward_ic)
    assert "SM.screen_symbol" in src
    assert "stage_a_screen" not in src, "the screen is called, not re-implemented"


def test_nothing_is_re_selected_across_mechanisms_or_horizons() -> None:
    """A confirmation that searches for the version which still works is a fresh search wearing
    the vocabulary of a confirmation -- and it restores every multiple-testing problem the
    pipeline spent four organs removing."""
    import inspect
    src = inspect.getsource(R.forward_ic)
    assert 'r.get("mechanism") == mechanism' in src
    assert 'r.get("horizon_s") == horizon_s' in src
    for banned in ("max(", "argmax", "best"):
        assert banned not in src, f"forward_ic must not optimise over anything: {banned}"


# ------------------------------------------------------------------- the organ

def test_nothing_pre_registered_is_reported_not_invented(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(R, "PREREG", tmp_path / "none.json")
    monkeypatch.setattr(R, "REPORT", tmp_path / "out.json")
    sys.argv = ["review_moat_clocks.py"]
    assert R.main() == 0
    rep = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert rep["state"] == "NOTHING PRE-REGISTERED"


def test_the_reviewer_has_no_authority(tmp_path, monkeypatch) -> None:
    """A HOLDING verdict is evidence for a later decision, not the decision. Fenced by source
    inspection because the temptation to wire a passing forward test straight to a weight is
    exactly what the two-stage law exists to resist."""
    monkeypatch.setattr(R, "PREREG", tmp_path / "p.json")
    monkeypatch.setattr(R, "REPORT", tmp_path / "out.json")
    (tmp_path / "p.json").write_text(json.dumps({
        "binance:BTCUSDT|imbalance|60": {
            "symbol": "binance:BTCUSDT", "mechanism": "imbalance", "horizon_s": 60,
            "pre_registered": "2026-01-04T00:00:00+00:00",
            "ic_mean": 0.08, "clock_days": 3}}), "utf-8")
    sys.argv = ["review_moat_clocks.py"]
    assert R.main() == 0
    rep = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert rep["authority"].startswith("NONE")
    src = Path("scripts/review_moat_clocks.py").read_text("utf-8")
    for banned in ("gated_leverage", "allocate_with_capacity", "place_order",
                   "max_sharpe_weights", "kelly", "notional"):
        assert banned not in src, f"the reviewer must not reach sizing: {banned}"


def test_every_reviewed_candidate_gets_a_verdict_and_a_reason(tmp_path, monkeypatch) -> None:
    """Reporting only the holders is p-hacking one stage further down the pipeline."""
    monkeypatch.setattr(R, "PREREG", tmp_path / "p.json")
    monkeypatch.setattr(R, "REPORT", tmp_path / "out.json")
    (tmp_path / "p.json").write_text(json.dumps({
        f"s{i}|imbalance|60": {"symbol": f"v:S{i}", "mechanism": "imbalance", "horizon_s": 60,
                               "pre_registered": "2026-01-04T00:00:00+00:00", "ic_mean": 0.08}
        for i in range(3)}), "utf-8")
    sys.argv = ["review_moat_clocks.py"]
    assert R.main() == 0
    rep = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert rep["reviewed"] == 3
    assert sum(rep["tally"].values()) == 3
    assert all(r.get("why") for r in rep["results"])
    assert np.isfinite(len(rep["results"]))
