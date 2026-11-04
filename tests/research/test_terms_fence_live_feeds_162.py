"""#162 audit, MF1 and the #262 should-fix: the live feeds a source's own terms permit keep running.

MF1: the per-source policy refused every IDEAS_ONLY source as live input, which also killed the
free stack's Telegram and Reddit feeds. Telegram is IDEAS_ONLY (auditor ruling 2026-10-13); the
Reddit, Yahoo, mql5 and Telegram rows carry their own terms page and the verbatim clause that puts
them in their state; Reddit's live route is its official Data API (OAuth), NEEDS_KEY until the
keys exist, and the free stack's fetcher uses that route -- never the public .json pages.

Should-fix (#262): `acquire_datasets._fetch` and `seed_miners.fetch` never follow a redirect into
a login / sign-in wall; the wall is never requested and the refusal is recorded METHOD_BLOCKED.

NO NETWORK: every request is served by an in-process handler or a fixture transport.
"""
from __future__ import annotations

import email.message
import io
import json
import sys
import urllib.request
import urllib.response
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
KEYS = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def _roster_row(sid: str) -> dict[str, Any]:
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    return next(r for r in doc["sources"] if r["id"] == sid)


# ------------------------------------------------------------------ the rows and their terms
@pytest.mark.parametrize(("key", "status", "needle"), [
    ("reddit", tf.IDEAS_ONLY, "Traffic not using OAuth or login credentials will be blocked"),
    ("reddit_api", tf.NEEDS_KEY, "Reddit requires OAuth for authentication"),
    ("yahoo", tf.IDEAS_ONLY, "using any automated means"),
    ("mql5", tf.IDEAS_ONLY, "through any automated means, including use of scripts"),
    ("telegram", tf.SOURCE_POLICY["telegram"]["status"], "Telegram firmly prohibits the scraping"),
])
def test_each_row_carries_its_own_terms_page_and_verbatim_clause(key: str, status: str,
                                                                 needle: str) -> None:
    row = tf.SOURCE_POLICY[key]
    assert tf.status(key) == status
    assert tf.terms_state(key) == "READ"
    assert row["terms"]["url"].startswith("https://") and row["terms"]["checked_at"]
    assert any(needle in c for c in row["terms"]["clauses"].values()), key
    reg = {r["source"]: r for r in tf.registry_rows()}
    assert reg[key]["terms_state"] == "READ" and reg[key]["terms_url"] == row["terms"]["url"]


def test_a_row_without_a_terms_record_reads_unread_never_permitted() -> None:
    assert tf.terms_state("stocktwits") == tf.UNREAD
    assert tf.input_source("stocktwits") == "stocktwits"


#: Read off the row (auditor ruling 2026-10-13: IDEAS_ONLY; the revert to PUBLIC_PAGE is the
#: one line `terms_fence.SOURCE_POLICY["telegram"]["status"]`, and these tests follow it).
TELEGRAM = tf.SOURCE_POLICY["telegram"]["status"]
_NOT_LIVE = (tf.IDEAS_ONLY, *tf.HOLDING)


def test_telegram_previews_follow_their_row_for_live_input() -> None:
    assert tf.policy_of_url("https://t.me/s/markettwits")["status"] == TELEGRAM
    want = "telegram" if TELEGRAM in _NOT_LIVE else None
    assert tf.input_source("telegram", "https://t.me/s/") == want


def test_the_free_stack_telegram_feed_follows_its_row(tmp_path: Path) -> None:
    from research import free_stack_hunter as H
    asked: list[str] = []

    def fetch(url: str, hd: Any = None, body: Any = None) -> bytes:
        asked.append(url)
        return b""

    h, _ = H.run_source(_roster_row("telegram"), H.Store(tmp_path), fetch, {}, NOW)
    if TELEGRAM in _NOT_LIVE:
        assert h.status == TELEGRAM, h.detail
        assert not asked, "an IDEAS_ONLY source is never fetched as live input"
    else:
        assert asked, "a PUBLIC_PAGE feed runs as live input"


def test_reddit_live_input_is_the_data_api_route_only(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tf.input_source("reddit") == "reddit_api"                      # NEEDS_KEY
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id-x")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret-x")
    assert tf.input_source("reddit") is None                              # the API route
    assert tf.input_source("https://oauth.reddit.com/r/Gold/new") is None
    # a public page is still IDEAS_ONLY, keys or not
    assert tf.input_source("https://www.reddit.com/r/Gold/new.json") == "reddit"


