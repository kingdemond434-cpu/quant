"""The real heavy-clock branch must price an empty incumbent, without funding it."""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)]
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


@pytest.mark.parametrize("heavy", [True, False])
def test_cash_incumbent_heavy_scan_refreshes_but_short_clock_carries(tmp_path, heavy):
    # Execute the admission section of run(), not a copied implementation. Other
    # stages of the full allocator pass are unnecessary for this clock contract.
    body = ast.parse(inspect.getsource(pa.run)).body[0].body
    start = next(i for i, n in enumerate(body)
                 if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                 and n.target.id == "admission")
    end = next(i for i, n in enumerate(body[start:], start)
               if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
               and n.targets[0].id == "explore")
    section = ast.Module(body=body[start:end], type_ignores=[])
    old = {"status": "MEASURED", "measured_utc": "2000-01-01T00:00:00+00:00",
           "candidates": {"OLD": {}}, "admitted": [], "unscored": {}, "warm": {}}
    output = tmp_path / "allocation.json"
    output.write_text(json.dumps({"admission": old}), encoding="utf-8")
    # Strong positive and negative controls keep real optimization and costs.
    noise = np.random.default_rng(18).normal(0, .005, 400)
    ev = [SleeveEvidence(name=name, daily_r=noise + mean, family="control",
                         symbol="EURUSD", n_trials=1, forward_days=400,
                         live_days=0, cost_r=.0001)
          for name, mean in (("POSITIVE", .08), ("NEGATIVE", -.08))]
    cfg = WorldConfig(seed=18, n_worlds=48, n_rows=100)
    worlds = sample_worlds(ev, cfg)
    scope = {**vars(pa), "heavy": heavy, "mode": "heavy" if heavy else "normal",
             "OUT": output, "ev": ev, "worlds": worlds, "cfg": cfg, "seed": 18,
             "funded": {}, "book": SimpleNamespace(total_heat=0.), "dd": {},
             "free": SimpleNamespace(marginal={}), "_log": lambda message: None,
             "_psb": lambda dd, heat: {e.name: .10 for e in ev}}
    exec(compile(section, pa.__file__, "exec"), scope)
    admission = scope["admission"]
    assert scope["funded"] == {}  # admission is evidence, never arming or funding
    if heavy:
        assert admission["status"] == "MEASURED"
        assert admission["measured_utc"] != old["measured_utc"]
        assert admission["basis"] == "free" and admission["incumbent"] == {}
        assert "POSITIVE" in admission["admitted"]
        assert "NEGATIVE" in admission["refused"]
        assert "OLD" not in admission["candidates"]
    else:
        assert admission["measured_utc"] == old["measured_utc"]
        assert admission["carried_from"] == old["measured_utc"]
