from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from side_channels import discovery_io as io  # noqa: E402

from libs.data.pit import is_stamped, payload_hash  # noqa: E402


def test_discovery_archive_and_returned_intake_have_the_same_provenance(tmp_path: Path) -> None:
    path = tmp_path / "source" / "discoveries_today.json"
    raw = [{"title": "captured recipe", "captured_at": "2026-10-03T08:00:00+00:00"}]
    emitted = io.write_discoveries(path, raw)
    assert json.loads(path.read_text("utf-8")) == emitted
    assert is_stamped(emitted[0])
    assert emitted[0]["payload_hash"] == payload_hash(emitted[0])
    assert emitted[0]["available_time"] == raw[0]["captured_at"]
    assert "payload_hash" not in raw[0]


def test_refused_batch_cannot_erase_prior_discoveries(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "discoveries_today.json"
    path.write_text('[{"title":"previous"}]', encoding="utf-8")
    monkeypatch.setattr(io, "stamp_or_refuse", lambda *_: ([], [{"why": "no provenance"}]))
    with pytest.raises(ValueError, match="refused"):
        io.write_discoveries(path, [{"title": "new"}])
    assert json.loads(path.read_text("utf-8")) == [{"title": "previous"}]


def test_interrupted_replace_preserves_existing_archive(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "discoveries_today.json"
    path.write_text('[{"title":"previous"}]', encoding="utf-8")

    def fail(*_):
        raise OSError("disk failure")

    monkeypatch.setattr(io.os, "replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        io.write_discoveries(path, [{"title": "new"}])
    assert json.loads(path.read_text("utf-8")) == [{"title": "previous"}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_converter_archive_and_latest_are_identically_stamped(tmp_path, monkeypatch):
    from side_channels import convert_to_hypotheses as converter

    raw = [{"symbol": "USDJPY", "family": "carry", "params": {}, "source": "fixture"}]
    monkeypatch.setattr(converter, "OUT", tmp_path)
    monkeypatch.setattr(converter, "convert_discoveries", lambda: raw)
    converter.save_hypotheses()
    latest = json.loads((tmp_path / "latest_external.json").read_text("utf-8"))
    archive = next(tmp_path.glob("external_*.json"))
    assert latest == json.loads(archive.read_text("utf-8"))
    assert is_stamped(latest[0])
    assert latest[0]["payload_hash"] == payload_hash(latest[0])
    assert "payload_hash" not in raw[0]


def test_bridge_grid_preserves_executable_identity_and_adds_provenance(tmp_path, monkeypatch):
    from side_channels import bridge_to_hunt as bridge

    monkeypatch.setattr(bridge, "HYPO", tmp_path)
    raw = [{"symbol": "USDJPY", "family": "carry", "params": {"x": 1}}]
    saved = json.loads(bridge.save_grid(raw).read_text("utf-8"))
    assert {k: saved[0][k] for k in raw[0]} == raw[0]
    assert is_stamped(saved[0])
    assert saved[0]["payload_hash"] == payload_hash(saved[0])
