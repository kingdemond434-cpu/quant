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
    if kind == 'chart':
        with pytest.raises(RuntimeError, match='writer lane'):
            publish()
    else:
        # The converter DEFERS rather than raising: the bank is untouched and the candidate
        # waits on disk for the next pass instead of being lost.
        assert publish() == (0, -1)
        assert [c['family'] for c in mh.read_deferred('local_converter')] == ['carry']
    assert bank.read_bytes() == b'[]'


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
