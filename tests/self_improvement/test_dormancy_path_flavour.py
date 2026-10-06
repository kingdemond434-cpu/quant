"""Reachability must be identical under native Windows and POSIX path spelling."""
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from libs.self_improvement import dormancy as D


@pytest.mark.parametrize('flavour', [PurePosixPath, PureWindowsPath])
def test_external_import_is_detected_with_either_path_flavour(tmp_path, monkeypatch, flavour):
    for rel in ('libs/research/capability.py', 'libs/research/internal.py',
                'scripts/caller.py', 'tests/test_caller.py'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('from libs.research.capability import run\n')
    monkeypatch.setattr(D, '_ROOT', tmp_path)
    monkeypatch.setattr(D, '_CORPUS', {})
    monkeypatch.setattr(D, 'Path', flavour)
    assert D._external_importers('libs/research/capability.py') == ['scripts/caller.py']
