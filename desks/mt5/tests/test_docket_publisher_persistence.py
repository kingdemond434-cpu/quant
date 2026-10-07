"""Actual producer writes preserve the bank on failure and publish stamped cells."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from libs.data.pit import is_stamped  # noqa: E402
from research import local_converter as lc  # noqa: E402
from research import merge_hypotheses as mh  # noqa: E402
from research import session_chart_equivalents as sce  # noqa: E402


@pytest.fixture(autouse=True)
def owned_writer_lane(monkeypatch, tmp_path):
    from research import job_lock

    monkeypatch.setattr(mh, "DEFERRED_DIR", tmp_path / "deferred")
    monkeypatch.setattr(mh, "DEFER_BACKOFF_S", 0.0)

    @contextmanager
    def owned(name, **kwargs):
        assert name == "merge_hypotheses"
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", owned)


def _publish(kind, monkeypatch, tmp_path):
    bank = tmp_path/'bank.json'
    if kind == 'converter':
        monkeypatch.setattr(lc, 'DOCKET', bank)
        return bank, lambda: lc.feed_docket([
            {'symbols': ['EURUSD'], 'family': 'carry', 'source': 'owned fixture'}])
    monkeypatch.setattr(sce, 'DOCKET', bank)
    monkeypatch.setattr(sce, 'OUT', tmp_path/'receipt.json')
    monkeypatch.setattr(sce, 'expand', lambda: {
        'new': [{'symbol': 'EURUSD', 'family': 'carry', 'params': {}}], 'n_new': 1,
        'parents_certified': 1, 'families_with_a_session_parameter': ['carry'],
        'idle_hours_targeted': [], 'by_variant': {}})
    return bank, lambda: sce.main(['--apply'])


@pytest.mark.parametrize('kind', ['converter', 'chart'])
def test_refused_shared_writer_lane_preserves_bank(kind, monkeypatch, tmp_path):
    from research import job_lock

    bank, publish = _publish(kind, monkeypatch, tmp_path)
    bank.write_bytes(b'[]')

    @contextmanager
    def refused(*args, **kwargs):
        yield False

    monkeypatch.setattr(job_lock, 'exclusive_job', refused)
    # Both writers DEFER rather than raising: the bank is untouched and the rows wait on disk
    # for the next pass of ANY docket writer instead of being lost.
    if kind == 'chart':
        assert publish() == 0
        assert [c['family'] for c in mh.read_deferred('session_chart_equivalents')] == ['carry']
    else:
        assert publish() == (0, -1)
        assert [c['family'] for c in mh.read_deferred('local_converter')] == ['carry']
    assert bank.read_bytes() == b'[]'


def test_any_writer_holding_the_lane_drains_every_other_writers_deferral(monkeypatch, tmp_path):
    """local_converter runs only from intel_ship_adopt.ps1; its deferral must not wait for it."""
    from research import breadth_sweep, job_lock

    bank, _ = _publish('converter', monkeypatch, tmp_path)
    monkeypatch.setattr(sce, 'DOCKET', bank)
    monkeypatch.setattr(breadth_sweep, 'DOCKET', bank)
    bank.write_text('[]', encoding='utf-8')

    @contextmanager
    def refused(*args, **kwargs):
        yield False

    monkeypatch.setattr(job_lock, 'exclusive_job', refused)
    assert lc.feed_docket([{'symbols': ['GBPUSD'], 'family': 'carry'}]) == (0, -1)
    assert sce._merge_locked is not None
    mh._write_deferred('session_chart_equivalents',
                       [{'symbol': 'AUDUSD', 'family': 'carry', 'params': {'session': 'asia'}}])

    @contextmanager
    def owned(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, 'exclusive_job', owned)
    assert breadth_sweep.apply([{'symbol': 'EURUSD', 'family': 'carry', 'params': {}}]) == (1, 1)
    syms = sorted(r['symbol'] for r in json.loads(bank.read_text()))
    assert syms == ['AUDUSD', 'EURUSD', 'GBPUSD']
    drained = mh.LAST_MERGE['breadth_sweep']['drained_for_others']
    assert drained['local_converter']['drained'] == 1
    assert drained['session_chart_equivalents']['drained'] == 1
    assert not mh.deferred_path('local_converter').exists()
    assert not mh.deferred_path('session_chart_equivalents').exists()


def test_a_drain_that_fails_keeps_the_other_writers_rows(monkeypatch, tmp_path):
    from research import job_lock

    bank, _ = _publish('converter', monkeypatch, tmp_path)
    bank.write_text('[]', encoding='utf-8')
    mh._write_deferred('session_chart_equivalents', [{'symbol': 'AUDUSD', 'family': 'carry'}])
    monkeypatch.setattr(sce, 'DOCKET', tmp_path / 'unreadable.json')
    (tmp_path / 'unreadable.json').write_text('[broken', encoding='utf-8')

    @contextmanager
    def owned(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, 'exclusive_job', owned)
    lc.feed_docket([{'symbols': ['EURUSD'], 'family': 'carry'}])
    assert 'why' in mh.LAST_MERGE['local_converter']['drained_for_others'][
        'session_chart_equivalents']
    assert mh.read_deferred('session_chart_equivalents') == [
        {'symbol': 'AUDUSD', 'family': 'carry'}]


def test_quarantine_receipts_and_deferrals_are_box_state():
    from libs.ops.release import is_state_path

    for rel in ('desks/mt5/data/quarantine/discoveries.jsonl',
                'desks/mt5/data/quarantine/write_receipts.jsonl',
                'desks/mt5/data/deferred/docket_merge_breadth_sweep.jsonl'):
        assert is_state_path(rel), rel


def test_converter_deferral_is_merged_first_on_the_next_pass(monkeypatch, tmp_path):
    from research import job_lock

    bank, _ = _publish('converter', monkeypatch, tmp_path)
    bank.write_text('[]', encoding='utf-8')

    @contextmanager
    def refused(*args, **kwargs):
        yield False

    monkeypatch.setattr(job_lock, 'exclusive_job', refused)
    held = {'symbols': ['GBPUSD'], 'family': 'carry', 'converted_at': 't0'}
    assert lc.feed_docket([held]) == (0, -1)
    # The same candidate minted again next hour with a new timestamp is ONE deferred cell.
    assert lc.feed_docket([{**held, 'converted_at': 't1'}]) == (0, -1)
    assert len(mh.read_deferred('local_converter')) == 1

    @contextmanager
    def owned(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, 'exclusive_job', owned)
    added, total = lc.feed_docket([{'symbols': ['EURUSD'], 'family': 'carry'}])
    assert (added, total) == (2, 2)
    assert {r['symbol'] for r in json.loads(bank.read_text())} == {'GBPUSD', 'EURUSD'}
    assert mh.read_deferred('local_converter') == []


def test_chart_rechecks_identity_under_the_shared_writer_lane(monkeypatch, tmp_path):
    bank, publish = _publish('chart', monkeypatch, tmp_path)
    original = {'sym': 'EURUSD', 'family': 'carry', 'params': {}, 'preserved': True}
    bank.write_text(json.dumps([original]))
    assert publish() == 0
    assert json.loads(bank.read_text()) == [original]


@pytest.mark.parametrize('kind', ['converter', 'chart'])
def test_corrupt_docket_is_not_replaced_by_new_rows(kind, monkeypatch, tmp_path):
    bank, publish = _publish(kind, monkeypatch, tmp_path)
    previous = b'[broken'
    bank.write_bytes(previous)
    with pytest.raises(json.JSONDecodeError):
        publish()
    assert bank.read_bytes() == previous


@pytest.mark.parametrize('kind', ['converter', 'chart'])
def test_failed_replacement_keeps_bank_and_cleans_pending_file(kind, monkeypatch, tmp_path):
    bank, publish = _publish(kind, monkeypatch, tmp_path)
    previous = b'[]'
    bank.write_bytes(previous)
    replace = mh.os.replace

    def interrupted(source, target):
        if Path(target) == bank:
            raise OSError('owned replacement interrupted')
        return replace(source, target)

    monkeypatch.setattr(mh.os, 'replace', interrupted)
    with pytest.raises(OSError, match='replacement interrupted'):
        publish()
    assert bank.read_bytes() == previous
    assert not list(tmp_path.glob('.bank.json.*.tmp'))


@pytest.mark.parametrize('kind', ['converter', 'chart'])
def test_actual_writer_publishes_stamped_rows(kind, monkeypatch, tmp_path):
    bank, publish = _publish(kind, monkeypatch, tmp_path)
    bank.write_text('[]', encoding='utf-8')
    publish()
    rows = json.loads(bank.read_text())
    assert len(rows) == 1 and is_stamped(rows[0])
    assert rows[0]['symbol'] == 'EURUSD' and rows[0]['family'] == 'carry'


def test_chart_writer_preserves_legacy_envelope(monkeypatch, tmp_path):
    bank, publish = _publish('chart', monkeypatch, tmp_path)
    bank.write_text('{"survivors": [], "receipt": "preserved"}', encoding='utf-8')
    publish()
    doc = json.loads(bank.read_text())
    assert doc['receipt'] == 'preserved'
    assert len(doc['survivors']) == 1 and is_stamped(doc['survivors'][0])


def test_converter_deduplicates_alias_and_same_pass_candidates(monkeypatch, tmp_path):
    bank, _ = _publish('converter', monkeypatch, tmp_path)
    bank.write_text('[{"sym": "EURUSD", "family": "carry", "params": {}}]', encoding='utf-8')
    candidates = [{'symbols': ['EURUSD'], 'family': 'carry'},
                  {'symbols': ['GBPUSD'], 'family': 'carry'},
                  {'symbols': ['GBPUSD'], 'family': 'carry'}]
    added, total = lc.feed_docket(candidates)
    assert (added, total) == (1, 2)


def test_a_deferral_is_claimed_by_rename_so_two_drainers_cannot_double_merge(tmp_path):
    """Audit of #222: two drainers reading the same waiting file would both merge it."""
    mh._write_deferred('local_converter', [{'symbol': 'GBPUSD', 'family': 'carry'}])
    first, claims = mh._claim('local_converter')
    second, none = mh._claim('local_converter')     # the file is already renamed away
    assert [r for r, _ in first] == [{'symbol': 'GBPUSD', 'family': 'carry'}]
    assert second == [] and none == []
    assert not mh.deferred_path('local_converter').exists()
    # A failed merge hands the rows back, with their original deferral time.
    stamp = first[0][1]
    mh._unclaim('local_converter', first, claims)
    assert mh.read_deferred('local_converter') == [{'symbol': 'GBPUSD', 'family': 'carry'}]
    assert mh._parse_lines(mh.deferred_path('local_converter'))[0][1] == stamp
    assert not mh._claims('local_converter')


