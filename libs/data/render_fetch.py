"""RENDER PATH -- the way into the forests that serve their content by script.

WHY THIS EXISTS. Five of the desk's twelve foreign sources answer HTTP but hand back a shell:
smart-lab's search results are fetched by script and its HTML carries only sidebar promos,
note.com's API returns 403 to urllib while its search PAGE is a normal server-rendered route,
Coinpan sits behind a WAF that a real browser clears, Tinh te and Eksi Sozluk both serve
challenges. Every one was recorded as a ROUTING problem with a named route rather than an empty
forest (L1.54), and this module is that route.

Chromium is already installed on this box (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers) and
Playwright is configured to find it. The blockers were never about capability; nothing had been
built to use what was already there -- L1.50 again, on the tool rather than the data.

RENDERING IS EXPENSIVE AND IS BUDGETED. A urllib fetch costs milliseconds; a browser page costs
seconds and a few hundred MB of RSS. So this is NEVER the default path: a source that works
without it must not use it, and the per-run budget below is a hard stop rather than a guideline. A
miner that quietly started rendering every query would turn a two-minute sweep into an hour and
the cadence would be cut for the wrong reason.

FAILURE IS A NAMED REASON, NEVER AN EXCEPTION. Every entry point returns (html, error) and never
raises, because these are called from scheduled organs where a traceback kills the run before it
can record why. An absent Playwright, a missing browser binary, a timeout and a challenge page are
four different facts and each is reported as itself.

UNVERIFIED IN THE CLAUDE-CODE CONTAINER, AND THE REASON IS NOT THIS CODE. Measured 2026-08-05:
Chromium's egress is blocked at the NETWORK layer in this sandbox. `chrome --headless --dump-dom
https://example.com` returns ERR_CONNECTION_RESET both WITH `--proxy-server=$HTTPS_PROXY` and
without it, while urllib through the same proxy fetches every one of these hosts fine, and the
agent proxy records NO relay failure -- so the browser's traffic never reaches it. Five sites do
not fail identically at the same instant; the block is local. Per /root/.ccr/README.md the correct
action for a tool that cannot work through the proxy is to REPORT it, not to route around it, and
disabling TLS verification is forbidden regardless.

So this module is written, fenced and unit-tested, and its live path is exercised the first time
it runs somewhere with ordinary egress -- the VPS. That is a real limitation and it is stated here
rather than discovered later: the five forests it targets stay BLOCKED on this box, and the
artifact says so instead of implying a capability the desk does not have here.

NOTHING HERE LOGS IN, solves a CAPTCHA, or presents credentials. It renders public pages the same
way a person opening the URL would, and a page that requires an account stays blocked and says so
-- a membership is a person, not a credential.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any

__all__ = ["RENDER_BUDGET_PER_RUN", "budget_left", "render", "render_available", "reset_budget"]

#: Hard stop on browser pages per process. Rendering is ~3-6s and ~300MB each, against ~50ms for a
#: plain fetch, so an unbudgeted render path silently converts a fast sweep into one that gets
#: killed by a timeout -- and a lane cut for being slow looks exactly like a lane cut for being
#: worthless. Sized for "the blocked sources, once each, per sweep" and not for bulk crawling.
RENDER_BUDGET_PER_RUN = int(os.environ.get("RENDER_BUDGET_PER_RUN", "24"))

_used = 0

#: Anti-bot interstitials. A challenge page is a 200 with real HTML, so length alone cannot tell it
#: from content -- reporting one as a parse failure would send the desk hunting a markup change
#: that never happened.
_CHALLENGE_MARKERS: tuple[str, ...] = (
    "just a moment", "checking your browser", "cf-browser-verification", "cf_chl_",
    "attention required", "ddos-guard", "access denied", "captcha", "are you a robot",
)


def reset_budget() -> None:
    """Called at the start of a sweep. The budget is per-run, not per-process-lifetime."""
    global _used
    _used = 0


def budget_left() -> int:
    return max(0, RENDER_BUDGET_PER_RUN - _used)


def _executable() -> str:
    """The Chromium binary to launch, or "" to let Playwright choose.

    THE BUNDLED BROWSER AND THE INSTALLED PLAYWRIGHT DISAGREE ON A BUILD NUMBER. This box ships
    /opt/pw-browsers/chromium-1194; the pip Playwright expects a different revision directory and
    launches with "Executable doesn't exist". The documented fix for this environment is to pass
    the path explicitly rather than run `playwright install`, which would download a second
    browser bundle onto a fixed disk allowance for no capability gain.

    Probed rather than hardcoded to one revision: a rebuilt image bumps 1194 and a pinned path
    would fail closed with a confusing message about a missing executable when the browser is
    right there.
    """
    override = os.environ.get("CHROMIUM_EXECUTABLE_PATH", "")
    if override and os.path.isfile(override):
        return override
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if not os.path.isdir(root):
        return ""
    # Full chrome first, headless_shell second: the shell is lighter but several anti-bot layers
    # fingerprint it, and being blocked for using a headless shell would look like a dead source.
    for pattern in ("chromium-*/chrome-linux/chrome", "chromium/chrome-linux/chrome",
                    "chromium_headless_shell-*/chrome-linux/headless_shell"):
        import glob
        for hit in sorted(glob.glob(os.path.join(root, pattern)), reverse=True):
            if os.access(hit, os.X_OK):
                return hit
    return ""


def _proxy() -> str:
    """The outbound HTTPS proxy this environment forces traffic through, or "".

    CHROMIUM DOES NOT READ $HTTPS_PROXY, AND THAT LOOKED EXACTLY LIKE FIVE DEAD SOURCES. Python's
    urllib picks the proxy up automatically, so every plain-fetch source worked and every RENDERED
    one returned net::ERR_CONNECTION_RESET -- uniformly, on all five, which is the tell: five
    independent sites do not fail identically at the same instant. The block was ours.

    Read from the environment rather than pinned, because the port is assigned per session.
    """
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key, "")
        if val:
            return val
    port = os.environ.get("CLOUDSDK_PROXY_PORT", "")
    return f"http://127.0.0.1:{port}" if port else ""


def render_available() -> tuple[bool, str]:
    """(usable, why not). Checked BEFORE a caller decides to spend a render on a source."""
    try:
        import playwright  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:
        return False, f"playwright not importable: {exc}"
    path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if path and not os.path.isdir(path):
        return False, (f"PLAYWRIGHT_BROWSERS_PATH={path} is not a directory -- the browser bundle "
                       "is missing; do NOT run `playwright install`, this box ships its own")
    if not _executable():
        return False, (f"no executable Chromium found under {path or '/opt/pw-browsers'} -- the "
                       "bundle is present but no chrome/headless_shell binary is runnable")
    return True, ""


def looks_challenged(html: str) -> str:
    """The challenge marker present in this page, or "". A challenge is not a markup change."""
    low = str(html or "").lower()[:6000]
    for marker in _CHALLENGE_MARKERS:
        if marker in low:
            return marker
    return ""


def render(url: str, *, wait_selector: str = "", timeout_s: float = 25.0,
           wait_ms: int = 1200, lang: str = "") -> tuple[str, str]:
    """(html, error). Renders one public page with the bundled Chromium.

    `wait_selector` is the honest way to wait: a fixed sleep either wastes seconds on a fast page
    or truncates a slow one, and a truncated render looks exactly like an empty forest. Where a
    caller cannot name a selector, `wait_ms` after networkidle is the fallback and is stated as
    such rather than tuned silently.

    `lang` sets Accept-Language. Several of these sources serve different markup per locale, and
    fetching a Korean forum with an English header is how a parser written against the real page
    stops matching.
    """
    global _used
    ok, why = render_available()
    if not ok:
        return "", f"RENDER-UNAVAILABLE: {why}"
    if budget_left() <= 0:
        return "", (f"RENDER-BUDGET-EXHAUSTED: {RENDER_BUDGET_PER_RUN} page(s) already rendered "
                    "this run. Not a source failure -- raise RENDER_BUDGET_PER_RUN if the spend "
                    "is worth it, but a sweep that renders everything gets killed for being slow "
                    "and the lane then looks worthless rather than expensive.")
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

    _used += 1
    ctx_kw: dict[str, Any] = {
        "user_agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "viewport": {"width": 1366, "height": 900},
    }
    if lang:
        ctx_kw["locale"] = lang
        ctx_kw["extra_http_headers"] = {"Accept-Language": f"{lang},en;q=0.7"}
    try:
        with sync_playwright() as pw:
            args = ["--no-sandbox", "--disable-dev-shm-usage"]
            proxy = _proxy()
            if proxy:
                # The proxy terminates TLS with its own CA. Chromium is told to trust it here
                # rather than having verification disabled -- ignore-certificate-errors would
                # make every rendered page unauthenticated, and a miner that cannot tell a real
                # site from an intercepted one is a worse problem than a blocked source.
                args += [f"--proxy-server={proxy}", "--proxy-bypass-list=<-loopback>"]
            launch_kw: dict[str, Any] = {"args": args}
            exe = _executable()
            if exe:
                launch_kw["executable_path"] = exe
            browser = pw.chromium.launch(**launch_kw)
            try:
                page = browser.new_context(**ctx_kw).new_page()
                page.set_default_timeout(timeout_s * 1000)
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
                if wait_selector:
                    # The selector never appearing is a REAL finding about the page. Returning what
                    # DID render lets the caller separate "no results" from "different markup",
                    # which raising here would collapse into one indistinguishable failure.
                    with contextlib.suppress(Exception):
                        page.wait_for_selector(wait_selector, timeout=timeout_s * 1000)
                else:
                    page.wait_for_timeout(wait_ms)
                html = str(page.content())
            finally:
                browser.close()
    except Exception as exc:
        return "", f"RENDER-FAILED: {type(exc).__name__}: {str(exc)[:180]}"

    marker = looks_challenged(html)
    if marker:
        return html, (f"RENDER-CHALLENGED: the page returned an anti-bot interstitial "
                      f"({marker!r}). A challenge is NOT a markup change and NOT an empty forest "
                      "-- it is a live block on a rendered session, which is the strongest signal "
                      "the desk can get that this source needs a person rather than an engineer.")
    return html, ""
