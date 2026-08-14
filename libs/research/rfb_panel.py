"""ERA-AWARE PARSE of the Receita Federal crypto panel, so a VINTAGE STACK can be built (R0472).

WHAT THIS IS FOR. :mod:`libs.research.vintage` can store what was knowable on date d, but R0316
started its history on 2026-08-12, so every axis needing a window that predates today is blocked on
SAMPLE, not on machinery. The RFB `criptoativos_dados_abertos_<date>.xls` series is a free
point-in-time stack (OP-047): Receita Federal republishes the WHOLE panel monthly under a dated
filename, so each release is a vintage and the older ones are still fetchable -- from the live
server while they last, and from the Wayback raw-replay modifier after they 404. This module is the
part that turns one downloaded workbook into observations keyed by reference month.

THE PARSE MUST BE BY HEADER SEMANTICS, NEVER BY CELL ADDRESS, and that is not a style preference.
Across eras of this one file the table MOVES: in the 2022-01 vintage `Relatorio1` starts at row 10
column 2, in the 2026-04 vintage at row 8 column 0. A fixed-offset reader does not fail on the other
era -- it returns a full, plausible, WRONG series, which is the OP-035-BR extension exactly. Worse,
the sibling sheet `Relatorio2` SWAPS its two count columns between eras (`CNPJ | CPF` -> `CPF |
CNPJ`), so a fixed reader there takes ~2k companies for ~160k individuals: an ~80x error that still
looks like a plausible count. :func:`locate` therefore finds every column by matching the header
TEXT, and asserts the group ORDER it found -- an era that reorders the groups REFUSES here rather
than silently mis-attributing, because a refusal is recoverable and a wrong series is not.

THE FILENAME'S DATE CONVENTION FLIPS MID-SERIES and it is the vintage key, so getting it wrong
mislabels the whole point of the exercise: `DDMMYYYY` up to 2023-09 (`04012022`, `25092023`) then
`YYYYMMDD` from 2024-10 (`20241007`, `20260415`). :func:`publication_date` does not guess by era --
it parses BOTH ways and requires exactly one to yield a real calendar date with a plausible year.
That is decidable rather than conventional: for `YYYYMMDD` to be valid its middle two digits must be
a month 01-12, which as a `DDMMYYYY` year would read 01xx-12xx, so the two readings cannot both
survive. An ambiguous or unparseable token raises instead of defaulting to today.

VALIDATION IS NOT OPTIONAL AND IT COMES FROM INSIDE THE DATA (OP-024). :func:`identities` returns
the conservation laws this table must satisfy -- `PF + PJ = Subtotal` for each of the two reporting
channels, plus the grand `Subtotal1 + Subtotal2 + Domestic = TotalGeral`. Measured over the 2022-01
and 2026-04 vintages the two `PF + PJ` laws close EXACTLY (worst residual 0.0), which is why they
carry the module's default tolerance of zero.

    from libs.research.rfb_panel import extract, publication_date
    sheets = read_xls(path)
    parsed = extract(sheets)
    publication_date("04012022")   # -> "2022-01-04", not "2022-04-01" and never today
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from libs.data.xls_reader import Sheet
from libs.research.conservation import ConservationReport, Identity, check_identities

#: R0472. What this parse guarantees about ITSELF, all refusals rather than repairs: every column is
#: found by header TEXT and never by address; the two reporting groups must appear in the order
#: PF, PJ, Subtotal twice; exactly one unlabelled column may sit between the second Subtotal and
#: Total Geral (the domestic-exchange column, which is headed in one era and bare in the other); and
#: the vintage key must be decidable from the filename under exactly one date convention. Shape
#: only -- the VALUES are checked by the conservation laws in :func:`identities`.
EXTRACTOR_INVARIANT = (
    "every column is located by header text, never by cell address; the two reporting groups must "
    "read PF, PJ, Subtotal in that order; exactly one column separates the second Subtotal from "
    "Total Geral; and the filename token must parse as a real date under exactly one of DDMMYYYY "
    "or YYYYMMDD -- paired with PF+PJ=Subtotal from inside the data for the numbers themselves"
)

#: The sheet carrying the monthly R$mn table. Both spellings are in the wild across eras.
SHEET_NAMES: Final = ("Relatorio1", "Relatório1")

_MONTHS: Final = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

#: A year outside this band is not a publication date, it is a misread filename token.
_YEAR_MIN: Final = 2000
_YEAR_MAX: Final = 2100

#: The grand identity's tolerance, and the reason it is not zero. `Total Geral` is a SUM EXCEL
#: ALREADY COMPUTED and stored, so its last bits carry the publisher's own accumulation order, not
#: ours: measured worst residual is 7.3e-12 on the 2026-04 vintage and 1.8e-12 on 2022-01, both
#: against magnitudes near 1e4. R$1e-6 million is one BRL, still a million times tighter than the
#: smallest real parse error (a swapped column moves the total by >= 1 R$mn = 1e6 of these), so the
#: law keeps its power. The two PF+PJ laws close exactly and are NOT given a tolerance.
GRAND_ATOL: Final = 1e-6

#: Value columns of the monthly table, in the order :class:`Layout` exposes them.
FIELDS: Final = (
    "exchange_pf",
    "exchange_pj",
    "exchange_subtotal",
    "noexchange_pf",
    "noexchange_pj",
    "noexchange_subtotal",
    "domestic_exchanges",
    "total_geral",
)

#: Series keys in the vintage store. Prefixed so one source's logs never collide with another's.
SERIES_PREFIX: Final = "RFB_CRIPTO"


class RfbPanelError(ValueError):
    """The workbook is not a readable RFB monthly panel.

    Raised rather than returning a partial layout: a half-located table is the outcome that passes
    a downstream sanity check while being wrong, which is the failure this module exists to avoid.
    """


def _norm(cell: object) -> str:
    """Accent-folded, case-folded, whitespace-collapsed text -- or '' for a non-string cell.

    Header matching has to survive `MÊS/ANO` vs `MES/ANO` and `Relatório` vs `Relatorio`, and the
    accents are not stable across the eras of this file.
    """
    if not isinstance(cell, str):
        return ""
    folded = unicodedata.normalize("NFKD", cell)
    stripped = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(stripped.replace("\xa0", " ").split()).strip("'\" ").lower()


def publication_date(token: str) -> str:
    """The vintage date encoded in a filename token, as ISO -- REFUSING when it is ambiguous.

    This is the key every recovered observation is stored under, so a wrong answer here does not
    corrupt one field, it mislabels an entire vintage and inverts the revision it was fetched to
    measure. Both conventions are tried and exactly one must survive.
    """
    digits = token.strip()
    if len(digits) != 8 or not digits.isdigit():
        raise RfbPanelError(f"filename token {token!r} is not 8 digits -- cannot date the vintage")

    readings: dict[str, date] = {}
    for name, (y, m, d) in (
        ("YYYYMMDD", (digits[0:4], digits[4:6], digits[6:8])),
        ("DDMMYYYY", (digits[4:8], digits[2:4], digits[0:2])),
    ):
        year = int(y)
        if not _YEAR_MIN <= year <= _YEAR_MAX:
            continue
        try:
            readings[name] = date(year, int(m), int(d))
        except ValueError:
            continue
    if len(readings) != 1:
        raise RfbPanelError(
            f"filename token {token!r} parses as {sorted(readings) or 'neither'} convention "
            f"-- the vintage date must be decidable, never defaulted"
        )
    return next(iter(readings.values())).isoformat()


def parse_period(cell: object) -> str | None:
    """``'Agosto de 2019'`` -> ``'2019-08'``; anything that is not a month label -> ``None``.

    Returning ``None`` rather than raising is deliberate: a real sheet carries headers, blanks and
    footnotes between its data rows, and the caller counts what it skipped (L1.60) instead of this
    function deciding a footnote is a fatal error.
    """
    text = _norm(cell)
    if " de " not in text:
        return None
    name, _, year = text.partition(" de ")
    month = _MONTHS.get(name.strip())
    if month is None or not year.strip().isdigit():
        return None
    value = int(year.strip())
    if not _YEAR_MIN <= value <= _YEAR_MAX:
        return None
    return f"{value:04d}-{month:02d}"


@dataclass(frozen=True)
class Layout:
    """Where the monthly table actually sits in THIS vintage -- every field found by header text."""

    header_row: int
    group_row: int
    first_data_row: int
    period_col: int
    columns: dict[str, int]

    def column(self, field: str) -> int:
        return self.columns[field]


def _find_cell(grid: list[list[object]], wanted: str) -> tuple[int, int] | None:
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if _norm(cell) == wanted:
                return r, c
    return None


def locate(sheet: Sheet) -> Layout:
    """Find the monthly table by its headers, refusing any era whose group order differs.

    The two group headers repeat (`PF`, `PJ`, `Subtotal` for exchange use and again for
    peer-to-peer), so position WITHIN the row is what tells them apart -- and asserting that order
    is what makes a silent re-ordering impossible.
    """
    grid = sheet.rows()
    found = _find_cell(grid, "mes/ano")
    if found is None:
        raise RfbPanelError("no 'MES/ANO' header cell -- this is not the RFB monthly panel sheet")
    header_row, period_col = found

    group_row = -1
    cols: dict[str, list[int]] = {}
    for r in range(header_row + 1, min(header_row + 6, len(grid))):
        seen: dict[str, list[int]] = {"pf": [], "pj": [], "subtotal": []}
        for c, cell in enumerate(grid[r]):
            key = _norm(cell)
            if key in seen:
                seen[key].append(c)
        if len(seen["pf"]) == 2 and len(seen["pj"]) == 2 and len(seen["subtotal"]) == 2:
            group_row, cols = r, seen
            break
    if group_row < 0:
        raise RfbPanelError(
            "no row carries exactly two each of PF / PJ / Subtotal -- the two reporting groups "
            "could not be identified, so no column may be trusted"
        )

    ordered = [
        cols["pf"][0], cols["pj"][0], cols["subtotal"][0],
        cols["pf"][1], cols["pj"][1], cols["subtotal"][1],
    ]
    if ordered != sorted(ordered):
        raise RfbPanelError(
            f"reporting-group columns are not in PF, PJ, Subtotal order twice (got {ordered}) -- "
            "an era that reorders them must be read deliberately, never inferred"
        )

    total = _find_cell(grid, "total geral")
    if total is None:
        raise RfbPanelError("no 'Total Geral' header cell -- the grand identity cannot be checked")
    total_col = total[1]

    between = list(range(ordered[-1] + 1, total_col))
    if len(between) != 1:
        raise RfbPanelError(
            f"expected exactly one domestic-exchange column between the second Subtotal "
            f"(col {ordered[-1]}) and Total Geral (col {total_col}), found {len(between)}"
        )

    columns = dict(zip(FIELDS, [*ordered, between[0], total_col], strict=True))
    return Layout(
        header_row=header_row,
        group_row=group_row,
        first_data_row=group_row + 1,
        period_col=period_col,
        columns=columns,
    )


def identities(layout: Layout) -> tuple[Identity, ...]:
    """The in-data conservation laws this table must satisfy, keyed to THIS vintage's columns."""
    return (
        Identity(
            "pf+pj=subtotal_exchange",
            (layout.column("exchange_pf"), layout.column("exchange_pj")),
            layout.column("exchange_subtotal"),
        ),
        Identity(
            "pf+pj=subtotal_noexchange",
            (layout.column("noexchange_pf"), layout.column("noexchange_pj")),
            layout.column("noexchange_subtotal"),
        ),
        Identity(
            "subtotals+domestic=total_geral",
            (
                layout.column("exchange_subtotal"),
                layout.column("noexchange_subtotal"),
                layout.column("domestic_exchanges"),
            ),
            layout.column("total_geral"),
            atol=GRAND_ATOL,
        ),
    )


