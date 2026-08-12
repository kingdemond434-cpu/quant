"""Tests for the ``read_xls`` CLI (R0317/R0318) -- mostly about what it REFUSES to hand over.

The dump is the thing that reaches a research artifact, so the interesting behaviour is the gate
in front of it, not the formatting behind it. A parse that "looks right" is the phantom-evidence
factory OP-025 warns about, and the only defence that survives contact with a plausible-but-wrong
grid is an arithmetic law taken from inside the data.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from tests.data.xls_builder import build_xls, cell_number, cell_rk, cell_sst

_ROOT = Path(__file__).resolve().parents[2]


def _load_cli():  # type: ignore[no-untyped-def]
    """Import ``scripts/read_xls.py`` by path -- ``scripts/`` is not an importable package."""
    spec = importlib.util.spec_from_file_location("read_xls_cli", _ROOT / "scripts" / "read_xls.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _panel(subtotal_of=lambda pf, pj: pf + pj) -> bytes:  # type: ignore[no-untyped-def]
    """A PF/PJ/Subtotal panel, with the total deliberately parameterised.

    ``subtotal_of`` is how a WRONG parse is simulated: the grid stays entirely plausible and only
    the accounting stops closing, which is exactly the shape of the sheet-collision bug.
    """
    records = cell_sst(0, 0, 0) + cell_sst(0, 1, 1) + cell_sst(0, 2, 2)
    for i, (pf, pj) in enumerate([(1200.0, 3400.0), (15828.5, 6471.5)], start=1):
        # Mixed encodings on purpose: a decoder bug in RK or NUMBER alone then cannot cancel.
        total = subtotal_of(pf, pj)
        records += cell_number(i, 0, pf) + cell_rk(i, 1, pj) + cell_number(i, 2, total)
    return build_xls([("Criptoativos", records), ("Notas", cell_sst(0, 0, 3))],
                     ["PF", "PJ", "Subtotal", "fonte"])


@pytest.fixture
def panel(tmp_path: Path) -> Path:
    path = tmp_path / "panel.xls"
    path.write_bytes(_panel())
    return path


def _run(args: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["read_xls.py", *args])
    return int(cli.main())


# ------------------------------------------------------------------------------- the refusals ---
def test_dump_without_an_identity_is_refused(panel: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default must be refusal: an unvalidated dump is what feeds a phantom finding."""
    assert _run([str(panel), "--sheet", "0"], monkeypatch) == 1


def test_violated_identity_refuses_the_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE NEGATIVE CONTROL. A plausible grid whose accounting does not close must not be dumped."""
    corrupt = tmp_path / "corrupt.xls"
    corrupt.write_bytes(_panel(subtotal_of=lambda pf, pj: pf + pj + 0.5))
    assert _run([str(corrupt), "--sheet", "0", "--skip", "1", "--identity", "s:0,1:2"],
                monkeypatch) == 1
    assert "VIOLATED" in capsys.readouterr().err


def test_unmeasured_refuses_as_hard_as_violated(
    panel: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A law that closed over nothing is not a law that held (L1.28a)."""
    assert _run([str(panel), "--sheet", "0", "--skip", "1", "--identity", "s:0,1:2",
                 "--min-rows", "78"], monkeypatch) == 1
    assert "UNMEASURED" in capsys.readouterr().err


def test_unreadable_file_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = tmp_path / "not.xls"
    bad.write_bytes(b"plain text" * 100)
    assert _run([str(bad)], monkeypatch) == 1


def test_missing_file_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run([str(tmp_path / "absent.xls")], monkeypatch) == 1


def test_unknown_sheet_is_refused(panel: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run([str(panel), "--sheet", "Ausente"], monkeypatch) == 1


@pytest.mark.parametrize("spec", ["nototal", "n:0,1", "n::2", "n:0,1:2:3:4"])
def test_malformed_identity_is_refused(
    panel: Path, monkeypatch: pytest.MonkeyPatch, spec: str
) -> None:
    """A malformed law must raise, never silently degrade into a weaker one that passes."""
    assert _run([str(panel), "--sheet", "0", "--identity", spec], monkeypatch) == 1


# ----------------------------------------------------------------------------- what it allows ---
def test_validated_dump_emits_csv(
    panel: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(panel), "--sheet", "Criptoativos", "--skip", "1", "--identity", "s:0,1:2"],
                monkeypatch) == 0
    captured = capsys.readouterr()
    assert "OK" in captured.err
    assert "1200.0,3400.0,4600.0" in captured.out
    assert "15828.5,6471.5,22300.0" in captured.out


def test_census_only_needs_no_identity(
    panel: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reading the file's SHAPE is not reading its numbers, so it carries no validation duty."""
    assert _run([str(panel)], monkeypatch) == 0
    err = capsys.readouterr().err
    assert "'Criptoativos'" in err and "'Notas'" in err
    assert "1200" not in err


def test_no_validate_allows_shape_finding(
    panel: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(panel), "--sheet", "0", "--no-validate"], monkeypatch) == 0
    assert "PF,PJ,Subtotal" in capsys.readouterr().out


def test_json_format_round_trips(
    panel: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run([str(panel), "--sheet", "0", "--skip", "1", "--identity", "s:0,1:2",
                 "--format", "json"], monkeypatch) == 0
    rows = json.loads(capsys.readouterr().out)
    # --skip scopes the CHECK, never the dump: the caller asked for the sheet, so the header row
    # is still row 0 and the data starts at row 1.
    assert rows[0] == ["PF", "PJ", "Subtotal"]
    assert rows[1] == [1200.0, 3400.0, 4600.0]


def test_named_columns_work_when_rows_are_mappings() -> None:
    """The identity parser must keep a non-numeric key as a NAME, not coerce it to an index."""
    identity = cli.parse_identity("pf+pj=sub:pf,pj:sub")
    assert identity.parts == ("pf", "pj") and identity.total == "sub"
    assert cli.parse_identity("n:0,1:2").parts == (0, 1)
    assert cli.parse_identity("n:0,1:2:0.5").atol == 0.5
