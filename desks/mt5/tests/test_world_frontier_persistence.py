"""Copied read-only state must not waste crawls or erase the durable search frontier."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_DESK / "side_channels"))
import world_frontier as wf  # noqa: E402


@pytest.fixture
def frontier(tmp_path, monkeypatch):
    monkeypatch.setattr(wf, "WORLD", tmp_path)
    monkeypatch.setattr(wf, "FRONTIER", tmp_path / "frontier.json")
    return wf.FRONTIER


def test_read_only_snapshot_can_advance_without_losing_history(frontier):
    source = wf.Source("https://example.test/strategy", fetches=8, failures=2,
                       first_seen="2026-09-01T00:00:00+00:00", last_hash="original")
    wf.save({source.url: source})
    frontier.chmod(0o444)
    if os.name == "posix" and os.geteuid() != 0:
        with pytest.raises(PermissionError):
            with frontier.open("a"):
                pass
    sources = wf.load()
    sources[source.url].fetches += 1
    sources[source.url].last_fetched = "2026-09-12T23:00:00+00:00"
    wf.save(sources, note="new crawl")
    recovered = wf.load()[source.url]
    assert recovered.fetches == 9
    assert recovered.failures == 2
    assert recovered.first_seen == source.first_seen
    assert recovered.last_hash == "original"
    assert json.loads(frontier.read_text())["note"] == "new crawl"
    assert list(frontier.parent.iterdir()) == [frontier]


@pytest.mark.parametrize("failure", ["serialize", "replace"])
def test_failed_publication_preserves_previous_bytes(frontier, monkeypatch, failure):
    source = wf.Source("https://example.test/strategy", fetches=8)
    wf.save({source.url: source})
    original = frontier.read_bytes()

    def fail(*args, **kwargs):
        if failure == "serialize":
            args[1].write('{"partial":')
        raise OSError("injected publication failure")

    if failure == "serialize":
        monkeypatch.setattr(wf.json, "dump", fail)
    else:
        monkeypatch.setattr(wf.os, "replace", fail)
    source.fetches += 1
    with pytest.raises(OSError, match="injected"):
        wf.save({source.url: source})
    assert frontier.read_bytes() == original
    assert list(frontier.parent.iterdir()) == [frontier]


@pytest.mark.parametrize("content", ['{"sources":', '[]', '{}', '{"sources": []}'])
def test_corrupt_frontier_is_never_silently_reseeded(frontier, content):
    frontier.write_text(content)
    with pytest.raises(ValueError):
        wf.load()
    assert frontier.read_text() == content


def test_missing_frontier_can_bootstrap(frontier):
    assert wf.load() == {}
