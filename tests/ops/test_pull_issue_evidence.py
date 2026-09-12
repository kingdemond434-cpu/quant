"""Exercise the scheduled pull block with a real copier and a failed/invalid source."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('source_kind', ['valid', 'invalid', 'missing'])
def test_issue_reports_cross_pull_without_restamping_or_losing_valid_copy(tmp_path, source_kind):
    reports = tmp_path / 'desks/mt5/reports'
    reports.mkdir(parents=True)
    source = tmp_path / 'source'
    source.mkdir()
    prior = {'measured_at': '2026-09-11T00:00:00Z', 'issues': [{'key': 'old'}]}
    fresh = {'measured_at': '2026-09-12T00:00:00Z', 'issues': []}
    for name in ('ISSUE_BOARD.json', 'ADVERSARY.json'):
        (reports / name).write_text(json.dumps(prior))
        if source_kind != 'missing':
            (source / name).write_text(json.dumps(fresh) if source_kind == 'valid' else 'broken')
            os.utime(source / name, (1789171200, 1789171200))
    venv = tmp_path / '.venv/bin'
    venv.mkdir(parents=True)
    (venv / 'python').symlink_to(sys.executable)
    script = (ROOT / 'ops/pull_desk_state.sh').read_text()
    block = script.split('# ISSUE_EVIDENCE_PULL_BEGIN\n', 1)[1].split(
        '# ISSUE_EVIDENCE_PULL_END', 1)[0]
    # scp's contract: preserve source mtime and leave failures to the caller.
    harness = '''
scp() {
  local remote="${@: -2:1}" dest="${@: -1}"
  cp -p "source/${remote##*/}" "$dest"
}
REMOTE=test-host
'''
    subprocess.run(['bash', '-u', '-c', harness + block], cwd=tmp_path, check=True)
    for name in ('ISSUE_BOARD.json', 'ADVERSARY.json'):
        expected = fresh if source_kind == 'valid' else prior
        assert json.loads((reports / name).read_text()) == expected
        assert not (reports / (name + '.tmp')).exists()
        if source_kind == 'valid':
            assert (reports / name).stat().st_mtime == (source / name).stat().st_mtime
    assert script.index('# ISSUE_EVIDENCE_PULL_END') < script.index(
        '.venv/bin/python scripts/build_zentech_state.py')
