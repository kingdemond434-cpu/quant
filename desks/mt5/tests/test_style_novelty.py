"""Style novelty: a textbook style reads as textbook, an unexplained one reads as novel, PIT."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import style_novelty as sn  # noqa: E402


@dataclass
class _Sig:
    time: Any
    side: int
    ttl_bars: int = 24
    trigger: float | None = None
    wait_bars: int = 1


def _bars(n_days: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_days * 24, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": c, "high": c * 1.0005, "low": c * 0.9995, "close": c},
                        index=idx)


def _trend_sigs(df: pd.DataFrame) -> list[_Sig]:
    logc = np.log(df["close"].to_numpy())
    out = []
    for i in range(300 * 24, len(df) - 30, 24):
        out.append(_Sig(df.index[i], int(np.sign(logc[i] - logc[i - 20 * 24]) or 1)))
    return out


def test_a_textbook_trend_follower_reads_as_explained() -> None:
    df = _bars()
    y, X = sn.style_matrix(df["close"].to_numpy(), df.index, _trend_sigs(df))
    p = sn.project(y, X)
    assert p["status"] == "MEASURED"
    assert p["style_r2_adj"] > 0.95 and p["novelty_return"] < 0.05
    assert p["dominant_style"] == "trend_20d"


def test_a_side_no_style_knows_reads_as_novel() -> None:
    df = _bars(seed=1)
    rng = np.random.default_rng(9)
    sigs = [_Sig(df.index[i], int(rng.choice([-1, 1])))
            for i in range(300 * 24, len(df) - 30, 24)]
    p = sn.project(*sn.style_matrix(df["close"].to_numpy(), df.index, sigs))
    assert p["status"] == "MEASURED" and p["novelty_return"] > 0.6
    assert p["dominant_style"] is None


def test_styles_are_decided_point_in_time() -> None:
    """The style columns for a signal never read a bar after its window."""
    df = _bars(seed=2)
    sig = _trend_sigs(df)[50]
    i = int(df.index.searchsorted(sig.time))
    _, x_full = sn.style_matrix(df["close"].to_numpy(), df.index, [sig])
    cut = df.iloc[: i + sig.ttl_bars + 1]
    _, x_cut = sn.style_matrix(cut["close"].to_numpy(), cut.index, [sig])
    assert np.allclose(x_full, x_cut)


def test_an_untouched_bracket_side_is_not_a_sample() -> None:
    df = _bars(seed=3)
    t = df.index[400 * 24]
    px = float(df["close"].iloc[400 * 24])
    hit = _Sig(t, 1, trigger=px * 0.5)            # below the next high: touched at once
    miss = _Sig(t, -1, trigger=px * 0.5)          # a short stop far below: never touched
    y, _X = sn.style_matrix(df["close"].to_numpy(), df.index, [hit, miss],
                            high=df["high"].to_numpy(), low=df["low"].to_numpy())
    assert len(y) == 1


def test_a_family_without_certificates_carries_its_genealogy() -> None:
    classes = {"carry": "carry", "pca_residual": "residual"}
    assert sn.family_novelty("carry", {}, classes) == 0.0
    assert sn.family_novelty("pca_residual", {}, classes) == 0.5
    assert sn.family_novelty("never_heard_of_it", {}, classes) == 1.0
    assert sn.family_novelty("carry", {"carry": 0.7}, classes) == 0.7


def test_the_run_writes_the_report_and_the_weekly_snapshot_then_stands_down(tmp_path) -> None:
    df = _bars(seed=4)
    certs = tmp_path / "certs.json"
    certs.write_text(json.dumps({"survivors": {
        "a.EURUSD.trend": {"shadow_spec": {"symbol": "EURUSD", "family": "multi_speed_trend"}},
        "b.EURUSD.nobars": {"shadow_spec": {"symbol": "EURUSD", "family": "discovered"}}}}),
        "utf-8")

    def build(sym, family, params, meta, **_k):
        return None if family == "discovered" else {"df": df, "sigs": _trend_sigs(df)}

    rep, wk = tmp_path / "r.json", tmp_path / "w.json"
    doc = sn.run(certs_path=certs, fallback=tmp_path / "x.json", report_path=rep,
                 weekly_path=wk, universe=tmp_path / "u.json", build=build)
    a = doc["per_certificate"]["a.EURUSD.trend"]
    assert a["status"] == "MEASURED" and a["novelty"] < 0.05 and not a["novel"]
    assert doc["per_certificate"]["b.EURUSD.nobars"]["novelty"] is None
    assert doc["n_measured"] == 1 and doc["n_novel"] == 0
    assert json.loads(wk.read_text("utf-8"))["n_measured"] == 1
    assert sn.family_values(rep) == {"multi_speed_trend": a["novelty"]}
    again = sn.run(certs_path=certs, report_path=rep, weekly_path=wk, build=build,
                   now=time.time() + 60)
    assert again["status"] == "FRESH"


def test_the_docket_fallback_judges_a_novel_family_first_at_equal_spend(monkeypatch) -> None:
    from research import merge_hypotheses as mh
    monkeypatch.setattr(mh, "alpha_rl_family_values", lambda: ({}, "none"))
    monkeypatch.setattr(mh, "residual_family_values", lambda: ({}, "none"))
    monkeypatch.setattr(mh, "novelty_family_values", lambda: ({}, "genealogy only"))
    rows = [{"family": "carry"}] * 4 + [{"family": "zz_unclassified_style"}] * 4
    ordered = mh.breadth_order(rows, {"carry": 8, "zz_unclassified_style": 8})
    assert ordered[0]["family"] == "zz_unclassified_style"
    assert len(ordered) == len(rows)
