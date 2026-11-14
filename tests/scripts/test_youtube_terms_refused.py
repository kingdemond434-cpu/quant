"""YouTube is refused at the corpus collector and the shared transcript fetcher.

governance/wayback-youtube-ruling-2026-11-14.md: no YouTube API key, the box never contacts
YouTube, and a keyless mirror is a banned route around YouTube's terms. Both scripts must
refuse before any socket opens and record the refusal with its missed_growth line.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"{name}_ut", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("a refused YouTube route opened a socket")

    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket.socket, "connect", _boom)


def test_the_corpus_collector_refuses_with_a_key_present(tmp_path, monkeypatch,
                                                         no_socket) -> None:
    mod = _load("collect_youtube_corpus", monkeypatch)
    key = tmp_path / "key"
    key.write_text("not-a-real-key", "utf-8")
    monkeypatch.setattr(mod, "KEYFILE", key)
    monkeypatch.setattr(mod, "COVERAGE", tmp_path / "cov.json")
    monkeypatch.setattr(mod, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(mod, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(sys, "argv", ["x"])
    assert mod.main() == 0
    cov = json.loads((tmp_path / "cov.json").read_text("utf-8"))
    assert cov["status"] == "BLOCKED_ON_TERMS" and cov["requests_sent"] == 0
    assert "terms-refused" in cov["terms"] and "missed_growth" in cov["missed_growth"]
    assert not (tmp_path / "out").exists()
    with pytest.raises(PermissionError, match="terms-refused"):
        mod.api("channels", [0], 1, part="id")


def test_the_transcript_fetcher_refuses_youtube_and_keeps_no_mirror(monkeypatch,
                                                                    no_socket) -> None:
    mod = _load("fetch_video_transcript", monkeypatch)
    with pytest.raises(mod.TranscriptUnavailable) as exc:
        mod.youtube("https://www.youtube.com/watch?v=abcdefghijk")
    msg = str(exc.value)
    assert "terms-refused" in msg and "missed_growth" in msg
    src = (SCRIPTS / "fetch_video_transcript.py").read_text("utf-8").lower()
    assert "pipedapi" not in src and "invidious.io" not in src
