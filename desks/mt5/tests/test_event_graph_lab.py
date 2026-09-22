"""The event-graph lab: a planted overnight-gap mechanism is SUPPORTED on synthetic bars, a
family with no template is UNMEASURED by name, the pass builds the graph from rows handed in,
donates compiler-shaped seeds, records nothing under --dry-run, and writes its artifact
otherwise."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import event_graph_lab as lab  # noqa: E402

from libs.research import causal_adjudicator as ca  # noqa: E402
from libs.research import event_graph as eg  # noqa: E402

N_DAYS = 400


def _gap_bars(seed: int = 3, fade: float = 0.0009) -> pd.DataFrame:
    """Hourly bars whose first bar of each day gaps by ~1.5 ATR and then decays back over the
    next eight bars: exactly the overnight_gap_decay mechanism, and nothing else."""
    rng = np.random.default_rng(seed)
    n = N_DAYS * 24
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC", name="time")
    step = rng.normal(0.0, 0.0002, n)
    hours = np.asarray(idx.hour)
    gap_sign = np.where(rng.random(N_DAYS) < 0.5, 1.0, -1.0)
    day_no = np.arange(n) // 24
    step[hours == 0] += 0.0025 * gap_sign
    fade_mask = (hours >= 1) & (hours <= 8)
    step[fade_mask] -= fade * gap_sign[day_no[fade_mask]]
    close = 100.0 * np.exp(np.cumsum(step))
    open_ = np.concatenate([[100.0], close[:-1]])
    open_[hours == 0] = close[np.maximum(np.nonzero(hours == 0)[0] - 1, 0)] * np.exp(
        0.002 * gap_sign)
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0002,
                         "low": np.minimum(open_, close) * 0.9998, "close": close},
                        index=idx)


def _loader(frame: pd.DataFrame):
    return lambda symbol, timeframe: frame


def test_a_planted_gap_fade_mechanism_is_supported_and_an_unknown_family_is_unmeasured() -> None:
    frame = _gap_bars()
    row = lab.adjudicate_mechanism("planted", "overnight_gap_decay", "TESTFX", "H1", {},
                                   falsifier="the gap stops decaying", competing=["momentum"],
                                   bars_loader=_loader(frame))
    assert row["verdict"] == ca.SUPPORTED, row
    assert row["effect"] < 0 and row["eligible"]
    none = lab.adjudicate_mechanism("carry", "carry", "TESTFX", "H1", {},
                                    bars_loader=_loader(frame))
    assert none["verdict"] == lab.UNMEASURED and none["failing_test"] == "template"
    absent = lab.adjudicate_mechanism("x", "dow_effect", "TESTFX", "H1", {},
                                      bars_loader=lambda s, t: None)
    assert absent["verdict"] == lab.UNMEASURED and absent["failing_test"] == "data"


def _seed_rows() -> list[dict[str, Any]]:
    return [{"from_country": "cn", "actor": "Chinese industrial buyers", "flow": "metal imports",
             "to_country": "au", "asset": "AUDUSD", "target": "sym:AUDUSD",
             "source": "sym:XCUUSD", "lag_days": 1.0, "measured": False, "strength": None,
             "evidence": {"why": "planted"}, "origin": "declared_channel:test"}]


def _series(selector: str):
    """Daily series with a planted one-day lead from XCUUSD into AUDUSD."""
    rng = np.random.default_rng(11)
    days = np.arange("2023-01-01", "2025-06-01", dtype="datetime64[D]")
    x = rng.normal(size=len(days))
    y = np.zeros(len(days))
    y[1:] = 0.4 * x[:-1] + rng.normal(size=len(days) - 1)
    return {"sym:XCUUSD": (days, x), "sym:AUDUSD": (days, y)}.get(selector)


def test_the_pass_measures_a_planted_edge_donates_seeds_and_dry_run_writes_nothing(
        tmp_path: Path) -> None:
    frame = _gap_bars()
    universe = {"AUDUSD": "Forex", "XCUUSD": "Commodities", "TESTFX": "Forex"}
    kw: dict[str, Any] = dict(
        universe=universe, seed_rows=_seed_rows(), causal_rows=[], event_rows=[],
        candidate_rows=[{"id": "cand-1", "status": "queued", "symbol": "TESTFX",
                         "family": "overnight_gap_decay", "params_json": "{}",
                         "falsifier": "the gap stops decaying",
                         "causal_rationale": "thin overnight books | momentum"}],
        sleeve_rows=[{"name": "s1", "status": "LIVE", "family": "carry", "symbol": "TESTFX"}],
        bars_loader=_loader(frame), series_loader=_series,
        store=tmp_path / "graph.json", cursor_path=tmp_path / "cursor.json",
        report=tmp_path / "EVENT_GRAPH.json", intel_dir=tmp_path / "intel")
    dry = lab.build(budget_s=120, dry_run=True, **kw)
    assert not list(tmp_path.iterdir())                       # nothing written anywhere
    assert dry["measured_edges"]["supported"] == 1
    assert dry["adjudications"]["counts"][ca.SUPPORTED] == 1
    assert dry["adjudications"]["counts"][lab.UNMEASURED] == 1   # carry: no template, by name
    assert dry["hypotheses"]["file"] is None and dry["adjudications"]["recorded"] == {
        "candidates": 0, "sleeves": 0, "graph": 0}

    wet = lab.build(budget_s=120, dry_run=False, conn=None, **kw)
    assert (tmp_path / "EVENT_GRAPH.json").exists() and (tmp_path / "graph.json").exists()
    files = list((tmp_path / "intel").glob("discoveries_*.json"))
    assert len(files) == 1 and wet["hypotheses"]["donated"] > 0
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    row = doc["discoveries"][0]
    assert row["kind"] == "hypothesis" and row["family"] in ("relative_value",
                                                             "correlation_regime")
    assert row["symbols"] == [row["symbol"]] and row["falsifier"] and row["competing"]
    assert isinstance(row["params"], dict) and row["params"]
    stored = eg.EventGraph.from_doc(json.loads((tmp_path / "graph.json").read_text("utf-8")))
    measured = [e for e in stored.edges.values() if e.evidence == eg.DESK_MEASURED]
    assert any(e.src == "asset:xcuusd" and e.dst == "asset:audusd" for e in measured)
    again = lab.build(budget_s=120, dry_run=True, **kw)
    assert again["community_change"]["status"] == "MEASURED"


def test_the_leg_is_wired_into_the_hourly_cycle() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    assert hc.department_of("event_graph_lab") == "macro"
    assert hc.LEG_BUDGET_SEC["event_graph_lab"] > 900
    assert layers.LEG_LAYER["event_graph_lab"] == "information"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("event_graph_lab"' in src and '"--budget-s", "900"' in src
