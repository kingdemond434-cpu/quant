"""Minimal OLE2 + BIFF8 WRITER, used only to build fixtures for the ``.xls`` reader tests.

WHY A WRITER EXISTS AT ALL. The two bugs OP-046 names as the dangerous ones -- sheet collision and
a shared-string table split mid-string across a CONTINUE boundary -- are both invisible in the
smallest file that parses. A single-sheet fixture with a short SST cannot express either, so a test
suite built on one would be structurally incapable of catching the exact failures the module was
written to avoid. That is the desk's own repeated lesson about fixtures: build from the WIDEST real
schema, not the narrowest.

The writer is deliberately dumb and independent of the reader: it lays bytes out from the format
spec rather than sharing any helper with :mod:`libs.data.xls_reader`, so a matched bug in both
would have to be an independent coincidence in two different directions. Expected values in the
tests are stated as literals besides, so a shared bug still has to survive an external assertion.
"""

from __future__ import annotations

import struct
from typing import Final

_OLE_SIG: Final = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_FREESECT: Final = 0xFFFFFFFF
_ENDOFCHAIN: Final = 0xFFFFFFFE
_FATSECT: Final = 0xFFFFFFFD

SECTOR: Final = 512
MINI: Final = 64
MINI_CUTOFF: Final = 4096

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
#: OBJ -- a real BIFF8 opcode this reader deliberately has no decoder for, used as inert padding.
_UNKNOWN: Final = 0x005D


def _rec(opcode: int, payload: bytes) -> bytes:
    return struct.pack("<HH", opcode, len(payload)) + payload


def _bof(substream: int) -> bytes:
    return _rec(_BOF, struct.pack("<HHHHII", 0x0600, substream, 0x0DBB, 0x07CC, 0, 0))


def encode_rk(value: float) -> int:
    """Pack a float into an RK word, using whichever of the four encodings fits.

    Exercising more than one branch matters: the identity that validates a parse is only strong
    evidence if it spans BOTH encodings, because a decoder bug confined to one cannot then cancel.
    """
    if float(value).is_integer() and -(2**29) <= value < 2**29:
        return ((int(value) << 2) & 0xFFFFFFFF) | 0x02
    scaled = value * 100.0
    if scaled.is_integer() and -(2**29) <= scaled < 2**29:
        return ((int(scaled) << 2) & 0xFFFFFFFF) | 0x03
    bits = struct.unpack("<Q", struct.pack("<d", value))[0]
    if bits & 0x00000000FFFFFFFF:
        raise ValueError(f"{value!r} needs full f64 precision -- write it as a NUMBER record")
    return int(bits >> 32) & 0xFFFFFFFC


def filler(n_bytes: int) -> bytes:
    """Exactly ``n_bytes`` of records the reader has no decoder for.

    Padding a stream with raw zeros would be the easy way to reach the big-sector path, but a
    BIFF stream is records end to end, so zero padding builds a fixture no real file resembles --
    and it would hide the fact that a reader must skip an UNKNOWN record by its length prefix
    rather than by recognising it. Using real records tests that instead of assuming it.
    """
    if n_bytes == 0:
        return b""
    if n_bytes < 4:
        raise ValueError(f"cannot pad {n_bytes} B: a record header alone is 4 B")
    out = b""
    left = n_bytes
    while left:
        take = min(left, 4 + 8216)
        if 0 < left - take < 4:  # never leave a tail too short to be a record
            take = left - 4
        out += _rec(_UNKNOWN, bytes(take - 4))
        left -= take
    return out


def cell_number(row: int, col: int, value: float) -> bytes:
    """A full IEEE-754 NUMBER record."""
    return _rec(_NUMBER, struct.pack("<HHHd", row, col, 0, value))


def cell_rk(row: int, col: int, value: float) -> bytes:
    """A compressed RK record."""
    return _rec(_RK, struct.pack("<HHHI", row, col, 0, encode_rk(value)))


