"""The organ that makes libs/ict more than a library nobody calls.

WHY IT EXISTS IS AN ADMISSION. Fourteen detectors landed with full test suites and no caller --
the desk's own "built but never runs" class, committed while fixing instances of it elsewhere. A
family wired to nothing produces exactly as much E[log W] as not building it.

The tests below are mostly about the REFUSALS, because on a desk with a 420/420 prior the ways a
screen can lie are more consequential than the ways it can pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.screen_ict as S


def _panel(tmp: Path, n: int = 1200, seed: int = 4) -> Path:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    sp = np.abs(rng.normal(0, 0.8, n)) + 0.1
    o = np.r_[c[0], c[:-1]]
    (tmp / "bars").mkdir(exist_ok=True)
    pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + sp,
                  "low": np.minimum(o, c) - sp, "close": c,
                  "open_interest": 1e6 + np.cumsum(rng.normal(0, 2000, n))
                  }).to_csv(tmp / "bars/b.csv", index=False)
    return tmp / "bars"


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "BARS", tmp_path / "bars")
    monkeypatch.setattr(S, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(S, "HISTORY", tmp_path / "h.jsonl")
    return tmp_path


def test_absent_bars_are_never_synthesised(desk) -> None:
    """THE REFUSAL THAT MATTERS MOST. Generating bars to keep the organ busy would produce
    verdicts about the GENERATOR, and they would enter the funnel wearing the same vocabulary as
    real ones -- indistinguishable downstream, forever."""
    assert S.main() == 0
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    assert rep["state"] == "NO BARS"
    assert rep["screened"] == 0
    assert "NOT synthesised" in rep["note"]


def test_every_detector_is_screened_and_logged_win_or_lose(desk) -> None:
    """§26.3: reporting only the printer is p-hacking. Fourteen screened and fourteen weak is a
    publishable outcome and the one the desk's prior expects."""
    _panel(desk)
    assert S.main() == 0
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    assert rep["screened"] == len(S.DETECTORS) == 14
    assert len(rep["results"]) == 14
    assert sum(rep["tally"].values()) == 14


def test_a_random_walk_produces_no_interesting_signal(desk) -> None:
    """The single most important negative. If pattern detectors scored INTERESTING on a random
    walk, the screen would be measuring the detectors' own arithmetic, not the market."""
    _panel(desk)
    S.main()
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    assert rep["interesting"] == [], rep["interesting"]
    assert rep["suspect_lookahead"] == []


def test_underpowered_is_not_recorded_as_refuted(desk) -> None:
    """SCREEN-WEAK is graveyard-grade negative knowledge; SCREEN-UNDERPOWERED means the sample
    could not resolve the question either way. Conflating them lets a thin sample 'kill' a family
    and books negative knowledge the desk never earned."""
    _panel(desk, n=400)
    S.main()
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    assert rep["tally"].get("SCREEN-UNDERPOWERED", 0) > 0
    assert "recording it as negative knowledge the desk did not earn" in rep["note"]


def test_a_missing_perp_column_is_reported_not_imputed(desk) -> None:
    """The crypto-native detectors need open_interest. Filling a plausible value would make the
    most informative detector on the desk into the least trustworthy one."""
    p = _panel(desk)
    df = pd.read_csv(p / "b.csv").drop(columns=["open_interest"])
    df.to_csv(p / "b.csv", index=False)
    S.main()
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    verdicts = {r["detector"]: r["verdict"] for r in rep["results"]}
    assert verdicts["ict_oi_flush"] in ("INPUT-MISSING", "DEGENERATE"), verdicts["ict_oi_flush"]


def test_one_broken_detector_does_not_kill_the_run(desk) -> None:
    """This runs in the cadence. Taking the cycle down to report one bad detector is a blast
    radius that does not match the failure."""
    _panel(desk)

    def _boom(_df):
        raise RuntimeError("synthetic")

    S.main()
    r = S.screen_one("broken", _boom, pd.read_csv(desk / "bars/b.csv"), 1.0)
    assert r["verdict"] == "ERROR" and "synthetic" in r["why"]


def test_the_organ_claims_no_promotion_authority(desk) -> None:
    _panel(desk)
    S.main()
    rep = json.loads((desk / "r.json").read_text("utf-8"))
    assert "NONE" in rep["authority"] and "stage A" in rep["authority"]


def test_history_is_append_only(desk) -> None:
    _panel(desk)
    S.main()
    S.main()
    assert len((desk / "h.jsonl").read_text("utf-8").strip().splitlines()) == 2
