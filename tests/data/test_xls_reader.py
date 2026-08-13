"""Tests for the stdlib ``.xls`` reader (R0317, OP-046).

THE FIXTURE IS THE ARGUMENT. Every assertion here is written against a workbook that can EXPRESS
the two bugs OP-046 names as the dangerous ones, because a fixture that cannot express a bug
cannot witness its absence. Both bugs return plausible data rather than raising, so a suite built
on the smallest file that parses would pass identically with either bug present:

  (a) SHEET COLLISION -- so the fixture puts DIFFERENT values at the SAME (row, col) on two
      sheets, and :func:`test_fixture_can_express_sheet_collision` asserts that property directly.
      Without it, "sheet A reads 111" is satisfied by a merged grid too.

  (b) SST CONTINUE BOUNDARY -- so the fixture forces the shared-string table to split MID-STRING,
      and :func:`test_fixture_can_express_sst_split` asserts the split actually happened. A cap
      large enough to hold the table in one record tests nothing.

Expected values are stated as literals rather than derived from the writer, so a bug shared by
reader and writer still has to survive an external assertion.
"""

from __future__ import annotations

import random
import struct

import pytest
from tests.data.xls_builder import (
    build_ole2,
    build_workbook,
    build_xls,
    cell_label,
    cell_mulrk,
    cell_number,
    cell_rk,
    cell_sst,
    encode_sst_detailed,
    filler,
)

from libs.data.xls_reader import XlsError, read_xls

# Two sheets, same coordinates, different values: the shape a merged grid cannot fake.
_COLLIDING = [("Alpha", cell_rk(0, 0, 111.0)), ("Beta", cell_rk(0, 0, 222.0))]

# Long enough to be split by a small cap, and GENUINELY mixed-width so the repeated flag byte can
# FLIP. The middle string previously read "...ção", which is entirely latin-1: all three encoded
# 8-bit, so every continuation repeated the same flag and the reader's central claim -- that width
# is a property of the SEGMENT, never of the string -- was never once exercised. The CJK characters
# force the wide branch, so the table now crosses compressed -> wide -> compressed.
_STRINGS = ["alpha" * 12, "Relatório de Criptoativos 交易所", "beta" * 15]

#: Caps MEASURED to cut inside a string rather than between two. `len(chunks) > 1` does not imply
#: it: at cap 97 this table spans two records with every boundary falling neatly between strings.
_MID_STRING_CAPS = [24, 32, 40, 97]
_ALL_CAPS = [24, 32, 40, 64, 97, 8216]


def _string_sheet() -> list[tuple[str, bytes]]:
    return [("S", b"".join(cell_sst(i, 0, i) for i in range(len(_STRINGS))))]


# ------------------------------------------------------------------ the fixture's own controls ---
def test_fixture_can_express_sheet_collision() -> None:
    """Bug (a) is only witnessed if the two sheets genuinely overlap -- assert that, not assume."""
    assert _COLLIDING[0][1] != _COLLIDING[1][1]
    sheets = read_xls(build_xls(_COLLIDING))
    coords = [set(sheet.cells) for sheet in sheets]
    assert coords[0] == coords[1] == {(0, 0)}, "sheets must occupy the SAME cell to express a merge"


@pytest.mark.parametrize("cap", _MID_STRING_CAPS)
def test_fixture_can_express_sst_split(cap: int) -> None:
    """Bug (b) is only witnessed if a boundary falls INSIDE a string, not merely between two.

    The weaker `len(chunks) > 1` reads like a control and is not one: at cap 97 this table spans
    two records with zero mid-string cuts, so the repeated flag byte the reader must consume never
    appears and the whole bug path goes untested while the control reports green.
    """
    chunks, mid_string = encode_sst_detailed(_STRINGS, cap)
    assert len(chunks) > 1, f"cap {cap} forced no split -- fixture is inert"
    assert mid_string > 0, f"cap {cap} split only BETWEEN strings -- bug (b) is not expressed"


def test_fixture_can_express_a_width_flip() -> None:
    """The reader's core claim is that width is per-SEGMENT; an all-8-bit table cannot test it."""
    widths = {any(ord(ch) > 0xFF for ch in text) for text in _STRINGS}
    assert widths == {True, False}, "fixture strings must mix wide and compressed encodings"


# ---------------------------------------------------------------------------- the two bug paths ---
def test_sheets_are_not_merged() -> None:
    sheets = read_xls(build_xls(_COLLIDING))
    assert [s.name for s in sheets] == ["Alpha", "Beta"]
    assert sheets[0].cells[(0, 0)] == 111.0
    assert sheets[1].cells[(0, 0)] == 222.0


