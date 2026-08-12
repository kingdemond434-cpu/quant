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

import struct

import pytest
from tests.data.xls_builder import (
    build_ole2,
    build_workbook,
    build_xls,
    cell_mulrk,
    cell_number,
    cell_rk,
    cell_sst,
    encode_sst,
    filler,
)

from libs.data.xls_reader import XlsError, read_xls

# Two sheets, same coordinates, different values: the shape a merged grid cannot fake.
_COLLIDING = [("Alpha", cell_rk(0, 0, 111.0)), ("Beta", cell_rk(0, 0, 222.0))]

# Long enough to be split by a small cap, and mixed-width so the repeated flag byte can FLIP.
_STRINGS = ["alpha" * 12, "Relatorio de Criptoativos ção", "beta" * 15]


def _string_sheet() -> list[tuple[str, bytes]]:
    return [("S", b"".join(cell_sst(i, 0, i) for i in range(len(_STRINGS))))]


# ------------------------------------------------------------------ the fixture's own controls ---
def test_fixture_can_express_sheet_collision() -> None:
    """Bug (a) is only witnessed if the two sheets genuinely overlap -- assert that, not assume."""
    assert _COLLIDING[0][1] != _COLLIDING[1][1]
    sheets = read_xls(build_xls(_COLLIDING))
    coords = [set(sheet.cells) for sheet in sheets]
    assert coords[0] == coords[1] == {(0, 0)}, "sheets must occupy the SAME cell to express a merge"


@pytest.mark.parametrize("cap", [40, 64, 97])
def test_fixture_can_express_sst_split(cap: int) -> None:
    """Bug (b) is only witnessed if the table actually spans CONTINUE records."""
    assert len(encode_sst(_STRINGS, cap)) > 1, f"cap {cap} forced no split -- fixture is inert"


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


@pytest.mark.parametrize("cap", [40, 64, 97, 8216])
def test_shared_strings_survive_continue_boundaries(cap: int) -> None:
    """The repeated option flag at each boundary must be consumed, never read as a character."""
    sheet = read_xls(build_xls(_string_sheet(), _STRINGS, sst_max_payload=cap))[0]
    assert [sheet.cells[(i, 0)] for i in range(len(_STRINGS))] == _STRINGS


def test_wide_string_round_trips() -> None:
    """A non-latin-1 string forces the wide (UTF-16) branch."""
    strings = ["交易所", "ascii"]
    sheets = read_xls(
        build_xls([("S", cell_sst(0, 0, 0) + cell_sst(1, 0, 1))], strings, sst_max_payload=24)
    )
    assert [sheets[0].cells[(i, 0)] for i in range(2)] == strings


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