def cell_mulrk(row: int, first_col: int, values: list[float]) -> bytes:
    """A MULRK run -- several RK cells sharing one record, ending with the last column index."""
    body = struct.pack("<HH", row, first_col)
    for value in values:
        body += struct.pack("<HI", 0, encode_rk(value))
    return _rec(_MULRK, body + struct.pack("<H", first_col + len(values) - 1))


def cell_sst(row: int, col: int, index: int) -> bytes:
    """A LABELSST record pointing into the shared-string table."""
    return _rec(_LABELSST, struct.pack("<HHHI", row, col, 0, index))


def cell_label(row: int, col: int, text: str, *, rich: bool = False, ext: bool = False) -> bytes:
    """An inline LABEL record -- the decoder path the SST cannot reach.

    ``rich`` and ``ext`` set fRichSt/fExtSt, which insert ``cRun`` (2 B) and ``cbExtRst`` (4 B)
    BETWEEN the flag byte and the characters. A reader that jumps straight to the text reads those
    headers as characters and returns a shortened, binary-prefixed string with no error. Excel
    itself prefers LABELSST, so bare LABELs come from third-party writers -- the ones that set
    these bits.
    """
    wide = any(ord(ch) > 0xFF for ch in text)
    flags = (0x01 if wide else 0x00) | (0x08 if rich else 0x00) | (0x04 if ext else 0x00)
    body = struct.pack("<HB", len(text), flags)
    if rich:
        body += struct.pack("<H", 0)          # cRun: zero runs, but the field is still present
    if ext:
        body += struct.pack("<I", 0)          # cbExtRst
    body += text.encode("utf-16-le" if wide else "latin-1")
    return _rec(_LABEL, struct.pack("<HHH", row, col, 0) + body)


def encode_sst_detailed(strings: list[str], max_payload: int = 8216) -> tuple[list[bytes], int]:
    """Encode the shared-string table, and report how many splits landed MID-STRING.

    THE COUNT IS THE POINT, NOT DECORATION. A table can span several CONTINUE records while every
    boundary falls neatly BETWEEN strings, and such a fixture exercises none of the repeated-flag
    logic the reader exists to get right -- ``len(chunks) > 1`` is satisfied and the control passes
    while testing nothing. Measured on this fixture: cap 40 -> 4 mid-string splits, cap 64 -> 1,
    cap 97 -> 0 despite producing multiple chunks. Only a caller that can SEE the difference can
    assert on it (L1.57).
    """
    chunks: list[bytearray] = [bytearray()]
    mid_string_splits = 0

    def room() -> int:
        return max_payload - len(chunks[-1])

    for text in strings:
        wide = any(ord(ch) > 0xFF for ch in text)
        width = 2 if wide else 1
        flag = 0x01 if wide else 0x00
        data = text.encode("utf-16-le") if wide else text.encode("latin-1")
        if room() < 3 + width:
            chunks.append(bytearray())
        chunks[-1] += struct.pack("<HB", len(text), flag)
        written = 0
        while written < len(text):
            available = room() // width
            if available <= 0:
                chunks.append(bytearray())
                chunks[-1] += bytes([flag])  # the repeated flag byte, mid-string
                mid_string_splits += 1
                continue
            take = min(len(text) - written, available)
            chunks[-1] += data[written * width : (written + take) * width]
            written += take
    return [bytes(chunk) for chunk in chunks], mid_string_splits


def encode_sst(strings: list[str], max_payload: int = 8216) -> list[bytes]:
    """Encode the shared-string table, splitting into CONTINUE chunks at ``max_payload``.

    THE RULE THIS EXISTS TO REPRODUCE: a string may be cut at any character boundary, and the
    continuation then restarts with a FRESH 1-byte option flag before the remaining characters.
    Drop that byte and the reader's character count still works out -- which is exactly why the
    corruption is silent. Pass a small ``max_payload`` to force splits in a tiny fixture.
    """
    return encode_sst_detailed(strings, max_payload)[0]


