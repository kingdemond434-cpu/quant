"""first_print_capture: a first print is recorded only when it is seen being born.

Offline: the robots read and the BLS POST are replaced, so these prove the bookkeeping
release_vintages depends on -- baseline first, firsts and revisions after, nothing older than the
baseline ever written, fail closed on robots and on an unreadable store.
"""
from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import first_print_capture as fpc


def _bls_body(values: dict[str, dict[tuple[int, int], float]]) -> bytes:
    series = [{"seriesID": sid,
               "data": [{"year": str(y), "period": f"M{m:02d}", "value": str(v)}
                        for (y, m), v in rows.items()]
                       + [{"year": "2026", "period": "M13", "value": "1"}]}
              for sid, rows in values.items()]
    return json.dumps({"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}).encode()


class _Net:
    def __init__(self, robots: bytes | Exception, bls: bytes | Exception) -> None:
        self.robots, self.bls, self.calls = robots, bls, []

    def __call__(self, req: urllib.request.Request) -> bytes:
        self.calls.append(req.full_url)
        out = self.robots if req.full_url.endswith("/robots.txt") else self.bls
        if isinstance(out, Exception):
            raise out
        return out


def _run(tmp: Path, net: _Net, day: str, key: str = "") -> dict:
    return fpc.run(now=datetime.fromisoformat(f"{day}T14:00:00+00:00"), folder=tmp / "fp",
                   state_path=tmp / "fp" / "_state.json", report=tmp / "rep.json", get=net,
                   key=key)


def _rows(tmp: Path, series: str) -> list[dict[str, str]]:
    with (tmp / "fp" / f"{series}.csv").open(newline="") as fh:
        return list(csv.DictReader(fh))


def test_baseline_then_first_prints_then_revisions(tmp_path) -> None:
    pay = fpc.BLS["PAYEMS"]
    net = _Net(b"User-agent: *\nAllow: /\n", _bls_body({pay: {(2026, 9): 100.0}}))
    doc = _run(tmp_path, net, "2026-10-03")
    assert doc["series"]["PAYEMS"]["status"] == "BASELINED"
    assert not (tmp_path / "fp" / "PAYEMS.csv").exists(), "a baseline value is never a print"
    net.bls = _bls_body({pay: {(2026, 9): 101.0, (2026, 10): 200.0}})
    doc = _run(tmp_path, net, "2026-11-07")
    assert doc["series"]["PAYEMS"]["new_first_prints"] == 1
    assert _rows(tmp_path, "PAYEMS") == [
        {"observation_date": "2026-10-01", "realtime_date": "2026-11-07", "value": "200.0"}]
    net.bls = _bls_body({pay: {(2026, 10): 205.0, (2026, 11): 300.0}})
    doc = _run(tmp_path, net, "2026-12-05")
    row = doc["series"]["PAYEMS"]
    assert (row["new_first_prints"], row["new_revisions"]) == (1, 1)
    assert [(r["observation_date"], r["realtime_date"], r["value"])
            for r in _rows(tmp_path, "PAYEMS")] == [
        ("2026-10-01", "2026-11-07", "200.0"), ("2026-10-01", "2026-12-05", "205.0"),
        ("2026-11-01", "2026-12-05", "300.0")]
    _run(tmp_path, net, "2026-12-06")
    assert len(_rows(tmp_path, "PAYEMS")) == 3, "an unchanged value appends nothing"


@pytest.mark.parametrize("robots", [urllib.error.HTTPError("u", 503, "x", {}, None),
                                    urllib.error.HTTPError("u", 403, "x", {}, None),
                                    b"<!doctype html><p>hi", OSError("down"),
                                    b"User-agent: *\nDisallow: /publicAPI/\n"])
def test_robots_fails_closed_and_bls_is_never_asked(tmp_path, robots) -> None:
    net = _Net(robots, AssertionError("BLS was asked after robots refused"))
    doc = _run(tmp_path, net, "2026-11-07")
    assert all(doc["series"][s]["status"] == "UNMEASURED" for s in fpc.BLS)
    assert all(u.endswith("/robots.txt") for u in net.calls)


def test_a_robots_404_means_no_rules(tmp_path) -> None:
    net = _Net(urllib.error.HTTPError("u", 404, "x", {}, None),
               _bls_body({fpc.BLS["UNRATE"]: {(2026, 9): 4.1}}))
    doc = _run(tmp_path, net, "2026-11-07")
    assert doc["series"]["UNRATE"]["status"] == "BASELINED"


def test_an_unreadable_store_is_never_overwritten(tmp_path) -> None:
    pay = fpc.BLS["PAYEMS"]
    net = _Net(b"", _bls_body({pay: {(2026, 9): 1.0}}))
    _run(tmp_path, net, "2026-10-03")
    bad = tmp_path / "fp" / "PAYEMS.csv"
    bad.write_text("not,the,header\n1,2,3\n", "utf-8")
    net.bls = _bls_body({pay: {(2026, 10): 2.0}})
    doc = _run(tmp_path, net, "2026-11-07")
    assert doc["series"]["PAYEMS"]["status"] == "UNMEASURED"
    assert bad.read_text("utf-8") == "not,the,header\n1,2,3\n"


def test_bls_refusal_and_bad_status_are_unmeasured(tmp_path) -> None:
    net = _Net(b"", urllib.error.HTTPError("u", 429, "x", {}, None))
    doc = _run(tmp_path, net, "2026-11-07")
    assert "hard stop" in doc["series"]["CPIAUCSL"]["why"]
    net.bls = json.dumps({"status": "REQUEST_NOT_PROCESSED", "message": ["limit"]}).encode()
    doc = _run(tmp_path, net, "2026-11-07")
    assert doc["series"]["CPIAUCSL"]["status"] == "UNMEASURED"


def test_the_key_rides_only_in_the_body_and_never_in_the_report(tmp_path) -> None:
    sent: list[bytes] = []
    net = _Net(b"", _bls_body({}))

    def get(req: urllib.request.Request) -> bytes:
        if not req.full_url.endswith("robots.txt"):
            sent.append(req.data or b"")
            assert req.get_header("User-agent") == fpc.UA
        return net(req)

    fpc.run(now=datetime(2026, 11, 7, tzinfo=UTC), folder=tmp_path / "fp",
            state_path=tmp_path / "s.json", report=tmp_path / "rep.json", get=get,
            key="sekret-value")
    assert b"sekret-value" in sent[0]
    assert "sekret-value" not in (tmp_path / "rep.json").read_text("utf-8")
    assert json.loads((tmp_path / "rep.json").read_text("utf-8"))["key_present"] is True


def test_unbuilt_publishers_are_named_gaps_with_missed_growth(tmp_path) -> None:
    doc = _run(tmp_path, _Net(b"", _bls_body({})), "2026-11-07")
    for pub, owned in fpc.NOT_BUILT.items():
        for s in owned:
            row = doc["series"][s]
            assert row["publisher"] == pub and row["status"] == "UNMEASURED"
            assert "missed_growth" in row["missed_growth"]


def test_the_bls_table_matches_release_vintages_where_it_exists() -> None:
    rv = pytest.importorskip("macro.release_vintages")
    want = {s: sid for s, (pub, sid) in rv.PRIMARY.items() if pub == "bls"}
    assert want == fpc.BLS
    built = set(fpc.BLS) | {s for v in fpc.NOT_BUILT.values() for s in v}
    assert built == set(rv.PRIMARY)


def test_the_leg_is_on_the_hourly_clock() -> None:
    src = (Path(fpc.__file__).parent / "hourly_cycle.py").read_text("utf-8")
    assert '"research/first_print_capture.py", "--once"' in src


def _redirecting_server(target: str):
    """A local https-less 302 server: every request is answered with a Location to `target`."""
    import http.server
    import threading

    hits: list[str] = []

    class H(http.server.BaseHTTPRequestHandler):
        def _go(self) -> None:
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()

        do_GET = do_POST = _go

        def log_message(self, *_a) -> None:
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


@pytest.mark.parametrize("method_body", [None, b"{}"])
def test_a_cross_host_redirect_is_never_followed(monkeypatch, method_body) -> None:
    """Auditor MF2: a 30x to another host sends no second request -- it is an HTTPError."""
    srv, hits = _redirecting_server("https://elsewhere.example/steal")
    sent: list[str] = []
    real = urllib.request.HTTPSHandler.https_open
    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open",
                        lambda self, req: sent.append(req.full_url) or real(self, req))
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/publicAPI/v2/timeseries/data/"
        req = urllib.request.Request(url, data=method_body, headers={"User-Agent": fpc.UA})
        with pytest.raises(urllib.error.HTTPError) as exc:
            fpc._http(req)
        assert exc.value.code == 302
        exc.value.close()
        assert len(hits) == 1 and sent == [], "the redirect target was contacted"
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_same_host_https_get_redirect_is_followed() -> None:
    h = fpc.PinnedHostRedirect()
    req = urllib.request.Request("https://api.bls.gov/robots.txt")
    assert h.redirect_request(req, None, 301, "x", {}, "https://api.bls.gov/robots.txt") is not None
    post = urllib.request.Request("https://api.bls.gov/a", data=b"{}")
    assert h.redirect_request(post, None, 307, "x", {}, "https://api.bls.gov/b") is None
    assert h.redirect_request(req, None, 301, "x", {}, "http://api.bls.gov/robots.txt") is None


def test_bls_free_text_never_reaches_the_report(tmp_path) -> None:
    net = _Net(b"", json.dumps({"status": "REQUEST_NOT_PROCESSED",
                                "message": ["call me at https://evil.example"]}).encode())
    _run(tmp_path, net, "2026-11-07")
    text = (tmp_path / "rep.json").read_text("utf-8")
    assert "evil.example" not in text and "REQUEST_NOT_PROCESSED" in text
