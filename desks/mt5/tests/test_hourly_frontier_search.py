from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import edge_search
from research.frontier_identity import cell_id, economic_prior
from scripts import external_gauntlet


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


def test_mechanism_prior_is_not_invented_for_price_shape() -> None:
    status, _ = edge_search.mechanism_for_feature("ret_24")
    assert status == "STATISTICAL_ONLY"
    assert not economic_prior({"family": "discovered", "mechanism_status": status})["passed"]

    status, note = edge_search.mechanism_for_feature("ext_triangle_resid_JPY")
    assert status == "NAMED"
    assert economic_prior(
        {"family": "discovered", "mechanism_status": status, "mechanism_note": note}
    )["passed"]


def test_family_free_cells_keep_exact_parameter_identity() -> None:
    a = {"sym": "EURUSD", "family": "discovered", "params": {"feature": "ret_24"}}
    b = {"sym": "EURUSD", "family": "discovered", "params": {"feature": "spread_z_48"}}
    assert cell_id(a) != cell_id(b)
    assert "rr=?" not in cell_id(a)


def test_gauntlet_rebuilds_discovered_external_inputs(monkeypatch, tmp_path) -> None:
    universe = tmp_path / "universe"
    universe.mkdir()
    bars = _bars()
    bars.to_parquet(universe / "EURUSD_H1.parquet")
    bars.to_parquet(universe / "GBPUSD_H1.parquet")
    captured = {}

    from mt5desk import families_orthogonal

    def discovered(df, **params):
        captured.update(params)
        return []

    monkeypatch.setattr(external_gauntlet, "UNI", universe)
    monkeypatch.setitem(families_orthogonal.ORTHOGONAL_FAMILIES, "discovered", discovered)
    marker = pd.Series(1.0, index=bars.index)
    monkeypatch.setattr(edge_search, "resolve_inputs", lambda *_args: {"peer_marker": marker})

    cell = external_gauntlet.build_cell(
        "EURUSD", "discovered", {"feature": "ext_peer_marker", "horizon": 12}, {},
    )

    assert cell is not None
    assert captured["extra"]["peer_marker"].equals(marker)


def test_orthogonal_candidates_persist_runtime_provenance() -> None:
    source = (DESK / "research" / "orthogonal_sweep.py").read_text("utf-8")
    assert '"peer_symbol": peers[0]' in source
    assert '"factor_symbols": peers[:2]' in source
    assert '"input_source": "fusion_tick_tape"' in source
    assert '"input_source": "ff_calendar_vintage"' in source
    assert 'dict((kw and {}) or {})' not in source
