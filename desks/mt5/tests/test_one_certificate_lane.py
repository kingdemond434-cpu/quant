"""ONE CANONICAL LANE: a forward clock exists only for a ten-gate certificate.

THE SPLIT THESE TESTS DELETE, measured on the trading box 2026-09-24. Three organs published
three different answers to "how many certificates does the desk hold":

    reports/UNIVERSAL_SURVIVORS.json   n = 28      the canonical store, 28/28 passing ten gates
    FORWARD_ENROLMENT.json  n_certificates = 148   28 certificates + 120 power-cure candidates
    CLOCK_LIVENESS.json        clocks_total = 153  every row in the engine's state file

The 148 was not a count of certificates. `shadow_admission.authorized_runs` carried a POWER-CURE
LANE that read `reports/POWER_CURE_CANDIDATES.json` and appended up to `CURE_BUDGET = 120`
validity-pass, power-DEFICIENT cells to the same list the canon's rows went into. Those rows
carried `promotion_authority: False` and `gate_admission: VALIDITY_PASS_POWER_DEFICIENT` -- they
said what they were -- and every organ downstream took `len()` of the combined list and called
the answer "certificates".

WHETHER THEY WERE CERTIFICATES WAS SETTLED BY MEASUREMENT, NOT PREFERENCE:

    canon survivors                  28   all_ten_pass  28 / 28
    eligible cure candidates      1,240   all_ten_pass   0 / 1,240
    failed_power_gates over the 1,240: deflated_sharpe 1,240, cpcv 54, expected_value 41,
                                       in_sample_screen 41, walk_forward 14

EVERY eligible cure row fails `deflated_sharpe` -- the multiple-testing charge, whose entire
purpose is to stop a wide search from minting false positives. A lane that forward-tested 120 of
them and kept the winners was running precisely the search that charge exists to price.

So the principal's ruling (2026-09-23, restated 2026-09-24 -- "all certis clocks must be one
canonised lane not seperate ... delete the other, and unify the whole pipeline") resolves to
outcome two: they are not certificates, and the lane that minted them is gone.

WHAT THESE TESTS DO NOT DO. They do not cap enrolment, and they must never be read as licence to.
Every ten-gate certificate still gets a clock the moment it exists, uncapped and unranked
(`scripts/check_forward_enrolment.py` fails if a quota returns). Deleting the cure lane lowers no
risk and forgoes no bet -- a forward clock deploys no capital -- and it RAISES throughput, because
the 120 shared a multiplicity cohort with the 28 and were making every real certificate's bar
harder.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sa = pytest.importorskip("shadow_admission", reason="ships with the research package")
gp = pytest.importorskip("gate_policy", reason="ships with the research package")

ADMISSION = _DESK / "research" / "shadow_admission.py"
TRUTH = _DESK / "research" / "certificate_truth.py"


def _gates(passed: bool = True) -> dict:
    return {name: {"passed": passed} for name in gp.GATES}


def _spec(symbol: str = "USDZAR", **over) -> dict:
    spec = {"symbol": symbol, "selector": "asia", "family": "overnight_gap_decay",
            "params": {}, "side": "LONG"}
    spec.update(over)
    return spec


def _base(tmp_path: Path, survivors: dict, cure: dict | None = None) -> Path:
    rep = tmp_path / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"survivors": survivors, "gate_policy": dict(gp.ATTESTATION)}), "utf-8")
    if cure is not None:
        (rep / "POWER_CURE_CANDIDATES.json").write_text(
            json.dumps({"candidates": cure, "gate_policy": dict(gp.ATTESTATION)}), "utf-8")
    return tmp_path


class TestThePowerCureLaneIsGone:
    """The lane is deleted at the source, not merely defaulted off."""

    def test_no_cure_symbol_survives_in_the_admission_module(self) -> None:
        for name in ("CURE_BUDGET", "cure_census", "_CURE_CENSUS", "power_cure_specs"):
            assert not hasattr(sa, name), (
                f"`shadow_admission.{name}` is back. The power-cure lane admitted 120 cells of "
                f"which 0 passed all ten gates, and every organ downstream counted them as "
                f"certificates. One canonical lane: the store is the canon and nothing else.")

    def test_no_code_path_reads_the_power_cure_store(self) -> None:
        """A comment may name the deleted store; executable code may not open it.

        AST, not grep, for the same reason `check_forward_enrolment` uses it: the headstone in
        this module DISCUSSES the lane at length, and that record is the point.
        """
        tree = ast.parse(ADMISSION.read_text(encoding="utf-8"))
        offenders = [n.lineno for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and "POWER_CURE_CANDIDATES" in n.value]
        assert not offenders, (
            f"shadow_admission.py opens the power-cure store again at line(s) {offenders}. "
            f"That file is still written by the sealed gauntlet and is still honest evidence "
            f"about which cells are close -- it simply confers no clock and no authority.")

    def test_the_default_lanes_do_not_include_cure(self) -> None:
        defaults = sa.authorized_runs.__defaults__ or ()
        lanes = next((d for d in defaults if isinstance(d, tuple)), ())
        assert "cure" not in lanes, (
            f"`cure` is back in the default lanes {lanes!r}. It was the default for a reason "
            f"nobody re-examined, and it is how 120 non-certificates entered every count.")

    def test_a_power_deficient_cell_gets_no_clock_even_when_the_store_offers_it(
            self, tmp_path) -> None:
        """The end-to-end refusal: a perfect cure candidate, offered, and not admitted."""
        cure = {"external.EURMXN.pca_residual.c1": {
            "validity_pass": True, "failed_power_gates": ["deflated_sharpe"],
            "cell": "external.EURMXN.pca_residual.c1",
            "gates": _gates(), "shadow_spec": _spec("EURMXN", family="pca_residual",
                                                    selector="continuous")}}
        base = _base(tmp_path, {}, cure=cure)
        assert sa.authorized_runs(base) == [], (
            "a validity-pass / power-deficient cell was admitted. It fails the multiple-testing "
            "charge, which is the one gate that exists to stop a wide forward search from "
            "keeping its winners.")
        assert sa.authorized_runs(base, lanes=("h1", "scalp", "cure")) == [], (
            "asking for the cure lane by name brought it back. The lane is deleted, so naming "
            "it must be inert rather than a way in.")


class TestEveryAdmittedRunIsATenGateCertificate:
    """The invariant that makes `len(authorized_runs())` a certificate count again."""

    def test_a_certified_row_is_admitted(self, tmp_path) -> None:
        base = _base(tmp_path, {"external.USDZAR.overnight_gap_decay.p=abc": {
            "gates": _gates(), "shadow_spec": _spec()}})
        runs = sa.authorized_runs(base)
        assert len(runs) == 1
        assert runs[0]["symbol"] == "USDZAR"
        assert runs[0].get("promotion_authority") is not False
        assert runs[0].get("gate_admission") != "VALIDITY_PASS_POWER_DEFICIENT"

    def test_a_row_failing_one_gate_is_not_admitted(self, tmp_path) -> None:
        gates = _gates()
        gates["deflated_sharpe"] = {"passed": False}
        base = _base(tmp_path, {"external.USDZAR.overnight_gap_decay.p=abc": {
            "gates": gates, "shadow_spec": _spec()}})
        assert sa.authorized_runs(base) == [], (
            "a row that fails deflated_sharpe was admitted. That is exactly the population the "
            "power-cure lane used to enrol -- all 1,240 of them failed this one gate.")

    def test_the_admitted_count_never_exceeds_the_ten_gate_count(self, tmp_path) -> None:
        """The shape of the 148-against-28 defect, as a property.

        Two certified rows and three power-deficient ones: the old lane returned five and called
        the answer "certificates". The count may now only ever be <= the ten-gate population.
        """
        survivors = {f"external.SYM{i}.overnight_gap_decay.p={i}": {
            "gates": _gates(), "shadow_spec": _spec(f"SYM{i}")} for i in range(2)}
        cure = {f"external.CURE{i}.pca_residual.c{i}": {
            "validity_pass": True, "failed_power_gates": ["deflated_sharpe"],
            "cell": f"external.CURE{i}.pca_residual.c{i}", "gates": _gates(),
            "shadow_spec": _spec(f"CURE{i}", family="pca_residual", selector="continuous")}
            for i in range(3)}
        base = _base(tmp_path, survivors, cure=cure)
        runs = sa.authorized_runs(base)
        n_ten = sum(1 for r in survivors.values() if gp.all_ten_pass(r["gates"]))
        assert len(runs) <= n_ten, (
            f"authorized_runs returned {len(runs)} from a canon holding {n_ten} ten-gate rows. "
            f"A count above the canon's is the 148-against-28 split returning.")
        assert {str(r["certificate"]) for r in runs} <= set(survivors), (
            "an admitted run names a certificate the canonical store does not hold")


class TestTheAuditNoLongerLaundersAnUnbackedClock:
    """`certificate_truth` is the organ that FINDS unbacked clocks; it was hiding 120."""

    @staticmethod
    def _reads_cure(fn_name: str) -> list[int]:
        """Lines inside `fn_name` where EXECUTABLE code reads the power-cure store.

        AST, never a text search, and this test learned that the hard way: the first version
        grepped the function's source segment and failed on the headstone comment that explains
        why the lane was deleted. That is the same mistake `check_forward_enrolment` documents at
        the top of its own scanner -- the record of a removal must not read as the removal being
        undone.
        """
        tree = ast.parse(TRUTH.read_text(encoding="utf-8"))
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"certificate_truth.{fn_name} has been renamed or removed"
        hits: list[int] = []
        for node in ast.walk(fn):
            # lane["cure_by_parts"]
            if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "cure_by_parts"):
                hits.append(node.lineno)
            # lane.get("cure_by_parts", ...)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "cure_by_parts"):
                hits.append(node.lineno)
        return sorted(set(hits))

    def test_classify_has_no_power_cure_escape(self) -> None:
        hits = self._reads_cure("classify")
        assert not hits, (
            f"`classify` reads the power-cure store again at line(s) {hits} and can return CURE "
            f"for a clock the canon does not back. That verdict counted as `cure_backed` rather "
            f"than as a divergence, so the audit whose whole purpose is to find unbacked clocks "
            f"was the organ concealing 120 of them.")

    def test_join_coverage_counts_only_the_canonical_lane_as_backed(self) -> None:
        hits = self._reads_cure("join_coverage")
        assert not hits, (
            f"`join_coverage` unions the power-cure store into `backed` again at line(s) "
            f"{hits}, so a row joining only that store counts as joining the canon and the "
            f"coverage number can never fall.")


class TestDeletingTheLaneIsNotACap:
    """Growth governance Rule 1: this removed a non-certificate lane, never an entitlement."""

    def test_enrolment_of_certificates_is_still_uncapped(self, tmp_path) -> None:
        """Forty certificates, forty runs. No budget, no ranking, no head-of-queue."""
        survivors = {f"external.S{i}.overnight_gap_decay.p={i}": {
            "gates": _gates(), "shadow_spec": _spec(f"S{i}")} for i in range(40)}
        runs = sa.authorized_runs(_base(tmp_path, survivors))
        assert len(runs) == 40, (
            f"{len(runs)} of 40 certificates admitted. Enrolment is uncapped forever (principal "
            f"2026-09-23): a forward clock gathers evidence and deploys no capital, so a quota "
            f"buys no safety and only costs hypotheses the desk can never rule on.")
