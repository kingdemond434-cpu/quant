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
    monkeypatch.setattr(cl, "SERIES_DIR", tmp_path / "series")
    monkeypatch.setattr(cl, "DONATE_DIR", tmp_path / "donate")
    monkeypatch.setattr(lab, "MODEL_CUTOFFS", tmp_path / "cutoffs.json")
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
    ("https://api.example.org/x", ["10.0.0.5"], "REFUSED"),
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
