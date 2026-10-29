"""Every 401/403/429/WAF hold waits for a person (audit GD_LANDING_TRAIN_6eb7a91b4).

* MF1 -- polite_fetch: a 429 or a challenge page used to be held for 24h (`recheck_after_ts`).
  Now every hold is the shared person-held record (released_by null) and still stands 400 days
  later; a legacy row carrying a past `recheck_after_ts` is still active; only `release` (or
  `python -m libs.data.polite_fetch --release site:<site> --by <name>`) ends it.
* gtrends -- `research/hard_stop.py` backs off on a clock (1h..7d) and is not edited here; both
  Google Trends readers now consult polite_fetch's person-held hold before every request and
  record one on a 401/403/429, so no expiry of hard_stop's marker can release the site.
* SF -- the fetch door (`fenced_urlopen` / `guarded_urlopen`) asks the same holds and robots.txt
  as `pf.get` before the first request and every redirect hop, and a refusal holds the site that
  refused. Exercised against a real local HTTP server; nothing leaves the machine.
"""
from __future__ import annotations

import http.server
import io
import json
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any, ClassVar

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402

DAY = 86400.0
T0 = 1_000_000.0
_ALLOW = b"User-agent: *\nDisallow:\n"
_CHALLENGE = b"<html><script>window._cf_chl_opt={}</script></html>"


