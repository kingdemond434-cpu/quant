"""Tests for in-data conservation laws (R0318, OP-024).

THE REFUSALS ARE THE POINT, so they get more tests than the happy path. A conservation check that
returns ``OK`` when it closed over nothing is worse than no check at all: it converts "we did not
verify this" into "we verified this", and the report reads as health either way. ``all([])`` is
``True``, which is exactly how an extractor that returned nothing but headers earns a clean bill.
"""

from __future__ import annotations

import json
import math

import pytest

from libs.research.conservation import Identity, check_identities

# PF + PJ = Subtotal, the shape the Receita Federal panel actually had.
_PF_PJ = Identity("pf+pj=sub", (0, 1), 2)
_HEADER = ["pessoa fisica", "pessoa juridica", "subtotal"]


def _rows(*body: list[object]) -> list[list[object]]:
    return [_HEADER, *body]


def test_clean_panel_passes_and_reports_its_denominator() -> None:
    report = check_identities(_rows([1.0, 2.0, 3.0], [4.0, 5.0, 9.0]), [_PF_PJ], skip=1)
    assert report.status == "OK"
    assert report.ok
    assert (report.n_usable, report.n_checks, report.n_violations) == (2, 2, 0)
    assert report.worst_residual == 0.0


def test_violation_names_the_worst_row() -> None:
    report = check_identities(
        _rows([1.0, 2.0, 3.0], [4.0, 5.0, 9.5], [10.0, 10.0, 40.0]), [_PF_PJ], skip=1
    )
    assert report.status == "VIOLATED"
    assert not report.ok
    assert report.n_violations == 2
    assert report.worst_residual == 20.0
    assert "row 3" in report.detail  # the -20.0 row, index counted in the ORIGINAL grid
    assert report.violations[-1].residual == -20.0


# ------------------------------------------------------------------------------- the refusals ---
@pytest.mark.parametrize(
    ("label", "rows", "kwargs"),
    [
        ("no rows at all", [], {}),
        ("headers only", [_HEADER], {}),
        ("every row non-numeric", [_HEADER, ["n/a", "n/a", "n/a"]], {}),
        ("total column missing", [_HEADER, [1.0, 2.0, None]], {}),
    ],
)
def test_zero_usable_rows_is_unmeasured_never_ok(
    label: str, rows: list[list[object]], kwargs: dict[str, int]
) -> None:
    report = check_identities(rows, [_PF_PJ], skip=1, **kwargs)
    assert report.status == "UNMEASURED", label
    assert not report.ok
    assert report.n_violations == 0  # zero violations, and that is NOT a pass


def test_declaring_no_identity_is_unmeasured() -> None:
    """An extractor with no in-data law is unvalidated, not validated-and-clean."""
    report = check_identities(_rows([1.0, 2.0, 3.0]), [], skip=1)
    assert report.status == "UNMEASURED"
    assert "no identity declared" in report.detail


def test_min_rows_floor_refuses_a_thin_sample() -> None:
    """"The law held on the 2 rows that parsed" is not evidence about the other 76."""
    rows = _rows([1.0, 2.0, 3.0], [4.0, 5.0, 9.0])
    assert check_identities(rows, [_PF_PJ], skip=1, min_rows=2).status == "OK"
    thin = check_identities(rows, [_PF_PJ], skip=1, min_rows=78)
    assert thin.status == "UNMEASURED"
    assert thin.n_usable == 2 and "floor 78" in thin.detail


def test_skipped_rows_are_counted_not_hidden() -> None:
    """78 of 78 closing is a different claim from 2 of 978, and both must stay legible."""
    body: list[list[object]] = [["header text", "x", "y"]] * 20 + [[1.0, 2.0, 3.0]]
    report = check_identities(_rows(*body), [_PF_PJ], skip=1)
    assert report.status == "OK"
    assert report.n_rows == 22
    assert report.n_usable == 1


