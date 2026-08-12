"""R0356: the phantom-paths detector must resolve paths as EXPRESSIONS, not as line text.

Each test below is one of the four blind spots measured in the wild on 2026-08-12, plus the
error-direction property that makes the whole thing safe to trust. The fixtures are minimal
reconstructions of real call sites, named in each docstring so a future reader can go and look.
"""
from __future__ import annotations

from pathlib import Path

from libs.research import path_refs as pr


def _mod(tmp_path: Path, body: str, name: str = "m.py") -> tuple[set[str], set[str], set[str]]:
    p = tmp_path / name
    p.write_text(body, "utf-8")
    return pr.scan_file(p)


def test_a_split_literal_write_is_seen(tmp_path):
    """BLIND SPOT 1. scripts/measure_permutation_null.py:48 and run_real_campaign.py:37.

    `_ROOT / "reports" / "x.json"` puts no `reports/` inside any single string, so a regex needing
    one could not bind `_OUT` and never saw the writer.
    """
    _, writes, _ = _mod(tmp_path, '''
from pathlib import Path
_ROOT = Path("/desk")
_OUT = _ROOT / "reports" / "permutation_null.json"
def main():
    _OUT.write_text("{}")
''')
    assert "reports/permutation_null.json" in writes


def test_a_path_written_through_a_positional_parameter_is_seen(tmp_path):
    """BLIND SPOT 2, and the costliest one: scripts/run_cost_identification.py:430.

    `_merge_ramp(rep, _RAMP)` where the callee writes through `path`. The old alias rule only
    understood a DEFAULT argument, so `data/ramp_state.json` -- the very file L1.55 was written
    about -- reported as a phantom after its producer had been built.
    """
    _, writes, _ = _mod(tmp_path, '''
from pathlib import Path
_RAMP = Path("/desk") / "data/ramp_state.json"
def _merge(rep, path):
    path.write_text("{}")
def main():
    _merge({}, _RAMP)
''')
    assert "data/ramp_state.json" in writes


def test_an_alias_whose_rhs_does_not_start_with_the_name_is_seen(tmp_path):
    """BLIND SPOT 3. The old pattern anchored the bound name immediately after `=`, so
    `out = root / _REPORT_REL` bound nothing."""
    _, writes, _ = _mod(tmp_path, '''
from pathlib import Path
root = Path("/desk")
_REPORT_REL = "reports/gate_power_audit.json"
def main():
    out = root / _REPORT_REL
    out.write_text("{}")
''')
    assert "reports/gate_power_audit.json" in writes


def test_a_provenance_label_is_not_a_read(tmp_path):
    """BLIND SPOT 4. scripts/audit_reality_check.py:201 -- `"source": "reports/real_campaign.json"`
    inside a dict that is serialised into a report. It opens nothing, so it cannot take the empty
    branch, so it cannot exhibit the failure this fence detects."""
    reads, _, labels = _mod(tmp_path, '''
doc = {"cohort": {"source": "reports/real_campaign.json"}, "n": 3}
''')
    assert "reports/real_campaign.json" in labels
    assert "reports/real_campaign.json" not in reads


def test_the_same_string_is_a_read_when_it_is_actually_opened(tmp_path):
    """The label rule must not swallow a genuine reader that also names the path in a dict --
    otherwise blind spot 4's repair would hide the defect class the fence exists for."""
    reads, _, labels = _mod(tmp_path, '''
from pathlib import Path
meta = {"source": "data/real_store.json"}
def load():
    return Path("data/real_store.json").read_text()
''')
    assert "data/real_store.json" in reads
    assert "data/real_store.json" not in labels


def test_an_unresolvable_expression_never_invents_a_writer(tmp_path):
    """THE ERROR-DIRECTION PROPERTY, and the reason this module is safe to trust.

    Resolving MORE writers can only remove a phantom report, so the one thing this must never do
    is guess. A path assembled from a runtime value is unknown, and unknown must stay unknown --
    which leaves the store REPORTED, the safe direction for a fence whose job is noticing absence.
    """
    _, writes, _ = _mod(tmp_path, '''
from pathlib import Path
def main(name):
    (Path("data") / f"{name}.json").write_text("{}")
''')
    assert writes == set()


def test_globs_and_templates_are_not_stores(tmp_path):
    """A shape is not a file: nothing can write "the path with a star in it", so counting one
    would produce an eternal phantom. Reachable only once expressions resolve properly, so the
    exclusion is stated rather than inherited from a character class."""
    reads, _, _ = _mod(tmp_path, '''
from pathlib import Path
def main():
    for p in Path("data").glob("data/*.jsonl"):
        p.read_text()
    Path("data/{name}.json").read_text()
''')
    assert reads == set()


def test_a_write_anywhere_clears_the_phantom_everywhere(tmp_path):
    """The verdict is tree-wide: one module's writer answers another module's read."""
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/reader.py").write_text('''
from pathlib import Path
def go():
    return Path("data/shared.json").read_text()
''', "utf-8")
    (tmp_path / "libs/writer.py").write_text('''
from pathlib import Path
_P = Path("/x") / "data" / "shared.json"
def go():
    _P.write_text("{}")
''', "utf-8")
    scan = pr.scan(tmp_path)
    assert scan.phantoms(tmp_path) == []
    assert "scripts/reader.py" in scan.reads["data/shared.json"]


def test_a_genuine_read_without_writer_is_still_reported(tmp_path):
    """THE BAR. Every repair above removes noise; none may remove the signal."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/reader.py").write_text('''
from pathlib import Path
FORENSICS = Path("/x") / "data" / "trade_forensics.json"
def go():
    return FORENSICS.read_text()
''', "utf-8")
    assert pr.scan(tmp_path).phantoms(tmp_path) == ["data/trade_forensics.json"]