def build_workbook(
    sheets: list[tuple[str, bytes]],
    strings: list[str] | None = None,
    *,
    sst_max_payload: int = 8216,
    layout: list[int] | None = None,
) -> bytes:
    """Assemble a BIFF8 ``Workbook`` stream from per-sheet cell records.

    ``layout`` writes the substreams in a DIFFERENT order from the BOUNDSHEET declarations, which
    is legal and which Excel does. Tab order is declaration order; stream order need not match. A
    fixture that always writes them in the same order cannot tell a reader that sorts by offset
    from one that preserves tab order -- both return the same list.
    """
    strings = strings or []
    globals_head = _bof(0x0005)
    sst_records = b""
    if strings:
        chunks = encode_sst(strings, sst_max_payload)
        sst_records = _rec(_SST, struct.pack("<II", len(strings), len(strings)) + chunks[0])
        for extra in chunks[1:]:
            sst_records += _rec(_CONTINUE, extra)

    # BOUNDSHEET carries the absolute offset of its sheet's BOF, so the globals substream has to be
    # sized before the offsets are known: build it once with placeholders, then patch them in.
    def globals_block(offsets: list[int]) -> bytes:
        out = globals_head
        for (name, _), offset in zip(sheets, offsets, strict=True):
            encoded = name.encode("latin-1")
            out += _rec(
                _BOUNDSHEET,
                struct.pack("<IBB", offset, 0, 0) + bytes([len(encoded), 0]) + encoded,
            )
        return out + sst_records + _rec(_EOF, b"")

    order = list(range(len(sheets))) if layout is None else layout
    if sorted(order) != list(range(len(sheets))):
        raise ValueError(f"layout {order} is not a permutation of {len(sheets)} sheets")
    placeholder = globals_block([0] * len(sheets))
    offsets = [0] * len(sheets)
    cursor = len(placeholder)
    bodies: dict[int, bytes] = {}
    for index in order:
        offsets[index] = cursor
        bodies[index] = _bof(0x0010) + sheets[index][1] + _rec(_EOF, b"")
        cursor += len(bodies[index])
    return globals_block(offsets) + b"".join(bodies[i] for i in order)