def test_cells_are_attributed_by_offset_not_by_order() -> None:
    """A third sheet between the two must not shift anyone's cells."""
    sheets = read_xls(
        build_xls(
            [
                ("First", cell_rk(0, 0, 1.0)),
                ("Middle", cell_rk(0, 0, 2.0) + cell_rk(5, 5, 55.0)),
                ("Last", cell_rk(0, 0, 3.0)),
            ]
        )
    )
    assert [s.cells[(0, 0)] for s in sheets] == [1.0, 2.0, 3.0]
    assert sheets[1].cells[(5, 5)] == 55.0
    assert (5, 5) not in sheets[0].cells and (5, 5) not in sheets[2].cells


@pytest.mark.parametrize("cap", _ALL_CAPS)
def test_shared_strings_survive_continue_boundaries(cap: int) -> None:
    """The repeated option flag at each boundary must be consumed, never read as a character."""
    sheet = read_xls(build_xls(_string_sheet(), _STRINGS, sst_max_payload=cap))[0]
    assert [sheet.cells[(i, 0)] for i in range(len(_STRINGS))] == _STRINGS


def test_wide_string_round_trips() -> None:
    """A non-latin-1 string forces the wide (UTF-16) branch, SPLIT across a boundary.

    The cap here used to be 24, which the table (17 B) never reached: it produced a single chunk
    and no CONTINUE at all, so a test named for the split tested the unsplit path.
    """
    strings = ["交易所" * 4, "ascii" * 4]
    chunks, mid_string = encode_sst_detailed(strings, 16)
    assert len(chunks) > 1 and mid_string > 0, "the wide string must actually be cut in half"
    sheets = read_xls(
        build_xls([("S", cell_sst(0, 0, 0) + cell_sst(1, 0, 1))], strings, sst_max_payload=16)
    )
    assert [sheets[0].cells[(i, 0)] for i in range(2)] == strings


