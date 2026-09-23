"""VIDEO ROUTE CLASSIFICATION -- a failed fetch is a verdict about a ROUTE or about a VIDEO,
and until now this desk could not tell which (R0639, L1.28a).

WHY THIS MODULE EXISTS, MEASURED 2026-08-20 FROM THIS BOX IN ONE MINUTE.
`scripts/fetch_video_transcript.py` rotated four hardcoded Piped instances and collapsed every
outcome into one string, `last = f"{host}: {type(exc).__name__} {exc}"`. Three consequences, each
measured, none visible to any reader of that string:

  1. THE ERROR BODY -- THE ONLY PLACE THE ANSWER LIVES -- WAS THROWN AWAY. `urlopen` RAISES on a
     500, and the raised `HTTPError` IS the response: its body carries the discriminator.
     Same instance, same minute, same HTTP 500:

        OWsum6xcNvM  ->  SignInConfirmNotBotException ... LOGIN_REQUIRED
                         "Sign in to confirm that you're not a bot"      = BOT_WALL
        ilSpSqKWkRg  ->  PrivateContentException: This video is private  = PRIVATE

     Those demand OPPOSITE decisions from the GAP #26 purchase gate -- a bot wall is exactly what
     a residential/authenticated route would buy back, and a withdrawn video is unbuyable at any
     price and would CORRUPT the gate if logged (OP-089). The old code rendered both as the
     byte-identical string `HTTPError HTTP Error 500: Internal Server Error`.

  2. LAST-ERROR-WINS MEANS THE DEADEST INSTANCE ALWAYS SPEAKS LAST. Of the four hardcoded hosts,
     three are dead and one (`api.piped.yt`) no longer resolves at all -- so the message a seat
     actually read was ALWAYS `api.piped.yt: URLError Name or service not known`. A DNS failure on
     a domain that no longer exists is the least informative sentence available, and it points the
     reader at the desk's own tooling. That is R0527's misattribution reproduced one layer down:
     a verdict about our egress presented as a verdict about the source.

  3. A HOLLOW 200 READ AS AN ABSENCE. `if not subs: last = "no subtitle tracks"` cannot separate
     "this video genuinely has no captions" from "this route returned a shell". Three distinct
     hollow-200 shapes were measured today, all of which the old path would have called an
     absence: a JSON body with an empty title and `subtitles: []`; an HTML landing page served
     with status 200 (`pipedapi.drgns.space`, `yewtu.be`, `invidious.nerdvpn.de`); and a
     ZERO-BYTE 200 (`inv.nadeko.net` caption content, for the KNOWN-GOOD CONTROL as well).

THE REFEREE, AND IT IS FREE. Two independent checks decide what a failure means, both keyless:

  THE CONTROL   a known-good popular video fetched through the SAME host in the SAME run. If the
                control fails too, the ROUTE is dead and the run has learned NOTHING about the
                target video -- it must not be logged as a wall. This is the desk lesson "a
                heartbeat proves the loop is alive, never that the pipe is", made mechanical.
  THE INVENTORY a second route that lists a video's caption tracks without serving their bodies.
                Measured today: `inv.nadeko.net/api/v1/captions/OWsum6xcNvM` returns 200 with one
                `Russian (auto-generated)` track for the very video Piped answers with a bot wall.
                So the tracks EXIST and no free route serves them -- which is precisely the claim
                GAP #26's purchase gate has to be able to make, and could previously only be made
                by hand (see the 2026-08-19 row in docs/research/video_locked_log.md, where a seat
                classified ten routes manually because the tool could not).

WHAT THIS MODULE DOES NOT DO. It buys nothing, promotes nothing, loosens nothing and fetches
nothing -- it is pure classification over responses a caller already holds. It cannot turn a
failure into a success; its whole effect is to make "no free route serves this" distinguishable
from "our proxy list has rotted", which were byte-identical on this desk until now, and only one
of them is evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "CONTROL_VIDEO",
    "RouteKind",
    "RouteOutcome",
    "Verdict",
    "caption_verdict",
    "classify_response",
    "locked_log_row",
]

# A very popular video that resolves whenever the route itself is healthy. It is the REFEREE, not
# a target: its only job is to answer "was this host able to serve anything at all just now?".
CONTROL_VIDEO = "dQw4w9WgXcQ"

RouteKind = Literal[
    "HAS_TRACKS",   # the route listed >=1 caption track for this video
    "NO_TRACKS",    # a REAL response (non-empty title, no error) that lists zero tracks
    "BOT_WALL",     # the anti-bot gate: LOGIN_REQUIRED / "not a bot" / SignInConfirm
    "PRIVATE",      # withdrawn or private -- unbuyable, must never feed the purchase gate
    "HOLLOW_200",   # status 200 carrying a shell: empty body, HTML, or empty-title JSON
    "ROUTE_DEAD",   # DNS, refused, timeout, 401/403/404/301/502/503/504 -- about the HOST
]

Verdict = Literal[
    "OK",           # a transcript was obtained
    "NO_CAPTIONS",  # the video genuinely has none -- corroborated by an inventory route
    "WALLED",       # captions exist (or a wall was named) and no free route serves them
    "PRIVATE",      # withdrawn/private -- unbuyable (OP-089); never a purchase-gate row
    "ROUTE_DEAD",   # every route failed AND the control failed too: says nothing about the video
    "UNMEASURED",   # could not tell -- never resolves to a clean verdict (L1.28a)
]

# Markers read out of the response body. These are NewPipe/Piped extractor exception names and the
# YouTube error strings they carry; matching is case-insensitive on the raw body, so it works
# whether the body is JSON, an HTML error page, or a plain string.
_BOT_MARKERS = (
    "signinconfirmnotbot",
    "login_required",
    "not a bot",
    "sign in to confirm",
    "confirm you're not a bot",
)
_PRIVATE_MARKERS = (
    "privatecontentexception",
    "video is private",
    "content is private",
    "unavailable video",
    "videounavailable",
)
# Statuses that describe the HOST, never the video. 500 is deliberately ABSENT: Piped answers a
# bot wall AND a private video with 500, so a 500 must be decided from its body, never its status.
_DEAD_STATUSES = frozenset({301, 302, 401, 403, 404, 410, 429, 502, 503, 504})


@dataclass(frozen=True)
class RouteOutcome:
    """One host's answer about one video, classified. `detail` is kept for the log row."""

    host: str
    kind: RouteKind
    detail: str
    n_tracks: int = 0

    @property
    def informative(self) -> bool:
        """Did this host tell us anything about the VIDEO (rather than about itself)?

        A dead or hollow route may never produce the verdict -- that is the whole defect this
        module exists to close, and it is why `caption_verdict` ranks outcomes instead of taking
        the last one.
        """
        return self.kind not in ("ROUTE_DEAD", "HOLLOW_200")


