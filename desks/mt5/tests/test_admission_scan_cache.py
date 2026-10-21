"""The admission scan does not re-solve a candidate whose inputs have not changed (2026-10-21).

    "Have the admission scan reuse each candidate's last result when its inputs are unchanged:
     same evidence hash, same incumbent book, same bounds. Only re-solve candidates whose inputs
     changed. Unchanged inputs must give bit-identical results. ... Fail closed: any hash miss,
     missing field or cache read error means a full re-solve."            -- the principal

Each test compares the WHOLE scan document with and without the cache, less the wall-clock
fields (how long a solve took is not a result).
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")

_CLOCK = {"measured_utc", "generated_utc", "elapsed_s", "solve_s", "per_candidate_s",
          "max_candidate_s", "cache"}


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in _CLOCK}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _fixture(seed: int = 7, n: int = 400):
    rng = np.random.default_rng(seed)
    core = rng.normal(0.0, 1.0, n)

    def sleeve(name: str, sharpe: float, rho: float) -> SleeveEvidence:
        z = rho * core + np.sqrt(1.0 - rho * rho) * rng.normal(0.0, 1.0, n)
        z = (z - z.mean()) / z.std()
        return SleeveEvidence(name=name, daily_r=z * 0.35 + sharpe / np.sqrt(252.0) * 0.35,
                              family="f", symbol=name.split("_")[0], n_trials=50,
                              forward_days=40, live_days=0, cost_r=0.02)

    held = [sleeve(f"HELD_{i}", 2.0, 0.9) for i in range(3)]
    cands = [sleeve("EURJPY_carry", 1.2, -0.2), sleeve("XAUUSD_trend", 2.5, 0.95),
             sleeve("GBPUSD_mr", 0.8, 0.1)]
    ev = [*held, *cands]
    cfg = WorldConfig(seed=3, n_worlds=64, n_rows=160)
    return ev, sample_worlds(ev, cfg), cfg, {e.name: 0.05 for e in held}


def _scan(ev, worlds, cfg, incumbent, **kw):
    # budget_s=0: no wall-clock deadline, so every solve is a pure function of its inputs.
    return pa.marginal_admission(ev, worlds, cfg, incumbent=incumbent,
                                 bounds={e.name: 0.2 for e in ev}, total_heat=0.2,
                                 budget_s=0, explore_share=0.0, **kw)


def test_unchanged_inputs_give_a_bit_identical_scan_and_skip_every_solve(tmp_path) -> None:
    ev, worlds, cfg, inc = _fixture()
    cache = tmp_path / "admission_cache.json"
    plain = _scan(ev, worlds, cfg, inc)
    first = _scan(ev, worlds, cfg, inc, cache_path=cache)
    second = _scan(ev, worlds, cfg, inc, cache_path=cache)
    assert plain["status"] == "MEASURED" and len(plain["candidates"]) == 3
    assert first["cache"]["hits"] == 0 and first["cache"]["stored"] == 3
    assert second["cache"]["hits"] == 3
    want = json.dumps(_strip(plain), sort_keys=True, default=str)
    assert json.dumps(_strip(first), sort_keys=True, default=str) == want
    assert json.dumps(_strip(second), sort_keys=True, default=str) == want


def test_a_changed_input_re_solves(tmp_path) -> None:
    ev, worlds, cfg, inc = _fixture()
    cache = tmp_path / "admission_cache.json"
    _scan(ev, worlds, cfg, inc, cache_path=cache)
    # A different incumbent book (one held sleeve dropped): every candidate's bounds change.
    # (A re-sized incumbent with the same held set can solve on identical inputs; then a replay
    # is correct, since the key covers every input the re-solve reads.)
    inc2 = {k: v for k, v in inc.items() if k != "HELD_0"}
    out = _scan(ev, worlds, cfg, inc2, cache_path=cache)
    assert out["cache"]["hits"] == 0
    assert json.dumps(_strip(out), sort_keys=True, default=str) == json.dumps(
        _strip(_scan(ev, worlds, cfg, inc2)), sort_keys=True, default=str)
    # Different evidence for one sleeve: a different scan key, so nothing replays.
    _scan(ev, worlds, cfg, inc, cache_path=cache)
    ev2 = list(ev)
    ev2[-1] = dataclasses.replace(ev[-1], cost_r=0.03)
    assert _scan(ev2, worlds, cfg, inc, cache_path=cache)["cache"]["hits"] == 0


@pytest.mark.parametrize("bad", ["{not json", json.dumps({"rows": []}), "MISSING_FIELD"])
def test_an_unreadable_or_incomplete_cache_is_a_full_re_solve(tmp_path, bad) -> None:
    ev, worlds, cfg, inc = _fixture()
    cache = tmp_path / "admission_cache.json"
    plain = _scan(ev, worlds, cfg, inc)
    if bad == "MISSING_FIELD":
        _scan(ev, worlds, cfg, inc, cache_path=cache)
        doc = json.loads(cache.read_text("utf-8"))
        for row in doc["rows"].values():
            row.pop("mean_log_growth")
        cache.write_text(json.dumps(doc), encoding="utf-8")
    else:
        cache.write_text(bad, encoding="utf-8")
    out = _scan(ev, worlds, cfg, inc, cache_path=cache)
    assert out["cache"]["hits"] == 0
    assert json.dumps(_strip(out), sort_keys=True, default=str) == json.dumps(
        _strip(plain), sort_keys=True, default=str)


def test_a_key_that_cannot_be_computed_means_no_cache(tmp_path, monkeypatch) -> None:
    ev, worlds, cfg, inc = _fixture()
    cache = tmp_path / "admission_cache.json"

    def boom(*_a, **_k):
        raise OSError("source unavailable")

    monkeypatch.setattr(pa, "_admission_scan_key", boom)
    out = _scan(ev, worlds, cfg, inc, cache_path=cache)
    assert "cache" not in out and not cache.exists()
    assert json.dumps(_strip(out), sort_keys=True, default=str) == json.dumps(
        _strip(_scan(ev, worlds, cfg, inc)), sort_keys=True, default=str)


def test_a_failed_write_leaves_no_temp_file(tmp_path, monkeypatch) -> None:
    ev, worlds, cfg, inc = _fixture()
    cache = tmp_path / "admission_cache.json"

    def refuse(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(pa.os, "replace", refuse)
    out = _scan(ev, worlds, cfg, inc, cache_path=cache)
    assert "write_error" in out["cache"]
    assert not list(tmp_path.glob(".admission_cache.json.*.tmp")) and not cache.exists()
