"""An unreadable lifetime ledger cannot silently shrink the allocator's trial count."""

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parent.parent / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import pf_allocator as pa  # noqa: E402

from libs.research import experiment_ledger as el  # noqa: E402


def test_search_trials_fails_closed_when_lifetime_is_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "BASE", tmp_path)

    def broken_lifetime(*, write=False):
        raise ValueError("malformed graph row")

    monkeypatch.setattr(el, "lifetime", broken_lifetime)
    with pytest.raises(RuntimeError, match="lifetime trial count unavailable"):
        pa.search_trials()
