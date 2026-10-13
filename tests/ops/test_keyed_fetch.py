"""A keyed request never follows a redirect to another host (audit #211, 2026-10-07)."""
from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from libs.ops.keyed_fetch import CrossHostRedirect, open_keyed

SEEN: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        SEEN.append(f"{self.headers.get('Host')}{self.path}")
        port = self.server.server_address[1]
        if self.path.startswith("/same"):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/final?api_key=SECRET")
        elif self.path.startswith("/away"):
            # localhost and 127.0.0.1 are different hosts to the guard, same server here
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{port}/stolen")
        else:
            self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def server() -> Iterator[int]:
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    SEEN.clear()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_a_same_host_redirect_is_followed(server: int) -> None:
    with open_keyed(f"http://127.0.0.1:{server}/same?api_key=SECRET", timeout=5) as r:
        assert r.read() == b"ok"
    assert any("/final" in s for s in SEEN)


def test_a_cross_host_redirect_is_refused_and_nothing_reaches_the_new_host(server: int) -> None:
    with pytest.raises(CrossHostRedirect):
        open_keyed(f"http://127.0.0.1:{server}/away?api_key=SECRET", timeout=5)
    assert not any("/stolen" in s for s in SEEN)


def test_the_fred_collector_fetches_through_the_guard() -> None:
    src = (Path(__file__).resolve().parents[2] / "scripts" / "collect_fred_macro.py").read_text(
        "utf-8")
    assert "open_keyed(req" in src and "urllib.request.urlopen(" not in src
