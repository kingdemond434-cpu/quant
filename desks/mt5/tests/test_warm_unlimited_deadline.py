"""Unlimited scheduling must let cold backlog reach the builder; finite limits still bind."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / 'scripts', DESK / 'research'):
    sys.path.insert(0, str(path))
import warm_gauntlet_cache as W  # noqa: E402
import judge_docket_order as O  # noqa: E402
import judging_burndown as JB  # noqa: E402
from research import job_lock  # noqa: E402


@pytest.mark.parametrize('limit,expected_sent', [(0, 2), (8641, 0)])
def test_actual_round_submits_cold_backlog_under_the_measured_deadline(
        tmp_path, monkeypatch, limit, expected_sent):
    report = tmp_path / 'throughput.json'
    report.write_text(json.dumps({'decision': {
        'task_time_limit_s': limit, 'fresh_budget_s': 8640}}))
    monkeypatch.setattr(W, 'JUDGING_THROUGHPUT', report)
    monkeypatch.setattr(W, 'DEFERRALS', tmp_path / 'deferrals.json')
    monkeypatch.setattr(JB, 'sweep_anatomy', lambda: {
        'status': 'MEASURED', 'post_build_s_per_cell': 1.0})
    specs = [{'sym': 'USDJPY', 'tf': 'H1', 'family': 'carry', 'params': {},
              'ckey': key, '_never_judged': key != 'old'} for key in ('old', 'a', 'b')]
    monkeypatch.setattr(W, 'docket_specs', lambda *a: specs)
    monkeypatch.setattr(O, 'sealed_keep', lambda *a: (specs, {
        'keep': 3, 'keep_never_judged': 2, 'outside_keep': 0}))
    monkeypatch.setattr(W, 'resolve_keys', lambda *a: (specs, {}, 0))
    monkeypatch.setattr(W, 'on_disk_keys', lambda *a: {'old'})
    monkeypatch.setattr(W, 'split_deferred', lambda cold, *a: (cold, [], {}))
    monkeypatch.setattr(W, 'plan_equivalents', lambda g, keyed, warm, order, held:
                        (order, {}, 0))
    monkeypatch.setattr(W, 'measure_capacity', lambda: {
        'pool': 2, 'inflight': 1, 'cores': 18, 'idle_cores': 5, 'free_mb': 60000})
    monkeypatch.setattr(job_lock, 'free_mb', lambda: 60000)
    submitted = []

    class OwnedPool:
        def __init__(self, **kwargs):
            assert kwargs['max_workers'] == 2
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def submit(self, builder, batch):
            assert builder is W._warm_batch
            submitted.extend(row['ckey'] for row in batch)
            future = Future()
            future.set_result([(row['ckey'], 'warmed') for row in batch])
            return future

    import concurrent.futures
    monkeypatch.setattr(concurrent.futures, 'ProcessPoolExecutor', OwnedPool)
    result = W.run_round(SimpleNamespace(CACHE_DIR=tmp_path), {}, None, time.time() + 60)
    assert result['sent'] == expected_sent
    assert len(submitted) == expected_sent
    assert result['never_judged_warmed'] == expected_sent
    assert result['held_for_gate_room'] == 2 - expected_sent
    assert result['cold'] == 2
    assert result['warm_before'] == 1
