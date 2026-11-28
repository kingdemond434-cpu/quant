"""collector_lab: collector_author's job, with the model writing a spec and never code.

  * a model reply carrying code is not a collector: only a JSON spec is read, and fixed code
    fetches and parses;
  * a spec cannot leave the source's own domain or reach a private address, and robots holds;
  * a working spec becomes a PIT lake series and exogenous_conditioner cells stamped with the
    look-ahead guard, and refreshes on the next pass with no model call.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import collector_lab as cl  # noqa: E402
import llm_lab as lab  # noqa: E402

SRC = "https://data.example.org/api/v1/series"
UNI = {"EURUSD": "fx", "XAUUSD": "metal"}


def _public(host: str) -> list[str]:
    return ["93.184.216.34"]


def _body(n: int = 200) -> bytes:
    d0 = date(2025, 1, 1)
    obs = [{"date": (d0 + timedelta(days=i)).isoformat(), "v": str(100 + (i * 7919) % 97)}
           for i in range(n)]
    return json.dumps({"data": {"observations": obs}}).encode()


class _Reply:
    def __init__(self, text: str) -> None:
        self.text, self.provider, self.model = text, "openrouter_free", "qwen/qwen3:free"


SPEC = json.dumps({"url": SRC, "format": "json", "records": "data.observations", "date": "date",
                   "value": "v", "symbols": ["EURUSD", "NOPE"], "side_when_high": -1,
                   "mechanism": "test"})


@pytest.fixture()
def tmp_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("SPECS", "ATTEMPTS"):
        monkeypatch.setattr(cl, name, tmp_path / "collector" / f"{name.lower()}.json")
    monkeypatch.setattr(cl, "STATE_DIR", tmp_path / "collector")
    monkeypatch.setattr(cl, "HOST_STATE", tmp_path / "collector" / "hosts.json")
    monkeypatch.setattr(cl, "VINTAGES", tmp_path / "collector" / "vintages")
    monkeypatch.setattr(cl, "SERIES_DIR", tmp_path / "series")
    monkeypatch.setattr(cl, "DONATE_DIR", tmp_path / "donate")
    monkeypatch.setattr(lab, "MODEL_CUTOFFS", tmp_path / "cutoffs.json")
    monkeypatch.setattr(lab, "STATE_DIR", tmp_path / "lab_state")
    monkeypatch.setattr(lab, "_lane_ok", lambda s, f: True)
    monkeypatch.setattr(lab, "gauntlet_trims", lambda: True)
    feed = tmp_path / "feed.jsonl"
    feed.write_text(json.dumps({"name": "Example Index", "url": SRC, "reachable": True,
                                "duplicate": False}) + "\n")
    return tmp_path


def _get(calls: list[str]) -> Any:
    def g(url: str) -> tuple[int, bytes]:
        calls.append(url)
        return (404, b"") if url.endswith("robots.txt") else (200, _body())
    return g


def test_a_spec_becomes_a_wired_series_and_stamped_cells(tmp_lab: Path) -> None:
    calls: list[str] = []
    out = cl.run(chat=lambda *a, **k: _Reply(SPEC), get=_get(calls), resolve=_public,
                 feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["attempts"] == {"WORKS": 1} and out["cells_donated"] == 2
    csv_text = (tmp_lab / "series" / "col_example_index.csv").read_text()
    assert csv_text.startswith("available_time,") and csv_text.count("\n") == 201
    # Daily data: available two days after the observation date, never the same day.
    assert "2025-01-03T00:00:00+00:00" in csv_text.splitlines()[1]
    don = json.loads(next((tmp_lab / "donate").glob("*.json")).read_text())["discoveries"]
    assert {d["symbol"] for d in don} == {"EURUSD"}
    assert all(d["lookahead_guard"]["evidence_from"] and d["params"]["side_when_high"] == -1
               for d in don)
    # The next pass refreshes the spec with no model call and donates nothing twice.
    again = cl.run(chat=lambda *a, **k: pytest.fail("a working spec asked a model"),
                   get=_get(calls), resolve=_public, feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert again["series_refreshed"] == 1 and again["cells_donated"] == 0


def test_model_code_is_never_a_collector(tmp_lab: Path) -> None:
    code = '```python\ndef fetch():\n    __builtins__["__imp"+"ort__"]("o"+"s").popen("id")\n```'
    out = cl.run(chat=lambda *a, **k: _Reply(code), get=_get([]), resolve=_public,
                 feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["attempts"] == {"NO_SPEC": 1} and out["collectors"] == 0


@pytest.mark.parametrize("url,addrs,want", [
    ("https://evil.example.com/x", ["93.184.216.34"], "OFF_SITE"),
    ("https://data.example.org/x", ["169.254.169.254"], "REFUSED"),
    ("https://api.data.example.org/x", ["10.0.0.5"], "REFUSED"),
])
def test_a_spec_cannot_leave_the_site_or_reach_a_private_host(url: str, addrs: list[str],
                                                             want: str) -> None:
    def never(u: str) -> tuple[int, bytes]:
        raise AssertionError("fetched a refused URL")
    body, why = cl.fetch(url, SRC, get=never, resolve=lambda h: addrs)
    assert body == b"" and why.startswith(want)


def test_robots_and_gates_hold() -> None:
    def g(u: str) -> tuple[int, bytes]:
        return (200, b"User-agent: *\nDisallow: /api\n") if u.endswith("robots.txt") \
            else (200, _body())
    assert cl.fetch(SRC, SRC, get=g, resolve=_public)[1] == "ROBOTS_DISALLOW"
    assert cl.fetch(SRC, SRC, get=lambda u: (403, b""), resolve=_public)[1] == "GATED:HTTP_403"


def test_parser_reads_the_shapes_sources_use() -> None:
    lists = json.dumps([[1735689600000 + i * 86400000, i] for i in range(5)]).encode()
    assert cl.parse(lists, {"format": "json", "date": "0", "value": "1"})[0]["2025-01-01"] == 0
    mapping = json.dumps({"rates": {"2025-01-02": 1.5, "bad": 2}}).encode()
    assert cl.parse(mapping, {"format": "json", "records": "rates", "date": "@key",
                              "value": "@value"})[0] == {"2025-01-02": 1.5}
    text = b"Date,Close\n2025-01-03,\"1,234.5\"\n2025-01,7\n"
    assert cl.parse(text, {"format": "csv", "date": "Date", "value": "Close"})[0] == {
        "2025-01-01": 7.0, "2025-01-03": 1234.5}


def test_monthly_series_waits_two_periods() -> None:
    assert cl.availability_lag(["2025-01-01", "2025-02-01", "2025-03-01"]).days >= 56


# ============================================================================ audit M1-M6 on #332
def test_the_fetch_connects_to_the_address_it_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    """M1: no second DNS lookup. The socket is opened to the approved IP itself."""
    import socket
    dialled: list[tuple[str, int]] = []

    def fake(addr: tuple[str, int], timeout: float | None = None) -> Any:
        dialled.append(addr)
        raise OSError("stop here")
    monkeypatch.setattr(socket, "create_connection", fake)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("re-resolved"))
    body, why = cl.fetch("http://data.example.org/x", SRC, resolve=_public)
    assert why.startswith("UNREACHABLE") and dialled == [("93.184.216.34", 80)]


@pytest.mark.parametrize("url,ok", [
    ("https://data.example.org/a", True), ("https://api.data.example.org/a", True),
    ("https://example.org/a", False), ("https://evil.co.uk/a", False),
    ("https://victim.github.io/a", False),
])
def test_a_spec_stays_on_the_source_host(url: str, ok: bool) -> None:
    """M3: the same host or a host under it, never a sibling under a shared suffix."""
    assert cl.same_site(url, SRC) is ok
    assert cl.same_site("https://x.co.uk/a", "https://evil.co.uk/") is False
    assert cl.same_site("https://a.github.io/", "https://b.github.io/") is False
    assert cl.same_site("https://api.boj.or.jp/x", "https://www.boj.or.jp/") is True


def test_odd_ports_and_unavailable_robots_are_refused() -> None:
    def never(u: str) -> tuple[int, bytes]:
        raise AssertionError("fetched")
    assert cl.fetch("https://data.example.org:11434/x", SRC, get=never,
                    resolve=_public)[1].startswith("BAD_PORT")
    assert cl.fetch(SRC, SRC, get=lambda u: (503, b""), resolve=_public)[1] == \
        "ROBOTS_UNAVAILABLE"


@pytest.mark.parametrize("spec,body", [
    ({"format": "json", "date": "0", "value": "1"},
     json.dumps([[1735689600 * 10**9, 1.0]]).encode()),
    ({"format": "csv", "date": "d", "value": "v", "date_format": "%Y%Y("}, b"d,v\n2025,1\n"),
    ({"format": "json", "records": "a", "date": "d", "value": "v"},
     b"[" * 100000 + b"]" * 100000),
])
def test_a_hostile_payload_or_format_never_raises(spec: dict, body: bytes) -> None:
    """M4: one bad payload marks one spec broken; the parser itself never raises."""
    series, why = cl.parse(body, spec)
    assert isinstance(series, dict)
    if spec["format"] == "json" and spec["date"] == "0":
        assert series == {"2025-01-01": 1.0}


def test_a_crashing_spec_is_recorded_and_the_pass_goes_on(tmp_lab: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    cl.run(chat=lambda *a, **k: _Reply(SPEC), get=_get(calls), resolve=_public,
           feed=tmp_lab / "feed.jsonl", uni=UNI)
    monkeypatch.setattr(cl, "_parse", lambda b, s: (_ for _ in ()).throw(RecursionError()))
    out = cl.run(chat=lambda *a, **k: pytest.fail("asked"), get=_get(calls), resolve=_public,
                 feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["state"] == "STALE" and out["refresh"]["failed"] == 1


def test_the_state_never_reads_green_when_nothing_happened(tmp_lab: Path) -> None:
    """M5: a dark chain with sources owed is DARK; failing refreshes are STALE, not RAN."""
    def dark(*a: Any, **k: Any) -> Any:
        raise TimeoutError("chain")
    out = cl.run(chat=dark, get=_get([]), resolve=_public, feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["state"] == "DARK" and out["asked"] == 0
    assert cl.candidates(tmp_lab / "feed.jsonl", {}, []), "a dark chain charges no attempt"
    cl.run(chat=lambda *a, **k: _Reply(SPEC), get=_get([]), resolve=_public,
           feed=tmp_lab / "feed.jsonl", uni=UNI)
    (tmp_lab / "collector" / "hosts.json").unlink(missing_ok=True)
    out = cl.run(chat=lambda *a, **k: pytest.fail("asked"),
                 get=lambda u: (404, b"") if u.endswith("robots.txt") else (503, b""),
                 resolve=_public, feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["state"] == "STALE" and out["series_refreshed"] == 0


def test_transient_failures_never_drop_a_source(tmp_lab: Path) -> None:
    rows = [{"source": "Example Index", "status": "SOURCE_UNREADABLE",
             "detail": "UNREACHABLE:TimeoutError"}] * 5
    assert cl.candidates(tmp_lab / "feed.jsonl", {}, rows)
    rows = [{"source": "Example Index", "status": "NO_SPEC", "detail": "BAD_JSON"}] * 2
    assert not cl.candidates(tmp_lab / "feed.jsonl", {}, rows)


def test_a_reading_is_never_available_before_this_organ_saw_it() -> None:
    """M6: post-birth readings wait for first sight, revisions stay in the store; the birth history keeps
    D + lag as warm-up, and evidence starts the day after birth."""
    born = "2026-10-13T12:00:00+00:00"
    store: dict[str, list[list[Any]]] = {}
    cl.merge_vintages(store, {"2026-10-01": 1.0, "2026-10-12": 2.0}, born)
    later = "2026-10-20T09:00:00+00:00"
    assert cl.merge_vintages(store, {"2026-10-01": 1.0, "2026-10-12": 2.5,
                                     "2026-10-19": 3.0}, later) == 2
    rows = cl.series_rows(store, "col_x", 2.0, born)
    by = {(r["value"]): r for r in rows}
    assert by[1.0]["available_time"] == "2026-10-03T00:00:00+00:00"          # warm-up
    assert 2.5 not in by and store["2026-10-12"][1][0] == 2.5     # revision kept, not served
    assert by[3.0]["available_time"] >= later[:19]                           # max(D+lag, seen)
    assert by[2.0]["vintage_id"] == "v1"
    import llm_lab as _lab
    g = cl.guard_for("openrouter_free:qwen/qwen3:free", born)
    assert g["evidence_from"] >= "2026-10-14" and _lab


def test_nat64_and_mapped_loopback_are_private() -> None:
    from libs.ops.public_host import public_url
    for a in ("64:ff9b::7f00:1", "::ffff:127.0.0.1", "2002:7f00:1::1", "64:ff9b:1::1"):
        assert public_url("https://x.org/", resolve=lambda h, a=a: [a]), a
    assert public_url("https://x.org/", resolve=lambda h: ["64:ff9b::5db8:d822"]) == ""



# ============================================================================ audit v4 on #332
@pytest.mark.parametrize("mode", ["headers", "body"])
def test_a_trickling_server_cannot_hold_the_call(monkeypatch: pytest.MonkeyPatch,
                                                 mode: str) -> None:
    """MF1: the deadline is a watchdog on the socket, not a check between reads."""
    import socket
    import threading
    import time as _t
    monkeypatch.setattr(cl, "REQUEST_S", 1.0)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        c, _ = srv.accept()
        c.recv(4096)
        if mode == "body":
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
        else:
            c.sendall(b"HTTP/1.1 200 OK\r\n")
        while not stop.is_set():
            try:
                c.sendall(b"X" if mode == "body" else b"X-A: b\r\n")
            except OSError:
                break
            _t.sleep(0.05)
        c.close()
    th = threading.Thread(target=serve, daemon=True)
    th.start()
    t0 = _t.monotonic()
    with pytest.raises(TimeoutError):
        cl._pinned_get(["127.0.0.1"])(f"http://127.0.0.1:{port}/x")
    stop.set()
    srv.close()
    assert _t.monotonic() - t0 < 3.0


def test_blackholed_addresses_share_one_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """MF1 connect phase: N blackholed answers cost REQUEST_S in total, never N x 10s."""
    import socket
    import time as _t
    monkeypatch.setattr(cl, "REQUEST_S", 1.0)
    timeouts: list[float] = []

    def blackhole(addr: tuple[str, int], timeout: float | None = None) -> socket.socket:
        timeouts.append(float(timeout or 0))
        _t.sleep(float(timeout or 0))
        raise TimeoutError("timed out")
    monkeypatch.setattr(socket, "create_connection", blackhole)
    t0 = _t.monotonic()
    with pytest.raises(TimeoutError):
        cl._pinned_get(["93.184.216.1", "93.184.216.2", "93.184.216.3"])("http://x.org/a")
    assert _t.monotonic() - t0 < 2.0
    assert timeouts and all(t <= 1.0 for t in timeouts)


def test_all_transient_or_skipped_never_reads_green(tmp_lab: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """MF2: an outage on every owed source is DARK; working specs all skipped are STALE."""
    out = cl.run(chat=lambda *a, **k: pytest.fail("asked"), get=lambda u: (503, b""),
                 resolve=_public, feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["state"] == "DARK"
    (tmp_lab / "collector" / "hosts.json").unlink(missing_ok=True)
    cl.run(chat=lambda *a, **k: _Reply(SPEC), get=_get([]), resolve=_public,
           feed=tmp_lab / "feed.jsonl", uni=UNI)
    specs = json.loads(cl.SPECS.read_text())
    counts, outcome = cl.refresh(specs, get=_get([]), deadline=0.0, resolve=_public)
    assert outcome == {"refreshed": 0, "failed": 0, "skipped_budget": 1}
    monkeypatch.setattr(cl, "refresh", lambda *a, **k: (counts, outcome))
    out = cl.run(chat=lambda *a, **k: pytest.fail("asked"), get=_get([]), resolve=_public,
                 feed=tmp_lab / "feed.jsonl", uni=UNI)
    assert out["state"] == "STALE"


def test_www_never_climbs_to_a_shared_suffix() -> None:
    """S1."""
    for src, other in (("https://www.co.uk/", "https://evil.co.uk/"),
                       ("https://www.github.io/", "https://x.github.io/"),
                       ("https://www.s3.amazonaws.com/", "https://b.s3.amazonaws.com/")):
        assert not cl.same_site(other, src)
    assert cl.same_site("https://api.example.org/", "https://www.example.org/")


def test_a_revision_never_becomes_the_current_reading() -> None:
    """S5/S4: only the first reading of a date enters the series; the store is bounded."""
    born = "2026-10-13T12:00:00+00:00"
    store: dict[str, list[list[Any]]] = {}
    cl.merge_vintages(store, {"2026-10-01": 1.0, "2026-10-12": 2.0}, born)
    for i in range(30):
        cl.merge_vintages(store, {"2026-10-01": float(i % 2) + 5}, f"2026-10-{14 + i % 9}T00:00")
    assert len(store["2026-10-01"]) <= cl.MAX_VINTAGES and store["2026-10-01"][0][0] == 1.0
    rows = cl.series_rows(store, "col_x", 2.0, born)
    assert [r["value"] for r in rows] == [1.0, 2.0]


def test_collector_cells_reach_the_evidence_map(tmp_lab: Path) -> None:
    """S6: the start date is on disk before the donation, as for the main pass."""
    cl.run(chat=lambda *a, **k: _Reply(SPEC), get=_get([]), resolve=_public,
           feed=tmp_lab / "feed.jsonl", uni=UNI)
    ev = json.loads((tmp_lab / "lab_state" / "evidence_start.json").read_text())
    assert len(ev) == 2 and all(v["from"] > "2026-01-01" for v in ev.values())


def test_implausible_numbers_skip_a_reading_not_the_spec() -> None:
    """S7."""
    assert cl.parse_date(1e300) is None
    body = ('{"r": [{"d": "2025-01-01", "v": ' + "1" + "0" * 400 + '}, '
            '{"d": "2025-01-02", "v": 3}]}').encode()
    series, why = cl.parse(body, {"format": "json", "records": "r", "date": "d", "value": "v"})
    assert why == "" and series == {"2025-01-02": 3.0}
