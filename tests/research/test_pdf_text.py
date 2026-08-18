"""libs/research/pdf_text.py -- the R0358 / GAP #70 stdlib extractor, pinned.

The capability exists to verify NUMBERS in academic PDFs instead of trusting search summaries
(the first hand-extraction corrected three recorded numbers). These tests build tiny synthetic
PDFs -- a FlateDecode stream, a TJ kerning array, escapes, an undecodable filter -- and pin
that text round-trips, that skipped streams are COUNTED (L1.60), and that an unreadable file
raises rather than reading as empty (L1.28a).
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from libs.research import pdf_text


def _pdf_with_stream(head: bytes, body: bytes) -> bytes:
    return (b"%PDF-1.4\n1 0 obj\n<<" + head + b">>\nstream\n" + body
            + b"\nendstream\nendobj\n%%EOF\n")


def test_flate_stream_roundtrips() -> None:
    content = b"BT /F1 12 Tf (Sharpe 1.23 net of costs) Tj ET"
    data = _pdf_with_stream(b" /Length 99 /Filter /FlateDecode ", zlib.compress(content))
    text, stats = pdf_text.extract(data)
    assert "Sharpe 1.23 net of costs" in text
    assert stats == {"streams": 1, "decoded": 1, "failed": 0}


def test_tj_array_and_escapes() -> None:
    content = (b"BT [(t-stat \\(net\\): 2.7) -250 (8)] TJ T* "
               b"(65\\045 fail at t>1.96) Tj ET")          # \045 = %
    data = _pdf_with_stream(b" /Length 99 /Filter /FlateDecode ", zlib.compress(content))
    text, _ = pdf_text.extract(data)
    assert "t-stat (net): 2.7" in text
    assert "8" in text
    assert "65% fail at t>1.96" in text


def test_plain_stream_and_newline_operators() -> None:
    content = b"BT (row one) Tj T* (row two) Tj ET"
    data = _pdf_with_stream(b" /Length 34 ", content)
    text, stats = pdf_text.extract(data)
    assert "row one" in text and "row two" in text
    assert text.index("row one") < text.index("row two")
    assert stats["decoded"] == 1


def test_unsupported_filter_is_counted_not_silently_dropped() -> None:
    good = _pdf_with_stream(b" /Filter /FlateDecode ", zlib.compress(b"(kept) Tj"))
    bad = _pdf_with_stream(b" /Filter /LZWDecode ", b"\x00\x01garbage")
    text, stats = pdf_text.extract(good + bad)
    assert "kept" in text
    assert stats == {"streams": 2, "decoded": 1, "failed": 1}


def test_unreadable_file_raises_never_reads_empty(tmp_path: Path) -> None:
    p = tmp_path / "enc.pdf"
    p.write_bytes(_pdf_with_stream(b" /Filter /LZWDecode ", b"\x00opaque"))
    with pytest.raises(ValueError, match="unreadable, not empty"):
        pdf_text.extract_text(p)
    notpdf = tmp_path / "x.pdf"
    notpdf.write_bytes(b"<html>not a pdf</html>")
    with pytest.raises(ValueError, match="not a PDF"):
        pdf_text.extract_text(notpdf)


def test_extract_text_happy_path(tmp_path: Path) -> None:
    p = tmp_path / "ok.pdf"
    p.write_bytes(_pdf_with_stream(b" /Filter /FlateDecode ",
                                   zlib.compress(b"(alpha decay 4.5bps/mo) Tj")))
    assert "alpha decay 4.5bps/mo" in pdf_text.extract_text(p)


def test_cli_main_prints_text_and_stats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import zlib as _z

    p = tmp_path / "ok.pdf"
    p.write_bytes(_pdf_with_stream(b" /Filter /FlateDecode ",
                                   _z.compress(b"(from the cli) Tj")))
    assert pdf_text.main([str(p)]) == 0
    out = capsys.readouterr()
    assert "from the cli" in out.out
    assert "decoded=1" in out.err
    assert pdf_text.main([]) == 2
