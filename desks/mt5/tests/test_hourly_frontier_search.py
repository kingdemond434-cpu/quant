from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research import edge_search


def _bars(n: int = 720) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    walk = 100.0 * np.exp(np.cumsum(np.sin(np.arange(n) / 17.0) * 0.001 + 0.0001))
    return pd.DataFrame(
        {
            "open": walk * 0.9998,
            "high": walk * 1.001,
            "low": walk * 0.999,
            "close": walk,
            "tick_volume": 100 + np.arange(n) % 37,
            "spread": 2 + np.arange(n) % 5,
        },
        index=idx,
    )


def test_primitives_include_distant_domain_and_execution_axes(monkeypatch) -> None:
    monkeypatch.setattr(edge_search, "_interaction_pool_size", lambda _n, _k: 2)
    primitives = edge_search.build_primitives(_bars(), "EURUSD")

    assert "sign_entropy_24" in primitives
    assert "path_efficiency_48" in primitives
    assert "serial_corr_96" in primitives
    assert "spread_z_48" in primitives
    assert "tick_volume_z_12" in primitives


def test_resolver_uses_every_peer_and_builds_registry_triangle(monkeypatch) -> None:
    idx = pd.date_range("2025-01-01", periods=720, freq="h", tz="UTC")
    base = pd.Series(np.exp(np.arange(len(idx)) * 0.0001), index=idx)
    series = {
        "EURUSD": base * 1.1,
        "EURJPY": base * 160.0,
        "USDJPY": pd.Series(np.full(len(idx), 145.0), index=idx),
        "GBPUSD": base * 1.25,
        "AUDUSD": base * 0.65,
        "NZDUSD": base * 0.60,
        "USDCAD": 1.35 / base,
    }
    monkeypatch.setattr(edge_search, "_close", lambda symbol: series.get(symbol))
    monkeypatch.setattr(edge_search, "BASE", Path("Z:/definitely/missing"))

    out = edge_search.resolve_inputs("EURUSD", idx, list(series))

    # The fifth and sixth peers used to be silently excluded by [:4].
    assert "lead_NZDUSD_24" in out
    assert "lead_USDCAD_1" in out
    assert "triangle_resid_JPY" in out
    assert "xsection_dispersion" in out
    assert "xsection_breadth" in out


def test_hourly_pipeline_runs_both_frontiers_on_desk_box() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "ops" / "run_external_pipeline.sh").read_text("utf-8")

    remote = "research\\edge_search.py && py -3 -W ignore research\\orthogonal_sweep.py"
    assert remote in script
    assert "desks/mt5/research/edge_search.py ||" not in script
    assert "orthogonal_candidates.json" in script
    assert "merge_hypotheses.py" in script
