"""The PC caption miner's own state can never kill it, and its order spends the hour well.

Offline: every network call (discovery, tab listing, caption and description fetch) is replaced,
so these run anywhere and prove only the miner's bookkeeping.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mine_channel_transcripts.py"


def _load(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("mine_channel_transcripts_ut", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setitem(sys.modules, "youtube_transcript_api",
                        types.SimpleNamespace(YouTubeTranscriptApi=lambda: object()))
    monkeypatch.setattr(mod.shutil, "make_archive", lambda *a, **k: None)
    monkeypatch.setattr(mod, "fetch_description", lambda vid: ("", [], {}))
    return mod


def _seed(tmp: Path) -> tuple[Path, Path, list[dict]]:
    out = tmp / "out"
    out.mkdir()
    rows = [{"video_id": f"v{i:010d}", "title": "t", "tab": "videos", "channel": ch,
             "status": "PENDING"}
            for i, ch in enumerate(["BIG"] * 5 + ["@A"] * 2 + ["SMALL"])]
    (out / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    (out / "discovered.json").write_text(json.dumps(
        {h: {"handle": h, "status": "CANDIDATE"} for h in ("BIG", "SMALL")}), "utf-8")
    cfg = tmp / "cfg.json"
    cfg.write_text(json.dumps({"channels": [{"handle": "@A", "tabs": ["videos"]}]}), "utf-8")
    return out, cfg, rows


def _run(mod, monkeypatch: pytest.MonkeyPatch, out: Path, cfg: Path) -> list[str]:
    fetched: list[str] = []
    monkeypatch.setattr(mod, "fetch_transcript",
                        lambda api, vid: (fetched.append(vid) or ("NO_TRANSCRIPT", "", {})))
    monkeypatch.setattr(sys, "argv", ["x", "--config", str(cfg), "--out", str(out),
                                      "--discover", "--sleep", "0"])
    assert mod.main() == 0
    return fetched


def test_a_truncated_cache_never_kills_the_miner(tmp_path, monkeypatch) -> None:
    """MF1 (#762 audit): the task's time limit can cut a cache write short; the next run must
    treat the unreadable cache as empty (re-list everything) and go on fetching."""
    mod = _load(monkeypatch)
    out, cfg, rows = _seed(tmp_path)
    (out / "enum_cache.json").write_text('{"@A/videos": {"t": 17', "utf-8")   # cut mid-write
    by_ch = {}
    for r in rows:
        by_ch.setdefault(r["channel"], []).append(
            {k: r[k] for k in ("video_id", "title", "tab")})
    monkeypatch.setattr(mod, "discover", lambda cfg, out, n: [
        {"handle": "BIG", "status": "CANDIDATE"}, {"handle": "SMALL", "status": "CANDIDATE"}])
    monkeypatch.setattr(mod, "enumerate_tab", lambda handle, tab: by_ch.get(handle, []))
    fetched = _run(mod, monkeypatch, out, cfg)
    assert len(fetched) == len(rows)
    cache = json.loads((out / "enum_cache.json").read_text("utf-8"))   # rewritten whole
    assert {"@A/videos", "BIG/videos", "SMALL/videos", "_discovery"} <= set(cache)
    assert not list(out.glob("*.tmp"))


def test_inside_the_window_nothing_is_relisted_and_named_channels_go_first(
        tmp_path, monkeypatch) -> None:
    """Runs spend their time on captions: no re-listing within --refresh-hours, the config's
    channels first, then discovered channels smallest-first (big ones last, never skipped)."""
    mod = _load(monkeypatch)
    out, cfg, rows = _seed(tmp_path)
    keys = ("@A/videos", "BIG/videos", "SMALL/videos", "_discovery")
    (out / "enum_cache.json").write_text(json.dumps({k: {"t": time.time()} for k in keys}),
                                         "utf-8")

    def boom(*a, **k):
        raise AssertionError("re-listed inside the refresh window")

    monkeypatch.setattr(mod, "enumerate_tab", boom)
    monkeypatch.setattr(mod, "discover", boom)
    fetched = _run(mod, monkeypatch, out, cfg)
    owner = {r["video_id"]: r["channel"] for r in rows}
    assert [owner[v] for v in fetched] == ["@A", "@A", "SMALL"] + ["BIG"] * 5


def test_a_missing_discovered_file_forces_discovery(tmp_path, monkeypatch) -> None:
    """SF2: discovered channels must not silently drop out for a day because the file is gone."""
    mod = _load(monkeypatch)
    out, cfg, _ = _seed(tmp_path)
    (out / "discovered.json").unlink()
    (out / "enum_cache.json").write_text(json.dumps({"_discovery": {"t": time.time()}}),
                                         "utf-8")
    called = []
    monkeypatch.setattr(mod, "discover", lambda cfg, out, n: called.append(1) or [])
    monkeypatch.setattr(mod, "enumerate_tab", lambda handle, tab: [])
    _run(mod, monkeypatch, out, cfg)
    assert called == [1]
