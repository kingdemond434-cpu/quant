"""Route classification (R0639, L1.28a).

Every fixture here is a body this desk MEASURED from a real host on 2026-08-20, not an invented
one. That matters: the defect being closed is that four different failures rendered identically,
so a test built from imagined responses would reproduce the blindness rather than catch it.
"""
from __future__ import annotations

import json

import pytest

from libs.research.video_routes import (
    RouteOutcome,
    caption_verdict,
    classify_response,
    locked_log_row,
)

# --- measured bodies, api.piped.private.coffee, 2026-08-20 -----------------------------------
# Two videos, the SAME host, the SAME minute, the SAME HTTP 500 -- and opposite dispositions for
# the GAP #26 purchase gate. This pair is the whole reason the module exists.
BOT_500 = json.dumps({"error": (
    "org.schabi.newpipe.extractor.exceptions.SignInConfirmNotBotException: YouTube probably "
    "temporarily blocked anonymous watch access with this IP , got error LOGIN_REQUIRED: "
    "\"Sign in to confirm that you're not a bot\"")}).encode()
PRIVATE_500 = json.dumps({"error": (
    "org.schabi.newpipe.extractor.exceptions.PrivateContentException: This video is private\n\tat "
    "org.schabi.newpipe.extractor.services.youtube.extractors.YoutubeStreamExtractor")}).encode()
SERVED_200 = json.dumps({
    "title": "Rick Astley - Never Gonna Give You Up",
    "subtitles": [{"code": "en", "url": "https://x/e"}] * 6}).encode()
# R0639's original find: 200, empty title, subtitles:[] -- an absence-shaped shell.
HOLLOW_200 = json.dumps({"title": "", "subtitles": []}).encode()
HTML_200 = b'\n<!DOCTYPE html>\n<html lang="en">\n  <head>\n\n<!-- G'   # drgns.space, yewtu.be
REAL_NO_SUBS = json.dumps({"title": "A real video with no captions", "subtitles": []}).encode()


class TestClassifyResponse:
    def test_bot_wall_and_private_are_distinguished_at_the_same_status(self) -> None:
        """THE defect. Both are HTTP 500 from one host; only one is buyable."""
        bot = classify_response("h", 500, BOT_500)
        priv = classify_response("h", 500, PRIVATE_500)
        assert bot.kind == "BOT_WALL"
        assert priv.kind == "PRIVATE"
        assert bot.kind != priv.kind

    def test_error_body_beats_status(self) -> None:
        """A 403 that names a bot wall is a wall, not a dead host."""
        assert classify_response("h", 403, BOT_500).kind == "BOT_WALL"

    @pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 502, 503, 504])
    def test_host_statuses_are_route_dead(self, status: int) -> None:
        assert classify_response("h", status, b"").kind == "ROUTE_DEAD"

    def test_no_response_is_route_dead_not_a_video_verdict(self) -> None:
        """NXDOMAIN on api.piped.yt was the sentence every seat actually read."""
        out = classify_response("h", None, b"", "URLError: Name or service not known")
        assert out.kind == "ROUTE_DEAD"
        assert not out.informative

    @pytest.mark.parametrize("body,why", [
        (b"", "zero-byte 200 (inv.nadeko.net caption content)"),
        (HTML_200, "HTML landing page served 200"),
        (HOLLOW_200, "empty title + zero tracks"),
    ])
    def test_three_hollow_200_shapes_are_not_absences(self, body: bytes, why: str) -> None:
        out = classify_response("h", 200, body)
        assert out.kind == "HOLLOW_200", why
        assert not out.informative

    def test_real_response_with_zero_tracks_is_no_tracks(self) -> None:
        assert classify_response("h", 200, REAL_NO_SUBS).kind == "NO_TRACKS"

    def test_served_tracks_are_counted(self) -> None:
        out = classify_response("h", 200, SERVED_200)
        assert (out.kind, out.n_tracks) == ("HAS_TRACKS", 6)

    def test_inventory_route_uses_its_own_tracks_key(self) -> None:
        """inv.nadeko.net returns {"captions": [...]}, not {"subtitles": [...]}."""
        body = json.dumps({"title": "t", "captions": [{"label": "Russian (auto-generated)"}]})
        out = classify_response("inv", 200, body.encode(), tracks_key="captions")
        assert (out.kind, out.n_tracks) == ("HAS_TRACKS", 1)


