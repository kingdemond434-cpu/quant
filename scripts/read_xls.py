"""Read a legacy ``.xls`` with no dependencies, and refuse to hand over numbers unvalidated.

WHY THIS SCRIPT EXISTS RATHER THAN JUST THE LIBRARY (R0317). The seats that hit ``.xls`` files are
the digger and miner seats, and they are research-frozen: they cannot write to ``scripts/``. A
library they cannot call is a capability the desk owns and cannot use, which is how the two earlier
prototypes came to rot in ``/tmp`` and be re-derived by later runs. This is the reachable surface.

THE ``--identity`` FLAG IS THE POINT, NOT A CONVENIENCE. A hand-rolled binary extractor fails by
returning a plausible grid, so "it parsed" is not evidence (OP-025). Declare an arithmetic identity
the data must satisfy from INSIDE itself -- ``PF + PJ = Subtotal`` -- and the parse is checked
against the file's own accounting rather than against how the output looks::

    python scripts/read_xls.py panel.xls --sheet 0 --skip 2 --identity "pf+pj=sub:3,4:5"

Without ``--identity`` the census is printed and the numeric dump is REFUSED, because a dump is
what feeds a research artifact and an unvalidated dump is the phantom-evidence factory itself.
Override with ``--no-validate`` when you are eyeballing an unknown file's shape, which is exactly
the case where the numbers are not yet going anywhere.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.data.xls_reader import Sheet, XlsError, read_xls  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.conservation import Identity, check_identities  # noqa: E402

_OK, _REFUSED = 0, 1


def parse_identity(spec: str) -> Identity:
    """``name:part,part,...:total[:atol]`` -- column keys are 0-based indices or column names.

    Raises rather than guessing: a malformed identity that silently becomes a weaker one would
    hand back a pass the data never earned.
    """
    fields = spec.split(":")
    if len(fields) not in (3, 4):
        raise ValueError(f"identity {spec!r} must read name:parts:total[:atol]")
    name, parts_raw, total_raw = fields[0], fields[1], fields[2]
    atol = float(fields[3]) if len(fields) == 4 else 0.0

    def key(raw: str) -> str | int:
        text = raw.strip()
        if not text:
            raise ValueError(f"identity {spec!r} has an empty column key")
        return int(text) if text.lstrip("-").isdigit() else text

    return Identity(name, tuple(key(p) for p in parts_raw.split(",")), key(total_raw), atol=atol)


def census(sheets: list[Sheet]) -> list[dict[str, Any]]:
    """What the file actually contains, per sheet.

    Printed before anything else because the failure this reader is most likely to hit is a
    workbook whose interesting table is not where the caller assumed -- and a census answers that
    in one look, rather than by eye over a dump (the OP-046 class-census discipline).
    """
    return [
        {
            "index": i,
            "name": sheet.name,
            "n_cells": len(sheet.cells),
            "n_rows": sheet.n_rows,
            "n_cols": sheet.n_cols,
        }
        for i, sheet in enumerate(sheets)
    ]


def _select(sheets: list[Sheet], wanted: str) -> Sheet:
    for i, sheet in enumerate(sheets):
        if wanted == str(i) or wanted == sheet.name:
            return sheet
    names = ", ".join(f"{i}={s.name!r}" for i, s in enumerate(sheets))
    raise ValueError(f"no sheet {wanted!r}; workbook has {names}")


def _dump(rows: list[list[object]], fmt: str, stream: Any) -> None:
    if fmt == "json":
        json.dump(rows, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
        return
    writer = csv.writer(stream)
    writer.writerows([["" if cell is None else cell for cell in row] for row in rows])


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", type=Path, help="the .xls file")
    ap.add_argument("--sheet", help="sheet index or name; omit to print only the census")
    ap.add_argument("--skip", type=int, default=0, help="header rows to drop before checking")
    ap.add_argument("--identity", action="append", default=[],
                    metavar="NAME:PARTS:TOTAL[:ATOL]",
                    help="in-data conservation law the parse must satisfy; repeatable")
    ap.add_argument("--min-rows", type=int, default=1,
                    help="rows the identity must close over before the result counts as measured")
    ap.add_argument("--format", choices=("csv", "json"), default="csv")
    ap.add_argument("--no-validate", action="store_true",
                    help="dump without an identity -- for shape-finding only, never for research")
    args = ap.parse_args()

    try:
        sheets = read_xls(args.path)
    except (XlsError, OSError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return _REFUSED

    print(f"# {args.path.name}: {len(sheets)} sheet(s)", file=sys.stderr)
    for entry in census(sheets):
        print(f"#   [{entry['index']}] {entry['name']!r}: {entry['n_cells']} cells, "
              f"{entry['n_rows']}x{entry['n_cols']}", file=sys.stderr)
    if args.sheet is None:
        return _OK

    try:
        sheet = _select(sheets, args.sheet)
        identities = [parse_identity(spec) for spec in args.identity]
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return _REFUSED

    rows = sheet.rows()
    if identities:
        report = check_identities(rows, identities, skip=args.skip, min_rows=args.min_rows)
        print(f"# conservation: {report.status} -- {report.detail}", file=sys.stderr)
        if not report.ok:
            # UNMEASURED refuses as hard as VIOLATED. "The law closed over nothing" and "the law
            # held" are opposite claims, and only one of them is evidence (L1.28a).
            for violation in report.violations[:5]:
                print(f"#   row {violation.row} {violation.identity}: "
                      f"{violation.parts_sum:.6g} vs {violation.total:.6g}", file=sys.stderr)
            return _REFUSED
    elif not args.no_validate:
        print("REFUSED: no --identity declared. A hand-rolled binary parse that 'looks right' is "
              "not validated (OP-024/OP-025); pass an in-data conservation law, or --no-validate "
              "if you are only inspecting the file's shape.", file=sys.stderr)
        return _REFUSED

    _dump(rows, args.format, sys.stdout)
    return _OK


if __name__ == "__main__":
    raise SystemExit(main())
