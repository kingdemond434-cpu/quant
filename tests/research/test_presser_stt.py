"""presser_stt: terms-first registry, fail-closed fetch law, UNMEASURED without a model, and
per-minute lexicon tone into the news seat. No test contacts the network."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT))

from research import presser_stt as m  # noqa: E402


def _no_network(*_a, **_k):
    raise AssertionError("a test reached the network")


def test_registry_is_terms_first_and_refuses_what_it_must() -> None:
    assert m.SOURCES["boj"]["verdict"] == m.REFUSED
    for bank, src in m.SOURCES.items():
        assert src["verdict"] in (m.ALLOWED, m.HELD, m.REFUSED), bank
        assert src["reading"], bank
        url = str(src.get("media_url") or "")
        assert "youtube" not in url and "youtu.be" not in url
    # nothing was verified terms-clean on 2026-11-18, so the box contacts nothing
    assert not [b for b, s in m.SOURCES.items() if s["verdict"] == m.ALLOWED]


def test_gate_refuses_youtube_and_fred_before_any_request() -> None:
    for url in ("https://www.youtube.com/embed/x", "https://youtu.be/x",
                "https://fred.stlouisfed.org/x.mp4"):
        assert m.gate(url, open_url=_no_network).startswith("REFUSED")
    assert m.gate("http://www.snb.ch/a.mp4", open_url=_no_network).startswith("REFUSED")


def test_robots_fail_closed_and_403_on_media_is_held(monkeypatch) -> None:
    monkeypatch.setattr(m, "_ROBOTS", {})

    def broken(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "x", {}, None)  # type: ignore[arg-type]
    assert m.gate("https://a.example.org/v.mp4", open_url=broken).startswith(m.HELD)

    calls: list[str] = []

    def robots_ok_media_403(req, timeout=None):
        calls.append(req.full_url)
        if req.full_url.endswith("/robots.txt"):
            return io.BytesIO(b"User-agent: *\nDisallow: /private/\n")
        raise urllib.error.HTTPError(req.full_url, 403, "x", {}, None)  # type: ignore[arg-type]
    monkeypatch.setattr(m, "_ROBOTS", {})
    body, why = m.fetch("https://b.example.org/private/v.mp4", open_url=robots_ok_media_403)
    assert body is None and "disallows" in why and len(calls) == 1
    body, why = m.fetch("https://b.example.org/v.mp4", open_url=robots_ok_media_403)
    assert body is None and why == f"{m.HELD}: HTTP 403"


def test_no_model_is_unmeasured_and_never_crashes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(m.MODEL_ENV, str(tmp_path / "absent"))
    st = m.model_status()
    assert st["ready"] is False and st["status"] == m.UNMEASURED and st["reason"]
    got = m.from_media(tmp_path / "x.mp3", "fed", datetime(2026, 12, 9, 19, 30, tzinfo=UTC))
    assert got["rows"] == 0 and got["status"] == m.UNMEASURED


def test_minute_rows_score_tone_with_the_desk_lexicon(tmp_path) -> None:
    segs = [(5.0, 9.0, "We remain hawkish and expect further rate hikes."),
            (61.0, 70.0, "A rate cut is possible; policy easing may follow."),
            (75.0, 80.0, "Thank you.")]
    start = datetime(2026, 12, 9, 19, 30, tzinfo=UTC)
    rows = m.minute_rows(segs, bank="fed", started_at=start, knowable_at=lambda s: s)
    assert [r["minute"] for r in rows] == [0, 1]
    assert rows[0]["monetary_tone"] > 0 > rows[1]["monetary_tone"]
    assert rows[1]["spoken_at"] == "2026-12-09T19:31:00Z"
    assert rows[0]["source"].startswith("central_bank") and rows[0]["research_input_only"]
    n = m.append_rows(rows, start, seat=tmp_path)
    lines = (tmp_path / "presser_tone_20261209.jsonl").read_text().splitlines()
    assert n == 2 and json.loads(lines[0])["kind"] == "presser_minute"


def test_calendar_windows_and_plan_report(tmp_path, monkeypatch) -> None:
    fomc = tmp_path / "ev.json"
    fomc.write_text(json.dumps({"events": [{"utc": "2026-12-09T19:00:00Z",
                                            "name": "FOMC decision"}]}))
    boc = tmp_path / "boc.json"
    boc.write_text(json.dumps({"tz": "America/Toronto", "dates": {"2026-12-09": "09:45"}}))
    wins, notes = m.windows(fomc=fomc, boc=boc)
    by = {w["bank"]: w for w in wins}
    assert by["fed"]["starts_at"] == "2026-12-09T19:30:00Z"
    assert by["boc"]["starts_at"] == "2026-12-09T15:45:00Z"
    assert any("ecb" in n for n in notes)
    assert m.open_window(wins, datetime(2026, 12, 9, 19, 40, tzinfo=UTC))["bank"] == "fed"
    monkeypatch.setattr(m, "FOMC_CALENDAR", fomc)
    monkeypatch.setattr(m, "BOC_CALENDAR", boc)
    monkeypatch.setattr(m, "SEAT", tmp_path / "seat")
    monkeypatch.setattr(m, "REPORT", tmp_path / "PRESSER_STT.json")
    doc = m.watch(datetime(2026, 12, 9, 19, 40, tzinfo=UTC))
    assert doc["status"] == m.UNMEASURED and "no source is ALLOWED" in doc["why"]
    assert doc["capture"]["status"] == m.HELD           # the Fed source is held, so no fetch
    saved = json.loads((tmp_path / "PRESSER_STT.json").read_text())
    assert saved["sources"]["ecb"]["verdict"] == m.REFUSED


def test_live_capture_refuses_a_source_that_is_not_allowed() -> None:
    got = m.capture_live("boc", datetime(2030, 1, 1, tzinfo=UTC), open_url=_no_network)
    assert got["rows"] == 0 and got["status"] == m.REFUSED


def test_presser_seat_feeds_the_news_stream_and_has_a_layer() -> None:
    from research import news_event_stream
    assert "presser_stt" in news_event_stream.NEWS_SEATS
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["presser_stt"] == "information"
    assert news_event_stream.source_tier("central_bank_presser_fed") == "official_statement"
