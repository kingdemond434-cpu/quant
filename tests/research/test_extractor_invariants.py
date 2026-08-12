"""Tests for extractor-invariant discovery (R0318).

THIS DETECTOR IS ITSELF AN EXTRACTOR -- it parses source to decide who parses badly -- so it gets
the treatment it exists to demand. Both false-positive classes found when it was first calibrated
against a hand census are pinned here as tests, because a detector that drifts back into
over-reporting is a fence that gets switched off, and a switched-off fence enforces nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from libs.research.extractor_invariants import (
    declaration_in,
    discover,
    summarise,
    techniques_in,
)


def _techniques(source: str) -> tuple[str, ...]:
    return techniques_in(ast.parse(source), source)


def _module(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, "utf-8")


# ----------------------------------------------------------------------------- technique detection
@pytest.mark.parametrize(
    "source",
    [
        'import re\nre.findall(r"<item>(.*?)</item>", body)',
        'import re\nre.sub(r"<[^>]+>", " ", page)',
        'import re\n_ROW = re.compile(r"<tr[^>]*>")',
        'import re\nre.findall(r"<opensearch:totalResults>(\\d+)<", xml)',
        'text.split("<div class=\\"txt-box\\">")',
    ],
)
def test_markup_torn_apart_by_regex_is_detected(source: str) -> None:
    assert "markup-by-regex" in _techniques(source)


def test_byte_level_decoding_is_detected() -> None:
    assert "byte-level" in _techniques('import struct\nstruct.unpack_from("<H", buf, 0)')
    assert "byte-level" in _techniques('int.from_bytes(raw[0:4], "little")')


def test_csv_fields_sliced_out_of_lines_are_detected() -> None:
    source = 'for line in payload.splitlines():\n    parts = line.split(",")\n'
    assert "delimited-by-hand" in _techniques(source)


def test_header_row_idiom_is_detected() -> None:
    source = 'lines = blob.splitlines()\nhdr = lines[0].split(",")\n'
    assert "delimited-by-hand" in _techniques(source)


# ------------------------------------------------------------------ the two false-positive classes
def test_regex_named_group_is_not_markup() -> None:
    """``(?P<file>...)`` is spelled exactly like an XML tag and is not one.

    Every log and mypy-output parser in the repo uses named groups; treating them as markup put
    a wall of innocent modules on the report the first time this ran.
    """
    source = 'import re\n_ERR = re.compile(r"^(?P<file>[^:]+):\\d+:\\s*error:")'
    assert "markup-by-regex" not in _techniques(source)


def test_splitting_a_cli_argument_is_not_csv() -> None:
    """``args.symbols.split(",")`` reads an argument; it does not parse a format."""
    source = (
        'for line in report.splitlines():\n    pass\n'
        'symbols = [s.strip() for s in str(args.symbols).split(",") if s]\n'
    )
    assert "delimited-by-hand" not in _techniques(source)


def test_stdlib_csv_module_is_not_hand_rolled() -> None:
    """The stdlib reader handles quoting and embedded delimiters -- that layer is not hand-rolled.
    """
    source = (
        'import csv\nrows = list(csv.DictReader(text))\n'
        'for line in text.splitlines():\n    parts = line.split(",")\n'
    )
    assert "delimited-by-hand" not in _techniques(source)


def test_a_module_that_parses_nothing_is_not_an_extractor() -> None:
    assert _techniques("import json\nrows = json.loads(payload)\n") == ()


# --------------------------------------------------------------------------------- the declaration
def test_explicit_declaration_is_read() -> None:
    source = 'EXTRACTOR_INVARIANT = "every row carries 4 fields and the count is non-zero"\n'
    assert "4 fields" in declaration_in(ast.parse(source), source)


def test_empty_declaration_does_not_count() -> None:
    """A checkbox is not a claim: the VALUE is what a later reader audits."""
    source = 'EXTRACTOR_INVARIANT = "   "\n'
    assert declaration_in(ast.parse(source), source) == ""


def test_importing_the_conservation_helper_counts() -> None:
    source = "from libs.research.conservation import Identity, check_identities\n"
    assert "conservation" in declaration_in(ast.parse(source), source)


def test_merely_mentioning_conservation_does_not_count() -> None:
    """THE ONE THAT MATTERS. A fence satisfiable by writing about the fix enforces nothing."""
    source = '"""We should use libs.research.conservation here one day."""\n'
    assert declaration_in(ast.parse(source), source) == ""


# -------------------------------------------------------------------------- discovery and refusals
def test_discovery_reports_an_unparseable_module_rather_than_skipping_it(tmp_path: Path) -> None:
    """"We could not read it" and "it is fine" are different claims (L1.28a)."""
    _module(tmp_path, "libs/broken.py", "def f(:\n")
    (tmp_path / "scripts").mkdir()
    found = discover(tmp_path)
    assert [e.path for e in found] == ["libs/broken.py"]
    assert found[0].techniques == ("unparseable",) and not found[0].declared


def test_zero_population_is_unmeasured_not_ok(tmp_path: Path) -> None:
    """An empty result means the detector broke, not that the defect was solved."""
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts").mkdir()
    report = summarise(tmp_path)
    assert report["status"] == "UNMEASURED"
    assert report["coverage"] is None


def test_coverage_is_measured_over_what_the_run_found(tmp_path: Path) -> None:
    _module(tmp_path, "libs/a.py", 'import re\nre.findall(r"<item>x</item>", b)')
    _module(tmp_path, "libs/b.py", 'import re\nEXTRACTOR_INVARIANT = "rows > 0"\n'
                                   're.findall(r"<tr>", b)')
    (tmp_path / "scripts").mkdir()
    report = summarise(tmp_path)
    assert (report["n_extractors"], report["n_declared"]) == (2, 1)
    assert report["coverage"] == 0.5
    assert report["status"] == "PARTIAL"


def test_full_coverage_reads_ok(tmp_path: Path) -> None:
    _module(tmp_path, "libs/a.py", 'import re\nEXTRACTOR_INVARIANT = "rows > 0"\n'
                                   're.findall(r"<item>", b)')
    (tmp_path / "scripts").mkdir()
    assert summarise(tmp_path)["status"] == "OK"


def test_skip_dirs_are_matched_relative_to_the_root(tmp_path: Path) -> None:
    """A checkout under a directory named `.claude` -- every git worktree here -- must still scan.

    Matching skip names against the ABSOLUTE path made discovery return nothing for the entire
    repo, which the fence then reported as UNMEASURED: correct status, wrong reason, and it would
    have looked like a broken detector rather than a broken exclusion list.
    """
    root = tmp_path / ".claude" / "worktrees" / "wt"
    _module(root, "libs/a.py", 'import re\nre.findall(r"<item>x</item>", b)')
    (root / "scripts").mkdir()
    assert [e.path for e in discover(root)] == ["libs/a.py"]


def test_vendored_directories_are_still_skipped(tmp_path: Path) -> None:
    _module(tmp_path, "libs/__pycache__/a.py", 'import re\nre.findall(r"<item>", b)')
    _module(tmp_path, "libs/real.py", 'import re\nre.findall(r"<item>", b)')
    (tmp_path / "scripts").mkdir()
    assert [e.path for e in discover(tmp_path)] == ["libs/real.py"]


# --------------------------------------------------------------------------- against the real repo
def test_the_real_repo_has_a_measurable_population() -> None:
    """A population of zero here would mean the detector stopped working (its own L1.57 refusal)."""
    report = summarise(Path(__file__).resolve().parents[2])
    assert report["status"] in {"OK", "PARTIAL"}
    assert report["n_extractors"] > 10
    assert report["coverage"] is not None


def test_the_detector_excludes_itself() -> None:
    """It carries markup patterns as DATA and parses Python with `ast` -- the opposite of the
    defect.
    """
    found = {e.path for e in discover(Path(__file__).resolve().parents[2])}
    assert "libs/research/extractor_invariants.py" not in found


# --------------------------------------------------- the fence script (check_extractor_invariants)
def _load_fence():  # type: ignore[no-untyped-def]
    """Import ``scripts/check_extractor_invariants.py`` by path -- ``scripts/`` is not a package."""
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "check_extractor_invariants.py"
    spec = importlib.util.spec_from_file_location("check_extractor_invariants", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fence_reports_partial_over_the_real_repo() -> None:
    """The live board: a real population, a real coverage number, and it does NOT block."""
    report = _load_fence().build()
    assert report["status"] in {"OK", "PARTIAL"}
    assert report["n_extractors"] > 10
    assert "generated" in report and "next_action" in report


def test_fence_next_action_names_a_specific_module(tmp_path: Path) -> None:
    """"Improve coverage" is not an action; a path someone can open is."""
    _module(tmp_path, "libs/a.py", 'import re\nre.findall(r"<item>x</item>", b)')
    (tmp_path / "scripts").mkdir()
    fence = _load_fence()
    assert "libs/a.py" in fence._next_action(fence.build(tmp_path))


def test_fence_next_action_on_a_broken_detector(tmp_path: Path) -> None:
    """UNMEASURED must route to repairing the DETECTOR, not to annotating modules."""
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts").mkdir()
    fence = _load_fence()
    assert "detector" in fence._next_action(fence.build(tmp_path))


def test_fence_coverage_is_a_ratchet_not_a_cliff() -> None:
    """PARTIAL exits 0 on purpose: a fence that goes red on day one gets switched off (L1.43)."""
    from libs.ops.fence_exit import fence_exit

    assert fence_exit("PARTIAL", frozenset({"OK", "PARTIAL"}), scanned=32, of="x", fence="t") == 0
    assert fence_exit("UNMEASURED", frozenset({"OK", "PARTIAL"}), scanned=0, of="x", fence="t") != 0