# ------------------------------------------- silently-wrong-output defects found in review 08-12 --
@pytest.mark.parametrize(
    ("rich", "ext"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_inline_label_skips_the_rich_and_phonetic_headers(rich: bool, ext: bool) -> None:
    """cRun and cbExtRst sit BETWEEN the flag byte and the characters.

    Reading straight past the flag returned 'Total geral' as '\\x01\\x00Total ger' (rich) and
    '\\x00\\x00\\x00\\x00Total g' (ext) -- shortened, binary-prefixed, and raising nothing, because
    the character count still works out. The SST decoder 100 lines away already handled this.
    """
    sheets = read_xls(build_xls([("S", cell_label(0, 0, "Total geral", rich=rich, ext=ext))]))
    assert sheets[0].cells[(0, 0)] == "Total geral"


def test_inline_label_round_trips_wide_text() -> None:
    sheets = read_xls(build_xls([("S", cell_label(2, 1, "Relatório 交易所", rich=True))]))
    assert sheets[0].cells[(2, 1)] == "Relatório 交易所"


def test_sheets_come_back_in_TAB_order_not_stream_order() -> None:
    """Excel's tab order is BOUNDSHEET declaration order; stream layout need not agree.

    Sorting the returned list by offset silently renumbers the tabs, so `--sheet 0` hands back a
    real sheet full of real numbers -- just not the one Excel shows first. Names travel with their
    grids, so selection by NAME was always safe and only index selection was wrong.
    """
    sheets = read_xls(
        build_xls(
            [("Betaa", cell_rk(0, 0, 222.0)), ("Alpha", cell_rk(0, 0, 111.0))],
            layout=[1, 0],  # Alpha's substream is written FIRST, but it is the SECOND tab
        )
    )
    assert [s.name for s in sheets] == ["Betaa", "Alpha"]
    assert sheets[0].cells[(0, 0)] == 222.0
    assert sheets[1].cells[(0, 0)] == 111.0


def test_an_encrypted_workbook_is_refused_not_decoded() -> None:
    """BIFF8 RC4 leaves record HEADERS in plaintext, so the walk succeeds and every payload
    decodes into ciphertext that looks exactly like data (measured: 1.779e+127).
    """
    workbook = build_workbook([("S", cell_rk(0, 0, 1.0))])
    bof_len = 4 + struct.unpack_from("<H", workbook, 2)[0]      # FILEPASS follows the globals BOF
    spliced = (
        workbook[:bof_len]
        + struct.pack("<HHH", 0x002F, 2, 0x0001)                 # FILEPASS, wEncryptionType=RC4
        + workbook[bof_len:]
    )
    with pytest.raises(XlsError, match="encrypted"):
        read_xls(build_ole2({"Workbook": spliced}))


def test_a_column_past_the_biff8_grid_is_refused() -> None:
    """One junk cell at column 65535 makes Sheet.rows() densify to billions of slots."""
    with pytest.raises(XlsError, match="outside the BIFF8 grid"):
        read_xls(build_xls([("S", cell_rk(0, 65535, 1.0))]))


def test_a_labelsst_past_the_table_is_refused_not_stored_as_none() -> None:
    """A hole in the grid, from a module whose contract is that it never returns a partial one."""
    with pytest.raises(XlsError, match="shared-string table"):
        read_xls(build_xls([("S", cell_sst(0, 0, 7))], ["only-one"]))


def _shrink_mini_stream(raw: bytes, lost: int) -> bytes:
    """Shrink the ROOT entry's size, which is what the mini stream is carved out of.

    Lopping bytes off the END of the file cannot probe this: that trips the big-sector guard in
    ``sector_bytes``, which already refused correctly, so a test written that way passes both
    before and after the fix and witnesses nothing.
    """
    data = bytearray(raw)
    sector_size = 1 << struct.unpack_from("<H", data, 0x1E)[0]
    base = (struct.unpack_from("<I", data, 0x30)[0] + 1) * sector_size
    for off in range(base, min(base + sector_size, len(data) - 128 + 1), 128):
        if data[off + 0x42] == 5:                      # the root entry owns the mini stream
            size = struct.unpack_from("<I", data, off + 0x78)[0]
            struct.pack_into("<I", data, off + 0x78, max(size - lost, 0))
            return bytes(data)
    raise AssertionError("no root directory entry found in the fixture")


@pytest.mark.parametrize("lost", [37, 121, 191])
def test_a_truncated_mini_stream_is_refused(lost: int) -> None:
    """out[:size] returned FEWER bytes than the directory promised, so trailing rows vanished with
    NOTHING RAISED. Measured against the previous reader by sweeping this fixture: 40 of 599
    truncations returned a short grid silently -- at ``lost=37`` a 40-row sheet came back with 39
    rows and no error. The conservation identities this module prescribes cannot catch it either,
    because the rows that survive still balance perfectly. 64-byte mini sectors against 512-byte
    big ones is what makes this the more exposed of the two paths.
    """
    raw = build_xls([("S", b"".join(cell_rk(r, 0, float(r)) for r in range(40)))])
    assert len(read_xls(raw)[0].cells) == 40, "fixture must take the miniFAT path intact first"
    with pytest.raises(XlsError, match=r"truncated|short"):
        read_xls(_shrink_mini_stream(raw, lost))


def test_a_corrupt_sector_exponent_refuses_instead_of_exploding() -> None:
    """These header fields are log2 sizes, so `1 << n` on a corrupt one is an integer with
    thousands of digits -- and the refusal raised ValueError while FORMATTING it into its own
    error message, escaping as a non-XlsError from a module contracted to raise XlsError.
    """
    data = bytearray(build_xls([("S", cell_rk(0, 0, 1.0))]))
    struct.pack_into("<H", data, 0x1E, 60000)
    with pytest.raises(XlsError, match="exponent"):
        read_xls(bytes(data))


def test_corrupted_files_only_ever_raise_xlserror() -> None:
    """The contract, held under fuzzing: 4000 corrupted files, zero non-XlsError escapes.

    Seeded, so this is a fixed corpus rather than a flaky sweep -- a test that fails on a different
    input every run gets muted rather than read.
    """
    rng = random.Random(20260812)
    base = build_xls([("S", cell_rk(0, 0, 1.0) + cell_label(1, 0, "hdr") + cell_sst(2, 0, 0))],
                     ["s"])
    escapes: list[str] = []
    for _ in range(4000):
        data = bytearray(base)
        for _ in range(rng.randint(1, 6)):
            data[rng.randrange(len(data))] = rng.randrange(256)
        try:
            read_xls(bytes(data))
        except XlsError:
            pass
        except Exception as exc:                      # broad ON PURPOSE: escapes are the finding
            escapes.append(f"{type(exc).__name__}: {exc}"[:90])
    assert not escapes, f"{len(escapes)} non-XlsError escapes, e.g. {escapes[:3]}"


# ------------------------------------------------------------------------------ number decoding ---
@pytest.mark.parametrize(
    "value",
    [0.0, 2.5, -0.01, -1234.0, 536870911.0, -536870912.0, 0.125, -0.75, 1024.0],
)
def test_rk_encodings_round_trip(value: float) -> None:
    """Covers all RK branches, including the 30-bit signed boundaries.

    The integer branch must SIGN-EXTEND: read unsigned, every negative becomes a number near 2**30
    that still looks like data, which is precisely the failure a conservation law would catch and
    an eyeball would not.
    """
    assert read_xls(build_xls([("S", cell_rk(0, 0, value))]))[0].cells[(0, 0)] == value


@pytest.mark.parametrize("value", [1234567.891, -98765.4321, 3.141592653589793, 1e300])
def test_number_records_keep_full_f64(value: float) -> None:
    assert read_xls(build_xls([("S", cell_number(0, 0, value))]))[0].cells[(0, 0)] == value


def test_mulrk_run_expands_across_columns() -> None:
    values = [1.0, 2.5, -3.75, 0.01]
    sheet = read_xls(build_xls([("S", cell_mulrk(3, 2, values))]))[0]
    assert [sheet.cells[(3, 2 + i)] for i in range(len(values))] == values
    assert (3, 1) not in sheet.cells and (3, 6) not in sheet.cells


def test_mixed_encodings_in_one_sheet() -> None:
    """RK and NUMBER cells side by side -- the property that makes a conservation law strong."""
    records = cell_rk(0, 0, 25.0) + cell_number(0, 1, 17.5) + cell_mulrk(0, 2, [7.5])
    sheet = read_xls(build_xls([("S", records)]))[0]
    assert sheet.rows() == [[25.0, 17.5, 7.5]]


# ---------------------------------------------------------------------- container-level paths ---
@pytest.mark.parametrize("pad_to", [0, 5000, 9000, 70000])
def test_mini_and_big_stream_paths(pad_to: int) -> None:
    """Streams under the 4096 B cutoff live in the miniFAT; above it, in ordinary sectors.

    A reader can implement exactly one and look correct on whichever fixtures it was written
    against -- small sheets simply vanish, with no error and no empty-file signal.
    """
    sheet = read_xls(build_xls([("S", cell_rk(0, 0, 7.25))], ["x"], pad_to=pad_to))[0]
    assert sheet.cells[(0, 0)] == 7.25


def test_unknown_records_are_skipped_by_length() -> None:
    """An undecoded opcode must cost nothing: the length prefix is authoritative."""
    records = cell_rk(0, 0, 4.0) + filler(2000) + cell_rk(1, 0, 8.0)
    sheet = read_xls(build_xls([("S", records)]))[0]
    assert sheet.cells == {(0, 0): 4.0, (1, 0): 8.0}


# -------------------------------------------------------------------------------- the refusals ---
@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("empty", b""),
        ("not ole2", b"plain text that is long enough to pass the length check" * 20),
        ("truncated header", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32),
    ],
)
def test_refuses_non_workbooks(label: str, payload: bytes) -> None:
    with pytest.raises(XlsError):
        read_xls(payload)