def test_an_orphaned_claim_is_taken_back_once_stale(tmp_path):
    import os

    mh._write_deferred('breadth_sweep', [{'symbol': 'EURUSD', 'family': 'carry'}])
    _rows, claims = mh._claim('breadth_sweep')         # this "pass" dies holding the claim
    assert mh._claim('breadth_sweep') == ([], [])      # fresh claim: someone holds it
    old = claims[0].stat().st_mtime - mh.CLAIM_STALE_S - 5
    os.utime(claims[0], (old, old))
    rows, again = mh._claim('breadth_sweep')
    assert [r for r, _ in rows] == [{'symbol': 'EURUSD', 'family': 'carry'}] and again


def test_deferral_depth_and_oldest_age_are_published_per_writer(tmp_path):
    from datetime import UTC, datetime, timedelta

    mh._write_deferred('local_converter', [{'symbol': 'GBPUSD'}, {'symbol': 'EURUSD'}])
    later = datetime.now(tz=UTC) + timedelta(hours=2)
    got = mh.deferral_status(later)
    assert got['local_converter']['depth'] == 2
    assert got['local_converter']['oldest_age_s'] >= 7190
    assert got['breadth_sweep'] == {'depth': 0, 'files': 0, 'oldest_age_s': None,
                                    'unaged_rows': 0}


