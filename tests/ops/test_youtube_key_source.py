"""youtube_miner reads its key through read_key, falling back to data/secrets/youtube.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "side_channels"))

import youtube_miner  # noqa: E402

FAKE = "fake-youtube-token-for-tests"


def test_the_key_comes_from_read_key(monkeypatch) -> None:
    monkeypatch.setattr("libs.ops.env_keys.read_key",
                        lambda name, default="", **_: FAKE if name == "YOUTUBE_API_KEY" else "")
    assert youtube_miner._load_api_key() == FAKE


def test_the_secrets_file_is_the_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("libs.ops.env_keys.read_key", lambda name, default="", **_: "")
    base = tmp_path / "desks" / "mt5"
    base.mkdir(parents=True)
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / "data" / "secrets" / "youtube.json").write_text(json.dumps({"api_key": FAKE}))
    monkeypatch.setattr(youtube_miner, "BASE", base)
    assert youtube_miner._load_api_key() == FAKE


def test_no_key_anywhere_is_empty_not_a_crash(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("libs.ops.env_keys.read_key", lambda name, default="", **_: "")
    base = tmp_path / "desks" / "mt5"
    base.mkdir(parents=True)
    monkeypatch.setattr(youtube_miner, "BASE", base)
    assert youtube_miner._load_api_key() == ""
