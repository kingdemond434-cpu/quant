import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from libs.ops.live_ledger_view import LedgerViewError, ledger_path, record_digest
from mt5desk.decision_core import ledger_rows
from mt5desk.markout import load_jsonl


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'live_ledger.jsonl'
        self.raw = {'deal': 123, 'profit': 10, 'sleeve': 'old', 'time': 'old'}
        self.revised = dict(self.raw, sleeve='audited', time='corrected')
        self.body = json.dumps(self.raw) + '\n'
        self.path.write_text(self.body, encoding='utf-8')
        self.events = [{'schema_version': 1, 'raw_prefix_records': 1,
                        'raw_prefix_sha256': hashlib.sha256(self.body.encode()).hexdigest(),
                        'projection_order': [123]},
                       {'deal': 123, 'before_sha256': record_digest(self.raw),
                        'after_sha256': record_digest(self.revised),
                        'set': {'sleeve': 'audited', 'time': 'corrected'}}]
        self.save()

    def save(self):
        self.path.with_name('live_ledger_corrections.jsonl').write_text(
            ''.join(json.dumps(event)+'\n' for event in self.events), encoding='utf-8')

    def test_both_consumers_project_without_raw_mutation(self):
        self.assertEqual(ledger_rows(self.path), [self.revised])
        self.assertEqual(load_jsonl(self.path), [self.revised])
        self.assertEqual(self.path.read_text(encoding='utf-8'), self.body)

    def test_future_broker_append_remains_visible(self):
        row = {'deal': 456, 'profit': -2}
        with ledger_path(self.path).open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row)+'\n')
        self.assertEqual(ledger_rows(self.path), [self.revised, row])

    def test_corrupt_raw_fails_closed(self):
        self.path.write_text(self.body.replace('10', '11'), encoding='utf-8')
        with self.assertRaises(LedgerViewError):
            ledger_rows(self.path)

    def test_financial_correction_rejected(self):
        self.events[1]['set']['profit'] = 99
        self.save()
        with self.assertRaises(LedgerViewError):
            load_jsonl(self.path)

    def test_raw_rewrite_refused(self):
        with self.assertRaises(LedgerViewError):
            ledger_path(self.path).open('w')

    def test_missing_required_correction_fails(self):
        self.path.with_name('live_ledger_corrections.jsonl').unlink()
        self.path.with_name('IMMUTABLE_MANIFEST.json').write_text(json.dumps(
            {'append_only': {'desks/mt5/data/live_ledger_corrections.jsonl': {}}}))
        with self.assertRaises(LedgerViewError):
            ledger_rows(self.path)


if __name__ == '__main__':
    unittest.main()
