"""Translingual diffusion lag: parsers on the codebook layout, the causal open-event table, the
snapshot buckets, and a walk that never skips or re-reads a slot."""
from __future__ import annotations

import io
import math
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import translingual_lag as tl  # noqa: E402

REGIONS = {"jp": {"fips": ["JA"], "langs": ["jpn"]},
           "ez": {"fips": ["GM", "FR"], "langs": ["deu", "fra"]}}
T0 = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)
M0 = int(T0.timestamp() // 60)


def _export(*rows: tuple[int, str]) -> bytes:
    out = []
    for eid, fips in rows:
        cols = [""] * 61
        cols[0], cols[53] = str(eid), fips
        out.append("\t".join(cols))
    return "\n".join(out).encode()


def _mentions(*rows: tuple[int, str]) -> bytes:
    out = []
    for eid, lang in rows:
        cols = [""] * 16
        cols[0] = str(eid)
        cols[14] = f"srclc:{lang};eng:GT-X 1.0" if lang else ""
        out.append("\t".join(cols))
    return "\n".join(out).encode()


def _zip(body: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x.CSV", body)
    return buf.getvalue()


def test_parsers_read_zip_and_plain_and_skip_junk():
    body = _export((7, "JA"), (8, "")) + b"\nnot\ta\trow"
    assert tl.parse_export(body) == {"7": "JA"} == tl.parse_export(_zip(body))
    m = tl.parse_mentions(_zip(_mentions((7, "jpn"), (7, "jpn"), (7, "fra"), (9, ""))))
    assert m == {"7": {"jpn": 2, "fra": 1}, "9": {"": 1}}
    assert tl.parse_mentions(b"PK-not-a-zip") == {} and tl.parse_export(None) == {}


def test_urls_name_the_four_files_of_a_slot():
    u = tl.urls("20261102001500")
    assert u["tl_mentions"].endswith("/20261102001500.translation.mentions.CSV.zip")
    assert len(set(u.values())) == 4 and all(v.startswith(tl.BASE) for v in u.values())


def test_local_lead_is_counted_until_english_arrives():
    st: dict = {}
    tl.step(st, M0, {"tl_export": _export((1, "JA")),
                     "tl_mentions": _mentions((1, "jpn"), (1, "jpn"), (1, "fra"))}, REGIONS)
    assert st["events"]["1"] == ["jp", M0, M0, None, 2]       # the French article is not local
    row = tl.snapshot(st, M0 + 30, REGIONS)["jp"]
    assert row["open_15_60"] == 1 and row["open_60_240"] == 0
    assert tl.snapshot(st, M0 + 90, REGIONS)["jp"]["open_60_240"] == 1
    c = tl.step(st, M0 + 120, {"mentions": _mentions((1, ""))}, REGIONS)
    assert c["matched"] == 1 and st["events"]["1"][3] == M0 + 120
    after = tl.snapshot(st, M0 + 135, REGIONS)["jp"]
    assert sum(after[f"open_{lo}_{hi}"] for lo, hi in tl.BUCKETS) == 0
    assert after["median_lag_24h"] == 120


def test_english_first_or_same_slot_is_not_a_lead():
    st: dict = {}
    tl.step(st, M0, {"export": _export((1, "GM"), (2, "FR")),
                     "mentions": _mentions((1, "")),
                     "tl_mentions": _mentions((1, "deu"), (1, "deu"))}, REGIONS)
    tl.step(st, M0 + 15, {"mentions": _mentions((2, ""))}, REGIONS)
    tl.step(st, M0 + 30, {"tl_mentions": _mentions((2, "fra"), (2, "fra"))}, REGIONS)
    row = tl.snapshot(st, M0 + 60, REGIONS)["ez"]
    assert row["covered_24h"] == 2 and all(row[f"open_{lo}_{hi}"] == 0 for lo, hi in tl.BUCKETS)
    assert math.isnan(row["median_lag_24h"]) and math.isnan(row["led_share_24h"])


def test_one_local_article_is_not_enough_and_old_events_leave():
    st: dict = {}
    tl.step(st, M0, {"tl_export": _export((1, "JA")), "tl_mentions": _mentions((1, "jpn"))},
            REGIONS)
    assert tl.snapshot(st, M0 + 30, REGIONS)["jp"]["open_15_60"] == 0
    tl.step(st, M0 + tl.HORIZON_MIN + 15, {}, REGIONS)
    assert st["events"] == {}


def test_an_event_outside_the_regions_or_untagged_counts_for_nobody():
    st: dict = {}
    c = tl.step(st, M0, {"tl_export": _export((1, "US"), (2, "JA")),
                         "tl_mentions": _mentions((1, "jpn"), (2, ""))}, REGIONS)
    assert set(st["events"]) == {"2"} and st["events"]["2"][2] is None and c["untagged"] == 1


def test_a_snapshot_is_the_same_whatever_arrives_later():
    st: dict = {}
    tl.step(st, M0, {"tl_export": _export((1, "JA")),
                     "tl_mentions": _mentions((1, "jpn"), (1, "jpn"))}, REGIONS)
    before = tl.snapshot(st, M0 + 30, REGIONS)
    tl.step(st, M0 + 45, {"mentions": _mentions((1, ""))}, REGIONS)
    assert before["jp"]["open_15_60"] == 1                    # the earlier reading stands


def _feed(present=lambda url: True):
    asked: list[str] = []

    def fetch(url: str):
        asked.append(url)
        if not present(url):
            return None
        return _export((1, "JA")) if url.endswith(".translation.export.CSV.zip") else b""
    return asked, fetch


def test_walk_starts_a_day_back_reads_in_order_and_never_twice():
    st: dict = {}
    asked, fetch = _feed()
    now = T0 + timedelta(hours=3, minutes=7)
    info = tl.advance(st, fetch, now, REGIONS, per_pass=3)
    assert info["slots"] == 3 and len(asked) == 12
    slots = [u.rsplit("/", 1)[1][:14] for u in asked[::4]]
    assert slots == sorted(slots) and len(set(slots)) == 3
    first = datetime.strptime(slots[0], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    assert now - first >= timedelta(minutes=tl.HORIZON_MIN)
    tl.advance(st, fetch, now, REGIONS, per_pass=3)
    again = [u.rsplit("/", 1)[1][:14] for u in asked[12::4]]
    assert not set(again) & set(slots) and min(again) > max(slots)


def test_no_slot_newer_than_the_publish_lag_is_asked():
    st: dict = {"cursor": M0, "run_start": M0 - 5000, "events": {}}
    asked, fetch = _feed()
    tl.advance(st, fetch, T0 + timedelta(minutes=50), REGIONS, per_pass=50)
    assert [u.rsplit("/", 1)[1][:14] for u in asked[::4]] == ["20261102000000", "20261102001500"]


def test_a_fetch_error_leaves_the_cursor_on_the_unread_slot():
    st: dict = {"cursor": M0, "run_start": M0 - 5000, "events": {}}
    n = {"calls": 0}

    def fetch(url: str):
        n["calls"] += 1
        if n["calls"] > 4:
            raise RuntimeError("refused")
        return b""
    with pytest.raises(RuntimeError):
        tl.advance(st, fetch, T0 + timedelta(hours=5), REGIONS)
    assert st["cursor"] == M0 + 15


def test_snapshots_wait_for_a_full_day_and_respect_the_gap_allowance():
    st: dict = {}
    _, fetch = _feed()
    now = T0 + timedelta(hours=3)
    info = tl.advance(st, fetch, now, REGIONS, per_pass=10_000)
    assert info["snapshots"] == 0 and "accruing" in info       # 00:00 came before a full day
    later = tl.advance(st, fetch, now + timedelta(hours=4), REGIONS, per_pass=10_000)
    assert later["snapshots"] == len(REGIONS)                  # the 06:00 snapshot
    assert {s["at"] for s in st["snaps"]} == {(T0 + timedelta(hours=6)).isoformat()}
    st2: dict = {}
    _, gappy = _feed(present=lambda url: False)
    tl.advance(st2, gappy, now, REGIONS, per_pass=10_000)
    out = tl.advance(st2, gappy, now + timedelta(hours=4), REGIONS, per_pass=10_000)
    assert out["snapshots"] == 0 and "skipped_for_gaps" in out and out["missing"] > 0


def test_a_walk_too_far_behind_restarts_and_says_so():
    st: dict = {"cursor": M0 - 10 * 1440, "run_start": M0 - 11 * 1440,
                "events": {"1": ["jp", M0 - 10 * 1440, None, None, 0]}}
    _, fetch = _feed(present=lambda url: False)
    info = tl.advance(st, fetch, T0, REGIONS, per_pass=1)
    assert "restarted_from" in info and st["events"] == {}
    assert st["run_start"] > M0 - 2 * 1440


def test_frame_rows_pick_one_region_and_hour_and_never_restate():
    snaps = [{"region": "jp", "at": "2026-11-02T06:00:00+00:00", "open_15_60": 3.0},
             {"region": "jp", "at": "2026-11-02T06:00:00+00:00", "open_15_60": 9.0},
             {"region": "jp", "at": "2026-11-02T12:00:00+00:00", "open_15_60": 5.0},
             {"region": "ez", "at": "2026-11-02T06:00:00+00:00", "open_15_60": 7.0},
             {"region": "jp", "at": "2026-11-01T06:00:00+00:00", "open_15_60": 1.0}]
    assert tl.frame_rows(snaps, "jp", 6) == [{"date": "2026-11-01", "open_15_60": 1.0},
                                             {"date": "2026-11-02", "open_15_60": 3.0}]
