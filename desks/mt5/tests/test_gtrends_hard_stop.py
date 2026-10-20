"""free_stack's Google Trends fetcher honours the hard stop and the PIT law (2026-10-14).

* The shared marker (`research/hard_stop.py`, the file `google_trends_miner` also writes) is
  checked before every request; a 401/403/429 writes it, records `google_trends` in the blocked
  register, sets the status and ends the pass with nothing from the refused term kept.
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
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import ClassVar

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


def test_a_429_writes_the_marker_records_the_block_and_stops(tmp_path: Path) -> None:
    state, reg = tmp_path / "google_trends_block.json", tmp_path / "blocked_sources.json"
    web = _Trends(refuse=(4, 429))          # term 1 answered; term 2's multiline refused
    h = fs.fetch_gtrends(web, ROW, {}, NOW, block_state=state, register=reg)
    assert len(web.calls) == 4, "a request was sent after the refusal"
    assert h.status == "METHOD_BLOCKED"
    assert {o["key"] for o in h.obs} == {"gt_gold_price"}, "the refused term leaked data"
    marker = json.loads(state.read_text("utf-8"))
    assert marker["http_status"] == 429 and marker["url_class"] == "widgetdata"
    assert marker["backoff_source"] == "retry_after"
    entry = json.loads(reg.read_text("utf-8"))["sources"]["google_trends"]
    assert entry["diagnosis"] == "METHOD_BLOCKED"
    # The next pass, inside the backoff, sends nothing at all.
    again = _Trends()
    h2 = fs.fetch_gtrends(again, ROW, {}, NOW + timedelta(seconds=60), block_state=state,
                          register=reg)
    assert again.calls == [] and h2.status == "METHOD_BLOCKED" and not h2.obs


def test_a_401_is_needs_key_and_an_active_marker_from_the_miner_is_honoured(
        tmp_path: Path) -> None:
    state, reg = tmp_path / "b.json", tmp_path / "r.json"
    h = fs.fetch_gtrends(_Trends(refuse=(1, 401)), ROW, {}, NOW, block_state=state, register=reg)
    assert h.status == "NEEDS_KEY" and not h.obs
    hs = fs._hard_stop()
    state.write_text(json.dumps(hs.block_marker(403, "explore", {}, NOW, None)), "utf-8")
    web = _Trends()
    fs.fetch_gtrends(web, ROW, {}, NOW + timedelta(minutes=5), block_state=state, register=reg)
    assert web.calls == []


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


def test_the_side_channel_miner_is_honest_and_stops_on_429(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """side_channels/google_trends_miner: the desk's UA, and a 429 ends the pass with the shared
    marker written -- it is not swallowed while the loop carries on."""
    side = str(_DESK / "side_channels")
    if side not in sys.path:
        sys.path.insert(0, side)
    import google_trends_miner as gtm
    assert gtm.HEADERS["User-Agent"] == pf.DESK_UA
    calls: list[str] = []

    class _R:
        status_code = 429
        headers: ClassVar[dict[str, str]] = {"Retry-After": "600"}
        text = ""

    def _get(url: str, headers: dict[str, str] | None = None, timeout: float = 0) -> _R:
        calls.append(str((headers or {}).get("User-Agent")))
        return _R()

    monkeypatch.setattr(gtm, "polite_requests_get", _get)
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", tmp_path / "reg.json")
    assert gtm.mine_google_trends(now=NOW) == []
    assert calls == [pf.DESK_UA]                          # one request, then the stop
    assert gtm.LAST_PASS["status"] == "METHOD_BLOCKED"
    assert json.loads((tmp_path / "block.json").read_text("utf-8"))["http_status"] == 429
    assert gtm.mine_google_trends(now=NOW + timedelta(seconds=60)) == []
    assert calls == [pf.DESK_UA]                          # the next pass sends nothing