def test_the_free_stack_reddit_fetcher_uses_oauth_and_never_the_public_pages(
        monkeypatch: pytest.MonkeyPatch) -> None:
    row = _roster_row("reddit")
    assert row["url"] == "https://oauth.reddit.com/"
    asked: list[tuple[str, dict[str, str], bytes | None]] = []
    listing = json.dumps({"data": {"children": [
        {"data": {"name": "t3_a", "author": "u1", "title": "gold squeeze incoming",
                  "selftext": "", "created_utc": 1_760_000_000}}]}}).encode()

    def fetch(url: str, hd: Any = None, body: Any = None) -> bytes:
        asked.append((url, dict(hd or {}), body))
        if url == fs.REDDIT_TOKEN_URL:
            return b'{"access_token": "tok-1", "token_type": "bearer"}'
        return listing

    # no keys: nothing is requested, NEEDS_KEY is named
    h = fs.fetch_reddit(fetch, row, {}, NOW)
    assert asked == [] and h.failures["NEEDS_KEY"] == 1
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id-x")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret-x")
    h = fs.fetch_reddit(fetch, row, {}, NOW)
    urls = [u for u, _, _ in asked]
    assert urls[0] == fs.REDDIT_TOKEN_URL and asked[0][2] == b"grant_type=client_credentials"
    assert asked[0][1]["Authorization"].startswith("Basic ")
    assert all(u.startswith("https://oauth.reddit.com/r/") for u in urls[1:]) and urls[1:]
    assert all(hd["Authorization"] == "bearer tok-1" for _, hd, _ in asked[1:])
    assert not [u for u in urls if ".json" in u], "a public .json page was requested"
    assert h.raw, "posts reach the archive through the API route"


# ------------------------------------------------- should-fix: login-wall redirects (#262)
class _FakeWeb(urllib.request.BaseHandler):
    handler_order = 100

    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes
        self.asked: list[str] = []

    def _serve(self, req: urllib.request.Request) -> Any:
        url = req.full_url
        self.asked.append(url)
        code, val = self.routes.get(url, (404, ""))
        hdrs = email.message.Message()
        if 300 <= code < 400:
            hdrs["Location"] = val
            body = b""
        else:
            hdrs["Content-Type"] = "text/csv"
            body = val.encode()
        resp = urllib.response.addinfourl(io.BytesIO(body), hdrs, url, code)
        resp.msg = "fake"  # type: ignore[attr-defined]
        return resp

    http_open = _serve
    https_open = _serve


WALL = "http://data.example.test/accounts/login?next=/a.csv"


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> _FakeWeb:
    fake = _FakeWeb({
        "http://data.example.test/a.csv": (302, WALL),
        "http://data.example.test/b.csv": (302, "http://data.example.test/signin"),
        "http://data.example.test/ok.csv": (200, "date,value\n2026-01-01,1\n"),
    })
    real = tf.guarded_opener
    monkeypatch.setattr(tf, "guarded_opener", lambda context=None, *h: real(context, fake, *h))
    return fake


def test_acquire_records_a_login_wall_redirect_as_method_blocked(
        web: _FakeWeb, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import acquire_datasets as ad
    assert ad._fetch("http://data.example.test/a.csv") == (None, "METHOD_BLOCKED:login_wall")
    assert WALL not in web.asked, "the login wall was requested"
    monkeypatch.setattr(ad, "STORE", tmp_path / "acq")
    monkeypatch.setattr(ad, "REGISTRY", tmp_path / "acq" / "registry.json")
    monkeypatch.setattr(ad, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(ad, "_endpoints", lambda limit: [
        ("http://data.example.test/a.csv", "data.example.test"),
        ("http://data.example.test/b.csv", "data.example.test")])
    rep = ad.acquire(limit=5)
    assert rep["method_blocked"] == {"by_reason": {"login_wall": 2}, "total": 2}
    reg = json.loads((tmp_path / "acq" / "registry.json").read_text("utf-8"))
    assert {v["status"] for v in reg["by_url"].values()} == {"METHOD_BLOCKED"}
    assert not [u for u in web.asked if tf.login_wall(u)]


def test_seed_miners_fetch_never_follows_a_login_wall_redirect(
        web: _FakeWeb, monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners as sm
    monkeypatch.setattr(sm.time, "sleep", lambda _s: None)
    with pytest.raises(pf.MethodRefused) as exc:
        sm.fetch("http://data.example.test/a.csv")
    assert exc.value.status == tf.METHOD_BLOCKED and exc.value.platform == "login_wall"
    assert WALL not in web.asked
    assert sm.fetch("http://data.example.test/ok.csv").startswith("date,value")
    assert "requests.get(" not in (DESK / "side_channels" / "seed_miners.py").read_text("utf-8")


def test_one_fetch_door_one_table() -> None:
    """#162 x #262 composition: polite_fetch's door IS terms_fence's, with one refusal type."""
    assert pf.MethodRefused is tf.TermsFenced
    assert pf.LOGIN_WALL is tf.LOGIN_WALL and pf.login_wall is tf.login_wall
    import mql5_terms
    assert mql5_terms.POLICY["clauses"] == tf.SOURCE_POLICY["mql5"]["terms"]["clauses"]
    src = (ROOT / "libs" / "data" / "polite_fetch.py").read_text("utf-8")
    assert "class MethodRedirectHandler" not in src and "re.compile(r\"(?i)/(?:i/flow" not in src
