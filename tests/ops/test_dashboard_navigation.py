"""ONE CANONICAL DASHBOARD, AND EVERY OTHER PAGE LEADS TO IT.

WHAT THIS TEST USED TO GUARD, and why the guard changed rather than went away. `web/index.html`
was the landing page and every link in its nav was a `#fragment` inside itself, so
`web/research.html` -- which carried the Stage-B shadow clocks -- was reachable only by typing
its filename. A page nobody can navigate to is a page nobody reads.

The desk had THREE dashboards by 2026-09-06: index.html (the retired Zenith build, 55KB),
research.html (22KB), and desk.html. Three views of one desk is worse than one: they disagree,
each is stale in a different way, and "which one is right" becomes a question the operator has to
answer before reading any number. So the answer to the navigation problem is no longer "link them
together" -- it is that there is only one page to be on.

index.html and research.html are now REDIRECTS rather than deletions. dash.quanttt.xyz and every
bookmark, tunnel and nginx root that already points at them keeps working and lands on the real
dashboard; deleting them would have turned a live URL into a 404 for no gain.
"""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent.parent.parent / "web"
CANONICAL = "desk.html"


def test_the_canonical_dashboard_exists() -> None:
    page = WEB / CANONICAL
    assert page.is_file(), "the one canonical dashboard is gone"
    assert len(page.read_text("utf-8")) > 5_000, "desk.html is a stub, not a dashboard"


def test_every_other_page_redirects_to_it() -> None:
    """THE ONE THAT MATTERS. No page may present a second, disagreeing view of the desk."""
    others = [p for p in WEB.glob("*.html") if p.name != CANONICAL]
    assert others, "nothing to check -- the glob is wrong and this test proves nothing"
    for p in others:
        src = p.read_text("utf-8")
        assert CANONICAL in src, f"{p.name} does not point at {CANONICAL}"
        assert 'http-equiv="refresh"' in src and "location.replace" in src, (
            f"{p.name} mentions {CANONICAL} but does not actually redirect to it -- a second "
            "dashboard that merely links to the first is still a second dashboard, and the "
            "operator still has to decide which number to believe")
        assert len(src) < 4_000, (
            f"{p.name} is {len(src)} bytes; a redirect is a redirect, and anything this large "
            "is a dashboard wearing one as a hat")


def test_the_canonical_page_reads_the_published_state() -> None:
    """A dashboard that cannot reach desk_state.json shows nothing, however good it looks."""
    src = (WEB / CANONICAL).read_text("utf-8")
    assert "desk_state.json" in src
    assert "build_zentech_state.py" in src, (
        "the page no longer names its producer; when it goes stale the reader has no thread to "
        "pull, which is exactly how a ten-day-old board went unnoticed")


def test_the_canonical_page_says_when_the_box_last_reported() -> None:
    """The single most important line on a dashboard for a desk holding live capital.

    A board showing ten-day-old numbers and one showing live numbers are pixel-identical; only
    the age distinguishes them, and for ten days the age was the one thing not on screen.
    """
    src = (WEB / CANONICAL).read_text("utf-8")
    for token in ("SILENT", "REPORTING", "box"):
        assert token in src, f"the dashboard never renders {token!r}; box liveness is invisible"
