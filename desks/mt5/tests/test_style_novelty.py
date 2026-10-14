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
    cut = df.iloc[: i + 1 + sig.ttl_bars + 1]       # through the exit bar's open
    _, x_cut = sn.style_matrix(cut["close"].to_numpy(), cut.index, [sig])
    assert np.allclose(x_full, x_cut)


def test_an_untouched_bracket_side_is_not_a_sample() -> None:
    df = _bars(seed=3)
    t = df.index[400 * 24]
    px = float(df["close"].iloc[400 * 24])
    nxt = float(df["close"].iloc[400 * 24 + 1])
    hit = _Sig(t, 1, trigger=nxt)                 # inside the next bar's range: filled
    miss = _Sig(t, -1, trigger=px * 0.5)          # far below every bar it lives on: never filled
    y, _X = sn.style_matrix(df["close"].to_numpy(), df.index, [hit, miss],
                            high=df["high"].to_numpy(), low=df["low"].to_numpy(),
                            open_=df["open"].to_numpy())
    assert len(y) == 1


def test_a_family_without_certificates_carries_its_genealogy() -> None:
    classes = {"carry": "carry", "pca_residual": "residual"}
    assert sn.family_novelty("carry", {}, classes) == 0.0
    assert sn.family_novelty("pca_residual", {}, classes) == 0.5
    assert sn.family_novelty("never_heard_of_it", {}, classes) == 0.0   # a registry gap: neutral
    assert sn.genealogy("never_heard_of_it", classes) == (0.0, "UNMEASURED")
    assert sn.family_novelty("gnn_propagation", {}, classes) == 1.0      # derived from MINERS
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
    rows = ([{"family": "carry"}] * 4 + [{"family": "zz_unclassified_style"}] * 4
            + [{"family": "gnn_propagation"}] * 4)
    ordered = mh.breadth_order(rows, {"carry": 8, "zz_unclassified_style": 8,
                                      "gnn_propagation": 8})
    assert ordered[0]["family"] == "gnn_propagation"
    assert len(ordered) == len(rows)
    # An unclassified family gets no lift: it ties with the textbook family on spend, so the
    # family name breaks the tie exactly as it did before the tilt.
    assert [r["family"] for r in ordered[4:]] == ["carry"] * 4 + ["zz_unclassified_style"] * 4


def test_a_family_with_certificates_and_nothing_novel_is_saturated() -> None:
    per = {"a": {"family": "carry", "novelty": 0.03, "novel": False, "mechanism_class": "carry",
                 "genealogy": 0.0, "return_projection": {"dominant_style": "passive_window"}},
           "b": {"family": "pca_residual", "novelty": 0.7, "novel": True},
           "c": {"family": "discovered", "novelty": None}}
    fam = sn.per_family(per)
    assert fam["carry"]["saturation"] == "SATURATED"
    assert fam["carry"]["dominant_styles"] == {"passive_window": 1}
    assert fam["pca_residual"]["saturation"] == "OPEN"
    assert fam["discovered"]["saturation"] == "UNMEASURED"


def test_a_partial_run_is_never_fresh_and_the_stalest_certificate_goes_first(tmp_path) -> None:
    certs = tmp_path / "certs.json"
    certs.write_text(json.dumps({"survivors": {
        k: {"shadow_spec": {"symbol": "EURUSD", "family": "carry"}} for k in ("a", "b", "c")}}),
        "utf-8")
    rep, wk = tmp_path / "r.json", tmp_path / "w.json"
    rep.write_text(json.dumps({"generated_utc": "2026-10-13T00:00:00+00:00", "complete": True,
                               "per_certificate": {
                                   "a": {"measured_at": "2026-10-13T00:00:03+00:00"},
                                   "b": {"measured_at": "2026-10-13T00:00:01+00:00"}}}),
                   "utf-8")
    seen: list[str] = []

    def build(sym, family, params, meta, **_k):
        seen.append(params.get("_id", "?"))
        return None

    doc = sn.run(certs_path=certs, fallback=tmp_path / "x.json", report_path=rep,
                 weekly_path=wk, universe=tmp_path / "u.json", build=build, budget_s=0.0,
                 force=True)
    assert doc["complete"] is False and not wk.exists()
    again = sn.run(certs_path=certs, report_path=rep, weekly_path=wk, build=build,
                   budget_s=600.0)
    assert again["status"] != "FRESH" and again["complete"] is True
    order = list(again["per_certificate"])
    assert order[0] == "c" and order.index("b") < order.index("a"), order


def test_a_report_stamped_in_the_future_is_never_fresh(tmp_path) -> None:
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"complete": True, "generated_utc": "2030-01-01T00:00:00+00:00"}),
                   "utf-8")
    certs = tmp_path / "c.json"
    certs.write_text(json.dumps({"survivors": {}}), "utf-8")
    doc = sn.run(certs_path=certs, fallback=tmp_path / "x.json", report_path=rep,
                 weekly_path=tmp_path / "w.json", build=lambda *a, **k: None)
    assert doc["status"] != "FRESH"


def test_overlapping_signals_follow_the_engines_single_position_rule() -> None:
    df = _bars(seed=5)
    t = df.index[400 * 24]
    sigs = [_Sig(t, 1, ttl_bars=24), _Sig(df.index[400 * 24 + 5], 1, ttl_bars=24),
            _Sig(df.index[400 * 24 + 30], 1, ttl_bars=24)]
    y, _X = sn.style_matrix(df["close"].to_numpy(), df.index, sigs)
    assert len(y) == 2                    # the second opens inside the first's window


def test_the_judge_labels_each_familys_novelty_source(monkeypatch) -> None:
    """MEASURED from the report, GENEALOGY from the registry, UNMEASURED for a registry gap."""
    from research import judge_coverage as jc
    monkeypatch.setattr(sn, "family_values", lambda *a, **k: {"multi_speed_trend": 0.1})
    monkeypatch.setattr(jc, "certified_family_shares", lambda: ({}, 0))
    backlog = {"multi_speed_trend": 1, "carry": 1, "zz_unclassified_style": 1}
    rows = {r["family"]: r for r in jc.rank_by_value(
        backlog, [{"family": f, "params": {}} for f in backlog], 100)}
    assert rows["multi_speed_trend"]["novelty_source"] == "MEASURED"
    assert rows["multi_speed_trend"]["novelty_factor"] == 1.1
    assert rows["carry"]["novelty_source"] == "GENEALOGY"
    assert rows["zz_unclassified_style"]["novelty_source"] == "UNMEASURED"
    assert rows["zz_unclassified_style"]["novelty_factor"] == 1.0