class TestVerdict:
    def test_private_outranks_a_wall(self) -> None:
        """A withdrawn video must never argue for a purchase that could not unlock it (OP-089)."""
        v, _ = caption_verdict([RouteOutcome("h", "PRIVATE", "")])
        assert v == "PRIVATE"

    def test_bot_wall_is_walled(self) -> None:
        v, _ = caption_verdict([RouteOutcome("h", "BOT_WALL", "")])
        assert v == "WALLED"

    def test_inventory_tracks_turn_a_dead_run_into_a_wall(self) -> None:
        """The measured case: Piped hollow, inv.nadeko.net lists a Russian auto-caption."""
        v, why = caption_verdict(
            [RouteOutcome("h", "HOLLOW_200", "")],
            inventory=RouteOutcome("inv", "HAS_TRACKS", "", 1))
        assert v == "WALLED"
        assert "1 caption track" in why

    def test_one_route_reporting_zero_tracks_is_UNMEASURED_not_NO_CAPTIONS(self) -> None:
        """L1.28a. The old code called this 'no subtitle tracks' and moved on."""
        v, _ = caption_verdict([RouteOutcome("h", "NO_TRACKS", "")])
        assert v == "UNMEASURED"

    def test_two_agreeing_routes_do_establish_no_captions(self) -> None:
        v, _ = caption_verdict([RouteOutcome("h", "NO_TRACKS", "")],
                               inventory=RouteOutcome("inv", "NO_TRACKS", ""))
        assert v == "NO_CAPTIONS"

    def test_dead_control_means_route_dead_never_walled(self) -> None:
        """If the control failed too, the run learned nothing about the video."""
        v, why = caption_verdict([RouteOutcome("h", "ROUTE_DEAD", "")],
                                 control=[RouteOutcome("h", "ROUTE_DEAD", "")])
        assert v == "ROUTE_DEAD"
        assert "do NOT log" in why

    def test_live_control_against_a_failing_target_is_a_wall(self) -> None:
        v, _ = caption_verdict([RouteOutcome("h", "HOLLOW_200", "")],
                               control=[RouteOutcome("h", "HAS_TRACKS", "", 6)])
        assert v == "WALLED"

    def test_no_control_and_nothing_informative_is_UNMEASURED(self) -> None:
        v, _ = caption_verdict([RouteOutcome("h", "ROUTE_DEAD", "")])
        assert v == "UNMEASURED"

    def test_a_dead_route_can_never_produce_the_verdict(self) -> None:
        """Last-error-wins put the deadest host in charge; ranking is what replaced it."""
        assert not RouteOutcome("h", "ROUTE_DEAD", "").informative
        assert not RouteOutcome("h", "HOLLOW_200", "").informative
        assert RouteOutcome("h", "BOT_WALL", "").informative


class TestPurchaseGateRow:
    def test_only_walled_earns_a_row(self) -> None:
        outs = [RouteOutcome("https://h", "BOT_WALL", "HTTP500 bot_wall")]
        row = locked_log_row("2026-08-20", "OWsum6xcNvM", "WALLED", "gate named", outs)
        assert "`OWsum6xcNvM`" in row and "BOT_WALL" in row and row.startswith("| 2026-08-20")

    @pytest.mark.parametrize("v", ["PRIVATE", "ROUTE_DEAD", "UNMEASURED", "NO_CAPTIONS", "OK"])
    def test_every_other_verdict_is_refused_a_row(self, v: str) -> None:
        """The log decides what the desk BUYS; a row it cannot support corrupts that decision."""
        with pytest.raises(ValueError, match="does not earn"):
            locked_log_row("2026-08-20", "x", v, "r", [])       # type: ignore[arg-type]