def build_ole2(streams: dict[str, bytes]) -> bytes:
    """Wrap named streams in an OLE2 compound file.

    Streams under :data:`MINI_CUTOFF` are placed in the miniFAT inside the root entry's stream --
    the path a reader silently misses, making small sheets vanish with no error at all.
    """
    names = list(streams)
    big = {n: streams[n] for n in names if len(streams[n]) >= MINI_CUTOFF}
    small = {n: streams[n] for n in names if len(streams[n]) < MINI_CUTOFF}

    mini_blob = bytearray()
    mini_start: dict[str, int] = {}
    minifat: list[int] = []
    for name, blob in small.items():
        first = len(mini_blob) // MINI
        mini_start[name] = first
        count = max(1, -(-len(blob) // MINI))
        mini_blob += blob + bytes((-len(blob)) % MINI)
        minifat.extend(range(first + 1, first + count))
        minifat.append(_ENDOFCHAIN)

    def sectors_for(size: int) -> int:
        return max(1, -(-size // SECTOR)) if size else 0

    minifat_bytes = b"".join(struct.pack("<I", entry) for entry in minifat)
    n_dir_entries = 1 + len(names)
    dir_bytes_len = n_dir_entries * 128

    plan = [
        *[(n, sectors_for(len(b))) for n, b in big.items()],
        ("*mini", sectors_for(len(mini_blob))),
        ("*minifat", sectors_for(len(minifat_bytes))),
        ("*dir", sectors_for(dir_bytes_len)),
    ]
    data_sectors = sum(count for _, count in plan)

    n_fat = 1
    while True:  # the FAT must describe itself, so grow it to a fixed point
        if -(-(data_sectors + n_fat) // (SECTOR // 4)) <= n_fat:
            break
        n_fat += 1
    total = data_sectors + n_fat

    fat = [_FREESECT] * total
    start: dict[str, int] = {}
    cursor = 0
    for name, count in plan:
        if not count:
            start[name] = _ENDOFCHAIN
            continue
        start[name] = cursor
        for i in range(count):
            fat[cursor + i] = cursor + i + 1 if i < count - 1 else _ENDOFCHAIN
        cursor += count
    for i in range(n_fat):
        fat[cursor + i] = _FATSECT

    directory = bytearray()

    def dir_entry(name: str, kind: int, start_sector: int, size: int, child: int) -> bytes:
        raw = name.encode("utf-16-le") + b"\x00\x00"
        entry = bytearray(128)
        entry[: len(raw)] = raw
        struct.pack_into("<H", entry, 0x40, len(raw))
        entry[0x42] = kind
        entry[0x43] = 1
        struct.pack_into("<iii", entry, 0x44, -1, -1, child)
        struct.pack_into("<I", entry, 0x74, start_sector)
        struct.pack_into("<I", entry, 0x78, size)
        return bytes(entry)

    directory += dir_entry(
        "Root Entry", 5, start["*mini"], len(mini_blob), 1 if names else -1
    )
    for name in names:
        if name in big:
            directory += dir_entry(name, 2, start[name], len(streams[name]), -1)
        else:
            directory += dir_entry(name, 2, mini_start[name], len(streams[name]), -1)
    directory += bytes((-len(directory)) % SECTOR)

    # The directory is a planned run like any other, so it is assembled into the payload here
    # rather than spliced in afterwards -- a splice has to recompute an offset that the plan
    # already knows, and that second computation is a place for the two to disagree.
    blobs = {"*mini": bytes(mini_blob), "*minifat": minifat_bytes, "*dir": bytes(directory)}
    payload = bytearray()
    for name, count in plan:
        if not count:
            continue
        blob = blobs.get(name, streams.get(name, b""))
        payload += blob + bytes((-len(blob)) % SECTOR)

    # Pad the FAT out to a whole sector with FREESECT, never with zeros: a zero decodes as a
    # perfectly valid pointer to sector 0, so zero padding turns a walk off the end of the live
    # entries into a silent loop back into the file instead of a refusal.
    fat += [_FREESECT] * (-len(fat) % (SECTOR // 4))
    fat_bytes = b"".join(struct.pack("<I", entry) for entry in fat)

    header = bytearray(512)
    header[:8] = _OLE_SIG
    struct.pack_into("<H", header, 0x18, 0x003E)
    struct.pack_into("<H", header, 0x1A, 3)
    struct.pack_into("<H", header, 0x1C, 0xFFFE)
    struct.pack_into("<H", header, 0x1E, 9)  # 1 << 9 == 512
    struct.pack_into("<H", header, 0x20, 6)  # 1 << 6 == 64
    struct.pack_into("<I", header, 0x2C, n_fat)
    struct.pack_into("<I", header, 0x30, start["*dir"])
    struct.pack_into("<I", header, 0x38, MINI_CUTOFF)
    struct.pack_into("<I", header, 0x3C, start["*minifat"])
    struct.pack_into("<I", header, 0x40, sectors_for(len(minifat_bytes)))
    struct.pack_into("<I", header, 0x44, _ENDOFCHAIN)
    struct.pack_into("<I", header, 0x48, 0)
    for i in range(109):
        struct.pack_into("<I", header, 0x4C + 4 * i, cursor + i if i < n_fat else _FREESECT)

    return bytes(header) + bytes(payload) + fat_bytes


def build_xls(
    sheets: list[tuple[str, bytes]],
    strings: list[str] | None = None,
    *,
    sst_max_payload: int = 8216,
    pad_to: int = 0,
    layout: list[int] | None = None,
) -> bytes:
    """One-call fixture: sheets plus shared strings out to a complete ``.xls`` file.

    ``pad_to`` inflates the workbook past :data:`MINI_CUTOFF` so the ordinary-FAT path is exercised
    as well as the miniFAT one; both are real and a reader can implement exactly one of them.
    """
    workbook = build_workbook(
        sheets, strings, sst_max_payload=sst_max_payload, layout=layout
    )
    if pad_to and len(workbook) < pad_to:
        workbook += filler(pad_to - len(workbook))
    return build_ole2({"Workbook": workbook})
