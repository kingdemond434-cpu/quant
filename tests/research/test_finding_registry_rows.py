"""THE REGISTER'S PARSER IS HELD AGAINST THE REGISTER ITSELF, NOT AGAINST A FIXTURE.

WHY THIS FILE EXISTS. `docs/GAP_REGISTER.md` is the only organ on this desk that drives work to
completion, and `finding_registry.parse_register` is the only way anything reads it:
`max_audit.check_gap_register_health`, `scripts/rerank_gaps.py`, `research_cycle` and the
strategic director's dossier all go through it. On 2026-09-24 that parser saw **121 of 225**
rows, and the 100 it missed were ids 130-212 almost without a break -- every row the MT5 desk has
opened since the pivot. The re-rank re-ranked the retired crypto backlog. The health check
reported on it. Neither said so, because a row the expression cannot match is not an error; it is
an absence, and absence read green (WS-005).

A hand-written fixture could never have caught that, because a fixture is written by the same
person who writes the expression and carries the same assumptions about what a row looks like.
So the oracle here is the REAL FILE, split on pipes by a rule with no assumptions in it at all,
and the test is that the two agree. When a future session writes a row shape the expression
cannot read, this fails instead of the row disappearing.

THE COVERAGE FLOOR RATCHETS UP ONLY (L1.50). `MIN_PARSED_FRACTION` is a floor under how much of
its own queue the desk can see. Lower it and the suite fails; that is the point.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from libs.research.finding_registry import parse_register

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "GAP_REGISTER.md"

#: Any line that OPENS like a register row, judged with no knowledge of the rest of the shape.
_LOOKS_LIKE_A_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*\*\*", re.MULTILINE)

#: The floor, measured 2026-09-24 at 210/225 = 93.3%. The 15 below it are rows whose CELL COUNT
#: is wrong (a 4-column row under a 7-column header, or an 8th column the header never defined) --
#: a defect in the file, not in the expression, and one no regex should paper over.
MIN_PARSED_FRACTION = 0.93


def _rows_that_look_like_rows(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if _LOOKS_LIKE_A_ROW.match(ln)]


@pytest.fixture(scope="module")
def register_text() -> str:
    if not REGISTER.exists():                       # pragma: no cover - the file is tracked
        pytest.skip("GAP_REGISTER.md is absent on this checkout")
    return REGISTER.read_text(encoding="utf-8")


def test_parser_sees_almost_every_row_in_the_live_register(register_text: str) -> None:
    """The floor under how much of its own work queue this desk can read."""
    looks = _rows_that_look_like_rows(register_text)
    parsed = parse_register(register_text)
    assert looks, "the register has no rows at all, which is itself the alarm"
    fraction = len(parsed) / len(looks)
    assert fraction >= MIN_PARSED_FRACTION, (
        f"parse_register reads {len(parsed)} of {len(looks)} rows ({fraction:.1%}); the floor is "
        f"{MIN_PARSED_FRACTION:.0%}. A row the parser cannot see is a row the re-rank, the health "
        f"check and the director's dossier all silently omit."
    )


def test_parser_agrees_with_a_naive_pipe_split_on_every_well_formed_row(
    register_text: str,
) -> None:
    """The oracle: a 7-cell row split on `|` carries owner/added/status in fixed positions.

    This is the test that would have caught the original defect. It makes no claim about what an
    owner may contain -- it reads the cell and demands the expression read the same one.
    """
    parsed = {}
    for row in parse_register(register_text):
        parsed.setdefault(row.row_id, []).append(row)

    checked = 0
    problems: list[str] = []
    for line in _rows_that_look_like_rows(register_text):
        cells = line.split("|")
        if len(cells) != 9:          # not a well-formed 7-column row; covered by the test below
            continue
        checked += 1
        row_id = int(cells[1].strip())
        owner, added, status = (cells[-4].strip(), cells[-3].strip(), cells[-2].strip())
        candidates = parsed.get(row_id, [])
        if not candidates:
            problems.append(f"row {row_id}: well-formed but the parser never saw it")
            continue
        # Ids are NOT unique -- a 2026-08-04 merge unioned two lineages without renumbering -- so
        # agreement means "some parsed row for this id matches these cells", never "the first".
        if not any(r.owner == owner and r.status == status
                   and added.startswith(r.added) and r.added for r in candidates):
            problems.append(
                f"row {row_id}: file says owner={owner!r} added={added[:12]!r} status={status!r}; "
                f"parser produced {[(r.owner, r.added, r.status) for r in candidates]}")

    assert checked > 100, f"only {checked} well-formed rows found; the oracle is not exercising"
    assert not problems, "parser disagrees with the file on:\n  " + "\n  ".join(problems[:20])


def test_every_row_the_parser_misses_is_a_malformed_cell_count(register_text: str) -> None:
    """The residual is NAMED, so it cannot quietly grow.

    A row the parser misses is acceptable only when the FILE is wrong about its own shape. If a
    9-cell row ever stops parsing, that is the expression's fault and this fails.
    """
    seen = {row.row_id for row in parse_register(register_text)}
    missed_but_well_formed = [
        int(line.split("|")[1].strip())
        for line in _rows_that_look_like_rows(register_text)
        if len(line.split("|")) == 9 and int(line.split("|")[1].strip()) not in seen
    ]
    assert not missed_but_well_formed, (
        f"these rows are shaped correctly and the parser still cannot read them: "
        f"{sorted(set(missed_but_well_formed))}")


def test_the_modern_mt5_rows_are_visible(register_text: str) -> None:
    """The specific regression: ids past 160 are this desk's LIVE queue.

    The original expression could read none of them, because every one is owned by `gap-fixer`,
    `gap-wirer`, `cro-cycle`, `box-session` or nobody -- and its owner class admitted no hyphen
    and no em-dash. A register whose live half is unreadable reports health about a retired desk.
    """
    modern = {row.row_id for row in parse_register(register_text) if row.row_id >= 160}
    assert len(modern) >= 30, (
        f"only {len(modern)} rows past id 160 are readable; the MT5 era is the part of this "
        f"register that is still true")


def test_owner_is_never_confused_with_the_date_cell(register_text: str) -> None:
    """The reason the owner class excludes digits, pinned as a property.

    `added` is date-shaped and may be empty, so an owner class admitting digits could let the two
    cells trade places and produce a confident wrong split rather than a miss.
    """
    for row in parse_register(register_text):
        assert not any(ch.isdigit() for ch in row.owner), (
            f"row {row.row_id}: owner {row.owner!r} contains a digit, which means the expression "
            f"has taken the Added cell for the Owner cell")