def _body_marker(body: bytes) -> RouteKind | None:
    """BOT_WALL / PRIVATE if the body names one, else None. Read the body of an ERROR too."""
    low = body[:4096].decode("utf-8", errors="replace").lower()
    if any(m in low for m in _PRIVATE_MARKERS):
        return "PRIVATE"
    if any(m in low for m in _BOT_MARKERS):
        return "BOT_WALL"
    return None


def classify_response(
    host: str,
    status: int | None,
    body: bytes,
    exc: str = "",
    *,
    tracks_key: str = "subtitles",
) -> RouteOutcome:
    """Classify ONE host's response.

    `status` is None when the request never completed (DNS, refused, timeout) -- those are always
    ROUTE_DEAD. `body` must be the response body EVEN FOR AN ERROR STATUS: on Piped the 500 body
    is the only place the bot-wall/private distinction exists, and discarding it is what made the
    two indistinguishable.
    """
    if status is None:
        return RouteOutcome(host, "ROUTE_DEAD", exc or "no response")

    # The body decides before the status does: a 500 carrying PrivateContentException is a fact
    # about the video, and a 200 carrying LOGIN_REQUIRED is a fact about the wall.
    marker = _body_marker(body)
    if marker is not None:
        return RouteOutcome(host, marker, f"HTTP{status} {marker.lower()}")

    if status in _DEAD_STATUSES:
        return RouteOutcome(host, "ROUTE_DEAD", f"HTTP{status}")
    if status != 200:
        # Any other non-200 (500 included, once the body has been read and named nothing) is a
        # statement about the host, not about the video.
        return RouteOutcome(host, "ROUTE_DEAD", f"HTTP{status} unclassified")

    if not body.strip():
        # Measured on inv.nadeko.net caption content, for the CONTROL as well as the target.
        return RouteOutcome(host, "HOLLOW_200", "HTTP200 zero-byte body")
    try:
        meta = json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        # An HTML landing page served with status 200. Measured on three hosts today.
        return RouteOutcome(host, "HOLLOW_200", f"HTTP200 non-JSON ({len(body)}B)")
    if not isinstance(meta, dict):
        return RouteOutcome(host, "HOLLOW_200", "HTTP200 non-object JSON")

    tracks = meta.get(tracks_key) or []
    n = len(tracks) if isinstance(tracks, list) else 0
    title = str(meta.get("title") or "").strip()
    if n:
        return RouteOutcome(host, "HAS_TRACKS", f"HTTP200 {n} track(s)", n_tracks=n)
    if not title:
        # R0639's original find: 200, empty title, subtitles:[]. An absence-shaped shell.
        return RouteOutcome(host, "HOLLOW_200", "HTTP200 empty title, zero tracks")
    return RouteOutcome(host, "NO_TRACKS", f"HTTP200 {title[:40]!r}, zero tracks")


