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


# ---------------------------------------------- BLIND SPOT 5: the rotted writer name list
def test_an_atomic_wrapper_is_seen_whatever_it_is_called(tmp_path):
    """MEASURED 2026-09-24. `WRITE_FUNCS` named `_atomic` and `_atomic_write`; the same house
    helper is also spelled `_atomic_json` and `_write_atomic`, and neither was in the list. So
    `market_constitution.py` (which writes reports/MARKET_CONSTITUTION.json and
    data/market_constraints.json through `_atomic_json`) resolved to ZERO writes and was reported
    as a reader of two files nothing writes -- with macro_intelligence.py, synthetic_regimes.py
    and transmission_engine.py beside it. Four of eighteen orphan rows were one rotted list.
    """
    body = '''
import os, json, tempfile
from pathlib import Path
DESK = Path("/desk")
OUT = DESK / "reports" / "NEVER_HEARD_OF_IT.json"
def _a_name_nobody_will_ever_guess(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value), "utf-8")
    os.replace(tmp, path)
def main():
    _a_name_nobody_will_ever_guess(OUT, {"a": 1})
'''
    _, writes, _ = _mod(tmp_path, body)
    assert "reports/NEVER_HEARD_OF_IT.json" in writes


def test_the_written_PARAMETER_is_identified_not_merely_the_first_argument(tmp_path):
    """`_dump(doc, path)` writes `path` and not `doc`: the index is measured, never assumed."""
    body = '''
from pathlib import Path
DESK = Path("/desk")
SRC = DESK / "data" / "input.json"
DST = DESK / "reports" / "output.json"
def _dump(doc, path):
    path.write_text(str(doc), "utf-8")
def main():
    _dump(SRC, DST)
'''
    _, writes, _ = _mod(tmp_path, body)
    assert "reports/output.json" in writes
    assert "data/input.json" not in writes


def test_a_wrapper_that_writes_nothing_never_invents_a_writer(tmp_path):
    """THE ERROR DIRECTION THAT MATTERS. A helper that only READS its parameter must not make
    its caller a producer -- inventing a writer is the one failure this module may not have."""
    body = '''
from pathlib import Path
DESK = Path("/desk")
IN = DESK / "data" / "only_ever_read.json"
def _load(path):
    return path.read_text("utf-8")
def main():
    return _load(IN)
'''
    reads, writes, _ = _mod(tmp_path, body)
    assert "data/only_ever_read.json" in reads
    assert writes == set()


def test_one_wrapper_calling_another_still_resolves(tmp_path):
    body = '''
import os, json
from pathlib import Path
DESK = Path("/desk")
OUT = DESK / "reports" / "TWO_HOPS.json"
def _inner(path, body):
    path.write_text(body, "utf-8")
def _outer(path, doc):
    _inner(path, json.dumps(doc))
def main():
    _outer(OUT, {"a": 1})
'''
    _, writes, _ = _mod(tmp_path, body)
    assert "reports/TWO_HOPS.json" in writes


def test_the_desks_real_atomic_writers_all_resolve_now():
    """Against the tree itself: the four modules the rotted list missed."""
    import pytest

    root = Path(__file__).resolve().parents[2]
    cases = {
        "desks/mt5/research/market_constitution.py": "reports/MARKET_CONSTITUTION.json",
        "desks/mt5/research/macro_intelligence.py": "reports/MACRO_INTELLIGENCE.json",
        "desks/mt5/research/synthetic_regimes.py": "reports/SYNTHETIC_REGIMES.json",
        "desks/mt5/research/transmission_engine.py": "reports/TRANSMISSION_GRAPH.json",
    }
    for rel, artifact in cases.items():
        src = root / rel
        if not src.exists():
            pytest.skip(f"UNMEASURED: {rel} is absent from this tree")
        _, writes, _ = pr.scan_file(src)
        assert artifact in writes, f"{rel} writes {artifact} and the resolver cannot see it"
