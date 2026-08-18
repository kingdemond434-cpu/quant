"""Pure-stdlib PDF text extraction -- R0358 / GAP #70, the litminer's un-blocker.

Two consecutive literature runs inherited "no PDF tooling on this box and the freeze forbids
installs" and left five findings at ABSTRACT level. The premise was true and the conclusion
false: academic PDF text lives overwhelmingly in FlateDecode content streams, the stdlib ships
zlib, and the first paper hand-extracted this way (Hou-Xue-Zhang) corrected THREE numbers the
desk had recorded from a search summary. This module lands that capability as code.

WHAT IT IS FOR: verifying NUMBERS and CLAIMS in academic PDFs (t-stats, failure rates, table
values) instead of trusting search summaries -- the exact class of error it already caught.
WebFetch on arXiv /pdf/ SILENTLY FABRICATES numbers (litminer run 7, desk lesson); this reads
the actual bytes.

HONEST LIMITS, so nobody trusts it past its design (L1.28a):
  * No ToUnicode/CMap parsing: subset fonts with custom encodings can yield mangled LETTERS.
    Digits and basic latin survive in practice (pdftex output), which is what number-checking
    needs. Treat garbled output as UNREADABLE, never as evidence of absence.
  * FlateDecode and plain streams only -- no LZW/DCT/JBIG2, no encrypted PDFs.
  * Layout is approximated: text-positioning operators become newlines; columns may interleave.

Every stream that fails to decode is COUNTED, never silently dropped (L1.60): `extract_text`
raises on an unreadable file, and `extract` returns (text, stats) where stats names streams
seen / decoded / failed, so "this PDF said nothing" and "this PDF could not be read" stay
different claims.

Consumer: literature deep-miner sessions, on demand --
    .venv/bin/python -m libs.research.pdf_text paper.pdf
(build-standard schedule exemption: invoked per-dig by the litminer organ, not cron -- the
cadence lives with the organ, not the tool.)
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

#: Start-of-stream marker. Streams are located PROCEDURALLY (anchor on `endstream`, take the
#: last `stream` marker before it, and a bounded window before THAT as the dictionary) because
#: the obvious regex -- `<<(.*?)>>\s*stream(.*?)endstream` DOTALL -- goes quadratic on real
#: PDFs: compressed bytes are full of `<<` with no matching dict, and a 2MB arXiv paper hung a
#: 60s budget where this scan reads it in well under a second. Fixtures could not show that;
#: the positive control did (2026-08-18).
_STREAM_START = re.compile(rb"\bstream\r?\n")
#: Dictionary window: substring checks (/FlateDecode, /Image, ...) never need a structural
#: parse, so 2KB before the stream marker covers every real dict incl. nested /DecodeParms.
_DICT_WINDOW = 2048
#: Text-showing operators inside a decoded content stream.
_SHOW_RE = re.compile(
    rb"\((?P<lit>(?:\\.|[^\\()])*)\)\s*(?:Tj|')"      # (..) Tj   (..) '
    rb"|\[(?P<arr>(?:\\.|[^\]])*)\]\s*TJ"             # [ .. ] TJ
    rb"|(?P<nl>T\*|TD|Td|ET)",                        # line/position breaks -> newline
    re.DOTALL,
)
_ARR_LIT_RE = re.compile(rb"\((?:\\.|[^\\()])*\)", re.DOTALL)
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
            b"(": b"(", b")": b")", b"\\": b"\\"}


def _unescape(lit: bytes) -> bytes:
    """PDF literal-string escapes: \\n \\r \\t \\b \\f \\( \\) \\\\ and \\ddd octal."""
    out = bytearray()
    i = 0
    while i < len(lit):
        c = lit[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = lit[i + 1:i + 2]
        if nxt in _ESCAPES:
            out += _ESCAPES[nxt]
            i += 2
        elif nxt.isdigit():
            j = 1
            while j < 3 and lit[i + 1 + j:i + 2 + j].isdigit():
                j += 1
            out.append(int(lit[i + 1:i + 1 + j], 8) & 0xFF)
            i += 1 + j
        else:
            i += 2                                    # unknown escape: drop the backslash
    return bytes(out)


def _stream_text(content: bytes) -> str:
    """Text-showing operators of ONE decoded content stream -> plain text."""
    parts: list[str] = []
    for m in _SHOW_RE.finditer(content):
        if m.group("nl") is not None:
            if parts and not parts[-1].endswith("\n"):
                parts.append("\n")
            continue
        if m.group("lit") is not None:
            parts.append(_unescape(m.group("lit")).decode("latin-1", "replace"))
        elif m.group("arr") is not None:
            for lit in _ARR_LIT_RE.findall(m.group("arr")):
                parts.append(_unescape(lit[1:-1]).decode("latin-1", "replace"))
    return "".join(parts)


def extract(data: bytes) -> tuple[str, dict[str, int]]:
    """(text, stats) from raw PDF bytes. stats counts streams seen/decoded/failed -- a skip is
    always visible (L1.60), because 'said nothing' and 'unreadable' are different claims."""
    seen = decoded = failed = 0
    texts: list[str] = []
    pos = 0
    while True:
        end = data.find(b"endstream", pos)
        if end == -1:
            break
        start = None
        for sm in _STREAM_START.finditer(data, pos, end):
            start = sm                                # LAST `stream` marker before this end
        pos = end + len(b"endstream")
        if start is None:
            continue                                  # orphan endstream (binary noise): skip
        seen += 1
        head = data[max(0, start.start() - _DICT_WINDOW):start.start()]
        raw = data[start.end():end].rstrip(b"\r\n")
        if b"Image" in head or (b"XObject" in head and b"Form" not in head):
            continue                                  # pixel data, never text
        if b"FlateDecode" in head:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                failed += 1
                continue
        elif b"Filter" in head:
            failed += 1                               # LZW/DCT/...: out of design, counted
            continue
        decoded += 1
        t = _stream_text(raw)
        if t.strip():
            texts.append(t)
    return "\n".join(texts), {"streams": seen, "decoded": decoded, "failed": failed}


def extract_text(path: str | Path) -> str:
    """Text of a PDF file. Raises on an unreadable file or a PDF yielding zero decodable
    streams -- an empty answer must never masquerade as a read (L1.28a)."""
    data = Path(path).read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{path}: not a PDF (no %PDF header)")
    text, stats = extract(data)
    if stats["decoded"] == 0:
        raise ValueError(f"{path}: 0 of {stats['streams']} streams decodable "
                         f"({stats['failed']} failed) -- unreadable, not empty")
    return text


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m libs.research.pdf_text <file.pdf>", file=sys.stderr)
        return 2
    data = Path(argv[0]).read_bytes()
    text, stats = extract(data)
    print(text)
    print(f"[pdf_text] streams={stats['streams']} decoded={stats['decoded']} "
          f"failed={stats['failed']}", file=sys.stderr)
    return 0 if stats["decoded"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
