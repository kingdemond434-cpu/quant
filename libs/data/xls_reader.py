"""Stdlib-only reader for legacy ``.xls`` -- OLE2 compound file + BIFF8 records (OP-046, R0317).

THE BLOCKER THIS REMOVES IS FALSE. ``pandas.read_excel`` cannot open a legacy ``.xls`` without
``xlrd``, and this box has no ``xlrd``, no ``openpyxl`` and no ``olefile`` -- installs are frozen.
Read literally, that reduces every government, regulator and central-bank publication served as
``.xls`` to a screenshot-grade citation. Those publications are disproportionately legacy ``.xls``
precisely BECAUSE they are old institutional pipelines, which is the same reason they stay
under-mined: the format is a moat made of tedium, not of secrecy. A ``.xls`` is two documented
byte-level layers and neither needs a dependency.

WHAT THIS IS NOT. It is not a spreadsheet engine. Formulas are not evaluated -- only the cached
result Excel stored beside them is read. Formatting, dates-as-serials, charts and macros are
ignored by construction: a research extractor wants the numbers, and every additional decoded
feature is another surface that can be plausibly wrong.

THE TWO BUGS THAT PRODUCE PLAUSIBLE-BUT-WRONG OUTPUT, both hit live in the run that produced
OP-046, and both are the reason ``tests/data/test_xls_reader.py`` builds a fixture with TWO sheets
and a deliberately split shared-string table rather than the smallest file that parses:

  (a) SHEET COLLISION. Cell records carry NO sheet id. Keying them on ``(row, col)`` merges every
      sheet in the workbook into one grid. It does not crash and it does not look wrong -- it
      produced a row reading ``CRIPTOATIVO | MES/ANO | ... | 899.79 | 990.46``, one report's
      header spliced onto another report's numbers. The ONLY attribution available is the
      record's absolute stream OFFSET compared against the BOUNDSHEET positions, which is why
      :func:`_parse_biff` tracks ``pos`` and never trusts record order alone.

  (b) SST CONTINUE BOUNDARIES. The shared-string table spans ``CONTINUE`` records and the 1-byte
      compressed/wide flag REPEATS at every continuation boundary, MID-STRING. Ignore it and the
      strings silently become mojibake from the first boundary onward -- silently, because the
      byte count still works out. :class:`_SstReader` exists solely to hold that boundary.

AND THE VALIDATION IS THE TRANSFERABLE HALF. An extractor validated by "it looks right" is a
phantom-evidence factory (OP-025). Pair every parse that feeds a research artifact with a
conservation law taken from INSIDE the data -- :mod:`libs.research.conservation`, which is what
caught bug (a) in the original run when the totals stopped adding up.

    from libs.data.xls_reader import read_xls
    sheets = read_xls(Path("criptoativos_dados_abertos_20250131.xls"))
    {s.name: len(s.cells) for s in sheets}
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: R0318. The structural invariants this parse enforces on ITSELF, all of them refusals rather
#: than repairs: the stream must end exactly on a record boundary (a 1-3 byte tail is a silent
#: truncation), no record may run past the stream, no sector chain may cycle, and the BIFF version
#: must be one this decoder actually implements. They bound the SHAPE of the parse; they cannot
#: tell you the NUMBERS are right -- for that a caller pairs this with an arithmetic identity from
#: inside the data (libs.research.conservation), which is what scripts/read_xls.py requires.
EXTRACTOR_INVARIANT = (
    "stream ends on a record boundary; no record overruns the stream; no sector chain cycles; "
    "BIFF version is 0x0600 -- structural only, so callers add a conservation law for the values"
)

_OLE_SIG: Final = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Sector chain sentinels (MS-CFB 2.2). Anything >= _MAXREGSECT is a marker, never an index.
_MAXREGSECT: Final = 0xFFFFFFFA
_ENDOFCHAIN: Final = 0xFFFFFFFE

_DIR_ENTRY_SIZE: Final = 128
_DIR_TYPE_STREAM: Final = 2
_DIR_TYPE_ROOT: Final = 5

# BIFF8 record opcodes actually decoded here. Everything else is skipped by length, which is why
# an unknown record can never corrupt the walk -- the length prefix is authoritative.
_BOF: Final = 0x0809
_EOF: Final = 0x000A
_BOUNDSHEET: Final = 0x0085
_SST: Final = 0x00FC
_CONTINUE: Final = 0x003C
_LABELSST: Final = 0x00FD
_LABEL: Final = 0x0204
_NUMBER: Final = 0x0203
_RK: Final = 0x027E
_MULRK: Final = 0x00BD
_FORMULA: Final = 0x0006
_BOOLERR: Final = 0x0205

_BIFF8_VERSION: Final = 0x0600

#: A chain longer than this is a cycle, not a file. Bounded so a corrupt FAT refuses rather than
#: hangs -- an extractor that spins on bad input is indistinguishable from a dead one.
_MAX_CHAIN: Final = 1_000_000


class XlsError(ValueError):
    """The input is not a readable BIFF8 ``.xls``.

    Always raised rather than returning a partial grid: a truncated parse that returns SOME cells
    is the single most dangerous outcome here, because the caller's conservation law may still
    pass over whatever survived.
    """


@dataclass(frozen=True)
class Sheet:
    """One worksheet: its name and its sparse cell map, keyed ``(row, col)``, both 0-based."""

    name: str
    cells: dict[tuple[int, int], object]

    @property
    def n_rows(self) -> int:
        return max((r for r, _ in self.cells), default=-1) + 1

    @property
    def n_cols(self) -> int:
        return max((c for _, c in self.cells), default=-1) + 1

    def rows(self) -> list[list[object]]:
        """Dense rectangular grid, ``None`` in every cell the file did not store."""
        width = self.n_cols
        grid: list[list[object]] = [[None] * width for _ in range(self.n_rows)]
        for (r, c), value in self.cells.items():
            grid[r][c] = value
        return grid

    def column(self, col: int, *, skip: int = 0) -> list[object]:
        """One column top-to-bottom, ``skip`` leading rows dropped (header rows)."""
        return [row[col] if col < len(row) else None for row in self.rows()[skip:]]


# --------------------------------------------------------------------------- OLE2 / compound ---
def _u16(buf: bytes, off: int) -> int:
    return int(struct.unpack_from("<H", buf, off)[0])


def _u32(buf: bytes, off: int) -> int:
    return int(struct.unpack_from("<I", buf, off)[0])


def _chain(fat: list[int], start: int) -> list[int]:
    """Follow a sector chain to its end, refusing cycles rather than looping forever."""
    out: list[int] = []
    sector = start
    while sector < _MAXREGSECT:
        if sector >= len(fat):
            raise XlsError(f"sector {sector} past the end of the FAT ({len(fat)} entries)")
        out.append(sector)
        if len(out) > _MAX_CHAIN:
            raise XlsError("sector chain exceeds the cycle bound -- corrupt FAT")
        sector = fat[sector]
    return out


def read_ole2_streams(data: bytes) -> dict[str, bytes]:
    """Split an OLE2 compound file into ``{stream name: bytes}``.

    Streams SMALLER than the header's mini-stream cutoff (normally 4096 B) do not live in ordinary
    sectors at all -- they live in the miniFAT, inside the root entry's own stream. Miss that and
    small sheets vanish SILENTLY, with no error and no empty-file signal.
    """
    if len(data) < 512 or not data.startswith(_OLE_SIG):
        raise XlsError("not an OLE2 compound file (bad signature)")

    sector_size = 1 << _u16(data, 0x1E)
    mini_size = 1 << _u16(data, 0x20)
    n_fat = _u32(data, 0x2C)
    dir_start = _u32(data, 0x30)
    mini_cutoff = _u32(data, 0x38)
    minifat_start = _u32(data, 0x3C)
    difat_start = _u32(data, 0x44)
    n_difat = _u32(data, 0x48)
    if sector_size < 128 or mini_size < 16:
        raise XlsError(f"implausible sector sizes: {sector_size}/{mini_size}")

    def sector_bytes(index: int) -> bytes:
        off = (index + 1) * sector_size
        chunk = data[off : off + sector_size]
        if len(chunk) != sector_size:
            raise XlsError(f"sector {index} is truncated ({len(chunk)}/{sector_size} B)")
        return chunk

    # DIFAT: the first 109 FAT-sector pointers live in the header; the rest chain through
    # dedicated DIFAT sectors, each spending its LAST slot on the next DIFAT pointer.
    difat: list[int] = [_u32(data, 0x4C + 4 * i) for i in range(109)]
    per_difat = sector_size // 4 - 1
    sector = difat_start
    for _ in range(n_difat):
        if sector >= _MAXREGSECT:
            break
        block = sector_bytes(sector)
        difat.extend(_u32(block, 4 * i) for i in range(per_difat))
        sector = _u32(block, 4 * per_difat)

    fat: list[int] = []
    for fat_sector in difat[:n_fat]:
        if fat_sector >= _MAXREGSECT:
            continue
        block = sector_bytes(fat_sector)
        fat.extend(_u32(block, 4 * i) for i in range(sector_size // 4))
    if not fat:
        raise XlsError("compound file declares no FAT sectors")

    def read_chain(start: int, size: int) -> bytes:
        raw = b"".join(sector_bytes(s) for s in _chain(fat, start))
        return raw[:size] if size else raw

    directory = read_chain(dir_start, 0)
    entries: list[tuple[str, int, int, int]] = []
    for off in range(0, len(directory) - _DIR_ENTRY_SIZE + 1, _DIR_ENTRY_SIZE):
        entry = directory[off : off + _DIR_ENTRY_SIZE]
        kind = entry[0x42]
        if kind not in (_DIR_TYPE_STREAM, _DIR_TYPE_ROOT):
            continue
        name_len = _u16(entry, 0x40)
        name = entry[: max(name_len - 2, 0)].decode("utf-16-le", "replace")
        entries.append((name, kind, _u32(entry, 0x74), _u32(entry, 0x78)))

    root = next((e for e in entries if e[1] == _DIR_TYPE_ROOT), None)
    if root is None:
        raise XlsError("compound file has no root directory entry")

    mini_stream = read_chain(root[2], root[3]) if root[3] else b""
    minifat: list[int] = []
    if minifat_start < _MAXREGSECT:
        raw = b"".join(sector_bytes(s) for s in _chain(fat, minifat_start))
        minifat = [_u32(raw, 4 * i) for i in range(len(raw) // 4)]

    def read_mini(start: int, size: int) -> bytes:
        out = bytearray()
        for index in _chain(minifat, start):
            off = index * mini_size
            out += mini_stream[off : off + mini_size]
        return bytes(out[:size])

    streams: dict[str, bytes] = {}
    for name, kind, start, size in entries:
        if kind != _DIR_TYPE_STREAM or not size:
            continue
        streams[name] = read_mini(start, size) if size < mini_cutoff else read_chain(start, size)
    return streams


# ------------------------------------------------------------------------------ BIFF8 records ---
def _rk_to_number(raw: int) -> float:
    """Decode an RK-packed number.

    Bit 0 means "divide by 100"; bit 1 selects a signed 30-bit integer over the TOP HALF of an
    IEEE double. The integer branch must sign-extend -- reading it as unsigned turns every
    negative revision into a number near 2^30 that still looks like data.
    """
    if raw & 0x02:
        signed = int(struct.unpack("<i", struct.pack("<I", raw & 0xFFFFFFFC))[0]) >> 2
        value = float(signed)
    else:
        value = float(struct.unpack("<d", struct.pack("<Q", (raw & 0xFFFFFFFC) << 32))[0])
    return value / 100.0 if raw & 0x01 else value


class _SstReader:
    """Reads the shared-string table across ``CONTINUE`` boundaries -- bug (b) lives here.

    The table is one logical byte stream cut into records. A string may be split at any character
    boundary, and when it is, the continuation restarts with a FRESH 1-byte option flag whose
    compressed/wide bit may DIFFER from the one the string started with. So width is a property of
    the current segment, never of the string.
    """

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self._i = 0
        self._pos = 0

    def _advance(self) -> bool:
        """Move to the next chunk holding bytes -- correct BETWEEN strings, never WITHIN one.

        A fresh string that happens to start in a new record carries no repeated flag byte, so
        skipping transparently is right here. Character data is the opposite case and is handled
        in :meth:`read_string`, which must consume that byte instead of reading it as text.
        """
        while self._i < len(self._chunks) and self._pos >= len(self._chunks[self._i]):
            self._i += 1
            self._pos = 0
        return self._i < len(self._chunks)

    def _exhausted(self) -> bool:
        return self._pos >= len(self._chunks[self._i])

    def _take(self, n: int) -> bytes:
        if not self._advance():
            raise XlsError("shared-string table ended mid-record")
        chunk = self._chunks[self._i]
        if self._pos + n > len(chunk):
            raise XlsError("shared-string header split across a CONTINUE boundary")
        out = chunk[self._pos : self._pos + n]
        self._pos += n
        return out

    def _remaining(self) -> int:
        return len(self._chunks[self._i]) - self._pos if self._advance() else 0

    def read_string(self) -> str:
        n_chars = int(struct.unpack("<H", self._take(2))[0])
        flags = self._take(1)[0]
        wide = bool(flags & 0x01)
        n_runs = int(struct.unpack("<H", self._take(2))[0]) if flags & 0x08 else 0
        ext_len = int(struct.unpack("<I", self._take(4))[0]) if flags & 0x04 else 0

        out: list[str] = []
        left = n_chars
        while left > 0:
            if self._i >= len(self._chunks):
                raise XlsError("shared-string table ended mid-string")
            if self._exhausted():
                # THE BOUNDARY, AND THE WHOLE REASON THIS CLASS EXISTS. Crossing a CONTINUE
                # record mid-string means the next byte is a REPEATED option flag, not text --
                # and its width bit may differ from the one this string started with. Advancing
                # transparently here reads that byte as a character: the count still works out,
                # so every following character shifts by one byte and the string silently
                # becomes mojibake with no error raised anywhere.
                self._i += 1
                self._pos = 0
                if self._i >= len(self._chunks):
                    raise XlsError("shared-string table ended mid-string")
                wide = bool(self._take(1)[0] & 0x01)
                continue
            width = 2 if wide else 1
            take = min(left, self._remaining() // width)
            if take <= 0:
                # A wide segment with one dangling byte cannot hold a character: it is a
                # boundary, so fall through to the branch above rather than reading half of one.
                self._pos = len(self._chunks[self._i])
                continue
            raw = self._take(take * width)
            out.append(raw.decode("utf-16-le" if wide else "latin-1"))
            left -= take

        for _ in range(n_runs):
            self._take(4)
        if ext_len:
            self._take(ext_len)
        return "".join(out)


def _unicode_string(payload: bytes, off: int) -> str:
    """Decode an inline BIFF8 unicode string (LABEL, BOUNDSHEET names)."""
    n_chars = _u16(payload, off)
    flags = payload[off + 2]
    body = payload[off + 3 :]
    if flags & 0x01:
        return body[: n_chars * 2].decode("utf-16-le", "replace")
    return body[:n_chars].decode("latin-1")


def _short_string(payload: bytes, off: int) -> str:
    """BOUNDSHEET carries an 8-bit length, not the 16-bit one every other record uses."""
    n_chars = payload[off]
    flags = payload[off + 1]
    body = payload[off + 2 :]
    if flags & 0x01:
        return body[: n_chars * 2].decode("utf-16-le", "replace")
    return body[:n_chars].decode("latin-1")


def _records(stream: bytes) -> list[tuple[int, int, bytes]]:
    """Walk the record stream, yielding ``(absolute offset, opcode, payload)``.

    The offset is not decoration: it is the ONLY thing that attributes a cell to a sheet.
    """
    out: list[tuple[int, int, bytes]] = []
    pos = 0
    while pos + 4 <= len(stream):
        opcode = _u16(stream, pos)
        length = _u16(stream, pos + 2)
        if pos + 4 + length > len(stream):
            raise XlsError(f"record 0x{opcode:04X} at {pos} runs past the end of the stream")
        out.append((pos, opcode, stream[pos + 4 : pos + 4 + length]))
        pos += 4 + length
    if pos != len(stream):
        # A BIFF stream is records end to end and the directory records its exact length, so
        # leftover bytes mean the stream was truncated -- and 1-3 of them are the dangerous
        # amount, because they are too short to be a header and a `pos + 4 <= len` walk simply
        # stops on them. That drops a record with no error at all, which is the truncation
        # failure mode that never throws: every number already read still looks right.
        raise XlsError(
            f"stream does not end on a record boundary: {len(stream) - pos} trailing byte(s) "
            f"after the last complete record -- truncated or not a BIFF stream"
        )
    return out


def _parse_biff(stream: bytes) -> list[Sheet]:
    records = _records(stream)
    if not records or records[0][1] != _BOF:
        raise XlsError("workbook stream does not start with a BOF record")
    version = _u16(records[0][2], 0) if len(records[0][2]) >= 2 else 0
    if version != _BIFF8_VERSION:
        raise XlsError(
            f"unsupported BIFF version 0x{version:04X} -- only BIFF8 (0x0600) is decoded; "
            "a 'Book' stream from Excel 5/95 needs a different record layout"
        )

    # Pass 1: sheet directory and the shared-string table, both of which live in the globals
    # substream and must be complete before any cell record can be interpreted.
    boundsheets: list[tuple[int, str]] = []
    sst: list[str] = []
    sst_chunks: list[bytes] = []
    collecting = False
    for _, opcode, payload in records:
        if opcode == _BOUNDSHEET:
            boundsheets.append((_u32(payload, 0), _short_string(payload, 6)))
            collecting = False
        elif opcode == _SST:
            sst_chunks = [payload[8:]]
            collecting = True
        elif opcode == _CONTINUE and collecting:
            sst_chunks.append(payload)
        elif opcode != _CONTINUE:
            collecting = False
    if sst_chunks:
        reader = _SstReader(sst_chunks)
        n_unique = _u32(records[[r[1] for r in records].index(_SST)][2], 4)
        for _ in range(n_unique):
            sst.append(reader.read_string())

    if not boundsheets:
        raise XlsError("workbook declares no sheets (no BOUNDSHEET record)")
    boundsheets.sort()
    starts = [off for off, _ in boundsheets]
    cells: list[dict[tuple[int, int], object]] = [{} for _ in boundsheets]

    def sheet_of(offset: int) -> int:
        """Attribute a record to a sheet by absolute offset -- never by record order (bug a)."""
        index = -1
        for i, start in enumerate(starts):
            if offset >= start:
                index = i
            else:
                break
        return index

    # Pass 2: cells. A record before the first sheet's BOF belongs to the globals substream and is
    # deliberately dropped rather than folded into sheet 0.
    for offset, opcode, payload in records:
        index = sheet_of(offset)
        if index < 0 or opcode in (_BOF, _EOF):
            continue
        grid = cells[index]
        if opcode == _NUMBER and len(payload) >= 14:
            grid[_u16(payload, 0), _u16(payload, 2)] = float(
                struct.unpack_from("<d", payload, 6)[0]
            )
        elif opcode == _RK and len(payload) >= 10:
            grid[_u16(payload, 0), _u16(payload, 2)] = _rk_to_number(_u32(payload, 6))
        elif opcode == _MULRK and len(payload) >= 6:
            row = _u16(payload, 0)
            first = _u16(payload, 2)
            for n in range((len(payload) - 6) // 6):
                grid[row, first + n] = _rk_to_number(_u32(payload, 4 + 6 * n + 2))
        elif opcode == _LABELSST and len(payload) >= 10:
            index_sst = _u32(payload, 6)
            grid[_u16(payload, 0), _u16(payload, 2)] = (
                sst[index_sst] if index_sst < len(sst) else None
            )
        elif opcode == _LABEL and len(payload) >= 8:
            grid[_u16(payload, 0), _u16(payload, 2)] = _unicode_string(payload, 6)
        elif opcode == _FORMULA and len(payload) >= 20:
            # Only the CACHED result is read. 0xFFFF in the high word marks a non-numeric result
            # (string/bool/error) whose value lives in a following record -- refused, not guessed.
            if _u16(payload, 12) != 0xFFFF:
                grid[_u16(payload, 0), _u16(payload, 2)] = float(
                    struct.unpack_from("<d", payload, 6)[0]
                )
        elif opcode == _BOOLERR and len(payload) >= 8 and payload[7] == 0:
            grid[_u16(payload, 0), _u16(payload, 2)] = bool(payload[6])

    paired = zip(boundsheets, cells, strict=True)
    return [Sheet(name=name, cells=grid) for (_, name), grid in paired]


def read_xls(src: Path | bytes) -> list[Sheet]:
    """Read a legacy ``.xls`` into sheets, in workbook order.

    Raises :class:`XlsError` on anything it cannot decode faithfully. It never returns a partial
    workbook: a half-parsed grid is the outcome most likely to pass a downstream sanity check
    while being wrong, which is the failure mode this whole module exists to avoid.
    """
    data = src.read_bytes() if isinstance(src, Path) else src
    streams = read_ole2_streams(data)
    for name in ("Workbook", "Book"):
        if name in streams:
            return _parse_biff(streams[name])
    raise XlsError(f"no Workbook stream; found {sorted(streams) or 'no streams'}")
