"""A DASHBOARD SECTION NOBODY CAN NAVIGATE TO IS AN ARTIFACT NOBODY WRITES, ONE LAYER UP.

Measured 2026-08-13, reported by the principal as "none of shadow candidates etc update here":
`web/index.html` is the page dash.quanttt.xyz lands on, and every link in its nav was a
`#fragment` inside itself. `web/research.html` -- which carries the Stage-B shadow clocks, the
axis verdicts and the loss forensics -- was reachable ONLY by typing the URL.

The artifacts were never stale. `serve_dashboard` sends `Cache-Control: no-store` and the cycle
rewrites `web/axis_shadows.json` every run. The page showing them simply had no door, so the data
looked frozen while being perfectly fresh -- which is the worst version of this failure, because
it reads as a broken pipeline and sends you looking in the wrong place.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"


def _pages() -> list[Path]:
    return sorted(WEB.glob("*.html"))


def test_every_page_is_reachable_from_the_landing_page() -> None:
    """THE ONE THAT MATTERS. Any page not linked from index.html is invisible to a human who
    does not already know it exists."""
    index = (WEB / "index.html").read_text("utf-8")
    linked = set(re.findall(r'href="([A-Za-z0-9_\-]+\.html)"', index))
    orphans = [p.name for p in _pages()
               if p.name != "index.html" and p.name not in linked]
    assert orphans == [], (
        f"{orphans} exist under web/ and nothing on the landing page links to them. Their data "
        "updates every cycle and no reader can get to it")


def test_the_shadow_clocks_are_actually_rendered_somewhere() -> None:
    """Guard the guard: a link to a page that does not read the artifact proves nothing."""
    assert any("axis_shadows" in p.read_text("utf-8") for p in _pages()), (
        "no dashboard page reads web/axis_shadows.json -- the forward clocks are unrendered")


def test_research_links_back_so_the_nav_is_not_a_dead_end() -> None:
    assert 'index.html' in (WEB / "research.html").read_text("utf-8")


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.name)
def test_no_page_links_to_a_file_that_does_not_exist(page: Path) -> None:
    """A nav entry pointing at a missing page is worse than no entry: it reads as a broken
    dashboard rather than an absent one."""
    for target in re.findall(r'href="([A-Za-z0-9_\-]+\.html)"', page.read_text("utf-8")):
        assert (WEB / target).exists(), f"{page.name} links to missing {target}"