def test_refuses_compound_file_without_a_workbook_stream() -> None:
    with pytest.raises(XlsError, match="no Workbook stream"):
        read_xls(build_ole2({"Summary": b"x" * 40}))


def test_refuses_biff5() -> None:
    """A Book stream from Excel 5/95 has a different record layout: decoding it would be a guess."""
    book = struct.pack("<HHH", 0x0809, 4, 0x0500) + b"\x00" * 2 + struct.pack("<HH", 0x000A, 0)
    with pytest.raises(XlsError, match="unsupported BIFF version"):
        read_xls(build_ole2({"Workbook": book}))


def test_refuses_workbook_with_no_sheets() -> None:
    stream = struct.pack("<HHH", 0x0809, 2, 0x0600) + struct.pack("<HH", 0x000A, 0)
    with pytest.raises(XlsError, match="declares no sheets"):
        read_xls(build_ole2({"Workbook": stream}))


@pytest.mark.parametrize("cut", [3, 6, 1])
def test_refuses_a_truncated_stream(cut: int) -> None:
    """THE FAILURE MODE THAT NEVER THROWS.

    Cutting 1-3 bytes leaves a tail too short to be a record header, so a ``pos + 4 <= len`` walk
    simply stops -- dropping a record and returning every number before it, all of which look
    right. Truncation must refuse, not shorten.
    """
    workbook = build_workbook([("S", cell_rk(0, 0, 1.0) + cell_rk(1, 0, 2.0))])
    with pytest.raises(XlsError):
        read_xls(build_ole2({"Workbook": workbook[: len(workbook) - cut]}))


# ------------------------------------------------------------------------------ sheet accessors ---
def test_sheet_grid_helpers() -> None:
    sheet = read_xls(build_xls([("S", cell_rk(0, 0, 1.0) + cell_rk(2, 3, 9.0))]))[0]
    assert (sheet.n_rows, sheet.n_cols) == (3, 4)
    assert sheet.rows() == [
        [1.0, None, None, None],
        [None, None, None, None],
        [None, None, None, 9.0],
    ]
    assert sheet.column(3) == [None, None, 9.0]
    assert sheet.column(3, skip=2) == [9.0]


def test_empty_sheet_reports_zero_extent() -> None:
    """A sheet with no cells must read as empty rather than raising on the max() of nothing."""
    sheet = read_xls(build_xls([("S", b"")]))[0]
    assert (sheet.n_rows, sheet.n_cols, sheet.rows()) == (0, 0, [])
