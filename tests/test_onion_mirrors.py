"""The onion allowlist fetcher, with no network and no Tor: the gates (NEEDS_TOR, awaiting the
auditor's ruling), the scope validator (markets / forums / leaks refused), the SOCKS5h handshake
against a fake proxy, the refusal of any non-onion host, and that a redirect is never followed.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from research import onion_mirrors as O  # noqa: E402

ONION = "a" * 56 + ".onion"
ALLOWED = frozenset({"news", "public_institution", "open_data_project"})


def _entry(**kw: Any) -> dict[str, Any]:
    e = {"id": "x", "publisher": "Example Public Broadcaster", "category": "news",
         "url": f"http://{ONION}/", "announced_at": "https://example.org/onion",
         "why": "public news mirror"}
    e.update(kw)
    return e


def test_committed_allowlist_validates_and_cites_publisher_pages() -> None:
    doc = O.load_allowlist()
    allowed = frozenset(doc["allowed_categories"])
    assert doc["entries"]
    for e in doc["entries"]:
        assert O.validate(e, allowed) == "", e["id"]
        assert e["announced_at"].startswith("https://")


@pytest.mark.parametrize("bad, why", [
    ({"url": "https://example.org/"}, "not a v3"),
    ({"url": "http://abcdefghijklmnop.onion/"}, "not a v3"),
    ({"url": f"http://{ONION}/?q=1"}, "query"),
    ({"category": "market"}, "category"),
    ({"why": "a carding forum mirror"}, "out of scope"),
    ({"publisher": "Some Leaks Site"}, "out of scope"),
    ({"why": "ransomware group blog"}, "out of scope"),
    ({"announced_at": f"http://{ONION}/"}, "announced_at"),
])
def test_validator_refuses_out_of_scope_entries(bad: dict[str, Any], why: str) -> None:
    assert why in O.validate(_entry(**bad), ALLOWED)


def _allow(tmp: Path, entries: list[dict[str, Any]]) -> Path:
    p = tmp / "allow.json"
    p.write_text(json.dumps({"allowed_categories": sorted(ALLOWED), "entries": entries}), "utf-8")
    return p


def test_absent_socks_is_needs_tor_for_every_row(tmp_path: Path) -> None:
    rep = O.run(environ={}, allowlist=_allow(tmp_path, [_entry(), _entry(id="y")]),
                ruling=tmp_path / "none.json", write_report=False)
    assert rep["gate"] == "UNMEASURED:NEEDS_TOR"
    assert [r["status"] for r in rep["rows"]] == ["UNMEASURED:NEEDS_TOR"] * 2
    assert rep["n_measured"] == 0


def test_socks_without_ruling_stays_off(tmp_path: Path) -> None:
    rep = O.run(environ={O.SOCKS_ENV: "127.0.0.1:9050"},
                allowlist=_allow(tmp_path, [_entry()]), ruling=tmp_path / "none.json",
                write_report=False)
    assert rep["rows"][0]["status"] == "UNMEASURED:AWAITING_AUDITOR_RULING"
    half = tmp_path / "half.json"
    half.write_text(json.dumps({"allowed": True}), "utf-8")        # no named auditor
    assert O.egress_ruling(half)[0] is False


def test_refused_entries_are_reported_not_fetched(tmp_path: Path) -> None:
    rep = O.run(environ={}, allowlist=_allow(tmp_path, [_entry(category="forum")]),
                ruling=tmp_path / "none.json", write_report=False)
    assert rep["rows"][0]["status"] == "REFUSED" and rep["n_refused"] == 1


def test_socks5_connect_refuses_non_onion_before_any_socket() -> None:
    with pytest.raises(OSError, match="non-onion"):
        O.socks5_connect(("127.0.0.1", 1), "example.org", 80, 1.0)


def _fake_socks() -> tuple[tuple[str, int], dict[str, Any], threading.Thread]:
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    seen: dict[str, Any] = {}

    def serve() -> None:
        c, _ = srv.accept()
        with c:
            seen["greet"] = c.recv(3)
            c.sendall(b"\x05\x00")
            head = c.recv(5)
            name = c.recv(head[4])
            port = c.recv(2)
            seen["atyp"], seen["name"], seen["port"] = head[3], name.decode(), port
            c.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
        srv.close()
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return srv.getsockname(), seen, t


def test_socks5_handshake_lets_the_proxy_resolve_the_name() -> None:
    addr, seen, t = _fake_socks()
    s = O.socks5_connect(addr, ONION, 80, 5.0)
    s.close()
    t.join(5)
    assert seen["greet"] == b"\x05\x01\x00"
    assert seen["atyp"] == 3 and seen["name"] == ONION and seen["port"] == b"\x00\x50"


def test_open_gate_fetches_listed_url_only_and_never_follows_redirects(tmp_path: Path,
                                                                       monkeypatch) -> None:
    ruling = tmp_path / "ruling.json"
    ruling.write_text(json.dumps({"allowed": True, "ruled_by": "auditor",
                                  "ruled_at": "2026-10-30"}), "utf-8")
    monkeypatch.setattr(O, "RAW", tmp_path / "raw")
    asked: list[str] = []

    class _Resp:
        status = 200
        def __init__(self, url: str) -> None:
            self.url = url
            self.headers = {"Content-Type": "text/html"}

        def read(self, n: int = -1) -> bytes:
            return b"<html><title>Mirror</title></html>"

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

    def opener(req: Any, timeout: float | None = None, context: Any = None) -> Any:
        url = req.full_url
        asked.append(url)
        if url.endswith("/robots.txt"):
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)  # type: ignore[arg-type]
        if "moved" in url:
            raise urllib.error.HTTPError(url, 302, "Found",
                                         {"Location": "http://elsewhere.onion/"},  # type: ignore[arg-type]
                                         None)
        return _Resp(url)

    from libs.data import polite_fetch as pf
    acc = pf.HostAccess(tmp_path / "access.json")
    monkeypatch.setattr(pf, "default_access", lambda: acc)
    entries = [_entry(id="ok"), _entry(id="moved", url=f"http://{'b' * 56}.onion/moved")]
    rep = O.run(environ={O.SOCKS_ENV: "127.0.0.1:9050"}, allowlist=_allow(tmp_path, entries),
                ruling=ruling, opener=opener, write_report=False)
    by = {r["id"]: r for r in rep["rows"]}
    assert by["ok"]["status"] == "MEASURED" and by["ok"]["title"] == "Mirror"
    assert by["moved"]["status"] == "REDIRECT_NOT_FOLLOWED"
    assert not any("elsewhere" in u for u in asked)
    assert {u.split("/")[2] for u in asked} <= {ONION, "b" * 56 + ".onion"}