# --------------------------------------------------------------------- what counts as a number ---
def test_booleans_are_not_numbers() -> None:
    """``True + True == 2``, so a column of flags would otherwise satisfy a sum identity."""
    report = check_identities(_rows([True, True, 2.0]), [_PF_PJ], skip=1)
    assert report.status == "UNMEASURED"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nan_and_inf_are_not_numbers(bad: float) -> None:
    report = check_identities(_rows([1.0, bad, 3.0]), [_PF_PJ], skip=1)
    assert report.status == "UNMEASURED"


def test_strings_that_look_numeric_are_still_not_numbers() -> None:
    """A parser that returns "1.234,56" unconverted must not be silently coerced into passing."""
    report = check_identities(_rows(["1.0", "2.0", "3.0"]), [_PF_PJ], skip=1)
    assert report.status == "UNMEASURED"


# ------------------------------------------------------------------------ shapes and tolerance ---
def test_mapping_rows_are_keyed_by_column_name() -> None:
    identity = Identity("pf+pj=sub", ("pf", "pj"), "sub")
    rows = [{"pf": 1.0, "pj": 2.0, "sub": 3.0}, {"pf": 4.0, "pj": 5.0, "sub": 9.0}]
    assert check_identities(rows, [identity]).status == "OK"


def test_missing_mapping_key_is_unusable_not_a_violation() -> None:
    identity = Identity("pf+pj=sub", ("pf", "pj"), "sub")
    report = check_identities([{"pf": 1.0, "pj": 2.0}], [identity])
    assert report.status == "UNMEASURED"


def test_default_tolerance_is_exactly_zero() -> None:
    """A residual you can explain to the last unit beats a small one waved through."""
    report = check_identities(_rows([1.0, 2.0, 3.000000001]), [_PF_PJ], skip=1)
    assert report.status == "VIOLATED"


def test_tolerance_is_honoured_when_declared() -> None:
    identity = Identity("rounded", (0, 1), 2, atol=0.5)
    assert check_identities(_rows([1.0, 2.0, 3.4]), [identity], skip=1).status == "OK"
    assert check_identities(_rows([1.0, 2.0, 3.6]), [identity], skip=1).status == "VIOLATED"


def test_several_identities_are_all_reported() -> None:
    """Spanning independent column groups is what makes a decoder bug unable to cancel."""
    rows = [[1.0, 2.0, 3.0, 10.0, 13.0]]
    identities = [Identity("inner", (0, 1), 2), Identity("outer", (2, 3), 4)]
    report = check_identities(rows, identities)
    assert report.status == "OK"
    assert report.n_checks == 2
    assert report.identities == ("inner", "outer")


def test_identity_rejects_an_empty_part_list() -> None:
    with pytest.raises(ValueError, match="no parts"):
        Identity("empty", (), 1)


def test_identity_rejects_a_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="negative tolerance"):
        Identity("bad", (0,), 1, atol=-1.0)


def test_report_serialises_for_an_artifact() -> None:
    report = check_identities(_rows([1.0, 2.0, 3.0]), [_PF_PJ], skip=1)
    payload = report.as_dict()
    assert payload["status"] == "OK"
    assert payload["n_usable"] == 1
    assert payload["identities"] == ["pf+pj=sub"]
    # The denominator has to survive into the artifact: a stored verdict with no record of what
    # it closed over cannot be re-audited later (L1.57).
    assert set(payload) >= {"n_rows", "n_usable", "n_checks", "n_violations", "worst_residual"}
    assert json.loads(json.dumps(payload))["worst_residual"] == 0.0


def test_float_summation_does_not_manufacture_a_violation() -> None:
    """0.1 + 0.2 != 0.3 in binary; fsum keeps the check from failing on its own arithmetic."""
    report = check_identities([[0.1, 0.2, 0.30000000000000004]], [_PF_PJ])
    assert report.status == "OK"
