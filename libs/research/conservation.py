"""IN-DATA CONSERVATION LAWS -- validating an extractor against the data itself (OP-024, R0318).

THE PROBLEM THIS SOLVES IS NOT "IS THE PARSER BUGGY". It is "how would I KNOW". A hand-rolled
extractor -- a byte-level ``.xls`` or PDF reader, a scraped table, a reconstructed panel -- fails in
a characteristic way: it does not crash, it returns a grid that looks entirely plausible, and every
downstream number is wrong. The original OP-046 run hit exactly that. Keying cells on ``(row, col)``
merged five sheets into one grid and produced a row reading ``CRIPTOATIVO | MES/ANO | ... | 899.79
| 990.46`` -- one report's header spliced onto another report's numbers. Nothing about it looked
wrong. What caught it was arithmetic: the columns stopped adding up.

WHY AN IN-DATA IDENTITY BEATS DIFFING A SECOND SOURCE. The obvious validation is to diff the
``.xls``
against its PDF twin, but that needs a SECOND unvalidated extractor (the PDF's text layer was
CID-encoded), so agreement between them is agreement between two suspects. An identity taken from
INSIDE the data needs nothing external, and it is strictly stronger evidence when it spans
independent column groups AND independent encodings: on the Receita Federal panel, ``PF + PJ =
Subtotal`` and ``Subtotal1 + Subtotal2 + Domestic = TotalGeral`` held over 78 monthly rows with a
worst residual of exactly ``0.00e+00``, across both RK- and NUMBER-encoded cells -- so a decoder bug
in either encoding could not have cancelled. OP-008 compares two SOURCES; this checks one source
against ITSELF. Run both when you have both.

THE THREE REFUSALS, and they are the whole design:

  1. ZERO USABLE ROWS IS ``UNMEASURED``, NEVER ``OK`` (L1.28a). ``all([])`` is ``True``, so an
     extractor that returned nothing but headers -- or nothing at all -- passes a naive check with
     "0 violations" and the report reads as health. The count of rows the law actually closed over
     is a first-class output, not a footnote (L1.57).

  2. NON-NUMERIC ROWS ARE COUNTED, NOT SILENTLY DROPPED. A real sheet has headers, blanks and
     footnotes, so skipping unusable rows is necessary -- but a run where 900 of 978 rows were
     skipped is a different claim from one where 78 of 78 closed, and only reporting both keeps
     those distinguishable.

  3. THE DEFAULT TOLERANCE IS EXACTLY ZERO. A residual you can EXPLAIN to the last unit is stronger
     verification than a small residual waved through (OP-024). Pass ``atol`` only with a reason --
     published figures rounded to the unit are the legitimate case, a parser you cannot get to
     close is not.

    from libs.research.conservation import Identity, check_identities
    rep = check_identities(sheet.rows(), [Identity("pf+pj=sub", (3, 4), 5)], skip=2)
    assert rep.status == "OK", rep.detail
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

#: Statuses that mean the law was actually exercised and held. Everything else is a refusal.
PASSING: Final = frozenset({"OK"})

Key = str | int
Row = Mapping[str, object] | Sequence[object]


@dataclass(frozen=True)
class Identity:
    """An arithmetic law the data must satisfy: ``sum(parts) == total``, row by row.

    Keys are column names for mapping rows, or 0-based indices for positional rows -- so a grid
    straight out of :func:`libs.data.xls_reader.Sheet.rows` can be checked with no conversion step,
    which matters because the conversion step is itself a place to introduce the bug.
    """

    name: str
    parts: tuple[Key, ...]
    total: Key
    atol: float = 0.0

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError(f"identity {self.name!r} has no parts to sum")
        if self.atol < 0.0:
            raise ValueError(f"identity {self.name!r} has a negative tolerance")


@dataclass(frozen=True)
class Violation:
    identity: str
    row: int
    parts_sum: float
    total: float

    @property
    def residual(self) -> float:
        return self.parts_sum - self.total


@dataclass(frozen=True)
class ConservationReport:
    """What the law closed over, what it refused, and how badly it failed at worst."""

    status: str
    n_rows: int
    n_usable: int
    n_checks: int
    n_violations: int
    worst_residual: float
    identities: tuple[str, ...] = ()
    violations: tuple[Violation, ...] = ()
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in PASSING

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "n_rows": self.n_rows,
            "n_usable": self.n_usable,
            "n_checks": self.n_checks,
            "n_violations": self.n_violations,
            "worst_residual": self.worst_residual,
            "identities": list(self.identities),
            "detail": self.detail,
        }


@dataclass
class _Tally:
    usable: int = 0
    checks: int = 0
    worst: float = 0.0
    violations: list[Violation] = field(default_factory=list)


def _value(row: Row, key: Key) -> float | None:
    """Coerce one cell to a float, or ``None`` when it is not a number.

    ``bool`` is rejected on purpose: ``True + True == 2`` would let a column of flags satisfy a
    sum identity and report a clean parse.
    """
    try:
        raw = row[key] if isinstance(row, Mapping) else row[int(key)]  # type: ignore[index]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    value = float(raw)
    return None if math.isnan(value) or math.isinf(value) else value


def check_identities(
    rows: Sequence[Row],
    identities: Sequence[Identity],
    *,
    skip: int = 0,
    min_rows: int = 1,
) -> ConservationReport:
    """Check every identity against every row, refusing to grade an empty or unusable input.

    ``skip`` drops leading header rows. ``min_rows`` is the floor below which the result is
    ``UNMEASURED`` rather than ``OK`` -- raise it when the source's real shape is known, because
    "the law held on the 2 rows that parsed" is not evidence the other 76 did.
    """
    if not identities:
        return ConservationReport(
            status="UNMEASURED",
            n_rows=len(rows),
            n_usable=0,
            n_checks=0,
            n_violations=0,
            worst_residual=0.0,
            detail="no identity declared -- an extractor with no in-data law is unvalidated",
        )

    body = list(rows)[skip:]
    tally = _Tally()
    for index, row in enumerate(body):
        row_usable = False
        for identity in identities:
            parts = [_value(row, key) for key in identity.parts]
            total = _value(row, identity.total)
            if total is None or any(part is None for part in parts):
                continue
            row_usable = True
            tally.checks += 1
            parts_sum = math.fsum(part for part in parts if part is not None)
            residual = abs(parts_sum - total)
            tally.worst = max(tally.worst, residual)
            if residual > identity.atol:
                tally.violations.append(
                    Violation(identity.name, index + skip, parts_sum, total)
                )
        tally.usable += int(row_usable)

    names = tuple(identity.name for identity in identities)
    common = {
        "n_rows": len(rows),
        "n_usable": tally.usable,
        "n_checks": tally.checks,
        "n_violations": len(tally.violations),
        "worst_residual": tally.worst,
        "identities": names,
        "violations": tuple(tally.violations),
    }
    if tally.usable < max(min_rows, 1):
        return ConservationReport(
            status="UNMEASURED",
            detail=(
                f"only {tally.usable} row(s) carried numbers in every declared column "
                f"(floor {max(min_rows, 1)}) -- the law closed over nothing, which is not a pass"
            ),
            **common,  # type: ignore[arg-type]
        )
    if tally.violations:
        worst = max(tally.violations, key=lambda v: abs(v.residual))
        return ConservationReport(
            status="VIOLATED",
            detail=(
                f"{len(tally.violations)} of {tally.checks} checks failed; worst is "
                f"{worst.identity!r} at row {worst.row}: parts sum to {worst.parts_sum:.6g} "
                f"but the total reads {worst.total:.6g} (residual {worst.residual:.6g})"
            ),
            **common,  # type: ignore[arg-type]
        )
    return ConservationReport(
        status="OK",
        detail=(
            f"{tally.checks} checks over {tally.usable} usable rows, {len(names)} "
            f"identit{'y' if len(names) == 1 else 'ies'}, worst residual {tally.worst:.2e}"
        ),
        **common,  # type: ignore[arg-type]
    )