def _number(cell: object) -> float | None:
    """A cell's numeric value, or ``None``.

    STRINGS ARE REFUSED, NOT COERCED, and that is the safe direction. One era of this file writes
    counts as text with Brazilian separators (`160.589`), where `.` is a THOUSANDS mark -- so
    `float()` would read 160589 as 160.589, a 1000x error that still looks like a number. A refused
    cell makes its row unusable and the caller reports how many rows it lost (L1.60); a coerced one
    is silently wrong.
    """
    if isinstance(cell, bool) or not isinstance(cell, int | float):
        return None
    return float(cell)


@dataclass(frozen=True)
class ParsedPanel:
    """One vintage's monthly table: where it was found, what it says, and what it refused."""

    layout: Layout
    observations: dict[str, dict[str, float]]
    conservation: ConservationReport
    n_data_rows: int
    n_period_rows: int
    n_dropped_rows: int

    @property
    def n_periods(self) -> int:
        return len(self.observations.get(f"{SERIES_PREFIX}_TOTAL_GERAL", {}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "header_row": self.layout.header_row,
            "group_row": self.layout.group_row,
            "period_col": self.layout.period_col,
            "columns": dict(self.layout.columns),
            "n_data_rows": self.n_data_rows,
            "n_period_rows": self.n_period_rows,
            "n_dropped_rows": self.n_dropped_rows,
            "n_periods": self.n_periods,
            "n_series": len(self.observations),
            "conservation": self.conservation.as_dict(),
        }


def select_sheet(sheets: list[Sheet]) -> Sheet:
    """The monthly-table sheet, BY NAME. Index selection would drift with the workbook's layout."""
    wanted = {_norm(name) for name in SHEET_NAMES}
    for sheet in sheets:
        if _norm(sheet.name) in wanted:
            return sheet
    names = ", ".join(repr(s.name) for s in sheets)
    raise RfbPanelError(f"no sheet named one of {SHEET_NAMES}; workbook has {names}")


def extract(sheets: list[Sheet], *, min_rows: int = 12) -> ParsedPanel:
    """Parse one vintage's monthly panel and validate it against the data's own arithmetic.

    ``min_rows`` is the floor below which the conservation result is ``UNMEASURED`` rather than
    ``OK``: the shortest genuine vintage of this file carries 28 monthly rows, so a parse that
    closes over a handful is reporting on its own breakage, not on the source.
    """
    sheet = select_sheet(sheets)
    layout = locate(sheet)
    grid = sheet.rows()
    body = grid[layout.first_data_row :]

    observations: dict[str, dict[str, float]] = {
        f"{SERIES_PREFIX}_{field.upper()}": {} for field in FIELDS
    }
    n_period_rows = 0
    for row in body:
        period = parse_period(row[layout.period_col] if layout.period_col < len(row) else None)
        if period is None:
            continue
        n_period_rows += 1
        for field in FIELDS:
            col = layout.column(field)
            value = _number(row[col]) if col < len(row) else None
            if value is not None:
                observations[f"{SERIES_PREFIX}_{field.upper()}"][period] = value

    report = check_identities(
        grid, identities(layout), skip=layout.first_data_row, min_rows=min_rows
    )
    return ParsedPanel(
        layout=layout,
        observations=observations,
        conservation=report,
        n_data_rows=len(body),
        n_period_rows=n_period_rows,
        n_dropped_rows=len(body) - n_period_rows,
    )
