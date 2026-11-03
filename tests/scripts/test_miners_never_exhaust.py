"""Every miner runs 24/7 and never finishes (principal, 2026-11-03): the YouTube corpus keeps
discovering channels and walking backlogs, a CDX walk wraps into new-capture polling, and a
frontier locale whose lexicon is spent refills from what it already found."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT / "scripts"), str(ROOT / "desks" / "mt5"),
          str(ROOT / "desks" / "mt5" / "side_channels")):
    if p not in sys.path:
        sys.path.insert(0, p)

import collect_youtube_corpus as yc  # noqa: E402


def _fake_api(calls: list[tuple[str, dict[str, Any]]]):
    def api(endpoint: str, spent: list[int], cost: int, **kw: Any) -> dict[str, Any]:
        if spent[0] + cost > yc.UNIT_BUDGET:
            raise RuntimeError("budget")
        spent[0] += cost
        calls.append((endpoint, kw))
        if endpoint == "search":
            return {"items": [{"id": {"channelId": "UCnewfromsearch0000000000"},
                               "snippet": {"title": "found"}}]}
        if endpoint == "channelSections":
            return {"items": [{"contentDetails": {"channels": ["UCfeatured000000000000000"]}}]}
        if endpoint == "channels" and "forHandle" in kw:
            return {"items": []}
        if endpoint == "channels":
            up = {"relatedPlaylists": {"uploads": "UU" + kw["id"]}}
            return {"items": [{"contentDetails": up}]}
        if endpoint == "playlistItems":
            tok = kw.get("pageToken")
            vid = f"{kw['playlistId']}-{tok or 'p0'}"
            return {"items": [{"snippet": {"publishedAt": "2026-01-01T00:00:00Z" if tok else
                                           "2026-11-01T00:00:00Z", "title": "t",
                                           "description": "see youtube.com/@similarhandle",
                                           "resourceId": {"videoId": vid}}}],
                    "nextPageToken": {None: "p1", "p1": "p2", "p2": None}[tok]}
        return {}
    return api


@pytest.fixture()
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(yc, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(yc, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(yc, "COVERAGE", tmp_path / "cov.json")
    monkeypatch.setattr(yc, "SEED_QUERIES", [])
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")
    (tmp_path / "reg.json").write_text(json.dumps(
        {"channels": {}, "discovered": {"seed": {"UCseed0000000000000000000": "seed"}}}), "utf-8")
    return tmp_path


def test_discovery_backfill_and_transcript_queue(corpus: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(yc, "api", _fake_api(calls))
    monkeypatch.setattr(yc, "fetch_transcript", lambda vid: (None, "ACCESS_LIMIT"))
    assert yc.main() == 0
    reg = json.loads((corpus / "reg.json").read_text("utf-8"))
    auto = reg["discovered"]["auto"]
    assert "UCnewfromsearch0000000000" in auto and "UCfeatured000000000000000" in auto
    assert reg["pending_handles"] == [] or "similarhandle" in reg["pending_handles"] or \
        any(e[0] == "channels" and e[1].get("forHandle") == "@similarhandle" for e in calls)
    # the seed channel's backlog was walked past the first page in the same run
    assert reg["backfill"]["UCseed0000000000000000000"] == "DONE"
    vids = {r["video_id"] for r in json.loads(next((corpus / "out").iterdir()).read_text("utf-8"))}
    assert {"UUUCseed0000000000000000000-p1", "UUUCseed0000000000000000000-p2"} <= vids
    assert reg["transcript_queue"], "a blocked transcript is queued for retry, never dropped"
    assert reg["quota"][next(iter(reg["quota"]))] > 0


def test_a_spent_daily_quota_stands_the_run_down(corpus: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime
    reg = json.loads((corpus / "reg.json").read_text("utf-8"))
    reg["quota"] = {f"{datetime.now(tz=UTC):%Y-%m-%d}": yc.DAILY_UNIT_BUDGET}
    (corpus / "reg.json").write_text(json.dumps(reg), "utf-8")
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(yc, "api", _fake_api(calls))
    monkeypatch.setattr(yc, "fetch_transcript", lambda vid: (None, "ACCESS_LIMIT"))
    assert yc.main() == 0
    assert calls == []


def test_a_missing_key_is_written_down_not_silent(corpus: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_API_KEY")
    monkeypatch.setattr(yc, "KEYFILE", corpus / "nope")
    monkeypatch.setattr(yc, "DESK_KEYFILE", corpus / "nope2")
    assert yc.main() == 0
    assert json.loads((corpus / "cov.json").read_text("utf-8"))["status"] == "KEY_MISSING"


def test_a_cdx_walk_wraps_into_new_capture_polling(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners as sm
    monkeypatch.setattr(sm, "STATE", tmp_path / "st.json")
    pages = [json.dumps([["h"], ["k", "20260101", "darwinex.com/darwin/ABC"]]), "[]",
             json.dumps([["h"]])]
    asked: list[str] = []
    monkeypatch.setattr(sm, "fetch", lambda url, **kw: (asked.append(url), pages.pop(0))[1])
    st: dict[str, Any] = {}
    assert len(sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")) == 2
    assert st["darwinex_cdx_offset"] == 1
    sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")      # empty page: lap ends
    assert st["darwinex_cdx_offset"] == 0 and st["darwinex_cdx_laps"] == 1
    sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")
    assert "&from=" in asked[-1], "the next lap polls only captures made since the last began"
