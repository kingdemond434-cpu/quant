"""A certificate that cannot enrol must say so by name, in the pass that refused it.

THE DEFECT, off the live dashboard 2026-09-05. Four certificates -- USDZAR, AUDCHF, CADCHF and
GBPCHF on overnight_gap_decay -- sat CERTIFIED-NOT-ENROLLED for 89, 115, 139 and 139 hours. The
same-day fence reported the breach correctly and the REASON existed nowhere: not in the shadow
log, not in an artifact, not on the dashboard.

`shadow_forward.certified_sleeves` is careful about this -- it logs an ENROL-GAP line for every
refusal it makes, and its own comment says "a silent skip is indistinguishable from enrolment that
works". But it can only refuse what it is HANDED, and `authorized_runs` dropped certificates one
function upstream with bare `continue`s. The care was taken at the second door while the first one
closed quietly.

The largest of those silent drops refuses the WHOLE canon on a gate-policy mismatch, and this desk
has already paid for it: `is_exact_policy`'s docstring records 2026-09-02, when 63 certificates
passed all ten gates, carried valid specs, and not one could enrol.

Certification and enrolment are one act (RESEARCH §6d). A door that closes without saying so
breaks that law quietly, and these tests fail if it starts closing quietly again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_UNSET = object()

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sa = pytest.importorskip("shadow_admission", reason="ships with the research package")
gp = pytest.importorskip("gate_policy", reason="ships with the research package")


def _passing_gates() -> dict:
    return {name: {"passed": True} for name in gp.GATES}


def _spec(symbol: str = "USDZAR", **over) -> dict:
    spec = {"symbol": symbol, "selector": "asia", "family": "overnight_gap_decay",
            "params": {}, "side": "LONG"}
    spec.update(over)
    return spec


def _canon(base: Path, survivors: dict, *, policy: object = _UNSET) -> Path:
    """Write a canon. Default policy is `gate_policy.ATTESTATION` itself -- the one value the
    exact-policy door accepts -- so these tests exercise the real door rather than a stand-in,
    and they follow the attestation automatically if it is ever revised."""
    rep = base / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    doc = {"survivors": survivors,
           "gate_policy": dict(gp.ATTESTATION) if policy is _UNSET else policy}
    (rep / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(doc), "utf-8")
    return base


def _exact_canon_or_skip(tmp_path: Path, survivors: dict) -> Path:
    """The canon the door accepts. Asserts rather than skips: a skipped test is not a test, and
    if the attestation ever stops round-tripping through JSON that is itself the finding."""
    base = _canon(tmp_path, survivors)
    doc = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    assert gp.is_exact_policy(doc.get("gate_policy")), (
        "gate_policy.ATTESTATION no longer survives a JSON round-trip, so no canon this desk "
        "writes could be accepted by its own door")
    return base


class TestTheCanonLevelRefusalIsAnnounced:
    def test_a_policy_mismatch_names_itself_and_the_count_it_refused(self, tmp_path) -> None:
        """The 2026-09-02 outage, made audible. One line refuses every certificate at once, so
        the symptom is "no new clocks" and the cause has to be stated or it is unfindable."""
        base = _canon(tmp_path, {"external.USDZAR.overnight_gap_decay.p=abc": {
            "gates": _passing_gates(), "shadow_spec": _spec()}},
            policy={"gates": ["not", "the", "ten"]})
        assert sa.authorized_runs(base, lanes=("h1",)) == []
        assert sa.DROPPED_CERTIFICATES, "the whole canon was refused with no report"
        why = sa.DROPPED_CERTIFICATES[0]["why"]
        # ASSERTED ON THE PROPERTY, NOT THE SENTENCE. The message gained the list of artifacts it
        # tried when the sealed canon became a fallback, and a fence pinned to one phrasing would
        # have to be edited every time the message got MORE useful.
        assert "attestation" in why
        assert "NOTHING can enrol" in why or "NO certificate can enrol" in why
        assert all(rel in why for rel, _ in sa.CANON_SOURCES), (
            "a whole-canon refusal must name every artifact it looked in")
        assert "1 survivor row" in sa.DROPPED_CERTIFICATES[0]["certificate"]


class TestPerCertificateDropsAreNamed:
    def test_a_certificate_with_no_shadow_spec_is_reported(self, tmp_path) -> None:
        base = _exact_canon_or_skip(tmp_path, {
            "external.USDZAR.overnight_gap_decay.p=abc": {"gates": _passing_gates()}})
        sa.authorized_runs(base, lanes=("h1",))
        named = {d["certificate"] for d in sa.DROPPED_CERTIFICATES}
        assert "external.USDZAR.overnight_gap_decay.p=abc" in named
        assert any("shadow_spec" in d["why"] for d in sa.DROPPED_CERTIFICATES)

    def test_a_certificate_with_unusable_params_is_reported_with_the_type(self, tmp_path) -> None:
        base = _exact_canon_or_skip(tmp_path, {
            "external.AUDCHF.overnight_gap_decay.p=abc": {
                "gates": _passing_gates(), "shadow_spec": _spec("AUDCHF", params=None)}})
        sa.authorized_runs(base, lanes=("h1",))
        assert any("params" in d["why"] and "NoneType" in d["why"]
                   for d in sa.DROPPED_CERTIFICATES), sa.DROPPED_CERTIFICATES

    def test_empty_params_is_a_parameterization_and_is_never_dropped(self, tmp_path) -> None:
        """`{}` is the complete parameterization "family defaults" -- byte-exactly what the
        gauntlet executed. Excluding it once already held two overnight_gap_decay certificates
        un-enrolled (2026-08-27), so this is pinned rather than left to a future reading."""
        base = _exact_canon_or_skip(tmp_path, {
            "external.CADCHF.overnight_gap_decay.p=abc": {
                "gates": _passing_gates(), "shadow_spec": _spec("CADCHF", params={})}})
        runs = sa.authorized_runs(base, lanes=("h1",))
        assert [r["symbol"] for r in runs] == ["CADCHF"]
        assert not sa.DROPPED_CERTIFICATES

    def test_an_uncertified_row_is_not_reported_as_a_drop(self, tmp_path) -> None:
        """Only a TEN-GATE PASS is owed a clock. Reporting every failing candidate here would
        bury the four certificates that matter under thousands of lines, which is how a report
        stops being read."""
        gates = _passing_gates()
        gates["pbo"] = {"passed": False}
        base = _exact_canon_or_skip(tmp_path, {
            "external.GBPCHF.overnight_gap_decay.p=abc": {"gates": gates}})
        sa.authorized_runs(base, lanes=("h1",))
        assert not sa.DROPPED_CERTIFICATES


class TestTheReportDescribesThisPass:
    def test_the_list_is_cleared_between_passes(self, tmp_path) -> None:
        bad = _exact_canon_or_skip(tmp_path / "bad", {
            "external.USDZAR.overnight_gap_decay.p=abc": {"gates": _passing_gates()}})
        sa.authorized_runs(bad, lanes=("h1",))
        assert sa.DROPPED_CERTIFICATES
        good = _exact_canon_or_skip(tmp_path / "good", {
            "external.USDZAR.overnight_gap_decay.p=abc": {
                "gates": _passing_gates(), "shadow_spec": _spec()}})
        sa.authorized_runs(good, lanes=("h1",))
        assert not sa.DROPPED_CERTIFICATES, "a healed pass still reported the previous pass's drop"

    def test_a_policy_refusal_also_clears_the_previous_pass(self, tmp_path) -> None:
        """The clear sits BEFORE the early return on purpose: a pass that refuses the canon must
        not leave the last pass's drops standing as if they were its own findings."""
        bad = _exact_canon_or_skip(tmp_path / "a", {
            "external.USDZAR.overnight_gap_decay.p=abc": {"gates": _passing_gates()}})
        sa.authorized_runs(bad, lanes=("h1",))
        before = list(sa.DROPPED_CERTIFICATES)
        assert before
        mismatch = _canon(tmp_path / "b", {}, policy={"gates": ["wrong"]})
        sa.authorized_runs(mismatch, lanes=("h1",))
        assert sa.DROPPED_CERTIFICATES != before
        assert len(sa.DROPPED_CERTIFICATES) == 1