def caption_verdict(
    target: list[RouteOutcome],
    control: list[RouteOutcome] | None = None,
    inventory: RouteOutcome | None = None,
    *,
    served_text: bool = False,
) -> tuple[Verdict, str]:
    """Decide what a set of route outcomes means. Returns (verdict, one-line reason).

    The ordering is not cosmetic. Each rule below is the answer to a way this desk has actually
    been wrong:

      PRIVATE before WALLED   -- a withdrawn video would otherwise argue for a purchase that could
                                 never unlock it (OP-089).
      inventory before        -- "zero tracks" is only an ABSENCE if an independent route agrees;
      NO_CAPTIONS               otherwise it is our route being shown a shell.
      control last            -- when nothing informative came back at all, the control is the only
                                 thing that separates a walled video from a rotted proxy list.
    """
    if served_text:
        return "OK", "transcript served"
    if any(o.kind == "PRIVATE" for o in target):
        return "PRIVATE", "withdrawn/private -- unbuyable, not a purchase-gate row (OP-089)"
    if any(o.kind == "BOT_WALL" for o in target):
        return "WALLED", "anti-bot gate named by the route body (LOGIN_REQUIRED / not-a-bot)"
    if inventory is not None and inventory.kind == "HAS_TRACKS":
        return "WALLED", (
            f"inventory route lists {inventory.n_tracks} caption track(s) that no free content "
            f"route would serve"
        )
    if any(o.kind == "NO_TRACKS" for o in target):
        if inventory is not None and inventory.kind == "NO_TRACKS":
            return "NO_CAPTIONS", "two independent routes agree the video carries no captions"
        # One route's "zero tracks" is not an absence. L1.28a: absence must not resolve clean.
        return "UNMEASURED", (
            "one route reported zero tracks and no inventory route corroborated it -- "
            "cannot separate 'no captions' from 'shown a shell'"
        )
    if control:
        if any(o.kind in ("HAS_TRACKS", "NO_TRACKS") for o in control):
            return "WALLED", (
                "the known-good control resolved through these same hosts in the same run, "
                "so the failure is specific to this video"
            )
        return "ROUTE_DEAD", (
            "the known-good control failed on every host too -- this run learned nothing about "
            "the video; do NOT log it as a wall"
        )
    return "UNMEASURED", "no informative route outcome and no control was run"


def locked_log_row(
    date: str,
    video: str,
    verdict: Verdict,
    reason: str,
    outcomes: list[RouteOutcome],
    mechanism: str = "",
) -> str:
    """Render the docs/research/video_locked_log.md row for a WALLED verdict.

    Only WALLED earns a row. PRIVATE is unbuyable (OP-089), ROUTE_DEAD is a statement about our
    egress, and UNMEASURED has by definition not established anything -- logging any of them would
    argue for a purchase on evidence that does not support one, on the single artifact whose whole
    job is to decide what to buy.
    """
    if verdict != "WALLED":
        raise ValueError(f"{verdict} does not earn a purchase-gate row -- only WALLED does")
    routes = "; ".join(f"{o.host}={o.kind}" for o in outcomes) or "no routes attempted"
    return (
        f"| {date} | youtube | `{video}` | {mechanism or 'mechanism not yet read'} | "
        f"{reason}. Routes tried: {routes} |"
    )