def test_a_claim_file_is_deleted_only_after_its_rows_land(tmp_path):
    """merge_hypotheses._drop is a declared POSITIVE destructive path: the claim file survives
    until the locked merge returns, and a failed merge puts its rows back before the claim goes."""
    writer = 'local_converter'
    row = {'symbol': 'GBPUSD', 'family': 'carry'}
    ident = (lambda r: f"{r['symbol']}:{r['family']}")
    seen: list[bool] = []

    def failing(rows):
        seen.append(bool(mh._claims(writer)))           # the claim is still on disk mid-merge
        raise RuntimeError('docket unreadable')

    mh._write_deferred(writer, [row])
    with pytest.raises(RuntimeError):
        mh.merge_or_defer(writer, [], failing, ident)
    assert seen == [True]
    assert mh.read_deferred(writer) == [row] and not mh._claims(writer)    # restored, not lost

    landed: list[dict] = []

    def ok(rows):
        assert mh._claims(writer)                       # not dropped before the rows land
        landed.extend(rows)
        return len(rows), len(rows)

    assert mh.merge_or_defer(writer, [], ok, ident) == (1, 1)
    assert landed == [row]
    assert not mh._claims(writer) and mh.read_deferred(writer) == []


def test_the_claim_drop_is_declared_to_the_destructive_path_fence():
    from libs.ops import reference_freshness as rf

    spec = rf.by_id('merge_hypotheses.drop_claims')
    assert spec is not None and spec.status == 'positive'
    assert (spec.module, spec.function) == ('desks/mt5/research/merge_hypotheses.py', '_drop')
