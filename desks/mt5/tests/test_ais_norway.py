"""ais_norway: the AIVDM decoder, the tanker filter, the window means and the series door."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK.parent.parent))

import ais_norway as A  # noqa: E402


# ----------------------------------------------------------------- a synthetic AIVDM encoder
def _bits(v: int, n: int) -> str:
    return format(v & ((1 << n) - 1), f"0{n}b")


def _txt(s: str, n: int) -> str:
    out = ""
    for ch in s.ljust(n, "@")[:n]:
        c = ord(ch)
        out += _bits(c - 64 if c >= 64 else c, 6)
    return out


def _armour(bits: str) -> tuple[str, int]:
    fill = (-len(bits)) % 6
    bits += "0" * fill
    chars = []
    for i in range(0, len(bits), 6):
        v = int(bits[i:i + 6], 2)
        chars.append(chr(v + 48 if v < 40 else v + 56))
    return "".join(chars), fill


def position(mmsi: int, lat: float, lon: float, sog: float) -> str:
    b = (_bits(1, 6) + _bits(0, 2) + _bits(mmsi, 30) + _bits(0, 4) + _bits(0, 8)
         + _bits(round(sog * 10), 10) + _bits(0, 1) + _bits(round(lon * 600000), 28)
         + _bits(round(lat * 600000), 27) + _bits(0, 12) + _bits(511, 9) + _bits(0, 6)
         + _bits(0, 2) + _bits(0, 3) + _bits(0, 1) + _bits(0, 19))
    p, f = _armour(b)
    return f"\\s:2573345,c:1763000000*00\\!BSVDM,1,1,,A,{p},{f}*00"


def static(mmsi: int, ship_type: int, draught: float, name: str = "TANKER ONE") -> list[str]:
    b = (_bits(5, 6) + _bits(0, 2) + _bits(mmsi, 30) + _bits(0, 2) + _bits(9300000, 30)
         + _txt("LAXX7", 7) + _txt(name, 20) + _bits(ship_type, 8) + _bits(100, 9)
         + _bits(20, 9) + _bits(10, 6) + _bits(10, 6) + _bits(1, 4) + _bits(11, 4)
         + _bits(14, 5) + _bits(8, 5) + _bits(0, 6) + _bits(round(draught * 10), 8)
         + _txt("ROTTERDAM", 20) + _bits(0, 1) + _bits(0, 1))
    p, f = _armour(b)
    return [f"!AIVDM,2,1,3,B,{p[:60]},0*00", f"!AIVDM,2,2,3,B,{p[60:]},{f}*00"]


# ----------------------------------------------------------------- decoding
def test_position_round_trips_through_the_decoder() -> None:
    msg, ts = A.Assembler().feed(position(257123450, 70.68, 23.61, 0.2))
    assert ts == 1763000000
    assert msg is not None and msg["mmsi"] == 257123450
    assert msg["lat"] == pytest.approx(70.68, abs=1e-5)
    assert msg["lon"] == pytest.approx(23.61, abs=1e-5)
    assert msg["sog"] == pytest.approx(0.2)


def test_static_report_is_reassembled_from_two_fragments() -> None:
    asm = A.Assembler()
    first, second = static(257123450, 84, 11.4)
    assert asm.feed(first)[0] is None
    msg = asm.feed(second)[0]
    assert msg is not None and msg["type"] == 5
    assert msg["ship_type"] == 84 and msg["draught"] == pytest.approx(11.4)
    assert msg["name"] == "TANKER ONE" and msg["destination"] == "ROTTERDAM"


def test_garbage_lines_decode_to_nothing_and_never_raise() -> None:
    asm = A.Assembler()
    for ln in ("", "hello", "!AIVDM,1,1,,A,~~~~,0*00", "!AIVDM,1,1,,A,1,0*00"):
        assert asm.feed(ln)[0] is None


# ----------------------------------------------------------------- the window
def _window() -> list[str]:
    lines = [*static(1, 84, 11.0), *static(2, 70, 9.0), *static(3, 80, 14.0)]
    lines += [position(1, 70.68, 23.61, 0.1),            # LNG tanker at Melkoya
              position(2, 70.68, 23.62, 0.1),            # cargo ship: discarded
              position(3, 65.00, 6.00, 0.0)]             # tanker idling off-port
    return lines


def test_only_tankers_survive_and_zones_are_counted() -> None:
    reg: dict = {}
    w, tankers = A.collect(_window(), reg, datetime(2026, 11, 12, 10, tzinfo=UTC))
    assert w.statics == 3 and w.positions == 3
    assert sorted(t["mmsi"] for t in tankers) == [1, 3]
    c = A.summarise(tankers)
    assert c["hammerfest_lng_tankers"] == 1.0 and c["north_cape_tankers"] == 0.0
    assert c["stationary_offport_tankers"] == 1.0             # the Melkoya one is in port
    assert c["hammerfest_lng_mean_draught"] == pytest.approx(11.0)


def test_a_day_needs_min_windows_and_is_a_mean_never_a_sum() -> None:
    day = datetime(2026, 11, 12, tzinfo=UTC)
    ws = [{"started": (day + timedelta(hours=h)).isoformat(),
           "counts": {"karsto_tankers": float(h % 2)}} for h in range(A.MIN_WINDOWS)]
    out = A.daily(ws)
    assert out[day.date()]["karsto_tankers"] == pytest.approx(0.5)
    assert out[day.date()]["windows"] == A.MIN_WINDOWS
    assert A.daily(ws[:-1]) == {}                              # too thin: no row, not zero


def test_a_pass_writes_the_lake_and_only_complete_days_reach_the_series(tmp_path: Path,
                                                                       monkeypatch) -> None:
    pytest.importorskip("pyarrow")
    monkeypatch.setattr(A, "REPORT", tmp_path / "AIS_NORWAY.json")
    lake, series = tmp_path / "lake", tmp_path / "series.parquet"
    d0 = datetime(2026, 11, 12, tzinfo=UTC)
    for h in range(A.MIN_WINDOWS):
        rep = A.run(0, lake=lake, series=series, lines=_window(),
                    now=d0 + timedelta(hours=h))
        assert rep["status"] == "OK"
    assert rep["series_rows"] == 0                             # the day is not over yet
    rep = A.run(0, lake=lake, series=series, lines=[], now=d0 + timedelta(days=1, hours=1))
    assert rep["status"] == "EMPTY_WINDOW" and rep["series_rows"] == 1
    import pandas as pd
    df = pd.read_parquet(series)
    assert df.loc[pd.Timestamp("2026-11-12"), "hammerfest_lng_tankers"] == 1.0
    assert json.loads((lake / "registry.json").read_text())["1"]["ship_type"] == 84
    assert json.loads((tmp_path / "AIS_NORWAY.json").read_text())["licence"] == "NLOD 2.0"


def test_an_unreachable_stream_is_reported_with_its_missed_growth(tmp_path: Path,
                                                                  monkeypatch) -> None:
    monkeypatch.setattr(A, "REPORT", tmp_path / "r.json")

    def boom(_w: float) -> list[str]:
        raise ConnectionRefusedError

    monkeypatch.setattr(A, "stream_lines", boom)
    rep = A.run(1, lake=tmp_path / "lake", series=tmp_path / "s.parquet")
    assert rep["status"] == "UNREACHABLE" and rep["missed_growth"]
    assert not list((tmp_path / "lake").glob("windows_*"))


def test_the_alt_proxies_row_reads_the_series_and_is_terms_confirmed() -> None:
    import alt_proxies as P
    src = P.BY_ID["no_ais_tankers"]
    assert src.terms == "confirmed" and src.parse is None and src.reader is P.read_ais_norway
    assert not src.substitutes_for
    assert "NLOD" in P.TERMS_EVIDENCE["no_ais_tankers"]["terms_quote"]


def test_an_unreadable_series_is_never_overwritten_by_the_window(tmp_path: Path,
                                                                 monkeypatch) -> None:
    pytest.importorskip("pyarrow")
    monkeypatch.setattr(A, "REPORT", tmp_path / "r.json")
    lake, series = tmp_path / "lake", tmp_path / "series.parquet"
    series.write_bytes(b"not a parquet file")
    d0 = datetime(2026, 11, 12, tzinfo=UTC)
    for h in range(A.MIN_WINDOWS):
        A.run(0, lake=lake, series=series, lines=_window(), now=d0 + timedelta(hours=h))
    rep = A.run(0, lake=lake, series=series, lines=[], now=d0 + timedelta(days=1, hours=1))
    assert rep["series_rows"] == 0
    assert series.read_bytes() == b"not a parquet file"


def test_prune_keeps_undated_and_recent_files(tmp_path: Path) -> None:
    today = datetime(2026, 11, 14, tzinfo=UTC).date()
    old = tmp_path / "windows_2026-01-01.jsonl"
    new = tmp_path / "windows_2026-11-13.jsonl"
    odd = tmp_path / "windows_notadate-x.jsonl"
    for p in (old, new, odd):
        p.write_text("{}\n")
    A._prune(tmp_path, today)
    assert not old.exists() and new.exists() and odd.exists()
