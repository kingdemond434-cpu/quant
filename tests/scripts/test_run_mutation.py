"""Fences for the mutation harness's SAMPLING and its honesty rails.

WHAT WENT WRONG, and why it needed a test rather than a comment. `data/mutation_score.json`
recorded `libs/autodiscovery/validation.py` at a 35.7% kill rate over 14 of 137 mutation sites.
Those 14 were not 14 random sites: the harness visited sites in SOURCE ORDER, so a budget-truncated
run measured the top of the file -- module-header constants and import-time literals -- and nothing
about the gate logic underneath. The reported rate was not a noisy estimate of the file's strength;
it was a precise measurement of a different thing.

The tests below pin the three properties that make a partial run readable and keep it unscoreable:

  * ORDER IS A SEEDED PERMUTATION, so any prefix of the visit order is a simple random sample --
    and it is REPRODUCIBLE from the recorded seed, so two operators measure the same sites.
  * THE INTERVAL IS FINITE-POPULATION CORRECTED, so a census reports a POINT (a complete run has no
    sampling error) and a small sample reports its real width instead of a spuriously tight one.
  * `budget_truncated` STILL MEANS "DO NOT SCORE". Sampling improves what a partial number MEANS;
    it must not make a partial run count, or the desk can buy points by running less -- the exact
    incentive `scripts/check_ratchets.py` and `libs/research/capability_ratchet.py` refuse.

The resume ledger gets the same treatment: it may only pool outcomes gathered against the SAME
source, seed, order and test list, because coverage accumulated across different measurements is
manufactured coverage.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    """Import scripts/run_mutation.py by path -- `scripts` is not an importable package."""
    if str(_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "run_mutation_under_test", _ROOT / "scripts" / "run_mutation.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses needs the module registered while executing
    spec.loader.exec_module(mod)
    return mod


RM = _load()

#: A file whose mutation sites are spread from top to bottom, with a deliberate CONCENTRATION of
#: numeric constants in the header -- the shape that made source order so misleading on the real
#: validator.
_SAMPLE_SRC = "\n".join(
    [f"A{i} = {i}" for i in range(20)]
    + ["", "", "def gate(x: float) -> bool:"]
    + [f"    if x > {i}:\n        return False" for i in range(20)]
    + ["    return True", ""])


def test_source_order_prefix_is_biased_toward_the_top_of_the_file() -> None:
    """The defect, stated as a measurement: a source-ordered prefix samples one END of the file.

    This is not a style point. Header constants and gate logic are different KINDS of code with
    different test coverage, so choosing sites by position chooses the answer.
    """
    sites = RM._enumerate_sites(_SAMPLE_SRC)
    prefix = RM.order_sites(sites, order="source", seed=1)[:14]
    linenos = [s.lineno for s, _ in prefix]
    assert max(linenos) < 20, "source order takes the first N lines, which is the bias"


def test_shuffled_order_spreads_a_truncated_run_across_the_whole_file() -> None:
    sites = RM._enumerate_sites(_SAMPLE_SRC)
    total_lines = _SAMPLE_SRC.count("\n")
    prefix = RM.order_sites(sites, order="shuffled", seed=RM._DEFAULT_SEED)[:14]
    linenos = [s.lineno for s, _ in prefix]
    assert max(linenos) > total_lines / 2, "a truncated shuffled run must reach the file's tail"
    assert min(linenos) < total_lines / 2


def test_shuffle_is_a_permutation_not_a_filter() -> None:
    """Every site must still be reachable -- sampling reorders the work, it never drops any."""
    sites = RM._enumerate_sites(_SAMPLE_SRC)
    shuffled = RM.order_sites(sites, order="shuffled", seed=7)
    assert len(shuffled) == len(sites)
    key = RM._site_key
    assert {key(s, i) for s, i in shuffled} == {key(s, i) for s, i in sites}


def test_same_seed_reproduces_the_same_sample() -> None:
    """An unbiased sample that nobody else can reproduce is not auditable evidence."""
    sites = RM._enumerate_sites(_SAMPLE_SRC)
    a = [RM._site_key(s, i) for s, i in RM.order_sites(sites, order="shuffled", seed=99)]
    b = [RM._site_key(s, i) for s, i in RM.order_sites(sites, order="shuffled", seed=99)]
    c = [RM._site_key(s, i) for s, i in RM.order_sites(sites, order="shuffled", seed=100)]
    assert a == b
    assert a != c, "different seeds must give different samples, or the seed is decorative"


def test_site_ordinals_do_not_depend_on_the_seed() -> None:
    """Site IDENTITY must be seed-independent or `--resume` cannot match yesterday's ledger.

    Two mutations of the same kind on one line are told apart by an ordinal. If the ordinal were
    assigned after shuffling, the same physical mutation would get a different key under a
    different seed and the resume ledger would silently re-run or skip the wrong ones.
    """
    src = "x = 1 + 2 + 3\n"
    sites = RM._enumerate_sites(src)
    assert len(sites) >= 2
    for seed in (1, 2, 3):
        shuffled = RM.order_sites(sites, order="shuffled", seed=seed)
        assert {RM._site_key(s, i) for s, i in shuffled} == {
            RM._site_key(s, i) for s, i in sites}


class TestConfidenceInterval:
    """The interval is the part that makes a partial number safe to read."""

    def test_a_census_reports_a_point_not_a_range(self) -> None:
        """A complete run has NO sampling error. An interval around a census would be a lie in the
        one direction that matters: it would make a finished measurement look negotiable."""
        s = RM.TargetScore(target="t", tests=[], n_sites=40, killed=36, survived=4)
        assert s.kill_rate == 0.9
        assert s.kill_rate_ci95() == [0.9, 0.9]

    def test_a_small_sample_reports_a_wide_interval(self) -> None:
        """14 of 137 sites at 35.7% is compatible with a very wide range of true kill rates, and
        the artifact has to say so rather than print one decimal place of false precision."""
        s = RM.TargetScore(target="t", tests=[], n_sites=137, killed=5, survived=9)
        lo, hi = s.kill_rate_ci95()
        assert lo < 0.357 < hi
        assert hi - lo > 0.3

    def test_the_interval_narrows_as_coverage_grows(self) -> None:
        """Finite-population correction: measuring more of the same file must buy precision."""
        wide = RM.TargetScore(target="t", tests=[], n_sites=200, killed=10, survived=10)
        narrow = RM.TargetScore(target="t", tests=[], n_sites=200, killed=80, survived=80)
        assert wide.kill_rate == narrow.kill_rate == 0.5
        w, n = wide.kill_rate_ci95(), narrow.kill_rate_ci95()
        assert (n[1] - n[0]) < (w[1] - w[0])

    def test_timeouts_count_toward_the_killed_numerator(self) -> None:
        """Documented behaviour, pinned: a mutation that hangs the suite changed behaviour."""
        s = RM.TargetScore(target="t", tests=[], n_sites=10, killed=4, timeout=4, survived=2)
        assert s.kill_rate == 0.8

    def test_errors_leave_the_denominator(self) -> None:
        s = RM.TargetScore(target="t", tests=[], n_sites=10, killed=4, survived=1, error=5)
        assert s.kill_rate == 0.8


class TestUnbiasedFlag:
    """`unbiased_sample` is the field that tells a reader whether the rate estimates the file."""

    def test_a_truncated_shuffled_run_is_unbiased(self) -> None:
        s = RM.TargetScore(target="t", tests=[], n_sites=137, killed=5, survived=9,
                           order="shuffled")
        assert s.unbiased is True

    def test_a_truncated_source_ordered_run_is_not(self) -> None:
        s = RM.TargetScore(target="t", tests=[], n_sites=137, killed=5, survived=9, order="source")
        assert s.unbiased is False

    def test_a_complete_source_ordered_run_is_unbiased(self) -> None:
        """A census is a census. Order only matters when the run stops early."""
        s = RM.TargetScore(target="t", tests=[], n_sites=14, killed=5, survived=9, order="source")
        assert s.unbiased is True


class TestTruncationRail:
    """THE RAIL THAT MUST NOT MOVE. `budget_truncated` means DO NOT SCORE THIS.

    Both readers of the artifact refuse truncated targets, and that refusal is what stops a shorter
    run from looking like a better one. Sampling changed what a partial number MEANS; if it also
    made a partial run scoreable, it would have re-opened the hole it was meant to close.
    """

    def test_an_unbiased_sample_is_still_flagged_truncated(self, monkeypatch: pytest.MonkeyPatch,
                                                           tmp_path: Path) -> None:
        row = _artifact_row_for(monkeypatch, tmp_path, killed=2, n_sites=10, order="shuffled")
        assert row["unbiased_sample"] is True
        assert row["budget_truncated"] is True, (
            "an unbiased partial run is an ESTIMATE, not a score -- clearing this flag would let "
            "the desk buy ratchet points by running fewer mutants")

    def test_the_ratchet_readers_still_skip_it(self, monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
        """Read the flag exactly as the two live consumers do, so this test fails if either the
        harness stops emitting it or its meaning drifts."""
        row = _artifact_row_for(monkeypatch, tmp_path, killed=2, n_sites=10, order="shuffled")
        assert bool(row.get("budget_truncated")) is True      # check_ratchets.py:78
        assert row.get("budget_truncated") is True            # capability_ratchet.py:507 (`is`)

    def test_a_complete_run_clears_the_flag(self, monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
        row = _artifact_row_for(monkeypatch, tmp_path, killed=10, n_sites=10, order="shuffled")
        assert row["budget_truncated"] is False
        assert row["coverage_of_sites"] == 1.0
        assert row["kill_rate_ci95"] == [1.0, 1.0]


def test_a_timeout_does_not_split_the_raw_and_adjusted_rates(monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    """`adjusted_kill_rate` is the number the ratchet reads. It must agree with `kill_rate`.

    Both are defined with TIMEOUT counting as killed -- a mutation that hangs the suite changed
    observable behaviour. The equivalence adjuster was being handed bare `killed`, so the first
    hanging mutant made the two numbers disagree (libs/risk/sizing.py, 2026-08-05: 86.2% against
    82.8% with no equivalences registered at all) and the ratchet would have filed a REGRESSION on
    a file nobody had touched. A metric that moves when the machine hiccups is not a measurement.
    """
    out = tmp_path / "mutation_score.json"
    monkeypatch.setattr(RM, "_OUT", out)
    score = RM.TargetScore(target="libs/fake.py", tests=["tests/fake.py"], killed=24, timeout=1,
                           survived=4, n_sites=29, order="shuffled")

    def fake_measure(target: str, tests: list[str], **kw: object) -> RM.TargetScore:
        return score

    monkeypatch.setattr(RM, "measure", fake_measure)
    monkeypatch.setattr(sys, "argv", ["run_mutation.py", "--target", "libs/fake.py",
                                      "--tests", "tests/fake.py"])
    assert RM.main() == 0
    row = next(t for t in json.loads(out.read_text("utf-8"))["targets"]
               if t["target"] == "libs/fake.py")
    assert row["kill_rate"] == pytest.approx(25 / 29, abs=1e-4)
    assert row["adjusted_kill_rate"] == pytest.approx(row["kill_rate"], abs=1e-4), (
        "with no equivalences registered the adjusted rate IS the raw rate")


def _artifact_row_for(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, killed: int,
                      n_sites: int, order: str) -> dict[str, object]:
    """Drive main() with a stubbed `measure` and read the row it writes.

    Stubbing the measurement (not the serialisation) is deliberate: the thing under test is what
    the ARTIFACT says about a partial run, which is what every downstream reader sees.
    """
    out = tmp_path / "mutation_score.json"
    monkeypatch.setattr(RM, "_OUT", out)
    score = RM.TargetScore(target="libs/fake.py", tests=["tests/fake.py"], killed=killed,
                           survived=0, n_sites=n_sites, order=order, seed=1234)

    def fake_measure(target: str, tests: list[str], **kw: object) -> RM.TargetScore:
        return score

    monkeypatch.setattr(RM, "measure", fake_measure)
    monkeypatch.setattr(sys, "argv", ["run_mutation.py", "--target", "libs/fake.py",
                                      "--tests", "tests/fake.py"])
    assert RM.main() == 0
    doc = json.loads(out.read_text("utf-8"))
    rows = [t for t in doc["targets"] if t["target"] == "libs/fake.py"]
    assert len(rows) == 1
    return dict(rows[0])


class TestResumeLedger:
    """Resume accumulates coverage. It may only pool outcomes that describe the SAME measurement."""

    @pytest.fixture()
    def ledger(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
        p = tmp_path / "mutation_progress.json"
        monkeypatch.setattr(RM, "_PROGRESS", p)
        yield p

    def test_round_trips_outcomes(self, ledger: Path) -> None:
        RM._save_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                          tests=["t.py"], n_sites=5, outcomes={"3:compare:0:Lt -> LtE": "killed"})
        got = RM._load_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                                tests=["t.py"])
        assert got == {"3:compare:0:Lt -> LtE": "killed"}

    @pytest.mark.parametrize(
        ("field", "value"),
        [("fingerprint", "different"), ("seed", 2), ("order", "source")])
    def test_a_changed_measurement_discards_the_ledger(self, ledger: Path, field: str,
                                                       value: object) -> None:
        """Pooling outcomes from a different source, seed or order would MANUFACTURE coverage --
        the artifact would claim sites were measured against a file that no longer exists."""
        RM._save_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                          tests=["t.py"], n_sites=5, outcomes={"3:compare:0:x": "killed"})
        kw: dict[str, object] = {"fingerprint": "abc", "seed": 1, "order": "shuffled",
                                 "tests": ["t.py"]}
        kw[field] = value
        assert RM._load_progress("libs/x.py", **kw) == {}       # type: ignore[arg-type]

    def test_a_changed_test_list_discards_the_ledger(self, ledger: Path) -> None:
        """A kill rate is a rate against a NAMED suite. Adding a test module makes every prior
        outcome an answer to a different question."""
        RM._save_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                          tests=["t.py"], n_sites=5, outcomes={"3:compare:0:x": "killed"})
        assert RM._load_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                                 tests=["t.py", "u.py"]) == {}

    def test_a_missing_or_corrupt_ledger_is_not_fatal(self, ledger: Path) -> None:
        assert RM._load_progress("libs/x.py", fingerprint="a", seed=1, order="shuffled",
                                 tests=[]) == {}
        ledger.write_text("{not json", "utf-8")
        assert RM._load_progress("libs/x.py", fingerprint="a", seed=1, order="shuffled",
                                 tests=[]) == {}

    def test_the_ledger_is_not_the_score(self, ledger: Path) -> None:
        """Two artifacts, two meanings: the ledger records what was ATTEMPTED, the score records
        what was MEASURED. Merging them is how "attempted" starts reading as "strong"."""
        RM._save_progress("libs/x.py", fingerprint="abc", seed=1, order="shuffled",
                          tests=["t.py"], n_sites=5, outcomes={"3:compare:0:x": "killed"})
        doc = json.loads(ledger.read_text("utf-8"))
        assert "kill_rate" not in json.dumps(doc)
        assert doc["targets"]["libs/x.py"]["attempted"] == 1
        assert doc["targets"]["libs/x.py"]["n_sites"] == 5


class TestMutantConstruction:
    """The splice fix and the applier/collector agreement, kept under test rather than in a
    comment: both were real defects that produced a FABRICATED score (a phantom 100% and a
    mid-file crash)."""

    def test_only_the_mutated_statement_is_rewritten(self) -> None:
        """`ast.unparse` of the whole module normalises quotes and drops comments, which killed
        every mutant of `validation.py` via a source-asserting test and fabricated a 100%."""
        src = ('X = "double quoted"  # a comment\n'
               'def f(a: int) -> bool:\n'
               '    return a > 1\n')
        sites = RM._enumerate_sites(src)
        cmp_site = next((s, i) for s, i in sites if s.kind == "compare")
        out = RM._mutant_source(src, *cmp_site)
        assert out is not None
        assert '"double quoted"  # a comment' in out, "untouched lines must stay byte-identical"
        assert "a >= 1" in out

    def test_string_constants_are_not_mutated_by_either_half(self) -> None:
        """The collector ignores str/None constants; the applier must classify them identically or
        the ordinals disagree and `str + 1` crashes the run mid-file."""
        src = 'S = "text"\nN = None\nK = 3\n'
        kinds = {s.kind for s, _ in RM._enumerate_sites(src)}
        assert kinds == {"num_const"}

    def test_every_enumerated_site_actually_applies(self) -> None:
        """A site the applier cannot find is a silently smaller denominator."""
        src = Path(__file__).read_text("utf-8").split("_SAMPLE_SRC = ")[0]
        for site, idx in RM._enumerate_sites(src):
            out = RM._mutant_source(src, site, idx)
            assert out is not None, f"unapplied site {site.lineno}:{site.kind}"
            ast.parse(out)          # and it must still be valid Python