class _Resp(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.status = 200
        self.url = ""
        self.headers = {"Content-Type": "text/html"}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _web(routes: dict[str, tuple[int, bytes]], sent: list[str]) -> Any:
    def opener(req: Any, timeout: float, context: Any = None) -> _Resp:
        sent.append(req.full_url)
        status, body = routes[req.full_url]
        if status == 200:
            return _Resp(body)
        raise urllib.error.HTTPError(req.full_url, status, "x", Message(), io.BytesIO(body))
    return opener


# ------------------------------------------------------------------------------------- MF1
@pytest.mark.parametrize("status,body", [(429, b""), (403, b""), (401, b""),
                                         (200, _CHALLENGE), (503, _CHALLENGE)])
def test_every_hold_still_stands_400_days_later(tmp_path: Path, status: int,
                                                body: bytes) -> None:
    state = tmp_path / "access.json"
    sent: list[str] = []
    web = _web({"https://a.test/robots.txt": (200, _ALLOW), "https://a.test/p": (status, body)},
               sent)
    acc = pf.HostAccess.load(state)
    acc._now = T0
    r = pf.get("https://a.test/p", opener=web, gate=None, sleep=lambda s: None, access=acc)
    assert not r.ok and r.verdict in ("METHOD_BLOCKED", "NEEDS_KEY")
    row = json.loads(state.read_text("utf-8"))["blocked"]["a.test"]
    assert row["key"] == "site:a.test" and row["released_by"] is None
    assert row["released_at"] is None and row["held_at"] == T0
    assert "recheck_after_ts" not in row and row["waits_for"] == "a person"
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    later = pf.HostAccess.load(state)
    later._now = T0 + 400 * DAY
    n = len(sent)
    assert later.hold("https://a.test/x") in ("METHOD_BLOCKED", "NEEDS_KEY")
    again = pf.get("https://a.test/p", opener=web, gate=None, sleep=lambda s: None, access=later)
    assert not again.ok and len(sent) == n, "a request went out under a 400-day-old hold"


def test_a_legacy_row_with_a_past_recheck_is_still_active(tmp_path: Path) -> None:
    state = tmp_path / "access.json"
    state.write_text(json.dumps({"blocked": {"a.test": {
        "verdict": "METHOD_BLOCKED", "status": 429, "recheck_after_ts": T0}}}), "utf-8")
    acc = pf.HostAccess.load(state)
    acc._now = T0 + 400 * DAY
    assert acc.hold("https://a.test/p") == "METHOD_BLOCKED"
    acc.save()
    assert "a.test" in json.loads(state.read_text("utf-8"))["blocked"]


def test_only_a_person_releases_a_hold_and_the_release_survives_a_running_process(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "access.json"
    monkeypatch.setattr(pf, "ACCESS_STATE", state)
    running = pf.HostAccess.load(state)
    running.block("https://www.a.test/p", 429)
    with pytest.raises(ValueError):
        pf.release("site:a.test", "  ", path=state)
    with pytest.raises(KeyError):
        pf.release("site:nothing.test", "principal", path=state)
    assert pf.main(["--release", "site:a.test", "--by", "principal"]) == 0
    row = json.loads(state.read_text("utf-8"))["blocked"]["a.test"]
    assert row["released_by"] == "principal" and row["released_at"]
    # A process that loaded the hold before the release saves later: the release is kept.
    running.save()
    assert json.loads(state.read_text("utf-8"))["blocked"]["a.test"]["released_by"] == "principal"
    fresh = pf.HostAccess.load(state)
    assert fresh.hold("https://a.test/p") == ""
    # A NEW refusal after the release is a new hold; the older release never clears it.
    fresh._now = float(row["released_at"]) + 10
    fresh.block("https://a.test/p", 403)
    assert pf.HostAccess.load(state).hold("https://a.test/q") == "METHOD_BLOCKED"


def test_missed_growth_counts_holds_until_a_person_releases_them(tmp_path: Path) -> None:
    from research import missed_growth as mg
    state = tmp_path / "access.json"
    acc = pf.HostAccess.load(state)
    acc.block("https://a.test/p", 429)
    acc.block("https://b.test/p", "WAF")
    assert mg.access_hold_lines(state, now=acc.now() + 400 * DAY)["n_held"] == 2
    pf.release("site:a.test", "principal", path=state)
    out = mg.access_hold_lines(state)
    assert [x["source"] for x in out["lines"]] == ["b.test"]
    assert out["lines"][0]["waits_for"] == "a person"


# ------------------------------------------------------------------------------------ gtrends
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
ROW = {"id": "gtrends", "terms": [["gold price", ["XAUUSD"]]]}


class _Trends:
    def __init__(self, refuse: int | None = None) -> None:
        self.refuse = refuse
        self.calls: list[str] = []

    def __call__(self, url: str, headers: Any = None, body: Any = None) -> bytes:
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nAllow: /\n"
        if self.refuse:
            err = urllib.error.HTTPError(url, self.refuse, "x", Message(), io.BytesIO(b""))
            raise fs.FetchError(f"http_{self.refuse}", url) from err
        fx = _DESK / "tests" / "fixtures" / "free_stack"
        return (fx / ("trends_explore.synthetic.txt" if "/explore" in url
                      else "trends_multiline.synthetic.txt")).read_bytes()


@pytest.mark.parametrize("code", [401, 403, 429])
def test_gtrends_refusal_is_held_in_the_access_record_too_and_one_release_frees_both(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    from desks.mt5.research import hard_stop as hs
    reg = tmp_path / "blocked_sources.json"
    monkeypatch.setattr(fs, "GTRENDS_REGISTER", reg)
    h = fs.fetch_gtrends(_Trends(refuse=code), ROW, {}, NOW)
    assert h.status in ("METHOD_BLOCKED", "NEEDS_KEY")
    assert pf.person_hold("https://trends.google.com/trends/api/explore") != ""
    # The hard_stop register vanishes (a reset box, a lost file -- not a person): the access
    # record still holds, 400 days on, and nothing is sent.
    reg.unlink()
    web = _Trends()
    h2 = fs.fetch_gtrends(web, ROW, {}, NOW + timedelta(days=400))
    assert web.calls == [] and not h2.obs
    # A person's named release of the mirrored hard_stop hold releases the access hold it covers.
    fs.fetch_gtrends(_Trends(refuse=code), ROW, {}, NOW)          # placed again in both
    hs.release(reg, "site:trends.google.com", "principal", now=NOW + timedelta(days=1))
    ok = fs.fetch_gtrends(_Trends(), ROW, {}, NOW + timedelta(days=2))
    assert ok.status == "OK" and pf.person_hold("https://trends.google.com/x") == ""


def test_the_side_channel_miner_consults_the_access_record(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import google_trends_miner as gtm
    calls: list[str] = []

    class _R:
        def __init__(self, code: int) -> None:
            self.status_code = code
            self.headers: dict[str, str] = {}
            self.text = ""

    def _get(url: str, headers: Any = None, timeout: float = 0) -> _R:
        calls.append(url)
        return _R(404 if url.endswith("/robots.txt") else 429)

    monkeypatch.setattr(gtm, "polite_requests_get", _get)
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    monkeypatch.setattr(gtm, "ROBOTS_STATE", tmp_path / "robots.json")
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", tmp_path / "reg.json")
    gtm.mine_google_trends(now=NOW)
    pages = [u for u in calls if not u.endswith("/robots.txt")]
    assert len(pages) == 1 and pf.person_hold("https://trends.google.com/x") == "METHOD_BLOCKED"
    (tmp_path / "block.json").unlink()                 # its own copy and the register gone:
    (tmp_path / "reg.json").unlink()                   # the access record still holds
    n = len(calls)
    assert gtm.mine_google_trends(now=NOW + timedelta(days=400)) == []
    assert len(calls) == n and gtm.LAST_PASS.get("skipped")


# ------------------------------------------------------------------------------ the fetch door
class _Site(http.server.BaseHTTPRequestHandler):
    """robots: /private disallowed. /r -> 302 /private; /x -> 302 to http://localhost/ok;
    /slow -> 429. Every request is recorded as (host header, path)."""

    seen: ClassVar[list[tuple[str, str]]] = []

    def log_message(self, *a: Any) -> None:
        pass

    def do_GET(self) -> None:
        host = (self.headers.get("Host") or "").split(":")[0]
        self.seen.append((host, self.path))
        port = self.server.server_address[1]
        if self.path == "/robots.txt":
            self._send(200, b"User-agent: *\nDisallow: /private\n")
        elif self.path == "/r":
            self._send(302, b"", {"Location": "/private"})
        elif self.path == "/x":
            self._send(302, b"", {"Location": f"http://localhost:{port}/ok"})
        elif self.path == "/slow":
            self._send(429, b"")
        else:
            self._send(200, b"ok")

    def _send(self, code: int, body: bytes, hdrs: dict[str, str] | None = None) -> None:
        self.send_response(code)
        for k, v in (hdrs or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def site() -> Iterator[int]:
    _Site.seen = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        yield int(srv.server_address[1])
    finally:
        srv.shutdown()
        srv.server_close()


def _paths(host: str = "127.0.0.1") -> list[str]:
    return [p for h, p in _Site.seen if h == host and p != "/robots.txt"]


@pytest.mark.parametrize("door", ["fenced", "guarded"])
def test_the_door_reads_robots_and_refuses_a_disallowed_path_before_sending(
        site: int, door: str) -> None:
    url = f"http://127.0.0.1:{site}/private"
    with pytest.raises(pf.AccessRefused) as exc:
        if door == "fenced":
            pf.fenced_urlopen(url, timeout=5)
        else:
            tf.guarded_urlopen(url, timeout=5)
    assert exc.value.platform == "robots_txt" and exc.value.verdict == "ROBOTS_DISALLOW"
    assert ("127.0.0.1", "/robots.txt") in _Site.seen and _paths() == []
    with pf.fenced_urlopen(f"http://127.0.0.1:{site}/ok", timeout=5) as fh:
        assert fh.read() == b"ok"


def test_a_redirect_hop_into_a_disallowed_path_is_refused_before_it_is_requested(
        site: int) -> None:
    with pytest.raises(pf.AccessRefused):
        pf.fenced_urlopen(f"http://127.0.0.1:{site}/r", timeout=5)
    assert _paths() == ["/r"], "the disallowed hop was requested"


def test_a_redirect_hop_into_a_held_site_is_refused_before_it_is_requested(site: int) -> None:
    pf.hold_site(f"http://localhost:{site}/anything", 403)
    with pytest.raises(pf.AccessRefused) as exc:
        pf.fenced_urlopen(f"http://127.0.0.1:{site}/x", timeout=5)
    assert exc.value.platform == "access_hold"
    assert [h for h, _ in _Site.seen if h == "localhost"] == [], "a held site was contacted"


def test_a_429_at_the_door_holds_the_refusing_site_and_nothing_more_is_sent(site: int) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        pf.fenced_urlopen(f"http://127.0.0.1:{site}/slow", timeout=5)
    assert exc.value.code == 429
    exc.value.close()
    assert pf.person_hold(f"http://127.0.0.1:{site}/ok") == "METHOD_BLOCKED"
    n = len(_Site.seen)
    with pytest.raises(pf.AccessRefused):
        pf.fenced_urlopen(f"http://127.0.0.1:{site}/ok", timeout=5)
    with pytest.raises(pf.AccessRefused):
        tf.guarded_urlopen(urllib.request.Request(f"http://127.0.0.1:{site}/ok"), timeout=5)
    assert len(_Site.seen) == n


def test_the_importers_reach_the_checks_through_the_door(site: int) -> None:
    """seed_miners and global_survivor_frontier fetch through the polite seam (`polite_urlopen`,
    robots-coverage 2026-10-14): a held site refuses both with nothing sent -- the seam names
    the hold as its PoliteRefused verdict."""
    import global_survivor_frontier as gsf
    import seed_miners as sm
    pf.hold_site(f"http://127.0.0.1:{site}/", 403)
    with pytest.raises(pf.PoliteRefused) as refused_sm:
        sm.fetch(f"http://127.0.0.1:{site}/ok", timeout=5)
    assert refused_sm.value.verdict == "METHOD_BLOCKED"
    with pytest.raises(pf.PoliteRefused) as refused:
        gsf._get_text(f"http://127.0.0.1:{site}/ok", 5)
    assert refused.value.verdict == "METHOD_BLOCKED"
    assert _Site.seen == []
