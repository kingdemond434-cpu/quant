"""free_stack's Google Trends fetcher honours the hard stop and the PIT law (2026-10-14).

* The hard stop itself (person-held, `research/hard_stop.py`) is Breadth's and is pinned by
  `test_free_stack_gtrends_stop.py` / `test_google_trends_reading.py`; the backoff-marker tests
  that lived here were retired with the 1h..7d ladder (audit GD_LANDING_TRAIN_6eb7a91b4).
* The request carries the desk's honest User-Agent.
* Every Trends point is stamped no earlier than the fetch that returned it -- never back-dated to
  its own period on the first fetch -- and the trailing isPartial point is never counted.
No socket is opened.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import polite_fetch as pf  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "free_stack"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
ROW = {"id": "gtrends", "terms": [["gold price", ["XAUUSD"]], ["recession", ["US500"]]]}


@pytest.fixture(autouse=True)
def _register_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hard stop's register is the box's file: a test never writes it."""
    monkeypatch.setattr(fs, "GTRENDS_REGISTER", tmp_path / "blocked_sources.json")


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


class _Trends:
    """Answers explore/multiline from the fixtures; `refuse` = (call number, status)."""

    def __init__(self, refuse: tuple[int, int] | None = None) -> None:
        self.refuse = refuse
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url: str, headers=None, body=None) -> bytes:
        self.calls.append((url, str((headers or {}).get("User-Agent"))))
        if self.refuse and len(self.calls) == self.refuse[0]:
            hdrs = Message()
            hdrs["Retry-After"] = "120"
            err = urllib.error.HTTPError(url, self.refuse[1], "refused", hdrs, io.BytesIO(b""))
            raise fs.FetchError(f"http_{self.refuse[1]}", url) from err
        return _fx("trends_explore.synthetic.txt" if "/explore" in url
                   else "trends_multiline.synthetic.txt")


def test_gtrends_sends_the_desk_ua(tmp_path: Path) -> None:
    web = _Trends()
    h = fs.fetch_gtrends(web, ROW, {}, NOW, block_state=tmp_path / "b.json",
                         register=tmp_path / "reg.json")
    assert h.status == "OK" and web.calls
    assert all(ua == pf.DESK_UA for _, ua in web.calls)
    assert fs.UA == pf.DESK_UA and not pf.looks_like_browser(fs.UA)






def test_gtrends_history_is_stamped_at_fetch_time_never_backfilled(tmp_path: Path) -> None:
    from free_stack_hunter import load_obs, merge_obs
    h = fs.fetch_gtrends(_Trends(), {"id": "gtrends", "terms": [["gold price", ["XAUUSD"]]]},
                         {}, NOW, block_state=tmp_path / "b.json", register=tmp_path / "r.json")
    assert h.obs and all(o[fs.STAMP_AT_FETCH] for o in h.obs)
    p = tmp_path / "gtrends.jsonl"
    merge_obs(p, h.obs, now=NOW, lag_h=24)          # the source's FIRST fetch
    rows = load_obs(p)
    assert rows and all(r["vintage"] != "backfill" for r in rows)
    assert all(r["available_time"] >= NOW.isoformat()[:19] for r in rows), \
        "a Trends point older than the first fetch was stamped at its own date"


def test_the_trailing_partial_point_is_never_counted_as_final(tmp_path: Path) -> None:
    raw = json.loads(_fx("trends_multiline.synthetic.txt").decode().split("\n", 1)[1])
    partial = [p for p in raw["default"]["timelineData"] if p["isPartial"]]
    assert partial, "fixture lost its partial point"
    partial_day = datetime.fromtimestamp(int(partial[-1]["time"]), tz=UTC).date().isoformat()
    h = fs.fetch_gtrends(_Trends(), {"id": "gtrends", "terms": [["gold price", ["XAUUSD"]]]},
                         {}, NOW, block_state=tmp_path / "b.json", register=tmp_path / "r.json")
    assert partial_day not in {o["period_end"] for o in h.obs}
    assert partial_day not in {r["day"] for r in h.raw}


